"""BrowserStack Automate adapter (Phase 25, task 25.01).

The adapter implements the SDK ``RunnerPlugin`` Protocol
(:mod:`sentinelqa.plugins`). The shape lets a third-party config opt
into BrowserStack via the Phase 24 plugin loader OR call the adapter
directly from a custom runner. SentinelQA does NOT auto-route audit
runs through BrowserStack; the engine remains location-agnostic
(CLAUDE.md §7).

CLAUDE.md §33: ``BROWSERSTACK_USERNAME`` and ``BROWSERSTACK_ACCESS_KEY``
are read from the environment at construction. They are never logged,
never written to disk, and never echoed in error messages. Quota
exhaustion surfaces as :class:`BrowserStackQuotaExceeded` rather than
an opaque HTTP error so the caller can fall back to a local runner.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar, Final

from integrations._http import (
    AuthHeader,
    HttpClient,
    IntegrationHttpError,
    RetrySpec,
)

BROWSERSTACK_API: Final[str] = "https://api.browserstack.com"
BROWSERSTACK_USER_ENV: Final[str] = "BROWSERSTACK_USERNAME"
BROWSERSTACK_KEY_ENV: Final[str] = "BROWSERSTACK_ACCESS_KEY"
DEFAULT_PROJECT: Final[str] = "sentinelqa"

# Allowed Playwright browser names that map to BrowserStack capabilities.
# BrowserStack Playwright support is "playwright-chromium", "playwright-firefox",
# "playwright-webkit". Anything else is a config error.
_SUPPORTED_BROWSERS: Final[frozenset[str]] = frozenset({"chromium", "firefox", "webkit"})

logger = logging.getLogger("sentinelqa.integrations.browserstack")


class BrowserStackQuotaExceededError(RuntimeError):
    """Raised (or returned in run() outcome) when the account is at quota."""


# Backwards-friendly alias kept so existing call-sites can still
# `except BrowserStackQuotaExceeded:`. The canonical class name is the
# ``Error`` suffix (CLAUDE.md §32 / ruff N818).
BrowserStackQuotaExceeded = BrowserStackQuotaExceededError


@dataclass(frozen=True)
class BrowserStackCredentials:
    """Resolved credentials. Never logged."""

    username: str
    access_key: str

    @classmethod
    def from_env(
        cls,
        *,
        username_env: str = BROWSERSTACK_USER_ENV,
        access_key_env: str = BROWSERSTACK_KEY_ENV,
        environ: Mapping[str, str] | None = None,
    ) -> BrowserStackCredentials:
        env = environ if environ is not None else os.environ
        username = (env.get(username_env) or "").strip()
        access_key = (env.get(access_key_env) or "").strip()
        if not username or not access_key:
            raise BrowserStackConfigError(
                f"BrowserStack adapter requires both {username_env!r} and "
                f"{access_key_env!r} to be set."
            )
        return cls(username=username, access_key=access_key)


class BrowserStackConfigError(ValueError):
    """Raised on missing credentials or unsupported capability inputs."""


def map_capabilities(
    *,
    browser: str,
    headless: bool,
    project: str = DEFAULT_PROJECT,
    build: str | None = None,
    name: str | None = None,
    os_name: str | None = None,
    os_version: str | None = None,
    viewport: tuple[int, int] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Translate SentinelQA-shaped capabilities into a BrowserStack payload.

    The return value follows BrowserStack's Playwright capability layout
    ("browserstack:options" sidecar). Deterministic for the given input
    so goldens / integration tests can assert byte equality.
    """

    browser_lc = browser.lower()
    if browser_lc not in _SUPPORTED_BROWSERS:
        raise BrowserStackConfigError(
            f"BrowserStack capability mapping: unsupported browser {browser!r}; "
            f"expected one of {sorted(_SUPPORTED_BROWSERS)}."
        )

    bstack_options: dict[str, Any] = {
        "projectName": project,
        "sessionName": name or f"sentinelqa-{browser_lc}",
        "playwrightVersion": "1.49.0",
        "local": False,
    }
    if build is not None:
        bstack_options["buildName"] = build
    if os_name is not None:
        bstack_options["os"] = os_name
    if os_version is not None:
        bstack_options["osVersion"] = os_version

    capabilities: dict[str, Any] = {
        "browser": f"playwright-{browser_lc}",
        "browser_version": "latest",
        "headless": bool(headless),
        "browserstack.options": bstack_options,
    }
    if viewport is not None:
        width, height = viewport
        if width <= 0 or height <= 0:
            raise BrowserStackConfigError(
                f"BrowserStack capability mapping: viewport {viewport!r} must be positive."
            )
        capabilities["viewport"] = {"width": int(width), "height": int(height)}
    if extra:
        capabilities.update(dict(extra))
    return capabilities


class BrowserStackRunner:
    """``RunnerPlugin``-shaped adapter for BrowserStack Automate."""

    kind: ClassVar[str] = "runner"
    name: ClassVar[str] = "browserstack"
    version: ClassVar[str] = "1.0.0"
    capabilities: ClassVar[frozenset[str]] = frozenset({"remote-browser"})
    permissions: ClassVar[frozenset[str]] = frozenset(
        {
            "network.outbound",
            f"env.read:{BROWSERSTACK_USER_ENV}",
            f"env.read:{BROWSERSTACK_KEY_ENV}",
        }
    )

    def __init__(
        self,
        *,
        credentials: BrowserStackCredentials,
        project: str = DEFAULT_PROJECT,
        client: HttpClient | None = None,
        retry: RetrySpec | None = None,
    ) -> None:
        self._credentials = credentials
        self._project = project
        self._client = client or HttpClient(
            auth=AuthHeader.basic(credentials.username, credentials.access_key),
            retry=retry,
        )

    # ------------------------------------------------------------------
    # RunnerPlugin protocol surface
    # ------------------------------------------------------------------

    def run(
        self,
        invocation: Mapping[str, Any],
        context: Any,
    ) -> Mapping[str, Any]:
        """Submit a runner invocation to BrowserStack.

        ``invocation`` is the same opaque mapping the local / Docker
        runners receive (Phase 08); the adapter pulls the fields it
        needs (browser, headless, build) and ignores the rest.

        Returns a deterministic outcome dict shaped like::

            {
              "status": "submitted" | "quota_exceeded",
              "session_id": "...",
              "build_id": "...",
              "capabilities": {...},
              "traces": [{"url": "..."}, ...],
            }

        Trace upload is best-effort: if BrowserStack returns 429 the
        outcome's ``status`` is ``"quota_exceeded"`` rather than an
        exception, so callers can degrade gracefully.
        """

        browser = str(invocation.get("browser", "chromium"))
        headless = bool(invocation.get("headless", True))
        build = invocation.get("build") or invocation.get("run_id")
        capabilities = map_capabilities(
            browser=browser,
            headless=headless,
            project=self._project,
            build=str(build) if build is not None else None,
            name=invocation.get("test_name"),
        )

        try:
            session = self._create_session(capabilities=capabilities)
        except BrowserStackQuotaExceeded:
            logger.warning("browserstack: quota exceeded; returning degraded outcome")
            return {
                "status": "quota_exceeded",
                "session_id": "",
                "build_id": "",
                "capabilities": capabilities,
                "traces": [],
            }

        trace_paths = list(invocation.get("trace_paths") or [])
        traces: list[dict[str, str]] = []
        for trace_path in trace_paths:
            try:
                uploaded = self._upload_trace(
                    session_id=session["session_id"],
                    trace_path=str(trace_path),
                )
                traces.append(uploaded)
            except BrowserStackQuotaExceeded:
                logger.warning(
                    "browserstack: trace upload quota exceeded; " "remaining traces dropped"
                )
                break
            except IntegrationHttpError as exc:
                # Trace upload failures must not crash the runner;
                # surface them in the outcome and continue.
                logger.warning("browserstack: trace upload failed: %s", exc)

        return {
            "status": "submitted",
            "session_id": session["session_id"],
            "build_id": session.get("build_id", ""),
            "capabilities": capabilities,
            "traces": traces,
        }

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    def _create_session(self, *, capabilities: Mapping[str, Any]) -> dict[str, Any]:
        url = f"{BROWSERSTACK_API}/automate/sessions.json"
        try:
            response = self._client.post_json(url, {"capabilities": dict(capabilities)})
        except IntegrationHttpError as exc:
            if "HTTP 429" in str(exc):
                raise BrowserStackQuotaExceeded(str(exc)) from exc
            raise
        if not isinstance(response, Mapping):
            raise IntegrationHttpError(
                "browserstack: create-session response was not a JSON object"
            )
        session_id = response.get("automation_session", {}).get("hashed_id") or response.get(
            "session_id"
        )
        build_id = response.get("automation_session", {}).get("build_hashed_id") or response.get(
            "build_id"
        )
        if not session_id:
            raise IntegrationHttpError("browserstack: create-session response lacked a session id")
        return {"session_id": str(session_id), "build_id": str(build_id or "")}

    def _upload_trace(self, *, session_id: str, trace_path: str) -> dict[str, str]:
        url = f"{BROWSERSTACK_API}/automate/sessions/{session_id}/screenshots/upload.json"
        try:
            response = self._client.post_json(url, {"trace_path": trace_path})
        except IntegrationHttpError as exc:
            if "HTTP 429" in str(exc):
                raise BrowserStackQuotaExceeded(str(exc)) from exc
            raise
        if not isinstance(response, Mapping):
            raise IntegrationHttpError("browserstack: trace-upload response was not a JSON object")
        return {"url": str(response.get("url", "")), "session_id": session_id}


__all__ = [
    "BrowserStackConfigError",
    "BrowserStackCredentials",
    "BrowserStackQuotaExceeded",
    "BrowserStackRunner",
    "BROWSERSTACK_API",
    "BROWSERSTACK_KEY_ENV",
    "BROWSERSTACK_USER_ENV",
    "DEFAULT_PROJECT",
    "map_capabilities",
]

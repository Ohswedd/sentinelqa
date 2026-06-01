"""Sauce Labs adapter (, ).

Same shape as the BrowserStack adapter : the class is
``RunnerPlugin``-shaped (:mod:`sentinelqa.plugins`); it is NOT
auto-wired into ``sentinel audit``; credentials read
from the environment, never logged.

The Sauce Labs Playwright endpoint sits under
``us-west-1.saucelabs.com``; the adapter exposes the region as a
constructor argument so EU / APAC accounts can override it without
touching the source.
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

SAUCELABS_API_TEMPLATE: Final[str] = "https://api.{region}.saucelabs.com"
SAUCE_USER_ENV: Final[str] = "SAUCE_USERNAME"
SAUCE_KEY_ENV: Final[str] = "SAUCE_ACCESS_KEY"
DEFAULT_PROJECT: Final[str] = "sentinelqa"
DEFAULT_REGION: Final[str] = "us-west-1"

# Sauce supports Playwright across the same three browsers BrowserStack does.
_SUPPORTED_BROWSERS: Final[frozenset[str]] = frozenset({"chromium", "firefox", "webkit"})
_SUPPORTED_REGIONS: Final[frozenset[str]] = frozenset(
    {"us-west-1", "eu-central-1", "apac-southeast-1"}
)

logger = logging.getLogger("sentinelqa.integrations.saucelabs")


class SauceLabsQuotaExceededError(RuntimeError):
    """Raised (or surfaced in run() outcome) when the account is at quota."""


# Friendly alias kept for call-site ergonomics; canonical class name
# carries the ``Error`` suffix per our engineering rules / ruff N818.
SauceLabsQuotaExceeded = SauceLabsQuotaExceededError


class SauceLabsConfigError(ValueError):
    """Raised on missing credentials or unsupported capability inputs."""


@dataclass(frozen=True)
class SauceLabsCredentials:
    """Resolved Sauce Labs credentials. Never logged."""

    username: str
    access_key: str

    @classmethod
    def from_env(
        cls,
        *,
        username_env: str = SAUCE_USER_ENV,
        access_key_env: str = SAUCE_KEY_ENV,
        environ: Mapping[str, str] | None = None,
    ) -> SauceLabsCredentials:
        env = environ if environ is not None else os.environ
        username = (env.get(username_env) or "").strip()
        access_key = (env.get(access_key_env) or "").strip()
        if not username or not access_key:
            raise SauceLabsConfigError(
                f"Sauce Labs adapter requires both {username_env!r} and "
                f"{access_key_env!r} to be set."
            )
        return cls(username=username, access_key=access_key)


def map_capabilities(
    *,
    browser: str,
    headless: bool,
    project: str = DEFAULT_PROJECT,
    build: str | None = None,
    name: str | None = None,
    tunnel_identifier: str | None = None,
    viewport: tuple[int, int] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Translate SentinelQA-shaped capabilities into a Sauce Labs payload.

    Sauce expects W3C capabilities with a ``sauce:options`` sidecar.
    Deterministic for the given input so integration tests can assert
    byte equality.
    """

    browser_lc = browser.lower()
    if browser_lc not in _SUPPORTED_BROWSERS:
        raise SauceLabsConfigError(
            f"Sauce Labs capability mapping: unsupported browser {browser!r}; "
            f"expected one of {sorted(_SUPPORTED_BROWSERS)}."
        )

    sauce_options: dict[str, Any] = {
        "name": name or f"sentinelqa-{browser_lc}",
        "build": build or "sentinelqa-untagged",
        "tags": [project],
    }
    if tunnel_identifier is not None:
        sauce_options["tunnelIdentifier"] = tunnel_identifier

    capabilities: dict[str, Any] = {
        "browserName": browser_lc,
        "browserVersion": "latest",
        "platformName": "Windows 11",
        "sauce:options": sauce_options,
        "headless": bool(headless),
    }
    if viewport is not None:
        width, height = viewport
        if width <= 0 or height <= 0:
            raise SauceLabsConfigError(
                f"Sauce Labs capability mapping: viewport {viewport!r} must be positive."
            )
        capabilities["viewport"] = {"width": int(width), "height": int(height)}
    if extra:
        capabilities.update(dict(extra))
    return capabilities


def _resolve_region(region: str) -> str:
    if region not in _SUPPORTED_REGIONS:
        raise SauceLabsConfigError(
            f"Sauce Labs region {region!r} not supported; "
            f"expected one of {sorted(_SUPPORTED_REGIONS)}."
        )
    return region


class SauceLabsRunner:
    """``RunnerPlugin``-shaped adapter for Sauce Labs Playwright runs."""

    kind: ClassVar[str] = "runner"
    name: ClassVar[str] = "saucelabs"
    version: ClassVar[str] = "1.0.0"
    capabilities: ClassVar[frozenset[str]] = frozenset({"remote-browser"})
    permissions: ClassVar[frozenset[str]] = frozenset(
        {
            "network.outbound",
            f"env.read:{SAUCE_USER_ENV}",
            f"env.read:{SAUCE_KEY_ENV}",
        }
    )

    def __init__(
        self,
        *,
        credentials: SauceLabsCredentials,
        project: str = DEFAULT_PROJECT,
        region: str = DEFAULT_REGION,
        client: HttpClient | None = None,
        retry: RetrySpec | None = None,
    ) -> None:
        self._credentials = credentials
        self._project = project
        self._region = _resolve_region(region)
        self._api_base = SAUCELABS_API_TEMPLATE.format(region=self._region)
        self._client = client or HttpClient(
            auth=AuthHeader.basic(credentials.username, credentials.access_key),
            retry=retry,
        )

    @property
    def api_base(self) -> str:
        return self._api_base

    # ------------------------------------------------------------------
    # RunnerPlugin protocol surface
    # ------------------------------------------------------------------

    def run(
        self,
        invocation: Mapping[str, Any],
        context: Any,
    ) -> Mapping[str, Any]:
        """Submit a runner invocation to Sauce Labs.

        ``invocation`` is the same opaque mapping the local / Docker
        runners receive ; the adapter consumes the fields it
        needs.

        Returns a deterministic outcome::

        {
        "status": "submitted" | "quota_exceeded",
        "job_id": "...",
        "region": "us-west-1",
        "capabilities": {...},
        "artifacts": [{"name": "...", "url": "..."},...],
        }
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
            tunnel_identifier=invocation.get("tunnel_identifier"),
        )

        try:
            job = self._create_job(capabilities=capabilities)
        except SauceLabsQuotaExceeded:
            logger.warning("saucelabs: quota exceeded; returning degraded outcome")
            return {
                "status": "quota_exceeded",
                "job_id": "",
                "region": self._region,
                "capabilities": capabilities,
                "artifacts": [],
            }

        trace_paths = list(invocation.get("trace_paths") or [])
        artifacts: list[dict[str, str]] = []
        for trace_path in trace_paths:
            try:
                uploaded = self._upload_artifact(
                    job_id=job["job_id"],
                    artifact_path=str(trace_path),
                )
                artifacts.append(uploaded)
            except SauceLabsQuotaExceeded:
                logger.warning(
                    "saucelabs: artifact upload quota exceeded; " "remaining artifacts dropped"
                )
                break
            except IntegrationHttpError as exc:
                logger.warning("saucelabs: artifact upload failed: %s", exc)

        return {
            "status": "submitted",
            "job_id": job["job_id"],
            "region": self._region,
            "capabilities": capabilities,
            "artifacts": artifacts,
        }

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    def _create_job(self, *, capabilities: Mapping[str, Any]) -> dict[str, str]:
        url = f"{self._api_base}/rest/v1/{self._credentials.username}/jobs"
        try:
            response = self._client.post_json(url, {"capabilities": dict(capabilities)})
        except IntegrationHttpError as exc:
            if "HTTP 429" in str(exc):
                raise SauceLabsQuotaExceeded(str(exc)) from exc
            raise
        if not isinstance(response, Mapping):
            raise IntegrationHttpError("saucelabs: create-job response was not a JSON object")
        job_id = response.get("id") or response.get("job_id")
        if not job_id:
            raise IntegrationHttpError("saucelabs: create-job response lacked a job id")
        return {"job_id": str(job_id)}

    def _upload_artifact(self, *, job_id: str, artifact_path: str) -> dict[str, str]:
        url = (
            f"{self._api_base}/rest/v1/{self._credentials.username}" f"/jobs/{job_id}/assets/upload"
        )
        try:
            response = self._client.post_json(url, {"path": artifact_path})
        except IntegrationHttpError as exc:
            if "HTTP 429" in str(exc):
                raise SauceLabsQuotaExceeded(str(exc)) from exc
            raise
        if not isinstance(response, Mapping):
            raise IntegrationHttpError("saucelabs: artifact-upload response was not a JSON object")
        return {
            "name": str(response.get("name", artifact_path)),
            "url": str(response.get("url", "")),
        }


__all__ = [
    "DEFAULT_PROJECT",
    "DEFAULT_REGION",
    "SAUCELABS_API_TEMPLATE",
    "SAUCE_KEY_ENV",
    "SAUCE_USER_ENV",
    "SauceLabsConfigError",
    "SauceLabsCredentials",
    "SauceLabsQuotaExceeded",
    "SauceLabsRunner",
    "map_capabilities",
]

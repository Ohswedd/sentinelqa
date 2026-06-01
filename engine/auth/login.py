"""Interactive sign-in flow (Phase 31, Task 31.02).

The CLI command ``sentinel auth login`` calls :func:`capture_session` to
launch a headed Playwright browser, wait for the operator to sign in
manually, capture ``storage_state``, encrypt it into the vault, and emit
a redacted audit-log entry. Everything Playwright-related is gated by a
single optional import — the unit tests substitute the launcher via
:class:`BrowserLauncher` so the suite doesn't need Chromium.

our engineering rules hard rules enforced here:

- The operator signs in. SentinelQA never reads credentials.
- If the post-login URL host doesn't match the start URL host AND isn't
  on the operator's allowlist, the flow refuses to capture (raises
  :class:`engine.errors.base.LoginOriginChangedError`).
- CI mode is forbidden — the flow needs a real human.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol
from urllib.parse import urlparse

from engine.auth.models import DEFAULT_TTL_HOURS, VaultEntry
from engine.auth.profiles import AuthProfile
from engine.auth.vault import Vault
from engine.errors.base import (
    AuthCommandForbiddenInCiError,
    LoginOriginChangedError,
)
from engine.policy.audit_log import write_audit_entry

BrowserName = Literal["chromium", "firefox", "webkit"]


@dataclass(frozen=True)
class LoginRequest:
    """Inputs from the CLI."""

    name: str
    login_url: str
    target_host: str
    allowed_hosts: tuple[str, ...]
    profile: AuthProfile | None = None
    browser: BrowserName = "chromium"
    ttl_hours: int = DEFAULT_TTL_HOURS
    force: bool = False
    ci: bool = False
    audit_log_path: Path | None = None


@dataclass
class LoginResult:
    """What :func:`capture_session` returns to the CLI."""

    entry: VaultEntry
    vault_path: Path
    landed_url: str


class BrowserLauncher(Protocol):
    """The slice of Playwright we need.

    A real launcher proxies to :mod:`playwright.sync_api`. The unit
    tests substitute a no-network double.
    """

    def capture(
        self,
        *,
        login_url: str,
        browser: BrowserName,
        confirm: Callable[[str], str],
    ) -> tuple[dict[str, Any], str]:
        """Open a headed browser, wait, return (storage_state, landed_url)."""


def _default_confirm(prompt: str) -> str:
    """Read one line from stdin (used to wait for the operator)."""

    sys.stderr.write(prompt)
    sys.stderr.flush()
    return sys.stdin.readline().strip()


def capture_session(
    request: LoginRequest,
    *,
    vault: Vault,
    launcher: BrowserLauncher,
    confirm: Callable[[str], str] | None = None,
    now: datetime | None = None,
) -> LoginResult:
    """Drive the interactive capture flow end-to-end."""

    if request.ci:
        raise AuthCommandForbiddenInCiError(command="login")

    confirmer = confirm or _default_confirm

    start_host = (urlparse(request.login_url).hostname or "").lower()
    if not start_host:
        raise ValueError(f"login_url is missing a host: {request.login_url!r}")

    banner = _banner(request.login_url, request.profile)
    sys.stderr.write(banner)
    sys.stderr.flush()

    storage_state, landed_url = launcher.capture(
        login_url=request.login_url,
        browser=request.browser,
        confirm=confirmer,
    )

    landed_host = (urlparse(landed_url).hostname or "").lower()
    if landed_host and landed_host != start_host:
        # Cross-origin redirect: the operator either landed on an IdP
        # they expected, in which case the IdP host needs to be on the
        # allowlist, or something went wrong (phishing redirect). We
        # refuse to capture unless the host is allowlisted.
        allowed_lower = {h.strip().lower() for h in request.allowed_hosts}
        if landed_host not in allowed_lower:
            raise LoginOriginChangedError(
                landed_host=landed_host,
                start_host=start_host,
                technical_context={
                    "landed_host": landed_host,
                    "start_host": start_host,
                    "allowed_hosts": sorted(allowed_lower),
                },
            )

    storage_state_json = json.dumps(storage_state, separators=(",", ":"), sort_keys=True)
    captured_at = now or datetime.now(UTC)
    entry = VaultEntry.from_storage_state(
        name=request.name,
        host=request.target_host.lower(),
        storage_state=storage_state,
        storage_state_json=storage_state_json,
        created_at=captured_at,
        ttl_hours=request.ttl_hours,
        captured_by="cli",
    )
    vault_path = vault.put(entry, force=request.force)

    if request.audit_log_path is not None:
        write_audit_entry(
            request.audit_log_path,
            {
                "event": "auth.login",
                "host": entry.host,
                "name": entry.name,
                "browser": request.browser,
                "captured_cookies_count": entry.cookies_count,
                "captured_localstorage_count": entry.local_storage_keys,
                "ttl_hours": request.ttl_hours,
                "profile": request.profile.name if request.profile else None,
                "landed_host": landed_host,
            },
        )

    return LoginResult(entry=entry, vault_path=vault_path, landed_url=landed_url)


def _banner(login_url: str, profile: AuthProfile | None) -> str:
    lines = [
        "",
        "SentinelQA opened a real browser at " + login_url,
        "Sign in with your own credentials. SentinelQA NEVER sees them.",
        "When sign-in is complete, this CLI captures the session and",
        "encrypts it locally. The session is stored under your home",
        "directory (~/.sentinel/auth/) and never transmitted off this",
        "machine by SentinelQA.",
    ]
    if profile is not None:
        lines.append("")
        lines.append(f"Profile: {profile.label}")
        if profile.mfa_hint:
            lines.append(f"  MFA:   {profile.mfa_hint}")
        lines.append(f"  ToS:   {profile.tos_url}")
    lines.append("")
    lines.append("Press Enter once you see the post-login screen.")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Optional Playwright-backed launcher (real implementation)
# ---------------------------------------------------------------------------


class PlaywrightLauncher:
    """Production launcher. Imports Playwright lazily on first use.

    Construct without arguments. The unit tests do NOT construct this
    class — they pass a stub :class:`BrowserLauncher` to
    :func:`capture_session` directly.
    """

    def capture(
        self,
        *,
        login_url: str,
        browser: BrowserName,
        confirm: Callable[[str], str],
    ) -> tuple[dict[str, Any], str]:
        try:
            from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - exercised at runtime only
            raise RuntimeError(
                "Playwright is required for `sentinel auth login`. "
                "Install it with `pnpm --filter @sentinelqa/ts-runtime exec "
                "playwright install` or `pip install playwright && "
                "playwright install`."
            ) from exc
        with sync_playwright() as p:  # pragma: no cover - browser path
            browser_type = {
                "chromium": p.chromium,
                "firefox": p.firefox,
                "webkit": p.webkit,
            }[browser]
            launched = browser_type.launch(headless=False)
            context = launched.new_context()
            page = context.new_page()
            page.goto(login_url)
            confirm("Press Enter once you see the post-login screen: ")
            landed_url = page.url
            state = context.storage_state()
            context.close()
            launched.close()
            return dict(state), landed_url


def host_pair_from_login_url(login_url: str, target_host: str | None) -> str:
    """Return the host to record in the vault.

    Use ``target_host`` if explicitly provided; otherwise derive from
    ``login_url``. Used by the CLI before calling :func:`capture_session`.
    """

    if target_host:
        return target_host.strip().lower()
    parsed = urlparse(login_url)
    if not parsed.hostname:
        raise ValueError(f"login_url is missing a host: {login_url!r}")
    return parsed.hostname.lower()


def hosts_iterable(target_host: str, allowed_hosts: Iterable[str]) -> tuple[str, ...]:
    """Return the de-duplicated lower-case host set."""

    out = {target_host.lower()}
    for h in allowed_hosts:
        if h:
            out.add(h.strip().lower())
    return tuple(sorted(out))


__all__ = [
    "BrowserLauncher",
    "BrowserName",
    "LoginRequest",
    "LoginResult",
    "PlaywrightLauncher",
    "capture_session",
    "host_pair_from_login_url",
    "hosts_iterable",
]

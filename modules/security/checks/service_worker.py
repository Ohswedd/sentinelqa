# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Service-worker audit (v1.3.0).

PWAs ship service workers; the existing security module doesn't audit
them. This module covers three categories of risk:

* **Registration**: presence + scope. A SW registered at the wrong
  scope can intercept far more than the developer expects.
* **Cache integrity**: aggressive ``CacheFirst`` or
  ``StaleWhileRevalidate`` strategies on sensitive endpoints can
  serve cross-session data.
* **Push permission flow**: requesting ``Notification.requestPermission``
  on page-load is the most-disliked PWA anti-pattern.

Detection is pure source inspection of the registered SW script and
the HTML around it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

Severity = Literal["critical", "high", "medium", "low", "info"]


@dataclass(frozen=True, slots=True)
class ServiceWorkerInfo:
    """Whatever discovery scraped about a registered SW."""

    registered: bool
    script_url: str | None = None
    scope: str | None = None
    script_body: str | None = None


@dataclass(frozen=True, slots=True)
class ServiceWorkerFinding:
    code: str
    severity: Severity
    rationale: str
    suggested_fix: str = ""


_REGISTER_RE = re.compile(
    r"navigator\.serviceWorker\.register\s*\(\s*['\"]([^'\"]+)['\"](?:\s*,\s*\{[^}]*scope\s*:\s*['\"]([^'\"]+)['\"])?",
)
_NOTIFY_RE = re.compile(r"Notification\.requestPermission\s*\(")

# Strategies that should never apply to /api/, /me, etc.
_RISKY_PATTERNS: Final[tuple[str, ...]] = (
    "CacheFirst",
    "StaleWhileRevalidate",
    "cacheFirst",
    "staleWhileRevalidate",
)
_SENSITIVE_PATH_RE = re.compile(
    r"['\"]([^'\"]*(?:/api/|/me|/user|/account|/auth)[^'\"]*)['\"]",
    re.IGNORECASE,
)


def detect_service_worker(html: str) -> ServiceWorkerInfo:
    """Walk the HTML and find a ``serviceWorker.register(...)`` call."""

    match = _REGISTER_RE.search(html)
    if match is None:
        return ServiceWorkerInfo(registered=False)
    return ServiceWorkerInfo(
        registered=True,
        script_url=match.group(1),
        scope=match.group(2),
    )


def evaluate_service_worker(
    info: ServiceWorkerInfo,
    *,
    page_origin: str,
    page_html_for_push_check: str = "",
) -> tuple[ServiceWorkerFinding, ...]:
    """Return findings for the service worker's surface."""

    out: list[ServiceWorkerFinding] = []
    if not info.registered:
        return tuple(out)

    # 1) Scope above root is the classic PWA mistake.
    if info.scope and info.scope == "/":
        # Root scope is fine; this is the documented default.
        pass
    elif info.scope and info.scope.count("/") > 3:
        out.append(
            ServiceWorkerFinding(
                code="SW-SCOPE-TOO-NARROW",
                severity="low",
                rationale=(
                    f"Service worker scope ``{info.scope}`` is several "
                    "directories deep. Confirm this matches the user-visible "
                    "PWA surface; misconfigured scopes can mean the SW is "
                    "active for fewer pages than expected."
                ),
                suggested_fix="Re-register at the broadest needed scope.",
            )
        )

    # 2) Push notification permission on page load.
    if _NOTIFY_RE.search(page_html_for_push_check):
        out.append(
            ServiceWorkerFinding(
                code="SW-PUSH-PROMPT-EAGER",
                severity="medium",
                rationale=(
                    "``Notification.requestPermission`` was called from the "
                    "page itself rather than from a user gesture. Browsers "
                    "block this; Chrome counts it against the site's "
                    "Permission UX score."
                ),
                suggested_fix=(
                    "Trigger the permission prompt only from an explicit " "button click."
                ),
            )
        )

    # 3) Risky cache strategies on sensitive endpoints.
    if info.script_body:
        for strategy in _RISKY_PATTERNS:
            if strategy not in info.script_body:
                continue
            window = _slice_around(info.script_body, strategy)
            sensitive_paths = _SENSITIVE_PATH_RE.findall(window)
            for path in sensitive_paths:
                out.append(
                    ServiceWorkerFinding(
                        code="SW-CACHE-SENSITIVE",
                        severity="high",
                        rationale=(
                            f"Strategy ``{strategy}`` is applied to "
                            f"``{path}``. Sensitive endpoints must use "
                            "``NetworkOnly`` to avoid cross-session leakage."
                        ),
                        suggested_fix="Switch to NetworkOnly for /api/ + /me.",
                    )
                )
                break  # one finding per strategy hit is enough

    _ = page_origin
    return tuple(out)


# end


def _slice_around(text: str, needle: str, window: int = 400) -> str:
    idx = text.find(needle)
    if idx == -1:
        return ""
    return text[max(0, idx - window) : idx + window]


__all__ = [
    "ServiceWorkerFinding",
    "ServiceWorkerInfo",
    "detect_service_worker",
    "evaluate_service_worker",
]

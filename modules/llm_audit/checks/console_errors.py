"""LLM-CONSOLE-ERROR-IGNORED + LLM-UNHANDLED-PROMISE (task 19.13).

Pure function over :class:`ConsoleEntry` records. We aggregate per
route. Third-party analytics / ads noise can be filtered via
``third_party_hosts``; entries whose ``source_url`` matches the host
list are dropped.

Findings:

* ``LLM-CONSOLE-ERROR-IGNORED`` — a ``level=='error'`` entry was
  captured while the UI reported success on the same route.
* ``LLM-UNHANDLED-PROMISE`` — any entry flagged as
  ``is_unhandled_rejection``.
"""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlparse

from modules.llm_audit.findings import CheckFinding
from modules.llm_audit.models import ConsoleEntry
from modules.llm_audit.rules import LLM_CONSOLE_ERROR_IGNORED, LLM_UNHANDLED_PROMISE


def check_console_errors(
    entries: Iterable[ConsoleEntry],
    *,
    third_party_hosts: Iterable[str] = (),
) -> tuple[CheckFinding, ...]:
    """Return console / unhandled-rejection findings.

    Always returns at most one ``LLM-CONSOLE-ERROR-IGNORED`` finding
    per route, with the first matching entry's snippet; unhandled
    rejections emit one finding per occurrence so distinct stack traces
    stay distinguishable.
    """

    host_blocklist = tuple(third_party_hosts)
    seen_routes: set[str] = set()
    findings: list[CheckFinding] = []
    for entry in entries:
        if _is_third_party(entry.source_url, host_blocklist):
            continue
        if entry.is_unhandled_rejection:
            findings.append(
                CheckFinding(
                    rule_id=LLM_UNHANDLED_PROMISE.id,
                    title=f"Unhandled promise rejection on {entry.route_url}",
                    description=(
                        f"The runner observed an unhandled promise rejection on "
                        f"{entry.route_url}: {entry.text[:200]}"
                    ),
                    route=entry.route_url,
                    snippet=entry.text,
                )
            )
            continue
        if entry.level != "error":
            continue
        if not entry.ui_reported_success:
            continue
        if entry.route_url in seen_routes:
            continue
        seen_routes.add(entry.route_url)
        findings.append(
            CheckFinding(
                rule_id=LLM_CONSOLE_ERROR_IGNORED.id,
                title=f"Console error on {entry.route_url} ignored by UI",
                description=(
                    f"The console emitted an error on {entry.route_url} "
                    "while the UI reported success: "
                    f"{entry.text[:200]}"
                ),
                route=entry.route_url,
                snippet=entry.text,
            )
        )
    return tuple(findings)


def _is_third_party(source_url: str | None, hosts: tuple[str, ...]) -> bool:
    if not source_url or not hosts:
        return False
    parsed = urlparse(source_url)
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    for blocked in hosts:
        blocked_host = blocked.lower().lstrip(".")
        if host == blocked_host or host.endswith("." + blocked_host):
            return True
    return False


__all__ = ["check_console_errors"]

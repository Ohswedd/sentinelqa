"""Findings v1 → v2 migration (Phase 32 / ADR-0044).

v2 adds three optional taxonomy ids — ``cwe_id``, ``attack_id``,
``owasp_api_id`` — and bumps the envelope's ``schema_version`` from
``"1"`` to ``"2"``. The Pydantic :class:`engine.domain.finding.Finding`
model accepts a v1 dict as-is because all three new fields default to
``None``; this migration is the canonical, explicit upgrade for
callers that want to persist a v1 input back as a v2 document
(re-stamping ``schema_version`` and stamping the three taxonomy keys
as ``null``).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from engine.domain.migrations import MIGRATIONS

ARTIFACT = "findings"
FROM_VERSION = "1"
TO_VERSION = "2"


_NEW_FIELDS: tuple[str, ...] = ("cwe_id", "attack_id", "owasp_api_id")


def _upgrade_finding(finding: dict[str, Any]) -> dict[str, Any]:
    upgraded = dict(finding)
    for key in _NEW_FIELDS:
        upgraded.setdefault(key, None)
    upgraded["schema_version"] = TO_VERSION
    return upgraded


def migrate(data: dict[str, Any]) -> dict[str, Any]:
    """Return a v2 wire dict given a v1 wire dict.

    Accepts either the top-level envelope (``{"schema_version": "1",
    "findings": [...]}``) or a single Finding dict. Idempotent on v2
    input.
    """

    if data.get("schema_version") == TO_VERSION:
        return dict(data)

    if "findings" in data and isinstance(data["findings"], Iterable):
        out = dict(data)
        out["schema_version"] = TO_VERSION
        out["findings"] = [_upgrade_finding(f) for f in data["findings"]]
        return out

    return _upgrade_finding(data)


MIGRATIONS[(ARTIFACT, FROM_VERSION, TO_VERSION)] = migrate


__all__ = ["ARTIFACT", "FROM_VERSION", "TO_VERSION", "migrate"]

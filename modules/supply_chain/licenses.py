"""SPDX license audit (Phase 33.06, ADR-0045).

For every component in the SBOM, resolve the declared license (when
present), match it against the configured allow / deny lists, and emit
one :class:`LicenseEntry` per component. Components whose license is
missing or unknown surface as ``verdict="unknown"`` with the configured
severity (default ``low``), per the Phase 33 README.

Resolution policy:

- npm components carry their license in ``packages/<path>/license``
  inside ``package-lock.json``; we already keep that on the SBOM
  component when present.
- PyPI components don't expose license info in the lockfile, so by
  default they resolve to ``unknown`` unless the operator extends the
  SBOM with explicit license data later. This is intentionally
  conservative — the alternative (fetching PyPI metadata over the
  network) would break the Phase 33 offline guarantee.

Allowlist / denylist semantics:

- An empty allowlist means "no SPDX whitelisting policy"; only the
  denylist gates findings.
- A non-empty allowlist + non-empty denylist: deny wins on overlap.
- Unknown ids default to the configured ``unknown_severity``.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime

from engine.domain.finding import Severity

from modules.supply_chain.models import (
    LicenseEntry,
    LicenseReport,
    LicenseVerdict,
    SbomComponent,
    SbomDocument,
)


def _canonicalize_spdx(raw: str) -> str:
    """Normalize a license string to a single SPDX id when obvious.

    SPDX allows expressions (``MIT OR Apache-2.0``); we take the
    first id from a tuple/expression for the allow/deny comparison
    while preserving the original string on the report.
    """

    raw = raw.strip()
    if not raw:
        return raw
    # Drop any parenthesized expression detail and split on ``OR``/``AND``.
    flattened = raw.replace("(", " ").replace(")", " ")
    for separator in (" OR ", " AND ", " WITH "):
        if separator in flattened:
            return flattened.split(separator, 1)[0].strip()
    return flattened


def resolve_license_ids(component: SbomComponent) -> tuple[str, ...]:
    """Return the list of SPDX-ish ids attached to a component.

    npm lockfiles attach a ``license`` field on each entry; we preserve
    whatever is there. PyPI components on the SBOM are intentionally
    license-less (see module docstring); we let those resolve to
    ``unknown`` rather than fabricating metadata.
    """

    return tuple(sorted({_canonicalize_spdx(spdx) for spdx in component.licenses if spdx}))


def _classify(
    spdx_ids: Sequence[str],
    *,
    allow: Iterable[str],
    deny: Iterable[str],
) -> LicenseVerdict:
    allow_set = {a.lower() for a in allow}
    deny_set = {d.lower() for d in deny}
    if not spdx_ids:
        return "unknown"
    for spdx in spdx_ids:
        if spdx.lower() in deny_set:
            return "deny"
    if not allow_set:
        return "allow"
    for spdx in spdx_ids:
        if spdx.lower() in allow_set:
            return "allow"
    return "unknown"


def _recommendation_for(
    verdict: LicenseVerdict,
    spdx_ids: Sequence[str],
    *,
    allow: Iterable[str],
    deny: Iterable[str],
) -> str:
    if verdict == "deny":
        denylist = ", ".join(sorted({d for d in deny})) or "(empty)"
        return (
            f"License {sorted(spdx_ids)!r} is on the denylist (denylist: {denylist}). "
            "Either remove this dependency, or extend the allowlist if the legal team "
            "has approved it."
        )
    if verdict == "unknown":
        return (
            "Declared license is unknown or missing. Verify the component's LICENSE / SPDX "
            "metadata upstream and either pin it to a known id or add it to the allowlist."
        )
    return ""


def audit_licenses(
    *,
    sbom: SbomDocument,
    allow: Sequence[str] = (),
    deny: Sequence[str] = (),
    unknown_severity: Severity = "low",
    now: datetime | None = None,
) -> LicenseReport:
    """Run the license audit over every component in the SBOM."""

    del now  # not persisted on the wire; kept for symmetry with other modules
    entries: list[LicenseEntry] = []
    for lockfile in sbom.lockfiles:
        for component in lockfile.components:
            spdx_ids = resolve_license_ids(component)
            verdict = _classify(spdx_ids, allow=allow, deny=deny)
            entries.append(
                LicenseEntry(
                    name=component.name,
                    version=component.version,
                    ecosystem=component.ecosystem,
                    spdx_ids=spdx_ids,
                    verdict=verdict,
                    recommendation=_recommendation_for(verdict, spdx_ids, allow=allow, deny=deny),
                )
            )
    return LicenseReport(
        allow=tuple(allow),
        deny=tuple(deny),
        unknown_severity=unknown_severity,
        entries=tuple(entries),
    )


__all__ = [
    "audit_licenses",
    "resolve_license_ids",
]

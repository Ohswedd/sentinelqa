"""License policy tests (Phase 33.06)."""

from __future__ import annotations

from datetime import UTC, datetime

from modules.supply_chain.licenses import audit_licenses
from modules.supply_chain.models import (
    SbomComponent,
    SbomDocument,
    SbomLockfileResult,
)


def _component(
    name: str, *, licenses: tuple[str, ...] = (), ecosystem: str = "npm"
) -> SbomComponent:
    return SbomComponent(
        name=name,
        version="1.0.0",
        ecosystem=ecosystem,  # type: ignore[arg-type]
        purl=f"pkg:{ecosystem.lower()}/{name}@1.0.0",
        licenses=licenses,
    )


def _sbom(*components: SbomComponent) -> SbomDocument:
    return SbomDocument(
        generated_at=datetime(2026, 5, 31, tzinfo=UTC),
        project_name="t",
        lockfiles=(
            SbomLockfileResult(
                path="package-lock.json",
                kind="package-lock.json",
                ecosystem="npm",
                components=tuple(components),
            ),
        ),
        components_count=len(components),
    )


def test_audit_marks_allowed_license_as_allow() -> None:
    sbom = _sbom(_component("lodash", licenses=("MIT",)))
    report = audit_licenses(sbom=sbom, allow=("MIT", "Apache-2.0"))
    assert [e.verdict for e in report.entries] == ["allow"]


def test_audit_marks_denied_license_as_deny() -> None:
    sbom = _sbom(_component("badlib", licenses=("AGPL-3.0-only",)))
    report = audit_licenses(
        sbom=sbom,
        allow=("MIT",),
        deny=("AGPL-3.0-only",),
    )
    assert report.entries[0].verdict == "deny"


def test_audit_marks_unknown_when_no_license() -> None:
    sbom = _sbom(_component("orphan", licenses=()))
    report = audit_licenses(sbom=sbom, allow=("MIT",), unknown_severity="medium")
    assert report.entries[0].verdict == "unknown"


def test_audit_deny_wins_over_allow_on_overlap() -> None:
    sbom = _sbom(_component("conflict", licenses=("MIT",)))
    report = audit_licenses(sbom=sbom, allow=("MIT",), deny=("MIT",))
    assert report.entries[0].verdict == "deny"


def test_audit_with_empty_allow_treats_known_as_allow() -> None:
    sbom = _sbom(_component("noallow", licenses=("BSD-3-Clause",)))
    report = audit_licenses(sbom=sbom, deny=("AGPL-3.0-only",))
    assert report.entries[0].verdict == "allow"


def test_audit_preserves_allow_deny_on_report() -> None:
    sbom = _sbom(_component("any", licenses=("MIT",)))
    report = audit_licenses(sbom=sbom, allow=("MIT",), deny=("AGPL-3.0-only",))
    assert report.allow == ("MIT",)
    assert report.deny == ("AGPL-3.0-only",)
    assert report.unknown_severity == "low"

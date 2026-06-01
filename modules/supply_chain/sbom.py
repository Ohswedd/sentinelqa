"""CycloneDX 1.5 SBOM generator.

Generates a CycloneDX 1.5 JSON document per detected lockfile plus an
aggregate index. The output is validated against the vendored CycloneDX
1.5 JSON Schema at ``packages/shared-schema/external/cyclonedx-1.5.json``;
schema-drift is caught by ``tests/integration/modules/supply_chain/
test_sbom_against_examples.py``.

The writer intentionally emits a minimal but conformant subset of
CycloneDX (``bomFormat`` / ``specVersion`` / ``serialNumber`` / ``version``
/ ``metadata.timestamp`` / ``metadata.component`` / ``components``).
Optional CycloneDX fields (vulnerabilities, services, compositions,
external references, hashes) are out of scope for adding
them would require either fetching package metadata over the network
or trusting the lockfile's hash field, which we don't.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from modules.supply_chain.lockfiles import DetectedLockfile, detect_lockfiles, parse_lockfile
from modules.supply_chain.models import (
    SUPPLY_CHAIN_SCHEMA_VERSION,
    SbomComponent,
    SbomDocument,
    SbomLockfileResult,
)

CYCLONEDX_SPEC_VERSION = "1.5"
"""Emitted ``specVersion`` (matches the vendored JSON Schema)."""

_TOOL_NAME = "sentinelqa-supply-chain"
_TOOL_VENDOR = "SentinelQA"


def _stable_serial_for(detected: DetectedLockfile, components: Sequence[SbomComponent]) -> str:
    """Return a deterministic ``urn:uuid:`` for a CycloneDX document.

    CycloneDX requires the ``serialNumber`` field to be a URN-style UUID.
    For reproducibility we derive a UUID v5 from (lockfile-path, sorted
    name@version list) so two runs over the same lockfile emit the
    byte-identical SBOM. ``Date.now``-style randomness would break
    fixture-driven goldens.
    """

    payload = "\n".join([detected.path.as_posix(), *(f"{c.name}@{c.version}" for c in components)])
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    return "urn:uuid:" + str(uuid.UUID(bytes=digest[:16], version=5))


def _purl_qualifier(component: SbomComponent) -> str:
    """No-op today; reserved for future qualifier emission (e.g. ``?type=jar``)."""

    return component.purl


def _component_dict(component: SbomComponent) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": "library",
        "name": component.name,
        "version": component.version,
        "purl": _purl_qualifier(component),
    }
    if component.licenses:
        payload["licenses"] = [{"license": {"id": spdx}} for spdx in component.licenses]
    return payload


def generate_cyclonedx(
    *,
    detected: DetectedLockfile,
    components: Sequence[SbomComponent],
    project_name: str,
    generated_at: datetime,
) -> dict[str, Any]:
    """Build the CycloneDX 1.5 JSON document for one lockfile."""

    return {
        "$schema": "http://cyclonedx.org/schema/bom-1.5.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": CYCLONEDX_SPEC_VERSION,
        "serialNumber": _stable_serial_for(detected, components),
        "version": 1,
        "metadata": {
            "timestamp": generated_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "tools": [
                {
                    "vendor": _TOOL_VENDOR,
                    "name": _TOOL_NAME,
                    "version": SUPPLY_CHAIN_SCHEMA_VERSION,
                }
            ],
            "component": {
                "type": "application",
                "name": project_name,
                "version": "0.0.0",
            },
        },
        "components": [_component_dict(c) for c in components],
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def build_sbom(
    *,
    project_root: Path,
    project_name: str,
    sbom_dir: Path,
    now: datetime | None = None,
) -> SbomDocument:
    """Detect lockfiles, parse them, write CycloneDX docs, return the index.

    Parser errors are caught per-lockfile and recorded on the
    :class:`SbomLockfileResult`; downstream callers see the failure but
    the run continues so a single malformed lockfile cannot stall the
    SBOM stage.
    """

    timestamp = now or datetime.now(UTC)
    detected = detect_lockfiles(project_root)
    results: list[SbomLockfileResult] = []
    sbom_dir.mkdir(parents=True, exist_ok=True)
    all_components: list[SbomComponent] = []

    for lockfile in detected:
        relative = lockfile.path.relative_to(project_root).as_posix()
        try:
            components = parse_lockfile(lockfile)
        except Exception as exc:
            results.append(
                SbomLockfileResult(
                    path=relative,
                    kind=lockfile.kind,
                    ecosystem=lockfile.ecosystem,
                    components=(),
                    cyclonedx_path=None,
                    parse_error=f"{type(exc).__name__}: {exc}"[:2000],
                )
            )
            continue
        output_filename = f"{lockfile.kind}.cdx.json".replace("/", "_")
        output_path = sbom_dir / output_filename
        cdx = generate_cyclonedx(
            detected=lockfile,
            components=components,
            project_name=project_name,
            generated_at=timestamp,
        )
        _write_json(output_path, cdx)
        results.append(
            SbomLockfileResult(
                path=relative,
                kind=lockfile.kind,
                ecosystem=lockfile.ecosystem,
                components=components,
                cyclonedx_path=output_path.relative_to(sbom_dir.parent).as_posix(),
                parse_error=None,
            )
        )
        all_components.extend(components)

    document = SbomDocument(
        generated_at=timestamp,
        project_name=project_name,
        lockfiles=tuple(results),
        components_count=len(_dedup_global(all_components)),
    )
    _write_json(sbom_dir / "index.json", document.model_dump(mode="json"))
    return document


def _dedup_global(components: Iterable[SbomComponent]) -> tuple[SbomComponent, ...]:
    """Global dedup across all lockfiles by (ecosystem, name lower, version)."""

    seen: set[tuple[str, str, str]] = set()
    out: list[SbomComponent] = []
    for c in components:
        key = (c.ecosystem, c.name.lower(), c.version)
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return tuple(out)


__all__ = [
    "CYCLONEDX_SPEC_VERSION",
    "build_sbom",
    "generate_cyclonedx",
]

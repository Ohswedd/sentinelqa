"""``run.json`` writer.

Serializes the per-run summary envelope. The schema lives at
``packages/shared-schema/run.schema.json`` (our engineering rules, §38).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import urlparse

from engine.domain.finding import Finding
from engine.domain.module_result import ModuleResult
from engine.domain.policy_decision import PolicyDecision, ReleaseDecision
from engine.domain.quality_score import QualityScore
from engine.domain.test_run import RunStatus, TestRun
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.policy.redaction import redact

# Wire format schema version. Mirrors `run.schema.json:schema_version`.
RUN_REPORT_SCHEMA_VERSION: str = "1"

# Artifact slots reported in `run.json.artifact_paths`. Listing them
# explicitly (rather than `dict[str, str | None]`) keeps the schema and the
# writer in lock-step — adding a new artifact requires updating both.
ARTIFACT_SLOTS: tuple[str, ...] = (
    "findings",
    "score",
    "junit",
    "sarif",
    "report_html",
    "report_md",
    "audit_log",
)


@dataclass(frozen=True)
class RunReport:
    """In-memory shape of `run.json` before serialization.

    Built by :func:`build_run_report` from the lifecycle inputs and dumped
    by :func:`write_run`. Exposed for tests + the SDK.
    """

    SCHEMA_VERSION: ClassVar[str] = RUN_REPORT_SCHEMA_VERSION

    schema_version: str
    run_id: str
    started_at: str
    finished_at: str | None
    status: RunStatus
    target: Mapping[str, str]
    config_digest: str
    modules_run: tuple[str, ...]
    release_decision: ReleaseDecision
    quality_score: float | None
    summary: Mapping[str, int]
    artifact_paths: Mapping[str, str | None]
    errors: tuple[Mapping[str, str], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
            "target": dict(self.target),
            "config_digest": self.config_digest,
            "modules_run": list(self.modules_run),
            "release_decision": self.release_decision,
            "quality_score": self.quality_score,
            "summary": dict(self.summary),
            "artifact_paths": dict(self.artifact_paths),
            "errors": [dict(e) for e in self.errors],
        }


def canonical_config_digest(config_snapshot: Mapping[str, Any]) -> str:
    """Return ``sha256:<hex>`` over a canonicalized config snapshot.

    Canonicalization: ``json.dumps(snapshot, sort_keys=True, separators=(",", ":"))``
    on a JSON-friendly dict. Paths and Pydantic models are coerced via
    :func:`_jsonable_for_digest` so the digest stays stable across calls.
    """

    payload = _jsonable_for_digest(dict(config_snapshot))
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(blob).hexdigest()


def derive_release_decision(
    *,
    run_status: RunStatus,
    policy: PolicyDecision | None,
) -> ReleaseDecision:
    """Return the release decision for a run, with PolicyDecision authoritative.

    (quality scoring) populates :class:`PolicyDecision`. Until that
    lands, callers may pass ``policy=None`` and we derive a safe default
    from the run status (our engineering rules — no fake completion: an absent
    decision becomes ``"inconclusive"`` rather than a fake pass).
    """

    if policy is not None:
        return policy.release_decision
    if run_status == "unsafe_blocked":
        return "unsafe_target_rejected"
    if run_status == "dry_run":
        return "inconclusive"
    if run_status == "passed":
        return "pass"
    if run_status == "failed":
        return "blocked"
    # incomplete
    return "inconclusive"


def summarize_modules_and_findings(
    *,
    module_results: Sequence[ModuleResult],
    findings: Sequence[Finding],
) -> dict[str, int]:
    """Return the ``summary`` block for `run.json`.

    Semantics (CI-aligned):

    - ``passed``: count of modules with ``status="passed"``.
    - ``failed``: count of modules with ``status="failed"``.
    - ``blocked``: count of modules that couldn't run cleanly —
    ``status in {"errored", "skipped", "incomplete"}``.
    - ``info``: count of findings with ``severity="info"``.
    """

    passed = sum(1 for m in module_results if m.status == "passed")
    failed = sum(1 for m in module_results if m.status == "failed")
    blocked = sum(1 for m in module_results if m.status in {"errored", "skipped", "incomplete"})
    info = sum(1 for f in findings if f.severity == "info")
    return {"passed": passed, "failed": failed, "blocked": blocked, "info": info}


def build_run_report(
    run: TestRun,
    *,
    config_snapshot: Mapping[str, Any] | None = None,
    findings: Sequence[Finding] = (),
    module_results: Sequence[ModuleResult] = (),
    score: QualityScore | None = None,
    policy: PolicyDecision | None = None,
    errors: Sequence[Mapping[str, str]] = (),
    artifact_paths: Mapping[str, str | None] | None = None,
) -> RunReport:
    """Assemble a :class:`RunReport` from lifecycle inputs (pure function)."""

    parsed = urlparse(str(run.target.base_url))
    host = parsed.hostname or ""
    base_url = str(run.target.base_url)

    snapshot = dict(config_snapshot) if config_snapshot is not None else dict(run.config_snapshot)
    digest = canonical_config_digest(snapshot)

    score_value: float | None
    if run.status in {"unsafe_blocked", "dry_run"} or score is None:
        score_value = None
    else:
        # Round here so the writer and the score.json writer agree on
        # precision (our engineering rules — score is reproducible).
        score_value = round(float(score.total), 2)

    paths_in = dict(artifact_paths) if artifact_paths else {}
    paths = {slot: paths_in.get(slot, None) for slot in ARTIFACT_SLOTS}

    return RunReport(
        schema_version=RUN_REPORT_SCHEMA_VERSION,
        run_id=run.id,
        started_at=run.started_at.isoformat(),
        finished_at=run.finished_at.isoformat() if run.finished_at else None,
        status=run.status,
        target={"base_url": base_url, "host": host, "mode": run.target.mode},
        config_digest=digest,
        modules_run=tuple(sorted(run.modules_run)),
        release_decision=derive_release_decision(run_status=run.status, policy=policy),
        quality_score=score_value,
        summary=summarize_modules_and_findings(module_results=module_results, findings=findings),
        artifact_paths=paths,
        errors=tuple(_normalize_error(e) for e in errors),
    )


def write_run(
    artifact_dir: ArtifactDirectory,
    run: TestRun,
    *,
    config_snapshot: Mapping[str, Any] | None = None,
    findings: Sequence[Finding] = (),
    module_results: Sequence[ModuleResult] = (),
    score: QualityScore | None = None,
    policy: PolicyDecision | None = None,
    errors: Sequence[Mapping[str, str]] = (),
    artifact_paths: Mapping[str, str | None] | None = None,
    filename: str = "run.json",
) -> Path:
    """Serialize a :class:`RunReport` to ``run.json`` and return its path."""

    report = build_run_report(
        run,
        config_snapshot=config_snapshot,
        findings=findings,
        module_results=module_results,
        score=score,
        policy=policy,
        errors=errors,
        artifact_paths=artifact_paths,
    )
    return artifact_dir.write_json(filename, report.to_dict())


def _normalize_error(entry: Mapping[str, Any]) -> dict[str, str]:
    """Coerce ``{code, message}`` shapes from anywhere into the wire format."""

    code = str(entry.get("code", "")).strip() or "E-INT-001"
    message = str(entry.get("message", "")).strip() or "Unspecified error."
    redacted = redact({"code": code, "message": message})
    assert isinstance(redacted, dict)
    return {"code": str(redacted["code"]), "message": str(redacted["message"])}


def _jsonable_for_digest(value: Any) -> Any:
    """Canonicalize a config snapshot for the digest (Paths→str, sets→sorted lists)."""

    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _jsonable_for_digest(value.to_dict())
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return _jsonable_for_digest(value.model_dump(mode="json"))
    if isinstance(value, Mapping):
        return {str(k): _jsonable_for_digest(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):  # noqa: UP038
        return [_jsonable_for_digest(v) for v in value]
    if isinstance(value, (set, frozenset)):  # noqa: UP038
        return sorted(_jsonable_for_digest(v) for v in value)
    if isinstance(value, Path):
        return str(value)
    return value


__all__ = [
    "ARTIFACT_SLOTS",
    "RUN_REPORT_SCHEMA_VERSION",
    "RunReport",
    "build_run_report",
    "canonical_config_digest",
    "derive_release_decision",
    "summarize_modules_and_findings",
    "write_run",
]

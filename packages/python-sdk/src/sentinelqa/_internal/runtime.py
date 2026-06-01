"""Internal: orchestrator + config wiring for the SDK facade.

Everything in this module is lazy — it is only imported by methods of
:class:`sentinelqa.Sentinel` that actually need the engine. ``import
sentinelqa`` therefore stays cheap and the SDK can be imported in
constrained environments (CI bootstraps, Lambda cold starts) without
paying for the discovery / planner / generator dependency graph.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from engine.config.schema import RootConfig

    from sentinelqa._models import AuditResult


def load_root_config(
    project_path: Path,
    config_path: Path | None,
    *,
    url: str | None = None,
    safe_mode: bool = True,
) -> RootConfig:
    """Load and validate ``sentinel.config.yaml``.

    ``project_path`` is used as the default config root when
    ``config_path`` is None. ``url`` overrides ``target.base_url`` for the
    duration of this object. ``safe_mode`` pins
    ``security.mode='safe'`` so the SDK default is identical to the documentation.
    """

    from engine.config.loader import load_config

    resolved = config_path or (project_path / "sentinel.config.yaml")
    config = load_config(resolved)

    if url is not None:
        config = config.model_copy(
            update={"target": config.target.model_copy(update={"base_url": url})}
        )
    if safe_mode and config.security.mode != "safe":
        config = config.model_copy(
            update={"security": config.security.model_copy(update={"mode": "safe"})}
        )
    return config


def build_audit_result_from_context(
    *,
    context: Any,
    run_dir: Path,
    target_url: str,
) -> AuditResult:
    """Build a :class:`sentinelqa.AuditResult` from a finished LifecycleContext."""

    from sentinelqa._models import build_audit_result

    started_at: datetime = context.started_at or datetime.now(UTC)
    finished_at: datetime | None = context.finished_at

    return build_audit_result(
        run_id=context.run_id or "RUN-unknown",
        status=context.status,
        target_url=target_url,
        config_digest=_digest_config(context.config),
        started_at=started_at,
        finished_at=finished_at,
        modules_run=tuple(sorted({o.name for o in context.module_outcomes})),
        typed_findings=context.typed_findings,
        typed_module_results=context.typed_module_results,
        typed_score=context.typed_score,
        typed_policy=context.typed_policy,
        run_dir=run_dir,
    )


def _digest_config(config: Any) -> str:
    """Reuse the engine reporter's canonical digest so SDK + report agree."""

    from engine.reporter.run_writer import canonical_config_digest

    snapshot: Mapping[str, Any] = config.to_dict()
    return canonical_config_digest(snapshot)


def stable_artifact_dir(root: Path, run_id: str) -> Path:
    """Return ``root/<run_id>``."""

    return root / run_id


__all__ = [
    "build_audit_result_from_context",
    "load_root_config",
    "stable_artifact_dir",
]

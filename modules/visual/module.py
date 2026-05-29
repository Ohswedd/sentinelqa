"""``VisualModule`` (Phase 21, PRD §10.6, ADR-0026).

Lifecycle (CLAUDE §9):

- ``validate_prerequisites`` — no-op; missing capture inputs surface as
  ``skipped`` (no PNG anywhere) or per-route ``missing_current``
  findings (PNG present for some viewports, missing for others).
- ``plan``                   — read :class:`VisualModuleOptions`, list
  every ``(viewport, route_slug)`` pair present under either the
  baselines tree or the current-capture tree.
- ``execute``                — diff each pair, accumulate
  :class:`DiffOutcome` records, persist
  ``<run-dir>/visual/index.json``.
- ``emit_findings``          — translate diff outcomes via
  :mod:`modules.visual.findings`.
- ``emit_metrics``           — per-status counts.
- ``summarize``              — overlay findings on a synthesised
  :class:`RunnerOutcome` (no Playwright tests).

The module reads PNGs that already live on disk; it does NOT drive
Playwright. The TS capture helper (Phase 21 + Phase 04 runtime) writes
PNGs into ``<run-dir>/visual/current/<viewport>/<route-slug>.png``,
hiding any selector-mask elements before screenshot. The Python diff
layer additionally paints any rect-masks before comparison so test
fixtures can verify masking without driving a browser (PRD §10.6 +
CLAUDE §29).

Baselines never auto-accept in CI. The CLI flag ``--accept`` refuses
to promote ``current`` PNGs into the baseline tree when ``--ci`` (or
``CI`` / ``SENTINEL_CI``) is set — that policy is enforced at the CLI
boundary (see ``apps/cli sentinel visual``), not here.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

from engine.config.schema import RootConfig, VisualViewportConfig
from engine.domain.finding import Finding
from engine.domain.module_result import ModuleResult, ModuleStatus
from engine.modules.base import ModuleContext, SentinelModule
from engine.orchestrator.registry import ModuleRegistry, default_registry
from engine.policy.safety import SafetyDecision
from engine.runner.results import EnvironmentContext, RunnerOutcome
from PIL import Image, UnidentifiedImageError

from modules.visual.baselines import (
    INDEX_SCHEMA_VERSION,
    baseline_path,
    load_index,
)
from modules.visual.breakpoints import resolve_viewports
from modules.visual.diff import pixel_diff, ssim
from modules.visual.findings import findings_from_diffs
from modules.visual.masking import apply_masks, select_masks
from modules.visual.models import BaselineRecord, DiffOutcome
from modules.visual.options import VisualModuleOptions


@dataclass(frozen=True)
class _PairAddress:
    viewport: str
    route_slug: str


class VisualModule(SentinelModule):
    """Visual-regression module — Phase 21 / PRD §10.6."""

    name: ClassVar[str] = "visual"

    def __init__(
        self,
        config: RootConfig,
        safety_decision: SafetyDecision,
    ) -> None:
        super().__init__(config, safety_decision)
        self._last_outcomes: tuple[DiffOutcome, ...] = ()

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    def validate_prerequisites(self, ctx: ModuleContext) -> None:
        return

    def plan(self, ctx: ModuleContext) -> Sequence[Path]:
        # The module does not drive Playwright; spec-walking returns
        # empty. Pair planning happens inside :meth:`execute`.
        del ctx
        return ()

    def execute(self, ctx: ModuleContext, specs: Sequence[Path]) -> RunnerOutcome:
        del specs
        options = _read_options(ctx)
        baselines_dir = self._resolve_baselines_dir(options)
        current_root = self._resolve_current_root(ctx, options)
        viewports = resolve_viewports(self._config.visual.viewports, options.viewports)
        threshold = (
            options.threshold if options.threshold is not None else self._config.visual.threshold
        )
        perceptual = self._config.visual.perceptual

        pairs = _enumerate_pairs(
            baselines_dir=baselines_dir,
            current_root=current_root,
            viewports=viewports,
            route_filter=options.routes,
        )
        outcomes: list[DiffOutcome] = []
        for pair in pairs:
            outcome = self._diff_pair(
                pair=pair,
                baselines_dir=baselines_dir,
                current_root=current_root,
                run_dir=ctx.run_dir,
                threshold=threshold,
                perceptual_enabled=perceptual.enabled,
                min_similarity=perceptual.min_similarity,
            )
            outcomes.append(outcome)

        self._last_outcomes = tuple(outcomes)
        _persist_index(
            ctx.run_dir,
            outcomes=self._last_outcomes,
            baselines_dir=baselines_dir,
            threshold=threshold,
            viewports=viewports,
        )
        return _synthetic_runner_outcome(ctx, self._last_outcomes)

    def emit_findings(
        self,
        ctx: ModuleContext,
        outcome: RunnerOutcome,
    ) -> tuple[Finding, ...]:
        del outcome
        return findings_from_diffs(
            self._last_outcomes,
            run_id=ctx.run_id,
            target_base_url=str(ctx.target.base_url),
            id_generator=ctx.id_generator,
            run_dir=ctx.run_dir,
        )

    def emit_metrics(
        self,
        ctx: ModuleContext,
        outcome: RunnerOutcome,
    ) -> Mapping[str, float | int]:
        del ctx, outcome
        metrics: dict[str, float | int] = {
            "pairs_total": len(self._last_outcomes),
        }
        for status in ("match", "differ", "missing_baseline", "missing_current", "size_mismatch"):
            metrics[f"pairs_{status}"] = sum(1 for o in self._last_outcomes if o.status == status)
        return metrics

    def summarize(
        self,
        ctx: ModuleContext,
        outcome: RunnerOutcome,
        findings: tuple[Finding, ...],
        metrics: Mapping[str, float | int],
    ) -> ModuleResult:
        has_blocking_finding = any(f.severity in {"critical", "high"} for f in findings)
        has_differ_outcome = any(o.status == "differ" for o in self._last_outcomes)
        if not self._last_outcomes:
            status: ModuleStatus = "skipped"
        elif has_blocking_finding or has_differ_outcome:
            status = "failed"
        else:
            status = "passed"
        merged_metrics = dict(outcome.module_result.metrics)
        merged_metrics.update(metrics)
        return outcome.module_result.model_copy(
            update={
                "findings": tuple(findings),
                "metrics": merged_metrics,
                "status": status,
            }
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_baselines_dir(self, options: VisualModuleOptions) -> Path:
        path = options.baselines_dir or self._config.visual.baselines_dir
        if not path.is_absolute():
            path = Path.cwd() / path
        return path

    def _resolve_current_root(
        self,
        ctx: ModuleContext,
        options: VisualModuleOptions,
    ) -> Path:
        if options.current_root is not None:
            path = options.current_root
        else:
            path = ctx.run_dir / "visual" / "current"
        if not path.is_absolute():
            path = Path.cwd() / path
        return path

    def _diff_pair(
        self,
        *,
        pair: _PairAddress,
        baselines_dir: Path,
        current_root: Path,
        run_dir: Path,
        threshold: float,
        perceptual_enabled: bool,
        min_similarity: float,
    ) -> DiffOutcome:
        baseline_file = baseline_path(baselines_dir, pair.viewport, pair.route_slug)
        current_file = current_root / pair.viewport / f"{pair.route_slug}.png"
        baseline_exists = baseline_file.exists()
        current_exists = current_file.exists()

        if baseline_exists and not current_exists:
            return DiffOutcome(
                route_slug=pair.route_slug,
                viewport=pair.viewport,
                status="missing_current",
                threshold=threshold,
                baseline_path=baseline_file,
                min_similarity=min_similarity if perceptual_enabled else None,
            )
        if current_exists and not baseline_exists:
            return DiffOutcome(
                route_slug=pair.route_slug,
                viewport=pair.viewport,
                status="missing_baseline",
                threshold=threshold,
                current_path=current_file,
                min_similarity=min_similarity if perceptual_enabled else None,
            )
        if not baseline_exists and not current_exists:
            # Should not happen — the pair came from one of the two
            # trees. Defensive: treat as missing_current.
            return DiffOutcome(
                route_slug=pair.route_slug,
                viewport=pair.viewport,
                status="missing_current",
                threshold=threshold,
                min_similarity=min_similarity if perceptual_enabled else None,
            )

        # Both exist — load and diff.
        try:
            baseline_img = Image.open(baseline_file)
            current_img = Image.open(current_file)
            baseline_img.load()
            current_img.load()
        except (FileNotFoundError, UnidentifiedImageError):
            return DiffOutcome(
                route_slug=pair.route_slug,
                viewport=pair.viewport,
                status="size_mismatch",
                threshold=threshold,
                baseline_path=baseline_file,
                current_path=current_file,
                min_similarity=min_similarity if perceptual_enabled else None,
                # Surface the load failure as a size_mismatch finding to
                # keep the lifecycle simple; the description is built
                # downstream and operators will see the corrupt-file
                # message via the run log. (CLAUDE §37 — no fake
                # completion: failing-to-load is a real defect.)
            )

        if baseline_img.size != current_img.size:
            baseline_img.close()
            current_img.close()
            return DiffOutcome(
                route_slug=pair.route_slug,
                viewport=pair.viewport,
                status="size_mismatch",
                threshold=threshold,
                baseline_path=baseline_file,
                current_path=current_file,
                width=current_img.size[0],
                height=current_img.size[1],
                min_similarity=min_similarity if perceptual_enabled else None,
            )

        masks_for_route = select_masks(self._config.visual.masks, pair.route_slug)
        baseline_masked, applied_baseline = apply_masks(
            baseline_img, masks_for_route, route_slug=pair.route_slug
        )
        current_masked, applied_current = apply_masks(
            current_img, masks_for_route, route_slug=pair.route_slug
        )
        del applied_current  # symmetric; recorded via applied_baseline.

        diff_result = pixel_diff(baseline_masked, current_masked)
        ssim_value: float | None = None
        if perceptual_enabled:
            ssim_value = ssim(baseline_masked, current_masked)

        baseline_img.close()
        current_img.close()
        baseline_masked.close()
        current_masked.close()

        triggers_pixel = diff_result.fraction > threshold
        triggers_perceptual = (
            perceptual_enabled and ssim_value is not None and ssim_value < min_similarity
        )
        is_differ = triggers_pixel and (not perceptual_enabled or triggers_perceptual)
        status = "differ" if is_differ else "match"
        diff_overlay_path: Path | None = None
        if is_differ:
            diff_overlay_path = (
                run_dir / "visual" / "diff" / pair.viewport / f"{pair.route_slug}.png"
            )
            diff_overlay_path.parent.mkdir(parents=True, exist_ok=True)
            diff_result.overlay.save(diff_overlay_path, format="PNG")
        diff_result.overlay.close()

        return DiffOutcome(
            route_slug=pair.route_slug,
            viewport=pair.viewport,
            status=status,
            diff_fraction=diff_result.fraction,
            differing_pixels=diff_result.differing_pixels,
            total_pixels=diff_result.total_pixels,
            ssim=ssim_value,
            threshold=threshold,
            min_similarity=min_similarity if perceptual_enabled else None,
            baseline_path=baseline_file,
            current_path=current_file,
            diff_path=diff_overlay_path,
            masks_applied=tuple(m.reason for m in applied_baseline),
            width=diff_result.width,
            height=diff_result.height,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _enumerate_pairs(
    *,
    baselines_dir: Path,
    current_root: Path,
    viewports: tuple[VisualViewportConfig, ...],
    route_filter: tuple[str, ...],
) -> tuple[_PairAddress, ...]:
    """Return every ``(viewport, route_slug)`` to evaluate this run.

    A pair is enumerated when:

    - the viewport is configured (or in the explicit subset), AND
    - at least one side (baseline OR current) has a PNG for it, AND
    - either ``route_filter`` is empty OR the route slug matches an
      entry.
    """

    allowed_viewports = {vp.name for vp in viewports}
    route_allowed = set(route_filter)
    pairs: set[_PairAddress] = set()

    for vp_name in allowed_viewports:
        # Inspect baseline tree
        baseline_subdir = baselines_dir / vp_name
        if baseline_subdir.is_dir():
            for png in baseline_subdir.glob("*.png"):
                slug = png.stem
                if route_allowed and slug not in route_allowed:
                    continue
                pairs.add(_PairAddress(viewport=vp_name, route_slug=slug))
        # Inspect current tree
        current_subdir = current_root / vp_name
        if current_subdir.is_dir():
            for png in current_subdir.glob("*.png"):
                slug = png.stem
                if route_allowed and slug not in route_allowed:
                    continue
                pairs.add(_PairAddress(viewport=vp_name, route_slug=slug))
    return tuple(sorted(pairs, key=lambda p: (p.viewport, p.route_slug)))


def _read_options(ctx: ModuleContext) -> VisualModuleOptions:
    raw: Any = ctx.options.get("visual") if "visual" in ctx.options else ctx.options
    if isinstance(raw, VisualModuleOptions):
        return raw
    if isinstance(raw, Mapping):
        current_root = _coerce_path(raw.get("current_root"))
        baselines_dir = _coerce_path(raw.get("baselines_dir"))
        viewports_value = raw.get("viewports") or ()
        if isinstance(viewports_value, str):
            viewports = tuple(v.strip() for v in viewports_value.split(",") if v.strip())
        else:
            viewports = tuple(str(v) for v in viewports_value)
        routes_value = raw.get("routes") or ()
        if isinstance(routes_value, str):
            routes = tuple(r.strip() for r in routes_value.split(",") if r.strip())
        else:
            routes = tuple(str(r) for r in routes_value)
        threshold_value = raw.get("threshold")
        threshold: float | None = float(threshold_value) if threshold_value is not None else None
        return VisualModuleOptions(
            current_root=current_root,
            baselines_dir=baselines_dir,
            viewports=viewports,
            routes=routes,
            threshold=threshold,
            extra_env=raw.get("extra_env", {}),
        )
    return VisualModuleOptions()


def _coerce_path(value: Any) -> Path | None:
    if value is None:
        return None
    if isinstance(value, Path):
        return value
    return Path(str(value))


def _synthetic_runner_outcome(
    ctx: ModuleContext,
    outcomes: tuple[DiffOutcome, ...],
) -> RunnerOutcome:
    if not outcomes:
        status: ModuleStatus = "skipped"
    elif any(o.status in {"differ", "size_mismatch", "missing_current"} for o in outcomes):
        # Final overlay in :meth:`summarize` may upgrade this further;
        # we mark non-passed early so the lifecycle records the right
        # phase status (CLAUDE §10).
        status = "failed"
    else:
        status = "passed"
    return RunnerOutcome.build(
        module_name="visual",
        module_id=ctx.id_generator.new("MOD"),
        status=status,
        tests=(),
        duration_ms=0,
        environment=EnvironmentContext(
            browser=ctx.config.runner.browser,
            browser_version="n/a",
            os="unknown",
        ),
    )


def _persist_index(
    run_dir: Path,
    *,
    outcomes: tuple[DiffOutcome, ...],
    baselines_dir: Path,
    threshold: float,
    viewports: tuple[VisualViewportConfig, ...],
) -> None:
    """Write ``<run-dir>/visual/index.json`` summarising the run."""

    target = run_dir / "visual"
    target.mkdir(parents=True, exist_ok=True)
    # Load baseline index so the run's index can attribute the
    # baseline sha256s — handy for downstream comparison without
    # re-hashing.
    try:
        baseline_index = load_index(baselines_dir)
    except ValueError:
        baseline_index = {}
    payload = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "threshold": threshold,
        "viewports": [
            {"name": vp.name, "width": vp.width, "height": vp.height} for vp in viewports
        ],
        "pairs": [
            {
                "route_slug": o.route_slug,
                "viewport": o.viewport,
                "status": o.status,
                "diff_fraction": o.diff_fraction,
                "differing_pixels": o.differing_pixels,
                "total_pixels": o.total_pixels,
                "ssim": o.ssim,
                "threshold": o.threshold,
                "width": o.width,
                "height": o.height,
                "masks_applied": list(o.masks_applied),
                "baseline_sha256": _baseline_sha256(baseline_index, o.viewport, o.route_slug),
            }
            for o in outcomes
        ],
    }
    index_path = target / "index.json"
    text = json.dumps(payload, sort_keys=True, indent=2) + "\n"
    index_path.write_text(text, encoding="utf-8")


def _baseline_sha256(
    index: dict[tuple[str, str], BaselineRecord],
    viewport: str,
    route_slug: str,
) -> str | None:
    record = index.get((viewport, route_slug))
    return record.sha256 if record is not None else None


def _factory(config: RootConfig, safety_decision: SafetyDecision) -> VisualModule:
    return VisualModule(config, safety_decision)


def register_with_default_registry(registry: ModuleRegistry | None = None) -> None:
    reg = registry or default_registry()
    if "visual" in reg.modules:
        return
    reg.register_module("visual", _factory)


__all__ = [
    "VisualModule",
    "VisualModuleOptions",
    "_factory",
    "register_with_default_registry",
]

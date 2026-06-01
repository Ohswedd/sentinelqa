"""The :class:`Sentinel` facade (our product spec, our engineering rules).

The facade is intentionally thin: it loads config, builds a
:class:`engine.orchestrator.run_lifecycle.RunLifecycle`, and returns
typed SDK results. All heavy modules (discovery, planner, generator,
runner, reporter) are imported lazily so ``import sentinelqa`` stays
fast.

Every long-running method has both a synchronous form and an ``async_``
counterpart. The sync forms are :func:`asyncio.run` wrappers over the
async forms (the documentation — "Async support"). This means there is exactly
one implementation per method; we never duplicate behavior.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sentinelqa._internal.runtime import (
    build_audit_result_from_context,
    load_root_config,
    stable_artifact_dir,
)

if TYPE_CHECKING:
    from engine.config.schema import RootConfig
    from engine.domain import (
        DiscoveryGraph,
        RepairSuggestion,
        TestPlan,
    )

    from sentinelqa._models import AuditResult, Policy

# Imported lazily by `discover` / `plan` / `generate_tests` — keeps
# `import sentinelqa` fast (the documentation + target: <200 ms).


class Sentinel:
    """Embeddable SentinelQA facade.

    Construct with a project path (defaults to the current working
    directory) and optionally a config override::

    from sentinelqa import Sentinel
    qa = Sentinel(project_path=".")
    result = qa.audit(url="http://localhost:3000")

    For LLM-agent flows::

    qa = Sentinel(project_path=".", machine_readable=True)
    plan = qa.plan(url="http://localhost:3000")
    result = qa.run_plan(plan)

    ``machine_readable`` is advisory — agent-friendly callers pass
    ``True`` to opt out of human-tuned defaults (no progress bars, no
    color, JSON-shaped errors). The SDK itself always returns typed
    objects regardless.
    """

    __slots__ = (
        "_artifacts_root",
        "_config_path",
        "_machine_readable",
        "_project_path",
    )

    def __init__(
        self,
        project_path: str | Path = ".",
        *,
        config: str | Path | None = None,
        machine_readable: bool = False,
        artifacts_root: str | Path | None = None,
    ) -> None:
        self._project_path = Path(project_path).resolve()
        self._config_path: Path | None = Path(config).resolve() if config is not None else None
        self._machine_readable = bool(machine_readable)
        self._artifacts_root: Path = (
            Path(artifacts_root).resolve()
            if artifacts_root is not None
            else self._project_path / ".sentinel" / "runs"
        )

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, path: str | Path) -> Sentinel:
        """Construct a :class:`Sentinel` pinned to an explicit config path.

        Equivalent to ``Sentinel(project_path=path.parent, config=path)``.
        """

        resolved = Path(path).resolve()
        return cls(project_path=resolved.parent, config=resolved)

    @property
    def project_path(self) -> Path:
        """The project root (resolved at construction)."""

        return self._project_path

    @property
    def config_path(self) -> Path:
        """The resolved config path (default: ``<project>/sentinel.config.yaml``)."""

        return self._config_path or (self._project_path / "sentinel.config.yaml")

    @property
    def machine_readable(self) -> bool:
        """Whether the caller requested machine-readable output."""

        return self._machine_readable

    def policy(self) -> Policy:
        """Return the current :class:`Policy` (read-only view of config)."""

        from sentinelqa._models import Policy

        config = self._load_config()
        return Policy.from_config(config)

    # ------------------------------------------------------------------
    # discover(url) — sync + async
    # ------------------------------------------------------------------

    def discover(self, url: str) -> DiscoveryGraph:
        """Crawl ``url`` and return a :class:`DiscoveryGraph`.

        Safety boundary: the engine refuses unsafe targets — an
        :class:`UnsafeTargetError` is raised before any I/O for hosts
        not in ``target.allowed_hosts`` (and not local).
        """

        return asyncio.run(self.async_discover(url))

    async def async_discover(self, url: str) -> DiscoveryGraph:
        """Asynchronous :meth:`discover`."""

        return await asyncio.to_thread(self._run_discover_sync, url)

    def _run_discover_sync(self, url: str) -> DiscoveryGraph:
        from engine.discovery.crawler import CrawlPolicy
        from engine.discovery.pipeline import DiscoveryInputs, DiscoveryPipeline
        from engine.domain.ids import IdGenerator
        from engine.domain.target import Target
        from engine.policy.safety import SafetyPolicy

        config = self._load_config(url=url)
        target = Target(
            base_url=config.target.base_url,
            allowed_hosts=frozenset(config.target.allowed_hosts),
            mode=config.security.mode,
            proof_of_authorization=config.target.proof_of_authorization,
        )
        SafetyPolicy().enforce(target, audit_log_path=self._audit_log_path())
        ids = IdGenerator()
        run_id = ids.new("RUN")
        pipeline = DiscoveryPipeline(id_generator=ids)
        result = pipeline.run(
            DiscoveryInputs(
                base_url=str(target.base_url),
                run_id=run_id,
                policy=CrawlPolicy(),
            )
        )
        return result.graph

    # ------------------------------------------------------------------
    # plan(url|graph) — sync + async
    # ------------------------------------------------------------------

    def plan(
        self,
        url: str | None = None,
        *,
        graph: DiscoveryGraph | None = None,
        risk_map: Any | None = None,
    ) -> TestPlan:
        """Produce a deterministic :class:`TestPlan` for ``url`` or ``graph``.

        Pass ``url`` to re-crawl, or ``graph`` (and optionally a
        pre-computed ``risk_map``) to plan against an existing
        :class:`DiscoveryGraph`. Exactly one of ``url`` / ``graph`` must
        be provided.
        """

        return asyncio.run(self.async_plan(url, graph=graph, risk_map=risk_map))

    async def async_plan(
        self,
        url: str | None = None,
        *,
        graph: DiscoveryGraph | None = None,
        risk_map: Any | None = None,
    ) -> TestPlan:
        """Asynchronous :meth:`plan`."""

        if (url is None) == (graph is None):
            raise ValueError("plan() requires exactly one of `url` or `graph`")
        return await asyncio.to_thread(self._run_plan_sync, url, graph, risk_map)

    def _run_plan_sync(
        self,
        url: str | None,
        graph: DiscoveryGraph | None,
        risk_map: Any | None,
    ) -> TestPlan:
        from engine.domain.ids import IdGenerator
        from engine.domain.risk_map import RiskMap
        from engine.planner.core import DeterministicPlanner

        config = self._load_config(url=url) if url is not None else self._load_config()
        if graph is None:
            assert url is not None  # narrowed by the validator above
            graph = self._run_discover_sync(url)
        if risk_map is None:
            risk_map = RiskMap(id=IdGenerator().new("RM"))
        run_id = IdGenerator().new("RUN")
        planner = DeterministicPlanner(id_generator=IdGenerator())
        outcome = planner.plan(graph=graph, risk=risk_map, config=config, run_id=run_id)
        return outcome.plan

    # ------------------------------------------------------------------
    # generate_tests(plan, out_dir) — sync + async
    # ------------------------------------------------------------------

    def generate_tests(
        self,
        plan: TestPlan,
        out_dir: str | Path,
        *,
        discovery: DiscoveryGraph | None = None,
        base_url: str = "",
        force: bool = False,
    ) -> tuple[Path, ...]:
        """Render Playwright specs for ``plan`` under ``out_dir``.

        Returns the paths of every written file. The generator's
        banner-aware writer refuses to overwrite hand-edited files
        unless ``force=True``.
        """

        return asyncio.run(
            self.async_generate_tests(
                plan, out_dir, discovery=discovery, base_url=base_url, force=force
            )
        )

    async def async_generate_tests(
        self,
        plan: TestPlan,
        out_dir: str | Path,
        *,
        discovery: DiscoveryGraph | None = None,
        base_url: str = "",
        force: bool = False,
    ) -> tuple[Path, ...]:
        """Asynchronous :meth:`generate_tests`."""

        return await asyncio.to_thread(
            self._run_generate_sync, plan, Path(out_dir), discovery, base_url, force
        )

    def _run_generate_sync(
        self,
        plan: TestPlan,
        out_dir: Path,
        discovery: DiscoveryGraph | None,
        base_url: str,
        force: bool,
    ) -> tuple[Path, ...]:
        from engine.domain.discovery_graph import DiscoveryGraph
        from engine.domain.ids import IdGenerator
        from engine.generator import (
            GenerationInputs,
            GenerationOptions,
            GeneratorPipeline,
            write_generated_files,
        )

        config = self._load_config()
        if discovery is None:
            discovery = DiscoveryGraph(id=IdGenerator().new("DG"))
        resolved_base_url = base_url or str(config.target.base_url)
        options = GenerationOptions(base_url=resolved_base_url)
        pipeline = GeneratorPipeline()
        result = pipeline.generate(
            GenerationInputs(
                plan=plan,
                graph=discovery,
                out_dir=out_dir,
                options=options,
            )
        )
        files_for_writer = [(gf.path, gf.content) for gf in result.files]
        outcomes = write_generated_files(files_for_writer, force=force)
        return tuple(o.path for o in outcomes)

    # ------------------------------------------------------------------
    # audit(url, *, modules, safe_mode) — sync + async
    # ------------------------------------------------------------------

    def audit(
        self,
        url: str | None = None,
        *,
        modules: Sequence[str] | None = None,
        safe_mode: bool = True,
        module_options: Mapping[str, Mapping[str, Any]] | None = None,
        dry_run: bool = False,
        ci: bool | None = None,
    ) -> AuditResult:
        """Run the canonical audit lifecycle.

        ``safe_mode=True`` (the default) forces ``security.mode='safe'``
        for this run regardless of the config on disk. Destructive checks
        require explicit opt-in plus a valid proof-of-authorization in
        the config (the documentation, our engineering rules).

        ``dry_run=True`` stops after planning (no module execution).
        ``ci`` defaults to whatever the ``CI`` environment variable
        indicates.
        """

        return asyncio.run(
            self.async_audit(
                url,
                modules=modules,
                safe_mode=safe_mode,
                module_options=module_options,
                dry_run=dry_run,
                ci=ci,
            )
        )

    async def async_audit(
        self,
        url: str | None = None,
        *,
        modules: Sequence[str] | None = None,
        safe_mode: bool = True,
        module_options: Mapping[str, Mapping[str, Any]] | None = None,
        dry_run: bool = False,
        ci: bool | None = None,
    ) -> AuditResult:
        """Asynchronous :meth:`audit`."""

        return await asyncio.to_thread(
            self._run_audit_sync,
            url,
            modules,
            safe_mode,
            module_options,
            dry_run,
            ci,
        )

    def _run_audit_sync(
        self,
        url: str | None,
        modules: Sequence[str] | None,
        safe_mode: bool,
        module_options: Mapping[str, Mapping[str, Any]] | None,
        dry_run: bool,
        ci: bool | None,
    ) -> AuditResult:
        from engine.orchestrator.run_lifecycle import RunLifecycle

        config = self._load_config(url=url, safe_mode=safe_mode)
        lifecycle = RunLifecycle(artifacts_root=self._artifacts_root)
        ci_mode = bool(ci) if ci is not None else bool(os.environ.get("CI"))
        test_run = lifecycle.execute(
            config,
            requested_modules=list(modules) if modules else None,
            dry_run=dry_run,
            ci=ci_mode,
            module_options=dict(module_options or {}),
        )
        context = lifecycle.last_context
        if context is None:  # pragma: no cover — execute always populates last_context
            raise RuntimeError("RunLifecycle.execute did not populate last_context")
        run_dir = stable_artifact_dir(self._artifacts_root, test_run.id)
        return build_audit_result_from_context(
            context=context,
            run_dir=run_dir,
            target_url=str(config.target.base_url),
        )

    # ------------------------------------------------------------------
    # run_plan(plan) — sync + async
    # ------------------------------------------------------------------

    def run_plan(
        self,
        plan: TestPlan,
        *,
        modules: Sequence[str] = ("functional",),
        spec_root: str | Path | None = None,
    ) -> AuditResult:
        """Materialise ``plan`` to specs and run the audit lifecycle.

        Specs are generated under ``spec_root`` (default
        ``<project>/tests/``) and the requested ``modules`` are invoked.
        The lifecycle still enforces the safety boundary.
        """

        return asyncio.run(self.async_run_plan(plan, modules=modules, spec_root=spec_root))

    async def async_run_plan(
        self,
        plan: TestPlan,
        *,
        modules: Sequence[str] = ("functional",),
        spec_root: str | Path | None = None,
    ) -> AuditResult:
        """Asynchronous :meth:`run_plan`."""

        target_dir = Path(spec_root) if spec_root is not None else self._project_path / "tests"
        await self.async_generate_tests(plan, target_dir)
        return await self.async_audit(modules=modules)

    # ------------------------------------------------------------------
    # report(run_id|latest) — sync + async
    # ------------------------------------------------------------------

    def report(
        self,
        run_id: str | None = None,
        *,
        latest: bool = False,
    ) -> Path:
        """Resolve and return the artifact directory for an existing run.

        Passing ``latest=True`` (or ``run_id=None``) resolves to the most
        recent run under ``.sentinel/runs/``. The returned path holds
        the persisted ``run.json``, ``findings.json``, ``score.json``,
        ``report.html``, and ``report.md`` written during the original
        audit (reporter). Re-rendering of additional formats
        currently lives in the CLI (`sentinel report --run-id...`).
        """

        return asyncio.run(self.async_report(run_id, latest=latest))

    async def async_report(
        self,
        run_id: str | None = None,
        *,
        latest: bool = False,
    ) -> Path:
        """Asynchronous :meth:`report`."""

        return await asyncio.to_thread(self._run_report_sync, run_id, latest or run_id is None)

    def _run_report_sync(
        self,
        run_id: str | None,
        latest: bool,
    ) -> Path:
        return self._resolve_run_dir(run_id=run_id, latest=latest)

    # ------------------------------------------------------------------
    # verify_fix(run_id, suggestion) — sync + async
    # ------------------------------------------------------------------

    def verify_fix(
        self,
        run_id: str,
        suggestion: RepairSuggestion,
    ) -> AuditResult:
        """Re-run a prior audit with ``suggestion`` applied; return the result.

        The Healer module owns the application logic. Until
        lands, calling this raises :class:`NotImplementedError`
        with a precise pointer (our engineering rules — no fake completion).
        """

        return asyncio.run(self.async_verify_fix(run_id, suggestion))

    async def async_verify_fix(
        self,
        run_id: str,
        suggestion: RepairSuggestion,
    ) -> AuditResult:
        """Asynchronous :meth:`verify_fix`."""

        raise NotImplementedError(
            "Sentinel.verify_fix is provided by the Healer (Phase 20). "
            "Apply `suggestion` manually and call `audit(...)` again to "
            "verify until Phase 20 ships."
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load_config(
        self,
        *,
        url: str | None = None,
        safe_mode: bool = True,
    ) -> RootConfig:
        return load_root_config(
            self._project_path,
            self._config_path,
            url=url,
            safe_mode=safe_mode,
        )

    def _audit_log_path(self) -> Path:
        # Discovery / planner paths that run outside the orchestrator still
        # need a writable audit log so safety decisions are persisted
        # . Use a sibling directory of the artifacts root.
        log_dir = self._artifacts_root.parent / "sdk-audit"
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / "audit.log"

    def _resolve_run_dir(self, *, run_id: str | None, latest: bool) -> Path:
        root = self._artifacts_root
        if run_id is not None and not latest:
            candidate = root / run_id
            if not candidate.is_dir():
                raise FileNotFoundError(f"No run found at {candidate}")
            return candidate
        # latest pointer or most-recent fallback.
        latest_ptr = root / "latest"
        if latest_ptr.exists() and latest_ptr.is_symlink():
            return latest_ptr.resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"Artifacts root not found: {root}")
        candidates = sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith("RUN-"))
        if not candidates:
            raise FileNotFoundError(f"No runs found under {root}")
        return candidates[-1]


__all__ = ["Sentinel"]

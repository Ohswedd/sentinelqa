"""SentinelQA test runner (PRD §9.4, CLAUDE.md §8, §9).

The runner is responsible for executing generated Playwright tests
(either locally or in a deterministic Docker container), aggregating
the JSONL event stream emitted by the TS reporter (Phase 04) into a
normalized :class:`engine.domain.module_result.ModuleResult`, persisting
the per-module artifact, applying retry + quarantine policy, and
producing a flake-rate metric the quality-score module (Phase 14)
consumes.

Public surface:

- :class:`LocalRunner` — spawns ``sentinel-ts run`` as a subprocess.
- :class:`DockerRunner` — same contract, container-isolated.
- :func:`aggregate` — translates an event stream into a typed
  :class:`RunnerOutcome` (module result + per-test executions).
- :class:`Quarantine` — strict YAML-backed list of suppressed tests.
- :func:`split_shard` / :func:`merge_outcomes` — deterministic sharding.

The runner is intentionally **not** a phase hook on the orchestrator
registry. The Phase-02 ``run_modules`` step keeps its no-op stub; the
``sentinel test`` command (Phase 08.06) drives the runner directly.
The Functional / API / etc. module phases will later register a hook
that calls into this package.
"""

from __future__ import annotations

from engine.runner.docker import DockerRunner, DockerRunnerError
from engine.runner.local import LocalRunner, LocalRunnerError, RunnerSpawnError
from engine.runner.quarantine import (
    Quarantine,
    QuarantineEntry,
    QuarantineError,
    QuarantineExpiredError,
)
from engine.runner.results import (
    EnvironmentContext,
    RunnerOutcome,
    TestExecution,
    aggregate,
    write_module_results,
)
from engine.runner.run_config import RunConfig
from engine.runner.sharding import ShardSpec, merge_outcomes, split_shard

__all__ = [
    "DockerRunner",
    "DockerRunnerError",
    "EnvironmentContext",
    "LocalRunner",
    "LocalRunnerError",
    "Quarantine",
    "QuarantineEntry",
    "QuarantineError",
    "QuarantineExpiredError",
    "RunConfig",
    "RunnerOutcome",
    "RunnerSpawnError",
    "ShardSpec",
    "TestExecution",
    "aggregate",
    "merge_outcomes",
    "split_shard",
    "write_module_results",
]

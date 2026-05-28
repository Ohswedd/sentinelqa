"""The performance module's runner abstraction (ADR-0017 §3).

The :class:`PerformanceModule` calls a :class:`PerformanceRunner` to obtain
a :class:`PerformanceRunOutcome`. Production code uses
:class:`LocalPerformanceRunner`, which spawns
``sentinel-ts audit-perf --input <run-config>.json`` via ``subprocess.run``;
the TS subcommand writes one ``<route-slug>.json`` artifact per route plus
``index.json`` listing every page result. Tests substitute
:class:`StubPerformanceRunner` so the Python layer is exercised without
launching Chromium.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from engine.config.schema import RootConfig
from engine.policy.safety import SafetyDecision

from modules.performance.models import (
    PerformancePageResult,
    PerformanceRunOutcome,
)


class PerformanceRunnerError(RuntimeError):
    """Raised when the configured performance runner cannot complete a run."""


@dataclass(frozen=True)
class PerformanceInvocation:
    """Inputs to one performance audit run."""

    run_id: str
    run_dir: Path
    target: str
    routes: tuple[str, ...]
    samples: int
    repeated_nav_samples: int
    request_timeout_seconds: float
    api_path_allowlist: tuple[str, ...] = ()


@runtime_checkable
class PerformanceRunner(Protocol):
    """Structural type for performance runners (production + test stubs)."""

    def run(self, invocation: PerformanceInvocation) -> PerformanceRunOutcome:  # pragma: no cover
        ...


class LocalPerformanceRunner:
    """Default runner: spawns ``sentinel-ts audit-perf`` and reads the JSON output.

    The TS subcommand:

    - Reads its inputs from a single JSON file (written by this class
      under ``<run-dir>/perf/run-config.json``).
    - Writes one ``<route-slug>.json`` per route under ``<run-dir>/perf/``.
    - Writes ``<run-dir>/perf/index.json`` listing every page result.
    - Returns exit code 0 even when budgets are exceeded (those are
      product output, not runtime errors). Non-zero exits indicate a
      launch / Playwright / Chromium failure.
    """

    SENTINEL_TS_ENV = "SENTINEL_TS_BIN"

    def __init__(
        self,
        *,
        config: RootConfig,
        safety: SafetyDecision,
        cwd: Path | None = None,
    ) -> None:
        self._config = config
        self._safety = safety
        self._cwd = cwd or Path.cwd()

    def _resolve_sentinel_ts(self) -> str:
        explicit = os.environ.get(self.SENTINEL_TS_ENV)
        if explicit:
            return explicit
        on_path = shutil.which("sentinel-ts")
        if on_path:
            return on_path
        raise PerformanceRunnerError(
            "sentinel-ts binary not found. Install @sentinelqa/ts-runtime or set "
            f"the {self.SENTINEL_TS_ENV} environment variable."
        )

    def run(self, invocation: PerformanceInvocation) -> PerformanceRunOutcome:
        binary = self._resolve_sentinel_ts()
        perf_dir = invocation.run_dir / "perf"
        perf_dir.mkdir(parents=True, exist_ok=True)
        run_config_path = perf_dir / "run-config.json"
        run_config_path.write_text(
            json.dumps(
                {
                    "schema_version": "1",
                    "run_id": invocation.run_id,
                    "target": invocation.target,
                    "out_dir": str(perf_dir),
                    "routes": list(invocation.routes),
                    "samples": invocation.samples,
                    "repeated_nav_samples": invocation.repeated_nav_samples,
                    "request_timeout_ms": int(invocation.request_timeout_seconds * 1000),
                    "api_path_allowlist": list(invocation.api_path_allowlist),
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        started = datetime.now(UTC)
        # Each route does (samples + repeated_nav_samples) Playwright visits.
        per_route_budget = invocation.request_timeout_seconds * (
            invocation.samples + invocation.repeated_nav_samples + 2
        )
        timeout_s = per_route_budget * max(len(invocation.routes), 1) + 60
        completed = subprocess.run(
            [binary, "audit-perf", "--input", str(run_config_path)],
            cwd=str(self._cwd),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        duration_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
        if completed.returncode != 0:
            raise PerformanceRunnerError(
                f"sentinel-ts audit-perf exited with code {completed.returncode}: "
                f"{completed.stderr.strip() or 'no stderr'}"
            )

        index_path = perf_dir / "index.json"
        if not index_path.exists():
            raise PerformanceRunnerError(
                f"sentinel-ts audit-perf did not write {index_path!s} — protocol violation."
            )
        return _load_outcome(index_path, duration_ms=duration_ms)


class StubPerformanceRunner:
    """In-memory runner for unit/integration tests."""

    def __init__(
        self,
        pages: Sequence[PerformancePageResult],
        *,
        incomplete: bool = False,
        duration_ms: int = 0,
    ) -> None:
        self._pages = tuple(pages)
        self._incomplete = incomplete
        self._duration_ms = duration_ms
        self.invocation: PerformanceInvocation | None = None

    def run(self, invocation: PerformanceInvocation) -> PerformanceRunOutcome:
        self.invocation = invocation
        return PerformanceRunOutcome(
            pages=self._pages,
            incomplete=self._incomplete,
            duration_ms=self._duration_ms,
        )


def _load_outcome(index_path: Path, *, duration_ms: int) -> PerformanceRunOutcome:
    """Load a :class:`PerformanceRunOutcome` from disk.

    ``index.json`` is a JSON document with a single ``pages`` array whose
    entries are :class:`PerformancePageResult`-shaped dicts. ``incomplete``
    defaults to false; the TS side sets it true when one or more routes
    failed to load.
    """

    payload = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "pages" not in payload:
        raise PerformanceRunnerError(
            f"{index_path!s} is malformed: expected a JSON object with a 'pages' key."
        )
    raw_pages = payload["pages"]
    if not isinstance(raw_pages, list):
        raise PerformanceRunnerError(f"{index_path!s} 'pages' must be a list.")
    pages = tuple(PerformancePageResult.model_validate(p) for p in raw_pages)
    incomplete = bool(payload.get("incomplete", False))
    return PerformanceRunOutcome(
        pages=pages,
        incomplete=incomplete,
        duration_ms=duration_ms,
    )


__all__ = [
    "LocalPerformanceRunner",
    "PerformanceInvocation",
    "PerformanceRunner",
    "PerformanceRunnerError",
    "PerformanceRunOutcome",
    "StubPerformanceRunner",
]

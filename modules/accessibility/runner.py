"""The accessibility module's runner abstraction (ADR-0016 §4).

The :class:`AccessibilityModule` calls an :class:`A11yRunner` to obtain
:class:`A11yRunOutcome`. Production code uses :class:`LocalA11yRunner`,
which spawns ``sentinel-ts audit-a11y --input <run-config>.json`` via
``subprocess.run``; the TS subcommand writes one ``<route-slug>.json``
artifact per route and prints the aggregate run path on stdout.

Tests substitute :class:`StubA11yRunner` (and friends) so the Python
translation layer is exercised without invoking Chromium.
ships the canonical Python-side coverage; the TS-side integration is
gated by ``SENTINELQA_HAS_CHROMIUM=1`` on the TS test runner.
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

from modules.accessibility.models import A11yPageResult, A11yRunOutcome


class A11yRunnerError(RuntimeError):
    """Raised when the configured A11y runner cannot complete a run."""


@dataclass(frozen=True)
class A11yInvocation:
    """Inputs to one A11y run."""

    run_id: str
    run_dir: Path
    target: str
    routes: tuple[str, ...]
    axe_tags: tuple[str, ...]
    request_timeout_seconds: float
    keyboard_max_tabs: int


@runtime_checkable
class A11yRunner(Protocol):
    """Structural type for accessibility runners (production + test stubs)."""

    def run(self, invocation: A11yInvocation) -> A11yRunOutcome:  # pragma: no cover
        ...


class LocalA11yRunner:
    """Default runner: spawns ``sentinel-ts audit-a11y`` and reads the JSON output.

    The TS subcommand:

    - Reads its inputs from a single JSON file (written by this class
    under ``<run-dir>/a11y/run-config.json``).
    - Writes one ``<route-slug>.json`` per route under ``<run-dir>/a11y/``.
    - Writes ``<run-dir>/a11y/index.json`` listing every page result.
    - Returns exit code 0 even when violations are found (violations are
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
        raise A11yRunnerError(
            "sentinel-ts binary not found. Install @sentinelqa/ts-runtime or set "
            f"the {self.SENTINEL_TS_ENV} environment variable."
        )

    def run(self, invocation: A11yInvocation) -> A11yRunOutcome:
        binary = self._resolve_sentinel_ts()
        a11y_dir = invocation.run_dir / "a11y"
        a11y_dir.mkdir(parents=True, exist_ok=True)
        run_config_path = a11y_dir / "run-config.json"
        run_config_path.write_text(
            json.dumps(
                {
                    "schema_version": "1",
                    "run_id": invocation.run_id,
                    "target": invocation.target,
                    "out_dir": str(a11y_dir),
                    "routes": list(invocation.routes),
                    "axe_tags": list(invocation.axe_tags),
                    "request_timeout_ms": int(invocation.request_timeout_seconds * 1000),
                    "keyboard_max_tabs": invocation.keyboard_max_tabs,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        started = datetime.now(UTC)
        completed = subprocess.run(
            [binary, "audit-a11y", "--input", str(run_config_path)],
            cwd=str(self._cwd),
            check=False,
            capture_output=True,
            text=True,
            timeout=invocation.request_timeout_seconds * max(len(invocation.routes), 1) + 60,
        )
        duration_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
        if completed.returncode != 0:
            raise A11yRunnerError(
                f"sentinel-ts audit-a11y exited with code {completed.returncode}: "
                f"{completed.stderr.strip() or 'no stderr'}"
            )

        index_path = a11y_dir / "index.json"
        if not index_path.exists():
            raise A11yRunnerError(
                f"sentinel-ts audit-a11y did not write {index_path!s} — protocol violation."
            )
        return _load_outcome(index_path, duration_ms=duration_ms)


class StubA11yRunner:
    """In-memory runner for unit/integration tests."""

    def __init__(
        self,
        pages: Sequence[A11yPageResult],
        *,
        incomplete: bool = False,
        duration_ms: int = 0,
    ) -> None:
        self._pages = tuple(pages)
        self._incomplete = incomplete
        self._duration_ms = duration_ms
        self.invocation: A11yInvocation | None = None

    def run(self, invocation: A11yInvocation) -> A11yRunOutcome:
        self.invocation = invocation
        return A11yRunOutcome(
            pages=self._pages,
            incomplete=self._incomplete,
            duration_ms=self._duration_ms,
        )


def _load_outcome(index_path: Path, *, duration_ms: int) -> A11yRunOutcome:
    """Load an :class:`A11yRunOutcome` from disk.

    ``index.json`` is a JSON document with a single ``pages`` array whose
    entries are ``A11yPageResult``-shaped dicts. ``incomplete`` defaults
    to false; the TS side sets it true when one or more routes failed to
    load.
    """

    payload = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "pages" not in payload:
        raise A11yRunnerError(
            f"{index_path!s} is malformed: expected a JSON object with a 'pages' key."
        )
    raw_pages = payload["pages"]
    if not isinstance(raw_pages, list):
        raise A11yRunnerError(f"{index_path!s} 'pages' must be a list.")
    pages = tuple(A11yPageResult.model_validate(p) for p in raw_pages)
    incomplete = bool(payload.get("incomplete", False))
    return A11yRunOutcome(
        pages=pages,
        incomplete=incomplete,
        duration_ms=duration_ms,
    )


__all__ = [
    "A11yInvocation",
    "A11yRunOutcome",
    "A11yRunner",
    "A11yRunnerError",
    "LocalA11yRunner",
    "StubA11yRunner",
]

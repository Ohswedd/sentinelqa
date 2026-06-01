"""Locator brittleness audit.

Python wrapper around ``sentinel-ts audit-locators``. The audit logic
itself lives in TypeScript (``packages/ts-runtime/src/locators.ts``);
Python only orchestrates: write the rendered specs to disk, invoke the
subcommand, parse its JSON report.

A spec set passes the audit iff zero findings are returned. Generation
fails closed on any warning unless the caller passes a callback that
explicitly downgrades.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from shutil import which


class LocatorAuditError(RuntimeError):
    """Raised when the audit subprocess cannot run (binary missing, bad exit)."""


@dataclass(frozen=True)
class BrittlenessWarning:
    """One finding from the brittleness audit."""

    file: str
    line: int
    column: int
    message: str
    snippet: str


@dataclass(frozen=True)
class BrittlenessAuditResult:
    """Aggregate result returned by :func:`audit_specs`."""

    files_scanned: int
    warnings: tuple[BrittlenessWarning, ...]

    @property
    def is_clean(self) -> bool:
        return len(self.warnings) == 0


def _resolve_sentinel_ts() -> str:
    """Locate the ``sentinel-ts`` binary; raise if unavailable.

    The binary is installed by ``pnpm install`` under
    ``node_modules/.bin/sentinel-ts`` when it lands as a workspace
    dependency. Locally it's also reachable via ``pnpm exec
    sentinel-ts``; for the CLI we use ``which`` so a global install
    works too. Tests inject the path directly via
    ``audit_specs(executable=...)``.
    """

    path = which("sentinel-ts")
    if path is not None:
        return path
    # Workspace fallback: the binary lives at
    # packages/ts-runtime/dist/cli.js after `pnpm build`. We deliberately
    # do not try to invoke `pnpm` because that adds 100s of ms per call.
    here = Path(__file__).resolve()
    repo_root = here.parents[2]
    candidate = repo_root / "packages" / "ts-runtime" / "dist" / "cli.js"
    if candidate.exists():
        node = which("node")
        if node is None:
            raise LocatorAuditError("`node` not on PATH; cannot run sentinel-ts.")
        return f"NODE::{node}::{candidate}"
    raise LocatorAuditError(
        "`sentinel-ts` not found on PATH and packages/ts-runtime/dist/cli.js is "
        "absent. Run `pnpm --filter @sentinelqa/ts-runtime build`."
    )


def _build_command(executable: str, files: Sequence[Path], cwd: Path) -> list[str]:
    rels = [str(f.relative_to(cwd)) if f.is_absolute() else str(f) for f in files]
    args: list[str] = []
    for rel in rels:
        args.extend(["--file", rel])
    if executable.startswith("NODE::"):
        _, node, cli = executable.split("::", 2)
        return [node, cli, "audit-locators", *args]
    return [executable, "audit-locators", *args]


def audit_specs(
    files: Sequence[Path],
    *,
    cwd: Path | None = None,
    executable: str | None = None,
    runner: object | None = None,
) -> BrittlenessAuditResult:
    """Run the brittleness audit over ``files`` and parse the JSON report.

    ``cwd`` defaults to the parent of the first file. ``executable`` is
    auto-resolved by :func:`_resolve_sentinel_ts` when omitted. ``runner``
    is an injection seam for tests: when provided, it must be a callable
    with the same signature as :func:`subprocess.run` and return a
    completed-process-like object exposing ``stdout`` / ``stderr`` /
    ``returncode``. The real implementation always uses
    :func:`subprocess.run`.
    """

    if not files:
        return BrittlenessAuditResult(files_scanned=0, warnings=())

    work_dir = cwd if cwd is not None else files[0].parent
    exe = executable if executable is not None else _resolve_sentinel_ts()
    cmd = _build_command(exe, files, work_dir)

    run = runner if runner is not None else subprocess.run
    try:
        result = run(  # type: ignore[operator]
            cmd,
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise LocatorAuditError(f"failed to spawn {cmd[0]!r}: {exc}") from exc

    if result.returncode not in (0, 1):
        raise LocatorAuditError(
            f"sentinel-ts audit-locators exited {result.returncode}: "
            f"{(result.stderr or '').strip() or '<no stderr>'}"
        )

    stdout = (result.stdout or "").strip()
    if not stdout:
        raise LocatorAuditError(
            "sentinel-ts audit-locators produced no JSON on stdout; "
            f"stderr: {(result.stderr or '').strip() or '<empty>'}"
        )
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise LocatorAuditError(f"audit JSON parse failed: {exc}") from exc

    if not isinstance(payload, dict) or "findings" not in payload:
        raise LocatorAuditError(f"audit JSON has unexpected shape: {payload!r}")

    warnings = tuple(
        BrittlenessWarning(
            file=str(f.get("file", "")),
            line=int(f.get("line", 0)),
            column=int(f.get("column", 0)),
            message=str(f.get("message", "")),
            snippet=str(f.get("snippet", "")),
        )
        for f in payload.get("findings", [])
    )
    return BrittlenessAuditResult(
        files_scanned=int(payload.get("files_scanned", len(files))),
        warnings=warnings,
    )


__all__ = [
    "BrittlenessAuditResult",
    "BrittlenessWarning",
    "LocatorAuditError",
    "audit_specs",
]

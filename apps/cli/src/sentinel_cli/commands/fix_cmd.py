"""``sentinel fix`` — apply or surface healer proposals.

Reads ``<run-dir>/healer/*.json`` for an existing run (default
``--latest``) and:

- prints each proposal as a unified diff (review mode),
- optionally applies the proposals the gating policy approves
 (``--apply safe|aggressive``),
- always logs every applied repair through the run's ``audit.log``
 with the gating decision reason verbatim,
- refuses to touch hand-edited specs (banner absence or post-generation
 mtime drift), and refuses to weaken assertions unless
 ``--allow-weaken`` is set.

The command never runs modules — it strictly operates on the
materialized run directory. Re-running tests after applying is a
separate concern (delegated to ``sentinel test --grep`` by the
agent or human).

Exit codes:

- ``0`` — success (proposals listed, applied, or none found).
- ``2`` — config / CLI usage error (missing run dir, unknown id).
- ``6`` — applying a proposal failed (file became unwritable,
 unified-diff did not apply cleanly).
- ``7`` — internal error.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Any, Literal

import typer
from engine.errors.codes import (
    EXIT_CONFIG_ERROR,
    EXIT_SUCCESS,
    EXIT_TEST_EXECUTION_FAILED,
)
from engine.healer.banner import detect_banner_status
from engine.healer.gating import AutoApplyMode, decide_auto_apply
from engine.healer.models import RepairProposal
from engine.healer.writer import iter_proposals
from engine.orchestrator.artifacts import list_runs
from engine.policy.audit_log import write_audit_entry

from sentinel_cli.json_mode import json_stdout
from sentinel_cli.state import GlobalState

_DEFAULT_RUNS_ROOT = Path(".sentinel/runs")


def _resolve_run_dir(*, latest: bool, run_id: str | None) -> Path | None:
    """Return the run directory or ``None`` when not found."""

    if run_id is not None:
        candidate = _DEFAULT_RUNS_ROOT / run_id
        return candidate if candidate.is_dir() else None
    if not latest:
        return None
    runs = list_runs(_DEFAULT_RUNS_ROOT)
    return runs[0] if runs else None


def _load_proposals(run_dir: Path) -> tuple[RepairProposal, ...]:
    """Re-hydrate persisted proposals as typed :class:`RepairProposal`."""

    out: list[RepairProposal] = []
    for document in iter_proposals(run_dir):
        try:
            out.append(RepairProposal.model_validate(document))
        except (ValueError, TypeError):
            # Corrupt artifact — skip and continue. A malformed proposal
            # in the run dir means an older healer version or manual
            # tampering; we never raise so `sentinel fix` stays usable.
            continue
    out.sort(key=lambda p: (p.kind, p.id))
    return tuple(out)


def _apply_unified_diff(
    *, original_path: Path, unified_diff: str, original_line: str, proposed_line: str
) -> bool:
    """Apply the single-line replacement encoded in the diff.

    The Healer's diff is always a one-line replacement on a known file
    (the generator never emits multi-hunk patches in ). We do
    the swap via a direct string substitution against the source file
    so the apply path stays portable and does not depend on the
    `patch(1)` binary.
    """

    if not original_path.is_file():
        return False
    source = original_path.read_text(encoding="utf-8")
    if original_line.rstrip("\n") not in source:
        return False
    # Preserve the line ending of the original line if any.
    eol = "\n" if source.endswith("\n") else ""
    replaced = source.replace(original_line.rstrip("\n"), proposed_line.rstrip("\n"), 1)
    if not replaced.endswith(eol):
        replaced += eol
    original_path.write_text(replaced, encoding="utf-8")
    return True


def _to_payload(proposal: RepairProposal) -> dict[str, Any]:
    return {
        "id": proposal.id,
        "kind": proposal.kind,
        "target_test": proposal.target_test,
        "confidence": proposal.confidence,
        "requires_human_review": proposal.requires_human_review,
        "reason": proposal.reason,
    }


def _print_human_diff(proposal: RepairProposal) -> None:
    """Render one proposal as a unified diff to stdout (review mode)."""

    sys.stdout.write(
        f"\nProposal {proposal.id} ({proposal.kind}, confidence={proposal.confidence:.2f})\n"
    )
    sys.stdout.write(f"Target: {proposal.target_test}\n")
    sys.stdout.write(f"Reason: {proposal.reason}\n")
    sys.stdout.write(proposal.unified_diff)
    if not proposal.unified_diff.endswith("\n"):
        sys.stdout.write("\n")


def run_fix(
    ctx: typer.Context,
    latest: Annotated[
        bool,
        typer.Option(
            "--latest/--no-latest",
            help="Read the most recent run (default).",
        ),
    ] = True,
    run_id: Annotated[
        str | None,
        typer.Option(
            "--run",
            help="Read a specific run by id (e.g. RUN-XXXXXXXXXXXX).",
        ),
    ] = None,
    apply_mode: Annotated[
        str,
        typer.Option(
            "--apply",
            help="Auto-apply mode: 'none' (default), 'safe', or 'aggressive'.",
        ),
    ] = "none",
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Print the apply plan without writing to disk.",
        ),
    ] = False,
    allow_weaken: Annotated[
        bool,
        typer.Option(
            "--allow-weaken",
            help=(
                "Allow assertion-stabilization repairs to auto-apply. "
                "Required only when --apply=aggressive."
            ),
        ),
    ] = False,
    review_only: Annotated[
        bool,
        typer.Option(
            "--review-only",
            help="Force review-only output regardless of --apply.",
        ),
    ] = False,
    threshold: Annotated[
        float,
        typer.Option(
            "--threshold",
            help="Auto-apply confidence threshold (default 0.9).",
            min=0.5,
            max=1.0,
        ),
    ] = 0.9,
) -> None:
    """Apply healer proposals from a completed run."""

    state: GlobalState = ctx.obj

    if apply_mode not in {"none", "safe", "aggressive"}:
        typer.echo(
            f"sentinel fix: unknown --apply value {apply_mode!r}. "
            "Use 'none', 'safe', or 'aggressive'.",
            err=True,
        )
        raise typer.Exit(code=EXIT_CONFIG_ERROR)
    mode: AutoApplyMode | Literal["none"] = apply_mode  # type: ignore[assignment]

    run_dir = _resolve_run_dir(latest=latest, run_id=run_id)
    if run_dir is None:
        typer.echo(
            "sentinel fix: no run directory found (expected `.sentinel/runs/<id>/`). "
            "Run `sentinel audit` first, then `sentinel fix`.",
            err=True,
        )
        raise typer.Exit(code=EXIT_CONFIG_ERROR)

    proposals = _load_proposals(run_dir)

    if not proposals:
        if state.mode == "json":
            with json_stdout() as stream:
                stream.emit(
                    {
                        "run_dir": str(run_dir),
                        "count": 0,
                        "applied": [],
                        "reviewed": [],
                        "skipped": [],
                    }
                )
        else:
            sys.stdout.write(f"No healer proposals found in {run_dir.name}.\n")
        raise typer.Exit(code=EXIT_SUCCESS)

    applied: list[str] = []
    reviewed: list[str] = []
    skipped: list[tuple[str, str]] = []
    errors: list[tuple[str, str]] = []

    for proposal in proposals:
        target_path = Path(proposal.target_test)
        if not target_path.is_absolute():
            target_path = run_dir.parent.parent / proposal.target_test
            if not target_path.is_file():
                target_path = Path(proposal.target_test)
        banner_status = detect_banner_status(target_path)

        if review_only or mode == "none":
            reviewed.append(proposal.id)
            if state.mode != "json":
                _print_human_diff(proposal)
            continue

        decision = decide_auto_apply(
            proposal=proposal,
            banner_status=banner_status,
            mode=mode,
            auto_apply_threshold=threshold,
            allow_weaken=allow_weaken,
        )

        if not decision.should_apply:
            skipped.append((proposal.id, decision.reason))
            if state.mode != "json":
                sys.stdout.write(f"skip {proposal.id} ({proposal.kind}): {decision.reason}\n")
            continue

        if dry_run:
            applied.append(proposal.id)
            if state.mode != "json":
                sys.stdout.write(
                    f"would-apply {proposal.id} ({proposal.kind}): {decision.reason}\n"
                )
            continue

        try:
            ok = _apply_unified_diff(
                original_path=target_path,
                unified_diff=proposal.unified_diff,
                original_line=proposal.original_behavior,
                proposed_line=proposal.proposed_change,
            )
        except OSError as exc:
            errors.append((proposal.id, str(exc)))
            continue
        if not ok:
            errors.append((proposal.id, "diff did not apply cleanly"))
            continue
        applied.append(proposal.id)
        write_audit_entry(
            run_dir / "audit.log",
            {
                "event": "healer.apply",
                "id": proposal.id,
                "kind": proposal.kind,
                "target_test": proposal.target_test,
                "confidence": proposal.confidence,
                "decision_reason": decision.reason,
                "allow_weaken": allow_weaken,
                "mode": mode,
            },
        )
        if state.mode != "json":
            sys.stdout.write(f"applied {proposal.id} ({proposal.kind}): {decision.reason}\n")

    if state.mode == "json":
        with json_stdout() as stream:
            stream.emit(
                {
                    "run_dir": str(run_dir),
                    "count": len(proposals),
                    "applied": applied,
                    "reviewed": reviewed,
                    "skipped": [{"id": pid, "reason": reason} for pid, reason in skipped],
                    "errors": [{"id": pid, "error": err} for pid, err in errors],
                }
            )

    if errors:
        raise typer.Exit(code=EXIT_TEST_EXECUTION_FAILED)
    raise typer.Exit(code=EXIT_SUCCESS)


__all__ = ["run_fix"]

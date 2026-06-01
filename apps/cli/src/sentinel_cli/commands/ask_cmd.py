# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""``sentinel ask`` — read-only NL query over a completed run."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer
from engine.runs.ask import (
    AskRequest,
    answer_question,
    deterministic_fallback,
)
from engine.runs.summary import load_run_summary

from sentinel_cli.json_mode import json_stdout
from sentinel_cli.state import GlobalState


def run_ask(
    ctx: typer.Context,
    question: Annotated[
        str,
        typer.Argument(
            help="A natural-language question about the run (in quotes).",
        ),
    ],
    run_id: Annotated[
        str | None,
        typer.Option(
            "--run-id",
            help=(
                "Run id to query (e.g. RUN-XXXXXXXXAAAA). When omitted, "
                "the most recent run under --output is used."
            ),
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Runs root (default: .sentinel/runs).",
        ),
    ] = None,
) -> None:
    """Ask a read-only question about a completed audit run."""

    state: GlobalState = ctx.obj
    runs_root = (output or Path(".sentinel") / "runs").resolve()

    target_dir = runs_root / run_id if run_id is not None else runs_root / "latest"
    if not target_dir.exists():
        sys.stderr.write(f"sentinel ask: no run directory at {target_dir}\n")
        raise typer.Exit(code=2)

    summary = load_run_summary(target_dir)
    request = AskRequest(question=question, summary=summary)
    answer = deterministic_fallback(request)

    if state.mode == "json":
        with json_stdout() as out:
            out.emit(
                {
                    "command": "ask",
                    "run_id": summary.run_id,
                    "answer": answer.text,
                    "provider": answer.provider,
                    "model": answer.model,
                    "available": answer.available,
                    "detail": answer.detail,
                }
            )
        return

    if state.mode == "quiet":
        sys.stdout.write(answer.text + "\n")
        return

    sys.stdout.write(answer.text + "\n")
    if answer.detail:
        sys.stdout.write(f"\n[provider: {answer.provider}; {answer.detail}]\n")


# Re-export the helper so tests can swap in their own adapter without
# touching CLI internals.
__all__ = ["run_ask", "answer_question"]

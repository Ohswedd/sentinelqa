# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""`sentinel flake` — query the cross-run flake database.

The flake DB is populated automatically by the run lifecycle at the
end of every audit. This subcommand reads it.

Sub-commands:

* ``sentinel flake list`` — print the top-N flakiest tests.
* ``sentinel flake stats`` — total runs + outcomes recorded.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer
from engine.persistence import DEFAULT_FLAKE_DB_PATH, FlakeDb

from sentinel_cli.json_mode import json_stdout
from sentinel_cli.state import GlobalState

flake_app = typer.Typer(
    name="flake",
    help=(
        "Inspect the cross-run flake database "
        "(populated automatically at the end of every `sentinel audit`)."
    ),
    no_args_is_help=True,
)


@flake_app.command("list")
def list_flaky(
    ctx: typer.Context,
    limit: Annotated[
        int,
        typer.Option("--limit", min=1, max=200, help="Maximum rows to print (default: 10)."),
    ] = 10,
    min_runs: Annotated[
        int,
        typer.Option(
            "--min-runs",
            min=1,
            help=(
                "Floor on observed runs before a test enters the flaky "
                "list (default: 3). Prevents one-run flukes."
            ),
        ),
    ] = 3,
    db_path: Annotated[
        Path | None,
        typer.Option(
            "--db",
            help=f"Path to the flake DB (default: {DEFAULT_FLAKE_DB_PATH}).",
        ),
    ] = None,
) -> None:
    """List the top flakiest (module, test_id) pairs."""

    state: GlobalState = ctx.obj
    resolved = db_path or DEFAULT_FLAKE_DB_PATH
    if not resolved.is_file():
        if state.mode == "json":
            with json_stdout() as out:
                out.emit({"command": "flake.list", "results": [], "db": str(resolved)})
        elif state.mode != "quiet":
            sys.stdout.write(
                f"No flake DB found at {resolved}. "
                "Run `sentinel audit` at least once to populate it.\n"
            )
        return

    with FlakeDb.open(resolved) as db:
        rows = db.top_flaky(limit=limit, min_runs=min_runs)

    if state.mode == "json":
        with json_stdout() as out:
            out.emit(
                {
                    "command": "flake.list",
                    "results": [
                        {
                            "module": s.module,
                            "test_id": s.test_id,
                            "runs": s.runs,
                            "failures": s.failures,
                            "rate": round(s.rate, 4),
                        }
                        for s in rows
                    ],
                    "db": str(resolved),
                }
            )
        return

    if not rows:
        if state.mode != "quiet":
            sys.stdout.write("No (module, test_id) pairs meet the min-runs floor.\n")
        return

    if state.mode == "quiet":
        for s in rows:
            sys.stdout.write(f"{s.module}\t{s.test_id}\t{s.failures}/{s.runs}\n")
        return

    # Human-readable, fixed-width.
    sys.stdout.write(f"{'MODULE':<14}{'TEST':<40}{'RATE':>6} {'FAILS/RUNS':>10}\n")
    for s in rows:
        sys.stdout.write(
            f"{s.module:<14}{s.test_id:<40}{int(round(s.rate * 100)):>5}% "
            f"{f'{s.failures}/{s.runs}':>10}\n"
        )


@flake_app.command("stats")
def show_stats(
    ctx: typer.Context,
    db_path: Annotated[
        Path | None,
        typer.Option(
            "--db",
            help=f"Path to the flake DB (default: {DEFAULT_FLAKE_DB_PATH}).",
        ),
    ] = None,
) -> None:
    """Print run / outcome totals for the flake DB."""

    state: GlobalState = ctx.obj
    resolved = db_path or DEFAULT_FLAKE_DB_PATH
    if not resolved.is_file():
        if state.mode == "json":
            with json_stdout() as out:
                out.emit(
                    {
                        "command": "flake.stats",
                        "runs": 0,
                        "outcomes": 0,
                        "db": str(resolved),
                    }
                )
        elif state.mode != "quiet":
            sys.stdout.write(
                f"No flake DB found at {resolved}. "
                "Run `sentinel audit` at least once to populate it.\n"
            )
        return

    with FlakeDb.open(resolved) as db:
        counts = db.stats()

    if state.mode == "json":
        with json_stdout() as out:
            out.emit({"command": "flake.stats", **counts, "db": str(resolved)})
        return

    if state.mode != "quiet":
        sys.stdout.write(f"runs    : {counts['runs']}\n" f"outcomes: {counts['outcomes']}\n")


__all__ = ["flake_app"]

"""``sentinel record import`` CLI command (v1.9.0, phase 39).

Parses a JSON recording trace and emits a SentinelQA-tagged Playwright
spec. See ``engine/recording/`` for the trace schema and emitter.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from engine.recording import (
    default_postconditions,
    emit_spec,
    llm_postconditions,
    parse_trace,
)

record_app = typer.Typer(
    name="record",
    help=(
        "Recording-driven test generation: import a JSON recording "
        "(e.g. saved `playwright codegen` actions) and emit a "
        "SentinelQA-tagged spec."
    ),
    no_args_is_help=True,
)


@record_app.command(name="import")
def run_record_import(
    source: Annotated[
        Path,
        typer.Argument(help="JSON recording trace produced by the recorder."),
    ],
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Directory where the .spec.ts will be written.",
        ),
    ] = Path("tests/recorded"),
    suggest_postconditions: Annotated[
        bool,
        typer.Option(
            "--suggest-postconditions/--no-suggest-postconditions",
            help=(
                "Append deterministic presence-check post-conditions "
                "derived from the last interactive steps. Default: on."
            ),
        ),
    ] = True,
    llm_postconditions_flag: Annotated[
        bool,
        typer.Option(
            "--llm-postconditions/--no-llm-postconditions",
            help=(
                "Use the configured LLM provider to suggest richer "
                "post-conditions (falls back to the deterministic suggester "
                "when no provider is available). Default: off."
            ),
        ),
    ] = False,
) -> None:
    """Parse the trace and write a spec."""

    if not source.is_file():
        typer.echo(f"recording trace not found: {source}", err=True)
        raise typer.Exit(code=2)

    try:
        trace = parse_trace(source)
    except ValueError as err:
        typer.echo(f"invalid trace: {err}", err=True)
        raise typer.Exit(code=2) from err

    if not suggest_postconditions:
        postconditions: tuple[str, ...] = ()
    elif llm_postconditions_flag:
        postconditions = llm_postconditions(trace)
    else:
        postconditions = default_postconditions(trace)
    spec_path = emit_spec(
        trace,
        output_dir=output_dir,
        source_label=str(source),
        postconditions=postconditions,
    )
    typer.echo(f"Wrote: {spec_path}")
    typer.echo(f"  steps          : {len(trace.steps)}")
    typer.echo(f"  postconditions : {len(postconditions)}")
    typer.echo(f"  priority       : {trace.priority}")

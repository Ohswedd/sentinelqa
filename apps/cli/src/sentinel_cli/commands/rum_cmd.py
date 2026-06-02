"""``sentinel rum ingest`` CLI command (v1.9.0, phase 39).

Reads a RUM JSONL stream produced by ``@sentinelqa/rum`` and writes a
synthetic SentinelQA run under ``.sentinel/runs/<run-id>/``. The
resulting directory is byte-equivalent to a discover-only synthetic
run so reporter / SDK / MCP consume it unchanged.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from engine.rum import RumIngestError, ingest_jsonl

rum_app = typer.Typer(
    name="rum",
    help=(
        "Ingest Real-User Monitoring streams from @sentinelqa/rum into "
        "the SentinelQA run artifact tree."
    ),
    no_args_is_help=True,
)


@rum_app.command(name="ingest")
def run_rum_ingest(
    source: Annotated[
        Path,
        typer.Argument(
            help="Path to the RUM JSONL stream produced by @sentinelqa/rum.",
        ),
    ],
    runs_root: Annotated[
        Path,
        typer.Option(
            "--runs-root",
            help="Where to write the synthesised run (default: .sentinel/runs).",
        ),
    ] = Path(".sentinel") / "runs",
    project_name: Annotated[
        str,
        typer.Option(
            "--project",
            help="Project name embedded in the run.json (default: rum).",
        ),
    ] = "rum",
    base_url: Annotated[
        str,
        typer.Option(
            "--base-url",
            help=(
                "Customer-facing base URL the RUM data is associated with. "
                "Embedded in run.json so the reporter can label it."
            ),
        ),
    ] = "https://rum.example.com",
) -> None:
    """Ingest a RUM JSONL stream into a new SentinelQA run."""

    runs_root.mkdir(parents=True, exist_ok=True)
    try:
        result = ingest_jsonl(
            source,
            runs_root=runs_root,
            project_name=project_name,
            base_url=base_url,
        )
    except RumIngestError as err:
        typer.echo(f"ingest failed: {err}", err=True)
        raise typer.Exit(code=2) from err

    typer.echo(f"Run created: {result.run_id}")
    typer.echo(f"  run dir            : {result.run_dir}")
    typer.echo(f"  events processed   : {result.events_processed}")
    typer.echo(f"  parse errors       : {result.parse_errors}")
    typer.echo(f"  findings emitted   : {result.findings_emitted}")

"""``sentinel rum`` CLI commands (v1.9.0+, phase 41).

* ``sentinel rum ingest <file.jsonl>`` — bake an existing RUM stream
  into a synthetic run.
* ``sentinel rum serve`` — lift the hosted ingest endpoint over
  loopback so a deployed ``@sentinelqa/rum`` SDK can POST to it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from engine.rum import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    RumIngestError,
    RumServerApp,
    ingest_jsonl,
    serve_forever,
)

rum_app = typer.Typer(
    name="rum",
    help=(
        "Real-User Monitoring: ingest streams from @sentinelqa/rum into "
        "the SentinelQA run artifact tree, or host a loopback ingest "
        "endpoint."
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
    typer.echo(f"  sessions           : {len(result.sessions)}")


@rum_app.command(name="serve")
def run_rum_serve(
    runs_root: Annotated[
        Path,
        typer.Option(
            "--runs-root",
            help="Where to write incoming events / baked runs (default: .sentinel/runs).",
        ),
    ] = Path(".sentinel") / "runs",
    host: Annotated[
        str,
        typer.Option(
            "--host",
            help=(
                "Bind address. Defaults to loopback. Pass 0.0.0.0 only when "
                "the receiver lives behind a reverse proxy."
            ),
        ),
    ] = DEFAULT_HOST,
    port: Annotated[
        int,
        typer.Option("--port", help="TCP port (default: 7332)."),
    ] = DEFAULT_PORT,
    project_name: Annotated[
        str,
        typer.Option(
            "--project",
            help="Project name embedded in the baked run.json (default: rum).",
        ),
    ] = "rum",
    base_url: Annotated[
        str,
        typer.Option(
            "--base-url",
            help="Customer-facing base URL embedded in baked runs.",
        ),
    ] = "https://rum.example.com",
    bake_threshold: Annotated[
        int,
        typer.Option(
            "--bake-threshold",
            help=(
                "Number of buffered events that triggers an automatic bake. "
                "Default 200; lower for chattier traffic."
            ),
        ),
    ] = 200,
) -> None:
    """Host the RUM ingest endpoint on (host, port)."""

    runs_root.mkdir(parents=True, exist_ok=True)
    app = RumServerApp(
        runs_root=runs_root,
        project_name=project_name,
        base_url=base_url,
        bake_threshold=bake_threshold,
    )

    def _on_ready(host: str, port: int) -> None:
        typer.echo(f"SentinelQA RUM receiver listening on http://{host}:{port}/")
        typer.echo("  POST /rum    — ingest a JSONL batch")
        typer.echo("  POST /bake   — force the inbox to bake into a run")
        typer.echo("  GET  /healthz — liveness probe")

    try:
        serve_forever(app, host=host, port=port, on_ready=_on_ready)
    except OSError as err:
        typer.echo(f"could not bind {host}:{port}: {err}", err=True)
        raise typer.Exit(code=1) from err

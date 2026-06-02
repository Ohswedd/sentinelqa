# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""``sentinel serve`` — self-hosted run viewer."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer
from engine.reporter.serve import DEFAULT_HOST, DEFAULT_PORT, ViewerApp, serve_forever


def run_serve(
    ctx: typer.Context,
    runs_root: Annotated[
        Path | None,
        typer.Option(
            "--runs-root",
            help=(
                "Path to the directory holding past runs. "
                "Defaults to .sentinel/runs under the current directory."
            ),
        ),
    ] = None,
    host: Annotated[
        str,
        typer.Option(
            "--host",
            help=(
                "Bind address. Defaults to 127.0.0.1 — the viewer is "
                "loopback-only by design; pass an explicit address to "
                "expose it elsewhere."
            ),
        ),
    ] = DEFAULT_HOST,
    port: Annotated[
        int,
        typer.Option(
            "--port",
            min=1,
            max=65535,
            help="TCP port for the viewer.",
        ),
    ] = DEFAULT_PORT,
    threshold: Annotated[
        float,
        typer.Option(
            "--threshold",
            help="Quality-score threshold used by /api/status.json.",
        ),
    ] = 80.0,
) -> None:
    """Run the SentinelQA run viewer over loopback HTTP."""

    _ = ctx  # the CLI context isn't consulted today
    resolved_runs_root = (runs_root or Path(".sentinel") / "runs").resolve()
    app = ViewerApp(runs_root=resolved_runs_root, threshold=threshold)

    def _on_ready(address: tuple[str, int]) -> None:
        sys.stdout.write(
            f"SentinelQA viewer running at http://{address[0]}:{address[1]}/ "
            f"(runs root: {resolved_runs_root}). Press Ctrl+C to stop.\n"
        )
        sys.stdout.flush()

    try:
        serve_forever(app, host=host, port=port, on_ready=_on_ready)
    except OSError as exc:
        sys.stderr.write(f"sentinel serve: {exc}\n")
        raise typer.Exit(code=1) from exc


__all__ = ["run_serve"]

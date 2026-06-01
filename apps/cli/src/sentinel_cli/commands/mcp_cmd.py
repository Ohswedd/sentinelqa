"""`sentinel mcp` — start the SentinelQA MCP server (task 18.05, ADR-0023).

Replaces the Phase-02 stub. Options:

- ``--stdio`` (default) — speak the MCP stdio transport on this process.
- ``--http <PORT>`` — bind a loopback HTTP transport on
  ``127.0.0.1:<PORT>``. Refuses any non-loopback bind (exit 4).
- ``--config`` — override the ``sentinel.config.yaml`` path.
- ``--log-level`` — engine log level, written to stderr only.

Exit codes follow the canonical grid (0/2/4/7).
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Annotated

import typer
from engine.errors.base import ConfigFileNotFoundError, InternalError, UnsafeTargetError
from engine.errors.codes import (
    EXIT_CONFIG_ERROR,
    EXIT_INTERNAL_ERROR,
    EXIT_SUCCESS,
    EXIT_UNSAFE_TARGET,
)

from sentinel_cli.state import GlobalState
from sentinelqa_mcp.server import build_default_server
from sentinelqa_mcp.transport import LoopbackHttpTransport, StdioTransport, Transport

LogLevel = str  # CLI surface stays string-typed; the underlying logger validates.


def run_mcp(
    ctx: typer.Context,
    stdio: Annotated[
        bool,
        typer.Option(
            "--stdio/--no-stdio",
            help="Speak the MCP stdio transport on this process (default).",
        ),
    ] = True,
    http: Annotated[
        int | None,
        typer.Option(
            "--http",
            help="Bind a loopback HTTP transport on 127.0.0.1:<PORT>.",
        ),
    ] = None,
    log_level: Annotated[
        str,
        typer.Option(
            "--log-level",
            help="Engine log level written to stderr (DEBUG|INFO|WARNING|ERROR).",
        ),
    ] = "INFO",
) -> None:
    """Start the SentinelQA MCP server (ADR-0023)."""

    state: GlobalState = ctx.obj

    # Logs go to stderr only — stdout is reserved for MCP wire bytes
    # . Reconfigure the root logger to point at stderr
    # so any third-party module that imports logging.getLogger sees
    # the right destination.
    _configure_stderr_logger(log_level)

    config_path = state.config_path if state.config_path.exists() else None

    try:
        server = build_default_server(
            project_path=Path.cwd(),
            config_path=config_path,
        )
    except (FileNotFoundError, ConfigFileNotFoundError) as exc:  # pragma: no cover - guard
        sys.stderr.write(f"config error: {exc}\n")
        raise typer.Exit(code=EXIT_CONFIG_ERROR) from exc

    transport: Transport
    if http is not None:
        try:
            transport = LoopbackHttpTransport(port=http)
        except ValueError as exc:
            sys.stderr.write(f"refused HTTP bind: {exc}\n")
            raise typer.Exit(code=EXIT_UNSAFE_TARGET) from exc
        if not state.quiet and state.mode != "quiet":  # pragma: no cover - log line
            sys.stderr.write(
                f"sentinel mcp: listening on http://127.0.0.1:{http} (loopback only)\n"
            )
    else:
        del stdio  # accepted but informational — stdio is the default
        transport = StdioTransport()

    try:  # pragma: no cover - blocks on real stdio / sockets
        asyncio.run(server.serve(transport))
    except UnsafeTargetError as exc:  # pragma: no cover
        sys.stderr.write(f"safety: {exc}\n")
        raise typer.Exit(code=EXIT_UNSAFE_TARGET) from exc
    except KeyboardInterrupt:  # pragma: no cover
        raise typer.Exit(code=EXIT_SUCCESS) from None
    except InternalError as exc:  # pragma: no cover
        sys.stderr.write(f"internal error: {exc}\n")
        raise typer.Exit(code=EXIT_INTERNAL_ERROR) from exc
    raise typer.Exit(code=EXIT_SUCCESS)  # pragma: no cover


def _configure_stderr_logger(level_name: str) -> None:
    """Reconfigure the root logger to write to stderr (CLAUDE §13)."""

    normalized = level_name.upper()
    level = getattr(logging, normalized, logging.INFO)
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(fmt="%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(handler)
    root.setLevel(level)


__all__ = ["run_mcp"]

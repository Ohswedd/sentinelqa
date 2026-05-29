"""Console entry point for ``sentinelqa-mcp``.

Mirrors :mod:`sentinel_cli.commands.mcp_cmd` for the cases where the
package is launched directly without going through the
``sentinel`` CLI. CLI argument shape kept intentionally minimal — the
``sentinel mcp`` command is the primary user-facing surface.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import NoReturn

from engine.errors.codes import EXIT_CONFIG_ERROR, EXIT_INTERNAL_ERROR, EXIT_UNSAFE_TARGET

from sentinelqa_mcp.server import build_default_server
from sentinelqa_mcp.transport import LoopbackHttpTransport, StdioTransport


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sentinelqa-mcp")
    parser.add_argument(
        "--stdio",
        action="store_true",
        help="Speak the MCP stdio transport on this process (default).",
    )
    parser.add_argument(
        "--http",
        type=int,
        metavar="PORT",
        help="Bind a loopback HTTP transport on 127.0.0.1:<PORT>.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Override the sentinel.config.yaml path.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Engine log level (written to stderr).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    # Logs go to stderr only — stdout is reserved for MCP wire bytes.
    logging.basicConfig(
        stream=sys.stderr,
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    try:
        server = build_default_server(config_path=args.config)
    except FileNotFoundError as exc:
        sys.stderr.write(f"config error: {exc}\n")
        return EXIT_CONFIG_ERROR

    if args.http is not None:
        try:
            transport = LoopbackHttpTransport(port=args.http)
        except ValueError as exc:
            sys.stderr.write(f"refused HTTP bind: {exc}\n")
            return EXIT_UNSAFE_TARGET
    else:
        transport = StdioTransport()  # type: ignore[assignment]

    try:  # pragma: no cover - blocks on real stdio/sockets
        asyncio.run(server.serve(transport))
    except KeyboardInterrupt:  # pragma: no cover
        return 0
    except Exception as exc:  # pragma: no cover - defensive
        sys.stderr.write(f"internal error: {type(exc).__name__}: {exc}\n")
        return EXIT_INTERNAL_ERROR
    return 0  # pragma: no cover


def _entry() -> NoReturn:  # pragma: no cover - thin wrapper
    sys.exit(main())


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = ["main"]

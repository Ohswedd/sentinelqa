"""CLI entry point (`sentinel` console script).

`main()` is the integer-returning function we wire into pyproject's
``[project.scripts]``. It catches every :class:`SentinelError` at the
outermost boundary and maps to the deterministic exit code; anything
that escapes as a plain exception is funneled into the internal-error
code (7) via :class:`InternalError`.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import NoReturn

from click.exceptions import ClickException, Exit, UsageError
from engine.errors.base import InternalError, SentinelError
from engine.errors.codes import (
    EXIT_CONFIG_ERROR,
    EXIT_INTERNAL_ERROR,
    EXIT_SUCCESS,
)
from engine.log import configure_logging

from sentinel_cli.app import app
from sentinel_cli.state import GlobalState

# Logging modes are derived from the global state but applied via
# engine.log.configure_logging. The state object lives on the Typer
# context; the root callback runs before any subcommand so we can read
# it back via the standalone_mode=False round-trip below.


def _print_error_json(exc: SentinelError) -> None:
    payload = exc.to_agent_message()
    sys.stdout.write(json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n")
    sys.stdout.flush()


def _print_error_human(exc: SentinelError) -> None:
    sys.stderr.write(f"\nerror [{exc.code}] {exc.message}\n")
    if exc.suggested_fix:
        sys.stderr.write(f"hint: {exc.suggested_fix}\n")


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return an integer exit code.

    Tests can call this with a fabricated argv. Returning rather than
    raising lets us wrap the call in pytest assertions cleanly.
    """

    args = list(sys.argv[1:] if argv is None else argv)

    # Pre-scan to pick the log mode without parsing flags twice. We honor
    # --json / --quiet / --ci / --verbose for the global logger so that
    # the very first message a user sees (even before a subcommand runs)
    # respects their request.
    mode = "human"
    level = "INFO"
    if "--quiet" in args or "-q" in args:
        mode = "quiet"
        level = "ERROR"
    elif "--json" in args or "--ci" in args:
        mode = "json"
    if "--verbose" in args or "-v" in args:
        level = "DEBUG"

    configure_logging(mode=mode, level=level)  # type: ignore[arg-type]

    try:
        # With `standalone_mode=False`, Click catches `Exit` internally and
        # returns its exit code from `app(...)`. We propagate that value.
        # The explicit Exit `except` below stays as defense-in-depth in case
        # Click's behavior changes.
        result = app(args=args, standalone_mode=False)
        if isinstance(result, int):
            return result
        return EXIT_SUCCESS
    except Exit as click_exit:
        return int(click_exit.exit_code)
    except UsageError as usage_exc:
        # Bad CLI invocation — argparse-style error. Print and exit 2
        # (configuration error: bad CLI args are a config-shape problem).
        sys.stderr.write(f"usage error: {usage_exc.format_message()}\n")
        return EXIT_CONFIG_ERROR
    except ClickException as click_exc:
        sys.stderr.write(f"error: {click_exc.format_message()}\n")
        return EXIT_INTERNAL_ERROR
    except SentinelError as exc:
        if mode == "json":
            _print_error_json(exc)
        else:
            _print_error_human(exc)
        logging.getLogger("sentinelqa.cli").debug(
            "SentinelError handled at CLI boundary",
            extra={"code": exc.code, "exit_code": exc.exit_code},
        )
        return exc.exit_code
    except KeyboardInterrupt:
        sys.stderr.write("\ninterrupted.\n")
        return EXIT_INTERNAL_ERROR
    except Exception as unexpected:
        wrapped = InternalError(
            f"Uncaught exception {type(unexpected).__name__}: {unexpected}",
            technical_context={"exception_type": type(unexpected).__name__},
        )
        if mode == "json":
            _print_error_json(wrapped)
        else:
            _print_error_human(wrapped)
        return wrapped.exit_code


def _entry() -> NoReturn:  # pragma: no cover - thin sys.exit wrapper
    sys.exit(main())


# `GlobalState` is unused here but lets `pyright`/`mypy` keep the symbol
# alive — it confirms the type binding the rest of the CLI relies on.
_ = GlobalState


__all__ = ["main"]

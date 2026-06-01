"""SentinelQA CLI (our product spec, our engineering rules).

The Typer app is constructed in :mod:`sentinel_cli.app`. The package
entry point lives in :mod:`sentinel_cli.main`. Tests reach into the
internals via :mod:`sentinel_cli.app` directly; production callers use
the ``sentinel`` console script.
"""

from sentinel_cli.app import app, build_app

__all__ = ["app", "build_app"]

"""``sentinel plugins`` — Phase 24 / PRD §22 plugins CLI.

Three subcommands:

- ``list`` — show every installed plugin discovered via the
  ``sentinelqa.plugins`` entry-point group.
- ``info <name>`` — print the manifest for one plugin in human or
  JSON form.
- ``validate <path>`` — validate a standalone JSON/TOML manifest
  before publishing, without needing the plugin installed.

Exit codes (CLAUDE §13):

- ``0`` — success.
- ``2`` — invalid CLI usage / missing plugin / bad manifest path.
- ``7`` — internal error.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Any

import typer
from engine.errors.codes import (
    EXIT_CONFIG_ERROR,
    EXIT_INTERNAL_ERROR,
    EXIT_SUCCESS,
)
from engine.plugins import (
    PROTOCOL_VERSION,
    Manifest,
    PluginCapabilityForbiddenError,
    PluginManifestError,
    discover,
    load_manifest_file,
)

from sentinel_cli.json_mode import json_stdout
from sentinel_cli.state import GlobalState

plugins_app = typer.Typer(
    name="plugins",
    help=(
        "Manage SentinelQA plugins (PRD §22). `list` shows installed "
        "plugins; `info` prints one plugin's manifest; `validate` "
        "checks a standalone manifest file."
    ),
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
)


def _emit_human(line: str) -> None:
    sys.stdout.write(line + "\n")


def _manifest_dict(manifest: Manifest) -> dict[str, Any]:
    payload: dict[str, Any] = manifest.model_dump(mode="json")
    # Drop None description for human/json consumers.
    if payload.get("description") is None:
        payload.pop("description", None)
    if payload.get("entry_point") is None:
        payload.pop("entry_point", None)
    return payload


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@plugins_app.command("list", help="List installed plugins.")
def list_cmd(
    ctx: typer.Context,
    show_errors: Annotated[
        bool,
        typer.Option(
            "--show-errors/--no-show-errors",
            help="Print discovery errors alongside successful loads.",
        ),
    ] = False,
) -> None:
    """List every plugin discovered via entry points."""

    state: GlobalState = ctx.obj
    registry = discover()

    if state.mode == "json":
        with json_stdout() as out:
            out.emit(
                {
                    "host_protocol_version": PROTOCOL_VERSION,
                    "plugins": [
                        {
                            "name": p.manifest.name,
                            "version": p.manifest.version,
                            "kind": p.manifest.kind,
                            "entry_point": p.entry_point_name,
                            "distribution": p.distribution,
                            "distribution_version": p.distribution_version,
                            "capabilities": list(p.manifest.capabilities),
                            "permissions": list(p.manifest.permissions),
                            "requires_protocol": p.manifest.requires_protocol,
                        }
                        for p in registry
                    ],
                    "errors": [dict(e) for e in registry.errors],
                }
            )
        raise typer.Exit(code=EXIT_SUCCESS)

    if len(registry) == 0 and not registry.errors:
        _emit_human("No SentinelQA plugins installed.")
        _emit_human("(Discovery group: sentinelqa.plugins. " "See docs/dev/plugins.md.)")
        raise typer.Exit(code=EXIT_SUCCESS)

    _emit_human(f"Host protocol version: {PROTOCOL_VERSION}")
    _emit_human("")
    if len(registry) > 0:
        header = f"{'NAME':<28} {'VERSION':<10} {'KIND':<16} ENTRY POINT"
        _emit_human(header)
        _emit_human("-" * len(header))
        for plugin in registry:
            _emit_human(
                f"{plugin.manifest.name:<28} "
                f"{plugin.manifest.version:<10} "
                f"{plugin.manifest.kind:<16} "
                f"{plugin.entry_point_name}"
            )

    if show_errors and registry.errors:
        _emit_human("")
        _emit_human("Discovery errors:")
        for err in registry.errors:
            _emit_human(
                f"  - {err.get('plugin', '?')} "
                f"[{err.get('stage', '?')}]: {err.get('detail', '?')}"
            )

    raise typer.Exit(code=EXIT_SUCCESS)


# ---------------------------------------------------------------------------
# info
# ---------------------------------------------------------------------------


@plugins_app.command("info", help="Show the manifest for a single plugin.")
def info_cmd(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Plugin name (manifest.name).")],
) -> None:
    state: GlobalState = ctx.obj
    registry = discover()

    plugin = None
    for candidate in registry:
        if candidate.manifest.name == name:
            plugin = candidate
            break

    if plugin is None:
        sys.stderr.write(f"sentinel plugins info: no installed plugin named {name!r}.\n")
        raise typer.Exit(code=EXIT_CONFIG_ERROR)

    payload = {
        "manifest": _manifest_dict(plugin.manifest),
        "entry_point": plugin.entry_point_name,
        "distribution": plugin.distribution,
        "distribution_version": plugin.distribution_version,
        "host_protocol_version": PROTOCOL_VERSION,
    }
    if state.mode == "json":
        with json_stdout() as out:
            out.emit(payload)
        raise typer.Exit(code=EXIT_SUCCESS)

    m = plugin.manifest
    _emit_human(f"name:               {m.name}")
    _emit_human(f"version:            {m.version}")
    _emit_human(f"kind:               {m.kind}")
    _emit_human(f"requires_protocol:  {m.requires_protocol}")
    _emit_human(f"host_protocol:      {PROTOCOL_VERSION}")
    _emit_human(f"entry_point:        {plugin.entry_point_name}")
    if plugin.distribution:
        _emit_human(f"distribution:       {plugin.distribution} {plugin.distribution_version}")
    if m.capabilities:
        _emit_human("capabilities:       " + ", ".join(sorted(m.capabilities)))
    if m.permissions:
        _emit_human("permissions:        " + ", ".join(sorted(m.permissions)))
    if m.description:
        _emit_human(f"description:        {m.description}")
    raise typer.Exit(code=EXIT_SUCCESS)


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


@plugins_app.command(
    "validate",
    help="Validate a standalone JSON/TOML manifest file.",
)
def validate_cmd(
    ctx: typer.Context,
    path: Annotated[
        Path,
        typer.Argument(
            exists=False,
            help="Path to a JSON or TOML manifest file.",
        ),
    ],
) -> None:
    state: GlobalState = ctx.obj
    try:
        manifest = load_manifest_file(path)
        manifest.assert_no_forbidden_capabilities()
    except PluginManifestError as exc:
        if state.mode == "json":
            with json_stdout() as out:
                out.emit({"ok": False, "error": exc.message, "code": exc.code})
        else:
            sys.stderr.write(f"sentinel plugins validate: {exc.message}\n")
        raise typer.Exit(code=EXIT_CONFIG_ERROR) from exc
    except PluginCapabilityForbiddenError as exc:
        if state.mode == "json":
            with json_stdout() as out:
                out.emit({"ok": False, "error": exc.message, "code": exc.code})
        else:
            sys.stderr.write(f"sentinel plugins validate: {exc.message}\n")
        raise typer.Exit(code=EXIT_CONFIG_ERROR) from exc
    except Exception as exc:  # pragma: no cover - defensive
        sys.stderr.write(f"sentinel plugins validate: {exc}\n")
        raise typer.Exit(code=EXIT_INTERNAL_ERROR) from exc

    if state.mode == "json":
        with json_stdout() as out:
            out.emit({"ok": True, "manifest": _manifest_dict(manifest)})
    else:
        _emit_human(f"OK: {manifest.name} {manifest.version} ({manifest.kind})")
    raise typer.Exit(code=EXIT_SUCCESS)


__all__ = ["plugins_app"]

"""``sentinel llm`` — / ADR-0042 multi-provider LLM CLI.

Three subcommands:

- ``sentinel llm list`` — prints registered providers + per-provider
 default model + whether the credential env var is set. JSON mode.
- ``sentinel llm doctor`` — runs each provider's ``doctor()`` probe and
 reports reachability + latency. JSON mode.
- ``sentinel llm price`` — prints the cost table for a given
 ``provider/model`` pair. JSON mode.

Exit codes (CLAUDE §13):

- ``0`` — success.
- ``1`` — at least one configured provider is unreachable.
- ``2`` — invalid CLI usage (unknown provider, malformed args).
- ``5`` — no provider reachable AND a provider is required by the call.
- ``7`` — internal error.
"""

from __future__ import annotations

import os
import sys
from typing import Annotated, Any

import typer
from engine.errors.codes import (
    EXIT_CONFIG_ERROR,
    EXIT_DEPENDENCY_MISSING,
    EXIT_INTERNAL_ERROR,
    EXIT_QUALITY_GATE_FAILED,
    EXIT_SUCCESS,
)
from engine.llm import LlmProvider, list_providers, resolve_provider
from engine.llm.protocol import ProviderHealth

from sentinel_cli.json_mode import json_stdout
from sentinel_cli.state import GlobalState

llm_app = typer.Typer(
    name="llm",
    help=(
        "Multi-provider LLM management (Phase 30, ADR-0042). `llm list` "
        "shows installed providers; `llm doctor` probes reachability + "
        "latency; `llm price` prints per-model cost tables."
    ),
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
)


def _emit_human(line: str) -> None:
    sys.stdout.write(line + "\n")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _provider_info(name: str) -> dict[str, Any]:
    provider = resolve_provider(name)
    api_key_env: str | None = None
    api_key_set: bool | None = None
    key_attr = getattr(provider, "API_KEY_ENV", None)
    if isinstance(key_attr, str) and key_attr:
        api_key_env = key_attr
        api_key_set = bool(os.environ.get(key_attr))
    return {
        "name": provider.name,
        "version": provider.version,
        "default_model": getattr(provider, "DEFAULT_MODEL", ""),
        "api_key_env": api_key_env,
        "api_key_set": api_key_set,
    }


def _pricing_for(provider: LlmProvider) -> dict[str, tuple[float, float]]:
    """Return a snapshot of the per-1k-token cost table.

    Returns an empty dict when the provider doesn't ship a table
    (Ollama is free; OpenRouter trusts its own ``usage.cost``).
    """

    import importlib

    module = importlib.import_module(provider.__class__.__module__)
    table: Any = getattr(module, "PRICING_USD_PER_1K", {})
    if isinstance(table, dict):
        return dict(table)
    return {}


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@llm_app.command("list")
def list_cmd(
    ctx: typer.Context,
    json_out: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
) -> None:
    """List registered providers."""

    state = ctx.find_object(GlobalState) or GlobalState()
    if state.json or state.ci:
        json_out = True
    rows = [_provider_info(name) for name in list_providers()]
    if json_out:
        with json_stdout() as out:
            out.emit({"providers": rows})
        raise typer.Exit(code=EXIT_SUCCESS)
    _emit_human(f"{'NAME':<14} {'VERSION':<8} {'DEFAULT MODEL':<36} {'API KEY':<10}")
    for row in rows:
        key_status = (
            "set"
            if row["api_key_set"] is True
            else "unset"
            if row["api_key_set"] is False
            else "n/a"
        )
        _emit_human(
            f"{row['name']:<14} "
            f"{row['version']:<8} "
            f"{row['default_model']:<36} "
            f"{key_status:<10}"
        )
    raise typer.Exit(code=EXIT_SUCCESS)


@llm_app.command("doctor")
def doctor_cmd(
    ctx: typer.Context,
    provider: Annotated[
        str | None,
        typer.Option(
            "--provider",
            help="Limit the probe to one provider; defaults to all registered.",
        ),
    ] = None,
    json_out: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
    require: Annotated[
        bool,
        typer.Option(
            "--require",
            help=(
                "Treat the probe as gating: exit 5 if no provider is "
                "reachable (default: warn but exit 0)."
            ),
        ),
    ] = False,
) -> None:
    """Probe each provider's reachability."""

    state = ctx.find_object(GlobalState) or GlobalState()
    if state.json or state.ci:
        json_out = True

    names: tuple[str, ...]
    if provider is not None:
        if provider not in list_providers():
            if json_out:
                with json_stdout() as out:
                    out.emit(
                        {
                            "error": "unknown_provider",
                            "provider": provider,
                            "available": list(list_providers()),
                        }
                    )
            else:
                _emit_human(f"unknown provider: {provider!r}")
            raise typer.Exit(code=EXIT_CONFIG_ERROR)
        names = (provider,)
    else:
        names = list_providers()

    results: list[dict[str, Any]] = []
    any_available = False
    for name in names:
        try:
            instance = resolve_provider(name)
            health: ProviderHealth = instance.doctor()
        except Exception as exc:
            results.append(
                {
                    "provider": name,
                    "model": "",
                    "status": "unavailable",
                    "latency_ms": 0.0,
                    "detail": f"doctor crashed: {type(exc).__name__}",
                }
            )
            continue
        if health.status == "available":
            any_available = True
        results.append(
            {
                "provider": health.provider,
                "model": health.model,
                "status": health.status,
                "latency_ms": round(health.latency_ms, 2),
                "detail": health.detail,
            }
        )

    if json_out:
        with json_stdout() as out:
            out.emit({"results": results, "any_available": any_available})
    else:
        _emit_human(f"{'PROVIDER':<14} {'STATUS':<12} {'LATENCY':<10} {'DETAIL'}")
        for row in results:
            _emit_human(
                f"{row['provider']:<14} "
                f"{row['status']:<12} "
                f"{row['latency_ms']:>8.1f}ms {row['detail']}"
            )

    if require and not any_available:
        raise typer.Exit(code=EXIT_DEPENDENCY_MISSING)
    has_unreachable = any(r["status"] != "available" for r in results)
    if provider is not None and not any_available:
        # Asking after one specific provider that isn't reachable.
        raise typer.Exit(code=EXIT_QUALITY_GATE_FAILED if has_unreachable else EXIT_SUCCESS)
    if has_unreachable and provider is None:
        # Multi-provider report: 0 if at least one is reachable, 1 otherwise.
        raise typer.Exit(code=EXIT_SUCCESS if any_available else EXIT_QUALITY_GATE_FAILED)
    raise typer.Exit(code=EXIT_SUCCESS)


@llm_app.command("price")
def price_cmd(
    ctx: typer.Context,
    provider: Annotated[str, typer.Option("--provider", help="Provider name (see `llm list`).")],
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            help="Print the rate for one model; omit to print the full table.",
        ),
    ] = None,
    json_out: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
) -> None:
    """Print cost-per-1k-token rates for a provider's models."""

    state = ctx.find_object(GlobalState) or GlobalState()
    if state.json or state.ci:
        json_out = True
    if provider not in list_providers():
        if json_out:
            with json_stdout() as out:
                out.emit({"error": "unknown_provider", "provider": provider})
        else:
            _emit_human(f"unknown provider: {provider!r}")
        raise typer.Exit(code=EXIT_CONFIG_ERROR)

    instance = resolve_provider(provider)
    table = _pricing_for(instance)
    if model is not None:
        rates = table.get(model)
        if rates is None:
            if json_out:
                with json_stdout() as out:
                    out.emit({"error": "unknown_model", "provider": provider, "model": model})
            else:
                _emit_human(
                    f"unknown model {model!r} for provider {provider!r}; "
                    f"known: {sorted(table)!r}"
                )
            raise typer.Exit(code=EXIT_CONFIG_ERROR)
        if json_out:
            with json_stdout() as out:
                out.emit(
                    {
                        "provider": provider,
                        "model": model,
                        "price_per_1k_input_usd": rates[0],
                        "price_per_1k_output_usd": rates[1],
                    }
                )
        else:
            _emit_human(
                f"{provider}/{model}: input ${rates[0]:.6f}/1k, " f"output ${rates[1]:.6f}/1k"
            )
        raise typer.Exit(code=EXIT_SUCCESS)

    rows = [
        {
            "provider": provider,
            "model": m,
            "price_per_1k_input_usd": rates[0],
            "price_per_1k_output_usd": rates[1],
        }
        for m, rates in sorted(table.items())
    ]
    if json_out:
        with json_stdout() as out:
            out.emit({"provider": provider, "models": rows})
    else:
        if not rows:
            _emit_human(f"{provider}: no per-model price table (cost is provider-driven).")
        else:
            _emit_human(f"{'MODEL':<40} {'INPUT/1k':<12} {'OUTPUT/1k':<12}")
            for row in rows:
                _emit_human(
                    f"{row['model']:<40} "
                    f"${row['price_per_1k_input_usd']:<11.6f} "
                    f"${row['price_per_1k_output_usd']:<11.6f}"
                )
    raise typer.Exit(code=EXIT_SUCCESS)


# Silence unused-import warning — EXIT_INTERNAL_ERROR is reserved for
# future extensions (audit-log probe etc.).
_ = EXIT_INTERNAL_ERROR


__all__ = ["llm_app"]

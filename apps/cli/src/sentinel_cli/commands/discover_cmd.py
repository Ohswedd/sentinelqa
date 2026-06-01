"""``sentinel discover`` -- crawl, build the DiscoveryGraph, write artifacts.

Wires the run-lifecycle steps 1-8 (config -> safety -> run id -> artifact dir
-> snapshot -> discovery), then writes the five JSON artifacts plus a
Markdown summary into the run dir. Replaces the stub.
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

import typer
from engine.auth import (
    Vault,
    cookies_for_host,
    load_storage_state_dict,
)
from engine.config.loader import load_config
from engine.config.schema import RootConfig
from engine.discovery.auth_boundary import AuthCredentials
from engine.discovery.backends import (
    PlaywrightCrawlBackend,
    SentinelTsNotInstalledError,
)
from engine.discovery.crawler import Crawler, CrawlPolicy
from engine.discovery.pipeline import DiscoveryInputs, DiscoveryPipeline
from engine.discovery.writer import write_discovery_artifacts
from engine.domain.ids import IdGenerator
from engine.domain.target import Target
from engine.errors.base import ConfigError, InternalError
from engine.errors.codes import (
    EXIT_INTERNAL_ERROR,
    EXIT_SUCCESS,
)
from engine.policy.audit_log import write_audit_entry
from engine.policy.safety import SafetyPolicy

from sentinel_cli.json_mode import json_stdout
from sentinel_cli.state import GlobalState


def run_discover(
    ctx: typer.Context,
    url: Annotated[
        str | None,
        typer.Option("--url", help="Override `target.base_url` for this discovery pass."),
    ] = None,
    max_depth: Annotated[
        int | None,
        typer.Option("--max-depth", help="Override discovery.max_depth."),
    ] = None,
    max_pages: Annotated[
        int | None,
        typer.Option("--max-pages", help="Override discovery.max_pages."),
    ] = None,
    rate_limit: Annotated[
        float | None,
        typer.Option("--rate-limit", help="Override discovery.rate_limit_rps."),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Override the artifact directory parent (default: .sentinel/runs).",
        ),
    ] = None,
    openapi: Annotated[
        Path | None,
        typer.Option("--openapi", help="Local OpenAPI 3.x JSON / YAML file to ingest."),
    ] = None,
    graphql_sdl: Annotated[
        Path | None,
        typer.Option("--graphql-sdl", help="Local GraphQL SDL file to ingest."),
    ] = None,
) -> None:
    """Crawl the target, build a DiscoveryGraph + RiskMap, and persist artifacts."""

    state: GlobalState = ctx.obj
    config = load_config(state.config_path)
    if url is not None:
        config = config.model_copy(
            update={"target": config.target.model_copy(update={"base_url": url})}
        )

    artifacts_root = output if output is not None else Path(".sentinel") / "runs"
    ids = IdGenerator()
    run_id = ids.new("RUN")
    run_dir = artifacts_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    audit_log_path = run_dir / "audit.log"

    # Lifecycle step 4: enforce safety boundary BEFORE any I/O. Failure here
    # raises UnsafeTargetError, which the outer CLI handler maps to exit 4.
    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
        mode=config.security.mode,
        proof_of_authorization=config.target.proof_of_authorization,
    )
    SafetyPolicy().enforce(target, audit_log_path=audit_log_path)

    write_audit_entry(
        audit_log_path,
        {
            "decided_at": datetime.now(UTC).isoformat(),
            "event": "discovery.start",
            "run_id": run_id,
            "target": str(config.target.base_url),
        },
    )

    policy = _build_crawl_policy(
        config,
        max_depth=max_depth,
        max_pages=max_pages,
        rate_limit=rate_limit,
    )

    credentials = _resolve_credentials(config)

    # , ADR-0043. `auth.strategy: browser_session` injects
    # cookies from the encrypted vault into the discovery crawler's
    # HTTP client. The decrypted payload stays in memory — we never
    # write the plaintext storage state to the run dir.
    extra_cookies = _resolve_vault_cookies(config, audit_log_path)

    # 07 — `discovery.engine` selects the crawl backend.
    # HTTP is the default; `playwright` lights up Chromium-driven
    # SPA crawling (ADR-0010). Construction is intentionally lazy: the
    # Playwright backend only resolves `sentinel-ts` when `.crawl` runs,
    # so HTTP runs never pay a startup cost.
    crawler: Crawler
    if config.discovery.engine == "playwright":
        crawler = Crawler(backend=PlaywrightCrawlBackend())
    else:
        crawler = Crawler()
    pipeline = DiscoveryPipeline(crawler=crawler, id_generator=ids)
    inputs = DiscoveryInputs(
        base_url=str(config.target.base_url),
        run_id=run_id,
        policy=policy,
        credentials=credentials,
        openapi_path=openapi or config.discovery.openapi.path,
        openapi_url=config.discovery.openapi.url,
        graphql_sdl_path=graphql_sdl or config.discovery.graphql.path,
        graphql_endpoint_url=config.discovery.graphql.url,
        extra_cookies=extra_cookies,
    )

    try:
        result = pipeline.run(inputs)
    except SentinelTsNotInstalledError as exc:
        from engine.errors.base import DependencyMissingError

        raise DependencyMissingError(
            f"sentinel-ts is required for `discovery.engine: playwright` "
            f"but was not found: {exc}",
            technical_context={"engine": "playwright"},
        ) from exc
    written = write_discovery_artifacts(result=result, out_dir=run_dir)

    write_audit_entry(
        audit_log_path,
        {
            "decided_at": datetime.now(UTC).isoformat(),
            "event": "discovery.complete",
            "run_id": run_id,
            "artifacts": {key: str(path) for key, path in written.items()},
        },
    )

    if state.mode == "json":
        with json_stdout() as emit:
            emit.emit(
                {
                    "command": "discover",
                    "run_id": run_id,
                    "run_dir": str(run_dir),
                    "routes": len(result.graph.routes),
                    "elements": len(result.graph.elements),
                    "forms": len(result.graph.forms),
                    "api_endpoints": len(result.graph.api_endpoints),
                    "auth_boundaries": len(result.graph.auth_boundaries),
                    "artifacts": {k: str(v) for k, v in written.items()},
                }
            )
    elif state.mode != "quiet":
        sys.stdout.write(
            f"run_id     : {run_id}\n"
            f"run_dir    : {run_dir}\n"
            f"routes     : {len(result.graph.routes)}\n"
            f"elements   : {len(result.graph.elements)}\n"
            f"forms      : {len(result.graph.forms)}\n"
            f"endpoints  : {len(result.graph.api_endpoints)}\n"
            f"auth bounds: {len(result.graph.auth_boundaries)}\n"
        )

    raise typer.Exit(code=EXIT_SUCCESS)


def _build_crawl_policy(
    config: RootConfig,
    *,
    max_depth: int | None,
    max_pages: int | None,
    rate_limit: float | None,
) -> CrawlPolicy:
    discovery = config.discovery
    return CrawlPolicy(
        max_depth=max_depth if max_depth is not None else discovery.max_depth,
        max_pages=max_pages if max_pages is not None else discovery.max_pages,
        rate_limit_rps=(rate_limit if rate_limit is not None else discovery.rate_limit_rps),
        request_timeout_seconds=discovery.request_timeout_seconds,
        respect_robots=discovery.respect_robots,
        same_host_only=discovery.same_host_only,
        extra_allowed_hosts=discovery.extra_allowed_hosts,
    )


def _resolve_vault_cookies(config: RootConfig, audit_log_path: Path) -> dict[str, str] | None:
    """, ADR-0043. Pull cookies from the auth vault if configured.

    Returns ``None`` when the strategy is not ``browser_session``. Raises
    :class:`engine.errors.base.AuthError` when the vault entry is
    missing, expired, host-mismatched, or fails AEAD verification — the
    caller surfaces those at the CLI boundary.
    """

    if config.auth.strategy != "browser_session":
        return None
    target_host = (urlparse(str(config.target.base_url)).hostname or "").lower()
    if not target_host:
        return None
    storage_state = load_storage_state_dict(
        Vault(),
        host=target_host,
        name=config.auth.session_name or "",
        allowed_hosts=config.target.allowed_hosts,
        audit_log_path=audit_log_path,
    )
    cookies = cookies_for_host(storage_state, target_host)
    return cookies or None


def _resolve_credentials(config: RootConfig) -> AuthCredentials | None:
    auth = config.auth
    if auth.login_url is None or auth.username_env is None or auth.password_env is None:
        return None
    username = os.environ.get(auth.username_env)
    password = os.environ.get(auth.password_env)
    if not username or not password:
        # Don't fail the crawl — emit a clear warning via stderr and skip the
        # authenticated pass. Tests still get deterministic behavior.
        sys.stderr.write(
            f"sentinel discover: credentials missing "
            f"({auth.username_env}/{auth.password_env} not set); "
            f"skipping authenticated crawl.\n"
        )
        return None
    return AuthCredentials(
        login_url=auth.login_url,
        username_env_name=auth.username_env,
        password_env_name=auth.password_env,
        username=username,
        password=password,
    )


# Re-export the symbols `app.py` references.
__all__ = ["run_discover"]


# Defensive imports — make sure errors used in type hints actually resolve at
# import time so a typo would fail fast.
_ = (ConfigError, InternalError, EXIT_INTERNAL_ERROR)

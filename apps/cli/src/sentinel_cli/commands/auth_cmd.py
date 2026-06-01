"""``sentinel auth`` — browser-authenticated audit CLI.

Subcommands:

- ``login`` — interactive flow that opens a headed Playwright browser,
 waits for the operator to sign in, captures ``storage_state``, and
 encrypts it into the vault. Forbidden in CI mode.
- ``list`` — show every vault entry with redacted metadata only (no
 cookie values, no localStorage payloads).
- ``list-profiles`` — show the built-in OAuth and LLM-web auth
 profiles (Tasks 31.04 / 31.05).
- ``revoke`` — delete one entry (or every entry with ``--all`` and a
 typed confirmation).
- ``export`` — decrypt and write the plaintext storage_state to a file
 so the operator can copy it to a teammate's machine. Mandatory
 ``--i-acknowledge`` flag with a stderr warning banner.

Exit codes:

- ``0`` — success.
- ``2`` — invalid CLI usage / unsafe host / CI mode rejection /
 vault-entry-not-found.
- ``4`` — safety-boundary refusal (expired entry, host mismatch,
 integrity failure, cross-origin login redirect).
- ``5`` — dependency missing (Playwright / cryptography / keyring).
- ``7`` — internal error.
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path
from typing import Annotated, Any, cast

import typer
from engine.auth import (
    BrowserLauncher,
    LoginRequest,
    PlaywrightLauncher,
    Vault,
    VaultMetadata,
    capture_session,
    host_pair_from_login_url,
    hosts_iterable,
    list_profiles,
    resolve_profile,
)
from engine.auth.profiles import ProfileNotFoundError
from engine.errors.base import (
    AuthCommandForbiddenInCiError,
    SentinelError,
)
from engine.errors.codes import (
    EXIT_CONFIG_ERROR,
    EXIT_DEPENDENCY_MISSING,
    EXIT_INTERNAL_ERROR,
    EXIT_SUCCESS,
)
from engine.policy.audit_log import write_audit_entry

from sentinel_cli.json_mode import json_stdout
from sentinel_cli.state import GlobalState

auth_app = typer.Typer(
    name="auth",
    help=(
        "Browser-authenticated audits (Phase 31, ADR-0043). `login` "
        "opens a real browser so the operator can sign in once; "
        "SentinelQA encrypts the session locally and replays it on "
        "later audits. `list`/`revoke`/`export` manage the vault. "
        "SentinelQA NEVER harvests credentials and NEVER bypasses MFA."
    ),
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
)


def _emit_human(line: str) -> None:
    sys.stdout.write(line + "\n")


def _emit_stderr(line: str) -> None:
    sys.stderr.write(line + "\n")
    sys.stderr.flush()


def _audit_log_path() -> Path:
    """Resolve the global audit-log path.

    The CLI lives outside a run, so the default lands under
    ``~/.sentinel/auth/audit.log``. The run lifecycle writes its own
    per-run audit log; vault uses out here are bookkeeping for the
    operator.
    """

    return Path.home() / ".sentinel" / "auth" / "audit.log"


def _handle_sentinel_error(exc: SentinelError) -> None:
    msg = exc.to_agent_message()
    _emit_stderr(f"error[{msg['code']}]: {msg['message']}")
    if msg.get("suggested_fix"):
        _emit_stderr(f"  fix: {msg['suggested_fix']}")
    raise typer.Exit(code=exc.exit_code)


# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------


@auth_app.command("login", help="Open a real browser so the operator can sign in.")
def login_cmd(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Argument(help="Stable vault entry name (e.g. 'github-myorg')."),
    ],
    url: Annotated[
        str,
        typer.Option("--url", help="Login URL to open in the browser."),
    ],
    target: Annotated[
        str | None,
        typer.Option(
            "--target",
            help="Override the host recorded in the vault (default: url's host).",
        ),
    ] = None,
    ttl_hours: Annotated[
        int,
        typer.Option(
            "--ttl",
            help="Session lifetime in hours (default: 24, max: 8760).",
            min=1,
            max=24 * 365,
        ),
    ] = 24,
    browser: Annotated[
        str,
        typer.Option(
            "--browser",
            help="Browser engine (chromium | firefox | webkit).",
        ),
    ] = "chromium",
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            help="Built-in auth profile (run `sentinel auth list-profiles`).",
        ),
    ] = None,
    allowed_host: Annotated[
        list[str] | None,
        typer.Option(
            "--allow-host",
            help=(
                "Extra host to permit on cross-origin redirects (e.g. an IdP). "
                "Repeat for multiple hosts."
            ),
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Overwrite an existing entry with the same name.",
        ),
    ] = False,
) -> None:
    """Run the interactive capture flow."""

    state: GlobalState = ctx.obj

    if browser not in ("chromium", "firefox", "webkit"):
        _emit_stderr(
            f"error[E-CFG-002]: --browser must be one of "
            f"chromium | firefox | webkit; got {browser!r}."
        )
        raise typer.Exit(code=EXIT_CONFIG_ERROR)

    if state.ci:
        # Cannot drive an interactive sign-in in CI.
        exc = AuthCommandForbiddenInCiError(command="login")
        _handle_sentinel_error(exc)
        return

    try:
        resolved_profile = resolve_profile(profile) if profile else None
    except ProfileNotFoundError as exc:
        _emit_stderr(f"error[E-CFG-002]: {exc}")
        raise typer.Exit(code=EXIT_CONFIG_ERROR) from exc

    try:
        target_host = host_pair_from_login_url(url, target)
    except ValueError as exc:
        _emit_stderr(f"error[E-CFG-002]: {exc}")
        raise typer.Exit(code=EXIT_CONFIG_ERROR) from exc

    allowed = hosts_iterable(target_host, allowed_host or [])
    request = LoginRequest(
        name=name,
        login_url=url,
        target_host=target_host,
        allowed_hosts=allowed,
        profile=resolved_profile,
        browser=cast("Any", browser),
        ttl_hours=ttl_hours,
        force=force,
        ci=state.ci,
        audit_log_path=_audit_log_path(),
    )

    vault = Vault()
    launcher = _resolve_launcher()

    try:
        result = capture_session(request, vault=vault, launcher=launcher)
    except SentinelError as exc:
        _handle_sentinel_error(exc)
        return
    except RuntimeError as exc:
        _emit_stderr(f"error[E-DEP-001]: {exc}")
        raise typer.Exit(code=EXIT_DEPENDENCY_MISSING) from exc

    payload = {
        "command": "auth.login",
        "host": result.entry.host,
        "name": result.entry.name,
        "cookies_count": result.entry.cookies_count,
        "local_storage_keys": result.entry.local_storage_keys,
        "expires_at": result.entry.expires_at.isoformat(),
        "vault_path": str(result.vault_path),
    }
    if state.mode == "json":
        with json_stdout() as out:
            out.emit(payload)
        raise typer.Exit(code=EXIT_SUCCESS)

    _emit_human(f"Captured session for {result.entry.host} → entry '{result.entry.name}'.")
    _emit_human(
        f"  cookies   : {result.entry.cookies_count}\n"
        f"  storage   : {result.entry.local_storage_keys} key(s)\n"
        f"  expires   : {result.entry.expires_at.isoformat()}\n"
        f"  vault path: {result.vault_path}"
    )
    raise typer.Exit(code=EXIT_SUCCESS)


def _resolve_launcher() -> BrowserLauncher:
    """Return the production Playwright launcher.

    Wrapped in a helper so tests can monkey-patch a stub.
    """

    return PlaywrightLauncher()


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@auth_app.command("list", help="List vault entries (redacted metadata only).")
def list_cmd(
    ctx: typer.Context,
    host: Annotated[
        str | None,
        typer.Option("--host", help="Filter to one host."),
    ] = None,
) -> None:
    state: GlobalState = ctx.obj
    vault = Vault()
    entries = vault.list()
    if host is not None:
        host_lower = host.strip().lower()
        entries = [e for e in entries if e.host == host_lower]

    if state.mode == "json":
        with json_stdout() as out:
            out.emit(
                {
                    "command": "auth.list",
                    "count": len(entries),
                    "entries": [_metadata_payload(e) for e in entries],
                }
            )
        write_audit_entry(
            _audit_log_path(),
            {"event": "auth.list", "count": len(entries)},
        )
        raise typer.Exit(code=EXIT_SUCCESS)

    if not entries:
        _emit_human("No vault entries.")
        write_audit_entry(_audit_log_path(), {"event": "auth.list", "count": 0})
        raise typer.Exit(code=EXIT_SUCCESS)

    header = f"{'host':30s}  {'name':24s}  {'cookies':>7s}  {'expires':25s}  state"
    _emit_human(header)
    _emit_human("-" * len(header))
    for entry in entries:
        state_label = "expired" if entry.expired else "ok"
        _emit_human(
            f"{entry.host:30s}  {entry.name:24s}  "
            f"{entry.cookies_count:7d}  {entry.expires_at.isoformat():25s}  {state_label}"
        )
    write_audit_entry(
        _audit_log_path(),
        {"event": "auth.list", "count": len(entries)},
    )
    raise typer.Exit(code=EXIT_SUCCESS)


def _metadata_payload(entry: VaultMetadata) -> dict[str, Any]:
    return {
        "host": entry.host,
        "name": entry.name,
        "created_at": entry.created_at.isoformat(),
        "expires_at": entry.expires_at.isoformat(),
        "last_used_at": entry.last_used_at.isoformat() if entry.last_used_at else None,
        "cookies_count": entry.cookies_count,
        "local_storage_keys": entry.local_storage_keys,
        "expired": entry.expired,
    }


# ---------------------------------------------------------------------------
# list-profiles
# ---------------------------------------------------------------------------


@auth_app.command("list-profiles", help="Show built-in auth profiles (OAuth + LLM-web).")
def list_profiles_cmd(ctx: typer.Context) -> None:
    state: GlobalState = ctx.obj
    profiles = list_profiles()

    if state.mode == "json":
        with json_stdout() as out:
            out.emit(
                {
                    "command": "auth.list-profiles",
                    "count": len(profiles),
                    "profiles": [
                        {
                            "name": p.name,
                            "label": p.label,
                            "category": p.category,
                            "login_url_pattern": p.login_url_pattern,
                            "success_url_patterns": list(p.success_url_patterns),
                            "tos_url": p.tos_url,
                            "mfa_hint": p.mfa_hint,
                        }
                        for p in profiles
                    ],
                }
            )
        raise typer.Exit(code=EXIT_SUCCESS)

    _emit_human(f"{'name':18s}  {'category':10s}  {'login URL'}")
    _emit_human("-" * 80)
    for profile in profiles:
        _emit_human(f"{profile.name:18s}  {profile.category:10s}  {profile.login_url_pattern}")
    raise typer.Exit(code=EXIT_SUCCESS)


# ---------------------------------------------------------------------------
# revoke
# ---------------------------------------------------------------------------


@auth_app.command("revoke", help="Delete a vault entry. `--all` deletes every entry.")
def revoke_cmd(
    ctx: typer.Context,
    name: Annotated[
        str | None,
        typer.Argument(help="Entry name to revoke (omit when using --all)."),
    ] = None,
    host: Annotated[
        str | None,
        typer.Option("--host", help="Host the entry is filed under."),
    ] = None,
    all_entries: Annotated[
        bool,
        typer.Option("--all", help="Delete every vault entry."),
    ] = False,
    yes_i_mean_it: Annotated[
        bool,
        typer.Option(
            "--yes-i-mean-it",
            help="Skip the typed confirmation (refused in CI).",
        ),
    ] = False,
) -> None:
    state: GlobalState = ctx.obj
    vault = Vault()

    if all_entries:
        if state.ci and not yes_i_mean_it:
            exc = AuthCommandForbiddenInCiError(command="revoke --all")
            _handle_sentinel_error(exc)
            return
        if not yes_i_mean_it:
            sys.stderr.write(
                "About to delete EVERY SentinelQA vault entry.\n" "Type 'delete all' to confirm: "
            )
            sys.stderr.flush()
            line = sys.stdin.readline().strip()
            if line != "delete all":
                _emit_stderr("aborted.")
                raise typer.Exit(code=EXIT_CONFIG_ERROR)
        removed = vault.revoke_all()
        write_audit_entry(
            _audit_log_path(),
            {"event": "auth.revoke", "scope": "all", "removed": removed},
        )
        if state.mode == "json":
            with json_stdout() as out:
                out.emit({"command": "auth.revoke", "scope": "all", "removed": removed})
        else:
            _emit_human(f"Removed {removed} vault entr{'y' if removed == 1 else 'ies'}.")
        raise typer.Exit(code=EXIT_SUCCESS)

    if not name or not host:
        _emit_stderr("error[E-CFG-002]: revoke requires a NAME argument and --host, " "or --all.")
        raise typer.Exit(code=EXIT_CONFIG_ERROR)

    removed = vault.revoke(host, name)
    write_audit_entry(
        _audit_log_path(),
        {
            "event": "auth.revoke",
            "scope": "entry",
            "host": host.strip().lower(),
            "name": name,
            "removed": removed,
        },
    )
    if state.mode == "json":
        with json_stdout() as out:
            out.emit(
                {
                    "command": "auth.revoke",
                    "scope": "entry",
                    "host": host.strip().lower(),
                    "name": name,
                    "removed": removed,
                }
            )
        raise typer.Exit(code=EXIT_SUCCESS)
    if removed:
        _emit_human(f"Removed vault entry {name!r} for {host}.")
    else:
        _emit_human(f"No vault entry named {name!r} for {host}.")
    raise typer.Exit(code=EXIT_SUCCESS)


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------


@auth_app.command(
    "export",
    help="Decrypt and write plaintext storage_state (requires --i-acknowledge).",
)
def export_cmd(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Vault entry name.")],
    host: Annotated[str, typer.Option("--host", help="Host the entry is filed under.")],
    out: Annotated[
        Path,
        typer.Option("--out", help="Output path for the plaintext JSON file."),
    ],
    acknowledge: Annotated[
        bool,
        typer.Option(
            "--i-acknowledge",
            help="Confirm you understand the file contains plaintext cookies.",
        ),
    ] = False,
) -> None:
    state: GlobalState = ctx.obj
    if state.ci:
        exc = AuthCommandForbiddenInCiError(command="export")
        _handle_sentinel_error(exc)
        return
    if not acknowledge:
        _emit_stderr(
            "error[E-CFG-002]: export requires --i-acknowledge; the output "
            "file will contain plaintext session cookies."
        )
        raise typer.Exit(code=EXIT_CONFIG_ERROR)

    _emit_stderr(
        "WARNING: writing plaintext session export. Treat the output file "
        "like a password manager backup. Encrypt it before sharing."
    )

    vault = Vault()
    try:
        plaintext = vault.export_plaintext(host, name, allowed_hosts={host.strip().lower()})
    except SentinelError as exc:
        _handle_sentinel_error(exc)
        return
    except Exception as exc:  # pragma: no cover - defensive
        _emit_stderr(f"error[E-INT-001]: {exc}")
        raise typer.Exit(code=EXIT_INTERNAL_ERROR) from exc

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(plaintext, encoding="utf-8")
    with contextlib.suppress(OSError, NotImplementedError):
        out.chmod(0o600)

    write_audit_entry(
        _audit_log_path(),
        {
            "event": "auth.export",
            "host": host.strip().lower(),
            "name": name,
            "target_path": str(out),
            "ack": True,
        },
    )
    if state.mode == "json":
        with json_stdout() as out_stream:
            out_stream.emit(
                {
                    "command": "auth.export",
                    "host": host.strip().lower(),
                    "name": name,
                    "target_path": str(out),
                    "bytes": len(plaintext),
                }
            )
    else:
        _emit_human(f"Wrote plaintext storage state to {out} ({len(plaintext)} bytes).")
    raise typer.Exit(code=EXIT_SUCCESS)


__all__ = ["auth_app"]

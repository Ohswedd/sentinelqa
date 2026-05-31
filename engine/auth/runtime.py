"""Runtime helpers that bridge the vault and the audit lifecycle.

The Phase-08 :class:`engine.runner.local.LocalRunner` and the Phase-05
crawler both consume a Playwright ``storage_state`` JSON file when the
config sets ``auth.strategy: browser_session``. This module provides the
narrow surface they need:

- :func:`materialize_storage_state` — decrypt the entry, write it to
  ``<run-dir>/auth/storage_state.json`` (chmod 0600), audit-log the use,
  return the path. Caller is responsible for calling
  :func:`cleanup_storage_state` on teardown so the plaintext file does
  not survive the run.
- :func:`load_storage_state_dict` — same as above but returns the
  decoded dict in-memory; used by the discovery crawler so cookies can
  be injected into the ``httpx`` client without ever hitting disk.

The audit log carries one line per use: host + name + cookie count +
age in seconds. Cookie values and local-storage payloads NEVER appear.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from engine.auth.models import VaultEntry
from engine.auth.vault import Vault
from engine.policy.audit_log import write_audit_entry

STORAGE_STATE_FILENAME = "storage_state.json"


@dataclass(frozen=True)
class SessionHandle:
    """Path + metadata for a materialized session.

    ``path`` is the on-disk JSON file. Call :func:`cleanup_storage_state`
    (or use :func:`session_scope`) to remove it after the run.
    """

    host: str
    name: str
    path: Path
    cookies_count: int
    age_seconds: float


def materialize_storage_state(
    vault: Vault,
    *,
    host: str,
    name: str,
    run_dir: Path,
    allowed_hosts: Iterable[str],
    audit_log_path: Path | None = None,
    now: datetime | None = None,
) -> SessionHandle:
    """Decrypt the entry and write the plaintext storage_state to ``run_dir``.

    Returns a :class:`SessionHandle` carrying the file path + redacted
    metadata. The file lands at
    ``<run-dir>/auth/storage_state.json``; the directory is created if
    needed and chmod'd 0700 (POSIX). The file is chmod'd 0600.
    """

    ts_now = now or datetime.now(UTC)
    entry: VaultEntry = vault.get(host, name, allowed_hosts=allowed_hosts, now=ts_now, touch=True)
    auth_dir = run_dir / "auth"
    auth_dir.mkdir(parents=True, exist_ok=True)
    with suppress(OSError, NotImplementedError):
        auth_dir.chmod(0o700)
    target = auth_dir / STORAGE_STATE_FILENAME
    target.write_text(entry.storage_state_json, encoding="utf-8")
    with suppress(OSError, NotImplementedError):
        target.chmod(0o600)

    handle = SessionHandle(
        host=entry.host,
        name=entry.name,
        path=target,
        cookies_count=entry.cookies_count,
        age_seconds=(ts_now - entry.created_at).total_seconds(),
    )

    if audit_log_path is not None:
        write_audit_entry(
            audit_log_path,
            {
                "event": "auth.session_used",
                "host": handle.host,
                "name": handle.name,
                "cookies_count": handle.cookies_count,
                "age_seconds": round(handle.age_seconds, 2),
            },
        )
    return handle


def cleanup_storage_state(handle: SessionHandle) -> None:
    """Remove the materialized plaintext file. Idempotent."""

    try:
        handle.path.unlink()
    except FileNotFoundError:
        return
    # Best-effort: remove the auth directory if it is now empty so the
    # `latest` symlink + report uploaders never see it.
    parent = handle.path.parent
    try:
        if parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
    except OSError:
        pass


@contextmanager
def session_scope(
    vault: Vault,
    *,
    host: str,
    name: str,
    run_dir: Path,
    allowed_hosts: Iterable[str],
    audit_log_path: Path | None = None,
) -> Iterator[SessionHandle]:
    """Materialize → yield → cleanup. Preferred for `with` blocks."""

    handle = materialize_storage_state(
        vault,
        host=host,
        name=name,
        run_dir=run_dir,
        allowed_hosts=allowed_hosts,
        audit_log_path=audit_log_path,
    )
    try:
        yield handle
    finally:
        cleanup_storage_state(handle)


def load_storage_state_dict(
    vault: Vault,
    *,
    host: str,
    name: str,
    allowed_hosts: Iterable[str],
    audit_log_path: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return the decoded storage_state dict WITHOUT writing it to disk.

    Used by the Python discovery crawler so cookies can be injected
    into an ``httpx.Client`` directly. Audit-logs the use just like
    :func:`materialize_storage_state`.
    """

    ts_now = now or datetime.now(UTC)
    entry = vault.get(host, name, allowed_hosts=allowed_hosts, now=ts_now, touch=True)
    payload = json.loads(entry.storage_state_json)
    if audit_log_path is not None:
        write_audit_entry(
            audit_log_path,
            {
                "event": "auth.session_used",
                "host": entry.host,
                "name": entry.name,
                "cookies_count": entry.cookies_count,
                "age_seconds": round((ts_now - entry.created_at).total_seconds(), 2),
            },
        )
    return payload  # type: ignore[no-any-return]


def cookies_for_host(storage_state: dict[str, Any], host: str) -> dict[str, str]:
    """Flatten Playwright ``storage_state.cookies`` for the given host.

    Returns a ``{name: value}`` mapping the discovery crawler can pass
    into :meth:`engine.discovery.crawler.Crawler.crawl` via the
    ``extra_cookies`` argument. Only cookies whose ``domain`` field
    matches (or is a parent of) ``host`` are included.
    """

    host_lower = host.strip().lower()
    out: dict[str, str] = {}
    for cookie in storage_state.get("cookies") or []:
        if not isinstance(cookie, dict):
            continue
        domain = str(cookie.get("domain", "")).lstrip(".").lower()
        if not domain:
            continue
        # Cookie applies when host equals the cookie's domain or is a
        # subdomain of it (matches the RFC 6265 attribute semantics).
        if host_lower != domain and not host_lower.endswith("." + domain):
            continue
        name = cookie.get("name")
        value = cookie.get("value")
        if isinstance(name, str) and isinstance(value, str):
            out[name] = value
    return out


__all__ = [
    "STORAGE_STATE_FILENAME",
    "SessionHandle",
    "cleanup_storage_state",
    "cookies_for_host",
    "load_storage_state_dict",
    "materialize_storage_state",
    "session_scope",
]

"""On-disk encrypted vault for Playwright ``storage_state`` blobs.

Phase 31 / ADR-0043. The vault lives at::

    ~/.sentinel/auth/<host-slug>/<name>.json.enc

Each ``.json.enc`` file is the AES-256-GCM ciphertext of a small JSON
envelope::

    {
      "schema_version": "1.0.0",
      "name": "<name>",
      "host": "<host>",
      "storage_state_json": "{...playwright storage_state...}",
      "created_at": "...",
      "expires_at": "...",
      "last_used_at": null,
      "cookies_count": 7,
      "local_storage_keys": 2,
      "captured_by": "cli"
    }

The associated-data field of the AEAD includes the schema version + the
``host:name`` pair, so swapping a ciphertext file from one entry to
another fails decryption.

Vault operations refuse to do anything dangerous silently:

- :meth:`get` requires an ``allowed_hosts`` set and raises
  :class:`engine.errors.base.VaultHostMismatchError` when the stored host
  is not in that set (CLAUDE.md §6).
- :meth:`get` raises :class:`engine.errors.base.VaultEntryExpiredError`
  when the stored ``expires_at`` is in the past.
- :meth:`list` returns redacted :class:`VaultMetadata` only — the
  storage state is never even decrypted during a list.

The vault never logs storage_state values; the audit log carries counts
only (cookies, local-storage keys).
"""

from __future__ import annotations

import contextlib
import json
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from engine.auth.crypto import CryptoError, decrypt_blob, encrypt_blob
from engine.auth.keyring_store import KeyringStore
from engine.auth.models import VaultEntry, VaultMetadata
from engine.errors.base import (
    VaultEntryExpiredError,
    VaultEntryNotFoundError,
    VaultHostMismatchError,
    VaultIntegrityError,
)

#: Schema version embedded in the encrypted envelope. Bump when the
#: envelope shape changes; old files become unreadable (refuse, prompt
#: re-capture) rather than getting silently migrated.
VAULT_SCHEMA_VERSION = "1.0.0"

#: Filename suffix for encrypted entries.
ENTRY_SUFFIX = ".json.enc"

#: Env var that overrides the default vault root (test hook + power users).
VAULT_ROOT_ENV_VAR = "SENTINEL_VAULT_ROOT"

_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]{0,127}$")
_SLUG_REPLACE = re.compile(r"[^a-z0-9._\-]")


class VaultError(Exception):
    """Base for vault file-layout / IO failures (not safety boundary).

    Safety-boundary refusals (host mismatch, expired entry, AEAD failure)
    raise the typed :class:`engine.errors.base.AuthError` subclasses
    instead — those exit with code 4 (unsafe target) and have CLI-grade
    suggested fixes.
    """


def host_slug(host: str) -> str:
    """Return a filesystem-safe slug for ``host``.

    Lowercases, replaces every char that isn't ``[a-z0-9._-]`` with an
    underscore, and prepends ``__`` if the result starts with a dot
    (avoids accidentally creating hidden directories).
    """

    lowered = host.strip().lower()
    slug = _SLUG_REPLACE.sub("_", lowered)
    if slug.startswith("."):
        slug = "__" + slug
    return slug or "unknown"


def _validate_name(name: str) -> str:
    if not _NAME_PATTERN.fullmatch(name):
        raise ValueError(
            f"Vault entry name {name!r} must match {_NAME_PATTERN.pattern} "
            "(alphanumerics, dots, dashes, underscores)."
        )
    return name


def _resolve_root(root: Path | None) -> Path:
    if root is not None:
        return root
    env = os.environ.get(VAULT_ROOT_ENV_VAR)
    if env:
        return Path(env)
    return Path.home() / ".sentinel" / "auth"


def _associated_data(host: str, name: str) -> bytes:
    return f"{VAULT_SCHEMA_VERSION}:{host}:{name}".encode()


def _safe_int(value: object) -> int:
    """Coerce ``value`` to ``int``; default to 0 on None / unknown shape."""

    if value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


@dataclass
class Vault:
    """File-backed vault. Stateless across calls.

    Construct with ``Vault()`` for production code; tests pass an
    explicit ``root`` and ``key_store`` so they don't touch the user's
    real keyring or home directory.
    """

    root: Path = field(default_factory=lambda: _resolve_root(None))
    key_store: KeyringStore = field(default_factory=KeyringStore)
    _materialized_root: bool = field(default=False, init=False)

    # ------------------------------------------------------------------
    # Write paths
    # ------------------------------------------------------------------

    def put(self, entry: VaultEntry, *, force: bool = False) -> Path:
        """Encrypt + write ``entry``. Returns the absolute file path.

        Raises :class:`VaultError` if an entry with the same name + host
        already exists and ``force`` is False.
        """

        _validate_name(entry.name)
        slug = host_slug(entry.host)
        target_dir = self.root / slug
        self._ensure_dir(target_dir)
        target = target_dir / f"{entry.name}{ENTRY_SUFFIX}"
        if target.exists() and not force:
            raise VaultError(
                f"vault entry already exists at {target}; pass force=True " "to overwrite."
            )
        envelope = self._envelope_from_entry(entry)
        plaintext = json.dumps(envelope, separators=(",", ":"), sort_keys=True).encode("utf-8")
        with self.key_store.load_or_create() as key:
            blob = encrypt_blob(
                key, plaintext, associated_data=_associated_data(entry.host, entry.name)
            )
        target.write_bytes(blob)
        self._chmod_0600(target)
        self._write_metadata_sidecar(entry)
        return target

    def revoke(self, host: str, name: str) -> bool:
        """Delete the entry. Returns True if a file was removed.

        Never raises if the entry is missing — `auth revoke` is
        idempotent by design.
        """

        _validate_name(name)
        slug_dir = self.root / host_slug(host)
        target = slug_dir / f"{name}{ENTRY_SUFFIX}"
        sidecar = slug_dir / f"{name}.json.meta"
        removed = False
        if target.exists():
            target.unlink()
            removed = True
        if sidecar.exists():
            sidecar.unlink()
        if not removed:
            return False
        # Best-effort: prune the host directory if empty so `auth list`
        # doesn't show stale folders.
        try:
            if slug_dir.exists() and not any(slug_dir.iterdir()):
                slug_dir.rmdir()
        except OSError:
            pass
        return True

    def revoke_all(self) -> int:
        """Delete every entry. Returns the number of files removed.

        Caller is responsible for prompting the operator before this
        runs (the CLI gates it behind ``--all`` + a typed confirmation).
        Does NOT touch the OS-keyring master key — call
        ``self.key_store.reset()`` separately if needed.
        """

        if not self.root.exists():
            return 0
        removed = 0
        for slug_dir in self.root.iterdir():
            if not slug_dir.is_dir():
                continue
            for path in slug_dir.glob(f"*{ENTRY_SUFFIX}"):
                path.unlink()
                removed += 1
            for path in slug_dir.glob("*.json.meta"):
                path.unlink()
            try:
                if not any(slug_dir.iterdir()):
                    slug_dir.rmdir()
            except OSError:
                pass
        return removed

    # ------------------------------------------------------------------
    # Read paths
    # ------------------------------------------------------------------

    def get(
        self,
        host: str,
        name: str,
        *,
        allowed_hosts: Iterable[str],
        now: datetime | None = None,
        touch: bool = True,
    ) -> VaultEntry:
        """Decrypt + return the entry. Enforces the host-match safety guard.

        ``allowed_hosts`` is the set drawn from the active target — the
        vault refuses to surface a session that doesn't match. ``now`` is
        a test hook for expiry checks.
        """

        _validate_name(name)
        target = self.root / host_slug(host) / f"{name}{ENTRY_SUFFIX}"
        if not target.exists():
            raise VaultEntryNotFoundError(host=host, name=name)
        allowed_lower = {h.strip().lower() for h in allowed_hosts}
        host_lower = host.strip().lower()
        if host_lower not in allowed_lower:
            raise VaultHostMismatchError(
                vault_host=host_lower,
                target_host="(unknown)",
                name=name,
                technical_context={
                    "vault_host": host_lower,
                    "name": name,
                    "allowed_hosts": sorted(allowed_lower),
                },
            )
        with self.key_store.load_existing() as key:
            try:
                plaintext = decrypt_blob(
                    key,
                    target.read_bytes(),
                    associated_data=_associated_data(host, name),
                )
            except CryptoError as exc:
                raise VaultIntegrityError(
                    host=host,
                    name=name,
                    technical_context={"host": host, "name": name},
                ) from exc
        envelope = json.loads(plaintext.decode("utf-8"))
        entry = self._entry_from_envelope(envelope)
        # The stored host MUST match the path-derived slug. Defends
        # against an attacker swapping ciphertext files across host
        # directories (the AEAD AD would already catch this, but the
        # belt-and-braces check makes the failure self-explanatory).
        if host_slug(entry.host) != host_slug(host):
            raise VaultHostMismatchError(
                vault_host=host_slug(entry.host),
                target_host=host_slug(host),
                name=name,
            )
        ts_now = now or datetime.now(UTC)
        if ts_now >= entry.expires_at:
            raise VaultEntryExpiredError(
                host=host,
                name=name,
                expires_at=entry.expires_at.isoformat(),
            )
        if touch:
            updated = entry.model_copy(update={"last_used_at": ts_now})
            self._rewrite_envelope(updated)
            return updated
        return entry

    def list(self) -> list[VaultMetadata]:
        """Return metadata for every entry. Sorted by host, then name.

        Does NOT decrypt the storage_state. The cookie / local-storage
        counts come from the stored metadata file, which means the
        ciphertext has to be read but the body is decrypted only by
        :meth:`get`. To keep `list` cheap and leak-proof, we maintain a
        sidecar metadata file (`.json.meta`) next to every entry; the
        sidecar carries the redacted view only.
        """

        if not self.root.exists():
            return []
        out: list[VaultMetadata] = []
        for slug_dir in sorted(p for p in self.root.iterdir() if p.is_dir()):
            for meta_path in sorted(slug_dir.glob("*.json.meta")):
                try:
                    payload = json.loads(meta_path.read_text(encoding="utf-8"))
                    out.append(VaultMetadata.model_validate(payload))
                except (OSError, json.JSONDecodeError, ValueError):
                    # A corrupt sidecar shouldn't break `auth list`; skip.
                    continue
        return out

    def has(self, host: str, name: str) -> bool:
        """Return True if an entry exists for (host, name)."""

        _validate_name(name)
        return (self.root / host_slug(host) / f"{name}{ENTRY_SUFFIX}").exists()

    # ------------------------------------------------------------------
    # Export (only ever used by `sentinel auth export --i-acknowledge`)
    # ------------------------------------------------------------------

    def export_plaintext(
        self,
        host: str,
        name: str,
        *,
        allowed_hosts: Iterable[str],
        now: datetime | None = None,
    ) -> str:
        """Decrypt and return the storage_state JSON.

        Bypasses the ``touch`` write so an export doesn't bump
        ``last_used_at``. Callers MUST surface the warning copy required
        by task 31.03 before invoking this.
        """

        entry = self.get(host, name, allowed_hosts=allowed_hosts, now=now, touch=False)
        return entry.storage_state_json

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _envelope_from_entry(self, entry: VaultEntry) -> dict[str, object]:
        return {
            "schema_version": VAULT_SCHEMA_VERSION,
            "name": entry.name,
            "host": entry.host,
            "storage_state_json": entry.storage_state_json,
            "created_at": entry.created_at.isoformat(),
            "expires_at": entry.expires_at.isoformat(),
            "last_used_at": (entry.last_used_at.isoformat() if entry.last_used_at else None),
            "cookies_count": entry.cookies_count,
            "local_storage_keys": entry.local_storage_keys,
            "captured_by": entry.captured_by,
        }

    def _entry_from_envelope(self, envelope: dict[str, object]) -> VaultEntry:
        if envelope.get("schema_version") != VAULT_SCHEMA_VERSION:
            raise VaultError(
                f"vault schema version mismatch: stored="
                f"{envelope.get('schema_version')!r} "
                f"current={VAULT_SCHEMA_VERSION!r}. "
                "Re-capture the session."
            )
        created_at = datetime.fromisoformat(str(envelope["created_at"]))
        expires_at = datetime.fromisoformat(str(envelope["expires_at"]))
        last_used_raw = envelope.get("last_used_at")
        last_used_at = datetime.fromisoformat(str(last_used_raw)) if last_used_raw else None
        return VaultEntry(
            name=str(envelope["name"]),
            host=str(envelope["host"]),
            storage_state_json=str(envelope["storage_state_json"]),
            created_at=created_at,
            expires_at=expires_at,
            last_used_at=last_used_at,
            cookies_count=_safe_int(envelope.get("cookies_count")),
            local_storage_keys=_safe_int(envelope.get("local_storage_keys")),
            captured_by=str(envelope.get("captured_by") or "cli"),
        )

    def _rewrite_envelope(self, entry: VaultEntry) -> None:
        """Persist a fresh envelope (used to update ``last_used_at``)."""

        slug = host_slug(entry.host)
        target = self.root / slug / f"{entry.name}{ENTRY_SUFFIX}"
        envelope = self._envelope_from_entry(entry)
        plaintext = json.dumps(envelope, separators=(",", ":"), sort_keys=True).encode("utf-8")
        with self.key_store.load_existing() as key:
            blob = encrypt_blob(
                key, plaintext, associated_data=_associated_data(entry.host, entry.name)
            )
        target.write_bytes(blob)
        self._chmod_0600(target)
        self._write_metadata_sidecar(entry)

    def _write_metadata_sidecar(self, entry: VaultEntry) -> None:
        slug = host_slug(entry.host)
        meta_path = self.root / slug / f"{entry.name}.json.meta"
        meta_payload = entry.to_metadata().model_dump(mode="json")
        meta_path.write_text(
            json.dumps(meta_payload, separators=(",", ":"), sort_keys=True),
            encoding="utf-8",
        )
        self._chmod_0600(meta_path)

    def _ensure_dir(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        # Best-effort directory permissions.
        with contextlib.suppress(OSError, NotImplementedError):
            path.chmod(0o700)

    def _chmod_0600(self, path: Path) -> None:
        # Windows / network FS won't honor mode bits — not a refusal.
        with contextlib.suppress(OSError, NotImplementedError):
            path.chmod(0o600)


__all__ = [
    "ENTRY_SUFFIX",
    "VAULT_ROOT_ENV_VAR",
    "VAULT_SCHEMA_VERSION",
    "Vault",
    "VaultError",
    "host_slug",
]

"""Master-key acquisition (, ADR-0043).

The vault stores its AES-256-GCM master key in the operator's OS keyring
(Login Keychain on macOS, Secret Service / kwallet on Linux, Credential
Manager on Windows) under the service name ``sentinelqa-vault`` and the
account name ``default``. When the keyring isn't available (headless
Linux box, locked-down CI, missing ``dbus`` daemon), we fall back to a
PBKDF2-SHA256 derivation of a passphrase the operator supplies via the
``SENTINEL_VAULT_PASSPHRASE`` env var or a stdin prompt.

Design points:

- The Python ``keyring`` library is an optional import. The vault works
 without it, but the only available code path then is the passphrase
 fallback. We never silently switch to "no encryption."
- The PBKDF2 salt is stored in plaintext under
 ``~/.sentinel/auth/.salt``. The salt itself is not a secret — knowing
 it doesn't help an attacker without the passphrase — and persisting
 it keeps subsequent runs reproducible.
- The iteration count is fixed at 600_000 (NIST SP 800-132 / OWASP 2026
 guidance for SHA-256). Configurable upward via
 ``SENTINEL_VAULT_PBKDF2_ITERATIONS`` for future hardening, but never
 downward.
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from engine.auth.crypto import KEY_BYTES, MasterKey, random_salt

#: OS keyring service + account labels. Stable across versions.
KEYRING_SERVICE = "sentinelqa-vault"
KEYRING_ACCOUNT = "default"

#: PBKDF2 floor; opt UP via SENTINEL_VAULT_PBKDF2_ITERATIONS, never down.
DEFAULT_PBKDF2_ITERATIONS = 600_000

#: Env var that carries the passphrase in headless environments.
PASSPHRASE_ENV_VAR = "SENTINEL_VAULT_PASSPHRASE"

#: Env var that carries the per-vault salt path override (test hook).
SALT_PATH_ENV_VAR = "SENTINEL_VAULT_SALT_PATH"


class KeyringUnavailableError(RuntimeError):
    """Raised when the OS keyring backend can't be reached."""


class _KeyringBackend(Protocol):
    """Minimal subset of the :mod:`keyring` library we depend on."""

    def get_password(self, service: str, username: str) -> str | None: ...

    def set_password(self, service: str, username: str, password: str) -> None: ...

    def delete_password(self, service: str, username: str) -> None: ...


def _import_keyring() -> _KeyringBackend | None:
    """Import :mod:`keyring`. Returns ``None`` when unavailable.

    Wrapped in a function so tests can monkey-patch the import; the
    library itself is not a hard dependency.
    """

    try:
        import keyring  # type: ignore[import-not-found,unused-ignore]
    except Exception:
        return None
    # `keyring`'s public functions are module-level — adapt to our Protocol.
    backend: _KeyringBackend = keyring
    return backend


def _resolve_salt_path() -> Path:
    override = os.environ.get(SALT_PATH_ENV_VAR)
    if override:
        return Path(override)
    return Path.home() / ".sentinel" / "auth" / ".salt"


def _resolve_iterations() -> int:
    raw = os.environ.get("SENTINEL_VAULT_PBKDF2_ITERATIONS")
    if not raw:
        return DEFAULT_PBKDF2_ITERATIONS
    try:
        parsed = int(raw)
    except ValueError as exc:
        raise ValueError(f"{raw!r} is not a valid PBKDF2 iteration count.") from exc
    if parsed < DEFAULT_PBKDF2_ITERATIONS:
        raise ValueError(
            f"SENTINEL_VAULT_PBKDF2_ITERATIONS={parsed} is below the "
            f"hardened floor ({DEFAULT_PBKDF2_ITERATIONS}). Refusing."
        )
    return parsed


@dataclass
class KeyringStore:
    """Acquire / store the master key, OS-keyring first.

    Construct with the defaults (``KeyringStore()``) for production code;
    pass overrides in tests via :meth:`with_backends` (see the unit tests).
    """

    backend: _KeyringBackend | None = None
    salt_path: Path | None = None
    passphrase_provider: Callable[[], str] | None = None
    iterations: int | None = None

    def __post_init__(self) -> None:
        if self.backend is None:
            self.backend = _import_keyring()
        if self.salt_path is None:
            self.salt_path = _resolve_salt_path()
        if self.iterations is None:
            self.iterations = _resolve_iterations()

    # ------------------------------------------------------------------
    # Key acquisition
    # ------------------------------------------------------------------

    def load_or_create(self) -> MasterKey:
        """Return the master key, creating one if none exists yet.

        Tries the OS keyring first, then falls back to the passphrase
        path. Either way, the returned :class:`MasterKey` is fresh —
        owners should ``.close()`` it (or use it as a context manager).
        """

        keyring_key = self._load_from_keyring()
        if keyring_key is not None:
            return keyring_key
        if self.backend is not None:
            # Keyring exists but has no entry yet: mint, store, return.
            return self._mint_and_store_in_keyring()
        # No keyring backend at all → passphrase fallback.
        return self._load_from_passphrase()

    def load_existing(self) -> MasterKey:
        """Return the master key. Refuses to mint a new one.

        Raises :class:`KeyringUnavailableError` when no key has ever
        been stored — that's the signal the caller is dealing with a
        fresh machine and must run ``sentinel auth login`` first.
        """

        keyring_key = self._load_from_keyring()
        if keyring_key is not None:
            return keyring_key
        if self.backend is not None:
            raise KeyringUnavailableError(
                "Master key not yet stored in OS keyring. "
                "Run `sentinel auth login` to create one."
            )
        # No keyring → passphrase fallback also handles the existing-key
        # case (it derives from the same passphrase + salt).
        return self._load_from_passphrase(refuse_create=True)

    def reset(self) -> None:
        """Remove the master key from the OS keyring AND the salt file.

        Used by `sentinel auth revoke --all` after every vault file has
        been deleted; the operator can start clean.
        """

        if self.backend is not None:
            # The library's exception hierarchy varies by backend; we
            # treat any failure as "nothing to delete."
            with contextlib.suppress(Exception):
                self.backend.delete_password(KEYRING_SERVICE, KEYRING_ACCOUNT)
        salt_path = self.salt_path
        if salt_path is not None and salt_path.exists():
            salt_path.unlink()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load_from_keyring(self) -> MasterKey | None:
        if self.backend is None:
            return None
        try:
            raw = self.backend.get_password(KEYRING_SERVICE, KEYRING_ACCOUNT)
        except Exception as exc:
            # Keyring backend present but unreachable (locked keychain).
            raise KeyringUnavailableError(f"OS keyring is present but unreachable: {exc}") from exc
        if raw is None:
            return None
        try:
            material = bytes.fromhex(raw)
        except ValueError as exc:
            raise KeyringUnavailableError(
                "OS keyring returned a malformed master key entry."
            ) from exc
        if len(material) != KEY_BYTES:
            raise KeyringUnavailableError("OS keyring returned a master key of the wrong size.")
        return MasterKey.from_bytes(material)

    def _mint_and_store_in_keyring(self) -> MasterKey:
        assert self.backend is not None  # narrowed by caller
        new_key = MasterKey.generate()
        self.backend.set_password(KEYRING_SERVICE, KEYRING_ACCOUNT, new_key.view().hex())
        return new_key

    def _load_from_passphrase(self, *, refuse_create: bool = False) -> MasterKey:
        passphrase = self._read_passphrase()
        salt_path = self.salt_path
        assert salt_path is not None
        if salt_path.exists():
            salt = salt_path.read_bytes()
        else:
            if refuse_create:
                raise KeyringUnavailableError(
                    "Vault salt file is missing and refuse_create=True. "
                    "Run `sentinel auth login` to initialize the vault."
                )
            salt_path.parent.mkdir(parents=True, exist_ok=True)
            salt = random_salt(16)
            salt_path.write_bytes(salt)
            # Windows / some filesystems don't honor chmod.
            with contextlib.suppress(OSError, NotImplementedError):
                salt_path.chmod(0o600)
        assert self.iterations is not None
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=KEY_BYTES,
            salt=salt,
            iterations=self.iterations,
        )
        derived = kdf.derive(passphrase.encode("utf-8"))
        return MasterKey.from_bytes(derived)

    def _read_passphrase(self) -> str:
        if self.passphrase_provider is not None:
            value = self.passphrase_provider()
        else:
            value = os.environ.get(PASSPHRASE_ENV_VAR, "")
        if not value:
            raise KeyringUnavailableError(
                "No OS keyring is available and "
                f"{PASSPHRASE_ENV_VAR} is not set. "
                "Either run on a desktop with a keyring, or export the "
                "env var with a strong passphrase before retrying."
            )
        return value


__all__ = [
    "DEFAULT_PBKDF2_ITERATIONS",
    "KEYRING_ACCOUNT",
    "KEYRING_SERVICE",
    "KeyringStore",
    "KeyringUnavailableError",
    "PASSPHRASE_ENV_VAR",
    "SALT_PATH_ENV_VAR",
]

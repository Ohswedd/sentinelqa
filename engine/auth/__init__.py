"""Browser-authenticated audit subsystem (, ADR-0043).

Public surface:

- :class:`Vault` — encrypted store for per-target Playwright ``storage_state``
 blobs (cookies + ``localStorage``). AES-256-GCM at rest; master key in the
 OS keyring with a PBKDF2-passphrase fallback for headless environments.
- :class:`VaultEntry` — one stored session (metadata + ciphertext bookkeeping).
- :class:`VaultMetadata` — redacted view returned by :meth:`Vault.list`; the
 storage state itself is never present in the metadata view.
- :class:`MasterKey` — opaque handle around the 32-byte AEAD key (zeroed on
 ``close()``).
- :class:`AuthProfile` — documented launcher recipe for a login URL +
 success URL patterns + ToS link (Tasks 31.04, 31.05). Profiles never
 carry credential data structurally; the AST lint guard in
 ``tests/security/test_no_credentials_in_profiles.py`` enforces that
 invariant at the field-name level.

Hard rules (our engineering rules, §33):

- The operator signs in interactively in a real browser. SentinelQA never
 harvests usernames / passwords / OTPs / OAuth bearer tokens.
- A captured ``storage_state`` is encrypted before it lands on disk.
- The vault refuses to surface a session whose recorded host doesn't
 match the active target's allowlist (re-uses
 :class:`engine.policy.safety.SafetyPolicy`).
- Audit-log lines describing vault operations carry counts only — no
 cookie values, no localStorage payloads.
"""

from __future__ import annotations

from engine.auth.crypto import MasterKey, decrypt_blob, encrypt_blob
from engine.auth.keyring_store import KeyringStore, KeyringUnavailableError
from engine.auth.login import (
    BrowserLauncher,
    LoginRequest,
    LoginResult,
    PlaywrightLauncher,
    capture_session,
    host_pair_from_login_url,
    hosts_iterable,
)
from engine.auth.models import VaultEntry, VaultMetadata
from engine.auth.profiles import (
    AuthProfile,
    list_profiles,
    resolve_profile,
)
from engine.auth.runtime import (
    SessionHandle,
    cleanup_storage_state,
    cookies_for_host,
    load_storage_state_dict,
    materialize_storage_state,
    session_scope,
)
from engine.auth.vault import Vault, VaultError

__all__ = [
    "AuthProfile",
    "BrowserLauncher",
    "KeyringStore",
    "KeyringUnavailableError",
    "LoginRequest",
    "LoginResult",
    "MasterKey",
    "PlaywrightLauncher",
    "SessionHandle",
    "Vault",
    "VaultEntry",
    "VaultError",
    "VaultMetadata",
    "capture_session",
    "cleanup_storage_state",
    "cookies_for_host",
    "decrypt_blob",
    "encrypt_blob",
    "host_pair_from_login_url",
    "hosts_iterable",
    "list_profiles",
    "load_storage_state_dict",
    "materialize_storage_state",
    "resolve_profile",
    "session_scope",
]

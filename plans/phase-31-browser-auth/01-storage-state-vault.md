# Task 31.01 — Encrypted storage-state vault

## Deliverables

- `engine/auth/__init__.py` exports `Vault`, `VaultEntry`, `VaultError`,
  `MasterKey`.
- `engine/auth/vault.py`:
  - Uses the OS keyring (`keyring` library, already license-compatible
    Apache-2.0) to store / retrieve a 256-bit master key under the
    service name `sentinelqa-vault`, account `default`.
  - On systems without a working keyring (Linux without `dbus`, CI),
    falls back to a passphrase-derived key via PBKDF2-SHA256 with
    `iterations=600_000` and a random per-vault salt stored in
    `~/.sentinel/auth/.salt`. The passphrase is prompted via stdin and
    NEVER persisted.
  - Encrypts each `VaultEntry` (`{name, host, storage_state_json,
    created_at, last_used_at, expires_at}`) with AES-256-GCM via the
    `cryptography` library (already a transitive dep — pin explicitly).
  - File layout: `~/.sentinel/auth/<host-slug>/<name>.json.enc`. The
    filename contains only the slug + nonce; the encrypted blob carries
    name + state. Permissions `0600`.
- `vault.put(host, name, storage_state)` — encrypts + writes.
- `vault.get(host, name)` — decrypts; raises `VaultError` if expired,
  tampered, or wrong key.
- `vault.list()` — returns redacted metadata only (name, host,
  created_at, expires_at, last_used_at). Never decrypts state.
- `vault.revoke(host, name)` — deletes the file + zeros the in-memory
  copy.

## Tests required

- `tests/unit/auth/test_vault_crypto.py` — round-trip, tamper detection
  (mutate a byte → decrypt fails), expiry, file permissions.
- `tests/unit/auth/test_vault_keyring.py` — mocked `keyring` happy +
  unavailable + passphrase fallback paths.
- `tests/unit/auth/test_vault_listing.py` — listing does NOT decrypt;
  redacted metadata only.

## Definition of Done

- [ ] No plaintext storage state ever lands on disk.
- [ ] File permissions verified to be `0600` on POSIX.
- [ ] Vault tests green; ≥ 95 % coverage on `engine/auth/vault.py`.
- [ ] `STATUS.md` updated.

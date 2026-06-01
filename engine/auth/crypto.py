"""AEAD primitives for the auth vault (, ADR-0043).

The vault stores Playwright ``storage_state`` blobs encrypted with
AES-256-GCM via the PyCA :mod:`cryptography` library (already a direct
dep — see ``engine/pyproject.toml``). Each blob carries its own random
12-byte nonce; the master key is shared across the per-vault directory
and is held only as long as a :class:`MasterKey` instance is alive.

This module is intentionally minimal — encrypt one byte-string with one
key, decrypt one byte-string with one key. Higher-level concerns (file
layout, JSON encoding, expiry checks) live in :mod:`engine.auth.vault`.
"""

from __future__ import annotations

import ctypes
import os
import secrets
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

#: AES-256-GCM key size, in bytes.
KEY_BYTES = 32
#: AES-GCM standard nonce size (96 bits).
NONCE_BYTES = 12


class CryptoError(Exception):
    """Raised when AEAD decryption fails (tampered ciphertext, wrong key)."""


@dataclass
class MasterKey:
    """A 32-byte AEAD master key.

    Construct via :meth:`generate` or :meth:`from_bytes`. Call
    :meth:`close` (or use the context-manager API) to zero the key
    material out of the underlying buffer when you're done — Python
    can't truly guarantee the GC will not duplicate the bytes, but we do
    what we can.
    """

    _material: bytearray

    @classmethod
    def generate(cls) -> MasterKey:
        """Return a fresh, cryptographically-random key."""

        return cls(_material=bytearray(secrets.token_bytes(KEY_BYTES)))

    @classmethod
    def from_bytes(cls, value: bytes) -> MasterKey:
        if len(value) != KEY_BYTES:
            raise ValueError(f"MasterKey requires exactly {KEY_BYTES} bytes; got {len(value)}.")
        return cls(_material=bytearray(value))

    @property
    def is_closed(self) -> bool:
        return len(self._material) == 0

    def view(self) -> bytes:
        """Return the key bytes. Raises if the key has been closed."""

        if self.is_closed:
            raise RuntimeError("MasterKey is closed.")
        return bytes(self._material)

    def close(self) -> None:
        """Zero the key material in-place."""

        if not self._material:
            return
        # ctypes memset on a Python bytearray buffer is the closest we
        # can portably get to zeroing the bytes in place. Best-effort.
        try:
            length = len(self._material)
            buf = (ctypes.c_byte * length).from_buffer(self._material)
            ctypes.memset(ctypes.addressof(buf), 0, length)
            del buf  # drop the memoryview before the bytearray resizes
        except (TypeError, ValueError):
            # Fallback: overwrite via slice assignment.
            for i in range(len(self._material)):
                self._material[i] = 0
        try:
            self._material.clear()
        except BufferError:
            # A lingering view (e.g. an unfinalized ctypes buffer) means
            # we can't resize. The bytes are already zeroed; reassign.
            self._material = bytearray()

    def __enter__(self) -> MasterKey:
        return self

    def __exit__(self, *_excinfo: object) -> None:
        self.close()


def encrypt_blob(key: MasterKey, plaintext: bytes, *, associated_data: bytes = b"") -> bytes:
    """Encrypt ``plaintext`` under ``key``.

    Returns ``nonce || ciphertext || tag`` (the AES-GCM tag is appended
    by the library to the ciphertext). The associated data — typically
    a stable per-entry context string (e.g. ``f"{host}:{name}"``) — is
    authenticated but NOT encrypted, so swapping ciphertext between
    entries fails the AEAD check.
    """

    nonce = secrets.token_bytes(NONCE_BYTES)
    aead = AESGCM(key.view())
    sealed: bytes = aead.encrypt(nonce, plaintext, associated_data or None)
    return nonce + sealed


def decrypt_blob(key: MasterKey, blob: bytes, *, associated_data: bytes = b"") -> bytes:
    """Decrypt ``blob`` produced by :func:`encrypt_blob`.

    Raises :class:`CryptoError` on tag failure (tampering, wrong key,
    wrong associated_data). The exception message intentionally does
    NOT echo back any of the ciphertext.
    """

    if len(blob) <= NONCE_BYTES + 16:  # nonce + (tag is appended, min 16 bytes)
        raise CryptoError("ciphertext too short to be a valid AEAD blob.")
    nonce = blob[:NONCE_BYTES]
    body = blob[NONCE_BYTES:]
    aead = AESGCM(key.view())
    try:
        result: bytes = aead.decrypt(nonce, body, associated_data or None)
    except InvalidTag as exc:
        raise CryptoError("vault entry failed AEAD tag verification.") from exc
    return result


def random_salt(byte_count: int = 16) -> bytes:
    """Return a cryptographically-random salt suitable for PBKDF2.

    Wrapped here so callers don't import :mod:`os` directly and the
    test suite can monkey-patch one function.
    """

    if byte_count < 16:
        raise ValueError("salt must be at least 16 bytes")
    return os.urandom(byte_count)


__all__ = [
    "CryptoError",
    "KEY_BYTES",
    "NONCE_BYTES",
    "MasterKey",
    "decrypt_blob",
    "encrypt_blob",
    "random_salt",
]

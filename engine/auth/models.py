"""Value objects for the auth vault (, ADR-0043).

:class:`VaultEntry` holds the encrypted material — the storage state and
the timing metadata. :class:`VaultMetadata` is the redacted view returned
by :meth:`engine.auth.vault.Vault.list`: it MUST NOT carry the storage
state, so callers that listed the vault can never accidentally leak a
session payload to a log line.

The expiry rule is hard: once :attr:`VaultEntry.expires_at` is in the
past, the vault refuses to decrypt the entry — the run aborts with
``E-AUTH-002`` and the operator re-runs ``sentinel auth login``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: Soft cap on the storage_state JSON size we'll encrypt. Playwright
#: sessions usually weigh well under 100 KB; >1 MB strongly suggests an
#: accidental capture of full-page state and the vault refuses.
MAX_STORAGE_STATE_BYTES = 1_048_576  # 1 MiB

#: Default session lifetime (24 h). The CLI accepts ``--ttl`` to override
#: per-capture, but the on-disk default keeps a stale session from sitting
#: around indefinitely.
DEFAULT_TTL_HOURS = 24


def _utc_now() -> datetime:
    return datetime.now(UTC)


class VaultMetadata(BaseModel):
    """Public, redacted view of a vault entry.

    Returned by :meth:`engine.auth.vault.Vault.list`. The storage_state
    JSON is intentionally absent — the only way to read it is via
    :meth:`engine.auth.vault.Vault.get`, which enforces the host match.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=128)
    host: str = Field(min_length=1, max_length=512)
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime | None = None
    cookies_count: int = Field(ge=0)
    local_storage_keys: int = Field(ge=0)

    @property
    def expired(self) -> bool:
        return _utc_now() >= self.expires_at

    @property
    def age_seconds(self) -> float:
        return (_utc_now() - self.created_at).total_seconds()


class VaultEntry(BaseModel):
    """One stored Playwright session.

    Construct from :meth:`from_storage_state` so the cookie / local-storage
    counts are derived from the actual payload — callers don't get to
    fabricate metadata.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=128)
    host: str = Field(min_length=1, max_length=512)
    storage_state_json: str = Field(min_length=2, max_length=MAX_STORAGE_STATE_BYTES)
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime | None = None
    cookies_count: int = Field(ge=0)
    local_storage_keys: int = Field(ge=0)
    captured_by: str = Field(default="cli", min_length=1, max_length=64)

    @field_validator("storage_state_json")
    @classmethod
    def _looks_like_json_object(cls, value: str) -> str:
        if not value.startswith("{") or not value.endswith("}"):
            raise ValueError("storage_state_json must be a JSON object string.")
        return value

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_storage_state(
        cls,
        *,
        name: str,
        host: str,
        storage_state: dict[str, Any],
        storage_state_json: str,
        created_at: datetime | None = None,
        expires_at: datetime | None = None,
        ttl_hours: int = DEFAULT_TTL_HOURS,
        captured_by: str = "cli",
    ) -> VaultEntry:
        cookies = storage_state.get("cookies") or []
        origins = storage_state.get("origins") or []
        local_storage_keys = sum(len(origin.get("localStorage") or []) for origin in origins)
        ts_created = created_at or _utc_now()
        ts_expires = expires_at or ts_created.replace(microsecond=0) + _ttl_to_delta(ttl_hours)
        if ts_expires <= ts_created:
            raise ValueError("expires_at must be after created_at")
        return cls(
            name=name,
            host=host,
            storage_state_json=storage_state_json,
            created_at=ts_created,
            expires_at=ts_expires,
            last_used_at=None,
            cookies_count=len(cookies),
            local_storage_keys=local_storage_keys,
            captured_by=captured_by,
        )

    def to_metadata(self) -> VaultMetadata:
        """Drop the secret payload, return a public view."""

        return VaultMetadata(
            name=self.name,
            host=self.host,
            created_at=self.created_at,
            expires_at=self.expires_at,
            last_used_at=self.last_used_at,
            cookies_count=self.cookies_count,
            local_storage_keys=self.local_storage_keys,
        )

    @property
    def expired(self) -> bool:
        return _utc_now() >= self.expires_at


def _ttl_to_delta(ttl_hours: int) -> datetime.timedelta:  # type: ignore[name-defined]
    from datetime import timedelta

    if ttl_hours <= 0:
        raise ValueError("ttl_hours must be positive")
    if ttl_hours > 24 * 365:
        raise ValueError("ttl_hours must be at most 1 year")
    return timedelta(hours=ttl_hours)


__all__ = [
    "DEFAULT_TTL_HOURS",
    "MAX_STORAGE_STATE_BYTES",
    "VaultEntry",
    "VaultMetadata",
]

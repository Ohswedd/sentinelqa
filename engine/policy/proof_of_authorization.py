"""Proof-of-authorization document schema + verifier (CLAUDE.md §6, §26).

Destructive mode against any host requires a `proof_of_authorization` file
that names the host, the authorized actor, the scope, and an expiry. The
MVP accepts an unsigned YAML doc; a future ADR may extend the format to
require a detached signature.

Schema (YAML):

```yaml
schema_version: "1"
host: staging.example.com
actor: alice@example.com
scope:
  - functional
  - api
  - security
issued_at: 2026-05-27T00:00:00Z
expires_at: 2026-08-27T00:00:00Z
notes: |
  Authorized by Acme Inc. infosec ticket SEC-1234.
```
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator

from engine.domain.base import SentinelModel
from engine.errors.base import (
    ConfigFileNotFoundError,
    ConfigSchemaError,
    DestructiveWithoutProofError,
)


class ProofOfAuthorization(SentinelModel):
    """Loaded proof-of-authorization document."""

    schema_version: str = Field(default="1")
    host: str = Field(min_length=1, max_length=512)
    actor: str = Field(min_length=1, max_length=200)
    scope: tuple[str, ...] = Field(min_length=1)
    issued_at: datetime
    expires_at: datetime
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("issued_at", "expires_at")
    @classmethod
    def _require_tz(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Proof-of-authorization datetimes must be timezone-aware.")
        return value.astimezone(UTC)

    def covers(self, *, host: str, capability: str, now: datetime | None = None) -> bool:
        """Return ``True`` if this doc authorizes ``capability`` on ``host`` now."""

        if host.lower() != self.host.lower():
            return False
        if capability not in self.scope:
            return False
        now_utc = (now or datetime.now(UTC)).astimezone(UTC)
        return self.issued_at <= now_utc <= self.expires_at


def load_proof(path: Path) -> ProofOfAuthorization:
    """Read and validate a proof-of-authorization YAML file."""

    if not path.exists() or not path.is_file():
        raise ConfigFileNotFoundError(path=str(path))
    try:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigSchemaError(detail=f"proof-of-authorization YAML invalid: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigSchemaError(detail="proof-of-authorization root must be a mapping.")
    try:
        return ProofOfAuthorization.model_validate(raw)
    except Exception as exc:  # pragma: no cover — exercised via ConfigSchemaError tests
        raise ConfigSchemaError(detail=f"proof-of-authorization failed validation: {exc}") from exc


def require_proof(
    proof_path: Path | None,
    *,
    host: str,
    capability: str = "destructive",
) -> ProofOfAuthorization:
    """Load and verify a proof for ``host``/``capability``, or raise."""

    if proof_path is None:
        raise DestructiveWithoutProofError(
            host=host,
            technical_context={"host": host, "capability": capability},
        )
    proof = load_proof(proof_path)
    if not proof.covers(host=host, capability=capability):
        raise DestructiveWithoutProofError(
            host=host,
            technical_context={
                "host": host,
                "capability": capability,
                "proof_host": proof.host,
                "proof_expires_at": proof.expires_at.isoformat(),
            },
        )
    return proof


__all__ = ["ProofOfAuthorization", "load_proof", "require_proof"]

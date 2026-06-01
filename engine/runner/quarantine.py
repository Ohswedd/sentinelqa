"""Test quarantine list.

The quarantine list is a strict YAML file at
``tests/sentinel/.quarantine.yaml`` (configurable via
``runner.quarantine.path``). Each entry names a test that runs but
whose result does NOT block the quality gate — instead, an ``info``
finding is emitted.

Schema (per entry):.. code-block:: yaml

 - test_id: "auth/login.spec.ts > sign in with bad password"
 reason: "Flaky on Safari while we land the polling fix"
 expires_at: "2026-06-10"
 issue_url: "https://github.com/Ohswedd/sentinelqa/issues/42"

Rules:

- Every field is required. Unknown fields are rejected.
- ``expires_at`` MUST be ≤ today + ``max_age_days`` (default 14). The
 loader refuses to load expired entries — this is intentional: a stale
 quarantine is a hidden quality regression.
- ``issue_url`` MUST be ``http(s)://`` so the quarantine cannot become a
 silent forever-skip.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


class QuarantineError(ValueError):
    """Raised when a quarantine list fails strict validation."""


class QuarantineExpiredError(QuarantineError):
    """Raised when one or more quarantine entries are past ``expires_at``."""

    def __init__(self, message: str, *, expired: tuple[str, ...]) -> None:
        super().__init__(message)
        self.expired = expired


class QuarantineEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    test_id: str = Field(min_length=1, max_length=512)
    reason: str = Field(min_length=8, max_length=2_048)
    expires_at: date
    issue_url: str = Field(min_length=1, max_length=2_048)

    @field_validator("issue_url")
    @classmethod
    def _validate_issue_url(cls, value: str) -> str:
        if not _URL_RE.match(value):
            raise ValueError(
                "issue_url must start with http:// or https:// "
                "so reviewers can follow it from the quarantine list."
            )
        return value


@dataclass(frozen=True)
class Quarantine:
    """Loaded quarantine list, indexed by ``test_id`` for O(1) lookups."""

    entries: tuple[QuarantineEntry, ...]
    source_path: Path | None

    def __contains__(self, test_id: object) -> bool:  # pragma: no cover — trivial
        if not isinstance(test_id, str):
            return False
        return any(e.test_id == test_id for e in self.entries)

    def lookup(self, test_id: str) -> QuarantineEntry | None:
        for entry in self.entries:
            if entry.test_id == test_id:
                return entry
        return None

    def test_ids(self) -> tuple[str, ...]:
        return tuple(e.test_id for e in self.entries)

    @classmethod
    def empty(cls) -> Quarantine:
        return cls(entries=(), source_path=None)

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        max_age_days: int = 14,
        today: date | None = None,
    ) -> Quarantine:
        """Load and validate the quarantine list at ``path``.

        A missing file is treated as an empty quarantine — quarantines are
        opt-in. A malformed file raises :class:`QuarantineError`. Any expired
        entry raises :class:`QuarantineExpiredError` (the caller cannot
        silently demote it; the operator must remove or refresh it).
        """

        if not path.exists():
            return cls(entries=(), source_path=None)
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise QuarantineError(f"{path}: invalid YAML: {exc}") from exc
        if raw is None:
            return cls(entries=(), source_path=path)
        if not isinstance(raw, list):
            raise QuarantineError(
                f"{path}: top-level YAML must be a list of entries (got {type(raw).__name__})."
            )

        cutoff = (today or date.today()) + timedelta(days=max_age_days)
        entries: list[QuarantineEntry] = []
        expired: list[str] = []
        for index, item in enumerate(raw):
            if not isinstance(item, dict):
                raise QuarantineError(
                    f"{path}[{index}]: each entry must be a mapping "
                    f"(got {type(item).__name__})."
                )
            try:
                entry = QuarantineEntry.model_validate(item)
            except ValidationError as exc:
                raise QuarantineError(
                    f"{path}[{index}]: {exc.error_count()} errors: {exc}"
                ) from exc
            if entry.expires_at > cutoff:
                raise QuarantineError(
                    f"{path}: entry for {entry.test_id!r} expires {entry.expires_at} which is "
                    f"more than {max_age_days} days from now (max allowed: {cutoff}). "
                    "Shorten the quarantine window."
                )
            if entry.expires_at < (today or date.today()):
                expired.append(entry.test_id)
            entries.append(entry)
        if expired:
            raise QuarantineExpiredError(
                f"{path}: {len(expired)} quarantine entries are past expiration: "
                f"{', '.join(expired)}. Remove or refresh them before running.",
                expired=tuple(expired),
            )
        return cls(entries=tuple(entries), source_path=path)


def quarantine_to_findings(
    quarantine: Quarantine,
    *,
    module: str,
    run_id: str,
) -> tuple[dict[str, Any], ...]:
    """Translate quarantine entries into our product spec-compliant ``info`` findings.

    Returned as plain dicts (NOT Finding instances) because the
    score module will lift these into typed Findings once it owns the
    severity gates. For now they are stable evidence trails.
    """

    out: list[dict[str, Any]] = []
    for entry in quarantine.entries:
        out.append(
            {
                "module": module,
                "category": "test-quarantine",
                "severity": "info",
                "title": f"Test quarantined: {entry.test_id}",
                "description": entry.reason,
                "evidence": {
                    "test_id": entry.test_id,
                    "expires_at": entry.expires_at.isoformat(),
                    "issue_url": entry.issue_url,
                },
                "run_id": run_id,
            }
        )
    return tuple(out)


__all__ = [
    "Quarantine",
    "QuarantineEntry",
    "QuarantineError",
    "QuarantineExpiredError",
    "quarantine_to_findings",
]

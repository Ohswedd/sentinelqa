"""Target entity (the documentation / §18.1).

Carries the safety-relevant fields that the policy layer consumes:
``base_url``, ``allowed_hosts``, ``mode``, and an optional pointer to a
proof-of-authorization document.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Literal

from pydantic import AnyUrl, Field, field_validator

from engine.domain.base import SentinelModel
from engine.domain.schema import CONFIG_SCHEMA_VERSION

Mode = Literal["safe", "authorized_destructive"]


class Target(SentinelModel):
    """The application endpoint SentinelQA is allowed to interact with."""

    SCHEMA_VERSION: ClassVar[str] = CONFIG_SCHEMA_VERSION

    base_url: AnyUrl
    allowed_hosts: frozenset[str] = Field(default_factory=frozenset)
    mode: Mode = "safe"
    proof_of_authorization: Path | None = None
    schema_version: str = Field(default=CONFIG_SCHEMA_VERSION)

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def _coerce_hosts(cls, value: object) -> frozenset[str]:
        """Accept list/tuple/set inputs from YAML and freeze."""

        if value is None:
            return frozenset()
        if isinstance(value, str):
            return frozenset({value})
        if isinstance(value, frozenset):
            return value
        if isinstance(value, (list, tuple, set)):  # noqa: UP038
            return frozenset(str(h) for h in value)
        raise ValueError(f"allowed_hosts must be a string or list of strings; got {type(value)!r}.")

    @field_validator("allowed_hosts")
    @classmethod
    def _reject_wildcards(cls, value: frozenset[str]) -> frozenset[str]:
        """our engineering rules: wildcard allowlists invite unsafe scans."""

        for host in value:
            if "*" in host or "?" in host:
                raise ValueError(
                    f"Wildcard host {host!r} is not allowed; "
                    f"list each authorized host explicitly."
                )
        return value


__all__ = ["Target", "Mode"]

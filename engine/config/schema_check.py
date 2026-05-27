"""Non-raising config validation for ``sentinel doctor`` (Phase 02).

The CLI ``doctor`` command wants to report every issue in one pass rather
than aborting on the first failure. This module wraps Pydantic so a caller
can collect a list of issues without intercepting exceptions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from engine.config.schema import RootConfig


@dataclass(frozen=True, slots=True)
class ConfigCheckError:
    """One issue found by :func:`validate_config_dict`."""

    location: tuple[str | int, ...]
    message: str
    type: str

    def render(self) -> str:
        loc = "/".join(str(p) for p in self.location) or "<root>"
        return f"{loc}: {self.message} ({self.type})"


def validate_config_dict(data: Any) -> list[ConfigCheckError]:
    """Validate ``data`` without raising.

    Returns a list of issues — empty means the config is valid.
    """

    issues: list[ConfigCheckError] = []
    if not isinstance(data, dict):
        return [
            ConfigCheckError(
                location=(),
                message=f"config root must be a mapping; got {type(data).__name__}",
                type="root_not_mapping",
            )
        ]
    try:
        RootConfig.model_validate(data)
    except ValidationError as exc:
        for err in exc.errors():
            issues.append(
                ConfigCheckError(
                    location=tuple(err["loc"]),
                    message=str(err["msg"]),
                    type=str(err["type"]),
                )
            )
    return issues


__all__ = ["validate_config_dict", "ConfigCheckError"]

"""YAML loader for ``sentinel.config.yaml`` (PRD §17, CLAUDE.md §12).

Responsibilities:

- Read YAML with :func:`yaml.safe_load` (no arbitrary tag execution).
- Interpolate ``${VAR}`` / ``${VAR:-default}`` references against the
  process environment in non-secret string values only. Keys are NEVER
  interpolated; secret fields refuse inline values.
- Reject unknown keys (Pydantic ``extra="forbid"`` already does this at the
  model level; we surface a clear message at the CLI boundary).
- Map every failure mode to a typed :class:`engine.errors.ConfigError`
  subclass with a stable code from `engine/errors/codes.py`.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from engine.config.schema import RootConfig
from engine.errors.base import (
    ConfigFileNotFoundError,
    ConfigSchemaError,
    ConfigSecretInlineError,
)

# `${VAR}` or `${VAR:-default}` — pattern stays anchored inside an existing
# string so we never run a substitution against a non-string scalar.
_ENV_PATTERN = re.compile(r"\$\{(?P<name>[A-Z_][A-Z0-9_]*)(?::-(?P<default>[^}]*))?\}")

# Keys that MUST come from env, not be inlined.
_FORBIDDEN_INLINE_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "client_secret",
        "private_key",
    }
)


def _interpolate(value: str) -> str:
    """Replace ``${VAR}`` references in a single string."""

    def _replace(match: re.Match[str]) -> str:
        name = match.group("name")
        default = match.group("default")
        env = os.environ.get(name)
        if env is not None:
            return env
        if default is not None:
            return default
        raise ConfigSchemaError(
            detail=f"environment variable ${{{name}}} is not set and no default provided",
            technical_context={"env_var": name},
        )

    return _ENV_PATTERN.sub(_replace, value)


def _walk(node: Any, *, key_path: tuple[str, ...] = ()) -> Any:
    """Recursively interpolate strings and enforce the no-inline-secret rule."""

    if isinstance(node, str):
        return _interpolate(node)
    if isinstance(node, list):
        return [_walk(item, key_path=key_path) for item in node]
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for key, sub in node.items():
            key_str = str(key)
            new_path = (*key_path, key_str)
            if key_str in _FORBIDDEN_INLINE_KEYS and not isinstance(sub, (dict, list)):  # noqa: UP038
                raise ConfigSecretInlineError(
                    field=".".join(new_path),
                    technical_context={"field": ".".join(new_path)},
                )
            out[key_str] = _walk(sub, key_path=new_path)
        return out
    return node


def load_config(path: Path) -> RootConfig:
    """Load and validate ``sentinel.config.yaml``.

    Raises:

    - :class:`ConfigFileNotFoundError` when ``path`` does not exist.
    - :class:`ConfigSchemaError` for YAML syntax errors, unknown keys, or
      Pydantic validation failures.
    - :class:`ConfigSecretInlineError` when a secret-named key carries an
      inline literal (use ``*_env`` instead).
    """

    if not path.exists() or not path.is_file():
        raise ConfigFileNotFoundError(
            path=str(path),
            technical_context={"path": str(path)},
        )

    raw_text = path.read_text(encoding="utf-8")
    try:
        raw: Any = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise ConfigSchemaError(
            detail=f"YAML syntax error in {path}: {exc}",
            technical_context={"path": str(path)},
        ) from exc

    if raw is None:
        raise ConfigSchemaError(
            detail=f"Config file {path} is empty.",
            technical_context={"path": str(path)},
        )
    if not isinstance(raw, dict):
        raise ConfigSchemaError(
            detail=f"Config root must be a mapping; got {type(raw).__name__}.",
            technical_context={"path": str(path)},
        )

    interpolated = _walk(raw)
    try:
        return RootConfig.model_validate(interpolated)
    except ValidationError as exc:
        raise ConfigSchemaError(
            detail=str(exc),
            technical_context={"path": str(path), "errors": exc.errors()},
        ) from exc


def dump_config(config: RootConfig) -> str:
    """Render ``config`` as a YAML string.

    Used by ``sentinel init`` (Phase 02) to write a default config file.
    The output is deterministic (sorted keys, single-quote strings).
    """

    return yaml.safe_dump(
        config.to_dict(),
        sort_keys=True,
        default_flow_style=False,
        allow_unicode=True,
    )


__all__ = ["load_config", "dump_config"]

"""Tests confirming the loader refuses inline secrets (CLAUDE.md §33)."""

from __future__ import annotations

from pathlib import Path

import pytest
from engine.config.loader import load_config
from engine.errors.base import ConfigSecretInlineError

_BASE = (
    "project:\n  name: demo\n"
    "target:\n  base_url: http://localhost:3000\n  allowed_hosts:\n    - localhost\n"
)


@pytest.mark.parametrize(
    "key",
    ["password", "secret", "token", "access_token", "api_key", "client_secret"],
)
def test_inline_secret_keys_rejected(tmp_path: Path, key: str) -> None:
    path = tmp_path / "sentinel.config.yaml"
    path.write_text(_BASE + f"auth:\n  {key}: inlined-secret\n")
    with pytest.raises(ConfigSecretInlineError):
        load_config(path)


def test_env_alias_keys_allowed(tmp_path: Path) -> None:
    path = tmp_path / "sentinel.config.yaml"
    path.write_text(
        _BASE
        + "auth:\n  strategy: test_user\n  username_env: USER_EMAIL\n  password_env: USER_PASS\n"
    )
    cfg = load_config(path)
    assert cfg.auth.password_env == "USER_PASS"

"""Tests for engine.config.loader.load_config."""

from __future__ import annotations

import os
from collections.abc import Callable, Generator
from pathlib import Path

import pytest
from engine.config.loader import load_config
from engine.errors.base import (
    ConfigFileNotFoundError,
    ConfigSchemaError,
    ConfigSecretInlineError,
)

WriteYaml = Callable[[str], Path]


@pytest.fixture
def write_yaml(tmp_path: Path) -> Generator[WriteYaml, None, None]:
    def _write(text: str) -> Path:
        p = tmp_path / "sentinel.config.yaml"
        p.write_text(text)
        return p

    yield _write


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigFileNotFoundError):
        load_config(tmp_path / "nope.yaml")


def test_invalid_yaml(write_yaml: WriteYaml) -> None:
    path = write_yaml(":\n  invalid:\n :\nbad: -\n  -")
    with pytest.raises(ConfigSchemaError):
        load_config(path)


def test_empty_yaml(write_yaml: WriteYaml) -> None:
    path = write_yaml("")
    with pytest.raises(ConfigSchemaError):
        load_config(path)


def test_unknown_root_key(write_yaml: WriteYaml) -> None:
    path = write_yaml(
        "project:\n  name: demo\ntarget:\n  base_url: http://localhost:3000\nevil: 1\n"
    )
    with pytest.raises(ConfigSchemaError):
        load_config(path)


_CONFIG_TMPL = (
    "project:\n  name: demo\n"
    "target:\n  base_url: {base_url}\n  allowed_hosts:\n    - localhost\n"
    "{extra}"
)


def test_env_interpolation(write_yaml: WriteYaml) -> None:
    os.environ["SENTINEL_TEST_BASE"] = "http://localhost:4242"
    try:
        path = write_yaml(_CONFIG_TMPL.format(base_url="${SENTINEL_TEST_BASE}", extra=""))
        cfg = load_config(path)
        assert str(cfg.target.base_url) == "http://localhost:4242/"
    finally:
        del os.environ["SENTINEL_TEST_BASE"]


def test_env_default_interpolation(write_yaml: WriteYaml) -> None:
    os.environ.pop("SENTINEL_TEST_UNSET", None)
    path = write_yaml(
        _CONFIG_TMPL.format(
            base_url="${SENTINEL_TEST_UNSET:-http://localhost:5000}",
            extra="",
        )
    )
    cfg = load_config(path)
    assert "5000" in str(cfg.target.base_url)


def test_missing_env_without_default_errors(write_yaml: WriteYaml) -> None:
    os.environ.pop("SENTINEL_TEST_UNSET", None)
    path = write_yaml(_CONFIG_TMPL.format(base_url="${SENTINEL_TEST_UNSET}", extra=""))
    with pytest.raises(ConfigSchemaError):
        load_config(path)


def test_inline_password_rejected(write_yaml: WriteYaml) -> None:
    path = write_yaml(
        _CONFIG_TMPL.format(
            base_url="http://localhost:3000",
            extra="auth:\n  password: hunter2\n",
        )
    )
    with pytest.raises(ConfigSecretInlineError):
        load_config(path)


def test_example_yaml_round_trips(tmp_path: Path) -> None:
    example = Path("sentinel.config.yaml.example")
    cfg = load_config(example)
    # Round-trip: dump → load should yield an equivalent config.
    rendered = tmp_path / "round.yaml"
    from engine.config.loader import dump_config

    rendered.write_text(dump_config(cfg))
    cfg2 = load_config(rendered)
    assert cfg2.project.name == cfg.project.name
    assert str(cfg2.target.base_url) == str(cfg.target.base_url)

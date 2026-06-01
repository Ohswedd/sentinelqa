# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for the ``sentinel init`` interactive wizard."""

from __future__ import annotations

import io
from pathlib import Path

import yaml
from engine.config.loader import dump_config

from sentinel_cli import init_detect, init_wizard


def _scripted_text(answers: list[str]):
    """Return a prompt_text replacement that pops one scripted answer per call."""

    queue = list(answers)

    def prompt(_console, _label, *, default):
        if not queue:
            return default
        return queue.pop(0)

    return prompt


def _scripted_bool(answers: list[bool]):
    queue = list(answers)

    def prompt(_console, _label, *, default):
        if not queue:
            return default
        return queue.pop(0)

    return prompt


def test_run_wizard_with_defaults_only(tmp_path: Path) -> None:
    """Pressing Enter five times must yield a working config."""

    detection = init_detect.Detection(
        framework="nextjs",
        package_manager="pnpm",
        has_playwright=True,
        project_name="my-app",
        base_url=None,
    )
    answers = init_wizard.run_wizard(
        detection=detection,
        prompt_text=_scripted_text([]),  # always fall back to defaults
        prompt_bool=_scripted_bool([]),
    )
    assert answers.project_name == "my-app"
    assert answers.framework == "nextjs"
    assert answers.package_manager == "pnpm"
    assert answers.base_url == "http://localhost:3000"
    assert answers.auth_strategy == "none"
    # Default modules match the documented defaults.
    assert answers.modules.functional is True
    assert answers.modules.visual is False
    assert answers.modules.chaos is False


def test_run_wizard_accepts_explicit_choices(tmp_path: Path) -> None:
    """The user's typed answers override the defaults."""

    detection = init_detect.Detection(
        framework="unknown",
        package_manager="unknown",
        has_playwright=False,
        project_name=None,
        base_url=None,
    )
    text_answers = [
        "checkout-service",  # project name
        "http://127.0.0.1:8080",  # base url
        "test_user",  # auth strategy by name
    ]
    # Disable visual + chaos, enable everything else.
    bool_answers = [True, True, True, True, True, True, False, False]
    answers = init_wizard.run_wizard(
        detection=detection,
        prompt_text=_scripted_text(text_answers),
        prompt_bool=_scripted_bool(bool_answers),
    )
    assert answers.project_name == "checkout-service"
    assert answers.base_url == "http://127.0.0.1:8080"
    assert answers.auth_strategy == "test_user"


def test_choice_resolves_by_number() -> None:
    """The choice prompt accepts either the visible number or the name."""

    choices = (
        ("none", "no auth", "none"),
        ("test_user", "form login", "test_user"),
        ("api_key", "api key", "api_key"),
    )
    assert init_wizard._resolve_choice("2", choices, default="none") == "test_user"
    assert init_wizard._resolve_choice("api_key", choices, default="none") == "api_key"
    assert init_wizard._resolve_choice("garbage", choices, default="none") == "none"


def test_render_config_from_answers_produces_loadable_yaml(tmp_path: Path) -> None:
    """The YAML the wizard emits must round-trip through the loader."""

    detection = init_detect.Detection(
        framework="fastapi",
        package_manager="uv",
        has_playwright=False,
        project_name="api-svc",
        base_url=None,
    )
    answers = init_wizard.run_wizard(
        detection=detection,
        prompt_text=_scripted_text(["api-svc", "http://localhost:5000", "api_key"]),
        prompt_bool=_scripted_bool([]),
    )
    config_yaml = init_wizard.render_config_from_answers(
        project_root=tmp_path,
        answers=answers,
        dump_config=dump_config,
    )
    parsed = yaml.safe_load(config_yaml)
    assert parsed["project"]["name"] == "api-svc"
    assert parsed["project"]["framework"] == "fastapi"
    # Pydantic normalises trailing slashes on AnyUrl; either form is fine.
    assert parsed["target"]["base_url"].rstrip("/") == "http://localhost:5000"
    assert parsed["auth"]["strategy"] == "api_key"


def test_is_interactive_handles_non_tty_streams() -> None:
    """``is_interactive`` must return False on piped / null streams."""

    pipe_like = io.StringIO()
    assert init_wizard.is_interactive(pipe_like) is False

    class _NoIsatty:
        pass

    assert init_wizard.is_interactive(_NoIsatty()) is False


def test_is_interactive_returns_true_for_tty_stream() -> None:
    class _TtyLike:
        def isatty(self) -> bool:
            return True

    assert init_wizard.is_interactive(_TtyLike()) is True

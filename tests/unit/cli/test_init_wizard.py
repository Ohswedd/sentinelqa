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


def test_is_interactive_returns_false_when_isatty_raises() -> None:
    """OS-level failures from ``isatty`` must be treated as non-interactive."""

    class _Broken:
        def isatty(self) -> bool:
            raise OSError("closed handle")

    assert init_wizard.is_interactive(_Broken()) is False


def test_header_panel_when_no_hints_found() -> None:
    """The header panel handles a fresh project with no detection hits."""

    from rich.console import Console

    detection = init_detect.Detection(
        framework="unknown",
        package_manager="unknown",
        has_playwright=False,
        project_name=None,
        base_url=None,
    )
    panel = init_wizard._header_panel(detection)
    console = Console(record=True, width=80)
    console.print(panel)
    rendered = console.export_text()
    assert "no project hints" in rendered


def test_ask_text_uses_prompt(monkeypatch) -> None:
    """The default ``_ask_text`` helper routes through Rich's Prompt.ask."""

    from rich.console import Console
    from rich.prompt import Prompt

    monkeypatch.setattr(Prompt, "ask", lambda *_a, default, console: f"  {default}-stripped  ")
    out = init_wizard._ask_text(Console(), "Name", default="x")
    assert out == "x-stripped"


def test_run_wizard_falls_back_to_default_prompters(monkeypatch) -> None:
    """When ``prompt_text``/``prompt_bool`` are omitted, the defaults are used."""

    from rich.prompt import Confirm, Prompt

    monkeypatch.setattr(Prompt, "ask", lambda *_a, default, console: default)
    monkeypatch.setattr(Confirm, "ask", lambda *_a, default, console: default)
    detection = init_detect.Detection(
        framework="nextjs",
        package_manager="pnpm",
        has_playwright=True,
        project_name="auto",
        base_url=None,
    )
    answers = init_wizard.run_wizard(detection=detection)
    assert answers.project_name == "auto"
    assert answers.auth_strategy == "none"


def test_ask_bool_uses_confirm(monkeypatch) -> None:
    """The default ``_ask_bool`` helper routes through Rich's Confirm.ask."""

    from rich.console import Console
    from rich.prompt import Confirm

    captured: dict[str, object] = {}

    def fake_ask(label: object, *, default: bool, console: object) -> bool:
        captured["label"] = label
        captured["default"] = default
        return True

    monkeypatch.setattr(Confirm, "ask", fake_ask)
    out = init_wizard._ask_bool(Console(), "Enable foo?", default=False)
    assert out is True
    assert "Enable foo?" in str(captured["label"])
    assert captured["default"] is False

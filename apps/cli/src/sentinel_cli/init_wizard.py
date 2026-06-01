# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Interactive wizard for ``sentinel init``.

Drives a short Rich-styled Q&A that turns the detected project state into
a working ``sentinel.config.yaml``. The wizard is intentionally minimal —
five prompts max, every one with a sensible detected default — so a new
user can press Enter five times and end up with a config that audits
their app cleanly.

The wizard is pure UI: it builds an :class:`engine.config.schema.RootConfig`
in memory and hands it back to :func:`render_config`. It never writes to
disk; the caller owns IO.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from engine.config.schema import (
    AuthConfig,
    ModulesConfig,
    ProjectConfig,
    RootConfig,
    TargetConfig,
)
from engine.domain.project import Framework, PackageManager
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from sentinel_cli import init_detect

_AUTH_STRATEGIES: tuple[tuple[str, str, str], ...] = (
    ("none", "No login required (public app or unauthenticated audit)", "none"),
    ("test_user", "Form login with a test user (email + password)", "test_user"),
    ("api_key", "API key in Authorization header", "api_key"),
    ("oauth", "OAuth provider redirect flow", "oauth"),
    ("browser_session", "Reuse a saved browser session (sentinel auth login)", "browser_session"),
)

_MODULE_DEFAULTS: tuple[tuple[str, str, bool], ...] = (
    ("functional", "End-to-end functional flows", True),
    ("api", "API contract + negative cases", True),
    ("accessibility", "axe-core + keyboard / focus checks", True),
    ("performance", "Synthetic page / API budgets", True),
    ("security", "Headers, cookies, CORS, safe XSS / IDOR", True),
    ("llm_audit", "LLM-generated code smells", True),
    ("visual", "Pixel + perceptual diff vs. baseline", False),
    ("chaos", "Slow network / 500 mocking / session expiry", False),
)


@dataclass(frozen=True, slots=True)
class WizardAnswers:
    """The user's answers from the wizard, ready for :func:`render_config`."""

    project_name: str
    framework: Framework
    package_manager: PackageManager
    base_url: str
    auth_strategy: str
    modules: ModulesConfig


def is_interactive(stream: object = sys.stdin) -> bool:
    """Return True iff we can hold an interactive conversation on ``stream``."""

    isatty = getattr(stream, "isatty", None)
    if isatty is None:
        return False
    try:
        return bool(isatty())
    except (OSError, ValueError):
        return False


def run_wizard(
    *,
    detection: init_detect.Detection,
    console: Console | None = None,
    prompt_text: Callable[..., str] | None = None,
    prompt_bool: Callable[..., bool] | None = None,
) -> WizardAnswers:
    """Drive the prompts and return the user's answers.

    ``prompt_text`` and ``prompt_bool`` exist so tests can substitute a
    scripted prompter without touching the real terminal.
    """

    console = console or Console()
    if prompt_text is None:
        prompt_text = _ask_text
    if prompt_bool is None:
        prompt_bool = _ask_bool

    console.print(_header_panel(detection))

    project_name = prompt_text(
        console,
        "Project name",
        default=detection.project_name or Path.cwd().resolve().name or "sentinelqa-project",
    )

    base_url = prompt_text(
        console,
        "Base URL of the app you want to audit",
        default="http://localhost:3000",
    )

    auth_strategy = _ask_choice(
        console,
        prompt_text,
        "How does this app authenticate users?",
        choices=_AUTH_STRATEGIES,
        default="none",
    )

    modules = _ask_modules(console, prompt_bool)

    console.print()
    console.print(
        Panel.fit(
            "[bold green]Configuration ready.[/]\n"
            "Run [bold]sentinel doctor[/] to verify the environment, then\n"
            "[bold]sentinel audit[/] to perform your first audit.",
            border_style="green",
        )
    )

    return WizardAnswers(
        project_name=project_name,
        framework=detection.framework,
        package_manager=detection.package_manager,
        base_url=base_url,
        auth_strategy=auth_strategy,
        modules=modules,
    )


def render_config_from_answers(
    *,
    project_root: Path,
    answers: WizardAnswers,
    dump_config: Callable[..., str],
) -> str:
    """Compose the YAML for a wizard-driven init.

    Mirrors :func:`init_detect.render_config` but uses the answers
    captured by :func:`run_wizard`.
    """

    del project_root  # reserved for future per-project paths

    auth_strategy_literal = answers.auth_strategy  # validated by Pydantic below
    auth_block = AuthConfig(strategy=auth_strategy_literal)  # type: ignore[arg-type]

    config = RootConfig(
        project=ProjectConfig(
            name=answers.project_name,
            framework=answers.framework,
            package_manager=answers.package_manager,
        ),
        target=TargetConfig(
            base_url=answers.base_url,  # type: ignore[arg-type]
            allowed_hosts=("localhost", "127.0.0.1"),
        ),
        auth=auth_block,
        modules=answers.modules,
    )
    yaml_body = dump_config(config)
    header = (
        "# SentinelQA configuration — generated by `sentinel init`.\n"
        "# Edit `target.base_url` to point at your app and add additional\n"
        "# `allowed_hosts` only for hosts you own or are authorized to test.\n"
        "# Secrets must come from environment variables, never inline.\n"
    )
    return header + yaml_body


# --------------------------------------------------------------------------- #
# UI helpers
# --------------------------------------------------------------------------- #


def _header_panel(detection: init_detect.Detection) -> Panel:
    detected_lines: list[str] = []
    if detection.framework != "unknown":
        detected_lines.append(f"  framework         [bold]{detection.framework}[/]")
    if detection.package_manager != "unknown":
        detected_lines.append(f"  package manager   [bold]{detection.package_manager}[/]")
    if detection.has_playwright:
        detected_lines.append("  Playwright        [bold]found[/]")
    body = (
        "Welcome to [bold cyan]SentinelQA[/].\n"
        "This wizard asks five short questions and writes a working\n"
        "[italic]sentinel.config.yaml[/] for your project.\n\n"
        "[bold]Detected so far:[/]\n"
        + ("\n".join(detected_lines) if detected_lines else "  (no project hints found)")
    )
    return Panel.fit(body, border_style="cyan", title="sentinel init")


def _ask_text(console: Console, label: str, *, default: str) -> str:
    return Prompt.ask(f"[bold]{label}[/]", default=default, console=console).strip()


def _ask_bool(console: Console, label: str, *, default: bool) -> bool:
    return Confirm.ask(f"[bold]{label}[/]", default=default, console=console)


def _ask_choice(
    console: Console,
    prompt_text: Callable[..., str],
    label: str,
    *,
    choices: tuple[tuple[str, str, str], ...],
    default: str,
) -> str:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column(style="bold")
    table.add_column()
    for i, (key, desc, _value) in enumerate(choices, start=1):
        table.add_row(str(i), key, desc)
    console.print()
    console.print(f"[bold]{label}[/]")
    console.print(table)
    default_index = next(
        (str(i) for i, (k, *_rest) in enumerate(choices, start=1) if k == default),
        "1",
    )
    raw = prompt_text(console, "Pick one (number or name)", default=default_index)
    return _resolve_choice(raw, choices, default=default)


def _resolve_choice(
    raw: str,
    choices: tuple[tuple[str, str, str], ...],
    *,
    default: str,
) -> str:
    raw = raw.strip().lower()
    if raw.isdigit():
        idx = int(raw)
        if 1 <= idx <= len(choices):
            return choices[idx - 1][2]
        return default
    for key, _desc, value in choices:
        if raw == key.lower():
            return value
    return default


def _ask_modules(
    console: Console,
    prompt_bool: Callable[..., bool],
) -> ModulesConfig:
    console.print()
    console.print("[bold]Which audit modules should run by default?[/]")
    console.print("[dim]You can change these later in sentinel.config.yaml.[/]")
    enabled: dict[str, bool] = {}
    for key, desc, default in _MODULE_DEFAULTS:
        enabled[key] = prompt_bool(console, f"  {key:<14} — {desc}", default=default)
    return ModulesConfig(**enabled)


__all__ = [
    "WizardAnswers",
    "is_interactive",
    "render_config_from_answers",
    "run_wizard",
]

"""Phase 23 — the chaos module must not ship stealth / evasion knobs.

our engineering rules forbids stealth automation, bot-detection bypass,
fingerprint evasion, proxy rotation for evasion, rate-limit bypass,
etc. This guard pairs two complementary checks (same shape as
:mod:`tests.security.test_api_no_aggressive_flags`):

1. Every ``.py`` file under :mod:`modules.chaos` and the
   ``sentinel chaos`` CLI is grepped for compound forbidden literals
   (``stealth_mode``, ``bot_detection_bypass``, ``proxy_rotation``,
   etc.). Compound forms keep us from poisoning docstrings that
   explain *why* a knob is forbidden.

2. The Typer parameters of :func:`sentinel_cli.commands.chaos_cmd.run_chaos`
   are introspected to assert no CLI option name matches a forbidden
   flag pattern (``--stealth``, ``--bypass``, ``--undetectable``,
   ``--aggressive``, ``--ignore-robots``).
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

# Compound literals — searched verbatim. They are deliberately
# multi-token so prose like "no bypass exists" does not match.
_FORBIDDEN_LITERALS: tuple[str, ...] = (
    "stealth_mode",
    "stealth-mode",
    "undetectable_mode",
    "undetectable-mode",
    "bot_detection_bypass",
    "bot-detection-bypass",
    "captcha_bypass",
    "captcha-bypass",
    "fingerprint_spoof",
    "fingerprint-spoof",
    "proxy_rotation",
    "proxy-rotation",
    "ratelimit_bypass",
    "ratelimit-bypass",
    "rate_limit_bypass",
    "rate-limit-bypass",
    "evasion_mode",
    "evasion-mode",
    "antibot_mode",
    "antibot-mode",
)

_AUDIT_TARGETS: tuple[Path, ...] = (
    Path("modules/chaos"),
    Path("apps/cli/src/sentinel_cli/commands/chaos_cmd.py"),
)

_ALLOWED_PATHS: tuple[Path, ...] = (Path("tests/security/test_chaos_no_evasion_flags.py"),)


def _iter_audit_files() -> list[Path]:
    files: list[Path] = []
    for target in _AUDIT_TARGETS:
        if not target.exists():
            continue
        if target.is_file():
            files.append(target)
        else:
            files.extend(p for p in target.rglob("*.py") if "__pycache__" not in p.parts)
    return files


def _is_allowed(path: Path) -> bool:
    for allowed in _ALLOWED_PATHS:
        try:
            path.resolve().relative_to(allowed.resolve())
        except ValueError:
            continue
        return True
    return False


@pytest.mark.parametrize("literal", _FORBIDDEN_LITERALS)
def test_no_forbidden_literal_in_chaos_module(literal: str) -> None:
    for path in _iter_audit_files():
        if _is_allowed(path):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert literal not in text, (
            f"Forbidden literal {literal!r} found in {path}. our engineering rules "
            "forbids stealth / evasion paths in the chaos module."
        )


_FORBIDDEN_OPTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^--aggressive"),
    re.compile(r"^--bypass"),
    re.compile(r"^--stealth"),
    re.compile(r"^--undetectable"),
    re.compile(r"^--unbounded"),
    re.compile(r"^--no-rate-limit$"),
    re.compile(r"^--ignore-robots$"),
    re.compile(r"^--evade"),
)


def _all_option_names(module_path: str, function_name: str) -> list[str]:
    module = importlib.import_module(module_path)
    func = getattr(module, function_name)
    names: list[str] = []
    for default in func.__defaults__ or ():
        decls = getattr(default, "param_decls", None) or ()
        for decl in decls:
            names.append(str(decl))
    for value in getattr(func, "__annotations__", {}).values():
        meta = getattr(value, "__metadata__", ()) or ()
        for entry in meta:
            decls = getattr(entry, "param_decls", None) or ()
            for decl in decls:
                names.append(str(decl))
    return names


@pytest.mark.parametrize("pattern", _FORBIDDEN_OPTION_PATTERNS, ids=lambda r: r.pattern)
def test_chaos_cli_has_no_forbidden_flag(pattern: re.Pattern[str]) -> None:
    names = _all_option_names("sentinel_cli.commands.chaos_cmd", "run_chaos")
    for name in names:
        if pattern.match(name):
            raise AssertionError(
                f"Forbidden CLI option {name!r} matches {pattern.pattern!r}. "
                "our engineering rules forbids stealth / evasion / bypass flags."
            )


def test_chaos_module_off_by_default() -> None:
    """The module must remain off by default in ModulesConfig."""

    from engine.config.schema import ModulesConfig

    assert ModulesConfig().chaos is False


def test_chaos_config_block_has_no_forbidden_field() -> None:
    """No field name in ChaosConfig may match a forbidden compound literal."""

    from engine.config.schema import ChaosConfig

    forbidden_substrings = {
        "stealth",
        "bypass",
        "evasion",
        "undetect",
        "fingerprint",
        "captcha",
        "antibot",
    }
    for field_name in ChaosConfig.model_fields:
        lowered = field_name.lower()
        for token in forbidden_substrings:
            assert (
                token not in lowered
            ), f"ChaosConfig.{field_name} contains forbidden substring {token!r}."

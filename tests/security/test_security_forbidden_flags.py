"""Phase 13.11 — the security CLI must not accept evasion / bypass flags.

`tests/security/test_no_stealth_flags.py` greps the codebase for the
forbidden stealth-flag literals. This file is the targeted check for
``apps/cli/src/sentinel_cli/commands/security_cmd.py``: it imports the
Typer command, walks its parameters, and asserts none match the
forbidden-flag patterns (CLAUDE §6).
"""

from __future__ import annotations

import importlib
import re

import pytest

_FORBIDDEN_OPTION_PATTERNS = (
    re.compile(r"^--stealth$"),
    re.compile(r"^--evade$"),
    re.compile(r"^--evasion$"),
    re.compile(r"^--bypass-"),
    re.compile(r"^--no-rate-limit$"),
    re.compile(r"^--ignore-robots$"),
    re.compile(r"^--undetectable$"),
    re.compile(r"^--rotate-proxies$"),
    re.compile(r"^--spoof-fingerprint$"),
)


def _all_option_names() -> list[str]:
    # We import the function and inspect its defaults at runtime; Typer's
    # OptionInfo carries the option spelling we want to audit.
    module = importlib.import_module("sentinel_cli.commands.security_cmd")
    func = module.run_security
    names: list[str] = []
    for default in func.__defaults__ or ():
        # Typer stores the user-visible option strings on `param_decls`.
        decls = getattr(default, "param_decls", None) or ()
        for decl in decls:
            names.append(str(decl))
    # Annotations can also wrap the OptionInfo (`Annotated[T, Option(...)]`).
    for value in getattr(func, "__annotations__", {}).values():
        meta = getattr(value, "__metadata__", ()) or ()
        for entry in meta:
            decls = getattr(entry, "param_decls", None) or ()
            for decl in decls:
                names.append(str(decl))
    return names


@pytest.mark.parametrize("pattern", _FORBIDDEN_OPTION_PATTERNS, ids=lambda r: r.pattern)
def test_security_cli_has_no_forbidden_flags(pattern: re.Pattern[str]) -> None:
    names = _all_option_names()
    for name in names:
        if pattern.match(name):
            raise AssertionError(
                f"Forbidden CLI option {name!r} matches {pattern.pattern!r}. "
                "CLAUDE §6 forbids stealth/evasion flags anywhere in the product."
            )

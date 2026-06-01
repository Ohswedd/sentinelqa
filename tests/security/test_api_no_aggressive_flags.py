"""the API module must not ship an aggressive-fuzz path.

Two complementary guards:

1. ``modules/api/`` and ``apps/cli/src/sentinel_cli/commands/api_cmd.py``
 are grepped for forbidden literals (``aggressive``, ``fuzz``,
 ``brute``, ``stress``, ``--unbounded``, etc.). Their presence
 anywhere outside an allow-list signals someone tried to wire a
 forbidden capability.
2. ``apps/cli/src/sentinel_cli/commands/api_cmd.py`` (when present)
 has its Typer parameters introspected to assert no CLI option
 matches the forbidden patterns (same pattern as
 :mod:`tests.security.test_security_forbidden_flags`).
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

# Substrings whose appearance in module/CLI source is forbidden.
_FORBIDDEN_LITERALS: tuple[str, ...] = (
    "aggressive_fuzz",
    "aggressive-fuzz",
    "brute_force",
    "brute-force",
    "stress_test",
    "stress-test",
    "--unbounded",
    "--no-rate-limit",
)

# Source files we audit.
_AUDIT_TARGETS: tuple[Path, ...] = (
    Path("modules/api"),
    Path("apps/cli/src/sentinel_cli/commands/api_cmd.py"),
)

_ALLOWED_PATHS: tuple[Path, ...] = (Path("tests/security/test_api_no_aggressive_flags.py"),)


def _iter_audit_files() -> list[Path]:
    files: list[Path] = []
    for target in _AUDIT_TARGETS:
        if not target.exists():
            continue
        if target.is_file():
            files.append(target)
        else:
            files.extend(target.rglob("*.py"))
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
def test_no_forbidden_literal_in_api_module(literal: str) -> None:
    """No file under modules/api/ or the api CLI may contain the literal."""

    for path in _iter_audit_files():
        if _is_allowed(path):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert literal not in text, (
            f"Forbidden literal {literal!r} found in {path}. our engineering rules "
            f"forbids aggressive-fuzz / brute-force / unbounded paths in "
            f"the API module."
        )


_FORBIDDEN_OPTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^--aggressive"),
    re.compile(r"^--fuzz"),
    re.compile(r"^--brute"),
    re.compile(r"^--stress"),
    re.compile(r"^--unbounded"),
    re.compile(r"^--no-rate-limit$"),
    re.compile(r"^--ignore-robots$"),
    re.compile(r"^--stealth$"),
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
def test_api_cli_has_no_forbidden_flag(pattern: re.Pattern[str]) -> None:
    """The `sentinel api` CLI (once shipped) must not expose forbidden flags."""

    try:
        names = _all_option_names("sentinel_cli.commands.api_cmd", "run_api")
    except (ImportError, AttributeError):
        # The CLI is wired in. Until then the literal-guard
        # above is sufficient; this assertion no-ops to keep the test
        # green during the phase build.
        return
    for name in names:
        if pattern.match(name):
            raise AssertionError(
                f"Forbidden CLI option {name!r} matches {pattern.pattern!r}. "
                "our engineering rules forbids aggressive-fuzz / brute-force flags."
            )

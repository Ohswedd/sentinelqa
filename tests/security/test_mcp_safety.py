"""Every URL-bearing MCP tool calls SafetyPolicy before any SDK call (ADR-0023).

This is the MCP analogue of ``tests/security/test_module_calls_policy.py``
— an AST-level guard so a future contributor cannot accidentally ship a
URL-accepting tool that skips :func:`sentinelqa_mcp.tools._safety.enforce_url`.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

TOOLS_DIR = (
    Path(__file__).resolve().parents[2]
    / "packages"
    / "mcp-server"
    / "src"
    / "sentinelqa_mcp"
    / "tools"
)

# Tools that explicitly take a `url` argument per their inputSchema.
URL_TOOLS = {
    "discover.py",
    "plan.py",
    "audit.py",
    "run_tests.py",
    "security_audit.py",
    "performance_audit.py",
    "accessibility_audit.py",
    "generate_tests.py",
    "verify_fix.py",
}


def _has_enforce_url_call(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "enforce_url":
                return True
            if isinstance(func, ast.Attribute) and func.attr == "enforce_url":
                return True
    return False


@pytest.mark.parametrize("module", sorted(URL_TOOLS))
def test_url_tool_calls_enforce_url(module: str) -> None:
    path = TOOLS_DIR / module
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assert _has_enforce_url_call(
        tree
    ), f"{module} accepts a URL but never calls enforce_url — ADR-0023 safety contract."


def test_safety_module_uses_safety_policy() -> None:
    """The shared safety helper itself must call SafetyPolicy.enforce."""

    path = TOOLS_DIR / "_safety.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    matches = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "enforce"
                and isinstance(func.value, ast.Call)
                and isinstance(func.value.func, ast.Name)
                and func.value.func.id == "SafetyPolicy"
            ):
                matches.append(node)
    assert matches, "_safety.enforce_url must call SafetyPolicy().enforce(...)."

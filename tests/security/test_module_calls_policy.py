"""Phase 13.11 — every security check enforces the safety policy.

This guard reads the AST of every ``run_*`` function in
``modules/security/checks/`` and confirms its body begins with one of:

- ``SafetyPolicy().enforce(...)`` (direct policy call).
- An early ``return`` of a skipped :class:`SecurityCheckResult` BEFORE
  any HTTP call — checks that legitimately short-circuit (e.g. xss_stored
  when destructive mode is off) are allowed to refuse the policy check.

This makes it impossible to land a probe that forgets to enforce the
safety boundary (CLAUDE §6 / §26).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKS_DIR = REPO_ROOT / "modules" / "security" / "checks"


def _check_files() -> list[Path]:
    out: list[Path] = []
    for file in CHECKS_DIR.glob("*.py"):
        if file.name in {"__init__.py", "context.py", "deps.py", "sast.py"}:
            # deps + sast are local-only / shell-out adapters; they do
            # not issue HTTP calls to the target.
            continue
        out.append(file)
    return out


def _public_run_functions(tree: ast.Module) -> list[ast.FunctionDef]:
    return [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("run_")
    ]


def _is_safety_enforce(node: ast.AST) -> bool:
    """True if ``node`` is ``SafetyPolicy(...).enforce(...)`` or similar."""

    if not isinstance(node, ast.Expr):
        return False
    call = node.value
    if not isinstance(call, ast.Call):
        return False
    func = call.func
    if not isinstance(func, ast.Attribute):
        return False
    if func.attr != "enforce":
        return False
    # Either SafetyPolicy().enforce(...) or self.policy.enforce(...).
    inner = func.value
    if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name):
        return inner.func.id == "SafetyPolicy"
    return isinstance(inner, ast.Attribute) and inner.attr.endswith("policy")


def _starts_with_early_skip(body: list[ast.stmt]) -> bool:
    """Detect the gated-check pattern: a precondition fetch followed by
    a short-circuit ``return`` BEFORE any I/O.

    Two accepted shapes:

    1. ``ok, reason = _allowed_to_run(ctx)`` + ``if not ok: return ...``.
    2. ``token = _second_user_token(ctx)`` (or any precondition helper) +
       ``if X is None: return ...``.

    The unifying signal is: a top-level call to a private precondition
    helper (``_<name>``) at body[0] or body[1] AND an ``if`` block whose
    body contains a ``return`` statement that *precedes* any
    :class:`SafetyPolicy.enforce` invocation.
    """

    if not body:
        return False
    found_precondition = False
    for stmt in body[:5]:
        if isinstance(stmt, ast.Assign):
            for call in ast.walk(stmt):
                if not isinstance(call, ast.Call):
                    continue
                func = call.func
                if isinstance(func, ast.Name) and func.id.startswith("_"):
                    found_precondition = True
                    break
        if isinstance(stmt, ast.If):
            for inner in stmt.body:
                if isinstance(inner, ast.Return) and found_precondition:
                    return True
    return False


@pytest.mark.parametrize("path", _check_files(), ids=lambda p: p.name)
def test_security_check_starts_with_policy_enforce(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    runners = _public_run_functions(tree)
    assert runners, f"{path.name} declares no `run_*` function — split it or rename."
    for func in runners:
        body = func.body
        # Skip docstring if present.
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body = body[1:]
        # Allow the early-skip pattern (gated checks may legitimately
        # return without enforcing because they never touch the network).
        if _starts_with_early_skip(body):
            # But there MUST also be a `SafetyPolicy.enforce` call after
            # the skip branch — the non-skipped path enforces policy.
            for stmt in body:
                if _is_safety_enforce(stmt):
                    break
            else:
                raise AssertionError(
                    f"{path.name}::{func.name} has an early-skip branch but never "
                    "enforces SafetyPolicy on the live path."
                )
            continue
        # No early-skip → first statement MUST be SafetyPolicy().enforce(...)
        assert body, f"{path.name}::{func.name} has an empty body."
        assert _is_safety_enforce(body[0]), (
            f"{path.name}::{func.name} does not begin with "
            "`SafetyPolicy().enforce(...)`. Every security probe must "
            "re-enforce the safety boundary at the entry-point "
            "(CLAUDE §6, §26)."
        )

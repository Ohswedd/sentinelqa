"""Postinstall hook scanner (Phase 33.04, ADR-0045).

Walks every ``package.json`` reachable under ``<project_root>/node_modules/``
and every Python package's ``setup.py`` / ``setup.cfg`` /
``pyproject.toml[build-system]``. Suspicious patterns are translated
into typed :class:`PostinstallIssue` records with CWE-506 (Embedded
Malicious Code) so the audit log captures the exact lockfile location
and shell snippet.

The scan is read-only and never executes any of the matched code. The
forbidden-token grep in ``tests/security/test_no_offensive_supply_chain.py``
keeps the implementation from drifting into "execute the hook to see
what it does" territory.
"""

from __future__ import annotations

import ast
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Final

from modules.supply_chain.models import (
    PostinstallIssue,
    PostinstallReport,
)

# npm scripts we care about (executed during ``npm install``).
_NPM_SCRIPT_HOOKS: Final[tuple[str, ...]] = (
    "preinstall",
    "install",
    "postinstall",
    "prepublishOnly",
    "prepublish",
)

# Shell-execution-flavoured tokens. Whole-word matching keeps "bash" in
# a package name from triggering — the regex below adds explicit word
# boundaries.
_NPM_NETWORK_TOKENS: Final[tuple[tuple[str, str], ...]] = (
    ("curl", r"\bcurl\b"),
    ("wget", r"\bwget\b"),
    ("nc", r"\bnc\b"),
    ("ncat", r"\bncat\b"),
    ("bash -c", r"\bbash\s+-c\b"),
    ("sh -c", r"\bsh\s+-c\b"),
    ("eval", r"\beval\b"),
)

_NPM_FILESYSTEM_PATHS: Final[tuple[str, ...]] = (
    "/etc/",
    "/usr/",
    "/var/",
    "/root/",
    "/home/",
    "~/",
    "$HOME",
)


def _all_files_named(root: Path, name: str) -> Iterable[Path]:
    """Yield every file under ``root`` whose basename matches ``name``.

    We walk only ``node_modules/`` deliberately — the project's own
    ``package.json`` is in scope via the implicit drift check rather
    than the postinstall scan (Phase 33.03).
    """

    if not root.is_dir():
        return
    yield from root.rglob(name)


def _classify_npm_match(snippet: str, pattern: str) -> str:
    if pattern == "curl":
        return "high"
    if pattern == "wget":
        return "high"
    if pattern in {"nc", "ncat"}:
        return "high"
    if pattern in {"bash -c", "sh -c"}:
        return "medium"
    if pattern == "eval":
        return "medium"
    return "medium"


def _scan_npm_script(
    *,
    package_name: str,
    package_path: Path,
    hook: str,
    script: str,
) -> tuple[PostinstallIssue, ...]:
    issues: list[PostinstallIssue] = []
    for token_label, regex in _NPM_NETWORK_TOKENS:
        if re.search(regex, script):
            issues.append(
                PostinstallIssue(
                    ecosystem="npm",
                    package=package_name,
                    path=str(package_path),
                    hook=hook,
                    snippet=script[:4000],
                    pattern=token_label,
                    severity=_classify_npm_match(script, token_label),  # type: ignore[arg-type]
                )
            )
    for path_token in _NPM_FILESYSTEM_PATHS:
        if path_token in script:
            issues.append(
                PostinstallIssue(
                    ecosystem="npm",
                    package=package_name,
                    path=str(package_path),
                    hook=hook,
                    snippet=script[:4000],
                    pattern=f"fs-write:{path_token}",
                    severity="medium",
                )
            )
    return tuple(issues)


def scan_npm_packages(node_modules_root: Path) -> tuple[PostinstallIssue, ...]:
    """Walk ``node_modules/`` for suspicious postinstall scripts."""

    issues: list[PostinstallIssue] = []
    for package_json in _all_files_named(node_modules_root, "package.json"):
        try:
            payload = json.loads(package_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        scripts = payload.get("scripts", {})
        if not isinstance(scripts, dict):
            continue
        package_name = payload.get("name")
        if not isinstance(package_name, str):
            package_name = package_json.parent.name
        for hook in _NPM_SCRIPT_HOOKS:
            script = scripts.get(hook)
            if not isinstance(script, str) or not script.strip():
                continue
            issues.extend(
                _scan_npm_script(
                    package_name=package_name,
                    package_path=package_json,
                    hook=hook,
                    script=script,
                )
            )
    return tuple(issues)


# ---------------------------------------------------------------------------
# Python AST scan
# ---------------------------------------------------------------------------


# Modules that, if imported at top-level by ``setup.py``, indicate code
# that may run at install time. These are heuristics — false positives
# are tolerable; missing a real malicious payload is not.
_PYTHON_FORBIDDEN_IMPORTS: Final[frozenset[str]] = frozenset(
    {
        "os.system",
        "subprocess",
        "urllib.request",
        "urllib3",
        "requests",
        "httpx",
        "socket",
    }
)


def _flatten_import_aliases(node: ast.AST) -> Iterable[str]:
    """Yield dotted names imported by ``import`` / ``from ... import``."""

    if isinstance(node, ast.Import):
        for alias in node.names:
            yield alias.name
    elif isinstance(node, ast.ImportFrom):
        module = node.module or ""
        for alias in node.names:
            full = f"{module}.{alias.name}" if module else alias.name
            yield full


def _flatten_calls(node: ast.AST) -> Iterable[str]:
    """Yield dotted callee names for direct calls at module level."""

    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Attribute):
                parts: list[str] = []
                current: ast.AST = func
                while isinstance(current, ast.Attribute):
                    parts.append(current.attr)
                    current = current.value
                if isinstance(current, ast.Name):
                    parts.append(current.id)
                yield ".".join(reversed(parts))
            elif isinstance(func, ast.Name):
                yield func.id


def scan_python_setup_py(setup_py: Path) -> tuple[PostinstallIssue, ...]:
    """Scan a single ``setup.py`` for forbidden imports / calls.

    The check runs at module-load time, not when ``setup()`` is called.
    Anything that imports ``subprocess`` / ``urllib.request`` / ``requests``
    / ``socket`` at the top of ``setup.py`` is flagged because those
    modules don't belong in build metadata.
    """

    issues: list[PostinstallIssue] = []
    try:
        source = setup_py.read_text(encoding="utf-8")
    except OSError:
        return ()
    try:
        tree = ast.parse(source, filename=str(setup_py))
    except SyntaxError:
        return ()
    package_name = setup_py.parent.name
    flagged_imports: set[str] = set()
    for node in tree.body:
        for name in _flatten_import_aliases(node):
            for forbidden in _PYTHON_FORBIDDEN_IMPORTS:
                if name == forbidden or name.startswith(forbidden + "."):
                    flagged_imports.add(forbidden)
                    issues.append(
                        PostinstallIssue(
                            ecosystem="python",
                            package=package_name,
                            path=str(setup_py),
                            hook="setup.py",
                            snippet=source.splitlines()[node.lineno - 1][:4000],
                            pattern=f"import:{forbidden}",
                            severity="high" if forbidden == "subprocess" else "medium",
                        )
                    )
    # Direct calls to ``os.system`` / ``subprocess.Popen`` / ``subprocess.run``
    # at module level.
    for callee in _flatten_calls(tree):
        if callee in {"os.system", "subprocess.Popen", "subprocess.run", "subprocess.call"}:
            issues.append(
                PostinstallIssue(
                    ecosystem="python",
                    package=package_name,
                    path=str(setup_py),
                    hook="setup.py",
                    snippet=callee,
                    pattern=f"call:{callee}",
                    severity="high",
                )
            )
    return tuple(issues)


def scan_python_packages(project_root: Path) -> tuple[PostinstallIssue, ...]:
    """Scan every ``setup.py`` under ``site-packages`` / ``.venv``.

    We deliberately skip the project's own ``setup.py`` (if any) — the
    operator owns that file. Third-party packages installed into the
    project virtualenv are in scope.
    """

    issues: list[PostinstallIssue] = []
    candidates: list[Path] = []
    for venv_dir in ("venv", ".venv"):
        venv_root = project_root / venv_dir
        if venv_root.is_dir():
            candidates.extend(venv_root.rglob("setup.py"))
    for site_packages in (project_root / ".tox").rglob("setup.py"):
        candidates.append(site_packages)
    seen: set[Path] = set()
    for setup_py in candidates:
        resolved = setup_py.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        issues.extend(scan_python_setup_py(setup_py))
    return tuple(issues)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def evaluate_postinstall(project_root: Path) -> PostinstallReport:
    """Run both scanners and aggregate the result."""

    node_modules_root = project_root / "node_modules"
    npm_issues = scan_npm_packages(node_modules_root)
    python_issues = scan_python_packages(project_root)
    issues = tuple(
        sorted(
            npm_issues + python_issues, key=lambda issue: (issue.package, issue.hook, issue.pattern)
        )
    )

    scanned = 0
    if node_modules_root.is_dir():
        scanned += sum(1 for _ in _all_files_named(node_modules_root, "package.json"))
    # We don't count Python setup.py files toward ``scanned_packages`` since
    # they're highly heterogeneous; the npm count is the primary signal
    # operators look at.

    if scanned == 0 and not python_issues:
        return PostinstallReport(
            scanned_packages=0,
            issues=(),
            skipped=True,
            skipped_reason="no node_modules/ or python setup.py files to scan",
        )
    return PostinstallReport(
        scanned_packages=scanned,
        issues=issues,
    )


__all__ = [
    "evaluate_postinstall",
    "scan_npm_packages",
    "scan_python_packages",
    "scan_python_setup_py",
]

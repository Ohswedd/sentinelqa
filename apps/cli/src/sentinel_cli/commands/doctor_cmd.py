"""`sentinel doctor` command.

Read-only preflight: env versions, Playwright install, config presence,
target reachability, env-var presence, writable `.sentinel/`, disk
space. Outputs human-readable ASCII table or one structured JSON object.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal
from urllib.parse import urlparse

import typer
from engine.config.loader import load_config
from engine.errors.base import (
    ConfigError,
    ConfigFileNotFoundError,
    UnsafeTargetError,
)
from engine.errors.codes import (
    EXIT_CONFIG_ERROR,
    EXIT_DEPENDENCY_MISSING,
    EXIT_SUCCESS,
    EXIT_UNSAFE_TARGET,
)
from engine.policy.safety import SafetyPolicy

from sentinel_cli.json_mode import json_stdout
from sentinel_cli.platform_install_hints import format_hint
from sentinel_cli.state import GlobalState

_MIN_PYTHON: Final[tuple[int, int]] = (3, 11)
_MIN_NODE_MAJOR: Final[int] = 20
_DISK_MIN_GB: Final[float] = 1.0

Status = Literal["ok", "warn", "fail"]


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    name: str
    status: Status
    detail: str
    suggestion: str
    exit_code_hint: int | None = None


def _check_python_version() -> DoctorCheck:
    current = sys.version_info[:2]
    if current >= _MIN_PYTHON:
        return DoctorCheck(
            name="python",
            status="ok",
            detail=f"Python {sys.version.split()[0]}",
            suggestion="",
        )
    return DoctorCheck(
        name="python",
        status="fail",
        detail=f"Python {sys.version.split()[0]} < {'.'.join(map(str, _MIN_PYTHON))}",
        suggestion=(
            f"Install Python {_MIN_PYTHON[0]}.{_MIN_PYTHON[1]} or newer." + format_hint("python")
        ),
        exit_code_hint=EXIT_DEPENDENCY_MISSING,
    )


def _check_node_version() -> DoctorCheck:
    node = shutil.which("node")
    if node is None:
        return DoctorCheck(
            name="node",
            status="warn",
            detail="Node.js not found.",
            suggestion=(
                "Install Node 20+ — required for the Playwright TypeScript runtime."
                + format_hint("node")
            ),
        )
    try:
        out = subprocess.run(
            [node, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return DoctorCheck(
            name="node",
            status="warn",
            detail=f"Could not run `node --version`: {exc}",
            suggestion="Reinstall Node or fix PATH.",
        )
    version_text = out.stdout.strip().lstrip("v")
    try:
        major = int(version_text.split(".")[0])
    except (IndexError, ValueError):
        return DoctorCheck(
            name="node",
            status="warn",
            detail=f"Unrecognized Node version string: {version_text!r}.",
            suggestion="Reinstall Node 20+.",
        )
    if major < _MIN_NODE_MAJOR:
        return DoctorCheck(
            name="node",
            status="warn",
            detail=f"Node v{version_text} < required v{_MIN_NODE_MAJOR}",
            suggestion=f"Upgrade Node to v{_MIN_NODE_MAJOR}+." + format_hint("node"),
        )
    return DoctorCheck(
        name="node",
        status="ok",
        detail=f"Node v{version_text}",
        suggestion="",
    )


def _check_playwright() -> DoctorCheck:
    npx = shutil.which("npx")
    if npx is None:
        return DoctorCheck(
            name="playwright",
            status="warn",
            detail="`npx` not found; Playwright cannot be exercised.",
            suggestion=(
                "Install Node 20+ then run `npx playwright install --with-deps`."
                + format_hint("node")
            ),
        )
    try:
        out = subprocess.run(
            [npx, "playwright", "--version"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return DoctorCheck(
            name="playwright",
            status="warn",
            detail=f"Could not run `npx playwright --version`: {exc}",
            suggestion="Re-install Playwright: `npx playwright install --with-deps`.",
        )
    if out.returncode != 0:
        return DoctorCheck(
            name="playwright",
            status="warn",
            detail=f"`npx playwright --version` exited {out.returncode}.",
            suggestion="Run `npx playwright install --with-deps`." + format_hint("playwright"),
        )
    version_line = out.stdout.strip().splitlines()[0] if out.stdout.strip() else "unknown"
    return DoctorCheck(
        name="playwright",
        status="ok",
        detail=version_line,
        suggestion="",
    )


def _check_config(config_path: Path) -> tuple[DoctorCheck, object | None]:
    if not config_path.exists():
        return (
            DoctorCheck(
                name="config",
                status="warn",
                detail=f"Config file {config_path} not found.",
                suggestion="Run `sentinel init` to scaffold a default config.",
            ),
            None,
        )
    try:
        config = load_config(config_path)
    except ConfigFileNotFoundError as exc:
        return (
            DoctorCheck(
                name="config",
                status="fail",
                detail=exc.message,
                suggestion=exc.suggested_fix,
                exit_code_hint=EXIT_CONFIG_ERROR,
            ),
            None,
        )
    except ConfigError as exc:
        return (
            DoctorCheck(
                name="config",
                status="fail",
                detail=exc.message,
                suggestion=exc.suggested_fix,
                exit_code_hint=EXIT_CONFIG_ERROR,
            ),
            None,
        )
    return (
        DoctorCheck(
            name="config",
            status="ok",
            detail=f"Config loaded from {config_path}.",
            suggestion="",
        ),
        config,
    )


def _check_safety(config: object) -> DoctorCheck:
    from engine.config.schema import RootConfig
    from engine.domain.target import Target

    assert isinstance(config, RootConfig)

    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
        mode=config.security.mode,
        proof_of_authorization=config.target.proof_of_authorization,
    )
    try:
        decision = SafetyPolicy().enforce(target)
    except UnsafeTargetError as exc:
        return DoctorCheck(
            name="safety",
            status="fail",
            detail=exc.message,
            suggestion=exc.suggested_fix,
            exit_code_hint=EXIT_UNSAFE_TARGET,
        )
    return DoctorCheck(
        name="safety",
        status="ok",
        detail=f"Target {decision.host!r} allowed in mode={decision.mode}.",
        suggestion="",
    )


def _check_reachability(config: object) -> DoctorCheck:
    from engine.config.schema import RootConfig

    assert isinstance(config, RootConfig)

    url = str(config.target.base_url)
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return DoctorCheck(
            name="reachability",
            status="warn",
            detail=f"Malformed target URL {url!r}.",
            suggestion="Fix `target.base_url` in sentinel.config.yaml.",
        )
    try:
        import httpx
    except ImportError:
        return DoctorCheck(
            name="reachability",
            status="warn",
            detail="httpx not installed; skipping reachability probe.",
            suggestion="Install httpx." + format_hint("httpx"),
        )
    try:
        response = httpx.head(url, follow_redirects=True, timeout=5.0)
    except httpx.HTTPError as exc:
        return DoctorCheck(
            name="reachability",
            status="warn",
            detail=f"Could not reach {url}: {type(exc).__name__}",
            suggestion="Start the app, fix the URL, or wait until later. Non-fatal.",
        )
    return DoctorCheck(
        name="reachability",
        status="ok" if response.status_code < 500 else "warn",
        detail=f"{url} responded {response.status_code}.",
        suggestion="" if response.status_code < 500 else "App returned 5xx; investigate.",
    )


def _check_env_vars(config: object) -> DoctorCheck:
    from engine.config.schema import RootConfig

    assert isinstance(config, RootConfig)

    required: list[str] = []
    auth = config.auth
    if config.modules.functional and auth.strategy != "none":
        for name in (auth.username_env, auth.password_env, auth.token_env):
            if name:
                required.append(name)

    missing = [name for name in required if not os.environ.get(name)]
    if not missing:
        return DoctorCheck(
            name="env-vars",
            status="ok",
            detail=f"All {len(required)} configured env vars present.",
            suggestion="",
        )
    return DoctorCheck(
        name="env-vars",
        status="fail",
        detail=f"Missing env vars: {', '.join(missing)}",
        suggestion=f"`export {missing[0]}=<value>` (and others) before running.",
        exit_code_hint=EXIT_DEPENDENCY_MISSING,
    )


def _check_sentinel_dir(root: Path) -> DoctorCheck:
    target_dir = root / ".sentinel"
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        probe = target_dir / ".doctor_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return DoctorCheck(
            name="sentinel-dir",
            status="fail",
            detail=f"`.sentinel/` is not writable: {exc}",
            suggestion="Check filesystem permissions on the project root.",
            exit_code_hint=EXIT_DEPENDENCY_MISSING,
        )
    return DoctorCheck(
        name="sentinel-dir",
        status="ok",
        detail=str(target_dir.resolve()),
        suggestion="",
    )


def _check_disk_space(root: Path) -> DoctorCheck:
    try:
        usage = shutil.disk_usage(str(root))
    except OSError as exc:
        return DoctorCheck(
            name="disk",
            status="warn",
            detail=f"Could not stat disk usage: {exc}",
            suggestion="",
        )
    free_gb = usage.free / (1024**3)
    if free_gb < _DISK_MIN_GB:
        return DoctorCheck(
            name="disk",
            status="warn",
            detail=f"Free disk space {free_gb:.2f} GB < {_DISK_MIN_GB:.1f} GB recommended.",
            suggestion="Free up space; runs collect traces/screenshots/videos.",
        )
    return DoctorCheck(
        name="disk",
        status="ok",
        detail=f"{free_gb:.2f} GB free.",
        suggestion="",
    )


def _aggregate_exit_code(checks: list[DoctorCheck]) -> int:
    for check in checks:
        if check.status == "fail" and check.exit_code_hint is not None:
            return check.exit_code_hint
    if any(c.status == "fail" for c in checks):
        return EXIT_DEPENDENCY_MISSING
    return EXIT_SUCCESS


def _overall_status(checks: list[DoctorCheck]) -> Status:
    if any(c.status == "fail" for c in checks):
        return "fail"
    if any(c.status == "warn" for c in checks):
        return "warn"
    return "ok"


def run_doctor(ctx: typer.Context) -> None:
    """Execute every doctor check."""

    state: GlobalState = ctx.obj
    config_path: Path = state.config_path
    project_root = config_path.parent if config_path.parent != Path("") else Path(".")

    checks: list[DoctorCheck] = []
    checks.append(_check_python_version())
    checks.append(_check_node_version())
    checks.append(_check_playwright())

    config_check, config_obj = _check_config(config_path)
    checks.append(config_check)
    if config_obj is not None:
        checks.append(_check_safety(config_obj))
        checks.append(_check_reachability(config_obj))
        checks.append(_check_env_vars(config_obj))
    checks.append(_check_sentinel_dir(project_root))
    checks.append(_check_disk_space(project_root))

    exit_code = _aggregate_exit_code(checks)
    status = _overall_status(checks)

    if state.mode == "json":
        with json_stdout() as out:
            out.emit(
                {
                    "command": "doctor",
                    "status": status,
                    "exit_code": exit_code,
                    "checks": [
                        {
                            "name": c.name,
                            "status": c.status,
                            "detail": c.detail,
                            "suggestion": c.suggestion,
                        }
                        for c in checks
                    ],
                }
            )
    elif state.mode != "quiet":
        _print_human_table(checks, status)

    if exit_code != EXIT_SUCCESS:
        raise typer.Exit(code=exit_code)


def _print_human_table(checks: list[DoctorCheck], status: Status) -> None:
    width = max(len(c.name) for c in checks) + 2
    sys.stdout.write("SentinelQA doctor:\n\n")
    for check in checks:
        marker = {"ok": "[ ok ]", "warn": "[warn]", "fail": "[FAIL]"}[check.status]
        sys.stdout.write(f"  {marker}  {check.name:<{width}} {check.detail}\n")
        if check.suggestion:
            sys.stdout.write(f"          {' ' * width} -> {check.suggestion}\n")
    sys.stdout.write(f"\noverall: {status}\n")


# Re-exported for tests; lets a test build a known list of checks.
DoctorCheck.__doc__ = "Single environment / config / target check result."


# Tests monkey-patch the `subprocess` and `shutil` modules used here. Listing
# them in __all__ makes that explicit and quiets `attr-defined` on strict mypy.
__all__ = ["run_doctor", "DoctorCheck", "subprocess", "shutil"]

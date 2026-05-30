"""Phase 24 task 24.04 — subprocess sandbox.

Acceptance criteria:

- Sandboxed plugin can't read env vars it didn't request.
- Stdin/stdout protocol round-trips a serialisable result.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from engine.plugins.errors import PluginPermissionError
from engine.plugins.sandbox import (
    ALWAYS_INHERITED_ENV,
    INHERITED_ENV_PREFIXES,
    SandboxInvocation,
    build_constrained_env,
    run_in_sandbox,
)

# ---------------------------------------------------------------------------
# Env filtering
# ---------------------------------------------------------------------------


def test_build_constrained_env_includes_always_inherited() -> None:
    env = build_constrained_env(
        granted_permissions=frozenset(),
        source_env={
            "PATH": "/usr/bin",
            "HOME": "/home/x",
            "SECRET_TOKEN": "should-not-pass",
        },
    )
    assert env["PATH"] == "/usr/bin"
    assert env["HOME"] == "/home/x"
    assert "SECRET_TOKEN" not in env


def test_build_constrained_env_passes_sentinel_prefixes() -> None:
    env = build_constrained_env(
        granted_permissions=frozenset(),
        source_env={
            "SENTINEL_RUN_ID": "RUN-1",
            "SENTINELQA_FLAG": "1",
            "OTHER": "no",
        },
    )
    assert env["SENTINEL_RUN_ID"] == "RUN-1"
    assert env["SENTINELQA_FLAG"] == "1"
    assert "OTHER" not in env


def test_build_constrained_env_honours_env_read_permission() -> None:
    env = build_constrained_env(
        granted_permissions=frozenset({"env.read:DATABASE_URL"}),
        source_env={
            "DATABASE_URL": "postgres://...",
            "AWS_SECRET_KEY": "leaked",
        },
    )
    assert env["DATABASE_URL"] == "postgres://..."
    assert "AWS_SECRET_KEY" not in env


def test_inherited_env_prefixes_are_documented() -> None:
    assert "SENTINEL_" in INHERITED_ENV_PREFIXES
    assert "SENTINELQA_" in INHERITED_ENV_PREFIXES
    # ALWAYS_INHERITED_ENV must contain at least PATH/HOME.
    assert "PATH" in ALWAYS_INHERITED_ENV
    assert "HOME" in ALWAYS_INHERITED_ENV


# ---------------------------------------------------------------------------
# Permission gate
# ---------------------------------------------------------------------------


def test_run_in_sandbox_requires_subprocess_spawn(tmp_path: Path) -> None:
    inv = SandboxInvocation(
        plugin_entry_point="json:dumps",
        granted_permissions=frozenset(),
        payload={},
        run_id="RUN-1",
        target_url="http://localhost",
        run_dir=tmp_path,
        config_snapshot={},
    )
    with pytest.raises(PluginPermissionError):
        run_in_sandbox(inv)


# ---------------------------------------------------------------------------
# End-to-end JSON round-trip with a fake plugin
# ---------------------------------------------------------------------------


def _write_fake_plugin(tmp_path: Path) -> Path:
    """Write a tiny plugin to a temp dir and return the package root.

    The plugin is registered under ``fake_pkg_<n>.plugin`` so we can
    address it via entry-point notation in the sandbox call.
    """

    package = tmp_path / "fake_pkg"
    package.mkdir(parents=True, exist_ok=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "plugin.py").write_text(
        textwrap.dedent(
            '''
            """Sandbox fake plugin."""
            from __future__ import annotations

            import os


            class Echoer:
                kind = "scanner"
                name = "echoer"
                version = "0.1.0"
                capabilities = frozenset({"audit"})
                permissions = frozenset({"subprocess.spawn", "env.read:LEAK_OK"})
                requires_protocol = ">=1.0,<2.0"

                def run(self, context):
                    return {
                        "ran": True,
                        "leak_ok": os.environ.get("LEAK_OK"),
                        "leak_no": os.environ.get("LEAK_NO"),
                        "run_id": context.run_id,
                    }
            '''
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return tmp_path


def test_sandbox_roundtrips_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package_root = _write_fake_plugin(tmp_path)
    # Inject the package's parent into PYTHONPATH so the worker can
    # import it; the worker inherits PYTHONPATH only via the sandbox
    # env filter, which we test below.
    monkeypatch.setenv("LEAK_OK", "allowed")
    monkeypatch.setenv("LEAK_NO", "blocked")
    monkeypatch.setenv("PYTHONPATH", str(package_root))

    inv = SandboxInvocation(
        plugin_entry_point="fake_pkg.plugin:Echoer",
        granted_permissions=frozenset({"subprocess.spawn", "env.read:LEAK_OK"}),
        payload={"hello": "world"},
        run_id="RUN-sb-1",
        target_url="http://localhost",
        run_dir=tmp_path / "runs",
        config_snapshot={},
    )

    outcome = run_in_sandbox(inv)

    if not outcome.ok:
        # surface the sandbox error to the test report so it's debuggable
        raise AssertionError(
            f"sandbox failed: result={outcome.result!r}, stderr={outcome.stderr!r}"
        )
    assert outcome.result["ran"] is True
    assert outcome.result["run_id"] == "RUN-sb-1"
    # LEAK_OK was permitted via env.read:LEAK_OK; LEAK_NO must NOT pass.
    assert outcome.result["leak_ok"] == "allowed"
    assert outcome.result["leak_no"] is None


def test_sandbox_strips_unrequested_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package_root = _write_fake_plugin(tmp_path)
    monkeypatch.setenv("SECRET_FOR_TEST", "leaked")
    monkeypatch.setenv("PYTHONPATH", str(package_root))

    inv = SandboxInvocation(
        plugin_entry_point="fake_pkg.plugin:Echoer",
        granted_permissions=frozenset({"subprocess.spawn"}),
        payload={},
        run_id="RUN-sb-2",
        target_url="http://localhost",
        run_dir=tmp_path / "runs",
        config_snapshot={},
    )

    outcome = run_in_sandbox(inv)
    assert outcome.ok
    assert outcome.result["leak_no"] is None
    assert outcome.result["leak_ok"] is None


def test_sandbox_handles_plugin_raising(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package = tmp_path / "fake_pkg_boom"
    package.mkdir(parents=True, exist_ok=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "plugin.py").write_text(
        textwrap.dedent(
            """
            class Boom:
                kind = "scanner"
                name = "boom"
                version = "0.1.0"
                capabilities = frozenset()
                permissions = frozenset({"subprocess.spawn"})
                requires_protocol = ">=1.0"

                def run(self, context):
                    raise RuntimeError("kaboom")
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))

    inv = SandboxInvocation(
        plugin_entry_point="fake_pkg_boom.plugin:Boom",
        granted_permissions=frozenset({"subprocess.spawn"}),
        payload={},
        run_id="RUN-3",
        target_url="http://localhost",
        run_dir=tmp_path / "runs",
        config_snapshot={},
    )
    outcome = run_in_sandbox(inv)
    assert outcome.ok is False
    assert "kaboom" in outcome.result.get("error", "")


def test_sandbox_handles_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package = tmp_path / "fake_pkg_slow"
    package.mkdir(parents=True, exist_ok=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "plugin.py").write_text(
        textwrap.dedent(
            """
            import time

            class Slow:
                kind = "scanner"
                name = "slow"
                version = "0.1.0"
                capabilities = frozenset()
                permissions = frozenset({"subprocess.spawn"})
                requires_protocol = ">=1.0"

                def run(self, context):
                    time.sleep(5)
                    return {}
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))

    inv = SandboxInvocation(
        plugin_entry_point="fake_pkg_slow.plugin:Slow",
        granted_permissions=frozenset({"subprocess.spawn"}),
        payload={},
        run_id="RUN-slow",
        target_url="http://localhost",
        run_dir=tmp_path / "runs",
        config_snapshot={},
    )

    outcome = run_in_sandbox(inv, timeout_seconds=0.5)
    assert outcome.ok is False
    assert "timed out" in outcome.result.get("error", "")


def test_sandbox_returns_serialisable_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = tmp_path / "fake_pkg_pydantic"
    package.mkdir(parents=True, exist_ok=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "plugin.py").write_text(
        textwrap.dedent(
            """
            from pydantic import BaseModel


            class Result(BaseModel):
                run_id: str
                score: int


            class Pyd:
                kind = "scanner"
                name = "pyd"
                version = "0.1.0"
                capabilities = frozenset()
                permissions = frozenset({"subprocess.spawn"})
                requires_protocol = ">=1.0"

                def run(self, context):
                    return Result(run_id=context.run_id, score=42)
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))

    inv = SandboxInvocation(
        plugin_entry_point="fake_pkg_pydantic.plugin:Pyd",
        granted_permissions=frozenset({"subprocess.spawn"}),
        payload={},
        run_id="RUN-pyd",
        target_url="http://localhost",
        run_dir=tmp_path / "runs",
        config_snapshot={},
    )

    outcome = run_in_sandbox(inv)
    assert outcome.ok
    assert outcome.result == {"run_id": "RUN-pyd", "score": 42}

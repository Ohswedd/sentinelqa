"""Direct coverage for :mod:`engine.plugins.sandbox_worker`.

The subprocess sandbox tests already exercise the worker end-to-end,
but coverage doesn't see lines run in a child interpreter. This file
calls ``main`` in-process with stdin/stdout monkey-patched so the
worker's branches are visible to ``coverage.py``.
"""

from __future__ import annotations

import io
import json
import sys
import textwrap
from pathlib import Path

from engine.plugins.sandbox_worker import _serialize_result, main


def _run_main(payload: dict) -> tuple[int, dict]:
    fake_stdin = io.StringIO(json.dumps(payload))
    fake_stdout = io.StringIO()
    orig_stdin, orig_stdout = sys.stdin, sys.stdout
    sys.stdin, sys.stdout = fake_stdin, fake_stdout
    try:
        exit_code = main([])
    finally:
        sys.stdin, sys.stdout = orig_stdin, orig_stdout
    output = fake_stdout.getvalue().strip().splitlines()[-1]
    return exit_code, json.loads(output)


def _plant_module(tmp_path: Path, source: str, name: str = "_in_proc_worker") -> Path:
    pkg = tmp_path / name
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "plugin.py").write_text(textwrap.dedent(source).strip() + "\n", encoding="utf-8")
    sys.path.insert(0, str(tmp_path))
    return pkg


def test_main_returns_zero_on_success(tmp_path: Path) -> None:
    _plant_module(
        tmp_path,
        """
        class Echo:
            kind = "scanner"
            name = "echo"
            version = "0.1.0"
            capabilities = frozenset()
            permissions = frozenset({"subprocess.spawn"})
            requires_protocol = ">=1.0"

            def run(self, context):
                return {"run_id": context.run_id, "ok": True}
        """,
        name="worker_pkg_ok",
    )
    exit_code, payload = _run_main(
        {
            "plugin_entry_point": "worker_pkg_ok.plugin:Echo",
            "granted_permissions": ["subprocess.spawn"],
            "payload": {},
            "run_id": "RUN-WORKERTEST01",
            "target_url": "http://localhost",
            "run_dir": str(tmp_path),
            "config_snapshot": {},
        }
    )
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["result"]["run_id"] == "RUN-WORKERTEST01"


def test_main_returns_two_on_bad_stdin_json(tmp_path: Path) -> None:
    fake_stdin = io.StringIO("not json")
    fake_stdout = io.StringIO()
    orig_stdin, orig_stdout = sys.stdin, sys.stdout
    sys.stdin, sys.stdout = fake_stdin, fake_stdout
    try:
        exit_code = main([])
    finally:
        sys.stdin, sys.stdout = orig_stdin, orig_stdout
    assert exit_code == 2
    payload = json.loads(fake_stdout.getvalue().strip().splitlines()[-1])
    assert payload["ok"] is False
    assert "bad stdin JSON" in payload["result"]["error"]


def test_main_returns_one_on_plugin_exception(tmp_path: Path) -> None:
    _plant_module(
        tmp_path,
        """
        class Boom:
            kind = "scanner"
            name = "boom"
            version = "0.1.0"
            capabilities = frozenset()
            permissions = frozenset({"subprocess.spawn"})
            requires_protocol = ">=1.0"

            def run(self, context):
                raise RuntimeError("kaboom-worker")
        """,
        name="worker_pkg_boom",
    )
    exit_code, payload = _run_main(
        {
            "plugin_entry_point": "worker_pkg_boom.plugin:Boom",
            "granted_permissions": ["subprocess.spawn"],
            "payload": {},
            "run_id": "RUN-WORKERTEST02",
            "target_url": "http://localhost",
            "run_dir": str(tmp_path),
            "config_snapshot": {},
        }
    )
    assert exit_code == 1
    assert payload["ok"] is False
    assert "kaboom-worker" in payload["result"]["error"]


def test_main_rejects_malformed_entry_point(tmp_path: Path) -> None:
    exit_code, payload = _run_main(
        {
            "plugin_entry_point": "no-colon-here",
            "granted_permissions": ["subprocess.spawn"],
            "payload": {},
            "run_id": "RUN-WORKERTEST03",
            "target_url": "http://localhost",
            "run_dir": str(tmp_path),
            "config_snapshot": {},
        }
    )
    assert exit_code == 1
    assert payload["ok"] is False


def test_serialize_result_pydantic_model() -> None:
    from pydantic import BaseModel

    class M(BaseModel):
        score: int

    assert _serialize_result(M(score=7)) == {"score": 7}


def test_serialize_result_namedtuple() -> None:
    from collections import namedtuple

    Pair = namedtuple("Pair", ["a", "b"])
    assert _serialize_result(Pair(1, 2)) == {"a": 1, "b": 2}


def test_serialize_result_unserialisable_falls_back_to_repr() -> None:
    class NotJson:
        def __repr__(self) -> str:
            return "<not-json>"

    assert _serialize_result(NotJson()) == "<not-json>"


def test_serialize_result_passes_through_basic_types() -> None:
    assert _serialize_result({"a": 1}) == {"a": 1}
    assert _serialize_result([1, 2]) == [1, 2]
    assert _serialize_result("hello") == "hello"

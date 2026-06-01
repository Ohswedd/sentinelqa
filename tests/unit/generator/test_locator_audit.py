"""Tests for the Python locator audit wrapper."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from engine.generator.locator_strategy import (
    BrittlenessAuditResult,
    LocatorAuditError,
    audit_specs,
)


@dataclass
class _FakeCompleted:
    stdout: str
    stderr: str = ""
    returncode: int = 0


def _runner_returning(payload: dict[str, Any], *, exit_code: int = 0) -> object:
    def _run(*_args: object, **_kwargs: object) -> _FakeCompleted:
        return _FakeCompleted(stdout=json.dumps(payload), returncode=exit_code)

    return _run


def test_empty_files_short_circuits(tmp_path: Path) -> None:
    result = audit_specs([])
    assert isinstance(result, BrittlenessAuditResult)
    assert result.is_clean
    assert result.files_scanned == 0


def test_parses_clean_report(tmp_path: Path) -> None:
    spec = tmp_path / "ok.ts"
    spec.write_text("x", encoding="utf-8")
    result = audit_specs(
        [spec],
        cwd=tmp_path,
        executable="dummy",
        runner=_runner_returning(
            {"schema_version": "1.0.0", "files_scanned": 1, "findings": []}, exit_code=0
        ),
    )
    assert result.is_clean
    assert result.files_scanned == 1


def test_parses_findings_with_exit_1(tmp_path: Path) -> None:
    spec = tmp_path / "bad.ts"
    spec.write_text("x", encoding="utf-8")
    result = audit_specs(
        [spec],
        cwd=tmp_path,
        executable="dummy",
        runner=_runner_returning(
            {
                "schema_version": "1.0.0",
                "files_scanned": 1,
                "findings": [
                    {
                        "file": "bad.ts",
                        "line": 3,
                        "column": 22,
                        "message": "brittle",
                        "snippet": "page.locator('...')",
                    }
                ],
            },
            exit_code=1,
        ),
    )
    assert not result.is_clean
    assert result.warnings[0].file == "bad.ts"
    assert result.warnings[0].line == 3


def test_nonzero_unknown_exit_raises(tmp_path: Path) -> None:
    spec = tmp_path / "x.ts"
    spec.write_text("x", encoding="utf-8")

    def _run(*_args: object, **_kwargs: object) -> _FakeCompleted:
        return _FakeCompleted(stdout="", stderr="boom", returncode=2)

    with pytest.raises(LocatorAuditError) as exc:
        audit_specs([spec], cwd=tmp_path, executable="dummy", runner=_run)
    assert "exited 2" in str(exc.value)


def test_empty_stdout_raises(tmp_path: Path) -> None:
    spec = tmp_path / "x.ts"
    spec.write_text("x", encoding="utf-8")

    def _run(*_args: object, **_kwargs: object) -> _FakeCompleted:
        return _FakeCompleted(stdout="", stderr="", returncode=0)

    with pytest.raises(LocatorAuditError) as exc:
        audit_specs([spec], cwd=tmp_path, executable="dummy", runner=_run)
    assert "no JSON" in str(exc.value)


def test_malformed_json_raises(tmp_path: Path) -> None:
    spec = tmp_path / "x.ts"
    spec.write_text("x", encoding="utf-8")

    def _run(*_args: object, **_kwargs: object) -> _FakeCompleted:
        return _FakeCompleted(stdout="{not json", stderr="", returncode=0)

    with pytest.raises(LocatorAuditError):
        audit_specs([spec], cwd=tmp_path, executable="dummy", runner=_run)


def test_payload_without_findings_key_raises(tmp_path: Path) -> None:
    spec = tmp_path / "x.ts"
    spec.write_text("x", encoding="utf-8")
    with pytest.raises(LocatorAuditError):
        audit_specs(
            [spec],
            cwd=tmp_path,
            executable="dummy",
            runner=_runner_returning({"schema_version": "1.0.0"}),
        )


def test_spawn_failure_wrapped(tmp_path: Path) -> None:
    spec = tmp_path / "x.ts"
    spec.write_text("x", encoding="utf-8")

    def _run(*_args: object, **_kwargs: object) -> _FakeCompleted:
        raise FileNotFoundError("missing binary")

    with pytest.raises(LocatorAuditError) as exc:
        audit_specs([spec], cwd=tmp_path, executable="dummy", runner=_run)
    assert "missing binary" in str(exc.value)

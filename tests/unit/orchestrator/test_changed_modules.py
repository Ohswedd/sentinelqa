# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for diff-based module selection."""

from __future__ import annotations

from pathlib import Path

import pytest
from engine.orchestrator.changed_modules import (
    ALL_MODULES,
    DiffSelection,
    GitNotAvailableError,
    changed_files_against,
    impacted_modules,
    select_modules,
)


def test_empty_diff_yields_empty_selection() -> None:
    s = impacted_modules([])
    assert isinstance(s, DiffSelection)
    assert s.modules == frozenset()
    assert s.empty()
    assert s.all_invalidated is False


def test_tsx_change_impacts_functional_a11y_visual_perf() -> None:
    s = impacted_modules([Path("src/components/Button.tsx")])
    assert "functional" in s.modules
    assert "a11y" in s.modules
    assert "visual" in s.modules
    assert "perf" in s.modules
    assert s.all_invalidated is False


def test_api_route_change_impacts_api_module() -> None:
    s = impacted_modules([Path("app/api/users/route.ts")])
    assert "api" in s.modules


def test_python_backend_change_impacts_api_and_security() -> None:
    s = impacted_modules([Path("backend/server/main.py")])
    assert "api" in s.modules
    assert "security" in s.modules


def test_lockfile_change_invalidates_everything() -> None:
    s = impacted_modules([Path("pnpm-lock.yaml")])
    assert s.modules == ALL_MODULES
    assert s.all_invalidated is True


def test_package_json_invalidates_everything() -> None:
    s = impacted_modules([Path("apps/web/package.json")])
    assert s.modules == ALL_MODULES
    assert s.all_invalidated is True


def test_next_config_invalidates_everything() -> None:
    s = impacted_modules([Path("apps/web/next.config.ts")])
    assert s.all_invalidated is True


def test_dockerfile_invalidates_everything() -> None:
    s = impacted_modules([Path("Dockerfile"), Path("apps/cli/Dockerfile.cli")])
    assert s.all_invalidated is True


def test_markdown_only_change_yields_no_modules() -> None:
    s = impacted_modules([Path("README.md"), Path("docs/intro.md"), Path("CHANGELOG.md")])
    assert s.modules == frozenset()
    assert s.empty() is True


def test_css_change_impacts_a11y_and_visual() -> None:
    s = impacted_modules([Path("apps/web/src/styles/globals.css")])
    assert "a11y" in s.modules
    assert "visual" in s.modules


def test_env_file_change_impacts_security() -> None:
    s = impacted_modules([Path("apps/web/.env.production")])
    assert "security" in s.modules


def test_openapi_change_impacts_api() -> None:
    s = impacted_modules([Path("docs/openapi.yaml")])
    assert "api" in s.modules


def test_select_modules_with_intersection() -> None:
    """When ``--modules`` is specified, intersect with the diff-derived set."""

    class _StubRun:
        def __init__(self) -> None:
            self.calls: list[list[str]] = []

        def __call__(self, args, *, cwd, check, capture_output, text):
            self.calls.append(args)
            return _StubResult(
                stdout="apps/web/src/components/Button.tsx\n" "apps/web/app/api/users/route.ts\n",
            )

    class _StubResult:
        def __init__(self, *, stdout: str = "", returncode: int = 0) -> None:
            self.stdout = stdout
            self.returncode = returncode
            self.stderr = ""

    runner = _StubRun()
    s = select_modules(
        "origin/main",
        intersect_with=frozenset({"functional", "api"}),
        runner=runner,
    )
    assert s.modules == frozenset({"functional", "api"})


def test_changed_files_raises_when_git_missing() -> None:
    def boom(*args, **kwargs):
        raise FileNotFoundError("no git")

    with pytest.raises(GitNotAvailableError):
        changed_files_against("origin/main", runner=boom)


def test_changed_files_raises_on_nonzero_exit() -> None:
    class _R:
        returncode = 128
        stdout = ""
        stderr = "not a git repository"

    def fake(*args, **kwargs):
        return _R()

    with pytest.raises(GitNotAvailableError):
        changed_files_against("origin/main", runner=fake)


def test_changed_files_unions_three_sources() -> None:
    """Diff, unstaged, and untracked outputs must all be unioned."""

    outputs = iter(
        [
            "committed.ts\n",  # diff vs base
            "unstaged.ts\n",  # diff unstaged
            "untracked.ts\n",  # ls-files
        ]
    )

    class _R:
        def __init__(self, stdout: str) -> None:
            self.stdout = stdout
            self.returncode = 0
            self.stderr = ""

    def fake(*args, **kwargs):
        return _R(next(outputs))

    files = changed_files_against("origin/main", runner=fake)
    names = {p.name for p in files}
    assert names == {"committed.ts", "unstaged.ts", "untracked.ts"}

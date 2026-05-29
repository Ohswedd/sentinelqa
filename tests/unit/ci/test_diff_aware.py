"""Unit tests for engine.ci.diff_aware (task 17.05)."""

from __future__ import annotations

from pathlib import Path

import pytest
from engine.ci.diff_aware import (
    DEFAULT_MAX_CHANGED_FILES,
    SMOKE_TAG,
    select_from_files,
    select_from_git,
)


def test_smoke_always_present_when_no_files_changed() -> None:
    sel = select_from_files(diff_range="HEAD~1...HEAD", changed_files=[])
    assert sel.grep() == SMOKE_TAG
    assert sel.fallback_to_full is False


def test_full_fallback_on_lockfile_change() -> None:
    sel = select_from_files(
        diff_range="HEAD~1...HEAD",
        changed_files=["pnpm-lock.yaml", "src/foo.ts"],
    )
    assert sel.fallback_to_full is True
    assert sel.grep() is None
    assert "pnpm-lock.yaml" in sel.reason


def test_full_fallback_on_framework_config() -> None:
    for config_file in ("next.config.ts", "vite.config.ts", "tsconfig.json"):
        sel = select_from_files(diff_range="x", changed_files=[config_file])
        assert sel.fallback_to_full is True, config_file


def test_full_fallback_on_many_files() -> None:
    many = [f"src/file{i}.ts" for i in range(DEFAULT_MAX_CHANGED_FILES + 1)]
    sel = select_from_files(diff_range="x", changed_files=many)
    assert sel.fallback_to_full is True
    assert "threshold" in sel.reason


def test_nextjs_app_router_route_mapping() -> None:
    sel = select_from_files(
        diff_range="x",
        changed_files=["app/dashboard/page.tsx"],
    )
    assert sel.impacted_routes == ("/dashboard",)
    assert sel.fallback_to_full is False
    assert "@route:/dashboard" in sel.tags
    assert SMOKE_TAG in sel.grep().split("|")  # type: ignore[union-attr]


def test_nextjs_app_router_root_page() -> None:
    sel = select_from_files(diff_range="x", changed_files=["app/page.tsx"])
    assert sel.impacted_routes == ("/",)


def test_nextjs_pages_router_route_mapping() -> None:
    sel = select_from_files(
        diff_range="x",
        changed_files=["pages/foo/bar.tsx", "pages/baz/index.tsx"],
    )
    # /foo/bar + /baz (index stripped)
    assert "/foo/bar" in sel.impacted_routes
    assert "/baz" in sel.impacted_routes


def test_vite_routes_dir_mapping() -> None:
    sel = select_from_files(
        diff_range="x",
        changed_files=["src/routes/profile.tsx"],
    )
    assert sel.impacted_routes == ("/profile",)


def test_api_endpoint_mapping() -> None:
    sel = select_from_files(
        diff_range="x",
        changed_files=[
            "app/api/users/route.ts",
            "pages/api/login.ts",
        ],
    )
    assert "/api/users" in sel.impacted_endpoints
    assert "/api/login" in sel.impacted_endpoints
    # Endpoint tags emitted
    assert "@endpoint:/api/users" in sel.tags


def test_openapi_schema_change_impacts_api_module() -> None:
    sel = select_from_files(
        diff_range="x",
        changed_files=["openapi.yaml"],
    )
    assert "@module:api" in sel.tags
    assert sel.fallback_to_full is False


def test_test_file_change_is_recorded() -> None:
    sel = select_from_files(
        diff_range="x",
        changed_files=["tests/sentinel/login.spec.ts"],
    )
    assert "tests/sentinel/login.spec.ts" in sel.impacted_test_files


def test_windows_path_normalization() -> None:
    sel = select_from_files(
        diff_range="x",
        changed_files=["app\\dashboard\\page.tsx"],
    )
    assert sel.impacted_routes == ("/dashboard",)


def test_p1_tag_added_when_any_impact_detected() -> None:
    sel = select_from_files(diff_range="x", changed_files=["app/dashboard/page.tsx"])
    assert "@p1" in sel.tags


def test_to_dict_round_trip() -> None:
    sel = select_from_files(diff_range="HEAD~3...HEAD", changed_files=["app/p/page.tsx"])
    data = sel.to_dict()
    assert data["diff_range"] == "HEAD~3...HEAD"
    assert data["impacted_routes"] == ["/p"]
    assert data["fallback_to_full"] is False


def test_select_from_git_uses_injected_runner(tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_runner(*, diff_range: str, repo_root: Path) -> tuple[str, ...]:
        captured["range"] = diff_range
        captured["root"] = repo_root
        return ("app/x/page.tsx", "src/components/Button.tsx")

    sel = select_from_git(
        diff_range="origin/main...HEAD",
        repo_root=tmp_path,
        runner=fake_runner,
    )
    assert captured["range"] == "origin/main...HEAD"
    assert captured["root"] == tmp_path
    assert "/x" in sel.impacted_routes


def test_select_from_git_raises_on_subprocess_error(tmp_path: Path) -> None:
    def boom(*, diff_range: str, repo_root: Path) -> tuple[str, ...]:
        raise ValueError("invalid range")

    with pytest.raises(ValueError):
        select_from_git(diff_range="garbage", repo_root=tmp_path, runner=boom)


def test_grep_or_combines_smoke_and_impacted_tags() -> None:
    sel = select_from_files(
        diff_range="x",
        changed_files=["app/dashboard/page.tsx", "app/api/users/route.ts"],
    )
    grep = sel.grep()
    assert grep is not None
    parts = set(grep.split("|"))
    assert SMOKE_TAG in parts
    assert "@p1" in parts
    assert "@route:/dashboard" in parts


def test_empty_file_in_input_is_skipped() -> None:
    sel = select_from_files(diff_range="x", changed_files=["", "app/x/page.tsx"])
    assert sel.changed_files == ("app/x/page.tsx",)


def test_duplicates_are_deduped() -> None:
    sel = select_from_files(
        diff_range="x",
        changed_files=["app/x/page.tsx", "app/x/page.tsx"],
    )
    assert sel.changed_files == ("app/x/page.tsx",)
    assert sel.impacted_routes == ("/x",)

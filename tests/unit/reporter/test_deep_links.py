# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for per-finding deep-link rendering."""

from __future__ import annotations

import pytest
from engine.reporter.deep_links import (
    CodeRef,
    DeepLinkConfig,
    bitbucket_link,
    build_links,
    github_link,
    gitlab_link,
    vscode_link,
)


def test_github_link_includes_line_anchor() -> None:
    ref = CodeRef(file="src/main.py", line=42)
    cfg = DeepLinkConfig(host_kind="github", repo="owner/repo", ref="main")
    link = github_link(ref, cfg)
    assert link.label == "GitHub"
    assert link.href == "https://github.com/owner/repo/blob/main/src/main.py#L42"


def test_github_link_includes_column_anchor() -> None:
    ref = CodeRef(file="src/main.py", line=42, column=5)
    cfg = DeepLinkConfig(host_kind="github", repo="owner/repo", ref="main")
    link = github_link(ref, cfg)
    assert link.href.endswith("#L42C5")


def test_github_link_handles_on_prem_host() -> None:
    ref = CodeRef(file="src/main.py", line=1)
    cfg = DeepLinkConfig(
        host_kind="github",
        repo="owner/repo",
        ref="main",
        host_url="https://github.acme.com",
    )
    link = github_link(ref, cfg)
    assert link.href.startswith("https://github.acme.com/")


def test_gitlab_link_uses_dash_segment() -> None:
    ref = CodeRef(file="src/main.py", line=10)
    cfg = DeepLinkConfig(host_kind="gitlab", repo="owner/proj", ref="main")
    link = gitlab_link(ref, cfg)
    assert "/-/blob/" in link.href
    assert link.href.endswith("#L10")


def test_bitbucket_link_uses_lines_anchor() -> None:
    ref = CodeRef(file="src/main.py", line=5)
    cfg = DeepLinkConfig(host_kind="bitbucket", repo="team/repo", ref="main")
    link = bitbucket_link(ref, cfg)
    assert "/src/" in link.href
    assert link.href.endswith("#lines-5")


def test_vscode_link_uses_file_scheme() -> None:
    ref = CodeRef(file="src/main.py", line=10, column=3)
    link = vscode_link(ref, repo_root_absolute="/Users/test/project")
    assert link.label == "VS Code"
    assert link.href == "vscode://file//Users/test/project/src/main.py:10:3"


def test_vscode_link_without_repo_root() -> None:
    ref = CodeRef(file="./src/main.py", line=1)
    link = vscode_link(ref)
    assert link.href == "vscode://file/src/main.py:1"


def test_build_links_returns_host_then_vscode() -> None:
    ref = CodeRef(file="src/main.py", line=1)
    cfg = DeepLinkConfig(host_kind="github", repo="o/r")
    links = build_links(ref, cfg, include_vscode=True)
    assert [link.label for link in links] == ["GitHub", "VS Code"]


def test_build_links_can_skip_vscode() -> None:
    ref = CodeRef(file="src/main.py", line=1)
    cfg = DeepLinkConfig(host_kind="github", repo="o/r")
    links = build_links(ref, cfg, include_vscode=False)
    assert [link.label for link in links] == ["GitHub"]


def test_build_links_for_local_only_returns_just_vscode() -> None:
    ref = CodeRef(file="src/main.py", line=1)
    cfg = DeepLinkConfig(host_kind="local", repo="")
    links = build_links(ref, cfg)
    assert [link.label for link in links] == ["VS Code"]


def test_normalise_strips_leading_slash() -> None:
    ref = CodeRef(file="/src/main.py", line=1)
    cfg = DeepLinkConfig(host_kind="github", repo="o/r")
    link = github_link(ref, cfg)
    assert "blob/main/src/main.py" in link.href
    assert "//src/main.py" not in link.href


def test_normalise_handles_windows_separators() -> None:
    ref = CodeRef(file="src\\main.py", line=1)
    cfg = DeepLinkConfig(host_kind="github", repo="o/r")
    link = github_link(ref, cfg)
    assert "src/main.py" in link.href


def test_coderef_optional_line_skips_anchor() -> None:
    ref = CodeRef(file="src/main.py")
    cfg = DeepLinkConfig(host_kind="github", repo="o/r")
    link = github_link(ref, cfg)
    assert "#" not in link.href


@pytest.mark.parametrize("host_kind", ["github", "gitlab", "bitbucket"])
def test_every_host_renders_without_raising(host_kind: str) -> None:
    cfg = DeepLinkConfig(host_kind=host_kind, repo="o/r", ref="main")  # type: ignore[arg-type]
    ref = CodeRef(file="src/main.py", line=1)
    links = build_links(ref, cfg)
    assert links[0].href.startswith("http")

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Per-finding code-reference deep links (v1.6.0).

When a finding carries a structured :class:`CodeRef` (file + line +
optional column), the reporter can render one or more deep links
that take the reviewer straight to the offending line on the host
(GitHub / GitLab / Bitbucket) or in the local editor
(``vscode://``).

The module is pure: it takes a :class:`CodeRef` and a
:class:`DeepLinkConfig` (the project's git host / branch / repo) and
returns the canonical URL strings. The CLI / reporter is responsible
for wiring the config from ``sentinel.config.yaml`` or env vars.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal
from urllib.parse import quote

HostKind = Literal["github", "gitlab", "bitbucket", "vscode", "local"]


@dataclass(frozen=True, slots=True)
class CodeRef:
    """One file/line/column reference inside the project source tree."""

    file: str
    line: int | None = None
    column: int | None = None


@dataclass(frozen=True, slots=True)
class DeepLinkConfig:
    """Project-wide deep-link configuration."""

    # The git host this project lives on, e.g. ``github.com``.
    host_kind: HostKind
    repo: str  # "owner/name"
    ref: str = "main"  # branch / tag / commit
    # Base URL of the host. The defaults match the public endpoints
    # for github.com / gitlab.com / bitbucket.org; on-prem instances
    # override.
    host_url: str = ""


@dataclass(frozen=True, slots=True)
class DeepLink:
    """One rendered link with a human label."""

    label: str
    href: str


_DEFAULT_HOST_URLS: Final[dict[HostKind, str]] = {
    "github": "https://github.com",
    "gitlab": "https://gitlab.com",
    "bitbucket": "https://bitbucket.org",
    "vscode": "vscode://file",
    "local": "",
}


def _host_url(config: DeepLinkConfig) -> str:
    if config.host_url:
        return config.host_url.rstrip("/")
    return _DEFAULT_HOST_URLS.get(config.host_kind, "")


def _line_anchor_github(line: int | None, column: int | None) -> str:
    if line is None:
        return ""
    if column is not None:
        return f"#L{line}C{column}"
    return f"#L{line}"


def _line_anchor_gitlab(line: int | None, column: int | None) -> str:
    # GitLab uses ``#L<line>`` (and #L<line>-<line> for ranges) — no
    # column anchor; we drop the column.
    _ = column
    return f"#L{line}" if line is not None else ""


def _line_anchor_bitbucket(line: int | None, column: int | None) -> str:
    # Bitbucket Cloud uses ``#lines-<line>``.
    _ = column
    return f"#lines-{line}" if line is not None else ""


def _vscode_fragment(line: int | None, column: int | None) -> str:
    if line is None:
        return ""
    if column is not None:
        return f":{line}:{column}"
    return f":{line}"


def _normalise_path(file: str) -> str:
    """Strip a leading ``./`` and collapse Windows separators."""

    cleaned = file.lstrip("/").replace("\\", "/")
    if cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned


def github_link(ref: CodeRef, config: DeepLinkConfig) -> DeepLink:
    """Render a github.com / GHE link."""

    base = _host_url(config)
    repo = config.repo.strip("/")
    path = _normalise_path(ref.file)
    href = (
        f"{base}/{repo}/blob/{config.ref}/{quote(path)}"
        f"{_line_anchor_github(ref.line, ref.column)}"
    )
    return DeepLink(label="GitHub", href=href)


def gitlab_link(ref: CodeRef, config: DeepLinkConfig) -> DeepLink:
    base = _host_url(config)
    repo = config.repo.strip("/")
    path = _normalise_path(ref.file)
    href = (
        f"{base}/{repo}/-/blob/{config.ref}/{quote(path)}"
        f"{_line_anchor_gitlab(ref.line, ref.column)}"
    )
    return DeepLink(label="GitLab", href=href)


def bitbucket_link(ref: CodeRef, config: DeepLinkConfig) -> DeepLink:
    base = _host_url(config)
    repo = config.repo.strip("/")
    path = _normalise_path(ref.file)
    href = (
        f"{base}/{repo}/src/{config.ref}/{quote(path)}"
        f"{_line_anchor_bitbucket(ref.line, ref.column)}"
    )
    return DeepLink(label="Bitbucket", href=href)


def vscode_link(
    ref: CodeRef,
    *,
    repo_root_absolute: str = "",
) -> DeepLink:
    """Open the file in the user's local VS Code via the ``vscode://`` scheme.

    ``repo_root_absolute`` is the absolute path of the working tree —
    the reporter / CLI substitutes the user's CWD at render time.
    """

    path = _normalise_path(ref.file)
    absolute = f"{repo_root_absolute.rstrip('/')}/{path}" if repo_root_absolute else path
    href = f"vscode://file/{absolute}{_vscode_fragment(ref.line, ref.column)}"
    return DeepLink(label="VS Code", href=href)


def build_links(
    ref: CodeRef,
    config: DeepLinkConfig,
    *,
    include_vscode: bool = True,
    repo_root_absolute: str = "",
) -> tuple[DeepLink, ...]:
    """Return every applicable deep link for ``ref`` under ``config``."""

    links: list[DeepLink] = []
    if config.host_kind == "github":
        links.append(github_link(ref, config))
    elif config.host_kind == "gitlab":
        links.append(gitlab_link(ref, config))
    elif config.host_kind == "bitbucket":
        links.append(bitbucket_link(ref, config))
    if include_vscode:
        links.append(vscode_link(ref, repo_root_absolute=repo_root_absolute))
    return tuple(links)


__all__ = [
    "CodeRef",
    "DeepLink",
    "DeepLinkConfig",
    "HostKind",
    "bitbucket_link",
    "build_links",
    "github_link",
    "gitlab_link",
    "vscode_link",
]

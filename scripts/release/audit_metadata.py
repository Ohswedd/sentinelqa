"""Audit publishable package manifests for SentinelQA.

For every publishable Python distributable (`apps/cli`, `engine`,
`packages/python-sdk`, `packages/mcp-server`) and every publishable TypeScript
package (`packages/ts-runtime`, optionally `packages/shared-schema`), assert
that the manifest carries the metadata a release requires:

Python::

 project.name, project.version, project.description, project.readme,
 project.requires-python, project.license.text == "Apache-2.0",
 project.authors (non-empty, no AI tools),
 project.urls (Homepage / Documentation / Repository / Issues / Changelog),
 project.classifiers (non-empty, includes the Apache-2.0 license trove),
 project.keywords (non-empty).

TypeScript::

 name, version, description, license == "Apache-2.0", repository,
 author (non-empty string or object, no AI tools), keywords (non-empty),
 files (non-empty array).

Internal manifests (the monorepo root, the docs site, examples, the internal
``@sentinelqa/shared-schema`` workspace member) must declare ``private: true``
(TypeScript) or ``tool.uv.package = false`` / live under ``examples/`` (Python)
so the auditor can confidently skip them.

our engineering rules forbids AI tool authorship; AI author names + email domains are
rejected explicitly so a slip can't ride through review.

Exit codes
----------

* 0 — every audited manifest passes.
* 2 — at least one manifest fails the audit (details printed to stderr).
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

# --------------------------------------------------------------------------- #
# Manifest catalogues
# --------------------------------------------------------------------------- #

PUBLISHABLE_PY: tuple[str, ...] = (
    "apps/cli/pyproject.toml",
    "engine/pyproject.toml",
    "modules/pyproject.toml",
    "integrations/pyproject.toml",
    "packages/python-sdk/pyproject.toml",
    "packages/mcp-server/pyproject.toml",
)

PUBLISHABLE_TS: tuple[str, ...] = ("packages/ts-runtime/package.json",)

INTERNAL_PY: tuple[str, ...] = (
    "pyproject.toml",  # monorepo root (tool.uv.package = false)
    "examples/plugins/sentinelqa-reporter-example/pyproject.toml",
    "examples/plugins/sentinelqa-scanner-example/pyproject.toml",
)

INTERNAL_TS: tuple[str, ...] = (
    "package.json",  # monorepo root
    "apps/docs/package.json",
    "apps/vscode-extension/package.json",  # ships via VS Code Marketplace, not npm
    "apps/browser-extension/package.json",  # ships via Chrome / Firefox stores, not npm
    "packages/shared-schema/package.json",
    "examples/nextjs/package.json",
    "examples/llm-broken/package.json",
    "examples/react-vite/package.json",
)

REQUIRED_PY_URL_KEYS: tuple[str, ...] = (
    "Homepage",
    "Documentation",
    "Repository",
    "Issues",
    "Changelog",
)

REQUIRED_TROVE_LICENSE = "License :: OSI Approved :: Apache Software License"

# --------------------------------------------------------------------------- #
# AI authorship deny-list
# --------------------------------------------------------------------------- #

AI_AUTHOR_NAMES: frozenset[str] = frozenset(
    {
        "anthropic",
        "claude",
        "openai",
        "gpt",
        "chatgpt",
        "cursor",
        "copilot",
        "github copilot",
        "codex",
        "bard",
        "gemini",
        "llama",
        "deepseek",
    }
)

AI_AUTHOR_DOMAINS: frozenset[str] = frozenset(
    {
        "anthropic.com",
        "openai.com",
        "githubcopilot.com",
        "cursor.so",
        "cursor.sh",
        "anthropic.ai",
    }
)


# --------------------------------------------------------------------------- #
# Result types
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class AuditFailure:
    manifest: str
    message: str

    def render(self) -> str:
        return f"  - {self.manifest}: {self.message}"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as fh:
        return tomllib.load(fh)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_ai_author(name: str | None, email: str | None) -> bool:
    if name:
        lowered = name.strip().lower()
        if any(banned in lowered for banned in AI_AUTHOR_NAMES):
            return True
    if email:
        at = email.rfind("@")
        if at >= 0:
            domain = email[at + 1 :].strip().lower()
            if domain in AI_AUTHOR_DOMAINS:
                return True
    return False


def _format_author_repr(author: Any) -> str:
    if isinstance(author, dict):
        name = author.get("name") or ""
        email = author.get("email") or ""
        return f"{name} <{email}>" if email else name
    return str(author)


# --------------------------------------------------------------------------- #
# Per-manifest auditors
# --------------------------------------------------------------------------- #


def audit_publishable_python(rel_path: str, *, root: Path = REPO_ROOT) -> list[AuditFailure]:
    fails: list[AuditFailure] = []
    path = root / rel_path
    if not path.is_file():
        return [AuditFailure(rel_path, "manifest file missing")]
    data = _load_toml(path)
    project = data.get("project")
    if not isinstance(project, dict):
        return [AuditFailure(rel_path, "missing [project] table")]

    # Required scalar fields.
    for field in ("name", "version", "description", "readme", "requires-python"):
        if not project.get(field):
            fails.append(AuditFailure(rel_path, f"missing required field: project.{field}"))

    # License.
    lic = project.get("license")
    if isinstance(lic, dict):
        if lic.get("text") != "Apache-2.0":
            fails.append(
                AuditFailure(
                    rel_path,
                    f'project.license.text must be "Apache-2.0", got {lic.get("text")!r}',
                )
            )
    else:
        fails.append(
            AuditFailure(rel_path, 'project.license must be a table with `text = "Apache-2.0"`')
        )

    # Authors (non-empty, no AI).
    authors = project.get("authors")
    if not isinstance(authors, list) or not authors:
        fails.append(AuditFailure(rel_path, "project.authors must be a non-empty array"))
    else:
        for author in authors:
            name = author.get("name") if isinstance(author, dict) else None
            email = author.get("email") if isinstance(author, dict) else None
            if _is_ai_author(name, email):
                fails.append(
                    AuditFailure(
                        rel_path,
                        f"AI author rejected: {_format_author_repr(author)}",
                    )
                )

    # URLs.
    urls = project.get("urls")
    if not isinstance(urls, dict):
        fails.append(
            AuditFailure(
                rel_path,
                "project.urls must be a table with Homepage/Documentation/"
                "Repository/Issues/Changelog",
            )
        )
    else:
        for key in REQUIRED_PY_URL_KEYS:
            value = urls.get(key)
            if not value:
                fails.append(AuditFailure(rel_path, f"missing project.urls.{key}"))
                continue
            if not isinstance(value, str) or not value.startswith(("https://", "http://")):
                fails.append(
                    AuditFailure(
                        rel_path,
                        f"project.urls.{key} must be an absolute http(s) URL (got {value!r})",
                    )
                )

    # Classifiers.
    classifiers = project.get("classifiers")
    if not isinstance(classifiers, list) or not classifiers:
        fails.append(AuditFailure(rel_path, "project.classifiers must be a non-empty array"))
    elif REQUIRED_TROVE_LICENSE not in classifiers:
        fails.append(
            AuditFailure(
                rel_path,
                f'project.classifiers must include "{REQUIRED_TROVE_LICENSE}"',
            )
        )

    # Keywords.
    keywords = project.get("keywords")
    if not isinstance(keywords, list) or not keywords:
        fails.append(AuditFailure(rel_path, "project.keywords must be a non-empty array"))

    return fails


def audit_internal_python(rel_path: str, *, root: Path = REPO_ROOT) -> list[AuditFailure]:
    fails: list[AuditFailure] = []
    path = root / rel_path
    if not path.is_file():
        return [AuditFailure(rel_path, "manifest file missing")]
    data = _load_toml(path)
    project = data.get("project")

    # Either tool.uv.package == false (root) OR the file lives under examples/.
    uv_pkg = data.get("tool", {}).get("uv", {}).get("package")
    is_root = rel_path == "pyproject.toml"
    is_example = rel_path.startswith("examples/")

    if is_root and uv_pkg is not False:
        fails.append(AuditFailure(rel_path, "root manifest must declare tool.uv.package = false"))

    if not is_root and not is_example:
        fails.append(
            AuditFailure(
                rel_path,
                "internal manifest not under examples/ — add it to INTERNAL_PY or PUBLISHABLE_PY",
            )
        )

    # AI-author check still applies — even internal manifests must not credit AI.
    if isinstance(project, dict):
        for author in project.get("authors") or []:
            name = author.get("name") if isinstance(author, dict) else None
            email = author.get("email") if isinstance(author, dict) else None
            if _is_ai_author(name, email):
                fails.append(
                    AuditFailure(
                        rel_path,
                        f"AI author rejected: {_format_author_repr(author)}",
                    )
                )

    return fails


def audit_publishable_ts(rel_path: str, *, root: Path = REPO_ROOT) -> list[AuditFailure]:
    fails: list[AuditFailure] = []
    path = root / rel_path
    if not path.is_file():
        return [AuditFailure(rel_path, "manifest file missing")]
    data = _load_json(path)

    # Required scalar fields.
    for field in ("name", "version", "description"):
        if not data.get(field):
            fails.append(AuditFailure(rel_path, f"missing required field: {field}"))

    # License.
    if data.get("license") != "Apache-2.0":
        fails.append(
            AuditFailure(
                rel_path,
                f'license must be "Apache-2.0", got {data.get("license")!r}',
            )
        )

    # Repository (object or string).
    repo = data.get("repository")
    if isinstance(repo, dict):
        url = repo.get("url")
    elif isinstance(repo, str):
        url = repo
    else:
        url = None
    if not url:
        fails.append(AuditFailure(rel_path, "missing repository.url"))

    # Author (string or object). Reject AI.
    author = data.get("author")
    if not author:
        fails.append(AuditFailure(rel_path, "missing author"))
    else:
        if isinstance(author, dict):
            name = author.get("name")
            email = author.get("email")
        else:
            # "Name <email>" or just "Name"
            text = str(author)
            name = text
            email = None
            if "<" in text and ">" in text:
                email = text.split("<", 1)[1].split(">", 1)[0].strip() or None
                name = text.split("<", 1)[0].strip()
        if _is_ai_author(name, email):
            fails.append(AuditFailure(rel_path, f"AI author rejected: {author!r}"))

    # Keywords (non-empty array).
    keywords = data.get("keywords")
    if not isinstance(keywords, list) or not keywords:
        fails.append(AuditFailure(rel_path, "keywords must be a non-empty array"))

    # Files (non-empty array — publish whitelist).
    files = data.get("files")
    if not isinstance(files, list) or not files:
        fails.append(AuditFailure(rel_path, "files must be a non-empty array (publish whitelist)"))

    return fails


def audit_internal_ts(rel_path: str, *, root: Path = REPO_ROOT) -> list[AuditFailure]:
    fails: list[AuditFailure] = []
    path = root / rel_path
    if not path.is_file():
        return [AuditFailure(rel_path, "manifest file missing")]
    data = _load_json(path)
    if data.get("private") is not True:
        fails.append(
            AuditFailure(
                rel_path,
                'internal manifest must declare `"private": true` to opt out of publishing',
            )
        )
    # AI-author check.
    author = data.get("author")
    if author:
        if isinstance(author, dict):
            name = author.get("name")
            email = author.get("email")
        else:
            text = str(author)
            name = text
            email = None
            if "<" in text and ">" in text:
                email = text.split("<", 1)[1].split(">", 1)[0].strip() or None
                name = text.split("<", 1)[0].strip()
        if _is_ai_author(name, email):
            fails.append(AuditFailure(rel_path, f"AI author rejected: {author!r}"))
    return fails


# --------------------------------------------------------------------------- #
# Top-level driver
# --------------------------------------------------------------------------- #


def run_audit(*, root: Path = REPO_ROOT) -> list[AuditFailure]:
    failures: list[AuditFailure] = []
    for rel in PUBLISHABLE_PY:
        failures.extend(audit_publishable_python(rel, root=root))
    for rel in INTERNAL_PY:
        failures.extend(audit_internal_python(rel, root=root))
    for rel in PUBLISHABLE_TS:
        failures.extend(audit_publishable_ts(rel, root=root))
    for rel in INTERNAL_TS:
        failures.extend(audit_internal_ts(rel, root=root))
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit SentinelQA package metadata.")
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root (defaults to the repo containing this script).",
    )
    args = parser.parse_args(argv)

    failures = run_audit(root=args.root)
    if not failures:
        n = len(PUBLISHABLE_PY) + len(PUBLISHABLE_TS) + len(INTERNAL_PY) + len(INTERNAL_TS)
        sys.stdout.write(f"audit-metadata: ok — {n} manifests audited\n")
        return 0

    sys.stderr.write(f"audit-metadata: {len(failures)} failure(s):\n")
    for f in failures:
        sys.stderr.write(f.render() + "\n")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

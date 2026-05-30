"""Regression tests for ``scripts/release/audit_metadata.py``.

This is the Phase 28 task 28.03 acceptance gate: every publishable manifest
must carry release-ready metadata at every CI run, and every internal manifest
must opt out of publishing.

The tests run on the live repo (so a future polish that drops a required field
will fail loud) plus a handful of synthetic-fixture tests to prove the auditor
catches what the spec says it catches.
"""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _ensure_scripts_on_path() -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(autouse=True)
def _path() -> None:
    _ensure_scripts_on_path()


# --------------------------------------------------------------------------- #
# Live-repo audit — must pass on every CI run.
# --------------------------------------------------------------------------- #


def test_live_repo_audit_is_clean() -> None:
    from scripts.release.audit_metadata import run_audit

    failures = run_audit()
    assert failures == [], "live repo audit failed:\n" + "\n".join(f.render() for f in failures)


def test_audit_catalogue_is_exhaustive() -> None:
    """Every Python and TypeScript manifest under the repo must be classified
    as either publishable or internal — no surprises."""
    from scripts.release.audit_metadata import (
        INTERNAL_PY,
        INTERNAL_TS,
        PUBLISHABLE_PY,
        PUBLISHABLE_TS,
    )

    catalogued = set(PUBLISHABLE_PY) | set(INTERNAL_PY) | set(PUBLISHABLE_TS) | set(INTERNAL_TS)

    seen: set[str] = set()
    for name in ("pyproject.toml", "package.json"):
        for path in REPO_ROOT.rglob(name):
            rel = path.relative_to(REPO_ROOT).as_posix()
            # Skip vendored / build artefacts.
            if "node_modules/" in rel or "dist/" in rel or ".venv/" in rel:
                continue
            seen.add(rel)

    missing = sorted(seen - catalogued)
    assert not missing, (
        "uncatalogued manifests — add them to PUBLISHABLE_* or INTERNAL_* in"
        " scripts/release/audit_metadata.py:\n" + "\n".join(f"  - {m}" for m in missing)
    )


# --------------------------------------------------------------------------- #
# Per-manifest field presence — live repo.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "rel_path",
    [
        "apps/cli/pyproject.toml",
        "engine/pyproject.toml",
        "modules/pyproject.toml",
        "integrations/pyproject.toml",
        "packages/python-sdk/pyproject.toml",
        "packages/mcp-server/pyproject.toml",
    ],
)
def test_python_publishable_has_full_metadata(rel_path: str) -> None:
    import tomllib

    data = tomllib.loads((REPO_ROOT / rel_path).read_text(encoding="utf-8"))
    project = data["project"]

    assert project["license"] == {"text": "Apache-2.0"}
    assert project["requires-python"].startswith(">=3.11")
    assert project["authors"], "authors must be non-empty"
    assert project["keywords"], "keywords must be non-empty"
    assert project["classifiers"], "classifiers must be non-empty"
    assert "License :: OSI Approved :: Apache Software License" in project["classifiers"]
    urls = project["urls"]
    for key in ("Homepage", "Documentation", "Repository", "Issues", "Changelog"):
        assert urls[key].startswith("https://github.com/Ohswedd/sentinelqa")


def test_ts_publishable_has_full_metadata() -> None:
    data = json.loads(
        (REPO_ROOT / "packages" / "ts-runtime" / "package.json").read_text(encoding="utf-8")
    )
    assert data["license"] == "Apache-2.0"
    assert data["author"]
    assert data["keywords"]
    assert data["files"]
    repo = data["repository"]
    assert repo["url"].endswith("sentinelqa.git")
    assert repo["directory"] == "packages/ts-runtime"


@pytest.mark.parametrize(
    "rel_path",
    [
        "package.json",
        "apps/docs/package.json",
        "packages/shared-schema/package.json",
        "examples/nextjs/package.json",
        "examples/llm-broken/package.json",
        "examples/react-vite/package.json",
    ],
)
def test_internal_ts_declares_private(rel_path: str) -> None:
    data = json.loads((REPO_ROOT / rel_path).read_text(encoding="utf-8"))
    assert data.get("private") is True, f'{rel_path} must declare "private": true'


# --------------------------------------------------------------------------- #
# Auditor unit tests — synthetic fixtures.
# --------------------------------------------------------------------------- #


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body).lstrip("\n"), encoding="utf-8")


def test_auditor_flags_missing_url_on_publishable_python(tmp_path: Path) -> None:
    from scripts.release.audit_metadata import audit_publishable_python

    _write(
        tmp_path / "apps/cli/pyproject.toml",
        """
        [project]
        name = "sentinelqa-cli"
        version = "0.1.0"
        description = "test"
        readme = "README.md"
        requires-python = ">=3.11"
        license = { text = "Apache-2.0" }
        authors = [{ name = "ohswedd" }]
        keywords = ["x"]
        classifiers = ["License :: OSI Approved :: Apache Software License"]
        """,
    )
    fails = audit_publishable_python("apps/cli/pyproject.toml", root=tmp_path)
    messages = [f.message for f in fails]
    assert any("project.urls" in m for m in messages)


def test_auditor_flags_non_apache_license(tmp_path: Path) -> None:
    from scripts.release.audit_metadata import audit_publishable_python

    _write(
        tmp_path / "apps/cli/pyproject.toml",
        """
        [project]
        name = "sentinelqa-cli"
        version = "0.1.0"
        description = "test"
        readme = "README.md"
        requires-python = ">=3.11"
        license = { text = "MIT" }
        authors = [{ name = "ohswedd" }]
        keywords = ["x"]
        classifiers = ["License :: OSI Approved :: Apache Software License"]
        [project.urls]
        Homepage = "https://github.com/Ohswedd/sentinelqa"
        Documentation = "https://github.com/Ohswedd/sentinelqa"
        Repository = "https://github.com/Ohswedd/sentinelqa"
        Issues = "https://github.com/Ohswedd/sentinelqa/issues"
        Changelog = "https://github.com/Ohswedd/sentinelqa/blob/main/CHANGELOG.md"
        """,
    )
    fails = audit_publishable_python("apps/cli/pyproject.toml", root=tmp_path)
    assert any("Apache-2.0" in f.message for f in fails)


def test_auditor_rejects_ai_author_in_python_manifest(tmp_path: Path) -> None:
    from scripts.release.audit_metadata import audit_publishable_python

    _write(
        tmp_path / "apps/cli/pyproject.toml",
        """
        [project]
        name = "sentinelqa-cli"
        version = "0.1.0"
        description = "test"
        readme = "README.md"
        requires-python = ">=3.11"
        license = { text = "Apache-2.0" }
        authors = [
            { name = "ohswedd" },
            { name = "Claude", email = "noreply@anthropic.com" },
        ]
        keywords = ["x"]
        classifiers = ["License :: OSI Approved :: Apache Software License"]
        [project.urls]
        Homepage = "https://github.com/Ohswedd/sentinelqa"
        Documentation = "https://github.com/Ohswedd/sentinelqa"
        Repository = "https://github.com/Ohswedd/sentinelqa"
        Issues = "https://github.com/Ohswedd/sentinelqa/issues"
        Changelog = "https://github.com/Ohswedd/sentinelqa/blob/main/CHANGELOG.md"
        """,
    )
    fails = audit_publishable_python("apps/cli/pyproject.toml", root=tmp_path)
    assert any("AI author rejected" in f.message for f in fails)


def test_auditor_rejects_ai_author_in_ts_manifest(tmp_path: Path) -> None:
    from scripts.release.audit_metadata import audit_publishable_ts

    _write(
        tmp_path / "packages/ts-runtime/package.json",
        json.dumps(
            {
                "name": "@sentinelqa/ts-runtime",
                "version": "0.0.0",
                "description": "x",
                "license": "Apache-2.0",
                "author": "OpenAI <support@openai.com>",
                "repository": {"type": "git", "url": "git+https://github.com/o/x.git"},
                "keywords": ["x"],
                "files": ["dist/**"],
            }
        ),
    )
    fails = audit_publishable_ts("packages/ts-runtime/package.json", root=tmp_path)
    assert any("AI author rejected" in f.message for f in fails)


def test_auditor_flags_missing_files_array(tmp_path: Path) -> None:
    from scripts.release.audit_metadata import audit_publishable_ts

    _write(
        tmp_path / "packages/ts-runtime/package.json",
        json.dumps(
            {
                "name": "@sentinelqa/ts-runtime",
                "version": "0.0.0",
                "description": "x",
                "license": "Apache-2.0",
                "author": "ohswedd",
                "repository": {"type": "git", "url": "git+https://github.com/o/x.git"},
                "keywords": ["x"],
            }
        ),
    )
    fails = audit_publishable_ts("packages/ts-runtime/package.json", root=tmp_path)
    assert any("publish whitelist" in f.message for f in fails)


def test_auditor_flags_internal_ts_missing_private(tmp_path: Path) -> None:
    from scripts.release.audit_metadata import audit_internal_ts

    _write(
        tmp_path / "apps/docs/package.json",
        json.dumps(
            {
                "name": "@sentinelqa/docs",
                "version": "0.1.0",
                "description": "x",
            }
        ),
    )
    fails = audit_internal_ts("apps/docs/package.json", root=tmp_path)
    assert any("private" in f.message for f in fails)


def test_auditor_passes_on_clean_publishable_python(tmp_path: Path) -> None:
    from scripts.release.audit_metadata import audit_publishable_python

    _write(
        tmp_path / "apps/cli/pyproject.toml",
        """
        [project]
        name = "sentinelqa-cli"
        version = "0.1.0"
        description = "test"
        readme = "README.md"
        requires-python = ">=3.11"
        license = { text = "Apache-2.0" }
        authors = [{ name = "ohswedd" }]
        keywords = ["x"]
        classifiers = ["License :: OSI Approved :: Apache Software License"]
        [project.urls]
        Homepage = "https://github.com/Ohswedd/sentinelqa"
        Documentation = "https://github.com/Ohswedd/sentinelqa"
        Repository = "https://github.com/Ohswedd/sentinelqa"
        Issues = "https://github.com/Ohswedd/sentinelqa/issues"
        Changelog = "https://github.com/Ohswedd/sentinelqa/blob/main/CHANGELOG.md"
        """,
    )
    assert audit_publishable_python("apps/cli/pyproject.toml", root=tmp_path) == []

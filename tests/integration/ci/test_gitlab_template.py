"""Structural tests for the GitLab CI include (task 17.02)."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = REPO_ROOT / "integrations" / "gitlab" / ".gitlab-ci.sentinel.yml"
README = REPO_ROOT / "integrations" / "gitlab" / "README.md"


def _load() -> dict:
    payload = yaml.safe_load(TEMPLATE.read_text())
    assert isinstance(payload, dict)
    return payload


def test_template_exists() -> None:
    assert TEMPLATE.is_file()
    assert README.is_file()


def test_template_declares_template_job() -> None:
    payload = _load()
    assert ".sentinelqa" in payload, "missing `.sentinelqa` template job"
    job = payload[".sentinelqa"]
    assert "script" in job and "before_script" in job and "after_script" in job
    # The job must enforce SENTINELQA_URL — empty URL means refusal (PRD §2).
    body = "\n".join(job["script"])
    assert "SENTINELQA_URL" in body
    assert "exit 4" in body, "must exit 4 when URL missing (PRD §2)"


def test_template_runs_sentinel_ci_with_required_flags() -> None:
    job = _load()[".sentinelqa"]
    body = "\n".join(job["script"])
    assert "sentinel ci" in body
    assert "--ci" in body
    assert "--mode" in body
    assert "--url" in body


def test_template_uploads_required_artifacts() -> None:
    job = _load()[".sentinelqa"]
    artifacts = job["artifacts"]
    paths = artifacts["paths"]
    required_globs = {
        ".sentinel/runs/*/run.json",
        ".sentinel/runs/*/findings.json",
        ".sentinel/runs/*/score.json",
        ".sentinel/runs/*/report.html",
        ".sentinel/runs/*/report.md",
        ".sentinel/runs/*/sarif.json",
        ".sentinel/runs/*/junit.xml",
    }
    assert required_globs.issubset(set(paths))
    reports = artifacts["reports"]
    assert "junit" in reports
    assert "codequality" in reports


def test_template_includes_caching() -> None:
    job = _load()[".sentinelqa"]
    cache = job["cache"]
    paths = set(cache["paths"])
    assert ".cache/pip" in paths
    assert ".cache/pnpm" in paths
    assert "node_modules/" in paths


def test_template_never_logs_tokens() -> None:
    raw = TEMPLATE.read_text()
    assert "echo $SENTINELQA_GITLAB_TOKEN" not in raw
    assert 'echo "$SENTINELQA_GITLAB_TOKEN"' not in raw
    assert "echo ${SENTINELQA_GITLAB_TOKEN}" not in raw


def test_template_rules_run_on_mr_and_default_branch() -> None:
    job = _load()[".sentinelqa"]
    rules = job["rules"]
    # PyYAML may parse "$" expressions as strings; we just check keys.
    has_mr = any("CI_MERGE_REQUEST_IID" in (r.get("if", "")) for r in rules)
    has_default = any("CI_DEFAULT_BRANCH" in (r.get("if", "")) for r in rules)
    assert has_mr and has_default

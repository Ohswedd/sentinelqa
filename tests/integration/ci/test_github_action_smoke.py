"""Smoke tests for the GitHub composite action.

The Action lives at ``integrations/github/action.yml`` and is invoked by
the reusable workflow under ``integrations/github/workflows/``. The
smoke target on the example Next.js app lands in;
this test enforces the structural contract here so the YAML can never
drift away from our product spec1.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
ACTION_YAML = REPO_ROOT / "integrations" / "github" / "action.yml"
REUSABLE_WORKFLOW = REPO_ROOT / "integrations" / "github" / "workflows" / "sentinel-pr.yml"


def _load(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text())
    assert isinstance(payload, dict), f"{path}: top-level must be a mapping"
    return payload


def test_action_yaml_exists() -> None:
    assert ACTION_YAML.is_file(), "integrations/github/action.yml is missing"


def test_action_yaml_metadata_branding() -> None:
    action = _load(ACTION_YAML)
    assert action["name"] == "SentinelQA"
    assert action["description"].startswith("Run SentinelQA")
    branding = action["branding"]
    assert branding["icon"] == "shield"
    assert branding["color"] in {"blue", "green", "red", "purple"}


def test_action_yaml_inputs_match_prd() -> None:
    action = _load(ACTION_YAML)
    inputs = action["inputs"]
    required_inputs = {"url", "config", "mode", "fail-under", "diff"}
    assert required_inputs.issubset(
        inputs.keys()
    ), f"missing inputs: {required_inputs - inputs.keys()}"
    assert inputs["url"]["required"] is True
    assert inputs["config"]["default"] == "sentinel.config.yaml"
    assert inputs["mode"]["default"] == "standard"


def test_action_yaml_outputs_present() -> None:
    action = _load(ACTION_YAML)
    outputs = action["outputs"]
    assert {"quality-score", "release-decision", "report-html-url"} == set(outputs.keys())


def test_action_yaml_composite_steps_cover_lifecycle() -> None:
    action = _load(ACTION_YAML)
    runs = action["runs"]
    assert runs["using"] == "composite"
    steps = runs["steps"]
    step_uses = {step.get("uses", "") for step in steps if "uses" in step}
    step_names = {step.get("name", "") for step in steps if "name" in step}
    # Python + Node setup (cached pip)
    assert any(u.startswith("actions/setup-python@v") for u in step_uses)
    assert any(u.startswith("actions/setup-node@v") for u in step_uses)
    # Install SentinelQA + Playwright + run + artifacts + SARIF
    assert "Install SentinelQA" in step_names
    assert any("Playwright" in n for n in step_names)
    assert any("sentinel ci" in n for n in step_names)
    assert any(u.startswith("actions/upload-artifact@v") for u in step_uses)
    assert any("codeql-action/upload-sarif" in u for u in step_uses)


def test_action_yaml_run_step_uses_ci_flag() -> None:
    action = _load(ACTION_YAML)
    run_steps = [s for s in action["runs"]["steps"] if "sentinel ci" in s.get("name", "")]
    assert len(run_steps) == 1
    body = run_steps[0]["run"]
    assert "sentinel ci" in body
    assert "--ci" in body
    assert "--mode" in body
    assert "--url" in body
    assert "--diff" in body
    assert "--fail-under" in body


@pytest.mark.parametrize(
    "field",
    [
        "GITHUB_TOKEN",
        "SECRET",
        "API_KEY",
    ],
)
def test_action_yaml_never_logs_secrets(field: str) -> None:
    """the engineering guidelines: tokens must never be echoed by the Action body."""

    raw = ACTION_YAML.read_text()
    # We allow `secrets.GITHUB_TOKEN` references in caller workflows but
    # never in the composite action body. The composite action body must
    # not contain `echo $TOKEN`-style leakage either.
    forbidden = f"echo ${field}"
    assert forbidden not in raw, f"action.yml must never echo {field}"


def test_reusable_workflow_exists_and_calls_action() -> None:
    assert REUSABLE_WORKFLOW.is_file()
    workflow = _load(REUSABLE_WORKFLOW)
    on_block = workflow.get("on") or workflow.get(True)  # PyYAML maps `on` to True
    assert on_block is not None
    assert "workflow_call" in on_block
    jobs = workflow["jobs"]
    assert len(jobs) == 1
    job = next(iter(jobs.values()))
    step_uses = [step.get("uses", "") for step in job["steps"]]
    assert "./integrations/github" in step_uses

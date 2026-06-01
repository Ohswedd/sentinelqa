# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Structural tests for the v1.5.0 CI templates.

Each template needs to:

- parse cleanly as YAML (or, for Jenkins, exist as a non-empty
  Groovy file with the right entry-point shape);
- contain the `sentinel ci` invocation;
- pin the SENTINELQA_URL gate;
- declare run-artifact persistence.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]

BITBUCKET_TEMPLATE = REPO_ROOT / "integrations" / "bitbucket" / "bitbucket-pipelines.sentinel.yml"
AZURE_TEMPLATE = REPO_ROOT / "integrations" / "azure_devops" / "azure-pipelines.sentinel.yml"
CIRCLECI_ORB = REPO_ROOT / "integrations" / "circleci" / "orb.yml"
JENKINS_STEP = REPO_ROOT / "integrations" / "jenkins" / "vars" / "sentinelAudit.groovy"


# --------------------------------------------------------------------------- #
# Existence
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "path",
    [
        BITBUCKET_TEMPLATE,
        AZURE_TEMPLATE,
        CIRCLECI_ORB,
        JENKINS_STEP,
    ],
)
def test_template_exists(path: Path) -> None:
    assert path.is_file(), f"{path} must ship as part of integrations/"
    assert path.stat().st_size > 256


# --------------------------------------------------------------------------- #
# YAML parses cleanly
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "path",
    [BITBUCKET_TEMPLATE, AZURE_TEMPLATE, CIRCLECI_ORB],
)
def test_yaml_parses_without_errors(path: Path) -> None:
    yaml.safe_load(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Bitbucket: contains the canonical step block
# --------------------------------------------------------------------------- #


def test_bitbucket_template_calls_sentinel_ci() -> None:
    body = BITBUCKET_TEMPLATE.read_text(encoding="utf-8")
    assert "sentinel ci" in body
    assert "SENTINELQA_URL" in body
    assert "playwright install" in body
    assert ".sentinel/runs" in body


def test_bitbucket_template_refuses_empty_url() -> None:
    body = BITBUCKET_TEMPLATE.read_text(encoding="utf-8")
    # The shell guard must abort the run when no URL was provided.
    assert "exit 4" in body
    assert "SENTINELQA_URL" in body


# --------------------------------------------------------------------------- #
# Azure DevOps: stage / job / template params + sentinel ci
# --------------------------------------------------------------------------- #


def test_azure_template_declares_stage_and_job() -> None:
    payload = yaml.safe_load(AZURE_TEMPLATE.read_text(encoding="utf-8"))
    stages = payload.get("stages") or []
    assert stages, "Azure DevOps template must declare a `stages:` block."
    sentinel_stage = next(
        (s for s in stages if s.get("stage", "").lower().startswith("sentinel")),
        None,
    )
    assert sentinel_stage is not None
    jobs = sentinel_stage.get("jobs") or []
    assert jobs, "Stage must declare at least one job."


def test_azure_template_calls_sentinel_ci_and_publishes_artifacts() -> None:
    body = AZURE_TEMPLATE.read_text(encoding="utf-8")
    assert "sentinel ci" in body
    assert "PublishBuildArtifacts" in body
    assert ".sentinel/runs" in body


# --------------------------------------------------------------------------- #
# CircleCI orb: commands + job + sentinel ci
# --------------------------------------------------------------------------- #


def test_circleci_orb_declares_install_and_audit_commands() -> None:
    payload = yaml.safe_load(CIRCLECI_ORB.read_text(encoding="utf-8"))
    commands = payload.get("commands") or {}
    assert "install_sentinelqa" in commands
    assert "run_audit" in commands
    assert "publish_artifacts" in commands


def test_circleci_orb_declares_audit_job() -> None:
    payload = yaml.safe_load(CIRCLECI_ORB.read_text(encoding="utf-8"))
    jobs = payload.get("jobs") or {}
    assert "audit" in jobs
    body = CIRCLECI_ORB.read_text(encoding="utf-8")
    assert "sentinel ci" in body


# --------------------------------------------------------------------------- #
# Jenkins: shared library step
# --------------------------------------------------------------------------- #


def test_jenkins_step_declares_call_entry_point() -> None:
    body = JENKINS_STEP.read_text(encoding="utf-8")
    assert "def call(" in body
    assert "sentinel ci" in body
    assert "archiveArtifacts" in body
    assert "junit" in body


def test_jenkins_step_refuses_empty_url() -> None:
    body = JENKINS_STEP.read_text(encoding="utf-8")
    assert "url?.trim()" in body or "url == null" in body
    assert "error" in body

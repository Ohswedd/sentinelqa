# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Docs-deploy workflow health (Phase 35.04).

Asserts `.github/workflows/docs-deploy.yml` is well-formed against
the subset of the GitHub Actions schema we care about: triggers,
permissions, the named build/deploy job, the Cloudflare action
pin, the fork-secrets fallback, and the docs-deploy.md operator
reference.

We deliberately do not pull the full GH-Actions JSON Schema from
the internet at test time — the keys we pin here are the contract
the workflow promises to the operator, not the upstream syntactic
surface.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "docs-deploy.yml"
OPERATOR_DOC = REPO_ROOT / "docs" / "dev" / "docs-deploy.md"


def _load() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_workflow_file_present() -> None:
    assert WORKFLOW.is_file(), f"workflow missing at {WORKFLOW}"


def test_workflow_top_level_keys() -> None:
    data = _load()
    assert data["name"] == "Docs deploy"
    # YAML's `on:` key is loaded as the Python boolean True by
    # safe_load (because `on` is a YAML 1.1 truthy token). Accept
    # either form so the test survives a YAML 1.2 loader upgrade.
    triggers = data.get("on") or data.get(True)
    assert triggers, "workflow must declare `on:` triggers."
    assert "push" in triggers and "pull_request" in triggers


def test_workflow_triggers_on_main_pushes_and_prs() -> None:
    data = _load()
    triggers = data.get("on") or data.get(True)
    push = triggers["push"]
    assert push["branches"] == ["main"]
    # Path filter must cover docs + lockfiles so unrelated commits
    # don't re-deploy.
    assert any("apps/docs" in p for p in push["paths"])
    assert any("pnpm-lock.yaml" in p for p in push["paths"])


def test_workflow_least_privilege_permissions() -> None:
    data = _load()
    perms = data["permissions"]
    # We need `contents: read` to checkout, `pull-requests: write`
    # for the preview-URL comment, `deployments: write` so the
    # Cloudflare action can post the deployment status. Nothing
    # else.
    assert perms["contents"] == "read"
    assert perms.get("pull-requests") == "write"
    assert perms.get("deployments") == "write"
    forbidden = {"actions", "checks", "issues", "packages", "security-events"}
    assert not (
        forbidden & set(perms)
    ), f"docs-deploy.yml asks for write on more scopes than necessary: {set(perms)}"


def test_workflow_has_named_job_with_required_steps() -> None:
    data = _load()
    jobs = data["jobs"]
    assert "build-and-deploy" in jobs
    job = jobs["build-and-deploy"]
    assert job["name"] == "docs deploy (Cloudflare Pages)"
    step_names = [s.get("name", "") for s in job["steps"]]
    required = [
        "Checkout",
        "Set up uv (with cache)",
        "Install Python 3.12",
        "Set up pnpm",
        "Set up Node 20 (with pnpm cache)",
        "Regenerate docs + build site",
        "Detect deploy secrets",
        "Deploy to Cloudflare Pages",
    ]
    missing = [name for name in required if name not in step_names]
    assert not missing, f"docs-deploy.yml missing steps: {missing}"


def test_cloudflare_action_pinned() -> None:
    data = _load()
    job = data["jobs"]["build-and-deploy"]
    deploy_step = next(s for s in job["steps"] if s.get("name") == "Deploy to Cloudflare Pages")
    assert deploy_step["uses"].startswith(
        "cloudflare/wrangler-action@"
    ), "deploy step must use the official cloudflare/wrangler-action."
    # The action must be version-pinned (not `@main` / `@latest`) so
    # supply-chain changes upstream cannot break us silently.
    version = deploy_step["uses"].split("@", 1)[1]
    assert version not in {
        "main",
        "latest",
    }, "cloudflare/wrangler-action must be version-pinned, not @main / @latest."


def test_fork_secrets_fallback_documented() -> None:
    """Fork PRs cannot read secrets; the workflow must skip the deploy with a clear notice."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "have_secrets" in text, (
        "docs-deploy.yml must conditionally skip the deploy step "
        "when CLOUDFLARE_API_TOKEN is unavailable (fork PRs)."
    )
    assert "::notice" in text, (
        "docs-deploy.yml must emit a GitHub `::notice` line when "
        "the deploy is skipped on a fork PR."
    )


def test_operator_doc_present_and_references_secrets() -> None:
    assert OPERATOR_DOC.is_file(), f"missing operator doc at {OPERATOR_DOC}"
    text = OPERATOR_DOC.read_text(encoding="utf-8")
    for secret in (
        "CLOUDFLARE_API_TOKEN",
        "CLOUDFLARE_ACCOUNT_ID",
        "CLOUDFLARE_PAGES_PROJECT",
    ):
        assert secret in text, f"docs/dev/docs-deploy.md must document the {secret} secret."
    assert (
        "docs.sentinelqa.dev" in text
    ), "docs/dev/docs-deploy.md must document the production URL."

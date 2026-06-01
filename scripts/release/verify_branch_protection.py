# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Verify GitHub branch protection on `main` matches the spec.

The source-of-truth spec lives in `docs/dev/branch-protection.md`.
This script reads the live config via:

 gh api repos/Ohswedd/sentinelqa/branches/main/protection

…and diffs it against the documented rules.

Exit codes (SentinelQA CLI grid):

 0 — live config matches the spec (or the repo is still private,
 in which case branch protection is not yet applicable).
 5 — `gh` is missing or not authenticated.
 6 — drift between the live config and the spec.

The script does NOT mutate GitHub state. The owner re-applies rules
via the Settings UI or `gh api -X PUT` if drift is detected.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPO = "Ohswedd/sentinelqa"
DEFAULT_BRANCH = "main"

EXPECTED_REQUIRED_CHECKS: tuple[str, ...] = (
    "python (3.11)",
    "python (3.12)",
    "typescript (node 20)",
    "typescript (node 22)",
    "docs (Astro Starlight)",
    "commitlint",
    "gitleaks",
    "lychee",
    "no-ai-coauthor",
)


EXPECTED_RULES: dict[str, object] = {
    # Pull-request flow.
    "required_pull_request_reviews.required_approving_review_count": 1,
    "required_pull_request_reviews.require_code_owner_reviews": True,
    "required_pull_request_reviews.dismiss_stale_reviews": True,
    # CI gate.
    "required_status_checks.strict": True,  # branches must be up to date
    # Linear history + safety.
    "required_linear_history.enabled": True,
    "required_conversation_resolution.enabled": True,
    "allow_force_pushes.enabled": False,
    "allow_deletions.enabled": False,
}


def _gh_available() -> bool:
    return shutil.which("gh") is not None


def _gh_auth_ok() -> bool:
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _repo_visibility(repo: str) -> str | None:
    """Return 'public' | 'private' | None on error."""
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{repo}", "-q", ".visibility"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    visibility = result.stdout.strip().lower()
    return visibility or None


def _fetch_protection(repo: str, branch: str) -> dict | None:
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{repo}/branches/{branch}/protection"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        # 404 ⇒ protection not configured; treat as drift, not a tool
        # failure.
        return {"__error__": result.stderr.strip() or result.stdout.strip()}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def _flatten(prefix: str, value: object) -> dict[str, object]:
    out: dict[str, object] = {}
    if isinstance(value, dict):
        for key, sub in value.items():
            path = f"{prefix}.{key}" if prefix else key
            out.update(_flatten(path, sub))
    else:
        out[prefix] = value
    return out


def _compare(live: dict) -> list[str]:
    flat = _flatten("", live)
    diffs: list[str] = []
    for key, expected in EXPECTED_RULES.items():
        actual = flat.get(key)
        if actual != expected:
            diffs.append(f"  - {key}: expected {expected!r}, live {actual!r}")
    contexts = live.get("required_status_checks", {}).get("contexts") or live.get(
        "required_status_checks", {}
    ).get("checks", [])
    if isinstance(contexts, list) and contexts and isinstance(contexts[0], dict):
        live_checks = sorted(entry.get("context", "") for entry in contexts)
    else:
        live_checks = sorted(contexts or [])
    expected_checks = sorted(EXPECTED_REQUIRED_CHECKS)
    missing = [c for c in expected_checks if c not in live_checks]
    extra = [c for c in live_checks if c not in expected_checks]
    if missing:
        diffs.append("  - required_status_checks missing: " + ", ".join(missing))
    if extra:
        diffs.append("  - required_status_checks unexpected: " + ", ".join(extra))
    return diffs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify GitHub branch protection on main matches " "docs/dev/branch-protection.md."
        ),
    )
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--branch", default=DEFAULT_BRANCH)
    args = parser.parse_args(argv)

    if not _gh_available():
        print(
            "gh CLI not found on PATH. Install from https://cli.github.com/ "
            "before running this verification.",
            file=sys.stderr,
        )
        return 5
    if not _gh_auth_ok():
        print(
            "gh CLI is not authenticated. Run `gh auth login` and re-try.",
            file=sys.stderr,
        )
        return 5

    visibility = _repo_visibility(args.repo)
    if visibility == "private":
        print(
            f"Repo {args.repo!r} is private. GitHub gates branch "
            "protection on private repos behind GitHub Pro; verification "
            "is not yet applicable. Re-run after the public flip "
            "(task 35.08)."
        )
        return 0

    live = _fetch_protection(args.repo, args.branch)
    if live is None:
        print(
            f"Could not query branch protection for {args.repo}@{args.branch}. "
            "Check `gh auth status` and your account permissions.",
            file=sys.stderr,
        )
        return 5
    if "__error__" in live:
        print(
            "No branch protection configured on "
            f"{args.repo}@{args.branch}. Apply the rules from "
            "docs/dev/branch-protection.md via Settings → Branches.\n"
            f"GitHub said: {live['__error__']}",
            file=sys.stderr,
        )
        return 6

    diffs = _compare(live)
    if diffs:
        print("Branch protection drift detected on " f"{args.repo}@{args.branch}:")
        for line in diffs:
            print(line)
        print(
            "\nRe-apply via "
            f"https://github.com/{args.repo}/settings/branches "
            "(rules: docs/dev/branch-protection.md)."
        )
        return 6

    print(f"Branch protection on {args.repo}@{args.branch}: matches spec ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())

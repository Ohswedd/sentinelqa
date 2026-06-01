# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Dependabot config health.

Asserts `.github/dependabot.yml` covers the four ecosystems the
task spec requires, that every watched directory exists on disk,
that schedules are weekly, and that the security-policy operator
doc stays consistent with the config.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
DEPENDABOT = REPO_ROOT / ".github" / "dependabot.yml"
SECURITY_POLICY = REPO_ROOT / "docs" / "dev" / "security-policy.md"


def _load() -> dict:
    data = yaml.safe_load(DEPENDABOT.read_text(encoding="utf-8"))
    assert isinstance(data, dict), "dependabot.yml must parse as a YAML mapping"
    return data


def test_dependabot_file_present() -> None:
    assert DEPENDABOT.is_file(), f"missing {DEPENDABOT}"


def test_dependabot_version_2() -> None:
    data = _load()
    assert data.get("version") == 2, "dependabot.yml must declare version: 2"


def test_every_required_ecosystem_present() -> None:
    data = _load()
    ecosystems = {entry["package-ecosystem"] for entry in data.get("updates", [])}
    required = {"pip", "npm", "github-actions", "docker"}
    missing = required - ecosystems
    assert not missing, f"dependabot.yml is missing ecosystems required by task 35.07: {missing}"


def test_every_directory_exists() -> None:
    data = _load()
    failures: list[str] = []
    for entry in data["updates"]:
        directory = entry["directory"]
        rel = directory.lstrip("/")
        candidate = REPO_ROOT / rel if rel else REPO_ROOT
        if not candidate.is_dir():
            failures.append(f"{entry['package-ecosystem']} → {directory} (missing)")
    assert not failures, "dependabot.yml directories that do not exist:\n" + "\n".join(failures)


def test_all_schedules_are_weekly() -> None:
    data = _load()
    failures: list[str] = []
    for entry in data["updates"]:
        schedule = entry.get("schedule", {})
        if schedule.get("interval") != "weekly":
            failures.append(
                f"{entry['package-ecosystem']} @ {entry['directory']} "
                f"→ {schedule.get('interval')!r}"
            )
    assert not failures, "Every Dependabot update must be weekly (task 35.07):\n" + "\n".join(
        failures
    )


def test_every_entry_has_conventional_commit_prefix() -> None:
    data = _load()
    failures: list[str] = []
    for entry in data["updates"]:
        commit = entry.get("commit-message", {})
        prefix = commit.get("prefix")
        if not prefix or not prefix.startswith(("chore(deps)", "ci(deps)")):
            failures.append(f"{entry['package-ecosystem']} @ {entry['directory']} " f"→ {prefix!r}")
    assert not failures, (
        "Dependabot commits must use Conventional Commits "
        "(chore(deps) / ci(deps)):\n" + "\n".join(failures)
    )


def test_security_policy_doc_present_and_consistent() -> None:
    assert SECURITY_POLICY.is_file(), f"missing {SECURITY_POLICY}"
    text = SECURITY_POLICY.read_text(encoding="utf-8")
    # The doc must enumerate every ecosystem the config covers so a
    # future contributor knows what Dependabot is actually doing.
    for ecosystem in ("pip", "npm", "github-actions", "docker"):
        assert (
            ecosystem in text
        ), f"docs/dev/security-policy.md must mention the {ecosystem!r} ecosystem."
    # Supported-versions matrix + CVSS v4.0 mention.
    assert "Supported versions" in text
    assert "CVSS v4.0" in text
    # Coordinated disclosure timeline.
    assert "90-day" in text or "coordinated disclosure" in text.lower()


def test_runner_dockerfile_path_documented_correctly() -> None:
    """The docker entry must point at the actual Dockerfile location."""
    data = _load()
    docker_entries = [e for e in data["updates"] if e["package-ecosystem"] == "docker"]
    assert docker_entries, "dependabot.yml has no docker ecosystem entry"
    for entry in docker_entries:
        dockerfile = REPO_ROOT / entry["directory"].lstrip("/") / "Dockerfile.runner"
        assert (
            dockerfile.is_file()
            or (REPO_ROOT / entry["directory"].lstrip("/") / "Dockerfile").is_file()
        ), (
            f"dependabot.yml docker entry points at {entry['directory']} but no "
            "Dockerfile lives there."
        )

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""GitHub community-files health (Phase 35.02).

Asserts every file that GitHub's "Community Standards" checklist looks
for is present and well-formed:

  * `.github/ISSUE_TEMPLATE/bug_report.yml` (issue form, structured)
  * `.github/ISSUE_TEMPLATE/feature_request.yml`
  * `.github/ISSUE_TEMPLATE/security_disclosure.yml` (redirect to
    SECURITY.md)
  * `.github/ISSUE_TEMPLATE/config.yml` (blank issues off; contact
    links)
  * `.github/pull_request_template.md`
  * `.github/CODE_OF_CONDUCT.md` (Contributor Covenant 2.1)
  * `SECURITY.md`
  * `CONTRIBUTING.md`
  * `LICENSE`
  * `.github/CODEOWNERS`

The test does not depend on the repo being public — it validates the
contents that GitHub will scan once the visibility flip happens
(task 35.08).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
GITHUB_DIR = REPO_ROOT / ".github"
ISSUE_TEMPLATES_DIR = GITHUB_DIR / "ISSUE_TEMPLATE"


REQUIRED_FILES = {
    "issue_bug": ISSUE_TEMPLATES_DIR / "bug_report.yml",
    "issue_feat": ISSUE_TEMPLATES_DIR / "feature_request.yml",
    "issue_sec": ISSUE_TEMPLATES_DIR / "security_disclosure.yml",
    "issue_cfg": ISSUE_TEMPLATES_DIR / "config.yml",
    "pr_template": GITHUB_DIR / "pull_request_template.md",
    "code_of_conduct": GITHUB_DIR / "CODE_OF_CONDUCT.md",
    "security": REPO_ROOT / "SECURITY.md",
    "contributing": REPO_ROOT / "CONTRIBUTING.md",
    "license": REPO_ROOT / "LICENSE",
    "codeowners": GITHUB_DIR / "CODEOWNERS",
}


@pytest.mark.parametrize("name,path", list(REQUIRED_FILES.items()))
def test_required_file_present(name: str, path: Path) -> None:
    assert path.is_file(), f"required community file missing: {name} → {path}"


def _load_yaml(path: Path) -> object:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_bug_report_form_is_valid_yaml() -> None:
    data = _load_yaml(REQUIRED_FILES["issue_bug"])
    assert isinstance(data, dict)
    assert data.get("name", "").lower().startswith("bug")
    body = data.get("body")
    assert isinstance(body, list) and body, "bug_report.yml `body` must be a non-empty list"
    types = {entry.get("type") for entry in body if isinstance(entry, dict)}
    # GitHub issue forms require at least one input/textarea/checkbox.
    assert types & {
        "input",
        "textarea",
        "checkboxes",
    }, f"bug_report.yml has no interactive fields; saw {types}"


def test_feature_request_form_is_valid_yaml() -> None:
    data = _load_yaml(REQUIRED_FILES["issue_feat"])
    assert isinstance(data, dict)
    assert data.get("name", "").lower().startswith("feature")
    body = data.get("body")
    assert isinstance(body, list) and body


def test_security_disclosure_form_redirects_to_security_md() -> None:
    data = _load_yaml(REQUIRED_FILES["issue_sec"])
    assert isinstance(data, dict)
    # The form is intentionally a redirect — body should reference
    # SECURITY.md or the private-vulnerability-reporting URL.
    text = REQUIRED_FILES["issue_sec"].read_text(encoding="utf-8")
    assert (
        "SECURITY.md" in text or "security/advisories/new" in text
    ), "security_disclosure.yml must point at the private channel."
    # It must explicitly tell people NOT to use it as a public form.
    assert any(
        marker.lower() in text.lower()
        for marker in (
            "do not use",
            "do-not-use",
            "stop. do not file",
            "stop — do not",
            "not the channel",
        )
    ), "security_disclosure.yml must warn users not to file publicly."


def test_issue_template_config_disables_blank_issues() -> None:
    data = _load_yaml(REQUIRED_FILES["issue_cfg"])
    assert isinstance(data, dict)
    assert (
        data.get("blank_issues_enabled") is False
    ), "ISSUE_TEMPLATE/config.yml must set blank_issues_enabled: false."
    contact_links = data.get("contact_links", [])
    assert (
        isinstance(contact_links, list) and contact_links
    ), "ISSUE_TEMPLATE/config.yml must surface at least one contact link."
    # At least one contact link must point at the private security path.
    has_security_link = any(
        "security/advisories" in (entry.get("url") or "")
        or "SECURITY.md" in (entry.get("url") or "")
        for entry in contact_links
        if isinstance(entry, dict)
    )
    assert (
        has_security_link
    ), "ISSUE_TEMPLATE/config.yml must include a private-disclosure contact link."


def test_pr_template_covers_definition_of_done() -> None:
    text = REQUIRED_FILES["pr_template"].read_text(encoding="utf-8")
    haystack = text.lower()
    required_markers = (
        "definition of done",
        "prd",
        "tests",
        "conventional commits",
        "co-authored-by",
        "safety",
    )
    missing = [m for m in required_markers if m not in haystack]
    assert not missing, f"pull_request_template.md missing markers: {missing}"


def test_code_of_conduct_is_contributor_covenant_2_1() -> None:
    text = REQUIRED_FILES["code_of_conduct"].read_text(encoding="utf-8")
    # We adopt by reference (the full text is upstream); the file must
    # name the standard and version, and point at the canonical URLs.
    assert "Contributor Covenant" in text
    assert "2.1" in text
    assert "contributor-covenant.org/version/2/1" in text


def test_security_md_carries_disclosure_path() -> None:
    text = REQUIRED_FILES["security"].read_text(encoding="utf-8")
    # Private channel (GitHub Private Vulnerability Reporting + email).
    assert "security/advisories/new" in text
    assert "security@" in text
    # Disclosure timeline must be present.
    assert "coordinated disclosure" in text.lower() or "90-day" in text.lower()
    # Supported-versions matrix.
    assert "Supported versions" in text or "supported versions" in text


def test_contributing_remains_present_and_non_empty() -> None:
    text = REQUIRED_FILES["contributing"].read_text(encoding="utf-8")
    assert "Conventional Commits" in text
    assert "Co-authored-by" in text  # no-AI-coauthor rule restated
    assert "our engineering rules" in text


def test_codeowners_has_default_owner() -> None:
    text = REQUIRED_FILES["codeowners"].read_text(encoding="utf-8")
    assert "@ohswedd" in text, "CODEOWNERS must list at least one human owner."
    assert "@" in text  # at least one handle


def test_no_old_markdown_issue_templates() -> None:
    legacy = list(ISSUE_TEMPLATES_DIR.glob("*.md"))
    # README.md or HOWTO.md inside ISSUE_TEMPLATE is fine, but the old
    # bug_report.md / feature_request.md form must not coexist with the
    # YAML forms (GitHub would show both and confuse users).
    legacy_forms = [p for p in legacy if p.stem in {"bug_report", "feature_request"}]
    assert not legacy_forms, (
        f"Legacy markdown issue templates still present: {legacy_forms}. "
        "Phase 35.02 replaces them with structured issue forms."
    )

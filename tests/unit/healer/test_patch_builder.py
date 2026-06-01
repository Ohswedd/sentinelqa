# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for the LLM patch-builder + safety check."""

from __future__ import annotations

from engine.healer.patch_builder import (
    PatchProposalRequest,
    build_patch,
    build_user_prompt,
    safety_check,
)

_REQUEST = PatchProposalRequest(
    failing_test_id="tests/login.spec.ts > can sign in",
    failing_test_path="tests/login.spec.ts",
    failure_summary="expect button to be visible — timed out after 30s",
    relevant_source_excerpt="export function login() { /* ... */ }",
    source_path="src/auth/login.ts",
    expectation="The login button must be visible within 30 seconds.",
)


# --------------------------------------------------------------------------- #
# Safety check
# --------------------------------------------------------------------------- #


_GOOD_DIFF = """diff --git a/src/auth/login.ts b/src/auth/login.ts
--- a/src/auth/login.ts
+++ b/src/auth/login.ts
@@ -1,3 +1,4 @@
 export function login() {
-  // wait
+  await page.waitForSelector('#sign-in', { state: 'visible' });
+  return true;
 }
"""


def test_clean_diff_has_no_safety_violations() -> None:
    violations = safety_check(_GOOD_DIFF, _REQUEST)
    assert violations == ()


def test_removed_expect_call_is_violation() -> None:
    diff = """diff --git a/src/auth/login.ts b/src/auth/login.ts
--- a/src/auth/login.ts
+++ b/src/auth/login.ts
@@ -1,4 +1,3 @@
-  expect(value).toBe(42);
"""
    violations = safety_check(diff, _REQUEST)
    assert any("expect(" in v for v in violations)


def test_removed_wait_for_call_is_violation() -> None:
    diff = """diff --git a/src/auth/login.ts b/src/auth/login.ts
--- a/src/auth/login.ts
+++ b/src/auth/login.ts
@@ -1,4 +1,3 @@
-  await page.waitForSelector('#x');
"""
    assert any("waitFor" in v for v in safety_check(diff, _REQUEST))


def test_added_test_skip_is_violation() -> None:
    diff = """diff --git a/src/auth/login.ts b/src/auth/login.ts
--- a/src/auth/login.ts
+++ b/src/auth/login.ts
@@ -1,3 +1,4 @@
+test.skip('temporarily disabled', () => {});
"""
    assert any("test.skip" in v for v in safety_check(diff, _REQUEST))


def test_added_try_except_is_violation() -> None:
    diff = """diff --git a/src/auth/login.ts b/src/auth/login.ts
--- a/src/auth/login.ts
+++ b/src/auth/login.ts
@@ -1,3 +1,5 @@
+try {
+  doIt();
+} catch (e) {}
"""
    assert any("try/except" in v for v in safety_check(diff, _REQUEST))


def test_multifile_diff_is_violation() -> None:
    diff = """diff --git a/a.ts b/a.ts
--- a/a.ts
+++ b/a.ts
@@ -1,1 +1,1 @@
-old
+new
diff --git a/b.ts b/b.ts
--- a/b.ts
+++ b/b.ts
@@ -1,1 +1,1 @@
-old
+new
"""
    violations = safety_check(diff, _REQUEST)
    assert any("2 files" in v for v in violations)


def test_test_file_modification_is_violation() -> None:
    diff = (
        "diff --git a/tests/login.spec.ts b/tests/login.spec.ts\n"
        "--- a/tests/login.spec.ts\n"
        "+++ b/tests/login.spec.ts\n"
        "@@ -1,1 +1,1 @@\n"
        "-old\n"
        "+new\n"
    )
    violations = safety_check(diff, _REQUEST)
    assert any("test file itself" in v for v in violations)


def test_oversized_diff_is_violation() -> None:
    lines = "\n".join(f"+line{i}" for i in range(100))
    diff = (
        "diff --git a/src/auth/login.ts b/src/auth/login.ts\n"
        "--- a/src/auth/login.ts\n"
        "+++ b/src/auth/login.ts\n"
        "@@ -1,1 +1,100 @@\n" + lines + "\n"
    )
    violations = safety_check(diff, _REQUEST)
    assert any("60" in v for v in violations)


def test_empty_diff_is_violation() -> None:
    violations = safety_check("", _REQUEST)
    assert violations == ("Empty diff",)


# --------------------------------------------------------------------------- #
# Builder
# --------------------------------------------------------------------------- #


def test_build_patch_returns_clean_verdict_for_valid_diff() -> None:
    def adapter(_system, _user, _model):
        return (f"```diff\n{_GOOD_DIFF}\n```", True, "")

    verdict = build_patch(_REQUEST, adapter=adapter)
    assert verdict.proposed is True
    assert verdict.safety_violations == ()
    assert "+++" in verdict.unified_diff


def test_build_patch_handles_no_safe_patch_marker() -> None:
    def adapter(_system, _user, _model):
        return ("```diff\nNO_SAFE_PATCH\n```", True, "")

    verdict = build_patch(_REQUEST, adapter=adapter)
    assert verdict.proposed is False
    assert verdict.safety_violations == ()
    assert "declined" in verdict.rationale.lower()


def test_build_patch_rejects_invalid_diff_format() -> None:
    def adapter(_system, _user, _model):
        return ("This is prose, not a diff.", True, "")

    verdict = build_patch(_REQUEST, adapter=adapter)
    assert verdict.proposed is False
    assert "invalid-diff-format" in verdict.safety_violations


def test_build_patch_rejects_unsafe_diff() -> None:
    bad_diff = (
        "```diff\n"
        "diff --git a/src/auth/login.ts b/src/auth/login.ts\n"
        "--- a/src/auth/login.ts\n"
        "+++ b/src/auth/login.ts\n"
        "@@ -1,1 +1,1 @@\n"
        "-  expect(x).toBe(42);\n"
        "+  // skipped\n"
        "```"
    )

    def adapter(_system, _user, _model):
        return (bad_diff, True, "")

    verdict = build_patch(_REQUEST, adapter=adapter)
    assert verdict.proposed is False
    assert any("expect(" in v for v in verdict.safety_violations)


def test_build_patch_handles_adapter_exception() -> None:
    def boom(*_a, **_k):
        raise RuntimeError("network down")

    verdict = build_patch(_REQUEST, adapter=boom)
    assert verdict.proposed is False
    assert "network down" in verdict.rationale


def test_build_patch_handles_adapter_unavailable() -> None:
    def adapter(*_a, **_k):
        return ("", False, "no api key")

    verdict = build_patch(_REQUEST, adapter=adapter)
    assert verdict.proposed is False
    assert "provider-unavailable" in verdict.safety_violations


def test_build_user_prompt_truncates_long_source() -> None:
    huge = PatchProposalRequest(
        failing_test_id="x",
        failing_test_path="tests/x.spec.ts",
        failure_summary="x",
        relevant_source_excerpt="x" * 10000,
        source_path="src/x.ts",
    )
    prompt = build_user_prompt(huge)
    assert "truncated" in prompt
    assert len(prompt) < 6000


def test_build_patch_no_adapter_returns_no_proposal() -> None:
    verdict = build_patch(_REQUEST, adapter=None)
    assert verdict.proposed is False
    assert "no-adapter" in verdict.safety_violations

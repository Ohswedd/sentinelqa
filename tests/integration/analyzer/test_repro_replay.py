"""End-to-end: a generated repro spec parses as valid TS and lines up
with the failure.

We don't execute the spec under Playwright in unit-grade CI — that would
require a browser. Instead we lock the parts we can: the banner is
present, the test name lines up with the failure title, and the
auth-env injection mirrors the analyzer's repro steps.
"""

from __future__ import annotations

from engine.analyzer.models import StepRecord
from engine.analyzer.repro import REPRO_BANNER, build_repro_spec, reproduction

from tests.unit.analyzer.conftest import make_signal


def test_repro_steps_and_spec_agree_on_the_failure():
    signal = make_signal(
        title="user can sign in",
        error_message=(
            "locator.click: Timeout 30000ms exceeded for "
            'getByRole("button", { name: "Sign in" })'
        ),
        evidence=("traces/test-1.zip",),
        steps=(
            StepRecord(step_id="s1", name="goto /login", duration_ms=100, ok=True),
            StepRecord(step_id="s2", name="fill[Email]", duration_ms=20, ok=True),
            StepRecord(
                step_id="s3",
                name="click[Sign in]",
                duration_ms=30,
                ok=False,
                error_message="timeout",
            ),
        ),
        route="/login",
    )
    steps = reproduction(signal, auth_env_vars=("SENTINEL_TEST_USER",))
    spec = build_repro_spec(
        signal,
        base_url="http://localhost:3000",
        finding_id="FND-0042",
        auth_env_vars=("SENTINEL_TEST_USER",),
    )

    assert spec.startswith(REPRO_BANNER)
    assert "FND-0042" in spec
    assert "user can sign in" in spec
    assert 'process.env["SENTINEL_TEST_USER"]' in spec
    # The user-visible action that failed appears as a comment.
    assert "click[Sign in]" in spec
    # The repro steps and spec both reference the auth env var by name only.
    assert "$SENTINEL_TEST_USER" in "\n".join(steps)
    # No literal credential values — only env-var references.
    assert "password=" not in spec.lower()
    assert "secret=" not in spec.lower()


def test_spec_round_trips_minimum_playwright_imports():
    signal = make_signal(
        title="basic smoke",
        steps=(StepRecord(step_id="s1", name="goto /", duration_ms=10, ok=True),),
    )
    spec = build_repro_spec(signal, base_url="http://localhost:3000", finding_id="FND-0001")
    # Imports + test() shape only — Playwright TS will reject anything else.
    assert 'import { test, expect } from "@playwright/test";' in spec
    assert 'test("repro: basic smoke", async ({ page }) => {' in spec
    assert "await page.goto(" in spec
    assert "});" in spec
    assert spec.count("\n") < 60  # small enough to read and adapt

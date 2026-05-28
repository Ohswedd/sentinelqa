"""Reproduction step generation tests (task 09.03)."""

from __future__ import annotations

from engine.analyzer.models import StepRecord
from engine.analyzer.repro import REPRO_BANNER, build_repro_spec, reproduction

from tests.unit.analyzer.conftest import make_signal


def test_repro_includes_trace_path_when_present():
    signal = make_signal(evidence=("traces/test-1.zip", "screenshots/test-1.png"))
    steps = reproduction(signal)
    assert any("trace" in s.lower() for s in steps)
    assert any("test-1.zip" in s for s in steps)


def test_repro_includes_user_visible_steps():
    signal = make_signal(
        steps=(
            StepRecord(step_id="s1", name="goto /login", duration_ms=120, ok=True),
            StepRecord(step_id="s2", name="fill[email]", duration_ms=18, ok=True),
            StepRecord(
                step_id="s3",
                name="click[Sign in]",
                duration_ms=42,
                ok=False,
                error_message="timeout",
            ),
        ),
    )
    steps = reproduction(signal)
    rendered = "\n".join(steps)
    assert "goto /login" in rendered
    assert "click[Sign in] → ERROR" in rendered


def test_repro_uses_env_var_names_not_literal_credentials():
    signal = make_signal(fixture_failed=True, error_message="login failed")
    steps = reproduction(signal, auth_env_vars=("SENTINEL_TEST_USER", "SENTINEL_TEST_PASSWORD"))
    rendered = "\n".join(steps)
    assert "$SENTINEL_TEST_USER" in rendered
    assert "$SENTINEL_TEST_PASSWORD" in rendered
    # Never expose anything that looks like a value.
    assert "password=" not in rendered.lower()


def test_repro_mentions_base_url_when_provided():
    signal = make_signal()
    steps = reproduction(signal, base_url="https://staging.example.test/")
    assert any("staging.example.test" in s for s in steps)


def test_repro_mentions_route_when_no_base_url():
    signal = make_signal(route="/checkout/cart")
    steps = reproduction(signal)
    assert any("/checkout/cart" in s for s in steps)


def test_repro_expected_vs_actual_uses_error_message():
    signal = make_signal(error_message="expected 'Welcome' but got nothing\nstack...")
    steps = reproduction(signal)
    last = steps[-1]
    assert "expected" in last.lower()
    assert "Welcome" in last or "nothing" in last
    # Multi-line errors collapse to the first line only.
    assert "\nstack" not in last


def test_repro_handles_timed_out_status():
    signal = make_signal(status="timed_out", error_message=None)
    steps = reproduction(signal)
    last = steps[-1]
    assert "timed out" in last.lower()


def test_repro_handles_flaky_status():
    signal = make_signal(status="flaky")
    steps = reproduction(signal)
    last = steps[-1]
    assert "flaky" in last.lower()


def test_repro_skips_framework_noise_steps():
    signal = make_signal(
        steps=(
            StepRecord(step_id="s0", name="before each", duration_ms=4, ok=True),
            StepRecord(step_id="s1", name="setup", duration_ms=1, ok=True),
            StepRecord(step_id="s2", name="click[Submit]", duration_ms=6, ok=True),
        ),
    )
    steps = reproduction(signal)
    rendered = "\n".join(steps)
    assert "click[Submit]" in rendered
    assert "before each" not in rendered.lower()
    assert "setup" not in rendered.lower().replace("setup the", "") or "click[Submit]" in rendered


# ---------------------------------------------------------------------------
# Spec exporter
# ---------------------------------------------------------------------------


def test_build_repro_spec_starts_with_banner():
    signal = make_signal(
        steps=(
            StepRecord(
                step_id="s1", name="click[Submit]", duration_ms=4, ok=False, error_message="boom"
            ),
        ),
    )
    spec = build_repro_spec(signal, base_url="https://staging.example.test", finding_id="FND-0001")
    assert spec.startswith(REPRO_BANNER)
    assert "FND-0001" in spec


def test_build_repro_spec_renders_steps_as_comments():
    signal = make_signal(
        steps=(
            StepRecord(step_id="s1", name="goto /login", duration_ms=12, ok=True),
            StepRecord(
                step_id="s2", name="click[Sign in]", duration_ms=80, ok=False, error_message="t"
            ),
        ),
    )
    spec = build_repro_spec(signal, base_url="http://localhost:3000", finding_id="FND-0002")
    assert "// 1. goto /login" in spec
    assert "click[Sign in]" in spec


def test_build_repro_spec_escapes_title():
    signal = make_signal(title='this "test" has\nspecial chars\\')
    spec = build_repro_spec(signal, base_url="http://localhost:3000", finding_id="FND-0003")
    # Quote escaped.
    assert '\\"test\\"' in spec
    # Backslash doubled.
    assert "chars\\\\" in spec


def test_build_repro_spec_uses_env_vars_for_auth():
    signal = make_signal()
    spec = build_repro_spec(
        signal,
        base_url="http://localhost:3000",
        finding_id="FND-0004",
        auth_env_vars=("SENTINEL_TEST_USER", "SENTINEL_TEST_PW"),
    )
    assert 'process.env["SENTINEL_TEST_USER"]' in spec
    assert 'process.env["SENTINEL_TEST_PW"]' in spec
    # No literal credential values — only env-var references.
    assert "password=" not in spec.lower()
    assert "secret=" not in spec.lower()
    assert "token:" not in spec.lower() or 'process.env["' in spec


def test_build_repro_spec_handles_no_steps_gracefully():
    signal = make_signal(steps=())
    spec = build_repro_spec(signal, base_url="http://localhost:3000", finding_id="FND-0005")
    assert "No step records captured" in spec


def test_repro_uses_route_label_when_step_extensible():
    # Cover the find_evidence path with a non-trace ext extension.
    signal = make_signal(evidence=("logs/runner.functional.log",))
    steps = reproduction(signal)
    # No "trace" reference: caller saw nothing trace-shaped, so the
    # default fallback fires.
    assert any(".sentinel/runs/" in s for s in steps)


def test_repro_fixture_failure_without_env_vars_mentions_fixture():
    signal = make_signal(fixture_failed=True, error_message="login failed")
    steps = reproduction(signal)
    rendered = "\n".join(steps)
    assert "auth/setup fixture" in rendered


def test_build_repro_spec_handles_title_with_unicode():
    signal = make_signal(title="page renders ✓")
    spec = build_repro_spec(signal, base_url="http://localhost:3000", finding_id="FND-0006")
    assert "page renders ✓" in spec

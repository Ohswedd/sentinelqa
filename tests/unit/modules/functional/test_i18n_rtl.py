# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for i18n / RTL detection."""

from __future__ import annotations

from modules.functional.checks.i18n_rtl import (
    LocaleRender,
    detect_lang_attribute,
    detect_rtl_attribute,
    detect_untranslated,
    evaluate_locale_render,
)


def test_detect_untranslated_finds_english_in_french_render() -> None:
    html = "<html lang='fr'><body><button>Sign in</button> Submit</body></html>"
    render = LocaleRender(locale="fr", html=html)
    untranslated = detect_untranslated(render)
    assert "Sign in" in untranslated
    assert "Submit" in untranslated


def test_detect_untranslated_returns_nothing_for_english() -> None:
    html = "<html lang='en'><body><button>Sign in</button></body></html>"
    render = LocaleRender(locale="en", html=html)
    assert detect_untranslated(render) == ()


def test_detect_rtl_attribute_true() -> None:
    render = LocaleRender(locale="ar", html='<html dir="rtl" lang="ar"></html>')
    assert detect_rtl_attribute(render) is True


def test_detect_rtl_attribute_false_when_missing() -> None:
    render = LocaleRender(locale="ar", html='<html lang="ar"></html>')
    assert detect_rtl_attribute(render) is False


def test_evaluate_rtl_locale_without_dir_flags_high() -> None:
    render = LocaleRender(
        locale="ar",
        html="<html lang='ar'><body><button>Sign in</button></body></html>",
    )
    findings = evaluate_locale_render(render)
    codes = {f.code for f in findings}
    assert "I18N-RTL-MISSING-DIR" in codes
    assert any(f.severity == "high" for f in findings if f.code == "I18N-RTL-MISSING-DIR")


def test_evaluate_ltr_locale_does_not_flag_missing_dir() -> None:
    render = LocaleRender(
        locale="fr",
        html="<html lang='fr'><body></body></html>",
    )
    findings = evaluate_locale_render(render)
    assert all(f.code != "I18N-RTL-MISSING-DIR" for f in findings)


def test_evaluate_lang_mismatch_flags_low() -> None:
    render = LocaleRender(locale="fr", html='<html lang="en"></html>')
    findings = evaluate_locale_render(render)
    codes = {f.code for f in findings}
    assert "I18N-LANG-MISMATCH" in codes


def test_detect_lang_attribute_returns_value() -> None:
    render = LocaleRender(locale="fr", html='<html lang="fr-CA"></html>')
    assert detect_lang_attribute(render) == "fr-CA"


def test_evaluate_severity_scales_with_count() -> None:
    """Three+ untranslated strings → medium; fewer → low."""

    html_few = "<html lang='fr'>Submit</html>"
    findings_few = evaluate_locale_render(LocaleRender(locale="fr", html=html_few))
    assert any(f.severity == "low" for f in findings_few if f.code == "I18N-UNTRANSLATED")

    html_many = "<html lang='fr'>Submit Cancel Sign in Welcome</html>"
    findings_many = evaluate_locale_render(LocaleRender(locale="fr", html=html_many))
    assert any(f.severity == "medium" for f in findings_many if f.code == "I18N-UNTRANSLATED")

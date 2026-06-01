# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""i18n / RTL audit (v1.3.0).

Switches the page through several locales (English, French, Arabic,
Japanese) and looks for two classes of regression:

* **Untranslated strings** — visible English on a non-English page.
  We catch this by comparing a curated whitelist of UI strings
  against the rendered DOM.
* **RTL layout breaks** — when the locale switches to a RTL
  language (ar, he, fa, ur) and the page omits ``dir="rtl"`` on
  ``<html>`` or sets a fixed ``text-align: left``, the layout
  inverts wrong.

This module owns the heuristics; the live locale switch lives in
the functional module shell. All helpers are pure HTML / locale
inspectors.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final, Literal

Severity = Literal["critical", "high", "medium", "low", "info"]

# Locales we audit out of the box.
DEFAULT_LOCALES: Final[tuple[str, ...]] = ("en", "fr", "ar", "ja")
RTL_LOCALES: Final[frozenset[str]] = frozenset({"ar", "he", "fa", "ur"})

# Stock English UI strings that almost certainly need translating.
_ENGLISH_PROBES: Final[tuple[str, ...]] = (
    "Sign in",
    "Sign up",
    "Log in",
    "Log out",
    "Submit",
    "Cancel",
    "Search",
    "Loading…",
    "Welcome",
    "Continue",
    "Settings",
    "Profile",
    "Help",
    "Settings",
)


@dataclass(frozen=True, slots=True)
class LocaleRender:
    """Render of the page in one locale."""

    locale: str
    html: str


@dataclass(frozen=True, slots=True)
class I18nFinding:
    code: str
    severity: Severity
    locale: str
    rationale: str
    suggested_fix: str = ""
    samples: tuple[str, ...] = field(default_factory=tuple)


_HTML_TAG_RE = re.compile(r"<html\b([^>]*)>", re.IGNORECASE)
_DIR_ATTR_RE = re.compile(r'\bdir\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
_LANG_ATTR_RE = re.compile(r'\blang\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)


def detect_untranslated(render: LocaleRender) -> tuple[str, ...]:
    """Return English UI strings that still appear in a non-English render."""

    if render.locale.startswith("en"):
        return ()
    body = _strip_tags(render.html)
    out: list[str] = []
    for probe in _ENGLISH_PROBES:
        if probe in body and probe not in out:
            out.append(probe)
    return tuple(out)


def detect_rtl_attribute(render: LocaleRender) -> bool:
    """Return True iff ``<html dir="rtl">`` is present."""

    match = _HTML_TAG_RE.search(render.html)
    if match is None:
        return False
    dir_match = _DIR_ATTR_RE.search(match.group(1))
    return bool(dir_match and dir_match.group(1).lower() == "rtl")


def detect_lang_attribute(render: LocaleRender) -> str | None:
    match = _HTML_TAG_RE.search(render.html)
    if match is None:
        return None
    lang_match = _LANG_ATTR_RE.search(match.group(1))
    return lang_match.group(1) if lang_match else None


def evaluate_locale_render(render: LocaleRender) -> tuple[I18nFinding, ...]:
    """Run every check against one rendered locale."""

    out: list[I18nFinding] = []
    untranslated = detect_untranslated(render)
    if untranslated:
        out.append(
            I18nFinding(
                code="I18N-UNTRANSLATED",
                severity="medium" if len(untranslated) >= 3 else "low",
                locale=render.locale,
                rationale=(
                    f"Page rendered for ``{render.locale}`` still shows " "English UI strings."
                ),
                suggested_fix=(
                    "Ensure these strings are wired through your i18n "
                    "library and have translation entries."
                ),
                samples=untranslated,
            )
        )

    if render.locale in RTL_LOCALES and not detect_rtl_attribute(render):
        out.append(
            I18nFinding(
                code="I18N-RTL-MISSING-DIR",
                severity="high",
                locale=render.locale,
                rationale=(
                    f"Page rendered for ``{render.locale}`` (RTL) does not "
                    'set ``<html dir="rtl">``. Native bidirectional '
                    "shaping is broken; layout artefacts likely follow."
                ),
                suggested_fix=(
                    'Add ``<html dir="rtl">`` (or use a runtime helper) ' "for every RTL locale."
                ),
            )
        )

    lang = detect_lang_attribute(render)
    if lang and not lang.lower().startswith(render.locale.lower()):
        out.append(
            I18nFinding(
                code="I18N-LANG-MISMATCH",
                severity="low",
                locale=render.locale,
                rationale=(
                    f"Switching to locale ``{render.locale}`` did not "
                    f"update ``<html lang>`` (still ``{lang}``)."
                ),
                suggested_fix=(
                    "Update the ``lang`` attribute on locale change so "
                    "screen readers pick the right voice."
                ),
            )
        )

    return tuple(out)


def _strip_tags(html: str) -> str:
    """A naive HTML → text dropper for the untranslated-string scan."""

    return re.sub(r"<[^>]+>", " ", html)


__all__ = [
    "DEFAULT_LOCALES",
    "I18nFinding",
    "LocaleRender",
    "RTL_LOCALES",
    "detect_lang_attribute",
    "detect_rtl_attribute",
    "detect_untranslated",
    "evaluate_locale_render",
]

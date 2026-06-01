"""SC 2.5.7, 3.3.7, 3.3.8 deterministic checks."""

from __future__ import annotations

from modules.accessibility.checks.wcag22 import (
    AuthChallenge,
    DraggableElement,
    FormField,
    detect_accessible_authentication,
    detect_dragging_movements,
    detect_redundant_entry,
)

# ---------------------------------------------------------------------------
# 2.5.7 Dragging Movements
# ---------------------------------------------------------------------------


def test_dragging_movements_fires_for_grab_cursor() -> None:
    issues = detect_dragging_movements(
        [DraggableElement(selector="#card-1", cursor="grab")],
    )
    assert len(issues) == 1
    issue = issues[0]
    assert issue.category == "dragging-movements"
    assert issue.success_criterion == "2.5.7"
    assert "no documented keyboard alternative" in issue.description


def test_dragging_movements_fires_for_draggable_attr() -> None:
    issues = detect_dragging_movements(
        [DraggableElement(selector="#row", draggable_attr=True)],
    )
    assert len(issues) == 1
    assert issues[0].category == "dragging-movements"


def test_dragging_movements_silent_when_keyboard_alternative_documented() -> None:
    issues = detect_dragging_movements(
        [
            DraggableElement(
                selector="#card-1",
                cursor="grab",
                has_keyboard_alternative=True,
            )
        ],
    )
    assert issues == ()


def test_dragging_movements_silent_for_text_cursor() -> None:
    issues = detect_dragging_movements(
        [DraggableElement(selector="p", cursor="text")],
    )
    assert issues == ()


# ---------------------------------------------------------------------------
# 3.3.7 Redundant Entry
# ---------------------------------------------------------------------------


def test_redundant_entry_fires_on_repeated_purpose() -> None:
    fields = (
        FormField(
            selector="#email-1",
            step=1,
            name="email",
            autocomplete="email",
            purpose="email",
        ),
        FormField(
            selector="#email-2",
            step=2,
            name="email_confirm",
            autocomplete="email",
            purpose="email",
        ),
    )
    issues = detect_redundant_entry(fields)
    assert len(issues) == 1
    issue = issues[0]
    assert issue.category == "redundant-entry"
    assert issue.success_criterion == "3.3.7"
    assert issue.selector == "#email-2"
    assert "step 1" in issue.description and "step 2" in issue.description


def test_redundant_entry_groups_by_autocomplete_when_purpose_missing() -> None:
    fields = (
        FormField(selector="#a", step=1, name="x", autocomplete="address-line1"),
        FormField(selector="#b", step=2, name="y", autocomplete="address-line1"),
    )
    issues = detect_redundant_entry(fields)
    assert len(issues) == 1


def test_redundant_entry_silent_on_same_step() -> None:
    fields = (
        FormField(selector="#a", step=1, name="x", purpose="email"),
        FormField(selector="#b", step=1, name="y", purpose="email"),
    )
    assert detect_redundant_entry(fields) == ()


def test_redundant_entry_silent_when_no_grouping_key() -> None:
    fields = (
        FormField(selector="#a", step=1, name="", label=""),
        FormField(selector="#b", step=2, name="", label=""),
    )
    assert detect_redundant_entry(fields) == ()


# ---------------------------------------------------------------------------
# 3.3.8 Accessible Authentication (Minimum)
# ---------------------------------------------------------------------------


def test_accessible_auth_fires_for_captcha_without_alternative() -> None:
    issues = detect_accessible_authentication(
        [AuthChallenge(selector="#captcha", kind="image-captcha")],
    )
    assert len(issues) == 1
    issue = issues[0]
    assert issue.category == "accessible-authentication"
    assert issue.success_criterion == "3.3.8"
    assert "image-captcha" in issue.description
    assert "passkey" in issue.description


def test_accessible_auth_silent_when_alternative_present() -> None:
    issues = detect_accessible_authentication(
        [
            AuthChallenge(
                selector="#captcha",
                kind="image-captcha",
                has_alternative=True,
            )
        ],
    )
    assert issues == ()


def test_accessible_auth_handles_unknown_kind_label() -> None:
    issues = detect_accessible_authentication(
        [AuthChallenge(selector="#auth", kind="")],
    )
    assert len(issues) == 1
    assert "unspecified" in issues[0].description

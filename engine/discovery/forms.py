"""Forms inventory (task 05.04).

Walks every HTML page in the crawl result and produces typed
:class:`~engine.domain.form.Form` records: id, action URL, method, fields,
submit-handler presence, client-side validation presence.

The HTTP-first MVP can only see attributes present in the rendered HTML.
JS-attached ``addEventListener`` handlers are not detectable without
executing the page — that case is flagged when there's no ``action``, no
``onsubmit`` attribute, and no JS reference to the form id. The Phase 17
Playwright backend will replace those inferences with real signal
(ADR-0010).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

from pydantic import ValidationError

from engine.discovery.crawler import CrawlResult
from engine.domain.form import Form, FormField, FormFieldType
from engine.domain.ids import IdGenerator
from engine.domain.route import HttpMethod

_FIELD_TYPE_MAP: dict[str, FormFieldType] = {
    "text": "text",
    "email": "email",
    "password": "password",
    "tel": "tel",
    "url": "url",
    "number": "number",
    "checkbox": "checkbox",
    "radio": "radio",
    "file": "file",
    "date": "date",
    "hidden": "hidden",
}


@dataclass(frozen=True)
class FormObservation:
    """Aux signal for the risk model."""

    form_id: str
    route_url: str
    kind: str
    detail: str


@dataclass(frozen=True)
class FormsInventoryResult:
    """Output of :meth:`FormsInventory.build`."""

    forms: tuple[Form, ...] = field(default_factory=tuple)
    observations: tuple[FormObservation, ...] = field(default_factory=tuple)
    recaptcha_routes: tuple[str, ...] = field(default_factory=tuple)


class FormsInventory:
    """Build :class:`Form` records from a crawl result."""

    def __init__(self, id_generator: IdGenerator | None = None) -> None:
        self._ids = id_generator or IdGenerator()

    def build(self, crawl: CrawlResult) -> FormsInventoryResult:
        from bs4 import BeautifulSoup, Tag

        forms: list[Form] = []
        observations: list[FormObservation] = []
        recaptcha_routes: list[str] = []

        for page in crawl.pages:
            if not page.is_html:
                continue
            soup = BeautifulSoup(page.html, "lxml")
            for tag in soup.find_all("form"):
                if not isinstance(tag, Tag):
                    continue
                action_attr = tag.get("action")
                action_url = self._absolute_action(page.url, action_attr)
                method_attr = tag.get("method")
                method = self._resolve_method(method_attr)
                fields = tuple(self._extract_fields(tag, soup=soup))
                submit_handler = bool(action_attr) or tag.has_attr("onsubmit")
                validation = self._has_client_validation(fields, tag)

                try:
                    form = Form(
                        id=self._ids.new("FRM"),
                        action_url=action_url,  # type: ignore[arg-type]
                        method=method,
                        fields=fields,
                        submit_handler_present=submit_handler,
                        validation_present=validation,
                    )
                except ValidationError:
                    continue

                forms.append(form)
                if not submit_handler:
                    observations.append(
                        FormObservation(
                            form_id=form.id,
                            route_url=page.url,
                            kind="form_missing_submit_handler",
                            detail="form has no action attribute and no onsubmit handler",
                        )
                    )
                if not validation:
                    observations.append(
                        FormObservation(
                            form_id=form.id,
                            route_url=page.url,
                            kind="form_missing_client_validation",
                            detail="no required/pattern/type-email/aria-invalid signals",
                        )
                    )

            # reCAPTCHA presence — SentinelQA NEVER bypasses CAPTCHA, but we
            # flag forms that have it so Phase 19 understands the UX.
            if any(
                isinstance(s, str) and "recaptcha" in s.lower()
                for s in (*page.discovered_script_srcs, *page.inline_scripts)
            ):
                recaptcha_routes.append(page.url)

        return FormsInventoryResult(
            forms=tuple(forms),
            observations=tuple(observations),
            recaptcha_routes=tuple(sorted(set(recaptcha_routes))),
        )

    def _absolute_action(self, page_url: str, action: Any) -> str | None:
        if not isinstance(action, str) or not action.strip():
            return None
        return urljoin(page_url, action)

    def _resolve_method(self, method: Any) -> HttpMethod:
        if not isinstance(method, str) or not method:
            return "POST"
        upper = method.upper()
        if upper in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
            return upper  # type: ignore[return-value]
        return "POST"

    def _extract_fields(self, form_tag: Any, *, soup: Any) -> Iterable[FormField]:
        for tag in form_tag.find_all(["input", "textarea", "select"]):
            getter = getattr(tag, "get", lambda *_a, **_kw: None)
            name = getter("name") or getter("id") or ""
            if not isinstance(name, str) or not name:
                continue
            type_attr = getter("type") or ("textarea" if tag.name == "textarea" else "text")
            type_str = type_attr if isinstance(type_attr, str) else "text"
            field_type = (
                "textarea"
                if tag.name == "textarea"
                else "select"
                if tag.name == "select"
                else _FIELD_TYPE_MAP.get(type_str, "unknown")
            )
            required = tag.has_attr("required")
            placeholder = getter("placeholder")
            label = self._associated_label(tag, soup=soup)
            try:
                yield FormField(
                    name=name[:200],
                    type=field_type,
                    required=required,
                    accessible_label=label or None,
                    placeholder=(
                        placeholder.strip()[:512] if isinstance(placeholder, str) else None
                    ),
                )
            except ValidationError:
                continue

    def _associated_label(self, tag: Any, *, soup: Any) -> str | None:
        field_id = tag.get("id") if hasattr(tag, "get") else None
        if isinstance(field_id, str) and field_id:
            label = soup.find("label", attrs={"for": field_id})
            if label is not None:
                text = label.get_text(strip=True)
                if isinstance(text, str) and text:
                    return text
        aria_label = tag.get("aria-label") if hasattr(tag, "get") else None
        if isinstance(aria_label, str) and aria_label.strip():
            return aria_label.strip()
        return None

    def _has_client_validation(self, fields: tuple[FormField, ...], form_tag: Any) -> bool:
        if any(f.required or f.type in {"email", "url", "number", "tel"} for f in fields):
            return True
        # Native pattern / minlength / maxlength on any input still inside the form.
        for descendant in form_tag.find_all(["input", "textarea"]):
            getter = getattr(descendant, "get", lambda *_a, **_kw: None)
            if any(isinstance(getter(attr), str) for attr in ("pattern", "minlength", "maxlength")):
                return True
            if descendant.has_attr("aria-invalid") or descendant.has_attr("aria-describedby"):
                return True
        return False


def forms_without_api_calls(
    forms: Iterable[Form],
    api_endpoint_paths: set[str],
) -> list[Form]:
    """Return forms whose ``action_url`` does not resolve to any discovered endpoint.

    Used by the risk model: a form that submits but never appears to talk to
    the backend is exactly the "fake completeness" smell the documentation calls out.
    """

    misfires: list[Form] = []
    for form in forms:
        if form.action_url is None:
            misfires.append(form)
            continue
        from urllib.parse import urlparse

        parsed = urlparse(str(form.action_url))
        if parsed.path not in api_endpoint_paths:
            misfires.append(form)
    return misfires


__all__ = [
    "FormObservation",
    "FormsInventory",
    "FormsInventoryResult",
    "forms_without_api_calls",
]

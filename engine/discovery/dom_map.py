"""DOM map builder (the documentation, ).

For each crawled HTML page, extract a structured list of interactive elements
plus auxiliary observations the Planner cares about:

- Unreachable internal anchors (links pointing at routes that returned 4xx).
- Repeated components (same accessible name + role appearing on ≥3 routes —
 heuristic for shared layout components).
- Elements missing accessible labels (consumed by a11y, but flagged
 here so the risk model can lift them up).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from urllib.parse import urlparse

from engine.discovery.crawler import CrawlPage, CrawlResult
from engine.domain.element import Element
from engine.domain.ids import IdGenerator

# Tag → ARIA role mapping (subset; matches WHATWG HTML AAM defaults).
_TAG_TO_ROLE: dict[str, str] = {
    "a": "link",
    "button": "button",
    "input": "textbox",
    "textarea": "textbox",
    "select": "combobox",
    "form": "form",
    "nav": "navigation",
    "main": "main",
    "header": "banner",
    "footer": "contentinfo",
    "h1": "heading",
    "h2": "heading",
    "h3": "heading",
    "h4": "heading",
    "h5": "heading",
    "h6": "heading",
    "img": "img",
    "label": "label",
}

# `<input type="...">` → role override for common cases.
_INPUT_TYPE_TO_ROLE: dict[str, str] = {
    "submit": "button",
    "button": "button",
    "reset": "button",
    "checkbox": "checkbox",
    "radio": "radio",
    "search": "searchbox",
}

_INTERACTIVE_TAGS = frozenset({"a", "button", "input", "textarea", "select"})


@dataclass(frozen=True)
class DomObservation:
    """Aux signal the risk model and a11y consume."""

    route_url: str
    element_id: str
    kind: str
    detail: str


@dataclass(frozen=True)
class DomMap:
    """Aggregated DOM map across the crawl result."""

    elements: tuple[Element, ...] = field(default_factory=tuple)
    unreachable_links: tuple[str, ...] = field(default_factory=tuple)
    repeated_components: tuple[tuple[str, str, int], ...] = field(default_factory=tuple)
    observations: tuple[DomObservation, ...] = field(default_factory=tuple)


class DomMapBuilder:
    """Build a :class:`DomMap` from a :class:`CrawlResult`."""

    def __init__(self, id_generator: IdGenerator | None = None) -> None:
        self._ids = id_generator or IdGenerator()

    def build(
        self,
        crawl: CrawlResult,
        *,
        route_id_by_url: dict[str, str],
    ) -> DomMap:
        elements: list[Element] = []
        observations: list[DomObservation] = []
        component_counts: Counter[tuple[str, str]] = Counter()
        component_routes: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
        unreachable: list[str] = []

        # Pre-compute reachable URL set to detect unreachable internal links.
        ok_urls = {p.url for p in crawl.pages if 200 <= p.status_code < 400}
        bad_urls = {p.url for p in crawl.pages if p.status_code >= 400}

        for page in crawl.pages:
            if not page.is_html:
                continue
            route_id = route_id_by_url.get(page.url)
            if route_id is None:
                continue
            for element, observation in self._extract_page(page=page, route_id=route_id):
                elements.append(element)
                if observation is not None:
                    observations.append(observation)
                key = (element.role, (element.accessible_name or "").strip().lower())
                if key[1]:
                    component_counts[key] += 1
                    component_routes[key].add(route_id)

            # Unreachable links: anchors point at a URL we observed returning 4xx+.
            for href in page.discovered_links:
                from urllib.parse import urljoin

                absolute = urljoin(page.url, href)
                if absolute in bad_urls and absolute not in ok_urls:
                    unreachable.append(absolute)

        repeated = tuple(
            (role, name, count)
            for (role, name), count in component_counts.items()
            if len(component_routes[(role, name)]) >= 3
        )

        return DomMap(
            elements=tuple(elements),
            unreachable_links=tuple(sorted(set(unreachable))),
            repeated_components=repeated,
            observations=tuple(observations),
        )

    def _extract_page(
        self,
        *,
        page: CrawlPage,
        route_id: str,
    ) -> Iterable[tuple[Element, DomObservation | None]]:
        from bs4 import BeautifulSoup, Tag

        soup = BeautifulSoup(page.html, "lxml")
        seen_keys: set[tuple[str, str, str]] = set()
        for tag in soup.find_all(_INTERACTIVE_TAGS):
            if not isinstance(tag, Tag):
                continue
            role = self._resolve_role(tag)
            name = self._accessible_name(tag)
            selector = self._selector(tag)
            tags: set[str] = set()
            if tag.has_attr("disabled"):
                tags.add("disabled")
            hidden_attr = tag.get("hidden")
            aria_hidden = tag.get("aria-hidden")
            if hidden_attr is not None or aria_hidden == "true":
                tags.add("hidden")
            if tag.name == "a" and tag.has_attr("href"):
                tags.add("link")
            if tag.name == "input" and isinstance(tag.get("type"), str):
                tags.add(f"type:{tag['type']}")

            key = (role, name or "", selector)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            try:
                element = Element(
                    id=self._ids.new("EL"),
                    role=role,
                    accessible_name=name or None,
                    selector=selector,
                    route_id=route_id,
                    tags=frozenset(tags),
                )
            except ValueError:
                # Malformed selector or empty role — skip rather than crash.
                continue

            observation: DomObservation | None = None
            if tag.name in {"button", "a"} and not name:
                observation = DomObservation(
                    route_url=page.url,
                    element_id=element.id,
                    kind="missing_accessible_name",
                    detail=f"<{tag.name}> with no text and no aria-label",
                )
            elif (
                tag.name == "input"
                and tag.get("type") not in {"submit", "button", "reset"}
                and not name
                and not tag.has_attr("aria-label")
            ):
                label_id = tag.get("id")
                label_for = None
                if isinstance(label_id, str) and label_id:
                    label_for = soup.find("label", attrs={"for": label_id})
                if label_for is None:
                    observation = DomObservation(
                        route_url=page.url,
                        element_id=element.id,
                        kind="input_missing_label",
                        detail=f"<input> id={label_id!r} has no associated <label>",
                    )

            yield element, observation

    def _resolve_role(self, tag: object) -> str:
        # Late-binding to avoid forcing bs4 typing at top of file.
        explicit = getattr(tag, "get", lambda _key: None)("role")
        if isinstance(explicit, str) and explicit:
            return explicit
        name = getattr(tag, "name", "")
        if name == "input":
            input_type = getattr(tag, "get", lambda _key, _default=None: None)("type", "text")
            if isinstance(input_type, str):
                return _INPUT_TYPE_TO_ROLE.get(input_type, "textbox")
        return _TAG_TO_ROLE.get(name, "generic")

    def _accessible_name(self, tag: object) -> str:
        getter = getattr(tag, "get", lambda *_args, **_kwargs: None)
        aria_label = getter("aria-label")
        if isinstance(aria_label, str) and aria_label.strip():
            return aria_label.strip()
        title = getter("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
        get_text = getattr(tag, "get_text", None)
        if callable(get_text):
            text = get_text(strip=True)
            if isinstance(text, str) and text:
                return text
        placeholder = getter("placeholder")
        if isinstance(placeholder, str) and placeholder.strip():
            return placeholder.strip()
        alt = getter("alt")
        if isinstance(alt, str) and alt.strip():
            return alt.strip()
        return ""

    def _selector(self, tag: object) -> str:
        getter = getattr(tag, "get", lambda *_args, **_kwargs: None)
        explicit_id = getter("id")
        if isinstance(explicit_id, str) and explicit_id:
            return f"#{explicit_id}"
        data_testid = getter("data-testid")
        if isinstance(data_testid, str) and data_testid:
            return f"[data-testid='{data_testid}']"
        name = getattr(tag, "name", "*")
        classes = getter("class")
        if isinstance(classes, list) and classes:
            return f"{name}.{'.'.join(c for c in classes if isinstance(c, str))}"
        return name or "*"


def route_url_to_path(url: str) -> str:
    """Return the path component of ``url`` (for Route.path persistence)."""

    parsed = urlparse(url)
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    return path


__all__ = ["DomMap", "DomMapBuilder", "DomObservation", "route_url_to_path"]

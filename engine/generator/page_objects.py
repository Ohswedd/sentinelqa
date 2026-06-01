"""Page-object generator.

Produces one ``<RouteName>Page.ts`` per route that:

- appears in ≥ 2 flows AND/OR
- has ≥ 3 interactive elements in the discovery graph.

Each generated page-object encapsulates semantic locators (one accessor
per interactive element it owns), a ``goto(page)`` action, and a
``verify(page)`` assertion against the route's anchor landmark. The
generator emits real TypeScript with the SentinelQA banner so the
writer can refuse to clobber hand-edits.

Design notes:

- We *never* emit a brittle CSS selector. If the discovery element has
 an accessible name/role, we use ``getByRole`` / ``getByLabel`` /
 ``getByText``. Elements without semantic anchors are dropped (the
 caller can detect this via :attr:`GeneratedPageObject.skipped_elements`).
- Naming uses :func:`route_to_page_name` so deterministic output is
 guaranteed for a given route path.
- The generator is import-free of Playwright at runtime — it only emits
 strings. Test files exercise the output by running ``tsc --noEmit``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from engine.domain.element import Element
from engine.domain.flow import Flow
from engine.domain.route import Route
from engine.generator.render import GENERATOR_BANNER

ACTIONABLE_ROLES: frozenset[str] = frozenset(
    {
        "button",
        "link",
        "textbox",
        "checkbox",
        "radio",
        "combobox",
        "switch",
        "tab",
        "menuitem",
        "searchbox",
    }
)

DEFAULT_MIN_FLOW_USES: int = 2
DEFAULT_MIN_ELEMENTS: int = 3


@dataclass(frozen=True)
class PageObjectOptions:
    """Tunable thresholds for which routes get a page object."""

    min_flow_uses: int = DEFAULT_MIN_FLOW_USES
    min_elements: int = DEFAULT_MIN_ELEMENTS


@dataclass(frozen=True)
class GeneratedPageObject:
    """One generated page-object file."""

    route_id: str
    route_path: str
    class_name: str
    rel_path: Path
    source: str
    accessor_count: int
    skipped_elements: tuple[str, ...]


_SLUG_SPLIT = re.compile(r"[^A-Za-z0-9]+")


def route_to_page_name(path: str) -> str:
    """Return the PascalCase class name for ``path`` (with ``Page`` suffix).

    ``/`` → ``RootPage``. ``/users/[id]/edit`` → ``UsersIdEditPage``.
    ``/api/v1/foo`` → ``ApiV1FooPage``.
    """

    parts = [p for p in _SLUG_SPLIT.split(path) if p]
    if not parts:
        return "RootPage"
    cleaned = [_capitalize_segment(p) for p in parts]
    name = "".join(cleaned) + "Page"
    if name[0].isdigit():
        name = "Page" + name
    return name


def _capitalize_segment(segment: str) -> str:
    # Split on lowercase→uppercase boundaries so existing camelCase ids
    # survive (``maxLength`` → ``MaxLength``).
    parts = re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z]+|\d+", segment)
    if not parts:
        return segment.capitalize()
    return "".join(p[:1].upper() + p[1:] for p in parts)


def _accessor_name(element: Element, used: set[str]) -> str:
    base = element.accessible_name or element.role or "element"
    slug = re.sub(r"[^A-Za-z0-9]+", " ", base).strip().lower()
    if not slug:
        slug = "element"
    parts = slug.split()
    camel = parts[0] + "".join(p.capitalize() for p in parts[1:])
    if camel and camel[0].isdigit():
        camel = "_" + camel
    suffix = _role_to_suffix(element.role)
    name = camel + suffix
    if name in used:
        idx = 2
        while f"{name}{idx}" in used:
            idx += 1
        name = f"{name}{idx}"
    used.add(name)
    return name


def _role_to_suffix(role: str) -> str:
    role_lc = role.lower()
    if role_lc in {"button", "tab", "menuitem"}:
        return "Button"
    if role_lc == "link":
        return "Link"
    if role_lc in {"textbox", "searchbox"}:
        return "Field"
    if role_lc in {"checkbox", "switch", "radio"}:
        return "Toggle"
    return "Locator"


def _emit_locator_call(element: Element) -> str | None:
    role = element.role.lower()
    name = element.accessible_name
    if not name:
        return None
    name_lit = _ts_string_literal(name)
    if role in ACTIONABLE_ROLES or role in {"heading", "navigation", "main", "banner"}:
        return f"this.page.getByRole('{role}', {{ name: {name_lit} }})"
    return f"this.page.getByText({name_lit})"


def _ts_string_literal(value: str) -> str:
    import json as _json

    return _json.dumps(value, ensure_ascii=False)


def _route_anchor(route: Route, elements_for_route: Sequence[Element]) -> str:
    """Pick the assertion used by ``verify(page)``.

    Preference order: a heading with a name → first link with a name →
    main landmark.
    """

    headings = [
        el for el in elements_for_route if el.role.lower() == "heading" and el.accessible_name
    ]
    if headings:
        name_lit = _ts_string_literal(headings[0].accessible_name or "")
        return f"await page.getByRole('heading', {{ name: {name_lit} }}).waitFor();"
    links = [el for el in elements_for_route if el.role.lower() == "link" and el.accessible_name]
    if links:
        name_lit = _ts_string_literal(links[0].accessible_name or "")
        return f"await page.getByRole('link', {{ name: {name_lit} }}).waitFor();"
    return "await page.getByRole('main').waitFor();"


def _flow_uses_route(flows: Sequence[Flow], route_id: str) -> int:
    """Count flows whose any step targets ``route_id``."""

    return sum(1 for flow in flows if any(s.target_route_id == route_id for s in flow.steps))


def _elements_by_route(elements: Sequence[Element]) -> Mapping[str, list[Element]]:
    by: dict[str, list[Element]] = {}
    for el in elements:
        by.setdefault(el.route_id, []).append(el)
    return by


def _should_emit(
    route: Route,
    *,
    flow_uses: int,
    elements_for_route: Sequence[Element],
    options: PageObjectOptions,
) -> bool:
    if flow_uses >= options.min_flow_uses:
        return True
    return len(elements_for_route) >= options.min_elements


def generate_page_objects(
    *,
    routes: Sequence[Route],
    elements: Sequence[Element],
    flows: Sequence[Flow],
    out_dir: Path,
    options: PageObjectOptions | None = None,
) -> list[GeneratedPageObject]:
    """Build page-object source files. Returns one entry per emitted file.

    Files are emitted with paths *relative to* ``out_dir``; the writer
    handles absolute resolution. The returned objects are deterministic
    (sorted by route path) so plan.md and goldens stay byte-stable.
    """

    if options is None:
        options = PageObjectOptions()

    elements_by_route = _elements_by_route(elements)
    out: list[GeneratedPageObject] = []
    sorted_routes = sorted(routes, key=lambda r: (r.path, r.id))
    for route in sorted_routes:
        els = elements_by_route.get(route.id, [])
        flow_count = _flow_uses_route(flows, route.id)
        if not _should_emit(route, flow_uses=flow_count, elements_for_route=els, options=options):
            continue

        used_names: set[str] = set()
        accessor_lines: list[str] = []
        skipped: list[str] = []
        sorted_els = sorted(els, key=lambda e: (e.role, e.accessible_name or "", e.id))
        for el in sorted_els:
            call = _emit_locator_call(el)
            if call is None:
                skipped.append(el.id)
                continue
            name = _accessor_name(el, used_names)
            accessor_lines.append(f"  get {name}() {{ return {call}; }}")

        class_name = route_to_page_name(route.path)
        rel_path = Path("pages") / f"{class_name}.ts"
        source = _render_class(
            class_name=class_name,
            route_path=route.path,
            accessor_lines=accessor_lines,
            anchor_call=_route_anchor(route, sorted_els),
        )
        out.append(
            GeneratedPageObject(
                route_id=route.id,
                route_path=route.path,
                class_name=class_name,
                rel_path=rel_path,
                source=source,
                accessor_count=len(accessor_lines),
                skipped_elements=tuple(skipped),
            )
        )
    return out


def _render_class(
    *,
    class_name: str,
    route_path: str,
    accessor_lines: Sequence[str],
    anchor_call: str,
) -> str:
    accessors = (
        "\n".join(accessor_lines) if accessor_lines else "  // no semantic accessors generated"
    )
    quoted_path = _ts_string_literal(route_path)
    return (
        GENERATOR_BANNER
        + "import type { Page } from '@playwright/test';\n"
        + "\n"
        + f"export class {class_name} {{\n"
        + "  constructor(private readonly page: Page) {}\n"
        + "\n"
        + f"  async goto() {{ await this.page.goto({quoted_path}); }}\n"
        + "\n"
        + "  async verify() {\n"
        + f"    {anchor_call}\n"
        + "  }\n"
        + "\n"
        + accessors
        + "\n"
        + "}\n"
    )


__all__ = [
    "ACTIONABLE_ROLES",
    "GeneratedPageObject",
    "PageObjectOptions",
    "generate_page_objects",
    "route_to_page_name",
]

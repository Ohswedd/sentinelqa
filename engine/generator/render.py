"""Template renderer for generated Playwright code.

Wraps Jinja2 with strict variable validation (``StrictUndefined``) and a
single source of the SentinelQA-generated banner that the file writer
detects to refuse clobbering hand-edited files (``write_generated_files``).

The renderer is deliberately small: every template lives under
:data:`TEMPLATE_DIR` and is rendered with a typed context dict. Missing
or unexpected variables raise :class:`RenderError` rather than silently
producing broken TypeScript.

Templates use ``.ts.j2`` extension. Jinja2's default delimiters collide
with TS literal interpolation (``${...}``) only inside backticks, so we
keep generated literals with backticks unrendered by always rendering
backtick blocks via the ``raw_backticks`` filter (or, equivalently,
authoring templates to compose template literals at runtime).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from jinja2 import (
    BaseLoader,
    ChoiceLoader,
    DictLoader,
    Environment,
    FileSystemLoader,
    StrictUndefined,
    TemplateNotFound,
    Undefined,
    UndefinedError,
)

TEMPLATE_DIR: Final[Path] = Path(__file__).parent / "templates"

GENERATOR_BANNER_MARKER: Final[str] = "SentinelQA Generated — do not edit by hand"
"""Substring every generated file MUST include in its header banner.

The writer (``engine.generator.writer.write_generated_files``) uses
this marker to detect whether an existing file at the target path was
created by SentinelQA. Files that lack the marker are considered hand
owned and only overwritten when ``--force`` is passed.
"""

GENERATOR_BANNER: Final[str] = f"""// {GENERATOR_BANNER_MARKER}.
// Re-run `sentinel generate` to regenerate. Manual edits will be
// preserved only when this banner is removed (then the file is treated
// as hand-owned and `sentinel generate` will refuse to overwrite it
// without --force).
"""


class RenderError(ValueError):
    """Raised when rendering fails (missing template, undefined var, etc.)."""


def _make_env(extra_loader: Mapping[str, str] | None = None) -> Environment:
    """Build a Jinja2 environment seeded with the bundled template dir.

    ``extra_loader`` lets unit tests inject in-memory templates without
    touching the filesystem. Strict undefined makes typos in template
    variables fail loudly at render time.
    """

    loaders: list[BaseLoader] = []
    if extra_loader:
        loaders.append(DictLoader(dict(extra_loader)))
    loaders.append(FileSystemLoader(str(TEMPLATE_DIR)))
    env = Environment(
        loader=ChoiceLoader(loaders),
        undefined=StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["js_string"] = _js_string_filter
    env.filters["regex_literal"] = _regex_literal_filter
    env.filters["regex_pattern"] = _regex_pattern_filter
    return env


def render_template(
    template_name: str,
    context: Mapping[str, Any],
    *,
    extra_templates: Mapping[str, str] | None = None,
) -> str:
    """Render ``template_name`` with ``context``; return the TS source.

    Raises :class:`RenderError` on missing template or undefined variable.
    The rendered output ALWAYS starts with :data:`GENERATOR_BANNER` —
    every template includes ``{{ banner }}`` at the top so the marker
    survives downstream edits to the templates themselves.
    """

    env = _make_env(extra_templates)
    try:
        tmpl = env.get_template(template_name)
    except TemplateNotFound as exc:
        raise RenderError(f"template not found: {template_name!r}") from exc
    merged: dict[str, Any] = {"banner": GENERATOR_BANNER, **dict(context)}
    try:
        body = tmpl.render(**merged)
    except UndefinedError as exc:
        raise RenderError(f"undefined variable in {template_name!r}: {exc}") from exc
    if GENERATOR_BANNER_MARKER not in body:
        raise RenderError(
            f"rendered template {template_name!r} is missing the SentinelQA banner; "
            "templates MUST emit `{{ banner }}` at the top."
        )
    return body


def _js_string_filter(value: Any) -> str:
    """Render ``value`` as a JSON double-quoted JS string literal.

    Templates use this for any text that lands inside double quotes in
    the generated source, so backslashes, quotes, and control chars get
    escaped consistently. Returns the *quoted* literal (including the
    surrounding double quotes) so templates can drop it in directly.
    """

    if isinstance(value, Undefined):
        raise RenderError("js_string filter received an undefined value")
    import json as _json

    return _json.dumps(str(value), ensure_ascii=False)


_JS_REGEX_META = set(r"\^$.|?*+()[]{}")


def _regex_literal_filter(value: Any, *, flags: str = "i") -> str:
    """Render ``value`` as a JS regex literal ``/.../<flags>`` matching it verbatim.

    Escapes only the JavaScript regex metacharacters that need escaping
    in a regex literal context (not the broader Python ``re.escape``
    set, which is too aggressive for JS and emits noise like ``\\ ``
    that some readers find confusing). Always escapes ``/`` so the
    literal cannot be terminated early.

    Use this when the caller's value is a literal label / phrase.
    """

    if isinstance(value, Undefined):
        raise RenderError("regex_literal filter received an undefined value")
    text = str(value)
    out: list[str] = []
    for ch in text:
        if ch in _JS_REGEX_META or ch == "/":
            out.append("\\" + ch)
        else:
            out.append(ch)
    return f"/{''.join(out)}/{flags}"


def _regex_pattern_filter(value: Any, *, flags: str = "i") -> str:
    """Render ``value`` as a JS regex literal, treating it as a regex pattern.

    Caller-provided regex (e.g. ``"sign in|log in"``) is wrapped in
    ``/.../<flags>`` verbatim. Only ``/`` is escaped to keep the
    literal well-formed.

    Use this when the value is already a regex pattern.
    """

    if isinstance(value, Undefined):
        raise RenderError("regex_pattern filter received an undefined value")
    text = str(value).replace("/", r"\/")
    return f"/{text}/{flags}"


__all__ = [
    "GENERATOR_BANNER",
    "GENERATOR_BANNER_MARKER",
    "RenderError",
    "TEMPLATE_DIR",
    "render_template",
]

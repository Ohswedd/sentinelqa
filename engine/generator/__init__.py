"""SentinelQA generator module (the documentation).

Turns a :class:`engine.domain.TestPlan` into idiomatic Playwright spec
files, page-object classes, fixtures, and a human-readable generated
plan markdown. Output goes under ``tests/sentinel/`` by default; every
generated file carries a `SentinelQA Generated` banner so the writer
can detect hand-edits and refuse to clobber them without ``--force``.

The generator is deterministic: same plan + same context → byte-equal
output. Templates live under :mod:`engine.generator.templates` and are
rendered via :func:`engine.generator.render.render_template`.
"""

from __future__ import annotations

from engine.generator.fixtures import (
    FixtureGenerationOptions,
    GeneratedFixture,
    generate_fixtures,
)
from engine.generator.locator_strategy import (
    BrittlenessAuditResult,
    BrittlenessWarning,
    LocatorAuditError,
    audit_specs,
)
from engine.generator.page_objects import (
    GeneratedPageObject,
    PageObjectOptions,
    generate_page_objects,
)
from engine.generator.pipeline import (
    GeneratedFile,
    GenerationInputs,
    GenerationOptions,
    GenerationResult,
    GeneratorPipeline,
)
from engine.generator.plan_md import GeneratedPlanInputs, render_generated_plan_md
from engine.generator.render import (
    GENERATOR_BANNER,
    GENERATOR_BANNER_MARKER,
    TEMPLATE_DIR,
    RenderError,
    render_template,
)
from engine.generator.writer import OverwriteError, write_generated_files

__all__ = [
    "BrittlenessAuditResult",
    "BrittlenessWarning",
    "FixtureGenerationOptions",
    "GENERATOR_BANNER",
    "GENERATOR_BANNER_MARKER",
    "GeneratedFile",
    "GeneratedFixture",
    "GeneratedPageObject",
    "GeneratedPlanInputs",
    "GenerationInputs",
    "GenerationOptions",
    "GenerationResult",
    "GeneratorPipeline",
    "LocatorAuditError",
    "OverwriteError",
    "PageObjectOptions",
    "RenderError",
    "TEMPLATE_DIR",
    "audit_specs",
    "generate_fixtures",
    "generate_page_objects",
    "render_generated_plan_md",
    "render_template",
    "write_generated_files",
]

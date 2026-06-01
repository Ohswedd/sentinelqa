"""— plugin discovery + load-time validation."""

from __future__ import annotations

import importlib.metadata as importlib_metadata

from engine.plugins import (
    PluginRegistry,
    discover,
    load_from_entry_point,
)
from engine.plugins.errors import (
    PluginCapabilityForbiddenError,
    PluginIncompatibleError,
    PluginManifestError,
)

from tests.integration.plugins._fakes import (
    BadShapeScanner,
    ForbiddenScanner,
    IncompatibleScanner,
    TinyReporter,
    TinyScanner,
)


def test_discover_loads_valid_scanner(make_entry_point) -> None:
    ep = make_entry_point("tiny", "tests.fakes.tiny_scanner:TinyScanner", TinyScanner)

    registry = discover(entry_points=[ep])

    assert "tiny-scanner" in registry
    assert len(registry) == 1
    assert registry.errors == ()


def test_discover_loads_multiple_kinds(make_entry_point) -> None:
    eps = [
        make_entry_point("tiny", "tests.fakes.tiny_scanner:TinyScanner", TinyScanner),
        make_entry_point("csv", "tests.fakes.csv_reporter:TinyReporter", TinyReporter),
    ]

    registry = discover(entry_points=eps)

    assert {p.manifest.kind for p in registry} == {"scanner", "reporter"}
    assert registry.by_kind("scanner")[0].manifest.name == "tiny-scanner"
    assert registry.by_kind("reporter")[0].manifest.name == "csv-reporter"


def test_discover_rejects_forbidden_capability(make_entry_point) -> None:
    ep = make_entry_point("bad", "tests.fakes.bad_scanner:ForbiddenScanner", ForbiddenScanner)

    registry = discover(entry_points=[ep])

    assert len(registry) == 0
    assert registry.errors and registry.errors[0]["plugin"] == "bad"
    assert "stealth_automation" in registry.errors[0]["detail"]


def test_discover_rejects_incompatible_protocol(make_entry_point) -> None:
    ep = make_entry_point(
        "future",
        "tests.fakes.future_scanner:IncompatibleScanner",
        IncompatibleScanner,
    )

    registry = discover(entry_points=[ep])

    assert len(registry) == 0
    err = registry.errors[0]
    assert err["plugin"] == "future"
    assert "requires protocol" in err["detail"]


def test_discover_rejects_bad_shape(make_entry_point) -> None:
    ep = make_entry_point("broken", "tests.fakes.broken_scanner:BadShapeScanner", BadShapeScanner)

    registry = discover(entry_points=[ep])

    assert len(registry) == 0
    assert "does not implement" in registry.errors[0]["detail"]


def test_discover_handles_import_error(monkeypatch) -> None:
    bad_ep = importlib_metadata.EntryPoint(
        name="ghost",
        value="this_module_definitely_does_not_exist:Ghost",
        group="sentinelqa.plugins",
    )

    registry = discover(entry_points=[bad_ep])

    assert len(registry) == 0
    assert registry.errors[0]["plugin"] == "ghost"
    assert registry.errors[0]["stage"] == "import"


def test_duplicate_plugin_name_keeps_first(make_entry_point) -> None:
    # Two distinct entry points registering the same plugin name. The
    # second registration should be recorded as an error and dropped.
    ep1 = make_entry_point("first", "tests.fakes.dup_a:TinyScanner", TinyScanner)
    ep2 = make_entry_point("second", "tests.fakes.dup_b:TinyScanner", TinyScanner)

    registry = discover(entry_points=[ep1, ep2])

    assert len(registry) == 1
    duplicate_errors = [e for e in registry.errors if e["stage"] == "duplicate"]
    assert len(duplicate_errors) == 1


def test_load_from_entry_point_returns_loaded_plugin(make_entry_point) -> None:
    ep = make_entry_point("tiny", "tests.fakes.tiny_scanner_2:TinyScanner", TinyScanner)

    loaded = load_from_entry_point(ep)

    assert loaded.manifest.name == "tiny-scanner"
    assert loaded.entry_point_name == "tiny"
    assert isinstance(loaded.instance, TinyScanner)


def test_load_from_entry_point_raises_on_forbidden(make_entry_point) -> None:
    ep = make_entry_point("bad2", "tests.fakes.bad_scanner_2:ForbiddenScanner", ForbiddenScanner)

    try:
        load_from_entry_point(ep)
    except PluginCapabilityForbiddenError as exc:
        assert "bad-scanner" in exc.message
    else:
        raise AssertionError("expected PluginCapabilityForbiddenError")


def test_load_from_entry_point_raises_on_incompatible(make_entry_point) -> None:
    ep = make_entry_point(
        "future2",
        "tests.fakes.future_scanner_2:IncompatibleScanner",
        IncompatibleScanner,
    )

    try:
        load_from_entry_point(ep)
    except PluginIncompatibleError as exc:
        assert "future-scanner" in exc.message
    else:
        raise AssertionError("expected PluginIncompatibleError")


def test_load_from_entry_point_raises_on_bad_shape(make_entry_point) -> None:
    ep = make_entry_point(
        "broken2",
        "tests.fakes.broken_scanner_2:BadShapeScanner",
        BadShapeScanner,
    )

    try:
        load_from_entry_point(ep)
    except PluginManifestError as exc:
        assert "does not implement" in exc.message
    else:
        raise AssertionError("expected PluginManifestError")


def test_registry_sorts_iteration_by_name(make_entry_point) -> None:
    eps = [
        make_entry_point("b", "tests.fakes.b_csv:TinyReporter", TinyReporter),
        make_entry_point("a", "tests.fakes.a_tiny:TinyScanner", TinyScanner),
    ]
    registry = discover(entry_points=eps)

    names = [p.manifest.name for p in registry]
    assert names == sorted(names)


def test_empty_registry_is_iterable() -> None:
    registry = PluginRegistry()
    assert list(registry) == []
    assert len(registry) == 0

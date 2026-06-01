"""License resolver tests."""

from __future__ import annotations

from modules.supply_chain.licenses import resolve_license_ids
from modules.supply_chain.models import SbomComponent


def _component(
    name: str, *, licenses: tuple[str, ...] = (), ecosystem: str = "npm"
) -> SbomComponent:
    return SbomComponent(
        name=name,
        version="1.0.0",
        ecosystem=ecosystem,  # type: ignore[arg-type]
        purl=f"pkg:{ecosystem.lower()}/{name}@1.0.0",
        licenses=licenses,
    )


def test_resolve_license_ids_for_npm_with_single_license() -> None:
    component = _component("lodash", licenses=("MIT",))
    assert resolve_license_ids(component) == ("MIT",)


def test_resolve_license_ids_drops_blank_entries() -> None:
    component = _component("blank", licenses=("", "MIT"))
    assert resolve_license_ids(component) == ("MIT",)


def test_resolve_license_ids_canonicalizes_expression() -> None:
    component = _component("dual", licenses=("MIT OR Apache-2.0",))
    assert resolve_license_ids(component) == ("MIT",)


def test_resolve_license_ids_empty_for_pypi_components() -> None:
    """PyPI lockfiles don't carry license metadata; resolver returns."""

    component = _component("flask", ecosystem="PyPI")
    assert resolve_license_ids(component) == ()


def test_resolve_license_ids_deduplicates_and_sorts() -> None:
    component = _component("multi", licenses=("MIT", "MIT", "Apache-2.0"))
    assert resolve_license_ids(component) == ("Apache-2.0", "MIT")

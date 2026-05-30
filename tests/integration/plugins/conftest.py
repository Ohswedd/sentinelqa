"""Shared fixtures for plugin integration tests.

We construct fake :class:`importlib.metadata.EntryPoint` instances so
the tests don't depend on what's installed in the dev venv. Each
fixture returns a callable that builds an entry point pointing at an
object defined inside the test module.
"""

from __future__ import annotations

import importlib.metadata as importlib_metadata
import sys
import types
from collections.abc import Callable
from typing import Any

import pytest


@pytest.fixture
def make_entry_point() -> Callable[[str, str, Any], importlib_metadata.EntryPoint]:
    """Return a factory that registers ``obj`` in a synthetic module.

    Usage::

        ep = make_entry_point("tiny", "tests.fakes.tiny:TinyScanner", TinyScanner)
    """

    created_modules: list[str] = []

    def _factory(
        name: str,
        target: str,
        obj: Any,
    ) -> importlib_metadata.EntryPoint:
        # Plant ``obj`` in a synthetic module so importlib can resolve
        # ``module:attr`` exactly the way a real entry point does.
        module_name, attr_name = target.split(":", 1)
        module = sys.modules.get(module_name)
        if module is None:
            module = types.ModuleType(module_name)
            sys.modules[module_name] = module
            created_modules.append(module_name)
        setattr(module, attr_name, obj)
        return importlib_metadata.EntryPoint(name=name, value=target, group="sentinelqa.plugins")

    yield _factory

    for module_name in created_modules:
        sys.modules.pop(module_name, None)

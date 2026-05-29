#!/usr/bin/env python3
"""Dump the public SDK surface to ``packages/python-sdk/api-snapshot.json``.

The snapshot is the SDK's contract gate (task 16.06, ADR-0021): CI runs
``tests/unit/sdk/test_api_snapshot.py`` to diff the current public
``__all__`` against the snapshot. Drift fails CI until either:

- the snapshot is regenerated (this script) and an ADR + minor-version
  bump accompany the PR, or
- the inadvertent change is reverted.

Run via ``make sdk-api-snapshot``.
"""

from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
from typing import Any

PUBLIC_MODULES: tuple[str, ...] = (
    "sentinelqa",
    "sentinelqa.errors",
    "sentinelqa.agent",
)


def _describe(obj: Any) -> dict[str, Any]:
    if inspect.isclass(obj):
        # Only count names defined ON the class itself, not inherited
        # bookkeeping from Pydantic BaseModel / Exception. Inherited
        # interfaces still work — we just don't pin their exact list
        # in the snapshot since they belong to the base library.
        own_names = sorted(name for name in obj.__dict__ if not name.startswith("_"))
        # Pydantic model_fields exposes the declared schema-stable fields.
        model_fields: list[str] = []
        fields = getattr(obj, "model_fields", None)
        if isinstance(fields, dict):
            model_fields = sorted(fields.keys())
        return {
            "kind": "class",
            "own_attributes": own_names,
            "model_fields": model_fields,
        }
    if inspect.isfunction(obj):
        try:
            signature = str(inspect.signature(obj))
        except (TypeError, ValueError):
            signature = "(...)"
        return {"kind": "function", "signature": signature}
    if isinstance(obj, str):
        return {"kind": "constant", "value": obj}
    return {"kind": type(obj).__name__}


def dump() -> dict[str, Any]:
    surface: dict[str, Any] = {}
    for module_name in PUBLIC_MODULES:
        module = importlib.import_module(module_name)
        names = sorted(getattr(module, "__all__", []))
        per_module: dict[str, Any] = {}
        for name in names:
            obj = getattr(module, name)
            per_module[name] = _describe(obj)
        surface[module_name] = per_module
    return {
        "schema_version": "1",
        "modules": surface,
    }


def main() -> None:
    payload = dump()
    target = (
        Path(__file__).resolve().parent.parent / "packages" / "python-sdk" / "api-snapshot.json"
    )
    target.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {target}")


if __name__ == "__main__":
    main()

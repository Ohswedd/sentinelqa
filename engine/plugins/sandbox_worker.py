"""Child-process worker for :mod:`engine.plugins.sandbox`.

Run via ``python -m engine.plugins.sandbox_worker``. Reads one line of
JSON from stdin, loads the named plugin entry point, instantiates a
:class:`PluginContextImpl` with the granted permissions, calls
``plugin.run(context)``, and writes one line of JSON to stdout.

The worker process IS the sandbox — no further isolation happens
here. The contract is documented in :mod:`engine.plugins.sandbox`.
"""

from __future__ import annotations

import importlib
import json
import sys
import traceback
from pathlib import Path
from typing import Any

from engine.plugins.runtime import build_plugin_context


def _import_entry_point(entry_point: str) -> Any:
    module_name, _, attr_name = entry_point.partition(":")
    if not module_name or not attr_name:
        raise ValueError(f"malformed entry point {entry_point!r}")
    module = importlib.import_module(module_name)
    obj = getattr(module, attr_name)
    if isinstance(obj, type):
        return obj()
    return obj


def _serialize_result(value: Any) -> Any:
    """Best-effort serialization for the worker's return value."""

    if hasattr(value, "model_dump"):  # Pydantic BaseModel
        return value.model_dump(mode="json")
    if hasattr(value, "_asdict"):  # NamedTuple
        return value._asdict()
    try:
        json.dumps(value)
    except TypeError:
        return repr(value)
    return value


def main(argv: list[str] | None = None) -> int:
    raw = sys.stdin.read()
    try:
        request = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.stdout.write(
            json.dumps({"ok": False, "result": {"error": f"bad stdin JSON: {exc.msg}"}}) + "\n"
        )
        return 2

    plugin_entry_point = request["plugin_entry_point"]
    granted = frozenset(request.get("granted_permissions", []))
    run_dir = Path(request["run_dir"])
    context = build_plugin_context(
        plugin_name=plugin_entry_point.split(":")[-1].lower(),
        run_id=request["run_id"],
        target_url=request["target_url"],
        run_dir=run_dir,
        config_snapshot=request.get("config_snapshot") or {},
        granted_permissions=granted,
    )

    try:
        instance = _import_entry_point(plugin_entry_point)
        result = instance.run(context)
    except Exception as exc:  # pragma: no cover - exercised via tests
        sys.stdout.write(
            json.dumps(
                {
                    "ok": False,
                    "result": {
                        "error": str(exc),
                        "traceback": traceback.format_exc(),
                    },
                }
            )
            + "\n"
        )
        return 1

    payload = _serialize_result(result)
    sys.stdout.write(json.dumps({"ok": True, "result": payload}) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover - module entry
    raise SystemExit(main(sys.argv))

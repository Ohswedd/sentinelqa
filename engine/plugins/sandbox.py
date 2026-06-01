"""Subprocess sandbox for risky plugins.

Plugins requesting ``subprocess.spawn`` or ``network.outbound`` are
launched in a child Python interpreter with a constrained environment.
Communication is a small JSON-over-stdio protocol:

- Host writes one line of JSON to the child's stdin (the
 ``invocation`` payload + the granted-permissions set).
- Child reads, runs the plugin's ``run(context)``, and prints one
 line of JSON back on stdout: either ``{"ok": true, "result":...}``
 or ``{"ok": false, "error": "..."}``.
- Host parses the result and returns it.

The child runs ``python -m engine.plugins.sandbox_worker --plugin <ep>``
with:

- ``env`` filtered to ``PATH``, ``HOME``, ``TMPDIR``, ``LANG``,
 ``SENTINEL_*`` keys, plus any ``env.read:<NAME>`` the plugin
 declared. Every other variable is stripped.
- ``cwd`` set to a fresh tmp directory under ``<run_dir>/plugins/<name>/``.
- ``stdin`` / ``stdout`` piped; ``stderr`` captured for logging.

OS-level sandboxing (firejail / bubblewrap) is intentionally NOT
required — the contract here is process isolation + env redaction.
The the documentation hint about firejail is best-effort and will land in a
later phase if needed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engine.plugins.errors import PluginPermissionError

#: Env vars always passed through to the child (regardless of declared
#: permissions). These are the minimum for Python + locale to work; no
#: secrets, no credentials, no auth tokens.
ALWAYS_INHERITED_ENV: tuple[str, ...] = (
    "PATH",
    "HOME",
    "TMPDIR",
    "TEMP",
    "TMP",
    "LANG",
    "LC_ALL",
    "PYTHONHASHSEED",
    "PYTHONIOENCODING",
    # ``PYTHONPATH`` is required so the child interpreter can import
    # the plugin module. It is NOT a secret — it controls module
    # lookup, which the host already trusts.
    "PYTHONPATH",
    # ``VIRTUAL_ENV`` keeps a uv/venv-based dev environment intact in
    # the child (uv-managed Python looks up its site-packages via it).
    "VIRTUAL_ENV",
)

#: Strictly-prefixed env vars also inherited so the SDK can configure
#: the child process (logging, dev flags, etc.).
INHERITED_ENV_PREFIXES: tuple[str, ...] = ("SENTINEL_", "SENTINELQA_")


@dataclass(frozen=True)
class SandboxInvocation:
    """Inputs to one sandboxed plugin call."""

    plugin_entry_point: str  # "package.module:Class"
    granted_permissions: frozenset[str]
    payload: Mapping[str, Any]
    run_id: str
    target_url: str
    run_dir: Path
    config_snapshot: Mapping[str, Any]


@dataclass(frozen=True)
class SandboxOutcome:
    """Result of one sandboxed plugin call."""

    ok: bool
    result: Mapping[str, Any]
    stderr: str


def build_constrained_env(
    *,
    granted_permissions: frozenset[str],
    source_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Filter an env mapping to the sandbox-allowed set.

    The plugin only sees:

    - The :data:`ALWAYS_INHERITED_ENV` vars.
    - Any var matching :data:`INHERITED_ENV_PREFIXES`.
    - Every ``env.read:<NAME>`` permission's named var.
    """

    source = source_env if source_env is not None else dict(os.environ)
    allowed_names: set[str] = set(ALWAYS_INHERITED_ENV)
    for perm in granted_permissions:
        if perm.startswith("env.read:"):
            allowed_names.add(perm.split(":", 1)[1])

    result: dict[str, str] = {}
    for name, value in source.items():
        if name in allowed_names:
            result[name] = value
            continue
        if any(name.startswith(prefix) for prefix in INHERITED_ENV_PREFIXES):
            result[name] = value
            continue
    return result


def _ensure_can_spawn(granted_permissions: frozenset[str]) -> None:
    if "subprocess.spawn" not in granted_permissions:
        raise PluginPermissionError(
            plugin="<sandbox>",
            permission="subprocess.spawn",
            granted=granted_permissions,
        )


def run_in_sandbox(
    invocation: SandboxInvocation,
    *,
    python_executable: str | None = None,
    timeout_seconds: float = 60.0,
) -> SandboxOutcome:
    """Run a plugin's ``run(context)`` inside a child interpreter.

    Raises :class:`PluginPermissionError` if the plugin did not declare
    ``subprocess.spawn``. The child process inherits only the env vars
    permitted by :func:`build_constrained_env`. The cwd is set to a
    dedicated subdir under the run dir so any stray writes land where
    the rest of the lifecycle expects them.
    """

    _ensure_can_spawn(invocation.granted_permissions)

    sandbox_cwd = invocation.run_dir / "plugins" / "_sandbox"
    sandbox_cwd.mkdir(parents=True, exist_ok=True)

    env = build_constrained_env(granted_permissions=invocation.granted_permissions)

    stdin_payload = json.dumps(
        {
            "plugin_entry_point": invocation.plugin_entry_point,
            "granted_permissions": sorted(invocation.granted_permissions),
            "payload": dict(invocation.payload),
            "run_id": invocation.run_id,
            "target_url": invocation.target_url,
            "run_dir": str(invocation.run_dir),
            "config_snapshot": dict(invocation.config_snapshot),
        },
        sort_keys=True,
    )

    cmd = [
        python_executable or sys.executable,
        "-m",
        "engine.plugins.sandbox_worker",
    ]

    try:
        completed = subprocess.run(
            cmd,
            input=stdin_payload,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(sandbox_cwd),
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return SandboxOutcome(
            ok=False,
            result={"error": f"sandbox timed out after {timeout_seconds}s"},
            stderr=str(exc),
        )

    stderr = completed.stderr or ""

    # Find the first parseable JSON line on stdout. Anything before it
    # is treated as worker noise (e.g. warnings) and surfaced via stderr.
    payload_line = ""
    leading_noise: list[str] = []
    for line in (completed.stdout or "").splitlines():
        if not payload_line and line.strip().startswith("{"):
            payload_line = line.strip()
        else:
            leading_noise.append(line)
    if leading_noise:
        stderr = "\n".join([stderr, *leading_noise]).strip()

    if not payload_line:
        return SandboxOutcome(
            ok=False,
            result={
                "error": "sandbox returned no JSON payload",
                "returncode": completed.returncode,
            },
            stderr=stderr,
        )

    try:
        decoded = json.loads(payload_line)
    except json.JSONDecodeError as exc:
        return SandboxOutcome(
            ok=False,
            result={"error": f"could not decode sandbox payload: {exc.msg}"},
            stderr=stderr,
        )

    return SandboxOutcome(
        ok=bool(decoded.get("ok")),
        result=decoded.get("result") or decoded,
        stderr=stderr,
    )


__all__ = [
    "ALWAYS_INHERITED_ENV",
    "INHERITED_ENV_PREFIXES",
    "SandboxInvocation",
    "SandboxOutcome",
    "build_constrained_env",
    "run_in_sandbox",
]

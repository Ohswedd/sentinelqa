"""tsc --noEmit acceptance test for the golden templates (task 07.01).

For each golden in ``tests/golden/generator/fixtures/``, copy it into a
temporary project that imports ``@sentinelqa/ts-runtime/playwright``
and run ``tsc --noEmit``. Skipped when node/tsc are not available
(local Python-only environments).

Slow tier (~3-5 s) — gated behind ``slow`` marker so the default
``make test`` stays fast; ``make test-full`` and CI run it.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

GOLDEN_DIR = Path(__file__).resolve().parents[2] / "golden" / "generator" / "fixtures"
REPO_ROOT = Path(__file__).resolve().parents[3]

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        shutil.which("pnpm") is None or not (REPO_ROOT / "node_modules").exists(),
        reason="pnpm not available or node_modules not installed",
    ),
]


def _golden_paths() -> list[Path]:
    return sorted(GOLDEN_DIR.glob("*.spec.ts"))


@pytest.mark.parametrize("golden", _golden_paths(), ids=lambda p: p.name)
def test_golden_compiles_with_tsc(golden: Path, tmp_path: Path) -> None:
    project = tmp_path / "tsc-project"
    project.mkdir()
    # Copy golden into project root.
    spec = project / golden.name
    spec.write_text(golden.read_text(encoding="utf-8"), encoding="utf-8")
    # Minimal tsconfig that resolves the workspace package via baseUrl/paths.
    # `typeRoots` points at the workspace's `@types/` install so the tmp
    # project can find `@types/node` without re-installing it (the workspace
    # already pins it; copying or symlinking would just duplicate the install).
    tsconfig = {
        "compilerOptions": {
            "target": "ES2022",
            "module": "ESNext",
            "moduleResolution": "Bundler",
            "lib": ["ES2022", "DOM"],
            "types": ["node"],
            "typeRoots": [f"{REPO_ROOT}/node_modules/@types"],
            "strict": True,
            "esModuleInterop": True,
            "skipLibCheck": True,
            "noEmit": True,
            "baseUrl": ".",
            "paths": {
                "@sentinelqa/ts-runtime/playwright": [
                    f"{REPO_ROOT}/packages/ts-runtime/src/playwright.ts"
                ],
                "@sentinelqa/ts-runtime": [f"{REPO_ROOT}/packages/ts-runtime/src/index.ts"],
                "@playwright/test": [f"{REPO_ROOT}/node_modules/@playwright/test/index.d.ts"],
            },
        },
        "include": [str(spec.name)],
    }
    (project / "tsconfig.json").write_text(json.dumps(tsconfig), encoding="utf-8")

    # Use the workspace's tsc to keep the version pinned (5.7.2).
    tsc = REPO_ROOT / "node_modules" / ".bin" / "tsc"
    if not tsc.exists():
        pytest.skip("workspace tsc binary not present")
    env = os.environ.copy()
    result = subprocess.run(
        [str(tsc), "--noEmit", "-p", str(project)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(
            f"tsc rejected {golden.name}:\n" f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

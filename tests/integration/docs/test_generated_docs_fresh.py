"""Freshness gate for every generated docs page.

Each generator is deterministic and idempotent (see scripts/docs/_common.py).
This test re-runs every generator and asserts the committed bytes match.
If the test fails the fix is always: run ``make docs-gen-all`` and commit
the diff.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _ensure_scripts_on_path() -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    # The MCP server lives outside the engine source root; load its path
    # eagerly so the generator import in this test process succeeds.
    mcp_src = REPO_ROOT / "packages" / "mcp-server" / "src"
    if str(mcp_src) not in sys.path:
        sys.path.insert(0, str(mcp_src))
    sdk_src = REPO_ROOT / "packages" / "python-sdk" / "src"
    if str(sdk_src) not in sys.path:
        sys.path.insert(0, str(sdk_src))


@pytest.fixture(autouse=True)
def _path() -> None:
    _ensure_scripts_on_path()


@pytest.mark.parametrize(
    ("module_name", "output_relpath"),
    [
        (
            "scripts.docs.gen_error_codes",
            "apps/docs/src/content/docs/errors/index.md",
        ),
        (
            "scripts.docs.gen_cli_status",
            "apps/docs/src/content/docs/cli/index.md",
        ),
        (
            "scripts.docs.gen_sdk_reference",
            "apps/docs/src/content/docs/sdk/index.md",
        ),
        (
            "scripts.docs.gen_mcp_reference",
            "apps/docs/src/content/docs/mcp/index.md",
        ),
        (
            "scripts.docs.gen_adr_index",
            "apps/docs/src/content/docs/adrs/index.md",
        ),
    ],
)
def test_generated_page_matches_fresh_render(module_name: str, output_relpath: str) -> None:
    import importlib

    module = importlib.import_module(module_name)
    rendered = module.render()
    committed_path = REPO_ROOT / output_relpath
    committed = committed_path.read_text(encoding="utf-8")
    assert (
        rendered == committed
    ), f"{output_relpath} is stale. Run `make docs-gen-all` and commit the diff."

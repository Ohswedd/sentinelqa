"""The GitHub Action template in `init_cmd.py` must equal PRD §21.1."""

from __future__ import annotations

import re
from pathlib import Path

from sentinel_cli.commands.init_cmd import GITHUB_ACTION_TEMPLATE


def test_template_matches_prd_section_21_1() -> None:
    prd = Path("PRD.md").read_text(encoding="utf-8")
    block = re.search(
        r"### 21\.1 GitHub Action\s*\n+```yaml\s*\n(?P<body>.*?)\n```",
        prd,
        flags=re.DOTALL,
    )
    assert block, "PRD §21.1 GitHub Action template block not found."
    expected = block.group("body") + "\n"
    assert (
        expected == GITHUB_ACTION_TEMPLATE
    ), "GITHUB_ACTION_TEMPLATE diverged from PRD §21.1. Update both in lockstep."

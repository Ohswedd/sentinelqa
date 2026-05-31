"""Safety guard: the supply-chain module never imports offensive tooling.

The Phase 33 README is explicit: every check is defensive / read-only.
This grep-guard mirrors :mod:`tests.security.test_no_offensive_checks`
(Phase 32) and keeps forbidden tokens from creeping into
``modules/supply_chain/`` or the matching CLI command.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_ROOT = REPO_ROOT / "modules" / "supply_chain"
CLI_FILE = REPO_ROOT / "apps" / "cli" / "src" / "sentinel_cli" / "commands" / "supply_chain_cmd.py"

# Tokens that, if they appear in module source, indicate offensive
# tooling drift. Each entry is a substring matched case-insensitively
# against module source code (not docstrings, not comments — see
# :func:`_strip_comments_and_docstrings`).
_FORBIDDEN_TOKENS = (
    "exploit",
    "shellcode",
    "obfuscate",
    "evade",
    "stealth",
    "captcha_bypass",
    "deobfuscate",
)


def _python_sources() -> list[Path]:
    out: list[Path] = []
    if MODULE_ROOT.is_dir():
        out.extend(p for p in MODULE_ROOT.rglob("*.py") if "tests" not in p.parts)
    if CLI_FILE.is_file():
        out.append(CLI_FILE)
    return out


def _strip_comments_and_strings(source: str) -> str:
    """Drop ``# ...`` comments and quoted string contents.

    The guard exists to catch *code* that uses forbidden tokens. Sentences
    in docstrings or comments that mention the same words (e.g.
    "never bypass the safety policy") are not the failure mode we're
    chasing. The strip is approximate but conservative.
    """

    # Remove triple-quoted blocks first so embedded quotes don't break
    # the single-line regex below.
    cleaned = re.sub(r'"""[\s\S]*?"""', "", source)
    cleaned = re.sub(r"'''[\s\S]*?'''", "", cleaned)
    cleaned = re.sub(r"#[^\n]*", "", cleaned)
    cleaned = re.sub(r'"[^"\n]*"', '""', cleaned)
    return re.sub(r"'[^'\n]*'", "''", cleaned)


def test_no_forbidden_tokens_in_module_or_cli() -> None:
    failures: list[str] = []
    for path in _python_sources():
        source = path.read_text(encoding="utf-8")
        cleaned = _strip_comments_and_strings(source).lower()
        for token in _FORBIDDEN_TOKENS:
            if token in cleaned:
                failures.append(
                    f"{path.relative_to(REPO_ROOT)} contains forbidden token: {token!r}"
                )
    assert not failures, "Offensive token drift in supply-chain module:\n" + "\n".join(failures)


def test_postinstall_scanner_never_executes_matched_code() -> None:
    """Sanity guard: the scanner must not invoke ``subprocess`` against
    matched scripts. Reading is fine; running them is not. We grep for
    ``subprocess.run(`` etc. inside the scanner module and assert there
    are none."""

    source = (MODULE_ROOT / "postinstall.py").read_text(encoding="utf-8")
    cleaned = _strip_comments_and_strings(source)
    for sentinel in ("subprocess.run(", "subprocess.Popen(", "subprocess.call(", "os.system("):
        assert sentinel not in cleaned, (
            f"modules/supply_chain/postinstall.py must not invoke {sentinel}; "
            "it only scans, never executes."
        )


def test_container_module_runs_only_against_configured_image() -> None:
    """Grep guard: the container scanner must accept the image as an arg
    and never pull or iterate registries."""

    source = (MODULE_ROOT / "container.py").read_text(encoding="utf-8")
    cleaned = _strip_comments_and_strings(source).lower()
    for forbidden in ("docker pull", "image inspect", "--privileged"):
        assert (
            forbidden not in cleaned
        ), f"modules/supply_chain/container.py contains forbidden directive: {forbidden!r}"

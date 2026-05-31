"""Safety guard for Phase 32 (ADR-0044): no offensive payloads or APIs.

Every check shipped in Phase 32 must remain inside the CLAUDE.md §6
boundary — no exploit weaponisation, no WAF bypass, no aggressive
fuzzing, no detection evasion. This test greps the Phase-32 check
modules for forbidden tokens and asserts none appear.

If a future Phase-32 check legitimately needs one of these tokens
(e.g. a finding *description* that quotes the word "exploit" in a
recommendation), the legal use must land an allowlist entry below
with a justification — otherwise this test fails CI.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PHASE_32_MODULES: tuple[Path, ...] = (
    Path("modules/security/checks/jwt_weakness.py"),
    Path("modules/security/checks/tls_posture.py"),
    Path("modules/security/checks/graphql_safety.py"),
    Path("modules/security/checks/api_bola_bfla.py"),
    Path("modules/security/checks/frontend_only_auth_deeper.py"),
    Path("modules/security/checks/bundle_secrets.py"),
    Path("modules/security/checks/ssrf_redirect.py"),
)

# Banned tokens. The first pass is straight substring; the second pass
# uses regex for word-boundary-sensitive matches.
_FORBIDDEN_SUBSTRINGS: tuple[str, ...] = (
    "shellcode",
    "payload_generator",
    "fuzz_random",
    "obfuscate",
    "stealth",
    "captcha_bypass",
    "evade",
    "rotate_user_agent",
    "anti_detect",
)

_FORBIDDEN_WORDS: tuple[str, ...] = (
    r"\bexploit\b",
    r"\bbypass\b",
    r"\bweaponize\b",
)

# Allow specific occurrences (e.g. recommendation text that mentions
# the word "bypass" in a non-evasion context). Format: (path, token).
_ALLOWLIST: frozenset[tuple[str, str]] = frozenset()


@pytest.mark.parametrize("module_path", PHASE_32_MODULES, ids=lambda p: p.stem)
def test_phase32_module_has_no_offensive_payload(module_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source = (repo_root / module_path).read_text(encoding="utf-8").lower()
    for token in _FORBIDDEN_SUBSTRINGS:
        if (module_path.as_posix(), token) in _ALLOWLIST:
            continue
        assert token not in source, (
            f"Phase 32 module {module_path} contains forbidden token "
            f"`{token}` (CLAUDE.md §6, ADR-0044)."
        )
    for pattern in _FORBIDDEN_WORDS:
        if (module_path.as_posix(), pattern) in _ALLOWLIST:
            continue
        assert not re.search(pattern, source), (
            f"Phase 32 module {module_path} matches forbidden pattern "
            f"`{pattern}` (CLAUDE.md §6, ADR-0044)."
        )


def test_jwt_module_does_not_iterate_external_wordlist() -> None:
    """SEC-JWT-WEAK-HS256-SECRET uses a fixed, enumerated wordlist."""

    repo_root = Path(__file__).resolve().parents[2]
    source = (repo_root / "modules" / "security" / "checks" / "jwt_weakness.py").read_text(
        encoding="utf-8"
    )
    # Sanity: the canonical constant exists and is small.
    assert "_WEAK_HS256_SECRETS" in source
    # No reads from local files or remote URLs that could form a
    # dictionary-attack corpus.
    forbidden = ("open(", "urlopen(", "requests.get", "httpx.get(", "wordlist.txt")
    for token in forbidden:
        assert token not in source, (
            f"jwt_weakness.py contains `{token}` — suggests external "
            "wordlist loading. Brute-force is forbidden (CLAUDE.md §6)."
        )


def test_ssrf_module_payload_list_is_a_constant() -> None:
    """SSRF_PAYLOADS / OPEN_REDIRECT_PAYLOADS must be module-level tuples."""

    repo_root = Path(__file__).resolve().parents[2]
    source = (repo_root / "modules" / "security" / "checks" / "ssrf_redirect.py").read_text(
        encoding="utf-8"
    )
    assert "SSRF_PAYLOADS: Final[tuple[str, ...]]" in source
    assert "OPEN_REDIRECT_PAYLOADS: Final[tuple[str, ...]]" in source
    # No random / mutation generators.
    forbidden = ("random.choice", "itertools.permutations", "secrets.token_")
    for token in forbidden:
        assert token not in source, (
            f"ssrf_redirect.py contains `{token}` — suggests payload "
            "generation. Fuzzing is forbidden (CLAUDE.md §6)."
        )


def test_tls_module_does_not_send_application_bytes() -> None:
    """TLS probe must be read-only (no downgrade attempts)."""

    repo_root = Path(__file__).resolve().parents[2]
    source = (repo_root / "modules" / "security" / "checks" / "tls_posture.py").read_text(
        encoding="utf-8"
    )
    # Only the HTTPS GET for HSTS detection is allowed; no raw socket
    # send calls outside the SSL handshake.
    forbidden = (
        "raw_sock.send",
        "raw_sock.sendall",
        "ssock.send(b",
        "ssock.sendall(",
    )
    for token in forbidden:
        assert token not in source, (
            f"tls_posture.py contains `{token}` — TLS probe must be "
            "read-only (ADR-0044 safety boundary)."
        )


def test_graphql_module_has_fixed_query_set() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source = (repo_root / "modules" / "security" / "checks" / "graphql_safety.py").read_text(
        encoding="utf-8"
    )
    assert "PROBE_QUERIES: Final[tuple[str, ...]]" in source
    forbidden = ("random.choice", "permutations", "fuzz")
    for token in forbidden:
        assert token not in source, (
            f"graphql_safety.py contains `{token}` — fuzzing is " "forbidden (CLAUDE.md §6)."
        )

"""``AuthProfile`` dataclass (, Tasks 31.04 + 31.05).

The fields here are intentionally minimal. Adding any field whose name
suggests credential material (password / secret / token / key / credential
/ otp) trips the structural lint in
``tests/security/test_no_credentials_in_profiles.py`` and the build
breaks — see our engineering rules / §33. Future profile additions go through
that guard.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class AuthProfile:
    """Documented launcher recipe for an interactive sign-in flow.

    Parameters
    ----------
    name:
    Stable identifier (lowercase + dashes). Used by ``--profile <name>``
    on the CLI and by :func:`engine.auth.profiles.resolve_profile`.
    label:
    Human-readable label printed in CLI banners.
    login_url_pattern:
    Canonical URL the operator is expected to start on. The login
    flow opens a real browser at this URL by default.
    success_url_patterns:
    URL prefixes that signal sign-in completed. The login flow
    watches ``page.url`` and auto-captures when it lands on one of
    these — the operator does not need to press Enter.
    mfa_hint:
    One short sentence the CLI prints if MFA is likely (e.g.
    "Complete 2FA in your authenticator app"). Empty when the
    provider's flow handles MFA inline.
    tos_url:
    Link to the provider's Terms of Service. The login banner cites
    it so the operator can verify they're authorized to audit their
    own account on the platform.
    category:
    ``"oauth"``  or ``"llm-web"``. Lets the
    ``sentinel auth list-profiles`` output and the docs group them
    sensibly.
    """

    name: str
    label: str
    login_url_pattern: str
    success_url_patterns: tuple[str, ...]
    mfa_hint: str
    tos_url: str
    category: str

    def __post_init__(self) -> None:
        # Validate every URL is HTTPS. We refuse HTTP because we're
        # documenting "where to sign in"; HTTP login is unsafe.
        for label, value in (
            ("login_url_pattern", self.login_url_pattern),
            *(
                ("success_url_patterns[%d]" % i, pat)
                for i, pat in enumerate(self.success_url_patterns)
            ),
            ("tos_url", self.tos_url),
        ):
            parsed = urlparse(value)
            if parsed.scheme != "https":
                raise ValueError(f"AuthProfile.{label} must be HTTPS; got {value!r}.")
            if not parsed.netloc:
                raise ValueError(f"AuthProfile.{label} is missing a host: {value!r}.")
        if not self.success_url_patterns:
            raise ValueError("AuthProfile.success_url_patterns must contain at least one entry.")
        if self.category not in {"oauth", "llm-web"}:
            raise ValueError(
                f"AuthProfile.category must be 'oauth' or 'llm-web'; got {self.category!r}."
            )

    @property
    def login_host(self) -> str:
        return urlparse(self.login_url_pattern).hostname or ""


__all__ = ["AuthProfile"]

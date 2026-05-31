"""Documented launcher recipes for the auth flow (Phase 31, Tasks 31.04 + 31.05).

A profile is a small, frozen dataclass: name, label, login URL pattern,
success URL patterns, MFA hint, and a ToS link. There is NO credential-
handling code here, and there are NO credential fields. The login flow
uses a profile to (a) print the right human banner before opening a
browser, (b) auto-detect that sign-in finished without the operator
having to press Enter, and (c) cite the provider's Terms of Service so
the operator knows what they're agreeing to.

The lack of credential fields is enforced structurally: the AST guard
in ``tests/security/test_no_credentials_in_profiles.py`` rejects any
new profile field whose name contains
``password|secret|token|key|credential|otp``.

Profile selection is optional. When the operator doesn't pass
``--profile``, the generic "press Enter when done" flow runs.
"""

from __future__ import annotations

from engine.auth.profiles.builtin import BUILTIN_PROFILES, profile_names
from engine.auth.profiles.model import AuthProfile


class ProfileNotFoundError(KeyError):
    """The requested profile name is not registered."""


def list_profiles() -> tuple[AuthProfile, ...]:
    """Return every built-in profile sorted by name."""

    return tuple(sorted(BUILTIN_PROFILES, key=lambda p: p.name))


def resolve_profile(name: str) -> AuthProfile:
    """Return the profile with this name. Raises if unknown."""

    for profile in BUILTIN_PROFILES:
        if profile.name == name:
            return profile
    raise ProfileNotFoundError(
        f"No auth profile named {name!r}. Known profiles: "
        + ", ".join(sorted(p.name for p in BUILTIN_PROFILES))
    )


__all__ = [
    "AuthProfile",
    "BUILTIN_PROFILES",
    "ProfileNotFoundError",
    "list_profiles",
    "profile_names",
    "resolve_profile",
]

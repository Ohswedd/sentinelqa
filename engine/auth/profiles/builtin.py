"""Built-in auth profiles (Tasks 31.04 + 31.05).

Three OAuth profiles for the common SSO shapes, plus five LLM-web
profiles for auditing your-own-account workflows in Claude, ChatGPT
(canonical + Codex variant), Gemini, and Mistral Le Chat. The CLI flow
opens the operator's own browser at the login URL — SentinelQA does
NOT harvest credentials, NOT bypass MFA, NOT touch CAPTCHA, NOT scrape
the LLM web UI for content generation.
"""

from __future__ import annotations

from typing import Final

from engine.auth.profiles.model import AuthProfile

# ---------------------------------------------------------------------------
# OAuth profiles
# ---------------------------------------------------------------------------

_GOOGLE_OAUTH = AuthProfile(
    name="google-oauth",
    label="Google OAuth (accounts.google.com)",
    login_url_pattern="https://accounts.google.com/signin",
    success_url_patterns=(
        "https://myaccount.google.com/",
        "https://accounts.google.com/CheckCookie",
    ),
    mfa_hint="Approve the sign-in on your trusted device or paste the 2-step code.",
    tos_url="https://policies.google.com/terms",
    category="oauth",
)

_GITHUB_OAUTH = AuthProfile(
    name="github-oauth",
    label="GitHub OAuth (github.com)",
    login_url_pattern="https://github.com/login",
    success_url_patterns=(
        "https://github.com/",
        "https://github.com/settings/",
    ),
    mfa_hint="Complete 2FA in your authenticator app or hardware key.",
    tos_url="https://docs.github.com/en/site-policy/github-terms/github-terms-of-service",
    category="oauth",
)

_MICROSOFT_ENTRA = AuthProfile(
    name="microsoft-entra",
    label="Microsoft Entra (login.microsoftonline.com)",
    login_url_pattern="https://login.microsoftonline.com/",
    success_url_patterns=(
        "https://portal.azure.com/",
        "https://office.com/",
        "https://www.microsoft365.com/",
    ),
    mfa_hint="Approve the sign-in in Microsoft Authenticator.",
    tos_url="https://www.microsoft.com/en-us/servicesagreement/",
    category="oauth",
)

# ---------------------------------------------------------------------------
# LLM-web profiles
#
# These exist so the operator can capture their OWN logged-in session in
# a consumer LLM web app — typically to audit a workflow they built on
# top of that platform (a Claude Project, a custom GPT, a Gemini
# extension). SentinelQA does NOT drive the LLM web UI for content
# generation; it audits what the user's authenticated workflow does.
# ---------------------------------------------------------------------------

_CLAUDE_AI = AuthProfile(
    name="claude-ai",
    label="Claude (claude.ai)",
    login_url_pattern="https://claude.ai/login",
    success_url_patterns=(
        "https://claude.ai/chats",
        "https://claude.ai/projects",
        "https://claude.ai/new",
    ),
    mfa_hint="Approve the email magic-link or complete 2FA if enabled.",
    tos_url="https://www.anthropic.com/legal/consumer-terms",
    category="llm-web",
)

_CHATGPT_WEB = AuthProfile(
    name="chatgpt-web",
    label="ChatGPT (chatgpt.com)",
    login_url_pattern="https://chatgpt.com/auth/login",
    success_url_patterns=(
        "https://chatgpt.com/",
        "https://chatgpt.com/c/",
    ),
    mfa_hint="Complete 2FA in your authenticator app if enabled.",
    tos_url="https://openai.com/policies/terms-of-use/",
    category="llm-web",
)

_CHATGPT_CODEX = AuthProfile(
    name="chatgpt-codex",
    label="ChatGPT Codex (chatgpt.com/codex)",
    login_url_pattern="https://chatgpt.com/auth/login",
    success_url_patterns=(
        "https://chatgpt.com/codex",
        "https://chatgpt.com/g/",
    ),
    mfa_hint="Complete 2FA if enabled. Codex routes via the same ChatGPT auth.",
    tos_url="https://openai.com/policies/terms-of-use/",
    category="llm-web",
)

_GOOGLE_GEMINI = AuthProfile(
    name="google-gemini",
    label="Google Gemini (gemini.google.com)",
    login_url_pattern="https://gemini.google.com/",
    success_url_patterns=(
        "https://gemini.google.com/app",
        "https://gemini.google.com/u/",
    ),
    mfa_hint="Approve the sign-in on your trusted Google device.",
    tos_url="https://policies.google.com/terms",
    category="llm-web",
)

_MISTRAL_LE_CHAT = AuthProfile(
    name="mistral-le-chat",
    label="Mistral Le Chat (chat.mistral.ai)",
    login_url_pattern="https://chat.mistral.ai/login",
    success_url_patterns=(
        "https://chat.mistral.ai/chat",
        "https://chat.mistral.ai/",
    ),
    mfa_hint="Complete 2FA in your authenticator app if enabled.",
    tos_url="https://mistral.ai/terms/",
    category="llm-web",
)


BUILTIN_PROFILES: Final[tuple[AuthProfile, ...]] = (
    _GOOGLE_OAUTH,
    _GITHUB_OAUTH,
    _MICROSOFT_ENTRA,
    _CLAUDE_AI,
    _CHATGPT_WEB,
    _CHATGPT_CODEX,
    _GOOGLE_GEMINI,
    _MISTRAL_LE_CHAT,
)


def profile_names() -> tuple[str, ...]:
    """Return the sorted set of profile names (for CLI completion)."""

    return tuple(sorted(p.name for p in BUILTIN_PROFILES))


__all__ = [
    "BUILTIN_PROFILES",
    "profile_names",
]

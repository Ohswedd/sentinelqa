# Task 31.04 — OAuth helper profiles (Google / GitHub / Microsoft)

## Deliverables

- `engine/auth/profiles/` is a Python package of **documented launcher
  recipes** for the three most common SSO shapes. A profile is a small
  dataclass with metadata only — there is no credential-handling code:
  ```python
  @dataclass(frozen=True)
  class AuthProfile:
      name: str               # "github-oauth"
      label: str              # "GitHub OAuth (github.com)"
      login_url_pattern: str  # "https://github.com/login"
      success_url_patterns: tuple[str, ...]  # what to wait for
      mfa_hint: str           # human-readable: "Complete 2FA in your authenticator app."
      tos_url: str            # link to the provider's ToS
  ```
- Built-in profiles:
  - `google-oauth` (accounts.google.com)
  - `github-oauth` (github.com/login)
  - `microsoft-entra` (login.microsoftonline.com)
- The profile is **used by the login flow** to (a) print the human
  banner with the right ToS link, (b) recognise when sign-in
  completed (URL match), (c) skip the "press Enter to capture" prompt
  when one of the `success_url_patterns` is reached.
- The profile is also surfaced by `sentinel auth list-profiles`.
- Profile selection is OPTIONAL — if the user does not pass `--profile`,
  the generic "press Enter when done" flow runs.

## Tests required

- `tests/unit/auth/test_profiles.py` — every built-in profile loads,
  has the four required URL fields populated, links resolve to known
  domains (sanity check; the test does NOT make network calls).

## Definition of Done

- [ ] Three profiles ship.
- [ ] Profiles never accept usernames, passwords, OAuth tokens, or any
      credential data structurally. Lint guard: an AST check on
      `engine/auth/profiles/` refuses fields with names matching
      `password|secret|token|key|credential|otp` (`tests/security/test_no_credentials_in_profiles.py`).
- [ ] `docs/dev/auth-profiles.md` documents how to add a custom profile.
- [ ] `STATUS.md` updated.

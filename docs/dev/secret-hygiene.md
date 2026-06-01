# Secret hygiene

Status: `Stable`

SentinelQA's product premise is trust through evidence. If we leak even one credential, we forfeit that premise. This document records the rules every contributor — human or agent — must follow.

The authority sources are our engineering rules(privacy & ownership) and our engineering rules(logging & secrets). our product spec lists the threat model.

## Rules (quoted from our engineering rules)

> Never log secrets.
>
> Redact: Passwords, Tokens, Cookies, Authorization headers, Session IDs, API keys, Private keys.
>
> Never commit `.env`, credentials, tokens, traces containing secrets, or real customer data.
>
> Provide `.env.example` only.

## How we enforce it

- **`.gitignore`** at the repo root forbids `.env`, `.env.*` (except `*.env.example`), `secrets.*`, `*.pem`, `*.key`, `id_rsa*`, `*.p12`, `*.pfx`, cloud credential blobs, and the SentinelQA runtime artifact tree (`.sentinel/`).
- **`.env.example`** at the repo root lists every environment variable SentinelQA reads, with safe placeholder values and one-line descriptions. Copy it to `.env` locally; never commit `.env`.
- **`pre-commit` hooks** (`/.pre-commit-config.yaml`): - `gitleaks` scans staged diffs for tokens, keys, and high-entropy strings. - `detect-private-key` from `pre-commit-hooks` blocks SSH/PGP private-key blocks. - `check-added-large-files` blocks anything over 2 MB. - `ruff` + `ruff-format` keep Python lint-clean (so secrets hidden in comments are also harder to slip in).
- **Pre-commit hook installation** is wired into `make install` (`make install-hooks`). New clones run `make install` before any other command.
- **CI** runs the same gitleaks scan on every PR (Phase 00.06).
- **Redaction primitives** live in `engine.policy.redaction` (stub today, full implementation in Phase 01) — the _only_ function any logger, report writer, or evidence collector should call before serializing untrusted strings.

## What to do if you find a leak

1. **Stop.** Don't push anything else from the affected branch.
2. Rotate the credential immediately at the issuing service. Treat any value pushed to a remote — even briefly — as compromised.
3. Open a `security/` branch and a private incident note (do **not** commit the leaked value while documenting).
4. If the leak landed in `main`, history rewrite is _not_ enough — assume the value was scraped. Rotation is the only mitigation.
5. Add the missing pattern to `gitleaks` config or the redaction rules so the next attempt is blocked at the hook layer.

## What to do if pre-commit blocks you legitimately

1. Read the hook output carefully — it tells you which rule fired and on which file.
2. If the value is a real secret: do not commit. Remove it, add it to `.env`, and reference it via `os.environ` / `process.env`.
3. If the value is a known false positive (e.g. a test fixture that matches an OpenAI key regex but is intentionally not a key): allowlist it via `gitleaks` baseline (`.gitleaks-baseline.json`) with a comment explaining _why_. Allowlisting in the config file is reviewable; bypassing the hook with `--no-verify` is not allowed (see our engineering rules).

## What never to do

- Commit a `.env` file.
- Paste a real secret into a commit message, PR title, comment, or issue body — those are mirrored everywhere.
- Print a secret to stdout/stderr without redaction.
- Bypass the pre-commit hook with `--no-verify` (forbidden by our engineering rules).
- Upload a SentinelQA trace, screenshot, or run artifact (`.sentinel/`) without auditing it for cookies, tokens, and personal data first (Phase 13 hardens this).

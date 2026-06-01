# LLM-web auth profiles

> Status: **Stable** (, ADR-0043).

SentinelQA ships five **LLM-web auth profiles** so operators can
audit logged-in workflows they built themselves on the consumer LLM
web surfaces. The profile is metadata only — it documents where to
sign in and where the login flow lands. SentinelQA does not drive the
LLM web UI for content generation, and it does not audit accounts
other than the operator's own.

| Profile           | App                 | Sign-in host        | Success URL pattern                            |
| ----------------- | ------------------- | ------------------- | ---------------------------------------------- |
| `claude-ai`       | claude.ai           | `claude.ai`         | `https://claude.ai/chats`, `/projects`, `/new` |
| `chatgpt-web`     | chatgpt.com         | `chatgpt.com`       | `https://chatgpt.com/`, `/c/`                  |
| `chatgpt-codex`   | chatgpt.com (Codex) | `chatgpt.com`       | `https://chatgpt.com/codex`, `/g/`             |
| `google-gemini`   | gemini.google.com   | `gemini.google.com` | `https://gemini.google.com/app`, `/u/`         |
| `mistral-le-chat` | chat.mistral.ai     | `chat.mistral.ai`   | `https://chat.mistral.ai/chat`, `/`            |

Each profile carries the provider's official Terms of Service link.
Run `sentinel auth list-profiles --json` to see the full structured
metadata.

---

## Authorized use cases

- **Audit your own ChatGPT plugin / custom GPT.** Does it leak PII? Does it refuse the things you instructed it to refuse? Does the loading state appear when it should?
- **Audit your own Claude Project workflow.** Internal Claude Projects sometimes touch internal data; SentinelQA can replay your authenticated session against the Project's URL and watch for finding-worthy behaviour.
- **Audit a Gemini extension you built.** Extensions run with your Workspace permissions; an audit against your own session catches bugs before your colleagues hit them.

---

## What this is NOT

- **Not a scraper.** SentinelQA does not pull conversations, prompts, responses, or generated content out of the LLM web UI.
- **Not a content generator.** SentinelQA does not send prompts to Claude / ChatGPT / Gemini / Le Chat to produce content.
- **Not an account-impersonation tool.** Auditing accounts other than your own — even with a teammate's explicit permission — is outside the use case these profiles document. Get an organization-scoped test account from your admin.
- **Not a bypass.** The captured session is the same session your browser holds. SentinelQA does not bypass MFA, does not touch CAPTCHA, does not evade rate limits, and does not hide its identity.

---

## Provider Terms of Service

Each profile links to the relevant ToS. The general principle every
provider in this list shares: **auditing your own account is
acceptable; auditing somebody else's account, scraping content for
redistribution, and using the platform in a way it wasn't designed
for are not.** Read the linked ToS for the platform you're targeting
before running an audit.

- Anthropic Consumer Terms — <https://www.anthropic.com/legal/consumer-terms>
- OpenAI Terms of Use — <https://openai.com/policies/terms-of-use/>
- Google Terms of Service — <https://policies.google.com/terms>
- Mistral Terms — <https://mistral.ai/terms/>

---

## Workflow

The capture flow is identical to the OAuth profiles documented in
[`docs/user/auth-flows.md`](../user/auth-flows.md):

```bash
sentinel auth login claude-projects \ --url https://claude.ai/login \ --profile claude-ai \ --ttl 12
```

After capture, point your audit config at the session:

```yaml
target: base_url: https://claude.ai/projects/<your-project-id> allowed_hosts: - claude.ai
auth: strategy: browser_session session_name: claude-projects
```

The materialized storage state is deleted on run teardown — including
on crash — so the cookies never outlive the audit.

For extending the profile catalogue with a new entry, see
[`docs/dev/auth-profiles.md`](auth-profiles.md). For the vault's
crypto and the runtime safety guards, see
[`docs/dev/auth-internals.md`](auth-internals.md).

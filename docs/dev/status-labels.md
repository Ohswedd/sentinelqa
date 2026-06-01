# Documentation status labels

Status: `Stable`

.

Every SentinelQA doc carries one of four status labels at the top so a reader can tell, at a glance, whether the doc describes something that exists, something in flight, something locked in, or something on its way out.

## The four labels

### `Planned`

The thing is documented but not yet built. The doc exists so contributors can see the design and plan around it; the code does not yet match.

**Examples:**

- `packages/python-sdk/README.md` until — "Real surface lands in."
- `apps/cli/README.md` until — "Real Typer app lands in."
- A new `docs/user/<feature>.md` written when the feature lands in `feature/...` but the code is not yet merged.

A `Planned` doc must reference the phase or PR that will move it to `Experimental` or `Stable`.

### `Experimental`

The thing is built and works in nominal cases, but the contract is unstable. Expect breaking changes between minor versions. Use at your own risk; opt-in via a flag where applicable.

**Examples:**

- The first version of the visual-regression module before tuning the diff threshold defaults.
- A new agent-facing MCP tool before's contract review.

An `Experimental` doc must name the conditions for promotion to `Stable` ("after 2 weeks of internal use without incident", "after the public review in PR #N").

### `Stable`

The thing is built, contract is locked, breaking changes require a major version bump. This is the default for production-quality features.

**Examples:**

- `docs/dev/secret-hygiene.md`, `docs/dev/branching.md`, `docs/dev/commits.md`, `docs/dev/ownership.md` — `Stable` already because the rules they document are non-negotiable.
- The CLI exit-code table from once the contract is locked.

A `Stable` doc has no required follow-up; it just gets maintained as the code evolves.

### `Deprecated`

The thing exists but should not be used in new code. A replacement (with a pointer) MUST be named.

**Examples:**

- An adapter that's been superseded by a more capable one but is kept for one release for compatibility.
- A CLI flag that's been replaced; the deprecation doc says what to use instead and when removal is scheduled.

A `Deprecated` doc must name the replacement and the removal version/date.

## How to label

Add a single line just under the title:

```markdown
# My Doc

Status: `Stable`
```

Use a backtick-wrapped label. No emoji, no badges, no color — the label is for humans and grep.

## Lifecycle

```
Planned → Experimental → Stable → Deprecated
```

You may skip from `Planned` straight to `Stable` (e.g. when the doc is a description of a static convention like `docs/dev/branching.md`). You may also drop a `Deprecated` doc to the archive once the deprecation window has elapsed (record the move in `CHANGELOG.md`).

## How to find docs by status

```bash
grep -Rln '^Status: `Planned`' docs apps packages engine modules
grep -Rln '^Status: `Experimental`' docs apps packages engine modules
grep -Rln '^Status: `Stable`' docs apps packages engine modules
grep -Rln '^Status: `Deprecated`' docs apps packages engine modules
```

The final-hardening audit confirms every Markdown file under those roots carries one of the four labels.

## What the label is NOT

- The label is not a CI gate today (it can become one if we add a markdown linter pass). It is a reader hint and a discipline.
- The label is not a feature flag. Feature flags live in `sentinel.config.yaml`.
- The label is not a substitute for the the documentation. Behavior changes still update our product spec.

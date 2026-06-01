# ADR-0039: Discovery + execution deterministic, planning LLM-augmented

## Status

Accepted

<!-- Date: 2026-05-30 -->
<!-- Authors: @ohswedd -->

## Context

our product spec Open Question #6 asked how much of the planner should be
deterministic versus LLM-based. The recommended answer was
"deterministic discovery, LLM planning, deterministic execution." The
shipped architecture follows that exactly:

- Discovery (, ADR-0010): pure-Python crawler, no LLM.
- Planner (, ADR-0011): eleven named deterministic extractors with an opt-in LLM refinement adapter.
- Generator (, ADR-0012): Jinja2 templates with strict undefined; no LLM.
- Runner (, ADR-0013): subprocess driver; no LLM.
- Analyzer (, ADR-0014): pure-function categorization with an optional one-sentence LLM refinement at the very end.

This ADR is one of the eight Phase-27 open-question ADRs.

## Decision

**Deterministic anywhere a wrong answer is hard to detect; LLM only
where the answer can be re-validated cheaply by a deterministic
step.** Concretely:

- **Discovery**: 100% deterministic. No LLM. Discovery output is the ground truth every later stage relies on.
- **Planner**: deterministic extractors produce a complete plan. Optional LLM adapter refines confidence / suggests tags / adds variants — but every LLM-suggested flow is re-validated against the deterministic extractor catalogue ( strict envelope validation). LLM failures fall back to the deterministic plan; the audit always proceeds.
- **Generator**: 100% deterministic. Jinja2 + StrictUndefined. No LLM. Generated specs are byte-stable across re-runs with the same inputs.
- **Runner**: 100% deterministic. Playwright + subprocess.
- **Analyzer**: deterministic categorization + repro generation; optional one-sentence LLM refinement (≤ 400 chars) appended at the very end. LLM failures degrade silently to deterministic output.

## Consequences

- **Positive:** every audit is reproducible by default. Two runs of the same target with the same config produce byte-identical `score.json` (enforced by a Hypothesis property test).
- **Positive:** LLM is additive, never load-bearing. Disabling the LLM (`Null<X>` defaults, `llm.enabled: false`) does not break any audit; it just removes the refinements.
- **Positive:** debugging is straightforward — the determinism floor makes flakiness visible immediately.
- **Negative / trade-off:** the deterministic floor caps how clever the planner can be without LLM help. Mitigated by the eleven extractors covering the common audit shapes (login, signup, CRUD, role, etc.).
- **Negative / trade-off:** the LLM cannot rescue a missing deterministic capability — it can only annotate one. Acceptable; that's the contract.
- **Follow-up obligations:** any future LLM-using module follows the same pattern — deterministic core + LLM annotation + deterministic fallback. No module becomes load-bearing on an LLM call.

## Alternatives considered

- **LLM-first planner.** Rejected — would make audits non-reproducible and would push the user into per-run cost decisions.
- **Deterministic-only.** Rejected — LLM refinements are genuinely useful for confidence scoring and one-sentence "why this failed" hints. Banning them sacrifices a real differentiator.

## References

- our product spec Open Question #6 + recommended answer
- the documentation Deterministic where possible
- Related ADRs: ADR-0010 (Discovery release), ADR-0011 (Planner), ADR-0012 (Generator conventions), ADR-0013 (Runner), ADR-0014 (Analyzer)

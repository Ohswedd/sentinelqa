# Task 34.05 — Compliance-pack policy DSL

## Deliverables

- `policy/compliance/` folder ships four ready-to-use packs:
  - `wcag-2.2-aa.yaml`
  - `gdpr-baseline.yaml`
  - `ccpa-baseline.yaml`
  - `soc2-trail.yaml`
- Pack shape (strict Pydantic):
  ```yaml
  pack:
    id: wcag-2.2-aa
    label: WCAG 2.2 AA (automated)
    description: ...
    version: 1
    includes:
      - module: accessibility
        options:
          axe_tags: [wcag2a, wcag2aa, wcag22a, wcag22aa]
      - module: accessibility
        checks: [focus_obscured, target_size_min]
    fail_on:
      - severity: critical
      - severity: high
    warn_on:
      - severity: medium
  ```
- `engine/policy/compliance.py` loads + validates a pack; the CLI
  exposes `sentinel audit --compliance-pack <id>` (auto-resolves to
  `policy/compliance/<id>.yaml`) and `sentinel audit
  --compliance-pack <path-to-yaml>` for custom packs.
- The pack can compose any module + any check; missing references
  fail at load time, not at run time.

## Tests required

- `tests/unit/policy/test_compliance_pack_loader.py` — valid +
  invalid pack fixtures.
- `tests/integration/cli/test_audit_with_compliance_pack.py` — `sentinel
  audit --compliance-pack wcag-2.2-aa` runs and produces the expected
  finding shape.

## Definition of Done

- [ ] Four built-in packs ship.
- [ ] DSL is strict (unknown keys rejected).
- [ ] Custom-pack YAML is documented in `docs/user/compliance-packs.md`.
- [ ] `STATUS.md` updated.

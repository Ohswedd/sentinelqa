# Task 05.04 — Forms inventory

## Objective

Inventory every form, capture its fields, action URL, method, and presence of submit handler + client-side validation.

## Deliverables

- `engine/discovery/forms.py` producing `Form` records with: id, route, action_url, method, fields[] (each with name, type, required, label, validation hints), submit_handler_present (bool), client_side_validation_present (bool), reCAPTCHA_present (bool — non-interaction; for Phase 19 to flag if found, since SentinelQA never bypasses CAPTCHA).
- Detection rules:
  - `submit_handler_present` — form has either `onSubmit` attribute, a JS listener (detect via TS-side `addEventListener` instrumentation), or an `action` URL.
  - `client_side_validation_present` — fields have `required`, `pattern`, `minlength`, `maxlength`, `type=email`, etc., or there are `aria-invalid` / `aria-describedby` references to error messages.

## Steps

1. Add a TS helper that walks the DOM and reports forms with the above details.
2. Python aggregates into `Form` records.
3. Persist `forms.json` under the run dir.
4. Cross-reference with API detection: forms that submit but never appear to call any API endpoint → flagged for Phase 19.

## Acceptance criteria

- Fixture login form fully captured.
- Form with no submit handler flagged.

## Tests required

- `tests/integration/discovery/test_forms.py`.

## PRD / CLAUDE.md references

- PRD §9.1, §10.9.
- CLAUDE.md §9, §31.

## Definition of Done

- [ ] Forms captured with all fields.
- [ ] Flags for missing submit / validation.
- [ ] Tests green.
- [ ] `STATUS.md` updated.

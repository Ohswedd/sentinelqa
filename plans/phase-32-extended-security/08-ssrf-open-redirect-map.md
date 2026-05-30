# Task 32.08 — SSRF / open-redirect surface map

## Deliverables

- `modules/security/checks/ssrf_redirect.py`. For each form field
  and query parameter the Phase 05 discovery module classified as
  URL-shaped (regex `^https?://` / `^//` / `^/[^/]`):
  - Submit a small fixed set of canonical "internal target"
    payloads:
    - `http://127.0.0.1/`
    - `http://localhost/`
    - `http://169.254.169.254/` (AWS / GCP metadata)
    - `http://[::1]/`
    - `file:///etc/passwd`
    - `gopher://127.0.0.1:6379/_PING%0a` (Redis canary)
  - If the server's response is anything other than a clean
    rejection (4xx OR a body that contains `Could not resolve`,
    `Invalid URL`, etc.), finding: `ssrf-suspected` (CWE-918;
    `severity: high`). Includes the request, the response status, and
    the response body's first 200 chars (redacted).
  - For open-redirect: send `//attacker.example.com` and
    `https://attacker.example.com.legit.com.allowedhost.example`. If
    the server emits a 30x with the attacker URL in `Location`,
    finding: `open-redirect` (CWE-601; `severity: medium`).
- Strict bounds: the payloads are a fixed list (no fuzzing); the
  check is gated behind `security.mode: authorized_destructive` AND
  `target.proof_of_authorization` is set (re-uses the same gate as
  task 32.05).

## Tests required

- `tests/unit/modules/security/test_ssrf_payloads.py` — verifies the
  payload list is fixed, no random generator anywhere.
- `tests/integration/modules/security/test_ssrf_against_stub.py` —
  stub server returns 200 for the metadata URL → finding fires.
- `tests/security/test_ssrf_requires_authorization.py` — refuses to
  run without the destructive-mode + PoA combo.

## Definition of Done

- [ ] Fixed payload list, no fuzzing.
- [ ] Gate respected.
- [ ] Findings reference CWE-918 / CWE-601.
- [ ] `STATUS.md` updated.

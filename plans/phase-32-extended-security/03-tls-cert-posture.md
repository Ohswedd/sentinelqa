# Task 32.03 — TLS / cert posture probe (read-only)

## Deliverables

- `modules/security/checks/tls_posture.py`. Read-only — uses Python's
  `ssl.SSLContext` to handshake against the configured host on port
  443 (or `target.port`), records:
  - TLS version (1.2 / 1.3; flag 1.0/1.1/SSLv3 as `severity: high`).
  - Negotiated cipher suite (flag `RC4`, `DES`, `3DES`, `NULL`, `EXP`
    suites; flag CBC suites with TLS 1.2 as `severity: medium`).
  - Cert chain — leaf cert SHA-256 fingerprint, issuer CN, expiry
    timestamp, SAN list. Flag certs expiring in < 14 days (`severity:
    medium`), already expired (`severity: critical`).
  - HSTS / `Strict-Transport-Security` header presence + `max-age`
    threshold (`severity: medium` if < 1 year).
- The check is **only** run against hosts on `target.allowed_hosts`
  (re-uses `SafetyPolicy.enforce`). No downgrade attacks, no cipher
  brute-forcing, no SSL-strip, no MITM.
- Findings carry `cwe_id` (CWE-326 weak crypto / CWE-295 cert
  validation), `attack_id` (`T1573` Encrypted Channel where weak
  ciphers fail).

## Tests required

- `tests/unit/modules/security/test_tls_posture_parse.py` — parser
  + rule logic; fixtures cover modern (1.3+ECDHE+AES-GCM) +
  weak (1.2+CBC) + ancient (1.0+RC4) handshakes.
- `tests/integration/modules/security/test_tls_against_loopback.py`
  (gated by a self-signed cert fixture) — handshakes against a local
  Python `ssl.wrap_socket` server.

## Definition of Done

- [ ] Probe is read-only; `tests/security/test_tls_no_downgrade.py`
      greps for any `socket.send` outside the handshake.
- [ ] Findings reference CWE-326 / CWE-295.
- [ ] `STATUS.md` updated.

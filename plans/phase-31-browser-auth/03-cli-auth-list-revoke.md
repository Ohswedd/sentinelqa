# Task 31.03 — `sentinel auth list|revoke|export`

## Deliverables

- `sentinel auth list [--host <host>] [--json]` — lists vault entries
  with redacted metadata only (name, host, created_at, expires_at,
  last_used_at, expired bool). Sorted by host then name.
- `sentinel auth revoke <name> [--host <host>] [--all]` — deletes the
  entry. `--all` deletes every entry; requires the operator to type
  `delete all` on stdin (no flag-only confirmation).
- `sentinel auth export <name> --host <host> --out <path>
  --i-acknowledge` — writes the plaintext `storage_state.json` to
  `<path>` so the operator can move it (e.g. to a teammate's machine).
  The `--i-acknowledge` flag is mandatory and the command prints a
  warning to stderr: "Plaintext session export. Treat the file like a
  password manager backup. Encrypt before sharing."
- All three respect `--ci`: `list` works (read-only metadata); `revoke
  --all` rejects without `--yes-i-mean-it`; `export` rejects in CI mode.
- Audit-log entries: `auth.list {count}`, `auth.revoke {host, name,
  expired}`, `auth.export {host, name, target_path, ack}`. Never log
  cookie values.

## Tests required

- `tests/integration/cli/test_auth_list.py` — JSON + human modes;
  empty + populated vault; expired flag.
- `tests/integration/cli/test_auth_revoke.py` — single, `--all`
  confirmation, `--ci` rejection of `--all`.
- `tests/integration/cli/test_auth_export.py` — `--i-acknowledge`
  required; export round-trip; `--ci` rejection.

## Definition of Done

- [ ] All three commands ship with JSON-mode support.
- [ ] Confirmation prompts cannot be bypassed by env / flag in `--ci`.
- [ ] `STATUS.md` updated.

#!/usr/bin/env bash
# Validate every numbered ADR under docs/adr/ against the canonical template.
#
# Required headings (in order, exactly as written below):
#   # ADR-NNNN: <title>
#   ## Status
#   ## Context
#   ## Decision
#   ## Consequences
#   ## Alternatives considered
#   ## References
#
# Exits 0 if all ADRs comply, 1 otherwise. Wired into `make adr-check` and
# .github/workflows/ci.yml (Phase 00.07).

set -euo pipefail

ADR_DIR="${1:-docs/adr}"

if [[ ! -d "$ADR_DIR" ]]; then
  echo "check-adrs: directory not found: $ADR_DIR" >&2
  exit 1
fi

REQUIRED_HEADINGS=(
  "^# ADR-[0-9]{4}: "
  "^## Status$"
  "^## Context$"
  "^## Decision$"
  "^## Consequences$"
  "^## Alternatives considered$"
  "^## References$"
)

failures=0
checked=0

while IFS= read -r -d '' file; do
  base="$(basename "$file")"
  # Skip the README and template themselves.
  if [[ "$base" == "README.md" || "$base" == "_template.md" ]]; then
    continue
  fi
  # Only validate files matching NNNN-*.md
  if [[ ! "$base" =~ ^[0-9]{4}-.*\.md$ ]]; then
    echo "WARN  $file: filename does not match NNNN-kebab-case.md; skipping" >&2
    continue
  fi

  checked=$((checked + 1))
  local_failures=0
  for heading in "${REQUIRED_HEADINGS[@]}"; do
    if ! grep -Eq "$heading" "$file"; then
      echo "FAIL  $file: missing required heading matching: $heading"
      local_failures=$((local_failures + 1))
    fi
  done
  if (( local_failures == 0 )); then
    echo "OK    $file"
  else
    failures=$((failures + 1))
  fi
done < <(find "$ADR_DIR" -maxdepth 1 -type f -name '*.md' -print0)

echo ""
echo "check-adrs: checked=$checked failed=$failures"
if (( failures > 0 )); then
  exit 1
fi

# SentinelQA — VS Code extension

Browse the latest [SentinelQA](https://github.com/Ohswedd/sentinelqa) audit
run's findings inside VS Code. Click any finding with a `code_ref` to jump
straight to the offending file and line. Right-click a fixable finding to
apply the repair proposal via `sentinel fix`.

## Features

- **Findings tree view** in the SentinelQA side bar — grouped by severity
  (critical → info), filtered to the latest run under `.sentinel/runs/`.
- **Jump to source** — clicking a finding opens the file at the offending
  line (`code_ref.path` + `code_ref.line`).
- **Apply fix proposal** — the inline wrench icon on a fixable finding
  runs `sentinel fix --apply --finding-id <id>` in the integrated
  terminal.
- **Refresh / Run audit** — toolbar actions for the SentinelQA view.

## Settings

- `sentinelqa.projectRoot` — override the project root (defaults to the
  first workspace folder).
- `sentinelqa.cliCommand` — command used to launch the SentinelQA CLI
  (default: `sentinel`). Useful when you launch via `uv run sentinel`.

## Requirements

- VS Code ≥ 1.86.
- `sentinelqa-cli` installed and on `$PATH`, or set
  `sentinelqa.cliCommand` to the right invocation.

## Install

The extension is published to the VS Code Marketplace under the
`Ohswedd.sentinelqa-vscode` identifier. To install locally during
development:

```bash
pnpm --filter sentinelqa-vscode build
code --install-extension ./dist
```

## License

Apache-2.0. See the repo root [LICENSE](../../LICENSE).

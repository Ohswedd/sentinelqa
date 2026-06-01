# SentinelQA — Browser extension

One-click "Audit this page" button for [SentinelQA](https://github.com/Ohswedd/sentinelqa).
The extension reads the active tab's URL and POSTs it to a local
SentinelQA MCP server over loopback (`127.0.0.1` / `localhost` /
`::1`) — never to a public host.

## How it works

1. You install the extension and pin its action button.
2. You start a local MCP server: `sentinel mcp --http --port 7333`.
3. You click the action button on any page; the popup shows the URL,
   the configured host (default `http://127.0.0.1`), and the port.
4. Click **Audit this page**. The popup posts a `sentinel.audit`
   JSON-RPC call to `http://127.0.0.1:7333/rpc`.
5. SentinelQA runs the full audit lifecycle and the popup shows the
   run ID + status. Open the report from your terminal with
   `sentinel report --latest`.

## Safety boundary

The extension enforces a loopback-only host allowlist
(`validateLoopbackTarget` in `src/loopback.ts`). Any URL that
resolves to a non-loopback host is refused before a request is sent:

- `127.0.0.1`, `localhost`, `::1` are accepted.
- `localhost.attacker.example` is refused.
- Schemes other than `http`/`https` are refused.
- Ports outside `1..65535` are refused.

The browser extension never talks to anything other than loopback.
The same safety boundary that protects `sentinel audit --url` (no
unauthorised targets) protects the extension.

## Settings

Stored in `chrome.storage.local`:

- `sentinelqa.mcp.host` — defaults to `http://127.0.0.1`.
- `sentinelqa.mcp.port` — defaults to `7333`.

## Install (developer)

```bash
pnpm --filter sentinelqa-browser build
# Then load apps/browser-extension/ as an unpacked extension via
# chrome://extensions → Developer mode → Load unpacked.
```

The public release ships through the Chrome Web Store and Firefox
Add-ons under the SentinelQA publisher.

## License

Apache-2.0. See the repo root [LICENSE](../../LICENSE).

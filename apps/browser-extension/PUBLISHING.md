# Publishing the SentinelQA browser extension

The extension publishes via
[`/.github/workflows/publish-browser-extension.yml`](../../.github/workflows/publish-browser-extension.yml).
The workflow:

1. fires on every `v*` tag push,
2. builds the manifest-v3 extension and packs a Chrome + Firefox zip,
3. attaches both zips to the GitHub Release,
4. generates an SLSA build-provenance attestation over the zips,
5. submits to the Chrome Web Store and Firefox AMO **when** the
   matching credentials are configured.

## Storefront credentials

The submission steps are gated on environment-level secrets so a human
owner manually approves each upload from the GitHub UI.

| Environment               | Secret                           | Variable               | Source                                                                                             |
| ------------------------- | -------------------------------- | ---------------------- | -------------------------------------------------------------------------------------------------- |
| `chrome-webstore-release` | `CHROME_WEB_STORE_CLIENT_ID`     |                        | Google Cloud project → OAuth client ID for "Chrome Web Store API"                                  |
| `chrome-webstore-release` | `CHROME_WEB_STORE_CLIENT_SECRET` |                        | Same OAuth client                                                                                  |
| `chrome-webstore-release` | `CHROME_WEB_STORE_REFRESH_TOKEN` |                        | One-time exchange following Google's [docs](https://developer.chrome.com/docs/webstore/using-api/) |
| `chrome-webstore-release` |                                  | `CHROME_EXTENSION_ID`  | Visible in the Chrome Web Store dev console once the listing exists                                |
| `firefox-amo-release`     | `FIREFOX_AMO_JWT_ISSUER`         |                        | https://addons.mozilla.org/en-US/developers/addon/api/key/                                         |
| `firefox-amo-release`     | `FIREFOX_AMO_JWT_SECRET`         |                        | Same page                                                                                          |
| `firefox-amo-release`     |                                  | `FIREFOX_EXTENSION_ID` | The `id` field in `manifest.json`'s `browser_specific_settings.gecko`                              |

When `vars.CHROME_EXTENSION_ID` or `vars.FIREFOX_EXTENSION_ID` is
empty, the corresponding submission job skips with `if: ${{ vars.X != '' }}`.
The build + zip + release-asset steps always run.

## First-time setup

1. Create the listings in the Chrome Web Store dev console and the
   Firefox AMO developer hub. Upload the v1.11.0 zips manually for
   the very first submission.
2. After both listings exist, populate the environment variables and
   secrets in **Settings → Environments**.
3. The next tag push triggers the full pipeline.

## Local sanity check

You can dry-run the packaging step from a clean checkout:

```bash
pnpm --filter sentinelqa-browser run build
( cd apps/browser-extension && zip -r /tmp/extension.zip manifest.json popup.html dist icons )
```

The zip is acceptable on both stores (Firefox accepts any well-formed
manifest v3 zip; Chrome only needs the manifest at the root).

## Status

The workflow ships in v1.11.0 with all steps wired. The two
submission jobs idle behind environment guards until the maintainer
populates the storefront credentials.

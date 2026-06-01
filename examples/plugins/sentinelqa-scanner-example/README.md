# sentinelqa-scanner-example

A reference SentinelQA scanner plugin that demonstrates the smallest
viable scanner: it checks the target URL for the `X-Frame-Options`
header and emits a single `low`-severity finding when it's missing.

## Install (editable, for local development)

```bash
pip install -e examples/plugins/sentinelqa-scanner-example
```

The package registers an entry point under
`sentinelqa.plugins`, so `sentinel plugins list` will surface it after
install:

```text
$ sentinel plugins list
header-checker 0.1.0 scanner (header-checker)
```

## Manifest

The plugin declares the four required attributes plus a semver range
against `sentinelqa.plugins.PROTOCOL_VERSION`:

```python
class HeaderChecker: kind = "scanner" name = "header-checker" version = "0.1.0" capabilities = frozenset({"http_check"}) permissions = frozenset({"network.outbound", "fs.write:.sentinel/runs"}) requires_protocol = ">=1.0,<2.0"
```

`capabilities` is a free-form tag set; `permissions` is the runtime
permission grant set (see `docs/dev/plugin-permissions.md`). The
loader rejects any plugin declaring a capability on the SentinelQA
forbidden list .

## Run the tests

```bash
pytest tests/integration/plugins/test_example_scanner.py
```

The tests monkeypatch `HeaderChecker._fetch` so they stay hermetic —
no real network access required.

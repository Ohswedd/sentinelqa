# sentinelqa-reporter-example

A reference SentinelQA reporter plugin that writes a small CSV summary
of the run's findings. Demonstrates the minimal `ReporterPlugin`
surface: declare `formats`, implement `emit(result, context)`, and
return `{format_name: path}`.

## Install (editable, for local development)

```bash
pip install -e examples/plugins/sentinelqa-reporter-example
```

`sentinel plugins list` will surface it once installed:

```text
$ sentinel plugins list
csv-reporter  0.1.0  reporter  (csv)
```

## Manifest

```python
class CsvReporter:
    kind = "reporter"
    name = "csv-reporter"
    version = "0.1.0"
    capabilities = frozenset({"report"})
    permissions = frozenset({"fs.write:.sentinel/runs"})
    requires_protocol = ">=1.0,<2.0"
    formats = ("csv",)
```

The single declared permission is `fs.write:.sentinel/runs`; the
plugin writes via `context.artifact_path(...)` which confines the
output under `<run_dir>/plugins/<name>/`.

## Run the tests

```bash
pytest tests/integration/plugins/test_example_reporter.py
```

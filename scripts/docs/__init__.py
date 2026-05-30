"""Documentation generators for the SentinelQA docs site (apps/docs/).

Every generator in this package is deterministic and idempotent: running it
twice against an unchanged source produces a byte-identical output file.
The freshness CI guard relies on that contract (see
``tests/integration/docs/test_generated_docs_fresh.py``).
"""

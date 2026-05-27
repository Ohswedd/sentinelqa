"""Allow ``python -m sentinel_cli`` to invoke the same entry point."""

from __future__ import annotations

import sys

from sentinel_cli.main import main

if __name__ == "__main__":
    sys.exit(main())

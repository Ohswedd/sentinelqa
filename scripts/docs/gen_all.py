"""Run every docs generator. Used by ``make docs-gen-all``."""

from __future__ import annotations

from scripts.docs import (
    gen_adr_index,
    gen_cli_status,
    gen_error_codes,
    gen_mcp_reference,
    gen_sdk_reference,
)


def main() -> int:
    rc = 0
    for module in (
        gen_error_codes,
        gen_cli_status,
        gen_sdk_reference,
        gen_mcp_reference,
        gen_adr_index,
    ):
        rc |= module.main()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

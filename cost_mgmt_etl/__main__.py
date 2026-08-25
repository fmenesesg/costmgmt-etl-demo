"""CLI: python -m cost_mgmt_etl"""

from __future__ import annotations

import sys

from cost_mgmt_etl.stack import main as stack_main


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] == "stack":
        return stack_main(args[1:])
    if args:
        return stack_main(args)
    sys.stdout.write(
        "usage: python -m cost_mgmt_etl stack compose.yaml\n"
        "Set HCC env and ORACLE_* then run the daily job from cost_mgmt_etl.jobs.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""CLI entry point for neotrade.

Handlers live in :mod:`neotrade.cli`. This module is the console-script surface
and re-exports symbols tests may patch.
"""

from __future__ import annotations

from neotrade.broker import (
    AlpacaPaperClient,
    assert_execute_allowed,
    build_trade_plan,
)
from neotrade.cli.broker_cmds import cmd_paper_execute as _cmd_paper_execute
from neotrade.cli.common import DEFAULT_MODEL_PATH, cmd_version as _cmd_version, log
from neotrade.cli.common import load_signals_for_paper as _load_signals_for_paper
from neotrade.cli.parser import build_parser
from neotrade.logging_config import setup_logging

__all__ = [
    "main",
    "build_parser",
    "_cmd_paper_execute",
    "_load_signals_for_paper",
    "assert_execute_allowed",
    "AlpacaPaperClient",
    "build_trade_plan",
    "DEFAULT_MODEL_PATH",
]


def main(argv: list[str] | None = None) -> None:
    """Parse CLI args and dispatch to the selected subcommand handler."""
    setup_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        raise SystemExit(_cmd_version(args))
    if args.command is None:
        _cmd_version(args)
        parser.print_help()
        raise SystemExit(0)
    log.debug("dispatch command=%s", args.command)
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()

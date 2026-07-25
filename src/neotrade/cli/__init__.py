"""CLI package: handlers + argparse (console script surface)."""

from neotrade.cli.parser import build_parser
from neotrade.cli.common import cmd_version

__all__ = ["build_parser", "cmd_version"]

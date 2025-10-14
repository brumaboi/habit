from __future__ import annotations

import sys
import argparse
from . import __version__

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="habit", description="Habit CLI (skeleton)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    # to implement subcommands, e.g.: add, list, remove, done etc.
    return parser

def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    print(f"[stub] {args.cmd} -> {vars(args)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
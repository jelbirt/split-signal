"""Command-line entry point for Split-Signal.

Subcommands:
    ingest  Build/refresh the local data cache for a universe.
    score   Compute the predictability index for one or more tickers.
    scan    Score every ticker in a watchlist file.

`score` and `scan` are stubs until the Phase A methodology is validated
(see SPEC.md); they currently explain their status and exit non-zero.
"""

from __future__ import annotations

import argparse
import sys

from split_signal import DISCLAIMER, __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="split-signal",
        description="Stock split predictability index (research tool).",
        epilog=DISCLAIMER,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest", help="build/refresh the local data cache")
    ingest.add_argument(
        "--universe",
        default="sp500-plus-splitters",
        help="universe to ingest (default: sp500-plus-splitters)",
    )
    ingest.add_argument(
        "--data-dir",
        default="data",
        help="root directory for raw/processed data (default: ./data)",
    )

    score = subparsers.add_parser("score", help="score tickers with the predictability index")
    score.add_argument("tickers", nargs="+", metavar="TICKER")

    scan = subparsers.add_parser("scan", help="score every ticker in a watchlist file")
    scan.add_argument("--watchlist", required=True, help="path to a newline-separated ticker file")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "ingest":
        from split_signal.data.ingest import run_ingest

        return run_ingest(universe=args.universe, data_dir=args.data_dir)

    # Phase B stubs — methodology gate (task A8) not passed yet.
    print(DISCLAIMER, file=sys.stderr)
    print(
        f"'{args.command}' is not available yet: the scoring methodology is still "
        "in research (Phase A). See tasks/todo.md.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())

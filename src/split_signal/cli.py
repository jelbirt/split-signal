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
from pathlib import Path

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

    score = subparsers.add_parser("score", help="score tickers with the Split Likelihood Index")
    score.add_argument("tickers", nargs="+", metavar="TICKER")
    score.add_argument("--data-dir", default="data")
    score.add_argument("--artifact", default=None, help="alternate model artifact path")

    scan = subparsers.add_parser("scan", help="score every ticker in a watchlist file")
    scan.add_argument("--watchlist", required=True, help="path to a newline-separated ticker file")
    scan.add_argument("--data-dir", default="data")
    scan.add_argument("--artifact", default=None, help="alternate model artifact path")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "ingest":
        from split_signal.data.ingest import run_ingest

        return run_ingest(universe=args.universe, data_dir=args.data_dir)

    from split_signal.scoring.likelihood import LikelihoodArtifact
    from split_signal.scoring.score import ScoreRefusal, format_score, score_ticker

    artifact = LikelihoodArtifact.load(args.artifact) if args.artifact \
        else LikelihoodArtifact.load()

    if args.command == "score":
        tickers = [t.upper() for t in args.tickers]
    else:  # scan
        watchlist = Path(args.watchlist).read_text().split()
        tickers = [t.strip().upper() for t in watchlist if t.strip()]

    scores, refusals = [], []
    for ticker in tickers:
        try:
            scores.append(score_ticker(args.data_dir, ticker, artifact=artifact))
        except ScoreRefusal as exc:
            refusals.append(str(exc))

    scores.sort(key=lambda s: -s.index)
    for score in scores:
        print(format_score(score))
        print()
    for refusal in refusals:
        print(f"REFUSED: {refusal}", file=sys.stderr)
    print(
        f"[model {artifact.version}, trained through {artifact.trained_through}] "
        "The index predicts the split EVENT only; Phase A research found no "
        "expected excess return from splits (docs/METHODOLOGY.md).",
        file=sys.stderr,
    )
    print(DISCLAIMER, file=sys.stderr)
    return 0 if scores else 1


if __name__ == "__main__":
    sys.exit(main())

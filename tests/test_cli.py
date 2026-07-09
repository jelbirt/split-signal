"""CLI surface tests: subcommands exist and --help works."""

import subprocess
import sys

import pytest

from split_signal.cli import build_parser


def test_parser_has_expected_subcommands() -> None:
    parser = build_parser()
    subparsers_action = next(
        a for a in parser._actions if a.dest == "command"  # noqa: SLF001
    )
    assert set(subparsers_action.choices) == {"ingest", "score", "scan"}


@pytest.mark.parametrize("command", ["ingest", "score", "scan"])
def test_subcommand_help_exits_zero(command: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "split_signal.cli", command, "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert command in result.stdout


def test_score_requires_tickers() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "split_signal.cli", "score"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


def test_output_carries_disclaimer() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "split_signal.cli", "score", "AAPL"],
        capture_output=True,
        text=True,
    )
    assert "not financial advice" in (result.stdout + result.stderr).lower()

"""Append dated sections to the data-quality log (docs/DATA_QUALITY.md)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

DEFAULT_LOG = Path("docs") / "DATA_QUALITY.md"


def append_report(log_path: str | Path, title: str, lines: list[str]) -> None:
    log = Path(log_path)
    log.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    body = "\n".join(f"- {line}" for line in lines)
    with log.open("a") as fh:
        fh.write(f"\n## {stamp} — {title}\n\n{body}\n")

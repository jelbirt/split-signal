"""Ingestion orchestrator. Filled in across tasks A1-A4."""

from __future__ import annotations

import sys


def run_ingest(universe: str, data_dir: str) -> int:
    print(
        f"ingest: universe '{universe}' -> {data_dir}/ (pipeline lands in tasks A1-A4)",
        file=sys.stderr,
    )
    return 2

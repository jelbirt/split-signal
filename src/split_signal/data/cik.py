"""SEC CIK <-> ticker mapping (https://www.sec.gov/files/company_tickers.json)."""

from __future__ import annotations

import pandas as pd
import requests

from split_signal.data.universe import USER_AGENT, normalize_symbol

CIK_MAP_URL = "https://www.sec.gov/files/company_tickers.json"


def parse_cik_map(payload: dict) -> pd.DataFrame:
    rows = [
        {
            "ticker": normalize_symbol(entry["ticker"]),
            "cik": int(entry["cik_str"]),
            "title": entry.get("title", ""),
        }
        for entry in payload.values()
    ]
    return pd.DataFrame(rows).drop_duplicates(subset="ticker").reset_index(drop=True)


def fetch_cik_map(session: requests.Session | None = None) -> pd.DataFrame:
    session = session or requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    response = session.get(CIK_MAP_URL, timeout=30)
    response.raise_for_status()
    return parse_cik_map(response.json())

"""Universe construction: S&P 500 constituents + full US-listed common stock.

Sources (all free):
- Wikipedia "List of S&P 500 companies" (current members, sector, CIK)
- NASDAQ Trader symbol directories (nasdaqlisted.txt / otherlisted.txt)

Parsers are pure (tested offline against fixtures); network access is
confined to the fetch_* functions. Known limitation, logged rather than
hidden: these sources cover *currently listed* names only, so delisted
splitters are invisible here (survivorship bias — see docs/DATA_QUALITY.md).
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import pandas as pd
import requests

SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt"

USER_AGENT = "split-signal-research/0.1 (personal research; jelbirt.consult@gmail.com)"

# NASDAQ Trader exchange codes for otherlisted.txt
_EXCHANGE_CODES = {
    "N": "NYSE",
    "A": "NYSE American",
    "P": "NYSE Arca",
    "Z": "Cboe BZX",
    "V": "IEX",
}

# Security-name patterns that indicate non-common-stock instruments.
_NON_COMMON_NAME = re.compile(
    r"preferred|warrant|\brights?\b|\bunits?\b|depositary|%|due\s+\d{4}",
    re.IGNORECASE,
)


def normalize_symbol(symbol: str) -> str:
    """Normalize to yfinance-style symbols (class shares use dashes: BRK.B -> BRK-B)."""
    return re.sub(r"[.$= ]", "-", symbol.strip())


def _common_stock_mask(names: pd.Series) -> pd.Series:
    return ~names.fillna("").str.contains(_NON_COMMON_NAME)


def parse_nasdaq_listed(text: str) -> pd.DataFrame:
    raw = pd.read_csv(io.StringIO(text), sep="|", dtype=str)
    raw = raw.dropna(subset=["Symbol"])
    raw = raw[~raw["Symbol"].str.startswith("File Creation")]
    keep = (
        (raw["Test Issue"] == "N")
        & (raw["ETF"] != "Y")
        & _common_stock_mask(raw["Security Name"])
    )
    out = raw.loc[keep, ["Symbol", "Security Name"]].rename(
        columns={"Symbol": "symbol", "Security Name": "name"}
    )
    out["symbol"] = out["symbol"].map(normalize_symbol)
    out["exchange"] = "NASDAQ"
    return out.reset_index(drop=True)


def parse_other_listed(text: str) -> pd.DataFrame:
    raw = pd.read_csv(io.StringIO(text), sep="|", dtype=str)
    raw = raw.dropna(subset=["ACT Symbol"])
    raw = raw[~raw["ACT Symbol"].str.startswith("File Creation")]
    keep = (
        (raw["Test Issue"] == "N")
        & (raw["ETF"] != "Y")
        & _common_stock_mask(raw["Security Name"])
    )
    out = raw.loc[keep, ["ACT Symbol", "Security Name", "Exchange"]].rename(
        columns={"ACT Symbol": "symbol", "Security Name": "name", "Exchange": "exchange"}
    )
    out["symbol"] = out["symbol"].map(normalize_symbol)
    out["exchange"] = out["exchange"].map(_EXCHANGE_CODES).fillna(out["exchange"])
    return out.reset_index(drop=True)


def parse_sp500_html(html: str) -> pd.DataFrame:
    tables = pd.read_html(io.StringIO(html))
    constituents = next(
        t for t in tables if {"Symbol", "GICS Sector"} <= set(map(str, t.columns))
    )
    out = constituents.rename(
        columns={
            "Symbol": "symbol",
            "Security": "name",
            "GICS Sector": "gics_sector",
            "CIK": "cik",
        }
    )[["symbol", "name", "gics_sector", "cik"]].copy()
    out["symbol"] = out["symbol"].astype(str).map(normalize_symbol)
    out["cik"] = out["cik"].astype(int)
    return out.reset_index(drop=True)


def build_universe(sp500: pd.DataFrame, listed: list[pd.DataFrame]) -> pd.DataFrame:
    """Merge listing directories with S&P 500 membership.

    S&P members absent from the listing files are still included (with
    exchange unknown) so index coverage never silently shrinks.
    """
    all_listed = (
        pd.concat(listed, ignore_index=True)
        .drop_duplicates(subset="symbol", keep="first")
        .set_index("symbol")
    )
    sp = sp500.set_index("symbol")

    universe = all_listed.join(sp[["gics_sector", "cik"]], how="outer")
    universe["name"] = universe["name"].fillna(sp["name"])
    universe["in_sp500"] = universe.index.isin(sp.index)
    return universe.reset_index().rename(columns={"index": "symbol"})


def fetch_universe(session: requests.Session | None = None) -> pd.DataFrame:
    session = session or requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    sp500 = parse_sp500_html(session.get(SP500_URL, timeout=30).text)
    nasdaq = parse_nasdaq_listed(session.get(NASDAQ_LISTED_URL, timeout=30).text)
    other = parse_other_listed(session.get(OTHER_LISTED_URL, timeout=30).text)
    return build_universe(sp500=sp500, listed=[nasdaq, other])


def save_universe(universe: pd.DataFrame, data_dir: str | Path) -> Path:
    out_path = Path(data_dir) / "processed" / "universe.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    universe.to_parquet(out_path, index=False)
    return out_path

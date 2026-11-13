"""Fetches prices, company financials, news and mutual fund NAVs.

Sources (all free, no login):
  - Yahoo Finance via yfinance: NSE prices and company numbers (prices ~15 min delayed)
  - Google News RSS: recent headlines for a company
  - mfapi.in: daily NAV for Indian mutual funds
"""
from __future__ import annotations

import json
import time
from pathlib import Path
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

import feedparser
import pandas as pd
import yfinance as yf


def nse(symbol: str) -> str:
    """'HDFCBANK' -> 'HDFCBANK.NS'. Leaves index tickers like ^NSEI alone."""
    s = symbol.strip().upper()
    if s.startswith("^") or s.endswith(".NS") or s.endswith(".BO"):
        return s
    return f"{s}.NS"


@dataclass
class StockSnapshot:
    symbol: str
    name: str
    sector: str | None
    price: float | None
    prev_close: float | None
    info: dict = field(default_factory=dict)
    history: pd.DataFrame = field(default_factory=pd.DataFrame)  # daily, ~5 years
    error: str | None = None

    @property
    def day_change_pct(self) -> float | None:
        if self.price and self.prev_close:
            return (self.price / self.prev_close - 1) * 100
        return None

    def change_over(self, days: int) -> float | None:
        """% change over the last `days` trading days."""
        h = self.history
        if h.empty or len(h) <= days:
            return None
        old = float(h["Close"].iloc[-days - 1])
        return (float(h["Close"].iloc[-1]) / old - 1) * 100 if old else None


CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache" / "info"
INFO_MAX_AGE = 24 * 3600  # company financials change slowly; refetch once a day


def _company_info(t: yf.Ticker, sym: str) -> tuple[dict, bool]:
    """Company financials, kept on disk for a day so Yahoo isn't asked too often.
    Returns (info, fetched_just_now). Falls back to an older saved copy if Yahoo refuses."""
    path = CACHE_DIR / f"{sym.replace('^', '_')}.json"
    saved = None
    if path.exists():
        try:
            saved = json.loads(path.read_text())
        except Exception:
            saved = None
        if saved and time.time() - saved.get("_saved_at", 0) < INFO_MAX_AGE:
            return saved, False
    try:
        info = t.info or {}
    except Exception:
        info = {}
    if info.get("longName") or info.get("shortName"):
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({**info, "_saved_at": time.time()}, default=str))
        except Exception:
            pass
        return info, True
    return (saved or {}), False


def get_stock(symbol: str) -> StockSnapshot:
    sym = nse(symbol)
    t = yf.Ticker(sym)
    try:
        hist = t.history(period="5y", interval="1d", auto_adjust=True)
    except Exception as e:  # network or Yahoo hiccup
        return StockSnapshot(sym, symbol, None, None, None, error=f"Price data unavailable: {e}")
    hist = hist.dropna(subset=["Close"])
    if hist.empty:
        return StockSnapshot(sym, symbol, None, None, None,
                             error=f"No data found for {symbol}. Check the NSE symbol (e.g. HDFCBANK, INFY).")
    info, fresh = _company_info(t, sym)
    price = float(hist["Close"].iloc[-1])
    prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else None
    # Prefer Yahoo's live quote when we just fetched it (intraday)
    if fresh and info.get("currentPrice"):
        price = float(info["currentPrice"])
    if fresh and info.get("previousClose"):
        prev = float(info["previousClose"])
    name = info.get("longName") or info.get("shortName") or symbol
    for suffix in (" Limited", " Ltd.", " Ltd"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return StockSnapshot(
        symbol=sym,
        name=name,
        sector=info.get("sector"),
        price=price,
        prev_close=prev,
        info=info,
        history=hist,
    )


def get_index(ticker: str = "^NSEI") -> dict:
    """Latest level, day change and a 3-month series for an index (default Nifty 50)."""
    try:
        h = yf.Ticker(ticker).history(period="3mo", interval="1d").dropna(subset=["Close"])
        last, prev = float(h["Close"].iloc[-1]), float(h["Close"].iloc[-2])
        month_ago = float(h["Close"].iloc[-22]) if len(h) > 22 else float(h["Close"].iloc[0])
        return {"level": last, "change_pct": (last / prev - 1) * 100,
                "month_pct": (last / month_ago - 1) * 100,
                "series": [float(x) for x in h["Close"].tail(60)]}
    except Exception:
        return {}


def get_mf_history(scheme_code: str) -> pd.Series:
    """Full NAV history of a mutual fund, indexed by date (oldest first)."""
    try:
        with urllib.request.urlopen(f"https://api.mfapi.in/mf/{scheme_code}", timeout=20) as r:
            j = json.load(r)
        df = pd.DataFrame(j["data"])
        s = pd.Series(df["nav"].astype(float).values,
                      index=pd.to_datetime(df["date"], format="%d-%m-%Y"))
        return s.sort_index()
    except Exception:
        return pd.Series(dtype=float)


@dataclass
class NewsItem:
    title: str
    link: str
    source: str
    published: str


def get_news(company_name: str, limit: int = 8) -> list[NewsItem]:
    """Recent India-focused headlines about a company from Google News."""
    clean = company_name.replace("Limited", "").replace("Ltd.", "").replace("Ltd", "").strip()
    q = urllib.parse.quote(f'"{clean}" share OR stock OR results when:30d')
    url = f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        feed = feedparser.parse(url)
    except Exception:
        return []
    items = []
    for e in feed.entries[:limit]:
        title = e.get("title", "")
        source = e.get("source", {}).get("title", "") if isinstance(e.get("source"), dict) else ""
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3]
        items.append(NewsItem(title, e.get("link", ""), source, e.get("published", "")[:16]))
    return items


def get_mf_nav(scheme_code: str) -> tuple[float | None, str | None, str | None]:
    """(latest NAV, date, scheme name) for an Indian mutual fund from mfapi.in."""
    try:
        with urllib.request.urlopen(f"https://api.mfapi.in/mf/{scheme_code}/latest", timeout=15) as r:
            j = json.load(r)
        d = j["data"][0]
        return float(d["nav"]), d["date"], j.get("meta", {}).get("scheme_name")
    except Exception:
        return None, None, None


def search_mutual_funds(query: str, limit: int = 15) -> list[dict]:
    """Search Indian mutual funds by name. Returns [{'schemeCode':..., 'schemeName':...}]."""
    try:
        url = "https://api.mfapi.in/mf/search?q=" + urllib.parse.quote(query)
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.load(r)[:limit]
    except Exception:
        return []

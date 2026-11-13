"""Loads and saves your portfolio, watchlist and settings.

Files live in the data/ folder. When GITHUB_TOKEN and GITHUB_REPO are set in Streamlit secrets,
saving from the app also commits the file to your GitHub repo, so changes survive app restarts
and the daily alert job sees them.
"""
from __future__ import annotations

import base64
import io
import json
import os
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

PORTFOLIO_COLS = ["type", "symbol", "name", "quantity", "avg_price", "scheme_code", "invested"]
WATCHLIST_COLS = ["symbol", "note"]

DEFAULT_SETTINGS = {
    "monthly_sip": 5000,
    "sip_day": 15,
    "target_stock_share": 25,
    "example_data": True,
}


def _secret(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    try:
        import streamlit as st
        return st.secrets.get(name)
    except Exception:
        return None


def load_portfolio() -> pd.DataFrame:
    p = DATA / "portfolio.csv"
    df = pd.read_csv(p) if p.exists() else pd.DataFrame(columns=PORTFOLIO_COLS)
    for c in PORTFOLIO_COLS:
        if c not in df.columns:
            df[c] = None
    df = df[PORTFOLIO_COLS]
    df["type"] = df["type"].fillna("stock").str.lower().str.strip()
    for c in ["quantity", "avg_price", "invested"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["scheme_code"] = df["scheme_code"].astype("string").str.replace(r"\.0$", "", regex=True)
    return df


def load_watchlist() -> pd.DataFrame:
    p = DATA / "watchlist.csv"
    df = pd.read_csv(p) if p.exists() else pd.DataFrame(columns=WATCHLIST_COLS)
    for c in WATCHLIST_COLS:
        if c not in df.columns:
            df[c] = ""
    return df[WATCHLIST_COLS].fillna("")


def load_settings() -> dict:
    p = DATA / "settings.json"
    s = dict(DEFAULT_SETTINGS)
    if p.exists():
        s.update(json.loads(p.read_text()))
    return s


def _commit_to_github(rel_path: str, content: str, message: str) -> str:
    token, repo = _secret("GITHUB_TOKEN"), _secret("GITHUB_REPO")
    if not (token and repo):
        return "saved for this session (add GITHUB_TOKEN and GITHUB_REPO secrets to make saves permanent)"
    api = f"https://api.github.com/repos/{repo}/contents/{rel_path}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    sha = None
    try:
        with urllib.request.urlopen(urllib.request.Request(api, headers=headers), timeout=15) as r:
            sha = json.load(r).get("sha")
    except Exception:
        pass
    body = {"message": message, "content": base64.b64encode(content.encode()).decode()}
    if sha:
        body["sha"] = sha
    req = urllib.request.Request(api, data=json.dumps(body).encode(), headers=headers, method="PUT")
    try:
        urllib.request.urlopen(req, timeout=20)
        return "saved permanently to GitHub"
    except Exception as e:
        return f"saved for this session, but GitHub save failed: {e}"


def _save(rel_path: str, content: str, message: str) -> str:
    (ROOT / rel_path).write_text(content)
    return _commit_to_github(rel_path, content, message)


def save_portfolio(df: pd.DataFrame) -> str:
    buf = io.StringIO()
    df[PORTFOLIO_COLS].to_csv(buf, index=False)
    return _save("data/portfolio.csv", buf.getvalue(), "Update portfolio from app")


def save_watchlist(df: pd.DataFrame) -> str:
    buf = io.StringIO()
    df[WATCHLIST_COLS].to_csv(buf, index=False)
    return _save("data/watchlist.csv", buf.getvalue(), "Update watchlist from app")


def save_settings(s: dict) -> str:
    return _save("data/settings.json", json.dumps(s, indent=2) + "\n", "Update settings from app")

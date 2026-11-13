"""Gold savings scheme tracker (jeweller monthly plan).

How the scheme works (as described by the user):
  - Pay a fixed amount every month for N months (default ₹15,000 × 12).
  - Each payment buys 24K grams at that day's rate; those grams are locked in.
  - Missing one month is OK if you pay double the next month. Missing 2+ months in a row ends the
    scheme (the jeweller returns the money, without the gold-rate benefit).
  - After the last month, the grams can be taken as jewellery (or anything else). Making charges
    depend on the product, and 3% GST is charged at the time of purchase.

Today's gold price: there's no free official feed for jewellers' Indian rates, so we take the
international 24K price in rupees (Yahoo: gold futures × USD/INR) and scale it by the gap between
your jeweller's rate and that international price on your latest payment date. You can also type
today's jeweller rate yourself, which overrides the estimate.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass

import pandas as pd
import yfinance as yf

from . import storage

TROY_OUNCE_G = 31.1035
GST_PCT = 3.0

DEFAULT_PLAN = {
    "jeweller": "",
    "monthly_amount": 15000,
    "months": 12,
    "start_month": "",          # "YYYY-MM" of the first payment
    "due_day": 10,              # day of month you usually pay
    "karat": 24,
    "making_charge_pct": 8.0,   # varies by product; adjustable in the app
    "manual_rate_today": None,  # optional: jeweller's rate today, ₹/gram
}

PAYMENT_COLS = ["date", "amount", "rate_per_g", "grams", "receipt_no"]


# ---------- storage ----------
def load_plan() -> dict:
    p = storage.DATA / "gold_plan.json"
    plan = dict(DEFAULT_PLAN)
    if p.exists():
        plan.update(json.loads(p.read_text()))
    return plan


def save_plan(plan: dict) -> str:
    return storage._save("data/gold_plan.json", json.dumps(plan, indent=2) + "\n", "Update gold plan from app")


def load_payments() -> pd.DataFrame:
    p = storage.DATA / "gold_payments.csv"
    df = pd.read_csv(p) if p.exists() else pd.DataFrame(columns=PAYMENT_COLS)
    for c in PAYMENT_COLS:
        if c not in df.columns:
            df[c] = None
    df = df[PAYMENT_COLS].copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for c in ["amount", "rate_per_g", "grams"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["receipt_no"] = df["receipt_no"].astype("string").fillna("")
    df = df.dropna(subset=["date", "amount"]).sort_values("date").reset_index(drop=True)
    # Grams from the receipt win; otherwise amount ÷ rate
    missing = df["grams"].isna() & df["rate_per_g"].notna() & (df["rate_per_g"] > 0)
    df.loc[missing, "grams"] = df.loc[missing, "amount"] / df.loc[missing, "rate_per_g"]
    return df


def save_payments(df: pd.DataFrame) -> str:
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    out = out.dropna(subset=["date"])
    return storage._save("data/gold_payments.csv", out[PAYMENT_COLS].to_csv(index=False), "Update gold payments from app")


# ---------- prices ----------
def intl_gold_inr_per_gram(period: str = "2y") -> pd.Series:
    """International 24K gold price in ₹ per gram, daily (no Indian duty/GST)."""
    gold = yf.Ticker("GC=F").history(period=period)["Close"].dropna()
    fx = yf.Ticker("INR=X").history(period=period)["Close"].dropna()
    gold.index = gold.index.tz_localize(None).normalize()
    fx.index = fx.index.tz_localize(None).normalize()
    df = pd.concat([gold.rename("g"), fx.rename("fx")], axis=1).sort_index().ffill().dropna()
    return (df["g"] * df["fx"] / TROY_OUNCE_G).rename("inr_per_g")


def jeweller_premium(payments: pd.DataFrame, intl: pd.Series) -> float | None:
    """How much above the international price your jeweller charged, from your latest payments.
    Returns a multiplier (e.g. 1.07 = 7% above). Uses up to the last 3 payments with a rate."""
    rows = payments.dropna(subset=["rate_per_g"]).tail(3)
    if rows.empty or intl.empty:
        return None
    ratios = []
    for _, r in rows.iterrows():
        d = pd.Timestamp(r["date"]).normalize()
        ref = intl.loc[:d]
        if ref.empty:
            continue
        ratios.append(r["rate_per_g"] / ref.iloc[-1])
    return sum(ratios) / len(ratios) if ratios else None


# ---------- schedule ----------
@dataclass
class MonthStatus:
    month: dt.date        # first day of the month
    label: str
    status: str           # paid / double / due / missed / upcoming
    paid: float


def _month_start(d: dt.date) -> dt.date:
    return d.replace(day=1)


def _add_months(d: dt.date, n: int) -> dt.date:
    y, m = divmod(d.month - 1 + n, 12)
    return dt.date(d.year + y, m + 1, 1)


def schedule(plan: dict, payments: pd.DataFrame, today: dt.date) -> list[MonthStatus]:
    if plan.get("start_month"):
        start = dt.datetime.strptime(plan["start_month"], "%Y-%m").date()
    elif not payments.empty:
        start = _month_start(payments["date"].iloc[0].date())
    else:
        start = _month_start(today)
    by_month = payments.groupby(payments["date"].dt.to_period("M"))["amount"].sum() if not payments.empty else {}
    monthly = float(plan["monthly_amount"])
    out = []
    for k in range(int(plan["months"])):
        m = _add_months(start, k)
        paid = float(by_month.get(pd.Period(m, "M"), 0)) if len(by_month) else 0.0
        if paid >= monthly * 1.95:
            status = "double"
        elif paid >= monthly * 0.99:
            status = "paid"
        elif m > _month_start(today):
            status = "upcoming"
        elif m == _month_start(today):
            status = "due"
        else:
            status = "missed"
        out.append(MonthStatus(m, m.strftime("%b %y"), status, paid))
    # A missed month is "covered" if the next month was paid double
    for i, s in enumerate(out):
        if s.status == "missed" and i + 1 < len(out) and out[i + 1].status == "double":
            s.status = "covered"
    return out


def scheme_health(sched: list[MonthStatus]) -> tuple[str, str]:
    """(tone, message) about the 'max 1 missed month' rule."""
    if not any(s.status in ("paid", "double", "covered") for s in sched):
        return "neutral", "No payments recorded yet. Add your receipts below."
    run = worst = 0
    for s in sched:
        if s.status == "missed":
            run += 1
            worst = max(worst, run)
        else:
            run = 0
    current_missed = 0
    for s in sched:
        if s.status in ("missed",):
            current_missed += 1
        elif s.status in ("paid", "double", "covered"):
            current_missed = 0
    if worst >= 2:
        return "bad", "Two months in a row were missed. Under the scheme rules the jeweller may return your money instead of the gold. Contact them now."
    if current_missed == 1:
        return "warn", "Last month was missed. Pay double this month to stay in the scheme."
    return "good", "All payments are on track."


# ---------- final purchase estimate ----------
def purchase_estimate(grams: float, rate: float, making_pct: float) -> dict:
    gold_value = grams * rate
    making = gold_value * making_pct / 100
    gst = (gold_value + making) * GST_PCT / 100
    return {"gold_value": gold_value, "making": making, "gst": gst, "extra_to_pay": making + gst,
            "total_bill": gold_value + making + gst}


def grams_for_budget(grams: float, making_pct: float) -> float:
    """If you don't want to pay anything extra, how many grams of jewellery can you take?
    The gold you saved has to cover the jewellery's weight + making + GST."""
    factor = (1 + making_pct / 100) * (1 + GST_PCT / 100)
    return grams / factor

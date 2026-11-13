"""Turns a company's numbers into a simple 0-10 scorecard, a verdict and plain-language reasons.

This is a rules-based checklist, not a price predictor. It looks for the things long-term
investors care about: a profitable, growing business, a healthy balance sheet, a sensible price,
and no alarming news. Every rule is written out below so you can see exactly why a score is what it is.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .data import StockSnapshot

FINANCIAL_SECTORS = {"Financial Services"}

NEG_WORDS = ["plunge", "slump", "tumble", "crash", "falls", "fall ", "drops", "decline", "loss", "probe",
             "fraud", "penalty", "fine ", "raid", "downgrade", "weak", "misses", "resigns", "default",
             "sebi order", "lawsuit", "cut target", "sell rating", "slips", "sinks", "hits 52-week low"]
POS_WORDS = ["surge", "jumps", "rises", "rally", "record", "wins", "bags", "order win", "upgrade", "beats",
             "strong", "profit up", "growth", "expands", "buy rating", "raises target", "52-week high",
             "dividend", "soars", "gains", "approval"]


def _band(value, bands, default=None):
    """bands: list of (threshold, score) checked in order with value >= threshold."""
    if value is None:
        return default
    for threshold, score in bands:
        if value >= threshold:
            return score
    return bands[-1][1]


def _avg(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 1) if xs else None


@dataclass
class Pillar:
    name: str
    score: float | None
    notes: list[str] = field(default_factory=list)


@dataclass
class Scorecard:
    pillars: list[Pillar]
    overall: float | None
    verdict: str          # Add slowly / Hold / Wait for a better price / Review / Avoid / Not enough data
    verdict_tone: str     # good / neutral / warn / bad
    summary: str
    reasons: list[str]
    watch_outs: list[str]


def _pct(x):
    return None if x is None else x * 100


def score_stock(s: StockSnapshot, headlines: list[str] | None = None) -> Scorecard:
    i = s.info
    is_fin = (s.sector in FINANCIAL_SECTORS)
    reasons, watch = [], []

    # 1. Business quality: return on equity, profit margin, profit growth
    roe = _pct(i.get("returnOnEquity"))
    margin = _pct(i.get("profitMargins"))
    eg = _pct(i.get("earningsGrowth"))
    rg = _pct(i.get("revenueGrowth"))
    q_roe = _band(roe, [(22, 10), (18, 8.5), (14, 7), (10, 5.5), (5, 4), (-1e9, 2)])
    q_margin = None if is_fin else _band(margin, [(20, 9), (12, 7.5), (7, 6), (3, 4.5), (-1e9, 2)])
    q_growth = _band(eg, [(25, 9), (12, 8), (5, 6.5), (0, 5), (-15, 3.5), (-1e9, 2)])
    quality = Pillar("Business quality", _avg([q_roe, q_margin, q_growth]))
    if roe is not None:
        quality.notes.append(f"Return on equity {roe:.0f}% (above 15% is good)")
        if roe >= 18:
            reasons.append(f"Earns a strong {roe:.0f}% return on shareholders' money every year.")
        elif roe < 10:
            watch.append(f"Low return on shareholders' money ({roe:.0f}%).")
    if eg is not None:
        quality.notes.append(f"Profit growth (latest quarter vs a year ago) {eg:+.0f}%")
        if eg >= 12:
            reasons.append(f"Profit grew {eg:.0f}% compared with a year ago.")
        elif eg < 0:
            watch.append(f"Profit fell {abs(eg):.0f}% compared with a year ago.")
    if margin is not None and not is_fin:
        quality.notes.append(f"Keeps {margin:.0f}% of sales as profit")

    # 2. Financial health: debt (non-financials) or return on assets (banks/NBFCs)
    if is_fin:
        roa = _pct(i.get("returnOnAssets"))
        h = _band(roa, [(1.8, 9.5), (1.4, 8.5), (1.0, 7), (0.6, 5), (-1e9, 3)])
        health = Pillar("Financial health", h)
        if roa is not None:
            health.notes.append(f"Return on assets {roa:.2f}% (above 1% is healthy for a bank/lender)")
            if roa >= 1.4:
                reasons.append("Healthy, profitable loan book for a lender.")
            elif roa < 0.8:
                watch.append("Thin profits on its loans (low return on assets).")
    else:
        de = i.get("debtToEquity")  # Yahoo reports this as a percentage, e.g. 45 = 0.45x
        cr = i.get("currentRatio")
        h_de = _band(None if de is None else -de, [(-10, 10), (-40, 8.5), (-80, 6.5), (-150, 4.5), (-1e9, 2)])
        h_cr = _band(cr, [(1.5, 8.5), (1.1, 7), (0.8, 5), (-1e9, 3)])
        health = Pillar("Financial health", _avg([h_de, h_cr]))
        if de is not None:
            health.notes.append(f"Debt is {de/100:.2f}× its equity (below 0.5× is comfortable)")
            if de < 15:
                reasons.append("Almost no debt, so it can survive bad years.")
            elif de > 150:
                watch.append(f"High debt ({de/100:.1f}× equity). Riskier when business slows.")
        if cr is not None:
            health.notes.append(f"Current ratio {cr:.2f} (short-term assets vs bills due)")

    # 3. Price vs value: P/E, PEG, and price vs its own 5-year average
    pe = i.get("trailingPE")
    peg = (pe / eg) if (pe and eg and eg > 0) else None
    v_pe = _band(None if pe is None else -pe, [(-12, 9), (-20, 7.5), (-30, 6), (-45, 4.5), (-70, 3), (-1e9, 2)])
    v_peg = _band(None if peg is None else -peg, [(-1, 9), (-1.5, 7.5), (-2.2, 6), (-3, 4), (-1e9, 2.5)])
    v_hist = None
    if not s.history.empty and len(s.history) > 500 and s.price:
        avg5 = float(s.history["Close"].mean())
        ratio = s.price / avg5
        v_hist = _band(-ratio, [(-0.9, 8.5), (-1.1, 7), (-1.35, 5.5), (-1.7, 4), (-1e9, 3)])
    value = Pillar("Price vs value", _avg([v_pe, v_peg, v_hist]))
    if pe:
        value.notes.append(f"P/E {pe:.1f}: you pay ₹{pe:.0f} for every ₹1 of yearly profit")
        if pe > 60:
            watch.append(f"Expensive: priced at {pe:.0f}× its yearly profit.")
        elif pe < 18 and (q_roe or 0) >= 7:
            reasons.append(f"Reasonably priced at {pe:.0f}× yearly profit for a good business.")
    elif i.get("trailingPE") is None and (i.get("trailingEps") or 0) < 0:
        watch.append("Currently making a loss, so it has no P/E.")

    # 4. Recent trend: price vs 50/200-day average and 1-year return
    trend = Pillar("Recent trend", None)
    h = s.history
    if not h.empty and len(h) >= 200 and s.price:
        ma50 = float(h["Close"].tail(50).mean())
        ma200 = float(h["Close"].tail(200).mean())
        above50, above200 = s.price > ma50, s.price > ma200
        t = 8 if (above50 and above200) else 6 if above200 else 4.5 if above50 else 3
        r1y = s.change_over(250)
        if r1y is not None:
            t += 1 if r1y > 15 else -1 if r1y < -15 else 0
        trend.score = max(1.0, min(10.0, float(t)))
        trend.notes.append("Above its 200-day average" if above200 else "Below its 200-day average")
        if r1y is not None:
            trend.notes.append(f"1-year price change {r1y:+.0f}%")
        hi = i.get("fiftyTwoWeekHigh")
        if hi:
            off = (s.price / hi - 1) * 100
            trend.notes.append(f"{abs(off):.0f}% below its 52-week high" if off < -1 else "Near its 52-week high")

    # 5. News: simple keyword tone on recent headlines (the AI summary reads them properly)
    news = Pillar("News", None)
    if headlines:
        low = [x.lower() for x in headlines]
        neg = sum(any(w in x for w in NEG_WORDS) for x in low)
        pos = sum(any(w in x for w in POS_WORDS) for x in low)
        news.score = max(2.0, min(9.0, 6 + pos * 0.6 - neg * 0.9))
        news.notes.append(f"{len(headlines)} headlines in 30 days: {pos} positive-sounding, {neg} negative-sounding")
        if neg >= 3 and neg > pos:
            watch.append("Several negative headlines recently. Read the news summary.")

    pillars = [quality, health, value, trend, news]
    weights = {"Business quality": 0.30, "Financial health": 0.20, "Price vs value": 0.20,
               "Recent trend": 0.15, "News": 0.15}
    have = [(p.score, weights[p.name]) for p in pillars if p.score is not None]
    if len(have) < 3 or quality.score is None:
        return Scorecard(pillars, None, "Not enough data", "neutral",
                         "Yahoo doesn't have enough financial data for this company to score it.",
                         reasons, watch)
    overall = round(sum(sc * w for sc, w in have) / sum(w for _, w in have), 1)

    strong_biz = (quality.score or 0) >= 7 and (health.score or 0) >= 6.5
    fair_price = (value.score or 0) >= 5.5
    if strong_biz and fair_price and overall >= 6.5:
        verdict, tone = "Add slowly", "good"
        summary = "Strong company at a fair price. Spread your buying over 3–4 months instead of all at once."
    elif strong_biz and not fair_price:
        verdict, tone = "Wait for a better price", "neutral"
        summary = "Good company, but the price is high right now. Keep it on your watchlist."
    elif overall >= 5.8:
        verdict, tone = "Hold", "neutral"
        summary = "Decent overall. If you own it, keep holding. No reason to rush in or out."
    elif overall >= 4.5:
        verdict, tone = "Review", "warn"
        summary = "Some weak spots. Read the reasons below before buying more."
    else:
        verdict, tone = "Avoid", "bad"
        summary = "Weak on several checks. Better options likely exist."

    return Scorecard(pillars, overall, verdict, tone, summary, reasons[:4], watch[:4])

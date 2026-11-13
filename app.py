"""Nivesh Co-Pilot: a personal long-term investing dashboard for Indian stocks and index funds.

Run locally:  streamlit run app.py
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import ai, storage, ui
from core.data import get_index, get_mf_history, get_mf_nav, get_news, get_stock, search_mutual_funds
from core.scoring import score_stock

st.set_page_config(page_title="Nivesh Co-Pilot", page_icon="📈", layout="wide")
st.markdown(ui.CSS, unsafe_allow_html=True)

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

LARGE_CAPS = [
    "RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS", "BHARTIARTL", "ITC", "LT", "SBIN", "KOTAKBANK",
    "AXISBANK", "HINDUNILVR", "BAJFINANCE", "MARUTI", "SUNPHARMA", "M&M", "HCLTECH", "TITAN", "ASIANPAINT",
    "ULTRACEMCO", "NTPC", "POWERGRID", "NESTLEIND", "TATASTEEL", "WIPRO", "ONGC", "ADANIPORTS", "COALINDIA",
    "JSWSTEEL", "BAJAJFINSV", "TECHM", "GRASIM", "HINDALCO", "CIPLA", "DRREDDY", "EICHERMOT", "BAJAJ-AUTO",
    "HEROMOTOCO", "BRITANNIA", "APOLLOHOSP", "TATACONSUM", "SBILIFE", "HDFCLIFE", "INDUSINDBK",
    "SHRIRAMFIN", "TRENT", "BEL", "ETERNAL", "TMPV", "ADANIENT",
]
INDICES = [("Nifty 50", "^NSEI"), ("Sensex", "^BSESN"), ("Bank Nifty", "^NSEBANK")]


# ---------- helpers ----------
def inr(x: float | None, decimals: int = 0) -> str:
    """Indian number format: 1234567 -> ₹12,34,567"""
    if x is None or pd.isna(x):
        return "–"
    neg = x < 0
    x = abs(x)
    s = f"{x:.{decimals}f}"
    whole, _, frac = s.partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts) + "," + tail
    return ("−" if neg else "") + "₹" + whole + (("." + frac) if frac else "")


def pct(x: float | None) -> str:
    if x is None or pd.isna(x):
        return "–"
    return f"{x:+.1f}%"


def html(s: str) -> None:
    st.markdown(s, unsafe_allow_html=True)


def section(title: str, note: str = "") -> None:
    html(f'<div class="section-title"><div class="h">{ui.esc(title)}</div><span>{ui.esc(note)}</span></div>')


def plot_layout(fig: go.Figure, height: int = 320) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", font=dict(family="IBM Plex Sans, sans-serif", color=ui.INK, size=12),
        hoverlabel=dict(font_family="IBM Plex Sans", bgcolor="#ffffff"), showlegend=False,
    )
    fig.update_xaxes(showgrid=False, linecolor=ui.LINE)
    fig.update_yaxes(gridcolor="#e6ecea", zeroline=False)
    return fig


def market_open(now: dt.datetime) -> bool:
    if now.weekday() >= 5:
        return False
    t = now.time()
    return dt.time(9, 15) <= t <= dt.time(15, 30)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_news(name: str):
    return get_news(name)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_nav(code: str):
    return get_mf_nav(code)


@st.cache_data(ttl=21600, show_spinner=False)
def cached_mf_history(code: str):
    return get_mf_history(code)


@st.cache_data(ttl=120, show_spinner=False)
def cached_index(ticker: str):
    return get_index(ticker)


@st.cache_data(ttl=21600, show_spinner=False)
def cached_ai_company(name, verdict, facts, headlines):
    return ai.summarize_company(name, verdict, list(facts), list(headlines))


@st.cache_data(ttl=21600, show_spinner=False)
def cached_ai_briefing(lines):
    return ai.daily_briefing(list(lines))


def useful_news(name: str, limit: int = 8):
    """News items minus generic quote-page titles."""
    return [n for n in cached_news(name)
            if "stock price, news, quote" not in n.title.lower() and len(n.title.split()) >= 5][:limit]


def useful_headlines(name: str) -> list[str]:
    return [n.title for n in useful_news(name, 10)]


class _Incomplete(Exception):
    """Raised inside a cached function so partial results (Yahoo refused financials) aren't kept."""
    def __init__(self, result):
        self.result = result


@st.cache_data(ttl=900, show_spinner=False)
def _analyse_cached(symbol: str):
    s = get_stock(symbol)
    if s.error:
        raise _Incomplete((s, None, []))
    heads = useful_headlines(s.name)
    result = (s, score_stock(s, heads), heads)
    if not s.info:
        raise _Incomplete(result)
    return result


def analyse(symbol: str):
    try:
        return _analyse_cached(symbol)
    except _Incomplete as e:
        return e.result


def cached_stock(symbol: str):
    return analyse(symbol)[0]


def key_facts(s, sc) -> list[str]:
    facts = [f"Price ₹{s.price:,.0f}"]
    for p in sc.pillars:
        facts.extend(p.notes)
    return facts


# ---------- load data ----------
settings = storage.load_settings()
portfolio = storage.load_portfolio()
watchlist = storage.load_watchlist()
now_ist = dt.datetime.now(IST)
is_open = market_open(now_ist)

# ---------- header ----------
h1, h2 = st.columns([3, 2], vertical_alignment="bottom")
with h1:
    html('<div class="rise"><h1 style="margin:0;font-size:2.4rem">Nivesh Co-Pilot</h1>'
         '<div style="color:var(--muted)">Your long-term investing desk · NSE &amp; BSE</div></div>')
with h2:
    status = ('<span class="live-dot"></span>Market open · refreshes every 2 min' if is_open
              else '<span class="closed-dot"></span>Market closed · showing last close')
    html(f'<div style="text-align:right" class="rise"><span class="status">{status}</span><br>'
         f'<span class="mono" style="color:var(--muted)">{now_ist:%a %d %b %Y · %I:%M %p} IST · prices ~15 min delayed</span></div>')


@st.fragment(run_every="120s" if is_open else None)
def market_strip():
    cells = []
    for label, tk in INDICES:
        d = cached_index(tk)
        if not d:
            continue
        cls = ui.tone_for_change(d["change_pct"])
        cells.append(
            f'<div class="tick rise"><span class="n">{label}</span>{ui.sparkline(d["series"], 110, 44)}'
            f'<span class="v num">{d["level"]:,.0f}</span>'
            f'<span class="{cls}" style="font-size:.85rem;font-weight:600">{ui.signed(d["change_pct"], 2)} today'
            f' <span class="m1" style="color:var(--muted);font-weight:400">· {d["month_pct"]:+.1f}% 1M</span></span></div>')
    if cells:
        html('<div class="strip" style="margin:14px 0 6px">' + "".join(cells) + "</div>")


market_strip()

if settings.get("example_data"):
    st.info("**You're looking at example holdings.** Go to the **My money** tab to enter your real "
            "investments, then untick *Show example banner*.", icon="ℹ️")

tab_home, tab_stock, tab_ideas, tab_money, tab_learn = st.tabs(
    ["🏠 Home", "🔎 Stock check", "💡 Find ideas", "💼 My money", "📘 Learn"]
)


# ---------- portfolio valuation ----------
def value_portfolio(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in df.iterrows():
        if r["type"] == "fund":
            code = str(r["scheme_code"]) if pd.notna(r["scheme_code"]) else None
            nav, nav_date, scheme = cached_nav(code) if code else (None, None, None)
            units = r["quantity"] if pd.notna(r["quantity"]) else None
            invested = r["invested"] if pd.notna(r["invested"]) else (
                units * r["avg_price"] if units and pd.notna(r["avg_price"]) else None)
            now = nav * units if (nav and units) else None
            hist = cached_mf_history(code) if code else pd.Series(dtype=float)
            spark = [float(x) for x in hist.tail(63)] if not hist.empty else []
            day = (hist.iloc[-1] / hist.iloc[-2] - 1) * 100 if len(hist) > 1 else None
            rows.append(dict(kind="fund", name=r["name"] or scheme or "Fund", symbol="Index fund",
                             invested=invested, now=now, day=day, verdict="On track", tone="good",
                             note=f"NAV ₹{nav:,.2f} on {nav_date}" if nav else "NAV unavailable", spark=spark))
        else:
            s, sc, _ = analyse(str(r["symbol"]))
            qty = r["quantity"] or 0
            invested = qty * (r["avg_price"] or 0)
            if s.error:
                rows.append(dict(kind="stock", name=r["name"] or r["symbol"], symbol=r["symbol"], invested=invested,
                                 now=None, day=None, verdict="Check symbol", tone="warn", note=s.error, spark=[]))
                continue
            rows.append(dict(kind="stock", name=r["name"] or s.name, symbol=r["symbol"], invested=invested,
                             now=qty * s.price, day=s.day_change_pct,
                             verdict=sc.verdict if sc else "Not enough data",
                             tone=sc.verdict_tone if sc else "neutral",
                             note=sc.summary if sc else "",
                             spark=[float(x) for x in s.history["Close"].tail(63)]))
    out = pd.DataFrame(rows)
    if not out.empty:
        out["gain_pct"] = (out["now"] / out["invested"] - 1) * 100
    return out


def portfolio_history(df: pd.DataFrame, days: int = 180) -> pd.Series:
    """Value of today's holdings over the past `days`, using each day's closing price / NAV."""
    parts = []
    start = pd.Timestamp(dt.date.today() - dt.timedelta(days=days))
    for _, r in df.iterrows():
        qty = r["quantity"] if pd.notna(r["quantity"]) else 0
        if not qty:
            continue
        if r["type"] == "fund" and pd.notna(r["scheme_code"]):
            h = cached_mf_history(str(r["scheme_code"]))
        elif r["type"] != "fund":
            s = cached_stock(str(r["symbol"]))
            h = s.history["Close"] if not s.error else pd.Series(dtype=float)
            if not h.empty:
                h.index = h.index.tz_localize(None).normalize()
        else:
            continue
        if h.empty:
            continue
        parts.append((h[h.index >= start] * qty).rename(len(parts)))
    if not parts:
        return pd.Series(dtype=float)
    combo = pd.concat(parts, axis=1).sort_index().ffill().dropna()
    return combo.sum(axis=1)


# ================= HOME =================
with tab_home:
    if portfolio.empty:
        section("Welcome!")
        st.write("Add your investments in the **My money** tab and this page will fill up.")
    else:
        with st.spinner("Fetching latest prices…"):
            val = value_portfolio(portfolio)
            hist = portfolio_history(portfolio)
        total_now = val["now"].sum(min_count=1)
        total_inv = val["invested"].sum(min_count=1)
        stocks = val[val["kind"] == "stock"]
        day_rs = sum((r["now"] - r["now"] / (1 + r["day"] / 100))
                     for _, r in val.iterrows() if pd.notna(r["day"]) and pd.notna(r["now"]))
        gain = total_now - total_inv
        gain_pct = (total_now / total_inv - 1) * 100 if total_inv else 0
        six_m = (hist.iloc[-1] / hist.iloc[0] - 1) * 100 if len(hist) > 1 else None

        c1, c2 = st.columns([5, 7], gap="medium")
        with c1:
            g_cls = "#9ff0bf" if gain >= 0 else "#ffb4ad"
            d_cls = "#9ff0bf" if day_rs >= 0 else "#ffb4ad"
            html(f"""
<div class="hero rise">
  <div class="label">Your money is worth</div>
  <div class="big">{inr(total_now)}</div>
  <div class="chips">
    <span class="chip">Invested <b>{inr(total_inv)}</b></span>
    <span class="chip" style="color:{g_cls}">{ui.signed(gain_pct)} · <b>{inr(gain)}</b> overall</span>
    <span class="chip" style="color:{d_cls}">Today <b>{inr(day_rs)}</b></span>
  </div>
  <div style="margin-top:16px;font-size:.9rem;opacity:.8;position:relative;z-index:1">
    {"Normal daily movement. Nothing to do today." if abs(day_rs) < 0.02 * total_now else "A bigger move than usual today. Check the briefing below."}
  </div>
</div>""")
        with c2:
            if len(hist) > 1:
                up = hist.iloc[-1] >= hist.iloc[0]
                col = ui.GOOD if up else ui.BAD
                fig = go.Figure(go.Scatter(
                    x=hist.index, y=hist.values, mode="lines", line=dict(color=col, width=2.6, shape="spline"),
                    fill="tozeroy", fillcolor="rgba(22,128,60,.10)" if up else "rgba(192,50,42,.10)",
                    hovertemplate="%{x|%d %b}<br>₹%{y:,.0f}<extra></extra>"))
                fig.add_trace(go.Scatter(x=[hist.index[-1]], y=[hist.iloc[-1]], mode="markers",
                                         marker=dict(size=10, color=col, line=dict(color="#fff", width=2)),
                                         hoverinfo="skip"))
                lo, hi = hist.min(), hist.max()
                fig.update_yaxes(range=[lo - (hi - lo) * 0.15, hi + (hi - lo) * 0.1], tickprefix="₹", tickformat=",.0f")
                html(f'<div style="display:flex;justify-content:space-between;align-items:baseline">'
                     f'<b>Your holdings over 6 months</b><span class="{ui.tone_for_change(six_m)}" '
                     f'style="font-weight:600">{ui.signed(six_m)}</span></div>')
                st.plotly_chart(plot_layout(fig, 210), width="stretch", config={"displayModeBar": False})
                st.caption("What today's holdings would have been worth on each day.")

        # ---- To-do + allocation ----
        today = now_ist.date()
        sip_day = int(settings.get("sip_day", 15))
        next_sip = today.replace(day=sip_day) if today.day <= sip_day else (
            (today.replace(day=1) + dt.timedelta(days=32)).replace(day=sip_day))
        days_to_sip = (next_sip - today).days
        when = "today" if days_to_sip == 0 else "tomorrow" if days_to_sip == 1 else f"in {days_to_sip} days"
        todo = [("🗓️", ui.ACCENT_SOFT, f"{inr(settings.get('monthly_sip', 0))} SIP on {next_sip:%d %b} ({when})",
                 "Runs automatically. Just keep enough balance in your bank account.")]

        stock_share = (stocks["now"].sum() / total_now * 100) if total_now else 0
        target = settings.get("target_stock_share", 25)
        if stock_share > target + 10:
            todo.append(("⚖️", ui.WARN_BG, f"Stocks are {stock_share:.0f}% of your money (target {target}%)",
                         "Put extra money into your index fund this month, not into stocks."))
        for _, r in val[val["tone"].isin(["warn", "bad"])].iterrows():
            todo.append(("🔍", ui.BAD_BG if r["tone"] == "bad" else ui.WARN_BG, f"Review {r['name']}",
                         f"{r['note']} Open it in Stock check to see why."))
        if stock_share <= target + 5:
            picks = []
            for sym in watchlist["symbol"].tolist():
                s, sc, _ = analyse(sym)
                if sc and sc.verdict == "Add slowly":
                    picks.append((sc.overall, s.name))
            picks.sort(reverse=True)
            if picks:
                todo.append(("🌱", ui.GOOD_BG, "Extra money to invest? Best on your watchlist: "
                             + ", ".join(f"{n} ({o}/10)" for o, n in picks[:2]),
                             "Buy in small pieces over 3–4 months, not all at once."))
        if len(todo) == 1:
            todo.append(("✅", ui.GOOD_BG, "Everything else is on track", "No action needed this month."))

        a, b = st.columns([7, 5], gap="medium")
        with a:
            section("What to do this month", f"{len(todo)} item{'s' if len(todo) > 1 else ''}")
            items = "".join(
                f'<div class="item rise" style="animation-delay:{k * 0.07:.2f}s"><div class="ic" style="background:{bg}">'
                f'{ic}</div><div><div class="t">{ui.esc(t)}</div><div class="d">{ui.esc(d)}</div></div></div>'
                for k, (ic, bg, t, d) in enumerate(todo))
            html(f'<div class="card"><div class="todo">{items}</div></div>')
        with b:
            section("Where your money is", f"target: {100 - target}% fund · {target}% stocks")
            labels = val["name"].tolist()
            values = val["now"].fillna(0).tolist()
            palette = [ui.ACCENT, ui.SAFFRON, "#5a8f84", "#c9a46a", "#8fb8ad", "#b56b45", "#3d5a80", "#9c6b98"]
            fig = go.Figure(go.Pie(labels=labels, values=values, hole=0.68, sort=False,
                                   marker=dict(colors=palette[:len(labels)], line=dict(color="#fff", width=2)),
                                   textinfo="none", hovertemplate="%{label}<br>₹%{value:,.0f} · %{percent}<extra></extra>"))
            fig.add_annotation(text=f"<b>{stock_share:.0f}%</b><br><span style='font-size:12px'>in stocks</span>",
                               showarrow=False, font=dict(size=22, family="Bricolage Grotesque", color=ui.INK))
            fig = plot_layout(fig, 230)
            fig.update_layout(showlegend=True, legend=dict(orientation="v", x=1.02, y=0.5, font=dict(size=11)))
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

        # ---- Holdings cards ----
        section("Your holdings", "last 3 months")
        cards = []
        for k, (_, r) in enumerate(val.iterrows()):
            g = r["gain_pct"]
            cards.append(f"""
<div class="card hold rise" style="animation-delay:{k * 0.06:.2f}s">
  <div class="top"><div><div class="name">{ui.esc(r['name'])}</div><div class="sym mono">{ui.esc(r['symbol'])}</div></div>
  {ui.pill(r['verdict'], r['tone'])}</div>
  <div style="display:flex;justify-content:space-between;align-items:end;gap:8px">
    <div><div class="worth">{inr(r['now'])}</div>
      <div class="row"><span class="{ui.tone_for_change(g)}">{ui.signed(g if pd.notna(g) else None)} overall</span>
      <span class="{ui.tone_for_change(r['day'])}">{ui.signed(r['day'] if pd.notna(r['day']) else None)} today</span></div></div>
    {ui.sparkline(r['spark'], 110, 46)}
  </div>
</div>""")
        html('<div class="grid">' + "".join(cards) + "</div>")

        # ---- Briefing ----
        section("Today's briefing", "from the last 30 days of news")
        lines = []
        for _, r in stocks.iterrows():
            heads = useful_headlines(cached_stock(r["symbol"]).name) if r["symbol"] else []
            lines.append(f"{r['name']}: {pct(r['day'])} today, verdict {r['verdict']}. Headlines: "
                         + " | ".join(heads[:4]))
        brief = cached_ai_briefing(tuple(lines)) if ai.available() else None
        if brief:
            with st.container(border=True):
                st.markdown(brief)
                st.caption("✨ Written by AI from today's headlines and numbers. It can make mistakes.")
        else:
            cards = []
            for _, r in stocks.iterrows():
                news = useful_news(cached_stock(r["symbol"]).name, 2)
                body = "".join(f'<div class="item"><a href="{ui.esc(n.link)}" target="_blank">{ui.esc(n.title)}</a>'
                               f'<div class="meta">{ui.esc(n.source)} · {ui.esc(n.published)}</div></div>'
                               for n in news) or '<div class="meta">No major news.</div>'
                cards.append(f'<div class="card news rise"><div style="display:flex;justify-content:space-between">'
                             f'<b>{ui.esc(r["name"])}</b><span class="{ui.tone_for_change(r["day"])}">'
                             f'{ui.signed(r["day"] if pd.notna(r["day"]) else None)}</span></div>{body}</div>')
            html('<div class="grid">' + "".join(cards) + "</div>")
            if not ai.available():
                st.caption("Tip: add an AI key (see README) to get these turned into a plain-English summary.")


# ================= STOCK CHECK =================
with tab_stock:
    c1, c2 = st.columns([2, 1])
    options = sorted(set(LARGE_CAPS) | set(watchlist["symbol"]) | set(portfolio["symbol"].dropna()) - {""})
    pick = c1.selectbox("Pick a company", options, index=options.index("HDFCBANK") if "HDFCBANK" in options else 0)
    typed = c2.text_input("…or type any NSE symbol", placeholder="e.g. PIDILITIND").strip().upper()
    symbol = typed or pick

    with st.spinner(f"Analysing {symbol}…"):
        s, sc, heads = analyse(symbol)

    if s.error:
        st.error(s.error)
    else:
        i = s.info
        day = s.day_change_pct
        verdict_pill = ui.pill(sc.verdict, sc.verdict_tone) if sc else ""
        rng = ""
        if i.get("fiftyTwoWeekLow") and i.get("fiftyTwoWeekHigh"):
            rng = ui.range_bar(i["fiftyTwoWeekLow"], i["fiftyTwoWeekHigh"], s.price, lambda v: inr(v))
        stats = [("1 month", s.change_over(21)), ("1 year", s.change_over(250)),
                 ("5 years", s.change_over(len(s.history) - 1) if len(s.history) > 1000 else None)]
        stat_html = "".join(
            f'<div><div style="color:var(--muted);font-size:.8rem">{lbl}</div>'
            f'<div class="num {ui.tone_for_change(v)}" style="font-size:1.25rem;font-weight:700">{pct(v)}</div></div>'
            for lbl, v in stats)
        html(f"""
<div class="card rise" style="padding:20px 22px;margin:8px 0 14px">
  <div style="display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;align-items:flex-start">
    <div style="min-width:0">
      <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
        <span style="font-family:'Bricolage Grotesque';font-size:1.8rem;font-weight:800">{ui.esc(s.name)}</span>{verdict_pill}</div>
      <div class="mono" style="color:var(--muted)">NSE: {ui.esc(s.symbol.replace('.NS', ''))} · {ui.esc(s.sector or '')}</div>
    </div>
    <div style="text-align:right">
      <div class="num" style="font-size:2.1rem;font-weight:800;line-height:1">{inr(s.price, 2)}</div>
      <div class="{ui.tone_for_change(day)}" style="font-weight:600">{ui.signed(day, 2)} today</div>
    </div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:12px;margin-top:16px;align-items:end">
    {stat_html}<div style="grid-column:span 2;min-width:200px">{rng}</div>
  </div>
</div>""")

        left, right = st.columns([3, 2], gap="medium")
        with left:
            style = st.segmented_control("Chart style", ["Line", "Candles"], default="Line",
                                         label_visibility="collapsed") or "Line"
            h = s.history
            ma200 = h["Close"].rolling(200).mean()
            fig = go.Figure()
            if style == "Candles":
                fig.add_trace(go.Candlestick(x=h.index, open=h["Open"], high=h["High"], low=h["Low"],
                                             close=h["Close"], name="Price",
                                             increasing_line_color=ui.GOOD, decreasing_line_color=ui.BAD))
            else:
                fig.add_trace(go.Scatter(x=h.index, y=h["Close"], name="Price", mode="lines",
                                         line=dict(color=ui.ACCENT, width=2.2), fill="tozeroy",
                                         fillcolor="rgba(15,107,92,.07)",
                                         hovertemplate="%{x|%d %b %Y}<br>₹%{y:,.2f}<extra></extra>"))
            fig.add_trace(go.Scatter(x=h.index, y=ma200, name="200-day average", mode="lines",
                                     line=dict(color=ui.SAFFRON, width=1.6, dash="dot"),
                                     hovertemplate="200-day avg ₹%{y:,.0f}<extra></extra>"))
            end = h.index[-1]
            lo = h["Low" if style == "Candles" else "Close"].loc[end - pd.Timedelta(days=365):].min()
            hi = h["High" if style == "Candles" else "Close"].loc[end - pd.Timedelta(days=365):].max()
            fig.update_xaxes(range=[end - pd.Timedelta(days=365), end], rangeslider_visible=False,
                             rangeselector=dict(buttons=[
                                 dict(count=1, label="1M", step="month", stepmode="backward"),
                                 dict(count=6, label="6M", step="month", stepmode="backward"),
                                 dict(count=1, label="1Y", step="year", stepmode="backward"),
                                 dict(count=5, label="5Y", step="year", stepmode="backward"),
                             ], bgcolor="#e9efed", activecolor=ui.ACCENT_SOFT, x=0, y=1.08))
            fig.update_yaxes(tickprefix="₹", range=[lo * 0.95, hi * 1.04], autorange=False)
            plot_layout(fig, 380)
            fig.update_layout(hovermode="x unified", margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
            st.caption("Gold dotted line = 200-day average. Price above it means the long-term trend is up. "
                       "Use the 1M–5Y buttons to zoom.")
        with right:
            if sc and sc.overall is not None:
                fg, bg = ui.TONES[sc.verdict_tone]
                g = go.Figure(go.Indicator(
                    mode="gauge+number", value=sc.overall,
                    number=dict(suffix="/10", font=dict(family="Bricolage Grotesque", size=40, color=ui.INK)),
                    gauge=dict(axis=dict(range=[0, 10], tickwidth=0, tickcolor="#fff", tickvals=[0, 5, 10]),
                               bar=dict(color=ui.score_color(sc.overall), thickness=0.32),
                               bgcolor="#eef3f1", borderwidth=0,
                               steps=[dict(range=[0, 5], color="#f8e6e3"), dict(range=[5, 7], color="#fbf1dd"),
                                      dict(range=[7, 10], color="#e3f3e8")])))
                g = plot_layout(g, 210)
                g.update_layout(margin=dict(l=30, r=30, t=20, b=10))
                st.plotly_chart(g, width="stretch", config={"displayModeBar": False})
                html(f'<div class="verdict rise" style="background:{bg};color:{fg};margin-bottom:14px">'
                     f'<div class="k">Verdict</div><div class="v">{ui.esc(sc.verdict)}</div>'
                     f'<div style="color:var(--ink)">{ui.esc(sc.summary)}</div></div>')
            elif sc:
                st.info(sc.summary)
            if sc:
                html(ui.score_bars(sc.pillars))

        if sc:
            a, b = st.columns(2, gap="medium")
            good = "".join(f"<li>{ui.esc(r)}</li>" for r in sc.reasons) or "<li>No standout strengths in the numbers.</li>"
            bad = "".join(f"<li>{ui.esc(w)}</li>" for w in sc.watch_outs) or "<li>Nothing alarming in the numbers.</li>"
            with a:
                html(f'<div class="card rise" style="background:{ui.GOOD_BG};border-color:transparent;margin-top:16px">'
                     f'<b style="color:{ui.GOOD}">✅ Strengths</b><ul style="margin:8px 0 0">{good}</ul></div>')
            with b:
                html(f'<div class="card rise" style="background:{ui.WARN_BG};border-color:transparent;margin-top:16px">'
                     f'<b style="color:{ui.WARN}">⚠️ Watch out for</b><ul style="margin:8px 0 0">{bad}</ul></div>')
            with st.expander("See the numbers behind each score"):
                for p in sc.pillars:
                    st.markdown(f"**{p.name}**" + (f": {p.score:.1f}/10" if p.score is not None else ": no data"))
                    for n in p.notes:
                        st.markdown(f"- {n}")

        section("News", "last 30 days")
        if ai.available() and sc and heads:
            if st.button("✨ Explain the news in simple words", key=f"ai-{symbol}"):
                with st.spinner("Reading the news…"):
                    out = cached_ai_company(s.name, sc.verdict, tuple(key_facts(s, sc)), tuple(heads[:10]))
                with st.container(border=True):
                    st.markdown(out or "AI summary isn't available for this one.")
        items = "".join(f'<div class="item"><a href="{ui.esc(n.link)}" target="_blank">{ui.esc(n.title)}</a>'
                        f'<div class="meta">{ui.esc(n.source)} · {ui.esc(n.published)}</div></div>'
                        for n in useful_news(s.name, 8))
        html(f'<div class="card news">{items or "No recent news found."}</div>')


# ================= FIND IDEAS =================
with tab_ideas:
    section("Find good companies", "same checklist, ranked")
    which = st.segmented_control("Scan", ["My watchlist", "50 large companies"], default="My watchlist",
                                 label_visibility="collapsed") or "My watchlist"
    syms = watchlist["symbol"].tolist() if which == "My watchlist" else LARGE_CAPS
    run = which == "My watchlist" or st.button("Run scan (takes about a minute)", type="primary")
    if run:
        rows = []
        bar = st.progress(0.0, text="Scanning…")
        for k, sym in enumerate(syms):
            s, sc, _ = analyse(sym)
            bar.progress((k + 1) / len(syms), text=f"Scanning {sym}…")
            if s.error or not sc or sc.overall is None:
                continue
            q = {p.name: p.score for p in sc.pillars}
            rows.append({"Company": s.name, "Symbol": sym, "Score": sc.overall, "Verdict": sc.verdict,
                         "tone": sc.verdict_tone, "Quality": q["Business quality"], "Health": q["Financial health"],
                         "Value": q["Price vs value"], "Trend": q["Recent trend"],
                         "1Y %": s.change_over(250), "Today %": s.day_change_pct,
                         "Sector": s.sector or "Other", "mcap": s.info.get("marketCap") or 1,
                         "spark": [float(x) for x in s.history["Close"].tail(63)]})
        bar.empty()
        if not rows:
            st.warning("Couldn't get company data from Yahoo Finance just now. It limits how often it can be "
                       "asked. Please try again in a few minutes.")
        else:
            df = pd.DataFrame(rows).sort_values("Score", ascending=False)

            top = df.head(3)
            cards = []
            for k, (_, r) in enumerate(top.iterrows()):
                cards.append(f"""
<div class="card hold rise" style="animation-delay:{k * 0.08:.2f}s">
  <div class="top"><div><div class="mono" style="color:var(--saffron);font-weight:600">#{k + 1}</div>
  <div class="name">{ui.esc(r['Company'])}</div></div>{ui.pill(r['Verdict'], r['tone'])}</div>
  <div style="display:flex;justify-content:space-between;align-items:end;margin-top:8px">
    <div><div class="worth">{r['Score']:.1f}<span style="font-size:.9rem;color:var(--muted)">/10</span></div>
    <div class="row"><span class="{ui.tone_for_change(r['1Y %'])}">{pct(r['1Y %'])} in 1 year</span></div></div>
    {ui.sparkline(r['spark'], 110, 46)}
  </div>
</div>""")
            html('<div class="grid">' + "".join(cards) + "</div>")

            section("Score map", "box size = company size · colour = checklist score")
            sectors = df.groupby("Sector").agg(mcap=("mcap", "sum"), Score=("Score", "mean")).reset_index()
            fig = go.Figure(go.Treemap(
                ids=list(df["Symbol"]) + ["sec:" + x for x in sectors["Sector"]] + ["all"],
                labels=list(df["Symbol"]) + list(sectors["Sector"]) + ["All"],
                parents=["sec:" + x for x in df["Sector"]] + ["all"] * len(sectors) + [""],
                values=list(df["mcap"]) + list(sectors["mcap"]) + [float(df["mcap"].sum())],
                customdata=[[c, sc_, v] for c, sc_, v in zip(df["Company"], df["Score"], df["Verdict"])]
                           + [[sec, sc_, "sector average"] for sec, sc_ in zip(sectors["Sector"], sectors["Score"])]
                           + [["All companies", float(df["Score"].mean()), "average"]],
                marker=dict(colors=list(df["Score"]) + list(sectors["Score"]) + [float(df["Score"].mean())],
                            cmin=3, cmax=9,
                            line=dict(color="#fff", width=2),
                            colorscale=[[0, ui.BAD], [0.45, "#f1d8a8"], [0.6, "#d7ead9"], [1, ui.GOOD]]),
                texttemplate="<b>%{label}</b><br>%{customdata[1]:.1f}",
                hovertemplate="<b>%{customdata[0]}</b><br>Score %{customdata[1]:.1f} · %{customdata[2]}<extra></extra>",
                branchvalues="total", pathbar=dict(visible=False), tiling=dict(pad=2),
                root_color="rgba(0,0,0,0)", level="all", maxdepth=3))
            st.plotly_chart(plot_layout(fig, 420), width="stretch", config={"displayModeBar": False})

            section("All results")
            st.dataframe(
                df[["Company", "Symbol", "Score", "Verdict", "Quality", "Health", "Value", "Trend", "1Y %", "spark"]],
                hide_index=True, width="stretch", column_config={
                    "Score": st.column_config.ProgressColumn(min_value=0, max_value=10, format="%.1f"),
                    "1Y %": st.column_config.NumberColumn(format="%+.0f%%"),
                    "spark": st.column_config.LineChartColumn("3 months"),
                })
            st.caption("Quality = profitable and growing · Health = low debt · Value = price vs profits · "
                       "Trend = price direction. Scores are a checklist, not a prediction.")


# ================= MY MONEY =================
with tab_money:
    section("Your investments")
    st.write("Edit the table like a spreadsheet, then press **Save**. "
             "For stocks: type `stock`, the NSE symbol, how many shares and your average buy price. "
             "For index/mutual funds: type `fund`, the fund's scheme code (search below), units and the total invested.")
    edited = st.data_editor(
        portfolio, num_rows="dynamic", width='stretch', hide_index=True,
        column_config={
            "type": st.column_config.SelectboxColumn("Type", options=["stock", "fund"], required=True),
            "symbol": st.column_config.TextColumn("NSE symbol", help="Stocks only, e.g. HDFCBANK"),
            "name": st.column_config.TextColumn("Name"),
            "quantity": st.column_config.NumberColumn("Shares / units", min_value=0),
            "avg_price": st.column_config.NumberColumn("Avg buy price ₹", min_value=0),
            "scheme_code": st.column_config.TextColumn("Fund scheme code", help="Funds only"),
            "invested": st.column_config.NumberColumn("Total invested ₹ (funds)", min_value=0),
        }, key="portfolio_editor")
    if st.button("💾 Save my investments", type="primary"):
        edited["symbol"] = edited["symbol"].fillna("").str.upper().str.strip()
        msg = storage.save_portfolio(edited)
        st.cache_data.clear()
        st.success(f"Saved: {msg}.")

    with st.expander("🔍 Find your fund's scheme code"):
        q = st.text_input("Fund name", placeholder="e.g. UTI Nifty 50 Index Fund Direct")
        if q:
            res = search_mutual_funds(q)
            if res:
                st.dataframe(pd.DataFrame(res).rename(columns={"schemeCode": "Scheme code", "schemeName": "Fund"}),
                             hide_index=True, width='stretch')
            else:
                st.write("No matches. Try fewer words.")

    st.divider()
    section("Watchlist")
    st.write("Companies you're interested in. The app checks them for buying opportunities.")
    wl = st.data_editor(watchlist, num_rows="dynamic", width='stretch', hide_index=True,
                        column_config={"symbol": st.column_config.TextColumn("NSE symbol"),
                                       "note": st.column_config.TextColumn("Your note")}, key="wl_editor")
    if st.button("💾 Save watchlist"):
        wl["symbol"] = wl["symbol"].fillna("").str.upper().str.strip()
        msg = storage.save_watchlist(wl[wl["symbol"] != ""])
        st.cache_data.clear()
        st.success(f"Saved: {msg}.")

    st.divider()
    section("Your plan")
    c1, c2, c3 = st.columns(3)
    sip = c1.number_input("Monthly SIP ₹", min_value=0, step=500, value=int(settings["monthly_sip"]))
    day = c2.number_input("SIP date (day of month)", min_value=1, max_value=28, value=int(settings["sip_day"]))
    tgt = c3.slider("Share of money in stocks %", 0, 60, int(settings["target_stock_share"]),
                    help="Beginners: 20–30%. The rest stays in your index fund.")
    ex = st.checkbox("Show example banner", value=bool(settings.get("example_data")))
    if st.button("💾 Save plan"):
        msg = storage.save_settings({"monthly_sip": sip, "sip_day": day, "target_stock_share": tgt,
                                     "example_data": ex})
        st.success(f"Saved: {msg}.")
        st.rerun()


# ================= LEARN =================
with tab_learn:
    section("The basics")
    st.markdown("""
**Share**: a tiny piece of ownership in a company. If its profits grow over years, your piece usually grows too.

**Nifty 50**: India's 50 biggest companies. "The market" usually means this.

**Index fund**: one purchase that buys all 50 Nifty companies. Cheap, simple, and hard to beat. This should be most of your money.

**SIP**: a fixed amount invested automatically every month. It removes the guesswork of *when* to buy.

**How to read the scorecard**
- **Business quality**: does the company earn good profits on its money and grow them?
- **Financial health**: can it survive a bad year without drowning in debt?
- **Price vs value**: are you paying a sensible price for those profits? (P/E = price ÷ yearly profit per share)
- **Recent trend**: is the price heading up or down over months? Less important for long-term investors.
- **News**: anything unusual happening?

**Verdicts**
- **Add slowly**: good company, fair price. Buy in small pieces over 3–4 months.
- **Wait for a better price**: good company, but expensive right now.
- **Hold**: fine to keep. No reason to act.
- **Review**: something's weakening. Read the reasons.
- **Avoid**: weak on several checks.

**Rules that protect you**
1. Keep 6 months of expenses as an emergency fund before investing.
2. Never invest money you'll need within 3 years.
3. No single stock above 10% of your money.
4. Stay away from F&O, intraday trading and "tips".
5. Market falls are normal. Your SIP buys more units when prices are low.
""")

st.divider()
st.caption("This app is a personal tool for learning and tracking. It is not advice from a SEBI-registered "
           "investment adviser. Scores come from simple rules and public data that can be wrong or delayed. "
           "You make every decision. Investments can lose value.")

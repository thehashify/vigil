"""Daily alert job. GitHub Actions runs this every weekday evening (see .github/workflows/alerts.yml).

It only messages you when something matters:
  - one of your stocks moved a lot today (down 5%+ or up 8%+)
  - a holding's verdict is Review / Avoid (Mondays only, so it doesn't nag)
  - a watchlist company with a good score has dropped 10%+ in a month (a possible buying chance)
  - the market fell 3%+ this week (a calm reminder to stick to the plan)
  - your SIP date is tomorrow
  - first working day of the month: a short monthly summary

Needs TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID. Without them it just prints the messages.
"""
from __future__ import annotations

import datetime as dt
import os
import urllib.parse
import urllib.request

import pandas as pd

from core import ai, gold, storage
from core.data import get_index, get_mf_nav, get_news, get_stock
from core.scoring import score_stock

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def send(text: str) -> None:
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        print("---- (no Telegram configured) ----\n" + text)
        return
    data = urllib.parse.urlencode({"chat_id": chat, "text": text, "parse_mode": "HTML",
                                   "disable_web_page_preview": "true"}).encode()
    urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=20)


def headlines(name: str) -> list[str]:
    return [n.title for n in get_news(name) if len(n.title.split()) >= 5
            and "stock price, news, quote" not in n.title.lower()]


def rs(x: float) -> str:
    return f"₹{x:,.0f}"


def main() -> None:
    today = dt.datetime.now(IST).date()
    settings = storage.load_settings()
    portfolio = storage.load_portfolio()
    watchlist = storage.load_watchlist()
    msgs: list[str] = []

    # Market mood
    nifty = get_index("^NSEI")
    if nifty and nifty.get("month_pct") is not None:
        week = get_stock("^NSEI").change_over(5)
        if week is not None and week <= -3:
            msgs.append(f"📉 The market (Nifty 50) fell {abs(week):.1f}% this week. This is normal and happens "
                        "a few times every year. Your plan doesn't change. Your SIP buys more units when prices are low.")

    # Holdings
    total_now = total_inv = stocks_now = 0.0
    for _, r in portfolio.iterrows():
        if r["type"] == "fund":
            nav, _, _ = get_mf_nav(str(r["scheme_code"])) if pd.notna(r["scheme_code"]) else (None, None, None)
            if nav and pd.notna(r["quantity"]):
                total_now += nav * r["quantity"]
                total_inv += r["invested"] if pd.notna(r["invested"]) else 0
            continue
        s = get_stock(str(r["symbol"]))
        if s.error:
            continue
        heads = headlines(s.name)
        sc = score_stock(s, heads)
        qty = r["quantity"] or 0
        stocks_now += qty * s.price
        total_now += qty * s.price
        total_inv += qty * (r["avg_price"] or 0)
        day = s.day_change_pct or 0
        if day <= -5 or day >= 8:
            arrow = "🔻" if day < 0 else "🚀"
            text = f"{arrow} <b>{s.name}</b> moved {day:+.1f}% today (now ₹{s.price:,.0f})."
            summary = ai.summarize_company(s.name, sc.verdict, [f"Moved {day:+.1f}% today"], heads[:8]) if ai.available() else None
            text += "\n" + (summary or ("Recent news:\n• " + "\n• ".join(heads[:3]) if heads else "No news found explaining it."))
            text += f"\nChecklist verdict: <b>{sc.verdict}</b>. A single day's move rarely changes a long-term plan."
            msgs.append(text)
        if today.weekday() == 0 and sc.verdict in ("Review", "Avoid"):
            why = "; ".join(sc.watch_outs[:2]) or sc.summary
            msgs.append(f"⚠️ <b>{s.name}</b> is marked <b>{sc.verdict}</b>. Why: {why}\nOpen it in the app's Stock check tab before adding more.")

    # Watchlist opportunities
    for sym in watchlist["symbol"].tolist():
        s = get_stock(sym)
        if s.error:
            continue
        month = s.change_over(21)
        if month is None or month > -10:
            continue
        sc = score_stock(s, headlines(s.name))
        if sc.overall and sc.overall >= 6.5 and (sc.pillars[0].score or 0) >= 7:
            msgs.append(f"🔎 <b>{s.name}</b> (watchlist) is down {abs(month):.0f}% in a month, but its checklist "
                        f"score is still {sc.overall}/10 ({sc.verdict}). Could be a chance to start buying slowly. "
                        "Check the news first.")

    # SIP reminder
    sip_day = int(settings.get("sip_day", 15))
    if (today + dt.timedelta(days=1)).day == sip_day:
        msgs.append(f"🗓️ Reminder: your {rs(settings.get('monthly_sip', 0))} SIP runs tomorrow. "
                    "Make sure your bank account has enough balance.")

    # Monthly summary on the first weekday of the month
    first_weekday = today.day <= 3 and all((today - dt.timedelta(days=k)).weekday() >= 5
                                           for k in range(1, today.day))
    if first_weekday and total_inv:
        share = stocks_now / total_now * 100 if total_now else 0
        target = settings.get("target_stock_share", 25)
        line = (f"📊 <b>Monthly summary</b>\nWorth {rs(total_now)} · invested {rs(total_inv)} · "
                f"gain {(total_now / total_inv - 1) * 100:+.1f}%\nStocks are {share:.0f}% of your money (target {target}%).")
        if share > target + 10:
            line += "\nPut extra money into your index fund this month, not stocks."
        msgs.append(line)

    # Gold savings plan: payment reminder 2 days before, and missed-payment warning
    plan, pays = gold.load_plan(), gold.load_payments()
    if plan.get("start_month") or not pays.empty:
        sched = gold.schedule(plan, pays, today)
        tone, health = gold.scheme_health(sched)
        cur = next((s for s in sched if s.month == today.replace(day=1)), None)
        due_day = min(int(plan.get("due_day", 10)), 28)
        if cur and cur.status == "due":
            owed = float(plan["monthly_amount"]) * (2 if tone == "warn" else 1)
            due_date = today.replace(day=due_day)
            if (due_date - today).days == 2:
                msgs.append(f"🪙 Gold plan: {rs(owed)} is due on {due_date:%d %b}. "
                            "Collect the receipt and add it in the app's Gold plan tab.")
            elif (today - due_date).days == 7:
                msgs.append(f"🪙 Gold plan: this month's {rs(owed)} hasn't been recorded yet. "
                            "If you've paid, add the receipt in the app. If not, pay this month to stay in the scheme.")
        if tone == "bad" and today.weekday() == 0:
            msgs.append("🚨 Gold plan: " + health)

    if not msgs:
        print("Nothing worth messaging about today.")
        return
    for m in msgs:
        send(m)
    print(f"Sent {len(msgs)} message(s).")


if __name__ == "__main__":
    main()

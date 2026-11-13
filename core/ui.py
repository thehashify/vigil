"""Visual building blocks: page styling, cards, sparklines, pills and score bars.

Everything is plain HTML/CSS injected through st.markdown, so it stays fast and needs no extra packages.
"""
from __future__ import annotations

import html

# Palette: deep teal ink on a cool off-white, with saffron as the one warm highlight.
INK = "#10201d"
MUTED = "#5d6f6b"
LINE = "#dbe4e1"
BG = "#f2f5f4"
SURFACE = "#ffffff"
ACCENT = "#0f6b5c"
ACCENT_SOFT = "#dcefe9"
SAFFRON = "#e08a1e"
GOOD, GOOD_BG = "#16803c", "#e1f4e7"
WARN, WARN_BG = "#a46a00", "#fcf0d7"
BAD, BAD_BG = "#c0322a", "#fce4e1"
NEUTRAL, NEUTRAL_BG = "#4f5f5b", "#e9efed"

TONES = {"good": (GOOD, GOOD_BG), "neutral": (NEUTRAL, NEUTRAL_BG), "warn": (WARN, WARN_BG), "bad": (BAD, BAD_BG)}

CSS = f"""
<style>
@import url("https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700;12..96,800&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500&display=swap");
:root {{ --ink:{INK}; --muted:{MUTED}; --line:{LINE}; --accent:{ACCENT}; --accent-soft:{ACCENT_SOFT};
        --saffron:{SAFFRON}; --surface:{SURFACE}; }}
html, body, .stMarkdown, p, li, label, input, textarea, button, td, th {{ font-family: "IBM Plex Sans", system-ui, sans-serif; }}
[data-testid="stIconMaterial"], .material-symbols-rounded {{ font-family: "Material Symbols Rounded" !important; }}
h1, h2, h3, h4 {{ font-family: "Bricolage Grotesque", "IBM Plex Sans", sans-serif !important; letter-spacing: -0.01em; }}
.block-container {{ padding-top: 2.2rem; padding-bottom: 4rem; max-width: 1220px; }}
.stDeployButton, [data-testid="stAppDeployButton"] {{ display: none; }}
.num {{ font-family: "Bricolage Grotesque", sans-serif; font-variant-numeric: tabular-nums; }}
.mono {{ font-family: "IBM Plex Mono", monospace; font-size: .78rem; }}

/* tabs */
.stTabs [data-baseweb="tab-list"] {{ gap: 6px; border-bottom: 1px solid var(--line); flex-wrap: wrap; }}
.stTabs [data-baseweb="tab"] {{ padding: 10px 16px; border-radius: 10px 10px 0 0; font-weight: 600; }}
.stTabs [aria-selected="true"] {{ background: var(--accent-soft); color: var(--accent) !important; }}

/* entrance motion */
@keyframes rise {{ from {{ opacity: .001; transform: translateY(10px); }} to {{ opacity: 1; transform: none; }} }}
@keyframes pulse {{ 0% {{ box-shadow: 0 0 0 0 rgba(22,128,60,.55); }} 70% {{ box-shadow: 0 0 0 9px rgba(22,128,60,0); }} 100% {{ box-shadow: 0 0 0 0 rgba(22,128,60,0); }} }}
.rise {{ animation: rise .55s cubic-bezier(.2,.7,.2,1) both; }}
@media (prefers-reduced-motion: reduce) {{ .rise, .live-dot {{ animation: none !important; }} }}

/* hero */
.hero {{ background: radial-gradient(120% 140% at 0% 0%, #155f52 0%, #0d3f37 55%, #0a2e29 100%);
         color: #eaf6f2; border-radius: 22px; padding: 26px 28px; position: relative; overflow: hidden; }}
.hero::after {{ content: ""; position: absolute; right: -60px; top: -60px; width: 260px; height: 260px;
               border-radius: 50%; background: radial-gradient(circle, rgba(224,138,30,.35), rgba(224,138,30,0) 70%); }}
.hero .label {{ font-size: .82rem; letter-spacing: .08em; text-transform: uppercase; opacity: .75; }}
.hero .big {{ font-family: "Bricolage Grotesque", sans-serif; font-size: clamp(2.2rem, 5vw, 3.4rem); font-weight: 800; line-height: 1.05; margin: 6px 0 10px; }}
.hero .chips {{ display: flex; gap: 8px; flex-wrap: wrap; position: relative; z-index: 1; }}
.hero .chip {{ background: rgba(255,255,255,.12); border: 1px solid rgba(255,255,255,.18); border-radius: 99px;
               padding: 5px 12px; font-size: .88rem; }}
.hero .chip b {{ font-weight: 600; }}

/* market strip */
.strip {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; }}
.tick {{ background: var(--surface); border: 1px solid var(--line); border-radius: 14px; padding: 12px 14px;
         display: grid; grid-template-columns: 1fr auto; gap: 2px 10px; align-items: center; }}
.tick .n {{ font-size: .8rem; color: var(--muted); font-weight: 600; }}
.tick .v {{ font-family: "Bricolage Grotesque", sans-serif; font-size: 1.35rem; font-weight: 700; }}
.tick svg {{ grid-row: span 3; }}
@media (max-width: 560px) {{
  .strip {{ grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }}
  .tick {{ padding: 10px; grid-template-columns: 1fr; }}
  .tick svg, .tick .m1 {{ display: none; }}
  .tick .v {{ font-size: 1.05rem; }}
  .tick .n, .tick span {{ font-size: .74rem !important; }}
  .hero {{ padding: 20px; }}
}}
.status {{ display: inline-flex; align-items: center; gap: 8px; font-size: .85rem; color: var(--muted); }}
.live-dot {{ width: 9px; height: 9px; border-radius: 50%; background: {GOOD}; animation: pulse 1.8s infinite; }}
.closed-dot {{ width: 9px; height: 9px; border-radius: 50%; background: #9aa9a5; }}

/* cards */
.card {{ background: var(--surface); border: 1px solid var(--line); border-radius: 16px; padding: 16px 18px;
         transition: transform .18s ease, box-shadow .18s ease; }}
.card:hover {{ transform: translateY(-2px); box-shadow: 0 14px 30px -22px rgba(16,32,29,.45); }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; }}
.hold .top {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }}
.hold .name {{ font-family: "Bricolage Grotesque", sans-serif; font-weight: 700; font-size: 1.08rem; line-height: 1.2; }}
.hold .sym {{ color: var(--muted); }}
.hold .worth {{ font-family: "Bricolage Grotesque", sans-serif; font-size: 1.5rem; font-weight: 700; margin-top: 8px; }}
.hold .row {{ display: flex; gap: 14px; font-size: .88rem; color: var(--muted); margin-top: 2px; flex-wrap: wrap; }}
.pill {{ display: inline-block; padding: 3px 10px; border-radius: 99px; font-size: .76rem; font-weight: 600; white-space: nowrap; }}
.up {{ color: {GOOD}; }} .down {{ color: {BAD}; }}

/* to-do */
.todo {{ display: grid; gap: 10px; }}
.todo .item {{ display: grid; grid-template-columns: 38px 1fr; gap: 12px; align-items: start; }}
.todo .ic {{ width: 38px; height: 38px; border-radius: 12px; display: grid; place-items: center; font-size: 1.15rem; }}
.todo .t {{ font-weight: 600; }}
.todo .d {{ color: var(--muted); font-size: .92rem; }}

/* verdict + score bars */
.verdict {{ border-radius: 18px; padding: 18px 20px; }}
.verdict .k {{ font-size: .78rem; letter-spacing: .08em; text-transform: uppercase; opacity: .8; }}
.verdict .v {{ font-family: "Bricolage Grotesque", sans-serif; font-size: 1.7rem; font-weight: 800; margin: 2px 0 6px; }}
.bars {{ display: grid; gap: 12px; }}
.bar .lbl {{ display: flex; justify-content: space-between; font-size: .9rem; margin-bottom: 5px; }}
.bar .track {{ height: 10px; border-radius: 99px; background: #e8eeec; overflow: hidden; }}
.bar .fill {{ height: 100%; border-radius: 99px; transform-origin: left; animation: grow .9s cubic-bezier(.2,.7,.2,1) both; }}
@keyframes grow {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}
@media (prefers-reduced-motion: reduce) {{ .bar .fill {{ animation: none; }} }}

/* gold plan */
.hero.gold {{ background: radial-gradient(120% 140% at 0% 0%, #6b4a12 0%, #3f2b08 60%, #2a1c05 100%); color: #fbf1dc; }}
.hero.gold::after {{ background: radial-gradient(circle, rgba(255,214,120,.45), rgba(255,214,120,0) 70%); }}
.ring {{ width: 132px; height: 132px; border-radius: 50%; display: grid; place-items: center; flex: none; }}
.ring .in {{ width: 100px; height: 100px; border-radius: 50%; background: #2f2006; display: grid; place-items: center;
            text-align: center; line-height: 1.1; }}
.ring .in b {{ font-family: "Bricolage Grotesque", sans-serif; font-size: 1.6rem; }}
.months {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(78px, 1fr)); gap: 8px; }}
.mo {{ border-radius: 12px; padding: 8px 6px; text-align: center; font-size: .8rem; border: 1px solid var(--line); background: var(--surface); }}
.mo .l {{ font-weight: 600; }}
.mo .s {{ font-size: .72rem; margin-top: 2px; }}
.mo.paid, .mo.double, .mo.covered {{ background: {GOOD_BG}; border-color: transparent; color: {GOOD}; }}
.mo.due {{ background: {WARN_BG}; border-color: {SAFFRON}; color: {WARN}; box-shadow: 0 0 0 2px rgba(224,138,30,.25); }}
.mo.missed {{ background: {BAD_BG}; border-color: transparent; color: {BAD}; }}
.mo.upcoming {{ color: var(--muted); }}
.kv {{ display: grid; grid-template-columns: 1fr auto; gap: 8px 16px; font-size: .95rem; }}
.kv .t {{ border-top: 1px solid var(--line); padding-top: 8px; font-weight: 700; }}

/* 52-week range */
.range {{ margin-top: 6px; }}
.range .track {{ position: relative; height: 8px; border-radius: 99px;
                 background: linear-gradient(90deg, {BAD_BG}, #f4f1e6 50%, {GOOD_BG}); }}
.range .dot {{ position: absolute; top: 50%; width: 16px; height: 16px; border-radius: 50%; background: var(--ink);
               border: 3px solid #fff; transform: translate(-50%, -50%); box-shadow: 0 2px 6px rgba(0,0,0,.25); }}
.range .ends {{ display: flex; justify-content: space-between; font-size: .8rem; color: var(--muted); margin-top: 6px; }}

/* news */
.news a {{ color: var(--ink); text-decoration: none; font-weight: 500; }}
.news a:hover {{ color: var(--accent); text-decoration: underline; }}
.news .item {{ padding: 10px 0; border-bottom: 1px solid var(--line); }}
.news .meta {{ font-size: .8rem; color: var(--muted); margin-top: 2px; }}
.section-title {{ display: flex; align-items: baseline; justify-content: space-between; gap: 10px; margin: 26px 0 12px; flex-wrap: wrap; }}
.section-title .h {{ font-family: "Bricolage Grotesque", sans-serif; font-size: 1.4rem; font-weight: 700; color: var(--ink); line-height: 1.2; }}
.section-title span {{ color: var(--muted); font-size: .88rem; }}
[data-testid="stMetric"] {{ background: var(--surface); border: 1px solid var(--line); border-radius: 14px; padding: 12px 14px; }}
</style>
"""


# Markdown ends an HTML block at a blank line, so strip blank lines before injecting.
CSS = "\n".join(line for line in CSS.splitlines() if line.strip())


def esc(x) -> str:
    return html.escape(str(x))


def tone_for_change(x: float | None) -> str:
    if x is None:
        return ""
    return "up" if x >= 0 else "down"


def signed(x: float | None, digits: int = 1, suffix: str = "%") -> str:
    if x is None:
        return "–"
    arrow = "▲" if x >= 0 else "▼"
    return f"{arrow} {abs(x):.{digits}f}{suffix}"


def pill(text: str, tone: str) -> str:
    fg, bg = TONES.get(tone, TONES["neutral"])
    return f'<span class="pill" style="color:{fg};background:{bg}">{esc(text)}</span>'


def sparkline(values: list[float], width: int = 120, height: int = 40, color: str | None = None,
              fill: bool = True) -> str:
    """A tiny inline SVG line chart. Green if the series ended higher than it started, red otherwise."""
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return f'<svg width="{width}" height="{height}"></svg>'
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    pad = 3
    step = (width - 2 * pad) / (len(vals) - 1)
    pts = [(pad + i * step, pad + (height - 2 * pad) * (1 - (v - lo) / span)) for i, v in enumerate(vals)]
    c = color or (GOOD if vals[-1] >= vals[0] else BAD)
    path = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = path + f" L{pts[-1][0]:.1f},{height} L{pts[0][0]:.1f},{height} Z"
    ex, ey = pts[-1]
    gid = f"g{abs(hash((tuple(vals[:3]), len(vals), c))) % 10**8}"
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="trend">'
        f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{c}" stop-opacity=".28"/><stop offset="100%" stop-color="{c}" stop-opacity="0"/>'
        f'</linearGradient></defs>'
        + (f'<path d="{area}" fill="url(#{gid})"/>' if fill else "")
        + f'<path d="{path}" fill="none" stroke="{c}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
        f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="3" fill="{c}"/></svg>'
    )


def score_color(score: float | None) -> str:
    if score is None:
        return "#c5d0cd"
    return GOOD if score >= 7 else SAFFRON if score >= 5 else BAD


def score_bars(pillars) -> str:
    rows = []
    for k, p in enumerate(pillars):
        if p.score is None:
            rows.append(f'<div class="bar"><div class="lbl"><span>{esc(p.name)}</span>'
                        f'<span style="color:{MUTED}">no data</span></div><div class="track"></div></div>')
            continue
        rows.append(
            f'<div class="bar"><div class="lbl"><span>{esc(p.name)}</span><b class="num">{p.score:.1f}</b></div>'
            f'<div class="track"><div class="fill" style="width:{p.score * 10:.0f}%;background:{score_color(p.score)};'
            f'animation-delay:{k * 0.08:.2f}s"></div></div></div>')
    return '<div class="bars">' + "".join(rows) + "</div>"


def range_bar(low: float, high: float, now: float, fmt) -> str:
    pos = 0 if high == low else max(0, min(100, (now - low) / (high - low) * 100))
    return (f'<div class="range"><div class="track"><div class="dot" style="left:{pos:.1f}%"></div></div>'
            f'<div class="ends"><span>52-wk low {fmt(low)}</span><span>52-wk high {fmt(high)}</span></div></div>')

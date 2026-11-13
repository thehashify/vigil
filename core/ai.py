"""Optional AI analyst: plain-language news summaries using the Claude API.

Works only when an ANTHROPIC_API_KEY is set (in Streamlit secrets or GitHub secrets).
Without it, the app still works and shows the raw headlines instead.
"""
from __future__ import annotations

import os

MODEL = "claude-opus-5-5"

SYSTEM = (
    "You are a calm, careful assistant helping a complete beginner who invests for the long term "
    "(3+ years) in Indian stocks and index funds. Explain in very simple English, no jargon. "
    "Never predict short-term prices and never tell them to trade on news. "
    "Give context: one quarter of bad news rarely changes a long-term view. "
    "Do not invent facts that aren't in the headlines or numbers given."
)


def api_key() -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    try:
        import streamlit as st
        return st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:
        return None


def available() -> bool:
    return bool(api_key())


def _call(prompt: str, max_tokens: int = 700) -> str | None:
    key = api_key()
    if not key:
        return None
    import anthropic

    client = anthropic.Anthropic(api_key=key)
    common = dict(
        model=MODEL,
        max_tokens=max_tokens,
        system=SYSTEM,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        # Server-side fallback: if the request is declined, the API retries it on another model.
        resp = client.beta.messages.create(
            betas=["server-side-fallback-2026-07-01"], fallbacks="default", **common
        )
    except anthropic.BadRequestError:
        resp = client.messages.create(**common)
    except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.APIStatusError) as e:
        return f"(AI summary unavailable right now: {type(e).__name__})"
    if resp.stop_reason == "refusal":
        return None
    return "".join(b.text for b in resp.content if b.type == "text").strip() or None


def summarize_company(name: str, verdict: str, facts: list[str], headlines: list[str]) -> str | None:
    if not headlines and not facts:
        return None
    prompt = (
        f"Company: {name}\nCurrent checklist verdict: {verdict}\n\nKey numbers:\n- "
        + "\n- ".join(facts or ["(none)"])
        + "\n\nHeadlines from the last 30 days:\n- "
        + "\n- ".join(headlines or ["(none)"])
        + "\n\nWrite exactly 3 short bullet points (start each with '- '):\n"
        "1. What's been happening with this company lately.\n"
        "2. Whether any of it matters for someone holding for 3+ years, and why.\n"
        "3. One thing to keep an eye on.\nMax 70 words total."
    )
    return _call(prompt)


def daily_briefing(lines: list[str]) -> str | None:
    """lines: one per holding, e.g. 'Infosys: -1.2% today, verdict Hold, headlines: ...'"""
    if not lines:
        return None
    prompt = (
        "Here is today's data for my holdings:\n" + "\n".join(lines) +
        "\n\nWrite a briefing of at most 4 bullet points (start each with '- '), most important first. "
        "Bold the company name like **Name**. Say clearly if no action is needed. Max 90 words."
    )
    return _call(prompt)

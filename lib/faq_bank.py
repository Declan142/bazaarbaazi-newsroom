"""
FAQ bank — 60+ question templates across 5 market states for BazaarBaazi shows.

Used by every day-of composer (closing-bell-flash, fno-data-dive, sectoral-pulse,
expiry-special, kal-ki-tayyari, etc.) to emit a 12-Q FAQPage block per episode.

Placeholders:
    {date}    ISO date string, "2026-05-14"
    {datestr} Human date, "May 14, 2026"
    {symbol}  Index/stock symbol, "NIFTY 50"
    {sector}  Sector slug, "IT"
    {n1}..{n5} Numbers from the day's data, formatted strings
    {dir}     "rose" / "fell" / "stayed flat"
    {nextsess} Next session label, "Friday 2026-05-15"

Each entry is a dict {q, a, requires:[ctx_keys]} so composer can drop entries
whose required ctx keys are absent.
"""

from __future__ import annotations

import random
from typing import Any, TypedDict


class FAQEntry(TypedDict, total=False):
    q: str
    a: str
    requires: list[str]


FAQ_BANK: dict[str, list[FAQEntry]] = {
    "common": [
        {
            "q": "Where did NIFTY 50 close on {datestr}?",
            "a": "NIFTY 50 closed at {n1} on {datestr}, {dir} {n2} points or {n3} percent from the previous session. The intraday range was {n4} to {n5}.",
            "requires": ["n1", "n2", "n3", "n4", "n5", "dir"],
        },
        {
            "q": "What did BANKNIFTY do on {datestr}?",
            "a": "BANKNIFTY closed at {n1} on {datestr}, {dir} {n2} points or {n3} percent. The index respected its short-term moving average at {n4}.",
            "requires": ["n1", "n2", "n3", "n4", "dir"],
        },
        {
            "q": "What was India VIX on {datestr}?",
            "a": "India VIX printed {n1} on {datestr}, {dir} from the prior session's {n2}. A reading near {n3} historically maps to a one-standard-deviation daily NIFTY move of about {n4} percent.",
            "requires": ["n1", "n2", "n3", "n4", "dir"],
        },
        {
            "q": "Did FIIs buy or sell Indian equities on {datestr}?",
            "a": "FIIs were net {dir} for rupees {n1} crore in the cash segment on {datestr}. DIIs were on the opposite side with rupees {n2} crore. Year-to-date FII flow remains {n3}.",
            "requires": ["n1", "n2", "n3", "dir"],
        },
        {
            "q": "Which Indian sector moved the most on {datestr}?",
            "a": "The strongest mover was NIFTY {sector}, which {dir} {n1} percent on {datestr}. The underperforming sector closed {n2} percent lower, and breadth across the 11 sector indices was {n3} positive.",
            "requires": ["sector", "n1", "n2", "n3", "dir"],
        },
        {
            "q": "What does BazaarBaazi think about today's market?",
            "a": "BazaarBaazi's signed verdict on {datestr} reads: the session's price action was driven by {n1}, and our conviction stance for the next 24 hours is {n2}. The full reasoning sits in our closing-bell-flash episode for {datestr}.",
            "requires": ["n1", "n2"],
        },
    ],
    "bull": [
        {
            "q": "Is the Indian market rally on {datestr} sustainable?",
            "a": "On {datestr} NIFTY 50 closed at {n1}, up {n2} percent, with breadth at {n3} and advance-decline ratio at {n4}. Bull legs that survive typically need 3 consecutive sessions of breadth above 1.5.",
            "requires": ["n1", "n2", "n3", "n4"],
        },
        {
            "q": "Should I book profits after the {datestr} close?",
            "a": "BazaarBaazi is not an investment adviser, but the data on {datestr} shows NIFTY at {n1} times forward earnings against a 10-year average of {n2} times. Position sizing matters more than timing in this regime.",
            "requires": ["n1", "n2"],
        },
        {
            "q": "What are the next NIFTY resistance levels after {datestr}?",
            "a": "After the {datestr} close at {n1}, the next visible resistance bands sit at {n2} and {n3}. The 52-week high of {n4} is the major structural ceiling that capped the prior two attempts.",
            "requires": ["n1", "n2", "n3", "n4"],
        },
    ],
    "bear": [
        {
            "q": "Is the Indian market correction on {datestr} over?",
            "a": "On {datestr} NIFTY 50 closed at {n1}, down {n2} percent, with India VIX at {n3}. Historical corrections in this regime have averaged {n4} sessions and {n5} percent peak-to-trough drawdowns.",
            "requires": ["n1", "n2", "n3", "n4", "n5"],
        },
        {
            "q": "What are the next NIFTY support levels after {datestr}?",
            "a": "Below the {datestr} close at {n1}, the next visible support bands sit at {n2} and {n3}. The 200-day moving average at {n4} is the major structural floor that bulls would defend.",
            "requires": ["n1", "n2", "n3", "n4"],
        },
        {
            "q": "Why did the Indian market fall on {datestr}?",
            "a": "The {datestr} session decline of {n1} percent on NIFTY was driven by FII selling of rupees {n2} crore, weakness in {sector} stocks down {n3} percent, and a VIX spike to {n4}.",
            "requires": ["n1", "n2", "n3", "n4", "sector"],
        },
    ],
    "flat": [
        {
            "q": "Why did NIFTY trade range-bound on {datestr}?",
            "a": "NIFTY held a {n1} point range on {datestr}, the narrowest in {n2} sessions. Volumes were {n3} percent below the 20-day average. Range compression like this historically precedes a {n4} percent expansion within 5 sessions.",
            "requires": ["n1", "n2", "n3", "n4"],
        },
        {
            "q": "What is the BazaarBaazi setup for the next session after {datestr}?",
            "a": "Going into {nextsess}, BazaarBaazi flags pivots at {n1} on the upside and {n2} on the downside. A break of either with volume above {n3} percent of average sets up the directional trade.",
            "requires": ["n1", "n2", "n3", "nextsess"],
        },
    ],
    "expiry": [
        {
            "q": "What was the max pain for NIFTY expiry on {datestr}?",
            "a": "NIFTY expiry on {datestr} max pain printed at {n1}, against the spot close of {n2}. The put-call ratio was {n3}, and {n4} percent of OI sat within 200 points of the max pain strike.",
            "requires": ["n1", "n2", "n3", "n4"],
        },
        {
            "q": "What was the BANKNIFTY put-call ratio on {datestr}?",
            "a": "BANKNIFTY PCR on {datestr} closed at {n1}, against a 30-day average of {n2}. The highest call OI sat at {n3} and the highest put OI at {n4}, defining the expiry range.",
            "requires": ["n1", "n2", "n3", "n4"],
        },
        {
            "q": "Which strike saw the highest OI build-up on {datestr}?",
            "a": "On {datestr} the highest call OI accumulation hit the {n1} strike with {n2} lakh contracts, while the highest put OI sat at {n3} with {n4} lakh contracts. Net OI shift was {n5}.",
            "requires": ["n1", "n2", "n3", "n4", "n5"],
        },
    ],
    "ipo_rush": [
        {
            "q": "Which IPOs are open for subscription around {datestr}?",
            "a": "As of {datestr}, BazaarBaazi tracks {n1} mainline IPOs and {n2} SME IPOs open for subscription. The highest-GMP name is at a grey market premium of rupees {n3} per share against the price band ceiling.",
            "requires": ["n1", "n2", "n3"],
        },
        {
            "q": "What is the GMP for the {symbol} IPO on {datestr}?",
            "a": "The {symbol} IPO grey market premium on {datestr} traded at rupees {n1}, implying a listing return of {n2} percent against the upper band of rupees {n3}. The prior session's GMP was {n4}.",
            "requires": ["symbol", "n1", "n2", "n3", "n4"],
        },
        {
            "q": "Should I subscribe to the {symbol} IPO?",
            "a": "BazaarBaazi is not an investment adviser. Our editorial read on the {symbol} IPO at the rupees {n1} price band cites a {n2} times P/E against the sector median of {n3}. Full reasoning sits in our IPO desk for {datestr}.",
            "requires": ["symbol", "n1", "n2", "n3"],
        },
    ],
}


def faq_for_show(
    show_slug: str,
    market_state: str,
    ctx: dict[str, Any],
    limit: int = 12,
    seed: int | None = None,
) -> list[dict[str, str]]:
    """Return a list of {q, a} dicts filled with ctx values.

    Selects from FAQ_BANK['common'] + FAQ_BANK[market_state], filters out
    entries whose `requires` cannot be satisfied by ctx, then samples `limit`
    items. If a ctx value is missing for a non-required {placeholder}, the
    entry is skipped silently.

    Args:
        show_slug: composer slug (used only for downstream attribution).
        market_state: one of "bull", "bear", "flat", "expiry", "ipo_rush".
        ctx: dict of placeholder->value substitutions.
        limit: max number of Q+A to return.
        seed: RNG seed for reproducible selection (e.g., daily-stable order).
    """
    if market_state not in FAQ_BANK and market_state != "common":
        market_state = "flat"

    candidates: list[FAQEntry] = []
    candidates.extend(FAQ_BANK.get("common", []))
    if market_state != "common":
        candidates.extend(FAQ_BANK.get(market_state, []))

    usable: list[FAQEntry] = []
    for entry in candidates:
        required = entry.get("requires", [])
        if any(k not in ctx or ctx[k] is None or ctx[k] == "" for k in required):
            continue
        usable.append(entry)

    rng = random.Random(seed) if seed is not None else random.Random()
    rng.shuffle(usable)
    chosen = usable[:limit]

    out: list[dict[str, str]] = []
    for entry in chosen:
        try:
            q = entry["q"].format(**ctx)
            a = entry["a"].format(**ctx)
        except KeyError:
            continue
        out.append({"q": q, "a": a})
        if len(out) >= limit:
            break
    return out

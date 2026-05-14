"""
Chart-brief generator for BazaarBaazi show composers.

Each show maps to a fixed set of session charts captured by
`scripts/capture-session-charts.py`. This module returns the
Markdown inventory + structural instructions the composer hands
to Opus so each episode embeds the right charts inline at the
right structural break.

Public API:
    chart_inventory_for(show_slug: str, focus_date: str) -> str
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
MANIFEST_DIR = ROOT / "public" / "charts" / "_manifest"


# Each entry: (slug, caption, position_hint)
# position_hint = the H3 section under which the chart should sit
# Keep entries in the order Opus should embed them.
CHART_PLAN: dict[str, list[tuple[str, str, str]]] = {
    "pratham-khabar": [
        ("NIFTY_50",     "Nifty 50 daily — yesterday's close and the overnight gap-up reference for the day frame",  "Overnight tape"),
        ("INDIA_VIX",    "India VIX daily — the volatility regime headed into the open",                              "Overnight tape"),
        ("NIFTY_BANK",   "Nifty Bank daily — financials' leadership question",                                        "Overnight tape"),
        ("NIFTY_IT",     "Nifty IT daily — US tech tape carry-over read",                                             "Overnight tape"),
    ],
    "opening-move": [
        ("NIFTY_50",     "Nifty 50 daily — the close that the pre-open reads off",                                    "Levels in"),
        ("NIFTY_BANK",   "Nifty Bank daily — pivot structure heading into 09:15",                                     "Levels in"),
        ("INDIA_VIX",    "India VIX daily — the premium regime for the day's writers",                                "Levels in"),
    ],
    "opening-15": [
        ("NIFTY_50",     "Nifty 50 daily — the reference candle the 09:15 to 09:30 print sets against",               "First quarter"),
        ("NIFTY_BANK",   "Nifty Bank daily — leadership read for the first 15 minutes",                               "First quarter"),
    ],
    "sectoral-pulse": [
        ("NIFTY_IT",       "Nifty IT — mid-session tech read",          "Sector by sector"),
        ("NIFTY_AUTO",     "Nifty Auto — auto and ancillaries",         "Sector by sector"),
        ("NIFTY_PHARMA",   "Nifty Pharma — health-care defensive",      "Sector by sector"),
        ("NIFTY_METAL",    "Nifty Metal — base-metal cyclical bid",     "Sector by sector"),
        ("NIFTY_ENERGY",   "Nifty Energy — oil and power",              "Sector by sector"),
        ("NIFTY_FMCG",     "Nifty FMCG — staples defensive",            "Sector by sector"),
        ("NIFTY_REALTY",   "Nifty Realty — rate-cycle proxy",           "Sector by sector"),
        ("NIFTY_PSU_BANK", "Nifty PSU Bank — PSU credit cycle",         "Sector by sector"),
    ],
    "pre-close-watch": [
        ("NIFTY_50",   "Nifty 50 daily — the close-bias reference",                       "Last two hours"),
        ("NIFTY_BANK", "Nifty Bank daily — the pivot the financials must hold",           "Last two hours"),
        ("INDIA_VIX",  "India VIX daily — the volatility lean into the close",            "Last two hours"),
    ],
    "closing-bell-flash": [
        ("NIFTY_50",         "Nifty 50 daily — the close print",                          "Where the indices settled"),
        ("NIFTY_BANK",       "Nifty Bank daily — financials' settlement",                 "Where the indices settled"),
        ("NIFTY_MIDCAP_100", "Nifty Midcap 100 daily — mid-cap breadth",                  "Where the indices settled"),
        ("NIFTY_SMLCAP_100", "Nifty Smallcap 100 daily — small-cap breadth",              "Where the indices settled"),
        ("INDIA_VIX",        "India VIX daily — the day's volatility imprint",            "Where the indices settled"),
        ("NIFTY_IT",         "Nifty IT daily — tech leadership",                          "Sectors that worked, sectors that didn't"),
        ("NIFTY_AUTO",       "Nifty Auto daily — auto rotation",                          "Sectors that worked, sectors that didn't"),
        ("NIFTY_PSU_BANK",   "Nifty PSU Bank daily — PSU credit",                         "Sectors that worked, sectors that didn't"),
    ],
    "fno-data-dive": [
        ("NIFTY_50",   "Nifty 50 daily — the underlying tape behind the option chain",      "The Nifty chain"),
        ("NIFTY_BANK", "Nifty Bank daily — the BankNifty chain reference",                  "The BankNifty chain"),
        ("INDIA_VIX",  "India VIX daily — IV regime for the writers and buyers",            "The volatility frame"),
    ],
    "expiry-special": [
        ("NIFTY_50",   "Nifty 50 daily — the expiry-day reference candle",                  "The 09:15 to 11:00 walk"),
        ("NIFTY_BANK", "Nifty Bank daily — the BankNifty walk through the morning",         "The 09:15 to 11:00 walk"),
        ("INDIA_VIX",  "India VIX daily — the IV crush regime for the expiry",              "Max-pain anchor"),
    ],
    "kal-ki-tayyari": [
        ("NIFTY_50",   "Nifty 50 daily — tomorrow's levels off today's close",              "Pivot levels for tomorrow"),
        ("NIFTY_BANK", "Nifty Bank daily — the financials' carry-over",                     "Pivot levels for tomorrow"),
    ],
}


def _load_manifest(focus_date: str) -> dict:
    p = MANIFEST_DIR / f"{focus_date}.json"
    if not p.exists():
        p = MANIFEST_DIR / "latest.json"
    if not p.exists():
        return {"charts": {}}
    return json.loads(p.read_text())


VOICE_AND_STYLE_BLOCK = """\
VOICE AND STYLE — BazaarBaazi house voice (NOT wire-service):

1. **Signed verdict, not Bloomberg-neutral.** Lead with conviction. Anchor every claim in a number. The reader is paying for an editorial take, not a headline feed.

2. **Filmy, not corporate.** The trading floor has heroes (the contra bid), villains (the FII trim), expiry magic (the max-pain pin). Cast them as characters, not jargon. "Writers parked their tents at 25,000 and dared anyone to break them." beats "Nifty 25,000 CE OI rose 32%."

3. **Similes welcome for structural moments.** One per ~300 words. Examples: "VIX printed like a heart-rate monitor flat-lining through the morning." "The 24,900 strike sat like a magnet pulling the spot toward settlement." "PSU Bank ran like the tape forgot 2021 happened." Do not over-use.

4. **Narrative arc per section.** Setup, tension, resolution. The morning had a frame; mid-session broke it; the close confirmed something. Each H2 or H3 tells a beat in that arc, not a list of bullets.

5. **Indian retail desk vocab.** Dalal Street. Writers. Expiry magic. FII trim. DII absorb. Gap and fade. Max-pain dot. Breadth bleed. Sectoral baton. OI flush. Pin risk. Theta crush. The reader knows these. Use them.

6. **One "What BazaarBaazi thinks" verdict line per article (max).** Goes in the closing section. Names the desk owning the read. Example: "What BazaarBaazi thinks: this was distribution dressed as digestion, and tomorrow's open will pay for it."

7. **One punchy 8 to 12 word verdict line near the close.** Rhetorical contrast OK. Example: "Cash bid said yes. Option chain said no."

8. **Sentence rhythm varied.** Punches of 6 to 10 words mixed with build-ups of 22 to 28 words. NEVER five sentences of the same length in a row. Read your draft aloud once before signing off.

9. **BANNED filler.** Strike on sight: 'moreover', 'furthermore', 'in addition', 'it is worth noting', 'as we can see', 'going forward', 'in conclusion', 'key takeaway', 'all things considered', 'needless to say', 'at the end of the day', 'this article will explore', 'now let us turn to'. Replace with action verbs and direct address.

Hard floor stays: zero em-dashes, every claim anchored to a specific number with a date or source tag, pure English body, no Hinglish particles, no buy or sell call.
"""


def chart_inventory_for(show_slug: str, focus_date: str) -> str:
    """Return a Markdown-ready instructions block for Opus.

    Drops in the user prompt to force chart embeds at specific
    structural positions with 60-90 word analytical callouts.
    Also appends the BazaarBaazi voice and style block so the prose
    between charts has conviction, not wire-service neutrality.
    """
    plan = CHART_PLAN.get(show_slug, [])
    if not plan:
        return VOICE_AND_STYLE_BLOCK
    manifest = _load_manifest(focus_date)
    charts = manifest.get("charts", {})

    available: list[tuple[str, str, str, str]] = []
    for slug, caption, pos in plan:
        meta = charts.get(slug)
        if not meta:
            continue
        path = meta.get("path")
        if not path:
            continue
        # Drop the leading /public/ that the capture's relpath produces;
        # web URL is /charts/... (Next.js serves public/ at root).
        web_path = path.replace("/public/charts/", "/charts/")
        available.append((slug, caption, pos, web_path))

    if not available:
        return VOICE_AND_STYLE_BLOCK

    lines = [
        "CHART INVENTORY — embed ALL of these in the body, in the section labeled, using the exact Markdown image syntax shown.",
        "After every image line, write a 60 to 90 word analytical callout that anchors specific numbers off the chart (levels, ranges, recent close, % move from prior close). The callout is signed-verdict, not caption. Read [[VOICE AND STYLE]] below before composing.",
        "",
    ]
    for slug, caption, pos, web_path in available:
        lines.append(f'- **Section: "{pos}"** — embed line:')
        lines.append(f'  `![{caption}]({web_path})`')
        lines.append(f"  Then 60 to 90 words of chart-anchored signed-verdict callout. Cite at least three specific numbers. Filmy not flat.")
        lines.append("")
    lines.append(f"Chart count to embed: {len(available)}. Do not skip any.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(VOICE_AND_STYLE_BLOCK)
    return "\n".join(lines)

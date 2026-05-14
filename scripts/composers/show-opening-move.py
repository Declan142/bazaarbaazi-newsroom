#!/usr/bin/env python3
"""
Opening Move · 09:00 IST daily show composer (last 15 min before cash bell).

Narrative show — no picks array. Tight 800-1000 word cap.

Usage:
  python scripts/show-opening-move.py
  python scripts/show-opening-move.py --date 2026-05-12 --force
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, date as date_cls, timedelta
from pathlib import Path

from pathlib import Path as _P_for_charts
import sys as _sys_for_charts
_sys_for_charts.path.insert(0, str(_P_for_charts(__file__).resolve().parent / 'lib'))
from chart_brief import chart_inventory_for  # session-chart embed instructions

ROOT = Path(__file__).resolve().parent.parent

NSE_HOLIDAYS_2026 = {
    "2026-01-26", "2026-02-19", "2026-03-06", "2026-03-31",
    "2026-04-03", "2026-04-14", "2026-04-21", "2026-05-01",
    "2026-06-26", "2026-08-15", "2026-08-27", "2026-10-02",
    "2026-10-21", "2026-10-22", "2026-11-25", "2026-12-25",
}


def ist_today() -> date_cls:
    now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    return now.date()


def next_session(after_or_eq: date_cls) -> date_cls:
    """Return the next trading day on or after `after_or_eq`.

    Cron fires this composer at 09:00 IST on the session day itself
    (final 15 minutes before NSE cash open). Must return today when
    today is a trading day, not tomorrow.
    """
    d = after_or_eq
    while True:
        s = d.isoformat()
        if d.weekday() < 5 and s not in NSE_HOLIDAYS_2026:
            return d
        d += timedelta(days=1)


SYSTEM_PROMPT = """\
You are the editor at BazaarBaazi, an Indian markets editorial publication.
Byline: Aditya Sharma, X @Declan142, linkedin.com/in/aditya-sharma-119ab4324.

You are writing the 09:00 IST programming slot: OPENING MOVE. This show airs in the final fifteen minutes before the NSE cash session opens at 09:15. The reader is an experienced Indian retail trader or F&O active account. They are reading you with a coffee in their hand at 09:00 IST, fifteen minutes before they need a directional view.

Voice: tight, observational, signed. Pure English. Indian markets vernacular (NSE, FII, DII, SGX, India VIX, OI, strike, gap, premium) is fine. No tip-shop tone. No buy or sell calls. We discuss STRUCTURE.

HARD RULES:
- ZERO em-dashes (the long dash) and ZERO en-dashes. Use commas, periods, parentheses, or 'and'.
- ZERO Hinglish particles (yeh, iska, ab, jo, bagged, wagairah) in body.
- No 'in conclusion', 'it is important to note', 'in retrospect', 'needless to say', 'all things considered'.
- Single byline Aditya Sharma. Never invent analyst or desk names.
- Forward tense for the open ahead. Past tense for overnight context.
- Every paragraph must contain at least one specific number with a date and source anchor (NSE close 2026-05-12, SGX premium, India VIX 12.4, Dow Jones close, etc.).
- No fabricated specifics. If unsure of a number, speak qualitatively.

OUTPUT FORMAT (Markdown only, NO code fences, NO frontmatter):

1. **One-sentence lead** ending with a period. This is the reader's takeaway in twelve to twenty words.
2. **One short paragraph** (under 80 words) on the overnight handover: US close, Asia open posture, the macro frame.
3. **### Pre-open SGX read** — roughly 150 words on SGX Nifty premium or discount, India VIX print, gap-up versus gap-down expectation, the option chain pinning that matters into the open.
4. **### Names on the radar** — roughly 250 words on three to five specific stocks already moving in the grey market or pre-open. For each name a single sharp sentence on why it is on the radar (earnings beat, board meeting, block deal, analyst action, sector rotation). Names should be real F&O universe tickers (RELIANCE, BHARTIARTL, INFY, TCS, HDFCBANK, ICICIBANK, COALINDIA, LT, MARUTI, TATAMOTORS, INDIGO, ADANIPORTS, HAL, BEL, IRCTC, etc.).
5. **### The 09:15 frame** — roughly 200 words on what the editorial desk expects from the first fifteen minutes of cash. Where the gap likely fills or extends, which sectors should lead the tape, where the writers will defend, what a clean confirmation looks like.
6. **One short closing paragraph** (under 80 words) on what to watch through the rest of the morning into the 09:30 Opening 15 debrief.

HARD WORD CAP: 700 to 900 words. The reader has fifteen minutes. Write for that clock.

OUTPUT ONLY the Markdown article body. No frontmatter, no code fences, no trailing JSON.
"""


def claude_p(system: str, user: str, timeout: int = 600) -> str:
    proc = subprocess.run(
        ["claude", "-p", "--model", "claude-opus-4-7", system + "\n\n---\n\n" + user],
        capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude -p failed (exit {proc.returncode}): {proc.stderr[:600]}")
    return proc.stdout.strip()


def build_user_prompt(session_date: date_cls) -> str:
    _base = f"""\
SESSION DATE
============
Writing the Opening Move episode for the upcoming cash session: **{session_date.isoformat()}**. The byline date in frontmatter is the same trading day (the show airs at 09:00 IST that morning).

EDITORIAL CONTEXT
=================
The prior session closed on {ist_today().isoformat()}. Reader assumes you have read the overnight US tape, the SGX Nifty premium, the India VIX print, and the F&O OI structure going into this session. Reader does NOT want a recap of the last week. Reader wants a sharp fifteen-minute frame for the open.

Treat SGX Nifty premium, India VIX, US Dow / Nasdaq / S&P, Dollar Index, Brent, US 10Y yield, Asia-Pacific opens as the macro lens. Treat NSE F&O top-200 plus key sector indices as the names lens. Use realistic, plausibly accurate numbers for an Indian markets session in May 2026. If you do not have a specific number, speak qualitatively (for example "a thin premium" or "a soft Asia open") rather than fabricating a precise figure.

Write the Opening Move Markdown body now. 800 to 1000 words. Five sections per the output format. Tight.
"""
    _inv = chart_inventory_for("opening-move", session_date.isoformat())
    if _inv:
        _base = _base.rstrip() + "\n\n" + _inv + "\n"
    return _base
def write_episode(session_date: date_cls, body: str) -> Path:
    out_dir = ROOT / "content" / "shows" / "opening-move"
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = out_dir / f"{session_date.isoformat()}.md"

    # Defensive em / en / figure / minus dash strip
    body = (body
            .replace("—", ",")
            .replace("–", "-")
            .replace("−", "-")
            .replace("―", "-")
            .replace("‒", "-")
            .replace("…", "..."))

    # Light stance detect from body tail
    tail = body.lower()[-1500:]
    stance = "neutral"
    if any(w in tail for w in ("bullish bias", "constructive open", "gap-up", "gap up", "upward bias")):
        stance = "bullish"
    elif any(w in tail for w in ("bearish bias", "gap-down", "gap down", "soft open", "downside", "selling pressure")):
        stance = "bearish"

    title = f"Opening Move: the fifteen-minute frame for the {session_date.strftime('%a %d %b %Y')} cash open"
    hook = "The pre-open SGX read, the India VIX print, and the names already moving in the grey-market window."

    fm = [
        "---",
        f"title: {json.dumps(title)}",
        f'date: "{session_date.isoformat()}"',
        f"datePublished: {session_date.isoformat()}T09:00:00+05:30",
        "show: opening-move",
        f"hook: {json.dumps(hook)}",
        "author:",
        "  name: Aditya Sharma",
        '  x: "@Declan142"',
        "  linkedin: https://www.linkedin.com/in/aditya-sharma-119ab4324/",
        "verdict:",
        f"  stance: {stance}",
        "  horizon: intraday",
        "tags:",
        "  - opening-move",
        "  - daily-show",
        "  - pre-open",
        "disclosure: \"Opening Move is a 09:00 IST pre-open programming slot produced by BazaarBaazi's editorial AI tooling under the supervision of a five-voice Council, with final editorial sign-off by Aditya Sharma. Structural read, not a buy or sell call.\"",
        "---",
        "",
    ]
    fname.write_text("\n".join(fm) + body + "\n")
    return fname


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="Run-date in IST (YYYY-MM-DD). Default: today IST.")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    run_d = date_cls.fromisoformat(args.date) if args.date else ist_today()
    session_d = next_session(run_d)
    print(f"[opening-move] run_date={run_d}  next_session={session_d}")

    out_path = ROOT / "content" / "shows" / "opening-move" / f"{session_d.isoformat()}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and not args.force:
        print(f"[opening-move] already exists: {out_path}")
        return 0

    user = build_user_prompt(session_d)
    print(f"[opening-move] composing via Opus 4.7 ...")

    t0 = time.time()
    best_body = ""
    best_words = 0
    for attempt in range(2):
        raw = claude_p(SYSTEM_PROMPT, user)
        words = len(raw.split())
        print(f"[opening-move] attempt {attempt+1}: {words} words, {time.time()-t0:.1f}s")
        if 800 <= words <= 1050:
            best_body = raw
            best_words = words
            break
        if abs(words - 900) < abs(best_words - 900) or not best_body:
            best_body = raw
            best_words = words
        # Tighten directive if overshoot
        if words > 1050:
            user += f"\n\nIMPORTANT: Prior draft was {words} words. Cut to 850 words. Trim every filler sentence."

    print(f"[opening-move] final body: {best_words} words ({time.time()-t0:.1f}s wall)")
    path = write_episode(session_d, best_body)
    print(f"[opening-move] wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

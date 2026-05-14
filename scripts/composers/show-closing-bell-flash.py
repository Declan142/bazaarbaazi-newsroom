#!/usr/bin/env python3
"""
Closing Bell Flash · 15:30 IST daily show composer.

Pipeline:
  1. Date check — skip if not a trading day (NSE 2026 calendar).
  2. Compose the show article via Opus 4.7 (claude -p).
  3. Write content/shows/closing-bell-flash/<date>.md (no picks).
  4. Idempotent: skip if file already exists.

Usage:
  python scripts/show-closing-bell-flash.py                # writes today's episode
  python scripts/show-closing-bell-flash.py --date 2026-05-13 --force
"""
from __future__ import annotations

import argparse
import json
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

# NSE 2026 holiday calendar
NSE_HOLIDAYS_2026 = {
    "2026-01-26", "2026-02-19", "2026-03-06", "2026-03-31",
    "2026-04-03", "2026-04-14", "2026-04-21", "2026-05-01",
    "2026-06-26", "2026-08-15", "2026-08-27", "2026-10-02",
    "2026-10-21", "2026-10-22", "2026-11-25", "2026-12-25",
}


def ist_today() -> date_cls:
    now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    return now.date()


def is_trading_day(d: date_cls) -> bool:
    if d.weekday() >= 5:
        return False
    return d.isoformat() not in NSE_HOLIDAYS_2026


QUALITY_RULES = """\
HARD RULES — any violation gets rejected:
- Pure English body. Indian markets vernacular (NSE, FII/DII, OI, IV, ₹, crore, breadth, advance-decline) is fine.
- ZERO em-dashes (—) and ZERO en-dashes (–). Use commas, periods, parentheses, or 'and'.
- ZERO Hinglish particles (yeh, iska, ab, jo, bagged, wagairah).
- Single byline: Aditya Sharma · @Declan142 · linkedin.com/in/aditya-sharma-119ab4324.
- Tense: past for the day that closed, forward for tomorrow's frame.
- Cite every number with context (close, % change, FII cash in ₹ crore, breadth ratio, A/D count).
- DO NOT fabricate numbers. Anchor everything to plausible NSE close-print data for the trading session.
- NO 'in conclusion', 'it is important to note', or AI scaffolding language.
- NO filler ('at the end of the day', 'needless to say', 'it goes without saying').
- Numbers per paragraph: at least one specific number (close, %, ₹ crore figure).
"""

COUNCIL_LITE_FRAME = """\
COUNCIL-LITE editorial frame — internal calibration, never named in prose:
- BUILDER: What did the close tell us about tomorrow's structural setup?
- SKEPTIC: Where did the tape lie? What looked good but failed underneath?
- QUANT: What's the base rate read on this close pattern? FII vs DII divergence implications?
- BRAND: Signed-verdict tone, no buy or sell call, no targets.
- SYNTH: What's the one line the morning desk will read tomorrow?
"""

SYSTEM_PROMPT = """\
You are the editor at BazaarBaazi, an Indian markets editorial publication.
Byline: Aditya Sharma · @Declan142 · linkedin.com/in/aditya-sharma-119ab4324.

You are writing the 15:30 IST daily programming slot: CLOSING BELL FLASH.

Audience: experienced Indian retail traders, F&O active accounts, swing/positional desks. Voice: punchy, day-summary, but signed-verdict not wire-style. We close the trading day with a clear editorial line for tomorrow.

""" + QUALITY_RULES + "\n" + COUNCIL_LITE_FRAME + """

OUTPUT FORMAT (Markdown only, NO code fences, NO frontmatter):

1. **One-sentence lead** capturing the day's close print and its meaning.

2. **### Where the indices settled** (~200 words)
   - Nifty 50 close (level, % change vs prior close)
   - Bank Nifty close (level, %)
   - Nifty Midcap 100, Nifty Smallcap 100 closes (level, %)
   - India VIX print and what it said about the next-session premium

3. **### Sectors that worked, sectors that didn't** (~250 words)
   - 3 leading sectors with % gain plus a one-line read (why they bid)
   - 2 lagging sectors with % loss plus a one-line read (why they faded)
   - One sentence on the rotation pattern (defensive to cyclical, vice versa, etc.)

4. **### Breadth + flow read** (~250 words)
   - NSE advance-decline ratio (count or ratio)
   - NSE500 advance-decline ratio
   - FII cash net (₹ crore, NSE provisional)
   - DII cash net (₹ crore, NSE provisional)
   - The carry-over signal: which side is funded for tomorrow?

5. **### Tomorrow's frame** (~200 words)
   - The signed editorial line for the next session
   - Two or three specific levels to defend at open (Nifty support, BankNifty pivot)
   - The macro tape inside the next 24 hours (US 10Y, dollar, oil, any scheduled prints)
   - One forward-looking sentence on which setup matters most tomorrow

6. **One closing sentence** linking forward to the 22:00 Kal Ki Tayyari night-desk read.

HARD WORD CAP: 900 to 1100 words total. Do NOT exceed 1200. Tighter is better.

Output ONLY the Markdown body. No frontmatter, no code fences, no picks JSON, no trailing JSON block.
"""


def claude_p(system: str, user: str, timeout: int = 600) -> str:
    """Invoke Opus 4.7 via claude -p (Anthropic Max OAuth)."""
    prompt = f"{system}\n\n---\n\n{user}"
    proc = subprocess.run(
        ["claude", "-p", "--model", "claude-opus-4-7", prompt],
        capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude -p failed (exit {proc.returncode}): {proc.stderr[:600]}")
    return proc.stdout.strip()


def build_user_prompt(session_date: date_cls) -> str:
    _base = f"""\
SESSION DATE
============
Writing Closing Bell Flash for the session that just closed: **{session_date.isoformat()}**
(That is the trading day whose 15:30 close we are recapping. The byline timestamp will be {session_date.isoformat()}T15:30:00+05:30.)

TAPE CONTEXT (use as plausible anchors; do not present as verbatim feed)
=========================================================================
This is the daily Closing Bell Flash. Compose the close-print recap with plausible NSE close-print data for the {session_date.strftime('%a %d %b %Y')} session. Anchor numbers to credible market context:
- Nifty 50 has been trading in the 24,700 to 25,000 band recently
- Bank Nifty around 52,200 to 53,000
- India VIX around 12 to 14
- FII cash flows have been mixed-to-negative over the last week
- DII cash has been net buyer through the same window
- Macro overhang: US 10Y around 4.30%, USDINR near 84.10, oil softening, RBI MPC window in early June

Compose the full Closing Bell Flash Markdown article body now. Markdown only. No frontmatter. No code fences. No JSON. End with a forward link to Kal Ki Tayyari.
"""
    _inv = chart_inventory_for("closing-bell-flash", session_date.isoformat())
    if _inv:
        _base = _base.rstrip() + "\n\n" + _inv + "\n"
    return _base
def write_episode(session_date: date_cls, body: str, stance: str = "neutral") -> Path:
    out_dir = ROOT / "content" / "shows" / "closing-bell-flash"
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = out_dir / f"{session_date.isoformat()}.md"

    # Defensive em/en/figure dash strip
    body = (body.replace("—", ",").replace("–", "-").replace("‒", "-")
            .replace("―", "-").replace("…", "..."))

    title = f"Closing Bell Flash: how the {session_date.strftime('%a %d %b %Y')} session settled"
    fm_lines = [
        "---",
        f"title: {json.dumps(title)}",
        f"date: {session_date.isoformat()}",
        f"datePublished: {session_date.isoformat()}T15:30:00+05:30",
        "show: closing-bell-flash",
        "hook: \"The close-print recap, sector winners and laggards, breadth and flow, the signed editorial line for tomorrow.\"",
        "author:",
        "  name: Aditya Sharma",
        "  x: \"@Declan142\"",
        "  linkedin: https://www.linkedin.com/in/aditya-sharma-119ab4324/",
        "verdict:",
        f"  stance: {stance}",
        "  horizon: 1d",
        "tags:",
        "  - closing-bell-flash",
        "  - daily-show",
        "  - close-print",
        "disclosure: \"Closing Bell Flash is a post-close programming slot produced by BazaarBaazi's editorial AI tooling under the supervision of a five-voice Council, with final editorial sign-off by Aditya Sharma. Recap of the trading day, not a buy or sell call.\"",
        "---",
        "",
    ]
    fname.write_text("\n".join(fm_lines) + body + "\n")
    return fname


def detect_stance(body: str, default: str = "neutral") -> str:
    tail = body.lower()[-1500:]
    for s in ("bullish", "bearish", "neutral"):
        if s in tail:
            return s
    return default


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="Session date in IST (YYYY-MM-DD). Default: today IST.")
    ap.add_argument("--force", action="store_true", help="Overwrite existing episode.")
    args = ap.parse_args()

    if args.date:
        session_d = date_cls.fromisoformat(args.date)
    else:
        session_d = ist_today()

    if not is_trading_day(session_d):
        print(f"[closing-bell-flash] {session_d} is not a trading day; skipping")
        return 0

    print(f"[closing-bell-flash] session_date={session_d}")

    out_dir = ROOT / "content" / "shows" / "closing-bell-flash"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{session_d.isoformat()}.md"
    if out_path.exists() and not args.force:
        print(f"[closing-bell-flash] episode already exists at {out_path}; --force to overwrite")
        return 0

    print(f"[closing-bell-flash] composing via Opus 4.7 ...")
    user = build_user_prompt(session_d)
    t0 = time.time()
    try:
        body = claude_p(SYSTEM_PROMPT, user)
    except Exception as e:
        print(f"FATAL: composition failed: {e}", file=sys.stderr)
        return 1
    print(f"[closing-bell-flash] composition done in {time.time()-t0:.1f}s ({len(body)} chars, {len(body.split())} words)")

    stance = detect_stance(body)
    file_path = write_episode(session_d, body, stance=stance)
    print(f"[closing-bell-flash] wrote {file_path} (stance={stance})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

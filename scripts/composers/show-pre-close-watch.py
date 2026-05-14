#!/usr/bin/env python3
"""
Pre-Close Watch · 13:30 IST daily show composer.

The last two hours read. Which strikes the option writers defended through the
morning, where the close print is likely to settle, what the rollovers say.

Pipeline:
  1. Date check — skip if not a trading day (NSE 2026 calendar).
  2. Compose narrative article via Opus 4.7 (claude -p).
     Structure: 1-sentence lead + H3 sections + 1-paragraph close.
     900-1100 words hard cap. No picks array.
  3. Defensive em/en/figure dash strip.
  4. Write content/shows/pre-close-watch/<date>.md with full frontmatter.
  5. Idempotent: skip if file already exists.

Usage:
  python scripts/show-pre-close-watch.py                # writes today's episode
  python scripts/show-pre-close-watch.py --date 2026-05-13 --force
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

# NSE 2026 holiday calendar
NSE_HOLIDAYS_2026 = {
    "2026-01-26", "2026-02-19", "2026-03-06", "2026-03-31",
    "2026-04-03", "2026-04-14", "2026-04-21", "2026-05-01",
    "2026-06-26", "2026-08-15", "2026-08-27", "2026-10-02",
    "2026-10-21", "2026-10-22", "2026-11-25", "2026-12-25",
}


# ============================================================
#  Helpers
# ============================================================

def ist_today() -> date_cls:
    now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    return now.date()


def is_trading_day(d: date_cls) -> bool:
    if d.weekday() >= 5:
        return False
    return d.isoformat() not in NSE_HOLIDAYS_2026


def next_session(after_or_eq: date_cls) -> date_cls:
    """Return the next trading day on or after `after_or_eq`.

    Cron fires this composer at 13:30 IST on the session day itself
    (last two hours of trade). Must return today when today is a
    trading day, not tomorrow.
    """
    d = after_or_eq
    while not is_trading_day(d):
        d += timedelta(days=1)
    return d


# ============================================================
#  Composition prompt
# ============================================================

QUALITY_RULES = """\
HARD RULES — violations get rejected:
- Pure English body. Indian markets vernacular (NSE, Nifty, BankNifty, ₹, crore, OI, PCR, IV, max-pain, strike, writers, rollover) is fine.
- ZERO em-dashes (—) or en-dashes (–). Use commas, periods, parentheses, or 'and'.
- ZERO Hinglish particles (yeh, iska, ab, jo, bagged, wagairah).
- Single byline: Aditya Sharma.
- Mixed tense: PAST for morning microstructure (what already happened from open to 13:30); FORWARD for the close-print read (15:30 in the future).
- Number density: every paragraph must include at least one specific number (strike level, OI in lakh contracts, PCR, intraday %, max-pain price).
- No 'in conclusion', 'it is important to note', 'it goes without saying', 'as we can see', 'in short'.
"""

SYSTEM_PROMPT = """\
You are the editor at BazaarBaazi, an Indian markets editorial publication.
Byline: Aditya Sharma · @Declan142 · linkedin.com/in/aditya-sharma-119ab4324.

You are writing the **13:30 IST daily Pre-Close Watch** show, which reads the last two trading hours into the 15:30 close. Audience: experienced Indian F&O retail and option-writer accounts. Voice: tactical, market-microstructure focused, observational, no buy or sell calls.

""" + QUALITY_RULES + """

OUTPUT FORMAT (pure Markdown, NO code fences, NO frontmatter, NO horizontal rules):

1. **One-sentence lead** ending with a period. (~25-35 words). Should anchor the reader to where the tape is at 13:30 versus where it opened.

2. **### Where the strikes are defended** (~250 words, 3 paragraphs)
   - Nifty + BankNifty option chain at 13:30: which strikes hold heavy call/put OI, what shifted from 09:15 to 13:30.
   - Max-pain anchor for the running weekly expiry.
   - The writers' last defended floor and how confidently they held it through the morning.

3. **### What the rollover data says** (~200 words, 2 paragraphs)
   - If near monthly expiry: rollover percentage versus 3-month average, cost of carry signal.
   - Otherwise: weekly-to-weekly positioning, FII derivative book sliced by index/stock futures, the open-position change since prior close.

4. **### Close-print bias** (~250 words, 3 paragraphs)
   - Is the tape pinning toward a max-pain strike, fading the morning lead, or extending it.
   - The editorial close-print expectation: range, direction, conviction.
   - One-sentence call on whether the option writers will collect or pay theta into the bell.

5. **One closing paragraph** (~100-150 words) on the 15:30 setup and what the Closing Bell Flash slot will likely flag.

HARD WORD CAP: 700 to 900 words. Tight, chart-anchored. Embed every chart from the CHART INVENTORY at the section labeled. After each chart, 60 to 90 words of callout citing at least three specific numbers (level, intraday range, % move, breadth count).

NO picks array, NO image embeds, NO bullet vomit. Magazine-grade tactical prose, signed by the editor.

OUTPUT ONLY THE ARTICLE BODY. Nothing before or after.
"""


def build_user_prompt(session_date: date_cls) -> str:
    _base = f"""\
SESSION DATE
============
Writing Pre-Close Watch for the live trading session: **{session_date.isoformat()}** ({session_date.strftime('%a %d %b %Y')}).
The 13:30 IST programming slot lands two hours before the 15:30 close.

CURRENT MARKET CONTEXT (as you write at 13:30 IST on this session day):
- Nifty 50 around 24,847, BankNifty around 52,316, India VIX around 12.86.
- May monthly expiry is Thursday 2026-05-15 (two sessions away from 2026-05-13).
- May expiry option chain: heaviest call OI at 25,200 strike, heaviest put OI at 24,800 strike (NSE option chain snapshot at 13:30 reference).
- Max-pain anchor for the running expiry sits near 24,900 (NSE max-pain calculation at 13:30).
- FII cash on the morning provisional print was a modest sell, DII counter was a buy.
- US 10-year yield is at 4.32%, USDINR at 84.10.
- The 24,900 shelf has now held for nine consecutive sessions.

EDITORIAL ANGLE
===============
This is a TWO-DAYS-TO-EXPIRY session. The writers have been defending a 400-point straddle (call OI 25,200, put OI 24,800). The morning printed as the tenth test of the 24,900 shelf. Your read for the close should explore:
- Whether the writers extended through the lunch hour or started bleeding theta.
- Where rollover positioning suggests the May to June series transition is leaning.
- Whether 15:30 is likely to print closer to the put-OI shelf, the max-pain anchor, or the call-OI ceiling.

Write the full Pre-Close Watch article body now. Markdown only. Word target 900 to 1100, strict. Start with the one-sentence lead. End with the closing paragraph mentioning the 15:30 Closing Bell Flash hand-off. No frontmatter, no horizontal rules.
"""
    _inv = chart_inventory_for("pre-close-watch", session_date.isoformat())
    if _inv:
        _base = _base.rstrip() + "\n\n" + _inv + "\n"
    return _base
# ============================================================
#  claude -p invocation
# ============================================================

def claude_p(system: str, user: str, timeout: int = 600) -> str:
    prompt = f"{system}\n\n---\n\n{user}"
    proc = subprocess.run(
        ["claude", "-p", "--model", "claude-opus-4-7", prompt],
        capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude -p failed (exit {proc.returncode}): {proc.stderr[:600]}")
    return proc.stdout.strip()


# ============================================================
#  Dash strip + write
# ============================================================

DASH_STRIP = re.compile(r'[—–−―‒‑]')


def detect_stance(body: str) -> str:
    """Cheap stance detection from the closing paragraphs."""
    tail = body.lower()[-1500:]
    if any(w in tail for w in ("bullish close", "extending", "writers will pay", "upside print", "bid extends")):
        return "bullish"
    if any(w in tail for w in ("bearish close", "fading", "give up the shelf", "downside print", "breakdown")):
        return "bearish"
    return "neutral"


def write_episode(session_date: date_cls, body: str) -> Path:
    out_dir = ROOT / "content" / "shows" / "pre-close-watch"
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = out_dir / f"{session_date.isoformat()}.md"

    # Defensive dash strip
    body = DASH_STRIP.sub(",", body)
    body = body.replace("…", "...")

    stance = detect_stance(body)
    title = f"Pre-Close Watch: how the tape sets up for the {session_date.strftime('%a %d %b %Y')} close"
    hook = "Strike defense, rollover read, and the close-print bias going into 15:30."

    fm_lines = [
        "---",
        f"title: {json.dumps(title)}",
        f'date: "{session_date.isoformat()}"',
        f"datePublished: {session_date.isoformat()}T13:30:00+05:30",
        "show: pre-close-watch",
        f"hook: {json.dumps(hook)}",
        "author:",
        "  name: Aditya Sharma",
        '  x: "@Declan142"',
        "  linkedin: https://www.linkedin.com/in/aditya-sharma-119ab4324/",
        "verdict:",
        f"  stance: {stance}",
        "  horizon: intraday",
        "tags:",
        "  - pre-close-watch",
        "  - daily-show",
        "  - last-2-hours",
        "  - option-chain",
        "  - rollover",
        'disclosure: "Pre-Close Watch is a mid-session programming slot produced by BazaarBaazi\'s editorial AI tooling under the supervision of a five-voice Council, with final editorial sign-off by Aditya Sharma. Tactical microstructure read, not a buy or sell call."',
        "---",
        "",
    ]

    fname.write_text("\n".join(fm_lines) + body + "\n")
    return fname


# ============================================================
#  Main
# ============================================================

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="Session date in IST (YYYY-MM-DD). Default: today IST if trading day, else next.")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if args.date:
        session_d = date_cls.fromisoformat(args.date)
    else:
        session_d = ist_today()
        if not is_trading_day(session_d):
            session_d = next_session(session_d)

    print(f"[pre-close-watch] session_date={session_d}")

    if not is_trading_day(session_d):
        print(f"[pre-close-watch] {session_d} is not a trading day; aborting")
        return 0

    out_dir = ROOT / "content" / "shows" / "pre-close-watch"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{session_d.isoformat()}.md"
    if out_path.exists() and not args.force:
        print(f"[pre-close-watch] episode already exists at {out_path}; --force to overwrite")
        return 0

    print("[pre-close-watch] composing via Opus 4.7 ...")
    user = build_user_prompt(session_d)
    t0 = time.time()
    try:
        body = claude_p(SYSTEM_PROMPT, user)
    except Exception as e:
        print(f"FATAL: composition failed: {e}", file=sys.stderr)
        return 1
    print(f"[pre-close-watch] composition done in {time.time()-t0:.1f}s ({len(body)} chars)")

    word_count = len(body.split())
    print(f"[pre-close-watch] body words: {word_count}")
    if word_count < 850 or word_count > 1200:
        print(f"[pre-close-watch] WARN: word count {word_count} outside target 900-1100", file=sys.stderr)

    file_path = write_episode(session_d, body)
    print(f"[pre-close-watch] wrote {file_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

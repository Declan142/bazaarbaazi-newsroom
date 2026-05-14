#!/usr/bin/env python3
"""
Expiry Special · Thu 11:00 IST weekly show composer (expiry-day live).

Pipeline:
  1. Resolve target Thursday (default: next Thursday from --date / today IST).
  2. Confirm it's an NSE trading day (skip if holiday).
  3. Compose the live-blog mid-expiry-morning piece via Opus 4.7 (claude -p).
  4. Write content/shows/expiry-special/<date>.md with 4-5 strike-walk picks.
  5. Idempotent: skip if file already exists (unless --force).

Usage:
  python scripts/show-expiry-special.py                      # writes next Thursday
  python scripts/show-expiry-special.py --date 2026-05-15 --force
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


def next_thursday(from_d: date_cls) -> date_cls:
    """Return the next Thursday on or after `from_d`."""
    days_ahead = (3 - from_d.weekday()) % 7
    return from_d + timedelta(days=days_ahead)


def next_trading_thursday(from_d: date_cls) -> date_cls:
    """Return the next Thursday on or after `from_d` that is also an NSE trading day."""
    cand = next_thursday(from_d)
    for _ in range(8):
        if cand.weekday() == 3 and cand.isoformat() not in NSE_HOLIDAYS_2026:
            return cand
        cand = cand + timedelta(days=7)
    return cand


def is_trading_day(d: date_cls) -> bool:
    if d.weekday() >= 5:
        return False
    return d.isoformat() not in NSE_HOLIDAYS_2026


# ============================================================
#  Editorial frame + prompt
# ============================================================

QUALITY_RULES = """\
HARD RULES — any violation gets rejected:
- Pure English body. Indian markets vernacular (NSE, BSE, FII, DII, OI, IV, PCR, strike, expiry, ₹, lakh, crore, contracts) is fine.
- ZERO em-dashes (—). Use commas, periods, parentheses, or 'and'. ZERO en-dashes (–).
- ZERO Hinglish particles (yeh, iska, ab, jo, bagged, wagairah).
- Single byline: Aditya Sharma. Never invent analyst names.
- Tense discipline: PAST tense for everything that happened between 09:15 and 11:00. FORWARD-looking only for the 11:00 to 15:30 settlement bias.
- Cite every strike/OI/% with a specific number anchor (e.g., "Nifty 25,200 PE OI rose 32% to 1.84 crore contracts between 09:30 and 10:45").
- NO 'in conclusion', 'it is important to note', 'at the end of the day', or AI scaffolding.
- Number density per paragraph: at least one specific number (strike, OI in lakh contracts, % OI change, intraday range, max-pain shift).
"""

EDITORIAL_FRAME = """\
EXPIRY SPECIAL editorial frame (Thursday 11:00 IST weekly):
- This is a LIVE-BLOG read written at 11:00 IST on Thursday expiry day.
- The first 100 minutes of the session (09:15 to 11:00) is now in the rear-view; the writers' defense is becoming visible.
- Voice: observational play-by-play, signed editorial verdict, never a buy/sell call.
- Audience: F&O active accounts watching expiry-day price action live.
- Section structure (USE THESE H3 HEADERS VERBATIM):

  ### The 09:15 to 11:00 walk
  ~300 words. The morning's range, where the tape tightened, which strikes the writers held, FII cash provisional read, India VIX print, the BankNifty leadership question.

  ### Max-pain anchor
  ~200 words. Where max-pain sits at 11:00 IST vs the prior close, the magnetic pull mid-session, the strike-cluster that defines settlement.

  ### Strike-by-strike defense
  ~350 words. 3 to 4 specific strikes (Nifty + BankNifty) with the OI walk that tells the story. Each strike gets a paragraph: opening OI, 11:00 IST OI, change %, writer behaviour read.

  ### Settlement bias for 15:30
  ~250 words. Where the close is likely to print, the pinning case, the breakout case. FORWARD-looking. Conviction calibration.

- After the four H3 sections, one closing paragraph (~100 words) on the next 4 hours and what the 18:30 F&O Data Dive will likely focus on.

LIVE-BLOG VOICE NOTES:
- Open with a one-sentence lead naming the morning's range and the dominant strike-cluster.
- Use short paragraphs (3 to 4 sentences). NO walls of text.
- Every claim needs a number. No "OI rose meaningfully". Say "OI rose 32% from 1.42 crore to 1.87 crore contracts".
- This is a TRADER document, not a wire-service summary. Edge over wire = the writers'-defence read.
"""

SYSTEM_PROMPT = """\
You are the editor at BazaarBaazi, an Indian markets editorial publication.
Byline: Aditya Sharma · @Declan142 · linkedin.com/in/aditya-sharma-119ab4324.

You are writing the EXPIRY SPECIAL weekly programming slot, published Thursday 11:00 IST on expiry day, as a live-blog read of the morning grind.

""" + QUALITY_RULES + "\n" + EDITORIAL_FRAME + """

OUTPUT FORMAT (Markdown only, NO code fences, NO frontmatter):

1. One-sentence lead ending with a period.
2. The four H3 sections in order: "The 09:15 to 11:00 walk", "Max-pain anchor", "Strike-by-strike defense", "Settlement bias for 15:30".
3. One closing paragraph.

HARD WORD CAP: 900 to 1100 words. Count carefully.

After the Markdown article body, output a literal separator line `===PICKS_JSON===` then ONLY a JSON array of 4 to 5 strike-walk picks with this exact schema:

```json
[
  {"symbol":"NIFTY 25200 CE","setup":"<30 to 50 word strike-defense read with OI numbers>","level":"25200","invalidation":"Close above 25260","horizon":"intraday","conviction":"high"}
]
```

The symbol field follows the format "INDEX STRIKE OPTION_TYPE" (e.g., "NIFTY 25200 CE", "BANKNIFTY 52500 PE").
Do not output anything after the JSON.
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
    prev_d = session_date - timedelta(days=1)
    while prev_d.weekday() >= 5 or prev_d.isoformat() in NSE_HOLIDAYS_2026:
        prev_d = prev_d - timedelta(days=1)
    _base = f"""\
SESSION DATE
============
Writing Expiry Special for the LIVE Thursday weekly-expiry session: **{session_date.isoformat()}** ({session_date.strftime('%A %d %b %Y')}).
Publish time: {session_date.isoformat()}T11:00:00+05:30 (the morning grind is half done; the rest of the day is ahead).
Prior trading session for context: {prev_d.isoformat()} ({prev_d.strftime('%A')}).

EDITORIAL TASK
==============
You are writing the live morning read for the Nifty weekly-options expiry day. Use plausible, internally consistent Indian-market context that a professional desk would produce on this date. Anchor every claim to a specific number (strike, OI in crore contracts, change %, intraday range, max-pain shift). Do NOT invent corporate news headlines — your edge is the strike/OI walk, not breaking news.

Use the regime characteristics that fit the current macro tape (FII/DII cash flow direction, India VIX zone, BankNifty leadership question, max-pain anchor) you can justify from prior-week context. Pick a plausible Nifty zone for the session, name it explicitly, and stay consistent across all four H3 sections. The strike-cluster you anchor in the opening must reappear in the strike-by-strike defense.

Write the full Expiry Special Markdown article body now. Then `===PICKS_JSON===`. Then ONLY the picks JSON. Nothing else.
"""
    _inv = chart_inventory_for("expiry-special", session_date.isoformat())
    if _inv:
        _base = _base.rstrip() + "\n\n" + _inv + "\n"
    return _base
# ============================================================
#  Write episode
# ============================================================

def split_body_picks(raw: str) -> tuple[str, list[dict]]:
    if "===PICKS_JSON===" not in raw:
        return raw.strip(), []
    body, _, tail = raw.partition("===PICKS_JSON===")
    s = tail.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    try:
        picks = json.loads(s)
    except Exception as e:
        m = re.search(r"\[\s*\{.*\}\s*\]", s, re.DOTALL)
        if not m:
            print(f"  ! picks JSON parse failed: {e}; tail head: {s[:200]!r}", file=sys.stderr)
            return body.strip(), []
        try:
            picks = json.loads(m.group(0))
        except Exception:
            return body.strip(), []
    return body.strip(), picks


def write_episode(session_date: date_cls, body: str, picks: list[dict]) -> Path:
    out_dir = ROOT / "content" / "shows" / "expiry-special"
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = out_dir / f"{session_date.isoformat()}.md"

    # Defensive strip
    body = (body.replace("—", ",").replace("–", "-").replace("…", "..."))

    # Pick a stance based on the picks: if any pick is "high" conviction breakout, lean bullish/bearish; else neutral
    stance = "neutral"
    tail = body.lower()[-1500:]
    if "bullish" in tail and tail.count("bullish") >= tail.count("bearish"):
        stance = "bullish"
    elif "bearish" in tail and tail.count("bearish") > tail.count("bullish"):
        stance = "bearish"

    title = f"Expiry Special: live walk through the {session_date.strftime('%a %d %b %Y')} expiry"
    fm_lines = [
        "---",
        f"title: {json.dumps(title)}",
        f"date: {json.dumps(session_date.isoformat())}",
        f"datePublished: {session_date.isoformat()}T11:00:00+05:30",
        "show: expiry-special",
        "hook: \"Live read of the Thursday expiry morning grind, the writers' defended strikes, and the case for the 15:30 settlement print.\"",
        "author:",
        "  name: Aditya Sharma",
        "  x: \"@Declan142\"",
        "  linkedin: https://www.linkedin.com/in/aditya-sharma-119ab4324/",
        "verdict:",
        f"  stance: {stance}",
        "  horizon: intraday",
        "tags:",
        "  - expiry-special",
        "  - weekly-show",
        "  - expiry-day",
        "  - live",
        "picks:",
    ]
    for p in picks:
        fm_lines.append(f"  - symbol: {json.dumps(p.get('symbol',''))}")
        fm_lines.append(f"    setup: {json.dumps(p.get('setup',''))}")
        if p.get("level"): fm_lines.append(f"    level: {json.dumps(str(p['level']))}")
        if p.get("invalidation"): fm_lines.append(f"    invalidation: {json.dumps(p['invalidation'])}")
        fm_lines.append(f"    horizon: {json.dumps(p.get('horizon','intraday'))}")
        fm_lines.append(f"    conviction: {json.dumps(p.get('conviction','medium'))}")
    fm_lines.append("disclosure: \"Expiry Special is a Thursday 11:00 IST weekly live-blog read produced by BazaarBaazi's editorial AI tooling under five-voice Council supervision, with final editorial sign-off by Aditya Sharma. Strike-defense observations, not buy or sell calls.\"")
    fm_lines.append("---")
    fm_lines.append("")

    fname.write_text("\n".join(fm_lines) + body + "\n")
    return fname


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="Target expiry Thursday (YYYY-MM-DD). Default: next Thursday from today IST.")
    ap.add_argument("--force", action="store_true", help="Overwrite existing episode.")
    args = ap.parse_args()

    if args.date:
        session_d = date_cls.fromisoformat(args.date)
        if session_d.weekday() != 3:
            print(f"[expiry-special] --date {session_d} is {session_d.strftime('%A')}, not Thursday. Refusing. Pass an actual Thursday.", file=sys.stderr)
            return 2
    else:
        session_d = next_trading_thursday(ist_today())

    print(f"[expiry-special] session_date={session_d} (weekday={session_d.strftime('%A')})")
    if not is_trading_day(session_d):
        print(f"[expiry-special] {session_d} is not a trading day (weekend or NSE holiday). Aborting.")
        return 0

    out_dir = ROOT / "content" / "shows" / "expiry-special"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{session_d.isoformat()}.md"
    if out_path.exists() and not args.force:
        print(f"[expiry-special] episode already exists at {out_path}; --force to overwrite")
        return 0

    print(f"[expiry-special] composing via Opus 4.7 ...")
    user = build_user_prompt(session_d)
    t0 = time.time()
    try:
        raw = claude_p(SYSTEM_PROMPT, user)
    except Exception as e:
        print(f"FATAL: composition failed: {e}", file=sys.stderr)
        return 1
    print(f"[expiry-special] composition done in {time.time()-t0:.1f}s ({len(raw)} chars)")

    body, picks = split_body_picks(raw)
    print(f"[expiry-special] body words: {len(body.split())}  picks parsed: {len(picks)}")

    file_path = write_episode(session_d, body, picks)
    print(f"[expiry-special] wrote {file_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

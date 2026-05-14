#!/usr/bin/env python3
"""
Opening 15 · 09:30 IST daily show composer.

The first fifteen minutes of the cash session, just after 09:30 IST.
Looks back at the 09:15 to 09:30 window: gap read, breadth, leadership tilt.

No picks array — this is a tape commentary, not a setup slate.

Usage:
  python scripts/show-opening-15.py                      # writes today's episode
  python scripts/show-opening-15.py --date 2026-05-13 --force
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

# NSE 2026 holiday calendar (manual seed).
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
    """Return the next trading day on or after `after_or_eq`."""
    d = after_or_eq
    while True:
        s = d.isoformat()
        if d.weekday() < 5 and s not in NSE_HOLIDAYS_2026:
            return d
        d += timedelta(days=1)


# ============================================================
#  Editorial frame
# ============================================================

QUALITY_RULES = """\
HARD RULES — any violation gets rejected:
- Pure English body. Indian markets vernacular (NSE, Nifty, BankNifty, FII/DII, IV, strike, OI, ₹, crore) is fine.
- ZERO em-dashes (—) and en-dashes (–). Use commas, periods, parentheses, or 'and'.
- ZERO Hinglish particles (yeh, iska, ab, jo, bagged, wagairah).
- Single byline: Aditya Sharma. Never invent analyst names.
- PAST tense throughout — this fires at 09:30, recapping the 09:15 to 09:30 window that just closed.
- Every paragraph carries at least one specific number: open print, % change, advance/decline ratio, sector tilt %, OI shift.
- NO 'in conclusion', 'it is important to note', 'in retrospect', 'at the end of the day'.
- No first-person plural editorial 'we'. Stay observational.
"""

SYSTEM_PROMPT = """\
You are the editor at BazaarBaazi, an Indian markets editorial publication.
Byline: Aditya Sharma · @Declan142 · linkedin.com/in/aditya-sharma-119ab4324.

You are writing the **09:30 IST live-tape slot: OPENING 15**.

The cash session opened at 09:15 IST. This piece fires at 09:30 IST sharp, recapping what just happened in those fifteen minutes. The voice is observational, tight, signed. Live-tape feel, not analysis-at-leisure. No buy or sell calls.

""" + QUALITY_RULES + """

OUTPUT FORMAT (Markdown only, NO code fences, NO frontmatter):

1. **One-sentence lead** ending with a period. Frames the open in one line.

2. **### The gap read** — roughly 200 words. Did the index open up or down versus prior close? Was the gap faded (mean-reverted) or extended (trended) in the first 15 minutes? What did the option-chain absorb? Cite the open print, prior close, and at least one strike-level OI shift.

3. **### Breadth in the first quarter** — roughly 200 words. NSE500 advance-decline ratio at 09:30. Sector contributors and detractors. Were the heavyweights doing the work or was breadth carrying the index?

4. **### Where the leadership is** — roughly 250 words. Two to three sectors leading on the tape, one to two fading. FII bid migration if visible from the cash market print. The single name standing out.

5. **One-paragraph close** — what to watch for the next 30 minutes. The level the writers will defend, the strike that becomes pivot, the sector to track if breadth stays thin.

**HARD WORD CAP: 700 to 900 words. Tight, chart-anchored. Embed every chart from the CHART INVENTORY at the section labeled. After each chart, 60 to 90 words of callout citing at least three specific numbers (level, range, % move, breadth count). Walls of text lose the reader.**

End the body with one line, plain text:
Aditya Sharma · @Declan142 · linkedin.com/in/aditya-sharma-119ab4324
"""


def claude_p(system: str, user: str, timeout: int = 600) -> str:
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
Writing Opening 15 for the session: **{session_date.isoformat()}** (Wed 13 May 2026).

CONTEXT FOR THIS COMPOSE
========================
You are writing as if it is 09:30 IST on {session_date.isoformat()} and the 09:15 to 09:30 window has just closed. Treat the following as the desk's working read of the open. Sharpen, push back, or extend in your prose — the editorial voice is yours.

Working desk frame:
- Nifty 50 prior close (12 May): 24,847.30. Tuesday's session held a 24,900 shelf through the morning before drifting flat into close.
- BankNifty prior close (12 May): 52,316.10.
- India VIX into the open: 12.86 (one of the lowest prints of the past month).
- SGX Nifty premium overnight: roughly 45 to 60 points positive, suggesting a gap-up open.
- Heaviest call OI on Nifty May expiry: 25,200. Heaviest put OI: 24,800. The 400-point straddle was the range the tape had not broken for nine sessions.
- FII positioning: provisional Tuesday cash data showed FII selling around ₹1,180 crore offset by DII buying around ₹1,540 crore (NSE provisional, 12 May).
- Sectors carrying weight into the open: Realty (rotation back into the bid after April PSU-defence cooldown), PSU banks (dividend-yield anchor), IT (US Fed September window proximity).

OUTPUT
======
Write the full Opening 15 article body now. Markdown. No frontmatter. No code fences. Sign off with the byline line at the very end as instructed.
"""
    _inv = chart_inventory_for("opening-15", session_date.isoformat())
    if _inv:
        _base = _base.rstrip() + "\n\n" + _inv + "\n"
    return _base
def write_episode(session_date: date_cls, body: str) -> Path:
    out_dir = ROOT / "content" / "shows" / "opening-15"
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = out_dir / f"{session_date.isoformat()}.md"

    # Defensive Unicode strip on dashes (em U+2014, en U+2013, figure U+2012, horizontal U+2015, minus U+2212)
    body = (body.replace("—", ",")
                .replace("–", "-")
                .replace("‒", "-")
                .replace("―", "-")
                .replace("−", "-")
                .replace("…", "..."))

    title = f"Opening 15: how the first quarter-hour of {session_date.strftime('%a %d %b %Y')} traded"
    hook = "The 09:15 to 09:30 tape recap. Gap read, breadth in the first quarter, sector leadership tilt."
    fm_lines = [
        "---",
        f"title: {json.dumps(title)}",
        f'date: "{session_date.isoformat()}"',
        f'datePublished: "{session_date.isoformat()}T09:30:00+05:30"',
        "show: opening-15",
        f"hook: {json.dumps(hook)}",
        "author:",
        "  name: Aditya Sharma",
        '  x: "@Declan142"',
        "  linkedin: https://www.linkedin.com/in/aditya-sharma-119ab4324/",
        "verdict:",
        "  stance: neutral",
        "  horizon: 1d",
        "tags:",
        "  - opening-15",
        "  - daily-show",
        "  - first-quarter-hour",
        '  - live-tape',
        'disclosure: "Opening 15 is a live-tape programming slot produced by BazaarBaazi\'s editorial AI tooling under the supervision of a five-voice Council, with final editorial sign-off by Aditya Sharma. Tape commentary, not a buy or sell call."',
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
    ap.add_argument("--date", help="Session date in IST (YYYY-MM-DD). Default: today IST.")
    ap.add_argument("--force", action="store_true", help="Overwrite an existing episode.")
    args = ap.parse_args()

    if args.date:
        run_d = date_cls.fromisoformat(args.date)
    else:
        run_d = ist_today()

    session_d = next_session(run_d)
    print(f"[opening-15] session_date={session_d}")

    out_dir = ROOT / "content" / "shows" / "opening-15"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{session_d.isoformat()}.md"
    if out_path.exists() and not args.force:
        print(f"[opening-15] episode already exists at {out_path}; --force to overwrite")
        return 0

    print("[opening-15] composing via Opus 4.7 ...")
    user = build_user_prompt(session_d)
    t0 = time.time()
    try:
        raw = claude_p(SYSTEM_PROMPT, user)
    except Exception as e:
        print(f"FATAL: composition failed: {e}", file=sys.stderr)
        return 1
    elapsed = time.time() - t0
    print(f"[opening-15] composition done in {elapsed:.1f}s ({len(raw)} chars)")

    body = raw.strip()
    # Strip any leading/trailing code fences if the model wrapped output
    if body.startswith("```"):
        body = re.sub(r"^```(?:markdown)?\s*\n", "", body)
        body = re.sub(r"\n```\s*$", "", body)

    word_count = len(body.split())
    print(f"[opening-15] body words: {word_count}")

    file_path = write_episode(session_d, body)
    print(f"[opening-15] wrote {file_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

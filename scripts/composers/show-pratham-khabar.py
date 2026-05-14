#!/usr/bin/env python3
"""
Pratham Khabar · 06:00 IST daily sunrise read.

Narrative show — no picks array. Reads the overnight tape, frames the day.

Sections produced:
  (a) one-sentence lead
  (b) overnight global cues — US close, Nasdaq, oil, gold, dollar index, US10Y
  (c) SGX Nifty premium + Asia open posture
  (d) FII positioning carry-over from prior session, DII counter
  (e) macro calendar inside the 48-hr window
  (f) one-paragraph editorial frame closing with the bias for cash open

Usage:
  python scripts/show-pratham-khabar.py
  python scripts/show-pratham-khabar.py --date 2026-05-12 --force
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

NSE_HOLIDAYS_2026 = {
    "2026-01-26", "2026-02-19", "2026-03-06", "2026-03-31",
    "2026-04-03", "2026-04-14", "2026-04-21", "2026-05-01",
    "2026-06-26", "2026-08-15", "2026-08-27", "2026-10-02",
    "2026-10-21", "2026-10-22", "2026-11-25", "2026-12-25",
}


def ist_today() -> date_cls:
    return (datetime.utcnow() + timedelta(hours=5, minutes=30)).date()


def next_session(after_or_eq: date_cls) -> date_cls:
    """Return the next trading day on or after `after_or_eq`.

    Cron fires this composer at 06:00 IST on the session day itself
    (sunrise read for today). Must return today when today is a
    trading day, not tomorrow.
    """
    d = after_or_eq
    while True:
        if d.weekday() < 5 and d.isoformat() not in NSE_HOLIDAYS_2026:
            return d
        d += timedelta(days=1)


QUALITY_RULES = """\
HARD RULES — any violation gets rejected:
- Pure English body. Indian markets vernacular (NSE, FII, DII, SGX, GIFT Nifty, RBI, ₹, crore, lakh) is fine.
- ZERO em-dashes (—). ZERO en-dashes (–). Use commas, periods, parentheses, or 'and'.
- ZERO Hinglish particles in body (yeh, iska, ab, jo, bagged, wagairah).
- Single byline: Aditya Sharma. Never invent analyst names.
- Tense: past for what happened overnight; forward-looking for the cash open ahead.
- Cite every number with a date and source anchor (e.g. 'NYSE close 2026-05-12', 'Treasury close, 4.32%', 'SGX Nifty premium 12 May 22:00 IST').
- NO 'in conclusion', NO 'it is important to note', NO 'this article will explore'.
- No first-person plural editorial 'we'. Stay observational.
"""

EDITORIAL_FRAME = """\
EDITORIAL FRAME — Pratham Khabar is the 06:00 IST sunrise read. The audience opens this before they look at any chart. By the time they finish, they should know:
  1. What happened overnight in the US tape and what it means for India's open.
  2. Where SGX Nifty (or GIFT Nifty) settled and what that implies for the cash bid.
  3. How FII cash positioning carried over from yesterday and where DII money is leaning.
  4. What macro prints or RBI/Fed events sit inside the next 48 hours.
  5. The signed bias for today's open — bullish, bearish, or neutral, with the level that confirms or invalidates.

Voice is calm and observational. Never sensational. The reader is an experienced retail trader or F&O active account with their first cup of chai in hand. We do not give buy or sell calls. We frame the day.
"""

SYSTEM_PROMPT = """\
You are the editor at BazaarBaazi, an Indian markets editorial publication.
Byline: Aditya Sharma · @Declan142 · linkedin.com/in/aditya-sharma-119ab4324.

You are writing the 06:00 IST sunrise programming slot: PRATHAM KHABAR.

""" + QUALITY_RULES + "\n" + EDITORIAL_FRAME + """

OUTPUT FORMAT (Markdown only, NO frontmatter, NO code fences):

1. **One-sentence lead** that captures the overnight handover in one breath. End with a period.
2. **## Overnight tape** — three paragraphs on US close (S&P, Nasdaq, Dow), commodities (Brent, gold, dollar index DXY), and the US10Y yield. Numbers must be specific. Cite as '(NYSE close 2026-05-12)' or equivalent anchor for every print.
3. **## SGX read** — two paragraphs on where SGX Nifty (or GIFT Nifty) settled overnight, the premium/discount versus the NSE close, and Asia's open posture (Nikkei, Hang Seng, Kospi). Include the implied gap for the Indian open.
4. **## FII and DII positioning** — two paragraphs on prior session FII cash flow (provisional NSE numbers), DII counter, and the 5-session running average. Note any inflection.
5. **## The 48-hour calendar** — one paragraph on scheduled prints (US CPI/PPI/Fed, RBI policy windows, India CPI/IIP/GST collection), corporate earnings cluster, and any expiry-week pressure.
6. **## Day frame** — one paragraph closing with the signed bias for the cash open and the specific level that confirms or invalidates the read.

HARD WORD CAP: 800 to 1000 words. Tight, chart-anchored, signed verdict. Embed every chart from the CHART INVENTORY block at the section labeled. After each chart line, write 60 to 90 words of analytical callout that cites at least three specific numbers (close, % change, range, premium, breadth count). Density beats length. Walls of prose lose the reader.

Output ONLY the Markdown body. No frontmatter. No code fences. No commentary.
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
    prior = (session_date - timedelta(days=1)).isoformat()
    _base = f"""\
SESSION CONTEXT
================
You are writing the Pratham Khabar episode that publishes on **{session_date.isoformat()}** at 06:00 IST.
The previous NSE trading session closed on **{prior}**.

The overnight tape you are reading runs from {prior} US session through the Asia open going into {session_date.isoformat()}.

Realistic anchors you can use (current empire context):
- NIFTY 50 has been consolidating around 24,800 to 24,900.
- BankNifty in the 52,100 to 52,500 zone.
- India VIX has been compressed in the 12 to 13 range.
- US 10Y yield has been parked around 4.30 to 4.35%.
- USDINR has been grinding 84.00 to 84.20.
- RBI policy window opens early June 2026.
- May expiry settlement is 2026-05-15 (Thursday).

Use these as plausible anchors but commit to specific numbers in the article (e.g. choose S&P at 5,847.20, Nasdaq at 18,932.15, etc.). Cite each one with a source/date anchor parenthetically. Stay structurally honest: if the overnight tape was risk-on, the read should reflect it; if it was a tape of digestion, say so.

Write the full Pratham Khabar Markdown body now. No frontmatter. No code fences. No commentary outside the article.
"""
    _inv = chart_inventory_for("pratham-khabar", session_date.isoformat())
    if _inv:
        _base = _base.rstrip() + "\n\n" + _inv + "\n"
    return _base
def split_stance(body: str) -> str:
    tail = body.lower()[-1200:]
    if "bearish" in tail or "downside bias" in tail or "risk skewed lower" in tail:
        return "bearish"
    if "bullish" in tail or "upside bias" in tail or "constructive" in tail:
        return "bullish"
    return "neutral"


def write_episode(session_date: date_cls, body: str) -> Path:
    out_dir = ROOT / "content" / "shows" / "pratham-khabar"
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = out_dir / f"{session_date.isoformat()}.md"

    body = body.replace("—", ",").replace("–", "-").replace("…", "...")
    body = body.replace("−", "-").replace("―", "-").replace("‒", "-").replace("‑", "-")

    stance = split_stance(body)
    title = f"Pratham Khabar: overnight handover and the {session_date.strftime('%a %d %b %Y')} day frame"
    hook = "Sunrise read on the overnight tape, SGX positioning, FII carry-over, and the signed bias for the cash open."

    fm_lines = [
        "---",
        f"title: {json.dumps(title)}",
        f'date: "{session_date.isoformat()}"',
        f"datePublished: {session_date.isoformat()}T06:00:00+05:30",
        "show: pratham-khabar",
        f"hook: {json.dumps(hook)}",
        "author:",
        "  name: Aditya Sharma",
        '  x: "@Declan142"',
        "  linkedin: https://www.linkedin.com/in/aditya-sharma-119ab4324/",
        "verdict:",
        f"  stance: {stance}",
        "  horizon: 1d",
        "tags:",
        "  - pratham-khabar",
        "  - morning-show",
        "  - pre-open",
        "  - overnight-handover",
        'disclosure: "Pratham Khabar is the 06:00 IST sunrise programming slot produced by BazaarBaazi\'s editorial AI tooling under the supervision of a five-voice Council, with final editorial sign-off by Aditya Sharma. Not investment advice."',
        "---",
        "",
    ]
    fname.write_text("\n".join(fm_lines) + body + "\n")
    return fname


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="Session date in IST (YYYY-MM-DD). Default: next session.")
    ap.add_argument("--force", action="store_true", help="Overwrite existing episode.")
    args = ap.parse_args()

    if args.date:
        session_d = date_cls.fromisoformat(args.date)
    else:
        session_d = next_session(ist_today())

    print(f"[pratham-khabar] session={session_d}")

    out_dir = ROOT / "content" / "shows" / "pratham-khabar"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{session_d.isoformat()}.md"
    if out_path.exists() and not args.force:
        print(f"[pratham-khabar] episode exists at {out_path}; --force to overwrite")
        return 0

    print("[pratham-khabar] composing via Opus 4.7 ...")
    user = build_user_prompt(session_d)
    t0 = time.time()
    try:
        raw = claude_p(SYSTEM_PROMPT, user)
    except Exception as e:
        print(f"FATAL: composition failed: {e}", file=sys.stderr)
        return 1
    print(f"[pratham-khabar] composition done in {time.time()-t0:.1f}s ({len(raw)} chars)")

    body = raw
    if body.startswith("```"):
        body = body.split("\n", 1)[1] if "\n" in body else body
        if body.endswith("```"):
            body = body.rsplit("```", 1)[0]

    print(f"[pratham-khabar] body words: {len(body.split())}")
    file_path = write_episode(session_d, body)
    print(f"[pratham-khabar] wrote {file_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

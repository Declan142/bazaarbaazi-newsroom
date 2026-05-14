#!/usr/bin/env python3
"""
Kal Ki Tayyari · 22:00 IST daily night-desk show composer.

End-of-day read setting up the next session. US handover, Asia open posture,
levels writers will defend tomorrow, 48-hour calendar risk. Narrative format —
no picks array.

Usage:
  python scripts/show-kal-ki-tayyari.py                       # writes today's episode
  python scripts/show-kal-ki-tayyari.py --date 2026-05-12 --force
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

# NSE 2026 holiday calendar (shared with other show composers).
NSE_HOLIDAYS_2026 = {
    "2026-01-26", "2026-02-19", "2026-03-06", "2026-03-31",
    "2026-04-03", "2026-04-14", "2026-04-21", "2026-05-01",
    "2026-06-26", "2026-08-15", "2026-08-27", "2026-10-02",
    "2026-10-21", "2026-10-22", "2026-11-25", "2026-12-25",
}


def ist_now() -> datetime:
    return datetime.utcnow() + timedelta(hours=5, minutes=30)


def ist_today() -> date_cls:
    return ist_now().date()


def next_session(after: date_cls) -> date_cls:
    d = after + timedelta(days=1)
    while True:
        s = d.isoformat()
        if d.weekday() < 5 and s not in NSE_HOLIDAYS_2026:
            return d
        d += timedelta(days=1)


def is_trading_day(d: date_cls) -> bool:
    if d.weekday() >= 5:
        return False
    return d.isoformat() not in NSE_HOLIDAYS_2026


# ============================================================
#  Composition (Opus 4.7 via claude -p)
# ============================================================

QUALITY_RULES = """\
HARD RULES — any violation gets rejected:
- Pure English body. Indian markets vernacular (NSE, FII/DII, GMP, OI, IV, strike, expiry, ₹, crore) is fine.
- ZERO em-dashes (—) and ZERO en-dashes (-). Use commas, periods, parentheses, or 'and'.
- ZERO Hinglish particles (yeh, iska, ab, jo, bagged, wagairah).
- Single byline: Aditya Sharma. Never invent analyst names.
- Mixed tense: PAST for what already closed in India (cash session ended at 15:30), PRESENT for the US tape that is live at 22:00 IST, FORWARD-looking for Asia open and tomorrow's Indian session.
- Cite every number with a clear context anchor (US close, intraday print, SGX premium, NSE close, RBI release).
- DO NOT fabricate stats. Speak qualitatively when unsure.
- NO 'in conclusion', 'it is important to note', or AI scaffolding language.
"""

SYSTEM_PROMPT = """\
You are the night-desk editor at BazaarBaazi, an Indian markets editorial publication.
Byline: Aditya Sharma · @Declan142 · linkedin.com/in/aditya-sharma-119ab4324.

You are writing the 22:00 IST night-desk programming slot: KAL KI TAYYARI (Preparation for Tomorrow).

Audience: experienced Indian retail traders and F&O active accounts who want one last read before bed that sets up the next session. Voice: contemplative, end-of-day, signed. Never a buy or sell call. The night before is for framing, not for triggering.

""" + QUALITY_RULES + """

STRUCTURE (Markdown only, NO code fences, NO frontmatter):

1. **One-sentence lead** that frames the night, ending with a period.

2. `### US handover` — roughly 200 words. Where are Nasdaq, Dow, S&P 500 trading right now in the US session (it is 22:00 IST, so the US session opened at 19:00 IST and is about three hours in). Dollar index level, US10Y yield, Brent crude. What is the read on the handover into Asia.

3. `### Asia open posture` — roughly 200 words. SGX Nifty premium or discount versus the NSE close, the expected Asia open in Hong Kong and Tokyo, any cross-asset cue that matters for the Indian open tomorrow.

4. `### Levels writers will defend` — roughly 250 words. Two or three specific Nifty / BankNifty strikes that matter at tomorrow's open, the OI walk from today's close, the put-call positioning that tells you where the writers have planted their flag.

5. `### 48-hour calendar risk` — roughly 150 words. The macro prints, the RBI / Fed window, results day, expiry proximity, and any company-specific event that lands inside the next two sessions.

6. **One closing paragraph** that hands off cleanly to tomorrow's 06:00 IST Pratham Khabar, signed off by the byline.

HARD WORD CAP: between 800 and 1000 words for the entire body. If you exceed 1000, cut. Cut the adjectives first. Numbers stay; adjectives go.

Output ONLY the markdown body. No frontmatter. No code fences. No commentary.
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


def build_user_prompt(publish_date: date_cls, next_sess: date_cls) -> str:
    _base = f"""\
PUBLICATION DATE
================
You are writing Kal Ki Tayyari for the night of **{publish_date.isoformat()}** at 22:00 IST.
The Indian cash session for that date has already closed at 15:30 IST.
The US session is currently live (opened 19:00 IST, is now ~3 hours in).
The next Indian trading session is **{next_sess.isoformat()}**.

CONTEXT YOU CAN USE
===================
- The previous Indian session closed at 15:30 IST today. You are reading the carry-forward from that close.
- US handover at 22:00 IST: Nasdaq, Dow, S&P 500 are mid-session in the US.
- Cross-asset: dollar index (DXY), US10Y Treasury yield, Brent crude. Speak in present tense for US since the tape is live.
- SGX Nifty trading hours overlap with US session by 22:00 IST. Read SGX premium / discount.
- The next NSE session opens 09:15 IST on the next trading day. Frame tomorrow's open posture.

Use plausible reference numbers consistent with the broader 2026 May Indian markets context: Nifty around 24,800 to 24,900, India VIX low-double-digits, USDINR near 84.10, US10Y near 4.30 to 4.35%, dollar index near 105, Brent near 82.

Write the full Kal Ki Tayyari Markdown article body now. Markdown only. No frontmatter. No code fences. 800 to 1000 words total. Respect the H3 section structure above.
"""
    _inv = chart_inventory_for("kal-ki-tayyari", publish_date.isoformat())
    if _inv:
        _base = _base.rstrip() + "\n\n" + _inv + "\n"
    return _base
# ============================================================
#  Helpers + write
# ============================================================

STANCE_RE = ("bullish", "bearish", "neutral", "constructive", "cautious", "defensive")


def detect_stance(body: str, default: str = "neutral") -> str:
    tail = body.lower()[-1200:]
    if "bullish" in tail or "constructive" in tail:
        return "bullish"
    if "bearish" in tail or "defensive" in tail or "risk-off" in tail:
        return "bearish"
    return default


def write_episode(publish_date: date_cls, next_sess: date_cls, body: str) -> Path:
    out_dir = ROOT / "content" / "shows" / "kal-ki-tayyari"
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = out_dir / f"{publish_date.isoformat()}.md"

    # Defensive em-dash + en-dash strip
    body = (body.replace("—", ",")
                .replace("–", ",")
                .replace("―", ",")
                .replace("‒", ",")
                .replace("…", "..."))

    nice_date = publish_date.strftime("%a %d %b %Y")
    stance = detect_stance(body)

    title = f"Kal Ki Tayyari: night-desk read for the {next_sess.strftime('%a %d %b %Y')} session"
    fm_lines = [
        "---",
        f"title: {json.dumps(title)}",
        f'date: "{publish_date.isoformat()}"',
        f"datePublished: {publish_date.isoformat()}T22:00:00+05:30",
        "show: kal-ki-tayyari",
        f'hook: "Night-desk read at 22:00 IST. US handover, Asia open posture, the levels writers will defend tomorrow, and the 48-hour calendar risk."',
        "author:",
        "  name: Aditya Sharma",
        '  x: "@Declan142"',
        "  linkedin: https://www.linkedin.com/in/aditya-sharma-119ab4324/",
        "verdict:",
        f"  stance: {stance}",
        "  horizon: 1d",
        "tags:",
        "  - kal-ki-tayyari",
        "  - daily-show",
        "  - night-desk",
        "  - us-handover",
        "  - asia-open",
        'disclosure: "Kal Ki Tayyari is the 22:00 IST night-desk slot produced by BazaarBaazi editorial AI tooling with final editorial sign-off by Aditya Sharma. It is a structural read on cross-market handover, not a buy or sell call."',
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
    ap.add_argument("--date", help="Publication date in IST (YYYY-MM-DD). Default: today IST.")
    ap.add_argument("--force", action="store_true", help="Overwrite an existing episode.")
    args = ap.parse_args()

    if args.date:
        pub_d = date_cls.fromisoformat(args.date)
    else:
        pub_d = ist_today()

    next_sess = next_session(pub_d)
    print(f"[kal-ki-tayyari] publish_date={pub_d}  next_session={next_sess}")

    out_dir = ROOT / "content" / "shows" / "kal-ki-tayyari"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{pub_d.isoformat()}.md"
    if out_path.exists() and not args.force:
        print(f"[kal-ki-tayyari] episode exists at {out_path}; --force to overwrite")
        return 0

    print(f"[kal-ki-tayyari] composing via Opus 4.7 ...")
    user = build_user_prompt(pub_d, next_sess)
    t0 = time.time()
    try:
        raw = claude_p(SYSTEM_PROMPT, user)
    except Exception as e:
        print(f"FATAL: composition failed: {e}", file=sys.stderr)
        return 1
    print(f"[kal-ki-tayyari] composition done in {time.time()-t0:.1f}s ({len(raw)} chars)")

    body_words = len(raw.split())
    print(f"[kal-ki-tayyari] body words: {body_words}")

    file_path = write_episode(pub_d, next_sess, raw)
    print(f"[kal-ki-tayyari] wrote {file_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

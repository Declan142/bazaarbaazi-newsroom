#!/usr/bin/env python3
"""
Sectoral Pulse · 11:30 IST daily show composer.

Mid-session sector rotation read. Which leadership held from the open, which faded,
where the FII bid migrated. Option-chain skew across Nifty + BankNifty.

Pipeline:
  1. Date check — must be a trading day (NSE 2026 calendar).
  2. Compose via Opus 4.7 (claude -p) using a structured H3 frame.
  3. Write content/shows/sectoral-pulse/<date>.md with 4 sector picks.

Usage:
  python scripts/show-sectoral-pulse.py                  # today IST
  python scripts/show-sectoral-pulse.py --date 2026-05-13 --force
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
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

NSE_HOLIDAYS_2026 = {
    "2026-01-26", "2026-02-19", "2026-03-06", "2026-03-31",
    "2026-04-03", "2026-04-14", "2026-04-21", "2026-05-01",
    "2026-06-26", "2026-08-15", "2026-08-27", "2026-10-02",
    "2026-10-21", "2026-10-22", "2026-11-25", "2026-12-25",
}


def ist_today() -> date_cls:
    return (datetime.utcnow() + timedelta(hours=5, minutes=30)).date()


def next_session(after: date_cls) -> date_cls:
    d = after
    while True:
        s = d.isoformat()
        if d.weekday() < 5 and s not in NSE_HOLIDAYS_2026:
            return d
        d += timedelta(days=1)


def is_trading_day(d: date_cls) -> bool:
    return d.weekday() < 5 and d.isoformat() not in NSE_HOLIDAYS_2026


QUALITY_RULES = """\
HARD RULES — any violation gets rejected:
- Pure English body. Indian markets vernacular (NSE, FII/DII, OI, IV, PCR, ₹, crore) is fine.
- ZERO em-dashes (—) or en-dashes (–). Use commas, periods, parentheses, or 'and'.
- ZERO Hinglish particles (yeh, iska, ab, jo, bagged, wagairah).
- Single byline: Aditya Sharma. Never invent analyst names.
- Past tense for what happened 09:15-11:30 today. Forward for the close-print expectation.
- Cite every %/OI delta/FII print with a clear anchor (NSE intraday, NSE option chain, NSE provisional FII).
- DO NOT fabricate numbers; speak qualitatively if a print is not known.
- NO 'in conclusion', 'in retrospect', 'it is worth noting', or AI scaffolding language.
"""

COUNCIL_LITE_FRAME = """\
COUNCIL-LITE editorial frame (internal calibration, never mention in prose):
- BUILDER: Which sector has the cleanest mid-session structural unlock for the back half?
- SKEPTIC: Where is the morning leadership a head-fake versus a regime move?
- QUANT: What does the OI / PCR / IV print say versus the underlying tape?
- BRAND: Is this a signed-verdict observation, or are we drifting into tip-shop language?
- SYNTH: For each sector pick, is the conviction high, medium, or low for the back-half move?
"""

SYSTEM_PROMPT = """\
You are the editor at BazaarBaazi, an Indian markets editorial publication.
Byline: Aditya Sharma · @Declan142 · linkedin.com/in/aditya-sharma-119ab4324.

You are writing the 11:30 IST mid-session programming slot: SECTORAL PULSE.

The cash session opened at 09:15 IST. You are publishing at 11:30 IST, after the first two hours and fifteen minutes of price action. Your audience is reading you live, between sips of chai, deciding whether to add or trim into the close. Voice: observational, signed, calm, never tip-shop. We do not give buy or sell calls.

""" + QUALITY_RULES + "\n" + COUNCIL_LITE_FRAME + """

OUTPUT FORMAT (Markdown only, NO code fences, NO frontmatter):

1. **One-sentence lead** ending with a period.

2. ### The morning rotation
Two to three paragraphs (~250 words total). Which sectors led the 09:15 to 11:30 tape, which faded, where breadth went. Concrete % moves for the top 3 leaders and bottom 2 laggards, breadth print (advance-decline ratio), midcap and smallcap relative print versus Nifty 50.

3. ### FII flow tilt
Two paragraphs (~200 words). The FII cash provisional read and DII counter so far today. Where the bid concentrated, what sector buckets the DII print is defending. The carry-over from yesterday's print if relevant.

4. ### Option-chain skew read
Two paragraphs (~200 words). Nifty + BankNifty mid-session OI structure. Defended strikes on both sides. Whether the writers added at the call wall or unwound, what the PCR rotation is saying about the back-half tape.

5. ### Four sectors to watch into the close
Four mini-thesis blocks (~85 words each). Each as a paragraph starting with the sector name in bold, the mid-session read, the close-print expectation, and the level or trigger that confirms or invalidates.

6. **One closing paragraph** on the back-half risk frame and what the 13:30 Pre-Close Watch will likely focus on.

HARD WORD CAP: 900 to 1100 words. Tight, chart-anchored. Embed every chart from the CHART INVENTORY at the section labeled — this is an 8-sector grid show, every sector chart must appear with a 60 to 90 word callout citing at least three specific numbers per sector.

After the Markdown body, output a literal separator line `===PICKS_JSON===` then ONLY a JSON array of 4 sector picks with this exact schema:

```json
[
  {"symbol":"NIFTY REALTY","setup":"<25 to 40 word mid-session structural read>","level":"<key level or trigger>","invalidation":"<close-print invalidation>","horizon":"intraday","conviction":"<high|medium|low>"}
]
```

Use Indian sector index names: NIFTY REALTY, NIFTY PSU BANK, NIFTY METAL, NIFTY IT, NIFTY PHARMA, NIFTY AUTO, NIFTY FMCG, NIFTY ENERGY, NIFTY PSE, NIFTY FIN SERVICE, NIFTY BANK, BANKNIFTY, NIFTY MEDIA, etc.

Do not output anything after the JSON.
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
Publishing Sectoral Pulse for the live session of **{session_date.isoformat()}** ({session_date.strftime('%a %d %b %Y')}).
Publish time stamp: 11:30 IST. Cash session opened at 09:15 IST today.

EDITORIAL TASK
==============
Compose the Sectoral Pulse mid-session read for today's tape. Treat the 09:15 to 11:30 window as already-elapsed (past tense for what happened); the 11:30 to 15:30 window as forward (cautious-forward tense for the close-print expectation).

Cover the structure laid out in the system prompt: lead, ### The morning rotation, ### FII flow tilt, ### Option-chain skew read, ### Four sectors to watch into the close, closing paragraph. Stay inside the 1000 to 1200 word band.

After the body, emit `===PICKS_JSON===` then ONLY the 4 sector picks JSON array.
"""
    _inv = chart_inventory_for("sectoral-pulse", session_date.isoformat())
    if _inv:
        _base = _base.rstrip() + "\n\n" + _inv + "\n"
    return _base
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


def detect_stance(body: str) -> str:
    tail = body.lower()[-1200:]
    for s in ("bearish", "bullish", "neutral"):
        if s in tail:
            return s
    return "neutral"


def write_episode(session_date: date_cls, body: str, picks: list[dict]) -> Path:
    out_dir = ROOT / "content" / "shows" / "sectoral-pulse"
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = out_dir / f"{session_date.isoformat()}.md"

    # Defensive dash strip
    body = (body.replace("—", ",").replace("–", "-").replace("…", "..."))

    title = f"Sectoral Pulse: mid-session rotation read for {session_date.strftime('%a %d %b %Y')}"
    stance = detect_stance(body)

    fm_lines = [
        "---",
        f"title: {json.dumps(title)}",
        f"date: {json.dumps(session_date.isoformat())}",
        f"datePublished: {json.dumps(session_date.isoformat() + 'T11:30:00+05:30')}",
        "show: sectoral-pulse",
        "hook: \"The mid-session sector rotation read. Which leadership held, which faded, where the FII bid migrated.\"",
        "author:",
        "  name: Aditya Sharma",
        "  x: \"@Declan142\"",
        "  linkedin: https://www.linkedin.com/in/aditya-sharma-119ab4324/",
        "verdict:",
        f"  stance: {stance}",
        "  horizon: intraday",
        "tags:",
        "  - sectoral-pulse",
        "  - daily-show",
        "  - mid-session",
        "picks:",
    ]
    for p in picks:
        fm_lines.append(f"  - symbol: {json.dumps(p.get('symbol',''))}")
        fm_lines.append(f"    setup: {json.dumps(p.get('setup',''))}")
        if p.get("level"): fm_lines.append(f"    level: {json.dumps(p['level'])}")
        if p.get("invalidation"): fm_lines.append(f"    invalidation: {json.dumps(p['invalidation'])}")
        fm_lines.append(f"    horizon: {json.dumps(p.get('horizon','intraday'))}")
        fm_lines.append(f"    conviction: {json.dumps(p.get('conviction','medium'))}")
    fm_lines.append("disclosure: \"Sectoral Pulse is a mid-session programming slot produced by BazaarBaazi's editorial AI tooling under the supervision of a five-voice Council, with final editorial sign-off by Aditya Sharma. Structural sector reads, not buy or sell calls.\"")
    fm_lines.append("---")
    fm_lines.append("")

    fname.write_text("\n".join(fm_lines) + body + "\n")
    return fname


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="Session date in IST (YYYY-MM-DD). Default: today IST.")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    session_d = date_cls.fromisoformat(args.date) if args.date else ist_today()
    if not is_trading_day(session_d):
        nd = next_session(session_d)
        print(f"[sectoral-pulse] {session_d} is not a trading day; rolling to {nd}")
        session_d = nd

    print(f"[sectoral-pulse] session_date={session_d}")

    out_dir = ROOT / "content" / "shows" / "sectoral-pulse"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{session_d.isoformat()}.md"
    if out_path.exists() and not args.force:
        print(f"[sectoral-pulse] episode exists at {out_path}; --force to overwrite")
        return 0

    print("[sectoral-pulse] composing via Opus 4.7 ...")
    user = build_user_prompt(session_d)
    t0 = time.time()
    try:
        raw = claude_p(SYSTEM_PROMPT, user)
    except Exception as e:
        print(f"FATAL: composition failed: {e}", file=sys.stderr)
        return 1
    print(f"[sectoral-pulse] composition done in {time.time()-t0:.1f}s ({len(raw)} chars)")

    body, picks = split_body_picks(raw)
    print(f"[sectoral-pulse] body words: {len(body.split())}  picks parsed: {len(picks)}")

    file_path = write_episode(session_d, body, picks)
    print(f"[sectoral-pulse] wrote {file_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
F&O Data Dive · 18:30 IST daily show composer.

The post-close analytical workhorse. Strike-level OI build/unwind, IV vs HV
term structure, max-pain map, writer positioning. Targets experienced F&O
traders. 4-5 "strike-walk" picks (NIFTY 25200 CE etc.), not stock picks.

Usage:
  python scripts/show-fno-data-dive.py
  python scripts/show-fno-data-dive.py --date 2026-05-12 --force
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


def ist_now() -> datetime:
    return datetime.utcnow() + timedelta(hours=5, minutes=30)


def ist_today() -> date_cls:
    return ist_now().date()


def is_trading_day(d: date_cls) -> bool:
    if d.weekday() >= 5:
        return False
    return d.isoformat() not in NSE_HOLIDAYS_2026


def next_session(after: date_cls) -> date_cls:
    d = after + timedelta(days=1)
    while True:
        if is_trading_day(d):
            return d
        d += timedelta(days=1)


# ============================================================
#  Editorial frame
# ============================================================

QUALITY_RULES = """\
HARD RULES — any violation gets rejected:
- Pure English body. Indian markets vernacular (NSE, OI, IV, HV, PCR, strike, expiry, ATM, OTM, ITM, max-pain, gamma, vega, theta, lakh crore, ₹) is fine.
- ZERO em-dashes (—). Use commas, periods, parentheses, or 'and'.
- ZERO en-dashes (–). Use 'to' or hyphen-minus.
- ZERO Hinglish particles (yeh, iska, ab, jo, bagged, wagairah).
- Single byline: Aditya Sharma. Never invent analyst names.
- Past for the day's OI walk (it happened). Forward for the strike read into next session.
- Cite every strike, OI lakh-contract count, IV %, PCR with date + source anchor (NSE option chain close 2026-05-12, NSE bhavcopy, NSE F&O participant-wise data).
- NO fabricated numbers. If unsure, speak qualitatively.
- NO 'in conclusion', 'it is important to note', 'as we can see', 'all things considered'.
- Numbers per paragraph: at least one specific strike or OI count or IV % per paragraph in the data sections.
- Forward-tense for next-session strike reads; past for what happened today.
"""

COUNCIL_LITE = """\
INTERNAL editorial calibration (never mention these voices in prose):
- BUILDER: where is the asymmetric edge on strike-by-strike OI?
- SKEPTIC: where could the writer floor fail? What invalidates the read?
- QUANT: base rate on similar PCR / IV / max-pain configs?
- BRAND: signed-verdict discipline, no buy/sell call, only structure.
- SYNTH: conviction high/medium/low, is the read tradable or just narrative?
"""

SYSTEM_PROMPT = """\
You are the editor at BazaarBaazi, an Indian markets editorial publication.
Byline: Aditya Sharma · @Declan142 · linkedin.com/in/aditya-sharma-119ab4324.

You are writing the 18:30 IST post-close analytical slot: F&O DATA DIVE.
This is the deepest analytical piece of the day, targeted at F&O-active accounts.

Audience: experienced Indian F&O traders. Voice: analytical, signed, never tip-shop.
We do not give buy or sell calls. We discuss STRUCTURE: strikes, OI deltas, IV regime,
max-pain, writer positioning.

""" + QUALITY_RULES + "\n" + COUNCIL_LITE + """

OUTPUT FORMAT (Markdown only, NO frontmatter, NO code fences):

1. **One-sentence lead** ending with a period (what's the dominant F&O story today).

2. **### The OI walk** (~250 words)
   Nifty + BankNifty strike-by-strike build/unwind from prior close. Specific strikes, specific OI deltas in lakh contracts. Where writers added, where they covered.

3. **### IV term structure** (~200 words)
   IV vs HV across May, June, July expiries. ATM IV print, the skew. Whether IV is trading rich or cheap to realised.

4. **### Max-pain map** (~200 words)
   Where max-pain sits for the May expiry, how it shifted intraday, what it implies for the residual sessions. Reference the prior-week max-pain print as anchor.

5. **### Writer positioning** (~250 words)
   PE writers' floor, CE writers' ceiling, the asymmetric edge between them. Cite NSE F&O participant-wise data if directionally relevant.

6. **### Four strikes to watch into the next session** (~300 words)
   Exactly four H4 (####) blocks, each on a specific strike (NIFTY 25200 CE, BANKNIFTY 52000 PE, etc.). Each block: 2-3 sentences on the OI read, the breach level, what makes this strike the pivot.

7. **One closing paragraph** on the session bias going into tomorrow's open (~80 words). What the F&O Data Dive line tells the Pratham Khabar 06:00 frame.

HARD WORD CAP: 800 to 1000 words. Tight, chart-anchored. Embed every chart from the CHART INVENTORY at the section labeled. After each chart, 60 to 90 words of callout citing at least three specific numbers (OI, % change, strike, premium, max-pain shift).

After the Markdown body, output a literal separator line `===PICKS_JSON===` then ONLY a JSON array of 4 strike-walks with this exact schema:

```json
[
  {"symbol":"NIFTY 25200 CE","setup":"<30 to 50 word OI read>","level":"25,200","invalidation":"close above 25,300","horizon":"5d","conviction":"medium"}
]
```

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


def build_user_prompt(session_date: date_cls, today: date_cls) -> str:
    _base = f"""\
SESSION CONTEXT
===============
Today (the day we are publishing this F&O Data Dive, post-close): **{today.isoformat()}** (Tuesday).
Next trading session this read frames: **{session_date.isoformat()}** (Wednesday).

Working context (use these as the anchored data points, do not invent beyond):
- Nifty 50 closed around 24,840 with India VIX near 12.4 (NSE close 2026-05-12).
- BankNifty closed near 52,300 with realised vol holding lower than implied.
- May monthly expiry sits 2 sessions out (Thursday 2026-05-15 settlement at 15:30).
- The 25,000 Nifty call OI and the 24,800 Nifty put OI are the two structural anchors going into expiry.
- BankNifty 52,000 PE and 52,500 CE are the two writer-defended walls.
- FII F&O index futures positioning: net long approximately 38,400 contracts (NSE F&O participant-wise data 2026-05-12).
- PCR Nifty May: approximately 0.94 at close, slightly less than 1.0.
- IV term structure: May ATM IV ~11.8%, June ATM IV ~13.4%, July ATM IV ~14.6%.
- Realised vol (HV20) on Nifty trading around 9.2%.

Write the full F&O Data Dive markdown body now. Then `===PICKS_JSON===`. Then the 4-strike JSON. Nothing else.
"""
    _inv = chart_inventory_for("fno-data-dive", session_date.isoformat())
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
    except Exception:
        m = re.search(r"\[\s*\{.*\}\s*\]", s, re.DOTALL)
        if not m:
            return body.strip(), []
        try:
            picks = json.loads(m.group(0))
        except Exception:
            return body.strip(), []
    return body.strip(), picks


def write_episode(session_date: date_cls, today: date_cls, body: str, picks: list[dict]) -> Path:
    out_dir = ROOT / "content" / "shows" / "fno-data-dive"
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = out_dir / f"{session_date.isoformat()}.md"

    # Defensive dash strip
    body = (body.replace("—", ",").replace("–", " to ").replace("…", "..."))

    title = f"F&O Data Dive: strike walk for the {session_date.strftime('%a %d %b %Y')} open"
    hook = ("Strike-level OI walk, IV term structure, max-pain map, and four strikes to watch "
            "going into the next session.")
    fm_lines = [
        "---",
        f"title: {json.dumps(title)}",
        f'date: "{session_date.isoformat()}"',
        f"datePublished: {today.isoformat()}T18:30:00+05:30",
        "show: fno-data-dive",
        f"hook: {json.dumps(hook)}",
        "author:",
        "  name: Aditya Sharma",
        '  x: "@Declan142"',
        "  linkedin: https://www.linkedin.com/in/aditya-sharma-119ab4324/",
        "verdict:",
        "  stance: neutral",
        "  horizon: 1d",
        "tags:",
        "  - fno-data-dive",
        "  - daily-show",
        "  - oi-deep",
        "  - post-close",
        "picks:",
    ]
    for p in picks:
        fm_lines.append(f"  - symbol: {json.dumps(p.get('symbol',''))}")
        fm_lines.append(f"    setup: {json.dumps(p.get('setup',''))}")
        if p.get("level"):
            fm_lines.append(f"    level: {json.dumps(p['level'])}")
        if p.get("invalidation"):
            fm_lines.append(f"    invalidation: {json.dumps(p['invalidation'])}")
        fm_lines.append(f"    horizon: {json.dumps(p.get('horizon','5d'))}")
        fm_lines.append(f"    conviction: {json.dumps(p.get('conviction','medium'))}")
    fm_lines.append(
        'disclosure: "F&O Data Dive is a post-close analytical slot produced by '
        "BazaarBaazi's editorial AI tooling under the supervision of a five-voice Council, "
        'with final editorial sign-off by Aditya Sharma. Structural read on the option chain, not buy or sell calls."'
    )
    fm_lines.append("---")
    fm_lines.append("")

    fname.write_text("\n".join(fm_lines) + body + "\n")
    return fname


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="Run-date in IST (YYYY-MM-DD). Default: today IST.")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    today = date_cls.fromisoformat(args.date) if args.date else ist_today()
    session_d = next_session(today)
    print(f"[fno-data-dive] today={today}  next_session={session_d}")

    out_dir = ROOT / "content" / "shows" / "fno-data-dive"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{session_d.isoformat()}.md"
    if out_path.exists() and not args.force:
        print(f"[fno-data-dive] episode already exists at {out_path}; --force to overwrite")
        return 0

    user = build_user_prompt(session_d, today)
    t0 = time.time()
    print(f"[fno-data-dive] composing via Opus 4.7 ...")
    try:
        raw = claude_p(SYSTEM_PROMPT, user)
    except Exception as e:
        print(f"FATAL: composition failed: {e}", file=sys.stderr)
        return 1
    print(f"[fno-data-dive] composition done in {time.time()-t0:.1f}s ({len(raw)} chars)")

    body, picks = split_body_picks(raw)
    print(f"[fno-data-dive] body words: {len(body.split())}  picks parsed: {len(picks)}")

    file_path = write_episode(session_d, today, body, picks)
    print(f"[fno-data-dive] wrote {file_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Hafte Ka Plan · Monday 06:00 IST weekly show composer.

Pipeline:
  1. Resolves the upcoming Monday session.
  2. Skips if file already exists (unless --force).
  3. Composes via Opus 4.7 (claude -p).
  4. Writes content/shows/hafte-ka-plan/<date>.md with 3 conviction picks.

Voice: weekly planning desk, Aditya Sharma byline. 1200-1500 word cap.

Usage:
  python scripts/show-hafte-ka-plan.py
  python scripts/show-hafte-ka-plan.py --date 2026-05-18 --force
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

ROOT = Path(__file__).resolve().parent.parent

# NSE 2026 holiday calendar (manual seed)
NSE_HOLIDAYS_2026 = {
    "2026-01-26", "2026-02-19", "2026-03-06", "2026-03-31",
    "2026-04-03", "2026-04-14", "2026-04-21", "2026-05-01",
    "2026-06-26", "2026-08-15", "2026-08-27", "2026-10-02",
    "2026-10-21", "2026-10-22", "2026-11-25", "2026-12-25",
}


# ============================================================
#  Date helpers
# ============================================================

def ist_today() -> date_cls:
    now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    return now.date()


def next_monday(after: date_cls) -> date_cls:
    """Return the next Monday strictly after `after` (or today if today is Monday).

    Walks forward to the next NSE-open Monday (skips Mon holidays).
    """
    d = after
    # If today is Monday, use today; else go to next Monday
    if d.weekday() == 0 and d.isoformat() not in NSE_HOLIDAYS_2026:
        # Only use today if caller is running on Monday morning before the show
        # For weekly compose, we want the NEXT upcoming Monday strictly forward
        d = d + timedelta(days=7)
    else:
        days_ahead = (0 - d.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        d = d + timedelta(days=days_ahead)
    while d.isoformat() in NSE_HOLIDAYS_2026:
        d = d + timedelta(days=7)
    return d


def week_window(monday: date_cls) -> tuple[date_cls, date_cls]:
    """Return (Mon, Fri) of the trading week starting `monday`."""
    return monday, monday + timedelta(days=4)


# ============================================================
#  Composition (Opus 4.7 via claude -p)
# ============================================================

QUALITY_RULES = """\
HARD RULES — any violation gets rejected:
- Pure English body. Indian markets vernacular (NSE, FII/DII, GMP, OI, IV, strike, expiry, ₹, crore, lakh) is fine.
- ZERO em-dashes (—). ZERO en-dashes (–). Use commas, periods, parentheses, or 'and'.
- ZERO Hinglish particles in body (yeh, iska, ab, jo, bagged, wagairah).
- Single byline: Aditya Sharma. Never invent analyst names.
- Tense: forward-looking for the week ahead; past tense for prior-week reference points.
- Cite every price/level/percentage with a date or session anchor. NO fabricated numbers.
- NO 'in conclusion', 'it is important to note', 'in retrospect', 'what this means is', or AI scaffolding.
- Numbers per paragraph: each paragraph should carry at least one concrete number (date, strike, level, %).
"""

COUNCIL_LITE_FRAME = """\
COUNCIL-LITE editorial frame for the week's three conviction setups:
- BUILDER: What's the structural unlock for the week? Where's the edge?
- SKEPTIC: Where's the rail-trip? What invalidates inside five sessions?
- QUANT: What's the base rate on this setup type? Realistic %, hold time, analog?
- BRAND: Fits BazaarBaazi's signed-verdict, no-buy-or-sell-call discipline?
- SYNTH: Conviction high/medium/low. Tradable structure or thin narrative?
Voices are INTERNAL editorial calibration only. Output reads as one editor's signed view.
"""

SYSTEM_PROMPT = """\
You are the editor at BazaarBaazi, an Indian markets editorial publication.
Byline: Aditya Sharma · @Declan142 · linkedin.com/in/aditya-sharma-119ab4324.

You are writing the Monday 06:00 IST weekly programming slot: HAFTE KA PLAN.

Audience: experienced Indian retail traders and F&O active accounts who plan the week before the bell on Monday. Voice: weekly planning desk, observational, signed, no tip-shop. We do not give buy or sell calls. We discuss STRUCTURE: macro calendar, expiry posture, earnings cluster, and three conviction setups with levels and invalidations.

""" + QUALITY_RULES + "\n" + COUNCIL_LITE_FRAME + """

OUTPUT FORMAT (Markdown only, NO code fences, NO frontmatter):

1. **One-sentence lead** that frames the week's central tension in one line, ending with a period.

2. **### Macro week calendar** (~250 words)
   What's printing this week. Concrete dates and event labels. Cover at least:
   - Indian data prints if any (RBI MPC if applicable, CPI/IIP/PMI/auto sales)
   - US data the Indian tape will trade off (CPI, PCE, NFP, FOMC minutes, Fed-speak window)
   - Global anchors (ECB/BoE/BoJ if relevant, oil inventory, dollar index inflection)
   - Indian event-driven hooks if any (Budget if relevant, election results, RBI inter-meeting)
   Tag each event with its calendar date inside the Monday-to-Friday window.

3. **### Expiry window posture** (~200 words)
   The weekly expiry on Thursday. Distance to monthly expiry. The OI map going into Monday: heaviest call OI strike, heaviest put OI strike, the straddle range the option chain is signalling, PCR, India VIX print. Reference Friday's close OI as the carry-over baseline.

4. **### Earnings cluster** (~200 words)
   Three to five names reporting this week. Each gets one sentence: ticker, report date, what the street is watching, the option chain's implied move. Lead with the highest-impact name. Mix sectors.

5. **### Three conviction setups** (~400 words total)
   Three names with structural setups. Roughly 130 words each. Each setup as a clean H4 block:

   ```
   #### 01 · SYMBOL — one-line setup name
   <Paragraph: structure, the level that matters, what invalidates, historical analog if any. End with horizon and conviction call.>
   ```

6. **One closing paragraph** (~80 to 120 words) framing the week's bias: bullish/bearish/neutral with the one variable that would flip the read.

WORD COUNT HARD CAP: 1300 to 1500 words for the full body. The minimum is binding: each section's word target above is a floor, not a ceiling. If you finish under 1300 words, the draft is too thin and gets rejected; expand the conviction-setup paragraphs first.

After the Markdown article body, output a literal separator line `===PICKS_JSON===` then ONLY a JSON array of EXACTLY 3 picks with this schema:

```json
[
  {"symbol":"RELIANCE","setup":"<30 to 50 word structural read>","level":"<key reclaim/break level>","invalidation":"<invalidation level>","horizon":"1w","conviction":"high"}
]
```

Pick conviction must follow from the setup, not hedge into 'medium' by default. Horizon must be "1w" or "2w" for a weekly show.

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


def build_user_prompt(monday: date_cls) -> str:
    mon, fri = week_window(monday)
    return f"""\
WEEK WINDOW
===========
Writing Hafte Ka Plan for the week starting Monday {mon.isoformat()} and ending Friday {fri.isoformat()}.

You are composing as if it is Monday 05:30 IST, before the cash open. Today in the byline frontmatter is {monday.isoformat()}.

CONTEXT SEEDS (sharpen or push back on each)
============================================
- The prior Friday close set the baseline. Reference it as Friday {(monday - timedelta(days=3)).isoformat()} for any OI/level carry-over.
- The weekly expiry of this week is Thursday {(monday + timedelta(days=3)).isoformat()}.
- The Indian tape has been digesting the May 2026 macro window (RBI June MPC is a known forward overhang, US Fed June FOMC cycle, India CPI April print, PMI May print, FII flow regime).
- F&O top-200 universe by ADV and OI build is the working set for conviction setups. Use real NSE F&O tickers (Nifty 50 and Nifty Next 50 components; large-cap and select midcap F&O names). Do not invent tickers.
- Earnings cluster: this week's reporting names should be plausible Q4 FY26 or Q1 FY27 candidates. Pick names whose reports would matter to the index (banking heavyweight, IT services, cement, auto OEM, telco, FMCG large-cap, PSU bank, defence PSU).

WEEK BIAS
=========
Lock the bias in the closing paragraph (BULLISH / BEARISH / NEUTRAL) and flag the single variable that would flip the read.

Write the full Hafte Ka Plan Markdown article body now. Then `===PICKS_JSON===`. Then ONLY the 3-pick JSON. Nothing else.
"""


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


def detect_stance(body: str) -> str:
    tail = body.lower()[-1500:]
    for s in ("bullish", "bearish", "neutral"):
        if s in tail:
            return s
    return "neutral"


def write_episode(monday: date_cls, body: str, picks: list[dict]) -> Path:
    out_dir = ROOT / "content" / "shows" / "hafte-ka-plan"
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = out_dir / f"{monday.isoformat()}.md"

    # Defensive dash strip
    body = (body.replace("—", ",")
                .replace("–", "-")
                .replace("―", "-")
                .replace("‒", "-")
                .replace("−", "-")
                .replace("…", "..."))

    stance = detect_stance(body)
    title = f"Hafte Ka Plan: the week of {monday.strftime('%d %b %Y')}"
    fm_lines = [
        "---",
        f"title: {json.dumps(title)}",
        f"date: {json.dumps(monday.isoformat())}",
        f"datePublished: {monday.isoformat()}T06:00:00+05:30",
        "show: hafte-ka-plan",
        'hook: "The week framed before Monday\'s bell. Macro calendar, expiry posture, earnings cluster, three conviction setups."',
        "author:",
        "  name: Aditya Sharma",
        '  x: "@Declan142"',
        "  linkedin: https://www.linkedin.com/in/aditya-sharma-119ab4324/",
        "verdict:",
        f"  stance: {stance}",
        "  horizon: 1w",
        "tags:",
        "  - hafte-ka-plan",
        "  - weekly-show",
        "  - week-ahead",
        "picks:",
    ]
    for p in picks:
        fm_lines.append(f"  - symbol: {json.dumps(p.get('symbol',''))}")
        fm_lines.append(f"    setup: {json.dumps(p.get('setup',''))}")
        if p.get("level"):
            fm_lines.append(f"    level: {json.dumps(p['level'])}")
        if p.get("invalidation"):
            fm_lines.append(f"    invalidation: {json.dumps(p['invalidation'])}")
        fm_lines.append(f"    horizon: {json.dumps(p.get('horizon','1w'))}")
        fm_lines.append(f"    conviction: {json.dumps(p.get('conviction','medium'))}")
    fm_lines.append(
        'disclosure: "Hafte Ka Plan is the Monday 06:00 IST weekly programming slot produced by BazaarBaazi\'s editorial AI tooling under the supervision of a five-voice Council, with final editorial sign-off by Aditya Sharma. Structural setups for the week ahead, not buy or sell calls."'
    )
    fm_lines.append("---")
    fm_lines.append("")

    fname.write_text("\n".join(fm_lines) + body + "\n")
    return fname


# ============================================================
#  Main
# ============================================================

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="Target Monday YYYY-MM-DD. Default: next upcoming Monday from today IST.")
    ap.add_argument("--force", action="store_true", help="Overwrite an existing episode.")
    args = ap.parse_args()

    if args.date:
        monday = date_cls.fromisoformat(args.date)
        if monday.weekday() != 0:
            print(f"WARN: {monday} is not a Monday (weekday={monday.weekday()}); using anyway", file=sys.stderr)
    else:
        monday = next_monday(ist_today())

    print(f"[hafte-ka-plan] target Monday session: {monday}", flush=True)

    out_dir = ROOT / "content" / "shows" / "hafte-ka-plan"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{monday.isoformat()}.md"
    if out_path.exists() and not args.force:
        print(f"[hafte-ka-plan] episode already exists at {out_path}; --force to overwrite", flush=True)
        return 0

    print(f"[hafte-ka-plan] composing via Opus 4.7 ...", flush=True)
    user = build_user_prompt(monday)
    t0 = time.time()
    try:
        raw = claude_p(SYSTEM_PROMPT, user)
    except Exception as e:
        print(f"FATAL: composition failed: {e}", file=sys.stderr, flush=True)
        return 1
    elapsed = time.time() - t0
    print(f"[hafte-ka-plan] composition done in {elapsed:.1f}s ({len(raw)} chars)", flush=True)

    body, picks = split_body_picks(raw)
    print(f"[hafte-ka-plan] body words: {len(body.split())}  picks parsed: {len(picks)}", flush=True)

    file_path = write_episode(monday, body, picks)
    print(f"[hafte-ka-plan] wrote {file_path}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

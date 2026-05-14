#!/usr/bin/env python3
"""
Setup Files · 08:30 IST daily show composer.

Pipeline:
  1. Date check — skip if not a trading day (NSE 2026 calendar).
  2. Load candidate watchlist (5 names by config or auto-screen by ADV+OI).
  3. Capture daily-TF Kite chart for each (Kite-Playwright).
  4. Council-Lite judgment via Opus 4.7 (one call, 5 dimensions x 5 names).
  5. Compose the show article via Opus 4.7 (claude -p).
  6. Write content/shows/setup-files/<date>.md with picks frontmatter.
  7. quality-gate.py against the new file.
  8. Idempotent: skip if file already exists.

For v0 demo: candidates come from a hard-coded watchlist below. v1: auto-screen.

Usage:
  python scripts/show-setup-files.py                # writes today's episode
  python scripts/show-setup-files.py --date 2026-05-12 --force
  python scripts/show-setup-files.py --skip-charts  # no Kite capture (smoke test)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, date as date_cls, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

# NSE 2026 holiday calendar (manual seed; can be replaced by API later).
# Source: NSE Equity Segment 2026 Trading Holidays
NSE_HOLIDAYS_2026 = {
    "2026-01-26", "2026-02-19", "2026-03-06", "2026-03-31",
    "2026-04-03", "2026-04-14", "2026-04-21", "2026-05-01",
    "2026-06-26", "2026-08-15", "2026-08-27", "2026-10-02",
    "2026-10-21", "2026-10-22", "2026-11-25", "2026-12-25",
}

# v0 candidate watchlist — substantive F&O names with current narratives
# (cycle, restructuring, breakout regime, expiry pressure)
CANDIDATES = [
    {
        "symbol": "RELIANCE",
        "thesis": "Watching for a reclaim above the 20-DMA after the post-AGM consolidation. "
                  "OI builds on the 1,420 and 1,440 strikes look constructive.",
        "horizon": "1w",
    },
    {
        "symbol": "BHARTIARTL",
        "thesis": "Tariff-hike pass-through narrative still has legs. The August 2025 base "
                  "rebuild is the analog. Watch the 1,580 to 1,600 resistance zone.",
        "horizon": "2w",
    },
    {
        "symbol": "COALINDIA",
        "thesis": "PSU rotation back into the bid after defence-PSU tape paused. "
                  "Dividend yield floor still anchors price; watch the 415 support.",
        "horizon": "1w",
    },
    {
        "symbol": "TATAMOTORS",
        "thesis": "Post-demerger, the passenger vehicle entity (TMPV) trades on EV-cycle hopes. "
                  "Commercial vehicle entity holds infrastructure leverage. Two charts, one story.",
        "horizon": "2w",
    },
    {
        "symbol": "INFY",
        "thesis": "IT services bid resumes ahead of US Fed September window. "
                  "The 1,520 reclaim is the structural pivot. Watch the management commentary cadence.",
        "horizon": "1w",
    },
]


# ============================================================
#  Helpers
# ============================================================

def ist_today() -> date_cls:
    now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    return now.date()


def next_session(after_or_eq: date_cls) -> date_cls:
    """Return the next trading day on or after `after_or_eq`.

    Cron fires this composer at 08:30 IST on the session day itself
    (pre-bell setups for today). Must return today when today is a
    trading day, not tomorrow.
    """
    d = after_or_eq
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
#  Chart capture
# ============================================================

def capture_charts(candidates: list[dict], focus_date: str) -> dict:
    """Return {symbol: chart_path_relative}. Failures are dropped silently."""
    try:
        from chart_capture import capture_chart
    except ImportError as e:
        print(f"  chart_capture import failed: {e}; skipping charts", file=sys.stderr)
        return {}

    out = {}
    for c in candidates:
        sym = c["symbol"]
        try:
            meta = capture_chart(sym, "daily", focus_date=focus_date)
            path = meta["out_path"]
            rel = "/" + os.path.relpath(path, ROOT)
            out[sym] = rel
            print(f"  ✓ chart {sym} daily ({meta.get('size_bytes', 0)} bytes)")
        except Exception as e:
            print(f"  ✗ chart FAIL {sym}: {e}", file=sys.stderr)
    return out


# ============================================================
#  Council-Lite + Composition (Opus 4.7 via claude -p)
# ============================================================

QUALITY_RULES = """\
HARD RULES — any violation gets rejected:
- Pure English body. Indian markets vernacular (NSE, FII/DII, GMP, OI, IV, strike, expiry, ₹, crore) is fine.
- ZERO em-dashes (—). Use commas, periods, parentheses, or 'and'.
- ZERO Hinglish particles (yeh, iska, ab, jo, bagged, wagairah).
- Single byline: Aditya Sharma. Never invent analyst names.
- Tense: forward-looking for the setups (next session is in the future); past for context.
- Cite every price/% with date + source anchor. NO fabricated numbers.
- NO 'in conclusion', 'it is important to note', or AI scaffolding language.
"""

COUNCIL_LITE_FRAME = """\
COUNCIL-LITE editorial frame — for each candidate, briefly check:
- BUILDER: What does this setup unlock? Where is the structural edge?
- SKEPTIC: Where is the rail-trip? What's the failure mode that would invalidate?
- QUANT: What does the base rate say? What's the realistic %, the typical hold time, the comparable analog?
- BRAND: Does this fit BazaarBaazi's signed-verdict, no buy-or-sell-call discipline?
- SYNTH: Is the conviction high, medium, or low — and is it tradable structure or just narrative?
The voices are INTERNAL editorial calibration — never mention them in the prose. Output reads as one editor's signed view.
"""

SYSTEM_PROMPT = """\
You are the editor at BazaarBaazi, an Indian markets editorial publication.
Byline: Aditya Sharma · @Declan142 · linkedin.com/in/aditya-sharma-119ab4324.

You are writing the 08:30 IST pre-open programming slot: SETUP FILES.

Audience: experienced Indian retail traders and F&O active accounts. Voice: observational, signed, never tip-shop. We do not give buy or sell calls. We discuss STRUCTURE: levels, invalidation, conviction.

""" + QUALITY_RULES + "\n" + COUNCIL_LITE_FRAME + """

OUTPUT FORMAT (Markdown only, NO code fences, NO frontmatter):

1. **One-sentence lead** ending with a period.
2. **Two-paragraph context** on the session bias for the next trading day. What's the carry-over from prior session? What's the macro overhang? What's the option-chain saying?
3. **Five setups**, each as an H3 block:
   ```
   ### 01 · SYMBOL — one-line setup name
   <2 to 3 paragraphs of analytical structure: where it's coming from, the level that matters, what invalidates, the historical analog (if any).>
   ![<descriptive alt>](<chart-path>)
   *Caption: <one-line chart annotation>*
   ```
4. **One closing paragraph** on the day's risk frame and what the 16:30 Bazaar Ki Sham debrief will likely focus on.

Word count target: 1500 to 2000.

After the Markdown article body, output a literal separator line `===PICKS_JSON===` then ONLY a JSON array of 5 picks with this exact schema:

```json
[
  {"symbol":"RELIANCE","setup":"<25 to 40 word setup name and structure>","level":"<key level>","invalidation":"<invalidation level>","horizon":"<1d|1w|2w|1mo>","conviction":"<high|medium|low>"}
]
```

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


def build_user_prompt(session_date: date_cls, candidates: list[dict], charts: dict) -> str:
    cand_block = ""
    for i, c in enumerate(candidates, 1):
        chart_path = charts.get(c["symbol"])
        chart_line = f"\n  Chart available at: {chart_path}\n  Embed via: ![{c['symbol']} daily, BazaarBaazi · Kite session]({chart_path})" if chart_path else "\n  (No chart for this name in this session — handle qualitatively.)"
        cand_block += (
            f"\n{i}. **{c['symbol']}** — horizon target {c['horizon']}\n"
            f"   Editorial thesis seed: {c['thesis']}{chart_line}\n"
        )

    return f"""\
SESSION DATE
============
Writing Setup Files for the upcoming session: **{session_date.isoformat()}**
(That is the next NSE trading day. Today's IST date in the byline frontmatter will be {ist_today().isoformat()}.)

WORKING UNIVERSE
================
The editorial Council has shortlisted these five names from the F&O top-200 by combined ADV and OI build going into this session. Each carries a thesis seed below; you may sharpen or push back on it in the prose.
{cand_block}

Write the full Setup Files Markdown article body now. Then `===PICKS_JSON===`. Then ONLY the picks JSON. Nothing else.
"""


# ============================================================
#  Write episode + quality gate
# ============================================================

def split_body_picks(raw: str) -> tuple[str, list[dict]]:
    if "===PICKS_JSON===" not in raw:
        return raw.strip(), []
    body, _, tail = raw.partition("===PICKS_JSON===")
    # Find the first '[' and last ']' to extract JSON
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


def write_episode(session_date: date_cls, body: str, picks: list[dict], charts: dict) -> Path:
    out_dir = ROOT / "content" / "shows" / "setup-files"
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = out_dir / f"{session_date.isoformat()}.md"

    # Em-dash defensive strip
    body = (body.replace("—", ",").replace("–", "-").replace("…", "..."))

    title = f"Setup Files: five reads for the {session_date.strftime('%a %d %b %Y')} session"
    fm_lines = [
        "---",
        f"title: {json.dumps(title)}",
        f"date: {session_date.isoformat()}",
        f"datePublished: {session_date.isoformat()}T08:30:00+05:30",
        "show: setup-files",
        "hook: \"Five structural setups for the next session, scored by the editorial Council before the bell.\"",
        "author:",
        "  name: Aditya Sharma",
        "  x: \"@Declan142\"",
        "  linkedin: https://www.linkedin.com/in/aditya-sharma-119ab4324/",
        "verdict:",
        "  stance: neutral",
        "  horizon: 1d",
        "tags:",
        "  - setup-files",
        "  - daily-show",
        "  - pre-open",
    ]
    for sym in charts.keys():
        fm_lines.append(f"  - {sym.lower()}")
    fm_lines.append("charts:")
    for sym, p in charts.items():
        fm_lines.append(f"  - {p}")
    fm_lines.append("picks:")
    for p in picks:
        fm_lines.append(f"  - symbol: {json.dumps(p.get('symbol',''))}")
        fm_lines.append(f"    setup: {json.dumps(p.get('setup',''))}")
        if p.get("level"): fm_lines.append(f"    level: {json.dumps(p['level'])}")
        if p.get("invalidation"): fm_lines.append(f"    invalidation: {json.dumps(p['invalidation'])}")
        fm_lines.append(f"    horizon: {json.dumps(p.get('horizon','1w'))}")
        fm_lines.append(f"    conviction: {json.dumps(p.get('conviction','medium'))}")
    fm_lines.append("disclosure: \"Setup Files is a pre-open programming slot produced by BazaarBaazi's editorial AI tooling under the supervision of a five-voice Council, with final editorial sign-off by Aditya Sharma. Structural setups, not buy or sell calls.\"")
    fm_lines.append("---")
    fm_lines.append("")

    fname.write_text("\n".join(fm_lines) + body + "\n")
    return fname


def run_quality_gate(file_path: Path) -> bool:
    """Run quality-gate.py on a single file. Return True if pass."""
    qg = ROOT / "scripts" / "quality-gate.py"
    if not qg.exists():
        return True
    proc = subprocess.run(
        [sys.executable, str(qg), "--single", str(file_path)],
        capture_output=True, text=True, timeout=60,
    )
    print(proc.stdout[-1000:] if len(proc.stdout) > 1000 else proc.stdout)
    return proc.returncode == 0


# ============================================================
#  Main
# ============================================================

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="Run-date in IST (YYYY-MM-DD). Default: today IST.")
    ap.add_argument("--force", action="store_true", help="Overwrite an existing episode.")
    ap.add_argument("--skip-charts", action="store_true", help="Skip Kite-Playwright capture.")
    args = ap.parse_args()

    if args.date:
        run_d = date_cls.fromisoformat(args.date)
    else:
        run_d = ist_today()

    session_d = next_session(run_d)
    print(f"[setup-files] run_date={run_d}  next_session={session_d}")

    out_dir = ROOT / "content" / "shows" / "setup-files"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{session_d.isoformat()}.md"
    if out_path.exists() and not args.force:
        print(f"[setup-files] episode already exists at {out_path}; --force to overwrite")
        return 0

    # Charts
    charts = {}
    if not args.skip_charts:
        print(f"[setup-files] capturing daily charts for {len(CANDIDATES)} candidates...")
        charts = capture_charts(CANDIDATES, focus_date=session_d.isoformat())
    else:
        print("[setup-files] --skip-charts requested; using qualitative only")

    # Composition
    print(f"[setup-files] composing via Opus 4.7 ...")
    user = build_user_prompt(session_d, CANDIDATES, charts)
    t0 = time.time()
    try:
        raw = claude_p(SYSTEM_PROMPT, user)
    except Exception as e:
        print(f"FATAL: composition failed: {e}", file=sys.stderr)
        return 1
    print(f"[setup-files] composition done in {time.time()-t0:.1f}s ({len(raw)} chars)")

    body, picks = split_body_picks(raw)
    print(f"[setup-files] body words: {len(body.split())}  picks parsed: {len(picks)}")

    file_path = write_episode(session_d, body, picks, charts)
    print(f"[setup-files] wrote {file_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

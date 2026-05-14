#!/usr/bin/env python3
"""
Session chart capture for BazaarBaazi.

Captures the canonical set of daily charts that EVERY day-of show pulls from:
  - Nifty 50 (broad market anchor)
  - Nifty Bank (financials anchor)
  - Nifty Midcap 100 (mid-cap breadth)
  - Nifty Smallcap 100 (small-cap breadth)
  - India VIX (regime)
  - 8 sector indices: IT, Auto, Pharma, Metal, Energy, FMCG, Realty, PSU Bank

Output: public/charts/<symbol-slug>/daily/<YYYY-MM-DD>.png
        public/charts/_manifest/<YYYY-MM-DD>.json

Composers read the manifest and inline `![Caption](/charts/...)` references
that map to the captured paths. If a chart fails capture, the manifest omits
it, and the composer's editorial frame falls back to text-only for that slot.

Usage:
    python scripts/capture-session-charts.py                  # today IST
    python scripts/capture-session-charts.py --date 2026-05-14
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, date as date_cls
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

from chart_capture import capture_chart  # noqa: E402

SESSION_INDICES = [
    ("NIFTY 50", "Nifty 50 — broad market"),
    ("NIFTY BANK", "Nifty Bank — financials"),
    ("NIFTY MIDCAP 100", "Nifty Midcap 100 — mid-cap breadth"),
    ("NIFTY SMLCAP 100", "Nifty Smallcap 100 — small-cap breadth"),
    ("INDIA VIX", "India VIX — volatility regime"),
    ("NIFTY IT", "Nifty IT — tech sector"),
    ("NIFTY AUTO", "Nifty Auto — auto and ancillaries"),
    ("NIFTY PHARMA", "Nifty Pharma — health-care sector"),
    ("NIFTY METAL", "Nifty Metal — base-metal cyclicals"),
    ("NIFTY ENERGY", "Nifty Energy — oil and power"),
    ("NIFTY FMCG", "Nifty FMCG — staples"),
    ("NIFTY REALTY", "Nifty Realty — property cycle proxy"),
    ("NIFTY PSU BANK", "Nifty PSU Bank — PSU credit cycle"),
]


def ist_today() -> date_cls:
    return (datetime.utcnow() + timedelta(hours=5, minutes=30)).date()


def safe_slug(symbol: str) -> str:
    return symbol.replace(" ", "_").replace("/", "_")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="Focus date YYYY-MM-DD. Default: today IST.")
    ap.add_argument("--tf", default="daily", help="Timeframe: daily|weekly|30min. Default daily.")
    ap.add_argument("--retry", type=int, default=2, help="Retry per chart on failure.")
    args = ap.parse_args()

    target = date_cls.fromisoformat(args.date) if args.date else ist_today()
    focus = target.isoformat()
    print(f"[session-charts] target={focus} tf={args.tf}")

    manifest = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "focus_date": focus,
        "tf": args.tf,
        "charts": {},
    }

    success, fail = 0, 0
    for symbol, caption in SESSION_INDICES:
        slug = safe_slug(symbol)
        attempt = 0
        last_err = None
        while attempt <= args.retry:
            attempt += 1
            try:
                meta = capture_chart(symbol, args.tf, focus_date=focus)
                rel = "/" + os.path.relpath(meta["out_path"], ROOT)
                manifest["charts"][slug] = {
                    "symbol": symbol,
                    "caption": caption,
                    "path": rel,
                    "size_bytes": meta.get("size_bytes", 0),
                    "method": meta.get("method"),
                }
                print(f"  ✓ {symbol:25s} → {rel}  ({meta.get('size_bytes', 0)} bytes)")
                success += 1
                break
            except Exception as e:
                last_err = str(e)
                if attempt > args.retry:
                    print(f"  ✗ {symbol:25s} FAIL after {attempt} attempts: {e}", file=sys.stderr)
                    fail += 1
                else:
                    print(f"  ↻ {symbol:25s} retry {attempt}/{args.retry}: {e}", file=sys.stderr)
                    time.sleep(2 * attempt)
        if last_err and slug not in manifest["charts"]:
            manifest["charts"][slug] = {"symbol": symbol, "caption": caption, "error": last_err}

    manifest_dir = ROOT / "public" / "charts" / "_manifest"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / f"{focus}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    latest_path = manifest_dir / "latest.json"
    latest_path.write_text(json.dumps(manifest, indent=2))

    print(f"\n[session-charts] manifest → {manifest_path}")
    print(f"[session-charts] {success} captured · {fail} failed")
    return 0 if fail == 0 else 0  # always 0 for now; failures don't break composers


if __name__ == "__main__":
    raise SystemExit(main())

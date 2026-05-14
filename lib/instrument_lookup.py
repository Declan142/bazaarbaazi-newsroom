#!/usr/bin/env python3
"""Build symbol → instrument-token map from your data provider.

ADAPT this for your source. Pattern: fetch a CSV/JSON list of all
instruments, filter to what you care about (equities + indices),
cache the result. The newsroom uses this to build chart URLs.

Env vars:
    INSTRUMENTS_CSV_URL   CSV endpoint (replace with your provider's URL)
    INSTRUMENTS_CACHE     Local cache path (defaults to ./_runtime/cache/instruments.json)
"""
import csv
import json
import os
import urllib.request
from pathlib import Path

CACHE = Path(os.environ.get("INSTRUMENTS_CACHE", "./_runtime/cache/instruments.json"))
CSV_URL = os.environ.get("INSTRUMENTS_CSV_URL", "")


def build_map(force: bool = False) -> dict:
    """Build {symbol: {token, exchange, name, segment}} map.

    Default implementation expects a CSV with columns:
        tradingsymbol, exchange, segment, instrument_type, instrument_token, name

    Replace logic below for your provider's schema.
    """
    if CACHE.exists() and not force:
        return json.loads(CACHE.read_text())

    if not CSV_URL:
        print("INSTRUMENTS_CSV_URL not set; returning empty map.")
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text("{}")
        return {}

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    print(f"Fetching instruments CSV from {CSV_URL} ...")
    csv_text = urllib.request.urlopen(CSV_URL, timeout=60).read().decode("utf-8")
    rdr = csv.DictReader(csv_text.splitlines())

    out = {}
    for row in rdr:
        sym = row.get("tradingsymbol") or row.get("symbol")
        ex = row.get("exchange", "")
        seg = row.get("segment", "")
        instr_type = row.get("instrument_type", "")
        token = row.get("instrument_token") or row.get("token")
        if not (sym and token):
            continue
        # ADAPT this filter to your market (NSE EQ + indices shown as example)
        if ex == "NSE" and instr_type == "EQ" and seg in ("NSE", "INDICES"):
            out[sym] = {
                "token": int(token),
                "exchange": ex,
                "name": row.get("name", sym),
                "segment": seg,
            }

    # Convenience aliases for common index names
    for canonical, short in [("NIFTY 50", "NIFTY"), ("NIFTY BANK", "BANKNIFTY")]:
        if canonical in out:
            out[short] = out[canonical]

    CACHE.write_text(json.dumps(out, indent=2))
    print(f"Mapped {len(out)} instruments to {CACHE}")
    return out


def get_token(symbol: str) -> int:
    m = build_map()
    if symbol not in m:
        raise KeyError(f"Symbol not in instrument map: {symbol}")
    return m[symbol]["token"]


if __name__ == "__main__":
    import sys
    m = build_map(force="--force" in sys.argv)
    print(f"Total instruments mapped: {len(m)}")

#!/usr/bin/env python3
"""
Generic chart-capture via Playwright. Loads a chart URL (broker, TradingView,
or any chart embed), waits for render, dismisses modals, screenshots the
chart iframe (falls back to viewport screenshot if iframe not found).

ADAPT chart_url() for your data source. Default points to a generic
TradingView-style symbol page; replace with your broker's chart endpoint.

Env vars:
    CHARTS_OUT_DIR  (defaults to ./public/charts)
    CHART_BASE_URL  (optional, e.g. https://www.tradingview.com/symbols)

Usage:
    python chart_capture.py NIFTY daily
    python chart_capture.py NIFTY daily 2026-05-14
"""
import os
import sys
import time
import json
from pathlib import Path
from datetime import date, datetime

from playwright.sync_api import sync_playwright

from data_session import ensure_session
from instrument_lookup import get_token

CHARTS_ROOT = Path(os.environ.get("CHARTS_OUT_DIR", "./public/charts"))
CHARTS_ROOT.mkdir(parents=True, exist_ok=True)
CHART_BASE_URL = os.environ.get("CHART_BASE_URL", "https://www.tradingview.com/symbols")


def chart_url(symbol: str, exchange: str = "NSE") -> str:
    """Build chart URL for symbol+exchange.

    ADAPT THIS for your data source. Examples:
    - TradingView:  https://www.tradingview.com/symbols/NSE-RELIANCE/
    - Generic TVC:  https://your-broker.example.com/chart/{exchange}/{symbol}/{token}
    """
    try:
        token = get_token(symbol)
    except KeyError:
        token = None
    if token:
        return f"{CHART_BASE_URL}/{exchange}/{symbol}/{token}"
    return f"{CHART_BASE_URL}/{exchange}-{symbol}/"


def dismiss_modals(page) -> None:
    """Aggressively dismiss any blocking modals/overlays."""
    selectors = [
        'button:has-text("I understand")',
        'button:has-text("Got it")',
        'button:has-text("Continue")',
        'button:has-text("Skip")',
        'button:has-text("Close")',
        'button[aria-label="Close"]',
        'button.dismiss-modal',
        'div.modal button[type="button"]',
    ]
    for sel in selectors:
        try:
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                btn.click()
                time.sleep(0.6)
        except Exception:
            continue


def safe_path_slug(symbol: str) -> str:
    """Web-friendly directory name for the captured chart."""
    return symbol.replace(" ", "_").replace("/", "_")


def capture_chart(symbol: str, tf: str, focus_date: str = None,
                  exchange: str = "NSE") -> dict:
    """Open chart for symbol+tf, screenshot, return meta."""
    out_dir = CHARTS_ROOT / safe_path_slug(symbol) / tf
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{focus_date or date.today().isoformat()}.png"
    out_path = out_dir / fname

    state_file = ensure_session()
    url = chart_url(symbol, exchange)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled",
                  "--force-color-profile=srgb",
                  "--hide-scrollbars"]
        )
        ctx = browser.new_context(
            storage_state=state_file,
            viewport={"width": 1600, "height": 900},
            device_scale_factor=2,
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        )
        page = ctx.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3.0)
            dismiss_modals(page)
            time.sleep(2.0)
            dismiss_modals(page)
            time.sleep(3.0)

            chart_locator = page.locator(
                'iframe[src*="tradingview"], iframe[id*="chart"], '
                'iframe[name*="chart"], div.chart-container, '
                'div#chart-container'
            ).first
            shot_taken = False
            try:
                if chart_locator.count() > 0:
                    chart_locator.screenshot(path=str(out_path), timeout=10000)
                    shot_taken = True
            except Exception:
                pass

            if not shot_taken:
                page.screenshot(path=str(out_path), full_page=False)

            meta = {
                "symbol": symbol, "exchange": exchange, "tf": tf,
                "focus_date": focus_date,
                "captured_at": datetime.now().isoformat(),
                "url": url,
                "out_path": str(out_path),
                "size_bytes": out_path.stat().st_size if out_path.exists() else 0,
                "method": "iframe" if shot_taken else "fullviewport",
            }

            ctx.close()
            browser.close()
            return meta
        except Exception as e:
            try:
                page.screenshot(path=str(out_dir / f"FAIL_{fname}"))
            except Exception:
                pass
            ctx.close()
            browser.close()
            raise RuntimeError(f"Capture failed for {symbol}/{tf}: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: chart_capture.py SYMBOL {weekly|daily|30min} [focus_date]")
        sys.exit(1)
    symbol = sys.argv[1].upper()
    tf = sys.argv[2]
    focus = sys.argv[3] if len(sys.argv) > 3 else None
    print(json.dumps(capture_chart(symbol, tf, focus_date=focus), indent=2))

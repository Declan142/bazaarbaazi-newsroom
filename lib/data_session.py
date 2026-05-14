#!/usr/bin/env python3
"""
Persistent browser-session manager for data sources that require login.
Generic Playwright wrapper - adapt the login flow for your data source
(broker, screener, paid data vendor, etc.).

The newsroom uses this to keep a logged-in session warm so chart captures
and intraday probes run without re-authenticating on every call.

Env vars:
    DATA_SOURCE_USER_ID     (required)
    DATA_SOURCE_PASSWORD    (required)
    DATA_SOURCE_TOTP_SECRET (optional, if 2FA enabled)
    DATA_SOURCE_LOGIN_URL   (required, e.g. https://your-broker.example.com/)
    DATA_SOURCE_HOME_REGEX  (regex, e.g. r".*your-broker.*/(dashboard|chart).*")
    SESSION_DIR             (defaults to ./_runtime/data-profile)

Adapt the FIELD SELECTORS in fresh_login() for your provider.
The skeleton handles: form login, TOTP, modal-dismissal, storage-state cache,
and validity probes.
"""
import os
import sys
import json
import time
import re
from pathlib import Path

# pyotp + playwright are optional - install only if your source needs them
try:
    import pyotp
except ImportError:
    pyotp = None
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

USER_ID = os.environ.get("DATA_SOURCE_USER_ID", "")
PASSWORD = os.environ.get("DATA_SOURCE_PASSWORD", "")
TOTP_SECRET = os.environ.get("DATA_SOURCE_TOTP_SECRET", "")
LOGIN_URL = os.environ.get("DATA_SOURCE_LOGIN_URL", "https://example.com/")
HOME_REGEX = os.environ.get("DATA_SOURCE_HOME_REGEX", r".*example\.com/(dashboard|home).*")

SESSION_DIR = Path(os.environ.get("SESSION_DIR", "./_runtime/data-profile"))
STATE_FILE = SESSION_DIR / "storage_state.json"
SESSION_DIR.mkdir(parents=True, exist_ok=True)


def fresh_login(headless: bool = True) -> dict:
    """Full login flow. ADAPT the selectors below for your data source."""
    if not (USER_ID and PASSWORD):
        raise RuntimeError("DATA_SOURCE_USER_ID and DATA_SOURCE_PASSWORD must be set.")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            viewport={"width": 1600, "height": 900},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        )
        page = ctx.new_page()

        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
        time.sleep(1.5)

        # ADAPT: replace these selectors for your provider's form
        page.fill('input#userid, input[name="username"]', USER_ID)
        time.sleep(0.7)
        page.fill('input#password, input[name="password"]', PASSWORD)
        time.sleep(0.5)
        page.click('button[type="submit"]')

        # Optional TOTP
        if TOTP_SECRET:
            if not pyotp:
                raise RuntimeError("pyotp not installed but TOTP_SECRET is set. pip install pyotp")
            page.wait_for_selector(
                'input[autocomplete="one-time-code"], input[type="number"], input.totp-input',
                timeout=15000,
            )
            time.sleep(1.0)
            code = pyotp.TOTP(TOTP_SECRET).now()
            for sel in [
                'input[autocomplete="one-time-code"]',
                'input[type="number"][maxlength="6"]',
                'input.totp-input',
                'input#totp',
            ]:
                if page.query_selector(sel):
                    page.fill(sel, code)
                    break
            time.sleep(1.0)
            try:
                page.click('button[type="submit"]', timeout=3000)
            except Exception:
                pass

        # Wait for post-login destination
        page.wait_for_url(re.compile(HOME_REGEX), timeout=20000)
        time.sleep(3.0)

        # ADAPT: dismiss any first-time modals (T&C, tours, etc.)
        for sel in [
            'button:has-text("I understand")',
            'button:has-text("Continue")',
            'button:has-text("Got it")',
            'button:has-text("Skip")',
            'button[aria-label="Close"]',
        ]:
            try:
                btn = page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click()
                    time.sleep(0.7)
            except Exception:
                pass

        time.sleep(2.0)
        ctx.storage_state(path=str(STATE_FILE))
        ctx.close()
        browser.close()
        return {"status": "ok", "state_file": str(STATE_FILE)}


def session_valid(probe_path: str = "/dashboard") -> bool:
    """Probe a logged-in URL to check session validity."""
    if not STATE_FILE.exists():
        return False
    probe_url = LOGIN_URL.rstrip("/") + probe_path
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            storage_state=str(STATE_FILE),
            viewport={"width": 1600, "height": 900},
        )
        page = ctx.new_page()
        try:
            page.goto(probe_url, wait_until="domcontentloaded", timeout=20000)
            time.sleep(2)
            valid = "login" not in page.url
            ctx.close()
            browser.close()
            return valid
        except Exception:
            ctx.close()
            browser.close()
            return False


def ensure_session() -> str:
    if session_valid():
        return str(STATE_FILE)
    print("Session invalid or missing, running fresh login...")
    fresh_login(headless=True)
    return str(STATE_FILE)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "test"
    if cmd == "login":
        print(json.dumps(fresh_login(headless=True), indent=2))
    elif cmd == "test":
        print(f"Session valid: {session_valid()}")
    elif cmd == "ensure":
        print(f"Session ready at: {ensure_session()}")
    else:
        print("Usage: data_session.py {login|test|ensure}")
        sys.exit(1)

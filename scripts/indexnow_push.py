#!/usr/bin/env python3
"""
IndexNow push client.

Bing IndexNow protocol: POST one or more URLs to https://api.indexnow.org/indexnow
with a host-bound key. The key file lives at public/<KEY>.txt and contains the key
verbatim. Bing, Yandex, Naver, Seznam consume the same endpoint; Google does not
participate but Bing's index feeds ChatGPT Search, Copilot, DuckDuckGo, Brave.

Env vars:
    NEWSROOM_HOST  Your site hostname, e.g. "example.com"
    NEWSROOM_ROOT  Repo root (defaults to script's parent dir)

Usage:
    python3 scripts/indexnow_push.py --urls https://example.com/foo/,https://example.com/bar/
    python3 scripts/indexnow_push.py --all                 # parse out/sitemap.xml
    python3 scripts/indexnow_push.py --all --dry-run       # print, do not POST
    python3 scripts/indexnow_push.py --since 2026-05-14    # only URLs with lastmod >= date

Exit 0 on 200/202, non-zero otherwise.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET


REPO_ROOT = Path(os.environ.get("NEWSROOM_ROOT", Path(__file__).resolve().parent.parent))
HOST = os.environ.get("NEWSROOM_HOST", "example.com")
INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"
USER_AGENT = f"Mozilla/5.0 Newsroom/IndexNow ({HOST})"


def discover_key() -> tuple[str, str]:
    """Return (key, keyLocation) by scanning public/<32-hex>.txt files.

    IndexNow spec: the file's NAME (minus .txt) IS the key, and its content
    must match. We trust the filename and confirm content matches.
    """
    public = REPO_ROOT / "public"
    pattern = re.compile(r"^([0-9a-fA-F]{8,128})\.txt$")
    for f in sorted(public.glob("*.txt")):
        m = pattern.match(f.name)
        if not m:
            continue
        key = m.group(1)
        try:
            body = f.read_text().strip()
        except OSError:
            continue
        if body == key:
            return key, f"https://{HOST}/{f.name}"
    raise SystemExit(
        "no IndexNow key file found in public/ (expected <hex>.txt with body = filename)"
    )


def urls_from_sitemap(sitemap_path: Path) -> list[str]:
    """Extract <loc> values from a sitemap.xml file."""
    if not sitemap_path.exists():
        raise SystemExit(f"sitemap not found: {sitemap_path}")
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    tree = ET.parse(sitemap_path)
    root = tree.getroot()
    locs = [el.text.strip() for el in root.findall("sm:url/sm:loc", ns) if el.text]
    return locs


def filter_since(urls: list[str], sitemap_path: Path, since_iso: str) -> list[str]:
    """Filter to URLs whose <lastmod> is >= since_iso (YYYY-MM-DD)."""
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    tree = ET.parse(sitemap_path)
    root = tree.getroot()
    keep = []
    cutoff = since_iso
    for url_el in root.findall("sm:url", ns):
        loc_el = url_el.find("sm:loc", ns)
        lm_el = url_el.find("sm:lastmod", ns)
        if loc_el is None or loc_el.text is None:
            continue
        loc = loc_el.text.strip()
        if loc not in urls:
            continue
        if lm_el is None or lm_el.text is None:
            keep.append(loc)
            continue
        lm = lm_el.text.strip()[:10]
        if lm >= cutoff:
            keep.append(loc)
    return keep


def chunk(seq: list[str], n: int):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def push(urls: list[str], key: str, key_location: str, dry_run: bool = False) -> int:
    """POST urls to IndexNow in batches of 10000. Returns 0 on success."""
    if not urls:
        print("no URLs to push", file=sys.stderr)
        return 0
    print(f"host={HOST} key={key[:8]}... urls={len(urls)} dry_run={dry_run}")
    rc = 0
    for batch in chunk(urls, 10000):
        payload = {
            "host": HOST,
            "key": key,
            "keyLocation": key_location,
            "urlList": batch,
        }
        body = json.dumps(payload).encode("utf-8")
        if dry_run:
            print(f"[dry-run] would POST {len(batch)} URLs; first 5:")
            for u in batch[:5]:
                print(f"  {u}")
            continue
        req = urllib.request.Request(
            INDEXNOW_ENDPOINT,
            data=body,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                code = resp.status
                print(f"  POST {len(batch)} URLs -> HTTP {code}")
                if code not in (200, 202):
                    rc = 1
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code} {e.reason}: {e.read().decode('utf-8', 'replace')[:300]}")
            rc = 1
        except urllib.error.URLError as e:
            print(f"  URLError: {e.reason}")
            rc = 1
    return rc


def main() -> int:
    p = argparse.ArgumentParser(description="IndexNow push for BazaarBaazi")
    p.add_argument("--urls", help="comma-separated URL list")
    p.add_argument(
        "--all",
        action="store_true",
        help="push every URL from out/sitemap.xml",
    )
    p.add_argument(
        "--since",
        help="when used with --all, only URLs with lastmod >= YYYY-MM-DD",
    )
    p.add_argument("--dry-run", action="store_true", help="print, do not POST")
    args = p.parse_args()

    if not args.urls and not args.all:
        p.error("either --urls or --all required")

    key, key_location = discover_key()

    urls: list[str] = []
    if args.urls:
        urls = [u.strip() for u in args.urls.split(",") if u.strip()]
    if args.all:
        sitemap = REPO_ROOT / "out" / "sitemap.xml"
        urls = urls_from_sitemap(sitemap)
        if args.since:
            urls = filter_since(urls, sitemap, args.since)

    return push(urls, key, key_location, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())

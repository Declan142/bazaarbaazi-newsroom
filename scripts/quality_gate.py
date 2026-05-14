#!/usr/bin/env python3
"""
Stage F: 16-point quality gate linter.
Runs on every .md article in content/lookback/. ANY fail → REJECT to revision queue.

Usage:
    python scripts/quality-gate.py                    # lint all
    python scripts/quality-gate.py --bucket stock-story
    python scripts/quality-gate.py --strict           # fail on any warning
    python scripts/quality-gate.py --report only      # just produce report, don't move files
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(os.environ.get("NEWSROOM_ROOT", Path(__file__).resolve().parent.parent))
LOOKBACK = ROOT / "content" / "lookback"
CHARTS_ROOT = ROOT / "public" / "charts"
REVISION_QUEUE = ROOT / "_runtime" / "revision-queue.json"
PASSED = ROOT / "_runtime" / "quality-passed.json"

# Hinglish particle blacklist (body, not chrome) — STRICT: only words that
# would never legitimately appear in pure English finance writing.
HINGLISH_PARTICLES = re.compile(
    r'\b(yeh|yahaan|wahaan|iska|uska|inka|unka|kya|kyun|kyu|wagairah|wagera|'
    r'vagairah|vagera|nahi|nahin|kabhi|abhi|accha|achha|bahut|toh|jaise|'
    r'lekin|magar|aur|chahiye|chahiyye|bilkul|sahi|theek|haan|thoda|zyada|'
    r'kaafi|kuchh|kuch|sab|matlab|thi|thii|gaya|gayi|hua|hue|aaya|aayi|'
    r'kiya|kara|chala|chali|jaane|jaaye|baith|baitha|liya|li|hota|hoti|'
    r'thaa|hain\s|jaata|jaati|raha|rahi|raha\s+hai|rahi\s+hai)\b',
    flags=re.IGNORECASE,
)
# Allow these in chrome only (titles, brand strings) — not in body
EM_DASH_CHARS = re.compile(r'[—–‒]')


def head_status(url: str, timeout: int = 5) -> int:
    try:
        req = Request(url, method='HEAD',
                      headers={'User-Agent': 'BazaarBaazi-QualityGate/1.0'})
        with urlopen(req, timeout=timeout) as r:
            return r.status
    except HTTPError as e:
        return e.code
    except (URLError, Exception):
        return 0


def parse_article(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding='utf-8')
    if not text.startswith('---\n'):
        return {}, text
    try:
        end = text.index('\n---\n', 4)
        fm = yaml.safe_load(text[4:end])
        body = text[end + 5:]
        return fm or {}, body
    except (ValueError, yaml.YAMLError):
        return {}, text


def lint_article(path: Path) -> dict:
    """Run 16-point check. Return {path, fails: [...], warns: [...], passed: bool}."""
    fm, body = parse_article(path)
    fails = []
    warns = []
    word_count = len(re.findall(r'\b\w+\b', body))

    # 1. Word count >= 1500
    if word_count < 1500:
        fails.append(f"01_word_count_{word_count}")

    # 2. 3 chart PNGs present (file_size > 50KB) — soft 50KB to allow legit smaller charts
    chart_paths = fm.get('charts', [])
    if len(chart_paths) < 3:
        fails.append(f"02_charts_listed_{len(chart_paths)}")
    else:
        for cp in chart_paths[:3]:
            full = ROOT / "public" / cp.lstrip('/')
            if not full.exists() or full.stat().st_size < 50_000:
                warns.append(f"02_chart_missing_or_thin: {cp}")

    # 3. All internal links resolve (within content/lookback or public/) — best-effort
    internal_links = re.findall(r'\]\((/[^)]+)\)', body)
    for link in internal_links[:10]:
        if link.startswith('/charts/'):
            continue  # already checked
        full = ROOT / "public" / link.lstrip('/')
        if not full.exists() and not (ROOT / "out" / link.lstrip('/')).exists():
            warns.append(f"03_internal_link_broken: {link}")

    # 4. External links 200 OK (sample first 5 to avoid slowness)
    external_links = re.findall(r'\]\((https?://[^)]+)\)', body)[:5]
    if external_links:
        with ThreadPoolExecutor(max_workers=5) as ex:
            statuses = list(ex.map(head_status, external_links))
        for url, st in zip(external_links, statuses):
            if st >= 400 or st == 0:
                warns.append(f"04_external_link_{st}: {url[:60]}")

    # 5. Citations near numeric claims — detect naked %s/figures, soft warning if too many
    naked_pcts = re.findall(r'(\d+(?:\.\d+)?%)', body)
    if len(naked_pcts) > 12:
        warns.append(f"05_many_naked_percents_{len(naked_pcts)}")

    # 6. (skipped — OHLC reconcile would need data fetch; defer to manual)

    # 7. Em-dash count = 0 in body AND in frontmatter title (gate hole found 2026-05-12 cold-read)
    em_dashes = EM_DASH_CHARS.findall(body)
    if em_dashes:
        fails.append(f"07_em_dash_count_{len(em_dashes)}")
    title_str = str(fm.get('title', ''))
    title_em = EM_DASH_CHARS.findall(title_str)
    if title_em:
        fails.append(f"07b_em_dash_in_title_{len(title_em)}: {title_str[:80]!r}")

    # 8. Hinglish particles in body
    hinglish_hits = HINGLISH_PARTICLES.findall(body)
    if len(hinglish_hits) > 2:  # tolerate up to 2 (could be quotes / proper nouns)
        fails.append(f"08_hinglish_particles_{len(hinglish_hits)}: {set(hinglish_hits[:5])}")

    # 9. Past-tense framing — soft check: presence of past-tense verbs + absence of "now is/are"
    if fm.get('lookback'):
        present_leak = len(re.findall(r'\b(currently|right now|as of today|today\'s)\b', body, re.IGNORECASE))
        if present_leak > 3:
            warns.append(f"09_present_tense_leak_{present_leak}")

    # 10. Verdict block present
    if not re.search(r'(?im)^##?\s*verdict|VERDICT', body):
        fails.append("10_no_verdict_block")

    # 11. Byline = Aditya Sharma
    author = fm.get('author', {})
    if isinstance(author, dict):
        if author.get('name', '').lower() != 'aditya sharma':
            fails.append(f"11_byline_wrong_{author.get('name')}")
        if not author.get('x'):
            warns.append("11_no_x_handle")
        if not author.get('linkedin'):
            warns.append("11_no_linkedin")
    else:
        fails.append(f"11_author_not_dict")

    # 12. Disclosure footer present
    if not fm.get('disclosure') and 'editorial AI tool' not in body.lower():
        fails.append("12_no_disclosure")

    # 13. JSON-LD prep: required fm fields
    required_fm = ['title', 'slug', 'bucket', 'datePublished', 'author', 'lookback']
    for k in required_fm:
        if not fm.get(k):
            fails.append(f"13_missing_fm_{k}")

    # 14. OG image — defer (built at site-build time)

    # 15. Per-chart alt text (caption follows image)
    img_pattern = re.findall(r'!\[([^\]]*)\]\(([^)]+)\)', body)
    bare_imgs = [(alt, src) for alt, src in img_pattern if len(alt) < 8]
    if len(bare_imgs) > 0:
        warns.append(f"15_bare_chart_alt_{len(bare_imgs)}")

    # 16. (Phrase overlap — skip, would need corpus embedding; defer to dedicated pass)

    return {
        "path": str(path),
        "slug": fm.get("slug", path.stem),
        "bucket": fm.get("bucket", path.parent.name),
        "word_count": word_count,
        "fails": fails,
        "warns": warns,
        "passed": len(fails) == 0,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket", default=None)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--report", default="full", choices=["full", "only"])
    args = ap.parse_args()

    pattern = f"{args.bucket}/*.md" if args.bucket else "*/*.md"
    files = sorted(LOOKBACK.glob(pattern))
    print(f"Linting {len(files)} articles...")

    results = []
    for f in files:
        results.append(lint_article(f))

    passed = [r for r in results if r["passed"] and (not args.strict or not r["warns"])]
    failed = [r for r in results if not r["passed"] or (args.strict and r["warns"])]

    REVISION_QUEUE.write_text(json.dumps(failed, indent=2, default=str))
    PASSED.write_text(json.dumps([r["path"] for r in passed], indent=2))

    print()
    print(f"=== QUALITY GATE COMPLETE ===")
    print(f"Total:  {len(results)}")
    print(f"PASSED: {len(passed)} → {PASSED}")
    print(f"FAILED: {len(failed)} → {REVISION_QUEUE}")
    print()

    by_bucket_pass = {}
    by_bucket_fail = {}
    for r in passed:
        by_bucket_pass[r["bucket"]] = by_bucket_pass.get(r["bucket"], 0) + 1
    for r in failed:
        by_bucket_fail[r["bucket"]] = by_bucket_fail.get(r["bucket"], 0) + 1
    buckets = sorted(set(list(by_bucket_pass) + list(by_bucket_fail)))
    print(f"{'bucket':25s} pass  fail")
    for b in buckets:
        print(f"  {b:23s} {by_bucket_pass.get(b,0):4d}  {by_bucket_fail.get(b,0):4d}")

    if failed:
        print(f"\nFirst 5 fail samples:")
        for r in failed[:5]:
            print(f"  {r['slug']}  fails={r['fails']}")


if __name__ == "__main__":
    main()

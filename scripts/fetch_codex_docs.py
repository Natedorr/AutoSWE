#!/usr/bin/env python3
"""
Fetch all Codex documentation pages and save as clean markdown in docs/codex/.

The Codex docs moved from developers.openai.com/codex to learn.chatgpt.com/docs
(October 2026). That site publishes clean markdown at <slug>.md URLs and a
compact index at https://learn.chatgpt.com/docs/llms.txt ("compact map of
ChatGPT docs for Codex"). This script downloads every page from that index,
preserving the sub-path structure under docs/codex/.

Pages with a ?surface= query parameter are disambiguated with a
`-<surface>` suffix (e.g. developer-commands.md?surface=cli ->
developer-commands-cli.md).

Meta files (llms-full.txt, use-cases/llms.txt) are skipped; codex-manual.md is kept.

Usage:
    python scripts/fetch_codex_docs.py           # Full run (overwrite)
    python scripts/fetch_codex_docs.py --dry-run # List URLs only
    python scripts/fetch_codex_docs.py --skip-existing
"""

import argparse
import os
import re
import sys
import time
import urllib.parse
import urllib.request

LLMS_URL = "https://learn.chatgpt.com/docs/llms.txt"
BASE_URL = "https://learn.chatgpt.com/docs"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "codex")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "AutoSWE-docs-fetch/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        print(f"    ! fetch failed: {url} ({e})")
        return None


def collect_urls():
    llms = fetch(LLMS_URL)
    if not llms:
        print("Failed to fetch index:", LLMS_URL)
        return []
    urls = re.findall(r"\(https://learn\.chatgpt\.com/docs/[^)\s]+\.md[^)\s]*\)", llms)
    urls = [u[1:-1] for u in urls]
    out, seen = [], set()
    for u in urls:
        if "llms-full" in u or u.endswith("/llms.txt"):
            continue
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def url_to_target(url):
    parts = urllib.parse.urlsplit(url)
    rel = url.split("?", 1)[0].replace(BASE_URL + "/", "")
    if parts.query:
        surface = urllib.parse.parse_qs(parts.query).get("surface", ["raw"])[0]
        rel = re.sub(r"\.md$", "", rel) + f"-{surface}.md"
    return os.path.join(OUTPUT_DIR, *rel.split("/"))


def main():
    parser = argparse.ArgumentParser(description="Fetch all Codex docs from learn.chatgpt.com")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--delay", type=float, default=0.3)
    args = parser.parse_args()

    urls = collect_urls()
    if not urls:
        return 1
    print(f"Found {len(urls)} Codex doc pages\n" + "=" * 70)

    ok, skipped, failed = 0, 0, []
    for url in urls:
        target = url_to_target(url)
        display = os.path.relpath(target, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        if args.dry_run:
            print(f"  {display}")
            continue
        if args.skip_existing and os.path.exists(target) and os.path.getsize(target) > 100:
            skipped += 1
            print(f"[skip] {display}")
            continue
        print(f"Fetching: {display}")
        md = fetch(url)
        if not md or len(md) < 50:
            print("  FAIL")
            failed.append(url)
            continue
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(f"# Source: {url}\n\n")
            f.write(md if md.endswith("\n") else md + "\n")
        ok += 1
        time.sleep(args.delay)

    print("\n" + "=" * 70)
    print(f"Fetched: {ok}  Skipped: {skipped}  Failed: {len(failed)}")
    for u in failed:
        print("  FAIL:", u)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

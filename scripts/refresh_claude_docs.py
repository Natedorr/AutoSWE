#!/usr/bin/env python3
"""
Refresh the cloned Claude Code / Agent SDK docs in docs/claude-agent-sdk/
from https://code.claude.com/docs (clean markdown at <path>.md URLs).

Local files mirror upstream: docs/claude-agent-sdk/<rel>.md
  <-> https://code.claude.com/docs/en/<rel>.md

Files that 404 are matched against the llms.txt index by title; if found
there, the local file is refreshed from the new URL.

Usage:
    python scripts/refresh_claude_docs.py            # Refresh all files
    python scripts/refresh_claude_docs.py --dry-run  # Report status only
"""

import argparse
import os
import re
import sys
import urllib.request

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "claude-agent-sdk")
UPSTREAM = "https://code.claude.com/docs/en"
LLMS = "https://code.claude.com/docs/llms.txt"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "AutoSWE-docs-refresh/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError:
        return None


def local_files():
    out = []
    for root, _dirs, names in os.walk(BASE_DIR):
        for n in sorted(names):
            if n.endswith(".md"):
                rel = os.path.relpath(os.path.join(root, n), BASE_DIR).replace(os.sep, "/")
                out.append(rel)
    return sorted(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--add-missing", action="store_true",
                        help="Also download upstream pages that have no local file")
    args = parser.parse_args()

    index = fetch(LLMS) or ""
    index_map = {}
    for m in re.finditer(r"\[([^\]]+)\]\((https://code\.claude\.com/docs/[^)]+)\):", index):
        index_map[m.group(1).lower()] = m.group(2)

    ok, moved, fail, local_urls = 0, [], [], set()

    for rel in local_files():
        path = os.path.join(BASE_DIR, rel)
        with open(path, encoding="utf-8") as f:
            local_title = next((l.lstrip("# ").strip() for l in f if l.startswith("# ")), "")
        url = UPSTREAM + "/" + rel
        md = fetch(url)
        if md is not None and len(md) > 50:
            local_urls.add(url)
            if not args.dry_run:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(md if md.endswith("\n") else md + "\n")
            ok += 1
            continue
        # 404: try title match in the index
        hit = index_map.get(local_title.lower())
        if hit:
            md2 = fetch(hit)
            if md2 is not None and len(md2) > 50:
                if not args.dry_run:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(md2 if md2.endswith("\n") else md2 + "\n")
                ok += 1
                moved.append((rel, url, hit))
                continue
        fail.append(rel)

    missing = [u for u in re.findall(r"(https://code\.claude\.com/docs/en/[^\s)]+\.md)", index)
               if u not in local_urls]

    print(f"Refreshed: {ok}  Moved: {len(moved)}  Failed: {len(fail)}")
    for rel, old, new in moved:
        print(f"  moved: {rel} ({old} -> {new})")
    for rel in fail:
        print(f"  FAIL: {rel}")
    if missing:
        print(f"\nUpstream pages with no local counterpart ({len(missing)}):")
        for u in missing:
            print(f"  {u}")
            if args.add_missing and not args.dry_run:
                md = fetch(u)
                if md and len(md) > 50:
                    rel = u.replace(UPSTREAM + "/", "")
                    dest = os.path.join(BASE_DIR, rel)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with open(dest, "w", encoding="utf-8") as f:
                        f.write(md if md.endswith("\n") else md + "\n")
                    print(f"  + downloaded -> docs/claude-agent-sdk/{rel}")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())

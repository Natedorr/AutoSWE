#!/usr/bin/env python3
"""
Refresh the cloned GitHub API reference in docs/github-api/ from docs.github.com.

Each topic file starts with a '# <title>' line and a 'Source: <url>' line.
docs.github.com serves clean markdown at <url>.md. The script rewrites each
local file with the matching section of the latest upstream page, preserving
the local layout (H1 title + Source line + upstream section).

Files whose title matches the upstream page's H1 are refreshed with the full
page (they are whole-page clones).

Usage:
    python scripts/refresh_github_docs.py            # Refresh all files
    python scripts/refresh_github_docs.py --dry-run  # Report matches only
"""

import argparse
import os
import re
import sys
import urllib.request

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "github-api")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "AutoSWE-docs-refresh/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        print(f"    ! fetch failed: {url} ({e})")
        return None


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def split_h2(md):
    """Return list of (title, section_text) for each H2 section (incl. heading)."""
    lines = md.splitlines()
    sections = []
    current = None
    for line in lines:
        if line.startswith("## ") and not line.startswith("###"):
            if current:
                sections.append(current)
            current = [line]
        elif current is not None:
            current.append(line)
    if current:
        sections.append(current)
    return [(c[0][3:].strip(), "\n".join(c).rstrip() + "\n") for c in sections]


def score(title, section_title):
    a, b = set(norm(title).split()), set(norm(section_title).split())
    if not a:
        return 0.0
    return len(a & b) / len(a)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    files = sorted(f for f in os.listdir(BASE_DIR) if f.endswith(".md") and f != "README.md")
    ok, fail = 0, []

    for name in files:
        path = os.path.join(BASE_DIR, name)
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
        title = lines[0].lstrip("# ").strip()
        source = next((l.split("Source:", 1)[1].strip() for l in lines if l.startswith("Source:")), None)
        if not source:
            print(f"[skip] {name}: no Source line")
            continue
        page_md = fetch(source + ".md")
        if page_md is None:
            fail.append((name, source, "fetch failed"))
            continue
        page_h1 = next((l.lstrip("# ").strip() for l in page_md.splitlines() if l.startswith("# ")), "")
        sections = split_h2(page_md)
        section_by_norm = {norm(st): (st, txt) for st, txt in sections}

        if norm(title) == norm(page_h1):
            section = page_md  # whole-page clone
            match = "whole page"
        else:
            # Primary key: the local file's own first H2 (its original section heading)
            local_h2 = next((l[3:].strip() for l in lines if l.startswith("## ")), None)
            hit = section_by_norm.get(norm(local_h2)) if local_h2 else None
            if hit is None:
                hit = section_by_norm.get(norm(title))
            if hit is None:
                best, best_score = None, 0.0
                for st, txt in sections:
                    s = score(title, st)
                    if s > best_score:
                        best, best_score = (st, txt), s
                hit = best if best is not None and best_score >= 0.5 else None
                if hit is None and best is not None:
                    print(f"    ? fuzzy: {name} -> {best[0]} (score {best_score:.2f})")
            if hit is None:
                fail.append((name, source, "no matching section"))
                print(f"[!!] {name}: no section match")
                continue
            match = hit[0]
            section = hit[1]

        out = f"# {title}\n\nSource: {source}\n\n{section}"
        if args.dry_run:
            print(f"[ok] {name} -> {source} ({match})")
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(out)
            print(f"[ok] {name} -> {source} ({match})")
        ok += 1

    print(f"\n{'=' * 60}\nRefreshed: {ok}  Failed: {len(fail)}")
    for name, source, why in fail:
        print(f"  FAIL {name} ({source}): {why}")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Fetch all Codex documentation pages from developers.openai.com
and save as cleaned markdown files in docs/codex/.

Usage:
    python3 scripts/fetch_codex_docs.py           # Full run
    python3 scripts/fetch_codex_docs.py --dry-run  # List URLs only
    python3 scripts/fetch_codex_docs.py --skip-existing
    python3 scripts/fetch_codex_docs.py --continue   # Resume from last failure
    python3 scripts/fetch_codex_docs.py --list        # Show doc manifest
"""

import argparse
import os
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

# ── Config ──────────────────────────────────────────────────────────

SITEMAP_URL = "https://developers.openai.com/sitemap-0.xml"
BASE_URL = "https://developers.openai.com"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "codex")
NAMESPACE = "{http://www.sitemaps.org/schemas/sitemap/0.9}"

# Pages to skip — collections, blogs, cookbook notebooks, etc.
SKIP_PATTERNS = [
    r"/blog/",
    r"/cookbook/",
    r"/community/",
    r"/showcase/",
    r"/learn/codex/",
    r"/resources/codex/",
    r"/codex/use-cases/collections/",
    r"/codex/use-cases/tracks/",
    r"/codex/tracks/",
    r"/codex/videos/",
]


# ── Simple HTML → Clean Markdown ────────────────────────────────────

class HTMLToMarkdown(HTMLParser):
    """Minimal HTML-to-markdown converter for doc pages."""

    def __init__(self):
        super().__init__()
        self.parts = []
        self.in_header = False
        self.in_link = False
        self.in_code = False
        self.in_pre = False
        self.in_li = False
        self.in_table = False
        self.in_td = False
        self.in_skip = False  # nav/sidebar/script
        self.link_text = ""
        self.link_url = ""
        self.current_header = 0
        self.skip_tags = {"nav", "script", "style", "header", "footer"}
        self.stack = []  # tag stack for skip tracking

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        self.stack.append(tag)

        # Skip navigation and scripts
        if tag in self.skip_tags:
            self.in_skip = True
            return

        if self.in_skip:
            return

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.in_header = True
            self.current_header = int(tag[1])
            self.parts.append("\n" + "#" * self.current_header + " ")

        elif tag == "a":
            self.in_link = True
            self.link_text = ""
            self.link_url = attrs_dict.get("href", "")

        elif tag == "code":
            self.in_code = True
            self.parts.append("`")

        elif tag == "pre":
            self.in_pre = True
            self.parts.append("\n```")

        elif tag == "strong" or tag == "b":
            self.parts.append("**")

        elif tag == "em" or tag == "i":
            self.parts.append("*")

        elif tag == "p":
            self.parts.append("\n\n")

        elif tag == "br":
            self.parts.append("\n")

        elif tag == "ul":
            self.parts.append("\n")

        elif tag == "ol":
            self.parts.append("\n")

        elif tag == "li":
            self.in_li = True
            self.parts.append("\n- ")

        elif tag == "blockquote":
            self.parts.append("\n> ")

        elif tag == "img":
            alt = attrs_dict.get("alt", "")
            src = attrs_dict.get("src", "")
            if alt:
                self.parts.append(f"[{alt}]({src})")

        elif tag == "table":
            self.in_table = True
            self.parts.append("\n")

        elif tag == "td" or tag == "th":
            self.in_td = True
            if self.parts and self.parts[-1] != "\n":
                self.parts.append(" | ")

        elif tag == "tr":
            if self.parts and self.parts[-1] == "|":
                self.parts.pop()
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        else:
            return  # mismatched tags

        if tag in self.skip_tags:
            self.in_skip = False
            return

        if self.in_skip:
            return

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.in_header = False

        elif tag == "a":
            self.in_link = False
            if self.link_text and self.link_url:
                self.parts.append(f"[{self.link_text.strip()}]({self.link_url})")

        elif tag == "code":
            self.in_code = False
            self.parts.append("`")

        elif tag == "pre":
            self.in_pre = False
            self.parts.append("```\n")

        elif tag == "strong" or tag == "b":
            self.parts.append("**")

        elif tag == "em" or tag == "i":
            self.parts.append("*")

        elif tag == "li":
            self.in_li = False

    def handle_data(self, data):
        if self.in_skip:
            return
        text = data.strip()
        if not text:
            return
        if self.in_header:
            text = re.sub(r'\s+', ' ', text)
        if self.in_link:
            self.link_text += text
        if not self.in_pre:
            text = re.sub(r'\s+', ' ', text)
        self.parts.append(text)

    def get_markdown(self):
        md = "".join(self.parts)
        # Cleanup
        md = re.sub(r'\n{3,}', '\n\n', md)
        md = re.sub(r'\n+#', r'\n\n#', md)
        return md.strip()


# ── Fetch & Parse ───────────────────────────────────────────────────

def fetch_url(url):
    """Fetch a URL and return clean body HTML."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; CodexDocFetcher/1.0)",
            "Accept": "text/html",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError:
        return None


def html_to_markdown(html):
    """Extract main content from HTML and convert to markdown."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")

    # Remove scripts, styles, nav, footer
    for tag in soup(["script", "style", "nav", "footer", "noscript"]):
        tag.decompose()

    # Try to find main content area
    main = soup.find("main") or soup.find("article") or soup.find(class_=re.compile(r"content|article|prose|markdown"))
    if not main:
        main = soup.find("div", class_=re.compile(r"container|wrapper|content"))
    if not main:
        main = soup

    # Remove security notice overlays
    for div in main.find_all(class_=re.compile(r"security|notice|banner|cookie")):
        div.decompose()

    # Convert to markdown
    converter = HTMLToMarkdown()
    converter.feed(str(main))
    return converter.get_markdown()


def url_to_filename(url):
    """Convert URL to a clean filename."""
    # Remove base and trailing slash
    path = url.replace(BASE_URL, "").rstrip("/")

    # Strip the leading /codex/ prefix so files land flat in docs/codex/
    rel = path.lstrip("/")
    if rel.startswith("codex"):
        rel = rel[5:].lstrip("/")
    if rel.startswith("codex/"):
        rel = rel[6:]

    # Split into dir and file
    if "/" in rel:
        parts = rel.rsplit("/", 1)
        subdir = parts[0]
        name = parts[1]
    else:
        subdir = ""
        name = rel

    if not name:
        name = "index"

    return subdir, f"{name}.md"


def should_skip(url):
    """Check if URL matches skip patterns."""
    for pattern in SKIP_PATTERNS:
        if re.search(pattern, url):
            return True
    return False


# ── Main ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fetch all Codex docs from developers.openai.com")
    parser.add_argument("--dry-run", action="store_true", help="List URLs without fetching")
    parser.add_argument("--skip-existing", action="store_true", help="Skip files that already exist")
    parser.add_argument("--continue", action="store_true", dest="continue_run", help="Resume from last failure")
    parser.add_argument("--list", action="store_true", dest="list_only", help="Show doc manifest")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between requests (default: 0.5s)")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Parse sitemap
    print(f"Fetching sitemap: {SITEMAP_URL}")
    sitemap_html = fetch_url(SITEMAP_URL)
    if not sitemap_html:
        print("❌ Failed to fetch sitemap")
        return 1

    root = ET.fromstring(sitemap_html.encode())
    all_urls = [elem.text.strip() for elem in root.iter(f"{NAMESPACE}loc")]

    # Filter to /codex/ URLs only
    codex_urls = [u for u in all_urls if "/codex" in u and not should_skip(u)]
    codex_urls.sort()

    print(f"\nFound {len(codex_urls)} Codex doc URLs (after filtering):")
    print("=" * 70)

    # Build manifest
    manifest = []
    for url in codex_urls:
        subdir, filename = url_to_filename(url)
        display = f"docs/codex/{subdir}/{filename}" if subdir else f"docs/codex/{filename}"
        manifest.append((url, subdir, filename, display))
        print(f"  {display}")

    print(f"\n{'=' * 70}")
    print(f"Total: {len(manifest)} pages to fetch\n")

    if args.list_only:
        return 0

    if args.dry_run:
        print("Dry run complete. Use --skip-existing to resume.")
        return 0

    # Fetch each URL
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    failed = []
    skipped = 0
    fetched = 0

    # Find resume point
    start_idx = 0
    if args.continue_run:
        for idx, (_url, subdir, filename, _display) in enumerate(manifest):
            target_path = os.path.join(OUTPUT_DIR, subdir, filename) if subdir else os.path.join(OUTPUT_DIR, filename)
            if os.path.exists(target_path) and os.path.getsize(target_path) > 100:
                start_idx = idx + 1
            else:
                break
        print(f"Resuming from index {start_idx} ({manifest[start_idx][3] if start_idx < len(manifest) else 'end'})\n")

    for idx, (url, subdir, filename, display) in enumerate(manifest):
        if idx < start_idx:
            skipped += 1
            continue

        target_path = os.path.join(OUTPUT_DIR, subdir, filename) if subdir else os.path.join(OUTPUT_DIR, filename)

        # Skip existing
        if args.skip_existing and os.path.exists(target_path) and os.path.getsize(target_path) > 100:
            skipped += 1
            print(f"[skip] {display}")
            continue

        # Ensure directory
        full_dir = os.path.join(OUTPUT_DIR, subdir) if subdir else OUTPUT_DIR
        os.makedirs(full_dir, exist_ok=True)

        # Fetch
        print(f"[{idx + 1}/{len(manifest)}] Fetching: {display}")
        html = fetch_url(url)

        if html is None:
            print(f"  ❌ Failed to fetch {url}")
            failed.append((url, display))
            continue

        # Convert
        md = html_to_markdown(html)

        if not md or len(md) < 50:
            print(f"  ⚠️  Content too short ({len(md)} chars)")
            failed.append((url, display))
            continue

        # Write
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(f"# Source: {url}\n\n")
            f.write(md)

        fetched += 1
        print(f"  ✅ {display} ({len(md)} chars)")

        # Rate limit
        time.sleep(args.delay)

    # Summary
    print(f"\n{'=' * 70}")
    print("Results:")
    print(f"  Fetched: {fetched}")
    print(f"  Skipped: {skipped}")
    print(f"  Failed:  {len(failed)}")

    if failed:
        print("\nFailed pages:")
        for url, display in failed:
            print(f"  - {display} ({url})")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

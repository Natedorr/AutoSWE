"""GitHub attachment discovery + download (issue #290).

There is no documented REST endpoint for listing issue attachments, so
discovery is a regex over the issue body and every comment body
(``github.com/user-attachments/assets/<uuid>``), and download is one of two
mechanisms (design doc §1.3, both live-verified 2026-10-09):

- **Mechanism A** — ``GET`` the plain URL, following redirects. Works for
  public repos (302 to a pre-signed S3 URL). For private repos this 404s.
- **Mechanism B** — re-fetch the *containing* body with the
  ``application/vnd.github.html+json`` media type and download the
  ``private-user-images.githubusercontent.com/...?jwt=*** URL rendered into
  it. Works for private repos, **but only for embedded-image
  references**; a plain markdown link yields no signed URL at all (the
  documented open gap — warn and skip). The signed URL lives ~300s, so the
  html re-fetch and the download happen in the same operation.

Both are best-effort: any failure logs a warning and the attachment is
skipped. A missing attachment is never a task failure.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib import request

from autoswe.attachments import downloads
from autoswe.core.logging_utils import get_debug_logger

dbg = get_debug_logger()

# Discovery (design doc §1.2): the raw markdown body always carries the plain
# URL for both embedded-image and linked references. 36-char hex/dash UUID.
GITHUB_ASSET_URL_REGEX = r"https?://github\.com/user-attachments/assets/[0-9a-f-]{36}"
ASSET_URL_RE = re.compile(GITHUB_ASSET_URL_REGEX)

# Mechanism B: signed private-image URL rendered into body_html. Slashes are
# allowed — the ``?jwt=*** query segment is base64url and may contain
# ``/``; truncating there yields a 404 on download. The real delimiters are
# quotes, whitespace, angle brackets, and backslashes (GitHub emits these in
# the surrounding HTML).
_SIGNED_URL_RE = re.compile(
    r"https://private-user-images\.githubusercontent\.com/[^\"'\s<>]+"
)

# Embedded-image markdown: captures the alt text (filename candidate) for a
# given asset URL. ``![alt](url)``; a bare link ``[x](url)`` gives no alt.
_EMBEDDED_IMAGE_RE = re.compile(
    r"!\[([^\]]*)\]\((https?://github\.com/user-attachments/assets/[^\s)]+)\)"
)

_HTML_ACCEPT = "application/vnd.github.html+json"


@dataclass
class AssetContext:
    """Where one asset URL was found: the containing body + alt name."""

    url: str
    source: str                        # "issue" | "comment:<id>"
    body: str
    comment_id: int | None = None
    alt: str | None = None


def discover_github_assets(issue_body: str, comments: list[dict]) -> list[AssetContext]:
    """Discover attachment contexts over body + comments (deduped, in order).

    *comments* is a list of raw GitHub comment dicts (``{"id": ..., "body": ...}``).
    """
    seen: set[str] = set()
    result: list[AssetContext] = []

    def _scan(body: str, source: str, comment_id: int | None) -> None:
        for m in ASSET_URL_RE.finditer(body or ""):
            url = m.group(0)
            if url in seen:
                continue
            seen.add(url)
            alt = None
            for em in _EMBEDDED_IMAGE_RE.finditer(body or ""):
                if em.group(2) == url:
                    alt = em.group(1)
                    break
            result.append(AssetContext(
                url=url, source=source, body=body or "",
                comment_id=comment_id, alt=alt,
            ))

    _scan(issue_body or "", "issue", None)
    for c in comments or []:
        if isinstance(c, dict):
            _scan(c.get("body", "") or "", f"comment:{c.get('id')}", c.get("id"))
    return result


def fetch_html_body(
    owner: str, repo: str, issue_num: int,
    comment_id: int | None, token: str,
    *,
    opener=None,
) -> str:
    """Re-fetch the containing body with the html+json media type.

    Returns the rendered ``body_html`` (empty when unavailable). Uses an
    injectable *opener* (defaulting to ``request.urlopen``) because the
    ``_gh_request`` seam is JSON-only (fixed ``Accept`` header); Mechanism B
    needs a custom media type. Tests drive the real request construction
    (media-type header, ``body_html`` parse, best-effort ``""`` on failure)
    by injecting a fake opener, matching how ``download_bytes`` is tested via
    ``OpenerDirector.open``. Best-effort: any failure degrades to ``""`` so
    the caller warns + skips.
    """
    if comment_id is not None:
        path = f"/repos/{owner}/{repo}/issues/comments/{comment_id}"
    else:
        path = f"/repos/{owner}/{repo}/issues/{issue_num}"
    url = f"https://api.github.com{path}"
    req = request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": _HTML_ACCEPT,
    }, method="GET")
    open_url = opener if opener is not None else request.urlopen
    try:
        with open_url(req, timeout=30) as resp:
            return json.loads(resp.read() or b"{}").get("body_html", "") or ""
    except Exception as e:
        dbg.debug("attachments: html re-fetch failed for %s: %s", path, e)
        return ""


def find_signed_url(html_body: str, asset_url: str) -> str | None:
    """Extract the signed ``private-user-images`` URL for *asset_url*.

    Matches the asset's UUID in the signed URL's path — the rendered
    ``<img src>`` carries the same final path segment as the plain URL.
    Returns ``None`` when the body holds no signed URL for this asset
    (e.g. a plain-link reference on a private repo).
    """
    asset_id = asset_url.rstrip("/").rsplit("/", 1)[-1]
    for m in _SIGNED_URL_RE.finditer(html_body or ""):
        if asset_id in m.group(0):
            return m.group(0)
    return None


def download_github_asset(
    url: str,
    *,
    owner: str,
    repo: str,
    issue_num: int,
    token: str,
    max_bytes: int,
    context: AssetContext | None = None,
    opener: request.OpenerDirector | None = None,
) -> bytes:
    """Download one GitHub asset. Returns the bytes.

    Mechanism A first (plain GET, redirect-follow, anonymous). On a 404,
    Mechanism B: re-fetch the *containing* body with html+json **in the same
    operation** and download the signed ``private-user-images`` URL for this
    asset (the JWT expires in ~300s — never persist or defer it). When the
    rendered body contains no signed URL for the asset (plain-link reference
    on a private repo — the documented open gap), raises
    :class:`downloads.DownloadError` with code ``"no_signed_url"``.

    Raises :class:`downloads.DownloadError` on any failure.
    """
    opener = opener or downloads._build_opener()

    # --- Mechanism A ---
    try:
        return downloads.download_bytes(url, max_bytes=max_bytes, opener=opener)
    except downloads.DownloadError as e:
        if not downloads.is_http_error_code(e.code, 404):
            raise

    # --- Mechanism B (private repos, embedded images only) ---
    if context is None:
        raise downloads.DownloadError(url, "no_context", "no containing body available")
    html_body = fetch_html_body(owner, repo, issue_num, context.comment_id, token)
    if not html_body:
        raise downloads.DownloadError(url, "html_unavailable", "could not fetch body_html")
    signed = find_signed_url(html_body, url)
    if signed is None:
        raise downloads.DownloadError(
            url, "no_signed_url",
            "no signed private-image URL for this asset (plain-link reference on a "
            "private repo — unreachable; docs/autoswe/attachments.md §1.3)",
        )
    return downloads.download_bytes(signed, max_bytes=max_bytes, opener=opener)

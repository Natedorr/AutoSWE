"""Azure DevOps REST API client.

Basic auth with ``base64(":" + pat)``.  Handles 429 rate limiting via the
``retry-after`` header, 5xx exponential backoff, and ``continuationToken``
paging.
"""
from __future__ import annotations

import base64
import json
import time
from urllib import error as url_error
from urllib import request
from urllib.parse import quote as url_quote

from autoswe.core.config import LOGS_DIR
from autoswe.core.logging_utils import init_debug_logger, log, mask_sensitive

dbg = init_debug_logger(LOGS_DIR)

_ADO_BASE = "https://dev.azure.com"
_VSSPS_BASE = "https://app.vssps.visualstudio.com"


def _encode_path_segment(seg: str) -> str:
    """URL-encode a single path segment (org, project, or repo name).

    Handles names with spaces, ``#``, ``&`` and other special characters
    that would otherwise break the request URL.
    """
    return url_quote(seg, safe="")


def _ado_api_version(path: str) -> str:
    """Append api-version query param if not already present."""
    if "api-version" in path:
        return path
    sep = "&" if "?" in path else "?"
    return f"{path}{sep}api-version=7.1"


def _ado_request(
    method: str,
    path: str,
    pat: str,
    body: dict | None = None,
    content_type: str = "application/json",
    max_retries: int = 3,
):
    """Generic Azure DevOps REST request with retry on 429/5xx."""
    dbg.debug("ADO_API: %s %s", method, path)
    auth = base64.b64encode((":" + pat).encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Accept": "application/json",
    }
    if content_type:
        headers["Content-Type"] = content_type

    for attempt in range(max_retries):
        data = json.dumps(body).encode() if body else None
        req = request.Request(path, data=data, method=method, headers=headers)
        try:
            with request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                if not raw:
                    return {}
                try:
                    return json.loads(raw)
                except json.JSONDecodeError as e:
                    snippet = raw.decode(errors="replace")[:300]
                    raise RuntimeError(
                        f"Azure API {path} -> HTTP {resp.status} returned non-JSON: {mask_sensitive(snippet)}"
                    ) from e
        except url_error.HTTPError as e:
            content = e.read().decode() if hasattr(e, "read") else ""
            if e.code == 429 and attempt < max_retries - 1:
                retry_after = e.headers.get("Retry-After")
                ms_255 = e.headers.get("x-ms-retry-after-ms")
                if retry_after:
                    wait = float(retry_after)
                elif ms_255:
                    wait = max(60, float(ms_255) / 1000)
                else:
                    wait = 30
                log(f"[RATELIM] Azure 429. Waiting {wait:.0f}s")
                time.sleep(wait)
                continue
            elif e.code >= 500 and attempt < max_retries - 1:
                wait = (2 ** attempt) + 5
                dbg.warning("_ado_request: server error %d attempt %d/%d: sleeping %ds",
                            e.code, attempt + 1, max_retries, wait)
                time.sleep(wait)
                continue
            else:
                raise RuntimeError(f"Azure API {path} -> HTTP {e.code}: {mask_sensitive(content)}") from e


def ado_get(path: str, pat: str, max_retries: int = 3) -> dict:
    """GET from Azure DevOps API."""
    return _ado_request("GET", path, pat, max_retries=max_retries)


def ado_post(path: str, pat: str, body: dict, max_retries: int = 3) -> dict:
    """POST to Azure DevOps API."""
    return _ado_request("POST", path, pat, body=body, max_retries=max_retries)


def ado_post_patch(path: str, pat: str, body: dict, max_retries: int = 3) -> dict:
    """POST with JSON-Patch content type."""
    return _ado_request("POST", path, pat, body=body, content_type="application/json-patch+json", max_retries=max_retries)


def ado_patch(path: str, pat: str, body: dict, max_retries: int = 3) -> dict:
    """PATCH (JSON-Patch) to Azure DevOps API."""
    return _ado_request(
        "PATCH", path, pat,
        body=body,
        content_type="application/json-patch+json",
        max_retries=max_retries,
    )


def ado_patch_json(path: str, pat: str, body: dict, max_retries: int = 3) -> dict:
    """PATCH with standard application/json (for endpoints like comments/update
    that take a plain JSON body, not a JSON-Patch document)."""
    return _ado_request("PATCH", path, pat, body=body,
                        content_type="application/json", max_retries=max_retries)


def ado_get_paged(path: str, pat: str) -> list:
    """Paginated GET following ``continuationToken``."""
    results = []
    token = None
    while True:
        if token:
            sep = "&" if "?" in path else "?"
            url = f"{path}{sep}continuationToken={token}"
        else:
            url = path
        page = ado_get(url, pat)
        value = page.get("value", [])
        results.extend(value)
        token = page.get("continuationToken")
        if not token or len(value) == 0:
            break
    return results

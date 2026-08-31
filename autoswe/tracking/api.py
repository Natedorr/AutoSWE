import json
import time
from email.utils import parsedate_to_datetime
from urllib import error as url_error
from urllib import request

from autoswe.core.constants import GH_API_VERSION  # re-exported for convenience
from autoswe.core.logging_utils import get_debug_logger, log, mask_sensitive
from autoswe.core.redact import redact_outbound

dbg = get_debug_logger()

# Bounds for a rate-limit backoff derived from a `Retry-After` header. A
# well-behaved GitHub secondary-limit header is seconds (delta) or an HTTP-date
# a short while out; clamp to [1, 300] so a malformed or far-future header
# can't block a dispatch for hours.
_RETRY_AFTER_MIN = 1.0
_RETRY_AFTER_MAX = 300.0


def _parse_retry_after(value: str | None) -> float | None:
    """Parse a ``Retry-After`` header value into seconds to wait.

    Handles both the delta-seconds form (``Retry-After: 120``) and the
    HTTP-date form. Returns ``None`` when the value is absent or malformed,
    in which case the caller falls back to exponential backoff.
    """
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    # Delta-seconds form.
    try:
        seconds = float(value)
        return min(max(_RETRY_AFTER_MIN, seconds), _RETRY_AFTER_MAX)
    except ValueError:
        pass
    # HTTP-date form.
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    try:
        now = time.time()
        delta = dt.timestamp() - now
    except (AttributeError, OverflowError, ValueError):
        return None
    return min(max(_RETRY_AFTER_MIN, delta), _RETRY_AFTER_MAX)


def _gh_request(
    method: str, path: str, token: str, body: dict | None = None,
    max_retries: int = 3, timeout: float = 30,
):
    """Generic GitHub API request with exponential backoff on rate-limit/errors.

    Rate-limit / transient-error handling:
    - 403 (primary limit): sleep until ``X-RateLimit-Reset``.
    - 403 (secondary limit, ``Retry-After`` present): honor ``Retry-After``.
    - 429: honor ``Retry-After`` if present, else exponential backoff; retry.
    - 5xx: exponential backoff; retry.
    All retryable paths are bounded by ``max_retries``; after the last attempt
    a ``RuntimeError`` is raised (a transient 429 no longer aborts mid-loop).

    Best-effort callers (e.g. link_branch_to_issue) should pass max_retries=1
    and a short timeout to avoid blocking the pipeline.
    """
    dbg.debug("GH_API: %s %s", method, path)
    url = f"https://api.github.com{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": GH_API_VERSION,
    }

    for attempt in range(max_retries):
        data = json.dumps(body).encode() if body else None
        req = request.Request(url, data=data, method=method, headers=headers)
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                remaining = resp.headers.get("X-RateLimit-Remaining")
                reset = resp.headers.get("X-RateLimit-Reset")
                if remaining and int(remaining) < 100:
                    log(f"[RATELIM] GitHub API low on quota: {remaining}/5000, resets at {reset}")
                body_text = resp.read()
                return json.loads(body_text) if body_text else {}
        except url_error.HTTPError as e:
            content = e.read().decode() if hasattr(e, 'read') else ""
            if e.code == 403:
                # Distinguish archived-repo 403 from genuine rate-limit 403.
                # Archived repos return 403 with "archived" in the body — no point sleeping.
                if "archived" in content:
                    raise RuntimeError(f"GitHub API {path} -> HTTP {e.code}: {mask_sensitive(content)}") from e
                retry_after = _parse_retry_after(e.headers.get("Retry-After"))
                if retry_after is not None and attempt < max_retries - 1:
                    # Secondary-limit 403: honor the server-provided Retry-After
                    # rather than sleeping to the full primary X-RateLimit-Reset.
                    log(f"[RATELIM] 403 secondary rate limit hit. Waiting {retry_after:.0f}s (Retry-After)")
                    time.sleep(retry_after)
                    continue
                reset_ts = int(e.headers.get("X-RateLimit-Reset", 0))
                if reset_ts and attempt < max_retries - 1:
                    wait_seconds = max(60, reset_ts - time.time())
                    log(f"[RATELIM] 403 rate limit hit. Waiting {wait_seconds:.0f}s until reset")
                    time.sleep(wait_seconds)
                    continue
                raise RuntimeError(f"GitHub API {path} -> HTTP {e.code}: {mask_sensitive(content)}") from e
            elif e.code == 429:
                # 429 is a rate-limit signal, not a fatal error. Honor
                # Retry-After when present; fall back to exponential backoff.
                if attempt < max_retries - 1:
                    wait = _parse_retry_after(e.headers.get("Retry-After"))
                    if wait is None:
                        wait = (2 ** attempt) + 5
                    log(f"[RATELIM] 429 rate limit hit. Waiting {wait:.0f}s")
                    time.sleep(wait)
                    continue
                raise RuntimeError(f"GitHub API {path} -> HTTP {e.code}: {mask_sensitive(content)}") from e
            elif e.code >= 500 and attempt < max_retries - 1:
                wait = (2 ** attempt) + 5
                dbg.warning("_gh_request: server error %d on attempt %d/%d for %s: sleeping %ds",
                            e.code, attempt + 1, max_retries, path, wait, exc_info=True)
                time.sleep(wait)
                continue
            else:
                raise RuntimeError(f"GitHub API {path} -> HTTP {e.code}: {mask_sensitive(content)}") from e


def gh_get(path: str, token: str, max_retries: int = 3):
    """GET from GitHub API with exponential backoff on rate-limit/errors."""
    return _gh_request("GET", path, token, max_retries=max_retries)


def gh_post(path: str, token: str, body: dict, max_retries: int = 3, timeout: float = 30):
    """POST to GitHub API with JSON body."""
    return _gh_request("POST", path, token, body=body, max_retries=max_retries, timeout=timeout)


def gh_put(path: str, token: str, body: dict, max_retries: int = 3, timeout: float = 30):
    """PUT to GitHub API with JSON body — used for replacing labels."""
    return _gh_request("PUT", path, token, body=body, max_retries=max_retries, timeout=timeout)


def gh_patch(path: str, token: str, body: dict, max_retries: int = 3, timeout: float = 30):
    """PATCH to GitHub API with JSON body — used for partial resource updates (e.g. edit comment)."""
    return _gh_request("PATCH", path, token, body=body, max_retries=max_retries, timeout=timeout)


def gh_get_all(path: str, token: str) -> list:
    """Paginated GET — follows ?page= until an empty page is returned."""
    sep = "&" if "?" in path else "?"
    results = []
    page = 1
    while True:
        batch = gh_get(f"{path}{sep}per_page=100&page={page}", token)
        if not batch:
            break
        results.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return results


def fetch_owned_repos(token: str) -> list:
    """Return list of 'owner/repo' strings for all repos owned by authenticated user."""
    repos = gh_get_all("/user/repos?type=owner", token)
    return [r["full_name"] for r in repos]


def gh_post_comment(owner: str, repo: str, issue_number: int, body: str, token: str) -> None:
    """Post a comment on a GitHub issue."""
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments"
    payload = json.dumps({"body": redact_outbound(body)}).encode()
    req = request.Request(url, data=payload, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": GH_API_VERSION,
    })
    try:
        with request.urlopen(req):
            pass
    except url_error.HTTPError as e:
        dbg.warning("gh_post_comment: HTTP %d posting to %s/%s#%d",
                    e.code, owner, repo, issue_number, exc_info=True)
        log(f"[WARN] comment post failed: HTTP {e.code}")


def _fetch_comments(owner: str, repo: str, issue_number: int, token: str) -> list:
    """Fetch all comments for an issue as a list of dicts."""
    try:
        return gh_get_all(f"/repos/{owner}/{repo}/issues/{issue_number}/comments", token)
    except RuntimeError as e:
        dbg.warning("_fetch_comments: failed for %s/%s#%d: %s",
                    owner, repo, issue_number, e, exc_info=True)
        log(f"[WARN] could not fetch comments for {owner}/{repo}#{issue_number}: {e}")
        return []

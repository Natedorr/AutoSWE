"""Raw HTTP download helpers for the attachment layer (issue #290).

Kept deliberately small and urllib-based: attachment bytes are untrusted
input, and the only invariants enforced here are the size cap (checked
*before* any bytes touch disk) and a hard timeout. All failures surface as
:class:`DownloadError` with a machine-readable ``code`` so callers can
distinguish the GitHub Mechanism-A 404 (which triggers the Mechanism-B
fallback) from anything else.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib import error as url_error
from urllib import request

_DOWNLOAD_TIMEOUT_SEC = 60.0
_CHUNK = 64 * 1024


@dataclass
class DownloadError(Exception):
    """A failed attachment download.

    ``code`` is one of ``"http_<status>"``, ``"too_large"``, or
    ``"transport"`` (network failure / timeout / non-HTTP error).
    """

    url: str
    code: str
    message: str = ""

    def __str__(self) -> str:
        # The url may be a Mechanism-B signed private-image URL carrying a
        # short-lived JWT in the query string — a credential. Strip the query
        # so the signed segment never reaches a log line (the path is not
        # secret and is kept for correlation).
        return (
            f"{type(self).__name__}({self.code}): "
            f"{_safe_url(self.url)}: {self.message}"
        )


def _safe_url(url: str) -> str:
    """Return *url* with its query string removed, for safe logging.

    Signed ``private-user-images`` URLs carry a scoped, ~300s-TTL JWT in the
    query string; it is a credential and must never appear in logs. Only the
    non-secret path is retained. Idempotent on query-free URLs.
    """
    return (url or "").split("?", 1)[0]


def _build_opener() -> request.OpenerDirector:
    """Opener that follows redirects but sends no cookies (fresh per call)."""
    return request.build_opener()


def download_bytes(
    url: str,
    *,
    max_bytes: int,
    headers: dict[str, str] | None = None,
    opener: request.OpenerDirector | None = None,
) -> bytes:
    """GET *url* following redirects, returning at most *max_bytes*.

    Raises :class:`DownloadError` — never returns partial data. The size cap
    is enforced while streaming so a file larger than *max_bytes* never
    occupies more than one chunk of memory and nothing is returned.
    """
    opener = opener or _build_opener()
    req = request.Request(url, headers=headers or {}, method="GET")
    try:
        with opener.open(req, timeout=_DOWNLOAD_TIMEOUT_SEC) as resp:
            parts: list[bytes] = []
            total = 0
            while True:
                chunk = resp.read(_CHUNK)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise DownloadError(url, "too_large", f"exceeds {max_bytes} bytes")
                parts.append(chunk)
            return b"".join(parts)
    except DownloadError:
        raise
    except url_error.HTTPError as e:
        raise DownloadError(url, f"http_{e.code}", f"HTTP {e.code}") from e
    except url_error.URLError as e:
        raise DownloadError(url, "transport", str(e.reason)) from e
    except (TimeoutError, OSError) as e:
        raise DownloadError(url, "transport", str(e)) from e


def is_http_error_code(code: str | None, *status: int) -> bool:
    """True when a :class:`DownloadError` code is HTTP *status* (any of)."""
    if not code:
        return False
    return code in {f"http_{s}" for s in status}

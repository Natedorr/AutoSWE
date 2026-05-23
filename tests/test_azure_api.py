"""Tests for autoswe.providers.azure.api — ADO HTTP layer."""
import json
import urllib.error
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from autoswe.providers.azure.api import (
    _ado_request,
    ado_get,
    ado_get_paged,
    ado_patch,
    ado_post,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ado_ok(body, status=200):
    """Return a mock response context-manager."""
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = json.dumps(body).encode()
    resp.headers = {}
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _ado_empty():
    """200 / empty body response."""
    resp = MagicMock()
    resp.status = 200
    resp.read.return_value = b""
    resp.headers = {}
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _ado_error(code, headers=None):
    hdr = MagicMock()
    hdr.get = lambda k, d=None: (headers or {}).get(k, d)
    return urllib.error.HTTPError(
        url="https://dev.azure.com/test",
        code=code,
        msg="error",
        hdrs=hdr,
        fp=BytesIO(b'{"error":"fail"}'),
    )


# ---------------------------------------------------------------------------
# _ado_request success
# ---------------------------------------------------------------------------

def test_ado_request_success():
    with patch("urllib.request.urlopen") as m:
        m.return_value = _ado_ok({"result": "ok"})
        result = _ado_request("GET", "https://dev.azure.com/test", "pat", max_retries=1)
    assert result == {"result": "ok"}


def test_ado_request_empty_body():
    with patch("urllib.request.urlopen") as m:
        m.return_value = _ado_empty()
        result = _ado_request("DELETE", "https://dev.azure.com/test", "pat", max_retries=1)
    assert result == {}


# ---------------------------------------------------------------------------
# _ado_request error handling
# ---------------------------------------------------------------------------

def test_ado_request_raises_404():
    with patch("urllib.request.urlopen", side_effect=_ado_error(404)):
        with pytest.raises(RuntimeError, match="404"):
            _ado_request("GET", "https://dev.azure.com/not-found", "pat", max_retries=1)


def test_ado_request_retries_500(mocker):
    """500 should retry then raise."""
    err = _ado_error(500)
    calls = {"n": 0}

    def side_effect(*a, **k):
        calls["n"] += 1
        raise err

    mocker.patch("urllib.request.urlopen", side_effect=side_effect)
    mocker.patch("time.sleep")

    with pytest.raises(RuntimeError, match="500"):
        _ado_request("GET", "https://dev.azure.com/test", "pat", max_retries=3)
    assert calls["n"] == 3


def test_ado_request_429_retry(mocker):
    """429 with Retry-After should sleep and retry."""
    err = _ado_error(429, headers={"Retry-After": "10"})
    ok = _ado_ok({"ok": True})
    calls = {"n": 0}

    def side_effect(*a, **k):
        calls["n"] += 1
        if calls["n"] < 2:
            raise err
        return ok

    mocker.patch("urllib.request.urlopen", side_effect=side_effect)
    mocker.patch("time.sleep")

    result = _ado_request("GET", "https://dev.azure.com/test", "pat", max_retries=3)
    assert result == {"ok": True}
    assert calls["n"] == 2


def test_ado_request_429_retry_after_missing(mocker):
    """429 without Retry-After should use fallback."""
    err = _ado_error(429)
    ok = _ado_ok({"ok": True})
    calls = {"n": 0}

    def side_effect(*a, **k):
        calls["n"] += 1
        if calls["n"] < 2:
            raise err
        return ok

    mocker.patch("urllib.request.urlopen", side_effect=side_effect)
    mocker.patch("time.sleep")

    result = _ado_request("GET", "https://dev.azure.com/test", "pat", max_retries=3)
    assert result == {"ok": True}


# ---------------------------------------------------------------------------
# Convenience wrappers
# ---------------------------------------------------------------------------

def test_ado_get():
    with patch("autoswe.providers.azure.api._ado_request", return_value={"a": 1}):
        result = ado_get("/test", "pat")
    assert result == {"a": 1}


def test_ado_post():
    with patch("autoswe.providers.azure.api._ado_request", return_value={"created": True}):
        result = ado_post("/test", "pat", body={"name": "x"})
    assert result == {"created": True}


def test_ado_patch_uses_json_patch_content_type():
    """ado_patch must set application/json-patch+json content type."""
    captured = {}

    def fake_request(method, path, pat, body=None, content_type="application/json", max_retries=3):
        captured["content_type"] = content_type
        return {}

    with patch("autoswe.providers.azure.api._ado_request", fake_request):
        ado_patch("/test", "pat", body=[{"op": "replace", "path": "/x", "value": 1}])

    assert captured["content_type"] == "application/json-patch+json"


# ---------------------------------------------------------------------------
# ado_get_paged — continuationToken
# ---------------------------------------------------------------------------

def test_ado_get_paged_single_page():
    with patch("autoswe.providers.azure.api.ado_get", return_value={"value": [1, 2, 3]}):
        result = ado_get_paged("/test", "pat")
    assert result == [1, 2, 3]


def test_ado_get_paged_two_pages():
    pages = [
        {"value": [1], "continuationToken": "abc123"},
        {"value": [2]},  # no token → last page
    ]
    idx = {"n": 0}

    def fake_get(path, pat, max_retries=3):
        r = pages[idx["n"]]
        idx["n"] += 1
        return r

    with patch("autoswe.providers.azure.api.ado_get", fake_get):
        result = ado_get_paged("/test", "pat")
    assert result == [1, 2]


# ------ Network/connection errors --------


def test_ado_request_connection_error():
    """URLError (network unreachable) propagates directly — not caught by retry logic."""
    import urllib.error as ue

    err = ue.URLError("Network is unreachable")
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(ue.URLError, match="Network"):
            _ado_request("GET", "https://dev.azure.com/test", "pat", max_retries=2)


def test_ado_request_dns_failure():
    """DNS resolution failure propagates as URLError."""
    import urllib.error as ue

    err = ue.URLError("[Errno -2] Name or service not known")
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(ue.URLError):
            _ado_request("GET", "https://dev.azure.com/test", "pat", max_retries=1)


def test_ado_request_401_raises():
    """401 (invalid PAT) should raise immediately without retry."""
    with patch("urllib.request.urlopen", side_effect=_ado_error(401)):
        with pytest.raises(RuntimeError, match="401"):
            _ado_request("GET", "https://dev.azure.com/test", "bad_pat", max_retries=1)


def test_ado_request_403_raises():
    """403 (forbidden) should raise immediately."""
    with patch("urllib.request.urlopen", side_effect=_ado_error(403)):
        with pytest.raises(RuntimeError, match="403"):
            _ado_request("GET", "https://dev.azure.com/test", "pat", max_retries=1)


# ------ Pagination edge cases ------


def test_ado_get_paged_empty():
    """Returns empty list when no results."""
    with patch("autoswe.providers.azure.api.ado_get", return_value={"value": []}):
        result = ado_get_paged("/test", "pat")
    assert result == []


def test_ado_get_paged_continuation_token_is_passed(mocker):
    """Continuation token is appended to the URL on subsequent pages."""
    pages = [
        {"value": [1], "continuationToken": "tok1"},
        {"value": [2], "continuationToken": "tok2"},
        {"value": [3]},
    ]
    call_count = {"n": 0}
    paths = []

    def fake_get(path, pat, max_retries=3):
        paths.append(path)
        r = pages[call_count["n"]]
        call_count["n"] += 1
        return r

    mocker.patch("autoswe.providers.azure.api.ado_get", fake_get)
    result = ado_get_paged("/test", "pat")

    assert result == [1, 2, 3]
    assert len(paths) == 3
    # First call has no token
    assert "continuationToken" not in paths[0]
    # Subsequent calls carry continuation token
    assert "continuationToken=tok1" in paths[1]
    assert "continuationToken=tok2" in paths[2]

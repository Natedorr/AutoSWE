"""Tests for autoswe.tracking.api — HTTP layer with urllib mocked."""

import json
import urllib.error
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from autoswe.tracking.api import _gh_request, gh_get_all

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_response(body: dict, status: int = 200, headers: dict = None):
    """Return a context-manager mock simulating urllib.request.urlopen response."""
    raw = json.dumps(body).encode()
    resp = MagicMock()
    resp.read.return_value = raw
    resp.headers = MagicMock()
    hdr = headers or {}
    resp.headers.get = lambda k, d=None: hdr.get(k, d)
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def make_http_error(code: int, headers: dict = None):
    hdr = MagicMock()
    hdr.get = lambda k, d=None: (headers or {}).get(k, d)
    err = urllib.error.HTTPError(
        url="https://api.github.com/test",
        code=code,
        msg="error",
        hdrs=hdr,
        fp=BytesIO(b'{"message":"error"}'),
    )
    return err


# ---------------------------------------------------------------------------
# _gh_request success
# ---------------------------------------------------------------------------

def test_gh_request_success():
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value = make_response({"login": "natedorr"})
        result = _gh_request("GET", "/user", "fake_token", max_retries=1)
    assert result == {"login": "natedorr"}


def test_gh_request_empty_body_returns_empty_dict():
    resp = MagicMock()
    resp.read.return_value = b""
    resp.headers = MagicMock()
    resp.headers.get = lambda k, d=None: d
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=resp):
        result = _gh_request("POST", "/issues/1/labels", "tok", body={}, max_retries=1)
    assert result == {}


# ---------------------------------------------------------------------------
# _gh_request error handling
# ---------------------------------------------------------------------------

def test_gh_request_raises_on_non_retryable_404():
    with patch("urllib.request.urlopen", side_effect=make_http_error(404)):
        with pytest.raises(RuntimeError, match="404"):
            _gh_request("GET", "/not-found", "tok", max_retries=1)


def test_gh_request_raises_on_403_no_reset():
    """403 without a reset timestamp should raise immediately."""
    with patch("urllib.request.urlopen", side_effect=make_http_error(403)):
        with pytest.raises(RuntimeError, match="403"):
            _gh_request("GET", "/rate", "tok", max_retries=1)


def test_gh_request_respects_custom_timeout():
    """_gh_request should pass the timeout parameter to urlopen."""
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value = make_response({"ok": True})
        _gh_request("GET", "/user", "fake_token", max_retries=1, timeout=5)
    mock_open.assert_called_once()
    # urlopen(req, timeout=5) — timeout is the keyword arg
    call_kwargs = mock_open.call_args[1]
    assert call_kwargs.get("timeout") == 5


def test_gh_request_max_retries_one_raises_immediately_on_403():
    """max_retries=1 should raise immediately on 403 without sleeping."""
    with patch("urllib.request.urlopen", side_effect=make_http_error(403)), \
         patch("time.sleep") as mock_sleep:
        with pytest.raises(RuntimeError, match="403"):
            _gh_request("GET", "/rate", "tok", max_retries=1)
    # Should NOT have called sleep — max_retries=1 means no retry attempt
    mock_sleep.assert_not_called()


def test_gh_request_retries_on_500(mocker):
    """500 should retry up to max_retries before raising."""
    err = make_http_error(500)
    # Succeed on third attempt
    success = make_response({"ok": True})
    call_count = {"n": 0}

    def side_effect(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise err
        return success

    mocker.patch("urllib.request.urlopen", side_effect=side_effect)
    mocker.patch("time.sleep")  # don't actually sleep

    result = _gh_request("GET", "/test", "tok", max_retries=3)
    assert result == {"ok": True}
    assert call_count["n"] == 3


# ---------------------------------------------------------------------------
# gh_get_all pagination
# ---------------------------------------------------------------------------

def test_gh_get_all_single_page():
    """Returns all items when fewer than per_page results."""
    items = [{"id": i} for i in range(5)]
    with patch("autoswe.tracking.api.gh_get", return_value=items):
        result = gh_get_all("/repos/o/r/issues", "tok")
    assert result == items


def test_gh_get_all_stops_on_empty_page():
    """Stops pagination when an empty list is returned."""
    pages = [[{"id": i} for i in range(100)], []]
    call_count = {"n": 0}

    def fake_get(path, token, max_retries=3):
        result = pages[call_count["n"]]
        call_count["n"] += 1
        return result

    with patch("autoswe.tracking.api.gh_get", side_effect=fake_get):
        result = gh_get_all("/repos/o/r/issues", "tok")
    assert len(result) == 100


def test_gh_get_all_stops_when_less_than_100():
    """Stops when a page returns fewer than 100 items (no more pages)."""
    page1 = [{"id": i} for i in range(100)]
    page2 = [{"id": i} for i in range(47)]
    pages = [page1, page2]
    call_count = {"n": 0}

    def fake_get(path, token, max_retries=3):
        result = pages[call_count["n"]]
        call_count["n"] += 1
        return result

    with patch("autoswe.tracking.api.gh_get", side_effect=fake_get):
        result = gh_get_all("/repos/o/r/issues", "tok")
    assert len(result) == 147


# ------ Network/connection errors --------


def test_gh_request_connection_error():
    """URLError (network unreachable) propagates directly — not caught by retry logic."""
    import urllib.error as ue

    err = ue.URLError("Network is unreachable")
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(ue.URLError, match="Network"):
            _gh_request("GET", "/user", "tok", max_retries=2)


def test_gh_request_connection_refused():
    """Connection refused propagates as URLError."""
    import urllib.error as ue

    err = ue.URLError("[Errno 111] Connection refused")
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(ue.URLError):
            _gh_request("GET", "/user", "tok", max_retries=1)


def test_gh_request_dns_failure():
    """DNS resolution failure propagates as URLError."""
    import urllib.error as ue

    err = ue.URLError("[Errno -2] Name or service not known")
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(ue.URLError):
            _gh_request("GET", "/user", "tok", max_retries=1)


def test_gh_get_all_empty_result():
    """Returns empty list when no results."""
    with patch("autoswe.tracking.api.gh_get", return_value=[]):
        result = gh_get_all("/repos/o/r/issues", "tok")
    assert result == []


# ------ Rate limit handling --------


def test_gh_request_403_with_reset_header_retries(mocker):
    """403 with X-RateLimit-Reset in future should retry."""
    import time

    future_reset = int(time.time()) + 3600
    err = make_http_error(403, headers={"X-RateLimit-Reset": str(future_reset)})
    ok = make_response({"ok": True})
    call_count = {"n": 0}

    def side_effect(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] < 2:
            raise err
        return ok

    mocker.patch("urllib.request.urlopen", side_effect=side_effect)
    mocker.patch("time.sleep")

    result = _gh_request("GET", "/user", "tok", max_retries=2)
    assert result == {"ok": True}
    assert call_count["n"] == 2


def test_gh_request_403_reset_in_past_raises(mocker):
    """403 with X-RateLimit-Reset in the past should raise immediately."""
    import time

    past_reset = int(time.time()) - 100
    err = make_http_error(403, headers={"X-RateLimit-Reset": str(past_reset)})
    mocker.patch("urllib.request.urlopen", side_effect=err)
    mocker.patch("time.sleep")

    with pytest.raises(RuntimeError, match="403"):
        _gh_request("GET", "/user", "tok", max_retries=2)

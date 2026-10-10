"""Tests for the attachment ingestion layer (issue #290).

Covers, through the existing test seams (provider mocks + a fake
signed-URL HTTP server via ``urllib`` patching):
- discovery regex (body + comments, dedup)
- Mechanism A -> Mechanism B fallback
- temp-dir lifecycle (create / cleanup / stale sweep)
- naming + magic-byte sniff
- path-traversal guard rejection
- cap enforcement (per-file + total)
- manifest injection into plan/fix/review prompts
- best-effort failure (warning, no task failure)
"""
from __future__ import annotations

import io
import time
import urllib.request

import pytest

# ---------------------------------------------------------------------------
# A stable 36-char UUID (8-4-4-4-12) for fixture URLs.
# ---------------------------------------------------------------------------
_UUID = "b45006e0-fabd-43a6-8d81-789330c687d7"
_UUID2 = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_ASSET_URL = f"https://github.com/user-attachments/assets/{_UUID}"
_ASSET_URL2 = f"https://github.com/user-attachments/assets/{_UUID2}"


# ============================================================================
# Discovery
# ============================================================================

class TestDiscovery:
    def test_discovers_in_body(self):
        from autoswe.attachments.github import discover_github_assets

        body = f"Here is the failing input: { _ASSET_URL }\n"
        ctxs = discover_github_assets(body, [])
        assert len(ctxs) == 1
        assert ctxs[0].url == _ASSET_URL
        assert ctxs[0].source == "issue"

    def test_discovers_in_comments(self):
        from autoswe.attachments.github import discover_github_assets

        comments = [{"id": 11, "body": f"see {_ASSET_URL}"}]
        ctxs = discover_github_assets("", comments)
        assert len(ctxs) == 1
        assert ctxs[0].source == "comment:11"
        assert ctxs[0].comment_id == 11

    def test_dedupes_across_body_and_comment(self):
        from autoswe.attachments.github import discover_github_assets

        body = f"body has {_ASSET_URL}"
        comments = [{"id": 1, "body": f"comment has {_ASSET_URL} again"}]
        ctxs = discover_github_assets(body, comments)
        assert len(ctxs) == 1

    def test_discovers_multiple_distinct(self):
        from autoswe.attachments.github import discover_github_assets

        body = f"{_ASSET_URL} and {_ASSET_URL2}"
        ctxs = discover_github_assets(body, [])
        assert [c.url for c in ctxs] == [_ASSET_URL, _ASSET_URL2]

    def test_no_match(self):
        from autoswe.attachments.github import discover_github_assets

        ctxs = discover_github_assets("no attachments here", [])
        assert ctxs == []

    def test_requires_36_char_uuid(self):
        from autoswe.attachments.github import discover_github_assets

        # Too short — should not match.
        bad = "https://github.com/user-attachments/assets/abc123"
        assert discover_github_assets(bad, []) == []

    def test_embedded_image_captures_alt(self):
        from autoswe.attachments.github import discover_github_assets

        body = f"![failing-input.csv]({_ASSET_URL})"
        ctxs = discover_github_assets(body, [])
        assert ctxs[0].alt == "failing-input.csv"

    def test_plain_link_has_no_alt(self):
        from autoswe.attachments.github import discover_github_assets

        body = f"[the file]({_ASSET_URL})"
        ctxs = discover_github_assets(body, [])
        assert ctxs[0].alt is None


# ============================================================================
# Naming + magic-byte sniff
# ============================================================================

class TestNaming:
    def test_is_trusted_name_accepts(self):
        from autoswe.attachments.naming import is_trusted_name

        assert is_trusted_name("data.csv")
        assert is_trusted_name("my file.png")
        assert is_trusted_name("A-b_c.txt")

    def test_is_trusted_name_rejects_traversal(self):
        from autoswe.attachments.naming import is_trusted_name

        assert not is_trusted_name("../etc/passwd")
        assert not is_trusted_name("a/../../b.csv")
        assert not is_trusted_name("..hidden.csv")
        assert not is_trusted_name("/abs/path.csv")
        assert not is_trusted_name(r"C:\win\evil.csv")
        assert not is_trusted_name("a\\b.csv")
        assert not is_trusted_name("C:evil.csv")

    def test_is_trusted_name_rejects_empty_and_long(self):
        from autoswe.attachments.naming import is_trusted_name

        assert not is_trusted_name("")
        assert not is_trusted_name(None)
        assert not is_trusted_name("x" * 500)

    def test_sniff_png(self):
        from autoswe.attachments.naming import sniff_content

        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        ext, ctype = sniff_content(data)
        assert ext == "png"
        assert ctype == "image/png"

    def test_sniff_jpeg(self):
        from autoswe.attachments.naming import sniff_content

        assert sniff_content(b"\xff\xd8\xff\xe0" + b"\x00" * 16) == ("jpg", "image/jpeg")

    def test_sniff_pdf(self):
        from autoswe.attachments.naming import sniff_content

        assert sniff_content(b"%PDF-1.4 hello") == ("pdf", "application/pdf")

    def test_sniff_gzip(self):
        from autoswe.attachments.naming import sniff_content

        assert sniff_content(b"\x1f\x8b" + b"\x00" * 16) == ("gz", "application/gzip")

    def test_sniff_text(self):
        from autoswe.attachments.naming import sniff_content

        ext, ctype = sniff_content(b"col1,col2\n1,2\n3,4\n")
        assert ext == "txt"
        assert ctype == "text/plain"

    def test_sniff_unknown_binary(self):
        from autoswe.attachments.naming import sniff_content

        ext, ctype = sniff_content(b"\x00\x01\x02\xff\xfe\x00")
        assert ext == "bin"
        assert ctype == "application/octet-stream"

    def test_pick_prefers_trusted_provider_name(self):
        from autoswe.attachments.naming import pick_filename

        name = pick_filename("report.csv", b"data", set(), 1)
        assert name == "report.csv"

    def test_pick_sniffs_when_no_name(self):
        from autoswe.attachments.naming import pick_filename

        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
        name = pick_filename(None, png, set(), 1)
        assert name == "attachment-1.png"

    def test_pick_sniffs_when_name_untrusted(self):
        from autoswe.attachments.naming import pick_filename

        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
        name = pick_filename("../../evil.png", png, set(), 1)
        assert name == "attachment-1.png"
        # No path separators — stays flat.
        assert "/" not in name and "\\" not in name and ".." not in name

    def test_pick_dedupes(self):
        from autoswe.attachments.naming import pick_filename

        used: set[str] = set()
        n1 = pick_filename("data.csv", b"x", used, 1)
        n2 = pick_filename("data.csv", b"x", used, 2)
        assert n1 == "data.csv"
        assert n2 != n1
        assert n2.startswith("data-")


# ============================================================================
# Downloads: cap + error classification (no network)
# ============================================================================

class TestDownloads:
    def test_download_error_is_http(self):
        from autoswe.attachments import downloads

        assert downloads.is_http_error_code("http_404", 404)
        assert not downloads.is_http_error_code("http_500", 404)
        assert not downloads.is_http_error_code("transport", 404)

    def test_download_too_large(self, monkeypatch):
        from autoswe.attachments import downloads

        max_bytes = 100

        def fake_open(req, timeout):
            class Resp:
                def __init__(self):
                    self._first = True

                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

                def read(self, size):
                    if self._first:
                        self._first = False
                        return b"\x00" * (max_bytes + 10)
                    return b""

            return Resp()

        monkeypatch.setattr(
            urllib.request.OpenerDirector, "open",
            lambda self, req, timeout=None: fake_open(req, timeout),
        )
        with pytest.raises(downloads.DownloadError) as exc:
            downloads.download_bytes("http://x/a", max_bytes=max_bytes)
        assert exc.value.code == "too_large"

    def test_download_http_error_404(self, monkeypatch):
        from urllib import error as url_error

        from autoswe.attachments import downloads

        def fake_open(req, timeout):
            raise url_error.HTTPError("http://x/a", 404, "Not Found", {}, io.BytesIO(b""))

        monkeypatch.setattr(
            urllib.request.OpenerDirector, "open",
            lambda self, req, timeout=None: fake_open(req, timeout),
        )
        with pytest.raises(downloads.DownloadError) as exc:
            downloads.download_bytes("http://x/a", max_bytes=100)
        assert exc.value.code == "http_404"


# ============================================================================
# GitHub A -> B fallback
# ============================================================================

class TestGithubFallback:
    def test_mechanism_a_success_no_b(self, monkeypatch):
        """When Mechanism A (plain GET) succeeds, Mechanism B is never invoked."""
        from autoswe.attachments import github as gh

        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
        html_calls = []

        def fake_download(url, *, max_bytes, headers=None, opener=None):
            if url.startswith("https://private-user-images."):
                html_calls.append("signed")
                return png
            return png  # plain mechanism A

        monkeypatch.setattr(gh.downloads, "download_bytes", fake_download)
        monkeypatch.setattr(gh, "fetch_html_body", lambda *a, **k: (_ for _ in ()).throw(AssertionError("B called")))

        data = gh.download_github_asset(
            _ASSET_URL, owner="o", repo="r", issue_num=1, token="t", max_bytes=1024,
        )
        assert data == png
        assert not html_calls

    def test_mechanism_b_fallback_on_404(self, monkeypatch):
        """On a 404 from Mechanism A, Mechanism B fetches html + signed URL."""
        from autoswe.attachments import downloads
        from autoswe.attachments import github as gh

        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16

        def fake_download(url, *, max_bytes, headers=None, opener=None):
            if url.startswith("https://private-user-images."):
                return png
            raise downloads.DownloadError(url, "http_404", "HTTP 404")

        signed = f"https://private-user-images.githubusercontent.com/1/{_UUID}?jwt=abc"
        html_body = f'<p><img src="{signed}" /></p>'

        monkeypatch.setattr(gh.downloads, "download_bytes", fake_download)
        monkeypatch.setattr(gh, "fetch_html_body", lambda *a, **k: html_body)

        ctx = gh.AssetContext(url=_ASSET_URL, source="issue", body=f"{_ASSET_URL}")
        data = gh.download_github_asset(
            _ASSET_URL, owner="o", repo="r", issue_num=1, token="t", max_bytes=1024,
            context=ctx,
        )
        assert data == png

    def test_mechanism_b_no_signed_url_warns(self, monkeypatch):
        """Plain-link on a private repo -> no signed URL -> no_signed_url error."""
        from autoswe.attachments import downloads
        from autoswe.attachments import github as gh

        def fake_download(url, *, max_bytes, headers=None, opener=None):
            raise downloads.DownloadError(url, "http_404", "HTTP 404")

        # html body has NO private-user-images signed URL for this asset.
        monkeypatch.setattr(gh.downloads, "download_bytes", fake_download)
        monkeypatch.setattr(
            gh, "fetch_html_body",
            lambda *a, **k: '<p><a href="https://github.com/user-attachments/assets/x">file</a></p>',
        )

        ctx = gh.AssetContext(url=_ASSET_URL, source="issue", body=f"{_ASSET_URL}")
        with pytest.raises(downloads.DownloadError) as exc:
            gh.download_github_asset(
                _ASSET_URL, owner="o", repo="r", issue_num=1, token="t", max_bytes=1024,
                context=ctx,
            )
        assert exc.value.code == "no_signed_url"

    def test_find_signed_url_matches_asset_id(self):
        from autoswe.attachments.github import find_signed_url

        signed = f"https://private-user-images.githubusercontent.com/1/{_UUID}?jwt=z"
        html = f'<img src="{signed}">'
        assert find_signed_url(html, _ASSET_URL) == signed
        # A different asset id is not matched.
        assert find_signed_url(html, _ASSET_URL2) is None

    def test_find_signed_url_full_base64_jwt(self):
        """Regression (live 2026-10-10): a real GitHub signed URL carries a
        base64url JWT whose segments contain ``s`` and ``/``.

        The delimiter class must use the whitespace escape (backslash-``s``)
        as a *character class*, not exclude a literal ``s`` — writing
        ``\\s`` inside a raw-string character class makes the regex see
        backslash+``s`` and truncates the URL at the first ``s``, making the
        download 404. The full URL (827 bytes in the live probe) must be
        returned intact.
        """
        from autoswe.attachments.github import find_signed_url

        jwt = (
            "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9"
            ".eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIs"
            "ImtleSI6InVzZXItYXR0YWNobWVudHMvIiwic2lnIjoiYWJjL3Nsb3NoL3Mvc2lnbmF0dXJl" + "/x/s="
        )
        signed = f"https://private-user-images.githubusercontent.com/185386482/670244241-{_UUID}.jpg?jwt={jwt}"
        html = f'<p><img src="{signed}" /></p>'
        assert find_signed_url(html, _ASSET_URL) == signed
        # The extraction must survive a ``s`` and a ``/`` inside the JWT.
        assert "s" in jwt and "/" in jwt
        assert len(find_signed_url(html, _ASSET_URL)) == len(signed)


# ============================================================================
# Azure discovery + download
# ============================================================================

class TestAzure:
    def test_discover_attached_file_relations(self):
        from autoswe.attachments import azure as az

        relations = [
            {"rel": "AttachedFile",
             "url": "https://dev.azure.com/o/p/_apis/wit/attachments/aaa",
             "attributes": {"name": "data.csv", "resourceSize": 74}},
            {"rel": "ArtifactLink", "url": "https://x/other"},
        ]
        refs = az.discover_azure_attachments(relations)
        assert len(refs) == 1
        assert refs[0].name == "data.csv"
        assert refs[0].resource_size == 74
        assert refs[0].url.endswith("/aaa")

    def test_discover_no_name(self):
        from autoswe.attachments import azure as az

        relations = [{"rel": "AttachedFile", "url": "https://x/a",
                     "attributes": {"resourceSize": 10}}]
        refs = az.discover_azure_attachments(relations)
        assert refs[0].name is None

    def test_discover_empty(self):
        from autoswe.attachments import azure as az

        assert az.discover_azure_attachments([]) == []
        assert az.discover_azure_attachments(None) == []

    def test_download_azure_uses_basic_auth(self, monkeypatch):
        import base64

        from autoswe.attachments import azure as az

        captured = {}

        def fake_download(url, *, max_bytes, headers=None, opener=None):
            captured.update(headers or {})
            return b"bytestuff"

        monkeypatch.setattr(az.downloads, "download_bytes", fake_download)
        data = az.download_azure_attachment("https://x/a", "mypat", max_bytes=100)
        assert data == b"bytestuff"
        expected = "Basic " + base64.b64encode(b":mypat").decode()
        assert captured["Authorization"] == expected


# ============================================================================
# End-to-end ingest (provider-agnostic temp-dir lifecycle + caps)
# ============================================================================

class _StubTracker:
    """A minimal tracker: provides list_workitem_attachments for azure."""

    provider = "github"

    def __init__(self, refs=None):
        self.refs = refs or []

    def list_workitem_attachments(self, issue_number):
        return self.refs


class TestIngestGithub:
    def test_ingest_stores_to_temp_dir(self, monkeypatch, tmp_path):
        from autoswe.attachments import github as gh
        from autoswe.attachments import ingest

        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
        monkeypatch.setattr(
            gh.downloads, "download_bytes",
            lambda url, **k: png,
        )

        body = f"see {_ASSET_URL}"
        set_ = ingest.ingest_task_attachments(
            _StubTracker(), 1, body, [], {"ATTACHMENTS_ENABLED": True},
            {"provider": "github", "owner": "o", "repo": "r", "pat": "t"},
        )
        assert set_ is not None
        assert set_.items, "expected at least one attachment"
        a = set_.items[0]
        assert a.path.parent == set_.dir
        assert a.path.read_bytes() == png
        assert a.content_type == "image/png"
        # temp dir lives outside the worktree (tmp dir based)
        assert set_.dir.name.startswith("autoswe-attach-")
        set_.remove()
        assert not set_.dir.exists()

    def test_ingest_disabled_returns_none(self):
        from autoswe.attachments import ingest

        body = f"see {_ASSET_URL}"
        set_ = ingest.ingest_task_attachments(
            _StubTracker(), 1, body, [],
            {"ATTACHMENTS_ENABLED": False},
            {"provider": "github", "owner": "o", "repo": "r", "pat": "t"},
        )
        assert set_ is None

    def test_ingest_no_attachments_returns_none(self, monkeypatch):
        from autoswe.attachments import ingest

        set_ = ingest.ingest_task_attachments(
            _StubTracker(), 1, "no attachments", [],
            {"ATTACHMENTS_ENABLED": True},
            {"provider": "github", "owner": "o", "repo": "r", "pat": "t"},
        )
        assert set_ is None

    def test_ingest_best_effort_failure_no_task_failure(self, monkeypatch):
        """A failing download warns + skips; the task is not failed."""
        from autoswe.attachments import downloads, ingest
        from autoswe.attachments import github as gh

        def fake_download(url, **k):
            raise downloads.DownloadError(url, "http_500", "server error")

        monkeypatch.setattr(gh.downloads, "download_bytes", fake_download)
        body = f"see {_ASSET_URL}"
        set_ = ingest.ingest_task_attachments(
            _StubTracker(), 1, body, [],
            {"ATTACHMENTS_ENABLED": True},
            {"provider": "github", "owner": "o", "repo": "r", "pat": "t"},
        )
        # No exception raised; empty result (nothing ingested).
        assert set_ is None

    def test_ingest_per_file_cap_enforced(self, monkeypatch):
        from autoswe.attachments import github as gh
        from autoswe.attachments import ingest

        big = b"\x00" * 300
        monkeypatch.setattr(
            gh.downloads, "download_bytes",
            lambda url, **k: big,
        )
        body = f"see {_ASSET_URL}"
        set_ = ingest.ingest_task_attachments(
            _StubTracker(), 1, body, [],
            {"ATTACHMENTS_ENABLED": True, "ATTACHMENT_MAX_SIZE_BYTES": 100},
            {"provider": "github", "owner": "o", "repo": "r", "pat": "t"},
        )
        # The download itself is capped at max_size by download_bytes; here
        # the stub returns 300 bytes regardless, so the ingest-level cap
        # skips it. Result: nothing ingested.
        assert set_ is None


class TestIngestAzure:
    def test_ingest_azure_stores(self, monkeypatch):
        from autoswe.attachments import azure as az
        from autoswe.attachments import ingest

        csv = b"id,name\n1,foo\n"
        monkeypatch.setattr(az.downloads, "download_bytes", lambda url, **k: csv)

        refs = [{"url": "https://dev.azure.com/o/p/_apis/wit/attachments/aaa",
                 "name": "data.csv", "resource_size": 14}]
        set_ = ingest.ingest_task_attachments(
            _StubTracker(refs=refs), 218, "", [],
            {"ATTACHMENTS_ENABLED": True},
            {"provider": "azure", "pat": "p"},
        )
        assert set_ is not None
        assert len(set_.items) == 1
        a = set_.items[0]
        assert a.name == "data.csv"
        assert a.path.read_bytes() == csv
        assert a.provider == "azure"
        set_.remove()

    def test_ingest_azure_no_name_sniffs(self, monkeypatch):
        from autoswe.attachments import azure as az
        from autoswe.attachments import ingest

        csv = b"id,name\n1,foo\n"
        monkeypatch.setattr(az.downloads, "download_bytes", lambda url, **k: csv)

        refs = [{"url": "https://x/aaa", "name": None, "resource_size": 14}]
        set_ = ingest.ingest_task_attachments(
            _StubTracker(refs=refs), 1, "", [],
            {"ATTACHMENTS_ENABLED": True},
            {"provider": "azure", "pat": "p"},
        )
        assert set_ is not None
        # No provider name -> sniff -> .txt
        assert set_.items[0].name.endswith(".txt")
        set_.remove()

    def test_github_alt_used_only_when_filename_like(self, monkeypatch):
        """Design doc §3: a GitHub markdown alt is used as the on-disk name
        only when it *looks* like a filename; prose alts fall through to
        magic-byte sniffing (never used verbatim as a filename)."""
        from autoswe.attachments import github as gh
        from autoswe.attachments import ingest

        csv = b"col1,col2\n1,2\n"
        monkeypatch.setattr(gh.downloads, "download_bytes", lambda url, **k: csv)

        # Prose alt: "the failing input" must NOT become the filename.
        body = f"![the failing input]({_ASSET_URL})"
        set_ = ingest.ingest_task_attachments(
            _StubTracker(), 1, body, [],
            {"ATTACHMENTS_ENABLED": True},
            {"provider": "github", "owner": "o", "repo": "r", "pat": "t"},
        )
        assert set_ is not None
        assert set_.items[0].name == "attachment-1.txt"
        assert "/" not in set_.items[0].name
        set_.remove()

        # Filename-like alt is preferred verbatim.
        set_ = ingest.ingest_task_attachments(
            _StubTracker(), 1, f"![failing-input.csv]({_ASSET_URL2})", [],
            {"ATTACHMENTS_ENABLED": True},
            {"provider": "github", "owner": "o", "repo": "r", "pat": "t"},
        )
        assert set_ is not None
        assert set_.items[0].name == "failing-input.csv"
        set_.remove()

    def test_ingest_content_type_resolution(self, monkeypatch):
        """Manifest content type: sniff wins for binary; the on-disk
        extension map is preferred only when the sniff is generic text."""
        from autoswe.attachments import azure as az
        from autoswe.attachments import ingest

        csv = b"id,name\n1,foo\n"
        monkeypatch.setattr(az.downloads, "download_bytes", lambda url, **k: csv)
        refs = [{"url": "https://x/aaa", "name": "data.csv", "resource_size": 14}]
        set_ = ingest.ingest_task_attachments(
            _StubTracker(refs=refs), 1, "", [],
            {"ATTACHMENTS_ENABLED": True},
            {"provider": "azure", "pat": "p"},
        )
        # data.csv is genuinely text -> the .csv extension type is preferred.
        assert set_.items[0].content_type == "text/csv"
        set_.remove()

        # Same name, PNG bytes: the magic-byte sniff must win over the name.
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
        monkeypatch.setattr(az.downloads, "download_bytes", lambda url, **k: png)
        set_ = ingest.ingest_task_attachments(
            _StubTracker(refs=refs), 1, "", [],
            {"ATTACHMENTS_ENABLED": True},
            {"provider": "azure", "pat": "p"},
        )
        assert set_.items[0].name == "data.csv"
        assert set_.items[0].content_type == "image/png"
        set_.remove()


# ============================================================================
# Manifest + prompt injection
# ============================================================================

class TestManifest:
    def test_render_manifest_empty(self):
        from autoswe.attachments.models import AttachmentSet, render_manifest

        assert render_manifest(None) == ""
        assert render_manifest(AttachmentSet(dir=None)) == ""

    def test_render_manifest_block(self, tmp_path):
        from autoswe.attachments.models import Attachment, AttachmentSet, render_manifest

        p = tmp_path / "autoswe-attach-x"
        p.mkdir()
        f = p / "data.csv"
        f.write_bytes(b"x,y\n1,2\n")
        att = AttachmentSet(dir=p, items=[Attachment(
            path=f, name="data.csv", content_type="text/csv", size_bytes=6,
        )])
        block = render_manifest(att)
        assert block.startswith("Attached files available locally (temp dir, read-only):")
        assert str(f) in block
        assert "(text/csv, 6 bytes)" in block

    def test_plan_prompt_includes_manifest(self, monkeypatch):
        from pathlib import Path

        from autoswe.attachments.models import Attachment, AttachmentSet
        from autoswe.harness.prompts import build_plan_prompt

        p = Path("/tmp/autoswe-attach-test")
        p.mkdir(parents=True, exist_ok=True)
        f = p / "failing-input.csv"
        f.write_bytes(b"a,b\n1,2\n")
        att = AttachmentSet(dir=p, items=[Attachment(
            path=f, name="failing-input.csv", content_type="text/csv", size_bytes=6,
        )])

        task = {
            "owner": "o", "repo": "r", "issue_number": 1, "title": "t",
            "body": "body text", "plan_file_path": None,
            "_attachment_set": att,
        }
        prompt = build_plan_prompt(
            task, comments=[], repo_cfg={"owner": "o", "repo": "r", "token": ""},
        )
        assert "Attached files available locally" in prompt
        assert str(f) in prompt
        assert "(text/csv, 6 bytes)" in prompt

    def test_fix_prompt_includes_manifest(self, monkeypatch):
        from pathlib import Path

        from autoswe.attachments.models import Attachment, AttachmentSet
        from autoswe.harness.prompts import build_fix_prompt

        p = Path("/tmp/autoswe-attach-test2")
        p.mkdir(parents=True, exist_ok=True)
        f = p / "log.txt"
        f.write_bytes(b"line1\n")
        att = AttachmentSet(dir=p, items=[Attachment(
            path=f, name="log.txt", content_type="text/plain", size_bytes=6,
        )])

        task = {
            "owner": "o", "repo": "r", "issue_number": 1, "title": "t",
            "body": "body", "plan_file_path": None, "_attachment_set": att,
        }
        prompt = build_fix_prompt(
            task, repo_root=None, comments=[], repo_cfg={"owner": "o", "repo": "r"},
        )
        assert "Attached files available locally" in prompt
        assert str(f) in prompt

    def test_review_prompt_includes_manifest(self, monkeypatch):
        from pathlib import Path

        from autoswe.attachments.models import Attachment, AttachmentSet
        from autoswe.harness.prompts import build_review_prompt

        p = Path("/tmp/autoswe-attach-test3")
        p.mkdir(parents=True, exist_ok=True)
        f = p / "crash.log"
        f.write_bytes(b"boom\n")
        att = AttachmentSet(dir=p, items=[Attachment(
            path=f, name="crash.log", content_type="text/plain", size_bytes=5,
        )])

        task = {
            "owner": "o", "repo": "r", "issue_number": 1, "title": "t",
            "body": "body", "plan_file_path": None, "_attachment_set": att,
        }
        prompt = build_review_prompt(
            task, repo_root=None, comments=[],
            repo_cfg={"owner": "o", "repo": "r"},
        )
        assert "Attached files available locally" in prompt
        assert str(f) in prompt
        assert "(text/plain, 5 bytes)" in prompt

    def test_prompt_without_attachments_has_no_block(self, monkeypatch):
        from autoswe.harness.prompts import build_plan_prompt

        task = {
            "owner": "o", "repo": "r", "issue_number": 1, "title": "t",
            "body": "body", "plan_file_path": None,
        }
        prompt = build_plan_prompt(
            task, comments=[], repo_cfg={"owner": "o", "repo": "r", "token": ""},
        )
        assert "Attached files available locally" not in prompt


# ============================================================================
# Stale-dir sweep
# ============================================================================

class TestStaleSweep:
    def test_sweep_removes_old_autoswe_dirs(self, tmp_path):
        from autoswe.attachments.ingest import sweep_stale_dirs

        old = tmp_path / "autoswe-attach-old"
        old.mkdir()
        (old / "a.txt").write_text("x")
        recent = tmp_path / "autoswe-attach-new"
        recent.mkdir()
        other = tmp_path / "not-autoswe-old"
        other.mkdir()
        now = time.time()
        old_time = now - 48 * 3600

        import os

        os.utime(old, (old_time, old_time))
        os.utime(other, (old_time, old_time))

        removed = sweep_stale_dirs(root=str(tmp_path), stale_seconds=24 * 3600, now=now)
        assert removed == 1
        assert not old.exists()
        assert recent.exists()  # fresh, kept
        assert other.exists()  # wrong prefix, kept

    def test_sweep_no_match(self, tmp_path):
        from autoswe.attachments.ingest import sweep_stale_dirs

        # No autoswe dirs at all.
        assert sweep_stale_dirs(root=str(tmp_path)) == 0

    def test_sweep_missing_root(self, tmp_path):
        from autoswe.attachments.ingest import sweep_stale_dirs

        assert sweep_stale_dirs(root=str(tmp_path / "nope")) == 0


# ============================================================================
# Config resolution
# ============================================================================

class TestConfig:
    def test_defaults(self):
        from autoswe.attachments.ingest import (
            DEFAULT_MAX_SIZE_BYTES,
            DEFAULT_MAX_TOTAL_BYTES,
            resolve_attachment_cfg,
        )

        acfg = resolve_attachment_cfg({}, {})
        assert acfg["enabled"] is True
        assert acfg["max_size_bytes"] == DEFAULT_MAX_SIZE_BYTES
        assert acfg["max_total_bytes"] == DEFAULT_MAX_TOTAL_BYTES

    def test_env_values(self):
        from autoswe.attachments.ingest import resolve_attachment_cfg

        acfg = resolve_attachment_cfg(
            {"ATTACHMENTS_ENABLED": False,
             "ATTACHMENT_MAX_SIZE_BYTES": 123,
             "ATTACHMENT_MAX_TOTAL_BYTES": 456},
            {},
        )
        assert acfg["enabled"] is False
        assert acfg["max_size_bytes"] == 123
        assert acfg["max_total_bytes"] == 456

    def test_per_repo_override(self):
        from autoswe.attachments.ingest import resolve_attachment_cfg

        acfg = resolve_attachment_cfg(
            {"ATTACHMENTS_ENABLED": True, "ATTACHMENT_MAX_SIZE_BYTES": 100},
            {"attachments_enabled": False, "attachment_max_size_bytes": 200},
        )
        assert acfg["enabled"] is False
        assert acfg["max_size_bytes"] == 200
        # total not overridden -> global
        assert acfg["max_total_bytes"] == 25 * 1024 * 1024


# ============================================================================
# Provider seam
# ============================================================================

class TestProviderSeam:
    def test_github_tracker_no_attachments(self, fake_token):
        from autoswe.providers.github.tracker import GitHubTracker

        tracker = GitHubTracker({"owner": "o", "repo": "r", "token": fake_token})
        assert tracker.list_workitem_attachments(1) == []

    def test_azure_tracker_attachments(self, monkeypatch):
        from autoswe.providers.azure import tracker as az_tracker
        from autoswe.providers.azure.tracker import AzureTracker

        raw = {
            "id": 218,
            "relations": [
                {"rel": "AttachedFile",
                 "url": "https://dev.azure.com/o/p/_apis/wit/attachments/aaa",
                 "attributes": {"name": "data.csv", "resourceSize": 74}},
                {"rel": "ArtifactLink", "url": "https://x"},
            ],
        }

        def fake_ado_get(path, pat, max_retries=3):
            return raw

        monkeypatch.setattr(az_tracker, "ado_get", fake_ado_get)
        tracker = AzureTracker({"provider": "azure", "org": "o",
                                "project": "p", "repo": "r", "pat": "pat"})
        refs = tracker.list_workitem_attachments(218)
        assert len(refs) == 1
        assert refs[0]["name"] == "data.csv"
        assert refs[0]["resource_size"] == 74
        assert refs[0]["url"].endswith("/aaa")

    def test_azure_tracker_no_relations(self, monkeypatch):
        from autoswe.providers.azure import tracker as az_tracker
        from autoswe.providers.azure.tracker import AzureTracker

        monkeypatch.setattr(az_tracker, "ado_get", lambda path, pat, max_retries=3: {"id": 1, "relations": []})
        tracker = AzureTracker({"provider": "azure", "org": "o",
                                "project": "p", "repo": "r", "pat": "pat"})
        assert tracker.list_workitem_attachments(1) == []

    def test_azure_tracker_fetch_failure_returns_empty(self, monkeypatch):
        from autoswe.providers.azure import tracker as az_tracker
        from autoswe.providers.azure.tracker import AzureTracker

        def boom(path, pat, max_retries=3):
            raise RuntimeError("network down")

        monkeypatch.setattr(az_tracker, "ado_get", boom)
        tracker = AzureTracker({"provider": "azure", "org": "o",
                                "project": "p", "repo": "r", "pat": "pat"})
        assert tracker.list_workitem_attachments(1) == []

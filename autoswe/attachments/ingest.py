"""Provider-agnostic attachment ingestion at task setup (issue #290).

``ingest_task_attachments`` downloads every attachment referenced by an
issue/work item into a **temp folder** (never the worktree, never the repo)
and returns an :class:`~autoswe.attachments.models.AttachmentSet` whose
manifest the planner/coder/reviewer prompts append.

Design (authoritative: ``docs/autoswe/attachments.md``):
- **Discover** — GitHub: regex over body + comments; Azure: ``AttachedFile``
  relations from the ``$expand=all`` fetch.
- **Download** — best-effort per attachment; a failure logs a warning and
  continues. A missing/unreachable attachment is **never** a task failure.
- **Name & store** — provider name when trustworthy → magic-byte sniff →
  ``attachment-<n>.<ext>``. Path-traversal guard on every provider-supplied
  name. Per-file and per-total size caps enforced before writing bytes.
- **Cleanup** — the dispatch loop removes the temp dir in a ``finally`` on
  task teardown; :func:`sweep_stale_dirs` at poller start handles leftovers.
"""
from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path

from autoswe.attachments import azure as az
from autoswe.attachments import github as gh
from autoswe.attachments.models import Attachment, AttachmentSet
from autoswe.attachments.naming import looks_like_filename, pick_filename, sniff_content
from autoswe.core.logging_utils import get_debug_logger

dbg = get_debug_logger()

DEFAULT_MAX_SIZE_BYTES = 10 * 1024 * 1024        # 10 MiB per file
DEFAULT_MAX_TOTAL_BYTES = 25 * 1024 * 1024       # 25 MiB per issue
STALE_SECONDS = 24 * 60 * 60                     # 24 h


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _coerce_bytes(value, default: int) -> int:
    """Coerce a config value to a positive byte count (or *default*)."""
    try:
        n = int(str(value).strip())
        return n if n > 0 else default
    except (TypeError, ValueError):
        return default


def resolve_attachment_cfg(cfg: dict | None, repo_cfg: dict | None) -> dict:
    """Resolve the attachment config block (issue #290 §Design item 5).

    Keys (all per-repo-overridable, lowercase beats the global cfg):
    - ``enabled`` (default ``True``)
    - ``max_size_bytes`` (default 10 MiB / file)
    - ``max_total_bytes`` (default 25 MiB / issue)
    """
    cfg = cfg or {}
    rc = repo_cfg or {}

    def flag(name: str, default: bool) -> bool:
        ov = rc.get(name.lower())
        if ov is not None:
            return bool(ov)
        if name.upper() in cfg:
            return bool(cfg[name.upper()])
        return default

    def ints(name: str, default: int) -> int:
        ov = rc.get(name.lower())
        if ov is not None:
            return _coerce_bytes(ov, default)
        if name.upper() in cfg:
            return _coerce_bytes(cfg[name.upper()], default)
        return default

    return {
        "enabled": flag("attachments_enabled", True),
        "max_size_bytes": ints("attachment_max_size_bytes", DEFAULT_MAX_SIZE_BYTES),
        "max_total_bytes": ints("attachment_max_total_bytes", DEFAULT_MAX_TOTAL_BYTES),
    }


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

def _store(
    data: bytes,
    dest_dir: Path,
    preferred_name: str | None,
    used: set[str],
    index: int,
    provider: str,
    source_url: str,
) -> Attachment:
    """Name + write one downloaded blob into *dest_dir* (flat).

    The magic-byte sniff is the robust content source (design doc §1.6 —
    never trust the URL extension or the served Content-Type). The manifest
    content type prefers the sniff; it falls back to the on-disk name's
    extension map (``guess_content_type``) **only when the sniff is
    ``txt``** — so a genuinely-text ``data.csv`` reports ``text/csv``, a
    ``data.csv`` holding PNG bytes reports ``image/png``, and an unknown
    binary blob named ``data.csv`` keeps ``application/octet-stream`` rather
    than the misleading ``text/csv``.
    """
    from autoswe.attachments.naming import guess_content_type

    name = pick_filename(preferred_name, data, used, index)
    # Guard against a trailing dot leaking in ("data.csv.") — prefer the
    # provider name without it so the extension map / content-type fallback
    # resolves on the real extension (Requirement 3).
    name = name.rstrip(".") or name
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    ext_ct = guess_content_type(ext) if ext else ""
    sniff_ext, sniff_ct = sniff_content(data)
    # Only text is ambiguous enough to trust the extension for. A binary
    # sniff (png/jpg/zip/… *or* unknown ``bin``) is authoritative: an
    # unknown binary named ``.csv`` must not be reported as ``text/csv``.
    # ``ext_ct`` is "" when the on-disk name has no extension — in that case
    # keep the sniff so the manifest never shows an empty content type.
    if sniff_ext == "txt" and ext_ct != "application/octet-stream" and ext_ct:
        content_type = ext_ct
    else:
        content_type = sniff_ct
    path = dest_dir / name
    path.write_bytes(data)
    return Attachment(
        path=path, name=name, content_type=content_type,
        size_bytes=len(data), provider=provider, source_url=source_url,
    )


def ingest_task_attachments(
    tracker,
    issue_number: int,
    body: str,
    comments: list,
    cfg: dict,
    repo_cfg: dict,
    *,
    opener=None,
) -> AttachmentSet | None:
    """Ingest all attachments for a task into a fresh temp dir.

    Returns an :class:`AttachmentSet` (possibly empty) or ``None`` when
    attachment ingestion is disabled or nothing was found. Never raises —
    any per-attachment failure is logged and skipped.
    """
    acfg = resolve_attachment_cfg(cfg, repo_cfg)
    if not acfg["enabled"]:
        return None

    provider = (repo_cfg or {}).get("provider", "github").lower()
    try:
        dest_dir = Path(tempfile.mkdtemp(prefix="autoswe-attach-"))
    except OSError as e:
        dbg.warning("attachments: could not create temp dir: %s", e)
        return None

    used: set[str] = set()
    total_state = {"total": 0}
    items: list[Attachment] = []
    index = 1

    try:
        if provider == "github":
            token = (repo_cfg or {}).get("pat") or (repo_cfg or {}).get("token", "")
            raw_comments = [
                {"id": getattr(c, "id", None), "body": getattr(c, "body", "") or ""}
                for c in (comments or [])
            ]
            for ctx in gh.discover_github_assets(body or "", raw_comments):
                try:
                    data = gh.download_github_asset(
                        ctx.url,
                        owner=(repo_cfg or {}).get("owner", ""),
                        repo=(repo_cfg or {}).get("repo", ""),
                        issue_num=issue_number,
                        token=token,
                        max_bytes=acfg["max_size_bytes"],
                        context=ctx,
                        opener=opener,
                    )
                except Exception as e:
                    dbg.warning("attachments: GitHub asset %s failed: %s", ctx.url, e)
                    continue
                if len(data) > acfg["max_size_bytes"]:
                    dbg.warning("attachments: GitHub asset exceeds cap: %s", ctx.url)
                    continue
                if total_state["total"] + len(data) > acfg["max_total_bytes"]:
                    dbg.warning("attachments: total cap reached; skipping %s", ctx.url)
                    break
                total_state["total"] += len(data)
                # A markdown ``alt`` is free text the issue author chose — it
                # is a filename only when it *looks* like one (design doc
                # §Design item 3); prose alts fall through to magic-byte
                # sniffing.
                alt = ctx.alt if looks_like_filename(ctx.alt) else None
                try:
                    items.append(_store(data, dest_dir, alt, used, index, "github", ctx.url))
                except OSError as e:
                    # Disk full / permission error while writing this file —
                    # best-effort: skip just this asset and keep going.
                    dbg.warning("attachments: could not store %s: %s", ctx.url, e)
                    continue
                index += 1
        elif provider == "azure":
            pat = (repo_cfg or {}).get("pat") or (repo_cfg or {}).get("token", "")
            list_refs = getattr(tracker, "list_workitem_attachments", None)
            raw_refs = list_refs(issue_number) if callable(list_refs) else []
            refs = _normalize_azure_refs(raw_refs)
            for ref in refs:
                try:
                    data = az.download_azure_attachment(
                        ref.url, pat, max_bytes=acfg["max_size_bytes"], opener=opener,
                    )
                except Exception as e:
                    dbg.warning("attachments: Azure asset %s failed: %s", ref.url, e)
                    continue
                if len(data) > acfg["max_size_bytes"]:
                    dbg.warning("attachments: Azure asset exceeds cap: %s", ref.url)
                    continue
                if total_state["total"] + len(data) > acfg["max_total_bytes"]:
                    dbg.warning("attachments: total cap reached; skipping %s", ref.url)
                    break
                total_state["total"] += len(data)
                try:
                    items.append(_store(data, dest_dir, ref.name, used, index, "azure", ref.url))
                except OSError as e:
                    # Disk full / permission error while writing this file —
                    # best-effort: skip just this asset and keep going.
                    dbg.warning("attachments: could not store %s: %s", ref.url, e)
                    continue
                index += 1
        else:
            # Unknown provider — no known attachment source.
            dbg.debug("attachments: provider %r has no attachment source", provider)
    except Exception as e:
        # A failure that escaped the per-attachment guards (e.g. the write
        # inside ``_store``) would otherwise propagate to the dispatch
        # wrapper's blanket ``except`` — which returns ``None`` with no
        # AttachmentSet — leaving *dest_dir* (possibly with partial bytes)
        # behind until the 24h stale sweep. Remove it here so the temp dir
        # never leaks regardless of where the failure lands. Best-effort per
        # spec: never a task failure.
        dbg.warning(
            "attachments: ingest failed; removing temp dir: %s: %s",
            type(e).__name__, e,
        )
        try:
            shutil.rmtree(dest_dir, ignore_errors=True)
        except Exception:
            pass
        return None
    if not items:
        # Nothing to show — don't leave an empty dir behind.
        try:
            shutil.rmtree(dest_dir, ignore_errors=True)
        except Exception:
            pass
        return None
    return AttachmentSet(dir=dest_dir, items=items)


def _normalize_azure_refs(raw_refs: list) -> list:
    """Coerce Azure attachment refs to ``AzureAttachmentRef`` objects.

    Accepts either the tracker's normalized shape (``{"url", "name",
    "resource_size"}``) or raw ADO relations (``{"rel", "url", "attributes"}
    with ``rel == "AttachedFile"``), so the ingest layer works whether the
    tracker pre-normalized the refs or handed us the raw ``relations[]``.
    Each item is shape-checked individually — a mixed list (a normalized ref
    next to a raw relation) is handled per item rather than dispatched on the
    first element's shape.
    """
    if not raw_refs:
        return []

    def _is_raw(r) -> bool:
        # A raw ADO relation carries ``rel``/``attributes``; the tracker's
        # normalized shape (``{url, name, resource_size}``) carries neither.
        return isinstance(r, dict) and ("rel" in r or "attributes" in r)

    raw_relations = [r for r in raw_refs if _is_raw(r)]
    normalized = [
        r for r in raw_refs
        if not _is_raw(r) and isinstance(r, dict) and r.get("url")
    ]
    refs: list = []
    if raw_relations:
        # ``discover_azure_attachments`` filters to ``AttachedFile`` with a
        # ``url`` internally, so non-attachment relations (e.g. ArtifactLink)
        # are dropped here.
        refs.extend(az.discover_azure_attachments(raw_relations))
    for r in normalized:
        refs.append(az.AzureAttachmentRef(
            url=r["url"],
            name=r.get("name"),
            resource_size=r.get("resource_size"),
        ))
    return refs


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def _is_stale(path: Path, now: float, stale_seconds: float) -> bool:
    """True when *path* is an autoswe temp dir older than *stale_seconds*."""
    if not path.is_dir():
        return False
    if not path.name.startswith("autoswe-attach-"):
        return False
    try:
        return (now - path.stat().st_mtime) > stale_seconds
    except OSError:
        return False


def sweep_stale_dirs(
    root: str | None = None,
    *,
    stale_seconds: float = STALE_SECONDS,
    now: float | None = None,
) -> int:
    """Remove stale ``autoswe-attach-*`` temp dirs (crash leftovers).

    Runs at poller start. Returns the number of dirs removed. *root* defaults
    to the OS temp dir. Only directories whose mtime is older than
    *stale_seconds* (default 24 h) and whose name matches the prefix are
    touched — never user temp files.
    """
    now = now if now is not None else time.time()
    base = Path(root) if root else Path(tempfile.gettempdir())
    if not base.exists():
        return 0
    removed = 0
    for child in base.iterdir():
        if _is_stale(child, now, stale_seconds):
            try:
                shutil.rmtree(child, ignore_errors=True)
                # ``ignore_errors=True`` swallows per-file failures; count a
                # dir only when it is actually gone, so the return value
                # never overcounts.
                if not child.exists():
                    removed += 1
            except Exception as e:
                dbg.debug("attachments: sweep failed for %s: %s", child, e)
    return removed

"""Attachment ingestion layer (issue #290).

Provider-agnostic discovery + download of issue/work-item attachments at
task setup, stored in a per-task temp dir (never the worktree, never the
repo). See ``docs/autoswe/attachments.md`` (authoritative design).

Public entry point: :func:`autoswe.attachments.ingest.ingest_task_attachments`.
"""
from autoswe.attachments.ingest import (
    DEFAULT_MAX_SIZE_BYTES,
    DEFAULT_MAX_TOTAL_BYTES,
    STALE_SECONDS,
    ingest_task_attachments,
    resolve_attachment_cfg,
    sweep_stale_dirs,
)
from autoswe.attachments.models import Attachment, AttachmentSet, render_manifest

__all__ = [
    "DEFAULT_MAX_SIZE_BYTES",
    "DEFAULT_MAX_TOTAL_BYTES",
    "STALE_SECONDS",
    "Attachment",
    "AttachmentSet",
    "ingest_task_attachments",
    "render_manifest",
    "resolve_attachment_cfg",
    "sweep_stale_dirs",
]

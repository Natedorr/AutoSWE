"""Data shapes for the attachment ingestion layer (issue #290).

An ``AttachmentSet`` is the per-task result of ingesting issue/work-item
attachments into a temp directory (never the worktree, never the repo). The
manifest rendered from it is what the planner/coder/reviewer prompts show the
model — absolute paths, because the temp dir sits outside the worktree.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Attachment:
    """One ingested attachment on disk."""

    path: Path
    name: str
    content_type: str
    size_bytes: int
    provider: str = ""          # "github" | "azure"
    source_url: str = ""        # where the bytes came from (plain/signed/ADO URL)


@dataclass
class AttachmentSet:
    """All attachments for one task, in one temp dir."""

    dir: Path
    items: list[Attachment] = field(default_factory=list)

    @property
    def total_bytes(self) -> int:
        return sum(a.size_bytes for a in self.items)

    def remove(self) -> None:
        """Remove the temp dir and its contents (best-effort, never raises)."""
        try:
            shutil.rmtree(self.dir, ignore_errors=True)
        except Exception:
            pass


def render_manifest(att: AttachmentSet | None) -> str:
    """Render the prompt manifest block (issue #290 §Design item 4).

    Returns ``""`` when there is nothing to show so the caller can append the
    result unconditionally. Paths are absolute — the temp dir is outside the
    worktree, so relative paths would mislead the model.
    """
    if att is None or not att.items:
        return ""
    lines = ["Attached files available locally (temp dir, read-only):"]
    for a in att.items:
        lines.append(f"- {a.path}  ({a.content_type}, {a.size_bytes} bytes)")
    return "\n".join(lines)

"""Azure DevOps attachment discovery + download (issue #290).

Azure has a first-class, documented attachments API (design doc §2, all
live-verified 2026-10-09). Attachments are exposed as work-item **relations**
with ``rel == "AttachedFile"``, but **only when the work item is fetched with
``$expand=all``** — which the Azure tracker already does, so the payload is
present in its fetch today and simply discarded until now.

Discovery: parse ``relations[]`` where ``rel == "AttachedFile"``. The relation
``url`` is the download URL and ``attributes.name`` (when present) is the
original filename. Note: in the live probes ``attributes.name`` was *absent*,
so it must be treated as optional.

Download: ``GET .../_apis/wit/attachments/{id}?api-version=7.1`` with the
standard Basic-PAT header.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib import request

from autoswe.attachments import downloads
from autoswe.core.logging_utils import get_debug_logger

dbg = get_debug_logger()


@dataclass
class AzureAttachmentRef:
    """One ``AttachedFile`` relation on a work item."""

    url: str
    name: str | None = None
    resource_size: int | None = None


def discover_azure_attachments(relations: list[dict] | None) -> list[AzureAttachmentRef]:
    """Parse ``AttachedFile`` relations from a ``$expand=all`` work item.

    *relations* is the raw ``relations[]`` array from the work-item fetch
    (empty/None when absent). Returns refs in document order.
    """
    refs: list[AzureAttachmentRef] = []
    for rel in relations or []:
        if not isinstance(rel, dict):
            continue
        if rel.get("rel") != "AttachedFile":
            continue
        url = rel.get("url")
        if not url:
            continue
        attrs = rel.get("attributes") or {}
        refs.append(AzureAttachmentRef(
            url=url,
            name=attrs.get("name") or None,
            resource_size=attrs.get("resourceSize"),
        ))
    return refs


def download_azure_attachment(
    url: str,
    pat: str,
    *,
    max_bytes: int,
    opener: request.OpenerDirector | None = None,
) -> bytes:
    """GET one Azure attachment with the standard Basic-PAT header.

    Raises :class:`downloads.DownloadError` on any failure.
    """
    import base64

    auth = base64.b64encode((":" + pat).encode()).decode()
    return downloads.download_bytes(
        url,
        max_bytes=max_bytes,
        headers={"Authorization": f"Basic {auth}"},
        opener=opener,
    )

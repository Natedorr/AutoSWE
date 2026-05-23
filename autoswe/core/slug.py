"""Slug helpers — provider-prefixed slugs."""
from __future__ import annotations


def make_slug(provider: str, parts: tuple[str, ...], issue_number: int) -> str:
    """Create a provider-prefixed slug.

    Examples:
        make_slug("github", ("natedorr", "autoswe"), 42)
        → "gh:natedorr_autoswe_42"

        make_slug("azure", ("my-org", "my-proj", "my-repo"), 7)
        → "ado:my-org_my-proj_my-repo_7"
    """
    prefix = {"github": "gh", "azure": "ado"}.get(provider.lower(), provider.lower()[:3])
    joined = "_".join(parts)
    return f"{prefix}:{joined}_{issue_number}"


def slug_to_filename(slug: str) -> str:
    """Sanitize a slug for use as a filesystem filename.

    Replaces characters that are invalid or problematic in filenames:
    - `:` → `_` (e.g. ``ado:org_proj_repo_70`` → ``ado_org_proj_repo_70``)
    - `/` → `_` (e.g. ``ado:natedorr_testProject/testProject_70`` →
                  ``ado_natedorr_testProject_testProject_70``)

    GitHub slugs (``gh:...``) only contain the leading colon, so they become
    ``gh__owner_repo_N``. Azure slugs may also contain slashes in the owner
    field (``org/proj``), so both characters are replaced.

    This is the inverse-safe counterpart for PID, .done, and log file names.
    """
    return slug.replace(":", "_").replace("/", "_")

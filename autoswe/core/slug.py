"""Slug helpers — provider-prefixed slugs."""
from __future__ import annotations


def make_slug(provider: str, parts: tuple[str, ...], issue_number: int) -> str:
    """Create a provider-prefixed slug.

    Examples:
        make_slug("github", ("natedorr", "autoswe"), 42)
        → "gh:natedorr_autoswe_42"

        make_slug("azure", ("my-org", "my-proj", "my-repo"), 7)
        → "ado:my-org_my-proj_my-repo_7"

    The prefix comes from the provider object (``VCSProvider.slug_prefix``),
    not a hardcoded map here, so a new provider supplies its own slug prefix
    (issue #168, seam table).
    """
    prefix = _slug_prefix(provider)
    joined = "_".join(parts)
    return f"{prefix}:{joined}_{issue_number}"


def _slug_prefix(provider: str) -> str:
    """The queue-slug prefix for *provider*, read off the provider object.

    Lazy-imports the factory so this module stays import-light and free of any
    core → provider → core cycle. Falls back to the conventional first-three
    characters for a provider that is not registered yet.
    """
    from autoswe.providers.factory import get_vcs

    try:
        return get_vcs({"provider": provider.lower()}).slug_prefix()
    except ValueError:
        return provider.lower()[:3]


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

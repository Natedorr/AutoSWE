"""Naming + trust helpers for provider-supplied attachment names (issue #290).

Attachment names come from untrusted input: Azure ``attributes.name`` is
set by whoever uploaded the file, and a GitHub markdown ``alt`` is free text
the issue author chose. The path-traversal guard rejects anything that could
escape the flat temp dir; the magic-byte sniffer is the fallback naming
source when no provider-supplied name is trustworthy.
"""
from __future__ import annotations

import mimetypes
import re

# ``alt`` text is only used as a filename when it *looks* like one: a single
# path-free token ending in an extension. Everything else (empty alt, prose
# like "the failing input") falls through to magic-byte sniffing.
_FILENAME_LIKE_RE = re.compile(r"^[\w.\-][\w.\- ]{0,150}$")
_MAX_NAME_LEN = 150

# Magic-byte signatures -> (extension, content-type). Checked in order; the
# first match wins. Order matters: gzip and zip share the "PK" space, and a
# PNG is the only format we can key on both a signature and a text check.
_MAGIC_SIGNATURES: tuple[tuple[bytes, str, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "png", "image/png"),
    (b"\xff\xd8\xff", "jpg", "image/jpeg"),
    (b"GIF87a", "gif", "image/gif"),
    (b"GIF89a", "gif", "image/gif"),
    (b"RIFF", "webp", "image/webp"),  # verified against bytes[8:12] below
    (b"%PDF-", "pdf", "application/pdf"),
    (b"PK\x03\x04", "zip", "application/zip"),
    (b"PK\x05\x06", "zip", "application/zip"),
    (b"\x1f\x8b", "gz", "application/gzip"),
)


def is_trusted_name(name: str | None) -> bool:
    """Return True when *name* is safe to use verbatim as a flat filename.

    Rejects: empty, over-length, anything containing ``/`` or ``\\`` (a
    traversal attempt or a directory component), any occurrence of ``..``,
    absolute paths, and control characters. Everything is attacker-influenced
    on both providers — GitHub ``alt`` is free markdown text, Azure
    ``attributes.name`` is an uploader-chosen value.
    """
    if not name:
        return False
    name = name.strip()
    if not name or len(name) > _MAX_NAME_LEN:
        return False
    if name.startswith(("/", "\\")):
        return False
    if name.startswith(".."):  # windows absolute + leading traversal
        return False
    # A traversal segment anywhere ("../x", "a/..", "a\\..") or a directory
    # separator of any kind fails the guard — files stay flat in the temp dir.
    if "/" in name or "\\" in name or "\x00" in name:
        return False
    if ".." in name:
        return False
    if any(ord(c) < 0x20 for c in name):
        return False
    # Strip the directory part of Windows-style absolute names ("C:\x" is
    # caught by the backslash rule; this catches "C:foo" drive-relative).
    return not re.match(r"^[A-Za-z]:", name)


def looks_like_filename(alt: str | None) -> bool:
    """Heuristic: does a GitHub markdown ``alt`` look like a filename?

    Only a single token (spaces are tolerated inside, e.g. "my data.csv")
    that carries an extension counts. ``"the failing input"`` does not;
    ``"failing-input.csv"`` does.
    """
    if not alt or not is_trusted_name(alt):
        return False
    name = alt.strip()
    if not _FILENAME_LIKE_RE.match(name):
        return False
    stem, _dot, ext = name.rpartition(".")
    return bool(stem) and 1 <= len(ext) <= 10 and ext.isalnum()


def sniff_content(data: bytes) -> tuple[str, str]:
    """Return ``(extension, content_type)`` from magic bytes, or ("bin", octet-stream).

    ``extension`` has no leading dot. Unknown binary falls back to ``bin``;
    decodable UTF-8 text falls back to ``txt``. Content-type resolution is the
    robust naming source (design doc §1.6): never trust the URL extension or
    the served Content-Type for the on-disk name.
    """
    for sig, ext, ctype in _MAGIC_SIGNATURES:
        if data[: len(sig)] == sig:
            if ext == "webp" and data[8:12] != b"WEBP":
                continue
            return ext, ctype
    # Text heuristic: printable-ASCII-heavy with no NULs.
    sample = data[:4096]
    if sample and b"\x00" not in sample:
        try:
            text = sample.decode("utf-8")
            printable = sum(c.isprintable() or c in "\r\n\t" for c in text)
            if printable / max(len(text), 1) > 0.95:
                return "txt", "text/plain"
        except UnicodeDecodeError:
            pass
    return "bin", "application/octet-stream"


def guess_content_type(ext: str) -> str:
    """Best-effort content type for a sniffed/guessed extension."""
    return mimetypes.guess_type(f"file.{ext}")[0] or "application/octet-stream"


def pick_filename(
    preferred: str | None,
    data: bytes,
    used: set[str],
    index: int,
) -> str:
    """Choose the on-disk filename for one attachment.

    Naming chain (design doc §Design item 3): provider-supplied name when
    trustworthy → magic-byte sniff → ``attachment-<n>.<ext>``. The chosen name
    is made unique against *used* so two same-named attachments from one
    issue both land on disk.
    """
    base: str | None = None
    ext: str | None = None
    if is_trusted_name(preferred):
        candidate = preferred.strip()
        stem, dot, maybe_ext = candidate.rpartition(".")
        if dot and stem and 1 <= len(maybe_ext) <= 10:
            base = stem
            ext = maybe_ext
        else:
            base = candidate
    else:
        ext = sniff_content(data)[0]

    if base is None:
        base = f"attachment-{index}"

    # Re-validate the final name — the rpartition split is a no-op on
    # trusted input, but the dedupe suffix must never reintroduce a bad char.
    final = f"{base}.{ext}" if ext else base
    if not is_trusted_name(final):
        final = f"attachment-{index}.{ext or 'bin'}"
    unique = final
    n = 2
    while unique in used:
        unique = f"{base}-{n}.{ext}" if ext else f"{base}-{n}"
        n += 1
    used.add(unique)
    return unique

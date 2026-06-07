"""NDJSON data processor.

Reads an NDJSON file (one JSON object per line), validates that each record
has a ``name`` (string) and ``age`` (integer), and reports valid / invalid counts.
"""

import json
import sys
from pathlib import Path


def validate_record(record: object) -> bool:
    """Return True if *record* is a dict with ``name`` (str) and ``age`` (int).

    ``age`` must be a plain int — booleans are explicitly rejected (bool is a
    subclass of int in Python).
    """
    if not isinstance(record, dict):
        return False
    name = record.get("name")
    age = record.get("age")
    return isinstance(name, str) and isinstance(age, int) and not isinstance(age, bool)


def process_file(filepath: str) -> dict:
    """Process an NDJSON file.

    Streams the file line-by-line (no full-file materialisation), attempts
    JSON decode, then validates.  ``utf-8-sig`` is used so files with a
    BOM are handled transparently.

    Returns ``{"valid": <count>, "invalid": <count>}``.
    """
    valid = 0
    invalid = 0
    with open(filepath, encoding="utf-8-sig") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                invalid += 1
                continue

            if validate_record(record):
                valid += 1
            else:
                invalid += 1
    return {"valid": valid, "invalid": invalid}


def main():
    """Entry point: accept a file path from ``sys.argv[1]``, print a summary."""
    if len(sys.argv) < 2:
        print("Usage: python data_processor.py <file.ndjson>", file=sys.stderr)
        sys.exit(1)
    path = sys.argv[1]
    if not Path(path).exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)
    try:
        result = process_file(path)
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    total = result["valid"] + result["invalid"]
    print(f"Valid records: {result['valid']}")
    print(f"Invalid records: {result['invalid']}")
    print(f"Total: {total}")


if __name__ == "__main__":
    main()

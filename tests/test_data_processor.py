"""Tests for data_processor module — NDJSON validation and CLI entry point."""

import json
import subprocess
import sys

from data_processor import process_file, validate_record

# --- validate_record ---

def test_valid_record():
    assert validate_record({"name": "Alice", "age": 30}) is True


def test_valid_with_extra_fields():
    """Extra fields beyond name/age are allowed."""
    assert validate_record({"name": "Bob", "age": 25, "email": "b@b.com"}) is True


def test_valid_empty_name():
    """Empty string is still a valid str — spec does not require non-empty."""
    assert validate_record({"name": "", "age": 0}) is True


def test_missing_name():
    assert validate_record({"age": 30}) is False


def test_missing_age():
    assert validate_record({"name": "Alice"}) is False


def test_wrong_name_type():
    assert validate_record({"name": 123, "age": 30}) is False


def test_wrong_age_type_string():
    assert validate_record({"name": "Alice", "age": "thirty"}) is False


def test_wrong_age_type_float():
    assert validate_record({"name": "Alice", "age": 30.5}) is False


def test_bool_age_rejected():
    """bool is a subclass of int in Python — must be explicitly rejected."""
    assert validate_record({"name": "Alice", "age": True}) is False
    assert validate_record({"name": "Alice", "age": False}) is False


def test_not_a_dict():
    assert validate_record([1, 2, 3]) is False
    assert validate_record("hello") is False
    assert validate_record(None) is False


def test_empty_dict():
    assert validate_record({}) is False


def test_age_zero_valid():
    assert validate_record({"name": "Baby", "age": 0}) is True


# --- process_file ---

def test_all_valid(tmp_path):
    f = tmp_path / "test.ndjson"
    f.write_text(
        json.dumps({"name": "A", "age": 1}) + "\n"
        + json.dumps({"name": "B", "age": 2}) + "\n"
    )
    assert process_file(str(f)) == {"valid": 2, "invalid": 0}


def test_all_invalid(tmp_path):
    f = tmp_path / "test.ndjson"
    f.write_text("not json\nalso not\n")
    assert process_file(str(f)) == {"valid": 0, "invalid": 2}


def test_mixed_valid_invalid(tmp_path):
    f = tmp_path / "test.ndjson"
    f.write_text(
        json.dumps({"name": "A", "age": 1}) + "\n"
        + "not json\n"
        + json.dumps({"foo": "bar"}) + "\n"
    )
    assert process_file(str(f)) == {"valid": 1, "invalid": 2}


def test_empty_file(tmp_path):
    f = tmp_path / "test.ndjson"
    f.write_text("")
    assert process_file(str(f)) == {"valid": 0, "invalid": 0}


def test_blank_lines_skipped(tmp_path):
    f = tmp_path / "test.ndjson"
    f.write_text(
        json.dumps({"name": "A", "age": 1}) + "\n"
        + "\n"
        + "   \n"
        + json.dumps({"name": "B", "age": 2}) + "\n"
    )
    assert process_file(str(f)) == {"valid": 2, "invalid": 0}


def test_non_dict_json_values(tmp_path):
    """JSON arrays, strings, numbers are not dicts — counted invalid."""
    f = tmp_path / "test.ndjson"
    f.write_text(
        json.dumps([1, 2]) + "\n"
        + json.dumps("just a string") + "\n"
        + json.dumps(42) + "\n"
    )
    assert process_file(str(f)) == {"valid": 0, "invalid": 3}


# --- CLI (main) via subprocess ---

def test_no_args_exits_nonzero():
    result = subprocess.run(
        [sys.executable, "data_processor.py"],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "Usage" in result.stderr


def test_file_not_found():
    result = subprocess.run(
        [sys.executable, "data_processor.py", "nonexistent.ndjson"],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "not found" in result.stderr


def test_successful_run(tmp_path):
    f = tmp_path / "input.ndjson"
    f.write_text(
        json.dumps({"name": "Alice", "age": 30}) + "\n"
        + json.dumps({"name": "Bob", "age": 25}) + "\n"
        + "invalid line\n"
    )
    result = subprocess.run(
        [sys.executable, "data_processor.py", str(f)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "Valid records: 2" in result.stdout
    assert "Invalid records: 1" in result.stdout
    assert "Total: 3" in result.stdout

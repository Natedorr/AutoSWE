"""Canonical API fixture contract tests.

Offline (default): For each fixture in tests/fixtures/api/, a READS map
declares the key-paths the production parser actually consumes. Assert each
path resolves with the expected type. Catches hand-edit errors in fixtures.

Live (@pytest.mark.live): Re-hit the API and assert the live response is a
structural superset of the recorded fixture (every recorded key still present,
same types) — early warning that GitHub or Azure changed something.
"""

import json
from pathlib import Path
from typing import Any

import pytest

API_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api"

# --------------------------------------------------------------------
# Key-path resolution helper

def _resolve_path(obj: Any, path: str) -> Any:
    """Resolve a dotted key path against a dict/list.

    Supports:
      'foo.bar' → obj['foo']['bar']
      'foo[].bar' → [item['bar'] for item in obj['foo']]  (list)
      'foo?' → obj.get('foo')  (optional, returns None if absent or null)
      'fields.System.Title' → obj['fields']['System.Title']  (Azure-style,
        keys with dots — try the combined key first before splitting)
    """
    parts = path.split(".")
    current = obj
    i = 0
    while i < len(parts):
        part = parts[i]
        is_optional = False
        if part.endswith("?"):
            part = part[:-1]
            is_optional = True
        if part.endswith("[]"):
            key = part[:-2]
            items = current.get(key, current if isinstance(current, list) else [])
            if isinstance(items, list):
                return items
            return None

        # Try the current key first, then try combining with the next part
        # (e.g. 'fields.System.Title' → try 'System' then 'System.Title')
        if isinstance(current, dict):
            if part in current:
                current = current[part]
                i += 1
                continue
            # Try combining with next part (Azure-style dotted keys)
            if i + 1 < len(parts):
                next_part = parts[i + 1].rstrip("?")
                combined = f"{part}.{next_part}"
                if combined in current:
                    current = current[combined]
                    i += 2
                    continue
        if is_optional:
            return None
        raise KeyError(f"Missing key: {part!r} in path {path!r}")
    return current


def _check_type(value: Any, type_str: str) -> bool:
    """Check if value matches the expected type string."""
    if type_str == "str":
        return isinstance(value, str)
    if type_str == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if type_str == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if type_str == "bool":
        return isinstance(value, bool)
    if type_str == "list":
        return isinstance(value, list)
    if type_str == "dict":
        return isinstance(value, dict)
    if type_str == "str?":
        return value is None or isinstance(value, str)
    if type_str == "dict?":
        return value is None or isinstance(value, dict)
    if type_str == "list?":
        return value is None or isinstance(value, list)
    if type_str == "int?":
        return value is None or (isinstance(value, int) and not isinstance(value, bool))
    return True


# --------------------------------------------------------------------
# READS maps — declare what the production parser actually consumes

# Format: fixture_file: list of (path, type_str)
# path uses dot notation: 'number', 'labels[].name', 'user.login', 'pull_request?'

GITHUB_READS: dict[str, list[tuple[str, str]]] = {
    "get_user": [
        ("login", "str"), ("id", "int"), ("type", "str"),
    ],
    "list_repos": [
        ("", "list"),
    ],
    "list_repo_labels": [
        ("", "list"),
    ],
    "list_issues": [
        ("", "list"),
    ],
    "get_issue": [
        ("number", "int"), ("title", "str"), ("body", "str"),
        ("state", "str"), ("labels", "list"), ("user", "dict"),
        ("user.login", "str"), ("created_at", "str"),
        ("updated_at", "str"), ("closed_at?", "str?"),
        ("author_association", "str"), ("comments?", "int?"),
        ("pull_request?", "dict?"),
    ],
    "list_issue_comments": [
        ("", "list"),
    ],
    "list_issue_labels": [
        ("", "list"),
    ],
    "create_comment": [
        ("id", "int"), ("body", "str"), ("user", "dict"),
        ("created_at", "str"), ("updated_at", "str"),
    ],
    "replace_labels": [],  # Returns empty dict {}
    "add_assignees": [
        ("login", "str"), ("id", "int"),
    ],
    "create_issue": [
        ("number", "int"), ("title", "str"), ("state", "str"),
    ],
    "list_pulls": [
        ("", "list"),
    ],
    "create_pull": [
        ("number", "int"), ("head", "dict"), ("base", "dict"),
        ("head.ref", "str"), ("base.ref", "str"),
    ],
}

AZURE_READS: dict[str, list[tuple[str, str]]] = {
    "get_current_user": [
        ("uniqueName", "str"), ("id", "str"),
    ],
    "list_repositories": [
        ("count", "int"), ("value", "list"),
    ],
    "wiql_query": [
        ("workItems", "list"),
    ],
    "workitems_batch": [
        ("count", "int"), ("value", "list"),
    ],
    "get_workitem": [
        ("id", "int"), ("fields", "dict"),
    ],
    "list_workitem_comments": [
        ("count", "int"), ("comments", "list"),
    ],
    "create_workitem_comment": [
        ("id", "int"), ("text", "str"), ("createdDate", "str"),
    ],
    "update_workitem": [
        ("", "list"),
    ],
    "create_workitem": [
        ("", "list"),
    ],
    "list_pullrequests": [
        ("count", "int"), ("value", "list"),
    ],
    "create_pullrequest": [
        ("pullRequestId", "int"), ("sourceRefName", "str"),
        ("targetRefName", "str"), ("status", "int"),
    ],
}


def _load_fixture(provider: str, name: str) -> dict:
    path = API_FIXTURE_DIR / provider / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _get_data(fixture: dict) -> Any:
    """Extract the data from a fixture (strip __meta, or use 'data' key for lists)."""
    if "data" in fixture:
        return fixture["data"]
    return {k: v for k, v in fixture.items() if k != "__meta"}


# --------------------------------------------------------------------
# Offline: Validate fixture structure

@pytest.mark.parametrize("fixture_name", list(GITHUB_READS.keys()))
def test_github_fixture_contract(fixture_name: str):
    """Assert GitHub fixture has all keys the production code reads."""
    fixture = _load_fixture("github", fixture_name)
    data = _get_data(fixture)
    reads = GITHUB_READS[fixture_name]
    for path, type_str in reads:
        if not path:
            # Root-level type check
            assert _check_type(data, type_str), (
                f"GitHub {fixture_name}: root type is {type(data).__name__}, expected {type_str}"
            )
        else:
            try:
                value = _resolve_path(data, path)
            except KeyError as e:
                pytest.fail(f"GitHub {fixture_name}: {e}")
            assert _check_type(value, type_str), (
                f"GitHub {fixture_name}: {path} is {type(value).__name__}, expected {type_str}"
            )


@pytest.mark.parametrize("fixture_name", list(AZURE_READS.keys()))
def test_azure_fixture_contract(fixture_name: str):
    """Assert Azure fixture has all keys the production code reads."""
    fixture = _load_fixture("azure", fixture_name)
    data = _get_data(fixture)
    reads = AZURE_READS[fixture_name]
    for path, type_str in reads:
        if not path:
            assert _check_type(data, type_str), (
                f"Azure {fixture_name}: root type is {type(data).__name__}, expected {type_str}"
            )
        else:
            try:
                value = _resolve_path(data, path)
            except KeyError as e:
                pytest.fail(f"Azure {fixture_name}: {e}")
            assert _check_type(value, type_str), (
                f"Azure {fixture_name}: {path} is {type(value).__name__}, expected {type_str}"
            )


def test_azure_workitem_fields_contract():
    """Assert Azure workitem fixture has the expected System.* fields."""
    fixture = _load_fixture("azure", "get_workitem")
    data = _get_data(fixture)
    fields = data["fields"]
    assert "System.Title" in fields, "Missing System.Title field"
    assert isinstance(fields["System.Title"], str)
    assert "System.State" in fields, "Missing System.State field"
    assert isinstance(fields["System.State"], str)


# --------------------------------------------------------------------
# Live: Shape-drift checks (replaced old TestFixtureConsistency classes)

@pytest.mark.live
class TestGitHubLiveShapeDrift:
    """Compare live GitHub API responses with recorded fixtures."""

    def test_live_issue_shape_superset(self, live_token):
        """Live issue response must contain every key in the fixture."""
        from autoswe.tracking.api import gh_get
        live = gh_get("/repos/natedorr/autoswe/issues/1", live_token)
        fixture = _load_fixture("github", "get_issue")
        fixture_data = _get_data(fixture)
        extra = set(fixture_data.keys()) - set(live.keys())
        assert not extra, f"Fixture has keys not in live API: {extra}"

    def test_live_comment_shape_superset(self, live_token):
        """Live comment response must contain every key in the fixture."""
        from autoswe.tracking.api import _fetch_comments
        live_comments = _fetch_comments("natedorr", "autoswe", 1, live_token)
        fixture = _load_fixture("github", "create_comment")
        fixture_data = _get_data(fixture)
        if live_comments and fixture_data:
            live_keys = set(live_comments[0].keys())
            fixture_keys = set(fixture_data.keys())
            extra = fixture_keys - live_keys
            assert not extra, f"Fixture comments have keys not in live API: {extra}"

    def test_live_user_shape_superset(self, live_token):
        """Live user response must contain every key in the fixture."""
        from autoswe.tracking.api import gh_get
        live = gh_get("/user", live_token)
        fixture = _load_fixture("github", "get_user")
        fixture_data = _get_data(fixture)
        extra = set(fixture_data.keys()) - set(live.keys())
        assert not extra, f"Fixture user has keys not in live API: {extra}"


@pytest.mark.live
class TestAzureLiveShapeDrift:
    """Compare live Azure API responses with recorded fixtures."""

    def test_live_workitem_shape_superset(self, ado_live_cfg):
        """Live workitem response must contain every key in the fixture."""
        from autoswe.providers.factory import get_tracker
        tracker = get_tracker(ado_live_cfg)
        issues = tracker.list_open_issues(ado_live_cfg)
        if not issues:
            pytest.skip("No live issues to compare")
        # Fetch the raw workitem
        from autoswe.providers.azure.api import _ado_api_version, ado_get
        wi_url = _ado_api_version(
            f"https://dev.azure.com/{ado_live_cfg['org']}/{ado_live_cfg['project']}"
            f"/_apis/wit/workitems/{issues[0].number}"
        )
        live = ado_get(wi_url, ado_live_cfg["pat"])
        fixture = _load_fixture("azure", "get_workitem")
        fixture_data = _get_data(fixture)
        extra = set(fixture_data.keys()) - set(live.keys())
        assert not extra, f"Fixture workitem has keys not in live API: {extra}"
        if "fields" in live and "fields" in fixture_data:
            field_extra = set(fixture_data["fields"].keys()) - set(live["fields"].keys())
            assert not field_extra, (
                f"Fixture workitem fields has keys not in live API: {field_extra}"
            )

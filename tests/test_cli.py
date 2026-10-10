"""Tests for autoswe.cli — poller drain loop logic."""

from argparse import Namespace
from unittest.mock import patch

# ---------------------------------------------------------------------------
# _cmd_poller drain loop
# ---------------------------------------------------------------------------

def test_poller_non_drain_single_run():
    """Without --drain, the poller runs one full poll cycle."""
    cfg = {"MAX_DRAIN_CYCLES": 50}
    args = Namespace(drain=False, max_cycles=None)

    with patch("autoswe.cli.orch_poll", return_value=0) as mock_poll:
        from autoswe.cli import _cmd_poller
        _cmd_poller(args, cfg)

    mock_poll.assert_called_once_with(cfg, mode="full")


def test_poller_drain_exits_on_zero_tasks():
    """Drain mode exits when a full cycle processes 0 tasks."""
    cfg = {"MAX_DRAIN_CYCLES": 50}
    args = Namespace(drain=True, max_cycles=None)

    with patch("autoswe.cli.orch_poll", return_value=0) as mock_poll:
        from autoswe.cli import _cmd_poller
        _cmd_poller(args, cfg)

    mock_poll.assert_called_once_with(cfg, mode="drain")


def test_poller_drain_calls_once():
    """Drain mode calls orch_poll with drain mode - the drain loop is internal."""
    cfg = {"MAX_DRAIN_CYCLES": 50}
    args = Namespace(drain=True, max_cycles=None)

    with patch("autoswe.cli.orch_poll") as mock_poll:
        # First call returns 2, second returns 0 -> drain exits
        mock_poll.side_effect = [2, 0]
        from autoswe.cli import _cmd_poller
        _cmd_poller(args, cfg)

    # orch_poll is called once with mode="drain"; the drain loop is inside poll()
    assert mock_poll.call_count == 1
    mock_poll.assert_called_with(cfg, mode="drain")


def test_sync_calls_poll_sync_mode():
    """The sync command calls orch_poll in sync-only mode."""
    cfg = {}
    args = Namespace(repo=None)

    with patch("autoswe.cli.orch_poll") as mock_poll:
        from autoswe.cli import _cmd_sync
        _cmd_sync(args, cfg)

    mock_poll.assert_called_once_with(cfg, mode="sync", repo_filter=None)


def test_sync_single_repo_filters():
    """The sync command with --repo passes repo_filter to orch_poll."""
    cfg = {}
    args = Namespace(repo="owner/repo")

    with patch("autoswe.cli.orch_poll") as mock_poll, \
         patch("autoswe.cli.load_repos_config", return_value={"owner/repo": {"provider": "github", "pat": "x"}}):
        from autoswe.cli import _cmd_sync
        _cmd_sync(args, cfg)

    mock_poll.assert_called_once_with(cfg, mode="sync", repo_filter="owner/repo")


def test_sync_passes_cfg_to_load_repos_config():
    """_cmd_sync must pass cfg through so an Azure done_state mismatch is a
    startup error here too (issue #245 §1.5), not only from the poller."""
    cfg = {"done_state": "Resolved"}
    args = Namespace(repo="owner/repo")

    with patch("autoswe.cli.orch_poll"), \
         patch("autoswe.cli.load_repos_config",
               return_value={"owner/repo": {"provider": "github", "pat": "x"}}) as mock_load:
        from autoswe.cli import _cmd_sync
        _cmd_sync(args, cfg)

    mock_load.assert_called_once_with(cfg)


def test_queue_list_passes_cfg_to_load_repos_config():
    """_cmd_queue_list must pass cfg through to load_repos_config (issue #245 §1.5)."""
    cfg = {"done_state": "Resolved"}
    args = Namespace(status=None)
    queue = {"o/r/1": {"id": "o/r/1", "owner": "o", "repo": "r", "issue_number": 1,
                        "created_at": "", "pr_number": None}}

    with patch("autoswe.cli._load_json", return_value=queue), \
         patch("autoswe.cli.load_repos_config", return_value={}) as mock_load:
        from autoswe.cli import _cmd_queue_list
        _cmd_queue_list(args, cfg)

    mock_load.assert_called_once_with(cfg)


def test_queue_status_passes_cfg_to_load_repos_config():
    """_cmd_queue_status must pass cfg through to load_repos_config (issue #245 §1.5)."""
    cfg = {"done_state": "Resolved"}
    args = Namespace(repo="o/r", issue=1, provider="github")
    queue = {"gh:o_r_1": {"id": "gh:o_r_1", "owner": "o", "repo": "r", "issue_number": 1}}

    with patch("autoswe.cli._load_json", return_value=queue), \
         patch("autoswe.cli.load_repos_config", return_value={}) as mock_load:
        from autoswe.cli import _cmd_queue_status
        _cmd_queue_status(args, cfg)

    mock_load.assert_called_once_with(cfg)


def test_dispatch_calls_poll_full_mode():
    """The dispatch command calls orch_poll in full mode."""
    cfg = {}
    args = Namespace()

    with patch("autoswe.cli.orch_poll", return_value=3) as mock_poll:
        from autoswe.cli import _cmd_dispatch
        _cmd_dispatch(args, cfg)

    mock_poll.assert_called_once_with(cfg, mode="full")

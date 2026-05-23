import argparse
import json
import sys
from datetime import datetime, timezone

from autoswe.commands import setup
from autoswe.core.config import LOGS_DIR, QUEUE_FILE, load_config, load_repos_config
from autoswe.core.logging_utils import init_debug_logger, log
from autoswe.core.queue_store import _atomic_write, _load_json
from autoswe.core.slug import make_slug
from autoswe.orch.loop import poll as orch_poll
from autoswe.providers.factory import build_repo_cfg, get_tracker

dbg = init_debug_logger(LOGS_DIR)


def main():
    parser = argparse.ArgumentParser(prog="autoswe", description="autoSWE GitHub Issue Agent")
    sub = parser.add_subparsers(dest="command", required=True)

    p_poller = sub.add_parser("poller", help="Run the full poller loop (sync + dispatch)")
    p_poller.add_argument("--drain", action="store_true", help="Keep processing until idle (re-sync between rounds)")
    p_poller.add_argument("--max-cycles", type=int, metavar="N", help="Max drain cycles (default: MAX_DRAIN_CYCLES or 50)")

    p_sync = sub.add_parser("sync", help="Sync GitHub issue state")
    p_sync.add_argument("--all", action="store_true")
    p_sync.add_argument("--repo", metavar="OWNER/REPO")

    sub.add_parser("dispatch", help="Process pending tasks (inner loop only)")

    p_setup = sub.add_parser("setup", help="Interactive first-run setup wizard")
    p_setup.add_argument("--force", action="store_true", help="Overwrite existing config without prompting")

    p_queue = sub.add_parser("queue", help="Queue management")
    q_sub = p_queue.add_subparsers(dest="queue_cmd", required=True)
    p_ls = q_sub.add_parser("list")
    p_ls.add_argument("--status")
    p_st = q_sub.add_parser("status")
    p_st.add_argument("--repo", required=True, metavar="OWNER/REPO")
    p_st.add_argument("--issue", required=True, type=int)
    p_pr = q_sub.add_parser("prune", help="Remove old done/skipped/closed tasks from the queue")
    p_pr.add_argument("--older-than-days", type=int, default=30, metavar="N",
                      help="Only prune tasks older than N days (default: 30)")
    p_pr.add_argument("--dry-run", action="store_true",
                      help="List tasks that would be pruned without deleting")

    p_st.add_argument("--provider", choices=["github", "azure"], default="github",
                      help="Provider for slug resolution (default: github)")

    args = parser.parse_args()
    cfg = load_config()

    if args.command == "poller":
        _cmd_poller(args, cfg)
    elif args.command == "sync":
        _cmd_sync(args, cfg)
    elif args.command == "dispatch":
        _cmd_dispatch(args, cfg)
    elif args.command == "setup":
        setup.cmd_setup(args, cfg)
    elif args.command == "queue":
        {"list": _cmd_queue_list, "status": _cmd_queue_status, "prune": _cmd_queue_prune}[args.queue_cmd](args, cfg)


def _cmd_poller(args, cfg):
    drain = getattr(args, "drain", False)
    mode = "drain" if drain else "full"
    tasks_processed = orch_poll(cfg, mode=mode)
    if not drain:
        log(f"[POLLER] Poller run complete, {tasks_processed} task(s)")


def _cmd_sync(args, cfg):
    """Sync issue state into queue.json from configured repos (decide-only, no run).

    If --repo is specified, only sync that single repo.
    """
    target_repo = getattr(args, "repo", None)

    if target_repo:
        log(f"[SYNC] Syncing single repo: {target_repo}")
        # Verify the repo exists in repos.json
        repos_cfg = load_repos_config()
        if target_repo not in repos_cfg:
            log(f"[ERROR] Repo '{target_repo}' not found in repos.json")
            sys.exit(1)

    orch_poll(cfg, mode="sync", repo_filter=target_repo)


def _cmd_dispatch(args, cfg):
    """Process pending tasks (one full poll cycle)."""
    tasks_processed = orch_poll(cfg, mode="full")
    log(f"[DISPATCH] Dispatch complete, {tasks_processed} task(s)")


def _cmd_queue_list(args, cfg):
    queue = _load_json(QUEUE_FILE, {})
    if not queue:
        print("Queue is empty.")
        return
    repos_cfg = load_repos_config()
    rows = sorted(queue.values(), key=lambda t: t.get("created_at", ""))
    if getattr(args, "status", None):
        filtered = []
        for t in rows:
            try:
                repo_cfg = build_repo_cfg(t["owner"], t["repo"], cfg, repos_cfg)
                if "provider" in t:
                    repo_cfg["provider"] = t["provider"]
                tracker = get_tracker(repo_cfg)
                issue = tracker.fetch_issue(repo_cfg, t["issue_number"])
                status = tracker.get_status(issue) or "none"
                if status == args.status:
                    filtered.append(t)
            except Exception:
                pass
        rows = filtered
    fmt = "{:<35} {:<14} {:<6} {}"
    print(fmt.format("SLUG", "LABEL STATUS", "PR", "CREATED_AT"))
    print("-" * 75)
    for t in rows:
        label_status = "-"
        try:
            repo_cfg = build_repo_cfg(t["owner"], t["repo"], cfg, repos_cfg)
            if "provider" in t:
                repo_cfg["provider"] = t["provider"]
            if repo_cfg.get("pat"):
                tracker = get_tracker(repo_cfg)
                issue = tracker.fetch_issue(repo_cfg, t["issue_number"])
                label_status = tracker.get_status(issue) or "-"
        except Exception:
            pass
        pr = str(t.get("pr_number") or "")
        created = (t.get("created_at", "") or "")[:16]
        print(fmt.format(t["id"][:35], label_status, pr, created))


def _cmd_queue_status(args, cfg):
    provider = getattr(args, "provider", "github") or "github"
    parts = args.repo.split("/")
    if provider == "azure" and len(parts) == 3:
        slug = make_slug(provider, tuple(parts), args.issue)
        owner = f"{parts[0]}/{parts[1]}"
        repo = parts[2]
    else:
        owner, _, repo = args.repo.partition("/")
        slug = make_slug(provider, (owner, repo), args.issue)
    queue = _load_json(QUEUE_FILE, {})
    if slug not in queue:
        print(f"Not found: {slug}")
        sys.exit(1)
    task = queue[slug]
    label_status = "-"
    try:
        repos_cfg = load_repos_config()
        repo_cfg = build_repo_cfg(owner, repo, cfg, repos_cfg)
        repo_cfg["provider"] = provider
        if repo_cfg.get("pat"):
            tracker = get_tracker(repo_cfg)
            issue = tracker.fetch_issue(repo_cfg, args.issue)
            label_status = tracker.get_status(issue) or "-"
    except Exception:
        pass
    task["label_status"] = label_status
    print(json.dumps(task, indent=2))


def _cmd_queue_prune(args, cfg):
    """Remove old done/skipped/closed tasks from the queue."""
    from autoswe.core.config import QUEUE_FILE

    older_than_days = getattr(args, "older_than_days", 30) or 30
    dry_run = getattr(args, "dry_run", False)

    from autoswe.tracking.labels import COMPLETED_STATUSES

    queue = _load_json(QUEUE_FILE, {})
    if not queue:
        print("Queue is empty. Nothing to prune.")
        return

    now = datetime.now(timezone.utc)
    prune_statuses = COMPLETED_STATUSES | {"skipped"}
    pruned = []

    for slug, task in list(queue.items()):
        if task.get("gh_closed", False) or task.get("autoswe_status") in prune_statuses:
            last_synced = task.get("last_synced", "")
            if last_synced:
                try:
                    synced_at = datetime.fromisoformat(last_synced)
                    if synced_at.tzinfo is None:
                        synced_at = synced_at.replace(tzinfo=timezone.utc)
                    age_days = (now - synced_at).total_seconds() / 86400
                    if age_days > older_than_days:
                        pruned.append((slug, task, age_days))
                except (ValueError, TypeError):
                    pass  # can't parse date, skip
            else:
                # No last_synced — too old to keep
                pruned.append((slug, task, float("inf")))

    if not pruned:
        print("No tasks match the prune criteria.")
        return

    if dry_run:
        print(f"[DRY RUN] Would prune {len(pruned)} task(s) older than {older_than_days} days:")
        for slug, task, age_days in pruned:
            status = task.get("autoswe_status") or "gh_closed"
            print(f"  {slug} (status={status}, age={age_days:.0f}d)")
        return

    # Actually prune
    for slug, _task, _age in pruned:
        del queue[slug]

    _atomic_write(QUEUE_FILE, queue)
    print(f"Pruned {len(pruned)} task(s). Remaining: {len(queue)}.")

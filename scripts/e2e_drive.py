"""E2E drive helper: seed a WI or post a slash command on the ADO test project.

Keeping the strings in this file (not in Bash args) avoids Git Bash backtick /
leading-slash mangling of issue bodies and slash commands.

Usage:
    e2e_drive.py seed <wi_file.json>     # create WI from a {title, body} file, post /plan
    e2e_drive.py post <wi> <command>     # post a slash command to WI
    e2e_drive.py read <wi> [<wi> ...]    # print WI state + last comments + queue row
"""
import json
import sys
from pathlib import Path

from autoswe.core.config import load_config, load_repos_config
from autoswe.providers.factory import get_tracker

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = "Natedorr/testProject/testProject"


def _tracker():
    load_config()
    return get_tracker(load_repos_config()[REPO])


def cmd_seed(wi_file: str) -> None:
    spec = json.loads(Path(wi_file).read_text(encoding="utf-8"))
    t = _tracker()
    wid = t.create_issue(spec["title"], spec["body"])
    print(f"created WI {wid}  ({spec['title']!r})")
    cid = t.post_comment(wid, "/plan")
    print(f"posted step-1 /plan -> comment {cid}")


def cmd_post(wid: int, body: str) -> None:
    t = _tracker()
    cid = t.post_comment(wid, body)
    print(f"posted {body!r} to WI {wid} -> comment {cid}")


def cmd_read(ids: list[int]) -> None:
    t = _tracker()
    for wid in ids:
        try:
            wi = t.fetch_issue(wid)
        except RuntimeError as e:
            print(f"WID {wid}: gone ({str(e)[:80]})")
            continue
        tags = [x for x in wi.labels if x.startswith("autoswe:")]
        print(f"WID {wid} state={wi.state!r} tags={tags}")
        print(f"   body={wi.body!r}")
        cs = sorted(t.fetch_comments(wid), key=lambda c: c.id)
        for c in cs[-6:]:
            who = "BOT" if "autoswe-bot" in (c.body or "") else c.author_login
            print(f"   [{c.id}] {who} | {c.body.replace(chr(10), ' / ')[:150]}")
        print()
    with open("data/queue.json") as f:
        q = json.load(f)
    for k, task in q.items():
        if k.startswith("ado:") and task.get("issue_number") in ids:
            print(
                f"queue {k}: status={task.get('autoswe_status')} "
                f"attempts={task.get('attempt_count')} guard_blocked={task.get('guard_blocked')} "
                f"last_disp={task.get('last_dispatched_command_id')} "
                f"last_consumed={task.get('last_consumed_reply_id')}"
            )


def main() -> None:
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return
    mode = a[0]
    if mode == "seed":
        cmd_seed(a[1])
    elif mode == "post":
        cmd_post(int(a[1]), " ".join(a[2:]))
    elif mode == "read":
        cmd_read([int(x) for x in a[1:]])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()

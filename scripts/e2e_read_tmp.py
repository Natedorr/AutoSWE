"""Live read of ADO WIs + queue. Usage: e2e_read_tmp.py [WI ...]"""
import json
import sys

from autoswe.core.config import load_config, load_repos_config
from autoswe.providers.factory import get_tracker

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = "Natedorr/testProject/testProject"


def main() -> None:
    ids = [int(x) for x in sys.argv[1:]] or [188, 189, 190]
    load_config()
    repos = load_repos_config()
    tracker = get_tracker(repos[REPO])

    for wid in ids:
        wi = tracker.fetch_issue(wid)
        print(f"==== WI {wid} state={wi.state}")
        print(f"   labels={wi.labels}  last_updated={wi.last_updated}")
        cs = sorted(tracker.fetch_comments(wid), key=lambda c: c.id)
        for c in cs[-5:]:
            body = c.body.replace("\n", " / ")[:140]
            print(f"   [{c.id}] {c.author_login} | {body}")
        print()

    with open("data/queue.json") as f:
        q = json.load(f)
    for k, t in q.items():
        if k.startswith("ado:"):
            print(
                f"queue {k}: status={t.get('autoswe_status')} "
                f"last_disp={t.get('last_dispatched_command_id')} "
                f"last_consumed={t.get('last_consumed_reply_id')}"
            )


if __name__ == "__main__":
    main()

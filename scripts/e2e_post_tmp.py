"""Post a comment (slash command) to an ADO WI. Usage: e2e_post_tmp.py <WI> <body...>"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from autoswe.core.config import load_config, load_repos_config
from autoswe.providers.factory import get_tracker

REPO = "Natedorr/testProject/testProject"


def main() -> None:
    wid = int(sys.argv[1])
    body = " ".join(sys.argv[2:])
    load_config()
    repos = load_repos_config()
    tracker = get_tracker(repos[REPO])
    cid = tracker.post_comment(wid, body)
    print(f"posted {body!r} to WI {wid} -> comment {cid}")


if __name__ == "__main__":
    main()

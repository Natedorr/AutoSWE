"""Seed fresh E2E WIs on ADO and post the first step command on each.

Seeds the three concurrent-pass cases (E2E-01, E2E-09, E2E-11) with their
exact titles/bodies, then posts each case's step-1 slash command.
Usage: e2e_seed_tmp.py            (seed + post step-1)
       e2e_seed_tmp.py --no-post  (seed only)
"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from autoswe.core.config import load_config, load_repos_config
from autoswe.providers.factory import get_tracker

REPO = "Natedorr/testProject/testProject"

# (case, title, body, step-1 command or None)
CASES = [
    (
        "E2E-01",
        "[E2E-01] Add a squares() helper to toolbox",
        "`src/toolbox.py` should gain a `squares(n)` function returning a list of the squares of\n"
        "0..n-1. Add one test for it in `tests/test_toolbox.py`. Nothing else.",
        "/plan",
    ),
    (
        "E2E-09",
        "[E2E-09] Add parse_port() - no tests please",
        "Add `parse_port(s)` to `src/toolbox.py` converting a string to an int port.\n"
        "Do not add any test for it, and do not validate the range. I will add tests later.",
        "/fix",
    ),
    (
        "E2E-11",
        "[E2E-11] Set flag.txt to red",
        "Replace the contents of `flag.txt` with the word `red`. Do not touch anything under `tests/`.",
        "/fix",
    ),
]


def main() -> None:
    no_post = "--no-post" in sys.argv
    load_config()
    repos = load_repos_config()
    tracker = get_tracker(repos[REPO])

    for case, title, body, cmd in CASES:
        wid = tracker.create_issue(title, body)
        print(f"created {case}: WI {wid}  ({title!r})")
        if not no_post and cmd:
            cid = tracker.post_comment(wid, cmd)
            print(f"  posted step-1 {cmd!r} -> comment {cid}")
    print("done")


if __name__ == "__main__":
    main()

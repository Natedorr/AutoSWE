"""Seed a fresh batch of small E2E work items on the Azure test project.

Exercises /plan, /fix, and /review->/fix through the pi-local harness end to
end, after a full reset of the project's prior work items.
Usage: e2e_seed_fresh.py            (seed + post step-1)
       e2e_seed_fresh.py --no-post  (seed only)
"""
import sys

from autoswe.core.config import load_config, load_repos_config
from autoswe.providers.factory import get_tracker

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = "Natedorr/testProject/testProject"

# (case, title, body, step-1 command or None)
CASES = [
    (
        "F1",
        "[F1] Add a cube(n) helper to toolbox",
        "`src/toolbox.py` should gain a `cube(n)` function returning n ** 3. "
        "Add one test for it in `tests/test_toolbox.py`. Nothing else.",
        "/fix",
    ),
    (
        "P1",
        "[P1] Add an is_even(n) helper to toolbox",
        "`src/toolbox.py` should gain an `is_even(n)` function returning a bool. "
        "Plan the change before implementing.",
        "/plan",
    ),
    (
        "R1",
        "[R1] Fix off-by-one in double(n)",
        "`double(n)` in `src/toolbox.py` looks correct but add a regression test "
        "confirming `double(0) == 0` and `double(-3) == -6`, plus the fix if needed.",
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

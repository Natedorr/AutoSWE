"""Drop live ADO E2E WIs + branches + PR, and clear queue entries.

Usage: e2e_drop_tmp.py 188 190 ...   (defaults to 188 189 190)
"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from autoswe.providers.azure.api import (
    _ado_api_version,
    _ado_request,
    _encode_path_segment,
    ado_get,
)
from autoswe.core.config import load_repos_config

REPO = "Natedorr/testProject/testProject"
QUEUE = "data/queue.json"


def main() -> None:
    ids = [int(x) for x in sys.argv[1:]] or [188, 189, 190]
    rc = load_repos_config()[REPO]
    pat = rc["pat"]
    org = _encode_path_segment(rc["org"])
    proj = _encode_path_segment(rc["project"])

    # resolve repo UUID
    repos = ado_get(_ado_api_version(f"https://dev.azure.com/{org}/{proj}/_apis/git/repositories"), pat)
    rid = next(r["id"] for r in repos.get("value", []) if r.get("name", "").lower() == rc["repo"].lower())
    base = f"https://dev.azure.com/{org}/{proj}/_apis/git/repositories/{rid}"

    # 1) abandon any open PR whose head is one of our branches
    prs = ado_get(_ado_api_version(f"{base}/pullrequests?searchCriteria.status=active"), pat)
    for p in prs.get("value", []):
        head = p["sourceRefName"]
        if any(f"issue-{i}" in head for i in ids):
            pid = p["pullRequestId"]
            print(f"abandoning PR {pid} ({head})")
            _ado_request(
                "PATCH",
                _ado_api_version(f"{base}/pullrequests/{pid}"),
                pat,
                body={"status": "abandoned"},
            )

    # 2) delete branches (ADO uses POST /refs with action=delete; needs the
    # ref's current objectId as newObjectId)
    from urllib.parse import quote
    for i in ids:
        ref = f"refs/heads/autoswe/issue-{i}"
        refinfo = ado_get(_ado_api_version(f"{base}/refs?filterContains={quote(ref, safe='')}"), pat)
        vals = refinfo.get("value") or []
        if not vals:
            print(f"  branch {ref} not found, skipping")
            continue
        sha = vals[0].get("objectId", "")
        print(f"deleting branch {ref} @ {sha}")
        _ado_request(
            "POST",
            _ado_api_version(f"{base}/refs"),
            pat,
            body=[{"action": "delete", "oldObjectName": ref, "newObjectId": sha}],
        )

    # 3) delete work items (404 = already gone, fine)
    for i in ids:
        print(f"deleting WI {i}")
        try:
            _ado_request("DELETE", _ado_api_version(f"https://dev.azure.com/{org}/{proj}/_apis/wit/workitems/{i}"), pat)
        except RuntimeError as e:
            if "404" in str(e):
                print(f"  WI {i} already gone")
            else:
                raise

    # 4) clear queue entries
    import json
    q = json.load(open(QUEUE))
    removed = [k for k in list(q) if any(f"_{i}" in k for i in ids)]
    for k in removed:
        del q[k]
    json.dump(q, open(QUEUE, "w"), indent=2)
    print("removed queue keys:", removed)
    print("done")


if __name__ == "__main__":
    main()

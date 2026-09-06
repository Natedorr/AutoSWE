#!/usr/bin/env python3
"""Score the live E2E suite from data/queue.json.

Runs on the autoSWE box, on the same cron tick as the poller. It is strictly a
reader: it never touches the provider and never writes the queue, so it cannot
perturb what it measures.

Each poll it samples every task whose issue title carries an ``[E2E-NN]`` marker,
appends any *changed* ``autoswe_status`` to that scenario's observed history
(persisted in ``observed.json``), and scores the history against the
``expect_sequence`` / ``forbidden_statuses`` in ``scenarios.json``.

    python e2e/monitor.py                 # print the table
    python e2e/monitor.py --write-report  # + write report.json
    python e2e/monitor.py --reset         # start a fresh pass

Exit code is 1 if any scenario has verdict ``fail`` or ``stalled``, else 0 —
so cron/CI can gate on it directly.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent      # <repo>/e2e
REPO_ROOT = HERE.parent
MANIFEST = HERE / "MANIFEST.json"
SCENARIOS = HERE / "scenarios.json"
OBSERVED = HERE / "observed.json"
REPORT = HERE / "report.json"
QUEUE = REPO_ROOT / "data" / "queue.json"

ID_RE = re.compile(r"\[(E2E-[0-9]+[a-z]?)\]")

RUNNING = {"planning", "fixing", "syncing", "reviewing", "shipping"}
# `pending` and the RUNNING states can pass between two samples: the poller does
# sync + dispatch in a single run, so a phase can start and finish inside one
# monitor tick. They are recorded when caught (they make the report readable and
# they still trip `forbidden_statuses`) but never *required* by the matcher —
# only resting states are load-bearing. Sampling faster than the poller (the
# suggested cron is 1 min monitor / 5 min poller) catches most of them.
TRANSIENT = RUNNING | {"pending"}
DEFAULT_STALL_S = 1800


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def scenario_id(title: str) -> str | None:
    m = ID_RE.search(title or "")
    return m.group(1) if m else None


def sample_queue(queue_path: Path = QUEUE) -> dict[str, dict]:
    """Map scenario id -> the queue entry currently backing it."""
    queue = load_json(queue_path, {})
    found: dict[str, dict] = {}
    for slug, entry in queue.items():
        sid = scenario_id(entry.get("title", ""))
        if not sid:
            continue
        found[sid] = {
            "slug": slug,
            "status": entry.get("autoswe_status"),
            "attempt_count": entry.get("attempt_count", 0),
            "plan_branch": entry.get("plan_branch"),
            "pr_number": entry.get("pr_number"),
            "gh_closed": bool(entry.get("gh_closed")),
            "last_dispatched_command": entry.get("last_dispatched_command"),
            "last_dispatched_command_id": entry.get("last_dispatched_command_id"),
            "last_good_session_backend": entry.get("last_good_session_backend"),
        }
    return found


def sample_key(cur: dict) -> str:
    """Identity of one visit to a status.

    Not the status alone: E2E-12 fails seven times in a row, and collapsing those
    into a single `failed` would make its ladder unscoreable. The triggering
    comment id is the state machine's own identity unit (see data-model.md), so a
    re-entry into the same status always carries a new key; `attempt_count` is
    included because the guard steps re-enter without dispatching a command.
    """
    return f"{cur['status']}|{cur.get('attempt_count')}|{cur.get('last_dispatched_command_id')}"


def update_observed(observed: dict, sample: dict[str, dict]) -> dict:
    """Append each newly-observed status visit to the scenario's history."""
    now = time.time()
    for sid, cur in sample.items():
        rec = observed.setdefault(
            sid, {"slug": cur["slug"], "history": [], "last_change_ts": now, "last_key": None}
        )
        rec["slug"] = cur["slug"]
        rec["latest"] = cur
        if not cur["status"]:
            continue
        key = sample_key(cur)
        if key != rec.get("last_key"):
            rec["history"].append(cur["status"])
            rec["last_key"] = key
            rec["last_change_ts"] = now
    return observed


def resting(statuses: list[str]) -> list[str]:
    """Drop the states that sampling cannot reliably observe."""
    return [s for s in statuses if s not in TRANSIENT]


def match_sequence(history: list[str], expected: list[str], loose: bool) -> tuple[str, str]:
    """Compare the observed resting-state sequence against the expected one.

    Strict (default): the observed resting states must equal the expected resting
    states, in order — landing on the right final state by the wrong route is a
    failure, which is the whole point of scoring a sequence.

    Loose: the expected states must merely appear in order, extra states allowed.
    Used by scenarios that repeat a state an indeterminate number of times
    (E2E-12's attempt ladder).

    Returns ("match" | "mismatch" | "incomplete", detail). A mismatch is a hard
    failure — the task went somewhere the scenario forbids. Incomplete just means
    the scenario has not finished yet; only the stall clock turns that into one.
    """
    obs, want = resting(history), resting(expected)
    i = 0
    for status in obs:
        if i < len(want) and status == want[i]:
            i += 1
        elif loose:
            continue
        else:
            seen = want[i] if i < len(want) else "<end of sequence>"
            return "mismatch", f"expected {seen!r} next, observed {status!r}"
    if i < len(want):
        return "incomplete", f"still missing {want[i:]}"
    return "match", "sequence matched"


def score(sid: str, spec: dict, rec: dict | None, stall_s: int) -> dict:
    expected = spec.get("expect_sequence", [])
    forbidden = set(spec.get("forbidden_statuses", []))
    loose = spec.get("sequence_match") == "loose"

    if rec is None:
        return {
            "id": sid,
            "slug": None,
            "verdict": "not_started",
            "detail": "no queue entry with this title marker yet",
            "observed": [],
        }

    history = rec.get("history", [])
    latest = rec.get("latest", {})
    idle_s = int(time.time() - rec.get("last_change_ts", time.time()))

    hit = forbidden.intersection(history)
    if hit:
        verdict, detail = "fail", f"forbidden status observed: {sorted(hit)}"
    else:
        kind, detail = match_sequence(history, expected, loose)
        if not expected:
            verdict = "pass" if not history else "fail"
            detail = "no dispatch expected" if verdict == "pass" else f"unexpected activity: {history}"
        elif kind == "match":
            verdict = "soft_fail" if spec.get("soft_assertions") else "pass"
            if verdict == "soft_fail":
                detail = "sequence matched; model-judgment assertions need a human read"
        elif kind == "mismatch":
            verdict = "fail"
        elif idle_s > stall_s:
            verdict, detail = "stalled", f"{detail}; no change for {idle_s}s"
        else:
            verdict = "in_progress"

    return {
        "id": sid,
        "slug": rec.get("slug"),
        "verdict": verdict,
        "detail": detail,
        "status": latest.get("status"),
        "attempt_count": latest.get("attempt_count"),
        "pr_number": latest.get("pr_number"),
        "observed": history,
        "expected": expected,
        "idle_s": idle_s,
    }


def render(rows: list[dict]) -> str:
    width = max((len(r["id"]) for r in rows), default=8)
    lines = [f"{'ID'.ljust(width)}  {'VERDICT'.ljust(12)} {'STATUS'.ljust(14)} DETAIL"]
    for r in rows:
        lines.append(
            f"{r['id'].ljust(width)}  {r['verdict'].ljust(12)} "
            f"{str(r.get('status') or '-').ljust(14)} {r['detail']}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write-report", action="store_true", help="write report.json")
    ap.add_argument("--reset", action="store_true", help="clear observed history and start a fresh pass")
    ap.add_argument("--pass-label", default="unlabelled", help="which backend pass this is, e.g. A-claude")
    ap.add_argument("--stall-seconds", type=int, default=DEFAULT_STALL_S)
    ap.add_argument("--quiet", action="store_true", help="only print on fail/stall")
    ap.add_argument("--queue", type=Path, default=QUEUE, help="queue.json to read (default: data/queue.json)")
    args = ap.parse_args(argv)

    if args.reset:
        OBSERVED.unlink(missing_ok=True)
        print("observed history cleared")
        return 0

    spec = load_json(SCENARIOS, None)
    if spec is None:
        print(f"missing {SCENARIOS}", file=sys.stderr)
        return 2

    observed = update_observed(load_json(OBSERVED, {}), sample_queue(args.queue))
    OBSERVED.write_text(json.dumps(observed, indent=2), encoding="utf-8")

    rows = [
        score(s["id"], s, observed.get(s["id"]), args.stall_seconds)
        for s in spec["scenarios"]
    ]

    summary: dict[str, int] = {}
    for r in rows:
        summary[r["verdict"]] = summary.get(r["verdict"], 0) + 1

    bad = summary.get("fail", 0) + summary.get("stalled", 0)

    if args.write_report:
        REPORT.write_text(
            json.dumps(
                {
                    "generated_at": _now(),
                    "pass_label": args.pass_label,
                    "scenarios": rows,
                    "summary": summary,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    if not args.quiet or bad:
        print(render(rows))
        print("\n" + "  ".join(f"{k}={v}" for k, v in sorted(summary.items())))

    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())

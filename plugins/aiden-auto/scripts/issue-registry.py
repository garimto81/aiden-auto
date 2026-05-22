#!/usr/bin/env python3
"""issue-registry — Issue-Driven Workflow CLI (Part 10)

사용법:
    issue-registry.py add --title T --severity HIGH --test "cmd" --expected "result"
    issue-registry.py list [--status open|in_progress|verifying|closed]
    issue-registry.py show <issue_id>
    issue-registry.py transition <issue_id> <new_status>
    issue-registry.py test <issue_id>
    issue-registry.py close <issue_id>
    issue-registry.py reopen <issue_id>
    issue-registry.py summary
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

USER_CLAUDE = Path.home() / ".claude"
REGISTRY_FILE = USER_CLAUDE / "state" / "issues.jsonl"

VALID_STATUS = {"open", "in_progress", "verifying", "closed", "reopened"}
VALID_SEVERITY = {"HIGH", "MED", "LOW"}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def gen_issue_id() -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    seq = 1
    if REGISTRY_FILE.exists():
        for line in REGISTRY_FILE.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("{\"_"):
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") == "issue" and rec.get("id", "").startswith(f"ISSUE-{today}"):
                try:
                    n = int(rec["id"].split("-")[-1])
                    seq = max(seq, n + 1)
                except (ValueError, IndexError):
                    pass
    return f"ISSUE-{today}-{seq:03d}"


def append_record(record: dict) -> None:
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with REGISTRY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_all_records() -> list[dict]:
    if not REGISTRY_FILE.exists():
        return []
    records = []
    for line in REGISTRY_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("{\"_"):
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def get_issues_state() -> dict[str, dict]:
    issues = {}
    for rec in load_all_records():
        if rec.get("type") == "issue":
            issues[rec["id"]] = {**rec, "current_status": rec.get("status", "open"),
                                 "test_pass_count": 0, "test_history": [],
                                 "reopen_count": 0}
        elif rec.get("type") == "transition":
            iid = rec.get("issue_id")
            if iid in issues:
                issues[iid]["current_status"] = rec.get("to_status")
                if rec.get("to_status") == "reopened":
                    issues[iid]["reopen_count"] += 1
                    issues[iid]["test_pass_count"] = 0
        elif rec.get("type") == "test_result":
            iid = rec.get("issue_id")
            if iid in issues:
                issues[iid]["test_history"].append(rec)
                if rec.get("pass"):
                    issues[iid]["test_pass_count"] += 1
                else:
                    issues[iid]["test_pass_count"] = 0
    return issues


def run_test(test_cmd: str, expected: str) -> tuple[bool, str]:
    try:
        r = subprocess.run(test_cmd, shell=True, capture_output=True, text=True, timeout=30)
        actual = (r.stdout + r.stderr).strip()
        passed = expected.strip() in actual or (r.returncode == 0 and expected == "exit_0")
        return passed, actual[:500]
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    except Exception as e:
        return False, f"ERROR: {e}"


def cmd_add(args):
    iid = gen_issue_id()
    record = {
        "type": "issue",
        "id": iid,
        "title": args.title,
        "severity": args.severity,
        "category": args.category,
        "discovered_at": now_iso(),
        "discovered_by": args.by,
        "description": args.description,
        "reproducible_test": args.test,
        "expected_result": args.expected,
        "close_condition": "test PASS 3회 연속",
        "status": "open",
    }
    append_record(record)
    print(f"Added: {iid} [{args.severity}] {args.title}")


def cmd_list(args):
    issues = get_issues_state()
    filtered = [i for i in issues.values()
                if (not args.status or i["current_status"] == args.status)
                and (not args.severity or i.get("severity") == args.severity)]
    sev_order = {"HIGH": 0, "MED": 1, "LOW": 2}
    filtered.sort(key=lambda i: (sev_order.get(i.get("severity"), 3), i["id"]))
    print(f"Total: {len(filtered)} issue(s)")
    print()
    for i in filtered:
        sev = i.get("severity", "-")
        st = i["current_status"]
        title = i.get("title", "")[:60]
        print(f"  {i['id']} [{sev:4s}] [{st:10s}] {title}")
        if i.get("reopen_count", 0) > 0:
            print(f"    reopened {i['reopen_count']} time(s)")


def cmd_show(args):
    issues = get_issues_state()
    if args.issue_id not in issues:
        print(f"Issue not found: {args.issue_id}")
        sys.exit(1)
    print(json.dumps(issues[args.issue_id], ensure_ascii=False, indent=2))


def cmd_transition(args):
    if args.to_status not in VALID_STATUS:
        print(f"Invalid status: {args.to_status}")
        sys.exit(1)
    issues = get_issues_state()
    if args.issue_id not in issues:
        print(f"Issue not found: {args.issue_id}")
        sys.exit(1)
    from_status = issues[args.issue_id]["current_status"]
    record = {
        "type": "transition",
        "issue_id": args.issue_id,
        "from_status": from_status,
        "to_status": args.to_status,
        "ts": now_iso(),
        "by": args.by,
        "reason": args.reason,
    }
    append_record(record)
    print(f"{args.issue_id}: {from_status} -> {args.to_status}")


def cmd_test(args):
    issues = get_issues_state()
    if args.issue_id not in issues:
        print(f"Issue not found: {args.issue_id}")
        sys.exit(1)
    i = issues[args.issue_id]
    test_cmd = i.get("reproducible_test")
    expected = i.get("expected_result", "")
    if not test_cmd:
        print(f"No test defined for {args.issue_id}")
        sys.exit(1)

    passed, actual = run_test(test_cmd, expected)
    append_record({
        "type": "test_result",
        "issue_id": args.issue_id,
        "ts": now_iso(),
        "pass": passed,
        "test_cmd": test_cmd,
        "expected": expected,
        "actual_excerpt": actual,
    })
    st = "PASS" if passed else "FAIL"
    print(f"{args.issue_id}: test {st}")
    if not passed:
        print(f"  expected: {expected}")
        print(f"  actual: {actual[:200]}")
    sys.exit(0 if passed else 1)


def cmd_close(args):
    issues = get_issues_state()
    if args.issue_id not in issues:
        print(f"Issue not found: {args.issue_id}")
        sys.exit(1)
    i = issues[args.issue_id]
    pc = i.get("test_pass_count", 0)
    if pc < 3 and not args.force:
        print(f"Cannot close: {args.issue_id} has {pc}/3 PASS")
        print(f"  Run: issue-registry.py test {args.issue_id} (3 times)")
        sys.exit(1)
    append_record({
        "type": "transition",
        "issue_id": args.issue_id,
        "from_status": i["current_status"],
        "to_status": "closed",
        "ts": now_iso(),
        "by": args.by,
        "reason": args.reason or f"{pc}/3 PASS",
    })
    print(f"Closed: {args.issue_id} ({pc}/3 PASS)")


def cmd_reopen(args):
    issues = get_issues_state()
    if args.issue_id not in issues:
        print(f"Issue not found: {args.issue_id}")
        sys.exit(1)
    i = issues[args.issue_id]
    append_record({
        "type": "transition",
        "issue_id": args.issue_id,
        "from_status": i["current_status"],
        "to_status": "reopened",
        "ts": now_iso(),
        "by": args.by,
        "reason": args.reason or "regression detected",
    })
    new_count = i.get("reopen_count", 0) + 1
    print(f"REOPENED: {args.issue_id} (count: {new_count})")
    if new_count >= 5:
        print(f"ESCALATION: reopen_count={new_count} >= 5 — user decision required")


def cmd_summary(args):
    issues = get_issues_state()
    by_status = {}
    by_severity = {"HIGH": 0, "MED": 0, "LOW": 0}
    reopened_count = 0
    for i in issues.values():
        s = i["current_status"]
        by_status[s] = by_status.get(s, 0) + 1
        sev = i.get("severity", "MED")
        if sev in by_severity:
            by_severity[sev] += 1
        if i.get("reopen_count", 0) > 0:
            reopened_count += 1
    total = sum(by_status.values())
    print(f"Issue Registry Summary (Total: {total})")
    print()
    print("  By Status:")
    for k in ["open", "in_progress", "verifying", "closed", "reopened"]:
        if k in by_status:
            print(f"    {k:12s} : {by_status[k]:3d}")
    print()
    print("  By Severity:")
    for k in ["HIGH", "MED", "LOW"]:
        print(f"    {k:4s} : {by_severity[k]:3d}")
    print()
    print(f"  Reopened (count > 0): {reopened_count}")


def main():
    parser = argparse.ArgumentParser(description="Issue Registry CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add")
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--severity", choices=VALID_SEVERITY, default="MED")
    p_add.add_argument("--category", default="general")
    p_add.add_argument("--test", required=True)
    p_add.add_argument("--expected", required=True)
    p_add.add_argument("--description", default="")
    p_add.add_argument("--by", default="claude")

    p_list = sub.add_parser("list")
    p_list.add_argument("--status", choices=VALID_STATUS)
    p_list.add_argument("--severity", choices=VALID_SEVERITY)

    p_show = sub.add_parser("show")
    p_show.add_argument("issue_id")

    p_trans = sub.add_parser("transition")
    p_trans.add_argument("issue_id")
    p_trans.add_argument("to_status")
    p_trans.add_argument("--by", default="claude")
    p_trans.add_argument("--reason", default="")

    p_test = sub.add_parser("test")
    p_test.add_argument("issue_id")

    p_close = sub.add_parser("close")
    p_close.add_argument("issue_id")
    p_close.add_argument("--force", action="store_true")
    p_close.add_argument("--by", default="claude")
    p_close.add_argument("--reason", default="")

    p_reopen = sub.add_parser("reopen")
    p_reopen.add_argument("issue_id")
    p_reopen.add_argument("--by", default="claude")
    p_reopen.add_argument("--reason", default="")

    sub.add_parser("summary")

    args = parser.parse_args()
    if args.command == "add":
        cmd_add(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "show":
        cmd_show(args)
    elif args.command == "transition":
        cmd_transition(args)
    elif args.command == "test":
        cmd_test(args)
    elif args.command == "close":
        cmd_close(args)
    elif args.command == "reopen":
        cmd_reopen(args)
    elif args.command == "summary":
        cmd_summary(args)


if __name__ == "__main__":
    main()

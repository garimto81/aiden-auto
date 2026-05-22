#!/usr/bin/env python3
"""regression-check — closed issue 의 reproducible_test 일괄 재실행 (Part 10)

배경: "수정 → 완료 → 재발 → 다시 발견" 패턴 해소.
    closed issue 가 다음 cycle 에 깨지면 자동 reopen.

사용법:
    regression-check.py            # 모든 closed issue 일괄 test
    regression-check.py --json     # JSON 출력
    regression-check.py --severity HIGH

Exit codes:
    0: 모두 PASS (regression 없음)
    1: 1+ FAIL (regression 발견, 자동 reopen 처리됨)
    2: script error
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


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_issues() -> dict[str, dict]:
    if not REGISTRY_FILE.exists():
        return {}
    issues = {}
    for line in REGISTRY_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("{\"_"):
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("type") == "issue":
            issues[rec["id"]] = {**rec, "current_status": rec.get("status", "open"),
                                 "reopen_count": 0}
        elif rec.get("type") == "transition":
            iid = rec.get("issue_id")
            if iid in issues:
                issues[iid]["current_status"] = rec.get("to_status")
                if rec.get("to_status") == "reopened":
                    issues[iid]["reopen_count"] += 1
    return issues


def run_test(cmd: str, expected: str) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        actual = (r.stdout + r.stderr).strip()
        passed = expected.strip() in actual or (r.returncode == 0 and expected == "exit_0")
        return passed, actual[:300]
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    except Exception as e:
        return False, f"ERROR: {e}"


def append_record(record: dict) -> None:
    with REGISTRY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--severity", choices=["HIGH", "MED", "LOW"])
    args = parser.parse_args()

    issues = load_issues()
    closed = [i for i in issues.values()
              if i["current_status"] == "closed"
              and (not args.severity or i.get("severity") == args.severity)]

    if not args.json:
        print("=" * 60)
        print(" Regression Check (closed issue 재실행)")
        print(f" Timestamp: {now_iso()}")
        print("=" * 60)
        print()
        print(f"Closed issue 수: {len(closed)}")
        print()

    pass_count = 0
    fail_count = 0
    reopened = []

    for issue in sorted(closed, key=lambda i: i["id"]):
        test_cmd = issue.get("reproducible_test")
        expected = issue.get("expected_result", "")
        if not test_cmd:
            continue

        passed, actual = run_test(test_cmd, expected)

        append_record({
            "type": "test_result",
            "issue_id": issue["id"],
            "ts": now_iso(),
            "pass": passed,
            "test_cmd": test_cmd,
            "expected": expected,
            "actual_excerpt": actual,
            "context": "regression_check",
        })

        if passed:
            pass_count += 1
            if not args.json:
                print(f"  [PASS] {issue['id']:30s} {issue.get('title', '')[:50]}")
        else:
            fail_count += 1
            append_record({
                "type": "transition",
                "issue_id": issue["id"],
                "from_status": "closed",
                "to_status": "reopened",
                "ts": now_iso(),
                "by": "regression-check",
                "reason": f"regression: expected '{expected[:40]}', got '{actual[:40]}'",
            })
            reopened.append(issue["id"])
            if not args.json:
                print(f"  [FAIL->REOPEN] {issue['id']:30s} {issue.get('title', '')[:50]}")
                print(f"         expected: {expected[:80]}")
                print(f"         actual:   {actual[:80]}")

    if args.json:
        print(json.dumps({
            "timestamp": now_iso(),
            "total_closed": len(closed),
            "pass": pass_count,
            "fail": fail_count,
            "reopened": reopened,
        }, ensure_ascii=False, indent=2))
    else:
        print()
        print(f"Total: {pass_count}/{len(closed)} PASS, {fail_count} FAIL")
        if reopened:
            print(f"REOPENED: {len(reopened)}건")
        print("=" * 60)

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(2)

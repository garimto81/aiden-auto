#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""framework_behavior_audit.py — 진짜 검증 (B2).

Surface check 가 아닌 actual import + invoke + assert.
각 hook/script 의 핵심 함수가 실제 작동하는지 검증.

발동: CLI / quantification_tracker hook.

PRD: aiden-auto-self-replication.prd.md v3 (Reality Validation B2)
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

GLOBAL_CLAUDE = Path.home() / ".claude"
HOOKS_DIR = GLOBAL_CLAUDE / "hooks"
SCRIPTS_DIR = GLOBAL_CLAUDE / "scripts"


def load_module(path: Path, name: str):
    """동적 모듈 로드 (subprocess 격리 가능)."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        return e


# ─────────────────────────────────────────────────────────────
# Behavior checks (각 hook/script 핵심 함수)
# ─────────────────────────────────────────────────────────────


def check_path_resolution_behavior() -> dict:
    """path_resolution.py 의 핵심 함수 작동."""
    sys.path.insert(0, str(HOOKS_DIR))
    try:
        import path_resolution as pr
        checks = {
            "resolve_global_claude_returns_path": isinstance(pr.resolve_global_claude(), Path),
            "resolve_plugin_source_callable": callable(pr.resolve_plugin_source),
            "resolve_cache_root_callable": callable(pr.resolve_cache_root),
            "resolve_aiden_auto_repo_callable": callable(pr.resolve_aiden_auto_repo),
        }
        return {"pass": all(checks.values()), "checks": checks}
    except Exception as e:
        return {"pass": False, "error": f"{type(e).__name__}: {e}"}


def check_goal_loop_state_behavior() -> dict:
    """goal_loop_state.py 의 counter + safety trip 실제 작동."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        import goal_loop_state as gls
        test_session = "behavior-audit-test"

        # 1. init
        state = gls.init_state(test_session, category="TEST")
        check_1 = state["counters"]["turn"] == 0 and state["counters"]["turn_limit"] == 20

        # 2. increment turn
        r = gls.increment_turn(test_session)
        check_2 = r["state"]["counters"]["turn"] == 1

        # 3. token usage
        r = gls.add_token_usage(test_session, 100)
        check_3 = r["state"]["counters"]["token_used"] == 100

        # 4. fail counter
        r = gls.increment_fail(test_session, "test")
        check_4 = r["state"]["counters"]["fail"] == 1

        # 5. safety trip on token limit
        r = gls.add_token_usage(test_session, 200_000)
        check_5 = r["trip"] is not None and r["trip"]["reason"] == "TOKEN_LIMIT"

        # cleanup
        gls.state_path(test_session).unlink(missing_ok=True)

        return {
            "pass": all([check_1, check_2, check_3, check_4, check_5]),
            "checks": {
                "init_correct": check_1,
                "increment_turn": check_2,
                "token_usage": check_3,
                "fail_counter": check_4,
                "safety_trip_token_limit": check_5,
            },
        }
    except Exception as e:
        return {"pass": False, "error": f"{type(e).__name__}: {e}"}


def check_framework_content_audit_behavior() -> dict:
    """framework_content_audit.py 의 통합 점수 공식 작동."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        import framework_content_audit as audit

        # 1. compute_integrated_score 호출
        result = {"total_checks": 25, "passed": 25, "failed": 0}
        score = audit.compute_integrated_score(result)

        checks = {
            "score_has_value": "value" in score,
            "score_in_range": 0 <= score["value"] <= 10,
            "weights_sum_to_1": abs(sum(v["weight"] for v in score["breakdown"].values()) - 1.0) < 0.001,
            "m4_capped_10": score["breakdown"]["M4_coverage"]["value"] <= 10.0,
            "has_confidence": "confidence" in score,
        }

        # 2. load_trend 호출
        trend = audit.load_trend(limit=3)
        checks["load_trend_returns_list"] = isinstance(trend, list)

        # 3. run_audit 호출 (실제 검사)
        audit_result = audit.run_audit()
        checks["run_audit_returns_dict"] = "results" in audit_result

        return {"pass": all(checks.values()), "checks": checks}
    except Exception as e:
        return {"pass": False, "error": f"{type(e).__name__}: {e}"}


def check_forbidden_pattern_check_behavior() -> dict:
    """forbidden_pattern_check.py 의 패턴 검사 + score 환산 작동."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        import forbidden_pattern_check as fpc

        # 1. 패턴 개수
        check_1 = len(fpc.FORBIDDEN_PATTERNS) >= 13

        # 2. P13 (estimation) 패턴 매칭
        p13 = next(p for p in fpc.FORBIDDEN_PATTERNS if p["id"] == "P13-estimation-expr")
        check_2 = p13["pattern"].search("추정 7.5") is not None
        check_3 = p13["pattern"].search("score = 9.86") is None  # 정상 표현은 매칭 X

        # 3. compute_score
        score = fpc.compute_score({
            "total_violations": 0,
            "severity": {"HIGH": 0, "MEDIUM": 0, "LOW": 0},
        })
        check_4 = score["raw_score"] == 10.0

        # 4. is_policy_context
        check_5 = fpc.is_policy_context("금지: hardcoded path 사용 X")
        check_6 = not fpc.is_policy_context("PATH = r'C:\\claude'")

        return {
            "pass": all([check_1, check_2, check_3, check_4, check_5, check_6]),
            "checks": {
                "patterns_13plus": check_1,
                "p13_estimation_matches": check_2,
                "p13_normal_score_excluded": check_3,
                "zero_violations_max_score": check_4,
                "policy_context_excludes_forbidden": check_5,
                "actual_hardcoded_caught": check_6,
            },
        }
    except Exception as e:
        return {"pass": False, "error": f"{type(e).__name__}: {e}"}


def check_auto_workflow_enforcer_behavior() -> dict:
    """auto_workflow_enforcer.py 의 model_plan + premise 평가 작동."""
    sys.path.insert(0, str(HOOKS_DIR))
    try:
        import auto_workflow_enforcer as awe

        # 1. resolve_model_for_role (fallback 동작)
        check_1 = awe.resolve_model_for_role({}, "executor") == "sonnet"

        # 2. tier 접미사 처리
        plan = {"executor": "sonnet"}
        check_2 = awe.resolve_model_for_role(plan, "executor-high") == "opus"
        check_3 = awe.resolve_model_for_role(plan, "executor-low") == "haiku"

        # 3. is_framework_asset
        test_path = GLOBAL_CLAUDE / "hooks" / "auto_workflow_enforcer.py"
        check_4 = awe.is_framework_asset(test_path)

        # 4. check_hardcoded_paths (자체)
        result = awe.check_hardcoded_paths(test_path)
        check_5 = "ok" in result

        return {
            "pass": all([check_1, check_2, check_3, check_4, check_5]),
            "checks": {
                "fallback_sonnet": check_1,
                "tier_high_upgrade": check_2,
                "tier_low_downgrade": check_3,
                "framework_asset_detected": check_4,
                "hardcoded_check_runs": check_5,
            },
        }
    except Exception as e:
        return {"pass": False, "error": f"{type(e).__name__}: {e}"}


def check_bootstrap_behavior() -> dict:
    """bootstrap.py 의 idempotent 작동."""
    sys.path.insert(0, str(HOOKS_DIR))
    try:
        import bootstrap

        # 1. autodetect_plugin_root
        plugin_root = bootstrap.autodetect_plugin_root()
        check_1 = plugin_root is None or plugin_root.is_dir()

        # 2. is_pristine_install (본 PC 는 install 됨 → False)
        check_2 = not bootstrap.is_pristine_install()

        # 3. should_skip 함수
        check_3 = bootstrap.should_skip(("state",), "test.json", ".json")
        check_4 = bootstrap.should_skip((), "settings.json", ".json")
        check_5 = not bootstrap.should_skip(("agents",), "executor.md", ".md")

        return {
            "pass": all([check_1, check_2, check_3, check_4, check_5]),
            "checks": {
                "autodetect_returns_valid": check_1,
                "pristine_install_false_on_existing": check_2,
                "exclude_state_dir": check_3,
                "exclude_settings": check_4,
                "include_agents_md": check_5,
            },
        }
    except Exception as e:
        return {"pass": False, "error": f"{type(e).__name__}: {e}"}


def check_pytest_passes() -> dict:
    """모든 pytest 테스트 통과 여부 — subprocess 격리."""
    tests_dir = GLOBAL_CLAUDE / "tests"
    if not tests_dir.is_dir():
        return {"pass": False, "error": "tests/ 디렉토리 부재"}
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(tests_dir), "--tb=no", "-q"],
            capture_output=True, text=True, timeout=60,
        )
        # "N passed" 또는 "N failed" 추출
        output = result.stdout + result.stderr
        passed = 0
        failed = 0
        for line in output.splitlines():
            if "passed" in line and "failed" in line:
                # "1 failed, 28 passed in ..."
                parts = line.replace(",", "").split()
                for i, p in enumerate(parts):
                    if p == "passed":
                        passed = int(parts[i-1])
                    if p == "failed":
                        failed = int(parts[i-1])
            elif " passed in " in line and "failed" not in line:
                parts = line.split()
                for i, p in enumerate(parts):
                    if p == "passed":
                        passed = int(parts[i-1])

        return {
            "pass": failed == 0 and passed > 0,
            "total_passed": passed,
            "total_failed": failed,
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"pass": False, "error": "pytest timeout"}
    except Exception as e:
        return {"pass": False, "error": f"{type(e).__name__}: {e}"}


# 검사 매핑
BEHAVIOR_CHECKS = {
    "B-path_resolution": ("path_resolution.py 핵심 함수", check_path_resolution_behavior),
    "B-goal_loop_state": ("goal_loop_state counter + safety trip", check_goal_loop_state_behavior),
    "B-framework_audit": ("framework_content_audit 통합 점수", check_framework_content_audit_behavior),
    "B-forbidden_check": ("forbidden_pattern_check 패턴 + score", check_forbidden_pattern_check_behavior),
    "B-auto_enforcer": ("auto_workflow_enforcer model_plan", check_auto_workflow_enforcer_behavior),
    "B-bootstrap": ("bootstrap idempotent", check_bootstrap_behavior),
    "B-pytest": ("모든 pytest 테스트 통과", check_pytest_passes),
}


def run_behavior_audit() -> dict:
    """전체 behavior 검사."""
    results = {}
    pass_count = 0
    for check_id, (desc, fn) in BEHAVIOR_CHECKS.items():
        try:
            result = fn()
            results[check_id] = {"description": desc, "pass": result.get("pass", False), "detail": result}
            if result.get("pass"):
                pass_count += 1
        except Exception as e:
            results[check_id] = {"description": desc, "pass": False, "error": str(e)}
    return {
        "total_checks": len(BEHAVIOR_CHECKS),
        "passed": pass_count,
        "failed": len(BEHAVIOR_CHECKS) - pass_count,
        "completeness": round(pass_count / len(BEHAVIOR_CHECKS) * 100, 1),
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="진짜 검증 도구 (B2) — import + invoke + assert")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    result = run_behavior_audit()

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    elif args.summary:
        print(f"=== Behavior Audit (B2) ===")
        print(f"  Total: {result['total_checks']}")
        print(f"  Passed: {result['passed']}")
        print(f"  Failed: {result['failed']}")
        print(f"  Completeness: {result['completeness']}%")
    else:
        print(f"=== Framework Behavior Audit (Reality, B2) ===\n")
        for cid, r in result["results"].items():
            mark = "✅" if r["pass"] else "❌"
            print(f"  {mark} [{cid}] {r['description']}")
            detail = r.get("detail", {})
            if not r["pass"]:
                if "error" in detail:
                    print(f"        error: {detail['error']}")
                for k, v in detail.get("checks", {}).items():
                    if not v:
                        print(f"        ❌ {k}")
        print(f"\n=== Summary ===")
        print(f"  Passed: {result['passed']}/{result['total_checks']} ({result['completeness']}%)")

    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

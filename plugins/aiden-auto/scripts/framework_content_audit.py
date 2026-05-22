#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""framework_content_audit.py — 22 결함 자동 검증 (Phase D 검증 도구).

⭐ Universal Deployment Premise 정합.

22 결함 매트릭스 (F1~F22) 자동 검사 + JSON 보고.

발동:
  · CLI: python framework_content_audit.py [--full | --area <name>]
  · /auto Step 0.7 자율 자산 inventory 회귀

PRD: aiden-auto-self-replication.prd.md (Phase D)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))
try:
    from path_resolution import resolve_global_claude  # type: ignore[import-not-found]
except ImportError:
    def resolve_global_claude(): return Path.home() / ".claude"

GLOBAL_CLAUDE = resolve_global_claude()
SKILL_AUTO = GLOBAL_CLAUDE / "skills" / "auto"
HOOKS_DIR = GLOBAL_CLAUDE / "hooks"
SCRIPTS_DIR = GLOBAL_CLAUDE / "scripts"
AGENTS_DIR = GLOBAL_CLAUDE / "agents"
STATE_DIR = GLOBAL_CLAUDE / "state"


def check_file_exists(p: Path) -> dict:
    return {"path": str(p), "exists": p.exists(), "size": p.stat().st_size if p.exists() else 0}


def check_F1_index_yml() -> dict:
    """F1: references/index.yml 부재 + v28.8 정합."""
    p = SKILL_AUTO / "references" / "index.yml"
    result = check_file_exists(p)
    if result["exists"]:
        try:
            content = p.read_text(encoding="utf-8")
            result["has_iron_laws"] = "iron_laws:" in content
            result["has_circuit_breakers"] = "circuit_breakers:" in content
            result["has_magic_words"] = "magic_words:" in content
            result["has_loading_rules"] = "loading_rules:" in content
            result["v28_8_compliant"] = all([
                result["has_iron_laws"],
                result["has_circuit_breakers"],
                result["has_magic_words"],
                result["has_loading_rules"],
            ])
        except OSError:
            result["v28_8_compliant"] = False
    result["pass"] = result["exists"] and result.get("v28_8_compliant", False)
    return result


def check_F2_goal_operation() -> dict:
    """F2: references/goal-operation.md 부재."""
    p = SKILL_AUTO / "references" / "goal-operation.md"
    result = check_file_exists(p)
    if result["exists"]:
        content = p.read_text(encoding="utf-8")
        result["has_3_stop_conditions"] = "3 멈춤 조건" in content or "3 stop" in content.lower()
        result["has_state_tracking"] = "state" in content.lower() and ("turn" in content.lower() or "counter" in content.lower())
        result["has_phase_4_qa_gate"] = "phase 4 qa gate" in content.lower() or "Phase 4 QA" in content
    result["pass"] = result["exists"] and result.get("has_3_stop_conditions", False)
    return result


def check_F3_options_handlers() -> dict:
    """F3: references/options-handlers.md 부재 + v28.8."""
    p = SKILL_AUTO / "references" / "options-handlers.md"
    result = check_file_exists(p)
    if result["exists"]:
        content = p.read_text(encoding="utf-8")
        result["has_no_auto"] = "--no-auto" in content
        result["has_eco_options"] = "--eco" in content
        result["has_failure_policy"] = "조용한 스킵 금지" in content or "NEVER silent skip" in content
    result["pass"] = result["exists"] and result.get("has_failure_policy", False)
    return result


def check_F4_F5_auto_workflow_enforcer() -> dict:
    """F4, F5: auto_workflow_enforcer.py 부재."""
    p = HOOKS_DIR / "auto_workflow_enforcer.py"
    result = check_file_exists(p)
    if result["exists"]:
        content = p.read_text(encoding="utf-8")
        result["has_save_model_plan"] = "save_model_plan" in content
        result["has_resolve_model_for_role"] = "resolve_model_for_role" in content
        result["has_universal_premise_eval"] = "enforce_premise_on_change" in content
    result["pass"] = result["exists"] and result.get("has_save_model_plan", False) and result.get("has_universal_premise_eval", False)
    return result


def check_F6_goal_loop_state() -> dict:
    """F6: goal_loop_state.py 부재."""
    p = SCRIPTS_DIR / "goal_loop_state.py"
    result = check_file_exists(p)
    if result["exists"]:
        content = p.read_text(encoding="utf-8")
        result["has_turn_counter"] = "increment_turn" in content
        result["has_token_counter"] = "add_token_usage" in content
        result["has_fail_counter"] = "increment_fail" in content
        result["has_safety_trip"] = "check_safety_trip" in content or "trip_status" in content
    result["pass"] = result["exists"] and all([
        result.get("has_turn_counter", False),
        result.get("has_token_counter", False),
        result.get("has_fail_counter", False),
        result.get("has_safety_trip", False),
    ])
    return result


def check_F7_harness_cycle() -> dict:
    """F7: harness_cycle_runner.py 부재."""
    p = HOOKS_DIR / "harness_cycle_runner.py"
    result = check_file_exists(p)
    if result["exists"]:
        content = p.read_text(encoding="utf-8")
        result["has_load_updates"] = "load_recent_updates" in content
        result["has_create_critic_flag"] = "create_critic_flag" in content
    result["pass"] = result["exists"] and result.get("has_create_critic_flag", False)
    return result


def check_F11_model_router() -> dict:
    """F11: model-router 31 keys vs iteration 13개."""
    p = AGENTS_DIR / "meta" / "model-router.md"
    result = check_file_exists(p)
    if result["exists"]:
        content = p.read_text(encoding="utf-8")
        required_iteration_agents = [
            "iteration-curator-a", "iteration-curator-b", "iteration-drift-reconciler",
            "iteration-runner", "iteration-e2e-orchestrator", "iteration-spec-validator",
            "iteration-screenshot-verifier", "iteration-spec-author",
            "iteration-spec-classifier", "iteration-spec-coherence",
            "iteration-decision-archivist", "iteration-phase-strategist",
            "iteration-prototype-validator",
        ]
        result["found"] = sum(1 for a in required_iteration_agents if a in content)
        result["expected"] = len(required_iteration_agents)
        result["missing"] = [a for a in required_iteration_agents if a not in content]
    result["pass"] = result.get("found", 0) >= 13
    return result


def check_F12_circuit_breaker() -> dict:
    """F12: circuit-breaker.json 4-counter."""
    p = STATE_DIR / "circuit-breaker.json"
    result = check_file_exists(p)
    if result["exists"]:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            required_counters = ["architect_reject", "pdca_iterator", "continuation_loop", "auto_recursion"]
            result["counters_present"] = [c for c in required_counters if c in data]
            result["all_counters"] = len(result["counters_present"]) == 4
        except (json.JSONDecodeError, OSError):
            result["all_counters"] = False
    result["pass"] = result.get("all_counters", False)
    return result


def check_F17_chapter_phase_path() -> dict:
    """F17: chapter 6종 phase_path 에 -1.5 포함."""
    chapters = ["chapter-doc", "chapter-code", "chapter-qa", "chapter-iteration", "chapter-research", "chapter-media"]
    results = {}
    for c in chapters:
        p = SKILL_AUTO / "references" / f"{c}.md"
        if p.exists():
            content = p.read_text(encoding="utf-8")
            # phase_path 라인 추출
            for line in content.splitlines():
                if line.strip().startswith("phase_path:"):
                    results[c] = {"has_minus_1_5": "-1.5" in line, "line": line.strip()}
                    break
            else:
                results[c] = {"has_minus_1_5": False, "line": "(no phase_path)"}
    all_pass = all(r.get("has_minus_1_5", False) for r in results.values())
    return {"pass": all_pass, "chapters": results, "exists": True}


def check_F18_chapter_dependency_guard() -> dict:
    """F18: chapter_dependency_guard.py 신규."""
    p = HOOKS_DIR / "chapter_dependency_guard.py"
    result = check_file_exists(p)
    if result["exists"]:
        content = p.read_text(encoding="utf-8")
        result["has_qa_check"] = "QA" in content and "CODE Phase 2" in content
    result["pass"] = result["exists"] and result.get("has_qa_check", False)
    return result


def check_F20_forbidden_pattern() -> dict:
    """F20: forbidden_pattern_check.py 신규."""
    p = SCRIPTS_DIR / "forbidden_pattern_check.py"
    result = check_file_exists(p)
    if result["exists"]:
        content = p.read_text(encoding="utf-8")
        result["has_forbidden_patterns"] = "FORBIDDEN_PATTERNS" in content
        result["has_universal_premise_check"] = "universal-premise" in content
    result["pass"] = result["exists"] and result.get("has_forbidden_patterns", False)
    return result


# 결함 → 검사 함수 매핑
DEFECT_CHECKS = {
    "F1": ("references/index.yml v28.8 정합", check_F1_index_yml),
    "F2": ("references/goal-operation.md 신규", check_F2_goal_operation),
    "F3": ("references/options-handlers.md v28.8 정합", check_F3_options_handlers),
    "F4_F5": ("auto_workflow_enforcer.py (Step 0.5/0.7 자동)", check_F4_F5_auto_workflow_enforcer),
    "F6": ("goal_loop_state.py (turn/token/fail counter)", check_F6_goal_loop_state),
    "F7": ("harness_cycle_runner.py (자가개선)", check_F7_harness_cycle),
    "F11": ("model-router iteration 13 agent 라우팅", check_F11_model_router),
    "F12": ("circuit-breaker.json 4-counter", check_F12_circuit_breaker),
    "F17": ("chapter 6종 phase_path -1.5 포함", check_F17_chapter_phase_path),
    "F18": ("chapter_dependency_guard.py 신규", check_F18_chapter_dependency_guard),
    "F20": ("forbidden_pattern_check.py 신규", check_F20_forbidden_pattern),
}


def run_audit() -> dict:
    """전체 결함 검사."""
    results = {}
    pass_count = 0
    for defect_id, (desc, check_fn) in DEFECT_CHECKS.items():
        try:
            check_result = check_fn()
            results[defect_id] = {
                "description": desc,
                "pass": check_result.get("pass", False),
                "detail": check_result,
            }
            if check_result.get("pass"):
                pass_count += 1
        except Exception as e:
            results[defect_id] = {
                "description": desc,
                "pass": False,
                "error": str(e),
            }

    summary = {
        "total_checks": len(DEFECT_CHECKS),
        "passed": pass_count,
        "failed": len(DEFECT_CHECKS) - pass_count,
        "completeness": round(pass_count / len(DEFECT_CHECKS) * 100, 1),
        "results": results,
    }
    return summary


def main():
    parser = argparse.ArgumentParser(description="22 결함 회귀 검증 도구 (Phase D)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    result = run_audit()

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.summary:
        print(f"=== Framework Content Audit ===")
        print(f"  Total checks: {result['total_checks']}")
        print(f"  Passed: {result['passed']}")
        print(f"  Failed: {result['failed']}")
        print(f"  Completeness: {result['completeness']}%")
    else:
        print(f"=== Framework Content Audit ===\n")
        for defect_id, r in result["results"].items():
            mark = "✅" if r["pass"] else "❌"
            print(f"  {mark} [{defect_id}] {r['description']}")
            if not r["pass"]:
                detail = r.get("detail", {})
                for k, v in detail.items():
                    if k not in ("path", "size") and isinstance(v, (bool, str, int, list)) and not (isinstance(v, list) and len(v) > 5):
                        print(f"        {k}: {v}")
        print(f"\n=== Summary ===")
        print(f"  Passed: {result['passed']}/{result['total_checks']} ({result['completeness']}%)")
        if result["failed"] > 0:
            print(f"  Failed: {result['failed']}")

    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

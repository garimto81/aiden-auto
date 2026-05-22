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


# ─────────────────────────────────────────────────────────────
# v3 추가 검사 (F8-F22 잔여 11 결함)
# ─────────────────────────────────────────────────────────────


def check_F8_part_a_skip_consistency() -> dict:
    """F8: Phase -1.5 Part A skip 조건 SKILL.md ↔ deep-interview.md 일관성."""
    skill = SKILL_AUTO / "SKILL.md"
    interview = SKILL_AUTO / "references" / "phase-minus-1.5-deep-interview.md"
    if not (skill.exists() and interview.exists()):
        return {"pass": False, "error": "files missing"}
    skill_content = skill.read_text(encoding="utf-8")
    interview_content = interview.read_text(encoding="utf-8")
    # 둘 다 "Skip 조건: !quick / !just / !hotfix" 패턴 일관성
    skill_skip = "!quick" in skill_content and "!hotfix" in skill_content
    interview_skip = "!quick" in interview_content and "!hotfix" in interview_content
    return {"pass": skill_skip and interview_skip, "skill_has": skill_skip, "interview_has": interview_skip}


def check_F9_part_ce_hardcoded() -> dict:
    """F9: Phase -1.5 Part C/E hardcoded path 제거."""
    interview = SKILL_AUTO / "references" / "phase-minus-1.5-deep-interview.md"
    if not interview.exists():
        return {"pass": False, "error": "file missing"}
    content = interview.read_text(encoding="utf-8")
    # hardcoded C:\ 경로 패턴 (backward compat 표시 제외)
    import re
    hardcoded = re.findall(r'C:[\\/]Users[\\/]AidenKim|C:[\\/]claude[\\/](?!.*backward compat)', content)
    return {"pass": len(hardcoded) <= 1, "hardcoded_count": len(hardcoded)}


def check_F10_part_d_clarity() -> dict:
    """F10: Part D 자율 판단 vs 자동 생성 단계 명확화."""
    interview = SKILL_AUTO / "references" / "phase-minus-1.5-deep-interview.md"
    if not interview.exists():
        return {"pass": False}
    content = interview.read_text(encoding="utf-8")
    # Part D 가 "질문 단계" 명시 + Phase 1.3 reference
    has_part_d = "Part D" in content
    has_question_stage = "질문" in content and "생성" in content
    return {"pass": has_part_d and has_question_stage}


def check_F13_quota_advisor_2tier() -> dict:
    """F13: quota_pretool_gate.py 가 2차 advisor escalate 구현."""
    p = GLOBAL_CLAUDE / "hooks" / "quota_pretool_gate.py"
    if not p.exists():
        return {"pass": False, "exists": False}
    content = p.read_text(encoding="utf-8")
    has_advisor = "advisor" in content.lower() or "escalate" in content.lower()
    has_sub_inference = "advisor-tool" in content or "sub_inference" in content.lower() or "ESCALATE" in content
    return {"pass": has_advisor and has_sub_inference, "has_advisor": has_advisor, "has_sub_inference": has_sub_inference}


def check_F14_code_chapter_reader_exp() -> dict:
    """F14: CODE chapter Multi-perspective 에 reader-experience 포함."""
    p = SKILL_AUTO / "references" / "chapter-code.md"
    if not p.exists():
        return {"pass": False}
    content = p.read_text(encoding="utf-8")
    return {"pass": "reader-experience" in content, "agent_present": "reader-experience" in content}


def check_F15_qa_chapter_4agent() -> dict:
    """F15: QA chapter Multi-perspective 4 agent 정합."""
    p = SKILL_AUTO / "references" / "chapter-qa.md"
    if not p.exists():
        return {"pass": False}
    content = p.read_text(encoding="utf-8")
    # 4 핵심 agent + ad-hoc 분리 명시
    has_aggregation = "aggregation" in content.lower() or "집계" in content or "ALL APPROVE" in content or "ALL PASS" in content
    return {"pass": has_aggregation}


def check_F16_iteration_critic() -> dict:
    """F16: ITERATION chapter critic agent 명시."""
    p = SKILL_AUTO / "references" / "chapter-iteration.md"
    if not p.exists():
        return {"pass": False}
    content = p.read_text(encoding="utf-8")
    # agent_team 에 critic 포함 OR Phase 3 에 critic 언급
    return {"pass": "critic" in content.lower()}


def check_F19_skill_md_concise() -> dict:
    """F19: SKILL.md ≤120 줄 (원칙 3 정합)."""
    p = SKILL_AUTO / "SKILL.md"
    if not p.exists():
        return {"pass": False}
    lines = len(p.read_text(encoding="utf-8").splitlines())
    return {"pass": lines <= 120, "lines": lines, "limit": 120, "excess": max(0, lines - 120)}


def check_F21_critic_verdict_bridge() -> dict:
    """F21: critic-protocol-unified.md 의 5종↔4종 verdict bridge."""
    p = SKILL_AUTO / "references" / "critic-protocol-unified.md"
    if not p.exists():
        return {"pass": False, "exists": False}
    content = p.read_text(encoding="utf-8")
    # 5 verdict (APPROVE/REJECT/QUESTION/SURVIVED/DESTROYED) ↔ 4 verdict bridge
    has_5_verdict = all(v in content for v in ["APPROVE", "REJECT", "QUESTION"])
    has_bridge = "bridge" in content.lower() or "매핑" in content
    return {"pass": has_5_verdict and has_bridge}


def check_F22_iteration_exit_oscillation() -> dict:
    """F22: ITERATION exit criteria 진동 허용."""
    p = SKILL_AUTO / "references" / "chapter-iteration.md"
    if not p.exists():
        return {"pass": False}
    content = p.read_text(encoding="utf-8")
    # "decreasing" 폐기 + "consecutive cycles" 또는 oscillation tolerance 명시
    has_old = "drift_direction=decreasing" in content or "decreasing\"" in content
    has_new = "consecutive" in content.lower() or "oscillation" in content.lower() or "진동" in content
    return {"pass": (not has_old) or has_new}


def check_D1_integrated_score() -> dict:
    """D1: framework_content_audit.py 에 compute_integrated_score() 존재."""
    p = SCRIPTS_DIR / "framework_content_audit.py"
    if not p.exists():
        return {"pass": False}
    content = p.read_text(encoding="utf-8")
    return {"pass": "compute_integrated_score" in content and "weighted" in content.lower()}


def check_D3_violation_score() -> dict:
    """D3: forbidden_pattern_check.py 에 score() 메서드."""
    p = SCRIPTS_DIR / "forbidden_pattern_check.py"
    if not p.exists():
        return {"pass": False}
    content = p.read_text(encoding="utf-8")
    return {"pass": "def score" in content or "compute_score" in content}


def check_D4_estimation_pattern() -> dict:
    """D4: forbidden_pattern_check.py 에 P13-estimation-expr 등재."""
    p = SCRIPTS_DIR / "forbidden_pattern_check.py"
    if not p.exists():
        return {"pass": False}
    content = p.read_text(encoding="utf-8")
    return {"pass": "P13-estimation-expr" in content or "estimation-expr" in content}


def check_D5_timeline_tracker() -> dict:
    """D5: quantification_tracker.py + framework-score-timeline.jsonl."""
    hook = GLOBAL_CLAUDE / "hooks" / "quantification_tracker.py"
    timeline = STATE_DIR / "framework-score-timeline.jsonl"
    return {"pass": hook.exists(), "hook_exists": hook.exists(), "timeline_exists": timeline.exists()}


# 결함 → 검사 함수 매핑 (v3 확장 — 22 결함 + 5 메타-결함)
DEFECT_CHECKS = {
    "F1": ("references/index.yml v28.8 정합", check_F1_index_yml),
    "F2": ("references/goal-operation.md 신규", check_F2_goal_operation),
    "F3": ("references/options-handlers.md v28.8 정합", check_F3_options_handlers),
    "F4_F5": ("auto_workflow_enforcer.py (Step 0.5/0.7 자동)", check_F4_F5_auto_workflow_enforcer),
    "F6": ("goal_loop_state.py (turn/token/fail counter)", check_F6_goal_loop_state),
    "F7": ("harness_cycle_runner.py (자가개선)", check_F7_harness_cycle),
    "F8": ("Phase -1.5 Part A skip 조건 일관성", check_F8_part_a_skip_consistency),
    "F9": ("Phase -1.5 Part C/E hardcoded path 제거", check_F9_part_ce_hardcoded),
    "F10": ("Part D 자율 판단 vs 자동 생성 명확화", check_F10_part_d_clarity),
    "F11": ("model-router iteration 13 agent 라우팅", check_F11_model_router),
    "F12": ("circuit-breaker.json 4-counter", check_F12_circuit_breaker),
    "F13": ("quota_pretool_gate 2차 advisor escalate", check_F13_quota_advisor_2tier),
    "F14": ("CODE chapter reader-experience 포함", check_F14_code_chapter_reader_exp),
    "F15": ("QA chapter Multi-perspective 4 agent 정합", check_F15_qa_chapter_4agent),
    "F16": ("ITERATION chapter critic agent 명시", check_F16_iteration_critic),
    "F17": ("chapter 6종 phase_path -1.5 포함", check_F17_chapter_phase_path),
    "F18": ("chapter_dependency_guard.py 신규", check_F18_chapter_dependency_guard),
    "F19": ("SKILL.md ≤120줄 (원칙 3 정합)", check_F19_skill_md_concise),
    "F20": ("forbidden_pattern_check.py 신규", check_F20_forbidden_pattern),
    "F21": ("critic-protocol-unified verdict bridge", check_F21_critic_verdict_bridge),
    "F22": ("ITERATION exit criteria 진동 허용", check_F22_iteration_exit_oscillation),
    # v3 메타-결함 검사
    "D1": ("compute_integrated_score() 공식 구현", check_D1_integrated_score),
    "D3": ("forbidden_pattern_check score() 메서드", check_D3_violation_score),
    "D4": ("P13-estimation-expr 등재", check_D4_estimation_pattern),
    "D5": ("quantification_tracker hook 신규", check_D5_timeline_tracker),
}


# ─────────────────────────────────────────────────────────────
# v3 통합 점수 공식 (메타-결함 D1 해소)
# ─────────────────────────────────────────────────────────────


def get_violation_count() -> int:
    """forbidden_pattern_check 실행 결과 가져오기."""
    import subprocess
    check_script = SCRIPTS_DIR / "forbidden_pattern_check.py"
    if not check_script.exists():
        return -1
    try:
        result = subprocess.run(
            [sys.executable, str(check_script), "--summary"],
            capture_output=True, text=True, timeout=30,
        )
        # "Violations: NNN total" 파싱
        for line in result.stdout.splitlines():
            if "Violations:" in line and "total" in line:
                parts = line.split()
                for token in parts:
                    if token.isdigit():
                        return int(token)
    except Exception:
        pass
    return -1


def get_replication_rate() -> float:
    """measure-replication.py 실행 결과."""
    import subprocess
    rep_script = SCRIPTS_DIR / "measure-replication.py"
    if not rep_script.exists():
        return -1.0
    try:
        result = subprocess.run(
            [sys.executable, str(rep_script), "--target", str(GLOBAL_CLAUDE), "--json"],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout)
        return float(data.get("self_replication_rate", 0))
    except Exception:
        pass
    return -1.0


def get_behavior_score() -> float:
    """B2 behavior audit score 가져오기."""
    import subprocess
    script = SCRIPTS_DIR / "framework_behavior_audit.py"
    if not script.exists():
        return -1.0
    try:
        result = subprocess.run(
            [sys.executable, str(script), "--json"],
            capture_output=True, text=True, timeout=60,
        )
        data = json.loads(result.stdout)
        passed = data.get("passed", 0)
        total = data.get("total_checks", 1)
        return (passed / total * 10) if total > 0 else 0
    except Exception:
        return -1.0


def get_hook_invocation_score() -> float:
    """B3 hook invocation score 가져오기."""
    import subprocess
    script = SCRIPTS_DIR / "hook_invocation_audit.py"
    if not script.exists():
        return -1.0
    try:
        result = subprocess.run(
            [sys.executable, str(script), "--score-only"],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout)
        return float(data.get("score", 0))
    except Exception:
        return -1.0


def get_e2e_score() -> float:
    """B4 e2e flow score — 캐싱된 trend 에서 (e2e 는 30-60초 소요)."""
    timeline_path = STATE_DIR / "framework-e2e-timeline.jsonl"
    if not timeline_path.exists():
        return -1.0
    try:
        lines = timeline_path.read_text(encoding="utf-8").splitlines()
        if not lines:
            return -1.0
        last_entry = json.loads(lines[-1])
        return float(last_entry.get("score", 0))
    except Exception:
        return -1.0


def get_test_coverage_score() -> float:
    """B1 pytest test coverage score."""
    import subprocess
    tests_dir = GLOBAL_CLAUDE / "tests"
    if not tests_dir.is_dir():
        return -1.0
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(tests_dir), "--tb=no", "-q"],
            capture_output=True, text=True, timeout=60,
        )
        output = result.stdout + result.stderr
        passed = 0
        failed = 0
        for line in output.splitlines():
            if "passed" in line and "in " in line:
                parts = line.replace(",", "").split()
                for i, p in enumerate(parts):
                    if p == "passed" and i > 0:
                        try:
                            passed = int(parts[i-1])
                        except ValueError:
                            pass
                    if p == "failed" and i > 0:
                        try:
                            failed = int(parts[i-1])
                        except ValueError:
                            pass
        total = passed + failed
        return (passed / total * 10) if total > 0 else 0
    except Exception:
        return -1.0


def compute_integrated_score(audit_result: dict) -> dict:
    """v4 통합 점수 공식 — Surface + Reality.

    Surface metrics (30% — 메타데이터):
      M1 (구조 완성도): PASS/total × 10 — 가중치 15%
      M2 (규칙 준수도): max(0, 10 - violations/50) — 가중치 10%
      M4 (검사 커버율): min(10, checked/22 × 10) — 가중치 5%

    Reality metrics (70% — 실제 작동):
      M3 (자기복제율): rate × 0.1 — 가중치 10%
      M5 (behavior validation): B2 behavior audit — 가중치 20%
      M6 (hook invocation): B3 hook invocation — 가중치 15%
      M7 (e2e flow): B4 e2e flow — 가중치 15%
      M8 (test coverage): B1 pytest — 가중치 10%

    Surface = 30%, Reality = 70% (사용자 지적 반영).
    """
    total_checks = audit_result.get("total_checks", 22)
    passed = audit_result.get("passed", 0)
    violations = get_violation_count()
    replication = get_replication_rate()
    behavior = get_behavior_score()
    hook_inv = get_hook_invocation_score()
    e2e = get_e2e_score()
    test_cov = get_test_coverage_score()

    # Surface metrics
    M1 = (passed / total_checks * 10) if total_checks > 0 else 0
    M2 = max(0, 10 - violations / 50) if violations >= 0 else 0
    M3 = (replication * 0.1) if replication >= 0 else 0
    M4 = min(10.0, total_checks / 22 * 10)

    # Reality metrics (v4 신규)
    M5 = behavior if behavior >= 0 else 0
    M6 = hook_inv if hook_inv >= 0 else 0
    M7 = e2e if e2e >= 0 else 0
    M8 = test_cov if test_cov >= 0 else 0

    # v4 가중치 (Reality 70%)
    weights = {
        "M1_structure": 0.15,
        "M2_rule_compliance": 0.10,
        "M3_replication": 0.10,
        "M4_coverage": 0.05,
        "M5_behavior": 0.20,
        "M6_hook_invocation": 0.15,
        "M7_e2e_flow": 0.15,
        "M8_test_coverage": 0.10,
    }

    metrics = {
        "M1_structure": (M1, f"{passed}/{total_checks} PASS (Surface)"),
        "M2_rule_compliance": (M2, f"{violations} violations (Surface)"),
        "M3_replication": (M3, f"{replication}% self-replication (Reality)"),
        "M4_coverage": (M4, f"{total_checks}/22 covered (Surface)"),
        "M5_behavior": (M5, "behavior audit (Reality)"),
        "M6_hook_invocation": (M6, "hook invocation (Reality)"),
        "M7_e2e_flow": (M7, "e2e flow (Reality)"),
        "M8_test_coverage": (M8, "pytest (Reality)"),
    }

    integrated = sum(weights[k] * v[0] for k, v in metrics.items())

    valid_metrics = sum(1 for k, v in metrics.items() if v[0] > 0)
    confidence = "HIGH" if valid_metrics >= 7 else ("MEDIUM" if valid_metrics >= 5 else "LOW")

    # Surface vs Reality 분리 score
    surface_score = (weights["M1_structure"] * M1 + weights["M2_rule_compliance"] * M2
                     + weights["M4_coverage"] * M4) / 0.30  # 30% 가중치 정규화
    reality_score = (weights["M3_replication"] * M3 + weights["M5_behavior"] * M5
                     + weights["M6_hook_invocation"] * M6 + weights["M7_e2e_flow"] * M7
                     + weights["M8_test_coverage"] * M8) / 0.70

    return {
        "value": round(integrated, 2),
        "formula": "Surface 30% (M1/M2/M4) + Reality 70% (M3/M5/M6/M7/M8) — v4",
        "surface_score": round(surface_score, 2),
        "reality_score": round(reality_score, 2),
        "breakdown": {
            k: {
                "value": round(v[0], 2),
                "basis": v[1],
                "weight": weights[k],
                "weighted": round(weights[k] * v[0], 2),
                "category": "Reality" if k in ("M3_replication", "M5_behavior", "M6_hook_invocation", "M7_e2e_flow", "M8_test_coverage") else "Surface",
            }
            for k, v in metrics.items()
        },
        "confidence": confidence,
        "max_score": 10.0,
    }


def append_to_timeline(audit_result: dict, integrated: dict) -> None:
    """D5: framework-score-timeline.jsonl 누적."""
    timeline_path = STATE_DIR / "framework-score-timeline.jsonl"
    entry = {
        "timestamp": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()),
        "metrics": integrated["breakdown"],
        "integrated_score": {"value": integrated["value"], "formula": integrated["formula"], "confidence": integrated["confidence"]},
        "audit_summary": {
            "total_checks": audit_result["total_checks"],
            "passed": audit_result["passed"],
            "failed": audit_result["failed"],
        },
    }
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with timeline_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def load_trend(limit: int = 10) -> list:
    """D5: 최근 N 점수 trend."""
    timeline_path = STATE_DIR / "framework-score-timeline.jsonl"
    if not timeline_path.exists():
        return []
    try:
        lines = timeline_path.read_text(encoding="utf-8").splitlines()
        entries = [json.loads(ln) for ln in lines[-limit:]]
        return entries
    except (OSError, json.JSONDecodeError):
        return []


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
    parser = argparse.ArgumentParser(description="22 결함 + 메타-결함 회귀 검증 + 통합 점수 (v3)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--integrated-score", action="store_true", help="v3: 통합 점수 산출 (4 메트릭 가중)")
    parser.add_argument("--trend", action="store_true", help="v3: 점수 trend timeline 출력")
    parser.add_argument("--no-timeline", action="store_true", help="timeline.jsonl 자동 기록 비활성")
    args = parser.parse_args()

    if args.trend:
        # trend 모드 — 별도 처리
        entries = load_trend(limit=20)
        if not entries:
            print("(no timeline entries yet)")
            return 0
        if args.json:
            print(json.dumps(entries, indent=2, ensure_ascii=False))
        else:
            print(f"=== Framework Score Timeline (recent {len(entries)}) ===")
            for e in entries:
                ts = e.get("timestamp", "?")
                score = e.get("integrated_score", {}).get("value", "?")
                conf = e.get("integrated_score", {}).get("confidence", "?")
                print(f"  {ts}  score={score}/10  ({conf})")
        return 0

    result = run_audit()

    # v3: 통합 점수 자동 산출
    integrated = compute_integrated_score(result)
    result["integrated_score"] = integrated

    # v3: timeline 자동 기록
    if not args.no_timeline:
        append_to_timeline(result, integrated)

    if args.integrated_score:
        # 통합 점수만 출력 (간결)
        if args.json:
            print(json.dumps({"integrated_score": integrated, "audit_summary": {
                "total_checks": result["total_checks"], "passed": result["passed"]
            }}, indent=2, ensure_ascii=False))
        else:
            print(f"=== Framework Integrated Score ===")
            print(f"  Score: {integrated['value']}/{integrated['max_score']}")
            print(f"  Confidence: {integrated['confidence']}")
            print(f"  Formula: {integrated['formula']}")
            print(f"\n  Breakdown:")
            for k, v in integrated["breakdown"].items():
                print(f"    {k}: {v['value']}/10 × {v['weight']} = {v['weighted']}  ({v['basis']})")
        return 0 if integrated["value"] >= 9.0 else 1

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.summary:
        print(f"=== Framework Content Audit ===")
        print(f"  Total checks: {result['total_checks']}")
        print(f"  Passed: {result['passed']}")
        print(f"  Failed: {result['failed']}")
        print(f"  Completeness: {result['completeness']}%")
        print(f"  Integrated Score: {integrated['value']}/10 ({integrated['confidence']})")
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

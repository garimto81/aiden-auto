#!/usr/bin/env python
"""PreToolUse(Agent) hook — model 파라미터 미주입 시 정적 매트릭스로 자동 주입 시도.

설계 원칙:
- Lead가 model을 명시 했으면 통과 (router 결정 그대로 사용)
- 미명시 시 매트릭스 lookup → tool_input.model 주입 시도 (modify response)
- Claude Code가 modify 응답을 무시하면 (분기 D) 최소한 통과는 됨 (continue: true)
- 어떤 경우에도 차단하지 않음 (UX 보호)
- 모든 결정을 stderr + log 에 기록 → logger hook 과 cross-reference 가능

설계 출처: ~/.claude/plans/opus-atomic-spark.md Round 6
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 정적 매트릭스 — 사용자 실제 호출 패턴 반영 (2026-05-12 진단 후 확장)
# 14 우리 agents + 사용자 작업 흐름에서 자주 호출되는 built-in / plugin agents 포함
MATRIX_NORMAL = {
    # 14 우리 agents (~/.claude/agents/ + project .claude/agents/ 정의)
    "model-router": "haiku",
    "planner": "sonnet",
    "executor": "sonnet",
    "executor-high": "opus",
    "qa-tester": "sonnet",
    "quality-gate": "sonnet",
    "gap-detector": "sonnet",
    "designer": "sonnet",
    "writer": "haiku",
    "document-specialist": "haiku",
    "reader-experience": "sonnet",
    "researcher": "sonnet",
    "analyst": "haiku",
    "critic": "sonnet",
    # 기존 project + plugin agents (이름 중복 X)
    "architect": "opus",
    "code-reviewer": "sonnet",
    "security-reviewer": "opus",
    "test-engineer": "sonnet",
    "tracer": "sonnet",
    "verifier": "sonnet",
    "doc-critic": "opus",
    "iteration-curator-a": "sonnet",
    "iteration-curator-b": "sonnet",
    "iteration-drift-reconciler": "opus",
    "iteration-runner": "sonnet",
    "iteration-e2e-orchestrator": "sonnet",
    "iteration-spec-validator": "sonnet",
    "iteration-screenshot-verifier": "haiku",
    "iteration-spec-author": "sonnet",
    "iteration-phase-strategist": "opus",
    "iteration-prototype-validator": "sonnet",
    "iteration-spec-classifier": "haiku",
    "iteration-spec-coherence": "sonnet",
    "iteration-decision-archivist": "haiku",
    "harness-watcher": "haiku",
    "harness-critic": "opus",
    "harness-applier": "sonnet",
    "pdca-iterator": "opus",
    "compaction-critic": "sonnet",
    "cc-version-researcher": "opus",
    "cc-auth-advisor": "opus",
    "cc-auth-executor": "sonnet",
    # 사용자 작업에서 자주 호출되는 built-in agents (진단 2026-05-12)
    "Explore": "haiku",          # built-in (대문자)
    "Plan": "haiku",             # built-in (대문자)
    "general-purpose": "sonnet", # built-in — Lead 상속 차단
    # NOTE: 2026-05-12 phantom 정리 — 매트릭스 등록만 있고 파일 없는 15개 entry 제거
    # 제거: prd-writer, prd-rewriter, wave1-builder, explore-high, critic-a,
    #       critic-editor, architect-verify, arch-verify, impl-manager,
    #       executor-A, scaffolder, workflow-improver, designer-high,
    #       executor-models, executor-server, explore (소문자)
    # 검증: tools/skill-* + agent-matrix-audit script. 호출 흔적 없음.
}
FALLBACK = "sonnet"  # 사용자 명시 (2026-05-12): fallback = sonnet, opus 상속 금지

# ════════════════════════════════════════════════════════════════════════
# Override 모드 (2026-05-12 사용자 지시: "모든 opus 를 sonnet 으로 변경")
#   True  → 모든 opus 결정을 sonnet 으로 override (← 현재)
#   False → 정상 매트릭스 사용
# 진단 결과: H6 (우리 14 agents 가 자동 워크플로우에서 거의 호출 안 됨).
# built-in/plugin agents 까지 매트릭스 확장 + 모든 opus → sonnet 강제.
# 복원 메모: ~/.claude/plans/sonnet-override-restore.md
# ════════════════════════════════════════════════════════════════════════
OVERRIDE_OPUS_TO_SONNET = True

MATRIX = (
    {k: ("sonnet" if v == "opus" else v) for k, v in MATRIX_NORMAL.items()}
    if OVERRIDE_OPUS_TO_SONNET
    else MATRIX_NORMAL
)
LOG_FILE = Path(os.environ.get("CLAUDE_PROJECT_DIR", "C:/claude")) / ".claude" / "state" / "agent_model_decisions.jsonl"


def log_decision(record: dict) -> None:
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass  # log 실패가 작업 차단 사유 되지 않게


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            sys.exit(0)
        data = json.loads(raw)
    except Exception:
        sys.exit(0)

    if data.get("tool_name") != "Agent":
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    subagent_type = tool_input.get("subagent_type", "")
    existing_model = tool_input.get("model")

    # Case 1: model 이미 명시 → 통과 + 기록
    if existing_model:
        log_decision({
            "ts": datetime.utcnow().isoformat(),
            "phase": "preToolUse",
            "subagent_type": subagent_type,
            "decided_model": existing_model,
            "source": "lead_explicit",
        })
        print(json.dumps({"continue": True}))
        return

    # Case 2: model 없음 → 매트릭스 lookup
    decided = MATRIX.get(subagent_type, FALLBACK)
    source = "matrix" if subagent_type in MATRIX else "fallback"

    log_decision({
        "ts": datetime.utcnow().isoformat(),
        "phase": "preToolUse",
        "subagent_type": subagent_type,
        "decided_model": decided,
        "source": source,
    })

    # tool_input modify 시도 (Claude Code 가 지원하면 적용됨)
    # 미지원 시 continue: true 만 적용되어 원본 input 으로 진행
    # → 우리 14 agents 는 frontmatter sonnet 이라 안전 fallback
    modified = dict(tool_input)
    modified["model"] = decided

    print(json.dumps({
        "continue": True,
        "tool_input": modified,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": f"[model-enforcer] {subagent_type or '?'} → {decided} (source={source})"
        }
    }))


if __name__ == "__main__":
    main()

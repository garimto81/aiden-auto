#!/usr/bin/env python
"""jargon_guard.py — Stop hook: 비개발자 응답 스타일 자동 안전망 (2026-05-30)

⚠️ best-effort (신뢰 금지) — critic 검증 2026-05-30:
    본 hook 은 발동·감지·기록은 정상 작동(13회 실행 / 4세션 block 기록 확인)하나,
    **실제 재호출(재작성 강제)이 이 환경에서 일어나는지는 미검증**이다. 이유:
    (1) dispatcher 가 다중 Stop hook 의 stdout 을 병합 없이 raw 연결 → goal_stop_evaluator
        등이 동시 JSON 출력 시 `{...}{...}` 깨진 형태 → CC 가 파싱 못 해 신호 유실 가능.
        (단 active goal/pending task 없는 평범한 대화 = 본 hook 단독 출력 → 깨끗할 수 있음)
    (2) CC 의 Stop `decision:block` 재호출 계약이 SDK/CLI 버전별로 미검증 (codebase 주석 다수 명시).
    → **주 보증은 CLAUDE.md "응답 스타일 룰" ①(Lead 7-게이트) + ②(user-friendly-reporter agent).**
       본 hook 은 그 위의 보너스 그물. 미작동해도 무해(정상 종료). 의존 금지.
    재신뢰화하려면: dispatcher Stop JSON 병합 + live 재호출 실측 (backlog, 보류).

목적
    긴 기술 세션에서 Lead 응답이 개발자 말투로 드리프트하는 root cause 차단.
    매 응답 종료 시 발동 → 마지막 응답에 풀이 안 된 전문용어/내부 ID/A·B·C 나열이
    과도하면 CC 에 재작성 요청 (decision:block). user-friendly-reporter agent 규칙의
    결정적 안전망 layer (CLAUDE.md "응답 스타일 룰" + /auto Step 0.4 와 3중 방어).

계약 (CC 공식 Stop hook — claude-code-guide 확인 2026-05-30)
    stdout: {"decision": "block", "reason": "..."} → 정지 차단 + reason 을 Claude 에 재프롬프트
    빈 stdout + exit 0 → 자연 종료
    ※ 환경별 계약 차이 가능 (일부 CC 버전은 continue:true 패턴). 본 hook 은 공식 decision
      계약 사용. 미작동 시 무해 (정상 종료) — 신뢰 layer 는 CLAUDE.md 규칙 + agent.

루프 차단 (3중)
    1. stop_hook_active == true → 이미 1회 재프롬프트됨 → 즉시 통과 (CC 공식 신호)
    2. state 카운터 (session 별 연속 block ≤1) → stop_hook_active 미제공 환경 backup
    3. dispatcher BLOCK 전파는 max_exit 기반 — 본 hook 은 exit 0 유지, JSON 으로만 신호

보수성 (false positive 최소 — critic A4)
    egregious (강한 jargon 신호 다수 + 완화 마커 없음 + 충분히 긴 응답) 일 때만 block.
    이미 비유·풀이·다이어그램 있거나 / 짧거나 / 코드 위주면 통과.

device-agnostic: state 는 ~/.claude/state/ (personalization, 비동기화). hardcoded path 0.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

STATE_DIR = Path.home() / ".claude" / "state"
COUNTER_FILE = STATE_DIR / "jargon-guard-counter.json"
MAX_CONSECUTIVE_BLOCKS = 1  # rule 17 정합 — 한 응답 시퀀스에 재작성 1회만

# 풀이 없이 등장 시 의심되는 전문용어 (보수적 핵심 집합)
JARGON_TERMS = [
    "junction", "idempotent", "SSOT", "drift", "subagent", "refactor",
    "EXCLUDE", "reconcile", "dispatcher", "frontmatter", "mtime", "SHA256",
    "skip_newer", "effort_plan", "model-router", "PostToolUse", "REST",
    "Basic Auth", "stdout", "stderr", "stub", "schema", "deprecated",
    "promote", "canonical", "blast radius", "footgun",
]
# 내부 ID / tier 라벨 (절대 사용자 노출 금지)
INTERNAL_ID = re.compile(r"\b[HTNPCR]\d+\b")  # H1, T2, P4, C5, R3 식
TIER_LABEL = re.compile(r"\b(PLATEAU|CIRCUIT_BREAKER|PARADOX_ONLY|tier\s*[123]|T[123]\s*승격)\b", re.I)
# A/B/C 옵션 나열 (의미 차원 AskUserQuestion 아닌 기술 옵션 떠넘김)
ABC_OPTION = re.compile(r"(^|\n)\s*[\(\[]?\s*[ABC]\s*[안)\].:]\s", re.M)

# 완화 마커 — 있으면 통역 시도된 것으로 간주
MITIGATION = ["비유", "처럼", "같은 것", "쉽게 말하", "(=", "★", "─────"]


def _load_counter() -> dict:
    try:
        return json.loads(COUNTER_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_counter(data: dict) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        COUNTER_FILE.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass


def _count_unexplained_jargon(text: str) -> int:
    """풀이(=...) 없이 등장한 jargon 수. 보수적 — term 직후 60자 내 풀이 있으면 제외."""
    hits = 0
    low = text.lower()
    for term in JARGON_TERMS:
        for m in re.finditer(re.escape(term.lower()), low):
            window = text[m.start(): m.start() + 80]
            if "(=" in window or "(=" in text[max(0, m.start() - 30): m.start()]:
                continue  # 풀이됨
            hits += 1
            break  # term 당 1회만 카운트 (중복 폭증 방지)
    return hits


def _is_egregious(text: str) -> tuple[bool, str]:
    """block 여부 판정. 강한 신호(내부ID/tier/A·B·C)는 길이 무관 차단,
    jargon 밀도는 완화 마커 대비로 판정. 보수적 — clean 응답 false positive 0 목표."""
    # 코드 위주면 통과 (코드 블록 비중 높음)
    if text.count("```") >= 4:
        return False, "code-heavy — pass"

    internal = len(INTERNAL_ID.findall(text))
    tier = len(TIER_LABEL.findall(text))
    abc = len(ABC_OPTION.findall(text))
    jargon = _count_unexplained_jargon(text)
    mitig = sum(text.count(m) for m in MITIGATION)

    # 강한 신호 — 길이 무관 즉시 차단 (사용자 응답에 절대 노출 금지)
    if internal >= 2 or tier >= 1:
        return True, f"내부 ID/tier 라벨 누출 (id={internal}, tier={tier})"
    if abc >= 2:
        return True, f"A/B/C 기술 옵션 나열 {abc}건 (AskUserQuestion 아닌 떠넘김)"

    # 매우 짧고 jargon 적으면 nitpick 방지 — 통과
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 5 and jargon < 4:
        return False, f"short+low jargon — pass (jargon={jargon})"

    # jargon 다수 + 완화(비유/풀이/다이어그램) 부족 → 차단
    if jargon >= 4 and mitig < jargon:
        return True, f"풀이 안 된 전문용어 {jargon}건 (완화 마커 {mitig} < {jargon})"
    return False, f"pass (jargon={jargon}, mitig={mitig}, internal={internal})"


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0

    # 루프 차단 1: CC 공식 신호
    if payload.get("stop_hook_active"):
        return 0

    session_id = payload.get("session_id", "unknown")
    text = payload.get("transcript_excerpt", "") or payload.get("last_assistant_message", "")
    if not text:
        return 0

    # 루프 차단 2: state 카운터 (stop_hook_active 미제공 환경 backup)
    counter = _load_counter()
    sess = counter.get(session_id, {"blocks": 0})

    egregious, reason = _is_egregious(text)

    if not egregious:
        # 깨끗한 응답 → 카운터 리셋 + 자연 통과
        if session_id in counter:
            counter[session_id] = {"blocks": 0}
            _save_counter(counter)
        return 0

    if sess.get("blocks", 0) >= MAX_CONSECUTIVE_BLOCKS:
        # 이미 1회 재작성 요청함 → 무한루프 방지, 통과 (escalate 안 함 — 무해)
        counter[session_id] = {"blocks": 0}
        _save_counter(counter)
        return 0

    # block: 재작성 요청
    counter[session_id] = {"blocks": sess.get("blocks", 0) + 1}
    _save_counter(counter)
    msg = (
        "[비개발자 응답 게이트] 방금 응답에 풀이 안 된 전문용어/내부 ID/기술 옵션 나열이 "
        f"과도합니다 ({reason}). user-friendly-reporter 규칙으로 다시 작성하세요: "
        "전문용어 첫 등장 시 (=풀이) + 일상 비유 1개 이상 + 흐름은 ASCII 다이어그램 먼저 + "
        "결과→이유 순서 + A/B/C 나열 금지(자율 결정 또는 AskUserQuestion) + 내부 ID 누출 금지 + "
        "마지막 한 줄 요약. 핵심 원칙: 주제가 기술적일수록 통역을 더 한다."
    )
    print(json.dumps({"decision": "block", "reason": msg}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

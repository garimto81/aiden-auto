"""
cc_auth_check.py — SessionStart hook for Claude Code OAuth advisor-tool pattern.

Anthropic 공식 advisor-tool 패턴 ("Executor-Advisor 2-tier" server-side decision
injection)을 Claude Code CLI 자체 OAuth(.credentials.json claudeAiOauth)에 차용.

흐름:
  SessionStart
    -> evaluate_executor(creds, failures, previous_scopes)
        -> safe pass-through            : verdict=None, exit 0, no output
        -> near_expiry single signal    : AUTO_REFRESH (executor 직접 결정)
        -> escalate (모호/위험)         : evaluate_advisor(...)
            -> AUTO_REFRESH / PROMPT_USER / BLOCK / DEFER

verdict 별 hook output:
  AUTO_REFRESH : exit 0, stdout 빈 출력 (Claude Code 자체 refresh에 위임)
  DEFER        : exit 0, stdout 빈 출력
  PROMPT_USER  : exit 0, stdout JSON {"systemMessage": "..."}
  BLOCK        : exit 2, stdout JSON {"reason": "..."}

보안:
  - access_token 평문 절대 노출/로깅 X (sha256 16자 prefix 해시만)
  - refresh_token 평문 메모리 접근 최소화

References:
  - PRD: docs/00-prd/aiden-auto-cc-auth-advisor.prd.md
  - Protocol: references/cc-auth-advisor-protocol.md
  - Executor agent: agents/meta/cc-auth-executor.md
  - Advisor agent: agents/meta/cc-auth-advisor.md
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------- constants

CREDENTIALS_PATH = Path.home() / ".claude" / ".credentials.json"
STATE_DIR = Path.home() / ".claude" / "state"
SCHEMA_VERSION_VERDICT = "cc_auth_verdict_v1"
SCHEMA_VERSION_DECISIONS = "cc_auth_decisions_v1"

NEAR_EXPIRY_THRESHOLD_MS = 24 * 3600 * 1000   # 24시간
FAILURE_BURST_THRESHOLD = 3                    # 24시간 내 401 횟수
FAILURE_WINDOW_SECONDS = 24 * 3600


# ---------------------------------------------------------------- helpers

def _now_ms() -> int:
    return int(time.time() * 1000)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _hash_prefix(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def load_credentials(path: Path) -> dict:
    """`.credentials.json` 평문 파싱. 실패 시 빈 dict 반환 (silent skip)."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def load_failures(path: Path) -> list[dict]:
    """state/cc-auth-failures-{date}.json 로드 (없으면 빈 리스트)."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("failures", []) if isinstance(data, dict) else []
    except (json.JSONDecodeError, OSError):
        return []


def load_previous_scopes(path: Path, default: list[str]) -> list[str]:
    """직전 세션 scopes snapshot."""
    if not path.exists():
        return list(default)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("scopes", default) if isinstance(data, dict) else default
    except (json.JSONDecodeError, OSError):
        return list(default)


def save_scopes_snapshot(path: Path, scopes: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"scopes": list(scopes), "updated_at": _now_iso()}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------- executor (1차 게이트)

def evaluate_executor(
    creds: dict,
    failures: list[dict],
    previous_scopes: list[str],
) -> tuple[bool, dict]:
    """3-질문 빠른 평가. (should_escalate, signals) 반환.

    signals = {
      near_expiry:    expiresAt - now < 24h
      scopes_changed: scopes 변경
      failure_burst:  401 누적 ≥3회/24h
    }

    결정 룰:
      - 모두 NO → 통과 (escalate=False, verdict 없음)
      - near_expiry 단독 → executor가 직접 AUTO_REFRESH (escalate=False)
      - 그 외 → escalate=True (advisor 호출)
    """
    oauth = creds.get("claudeAiOauth", {}) if isinstance(creds, dict) else {}
    expires_at = oauth.get("expiresAt") or 0
    scopes = oauth.get("scopes") or []

    now_ms = _now_ms()
    now_s = now_ms / 1000

    near_expiry = bool(expires_at) and (expires_at - now_ms) < NEAR_EXPIRY_THRESHOLD_MS
    scopes_changed = set(scopes) != set(previous_scopes)

    recent_failures = [
        f for f in failures
        if isinstance(f, dict)
        and f.get("code") == 401
        and (now_s - f.get("ts", 0)) <= FAILURE_WINDOW_SECONDS
    ]
    failure_burst = len(recent_failures) >= FAILURE_BURST_THRESHOLD

    signals = {
        "near_expiry": near_expiry,
        "scopes_changed": scopes_changed,
        "failure_burst": failure_burst,
    }

    # Case A: 모두 NO → 안전 통과
    if not any(signals.values()):
        return (False, signals)

    # Case B: near_expiry 단독 → executor 직접 결정 (advisor 비용 절감)
    if signals == {"near_expiry": True, "scopes_changed": False, "failure_burst": False}:
        return (False, signals)

    # Case C: 모호/위험 → escalate
    return (True, signals)


def derive_verdict_from_executor(signals: dict) -> dict:
    """Executor가 직접 결정 가능한 verdict.

    - 모든 신호 NO            → PASS_THROUGH (안전, 무 로깅, 무 출력)
    - near_expiry 단독         → AUTO_REFRESH (Claude Code 자체 refresh 위임)
    - 그 외 (호출되지 않아야 함) → DEFER (방어적 기본값)
    """
    if not any(signals.values()):
        return {
            "schema_version": SCHEMA_VERSION_VERDICT,
            "verdict": "PASS_THROUGH",
            "tier": "executor",
            "weighted_score": None,
            "confidence": "HIGH",
            "rationale": "all signals clear — 토큰 정상, 무 로깅",
            "scores_per_question": None,
            "timestamp": _now_iso(),
        }
    if signals.get("near_expiry") and not signals.get("scopes_changed") and not signals.get("failure_burst"):
        return {
            "schema_version": SCHEMA_VERSION_VERDICT,
            "verdict": "AUTO_REFRESH",
            "tier": "executor",
            "weighted_score": None,
            "confidence": "HIGH",
            "rationale": "near_expiry 단독 신호 — Claude Code 자체 refresh에 위임",
            "scores_per_question": None,
            "timestamp": _now_iso(),
        }
    # 방어적 fallback (evaluate_executor가 이 경로로 보내지 않음)
    return {
        "schema_version": SCHEMA_VERSION_VERDICT,
        "verdict": "DEFER",
        "tier": "executor",
        "weighted_score": None,
        "confidence": "LOW",
        "rationale": "executor가 결정 불가, advisor 호출 필요 (fallback)",
        "scores_per_question": None,
        "timestamp": _now_iso(),
    }


# ---------------------------------------------------------------- advisor (2차, deterministic rule)

def evaluate_advisor(signals: dict, creds: dict) -> dict:
    """5-질문 정가중 평가. 결정적 휴리스틱으로 verdict 산출.

    (실제 LLM 호출이 아닌 결정적 룰 — hook은 즉시 응답이 필요하기 때문.
     LLM 기반 추세 분석은 harness-watcher가 별도 사이클로 수행.)
    """
    oauth = creds.get("claudeAiOauth", {}) if isinstance(creds, dict) else {}
    expires_at = oauth.get("expiresAt") or 0
    now_ms = _now_ms()
    delta_h = (expires_at - now_ms) / (3600 * 1000) if expires_at else 9999

    # 질문 1: 만료 임박 점수
    if delta_h < 1:
        score_1 = 10
    elif delta_h < 24:
        score_1 = 7
    elif delta_h < 48:
        score_1 = 5
    elif delta_h < 168:  # 1주
        score_1 = 2
    else:
        score_1 = 0

    # 질문 2: scope 변화 (단순 — 변화 있으면 7, 없으면 0)
    score_2 = 7 if signals.get("scopes_changed") else 0

    # 질문 3: 401 패턴
    score_3 = 10 if signals.get("failure_burst") else 0

    # 질문 4: rateLimitTier (현재 신호 없으면 0; 향후 history 비교로 확장)
    score_4 = 0

    # 질문 5: 작업 컨텍스트 의존도 (hook 시점에 모르므로 중립 5)
    score_5 = 5

    weighted = (
        score_1 * 0.25
        + score_2 * 0.20
        + score_3 * 0.25
        + score_4 * 0.15
        + score_5 * 0.15
    ) * 10  # 0-100

    # Security floor: 보안 위협 단일 신호(Q3 또는 Q4 ≥7)는
    # 다른 신호와 무관하게 critical로 분류 → weighted_score 70 floor 적용
    if score_3 >= 7 or score_4 >= 7:
        weighted = max(weighted, 70.0)

    # Verdict 결정 룰
    if score_3 >= 7 or score_4 >= 7:
        verdict_name = "BLOCK"
        confidence = "HIGH"
    elif score_2 >= 7:
        verdict_name = "PROMPT_USER"
        confidence = "MEDIUM"
    elif weighted >= 50:
        verdict_name = "PROMPT_USER"
        confidence = "MEDIUM"
    elif weighted >= 30:
        verdict_name = "AUTO_REFRESH"
        confidence = "HIGH"
    else:
        verdict_name = "DEFER"
        confidence = "MEDIUM"

    rationale = (
        f"Q1({score_1}/10) 만료={delta_h:.1f}h, "
        f"Q2({score_2}/10) scope변화={signals.get('scopes_changed')}, "
        f"Q3({score_3}/10) 401_burst={signals.get('failure_burst')}, "
        f"Q4({score_4}/10) tier=neutral, "
        f"Q5({score_5}/10) ctx=neutral. "
        f"weighted={weighted:.0f} → {verdict_name}"
    )

    return {
        "schema_version": SCHEMA_VERSION_VERDICT,
        "verdict": verdict_name,
        "tier": "advisor",
        "weighted_score": round(weighted),
        "confidence": confidence,
        "rationale": rationale,
        "scores_per_question": [score_1, score_2, score_3, score_4, score_5],
        "timestamp": _now_iso(),
    }


# ---------------------------------------------------------------- output + logging

def emit_hook_output(verdict: dict) -> int:
    """verdict → stdout + exit code 분기.

    Returns: exit code (0 또는 2)
    """
    v = verdict.get("verdict")
    rationale = verdict.get("rationale", "")

    if v == "PASS_THROUGH":
        return 0

    if v == "BLOCK":
        payload = {"reason": f"Claude Code OAuth BLOCK: {rationale}"}
        print(json.dumps(payload, ensure_ascii=False))
        return 2

    if v == "PROMPT_USER":
        msg = (
            "Claude Code 재인증 권장: `claude login`\n"
            f"(사유: {rationale})"
        )
        payload = {"systemMessage": msg}
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    # AUTO_REFRESH / DEFER / 미정 → 무 출력
    return 0


def log_decision(
    verdict: dict,
    log_path: Path,
    access_token_hash: str,
) -> None:
    """state/cc-auth-decisions-{date}.json에 append.

    - 평문 토큰 절대 X (해시만)
    - 파일 부재 시 신규 생성
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "schema_version": verdict.get("schema_version", SCHEMA_VERSION_VERDICT),
        "verdict": verdict.get("verdict"),
        "tier": verdict.get("tier"),
        "weighted_score": verdict.get("weighted_score"),
        "confidence": verdict.get("confidence"),
        "rationale": verdict.get("rationale", ""),
        "scores_per_question": verdict.get("scores_per_question"),
        "access_token_hash": access_token_hash,
        "timestamp": verdict.get("timestamp", _now_iso()),
    }

    if log_path.exists():
        try:
            existing = json.loads(log_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    else:
        existing = {}

    if not isinstance(existing, dict) or "decisions" not in existing:
        existing = {
            "schema_version": SCHEMA_VERSION_DECISIONS,
            "decisions": [],
        }

    existing["decisions"].append(record)
    log_path.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------- main

def main() -> int:
    """Hook entry point.

    Failure modes are silent (exit 0, no output) to prevent blocking SessionStart.
    Only BLOCK verdict returns exit 2.
    """
    try:
        creds = load_credentials(CREDENTIALS_PATH)
        oauth = creds.get("claudeAiOauth", {}) if isinstance(creds, dict) else {}

        # credentials 부재 → silent skip (예: claude login 미수행)
        if not oauth or "accessToken" not in oauth:
            return 0

        access_token = oauth.get("accessToken", "")
        access_token_hash = _hash_prefix(access_token) if access_token else "unknown"
        scopes = oauth.get("scopes") or []

        today = _today_str()
        failures_file = STATE_DIR / f"cc-auth-failures-{today}.json"
        scopes_snapshot_file = STATE_DIR / "cc-auth-scopes-snapshot.json"
        decisions_file = STATE_DIR / f"cc-auth-decisions-{today}.json"

        failures = load_failures(failures_file)
        previous_scopes = load_previous_scopes(scopes_snapshot_file, scopes)

        should_escalate, signals = evaluate_executor(creds, failures, previous_scopes)

        # scopes snapshot 갱신 (다음 세션을 위해)
        save_scopes_snapshot(scopes_snapshot_file, scopes)

        if not should_escalate:
            # 모두 NO (PASS_THROUGH)이거나 near_expiry 단독 (AUTO_REFRESH)
            verdict = derive_verdict_from_executor(signals)
            v_name = verdict.get("verdict")
            if v_name == "AUTO_REFRESH":
                # 단일 신호 케이스만 추세 로깅 (PASS_THROUGH는 무 로깅)
                log_decision(verdict, decisions_file, access_token_hash)
            return emit_hook_output(verdict)

        # escalate → advisor 평가
        verdict = evaluate_advisor(signals, creds)
        log_decision(verdict, decisions_file, access_token_hash)
        return emit_hook_output(verdict)

    except Exception as exc:  # pragma: no cover  # noqa: BLE001
        # 모든 예외는 silent (SessionStart 블로킹 방지)
        # stderr에만 짧게 기록 (개발용)
        sys.stderr.write(f"[cc_auth_check] silent skip: {type(exc).__name__}\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())

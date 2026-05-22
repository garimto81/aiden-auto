"""Model Fallback Ladder — haiku → sonnet → opus 자동 escalation.

핵심 아이디어:
  - 모든 super skill 호출 시 기본 haiku로 시도
  - 출력 평가 (heuristic):
    * 길이 너무 짧음 (<200 chars)
    * 에러 마커 ("unable to", "sorry, can't", "I cannot")
    * confidence 낮음 ("not sure", "maybe", "I think")
    * exit code != 0 또는 timeout
  - escalate 필요 시 sonnet으로 retry — 이전 답변 + 비판 context 전달
  - sonnet도 fail → opus
  - opus fail → 사용자 알림

사용자 결정 (lock):
  Q48: heuristic 자동 평가
  Q49: 모든 super skill 적용
  Q50: 이전 답변 + 비판 context 전달
  Q51: opus까지 escalate, cost 알림은 stderr
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ModelTier(str, Enum):
    HAIKU = "haiku"
    SONNET = "sonnet"
    OPUS = "opus"

    def next(self) -> Optional["ModelTier"]:
        ladder = [ModelTier.HAIKU, ModelTier.SONNET, ModelTier.OPUS]
        idx = ladder.index(self)
        return ladder[idx + 1] if idx + 1 < len(ladder) else None


# 만족 판정 heuristic 임계
MIN_OUTPUT_CHARS = 200
ERROR_MARKERS = [
    r"\bunable to\b",
    r"\bcan'?t (do|help|provide)\b",
    r"\bI cannot\b",
    r"\bI don'?t know\b",
    r"\bsorry,?\s+(but|I)",
    r"\bnot able\b",
    r"\binsufficient (information|context|data)\b",
]
LOW_CONFIDENCE_MARKERS = [
    r"\bnot sure\b",
    r"\bI think (?:maybe|perhaps)\b",
    r"\b(?:might|could)\s+be\s+(?:wrong|incorrect)\b",  # non-greedy: 직접 인접만
    r"\b[Mm]aybe\b",  # "maybe" 단독 등장도 카운트
    r"\bunclear\b",
    r"\b(?:I'?m|I am|I)\s+not\s+certain\b",  # "I am not certain"·"I'm not certain"·"I not certain"
    r"\bperhaps\b",
    r"\bprobably\b",
]


@dataclass
class QualityVerdict:
    satisfied: bool
    reasons: list[str]  # 만족하지 못한 이유 (escalate context로 전달)
    score: float  # 0.0 (총체적 실패) ~ 1.0 (만족)


def evaluate_output(output: str, *, exit_code: int = 0, timed_out: bool = False) -> QualityVerdict:
    """출력 quality heuristic 평가.

    Returns:
        QualityVerdict — satisfied=False면 다음 tier로 escalate
    """
    reasons: list[str] = []
    score = 1.0

    # 0. 실행 자체 실패
    if timed_out:
        reasons.append("timeout — 응답 미완성")
        score = 0.0
    if exit_code != 0:
        reasons.append(f"exit_code={exit_code} (정상 종료 아님)")
        score = min(score, 0.2)

    # 1. 길이 검사
    output_stripped = output.strip()
    if len(output_stripped) < MIN_OUTPUT_CHARS:
        reasons.append(f"출력 길이 부족 ({len(output_stripped)} < {MIN_OUTPUT_CHARS})")
        score = min(score, 0.4)

    # 2. 에러 마커 — 강력한 fail 신호
    for marker in ERROR_MARKERS:
        if re.search(marker, output, re.IGNORECASE):
            reasons.append(f"실패 마커 발견: '{marker}'")
            score = min(score, 0.2)

    # 3. confidence 마커 — 매칭 횟수 합계
    low_conf_total = 0
    for marker in LOW_CONFIDENCE_MARKERS:
        low_conf_total += len(re.findall(marker, output, re.IGNORECASE))
    if low_conf_total >= 2:
        reasons.append(f"낮은 confidence 마커 {low_conf_total}회")
        score = min(score, 0.5)

    # 4. 빈 응답 또는 placeholder
    if not output_stripped or output_stripped in ("...", "TODO", "TBD"):
        reasons.append("빈 응답 또는 placeholder")
        score = 0.0

    return QualityVerdict(
        satisfied=(score >= 0.7 and not reasons),
        reasons=reasons,
        score=round(score, 2),
    )


def build_retry_context(
    prev_output: str,
    prev_tier: ModelTier,
    verdict: QualityVerdict,
) -> str:
    """다음 tier 모델에게 전달할 retry context.

    Q50 결정: 이전 답변 + 비판 context 전달.
    """
    next_tier = prev_tier.next()
    next_name = next_tier.value if next_tier else "manual"

    return f"""<retry-escalation tier={prev_tier.value}-to-{next_name}>
이전 시도가 만족스럽지 않아 더 강력한 모델로 재시도합니다.

**이전 시도 ({prev_tier.value}, score={verdict.score})**:
{prev_output[:1000]}{'...(truncated)' if len(prev_output) > 1000 else ''}

**부족한 점 (heuristic 판정)**:
{chr(10).join('- ' + r for r in verdict.reasons)}

**개선 요구사항**:
이전 답변의 위 부족한 점을 개선하여 더 깊고 정확한 답변을 제공해주세요.
- 더 긴 분석 (충분한 detail)
- 명확한 결론 (hedge 단어 최소화)
- 구체적 evidence·예시
</retry-escalation>"""


def select_model(complexity: str, *, force_tier: ModelTier | None = None) -> ModelTier:
    """기본 모델 선정 — 사용자 정책: 모든 작업 haiku 시작.

    force_tier 명시되면 우선 (사용자 override).
    """
    if force_tier is not None:
        return force_tier
    return ModelTier.HAIKU


def should_escalate(verdict: QualityVerdict, current_tier: ModelTier) -> ModelTier | None:
    """escalation 필요 여부 + 다음 tier."""
    if verdict.satisfied:
        return None
    return current_tier.next()


__all__ = [
    "ModelTier",
    "QualityVerdict",
    "evaluate_output",
    "build_retry_context",
    "select_model",
    "should_escalate",
]

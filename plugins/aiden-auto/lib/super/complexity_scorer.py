"""Complexity Scorer — prompt → LOW/MEDIUM/HIGH → 모델 자동 선정.

사용자 결정 (Phase N):
  - 모든 작업 haiku 기본 시작
  - 만족 안 되면 sonnet → opus escalate

이 모듈은 **초기 모델 hint** 제공:
  - 트리비얼 prompt → haiku 강제 (escalation 거의 안 됨)
  - 명백히 복잡 prompt → sonnet으로 직접 시작 (haiku 시도 cost 절감)
  - 매우 복잡 prompt → opus 직접 시작

force_tier로 model_ladder.select_model에 전달.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from super.model_ladder import ModelTier
else:
    from .model_ladder import ModelTier


class Complexity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


# 복잡도 신호 (한국어 + 영문)
# Note: \b는 한글에서 작동 안 함 — 한글 키워드는 직접 substring 검사
HIGH_SIGNALS = [
    "아키텍처", r"\barchitecture\b",
    "전체 리팩토링", "전체 시스템", r"\brefactor\b.*entire",
    "복잡한 디버그", r"\bdebug.*\bcomplex\b",
    "분산", r"\bdistributed\b",
    "마이그레이션", r"\bmigration\b",
    "성능 최적화", "성능최적화", r"\bperformance\s+optimization\b",
    "보안 감사", r"\bsecurity\s+audit\b",
    r"\bend.?to.?end\b",
    "전체 구현",
]

MEDIUM_SIGNALS = [
    "구현", r"\bimplement\b",
    "기능 추가", "추가해", r"\badd\s+feature\b",
    "수정", r"\bfix\b",
    "리뷰", r"\breview\b",
    "테스트", r"\btest\b",
    "리팩토링", r"\brefactor\b",
    "분석", r"\banalyze\b",
    "디버그", r"\bdebug\b",
    "PR 만들", "커밋",
]

LOW_SIGNALS = [
    "이게 뭐", "이게뭐", r"\bwhat\s+is\b",
    "파일 보여", r"\bshow\s+(?:me\s+)?(?:the\s+)?file\b",
    "상태 확인", r"\bstatus\b",
    "커밋 로그", r"\bgit\s+log\b",
    "브랜치", r"\bbranch\b",
]


def _matches(pattern: str, text: str) -> bool:
    """regex pattern이면 re.search, 일반 substring이면 in."""
    if any(c in pattern for c in r"\^$*+?{}[]|()"):
        return bool(re.search(pattern, text, re.IGNORECASE))
    return pattern.lower() in text.lower()


@dataclass
class ComplexityVerdict:
    level: Complexity
    score: int  # cumulative weight
    matched_signals: list[str]
    recommended_tier: ModelTier


def score_prompt(prompt: str) -> ComplexityVerdict:
    """prompt 복잡도 점수 + 권장 모델 tier."""
    score = 0
    matched: list[str] = []

    for sig in HIGH_SIGNALS:
        if _matches(sig, prompt):
            score += 4
            matched.append(f"HIGH: {sig}")
    for sig in MEDIUM_SIGNALS:
        if _matches(sig, prompt):
            score += 2
            matched.append(f"MED: {sig}")
    for sig in LOW_SIGNALS:
        if _matches(sig, prompt):
            score -= 1
            matched.append(f"LOW: {sig}")

    # 길이 기반 보정
    word_count = len(prompt.split())
    if word_count > 50:
        score += 2
    elif word_count > 100:
        score += 4

    # 다중 카테고리 신호 (e.g. "리뷰하고 PR 만들어")
    multi_signals = [r"\b그리고\b", r"\b그 후\b", r"\bafter\b", r"\bthen\b"]
    multi_count = sum(1 for sig in multi_signals if re.search(sig, prompt, re.IGNORECASE))
    if multi_count >= 1:
        score += 2 * multi_count

    # tier 결정
    if score >= 6:
        level = Complexity.HIGH
        tier = ModelTier.OPUS
    elif score >= 2:
        level = Complexity.MEDIUM
        tier = ModelTier.SONNET
    else:
        level = Complexity.LOW
        tier = ModelTier.HAIKU

    return ComplexityVerdict(
        level=level,
        score=score,
        matched_signals=matched[:5],  # 최대 5개만 보고
        recommended_tier=tier,
    )


__all__ = ["Complexity", "ComplexityVerdict", "score_prompt"]

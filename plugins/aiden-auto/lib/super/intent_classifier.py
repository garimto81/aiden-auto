"""Intent Classifier — keyword·heuristic 기반 사용자 prompt 분류.

LLM 의존 0. 토큰 비용 0. confidence 임계로 모호 케이스 처리.

12 super skill 카테고리 매핑:
  plan / check / simplify / commit / debug / tdd /
  parallel / verify / skill-create / research / pr / (auto)

CLI:
  python intent_classifier.py "이 코드 리뷰해줘"
  → category=check confidence=0.85 intent_type=simple
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from enum import Enum


class IntentType(str, Enum):
    SIMPLE = "simple"
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    AMBIGUOUS = "ambiguous"


@dataclass
class CategoryScore:
    category: str
    confidence: float
    matched_keywords: list[str] = field(default_factory=list)


@dataclass
class ClassificationResult:
    prompt: str
    categories: list[CategoryScore]
    intent_type: IntentType
    bypass: bool = False
    bypass_reason: str = ""

    @property
    def top_category(self) -> CategoryScore | None:
        return self.categories[0] if self.categories else None

    @property
    def max_confidence(self) -> float:
        return self.top_category.confidence if self.top_category else 0.0


# ---- Bypass 룰 (Section 8.1 우선순위 행렬) ----

SLASH_PATTERN = re.compile(r"^\s*/[a-zA-Z][\w-]*", re.MULTILINE)
MAGIC_WORDS = ("!quick", "!just", "!hotfix")
NO_AUTO_FLAG = "--no-auto"
SUB_ORCHESTRATION = "<sub-orchestration"

QUESTION_PATTERNS = [
    r"이게\s*뭐야",
    r"무엇이|무엇인가",
    r"설명해\s*줘",
    r"어떻게\s*동작",
    r"what\s+is\b",
    r"how\s+does\b",
    r"explain\b",
]

FILE_READ_PATTERNS = [
    r"파일\s*보여\s*줘",
    r"내용\s*확인",
    r"현재\s*상태\s*확인",
    r"show\s+me\s+the\s+(file|content)",
]


SYSTEM_MESSAGE_PATTERNS = [
    r"^\s*<task-notification>",
    r"^\s*<system-reminder>",
    r"^\s*<command-name>",
    r"^\s*<command-message>",
    r"^\s*<local-command-stdout>",
    r"^\s*<local-command-caveat>",
]


def _is_bypass(prompt: str) -> tuple[bool, str]:
    """bypass 조건 검사. (bypass 여부, 사유)."""
    stripped = prompt.lstrip()

    # 시스템 메시지 (사용자 입력 아님) — 항상 bypass
    for pat in SYSTEM_MESSAGE_PATTERNS:
        if re.search(pat, prompt, re.MULTILINE):
            return True, "system_message"

    if SLASH_PATTERN.match(stripped):
        return True, "explicit_slash"
    for mw in MAGIC_WORDS:
        if mw in prompt:
            return True, f"magic_word:{mw}"
    if NO_AUTO_FLAG in prompt:
        return True, "no_auto_flag"
    if SUB_ORCHESTRATION in prompt:
        return True, "sub_orchestration"

    for pat in QUESTION_PATTERNS:
        if re.search(pat, stripped, re.IGNORECASE):
            return True, "question"
    for pat in FILE_READ_PATTERNS:
        if re.search(pat, stripped, re.IGNORECASE):
            return True, "file_read"

    return False, ""


# ---- 카테고리 트리거 매핑 (Section 3.3) ----

CATEGORY_TRIGGERS: dict[str, dict] = {
    "plan": {
        "keywords_strong": ["계획", "기획", "설계", "plan", "design", "brainstorm", "기능 추가", "만들어줘", "구현"],
        "keywords_weak": ["새", "신규", "생각", "feature", "implement"],
        "weight": 1.0,
    },
    "check": {
        "keywords_strong": ["리뷰", "검토", "검사", "review", "품질", "보안", "security"],
        "keywords_weak": ["pr", "PR", "체크", "check", "감사"],
        "weight": 1.0,
    },
    "simplify": {
        "keywords_strong": ["단순화", "정리", "리팩토링", "refactor", "slop", "깔끔"],
        "keywords_weak": ["clean", "simplify", "개선"],
        "weight": 1.0,
    },
    "commit": {
        "keywords_strong": ["커밋", "commit", "conventional", "메시지"],
        "keywords_weak": ["push", "스테이지", "stage"],
        "weight": 1.0,
    },
    "debug": {
        "keywords_strong": ["디버그", "debug", "안 돼", "안돼", "에러", "버그", "bug", "error", "실패"],
        "keywords_weak": ["문제", "이슈", "왜", "fail"],
        "weight": 1.0,
    },
    "tdd": {
        "keywords_strong": ["테스트", "TDD", "test", "red-green", "pytest", "unit test"],
        "keywords_weak": ["spec", "테스트 먼저"],
        "weight": 1.0,
    },
    "parallel": {
        "keywords_strong": ["병렬", "parallel", "동시에", "ultrawork", "swarm", "여러 개"],
        "keywords_weak": ["multi", "concurrent"],
        "weight": 1.0,
    },
    "verify": {
        "keywords_strong": ["검증", "verify", "완료", "다 됐", "evidence", "validate"],
        "keywords_weak": ["confirm", "done"],
        "weight": 1.0,
    },
    "skill-create": {
        "keywords_strong": ["스킬 만들", "skill create", "능력 추가", "스킬화"],
        "keywords_weak": ["skill", "ability"],
        "weight": 1.0,
    },
    "research": {
        "keywords_strong": ["리서치", "research", "조사", "알아봐", "찾아봐", "어떻게 쓰"],
        "keywords_weak": ["search", "lookup", "investigate", "분석"],
        "weight": 1.0,
    },
    "pr": {
        "keywords_strong": ["PR 만들", "PR 생성", "머지", "merge", "pull request"],
        "keywords_weak": ["finishing", "종료"],
        "weight": 0.9,
    },
}


# ---- 의도 타입 시그널 ----

DEPENDENCY_SIGNALS = ["후에", "다음에", "그리고 나서", "그 후", "after", "then", "→", "->"]
PARALLEL_SIGNALS = ["동시에", "함께", "병렬", "parallel", "concurrently", "여러 개", "multiple"]


def _score_category(prompt: str, cfg: dict) -> tuple[float, list[str]]:
    """카테고리 single 점수: 0.0~1.0 + 매칭 키워드."""
    matched: list[str] = []
    score = 0.0
    for kw in cfg["keywords_strong"]:
        if kw.lower() in prompt.lower():
            matched.append(kw)
            score += 0.55  # single strong = above 0.5 auto threshold
    for kw in cfg["keywords_weak"]:
        if kw.lower() in prompt.lower():
            matched.append(kw)
            score += 0.15
    score *= cfg.get("weight", 1.0)
    return min(score, 1.0), matched


def _detect_intent_type(prompt: str, num_categories: int) -> IntentType:
    if num_categories == 0:
        return IntentType.AMBIGUOUS
    if num_categories == 1:
        return IntentType.SIMPLE
    has_dep = any(sig in prompt.lower() for sig in DEPENDENCY_SIGNALS)
    has_par = any(sig in prompt.lower() for sig in PARALLEL_SIGNALS)
    if has_par and not has_dep:
        return IntentType.PARALLEL
    return IntentType.SEQUENTIAL  # default for multi


def classify(prompt: str, *, min_confidence: float = 0.3) -> ClassificationResult:
    """사용자 prompt 분류."""
    bypass, reason = _is_bypass(prompt)
    if bypass:
        return ClassificationResult(
            prompt=prompt,
            categories=[],
            intent_type=IntentType.AMBIGUOUS,
            bypass=True,
            bypass_reason=reason,
        )

    scores: list[CategoryScore] = []
    for cat, cfg in CATEGORY_TRIGGERS.items():
        score, matched = _score_category(prompt, cfg)
        if score >= min_confidence:
            scores.append(CategoryScore(category=cat, confidence=score, matched_keywords=matched))

    scores.sort(key=lambda s: s.confidence, reverse=True)

    intent_type = _detect_intent_type(prompt, len(scores))
    return ClassificationResult(
        prompt=prompt,
        categories=scores,
        intent_type=intent_type,
    )


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        sys.stderr.write("Usage: intent_classifier.py <prompt>\n")
        return 1
    prompt = " ".join(args)
    result = classify(prompt)
    out = {
        "prompt": result.prompt,
        "bypass": result.bypass,
        "bypass_reason": result.bypass_reason,
        "intent_type": result.intent_type.value,
        "categories": [asdict(c) for c in result.categories],
        "max_confidence": result.max_confidence,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

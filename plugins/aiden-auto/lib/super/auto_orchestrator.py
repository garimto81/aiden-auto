"""Auto Orchestrator — intent_classifier 결과를 기반으로 super skill 호출 sequence 빌드.

핵심 책임:
  1. ClassificationResult를 받아 orchestration plan 생성 (single/seq/parallel)
  2. 각 카테고리를 super skill 이름으로 매핑
  3. context handoff 메타데이터 준비
  4. audit_logger 기록 entry 생성
  5. attribution 헤더 문자열 출력 (사용자에게 노출)

런타임 호출은 Skill tool로 모델이 수행 — 본 모듈은 plan + 메타데이터 생성만.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from super.intent_classifier import (
        CategoryScore,
        ClassificationResult,
        IntentType,
        classify,
    )
else:
    from .intent_classifier import (
        CategoryScore,
        ClassificationResult,
        IntentType,
        classify,
    )


CATEGORY_TO_SKILL = {
    "analyze": "aiden-auto:analyze",  # NEW — 모든 chain 첫 단계
    "plan": "aiden-auto:plan",
    "check": "aiden-auto:check",
    "simplify": "aiden-auto:simplify",
    "commit": "aiden-auto:commit",
    "debug": "aiden-auto:debug",
    "tdd": "aiden-auto:tdd",
    "parallel": "aiden-auto:parallel",
    "verify": "aiden-auto:verify",
    "skill-create": "aiden-auto:skill-create",
    "research": "aiden-auto:research",
    "pr": "aiden-auto:pr",
}


def _make_analyze_step() -> "OrchestrationStep":
    """모든 chain 첫 단계 — 사용자 의도 본격 분석.

    Q38 결정: 모든 workflow는 analyze로 시작 (mandate, opt-out 없음).
    """
    return OrchestrationStep(
        order=0,
        super_skill="aiden-auto:analyze",
        confidence=1.0,
        rationale="user intent analysis (mandatory phase 0)",
    )


@dataclass
class OrchestrationStep:
    order: int
    super_skill: str
    confidence: float
    rationale: str  # 매칭된 키워드 등


@dataclass
class OrchestrationPlan:
    pattern: str  # "single" | "sequential" | "parallel" | "ambiguous"
    steps: list[OrchestrationStep] = field(default_factory=list)
    intent_type: str = ""
    audit_entry: dict = field(default_factory=dict)
    attribution_line: str = ""

    @property
    def is_executable(self) -> bool:
        return self.pattern in ("single", "sequential", "parallel") and bool(self.steps)


# ---- 패턴 결정 (Section 8.3) ----

CONFIDENCE_AUTO_THRESHOLD = 0.5  # 이상이면 자동, 미만이면 AskUserQuestion 권유
CONFIDENCE_HIGH_THRESHOLD = 0.7  # single 패턴 강제 임계


def build_plan(
    result: ClassificationResult,
    *,
    auto_threshold: float = CONFIDENCE_AUTO_THRESHOLD,
) -> OrchestrationPlan:
    """ClassificationResult → OrchestrationPlan."""
    if result.bypass:
        return OrchestrationPlan(
            pattern="bypass",
            intent_type=result.intent_type.value,
            audit_entry={
                "ts": _now(),
                "prompt": result.prompt,
                "bypass": True,
                "bypass_reason": result.bypass_reason,
            },
            attribution_line=f"[auto] bypass ({result.bypass_reason})",
        )

    if not result.categories:
        return OrchestrationPlan(
            pattern="ambiguous",
            intent_type=result.intent_type.value,
            audit_entry={
                "ts": _now(),
                "prompt": result.prompt,
                "categories": [],
                "pattern": "ambiguous",
            },
            attribution_line="[auto] ambiguous — AskUserQuestion 권유",
        )

    if result.max_confidence < auto_threshold:
        return OrchestrationPlan(
            pattern="ambiguous",
            intent_type=result.intent_type.value,
            audit_entry={
                "ts": _now(),
                "prompt": result.prompt,
                "categories": [asdict(c) for c in result.categories],
                "pattern": "ambiguous",
                "max_confidence": result.max_confidence,
            },
            attribution_line=f"[auto] ambiguous (max conf={result.max_confidence:.2f}) — AskUserQuestion 권유",
        )

    # 패턴 결정 — analyze 항상 first
    if len(result.categories) == 1 or result.max_confidence >= CONFIDENCE_HIGH_THRESHOLD:
        pattern = "single"
        steps = [_make_analyze_step(), _make_step(result.categories[0], 1)]
    else:
        # multi-category
        if result.intent_type == IntentType.PARALLEL:
            pattern = "parallel"
            steps = [_make_analyze_step()] + [_make_step(c, i + 1) for i, c in enumerate(result.categories[:5])]  # analyze + 최대 5
        else:
            pattern = "sequential"
            steps = _order_sequential(result.categories[:5])

    chain_str = " → ".join(s.super_skill for s in steps)
    attribution = (
        f"[auto] intent={result.intent_type.value} pattern={pattern} "
        f"conf={result.max_confidence:.2f} → {chain_str}"
    )

    audit_entry = {
        "ts": _now(),
        "prompt": result.prompt,
        "categories": [asdict(c) for c in result.categories],
        "pattern": pattern,
        "intent_type": result.intent_type.value,
        "max_confidence": result.max_confidence,
        "invoked": [s.super_skill for s in steps],
    }

    return OrchestrationPlan(
        pattern=pattern,
        steps=steps,
        intent_type=result.intent_type.value,
        audit_entry=audit_entry,
        attribution_line=attribution,
    )


def _make_step(score: CategoryScore, order: int) -> OrchestrationStep:
    return OrchestrationStep(
        order=order,
        super_skill=CATEGORY_TO_SKILL.get(score.category, f"aiden-auto:{score.category}"),
        confidence=score.confidence,
        rationale=", ".join(score.matched_keywords[:3]),
    )


def _order_sequential(categories: list[CategoryScore]) -> list[OrchestrationStep]:
    """sequential 패턴 — analyze first, then PDCA priority order.

    Order: analyze → plan → research → tdd → simplify → debug → check → verify → commit → pr
    """
    priority = ["plan", "research", "tdd", "simplify", "debug", "check", "verify", "commit", "pr", "parallel", "skill-create"]
    cat_to_score = {c.category: c for c in categories}
    ordered: list[OrchestrationStep] = [_make_analyze_step()]  # always first
    counter = 1
    for cat in priority:
        if cat in cat_to_score:
            ordered.append(_make_step(cat_to_score[cat], counter))
            counter += 1
    for c in categories:
        if c.category not in priority:
            ordered.append(_make_step(c, counter))
            counter += 1
    return ordered


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_audit(plan: OrchestrationPlan, *, audit_path: Path) -> None:
    """audit/auto-routing.ndjson에 결정 기록."""
    if not plan.audit_entry:
        return
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(plan.audit_entry, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        sys.stderr.write("Usage: auto_orchestrator.py <prompt>\n")
        return 1
    prompt = " ".join(args)
    result = classify(prompt)
    plan = build_plan(result)
    print(plan.attribution_line)
    print()
    print(json.dumps({
        "pattern": plan.pattern,
        "intent_type": plan.intent_type,
        "steps": [asdict(s) for s in plan.steps],
        "audit": plan.audit_entry,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

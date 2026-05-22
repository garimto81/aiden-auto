"""Delegation Planner — DAG → Task tool 호출 sequence (stub).

현재는 플레이스홀더. 미래 Phase P에서 본격 구현 예정.

목적:
  - TaskDAG → "이 노드는 main에서, 저 노드는 subagent로" 결정
  - subagent_type 매핑 (architect / executor / qa-tester ...)
  - 모델 tier 매핑
  - 결과 병합 정책

미래 구현 시 사용할 인터페이스:
  DelegationStep(node, subagent_type, model, can_run_parallel)
  DelegationPlan(steps, expected_tokens)
  plan_delegation(dag: TaskDAG) -> DelegationPlan
"""
from __future__ import annotations

from dataclasses import dataclass, field

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from super.task_dag import TaskDAG, TaskNode
    from super.model_ladder import ModelTier
else:
    from .task_dag import TaskDAG, TaskNode
    from .model_ladder import ModelTier


# subagent_type 매핑 (oh-my-claudecode pattern)
COMPLEXITY_TO_SUBAGENT = {
    "search": "explore",       # 코드 탐색
    "code_change": "executor",  # 구현·수정
    "analysis": "architect",   # 깊은 분석
    "test": "qa-tester",       # 테스트
    "review": "code-reviewer",  # 리뷰
    "doc": "writer",           # 문서
}


@dataclass
class DelegationStep:
    node_id: str
    label: str
    subagent_type: str | None  # None = main에서 직접
    model: ModelTier
    can_run_parallel: bool = False


@dataclass
class DelegationPlan:
    steps: list[DelegationStep] = field(default_factory=list)
    expected_token_savings: int = 0  # 추정 — 미래 telemetry 기반

    @property
    def parallel_groups(self) -> list[list[DelegationStep]]:
        """병렬 가능한 step 그룹화."""
        groups: list[list[DelegationStep]] = []
        current: list[DelegationStep] = []
        for step in self.steps:
            if step.can_run_parallel and current:
                current.append(step)
            else:
                if current:
                    groups.append(current)
                current = [step]
        if current:
            groups.append(current)
        return groups


def plan_delegation(dag: TaskDAG) -> DelegationPlan:
    """stub — 단일 main step.

    미래 구현 시:
      - dag.topological_order 순회
      - 같은 그룹 (의존 없음) → can_run_parallel=True
      - complexity·label 분석 → subagent_type 결정
      - tier는 노드 recommended_tier 사용
    """
    steps: list[DelegationStep] = []
    for group in dag.topological_order:
        for node in group:
            steps.append(DelegationStep(
                node_id=node.id,
                label=node.label,
                subagent_type=None,  # stub: main 처리
                model=node.recommended_tier,
                can_run_parallel=len(group) > 1,
            ))
    return DelegationPlan(steps=steps)


__all__ = ["DelegationStep", "DelegationPlan", "plan_delegation", "COMPLEXITY_TO_SUBAGENT"]

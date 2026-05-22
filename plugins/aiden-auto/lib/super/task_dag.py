"""Task DAG — 작업 의존 그래프 추출 (stub).

현재는 플레이스홀더. 미래 Phase P에서 본격 구현 예정.

목적:
  - 사용자 prompt를 작업 노드들로 분해
  - 노드 간 의존성 매핑 (A → B 또는 A ⊥ B)
  - 독립 노드 = subagent 병렬 위임 후보

미래 구현 시 사용할 인터페이스:
  TaskNode(id, label, dependencies, complexity, recommended_tier)
  TaskDAG(nodes, edges)
  extract_dag(prompt: str) -> TaskDAG
"""
from __future__ import annotations

from dataclasses import dataclass, field

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from super.complexity_scorer import Complexity
    from super.model_ladder import ModelTier
else:
    from .complexity_scorer import Complexity
    from .model_ladder import ModelTier


@dataclass
class TaskNode:
    id: str
    label: str
    dependencies: list[str] = field(default_factory=list)  # 다른 node id
    complexity: Complexity = Complexity.LOW
    recommended_tier: ModelTier = ModelTier.HAIKU
    can_delegate: bool = True


@dataclass
class TaskDAG:
    nodes: list[TaskNode] = field(default_factory=list)

    @property
    def independent_nodes(self) -> list[TaskNode]:
        """의존성 없는 노드 (병렬 위임 후보)."""
        return [n for n in self.nodes if not n.dependencies]

    @property
    def topological_order(self) -> list[list[TaskNode]]:
        """의존성 순서대로 그룹화 — 같은 그룹은 병렬 가능.

        간단한 BFS topological sort. cycle 없음 가정 (사용자 prompt 기반).
        """
        if not self.nodes:
            return []
        node_map = {n.id: n for n in self.nodes}
        remaining = {n.id: list(n.dependencies) for n in self.nodes}
        result: list[list[TaskNode]] = []
        while remaining:
            ready_ids = [nid for nid, deps in remaining.items() if not deps]
            if not ready_ids:
                # cycle or missing dep — 남은 모두 break
                result.append([node_map[nid] for nid in remaining])
                break
            result.append([node_map[nid] for nid in ready_ids])
            for nid in ready_ids:
                del remaining[nid]
            for deps in remaining.values():
                for nid in ready_ids:
                    if nid in deps:
                        deps.remove(nid)
        return result


def extract_dag(prompt: str) -> TaskDAG:
    """stub — 사용자 prompt를 단일 node DAG로.

    미래 구현: 모델이 직접 분해 (analyze phase에서 호출).
    현재는 plan 단순화: prompt 전체를 1 노드로.
    """
    return TaskDAG(nodes=[TaskNode(
        id="root",
        label=prompt[:80],
        dependencies=[],
        complexity=Complexity.LOW,
        recommended_tier=ModelTier.HAIKU,
        can_delegate=False,
    )])


__all__ = ["TaskNode", "TaskDAG", "extract_dag"]

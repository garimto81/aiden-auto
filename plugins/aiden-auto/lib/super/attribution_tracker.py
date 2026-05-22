"""super SKILL.md의 line range → source 매핑 추적.

사용 시 시나리오:
  - 디버깅: super skill의 임의 line이 어느 source에서 왔는지 즉시 식별
  - sync: source drift 시 영향받는 super skill의 섹션 범위 산정

attribution_map.json:
{
  "category": "tdd",
  "super_path": "skills/tdd/SKILL.md",
  "ranges": [
    {"line_start": 10, "line_end": 80, "source_id": "superpowers:tdd@sha256:abc", "role": "backbone"},
    ...
  ]
}
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class AttributionEntry:
    line_start: int
    line_end: int  # exclusive
    source_id: str
    role: str  # backbone | absorber | complement


class AttributionTracker:
    def __init__(self) -> None:
        self.entries: list[AttributionEntry] = []

    def add(self, *, line_start: int, line_end: int, source_id: str, role: str) -> None:
        self.entries.append(
            AttributionEntry(
                line_start=line_start,
                line_end=line_end,
                source_id=source_id,
                role=role,
            )
        )

    def reset(self) -> None:
        self.entries.clear()

    def serialize(self, *, category: str, super_path: str) -> dict:
        return {
            "category": category,
            "super_path": super_path,
            "ranges": [asdict(e) for e in self.entries],
        }

    def write(self, out_path: Path, *, category: str, super_path: str) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(
                self.serialize(category=category, super_path=super_path),
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def lookup(self, line_no: int) -> AttributionEntry | None:
        for e in self.entries:
            if e.line_start <= line_no < e.line_end:
                return e
        return None

    @classmethod
    def load(cls, path: Path) -> "AttributionTracker":
        data = json.loads(path.read_text(encoding="utf-8"))
        out = cls()
        for r in data.get("ranges", []):
            out.add(**r)
        return out

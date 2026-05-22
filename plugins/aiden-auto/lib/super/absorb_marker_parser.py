"""SKILL.md를 H2/H3 섹션 단위로 파싱.

sources.yaml의 absorb 룰(section_h2 / section_h3 / contains)에 따라
대상 섹션을 추출한다. 외부 SKILL.md는 절대 수정하지 않으므로 룰은 호출 측 메타데이터에서만 정의한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


_HEADER_RE = re.compile(r"^(#+)\s+(.*?)\s*$")


@dataclass
class ParsedSection:
    level: int  # 1~6 (H1~H6)
    title: str
    body: str  # heading 라인 포함
    line_start: int
    line_end: int


class AbsorbMarkerParser:
    """SKILL.md 본문을 섹션 트리로 분해."""

    def parse_sections(self, body: str) -> list[ParsedSection]:
        lines = body.splitlines()
        headers: list[tuple[int, int, str]] = []
        for idx, line in enumerate(lines):
            m = _HEADER_RE.match(line)
            if m:
                headers.append((idx, len(m.group(1)), m.group(2).strip()))

        out: list[ParsedSection] = []
        for i, (line_idx, level, title) in enumerate(headers):
            end = headers[i + 1][0] if i + 1 < len(headers) else len(lines)
            section_body = "\n".join(lines[line_idx:end])
            out.append(
                ParsedSection(
                    level=level,
                    title=title,
                    body=section_body,
                    line_start=line_idx,
                    line_end=end,
                )
            )
        return out

    def find_section(
        self,
        body: str,
        *,
        section_h2: str | None = None,
        section_h3: str | None = None,
        contains: str | None = None,
    ) -> ParsedSection | None:
        for s in self.parse_sections(body):
            if section_h2 is not None and s.level == 2 and s.title == section_h2:
                return s
            if section_h3 is not None and s.level == 3 and s.title == section_h3:
                return s
            if contains is not None and contains in s.body:
                return s
        return None

    def extract_by_rules(self, body: str, rules: Iterable[dict]) -> list[ParsedSection]:
        seen: set[tuple[int, int]] = set()
        out: list[ParsedSection] = []
        for rule in rules:
            section = self.find_section(
                body,
                section_h2=rule.get("section_h2"),
                section_h3=rule.get("section_h3"),
                contains=rule.get("contains"),
            )
            if section and (section.line_start, section.line_end) not in seen:
                seen.add((section.line_start, section.line_end))
                out.append(section)
        return out

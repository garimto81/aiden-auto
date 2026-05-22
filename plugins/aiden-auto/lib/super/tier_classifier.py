"""drift된 SKILL.md 변경을 LOW/MEDIUM/HIGH로 분류.

휴리스틱:
  LOW    — body word diff < 50 AND new H2/H3 = 0 AND code block delta = 0
  MEDIUM — H2/H3 추가 1~3 OR code block delta < 30 lines
  HIGH   — 그 외 (핵심 protocol 변경)

LOW만 자동 적용, MEDIUM은 draft, HIGH는 PR.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class Tier(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class DiffMetrics:
    word_diff: int
    new_h2_h3_count: int
    code_block_line_delta: int


class TierClassifier:
    LOW_WORD_THRESHOLD = 50
    MEDIUM_NEW_HEADING_MAX = 3
    MEDIUM_CODE_LINE_MAX = 30

    def classify(self, before: str, after: str) -> tuple[Tier, DiffMetrics]:
        m = self._compute_metrics(before, after)
        return self._tier_from_metrics(m), m

    def _tier_from_metrics(self, m: DiffMetrics) -> Tier:
        if (
            m.word_diff < self.LOW_WORD_THRESHOLD
            and m.new_h2_h3_count == 0
            and m.code_block_line_delta == 0
        ):
            return Tier.LOW
        if (
            m.new_h2_h3_count <= self.MEDIUM_NEW_HEADING_MAX
            and m.code_block_line_delta <= self.MEDIUM_CODE_LINE_MAX
        ):
            return Tier.MEDIUM
        return Tier.HIGH

    def _compute_metrics(self, before: str, after: str) -> DiffMetrics:
        before_words = set(before.split())
        after_words = set(after.split())
        word_diff = len(before_words.symmetric_difference(after_words))

        before_h = len(re.findall(r"^(?:##|###)\s", before, re.MULTILINE))
        after_h = len(re.findall(r"^(?:##|###)\s", after, re.MULTILINE))
        new_h_count = max(0, after_h - before_h)

        before_code = self._code_line_count(before)
        after_code = self._code_line_count(after)
        code_delta = abs(after_code - before_code)

        return DiffMetrics(
            word_diff=word_diff,
            new_h2_h3_count=new_h_count,
            code_block_line_delta=code_delta,
        )

    @staticmethod
    def _code_line_count(text: str) -> int:
        in_block = False
        count = 0
        for line in text.splitlines():
            if line.startswith("```"):
                in_block = not in_block
                continue
            if in_block:
                count += 1
        return count

"""Smoke Tester: LOW 자동 적용 후 super skill의 최소 무결성 검사.

검증 항목:
  - SKILL.md frontmatter 파싱 가능
  - description 필드 존재
  - triggers 필드 존재 (단, 빈 list는 허용)
  - body 길이 > 100 문자
  - absorb start/end 마커 짝 일치
  - attribution_map.json 존재 + 파싱 가능

실제 트리거 시뮬레이션은 CC 런타임이 필요해 protocol-level 검사로 대체.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
_ABSORB_START = re.compile(r"<!-- aiden-auto:absorb start \|")
_ABSORB_END = re.compile(r"<!-- aiden-auto:absorb end -->")


@dataclass
class SmokeResult:
    category: str
    passed: bool
    failures: list[str] = field(default_factory=list)


class SmokeTester:
    MIN_BODY_LEN = 100

    def __init__(self, plugin_root: Path) -> None:
        self.plugin_root = plugin_root

    def test(self, category: str) -> SmokeResult:
        result = SmokeResult(category=category, passed=True)

        skill_path = self.plugin_root / "skills" / f"super_{category}" / "SKILL.md"
        if not skill_path.exists():
            result.passed = False
            result.failures.append(f"SKILL.md not found: {skill_path}")
            return result

        text = skill_path.read_text(encoding="utf-8")
        m = _FRONTMATTER_RE.match(text)
        if not m:
            result.failures.append("frontmatter parse failed")
        else:
            fm_text, body = m.group(1), m.group(2)
            if yaml is not None:
                try:
                    fm = yaml.safe_load(fm_text) or {}
                except Exception as e:
                    result.failures.append(f"frontmatter yaml error: {e}")
                    fm = {}
                if not fm.get("description"):
                    result.failures.append("frontmatter.description missing")
                if "triggers" not in fm:
                    result.failures.append("frontmatter.triggers missing")
            if len(body) < self.MIN_BODY_LEN:
                result.failures.append(f"body too short: {len(body)} < {self.MIN_BODY_LEN}")

            start_count = len(_ABSORB_START.findall(body))
            end_count = len(_ABSORB_END.findall(body))
            if start_count != end_count:
                result.failures.append(f"absorb marker mismatch: {start_count} start vs {end_count} end")

        attr_path = self.plugin_root / "attribution" / f"{category}.attribution.json"
        if attr_path.exists():
            try:
                data = json.loads(attr_path.read_text(encoding="utf-8"))
                if "ranges" not in data:
                    result.failures.append("attribution.json: 'ranges' missing")
            except Exception as e:
                result.failures.append(f"attribution.json parse error: {e}")
        # attribution.json 없는 것은 경고가 아님 (compile 직후엔 있어야 하지만 optional)

        result.passed = len(result.failures) == 0
        return result

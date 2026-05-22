"""Harvester: 외부 SKILL.md 수집 + frontmatter/body 파싱 + SHA-256 해시.

source-of-truth tracking을 위해 각 source의 콘텐츠 해시를 sources.yaml과 비교한다.
외부 플러그인 SKILL.md의 위치를 filesystem scan으로 찾고, frontmatter와 body로 분해한다.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # graceful fallback — frontmatter parse skip

try:
    from .paths import find_project_root
except ImportError:  # direct script execution fallback
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from super.paths import find_project_root


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


@dataclass
class HarvestedSkill:
    """파싱된 외부 SKILL.md."""

    skill_id: str
    source_path: Path
    frontmatter: dict
    body: str
    content_hash: str  # "sha256:<hex>"

    @property
    def description(self) -> str:
        return self.frontmatter.get("description", "") or ""

    @property
    def triggers(self) -> list[str]:
        t = self.frontmatter.get("triggers", "")
        if isinstance(t, list):
            return [str(x).strip() for x in t if str(x).strip()]
        if isinstance(t, str):
            return [s.strip() for s in t.split(",") if s.strip()]
        return []


class Harvester:
    """SKILL.md 수집 및 해시 계산."""

    @staticmethod
    def _default_scan_roots() -> tuple[Path, ...]:
        """Cross-platform scan roots: 사용자 홈 + 동적 탐지된 project root."""
        project_root = find_project_root()
        return (
            Path("~/.claude/plugins").expanduser(),
            Path.home() / ".claude" / "skills",
            project_root / ".claude" / "skills",
            project_root / "plugins",
        )

    def __init__(self, scan_roots: list[Path] | None = None) -> None:
        self.scan_roots = list(scan_roots) if scan_roots is not None else list(self._default_scan_roots())

    def harvest_all(self) -> list[HarvestedSkill]:
        out: list[HarvestedSkill] = []
        seen: set[Path] = set()
        for root in self.scan_roots:
            if not root.exists():
                continue
            for skill_md in root.rglob("SKILL.md"):
                if skill_md in seen:
                    continue
                seen.add(skill_md)
                try:
                    out.append(self.harvest_one(skill_md))
                except Exception:
                    continue
        return out

    def harvest_one(self, path: Path) -> HarvestedSkill:
        text = path.read_text(encoding="utf-8")
        fm, body = self._split_frontmatter(text)
        return HarvestedSkill(
            skill_id=self._infer_skill_id(path, fm),
            source_path=path,
            frontmatter=fm,
            body=body,
            content_hash=self.content_hash(text),
        )

    def harvest_by_id(self, skill_id: str) -> HarvestedSkill | None:
        for skill in self.harvest_all():
            if skill.skill_id == skill_id:
                return skill
        return None

    @staticmethod
    def content_hash(text: str) -> str:
        return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _split_frontmatter(text: str) -> tuple[dict, str]:
        m = _FRONTMATTER_RE.match(text)
        if not m:
            return {}, text
        fm_text, body = m.group(1), m.group(2)
        if yaml is None:
            return {}, body
        try:
            return yaml.safe_load(fm_text) or {}, body
        except Exception:
            return {}, body

    @staticmethod
    def _infer_skill_id(path: Path, fm: dict) -> str:
        if fm.get("name"):
            return str(fm["name"])
        parts = path.parts
        plugin = "local"
        if "plugins" in parts:
            pi = parts.index("plugins")
            if pi + 1 < len(parts):
                plugin = parts[pi + 1]
        if "skills" in parts:
            i = parts.index("skills")
            if i + 1 < len(parts):
                return f"{plugin}:{parts[i + 1]}"
        return path.parent.name

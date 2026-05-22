"""Compiler: winner backbone + losers absorber sections → 단일 super SKILL.md.

흐름:
  1. sources/<cat>.yaml 로드 (winner backbone + losers absorber + absorb 룰)
  2. winner SKILL.md를 backbone으로 채택
  3. 각 loser에서 absorb 룰에 따라 섹션 추출
  4. backbone에 attribution 주석으로 wrap하여 삽입
  5. frontmatter 통합 (description + triggers union)
  6. attribution_map.json 생성
  7. sources/<cat>.yaml의 version_hash·last_seen 갱신

외부 SKILL.md는 절대 수정하지 않는다. 모든 메타데이터는 sources/<cat>.yaml에만 기록.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

from .absorb_marker_parser import AbsorbMarkerParser
from .attribution_tracker import AttributionTracker
from .harvester import HarvestedSkill, Harvester


ABSORB_START = "<!-- aiden-auto:absorb start | src={src}@{hash} | role={role} -->"
ABSORB_END = "<!-- aiden-auto:absorb end -->"


@dataclass
class CompileResult:
    super_skill_md: str
    attribution_path: Path
    sources_yaml_updated: dict
    backbone_id: str
    absorber_ids: list[str]


class Compiler:
    def __init__(
        self,
        *,
        plugin_root: Path,
        harvester: Harvester | None = None,
        marker_parser: AbsorbMarkerParser | None = None,
    ) -> None:
        self.plugin_root = plugin_root
        self.harvester = harvester or Harvester()
        self.marker_parser = marker_parser or AbsorbMarkerParser()

    def compile(self, category: str) -> CompileResult:
        if yaml is None:
            raise RuntimeError("PyYAML is required for compile()")

        sources_yaml_path = self.plugin_root / "sources" / f"{category}.yaml"
        if not sources_yaml_path.exists():
            raise FileNotFoundError(f"sources/{category}.yaml not found")

        cfg = yaml.safe_load(sources_yaml_path.read_text(encoding="utf-8")) or {}
        sources = cfg.get("sources", [])

        backbone_cfg = next((s for s in sources if s.get("role") == "backbone"), None)
        if backbone_cfg is None:
            raise ValueError(f"no backbone source in sources/{category}.yaml")
        absorber_cfgs = [s for s in sources if s.get("role") in ("absorber", "complement")]

        backbone_skill = self._resolve_skill(backbone_cfg)
        absorbers: list[tuple[HarvestedSkill, dict]] = []
        for c in absorber_cfgs:
            try:
                absorbers.append((self._resolve_skill(c), c))
            except FileNotFoundError:
                # absorber가 미설치면 skip — 나머지로 컴파일 (forward-compatible)
                continue

        super_md, attribution = self._merge(category, backbone_skill, absorbers)

        attribution_path = self.plugin_root / "attribution" / f"{category}.attribution.json"
        attribution.write(
            attribution_path,
            category=category,
            super_path=f"skills/super_{category}/SKILL.md",
        )

        cfg = self._update_hashes(
            cfg,
            backbone_skill,
            [s for s, _ in absorbers],
        )

        return CompileResult(
            super_skill_md=super_md,
            attribution_path=attribution_path,
            sources_yaml_updated=cfg,
            backbone_id=backbone_cfg["id"],
            absorber_ids=[c["id"] for _, c in absorbers],
        )

    def write_super(self, category: str, result: CompileResult) -> Path:
        # super skill은 v1과 분리된 디렉터리(`skills/super_<cat>/`)에 출력 — v1 보존 원칙
        out = self.plugin_root / "skills" / f"super_{category}" / "SKILL.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(result.super_skill_md, encoding="utf-8")

        if yaml is not None:
            sources_path = self.plugin_root / "sources" / f"{category}.yaml"
            sources_path.write_text(
                yaml.safe_dump(
                    result.sources_yaml_updated,
                    sort_keys=False,
                    allow_unicode=True,
                    default_flow_style=False,
                ),
                encoding="utf-8",
            )
        return out

    # ---- internals ----

    def _resolve_skill(self, src_cfg: dict) -> HarvestedSkill:
        # yaml의 id가 source-of-truth — harvester의 path-inference id를 덮어쓴다.
        path = src_cfg.get("plugin_path")
        if path:
            p = Path(str(path)).expanduser()
            if p.exists():
                h = self.harvester.harvest_one(p)
                h.skill_id = src_cfg["id"]
                return h
        h = self.harvester.harvest_by_id(src_cfg["id"])
        if h is not None:
            h.skill_id = src_cfg["id"]
            return h
        raise FileNotFoundError(f"source skill not found: {src_cfg['id']}")

    def _merge(
        self,
        category: str,
        backbone: HarvestedSkill,
        absorbers: list[tuple[HarvestedSkill, dict]],
    ) -> tuple[str, AttributionTracker]:
        attribution = AttributionTracker()

        all_descriptions: list[str] = []
        if backbone.description:
            all_descriptions.append(backbone.description)
        for a, _ in absorbers:
            if a.description:
                all_descriptions.append(a.description)

        all_triggers = sorted(
            {t for t in backbone.triggers}
            | {t for a, _ in absorbers for t in a.triggers}
        )

        fm_lines = [
            "---",
            f"name: aiden-auto:{category}",
            "description: " + " | ".join(all_descriptions)[:280],
            "triggers: " + ", ".join(all_triggers),
            "super_skill: true",
            f"sources_ref: sources/{category}.yaml",
            "---",
            "",
        ]

        body_chunks: list[str] = []
        cursor = len(fm_lines)

        # backbone full body
        backbone_block = self._wrap_attribution(backbone.body, backbone, role="backbone")
        body_chunks.append(backbone_block)
        bb_lines = backbone_block.count("\n") + 1
        attribution.add(
            line_start=cursor,
            line_end=cursor + bb_lines,
            source_id=f"{backbone.skill_id}@{backbone.content_hash}",
            role="backbone",
        )
        cursor += bb_lines + 1
        body_chunks.append("")

        # absorber sections
        for absorber_skill, absorber_cfg in absorbers:
            sections = self.marker_parser.extract_by_rules(
                absorber_skill.body, absorber_cfg.get("absorb", [])
            )
            role = absorber_cfg.get("role", "absorber")
            for section in sections:
                wrapped = self._wrap_attribution(section.body, absorber_skill, role=role)
                body_chunks.append(wrapped)
                wlines = wrapped.count("\n") + 1
                attribution.add(
                    line_start=cursor,
                    line_end=cursor + wlines,
                    source_id=f"{absorber_skill.skill_id}@{absorber_skill.content_hash}",
                    role=role,
                )
                cursor += wlines + 1
                body_chunks.append("")

        super_md = "\n".join(fm_lines) + "\n".join(body_chunks)
        return super_md, attribution

    @staticmethod
    def _wrap_attribution(content: str, skill: HarvestedSkill, *, role: str) -> str:
        return (
            ABSORB_START.format(src=skill.skill_id, hash=skill.content_hash, role=role)
            + "\n"
            + content.strip()
            + "\n"
            + ABSORB_END
        )

    @staticmethod
    def _update_hashes(
        cfg: dict,
        backbone: HarvestedSkill,
        absorbers: list[HarvestedSkill],
    ) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        skill_by_id = {backbone.skill_id: backbone}
        for a in absorbers:
            skill_by_id[a.skill_id] = a
        for src in cfg.get("sources", []):
            sid = src.get("id")
            if sid in skill_by_id:
                src["version_hash"] = skill_by_id[sid].content_hash
                src["last_seen"] = now
        cfg["last_compiled"] = now
        cfg["drift_status"] = "clean"
        return cfg

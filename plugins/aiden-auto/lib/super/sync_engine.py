"""Sync Engine: source drift 감지 + tier 분류 + LOW 자동 적용.

사용 시점:
  - SessionStart hook이 detect_drift_all()로 가벼운 변경 감지
  - /audit super-sync가 본격 sync 실행 (apply_low/queue_medium/queue_high)
  - daily cron (evolution_scheduler) 가 apply_low()로 자동 머지
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

from .compiler import Compiler
from .harvester import Harvester
from .tier_classifier import Tier, TierClassifier


@dataclass
class DriftEntry:
    source_id: str
    role: str
    before_hash: str
    after_hash: str
    tier: Tier


@dataclass
class DriftReport:
    category: str
    drifted_sources: list[DriftEntry] = field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        return bool(self.drifted_sources)

    @property
    def highest_tier(self) -> Tier | None:
        if not self.drifted_sources:
            return None
        order = {Tier.LOW: 0, Tier.MEDIUM: 1, Tier.HIGH: 2}
        return max(self.drifted_sources, key=lambda d: order[d.tier]).tier


class SyncEngine:
    def __init__(
        self,
        *,
        plugin_root: Path,
        harvester: Harvester | None = None,
        compiler: Compiler | None = None,
        classifier: TierClassifier | None = None,
    ) -> None:
        self.plugin_root = plugin_root
        self.harvester = harvester or Harvester()
        self.compiler = compiler or Compiler(plugin_root=plugin_root, harvester=self.harvester)
        self.classifier = classifier or TierClassifier()

    def detect_drift(self, category: str) -> DriftReport:
        cfg_path = self.plugin_root / "sources" / f"{category}.yaml"
        report = DriftReport(category=category)
        if not cfg_path.exists() or yaml is None:
            return report

        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        for src in cfg.get("sources", []):
            current = self._current_hash_and_body(src)
            if current is None:
                continue
            current_hash, current_body = current
            recorded_hash = src.get("version_hash")
            if not recorded_hash:
                # uncompiled — drift가 아님 (initial compile은 /evolve --bootstrap 또는 /audit super-sync 명시 호출)
                continue
            if current_hash != recorded_hash:
                tier, _ = self.classifier.classify("", current_body)
                report.drifted_sources.append(DriftEntry(
                    source_id=src["id"],
                    role=src.get("role", "absorber"),
                    before_hash=recorded_hash,
                    after_hash=current_hash,
                    tier=tier,
                ))
        return report

    def detect_uncompiled(self) -> list[str]:
        """version_hash가 비어있는 카테고리(미컴파일) 목록.

        drift와 구분: 미컴파일은 사용자가 명시적으로 bootstrap해야 함.
        """
        out: list[str] = []
        if yaml is None:
            return out
        sources_dir = self.plugin_root / "sources"
        if not sources_dir.exists():
            return out
        for cfg_path in sources_dir.glob("*.yaml"):
            if cfg_path.name == "catalog.yaml":
                continue
            try:
                cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            except Exception:
                continue
            sources = cfg.get("sources", [])
            if any(not s.get("version_hash") for s in sources):
                out.append(cfg_path.stem)
        return out

    def detect_drift_all(self) -> list[DriftReport]:
        out: list[DriftReport] = []
        sources_dir = self.plugin_root / "sources"
        if not sources_dir.exists():
            return out
        for cfg in sources_dir.glob("*.yaml"):
            if cfg.name == "catalog.yaml":
                continue
            out.append(self.detect_drift(cfg.stem))
        return out

    def apply_low(self, category: str) -> bool:
        """LOW tier만 자동 적용. drift가 없거나 더 높은 tier가 있으면 False."""
        report = self.detect_drift(category)
        if not report.has_drift:
            return False
        if report.highest_tier != Tier.LOW:
            return False
        result = self.compiler.compile(category)
        self.compiler.write_super(category, result)
        return True

    # ---- internals ----

    def _current_hash_and_body(self, src: dict) -> tuple[str, str] | None:
        path = src.get("plugin_path")
        if path:
            p = Path(str(path)).expanduser()
            if p.exists():
                text = p.read_text(encoding="utf-8")
                return self.harvester.content_hash(text), text
        h = self.harvester.harvest_by_id(src["id"])
        if h is None:
            return None
        text = h.source_path.read_text(encoding="utf-8")
        return h.content_hash, text

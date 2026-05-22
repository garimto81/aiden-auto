"""Checkpoint Manager: super SKILL.md 백업 + rollback + 만료.

LOW 자동 적용 직전 백업 → 실패 시 즉시 rollback.
30일 경과 백업은 자동 만료.
"""
from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass
class Checkpoint:
    category: str
    timestamp: str  # ISO 8601
    path: Path


class CheckpointManager:
    EXPIRY_DAYS = 30

    def __init__(self, plugin_root: Path) -> None:
        self.plugin_root = plugin_root
        self.checkpoint_dir = plugin_root / "checkpoints"

    def create(self, category: str) -> Checkpoint | None:
        """super SKILL.md → checkpoints/<cat>-<timestamp>.md 복사."""
        src = self.plugin_root / "skills" / f"super_{category}" / "SKILL.md"
        if not src.exists():
            return None
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        dst = self.checkpoint_dir / f"{category}-{ts}.md"
        shutil.copy2(src, dst)
        return Checkpoint(category=category, timestamp=ts, path=dst)

    def list(self, category: str | None = None) -> list[Checkpoint]:
        """전체 또는 특정 카테고리의 체크포인트 목록 (시간 역순)."""
        if not self.checkpoint_dir.exists():
            return []
        out: list[Checkpoint] = []
        for p in sorted(self.checkpoint_dir.glob("*.md"), reverse=True):
            stem = p.stem
            if "-" not in stem:
                continue
            cat, ts = stem.rsplit("-", 1)
            if category is not None and cat != category:
                continue
            out.append(Checkpoint(category=cat, timestamp=ts, path=p))
        return out

    def restore(self, category: str, timestamp: str | None = None) -> bool:
        """timestamp 미지정 시 가장 최근 체크포인트 복원."""
        candidates = self.list(category=category)
        if not candidates:
            return False
        if timestamp:
            target = next((c for c in candidates if c.timestamp.startswith(timestamp)), None)
        else:
            target = candidates[0]  # 가장 최근
        if target is None:
            return False
        dst = self.plugin_root / "skills" / f"super_{category}" / "SKILL.md"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target.path, dst)
        return True

    def expire_old(self) -> int:
        """EXPIRY_DAYS 경과 백업 삭제. 삭제된 개수 반환."""
        if not self.checkpoint_dir.exists():
            return 0
        cutoff = time.time() - self.EXPIRY_DAYS * 86400
        removed = 0
        for p in self.checkpoint_dir.glob("*.md"):
            if p.stat().st_mtime < cutoff:
                p.unlink()
                removed += 1
        return removed

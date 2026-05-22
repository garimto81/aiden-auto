"""Plugin marketplace probe: 외부 플러그인 최신 버전 탐지.

`claude plugin marketplace list` + git ls-remote 두 가지 방식 지원.
caching 디렉터리(`~/.claude/plugins/cache/`)의 SKILL.md 해시를 직접 비교하는 것이
가장 신뢰할 만한 방식이므로 1차 구현은 디스크 기반.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class PluginVersion:
    plugin_name: str
    cache_path: Path
    version: str  # 디렉터리 이름 또는 'unknown'


class PluginMarketplaceProbe:
    """plugin cache 디렉터리에서 최신 버전 발견."""

    DEFAULT_CACHE_ROOTS = (
        Path("~/.claude/plugins/cache").expanduser(),
    )

    def __init__(self, cache_roots: list[Path] | None = None) -> None:
        self.cache_roots = list(cache_roots) if cache_roots is not None else list(self.DEFAULT_CACHE_ROOTS)

    def list_installed_plugins(self) -> list[PluginVersion]:
        """캐시된 플러그인 + 최신 버전 목록."""
        out: list[PluginVersion] = []
        for cache in self.cache_roots:
            if not cache.exists():
                continue
            # 구조: cache/<marketplace>/<plugin>/<version>/...
            for marketplace in cache.iterdir():
                if not marketplace.is_dir():
                    continue
                for plugin in marketplace.iterdir():
                    if not plugin.is_dir():
                        continue
                    versions = sorted(
                        [v for v in plugin.iterdir() if v.is_dir()],
                        key=self._version_sort_key,
                    )
                    if not versions:
                        continue
                    latest = versions[-1]
                    out.append(PluginVersion(
                        plugin_name=plugin.name,
                        cache_path=latest,
                        version=latest.name,
                    ))
        return out

    def find_latest(self, plugin_name: str) -> PluginVersion | None:
        for pv in self.list_installed_plugins():
            if pv.plugin_name == plugin_name:
                return pv
        return None

    @staticmethod
    def _version_sort_key(path: Path):
        """semver 또는 'unknown' 정렬 — semver는 tuple, 그 외는 문자열."""
        name = path.name
        parts = name.split(".")
        try:
            return (1, tuple(int(p) for p in parts))
        except ValueError:
            return (0, name)

    def query_marketplace_cli(self) -> str | None:
        """선택적: claude plugin marketplace list CLI 호출.

        claude CLI가 PATH에 없거나 응답 시간이 길면 None 반환.
        """
        try:
            r = subprocess.run(
                ["claude", "plugin", "marketplace", "list"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return r.stdout if r.returncode == 0 else None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

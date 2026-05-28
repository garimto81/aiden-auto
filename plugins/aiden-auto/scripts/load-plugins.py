#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plugin Loader - Progressive Disclosure Pattern
Based on wshobson/agents plugin architecture (MIT License)

토큰 최적화: Phase/키워드 기반 선택적 플러그인 로딩
"""

import json
import sys
import io
from pathlib import Path
from typing import List, Dict, Optional

# Windows 인코딩 처리
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


class PluginLoader:
    """Claude Code 플러그인 로더"""

    def __init__(self, manifest_path: str = ".claude/plugins/plugin-manifest.json"):
        """플러그인 manifest 로드"""
        self.manifest_path = Path(manifest_path)

        if not self.manifest_path.exists():
            raise FileNotFoundError(f"플러그인 manifest 없음: {manifest_path}")

        with open(self.manifest_path, "r", encoding="utf-8") as f:
            self.manifest = json.load(f)

        self.plugins = self.manifest["plugins"]

    def load_active_plugins(
        self,
        phase: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        priority_filter: Optional[str] = None,
    ) -> List[Dict]:
        """
        현재 Phase/키워드에 맞는 플러그인만 로드

        Args:
            phase: 현재 Phase (예: "Phase 0", "Phase 1")
            keywords: 검색 키워드 리스트
            priority_filter: 우선순위 필터 ("high", "medium", "low")

        Returns:
            활성화된 플러그인 목록 (우선순위 정렬)
        """
        active = []

        for plugin in self.plugins:
            # Phase 매칭
            if phase and phase in plugin["activation_triggers"]:
                active.append(plugin)
                continue

            # 키워드 매칭
            if keywords:
                for kw in keywords:
                    kw_lower = kw.lower()
                    # activation_triggers에서 키워드 검색
                    if any(
                        kw_lower in trigger.lower()
                        for trigger in plugin["activation_triggers"]
                    ):
                        active.append(plugin)
                        break

        # 중복 제거
        unique_plugins = {p["id"]: p for p in active}.values()
        active = list(unique_plugins)

        # 우선순위 필터
        if priority_filter:
            active = [p for p in active if p["priority"] == priority_filter]

        # 우선순위 정렬 (high → medium → low)
        priority_order = {"high": 0, "medium": 1, "low": 2}
        active.sort(key=lambda p: priority_order.get(p["priority"], 999))

        return active

    def load_plugin_instructions(self, plugin_id: str, level: str = "metadata") -> str:
        """
        플러그인 Instructions 로드 (Progressive Disclosure)

        Args:
            plugin_id: 플러그인 ID
            level: 로딩 레벨 ("metadata", "instructions", "resources")

        Returns:
            Instructions 내용
        """
        plugin = next((p for p in self.plugins if p["id"] == plugin_id), None)

        if not plugin:
            raise ValueError(f"플러그인 없음: {plugin_id}")

        plugin_path = Path(plugin["path"])
        instructions_file = plugin_path / "instructions.md"

        if not instructions_file.exists():
            return f"# {plugin['name']}\n\n{plugin['description']}"

        with open(instructions_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Progressive Disclosure
        if level == "metadata":
            # Metadata만 반환 (details 태그 이전까지)
            return content.split("<details>")[0]
        elif level == "instructions":
            # Metadata + Instructions 반환 (첫 번째 details 포함)
            parts = content.split("</details>")
            if len(parts) >= 1:
                return parts[0] + "</details>"
            return content
        elif level == "resources":
            # 전체 반환
            return content

        return content

    def print_active_summary(self, active_plugins: List[Dict]):
        """활성화된 플러그인 요약 출력"""
        if not active_plugins:
            print("⚠️  활성화된 플러그인 없음")
            return

        print(f"\n🔌 활성화된 플러그인: {len(active_plugins)}개\n")

        total_tokens = 0

        for plugin in active_plugins:
            priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                plugin["priority"], "⚪"
            )

            model_emoji = {"sonnet": "🧠", "haiku": "⚡"}.get(plugin["model"], "🤖")

            print(f"{priority_emoji} {model_emoji} {plugin['name']}")
            print(f"   ├─ 모델: {plugin['model']} ({plugin['token_cost']} tokens)")
            print(f"   ├─ 활성화: {', '.join(plugin['activation_triggers'][:3])}")
            print(f"   └─ 기능: {', '.join(plugin['capabilities'][:2])}\n")

            total_tokens += plugin["token_cost"]

        # 토큰 절감 효과 (전체 플러그인 비용 계산)
        baseline = sum(p["token_cost"] for p in self.plugins)
        savings = ((baseline - total_tokens) / baseline) * 100 if baseline > 0 else 0

        print(f"📊 토큰 사용: {total_tokens} / {baseline} (절감: {savings:.1f}%)")


def main():
    """CLI 인터페이스"""
    import argparse

    parser = argparse.ArgumentParser(description="Claude Code 플러그인 로더")
    parser.add_argument("--phase", help='Phase 번호 (예: "Phase 0")')
    parser.add_argument("--keywords", nargs="+", help="키워드 리스트")
    parser.add_argument(
        "--priority", choices=["high", "medium", "low"], help="우선순위 필터"
    )
    parser.add_argument(
        "--show-instructions", metavar="PLUGIN_ID", help="플러그인 Instructions 표시"
    )
    parser.add_argument(
        "--level",
        choices=["metadata", "instructions", "resources"],
        default="metadata",
        help="Progressive disclosure level",
    )

    args = parser.parse_args()

    try:
        loader = PluginLoader()

        if args.show_instructions:
            # 특정 플러그인 instructions 표시
            instructions = loader.load_plugin_instructions(
                args.show_instructions, args.level
            )
            print(instructions)
        else:
            # 활성 플러그인 표시
            active = loader.load_active_plugins(
                phase=args.phase, keywords=args.keywords, priority_filter=args.priority
            )

            loader.print_active_summary(active)

            # JSON 출력 (다른 스크립트에서 사용 가능)
            if active:
                print("\n📋 JSON Output:")
                print(json.dumps([p["id"] for p in active], indent=2))

    except Exception as e:
        print(f"❌ 오류: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

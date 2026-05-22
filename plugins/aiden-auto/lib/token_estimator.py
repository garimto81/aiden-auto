#!/usr/bin/env python3
"""Token cost estimator for `.claude/` configuration.

`.claude/`의 매 세션 inject되는 markdown·json의 토큰 비용을 추정한다.
3 chars/token 휴리스틱(영문·한글 혼합 평균치 기준).

CLI:
  python -m token_estimator
  python token_estimator.py [--baseline=30000] [--json]

/audit Phase 1.6에서 import:
  from token_estimator import estimate_session_baseline, format_report
  print(format_report(estimate_session_baseline()))
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


CHARS_PER_TOKEN = 3.0  # 영문·한글 혼합 평균 (보수적)


# 토큰 임계
THRESHOLD_GOOD = 30_000
THRESHOLD_CAUTION = 60_000


@dataclass
class FileMeasurement:
    path: str
    size_bytes: int
    line_count: int
    tokens_estimated: int


@dataclass
class TokenReport:
    files: list[FileMeasurement] = field(default_factory=list)
    total_tokens: int = 0
    by_category: dict = field(default_factory=dict)
    status: str = ""  # good | caution | action_needed
    threshold_good: int = THRESHOLD_GOOD
    threshold_caution: int = THRESHOLD_CAUTION


def _measure(path: Path) -> FileMeasurement | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None
    size = len(text.encode("utf-8"))
    lines = text.count("\n") + 1
    tokens = int(size / CHARS_PER_TOKEN)
    return FileMeasurement(
        path=str(path),
        size_bytes=size,
        line_count=lines,
        tokens_estimated=tokens,
    )


def _scan_dir(dir_path: Path, glob: str = "*.md") -> list[FileMeasurement]:
    out: list[FileMeasurement] = []
    if not dir_path.exists():
        return out
    for f in sorted(dir_path.glob(glob)):
        m = _measure(f)
        if m is not None:
            out.append(m)
    return out


def estimate_session_baseline(project_root: Path | None = None) -> TokenReport:
    """매 세션 자동 inject되는 markdown·json 토큰 합계 추정."""
    project = project_root or Path("C:/Claude")
    user_home = Path.home()

    report = TokenReport()
    categories: dict[str, list[FileMeasurement]] = {
        "claude_md_project": [],
        "claude_md_user": [],
        "rules": [],
        "references": [],
        "settings": [],
    }

    # CLAUDE.md (project)
    m = _measure(project / "CLAUDE.md")
    if m:
        categories["claude_md_project"].append(m)

    # CLAUDE.md (user global)
    m = _measure(user_home / ".claude" / "CLAUDE.md")
    if m:
        categories["claude_md_user"].append(m)

    # rules/ (excluding _archived/)
    rules_dir = project / ".claude" / "rules"
    if rules_dir.exists():
        for f in sorted(rules_dir.glob("*.md")):
            if f.name.startswith("000-"):  # CHANGELOG
                continue
            m = _measure(f)
            if m:
                categories["rules"].append(m)

    # references/ (excluding _archived/)
    refs_dir = project / ".claude" / "references"
    if refs_dir.exists():
        for f in sorted(refs_dir.glob("*.md")):
            m = _measure(f)
            if m:
                categories["references"].append(m)

    # settings.json + settings.local.json
    for name in ("settings.json", "settings.local.json"):
        m = _measure(project / ".claude" / name)
        if m:
            categories["settings"].append(m)

    # 총합 + 카테고리별
    for cat, files in categories.items():
        cat_total = sum(f.tokens_estimated for f in files)
        report.by_category[cat] = {
            "file_count": len(files),
            "tokens": cat_total,
        }
        report.files.extend(files)
        report.total_tokens += cat_total

    # 상태 판정
    if report.total_tokens < THRESHOLD_GOOD:
        report.status = "good"
    elif report.total_tokens < THRESHOLD_CAUTION:
        report.status = "caution"
    else:
        report.status = "action_needed"

    return report


def format_report(report: TokenReport) -> str:
    lines: list[str] = []
    status_emoji = {"good": "🟢", "caution": "🟡", "action_needed": "🔴"}.get(report.status, "")
    lines.append(f"## Token Baseline {status_emoji}")
    lines.append("")
    lines.append(f"- 총 추정: **{report.total_tokens:,} tokens**")
    lines.append(f"- 상태: **{report.status}** (good <{report.threshold_good:,} / caution <{report.threshold_caution:,} / action_needed ≥{report.threshold_caution:,})")
    lines.append("")
    lines.append("### 카테고리별")
    lines.append("")
    lines.append("| 카테고리 | 파일 수 | 추정 토큰 |")
    lines.append("|---------|--------:|----------:|")
    for cat, info in report.by_category.items():
        lines.append(f"| {cat} | {info['file_count']} | {info['tokens']:,} |")
    lines.append("")
    if report.status == "action_needed":
        lines.append("### 권장 조치 (action_needed)")
        lines.append("")
        lines.append("- references/ SoT 단일화 검토 (외부 플러그인이 권위인 항목 archive)")
        lines.append("- rules/ 11번(가장 큼) sub-rule 분할 또는 references로 일부 이전")
        lines.append("- 매 세션 inject되지 않아도 되는 file은 on-demand load로 전환")
    elif report.status == "caution":
        lines.append("### 권장 조치 (caution)")
        lines.append("")
        lines.append("- 새 룰·참조 추가 전 기존 정리 검토")
        lines.append("- 카테고리별 토큰 분포 확인")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=".claude/ token baseline estimator")
    parser.add_argument("--json", action="store_true", help="JSON 출력")
    parser.add_argument("--baseline", type=int, default=None, help="비교 baseline 토큰 (drift 알림)")
    args = parser.parse_args(argv)

    report = estimate_session_baseline()

    if args.json:
        out = {
            "total_tokens": report.total_tokens,
            "status": report.status,
            "by_category": report.by_category,
            "files": [asdict(f) for f in report.files],
            "thresholds": {"good": report.threshold_good, "caution": report.threshold_caution},
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(format_report(report))

    if args.baseline is not None:
        diff = report.total_tokens - args.baseline
        sign = "+" if diff >= 0 else ""
        pct = (diff / args.baseline * 100) if args.baseline else 0.0
        print()
        print(f"baseline diff: {sign}{diff:,} tokens ({sign}{pct:.1f}%)")

    return 0


if __name__ == "__main__":
    sys.exit(main())

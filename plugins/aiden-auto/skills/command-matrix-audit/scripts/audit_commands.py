#!/usr/bin/env python3
"""command .md 파일 전수 무결성 감사.

목적:
- 3 경로(local / global / plugin)의 command .md 파일을 전수 수집
- redirect stub 탐지 (본문이 Skill 호출/redirect/deprecated 만 포함)
- broken redirect 탐지 (redirect 대상 skill 파일 없음)
- empty command 탐지 (5줄 미만)
- duplicate name 탐지 (동일 이름 여러 위치)

출력: 표 + JSON. JSON 경로: C:/claude/.claude/state/command-matrix-mapping.json

설계 원칙:
- read-only (파일 수정 없음, 권고만)
- 10 초 이내
- exit code: 0 (정상) / 1 (BROKEN_REDIRECT 발견)
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# 공유 helper import (stub-aware classification)
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "_shared"))
try:
    from audit_helpers import (
        BENIGN_INTENTS,
        classify_duplicate_intent,
        is_in_shadow_marketplace,
        parse_frontmatter_simple,
        read_text_safe,
    )
    _HAS_HELPERS = True
except ImportError:
    _HAS_HELPERS = False
    # fallback BENIGN_INTENTS — helper와 반드시 동기화
    # A-8 (2026-05-18 audit-loop critic DI-1): plugin_multi_version_cache + external_plugin_internal_drift 추가
    BENIGN_INTENTS = frozenset({
        "shadow_marketplace", "byte_identical_mirror", "redirect_stub",
        "project_global_mirror", "plugin_namespaced",
        "priority_resolution_local_wins", "priority_resolution_global_wins",
        "localization_override",
        "plugin_multi_version_cache", "external_plugin_internal_drift",
    })

# ── 경로 상수 ─────────────────────────────────────────────────────────────────
PROJECT_COMMANDS_DIR = Path("C:/claude/.claude/commands")
GLOBAL_COMMANDS_DIR  = Path.home() / ".claude" / "commands"
# Rule 19 v2.0 정합화 (2026-05-18 audit-loop): marketplaces + cache 양쪽 스캔
PLUGIN_MARKETPLACE_ROOT = Path.home() / ".claude" / "plugins" / "marketplaces"
PLUGIN_CACHE_ROOT       = Path.home() / ".claude" / "plugins" / "cache"
PLUGIN_SCAN_ROOTS       = [PLUGIN_MARKETPLACE_ROOT, PLUGIN_CACHE_ROOT]

PROJECT_SKILLS_DIR   = Path("C:/claude/.claude/skills")
GLOBAL_SKILLS_DIR    = Path.home() / ".claude" / "skills"

OUTPUT_PATH = Path("C:/claude/.claude/state/command-matrix-mapping.json")

# redirect stub 탐지 패턴 (본문 전체에서 매칭)
REDIRECT_PATTERNS = [
    re.compile(r"Skill\s*\(", re.IGNORECASE),
    re.compile(r"\bredirect\b", re.IGNORECASE),
    re.compile(r"\bdeprecated\b", re.IGNORECASE),
    re.compile(r"이 커맨드는.+(스킬|skill)", re.IGNORECASE),
    re.compile(r"Use\s+/auto", re.IGNORECASE),
    re.compile(r"→\s+`/", ),
]

# A-23 (Cycle 20 critic): deprecated 단어 경계 + 부정어 회피 정규식 — 모듈 레벨 hoisting
# 매 analyze_command() 호출마다 재컴파일 방지 (~63 cmd × 매 cycle)
_DEPRECATED_RE = re.compile(r"\bdeprecated\b", re.IGNORECASE)
_NEG_RE = re.compile(r"\b(not|never|no\s+longer|isn'?t|wasn'?t|aren'?t)\b", re.IGNORECASE)

# redirect 에서 skill 이름 추출 패턴
SKILL_NAME_PATTERNS = [
    re.compile(r'Skill\s*\(\s*["\']([^"\']+)["\']', re.IGNORECASE),
    re.compile(r'→\s+`/([^`]+)`'),
    re.compile(r'redirect[^\n]*?["\']([a-z0-9_-]+)["\']', re.IGNORECASE),
    re.compile(r'Use\s+/(\S+)', re.IGNORECASE),
    re.compile(r'/([a-z0-9_-]+)\s+skill', re.IGNORECASE),
]


# ── frontmatter 추출 ──────────────────────────────────────────────────────────
def parse_frontmatter(text: str) -> tuple[dict, str]:
    """YAML frontmatter 파싱 — helper의 parse_frontmatter_simple 사용 (DRY).

    helper는 YAML block scalar(>, |)도 정확히 파싱. fallback은 안전 default.
    """
    if _HAS_HELPERS:
        return parse_frontmatter_simple(text)
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    return {}, text[end + 4:].strip()


# ── redirect stub 감지 ────────────────────────────────────────────────────────
def is_redirect_stub(body: str) -> tuple[bool, str | None]:
    """본문이 redirect stub 인지 판단. (is_stub, skill_name_or_None) 반환."""
    # 유효 콘텐츠 줄 (주석·공백 제외)
    content_lines = [l for l in body.splitlines()
                     if l.strip() and not l.strip().startswith("#")]
    # 콘텐츠가 없거나 적고 redirect 패턴 포함
    has_redirect = any(p.search(body) for p in REDIRECT_PATTERNS)
    if not has_redirect:
        return False, None

    # 실질 내용이 10줄 미만 + redirect 패턴 → stub 으로 분류
    if len(content_lines) < 10:
        # skill 이름 추출
        skill_name: str | None = None
        for pat in SKILL_NAME_PATTERNS:
            m = pat.search(body)
            if m:
                skill_name = m.group(1).strip()
                break
        return True, skill_name

    return False, None


# ── skill 존재 확인 ───────────────────────────────────────────────────────────
def skill_exists(skill_name: str) -> bool:
    """skill 이름으로 project / global / plugin 에서 존재 여부 확인."""
    if not skill_name:
        return False
    # project local
    if (PROJECT_SKILLS_DIR / skill_name).is_dir():
        return True
    if (PROJECT_SKILLS_DIR / f"{skill_name}.md").is_file():
        return True
    # global user
    if (GLOBAL_SKILLS_DIR / skill_name).is_dir():
        return True
    if (GLOBAL_SKILLS_DIR / f"{skill_name}.md").is_file():
        return True
    # plugin (marketplaces + cache) — exact match
    for root in PLUGIN_SCAN_ROOTS:
        if not root.is_dir():
            continue
        for path in root.rglob(skill_name):
            if path.is_dir():
                return True
        for path in root.rglob(f"{skill_name}.md"):
            if path.is_file():
                return True
    return False


# ── command 수집 ──────────────────────────────────────────────────────────────
def collect_commands() -> list[tuple[str, Path]]:
    """(name, path) 리스트. 이름은 stem (확장자 제외)."""
    found: list[tuple[str, Path]] = []

    def scan_dir(d: Path) -> None:
        if not d.is_dir():
            return
        for p in d.glob("*.md"):
            found.append((p.stem, p))

    def scan_plugin() -> None:
        seen_resolved: set[Path] = set()
        for root in PLUGIN_SCAN_ROOTS:
            if not root.is_dir():
                continue
            for p in root.rglob("*.md"):
                if "commands" not in p.parts:
                    continue
                try:
                    resolved = p.resolve()
                except OSError:
                    resolved = p
                if resolved in seen_resolved:
                    continue
                seen_resolved.add(resolved)
                found.append((p.stem, p))

    scan_dir(PROJECT_COMMANDS_DIR)
    scan_dir(GLOBAL_COMMANDS_DIR)
    scan_plugin()
    return found


# ── 단일 command 분석 ─────────────────────────────────────────────────────────
def analyze_command(name: str, path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return {
            "name": name, "status": "EMPTY", "lines": 0,
            "redirect_target": None, "redirect_resolved": None,
            "paths": [path.as_posix()], "error": str(e),
        }

    fm, body = parse_frontmatter(text)
    total_lines = len(text.splitlines())

    if total_lines < 5:
        return {
            "name": name, "status": "EMPTY", "lines": total_lines,
            "frontmatter": fm, "redirect_target": None,
            "redirect_resolved": None, "paths": [str(path)],
        }

    is_stub, skill_name = is_redirect_stub(body)
    if is_stub:
        resolved = skill_exists(skill_name) if skill_name else False
        # A-6 (2026-05-18 audit-loop): deprecated marker 인식 — 외부 plugin 의 의도된 deprecation
        # frontmatter description 또는 본문에 "deprecated" 명시되면 BROKEN_REDIRECT 대신 REDIRECT_STUB
        # (사용자 작동 영향 0 — plugin 저자가 의도적으로 옛 entry 유지)
        # A-10 (2026-05-18 critic FN-2): substring 매칭 → 단어 경계 정규식 (NOT deprecated 오판 방지)
        # A-19 (Cycle 18 critic FP-1): 부정어 회피도 단어 경계 정규식으로 강화 — 줄바꿈/탭/문장 시작 모두 처리
        # A-23 (Cycle 20 critic): 정규식을 모듈 레벨 _DEPRECATED_RE / _NEG_RE 로 hoisting (매 호출 재컴파일 방지)
        is_deprecated = False
        fm_desc = (fm.get("description", "") if isinstance(fm, dict) else "")
        if _DEPRECATED_RE.search(fm_desc) or _DEPRECATED_RE.search(body):
            # "NOT deprecated" / "previously deprecated but restored" 등의 부정 표현 회피
            # body 에서 deprecated 매치 주변 30자 검사 — 부정어 정규식 매칭 시 제외
            text_to_check = fm_desc + " " + body
            for m in _DEPRECATED_RE.finditer(text_to_check):
                start = max(0, m.start() - 30)
                context = text_to_check[start:m.start()]
                if _NEG_RE.search(context):
                    continue
                is_deprecated = True
                break
        if is_deprecated:
            status = "REDIRECT_STUB"
        else:
            status = "REDIRECT_STUB" if resolved else "BROKEN_REDIRECT"
        return {
            "name": name, "status": status, "lines": total_lines,
            "frontmatter": fm, "redirect_target": skill_name,
            "redirect_resolved": resolved, "paths": [str(path)],
        }

    return {
        "name": name, "status": "OK", "lines": total_lines,
        "frontmatter": fm, "redirect_target": None,
        "redirect_resolved": None, "paths": [str(path)],
    }


# ── 중복 병합 ─────────────────────────────────────────────────────────────────
def merge_duplicates(records: list[dict]) -> list[dict]:
    """같은 이름의 레코드를 DUPLICATE 로 병합 + intent 분류."""
    by_name: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_name[r["name"]].append(r)

    merged: list[dict] = []
    for name, group in by_name.items():
        if len(group) == 1:
            merged.append(group[0])
        else:
            all_paths = [p for r in group for p in r["paths"]]

            # intent 분류 (stub-aware)
            intent = "unclassified"
            if _HAS_HELPERS:
                path_objs = [Path(p) for p in all_paths]
                bodies: list[str] = []
                fms: list[dict] = []
                for p in path_objs:
                    text = read_text_safe(p)
                    fm, body = parse_frontmatter_simple(text)
                    bodies.append(body)
                    fms.append(fm)
                intent = classify_duplicate_intent(path_objs, bodies, fms)

            merged.append({
                "name": name,
                "status": "DUPLICATE",
                "intent": intent,
                "lines": max(r["lines"] for r in group),
                "redirect_target": None,
                "redirect_resolved": None,
                "paths": all_paths,
            })
    return merged


# ── audit 메인 ────────────────────────────────────────────────────────────────
def audit() -> dict:
    raw_commands = collect_commands()
    raw_records = [analyze_command(name, path) for name, path in raw_commands]
    results = merge_duplicates(raw_records)

    summary = {"OK": 0, "REDIRECT_STUB": 0, "BROKEN_REDIRECT": 0,
               "EMPTY": 0, "DUPLICATE": 0}
    for r in results:
        summary[r["status"]] = summary.get(r["status"], 0) + 1

    # intent 별 분포 (DUPLICATE 내부 세분화)
    intent_summary: dict[str, int] = {}
    for r in results:
        if r["status"] == "DUPLICATE":
            intent = r.get("intent", "unclassified")
            intent_summary[intent] = intent_summary.get(intent, 0) + 1

    return {
        "ts": datetime.now().isoformat(),
        "commands_total": len(results),
        "raw_files": len(raw_commands),
        "summary": summary,
        "intent_summary": intent_summary,
        "results": sorted(results, key=lambda x: x["name"]),
    }


# ── 콘솔 출력 ─────────────────────────────────────────────────────────────────
def print_report(report: dict) -> None:
    print(f"\n=== Command Audit Report ({report['ts']}) ===\n")
    print(f"Commands found: {report['commands_total']}  "
          f"(raw files: {report['raw_files']})\n")

    print("Status distribution:")
    for status, count in report["summary"].items():
        if count > 0:
            print(f"  {status:20s}: {count:3d}")

    # intent 분포 출력 — 단일 BENIGN_INTENTS 사용
    intent_summary = report.get("intent_summary", {})
    if intent_summary:
        print("\nDUPLICATE intent breakdown:")
        for intent, count in sorted(intent_summary.items()):
            tag = "OK" if intent in BENIGN_INTENTS else "WARN"
            print(f"  [{tag:4s}] {intent:25s}: {count:3d}")

    issue_statuses = {"BROKEN_REDIRECT", "EMPTY", "DUPLICATE"}
    issues = [
        r for r in report["results"]
        if r["status"] in issue_statuses
        and not (r["status"] == "DUPLICATE" and r.get("intent") in BENIGN_INTENTS)
    ]

    if issues:
        print(f"\nReal issues (action needed): {len(issues)}\n")
        for r in issues:
            target_info = ""
            if r["redirect_target"]:
                target_info = f" → skill '{r['redirect_target']}' not found"
            elif r["status"] == "EMPTY":
                target_info = f" {r['lines']} lines"
            intent_info = f" intent={r['intent']}" if r.get("intent") else ""
            print(f"  [{r['status']:20s}] {r['name']:25s}{intent_info}{target_info}")
            for p in r["paths"]:
                print(f"      → {p}")
    else:
        print("\nNo real issues found. All duplicates classified as intended.\n")

    # REDIRECT_STUB 목록 (이름만)
    stubs = [r["name"] for r in report["results"] if r["status"] == "REDIRECT_STUB"]
    if stubs:
        print(f"\nRedirect stubs ({len(stubs)}) — all resolved:")
        for name in sorted(stubs):
            r = next(x for x in report["results"] if x["name"] == name)
            print(f"  - {name:25s} → {r['redirect_target']}")


def save(report: dict) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nSaved to: {OUTPUT_PATH}")


def main() -> int:
    report = audit()
    print_report(report)
    save(report)
    broken = report["summary"].get("BROKEN_REDIRECT", 0)
    # real_duplicate 도 issue 로 카운트
    real_dup = report.get("intent_summary", {}).get("real_duplicate", 0)
    real_dup += report.get("intent_summary", {}).get("unclassified", 0)
    return 1 if (broken > 0 or real_dup > 0) else 0


if __name__ == "__main__":
    sys.exit(main())

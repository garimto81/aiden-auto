#!/usr/bin/env python3
"""skill 디렉토리 3 경로 전수 감사 — 각 SKILL.md 의 무결성 검증.

목적:
- NAME_MISMATCH: dir명 != frontmatter name
- WEAK_DESC: description < 50 chars
- STUB: 본문 < 10 lines 또는 deprecated/redirect stub 키워드
- NO_FRONTMATTER: YAML frontmatter 없음
- DUPLICATE: 동일 name 이 2 곳 이상

출력: 표 + JSON. JSON 경로: .claude/state/skill-matrix-mapping.json

설계 원칙:
- read-only (수정 안 함, 권고만)
- 10초 이내
- 인간/AI 모두 읽기 좋은 출력
- 표준 라이브러리만 (yaml 파싱은 수동)
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

# 공유 helper import (stub-aware classification)
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "_shared"))
try:
    from audit_helpers import (
        BENIGN_INTENTS,
        CANONICAL_PLUGINS,  # A-9: SSOT 단일 정본
        classify_duplicate_intent,
        is_canonical_plugin,
        is_in_shadow_marketplace,
        is_redirect_stub,
        parse_frontmatter_simple,
        path_plugin,  # A-21 (Cycle 20 critic): DRY — inline plugin 추출 대신 helper 재사용
        read_text_safe,
    )
    _HAS_HELPERS = True
except ImportError:
    _HAS_HELPERS = False
    CANONICAL_PLUGINS = frozenset({"aiden-auto"})
    def is_canonical_plugin(name):
        return bool(name) and name in CANONICAL_PLUGINS
    def path_plugin(p):  # fallback — helper import 실패 시
        parts = p.parts
        if "marketplaces" in parts:
            i = parts.index("marketplaces")
            if i + 3 < len(parts) and parts[i + 2] in ("plugins", "external_plugins"):
                return parts[i + 3]
        for i in range(len(parts) - 1):
            if parts[i] == "plugins" and parts[i + 1] == "cache":
                return parts[i + 3] if i + 3 < len(parts) else None
        return None
    # fallback (helper import 실패 시) — helper BENIGN_INTENTS 와 반드시 동기화
    # A-8 (2026-05-18 audit-loop critic DI-1): plugin_multi_version_cache + external_plugin_internal_drift 추가
    BENIGN_INTENTS = frozenset({
        "shadow_marketplace", "byte_identical_mirror", "redirect_stub",
        "project_global_mirror", "plugin_namespaced",
        "priority_resolution_local_wins", "priority_resolution_global_wins",
        "localization_override",
        "plugin_multi_version_cache", "external_plugin_internal_drift",
    })

PROJECT_SKILLS_DIR = Path("C:/claude/.claude/skills")
GLOBAL_SKILLS_DIR = Path.home() / ".claude" / "skills"
# Rule 19 v2.0 정합화 (2026-05-18 audit-loop): marketplaces + cache 양쪽 스캔
PLUGIN_MARKETPLACE_ROOT = Path.home() / ".claude" / "plugins" / "marketplaces"
PLUGIN_CACHE_ROOT = Path.home() / ".claude" / "plugins" / "cache"
PLUGIN_SCAN_ROOTS = [PLUGIN_MARKETPLACE_ROOT, PLUGIN_CACHE_ROOT]
OUTPUT_PATH = Path("C:/claude/.claude/state/skill-matrix-mapping.json")

STUB_KEYWORDS = re.compile(r"\bdeprecated\b|\bredirect stub\b", re.IGNORECASE)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """YAML frontmatter 파싱 — helper의 parse_frontmatter_simple 사용 (DRY).

    helper import 실패 시 빈 dict fallback.
    """
    if _HAS_HELPERS:
        return parse_frontmatter_simple(text)
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    return {}, text[end + 4:].strip()


def collect_skill_files() -> list[Path]:
    """4 경로에서 SKILL.md 파일 수집 (marketplaces + cache).

    Windows junction / symlink 중복은 resolve() set 으로 제거.
    """
    found: list[Path] = []
    for base in [PROJECT_SKILLS_DIR, GLOBAL_SKILLS_DIR]:
        if base.is_dir():
            for p in base.rglob("SKILL.md"):
                found.append(p)
    seen_resolved: set[Path] = set()
    for root in PLUGIN_SCAN_ROOTS:
        if not root.is_dir():
            continue
        for p in root.rglob("SKILL.md"):
            try:
                resolved = p.resolve()
            except OSError:
                resolved = p
            if resolved in seen_resolved:
                continue
            seen_resolved.add(resolved)
            found.append(p)
    return sorted(found)


def classify_path(path: Path) -> str:
    """경로 기반 출처 분류 (marketplaces + cache 모두 PLUGIN)."""
    try:
        path.relative_to(PROJECT_SKILLS_DIR)
        return "LOCAL"
    except ValueError:
        pass
    try:
        path.relative_to(GLOBAL_SKILLS_DIR)
        return "GLOBAL"
    except ValueError:
        pass
    return "PLUGIN"


def audit_file(path: Path) -> dict:
    """단일 SKILL.md 감사."""
    dir_name = path.parent.name
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        return {
            "name": dir_name,
            "frontmatter_name": "",
            "path": path.as_posix(),
            "source": classify_path(path),
            "status": "NO_FRONTMATTER",
            "desc_len": 0,
            "body_lines": 0,
            "error": str(e),
        }

    fm, body = parse_frontmatter(text)
    has_fm = bool(fm)

    fm_name = fm.get("name", "").strip()
    description = fm.get("description", "").strip()
    desc_len = len(description)
    body_lines = len([l for l in body.splitlines() if l.strip()])

    # 상태 결정 (우선순위: NO_FRONTMATTER > STUB > NAME_MISMATCH > WEAK_DESC > OK)
    # STUB 임계값: helper의 _STUB_BODY_LINE_THRESHOLD(30)와 통일 (Cycle 9 MED-8)
    #
    # A-4 patch (2026-05-18 audit-loop): dir 명 vs frontmatter name 정규화 비교.
    # claude-code-plugins 같은 외부 plugin 이 공백 포함 영어 이름을 dir 로 사용 → audit 가
    # 잘못 NAME_MISMATCH 분류하는 false positive 해소. 공백/하이픈/언더스코어/대소문자 무시.
    def _normalize_name(n: str) -> str:
        return n.replace(" ", "").replace("-", "").replace("_", "").lower()

    if not has_fm:
        status = "NO_FRONTMATTER"
    elif body_lines < 10 or (body_lines < 30 and STUB_KEYWORDS.search(body)):
        status = "STUB"
    elif fm_name and _normalize_name(fm_name) != _normalize_name(dir_name):
        status = "NAME_MISMATCH"
    elif desc_len < 50:
        status = "WEAK_DESC"
    else:
        status = "OK"

    # audit_exclude: true 명시 시 false positive 방지 (의도된 redirect stub / 짧은 한글 desc 등)
    # 스펙(frontmatter 필드) ↔ 구현(audit script) 불일치 해소 (audit-loop critic FP 분류)
    if status != "OK" and fm.get("audit_exclude") is True:
        status = "OK"

    # A-13 (2026-05-18 audit-loop): user-invocable: false 인식
    # plugin 의 internal helper skill (user 가 직접 호출 안 함, 다른 skill 이 호출)은
    # dir 명 != frontmatter name 이어도 정상 패턴 (namespace 분리).
    # 예: vercel/skills/nextjs/upstream/SKILL.md (frontmatter name: next-best-practices)
    if status == "NAME_MISMATCH" and fm.get("user-invocable") is False:
        status = "OK"

    # A-13b (2026-05-18): plugin internal subdirectory 패턴 인식
    # vercel/skills/<main>/upstream/SKILL.md — main skill 의 보조 파일 (Anthropic 원본 등).
    # dir 명이 'upstream' / 'internal' / '_helper' 등의 경우 parent skill 의 namespace 분리.
    # plugin 의 의도된 multi-file 패턴이므로 NAME_MISMATCH 가 정상 패턴.
    # A-15 (Cycle 18 critic FN-2): canonical plugin (aiden-auto) 의 진짜 결함 마스킹 차단.
    # A-17 (Cycle 18 critic FP-2): Windows case-insensitive 처리 — dir_name.lower() 정규화.
    _INTERNAL_DIRS = ("upstream", "internal", "_helper", "_internal")
    if status == "NAME_MISMATCH" and dir_name.lower() in _INTERNAL_DIRS:
        # canonical plugin 의 internal dir 은 strict 검증 유지 (FN-2 차단)
        # A-21 (Cycle 20 critic): inline 추출 → path_plugin() 재사용 (DRY)
        # A-26 (Cycle 20 critic): _P 중복 import 제거
        if not is_canonical_plugin(path_plugin(Path(str(path)))):
            status = "OK"

    # A-7 (2026-05-18 audit-loop): 외부 plugin (aiden-auto 외) 의 NAME_MISMATCH / WEAK_DESC 는
    # 우리 권한 밖이므로 BENIGN 분류. 유연 아키텍처 — plugin 별 정책 정의.
    # CANONICAL_PLUGINS = 정밀 검증 대상. 그 외는 plugin 저자 책임 (사용자 결정 영역).
    # A-11 (critic FN-1, AS-2): masking 가시성 — note 필드 + masked counter 보고서 출력
    masked_status: str | None = None
    masked_plugin: str | None = None
    # A-21/A-26 (Cycle 20 critic): inline 추출 → path_plugin() 재사용 (DRY) + _P import 제거
    if status in ("NAME_MISMATCH", "WEAK_DESC"):
        plugin_name = path_plugin(Path(str(path)))
        if plugin_name and not is_canonical_plugin(plugin_name):
            masked_status = status  # 원본 결함 보존
            masked_plugin = plugin_name
            status = "OK"  # 외부 plugin manifest 결함 — plugin 저자 책임

    result = {
        "name": fm_name or dir_name,
        "frontmatter_name": fm_name,
        "path": str(path),
        "source": classify_path(path),
        "status": status,
        "desc_len": desc_len,
        "body_lines": body_lines,
    }
    if masked_status:  # A-11: masking 가시성
        result["masked_status"] = masked_status
        result["masked_plugin"] = masked_plugin
        result["note"] = "external_plugin_non_canonical"
    return result


def find_duplicates(results: list[dict]) -> None:
    """동일 name 이 2 곳 이상이면 status 를 DUPLICATE 로 교체 + intent 분류.

    intent (stub-aware classification, 작동 영향 0):
    - shadow_marketplace: 비활성 marketplace 잔재
    - redirect_stub     : 의도된 stub + canonical 패턴
    - project_global_mirror: local + global user 미러
    - real_duplicate    : 진짜 의도되지 않은 중복 (정리 필요)
    """
    name_count: dict[str, int] = {}
    for r in results:
        n = r["name"]
        name_count[n] = name_count.get(n, 0) + 1

    # 중복 그룹 모음
    dup_groups: dict[str, list[dict]] = {}
    for r in results:
        if name_count[r["name"]] > 1:
            dup_groups.setdefault(r["name"], []).append(r)

    # 그룹별 intent 분류
    for name, group in dup_groups.items():
        if _HAS_HELPERS:
            paths = [Path(r["path"]) for r in group]
            bodies: list[str] = []
            fms: list[dict] = []
            for p in paths:
                text = read_text_safe(p)
                fm, body = parse_frontmatter_simple(text)
                bodies.append(body)
                fms.append(fm)
            intent = classify_duplicate_intent(paths, bodies, fms)
        else:
            intent = "unclassified"

        for r in group:
            r["original_status"] = r["status"]
            r["status"] = "DUPLICATE"
            r["intent"] = intent


def audit() -> dict:
    files = collect_skill_files()
    results = [audit_file(p) for p in files]
    find_duplicates(results)

    summary: dict[str, int] = {
        "OK": 0, "NAME_MISMATCH": 0, "WEAK_DESC": 0,
        "STUB": 0, "NO_FRONTMATTER": 0, "DUPLICATE": 0,
    }
    for r in results:
        s = r["status"]
        summary[s] = summary.get(s, 0) + 1

    # intent 별 분포 (DUPLICATE 내부 세분화)
    intent_summary: dict[str, int] = {}
    for r in results:
        if r["status"] == "DUPLICATE":
            intent = r.get("intent", "unclassified")
            intent_summary[intent] = intent_summary.get(intent, 0) + 1

    # A-11 (critic FN-1, AS-2): masked counter 집계 — A-7 가 OK 변환한 건수 가시화
    masked_summary: dict[str, int] = {}
    masked_plugins: dict[str, int] = {}
    for r in results:
        if r.get("masked_status"):
            ms = r["masked_status"]
            masked_summary[ms] = masked_summary.get(ms, 0) + 1
            mp = r.get("masked_plugin", "?")
            masked_plugins[mp] = masked_plugins.get(mp, 0) + 1

    return {
        "ts": datetime.now().isoformat(),
        "total": len(results),
        "summary": summary,
        "intent_summary": intent_summary,
        "masked_summary": masked_summary,
        "masked_plugins": masked_plugins,
        "results": results,
    }


def print_report(report: dict) -> None:
    print(f"\n=== Skill Audit Report ({report['ts']}) ===\n")
    print(f"Skills found: {report['total']}\n")

    print("Status distribution:")
    for status, count in report["summary"].items():
        if count > 0:
            print(f"  {status:20s}: {count:3d}")

    # intent 분포 출력 (DUPLICATE 세분화) — 단일 BENIGN_INTENTS 사용
    intent_summary = report.get("intent_summary", {})
    if intent_summary:
        print("\nDUPLICATE intent breakdown:")
        for intent, count in sorted(intent_summary.items()):
            tag = "OK" if intent in BENIGN_INTENTS else "WARN"
            print(f"  [{tag:4s}] {intent:25s}: {count:3d}")

    # A-11 (critic FN-1, AS-2): masked external plugin 결함 가시화
    masked_summary = report.get("masked_summary", {})
    masked_plugins = report.get("masked_plugins", {})
    if masked_summary:
        total_masked = sum(masked_summary.values())
        print(f"\n[MASKED] External plugin defects (auto OK via A-7): {total_masked}")
        for ms, count in sorted(masked_summary.items()):
            print(f"  [MASK] {ms:20s}: {count:3d}")
        print("  by plugin:")
        for mp, count in sorted(masked_plugins.items()):
            print(f"    - {mp:30s}: {count:3d}")
        print("  → 외부 plugin 저자 책임. 사용자 customize 영역.")

    # real issue 필터 — 동일한 BENIGN_INTENTS 사용 (이전 두 벌 정의 버그 수정)
    def _shadow_check(p):
        return is_in_shadow_marketplace(p) if _HAS_HELPERS else False

    real_issues = [
        r for r in report["results"]
        if r["status"] != "OK"
        and not (r["status"] == "DUPLICATE" and r.get("intent") in BENIGN_INTENTS)
        and not _shadow_check(Path(r["path"]))
    ]
    if real_issues:
        print(f"\nReal issues (action needed): {len(real_issues)}\n")
        for r in real_issues:
            intent_info = f" intent={r['intent']}" if r["status"] == "DUPLICATE" else ""
            print(f"  [{r['status']:16s}] {r['name']:20s}{intent_info} {r['path']}")
            if r["status"] == "NAME_MISMATCH":
                dir_name = Path(r["path"]).parent.name
                print(f"      dir={dir_name!r}  frontmatter={r['frontmatter_name']!r}")
            elif r["status"] == "WEAK_DESC":
                print(f"      desc_len={r['desc_len']} (< 50)")
            elif r["status"] == "STUB":
                print(f"      body_lines={r['body_lines']}")
    else:
        print("\nNo real issues found. All duplicates classified as intended.\n")

    plugin_skills = [r["name"] for r in report["results"] if r["source"] == "PLUGIN"]
    if plugin_skills:
        print(f"\nPlugin-located skills ({len(plugin_skills)}):")
        for name in sorted(plugin_skills):
            print(f"  - {name}")


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

    # real_duplicate (benign intent 제외) + 우리 소유 path의 NAME_MISMATCH/WEAK_DESC/STUB 만 카운트
    intent_summary = report.get("intent_summary", {})
    real_dup = intent_summary.get("real_duplicate", 0) + intent_summary.get("unclassified", 0)
    # 외부 plugin / shadow marketplace는 우리 책임 아님 — local 경로만 카운트
    local_issues = sum(
        1 for r in report["results"]
        if r["status"] in ("NAME_MISMATCH", "WEAK_DESC", "STUB", "NO_FRONTMATTER")
        and str(r["path"]).replace("\\", "/").lower().startswith("c:/claude/.claude")
    )
    issue_count = real_dup + local_issues
    return 1 if issue_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())

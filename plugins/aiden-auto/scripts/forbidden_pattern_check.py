#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""forbidden_pattern_check.py — 12 금지 패턴 정적 검사 (F20 결함 해소).

⭐ Universal Deployment Premise + Core Philosophy 정합.

검사 대상:
  - /auto 12 금지 사항
  - universal premise 위반 표현
  - personalization 영역 cross-device 누출 위험

발동:
  - pre-commit hook (commit 전)
  - PostToolUse hook (Edit/Write 후)
  - CLI (--scan <dir>)

PRD: aiden-auto-self-replication.prd.md (F20)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))
try:
    from path_resolution import resolve_global_claude  # type: ignore[import-not-found]
except ImportError:
    def resolve_global_claude(): return Path.home() / ".claude"

GLOBAL_CLAUDE = resolve_global_claude()

# ─────────────────────────────────────────────────────────────
# 금지 패턴 매트릭스
# ─────────────────────────────────────────────────────────────

FORBIDDEN_PATTERNS = [
    {
        "id": "P01-hardcoded-claude-path",
        "category": "universal-premise",
        "severity": "HIGH",
        "pattern": re.compile(r'r"C:\\claude\\(?!.*backward\s+compat)', re.IGNORECASE),
        "message": "hardcoded C:\\claude\\ path — universal deployment premise 위배",
    },
    {
        "id": "P02-hardcoded-aiden-repo",
        "category": "universal-premise",
        "severity": "HIGH",
        "pattern": re.compile(r'r"C:\\aiden-auto-repo\\(?!.*backward\s+compat)', re.IGNORECASE),
        "message": "hardcoded C:\\aiden-auto-repo\\ — universal deployment premise 위배",
    },
    {
        "id": "P03-device-scoped-expr",
        "category": "universal-premise",
        "severity": "MEDIUM",
        "pattern": re.compile(r'본인\s*PC\s*만|내\s*환경에서만|다른\s*PC\s*는\s*수동'),
        "message": "device-scoped 표현 — universal premise 위배",
    },
    {
        "id": "P04-personalization-leak",
        "category": "personalization-isolation",
        "severity": "HIGH",
        "pattern": re.compile(r'(\.credentials\.json|oauth_tokens/|\.env)(?!.*EXCLUDE)'),
        "message": "personalization 자산 (credentials/oauth/env) 직접 참조 — 격리 위반 가능",
    },
    {
        "id": "P05-no-verify-bypass",
        "category": "iron-laws",
        "severity": "HIGH",
        "pattern": re.compile(r'--no-verify\b'),
        "message": "hook bypass (--no-verify) — Iron Law IL-5 위배",
    },
    {
        "id": "P06-force-flag-misuse",
        "category": "iron-laws",
        "severity": "MEDIUM",
        "pattern": re.compile(r'--force\b(?!.*사용자\s*승인|.*explicit\s*approval)', re.IGNORECASE),
        "message": "--force 사용 시 사용자 승인 명시 필요",
    },
    {
        "id": "P07-silent-option-skip",
        "category": "auto-policy",
        "severity": "MEDIUM",
        "pattern": re.compile(r'옵션\s*실패\s*시\s*조용히\s*스킵|silent\s*skip', re.IGNORECASE),
        "message": "옵션 실패 silent skip — /auto 금지 정책",
    },
    {
        "id": "P08-options-abc-list",
        "category": "core-philosophy",
        "severity": "LOW",
        "pattern": re.compile(r'A안:.*\n.*B안:.*\n.*C안:', re.MULTILINE),
        "message": "A/B/C 기술 옵션 나열 — Core Philosophy 위배 (단일 추천안 제시)",
    },
    {
        "id": "P09-architect-write",
        "category": "auto-policy",
        "severity": "HIGH",
        "pattern": re.compile(r'subagent_type="architect".*\n.*Write\(|architect\s+에이전트.*파일\s*쓰기', re.DOTALL),
        "message": "architect 에이전트 파일 쓰기 — READ-ONLY 위반",
    },
    {
        "id": "P10-test-deletion-fix",
        "category": "iron-laws",
        "severity": "HIGH",
        "pattern": re.compile(r'테스트\s*삭제.*해결|delete\s+test.*fix', re.IGNORECASE),
        "message": "테스트 삭제로 문제 해결 — Iron Law IL-1 위배",
    },
    {
        "id": "P11-os-sep-direct",
        "category": "universal-premise",
        "severity": "MEDIUM",
        "pattern": re.compile(r'os\.sep|os\.path\.sep'),
        "message": "os.sep 직접 사용 — OS-agnostic 위반 (pathlib.Path 권장)",
    },
    {
        "id": "P12-admin-required",
        "category": "universal-premise",
        "severity": "MEDIUM",
        "pattern": re.compile(r'\b(sudo|runas|admin\s+권한\s*필수|requires?\s+admin)\b', re.IGNORECASE),
        "message": "admin/sudo 권한 필수 명시 — 권한-agnostic 위반",
    },
]


# 검사 대상 디렉토리 (universal 자산)
SCAN_DIRS = {"agents", "skills", "hooks", "commands", "rules", "references", "hud", "lib", "scripts"}

# 검사 제외 파일 / 디렉토리
EXCLUDE_DIRS = {"__pycache__", ".git", "state", "projects", "oauth_tokens", "logs", "tmp", "node_modules"}
EXCLUDE_FILE_SUFFIXES = {".pyc", ".pyo", ".log", ".bak", ".swp"}
EXCLUDE_FILE_NAMES = {"forbidden_pattern_check.py"}  # self-exclude (검사 도구 자체)


def should_scan(p: Path, rel: Path) -> bool:
    if not p.is_file():
        return False
    if p.name in EXCLUDE_FILE_NAMES:
        return False
    if p.suffix in EXCLUDE_FILE_SUFFIXES:
        return False
    if any(part in EXCLUDE_DIRS for part in rel.parts):
        return False
    return True


def scan_file(p: Path) -> list:
    """단일 파일 검사."""
    violations = []
    try:
        content = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    for pattern_def in FORBIDDEN_PATTERNS:
        matches = list(pattern_def["pattern"].finditer(content))
        if matches:
            # 라인 번호 추출
            for m in matches[:5]:  # 파일당 패턴 5건 까지
                line_num = content[:m.start()].count("\n") + 1
                # 컨텍스트 (해당 라인)
                line_text = content.splitlines()[line_num - 1].strip()[:120] if line_num <= len(content.splitlines()) else ""
                violations.append({
                    "rule_id": pattern_def["id"],
                    "category": pattern_def["category"],
                    "severity": pattern_def["severity"],
                    "message": pattern_def["message"],
                    "line": line_num,
                    "text": line_text,
                })
    return violations


def scan_directory(root: Path) -> dict:
    """디렉토리 재귀 검사."""
    if not root.is_dir():
        return {"error": f"directory not found: {root}"}

    total_files = 0
    files_with_violations = 0
    all_violations = []

    for d in SCAN_DIRS:
        subdir = root / d
        if not subdir.is_dir():
            continue
        for sp in subdir.rglob("*"):
            rel = sp.relative_to(subdir)
            if not should_scan(sp, rel):
                continue
            total_files += 1
            file_violations = scan_file(sp)
            if file_violations:
                files_with_violations += 1
                for v in file_violations:
                    v["file"] = str(sp.relative_to(root))
                    all_violations.append(v)

    severity_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for v in all_violations:
        severity_counts[v["severity"]] = severity_counts.get(v["severity"], 0) + 1

    return {
        "root": str(root),
        "scanned_files": total_files,
        "files_with_violations": files_with_violations,
        "total_violations": len(all_violations),
        "severity": severity_counts,
        "violations": all_violations,
    }


def main():
    parser = argparse.ArgumentParser(description="/auto 12 금지 패턴 정적 검사")
    parser.add_argument("--scan", default=str(GLOBAL_CLAUDE), help="검사 root 디렉토리 (default: ~/.claude/)")
    parser.add_argument("--severity", choices=["HIGH", "MEDIUM", "LOW", "ALL"], default="ALL")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--summary", action="store_true", help="요약만 출력")
    parser.add_argument("--rule", help="특정 rule_id 만 검사")
    args = parser.parse_args()

    result = scan_directory(Path(args.scan))

    # severity 필터링
    if args.severity != "ALL":
        result["violations"] = [v for v in result["violations"] if v["severity"] == args.severity]
    if args.rule:
        result["violations"] = [v for v in result["violations"] if v["rule_id"] == args.rule]

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["total_violations"] == 0 else 1

    if args.summary:
        print(f"=== Forbidden Pattern Check ===")
        print(f"  Scanned: {result['scanned_files']} files")
        print(f"  Violations: {result['total_violations']} total")
        print(f"    HIGH:   {result['severity']['HIGH']}")
        print(f"    MEDIUM: {result['severity']['MEDIUM']}")
        print(f"    LOW:    {result['severity']['LOW']}")
        return 0 if result["total_violations"] == 0 else 1

    # 상세 출력 (severity 별)
    print(f"=== Forbidden Pattern Check — {result['scanned_files']} files scanned ===\n")
    if not result["violations"]:
        print("  ✅ no violations")
        return 0

    by_severity = {"HIGH": [], "MEDIUM": [], "LOW": []}
    for v in result["violations"]:
        by_severity.setdefault(v["severity"], []).append(v)

    for sev in ["HIGH", "MEDIUM", "LOW"]:
        items = by_severity.get(sev, [])
        if not items:
            continue
        print(f"--- {sev} ({len(items)} violations) ---")
        for v in items[:20]:  # severity 별 상위 20건
            print(f"  [{v['rule_id']}] {v['file']}:{v['line']}")
            print(f"    {v['message']}")
            print(f"    text: {v['text']}")
        if len(items) > 20:
            print(f"  ... and {len(items) - 20} more")
        print()

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

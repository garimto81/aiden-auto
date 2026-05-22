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
        # v3.1: 진짜 sync/copy/write 동작과 함께 등장할 때만 매칭 (false positive 제거)
        "pattern": re.compile(
            r'(shutil\.(?:copy|move)|rsync|sync_one|write_text|copy2|cp\s+).*'
            r'(\.credentials\.json|oauth_tokens|\.env)'
            r'|'
            r'(\.credentials\.json|oauth_tokens|\.env).*'
            r'(shutil\.(?:copy|move)|rsync|sync_one|write_text|copy2)'
        ),
        "message": "personalization 자산 (credentials/oauth/env) sync/copy 동작 — 격리 위반",
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
        # v3.1: 실제 위험 동작 (gh pr merge / git push --force / admin merge) 과 함께 매칭
        "pattern": re.compile(
            r'(gh\s+pr\s+merge.*--admin|gh\s+pr\s+merge.*--force|'
            r'git\s+push\s+.*--force|--force-push\b|push\s+-f\b)',
            re.IGNORECASE,
        ),
        "message": "위험한 force push/merge — 사용자 승인 필수",
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
    {
        "id": "P13-estimation-expr",
        "category": "quantification-requirement",
        "severity": "HIGH",
        "pattern": re.compile(
            r'(추정\s*\d+(?:\.\d+)?|약\s+\d+(?:\.\d+)?\s*(?:점|/10)|대략\s+\d+|'
            r'approximately\s+\d+|estimated\s+\d+|예상\s+\d+(?:\.\d+)?(?:점|/10)?|'
            r'\d+(?:\.\d+)?\s*~\s*\d+(?:\.\d+)?\s*(?:점|/10)|달성\s*예상)',
            re.IGNORECASE,
        ),
        "message": "정량 점수 추정 표현 금지 — framework_content_audit --integrated-score 의 객관 측정 결과만 인정 (D4 메타-결함 해소)",
    },
]


# ─────────────────────────────────────────────────────────────
# v3 D3: violation → 0-10 점수 환산
# ─────────────────────────────────────────────────────────────


def compute_score(audit_result: dict) -> dict:
    """v3 D3: forbidden_pattern_check 결과를 0-10 점수로 환산.

    공식: score = max(0, 10 - violations / 50)
    - 0 violations → 10.0
    - 50 violations → 9.0
    - 250 violations → 5.0
    - 500+ violations → 0.0
    """
    total = audit_result.get("total_violations", 0)
    severity = audit_result.get("severity", {})

    # severity 가중 (HIGH 무겁게)
    weighted_violations = (
        severity.get("HIGH", 0) * 1.5
        + severity.get("MEDIUM", 0) * 1.0
        + severity.get("LOW", 0) * 0.5
    )

    raw_score = max(0, 10 - weighted_violations / 50)

    return {
        "raw_score": round(raw_score, 2),
        "raw_violations": total,
        "weighted_violations": round(weighted_violations, 1),
        "severity_breakdown": severity,
        "formula": "10 - (HIGH*1.5 + MEDIUM + LOW*0.5) / 50, floor=0",
    }


# 검사 대상 디렉토리 (universal 자산)
SCAN_DIRS = {"agents", "skills", "hooks", "commands", "rules", "references", "hud", "lib", "scripts"}

# v3.2 (2026-05-23): 정책 본문 / 정의 / 금지 안내 / 검사 코드 / 예시 라인 자동 제외 (false positive)
POLICY_CONTEXT_PATTERNS = [
    re.compile(r'금지|forbidden|차단|prohibited|deny|block', re.IGNORECASE),
    re.compile(r'EXCLUDE|exclude_|위반|violation|위배|incorrect'),
    re.compile(r'정책|policy|정의|definition|설명|description'),
    re.compile(r'개인화|personalization'),                                # 정의 본문
    re.compile(r'❌|⚠'),                                                  # 금지 / 경고 마크
    re.compile(r'^\s*#.*(?:금지|forbidden|exclude)', re.IGNORECASE),       # 주석 내
    re.compile(r'\b(message|rule|pattern|severity)\b\s*[=:]'),             # forbidden_pattern_check 본문 자체
    re.compile(r'graceful', re.IGNORECASE),                                # graceful skip 정당화
    re.compile(r'\b(self-check|검사\s*(?:코드|함수|기준))\b', re.IGNORECASE),  # 검사 코드 자체
    re.compile(r'예시|example|sample\s*output', re.IGNORECASE),            # 코드 예시
    re.compile(r'^\s*"""'),                                                 # docstring
    re.compile(r'\b(0\s*~\s*10|점수\s*평가|weighted\s*score)\b'),           # 점수 시스템 정의
    re.compile(r'fallback', re.IGNORECASE),                                # fallback 구문 정당
]


def is_policy_context(line: str, file_path: Path = None) -> bool:
    """라인이 정책 정의/설명 컨텍스트인지 (false positive 제외).

    forbidden_pattern_check.py / universal-deployment-checklist.md /
    options-handlers.md 등 정책 본문 라인은 매칭 제외.
    """
    # 본 검사 도구 자체는 항상 제외
    if file_path and file_path.name == "forbidden_pattern_check.py":
        return True
    # 정책 컨텍스트 키워드 매칭
    for pat in POLICY_CONTEXT_PATTERNS:
        if pat.search(line):
            return True
    return False

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
    """단일 파일 검사 (v3.1: 정책 본문 false positive 제외)."""
    violations = []
    try:
        content = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    content_lines = content.splitlines()
    for pattern_def in FORBIDDEN_PATTERNS:
        matches = list(pattern_def["pattern"].finditer(content))
        if matches:
            # 라인 번호 추출
            for m in matches[:5]:  # 파일당 패턴 5건 까지
                line_num = content[:m.start()].count("\n") + 1
                # 컨텍스트 (해당 라인)
                line_text = content_lines[line_num - 1].strip()[:120] if line_num <= len(content_lines) else ""

                # v3.1: 정책 본문이면 제외 (false positive)
                if is_policy_context(line_text, p):
                    continue

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
    parser = argparse.ArgumentParser(description="/auto 13 금지 패턴 정적 검사 (P1-P13)")
    parser.add_argument("--scan", default=str(GLOBAL_CLAUDE), help="검사 root 디렉토리 (default: ~/.claude/)")
    parser.add_argument("--severity", choices=["HIGH", "MEDIUM", "LOW", "ALL"], default="ALL")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--summary", action="store_true", help="요약만 출력")
    parser.add_argument("--score", action="store_true", help="v3 D3: 0-10 점수 환산")
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

    if args.score:
        score_result = compute_score(result)
        if args.json:
            print(json.dumps(score_result, indent=2, ensure_ascii=False))
        else:
            print(f"=== Forbidden Pattern Score (v3 D3) ===")
            print(f"  Score: {score_result['raw_score']}/10")
            print(f"  Violations: {score_result['raw_violations']} total")
            print(f"    HIGH:   {score_result['severity_breakdown'].get('HIGH', 0)}")
            print(f"    MEDIUM: {score_result['severity_breakdown'].get('MEDIUM', 0)}")
            print(f"    LOW:    {score_result['severity_breakdown'].get('LOW', 0)}")
            print(f"  Formula: {score_result['formula']}")
        return 0 if score_result["raw_score"] >= 9.0 else 1

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

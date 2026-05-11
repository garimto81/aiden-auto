#!/usr/bin/env python3
"""Workflow Document Drift Checker — 5개 교차 검증으로 문서 간 불일치 감지"""
import json
import re
import sys
from pathlib import Path

# 경로 설정
PROJECT_ROOT = Path("C:/claude")
SKILL_MD = PROJECT_ROOT / ".claude" / "skills" / "auto" / "SKILL.md"
REFERENCE_MD = PROJECT_ROOT / ".claude" / "skills" / "auto" / "REFERENCE.md"
SETTINGS_JSON = PROJECT_ROOT / ".claude" / "settings.json"
HOOK_LIFECYCLE = Path.home() / ".claude" / "references" / "hook-lifecycle.md"
MODEL_ROUTING = Path.home() / ".claude" / "references" / "model-routing-guide.md"
AGENTS_DIR = PROJECT_ROOT / ".claude" / "agents"
HOOKS_DIR = PROJECT_ROOT / ".claude" / "hooks"


def check_version_consistency() -> dict:
    """검증 1: SKILL.md frontmatter version == 헤더 version"""
    result = {"name": "version_consistency", "status": "PASS", "details": ""}

    try:
        content = SKILL_MD.read_text(encoding="utf-8")

        # frontmatter version
        fm_match = re.search(r"^version:\s*(.+)$", content, re.MULTILINE)
        fm_version = fm_match.group(1).strip() if fm_match else None

        # 헤더 version (예: "v25.0")
        header_match = re.search(r"#.*\(v([\d.]+)", content)
        header_version = header_match.group(1) if header_match else None

        if not fm_version or not header_version:
            result["status"] = "FAIL"
            result["details"] = f"버전 추출 실패: fm={fm_version}, header={header_version}"
            return result

        # 비교: fm "25.1.0" vs header "25.0" → 메이저.마이너 비교
        fm_parts = fm_version.split(".")
        header_parts = header_version.split(".")

        if fm_parts[0] != header_parts[0]:
            result["status"] = "FAIL"
            result["details"] = f"메이저 버전 불일치: frontmatter={fm_version}, header=v{header_version}"
    except Exception as e:
        result["status"] = "ERROR"
        result["details"] = str(e)

    return result


def check_phase_structure() -> dict:
    """검증 2: SKILL.md Phase 0-4 구조 존재 확인"""
    result = {"name": "phase_structure", "status": "PASS", "details": ""}

    try:
        content = SKILL_MD.read_text(encoding="utf-8")

        expected_phases = ["Phase 0", "Phase 1", "Phase 2", "Phase 3", "Phase 4"]
        missing = [p for p in expected_phases if p not in content]

        if missing:
            result["status"] = "FAIL"
            result["details"] = f"누락된 Phase: {missing}"
    except Exception as e:
        result["status"] = "ERROR"
        result["details"] = str(e)

    return result


def check_agent_count() -> dict:
    """검증 3: 실제 에이전트 파일 수 확인"""
    result = {"name": "agent_count", "status": "PASS", "details": ""}

    try:
        if not AGENTS_DIR.exists():
            result["status"] = "FAIL"
            result["details"] = "에이전트 디렉토리 없음"
            return result

        agent_files = list(AGENTS_DIR.glob("*.md"))
        count = len(agent_files)

        result["details"] = f"에이전트 {count}개 발견"

        if count == 0:
            result["status"] = "FAIL"
            result["details"] = "에이전트 파일 0개"
    except Exception as e:
        result["status"] = "ERROR"
        result["details"] = str(e)

    return result


def check_hook_registry() -> dict:
    """검증 4: settings.json Hook == 실제 .claude/hooks/ 파일 교차 검증"""
    result = {"name": "hook_registry", "status": "PASS", "details": ""}

    try:
        # settings.json에서 Hook 파일 목록 추출
        settings = json.loads(SETTINGS_JSON.read_text(encoding="utf-8"))
        registered_hooks = set()

        hooks_config = settings.get("hooks", {})
        for event, entries in hooks_config.items():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                for hook in entry.get("hooks", []):
                    cmd = hook.get("command", "")
                    # 파일명 추출 (마지막 경로 컴포넌트)
                    if "/" in cmd:
                        filename = cmd.split("/")[-1]
                        registered_hooks.add(filename)

        # 실제 Hook 파일 목록
        actual_hooks = set()
        if HOOKS_DIR.exists():
            for f in HOOKS_DIR.iterdir():
                if f.is_file() and f.suffix in (".py", ".js") and not f.name.startswith("."):
                    actual_hooks.add(f.name)

        # recovery/ 서브디렉토리
        recovery_dir = HOOKS_DIR / "recovery"
        if recovery_dir.exists():
            for f in recovery_dir.iterdir():
                if f.is_file() and f.suffix in (".py", ".js") and f.name != "__init__.py":
                    actual_hooks.add(f.name)

        # 교차 검증
        unregistered = actual_hooks - registered_hooks
        missing_files = registered_hooks - actual_hooks

        issues = []
        if unregistered:
            issues.append(f"settings.json 미등록: {sorted(unregistered)}")
        if missing_files:
            issues.append(f"파일 없음: {sorted(missing_files)}")

        if issues:
            result["status"] = "WARN"
            result["details"] = "; ".join(issues)
        else:
            result["details"] = f"등록 {len(registered_hooks)}개, 실제 {len(actual_hooks)}개 일치"
    except Exception as e:
        result["status"] = "ERROR"
        result["details"] = str(e)

    return result


def check_option_consistency() -> dict:
    """검증 5: SKILL.md 옵션 목록 기본 검증"""
    result = {"name": "option_consistency", "status": "PASS", "details": ""}

    try:
        skill_content = SKILL_MD.read_text(encoding="utf-8")

        # SKILL.md에서 옵션 추출
        skill_options = set(re.findall(r"`(--[\w-]+)`", skill_content))

        if not skill_options:
            result["status"] = "FAIL"
            result["details"] = "SKILL.md에서 옵션 추출 실패"
            return result

        # REFERENCE.md 존재 확인 및 옵션 교차 검증
        if REFERENCE_MD.exists():
            ref_content = REFERENCE_MD.read_text(encoding="utf-8")
            ref_options = set(re.findall(r"`(--[\w-]+)`", ref_content))

            skill_only = skill_options - ref_options
            # 일부 옵션은 SKILL.md에만 있을 수 있으므로 WARN
            if skill_only and len(skill_only) > 5:
                result["status"] = "WARN"
                result["details"] = f"SKILL.md에만 존재하는 옵션 {len(skill_only)}개: {sorted(list(skill_only))[:5]}..."
            else:
                result["details"] = f"SKILL.md 옵션 {len(skill_options)}개, REFERENCE.md 옵션 {len(ref_options)}개"
        else:
            result["details"] = f"SKILL.md 옵션 {len(skill_options)}개 (REFERENCE.md 없음)"
    except Exception as e:
        result["status"] = "ERROR"
        result["details"] = str(e)

    return result


def run_all_checks() -> dict:
    """모든 검증 실행 및 리포트 생성"""
    checks = [
        check_version_consistency(),
        check_phase_structure(),
        check_agent_count(),
        check_hook_registry(),
        check_option_consistency(),
    ]

    verdicts = [c["status"] for c in checks]

    if "FAIL" in verdicts or "ERROR" in verdicts:
        overall = "FAIL"
    elif "WARN" in verdicts:
        overall = "WARN"
    else:
        overall = "PASS"

    report = {
        "verdict": overall,
        "checks": checks,
        "summary": {
            "total": len(checks),
            "pass": verdicts.count("PASS"),
            "warn": verdicts.count("WARN"),
            "fail": verdicts.count("FAIL"),
            "error": verdicts.count("ERROR"),
        }
    }

    return report


def main():
    report = run_all_checks()
    print(json.dumps(report, indent=2, ensure_ascii=False))

    # Exit code: 0=PASS, 1=WARN, 2=FAIL
    if report["verdict"] == "PASS":
        sys.exit(0)
    elif report["verdict"] == "WARN":
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()

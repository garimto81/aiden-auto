"""audit_spec_code_drift.py — spec(.md) 과 코드(.py) 사이 drift 자동 감지

배경: 본 세션에서 발견된 결함 #4. spec 갱신 후 코드 미수정 (Output Schema v1.1
선언했으나 goal_writer.py는 "1.0" 반환 등) 사례. 본 audit 가 사전 감지.

검증 대상 (정본 ~/.claude/):
1. SCHEMA_VERSION 일치
   - agents/core/intake-interviewer.md "Output Schema (v{X})" ↔ lib/goal/goal_writer.py SCHEMA_VERSION
2. 함수 시그니처 일치
   - references/phase-minus-1.5-deep-interview.md 의사코드 ↔ lib/goal/goal_writer.py 실제 함수
3. 필드 이름 일치
   - spec 의 interview_answers 필드 vs goal_writer.py 사용 키

출력: state/spec-code-drift-mapping.json
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


HOME = Path.home() / ".claude"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def resolve_canonical(p: Path) -> Path:
    """이사 간 파일 자동 추적 — 파일이 stub(frontmatter canonical:/superseded_by:)이면
    정본 경로로 따라간다. 파일 이동/stub화 후 audit pointer 가 stale 되는 결함 방지.
    정본이 부재하거나 stub 가 아니면 원래 경로 반환 (멱등·안전)."""
    text = _read(p)
    if not text:
        return p
    m = re.search(r'^(?:canonical|superseded_by):\s*(.+)$', text, re.MULTILINE)
    if not m:
        return p
    target = m.group(1).strip().strip('"\'')
    # device-agnostic 정규화: ~/.claude/ · $HOME/.claude/ 접두 제거 → HOME 기준 상대
    for pre in ("~/.claude/", "$HOME/.claude/", str(HOME).replace("\\", "/") + "/"):
        if target.replace("\\", "/").startswith(pre):
            target = target.replace("\\", "/")[len(pre):]
            break
    cand = HOME / target
    return cand if cand.exists() else p


def check_schema_version_drift() -> dict:
    """spec 의 'Output Schema (v{X})' vs 코드 SCHEMA_VERSION 일치 확인."""
    spec_path = HOME / "agents" / "core" / "intake-interviewer.md"
    code_path = HOME / "lib" / "goal" / "goal_writer.py"

    spec_text = _read(spec_path)
    code_text = _read(code_path)

    # spec: "Output Schema (v1.1, ...)"
    spec_match = re.search(r"Output Schema \(v(\d+\.\d+)", spec_text)
    spec_version = spec_match.group(1) if spec_match else None

    # code: SCHEMA_VERSION = "1.1"
    code_match = re.search(r'SCHEMA_VERSION\s*=\s*"(\d+\.\d+)"', code_text)
    code_version = code_match.group(1) if code_match else None

    return {
        "check": "schema_version",
        "spec_path": str(spec_path),
        "code_path": str(code_path),
        "spec_value": spec_version,
        "code_value": code_version,
        "match": spec_version == code_version and spec_version is not None,
    }


def check_safety_clauses_drift() -> dict:
    """spec 의 안전절 3개 ↔ 코드 DEFAULT_SAFETY_CLAUSES 일치."""
    spec_path = HOME / "agents" / "core" / "intake-interviewer.md"
    code_path = HOME / "lib" / "goal" / "goal_writer.py"

    spec_text = _read(spec_path)
    code_text = _read(code_path)

    expected = [
        "or stop after 20 turns",
        "or stop after 200k tokens consumed",
        "or stop if Perfect Output Gate FAIL 5 times consecutively",
    ]

    spec_has = sum(1 for c in expected if c in spec_text)
    code_has = sum(1 for c in expected if c in code_text)

    return {
        "check": "safety_clauses",
        "expected_count": len(expected),
        "spec_count": spec_has,
        "code_count": code_has,
        "match": spec_has == len(expected) and code_has == len(expected),
    }


def check_q4_recommendation_signals() -> dict:
    """spec 의 추천 알고리즘 4 시그널 ↔ 코드 recommend_multi_session() 구현."""
    spec_path = HOME / "agents" / "core" / "intake-interviewer.md"
    code_path = HOME / "lib" / "goal" / "goal_writer.py"

    spec_text = _read(spec_path)
    code_text = _read(code_path)

    expected_signals = [
        "estimated_lines",
        "has_plan",
        "independent_tasks_count",
        "long_running_streams",
        "estimated_hours",
    ]

    spec_has = sum(1 for s in expected_signals if s in spec_text)
    code_has = sum(1 for s in expected_signals if s in code_text)

    return {
        "check": "q4_signals",
        "expected_count": len(expected_signals),
        "spec_count": spec_has,
        "code_count": code_has,
        "match": spec_has == len(expected_signals) and code_has == len(expected_signals),
    }


def check_legacy_map() -> dict:
    """spec 의 LEGACY_MAP 5 엔트리 ↔ 코드 LEGACY_PROCESSING_METHOD_MAP."""
    spec_path = HOME / "agents" / "core" / "intake-interviewer.md"
    code_path = HOME / "lib" / "goal" / "goal_writer.py"

    spec_text = _read(spec_path)
    code_text = _read(code_path)

    # spec 표에 5 매핑 명시 / code dict 에 5 키
    spec_legacy = re.search(r"LEGACY_MAP\s*=\s*\{", spec_text) is not None
    code_legacy = re.search(r"LEGACY_PROCESSING_METHOD_MAP\s*=\s*\{", code_text) is not None

    return {
        "check": "legacy_map",
        "spec_present": spec_legacy,
        "code_present": code_legacy,
        "match": spec_legacy and code_legacy,
    }


def check_legacy_map_entries() -> dict:
    """W5 신규: LEGACY_MAP 5개 매핑 (1→D, 2→B, 3→A, 4→B, 5→B) spec ↔ code 항목별 일치."""
    spec_path = HOME / "agents" / "core" / "intake-interviewer.md"
    code_path = HOME / "lib" / "goal" / "goal_writer.py"

    spec_text = _read(spec_path)
    code_text = _read(code_path)

    expected_mapping = {"1": "D", "2": "B", "3": "A", "4": "B", "5": "B"}

    # spec 의 LEGACY_MAP dict 본문 추출
    spec_map_match = re.search(r'LEGACY_MAP\s*=\s*\{(.*?)\}', spec_text, re.DOTALL)
    spec_entries = {}
    if spec_map_match:
        for k, v in re.findall(r'"(\d)"\s*:\s*"([A-D])"', spec_map_match.group(1)):
            spec_entries[k] = v

    # code 의 LEGACY_PROCESSING_METHOD_MAP dict 본문 추출
    code_map_match = re.search(r'LEGACY_PROCESSING_METHOD_MAP\s*=\s*\{(.*?)\}', code_text, re.DOTALL)
    code_entries = {}
    if code_map_match:
        for k, v in re.findall(r'"(\d)"\s*:\s*"([A-D])"', code_map_match.group(1)):
            code_entries[k] = v

    mismatches = []
    for k, expected_v in expected_mapping.items():
        spec_v = spec_entries.get(k)
        code_v = code_entries.get(k)
        if spec_v != expected_v or code_v != expected_v:
            mismatches.append({"key": k, "expected": expected_v, "spec": spec_v, "code": code_v})

    return {
        "check": "legacy_map_entries",
        "expected_count": 5,
        "spec_count": len(spec_entries),
        "code_count": len(code_entries),
        "mismatches": mismatches,
        "match": len(mismatches) == 0 and len(spec_entries) == 5 and len(code_entries) == 5,
    }


def check_phase_minus_1_5_schema_version() -> dict:
    """W1 신규: phase-minus-1.5-deep-interview.md 의 schema_version 라벨 ↔ SCHEMA_VERSION."""
    # 이사 간 파일 자동 추적: top-level 은 stub → resolve_canonical 이 정본(skills/auto/references/)을 따라감.
    phase_path = resolve_canonical(HOME / "references" / "phase-minus-1.5-deep-interview.md")
    code_path = HOME / "lib" / "goal" / "goal_writer.py"

    phase_text = _read(phase_path)
    code_text = _read(code_path)

    # phase 본문 "schema_version 1.X" 패턴
    phase_match = re.search(r"schema_version\s+(\d+\.\d+)", phase_text)
    phase_version = phase_match.group(1) if phase_match else None

    # code SCHEMA_VERSION
    code_match = re.search(r'SCHEMA_VERSION\s*=\s*"(\d+\.\d+)"', code_text)
    code_version = code_match.group(1) if code_match else None

    return {
        "check": "phase_minus_1_5_schema_version",
        "spec_value": phase_version,   # print 줄(spec_value 조회) 정합 — 표시 정상화
        "phase_value": phase_version,  # 하위호환 유지
        "code_value": code_version,
        "match": phase_version == code_version and phase_version is not None,
    }


def main() -> int:
    checks = [
        check_schema_version_drift(),
        check_safety_clauses_drift(),
        check_q4_recommendation_signals(),
        check_legacy_map(),
        check_legacy_map_entries(),       # W5
        check_phase_minus_1_5_schema_version(),  # W1
    ]

    drift_count = sum(1 for c in checks if not c["match"])

    result = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "total_checks": len(checks),
        "drift_count": drift_count,
        "summary": {
            "match": sum(1 for c in checks if c["match"]),
            "drift": drift_count,
        },
        "checks": checks,
    }

    out = Path("C:/claude/.claude/state/spec-code-drift-mapping.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved to: {out}")
    print(f"Drift count: {drift_count} / {len(checks)}")
    for c in checks:
        status = "✓" if c["match"] else "✗"
        print(f"  {status} {c['check']}: {c.get('spec_value', c.get('spec_count', '-'))} ↔ {c.get('code_value', c.get('code_count', '-'))}")

    return 0 if drift_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

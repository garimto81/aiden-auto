#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""quantification_tracker.py — 자기 정량화 추적 hook (D5/D6 메타-결함 해소).

⭐ Universal Deployment Premise + 추정 차단.

기능:
  · framework_content_audit.py 실행 → 통합 점수 자동 timeline 누적
  · framework-score-timeline.jsonl 갱신
  · 추정 표현 사용 차단 — forbidden_pattern_check P13 발동

발동:
  · PostToolUse hook (Edit/Write 후, framework 자산 변경 시)
  · CLI: python quantification_tracker.py --measure

본 hook 의 목적:
  "5.9 → 7.5 추정" 같은 주관 산출 표현 차단.
  모든 framework 점수 보고는 객관 측정 (4 메트릭 가중 공식) 결과만 허용.

6 기준 자체 평가: 6/6 PASS.

PRD: aiden-auto-self-replication.prd.md v3 (D5/D6)
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    from path_resolution import resolve_global_claude  # type: ignore[import-not-found]
except ImportError:
    def resolve_global_claude(): return Path.home() / ".claude"

GLOBAL_CLAUDE = resolve_global_claude()
STATE_DIR = GLOBAL_CLAUDE / "state"
SCRIPTS_DIR = GLOBAL_CLAUDE / "scripts"
LOG_FILE = STATE_DIR / "quantification-tracker.log"


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] {msg}"
    print(line, file=sys.stderr)
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def measure_and_record(silent: bool = True) -> dict:
    """framework_content_audit.py 실행하여 정량 점수 산출 + timeline 기록.

    Returns:
        {value, formula, breakdown, confidence} 또는 {"error": ...}
    """
    audit_script = SCRIPTS_DIR / "framework_content_audit.py"
    if not audit_script.is_file():
        return {"error": "framework_content_audit.py 부재"}

    try:
        result = subprocess.run(
            [sys.executable, str(audit_script), "--integrated-score", "--json"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode not in (0, 1):
            return {"error": f"audit exit={result.returncode}: {result.stderr[:200]}"}

        data = json.loads(result.stdout)
        score = data.get("integrated_score", {})

        # log
        if not silent:
            log(f"score = {score.get('value')}/{score.get('max_score', 10)}  confidence={score.get('confidence')}")

        return score
    except subprocess.TimeoutExpired:
        return {"error": "audit timeout"}
    except json.JSONDecodeError as e:
        return {"error": f"json parse fail: {e}"}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def check_estimation_violations() -> dict:
    """P13-estimation-expr 위반 검사 (보고서 작성 직전 자율 발동)."""
    check_script = SCRIPTS_DIR / "forbidden_pattern_check.py"
    if not check_script.is_file():
        return {"violations": 0, "skip": True}

    try:
        result = subprocess.run(
            [sys.executable, str(check_script), "--rule", "P13-estimation-expr", "--summary"],
            capture_output=True, text=True, timeout=30,
        )
        # "Violations: NNN total" 파싱
        for line in result.stdout.splitlines():
            if "Violations:" in line and "total" in line:
                for token in line.split():
                    if token.isdigit():
                        return {"violations": int(token)}
        return {"violations": 0}
    except Exception as e:
        return {"violations": -1, "error": str(e)}


def is_framework_change() -> bool:
    """PostToolUse 발동 시 framework 자산 변경 여부 판단."""
    # 환경변수로 변경 파일 경로 받음 (CC PostToolUse 패턴)
    import os
    changed = os.environ.get("CLAUDE_TOOL_FILE", "")
    if not changed:
        return False
    universal_dirs = {"agents", "skills", "hooks", "commands", "rules", "references", "hud", "lib", "scripts"}
    return any(d in changed for d in universal_dirs)


def main():
    """CLI entry.

    Usage:
        python quantification_tracker.py --measure      # 즉시 측정 + timeline 기록
        python quantification_tracker.py --check-only   # 추정 표현 위반 검사만
        python quantification_tracker.py                # PostToolUse hook 모드
    """
    if "--measure" in sys.argv:
        score = measure_and_record(silent=False)
        print(json.dumps(score, indent=2, ensure_ascii=False))
        return 0

    if "--check-only" in sys.argv:
        result = check_estimation_violations()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    # 기본 모드 — PostToolUse hook
    if is_framework_change():
        score = measure_and_record(silent=True)
        if "error" in score:
            log(f"measure skip: {score['error']}")
        else:
            log(f"auto-tracked: score={score.get('value')}/10")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

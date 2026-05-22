#!/usr/bin/env python3
"""Phase 0.7 — Safety Gate.

cohesion_ratio 기반 4 case 분기:
  1.0      → silent pass
  0.5-1.0  → warning + auto proceed
  0.0-0.5  → user confirm required
  0.0      → user 3 선택 (defer / wait / force)

사용:
    python team_safety_gate.py --sid <sid> [--auto-answer <y|d|n>]

stdout: JSON {
    case: "clean|partial|major|total",
    decision: "proceed|defer|wait|force|cancel",
    prompt: "<사용자에게 표시할 메시지>",
    requires_user_input: bool
}
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import team_manifest  # noqa: E402


def _format_deferred(deferred: list[str], limit: int = 5) -> str:
    shown = deferred[:limit]
    extra = len(deferred) - limit
    lines = [f"  · {p}" for p in shown]
    if extra > 0:
        lines.append(f"  · ... 외 {extra}건")
    return "\n".join(lines)


def gate(sid: str, auto_answer: str | None = None) -> dict:
    m = team_manifest.get(sid)
    if m is None:
        return {"error": "manifest not found"}

    ratio = m.get("cohesion_ratio", 1.0) or 0.0
    deferred = m.get("deferred", []) or []
    remaining = m.get("planned_writes", []) or []
    original = m.get("original_count", 0) or 0

    if ratio >= 0.999 or original == 0:
        return {
            "case": "clean",
            "decision": "proceed",
            "prompt": "",
            "requires_user_input": False,
            "cohesion_ratio": ratio,
        }

    if ratio >= 0.5:
        # partial — warning only
        prompt = (
            f"⚠ Conflict Detected — 계획 수정됨 (revision 1)\n"
            f"{'━' * 60}\n"
            f"원본 scope: {original} 파일 → 수정 scope: {len(remaining)} 파일 "
            f"(cohesion {int(ratio * 100)}%)\n\n"
            f"Deferred ({len(deferred)}건):\n{_format_deferred(deferred)}\n\n"
            f"Revised task:\n  {m.get('revised_task', '')}\n\n"
            f"진행 중... (Phase 1 →)"
        )
        return {
            "case": "partial",
            "decision": "proceed",
            "prompt": prompt,
            "requires_user_input": False,
            "cohesion_ratio": ratio,
        }

    if 0 < ratio < 0.5:
        # major conflict
        prompt = (
            f"⚠ Major Conflict — scope {int(ratio * 100)}% 만 남음\n"
            f"{'━' * 60}\n"
            f"원본 scope: {original} 파일 → 수정 scope: {len(remaining)} 파일\n\n"
            f"제외된 파일 (Deferred):\n{_format_deferred(deferred)}\n\n"
            f"계속 진행하시겠습니까? 작업의 완결성이 깨질 수 있습니다.\n"
            f"  [y] 남은 {len(remaining)} 파일만 진행\n"
            f"  [d] 전체 defer (이번 /team 취소)\n"
            f"  [n] 취소 후 task 재입력"
        )
        decision = _resolve_answer(auto_answer, ["y", "d", "n"], "y",
                                   {"y": "proceed", "d": "defer", "n": "cancel"})
        return {
            "case": "major",
            "decision": decision,
            "prompt": prompt,
            "requires_user_input": auto_answer is None,
            "cohesion_ratio": ratio,
        }

    # ratio == 0 — total conflict
    prompt = (
        f"✗ Total Conflict — 모든 파일이 다른 세션에서 사용 중\n"
        f"{'━' * 60}\n"
        f"원본 scope {original} 파일 전체가 충돌. Cohesion 0%.\n\n"
        f"제외된 파일:\n{_format_deferred(deferred)}\n\n"
        f"Fallback 선택:\n"
        f"  [d] Defer 모두 (다음 /team 에서 재시도) — 권장\n"
        f"  [w] Wait fallback (5분 polling) — 비상용\n"
        f"  [f] Force (race 위험 수용)"
    )
    decision = _resolve_answer(auto_answer, ["d", "w", "f"], "d",
                               {"d": "defer", "w": "wait", "f": "force"})
    return {
        "case": "total",
        "decision": decision,
        "prompt": prompt,
        "requires_user_input": auto_answer is None,
        "cohesion_ratio": ratio,
    }


def _resolve_answer(auto: str | None, valid: list[str], default: str,
                    mapping: dict[str, str]) -> str:
    if auto is None:
        return mapping[default]
    a = auto.lower().strip()
    if a in valid:
        return mapping[a]
    return mapping[default]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sid", required=True)
    ap.add_argument("--auto-answer", default=None,
                    help="Non-interactive answer: y/d/n/w/f")
    args = ap.parse_args()

    result = gate(args.sid, args.auto_answer)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    sys.exit(main())

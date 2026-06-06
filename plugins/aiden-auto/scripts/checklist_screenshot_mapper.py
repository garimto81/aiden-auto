#!/usr/bin/env python
"""
checklist_screenshot_mapper.py — QA 스크린샷 워크플로우 3단계 매핑 도구

체크리스트 항목(checklist.yaml) ↔ 수집된 증거 파일(스크린샷/로그)을 연결하고
각 항목의 evidence + verdict 를 기록한다.

설계 원칙 (rule: 위임):
  - 본 스크립트 = 결정론적 glue. "파일 연결 + 구조적 게이트 + 기록" 만 담당.
  - 의미적 통과 판정(콘솔 에러 0, status matrix, coverage 등)은 e2e-qa-prover 위임.
    e2e-qa-prover 의 판정은 --verdicts <json> 으로 주입하면 구조적 verdict 를 override.

구조적 게이트 (mapper 자체 결정 — 결정론적):
  - VISUAL_INTERACTION: shots/{item-id}-*.png ≥ 3장 → 충족, 미만 → fail
  - LOGIC_DATA: logic-evidence/{item-id}.md 존재 → 충족, 부재 → fail

CLI:
  python checklist_screenshot_mapper.py \
    --checklist test-results/qa-login/checklist.yaml \
    [--shots-dir test-results/qa-login/shots] \
    [--logic-dir test-results/qa-login/logic-evidence] \
    [--verdicts e2e-verdicts.json] \
    [--min-shots 3]

--verdicts JSON 형식 (e2e-qa-prover 산출):
  {
    "QA-001": {"verdict": "pass"},
    "QA-007": {"verdict": "fail", "reason": "성공 화면에 'STAGE CLEAR' 미표시"}
  }

종료 코드: 0 = 정상 (verdict 채움 완료), 2 = 입력 오류
출력(stdout): 매핑 요약 JSON (pass/fail 카운트 + 미통과 항목 id 목록)
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

VISUAL = "VISUAL_INTERACTION"
LOGIC = "LOGIC_DATA"


def load_verdicts(path: Path | None) -> dict:
    """e2e-qa-prover 가 산출한 의미적 verdict override (선택)."""
    if not path:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8")) or {}
    except (OSError, json.JSONDecodeError) as e:
        print(f"[warn] verdicts 파일 무시 ({e})", file=sys.stderr)
        return {}


def match_visual(item_id: str, shots_dir: Path) -> list[str]:
    """shots/{item-id}-*.png glob 매칭 → 정렬된 상대 경로 목록."""
    if not shots_dir.is_dir():
        return []
    matches = sorted(shots_dir.glob(f"{item_id}-*.png"))
    return [str(p) for p in matches]


def match_logic(item_id: str, logic_dir: Path) -> list[str]:
    """logic-evidence/{item-id}.md 존재 매칭."""
    candidate = logic_dir / f"{item_id}.md"
    return [str(candidate)] if candidate.is_file() else []


def structural_verdict(kind: str, evidence: list[str], min_shots: int) -> tuple[str, str | None]:
    """결정론적 구조 게이트. (verdict, fail_reason) 반환."""
    if kind == VISUAL:
        if len(evidence) >= min_shots:
            return "pass", None
        return "fail", f"스크린샷 {len(evidence)}장 (최소 {min_shots}장 필요)"
    if kind == LOGIC:
        if evidence:
            return "pass", None
        return "fail", "텍스트 증거 파일(logic-evidence) 부재"
    # kind 미지정 — 보수적 fail
    return "fail", f"kind 미지정 또는 알 수 없음 ('{kind}')"


def map_item(item: dict, shots_dir: Path, logic_dir: Path,
             verdicts: dict, min_shots: int) -> dict:
    """단일 체크리스트 항목에 evidence + verdict 기록."""
    item_id = item.get("id", "")
    kind = item.get("kind", "")

    if kind == VISUAL:
        evidence = match_visual(item_id, shots_dir)
    elif kind == LOGIC:
        evidence = match_logic(item_id, logic_dir)
    else:
        evidence = []

    item["evidence"] = evidence

    # 1) 구조적 게이트 (결정론적)
    verdict, fail_reason = structural_verdict(kind, evidence, min_shots)

    # 2) e2e-qa-prover 의미적 verdict override (있으면 우선)
    override = verdicts.get(item_id)
    if override and override.get("verdict") in ("pass", "fail"):
        verdict = override["verdict"]
        fail_reason = override.get("reason") if verdict == "fail" else None

    item["verdict"] = verdict
    item["fail_reason"] = fail_reason
    return item


def recompute_stats(data: dict) -> None:
    """stats 재계산 (by_kind + verdict 집계)."""
    pending = data.get("pending") or []
    by_kind = {VISUAL: 0, LOGIC: 0}
    passed = failed = 0
    for it in pending:
        k = it.get("kind", "")
        if k in by_kind:
            by_kind[k] += 1
        if it.get("verdict") == "pass":
            passed += 1
        elif it.get("verdict") == "fail":
            failed += 1
    stats = data.setdefault("stats", {})
    stats["total"] = len(pending)
    stats["pending"] = len(pending)
    stats["by_kind"] = by_kind
    stats["verdict_pass"] = passed
    stats["verdict_fail"] = failed


def main() -> int:
    parser = argparse.ArgumentParser(description="QA 체크리스트 ↔ 증거 매핑")
    parser.add_argument("--checklist", required=True, help="checklist.yaml 경로")
    parser.add_argument("--shots-dir", help="스크린샷 디렉토리 (기본: <checklist부모>/shots)")
    parser.add_argument("--logic-dir", help="로직 증거 디렉토리 (기본: <checklist부모>/logic-evidence)")
    parser.add_argument("--verdicts", help="e2e-qa-prover verdict override JSON (선택)")
    parser.add_argument("--min-shots", type=int, default=3, help="VISUAL 최소 스크린샷 수 (기본 3)")
    args = parser.parse_args()

    if yaml is None:
        print(json.dumps({"error": "PyYAML 미설치"}), file=sys.stderr)
        return 2

    checklist_path = Path(args.checklist)
    if not checklist_path.is_file():
        print(json.dumps({"error": f"checklist 없음: {checklist_path}"}), file=sys.stderr)
        return 2

    base = checklist_path.parent
    shots_dir = Path(args.shots_dir) if args.shots_dir else base / "shots"
    logic_dir = Path(args.logic_dir) if args.logic_dir else base / "logic-evidence"
    verdicts = load_verdicts(Path(args.verdicts) if args.verdicts else None)

    data = yaml.safe_load(checklist_path.read_text(encoding="utf-8")) or {}
    pending = data.get("pending") or []

    failed_ids = []
    for item in pending:
        map_item(item, shots_dir, logic_dir, verdicts, args.min_shots)
        if item.get("verdict") == "fail":
            failed_ids.append(item.get("id"))

    data["updated_at"] = datetime.now().isoformat()
    recompute_stats(data)

    checklist_path.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )

    summary = {
        "checklist": str(checklist_path),
        "total": len(pending),
        "pass": data["stats"].get("verdict_pass", 0),
        "fail": data["stats"].get("verdict_fail", 0),
        "failed_ids": failed_ids,
        "all_pass": len(failed_ids) == 0 and len(pending) > 0,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

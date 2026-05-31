#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""detect-t2-promotion.py — 반복 문제 자동 승격 후보 탐지 (#3 개선).

rule 21 Tier Progression: 같은 root cause 가 30일 내 3회+ 재발하면 T2(메커니즘 정정)
승격 대상. improvement-ledger 에 root_cause 필드가 없으므로 files_changed 를
재발 신호 proxy 로 사용 — "같은 파일이 30일 내 T1 정정 3회+ = 구조 불안정".

⚠️ 자동 승격이 아니라 *후보 flag* (과탐은 framework-critic/사용자 검토로 거름).
결과: state/t2-promotion-candidates.json. device-agnostic, 멱등.
"""
from __future__ import annotations

import ast
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

HOME = Path.home() / ".claude"
LEDGER = HOME / "audit" / "improvement-ledger.json"

import sys
sys.path.insert(0, str(HOME / "hooks"))
try:
    from path_resolution import is_dev_pc
except Exception:
    def is_dev_pc():  # fallback: ledger 부재 graceful-skip 이 안전망
        return True

WINDOW_DAYS = 30
MIN_RECUR = 3

# 주제(테마) 키워드 — files_changed 가 못 잡는 "같은 종류, 다른 파일" 재발 탐지.
# (전체 이력 검증: doc-count-drift 15·sync-mirror 10·double-fire 7회 재발 확인)
THEMES = {
    "doc-count-drift": ["개수", "count", "정합", "불일치", "drift", "reference", "갱신"],
    "path-device": ["경로", "path", "hardcoded", "device", "$home"],
    "sync-mirror": ["sync", "동기화", "mirror", "plugin", "ssot"],
    "double-fire": ["double", "중복", "dispatcher", "phantom", "락", "lock"],
    "schema-version": ["schema", "version", "버전"],
}


def _parse_files(s) -> list:
    if isinstance(s, list):
        return s
    try:
        v = ast.literal_eval(s)
        return v if isinstance(v, list) else []
    except Exception:
        return []


def main() -> int:
    # 명시 게이트: 반복 패턴 탐지(자가개선)는 정본(dev) PC 만. 배포 PC = 소비만.
    if not is_dev_pc():
        return 0
    if not LEDGER.is_file():
        return 0
    try:
        data = json.loads(LEDGER.read_text(encoding="utf-8"))
    except Exception:
        return 0

    entries = data.get("entries", [])
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=WINDOW_DAYS)

    # 윈도우 내 T1 엔트리를 (a) 주제 키워드 + (b) files_changed 두 신호로 그룹
    theme_hits: dict[str, list[str]] = defaultdict(list)
    file_hits: dict[str, list[str]] = defaultdict(list)
    for e in entries:
        if str(e.get("tier", "")).strip() not in ("1", "T1"):
            continue
        try:
            d = datetime.strptime(e.get("date", ""), "%Y-%m-%d").date()
        except Exception:
            continue
        if d < cutoff:
            continue
        eid = e.get("id", "?")
        s = str(e.get("suggestion", "")).lower()
        for th, kws in THEMES.items():
            if any(k.lower() in s for k in kws):
                theme_hits[th].append(eid)
        for f in _parse_files(e.get("files_changed", [])):
            file_hits[f].append(eid)

    candidates = []
    for th, ids in theme_hits.items():
        if len(ids) >= MIN_RECUR:
            candidates.append({
                "signature": f"theme:{th}", "kind": "theme", "recur_count": len(ids),
                "entry_ids": ids,
                "reason": f"최근 {WINDOW_DAYS}일 내 '{th}' 종류 T1 정정 {len(ids)}회 — 메커니즘 차원 정정(T2) 검토",
            })
    for f, ids in file_hits.items():
        if len(ids) >= MIN_RECUR:
            candidates.append({
                "signature": f"file:{f}", "kind": "file", "recur_count": len(ids),
                "entry_ids": ids,
                "reason": f"최근 {WINDOW_DAYS}일 내 같은 파일 T1 정정 {len(ids)}회 — 구조 불안정 의심",
            })
    candidates.sort(key=lambda c: c["recur_count"], reverse=True)

    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "window_days": WINDOW_DAYS,
        "min_recur": MIN_RECUR,
        "method": "files_changed proxy (root_cause 필드 부재)",
        "note": "후보 flag only — 실제 T2 승격은 framework-critic/사용자 검토 후",
        "candidate_count": len(candidates),
        "candidates": candidates,
    }
    state_dir = HOME / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "t2-promotion-candidates.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if candidates:
        top = candidates[0]
        print(f"detect-t2-promotion: {len(candidates)} 후보 (top: {top['signature']} {top['recur_count']}회)")
    else:
        print(f"detect-t2-promotion: 후보 0 (최근 {WINDOW_DAYS}일 재발 패턴 없음)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

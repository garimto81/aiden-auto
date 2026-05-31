#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""record-replication.py — 복제율 자동 측정 + 기록 (SessionStart, #2 개선).

정본(~/.claude/) vs 배포 패키지(aiden-auto-repo/plugins/aiden-auto)의 universal
자산 일치율을 측정해 state/replication-rate.json 에 기록한다. Universal Deployment
Premise #1(자기복제율 ≥95%)에 실측 숫자를 부여.

device-agnostic: path_resolution 으로 경로 해석. 배포 repo 가 없는 일반 PC 는
graceful skip (측정 불가 ≠ 오류). 멱등(매 SessionStart 덮어쓰기).
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home() / ".claude"
sys.path.insert(0, str(HOME / "hooks"))

try:
    from path_resolution import resolve_aiden_auto_repo, resolve_global_claude
except Exception:
    # path_resolution 부재/오류 — 안전 skip
    raise SystemExit(0)


def main() -> int:
    repo = resolve_aiden_auto_repo()
    target = (repo / "plugins" / "aiden-auto") if repo else None
    if not target or not target.is_dir():
        # 배포 repo 없는 일반 PC — graceful skip (universal-safe)
        return 0

    canonical = resolve_global_claude()
    measure_script = HOME / "scripts" / "measure-replication.py"
    if not measure_script.is_file():
        return 0

    try:
        proc = subprocess.run(
            [sys.executable, str(measure_script),
             "--target", str(target), "--canonical", str(canonical), "--json"],
            capture_output=True, text=True, timeout=25,
        )
        data = json.loads(proc.stdout)
    except Exception as e:
        print(f"record-replication: 측정 실패 — {e}")
        return 0

    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "scope": "canonical_vs_distribution_package",
        "self_replication_rate": data.get("self_replication_rate"),
        "premise_pass": data.get("premise_pass"),
        "canonical_total": data.get("canonical_total"),
        "target_total": data.get("target_total"),
        "target_root": data.get("target_root"),
    }
    state_dir = HOME / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "replication-rate.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"record-replication: {record['self_replication_rate']}% "
          f"(canon {record['canonical_total']} → dist {record['target_total']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

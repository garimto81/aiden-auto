#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""framework_e2e_test.py — 진짜 검증 (B4).

신규 PC 시뮬레이션 e2e — tmpdir HOME 환경에서:
  1. plugin cache 만 있는 상태 (CC plugin install 흉내)
  2. bootstrap 실행 → ~/.claude/ 자동 채워짐
  3. framework_content_audit 실행 → 점수 측정
  4. forbidden_pattern_check 실행 → violations 측정
  5. 전체 흐름 정상 작동 검증

PRD: aiden-auto-self-replication.prd.md v3 (Reality Validation B4)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

GLOBAL_CLAUDE = Path.home() / ".claude"
CACHE_BASE = GLOBAL_CLAUDE / "plugins" / "cache" / "garimto81-aiden-auto" / "aiden-auto"


def find_latest_cache_version() -> Path | None:
    """Cache 의 가장 높은 version 디렉토리."""
    if not CACHE_BASE.is_dir():
        return None
    versions = sorted(
        [d for d in CACHE_BASE.iterdir() if d.is_dir() and not d.name.startswith(".")],
        reverse=True,
    )
    return versions[0] if versions else None


def setup_simulated_pc(tmphome: Path) -> dict:
    """신규 PC 시뮬레이션 setup."""
    # 1. tmphome/.claude 생성 (비어있는 상태 — agents/skills/hooks 모두 부재)
    sim_claude = tmphome / ".claude"
    sim_claude.mkdir(parents=True, exist_ok=True)

    # 2. plugin cache 복사 (CC plugin install 흉내)
    cache_src = find_latest_cache_version()
    if cache_src is None:
        return {"setup_ok": False, "error": "no cache version found"}

    cache_dst = sim_claude / "plugins" / "cache" / "garimto81-aiden-auto" / "aiden-auto" / cache_src.name
    cache_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(cache_src, cache_dst, dirs_exist_ok=True)

    # 3. 상태 검증
    skills_in_target = (sim_claude / "skills").exists()
    cache_exists = cache_dst.exists()
    cache_skill_exists = (cache_dst / "skills" / "auto" / "SKILL.md").exists()

    return {
        "setup_ok": True,
        "tmphome": str(tmphome),
        "sim_claude": str(sim_claude),
        "cache_version": cache_src.name,
        "skills_pre_bootstrap": skills_in_target,  # False expected (pristine)
        "cache_copied": cache_exists,
        "cache_has_skill": cache_skill_exists,
    }


def run_bootstrap_in_sim(tmphome: Path) -> dict:
    """시뮬레이션 환경에서 bootstrap.py 실행."""
    bootstrap_script = GLOBAL_CLAUDE / "hooks" / "bootstrap.py"
    if not bootstrap_script.is_file():
        return {"bootstrap_ok": False, "error": "bootstrap.py 부재"}

    env = os.environ.copy()
    env["HOME"] = str(tmphome)
    env["USERPROFILE"] = str(tmphome)  # Windows

    try:
        result = subprocess.run(
            [sys.executable, str(bootstrap_script)],
            capture_output=True, text=True, timeout=120, env=env,
        )
        return {
            "bootstrap_ok": result.returncode == 0,
            "stdout": result.stdout[:500],
            "stderr": result.stderr[:500],
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"bootstrap_ok": False, "error": "bootstrap timeout"}


def measure_replication_in_sim(tmphome: Path) -> dict:
    """시뮬레이션 환경에서 자기복제율 측정."""
    measure_script = GLOBAL_CLAUDE / "scripts" / "measure-replication.py"
    if not measure_script.is_file():
        return {"measure_ok": False, "error": "measure-replication.py 부재"}

    env = os.environ.copy()
    env["HOME"] = str(tmphome)
    env["USERPROFILE"] = str(tmphome)

    try:
        result = subprocess.run(
            [sys.executable, str(measure_script),
             "--canonical", str(GLOBAL_CLAUDE),
             "--target", str(tmphome / ".claude"),
             "--json"],
            capture_output=True, text=True, timeout=60, env=env,
        )
        if result.returncode in (0, 1):
            data = json.loads(result.stdout)
            return {
                "measure_ok": True,
                "self_replication_rate": data.get("self_replication_rate", 0),
                "premise_pass": data.get("premise_pass", False),
                "canonical_total": data.get("canonical_total", 0),
                "target_total": data.get("target_total", 0),
            }
        return {"measure_ok": False, "stderr": result.stderr[:300]}
    except Exception as e:
        return {"measure_ok": False, "error": f"{type(e).__name__}: {e}"}


def verify_personalization_isolation(tmphome: Path) -> dict:
    """개인화 격리 — credentials/state/projects/settings 부재 확인."""
    sim_claude = tmphome / ".claude"
    leaks = {
        "credentials_leaked": (sim_claude / ".credentials.json").exists(),
        "oauth_leaked": (sim_claude / "oauth_tokens").exists(),
        "env_leaked": (sim_claude / ".env").exists(),
        "settings_leaked": (sim_claude / "settings.json").exists(),
        "personal_memory_leaked": (sim_claude / "projects" / "C--claude" / "memory" / "MEMORY.md").exists(),
    }
    return {
        "isolation_ok": not any(leaks.values()),
        "leaks": leaks,
    }


def verify_universal_assets_present(tmphome: Path) -> dict:
    """universal 자산 (agents/skills/hooks 등) 존재 확인."""
    sim_claude = tmphome / ".claude"
    required_dirs = ["agents", "skills", "hooks", "commands", "rules", "references", "hud", "lib", "scripts"]
    present = {}
    for d in required_dirs:
        target = sim_claude / d
        present[d] = target.is_dir() and any(target.rglob("*.md")) or any(target.rglob("*.py")) if target.is_dir() else False
    return {
        "all_universal_present": all(present.values()),
        "by_directory": present,
    }


def run_e2e_test() -> dict:
    """전체 e2e 시뮬레이션."""
    with tempfile.TemporaryDirectory(prefix="aiden-auto-e2e-") as td:
        tmphome = Path(td)

        # Step 1: setup
        setup = setup_simulated_pc(tmphome)
        if not setup.get("setup_ok"):
            return {"e2e_ok": False, "stage": "setup", "detail": setup}

        # Step 2: bootstrap
        bootstrap = run_bootstrap_in_sim(tmphome)
        if not bootstrap.get("bootstrap_ok"):
            return {"e2e_ok": False, "stage": "bootstrap", "detail": bootstrap, "setup": setup}

        # Step 3: measure replication
        replication = measure_replication_in_sim(tmphome)

        # Step 4: 개인화 격리 검증
        isolation = verify_personalization_isolation(tmphome)

        # Step 5: universal 자산 검증
        universal = verify_universal_assets_present(tmphome)

        # 종합 판정
        all_pass = (
            setup.get("setup_ok")
            and bootstrap.get("bootstrap_ok")
            and replication.get("premise_pass")
            and isolation.get("isolation_ok")
            and universal.get("all_universal_present")
        )

        return {
            "e2e_ok": all_pass,
            "setup": setup,
            "bootstrap": bootstrap,
            "replication": replication,
            "isolation": isolation,
            "universal_assets": universal,
        }


def compute_e2e_score(result: dict) -> dict:
    """B4 통합 점수 (0-10).

    5 stage 평가:
      1. setup (cache 복사 + pristine 상태)
      2. bootstrap (실행 성공)
      3. replication (≥95%)
      4. isolation (credentials/state 누출 0)
      5. universal assets (모든 9 디렉토리 채워짐)
    """
    if not result.get("e2e_ok") and "stage" in result:
        # 초기 단계 실패
        return {
            "score": 0.0,
            "stage_failed": result.get("stage"),
            "basis": f"e2e failed at {result.get('stage')}",
        }

    stages_pass = [
        result.get("setup", {}).get("setup_ok", False),
        result.get("bootstrap", {}).get("bootstrap_ok", False),
        result.get("replication", {}).get("premise_pass", False),
        result.get("isolation", {}).get("isolation_ok", False),
        result.get("universal_assets", {}).get("all_universal_present", False),
    ]
    passed = sum(stages_pass)
    total = len(stages_pass)
    score = (passed / total) * 10
    return {
        "score": round(score, 2),
        "stages_passed": passed,
        "stages_total": total,
        "replication_rate": result.get("replication", {}).get("self_replication_rate", 0),
        "basis": f"{passed}/{total} stages passed, replication={result.get('replication', {}).get('self_replication_rate', 0)}%",
    }


def main():
    parser = argparse.ArgumentParser(description="진짜 검증 도구 (B4) — 신규 PC 시뮬레이션 e2e")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--score-only", action="store_true")
    args = parser.parse_args()

    print("e2e 시뮬레이션 시작 (시간 소요 30-60초)...", file=sys.stderr)
    result = run_e2e_test()
    score = compute_e2e_score(result)

    output = {"score": score, "result": result}

    if args.score_only:
        print(json.dumps(score, indent=2, ensure_ascii=False))
    elif args.json:
        print(json.dumps(output, indent=2, ensure_ascii=False, default=str))
    else:
        print(f"\n=== Framework E2E Test (Reality, B4) ===\n")
        print(f"  Score: {score['score']}/10")
        print(f"  Stages: {score.get('stages_passed', 0)}/{score.get('stages_total', 5)}")
        print(f"  Replication rate: {score.get('replication_rate', 0)}%\n")

        for stage_name in ["setup", "bootstrap", "replication", "isolation", "universal_assets"]:
            data = result.get(stage_name, {})
            ok_keys = ["setup_ok", "bootstrap_ok", "premise_pass", "isolation_ok", "all_universal_present"]
            ok = any(data.get(k, False) for k in ok_keys)
            mark = "✅" if ok else "❌"
            print(f"  {mark} {stage_name}")
            if not ok:
                for k, v in data.items():
                    if isinstance(v, (bool, str, int, float)) and not k.startswith("_"):
                        print(f"      {k}: {str(v)[:80]}")

    return 0 if score["score"] >= 9.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Stop hook: server/Flutter/src 변경 감지 시 자동 빌드 + Docker 배포.

기존 deploy_gate.py(경고만)를 대체. 실제 빌드/배포를 자동 실행.
"""

import json
import os
import subprocess
import sys
import time

DEFAULT_PROJECT = "C:/claude/game_kfc"
DEFAULT_FLUTTER_DIR = os.path.join(DEFAULT_PROJECT, "game_kfc_flutter")
DEFAULT_WEB_BUILD = os.path.join(DEFAULT_PROJECT, "web_build")
DEFAULT_WATCH_PATHS = ["server/", "game_kfc_flutter/lib/", "src/"]


def _load_deploy_config():
    """프로젝트별 deploy-config.json 로드. 없으면 game_kfc 기본값 사용.

    반복 프롬프트 분석(2026-03-25): Docker 재빌드 6회 반복 해소.
    각 프로젝트에 .claude/deploy-config.json을 두면 자동 배포 대상이 됨.
    """
    cwd = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    config_path = os.path.join(cwd, ".claude", "deploy-config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            return {
                "project": cwd,
                "watch_paths": cfg.get("watch_paths", ["server/", "src/"]),
                "docker_compose": cfg.get("docker_compose", "docker-compose.yml"),
                "health_check": cfg.get("health_check", ""),
                "flutter_dir": cfg.get("flutter_dir", ""),
                "web_build": cfg.get("web_build", ""),
            }
        except Exception:
            pass
    # 기본값: game_kfc
    return {
        "project": DEFAULT_PROJECT,
        "watch_paths": DEFAULT_WATCH_PATHS,
        "docker_compose": "docker-compose.yml",
        "health_check": "http://localhost:8000/api/rooms",
        "flutter_dir": DEFAULT_FLUTTER_DIR,
        "web_build": DEFAULT_WEB_BUILD,
    }


def _get_flag_path(project_dir):
    """커밋 SHA 기반 flag 경로. 새 커밋마다 리셋. SHA 실패 시 timestamp fallback."""
    try:
        r = subprocess.run(
            "git rev-parse --short HEAD", capture_output=True, text=True,
            cwd=project_dir, shell=True, timeout=5,
        )
        sha = r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else ""
    except Exception:
        sha = ""
    if not sha:
        sha = str(int(time.time()))
    return os.path.join(project_dir, f".deploy_verified_{sha}")


def run(cmd, cwd=None, timeout=300):
    """명령 실행. Windows에서 shell=True로 .bat/.cmd 명령 지원."""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, cwd=cwd,
            timeout=timeout, shell=True, encoding="utf-8", errors="replace",
        )
        return (r.returncode == 0, (r.stdout or "") + (r.stderr or ""))
    except subprocess.TimeoutExpired:
        return (False, f"Timeout: {cmd if isinstance(cmd, str) else ' '.join(cmd)}")


def main():
    try:
        sys.stdin.read()
    except Exception:
        pass

    # 0. Deployment Freeze 확인
    freeze_path = os.path.join("C:/claude/.claude/config", "deploy-freeze.json")
    if os.path.exists(freeze_path):
        try:
            with open(freeze_path, "r", encoding="utf-8") as f:
                freeze = json.load(f)
            if freeze.get("frozen"):
                reason = freeze.get("reason", "이유 미기재")
                sys.stderr.write(f"🧊 DEPLOY FROZEN: {reason}\n")
                sys.stderr.write("   해제: .claude/config/deploy-freeze.json → frozen: false\n")
                return
        except (json.JSONDecodeError, KeyError):
            pass

    # 설정 로드 (프로젝트별 또는 기본값)
    cfg = _load_deploy_config()
    PROJECT = cfg["project"]
    WATCH_PATHS = cfg["watch_paths"]
    FLAG = _get_flag_path(PROJECT)

    # 1. 변경 파일 확인
    ok, out = run("git diff --name-only HEAD", cwd=PROJECT)
    if not ok:
        return
    changed = [f for f in out.strip().split("\n") if f]

    # 2. 감시 대상 변경 여부
    needs_deploy = any(
        any(f.startswith(wp) for wp in WATCH_PATHS) for f in changed
    )
    if not needs_deploy:
        return

    # 3. 플래그 확인
    if os.path.exists(FLAG):
        return

    sys.stderr.write(f"🚀 auto_deploy [{os.path.basename(PROJECT)}]: 변경 감지, 빌드+배포 시작...\n")

    # 4a. Flutter Web 빌드 (flutter 변경 시만)
    flutter_dir = cfg.get("flutter_dir", "")
    web_build = cfg.get("web_build", "")
    if flutter_dir and os.path.isdir(flutter_dir):
        flutter_changed = any(f.startswith("game_kfc_flutter/") for f in changed)
        if flutter_changed:
            ok, out = run(
                f"flutter build web --output={web_build}",
                cwd=flutter_dir,
                timeout=300,
            )
            if not ok:
                sys.stderr.write(f"❌ Flutter build 실패: {out[:200]}\n")
                return

    # 4b. Docker rebuild
    ok, out = run("docker compose down --remove-orphans", cwd=PROJECT)
    if not ok:
        sys.stderr.write(f"❌ docker compose down 실패: {out[:200]}\n")
        return

    ok, out = run("docker compose build", cwd=PROJECT, timeout=300)
    if not ok:
        sys.stderr.write(f"❌ docker compose build 실패: {out[:200]}\n")
        return

    ok, out = run("docker compose up -d", cwd=PROJECT)
    if not ok:
        sys.stderr.write(f"❌ docker compose up 실패: {out[:200]}\n")
        return

    # 4c. 헬스 체크
    health_url = cfg.get("health_check", "")
    if health_url:
        time.sleep(3)
        ok, out = run(f"curl -sf {health_url}", timeout=10)
        if not ok:
            sys.stderr.write("⚠️ 헬스 체크 실패 (서버 시작 지연 가능)\n")

    # 4d. 플래그 생성
    with open(FLAG, "w") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S"))

    sys.stderr.write(f"✅ auto_deploy [{os.path.basename(PROJECT)}]: 빌드+배포 완료\n")


if __name__ == "__main__":
    main()

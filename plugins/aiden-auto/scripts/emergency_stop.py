#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Claude Code 긴급 강제 종료 스크립트 (Nuclear Option)

사용 상황:
  - Claude Code가 완전히 frozen (아무 응답 없음)
  - Ctrl+C가 무효 (키 입력 자체가 무시됨)
  - /auto stop 등 in-process 명령 실행 불가

실행 방법 (별도 PowerShell/CMD 창에서):
  python C:\\claude\\.claude\\scripts\\emergency_stop.py

  또는 빠른 전체 강제 종료:
  python C:\\claude\\.claude\\scripts\\emergency_stop.py --force

  활성 팀 목록 확인:
  python C:\\claude\\.claude\\scripts\\emergency_stop.py --list

  특정 팀만 선택 정리 (PID 종료 없음):
  python C:\\claude\\.claude\\scripts\\emergency_stop.py --team pdca-my-feature

  파일 정리만 실행 (PID 종료 없음):
  python C:\\claude\\.claude\\scripts\\emergency_stop.py --soft

  특정 팀 정리 + soft 조합:
  python C:\\claude\\.claude\\scripts\\emergency_stop.py --team foo --soft

왜 Ctrl+C가 안 되나?
  Claude Code(Node.js)가 teammate IPC 응답을 await 중이면
  이벤트 루프 자체가 블락됩니다. SIGINT(Ctrl+C)는 이벤트 루프가
  돌아야 처리되는데, 루프가 멈춰있으면 신호가 큐에만 쌓이고
  실행되지 않습니다. 외부에서 taskkill /F /PID 만이 해결책입니다.
"""

import io
import os
import sys
import json
import shutil
import subprocess
from pathlib import Path

# Windows 콘솔 UTF-8 강제 설정
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


# ──────────────────────────────────────────────
# 1. Claude Code PID 탐색
# ──────────────────────────────────────────────

def find_claude_pids() -> list[tuple[int, str]]:
    """node.exe 프로세스 중 claude 관련 PID 목록 반환"""
    pids = []

    # 방법 A: WMIC (상세 명령줄 포함)
    try:
        result = subprocess.run(
            ['wmic', 'process', 'where', 'name="node.exe"',
             'get', 'ProcessId,CommandLine', '/format:csv'],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.splitlines():
            if not line.strip() or line.startswith('Node'):
                continue
            parts = line.split(',', 2)  # Node, CommandLine, ProcessId
            if len(parts) >= 3:
                cmd = parts[1].lower()
                pid_str = parts[2].strip()
                if 'claude' in cmd and pid_str.isdigit():
                    pids.append((int(pid_str), parts[1][:80]))
    except Exception:
        pass

    # 방법 B: PowerShell (WMIC 실패 시 fallback)
    if not pids:
        try:
            result = subprocess.run(
                ['powershell', '-NoProfile', '-Command',
                 'Get-Process node -ErrorAction SilentlyContinue | '
                 'Select-Object Id,@{N="Cmd";E={$_.MainModule.FileName}} | '
                 'ConvertTo-Json'],
                capture_output=True, text=True, timeout=10
            )
            data = json.loads(result.stdout or '[]')
            if isinstance(data, dict):
                data = [data]
            for proc in data:
                pid = proc.get('Id', 0)
                cmd = proc.get('Cmd', '') or ''
                if pid:
                    pids.append((pid, cmd[:80]))
        except Exception:
            pass

    # 방법 C: tasklist (가장 단순, 명령줄 없음)
    if not pids:
        try:
            result = subprocess.run(
                ['tasklist', '/fi', 'imagename eq node.exe', '/fo', 'csv', '/nh'],
                capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.splitlines():
                line = line.strip().strip('"')
                parts = [p.strip('"') for p in line.split('","')]
                if len(parts) >= 2 and parts[1].isdigit():
                    pids.append((int(parts[1]), f"node.exe (PID={parts[1]})"))
        except Exception:
            pass

    return pids


def kill_pid(pid: int) -> bool:
    """특정 PID 강제 종료 (taskkill /F)"""
    try:
        result = subprocess.run(
            ['taskkill', '/F', '/PID', str(pid)],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except Exception as e:
        print(f"  ⚠️  PID {pid} 종료 실패: {e}")
        return False


# ──────────────────────────────────────────────
# 2. 고아 리소스 정리
# ──────────────────────────────────────────────

def cleanup_orphan_teams() -> list[str]:
    """~/.claude/teams/ 과 ~/.claude/tasks/ 고아 항목 즉시 삭제"""
    home = Path.home()
    deleted = []

    for subdir in ['teams', 'tasks']:
        target = home / '.claude' / subdir
        if not target.exists():
            continue
        for entry in target.iterdir():
            if entry.is_dir():
                try:
                    shutil.rmtree(entry, ignore_errors=True)
                    deleted.append(f"{subdir}/{entry.name}")
                except Exception as e:
                    print(f"  ⚠️  {subdir}/{entry.name} 삭제 실패: {e}")

    return deleted


def cleanup_stale_todos() -> int:
    """~/.claude/todos/ stale TODO 파일 초기화"""
    todos_dir = Path.home() / '.claude' / 'todos'
    cleaned = 0
    if todos_dir.exists():
        for f in todos_dir.glob('*.json'):
            try:
                f.write_text('[]', encoding='utf-8')
                cleaned += 1
            except Exception:
                pass
    return cleaned


def deactivate_state_files():
    """ultrawork/ralph stale 상태 파일 비활성화"""
    targets = [
        Path.home() / '.claude' / 'ultrawork-state.json',
        Path.home() / '.claude' / '.session-stats.json',
    ]
    for p in targets:
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding='utf-8'))
                data['active'] = False
                data['emergency_stopped'] = True
                p.write_text(json.dumps(data, indent=2), encoding='utf-8')
            except Exception:
                pass


# ──────────────────────────────────────────────
# 3. 팀 목록 / 선택 정리
# ──────────────────────────────────────────────

def list_teams():
    """~/.claude/teams/ 와 ~/.claude/tasks/ 에 존재하는 팀 목록 출력 후 종료"""
    home = Path.home()
    teams_dir = home / '.claude' / 'teams'
    tasks_dir = home / '.claude' / 'tasks'

    teams = set()
    if teams_dir.exists():
        teams.update(entry.name for entry in teams_dir.iterdir() if entry.is_dir())
    tasks = set()
    if tasks_dir.exists():
        tasks.update(entry.name for entry in tasks_dir.iterdir() if entry.is_dir())

    all_names = teams | tasks

    print()
    print("현재 활성 팀 목록:")
    if not all_names:
        print("  정리할 팀 없음 (비어 있음)")
    else:
        for name in sorted(all_names):
            has_team = name in teams
            has_task = name in tasks
            if has_team and has_task:
                print(f"  teams/{name} (tasks/{name})")
            elif has_team:
                print(f"  teams/{name}")
            else:
                print(f"  tasks/{name}")
    print()


def cleanup_specific_team(name: str):
    """~/.claude/teams/{name} 과 ~/.claude/tasks/{name} 만 삭제 (PID 종료 없음)"""
    home = Path.home()
    print()
    print(f"[팀 선택 정리] {name}")

    for subdir in ['teams', 'tasks']:
        target = home / '.claude' / subdir / name
        if target.exists():
            try:
                shutil.rmtree(target)
                print(f"  ✅  {subdir}/{name} 삭제")
            except Exception as e:
                print(f"  ❌  {subdir}/{name} 삭제 실패: {e}")
        else:
            print(f"  ⚠️  {subdir}/{name} 없음 (이미 정리됨)")
    print()


# ──────────────────────────────────────────────
# 4. 메인 실행
# ──────────────────────────────────────────────

def main():
    force_mode = '--force' in sys.argv
    soft_mode = '--soft' in sys.argv

    # --list: 팀 목록 출력 후 종료
    if '--list' in sys.argv:
        list_teams()
        return

    # --team {name}: 특정 팀만 정리
    if '--team' in sys.argv:
        idx = sys.argv.index('--team')
        if idx + 1 >= len(sys.argv):
            print("  ❌  --team 옵션에 팀 이름을 지정하세요.")
            print("      예: python emergency_stop.py --team pdca-my-feature")
            sys.exit(1)
        team_name = sys.argv[idx + 1]
        cleanup_specific_team(team_name)
        if not soft_mode:
            print("  ℹ️   PID 종료 없이 종료합니다. (세션 유지)")
            print("       PID도 종료하려면 --team 없이 메인 모드를 사용하세요.")
        return

    print()
    print("=" * 62)
    print("  Claude Code 긴급 강제 종료 스크립트 (Nuclear Option)")
    print("=" * 62)
    print()

    if soft_mode:
        print("--soft 모드: 파일 정리만 실행 (PID 종료 없음)")
        print()

    # ── Step 1: 고아 팀/태스크 정리 ──────────────────────────
    print("[Step 1/3] 고아 Agent Teams/Tasks 정리")
    deleted = cleanup_orphan_teams()
    if deleted:
        print(f"  ✅  {len(deleted)}개 항목 삭제:")
        for d in deleted[:8]:
            print(f"      - {d}")
        if len(deleted) > 8:
            print(f"      ... 외 {len(deleted)-8}개")
    else:
        print("  ℹ️   정리할 고아 팀 없음")

    # ── Step 2: stale TODO 초기화 ────────────────────────────
    print()
    print("[Step 2/3] Stale TODO / 상태 파일 초기화")
    cleaned = cleanup_stale_todos()
    if cleaned:
        print(f"  ✅  TODO 파일 {cleaned}개 초기화")
    deactivate_state_files()
    print("  ✅  상태 파일 비활성화 완료")

    # ── Step 3: Claude Code 프로세스 종료 ───────────────────
    if soft_mode:
        print()
        print("[Step 3/3] 건너뜀 (--soft 모드: PID 종료 없음)")
        print()
        print("=" * 62)
        print("  완료. (세션 유지됨)")
        print("=" * 62)
        print()
        return

    print()
    print("[Step 3/3] Claude Code 프로세스 강제 종료")
    pids = find_claude_pids()

    if not pids:
        print("  ⚠️   node.exe 프로세스를 찾을 수 없습니다.")
        print()
        print("  수동 종료 방법:")
        print("  1. 작업 관리자(Ctrl+Shift+Esc) → 프로세스 탭 →")
        print("     node.exe 선택 → 작업 끝내기")
        print("  2. 또는 PowerShell: Get-Process node | Stop-Process -Force")
    elif force_mode:
        # --force: 확인 없이 모두 종료
        print(f"  ⚡  --force 모드: {len(pids)}개 프로세스 모두 강제 종료")
        for pid, desc in pids:
            success = kill_pid(pid)
            status = "✅  종료" if success else "❌  실패"
            print(f"      {status}: PID {pid} ({desc[:40]})")
    elif len(pids) == 1:
        pid, desc = pids[0]
        print(f"  탐지: PID {pid}  ({desc[:50]})")
        print()
        answer = input("  이 프로세스를 강제 종료하시겠습니까? [Y/n]: ").strip().lower()
        if answer in ('', 'y', 'yes'):
            if kill_pid(pid):
                print(f"  ✅  PID {pid} 강제 종료 성공")
            else:
                print(f"  ❌  PID {pid} 종료 실패")
                print("      → 작업 관리자에서 node.exe 수동 종료 필요")
        else:
            print("  취소됨.")
    else:
        print(f"  탐지된 node.exe 프로세스 {len(pids)}개:")
        for i, (pid, desc) in enumerate(pids):
            print(f"  [{i+1}] PID={pid}  {desc[:50]}")
        print()
        print("  선택:")
        print("  - 특정 번호 입력 (1, 2, ...): 해당 PID만 종료")
        print("  - 'all': 모두 종료")
        print("  - 'n' / Enter: 취소")
        answer = input("  > ").strip().lower()

        if answer == 'all':
            for pid, desc in pids:
                if kill_pid(pid):
                    print(f"  ✅  PID {pid} 종료")
                else:
                    print(f"  ❌  PID {pid} 실패")
        elif answer.isdigit():
            idx = int(answer) - 1
            if 0 <= idx < len(pids):
                pid, _ = pids[idx]
                if kill_pid(pid):
                    print(f"  ✅  PID {pid} 종료 성공")
                else:
                    print(f"  ❌  PID {pid} 종료 실패")
            else:
                print("  ⚠️   잘못된 번호")
        else:
            print("  취소됨.")

    print()
    print("=" * 62)
    print("  완료. Claude Code를 다시 시작하려면:")
    print("  새 터미널 창에서 'claude' 명령 실행")
    print("=" * 62)
    print()


if __name__ == '__main__':
    main()

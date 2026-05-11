#!/usr/bin/env python3
"""
세션 시작 Hook - 브랜치 확인, TODO 표시, Stale 상태 정리

SessionStart 이벤트에서 실행됩니다.
"""

import json
import subprocess
import os
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())


def _get_project_root() -> Path:
    """플랫폼에 따라 루트 프로젝트 경로 반환"""
    if os.name == "nt":
        return Path("C:/claude")
    wsl_path = Path("/mnt/c/claude")
    if wsl_path.exists():
        return wsl_path
    return Path(PROJECT_DIR)


ROOT_PROJECT_DIR = _get_project_root()
ROOT_COMMANDS_DIR = ROOT_PROJECT_DIR / ".claude" / "commands"


def get_current_branch() -> str:
    """현재 브랜치 이름 반환"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def get_uncommitted_changes() -> int:
    """커밋되지 않은 변경 수"""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
        )
        return len([line for line in result.stdout.strip().split("\n") if line])
    except Exception:
        return 0


def setup_commands_junction() -> tuple[bool, str]:
    """서브 프로젝트에 커맨드 Junction 자동 설정"""
    project_path = Path(PROJECT_DIR)

    if project_path == ROOT_PROJECT_DIR:
        return False, ""

    try:
        project_path.relative_to(ROOT_PROJECT_DIR)
    except ValueError:
        return False, ""

    if not ROOT_COMMANDS_DIR.exists():
        return False, ""

    claude_dir = project_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    commands_dir = claude_dir / "commands"
    if commands_dir.exists():
        return False, ""

    try:
        result = subprocess.run(
            ["cmd.exe", "/c", "mklink", "/J", str(commands_dir), str(ROOT_COMMANDS_DIR)],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 or commands_dir.exists():
            gitignore_path = project_path / ".gitignore"
            gitignore_entry = ".claude/commands/"

            if gitignore_path.exists():
                content = gitignore_path.read_text(encoding="utf-8")
                if gitignore_entry not in content:
                    with open(gitignore_path, "a", encoding="utf-8") as f:
                        f.write(f"\n# Claude commands (Junction to root)\n{gitignore_entry}\n")
            else:
                gitignore_path.write_text(
                    f"# Claude commands (Junction to root)\n{gitignore_entry}\n",
                    encoding="utf-8"
                )

            return True, f"✨ 커맨드 Junction 자동 설정됨 → {ROOT_COMMANDS_DIR}"
        else:
            return False, ""
    except Exception:
        return False, ""


def _deactivate_state_file(path: Path, now: datetime) -> str | None:
    """상태 JSON 파일의 active 플래그를 비활성화 (새 세션이므로 무조건 stale)"""
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)

        if not state.get("active"):
            return None

        state["active"] = False
        state["deactivated_reason"] = "SessionStart cleanup (new session)"
        state["deactivated_at"] = now.isoformat()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

        name = path.stem
        return f"🔄 {name} 비활성화 (새 세션 시작)"
    except Exception:
        return None


def cleanup_stale_omc_states(ttl_hours: int = 2) -> list[str]:
    """OMC persistent mode의 stale 상태를 정리 (Stop hook 차단 방지)

    정리 대상:
    - .omc/ultrawork-state.json (local)
    - ~/.claude/ultrawork-state.json (global)
    - .omc/ralph-state.json
    - .omc/ralph-verification.json
    - .omc/continuation-count.json
    - ~/.claude/.session-stats.json
    """
    messages = []
    now = datetime.now(timezone.utc)
    omc_dir = Path(PROJECT_DIR) / ".omc"
    global_claude_dir = Path.home() / ".claude"

    # ultrawork-state (LOCAL + GLOBAL)
    for ultrawork_path in [
        omc_dir / "ultrawork-state.json",
        global_claude_dir / "ultrawork-state.json",
    ]:
        msg = _deactivate_state_file(ultrawork_path, now)
        if msg:
            loc = "global" if ultrawork_path.parent == global_claude_dir else "local"
            messages.append(f"{msg} [{loc}]")

    # ralph-state
    msg = _deactivate_state_file(omc_dir / "ralph-state.json", now)
    if msg:
        messages.append(msg)

    # ralph-verification
    ralph_verify_path = omc_dir / "ralph-verification.json"
    if ralph_verify_path.exists():
        try:
            with open(ralph_verify_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            modified = False
            if state.get("pending"):
                state["pending"] = False
                modified = True
            if state.get("status") == "pending":
                state["status"] = "expired"
                modified = True
            if modified:
                state["expired_reason"] = "SessionStart cleanup (new session)"
                with open(ralph_verify_path, "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=2)
                messages.append("🔄 ralph-verification pending 상태 만료 처리")
        except Exception:
            pass

    # continuation-count 항상 리셋
    cont_path = omc_dir / "continuation-count.json"
    if cont_path.exists():
        try:
            with open(cont_path, "r", encoding="utf-8") as f:
                cont_state = json.load(f)
            prev_count = cont_state.get("count", 0)
            if prev_count > 0:
                with open(cont_path, "w", encoding="utf-8") as f:
                    json.dump({"count": 0, "reset_at": now.isoformat()}, f, indent=2)
                messages.append(f"🔄 Todo continuation 카운터 리셋 (이전: {prev_count}회)")
        except Exception:
            pass

    # 로컬 TODO 파일 정리
    for local_todo_path in [
        omc_dir / "todos.json",
        Path(PROJECT_DIR) / ".claude" / "todos.json",
    ]:
        if local_todo_path.exists():
            try:
                mtime = datetime.fromtimestamp(
                    local_todo_path.stat().st_mtime, tz=timezone.utc
                )
                elapsed = now - mtime
                if elapsed > timedelta(hours=ttl_hours):
                    with open(local_todo_path, "r", encoding="utf-8") as f:
                        todos = json.load(f)
                    if isinstance(todos, list) and any(
                        isinstance(t, dict)
                        and t.get("status") not in ("completed", "cancelled")
                        for t in todos
                    ):
                        with open(local_todo_path, "w", encoding="utf-8") as f:
                            json.dump([], f)
                        messages.append(f"🔄 로컬 TODO 정리: {local_todo_path.name}")
            except Exception:
                pass

    # 세션 통계 리셋
    stats_path = global_claude_dir / ".session-stats.json"
    if stats_path.exists():
        try:
            with open(stats_path, "r", encoding="utf-8") as f:
                stats = json.load(f)
            if isinstance(stats.get("sessions"), dict):
                stats["sessions"] = {}
                stats["sessionStart"] = now.isoformat()
                with open(stats_path, "w", encoding="utf-8") as f:
                    json.dump(stats, f, indent=2)
            elif stats.get("toolCalls", 0) > 0:
                stats["toolCalls"] = 0
                stats["sessionStart"] = now.isoformat()
                with open(stats_path, "w", encoding="utf-8") as f:
                    json.dump(stats, f, indent=2)
        except Exception:
            pass

    return messages


def cleanup_orphan_agent_teams() -> list[str]:
    """세션 시작 시 고아 Agent Teams 즉시 정리 (TTL 없이 모두 제거)"""
    messages = []
    home = Path.home()
    teams_dir = home / ".claude" / "teams"
    tasks_dir = home / ".claude" / "tasks"

    # Teams 정리
    deleted_teams = []
    if teams_dir.exists():
        for entry in teams_dir.iterdir():
            if entry.is_dir():
                try:
                    shutil.rmtree(entry)
                    deleted_teams.append(entry.name)
                except Exception as e:
                    messages.append(f"⚠️ 팀 정리 실패: {entry.name} ({e})")

    # Tasks 정리 (teams와 같은 이름만)
    if tasks_dir.exists():
        for entry in tasks_dir.iterdir():
            if entry.is_dir() and entry.name in deleted_teams:
                try:
                    shutil.rmtree(entry)
                except Exception:
                    pass

    if deleted_teams:
        messages.append(f"🧹 고아 팀 {len(deleted_teams)}개 정리: {', '.join(deleted_teams[:3])}{'...' if len(deleted_teams) > 3 else ''}")

    return messages


def cleanup_stale_global_todos(ttl_hours: int = 2) -> list[str]:
    """~/.claude/todos/ 내 이전 세션의 stale TODO 파일 정리

    persistent-mode.mjs의 countIncompleteTodos()가 이전 agent 세션의
    미완료 TODO를 감지하여 새 세션의 Stop hook을 차단하는 문제를 방지합니다.
    """
    messages = []
    now = datetime.now(timezone.utc)
    todos_dir = Path.home() / ".claude" / "todos"

    if not todos_dir.exists():
        return messages

    cleaned_count = 0
    incomplete_total = 0

    try:
        for todo_file in todos_dir.glob("*.json"):
            try:
                mtime = datetime.fromtimestamp(
                    todo_file.stat().st_mtime, tz=timezone.utc
                )
                elapsed = now - mtime

                if elapsed <= timedelta(hours=ttl_hours):
                    continue

                with open(todo_file, "r", encoding="utf-8") as f:
                    todos = json.load(f)

                if not isinstance(todos, list) or len(todos) == 0:
                    continue

                incomplete = [
                    t for t in todos
                    if isinstance(t, dict)
                    and t.get("status") not in ("completed", "cancelled")
                ]

                if not incomplete:
                    continue

                incomplete_total += len(incomplete)

                with open(todo_file, "w", encoding="utf-8") as f:
                    json.dump([], f)
                cleaned_count += 1

            except Exception:
                continue

    except Exception:
        pass

    if cleaned_count > 0:
        messages.append(
            f"🔄 Stale TODO 파일 정리: {cleaned_count}개 파일, "
            f"{incomplete_total}개 미완료 항목 초기화 (TTL {ttl_hours}h 초과)"
        )

    return messages


def check_fatigue_signals(ttl_hours: int = 24) -> list[str]:
    """피로도 신호 파일 분석 및 경고 생성"""
    warnings = []
    fatigue_log = ROOT_PROJECT_DIR / ".claude" / "logs" / "fatigue_signals.jsonl"

    if not fatigue_log.exists():
        return warnings

    try:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=ttl_hours)
        cutoff_ts = cutoff.timestamp() * 1000  # ms

        content = fatigue_log.read_text(encoding="utf-8")
        lines = [l.strip() for l in content.strip().split("\n") if l.strip()]

        burst_files = set()
        burst_count = 0

        for line in lines:
            try:
                entry = json.loads(line)
                if entry.get("type") == "edit_burst" and entry.get("ts", 0) > cutoff_ts:
                    burst_files.add(entry.get("file", ""))
                    burst_count += 1
            except Exception:
                continue

        if burst_count >= 3:
            warnings.append(
                f"⚠️ 피로도 경고: 최근 {ttl_hours}시간 내 집중 편집 패턴 {burst_count}회 감지 "
                f"({len(burst_files)}개 파일). 잠시 휴식을 권장합니다."
            )
        elif burst_count >= 1:
            warnings.append(
                f"📊 편집 집중 패턴: {burst_count}회 (파일: {len(burst_files)}개)"
            )
    except Exception:
        pass

    return warnings


def check_agent_history(ttl_days: int = 7) -> list[str]:
    """에이전트 실행 이력 분석 — 최근 N일간 실패율 높은 에이전트 경고"""
    warnings = []
    history_path = Path.home() / ".claude" / "logs" / "agent_history.jsonl"
    if not history_path.exists():
        return warnings
    try:
        now = datetime.now(timezone.utc)
        cutoff_ts = int((now - timedelta(days=ttl_days)).timestamp() * 1000)
        content = history_path.read_text(encoding="utf-8")
        lines = [l.strip() for l in content.strip().split("\n") if l.strip()]
        # 30일 초과 항목 자동 정리
        fresh_lines = []
        cutoff_30d = int((now - timedelta(days=30)).timestamp() * 1000)
        for line in lines:
            try:
                entry = json.loads(line)
                if entry.get("ts", 0) >= cutoff_30d:
                    fresh_lines.append(line)
            except Exception:
                continue
        if fresh_lines and len(fresh_lines) < len(lines):
            history_path.write_text("\n".join(fresh_lines) + "\n", encoding="utf-8")
        # 최근 7일 분석
        agent_stats: dict[str, dict[str, int]] = {}
        for line in fresh_lines:
            try:
                entry = json.loads(line)
                if entry.get("ts", 0) < cutoff_ts:
                    continue
                agent = entry.get("agent_type", "unknown")
                if agent not in agent_stats:
                    agent_stats[agent] = {"total": 0, "failures": 0}
                agent_stats[agent]["total"] += 1
                if entry.get("status") == "failure":
                    agent_stats[agent]["failures"] += 1
            except Exception:
                continue
        for agent, stats in agent_stats.items():
            if stats["total"] >= 3 and stats["failures"] / stats["total"] > 0.3:
                rate = int(stats["failures"] / stats["total"] * 100)
                warnings.append(
                    f"agent failure rate warning: {agent} — {rate}% "
                    f"(last {ttl_days}d, {stats['failures']}/{stats['total']})"
                )
    except Exception:
        pass
    return warnings


def check_pending_backlog() -> list[str]:
    """프로젝트 백로그에서 PENDING 항목 표시"""
    warnings = []
    backlog_path = ROOT_PROJECT_DIR / "docs" / "backlog.md"

    if not backlog_path.exists():
        return warnings

    try:
        content = backlog_path.read_text(encoding="utf-8")

        # ## PENDING 섹션 추출 (## IN_PROGRESS 또는 ## DONE 전까지)
        pending_start = content.find("## PENDING")
        if pending_start == -1:
            return warnings

        pending_end = len(content)
        for marker in ["## IN_PROGRESS", "## DONE"]:
            idx = content.find(marker, pending_start + 10)
            if idx != -1 and idx < pending_end:
                pending_end = idx

        pending_section = content[pending_start + len("## PENDING"):pending_end].strip()

        if pending_section and "미처리 요구사항 없음" not in pending_section:
            # ### [B-NNN] 형식의 항목 수 카운트
            items = [line for line in pending_section.split("\n") if line.startswith("### [B-")]
            if items:
                warnings.append(f"📋 미처리 백로그 {len(items)}건:")
                for item in items[:5]:
                    warnings.append(f"   {item.lstrip('#').strip()}")
                if len(items) > 5:
                    warnings.append(f"   ... 외 {len(items) - 5}건")
    except Exception:
        pass

    return warnings


def check_prd_sync_status() -> list[str]:
    """최근 구현 커밋에 대한 PRD 업데이트 여부 감지

    feat/fix 커밋이 있지만 docs(prd) 커밋이 없으면 PRD 미업데이트로 판단.
    """
    warnings = []
    try:
        # 최근 10개 커밋 로그 추출
        result = subprocess.run(
            ["git", "log", "--oneline", "-10"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
        )
        if result.returncode != 0:
            return warnings

        commits = result.stdout.strip().split("\n")
        if not commits or commits == [""]:
            return warnings

        # feat/fix 커밋과 docs(prd) 커밋 분리
        has_impl_commits = any(
            line and (
                " feat(" in line or line.split(" ", 1)[-1].startswith("feat(") or
                " fix(" in line or line.split(" ", 1)[-1].startswith("fix(") or
                " feat!" in line or " fix!" in line
            )
            for line in commits
        )
        has_prd_commits = any(
            line and (
                "docs(prd)" in line.lower() or
                "docs: prd" in line.lower() or
                "prd:" in line.lower()
            )
            for line in commits
        )

        if has_impl_commits and not has_prd_commits:
            # docs/00-prd/ 최근 수정일 확인
            prd_dir = ROOT_PROJECT_DIR / "docs" / "00-prd"
            if prd_dir.exists():
                prd_files = list(prd_dir.glob("*.prd.md"))
                if prd_files:
                    # 가장 최근 수정된 PRD 파일 확인
                    latest_prd = max(prd_files, key=lambda p: p.stat().st_mtime)
                    prd_age_days = (
                        datetime.now(timezone.utc) -
                        datetime.fromtimestamp(latest_prd.stat().st_mtime, tz=timezone.utc)
                    ).days
                    if prd_age_days >= 1:
                        warnings.append(
                            "📋 PRD 동기화 권장: 최근 구현에 대한 PRD 업데이트가 감지되지 않았습니다. "
                            "/prd-update 실행 권장"
                        )
                else:
                    warnings.append(
                        "📋 PRD 미작성 감지: docs/00-prd/ 에 PRD 파일이 없습니다. "
                        "/prd-update --new 로 생성 권장"
                    )
    except Exception:
        pass

    return warnings


def load_previous_session() -> dict:
    """이전 세션 상태 로드"""
    session_file = Path(PROJECT_DIR) / ".claude" / "session_state.json"
    if session_file.exists():
        try:
            with open(session_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def load_auto_state() -> dict:
    """자동 완성 상태 로드"""
    auto_state_file = Path(PROJECT_DIR) / ".claude" / "workflow" / "auto_state.json"
    if auto_state_file.exists():
        try:
            with open(auto_state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_session_state(state: dict):
    """세션 상태 저장"""
    session_file = Path(PROJECT_DIR) / ".claude" / "session_state.json"
    session_file.parent.mkdir(parents=True, exist_ok=True)
    state["last_start"] = datetime.now().isoformat()
    with open(session_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def cleanup_mcp_archives(ttl_days: int = 7) -> list[str]:
    """MCP 프로파일 아카이브 파일 TTL 정리 (7일 초과 삭제)"""
    messages = []
    logs_dir = ROOT_PROJECT_DIR / ".claude" / "logs"
    if not logs_dir.exists():
        return messages
    try:
        now = datetime.now(timezone.utc)
        deleted = 0
        for f in logs_dir.glob("mcp_profile.*.jsonl"):
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            if (now - mtime).days > ttl_days:
                f.unlink()
                deleted += 1
        if deleted:
            messages.append(f"🗑️ MCP 아카이브 {deleted}개 정리 (TTL {ttl_days}d 초과)")
    except Exception:
        pass
    return messages


def verify_agent_loading() -> list[str]:
    """에이전트 파일 수 검증 (동적 카운트)"""
    messages = []
    agents_dir = ROOT_PROJECT_DIR / ".claude" / "agents"
    if not agents_dir.exists():
        messages.append("⚠️ 에이전트 디렉토리 없음: .claude/agents/")
        return messages

    agent_files = list(agents_dir.glob("*.md"))
    count = len(agent_files)

    if count == 0:
        messages.append("⚠️ 에이전트 파일 0개. .claude/agents/ 확인 필요")
    return messages


def load_project_context() -> list[str]:
    """프로젝트별 자동 컨텍스트 로드 (.claude/project-context.json)

    반복 프롬프트 분석(2026-03-25)에서 식별: 동일 지시문을 매 세션 반복 입력하는 패턴 해소.
    """
    messages = []
    ctx_path = Path(PROJECT_DIR) / ".claude" / "project-context.json"
    if not ctx_path.exists():
        return messages
    try:
        with open(ctx_path, "r", encoding="utf-8") as f:
            ctx = json.load(f)
        instructions = ctx.get("auto_instructions", [])
        if instructions:
            messages.append("📌 프로젝트 자동 컨텍스트:")
            for inst in instructions[:5]:
                messages.append(f"   → {inst}")
    except Exception:
        pass
    return messages


def detect_server_network_binding() -> list[str]:
    """서버 프로젝트에서 localhost 바인딩 감지 → 네트워크 접근 안내

    반복 프롬프트 분석(2026-03-25)에서 식별: '동일 네트워크에서 접근 가능하게' 3회 반복.
    """
    messages = []
    project_path = Path(PROJECT_DIR)
    compose_file = project_path / "docker-compose.yml"
    compose_yaml = project_path / "docker-compose.yaml"
    server_dir = project_path / "server"

    if not (compose_file.exists() or compose_yaml.exists() or server_dir.exists()):
        return messages

    # docker-compose에서 localhost 바인딩 감지
    for cf in [compose_file, compose_yaml]:
        if cf.exists():
            try:
                content = cf.read_text(encoding="utf-8")
                if "127.0.0.1:" in content or "localhost:" in content:
                    messages.append(
                        "🌐 서버가 localhost에 바인딩됨. "
                        "네트워크 접근 필요 시 0.0.0.0으로 변경하세요"
                    )
                    break
            except Exception:
                pass
    return messages


def main():
    try:
        # Circuit Breaker 상태 초기화 (새 세션이므로 CLOSED로 리셋)
        cb_state_file = ROOT_PROJECT_DIR / ".claude" / "hooks" / ".circuit_breaker_state.json"
        if cb_state_file.exists():
            try:
                with open(cb_state_file, "w", encoding="utf-8") as f:
                    json.dump({"state": "CLOSED", "failures": 0, "last_failure": 0, "backoff": 1}, f)
            except Exception:
                pass

        # Pre-compact 스냅샷 복구 경고
        compact_snapshot = ROOT_PROJECT_DIR / ".claude" / "hooks" / ".pre_compact_snapshot.json"
        if compact_snapshot.exists():
            try:
                with open(compact_snapshot, "r", encoding="utf-8") as f:
                    snapshot = json.load(f)
                tasks_info = snapshot.get("tasks_summary", {})
                in_progress = tasks_info.get("in_progress", 0)
                if in_progress > 0:
                    import sys as _sys
                    _sys.stderr.write(
                        f"⚠️ Pre-compact 스냅샷 발견: {in_progress}개 진행 중 태스크. "
                        "이전 세션의 compaction 전 상태를 확인하세요.\n"
                    )
            except Exception:
                pass

        # Stale 상태 정리 (Stop hook 차단 방지)
        stale_messages = cleanup_stale_omc_states(ttl_hours=2)
        stale_messages.extend(cleanup_stale_global_todos(ttl_hours=2))
        stale_messages.extend(cleanup_orphan_agent_teams())
        stale_messages.extend(check_fatigue_signals(ttl_hours=24))
        stale_messages.extend(check_agent_history(ttl_days=7))
        stale_messages.extend(cleanup_mcp_archives(ttl_days=7))
        stale_messages.extend(check_pending_backlog())
        stale_messages.extend(check_prd_sync_status())
        stale_messages.extend(verify_agent_loading())
        stale_messages.extend(load_project_context())
        stale_messages.extend(detect_server_network_binding())

        # Junction 설정
        junction_created, junction_message = setup_commands_junction()

        # 세션 정보
        prev_session = load_previous_session()
        branch = get_current_branch()
        changes = get_uncommitted_changes()

        session_info = []
        session_info.extend(stale_messages)

        if junction_created:
            session_info.append(junction_message)

        # 브랜치 경고
        if branch in ["main", "master"]:
            session_info.append(
                f"⚠️ 현재 {branch} 브랜치입니다. 기능 개발 시 새 브랜치 생성 권장"
            )

        # 미커밋 변경사항
        if changes > 0:
            session_info.append(f"📝 커밋되지 않은 변경: {changes}개 파일")

        # 이전 세션 미완료 작업
        if prev_session.get("pending_tasks"):
            tasks = prev_session["pending_tasks"]
            session_info.append(f"📋 이전 세션 미완료 작업: {len(tasks)}개")
            for task in tasks[:3]:
                session_info.append(f"   - {task}")
            if len(tasks) > 3:
                session_info.append(f"   ... 외 {len(tasks) - 3}개")

        # 자동 완성 상태
        auto_state = load_auto_state()
        if auto_state.get("enabled") and auto_state.get("status") in ["running", "paused"]:
            queue_len = len(auto_state.get("taskQueue", []))
            completed = auto_state.get("stats", {}).get("completed", 0)
            session_info.append("")
            session_info.append(
                f"🔄 자동 완성 루프 {'일시정지' if auto_state['status'] == 'paused' else '진행'} 중"
            )
            session_info.append(f"   - 완료: {completed}개, 대기: {queue_len}개")
            if auto_state.get("currentTask"):
                task_title = auto_state["currentTask"].get("title", "Unknown")
                session_info.append(f"   - 현재 작업: {task_title}")
            session_info.append("   → /auto --resume 로 재개 가능")

        # 세션 상태 저장
        save_session_state(
            {
                "branch": branch,
                "pending_tasks": prev_session.get("pending_tasks", []),
                "last_end": prev_session.get("last_end"),
            }
        )

        # 출력
        if session_info:
            message = "\n".join(session_info)
            print(json.dumps({"continue": True, "message": f"📍 세션 시작\n\n{message}"}))
        else:
            print(json.dumps({"continue": True}))

    except Exception as e:
        print(json.dumps({"continue": True, "error": str(e)}))


if __name__ == "__main__":
    main()

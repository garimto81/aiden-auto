#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Single Dispatcher Hook v1.0.0
=============================

Root cause solution for Claude Code hook cross-cutting wrapper limitation (L3).

Architecture:
  Claude Code event
        |
        v
  settings.json: { "Stop": [{"command": "python dispatcher.py Stop", ...}] }
        |
        v
  dispatcher.py {event}
        |
        +-- Registry scan (3 axes)
        |     ~/.claude/hooks/registry/{event}/*.json
        |     {proj}/.claude/hooks/registry/{event}/*.json
        |     {plugin}/hooks/registry/{event}/*.json
        |
        +-- Matcher filter (regex on tool_name)
        |
        +-- Serial execution (subprocess.run, per-process stderr buffer)
        |     - No shared file handle => no Windows ERROR_SHARING_VIOLATION
        |     - Sequential => zero concurrent invocation
        |
        +-- SQLite WAL logger (lock-free for our workload)
              ~/.claude/logs/hook-events.db

Modes:
  python dispatcher.py {event}              # normal hook execution
  python dispatcher.py --generate-registry  # one-shot: settings.json -> registry/
  python dispatcher.py --self-test          # built-in unit tests
  python dispatcher.py --version            # show version
"""
import os
import sys
import json
import re
import time
import shutil
import hashlib
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any

# === Configuration ===
HOME = Path(os.path.expanduser("~"))
# 외부배포 CRIT-2 (2026-05-31, 6관점 검증): 네이티브 Windows(cmd/PowerShell)는 HOME 환경변수
# 부재(USERPROFILE 만 존재). registry 39/40 command 가 리터럴 "$HOME/..." 사용 →
# os.path.expandvars 가 HOME 미설정 시 $HOME 을 못 펴 깨진 리터럴 경로로 전부 실패.
# setdefault 로 HOME 보장 (이미 set 시 미변경 — git-bash/Unix 무영향, idempotent, cross-OS).
os.environ.setdefault("HOME", str(HOME))

# 외부배포 인코딩 정합 (2026-06-09, "텍스트 깨짐" 재발 fix):
# Windows 콘솔 기본 코드페이지(cp949/cp1252) ↔ 본 dispatcher 의 Popen(encoding="utf-8")
# 디코딩 불일치로, 한글을 print 하는 자식 hook 출력이 깨지던 결함을 차단.
#   - PYTHONUTF8/PYTHONIOENCODING: os.environ 상속 → 자식 hook 이 utf-8 로 인코딩
#     → Popen 의 utf-8 디코딩과 일치 (pipe 경계 mojibake 해소).
#   - sys.stdout/stderr reconfigure: dispatcher 자신의 최종 콘솔 출력도 utf-8 강제.
# setdefault/try 라 이미 utf-8 이면 무영향(idempotent) + Unix 무해 = device/OS-agnostic.
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # py3.7+
    except (AttributeError, ValueError):
        pass  # reconfigure 미지원/이미 utf-8 — 무해

GLOBAL_REGISTRY = HOME / ".claude" / "hooks" / "registry"
PROJECT_REGISTRY = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")) / ".claude" / "hooks" / "registry"
PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT", "")

LOG_DB = HOME / ".claude" / "logs" / "hook-events.db"
LOG_DB.parent.mkdir(parents=True, exist_ok=True)

# 이벤트당 1회 락 (2026-06-01, double-fire root cause fix):
# settings.json(직접 python 진입) + plugin hooks.json(node shim 진입) 두 등록이 같은
# 이벤트에 각각 dispatcher 프로세스를 spawn → registry(reconcile/session_init/사운드 등)가
# 매 이벤트 2회 실행. scan_registry 의 _deduped 는 "한 프로세스 안" registry 중복만 막아
# "프로세스 자체가 2회 spawn" 되는 건 못 막음. → cross-process 파일 락으로 첫 진입만 진행.
LOCK_DIR = HOME / ".claude" / "state" / "dispatch-locks"
DISPATCH_LOCK_TTL = 5.0  # 초. 거의 동시(<1s)인 double-fire 차단용 — 정상 반복 호출은 통과

VERSION = "1.2.0"
SUCCESS = 0
BLOCK = 2


# === Event-level cross-process lock (double-fire 차단) ===
def _cleanup_stale_locks(now: float) -> None:
    """TTL*12(=60s) 초과한 lock 파일 정리. 저빈도(키 prefix 확률)로만 호출 — 누적 방지."""
    try:
        for p in LOCK_DIR.glob("*.lock"):
            try:
                if now - p.stat().st_mtime > DISPATCH_LOCK_TTL * 12:
                    p.unlink()
            except OSError:
                pass
    except Exception:
        pass


def acquire_event_lock(event: str, stdin_data: str) -> bool:
    """같은 (event, payload)가 TTL 내 두 번째로 진입하면 False(중복 — skip).

    첫 dispatcher 프로세스만 True(진행). 두 진입점이 거의 동시에 spawn 하므로
    payload 해시 + 짧은 TTL 로 double-fire 만 정확히 차단하고 정상 반복 호출은 통과.
    락 메커니즘 자체가 실패하면 True 반환 → 기존 동작(진행) 유지 (graceful, fail-open).
    """
    try:
        LOCK_DIR.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(
            (event + "\x00" + (stdin_data or "")).encode("utf-8", "replace")
        ).hexdigest()[:32]
        if key.startswith("0"):  # ~1/16 확률 저빈도 청소
            _cleanup_stale_locks(time.time())
        lock_path = LOCK_DIR / f"{key}.lock"
        now = time.time()
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)  # atomic
            try:
                os.write(fd, str(now).encode())
            finally:
                os.close(fd)
            return True  # 첫 진입 — 진행
        except FileExistsError:
            try:
                age = now - lock_path.stat().st_mtime
            except OSError:
                return True  # 상태 못 읽으면 안전하게 진행
            if age < DISPATCH_LOCK_TTL:
                return False  # 방금 다른 dispatcher 가 처리 — 중복 차단
            try:
                lock_path.write_text(str(now))  # stale — 갱신 후 take over
            except OSError:
                pass
            return True
    except Exception:
        return True  # fail-open

# === Logger (SQLite WAL — single-writer auto-serialized) ===
def _conn():
    conn = sqlite3.connect(str(LOG_DB), timeout=2.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hook_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            event TEXT NOT NULL,
            hook_name TEXT NOT NULL,
            owner TEXT,
            exit_code INTEGER,
            duration_ms INTEGER,
            stderr_excerpt TEXT,
            error TEXT
        )
    """)
    return conn


def log_event(event, hook_name, owner, exit_code, duration_ms, stderr_excerpt="", error=""):
    try:
        c = _conn()
        c.execute(
            "INSERT INTO hook_events (ts, event, hook_name, owner, exit_code, duration_ms, stderr_excerpt, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                datetime.now(timezone.utc).isoformat(),
                event,
                hook_name,
                owner,
                int(exit_code),
                int(duration_ms),
                (stderr_excerpt or "")[:2000],
                (error or "")[:500],
            ),
        )
        c.commit()
        c.close()
    except Exception:
        pass  # Logger must never break dispatcher


# === Registry scan ===
def scan_registry(event: str) -> List[Dict[str, Any]]:
    """3-axis registry scan, sorted by (priority asc, name asc)."""
    hooks: List[Dict[str, Any]] = []
    sources: List = [(GLOBAL_REGISTRY, "global")]

    try:
        if PROJECT_REGISTRY.exists() and PROJECT_REGISTRY.resolve() != GLOBAL_REGISTRY.resolve():
            sources.append((PROJECT_REGISTRY, "project"))
    except Exception:
        pass

    if PLUGIN_ROOT:
        plugin_reg = Path(PLUGIN_ROOT) / "hooks" / "registry"
        if plugin_reg.exists():
            sources.append((plugin_reg, "plugin"))

    for axis_root, axis_name in sources:
        event_dir = axis_root / event
        if not event_dir.exists():
            continue
        for json_file in sorted(event_dir.glob("*.json")):
            try:
                with open(json_file, encoding="utf-8") as f:
                    spec = json.load(f)
                # 외부배포 HIGH-2 (2026-05-31): OS 전용 hook(예: powershell userpromptsubmit-drain,
                # spec["os"]=="nt")을 다른 OS 에서 skip → mac/linux 매 이벤트 ENOENT 실패 + 머신특화
                # 자산 cross-OS 누출 방지. spec 에 "os" 필드 없으면 모든 OS 적용(기존 동작).
                spec_os = spec.get("os")
                if spec_os and spec_os != os.name:
                    continue
                spec.setdefault("priority", 50)
                spec.setdefault("timeout", 10)
                spec.setdefault("blocking", False)
                spec.setdefault("name", json_file.stem)
                spec.setdefault("owner", axis_name)
                spec["_source"] = str(json_file)
                spec["_axis"] = axis_name  # 발견된 실제 axis (json 의 owner 필드와 무관)
                hooks.append(spec)
            except Exception as e:
                log_event(event, json_file.name, axis_name, -1, 0, "", f"registry parse error: {e}")

    # 외부배포 critic — DOUBLE-FIRE 차단 (2026-05-31, 신규 PC 모래상자 실측):
    # 신규 PC 는 plugin hook context 라 CLAUDE_PLUGIN_ROOT 설정됨 → global(bootstrap 복사본)
    # + plugin registry 가 같은 hook 을 중복 보유 → 매 hook 2회 실행. 작업 PC 는
    # CLAUDE_PLUGIN_ROOT 미설정이라 global 단일축 → 무영향.
    # rule 19 Resolution Priority (Project > Global > Plugin) 로 이름당 1개만 유지.
    _axis_rank = {"project": 0, "global": 1, "plugin": 2}
    _deduped: Dict[str, Dict[str, Any]] = {}
    for spec in hooks:
        nm = spec.get("name", "")
        rank = _axis_rank.get(spec.get("_axis", "global"), 1)
        prev = _deduped.get(nm)
        if prev is None or rank < _axis_rank.get(prev.get("_axis", "global"), 1):
            _deduped[nm] = spec
    hooks = list(_deduped.values())

    hooks.sort(key=lambda h: (h.get("priority", 50), h.get("name", "")))
    return hooks


# === Matcher (regex on tool_name) ===
def matches(spec: Dict[str, Any], tool_name: str) -> bool:
    matcher = spec.get("matcher", "")
    if not matcher:
        return True
    try:
        return bool(re.match(f"^({matcher})$", tool_name))
    except Exception:
        return True


# === Executor (serial, per-process stderr, Windows process-tree kill on timeout) ===
def _kill_tree(pid: int) -> None:
    """Windows: kill process and all its descendants via taskkill /T."""
    if os.name == "nt":
        try:
            subprocess.run(
                f"taskkill /F /T /PID {pid}",
                shell=True,
                capture_output=True,
                timeout=5,
            )
        except Exception:
            pass
    else:
        try:
            os.killpg(os.getpgid(pid), 9)
        except Exception:
            pass


def _resolve_python() -> str:
    """현재 OS에서 실재하는 Python 3 실행기 토큰을 반환.

    외부배포 critic B2 (2026-05-31): registry command 는 `python X.py` 형태로
    고정되어 있으나, 신규 PC(특히 mac/linux)는 `python` 이 없고 `python3` 만 있는
    경우가 흔하다(대칭 문제). 이 helper 가 OS 별로 실재 실행기를 골라준다.

    Windows: `python` 우선 → 기존 동작 그대로(무변경 보장). 없으면 py 런처/python3.
    Unix:    `python3` 우선 → 신규 PC 자동 정합. 없으면 python.
    """
    candidates = ["python", "py", "python3"] if os.name == "nt" else ["python3", "python"]
    for c in candidates:
        if shutil.which(c):
            return "py -3" if c == "py" else c  # py 런처는 -3 로 Python 3 강제
    return "python" if os.name == "nt" else "python3"  # 최후 fallback = 기존 동작


_PYTHON = _resolve_python()


def _rewrite_interpreter(cmd: str) -> str:
    """registry command 의 선두 interpreter 토큰(python/python3)만 resolved 실행기로 치환.

    - Windows + `python` 실재 → `python` 그대로 (zero live regression).
    - Unix + `python` 부재 → `python3` 로 자동 치환.
    - node/기타 토큰은 그대로 (cross-platform 일관 → 손대지 않음).
    """
    stripped = cmd.lstrip()
    lead = len(cmd) - len(stripped)  # 보존할 선행 공백 길이
    for tok in ("python3", "python"):  # python3 먼저 — python 이 prefix 로 오인 매칭되지 않도록
        if stripped.startswith(tok + " "):
            return cmd[:lead] + _PYTHON + stripped[len(tok):]
    return cmd


def _maybe_bootstrap() -> None:
    """신규 PC(pristine install) + plugin context 감지 시 dispatcher 시작에서 1회 자가 부트스트랩.

    외부배포 (2026-05-31, 신규 PC 모래상자 실측): plugin hooks.json 이 모든 이벤트를
    dispatcher 로 라우팅하므로, 신규 PC 첫 이벤트에서 registry 가 참조하는
    `$HOME/.claude/hooks/*.py` 가 아직 부재(pristine). 여기서 bootstrap.py(plugin 동봉)를
    먼저 실행해 9개 디렉토리를 $HOME 로 복사 → registry 명령 경로 실존 보장 (race-free).

    게이트 (HIGH-3/HIGH-4 정합, 2026-05-31 6관점 검증):
    · sentinel(state/.bootstrap-complete) 존재 → 완료 상태 → return.
    · PLUGIN_ROOT 빈값 + marker 존재 → 작업/설치완료 PC → return (cache→SSOT 역오염 방지).
      (CC SessionStart CLAUDE_PLUGIN_ROOT 빈값 버그 빌드라도, pristine[marker 부재]이면 아래서 진행)
    · 그 외(PLUGIN_ROOT set, 또는 pristine) → bootstrap.py 실행.
      bootstrap.py 가 plugin root 자동탐지(env>autodetect, HIGH-3) + 완료 시에만 sentinel 기록(HIGH-4).
    · half-install(중단)은 sentinel 부재라 다음 이벤트에 재시도. lock 으로 동시실행 방지(MED-2).
    """
    try:
        claude = HOME / ".claude"
        sentinel = claude / "state" / ".bootstrap-complete"
        if sentinel.exists():
            return  # 이미 완료 (정상 상태) — 작업 PC 포함 매 이벤트 빠른 skip
        marker = claude / "skills" / "auto" / "SKILL.md"
        # live PC 보호: plugin context 아님(PLUGIN_ROOT 없음) + 이미 설치됨(marker)
        #   → cache→SSOT 역오염 방지 위해 bootstrap 미실행 (단 sentinel 은 1회 기록해 차후 skip)
        if not PLUGIN_ROOT and marker.exists():
            try:
                sentinel.parent.mkdir(parents=True, exist_ok=True)
                sentinel.write_text("preexisting-install\n", encoding="utf-8")
            except OSError:
                pass
            return
        bootstrap_py = Path(__file__).resolve().parent / "bootstrap.py"
        if not bootstrap_py.exists():
            return
        subprocess.run(
            [sys.executable, str(bootstrap_py)],
            timeout=120, capture_output=True, text=True,
        )
    except Exception:
        pass  # 부트스트랩 실패해도 dispatcher 본진행 막지 않음 (graceful)


def run_hook(event: str, spec: Dict[str, Any], stdin_data: str, collect: bool = False):
    # collect=True: stdout 을 직접 쓰지 않고 (code, stdout) 반환 — Stop 이벤트 JSON 병합용 (#5).
    start = datetime.now()
    name = spec["name"]
    cmd = os.path.expandvars(os.path.expanduser(spec["command"]))
    cmd = _rewrite_interpreter(cmd)  # 외부배포 critic B2: OS별 python/python3 정합 (Windows 무변경)
    timeout = spec.get("timeout", 10)
    blocking = spec.get("blocking", False)
    owner = spec.get("owner", "?")

    proc = None
    try:
        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            # 외부배포 critic M3 (2026-05-31): 자체 process group 격리.
            # POSIX 에서 _kill_tree 의 os.killpg 가 dispatcher/부모(CC) 자신을 SIGKILL 하는 사고 방지.
            # POSIX 에서만 의미(setsid), Windows 는 무시 — cross-platform 안전.
            start_new_session=(os.name != "nt"),
        )
        try:
            stdout, stderr = proc.communicate(input=stdin_data, timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_tree(proc.pid)
            try:
                stdout, stderr = proc.communicate(timeout=2)
            except Exception:
                stdout, stderr = "", ""
            duration_ms = int((datetime.now() - start).total_seconds() * 1000)
            log_event(event, name, owner, -1, duration_ms, stderr or "", f"timeout {timeout}s")
            return (SUCCESS, "") if collect else SUCCESS

        duration_ms = int((datetime.now() - start).total_seconds() * 1000)
        log_event(event, name, owner, proc.returncode, duration_ms, stderr or "", "")
        code = proc.returncode if blocking else SUCCESS
        if collect:
            return (code, stdout or "")
        if stdout:
            sys.stdout.write(stdout)
            sys.stdout.flush()
        return code
    except Exception as e:
        duration_ms = int((datetime.now() - start).total_seconds() * 1000)
        if proc is not None:
            try:
                _kill_tree(proc.pid)
            except Exception:
                pass
        log_event(event, name, owner, -1, duration_ms, "", f"exception: {e}")
        return (SUCCESS, "") if collect else SUCCESS


# === Registry generator (one-shot, from existing settings.json) ===
def strip_wrapper(cmd: str) -> str:
    if "_silent_wrap.cmd" in cmd:
        return cmd.split("_silent_wrap.cmd", 1)[1].strip()
    return cmd


def derive_name(cmd: str, event: str) -> str:
    base = strip_wrapper(cmd)
    tokens = base.split()
    for token in tokens:
        clean = token.strip('"').strip("'")
        if "/" in clean or "\\" in clean or clean.endswith(
            (".py", ".mjs", ".js", ".sh", ".ps1", ".cmd", ".bat")
        ):
            return Path(clean).stem
    return f"{event}-{tokens[0] if tokens else 'unnamed'}".lower()


def generate_registry_from_settings():
    settings_path = HOME / ".claude" / "settings.json"
    if not settings_path.exists():
        print(f"ERROR: settings.json not found at {settings_path}", file=sys.stderr)
        sys.exit(1)
    with open(settings_path, encoding="utf-8") as f:
        settings = json.load(f)

    hooks_section = settings.get("hooks", {})
    total = 0
    seen_keys: Dict[str, int] = {}

    for event_name, matcher_groups in hooks_section.items():
        if not isinstance(matcher_groups, list):
            continue
        for group in matcher_groups:
            matcher = group.get("matcher", "")
            for hook_def in group.get("hooks", []):
                raw_cmd = hook_def.get("command", "")
                if not raw_cmd:
                    continue
                cmd = strip_wrapper(raw_cmd)
                timeout = hook_def.get("timeout", 10)
                is_async = hook_def.get("async", False)
                name = derive_name(raw_cmd, event_name)

                key = f"{event_name}/{name}"
                if key in seen_keys:
                    seen_keys[key] += 1
                    name = f"{name}-{seen_keys[key]}"
                else:
                    seen_keys[key] = 1

                spec = {
                    "name": name,
                    "command": cmd,
                    "timeout": timeout,
                    "blocking": not is_async,
                    "priority": 50,
                    "owner": "global",
                }
                if matcher:
                    spec["matcher"] = matcher

                target_dir = GLOBAL_REGISTRY / event_name
                target_dir.mkdir(parents=True, exist_ok=True)
                target_file = target_dir / f"{name}.json"
                with open(target_file, "w", encoding="utf-8") as f:
                    json.dump(spec, f, indent=2, ensure_ascii=False)
                total += 1
                print(f"  [{event_name}] {name} -> {target_file.relative_to(HOME)}")

    print(f"\nGenerated {total} registry JSON files under {GLOBAL_REGISTRY.relative_to(HOME)}")


# === Self test ===
def run_self_test():
    print("=" * 60)
    print(f"Dispatcher v{VERSION} self-test")
    print("=" * 60)
    results = {"pass": 0, "fail": 0}

    # T1: Registry scan
    print("\n[T1] Registry scan...")
    for event in [
        "Stop",
        "SubagentStop",
        "PostToolUse",
        "PreToolUse",
        "SessionStart",
        "SessionEnd",
        "UserPromptSubmit",
    ]:
        hooks = scan_registry(event)
        print(f"  {event:20s}: {len(hooks)} hooks")
        for h in hooks:
            tag = " [blocking]" if h.get("blocking") else " [async]"
            mtag = f" matcher={h['matcher']}" if h.get("matcher") else ""
            print(f"    - {h['name']:35s} timeout={h['timeout']}s{tag}{mtag}")
    results["pass"] += 1

    # T2: Matcher logic
    print("\n[T2] Matcher logic...")
    cases = [
        ({"matcher": "Edit|Write|MultiEdit"}, "Edit", True),
        ({"matcher": "Edit|Write|MultiEdit"}, "Write", True),
        ({"matcher": "Edit|Write|MultiEdit"}, "Read", False),
        ({"matcher": ""}, "Anything", True),
        ({}, "Anything", True),
        ({"matcher": "Bash"}, "Bash", True),
        ({"matcher": "Bash"}, "BashTool", False),
    ]
    for spec, tool, expected in cases:
        actual = matches(spec, tool)
        ok = (actual == expected)
        tag = "PASS" if ok else "FAIL"
        results["pass" if ok else "fail"] += 1
        m = spec.get("matcher", "<none>")
        print(f"  [{tag}] matcher={m!r:30s} tool={tool!r:12s} -> {actual} (exp {expected})")

    # T3: Logger
    print("\n[T3] Logger SQLite WAL...")
    log_event("__selftest__", "self_test_marker", "system", 0, 0, "", "")
    c = _conn()
    cnt = c.execute("SELECT COUNT(*) FROM hook_events WHERE event='__selftest__'").fetchone()[0]
    c.close()
    if cnt >= 1:
        print(f"  [PASS] event row count={cnt}")
        results["pass"] += 1
    else:
        print(f"  [FAIL] event row count={cnt}")
        results["fail"] += 1
    print(f"  Log DB: {LOG_DB}")

    # T4: Serial execution
    print("\n[T4] Serial execution (3 echo hooks)...")
    import time
    specs = [
        {"name": "echo1", "command": "cmd /c echo hook1", "timeout": 5, "blocking": False, "owner": "test"},
        {"name": "echo2", "command": "cmd /c echo hook2", "timeout": 5, "blocking": False, "owner": "test"},
        {"name": "echo3", "command": "cmd /c echo hook3", "timeout": 5, "blocking": False, "owner": "test"},
    ]
    start = time.time()
    for s in specs:
        run_hook("__selftest__", s, "")
    elapsed_ms = (time.time() - start) * 1000
    print(f"  [PASS] 3 echo hooks executed serially in {elapsed_ms:.0f}ms")
    results["pass"] += 1

    # T5: Concurrent collision absence (key safety test)
    print("\n[T5] Concurrent collision absence (rapid-fire 10 hooks)...")
    spec = {"name": "rapid", "command": "cmd /c echo x", "timeout": 5, "blocking": False, "owner": "test"}
    errs = 0
    start = time.time()
    for i in range(10):
        try:
            run_hook("__selftest__", spec, "")
        except Exception:
            errs += 1
    elapsed_ms = (time.time() - start) * 1000
    if errs == 0:
        print(f"  [PASS] 10 hooks, 0 errors, {elapsed_ms:.0f}ms total")
        results["pass"] += 1
    else:
        print(f"  [FAIL] 10 hooks, {errs} errors")
        results["fail"] += 1

    # T6: blocking exit code propagation
    print("\n[T6] Blocking exit-code propagation...")
    spec_block = {"name": "block_fail", "command": "cmd /c exit 2", "timeout": 5, "blocking": True, "owner": "test"}
    spec_async = {"name": "async_fail", "command": "cmd /c exit 1", "timeout": 5, "blocking": False, "owner": "test"}
    code_block = run_hook("__selftest__", spec_block, "")
    code_async = run_hook("__selftest__", spec_async, "")
    if code_block == 2 and code_async == 0:
        print(f"  [PASS] blocking exit=2 propagated, async exit suppressed (got 0)")
        results["pass"] += 1
    else:
        print(f"  [FAIL] blocking={code_block} async={code_async}")
        results["fail"] += 1

    # T7: Timeout handling
    print("\n[T7] Timeout handling (1s timeout vs 3s sleep)...")
    spec_to = {
        "name": "timeout_test",
        "command": "cmd /c ping -n 7 127.0.0.1 > nul",  # ~6 seconds (timeout 1s 가 끊어야)
        "timeout": 1,
        "blocking": False,
        "owner": "test",
    }
    start = time.time()
    code = run_hook("__selftest__", spec_to, "")
    elapsed = time.time() - start
    # 외부배포 (2026-05-31): T7 마진 완화 — 로드된 Windows 의 process teardown 지연(~2.6s)에도
    # timeout(1s) 이 6s 명령을 끊었음을 판별. broken-timeout(~6s)은 여전히 > 3.5 로 FAIL.
    if code == 0 and elapsed < 3.5:
        print(f"  [PASS] timeout enforced ({elapsed:.1f}s), returned 0 (non-blocking)")
        results["pass"] += 1
    else:
        print(f"  [FAIL] elapsed={elapsed:.1f}s code={code}")
        results["fail"] += 1

    # T8: Event-level double-fire lock
    print("\n[T8] Event-level double-fire lock...")
    _ev, _data = "__locktest__", '{"session_id":"selftest","x":1}'
    # 사전 정리 (이전 self-test 잔재 제거 — 결정적 결과 보장)
    try:
        _k = hashlib.sha256((_ev + "\x00" + _data).encode("utf-8", "replace")).hexdigest()[:32]
        _lp = LOCK_DIR / f"{_k}.lock"
        if _lp.exists():
            _lp.unlink()
    except Exception:
        pass
    first = acquire_event_lock(_ev, _data)          # 첫 진입 → True
    second = acquire_event_lock(_ev, _data)         # 즉시 재진입(double-fire) → False
    diff = acquire_event_lock(_ev, '{"session_id":"selftest","x":2}')  # 다른 payload → True
    if first and not second and diff:
        print(f"  [PASS] first={first} second={second} diff_payload={diff}")
        results["pass"] += 1
    else:
        print(f"  [FAIL] first={first} second={second} diff_payload={diff}")
        results["fail"] += 1

    # Summary
    print("\n" + "=" * 60)
    print(f"RESULT: {results['pass']} PASS, {results['fail']} FAIL")
    print("=" * 60)
    sys.exit(0 if results["fail"] == 0 else 1)


# === Main ===
STOP_EVENTS = {"Stop", "SubagentStop"}
# 컨텍스트 주입형 이벤트 — 여러 hook 의 JSON 출력을 단일 객체로 병합해야 함.
# (SessionStart 에 8개 hook 이 각각 JSON/텍스트를 raw concat → 객체 2개+ 가 붙어
#  유효하지 않은 JSON 이 되어 CC 가 파싱 실패 → raw 노출 + hook 신호 유실되던 결함.)
CONTEXT_MERGE_EVENTS = {"SessionStart"}


def merge_context_decisions(decisions: list):
    """여러 SessionStart hook 의 JSON 을 단일 객체로 병합.
    continue 는 하나라도 False 면 False, message/additionalContext 는 concat.
    (merge_stop_decisions 의 SessionStart 판본 — raw concat 으로 JSON 깨지던 결함 방지.)"""
    dicts = [d for d in decisions if isinstance(d, dict)]
    if not dicts:
        return None
    cont = not any(d.get("continue") is False for d in dicts)
    msgs = []
    for d in dicts:
        m = d.get("message") or d.get("systemMessage")
        if not m:
            hso = d.get("hookSpecificOutput")
            if isinstance(hso, dict):
                m = hso.get("additionalContext")
        if m and str(m).strip():
            msgs.append(str(m).strip())
    merged = {"continue": cont}
    if msgs:
        merged["message"] = "\n".join(msgs)
    return merged


def merge_stop_decisions(decisions: list):
    """#5: 여러 Stop hook 의 JSON decision 을 하나로 병합. block 우선.
    (jargon_guard 의 {"decision":"block"} 가 다른 hook JSON 과 raw concat 되어
     깨지던 결함 방지 — best-effort → 신뢰 가능 신호로.)"""
    dicts = [d for d in decisions if isinstance(d, dict)]
    if not dicts:
        return None
    blocks = [d for d in dicts if d.get("decision") == "block"]
    if blocks:
        reasons = " | ".join(
            str(d.get("reason", "")).strip()
            for d in blocks if str(d.get("reason", "")).strip()
        )
        return {"decision": "block", "reason": reasons or "blocked by Stop hook"}
    for d in dicts:
        if "decision" in d or "continue" in d:
            return d
    return dicts[0]


def main():
    if len(sys.argv) < 2:
        sys.exit(SUCCESS)

    arg = sys.argv[1]
    if arg == "--generate-registry":
        generate_registry_from_settings()
        return
    if arg == "--self-test":
        run_self_test()
        return
    if arg in ("--version", "-v"):
        print(f"dispatcher {VERSION}")
        return

    event = arg
    _maybe_bootstrap()  # 외부배포: 신규 PC 첫 이벤트 시 self-bootstrap (작업 PC pristine 아님 → skip)
    stdin_data = ""
    try:
        if not sys.stdin.isatty():
            stdin_data = sys.stdin.read()
    except Exception:
        stdin_data = ""

    # 이벤트당 1회 락: settings.json + plugin hooks.json 두 진입점이 같은 이벤트에
    # 각각 dispatcher 를 spawn 하는 double-fire 차단. 두 번째 프로세스는 여기서 즉시 종료.
    if not acquire_event_lock(event, stdin_data):
        log_event(event, "_dispatcher", "system", 0, 0, "", f"v{VERSION} skipped (double-fire lock)")
        sys.exit(SUCCESS)

    tool_name = ""
    try:
        if stdin_data:
            payload = json.loads(stdin_data)
            tool_name = payload.get("tool_name", "") or payload.get("tool", "")
    except Exception:
        pass

    hooks = scan_registry(event)
    hooks = [h for h in hooks if matches(h, tool_name)]
    log_event(event, "_dispatcher", "system", 0, 0, "", f"v{VERSION} scanned {len(hooks)} hooks tool={tool_name!r}")

    if not hooks:
        sys.exit(SUCCESS)

    # 외부배포 MED-1 (2026-05-31): blocking hook 이 정당하게 BLOCK(2) 을 반환해도, 다른 hook 이
    # 2 보다 큰 코드(예: powershell ENOENT 127)를 내면 옛 max_exit 로직이 BLOCK 을 SUCCESS 로 강등.
    # → "BLOCK 을 낸 hook 이 하나라도 있으면 BLOCK" 으로 변경 (비-2 에러코드가 차단 신호 못 가림).
    # #5: Stop/SubagentStop 은 여러 hook 의 JSON decision 을 모아 병합(block 우선)해
    # 하나만 출력 — raw concat 으로 JSON 이 깨져 block 신호가 유실되던 결함 방지.
    if event in STOP_EVENTS:
        block_seen = False
        decisions = []
        raw_nonjson = []
        for spec in hooks:
            code, out = run_hook(event, spec, stdin_data, collect=True)
            if code == BLOCK:
                block_seen = True
            out = (out or "").strip()
            if not out:
                continue
            try:
                decisions.append(json.loads(out))
            except Exception:
                raw_nonjson.append(out)
        merged = merge_stop_decisions(decisions)
        if merged is not None:
            sys.stdout.write(json.dumps(merged, ensure_ascii=False))
            sys.stdout.flush()
        elif raw_nonjson:
            # 2026-06-04 LEAK FIX (다른 프로젝트 기능 실패 — 예: ebs docker 배포 명령 오염):
            # Stop/SubagentStop 에서 비-decision 일반 텍스트 hook stdout 을 *절대 주입하지 않음*.
            # 비차단 hook(telemetry/cleanup/checklist)이 찍는 count/timeout/status 텍스트가
            # raw concat 되어 stdout 으로 주입 → 모델의 다음 턴/도구 호출을 오염시키던 결함.
            # → 주입 대신 로그만. (정당한 stop 차단 신호는 JSON decision 경로로 위에서 이미 처리됨.)
            log_event(event, "_dispatcher", "system", 0, 0,
                      ("\n".join(raw_nonjson))[:2000],
                      "raw non-JSON Stop stdout suppressed (leak fix 2026-06-04)")
        sys.exit(BLOCK if block_seen else SUCCESS)

    # SessionStart 등 컨텍스트 주입형: Stop 과 동일하게 여러 hook 의 JSON 을 단일 객체로
    # 병합해 한 번만 출력. non-JSON stdout 은 주입하지 않고 로그만 (raw 노출 차단).
    if event in CONTEXT_MERGE_EVENTS:
        block_seen = False
        decisions = []
        raw_nonjson = []
        for spec in hooks:
            code, out = run_hook(event, spec, stdin_data, collect=True)
            if code == BLOCK:
                block_seen = True
            out = (out or "").strip()
            if not out:
                continue
            try:
                decisions.append(json.loads(out))
            except Exception:
                raw_nonjson.append(out)
        merged = merge_context_decisions(decisions)
        if merged is not None:
            sys.stdout.write(json.dumps(merged, ensure_ascii=False))
            sys.stdout.flush()
        if raw_nonjson:
            log_event(event, "_dispatcher", "system", 0, 0,
                      ("\n".join(raw_nonjson))[:2000],
                      "raw non-JSON SessionStart stdout suppressed (merge fix 2026-06-09)")
        sys.exit(BLOCK if block_seen else SUCCESS)

    block_seen = False
    for spec in hooks:
        code = run_hook(event, spec, stdin_data)
        if code == BLOCK:
            block_seen = True

    sys.exit(BLOCK if block_seen else SUCCESS)


if __name__ == "__main__":
    main()

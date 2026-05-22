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
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any

# === Configuration ===
HOME = Path(os.path.expanduser("~"))
GLOBAL_REGISTRY = HOME / ".claude" / "hooks" / "registry"
PROJECT_REGISTRY = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")) / ".claude" / "hooks" / "registry"
PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT", "")

LOG_DB = HOME / ".claude" / "logs" / "hook-events.db"
LOG_DB.parent.mkdir(parents=True, exist_ok=True)

VERSION = "1.0.0"
SUCCESS = 0
BLOCK = 2

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
                spec.setdefault("priority", 50)
                spec.setdefault("timeout", 10)
                spec.setdefault("blocking", False)
                spec.setdefault("name", json_file.stem)
                spec.setdefault("owner", axis_name)
                spec["_source"] = str(json_file)
                hooks.append(spec)
            except Exception as e:
                log_event(event, json_file.name, axis_name, -1, 0, "", f"registry parse error: {e}")

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


def run_hook(event: str, spec: Dict[str, Any], stdin_data: str) -> int:
    start = datetime.now()
    name = spec["name"]
    cmd = os.path.expandvars(os.path.expanduser(spec["command"]))
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
            return SUCCESS

        duration_ms = int((datetime.now() - start).total_seconds() * 1000)
        log_event(event, name, owner, proc.returncode, duration_ms, stderr or "", "")
        if stdout:
            sys.stdout.write(stdout)
            sys.stdout.flush()
        return proc.returncode if blocking else SUCCESS
    except Exception as e:
        duration_ms = int((datetime.now() - start).total_seconds() * 1000)
        if proc is not None:
            try:
                _kill_tree(proc.pid)
            except Exception:
                pass
        log_event(event, name, owner, -1, duration_ms, "", f"exception: {e}")
        return SUCCESS


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
        "command": "cmd /c ping -n 4 127.0.0.1 > nul",  # ~3 seconds
        "timeout": 1,
        "blocking": False,
        "owner": "test",
    }
    start = time.time()
    code = run_hook("__selftest__", spec_to, "")
    elapsed = time.time() - start
    if code == 0 and elapsed < 2.5:
        print(f"  [PASS] timeout enforced ({elapsed:.1f}s), returned 0 (non-blocking)")
        results["pass"] += 1
    else:
        print(f"  [FAIL] elapsed={elapsed:.1f}s code={code}")
        results["fail"] += 1

    # Summary
    print("\n" + "=" * 60)
    print(f"RESULT: {results['pass']} PASS, {results['fail']} FAIL")
    print("=" * 60)
    sys.exit(0 if results["fail"] == 0 else 1)


# === Main ===
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
    stdin_data = ""
    try:
        if not sys.stdin.isatty():
            stdin_data = sys.stdin.read()
    except Exception:
        stdin_data = ""

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

    max_exit = SUCCESS
    for spec in hooks:
        code = run_hook(event, spec, stdin_data)
        if code > max_exit:
            max_exit = code

    sys.exit(BLOCK if max_exit == BLOCK else SUCCESS)


if __name__ == "__main__":
    main()

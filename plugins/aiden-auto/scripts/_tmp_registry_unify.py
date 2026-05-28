"""Iter 2: Project registry 21개 → Global registry 이전 + Project _disabled. P2b 패턴 일관."""
import os
import json
import shutil
from pathlib import Path

USER = Path.home() / ".claude"
PROJ = Path(r"C:\claude\.claude")
GLOBAL_REG = USER / "hooks" / "registry"
PROJ_REG = PROJ / "hooks" / "registry"
DISABLED = PROJ_REG / "_disabled"
DISABLED.mkdir(parents=True, exist_ok=True)

# 21개 — registry-body 분리 (Iter 1 결과)
TARGETS = [
    ("PostToolUse", "circuit_breaker"),
    ("PostToolUse", "context_limit_recovery"),
    ("PostToolUse", "daily_sample_sender"),
    ("PostToolUse", "edit_error_recovery"),
    ("PostToolUse", "edit_slack_reporter"),
    ("PostToolUse", "post_edit_check"),
    ("PostToolUse", "task_completed_trigger"),
    ("PreCompact", "pre_compact_save"),
    ("PreToolUse", "branch_guard"),
    ("PreToolUse", "pre_tool_use_block_node_modules"),
    ("PreToolUse", "tool_validator"),
    ("SessionEnd", "memory_sync"),
    ("SessionEnd", "session_error_recovery"),
    ("SessionEnd", "session_snapshot"),
    ("SessionStart", "agent_validator"),
    ("SessionStart", "session_init"),
    ("Stop", "stop_completion_check"),
    ("SubagentStop", "checklist_updater"),
    ("SubagentStop", "subagent_zombie_detector"),
    ("SubagentStop", "tmpclaude_cleanup"),
]
# 21번째: _disabled/PostToolUse-bidirectional_sync.json 는 이미 Project _disabled 상태 → skip

moved = []
already_global = []
errors = []

for event, name in TARGETS:
    proj_json = PROJ_REG / event / f"{name}.json"
    global_json = GLOBAL_REG / event / f"{name}.json"

    if not proj_json.is_file():
        errors.append(f"Project json 없음: {event}/{name}")
        continue

    # Global 에 이미 존재?
    if global_json.is_file():
        already_global.append(f"{event}/{name} (Global 이미 등록 — Project 만 _disabled)")
    else:
        # Project → Global 이전 (owner: project → global)
        spec = json.loads(proj_json.read_text(encoding="utf-8"))
        spec["owner"] = "global"
        global_json.parent.mkdir(parents=True, exist_ok=True)
        global_json.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        moved.append(f"{event}/{name}")

    # Project 는 _disabled 로 이동 (dispatcher dedup)
    disabled_target = DISABLED / f"{event}-{name}.json"
    shutil.move(str(proj_json), str(disabled_target))

print(f"=== Iter 2 결과 ===")
print(f"이전 (Project → Global): {len(moved)}개")
for m in moved:
    print(f"  + {m}")
print(f"\nGlobal 이미 존재 (Project만 _disabled): {len(already_global)}개")
for m in already_global:
    print(f"  ~ {m}")
print(f"\n에러: {len(errors)}개")
for e in errors:
    print(f"  ! {e}")

# 검증
print("\n--- 검증 ---")
print(f"Global registry 총 hook json: {len(list(GLOBAL_REG.rglob('*.json')))}")
print(f"Project registry 총 hook json (active, _disabled 제외): "
      f"{len([p for p in PROJ_REG.rglob('*.json') if '_disabled' not in str(p)])}")
print(f"Project _disabled: {len(list(DISABLED.glob('*.json')))}")

# Global 측 각 hook 의 .py 존재 확인 (phantom 방지)
print("\n--- Global registry .py 실행체 검증 ---")
bad = 0
for jf in GLOBAL_REG.rglob("*.json"):
    if "_disabled" in str(jf):
        continue
    spec = json.loads(jf.read_text(encoding="utf-8"))
    cmd = os.path.expandvars(spec.get("command", ""))
    parts = cmd.replace('"', "").split()
    script = ""
    for i, p in enumerate(parts):
        if p == "-File" and i + 1 < len(parts):
            script = parts[i + 1]
            break
        if p.endswith((".py", ".mjs", ".ps1")):
            script = p
            break
    if script and not os.path.isfile(script):
        print(f"  PHANTOM: {jf.name} -> {script}")
        bad += 1
print(f"phantom count: {bad}")

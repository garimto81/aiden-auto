"""Iter 4: 5개 P2b doublefire 정정 + scripts 11개 Global 이전 (Universal 흡수)."""
import os
import shutil
from pathlib import Path

USER = Path.home() / ".claude"
PROJ = Path(r"C:\claude\.claude")
sep = chr(92)

# 1. 5개 P2b doublefire — Project registry → _disabled
P2B_TARGETS = [
    ("PostToolUse", "quantification_tracker"),
    ("SessionEnd", "session_cleanup"),
    ("SessionStart", "bootstrap"),
    ("SessionStart", "harness_cycle_runner"),
    ("UserPromptSubmit", "userpromptsubmit-drain"),
]

PROJ_REG = PROJ / "hooks" / "registry"
DISABLED = PROJ_REG / "_disabled"

disabled_count = 0
for event, name in P2B_TARGETS:
    src = PROJ_REG / event / f"{name}.json"
    dst = DISABLED / f"{event}-{name}.json"
    if src.is_file():
        shutil.move(str(src), str(dst))
        disabled_count += 1
        print(f"  + deregister: {event}/{name}")

print(f"\n=== 5개 P2b 정정 완료: {disabled_count}/{len(P2B_TARGETS)} ===\n")

# 2. scripts 11개 + hooks/_python_runner.mjs + hooks/registry/_generate.py 를 Global 로 mirror
# (Project 보존 — 비파괴, sync hook 이 양방향)

# 단 _generate.py 는 hooks/registry 하위라 Global hooks/registry/ 로
SCRIPT_TARGETS = [
    # (Project relative, Global relative)
    ("scripts/load-plugins.py", "scripts/load-plugins.py"),
    ("scripts/command-logger.py", "scripts/command-logger.py"),
    ("scripts/context-monitor.py", "scripts/context-monitor.py"),
    ("scripts/emergency_stop.py", "scripts/emergency_stop.py"),
    ("scripts/screenshot-capture.ps1", "scripts/screenshot-capture.ps1"),
    ("scripts/add-docker-intranet-firewall.ps1", "scripts/add-docker-intranet-firewall.ps1"),
    ("scripts/rollback-docker-intranet-firewall.ps1", "scripts/rollback-docker-intranet-firewall.ps1"),
    ("scripts/analyze-agent-usage.py", "scripts/analyze-agent-usage.py"),
    ("scripts/analyze_agent_usage.py", "scripts/analyze_agent_usage.py"),
    ("hooks/_python_runner.mjs", "hooks/_python_runner.mjs"),
    ("hooks/registry/_generate.py", "hooks/registry/_generate.py"),
]

copied = 0
already = 0
for proj_rel, global_rel in SCRIPT_TARGETS:
    src = PROJ / proj_rel
    dst = USER / global_rel
    if not src.is_file():
        print(f"  ! source missing: {proj_rel}")
        continue
    if dst.is_file():
        already += 1
        print(f"  ~ already in Global: {global_rel}")
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))
        copied += 1
        print(f"  + Global 이전: {global_rel}")

print(f"\n=== scripts/도구 Universal 흡수 완료: {copied} 신규, {already} 기존 ===\n")

# 3. 검증
print("--- 검증 ---")
import sys
sys.path.insert(0, str(USER / "hooks"))
from bidirectional_sync import SYNC_DIRS, is_excluded_path  # type: ignore

# 남은 Project-only (Global 부재) 수
remaining = []
for d in sorted(SYNC_DIRS):
    pdir = PROJ / d
    if not pdir.is_dir():
        continue
    for dirpath, dirnames, filenames in os.walk(pdir, topdown=True):
        dirnames[:] = [dn for dn in dirnames if dn not in {"node_modules", "__pycache__", ".git", "dist", "build"}]
        # _disabled 제외
        if "_disabled" in dirpath.replace(sep, "/"):
            continue
        for fn in filenames:
            sp = Path(dirpath) / fn
            rel = sp.relative_to(PROJ)
            excluded, _ = is_excluded_path(rel)
            if excluded:
                continue
            if not (USER / rel).exists():
                remaining.append(str(rel).replace(sep, "/"))

print(f"남은 Project-only (active): {len(remaining)}개")
for r in remaining:
    print(f"  - {r}")

# Project registry active 수
active_proj_reg = [p for p in PROJ_REG.rglob("*.json") if "_disabled" not in str(p)]
print(f"\nProject registry active: {len(active_proj_reg)}개")
for p in active_proj_reg:
    rel = str(p.relative_to(PROJ_REG)).replace(sep, "/")
    print(f"  - {rel}")
print(f"Project _disabled: {len(list(DISABLED.glob('*.json')))}개")

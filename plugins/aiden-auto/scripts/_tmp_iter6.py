"""Iter 6: N3/N5/N4/N2/H4-residual/H6-residual 자율 정정."""
import os
import json
import hashlib
import shutil
from pathlib import Path

USER = Path.home() / ".claude"
PROJ = Path(r"C:\claude\.claude")
sep = chr(92)


def sha256_file(p: Path) -> str:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    except Exception:
        return "?"


# === N5: _disabled/Notification-notify_voice.json hardcoded → $HOME ===
n5 = PROJ / "hooks" / "registry" / "_disabled" / "Notification-notify_voice.json"
if n5.is_file():
    raw = n5.read_text(encoding="utf-8")
    if "C:/claude/.claude" in raw:
        new = raw.replace("C:/claude/.claude/hooks/notify_voice.py", "$HOME/.claude/hooks/notify_voice.py")
        # owner 도 disabled 상태에 맞게
        n5.write_text(new, encoding="utf-8")
        print("  N5: notify_voice _disabled command → $HOME 정정")

# === N4: _disabled 28 json 의 owner 일관 정정 (project → archived) ===
n4_count = 0
disabled_dir = PROJ / "hooks" / "registry" / "_disabled"
for jf in disabled_dir.glob("*.json"):
    try:
        spec = json.loads(jf.read_text(encoding="utf-8"))
        if spec.get("owner") == "project":
            spec["owner"] = "archived"
            # 보존 의미 명시
            if "comment" not in spec:
                spec["comment"] = "deregistered mirror (Global registry 정본) — Plan B 양방향 doublefire 방지"
            jf.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            n4_count += 1
    except Exception as e:
        print(f"  N4 error {jf.name}: {e}")
print(f"  N4: _disabled owner 'project' → 'archived' {n4_count}개")

# === N2: notify_voice.py 양쪽 SHA256 비교 ===
g = USER / "hooks" / "notify_voice.py"
p = PROJ / "hooks" / "notify_voice.py"
g_sha = sha256_file(g)
p_sha = sha256_file(p)
print(f"  N2: notify_voice.py SHA")
print(f"      Global  : {g_sha}")
print(f"      Project : {p_sha}")
print(f"      {'✓ 일치 (mirror 정상)' if g_sha == p_sha else '✗ DRIFT (즉시 bidirectional sync 필요)'}")

# === H4-residual: _tmp_project_registry_r3.py 정리 ===
for tmp_path in [
    USER / "scripts" / "_tmp_project_registry_r3.py",
    PROJ / "scripts" / "_tmp_project_registry_r3.py",
]:
    if tmp_path.is_file():
        tmp_path.unlink()
        print(f"  H4-residual: rm {tmp_path}")

# === 최종 실측 ===
print("\n--- 최종 실측 ---")
# Active 38 hardcoded 재확인
active_hardcoded = 0
for jf in (USER / "hooks" / "registry").rglob("*.json"):
    if "_disabled" in str(jf):
        continue
    if "C:/Users/AidenKim" in jf.read_text(encoding="utf-8"):
        active_hardcoded += 1
print(f"Global active registry hardcoded path 잔여: {active_hardcoded}")

# _disabled 28 hardcoded 재확인
disabled_hardcoded = 0
for jf in disabled_dir.glob("*.json"):
    if "C:/Users/AidenKim" in jf.read_text(encoding="utf-8") or "C:/claude/.claude" in jf.read_text(encoding="utf-8"):
        disabled_hardcoded += 1
print(f"Project _disabled hardcoded path 잔여: {disabled_hardcoded}")

# Project-only active
import sys
sys.path.insert(0, str(USER / "hooks"))
from bidirectional_sync import SYNC_DIRS, is_excluded_path  # type: ignore
remaining = []
for d in sorted(SYNC_DIRS):
    pdir = PROJ / d
    if not pdir.is_dir():
        continue
    for dirpath, dirnames, filenames in os.walk(pdir, topdown=True):
        dirnames[:] = [dn for dn in dirnames if dn not in {"node_modules", "__pycache__", ".git", "dist", "build"}]
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
print(f"Project-only active: {len(remaining)}")
for r in remaining:
    print(f"  - {r}")

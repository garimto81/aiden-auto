"""33개 Project-only 자산 1개씩 실측 분류. critic 권고 #5 적용."""
import os
import json
import glob
from pathlib import Path

USER = Path.home() / ".claude"
PROJ = Path(r"C:\claude\.claude")
sep = chr(92)

# 33개 자산 목록 (직전 turn 실측)
import sys
sys.path.insert(0, str(USER / "hooks"))
from bidirectional_sync import SYNC_DIRS, is_excluded_path  # type: ignore

proj_only = []
for d in sorted(SYNC_DIRS):
    pdir = PROJ / d
    if not pdir.is_dir():
        continue
    for dirpath, dirnames, filenames in os.walk(pdir, topdown=True):
        dirnames[:] = [dn for dn in dirnames if dn not in {"node_modules", "__pycache__", ".git", "dist", "build"}]
        for fn in filenames:
            sp = Path(dirpath) / fn
            rel = sp.relative_to(PROJ)
            excluded, _ = is_excluded_path(rel)
            if excluded:
                continue
            if not (USER / rel).exists():
                proj_only.append((sp, rel))

print(f"=== 총 {len(proj_only)}개 자산 1개씩 실측 분류 ===\n")

# 각 자산 분류
classifications = {
    "registry-body 분리 (Universal 흡수 가능)": [],
    "project-only 실제 (Global 부재 확정)": [],
    "phantom (실행체 어디에도 없음)": [],
    "registry 항목 (실측 필요)": [],
    "scripts/도구 (분류 필요)": [],
}

for sp, rel in proj_only:
    rel_str = str(rel).replace(sep, "/")

    # registry JSON?
    if rel_str.startswith("hooks/registry/") and rel_str.endswith(".json"):
        # command 의 .py 가 어디 있나?
        try:
            spec = json.load(open(sp, encoding="utf-8"))
            cmd = spec.get("command", "")
            exp = os.path.expandvars(cmd)
            # 스크립트 경로 추출
            script = ""
            parts = exp.replace('"', "").split()
            for i, p in enumerate(parts):
                if p == "-File" and i + 1 < len(parts):
                    script = parts[i + 1]
                    break
                if p.endswith((".py", ".mjs", ".ps1", ".cjs", ".js")):
                    script = p
                    break
            # script 의 위치
            if script:
                script_path = Path(script)
                if script_path.is_file():
                    # 실행체 존재
                    script_rel = str(script_path).replace(str(USER) + sep, "").replace(sep, "/")
                    if str(USER) in str(script_path):
                        classifications["registry-body 분리 (Universal 흡수 가능)"].append(
                            f"{rel_str} -> Global:{script_rel}"
                        )
                    else:
                        classifications["registry 항목 (실측 필요)"].append(f"{rel_str} -> {script}")
                else:
                    # 실행체 부재 — 다른 위치 search
                    fname = script_path.name
                    fallback = []
                    for root in [USER, PROJ, Path(r"C:\claude\plugins\aiden-auto")]:
                        if root.exists():
                            for found in root.rglob(fname):
                                if "__pycache__" not in str(found) and "node_modules" not in str(found):
                                    fallback.append(str(found))
                                    break
                    if fallback:
                        classifications["registry-body 분리 (Universal 흡수 가능)"].append(
                            f"{rel_str} -> fallback:{fallback[0]}"
                        )
                    else:
                        classifications["phantom (실행체 어디에도 없음)"].append(
                            f"{rel_str} -> MISSING:{script}"
                        )
            else:
                classifications["registry 항목 (실측 필요)"].append(f"{rel_str} (no script in cmd)")
        except Exception as e:
            classifications["registry 항목 (실측 필요)"].append(f"{rel_str} (parse error: {e})")
    elif rel_str.startswith("scripts/"):
        # script 본문 첫 줄 docstring
        try:
            with open(sp, encoding="utf-8", errors="replace") as f:
                head = ""
                for line in f.readlines()[:10]:
                    s = line.strip()
                    if s and not s.startswith("#!") and not s.startswith('"""') and not s.startswith("//"):
                        head = s[:80]
                        break
                    if s.startswith('"""') and len(s) > 3:
                        head = s[3:].strip()[:80]
                        break
            classifications["scripts/도구 (분류 필요)"].append(f"{rel_str} :: {head}")
        except Exception as e:
            classifications["scripts/도구 (분류 필요)"].append(f"{rel_str} (read error)")
    else:
        # hooks/_other
        classifications["scripts/도구 (분류 필요)"].append(f"{rel_str} (non-registry)")

# 출력
for cat, items in classifications.items():
    print(f"--- [{cat}] {len(items)}개 ---")
    for it in items:
        print(f"  {it}")
    print()

# 요약
total = sum(len(v) for v in classifications.values())
print(f"=== 분류 요약: {total}개 ===")
for cat, items in classifications.items():
    print(f"  {cat}: {len(items)}")

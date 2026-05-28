"""One-shot generator: Project settings.json wrapper hooks → registry JSON.

Reads C:/claude/.claude/settings.json.bak.silent-wrap-removal, strips _silent_wrap.cmd
wrapper from each command, derives a hook name, and writes a dispatcher-compatible
registry JSON file under C:/claude/.claude/hooks/registry/{event}/.

This removes the wrapper layer entirely — dispatcher.py handles execution natively
with subprocess.Popen, stderr captured into hook-events.db, no shell expansion quirks.
"""

import json
from pathlib import Path

SOURCE = Path(r"C:\claude\.claude\settings.json.bak.silent-wrap-removal")
REGISTRY_ROOT = Path(r"C:\claude\.claude\hooks\registry")
WRAPPER_TOKEN = "_silent_wrap.cmd "


def strip_wrapper(cmd: str) -> str:
    if WRAPPER_TOKEN in cmd:
        return cmd.split(WRAPPER_TOKEN, 1)[1].strip()
    return cmd.strip()


def derive_name(cmd: str, event: str) -> str:
    base = strip_wrapper(cmd)
    for token in base.split():
        clean = token.strip('"').strip("'")
        if (
            "/" in clean
            or "\\" in clean
            or clean.endswith((".py", ".mjs", ".js", ".sh", ".ps1", ".cmd", ".bat"))
        ):
            return Path(clean).stem
    return f"{event}-unnamed"


def main():
    settings = json.loads(SOURCE.read_text(encoding="utf-8"))
    hooks_section = settings.get("hooks", {})
    written = []
    seen = {}

    for event, groups in hooks_section.items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            matcher = group.get("matcher", "")
            for hook_def in group.get("hooks", []):
                raw_cmd = hook_def.get("command", "")
                if not raw_cmd:
                    continue
                cmd = strip_wrapper(raw_cmd)
                name = derive_name(raw_cmd, event)
                key = f"{event}/{name}"
                if key in seen:
                    seen[key] += 1
                    name = f"{name}-{seen[key]}"
                else:
                    seen[key] = 1

                is_async = hook_def.get("async", False)
                timeout = hook_def.get("timeout", 10)

                spec = {
                    "name": name,
                    "command": cmd,
                    "timeout": timeout,
                    "blocking": not is_async,
                    "priority": 50,
                    "owner": "project",
                }
                if matcher:
                    spec["matcher"] = matcher

                target_dir = REGISTRY_ROOT / event
                target_dir.mkdir(parents=True, exist_ok=True)
                target_file = target_dir / f"{name}.json"
                target_file.write_text(
                    json.dumps(spec, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                written.append(f"  [{event}] {name}")

    print(f"Wrote {len(written)} registry specs under {REGISTRY_ROOT}\n")
    for line in written:
        print(line)


if __name__ == "__main__":
    main()

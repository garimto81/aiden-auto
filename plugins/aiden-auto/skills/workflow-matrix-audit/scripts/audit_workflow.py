"""
workflow-matrix-audit: settings.json hooks 전수 검증
exit 0 = all OK / exit 1 = PHANTOM_HOOK 발견
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SETTINGS_CANDIDATES = [
    Path("C:/claude/.claude/settings.json"),
    Path("C:/claude/.claude/settings.local.json"),
    Path.home() / ".claude" / "settings.json",
    Path.home() / ".claude" / "settings.local.json",
]
OUTPUT_PATH = Path("C:/claude/.claude/state/workflow-matrix-mapping.json")


def extract_file_path(command: str) -> str | None:
    """command 문자열에서 실제 파일 경로를 추출 (Windows + POSIX + PowerShell 지원).

    Cycle 9 LOW-12: Linux/macOS 경로(`/home/user/...`) 도 추출.
    Cycle 2 audit-loop critic FN-HIGH: PowerShell `-File "..."` 패턴 추출.
    """
    # python C:/... 또는 node C:/... (Windows)
    m = re.search(r"(?:python|node)\s+(C:[^\s]+)", command)
    if m:
        return m.group(1)
    # python /path/... 또는 node /path/... (POSIX, quoted 경로 포함)
    m = re.search(r'(?:python|node)\s+["\']?(/[^\s"\']+)', command)
    if m:
        return m.group(1)
    # quoted Windows 경로
    m = re.search(r'(?:python|node)\s+["\'](C:[^"\']+)["\']', command)
    if m:
        return m.group(1)
    # PowerShell -File "..." (quoted)
    m = re.search(r'-File\s+["\']([^"\']+)["\']', command)
    if m:
        return m.group(1)
    # PowerShell -File ... (unquoted, single token)
    m = re.search(r'-File\s+(\S+)', command)
    if m:
        return m.group(1)
    return None


def audit() -> dict:
    results = []
    # (source, event) -> [commands]: 같은 settings.json + event 안의 중복만 진짜 DUP
    seen_in_source: dict[tuple, list[str]] = {}
    # event -> [(source, command)]: cross-settings 잉여 탐지용
    seen_cross: dict[str, list[tuple]] = {}

    for settings_path in SETTINGS_CANDIDATES:
        if not settings_path.is_file():
            continue
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # 손상된 settings.json 은 안전하게 skip (critic HIGH-3 대응)
            continue
        hooks_section = settings.get("hooks", {})
        source = settings_path.as_posix()

        for event, groups in hooks_section.items():
            for group in groups:
                matcher = group.get("matcher", "")
                for hook in group.get("hooks", []):
                    if hook.get("type") != "command":
                        continue
                    command = hook.get("command", "")
                    is_async = hook.get("async", False)
                    file_path_raw = extract_file_path(command)
                    file_path = Path(file_path_raw).as_posix() if file_path_raw else None
                    file_exists = Path(file_path).is_file() if file_path else False

                    # 같은 source + event 안의 진짜 중복 (정리 필요)
                    same_source_key = (source, event)
                    seen_in_source.setdefault(same_source_key, [])
                    is_same_source_dup = command in seen_in_source[same_source_key]
                    seen_in_source[same_source_key].append(command)

                    # cross-settings 등록 (다른 settings.json에서 같은 cmd) - 의도된 fallback 일 수 있음
                    seen_cross.setdefault(event, [])
                    is_cross_dup = any(s != source and c == command for s, c in seen_cross[event])
                    seen_cross[event].append((source, command))

                    if is_same_source_dup:
                        status = "DUPLICATE_REGISTRATION"
                    elif file_path and not file_exists:
                        status = "PHANTOM_HOOK"
                    elif is_cross_dup:
                        status = "CROSS_SETTINGS_REDUNDANCY"
                    else:
                        status = "OK"

                    results.append({
                        "event": event,
                        "matcher": matcher,
                        "command": command,
                        "file_path": file_path,
                        "file_exists": file_exists,
                        "async": is_async,
                        "status": status,
                        "source": source,
                    })

    summary: dict[str, int] = {}
    for r in results:
        summary[r["status"]] = summary.get(r["status"], 0) + 1

    events_used = sorted(set(r["event"] for r in results))

    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "total_registered": len(results),
        "events_used": events_used,
        "summary": summary,
        "results": results,
    }


def print_report(data: dict) -> None:
    print(f"\n=== Workflow Matrix Audit  {data['ts']} ===")
    print(f"Total registered hooks : {data['total_registered']}")
    print(f"Events used            : {', '.join(data['events_used'])}")
    print(f"Summary                : {data['summary']}\n")

    col = {"OK": "OK", "PHANTOM_HOOK": "PHANTOM",
           "DUPLICATE_REGISTRATION": "DUP",
           "CROSS_SETTINGS_REDUNDANCY": "X-RED"}
    for r in data["results"]:
        tag = col.get(r["status"], r["status"])
        flag = "[ASYNC]" if r["async"] else "      "
        print(f"  [{tag:<7}] {flag} {r['event']:<15} matcher={r['matcher']!r:<20} {r['command']}")
    print()


def auto_repair(data: dict, dry_run: bool = False) -> dict:
    """PHANTOM_HOOK 과 DUPLICATE_REGISTRATION 을 settings.json 에서 자동 제거.

    dry_run=True 이면 실제 파일 수정 없이 제거 예정 목록만 반환.
    반환값: {"removed": [...], "skipped": [...], "dry_run": bool}
    """
    removed: list[dict] = []
    skipped: list[dict] = []

    # settings 파일별로 수정이 필요한 항목 수집
    bad_results = [
        r for r in data["results"]
        if r["status"] in ("PHANTOM_HOOK", "DUPLICATE_REGISTRATION")
    ]
    if not bad_results:
        return {"removed": [], "skipped": [], "dry_run": dry_run}

    # source → bad commands 매핑
    bad_by_source: dict[str, set[str]] = {}
    for r in bad_results:
        bad_by_source.setdefault(r["source"], set()).add(r["command"])

    for settings_posix, bad_commands in bad_by_source.items():
        settings_path = Path(settings_posix)
        if not settings_path.is_file():
            for cmd in bad_commands:
                skipped.append({"source": settings_posix, "command": cmd, "reason": "settings file not found"})
            continue

        try:
            original_text = settings_path.read_text(encoding="utf-8")
            settings = json.loads(original_text)
        except (json.JSONDecodeError, OSError) as e:
            for cmd in bad_commands:
                skipped.append({"source": settings_posix, "command": cmd, "reason": f"parse error: {e}"})
            continue

        hooks_section = settings.get("hooks", {})
        changed = False

        for event, groups in hooks_section.items():
            seen_in_event: set[str] = set()
            for group in groups:
                new_hooks: list[dict] = []
                for hook in group.get("hooks", []):
                    if hook.get("type") != "command":
                        new_hooks.append(hook)
                        continue
                    cmd = hook.get("command", "")
                    # PHANTOM_HOOK 또는 DUPLICATE_REGISTRATION 에 해당하는지 확인
                    should_remove = cmd in bad_commands
                    # DUPLICATE_REGISTRATION: 이미 같은 event에서 본 명령어
                    is_dup_in_event = cmd in seen_in_event
                    if should_remove or is_dup_in_event:
                        status = "DUPLICATE_REGISTRATION" if is_dup_in_event else "PHANTOM_HOOK"
                        if dry_run:
                            skipped.append({
                                "source": settings_posix, "event": event,
                                "command": cmd, "reason": f"dry_run: would remove ({status})"
                            })
                        else:
                            removed.append({
                                "source": settings_posix, "event": event,
                                "command": cmd, "status": status
                            })
                            changed = True
                    else:
                        new_hooks.append(hook)
                        seen_in_event.add(cmd)
                group["hooks"] = new_hooks

        if changed and not dry_run:
            new_text = json.dumps(settings, indent=2, ensure_ascii=False)
            settings_path.write_text(new_text, encoding="utf-8")
            print(f"  [REPAIRED] {settings_posix} — {len(bad_commands)} hook(s) removed")

    return {"removed": removed, "skipped": skipped, "dry_run": dry_run}


def print_repair_report(repair: dict) -> None:
    if repair["dry_run"]:
        print("\n=== Auto-Repair (DRY RUN — no files modified) ===")
    else:
        print("\n=== Auto-Repair Result ===")
    if repair["removed"]:
        print(f"Removed ({len(repair['removed'])}):")
        for item in repair["removed"]:
            print(f"  [{item['status']}] {item['event']} — {item['command']}")
    if repair["skipped"]:
        print(f"Skipped ({len(repair['skipped'])}):")
        for item in repair["skipped"]:
            print(f"  [SKIP] {item.get('event','?')} — {item['command']} ({item['reason']})")
    if not repair["removed"] and not repair["skipped"]:
        print("  (nothing to repair)")
    print()


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="workflow-matrix-audit: hook 무결성 검증 + auto-repair")
    parser.add_argument("--repair", action="store_true",
                        help="PHANTOM_HOOK / DUPLICATE_REGISTRATION 자동 제거 (settings.json 직접 수정)")
    parser.add_argument("--dry-run", action="store_true",
                        help="--repair 와 함께 사용: 실제 수정 없이 제거 예정 목록만 출력")
    args = parser.parse_args()

    data = audit()
    print_report(data)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"JSON saved -> {OUTPUT_PATH}")

    phantom_count = data["summary"].get("PHANTOM_HOOK", 0)
    real_dup = data["summary"].get("DUPLICATE_REGISTRATION", 0)
    has_issues = phantom_count > 0 or real_dup > 0

    if has_issues and (args.repair or args.dry_run):
        dry_run = args.dry_run and not args.repair  # --repair 단독이면 실제 수정
        if args.repair and args.dry_run:
            dry_run = True  # 둘 다 지정 시 dry_run 우선 (안전)
        repair = auto_repair(data, dry_run=dry_run)
        print_repair_report(repair)
        if repair["removed"]:
            # 수정 후 재검증
            data2 = audit()
            OUTPUT_PATH.write_text(json.dumps(data2, indent=2, ensure_ascii=False), encoding="utf-8")
            print("Re-audit after repair:")
            print_report(data2)
            phantom_count = data2["summary"].get("PHANTOM_HOOK", 0)
            real_dup2 = data2["summary"].get("DUPLICATE_REGISTRATION", 0)
            return 1 if (phantom_count > 0 or real_dup2 > 0) else 0
    elif has_issues:
        print(f"Issues found: PHANTOM_HOOK={phantom_count}, DUPLICATE_REGISTRATION={real_dup}")
        print("Re-run with --repair to auto-fix, or --dry-run to preview changes.")

    # CROSS_SETTINGS_REDUNDANCY 는 의도된 fallback 가능성 (idempotent hook) — issue 아님
    return 1 if has_issues else 0


if __name__ == "__main__":
    sys.exit(main())

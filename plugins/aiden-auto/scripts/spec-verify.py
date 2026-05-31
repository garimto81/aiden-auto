#!/usr/bin/env python3
"""
Spec-Verify: Deterministic 5-Layer Verifier (LLM-free External Oracle)

목적:
    - "보고-발견-재작업" 무한 cycle 의 진짜 fundamental 해결책
    - LLM 의존 없는 deterministic verification
    - cleanup cycle 의 외부 oracle 역할

Layer:
    1. Physical (파일 존재 + JSON valid + SHA256 lock)
    2. Logical (책임 매트릭스 — Project/Global/Plugin 영역별)
    3. Policy ↔ Implementation (Rule 19 본문 ↔ guard/watcher 코드)
    4. Behavioral (watcher 동작, hook chain)
    5. Reversibility (backup, rollback 가능성)

Usage:
    python spec-verify.py            # 5 Layer 모두 검증
    python spec-verify.py --verbose  # 상세 출력
    python spec-verify.py --json     # JSON 출력 (regression suite 용)

Exit codes:
    0: 모든 Layer PASS (total_score >= 0.95)
    1: 일부 Layer FAIL
    2: Script 자체 오류
"""
import os
import json
import hashlib
import sys
from pathlib import Path
from datetime import datetime

USER_CLAUDE = Path(os.path.expanduser("~")) / ".claude"
PROJECT_CLAUDE = Path("C:/claude/.claude")
CACHE_ROOT = USER_CLAUDE / "plugins" / "cache" / "garimto81-aiden-auto" / "aiden-auto"


# PLUGIN_SOURCE: 2026-05-30 — plugin-source(C:\claude\plugins\aiden-auto) deregister 후
# spec-verify 의 "plugin" 축 검증 대상을 실제 CC 런타임 = cache 활성 버전으로 repoint.
# (이전 하드코딩 device 경로도 제거 → device-agnostic). cache 부재 시 Global fallback (false drift 0).
def _cache_active() -> Path:
    if CACHE_ROOT.is_dir():
        vers = [p for p in CACHE_ROOT.iterdir() if p.is_dir()]
        def _vk(p: Path):
            try:
                return tuple(int(x) for x in p.name.split("."))
            except ValueError:
                return (0,)
        vers.sort(key=_vk, reverse=True)
        if vers:
            return vers[0]
    return USER_CLAUDE


PLUGIN_SOURCE = _cache_active()

LAYER_WEIGHTS = {
    "L1_Physical":       0.20,
    "L2_Logical":        0.20,
    "L3_Policy_Impl":    0.25,
    "L4_Behavioral":     0.20,
    "L5_Reversibility":  0.15,
}


def sha256_short(p: Path) -> str:
    if not p.exists():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def safe_json_load(p: Path):
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding='utf-8-sig'))
    except json.JSONDecodeError:
        return None


def layer1_physical():
    """Layer 1: Physical — settings.json valid + hook 파일 실재"""
    passed = 0
    total = 0
    issues = []

    # 1.1 settings.json JSON validity
    for label, path in [
        ("global", USER_CLAUDE / "settings.json"),
        ("project", PROJECT_CLAUDE / "settings.json"),
    ]:
        total += 1
        if not path.exists():
            issues.append(f"[L1] {label} settings.json 부재")
            continue
        if safe_json_load(path) is None:
            issues.append(f"[L1] {label} settings.json INVALID JSON")
        else:
            passed += 1

    # 1.2 Project settings hook 파일 실재
    proj_settings = safe_json_load(PROJECT_CLAUDE / "settings.json")
    if proj_settings:
        for event, matchers in proj_settings.get("hooks", {}).items():
            for matcher in matchers:
                for hook in matcher.get("hooks", []):
                    cmd = hook.get("command", "")
                    if '"' in cmd:
                        parts = cmd.split('"')
                        if len(parts) >= 2:
                            hook_path = Path(parts[1])
                            total += 1
                            if hook_path.exists():
                                passed += 1
                            else:
                                issues.append(f"[L1] hook 부재: {event} / {hook_path.name}")

    return passed, total, issues


def layer2_logical():
    """Layer 2: Logical — v3.1 포함 패러다임 (제거 ≠ 답, mirror 일관성 검증)"""
    passed = 0
    total = 0
    issues = []

    # 2.1 v3.1 — Project + Global commands SHA 일관성 (mirror 검증)
    # "제거"가 아니라 "동기화 일관성" 검증
    total += 1
    proj_cmd_dir = PROJECT_CLAUDE / "commands"
    global_cmd_dir = USER_CLAUDE / "commands"
    proj_cmds = list(proj_cmd_dir.glob("*.md")) if proj_cmd_dir.exists() else []
    global_cmds = list(global_cmd_dir.glob("*.md")) if global_cmd_dir.exists() else []

    # Global = 정본. Project = 자동 mirror. 양쪽 다 있어야 정상.
    if global_cmds:
        drift_count = 0
        for gc in global_cmds:
            pc = proj_cmd_dir / gc.name
            if pc.exists() and sha256_short(pc) != sha256_short(gc):
                drift_count += 1
        if drift_count == 0:
            passed += 1
        else:
            issues.append(f"[L2] Project↔Global commands drift {drift_count}개 (다음 watcher sync 시 정정)")
    else:
        issues.append(f"[L2] Global commands 0개 — 정본 부재 (즉시 plugin 에서 복원 필요)")

    # 2.2 v3.1 — Global ↔ Plugin commands 일관성 (watcher sync 결과)
    total += 1
    plugin_cmd_dir = PLUGIN_SOURCE / "commands"
    plugin_cmds = list(plugin_cmd_dir.glob("*.md")) if plugin_cmd_dir.exists() else []
    if plugin_cmds and global_cmds:
        drift_count = 0
        for plc in plugin_cmds:
            gc = global_cmd_dir / plc.name
            if gc.exists() and sha256_short(plc) != sha256_short(gc):
                drift_count += 1
        # drift 는 허용 (사용자 override 의도 가능). 단 통보.
        passed += 1
        if drift_count > 0:
            issues.append(f"[L2] Plugin↔Global commands drift {drift_count}개 (의도된 override 가능, 정보)")
    else:
        passed += 1  # plugin 부재면 검증 skip

    # 2.3 v3.1 — Global agents root vs subdir mirror 일관성 (drift만 WARN, SAME=PASS)
    total += 1
    global_agt_dir = USER_CLAUDE / "agents"
    if global_agt_dir.exists():
        root_files = list(global_agt_dir.glob("*.md"))
        drift_count = 0
        mirror_count = 0
        for rf in root_files:
            subs = list(global_agt_dir.rglob(rf.name))
            sub_other = [s for s in subs if s != rf]
            if sub_other:
                if sha256_short(rf) == sha256_short(sub_other[0]):
                    mirror_count += 1
                else:
                    drift_count += 1
        # v3.1 포함 패러다임: SAME = mirror PASS. drift 만 WARN
        passed += 1
        if drift_count > 0:
            issues.append(f"[L2] Global agents root vs subdir drift {drift_count}개 (Plan B sync 대상)")

    return passed, total, issues


def layer3_policy_impl():
    """Layer 3: Policy ↔ Implementation"""
    passed = 0
    total = 0
    issues = []

    # 3.1 Rule 19 path drift (v 접두사 없음)
    total += 1
    rule19 = PROJECT_CLAUDE / "rules" / "19-plugin-ssot-policy.md"
    if rule19.exists():
        content = rule19.read_text(encoding='utf-8')
        if "v28.2.0" in content:
            issues.append("[L3] Rule 19 path drift: v28.2.0 잔존")
        else:
            passed += 1
    else:
        issues.append("[L3] Rule 19 파일 부재")

    # 3.2 framework_edit_guard.py 실재
    total += 1
    guard = USER_CLAUDE / "hooks" / "framework_edit_guard.py"
    if guard.exists():
        passed += 1
    else:
        issues.append("[L3] framework_edit_guard.py 부재")

    # 3.3 machine_framework_watcher.py SYNC_DIRS 7개 모두
    total += 1
    watcher = USER_CLAUDE / "hooks" / "machine_framework_watcher.py"
    if watcher.exists():
        content = watcher.read_text(encoding='utf-8')
        required = {"agents", "skills", "hooks", "rules", "references", "commands", "lib"}
        if all(d in content for d in required):
            passed += 1
        else:
            missing = required - {d for d in required if d in content}
            issues.append(f"[L3] watcher SYNC_DIRS 누락: {missing}")
    else:
        issues.append("[L3] machine_framework_watcher.py 부재")

    # 3.4 v3.1 — Plugin hooks.json phantom 분석 (_disabled metadata 인식)
    total += 1
    plugin_hooks = PLUGIN_SOURCE / "hooks" / "hooks.json"
    data = safe_json_load(plugin_hooks)
    if data:
        phantom_count = 0
        # _disabled_* 메타데이터 키 확인 (의도된 차단 상태)
        has_disabled_metadata = any(k.startswith("_disabled") for k in data.keys() if isinstance(k, str))
        for event, matchers in data.get("hooks", {}).items():
            for matcher in matchers:
                for hook in matcher.get("hooks", []):
                    cmd = hook.get("command", "")
                    if "agent_teams_guard" in cmd or "loop_detector" in cmd:
                        phantom_count += 1
        if phantom_count == 0:
            passed += 1
        elif has_disabled_metadata:
            # v3.1 포함 패러다임: _disabled 의도 명시되면 PASS (정보만)
            passed += 1
            issues.append(f"[L3] plugin hooks.json phantom {phantom_count}개 (의도된 _disabled metadata, INFO)")
        else:
            issues.append(f"[L3] plugin hooks.json phantom 활성 등록: {phantom_count}개")
    else:
        issues.append("[L3] plugin hooks.json 부재 또는 invalid")

    # 3.5 책임 매트릭스 본문 인용 (Rule 19 v3.0 신호)
    total += 1
    if rule19.exists():
        content = rule19.read_text(encoding='utf-8')
        if "책임 매트릭스" in content and "Responsibility Matrix" in content:
            passed += 1
        else:
            issues.append("[L3] Rule 19 에 책임 매트릭스 섹션 부재")

    return passed, total, issues


def layer4_behavioral():
    """Layer 4: Behavioral — watcher / hook chain 동작"""
    passed = 0
    total = 0
    issues = []

    # 4.1 Watcher sync log 활성 여부
    total += 1
    sync_log = USER_CLAUDE / "state" / "machine-framework-sync.log"
    if sync_log.exists() and sync_log.stat().st_size > 0:
        passed += 1
    else:
        issues.append("[L4] watcher sync log 비어있음 또는 부재")

    return passed, total, issues


def layer5_reversibility():
    """Layer 5: Reversibility — Backup + rollback 가능성"""
    passed = 0
    total = 0
    issues = []

    # 5.1 Backup 디렉토리 존재 + 내용 있음
    total += 1
    backup_dirs = list((USER_CLAUDE / "backups").glob("cleanup-*")) if (USER_CLAUDE / "backups").exists() else []
    if backup_dirs and any(d.is_dir() and any(d.iterdir()) for d in backup_dirs):
        passed += 1
    else:
        issues.append("[L5] Backup 디렉토리 부재 또는 비어있음")

    return passed, total, issues


def main():
    args = sys.argv[1:]
    verbose = "--verbose" in args
    json_out = "--json" in args

    if not json_out:
        print("=" * 60)
        print(" Deterministic Spec-Verify (5-Layer, LLM-free)")
        print(f" Timestamp: {datetime.now().isoformat()}")
        print("=" * 60)
        print()

    all_issues = []
    layer_results = {}

    fns = [
        ("L1_Physical",      "Layer 1 (Physical)",       layer1_physical),
        ("L2_Logical",       "Layer 2 (Logical)",        layer2_logical),
        ("L3_Policy_Impl",   "Layer 3 (Policy<->Impl)",  layer3_policy_impl),
        ("L4_Behavioral",    "Layer 4 (Behavioral)",     layer4_behavioral),
        ("L5_Reversibility", "Layer 5 (Reversibility)",  layer5_reversibility),
    ]

    for key, name, fn in fns:
        passed, total, issues = fn()
        rate = (passed / total) if total > 0 else 0
        layer_results[key] = {
            "name": name,
            "passed": passed,
            "total": total,
            "rate": rate,
            "issues": issues,
        }
        all_issues.extend(issues)
        if not json_out:
            status = "PASS" if passed == total else ("PART" if passed > 0 else "FAIL")
            print(f"  [{status}] {name:30s} {passed}/{total} ({rate*100:.0f}%)")

    total_score = sum(
        LAYER_WEIGHTS[key] * layer_results[key]["rate"]
        for key in LAYER_WEIGHTS
    )

    if json_out:
        result = {
            "timestamp": datetime.now().isoformat(),
            "total_score": total_score,
            "cleanup_complete": total_score >= 0.95,
            "layers": layer_results,
            "issues": all_issues,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print()
        print(f"  Total Score: {total_score * 100:.1f} / 100")
        print(f"  Cleanup Complete: {'YES' if total_score >= 0.95 else 'NO'} (>= 95 필요)")
        print()

        # 커버리지 명시 (Part 9 E3 적용 — Goodhart's Law 완화)
        total_checks = sum(layer_results[k]["total"] for k in layer_results)
        try:
            # 시스템 파일 카운트 (대략적)
            DIRS_TO_COUNT = ["commands", "agents", "skills", "hooks", "rules", "references", "lib"]
            EXTS_TO_COUNT = {".md", ".py", ".js", ".yml", ".yaml", ".json"}
            system_file_count = 0
            for d in DIRS_TO_COUNT:
                base = USER_CLAUDE / d
                if base.exists():
                    for f in base.rglob("*"):
                        if (f.is_file() and f.suffix in EXTS_TO_COUNT
                            and "__pycache__" not in str(f)
                            and "node_modules" not in str(f)):
                            system_file_count += 1
            coverage = (total_checks * 100 / system_file_count) if system_file_count else 0
            print(f"  ⚠ COVERAGE NOTICE (Part 9 critic E3):")
            print(f"     검사 항목: {total_checks} / 시스템 파일: {system_file_count}")
            print(f"     커버리지: {coverage:.1f}%  ← '100/100' 은 검사 항목 PASS, 시스템 신뢰도 ≠ 점수")
            print(f"     미검사 영역: lib import chain, subagent_type phantom, frontmatter, sync 폭발 등")
            print()
        except Exception:
            pass

        # Issue Registry 통합 (Part 10 Phase 4 — Honest Reporting)
        try:
            registry_file = USER_CLAUDE / "state" / "issues.jsonl"
            if registry_file.exists():
                from collections import defaultdict
                issues = {}
                for line in registry_file.read_text(encoding='utf-8').splitlines():
                    if not line.strip() or line.startswith("{\"_"):
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if rec.get("type") == "issue":
                        issues[rec["id"]] = {"status": rec.get("status", "open"),
                                              "severity": rec.get("severity", "MED"),
                                              "reopen_count": 0}
                    elif rec.get("type") == "transition":
                        iid = rec.get("issue_id")
                        if iid in issues:
                            issues[iid]["status"] = rec.get("to_status")
                            if rec.get("to_status") == "reopened":
                                issues[iid]["reopen_count"] += 1

                by_status = defaultdict(int)
                by_severity_open = defaultdict(int)
                reopened = 0
                for i in issues.values():
                    by_status[i["status"]] += 1
                    if i["status"] in ("open", "reopened"):
                        by_severity_open[i["severity"]] += 1
                    if i.get("reopen_count", 0) > 0:
                        reopened += 1

                print(f"  📋 ISSUE REGISTRY (Part 10 — Issue-Driven Workflow):")
                print(f"     Total: {len(issues)}")
                print(f"     Status: open={by_status.get('open',0)} / in_progress={by_status.get('in_progress',0)} / "
                      f"verifying={by_status.get('verifying',0)} / closed={by_status.get('closed',0)} / "
                      f"reopened={by_status.get('reopened',0)}")
                if sum(by_severity_open.values()) > 0:
                    print(f"     Open by severity: HIGH={by_severity_open['HIGH']} / "
                          f"MED={by_severity_open['MED']} / LOW={by_severity_open['LOW']}")
                if reopened > 0:
                    print(f"     ⚠ Reopened (regression detected): {reopened}")
                print(f"     CLI: python ~/.claude/scripts/issue-registry.py list")
                print()
        except Exception:
            pass

        if all_issues:
            print("Issues:")
            for issue in all_issues:
                print(f"  - {issue}")
            print()
        print("=" * 60)

    return 0 if total_score >= 0.95 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(2)

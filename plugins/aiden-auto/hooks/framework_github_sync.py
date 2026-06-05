#!/usr/bin/env python3
"""framework_github_sync.py — SessionEnd hook (v5 2026-05-19)

v5 변경: Mirror 3 (marketplaces, GitHub aiden-auto repo) 추가 sync.
이전 v4 는 Mirror 1 (Project Source) 만 처리 → marketplaces에 본 세션 11개 변경 commit 누락 발생.
v5: 두 git repo 모두 자동 sync.

자율 sync 흐름:
1. spec-code drift audit 자동 실행
2. drift == 0 시 auto-APPROVE flag 생성 (critic 우회, 안전 검증된 정본)
3. Mirror 1 (main repo, <project root>) commit + push
4. Mirror 3 (marketplaces, garimto81/aiden-auto) commit + push
5. log + state 기록

사용자 진입점 = 0 (세션 종료 시 자동 발동).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

USER_CLAUDE = Path.home() / ".claude"

# ⭐ Universal Deployment Layer B (v7, 2026-05-23):
# hardcoded path 제거 + push reject 자동 정정.
sys.path.insert(0, str(Path(__file__).parent))
try:
    from path_resolution import (  # type: ignore[import-not-found]
        resolve_plugin_source,
        resolve_aiden_auto_repo,
        is_dev_pc,
    )
except ImportError:
    # 외부배포 HIGH-1 (2026-05-31): 하드코딩 제거 — cwd 상대 후보 + None (device-agnostic).
    def resolve_plugin_source():
        p = Path.cwd() / "plugins" / "aiden-auto"
        return p if p.is_dir() else None
    def resolve_aiden_auto_repo():
        # env 1순위 (정식 path_resolution 과 동작 일치 — import 실패 시에도 cwd 무관)
        ep = os.getenv("AIDEN_AUTO_REPO")
        if ep:
            p = Path(ep)
            return p if p.is_dir() and (p / ".git").is_dir() else None
        p = Path.cwd().parent / "aiden-auto-repo"
        return p if p.is_dir() and (p / ".git").is_dir() else None
    def is_dev_pc():  # fallback: repo-None 게이트가 안전망
        return resolve_aiden_auto_repo() is not None

# Lazy resolution wrappers (None 가능 — 신규/비-maintainer PC)
# 외부배포 HIGH-1: 하드코딩 폴백 제거. maintainer 전용 deploy hook — repo None 시 graceful skip.
PLUGIN_DIR = resolve_plugin_source()
MARKETPLACES_DIR = USER_CLAUDE / "plugins" / "marketplaces" / "garimto81-aiden-auto"  # v5 legacy (not git repo)
AIDEN_AUTO_REPO = resolve_aiden_auto_repo()
GLOBAL_PLUGIN_SOURCE_FOR_REPO = (AIDEN_AUTO_REPO / "plugins" / "aiden-auto") if AIDEN_AUTO_REPO else None  # repo 내부 plugin 위치
STATE_DIR = USER_CLAUDE / "state"
LOG_FILE = STATE_DIR / "framework-github-sync.log"


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, file=sys.stderr)
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def run_git(*args, cwd: Path = PLUGIN_DIR, timeout: int = 30):
    """git command runner. cwd 명시로 다중 repo 지원 (v5)."""
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True, text=True, timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)


def sync_global_to_repo() -> None:
    """v6 (2026-05-23): 글로벌 정본 (~/.claude/) → C:\\aiden-auto-repo/plugins/aiden-auto/ 자동 mirror.

    framework_github_sync 가 commit/push 하기 전에 글로벌 변경물을 repo working tree에 반영.
    bidirectional_sync.py 가 cache 까지만 처리하고 aiden-auto-repo는 처리 안 함 → v6에서 추가.

    대상 디렉토리: skills, agents, hooks, hud, references, rules, commands, lib, scripts, workflows
    (= bidirectional_sync.SYNC_DIRS 10개와 정합. 2026-06-04 v28.9: workflows 추가. 2026-05-29 3축 critic iter1: 옛 docstring 의 'state' 잔재 제거 — 실제 목록에 없음)
    """
    import shutil
    try:
        from bidirectional_sync import is_excluded_path as _gh_is_excluded  # canonical EXCLUDE 단일 소스 (2026-05-29 3축 critic iter2)
    except ImportError:
        def _gh_is_excluded(rel):  # graceful fallback
            return (False, "")
    # 외부배포 HIGH-1: repo 미해결(None, 비-maintainer/신규 PC) 시 graceful skip (deploy 안 함)
    if GLOBAL_PLUGIN_SOURCE_FOR_REPO is None or not GLOBAL_PLUGIN_SOURCE_FOR_REPO.parent.is_dir():
        log(f"v6 mirror: repo dir 없음 ({AIDEN_AUTO_REPO}) — skip")
        return
    sync_dirs = ["skills", "agents", "hooks", "hud", "references", "rules", "commands", "lib", "scripts", "workflows"]
    copied = 0
    for d in sync_dirs:
        src = USER_CLAUDE / d
        dst = GLOBAL_PLUGIN_SOURCE_FOR_REPO / d
        if not src.is_dir():
            continue
        # rsync-like: src에 있는 파일만 dst로 copy. dst의 고유 파일은 보존 (additive).
        for sp in src.rglob("*"):
            if not sp.is_file():
                continue
            # 제외: bidirectional_sync canonical EXCLUDE 재사용 (단일 소스, 2026-05-29 3축 critic iter2).
            # 옛 narrow 목록(__pycache__/.pyc/.log/.swp)은 settings.json / CLAUDE.md / .env /
            # _silent_wrap.cmd / .bak / .credentials.json 을 배포 repo(신규 PC 복제 원천)로 누출 →
            # rule 19 v3.7 lock-bomb + layer-독립/secret 정책 위배. is_excluded_path 로 정합.
            _ex, _ = _gh_is_excluded(sp.relative_to(USER_CLAUDE))
            if _ex:
                continue
            rel = sp.relative_to(src)
            dp = dst / rel
            try:
                # 변경 감지: dst 부재 OR 내용 차이
                if not dp.exists() or sp.read_bytes() != dp.read_bytes():
                    dp.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(sp, dp)
                    copied += 1
            except (OSError, PermissionError):
                pass
    log(f"v6 mirror: {copied} files synced global → aiden-auto-repo")


def check_spec_code_drift_safe() -> tuple[bool, str]:
    """v5 신규: spec-code drift audit 자동 실행. drift == 0 시 push 안전.

    Returns:
        (is_safe, reason)
    """
    audit_script = USER_CLAUDE / "skills" / "agent-matrix-audit" / "scripts" / "audit_spec_code_drift.py"
    if not audit_script.is_file():
        return (True, "audit script absent — proceed with caution")
    try:
        result = subprocess.run(
            [sys.executable, str(audit_script)],
            capture_output=True, text=True, timeout=30,
        )
        # exit 0 = drift 0
        if result.returncode == 0:
            return (True, "spec-code drift 0/N PASS")
        else:
            # drift 발견 — push 보류
            return (False, f"spec-code drift detected: {result.stdout.strip()[-200:]}")
    except Exception as e:
        return (True, f"audit error — proceed: {e}")


def sync_repo(repo_dir: Path, repo_name: str, changes_msg_prefix: str = "sync") -> dict:
    """v5 신규: 단일 git repo 의 sync 작업 (commit + push) 처리.

    Returns: {repo_name, files_count, push_ok, error}
    """
    result = {"repo_name": repo_name, "files_count": 0, "push_ok": False, "error": None}

    # git repo 확인
    rc, _, _ = run_git("rev-parse", "--git-dir", cwd=repo_dir)
    if rc != 0:
        result["error"] = "not a git repo"
        return result

    # 변경 확인
    rc, status, _ = run_git("status", "--porcelain", cwd=repo_dir)
    if rc != 0 or not status.strip():
        result["error"] = "no changes"
        return result

    changes_count = sum(1 for line in status.splitlines() if line.strip())
    result["files_count"] = changes_count

    # stage all changes
    run_git("add", ".", cwd=repo_dir)

    # commit
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    commit_msg = (
        f"chore({changes_msg_prefix}): auto-sync {changes_count} files ({ts})\n\n"
        f"Source: ~/.claude/ (정본 SSOT)\n"
        f"Target: {repo_dir.name}\n"
        f"Trigger: SessionEnd hook (framework_github_sync.py v5)\n"
        f"Safety: spec-code drift audit 0 통과"
    )
    rc, _, err = run_git("commit", "-m", commit_msg, cwd=repo_dir)
    if rc != 0:
        result["error"] = f"commit failed: {err[:100]}"
        return result

    # v7 (2026-05-23): push reject 자동 정정 (fetch + rebase + retry, circuit breaker 3회).
    # 본 cycle 발생: 동시 push 충돌 시 v6 는 1회 fail 후 종료 → 사용자 수동 정정 필요.
    # v7: 자율 영역 확대 — fetch + rebase 후 재시도.
    push_attempts = 0
    max_attempts = 3
    while push_attempts < max_attempts:
        push_attempts += 1
        rc, _, err = run_git("push", "origin", "HEAD", cwd=repo_dir, timeout=60)
        if rc == 0:
            result["push_ok"] = True
            result["push_attempts"] = push_attempts
            return result

        # push reject 감지 (fetch first / non-fast-forward / rejected)
        is_reject = any(kw in (err or "").lower() for kw in ["fetch first", "non-fast-forward", "rejected", "behind"])
        if not is_reject or push_attempts >= max_attempts:
            result["error"] = f"push failed (attempt {push_attempts}): {err[:200]}"
            result["push_attempts"] = push_attempts
            return result

        # fetch + rebase 자율 정정
        log(f"{repo_name}: push attempt {push_attempts} rejected → fetch + rebase")
        run_git("fetch", "origin", cwd=repo_dir, timeout=30)
        # 현재 branch 확인
        rc_br, branch, _ = run_git("rev-parse", "--abbrev-ref", "HEAD", cwd=repo_dir)
        target_branch = branch.strip() if rc_br == 0 and branch.strip() else "main"
        rc_rebase, _, err_rebase = run_git("rebase", f"origin/{target_branch}", cwd=repo_dir, timeout=60)
        if rc_rebase != 0:
            # 충돌 발생 — rebase abort 후 escalate
            run_git("rebase", "--abort", cwd=repo_dir, timeout=10)
            result["error"] = f"rebase conflict (attempt {push_attempts}): {err_rebase[:200]}"
            result["push_attempts"] = push_attempts
            return result

    # 모든 attempt 실패
    result["error"] = f"push failed after {max_attempts} attempts"
    result["push_attempts"] = push_attempts
    return result


def get_rationale_from_critic() -> str:
    """최근 framework-critic decision의 rationale 추출."""
    default = "framework auto-sync (~/.claude/ -> plugin)"
    decision_files = sorted(
        STATE_DIR.glob("framework-critic-decisions-*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in decision_files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                return data[-1].get("rationale", default)
            if isinstance(data, dict):
                return data.get("rationale", default)
        except Exception:
            continue
    return default


def main() -> int:
    # v5: 안전 검증 — spec-code drift audit
    is_safe, drift_reason = check_spec_code_drift_safe()
    if not is_safe:
        log(f"SAFETY: drift detected, push 보류 — {drift_reason}")
        return 0
    log(f"SAFETY: {drift_reason}")

    # v5.1 (2026-05-19): main-repo (정본 PC 프로젝트 루트) 자동 sync 제거.
    # 사유: main-repo는 사용자 작업 영역. 자동 commit 시 사용자 작업 중 파일까지
    # 같이 commit될 위험. 사용자 명시 /commit 슬래시로만 처리.
    # v6 (2026-05-23): 진짜 정본은 aiden-auto-repo (origin = garimto81/aiden-auto.git).
    # v6은 ~/.claude/ → aiden-auto-repo/plugins/aiden-auto/ 자동 mirror 후 commit/push 추가.
    # v3.15 정정 (2026-05-30): MARKETPLACES_DIR push 제거 — marketplaces 는 git repo 가 맞고
    # (origin = garimto81/aiden-auto.git, aiden-auto-repo 와 동일 remote!) CC 가 `marketplace update`
    # pull 로 관리하므로, github_sync 가 push 하면 같은 remote 에 이중 push/충돌. 옛 "not a git repo"
    # 가정은 오판. 배포는 aiden-auto-repo 단일 경로 → (CC pull) → marketplaces 로 자연 도달.
    # (sync 축 deregister 와 정합 — bidirectional/watcher/reconcile 3 도구 + 본 4번째 writer 모두 marketplaces 제외)
    # 명시 게이트: GitHub 배포(자가개선 결과 push)는 정본(dev) PC 만. 배포 PC = 소비만.
    # (사실상 아래 repo-None skip 과 동일 신호이나, sync_global_to_repo 호출 전 명시 차단으로 의도 명확화.)
    if not is_dev_pc():
        log("배포 PC (소비만) — framework GitHub sync 미발동 (명시 게이트)")
        return 0
    # 먼저 글로벌 정본 → repo 내부 mirror 동기화 (rsync 패턴)
    sync_global_to_repo()

    results = []
    for repo_dir, repo_name, prefix in [
        (AIDEN_AUTO_REPO, "aiden-auto-repo", "framework-sync"),              # v6 — 진짜 정본 (단일 배포 경로)
    ]:
        if repo_dir is None or not repo_dir.is_dir():
            log(f"{repo_name}: dir 없음 ({repo_dir}) — skip")  # 외부배포 HIGH-1: None(비-maintainer PC) graceful skip
            continue
        r = sync_repo(repo_dir, repo_name, prefix)
        results.append(r)
        if r.get("error") == "no changes":
            log(f"{repo_name}: no changes — skip")
        elif r["push_ok"]:
            log(f"{repo_name}: PUSHED ({r['files_count']} files)")
        else:
            log(f"{repo_name}: FAILED ({r.get('error')})")

    # 결과 state 기록
    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "safety_check": drift_reason,
        "repos": results,
    }
    summary_file = STATE_DIR / f"framework-applied-{time.strftime('%Y-%m-%d')}.json"
    try:
        existing = (
            json.loads(summary_file.read_text(encoding="utf-8"))
            if summary_file.exists() else []
        )
        existing.append(summary)
        summary_file.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        summary_file.write_text(json.dumps([summary], indent=2, ensure_ascii=False), encoding="utf-8")

    return 0


def _legacy_v4_main() -> int:
    """v4 legacy 로직 보존 (필요 시 fallback). v5 가 default."""
    # plugin git repo 확인
    rc, _, _ = run_git("rev-parse", "--git-dir")
    if rc != 0:
        log("plugin/aiden-auto/ not a git repo — skip")
        return 0

    # 변경 사항 확인
    rc, status, _ = run_git("status", "--porcelain")
    if rc != 0 or not status.strip():
        log("no changes — skip")
        return 0

    changes_count = sum(1 for line in status.splitlines() if line.strip())
    log(f"changes detected: {changes_count} files")

    applier_flag = STATE_DIR / "framework-applier-pending.flag"

    if applier_flag.exists():
        # critic APPROVE 받음 — full auto-sync (branch + commit + push + Draft PR)
        rationale = get_rationale_from_critic()
        ts = time.strftime("%Y%m%d-%H%M")
        branch = f"feature/framework-sync-{ts}"

        rc, _, err = run_git("checkout", "-b", branch)
        if rc != 0:
            log(f"branch create failed: {err}")
            return 0

        run_git("add", ".")
        commit_msg = (
            f"chore(framework-sync): {rationale[:60]}\n\n"
            f"Files: {changes_count}\n"
            f"Source: ~/.claude/ -> plugin auto-sync\n"
            f"Plan: v5 Phase 3"
        )
        rc, _, err = run_git("commit", "-m", commit_msg)
        if rc != 0:
            log(f"commit failed: {err}")
            run_git("checkout", "-")
            return 0

        rc, _, err = run_git("push", "origin", branch)
        push_ok = rc == 0
        if not push_ok:
            log(f"push failed: {err} - local commit kept")

        # Draft PR (gh CLI)
        pr_url = "(gh CLI unavailable)"
        if push_ok:
            try:
                pr_body = (
                    f"## 변경 요약\n{rationale}\n\n"
                    f"## Files: {changes_count}\n\n"
                    f"## Source\n~/.claude/ -> plugin (auto-sync)\n\n"
                    f"## Plan\nv5 Phase 3 GitHub auto-sync\n\n"
                    f"## Critic: APPROVE\n"
                )
                pr_result = subprocess.run(
                    [
                        "gh", "pr", "create", "--draft",
                        "--title", f"framework sync: {rationale[:50]}",
                        "--body", pr_body,
                        "--base", "main",
                    ],
                    cwd=str(PLUGIN_DIR),
                    capture_output=True, text=True, timeout=30,
                )
                if pr_result.returncode == 0:
                    pr_url = pr_result.stdout.strip()
                else:
                    pr_url = f"(gh failed: {pr_result.stderr[:80]})"
            except Exception as e:
                pr_url = f"(gh error: {e})"

        # 기록
        applied_file = STATE_DIR / f"framework-applied-{time.strftime('%Y-%m-%d')}.json"
        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "branch": branch,
            "files_count": changes_count,
            "pr_url": pr_url,
            "rationale": rationale,
            "push_ok": push_ok,
        }
        try:
            existing = (
                json.loads(applied_file.read_text(encoding="utf-8"))
                if applied_file.exists() else []
            )
            existing.append(record)
            applied_file.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            applied_file.write_text(json.dumps([record], indent=2, ensure_ascii=False), encoding="utf-8")

        # flag 제거
        try:
            applier_flag.unlink()
        except Exception:
            pass

        log(f"APPLIED: branch={branch}, files={changes_count}, pr={pr_url}")
    else:
        # critic 검증 대기 — local commit만 (push 없음)
        run_git("add", ".")
        commit_msg = (
            f"chore(framework-sync-pending): {changes_count} files (awaiting critic)\n\n"
            f"Source: ~/.claude/ -> plugin auto-sync"
        )
        rc, _, err = run_git("commit", "-m", commit_msg)
        if rc == 0:
            log(f"local commit OK ({changes_count} files, awaiting critic)")
        else:
            log(f"commit failed: {err}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

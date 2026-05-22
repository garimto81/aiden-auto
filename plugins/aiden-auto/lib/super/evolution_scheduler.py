"""Evolution Scheduler: daily/weekly/monthly cron orchestrator.

CLI:
  python -m super.evolution_scheduler --cadence=daily   [--apply | --dry-run]
  python -m super.evolution_scheduler --cadence=weekly  [--apply | --dry-run]
  python -m super.evolution_scheduler --cadence=monthly [--apply | --dry-run]
  python -m super.evolution_scheduler --category=tdd    [--apply]
  python -m super.evolution_scheduler --bootstrap       (uncompiled 카테고리 전부 컴파일)

흐름 (per category, daily 기준):
  1. circuit_breaker.can_evolve(cat) 확인
  2. sync_engine.detect_drift(cat) → DriftReport
  3. tier 분기:
       LOW    → checkpoint → compile → smoke_test → write or rollback
       MEDIUM → compile draft (skills/<cat>/SKILL.md.draft)
       HIGH   → 알림만 (PR 생성은 GitHub Actions에서 별도 단계)
  4. NDJSON 로그 + circuit_breaker.record_attempt
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# Support both `python -m super.evolution_scheduler` and `python evolution_scheduler.py`
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from super.checkpoint_manager import CheckpointManager
    from super.circuit_breaker_super import CircuitBreakerSuper
    from super.compiler import Compiler
    from super.evolution_reporter import EvolutionReporter
    from super.harvester import Harvester
    from super.plugin_marketplace_probe import PluginMarketplaceProbe
    from super.smoke_tester import SmokeTester
    from super.sync_engine import SyncEngine
    from super.tier_classifier import Tier
else:
    from .checkpoint_manager import CheckpointManager
    from .circuit_breaker_super import CircuitBreakerSuper
    from .compiler import Compiler
    from .evolution_reporter import EvolutionReporter
    from .harvester import Harvester
    from .plugin_marketplace_probe import PluginMarketplaceProbe
    from .smoke_tester import SmokeTester
    from .sync_engine import SyncEngine
    from .tier_classifier import Tier


PLUGIN_ROOT_DEFAULT = Path(__file__).resolve().parent.parent.parent  # plugins/aiden-auto


@dataclass
class EvolveOutcome:
    category: str
    tier: str
    applied: bool
    reason: str
    drifted_count: int


class EvolutionScheduler:
    def __init__(
        self,
        plugin_root: Path | None = None,
        *,
        apply_changes: bool = False,
    ) -> None:
        self.plugin_root = plugin_root or PLUGIN_ROOT_DEFAULT
        self.apply = apply_changes
        self.harvester = Harvester()
        self.compiler = Compiler(plugin_root=self.plugin_root, harvester=self.harvester)
        self.sync_engine = SyncEngine(
            plugin_root=self.plugin_root,
            harvester=self.harvester,
            compiler=self.compiler,
        )
        self.checkpoint = CheckpointManager(self.plugin_root)
        self.breaker = CircuitBreakerSuper(self.plugin_root)
        self.smoke = SmokeTester(self.plugin_root)
        self.reporter = EvolutionReporter(self.plugin_root)
        self.probe = PluginMarketplaceProbe()

    def run_daily(self, only_category: str | None = None) -> list[EvolveOutcome]:
        """LOW tier만 자동 적용. MEDIUM은 draft, HIGH는 로그 알림.

        Phase G 확장: source drift sync 후 telemetry aggregation + self-optimization 실행.
        """
        outcomes: list[EvolveOutcome] = []
        reports = self._reports(only_category)
        for report in reports:
            if not report.has_drift:
                continue
            outcome = self._evolve_one(report)
            outcomes.append(outcome)
            self._log_outcome(outcome, cadence="daily")

        # 만료 백업 정리
        self.checkpoint.expire_old()

        # Phase G: telemetry + self-optimization 통합
        try:
            self._run_telemetry_pipeline()
        except Exception as e:
            self._log_event({
                "ts": _now_iso(),
                "event": "telemetry_pipeline_error",
                "error": str(e),
            })

        return outcomes

    def _run_telemetry_pipeline(self) -> None:
        """Step 2-3: telemetry aggregation + self-optimization 제안 생성·적용."""
        from datetime import date as _date, timedelta as _td
        try:
            if __package__ in (None, ""):
                from super.telemetry_analyzer import write_daily, purge_old
                from super.self_optimizer import analyze_daily, write_proposals
            else:
                from .telemetry_analyzer import write_daily, purge_old
                from .self_optimizer import analyze_daily, write_proposals
        except Exception:
            return

        yesterday = _date.today() - _td(days=1)

        # Step 2: aggregate telemetry
        try:
            write_daily(yesterday)
            self._log_event({
                "ts": _now_iso(),
                "event": "telemetry_aggregated",
                "date": yesterday.isoformat(),
            })
        except Exception as e:
            self._log_event({"ts": _now_iso(), "event": "telemetry_aggregate_error", "error": str(e)})

        # Step 3: self-optimization 제안
        try:
            proposals = analyze_daily(yesterday)
            if proposals:
                write_proposals(proposals)
                tier_count = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
                for p in proposals:
                    tier_count[p.tier.value] += 1
                self._log_event({
                    "ts": _now_iso(),
                    "event": "optimization_proposed",
                    "count": len(proposals),
                    "by_tier": tier_count,
                })
        except Exception as e:
            self._log_event({"ts": _now_iso(), "event": "optimization_error", "error": str(e)})

        # Step 2.5: telemetry 30일 TTL purge
        try:
            removed = purge_old()
            if any(removed.values()):
                self._log_event({"ts": _now_iso(), "event": "telemetry_purged", **removed})
        except Exception:
            pass

    def run_weekly(self) -> list[EvolveOutcome]:
        """MEDIUM tier draft 생성까지."""
        outcomes: list[EvolveOutcome] = []
        for report in self._reports(None):
            if not report.has_drift:
                continue
            tier = report.highest_tier
            if tier == Tier.MEDIUM:
                outcome = self._evolve_medium_draft(report)
            elif tier == Tier.LOW:
                outcome = self._evolve_one(report)
            else:
                outcome = EvolveOutcome(
                    category=report.category,
                    tier=tier.value if tier else "?",
                    applied=False,
                    reason="HIGH tier — PR generation deferred to GitHub Actions",
                    drifted_count=len(report.drifted_sources),
                )
            outcomes.append(outcome)
            self._log_outcome(outcome, cadence="weekly")
        return outcomes

    def run_monthly(self) -> list[EvolveOutcome]:
        """winner 재평가는 critic 룰 외부 호출 필요 → 로그 알림만."""
        self._log_event({
            "event": "monthly_re_eval_due",
            "ts": _now_iso(),
            "note": "Run /audit super-sync --re-evaluate for backbone reconsideration",
        })
        return self.run_weekly()  # 기본 동작은 weekly와 동일

    def bootstrap(self) -> list[EvolveOutcome]:
        """uncompiled 카테고리 전부 초기 컴파일."""
        outcomes: list[EvolveOutcome] = []
        cats = self.sync_engine.detect_uncompiled()
        for cat in cats:
            try:
                if self.apply:
                    self.checkpoint.create(cat)
                    result = self.compiler.compile(cat)
                    self.compiler.write_super(cat, result)
                    smoke = self.smoke.test(cat)
                    if not smoke.passed:
                        self.checkpoint.restore(cat)
                        outcomes.append(EvolveOutcome(
                            category=cat, tier="BOOTSTRAP", applied=False,
                            reason=f"smoke failed: {smoke.failures}", drifted_count=0,
                        ))
                        continue
                outcomes.append(EvolveOutcome(
                    category=cat, tier="BOOTSTRAP",
                    applied=self.apply,
                    reason="initial compile" if self.apply else "dry-run",
                    drifted_count=0,
                ))
                self._log_event({
                    "event": "bootstrapped" if self.apply else "bootstrap_dry_run",
                    "ts": _now_iso(),
                    "category": cat,
                })
            except Exception as e:
                outcomes.append(EvolveOutcome(
                    category=cat, tier="BOOTSTRAP", applied=False,
                    reason=f"compile error: {e}", drifted_count=0,
                ))
                self._log_event({
                    "event": "bootstrap_error",
                    "ts": _now_iso(),
                    "category": cat,
                    "error": str(e),
                })
        return outcomes

    # ---- internals ----

    def _reports(self, only_category: str | None):
        if only_category:
            return [self.sync_engine.detect_drift(only_category)]
        return self.sync_engine.detect_drift_all()

    def _evolve_one(self, report) -> EvolveOutcome:
        """LOW tier 자동 적용. 그 외는 미적용 (사유 기록)."""
        cat = report.category
        ok, reason = self.breaker.can_evolve(cat)
        if not ok:
            return EvolveOutcome(category=cat, tier="?", applied=False,
                                 reason=f"circuit breaker: {reason}",
                                 drifted_count=len(report.drifted_sources))

        tier = report.highest_tier
        tier_str = tier.value if tier else "?"

        if tier != Tier.LOW:
            self.breaker.record_attempt(cat, applied=False, tier=tier_str)
            return EvolveOutcome(category=cat, tier=tier_str, applied=False,
                                 reason=f"{tier_str} tier — manual review required",
                                 drifted_count=len(report.drifted_sources))

        if not self.apply:
            return EvolveOutcome(category=cat, tier="LOW", applied=False,
                                 reason="dry-run",
                                 drifted_count=len(report.drifted_sources))

        try:
            self.checkpoint.create(cat)
            result = self.compiler.compile(cat)
            self.compiler.write_super(cat, result)
            smoke = self.smoke.test(cat)
            if not smoke.passed:
                self.checkpoint.restore(cat)
                self.breaker.record_attempt(cat, applied=False, tier="LOW")
                return EvolveOutcome(category=cat, tier="LOW", applied=False,
                                     reason=f"smoke failed → rollback: {smoke.failures}",
                                     drifted_count=len(report.drifted_sources))
            self.breaker.record_attempt(cat, applied=True, tier="LOW")
            return EvolveOutcome(category=cat, tier="LOW", applied=True,
                                 reason="LOW auto-applied",
                                 drifted_count=len(report.drifted_sources))
        except Exception as e:
            self.breaker.record_attempt(cat, applied=False, tier=tier_str)
            return EvolveOutcome(category=cat, tier=tier_str, applied=False,
                                 reason=f"compile error: {e}",
                                 drifted_count=len(report.drifted_sources))

    def _evolve_medium_draft(self, report) -> EvolveOutcome:
        cat = report.category
        if not self.apply:
            return EvolveOutcome(category=cat, tier="MEDIUM", applied=False,
                                 reason="dry-run (would create .draft)",
                                 drifted_count=len(report.drifted_sources))
        try:
            result = self.compiler.compile(cat)
            draft_path = self.plugin_root / "skills" / cat / "SKILL.md.draft"
            draft_path.parent.mkdir(parents=True, exist_ok=True)
            draft_path.write_text(result.super_skill_md, encoding="utf-8")
            return EvolveOutcome(category=cat, tier="MEDIUM", applied=False,
                                 reason=f"draft created: {draft_path.name}",
                                 drifted_count=len(report.drifted_sources))
        except Exception as e:
            return EvolveOutcome(category=cat, tier="MEDIUM", applied=False,
                                 reason=f"draft error: {e}",
                                 drifted_count=len(report.drifted_sources))

    # ---- Step 4: Full Smoke (workflow line 102-128 추출) ----

    SMOKE_CATEGORIES = (
        "tdd", "commit", "simplify", "debug", "plan", "check",
        "parallel", "verify", "skill-create", "research", "auto", "pr",
    )

    CLASSIFIER_TESTS = (
        ("이 코드 리뷰해줘", "check"),
        ("TDD로 결제 구현", "tdd"),
        ("이 에러 디버그", "debug"),
        ("/check fast", None),  # bypass expected
    )

    def run_full_smoke(self) -> dict:
        """Step 4 — 12개 super skill 무결성 + auto-routing classifier 정확도 smoke.

        Returns:
            {"skills": {"tdd": True, ...}, "classifier": {"prompt": "ok"|"miss", ...}, "passed": bool}
        """
        skill_results: dict[str, bool] = {}
        for cat in self.SMOKE_CATEGORIES:
            try:
                r = self.smoke.test(cat)
                skill_results[cat] = r.passed
            except Exception as e:
                skill_results[cat] = False
                self._log_event({
                    "ts": _now_iso(),
                    "event": "smoke_full_skill_error",
                    "category": cat,
                    "error": str(e),
                })

        classifier_results: dict[str, bool] = {}
        try:
            if __package__ in (None, ""):
                from super.intent_classifier import classify
            else:
                from .intent_classifier import classify

            for prompt, expected in self.CLASSIFIER_TESTS:
                try:
                    r = classify(prompt)
                    if r.bypass:
                        top = "bypass"
                    elif r.categories:
                        top = r.top_category.category
                    else:
                        top = "ambiguous"
                    if expected is None:
                        ok = bool(r.bypass)
                    else:
                        ok = (top == expected)
                    classifier_results[prompt[:30]] = ok
                except Exception as e:
                    classifier_results[prompt[:30]] = False
                    self._log_event({
                        "ts": _now_iso(),
                        "event": "smoke_full_classifier_error",
                        "prompt": prompt,
                        "error": str(e),
                    })
        except ImportError as e:
            self._log_event({
                "ts": _now_iso(),
                "event": "smoke_full_classifier_import_error",
                "error": str(e),
            })

        all_skills_ok = all(skill_results.values())
        all_classifier_ok = all(classifier_results.values()) if classifier_results else False
        passed = all_skills_ok and all_classifier_ok

        self._log_event({
            "ts": _now_iso(),
            "event": "smoke_full",
            "skills_passed": sum(1 for v in skill_results.values() if v),
            "skills_total": len(skill_results),
            "classifier_passed": sum(1 for v in classifier_results.values() if v),
            "classifier_total": len(classifier_results),
            "passed": passed,
        })

        return {
            "skills": skill_results,
            "classifier": classifier_results,
            "passed": passed,
        }

    # ---- Step 5-6: Auto commit / PR (workflow line 139-164 재현) ----

    AUTO_COMMIT_PATHS = ("plugins/aiden-auto/skills",
                        "plugins/aiden-auto/sources",
                        "plugins/aiden-auto/attribution")

    def _repo_root(self) -> Path | None:
        """plugin_root에서 git repo root 추적. 없으면 None."""
        cur = self.plugin_root.resolve()
        for _ in range(6):
            if (cur / ".git").exists():
                return cur
            if cur.parent == cur:
                break
            cur = cur.parent
        return None

    def _git(self, *args: str, cwd: Path) -> tuple[int, str, str]:
        """git 호출 헬퍼. (returncode, stdout, stderr)."""
        try:
            p = subprocess.run(
                ["git", *args],
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=30,
            )
            return p.returncode, p.stdout, p.stderr
        except FileNotFoundError:
            return 127, "", "git not found"
        except subprocess.TimeoutExpired:
            return 124, "", "git timeout"

    def auto_commit_low(self) -> dict:
        """daily LOW tier 적용 후 git add + commit. 변경 없으면 no-op.

        rules/20-evolution-cadence.md 표준 메시지:
            chore(super-evolve): daily LOW-tier sync YYYY-MM-DD
        """
        if not shutil.which("git"):
            self._log_event({"ts": _now_iso(), "event": "auto_commit_skipped",
                            "reason": "git not found"})
            return {"committed": False, "reason": "git not found"}

        repo = self._repo_root()
        if repo is None:
            self._log_event({"ts": _now_iso(), "event": "auto_commit_skipped",
                            "reason": "git repo not found"})
            return {"committed": False, "reason": "git repo not found"}

        rc, out, _ = self._git("diff", "--quiet", "--", *self.AUTO_COMMIT_PATHS, cwd=repo)
        if rc == 0:
            rc2, out2, _ = self._git("status", "--porcelain", "--", *self.AUTO_COMMIT_PATHS, cwd=repo)
            if rc2 == 0 and not out2.strip():
                self._log_event({"ts": _now_iso(), "event": "auto_commit_skipped",
                                "reason": "no changes"})
                return {"committed": False, "reason": "no changes"}

        rc, _, err = self._git("add", "--", *self.AUTO_COMMIT_PATHS, cwd=repo)
        if rc != 0:
            self._log_event({"ts": _now_iso(), "event": "auto_commit_error",
                            "stage": "add", "stderr": err.strip()[:200]})
            return {"committed": False, "reason": f"git add failed: {err.strip()}"}

        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        msg = f"chore(super-evolve): daily LOW-tier sync {date_str}"
        rc, _, err = self._git("commit", "-m", msg, cwd=repo)
        if rc != 0:
            self._log_event({"ts": _now_iso(), "event": "auto_commit_error",
                            "stage": "commit", "stderr": err.strip()[:200]})
            return {"committed": False, "reason": f"git commit failed: {err.strip()}"}

        rc, sha_out, _ = self._git("rev-parse", "--short", "HEAD", cwd=repo)
        sha = sha_out.strip() if rc == 0 else "?"

        self._log_event({"ts": _now_iso(), "event": "auto_commit",
                        "message": msg, "sha": sha})
        return {"committed": True, "sha": sha, "message": msg}

    def auto_pr_medium_high(self, cadence: str) -> dict:
        """weekly/monthly 시 브랜치 생성 + gh pr create.

        gh CLI 없거나 git push 실패 시 graceful degrade (LOW commit만 시도).
        """
        if cadence not in ("weekly", "monthly"):
            return {"created": False, "reason": f"PR not applicable for cadence={cadence}"}

        if not shutil.which("git"):
            self._log_event({"ts": _now_iso(), "event": "auto_pr_skipped",
                            "reason": "git not found"})
            return {"created": False, "reason": "git not found"}

        repo = self._repo_root()
        if repo is None:
            return {"created": False, "reason": "git repo not found"}

        rc, status_out, _ = self._git("status", "--porcelain", "--",
                                      "plugins/aiden-auto", cwd=repo)
        if rc != 0 or not status_out.strip():
            self._log_event({"ts": _now_iso(), "event": "auto_pr_skipped",
                            "reason": "no changes in plugins/aiden-auto"})
            return {"created": False, "reason": "no changes"}

        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
        branch = f"auto/super-evolve-{cadence}-{date_str}"

        rc, _, err = self._git("checkout", "-b", branch, cwd=repo)
        if rc != 0:
            self._log_event({"ts": _now_iso(), "event": "auto_pr_error",
                            "stage": "checkout", "stderr": err.strip()[:200]})
            return {"created": False, "reason": f"checkout failed: {err.strip()}"}

        rc, _, err = self._git("add", "--", "plugins/aiden-auto", cwd=repo)
        if rc != 0:
            return {"created": False, "reason": f"git add failed: {err.strip()}"}

        msg = f"chore(super-evolve): {cadence} sync proposal"
        rc, _, err = self._git("commit", "-m", msg, cwd=repo)
        if rc != 0:
            self._log_event({"ts": _now_iso(), "event": "auto_pr_error",
                            "stage": "commit", "stderr": err.strip()[:200]})
            return {"created": False, "reason": f"commit failed: {err.strip()}"}

        if not shutil.which("gh"):
            self._log_event({"ts": _now_iso(), "event": "auto_pr_partial",
                            "reason": "gh CLI not found — branch created but PR skipped",
                            "branch": branch})
            return {"created": False, "branch": branch,
                    "reason": "gh CLI not installed (branch created locally only)"}

        rc, _, err = self._git("push", "-u", "origin", branch, cwd=repo)
        if rc != 0:
            self._log_event({"ts": _now_iso(), "event": "auto_pr_error",
                            "stage": "push", "stderr": err.strip()[:200]})
            return {"created": False, "branch": branch,
                    "reason": f"push failed: {err.strip()}"}

        try:
            p = subprocess.run(
                ["gh", "pr", "create",
                 "--title", f"Super Evolve: {cadence} sync proposal",
                 "--body", f"Auto-generated by /evolve --full ({cadence} cadence)",
                 "--label", f"auto-evolve-{cadence}",
                 "--label", "needs-review"],
                cwd=str(repo), capture_output=True, text=True, timeout=60,
            )
            if p.returncode != 0:
                self._log_event({"ts": _now_iso(), "event": "auto_pr_error",
                                "stage": "gh_pr_create", "stderr": p.stderr.strip()[:200]})
                return {"created": False, "branch": branch,
                        "reason": f"gh pr create failed: {p.stderr.strip()}"}
            pr_url = p.stdout.strip()
            self._log_event({"ts": _now_iso(), "event": "auto_pr",
                            "branch": branch, "url": pr_url, "cadence": cadence})
            return {"created": True, "branch": branch, "url": pr_url}
        except Exception as e:
            return {"created": False, "branch": branch, "reason": str(e)}

    def _log_outcome(self, outcome: EvolveOutcome, *, cadence: str) -> None:
        self._log_event({
            "ts": _now_iso(),
            "event": "evolve_outcome",
            "cadence": cadence,
            "category": outcome.category,
            "tier": outcome.tier,
            "applied": outcome.applied,
            "reason": outcome.reason,
            "drifted_count": outcome.drifted_count,
        })

    def _log_event(self, event: dict) -> None:
        log_path = self.plugin_root / "audit" / "super-evolution.ndjson"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="aiden-auto super evolution scheduler")
    parser.add_argument("--cadence", choices=["daily", "weekly", "monthly"], default="daily")
    parser.add_argument("--category", default=None, help="단일 카테고리만 처리")
    parser.add_argument("--bootstrap", action="store_true", help="uncompiled 카테고리 전부 초기 컴파일")
    parser.add_argument("--apply", action="store_true", help="실제 적용 (default: dry-run)")
    parser.add_argument("--report", action="store_true", help="기간 보고서 출력")
    parser.add_argument("--full-smoke", action="store_true",
                       help="Step 4 풀 smoke (12 카테고리 + classifier 정확도)")
    parser.add_argument("--auto-commit", action="store_true",
                       help="Step 5/6 자동 commit(daily) 또는 PR(weekly/monthly)")
    parser.add_argument("--full", action="store_true",
                       help="--apply --full-smoke --auto-commit alias (cron 100%% 동등)")
    args = parser.parse_args(argv)

    if args.full:
        args.apply = True
        args.full_smoke = True
        args.auto_commit = True

    apply_env = os.environ.get("SUPER_EVOLVE_APPLY") == "1"
    apply_flag = args.apply or apply_env

    scheduler = EvolutionScheduler(apply_changes=apply_flag)

    smoke_only = args.full_smoke and not args.apply and not args.bootstrap
    outcomes: list[EvolveOutcome] = []

    if not smoke_only:
        try:
            if args.bootstrap:
                outcomes = scheduler.bootstrap()
            elif args.cadence == "weekly":
                outcomes = scheduler.run_weekly()
            elif args.cadence == "monthly":
                outcomes = scheduler.run_monthly()
            else:
                outcomes = scheduler.run_daily(only_category=args.category)
        except Exception:
            traceback.print_exc(file=sys.stderr)
            return 1

        print(f"[evolution] cadence={args.cadence} apply={apply_flag} outcomes={len(outcomes)}")
        for o in outcomes:
            print(f"  - {o.category} [{o.tier}] applied={o.applied} drift={o.drifted_count}: {o.reason}")

    if args.full_smoke:
        try:
            smoke = scheduler.run_full_smoke()
            print()
            print(f"[smoke] passed={smoke['passed']}")
            for cat, ok in smoke["skills"].items():
                print(f"  skill {cat:14s} {'PASS' if ok else 'FAIL'}")
            for prompt, ok in smoke["classifier"].items():
                print(f"  class {prompt[:30]:30s} {'OK' if ok else 'MISS'}")
        except Exception:
            traceback.print_exc(file=sys.stderr)
            return 1

    if args.auto_commit and apply_flag and not smoke_only:
        try:
            if args.cadence in ("weekly", "monthly"):
                pr_result = scheduler.auto_pr_medium_high(args.cadence)
                print()
                if pr_result.get("created"):
                    print(f"[pr] branch={pr_result['branch']} url={pr_result.get('url','')}")
                else:
                    print(f"[pr] skipped: {pr_result.get('reason','')}")
            else:
                commit_result = scheduler.auto_commit_low()
                print()
                if commit_result.get("committed"):
                    print(f"[commit] sha={commit_result['sha']} msg={commit_result['message']}")
                else:
                    print(f"[commit] skipped: {commit_result.get('reason','')}")
        except Exception:
            traceback.print_exc(file=sys.stderr)
            return 1

    if args.report:
        print()
        print(scheduler.reporter.daily_report())

    return 0


if __name__ == "__main__":
    sys.exit(main())

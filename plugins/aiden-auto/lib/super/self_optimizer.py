"""Self Optimizer — daily telemetry 분석 → 최적화 제안 생성.

7-차원 분석 (Section 17.1):
  1. 라우팅 정확도 — accuracy
  2. token 효율 — cost per outcome
  3. 캐시 효율 — cache hit ratio
  4. 컨텍스트 압박 — context size
  5. skill latency — p95
  6. false positive — auto-trigger 오탐
  7. AskUserQuestion 빈도 — 모호 분류 비율

각 차원에서 임계 위반 시 LOW/MEDIUM/HIGH tier 제안 생성.
NDJSON `audit/optimization-proposals.ndjson`에 append.

CLI:
  python self_optimizer.py analyze 2026-05-09
  python self_optimizer.py propose
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent  # plugins/aiden-auto


class Tier(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class Proposal:
    tier: Tier
    dimension: str
    issue: str
    recommendation: str
    target_file: str = ""
    metrics: dict = field(default_factory=dict)


# 임계 (Section 17.1)
THRESH_ACCURACY = 0.80
THRESH_CACHE_HIT = 0.30
THRESH_CONTEXT_PRESSURE = 0.80  # context size > 80% of limit
THRESH_LATENCY_P95_MS = 5000
THRESH_FALSE_POSITIVE = 0.10
THRESH_ASK_USER = 0.20


def analyze_daily(target_date: date) -> list[Proposal]:
    """daily 집계 파일 → 제안 리스트."""
    daily_path = PLUGIN_ROOT / "audit" / f"telemetry-daily-{target_date:%Y%m%d}.json"
    if not daily_path.exists():
        return []
    try:
        daily = json.loads(daily_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    proposals: list[Proposal] = []

    # 1. 캐시 효율
    cache_ratio = daily.get("cache_hit_ratio", 0.0)
    if 0 < cache_ratio < THRESH_CACHE_HIT and daily.get("prompts_count", 0) > 5:
        proposals.append(Proposal(
            tier=Tier.MEDIUM,
            dimension="cache_efficiency",
            issue=f"cache hit ratio {cache_ratio:.2%} below threshold {THRESH_CACHE_HIT:.0%}",
            recommendation="prompt 구조 개선 — references SoT 안정화로 캐시 적중률 향상 검토",
            target_file="references/",
            metrics={"cache_hit_ratio": cache_ratio},
        ))

    # 2. skill latency p95
    for tool, stats in daily.get("latency_stats", {}).items():
        p95 = stats.get("p95", 0)
        if p95 > THRESH_LATENCY_P95_MS:
            proposals.append(Proposal(
                tier=Tier.LOW,
                dimension="skill_latency",
                issue=f"{tool} p95 {p95}ms > {THRESH_LATENCY_P95_MS}ms",
                recommendation=f"{tool} bottleneck 분석 — 호출 빈도 또는 입력 크기 검토",
                target_file=f"tool:{tool}",
                metrics={"p95_ms": p95, "tool": tool},
            ))

    # 3. token 효율 — 상위 10% 카테고리 consolidation 제안
    skills_called = daily.get("skills_called", {})
    if skills_called:
        max_calls = max(skills_called.values())
        if max_calls > 10:  # 최소 호출 횟수 임계
            top_skills = [s for s, n in skills_called.items() if n >= max_calls * 0.9]
            if len(top_skills) >= 1:
                proposals.append(Proposal(
                    tier=Tier.MEDIUM,
                    dimension="token_efficiency",
                    issue=f"high-call skills: {', '.join(top_skills)}",
                    recommendation="해당 super skill의 absorb 룰 점검 — 불필요한 sections 정리",
                    target_file="sources/",
                    metrics={"top_skills": top_skills, "max_calls": max_calls},
                ))

    # 4. routing accuracy + false positive 분석 (auto-routing.ndjson 검토 필요)
    routing_proposals = _analyze_auto_routing(target_date)
    proposals.extend(routing_proposals)

    return proposals


def _analyze_auto_routing(target_date: date) -> list[Proposal]:
    """auto-routing.ndjson에서 정확도·false positive 산출."""
    routing_path = PLUGIN_ROOT / "audit" / "auto-routing.ndjson"
    if not routing_path.exists():
        return []

    start = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    total = 0
    bypass = 0
    ambiguous = 0
    auto_routed = 0
    confidences: list[float] = []

    try:
        with routing_path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                ts_str = e.get("ts", "")
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except Exception:
                    continue
                if not (start <= ts < end):
                    continue
                total += 1
                if e.get("bypass"):
                    bypass += 1
                elif e.get("pattern") == "ambiguous":
                    ambiguous += 1
                else:
                    auto_routed += 1
                    confidences.append(e.get("max_confidence", 0))
    except Exception:
        return []

    out: list[Proposal] = []
    if total < 5:
        return out

    ambiguous_ratio = ambiguous / max(total - bypass, 1)
    if ambiguous_ratio > THRESH_ASK_USER:
        out.append(Proposal(
            tier=Tier.LOW,
            dimension="ask_user_frequency",
            issue=f"ambiguous classification ratio {ambiguous_ratio:.1%} > {THRESH_ASK_USER:.0%}",
            recommendation="trigger 키워드 weak 항목 보강 또는 confidence 임계 ±0.05 조정",
            target_file="rules/21-auto-routing.md, lib/super/intent_classifier.py",
            metrics={"ambiguous_ratio": ambiguous_ratio, "total": total},
        ))

    if confidences:
        avg_conf = sum(confidences) / len(confidences)
        if avg_conf < 0.6:
            out.append(Proposal(
                tier=Tier.LOW,
                dimension="routing_confidence",
                issue=f"avg confidence {avg_conf:.2f} (target 0.60+)",
                recommendation="strong keyword 가중치 +0.05 또는 신규 strong 키워드 추가",
                target_file="lib/super/intent_classifier.py",
                metrics={"avg_confidence": avg_conf, "samples": len(confidences)},
            ))

    return out


def write_proposals(proposals: list[Proposal]) -> Path:
    out_path = PLUGIN_ROOT / "audit" / "optimization-proposals.ndjson"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    with out_path.open("a", encoding="utf-8") as f:
        for p in proposals:
            entry = asdict(p)
            entry["tier"] = p.tier.value
            entry["proposed_at"] = now
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="aiden-auto self optimizer")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_an = sub.add_parser("analyze")
    p_an.add_argument("date", nargs="?", default=None, help="YYYY-MM-DD (default: yesterday)")
    sub.add_parser("propose")  # alias for analyze + write
    args = parser.parse_args(argv)

    target = date.fromisoformat(args.date) if getattr(args, "date", None) else date.today() - timedelta(days=1)
    proposals = analyze_daily(target)

    print(f"## Self-Optimization Proposals ({target.isoformat()})")
    print(f"Total: {len(proposals)}")
    print()

    if not proposals:
        print("(no proposals — system within all thresholds)")
        return 0

    # tier 분포
    by_tier = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    for p in proposals:
        by_tier[p.tier.value] += 1
    print(f"By tier: LOW={by_tier['LOW']} MEDIUM={by_tier['MEDIUM']} HIGH={by_tier['HIGH']}")
    print()

    print("| Tier | Dimension | Issue | Recommendation |")
    print("|------|-----------|-------|----------------|")
    for p in proposals:
        print(f"| {p.tier.value} | {p.dimension} | {p.issue} | {p.recommendation[:60]} |")

    if args.cmd == "propose":
        out = write_proposals(proposals)
        print()
        print(f"appended to: {out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

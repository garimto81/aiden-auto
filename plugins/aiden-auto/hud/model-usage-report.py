#!/usr/bin/env python3
"""On-demand per-model usage report (READABLE version of model-usage-line.py).

Aggregates actual model usage from CC transcripts — the GROUND TRUTH for
"am I really using Sonnet/Haiku?". Reads each assistant message's
`message.model` field (what the API actually billed), including subagent
transcripts where dynamic model routing (4:3:3) actually happens.

Usage:
  python model-usage-report.py [project_dir] [--last N]
    project_dir : CC project transcript dir
                  (default: ~/.claude/projects/C--claude)
    --last N    : only the N most-recent sessions (default: 10)

Distinct from the OAuth Usage API (.usage-cache.json), which only gives
aggregate 5h/weekly quota % with NO per-model breakdown.
"""
import json
import os
import sys
from pathlib import Path
from collections import defaultdict

TIERS = ("opus", "sonnet", "haiku", "other")


def fam(m: str) -> str:
    m = (m or "").lower()
    if "opus" in m:
        return "opus"
    if "haiku" in m:
        return "haiku"
    if "sonnet" in m:
        return "sonnet"
    return "other"


def k(n) -> str:
    n = int(n or 0)
    if n >= 1_000_000:
        return f"{n / 1e6:.1f}m"
    if n >= 1_000:
        return f"{n / 1000:.1f}k"
    return str(n)


def new_agg():
    return defaultdict(lambda: {"in": 0, "out": 0, "cr": 0, "cw": 0, "msgs": 0})


def parse(path, agg) -> None:
    try:
        text = open(path, encoding="utf-8", errors="ignore").read()
    except Exception:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("type") != "assistant":
            continue
        msg = rec.get("message") or {}
        u = msg.get("usage") or {}
        if not isinstance(u, dict):
            continue
        t = fam(msg.get("model"))
        a = agg[t]
        a["msgs"] += 1
        a["in"] += int(u.get("input_tokens", 0) or 0)
        a["out"] += int(u.get("output_tokens", 0) or 0)
        a["cr"] += int(u.get("cache_read_input_tokens", 0) or 0)
        a["cw"] += int(u.get("cache_creation_input_tokens", 0) or 0)


def main() -> None:
    args = [a for a in sys.argv[1:]]
    last_n = 10
    proj = Path.home() / ".claude" / "projects" / "C--claude"
    i = 0
    while i < len(args):
        if args[i] == "--last" and i + 1 < len(args):
            last_n = int(args[i + 1])
            i += 2
        else:
            proj = Path(args[i])
            i += 1

    if not proj.is_dir():
        print(f"프로젝트 디렉토리 없음: {proj}")
        return

    sessions = sorted(
        proj.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
    )[:last_n]

    main_agg = new_agg()  # Lead (메인 세션)
    sub_agg = new_agg()   # 서브에이전트

    for s in sessions:
        parse(s, main_agg)
        subdir = proj / s.stem / "subagents"
        if subdir.is_dir():
            for j in subdir.glob("*.jsonl"):
                parse(j, sub_agg)

    def cost(a):
        price = {
            "opus": (15, 75, 1.5, 18.75),
            "sonnet": (3, 15, 0.3, 3.75),
            "haiku": (1, 5, 0.1, 1.25),
            "other": (3, 15, 0.3, 3.75),
        }
        c = 0.0
        for t in TIERS:
            pin, pout, pcr, pcw = price[t]
            x = a[t]
            c += (x["in"] * pin + x["out"] * pout + x["cr"] * pcr + x["cw"] * pcw) / 1e6
        return c

    def block(title, agg, show_pct=False):
        tot_msgs = sum(agg[t]["msgs"] for t in TIERS)
        print(title)
        if tot_msgs == 0:
            print("  (없음)")
            print()
            return
        for t in TIERS:
            a = agg[t]
            if a["msgs"] == 0:
                continue
            pct = f" ({100 * a['msgs'] / tot_msgs:4.0f}%)" if show_pct else ""
            print(
                f"  {t:7} {a['msgs']:5} 응답{pct}   "
                f"in={k(a['in']):>7}  out={k(a['out']):>7}  "
                f"cache_read={k(a['cr']):>7}"
            )
        print(f"  └ 합계 {tot_msgs} 응답 · 추정 비용 ${cost(agg):.2f}")
        print()

    print(f"# 모델별 실사용 리포트 — 최근 {len(sessions)} 세션 ({proj.name})")
    print("# 출처: transcript의 실제 message.model (API가 청구한 그대로)")
    print()
    block("== 메인 세션 (Lead — 당신이 대화하는 모델) ==", main_agg)
    block(
        "== 서브에이전트 (4:3:3 동적 라우팅이 실제 일어나는 곳) ==",
        sub_agg,
        show_pct=True,
    )


if __name__ == "__main__":
    main()

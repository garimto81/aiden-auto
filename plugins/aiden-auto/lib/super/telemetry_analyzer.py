"""Telemetry Analyzer — telemetry.ndjson을 daily/monthly로 집계.

산출물:
  - audit/telemetry-daily-<YYYYMMDD>.json
  - audit/telemetry-monthly-<YYYYMM>.json

CLI:
  python telemetry_analyzer.py daily 2026-05-09
  python telemetry_analyzer.py monthly 2026-05
  python telemetry_analyzer.py purge  # 30일 초과 raw NDJSON 삭제
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent  # plugins/aiden-auto
TELEMETRY_PATH = PLUGIN_ROOT / "audit" / "telemetry.ndjson"
RAW_TTL_DAYS = 30
DAILY_TTL_DAYS = 90
MONTHLY_TTL_DAYS = 365


def aggregate_daily(target_date: date) -> dict:
    """target_date의 raw NDJSON을 집계."""
    if not TELEMETRY_PATH.exists():
        return _empty_daily(target_date)

    start = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    by_event: Counter = Counter()
    tools_called: Counter = Counter()
    skills_called: Counter = Counter()
    tool_latency_ms: dict[str, list[int]] = defaultdict(list)
    tokens_total = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    prompts_count = 0
    prompt_chars_total = 0

    with TELEMETRY_PATH.open("r", encoding="utf-8") as f:
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

            evt = e.get("event", "?")
            by_event[evt] += 1
            if evt == "UserPromptSubmit":
                prompts_count += 1
                prompt_chars_total += e.get("prompt_chars", 0)
            if evt == "PreToolUse":
                tools_called[e.get("tool", "?")] += 1
                if e.get("skill"):
                    skills_called[e["skill"]] += 1
            if evt == "PostToolUse":
                tool = e.get("tool", "?")
                lat = e.get("latency_ms")
                if lat is not None:
                    tool_latency_ms[tool].append(lat)
            for k, mk in (("input_tokens", "input"), ("output_tokens", "output"),
                         ("cache_read_tokens", "cache_read"), ("cache_write_tokens", "cache_write")):
                if k in e:
                    tokens_total[mk] += int(e[k])

    # latency stats
    latency_stats = {}
    for tool, samples in tool_latency_ms.items():
        if samples:
            samples.sort()
            n = len(samples)
            latency_stats[tool] = {
                "count": n,
                "p50": samples[n // 2],
                "p95": samples[min(n - 1, int(n * 0.95))],
                "max": samples[-1],
                "mean": sum(samples) // n,
            }

    return {
        "date": target_date.isoformat(),
        "by_event": dict(by_event),
        "prompts_count": prompts_count,
        "prompt_chars_total": prompt_chars_total,
        "tools_called": dict(tools_called.most_common(20)),
        "skills_called": dict(skills_called.most_common(20)),
        "tokens_total": tokens_total,
        "latency_stats": latency_stats,
        "cache_hit_ratio": _cache_hit_ratio(tokens_total),
    }


def aggregate_monthly(year: int, month: int) -> dict:
    """daily 집계를 월간으로 통합."""
    audit_dir = PLUGIN_ROOT / "audit"
    pattern = f"telemetry-daily-{year:04d}{month:02d}*.json"
    monthly = {
        "month": f"{year:04d}-{month:02d}",
        "by_event": Counter(),
        "tools_called": Counter(),
        "skills_called": Counter(),
        "tokens_total": {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0},
        "prompts_count": 0,
        "days_with_data": 0,
    }
    if audit_dir.exists():
        for p in audit_dir.glob(pattern):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            monthly["days_with_data"] += 1
            for evt, n in d.get("by_event", {}).items():
                monthly["by_event"][evt] += n
            for tool, n in d.get("tools_called", {}).items():
                monthly["tools_called"][tool] += n
            for skill, n in d.get("skills_called", {}).items():
                monthly["skills_called"][skill] += n
            for k, v in d.get("tokens_total", {}).items():
                monthly["tokens_total"][k] += v
            monthly["prompts_count"] += d.get("prompts_count", 0)

    monthly["by_event"] = dict(monthly["by_event"])
    monthly["tools_called"] = dict(monthly["tools_called"].most_common(20))
    monthly["skills_called"] = dict(monthly["skills_called"].most_common(20))
    monthly["cache_hit_ratio"] = _cache_hit_ratio(monthly["tokens_total"])
    return monthly


def write_daily(target_date: date) -> Path:
    data = aggregate_daily(target_date)
    out = PLUGIN_ROOT / "audit" / f"telemetry-daily-{target_date:%Y%m%d}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def write_monthly(year: int, month: int) -> Path:
    data = aggregate_monthly(year, month)
    out = PLUGIN_ROOT / "audit" / f"telemetry-monthly-{year:04d}{month:02d}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def purge_old() -> dict:
    """raw NDJSON 30일 초과 entry 제거. daily/monthly TTL 적용."""
    removed = {"raw_lines": 0, "daily_files": 0, "monthly_files": 0}
    audit_dir = PLUGIN_ROOT / "audit"

    # raw NDJSON: 30일 초과 라인 필터링
    if TELEMETRY_PATH.exists():
        cutoff = datetime.now(timezone.utc) - timedelta(days=RAW_TTL_DAYS)
        kept = []
        with TELEMETRY_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                    ts = datetime.fromisoformat(e.get("ts", "").replace("Z", "+00:00"))
                    if ts >= cutoff:
                        kept.append(line)
                    else:
                        removed["raw_lines"] += 1
                except Exception:
                    kept.append(line)  # 알 수 없는 라인 보존
        TELEMETRY_PATH.write_text("".join(kept), encoding="utf-8")

    # daily: 90일 초과 삭제
    if audit_dir.exists():
        cutoff_daily = datetime.now(timezone.utc) - timedelta(days=DAILY_TTL_DAYS)
        for p in audit_dir.glob("telemetry-daily-*.json"):
            if datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc) < cutoff_daily:
                p.unlink()
                removed["daily_files"] += 1

    # monthly: 365일 초과 삭제
    if audit_dir.exists():
        cutoff_monthly = datetime.now(timezone.utc) - timedelta(days=MONTHLY_TTL_DAYS)
        for p in audit_dir.glob("telemetry-monthly-*.json"):
            if datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc) < cutoff_monthly:
                p.unlink()
                removed["monthly_files"] += 1

    return removed


def _cache_hit_ratio(tokens: dict) -> float:
    total = tokens.get("input", 0) + tokens.get("cache_read", 0)
    if total <= 0:
        return 0.0
    return round(tokens.get("cache_read", 0) / total, 3)


def _empty_daily(d: date) -> dict:
    return {
        "date": d.isoformat(),
        "by_event": {},
        "prompts_count": 0,
        "prompt_chars_total": 0,
        "tools_called": {},
        "skills_called": {},
        "tokens_total": {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0},
        "latency_stats": {},
        "cache_hit_ratio": 0.0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="aiden-auto telemetry analyzer")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_daily = sub.add_parser("daily")
    p_daily.add_argument("date", nargs="?", default=None, help="YYYY-MM-DD (default: yesterday)")
    p_monthly = sub.add_parser("monthly")
    p_monthly.add_argument("month", nargs="?", default=None, help="YYYY-MM (default: this month)")
    sub.add_parser("purge")
    args = parser.parse_args(argv)

    if args.cmd == "daily":
        d = date.fromisoformat(args.date) if args.date else date.today() - timedelta(days=1)
        out = write_daily(d)
        print(f"daily aggregation written: {out}")
    elif args.cmd == "monthly":
        if args.month:
            y, m = args.month.split("-")
            y, m = int(y), int(m)
        else:
            today = date.today()
            y, m = today.year, today.month
        out = write_monthly(y, m)
        print(f"monthly aggregation written: {out}")
    elif args.cmd == "purge":
        removed = purge_old()
        print(f"purged: {removed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

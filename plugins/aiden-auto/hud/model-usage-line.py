#!/usr/bin/env python3
"""Model-by-model token usage statusline component.

Reads {transcript_path, session_id} from stdin JSON, parses transcript JSONL
incrementally (byte-offset cache), aggregates tokens by model, prints a SINGLE
line with three tier groups separated by '|'. Model identity is encoded by
color only (opus=white, sonnet=pink, haiku=green). Cost is omitted.

Output format (one line):
  4.3k 336.8k 50.1m 1.9m|43.8k 676.0k 276.3m 6.2m|166.1k 6.2k 0 0
  ^^^^^^^^^^^^^^^^^^^^^ ^^^^^^^^^^^^^^^^^^^^^^^^^ ^^^^^^^^^^^^^^^
   opus (white)          sonnet (pink)            haiku (green)

Numbers (per group): input, output, cache_read, cache_write
Cache: ~/.claude/.model-usage-cache/<session_id>.json
"""
import os
import sys
import json
from pathlib import Path
from collections import defaultdict

# ---- Pricing (USD per 1M tokens) ----
# Anthropic public list price; cache_write = base * 1.25, cache_read = base * 0.10
PRICES = {
    "opus":   {"in": 15.0, "out": 75.0, "cw": 18.75, "cr": 1.50},
    "sonnet": {"in":  3.0, "out": 15.0, "cw":  3.75, "cr": 0.30},
    "haiku":  {"in":  1.0, "out":  5.0, "cw":  1.25, "cr": 0.10},
}
WEB_SEARCH_COST_USD = 0.01  # $10 per 1000 queries

# Always-display tier order (aiden-auto v28.1 3-tier visibility)
TIER_ORDER = ["opus", "sonnet", "haiku"]

CACHE_DIR = Path.home() / ".claude" / ".model-usage-cache"

# ANSI colors (256-color for accurate pink)
WHITE  = "\x1b[97m"          # opus
PINK   = "\x1b[38;5;213m"    # sonnet (hot pink)
GREEN  = "\x1b[92m"          # haiku
YELLOW = "\x1b[93m"          # cost
RESET  = "\x1b[0m"

TIER_COLOR = {
    "opus":   WHITE,
    "sonnet": PINK,
    "haiku":  GREEN,
}


def family(model_id: str) -> str:
    m = (model_id or "").lower()
    if "opus" in m:   return "opus"
    if "haiku" in m:  return "haiku"
    if "sonnet" in m: return "sonnet"
    return "sonnet"  # safe fallback


def fmt_tok(n: int) -> str:
    n = int(n or 0)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}m"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def empty_agg():
    return {"in": 0, "out": 0, "cw": 0, "cr": 0, "ws": 0}


def parse_text(text: str, agg: dict) -> None:
    """Parse JSONL text, accumulate usage into agg keyed by model id."""
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
        model = msg.get("model") or "unknown"
        usage = msg.get("usage") or {}
        if not isinstance(usage, dict):
            continue
        a = agg[model]
        a["in"]  += int(usage.get("input_tokens", 0) or 0)
        a["out"] += int(usage.get("output_tokens", 0) or 0)
        a["cw"]  += int(usage.get("cache_creation_input_tokens", 0) or 0)
        a["cr"]  += int(usage.get("cache_read_input_tokens", 0) or 0)
        # WebSearch counter (server_tool_use shape varies by API version)
        stu = usage.get("server_tool_use")
        if isinstance(stu, dict):
            a["ws"] += int(stu.get("web_search_requests", 0) or 0)
        # Fallback: scan content for server_tool_use / tool_use WebSearch entries
        # only if usage didn't report it
        elif isinstance(msg.get("content"), list):
            for item in msg["content"]:
                if not isinstance(item, dict):
                    continue
                t = item.get("type")
                name = (item.get("name") or "").lower()
                if t == "server_tool_use" and name in ("web_search", "websearch"):
                    a["ws"] += 1
                elif t == "tool_use" and name == "websearch":
                    a["ws"] += 1


def load_cache(sid: str):
    if not sid:
        return None
    p = CACHE_DIR / f"{sid}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_cache(sid: str, offset: int, agg: dict) -> None:
    if not sid:
        return
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        p = CACHE_DIR / f"{sid}.json"
        p.write_text(
            json.dumps({"offset": int(offset), "agg": {k: dict(v) for k, v in agg.items()}}),
            encoding="utf-8",
        )
    except Exception:
        pass


def main() -> None:
    try:
        raw = sys.stdin.read()
        meta = json.loads(raw) if raw.strip() else {}
    except Exception:
        return

    tp = meta.get("transcript_path")
    sid = meta.get("session_id") or ""
    if not tp or not os.path.exists(tp):
        return

    try:
        file_size = os.path.getsize(tp)
    except Exception:
        return

    cache = load_cache(sid)
    agg = defaultdict(empty_agg)
    start_offset = 0

    # Reuse cache if offset still valid (file only grew)
    if cache and isinstance(cache.get("offset"), int) and cache["offset"] <= file_size:
        start_offset = cache["offset"]
        for k, v in (cache.get("agg") or {}).items():
            if isinstance(v, dict):
                for kk in ("in", "out", "cw", "cr", "ws"):
                    agg[k][kk] = int(v.get(kk, 0) or 0)
    # If file shrank (very rare), restart from 0
    elif cache:
        start_offset = 0

    try:
        with open(tp, "rb") as f:
            f.seek(start_offset)
            chunk = f.read().decode("utf-8", errors="ignore")
    except Exception:
        return

    parse_text(chunk, agg)
    save_cache(sid, file_size, agg)

    # Merge sub-agent transcripts (.../<sid>/subagents/*.jsonl).
    # Sub-agents (Explore, Task, etc.) write to a sibling directory and are
    # not part of the main transcript, but their token usage is billed.
    try:
        tp_path = Path(tp)
        sub_dir = tp_path.parent / tp_path.stem / "subagents"
        if sub_dir.is_dir():
            sub_agg = defaultdict(empty_agg)
            for sub_jsonl in sub_dir.glob("*.jsonl"):
                try:
                    with open(sub_jsonl, "rb") as sf:
                        sub_text = sf.read().decode("utf-8", errors="ignore")
                    parse_text(sub_text, sub_agg)
                except Exception:
                    continue
            for model, a in sub_agg.items():
                for k in ("in", "out", "cw", "cr", "ws"):
                    agg[model][k] += int(a.get(k, 0) or 0)
    except Exception:
        pass

    # Aggregate by tier (merge multiple model_id variants of the same family)
    tier_agg = {t: empty_agg() for t in TIER_ORDER}

    for model, a in agg.items():
        if not isinstance(model, str) or model.startswith("<"):
            continue
        tier = family(model)
        if tier not in tier_agg:
            continue
        for k in ("in", "out", "cw", "cr", "ws"):
            tier_agg[tier][k] += int(a.get(k, 0) or 0)

    # Single line: three tier groups separated by '|', identity by color only.
    # Each group = "input output cache_read cache_write" + yellow integer cost
    groups = []
    for tier in TIER_ORDER:
        a = tier_agg[tier]
        p = PRICES[tier]
        cost = (
            a["in"]  * p["in"] +
            a["out"] * p["out"] +
            a["cw"]  * p["cw"] +
            a["cr"]  * p["cr"]
        ) / 1_000_000
        cost += a["ws"] * WEB_SEARCH_COST_USD
        nums = " ".join([
            fmt_tok(a["in"]),
            fmt_tok(a["out"]),
            fmt_tok(a["cr"]),
            fmt_tok(a["cw"]),
        ])
        groups.append(f"{TIER_COLOR[tier]}{nums}{RESET} {YELLOW}${int(cost)}{RESET}")
    print("|".join(groups))


if __name__ == "__main__":
    main()

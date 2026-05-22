#!/usr/bin/env python3
"""Prompt Intelligence — history.jsonl 기반 프롬프트 패턴 분석기."""

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

# Paths
HISTORY_PATH = Path.home() / ".claude" / "history.jsonl"
DATA_DIR = Path(__file__).parent.parent / "data"
WATERMARK_PATH = DATA_DIR / "prompt-watermark.json"
STATS_PATH = DATA_DIR / "prompt-stats.json"

# Category rules (order matters — first match wins)
CATEGORY_RULES = [
    (re.compile(r"^/"), "command"),
    (re.compile(r"fix|bug|오류|에러|수정", re.IGNORECASE), "fix"),
    (re.compile(r"feat|add|추가|만들|생성|구현", re.IGNORECASE), "feature"),
    (re.compile(r"\?|어떻게|왜|뭐|설명|알려", re.IGNORECASE), "question"),
    (re.compile(r"config|설정|hook|rule", re.IGNORECASE), "config"),
    (re.compile(r"research|조사|분석|리서치", re.IGNORECASE), "research"),
]

# Skill pattern
SKILL_PATTERN = re.compile(r"^(/\S+)")

# Keyword extraction: Korean nouns (2+ chars) and English tokens (3+ chars)
KEYWORD_PATTERN = re.compile(r"[가-힣]{2,}|[a-zA-Z_]{3,}")


def categorize(prompt: str) -> str:
    """Categorize a prompt by keyword rules."""
    for pattern, category in CATEGORY_RULES:
        if pattern.search(prompt):
            return category
    return "general"


def extract_skill(prompt: str) -> str | None:
    """Extract skill/command name from prompt (e.g., '/auto' from '/auto --eco')."""
    m = SKILL_PATTERN.match(prompt.strip())
    return m.group(1) if m else None


def extract_keywords(prompt: str) -> list[str]:
    """Extract meaningful keywords from prompt text."""
    return KEYWORD_PATTERN.findall(prompt)


def get_time_slot(timestamp_ms: int) -> str:
    """Map timestamp to time-of-day slot."""
    hour = datetime.fromtimestamp(timestamp_ms / 1000).hour
    if 6 <= hour < 12:
        return "morning"
    elif 12 <= hour < 18:
        return "afternoon"
    elif 18 <= hour < 24:
        return "evening"
    else:
        return "night"


def load_watermark() -> dict:
    """Load watermark (last processed state)."""
    if WATERMARK_PATH.exists():
        return json.loads(WATERMARK_PATH.read_text(encoding="utf-8"))
    return {"last_timestamp": 0, "last_count": 0, "last_analyzed": None}


def save_watermark(timestamp: int, count: int):
    """Save watermark after analysis."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "last_timestamp": timestamp,
        "last_count": count,
        "last_analyzed": datetime.now().isoformat(timespec="seconds"),
    }
    WATERMARK_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_stats() -> dict:
    """Load cumulative stats."""
    if STATS_PATH.exists():
        return json.loads(STATS_PATH.read_text(encoding="utf-8"))
    return {
        "total_analyzed": 0,
        "categories": {},
        "skills": {},
        "top_keywords": [],
        "time_slots": {},
        "repeats": {},
        "sessions": {},
        "last_updated": None,
    }


def save_stats(stats: dict):
    """Save cumulative stats."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    stats["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    # Convert top_keywords from Counter to sorted list
    if isinstance(stats.get("top_keywords"), Counter):
        stats["top_keywords"] = stats["top_keywords"].most_common(20)
    STATS_PATH.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")


def load_prompts(project_filter: str | None = None, after_timestamp: int = 0) -> list[dict]:
    """Load prompts from history.jsonl, optionally filtering by project and timestamp."""
    prompts = []
    if not HISTORY_PATH.exists():
        return prompts

    with open(HISTORY_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            ts = entry.get("timestamp", 0)
            if ts <= after_timestamp:
                continue

            if project_filter:
                proj = entry.get("project", "")
                # Normalize paths for comparison
                if proj.replace("\\", "/").rstrip("/") != project_filter.replace("\\", "/").rstrip("/"):
                    continue

            display = entry.get("display", "").strip()
            if not display:
                continue

            prompts.append({
                "display": display,
                "timestamp": ts,
                "sessionId": entry.get("sessionId", ""),
                "project": entry.get("project", ""),
            })

    return prompts


def normalize_prompt(text: str) -> str:
    """Normalize prompt for repeat detection."""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    # Remove file paths and hashes
    text = re.sub(r"[a-f0-9]{7,}", "", text)
    text = re.sub(r"[A-Z]:\\[^\s]+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"/[^\s]+\.[a-z]+", "", text)
    return text.strip()


def analyze_prompts(prompts: list[dict]) -> dict:
    """Analyze a batch of prompts and return stats delta."""
    categories = Counter()
    skills = Counter()
    keywords = Counter()
    time_slots = Counter()
    sessions = Counter()
    normalized = Counter()

    for p in prompts:
        display = p["display"]

        # Category
        categories[categorize(display)] += 1

        # Skill usage
        skill = extract_skill(display)
        if skill:
            skills[skill] += 1

        # Keywords
        for kw in extract_keywords(display):
            keywords[kw] += 1

        # Time slot
        time_slots[get_time_slot(p["timestamp"])] += 1

        # Session
        sessions[p["sessionId"]] += 1

        # Repeat detection
        norm = normalize_prompt(display)
        if len(norm) > 5:  # Skip very short prompts
            normalized[norm] += 1

    repeats = {k: v for k, v in normalized.items() if v >= 3}

    return {
        "count": len(prompts),
        "categories": dict(categories),
        "skills": dict(skills),
        "keywords": keywords,
        "time_slots": dict(time_slots),
        "repeats": repeats,
        "session_count": len(sessions),
        "sessions": dict(sessions),
    }


def merge_stats(existing: dict, delta: dict) -> dict:
    """Merge delta stats into existing cumulative stats."""
    # Categories
    cats = Counter(existing.get("categories", {}))
    cats.update(delta["categories"])
    existing["categories"] = dict(cats)

    # Skills
    sk = Counter(existing.get("skills", {}))
    sk.update(delta["skills"])
    existing["skills"] = dict(sk)

    # Keywords — merge and keep top 20
    kw = Counter()
    if isinstance(existing.get("top_keywords"), list):
        for item in existing["top_keywords"]:
            if isinstance(item, list) and len(item) == 2:
                kw[item[0]] = item[1]
    kw.update(delta["keywords"])
    existing["top_keywords"] = kw.most_common(20)

    # Time slots
    ts = Counter(existing.get("time_slots", {}))
    ts.update(delta["time_slots"])
    existing["time_slots"] = dict(ts)

    # Repeats — merge
    reps = existing.get("repeats", {})
    for k, v in delta["repeats"].items():
        reps[k] = reps.get(k, 0) + v
    existing["repeats"] = {k: v for k, v in reps.items() if v >= 3}

    # Total
    existing["total_analyzed"] = existing.get("total_analyzed", 0) + delta["count"]

    # Sessions
    sess = Counter(existing.get("sessions", {}))
    sess.update(delta["sessions"])
    existing["sessions"] = dict(sess)

    return existing


def run_stats(project_filter: str | None = None, full: bool = False, as_json: bool = False) -> dict:
    """Run incremental or full stats analysis."""
    watermark = load_watermark()
    after_ts = 0 if full else watermark["last_timestamp"]

    prompts = load_prompts(project_filter=project_filter, after_timestamp=after_ts)

    if full:
        stats = {
            "total_analyzed": 0, "categories": {}, "skills": {},
            "top_keywords": [], "time_slots": {}, "repeats": {},
            "sessions": {}, "last_updated": None,
        }
    else:
        stats = load_stats()

    if prompts:
        delta = analyze_prompts(prompts)
        stats = merge_stats(stats, delta)
        max_ts = max(p["timestamp"] for p in prompts)
        save_watermark(max_ts, stats["total_analyzed"])
        save_stats(stats)
    else:
        delta = {"count": 0}

    result = {
        "new_count": delta["count"],
        "total": stats["total_analyzed"],
        "project": project_filter or "(all)",
        "stats": stats,
    }

    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        _print_report(result)

    return result


def get_new_prompts(n: int = 50, project_filter: str | None = None) -> list[dict]:
    """Get N most recent prompts after watermark."""
    watermark = load_watermark()
    prompts = load_prompts(project_filter=project_filter, after_timestamp=watermark["last_timestamp"])
    # Return most recent N
    prompts.sort(key=lambda x: x["timestamp"], reverse=True)
    return prompts[:n]


def _print_report(result: dict):
    """Print human-readable report to terminal."""
    # Force UTF-8 output on Windows
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    stats = result["stats"]
    cats = stats.get("categories", {})
    skills = stats.get("skills", {})
    total = result["total"]

    print(f"\n━━━ Prompt Intelligence - {datetime.now().strftime('%Y-%m-%d')} ━━━")
    print(f"신규: {result['new_count']}건 | 누적: {total:,}건 ({result['project']})")

    # Category distribution
    if cats:
        print("\n[카테고리 분포]")
        max_val = max(cats.values()) if cats else 1
        for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
            bar_len = int((count / max_val) * 16)
            bar = "\u2588" * bar_len
            pct = (count / total * 100) if total else 0
            print(f"  {cat:<10} {bar:<16} {count}건 ({pct:.0f}%)")

    # Skill usage TOP 5
    if skills:
        print("\n[스킬 사용 TOP 5]")
        top5 = sorted(skills.items(), key=lambda x: -x[1])[:5]
        max_val = top5[0][1] if top5 else 1
        for skill, count in top5:
            bar_len = int((count / max_val) * 12)
            bar = "\u2588" * bar_len
            print(f"  {skill:<10} {bar:<12} {count}회")

    # Repeats
    repeats = stats.get("repeats", {})
    if repeats:
        print("\n[반복 패턴 TOP 3]")
        top3 = sorted(repeats.items(), key=lambda x: -x[1])[:3]
        for i, (prompt, count) in enumerate(top3, 1):
            display = prompt[:40] + "..." if len(prompt) > 40 else prompt
            print(f"  {i}. \"{display}\" \u2014 {count}회")

    # Time slots
    ts = stats.get("time_slots", {})
    if ts:
        print("\n[시간대 분포]")
        slot_names = {"morning": "아침(6-12)", "afternoon": "오후(12-18)",
                      "evening": "저녁(18-24)", "night": "새벽(0-6)"}
        for slot in ["morning", "afternoon", "evening", "night"]:
            count = ts.get(slot, 0)
            pct = (count / total * 100) if total else 0
            print(f"  {slot_names.get(slot, slot):<14} {count}건 ({pct:.0f}%)")

    # Keywords TOP 10
    kw = stats.get("top_keywords", [])
    if kw:
        print("\n[키워드 TOP 10]")
        for word, count in kw[:10]:
            print(f"  {word}: {count}")


def main():
    parser = argparse.ArgumentParser(description="Prompt Intelligence Analyzer")
    parser.add_argument("--stats", action="store_true", help="Run incremental analysis")
    parser.add_argument("--full", action="store_true", help="Full re-analysis (reset watermark)")
    parser.add_argument("--project", type=str, default=None, help="Filter by project path")
    parser.add_argument("--new-prompts", type=int, default=0, metavar="N",
                        help="Show N newest prompts after watermark")
    parser.add_argument("--json", action="store_true", help="JSON output for pipeline")
    args = parser.parse_args()

    if args.new_prompts > 0:
        prompts = get_new_prompts(n=args.new_prompts, project_filter=args.project)
        if args.json:
            print(json.dumps([p["display"] for p in prompts], indent=2, ensure_ascii=False))
        else:
            for p in prompts:
                ts = datetime.fromtimestamp(p["timestamp"] / 1000).strftime("%m-%d %H:%M")
                print(f"  [{ts}] {p['display'][:80]}")
        return

    if args.stats or args.full:
        run_stats(project_filter=args.project, full=args.full, as_json=args.json)
        return

    parser.print_help()


if __name__ == "__main__":
    main()

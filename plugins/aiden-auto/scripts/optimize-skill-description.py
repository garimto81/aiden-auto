#!/usr/bin/env python3
"""Optimize a skill's frontmatter `description` for trigger accuracy.

Self-contained, environment-fixed replacement for the skill-creator
description-optimization loop (run_eval.py + improve_description.py +
run_loop.py). The upstream scripts live in a read-only third-party plugin
cache and break here for two reasons; both are fixed in this file:

  1. Windows socket bug (was: WinError 10038)
     Upstream used `select.select([process.stdout], ...)` + `os.read(fileno)`.
     On Windows `select` only accepts sockets, not subprocess pipes, so every
     query raised WinError 10038 and was scored as "did not trigger".
     Fix: read the `claude -p` stream with a background thread + readline,
     which is cross-platform.

  2. OAuth-only auth (was: "Could not resolve authentication method")
     Upstream improve step used the Anthropic SDK (`anthropic.Anthropic()`),
     which requires ANTHROPIC_API_KEY. This environment is browser-OAuth only,
     API keys prohibited.
     Fix: call the `claude` CLI (uses the logged-in OAuth session) for BOTH
     trigger evaluation and description improvement.

Lives in ~/.claude/scripts/ (canonical SSOT) so it survives plugin updates and
auto-replicates to other machines. Device-agnostic: no hardcoded paths.

Eval set JSON: a list of {"query": str, "should_trigger": bool}.

Usage:
  python optimize-skill-description.py \
      --eval-set trigger-eval.json \
      --skill-path ~/.claude/skills/root-cause \
      --model claude-opus-4-8 \
      [--max-iterations 3] [--runs-per-query 2] [--holdout 0.4] \
      [--num-workers 4] [--timeout 45] [--apply] [--verbose]

Prints a JSON result with best_description. With --apply, writes the best
description back into the skill's SKILL.md frontmatter (as a single
double-quoted YAML scalar).
"""

import argparse
import json
import os
import random
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


# --------------------------------------------------------------------------- #
# SKILL.md parsing / writing
# --------------------------------------------------------------------------- #

def parse_skill_md(skill_path: Path) -> tuple[str, str, str]:
    """Return (name, description, full_content) from a skill's SKILL.md."""
    md = (skill_path / "SKILL.md").read_text(encoding="utf-8")
    name, description = skill_path.name, ""
    lines = md.splitlines()
    if not lines or lines[0].strip() != "---":
        return name, description, md

    close = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if close is None:
        return name, description, md
    front = "\n".join(lines[1:close])

    try:
        import yaml  # type: ignore
        data = yaml.safe_load(front) or {}
        name = str(data.get("name", name))
        description = str(data.get("description", "") or "").strip()
        return name, description, md
    except Exception:
        pass

    # Minimal fallback parser (name + folded/inline description).
    fl = front.splitlines()
    i = 0
    while i < len(fl):
        line = fl[i]
        if line.startswith("name:"):
            name = line.split(":", 1)[1].strip() or name
        elif line.startswith("description:"):
            rest = line.split(":", 1)[1].strip()
            if rest and rest not in (">", "|", ">-", "|-", ">+", "|+"):
                description = rest.strip().strip('"')
            else:
                body = []
                j = i + 1
                while j < len(fl) and (fl[j].startswith("  ") or fl[j].startswith("\t")):
                    body.append(fl[j].strip())
                    j += 1
                description = " ".join(body)
                i = j - 1
        i += 1
    return name, description, md


def apply_description(skill_path: Path, new_description: str) -> None:
    """Replace the frontmatter description with a single double-quoted scalar.

    json.dumps produces a valid YAML double-quoted string (JSON string syntax
    is a subset of YAML flow scalars), so all quotes/unicode are escaped safely.
    """
    skill_md = skill_path / "SKILL.md"
    lines = skill_md.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise RuntimeError("SKILL.md has no opening frontmatter fence")
    close = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if close is None:
        raise RuntimeError("SKILL.md frontmatter is not terminated")

    out = [lines[0]]
    i, replaced = 1, False
    while i < close:
        line = lines[i]
        if line.startswith("description:") and not replaced:
            out.append("description: " + json.dumps(new_description, ensure_ascii=False))
            replaced = True
            i += 1
            # skip the old description's indented continuation lines
            while i < close and (lines[i].startswith("  ") or lines[i].startswith("\t")):
                i += 1
            continue
        out.append(line)
        i += 1
    if not replaced:
        out.append("description: " + json.dumps(new_description, ensure_ascii=False))
    out.extend(lines[close:])
    skill_md.write_text("\n".join(out) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# Trigger evaluation (Windows-safe: thread reader, no select/os.read)
# --------------------------------------------------------------------------- #

def find_project_root() -> Path:
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / ".claude").is_dir():
            return parent
    return current


def _detect_from_line(line: str, state: dict, clean_name: str):
    """Process one stream-json line. Return True (triggered), False (decided
    not triggered) or None (inconclusive — keep reading)."""
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return None

    etype = event.get("type")
    if etype == "stream_event":
        se = event.get("event", {})
        se_type = se.get("type", "")
        if se_type == "content_block_start":
            cb = se.get("content_block", {})
            if cb.get("type") == "tool_use":
                tool_name = cb.get("name", "")
                if tool_name in ("Skill", "Read"):
                    state["pending_tool_name"] = tool_name
                    state["accumulated_json"] = ""
                else:
                    return False
        elif se_type == "content_block_delta" and state.get("pending_tool_name"):
            delta = se.get("delta", {})
            if delta.get("type") == "input_json_delta":
                state["accumulated_json"] += delta.get("partial_json", "")
                if clean_name in state["accumulated_json"]:
                    return True
        elif se_type in ("content_block_stop", "message_stop"):
            if state.get("pending_tool_name"):
                return clean_name in state.get("accumulated_json", "")
            if se_type == "message_stop":
                return False
    elif etype == "assistant":
        message = event.get("message", {})
        for content_item in message.get("content", []):
            if content_item.get("type") != "tool_use":
                continue
            tool_name = content_item.get("name", "")
            tool_input = content_item.get("input", {})
            if tool_name == "Skill" and clean_name in tool_input.get("skill", ""):
                return True
            if tool_name == "Read" and clean_name in tool_input.get("file_path", ""):
                return True
            return False
    elif etype == "result":
        return False
    return None


def run_single_query(query, skill_name, skill_description, timeout, project_root, model=None) -> bool:
    """Run one query through `claude -p` and report whether the skill triggered.

    Writes a temporary command file into .claude/commands/ so the skill shows
    up in available_skills, then streams the response and detects whether
    Claude invokes Skill/Read on that command. Reads the stream in a background
    thread (cross-platform) instead of select/os.read (Windows-incompatible).
    """
    import uuid
    unique_id = uuid.uuid4().hex[:8]
    clean_name = f"{skill_name}-skill-{unique_id}"
    project_commands_dir = Path(project_root) / ".claude" / "commands"
    command_file = project_commands_dir / f"{clean_name}.md"

    process = None
    try:
        project_commands_dir.mkdir(parents=True, exist_ok=True)
        indented_desc = "\n  ".join(skill_description.split("\n"))
        command_file.write_text(
            f"---\ndescription: |\n  {indented_desc}\n---\n\n"
            f"# {skill_name}\n\nThis skill handles: {skill_description}\n",
            encoding="utf-8",
        )

        cmd = ["claude", "-p", query,
               "--output-format", "stream-json", "--verbose",
               "--include-partial-messages"]
        if model:
            cmd.extend(["--model", model])

        # Drop CLAUDECODE so nesting `claude -p` inside a CC session is allowed.
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            cwd=project_root, env=env, text=True,
            encoding="utf-8", errors="replace", bufsize=1,
        )

        result = {"triggered": False}
        state = {"pending_tool_name": None, "accumulated_json": ""}

        def reader():
            try:
                for raw_line in process.stdout:
                    line = raw_line.strip()
                    if not line:
                        continue
                    verdict = _detect_from_line(line, state, clean_name)
                    if verdict is not None:
                        result["triggered"] = verdict
                        return
            except Exception:
                pass

        t = threading.Thread(target=reader, daemon=True)
        t.start()
        t.join(timeout)
        return result["triggered"]
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            try:
                process.wait(timeout=5)
            except Exception:
                pass
        if command_file.exists():
            command_file.unlink()


def run_single_query_installed(query, match_token, timeout, project_root, model=None) -> bool:
    """Measure whether the ALREADY-INSTALLED skill triggers, WITHOUT injecting a
    stub command. Detects Skill/Read tool calls whose target contains
    match_token (e.g. the skill name).

    Use this to honestly measure a skill that is already registered: the stub
    approach is shadowed by the real skill in that case, so trigger rates read 0
    even for queries that genuinely fire the skill. Writes no files, so it never
    pollutes the .claude/commands namespace.
    """
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    cmd = ["claude", "-p", query, "--output-format", "stream-json",
           "--verbose", "--include-partial-messages"]
    if model:
        cmd.extend(["--model", model])
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        cwd=project_root, env=env, text=True,
        encoding="utf-8", errors="replace", bufsize=1,
    )
    result = {"triggered": False}
    state = {"pending_tool_name": None, "accumulated_json": ""}

    def reader():
        try:
            for raw_line in process.stdout:
                line = raw_line.strip()
                if not line:
                    continue
                verdict = _detect_from_line(line, state, match_token)
                if verdict is not None:
                    result["triggered"] = verdict
                    return
        except Exception:
            pass

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    t.join(timeout)
    if process.poll() is None:
        process.kill()
        try:
            process.wait(timeout=5)
        except Exception:
            pass
    return result["triggered"]


def run_measure(eval_set, match_token, num_workers, timeout, project_root,
                runs_per_query, trigger_threshold, model) -> dict:
    """One measurement pass over the eval set against the installed skill."""
    query_triggers: dict[str, list[bool]] = {}
    query_items: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        fut_to_q = {}
        for item in eval_set:
            for _ in range(runs_per_query):
                fut = executor.submit(run_single_query_installed, item["query"],
                                      match_token, timeout, str(project_root), model)
                fut_to_q[fut] = item["query"]
                query_items[item["query"]] = item
        for fut in as_completed(fut_to_q):
            q = fut_to_q[fut]
            query_triggers.setdefault(q, [])
            try:
                query_triggers[q].append(fut.result())
            except Exception as e:
                print(f"Warning: query failed: {e}", file=sys.stderr)
                query_triggers[q].append(False)

    results = []
    for query, triggers in query_triggers.items():
        item = query_items[query]
        rate = sum(triggers) / len(triggers)
        should = item["should_trigger"]
        did_pass = (rate >= trigger_threshold) if should else (rate < trigger_threshold)
        results.append({"query": query, "should_trigger": should, "trigger_rate": rate,
                        "triggers": sum(triggers), "runs": len(triggers), "pass": did_pass})
    passed = sum(1 for r in results if r["pass"])
    return {"results": results, "summary": {"total": len(results), "passed": passed, "failed": len(results) - passed}}


def run_eval(eval_set, skill_name, description, num_workers, timeout,
             project_root, runs_per_query=1, trigger_threshold=0.5, model=None) -> dict:
    """Run the full eval set and return pass/fail per query."""
    query_triggers: dict[str, list[bool]] = {}
    query_items: dict[str, dict] = {}

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        future_to_query = {}
        for item in eval_set:
            for _ in range(runs_per_query):
                fut = executor.submit(
                    run_single_query, item["query"], skill_name, description,
                    timeout, str(project_root), model,
                )
                future_to_query[fut] = item["query"]
                query_items[item["query"]] = item

        for fut in as_completed(future_to_query):
            q = future_to_query[fut]
            query_triggers.setdefault(q, [])
            try:
                query_triggers[q].append(fut.result())
            except Exception as e:
                print(f"Warning: query failed: {e}", file=sys.stderr)
                query_triggers[q].append(False)

    results = []
    for query, triggers in query_triggers.items():
        item = query_items[query]
        rate = sum(triggers) / len(triggers)
        should = item["should_trigger"]
        did_pass = (rate >= trigger_threshold) if should else (rate < trigger_threshold)
        results.append({
            "query": query, "should_trigger": should, "trigger_rate": rate,
            "triggers": sum(triggers), "runs": len(triggers), "pass": did_pass,
        })

    passed = sum(1 for r in results if r["pass"])
    return {
        "skill_name": skill_name, "description": description, "results": results,
        "summary": {"total": len(results), "passed": passed, "failed": len(results) - passed},
    }


# --------------------------------------------------------------------------- #
# Description improvement (OAuth: via `claude` CLI, no SDK / API key)
# --------------------------------------------------------------------------- #

def call_claude(prompt: str, model: str, timeout: int = 300) -> str:
    """Generate text via the `claude` CLI using the logged-in OAuth session."""
    cmd = ["claude", "-p", prompt]
    if model:
        cmd.extend(["--model", model])
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    r = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8",
        errors="replace", env=env, timeout=timeout,
    )
    if r.returncode != 0:
        raise RuntimeError(f"claude CLI failed (exit {r.returncode}): {(r.stderr or '').strip()[:500]}")
    return r.stdout or ""


def _extract_description(text: str) -> str:
    m = re.search(r"<new_description>(.*?)</new_description>", text, re.DOTALL)
    return (m.group(1) if m else text).strip().strip('"')


def improve_description(skill_name, skill_content, current_description,
                        eval_results, history, model) -> str:
    """Ask Claude (via CLI) for a better description based on the failures."""
    failed = [r for r in eval_results["results"] if r["should_trigger"] and not r["pass"]]
    false_t = [r for r in eval_results["results"] if not r["should_trigger"] and not r["pass"]]

    prompt = f"""You are optimizing a skill description for a Claude Code skill called "{skill_name}". The description appears in Claude's available_skills list; Claude decides whether to invoke the skill based on the title and this description. Goal: trigger for relevant queries, not for irrelevant ones.

Current description:
<current_description>
"{current_description}"
</current_description>

"""
    if failed:
        prompt += "FAILED TO TRIGGER (should have, but didn't):\n"
        for r in failed:
            prompt += f'  - "{r["query"]}" (triggered {r["triggers"]}/{r["runs"]})\n'
        prompt += "\n"
    if false_t:
        prompt += "FALSE TRIGGERS (triggered but shouldn't have):\n"
        for r in false_t:
            prompt += f'  - "{r["query"]}" (triggered {r["triggers"]}/{r["runs"]})\n'
        prompt += "\n"
    if history:
        prompt += "PREVIOUS ATTEMPTS (do NOT repeat — try something structurally different):\n"
        for h in history:
            prompt += f'  - "{h["description"]}" (train {h.get("passed", "?")}/{h.get("total", "?")})\n'
        prompt += "\n"

    prompt += f"""Skill content (context on what the skill does):
<skill_content>
{skill_content}
</skill_content>

Write an improved description. Generalize from failures to broader categories of user intent — do NOT produce an ever-growing list of specific queries (avoid overfitting; keep it ~100-200 words max). Tips: phrase imperatively ("Use this skill for..."), focus on user intent over implementation, make it distinctive vs other skills. Preserve this skill's language style (it may be Korean). Respond with ONLY the new description inside <new_description> tags."""

    desc = _extract_description(call_claude(prompt, model))

    if len(desc) > 1024:
        shorten = (
            f"This description is {len(desc)} characters, over the hard 1024 limit. "
            f"Rewrite it under 1024 characters, preserving the most important trigger "
            f"words and intent coverage. Respond with ONLY the new description in "
            f"<new_description> tags.\n\n<current_description>\n{desc}\n</current_description>"
        )
        desc = _extract_description(call_claude(shorten, model))
    return desc


# --------------------------------------------------------------------------- #
# Loop
# --------------------------------------------------------------------------- #

def split_eval_set(eval_set, holdout, seed=42):
    random.seed(seed)
    trig = [e for e in eval_set if e["should_trigger"]]
    notrig = [e for e in eval_set if not e["should_trigger"]]
    random.shuffle(trig)
    random.shuffle(notrig)
    n_trig = max(1, int(len(trig) * holdout)) if trig else 0
    n_not = max(1, int(len(notrig) * holdout)) if notrig else 0
    test = trig[:n_trig] + notrig[:n_not]
    train = trig[n_trig:] + notrig[n_not:]
    if not train:  # tiny sets: don't starve training
        train, test = eval_set, []
    return train, test


def _stats(results):
    pos = [r for r in results if r["should_trigger"]]
    neg = [r for r in results if not r["should_trigger"]]
    tp = sum(r["triggers"] for r in pos); pos_runs = sum(r["runs"] for r in pos)
    fp = sum(r["triggers"] for r in neg); neg_runs = sum(r["runs"] for r in neg)
    fn, tn = pos_runs - tp, neg_runs - fp
    total = tp + tn + fp + fn
    prec = tp / (tp + fp) if (tp + fp) else 1.0
    rec = tp / (tp + fn) if (tp + fn) else 1.0
    acc = (tp + tn) / total if total else 0.0
    return prec, rec, acc, tp + tn, total


def run_loop(eval_set, skill_path, num_workers, timeout, max_iterations,
             runs_per_query, trigger_threshold, holdout, model, verbose):
    project_root = find_project_root()
    name, original_description, content = parse_skill_md(skill_path)
    current = original_description

    if holdout > 0:
        train_set, test_set = split_eval_set(eval_set, holdout)
    else:
        train_set, test_set = eval_set, []
    if verbose:
        print(f"Split: {len(train_set)} train, {len(test_set)} test (holdout={holdout})", file=sys.stderr)

    history, exit_reason = [], "unknown"
    for iteration in range(1, max_iterations + 1):
        if verbose:
            print(f"\n{'='*60}\nIteration {iteration}/{max_iterations}\n{current}\n{'='*60}", file=sys.stderr)

        t0 = time.time()
        all_results = run_eval(train_set + test_set, name, current, num_workers,
                               timeout, project_root, runs_per_query, trigger_threshold, model)
        elapsed = time.time() - t0

        train_q = {q["query"] for q in train_set}
        tr = [r for r in all_results["results"] if r["query"] in train_q]
        te = [r for r in all_results["results"] if r["query"] not in train_q]
        train_passed = sum(1 for r in tr if r["pass"])
        test_passed = sum(1 for r in te if r["pass"])
        train_results = {"results": tr, "summary": {"passed": train_passed, "failed": len(tr) - train_passed, "total": len(tr)}}

        history.append({
            "iteration": iteration, "description": current,
            "train_passed": train_passed, "train_total": len(tr),
            "test_passed": test_passed if test_set else None, "test_total": len(te) if test_set else None,
            "passed": train_passed, "total": len(tr), "results": tr,
        })

        if verbose:
            p, rc, ac, correct, tot = _stats(tr)
            print(f"Train: {correct}/{tot} correct, precision={p:.0%} recall={rc:.0%} accuracy={ac:.0%} ({elapsed:.1f}s)", file=sys.stderr)
            for r in tr:
                print(f"  [{'PASS' if r['pass'] else 'FAIL'}] {r['triggers']}/{r['runs']} expected={r['should_trigger']}: {r['query'][:60]}", file=sys.stderr)
            if test_set:
                p, rc, ac, correct, tot = _stats(te)
                print(f"Test : {correct}/{tot} correct, precision={p:.0%} recall={rc:.0%} accuracy={ac:.0%}", file=sys.stderr)

        if train_results["summary"]["failed"] == 0:
            exit_reason = f"all_passed (iteration {iteration})"
            break
        if iteration == max_iterations:
            exit_reason = f"max_iterations ({max_iterations})"
            break

        if verbose:
            print("\nImproving description...", file=sys.stderr)
        t0 = time.time()
        current = improve_description(name, content, current, train_results,
                                      [{k: v for k, v in h.items() if not str(k).startswith("test_")} for h in history],
                                      model)
        if verbose:
            print(f"Proposed ({time.time()-t0:.1f}s): {current}", file=sys.stderr)

    if test_set:
        best = max(history, key=lambda h: (h["test_passed"] or 0, h["train_passed"]))
        best_score = f"{best['test_passed']}/{best['test_total']} (test)"
    else:
        best = max(history, key=lambda h: h["train_passed"])
        best_score = f"{best['train_passed']}/{best['train_total']} (train)"

    if verbose:
        print(f"\nExit: {exit_reason}\nBest: {best_score} (iteration {best['iteration']})", file=sys.stderr)

    return {
        "exit_reason": exit_reason,
        "original_description": original_description,
        "best_description": best["description"],
        "best_score": best_score,
        "final_description": current,
        "iterations_run": len(history),
        "train_size": len(train_set), "test_size": len(test_set),
        "history": history,
    }


def main():
    ap = argparse.ArgumentParser(description="Optimize a skill description for trigger accuracy (Windows + OAuth safe)")
    ap.add_argument("--eval-set", required=True)
    ap.add_argument("--skill-path", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--max-iterations", type=int, default=3)
    ap.add_argument("--runs-per-query", type=int, default=2)
    ap.add_argument("--trigger-threshold", type=float, default=0.5)
    ap.add_argument("--holdout", type=float, default=0.4)
    ap.add_argument("--num-workers", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=45)
    ap.add_argument("--apply", action="store_true", help="Write best_description back into SKILL.md")
    ap.add_argument("--measure-installed", action="store_true",
                    help="Measure the ALREADY-INSTALLED skill's current trigger accuracy "
                         "(no stub, no improve loop) — use when the skill is already registered")
    ap.add_argument("--match-token", default=None,
                    help="Token to match in Skill/Read tool calls (default: skill name). "
                         "Only used with --measure-installed")
    ap.add_argument("--out", default=None, help="Write the JSON result to this path")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    skill_path = Path(args.skill_path).expanduser()
    if not (skill_path / "SKILL.md").exists():
        print(f"Error: No SKILL.md at {skill_path}", file=sys.stderr)
        sys.exit(1)
    eval_set = json.loads(Path(args.eval_set).expanduser().read_text(encoding="utf-8"))

    if args.measure_installed:
        name, _, _ = parse_skill_md(skill_path)
        match_token = args.match_token or name
        project_root = find_project_root()
        if args.verbose:
            print(f"Measuring installed-skill triggering (match token: {match_token!r})", file=sys.stderr)
        m = run_measure(eval_set, match_token, args.num_workers, args.timeout,
                        project_root, args.runs_per_query, args.trigger_threshold, args.model)
        if args.verbose:
            p, rc, ac, correct, tot = _stats(m["results"])
            print(f"\nInstalled trigger accuracy: {correct}/{tot} correct, "
                  f"precision={p:.0%} recall={rc:.0%} accuracy={ac:.0%}", file=sys.stderr)
            for r in sorted(m["results"], key=lambda x: (not x["should_trigger"], x["query"])):
                print(f"  [{'PASS' if r['pass'] else 'FAIL'}] {r['triggers']}/{r['runs']} "
                      f"expected={r['should_trigger']}: {r['query'][:64]}", file=sys.stderr)
        out = {"mode": "measure_installed", "match_token": match_token, **m}
        text = json.dumps(out, indent=2, ensure_ascii=False)
        print(text)
        if args.out:
            Path(args.out).expanduser().write_text(text, encoding="utf-8")
        return

    output = run_loop(
        eval_set=eval_set, skill_path=skill_path, num_workers=args.num_workers,
        timeout=args.timeout, max_iterations=args.max_iterations,
        runs_per_query=args.runs_per_query, trigger_threshold=args.trigger_threshold,
        holdout=args.holdout, model=args.model, verbose=args.verbose,
    )

    if args.apply:
        apply_description(skill_path, output["best_description"])
        output["applied"] = True
        if args.verbose:
            print(f"\nApplied best_description to {skill_path / 'SKILL.md'}", file=sys.stderr)

    text = json.dumps(output, indent=2, ensure_ascii=False)
    print(text)
    if args.out:
        Path(args.out).expanduser().write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()

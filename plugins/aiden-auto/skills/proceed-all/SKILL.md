---
name: proceed-all
description: This skill should be used when a user asks to "create tasks and proceed all without approval", "no need approvement", "auto proceed all steps", or similar autonomous-execution patterns. It decomposes a multi-step request into discrete TaskCreate entries, executes every step sequentially without pausing for approval, reports progress inline, and delivers a final summary. Designed for users who explicitly opt into autonomous execution of routine, reversible work.
---

# /proceed-all — Autonomous Multi-Step Executor

## Purpose

To accept a user request that spans multiple discrete steps, convert it into a tracked task list, execute every step sequentially without prompting for approval between steps, and report the outcome once finished. To eliminate the friction of repeatedly typing "no need approvement" or "proceed all" on each iteration.

## When to Use

To invoke this skill when the user message contains any of the following patterns (case-insensitive, allow paraphrase):

- "create tasks and proceed all"
- "no need approve" / "no need approvement" / "don't ask for approval"
- "proceed without approval" / "proceed autonomously"
- "run all steps" / "execute all" / "do it all"
- `/proceed-all` explicit invocation
- Any combination signaling autonomous multi-step execution

To skip this skill when:

- The request is a single trivial action (direct execution is faster)
- The user explicitly asks to confirm each step
- Destructive operations dominate the workflow (defer to Claude Code's safety rules)

## Execution Contract

To guarantee predictable behavior, adhere to the following contract when this skill activates:

### 1. Decompose

To turn the request into discrete tasks, create a TaskCreate entry for every step larger than a trivial one-liner. To pick a reasonable granularity, target **3 to 15 tasks** per invocation — fewer risks under-tracking, more risks over-planning.

To capture the request accurately, include in each TaskCreate:

- `subject` — imperative verb phrase (e.g., "Refactor auth middleware")
- `description` — scope, files touched, success criterion
- `activeForm` — present continuous (e.g., "Refactoring auth middleware")

### 2. Announce

To set expectations, print a one-line plan summary before starting execution. For example:

```
📋 Plan: 7 tasks. Starting autonomous execution.
```

### 3. Execute Sequentially

To process tasks:

- To start a task, call `TaskUpdate` with `status: in_progress` immediately before beginning the work.
- To finish a task, call `TaskUpdate` with `status: completed` as soon as the work is done — never batch completions.
- To keep momentum, do not wait for user input between tasks. Proceed directly to the next pending task.
- To surface blockers, if a task encounters an unrecoverable error, mark it `completed` only if partially done is acceptable, otherwise keep `in_progress` and surface the error to the user.

### 4. Respect Safety Boundaries

To preserve user trust while moving fast, autonomy **does not** override Claude Code's destructive-action rules:

- To handle operations like `rm -rf`, `git push --force` on shared refs, `DROP TABLE`, mass deletion, or destructive third-party API calls, pause and ask the user first — regardless of this skill's autonomy.
- To handle external messaging (Slack, email, GitHub comments, issue creation), ask unless the user explicitly authorized that specific destination in this session.
- To handle secret disclosure, always refuse unless explicitly authorized.

To summarize: autonomy covers routine, reversible work. It does not cover irreversible or externally visible side effects.

### 5. Report

To close the loop, after the final task completes, report:

- What changed — terse bullet list
- What was skipped or deferred, with reason
- What remains for the user to verify or approve (if any destructive step was paused)

To keep the summary lean, aim for under 10 lines unless the task count is large.

## Interaction with Other Skills

To layer cleanly on top of existing workflows:

- To work alongside `/auto`, `/team`, `/parallel`, this skill does not replace them. If the user's request fits a specialized workflow (e.g., a team-scale PDCA run), invoke that workflow and use proceed-all's contract as the autonomy envelope around it.
- To avoid conflicting with TaskList semantics, if a teammate owns tasks in the current TaskList, coordinate via SendMessage rather than reassigning autonomously.
- To respect existing active_work claims (in EBS or similar repos with pre-work contracts), register the claim per the project's workflow before autonomous execution begins.

## Output Style

To stay readable during autonomous runs:

- To minimize noise, emit at most one status line per task (start) and one per completion.
- To surface decisions, announce non-obvious choices inline (e.g., "Using rebase instead of merge because the branch has been shared only locally").
- To avoid duplication, skip recapping what the TaskList already shows — the user can read it.

## Edge Cases

To handle common pitfalls:

- **User changes mind mid-run**: If the user sends a new message during autonomous execution, pause after the current task, acknowledge the new input, and re-plan.
- **Task reveals hidden complexity**: Split it by calling TaskCreate for the new subtasks and continue.
- **External tool fails**: Retry once with adjustment; if it fails again, surface the error and pause.
- **Context exhaustion**: If the running plan is large, commit intermediate progress with a sensible checkpoint so the run can resume in a fresh session.

## Examples

To illustrate typical invocations:

- `/proceed-all migrate all routes from kebab-case to PascalCase across services` — decomposes per service, executes sequentially, reports diffs.
- `create tasks and proceed all: audit dependencies, update minor versions, run tests` — three tasks, executed without pause.
- `do all the cleanup items on the backlog and no need approve` — reads backlog, creates one task per item, executes top-to-bottom.

## Non-Goals

To keep this skill focused:

- Not a scheduler — use `/loop` or `/schedule` for recurring work.
- Not a planner — for complex multi-session planning, use `Plan` or `/auto` with planning phase.
- Not a substitute for code review — autonomous execution does not imply autonomous merging to shared branches without the project's PR gate.

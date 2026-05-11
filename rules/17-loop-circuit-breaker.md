# Infinite Loop Circuit Breaker Rule (CRITICAL)

**Trigger**: All auto-repeating workflows including PDCA Act Phase, Architect verification, Continuation Loop, executor re-invocation.

## Core Principle

Every location where automatic re-invocation/retry occurs must have a **counter + limit + escalation** triad. Counters persist across session boundaries.

## Persistent State File

**Path**: `~/.claude/state/circuit-breaker.json`

```json
{
  "architect_reject": {"count": 0, "last_reason": "", "updated_at": "..."},
  "pdca_iterator": {"count": 0, "last_gap": 0, "updated_at": "..."},
  "continuation_loop": {"count": 0, "updated_at": "..."},
  "auto_recursion": {"count": 0, "updated_at": "..."}
}
```

**Rules**:
- **session_init.py must never reset this file** (cross-session persistence)
- Reset a counter to 0 only after user escalation and explicit user approval
- On new work (new PRD, new feature start), Lead explicitly resets

## Per-Counter Limits

| Counter | Limit | On reaching limit |
|---------|:-----:|-------------------|
| `architect_reject` | 3 | Block auto executor re-invocation → escalate to user |
| `pdca_iterator` | 5 | Block REJECT path → ask user to redefine requirements |
| `continuation_loop` | 3 | Force Map-Reduce chunking (12-large-document-protocol.md) |
| `auto_recursion` | 1 | Block nested `Skill("auto")` → direct response |

## Escalation Output Format

On reaching a limit, Lead must report to the user using the format below and **stop automatic retries**.

```
═══════════════════════════════════════════════════
 ⚠ Circuit Breaker triggered — {counter_name} reached {count}
═══════════════════════════════════════════════════
 Reason: {last failure reason}
 Attempt history: {brief summary}

 Automatic retries stopped. Choose one:
   1. Redefine requirements and retry
   2. Reset counter and retry (`/reset-breaker {counter_name}`)
   3. Abort
═══════════════════════════════════════════════════
```

## Execution Rules

### On Architect REJECT
1. `architect_reject.count` += 1, update `last_reason`
2. count < 3: re-invoke executor via existing flow
3. count >= 3: **executor invocation forbidden**, output escalation

### On pdca-iterator gap < 90%
1. `pdca_iterator.count` += 1, update `last_gap`
2. count < 5: re-invoke pdca-iterator
3. count >= 5: **REJECT path forbidden**, ask user to redefine requirements

### On Continuation Loop
- Combined with max_attempts=3 rule from 12-large-document-protocol.md
- On exceeding 3, force Map-Reduce chunking

### On `/auto` recursion (see 16-auto-default.md)
- When `~/.claude/state/auto-active.lock` exists, `auto_recursion.count` += 1
- count >= 1: auto `Skill("auto")` call forbidden, direct response

## Counter Reset Timing

| Event | Reset Target |
|-------|--------------|
| User runs `/reset-breaker {name}` | That counter only |
| User runs `/reset-breaker all` | All |
| New PRD/feature start (Lead's judgment) | architect_reject, pdca_iterator |
| `/auto` normal completion | auto_recursion |

**Forbidden**: auto-reset in session_init.py, time-based auto-reset.

## Forbidden

- Implementing auto-retry loops without counters
- Resetting `circuit-breaker.json` in session_init.py
- Circumventing escalation after reaching a limit (e.g., REJECT → iterator → REJECT bypass)
- "Just one more try"-style ad-hoc workarounds

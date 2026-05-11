---
name: critic
description: Critical review of EBS project docs/design/DB/API — parallel 2-critic + authority checklist + mandatory counter-evidence. Cross-adjudicates WSOP LIVE alignment (Principle 1) and EBS Core scope (§1.2 matrix) as joint criteria.
version: 1.0.0
triggers:
  keywords:
    - "critic"
    - "critic mode"
    - "검토"
    - "비판"
    - "정합성 검토"
    - "정렬 검토"
---

# /critic — EBS Design/Doc Critical Review Skill

## Purpose

Structurally prevent **anchoring errors and missing authoritative evidence** when adjudicating EBS project specs, DB, API, or design. A single agent iterating sequentially anchors on its own prior verdict — this is resolved by **parallel 2-critic**.

## Activation Conditions

Invoke this skill **first** if any of the following apply:
- Explicit requests such as "critic mode", "review critically", "alignment review"
- WSOP LIVE alignment review requested
- Pre-review before major design decisions
- Verdicts on "missing/wrong" for docs, schemas, or APIs

## 5-Phase Workflow

### Phase 1 — Mandatory Authority Checklist Pre-Read

Documents that **must be Read first** before any verdict (specified in the Explore agent's prompt):

```
[Authority order — higher always wins]
1. C:/claude/ebs/CLAUDE.md §"Project Design Principles" (especially Principle 1 WSOP LIVE alignment)
2. C:/claude/ebs/docs/2. Development/2.2 Backend/Back_Office/Overview.md §1.2 Adopt/Remove Matrix
3. C:/claude/ebs/docs/1. Product/Foundation.md §4.2 Overlay render elements
4. C:/claude/ebs/docs/2. Development/2.5 Shared/team-policy.json (governance_model + version)
5. C:/claude/ebs/docs/4. Operations/Multi_Session_Workflow.md (parallel operation policy)

[Auxiliary — treat with suspicion]
6. ~/.claude/projects/C--claude-ebs/memory/ (downgrade if stale warning or age > 7 days; secondary verification required)
```

**Prohibited**: Emitting a verdict without Reading the 5 documents above. Verdicts citing memory only.

### Phase 2 — Parallel 2-Critic Deployment

**Concurrent execution** (parallel tool calls in a single message):

**Agent A — WSOP LIVE Alignment View**
```
prompt:
"Against Principle 1 (maximum WSOP LIVE alignment), for each target:
 - Do value/name/structure match the WSOP LIVE source?
 - If diverged, is justified divergence documented in EBS docs?
 - If no justification, verdict = alignment violation.
Citations from wsoplive/docs/confluence-mirror/ are mandatory."
subagent_type: Explore (thoroughness: very thorough)
```

**Agent B — EBS Core Scope View**
```
prompt:
"Against EBS Core (3-input → overlay, real-time live only) and §1.2 matrix removed areas
 (Registration/Payout/KYC, etc.):
 - Is the target inside EBS scope or outside?
 - If outside, absent from EBS is correct even if present in WSOP LIVE.
 - Does the field/value actually enter the overlay render chain?
Citations from Foundation.md §4.2 and Back_Office/Overview.md §1.2 are mandatory."
subagent_type: Explore (thoroughness: very thorough)
```

### Phase 3 — Cross-Adjudication + Mandatory Counter-Evidence

After Lead receives both agents' outputs:

**3-1. Verdict table** (three columns required per item):

| Verdict | Evidence | Authority | Counter-Evidence (deliberately sought) |
|---------|----------|:---------:|----------------------------------------|
| e.g. Transaction addition required | §1.2 matrix #12–15 (finance removed) | doc:line | "one reason addition might be needed" |

- **Authority**: doc citation (H) > memory citation (M) > inference (L)
- If no counter-evidence is found, mark "insufficient evidence" and request user confirmation
- Verdicts based solely on authority L are prohibited — must add doc-based evidence

**3-2. Agent A vs Agent B conflict handling**:
| Situation | Action |
|-----------|--------|
| Both agents agree | Adopt |
| Disagree (e.g., A "align" / B "out of scope") | Compare evidence strength, then **escalate to user immediately** — arbitrary synthesis prohibited |

### Phase 4 — Self-Rebuttal Loop (mandatory at report end)

A **"Weaknesses of this report"** section is required at the end of every critic report:
1. Documents not Read (if any, immediate risk)
2. Memories this verdict depends on, and the memory's age
3. Strongest argument an opponent could use to attack this report

Reports missing this section are incomplete — do not emit.

### Phase 5 — Memory Update

If the user corrected a verdict (pattern like v1–v4 in this session):
1. Append the failure pattern to `~/.claude/projects/C--claude-ebs/memory/feedback_critic_discipline.md`
2. If an existing memory was overturned, edit that memory file + update the MEMORY.md index

## Output Format

```markdown
# Critic Report

## Phase 1 Authority Documents Confirmed
- [ ] CLAUDE.md §Principle 1 (cited lines)
- [ ] Overview.md §1.2 matrix (cited lines)
- [ ] Foundation.md §4.2 (cited lines)
- [ ] team-policy.json (version)
- [ ] Multi_Session_Workflow.md (cited lines)

## Phase 2 Agent Verdicts
### Agent A (WSOP LIVE alignment)
...
### Agent B (EBS Core scope)
...

## Phase 3 Cross-Adjudication
| Item | Verdict | Evidence | Authority | Counter-Evidence | A/B Agreement |
|------|---------|----------|:---------:|------------------|:-------------:|
...

## Phase 4 Weaknesses of This Report
1. Unread documents: ...
2. Memory dependency age: ...
3. Strongest attack: ...

## Final Recommendation
Prioritized action matrix + explicit out-of-scope items
```

## Prohibited

- Emitting verdicts while skipping the Phase 1 authority checklist
- Running only Agent A or only Agent B
- Emitting verdicts without the counter-evidence column
- Verdicts based solely on memory (no doc cross-check)
- Omitting the Phase 4 self-rebuttal section
- Lead arbitrarily synthesizing on Agent conflict (must escalate to user)

## Meta

**Why this skill exists**: In the 2026-04-15 session, EBS DB/API critic was performed ad-hoc, leading to four re-adjudications v1→v2→v3→v4. Each time, a different authority document was missed (CLAUDE.md Principle 1, §1.2 matrix, team-policy v6, Multi_Session_Workflow). Four structural safeguards — checklist + parallel + counter-evidence + self-rebuttal — block the failure mode.

**Reuse points**: The pattern is portable to non-EBS projects, but the Phase 1 authority list must be rewritten per project.

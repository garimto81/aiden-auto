---
name: critic
description: Critical review of project docs/design/DB/API — parallel 2-critic + authority checklist + mandatory counter-evidence. Project-agnostic; authority documents are defined per project in CLAUDE.md or .claude/references/.
version: 2.0.0
triggers:
  keywords:
    - "critic"
    - "critic mode"
    - "검토"
    - "비판"
    - "정합성 검토"
    - "정렬 검토"
---

# /critic — Design/Doc Critical Review Skill

## Purpose

Structurally prevent **anchoring errors and missing authoritative evidence** when adjudicating project specs, DB, API, or design. A single agent iterating sequentially anchors on its own prior verdict — this is resolved by **parallel 2-critic**.

## Activation Conditions

Invoke this skill **first** if any of the following apply:
- Explicit requests such as "critic mode", "review critically", "alignment review"
- Pre-review before major design decisions
- Verdicts on "missing/wrong" for docs, schemas, or APIs

## 5-Phase Workflow

### Phase 1 — Mandatory Authority Checklist Pre-Read

Documents that **must be Read first** before any verdict (specified in the Explore agent's prompt):

```
[Authority order — higher always wins]
Define your project's 5 authority documents in your project CLAUDE.md
or .claude/references/critic-authority.md, following this template:

1. <project-root>/CLAUDE.md §"Project Design Principles"
2. <project-root>/docs/<architecture-or-spec>.md §<key-section>
3. <project-root>/docs/<domain-model>.md §<key-section>
4. <project-root>/docs/<governance-or-policy>.json
5. <project-root>/docs/<operations-or-workflow>.md

[Auxiliary — treat with suspicion]
6. ~/.claude/projects/<project>/memory/ (downgrade if stale warning or age > 7 days)

If no authority list is defined, raise "Authority list not configured" and
ask the user to specify 5 authoritative documents before proceeding.
```

**Prohibited**: Emitting a verdict without Reading the 5 documents above. Verdicts citing memory only.

### Phase 2 — Parallel 2-Critic Deployment

**Concurrent execution** (parallel tool calls in a single message):

**Agent A — Principle Alignment View**
```
prompt:
"Against the project's primary design principle (defined in authority doc #1),
 for each target:
 - Does value/name/structure conform to the principle?
 - If diverged, is justified divergence documented?
 - If no justification, verdict = alignment violation.
Citations from authority documents are mandatory."
subagent_type: Explore (thoroughness: very thorough)
```

**Agent B — Scope Boundary View**
```
prompt:
"Against the project's scope definition (authority docs #2–#3):
 - Is the target inside or outside the defined scope?
 - If outside scope, its absence is correct even if it exists elsewhere.
 - Does the field/value actually enter the core processing chain?
Citations from authority documents are mandatory."
subagent_type: Explore (thoroughness: very thorough)
```

### Phase 3 — Cross-Adjudication + Mandatory Counter-Evidence

After Lead receives both agents' outputs:

**3-1. Verdict table** (three columns required per item):

| Verdict | Evidence | Authority | Counter-Evidence (deliberately sought) |
|---------|----------|:---------:|----------------------------------------|
| e.g. Field addition required | §scope-matrix #12 (removed) | doc:line | "one reason addition might be needed" |

- **Authority**: doc citation (H) > memory citation (M) > inference (L)
- If no counter-evidence is found, mark "insufficient evidence" and request user confirmation
- Verdicts based solely on authority L are prohibited — must add doc-based evidence

**3-2. Agent A vs Agent B conflict handling**:
| Situation | Action |
|-----------|--------|
| Both agents agree | Adopt |
| Disagree | Compare evidence strength, then **escalate to user immediately** — arbitrary synthesis prohibited |

### Phase 4 — Self-Rebuttal Loop (mandatory at report end)

A **"Weaknesses of this report"** section is required at the end of every critic report:
1. Documents not Read (if any, immediate risk)
2. Memories this verdict depends on, and the memory's age
3. Strongest argument an opponent could use to attack this report

Reports missing this section are incomplete — do not emit.

### Phase 5 — Memory Update

If the user corrected a verdict:
1. Append the failure pattern to `~/.claude/projects/<project>/memory/feedback_critic_discipline.md`
2. If an existing memory was overturned, edit that memory file + update the MEMORY.md index

## Output Format

```markdown
# Critic Report

## Phase 1 Authority Documents Confirmed
- [ ] Authority doc #1 (cited lines)
- [ ] Authority doc #2 (cited lines)
- [ ] Authority doc #3 (cited lines)
- [ ] Authority doc #4 (version)
- [ ] Authority doc #5 (cited lines)

## Phase 2 Agent Verdicts
### Agent A (Principle alignment)
...
### Agent B (Scope boundary)
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
- Hardcoding project-specific paths in this file (use project CLAUDE.md instead)

## Meta

**Why this skill exists**: In a 2026-04 session, DB/API critic was performed ad-hoc, leading to four re-adjudications v1→v2→v3→v4. Each time, a different authority document was missed. Four structural safeguards — checklist + parallel + counter-evidence + self-rebuttal — block the failure mode.

**Project configuration**: Each project must define its own 5 authority documents. This skill is project-agnostic by design — EBS-specific paths have been removed in v2.0.0. See `.claude/references/critic-authority.md` in your project for the authority list template.

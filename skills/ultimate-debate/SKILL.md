---
name: ultimate-debate
description: "3-AI parallel analysis and consensus judgment system"
version: "2.0.0"
author: "Claude Code"

triggers:
  keywords:
    - "토론"
    - "debate"
    - "합의"
    - "다중 AI"
    - "3AI 분석"
    - "교차 검토"
  file_patterns:
    - ".claude/debates/**/*.md"
  context:
    - "Complex design decisions"
    - "Multiple perspectives needed"
    - "Architecture decisions"
    - "Strategy formulation"

capabilities:
  - multi_ai_parallel
  - consensus_building
  - round_based_debate
  - context_management
  - strategy_patterns

model_preference: opus
phase: [1, 2]
auto_trigger: false
token_budget: 5000
---

# Ultimate Debate Skill

**Type**: Cross-AI Consensus Verifier
**Status**: Phase 2 - Hybrid Architecture

## Overview

A skill that runs three AIs (Claude, GPT, Gemini) in parallel analysis → cross review → consensus judgment → re-debate, repeating the loop until a final consensus is reached.

## Core Features

| Feature | Description |
|---------|-------------|
| **Parallel analysis** | 3 AIs analyze independently and concurrently |
| **Cross review** | Each AI reviews the others' analyses |
| **Consensus judgment** | Hash-based conclusion comparison to check consensus |
| **Re-debate** | Evidence-based debate when disagreement remains |
| **Context management** | History stored in MD files (saves main context) |

## 5-Phase Workflow

```
Phase 1: Parallel analysis (3 AIs concurrently)
    ↓
Phase 2: Initial consensus check (hash comparison)
    ↓
Phase 3: Cross review (if no consensus)
    ↓
Phase 4: Re-debate (resolve disagreement)
    ↓
Phase 5: Final strategy formulation
```

## Directory Layout (Hybrid Architecture)

### Core Engine (standalone package)
```
packages/ultimate-debate/
├── pyproject.toml
├── src/ultimate_debate/
│   ├── engine.py               # Main debate engine
│   ├── comparison/             # 3-Layer comparison system
│   ├── consensus/              # Consensus protocol
│   ├── strategies/             # Strategy patterns
│   └── storage/                # Context management
└── tests/
```

### Skill Layer (Claude Code integration)
```
.claude/skills/ultimate-debate/
├── SKILL.md
├── requirements.txt
└── scripts/
    ├── main.py                 # CLI entry point
    ├── adapter.py              # Core Engine adapter
    └── debate/                 # Legacy (fallback)
```

## Usage

### CLI Usage

```bash
# Start a new debate
python .claude/skills/ultimate-debate/scripts/main.py --task "API refactoring strategy"

# Check status
python .claude/skills/ultimate-debate/scripts/main.py --status --task-id debate_20260118_abc123

# Configure options
python .claude/skills/ultimate-debate/scripts/main.py \
  --task "Security audit" \
  --max-rounds 3 \
  --threshold 0.9 \
  --output text
```

## Context Management System

All debate history is saved to MD files to preserve main context.

```
.claude/debates/{task_id}/
├── TASK.md                      # Initial task description
├── round_00/
│   ├── claude.md                # Claude analysis
│   ├── gpt.md                   # GPT analysis
│   └── gemini.md                # Gemini analysis
└── FINAL.md                     # Final consensus
```

## Consensus States

| State | Condition | Next Action |
|-------|-----------|-------------|
| `FULL_CONSENSUS` | ≥ 80% agreement | None (terminate) |
| `PARTIAL_CONSENSUS` | 50-80% agreement | CROSS_REVIEW |
| `NO_CONSENSUS` | < 50% agreement | DEBATE |

## Installation

```bash
# Install Core Engine (development mode)
cd C:\claude\packages\ultimate-debate
pip install -e .

# Run tests
python -m pytest tests/ -v
```

## Related Documents

- PRD: `tasks/prds/PRD-0035-multi-ai-consensus-verifier.md`
- Cross-AI Verifier: `.claude/skills/cross-ai-verifier/`

---

**Last Updated**: 2026-01-19
**License**: MIT

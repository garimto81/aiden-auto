# Daily Skill v3.0 — 9-Phase Pipeline Detail

> 상세 phase-by-phase 명세. index 는 `../SKILL.md` 참조.

3-source (Gmail/Slack/GitHub) incremental collection + AI cross-source analysis + action recommendation engine.

**Paradigm**: "collect+display" -> "learn+recommend actions"

**Design Reference**: `C:\claude\docs\02-design\daily-redesign.design.md`

## Execution Rules (CRITICAL)

**When this skill activates, you MUST run the 9-Phase Pipeline below in order.**

```
Phase 0 -> 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8
Config   Expert  Collect  Attach  AI     Action  Project  Gmail    State
Bootstrap Context  (incr)  Analyze Analyze Recom   Ops    Housekp  Update
```

---

## Phase 0: Config Bootstrap

Search for `.project-sync.yaml` in CWD; auto-generate if missing.

**Step 0.1: File lookup**

```
Read: .project-sync.yaml
# If missing, go to Step 0.2
# If present, check version:
#   v1.0 -> compat mode (read-only, treat meta.auto_generated=false)
#   v2.0 + auto_generated=true -> auto-update allowed
#   v2.0 + auto_generated=false -> read-only
```

**Step 0.2: Auto-generate (when file is absent)**

```bash
# Project identification
# Priority 1: Read CLAUDE.md -> extract project name, tech stack, goals
# Priority 2: Read README.md -> fallback
# Priority 3: Use directory name

# Source discovery
python -m lib.gmail status --json          # Gmail auth + email address
python -m lib.slack status --json          # Slack auth + workspace
gh auth status                             # GitHub auth + repo

# Project type auto-classification
# vendor_management: keywords "업체", "vendor", "RFP", "견적"
# development: presence of src/, package.json, setup.py
# infrastructure: presence of Dockerfile, terraform
# research: high docs/ ratio
# content: keywords "영상", "media", "upload"
```

Write `.project-sync.yaml` v2.0:
```yaml
version: "2.0"
project_name: "{auto-detected}"
meta:
  auto_generated: true
  confidence: 0.0-1.0
  generated_at: "ISO timestamp"
  pending_additions: []
daily:
  sources:
    gmail: { enabled: true/false }
    slack: { enabled: true/false, channel_id: "{fuzzy-matched}" }
    github: { enabled: true/false, repo: "{from git remote}" }
  project_type: "{auto-classified}"
```

**Error**: If both CLAUDE.md and README.md are missing, create a minimal config based on the directory name.

---

## Phase 1: Expert Context Loading

Build project expert context in 3 tiers.

```
# Tier 1: Identity Context (500t)
Read: CLAUDE.md + .project-sync.yaml
-> project name, goals, tech stack, key terminology, data sources, communication_style

# Tier 2: Operational Context (2000t)
Read: .omc/daily-state/<project>.json -> learned_context section
-> entities (vendors, people, statuses), patterns (recurring patterns)

# Tier 3: Deep Context (3000t, only when present)
Read: docs/ core files (README, PRD, architecture)
Read: .omc/daily-state/<project>.learned-context.json
-> domain knowledge, accumulated prior analysis
```

Output: expert_context JSON (injected into Phase 4, 5 prompts)

**Error**: Without CLAUDE.md, build minimal Tier 1. Without daily-state, skip Tier 2 (first run).

---

## Phase 2: Incremental Data Collection

Incremental collection across 3 sources. Cursors stored in `.omc/daily-state/<project>.json` so subsequent runs collect only new data.

**Step 0: Auth check**

```bash
python -m lib.gmail status --json    # check authenticated, valid
python -m lib.slack status --json    # check authenticated, valid
gh auth status                       # check exit code
```

Skip sources that fail auth for this run. Abort with error if zero sources are active.

**Step 1: Gmail collection**

```python
from lib.gmail import GmailClient
client = GmailClient()

# First run: seed historyId + 7-day lookback
profile = client.get_profile()          # obtain historyId
emails = client.list_emails(query="newer_than:7d", max_results=50)

# Incremental: History API
result = client.list_history(
    start_history_id=state["cursors"]["gmail"]["history_id"],
    history_types=["messageAdded"],
    max_results=100
)
# historyId 404 -> fallback to list_emails(query="after:...")
```

**Step 2: Slack collection**

```python
from lib.slack import SlackClient
client = SlackClient()

# First run: 7-day lookback
messages = client.get_history(channel=channel_id, limit=100, oldest=str(time.time()-604800))

# Incremental: since last_ts
messages = client.get_history(channel=channel_id, limit=100, oldest=state["cursors"]["slack"]["last_ts"])
```

**Step 3: GitHub collection**

```bash
gh issue list --since "{last_check}" --json number,title,state,author,updatedAt,labels
gh pr list --json number,title,state,author,updatedAt,reviewDecision
gh api repos/{owner}/{repo}/commits --jq '.[0:10] | .[] | {sha: .sha[0:7], message: .commit.message[0:80], date: .commit.author.date}'
```

---

## Phase 3: Attachment Analysis

AI analysis of attachments from emails collected in Phase 2.

**Target filter**: PDF, Excel, images (PNG/JPG)

**SHA256 cache**: Previous analysis results stored in `state.cache.attachments[sha256]`. Prevents re-analysis of identical attachments.

**Download**:

```python
data = client.download_attachment(message_id, attachment_id)  # lib/gmail/client.py
```

**Analysis methods**:

| Type | Condition | Method |
|------|-----------|--------|
| PDF (<= 20p) | `page_count <= 20` | Direct analysis via Claude Read tool |
| PDF (> 20p) | `page_count > 20` | Chunk-split analysis via `lib/pdf_utils` PDFExtractor |
| Excel/CSV | - | Structure summary (rows/cols, headers, 5-row sample) |
| Images | PNG/JPG | Claude Vision analysis |

**Analysis perspective**: Apply expert_context.analysis_perspective
- `vendor_management`: "Is this a quote? Amount, validity, terms?"
- `development`: "Is this an API spec? Changes, breaking changes?"

**Error**: Download failure -> skip; encrypted PDF -> skip and report

---

## Phase 4: AI Cross-Source Analysis

Inject expert_context and analyze as a project expert.

**Step 1: Independent per-source analysis**

Claude reads Phase 2 raw data + Phase 3 attachment analysis and analyzes each source:

- **Gmail**: sender, key content, urgency (URGENT/HIGH/MEDIUM/LOW), required actions, quote info, status inference
- **Slack**: decisions, action items, unresolved questions, entity matching
- **GitHub**: PR status, issue status, CI/CD status

**Step 2: Cross-source connection analysis**

Detect links across sources:
1. Same-topic detection (simultaneous mention in Gmail + Slack)
2. Action linkage (email request -> GitHub issue/PR)
3. Status inconsistency (Gmail "done" vs GitHub issue open)
4. Timeline construction (chronological linking of events on the same topic across sources)

**Prompt details**: See `docs/02-design/daily-redesign.design.md` Sections 3.2, 3.3

**Error**: If only a single source is active, skip cross-source analysis and perform independent analysis only.

---

## Phase 5: Action Recommendation

Generate concrete action drafts from analysis results.

| Action Type | Generation Condition |
|-------------|---------------------|
| Email reply draft | No response for 48h+, quote received, explicit request |
| Slack message draft | Unanswered question, follow-up needed |
| GitHub action | PR review pending 3+ days, unanswered issue |

**Tone calibration**: Reference `communication_style`
- `email_tone`: professional / casual / formal
- `slack_tone`: casual / professional
- `language`: ko / en / mixed

**Limits**: Max 10 items, sorted URGENT -> HIGH -> MEDIUM; include estimated time per action

**Prompt details**: See `docs/02-design/daily-redesign.design.md` Section 3.4

**Error**: If no analysis results, display "No additional actions required."

---

## Phase 6: Project-Specific Operations

Conditionally run based on `project_type` in `.project-sync.yaml`.

**vendor_management type**:
- Update Slack Lists (ListsSyncManager)
- Auto vendor status transitions (StatusInferencer)
- Quote comparison table (QuoteFormatter)

```bash
cd {project_path} && python -c "
import sys; sys.path.insert(0, 'scripts/sync')
from lists_sync import ListsSyncManager
manager = ListsSyncManager()
manager.update_item('{vendor}', status='{status}', quote='{quote}', last_contact='{date}')
manager.generate_summary_message()
manager.post_summary()
"
```

**development type**:
```bash
gh run list --limit 5 --json databaseId,status,conclusion,name,createdAt
gh pr list --state open --json number,title,headRefName,updatedAt
gh api repos/{owner}/{repo}/milestones --jq '.[] | {title, open_issues, closed_issues}'
```

**Error**: Skip Phase 6 if config_file is missing. On Slack Lists API failure -> print warning and continue.

---

## Phase 7: Gmail Housekeeping

Clean up Gmail based on `housekeeping` in `.project-sync.yaml`.

**7a. Auto label application** (`gmail_label_auto: true`):
- Filter Phase 2 emails without labels
- Auto-apply labels on vendor_domains match
- Exclude system mail (noreply, notifications, drive-shares)

**7b. INBOX cleanup** (`inbox_cleanup` setting):

| Mode | Behavior |
|------|----------|
| `"auto"` | Auto archive |
| `"confirm"` | Show target list, confirm via AskUserQuestion |
| `"skip"` | Skip (default) |

**Error**: On Gmail API failure -> skip action, print warning

---

## Phase 8: State Update

**Phase A (right after collection — record cursors)**:
```python
state["cursors"]["gmail"]["history_id"] = new_history_id
state["cursors"]["gmail"]["last_timestamp"] = datetime.utcnow().isoformat() + "Z"
state["cursors"]["slack"]["last_ts"] = last_message_ts
state["cursors"]["github"]["last_check"] = datetime.utcnow().isoformat() + "Z"
state["last_run"] = datetime.utcnow().isoformat() + "Z"
state["run_count"] += 1
```

**Phase B (after analysis — cache + learning record)**:
```python
state["cache"]["attachments"][sha] = analysis  # attachment cache
state["learned_context"]["entities"].update(new_entities)
state["learned_context"]["patterns"].extend(new_patterns)
```

**Auto config update** (only when `auto_generated: true`):
- On new domain detection, append to `pending_additions`

**Error**: On file write failure -> same data is re-collected next run (no data loss).

---

## Output Format

```
================================================================================
                   Daily Dashboard v3.0 (YYYY-MM-DD Day)
                   Project: {project_identity}
================================================================================

[Sources] --------------------------------------------------------
  Gmail: {N} items ({new} new) {auth_status}
  Slack: {N} items ({new} new) {auth_status}
  GitHub: {N} issues, {N} PRs {auth_status}

[Cross-Source Insights] ------------------------------------------------
  1. {topic}: {insight} (sources: Gmail+Slack)

[Action Items] --------------------------------------------------------

  URGENT ({N} items)
  #{id}. [{type}] {target}
     Draft: {draft_preview}
     ETA: {estimated_time} | Reason: {reason}

  HIGH ({N} items)
  #{id}. [{type}] {target}
     Draft: {draft_preview}
     ETA: {estimated_time} | Reason: {reason}

[Per-Source Details] --------------------------------------------------------
  Gmail / Slack / GitHub details

[Attachment Analysis] --------------------------------------------------------
  * {filename}: {summary}

================================================================================
  Total actions: {total} | Estimated: ~{total_time} min
  Next run: incremental collection (cursors saved)
================================================================================
```

**vendor_management extra sections**: vendor status table, quote comparison, Slack Lists update result
**development extra sections**: CI/CD status, branch status, milestone progress

---

## Subcommands

| Command | Description |
|---------|-------------|
| `/daily` | Full dashboard (all 9 phases) |
| `/daily ebs` | EBS daily briefing (existing EBS-specific workflow) |

### EBS Briefing Mode

`/daily ebs` preserves the existing EBS-specific workflow.

```bash
cd C:\claude\ebs\tools\morning-automation && python main.py --post
```

Detailed workflow: identical to the prior v2.0.0 EBS section.

---

## Changelog

| Version | Changes |
|---------|---------|
| 3.0.0 | Full 9-Phase Pipeline redesign. Removed Secretary dependency. Added incremental collection, attachment AI analysis, cross-source analysis, action recommendation engine, Config Auto-Bootstrap, Expert Context Loading. Absorbed daily-sync functionality. |
| 2.0.0 | Integrated EBS briefing mode (`/daily ebs`) |
| 1.1.0 | Skill-chain integration (Gmail, Secretary) |
| 1.0.0 | Initial release |

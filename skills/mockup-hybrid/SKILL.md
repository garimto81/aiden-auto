---
name: mockup-hybrid
description: >
  Hybrid mockup system combining HTML wireframes with Google Stitch.
  Prompt-analysis based automatic backend selection, Stitch API integration, with fallback support.
version: 1.0.0

triggers:
  keywords:
    - "mockup"
    - "/mockup"
    - "목업"
    - "와이어프레임"
    - "wireframe"
    - "ui mockup"
    - "--hifi"
    - "--bnw"
    - "stitch"
  file_patterns:
    - "docs/mockups/*.html"
    - "docs/images/mockups/*.png"
  context:
    - "UI design"
    - "Screen design"
    - "Prototype"

capabilities:
  - auto_backend_selection
  - html_wireframe_generation
  - stitch_api_integration
  - playwright_screenshot
  - fallback_handling

model_preference: sonnet

auto_trigger: true
---

# Mockup Hybrid Skill

A hybrid mockup system that integrates HTML wireframes with the Google Stitch API.

## Architecture

```
/mockup [name] --bnw
      |
      v
+--------------------------------------------------+
|        Design Context Analyzer (built-in)        |
+--------------------------------------------------+
|  1. Prompt analysis (keywords, complexity)       |
|  2. Environment check (Stitch API key valid?)    |
|  3. Apply auto-selection rules                   |
+--------------------------------------------------+
      |
      v
+--------------------------------------------------+
|              Backend Router                      |
+--------------------------------------------------+
|  Stitch chosen -> Stitch Adapter -> Stitch API   |
|  HTML chosen   -> HTML Adapter   -> Local Gen    |
+--------------------------------------------------+
      |
      v
+--------------------------------------------------+
|           Fallback Handler                       |
|  Stitch API failure -> auto fallback to HTML     |
+--------------------------------------------------+
      |
      v
+--------------------------------------------------+
|           Export Manager                         |
|  Save HTML + PNG + print selection reason        |
+--------------------------------------------------+
```

## Options

| Option | Behavior | Backend Selection |
|--------|----------|-------------------|
| `--bnw` (default) | **Auto-select** | Prompt analysis -> HTML or Stitch |
| `--force-html` | Force HTML | Always local HTML |
| `--force-hifi` | Force Stitch | Always Stitch API |

## Auto-Selection Rules

### Priority

1. **Force options** (user-specified)
   - `--force-html` -> HTML
   - `--force-hifi` -> Stitch

2. **Keyword detection**
   - Stitch triggers: "presentation", "high fidelity", "for review", "stakeholder", "final", "official"
   - HTML triggers: "quick", "structure", "wireframe", "draft", "review"

3. **Context**
   - `--prd=PRD-NNNN` -> Stitch (high-fidelity for docs)
   - `--screens=3+` -> HTML (fast generation)

4. **Environment check**
   - No Stitch API key -> HTML
   - Rate limit exceeded -> HTML

5. **Default** -> HTML (fastest)

## Core Feature: Replace ASCII Diagrams with Images

The **core purpose** of the `--bnw` option is to replace ASCII diagrams in Markdown files with images.

### Workflow

```
Detect ASCII diagram -> Generate HTML mockup -> Capture PNG -> Replace in Markdown
```

### Steps

| Step | Action | Output |
|:----:|--------|--------|
| 1 | Detect ASCII diagrams in target file | Box/arrow/line patterns |
| 2 | Convert each ASCII into an HTML wireframe | `docs/mockups/*.html` |
| 3 | Capture screenshot via Playwright | `docs/images/*.png` |
| 4 | **Replace ASCII in original Markdown with image reference** | `![](../images/*.png)` |

### ASCII Detection Patterns

```python
ASCII_PATTERNS = [
    r'[┌┐└┘├┤┬┴┼]',  # box corners/intersections
    r'[─│═║]',        # lines
    r'[→←↑↓▶◀▲▼]',    # arrows
    r'[╔╗╚╝╠╣╦╩╬]',   # double-line boxes
]
```

### Replace Options

| Option | Description |
|--------|-------------|
| `--target=FILE` | Target Markdown file for replacement |
| `--keep-ascii` | Preserve original ASCII as HTML comments |
| `--dry-run` | Preview only (no actual modification) |
| `--force` | Replace immediately, skip confirmation |

## Usage Examples

```bash
# Replace ASCII diagrams (core use case)
/mockup "system structure" --bnw --target=docs/ARCHITECTURE.md

# Replace all ASCII in a PRD file
/mockup --bnw --target=docs/prds/PRD-0001.md

# Auto-select -> HTML (simple request)
/mockup "login screen" --bnw

# Auto-select -> Stitch (high-fidelity keywords)
/mockup "dashboard - stakeholder presentation" --bnw

# Auto-select -> Stitch (linked to PRD)
/mockup "auth flow" --bnw --prd=PRD-0001

# Force HTML
/mockup "dashboard" --bnw --force-html

# Force Stitch
/mockup "landing page" --bnw --force-hifi
```

## Output Format

```bash
# On success
Selected: Stitch API (reason: high-fidelity keywords detected)
Generated: docs/mockups/dashboard-hifi.html
Captured:  docs/images/mockups/dashboard-hifi.png

# On fallback
Stitch API failed -> falling back to HTML
Generated: docs/mockups/dashboard.html
Captured:  docs/images/mockups/dashboard.png
```

## Module Structure

```
.claude/skills/mockup-hybrid/
├── SKILL.md                    # this file
├── adapters/
│   ├── html_adapter.py         # HTML wireframe generation
│   └── stitch_adapter.py       # Stitch API integration
├── core/
│   ├── analyzer.py             # prompt analysis + auto-selection
│   ├── router.py               # backend routing
│   └── fallback_handler.py     # Stitch -> HTML fallback
└── config/
    └── selection_rules.yaml    # auto-selection rules

lib/mockup_hybrid/
├── __init__.py
├── stitch_client.py            # Stitch API client
└── export_utils.py             # export utilities
```

## Environment Variables

```bash
# Google Stitch (free - 350 screens/month)
STITCH_API_KEY=your-api-key
STITCH_API_BASE_URL=https://api.stitch.withgoogle.com/v1
```

## Google Stitch Cost

| Item | Cost | Monthly Limit |
|------|:----:|---------------|
| Standard Mode (Gemini 2.5 Flash) | **Free** | 350 screens/month |
| Experimental Mode (Gemini 2.5 Pro) | **Free** | 50-200 screens/month |

> **Note**: Currently free during the Google Labs experimental phase. Subject to change.

## Integrations

| Skill/Agent | Integration Point |
|-------------|-------------------|
| `google-workspace` | Google Drive upload |
| `frontend-dev` | UI implementation |
| `docs-writer` | Insert into PRD docs |

## Related Docs

- `docs/MOCKUP_HYBRID_GUIDE.md` - detailed guide
- `.claude/commands/mockup.md` - command definition
- `.claude/templates/mockup-wireframe.html` - HTML template

## Changelog

### v1.0.0 (2026-01-23)

**Features:**
- Initial release
- Hybrid support for HTML wireframes + Stitch API
- Prompt-based automatic backend selection
- Automatic Stitch -> HTML fallback

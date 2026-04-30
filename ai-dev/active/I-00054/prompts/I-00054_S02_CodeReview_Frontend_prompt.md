# I-00054_S02_CodeReview_Frontend_prompt

**Work Item**: I-00054 -- Coverage Page Toggle Label Does Not Update on Expand/Collapse
**Step Being Reviewed**: S01 (Frontend)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Not applicable to this step.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state**: `uv run iw item-status I-00054 --json`
- `ai-dev/active/I-00054/I-00054_Issue_Design.md` — Design document
- `ai-dev/active/I-00054/reports/I-00054_S01_Frontend_report.md` — S01 implementation report
- `dashboard/templates/pages/system/coverage.html` — The modified template

## Output Files

- `ai-dev/active/I-00054/reports/I-00054_S02_CodeReview_Frontend_report.md` — Review report

## Context

You are reviewing the frontend fix applied in S01 for **I-00054: Coverage Page Toggle Label Does Not Update on Expand/Collapse**.

The fix modifies a single Jinja2 template (`dashboard/templates/pages/system/coverage.html`) to add toggle state tracking and collapse behavior to the package expand/collapse rows on the `/system/coverage` page.

Read the design document to understand the intended fix. Read the S01 report to understand what was done. Then review the modified template.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

Report any NEW violations in `dashboard/templates/pages/system/coverage.html` as CRITICAL findings.

Note: Jinja2 templates are not processed by ruff — these commands will primarily catch any Python files inadvertently touched. Run them regardless.

## Review Checklist

### 1. Correctness of the Toggle Logic

- Does the `hx-trigger` guard condition `this.dataset.expanded!='true'` correctly prevent htmx from re-fetching when the row is already expanded?
- Does the `htmx:afterSwap` listener correctly identify coverage file divs (by checking `target.id.startsWith('files-')`)?
- Does the collapse path correctly clear `filesDiv.innerHTML`, reset `data-expanded` to `'false'`, and reset the label text to "click to expand"?
- Is the IIFE pattern used correctly (function wraps everything, no global variable leakage)?
- Are there any race conditions — e.g., could the click listener and `htmx:afterSwap` fire simultaneously?

### 2. Data Attribute Presence

- Is `data-pkg-toggle="{{ pkg.name }}"` present on each package `<tr>`?
- Is `data-expanded="false"` present as the initial state on each `<tr>`?
- Is `id="expand-label-{{ pkg.name }}"` present on the label `<td>`?
- Are the `id` values unique per package (they should be, since `pkg.name` is unique per row)?

### 3. htmx Trigger Guard

- Does the modified `hx-trigger` include both the `click` guard and the `keydown[key=='Enter']` guard?
- Would the keydown guard correctly prevent collapse re-fetching via keyboard?

### 4. Security

- No user-supplied data is used in JavaScript string concatenation that could lead to XSS. The `pkgName` comes from `target.id.slice(...)` — which is server-rendered and derived from `pkg.name` (a package directory name). Verify this is safe (no user input reaches `pkg.name`).

### 5. Scope of Change

- Is the fix strictly limited to `dashboard/templates/pages/system/coverage.html`?
- No backend files, no new routes, no service changes?
- No new Tailwind classes added that would require `make css` to regenerate?

### 6. No Regressions

- Does the template still render all package rows, file detail divs, and htmx attributes for the expand-on-first-click path?
- Is the `<script>` block placed correctly (at the bottom of `{% block content %}`, so the DOM is available when it runs)?

## Test Verification (NON-NEGOTIABLE)

Run unit tests to confirm no regressions:

```bash
make test-unit
```

Report results in the result contract.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Breaks functionality, XSS vulnerability, wrong data attributes |
| **HIGH** | Toggle logic bug (e.g. guard condition wrong), keydown path broken |
| **MEDIUM (fixable)** | Minor code quality issue, missing null check |
| **MEDIUM (suggestion)** | Optional improvement |
| **LOW** | Nitpick |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00054",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file",
      "line": 0,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

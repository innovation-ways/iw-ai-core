# I-00089_S02_CodeReview_Frontend_prompt

**Work Item**: I-00089 -- AI Assistant panel — in-header collapse button is unusable in both states
**Step**: S02
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

You MUST NOT run docker compose / kill / stop / restart commands against
running infrastructure. Read-only `docker ps` / `docker logs` is allowed.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic upgrade/downgrade/stamp commands. Read-only
`alembic history / current / show` is allowed. This step is review-only;
you should not need any alembic commands.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00089 --json` for current step + previous-step report paths.
- `ai-dev/active/I-00089/I-00089_Issue_Design.md` -- design document (RCA, ACs)
- `ai-dev/active/I-00089/reports/I-00089_S01_Frontend_report.md` -- S01's report (read this FIRST)
- `dashboard/templates/chat_assistant/panel.html` -- as modified by S01
- `dashboard/static/chat_assistant/chat.css` -- as modified by S01
- `dashboard/static/chat_assistant/chat.js` -- read-only reference (S01 must NOT have changed this)
- `ai-dev/active/I-00089/evidences/pre/` -- pre-fix DOM snapshots for comparison
- `CLAUDE.md` and `dashboard/CLAUDE.md` -- project conventions
- `git diff main -- dashboard/templates/chat_assistant/ dashboard/static/chat_assistant/` -- the actual change as it will land

## Output Files

- `ai-dev/active/I-00089/reports/I-00089_S02_CodeReview_Frontend_report.md` -- Review report with findings table

## Context

You are reviewing S01's fix for I-00089. The fix is template + CSS only. There is no Python, no JS, no DB. Verify correctness and scope adherence.

## Review Checklist

### Correctness

- [ ] **Bug A — inline `<style>` block extended correctly**: `panel.html` lines 1-13 (or wherever the `<style>` block now lives) include `#chat-assistant-panel[data-collapsed="true"] #chat-assistant-collapse-btn` in the `display: none` selector group. The selector chain is grouped with the other `[data-collapsed="true"]` selectors (comma-separated, no stray semicolons).
- [ ] **Bug B — collapse button has a `title` attribute**. Open the button tag in `panel.html` and confirm `title="..."` is present (any descriptive label like "Collapse panel" or "Collapse AI Assistant" is acceptable).
- [ ] **Bug B — collapse button has a distinguishing class marker**: either `chat-assistant-collapse-btn-distinct` OR a Tailwind border utility (`border`, `border-l`, etc.) is present on the button's class list.
- [ ] **`aria-label` preserved**: the existing `aria-label="Collapse AI Assistant panel (Ctrl+/)"` is unchanged.
- [ ] **SVG path preserved**: the existing chevron-left path (`d="M15 19l-7-7 7-7"`) is unchanged.
- [ ] **JS unchanged**: `dashboard/static/chat_assistant/chat.js` is identical to main — no JS modifications. Confirm via `git diff main -- dashboard/static/chat_assistant/chat.js`.
- [ ] **Expand rail unchanged**: the `#chat-assistant-expand-rail` block (`panel.html` lines ~75-86 pre-fix) is untouched.

### Scope adherence

- [ ] **`git diff main --name-only`** lists ONLY paths inside `dashboard/templates/chat_assistant/`, `dashboard/static/chat_assistant/`, and the `ai-dev/active/I-00089/**` work folder. Any other file is a scope violation — flag as CRITICAL.
- [ ] No new Tailwind utility classes are introduced that aren't already in the prebuilt `dashboard/static/styles.css` (run `grep -F "<class>" dashboard/static/styles.css` for any new class you spot in the button's class list). If a class is missing, the implementer must either run `make css` OR move the styling to plain CSS in `chat.css`.

### Accessibility

- [ ] Tab order through the header is unchanged (the buttons appear in the same DOM order: tray-toggle → history-toggle → new-btn → collapse-btn).
- [ ] The `title` attribute is in addition to, not a replacement for, `aria-label`. Screen-reader users still hear the full descriptive label including the Ctrl+/ shortcut.
- [ ] The collapse button remains keyboard-focusable (no `tabindex="-1"` added).

### Behaviour preservation

- [ ] The Ctrl+/ keybinding (`chat.js:937-942`) is unchanged.
- [ ] The nav-bar toggle button (`#chat-assistant-nav-toggle`, wired at `chat.js:965-968`) is unchanged.
- [ ] The expand rail (`#chat-assistant-expand-rail`) still opens the panel.

### Cross-page check

The chat panel template is included on every dashboard page via `chat_assistant/panel.html`. Run:

```bash
grep -rn 'chat_assistant/panel.html' dashboard/templates/
```

For each page that includes the panel, the CSS rules added by the fix MUST be scoped to `#chat-assistant-panel` (or to a class only present inside the panel). A rule that leaks (e.g. `button[title="Collapse panel"] { ... }`) would affect unrelated buttons across the dashboard — flag as HIGH.

### Pre-flight gate sanity

- [ ] S01's report shows `preflight.format`, `preflight.typecheck`, `preflight.lint` all in (`ok`, `fixed`, or a justified `skipped:<reason>`). Anything else is a red flag.

## Findings Format

Produce a markdown report at `ai-dev/active/I-00089/reports/I-00089_S02_CodeReview_Frontend_report.md` with this structure:

```markdown
# I-00089 S02 CodeReview Frontend — Report

## Summary

{1-2 sentences: pass / partial / fail and headline reason}

## Findings

| Severity | Area | Finding | File:line | Required Fix |
|----------|------|---------|-----------|--------------|
| CRITICAL | … | … | … | … |
| HIGH | … | … | … | … |
| MEDIUM | … | … | … | … |
| LOW | … | … | … | … |

(Empty table is acceptable if review is clean.)

## Acceptance Criteria Traceability

| AC | Covered by | Status |
|----|------------|--------|
| AC1 | Bug A hide-rule extension in panel.html `<style>` block | pass / fail |
| AC2 | Bug B title attribute + distinguishing class marker in panel.html | pass / fail |

## Decision

- `complete` if no CRITICAL or HIGH findings.
- `partial` if CRITICAL/HIGH findings exist and the fix-cycle agent needs to address them.
```

Then call:

```bash
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00089/reports/I-00089_S02_CodeReview_Frontend_report.md
```

(Use `iw step-fail` only if the review cannot complete due to missing inputs or tooling — a fix-needed review still reports `step-done` with the findings listed.)

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00089",
  "completion_status": "complete",
  "files_changed": [
    "ai-dev/active/I-00089/reports/I-00089_S02_CodeReview_Frontend_report.md"
  ],
  "preflight": {
    "format": "skipped:review-only",
    "typecheck": "skipped:review-only",
    "lint": "skipped:review-only"
  },
  "tests_passed": true,
  "test_summary": "skipped: review step",
  "tdd_red_evidence": "n/a — review step",
  "findings_count": {"critical": 0, "high": 0, "medium": 0, "low": 0},
  "blockers": [],
  "notes": ""
}
```

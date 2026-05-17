# CR-00056_S09_CodeReview_Frontend_prompt

**Work Item**: CR-00056 -- Surface step prompts in dashboard (Prompt column + modal viewer)
**Step Being Reviewed**: S08 (frontend-impl)
**Review Step**: S09

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00056 --json`
- `ai-dev/active/CR-00056/CR-00056_CR_Design.md` — focus on `AC4–AC8`
- `ai-dev/work/CR-00056/reports/CR-00056_S08_Frontend_report.md`
- All files in S08 `files_changed`
- `dashboard/CLAUDE.md` — hard rules on clipboard, fragment templates, Jinja format filter

## Output Files

- `ai-dev/work/CR-00056/reports/CR-00056_S09_CodeReview_report.md`

## Context

S08 added the Prompt column, the modal fragment, CSS, and the JS handler. You're verifying the visible half of CR-00056.

## Read the Design Document FIRST

- `AC4` — Prompt column rendering (between Model and Status; View button or "—")
- `AC5` — modal renders prompt text in `<pre>` with role="dialog" aria-modal="true"
- `AC6` — Escape / backdrop / close-button dismissal + focus restore
- `AC7` — stacked sections for Initial + Fix Prompt (cycle N)
- `AC8` — copy-to-clipboard works

## Pre-Review Lint & Format Gate

```bash
make lint
make format
```

`make lint` includes `scripts/check_templates.py` — Jinja format-filter misuse will fail here. NEW failures → CRITICAL.

## Review Checklist

### 1. CLAUDE.md hard rule: clipboard helper

- **CRITICAL** if any file under `dashboard/` calls `navigator.clipboard.writeText` directly. The required path is `window.iwClipboard.copy(text, button)`. Grep:
  ```bash
  grep -RIn 'navigator\.clipboard\.writeText' dashboard/
  ```
  Should produce zero hits in files changed by S08.

### 2. CLAUDE.md hard rule: fragment templates must NOT extend base.html

- Open `dashboard/templates/fragments/prompt_text_modal.html`. Confirm no `{% extends "base.html" %}`.

### 3. CLAUDE.md hard rule: Jinja format filter

- Search the modified templates for `|format(`. Any usage must be `%`-style (e.g., `"%d"|format(n)`), NEVER `{}`-style. If `make lint` passed, this is already enforced — but spot-check.

### 4. Column ordering matches design

- Open `dashboard/templates/fragments/item_steps_table.html`. Confirm header order is: Step, Agent, CLI, Model, **Prompt**, Status, Started, Duration, Runs, Error, Actions (11 columns).
- Cell order in the `<tr>` matches.
- The empty-state row's `colspan` was updated from 8 to match the new visible-column count (likely 10 or 11 depending on which the table previously used — verify the rendered HTML doesn't break on no-steps).

### 5. Accessibility

- Modal has `role="dialog"`, `aria-modal="true"`, `aria-labelledby="prompt-modal-title"`.
- Trigger button has `aria-label` describing what it opens.
- Focus is moved into the modal on open and restored on close (verify the JS in `prompt_modal.js`).
- Escape closes the modal (JS keydown listener exists and is scoped correctly).
- Backdrop click closes the modal (JS click handler on `.prompt-modal-backdrop` or `#prompt-modal-overlay`).

### 6. XSS / autoescape

- `{{ section.text }}` and `{{ prompt_file_display }}` are rendered without `|safe`. **CRITICAL** if either uses `|safe` (XSS risk: a malicious prompt could contain `<script>alert(1)</script>`).
- `<pre>` tag preserves whitespace correctly.

### 7. CSS additions

- New CSS rules are appended to `dashboard/static/styles.css` (not to a separate Tailwind partial that requires recompile, per CR-00033 fallback rule).
- Selectors are namespaced (`.prompt-modal-*` or reuse `.activity-modal-*`); no overly-generic selectors that could leak (`.modal-body { ... }` without prefix is a HIGH finding).

### 8. JS quality

- `prompt_modal.js` is idempotent — re-init on htmx swap doesn't double-bind event listeners (use a `window.__promptModalInit` sentinel or attach to a stable parent only once).
- Focus trap handles both Tab and Shift+Tab correctly.
- Copy button calls `window.iwClipboard.copy(text, button)` — verify the section's text is read from the `<pre>` element via `textContent` (NOT `innerHTML`).

### 9. htmx wiring

- The View button uses `hx-get` to the route from S06, with `hx-target="#prompt-modal-mount"` and `hx-swap="innerHTML"`.
- The mount element `#prompt-modal-mount` exists somewhere reachable from where the steps table renders.

### 5a. TDD RED Evidence

Frontend step: `tdd_red_evidence` should use the `n/a` form. Behaviour is verified by qv-browser S22.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/test_prompt_modal_route.py -v
uv run pytest tests/dashboard/ -v
```

## Review Result Contract

```json
{
  "step": "S09",
  "agent": "CodeReview",
  "work_item": "CR-00056",
  "step_reviewed": "S08",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```

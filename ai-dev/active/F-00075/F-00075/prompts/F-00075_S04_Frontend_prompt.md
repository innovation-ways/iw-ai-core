# F-00075_S04_Frontend_prompt

**Work Item**: F-00075 -- MiniMax Coding Plan usage from /coding_plan/remains (replace local SQLite estimate)
**Step**: S04
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

(Same policy as in S01. Full policy: docs/IW_AI_Core_Agent_Constraints.md)

## ⛔ Migrations: agents generate, daemon applies

This work item touches no migrations.

## Input Files

- `ai-dev/active/F-00075/F-00075_Feature_Design.md`
- `ai-dev/active/F-00075/evidences/pre/F-00075-before-fragment.html` — current rendered fragment showing the wrong 19% and no reset countdown.
- `dashboard/templates/fragments/llm_usage_footer.html` — the file to modify (35 lines).
- `ai-dev/active/F-00075/reports/F-00075_S03_API_report.md` — confirms the new template vars.

## Output Files

- `ai-dev/active/F-00075/reports/F-00075_S04_Frontend_report.md`

## Context

Add a 5h reset countdown next to the MiniMax bar in the footer fragment, mirroring the Claude row's pattern. Optionally add a tooltip exposing the request counts.

## Requirements

### 1. Add the reset-countdown label next to the MiniMax bar

The MiniMax block currently looks like this (lines 24–32 in the fragment):

```jinja
<span class="font-medium text-foreground">MiniMax</span>

<div class="hidden sm:flex items-center gap-1.5">
  <span class="text-muted-foreground">5h</span>
  <div class="w-20 h-1.5 bg-border rounded-full overflow-hidden">
    <div class="h-full {{ minimax_5h_color }} rounded-full transition-all duration-700" style="width: {{ minimax_5h_pct }}%"></div>
  </div>
  <span class="font-medium tabular-nums">{{ minimax_5h_pct }}%</span>
</div>
```

Replace the literal `"5h"` label with `{{ minimax_reset or '5h' }}`, mirroring exactly how the Claude row uses `{{ claude_reset or '5h' }}` (lines 6–7). The fallback string `'5h'` matches the literal already there for Claude when its remote call has not produced a reset value.

After the change, the block should read:

```jinja
<div class="hidden sm:flex items-center gap-1.5">
  <span class="text-muted-foreground">{{ minimax_reset or '5h' }}</span>
  <div class="w-20 h-1.5 bg-border rounded-full overflow-hidden">
    <div class="h-full {{ minimax_5h_color }} rounded-full transition-all duration-700" style="width: {{ minimax_5h_pct }}%"></div>
  </div>
  <span class="font-medium tabular-nums">{{ minimax_5h_pct }}%</span>
</div>
```

### 2. Add the request-count tooltip

When `minimax_5h_used` and `minimax_5h_total` are both not `None` (success branch), surface them as a `title` attribute on the outer `<div class="hidden sm:flex items-center gap-1.5">` so a hover reveals e.g. `"0 / 4500 requests"`. Skip the `title` attribute when either value is `None` (failure branch — avoids `"None / None requests"`). The S07 router pass-through test asserts that `"0 / 4500 requests"` appears in the rendered fragment when the success-branch values are present, so this tooltip must be implemented.

Use Jinja's conditional attribute pattern:

```jinja
<div class="hidden sm:flex items-center gap-1.5"{% if minimax_5h_used is not none and minimax_5h_total is not none %} title="{{ minimax_5h_used }} / {{ minimax_5h_total }} requests"{% endif %}>
```

Keep this on a reasonably long but readable line; do not let it sprawl into multiple lines if it breaks the htmx swap target structure.

### 3. Do **not** introduce new Tailwind utility classes

The dashboard uses prebuilt Tailwind CSS. Any class string not already present in the codebase risks being purged by JIT. Stick to classes already used in the same file (`text-muted-foreground`, `font-medium`, `tabular-nums`, `hidden sm:flex`, etc.).

If you must add a new class, also run `make css` and commit the regenerated `dashboard/static/styles.css` along with the template change.

### 4. Run `make css` if needed

If you only changed text expressions (no new classes), `make css` is **not** required. Verify by diffing the generated CSS hash before and after (or simply by inspecting your diff and confirming you added no new class names).

## Project Conventions

Read `dashboard/CLAUDE.md`:
- Fragment templates do **not** extend `base.html`.
- `make css` regenerates `dashboard/static/styles.css` from `dashboard/templates/**/*.html`.

## TDD Requirement

Update or add a Jinja-rendering test if `tests/dashboard/` already has one targeting this fragment. Otherwise rely on S07 to add coverage. At minimum, render the template once locally with stubbed context (e.g. `python -c "import jinja2; jinja2.Environment(...).get_template(...)"`) and confirm no Jinja errors.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint` — note the `lint` target also runs `node --check` over `dashboard/static/**/*.js`. The template itself is not lint-checked, but ensure no JS file you touched (you shouldn't) breaks the check.

## Test Verification

`make test-unit` must pass. If the dashboard has a `tests/dashboard/` tier that includes template rendering, confirm those still pass.

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "frontend-impl",
  "work_item": "F-00075",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["dashboard/templates/fragments/llm_usage_footer.html"],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```

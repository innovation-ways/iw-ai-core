# I-00120_S03_Frontend_prompt

**Work Item**: I-00120 — Codex usage chips silently show 0% when the opencode OAuth token is expired or invalid
**Step**: S03
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state. Read-only
introspection, testcontainer fixtures, and `./ai-core.sh` / `make` targets are allowed.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step adds no migrations.

## Input Files

- Runtime step state: `uv run iw item-status I-00120 --json`.
- `ai-dev/active/I-00120/I-00120_Issue_Design.md` — design doc (read **Warning message mapping** and **Status discriminator contract**).
- `ai-dev/work/I-00120/reports/I-00120_S01_Backend_report.md` — confirms the `status` values the backend now emits.
- `dashboard/routers/usage.py` and `dashboard/templates/fragments/llm_usage_footer.html` — the files you modify.

## Output Files

- `ai-dev/work/I-00120/reports/I-00120_S03_Frontend_report.md` — step report.

## Context

S01 added a `status` field to the Codex usage dict (`ok` / `expired` / `unauthenticated` / `error`).
Your job is to surface a visible warning in the footer fragment when status ≠ `ok`, **replacing** the
two Codex usage bars with inline warning text. When status == `ok`, the footer is unchanged.

Read the design doc, then `CLAUDE.md` and `dashboard/CLAUDE.md` (note: routers are thin; Tailwind is
prebuilt — prefer classes already in `dashboard/static/styles.css`).

## Requirements

### 1. Map status → warning message in `dashboard/routers/usage.py`

In `llm_usage_fragment()`:
- Read the backend status: `codex_status = codex.get("status") or "ok"`.
- Define a module-level mapping from status → warning text (per the design doc's **Warning message mapping** table):

  | status | warning text |
  |--------|--------------|
  | `expired` | `token expired — re-authenticate` |
  | `unauthenticated` | `not configured — run opencode auth login` |
  | `error` | `usage unavailable` |
  | `ok` | (none) |

- Pass two new template context variables:
  - `codex_warning` — the warning string, or `None`/empty when status == `ok`.
  - (Optional) keep passing `codex_status` if useful for the template.
- Also update the stale-cache fallback dict (the `usage.get("codex") or {...}` branch) to include
  `"status": "error"` so a pre-upgrade cache surfaces a warning rather than a silent 0%.

The `⚠` glyph and amber styling live in the template (presentation), not the message string.

### 2. Render the warning in `dashboard/templates/fragments/llm_usage_footer.html`

In the Codex section (currently the two `<div>` bars after the `Codex` label):
- When `codex_warning` is falsy → render the existing two bars **unchanged**.
- When `codex_warning` is set → render a single inline warning element **in place of** the two bars,
  e.g.:
  ```html
  <span class="hidden sm:flex items-center gap-1 text-amber-600" title="Codex usage unavailable — {{ codex_warning }}">⚠ {{ codex_warning }}</span>
  ```
- Use the class `text-amber-600` — it is already present in the compiled `dashboard/static/styles.css`,
  so **no `make css` run is required**. Do NOT introduce a brand-new Tailwind class that isn't already
  compiled (per CLAUDE.md / I-00067).
- Keep the `Codex` label line and its `title="ChatGPT … plan"` behaviour intact.

### 3. Keep `format`-filter usage `%`-style

If you add any `|format(...)` filter call, use `%`-style (`"%s"|format(x)`), never `str.format`-style
(`"{}"|format(x)`) — enforced by `make lint` (CLAUDE.md). (Likely not needed here.)

### Do NOT

- Do NOT change the Claude or MiniMax sections of the fragment.
- Do NOT add backend/business logic to the router beyond the trivial status→message mapping.
- Do NOT run `make css` unless lint/template checks force it; prefer the already-compiled `text-amber-600`.

## Project Conventions

Read `dashboard/CLAUDE.md`. Fragment templates MUST NOT extend `base.html` (this one already doesn't).
Keep the router thin.

## TDD Requirement

The dedicated `tests-impl` step (S05) owns the rendering tests. For your own verification, you may run
the dashboard test file once it exists; otherwise verify by rendering the fragment via the route in a
quick targeted check. Do not run the full suite.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `complete`, run and fix issues in files you touched:
1. `make format`
2. `make typecheck`
3. `make lint`  (this includes `scripts/check_templates.py` for the Jinja2 fragment)

Full-suite / aggregate-gate success (`make quality` / `make check` / `make test-frontend` /
`make test-integration`) is **NOT** this step's responsibility and MUST NOT be used as a
completion gate — those are owned by the downstream `tests-impl` (S05) and `qv-gate` steps
(S08..S15). (Canonical Verification Placement Rule — `skills/iw-workflow/SKILL.md`; CR-00092 / I-00117.)

## Test Verification (NON-NEGOTIABLE)

Targeted only — render the fragment route and confirm the warning appears for a non-`ok` status and
the bars appear for `ok`. Do NOT run `make test-frontend` / `make test-integration` (downstream QV gates).

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "frontend-impl",
  "work_item": "I-00120",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["dashboard/routers/usage.py", "dashboard/templates/fragments/llm_usage_footer.html"],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "targeted render check passed",
  "tdd_red_evidence": "n/a — router mapping + template edits; behavioural tests owned by S05",
  "blockers": [],
  "notes": ""
}
```

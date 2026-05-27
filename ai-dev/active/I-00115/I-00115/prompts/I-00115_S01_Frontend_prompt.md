# I-00115_S01_Frontend_prompt

**Work Item**: I-00115 — Amend-scope modal locks the dashboard UI after dismissal
**Step**: S01
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step touches NO migrations. Do not run any `alembic` command. If you
think you need to, STOP and raise a blocker.

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status I-00115 --json`. The `workflow-manifest.json` file is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/active/I-00115/I-00115_Issue_Design.md` — design document (READ FIRST)
- `dashboard/templates/components/scope_amend_modal.html` — the broken template
- `dashboard/routers/actions.py` (lines 215-232, 440-505) — read-only context for the 204+toast response shape
- `dashboard/templates/pages/project/item_detail.html` (lines 158-172) — read-only context for the page-level `htmx:afterRequest` toast handler
- `dashboard/static/styles.css` — search for `.activity-modal-backdrop` to confirm the backdrop's CSS (it is fixed/full-viewport/z-index 50)

## Output Files

- `ai-dev/active/I-00115/reports/I-00115_S01_Frontend_report.md` — step report

## Context

You are fixing two cosmetic frontend defects in the scope-amend modal:

1. **Submit success leaves the modal + backdrop on screen.** The form returns 204 No Content with an `HX-Trigger: showToast` header. The current template has no cleanup wiring on the form, so the modal stays open over an inaccessible page.
2. **The "×" close button uses a broken DOM walk.** `this.closest('#scope-amend-overlay')` returns null (the overlay is a sibling, not an ancestor), so `.remove()` on the result throws `TypeError`, leaving the backdrop behind.

The user also requested two standard modal UX additions: **ESC to dismiss** and **backdrop click to dismiss**.

The Cancel button at line 60 already does it correctly (`document.getElementById(...)` for both elements) — use it as the reference.

Read `ai-dev/active/I-00115/I-00115_Issue_Design.md` in full before editing. Then read `CLAUDE.md` and `dashboard/CLAUDE.md` for project-specific patterns.

## Requirements

### 1. Repair all five dismissal paths in `dashboard/templates/components/scope_amend_modal.html`

After your edit, every one of the following must fully remove BOTH `#scope-amend-modal` AND `#scope-amend-overlay` from the DOM:

1. **Form submit (Amend & restart)** — after the htmx POST returns successfully (any 2xx, including 204). The cleanup MUST fire on `htmx:afterRequest` only when the response succeeded; on failure (4xx/5xx) the modal should stay open so the operator can see the error toast and retry. **You MUST use the inline `hx-on::after-request="…"` attribute on the `<form>` element itself** (the project's existing idiom — see `dashboard/templates/fragments/oss_status_frame.html:83` or `dashboard/templates/fragments/item_steps_table.html:134` for examples). The attribute body MUST reference both `scope-amend-modal` and `scope-amend-overlay` by ID so it removes both. Do NOT delegate this particular hook to a separate `<script>` block — the S03 regression test asserts on the form's open-tag attributes and a script-block detour would make the test fail. (Inline `onclick` handlers and a `<script>` block remain acceptable for the other dismissal paths if they are simpler that way.)
2. **× close button** (header) — replace the broken `this.closest('#scope-amend-overlay').remove()` with `document.getElementById('scope-amend-overlay').remove()`, or call the shared cleanup helper if you choose to factor one out.
3. **Cancel button** (footer) — already correct; if you factor out a shared cleanup helper, re-point Cancel at it for consistency.
4. **ESC key** — pressing the `Escape` key while the modal is open dismisses it (same as Cancel). The listener MUST be removed when the modal is dismissed so it does not leak across reopens.
5. **Backdrop click** — clicking on `#scope-amend-overlay` itself (not on the modal, not on its contents) dismisses the modal. Make sure clicks inside the modal don't propagate to the backdrop handler and inadvertently close.

### 2. Listener-leak hygiene

The modal is appended via `hx-swap="beforeend"` to `#modal-root`, so it can be opened multiple times. Any document-level listeners you install (ESC key) MUST be removed when the modal is dismissed. State this explicitly in your step report.

### 3. Preserve existing accessible behaviour

- The form's `aria-*` attributes, role, `tabindex`, and overall accessibility wiring stay intact.
- The toast still appears on successful submit (page-level handler at `item_detail.html:159-172` consumes `HX-Trigger: showToast`).
- Do NOT modify `dashboard/routers/actions.py`. The 204 + `HX-Trigger` response is correct.

### 4. Diff minimality

Keep the diff focused. Do NOT introduce a new shared JS file, do NOT touch unrelated modals, do NOT restructure the modal markup. The form's success-teardown hook MUST be inline (`hx-on::after-request` — see §1.1). For the other dismissal paths (× button, Cancel, ESC, backdrop click), a single small `<script>` block at the bottom of `scope_amend_modal.html` is preferred over scattering inline handlers when it produces the cleanest diff.

### 5. CSS

If you find that you need a new Tailwind class, **append it as plain CSS to `dashboard/static/styles.css`** per the project rule in `CLAUDE.md` (Tailwind toolchain is broken in worktrees per I-00067). Most likely you need no CSS change at all — this is a JS/template fix.

## Project Conventions

Read `CLAUDE.md` and `dashboard/CLAUDE.md` in full. Key rules for this step:

- Dashboard templates use Jinja2 + htmx + Tailwind. No JS framework.
- Tailwind CSS is **prebuilt** — if you need a new class and `make css` reports "Nothing to be done", append plain CSS to `dashboard/static/styles.css`.
- htmx attributes used here: `hx-post`, `hx-target`, `hx-swap`, `hx-on::after-request`, `hx-trigger`.
- Inline `onclick` handlers are acceptable in this codebase (the existing modal uses them); a small `<script>` block at the end of a component template is also acceptable. Pick whichever produces the cleaner diff.

## TDD Requirement

This step is a **frontend template fix**. The RED phase here is the test work that S03 will do. For S01:

1. Before editing the template, run `uv run pytest tests/dashboard/ -k "scope_amend" -v` (any existing scope-amend tests) to confirm the baseline passes — your fix must not regress them.
2. After editing, re-run the same command to confirm nothing broke.
3. The new I-00115 tests will be authored in S03 against your fixed template.

Because this is template-only with no production-Python behaviour added, your `tdd_red_evidence` field should be: `"n/a — Jinja2 template fix only; behavioural tests are authored in S03 (tests-impl) against the fixed template, and the RED check is asserted there"`.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in order and fix any issues they report:

1. **`make format`** — auto-fixes formatting drift.
2. **`make type-check`** — must report zero errors involving the files you touched.
3. **`make lint`** — must report zero errors (this includes `scripts/check_templates.py`, which catches `str.format`-style Jinja2 `format` filter calls — re-read the rule in `CLAUDE.md`).

If any tool is unavailable, STOP and raise a blocker.

## Test Verification (NON-NEGOTIABLE)

Run only the **targeted** tests that exercise your change. **DO NOT** run the full suite — that's downstream QV gates' job:

```bash
uv run pytest tests/dashboard/ -k "scope_amend" -v
uv run pytest tests/integration/test_scope_amend_endpoints.py -v
```

These existing tests must still pass. They cover the server endpoint behaviour (which you are NOT changing).

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "frontend-impl",
  "work_item": "I-00115",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/components/scope_amend_modal.html"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — Jinja2 template fix only; behavioural tests are authored in S03 (tests-impl) against the fixed template, and the RED check is asserted there",
  "blockers": [],
  "notes": "How the ESC listener is detached on dismissal; which idiom (hx-on::after-request vs inline <script>) was chosen and why; whether a shared cleanup helper was factored out."
}
```

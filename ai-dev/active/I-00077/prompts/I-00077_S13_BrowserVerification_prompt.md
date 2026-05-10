# Browser Verification Prompt: I-00077-S13-BrowserVerification

**Work Item**: I-00077 — Doc-generation jobs abort on missing editorial guide and the failure is invisible on the Docs page
**Step**: S13
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state
(`docker kill|stop|rm|restart`, `docker compose up|down|restart`, `docker volume rm|prune`,
`docker system|container|image prune`). The orchestration DB, daemon, dashboard, and any
long-lived infra containers are outside your scope. Allowed exceptions: testcontainers spun
up by pytest fixtures; read-only `docker ps|inspect|logs`; **`docker compose -p "$COMPOSE_PROJECT_NAME" exec app …`** is allowed and required when re-running the seed after writing a fixture file; `./ai-core.sh` / `make` targets.
If a task seems to require a prohibited command, STOP and raise a blocker.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Do not run `alembic upgrade|downgrade|stamp` against any live DB. This item has no migrations.

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source. Do NOT start, stop, or rebuild any service.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:9900`, no `localhost:5173`) or application route paths — read `$IW_BROWSER_BASE_URL` and navigate via the UI where possible. Before asserting on page *content*, confirm the page loaded (HTTP 200, no unhandled-exception page, no load-time console errors). A 500 on a page you're verifying is itself a `code_defect` finding.

Do NOT run: `make dev` / `make e2e-up` / any `docker compose up|down|restart|build`; `playwright install`; `agent-browser`; raw `chromium.launch()`. Use `playwright-cli` **exclusively**.

## Input Files

- `ai-dev/active/I-00077/I-00077_Issue_Design.md` — design document
- `dashboard/routers/docs.py` — `docs_running_jobs`
- `dashboard/templates/docs_library.html` — the Docs catalogue page
- `dashboard/templates/fragments/docs_running_jobs.html` — the running-jobs strip fragment

## Output Files

- `ai-dev/active/I-00077/reports/I-00077_S13_BrowserVerification_Report.md` — the mandatory report
- `ai-dev/active/I-00077/evidences/post/` — screenshots taken during verification
- `ai-dev/active/I-00077/e2e_fixtures/001_failed_doc_job.py` — fixture seeding a failed `DocGenerationJob` (you create this; see below)

## Prerequisites

Start every run with, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then log in:

```bash
playwright-cli snapshot
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Always `playwright-cli snapshot` before `fill`/`click`; wait for transitions to settle; screenshots go under `ai-dev/active/I-00077/evidences/post/`.

## E2E DB seed data — required fixture

The E2E PostgreSQL is `pg_dump`-seeded from production, so the `iw-ai-core` project and its docs (including `iw-ai-core:diagram-architecture`) exist, but there is no recently-`failed` `DocGenerationJob` to look at. You MUST add one:

Create `ai-dev/active/I-00077/e2e_fixtures/001_failed_doc_job.py` exporting `def seed(db: Session) -> None` that is **idempotent** (`db.get(...)` / query-before-insert) and inserts a `DocGenerationJob` for an existing non-research doc of the `iw-ai-core` project — `doc_id="iw-ai-core:diagram-architecture"` — with:
- `status=JobStatus.failed`
- `error="job context has no section_guides_snapshot — cannot generate content without editorial guidance"`
- `requested_at` / `started_at` a couple of minutes ago, `completed_at=datetime.now(UTC)` (recent, within the strip's ~10-min window)
- a stable `id` (e.g. a fixed UUID string) so re-running the seed is idempotent
- `public_id` may be left for the auto-assign trigger / set to a fixed test value if the model requires it

(Use the ORM models from `orch.db.models`; mirror how `scripts/e2e_seed.py` constructs rows. Look at the `DocGenerationJob` model for required columns.)

**After writing the fixture you MUST re-run the seed inside the `app` container** (the worktree is mounted at `/workspace`):

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app uv run python scripts/e2e_seed.py
```

> ⚠️ NEVER run the seed from your host shell — the host `.env` points at the production orchestration DB on port 5433.

If `docker compose exec` is unreachable, call `iw step-fail` with reason prefixed `ENV_DATA_MISSING:` so the daemon re-provisions the stack.

## Verification Steps

### V0: Pre-flight page sanity (built-in — do NOT modify or remove)

The qv-browser agent automatically visits every distinct route referenced in V1..Vn, checks that every `hx-target`/`hx-include`/`aria-controls`/`aria-labelledby`/`href="#…"`/`for=` reference resolves to an `id` present in the same HTML, and reads `.playwright-cli/console-*.log` for unhandled JS/HTMX errors. Any dangling reference or load-time error is a V0 FAIL. V1..Vn still run regardless.

### V1: A recently-failed doc-generation job is visible on the Docs catalogue page

1. Navigate to `{{IW_BROWSER_BASE_URL}}/project/iw-ai-core/docs`.
2. No interaction needed — the running-jobs strip (`#docs-running-jobs`) loads on page load and fetches `/project/iw-ai-core/api/docs/running-jobs`, which (post-fix) now includes recently-`failed` jobs. (If the strip is empty, give it a moment / reload the page once — the fixture row must be in the per-worktree DB.)
3. **Verify:** the strip contains an entry for the seeded failed job — it shows the doc title ("…Architecture…" / matching `iw-ai-core:diagram-architecture`), renders with the failed-row distinct styling (a red/destructive accent, visually distinct from a running spinner row), displays the seeded error text ("…no section_guides_snapshot…"), and has a **Dismiss** button (and **no** Cancel button / no spinner / no live elapsed timer on that row). Confirm the page itself returned HTTP 200 with no console errors.
4. **Screenshot:** `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/I-00077/evidences/post/I-00077_v1_failed_job_visible.png`.

### V2: The failed-job row can be dismissed

1. On the same page, `playwright-cli snapshot`, then click the **Dismiss** button on the seeded failed-job row.
2. **Verify:** the row disappears from the strip immediately (client-side removal). The rest of the page is unaffected (the doc grid still rendered; no console errors).
3. **Screenshot:** `cp .playwright-cli/page-*.png ai-dev/active/I-00077/evidences/post/I-00077_v2_failed_row_dismissed.png`.

### V3: Successful / running doc-generation flow still works (No Regressions, part 1)

1. Reload `{{IW_BROWSER_BASE_URL}}/project/iw-ai-core/docs` and open any document's detail page (click a doc card → its detail view). Use the doc's own "Regenerate" / "Generate" control if present to enqueue a job — OR, if you'd rather not depend on a live agent run, just verify the strip + page still render cleanly.
2. **Verify:** if you enqueued a job, the strip shows a normal running row (spinner, elapsed timer, Cancel button) — i.e. the `status=="running"` path is unchanged. In all cases: no console errors, the catalogue and detail pages render normally, the doc grid is intact.
3. **Screenshot:** `cp .playwright-cli/page-*.png ai-dev/active/I-00077/evidences/post/I-00077_v3_running_path_unchanged.png`.

### V4: No Regressions, part 2

1. Revisit the Docs catalogue page filters (status filter, search box) and the per-doc cards — confirm they still work (typing in search filters the grid; the filter dropdown still functions).
2. Verify no new console errors appeared on any page visited during V1..V3.
3. **Screenshot:** `cp .playwright-cli/page-*.png ai-dev/active/I-00077/evidences/post/I-00077_v4_no_regressions.png`.

## Pass Criteria

All V1..V4 must pass. Any failure — including a partial/ambiguous result — requires `iw step-fail` with a reason. Classify the failure first:

| Failure shape | Class | Action |
|---|---|---|
| Page returned 5xx or threw a console exception | CODE_DEFECT | normal `--reason` |
| Page rendered cleanly but the failed-job row is missing because the seed lacks it | ENV_DATA_MISSING | `--reason "ENV_DATA_MISSING: …"` + ensure the fixture ran |
| Page rendered cleanly, element correctly absent per the design doc, V step asks for it anyway | SPEC_MISMATCH | `--reason "SPEC_MISMATCH: V{N} …"` |
| Page rendered cleanly, design says the failed row/dismiss control should be present, it isn't | CODE_DEFECT | normal `--reason` |

Do not write cascading `n/a` chains — seed the precondition yourself (the fixture above), then verify.

## Report

Write `ai-dev/active/I-00077/reports/I-00077_S13_BrowserVerification_Report.md` with: a pass/fail table (one row per V1..V4), the exact `$IW_BROWSER_BASE_URL` used, any issues found (with `file:line` if you investigated root cause), the list of screenshots under `evidences/post/`, and a **No regressions observed** subsection. Then call exactly one of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00077/reports/I-00077_S13_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00077/reports/I-00077_S13_BrowserVerification_Report.md
```

Always include `--report` on both success and failure.

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "qv-browser",
  "work_item": "I-00077",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "{{IW_BROWSER_BASE_URL}}",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Failed doc job visible on catalogue page", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Failed-job row dismissible", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Running/successful path unchanged", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "No regressions (filters/search/cards)", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```

- `overall_status`: `pass` only if every V passed (or was legitimately `n/a`).
- `overall_failure_class`: most severe across all Vs (`spec_mismatch` > `env_data_missing` > `code_defect`); `null` when `pass`.
- `base_url_used`: the concrete URL actually hit.
- `console_errors_observed`: any console errors seen during any V, even on an otherwise-passing run.

# F-00088_S03_Backend_prompt

**Work Item**: F-00088 — Structured Dashboard E2E Test Layer
**Step**: S03
**Agent**: backend-impl

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

This Feature adds **no migration** and **no schema change**. You MUST NOT
create, modify, or apply any alembic migration. If your work appears to
need one, STOP and raise a blocker — that means the scope is wrong.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status F-00088 --json`.
- `ai-dev/active/F-00088/F-00088_Feature_Design.md` — the design document. **Read it in full before writing any code.**
- `ai-dev/active/F-00088/F-00088_Functional.md` — human-facing summary.
- `ai-dev/work/F-00088/reports/F-00088_S01_Backend_report.md` — S01 report (to understand what was already built).
- `ai-dev/work/F-00088/reports/F-00088_S02_CodeReview_report.md` — S02 review (apply any mandatory fixes from S02 first).
- Reference: `tests/e2e/playwright_wrapper.py` and `tests/e2e/conftest.py` (created in S01).
- Reference: `scripts/e2e_seed.py` (to understand existing seed shape before extending).
- Reference: `dashboard/routers/` (to understand route paths for journey navigation — navigate via the UI, not hardcoded paths).

## Output Files

- `ai-dev/work/F-00088/reports/F-00088_S03_Backend_report.md` — step report.

## Context

You are implementing the **remaining five journeys and the CI workflow**
for F-00088. S01 delivered the harness and journey 1. S03 delivers
journeys 2–6, the `e2e_smoke` subset designation, the GitHub Actions
workflow, and the documentation/skill/plan updates.

This Feature is **strictly test-infrastructure**: you MUST NOT edit any
production code (`orch/`, `dashboard/`, `executor/`). The only production-
adjacent file you may touch is `scripts/e2e_seed.py` (if a journey needs
extra seed rows) — and only to add idempotent seed calls. The merge-time
scope gate enforces this against `scope.allowed_paths`.

Read `CLAUDE.md` and `tests/CLAUDE.md` for project conventions. Read
`skills/iw-ai-core-testing/SKILL.md` — MUST-read for any test work here.

Journey screenshots go to the `evidence_dir` fixture created in S01 (a neutral
artifact dir — `IW_E2E_EVIDENCE_DIR`, defaulting to `tests/e2e/_artifacts/`).
Use neutral screenshot filenames — never bake the F-00088 ID into a permanent
journey file.

**Apply mandatory fixes from S02 first** before writing new code.

## Requirements

### 1. Apply S02 mandatory fixes

Read `F-00088_S02_CodeReview_report.md`. Fix every finding with severity
CRITICAL, HIGH, or MEDIUM (fixable) before proceeding. Do not proceed
if the S02 verdict is `fail` without addressing all mandatory issues.

### 2. Journey 2 — `tests/e2e/test_journey_queue_to_merge.py`

Mark with `@pytest.mark.e2e` AND `@pytest.mark.e2e_smoke`.

The journey should:
1. Open the project's Queue page.
2. Navigate to an existing approved work item (use seed data — navigate via the
   UI list, not a hardcoded URL; read `scripts/e2e_seed.py` to understand what
   rows exist).
3. Locate and click the "Create Batch" / "Add to batch" action.
4. Assert a batch is created and appears in the Batches page.
5. Assert zero console errors throughout.
6. Run an accessibility check on the queue/batch pages visited.
7. Navigate to the batch detail and assert it shows expected status transitions
   (the journey does not wait for an actual agent run — it asserts the batch
   creation flow and initial state, not the merge completion; if the seed includes
   a completed batch, also verify its history row).
8. Capture screenshots at each major step.

If the seed data does not have a suitable work item in `approved` state,
extend `scripts/e2e_seed.py` (idempotent) to add one. Document the
extension in the S03 report.

### 3. Journey 3 — `tests/e2e/test_journey_code_qa_sse.py`

Mark with `@pytest.mark.e2e`.

The journey should:
1. Open the project's Code / Q&A page.
2. Type a question into the code Q&A input.
3. Submit the question and assert that the SSE stream begins — the answer
   renders incrementally (text appears in the answer panel progressively;
   assert at least one non-empty chunk is rendered within a timeout).
4. Assert that at least one citation link is visible in the completed answer.
5. Assert zero console errors.
6. Run an accessibility check on the Code page.
7. Capture screenshots at: question submitted, stream in progress (if observable
   via snapshot), stream complete.

Use a configurable timeout for the SSE stream (default 30s). If the stream
does not emit a first chunk within the timeout, fail with a clear assertion
error (`SSE_TIMEOUT: no content received within 30s`) — never hang.

### 4. Journey 4 — `tests/e2e/test_journey_docs_export.py`

Mark with `@pytest.mark.e2e`.

The journey should:
1. Open the project's Docs page.
2. Navigate to an existing document (use seed data — navigate via the list).
3. Click the "Export HTML" button (or equivalent).
4. Assert the download/export completes: either a new browser tab opens with
   rendered HTML, or the response is a 200 with `Content-Type: text/html`.
   Use `playwright-cli snapshot` to confirm the export link is present; then
   verify via `curl` that the export endpoint returns non-empty HTML.
5. Click the "Export PDF" button (or equivalent).
6. Assert the PDF export endpoint returns 200 with `Content-Type: application/pdf`.
7. Assert zero console errors throughout.
8. Run an accessibility check on the Docs page.
9. Capture screenshots at each export trigger.

If the export is async (a job is queued), assert the job appears in the Jobs
page and check it transitions to completed state within a reasonable timeout
(use seed data for a completed export job if available rather than waiting
for a live run).

### 5. Journey 5 — `tests/e2e/test_journey_jobs_filters.py`

Mark with `@pytest.mark.e2e`.

The journey should:
1. Open the Jobs page.
2. Assert the unfiltered list shows job rows (seed must include at least 2–3
   different job types; extend `scripts/e2e_seed.py` if needed).
3. Select a filter (e.g. "type: code_index") from the multi-select filter UI.
4. Assert the job list updates to show only matching rows.
5. Select a second filter value and assert it narrows the results further.
6. Clear all filters and assert the full list is restored.
7. Assert zero console errors throughout (the filter interactions use htmx —
   verify no htmx error responses).
8. Run an accessibility check on the Jobs page.
9. Capture screenshots at: initial list, first filter applied, second filter, cleared.

### 6. Journey 6 — `tests/e2e/test_journey_htmx_fragments.py`

Mark with `@pytest.mark.e2e`.

**This journey is the browser-level complement to CR-00072's TestClient-level
route sweep. Note this relationship clearly in the module docstring: CR-00072
has no JS/HTMX runtime and tests for HTTP 5xx only; this journey exercises
the same pages in a real browser and asserts that htmx attributes resolve
correctly, no client-side errors occur, and no dangling `hx-target` references
exist. They are complementary, not redundant.**

The journey should:
1. For each major dashboard page that uses htmx fragments (at minimum: queue page,
   batch detail, jobs page, docs page, code page):
   a. Navigate to the page via `goto`.
   b. Read console errors — assert zero htmx error responses (lines containing
      `htmx:error` or `htmx:responseError`) and zero JS unhandled exceptions.
   c. Inspect the rendered HTML via `curl` on the same URL; extract all
      `hx-target="#X"`, `hx-include="#X"`, `aria-controls="X"`, and `for="X"`
      references; assert that every referenced `id="X"` is present in the
      same HTML response (dangling reference check).
   d. If any interactive htmx trigger is present (e.g. a pagination button, a
      filter, a modal opener), click it and assert the fragment swaps without
      a console error.
2. Capture a screenshot of at least one htmx-rich page (e.g. the jobs page with
   filters applied).
3. Assert zero console errors for the full journey.
4. Run an accessibility check on at least two of the pages visited.

If a route returns a genuine 5xx in the browser (different from CR-00072's
TestClient result), record it as an xfail with a filed Incident ID — never fix
the bug in this Feature.

### 7. `e2e_smoke` subset designation

The two journeys marked `@pytest.mark.e2e_smoke` MUST be exactly:
- `test_journey_home_navigation` (journey 1, added in S01)
- `test_journey_queue_to_merge` (journey 2, added in S03)

Verify: `uv run pytest tests/e2e/ -m e2e_smoke --collect-only -q` must
collect exactly these two modules.

### 8. GitHub Actions workflow — `.github/workflows/e2e.yml`

Create a two-job workflow:

**Job 1: `e2e-smoke`** (blocking):
- Triggers: `pull_request` and `push`. MUST NOT trigger on `schedule` or
  `workflow_dispatch` alone (it CAN also trigger on those, but must trigger
  on push/PR).
- No `continue-on-error` — this job blocks the PR if it fails.
- Steps: check out the repo, set up Python/uv (mirror the setup from
  `.github/workflows/test-quality.yml`'s integration job), bring up the
  isolated E2E stack (the workflow adapts `scripts/e2e_up.sh` — the
  implementer MUST document the required env vars: `COMPOSE_PROJECT_NAME`,
  `E2E_FRONTEND_PORT`, `E2E_DB_PORT`, `IW_BROWSER_BASE_URL`), run
  `make test-e2e-smoke`, bring down the stack in an `always:` cleanup step.

**Job 2: `e2e-full`** (informational):
- Triggers: `schedule:` nightly cron **and** `workflow_dispatch:`. MUST NOT
  trigger on `push` or `pull_request`.
- `continue-on-error: true` at job level (informational during burn-in).
- Same setup, but runs `make test-e2e`.

Neither job may hardcode ports — read `$E2E_FRONTEND_PORT` etc. from env or
workflow inputs. Add comments explaining the env vars `scripts/e2e_up.sh`
expects (operators need to configure repository secrets/variables).

### 9. Docs, skill, and plan updates

- `docs/IW_AI_Core_Testing_Strategy.md`: add the E2E layer to §3 (layers),
  add a gate-table row to §5 (include `make test-e2e-smoke` as a blocking gate
  and `make test-e2e` as a nightly periodic gate), and update §9 (remove the
  "known gap" row for the absence of journey-level browser tests; replace the
  ad-hoc `-m browser` description with the new structured E2E layer description).
- `skills/iw-ai-core-testing/SKILL.md`: add a sub-section describing the E2E
  layer — what it does, how to add a new journey (add a file under `tests/e2e/`,
  mark `@pytest.mark.e2e`, include a11y + no-console-error assertions), and
  when to promote a journey to the `e2e_smoke` subset (criteria: ≤2 journeys
  total in smoke, journey is <30s, covers a critical path). Then run
  `uv run iw sync-skills --force iw-ai-core-testing` and verify
  `.claude/skills/iw-ai-core-testing/SKILL.md` is byte-identical to the master.
- `ai-dev/work/TESTS_ENHANCEMENT.md`: set item 3.1's status to
  `DONE 2026-05-21 (F-00088)` with the link; add a `## 11. Changelog` entry
  dated 2026-05-21 summarising what shipped (6 journeys, their names, the smoke
  subset, the CI workflow, whether any journeys were xfailed with filed Incidents);
  update §9 if the E2E layer belongs in the blocking / periodic columns.

### 10. "Every test must be able to fail" — required demonstration (S03 scope)

Prove the new journeys and detectors can fail **without touching any
production code** — the entire demonstration stays inside `tests/e2e/**`.

1. **Extend `tests/e2e/test_harness_selfcheck.py`** (created in S01, unmarked).
   Add RED-first unit tests for the detection logic these journeys depend on,
   each fed synthetic in-memory input — no browser, no E2E stack:
   - Dangling-reference detector: feed an HTML fragment containing
     `hx-target="#nonexistent-id"` (with no matching `id`); assert the
     detector flags the dangling reference. Assert clean HTML passes.
   - SSE-timeout detector (journey 3): feed the stream helper a source that
     emits no chunk; assert it raises the `SSE_TIMEOUT: ...` assertion
     rather than hanging.
   Run with `uv run pytest tests/e2e/test_harness_selfcheck.py -v` and record
   the RED-then-GREEN runs as `tdd_red_evidence`.
2. **Per-journey assertion-inversion marker**: in each of the 5 new journey
   modules, add a one-line comment naming the single behavioural assertion
   that, if inverted, proves that journey can fail. The actual inverted-
   assertion RED run is performed at S14 against the live stack.

You MUST NOT edit `dashboard/`, `orch/`, or `executor/` for any reason —
including a "temporary" break that you revert. The merge-time scope gate
enforces `scope.allowed_paths`. `git status` / `git diff` must show changes
only under `scope.allowed_paths`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`, run in order and fix anything
they report:

1. `make format` — auto-fixes formatting drift; inspect the diff and re-stage.
2. `make typecheck` — zero errors involving files you touched.
3. `make lint` — zero errors.

Also run `make test-assertions` — your new test files must not trip the
assertion scanner.

## Test Verification (NON-NEGOTIABLE)

Verify the full collection:

```bash
uv run pytest tests/e2e/ --collect-only -q
# expect: only test_harness_selfcheck.py tests collected;
#         0 e2e-marked journey tests under default addopts

uv run pytest tests/e2e/ -m e2e --collect-only -q
# expect: 6 journey modules collected (all 6 journey test functions)

uv run pytest tests/e2e/ -m e2e_smoke --collect-only -q
# expect: exactly 2 journeys: home_navigation and queue_to_merge
```

Run the harness self-check unit tests (no browser or E2E stack needed):

```bash
uv run pytest tests/e2e/test_harness_selfcheck.py -v
# expect: all self-check tests pass
```

Do not report `tests_passed: true` based on collection-only checks — report
what you actually ran. The S14 qv-browser step runs the actual journeys against
the live stack.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "F-00088",
  "completion_status": "complete|partial|blocked",
  "files_changed": [],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "collection verified: 6 journeys under -m e2e; 2 under -m e2e_smoke; 0 e2e-marked journey tests under default addopts; test_harness_selfcheck.py self-check tests pass",
  "tdd_red_evidence": "harness self-check extended (tests/e2e/test_harness_selfcheck.py, in scope) — dangling-hx-target detector: RED then GREEN, flags synthetic HTML with hx-target=\"#nonexistent-id\"; SSE-timeout detector: RED then GREEN, raises SSE_TIMEOUT on a no-chunk source. Per-journey assertion-inversion comment added to each of the 5 new journey modules (RED run executed at S14). No dashboard/orch/executor file edited.",
  "blockers": [],
  "notes": "e2e_smoke subset: test_journey_home_navigation + test_journey_queue_to_merge. TESTS_ENHANCEMENT.md item 3.1 marked DONE. iw sync-skills --force iw-ai-core-testing run. Any xfailed journeys with Incident IDs: <list here>."
}
```

# Browser Verification Prompt: F-00060-S14-BrowserVerification

**Work Item**: F-00060 — Hybrid Code Q&A retrieval
**Step**: S14
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

Same rules as S01. If a testcontainer appears stuck, rely on pytest
teardown / Ryuk — never `docker kill`.

---

## Environment

The IW orchestrator has **already** started an isolated E2E stack built
from THIS worktree's source. Do NOT attempt to start, stop, or rebuild
services.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports. Always use the env var.

Do NOT run `make dev`, `make e2e-up`, any `docker compose`, `playwright install`, `agent-browser`, or `chromium.launch()` snippets.

## Input Files

- `ai-dev/active/F-00060/F-00060_Feature_Design.md` — especially AC2, AC3, AC5
- Source files from S01..S08 (see *File Manifest*)

## Output Files

- `ai-dev/active/F-00060/reports/F-00060_S14_BrowserVerification_Report.md`
- `ai-dev/active/F-00060/evidences/post/` — screenshots

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then authenticate:

```bash
playwright-cli snapshot
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules:

1. Always `snapshot` before `fill` / `click`.
2. Wait for transitions before re-snapshotting.
3. Screenshots under `ai-dev/active/F-00060/evidences/post/`.

## E2E DB seed data

The E2E stack starts with a fresh Postgres + migrations + baseline seed.
For F-00060, the verification requires:

- A project with ≥3 work items, each with `functional_doc_content`
  populated. One item should be the "button feature" used for AC3.
- At least one other item with `functional_doc_content = NULL` (so the
  fallback path is exercised).
- Git history that includes `Merge F-<ID>:` / `Merge CR-<ID>:` lines for
  those items so `git_log_resolver` finds them.

If the baseline seed does not cover this, add a fixture at
`ai-dev/active/F-00060/e2e_fixtures/001_qa_seed.py` exporting
`def seed(db: Session) -> None`, idempotent. The fixture runs **inside**
`scripts/e2e_seed.py` at stack bring-up, so it writes to the isolated E2E
DB — do NOT roll your own ad-hoc inserts from the agent subprocess.

## Writing to the E2E DB from the agent

If a specific V step needs to INSERT rows *after* the stack is up (e.g. to
inject a `DaemonEvent` and observe it in the UI), do NOT use
`orch.db.session.SessionLocal`. The worktree's `.env` pins `IW_CORE_DB_*` at
the **live** orchestration DB (port 5433) and `SessionLocal()` will quietly
write there — the dashboard under test will never see the row because it
polls the isolated `e2e-db` container. Use the DSN the daemon exports:

```bash
uv run python -c "
import os, psycopg
with psycopg.connect(os.environ['IW_BROWSER_E2E_DB_URL']) as conn:
    with conn.cursor() as cur:
        cur.execute('INSERT INTO ... VALUES (...)')
    conn.commit()
"
```

The DSN is `postgresql://iw_e2e:iw_e2e_dev@127.0.0.1:${E2E_DB_PORT}/iw_e2e`
(credentials from `docker-compose.e2e.yml`, non-secret).

## Verification Steps

### V1a: "Re-index Docs" action exists in the Code-page dropdown (AC1 surface)

1. Navigate to `$IW_BROWSER_BASE_URL/project/<seeded-project>/code`.
2. Open the action dropdown.
3. **Verify:** a "Re-index Docs" entry is present immediately below
   "Re-index changed files".
4. **Screenshot:** `F-00060_v1a_reindex_button.png`.

### V1b: Clicking "Re-index Docs" creates a `doc_index_jobs` row

1. From V1a, click "Re-index Docs".
2. **Verify via the E2E DB** (using `$IW_BROWSER_E2E_DB_URL`) that a
   `doc_index_jobs` row now exists for this project with
   `status IN ('queued', 'running', 'completed')`:

   ```bash
   uv run python -c "
   import os, psycopg
   with psycopg.connect(os.environ['IW_BROWSER_E2E_DB_URL']) as conn:
       with conn.cursor() as cur:
           cur.execute(
               \"SELECT id, status, triggered_at FROM doc_index_jobs \"
               \"WHERE project_id = 'iw-ai-core' ORDER BY triggered_at DESC LIMIT 1\"
           )
           print(cur.fetchone())
   "
   ```

3. **Screenshot:** `F-00060_v1b_job_row_created.png`.

### V1c: Job row transitions to `completed` via the E2E daemon stub

The E2E stack now runs `scripts/e2e_daemon_stub.py` (see
`docker-compose.e2e.yml:e2e-daemon-stub`) which advances queued doc-index
jobs through `running → completed` on a ~5 s cycle. The real RAG
pipeline is not exercised in E2E — the stub just flips the state columns
so downstream V steps that read the Jobs view can observe the lifecycle.

1. Wait up to 20 s for the row created in V1b to reach `status='completed'`:

   ```bash
   for _ in $(seq 1 20); do
     STATUS=$(uv run python -c "
   import os, psycopg
   with psycopg.connect(os.environ['IW_BROWSER_E2E_DB_URL']) as conn:
       with conn.cursor() as cur:
           cur.execute(\"SELECT status FROM doc_index_jobs WHERE project_id = 'iw-ai-core' ORDER BY triggered_at DESC LIMIT 1\")
           print(cur.fetchone()[0])
   ")
     echo "status: $STATUS"
     [ "$STATUS" = "completed" ] && break
     sleep 1
   done
   [ "$STATUS" = "completed" ] || { echo "job did not complete within 20s"; exit 1; }
   ```

2. Navigate to the unified Jobs view in the browser.
3. **Verify:** the job appears with `job_type='doc_indexing'` and
   `status='completed'`.
4. **Screenshot:** `F-00060_v1c_jobs_view_completed.png`.

### V2a: Workitem-aware pipeline emits phase events in order (AC2 infrastructure)

The E2E Ollama stub at `scripts/e2e_ollama_stub.py` is intentionally
**not** a real LLM — it parses the `## Work Item Context` block in the
system prompt and emits a deterministic reply that opens with a
`[1] <ID> — <title>` citation for the candidate that best matches the
question's keywords. That is enough to exercise the whole pipeline
(classifier → retrieval → allowlist → citation emission) without a real
model.

1. From the Code page, ask: "When was the New project button created?
   What does it do?" via `POST /api/projects/iw-ai-core/code/qa` with
   `context_chips=["why"]` so the classifier picks the workitem-aware
   branch unconditionally.
2. **Verify the stream emits these phase events in order:**
   `retrieving` → `finding_items` → `reading_docs` → `composing`,
   followed by `token` events, followed by at least one `citation`
   event, followed by `done`.
3. If ANY phase event is missing, V2a fails — phases are emitted by
   `orch/rag/qa.py:answer_stream_v2` so a missing one means the
   workitem_aware branch was not taken (likely a classifier bug or a
   swallowed exception in the pipeline).
4. **Screenshot:** `F-00060_v2a_phase_events.png`.

### V2b: Citation event names a work item seeded for this project

1. From V2a, inspect the `citation` events in the stream.
2. **Verify:** at least one citation's `work_item_id` field matches one
   of the seeded items (`F-99001`, `CR-99001`, `CR-99002`, `F-99002` —
   production-shape 5-digit IDs chosen to match
   `orch/rag/citation_allowlist.py:WORK_ITEM_ID_PATTERN`).
3. **Verify:** for the question "When was the New project button
   created?", the top-ranked citation is `F-99001` — the stub's keyword
   ranker prefers candidates whose title/content contains "new",
   "project", "button", "created".
4. **Screenshot:** `F-00060_v2b_citation_originating_item.png`.

### V3: Relevance filter picks the recolor item for a colour question (AC3)

With the citation-aware stub, V3 is a deterministic property check: the
stub's ranker is a simple keyword scorer and MUST pick the recolor
candidate when the question is about colour.

1. Ask: "Why is the New project button blue?" via the Q&A endpoint with
   `context_chips=["why"]`.
2. **Verify:** the first `citation` event's `work_item_id` is `CR-99001`.
   The keyword "blue" appears in that candidate's functional-doc content
   and nowhere else, so the ranker must place it first.
3. **Verify:** `CR-99002` does not appear in any citation event for this
   question (its content is about shape/rounded-rect, not blue).
4. **Screenshot:** `F-00060_v3_relevance_filter.png`.

### V4: Allowlist gates emission (AC5)

This browser check verifies the observable property that un-allowed IDs
never reach the UI. The deterministic invariant (hallucinated IDs are
stripped) is covered by `tests/unit/test_qa_v2_allowlist_wiring.py`.

1. From V2 or V3, collect all `work_item_id` values from every `citation`
   event in the stream.
2. **Verify:** every collected ID matches one of the candidates the
   stream also listed in its `phase: finding_items` detail (the set
   of allowed IDs).
3. **Verify:** no citation event carries an ID that wasn't in the
   candidate set.
4. **Screenshot:** `F-00060_v4_allowlist_stripping.png`.

### V5: Code-only path regression (no regressions)

1. Ask: "Show me the signature of `classify_query`."
2. **Verify:** the answer is code-focused; there is no "Work Item Context"
   section in the streamed response; no citations are emitted.
3. **Verify:** no console errors; no UI regressions on the Q&A surface.
4. **Screenshot:** `F-00060_v5_code_only_regression.png`.

### V6: No Regressions on sibling views

1. Visit Code, Tests, Quality, Documentation pages.
2. **Verify:** each renders without console errors.
3. **Verify:** the dashboard home / jobs view is unchanged in behaviour.
4. **Screenshot:** `F-00060_v6_no_regressions.png`.

## Pass Criteria

Every V (V1a, V1b, V1c, V2a, V2b, V3, V4, V5, V6) must pass. Any failure
requires `iw step-fail` with a reason. The V-splits mean a flake in one
sub-step no longer pollutes its siblings — report each independently.

### Distinguishing code defects from environment gaps

The daemon **no longer terminates the fix cycle on an ``ENV_DATA_MISSING:``
prefix** (see `orch/daemon/fix_cycle.py:should_attempt_fix`). A subsequent
fix cycle will always run within the cycle budget, and its prompt includes
a warning section pointing out that six recent "environmental" diagnoses on
browser_verification steps were all real code defects in disguise.

That relaxation does not make misclassification free. A fix cycle spent
on the wrong hypothesis still burns budget. Use the classification below.

- **CODE DEFECT** (normal `--reason`, no prefix):
  - Any HTTP 4xx/5xx on a page the verification visits (including 500 on
    `/project/{id}/jobs`, 404 on a route the test asserts exists).
  - Any uncaught server exception in the logs.
  - Any JS console error or `ReferenceError`.
  - A page renders but the asserted element is absent or wrong.
  - The streaming endpoint returns 200 but emits zero tokens where the stub
    provider at `scripts/e2e_ollama_stub.py` would have emitted them — that's
    a bug in the server-side pipeline, not the env.
  - An INSERT to ``$IW_BROWSER_E2E_DB_URL`` is not reflected in the
    dashboard under test — that's a routing bug (often: the agent used
    `SessionLocal` by accident and wrote to the live DB).
- **ENV_DATA_MISSING** (`--reason "ENV_DATA_MISSING: ..."`) — reserve for:
  - The `$IW_BROWSER_E2E_DB_URL` DSN points at a DB that won't accept
    connections AND the compose stack is not recoverable by editing
    ``docker-compose.e2e.yml`` or ``scripts/e2e_dashboard_entrypoint.sh``.
  - A missing seed row where no fixture file at
    ``ai-dev/active/F-00060/e2e_fixtures/*.py`` could produce it (e.g.
    because the data must come from a git-log scan of a repo the stack
    cannot access).

  Missing `functional_doc_content`, missing button-history items, or
  missing `Merge F-...:` lines are NOT ENV_DATA_MISSING — they are a
  missing fixture you are explicitly authorized to write.

## Report

Write `ai-dev/active/F-00060/reports/F-00060_S14_BrowserVerification_Report.md`
with:

- Pass/fail table for V1..V6.
- `$IW_BROWSER_BASE_URL` used.
- Any issues with `file:line` references.
- List of screenshots.
- **No regressions observed** subsection for V5 + V6.

Then call exactly one of:

```bash
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/F-00060/reports/F-00060_S14_BrowserVerification_Report.md

uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/F-00060/reports/F-00060_S14_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S14",
  "agent": "qv-browser",
  "work_item": "F-00060",
  "overall_status": "pass|fail",
  "base_url_used": "",
  "verifications": [
    {"id": "V1a", "name": "re-index docs action in dropdown", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V1b", "name": "click creates doc_index_jobs row", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V1c", "name": "daemon stub transitions row to completed", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2a", "name": "workitem_aware phase events fire in order", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2b", "name": "citation event names seeded originating item", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "colour question picks recolor item", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "allowlist gates emission", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "code-only regression", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V6", "name": "no regressions on sibling views", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```

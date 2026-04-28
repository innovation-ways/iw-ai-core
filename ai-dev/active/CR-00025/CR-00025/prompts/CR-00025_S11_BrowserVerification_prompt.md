# Browser Verification Prompt: CR-00025-S11-BrowserVerification

**Work Item**: CR-00025 -- Implement missing evidence-ingestion pipeline (CR-00020 follow-up) and backfill archived items
**Step**: S11
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions: testcontainers spun up by pytest fixtures; read-only
introspection (`docker ps`, `docker inspect`, `docker logs`); invoking
`./ai-core.sh` or `make` targets.

If your task seems to require a prohibited command, STOP and raise a blocker.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This CR adds no DDL. Do not run any `alembic upgrade/downgrade/stamp`
commands against the live orch DB.

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs -- do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:5173`, no `localhost:9900`, no `localhost:3100`). Always use the env var.

Do NOT run any of the following:
- `make dev`, `make test-e2e`, `make e2e-up`, or any `docker compose` command
- `playwright install` or `npx playwright install`
- `agent-browser`
- Any `chromium.launch()` Python/Node snippet

## Input Files

- `ai-dev/active/CR-00025/CR-00025_CR_Design.md` -- the design document
- Files modified by S01:
  - `orch/evidences.py`
  - `orch/cli/item_commands.py`
  - `orch/cli/step_commands.py`

## Output Files

- `ai-dev/active/CR-00025/reports/CR-00025_S11_BrowserVerification_Report.md` -- the mandatory report
- `ai-dev/active/CR-00025/evidences/post/` -- screenshots taken during verification

## Prerequisites

Every QvBrowser run MUST start with these commands, in this order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Then log in:

```bash
playwright-cli snapshot                       # get accessible element refs
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules:
1. Always call `playwright-cli snapshot` **before** `fill` / `click`.
2. Wait for navigation/transitions to settle before snapshotting again.
3. Screenshots go under `ai-dev/active/CR-00025/evidences/post/` with descriptive filenames.

## E2E DB seed data

The E2E stack starts with a fresh PostgreSQL with project schema and migrations applied, plus the baseline seed in `scripts/e2e_seed.py`. It does **not** mirror the production database.

If your verifications need historical data, add a fixture file:

```
ai-dev/active/CR-00025/e2e_fixtures/001_<name>.py
```

The file must export `def seed(db: Session) -> None` and is auto-run by `scripts/e2e_seed.py` after the central seed. Make seeding idempotent.

This step needs a **registered work item with a browser_verification step** so we can drive `iw step-done` against it. The baseline seed includes F-00055/CR-00001/I-00001 — check `scripts/e2e_seed.py` to see whether any of them has a browser_verification step. If not, add a fixture
`001_cr00025_evidence_fixture.py` that registers a synthetic work item
(e.g. `CR-99025`) with one `browser_verification` step in `in_progress`
state, plus pre/ and post/ files in
`ai-dev/active/CR-99025/evidences/{pre,post}/` (write the bytes to disk
in the fixture using a small embedded PNG payload).

> ⚠️ NEVER run the fixture seed from your host shell — that would write
> into the production DB. If a fixture needs to be re-seeded against a
> running E2E stack, exec INTO the container.

If the verifications cannot be satisfied with seed data alone, call
`iw step-fail` with reason prefixed `ENV_DATA_MISSING:`.

## Verification Steps

### V1: `iw approve` ingests pre evidences and the dashboard renders them

1. Inside the e2e environment, call `uv run iw approve <FIXTURE_ID>` where the fixture work item has files in `ai-dev/active/<FIXTURE_ID>/evidences/pre/`. (If the fixture pre-approves the item, skip this and verify the rows already exist.)
2. Navigate to `{{IW_BROWSER_BASE_URL}}/project/iw-ai-core/item/<FIXTURE_ID>/tab/evidences`.
3. **Verify:** the "pre" gallery shows at least one screenshot — element matching `img[src*="evidence/pre/"]` is visible. There is NO "No evidences captured for this item." paragraph.
4. **Screenshot:** `cp .playwright-cli/page-*.png ai-dev/active/CR-00025/evidences/post/CR-00025_v1_pre_evidence_visible.png`.

### V2: `iw step-done` for browser_verification ingests post evidences

1. With the fixture's browser_verification step in `in_progress` and at least one PNG in `evidences/post/`, run `uv run iw step-done <FIXTURE_ID> --step <S>`.
2. Re-navigate to the Evidences tab (or refresh).
3. **Verify:** the "post" gallery now shows the screenshot, AND inspecting the row in the DB shows `phase='post'`, `step_id='<S>'`. (You can verify the DB row by running `uv run python -c "..."` inside the e2e container against the e2e DB — DO NOT touch port 5433.)
4. **Screenshot:** `ai-dev/active/CR-00025/evidences/post/CR-00025_v2_post_evidence_visible.png`.

### V3: Post-archive visibility (the regression case)

1. Inside the e2e environment, set the fixture work item to `completed` status (via `iw step-done` for any final step, or directly in the fixture seed for simplicity).
2. Run the archive: `uv run iw archive <FIXTURE_ID>` against the e2e DB.
3. **Verify:** `ai-dev/active/<FIXTURE_ID>/` no longer exists in the worktree (or the e2e container's view of it).
4. Re-navigate to the Evidences tab.
5. **Verify:** both pre and post galleries are still populated — exactly the same screenshots as V1 and V2 are visible. The "No evidences captured for this item." paragraph must NOT appear.
6. **Screenshot:** `ai-dev/active/CR-00025/evidences/post/CR-00025_v3_post_archive_still_visible.png`.

### V4: Hard-fail on oversize evidence (AC4)

1. Add a synthetic large file to a fresh fixture work item's `evidences/pre/`. The fixture should pre-approve the item with a small file, then the test mutates the dir to add a file > `IW_CORE_EVIDENCE_MAX_BYTES` and tries to re-run `iw approve`. Alternatively, override the env var to a tiny value (e.g. 100 bytes) before the run.
2. Run `uv run iw approve <FIXTURE_ID_2>` with the oversize file present.
3. **Verify:** the command exits non-zero with a clear error message naming the file and its size, AND the work item status remains `draft` in the DB, AND no rows for that item exist in `work_item_evidences`.
4. **Screenshot:** the terminal output is sufficient — capture as `ai-dev/active/CR-00025/evidences/post/CR-00025_v4_oversize_rejected.txt` (a copy of the stderr/stdout output) or take a snapshot of the dashboard's error-handling UI if there is one.

### V5: No Regressions

1. Open existing items in the e2e dashboard (the baseline F-00055/CR-00001/I-00001) and verify the Evidences tab still works (empty state for items that have no evidences).
2. Verify no new console errors appeared on any page visited during V1..V4.
3. **Screenshot:** `ai-dev/active/CR-00025/evidences/post/CR-00025_v5_no_regressions.png`.

## Pass Criteria

All V1..V5 must pass. Any failure requires calling `iw step-fail` with a reason. There is no "mostly passed".

### Distinguishing code defects from environment gaps

- **CODE DEFECT** -- the page returned an HTTP error, threw a console exception, or the assertions about pre/post galleries failed when the rows actually exist in DB. Use a normal `--reason`.
- **ENV_DATA_MISSING** -- the page rendered cleanly but the fixture work item or its evidence files are missing from the e2e environment. Prefix the reason with `ENV_DATA_MISSING:`.

## Report

After verification, write `ai-dev/active/CR-00025/reports/CR-00025_S11_BrowserVerification_Report.md` containing:

- A pass/fail table with one row per V1..V5.
- The exact `$IW_BROWSER_BASE_URL` used.
- Any issues found, with `file:line` references if you investigated root cause.
- A list of screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection.

Then call **one** of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00025/reports/CR-00025_S11_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/CR-00025/reports/CR-00025_S11_BrowserVerification_Report.md
```

Always include the `--report` path on both success and failure.

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "qv-browser",
  "work_item": "CR-00025",
  "overall_status": "pass|fail",
  "base_url_used": "{{IW_BROWSER_BASE_URL}}",
  "verifications": [
    {"id": "V1", "name": "iw approve ingests pre evidences", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "iw step-done for browser_verification ingests post", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Post-archive visibility (regression for CR-00020 gap)", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Hard-fail on oversize evidence", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "No regressions", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```

- `overall_status`: `pass` only if every V1..V5 passed.
- `base_url_used`: The concrete URL the agent actually hit -- used by reviewers to confirm the worktree stack (not the dev server) was tested.
- `console_errors_observed`: Any console errors seen during any V(n).

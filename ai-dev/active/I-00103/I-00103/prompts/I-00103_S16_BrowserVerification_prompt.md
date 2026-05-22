# Browser Verification Prompt: I-00103-S16-BrowserVerification

**Work Item**: I-00103 -- `merge_auto_resolution_failed` event drops per-file error string
**Step**: S16
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

Standard policy. The isolated E2E stack is already up; do NOT touch it. Full policy: docs/IW_AI_Core_Agent_Constraints.md.

## ⛔ Migrations: agents generate, daemon applies

No migration in this item. Full policy: docs/IW_AI_Core_Agent_Constraints.md.

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code. The environment is ready before this prompt runs -- do NOT attempt to start, stop, or rebuild any services yourself.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:9900`, no other literal). Always use the env var.

Do NOT hardcode application route paths — prefer to navigate via the UI. The auto-merge view is reachable from the project home page (left navigation or main dashboard). Click through, do not paste a URL.

Do NOT run any of:

- `make dev`, `make e2e-up`, `make test-e2e`, any `docker compose` command
- `playwright install` / `npx playwright install`
- `agent-browser` -- use `playwright-cli` exclusively
- Any `chromium.launch()` snippet

## Input Files

- `ai-dev/active/I-00103/I-00103_Issue_Design.md` -- the design document.
- `orch/daemon/auto_merge.py` -- backend change (S01).
- `dashboard/templates/fragments/auto_merge_event_detail.html` -- frontend change (S03).
- `dashboard/static/styles.css` -- possible CSS additions (S03).

## Output Files

- `ai-dev/active/I-00103/reports/I-00103_S16_BrowserVerification_Report.md` -- mandatory report.
- `ai-dev/active/I-00103/evidences/post/` -- screenshots taken during verification.

## Prerequisites

Start with these commands, in order:

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Login if needed (most likely the IW dashboard is unauthenticated on localhost — try the auto-merge page directly first; if it 302s to a login, then log in):

```bash
playwright-cli snapshot
# If login form is visible:
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

Rules:

1. Always call `playwright-cli snapshot` BEFORE `fill` / `click` to read current accessible refs. Never reuse refs from a previous page.
2. Wait for navigation to settle before snapshotting.
3. Screenshots go under `ai-dev/active/I-00103/evidences/post/` with descriptive filenames. Workflow: `playwright-cli screenshot` (no path argument), then `cp .playwright-cli/page-*.png ai-dev/active/I-00103/evidences/post/<name>.png`.

## E2E DB seed data

The E2E stack's PostgreSQL is seeded from production via `pg_dump`. It already contains the auto-merge events from the audit window — specifically `daemon_events.id` 80528 (resolved, I-00097), 80689 (failed/timeout, I-00091), and 88770 (failed/timeout, CR-00066). These are sufficient to verify the rendering behaviour for both the "field absent" path (events 80689 / 88770 were emitted pre-fix, so they have no `per_file_errors` key) AND the "field present" path — for the present path you need to seed a fresh failed event whose metadata contains `per_file_errors`.

If your verifications require a NEW seeded event (to exercise AC3), add an idempotent fixture:

```
ai-dev/active/I-00103/e2e_fixtures/001_seed_failed_event_with_per_file_errors.py
```

Module shape:

```python
from sqlalchemy.orm import Session
from orch.db.models import DaemonEvent

PROJECT_ID = "iw-ai-core"
SENTINEL_ITEM_ID = "I-00103-fixture"

def seed(db: Session) -> None:
    existing = db.execute(
        # idempotent: only insert if not already present for this sentinel
        ...
    ).scalar_one_or_none()
    if existing:
        return
    db.add(DaemonEvent(
        project_id=PROJECT_ID,
        event_type="merge_auto_resolution_failed",
        entity_type="work_item",
        entity_id=SENTINEL_ITEM_ID,
        message="Auto-merge resolution incomplete: 0 abstained, 1 errored",
        event_metadata={
            "phase": 1,
            "abstained_files": [],
            "error_files": ["tests/dashboard/test_auto_merge_routes.py"],
            "proposed_files": [],
            "runtime_option_id": 7,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "per_file_errors": [
                {
                    "file_path": "tests/dashboard/test_auto_merge_routes.py",
                    "error": "LLM call timed out after 600s: subprocess.TimeoutExpired(...)",
                    "cli_tool": "pi",
                    "model": "minimax/MiniMax-M2.7",
                },
            ],
        },
    ))
    db.commit()
```

After writing the fixture file, re-run the seed inside the `app` container (the worktree dir is mounted at `/workspace`):

```bash
docker compose -p "$COMPOSE_PROJECT_NAME" exec app \
  uv run python scripts/e2e_seed.py
```

⚠️ NEVER run the seed from your host shell — host's `.env` points at the production DB on port 5433.

If `docker compose exec` fails, call `iw step-fail` with `--reason "ENV_DATA_MISSING: ..."`.

## Verification Steps

### V0: Pre-flight page sanity (built-in)

(Automatically prepended by the qv-browser agent — do not modify.)

### V1: Modal renders `per_file_errors` section when the field is present (AC3)

1. Navigate to the project's auto-merge page via the UI:
   - Open `$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge` (or navigate via the UI by going to the project home and clicking the "Auto-merge" / "Resolver" nav item).
2. Locate the event row for the fixture event seeded by `001_seed_failed_event_with_per_file_errors.py` — its entity_id is `I-00103-fixture`. Filter by `failed` type if needed to narrow the list.
3. Click the event row (or its "View" / detail link) to open the event-detail modal — this triggers the per-file-errors render path.
4. **Verify**: the modal shows a labelled "Per-file errors" section containing:
   - the file path `tests/dashboard/test_auto_merge_routes.py`
   - the literal error string `LLM call timed out after 600s` (substring match)
   - the runtime label `pi/minimax/MiniMax-M2.7` (or `pi` and `minimax/MiniMax-M2.7` separated; whichever S03 chose)
5. **Screenshot**: `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/I-00103/evidences/post/I-00103_v1_per_file_errors_visible.png`.

### V2: Modal renders historical event without per_file_errors (AC4 — backward compat)

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge`.
2. Locate the historical event row for daemon_event id 80689 (I-00091 failed at 2026-05-18 16:07 UTC) — this event was emitted BEFORE S01 landed and therefore has no `per_file_errors` key.
3. Click into the event to open the detail modal.
4. **Verify**:
   - The modal opens with HTTP 200, no traceback, no JS exception.
   - The "Per-file errors" section is NOT visible — no empty "Per-file errors" heading, no empty card.
   - The existing "Metadata" `<details>` section IS still visible (containing the 7 historical keys).
5. **Screenshot**: `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/I-00103/evidences/post/I-00103_v2_per_file_errors_hidden_historical.png`.

### V3: No Regressions

1. Revisit the auto-merge page list view. Verify the events table still renders correctly with all filter chips (`all / attempted / resolved / failed / skipped / health_probe / config_updated`).
2. Click into the historical `merge_auto_resolved` event (daemon_event id 80528, I-00097) — verify its existing diff viewer modal still renders correctly. The new per-file-errors section MUST NOT appear (that event is `resolved`, not `failed`).
3. Visit the project home `$IW_BROWSER_BASE_URL/project/iw-ai-core/` and confirm the status chip still renders (no new console errors).
4. Verify no new console errors appeared on any page visited during V1..V2.
5. **Screenshot**: `playwright-cli screenshot` then `cp .playwright-cli/page-*.png ai-dev/active/I-00103/evidences/post/I-00103_v3_no_regressions.png`.

## Pass Criteria

All V1..V3 must pass. Any failure — partial or ambiguous — requires `iw step-fail` with a `--reason`.

Use the failure classification table from the template:

- CODE_DEFECT: page 5xx, exception, wrong element / missing element when design says present.
- ENV_DATA_MISSING: page renders cleanly but the fixture event isn't in the DB. Add a fixture; do not retry without it.
- SPEC_MISMATCH: design and verification disagree. Do NOT patch code; fix the prompt.

## Report

Write `ai-dev/active/I-00103/reports/I-00103_S16_BrowserVerification_Report.md` containing:

- Pass/fail table for V0..V3.
- `$IW_BROWSER_BASE_URL` used.
- List of screenshots captured.
- A **No regressions observed** subsection citing what was checked in V3.

Then call:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00103/reports/I-00103_S16_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00103/reports/I-00103_S16_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S16",
  "agent": "qv-browser",
  "work_item": "I-00103",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": "code_defect|null", "screenshot": "", "notes": ""},
    {"id": "V1", "name": "per_file_errors visible (AC3)", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "historical event renders without section (AC4)", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "no regressions", "status": "pass|fail|n/a", "failure_class": "code_defect|env_data_missing|spec_mismatch|null", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```

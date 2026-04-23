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
`def seed(db: Session) -> None`, idempotent.

## Verification Steps

### V1: Re-index Docs button enqueues and completes (AC1)

1. Navigate to `$IW_BROWSER_BASE_URL/project/<seeded-project>/code`.
2. Open the action dropdown.
3. **Verify:** a "Re-index Docs" entry is present immediately below
   "Re-index changed files".
4. Click "Re-index Docs".
5. **Verify:** a job row appears with `status='queued'` transitioning to
   `running` then `completed` within 120 s in the E2E environment.
6. Navigate to the unified Jobs view.
7. **Verify:** the job appears with `job_type='doc_indexing'` and the
   expected project.
8. **Screenshot:** `F-00060_v1_reindex_complete.png`.

### V2: Workitem-aware question cites and narrates (AC2)

1. Navigate to `/project/<seeded-project>/code/qa` (or whatever the Q&A
   entry point is).
2. Ask: "When was the New project button created? What does it do?"
3. **Verify:** the streamed answer cites the originating work item (e.g.
   CR-00011) and the narrative paraphrases its functional-doc reasoning
   (colour, purpose, where it appears).
4. **Verify:** no unrelated work-item IDs appear in the citation list.
5. **Verify:** the citation snippet for the cited item is drawn from its
   functional doc, not its summary (compare first 100 chars against the
   DB value).
6. **Screenshot:** `F-00060_v2_originating_item_citation.png`.

### V3: Relevance filter drops off-topic items (AC3)

1. Ask: "Why is button X blue?" (X being the button whose history includes
   an add + recolor + reshape).
2. **Verify:** the streamed answer cites only the recolor item (CR-B) in
   the citation list.
3. **Verify:** the answer does NOT mention the reshape item (CR-C) by ID
   or reasoning.
4. **Verify:** the answer does NOT cite the original feature (F-A) even
   though git-log would include it.
5. **Screenshot:** `F-00060_v3_relevance_filter.png`.

### V4: Allowlist gates emission (AC5)

Note: hallucination is inherently non-deterministic, so the strict
"hallucinated IDs are dropped" invariant is covered by the deterministic
unit test `tests/unit/test_qa_v2_allowlist_wiring.py`. This browser check
verifies the weaker, observable property that un-allowed IDs never reach
the UI — it passes whether or not the LLM actually hallucinates.

1. Ask a question crafted to invite free association (e.g. "why did you
   change X" phrasing over a surface with known history).
2. Inspect the phase events in the streaming response to capture the
   retrieval bundle's `allowed_ids`.
3. **Verify:** every work-item ID that appears in the citation panel is
   a member of `allowed_ids`. If the LLM happened not to reference any
   out-of-bundle ID on this run, V4 still passes — note the observation
   in the report.
4. **Verify:** no un-allowed ID appears in the citation panel under any
   circumstance.
5. **Screenshot:** `F-00060_v4_allowlist_stripping.png`.

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

All V1..V6 must pass. Any failure requires `iw step-fail` with a reason.

### Distinguishing code defects from environment gaps

- **CODE DEFECT** — page errored, wrong element, console exception. Normal
  `--reason`.
- **ENV_DATA_MISSING** — HTTP 200 but seed lacks expected data. Prefix
  `--reason` with `ENV_DATA_MISSING:`.

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
    {"id": "V1", "name": "reindex button + jobs view", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "originating-item citation + functional snippet", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "relevance filter drops off-topic items", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "allowlist stripping", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "code-only regression", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V6", "name": "no regressions on sibling views", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```

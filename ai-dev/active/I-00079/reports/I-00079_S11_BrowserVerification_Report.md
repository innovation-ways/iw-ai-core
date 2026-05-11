# I-00079 S11 Browser Verification Report

## Environment
- **Base URL used:** `http://localhost:9923`
- **E2E user:** `dev@example.local`
- **Worktree project:** `iw-ai-core-e2e-i-00079` (port 9923)

## E2E Fixture Created

**File:** `ai-dev/active/I-00079/e2e_fixtures/001_empty_project.py`

The seed script was re-run inside the `e2e-dashboard` container:
```bash
docker compose -p "iw-ai-core-e2e-i00079" exec e2e-dashboard uv run python scripts/e2e_seed.py
```
Output:
```
e2e_seed: running fixture ai-dev/active/I-00077/e2e_fixtures/001_failed_doc_job.py
e2e_seed: running fixture ai-dev/active/I-00078/e2e_fixtures/001_long_pipeline.py
e2e_seed: running fixture ai-dev/active/I-00079/e2e_fixtures/001_empty_project.py
e2e_seed: project iw-ai-core + 3 modules + index job + work items + 3 per-item fixture(s)
```

The `empty-test-project` project (created by the fixture) has **no** work items, batches, or docs, causing all empty-state panels to render on its Queue, History, Batches, Docs, and Research pages.

---

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | **pass** | null | — | No dangling DOM references on any visited page. Fragment refs all resolved to matching IDs. |
| V1 | Queue empty-state CTA opens CLI-spec doc | **pass** | null | `evidences/post/I-00079_v1_queue_cta_opens_cli_spec.png` | Both CTA links (`/system/docs/IW_AI_Core_CLI_Spec#iw-approve`) render the CLI-spec doc (HTTP 200). No console errors on this page. |
| V2 | History empty-state CTA opens Architecture doc | **pass** | null | `evidences/post/I-00079_v2_history_cta_opens_architecture.png` | CTA link (`/system/docs/IW_AI_Core_Architecture`) renders the Architecture doc (HTTP 200). 5 pre-existing console errors for missing SVG diagram files (`diagrams/01-system-architecture.svg` etc.) — unrelated to this fix. |
| V3 | Batches empty-state CTA opens Daemon-Design doc | **pass** | null | `evidences/post/I-00079_v3_batches_cta_opens_daemon_design.png` | CTA link (`/system/docs/IW_AI_Core_Daemon_Design#batches`) renders the Daemon-Design doc (HTTP 200). |
| V4 | Docs/Research/All-Active CTAs open real doc pages | **pass** | null | `evidences/post/I-00079_v4_docs_index_opens.png`, `I-00079_v4_research_index_opens.png`, `I-00079_v4_all_active.png` | Docs CTA → `/system/docs/implementation/00_INDEX` (HTTP 200). Research CTA → same URL (HTTP 200). All-Active CTA → `/system/docs/IW_AI_Core_Daemon_Design` (HTTP 200). All three subdir doc pages served correctly (CR-00044 subdirectory serving confirmed working). |
| V5 | No regressions | **pass** | null | `evidences/post/I-00079_v5_no_regressions.png` | Help popover "Open full docs →" on Queue resolves to `/system/docs/IW_AI_Core_CLI_Spec#iw-approve` (same target as the empty-state CTA — AC3 satisfied). Help popover on History resolves to `/system/docs/IW_AI_Core_CLI_Spec` (help-popover and empty-state CTA intentionally diverge on History per design doc — AC3 note). No new console errors. |

---

## Console / Network Errors

| Page | Errors | Classification |
|------|--------|----------------|
| `/system/docs/IW_AI_Core_Architecture` | 5 × `Failed to load resource: 404 (Not Found)` for `diagrams/01-system-architecture.svg`, `02-end-to-end-flow.svg`, `03-daemon-execution.svg`, `04-multi-project-topology.svg`, `05-database-er.svg` | **Pre-existing** — these SVG diagram files are missing from the docs directory and are unrelated to the I-00079 fix. Not flagged as a code defect. |
| All other pages | None | — |

---

## All-Active Empty State

The all-active page **did** show its empty-state panel ("Nothing is running") because the seed data has no in-progress work items (only the 3 completed items in `iw-ai-core`). The "Daemon overview →" CTA was exercised directly and rendered the Daemon-Design doc (HTTP 200). The all-active empty state was **reachable and verified**.

---

## CTA Targets Confirmed (post-fix)

| Page | CTA Label | Target (from snapshot) | Status |
|------|-----------|-------------------------|--------|
| Queue (approved section) | "How to design an item →" | `/system/docs/IW_AI_Core_CLI_Spec#iw-approve` | ✅ |
| Queue (drafts section) | "How to design an item →" | `/system/docs/IW_AI_Core_CLI_Spec#iw-approve` | ✅ |
| History | "How execution works →" | `/system/docs/IW_AI_Core_Architecture` | ✅ |
| Batches | "About batches →" | `/system/docs/IW_AI_Core_Daemon_Design#batches` | ✅ |
| Docs library | "Doc catalogue →" | `/system/docs/implementation/00_INDEX` | ✅ |
| Research library | "Open the catalogue →" | `/system/docs/implementation/00_INDEX` | ✅ |
| All Active Work | "Daemon overview →" | `/system/docs/IW_AI_Core_Daemon_Design` | ✅ |

None of the broken patterns (`/docs/*.md`, bare `/docs/`) are present. All CTAs resolve to HTTP 200 doc pages with the dashboard chrome rendered correctly.

---

## Help Popover Cross-Check (AC3)

| Page | Help "Open full docs →" target | Empty-state CTA target | Same doc? |
|------|-------------------------------|------------------------|-----------|
| Queue | `/system/docs/IW_AI_Core_CLI_Spec#iw-approve` | `/system/docs/IW_AI_Core_CLI_Spec#iw-approve` | ✅ Yes |
| History | `/system/docs/IW_AI_Core_CLI_Spec` | `/system/docs/IW_AI_Core_Architecture` | Documented divergence (design doc explicitly notes History's CTA intentionally points at Architecture, not CLI-Spec) |
| Batches | `/system/docs/IW_AI_Core_Daemon_Design` | `/system/docs/IW_AI_Core_Daemon_Design#batches` | ✅ Same doc (anchor doesn't affect routing) |

---

## Screenshots Captured

- `ai-dev/active/I-00079/evidences/post/I-00079_v1_queue_cta_opens_cli_spec.png`
- `ai-dev/active/I-00079/evidences/post/I-00079_v2_history_cta_opens_architecture.png`
- `ai-dev/active/I-00079/evidences/post/I-00079_v3_batches_cta_opens_daemon_design.png`
- `ai-dev/active/I-00079/evidences/post/I-00079_v4_docs_index_opens.png`
- `ai-dev/active/I-00079/evidences/post/I-00079_v4_research_index_opens.png`
- `ai-dev/active/I-00079/evidences/post/I-00079_v4_all_active.png`
- `ai-dev/active/I-00079/evidences/post/I-00079_v5_no_regressions.png`

---

## Root Cause

**Pre-fix behavior (confirmed by pre-fix screenshot `evidences/pre/I-00079-broken-link-404.png`):**
- CTA href = `/docs/IW_AI_Core_CLI_Spec.md` → FastAPI 404 `{"detail":"Not Found"}`
- `dashboard/routers/docs_global.py` only registers `GET /docs` (exact) and `GET /api/docs/search`; no `/docs/{path}` route

**Post-fix behavior (verified):**
- CTA href = `/system/docs/IW_AI_Core_CLI_Spec#iw-approve` → `dashboard/routers/system.py:438` `@router.get("/docs/{doc_path:path}")` matches, strips `.md`, serves the markdown file as HTML
- Subdirectory doc `implementation/00_INDEX` correctly served (CR-00044 working)

**No code defect found.** The fix (S01) correctly updated all 7 `primary_href` values from the broken `/docs/<name>.md` form to the working `/system/docs/<name>` form. The 6 page templates and the macro have been correctly patched. The regression test in `tests/dashboard/test_empty_states.py` was added in S03.

---

## Summary

All 7 verification points pass. The broken `/docs/<name>.md` empty-state CTA links have been replaced with working `/system/docs/<name>` links. All doc pages render correctly with full dashboard chrome. The help-popover "Open full docs →" and the empty-state CTA agree on the Queue and Batches pages (AC3 satisfied; History's divergence is by design). No new console errors were introduced. The pre-existing diagram 404 errors on the Architecture page are outside the scope of this fix.

**overall_status: pass**
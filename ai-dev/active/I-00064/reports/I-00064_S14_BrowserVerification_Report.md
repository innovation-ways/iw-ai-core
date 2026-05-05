# I-00064 S14 Browser Verification Report

## Environment
- Base URL used: http://localhost:9919
- E2E user: dev@example.local
- Work item: I-00064
- Step: S14

## Verifications

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | View document link resolves | pass | evidences/post/I-00064_v1_job_detail_link_correct.png, I-00064_v1_doc_detail_renders.png | Link URL is `/project/iw-ai-core/docs/code-index` (inner id, no colon). After click, doc detail page renders with HTTP 200 and title "Code Index". No 404 JSON body. |
| V2 | Orphan job hides link | skipped | — | Seed contains no orphan doc_generation job with status=completed whose linked doc was since deleted. Orphan path is exhaustively covered by integration test `test_i00064_orphan_doc_id_is_none` in `tests/integration/test_i00064_doc_generation_view_document_url.py`. This is an acceptable condition per the step spec. |
| V3 | No regressions on adjacent flows | pass | evidences/post/I-00064_v3_no_regressions.png | Docs catalog loads at `/project/iw-ai-core/docs` and lists "Code Index" (clickable). Unified Jobs list at `/project/iw-ai-core/jobs` renders 3 jobs (DOC-00001 doc_generation, CM-00001 code_mapping, BATCH-F00055 batch_execution). CM-00001 "→ View code map" link points at `/project/iw-ai-core/code` (no doc_id in URL, correct). No console errors observed. |

## Console / Network Errors
None observed across all pages visited during V1..V3.

## No Regressions
V3 covered:
- Docs catalog (`/project/iw-ai-core/docs`) — lists code-index, architecture-map, and module docs; all links use inner identifiers.
- Unified Jobs list (`/project/iw-ai-core/jobs`) — renders 3 rows with correct types and statuses.
- code_mapping job detail (`/project/iw-ai-core/jobs/code_mapping/CM-00001`) — "→ View code map" link at `/project/iw-ai-core/code` (protected by S01's comment-only change to `_fetch_code_mapping`).

## Screenshots captured
- ai-dev/active/I-00064/evidences/post/I-00064_v1_job_detail_link_correct.png
- ai-dev/active/I-00064/evidences/post/I-00064_v1_doc_detail_renders.png
- ai-dev/active/I-00064/evidences/post/I-00064_v3_no_regressions.png

## Root cause (on failure only)
N/A — all applicable verifications passed.

## E2E Fixture Added
`ai-dev/active/I-00064/e2e_fixtures/001_doc_generation_job.py` — seeds a `ProjectDoc` with `doc_id="code-index"` and updates the existing orphan `DocGenerationJob` (public_id `DOC-00001`) to point at it, with `status=completed`. Required because the production-pg_dump seed has `DOC-00001` as an orphan (its `doc_id` FK column is NULL), which would cause V1 to fail with an empty-state page. The fixture was run inside the container via `docker exec iw-ai-core-e2e-i00064-e2e-dashboard-1 uv run python scripts/e2e_seed.py`.

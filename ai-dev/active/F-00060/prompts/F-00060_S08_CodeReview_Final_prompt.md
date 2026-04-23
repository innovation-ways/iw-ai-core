# F-00060_S08_CodeReview_Final_prompt

**Work Item**: F-00060 — Hybrid Code Q&A retrieval
**Step**: S08 — Global cross-layer review
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

Read-only `docker ps | inspect | logs` is fine. No mutation.

---

## Input Files

- `ai-dev/active/F-00060/F-00060_Feature_Design.md` — the source of truth
- All S01..S07 reports
- Every file in the *File Manifest*

## Output Files

- `ai-dev/active/F-00060/reports/F-00060_S08_CodeReview_Final_report.md` (new)

## Context

Global cross-layer review. Each prior step ran its own tests and
ground-truth checks; this step inspects the seams between layers for
correctness, AC coverage, Invariant enforcement, and regression safety.

## Review Checklist

### 1. Design-contract coverage

For AC1..AC6, trace implementation + test artefacts and mark each as
covered or not. Any uncovered AC is a blocking finding.

For Invariants 1..7, confirm each is either mechanically guaranteed or
test-enforced.

### 2. DB / ORM symmetry

Compare `DocIndexJob` with `CodeIndexJob` line-by-line. Any asymmetry not
documented in the design doc's "intentional differences" list is a finding.
Indexes, defaults, nullability, FK cascade — all must mirror.

### 3. Indexing layer correctness

- LanceDB table naming uses `docs_{project_id.replace('-', '_')}`; code
  table name pattern is untouched.
- Embed-model change triggers table drop + re-embed, matching code-indexer
  policy.
- Watermark-based upsert: simulate two runs with one item changed and
  verify only that item is re-embedded (S02 test covers this — check it
  exists).
- NUL-character sanitisation is present.
- `SentenceSplitter` chunk_size / overlap matches the design doc.

### 4. Retrieval layer correctness

- `_retrieve_evidence_bundle` populates all four collections on the
  `EvidenceBundle`.
- `_merge_and_rank_work_items` normalises each source's scores before the
  α/β/γ blend.
- The Work Item Context section is appended to the existing system prompt,
  not replacing it.
- Budget enforcement order: drop candidates 8→4 first, then downgrade
  top-3 last (verify via unit test).
- Citation snippet prefers functional doc; NULL fallback to summary.
- `citation_allowlist.filter_citations` is wired in; every emitted
  citation's `work_item_id` is validated against `bundle.allowed_ids ∩
  extracted_from_llm`.
- `answer_stream` (code-only) is byte-for-byte unchanged in the diff.

### 5. Pipeline correctness

- `DocIndexPoller.MAX_CONCURRENT_JOBS_PER_PROJECT = 1`.
- Stall timeout = 600 s.
- Orphan recovery runs before the first `poll()`.
- Recovery is idempotent.
- Existing pollers (`DocJobPoller`, batch manager, merge queue) are
  untouched in the diff.

### 6. API + frontend

- `POST /project/{project_id}/api/code/reindex-docs` returns 200 / 409 /
  404 as specified.
- The endpoint does not launch the runner directly.
- Dropdown button is placed immediately below "Re-index changed files";
  uses sibling CSS classes.
- Shared `code_job_status.html` fragment labels doc rows correctly.

### 7. Tests

- Every *Boundary Behavior* row has at least one test.
- Every *Invariant* is enforced.
- Cross-project isolation test exists.
- Code-only regression test exists.
- Relevance-filter eval test exists and passes.
- Tests use testcontainer fixtures; no live DB. LanceDB in `tmp_path`.

### 8. No regressions

- `orch/rag/qa.py` diff leaves `answer_stream` and `classify_query` call
  sites unchanged.
- `code_index_jobs` table not queried or mutated by new code.
- Existing dashboard views render unchanged (spot-check Code, Docs, Tests,
  Quality tabs via a Jinja reproduction test if available).

## Procedure

1. Read the design doc end-to-end.
2. Read every step report.
3. Walk each file in the *File Manifest* diff.
4. Run `make check` locally in the worktree.
5. Write the report grouped by *Blocking* / *Non-blocking* findings.
6. Call `iw step-done` on a clean pass; otherwise `iw step-fail` with a
   specific reason.

## Test Verification (NON-NEGOTIABLE)

1. `make check` — pass.
2. Zero blocking findings.

## Subagent Result Contract

Standard JSON with `step: "S08"`, `agent: "code-review-final-impl"`, `work_item: "F-00060"`.

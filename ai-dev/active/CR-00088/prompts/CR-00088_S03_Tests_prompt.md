# CR-00088_S03_Tests_prompt

**Work Item**: CR-00088 -- Auto-merge — partial-allowlist semantics in Phase 1 dry-run
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Allowed: pytest fixtures' testcontainers. Disallowed: `docker compose up/down/restart/build`, container/volume management.

## ⛔ Migrations: agents generate, daemon applies

No migrations.

## Input Files

- `ai-dev/active/CR-00088/CR-00088_CR_Design.md` — design (AC5 is this step's bar).
- `ai-dev/work/CR-00088/reports/CR-00088_S01_Backend_report.md`
- `ai-dev/work/CR-00088/reports/CR-00088_S02_Backend_report.md`
- `tests/integration/test_auto_merge_phase1.py` — read for the existing fixture / setup pattern; do NOT modify it.
- `tests/integration/test_auto_merge_refuse_list.py` — read for the worktree-with-conflict construction pattern.
- `docs/research/R-00076-llm-automated-merge-resolution.md` §5 — phase-ladder context.
- `ai-dev/active/AUTO_MERGE_RESOLUTION.md` — rolling tracker; update with a one-line "CR-00088 shipped" note.

## Output Files

- `tests/integration/test_auto_merge_partial_allowlist.py` — NEW file (this step creates it).
- `docs/research/R-00076-llm-automated-merge-resolution.md` — add a short subsection noting the partition semantics.
- `ai-dev/active/AUTO_MERGE_RESOLUTION.md` — append a one-line tracker update.
- `ai-dev/work/CR-00088/reports/CR-00088_S03_Tests_report.md` — Step report.

## Context

S01 + S02 changed `classify_conflicts()` + event metadata. This step adds a single integration test reproducing the **exact CR-00084 conflict shape** (the original failure that motivated this CR) and a small docs update so future readers find the new semantics.

The integration test exercises the full merge-queue path: build a worktree with rebase conflicts in three files (one allowlisted, two deferred), let the daemon's classification + dry-run path run, assert the emitted events partition correctly, and assert the worktree is byte-identical to the pre-call state (Phase-1 invariant).

## Requirements

### 1. Create `tests/integration/test_auto_merge_partial_allowlist.py`

Mirror the structure of `tests/integration/test_auto_merge_refuse_list.py` (same fixtures, same `IwTestcontainerSession`-style harness, same `_setup_conflict_worktree` pattern — read that file's helpers first; do NOT duplicate them inline if a fixture already exists in `tests/conftest.py` or a `tests/fixtures/` module — import it).

Test: `test_cr00084_shape_partitions_event_metadata`.

Setup:
- Build a worktree with rebase conflicts in three files:
  - `docs/foo.md` (allowlisted by the default `**/*.md` pattern)
  - `Makefile` (not allowlisted, not refused)
  - `pyproject.toml` (not allowlisted, not refused)
- Use the default `AutoMergeConfig` (don't override `allowlist_patterns` or `refuselist_patterns`); rely on `executor/auto_merge.toml` defaults so the test exercises real config.
- Phase = 1 (dry-run). Stub the LLM call so no real `ANTHROPIC_API_KEY` is needed — the test's job is to assert metadata partitioning, NOT LLM behaviour. Use whatever stub the existing `test_auto_merge_phase1.py` uses (likely a `monkeypatch.setattr(auto_merge, "invoke_llm_for_file", ...)` returning an `LLMCallResult` with `abstained=False, proposed_content="<stub>"`).

Assertions:

```python
# NOTE: SQLAlchemy reserves `metadata` on DeclarativeBase, so the Python
# attribute on DaemonEvent is `event_metadata` (the SQL column is still
# named `metadata`). Mirror tests/integration/test_auto_merge_phase1.py
# and tests/integration/test_auto_merge_refuse_list.py — never use
# `event.metadata[...]` in a test or it raises AttributeError.
attempted = _latest_event(db, project_id, item_id, EVENT_AUTO_RESOLUTION_ATTEMPTED)
assert attempted.event_metadata["allowlisted_files"] == ["docs/foo.md"]
assert attempted.event_metadata["deferred_files"] == ["Makefile", "pyproject.toml"]
assert attempted.event_metadata["phase"] == 1

resolved = _latest_event(db, project_id, item_id, EVENT_AUTO_RESOLVED)
assert "docs/foo.md" in resolved.event_metadata.get("proposed_files", [])
assert resolved.event_metadata["deferred_files"] == ["Makefile", "pyproject.toml"]

# Phase-1 invariant: worktree untouched
post_hash = _hash_worktree_tree(worktree_path)
assert post_hash == pre_hash, "Phase 1 must not mutate the worktree"

# Work item still ends failed (Phase-1 behaviour)
wi = db.query(WorkItem).filter_by(project_id=project_id, id=item_id).one()
assert wi.status == "failed"
```

Provide a `_hash_worktree_tree` helper inline (use `git ls-files | xargs sha256sum | sha256sum` semantics in Python, or import an existing helper if one exists in `tests/fixtures/`).

Use module-level fixtures (no autouse cleanup outside the testcontainer). Do NOT mutate the production DB — testcontainers only (see `tests/CLAUDE.md`).

### 2. Update `docs/research/R-00076-llm-automated-merge-resolution.md`

Find the section that describes the classification pipeline (look for "allowlist" / "refuse list" / "classify_conflicts"). Add a short subsection (3–6 sentences) titled "Partial-allowlist semantics (CR-00088)" describing:
- The change from all-or-nothing to partition.
- `deferred_files` as the new metadata key.
- That refuse-list precedence is unchanged.
- That Phase 1 still doesn't mutate the worktree; the partition only affects what the LLM is invoked for and what the dashboard renders.

Do NOT touch any other section.

### 3. Update `ai-dev/active/AUTO_MERGE_RESOLUTION.md`

Append (do not insert) a one-line tracker entry under whatever timeline/log section exists, e.g.:

```markdown
- **2026-05-25 (CR-00088)** — Partition allowlist: when at least one conflicted file is allowlisted, run LLM on the eligible subset and surface non-allowlisted files as `deferred_files` in event metadata. Phase stays 1 (dry-run, no worktree mutation). Sequencing prereq for the Phase-2 promotion CR.
```

### 4. Do NOT touch in this step

- `orch/daemon/auto_merge.py` / `orch/daemon/merge_queue.py` (S01 + S02 are done).
- Any unit test under `tests/unit/test_auto_merge_*.py` (S01 + S02 own those).
- Any executor file (`executor/auto_merge.toml`, `executor/worktree_commit.sh`).
- Any other research doc or tracker.

## TDD Approach

The new integration test is RED before S01+S02's changes are present. Since this step runs after S01+S02, capture the RED state by explaining in the report that S01's RED unit tests + the partition logic itself stand as the RED-evidence chain, and this integration test is the GREEN end-to-end confirmation. Do NOT `git checkout` or `git stash` source files at runtime to manufacture a fresh RED — pre-fix reproduction is a design-time exercise, not a runtime verification (see iw-new-incident SKILL.md §5b).

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

Applied to this step concretely:

- BAD: `assert "allowlisted_files" in attempted.event_metadata` (key-exists; passes even if partition logic regresses to empty list)
- BAD: `assert isinstance(attempted.event_metadata["deferred_files"], list)` (shape; passes for `[]`)
- BAD: `assert len(resolved.event_metadata["proposed_files"]) > 0` (non-empty; passes if the wrong file is proposed)
- GOOD: `assert attempted.event_metadata["allowlisted_files"] == ["docs/foo.md"]` (exact list with order)
- GOOD: `assert attempted.event_metadata["deferred_files"] == ["Makefile", "pyproject.toml"]` (exact partition)
- GOOD: `assert "docs/foo.md" in resolved.event_metadata.get("proposed_files", [])` AND `assert "Makefile" not in resolved.event_metadata.get("proposed_files", [])` (specific value present + specific value absent)

Every metadata assertion in the new test MUST be a specific-value check, not a shape check.

### Reproduction & Regression Tests

This step's single integration test serves as BOTH:
- **Reproduction** — runs the exact CR-00084 conflict shape (3 files: 1 allowlisted, 2 deferred) end-to-end through the merge-queue path. Before S01+S02's changes, this test would have failed because the partition wouldn't have been emitted.
- **Regression** — pins the partition behavior (refuse-list still wins, order preserved, Phase-1 worktree untouched, work-item-still-failed) so that any future change that breaks any of these invariants fails this test loudly.

Do NOT collapse the assertions into a single `assert True`-style happy-path check. Assert each invariant separately with a clear failure message.

## Acceptance Criteria for this step

1. New integration test file exists at `tests/integration/test_auto_merge_partial_allowlist.py` and passes.
2. The test reproduces the CR-00084 conflict shape (3 files; 1 allowlisted, 2 deferred).
3. The test asserts event-metadata partition AND worktree non-mutation AND work-item-still-failed.
4. Research doc R-00076 has a partial-allowlist subsection.
5. Tracker `AUTO_MERGE_RESOLUTION.md` has the one-line entry.
6. `make lint && make test-assertions && make typecheck` all green. Run targeted tests only: `uv run pytest tests/integration/test_auto_merge_partial_allowlist.py -v`. Do NOT run `make test-integration` or `make test-unit` (full-suite execution is owned by the QV gates S10/S11).

## Hard rules

- Allowed paths: `tests/integration/test_auto_merge_partial_allowlist.py` (new), `docs/research/R-00076-llm-automated-merge-resolution.md` (append-only), `ai-dev/active/AUTO_MERGE_RESOLUTION.md` (append-only), `ai-dev/work/CR-00088/reports/**`.
- Do NOT touch any production Python file.
- Do NOT call real LLM APIs — stub `invoke_llm_for_file`.
- Use testcontainer DB only — never the production orch DB on port 5433.

## Result Contract

Emit the standard `iw step-done` result contract JSON with:
- `tdd_red_evidence`: short string describing the RED chain (S01's unit tests OR the temporary-revert approach).
- `files_changed`: exact list.
- `tests_added`: `tests/integration/test_auto_merge_partial_allowlist.py::test_cr00084_shape_partitions_event_metadata`.

# F-00084_S04_CodeReview_Backend_prompt

**Work Item**: F-00084 — LLM-Assisted Merge Conflict Resolution (Phase 0 + Phase 1 dry-run)
**Step**: S04 (Per-agent review of S03)
**Agent**: code-review-impl

---

## Inputs

- `ai-dev/active/F-00084/F-00084_Feature_Design.md`
- `ai-dev/active/F-00084/reports/F-00084_S03_Backend_report.md`
- Diff of files in `files_changed` from the S03 report
- Canonical reference: `docs/research/R-00076-llm-automated-merge-resolution.md` §5.4, §5.5, §5.7

## Output

- `ai-dev/active/F-00084/reports/F-00084_S04_CodeReview_report.md`

## Review Checklist (S03-specific)

### Module structure

- [ ] `orch/daemon/auto_merge.py` exists with the dataclasses and functions from the design's §"Requirements 1".
- [ ] All four new event-type STRING constants are defined and used consistently (no string literals scattered through code).
- [ ] `PHASE_*` constants exist; `phase >= 2` paths raise `ValueError` (Phase 2/3 reserved for follow-up CR).

### Phase-0 short-circuit (Invariant 2)

- [ ] `attempt_resolution()` with `config.phase == 0` MUST NOT call `subprocess.run` for an LLM. Verify by reading the code path; absence of subprocess calls before the return is the gate.
- [ ] The Phase-0 path emits `merge_auto_resolution_skipped` with `reason="phase_0"`.
- [ ] Unit test `test_attempt_resolution_phase_0_no_llm` (in S03's RED tests) exists and asserts subprocess.run is NOT called (mock and check call_count == 0).

### Dry-run never-applies (Invariant 3)

- [ ] In `attempt_resolution()` Phase 1, there is NO call to `git add`, `git rebase --continue`, or any subprocess that mutates the worktree's git index. `git show :1:`/`:2:`/`:3:` reads are fine. `git log -p` reads are fine.
- [ ] Return value of `attempt_resolution()` is `AutoMergeResult(success=False, ...)` on EVERY code path in Phase 1.
- [ ] Unit test asserts worktree index/HEAD hashes are unchanged after `attempt_resolution()` returns.

### Classification correctness

- [ ] `classify_conflicts()` order of precedence matches R-00076 §5.2 and the design's Boundary Behavior table:
      refuse-list > binary > oversized hunk > oversized file > too-many-files > not-allowlisted > eligible.
- [ ] Mixed refuse-list + eligible → `skipped_reason="mixed_refuse_list"` (refuse wins).
- [ ] Binary detection actually reads file bytes (not just suffix) — `\x00` in first 8KB OR suffix match.
- [ ] `fnmatch` (or equivalent glob) used for patterns, not regex.
- [ ] Empty `eligible_files` after filtering → `skipped_reason="not_allowlisted"`.

### Prompt builder (R-00076 §5.5)

- [ ] All 5 prompt sections present: work-item header, file purpose / path, recent-commits-both-sides, three-way file content (base/ours/theirs), instructions (ABSTAIN, no-invention, output-format).
- [ ] `prompt_hash = sha256(prompt)` computed and stored in `LLMCallResult`.
- [ ] Item description is truncated to ~500 words (or otherwise bounded — must not be unbounded).
- [ ] No environment variables or credentials leak into the prompt (no `os.environ`, no auth headers).
- [ ] Prompt is deterministic given identical inputs — no `datetime.now()` interpolation, no random sampling.

### LLM invocation

- [ ] `invoke_llm_for_file()` uses `executor/step_executor.sh` via subprocess.run — NOT a direct Anthropic/OpenAI SDK call.
- [ ] Timeout = `config.llm_call_timeout_seconds`; timeout maps to `LLMCallResult(error="timeout", ...)`.
- [ ] Non-zero exit captured in `LLMCallResult.error`.
- [ ] `ABSTAIN` token detection is exact-match-after-strip (tolerant of trailing whitespace/newline only).
- [ ] `(cli_tool, model)` resolved via `_resolve_runtime_option`; fallback to project default if id missing.

### merge_queue.py integration

- [ ] New parsing code inserted AFTER existing `_CONFLICT_MARKER_RE` parse and BEFORE the `merge_failed` status assignment.
- [ ] Existing `merge_conflict` DaemonEvent still fires on every conflict.
- [ ] Existing `BatchItem.status = merge_failed` still executes.
- [ ] All new code is inside a try/except so an exception in auto_merge cannot prevent today's failure handling.
- [ ] Event emission ORDER: `merge_auto_resolution_attempted` → (LLM calls) → `merge_auto_resolved | _failed | _skipped` → existing `merge_conflict`.
- [ ] Event metadata payload size is checked against `max_event_metadata_bytes`; oversized entries truncated with a `truncated_files: [...]` marker.

### step_executor_lib.sh extension

- [ ] New `auto_merge_resolve` case branch added.
- [ ] `_run_agent_oneshot` helper is NEW and minimal: stdin → LLM CLI → stdout. No DB writes, no PID files, no `iw step-done`.
- [ ] No regression to existing step-launch flow.

### Config loader

- [ ] `AutoMergeConfig.load()` uses `tomllib` (stdlib).
- [ ] Missing file → defaults (no exception thrown to caller).
- [ ] Malformed TOML → defaults + sentinel so caller can emit `auto_merge_config_invalid`.
- [ ] Reserved phase (>= 2) → caller refuses with clear error.

### Hot reload

- [ ] SIGHUP path re-reads `executor/auto_merge.toml`. Cache at module level.
- [ ] Reload is integrated with existing project_registry SIGHUP — no separate signal handler.

### Logging and audit

- [ ] Each public function logs entry/outcome at INFO with `item_id` (and `file_path` where applicable).
- [ ] Logger is `logging.getLogger(__name__)` — not a custom config.
- [ ] No PII leakage in logs (item descriptions are not logged in full).

### Invariant coverage (cross-check against design §"Invariants")

- [ ] Invariant 1 (refuse-list → 0 LLM tokens): refuse-list short-circuits BEFORE any subprocess call.
- [ ] Invariant 2 (phase 0 → 0 LLM tokens): verified above.
- [ ] Invariant 3 (Phase 1 never `git add`/`git rebase --continue`): verified above.
- [ ] Invariant 4 (operator UX unchanged): existing merge_conflict + merge_failed paths intact.
- [ ] Invariant 5 (event_metadata <= 256 KB): truncation logic present.
- [ ] Invariant 6 (decision tree deterministic): no `now()` / random in `classify_conflicts`.
- [ ] Invariant 7 (agent + model = configured): `_resolve_runtime_option` is the ONLY source of (cli_tool, model).
- [ ] Invariant 8 (failed LLM leaves clean state): verified by reading code — `invoke_llm_for_file` returns a result; the caller must NOT mutate the worktree on failure.

### Project conventions

- [ ] `DaemonEvent.metadata` accessed via Python attribute `event_metadata` (NOT `metadata`).
- [ ] Sync SQLAlchemy — no `async def`.
- [ ] Subprocess noqa comments where appropriate.
- [ ] Type hints throughout; `Mapped[]` style if any ORM (you shouldn't need it).

### Out-of-scope guard

- [ ] No new alembic migration files (this Feature uses JSONB metadata only).
- [ ] No `executor/worktree_commit.sh` edits — that was S01.
- [ ] No new tests beyond the RED-phase unit-test stubs that S03 needed to drive its TDD (those tests should fail at S03's start and be green at S03's end). The full test suite is S06's work.
- [ ] No API or frontend changes.

## Severity Mapping

- **CRITICAL** — Phase 1 actually applies a resolution (Invariant 3 violation); Phase 0 calls the LLM (Invariant 2 violation); refuse-list bypassed; existing merge_conflict event suppressed.
- **HIGH** — Event ordering wrong; metadata truncation missing; runtime_option_id lookup broken; deterministic-prompt invariant violated.
- **MEDIUM** — Logging gaps; missing type hints; subprocess timeouts not enforced.
- **LOW** — Style nits; missing docstrings.

## Result Contract

Standard code-review JSON.

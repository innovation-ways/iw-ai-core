# F-00084_S02_CodeReview_Pipeline_prompt

**Work Item**: F-00084 — LLM-Assisted Merge Conflict Resolution (Phase 0 + Phase 1 dry-run)
**Step**: S02 (Per-agent review of S01)
**Agent**: code-review-impl

---

## Inputs

- `ai-dev/active/F-00084/F-00084_Feature_Design.md`
- `ai-dev/active/F-00084/reports/F-00084_S01_Pipeline_report.md`
- Diff of files in `files_changed` from the S01 report
- Canonical reference: `docs/research/R-00076-llm-automated-merge-resolution.md` §5.2, §5.3, §5.7

## Output

- `ai-dev/active/F-00084/reports/F-00084_S02_CodeReview_report.md`

## Review Checklist (S01-specific)

### Correctness vs design

- [ ] `executor/auto_merge.toml` exists with `phase = 0` default, the documented allowlist/refuselist patterns, and limits from the Feature Design §"In Scope" and R-00076 §5.2.
- [ ] `runtime_option_id = null` default; comments explain how the lookup falls back to project default.
- [ ] Refuse-list explicitly includes `orch/db/migrations/versions/*.py`, `.gitleaks.toml`, `.env*`, `.gitignore`, `orch/db/identity.py`, `orch/config.py`, all `executor/*.sh`, `executor/scope_gate.py`, `executor/auto_merge.toml`, `uv.lock`, and the binary-suffix list.
- [ ] Allowlist patterns scoped to `tests/**`, `docs/**`, `ai-dev/active/**/reports/**` only — no source-code paths.

### Bash edits in `executor/worktree_commit.sh`

- [ ] New code is inserted in the conflict branch (after existing auto-resolve rules, before the abort branch) — does NOT alter the happy path or the existing `_REBASE_TAKE_OURS` / `_REBASE_TAKE_THEIRS` behaviour for `uv.lock` / `Makefile`.
- [ ] Bash refuse-list is a defence-in-depth coarse match (prefixes + suffixes). The Python side will do the rich-glob classification.
- [ ] `AUTO_RESOLVE_REQUESTED=<json>` marker is emitted on stdout (NOT stderr) when at least one conflict is eligible AND no refuse-list match.
- [ ] `AUTO_RESOLVE_SKIPPED=<json>` marker is emitted on stdout when any refuse-list match (with `reason="refuse_list"` or `"mixed_refuse_list"`).
- [ ] Both markers' JSON includes the right fields (eligible_files, refuse_files, branch, main_sha, reason).
- [ ] Existing `CONFLICT_FILES=<json>` marker is STILL emitted on every conflict — F-00076 parser must keep working.
- [ ] The rebase is ALWAYS aborted on conflict in Phase 0/1 — script exit code remains 1; bash never calls `git rebase --continue` in this Feature.
- [ ] `--resume-rebase` flag is parsed and exits 2 with the documented error message.
- [ ] `jq` fallback to awk follows the existing pattern at lines 362–373.

### Safety / defence-in-depth

- [ ] Stdout/stderr separation is preserved (log → stderr, markers → stdout). The Python side parses stdout for markers; mixing would break F-00076's parser.
- [ ] If TOML file is missing, bash defaults `AUTO_MERGE_PHASE=0` (no crash).
- [ ] If `grep` finds the phase line but value is non-integer, treat as 0 (defensive).
- [ ] No new dependencies (no `yq`, no `python -c ...` — only existing `grep`/`awk`/`jq` patterns).

### Documentation

- [ ] Inline comment block in `worktree_commit.sh` cites R-00076 and explains the Phase-0/1 always-abort invariant.
- [ ] `auto_merge.toml` comments explain phase ladder, runtime_option_id fallback, and the refuse-list defence-in-depth principle.

### Project conventions

- [ ] `executor/CLAUDE.md` rules respected — no docker, no alembic invocations.
- [ ] Existing script style matched (quoting, `>&2` for logs, marker format).
- [ ] The S01 report's "manual verification" output is included and matches what the design requires.

### Out-of-scope guard

- [ ] No Python module touched in this step (`orch/daemon/auto_merge.py` and `orch/daemon/merge_queue.py` are S03's work).
- [ ] No test file touched (tests live in S06).

## Severity Mapping

- **CRITICAL** — refuse-list missing a required pattern, `git rebase --continue` accidentally introduced, secret/sensitive files allowed through.
- **HIGH** — marker emitted on stderr instead of stdout, `--resume-rebase` not refused, missing CONFLICT_FILES marker emit.
- **MEDIUM** — phase parsing fragile, comments missing, refuse-list ordering subtly wrong.
- **LOW** — style nits.

## Result Contract

Emit standard code-review JSON with `decision: approve|request_changes|escalate` and a findings list.

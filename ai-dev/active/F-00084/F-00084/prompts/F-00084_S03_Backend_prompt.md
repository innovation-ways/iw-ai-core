# F-00084_S03_Backend_prompt

**Work Item**: F-00084 — LLM-Assisted Merge Conflict Resolution (Phase 0 + Phase 1 dry-run)
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in `tests/integration/` are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This step writes NO migrations.** The four new event-type strings are TEXT values in `daemon_events.event_type`; `event_metadata` is JSONB and already accepts arbitrary payloads. Do NOT generate any alembic file in this step.

## Input Files

- Runtime step state: `uv run iw item-status F-00084 --json`
- Design doc: `ai-dev/active/F-00084/F-00084_Feature_Design.md`
- Canonical reference: `docs/research/R-00076-llm-automated-merge-resolution.md` — **§5.2 decision tree, §5.4 LLM resolver, §5.5 prompt template, §5.7 DaemonEvent types** are mandatory reading
- S01 deliverables (just merged): `executor/auto_merge.toml`, edited `executor/worktree_commit.sh`
- Existing patterns to study before writing code:
  - `orch/daemon/merge_queue.py` — `_merge_item()` and `_emit_event()`; the F-00076 `_CONFLICT_MARKER_RE` parser (around line 454)
  - `orch/daemon/migration_rebase.py` — `_capture_worktree_state()`, `_git()` helper; pattern for safe `subprocess.run` against a worktree
  - `executor/step_executor.sh` / `executor/step_executor_lib.sh` — agent launch path; you will reuse this to invoke the LLM
  - `orch/db/models.py` — `DaemonEvent` (line 1271), `AgentRuntimeOption` (search for class name); confirm the FK column name for the runtime-option lookup
  - `orch/cli/` — how existing commands look up `agent_runtime_options`

## Output Files

- `ai-dev/active/F-00084/reports/F-00084_S03_Backend_report.md` — Step report

## Context

You are implementing the daemon-side logic for LLM-assisted merge conflict resolution, **Phase 0 plumbing + Phase 1 dry-run** only. You will:

1. Create a new module `orch/daemon/auto_merge.py`.
2. Edit `orch/daemon/merge_queue.py` to detect the new stdout markers from S01 and route to `auto_merge.attempt_resolution()`.

Your code MUST:
- Never call `git add` or `git rebase --continue` in this Feature (Phase 2's job).
- Use the existing `step_executor.sh` runtime path to invoke the LLM — no new SDK dependency, no direct Anthropic/OpenAI calls.
- Reuse the F-00081 `agent_runtime_options` table for the cli_tool + model selection.
- Emit the four new DaemonEvent types per R-00076 §5.7 schema.
- Be safe-by-default: Phase 0 short-circuits before any LLM call.

## Requirements

### 1. New module `orch/daemon/auto_merge.py`

Public surface (see also F-00084 design §"In Scope"):

```python
# Module-level constants
PHASE_DISABLED = 0
PHASE_DRY_RUN = 1
PHASE_TESTS_ONLY = 2     # Reserved for follow-up CR — refuse if encountered
PHASE_BROADER = 3        # Reserved — refuse if encountered

# Event type strings (NO enum — TEXT column)
EVENT_AUTO_RESOLUTION_ATTEMPTED = "merge_auto_resolution_attempted"
EVENT_AUTO_RESOLVED = "merge_auto_resolved"
EVENT_AUTO_RESOLUTION_FAILED = "merge_auto_resolution_failed"
EVENT_AUTO_RESOLUTION_SKIPPED = "merge_auto_resolution_skipped"
EVENT_AUTO_MERGE_CONFIG_INVALID = "auto_merge_config_invalid"


@dataclass(frozen=True)
class AutoMergeConfig:
    phase: int
    runtime_option_id: int | None
    allowlist_patterns: tuple[str, ...]
    refuselist_patterns: tuple[str, ...]
    max_conflict_hunk_lines: int
    max_conflicted_files_per_merge: int
    max_file_size_bytes: int
    max_event_metadata_bytes: int
    llm_call_timeout_seconds: int

    @classmethod
    def load(cls, path: Path) -> "AutoMergeConfig":
        """Load from TOML; return defaults on missing/malformed file.
        On malformed: log ERROR and emit EVENT_AUTO_MERGE_CONFIG_INVALID
        (the caller is responsible for emitting the event — this method
        returns a defaults-only config and a parse_error string)."""
        ...


@dataclass(frozen=True)
class ClassificationResult:
    eligible_files: tuple[str, ...]
    refuse_files: tuple[str, ...]
    oversized_files: tuple[str, ...]      # file size > max_file_size_bytes
    oversized_hunks: tuple[str, ...]      # conflict region > max_conflict_hunk_lines
    binary_files: tuple[str, ...]
    skipped_reason: str | None             # None if at least one eligible_file remains and no refuse_files


def classify_conflicts(
    worktree_path: Path,
    conflict_files: list[str],
    config: AutoMergeConfig,
) -> ClassificationResult:
    """Apply the decision tree from R-00076 §5.2.

    Order (highest precedence first):
      1. Any refuse-list match anywhere → skipped_reason = "refuse_list"
                                          (or "mixed_refuse_list" if also eligible)
      2. Any binary file → skipped_reason = "binary"
      3. Any oversized file (size or hunk) → skipped_reason = "hunk_too_large"
                                              or "file_too_large"
      4. len(conflict_files) > max_conflicted_files_per_merge → "too_many_files"
      5. Any file NOT matching allowlist → "not_allowlisted"
      6. Else → eligible_files = all of conflict_files; skipped_reason = None
    """
    ...


@dataclass(frozen=True)
class LLMCallResult:
    file_path: str
    abstained: bool
    proposed_content: str | None       # None if abstained or error
    error: str | None                  # populated on subprocess error / timeout
    model: str
    cli_tool: str
    input_tokens: int | None
    output_tokens: int | None
    prompt_hash: str                   # sha256(prompt)
    output_hash: str | None            # sha256(proposed_content) if any


@dataclass(frozen=True)
class AutoMergeResult:
    success: bool                       # False in Phase 1 (always)
    phase: int
    resolved_files: tuple[str, ...]
    abstained_files: tuple[str, ...]
    error_files: tuple[str, ...]
    llm_calls: tuple[LLMCallResult, ...]


def attempt_resolution(
    *,
    db: Session,
    project_id: str,
    item_id: str,
    worktree_path: Path,
    eligible_files: list[str],
    branch_name: str,
    main_sha: str,
    config: AutoMergeConfig,
    item_title: str,
    item_description: str,
) -> AutoMergeResult:
    """Per-file LLM invocation + audit-event emission.

    Behaviour by phase:
      phase == 0 → short-circuit: emit EVENT_AUTO_RESOLUTION_SKIPPED with
                   reason="phase_0" and return AutoMergeResult(success=False).
                   ZERO LLM calls. ZERO subprocess invocations.
      phase == 1 → emit EVENT_AUTO_RESOLUTION_ATTEMPTED, then for each
                   eligible file call invoke_llm_for_file(); then emit
                   EVENT_AUTO_RESOLVED (or EVENT_AUTO_RESOLUTION_FAILED if
                   any abstention or error). NEVER call git add. NEVER call
                   git rebase --continue. Return AutoMergeResult(success=False)
                   regardless — Phase 1 is always-abort.
      phase >= 2 → refuse with ValueError("phase X reserved for follow-up CR").
    """
    ...


def invoke_llm_for_file(
    *,
    db: Session,
    project_id: str,
    worktree_path: Path,
    file_path: str,
    branch_name: str,
    main_sha: str,
    config: AutoMergeConfig,
    item_id: str,
    item_title: str,
    item_description: str,
) -> LLMCallResult:
    """Build the prompt (per build_resolution_prompt) and invoke the LLM
    via subprocess to executor/step_executor.sh with step_type=auto_merge_resolve.

    The agent slug + model are looked up via _resolve_runtime_option(db, project_id, config).

    On non-zero exit, timeout, or LLM output that is literally 'ABSTAIN':
      return LLMCallResult(abstained=True, proposed_content=None, ...).
    """
    ...


def build_resolution_prompt(
    *,
    worktree_path: Path,
    file_path: str,
    branch_name: str,
    main_sha: str,
    item_id: str,
    item_title: str,
    item_description: str,
) -> str:
    """Construct the prompt per R-00076 §5.5.

    MUST include:
      - work item id, title, first 500 words of description
      - relative file path
      - merge-base content: git show :1:<file>
      - main's version (ours during rebase): git show :2:<file>
      - branch's version (theirs during rebase): git show :3:<file>
      - recent commit log on main: git log -p -n 3 <main_sha> -- <file>
      - recent commit log on branch: git log -p -n 3 HEAD -- <file>
      - the explicit ABSTAIN escape token instruction
      - no-invention clause
      - output-format spec: full resolved file content, no markdown fences,
        no prose

    The prompt MUST be deterministic given identical inputs (used by
    test_auto_merge_prompt.py invariants test).
    """
    ...


def _resolve_runtime_option(
    db: Session,
    project_id: str,
    config: AutoMergeConfig,
) -> tuple[str, str] | None:
    """Look up (cli_tool, model) from agent_runtime_options.

    Order:
      1. If config.runtime_option_id is set: load that row; if missing or
         disabled, fall through to (2).
      2. Project default: AgentRuntimeOption where project_id matches AND
         is_default = True AND enabled = True.
      3. Return None — caller treats as 'runtime_option_missing' error.
    """
    ...


def parse_auto_resolve_marker(stdout: str) -> dict | None:
    """Parse 'AUTO_RESOLVE_REQUESTED=<json>' from worktree_commit.sh stdout.
    Returns the parsed dict, or None if marker absent.
    Returns None (and logs WARNING) if marker present but JSON is malformed."""
    ...


def parse_auto_skip_marker(stdout: str) -> dict | None:
    """Parse 'AUTO_RESOLVE_SKIPPED=<json>' from worktree_commit.sh stdout."""
    ...


_AUTO_RESOLVE_REQUESTED_RE = re.compile(r"^AUTO_RESOLVE_REQUESTED=(.+)$", re.MULTILINE)
_AUTO_RESOLVE_SKIPPED_RE = re.compile(r"^AUTO_RESOLVE_SKIPPED=(.+)$", re.MULTILINE)
```

**Implementation specifics**:

- **`AutoMergeConfig.load()`**: use `tomllib.loads(Path(path).read_text())`. On `FileNotFoundError` return defaults. On `tomllib.TOMLDecodeError` log ERROR and return defaults — but ALSO set a sentinel on the returned object (e.g., a `parse_error` attribute) so callers can emit `EVENT_AUTO_MERGE_CONFIG_INVALID`. Implementation hint: use `dataclasses.replace` to attach a private field, or expose a tuple `(config, parse_error_or_none)` from the loader.

- **`classify_conflicts()`**: use `fnmatch.fnmatchcase()` for glob patterns. Binary detection: `is_binary = b"\x00" in path.read_bytes()[:8192]` plus a suffix check. Hunk-size check: count lines between `<<<<<<<` and `>>>>>>>` markers in the conflicted file. **Order of precedence is from R-00076 §5.2 and Boundary Behavior table** — implement deterministically; same inputs MUST produce same classification (Invariant 6).

- **`attempt_resolution()`** — Phase 0 path:
  1. Emit `EVENT_AUTO_RESOLUTION_SKIPPED` with `reason="phase_0"`.
  2. Return `AutoMergeResult(success=False, phase=0, resolved_files=(), abstained_files=(), error_files=tuple(eligible_files), llm_calls=())`.
  3. ZERO subprocess calls. Unit test will assert via mocking subprocess.

- **`attempt_resolution()`** — Phase 1 path:
  1. Resolve runtime option (`_resolve_runtime_option`); if None, emit `EVENT_AUTO_RESOLUTION_FAILED` with `reason="runtime_option_missing"` and return.
  2. Emit `EVENT_AUTO_RESOLUTION_ATTEMPTED` with metadata `{phase: 1, conflict_files: [...], policy_decision: "allowlist", runtime_option_id: <id>}`.
  3. For each eligible file (sequentially OR with concurrency=3 — see Notes): call `invoke_llm_for_file()`.
  4. If any `LLMCallResult.abstained` or `.error`: emit `EVENT_AUTO_RESOLUTION_FAILED` with the per-file details.
  5. If all clean: emit `EVENT_AUTO_RESOLVED` with metadata including each file's `proposed_content` (capped at `max_file_size_bytes`), `llm_calls` summary, and total tokens.
  6. **Critical**: total metadata payload size MUST be checked against `max_event_metadata_bytes` (Invariant 5). If oversized, truncate `proposed_content` fields and add a metadata key `truncated_files: [...]`.
  7. ALWAYS return `AutoMergeResult(success=False, ...)` — Phase 1 never auto-applies.

- **`invoke_llm_for_file()`** implementation:
  1. Build prompt via `build_resolution_prompt()`.
  2. Compute `prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()`.
  3. Look up `(cli_tool, model)` via `_resolve_runtime_option`.
  4. Invoke `executor/step_executor.sh` with a new step type `auto_merge_resolve`. The script accepts the prompt on stdin and writes the LLM's response to stdout. **You will need to extend `executor/step_executor_lib.sh` `case "$step_type" in` to add this new step type** — keep the addition minimal: it should be a single-shot prompt → LLM CLI invocation, identical to fix-cycle but with no DB writes.
  5. Use `subprocess.run` with `timeout=config.llm_call_timeout_seconds`, capture stdout+stderr+returncode.
  6. If timeout or non-zero exit: return `LLMCallResult(abstained=False, proposed_content=None, error=<stderr or "timeout">, ...)`.
  7. If stdout starts with `ABSTAIN` (allow trailing whitespace/newline): return `abstained=True`.
  8. Otherwise: return `proposed_content=stdout.strip()`, `output_hash=sha256(...)`, parse token counts if the CLI exposes them (opencode and claude-code both write token counts to stderr; capture via a simple regex — if not present, leave as None).

- **`build_resolution_prompt()`**: keep the prompt structure exactly per R-00076 §5.5. Use `git -C <worktree_path> show :1:<file>` etc. via subprocess. Bound each section's size to `max_file_size_bytes`. The prompt MUST be a single string. Test S06 will hash this and pin the structure.

### 2. Edits to `orch/daemon/merge_queue.py`

Inside `_merge_item()`, **after** the existing `_CONFLICT_MARKER_RE` parse and **before** setting `BatchItem.status = merge_failed`:

```python
# F-00084: parse new auto-resolve markers
auto_resolve_request = auto_merge.parse_auto_resolve_marker(output)
auto_skip = auto_merge.parse_auto_skip_marker(output)

if auto_skip is not None:
    # Refuse-list / mixed / decision-tree skip — bash already aborted.
    # Emit the audit event; merge_conflict still fires below.
    auto_merge.emit_skipped_event(db, project_id, item_id, auto_skip)

elif auto_resolve_request is not None:
    # Bash classified at least one file as eligible — invoke the Python decision
    # tree (which may further filter) and the LLM (Phase 1 only).
    try:
        config = auto_merge.AutoMergeConfig.load(
            Path(orch_root) / "executor" / "auto_merge.toml"
        )
    except auto_merge.AutoMergeConfigError as exc:
        auto_merge.emit_config_invalid_event(db, project_id, item_id, str(exc))
        config = auto_merge.AutoMergeConfig.defaults()

    classification = auto_merge.classify_conflicts(
        worktree_path=Path(worktree_path),
        conflict_files=list(auto_resolve_request["eligible_files"]),
        config=config,
    )

    if classification.skipped_reason is not None:
        # Python's classifier disagrees with bash's coarse match (more
        # patterns to apply, hunk-size check, binary check, etc.) — record
        # the skip and proceed to the existing merge_failed path.
        auto_merge.emit_skipped_event(
            db,
            project_id,
            item_id,
            {
                "reason": classification.skipped_reason,
                "eligible_files": list(auto_resolve_request["eligible_files"]),
                "refuse_files": list(classification.refuse_files),
                "binary_files": list(classification.binary_files),
                "oversized_files": list(classification.oversized_files),
                "oversized_hunks": list(classification.oversized_hunks),
            },
        )
    else:
        work_item = db.execute(...).scalar_one()      # fetch item title/description
        result = auto_merge.attempt_resolution(
            db=db,
            project_id=project_id,
            item_id=item_id,
            worktree_path=Path(worktree_path),
            eligible_files=list(classification.eligible_files),
            branch_name=auto_resolve_request["branch"],
            main_sha=auto_resolve_request["main_sha"],
            config=config,
            item_title=work_item.title,
            item_description=work_item.design_doc_text or "",  # truncated in prompt builder
        )
        # In Phase 1 result.success is ALWAYS False — we fall through to the
        # existing merge_failed path below. Phase 2 will add a non-fall-through
        # branch here.
```

**Critical invariants for this edit**:

- The existing `merge_conflict` event MUST still fire on every conflict. Do NOT replace it.
- The existing `BatchItem.status = merge_failed` MUST still execute. Do NOT alter operator UX.
- All new code paths must be wrapped in a try/except so an exception in `auto_merge.attempt_resolution` does NOT prevent the existing failure handling. Log + emit `merge_auto_resolution_failed` with `failed_reason=internal_error` on any exception.
- The order of event emission MUST be: `merge_auto_resolution_attempted` → (per-file LLM) → `merge_auto_resolved | merge_auto_resolution_failed | merge_auto_resolution_skipped` → existing `merge_conflict`. This ordering is asserted by S06's integration tests.

### 3. Minimal extension to `executor/step_executor_lib.sh`

Add a new case branch for `step_type=auto_merge_resolve`:

```bash
case "$step_type" in
  ...existing cases...
  auto_merge_resolve)
    # F-00084: invoke the configured agent runtime in one-shot mode.
    # Prompt comes from stdin (passed by orch/daemon/auto_merge.py).
    # Output goes to stdout. No DB writes. No step-done call.
    # Agent + model are passed as CLI args from auto_merge.py.
    _run_agent_oneshot "$agent" "$model"
    ;;
esac
```

`_run_agent_oneshot` is a NEW helper you add to the same lib file. It must:
- Accept stdin as the prompt.
- Call `opencode run -p <model>` or `claude --print --model <model>` (depending on `agent`) with the prompt.
- Write the model's response to stdout.
- NOT call `iw step-done`, NOT touch any DB, NOT create any worktree state.

Keep this thin — the existing `step_executor_lib.sh` already has the patterns; just don't reuse the step-launching machinery that writes PIDs and reports.

### 4. Hot-reload integration

The project_registry SIGHUP path already exists. Add a small handler in `orch/daemon/auto_merge.py` (or in `main.py` if cleaner) that re-reads `executor/auto_merge.toml` on SIGHUP. Cache the config at module level; the merge queue reads from the cache on each `_merge_item` invocation.

### 5. Logging and audit hygiene

- Every public function in `auto_merge.py` MUST `logger.info` its entry and outcome with `item_id` and (where relevant) `file_path` in the message.
- DaemonEvent metadata is the source of truth for audit; do NOT also write to ad-hoc log files.
- `prompt_hash` and `output_hash` (sha256) MUST be stored in event metadata — this lets us identify deterministic vs flaky LLM behaviour without storing the full prompt.

## Project Conventions

- Read `orch/CLAUDE.md` for orch package rules.
- Use SQLAlchemy 2.0 `Mapped[]` declarative style only if you add ORM code (you shouldn't — `DaemonEvent` already exists).
- Sync (NOT async) SQLAlchemy — daemon is single-threaded.
- `DaemonEvent.metadata` is mapped as `event_metadata` in Python — CLAUDE.md hard rule.
- Use `with get_orch_session() as db:` for any standalone DB access; the merge queue already passes a session into `_merge_item` — reuse it.
- subprocess invocations MUST use `# noqa: S603, S607` comments where appropriate (see existing patterns).
- File reads MUST handle UnicodeDecodeError gracefully — use `path.read_text(errors="replace")` or pre-check is_binary.

## TDD Requirement

**RED phase** — before writing any production code:

1. Write failing unit tests in `tests/unit/test_auto_merge_config.py`, `tests/unit/test_auto_merge_classifier.py`, `tests/unit/test_auto_merge_prompt.py`, `tests/unit/test_auto_merge_marker.py` (per S06's test plan, but you write the **stubs** here as RED tests against the not-yet-implemented module).
2. Run them: `uv run pytest tests/unit/test_auto_merge_*.py -v` — must fail with `ImportError: cannot import name 'AutoMergeConfig'` (or similar). Capture the failing line.

**GREEN phase** — implement `auto_merge.py` and the `merge_queue.py` edits until those unit tests pass.

**REFACTOR phase** — tidy without breaking RED→GREEN.

S06 expands these tests to integration coverage; S03 lays the unit-test groundwork to validate your module's contracts.

Record the captured RED output in `tdd_red_evidence` in your result contract.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format` — auto-fix.
2. `make typecheck` — zero errors involving `orch/daemon/auto_merge.py` and `orch/daemon/merge_queue.py`.
3. `make lint` — zero errors.
4. **Targeted unit tests**: `uv run pytest tests/unit/test_auto_merge_*.py -v` — must be green at completion.

## Test Verification

- Run only the targeted unit tests you wrote (`tests/unit/test_auto_merge_*.py`).
- Do NOT run `make test-unit` (full suite) or `make test-integration` — those are S13/S14 QV gates.
- The integration tests for full daemon flow live in S06.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "F-00084",
  "completion_status": "complete",
  "files_changed": [
    "orch/daemon/auto_merge.py",
    "orch/daemon/merge_queue.py",
    "executor/step_executor_lib.sh",
    "tests/unit/test_auto_merge_config.py",
    "tests/unit/test_auto_merge_classifier.py",
    "tests/unit/test_auto_merge_prompt.py",
    "tests/unit/test_auto_merge_marker.py"
  ],
  "preflight": {
    "format": "ok",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "<N> passed, 0 failed (targeted unit tests for auto_merge)",
  "tdd_red_evidence": "tests/unit/test_auto_merge_config.py::test_load_defaults — ImportError: cannot import name 'AutoMergeConfig' from 'orch.daemon.auto_merge'",
  "blockers": [],
  "notes": "Phase 1 dry-run wiring complete. attempt_resolution() returns success=False unconditionally; merge_queue.py falls through to the existing merge_failed path. New event types are plain TEXT strings — no enum migration. _run_agent_oneshot extension in step_executor_lib.sh is minimal (no DB writes, no PID handling)."
}
```

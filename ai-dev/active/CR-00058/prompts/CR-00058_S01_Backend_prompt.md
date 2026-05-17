# CR-00058_S01_Backend_prompt

**Work Item**: CR-00058 — Configurable per-project scope-overlap gate with block/allow policy
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any docker container/volume/network mutating command. Allowed: `docker ps`, `docker inspect`, `docker logs`, `./ai-core.sh`, `make`. Testcontainer fixtures spun up by pytest are exempt. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step **does not** add or modify any Alembic migration. The new policy lives in the existing `Project.config` JSONB column. If you find yourself wanting to add a migration, STOP — review the design doc with the operator.

## Input Files

- `ai-dev/active/CR-00058/CR-00058_CR_Design.md` — design doc (read first; "Current Behavior", "Desired Behavior", AC1–AC6, "Affected Components")
- `orch/daemon/scope_overlap.py` — main file you are changing
- `orch/daemon/project_registry.py` — file you are extending
- `orch/daemon/batch_manager.py` — caller you are wiring
- `tests/unit/daemon/test_scope_overlap.py` — existing unit tests (will need updates)
- `CLAUDE.md`, `orch/CLAUDE.md` — project conventions
- Runtime step state via `uv run iw item-status CR-00058 --json`

## Output Files

- `ai-dev/active/CR-00058/reports/CR-00058_S01_Backend_report.md`
- Modified: `orch/daemon/scope_overlap.py`
- Modified: `orch/daemon/project_registry.py`
- Modified: `orch/daemon/batch_manager.py`
- Modified: `tests/unit/daemon/test_scope_overlap.py`
- Modified: `tests/integration/test_f_00076_gate_performance.py` (signature update only)
- Modified: `tests/integration/daemon/test_batch_manager_scope_gate.py` (signature update only)
- New: `tests/unit/daemon/test_project_registry_overlap_gate.py`
- New: `tests/integration/daemon/__init__.py` (empty, if missing)

## Context

You are turning the F-00076 cross-batch overlap gate from a hardcoded rule into a per-project policy. This step owns the three backend files and their unit tests; the integration scenario, dashboard surfacing, and docs are separate steps. Read AC1–AC5 in the design doc — they are the contract you must satisfy.

## Requirements

### 1. `scope_overlap.py` — explicit policy parameters, drop hardcoded test-strip

Change `find_blocking_items` to a kw-only contract:

```python
def find_blocking_items(
    candidate_paths: list[str],
    in_flight: list[tuple[str, list[str]]],
    *,
    block_patterns: list[str],
    allow_patterns: list[str],
) -> list[tuple[str, list[str]]]:
```

Behavior:

- **Remove** the implicit `_strip_test_globs` calls in **both** `find_blocking_items` (lines 152, 157) and `globs_intersect` (lines 91-92). The caller is now responsible for supplying the desired test policy via `allow_patterns`. Update `globs_intersect`'s docstring to drop the "after stripping test-path globs from both sides" clause. (The `_strip_test_globs` helper itself, and the `is_test_path` classifier, both stay — `is_test_path` is also used elsewhere; see #3.)
- Run the existing intersection logic (`globs_intersect` + sibling-via-`_same_parent`) using the current candidate/in-flight globs — but only after filtering: a candidate or in-flight glob whose pattern matches *no* `block_patterns` entry is treated as out-of-scope for the gate. The most common policy is `block_patterns=["**/*"]`, which matches everything.
- After producing the per-in-flight `intersecting` list, apply the allow filter **per conflicting glob**: any glob in `intersecting` that matches any pattern in `allow_patterns` is dropped. If `intersecting` becomes empty, that in-flight item is removed from the result tuple.
- Return type is unchanged: `list[tuple[item_id, conflicting_globs]]`. Order preserved.

Edge cases:

- `block_patterns == []` → never blocks (the gate is effectively off for this project).
- `allow_patterns` patterns are matched against globs using `fnmatch.fnmatch(glob, pattern)` plus an anchor-containment check (re-use `_pattern_to_anchor` + `_is_under_dir`) so that `dashboard/**` matches `dashboard/static/chat_assistant/chat.js`.
- Unparseable patterns (e.g. raises in `fnmatch`) must not crash the daemon: catch and log a one-line warning, treat as no-match.

### 2. `is_test_path` and default policy helper

Keep `is_test_path` exported as-is — it's a useful classifier used by `batch_planner.py` too. Add a module-level constant:

```python
DEFAULT_ALLOW_PATTERNS: tuple[str, ...] = (
    "tests/**",
    "test/**",
    "__tests__/**",
    "**/*conftest*",
    "**/*.test.*",
    "**/*.spec.*",
)
DEFAULT_BLOCK_PATTERNS: tuple[str, ...] = ("**/*",)
```

These are the values `project_registry` will synthesize when `overlap_gate` is absent. Putting them next to the matching logic keeps the contract honest.

### 3. `project_registry.py` — parse `overlap_gate`, expose on `ProjectConfig`

In `ProjectConfig`, add two fields (both with `field(default_factory=...)` to avoid mutable-default pitfalls):

```python
overlap_block_patterns: list[str] = field(default_factory=lambda: list(DEFAULT_BLOCK_PATTERNS))
overlap_allow_patterns: list[str] = field(default_factory=lambda: list(DEFAULT_ALLOW_PATTERNS))
```

(Import `DEFAULT_BLOCK_PATTERNS` / `DEFAULT_ALLOW_PATTERNS` from `orch.daemon.scope_overlap`.)

Extract parsing into a private `_parse_overlap_gate(project_id: str, raw: object) -> tuple[list[str], list[str]]` helper placed next to `_validate_staleness_config`. Validation rules:

- When `raw` is `None` / absent → return defaults.
- When `raw` is not a `dict` → warn, return defaults.
- For each of `block_on_overlap` / `allow_on_overlap`: when present, must be a list of strings; non-list → warn and skip that side (keep its default); non-string entries are dropped with a per-entry warning; empty list is honored (e.g. `block_on_overlap=[]` means "never block").
- Defaults are only applied for the side that's missing or malformed — supplying `allow_on_overlap` without `block_on_overlap` still gets the strict block default, not no-op.

Wire it in `_build_project_config` after the existing `scope_gate_enabled` block; pass the parsed lists into the `ProjectConfig(...)` constructor call.

Note: the new keys live in `.iw-orch.json` (read via `_read_iw_orch_json`), not in `projects.toml`. Mirror the placement of `scope_gate_enabled`.

### 4. `batch_manager.py` — read policy, emit allowed-by-policy event

Inside `_process_batch`, where you currently call:

```python
blocked_by = scope_overlap.find_blocking_items(candidate_paths, in_flight_scopes)
```

`BatchOrchestrator.__init__` already receives `project_config: ProjectConfig` (see `orch/daemon/batch_manager.py:82-91`) and stores it as `self.project_config`. Read the policy directly from there — there is no `self.registry`. Use `cfg = self.project_config` and pass `block_patterns=cfg.overlap_block_patterns, allow_patterns=cfg.overlap_allow_patterns`.

Then compute the "would-have-been-blocked under default" diff to decide whether to emit `item_overlap_allowed_by_policy`. Use this pattern:

```python
blocked_by = scope_overlap.find_blocking_items(
    candidate_paths, in_flight_scopes,
    block_patterns=cfg.overlap_block_patterns,
    allow_patterns=cfg.overlap_allow_patterns,
)
if not blocked_by:
    # Would the strict default have blocked? Only run the more expensive check
    # when the project actually customised its policy — avoids redundant work.
    if (list(cfg.overlap_block_patterns) != list(scope_overlap.DEFAULT_BLOCK_PATTERNS)
            or list(cfg.overlap_allow_patterns) != list(scope_overlap.DEFAULT_ALLOW_PATTERNS)):
        default_blocked = scope_overlap.find_blocking_items(
            candidate_paths, in_flight_scopes,
            block_patterns=list(scope_overlap.DEFAULT_BLOCK_PATTERNS),
            allow_patterns=list(scope_overlap.DEFAULT_ALLOW_PATTERNS),
        )
        if default_blocked:
            _emit_event(
                db, self.project_id, "item_overlap_allowed_by_policy",
                item.work_item_id, "work_item",
                f"Allowed: {item.work_item_id} overlapped with "
                f"{', '.join(bid for bid, _ in default_blocked)} but policy released it",
                {
                    "candidate_item_id": item.work_item_id,
                    "in_flight_item_ids": [bid for bid, _ in default_blocked],
                    "dropped_globs": sorted({g for _, globs in default_blocked for g in globs}),
                    "matched_allow_patterns": sorted({
                        p for p in cfg.overlap_allow_patterns
                        if any(_matches(g, p)
                               for _, globs in default_blocked for g in globs)
                    }),
                },
            )
```

Emit the event **once per launch decision** — i.e. only when the candidate actually launches (in the same branch that calls `self._launch_item(db, item)`). Do NOT emit it during the dependency-failed branch or the still-held branch. Use the same de-dup discipline as the existing `item_held_for_scope` block (which fires per poll, but per blocking item — we want per *launch*, so emit *before* `_launch_item`).

Add a small `_matches(glob: str, pattern: str) -> bool` helper somewhere in `scope_overlap.py` (or reuse the public function it implements) so the event metadata calculation is consistent with the gate's own matching.

### 5. Unit tests (TDD — RED first)

Update `tests/unit/daemon/test_scope_overlap.py`:

- Find every existing test that relies on the old hardcoded test-strip and convert it to pass `block_patterns=["**/*"], allow_patterns=list(DEFAULT_ALLOW_PATTERNS)` explicitly. The same assertions should still pass.
- Add new cases per the design doc's "TDD Approach" section:
  - `test_default_policy_blocks_source_overlap`
  - `test_default_policy_with_test_allows_releases_tests`
  - `test_allow_takes_precedence_per_conflicting_glob`
  - `test_allow_releases_full_overlap`
  - `test_sibling_directory_overlap_respects_allow`
  - `test_anchor_containment_respects_allow`
  - `test_unparseable_block_pattern_treated_as_no_match` (use a pattern that triggers `fnmatch` edge cases or simulate by patching)
  - `test_empty_block_patterns_means_no_gating`

Create `tests/unit/daemon/test_project_registry_overlap_gate.py`:

- `test_parse_valid_overlap_gate`
- `test_parse_missing_block_synthesises_default`
- `test_parse_malformed_block_warns_and_defaults`
- `test_parse_non_string_pattern_dropped`
- `test_partial_block_uses_default_for_missing_side`
- `test_empty_block_list_honored`

Use `caplog` for warning assertions.

**RED requirement** — for each new behavioural test you add, run it before the implementation exists, confirm the failure mode is `AssertionError` / `AttributeError` (not `ImportError` / `SyntaxError`), and record one line per failing test under `tdd_red_evidence` in your result.

### 6. Update other call sites of the kw-only signature

`find_blocking_items` is also called positionally from these two existing integration tests — update them in-scope to the new kw-only contract (pass `block_patterns=list(DEFAULT_BLOCK_PATTERNS), allow_patterns=list(DEFAULT_ALLOW_PATTERNS)`); behaviour assertions must remain unchanged:

- `tests/integration/test_f_00076_gate_performance.py` (lines ~89, ~104, ~118)
- `tests/integration/daemon/test_batch_manager_scope_gate.py` (line ~161)

Also create `tests/integration/daemon/__init__.py` (empty) if it doesn't exist — this avoids pytest collection edge cases when the new `tests/integration/daemon/test_overlap_gate_policy.py` lands in S02.

### 7. Do not regress existing tests

Targeted run only:

```bash
uv run pytest tests/unit/daemon/test_scope_overlap.py tests/unit/daemon/test_project_registry_overlap_gate.py -v
uv run pytest tests/unit/daemon/test_project_registry.py -v
uv run pytest tests/integration/test_f_00076_gate_performance.py tests/integration/daemon/test_batch_manager_scope_gate.py -v
```

`make test-unit` and `make test-integration` are owned by S12/S13 — do NOT run them here.

## Project Conventions

Read `orch/CLAUDE.md` for daemon conventions (sync SQLAlchemy, append-only `daemon_events`, `event_metadata` Python-side reserved-name workaround). Match the style of the surrounding code in `scope_overlap.py` and `project_registry.py` — they're both well-commented and the new code should not break the rhythm.

## TDD Requirement

Follow Red-Green-Refactor strictly. RED first; capture one failure line per new behavioural test in `tdd_red_evidence`.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`:

1. `make format` — auto-fix and re-stage.
2. `make typecheck` — zero errors involving your touched files.
3. `make lint` — zero errors.

Record each in `preflight`.

## Test Verification (NON-NEGOTIABLE)

Run only the test files you modified (see #6). Do NOT run `make test-unit` or `make test-integration`.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00058",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/scope_overlap.py",
    "orch/daemon/project_registry.py",
    "orch/daemon/batch_manager.py",
    "tests/unit/daemon/test_scope_overlap.py",
    "tests/unit/daemon/test_project_registry_overlap_gate.py",
    "tests/integration/test_f_00076_gate_performance.py",
    "tests/integration/daemon/test_batch_manager_scope_gate.py",
    "tests/integration/daemon/__init__.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/unit/daemon/test_scope_overlap.py::test_allow_takes_precedence_per_conflicting_glob — AssertionError: ['orch/foo.py'] != []",
  "blockers": [],
  "notes": ""
}
```

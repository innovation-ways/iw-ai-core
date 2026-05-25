# CR-00087_S02_BackendImpl_prompt

**Work Item**: CR-00087 -- Auto-amend scope violations matching per-project allow-patterns
**Step**: S02
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures.
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

If your task seems to require a prohibited command, STOP and raise a blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step adds NO migration. Do not run alembic commands against the live DB.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00087 --json`.
- `ai-dev/active/CR-00087/CR-00087_CR_Design.md` — Design document.
- `orch/daemon/scope_amendment.py` — file to modify.
- `orch/daemon/scope_overlap.py` — reference for `_matches` (matcher to reuse).
- `tests/unit/daemon/test_scope_amendment.py` — file where the new helper tests go.

## Output Files

- `ai-dev/work/CR-00087/reports/CR-00087_S02_BackendImpl_report.md` — Step report

## Context

You are implementing **Step 2** of CR-00087. This step adds a single pure helper, `should_auto_amend`, to `orch/daemon/scope_amendment.py`. The helper does no I/O and no DB access — it answers a single yes/no question that S03 will call inside `_complete_fix_cycle`.

Read the design doc first (especially **AC2, AC3, AC4**). Then read the existing `orch/daemon/scope_amendment.py` and `orch/daemon/scope_overlap.py:_matches` so you understand the matcher contract.

## Requirements

### 1. Add the pure helper `should_auto_amend` (orch/daemon/scope_amendment.py)

Signature and behaviour:

```python
def should_auto_amend(
    violations: list[str],
    allow_patterns: list[str],
    max_paths: int | None,
) -> bool:
    """Return True when an auto-amend should fire for these violations.

    Returns True only when ALL of:
      1. allow_patterns is non-empty (feature off when empty);
      2. violations is non-empty (nothing to amend means nothing to do);
      3. max_paths is None OR len(violations) <= max_paths;
      4. EVERY violation in `violations` matches at least one pattern in
         `allow_patterns` via fnmatch + anchor-containment (the same
         matcher semantics as orch.daemon.scope_overlap._matches).
    """
```

Implementation notes:

- **Reuse the matcher.** `orch/daemon/scope_overlap.py` already has a `_matches(glob, pattern)` function and a `_pattern_to_anchor(pattern)` helper that together implement `fnmatch + anchor-containment`. Pick ONE of these approaches and capture the choice in your report:
  - **(a) Promote `_matches` to a public name.** Rename `_matches` to `match_path_against_pattern` in `scope_overlap.py` (keep `_matches` as a thin backward-compat alias if it has other callers). Import the public name into `scope_amendment.py`. This is preferred because it avoids duplication.
  - **(b) If you cannot promote because tests pin `_matches` directly**, import the underscore-prefixed function from `scope_overlap` (acceptable in same-package imports). Do NOT copy-paste the function body — duplicating a matcher creates a long-term divergence risk.
- The helper is **pure** — no logging, no exceptions, no side effects. Return `False` for any unexpected input shape (the caller in S03 will never pass bad input because the registry's `_parse_auto_amend_scope` from S01 has already sanitised it; but pure-helper hygiene means handle empty / non-list input gracefully without raising).
- Place the helper directly in `orch/daemon/scope_amendment.py`. Add a module-level `__all__` entry if the file already maintains one (it currently does not — leave as-is if absent).

### 2. Unit tests (tests/unit/daemon/test_scope_amendment.py)

Following **TDD (Red-Green-Refactor)**. Write the tests FIRST and confirm RED before implementing.

Add a new test class or test functions covering this matrix:

- `allow_patterns=[]` → returns `False`, even with empty violations.
- `violations=[]` and `allow_patterns=["tests/**"]` → returns `False` (nothing to amend).
- `violations=["tests/unit/test_foo.py"]`, `allow_patterns=["tests/**"]`, `max_paths=None` → returns `True`.
- `violations=["tests/unit/test_foo.py", "docs/notes.md"]`, `allow_patterns=["tests/**", "**/*.md"]`, `max_paths=10` → returns `True`.
- `violations=["tests/unit/test_foo.py", "orch/daemon/fix_cycle.py"]`, `allow_patterns=["tests/**"]`, `max_paths=10` → returns `False` (partial match — one violation doesn't match any pattern).
- `violations=["tests/a.py", "tests/b.py", "tests/c.py", "tests/d.py"]`, `allow_patterns=["tests/**"]`, `max_paths=3` → returns `False` (exceeds cap).
- `violations=["tests/a.py"]`, `allow_patterns=["tests/**"]`, `max_paths=1` → returns `True` (at-cap is allowed).
- Anchor-containment: `violations=["docs/sub/notes.md"]`, `allow_patterns=["docs/**"]`, `max_paths=None` → returns `True` (matcher should treat `docs/**` as containing `docs/sub/notes.md`, matching `_matches` semantics).
- Anchor-containment: `violations=["dashboard/static/chat.js"]`, `allow_patterns=["dashboard/**"]`, `max_paths=None` → returns `True`.

**RED capture**: pick the first test (e.g. `test_should_auto_amend_returns_true_for_single_matching_violation`), implement only the test, and run it via `uv run pytest tests/unit/daemon/test_scope_amendment.py::<test_name> -v`. Confirm it fails with `ImportError` or `AttributeError` (function doesn't exist yet) — wait, no: an ImportError is NOT acceptable as RED evidence (per CLAUDE.md TDD rules). Adjust by either:
  - Writing a stub `def should_auto_amend(*args, **kwargs): raise NotImplementedError` first, then running the test (it should fail with `NotImplementedError` — valid RED), OR
  - Writing a stub that returns `False` unconditionally, then running the test (it should fail with `AssertionError` — valid RED).
Capture the test id and the first 2-3 lines of failure output.

## Project Conventions

Read `orch/CLAUDE.md` and root `CLAUDE.md`. Match existing helper signatures and docstring style in `orch/daemon/scope_amendment.py` and `orch/daemon/scope_overlap.py`.

## TDD Requirement

Follow TDD (Red-Green-Refactor). Do not skip the RED phase. Tests must exist before implementation code.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`:

1. **`make format`** — auto-fixes formatting drift.
2. **`make typecheck`** — must report zero errors involving the files you touched.
3. **`make lint`** — must report zero errors.

## Test Verification (NON-NEGOTIABLE)

After implementation, run only the targeted tests:

```bash
uv run pytest tests/unit/daemon/test_scope_amendment.py -v
```

If you renamed `_matches` → `match_path_against_pattern` in `scope_overlap.py`, also run the overlap tests to confirm no regression:

```bash
uv run pytest tests/unit/daemon/test_scope_overlap.py -v
```

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "backend-impl",
  "work_item": "CR-00087",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/scope_amendment.py",
    "tests/unit/daemon/test_scope_amendment.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/unit/daemon/test_scope_amendment.py::test_should_auto_amend_returns_true_for_single_matching_violation — AssertionError: assert False is True",
  "blockers": [],
  "notes": "Matcher reuse choice: (a) renamed _matches → match_path_against_pattern in scope_overlap.py, OR (b) imported _matches directly from scope_overlap. State which and why."
}
```

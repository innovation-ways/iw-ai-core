# I-00084_S03_Tests_prompt

**Work Item**: I-00084 — Stale origin/main ref breaks make diff-coverage
**Step**: S03
**Agent**: tests-impl

---

## Input Files

- `ai-dev/active/I-00084/I-00084_Issue_Design.md` — see "Test to Reproduce" and 3 ACs
- `ai-dev/work/I-00084/reports/I-00084_S01_Pipeline_report.md`
- `tests/CLAUDE.md`

## Output Files

- `tests/integration/test_worktree_setup_origin_main_sync.py` (new file)
- `ai-dev/work/I-00084/reports/I-00084_S03_Tests_report.md`

## Context

Two tests minimum:

1. **Reproduction test (AC1, AC2)** — fake repo with origin/main lagging
   local main by N commits; run worktree_setup; assert origin/main now
   matches local main.
2. **Idempotency test** — run worktree_setup twice; assert no error,
   origin/main still matches local main.
3. (Optional bonus, AC3) — invoke `make diff-coverage` in the fake
   repo's worktree and assert the file list contains only the in-scope
   changes. This may be impractical in a unit test context (the make
   target spins pytest); skip if the orchestration is too heavy.

### CRITICAL: Semantic Correctness Over Shape Checking

- BAD: `assert "origin" in remotes`
- GOOD: `assert get_origin_main_sha(worktree) == get_main_sha(repo)`

### Fixture pattern

`tmp_path` for the fake repo. Use `subprocess.run(["git", ...])` directly
to set up the simulated commits and refs. Then either invoke
`worktree_setup.sh` directly via subprocess, or import the Python wrapper
that calls it (whichever entry point exists in the codebase).

## TDD Requirement

This step is the test step. The reproduction test must FAIL against
pre-S01 code and PASS after S01.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/integration/test_worktree_setup_origin_main_sync.py -v
```

Do NOT run `make test-integration`.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00084",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["tests/integration/test_worktree_setup_origin_main_sync.py"],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "2 passed, 0 failed",
  "tdd_red_evidence": "n/a — S01 already applied; tests are the regression suite",
  "blockers": [],
  "notes": ""
}
```

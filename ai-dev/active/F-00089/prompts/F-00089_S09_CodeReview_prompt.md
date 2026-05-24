# F-00089_S09_CodeReview_prompt

**Work Item**: F-00089 -- Daemon chaos / fault-injection test layer
**Step Being Reviewed**: S01..S08 (all Backend implementation steps)
**Review Step**: S09

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures only. Read-only Docker introspection is allowed. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. No migrations were generated or applied by this Feature. Verify this in your review. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `uv run iw item-status F-00089 --json` — runtime step state.
- `ai-dev/work/F-00089/F-00089_Feature_Design.md` — Design document (read in full BEFORE running lint/format).
- All implementation reports: `ai-dev/work/F-00089/reports/F-00089_S0[1-8]_Backend_report.md`.
- All files listed in those reports' `files_changed`.

## Output Files

- `ai-dev/work/F-00089/reports/F-00089_S09_CodeReview_report.md` — Review report.

## Context

You are performing the **per-agent code review** of all eight Backend implementation steps (S01..S08) for F-00089. The implementation is all Backend — so one reviewer covers everything.

This is **test-only scope**. Any production-code change is a CRITICAL finding (Invariant 4). Any non-deterministic test (random, kill -9, wall-clock > 5s) is a CRITICAL finding (Invariant 3). Any test that asserts only "the hook fired" without also asserting against a daemon-mutated DB row / event row is a HIGH finding.

## Read the Design Document FIRST

Read the design document before opening any code:

- **Acceptance Criteria AC1..AC8** — every criterion is a mandatory check.
- **Boundary Behavior** — every row is a mandatory test case.
- **Invariants 1..10** — every invariant maps to a test or an enforcement.
- **TDD Approach** — every named test file must appear in some implementation step's `files_changed`. Missing entries = CRITICAL.

Write down every test file the design names and every Invariant before reading the code. Then check each against the implementation.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code:

```bash
make lint
make format
```

Any NEW violation in the changed files (not present on `main` before this Feature) → CRITICAL finding with `"category": "conventions"`, file + line + exact violation code/message.

If a tool is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Test-only scope (CRITICAL per-row)

- `git diff main -- 'orch/**' 'dashboard/**' 'executor/**' 'orch/db/migrations/**'` must be EMPTY. Any hit = CRITICAL (Invariant 1, 4).
- No file modified outside `scope.allowed_paths` (per `workflow-manifest.json`). The merge-time scope gate will also enforce this, but you catch it earlier.

### 2. Determinism (CRITICAL per-row)

For every file under `tests/integration/daemon_chaos/**`:

- Grep for `os.kill`, `subprocess.Popen.kill`, `kill -9`, `signal.SIGKILL` → any hit = CRITICAL (Invariant 3).
- Grep for `random.*`, `numpy.random.*` → any hit = CRITICAL.
- Grep for `time.sleep` and inspect every match. Any sleep > 5s = CRITICAL. Sleeps ≤ 5s are HIGH (suggest the harness's clock-shim instead).
- Grep for `datetime.now()`, `time.time()` outside of test-setup/teardown context → HIGH.

### 3. Harness API consistency (HIGH)

The hook names documented in S01's `harness.py` module docstring, S07's `skills/iw-workflow/SKILL.md` update, and S08's `skills/iw-ai-core-testing/SKILL.md` section MUST agree byte-for-byte. Inconsistency = HIGH.

Likewise, the smoke subset (S02 + S03) must be the same set in:
- `Makefile` `daemon-chaos-smoke` target (S07).
- `.github/workflows/daemon-chaos.yml` `daemon-chaos-smoke` job (S07).
- The strategy doc §5 gate matrix (S08).
- The testing-skill scenario-addition checklist (S08).

### 4. Assertion strength (HIGH per failing test)

For every test in `tests/integration/daemon_chaos/test_*.py`:

- Must contain at least one `assert` against a daemon-mutated DB row (e.g. `WorkItem.status`, `WorkItem.fix_cycle_count`, `WorkItem.failure_reason`, `DaemonEvent.*`) **or** a verified filesystem state (worktree dir, alembic_version row, git status of `main`).
- Tests that assert ONLY "the injection hook was called" = HIGH.
- `pytest.raises(Exception)` without `match=` = HIGH.
- `assert True`, `assert 1 == 1`, mock-only tests = CRITICAL.

### 5. TDD RED evidence (HIGH per missing/implausible)

For S01..S06 (behaviour-implementing Backend steps that add new tests):

- Each report's `tdd_red_evidence` must record a captured RED failure line. The snippet must show `AssertionError` (or `AttributeError`/`NotImplementedError` from a missing implementation), NOT `ImportError`/`SyntaxError`/collection error.
- For at least one test per step, reason about whether the test would actually fail against the daemon code path before the harness hook was armed. If you can argue the test would pass without the hook, that's a HIGH finding.
- S07 and S08 are wire-up / docs steps — `tdd_red_evidence: "n/a — ..."` is correct for those.

### 6. xfail discipline (CRITICAL per failing row)

Any `xfail` introduced by this Feature must:
- Use `strict=True` (Invariant 5).
- Reference a filed Incident ID in the reason (e.g. `reason="see I-NNNNN"`).
- Be classified as a daemon bug (not a test bug) — read the report's `notes` to confirm the agent diagnosed correctly.

`strict=False` xfails = CRITICAL.

### 7. Skill sync correctness (HIGH per mismatch)

For both skill updates (S07 + S08):

- `diff skills/iw-workflow/SKILL.md .claude/skills/iw-workflow/SKILL.md` → must be empty.
- `diff -r skills/iw-ai-core-testing/ .claude/skills/iw-ai-core-testing/` → must be empty.

Mismatch = HIGH (the executor's sync step was skipped or partial).

### 8. Conventions (CLAUDE.md)

- Strong-assertion rules from `skills/iw-ai-core-testing/SKILL.md`.
- Testcontainer Postgres only — no port 5433 connection.
- `postgresql+psycopg2://` → `postgresql+psycopg://` URL rewrite where applicable.
- `event_metadata` (not `metadata`) on `DaemonEvent`.

### 9. New gate is NOT on F-00089's manifest (CRITICAL)

Verify Invariant 10: `ai-dev/active/F-00089/workflow-manifest.json` must NOT contain a `qv-gate` step with `gate: "daemon-chaos-smoke"`. A gate cannot gate its own delivery. If it does, CRITICAL.

## Test Verification (NON-NEGOTIABLE)

Run the project's unit test command:

```bash
make test-unit
```

Plus the chaos package's targeted run (proves S01..S06 + S07 wire-up work together):

```bash
uv run pytest tests/integration/daemon_chaos/ -v
make daemon-chaos-smoke
```

Report results accurately. Do NOT run `make test-integration` here — it's S16's gate, with its own budget.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| **CRITICAL** | Production-code modified, non-determinism (kill/random/long-sleep), `xfail strict=False`, `daemon-chaos-smoke` on F-00089's own manifest, vacuous assertion | Must fix |
| **HIGH** | Assertion-strength regression, harness-API drift across docs, skill-sync mismatch, missing TDD RED evidence | Must fix |
| **MEDIUM (fixable)** | Convention violation, weak boundary-behavior coverage | Should fix |
| **MEDIUM (suggestion)** | Better pattern available | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S09",
  "agent": "CodeReview",
  "work_item": "F-00089",
  "step_reviewed": "S01..S08",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y chaos passed, daemon-chaos-smoke: PASS",
  "notes": ""
}
```

- `verdict`: `pass` iff zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
- `mandatory_fix_count`: count of CRITICAL + HIGH + MEDIUM_FIXABLE.

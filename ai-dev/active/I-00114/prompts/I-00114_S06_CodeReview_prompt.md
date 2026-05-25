# I-00114_S06_CodeReview_prompt

**Work Item**: I-00114 -- pi narration-exit escapes step-done contract, burns retry budget
**Step Being Reviewed**: S04 (Tests)
**Review Step**: S06

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures only (the suite uses one). Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. Verify no migrations were added. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `uv run iw item-status I-00114 --json` — runtime step state.
- `ai-dev/active/I-00114/I-00114_Issue_Design.md` — design document.
- `ai-dev/active/I-00114/reports/I-00114_S04_Tests_report.md` — Tests step report.
- All test files listed in S04's `files_changed`.
- `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md` — assertion-strength rules, the live-DB write guard, cross-project isolation, RED-flag checklist.

## Output Files

- `ai-dev/active/I-00114/reports/I-00114_S06_CodeReview_report.md`

## Context

You are reviewing the Tests step (S04). It added unit tests for the JSONL classifier and supporting helpers, and integration tests for the guard's end-to-end behaviour (5-reprompt loop, clean exit short-circuit, non-zero pass-through, opencode/claude untouched).

## Read the Design Document FIRST

Read the design's "Test to Reproduce", "Acceptance Criteria" (AC1..AC5), and "TDD Approach" sections. Each test the design names by purpose must exist; missing tests are CRITICAL.

## Item-Specific Test Review Anchors

### A. Semantic correctness (I-003 lesson)

**This is the highest-priority check.** Every assertion must verify a specific value, not just shape. Walk through every `assert` statement in both test files and classify it:

- `assert len(events) > 0` → BAD (shape only).
- `assert len(events) == 5` → GOOD (exact count).
- `assert "narration" in events[0].event_type` → BAD if it merely checks substring; the design requires `event_type == "step_narration_exit"`.
- `assert events[0].event_type == "step_narration_exit"` → GOOD.
- `assert events[-1].metadata["reprompt_attempt"] == 5` → GOOD.

Flag any shape-only assertion as a HIGH finding with the suggested specific value.

### B. AC coverage

Map each test in `S04`'s `files_changed` to the ACs it covers. Required coverage:

| AC | Required test(s) |
|----|-----------------|
| AC1 (narration classified, event emitted, reprompt happens) | `test_narration_exit_emits_event_and_reprompts` |
| AC2 (cap = 5, fallback after 5) | `test_narration_exit_emits_event_and_reprompts` + `test_guard_falls_back_after_5_reprompts` |
| AC3 (step-done short-circuits) | `test_clean_exit_with_step_done_does_not_reprompt` |
| AC4 (opencode/claude unchanged) | `test_opencode_launch_does_not_use_guard` |
| AC5 (reproduction test exists) | `test_narration_exit_emits_event_and_reprompts` (with RED evidence captured) |

Missing any AC's test → CRITICAL.

### C. Live-DB write guard

Per `tests/CLAUDE.md`: NEVER connect tests to the live DB on port 5433. Verify the integration tests use the testcontainer fixture (`chaos_db`-style or whatever the project standard is). Flag any code that imports from `orch.db.session` or constructs a session against port 5433 as CRITICAL.

### D. Determinism

- No `time.sleep > 0.1`, no real network, no random seeds without `Faker`/`hypothesis` proper seeding.
- The stub pi binary must not hang. Subprocess calls in the integration tests must have a bounded timeout.
- Reprompt-loop integration tests must finish in under 30s wall-clock each.

Flag any non-determinism as HIGH.

### E. RED evidence

S04's `tdd_red_evidence` field must show a real failure line — `AssertionError: expected 5 narration events, got 0`, or `ImportError: cannot import name 'classify_last_assistant'`. NOT a fixture error or collection error. If the evidence string says only "tests fail" with no specific line, flag as HIGH.

### F. Cross-project isolation

If the integration tests seed a `WorkItem`, they must use a unique `project_id` (e.g. `"test-proj"` or generated per-test) — not the real `iw-ai-core` project_id. Otherwise the test pollutes the daemon's view of the live project.

### G. Stub-pi pattern correctness

- The stub pi must be invokable as a real binary (executable bit set or invoked via `python <path>` from `PATH`).
- The stub pi's JSONL writes must use the exact pi session-dir convention (`/home/sergiog/.pi/agent/sessions/--<transformed-cwd>--/`). If the stub uses a tmp dir override (env var) instead, verify the guard supports the same override.
- The stub pi's "scenario" knob must be deterministic per test (no shared state between tests).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any new violations in S04's `files_changed` → CRITICAL with `"category": "conventions"`.

## Test Verification

Re-run S04's tests yourself:

```bash
uv run pytest tests/unit/test_pi_narration_guard.py tests/integration/test_pi_narration_guard.py -v
```

If anything fails: HIGH finding with the failure line, and verdict = NEEDS_FIX.

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "I-00114",
  "reviewed_steps": ["S04"],
  "verdict": "PASS|NEEDS_FIX|BLOCKED",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "category": "testing|conventions|correctness|determinism|isolation",
      "file": "tests/...",
      "line": 42,
      "description": "Specific issue and suggested fix.",
      "ac_violated": "AC2"
    }
  ],
  "notes": ""
}
```

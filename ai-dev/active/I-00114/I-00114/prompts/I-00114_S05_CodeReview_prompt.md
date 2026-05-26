# I-00114_S05_CodeReview_prompt

**Work Item**: I-00114 -- pi narration-exit escapes step-done contract, burns retry budget
**Step Being Reviewed**: S01 (Backend), S02 (Backend), S03 (Backend) — bundled backend review
**Review Step**: S05

---

## ⛔ Docker is off-limits

Standard policy. Read-only `docker ps/inspect/logs` allowed. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This Incident adds **no migrations**. Verify none were sneaked in. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `uv run iw item-status I-00114 --json` — runtime step state.
- `ai-dev/active/I-00114/I-00114_Issue_Design.md` — design document (read in full, especially Acceptance Criteria and Root Cause Analysis).
- `ai-dev/active/I-00114/reports/I-00114_S01_Backend_report.md`
- `ai-dev/active/I-00114/reports/I-00114_S02_Backend_report.md`
- `ai-dev/active/I-00114/reports/I-00114_S03_Backend_report.md`
- All files in those reports' `files_changed`.

## Output Files

- `ai-dev/active/I-00114/reports/I-00114_S05_CodeReview_report.md`

## Context

You are reviewing the three Backend implementation steps for I-00114. The work added a `iw daemon-event` CLI (S01), a `executor/pi_narration_guard.py` wrapper (S02), and wired the wrapper into the daemon's pi launch command builders (S03).

## Read the Design Document FIRST

Before opening code: read every Acceptance Criterion (AC1..AC5) in the design and write each one down. Each is a mandatory check below.

## Scope Discipline — Implicitly Allowed Paths

`ai-dev/active/I-00114/**`, `ai-dev/archive/I-00114/**`, and `ai-dev/work/I-00114/**` are daemon-implicit allows. Edits there are NOT scope-creep findings even though the manifest doesn't list them. (See the 2026-05-25 CR-00082 thrash for the cost case.)

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any new violations in files from the three reports' `files_changed` lists → CRITICAL findings with `"category": "conventions"`, file/line, and the exact violation message.

## Item-Specific Review Anchors

### A. AC1 — Narration detection is correct

- The guard distinguishes "narration" from "tool call" purely on the `[thinking?, text]` vs `toolCall` shape — verify by reading `classify_last_assistant` and the JSONL fixtures used by S04.
- The **DB signal** (`StepRun.status == in_progress` after pi exit) is the GATE for reprompts. The JSONL verdict is telemetry-only. Confirm the guard does NOT skip the reprompt purely because the JSONL parse failed.

### B. AC2 — Reprompt cap

- The cap is exactly 5 (matches `MAX_FIX_CYCLE`). Hardcoded? Configurable via flag? Either is acceptable but the default must be 5.
- After the 5th narration-exit, the guard exits with the original pi code (typically 0) so the daemon's existing `_handle_crashed` path fires exactly **once**. The guard must NOT call `iw step-fail` itself — that would change the failure classification.

### C. AC3 — Successful runs are untouched

- If pi exits cleanly AND `StepRun.status != in_progress`, the guard MUST exit immediately with the original code and emit ZERO narration events. Read the early-return path and confirm.

### D. AC4 — opencode and claude unchanged

- Read both `_build_initial_command` and `_build_fix_inner_command`. The opencode and claude branches must be byte-identical to pre-S03. Specifically grep the diffs for any change in those branches and flag any as CRITICAL.

### E. Builder pairing

- `_build_initial_command` (`orch/daemon/batch_manager.py`) and `_build_fix_inner_command` (`orch/daemon/fix_cycle.py`) must encode the same guard invocation shape. The "Keep in sync" comment at `batch_manager.py:2122-2123` exists precisely to flag drift. Diff the two callers side-by-side.

### F. CLI surface — `iw daemon-event`

- The command must:
  - Resolve `project_id` via `resolve_project(ctx)` (matches `step_commands.py`).
  - Accept `--metadata` as a JSON string and validate it parses.
  - Insert via the ORM (`DaemonEvent`), NOT raw SQL.
  - Use `event_metadata` for the Python attribute name (the SQLAlchemy reserved-word quirk — `orch/CLAUDE.md` "Gotcha").
- Flag any direct SQL, missing validation, or wrong attribute name as CRITICAL.

### G. Guard isolation rules

- The guard MUST NOT run docker, alembic, or any iw subcommand other than `daemon-event` and `item-status`. Read every `subprocess.run` / `subprocess.Popen` call.
- The guard MUST NOT write directly to the DB. The only DB writes happen through the `iw daemon-event` invocation.
- The guard's logs go to stderr only (matches `executor/CLAUDE.md`).

### H. TDD RED Evidence

- S01, S02, S03 each include behavioural changes — verify each report's `tdd_red_evidence` is plausible (AssertionError or ImportError from missing module, not SyntaxError or fixture error).

## Standard Review Checklist

Use the standard categories from `ai-dev/templates/CodeReview_Prompt_Template.md`: Architecture, Code Quality, Project Conventions, Security, Testing, TDD evidence, Documentation. Apply each to the three reports' `files_changed`.

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview",
  "work_item": "I-00114",
  "reviewed_steps": ["S01", "S02", "S03"],
  "verdict": "PASS|NEEDS_FIX|BLOCKED",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "category": "architecture|conventions|security|testing|tdd|correctness",
      "file": "path/to/file.py",
      "line": 42,
      "description": "Specific issue and suggested fix.",
      "ac_violated": "AC4"
    }
  ],
  "notes": ""
}
```

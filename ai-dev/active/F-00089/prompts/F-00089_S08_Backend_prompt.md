# F-00089_S08_Backend_prompt

**Work Item**: F-00089 -- Daemon chaos / fault-injection test layer
**Step**: S08
**Agent**: Backend

---

## ⛔ Docker is off-limits

Standard policy. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. No migrations involved. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `uv run iw item-status F-00089 --json` — runtime step state.
- `ai-dev/work/F-00089/F-00089_Feature_Design.md` — Design document (AC8 second half).
- All S01..S07 reports + their changed files (so you have a complete picture of what shipped).
- `ai-dev/work/TESTS_ENHANCEMENT.md` — tracker (you update §8 row 4.3 and the v1.4 header / changelog).
- `docs/IW_AI_Core_Testing_Strategy.md` — strategy doc (§2 layer list, §5 CI gate matrix; you add Layer 9 + two gate rows).
- `docs/IW_AI_Core_Daemon_Design.md` — daemon design + state transitions (you cross-link the new test layer).
- `skills/iw-ai-core-testing/SKILL.md` — testing-skill master (you add a new section).
- `.claude/skills/iw-ai-core-testing/**` — mirror that `iw sync-skills --force iw-ai-core-testing` writes.

## Output Files

- `ai-dev/work/F-00089/reports/F-00089_S08_Backend_report.md` — Step report.

## Context

You are implementing **S08: docs + tracker + testing-skill update** — the final test-layer-documenting step. After this step, the new chaos layer is fully discoverable: it appears in the testing strategy doc, the tracker is updated to DONE, the daemon-design doc cross-links the new layer, and the testing skill has a section documenting the harness API for future scenario additions.

**Test-only scope.** No production code changes.

## Requirements

### 1. Tracker update

Edit `ai-dev/work/TESTS_ENHANCEMENT.md`:

- §8 (Phase 4) row 4.3 — change Status from `TODO` to `DONE`. Add a short note column entry referencing F-00089 and the commit-or-PR.
- Header status block — bump to **v1.4** (current is v1.3 per the §11 changelog). Update the date to today (2026-05-24 or the actual execution date). Add one sentence describing F-00089's delivery to the running narrative.
- §11 Changelog — prepend a new entry dated today describing the F-00089 merge: which test layer was added (Layer 9 — daemon chaos), which scenarios shipped (S02..S06: worktree-setup-mid-failure, fix-cycle-cap-exhaustion, agent-stall-recovery, squash-merge-conflict, migration-rebase-failure), which gate was added to the canonical chain (`daemon-chaos-smoke`), and the smoke-vs-full split rationale (S02 + S03 smoke per PR; full matrix nightly).
- §10 Open Questions — update or remove the "daemon chaos" entry if one exists; or add a note saying 4.3 is now closed.

### 2. Testing strategy doc

Edit `docs/IW_AI_Core_Testing_Strategy.md`:

- §2 (Test layers) — add a new layer entry **Layer 9 — Daemon chaos** (or whatever the next number is — F-00088 took Layer 8 / E2E per the v1.3 narrative; verify by reading §2 first). The entry should describe: location (`tests/integration/daemon_chaos/`), purpose (deterministic fault-injection for the 5 documented daemon failure modes), scope (test-only, no production code), how to run (`make daemon-chaos-smoke` / `make daemon-chaos-full`), and a back-reference to F-00089.
- §5 (CI gate matrix) — add **two** new rows:
  - `daemon-chaos-smoke` — blocking on PR + push to main; command `make daemon-chaos-smoke`; F-00089.
  - `daemon-chaos-full` — non-blocking nightly + workflow_dispatch; command `make daemon-chaos-full`; F-00089.

### 3. Daemon design doc cross-link

Edit `docs/IW_AI_Core_Daemon_Design.md`:

- Find the state-transition section (the one documenting setup → running → review → merge → done, including the failure-mode terminal states). Add a short paragraph at the end of that section (or as a new "Recovery testing" subsection) cross-linking to `docs/IW_AI_Core_Testing_Strategy.md` Layer 9 and to F-00089's test files. Keep it to a paragraph — this is a back-link, not a duplication of the test-layer content.

### 4. Testing skill — new harness section

Edit `skills/iw-ai-core-testing/SKILL.md`:

- Add a new section titled "Daemon chaos / fault-injection harness" (or similar, matching the doc's heading conventions). Content:
  - One-paragraph overview of what the harness is (deterministic fault-injection for the daemon poll loop) and what it is not (chaos-monkey, random failure, kill -9).
  - The full hook list, taken verbatim from S01's harness module docstring (don't invent hook names — use S01's actual names): `inject_worktree_setup_failure_after_clone(stage=...)`, `inject_fix_cycle_always_fails()`, `inject_agent_stall_after_seconds(seconds)`, `inject_squash_merge_conflict_on_main()`, `inject_migration_rebase_conflict_revision()`.
  - A "scenario-addition checklist" — 5–8 bullet points covering: read the harness module docstring; add a new hook to `harness.py` only if no existing hook fits; the hook must be deterministic (no `kill -9`, no `random.*`, no wall-clock); the hook must be idempotent; the scenario test must assert against a daemon-mutated DB row / event row (not just "the hook fired"); if a real daemon bug is surfaced, `xfail strict=True` + file an Incident — do not "fix" the daemon in the test CR; the determinism meta-test must keep passing; if the smoke subset (S02 + S03) needs to change, update `Makefile` + `.github/workflows/daemon-chaos.yml` together.
  - A pointer to the harness module docstring as the source of truth.

After editing the master copy, run:

```bash
uv run iw sync-skills --force iw-ai-core-testing
```

This writes the mirror at `.claude/skills/iw-ai-core-testing/**`. **Both files** must appear in your `files_changed`. Verify byte-for-byte agreement.

### 5. Follow project conventions

Read `CLAUDE.md`. Match the editorial style of the existing doc / tracker / skill — terse, factual, evidence-anchored (link to F-00089 / commit / PR).

## TDD Requirement

This step is **docs + tracker + skill text**, not behavioural code. Use `"n/a — docs / tracker / skill text only, no production behavioural logic"` in `tdd_red_evidence`.

You SHOULD validate that the testing-strategy doc still parses (no broken Markdown — check by rendering or by `grep` for common errors like unmatched code fences, bad table syntax).

## Pre-flight Quality Gates (NON-NEGOTIABLE)

`make format`, `make typecheck`, `make lint` — all must pass. Lint will run `scripts/check_templates.py` over any Jinja2 templates (none expected in this step) and `lint-templates` over docs (check what it does — if it flags anything in your changed docs, fix it).

## Test Verification (NON-NEGOTIABLE)

No new tests to run in this step (docs / tracker / skill only). Use:

```bash
uv run pytest tests/integration/daemon_chaos/ -v --collect-only
```

to confirm the chaos test package is still discoverable from the integration suite root — this catches accidental `__init__.py` corruption from S01.

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "Backend",
  "work_item": "F-00089",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/TESTS_ENHANCEMENT.md",
    "docs/IW_AI_Core_Testing_Strategy.md",
    "docs/IW_AI_Core_Daemon_Design.md",
    "skills/iw-ai-core-testing/SKILL.md",
    ".claude/skills/iw-ai-core-testing/SKILL.md"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "no new tests; chaos package collects clean",
  "tdd_red_evidence": "n/a — docs / tracker / skill text only, no production behavioural logic",
  "blockers": [],
  "notes": "Confirm sync-skills mirror is byte-for-byte equal to the master. Confirm tracker v1.4 header reflects the F-00089 delivery date."
}
```

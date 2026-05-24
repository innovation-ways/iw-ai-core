# CR-00084_S02_Backend_prompt

**Work Item**: CR-00084 -- LLM-as-judge test review (spike) — a stronger model scores newly-written tests against an assertion-strength rubric; advisory-only signal in the CodeReview step
**Step**: S02
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

(Standard policy. See S01 prompt for full text. This step does not touch Docker.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This step adds no migrations.)

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00084 --json`
- `ai-dev/work/CR-00084/CR-00084_CR_Design.md` — Design document
- `ai-dev/work/CR-00084/reports/CR-00084_S01_Backend_report.md` — **Critical**: read `calibration_verdict` field. `MET` → ship hook live. `NOT_MET` or `DEFERRED` → ship hook dormant.
- `ai-dev/active/CR-00084/evidences/pre/cr-00084-judge-calibration.txt` — referenced from the dormant-form note when applicable.
- `agents/claude/code-review-impl.md` — Master spec to edit
- `agents/opencode/code-review-impl.md` — Master spec to edit (mirror of the above)
- `.claude/agents/code-review-impl.md` — Mirror copy synced from `agents/claude/code-review-impl.md`
- `.opencode/agents/code-review-impl.md` — Mirror copy synced from `agents/opencode/code-review-impl.md`

## Output Files

- `ai-dev/work/CR-00084/reports/CR-00084_S02_Backend_report.md` — Step report
- Modified: `agents/claude/code-review-impl.md`
- Modified: `agents/opencode/code-review-impl.md`
- Modified: `.claude/agents/code-review-impl.md` (kept byte-identical to master after `iw sync-agents` if such a command exists, otherwise via a direct copy)
- Modified: `.opencode/agents/code-review-impl.md` (same convention)

## Context

You are implementing **Step S02** of CR-00084: the conditional advisory hook in the CodeReview agent spec. The hook's form depends entirely on S01's `calibration_verdict`:

- `MET` → ship the hook **live** (instructions tell the agent to optionally invoke the judge on new test files and log scores as advisory lines).
- `NOT_MET` or `DEFERRED` → ship the hook **dormant** (instructions tell the agent the judge exists but NOT to invoke it pending re-calibration, with a forward link to the evidence file).

The verdict is the single load-bearing input to this step. Read S01's report first.

## Requirements

### 1. Read S01's verdict

```bash
cat ai-dev/work/CR-00084/reports/CR-00084_S01_Backend_report.md | grep '"calibration_verdict"'
```

Record the verdict (MET / NOT_MET / DEFERRED) in your report's `notes`.

### 2. Edit `agents/claude/code-review-impl.md` and `agents/opencode/code-review-impl.md`

Add a new section **after the existing `### 5. Produce Findings` section and before `## Severity Levels`** (or the closest equivalent if the file shape differs slightly). The section title is:

```
### 6. (Advisory) LLM-as-judge test-quality signal
```

#### If `calibration_verdict == "MET"` — write the LIVE form:

The section body must:

- State that for each newly added test file in `files_changed`, the agent SHOULD optionally invoke `scripts/llm_judge_test_review.py --test-file <path> --test-name <function>` for the most behaviour-heavy 1–3 test functions in that file (the agent picks; the judge is expensive and we are not blanket-running it).
- State that the judge's stdout JSON record must be appended verbatim to the review report under a clearly marked `## Advisory: LLM-judge scores` subsection — one bullet per scored test with the test id, the overall score, and the rationale.
- State explicitly: **the judge score MUST NOT raise `verdict` to `fail` and MUST NOT increment `mandatory_fix_count`**. It is informational. A low score may be quoted in a `MEDIUM_SUGGESTION` finding if the reviewer agrees with the rationale — but the agent's own judgement, not the judge's score, is what creates findings.
- State that `ANTHROPIC_API_KEY` is required in the environment; if missing the agent skips the judge entirely and writes one line `Advisory: LLM judge skipped — ANTHROPIC_API_KEY not set` to the report (no failure).
- State that the judge invocation has no retries — if it errors or returns unparseable JSON, the agent logs `Advisory: LLM judge failed for <test_id>: <one-line reason>` and moves on.
- State that cumulative token spend for the advisory invocations in one review must stay under **$0.50** — if approaching that, stop invoking the judge and note the cap was hit.
- Include a forward link to `ai-dev/active/CR-00084/evidences/pre/cr-00084-judge-calibration.txt` (or its post-merge home under `ai-dev/archive/CR-00084/`) for the calibration record.

#### If `calibration_verdict == "NOT_MET"` or `"DEFERRED"` — write the DORMANT form:

The section body must:

- State that the judge utility (`scripts/llm_judge_test_review.py`) exists from CR-00084's spike but the calibration bar (WEAK-recall ≥ 70% AND STRONG-FP ≤ 30%) was NOT met (or was DEFERRED for missing API key), per the linked evidence file.
- State explicitly: **DO NOT invoke the judge in this review.** Future re-calibration is required before the hook is enabled.
- Include the forward link to `ai-dev/active/CR-00084/evidences/pre/cr-00084-judge-calibration.txt` (or its archive home).
- Add a one-line note: "To re-enable, file a small follow-up CR that re-runs `make llm-judge-calibrate` and flips this section to the LIVE form."

### 3. Sync mirrors

The `.claude/agents/code-review-impl.md` and `.opencode/agents/code-review-impl.md` mirrors must end byte-identical to their masters. Check if the project has a sync command:

```bash
uv run iw --help | grep -i sync
ls scripts/ | grep -i sync
```

If `iw sync-agents` or equivalent exists, use it. Otherwise, copy the files directly:

```bash
cp agents/claude/code-review-impl.md .claude/agents/code-review-impl.md
cp agents/opencode/code-review-impl.md .opencode/agents/code-review-impl.md
```

Verify byte-identical with `diff -q agents/claude/code-review-impl.md .claude/agents/code-review-impl.md` (no output → identical).

### 4. Do NOT touch any other agent spec

- Do NOT edit `agents/pi/code-review-impl.md` (the PI variant is out of scope; touching it would expand the CR's blast radius).
- Do NOT edit any other agent under `agents/{claude,opencode,pi}/`.
- Do NOT edit the testing skill or strategy doc — those are S03's job.

## Project Conventions

Read the project's `CLAUDE.md` for conventions. The agent-spec files follow YAML frontmatter + Markdown body; the new section uses the same Markdown level (`### 6.`) as the existing numbered sections (`### 1.`, `### 2.`, …).

## TDD Requirement

This step modifies documentation/agent-instructions, not behavioural Python code. **No new behavioural tests are required.** Set `tdd_red_evidence` in your report to `"n/a — agent-spec markdown edits only, no production logic"`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`:

1. **`make format`** — for the markdown files, this is a no-op but run it anyway.
2. **`make typecheck`** — no Python touched, expect `ok` (skipped:no-code-changes is also acceptable).
3. **`make lint`** — expect zero new violations (the agent-spec files are plain markdown; ruff/mypy do not lint them, but `make lint` also invokes `scripts/check_templates.py` for Jinja2 — irrelevant here, but the gate must still pass on the unchanged codebase).

If a tool isn't available, STOP and raise a blocker.

## Test Verification

No new tests. Verify the mirror sync with `diff -q` (see Requirement 3).

## Allowed File Modifications

You MAY ONLY modify:

- `agents/claude/code-review-impl.md`
- `agents/opencode/code-review-impl.md`
- `.claude/agents/code-review-impl.md`
- `.opencode/agents/code-review-impl.md`

If you discover a need to touch any other file, STOP and raise a blocker.

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "backend-impl",
  "work_item": "CR-00084",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "agents/claude/code-review-impl.md",
    "agents/opencode/code-review-impl.md",
    ".claude/agents/code-review-impl.md",
    ".opencode/agents/code-review-impl.md"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:no-code-changes",
    "typecheck": "ok|skipped:no-code-changes",
    "lint": "ok|skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "skipped: no behavioural code changes",
  "tdd_red_evidence": "n/a — agent-spec markdown edits only, no production logic",
  "hook_form": "LIVE|DORMANT",
  "calibration_verdict_read_from_s01": "MET|NOT_MET|DEFERRED",
  "mirror_sync_verified": true,
  "blockers": [],
  "notes": "Hook form: LIVE/DORMANT (because S01 reported calibration_verdict: <verdict>). Mirrors verified byte-identical via `diff -q`."
}
```

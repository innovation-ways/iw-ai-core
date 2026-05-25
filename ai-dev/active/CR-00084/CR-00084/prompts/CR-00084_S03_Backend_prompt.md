# CR-00084_S03_Backend_prompt

**Work Item**: CR-00084 -- LLM-as-judge test review (spike) — a stronger model scores newly-written tests against an assertion-strength rubric; advisory-only signal in the CodeReview step
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

(Standard policy. See S01 prompt for full text. This step does not touch Docker.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This step adds no migrations.)

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00084 --json`
- `ai-dev/work/CR-00084/CR-00084_CR_Design.md` — Design document
- `ai-dev/work/CR-00084/reports/CR-00084_S01_Backend_report.md` — **Critical**: read `calibration_verdict`, `calibration_cost_usd`, `labelled_set_size`
- `ai-dev/work/CR-00084/reports/CR-00084_S02_Backend_report.md` — confirms `hook_form` (LIVE/DORMANT)
- `ai-dev/active/CR-00084/evidences/pre/cr-00084-judge-calibration.txt` — the calibration record
- `docs/IW_AI_Core_Testing_Strategy.md` — locate §10 (open questions / decisions) and the changelog at the bottom; the new subsection goes after §10 as a new §, or at the end of §10 — pick whichever fits the doc's existing structure best
- `skills/iw-ai-core-testing/SKILL.md` — master copy of the testing skill
- `.claude/skills/iw-ai-core-testing/SKILL.md` — mirror (synced via `iw sync-skills`)
- `ai-dev/work/TESTS_ENHANCEMENT.md` — the tracker; §8 row 4.4 and §11 changelog

## Output Files

- `ai-dev/work/CR-00084/reports/CR-00084_S03_Backend_report.md` — Step report
- Modified: `docs/IW_AI_Core_Testing_Strategy.md`
- Modified: `skills/iw-ai-core-testing/SKILL.md`
- Modified: `.claude/skills/iw-ai-core-testing/SKILL.md` (synced from master via `iw sync-skills`)
- Modified: `ai-dev/work/TESTS_ENHANCEMENT.md`

## Context

You are implementing **Step S03** of CR-00084: documentation + skill + tracker sync. This is the last impl step; S04/S05 are reviews, S06–S13 are QV gates, S14 is self-assess. Your edits propagate the spike's outcome (calibration verdict, hook form, evidence path) to every place an operator might look for the LLM-as-judge story.

## Requirements

### 1. `docs/IW_AI_Core_Testing_Strategy.md` — add the LLM-as-judge subsection

Add a new section (suggested title: `## 10.X. LLM-as-judge advisory signal (CR-00084 spike)` — pick the next available subsection number under §10, or add it as a new top-level section directly after §10 if §10 has no numbered subsections). The section body must cover:

- **What it is** — a stronger model (Claude Opus 4.7) scores newly-written tests on three axes (assertion specificity, behaviour-vs-mock, edge coverage). Complementary to (not a replacement for) the structural assertion scanner (CR-00046).
- **The rubric** — name the three axes, the 1–5 scale, the bucketing rule (`overall >= 4` → STRONG, `3` → MEDIUM, `<= 2` → WEAK).
- **The calibration outcome** — quote the verdict (MET / NOT_MET / DEFERRED), the WEAK-recall and STRONG-FP percentages from the evidence file, the labelled-set size, and the total token spend. Link to the evidence file by relative path.
- **The current disposition** — "advisory hook LIVE in `agents/{claude,opencode}/code-review-impl.md` §6" or "advisory hook DORMANT pending re-calibration". Quote the calibration bar (`WEAK-recall ≥ 70% AND STRONG-FP ≤ 30%`).
- **Cost discipline** — note the < $2.00 calibration budget, the < $0.50 per-review cap, and the no-retry / no-auto-loop rule.
- **What's out of scope** — promoting the judge to a blocking gate.

Update the strategy doc's own changelog entry (the dated `## Changelog` or equivalent at the bottom — same convention as CR-00081 used) with a one-line entry dated 2026-05-24 recording the spike's outcome.

### 2. `skills/iw-ai-core-testing/SKILL.md` — add the advisory-signal subsection

Add a new subsection (title: `## Advisory: LLM-as-judge signal (CR-00084)`) that mirrors the strategy doc but is keyed to the skill's audience (an agent writing or reviewing tests). The body must:

- Tell the reader the judge utility exists and where (`scripts/llm_judge_test_review.py`).
- Tell the reader the hook in CodeReview is LIVE or DORMANT (per S01/S02).
- If LIVE: instruct test-writers that their tests may be sampled by the judge and that an advisory low-score line may appear in the review report — this is informational and never blocks merge.
- If DORMANT: instruct readers the judge exists but is currently disabled; pointer to the calibration evidence file.
- One sentence on the rubric (three axes, 1–5 scale).

### 3. Sync `.claude/skills/iw-ai-core-testing/SKILL.md`

Run:

```bash
uv run iw sync-skills --force iw-ai-core-testing
```

Verify byte-identity:

```bash
diff -q skills/iw-ai-core-testing/SKILL.md .claude/skills/iw-ai-core-testing/SKILL.md
```

(no output → identical). If the project has any other mirror locations for skills (check `iw sync-skills --help` or grep for `iw-ai-core-testing` under the repo root) sync them all.

### 4. `ai-dev/work/TESTS_ENHANCEMENT.md` — update §8 row 4.4 and add §11 changelog entry

Locate the row in §8 (line ~152 currently) whose `Item` cell is `4.4` and `Subject` is `LLM-as-judge test review (experimental)`. Update the **Status** column from `TODO` to one of:

- `DONE (CR-00084, 2026-05-24)` — if S01's `calibration_verdict == "MET"`
- `DEFERRED (CR-00084, 2026-05-24)` — if S01's `calibration_verdict == "NOT_MET"` or `"DEFERRED"` (cite the calibration shortfall in the Notes column with a link to the evidence file)

Update the `Reference` column with `CR-00084`.

Add a new §11 changelog entry dated **2026-05-24** that summarises:

- The spike's two artefacts: the labelled set (with size and STRONG/WEAK split) and the judge script.
- The calibration verdict (MET / NOT_MET / DEFERRED) and the WEAK-recall + STRONG-FP percentages.
- The total token spend in USD and whether it stayed under the $2.00 budget.
- The hook form (LIVE / DORMANT) and which file carries it.
- A forward link from CR-00046's existing entry (note CR-00046 is the structural scanner; this entry can reference it inline as "complementary to CR-00046's structural scanner").

Match the prose style and density of the existing 2026-05-24 entry (the one that reconciled Phase 3 status).

### 5. Header status block

Update the v1.3 header status block (around line 8) with one sentence noting that item 4.4 was attempted as **CR-00084** with verdict MET/NOT_MET. Do NOT rewrite the whole header — append one sentence to the "Open follow-ups within Phases 0–3" or "Next pickup: Phase 4" paragraph as is most natural.

### 6. Do NOT touch any other doc, skill, or tracker section

- Do NOT edit `tests/CLAUDE.md` (the testing skill is the source of truth for the rubric; tests/CLAUDE.md is operational rules for writing tests).
- Do NOT edit `skills/iw-workflow/SKILL.md` (workflow rules are unchanged).
- Do NOT edit any other doc under `docs/`.
- Do NOT touch §1–§7, §9, or §10 of `TESTS_ENHANCEMENT.md` beyond the §8 row 4.4 and the header line described above.

## Project Conventions

Read the project's `CLAUDE.md` for conventions. The strategy doc, skill, and tracker each have a distinct prose voice — match the existing voice of the surrounding paragraphs.

## TDD Requirement

This step modifies documentation/markdown, not behavioural code. **No new behavioural tests required.** Set `tdd_red_evidence` to `"n/a — docs/skill/tracker markdown edits only, no production logic"`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. **`make format`** — markdown is a no-op but run it.
2. **`make typecheck`** — expect `ok` (or `skipped:no-code-changes`).
3. **`make lint`** — expect zero new violations. `scripts/check_templates.py` runs here too (irrelevant for these doc edits but must still pass on the unchanged Jinja templates).

If a tool isn't available, STOP and raise a blocker.

## Test Verification

No new tests. Verify the mirror sync with `diff -q`.

## Allowed File Modifications

You MAY ONLY modify:

- `docs/IW_AI_Core_Testing_Strategy.md`
- `skills/iw-ai-core-testing/**`
- `.claude/skills/iw-ai-core-testing/**`
- `ai-dev/work/TESTS_ENHANCEMENT.md`

If you need to touch any other file, STOP and raise a blocker.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "CR-00084",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "docs/IW_AI_Core_Testing_Strategy.md",
    "skills/iw-ai-core-testing/SKILL.md",
    ".claude/skills/iw-ai-core-testing/SKILL.md",
    "ai-dev/work/TESTS_ENHANCEMENT.md"
  ],
  "preflight": {
    "format": "ok|skipped:no-code-changes",
    "typecheck": "ok|skipped:no-code-changes",
    "lint": "ok|skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "skipped: no behavioural code changes",
  "tdd_red_evidence": "n/a — docs/skill/tracker markdown edits only, no production logic",
  "calibration_verdict_propagated": "MET|NOT_MET|DEFERRED",
  "tracker_row_4_4_status": "DONE|DEFERRED",
  "skill_mirror_synced": true,
  "blockers": [],
  "notes": "All four doc surfaces updated and consistent. Tracker row 4.4 → DONE/DEFERRED with reference CR-00084 and date 2026-05-24. §11 changelog entry added. .claude/skills/ mirror byte-identical to master."
}
```

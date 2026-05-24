# CR-00080_S03_Backend_prompt

**Work Item**: CR-00080 -- Widen mutmut mutation-testing scope from `orch/daemon/` to all of `orch/`, run a second spike, and flip the mutation gate from informational to blocking
**Step**: S03
**Agent**: Backend

---

## ⛔ Docker is off-limits

Standard policy. Docs / skill / tracker updates do not require any container changes.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step does not touch migrations.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00080 --json`.
- `ai-dev/active/CR-00080/CR-00080_CR_Design.md` -- Design document (AC4 lists every doc surface that must be updated)
- `ai-dev/active/CR-00080/evidences/pre/cr-00080-spike-measurements.txt` -- S01 output (the wall-clock + score that must be cited)
- `ai-dev/work/CR-00080/reports/CR-00080_S01_Backend_report.md` -- S01 report
- `ai-dev/work/CR-00080/reports/CR-00080_S02_Backend_report.md` -- S02 report (threshold T, or `blocked` if viability guard failed)
- `docs/IW_AI_Core_Testing_Strategy.md` -- §5 gate table, §8 mutation section, §9 gap row
- `ai-dev/work/TESTS_ENHANCEMENT.md` -- §5 follow-up row, §6 item 2.1, §8 item 4.8, §9 gate matrix, §10 mutation-cost question
- `skills/iw-ai-core-testing/SKILL.md` -- mutmut section (master copy)
- `.claude/skills/iw-ai-core-testing/SKILL.md` -- synced project copy

**Do NOT touch `skills/iw-workflow/SKILL.md` or its project copy.** The canonical QV chain is unchanged by this CR — mutmut lives on the nightly surface only.

## Output Files

- `docs/IW_AI_Core_Testing_Strategy.md` -- §5 / §8 / §9 updated
- `ai-dev/work/TESTS_ENHANCEMENT.md` -- §5 / §6 / §8 / §9 / §10 updated, §11 changelog entry added
- `skills/iw-ai-core-testing/SKILL.md` -- mutmut section updated
- `.claude/skills/iw-ai-core-testing/SKILL.md` -- regenerated via `iw sync-skills --force iw-ai-core-testing`
- `ai-dev/work/CR-00080/reports/CR-00080_S03_Backend_report.md` -- Step report

## Context

You are implementing the final implementation step. S01 ran the spike. S02 either wired the nightly GH workflow (viability passed) or reported `blocked` (viability failed). Your job is to bring every document, tracker, and skill into agreement so a future reader knows: (a) what state the gate is in, (b) what threshold and ratchet rule apply (or why the gate is deferred), and (c) which open tracker items are now DONE (or still IN PROGRESS).

Read AC4 in the design doc — it enumerates every surface.

**Branch on S02 outcome.** Open `ai-dev/work/CR-00080/reports/CR-00080_S02_Backend_report.md` and check `completion_status`:

- `complete` → S02 wired the gate. Mark tracker / strategy doc / skill as DONE. Follow the "viable" path below.
- `blocked` → S02 deferred the gate (viability guard fired). Mark tracker / strategy doc / skill as DEFERRED with the explanation. Follow the "blocked" path below.

## Requirements

### 1. Update the testing strategy doc

Edit `docs/IW_AI_Core_Testing_Strategy.md`:

- **§5 gate table** (viable path): update the mutmut row from "on-demand, not gated" to "blocking nightly GH workflow, threshold T=<N>%". Cite CR-00080.
- **§5 gate table** (blocked path): update the mutmut row to "DEFERRED by CR-00080 viability guard — spike data too thin (M=<value>%, K=<value>); next step: <verbatim from S02 report>". Cite CR-00080.
- **§8 mutation-testing section**: replace the "CR-00059 spike measured 0 mutants because cov-fail-under killed the runner" paragraph with the second-spike narrative — what was fixed (cov-fail-under override), the widened scope (`orch/`), the second-spike numbers (W wall-clock, M measured score, K exercised mutants), the design's nightly-only surface choice (with the rationale that per-batch cost is impractical), the viability guard (M>=20% AND K>=30), the chosen threshold T (or "DEFERRED — viability guard fired" on the blocked path), and the ratchet rule (raise T as test coverage improves, mirroring CR-00047 diff-coverage).
- **§9 gap row** (viable path): mark the "mutation testing not blocking" gap as CLOSED by CR-00080 (or remove the row entirely if the §9 format prefers active gaps only — match the existing convention; check how CR-00047 / CR-00050 closures are recorded).
- **§9 gap row** (blocked path): leave the gap row open and append "(CR-00080 viability guard fired — see §8 for next step)".

### 2. Update the tracker

Edit `ai-dev/work/TESTS_ENHANCEMENT.md`:

**Viable path** (S02 `complete`):
- **§5 grouping table row `P2-CR-A-followup-mutation-block`**: status → DONE (CR-00080), tag "nightly GH workflow, T=<N>%".
- **§6 item 2.1 "Adopt mutation testing in CI"**: status → DONE (CR-00080).
- **§8 Phase-4 item 4.8 "Tighten mutation gate to blocking"**: status → DONE (CR-00080).
- **§9 gate matrix**: update the mutmut row to show the new state (blocking nightly GH workflow, threshold T=<N>%).
- **§10 open questions, "Mutation testing cost"**: answer the question. Quote the W wall-clock, the per-mutant cost (`W / mutants_generated`), and the nightly surface decision (per-batch impractical at this cost; future diff-scoped optimisation could revisit).
- **§11 changelog**: add a dated entry (today's date, 2026-05-24) summarising the CR — bug fix (cov-fail-under), scope widening, second spike numbers, nightly surface, threshold T, viability guard, ratchet rule.

**Blocked path** (S02 `blocked`):
- **§5 grouping table row `P2-CR-A-followup-mutation-block`**: status stays IN PROGRESS, append "(CR-00080 deferred wiring — viability guard fired; M=<value>%, K=<value>; next step: <S02's recommended next step>)".
- **§6 item 2.1**: stays IN PROGRESS, same annotation.
- **§8 item 4.8**: stays OPEN, same annotation.
- **§9 gate matrix**: mutmut row stays "on-demand, not gated", note that CR-00080 attempted blocking but viability guard fired.
- **§10 mutation-testing cost**: STILL ANSWER the question with the W / per-mutant cost data S01 produced (even partial data is useful), but conclude with "wiring deferred until viability guard passes — see §11 changelog 2026-05-24".
- **§11 changelog**: dated entry summarising CR-00080's attempt — what worked (cov-fail-under fix, scope widening), what blocked (viability guard fired with the measured M / K), recommended next step.

Keep the tracker's tone and format consistent with the existing rows (check the §5 row for CR-00049 / CR-00059 for the precedent format).

### 3. Update the testing skill

Edit `skills/iw-ai-core-testing/SKILL.md` mutmut section:

**Viable path:**
- Change "scope: orch/daemon/ only" → "scope: orch/ (whole backend)".
- Change "on-demand via `make mutation-check`" → "blocking nightly GH workflow at .github/workflows/mutation.yml; manual via `make mutation-check MODULE=...` for ad-hoc investigation".
- Add: "Threshold T=<N>% (CR-00080, AC3 viability-guard rule); raise over time as coverage improves."
- Preserve any pre-existing "Earlier behaviour (CR-00059): daemon-only, informational" note as a historical breadcrumb (mirror the CR-00049 pattern of preserving an "Earlier fallback" note for context).

**Blocked path:**
- Change "scope: orch/daemon/ only" → "scope: orch/ (whole backend) — config widened, gate wiring deferred".
- Keep "on-demand via `make mutation-check`" with an added sentence: "CR-00080 attempted nightly blocking gate; viability guard fired (M=<value>%, K=<value>); wiring deferred until <recommended next step>."
- Preserve the historical CR-00059 breadcrumb.

### 4. Sync the skill to the project copy

```bash
uv run iw sync-skills --force iw-ai-core-testing
```

Verify byte-equality:

```bash
diff skills/iw-ai-core-testing/SKILL.md .claude/skills/iw-ai-core-testing/SKILL.md
```

Must produce zero output.

You MUST NOT run `iw sync-skills --force iw-workflow` — that skill is not touched by this CR (mutmut lives on the nightly surface only, not in the canonical QV chain). Verify by reading S02's `files_changed` (should not contain `skills/iw-workflow/SKILL.md`).

### 5. Verify consistency

After all edits, the following invariant must hold:

**Viable path:**
- "nightly GH workflow" phrasing appears identically in: the design doc, the strategy doc §5 + §8, the tracker §5 row + §9 gate matrix + §11 changelog, and the skill mutmut section.
- The threshold value `T` is the same integer in: the strategy doc §5 + §8, the tracker §9 gate matrix + §11 changelog, the skill, and (from S02) the `.github/workflows/mutation.yml` file.

**Blocked path:**
- The deferred-state phrasing (including the measured M and K values, and the recommended next step) appears identically in: the strategy doc §8, the tracker §5/§6/§8/§10/§11, and the skill.

Cross-check by grepping for the surface name (viable) or the M/K values (blocked) across all touched files.

## Project Conventions

Read `CLAUDE.md`. Match the existing tracker / strategy-doc / skill formatting precisely — these documents have stable conventions and reviewers will flag drift.

## TDD Requirement

No new behavioural code. Use `tdd_red_evidence: "n/a — documentation + tracker + skill updates only"`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. **`make format`** — N/A for markdown-only edits; run anyway.
2. **`make typecheck`** — N/A; run anyway.
3. **`make lint`** — must report zero errors. (Includes the `scripts/check_templates.py` Jinja2 check and any markdown lint.)

## Test Verification (NON-NEGOTIABLE)

- Targeted test verification is the byte-equality `diff` between master skill and project copy (above). That is the testable invariant of skill sync.
- Do NOT run `make test-unit` or `make test-integration`.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "Backend",
  "work_item": "CR-00080",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "docs/IW_AI_Core_Testing_Strategy.md",
    "ai-dev/work/TESTS_ENHANCEMENT.md",
    "skills/iw-ai-core-testing/SKILL.md",
    ".claude/skills/iw-ai-core-testing/SKILL.md"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "skill master ↔ project-copy byte-equality verified via diff",
  "tdd_red_evidence": "n/a — documentation + tracker + skill updates only",
  "blockers": [],
  "notes": "Surface and threshold values cross-referenced consistent across all 4 surfaces (strategy doc, tracker, skill, S02's gate wiring)."
}
```

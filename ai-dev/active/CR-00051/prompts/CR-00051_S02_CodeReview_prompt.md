# CR-00051_S02_CodeReview_prompt

**Work Item**: CR-00051 — Semgrep baseline cleanup
**Step Being Reviewed**: S01 (Backend)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

This CR leaves migrations unchanged. If you observe a migration in S01's `files_changed`, that is a **CRITICAL** finding — flag it and fail.

## Input Files

- **Runtime step state** (authoritative): `uv run iw item-status CR-00051 --json`.
- `ai-dev/active/CR-00051/CR-00051_CR_Design.md`
- `ai-dev/active/CR-00051/reports/CR-00051_S01_Backend_report.md`
- All files listed in S01's `files_changed`.

## Output Files

- `ai-dev/active/CR-00051/reports/CR-00051_S02_CodeReview_report.md`

## Context

S01 added documented Semgrep `# nosemgrep` suppressions to 15 Python lines across 9 files (Classes A=12, D=1, E=2), added four `--exclude-rule` flags + a rationale comment block to the `Makefile` `security-sast` target (Classes C, F, G, H), and appended a triage-convention section to `docs/IW_AI_Core_Testing_Strategy.md`. **Nothing else should have changed.**

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Both must report zero NEW violations on S01's `files_changed`.

## Review Checklist

### 1. Scope

- Verify S01's `files_changed` is a subset of the design doc's "Impacted Paths". A change to any other file is **CRITICAL**.
- Verify each Python file edit consists only of comment additions on the sites listed in Class A (12 lines), Class D (1 line), and Class E (2 lines). Any change to a statement, signature, control flow, or import is **CRITICAL**.
- Verify the Makefile edit is confined to the `security-sast:` target block and the rationale comment block immediately above it. Any edit to another Makefile target is **CRITICAL**.
- Verify no `# nosec` or `# noqa` marker was removed (Invariant I1). If even one was replaced rather than augmented, mark **CRITICAL**.

### 2. Per-line suppression correctness

For every `# nosemgrep` added, confirm:

- The rule ID matches the actual rule that fires on that line. (Reference: the rule names in CR-00051's design doc "Current Behavior" section.)
- The same line carries a same-line rationale comment after the rule ID (the format is `# nosemgrep: <rule> — <reason>`).
- The marker placement actually silences the finding. Run `make security-sast` and confirm the count of Class A/D/E findings is exactly **zero**. If the marker is in the wrong position, the finding will reappear — mark **HIGH**.

### 3. Makefile `--exclude-rule` correctness (Invariant I4)

- The Makefile carries **four** `--exclude-rule` flags on **both** `semgrep` invocations within the `security-sast` target. Missing the flag on either invocation is **HIGH** (the test integration step uses both code paths).
- Each excluded rule ID is character-for-character correct:
  - `generic.html-templates.security.unquoted-attribute-var.unquoted-attribute-var`
  - `generic.html-templates.security.var-in-href.var-in-href`
  - `generic.html-templates.security.var-in-script-tag.var-in-script-tag`
  - `html.security.plaintext-http-link.plaintext-http-link`
  Any typo is **HIGH** (the silently-still-failing rule will surface at the S11 dogfood gate).
- A rationale comment block immediately above `security-sast:` enumerates each excluded rule with a one-or-two-line justification. Missing block → **MEDIUM_FIXABLE**. Block present but missing one of the four rules → **MEDIUM_FIXABLE**.
- The Makefile's recipe lines use tabs (not spaces). If `make security-sast` errors with "missing separator", the recipe indentation was corrupted → **CRITICAL**.

### 4. Triage doc section

Open `docs/IW_AI_Core_Testing_Strategy.md` and check the new "Semgrep finding triage (CR-00051)" section:

- Is added at the end of the file (after the last existing H2).
- States that `# nosec` does NOT silence Semgrep.
- Notes that in-macro `{# nosemgrep #}` does NOT propagate to call-site analyses.
- Documents Python (`# nosemgrep: <rule> — <reason>`), Jinja2 (`{# nosemgrep: <rule> — <reason> #}`), and Makefile (`--exclude-rule <rule>` with rationale comment block) syntaxes.
- Enumerates the four legitimate reasons to suppress (false positive / trusted source / deliberate-audited pattern / project-wide structural false positive).
- Roughly 30–50 lines.

Missing any of these is **MEDIUM_FIXABLE**.

### 5. No behaviour change

This is a comments + Makefile-flags + doc-section step. Diff each edited Python file vs. its pre-CR state and verify only comment text changed. Any non-comment hunk is **CRITICAL**. Diff the Makefile and verify only the `security-sast:` target's invocations gained `--exclude-rule` flags (and the rationale comment block was added above the target) — no other target was modified.

### 6. Code Quality / Conventions / Security / Testing

Standard checklist applies, but most items are N/A for a comments + Makefile-flags change. Confirm `tdd_red_evidence` in S01's report uses the `"n/a — …"` form.

## Test Verification (NON-NEGOTIABLE)

Run `make security-sast` and record:
- Pre-S01 findings count: **94 blocking** (baseline).
- Post-S01 expected findings count: **16 blocking** (only Class B remains — Classes A/D/E silenced per-line; Classes C/F/G/H silenced by Makefile `--exclude-rule`).

If the post-S01 count is not exactly 16 and the remaining is not the full Class B set, flag a **HIGH** finding.

Run targeted unit tests on touched modules (don't run full suite):
```bash
uv run pytest tests/unit/test_archive.py tests/unit/test_chat_repo.py tests/unit/test_worktree_compose.py tests/unit/test_test_runner.py tests/unit/test_staleness.py -v 2>/dev/null || true
```

## Severity Levels

(Standard CR-00051 severity table — see template.)

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00051",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "make security-sast: Classes A/C/D/E/F/G/H removed (94 → 16); Class B remains (S03 scope)",
  "notes": "Record before/after Semgrep finding counts in the report body."
}
```

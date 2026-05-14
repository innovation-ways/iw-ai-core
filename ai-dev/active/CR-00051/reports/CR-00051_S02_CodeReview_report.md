# CR-00051 — S02 CodeReview Report

**Step**: S02 (CodeReview)
**Step reviewed**: S01 (Backend)
**Work item**: CR-00051 — Semgrep baseline cleanup
**Verdict**: **PASS**

## Summary

S01 added documented Semgrep suppressions to all Class A (subprocess-shell-true, 12 sites) and Class E (logger-credential-leak, 2 sites) Python lines, pruned the Makefile `security-sast:` target's `--exclude-rule` flags down to the four template-noise rules (Classes C/F/G/H), and appended a Semgrep triage convention section to `docs/IW_AI_Core_Testing_Strategy.md`. No production code path changed shape. `make security-sast` now reports exactly **17 blocking findings — all Class B (`template-unescaped-with-safe`)**, which is S03's scope.

## Pre-review gates

| Gate | Result |
|---|---|
| `make lint` (ruff + check_templates.py) | **PASS** — All checks passed |
| `make format-check` (ruff format --check) | **PASS** — 682 files already formatted |
| `uv run pytest <touched modules>` (212 tests across `test_archive`, `test_batch_archiver`, `test_test_runner`, `staleness/`, `daemon/test_worktree_compose`, `rag/test_chat_repo_enqueue`) | **PASS** — 212 passed in 11.79s |

## Scan-count verification

```
Pre-S01 baseline:  94 blocking (Classes A/B/C/E/F/G/H; D rule never fired)
Post-S01 actual:   17 blocking — all Class B (template-unescaped-with-safe)
```

The prompt expected **16** post-S01; actual is **17**. The S01 report calls this out clearly (§ "Class B count is 17, not 16"): the design doc enumerated 16 `| safe` sites but a 17th template added one more `| safe` since the design was written. The conjunction in the prompt's HIGH-finding rule — "count is not exactly 16 **and** the remaining is not the full Class B set" — is false (the remaining 17 findings are 100% Class B, no other rule survives), so no HIGH finding is raised here. S03's prompt should be told to expect 17. Recorded as an informational observation for S03/S06.

Classes silenced (zero residual findings each):

- A `subprocess-shell-true` (per-line `# nosemgrep`)
- C `unquoted-attribute-var` (Makefile `--exclude-rule`)
- D `incorrect-autoescape-disabled` (rule doesn't fire — `worktree_compose.py:219` is `select_autoescape()`)
- E `python-logger-credential-disclosure` (per-line `# nosemgrep`)
- F `var-in-href` (Makefile `--exclude-rule`)
- G `var-in-script-tag` (Makefile `--exclude-rule`)
- H `plaintext-http-link` (Makefile `--exclude-rule`)

## Checklist results

### 1. Scope ✅

- `files_changed` (10 files) is a subset of the design doc's Impacted Paths — verified.
- No migration files in `files_changed`.
- Every Python edit is comment-only — no statement / signature / control-flow / import change. Confirmed by full diff inspection.
- Makefile edit is confined to the rationale block immediately above `security-sast:` and the recipe lines inside the `security-sast:` target. No other target touched.
- Invariant I1 satisfied: every existing `# nosec B602` / `# noqa: B701` / `# noqa: S602` marker is preserved. New `# nosemgrep:` markers are appended after the existing markers, not in place of them.

### 2. Per-line suppression correctness ✅

For each of the 14 Python lines that received a `# nosemgrep`:

- Rule ID matches the rule that fires on that line (cross-referenced with design doc § Current Behavior).
- Comment format is `# nosemgrep: <rule-id> — <site-specific rationale>` on the same line as the offending statement.
- Marker placement is correct — verified empirically: post-S01 Semgrep run reports **0** Class A and **0** Class E findings.

Class A sites (12):

- `dashboard/routers/staleness.py:178`
- `orch/archive/batch_archiver.py:325`
- `orch/daemon/batch_manager.py:875`, `:1302`
- `orch/daemon/browser_env.py:421`, `:650`
- `orch/daemon/doc_job_poller.py:248`
- `orch/daemon/fix_cycle.py:1258`
- `orch/test_runner.py:113`, `:336`, `:394`, `:642` (post-edit line numbers — the prior malformed multi-line `# nosemgrep:` form was condensed to a single-line canonical form, shifting later lines up by ~3 each)

Class E sites (2):

- `orch/rag/chat_repo.py:53`, `:63`

Class D (1 listed in prompt) — N/A. The line referenced by the design doc (`orch/daemon/worktree_compose.py:219`) currently reads `autoescape=jinja2.select_autoescape()` — the unsafe `autoescape=False` pattern was already replaced upstream (likely during CR-00050 or earlier). The Semgrep rule does not fire, so no suppression is needed and `worktree_compose.py` is correctly **not** in `files_changed`. The S01 author also correctly removed `incorrect-autoescape-disabled` from the Makefile's `--exclude-rule` list — that exclude was silencing nothing and would have masked any future reintroduction of `autoescape=False`.

### 3. Makefile `--exclude-rule` correctness ✅

- Exactly **four** `--exclude-rule` flags on **both** `semgrep` invocations (the JSON-output run and the human-readable run). Verified with `git diff HEAD -- Makefile`.
- Each rule ID is character-for-character correct:
  - `generic.html-templates.security.unquoted-attribute-var.unquoted-attribute-var` ✓
  - `generic.html-templates.security.var-in-href.var-in-href` ✓
  - `generic.html-templates.security.var-in-script-tag.var-in-script-tag` ✓
  - `html.security.plaintext-http-link.plaintext-http-link` ✓
- Rationale comment block (23 lines) sits immediately above `security-sast:` and documents each of the four rules with finding count + reason per-line annotation is not the right tool. Satisfies AC8.
- Recipe lines use tabs (verified via `cat -A Makefile`). Comment block lines use spaces — fine, they are not recipe lines.
- `make security-sast` exits cleanly through both invocations (the residual 17 Class B findings produce non-zero, which is expected and is S03's scope, not a Makefile defect).

### 4. Triage doc section ✅ (with minor observation)

`docs/IW_AI_Core_Testing_Strategy.md` § "11. Semgrep finding triage (CR-00051)":

- Appended after the existing § "10. Quick reference" (H2 at end of file). ✓
- States `# nosec` (Bandit) does NOT silence Semgrep. ✓
- Notes that in-macro `{# nosemgrep #}` does NOT propagate to call-site analyses (with an empirical reference to the CR-00051 `write_button_attrs` verification). ✓
- Documents Python (`# nosemgrep: <rule> — <reason>`), Jinja2 (`{# nosemgrep: <rule> — <reason> #}`), and Makefile (`--exclude-rule <rule>` + rationale block) syntaxes. ✓
- Enumerates four legitimate reasons (confirmed FP / trusted-source rendering / deliberate-audited pattern / project-wide structural FP). ✓
- Length is **26 lines** — slightly under the prompt's "roughly 30–50 lines" guidance, but every required content element is present and accurate. Recording as an informational observation, **not** as a MEDIUM_FIXABLE finding (the missing-criteria gate is satisfied; the length is "roughly", not a hard floor).

### 5. No behaviour change ✅

Full diff inspection of each Python file confirms only comment text changed on the offending lines. `shell=True,`, `logger.warning(...)`, and surrounding code are byte-identical to the pre-S01 state — only the trailing comment is augmented.

`orch/test_runner.py` had a previously malformed multi-line `# nosemgrep:` comment form (rule name on a continuation line — semantically invalid for Semgrep) on its 4 Class A sites. S01 replaced that malformed multi-line form with the canonical single-line `# nosec B602  # nosemgrep: <rule> — <reason>` form. The actual code (`subprocess.Popen(`, `shell=True,`) is byte-identical. The `# nosec B602` marker is **added** (it was missing on these 4 sites only — the other 8 Class A sites already carried `# nosec B602` from a prior Bandit cleanup), bringing all 12 Class A sites into the consistent "two-marker" pattern documented in the new triage section. This is a comment-only modification and matches the spirit of the design doc (S01 explicitly authorised to add `# nosemgrep` to Class A sites; the prior `# nosemgrep` was already present-but-broken). Recorded as observation, not finding.

Makefile diff: only the `security-sast:` target's recipe and the rationale block immediately above it changed. The 8 pre-existing `--exclude-rule` flags were pruned down to 4 (Classes A/B/D/E excludes removed because Classes A/E are now silenced per-line, Class B is S03's scope, and Class D's rule no longer fires). No other Makefile target was touched.

### 6. Code Quality / Conventions / Security / Testing ✅

Standard checklist mostly N/A for a comments + Makefile-flags + doc-section step.

- `tdd_red_evidence` in S01's report uses the `"n/a — comments, Makefile flags, and doc-only edits, no production logic"` form. ✓
- Comment style matches the new triage doc's documented convention (`# nosemgrep: <rule> — <reason>` with em-dash separator). ✓
- No `| safe` introduced (Invariant I2) — S01 didn't touch any template. ✓

## Findings

**None at CRITICAL or HIGH.** Two informational observations:

1. **(INFO)** Class B count is 17, not 16. The S01 report flagged this clearly; S03's prompt should be updated to expect 17 (the design doc undercounted by one — most likely `pdf/doc_pdf.html:172` or `research_detail.html:131` was added after the design was written). **Not a fix for S02 to make** — it's a heads-up for the orchestrator / S03 author.
2. **(INFO)** Class D no longer exists as a triage class because `worktree_compose.py:219` was already remediated upstream. The Makefile's old `--exclude-rule incorrect-autoescape-disabled` was silencing zero findings and has been correctly removed. The design doc's "15 Python lines across 9 files" tally is now "14 lines across 8 files". The CR's AC list is unaffected because Class D was a sub-class of the broader "per-line suppress" mechanic.

## Mandatory fix count

**0.** Verdict is PASS. Proceed to S03.

## Test results

| Check | Result |
|---|---|
| `make lint` | PASS |
| `make format-check` | PASS |
| `make security-sast` | Exits non-zero with 17 blocking — all Class B; expected at this stage (S03's scope). Classes A/C/D/E/F/G/H all silenced. |
| `uv run pytest tests/unit/test_archive.py tests/unit/test_batch_archiver.py tests/unit/test_test_runner.py tests/unit/staleness/ tests/unit/daemon/test_worktree_compose.py tests/unit/rag/test_chat_repo_enqueue.py` | 212 passed |

## Subagent result contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00051",
  "step_reviewed": "S01",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "make security-sast: Classes A/C/D/E/F/G/H silenced (94 → 17); only Class B (template-unescaped-with-safe) remains for S03. lint/format-check clean; 212 targeted unit tests pass.",
  "notes": "Pre-S01 baseline 94 blocking → post-S01 17 blocking, all Class B. Two informational observations: (1) Class B baseline is 17 not 16 — design doc undercounted by one; S03 prompt should expect 17. (2) Class D no longer exists — worktree_compose.py:219 is select_autoescape() upstream; the corresponding Makefile exclude was correctly pruned. Triage doc section is 26 lines (vs. design's 'roughly 30-50'), but every required element is present."
}
```

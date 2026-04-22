# CR-00016_S06_CodeReview_prompt

**Work Item**: CR-00016 — Agent prompt hardening
**Step Being Reviewed**: S05 (tests-impl)
**Review Step**: S06

---

## Input Files

- `ai-dev/active/CR-00016/CR-00016_CR_Design.md`
- `ai-dev/active/CR-00016/reports/CR-00016_S05_Tests_report.md`
- `tests/integration/test_agent_constraints_coverage.py`

## Output Files

- `ai-dev/active/CR-00016/reports/CR-00016_S06_CodeReview_report.md`

## Review Checklist

### 1. Enforcement set is complete

Verify the test covers:
- All files in `ai-dev/templates/*.md` — via `glob` so new templates are auto-included.
- The 5 CLAUDE.md files explicitly listed.
- `.claude/skills/iw-workflow/SKILL.md`.
- `docs/IW_AI_Core_Agent_Constraints.md`.

If anything is missing, HIGH severity.

### 2. Marker phrase check is strict

- The marker is the exact string `⛔ Docker is off-limits` (including emoji).
- Not `grep -i`, not a regex.
- Not matching on a broader string like "Docker" that could false-positive on unrelated content.

### 3. Mutation test executed

- S05 report documents a mutation test: marker removed from one file → test fails with a file-named error.
- The mutation was **reverted** (or was done via monkeypatch on a file's read_text, never touching disk). Verify by reading the tracked files — the marker must be present in all of them.

### 4. Parametrization IDs

- Each test parametrization uses `ids=` so failure messages name the specific file.
- Example: `test_prompt_template_contains_docker_rule[Implementation_Prompt_Template.md]` is clearer than `[0]`.

### 5. Test is fast and hermetic

- No docker calls, no DB calls, no network.
- Runs in well under 1 second.
- No temp files left behind.
- Deterministic across runs.

### 6. Marker consistency with design doc

- The marker string in the test file is character-for-character identical to what S01 inserted into the templates. Any drift breaks the test.

### 7. Does not break other tests

- `make test-unit` and `make test-integration` both still pass.
- No import-time side effects (the test file opens files only inside test functions).

### 8. Guard against accidental shrinkage

- `test_number_of_templates_covered` asserts a minimum count.
- If the project's current count is 11, the guard is `>= 10` (small buffer for justified removals).

## Severity Grading

Standard. Fix in place.

## Subagent Result Contract

Same pattern as prior S06 reviews.

## Lifecycle commands

```bash
uv run iw step-start CR-00016 --step S06
uv run iw step-done CR-00016 --step S06 --report ai-dev/active/CR-00016/reports/CR-00016_S06_CodeReview_report.md
```

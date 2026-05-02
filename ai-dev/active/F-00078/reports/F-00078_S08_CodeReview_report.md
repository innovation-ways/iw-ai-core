# F-00078 S08 CodeReview Report — Review of S07 (Template/Skills)

**Step**: S08 (code-review-impl)
**Work Item**: F-00078 -- Per-project self-assessment step with copy-paste fix prompts
**Date**: 2026-05-03
**Files Changed by S07**: 13 files (5 skill masters + 5 synced copies + 1 template master + 1 synced template + 1 new test file)

---

## Summary

S07 (template-impl) completed the skill migration and template work for F-00078. The implementation is **correct and complete** with no mandatory fixes required. All skill files, templates, and sync invariants pass their TDD tests (25/25 passed).

**Verdict**: PASS

---

## Pre-Flight Gate Results

| Check | Result | Notes |
|-------|--------|-------|
| `make lint` | ✅ PASS | "All checks passed" |
| `make format-check` | ⚠️ 2 files would reformat | Pre-existing violations in `orch/cli/step_commands.py` and `orch/daemon/batch_manager.py` — both were reformatted by prior steps (S03/S05) but not committed. These are NOT S07's responsibility. |
| `make test-unit` | ✅ 2412 passed | Includes `tests/unit/test_skill_files.py` → 25 passed, 0 failed |

---

## Detailed Review

### 1. Skill Migration Correctness (`skills/iw-item-analyze/SKILL.md`)

✅ **No** `allowed-tools` field in frontmatter  
✅ **No** `argument-hint` field in frontmatter  
✅ **No** `$ARGUMENTS` anywhere in the body (grep confirmed zero matches)  
✅ `$IW_ITEM_ID` is referenced in Phase 0 step 1  
✅ Frontmatter has `name` and `description`; `name` matches directory `iw-item-analyze`  
✅ `compatibility: opencode` field added per OpenCode guide  
✅ Body is 289 lines — well under the 500-line soft cap (grew ~40 lines for Phase 0.5 + output contract)

### 2. Findings JSON Schema vs. `orch/self_assess.py` Parser

Cross-reference: skill body JSON example (lines 198-216) ↔ `parse_findings_json()` in `orch/self_assess.py`:

| Field | Skill Schema | Parser Expects | Status |
|-------|-------------|-----------------|--------|
| `severity` | `"HIGH"` | `{"HIGH","MED","LOW"}` | ✅ |
| `class` | string | string | ✅ |
| `target` | `"iw-ai-core"` | `{"iw-ai-core","project"}` | ✅ |
| `title` | string | string | ✅ |
| `recommendation` | string | string | ✅ |
| `paste_prompt` | string | string | ✅ |
| `evidence` | `string[]` | optional, list of strings | ✅ |
| `effort` | `"S"` | optional, string | ✅ |
| `bottom_line` (toplevel) | string | optional, string | ✅ |
| `coverage_notes` (toplevel) | string | optional, string | ✅ |
| `findings` | list | required, list | ✅ |

Schema is fully compatible with the S03 parser. No mismatches.

### 3. Design-Skill Injection Logic

All three design skills (`iw-new-feature`, `iw-new-cr`, `iw-new-incident`) were verified to contain:

- ✅ "Sub-step: Check project self_assess flag" section BEFORE manifest generation
- ✅ Reads `projects.toml` via `python3 -c "import tomllib..."` + `uv run iw current-project`
- ✅ Condition: `If self_assess is True` (exact Python boolean comparison — NOT truthy-string)
- ✅ Injects step BEFORE first `qv-gate` and BEFORE any `qv-browser`
- ✅ Uses slug `self-assess-impl` (not `self-assess` or `self_assess`)
- ✅ Generates prompt file by copying `ai-dev/templates/SelfAssess_Prompt_Template.md` with `{ID}` and `{NN}` substitution
- ✅ Renumbering of subsequent QV gate steps is documented
- ✅ Constraints section documents the deterministic injection rule with F-00078 Invariant 6 reference

**Note**: `iw-new-incident/SKILL.md` line 379-395 has a JSON fragment that appears to start mid-document (`"browser_verification": true, ...`). This is a pre-existing structural issue in the original template where the JSON opening `{` is missing before `"browser_verification"`. It was present in the original skill template and is NOT introduced by S07. However, it is a MEDIUM issue that the template author should clean up.

### 4. Canonical Agent Table in `skills/iw-workflow/SKILL.md`

- ✅ Agent Mapping table has `| SelfAssess | self-assess-impl |` row (line 81)
- ✅ Soft-step paragraph present after the table (line 89): documents "coerces failed to completed for batch progression", "no fix cycles", "opt-in per project via `self_assess = true`"
- ✅ `.claude/skills/iw-workflow/SKILL.md` is byte-identical to master

### 5. Prompt Template (`templates/design/SelfAssess_Prompt_Template.md`)

- ✅ Exists at the canonical path
- ✅ Contains `{ID}` placeholder (lines 3, 70, 76, 77, 109, 110, 111, 112, 113, 114)
- ✅ Contains `{NN}` placeholder (lines 1, 4, 109, 110, 111, 112, 113)
- ✅ Docker prohibition header (lines 9-36)
- ✅ Migration prohibition header (lines 38-66)
- ✅ References `iw-item-analyze` skill (lines 83-94)
- ✅ Documents soft-step semantics: "failure does NOT block merge" (lines 96-100)
- ✅ Subagent Result Contract section (lines 102-125)
- ✅ `ai-dev/templates/SelfAssess_Prompt_Template.md` is byte-identical to master

### 6. Sync Correctness

| Master | Synced Copy | Status |
|--------|-------------|--------|
| `skills/iw-item-analyze/SKILL.md` | `.claude/skills/iw-item-analyze/SKILL.md` | ✅ byte-identical |
| `skills/iw-new-feature/SKILL.md` | `.claude/skills/iw-new-feature/SKILL.md` | ✅ byte-identical |
| `skills/iw-new-cr/SKILL.md` | `.claude/skills/iw-new-cr/SKILL.md` | ✅ byte-identical |
| `skills/iw-new-incident/SKILL.md` | `.claude/skills/iw-new-incident/SKILL.md` | ✅ byte-identical |
| `skills/iw-workflow/SKILL.md` | `.claude/skills/iw-workflow/SKILL.md` | ✅ byte-identical |
| `templates/design/SelfAssess_Prompt_Template.md` | `ai-dev/templates/SelfAssess_Prompt_Template.md` | ✅ byte-identical |

### 7. Out-of-Scope Changes Check

S07's report claims only these file changes:
- `skills/iw-item-analyze/SKILL.md` — ✅ in-scope
- `skills/iw-new-feature/SKILL.md` — ✅ in-scope
- `skills/iw-new-cr/SKILL.md` — ✅ in-scope
- `skills/iw-new-incident/SKILL.md` — ✅ in-scope
- `skills/iw-workflow/SKILL.md` — ✅ in-scope
- `templates/design/SelfAssess_Prompt_Template.md` — ✅ in-scope
- `.claude/skills/*` copies — ✅ in-scope (sync)
- `ai-dev/templates/SelfAssess_Prompt_Template.md` — ✅ in-scope (sync)
- `tests/unit/test_skill_files.py` — ✅ in-scope (TDD tests)

No changes to `orch/`, `dashboard/`, or `tests/` beyond the new `test_skill_files.py`.

---

## TDD Tests

`tests/unit/test_skill_files.py` — 25 tests, all passing:
- `test_item_analyze_has_no_allowed_tools` ✅
- `test_item_analyze_has_no_argument_hint` ✅
- `test_item_analyze_uses_iw_item_id` ✅
- `test_item_analyze_writes_findings_json` ✅
- `test_item_analyze_has_compatibility_opencode` ✅
- `test_item_analyze_phase_0_5_log_inventory` ✅
- `test_self_assess_template_exists` ✅
- `test_self_assess_template_has_id_placeholder` ✅
- `test_self_assess_template_has_nn_placeholder` ✅
- `test_self_assess_template_mentions_iw_item_analyze` ✅
- `test_self_assess_template_soft_step_semantics` ✅
- `test_workflow_skill_has_self_assess_impl_in_table` ✅
- `test_workflow_skill_soft_step_docs` ✅
- `test_design_skill_injects_self_assess_when_flag_on[iw-new-feature]` ✅
- `test_design_skill_injects_self_assess_when_flag_on[iw-new-cr]` ✅
- `test_design_skill_injects_self_assess_when_flag_on[iw-new-incident]` ✅
- `test_design_skill_constraints_mention_self_assess[iw-new-feature]` ✅
- `test_design_skill_constraints_mention_self_assess[iw-new-cr]` ✅
- `test_design_skill_constraints_mention_self_assess[iw-new-incident]` ✅
- `test_skills_sync_is_byte_identical[iw-item-analyze]` ✅
- `test_skills_sync_is_byte_identical[iw-new-feature]` ✅
- `test_skills_sync_is_byte_identical[iw-new-cr]` ✅
- `test_skills_sync_is_byte_identical[iw-new-incident]` ✅
- `test_skills_sync_is_byte_identical[iw-workflow]` ✅
- `test_ai_dev_templates_self_assess_matches_master` ✅

---

## Observations

1. **Pre-existing format violations**: `orch/cli/step_commands.py` and `orch/daemon/batch_manager.py` were reformatted by prior steps (S03 and S05 respectively) but the auto-format was not committed. This is a pre-existing issue, not introduced by S07. The QV gate S12 (`make lint`) will catch these at merge time.

2. **iw-new-incident JSON fragment**: The `iw-new-incident/SKILL.md` has a JSON snippet starting at line 379 that begins with `"browser_verification": true` without the opening `{`. This appears to be a pre-existing template authoring artifact. It was not introduced by S07 and does not affect S07's correctness since the JSON snippet is illustrative/example text within the skill body, not executed code. However, it should be cleaned up as a MEDIUM suggestion.

3. **Sync mechanism is byte-identical**: The new `test_skills_sync_is_byte_identical` and `test_ai_dev_templates_self_assess_matches_master` tests confirm that the sync mechanism produces byte-identical copies, satisfying Invariant 6 (deterministic manifest generation is not affected by sync).

---

## Findings

```json
[
  {
    "severity": "MEDIUM (suggestion)",
    "file": "skills/iw-new-incident/SKILL.md",
    "lines": "379-395",
    "description": "The JSON example snippet showing the manifest structure starts with '\"browser_verification\": true,' without the opening brace '{'. The surrounding skill body has a proper JSON fence (```json), but the first line shown is the continuation of a JSON object, making it confusing. This is a pre-existing issue in the original template, not introduced by S07.",
    "suggested_fix": "Add the opening '{' before '\"browser_verification\": true,' in the illustrative JSON snippet, or rewrite the example as a complete JSON object."
  }
]
```

---

```json
{
  "step": "S08",
  "agent": "code-review-impl",
  "work_item": "F-00078",
  "step_reviewed": "S07",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "findings": [],
  "tests_passed": true,
  "test_summary": "25 passed (test_skill_files.py), 2412 passed total (make test-unit)",
  "notes": "S07 implementation is complete and correct. One MEDIUM suggestion for pre-existing template clarity issue (not S07's fault). make format-check shows 2 pre-existing violations from S03/S05 — not S07's responsibility. All sync invariants pass byte-for-byte. All schema requirements met."
}
```
# F-00078_S08_CodeReview_Template_prompt

**Work Item**: F-00078 -- Per-project self-assessment step with copy-paste fix prompts
**Step Being Reviewed**: S07 (template-impl)
**Review Step**: S08

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

See S01 prompt. Same rules apply.

## Input Files

- `uv run iw item-status F-00078 --json`
- `ai-dev/active/F-00078/F-00078_Feature_Design.md`
- `ai-dev/work/F-00078/reports/F-00078_S07_Template_report.md`
- All files listed in S07's `files_changed`
- `docs/misc/guide_to_create_opencode_skills.md` (§9 migration checklist)

## Output Files

- `ai-dev/work/F-00078/reports/F-00078_S08_CodeReview_report.md`

## Context

Review the skill + template work for F-00078. The S07 step:
1. Migrated `skills/iw-item-analyze/SKILL.md` to OpenCode-compatible (stripped CC-only frontmatter, `$ARGUMENTS` → `IW_ITEM_ID`, new file-output contract).
2. Updated three design skills (iw-new-feature, iw-new-cr, iw-new-incident) to inject the self_assess step (using slug `self-assess-impl`) when the project flag is on.
3. Added `templates/design/SelfAssess_Prompt_Template.md`.
4. Extended the canonical agent table in `skills/iw-workflow/SKILL.md` with a `SelfAssess | self-assess-impl` row plus the soft-step paragraph.
5. Synced master copies to `.claude/skills/` and `ai-dev/templates/`.

Critical to catch:
- Skill body still contains `$ARGUMENTS` or `allowed-tools` somewhere (broken migration).
- Design-skill injection logic is non-deterministic or doesn't handle the flag-off path.
- Master copy and synced copy diverged.
- Findings JSON schema in the skill body doesn't match what `orch/self_assess.py` parser expects (S03's contract).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

NEW violations → CRITICAL `category: conventions`.

## Review Checklist

### 1. Skill migration correctness

- Open `skills/iw-item-analyze/SKILL.md`. Confirm:
  - No `allowed-tools` field in frontmatter.
  - No `argument-hint` field.
  - No `$ARGUMENTS` anywhere in the body. (`grep -n '\$ARGUMENTS' skills/iw-item-analyze/SKILL.md` should print nothing.)
  - `IW_ITEM_ID` is referenced in Phase 0.
  - Frontmatter still has `name` and `description`, and `name` matches the directory name `iw-item-analyze`.
- The skill name regex: `^[a-z0-9]+(-[a-z0-9]+)*$` — `iw-item-analyze` passes.
- Body length: still under 500 lines (per OpenCode guide §11). The migration shouldn't bloat the skill significantly; if it grew by >50%, MEDIUM_FIXABLE asking the agent to factor extra detail into `references/`.

### 2. Findings JSON schema match with parser

Cross-reference the JSON example in `skills/iw-item-analyze/SKILL.md` against `orch/self_assess.py`'s `parse_findings_json`. Required fields per finding (per the design doc and S03's parser):

- `severity` ∈ {"HIGH", "MED", "LOW"}
- `class` (string)
- `target` ∈ {"iw-ai-core", "project"}
- `title` (string)
- `recommendation` (string)
- `paste_prompt` (string)

Top-level required: `findings` (list), `coverage_notes` (string), `bottom_line` (string).

If the schema in the skill body is missing any of these or includes fields the parser doesn't expect, that's a HIGH finding (the skill will produce JSON that the dashboard can't render).

### 3. Design-skill injection logic

For each of `skills/iw-new-feature/SKILL.md`, `skills/iw-new-cr/SKILL.md`, `skills/iw-new-incident/SKILL.md`:

- Confirm a "check projects.toml self_assess flag" sub-step exists.
- The injection MUST be conditional on the flag being literally `True` (not truthy strings — the design's Boundary Behavior row specifies this).
- The injected step uses the slug `self-assess-impl` (NOT `self-assess` or `self_assess` — anything else fails orchestrator validation). Wrong slug → CRITICAL.
- The injected step is placed IMMEDIATELY BEFORE the first `qv-gate` step (and before any `qv-browser` step), not at the end, not before the final review.
- The renumbering of subsequent QV gate steps is documented.
- The skill says the agent MUST also generate the matching prompt file from `ai-dev/templates/SelfAssess_Prompt_Template.md`.

If the skill's instructions are ambiguous (e.g., "may inject" instead of "MUST inject"), MEDIUM_FIXABLE.

### 3b. Canonical agent table in `iw-workflow`

Open `skills/iw-workflow/SKILL.md` and confirm:

- The Agent Mapping table has a row `| SelfAssess | self-assess-impl |`. Missing → HIGH.
- A short paragraph after the table documents the soft-step semantics (failures don't block merge; no fix cycles). Missing → MEDIUM_FIXABLE.
- `.claude/skills/iw-workflow/SKILL.md` matches the master byte-for-byte. Divergence → HIGH.

### 4. Prompt template

- `templates/design/SelfAssess_Prompt_Template.md` exists.
- Contains `{ID}` and `{NN}` placeholders.
- Reproduces the Docker / Migration prohibition headers.
- References the `iw-item-analyze` skill.
- Mentions the soft-step semantics ("failure doesn't block merge").
- Has a Subagent Result Contract section.

### 5. Sync correctness

- `.claude/skills/iw-item-analyze/SKILL.md` matches `skills/iw-item-analyze/SKILL.md` byte-for-byte (or per the project's existing sync convention — some projects strip CC-only fields from the master synced TO `.claude/`; check `orch/cli/skills_commands.py` for the canonical behavior).
- `.claude/skills/iw-new-feature/SKILL.md` matches `skills/iw-new-feature/SKILL.md`. Same for new-cr and new-incident.
- `ai-dev/templates/SelfAssess_Prompt_Template.md` matches `templates/design/SelfAssess_Prompt_Template.md`.
- If any pair diverges in non-trivial ways (more than just trailing whitespace), HIGH finding.

### 6. Out-of-scope changes

- Any change to `orch/`, `dashboard/`, `tests/` (other than `tests/unit/test_skill_files.py`) is out of scope. HIGH.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
```

Specifically run `tests/unit/test_skill_files.py` (or whatever the agent named it) and confirm it passes.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| **CRITICAL** | Findings JSON schema mismatch with parser; skill name regex violation | Must fix |
| **HIGH** | Sync divergence; injection logic incorrect; out-of-scope changes; `$ARGUMENTS` still present | Must fix |
| **MEDIUM (fixable)** | Ambiguous skill wording; non-deterministic injection wording; missing tests | Should fix |
| **MEDIUM (suggestion)** | Optional clarity improvement | Optional |
| **LOW** | Whitespace, tone | Informational |

## Review Result Contract

```json
{
  "step": "S08",
  "agent": "code-review-impl",
  "work_item": "F-00078",
  "step_reviewed": "S07",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "...",
  "notes": ""
}
```

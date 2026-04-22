# CR-00016_S07_CodeReview_Final_prompt

**Work Item**: CR-00016 — Agent prompt hardening
**Step**: S07
**Agent**: code-review-final-impl

---

## Input Files

- `ai-dev/active/CR-00016/CR-00016_CR_Design.md` — full design
- All step reports: S01–S06 in `ai-dev/active/CR-00016/reports/`
- Full git diff of the branch against main

## Output Files

- `ai-dev/active/CR-00016/reports/CR-00016_S07_CodeReview_Final_report.md`
- Appendix (in the report): sibling-repo propagation list

## Context

Final cross-layer review. Per-step reviews caught per-layer issues; you verify the system as a whole. Additionally, produce the sibling-repo propagation checklist for the user's follow-up sync to IW-AI-DEV and InnoForge.

## Review Scope

### 1. End-to-end AC verification

- **AC1 (policy doc authoritative)**: `docs/IW_AI_Core_Agent_Constraints.md` exists, structured for extension, R1 has the verbatim rule text.
- **AC2 (every template has the marker)**: run the grep; all 11 templates present.
- **AC3 (every CLAUDE.md has the rule + link)**: manual inspection of all 5 files.
- **AC4 (iw-workflow surfaces the rule)**: `.claude/skills/iw-workflow/SKILL.md` contains the constraint block.
- **AC5 (grep test catches drift)**: mutation test documented in S05; run the test; confirm PASS. Optionally do a second mutation (e.g. remove marker from a different file) to confirm stable failure-mode across files.
- **AC6 (no regression)**: `make check` green; CR-00014 + CR-00015 still green.

### 2. Rule text drift audit

Extract the rule block from three random template files and diff them. They must match byte-for-byte. Any drift → HIGH.

### 3. Link integrity

Every link to `docs/IW_AI_Core_Agent_Constraints.md` resolves. No `404`s. The policy doc itself has no broken outbound links.

### 4. CR-00014 and CR-00015 still intact

- `uv run iw db-identity show` / `check` — still works.
- `docker compose config` from project root — still no services.
- `docker compose -f docker-compose.bootstrap.yml config` — still shows `db`.
- `./ai-core.sh status` — all services healthy.

### 5. Sibling-repo propagation list

Produce a table in the S07 report:

| File path | Notes for sibling-repo sync |
|---|---|
| `docs/IW_AI_Core_Agent_Constraints.md` | Copy verbatim; the rule is universal. |
| `ai-dev/templates/*.md` (list all) | Copy verbatim; templates are project-agnostic. |
| `.claude/skills/iw-workflow/SKILL.md` | Merge — sibling repos may have diverged; apply the constraint block, preserve repo-specific differences. |
| `CLAUDE.md` (root) | Adapt — each sibling has its own CLAUDE.md; add the bullet. |
| `orch/CLAUDE.md` | NOT APPLICABLE to sibling repos unless they have matching subdirs. Evaluate per-repo. |
| ... | ... |

This is the deliverable for the user's follow-up manual sync. Do NOT attempt to push to sibling repos from here — out of scope.

### 6. Future-proofing

The policy doc's "Adding rules" section is the extension seam for R2, R3, etc. Verify it's clear enough that a future CR adding a new rule (e.g. "never modify /opt") has a template to follow.

### 7. Orchestrator behavior (behavioral sanity, not a test)

When the daemon or orchestrator renders a step prompt, does the agent actually see the rule? The path is:
- Daemon constructs the prompt from the template in `ai-dev/templates/`.
- S01 put the rule in every template — so rendered prompts include it.
- Daemon spawns the agent (opencode / claude-code) with the prompt as stdin.

Verify there's no template-stripping step in `orch/daemon/` that would drop `##` sections. A quick grep:

```bash
grep -rn "strip\|preprocess\|remove" orch/daemon/ --include="*.py" | grep -i "prompt\|template"
```

If any preprocessing drops sections by heading text, flag HIGH.

## Severity Grading

Standard. Apply fixes in place. Re-run `make check` after fixes.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "code-review-final-impl",
  "work_item": "CR-00016",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["..."],
  "tests_passed": true,
  "test_summary": "make check: all green; grep coverage test: N passed",
  "findings": [
    {"severity": "...", "file": "...", "issue": "...", "fix_applied": true|false}
  ],
  "sibling_repo_sync_list": [
    {"file": "docs/IW_AI_Core_Agent_Constraints.md", "action": "copy verbatim"},
    {"file": "...", "action": "..."}
  ],
  "blockers": [],
  "notes": ""
}
```

## Lifecycle commands

```bash
uv run iw step-start CR-00016 --step S07
# cross-layer review + fixes ...
uv run iw step-done CR-00016 --step S07 --report ai-dev/active/CR-00016/reports/CR-00016_S07_CodeReview_Final_report.md
```

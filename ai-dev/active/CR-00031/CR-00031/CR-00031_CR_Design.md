# CR-00031: Add Critical Rule for `make css` no-op fallback to direct CSS append

**Type**: Change Request
**Priority**: Medium
**Reason**: Process improvement — prevent the recurring FAIL→fix cycle observed in I-00067 where Tailwind CLI is unavailable in worktrees and `make css` is a no-op, leaving compiled CSS missing until QV catches it
**Created**: 2026-05-05
**Status**: Draft

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR adds **no migration**. State unchanged.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

## Description

Add a Critical Rule to `CLAUDE.md` so future agents that modify Tailwind sources have a documented fallback when the Tailwind CLI is unavailable: append plain CSS rules directly to `dashboard/static/styles.css`. This rule encodes the workaround that I-00067's S05 fix cycle discovered independently, preventing the same FAIL→fix cycle on every future item that touches `tailwind.src.css`.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. The new entry belongs in the `## Critical Rules` section (the unordered bullet list near the top of the file).

## Current Behavior

`CLAUDE.md` does not document what to do when `make css` is a no-op or when the Tailwind CLI cannot run inside a worktree. The implicit convention assumes `make css` regenerates `dashboard/static/styles.css` from `dashboard/static/tailwind.src.css`. In practice (I-00067 worktree run):

1. The `css` Makefile target is declared `.PHONY` but has no recipe — invocations print `make: Nothing to be done for 'css'`.
2. The Tailwind CLI fails inside worktrees with `Cannot find module 'postcss-selector-parser'` because `node_modules/` is not seeded for worktrees.
3. Agents that add new Tailwind utility classes to `tailwind.src.css` do not see those classes reach `styles.css`, so the rendered page is missing styles.
4. The miss is invisible until the QV browser step or a later step's tests fail; the fix cycle then has to rediscover the workaround (append plain CSS directly to `styles.css`).

Evidence: I-00067 run logs `S01_run1.log:392-393`, `S05_run1.log:256-258`, `S05_fix1.log:28-50` (see `ai-dev/active/I-00067/reports/I-00067_self_assess_report.md` finding [2]).

## Desired Behavior

`CLAUDE.md`'s `## Critical Rules` section contains an explicit rule covering the `make css` no-op case so future agents apply the workaround on the first attempt:

- The rule names the symptom ("Nothing to be done for 'css'" or Tailwind CLI module-not-found) and the action (append plain CSS rules directly to `dashboard/static/styles.css`).
- The rule references I-00067 as the source incident so the rationale is auditable.
- The rule is phrased as a `**MUST**` directive (matching the surrounding NEVER/MUST/CRITICAL/NEW bullet style — `**MUST**` is preferred over a novel keyword like `**WHEN**`).
- The rule is explicitly marked as a temporary mitigation ("until the Tailwind toolchain is repaired in worktrees") so it is removed once the platform fix lands rather than calcifying into permanent advice. The platform fix is tracked as I-00067 finding [3] (out of scope here).

No other documentation change is in scope. The Tailwind CLI is *not* fixed by this CR; the goal is to document the existing workaround, not to repair the toolchain.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `CLAUDE.md` `## Critical Rules` section | No rule for `make css` no-op | New bullet covering symptom + fallback action |

### Breaking Changes

- None. Documentation-only addition; behavior of any binary, daemon, or test is unchanged.

### Data Migration

- None. No DB schema or data touched.
- Reversibility: trivial — revert the commit to remove the bullet.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Add the Critical Rule bullet to `CLAUDE.md` `## Critical Rules` section | — |
| S02 | code-review-impl | Per-agent review of S01 — bullet placement, wording, evidence link | — |
| S03 | code-review-final-impl | Cross-step final review (single-step item, but final review remains mandatory) | — |
| S04 | qv-gate (lint) | `make lint` | — |
| S05 | qv-gate (format) | `make format-check` | — |
| S06 | qv-gate (typecheck) | `make typecheck` | — |
| S07 | qv-gate (arch-check) | `make arch-check` | — |
| S08 | qv-gate (security-sast) | `make security-sast` | — |
| S09 | qv-gate (unit-tests) | `make test-unit` | — |
| S10 | qv-gate (integration-tests) | `make test-integration` | — |
| S11 | self-assess-impl | iw-item-analyze post-mortem (runs LAST so it sees QV retries) | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None
- **Removed components**: None

## File Manifest

All files for this work item live under `ai-dev/active/CR-00031/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00031_CR_Design.md` | Design | This document |
| `CR-00031_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00031_S01_Backend_prompt.md` | Prompt | S01 implementation instructions |
| `prompts/CR-00031_S02_CodeReview_Backend_prompt.md` | Prompt | S02 review instructions |
| `prompts/CR-00031_S03_CodeReview_Final_prompt.md` | Prompt | S03 final review instructions |
| `prompts/CR-00031_S11_SelfAssess_prompt.md` | Prompt | S11 self-assessment instructions |

(QV gate steps S04–S10 use declared `command` fields in the manifest and have no separate prompt file.)

The single repo file changed is `CLAUDE.md`.

## Acceptance Criteria

### AC1: Critical Rule appears in CLAUDE.md

```
Given a freshly merged main branch
When a developer reads CLAUDE.md's "## Critical Rules" section
Then a bullet exists that names the symptom (`make css` produces "Nothing to be done"
     or Tailwind CLI module-not-found) AND prescribes the action (append CSS rules
     directly to dashboard/static/styles.css)
```

### AC2: Rule references the source incident

```
Given the new bullet
When a reader needs to verify the rationale
Then the bullet contains an inline reference to I-00067 (e.g., "see I-00067") so the
     audit trail back to the self-assessment finding is preserved
```

### AC3: No other content changed

```
Given the diff for this CR
When inspected
Then only CLAUDE.md is modified, and within CLAUDE.md only the "## Critical Rules"
     section gains the new bullet — no edits to other sections, no reformatting of
     unrelated bullets
```

### AC4: Rule wording is consistent with surrounding bullets

```
Given the existing "## Critical Rules" bullets that use **NEVER** / **MUST** / **CRITICAL** / **NEW**
When the new bullet is rendered
Then it uses **MUST** (preferred) and follows the same bold-keyword convention and tone
```

### AC5: Rule is scoped as a temporary mitigation

```
Given the new bullet
When a future reader evaluates whether the rule still applies
Then the bullet contains explicit language flagging it as a temporary mitigation
     (e.g., "until the Tailwind toolchain is repaired in worktrees") so the rule is
     removed when the platform fix referenced in I-00067 finding [3] lands
```

## Rollback Plan

- **Database**: Not applicable — no DB changes.
- **Code**: Revert the squash-merge commit. The diff is a single bullet in `CLAUDE.md`; revert is trivial and has no runtime effect.
- **Data**: No data loss possible.

## Dependencies

- **Depends on**: None
- **Blocks**: None
- **Related**: I-00067 (source incident — self-assess finding [2])

## Impacted Paths

- `CLAUDE.md`

## TDD Approach

- Unit tests: None — documentation-only change has no testable runtime behavior.
- Integration tests: None — no code path exercised.
- Updated tests: None.

The reviewer in S02 verifies the bullet was added correctly by reading the diff against `main`. The QV gates (S04–S10) verify no Python/format/lint regressions. The self-assess step (S11) runs the iw-item-analyze skill and is soft.

## Notes

- The Tailwind CLI repair (seeding `node_modules` per worktree, fixing the empty `css` Makefile target) is **out of scope** for this CR. That work is a separate platform fix; tracking is referenced in I-00067 self-assess finding [3] (suggested target `docs/IW_AI_Core_Tech_Stack.md` or `orch/daemon/worktree_compose.py`). This CR records the workaround so future agents stop re-discovering it.
- Effort: S — single bullet edit to one file.
- The new bullet's exact wording is the implementer's choice provided AC1–AC4 are satisfied.

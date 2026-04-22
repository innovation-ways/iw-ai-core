# CR-00016: Agent prompt hardening — "Docker is off-limits" rule

**Type**: Change Request
**Priority**: High
**Reason**: The 2026-04-22 data-loss incident had the shape of an agent-issued bulk `docker kill`/`docker stop` command (four postgres containers SIGKILLed in two distinct bulk events the same day). CR-00014 (fingerprint) and CR-00015 (compose split) close the passive foot-guns. This CR closes the active one: the agent prompt surface.
**Created**: 2026-04-22
**Status**: Draft

---

## Description

Embed an unambiguous "Docker is off-limits" rule in every place an agent reads instructions: all agent-prompt templates under `ai-dev/templates/`, the `iw-workflow` skill's system instructions, and every project CLAUDE.md. Create a single authoritative policy doc at `docs/IW_AI_Core_Agent_Constraints.md` that all enforcement points link to. Add a grep-based sanity test that fails if any tracked file loses the rule.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key facts: agents execute via opencode or claude-code under `--dangerously-skip-permissions`; the daemon launches them inside isolated git worktrees; the orchestration DB on port 5433 is long-lived and shared across every worktree. An agent that runs a bulk docker command can bring down the entire dev platform for hours.

## Current Behavior

No prompt template, no CLAUDE.md, and no skill system-instruction file explicitly forbids docker-container-management commands. There are scattered references like CLAUDE.md's "NEVER use agent-browser for browser automation" bullet, but nothing about docker.

Concrete evidence gap: F-00058's S01 prompt (the one that was running during the 2026-04-22 incident) contains `## Subagent Result Contract`, `## TDD Requirement`, lifecycle commands — nothing that would stop the agent from typing `docker kill`. Whether or not that specific agent caused the incident, the prompt surface was unprotected.

Existing related rules we'll follow the *style* of:

- Root `CLAUDE.md` → **Critical Rules** bulleted list: high-visibility "NEVER" statements with rationale.
- `tests/CLAUDE.md` → scoped rules for the test layer with explicit "MUST / NEVER" phrasing.
- Agent-prompt templates → a standard "Project Conventions" section that references `CLAUDE.md` but doesn't re-state all rules.

## Desired Behavior

1. A new file `docs/IW_AI_Core_Agent_Constraints.md` is the single authoritative policy document. It contains the Docker rule and is structured so future shared-resource rules (e.g. "never modify `/opt/`", "never run `rm -rf` outside your worktree") can be added with minimal restructuring.

2. Every agent-prompt template in `ai-dev/templates/` (11 files) has a new `## ⛔ Docker is off-limits` section containing the exact marker text (see §Rule Text below) so agents reading any step prompt see the rule.

3. The `iw-workflow` skill's `SKILL.md` has the rule embedded in its system-level guidance so the orchestrator enforces it at the meta-layer before any step begins.

4. Every CLAUDE.md in the repo (root, `orch/`, `dashboard/`, `executor/`, `tests/`) gains a Critical Rules bullet: `**NEVER** run docker kill / docker stop / docker rm / docker compose up|down|restart / docker system prune ... (full list in docs/IW_AI_Core_Agent_Constraints.md).`

5. `docs/IW_AI_Core_DB_Setup.md` (created in CR-00015) cross-references the constraints doc as "Related policy".

6. A grep-based integration test (`tests/integration/test_agent_constraints_coverage.py`) asserts every file in the enforcement set contains the unique marker phrase `⛔ Docker is off-limits`. If any file drops the marker, the test fails and the CI gate blocks the merge.

7. Agents that attempt a prohibited command should raise a blocker in their result contract instead of executing it. (We cannot technically block the command — we can only make the prompt unambiguous about the expectation.)

## Rule Text (verbatim — must appear in every prompt template)

```
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
```

The **unique marker phrase** used by the grep sanity test is `⛔ Docker is off-limits` (including the emoji).

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|---|---|---|
| `docs/IW_AI_Core_Agent_Constraints.md` | Does not exist | Authoritative policy doc |
| `ai-dev/templates/*.md` (11 files) | No docker rule | Each has `## ⛔ Docker is off-limits` section |
| `.claude/skills/iw-workflow/SKILL.md` | No docker rule | Embedded at system-instruction level |
| `CLAUDE.md` (root) | No docker rule | Critical Rules bullet + link to policy doc |
| `orch/CLAUDE.md` | No docker rule | Critical Rules bullet + link |
| `dashboard/CLAUDE.md` | No docker rule | Critical Rules bullet + link |
| `executor/CLAUDE.md` | No docker rule | Critical Rules bullet + link |
| `tests/CLAUDE.md` | No docker rule | Critical Rules bullet + link + explicit testcontainer exception note |
| `docs/IW_AI_Core_DB_Setup.md` (from CR-00015) | Exists | Cross-reference to new policy doc |
| `tests/integration/test_agent_constraints_coverage.py` | Does not exist | Grep sanity test |

### Breaking Changes

- **None mechanically.** The daemon, dashboard, tests, and DB all continue to work exactly as before. No code paths change.
- **Behavior change for agents**: any future agent prompt that implicitly assumed docker management is allowed will now explicitly know it is not. If any existing open work item (e.g. F-00058) has a step prompt that runs `docker compose up -d db`, that prompt will need an update when it re-runs — but that was always the intent of the safe bootstrap path.

### Data Migration

- **None.** Documentation/prompt text only.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | template-impl | Create `docs/IW_AI_Core_Agent_Constraints.md`. Add the rule section to every file in `ai-dev/templates/` (11 files). Embed in `.claude/skills/iw-workflow/SKILL.md` system-instruction area. | — |
| S02 | code-review-impl | Review S01 | — |
| S03 | template-impl | Add Critical Rules bullet to all 5 CLAUDE.md files (root, orch/, dashboard/, executor/, tests/). Cross-reference from `docs/IW_AI_Core_DB_Setup.md`. Grep-audit for any stray references that could contradict. | — |
| S04 | code-review-impl | Review S03 | — |
| S05 | tests-impl | `tests/integration/test_agent_constraints_coverage.py` — asserts the marker phrase appears in every file of the enforcement set. Mutation-tested (temporarily remove marker from one file → test must fail). | — |
| S06 | code-review-impl | Review S05 | — |
| S07 | code-review-final-impl | Global: rule text identical across all touch-points; policy doc is primary; all links resolve; grep test passes and correctly fails on mutation; sibling-repo propagation list documented for follow-up. | — |
| S08 | qv-gate (lint) | `make lint` | — |
| S09 | qv-gate (format) | `uv run ruff format --check .` | — |
| S10 | qv-gate (typecheck) | `uv run mypy orch/ dashboard/` | — |
| S11 | qv-gate (unit-tests) | `make test-unit` | — |
| S12 | qv-gate (integration-tests) | `make test-integration` | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: N/A

### API Changes

None.

### Frontend Changes

None.

## File Manifest

All files for this work item live under `ai-dev/active/CR-00016/`:

| File | Type | Purpose |
|---|---|---|
| `CR-00016_CR_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/CR-00016_S01_Template_prompt.md` | Prompt | Policy doc + prompt templates + iw-workflow |
| `prompts/CR-00016_S02_CodeReview_prompt.md` | Prompt | Review S01 |
| `prompts/CR-00016_S03_Template_prompt.md` | Prompt | CLAUDE.md files + cross-reference |
| `prompts/CR-00016_S04_CodeReview_prompt.md` | Prompt | Review S03 |
| `prompts/CR-00016_S05_Tests_prompt.md` | Prompt | Grep sanity test |
| `prompts/CR-00016_S06_CodeReview_prompt.md` | Prompt | Review S05 |
| `prompts/CR-00016_S07_CodeReview_Final_prompt.md` | Prompt | Global review |

## Acceptance Criteria

### AC1: Policy doc exists and is authoritative

```
Given the branch has been merged
When a reader opens docs/IW_AI_Core_Agent_Constraints.md
Then the file exists and contains the Docker rule as its first major section
 And the structure supports adding future rules without restructuring
```

### AC2: Every prompt template contains the marker

```
Given the enforcement set {ai-dev/templates/*.md}
When the marker phrase "⛔ Docker is off-limits" is grep'd
Then every file in the set contains at least one match
 And the rule text within each file matches the canonical text verbatim
```

### AC3: Every CLAUDE.md contains the rule bullet

```
Given the enforcement set {CLAUDE.md, orch/CLAUDE.md, dashboard/CLAUDE.md,
                           executor/CLAUDE.md, tests/CLAUDE.md}
When each file is opened
Then each has a Critical Rules bullet containing "docker" and a link to
     docs/IW_AI_Core_Agent_Constraints.md
```

### AC4: iw-workflow skill embeds the rule

```
Given .claude/skills/iw-workflow/SKILL.md
When the file is opened
Then it contains the Docker rule or a verbatim quote of it in its
     system-instruction guidance
 And the orchestrator, when enumerating constraints for any step, surfaces it
```

### AC5: Grep sanity test catches drift

```
Given the integration test test_agent_constraints_coverage exists
When the test runs
Then it passes with the current state
When any single file in the enforcement set has its marker phrase removed
Then the test fails with a clear message naming the offending file
```

### AC6: No regressions

```
Given this CR is applied
When make check is executed
Then CR-00014's identity check is still green
 And CR-00015's compose-split tests are still green
 And no other test regresses
```

## Rollback Plan

- **Database**: N/A.
- **Code**: Revert the squash-merge. Prompt templates and CLAUDE.md files return to their prior content. Immediate rollback; no dependencies.
- **Data**: No data affected.
- **Environment**: None.

## Dependencies

- **Depends on**: **CR-00015** — this CR's docs link to `docs/IW_AI_Core_DB_Setup.md` which is created by CR-00015. Must be merged first.
- **Blocks**: The daemon-only-migration CR (next in the sequence) benefits from this, but is not strictly blocked.

## TDD Approach

- **Unit tests**: None. This CR is documentation-heavy.
- **Integration tests**: One new test in `tests/integration/test_agent_constraints_coverage.py` that validates the marker phrase across the enforcement set. Mutation test in the S05 verification: temporarily strip the marker from one file, run the test, confirm it fails with a file-named error; restore the marker.
- **Updated tests**: Any existing agent-prompt rendering test (if any) should still pass — the rule is added, not replacing existing content.

## Notes

- **Sibling-repo propagation**: Per the user's memory note, skill / prompt-template changes must be replicated to IW-AI-DEV and InnoForge. **That replication is OUT OF SCOPE for this CR** — the final-review step (S07) documents the exact file list for a manual or scripted sync afterwards.
- **The rule is a contract, not a sandbox**: we cannot prevent an agent from calling docker — we can only make the instruction unambiguous. Real enforcement would require a tool-use allow-list (out of scope; flagged as future-work in the notes).
- **Emoji in the marker phrase** (⛔): kept deliberately. It's visually distinctive, hard to fat-finger into another phrase, and doesn't conflict with any existing section header in the repo.
- **`iw-workflow` SKILL.md**: this is what the orchestrator itself reads. Embedding the rule there means the orchestrator surface (before any step prompt is loaded) already carries the constraint. Check current SKILL.md structure and add the rule in the "Constraints" or equivalent section.
- **`.claude/skills/` vs `skills/`**: the repo has both locations. `.claude/skills/` is the active copy that Claude/agents see; `skills/` is the master copy that gets synced. S01 touches `.claude/skills/iw-workflow/SKILL.md`; if `skills/iw-workflow/` also exists, update it in the same step so sync stays clean.

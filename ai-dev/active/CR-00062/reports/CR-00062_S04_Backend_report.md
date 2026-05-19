# CR-00062 S04 — Backend Implementation Report

**Step**: S04 — Add Pi master agent tree + extend sync engine + extend CLI
**Agent**: backend-impl
**Completion**: complete

## Summary

Created the master `agents/pi/` directory (30 .md files mirroring `agents/claude/`),
extended `AgentSyncResult` with a `pi_agents_synced` counter, wired a third
`_sync_directory()` call into `sync_agents_and_commands()` that copies to
`<project>/.pi/agents/`, and extended `iw sync-agents`'s JSON and human-readable
output (with adjusted total). No projects switched to `cli_tool = "pi"` —
`projects.toml` is unchanged as required.

## Files Changed

### Created — master Pi agent tree (`agents/pi/`, 30 files)

Every `.md` filename in `agents/claude/` has a peer in `agents/pi/`:

```
api-impl.md, api-review.md, backend-impl.md, backend-review.md, batch-planner.md,
code-review-final-impl.md, code-review-final-review.md,
code-review-fix-final-impl.md, code-review-fix-final-review.md,
code-review-fix-impl.md, code-review-fix-review.md,
code-review-impl.md, code-review-review.md,
database-impl.md, database-review.md,
deep-research.md, design-reviewer.md,
frontend-impl.md, frontend-review.md,
orchestrator.md,
pipeline-impl.md, pipeline-review.md,
quality-fix-impl.md, quality-validation-impl.md,
qv-browser.md, qv-gate.md,
template-impl.md, template-review.md,
tests-impl.md, tests-review.md
```

(Note: the prompt referenced 31 files; the live `agents/claude/` master tree
currently contains 30 — verified via `ls agents/claude/*.md | wc -l`. The Pi
tree was built to exact parity with the master tree, which is what
**AC3** asserts.)

### Modified

- `orch/skills/sync_agents.py` — added `pi_agents_synced: int = 0` after
  `claude_agents_synced`; added a third `_sync_directory(...)` call between
  the Claude and OpenCode calls; expanded the docstring to mention the new
  copy path.
- `orch/cli/skills_commands.py` (`sync_agents_cmd`) — added `"pi_agents"` to
  the JSON payload, added the `Pi agents: N` line to human output, included
  `result.pi_agents_synced` in the `Total: ...` accumulator.

### Created — unit test

- `tests/unit/test_sync_agents_pi.py` — three tests covering:
  - `test_sync_creates_pi_agents_directory` — RED test: asserts
    `pi_agents_synced` on `AgentSyncResult` (started the TDD cycle).
  - `test_pi_agents_synced_default_zero` — invariant on the dataclass default.
  - `test_sync_creates_target_when_missing` — verifies the `.pi/agents/`
    directory is created when absent (uses the existing `mkdir(parents=True,
    exist_ok=True)` in `_sync_directory()`).

## TDD Evidence

Pre-implementation RED:

```
tests/unit/test_sync_agents_pi.py::test_sync_creates_pi_agents_directory FAILED
>       assert result.pi_agents_synced == 2
E       AttributeError: 'AgentSyncResult' object has no attribute 'pi_agents_synced'. Did you mean: 'claude_agents_synced'?
```

Post-implementation GREEN: `3 passed in 0.08s`.

## Frontmatter Translation

All 30 Claude agent files carry Claude-specific frontmatter fields not consumed
by Pi:

- `model: opus | sonnet` — Claude-specific model identifier
- `maxTurns: N` — Claude-specific turn cap
- `disallowedTools: [...]` — Claude-specific
- `permissionMode: default | acceptEdits` — Claude-specific

These four fields were **stripped** from every Pi copy and replaced with one
`<!-- pi-port: stripped model, maxTurns, disallowedTools, permissionMode —
Claude-specific frontmatter not consumed by Pi -->` comment placed immediately
below the closing `---` of the frontmatter (as the prompt's option (b)
prescribes). The portable fields — `name`, `description`, `tools`, and
`skills` (orchestrator.md only) — pass through verbatim. No files were
stubbed; every body is a runtime-agnostic Markdown body that references
skills by name and is therefore reusable as-is.

## Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ok — 774 files already formatted |
| `make typecheck` | ok — 257 source files, no issues |
| `make lint` | ok — All checks passed |
| `uv run pytest tests/unit/test_sync_agents_pi.py -v` | 3 passed |

## Observations

- `_sync_directory()` already handles missing-target creation via
  `target_dir.mkdir(parents=True, exist_ok=True)`, so the new Pi path
  required no helper changes — only one more `_sync_directory(...)` call.
- The Pi master tree currently has exactly the same filename set as
  `agents/claude/`, satisfying AC3 (filename-set equality, not byte
  equality — byte equality is impossible given the legitimate frontmatter
  translation).
- `projects.toml` left untouched per *Notes* / GO-NO-GO decision in the
  design doc — no project is moved onto `cli_tool = "pi"` in this CR.

## Blockers

None.

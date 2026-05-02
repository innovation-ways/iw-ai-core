---
name: iw-item-analyze
version: "1.1.0"
description: >
  Post-execution workflow analyzer. Reads the logs, prompts, reports, and DB telemetry
  for a single completed work item (Feature / Incident / CR) and surfaces recurring
  process issues — agent thrashing, repeated tool failures, redundant env/install steps,
  prompt gaps, manifest issues. Proposes concrete, evidence-anchored improvements to
  CLAUDE.md, AGENTS.md, prompt templates, workflow manifests, skills, or environment.
  NEVER reviews the generated code itself. NEVER edits any file — reports only.
  Triggers on "analyze item", "item postmortem", "what went wrong with X", "/iw-item-analyze".
compatibility: opencode
---

# IW Item Analyze

Analyze the execution history of work item **$IW_ITEM_ID** and propose concrete process improvements.

**Strict scope:** look only at *how the agents behaved during execution* — tool failures, retries, fix-cycles, repeated env setup, error patterns, prompt gaps. **Never review the generated code.** **Never edit any file.** This skill reports only.

---

## Phase 0 — Resolve the item and check sources

1. Read the item ID from `$IW_ITEM_ID`. If unset, fall back to the first positional argument or stop with an error — the daemon launches this step with the env var set.

2. **Check DB availability** (controls whether we use DB-first or file-only mode):
   ```bash
   uv run iw db-identity check >/dev/null 2>&1 && echo "DB:UP" || echo "DB:DOWN"
   ```

3. **Locate the item** in this priority:
   - **Active**: `ai-dev/active/<ID>/` exists → use directly. Worktree should be at `.worktrees/<ID>/` (raw logs live here under `ai-dev/logs/`).
   - **Archived**: `ai-dev/archives/<project>/<ID>.tar.zst` exists → extract to a temp dir:
     ```bash
     TMP=$(mktemp -d) && tar --use-compress-program=unzstd -xf ai-dev/archives/iw-ai-core/<ID>.tar.zst -C "$TMP"
     ```
     Note: archived tarballs contain prompts + reports + execution_report only — **no raw run logs**. Signal will be weaker; the DB (if up) becomes the primary source.
   - **Neither** → stop and tell the user the item cannot be found.

4. **Pull the high-level step list** (works in both modes):
   ```bash
   uv run iw item-status <ID> --json
   ```

5. Build an inventory of available sources per step (active example):
   - Prompt: `ai-dev/active/<ID>/prompts/<ID>_<STEP>_*_prompt.md`
   - Run logs: `.worktrees/<ID>/ai-dev/logs/<ID>_<STEP>_run*.log`
   - Fix-cycle logs: `.worktrees/<ID>/ai-dev/logs/<ID>_<STEP>_fix*.log`
   - Fix-cycle prompt: `ai-dev/active/<ID>/fix-cycles/<ID>_<STEP>_FIX_cycle*_prompt.md` (also in archive tarball)
   - Report: `ai-dev/work/<ID>/reports/<ID>_<STEP>_*_report.md` (treat as secondary — agent self-report)
   - Manifest: `ai-dev/active/<ID>/workflow-manifest.json`

---

## Phase 0.5 — Inventory log sizes

Run: `ls -la .worktrees/<ID>/ai-dev/logs/ | awk '{print $5, $9}`

For any log > 1 MB, plan to use:
  - `tail -500 <log>`      (last lines, where errors usually live)
  - `head -200 <log>`      (initial setup / env)
  - `grep -nE 'Error|error:|failed|Permission denied|command not found' <log>`

Only read the full file when a specific match in grep needs full context.
Record what you skipped in `coverage_notes`.

---

## Phase 1 — Per-step pass (one structured analysis per step)

For each step in the manifest, produce an internal scratch record. **Do not show the user yet.** Each record contains:

```
step: <STEP_ID>  agent: <agent>  status: <status>
runs: <N>   fix_cycles: <N>   total_duration: <s>
findings:
  - { id, type, severity, evidence: "<file>:<line> — '<short quote>'", note }
```

Compute these signals from the run logs (or `log_content` from DB):

### A. Thrash / retry signal
- `runs > 1` or `fix_cycles >= 1` → flag potential thrash. Severity scales with count.
- Same error string repeating ≥3 times in one log → "stuck loop", severity HIGH.

### B. Tool/CLI failure traces
- Lines matching `Error:`, `error:`, `failed`, `command not found`, `Permission denied`, `refused`.
- Common patterns to extract:
  - `iw <subcommand>` failed and was retried with different args → CLI affordance gap.
  - Missing env vars (`IW_CORE_*`, `VIRTUAL_ENV` mismatches) → environment gap.
  - `uv run` / `pytest` / `alembic` errors specifically about config or fixtures.

### C. Setup / install commands during steps
Search for: `uv add`, `uv pip install`, `pip install`, `apt-get install`, `apt install`, `npm i`, `npm install`, `pnpm add`, `cargo add`, `playwright install`, `gem install`.

Each match in a step log = candidate "move to base env" finding (per your example: don't reinstall pyright in every worktree).

### D. Prompt-vs-log gap
For any error pattern flagged in B/C, **read the prompt for that step** and check whether the failing knowledge was already in the prompt. If the agent failed because the prompt didn't tell it how to use a tool / which env var to set / which command to run → classify as `prompt-gap` finding.

### E. Manifest / workflow signals
- Any step that needed multiple runs but had no fix cycle → check whether the step type should automatically trigger a fix cycle.
- A step that ran very long (`duration_secs` > 2× peer steps of the same agent type) → flag potential timeout/structure issue.
- QV-gate failures that immediately re-passed on retry → flaky gate or premature gate.

### F. Convention / CLAUDE.md drift
- If the agent did something the project's CLAUDE.md explicitly forbids (e.g., `docker compose up`, `npx playwright install`, `agent-browser`), classify as `convention` finding even if the agent recovered. The fact that it tried means the prompt/agent context didn't surface the rule loudly enough.

### Severity rubric

| Severity | Meaning |
|----------|---------|
| HIGH | Step blocked, required human intervention, or wasted ≥5 min of agent time |
| MED  | Step recovered but with clear thrash (≥2 retries on same error) |
| LOW  | Single transient error or minor inefficiency |

### Classification (assign exactly one)

| Class | Owner / target |
|-------|----------------|
| `agent`       | Agent reasoning issue — usually no fix possible at platform level |
| `platform`    | iw CLI, daemon, or executor behavior — fix in `orch/` or `executor/` |
| `prompt`      | Prompt missing instructions — fix in `templates/`, `ai-dev/templates/`, or design-doc generators |
| `environment` | Tool/dep should be pre-installed in main repo, not per-worktree |
| `design`      | Design document missing context the agent needed — fix design-doc template |
| `convention`  | CLAUDE.md / AGENTS.md rule needs to be louder — fix project guidance |

**Target field defaults:**
- For `class in {prompt, design, convention, agent, platform}` → default `target: "iw-ai-core"`
- For `class == environment` → default `target: "project"` when the suggested fix is a dependency/config in the project root; otherwise `"iw-ai-core"` if it's a dependency/config that belongs in iw-ai-core

---

## Phase 2 — Synthesis (cross-step promotion)

A finding is **promoted to the final report** only if:

- It appears in **≥2 steps**, OR
- It is **severity=HIGH** in at least 1 step.

Cluster findings by `(class, target file)`. Merge near-duplicates. Drop singletons that don't clear the bar.

**Hard cap: 7 findings.** If more clear the bar, keep the 7 highest-impact and add a one-line "N lower-priority findings omitted; ask to see them" footer.

**Frequency tag** on each promoted finding:
- `recurring` — seen in 3+ steps
- `systemic` — seen in 2 steps OR HIGH severity once
- `one-off` — only used internally; never promoted

---

## Phase 3 — Output (two files written)

Write two files:

- `ai-dev/work/<ID>/reports/<ID>_self_assess_report.md` — the human-readable narrative (structure described below).
- `ai-dev/work/<ID>/reports/<ID>_self_assess_findings.json` — structured JSON (schema described below).

If **no findings clear the bar**, the report MD contains:

```
### Item Analysis: <ID>

No actionable patterns detected. Workflow ran cleanly across all steps.

Steps analyzed: <N>   Total retries: <N>   Total fix-cycles: <N>
```

And the JSON has `findings: []` plus a `coverage_notes` field.

Otherwise, write the report MD:

```
### Item Analysis: <ID>

Bottom line: <one sentence — the single most useful change to make>

Steps analyzed: <N>   Steps with retries: <N>   Total fix-cycles: <N>   DB signal: <yes|no>

[1] <Title>
    Severity: <HIGH|MED>   Class: <agent|platform|prompt|environment|design|convention>   Frequency: <recurring|systemic>
    Evidence:
      - <file>:<line> — "<short quote>"
      - <file>:<line> — "<short quote>"  (also seen in S03, S05)
    Recommendation: <concrete change>
    Target: <exact file path to edit, e.g. CLAUDE.md, ai-dev/templates/Issue_Design_Template.md, skills/iw-execute/SKILL.md>
    Pros: <1–2 short lines>
    Cons: <1–2 short lines>
    If we don't: <do-nothing cost — what continues to break>
    Effort: <S | M | L>   (~<lines/files touched>)

[2] ...
```

And the findings JSON:

```json
{
  "item_id": "<ID>",
  "bottom_line": "Single sentence — the most useful change to make.",
  "coverage_notes": "Sampled tail (last 500 lines) of S05 log (12 MB); read S01-S04 logs in full. DB telemetry: full.",
  "findings": [
    {
      "severity": "HIGH",
      "class": "environment",
      "target": "iw-ai-core",
      "title": "Per-worktree pyright reinstall on every Tests step",
      "recommendation": "Add pyright to main repo's dev dependencies",
      "evidence": [".worktrees/<ID>/ai-dev/logs/<ID>_S05_run1.log:142 — 'Installing pyright...'"],
      "effort": "S",
      "paste_prompt": "/iw-new-cr Add pyright to main repo's dev dependencies so worktrees inherit it; analyzed in <ID> (see ai-dev/active/<ID>/reports/<ID>_self_assess_report.md). Target file: pyproject.toml. Effort: S."
    }
  ]
}
```

Bottom-line rules:
- Lead with the single change with the best ratio of (impact × frequency) / effort.
- It's OK for "Bottom line" to disagree with [1] if [1] is high-impact-high-effort and a quick win exists at [2].

---

## Constraints

- **NEVER** review the generated code or comment on code quality.
- **NEVER** edit any file. This skill is read-only — output goes to two files.
- **NEVER** invent findings to look useful. If the item ran cleanly, say so.
- **NEVER** rely on the agent self-report (`*_report.md`) as primary evidence. Self-reports are biased; cite raw logs and DB telemetry.
- **NEVER** propose code refactors as findings.
- **MUST** anchor every promoted finding to at least one `<file>:<line>` quote.
- **MUST** check `iw db-identity check` before attempting DB queries.
- **MUST** handle archived items via tarball extraction to `mktemp -d`.
- **MUST** clean up the temp dir at the end (`rm -rf "$TMP"`) when extracting an archive.
- Hard cap: **7 findings** in the final output.
- All recommendations must include a `Target` file path that the user could open and edit.
- **MUST** write the two output files atomically (write to a tempfile then rename, OR write directly if a partial write is acceptable for failures — soft-step semantics tolerate partial output).
- **MUST** populate `target` with exactly `"iw-ai-core"` or `"project"` for every finding. Default to `"iw-ai-core"` for `class in {prompt, design, convention, agent, platform}`. Default to `"project"` for `class == environment` when the suggested fix is a dependency/config in the project root rather than in iw-ai-core.
- **MUST** populate `paste_prompt` with a one-line, copy-pasteable prompt: `/iw-new-cr <one-sentence description>` or `/iw-new-incident <one-sentence description>`, plus a short context tail referencing this analysis report.
- **MUST** include `coverage_notes` describing what was sampled vs read in full. Use selective reads (`tail -500`, `head -200`, `grep -E '^Error|^error|failed'`) for any log file > 1 MB. Spelunk fully only when a specific anomaly demands it.
- **MUST NOT** write any files outside `ai-dev/work/<ID>/reports/`. Read-only with respect to the rest of the worktree.
- The previous "no findings" output also writes the report file (with a one-line "no actionable patterns" body) AND a findings JSON with `findings: []`.

---

## Examples of well-formed findings

**Good (environment class, recurring):**
```
[1] Per-worktree pyright reinstall on every Tests step
    Severity: MED   Class: environment   Frequency: recurring
    Evidence:
      - .worktrees/I-00041/ai-dev/logs/I-00041_S05_run1.log:142 — "Installing pyright..."
      - .worktrees/I-00041/ai-dev/logs/I-00041_S06_run1.log:88  — "Installing pyright..."  (also seen in S09, S12)
    Recommendation: Add pyright to the main repo's dev dependencies (`uv add --dev pyright`) so worktrees inherit it.
    Target: pyproject.toml
    Pros: ~30s saved per Tests step; deterministic agent behavior.
    Cons: One-time bump in main lockfile; minor disk overhead.
    If we don't: Every Tests/quality step continues to spend ~30s reinstalling pyright; agent occasionally
                 fails the install and retries, costing more.
    Effort: S (~2 lines, 1 file)
```

**Good (convention class, systemic):**
```
[2] Agent attempted `docker compose up -d db` despite CLAUDE.md prohibition
    Severity: HIGH   Class: convention   Frequency: systemic
    Evidence:
      - .worktrees/I-00040/ai-dev/logs/I-00040_S01_run1.log:312 — "$ docker compose up -d db"
    Recommendation: Move the docker prohibition from a bullet inside "Critical Rules" to a top-of-file
                    boxed warning in CLAUDE.md, AND mirror in AGENTS.md. Reference the 2026-04-22 incident
                    inline so the agent sees the cost.
    Target: CLAUDE.md, AGENTS.md
    Pros: One of the most expensive past incidents; cheap to surface louder.
    Cons: Slightly noisier top of CLAUDE.md.
    If we don't: Risk of repeating a data-loss event the project has already paid for once.
    Effort: S (~10 lines, 2 files)
```

**Bad (would be rejected):**
```
[X] Backend code in S01 could be simpler if we extracted a helper.
```
→ Out of scope. This skill never reviews generated code.

```
[X] Agent should think more carefully before retrying.
```
→ No evidence anchor; no actionable target.
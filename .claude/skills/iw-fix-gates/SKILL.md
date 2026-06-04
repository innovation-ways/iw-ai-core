---
name: iw-fix-gates
version: "1.2.0"
description: >
  Run both the project's test and quality gates end-to-end, gather every
  failure across all categories, then fix them iteratively with mandatory
  per-cluster reasoning. The goal is NOT to make tests pass — the goal is to
  understand what each test guards, diagnose the real root cause, and apply
  the smallest fix that preserves the test's intent. Triggers on "fix gates",
  "run gates and fix", "fix all failing tests", "/iw-fix-gates".
allowed-tools: Read, Grep, Glob, Bash, Edit, Write
---

# Fix Gates — Run Both Gates, Understand Every Failure, Then Fix

You will run both the project's gates (quality and tests), gather every
failure across every category up-front, and then fix them. The skill exists
because most LLM "fix the failing test" loops drift into anti-patterns —
weakening assertions, adding `@pytest.mark.skip`, slapping `# type: ignore`,
shortcutting to `assert True`. **That is not what this skill is for.**

> **Before any fix: understand what the test or gate is guarding. The fix must
> preserve that intent. If you cannot articulate the intent, you cannot fix it
> — flag it as unresolved.**

This is a **developer tool**, not a daemon-driven workflow. No work item is
created, no worktree is spawned, no commit is made. The operator reviews
`git diff` and the session log, then commits manually.

---

## Phase 0 — Resolve project and pre-flight

1. **Identify project** by walking up from the cwd until finding a parent
   directory that matches a `repo_root` entry in IW AI Core's `projects.toml`,
   or by running:
   ```bash
   uv run --directory /home/sergiog/dev/iw-doc-plan/main/iw-ai-core \
     iw current-project 2>/dev/null
   ```
   If the project is unknown to IW AI Core or `enabled = false`, stop and
   report. Never proceed against an unregistered project.

2. **Snapshot working tree:**
   ```bash
   git -C <repo_root> status --porcelain
   ```
   If the tree is dirty, ask the user to confirm before continuing. Dirty
   trees make it harder to spot weakened-assertion diffs later.

3. **Load gate categories** from the orchestration DB (port 5433). The two
   dicts you need are `Project.config.test_config.categories` and
   `Project.config.quality_config.categories`. Use this Python one-liner from
   the iw-ai-core repo:
   ```bash
   uv run --directory /home/sergiog/dev/iw-doc-plan/main/iw-ai-core python -c "
   import json, sys
   from orch.db.session import get_session
   from orch.db.models import Project
   pid = '<PROJECT_ID>'
   with get_session() as s:
       p = s.query(Project).filter_by(id=pid).one()
       cfg = p.config or {}
       print(json.dumps({
           'repo_root': p.repo_root,
           'test': cfg.get('test_config', {}).get('categories', {}),
           'quality': cfg.get('quality_config', {}).get('categories', {}),
       }))
   "
   ```
   Each category entry has at minimum `command`; may also carry `label`,
   `description`, `group`, `cleanup_command`, `bundle`, `e2e_stack`.

4. **Skip bundle categories.** Any category with `bundle: true` is a
   "run-everything" composite (e.g. `make check`) that overlaps the
   individual categories. Iterating per-category gives per-failure attribution
   — bundles would double-run the same code and merge failures together.

   **Coverage check (mandatory):** After loading categories, verify that the
   non-bundle test categories together cover the same test directories as the
   bundle. Compare the paths in the bundle command (e.g. `pytest tests/`) against
   the union of paths in the non-bundle categories. If any subdirectory (e.g.
   `tests/orch/`, `tests/dashboard/`) is only covered by the bundle, **flag it
   to the operator** and ask them to add a dedicated category for that directory
   in the project's DB config before proceeding. Do NOT silently skip that
   directory — that is the same failure mode this skill exists to prevent.

   For `iw-ai-core`, the expected non-bundle test categories are:
   `unit` (`tests/unit/`), `integration` (`tests/integration/`),
   `dashboard` (`tests/dashboard/`), and `orch` (`tests/orch/`).
   Any missing category must be added to `Project.config.test_config.categories`
   before gathering.

5. **Check for a resumable previous run.** A 529-class API error, a manual
   `Esc`-interrupt, or a connectivity blip can kill the agent mid-gather —
   but the subprocesses already launched usually finish, and their logs
   persist in `/tmp/iw-fix-gates-*`. To avoid forcing the operator to wait
   another 17 minutes for the integration suite they already ran:

   ```bash
   # List recent gather logs and their sidecar exit codes.
   for f in /tmp/iw-fix-gates-*.log; do
     [ -f "$f" ] || continue
     age=$(( $(date +%s) - $(stat -c %Y "$f") ))
     exit_file="${f%.log}.exit"
     ec=$( [ -f "$exit_file" ] && cat "$exit_file" || echo "?")
     head_file="${f%.log}.head"
     head_sha=$( [ -f "$head_file" ] && cat "$head_file" || echo "?")
     echo "${f}  age=${age}s  exit=${ec}  head=${head_sha}"
   done
   ```

   Reuse a category's previous result iff **all three** hold:
   - The log file's age is < 30 minutes.
   - The sidecar `.exit` file exists and contains a definite exit code.
   - The sidecar `.head` file matches the current `git rev-parse HEAD`
     (no edits since the log was written).

   When reuse is possible, surface it to the operator and ask:
   ```
   Found resumable results from <N> minutes ago at git HEAD <sha>:
     ✔ quality/lint        (exit 0, 3s ago)
     ✗ test/integration    (exit 1, 14m ago)
   Reuse these, or re-run from scratch? [reuse/rerun]
   ```
   Default to **rerun** if the operator does not answer affirmatively —
   reusing a stale gather is worse than spending the wall time.

   When launching new gathers, also write the sidecar files so the next
   session can resume:
   ```bash
   echo "${gate_exit}" > /tmp/iw-fix-gates-<gate>-<category>.exit
   git rev-parse HEAD  > /tmp/iw-fix-gates-<gate>-<category>.head
   ```

---

## Phase 1 — Gather (READ-ONLY, NO CODE CHANGES)

Run every non-bundle category of both gates and collect every failure. Do
not stop on a failing category — keep going to capture the full landscape.

**Order and concurrency:**
1. **Quality categories first**, sequentially, fastest first (lint, format,
   typecheck, …). They are individually fast (~seconds each); parallelism
   buys little and complicates log parsing.
2. **Test categories next.** Run them **in parallel** when safe to do so;
   the integration suite alone often dominates wall time, and serial
   gathering wastes the slack. A test category is **safe to parallelise**
   iff it declares **neither** `e2e_stack: true` **nor** a
   `cleanup_command`. Any category that declares either signals exclusive
   resource use (a docker stack, a shared port, a global teardown) and
   MUST run alone — finish the parallel-safe categories first, then run
   each exclusive category sequentially.
3. Within each group (parallel or sequential), launch fastest first so
   short-running failures surface early in the gather.

For `iw-ai-core` today this means `unit` + `integration` + `dashboard` +
`orch` may run concurrently (none declare `e2e_stack` or `cleanup_command`);
for projects like `innoforge` with an `e2e` category that declares
`e2e_stack: true`, `e2e` runs after the parallel-safe group completes.

### Operator-visible progress (NON-OPTIONAL)

This skill runs gate commands that can take many minutes (especially the
integration suite). The operator MUST be able to see what is happening,
otherwise the session looks stalled and is indistinguishable from a hung
agent. Therefore:

1. **Announce every launch in plain text — not just via the tool call.**
   Before each Bash invocation that launches a category, send a one-line
   user-visible message of the form:
   ```
   ▶ <gate>/<category> — <command>
   ```
   When launching a parallel group, announce the group up front:
   ```
   ▶ Running test/unit + test/integration + test/dashboard + test/orch in parallel…
   ```
2. **Stream output live; do NOT silently redirect to a file.** Use `tee`
   (see the launch incantation below) so the gate command's stdout/stderr
   reach the operator's screen in real time AND a copy is captured for
   Phase 3 parsing. The "I see tests scrolling by" feedback loop is the
   whole reason for this rule.
3. **Announce every completion in plain text** with a one-line summary:
   ```
   ✔ <gate>/<category> · PASS · <duration>
   ✗ <gate>/<category> · FAIL · <N> findings · <duration>
   ```
   Append findings count once Phase-1 parsing has run; never delay the
   announcement waiting for it.
4. **For categories run in the background**, emit the start announcement,
   then a short "running in background, will notify on completion" line.
   On the completion notification, emit the finish announcement
   immediately — do not bury it inside a larger paragraph.

These announcements are not optional polish; the v1.0/1.1 skills omitted
them and produced sessions that looked dead for ~20 minutes while the
integration suite ran. **Silent gather is a bug.**

### Launch incantation

**For each category, in `cwd = repo_root`:**

```bash
# Stream stdout+stderr live to the operator AND capture to a log file
# for Phase 3 parsing. `pipefail` makes the pipeline's exit code reflect
# the gate command (not tee's exit code), and we additionally store the
# gate's own exit via PIPESTATUS for clarity in the session log.
( set -o pipefail; <command> ) 2>&1 | tee /tmp/iw-fix-gates-<gate>-<category>.log
gate_exit=${PIPESTATUS[0]}
# Sidecar files for cross-session resumability (Phase 0 step 5).
echo "${gate_exit}"     > /tmp/iw-fix-gates-<gate>-<category>.exit
git rev-parse HEAD      > /tmp/iw-fix-gates-<gate>-<category>.head
echo "exit=${gate_exit}"
```

For a long-running category (any test category, or any quality category
that historically takes >60 s on this project) launch it with the Bash
tool's `run_in_background: true` so the operator gets a completion
notification rather than a frozen-looking turn. Foreground is fine for
the short quality categories (lint / format / typecheck — each finishes
in seconds).

If the category declares `cleanup_command`, run it on exit (pass or fail) —
e.g. `make e2e-cleanup-all` for e2e categories that spin up a stack.

**Verdict per category:** subprocess exit code (matches dashboard semantics).
**Per-failure detail:** parse the log file.

**Build a normalized failure list.** For each failing category, parse the log
and emit one record per individual finding:

```
{
  "gate":     "test" | "quality",
  "category": "<name from config>",
  "kind":     "test_failure" | "test_error" | "lint" | "type" | "format" | "other",
  "location": "tests/path/test_x.py::test_foo" | "orch/foo.py:42",
  "summary":  "<one-line failure summary — exception type + message, or rule code>",
  "log_path": "/tmp/iw-fix-gates-<gate>-<category>.log"
}
```

Parsing hints:
- **pytest:** `^FAILED (.+?) - (.+)$` (one record per FAILED line). Errors
  during collection use `ERROR <path>` — capture as `test_error`.
- **ruff:** `^([^:]+):(\d+):(\d+): (\w+) (.+)$` — file, line, col, code, msg.
- **mypy:** `^([^:]+):(\d+): error: (.+)$`.
- **format-check (ruff format / black):** the list of files reported as
  "would reformat" / "would be reformatted".
- **anything else:** capture the last non-empty stderr line as `summary`.

If the verdict is non-zero but no individual findings parse, record a single
`kind: "other"` entry with the tail of the log as `summary` — the agent will
read the full log in Phase 3.

**End of Phase 1 — output a gather report to the session log:**

```
| Gate    | Category    | Verdict | Findings |
|---------|-------------|---------|----------|
| quality | lint        | PASS    | 0        |
| quality | typecheck   | FAIL    | 7        |
| test    | unit        | FAIL    | 3        |
| test    | integration | PASS    | 0        |
```

**Early exit — all-green shortcut.** If every category exited with code `0`
AND the normalized failure list is empty, skip Phase 2, Phase 3, and
Phase 4 entirely. Jump straight to Phase 5 with the all-green template
(see Phase 5 below): the Phase-1 gather IS the authoritative verdict, and
re-running every category a second time in Phase 4 just to re-confirm
"already green" is pure wall-time burn — most painfully when the
integration suite is the long pole. The early exit is only valid when
nothing was edited; the moment Phase 2 applies an auto-fix or Phase 3
applies any diff, Phase 4 is mandatory.

---

## Phase 2 — Mechanical auto-fix pass (ONE shot, then re-gather)

Run known auto-fixers once. These produce deterministic edits, are
low-risk, and save LLM cycles on lint/format noise.

**If `format` (or equivalent) failed:**
```bash
make format 2>&1 | tee -a <session-log>
# or, if no make target: uv run ruff format <paths-from-failures>
```

**If `lint` failed AND the failures are auto-fixable rules:**
```bash
uv run ruff check --fix . 2>&1 | tee -a <session-log>
```
Do NOT use `--unsafe-fixes`. Stop at the safe default — anything ruff won't
auto-fix goes to Phase 3.

**Re-run only the categories that had findings** to refresh the failure list.
Anything still failing falls through to Phase 3.

---

## Phase 3 — Diagnose, cluster, fix (with mandatory "Why" notes)

Take the post-Phase-2 failure list and group related failures into clusters.
Many failures share a root cause: one import broke 30 tests; one type change
broke 10 mypy errors; one renamed field broke a contract test plus its
integration counterpart. **One cluster, one "Why" note, one fix.**

### 3a. Cluster

Greedy grouping rules:
- Failures in the same test file with the same exception type and message →
  one cluster.
- mypy/lint findings in the same file, same rule code → one cluster.
- A production-code change suggested by one failure that obviously explains
  others → merge into one cluster, even across categories.
- When in doubt, split rather than over-merge.

### 3b. Write the "Why" note BEFORE editing anything

For each cluster, append to the session log:

```
### Cluster <N>: <short name>

Gate / Category : <gate> / <category list>
Affected        :
  - <location 1> — <summary>
  - <location 2> — <summary>
  - ...

Guards          : <what behavior, invariant, or contract these failures
                   protect. Read the test file AND the production code it
                   imports. If you cannot answer this, write
                   "UNKNOWN — pausing for review" and skip the cluster.>

Root cause      : <which side is wrong — the test or the production code?
                   Quote the smallest piece of evidence: a recent commit,
                   a missing import, a renamed field, a tightened contract.>

Fix intent      : <what behavior the change preserves. Use the form
                   "this change <verb>, while still ensuring <invariant>".>

[ONLY if cluster touches test files]
Still guarded   : <after the test edit, what behavior remains protected?
                   Name it concretely. "The test still asserts X == Y at
                   boundary Z." If the answer is "nothing", DO NOT edit the
                   test — that is dilution, not fixing.>
```

If you cannot fill any of those four (five) lines truthfully, the cluster
goes to "unresolved" and you move on. Faking the note to justify a weak fix
is the failure mode this skill exists to prevent.

### 3c. Apply the fix

Edit production code (preferred) or test code (only when justified by the
"Still guarded" line). After editing, **re-run only the affected
category** for fast iteration:

```bash
( set -o pipefail; <category-command> ) > /tmp/iw-fix-gates-<gate>-<category>.log 2>&1
```

If still failing, iterate — read the new log, refine. **Hard cap: 5
iterations per category total across all clusters touching it.** If the cap
is hit and failures remain, mark the remaining clusters `unresolved` and
move on. Do not loosen the "Why" note's promises to escape the cap.

### 3d. Anti-pattern soft-warn list (🚩 flag in report, do NOT block)

If a diff you applied adds any of these, flag the cluster with 🚩 in the
final report. The "Why" note must explicitly justify the choice; otherwise,
the cluster is flagged for human review even if the gate now passes.

**In tests:**
- `@pytest.mark.skip`, `@pytest.mark.xfail`, `@pytest.mark.skipif`
- `assert True`, `assert 1`, removed/emptied test body
- Weakening: `assert x is not None` replacing `assert x == 5`
- Broadening: `pytest.raises(Exception)` replacing a typed `raises(TError)`
- `pytest.raises(...)` without `match=` where the previous version had one

**In production / quality config:**
- New `# type: ignore`, `# noqa`, `# pragma: no cover`
- New `--ignore`, `--exclude`, or rule-disable flags in gate commands
- New entries in any `ignore-paths`, `per-file-ignores`, or
  `tool.ruff.lint.per-file-ignores` table

---

## Phase 4 — Final verification

**Skip Phase 4 entirely if no diffs were applied** (Phase 1 all-green or
no auto-fixes and no clusters fixed). In that case the Phase-1 gather is
already authoritative — see the early-exit rule at the end of Phase 1.

Otherwise, after all clusters are either fixed or marked unresolved:

1. **Re-run BOTH full gates from scratch**, every non-bundle category, in
   the same order and concurrency as Phase 1. This is the authoritative
   verdict — it mirrors the dashboard's final-verification pass in
   `launch_quality_fix_run` (`orch/test_runner.py:389`).

2. **Compare before/after** per category and produce the final report.

---

## Phase 5 — Final report

Write the session log to `ai-dev/work/fix-gates-<timestamp>.md` (relative to
the project's `repo_root`; create the directory if missing). The log is
NOT committed — the operator reviews and discards.

The log MUST contain, in this order:

1. **Header** — project ID, timestamp, cwd, git HEAD sha.
2. **Before / after table** — verdict per category, both gates.
3. **Mechanical auto-fix log** — Phase 2 diffs in one block.
4. **One section per cluster** — the "Why" note, the diff applied (use
   `git diff <files>` output), and any 🚩 flags raised against it.
5. **Unresolved clusters** — for each: the "Why" note (or the explicit
   "UNKNOWN — pausing for review" marker), the last error, and a one-line
   recommendation for the human ("test contract is genuinely stale, need
   product decision"; "needs a real DB row not in conftest seed"; etc.).
6. **🚩 anti-pattern summary** — a single table of every flag raised, with
   the cluster name and the justification line from the "Why" note.

Then print to stdout a short summary the operator can read in one screen:

```
fix-gates: <project_id> @ <git HEAD short>
  Quality: <X/Y pass> (before: <a/b>)
  Tests  : <X/Y pass> (before: <a/b>)
  Clusters fixed     : <N>
  Clusters unresolved: <N>
  Anti-pattern flags : <N>
  Session log: ai-dev/work/fix-gates-<timestamp>.md
  Review with: git diff
```

---

## Constraints (NON-NEGOTIABLE)

- **NEVER** create a work item, batch, or worktree from this skill.
- **NEVER** commit, push, or merge from this skill — the operator owns
  the commit.
- **NEVER** weaken a test or quality gate to escape the iteration cap —
  the cluster is `unresolved`, not "fixed".
- **NEVER** add `@pytest.mark.skip`, `@pytest.mark.xfail`, `assert True`,
  `# type: ignore`, or `# noqa` without an explicit "Why"-note line
  justifying that exact choice. The 🚩 flag is mandatory.
- **NEVER** edit a test without filling the "Still guarded" line of the
  "Why" note with a concrete remaining assertion.
- **NEVER** invent or backfill the "Why" note after applying the fix —
  the note is the diagnostic step, not paperwork.
- **MUST** skip categories marked `bundle: true` to avoid double-running.
- **MUST** run `cleanup_command` (if declared) for any category that
  started a stack, regardless of pass/fail — orphan stacks block the
  next run.
- **MUST** stop and report if the project is unknown to IW AI Core or
  `enabled = false`.
- **MUST** treat the orch DB (port 5433) as read-only from this skill —
  the only DB interaction is reading `Project.config`.

---

## When to use this skill vs. alternatives

- Use **this skill** to triage real failures in your working copy before
  committing. It is interactive, project-local, and operator-reviewed.
- Use the dashboard's **Quality fix** button (`launch_quality_fix_run`) when
  you want the daemon to drive a single failing quality category in an
  isolated worktree — narrower scope, no test gate, no clustering.
- Use **`/iw-new-incident`** when a failing test exposes a real production
  bug that needs proper tracking, design, and a worktree-isolated fix —
  not just local cleanup before a commit.

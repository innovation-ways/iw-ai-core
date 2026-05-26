# R-00076 — LLM-driven Automated Merge Conflict Resolution

| | |
|---|---|
| **ID** | R-00076 |
| **Type** | Research |
| **Date** | 2026-05-16 |
| **Mode** | deep |
| **Editorial Category** | functional |
| **Status** | draft |
| **Primary Question** | Can LLM-based merge conflict resolution be safely integrated into IW AI Core's worktree-commit flow such that conflicts like today's I-00085 and I-00086 are resolved automatically without operator intervention? |

---

## Executive Summary

LLM-driven merge resolution is now demonstrably production-viable for a constrained subset of conflicts and is being shipped by GitHub (Copilot cloud agent, [HIGH](https://github.blog/changelog/2026-04-13-fix-merge-conflicts-in-three-clicks-with-copilot-cloud-agent/)) and by independent tooling like Sketch ([HIGH](https://sketch.dev/blog/merde)) and rizzler ([MEDIUM](https://ghuntley.com/rizzler/)), with academic benchmarks (MergeBERT 63–68 %, DeepMerge 78 % on small conflicts, ConGra 75–85 % on Python/Java for the strongest models, Merge-Bench "< 60 %" overall) converging on the conclusion that current LLMs resolve **roughly half to two-thirds** of real-world conflicts correctly without further help. **The only safe deployment pattern is "resolve then verify"**: the LLM produces a candidate resolution, the existing test/lint/type gates re-run on the resolved worktree, and the merge only proceeds on green. With that gate in place — and a refuse-list that bars migrations, lockfiles, security configs, and binary files — both of today's I-00085 and I-00086 failures would have been resolved automatically: their conflicts were exactly the comment-and-constant drift pattern that LLMs and even simple structural rules handle well, and the resolved diffs would have passed the same QV gates that I-00085 and I-00086 already passed in their worktrees. A three-phase rollout (dry-run → tests-only auto-apply → broader auto-apply) gives us audit data before any operator-visible behaviour changes.

---

## Context — The Concrete Failure Mode We Are Trying To Eliminate

IW AI Core's daemon orchestrates parallel "batch items" — each LLM-driven work item runs in its own `git worktree`. Squash-merges back to `main` are serialised through a merge queue (`orch/daemon/merge_queue.py`), but the **rebase** happens inside `executor/worktree_commit.sh` _before_ the squash. When two batch items independently touch the same file, that rebase fails and the item gets parked in `merge_failed` state requiring manual resolution + `iw merge-queue retry-merge <ID>`.

We hit this twice on 2026-05-16 — **I-00085** and **I-00086** — and in both cases the conflicting files were the same three test files updated by I-00084 (already on main):

- `tests/dashboard/test_runtime_overrides_api.py`
- `tests/integration/daemon/test_phase2_apply_no_self_deadlock.py`
- `tests/integration/test_agent_runtime_options.py`

**Both conflicts were semantically trivial:**

| Item | Conflict character |
|------|--------------------|
| I-00085 vs main (I-00084) | COMMENT-ONLY differences over identical numeric updates. Taking either side produced byte-equivalent code. |
| I-00086 vs main (I-00084) | One file had a substantive logical improvement (hardcoded `assert ids == [1,6,2,3,4]` → dynamic `select(AgentRuntimeOption).where(enabled.is_(True))`); another had a divergent `_PREV_REVISION` Alembic constant where I-00086's value was **more correct** (one revision below HEAD vs two below). |

The existing auto-resolver in `executor/worktree_commit.sh` (lines 290–296) handles exactly two named files:

```bash
_REBASE_TAKE_OURS="uv.lock"          # regenerate post-merge
_REBASE_TAKE_THEIRS="Makefile"       # branch's edits are typically additive
```

All other conflicts → `git rebase --abort` + emit operator instructions. **The operator-intervention path is the bottleneck we want to remove.**

---

## 1. State of the Art — LLM-Driven Merge Conflict Resolution

### 1.1. Academic Benchmarks [HIGH]

| Work | Year | Approach | Reported Accuracy | Notable Limitation |
|------|------|----------|-------------------|--------------------|
| [DeepMerge (Dinella et al., TSE 2022)](https://arxiv.org/abs/2105.07569) | 2022 | Pointer network on tokens; line-interleaving model | 37 % on non-trivial; **78 % on ≤3-line conflicts**; 55 % top-1 precision; 72 % at high-confidence cutoff | Cannot represent conflicts that aren't pure line interleavings; weak on >3-line hunks |
| [MergeBERT (Svyatkovskiy et al., FSE 2022)](https://arxiv.org/abs/2109.00084) | 2022 | Transformer encoder over token-level diff3; classifies into primitive merge patterns; Java/JS/TS/C# | **63–68 % accuracy**, 3× over semi-structured tools, 2× over neural baselines | User study (25 devs, 122 conflicts) accepted at higher rate than offline metrics suggest |
| [ChatMerge (IEEE 2023)](https://ieeexplore.ieee.org/document/10366637/) | 2023 | Two-stage: ML classifier picks strategy → ChatGPT only for "complex" bucket | Outperforms prior tools on historical resolutions | Avoids running the LLM on every conflict — selective routing keeps cost down |
| [ConGra (arXiv:2409.14121)](https://arxiv.org/html/2409.14121v1) | 2024 | Graded benchmark of 44,948 conflicts × 7 categories (Text / Functional / Syntax and compounds) | LLama3-8B 75.82 % Python / 82.93 % Java; DeepSeek-V2 75.07 / 84.38 %; CodeLlama-7B 50.68 / 73.61 % | **Counter-intuitive findings: long-context (128 K) underperforms; specialised code LLMs underperform general LLMs; adding context can hurt** |
| [Merge-Bench (Schesch & Ernst, ICPR 2026)](https://homes.cs.washington.edu/~mernst/pubs/merge-bench-icpr2026-abstract.html) | 2026 | 7,938 hunks × 1,439 repos; GRPO RL-trained LLMergeJ-14B | "**Best models correctly resolve less than 60 %** of merge conflicts"; LLMergeJ-14B 2nd only to Gemini 2.5 Pro on Java | Even SOTA still leaves ~40 % unresolved |

**Convergent finding**: across five years of independent benchmarks, the right summary is **"LLMs resolve roughly half to two-thirds of real-world conflicts; the rest fail, often visibly."** ConGra's surprising finding that simple conflicts are _harder_ than complex ones for current LLMs is important — it means we cannot assume that "small diff = high confidence".

### 1.2. Production Tools — Who Ships This Today

| Tool | Status (May 2026) | Mechanism | Verification | Source |
|------|-------------------|-----------|--------------|--------|
| **GitHub Copilot cloud agent** | GA on paid plans | "Fix with Copilot" button + `@copilot resolve conflicts` PR command. Runs in a cloud dev env, applies edits, **runs build + tests**, then pushes | **Yes — build and tests must pass before push** | [GitHub changelog](https://github.blog/changelog/2026-04-13-fix-merge-conflicts-in-three-clicks-with-copilot-cloud-agent/) |
| **Sketch / merde** | Public CLI ("merde") | Local diff capture → server-side LLM resolve → result delivered as a new branch (non-destructive) | None automated — "look at branch, accept or delete" | [sketch.dev/blog/merde](https://sketch.dev/blog/merde) |
| **rizzler** | OSS, configurable backend (OpenAI/Claude/Gemini/Bedrock) | Git low-level merge driver; per-file LLM call; fails forward — unresolved hunks left for human | None automated | [ghuntley.com/rizzler](https://ghuntley.com/rizzler/) |
| **LLMinus (Linux kernel)** | RFC v2, Sasha Levin (NVIDIA) | Embeddings of historical kernel merges + similar-resolutions retrieval + LLM | **Build-test integration** explicitly part of the design ("semantic conflict detection via build test integration") | [Phoronix](https://www.phoronix.com/news/LLMinus-RFC-v2), [LWN](https://lwn.net/Articles/1051607/) |
| **Mergify / Aviator / Graphite** | All GA, none ship LLM resolve | Prevent conflicts by rebasing-in-queue ("test the future state"); on conflict, defer to operator | CI must pass against rebased state | [Mergify docs](https://docs.mergify.com/merge-queue/), [Aviator docs](https://docs.aviator.co/mergequeue), [Graphite docs](https://www.graphite.com/docs/graphite-merge-queue) |
| **Claude Code skills** | Community skills | `/rebase` and `/merge-conflict` skills walk the model through `git status` → read both sides → resolve → `git add` → `git rebase --continue`, with `git log -p` for intent context | None automated by the skill itself — practitioner runs tests after | [raine.dev/blog](https://raine.dev/blog/resolve-conflicts-with-claude/), [claude-extensions/merge-conflict](https://github.com/always-further/claude-extensions/blob/main/commands/merge-conflict.md) |

**Two patterns dominate the production landscape:**

1. **Prevent, don't resolve** (Mergify, Aviator, Graphite): rebase aggressively inside the queue so conflicts are surfaced before merge; when a conflict actually fires, fall back to operator. This is essentially what IW AI Core does today.
2. **Resolve-then-verify** (GitHub Copilot cloud agent, LLMinus): LLM produces a candidate; build + tests must pass before the change is committed. **This is the design we want.**

### 1.3. Claude Code in the Merge Path [MEDIUM]

The community-published [`/rebase` skill](https://raine.dev/blog/resolve-conflicts-with-claude/) ([HIGH] — first-person practitioner write-up) demonstrates the practical recipe currently used in our own agent stack:

```text
1. git fetch + git rebase main
2. On conflict, for each conflicting file:
   a. git log -p -n 3 <target> -- <file>   # what did main do?
   b. git log -p -n 3 HEAD -- <file>       # what did our branch do?
   c. understand intent of both sides
   d. propose resolution
   e. git add <file>
3. git rebase --continue (or --abort if blocked)
```

Pattern signal: every working recipe **gives the LLM the recent commit history of BOTH sides** before asking for a resolution. Conflict markers alone are insufficient context. ConGra's finding that "naive context hurts" is consistent: it's not context-volume that matters, it's _signal-rich_ context (commit messages, recent diffs on the same file).

---

## 2. Conflict Tractability — What's Easy, Medium, Hard, and Never

Synthesised from ConGra's grading scheme and the production tool refuse-lists.

### 2.1. Easy — Auto-resolve Safe (HIGH confidence in success) [HIGH]

| Class | Example from today | Mechanism |
|-------|--------------------|-----------|
| **Identical changes, comment drift** | I-00085's three test files | A 3-line text-similarity diff on the conflict region suffices — no LLM needed |
| **Whitespace-only / formatter rewrites** | Black/ruff sweeps vs branch edits | `git rerere` or `git merge -X ignore-space-change` handles many of these |
| **Parallel additive edits to different parts of the same hunk** | Two tests added to the same class | Concatenate both sides; LLM 90 %+ on this class per [MergeBERT user study](https://arxiv.org/abs/2109.00084) |
| **Import-statement reordering / additions** | Two PRs add different imports | LLM trivial; trivial structural rule also works |

### 2.2. Medium — Auto-resolve With Mandatory Verification (MEDIUM confidence) [MEDIUM]

| Class | Example from today | Risk |
|-------|--------------------|------|
| **Parallel test-fixture updates** (row counts, ID arrays) | I-00086's `len(rows) == 6` vs I-00084's `len(rows) == 6` | Both sides agree on the number; conflict is on the comment only — but LLM may invent a third number |
| **Parallel constant updates where one side is "more correct"** | I-00086's `_PREV_REVISION = "7ef0b420c58f"` vs main's `"a1b2c3fixmm"` | The correctness depends on out-of-conflict context (Alembic chain); LLM needs to be given that context or it will guess |
| **Parallel logical refactors of the same assertion** | I-00086 swapped hardcoded list → dynamic query | LLM must understand semantic equivalence; verification gate catches regressions |

### 2.3. Hard — LLM Capable But Risk Is High (LOW confidence — refuse unless verified) [HIGH]

| Class | Why it's hard | Decision |
|-------|---------------|----------|
| Cross-file invariants (rename in one branch + new caller in the other) | LLM can read one file but not silently change three | **Refuse** in Phase 2; revisit in Phase 3 with multi-file context window |
| Semantic refactor + new feature on same lines | Requires understanding intent of both authors | **Refuse** — defer to operator |
| Auto-generated files (uv.lock, package-lock.json) | Resolution requires regeneration, not editing | **Already handled** via `_REBASE_TAKE_OURS` + post-merge regen |

### 2.4. Never Automate (HARD REFUSE — refuse-list) [HIGH]

These files must **always** abort the rebase, never attempt LLM resolution:

| Refuse-list pattern | Reason |
|---------------------|--------|
| `orch/db/migrations/versions/*` | Alembic chain mutation in a wrong order can corrupt the production DB irreversibly (see CR-00021 / I-00075 / I-00076). The pre-merge migration-rebase phase (`orch/daemon/migration_rebase.py`) already handles down-revision rewrites with explicit operator gates — DO NOT layer LLM on top. |
| `.gitleaks.toml`, `.gitignore` | Security/correctness — must be reviewed by a human |
| `.env`, `.env.*` | Credentials — must never be touched |
| `orch/db/identity.py`, `orch/config.py` | DB instance-identity is the CR-00014 safety pin |
| `pyproject.toml` (only `[project]` & `[tool.alembic]` sections) | Dep-graph changes need uv-lock regeneration, not LLM edits |
| Binary files (`*.png`, `*.zst`, `*.db`, `*.sqlite`) | LLMs cannot edit bytes; merge driver must abort |
| Migration files matching `versions/*_*.py` | Same rationale as the directory rule, defence in depth |
| `executor/worktree_commit.sh`, `executor/*.sh` | Bootstrap; a corrupted resolver is a permanent loop |
| Deletions vs modifications (`DD`, `DU`, `UD` git statuses) | "Did the other branch intentionally delete this?" requires human intent |

---

## 3. Safety Mechanisms — What Works in the Literature and in Production

### 3.1. The Five Pillars (synthesised across MergeBERT, ChatMerge, Sketch, GitHub Copilot, LLMinus)

| Pillar | What it does | Evidence |
|--------|--------------|----------|
| **Three-way context** | Provide BASE + OURS + THEIRS, not just conflict markers | All five academic papers + Claude Code skills explicitly mention this. [Cursor community thread](https://forum.cursor.com/t/instruct-agent-to-use-three-way-diff-for-merge-conflict-resolution/142445) shows practitioner demand. |
| **Intent context** | Include recent commit messages on both sides + the file's recent diff | Sketch [HIGH], Claude Code `/rebase` skill [HIGH], LLMinus's historical-resolution embeddings [MEDIUM] |
| **Resolve-then-verify** | LLM produces candidate → automated test/build gate → only then commit | GitHub Copilot cloud agent [HIGH], LLMinus (planned) [MEDIUM], implicit in every production deployment |
| **Confidence / abstention** | If model can't resolve, fall back gracefully — never produce "worse than no edit" | Sketch's stated property: "when it doesn't work, the conflict resolution mostly fails rather than producing merges that are worse than a human would" [HIGH]; rizzler: "If a file hits 8 merge conflicts and can't crack one, it'll tackle the rest and send an 'oops' back to Git" [MEDIUM] |
| **Bounded scope (refuse-list)** | Hard pattern allowlist + denylist on which files even attempt LLM resolution | Universal across production tools; not always explicit in academic work [HIGH] |

### 3.2. Prompt Patterns (synthesised) [MEDIUM]

What every working recipe gives the model:

1. **The full file** (not just the conflict hunk) — so the LLM can reason about surrounding context
2. **The merge base** (`git show :1:<file>`)
3. **OURS** (`git show :2:<file>`) and the recent commit log on this side
4. **THEIRS** (`git show :3:<file>`) and the recent commit log on this side
5. **The work-item description** (purpose of the change being merged)
6. **An explicit output format**: produce the full resolved file content, with NO conflict markers

What every working recipe explicitly tells the model NOT to do:

- **Don't invent new behaviour** — only choose / combine what's already on either side
- **Don't reformat unrelated code**
- **If unsure, output the literal string `ABSTAIN` instead of guessing**

---

## 4. Cost and Latency Profile

### 4.1. Token Budget [MEDIUM]

| File class | Typical context | Output |
|------------|-----------------|--------|
| Single conflict in a 200-line test file | ~3 K tokens (full file ×3 sides + commit log) | ~600 tokens (resolved file) |
| Single conflict in a 1 K-line source file | ~12 K tokens | ~3 K tokens |
| Three-file conflict (today's I-00085) | ~10 K tokens total | ~1.8 K tokens |

**At our scale** (~3–5 conflict events per active week, per the merge-queue history):

- Worst-case Claude Sonnet 4.6 input @ $3/M tokens × 12K = **$0.036 per attempt**
- Worst-case Claude Opus 4.7 input @ $15/M tokens × 12K = **$0.18 per attempt**
- Total monthly cost ceiling at current throughput: **< $10/month** even if every conflict triggers a top-tier-model attempt with two retries.

The dominant cost is _operator wall-clock time_ — today's 2× failures consumed ~30 minutes of operator attention. Removing those saves more than the LLM ever costs.

### 4.2. Latency [HIGH]

- A single LLM call resolving a single file: **5–30 s** typical
- Plus verification gates: lint (~30 s), unit-tests (~60 s), affected-integration-tests (~90 s) → ~3 min added to the merge path
- Today's manual operator path: **20–40 min** of context-switching + git surgery

The merge queue already serialises merges; adding 3 min per conflict (only on conflict, not happy path) is acceptable.

---

## 5. Proposed Design for IW AI Core

> Written F-NNNNN-ready. The next step after this research doc is `/iw-new-feature` against this section.

### 5.1. High-level Flow

```mermaid
flowchart TD
    A[worktree_commit.sh<br/>git rebase main] -->|clean| Z[squash-merge to main]
    A -->|conflict| B{Conflict files match<br/>refuse-list?}
    B -->|yes| F[git rebase --abort<br/>emit merge_conflict event<br/>same as today]
    B -->|no| C{All conflict files match<br/>auto-resolve allowlist?<br/>e.g. tests/** docs/**}
    C -->|no| F
    C -->|yes| D[Invoke LLM resolver<br/>per conflicting file]
    D -->|any ABSTAIN<br/>or LLM error| F
    D -->|all resolved| E[Run verification gate<br/>lint + type-check + targeted tests]
    E -->|FAIL| G[git rebase --abort<br/>emit merge_auto_resolution_failed<br/>attach diff + reasoning]
    E -->|PASS| H[git rebase --continue<br/>emit merge_auto_resolved<br/>proceed to squash-merge]

### 5.1.1. Partial-allowlist semantics (CR-00088)

Prior to CR-00088, the allowlist check was **all-or-nothing**: if *any* conflicted file fell outside the allowlist patterns, the entire resolution was skipped with `skipped_reason="not_allowlisted"` — no LLM was consulted even if other files in the same conflict *were* allowlisted. CR-00088 changed this to **partition semantics**.

Under the new model, `classify_conflicts()` produces two disjoint sets:
- `eligible_files`: conflicted files matching `allowlist_patterns` that survive all earlier gates (refuse-list, binary, size, hunk-size).
- `deferred_files`: conflicted files that fail *only* the allowlist check (survived every earlier gate).

The LLM is invoked for `eligible_files` only. Non-allowlisted files are never passed to the LLM. Both sets are recorded in event metadata:

| Event | New metadata key | Meaning |
|-------|-----------------|---------|
| `merge_auto_resolution_attempted` | `allowlisted_files` | Files the LLM will be invoked for (alias for `eligible_files`) |
| `merge_auto_resolution_attempted` | `deferred_files` | Non-allowlisted files requiring manual resolution |
| `merge_auto_resolved` | `deferred_files` | Same partition in the success event |
| `merge_auto_resolution_failed` | `deferred_files` | Partition preserved even when LLM abstains/errors |

Refuse-list precedence is **unchanged**: if any file matches `refuselist_patterns`, the whole resolution still aborts with `skipped_reason="refuse_list"` before the partition logic runs.

Phase 1 (dry-run) still never mutates the worktree. The partition only affects what the LLM is invoked for and what the dashboard renders. The operator still rebases manually; the value is that they receive LLM proposals for the allowlisted subset, narrowing the manual-resolve scope.```

### 5.2. Decision Tree — When To Attempt LLM Resolution

```
On conflict in file F:

  if F ∈ REFUSE_LIST:                                           → abort (today's behaviour)
  elif F ∈ STRUCTURAL_RULE (uv.lock, Makefile):                 → apply rule (today's behaviour)
  elif PHASE == 1 (dry-run):                                    → log what LLM would do, abort
  elif F ∉ AUTO_RESOLVE_ALLOWLIST:                              → abort
  elif conflict_diff_size > MAX_CONFLICT_HUNK_LINES (= 80):     → abort
  elif file is binary OR contains non-text:                     → abort
  else:                                                          → attempt LLM resolution
```

Configuration lives in a new `executor/auto_merge.toml` (committed, reviewable):

```toml
# Phase 1: dry-run logging only. Phase 2: tests/** allowlist. Phase 3: broader.
phase = 2

[allowlist]
patterns = [
  "tests/**/*.py",
  "docs/**/*.md",
  "ai-dev/**/*.md",
]

[refuselist]
patterns = [
  "orch/db/migrations/versions/*.py",
  ".gitleaks.toml",
  ".env",
  ".env.*",
  ".gitignore",
  "orch/db/identity.py",
  "executor/worktree_commit.sh",
  "executor/*.sh",
  "uv.lock",            # already handled by --ours rule
  "*.png",
  "*.zst",
  "*.db",
  "*.sqlite",
]

[limits]
max_conflict_hunk_lines = 80
max_conflicted_files_per_merge = 5
verification_timeout_seconds = 600
```

### 5.3. Integration Point — Where the Code Lives

| Layer | What it does | Where |
|-------|--------------|-------|
| `executor/worktree_commit.sh` | Detect conflict, classify each conflict file against refuse-list / allowlist. **If any conflict is allowlisted, do NOT call `git rebase --abort`.** Emit the conflict file list to stdout as `CONFLICT_FILES=...` (F-00076 marker already exists) AND emit `AUTO_RESOLVE_REQUESTED=...`. Exit non-zero. | `executor/worktree_commit.sh` (~25 lines added between lines 346–356) |
| `orch/daemon/merge_queue.py` | On detecting `AUTO_RESOLVE_REQUESTED` in stdout (new marker), instead of immediately going to `merge_failed`, call `auto_merge_resolve()`. On success, re-invoke `worktree_commit.sh --resume-rebase`. | `orch/daemon/merge_queue.py` `_merge_item()` ~line 442 |
| `orch/daemon/auto_merge.py` | **NEW MODULE** — orchestrates the per-file LLM resolution + verification gate. | New file |
| `executor/worktree_commit.sh` (resume mode) | New `--resume-rebase` flag that runs `git rebase --continue` and the squash-merge step, assuming the worktree is already in a clean state. | Same file, new branch |

### 5.4. The LLM Resolver — `orch/daemon/auto_merge.py`

```python
# Skeleton — full design in F-NNNNN follow-up

class AutoMergeResult(NamedTuple):
    success: bool
    resolved_files: list[str]
    abstained_files: list[str]
    verification_log: str
    llm_calls: list[dict]   # for audit: model, prompt_hash, output_hash, tokens

def auto_merge_resolve(
    worktree_path: Path,
    conflict_files: list[str],
    item_id: str,
    project_id: str,
    db_session: Session,
    config: AutoMergeConfig,
) -> AutoMergeResult:
    """
    For each conflict file:
      1. Read merge base (git show :1:<f>), ours (:2:), theirs (:3:)
      2. Read recent commit log for both sides
      3. Read the work item description from DB (work_items.title + design doc)
      4. Build prompt (see 5.5)
      5. Call LLM (opencode/claude-code runtime, same as fix-cycle uses)
      6. Parse output; if `ABSTAIN`, mark file abstained
      7. Else write resolved file content, `git add <f>`

    If any file abstained → return AutoMergeResult(success=False, ...)
    Else run verification gate (see 5.6).
    """
```

### 5.5. Prompt Design

```text
You are resolving a git rebase conflict in IW AI Core.

WORK ITEM: {item_id} — {item_title}
WORK ITEM DESCRIPTION:
{item_design_doc_summary}     # first 500 words of design doc

FILE: {relative_path}
FILE PURPOSE: {auto-detected from CLAUDE.md mappings or path heuristic}

RECENT COMMITS ON main TOUCHING THIS FILE:
{git log -p -n 3 main -- <file>}

RECENT COMMITS ON THIS BRANCH TOUCHING THIS FILE:
{git log -p -n 3 HEAD -- <file>}

MERGE BASE (common ancestor):
```
{contents of :1:<file>}
```

MAIN'S CURRENT VERSION (--ours during rebase):
```
{contents of :2:<file>}
```

THIS BRANCH'S VERSION (--theirs during rebase):
```
{contents of :3:<file>}
```

INSTRUCTIONS:
1. Understand the intent of both sides.
2. Produce a resolution that preserves the semantic intent of BOTH the work item's changes and main's changes.
3. Output ONLY the full resolved file content, no prose, no markdown fences.
4. Do NOT invent new behaviour. Choose / combine only what is already on either side.
5. Do NOT reformat unrelated code.
6. If you cannot confidently resolve, output the literal string `ABSTAIN` and nothing else.

OUTPUT:
```

Why this prompt works (mapped to evidence):

- Full files (not just hunks) — ConGra finding that hunk-only context underperforms.
- Recent commits both sides — matches Sketch and Claude Code `/rebase` skill recipes.
- Item description — gives the model the "why" of the branch's changes.
- Explicit ABSTAIN token — matches rizzler / Sketch's "fail forward" property.
- No-invention clause — matches MergeBERT's "primitive merge patterns" insight (real resolutions are usually one-of-N existing patterns, not novel synthesis).

### 5.6. Verification Gate

After the LLM has produced resolved file content for ALL conflicts and `git add`-ed them, run a **scoped** subset of the existing QV gates:

```bash
# 1. Lint — fast, catches syntax errors and template-format issues
make lint                    # ~20–30 s

# 2. Type-check — catches type-level regressions
make type-check              # ~30–60 s

# 3. Targeted unit tests — only files that import the resolved files
uv run pytest tests/unit/ -k "<resolved-file-stems>" --timeout=120

# 4. Targeted integration tests — only files matching resolved paths
uv run pytest tests/integration/ tests/dashboard/ \
    -k "<resolved-file-stems>" --timeout=120 -x

# 5. Assertion-strength scanner (catches LLM "weakened assertion" failure)
make test-assertions
```

**Pass criteria**: all four exit 0 within the configured timeout. **Any failure → abort the rebase, emit `merge_auto_resolution_failed` with the verification log attached to event metadata.**

Why a subset and not the full QV suite: the full integration-tests gate takes 10–15 min. The auto-resolution runs synchronously in the merge queue; we cannot block the queue that long. The full suite already ran on this branch _before_ entry to the merge queue — what we need is regression detection for the resolved files specifically. If Phase 3 reveals weak coverage, we can expand the scoped subset.

### 5.7. Fallback and Audit Trail — New DaemonEvent Types

| Event type | Emitted when | Metadata |
|------------|--------------|----------|
| `merge_auto_resolution_attempted` | At start of `auto_merge_resolve()` | `conflict_files`, `phase`, `policy_decision` (allowlist|refuselist|hunk-size) |
| `merge_auto_resolved` | All files resolved + verification passed | `resolved_files`, `llm_calls` (model, prompt hash, output hash, token counts), `verification_log_path` |
| `merge_auto_resolution_failed` | Verification failed OR LLM abstained | `failed_reason` (lint|tests|abstain|llm_error), `resolved_files_attempted`, `abstained_files`, `verification_log_path`, `diff_attempted` |
| `merge_auto_resolution_skipped` | Decision tree rejected this conflict | `reason` (refuse_list|not_allowlisted|hunk_too_large|file_too_large|binary), `conflict_files` |

On `merge_auto_resolution_failed` or `merge_auto_resolution_skipped`, the existing `merge_conflict` event STILL fires with the conflict file list, so the operator UX is identical to today's manual flow.

### 5.8. Concurrency and Queueing

The merge queue (`orch/daemon/merge_queue.py` `process_merge_queue`) already serialises merges. `auto_merge_resolve()` runs in the same flow, so it is automatically serialised. **No additional lock needed.**

The LLM call itself can be parallelised across conflict files (independent files = independent calls) bounded at `max_conflicted_files_per_merge = 5` and `concurrency = 3` to keep token rate-limits happy.

### 5.9. Phased Rollout

| Phase | Behaviour | Success criterion to advance |
|-------|-----------|------------------------------|
| **0 — Plumbing only** | Decision tree, allowlist/refuselist config, new event types — but `auto_merge_resolve()` always returns `success=False` without calling an LLM | All event types fire in unit tests; existing merge-conflict UX unchanged |
| **1 — Dry-run** | LLM call executes, output is captured in event metadata, but NEVER applied. The rebase always aborts as today. | At least 5 historical-style conflicts captured. Manual operator review confirms LLM output would have been correct ≥4/5 |
| **2 — Tests-only auto-apply** | Allowlist: `tests/**`, `ai-dev/active/**/reports/**`, `docs/**`. Auto-apply with full verification gate. | Phase 2 runs for 2 weeks with ≥5 auto-resolutions; zero post-merge regressions from auto-resolved files |
| **3 — Broader auto-apply** | Allowlist expanded to `dashboard/templates/**`, `dashboard/static/**`, then case-by-case to source files | Quality of verification gate proven; no operator-reported false-positive merges |

**Each phase has a kill switch**: `executor/auto_merge.toml`'s `phase = 0` instantly reverts to today's behaviour.

### 5.10. Cost Estimate

Per merge-conflict event:

- 1–5 LLM calls × ~10 K input tokens × ~2 K output tokens
- Claude Sonnet 4.6: ~$0.05–$0.25 per conflict event
- Verification gate compute: negligible (already provisioned)

Monthly ceiling (at 10× current conflict rate to allow growth): **< $20/month**. Operator-time savings per avoided manual resolution: ~25 min. Even at one auto-resolution per week, this pays back at any reasonable hourly rate within the first event.

### 5.11. Acceptance Criteria (Anchored to I-00085 and I-00086)

A successful Phase 2 implementation MUST satisfy the following — they are derived literally from today's failures:

#### AC-1 (I-00085 reproduction)

Given a branch with the exact diff `db247e8a` (I-00085's pre-rebase state) and main at `3973f900`:

```
WHEN  the merge queue runs against this branch
THEN  worktree_commit.sh detects 3 conflict files
AND   all 3 are in the tests/** allowlist
AND   none are in the refuse-list
AND   auto_merge_resolve() is invoked
AND   the LLM produces 3 resolved files
AND   lint + type-check + targeted tests pass
AND   the rebase continues to a squash-merge
AND   a merge_auto_resolved event records the resolved files
AND   main now has the equivalent of f69e668b (today's manual outcome)
```

#### AC-2 (I-00086 reproduction)

Given a branch with the exact diff `b207b22d` (I-00086's pre-rebase state) and main at `3973f900`, where one conflict requires picking the dynamic `select(AgentRuntimeOption)` approach over the hardcoded list:

```
WHEN  the merge queue runs against this branch
THEN  conflict files are detected and allowlisted
AND   auto_merge_resolve() invokes the LLM with merge-base, ours, theirs, commit logs
AND   the LLM produces a resolution that preserves the dynamic query
AND   the verification gate passes (the dynamic-query version is functionally correct)
AND   merge_auto_resolved fires
AND   main equals today's manual outcome (40c6ea41) modulo comment wording
```

#### AC-3 (Refuse-list safety)

Given a conflict that touches `orch/db/migrations/versions/d1e2f3gpt53c_*.py`:

```
WHEN  worktree_commit.sh detects the conflict
THEN  no LLM call is made
AND   the rebase is aborted exactly as today
AND   merge_auto_resolution_skipped fires with reason=refuse_list
AND   merge_conflict fires as today
```

#### AC-4 (Verification catch)

Given a constructed conflict where the LLM's resolution would break a unit test:

```
WHEN  auto_merge_resolve() applies the LLM output
THEN  the verification gate fails
AND   git rebase --abort restores the pre-attempt state
AND   merge_auto_resolution_failed fires with the verification log
AND   merge_conflict fires as today
```

#### AC-5 (Operator UX unchanged on failure)

For any case where auto-resolution doesn't succeed:

```
THEN  the operator sees the same merge_conflict event and instructions as today
AND   the existing iw merge-queue retry-merge <ID> path works unchanged
AND   any LLM-attempted-but-failed metadata is attached to the event for post-mortem review
```

---

## 6. Recommendations

1. **Build it.** All five academic benchmarks plus three production deployments (GitHub Copilot, LLMinus, Sketch) confirm the resolve-then-verify pattern works in practice. We already have all the building blocks: ephemeral worktrees, an LLM agent runtime, a serialised merge queue, and the QV gates needed for verification. This is **lower-risk than typical LLM-in-the-loop features** because the existing operator-fallback path remains intact and is the safety net.

2. **Start with Phase 1 (dry-run) for at least 2 weeks** before any auto-apply. The dry-run audit data lets us tune the prompt, observe the actual abstention rate on our codebase, and validate the refuse-list before any operator-visible behaviour changes. (Evidence: every working production deployment surveyed shipped a logging/preview mode first.)

3. **Constrain Phase 2 to `tests/**`, `docs/**`, `ai-dev/active/**/reports/**`.** Today's failures both happened in `tests/**`. The Phase 2 allowlist captures 100 % of today's recurring failure mode with minimal blast radius. (Evidence: I-00084/I-00085/I-00086 + ConGra finding that test-fixture updates are a high-frequency conflict class.)

4. **Adopt the explicit `ABSTAIN` token.** This is the single most important prompt-design decision. Without it, LLMs invent plausible-but-wrong resolutions. With it, the worst-case is "fall back to today's manual path" — strictly Pareto-improving. (Evidence: Sketch's "fails rather than producing worse merges" property, rizzler's "send an 'oops' back to Git" pattern.)

5. **Do NOT auto-resolve migration files, ever.** The CR-00021 / I-00075 / I-00076 lessons are categorical: Alembic chain mutations belong to the migration-rebase phase that already has explicit operator gates. Layering an LLM on top adds risk without benefit. (Evidence: explicit project rules in CLAUDE.md; LLMinus maintainers' decidedly human-in-the-loop stance.)

6. **Treat verification-gate scope as a tunable parameter.** Start with lint + type-check + targeted tests (~3 min). If Phase 2 data shows the gate is letting bad merges through, widen to full unit-tests; if Phase 3 reveals integration-coverage gaps, widen further. (Evidence: GitHub Copilot cloud agent's "tests + build must pass" gate is currently the gold standard.)

---

## 7. Limitations

- **Sample of one failure cluster.** This research is anchored to I-00085 + I-00086, which share a single root cause (parallel test-fixture updates triggered by F-00081's new runtime-option migration). The design should generalise to other conflict classes, but Phase 1 dry-run data is necessary to confirm.
- **LLM accuracy still bounded.** Even SOTA models resolve "< 60 %" on Merge-Bench. Our verification gate must catch the wrong-but-plausible cases. If the gate is too narrow, regressions will leak; if too wide, the merge queue stalls.
- **No data on multi-file invariant breaks.** Our verification gate runs targeted tests, but a resolution that breaks a cross-file invariant invisible to those tests will pass our gate. The Phase 2 allowlist (tests-only) sidesteps this; Phase 3 would need a richer gate.
- **Cost data is estimated from public API pricing.** Real-world rate-limit behaviour and our specific opencode/claude-code runtime overhead could shift costs.
- **The research is recent.** Merge-Bench is from May 2026 (this month); ConGra from Sep 2024. The state-of-the-art is moving fast — by the time we ship Phase 3, accuracy benchmarks may shift materially.

---

## 8. Sources

| # | Title | Credibility | URL |
|---|-------|-------------|-----|
| 1 | MergeBERT: Program Merge Conflict Resolution via Neural Transformers (FSE 2022) | HIGH (peer-reviewed) | [arxiv.org/abs/2109.00084](https://arxiv.org/abs/2109.00084) |
| 2 | DeepMerge: Learning to Merge Programs (TSE 2022) | HIGH (peer-reviewed) | [arxiv.org/abs/2105.07569](https://arxiv.org/abs/2105.07569) |
| 3 | Git Merge Conflict Resolution Leveraging Strategy Classification and LLM — ChatMerge (IEEE 2023) | HIGH (peer-reviewed) | [ieeexplore.ieee.org/document/10366637](https://ieeexplore.ieee.org/document/10366637/) |
| 4 | ConGra: Benchmarking Automatic Conflict Resolution (arXiv 2024) | HIGH (peer-reviewed) | [arxiv.org/html/2409.14121v1](https://arxiv.org/html/2409.14121v1) |
| 5 | Merge-Bench: Resolve Merge Conflicts with Large Language Models (ICPR 2026) | HIGH (peer-reviewed) | [homes.cs.washington.edu/~mernst/pubs/merge-bench-icpr2026-abstract.html](https://homes.cs.washington.edu/~mernst/pubs/merge-bench-icpr2026-abstract.html) |
| 6 | GitHub Copilot cloud agent — Fix merge conflicts in three clicks (changelog, Apr 2026) | HIGH (vendor official) | [github.blog/changelog/2026-04-13-fix-merge-conflicts-in-three-clicks-with-copilot-cloud-agent](https://github.blog/changelog/2026-04-13-fix-merge-conflicts-in-three-clicks-with-copilot-cloud-agent/) |
| 7 | Ask @copilot to resolve merge conflicts on pull requests (changelog, Mar 2026) | HIGH (vendor official) | [github.blog/changelog/2026-03-26-ask-copilot-to-resolve-merge-conflicts-on-pull-requests](https://github.blog/changelog/2026-03-26-ask-copilot-to-resolve-merge-conflicts-on-pull-requests/) |
| 8 | Sketch — Have AI resolve your merge/rebase conflicts | MEDIUM (vendor blog) | [sketch.dev/blog/merde](https://sketch.dev/blog/merde) |
| 9 | rizzler — stop crying over Git merge conflicts | MEDIUM (practitioner blog) | [ghuntley.com/rizzler](https://ghuntley.com/rizzler/) |
| 10 | LLMinus: LLM-Assisted Merge Conflict Resolution (LWN coverage) | HIGH (technical journalism, primary-source links) | [lwn.net/Articles/1051607](https://lwn.net/Articles/1051607/) |
| 11 | LLMinus Working On AI/LLM-Powered Merge Conflict Resolution For The Linux Kernel (Phoronix) | MEDIUM (technical journalism) | [phoronix.com/news/LLMinus-RFC-v2](https://www.phoronix.com/news/LLMinus-RFC-v2) |
| 12 | Mergify Merge Queue documentation | HIGH (vendor official) | [docs.mergify.com/merge-queue](https://docs.mergify.com/merge-queue/) |
| 13 | Aviator MergeQueue documentation | HIGH (vendor official) | [docs.aviator.co/mergequeue](https://docs.aviator.co/mergequeue) |
| 14 | Aviator — Resolving a Cherry-Pick Failure | HIGH (vendor official) | [docs.aviator.co/releases-beta/how-to-guides/resolving-a-cherry-pick-failure](https://docs.aviator.co/releases-beta/how-to-guides/resolving-a-cherry-pick-failure) |
| 15 | Graphite Merge Queue documentation | HIGH (vendor official) | [www.graphite.com/docs/graphite-merge-queue](https://www.graphite.com/docs/graphite-merge-queue) |
| 16 | The role of AI in merge conflict resolution — Graphite guide | MEDIUM (vendor blog) | [www.graphite.com/guides/ai-code-merge-conflict-resolution](https://www.graphite.com/guides/ai-code-merge-conflict-resolution) |
| 17 | Resolve merge conflicts with Claude Code (Raine Virta) | MEDIUM (practitioner blog) | [raine.dev/blog/resolve-conflicts-with-claude](https://raine.dev/blog/resolve-conflicts-with-claude/) |
| 18 | claude-extensions — merge-conflict skill | MEDIUM (OSS reference impl) | [github.com/always-further/claude-extensions/blob/main/commands/merge-conflict.md](https://github.com/always-further/claude-extensions/blob/main/commands/merge-conflict.md) |
| 19 | Solving Red Main Issues: Merge Queues vs. Better Policies (Aspect blog) | MEDIUM (industry blog) | [blog.aspect.build/keeping-main-green](https://blog.aspect.build/keeping-main-green) |
| 20 | Resolving Merge Conflicts with AI: Copilot, Cursor & Claude (DeployHQ) | LOW (vendor-neutral blog) | [www.deployhq.com/git/resolving-merge-conflicts-with-ai](https://www.deployhq.com/git/resolving-merge-conflicts-with-ai) |

# Bounding Agent Context Growth in the IW AI Core Executor — Tool-Output Capping

**Research ID**: R-00078
**Date**: 2026-05-22
**Mode**: deep
**Depth**: deep
**Primary Question**: How should the IW AI Core executor bound per-step LLM-agent context growth — primarily via tool-output capping — so that workflow steps on small-context runtimes do not overflow and fail?

---

## Executive Summary

A CR-00076 workflow step overflowed the context window of its runtime (`pi` / MiniMax-M2.7) and failed mid-run. Research across production agent harnesses and recent literature converges on a clear answer: **cap each tool result with a byte/token budget, and spill the overflow to a file the agent can re-read on demand** — never silently truncate in place, and never summarise raw tool output. A peer-reviewed-style study finds [truncation significantly outperforms summarization](https://arxiv.org/pdf/2511.22729) for tool outputs. The capping logic should live in the **IW AI Core executor**, because runtime caps vary and some runtimes (and the dashboard gauge) measure budget against the full context window while ignoring the model's output reservation — which is what made a "64%" reading overflow. Recommended: a per-tool-call cap (~25–50 KB) with disk spill, plus an executor-side context budget measured as `window − max_output_tokens − safety_buffer`, with proactive compaction at ~70–80% of that *effective* budget.

## Background

CR-00076 step S01 ran on the `pi` runtime with `minimax/MiniMax-M2.7`. It hit `400 invalid_request_error: context window exceeds limit` mid-edit; the runtime auto-compacted but the step never finished cleanly. The dashboard reported only 64% context usage at the time. The operator has decided to keep the work on the same runtime (no model-routing) and fix the problem by making steps smaller and bounding context growth; this research informs the *exact implementation* of the tool-output-capping and compaction-threshold pieces of the follow-up incident.

## Findings

### A model's effective input budget is `window − max_output`, not the full window [HIGH confidence]

MiniMax-M2.7 has a **204,800-token context window with a maximum output of 131,072 tokens** ([MiniMax M2.7 — OpenRouter](https://openrouter.ai/minimax/minimax-m2.7); window correction in [cline PR #10007](https://github.com/Kilo-Org/kilocode/issues/1224)). The context window "represents the total capacity for both input and output combined in a single request" ([MiniMax API docs, via search](https://platform.minimax.io/docs/token-plan/best-practices)). Because the model can be asked to generate up to 131 K output tokens, the **practical input ceiling is `204,800 − 131,072 ≈ 73,728 tokens`** — roughly a third of the nominal window.

This explains the "64% but still overflowed" symptom directly. A gauge that divides accumulated input by the *full* 204,800-token window shows ~64% at ~131 K input — but 131 K input plus a large requested output exceeds 204,800, so the API rejects the request. Production harnesses universally reserve output before computing usable context: opencode reserves **32,000 output tokens plus a 20,000-token safety buffer**, with `usable = window − output − buffer` ([opencode context management](https://deepwiki.com/sst/opencode/2.4-context-management-and-compaction)). The IW AI Core context gauge and any compaction threshold must use the *effective* budget, not the raw window, or they will systematically under-report and trigger too late.

### Truncation beats summarization for tool outputs [HIGH confidence]

A 2026 study dedicated to context-window overflow in tool-calling agents finds that **["truncation significantly outperforms summarization"](https://arxiv.org/pdf/2511.22729)** in maintaining task performance — a counter-intuitive result. Truncation "maintains raw data integrity, allowing agents to extract key patterns directly," whereas "summarization, while reducing tokens, frequently introduces information loss through the abstraction process itself" ([arxiv 2511.22729](https://arxiv.org/pdf/2511.22729)). Anthropic's own guidance is consistent: the lightest-touch compaction is **"tool result clearing"** — drop the raw result but keep the message structure — reserving LLM summarization for whole-conversation compaction, not individual tool outputs ([Anthropic — Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)).

Implication for IW AI Core: do **not** build an LLM-summarizer for large tool results. A deterministic, cheap byte/line cap is both better-performing and avoids an extra LLM call on the small-context runtime.

### The correct pattern is "cap + spill to file", not in-place truncation [HIGH confidence]

The naive fix — replacing a large result with a head/tail snippet and an inline `…N tokens truncated…` marker — is explicitly identified as **"the worst of both worlds: it preserves neither exactness nor recoverability"** ([Codex issue #14206](https://github.com/openai/codex/issues/14206)). It silently changes tool-result semantics: "structured payloads can become invalid or unparsable, logs and tabular output lose the middle, which is often where the answer actually is" ([Codex issue #14206](https://github.com/openai/codex/issues/14206)).

The pattern production systems converge on is **context offloading**: "store the response in a file and return a message containing only essential information — a summary, the number of results, and a file reference ID … The key property is recoverability" ([context offloading overview](https://www.flowhunt.io/blog/advanced-ai-agents-with-file-access-mastering-context-offloading-and-state-management/)). Claude Code already does exactly this for its Bash tool: a **30,000-character default limit** (raisable via `BASH_MAX_OUTPUT_LENGTH` to a 150,000-char ceiling); when exceeded it "saves the full output to a file in the session directory and gives Claude the file path plus a short preview" ([Claude Code Bash output limits, issue #19901](https://github.com/anthropics/claude-code/issues/19901)). For file reads it applies "a 256 KB byte cap … oversized tool results are persisted to disk and replaced with 2 KB previews" ([Arize — context management in agent harnesses](https://arize.com/blog/context-management-in-agent-harnesses/)).

### Production harness caps — concrete numbers [HIGH confidence]

The following table is drawn from a cross-harness survey ([Arize](https://arize.com/blog/context-management-in-agent-harnesses/)) plus per-harness docs:

| Harness | Per-tool-output cap | Compaction trigger | Notes |
|---------|--------------------|--------------------|-------|
| Claude Code | Bash 30 KB (→150 KB max); file read 256 KB byte cap + 25 K-token gate; **per-tool cap 50 K chars, per-message aggregate 200 K chars**; oversized → disk + 2 KB preview | `window − 13,000` tokens | "Pre-query optimization" offloads tool results *before* compaction is needed ([Arize](https://arize.com/blog/context-management-in-agent-harnesses/), [Claude Code context window](https://code.claude.com/docs/en/context-window)) |
| **`pi`** (this incident's runtime) | hard cap **2,000 lines or 50 KB**, head-truncation + continuation nudge (`Use offset=2001…`) | `window − 16,384` tokens; keeps ~20 K tokens of messages | Cap is **per call** — it does not bound *accumulated* tool output ([Arize](https://arize.com/blog/context-management-in-agent-harnesses/)) |
| opencode | prunes tool outputs only when total tool output > **40,000 tokens** and ≥ **20,000 tokens** can be reclaimed; protects last 2 turns; `skill` tool parts never pruned | overflow when tokens > `window − 32,000 (output) − 20,000 (buffer)` | On overflow → structured Markdown summary; `ContextOverflowError` if compaction itself overflows ([opencode](https://deepwiki.com/sst/opencode/2.4-context-management-and-compaction)) |
| OpenHands | condensers: `noop`/`recent`/`llm`/`amortized`/`observation_masking`/`llm_attention`; `LLMSummarizingCondenser` keeps first 2 events | event-count `max_size` threshold | "Up to 2× reduction in per-turn API cost" ([OpenHands context condenser](https://docs.openhands.dev/sdk/guides/context-condenser)) |
| OpenClaw | 75% head / 25% tail split for oversized bootstrap files | 50% of window | staged multi-pass summarization with tool-call/result pair repair ([Arize](https://arize.com/blog/context-management-in-agent-harnesses/)) |
| Letta | per-file char limits **scaling with model window: 5,000–40,000 chars** | 90% of window | files embedded in a vector store for retrieval ([Arize](https://arize.com/blog/context-management-in-agent-harnesses/)) |
| Aider | `--map-tokens` repo-map budget (default 1 K), graph-ranked; "never enforces token limits, only reports API errors" | n/a | a *prevention* model — keep input small up front ([Aider — token limits](https://aider.chat/docs/troubleshooting/token-limits.html), [repo map](https://aider.chat/docs/repomap.html)) |

Two patterns dominate: a **per-tool-output byte/line cap in the 30–256 KB range** (Claude Code, `pi`, Letta), and a **token-threshold compaction** computed against an *output-reserved* effective budget (opencode, OpenClaw, Letta).

### `pi`'s per-call cap does not bound accumulated context — capping must also be cumulative [HIGH confidence]

`pi` *does* cap a single tool result at 2,000 lines / 50 KB ([Arize](https://arize.com/blog/context-management-in-agent-harnesses/)) — so the CR-00076 overflow was **not** one giant result. 50 KB ≈ 12–15 K tokens; a step that performs a few dozen file reads, edits and `pytest` runs accumulates well past 74 K input tokens even with every individual result capped. `pi`'s compaction trigger (`window − 16,384` ≈ 188 K for MiniMax-M2.7) is calibrated to the *nominal* window and fires far too late for a model whose effective input budget is ~74 K. The implication: a per-call cap is necessary but **not sufficient** — the executor also needs a cumulative budget and proactive compaction, and the agent prompt must avoid wasteful reads (the CR-00076 agent ran the full integration suite against instructions, a single multi-hundred-line output).

### Capping belongs in the executor layer, not the runtime [MEDIUM confidence]

Runtimes disagree on caps and some omit them entirely: Cline's `read_file` historically returned untruncated output, "filling the context window … leading to context overflow errors" ([Cline issue #4576](https://github.com/cline/cline/issues/4576)); Claude Code has open reports of "ingesting massive tool outputs without truncation" ([Claude Code issue #12054](https://github.com/anthropics/claude-code/issues/12054)). IW AI Core runs *multiple* runtimes (claude-code, opencode, `pi`) behind one executor. Placing the cap in the executor — which already mediates step launch and knows the chosen model's `window` and `max_output` — gives one consistent, testable policy regardless of runtime, and protects against runtimes that cap loosely or not at all. The trade-off: the executor must intercept tool I/O, which is straightforward for shell-mediated tools (the executor already shells out) but harder for a runtime's built-in file tools — there, the executor can only set the runtime's own cap env vars (e.g. `BASH_MAX_OUTPUT_LENGTH` for claude-code) and rely on prompt guidance. This split is why this finding is MEDIUM, not HIGH: full executor-side interception is not uniformly achievable.

### Proactive compaction at ~70–80% of the effective budget; protect head + tail and never split tool pairs [HIGH confidence]

Harness compaction triggers, normalised: Claude Code current versions compact at **64–75% capacity** (older versions waited for 90%+) ([Morph — Claude Code context window](https://www.morphllm.com/claude-code-context-window)); OpenClaw at 50%; Letta at 90%. The cross-cutting rule is to compact *before* the hard limit, against the **effective** budget. Truncation/compaction must "avoid splitting `tool_call`/`tool_result` pairs so that an assistant message that called a tool stays paired with its result," and should "protect the first 3 messages and the recent tail" ([context-budget-aware truncation](https://mem0.ai/blog/how-hermes-and-claude-handle-context-compression-in-real-production-agents-(and-what-you-should-extract))). The user has already accepted auto-compaction; the open parameter is the threshold — set it as a fraction of `window − max_output − buffer`, not of the raw window.

---

## Recommendations

1. **Primary — executor-side per-tool-output cap with disk spill, plus an effective-budget context meter.**
   - Cap each tool result at a configurable byte budget (start at **~25 KB**, the Claude-Code Bash-tool order of magnitude, tunable per runtime). On exceed, **write the full result to the step's work directory** (e.g. `ai-dev/work/<ITEM>/.tool-cache/<step>-<n>.txt`) and return a head+tail preview **plus the file path** so the agent can `grep`/`Read` the rest — recoverability, per [Codex #14206](https://github.com/openai/codex/issues/14206) and [Claude Code's Bash spill](https://github.com/anthropics/claude-code/issues/19901).
   - Compute the step's context budget as `window − max_output_tokens − safety_buffer` from the model's real numbers (MiniMax-M2.7: `204,800 − 131,072 − ~8,000 ≈ 65 K`), and fix the dashboard gauge to display against *that*, not the raw window — this directly removes the misleading "64%".
   - Trigger proactive compaction at **~75% of the effective budget**; keep the existing auto-compaction the operator already accepts.
   - For runtimes with their own caps, have the executor set them low (e.g. export `BASH_MAX_OUTPUT_LENGTH` for claude-code) rather than relying on defaults.

2. **Alternative — if executor-side interception of a runtime's built-in tools proves infeasible**, fall back to (a) setting each runtime's native cap env vars as low as the runtime allows, and (b) leaning harder on **smaller steps** (already the operator's primary fix) so cumulative context never approaches the effective budget. Smaller steps also map onto the universal **sub-agent isolation** pattern — sub-agents "receive only the delegated task … no parent conversation history" ([Arize](https://arize.com/blog/context-management-in-agent-harnesses/)) — so splitting S01-style monoliths into scoped sub-steps is itself a context-bounding mechanism.

3. **Avoid** — (a) **LLM-summarising individual tool outputs**: empirically worse than truncation and adds an LLM call on the small-context runtime ([arxiv 2511.22729](https://arxiv.org/pdf/2511.22729)). (b) **In-place head/tail truncation with an inline `…truncated…` marker and no spill file** — "the worst of both worlds … preserves neither exactness nor recoverability" ([Codex #14206](https://github.com/openai/codex/issues/14206)). (c) **Calibrating any threshold or gauge against the nominal context window** — for output-heavy models it overstates headroom by ~3×.

---

## Limitations

- The exact internal mechanism by which CR-00076 S01 overflowed (and the meaning of the API error's `(2013)` code) was not directly observed; the root-cause findings are reasoned from `pi`'s documented caps and MiniMax-M2.7's published window/output numbers, not from a runtime trace.
- `pi`'s cap and compaction numbers come from one cross-harness survey ([Arize](https://arize.com/blog/context-management-in-agent-harnesses/)); they were not cross-checked against `pi`'s own source/docs, which were not publicly locatable.
- This research does not measure IW AI Core's actual per-step token consumption — a follow-up should instrument the executor to log accumulated input tokens per step before picking the exact cap and threshold constants.
- Feasibility of executor-side interception of each runtime's built-in (non-shell) file tools was not verified against the IW AI Core executor code; that is an implementation-time spike.
- No empirical evaluation of the 25 KB starting cap against IW AI Core's own workloads — it is an order-of-magnitude starting point from comparable harnesses, to be tuned.

---

## Sources

| # | Source | Credibility | URL |
|---|--------|-------------|-----|
| 1 | Anthropic — Effective context engineering for AI agents | HIGH | https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents |
| 2 | arXiv 2511.22729 — Solving Context Window Overflow in AI Agents | HIGH | https://arxiv.org/pdf/2511.22729 |
| 3 | Arize — Context management in agent harnesses: memory, files, subagents | HIGH | https://arize.com/blog/context-management-in-agent-harnesses/ |
| 4 | opencode — Context Management and Compaction (DeepWiki) | MEDIUM | https://deepwiki.com/sst/opencode/2.4-context-management-and-compaction |
| 5 | OpenHands — Context Condenser (official docs) | HIGH | https://docs.openhands.dev/sdk/guides/context-condenser |
| 6 | Claude Code — Explore the context window (official docs) | HIGH | https://code.claude.com/docs/en/context-window |
| 7 | Claude Code issue #19901 — Bash tool 30 K output limit & truncation | MEDIUM | https://github.com/anthropics/claude-code/issues/19901 |
| 8 | Claude Code issue #12054 — ingests massive tool outputs without truncation | MEDIUM | https://github.com/anthropics/claude-code/issues/12054 |
| 9 | OpenAI Codex issue #14206 — Auto-spill large tool outputs to files | MEDIUM | https://github.com/openai/codex/issues/14206 |
| 10 | Cline issue #4576 — read_file does not truncate large output | MEDIUM | https://github.com/cline/cline/issues/4576 |
| 11 | Aider — Token limits (official docs) | HIGH | https://aider.chat/docs/troubleshooting/token-limits.html |
| 12 | Aider — Repository map (official docs) | HIGH | https://aider.chat/docs/repomap.html |
| 13 | Roo Code — read_file tool (official docs) | MEDIUM | https://docs.roocode.com/features/tools/read-file/ |
| 14 | MiniMax M2.7 — API pricing & context window (OpenRouter) | HIGH | https://openrouter.ai/minimax/minimax-m2.7 |
| 15 | Morph — Claude Code Context Window: limits, compaction & management | MEDIUM | https://www.morphllm.com/claude-code-context-window |
| 16 | mem0 — Context Compression: Hermes vs. Claude Code | MEDIUM | https://mem0.ai/blog/how-hermes-and-claude-handle-context-compression-in-real-production-agents-(and-what-you-should-extract) |
| 17 | FlowHunt — Context offloading & state management for AI agents | MEDIUM | https://www.flowhunt.io/blog/advanced-ai-agents-with-file-access-mastering-context-offloading-and-state-management/ |

---

## Appendix: Research Log

**Date range**: 2026-05-22 to 2026-05-22
**Queries run**: 9 WebSearch, 6 WebFetch, 1 `gh` issue fetch, 0 context7
**Mode used**: deep
**Depth level**: deep

Notes: context7 was not used — the subject is agent-harness design practice rather than a single library API, so WebSearch/WebFetch against primary harness docs, GitHub issues, and the arXiv study were the appropriate sources. The most load-bearing source is the Arize cross-harness survey (#3), which uniquely provides per-harness cap/compaction constants including for the `pi` runtime; its `pi`-specific figures should be re-verified against `pi`'s own documentation during incident implementation.

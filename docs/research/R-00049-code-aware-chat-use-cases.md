# R-00049 — Code-aware LLM chat in real products: use cases, outcomes, and implementation patterns

| Field | Value |
|-------|-------|
| ID | R-00049 |
| Date | 2026-04-17 |
| Mode | deep |
| Editorial category | functional |
| Primary question | How are chatbots/LLMs actually being used to interact with codebases in shipping products, which patterns produce measurable value, and what should iw-ai-core expect to gain by investing in a high-quality code-aware chat for the dashboard's code module view? |

---

## Executive Summary

Code-aware LLM chat has moved from novelty to **mainstream developer workflow**: the 2025 DORA report puts AI adoption at 90% of technology professionals, with 80%+ reporting productivity gains and users completing **21% more tasks and 98% more merged PRs** ([Faros — DORA 2025 takeaways](https://www.faros.ai/blog/key-takeaways-from-the-dora-report-2025), [Google Cloud — Announcing 2025 DORA](https://cloud.google.com/blog/products/ai-machine-learning/announcing-the-2025-dora-report)). The highest-value patterns are **not autocompletion** but the Q&A/navigational ones: "explain this module", "where is this used", "what would break if I change X", "generate a diagram", "write tests for this". For a **read-first dashboard** (iw-ai-core's context — not an IDE), these are exactly the workflows that a chat panel can support better than a file tree or dependency graph ever could. The investment pays off **if and only if** three things are true: (1) retrieval is grounded (hybrid BM25 + dense, symbol-aware, cited inline), (2) every answer has a jump-to-source affordance, and (3) scoping controls (@-mentions, context chips) are present. Without those, we replicate the industry's well-documented anti-patterns — hallucinated APIs, dependency confusion, the METR "19% slower" trap — and the chat becomes a net tax, not a net win. Recommendation: proceed, but scope the MVP around five killer use cases (explain, find usages, trace flow, summarize module, generate diagram), with citations and jump-to-source as non-negotiables.

---

## Findings

### F1 — AI code-assistant adoption is now the norm, with solid individual-productivity evidence [HIGH]

The **2025 DORA report** (~5,000 technology professionals surveyed) reports **90% AI adoption at work**, **80%+ self-reporting productivity gains**, **21% more tasks completed**, and **98% more PRs merged** for AI users, with **59% reporting a positive influence on code quality** ([DORA 2025 — dora.dev](https://dora.dev/research/2025/dora-report/), [Google Cloud blog](https://cloud.google.com/blog/products/ai-machine-learning/announcing-the-2025-dora-report), [Faros summary](https://www.faros.ai/blog/key-takeaways-from-the-dora-report-2025)). The original **GitHub Copilot SPACE study** (n=95 in the controlled trial, 2,000+ survey respondents) showed a **55.8% speedup on a scoped HTTP-server task**, 78% vs 70% completion, and self-reported gains in focus, flow, and reduced frustration ([GitHub blog — Copilot SPACE study](https://github.blog/news-insights/research/research-quantifying-github-copilots-impact-on-developer-productivity-and-happiness/), [Microsoft/Accenture field experiment](https://mit-genai.pubpub.org/pub/v5iixksv): 12.92%–21.83% more PRs/week at Microsoft, 7.51%–8.69% at Accenture).

**Counter-evidence is important and worth naming.** The METR study (246 tasks, experienced open-source maintainers) found that developers using AI tools like Cursor took **19% longer** despite *perceiving* themselves as faster — driven by prompting overhead, context-switching, and 9% of time spent validating outputs ([Augment — Why AI tools make devs 19% slower](https://www.augmentcode.com/guides/why-ai-coding-tools-make-experienced-developers-19-slower-and-how-to-fix-it)). A NAV IT (Norway) longitudinal study of 250 Copilot users found no statistically significant weekly-activity gain ([arXiv 2509.20353](https://arxiv.org/html/2509.20353v2)). The **2025 DORA report also flags AI's negative relationship with delivery stability** — i.e. throughput goes up, but so does change-failure rate.

**What this means for iw-ai-core**: gains are real but **conditional on context quality** (F4) and **grounding** (F5). A chat that adds prompting overhead or returns unverifiable output will replicate the 19%-slower case, not the 21%-more-tasks case.

### F2 — Enterprise case studies from Cody, Amazon Q, and others converge on the same "code understanding" use cases [HIGH]

Concrete enterprise numbers, clustered by use case:

| Product | Customer | Headline metric | Primary use cases |
|---|---|---|---|
| Cody (Sourcegraph) | **Palo Alto Networks** | Up to **40% productivity boost** for 2,000 developers ([Sourcegraph case studies](https://sourcegraph.com/case-studies)) | Code understanding, search, navigation |
| Cody | **Qualtrics** | **28% fewer IDE exits**, **25% faster code understanding**, **unit tests: 1 day → ~10 min** ([Qualtrics case study](https://sourcegraph.com/case-studies/qualtrics-speeds-up-unit-tests-and-code-understanding-with-cody)) | Test gen, code QA, junior onboarding |
| Amazon Q Dev | **Boomi** | **+20% productivity** for 445 devs; 20% of code AI-generated ([Boomi case study](https://aws.amazon.com/solutions/case-studies/boomi-case-study/)) | Chat-first exploration, inline suggestions |
| Amazon Q Dev | **DTCC** | **+40% throughput during POC** ([DTCC case study](https://aws.amazon.com/solutions/case-studies/dtcc-case-study/)) | Code understanding, modernization |
| Amazon Q Dev | **nnamu** | **−30% development time** ([nnamu case study](https://aws.amazon.com/solutions/case-studies/nnamu/)) | Chat + codegen |
| Sourcegraph (Batch Changes) | **Workiva** | **−80% time for large-scale code changes** ([Sourcegraph blog — Cody is enterprise ready](https://sourcegraph.com/blog/cody-is-enterprise-ready)) | Refactors (separate product but same grounding story) |

The consistent top-of-list use cases across these studies are **code understanding / navigation** and **test generation**, *not* raw autocomplete. Qualtrics' Senior Engineer Brendan Doyle is quoted: *"Something that would've taken me multiple dev days was done in an hour with Cody. Cody can generate a template for a test, and then I can prompt it to make adjustments."* ([Qualtrics case study](https://sourcegraph.com/case-studies/qualtrics-speeds-up-unit-tests-and-code-understanding-with-cody)).

### F3 — The killer interaction patterns are read-oriented, not write-oriented [HIGH]

Across Cursor, Cody, Copilot Chat, Claude Code, Continue, Aider, Amazon Q, and others, the same patterns appear as the headline "what can you do with it?" demos:

| Pattern | Where it shows up | Evidence |
|---|---|---|
| **Explain this symbol / module / file** | All major products | Universal — Cody's `@`-mentions and `@#` symbol context ([Sourcegraph — Chat](https://sourcegraph.com/docs/cody/capabilities/chat)); Continue's `@File`, `@Code`, `@Folder`, `@Repo-Map` ([Continue context providers](https://docs.continue.dev/customize/custom-providers)) |
| **Where is this used / find references** | Cursor, Cody, Claude Code | Cursor @codebase example: *"which files handle payment processing?"* ([techjacksolutions review](https://techjacksolutions.com/ai/ai-development/cursor-ide-what-it-is/)); LSP-backed tools run `find_all_references` automatically ([Augment Code — Best coding LLMs](https://www.augmentcode.com/tools/best-coding-llms-that-actually-work)) |
| **Trace flow / impact analysis** | Claude Code, LSP-integrated | *"trace code paths across multiple files … how changes in one part of the system might affect other components"* ([VirtusLab — How Claude Code Works](https://virtuslab.com/blog/ai/how-claude-code-works)); risk summaries like *"Updated payment validation could affect checkout, refund, subscription renewals"* ([Augment Code](https://www.augmentcode.com/tools/best-coding-llms-that-actually-work)) |
| **Find similar code** | Cody, Continue, Cursor | Semantic + lexical hybrid search ([GitHub — Towards NL Semantic Code Search](https://github.blog/ai-and-ml/machine-learning/towards-natural-language-semantic-code-search/), [CodeSearchNet](https://github.com/github/CodeSearchNet)) |
| **Summarize a module / subsystem** | All, strongest for onboarding | *"Junior engineer onboarding (domain knowledge gaps)"* as top-4 Cody use case ([Qualtrics](https://sourcegraph.com/case-studies/qualtrics-speeds-up-unit-tests-and-code-understanding-with-cody)); *"new developers can quickly get up to speed with new codebases"* ([AWS — Boomi](https://aws.amazon.com/solutions/case-studies/boomi-case-study/)) |
| **Generate a diagram of this subsystem** | Emerging; Mermaid fences + LLM | Claude Code / Cursor render Mermaid in responses; ([O'Reilly — Reverse Engineering your architecture with Claude Code](https://www.oreilly.com/radar/reverse-engineering-your-software-architecture-with-claude-code-to-help-claude-code/)) |
| **Generate tests for this** | Highest-ROI reported | Qualtrics: **1 day → 10 minutes = 24×** ([Qualtrics](https://sourcegraph.com/case-studies/qualtrics-speeds-up-unit-tests-and-code-understanding-with-cody)) |
| **Why is this here** (blame + RAG) | Under-explored; high potential | No dominant product implementation found, but aider/Cody's symbol+history context makes it trivially derivable; noted as an open gap |
| **What-if / impact of a change** | Claude Code agentic loop | *"analyze the impact of potential changes"* ([VirtusLab](https://virtuslab.com/blog/ai/how-claude-code-works)) |

The **reading-and-navigation patterns** (explain, find, trace, summarize, diagram) map almost perfectly to iw-ai-core's dashboard context, where users are *reading* code modules, not editing them. The **write-oriented patterns** (autocomplete, inline diff) are IDE-only and not relevant to the dashboard chat.

### F4 — Retrieval/grounding is the single biggest driver of success [HIGH]

The 2026 **"Practical Code RAG at Scale"** paper (arXiv 2510.20609) tested chunking and retrieval strategies head-to-head ([arXiv 2510.20609](https://arxiv.org/html/2510.20609)):

- **BM25 with word-level splitting** beats dense embeddings for **code→code retrieval** — and is ~10× faster.
- **Dense embeddings** win for **natural-language→code retrieval**: Voyager-3-Code 0.72 NDCG vs 0.57 BM25, at 100× latency.
- **Line-based chunking matches or exceeds syntax-aware splitting** in most tasks (surprising, and simplifies implementation).
- **Chunk size should scale with the model's context budget**: 32–64 lines for small (≤4K), 64–128 for medium, whole-file for ≥16K.
- **Graph/dataflow approaches (DraCo, path-distance)** help at large context but mostly converge to chunking performance.

**Hybrid BM25 + dense** is the canonical production pattern: BM25 catches exact identifier/symbol matches (which dense embeddings miss), dense catches semantic intent (which BM25 misses), and **Reciprocal Rank Fusion / linear weighting** merges them. Dynamic Alpha Tuning (DAT) adds 6–7 points over static weighting ([Elastic — Hybrid search guide](https://www.elastic.co/what-is/hybrid-search), [LanceDB — BM25+Semantic](https://www.lancedb.com/blog/hybrid-search-combining-bm25-and-semantic-search-for-better-results-with-lan-1358038fe7e6)).

**Aider's repo map** offers a structurally different approach: tree-sitter AST extraction of classes/functions/signatures, then a **PageRank-style graph-ranking algorithm** over the file-dependency graph to select the N most-referenced identifiers that fit a token budget (default 1,000 tokens) ([aider — Repository Map](https://aider.chat/docs/repomap.html), [aider — Better repo map with tree-sitter](https://aider.chat/2023/10/22/repomap.html)). This is effectively a cheap, deterministic "compressed index" and an excellent complement to (not replacement for) embedding-based RAG.

**Continue.dev** exposes this as a user-visible taxonomy: 18 distinct context providers including `@Codebase` (embed + re-rank), `@Folder` (scoped), `@Code` (symbol), `@Repo-Map` (aider-style outline), `@Problems` (linter/LSP), `@Docs`, `@Search`, `@Diff`, `@Terminal`, `@Debugger` ([Continue context providers](https://docs.continue.dev/customize/custom-providers)). The diversity itself is a lesson: **one retrieval path is not enough** — users need explicit scoping controls.

### F5 — Inline citations + jump-to-source is the trust contract [HIGH]

**Citations are not optional.** Cody explicitly "cites the sources it uses to generate responses" and surfaces them as **context chips** showing type (repo / file / symbol / webpage) ([Sourcegraph — Cody chat](https://sourcegraph.com/docs/cody/capabilities/chat), [Sourcegraph blog — Cody VS Code 1.24](https://sourcegraph.com/blog/cody-vscode-1-24-0-release)). Simon Willison's widely-shared analysis notes that code hallucinations are *less* dangerous than prose hallucinations only because a bad API call fails fast when run — but in a **read-only dashboard context, there's no runtime to catch it**, which elevates the citation requirement ([simonwillison.net — Hallucinations in code](https://simonwillison.net/2025/Mar/2/hallucinations-in-code/)).

Chrome's developer guidance is unambiguous on how to render streamed model output safely: treat it as user-generated content, use **DOMPurify or sanitize-html** on the accumulated buffer (not per-chunk — dangerous sequences can split across chunks), and **stop rendering immediately** if the sanitizer flags content ([Chrome for Developers — Rendering LLM responses](https://developer.chrome.com/docs/ai/render-llm-responses)). Overlap with R-00048's rendering guidance is intentional and confirms the pipeline.

### F6 — Anti-patterns are well-documented and avoidable [HIGH]

| Anti-pattern | Why it fails | Evidence |
|---|---|---|
| **Naive RAG over raw files** | Loses symbol semantics; chunks mid-function; hallucinates APIs | [HN — leapfrogging traditional vector RAG](https://news.ycombinator.com/item?id=40998497); [Qodo — RAG for 10k repos](https://www.qodo.ai/blog/rag-for-large-scale-code-repos/) |
| **No citations / no jump-to-source** | Devs can't verify → trust collapses | [InfoWorld — Keep AI hallucinations out](https://www.infoworld.com/article/3822251/how-to-keep-ai-hallucinations-out-of-your-code.html); DORA's 30% "little or no trust" datapoint ([DORA 2025](https://dora.dev/research/2025/dora-report/)) |
| **Hallucinated APIs / packages** | Supply-chain risk when adversaries register hallucinated names | [arXiv 2512.12117 — Preventing hallucination via hybrid retrieval](https://www.arxiv.org/pdf/2512.12117); [InfoWorld](https://www.infoworld.com/article/3822251/how-to-keep-ai-hallucinations-out-of-your-code.html) |
| **No scoping controls** | User can't focus the chat on a module → irrelevant retrieval | [Continue — context providers](https://docs.continue.dev/customize/custom-providers) |
| **Forcing manual context re-entry** | Prompting overhead eats savings — source of the METR 19% | [Augment — 19% slower](https://www.augmentcode.com/guides/why-ai-coding-tools-make-experienced-developers-19-slower-and-how-to-fix-it) |
| **Dependency hallucination in dashboards** | No runtime to catch the error; false confidence | [simonwillison.net](https://simonwillison.net/2025/Mar/2/hallucinations-in-code/) (inverse implication) |
| **Opaque context window** | User doesn't know what the model sees | [Copilot Chat context docs](https://code.visualstudio.com/docs/copilot/chat/copilot-chat-context) — token meter is a standard |
| **Generic "ask me anything" input** | No discoverability of capabilities → low activation | Covered by slash commands / context pills in R-00048 |

### F7 — For a read-first dashboard, chat is genuinely additive over existing panels [MEDIUM]

iw-ai-core's dashboard already has a file tree, symbol search, module pages, and (for some projects) dependency graph visualisations. A code-aware chat adds value **where these fail**:

- **Natural-language intent**: "find the function that handles 403s on /api/jobs" cannot be expressed in a tree.
- **Multi-hop answers**: "what calls this, and what does *that* in turn call?" — dependency graphs show the edges, but don't *narrate* them.
- **Summarisation**: a 1,200-line module condensed to 5 bullets with citations is what a reader actually wants. The file tree can't do this.
- **Onboarding / orientation**: Qualtrics & Boomi both flagged junior-developer onboarding as a top-3 ROI use case — and the dashboard is the natural home for it (new joiners read dashboards before they open an IDE).
- **"Why is this here"**: blame + commit history + RAG combined → a chat response is literally the only UI where this composite answer fits.

**Where it's novelty, not value**: generating new code in a read-only dashboard (no runtime, no tests, no apply-and-edit loop) falls into the METR trap. Scope the MVP to **read, navigate, explain, diagram** — not "write the patch for me".

### F8 — What to measure: leading and lagging metrics [MEDIUM]

Production LLM chat evaluation has settled on a mix of implicit and explicit signals because explicit thumbs up/down is sparse ([Medium — Evaluating LLM chatbots](https://medium.com/data-science-at-microsoft/evaluating-llm-based-chatbots-a-comprehensive-guide-to-performance-metrics-9c2388556d3e), [Confident AI — LLM metrics](https://www.confident-ai.com/blog/llm-evaluation-metrics-everything-you-need-for-llm-evaluation), [Evidently — LLM eval metrics](https://www.evidentlyai.com/llm-guide/llm-evaluation-metrics)):

**Leading indicators (hours-to-days after ship)**:
- Time-to-first-token (TTFT) median + p95
- Answer length & streaming completion rate
- Citations-per-answer (expect ≥1, prefer ≥3 for multi-file questions)
- **Citation click-through rate** (did the user click through to source?)
- Context-chip use rate (users scoping the chat via @-mentions)
- Slash-command use rate (activation of advertised capabilities)
- Apology rate / no-response rate ([Evidently](https://www.evidentlyai.com/llm-guide/llm-evaluation-metrics))

**Lagging indicators (weeks-to-months)**:
- Session length; repeat-use rate (did users come back?)
- Thumbs-up rate on answers that got a citation click
- Downstream action rate (did the answer lead to navigating, opening a file, filing an issue?)
- Time-to-first-useful-answer for new project members (onboarding proxy)
- Reduction in repetitive "where is X" support questions in project Slack/comments

Explicit evaluation alongside the production metrics: **LLM-as-a-judge** on a held-out test set of representative queries, scoring factuality + relevance + citation accuracy ([Confident AI](https://www.confident-ai.com/blog/llm-evaluation-metrics-everything-you-need-for-llm-evaluation)).

---

## Killer Use Cases for iw-ai-core (ranked by evidence strength)

Each with a one-line implementation sketch for our FastAPI + htmx + Jinja2 stack, assuming the R-00048 UX layer (docked right panel + SSE streaming).

1. **Explain this module/symbol** [HIGH]. Pre-seed the chat with `#module:<current>` when the user opens a module page; stream a structured response (purpose, key symbols, dependencies, gotchas) with inline citations to `code_symbols` rows. *Impl*: `POST /chat/explain` → RAG against `code_chunks` scoped to the module → stream answer via `StreamingResponse`.

2. **Where is this used / find references** [HIGH]. Button on any symbol → "find usages" prompt → LLM returns a grouped list (file → usage type) with jump links. *Impl*: combine our existing `code_edges` (call graph) with RAG over callsite context; render as htmx partial.

3. **Summarize a module for onboarding** [HIGH]. `/onboard` slash command → answers "what is this module, who owns it, what are the top 5 files, what should I read first?" *Impl*: same retrieval as #1 plus project README/owners metadata; one-shot cacheable.

4. **Trace flow across modules** [HIGH]. `/trace <symbol>` → LLM walks the call chain, citing each hop, producing a ranked list with a Mermaid sequence diagram. *Impl*: multi-turn internal tool loop; budget-limited to N hops; cache by `(symbol_id, version_sha)`.

5. **Generate a Mermaid diagram of this subsystem** [HIGH]. `/diagram` slash command → LLM writes `mermaid` fenced code → client validates + renders. *Impl*: confined prompt template; max-node budget; render via the markdown pipeline from R-00048.

6. **Write tests for this function** [HIGH]. Highest-ROI pattern (Qualtrics 24× finding) but **only once editing is in scope**; for MVP, return a *drafted* test block the user can copy. *Impl*: prompt template + RAG over similar existing tests in the project.

7. **"Why is this here" (blame + history + RAG)** [MEDIUM]. Under-explored in competitors — a differentiator. Combine the last N blame entries + PR messages that touched the symbol + RAG context → LLM narrates the rationale. *Impl*: needs a blame service (we have git access per project); one prompt, heavy context.

8. **Natural-language code search** [MEDIUM]. Free-text query → hybrid BM25 + embeddings over `code_chunks` → top-K with LLM-generated rationale ("why this matches"). *Impl*: piggyback on the planned hybrid retrieval layer.

9. **Impact analysis / what-would-break** [MEDIUM]. "I'm about to change X — what should I check?" → walks reverse call graph + tests + RAG. *Impl*: agentic multi-step; defer until we have the tool-call plumbing from the broader orchestration platform.

10. **Compare two modules / versions** [LOW]. "What changed between v1 and v2 of module X?" → diff + RAG. *Impl*: niche; park for later.

**MVP recommendation**: ship #1, #2, #3, #5, plus free-form chat (#8 fallback). Defer #4, #6, #7, #9 to a second milestone.

---

## Expected Gains

| Gain | Mechanism | Leading metric | Lagging metric |
|---|---|---|---|
| Faster code comprehension | Explain-module and summarize on one SSE round-trip | Mean TTFT; answer-length distribution | Qualtrics-style "25% faster to answer code questions" self-report |
| Shorter onboarding | Onboard slash command + summarize for new joiners | `/onboard` use rate in first 7 days | Time-to-first-commit for new project members |
| Fewer IDE/dashboard exits | In-context answers with citations | Citation click-through rate | Qualtrics-style "28% fewer IDE exits" equivalent |
| Better cross-module navigation | Trace + find-usages grounded in call graph | Jump-to-source click-through | Reduction in "where is X" questions in issue comments |
| Diagram-on-demand | `/diagram` + Mermaid pipeline | `/diagram` use rate; render success rate | Documentation debt reduction (subjective survey) |
| Test generation (future) | Test-gen prompt + RAG over existing tests | Test block copy/paste rate | Qualtrics-style unit-test time reduction |
| Trust in platform | Inline citations, scoping, jump-to-source | Thumbs-up on cited answers | Return-user rate after first session |

**Realistic targets**, calibrated off enterprise case studies:
- Median TTFT: <1.5s (enables "flow" per GitHub SPACE findings)
- Citations-per-answer: ≥2 for module/symbol questions
- Citation click-through: ≥25%
- Repeat-use rate (user returns within 7 days): ≥40%
- Self-reported "helpful" rate on first-time answers: ≥60%

---

## Anti-patterns to avoid (explicit NO list for iw-ai-core)

- ❌ **No generic "one-shot RAG over raw file contents"** — chunk-align with symbols, use hybrid BM25+embeddings.
- ❌ **No answers without citations** — every answer must have ≥1 source link, and the UI must make it clickable.
- ❌ **No silent context** — show context chips and a token meter (R-00048 F5); the user must see what the model sees.
- ❌ **No "force re-prompting"** — preserve module/symbol context across turns without the user re-typing @-mentions.
- ❌ **No write-oriented features in MVP** — no "apply this patch" button until we have an editing story.
- ❌ **No uncaptioned Mermaid / image output** — always include a one-line text summary (accessibility + fallback).
- ❌ **No shadcn/assistant-ui-style React components** — we're on htmx; borrow the *primitives list*, not the implementation.

---

## Limitations

- **No code-base audit performed** (deep-mode rule); recommendations assume R-00048's UX work and the existing `code_chunks`/`code_symbols`/`code_edges` tables are present. Verify current schema during CR scoping.
- **Enterprise case studies are self-reported by vendors** (Sourcegraph, AWS). Headline percentages should be treated as upper-bound marketing numbers, not peer-reviewed science. Independent data (DORA, arXiv studies, METR) is more reliable but tells a more mixed story.
- **2025 DORA headline page did not expose specific numbers via WebFetch** — numbers cited come from the Faros summary and Google Cloud announcement blog, not the primary PDF. A follow-up reading of the full PDF is recommended before citing any figure in user-facing docs.
- **The "why is this here" pattern is under-evidenced** — no dominant product implementation was found in the searches. Confidence on its value is based on first-principles (blame + RAG) rather than deployment data.
- **Latency numbers from arXiv 2510.20609** are workload-specific; our production retrieval numbers will differ and must be re-measured.
- **METR sample is small and skews to experienced open-source maintainers** — its 19% slowdown finding may not generalise to the corporate "read + understand" workflow that describes most dashboard users.

---

## Sources

| # | Title | Credibility | URL |
|---|---|---|---|
| 1 | DORA 2025 — State of AI-assisted Software Development | Official research (HIGH) | https://dora.dev/research/2025/dora-report/ |
| 2 | Google Cloud Blog — Announcing 2025 DORA Report | Official (HIGH) | https://cloud.google.com/blog/products/ai-machine-learning/announcing-the-2025-dora-report |
| 3 | Faros — DORA 2025 key takeaways | Vendor summary | https://www.faros.ai/blog/key-takeaways-from-the-dora-report-2025 |
| 4 | GitHub blog — Quantifying Copilot's impact on productivity | First-party (HIGH) | https://github.blog/news-insights/research/research-quantifying-github-copilots-impact-on-developer-productivity-and-happiness/ |
| 5 | Ziegler et al. — The Impact of AI on Developer Productivity (arXiv 2302.06590) | Peer-reviewed (HIGH) | https://arxiv.org/abs/2302.06590 |
| 6 | Microsoft/Accenture Field Experiment — GitHub Copilot | Academic (HIGH) | https://mit-genai.pubpub.org/pub/v5iixksv |
| 7 | Longitudinal mixed-methods case study (arXiv 2509.20353) | Peer-reviewed | https://arxiv.org/html/2509.20353v2 |
| 8 | Augment — Why AI tools make experienced devs 19% slower (METR) | Vendor, cites METR | https://www.augmentcode.com/guides/why-ai-coding-tools-make-experienced-developers-19-slower-and-how-to-fix-it |
| 9 | Practical Code RAG at Scale (arXiv 2510.20609) | Peer-reviewed (HIGH) | https://arxiv.org/html/2510.20609 |
| 10 | Preventing LLM Hallucination via Hybrid Retrieval (arXiv 2512.12117) | Peer-reviewed | https://www.arxiv.org/pdf/2512.12117 |
| 11 | Sourcegraph — Cody is enterprise ready | First-party (HIGH) | https://sourcegraph.com/blog/cody-is-enterprise-ready |
| 12 | Sourcegraph — Qualtrics case study | First-party case study | https://sourcegraph.com/case-studies/qualtrics-speeds-up-unit-tests-and-code-understanding-with-cody |
| 13 | Sourcegraph — Case studies index (Palo Alto, Leidos, etc.) | First-party | https://sourcegraph.com/case-studies |
| 14 | Sourcegraph — Cody chat (official docs) | Official docs (HIGH) | https://sourcegraph.com/docs/cody/capabilities/chat |
| 15 | Sourcegraph blog — Cody VS Code 1.24 (context chips) | First-party | https://sourcegraph.com/blog/cody-vscode-1-24-0-release |
| 16 | AWS — Boomi case study (Amazon Q) | First-party case study | https://aws.amazon.com/solutions/case-studies/boomi-case-study/ |
| 17 | AWS — DTCC case study | First-party | https://aws.amazon.com/solutions/case-studies/dtcc-case-study/ |
| 18 | AWS — nnamu case study | First-party | https://aws.amazon.com/solutions/case-studies/nnamu/ |
| 19 | aider — Repository Map docs | First-party (HIGH) | https://aider.chat/docs/repomap.html |
| 20 | aider — Building a better repo map with tree-sitter (2023) | First-party engineering blog | https://aider.chat/2023/10/22/repomap.html |
| 21 | Continue.dev — Context providers docs | Official docs | https://docs.continue.dev/customize/custom-providers |
| 22 | VS Code — Copilot Chat context docs | Official Microsoft docs (HIGH) | https://code.visualstudio.com/docs/copilot/chat/copilot-chat-context |
| 23 | VirtusLab — How Claude Code works | Engineering analysis | https://virtuslab.com/blog/ai/how-claude-code-works |
| 24 | O'Reilly — Reverse-engineering architecture with Claude Code | Editorial (HIGH) | https://www.oreilly.com/radar/reverse-engineering-your-software-architecture-with-claude-code-to-help-claude-code/ |
| 25 | TechJack Solutions — Cursor IDE 2026 overview | Independent review | https://techjacksolutions.com/ai/ai-development/cursor-ide-what-it-is/ |
| 26 | Cursor — Best practices for coding with agents | First-party | https://cursor.com/blog/agent-best-practices |
| 27 | Chrome for Developers — Rendering LLM responses | Official Chrome team (HIGH) | https://developer.chrome.com/docs/ai/render-llm-responses |
| 28 | simonwillison.net — Hallucinations in code are the least dangerous | Engineering analysis (HIGH) | https://simonwillison.net/2025/Mar/2/hallucinations-in-code/ |
| 29 | InfoWorld — How to keep AI hallucinations out of your code | Editorial | https://www.infoworld.com/article/3822251/how-to-keep-ai-hallucinations-out-of-your-code.html |
| 30 | GitHub blog — Towards NL Semantic Code Search | First-party research | https://github.blog/ai-and-ml/machine-learning/towards-natural-language-semantic-code-search/ |
| 31 | CodeSearchNet (GitHub × MSR) | Benchmark dataset (HIGH) | https://github.com/github/CodeSearchNet |
| 32 | Elastic — Hybrid search guide | Vendor docs | https://www.elastic.co/what-is/hybrid-search |
| 33 | LanceDB — Hybrid search: BM25 + semantic | Vendor blog | https://www.lancedb.com/blog/hybrid-search-combining-bm25-and-semantic-search-for-better-results-with-lan-1358038fe7e6 |
| 34 | Augment Code — Best coding LLMs (LSP-integrated) | Vendor analysis | https://www.augmentcode.com/tools/best-coding-llms-that-actually-work |
| 35 | Qodo — RAG for 10k repos | Vendor engineering blog | https://www.qodo.ai/blog/rag-for-large-scale-code-repos/ |
| 36 | HN — Leapfrogging traditional vector RAG with a language map | Community (aider context) | https://news.ycombinator.com/item?id=40998497 |
| 37 | Confident AI — LLM evaluation metrics guide | Vendor guide | https://www.confident-ai.com/blog/llm-evaluation-metrics-everything-you-need-for-llm-evaluation |
| 38 | Evidently AI — LLM evaluation metrics | Vendor guide | https://www.evidentlyai.com/llm-guide/llm-evaluation-metrics |
| 39 | Medium (Microsoft) — Evaluating LLM-based chatbots | Practitioner article | https://medium.com/data-science-at-microsoft/evaluating-llm-based-chatbots-a-comprehensive-guide-to-performance-metrics-9c2388556d3e |
| 40 | Developer Experiences with Contextualized AI Coding Assistant (arXiv 2311.18452) | Peer-reviewed | https://arxiv.org/abs/2311.18452 |

# Natural-Language Code Q&A for Non-Technical Users Linked to Work Item History

**Research ID**: R-00057
**Date**: 2026-04-19
**Mode**: deep
**Depth**: deep
**Primary Question**: Do any existing tools let a non-technical user ask natural-language questions about observable software behavior ("what does button X do?") and receive both a functional explanation *and* a linked history of work items (Features/CRs/Incidents/PRs) that shaped that behavior — and if so, how?

---

## Executive Summary

No commercial tool today combines all three ingredients the user described: **(a)** NL queries about observable behavior from **(b)** a non-technical user, answered with **(c)** a narrative history of work items that shaped that behavior. The closest analog is [Unblocked](https://getunblocked.com), which ingests code, Jira, Slack, PRs, and docs into a contextual knowledge graph, but it targets developers and does not emphasize behavior-level or UI-element queries. All major codebase-Q&A tools (Cursor, Copilot, Cody, Augment, Glean, Greptile, Bloop) assume a developer user inside an IDE and treat work-item history as secondary context, not primary output. The genuine whitespace is the intersection of **business-user framing + observable-behavior resolution + work-item-narrative history**, all of which the project's existing squash-merge → work-item-ID convention makes unusually cheap to support.

## Background

Enhancing the code analysis and AI chat agent in iw-ai-core. The user wants non-technical stakeholders to ask "what does button X do?" and get a functional explanation plus a timeline of the Features, CRs, and Incidents that created or changed that behavior — leveraging the project's structured squash-merge commits (`Merge CR-00010: ...`) that already map 1:1 to work items. Research was commissioned to check prior art before committing implementation effort.

---

## Findings

### No tool directly addresses the full use case [HIGH confidence]

Across ten commercial tools examined — Unblocked, Sourcegraph Cody, Cursor, GitHub Copilot Spaces/Workspace, Augment Code, Glean, Bloop, Greptile, Notion Enterprise Search, Dust — none matches the combination of non-technical user framing, observable-behavior (UI/feature-level) resolution, and explicit work-item-history narrative as a first-class answer type. Tools either address developer codebase Q&A with some history context ([Unblocked](https://getunblocked.com), [Glean](https://www.glean.com/blog/code-search-code-writer-jan-drop-2026)), developer code Q&A without history ([Cursor](https://docs.cursor.com/context/codebase-indexing), [Sourcegraph Cody](https://sourcegraph.com/blog/how-cody-understands-your-codebase)), or non-technical chatbots over code with no history integration ([Bridging the Gap Medium article](https://ravjot03.medium.com/bridging-the-gap-a-chatbot-that-explains-code-to-non-technical-stakeholders-c9f0a1b85583)).

### Unblocked is the closest analog but targets developers [HIGH confidence]

Unblocked ingests codebase + Jira/Linear/Asana + Slack/Teams + Confluence/Notion/Google Drive + GitHub PRs into "a knowledge graph that traverses connections between Jira issues, PRs, Slack discussions, code, and docs, ranking by recency and authority while de-conflicting when sources disagree" per the [TechCrunch Series A coverage](https://techcrunch.com/2025/05/06/unblocked-raises-20-million-for-its-ai-assistant-to-help-devs-understand-legacy-codebases/) and confirmed via the [Unblocked homepage](https://getunblocked.com). Positioning is explicitly developer-focused: "another expert on the team, available 24/7" per the [Series A blog post](https://getunblocked.com/blog/series-a/), with secondary audiences as engineering managers. The product does not demonstrate UI-element or behavior-level resolution, and the blog post fetched does not describe a feature that takes an observable behavior and returns the work items that shaped it as a narrative.

### Major IDE codebase-Q&A tools treat history as secondary context, not output [HIGH confidence]

[Cursor](https://docs.cursor.com/context/codebase-indexing) uses vector embeddings via Turbopuffer and can "fetch relevant PRs into context" when asked, but the PRs are retrieval context for a developer answer, not a narrative output for a business reader. [Sourcegraph Cody](https://sourcegraph.com/blog/how-cody-understands-your-codebase) deprecated embeddings in favor of BM25-based keyword retrieval and makes no claim to link answers to commits, PRs, or tickets. [GitHub Copilot Spaces](https://docs.github.com/en/copilot/concepts/context/spaces) lets users organize "repositories, code, pull requests, issues, free-text content" as Q&A context but does not advertise work-item-history as an answer format. [Augment Code](https://www.augmentcode.com/) indexes "commit history, cross-repo dependencies, and architectural patterns" in its Context Engine but its read-only Q&A mode is still pitched at developers tracing dependencies. In all four, work-item history is *input* to answers about code, not the answer itself.

### UI-element → source-code resolution for business users is genuine whitespace [HIGH confidence]

No commercial code-Q&A tool examined advertises the ability to take an observable UI reference ("the submit button on the checkout page") and resolve it to the corresponding source, let alone the work items that touched it. Academic and Google-open-source work exists on NL-to-UI mapping for automation ([Google's mobile UI action mapping](https://www.infoq.com/news/2020/07/google-mobile-ai/), [NLDesign](https://dl.acm.org/doi/fullHtml/10.1145/3674399.3674455)), but these convert NL to UI actions for agents, not UI elements back to source history. The closest patterns in web tooling are [Chrome DevTools AI Assistant](https://developer.chrome.com/docs/devtools/ai-assistance) and [Open Web Inspector](https://chromewebstore.google.com/detail/open-web-inspector-ai-ele/agijlmbamhdjgdehdcginejjnlkheeam), which let users click elements and ask AI about their CSS/DOM — but neither traverses to source repositories or work-item history. The `data-testid` / aria-label convention that frontend teams use for testing ([Kent C. Dodds on resilient UI tests](https://kentcdodds.com/blog/making-your-ui-tests-resilient-to-change)) is the natural bridge and is widely present in modern codebases, but no code-Q&A tool currently exploits it as a resolution key.

### Narrative Version Control (academic) matches the target UX most closely [MEDIUM confidence]

The [Narrative Version Control proposal](https://thoughts-and-experiments.github.io/Narrative-Version-Control/) explicitly proposes "progressive disclosure" across three tiers — feature milestones for executives, engineering reasoning for managers, raw code plus conversation for developers — and treats intent/conversation as the primary versioning unit. This is the only source found that designs the UX for non-technical consumption of code history. Critically, it does *not* emphasize external work-item linkage (Jira/Linear/GitHub issues), focusing instead on LLM conversation as the narrative substrate. The project's work-item-first world (Features/CRs/Incidents already curated with titles and summaries) is a much richer narrative substrate than raw LLM conversations, suggesting the same UX pattern applied to a superior data source.

### Work-item-to-commit linkage is technically solved; the novelty is presentation [HIGH confidence]

Every modern PM/code stack already supports linking work items to commits and PRs: [Linear](https://linear.app/docs/github-integration) auto-detects branch names and PR titles containing issue IDs, [Jira's GitHub integration](https://www.atlassian.com/software/jira/product-discovery/guides/integrations/overview) does the same, and the project's own squash-merge convention (`Merge CR-00010: ...`) encodes the mapping directly in commit message first lines, making `git log --follow -- <file>` sufficient to extract work-item IDs without any new infrastructure. The novelty in the user's idea is *not* the linkage but the **presentation of that linkage as a narrative answer to a non-technical observer**.

### Lore protocol is a complementary building block [MEDIUM confidence]

The [Lore arxiv paper](https://arxiv.org/html/2603.15566v1) proposes git commit trailers encoding constraints, rejected alternatives, risk, and directives, enabling AI agents to query decision history before modifying code. It is complementary to — not competitive with — the user's feature: Lore enriches the per-commit record; the user's feature aggregates records across commits into a human narrative. The paper explicitly lists "linking commits to external work items" as outside its scope, which aligns with what the user's feature would contribute.

### Glean and Notion Enterprise Search overlap but answer as generalists [MEDIUM confidence]

[Glean](https://www.glean.com/blog/code-search-code-writer-jan-drop-2026) claims to surface "the flag definition, and the PR that changed default behavior" in responses, spanning code + PRs + commits + docs + tickets. [Notion Enterprise Search](https://www.notion.com/product/enterprise-search) connects Jira + GitHub + Slack and returns "details from JIRA tickets, related pull requests, and design files in one search." Both are generalist enterprise-search tools whose code capabilities are recent additions; neither resolves observable behavior to source, and their answers are retrieval mashups rather than curated work-item narratives. They are the right comparison class for what a "generalist" attempt at this feature would look like — and they fall short on the specific angle the user is pursuing.

### Simple non-technical-stakeholder chatbots exist but ignore history [LOW confidence]

A [Medium tutorial](https://ravjot03.medium.com/bridging-the-gap-a-chatbot-that-explains-code-to-non-technical-stakeholders-c9f0a1b85583) demonstrates a LangChain + embeddings pipeline aimed at "clients, managers, and business executives" asking codebase questions in plain language, but contains "zero discussion of linking answers to commits, pull requests, or work-item history," per the fetched summary. This is representative of a category of DIY pipelines: the non-technical-framing problem is recognized in the dev-education space, but the history-linkage problem is not. Confidence is LOW because this is based on one tutorial; there may be private enterprise tools solving this that do not publish.

---

## Recommendations

1. **Primary**: Build the feature. The research confirms meaningful whitespace at the intersection of (a) non-technical user framing, (b) observable-behavior resolution, and (c) work-item-narrative history. The project's existing assets — structured squash-merge commits with work-item IDs, curated Features/CRs/Incidents with titles and summaries, and a chat agent already wired to the codebase — lower the build cost dramatically compared to a greenfield effort. Position the feature as **"ask about what users see, get back a functional explanation and the story of how it came to be"** rather than another codebase chat.

2. **Alternative**: If end-to-end NL-to-UI-to-code resolution proves too unreliable in v1, fall back to a **hybrid picker model** — browser-extension or screenshot-annotation flow where the user indicates the UI element (via click or highlight), and only the *question* is natural language. This preserves the non-technical UX (no file/symbol selection) while sidestepping the hardest retrieval problem. Narrative Version Control's [progressive-disclosure UX](https://thoughts-and-experiments.github.io/Narrative-Version-Control/) (high-level summary → expand to work items → expand to code) is a directly applicable pattern for the answer format.

3. **Avoid**: Do not pitch this as "codebase chat for non-developers." That framing puts the product in direct comparison with Unblocked, Glean, Copilot, and Cursor — all of which are better resourced and all of which address a different (developer) audience. The differentiator collapses if the feature is described by its input (NL) or its corpus (code). Describe it by its output: **a functional narrative tied to work-item history**, which is the unusual part.

---

## Follow-up Research Proposals

Based on whitespace findings, two follow-up deep researches would de-risk implementation:

- **R-TBD-A: NL-to-UI-element resolution techniques for code Q&A** — deep dive into practical approaches: `data-testid`/aria mining, screenshot + vision model, DOM snapshot + agentic retrieval, component-tree traversal, Playwright accessibility snapshot. Covers accuracy trade-offs and implementation cost for each.
- **R-TBD-B: Work-item-narrative answer presentation patterns** — deep dive into how to format the *answer* for business users: timeline vs. per-item cards vs. change summary; how much technical jargon to retain; prior art from release-notes automation tools (e.g., Release.com, GitStart), Narrative VC, and product-changelog tools.

Recommend kicking these off after the user reviews this landscape document.

---

## Limitations

- **Time-bounded to April 2026.** Unblocked, Cursor, Copilot, Glean are all iterating rapidly; features documented here may exist by H2 2026 that were not in scope at time of research.
- **Commercial-tool coverage only for major players.** Niche or internal enterprise tools (e.g., Google's internal Code Search + LLMs, Meta's equivalent) are not public and are excluded.
- **No hands-on evaluation.** Findings are based on vendor documentation, blog posts, and third-party reviews — not on direct use of each tool against a reference question. Vendor claims may overstate capabilities.
- **UI-element-to-code whitespace claim is a negative result** ("could not find a tool that does X"). Absence of evidence is not evidence of absence; a tool may exist that was not surfaced by the 11 search queries.
- **Non-technical-user framing in vendor docs is often aspirational.** Tools like Glean and Copilot Spaces claim broad audiences but their actual UX assumes developer mental models; finer evaluation would require user testing with actual PMs / support staff.
- **No evaluation of pricing, licensing, or deployability.** Several candidates (Glean, Unblocked, Augment) are enterprise-licensed; competitive positioning was not assessed.

---

## Sources

| # | Source | Credibility | URL |
|---|--------|-------------|-----|
| 1 | Unblocked — product homepage | HIGH | https://getunblocked.com |
| 2 | Unblocked — Series A blog post | HIGH | https://getunblocked.com/blog/series-a/ |
| 3 | TechCrunch — Unblocked raises $20M | HIGH | https://techcrunch.com/2025/05/06/unblocked-raises-20-million-for-its-ai-assistant-to-help-devs-understand-legacy-codebases/ |
| 4 | Sourcegraph — How Cody understands your codebase | HIGH | https://sourcegraph.com/blog/how-cody-understands-your-codebase |
| 5 | Cursor — Codebase indexing docs | HIGH | https://docs.cursor.com/context/codebase-indexing |
| 6 | GitHub Docs — Copilot Spaces | HIGH | https://docs.github.com/en/copilot/concepts/context/spaces |
| 7 | GitHub Blog — Copilot Workspace | HIGH | https://github.blog/news-insights/product-news/github-copilot-workspace/ |
| 8 | Augment Code — product page | HIGH | https://www.augmentcode.com/ |
| 9 | Glean — Code search and code writer blog | HIGH | https://www.glean.com/blog/code-search-code-writer-jan-drop-2026 |
| 10 | Greptile vs Bloop comparison | MEDIUM | https://slashdot.org/software/comparison/Bloop.ai-vs-Greptile/ |
| 11 | Bloop — GitHub repository | HIGH | https://github.com/BloopAI/bloop |
| 12 | Watermelon — GitHub repository (archived 2024-03) | HIGH | https://github.com/watermelontools/watermelon |
| 13 | Lore arxiv paper — commit messages as structured knowledge | HIGH | https://arxiv.org/html/2603.15566v1 |
| 14 | Narrative Version Control — proposal | MEDIUM | https://thoughts-and-experiments.github.io/Narrative-Version-Control/ |
| 15 | Martin Fowler — AI-assisted onboarding to legacy codebase | HIGH | https://martinfowler.com/articles/exploring-gen-ai/09-ai-help-onboarding-codebase.html |
| 16 | Medium — Bridging the Gap chatbot for non-technical stakeholders | LOW | https://ravjot03.medium.com/bridging-the-gap-a-chatbot-that-explains-code-to-non-technical-stakeholders-c9f0a1b85583 |
| 17 | Linear — GitHub integration docs | HIGH | https://linear.app/docs/github-integration |
| 18 | Atlassian — Jira Product Discovery integrations | HIGH | https://www.atlassian.com/software/jira/product-discovery/guides/integrations/overview |
| 19 | Notion — Enterprise Search product page | HIGH | https://www.notion.com/product/enterprise-search |
| 20 | Dust.tt — product page | MEDIUM | https://dust.tt/home/product |
| 21 | Kent C. Dodds — Making UI tests resilient to change | HIGH | https://kentcdodds.com/blog/making-your-ui-tests-resilient-to-change |
| 22 | Chrome DevTools AI Assistance | HIGH | https://developer.chrome.com/docs/devtools/ai-assistance |
| 23 | Open Web Inspector Chrome extension | MEDIUM | https://chromewebstore.google.com/detail/open-web-inspector-ai-ele/agijlmbamhdjgdehdcginejjnlkheeam |
| 24 | InfoQ — Google Open-Sources AI for Mapping NL to Mobile UI | HIGH | https://www.infoq.com/news/2020/07/google-mobile-ai/ |
| 25 | NLDesign — ACM paper | HIGH | https://dl.acm.org/doi/fullHtml/10.1145/3674399.3674455 |
| 26 | Pullflow — The New Git Blame (AI attribution) | MEDIUM | https://pullflow.com/blog/the-new-git-blame/ |
| 27 | AI Blame — VS Code extension listing | MEDIUM | https://marketplace.visualstudio.com/items?itemName=skilync.ai-blame |
| 28 | Swimm docs — GitHub App | HIGH | https://docs.swimm.io/continuous-integration/github-app/ |

---

## Appendix: Research Log

**Date range**: 2026-04-19 (single session)
**Queries run**: 11 WebSearch, 9 WebFetch, 0 context7
**Mode used**: deep
**Depth level**: deep

Research covered five angles (landscape, UI-to-code resolution, work-item linkage patterns, non-technical-user framing, narrative-history presentation). The UI-to-code-mapping angle is the weakest-covered area in vendor literature, which itself is a signal: if anyone solved it publicly, they would be marketing it. Follow-up research on NL→UI→code resolution techniques is recommended before implementation.

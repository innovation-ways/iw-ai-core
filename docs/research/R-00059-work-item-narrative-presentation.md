# Work-Item-Narrative Answer Presentation Patterns for Business Users

**Research ID**: R-00059
**Date**: 2026-04-19
**Mode**: deep
**Depth**: deep
**Primary Question**: When a system answers a non-technical user's question about observable software behavior with a functional explanation *plus* the history of work items (Features/CRs/Incidents/PRs) that shaped that behavior, what presentation patterns make that answer readable, trustworthy, and actionable — and where does each pattern succeed or fail?

---

## Executive Summary

The strongest pattern synthesis across changelog tools, AI-answer UX research, and trustworthy-AI guidelines is: **functional answer first in plain language, followed by a chronological Linear-style work-item feed, with inline Perplexity-style citations between them and a strict 2–3 layer progressive-disclosure hierarchy**. Industry agreement is remarkably tight on the AI-trust side — [NN/G](https://www.nngroup.com/articles/ai-hallucinations/), [Shape of AI](https://www.shapeof.ai/patterns/citations), [Intercom](https://www.intercom.com/blog/trust-issues-help-customers-believe-your-ai-agent/), and [brics-econ.org](https://brics-econ.org/ui-patterns-for-trustworthy-generative-ai-show-sources-and-last-updated-dates) converge on the same rules (inline citations, categorical confidence, specific freshness, first-person uncertainty, no generic disclaimers). For the work-item narrative itself, [Linear's date + bold title + concise paragraph](https://www.worknotes.ai/blog/best-changelog-page-designs) is the consensus gold standard over categorized lists (GitHub), utility lists (Stripe), or image-heavy cards (Vercel). Practically: show (1) a 1-paragraph plain-language functional answer, (2) 3–5 inline-cited work items in a chronological mini-feed, (3) expand-in-place drawer per item for deeper detail, (4) a small trust strip stating item count, data freshness, and categorical confidence. Avoid chain-of-thought explanations, percentage confidence scores, generic "AI can make mistakes" footers, and raw technical language at the first layer.

## Background

Follow-up to [R-00057](./R-00057-nl-code-qa-work-item-history.md) (landscape) and [R-00058](./R-00058-nl-to-ui-element-resolution.md) (technique). Those two answered *whether* the feature is novel and *how* to resolve an NL reference to source; this one answers *how to present* the answer once the system has it, so that a non-technical stakeholder (PM, support, client) can actually read, trust, and act on it.

---

## Findings

### Linear-style clean feed is the gold-standard shape for a small work-item list [HIGH confidence]

Of the changelog tools surveyed, Linear is consistently cited as the gold standard for developer-tool presentation: [clean typography, generous whitespace, inline product screenshots for every major entry, each post gets a date, a title in bold, and a concise paragraph. There are no categories, tags, or clutter](https://www.worknotes.ai/blog/best-changelog-page-designs). Stripe opts for [pure utility — 1-3 sentence entries tagged by API version and product area, with breaking changes flagged](https://www.worknotes.ai/blog/best-changelog-page-designs); Vercel opts for [daily cards with inline screenshots](https://www.worknotes.ai/blog/best-changelog-page-designs); GitHub opts for [categorized groups by PR label (Breaking Changes, Features, Fixes)](https://docs.github.com/en/repositories/releasing-projects-on-github/automatically-generated-release-notes). For a small set (3–5 work items answering a single user question), Linear's unadorned flowing feed minimizes visual chrome and maximizes scan speed; categorization adds overhead that only pays off at catalog scale.

### Plain-language, user-benefit-first writing beats technical changelog prose for business audiences [HIGH confidence]

Both [Appcues](https://www.appcues.com/blog/release-notes-examples) and [Cycle](https://cycle.app/blog/public-changelog-best-practices-examples-make-your-product-shine-with-stunning-release-notes) are explicit: for non-technical readers, [replace technical commit notes with simple explanations of what users actually gain](https://www.appcues.com/blog/release-notes-examples), and [focus on what new features mean for the user and not for your company](https://userpilot.com/blog/release-notes-best-practices/). The Usersnap / Amoeboids reviews highlight [Slack and Usersnap as most effective for general audiences because they connect features to user workflows rather than technical specifications, and use conversational tone](https://usersnap.com/blog/changelog-examples/). Straightforward implication: when presenting a work-item narrative to a business user, the displayed summary for each item must be rewritten from the technical Feature/CR/Incident title into "what changed for the user and why."

### LLM rewriting of technical prose is viable but imperfect [MEDIUM confidence]

LLM-based rewriting of commit messages and PR descriptions is a well-established pattern as of 2026 — [git-cliff and semantic-release cover the common case](https://git-cliff.org/); [GitHub Copilot auto-summarises merged PRs directly in the release creation UI](https://www.deployhq.com/git/generating-changelogs-with-ai). [Academic evaluation found LLM-generated commit messages preferred by humans in 78% of samples](https://arxiv.org/html/2401.05926v2), which is good-but-not-great. The implication is that LLM rewriting can produce the business-language summary for each work item, but it should be done at index/ingest time (not query time) so human reviewers can inspect and correct outputs before they reach readers — and because the work-item titles for this project are already curated (Feature/CR/Incident titles follow a convention), the amount of rewriting needed is smaller than for raw git commits.

### Inline, sentence-level citations are the industry-standard AI-answer trust signal [HIGH confidence]

[Perplexity pioneered this pattern: every prose answer carries inline citation numbers at the claim level, with source metadata (title, favicon) visible on hover, and the citations are assigned structurally during context assembly, not retrofitted after generation](https://www.unusual.ai/blog/perplexity-platform-guide-design-for-citation-forward-answers). The [Shape of AI citations pattern](https://www.shapeof.ai/patterns/citations) and [NN/G's explainable-AI guidance](https://www.nngroup.com/articles/explainable-ai/) both converge on: inline cues for sentence-level claims, panels or drawers for long-form exploration, hover for preview plus click-through for the full source, and explicit handling when a citation is missing or broken rather than hiding it. Shape of AI specifically calls out that [citations should be styled distinctly, link to specific source sections, and use meaningful labels (not generic "Source" text)](https://www.shapeof.ai/patterns/citations). For this project, the work items *are* the natural citation targets — every claim in the functional answer can carry a marker that resolves to a work-item card.

### Categorical confidence beats percentage confidence [HIGH confidence]

[NN/G recommends categorical labels (High/Medium/Low) over numeric percentages to avoid false precision, or explainable factors showing which data influenced the answer](https://www.nngroup.com/articles/ai-hallucinations/). The [brics-econ.org trustworthy-AI pattern review](https://brics-econ.org/ui-patterns-for-trustworthy-generative-ai-show-sources-and-last-updated-dates) concurs: [use visual cues like color coding or hedging language ("reasonably sure") instead of percentage scores that create false precision](https://brics-econ.org/ui-patterns-for-trustworthy-generative-ai-show-sources-and-last-updated-dates). Percentage scores invite a specious debate about whether 73% vs 75% matters; categorical bins are honest about the granularity the system can actually justify.

### First-person uncertainty language is better than generalized [HIGH confidence]

[NN/G research found it was important to express uncertainty in first-person perspective ("I'm not sure") rather than generalized ("It's not clear")](https://www.nngroup.com/articles/ai-hallucinations/). This is a small wording choice with an outsized trust effect: the former admits the AI's own limit, the latter implies the information is just ambiguous in general. [NN/G also warns against anthropomorphic language that inflates trust — use neutral phrasing focused on factual information](https://www.nngroup.com/articles/explainable-ai/), so "I'm not sure" should not slide into "I think" or "I believe."

### Specific, concrete wording builds trust better than generic validation [MEDIUM confidence]

[Intercom's trust-building guidance for Fin AI agent](https://www.intercom.com/blog/trust-issues-help-customers-believe-your-ai-agent/) recommends specificity over genericness: the generic "Fin was correct" underperforms versus the specific "The workflow steps Fin outlined are exactly what I guide customers through when setting up their first automation." Translated to this project: the summary line for each work item should be a concrete, specific sentence tied to the observable behavior, not a generic "This was a feature update."

### Last-updated / data-freshness markers must be specific not vague [HIGH confidence]

[brics-econ.org recommends "Data current as of [Date]" rather than vague "Last updated" labels, and specifying update frequency](https://brics-econ.org/ui-patterns-for-trustworthy-generative-ai-show-sources-and-last-updated-dates). Critically, they note a distinction between when an *answer* was generated versus when the *underlying data* was refreshed. For this project, the underlying data (work items, commits) is always current against the git/DB state, so the answer provenance marker should say something like: "Based on N work items merged up to {YYYY-MM-DD}."

### Progressive disclosure should cap at 2–3 layers [HIGH confidence]

Multiple independent sources converge on this limit. [aiuxdesign.guide](https://www.aiuxdesign.guide/patterns/progressive-disclosure) explicitly states "Limit disclosure to 2-3 layers to avoid user frustration," using the structure initial view → expanded view → full view. [LogRocket UX research demonstrates progressive interfaces achieving 30–50% faster initial completion versus full-exposure alternatives](https://blog.logrocket.com/ux-design/progressive-disclosure-ux-types-use-cases/). The [ChatGPT model of hiding advanced options behind a single text input is frequently cited as the archetypal example](https://www.aiuxdesign.guide/patterns/progressive-disclosure). For this feature: L1 = functional answer + top 3 work items summarized; L2 = expanded narrative with all relevant work items in detail; L3 = raw commit/diff/template source for users who explicitly ask.

### Chain-of-thought "show reasoning" displays are a trust trap to avoid [HIGH confidence]

[NN/G explicitly advises against relying on step-by-step reasoning displays in AI interfaces, because research shows they're "often unfaithful" to actual model computation — these walkthroughs may rationalize incorrect answers rather than reveal genuine reasoning](https://www.nngroup.com/articles/explainable-ai/). Better alternatives: focus on sources and limitations instead. This directly contradicts the [brics-econ.org pattern that recommends chain-of-thought displays with progressive disclosure](https://brics-econ.org/ui-patterns-for-trustworthy-generative-ai-show-sources-and-last-updated-dates) — evidence is mixed, but the NN/G position is backed by empirical unfaithfulness research and is the more conservative call. For this project, presenting the *work items themselves* as the "reasoning" is far safer than synthesising a chain-of-thought narrative about how the answer was derived.

### Generic "AI can make mistakes" disclaimers are noise, not trust [HIGH confidence]

[NN/G critiques ChatGPT's small-font disclaimer as exemplifying a weak strategy: constantly showing a generic warning label turns it into background clutter](https://www.nngroup.com/articles/ai-hallucinations/), comparing it to ubiquitous warnings that lose effectiveness through repetition. Better: [disclaimers must use plain language describing specific limitations, not vague AI terminology, and should be paired with actionable guidance](https://www.nngroup.com/articles/explainable-ai/). For this feature, a specific limitation like "This answer covers work items merged to main; open branches and drafts are not included" is worth showing; "AI can make mistakes" is not.

### Source citations can create a false halo of truth [MEDIUM confidence]

[NN/G cautions that source links might create a "false halo effect of truth," potentially reducing user vigilance rather than enhancing it](https://www.nngroup.com/articles/ai-hallucinations/), and [citations are frequently hallucinated; users rarely verify them despite their apparent credibility](https://www.nngroup.com/articles/explainable-ai/). Mitigations that generalize to this project: only cite work items the system actually retrieved (not items the LLM might invent), make broken or missing citations explicit rather than silent ("no matching work items found"), and pre-compute the citation→work-item mapping rather than letting the LLM choose IDs freely.

### Audit-log-style right-side detail panels keep context [MEDIUM confidence]

Several audit-log UX redesigns (HighLevel, Zuora, UI Bakery) settle on the same interaction: [open details in a right-side panel so you never lose your table position, with keyboard arrows to navigate between records without closing the panel](https://help.gohighlevel.com/support/solutions/articles/155000006667-audit-logs). This is a good fit for the work-item drill-in at L2/L3 of this feature — clicking a work item in the feed opens a right-hand drawer with its full title, summary, linked commit, and diff, without losing the user's position in the main answer.

### Group work items by feature/behavior, not by type, when the user asked a behavioral question [MEDIUM confidence]

GitHub's auto-generated release notes [group PRs by category (Breaking Changes, Features, Fixes) using PR labels](https://docs.github.com/en/repositories/releasing-projects-on-github/automatically-generated-release-notes), which is correct when the question is "what's in this release?" But when the question is "what does button X do?", the natural grouping is chronological *through the life of that behavior* — the first item created it, subsequent items changed it. Linear-style undated grouping is a better fit here than GitHub-style categorized grouping. Confidence is MEDIUM because this is a synthesis inference, not directly cited — no source was found addressing this specific behavioral-question grouping case.

---

## Recommendations

1. **Primary — "Functional answer first, Linear-style work-item feed second, inline citations between them, 3-layer progressive disclosure"**
   - **L1 (default view)**: a 1-paragraph plain-language functional answer to the user's question, with inline Perplexity-style citation markers (`[F-00042]`, `[CR-00010]`, `[I-00007]`) against each load-bearing claim. Below it, a chronological mini-feed of the 3–5 most relevant work items, each rendered as `date | item-id | business-friendly title | 1-2 sentence impact summary`. No categorization, no icons beyond item-type glyph. Small trust strip at the top or bottom: **"Based on N work items merged up to YYYY-MM-DD. Confidence: High/Medium/Low."**
   - **L2 (expand-in-place drawer per item)**: full work-item title, curated summary, author, list of commits merged, optional `diff` link.
   - **L3 (full audit)**: dedicated page showing every commit touching the resolved source file/symbol, with a link to the complete git log as an escape hatch.
   - **Tone**: plain English, user-benefit framing ("When this page loads, pressing Approve sends the batch to the daemon"), never raw technical jargon at L1.
   - **Citation semantics**: the LLM is *not* allowed to invent work-item IDs — only the retrieval pipeline may emit them. The LLM's job is to compose prose around retrieved IDs. This pre-empts the hallucinated-citation failure mode NN/G warns about.

2. **Alternative — Minimal v1: functional answer + un-rewritten item titles, no LLM prose for work-item summaries**
   If the LLM-rewriting-to-business-language step is risky or expensive, ship v1 using the curated Feature/CR/Incident titles as they exist (the project already enforces descriptive titles). The functional answer can still be LLM-generated; the work-item feed just uses the stored titles verbatim. This gets the feature live with one less failure mode, at the cost of occasional technical-sounding item labels. Add LLM rewriting in v2 once curator review is in place.

3. **Alternative — Vercel-style card layout with inline screenshots for heavy-visual answers**
   If the answer frequently involves UI elements users recognize by appearance (buttons, menus, workflows), a card-per-item layout with an inline screenshot from the source template — indexable via the [R-00058](./R-00058-nl-to-ui-element-resolution.md) Playwright snapshot pipeline — gives faster recognition than prose alone. Higher implementation cost and larger visual footprint, so defer until after v1 validates the core pattern.

4. **Avoid — Chain-of-thought "show me how you thought" displays**
   Per [NN/G](https://www.nngroup.com/articles/explainable-ai/), these are often unfaithful to model computation and can rationalize wrong answers. Present the *retrieved work items* as the reasoning. No synthesis of "the model considered X then Y then concluded Z."

5. **Avoid — Percentage confidence scores**
   Per [NN/G](https://www.nngroup.com/articles/ai-hallucinations/) and [brics-econ.org](https://brics-econ.org/ui-patterns-for-trustworthy-generative-ai-show-sources-and-last-updated-dates), these create false precision. Use three-bin categorical (High / Medium / Low) or hedging language.

6. **Avoid — Generic AI disclaimers in footer**
   Per [NN/G](https://www.nngroup.com/articles/ai-hallucinations/), they become background clutter. Replace with specific, actionable limitations ("Based on items merged to main; open branches excluded.").

7. **Avoid — Anthropomorphic framing**
   Per [NN/G](https://www.nngroup.com/articles/explainable-ai/), "I think" / "I believe" inflates perceived authority. Use "Based on the data retrieved..." or "The work items touching this behavior are..."

---

## Concrete Answer Template

A mock of the recommended answer shape for the running example ("what does the Approve button on the batch page do?"):

```
┌─────────────────────────────────────────────────────────────────────┐
│ Based on 3 work items merged up to 2026-04-19.  Confidence: High   │
├─────────────────────────────────────────────────────────────────────┤
│ The Approve button on the Batch Detail page marks the batch as    │
│ approved [F-00015] and schedules it for the daemon to pick up on   │
│ the next poll cycle [CR-00002]. A confirmation dialog was added   │
│ after an incident where batches were approved by accident         │
│ [I-00004].                                                         │
│                                                                     │
│ History                                                             │
│ ─────────                                                           │
│ 2025-08-11 · F-00015 · Batch approval workflow                     │
│   Introduced the Approve button and the approved→pending           │
│   transition the daemon polls for.                                  │
│                                                                     │
│ 2026-01-22 · CR-00002 · Daemon picks up approved batches faster    │
│   Reduced the polling interval from 5 min to 60s so approvals       │
│   take effect within a minute rather than five.                     │
│                                                                     │
│ 2026-03-05 · I-00004 · Prevent accidental batch approvals          │
│   Added the confirmation dialog that now shows before approval     │
│   goes through, after three batches were approved by misclick.      │
└─────────────────────────────────────────────────────────────────────┘
```

Key properties of this mock tied to findings above:
- Functional answer first, Linear-style history feed second.
- Inline citations at sentence level, each resolving to exactly one work item from the retrieval pipeline (no free-form IDs).
- Each history entry is `date · ID · business-friendly title`, then a 1-2 sentence impact summary that would have been LLM-rewritten at ingest time from the raw work-item summary.
- Trust strip with count, date, categorical confidence — no percentage, no generic disclaimer.
- No category headers (Linear pattern, not GitHub pattern).
- Clicking any row would open an L2 drawer with the full curated work-item summary and links; clicking a commit reference would open L3 (full source/diff).

---

## Limitations

- **No user testing.** Every recommendation here is drawn from third-party UX guidance, vendor documentation, and public pattern libraries. An A/B test against real PM / support / business users on the actual dashboard is strongly recommended before declaring the pattern final.
- **Confidence-signal effectiveness is contested.** NN/G and brics-econ.org disagree on chain-of-thought displays; the recommendation defers to NN/G's more conservative position, but reasonable people disagree.
- **No cost model for LLM rewriting.** Ingest-time rewriting of every work item adds latency and token spend; this was not quantified.
- **Layout assumes a desktop chat panel.** Mobile-viewport adjustments (drawer → full-screen, etc.) were not covered.
- **Work-item scope assumed to be modest (3–5 per answer).** For heavy-touch behaviors with 20+ linked items, a different structure (grouped by release, or collapsed by year) may be needed — not covered.
- **Citation UX for non-URL citations is less studied.** Most cited sources describe web-source citations; citation to internal work-item IDs is an extension not directly studied in the literature.
- **Tone-translation failure modes not empirically measured.** The 78% LLM-preferred-commit-message figure is from one academic study; real-world quality on this project's Feature/CR/Incident prose is unknown.

---

## Sources

| # | Source | Credibility | URL |
|---|--------|-------------|-----|
| 1 | NN/G — AI Hallucinations: What Designers Need to Know | HIGH | https://www.nngroup.com/articles/ai-hallucinations/ |
| 2 | NN/G — Explainable AI in Chat Interfaces | HIGH | https://www.nngroup.com/articles/explainable-ai/ |
| 3 | Shape of AI — Citations Pattern | HIGH | https://www.shapeof.ai/patterns/citations |
| 4 | brics-econ.org — UI Patterns for Trustworthy Generative AI | MEDIUM | https://brics-econ.org/ui-patterns-for-trustworthy-generative-ai-show-sources-and-last-updated-dates |
| 5 | Intercom — Trust Issues: How to Help Customers Believe Your AI Agent | HIGH | https://www.intercom.com/blog/trust-issues-help-customers-believe-your-ai-agent/ |
| 6 | Unusual — Perplexity Platform Guide: Citation-Forward Answers | MEDIUM | https://www.unusual.ai/blog/perplexity-platform-guide-design-for-citation-forward-answers |
| 7 | Worknotes — Best Changelog Page Designs | MEDIUM | https://www.worknotes.ai/blog/best-changelog-page-designs |
| 8 | Appcues — How to Write Release Notes | MEDIUM | https://www.appcues.com/blog/release-notes-examples |
| 9 | Cycle — Public Changelog Best Practices | MEDIUM | https://cycle.app/blog/public-changelog-best-practices-examples-make-your-product-shine-with-stunning-release-notes |
| 10 | Userpilot — Release Notes Best Practices | MEDIUM | https://userpilot.com/blog/release-notes-best-practices/ |
| 11 | Usersnap — 10 Inspiring Changelog Examples | MEDIUM | https://usersnap.com/blog/changelog-examples/ |
| 12 | Amoeboids — Changelog 101 | MEDIUM | https://amoeboids.com/blog/changelog-how-to-write-good-one/ |
| 13 | LaunchNotes — 51 of the Best Release Notes Examples | MEDIUM | https://www.launchnotes.com/blog/release-notes-examples |
| 14 | GitHub Docs — Automatically Generated Release Notes | HIGH | https://docs.github.com/en/repositories/releasing-projects-on-github/automatically-generated-release-notes |
| 15 | git-cliff — Highly customizable changelog generator | HIGH | https://git-cliff.org/ |
| 16 | DeployHQ — Generating Changelogs and Release Notes with AI | MEDIUM | https://www.deployhq.com/git/generating-changelogs-with-ai |
| 17 | Release Drafter — GitHub Action | HIGH | https://github.com/release-drafter/release-drafter |
| 18 | Graphite — Automatic release note generation from PRs | MEDIUM | https://graphite.com/guides/automate-release-notes-from-prs |
| 19 | aiuxdesign.guide — Progressive Disclosure in AI | MEDIUM | https://www.aiuxdesign.guide/patterns/progressive-disclosure |
| 20 | LogRocket — Progressive disclosure in UX design | MEDIUM | https://blog.logrocket.com/ux-design/progressive-disclosure-ux-types-use-cases/ |
| 21 | NN/G — Progressive Disclosure | HIGH | https://www.nngroup.com/articles/progressive-disclosure/ |
| 22 | Primer (GitHub) — Progressive Disclosure | HIGH | https://primer.style/product/ui-patterns/progressive-disclosure/ |
| 23 | IxDF — What is Progressive Disclosure | HIGH | https://ixdf.org/literature/topics/progressive-disclosure |
| 24 | Automatic PR Description Generation (T5) — arxiv | HIGH | https://arxiv.org/html/2408.00921v1 |
| 25 | LLM Commit Message Preliminary Study — arxiv | HIGH | https://arxiv.org/html/2401.05926v2 |
| 26 | Zendesk — About AI Agents | HIGH | https://support.zendesk.com/hc/en-us/articles/6970583409690-About-AI-agents |
| 27 | Intercom — Fin AI Agent Explained | HIGH | https://www.intercom.com/help/en/articles/7120684-fin-ai-agent-explained |
| 28 | Figma — View a File's Version History | HIGH | https://help.figma.com/hc/en-us/articles/360038006754-View-a-file-s-version-history |
| 29 | HighLevel — Audit Logs Redesign | MEDIUM | https://help.gohighlevel.com/support/solutions/articles/155000006667-audit-logs |
| 30 | Modexa — The Confidence UI Pattern | LOW | https://medium.com/@Modexa/the-confidence-ui-pattern-that-users-actually-trust-ff27e1a8a956 |

---

## Appendix: Research Log

**Date range**: 2026-04-19 (single session)
**Queries run**: 10 WebSearch, 9 WebFetch, 0 context7
**Mode used**: deep
**Depth level**: deep

Coverage was strongest on AI-answer trust patterns (NN/G, Shape of AI, Intercom, brics-econ.org all converge tightly) and on changelog layouts (Linear, Stripe, Vercel, GitHub widely documented). Weakest on *combining* a functional NL answer with a narrative history list — there is no directly comparable prior art in the sources surveyed, so the answer template in Recommendations is a synthesis of adjacent patterns, not a copy of any single precedent. An empirical spike (10–20 real queries, shown to real PMs/business users) would substantially improve confidence on the combined shape.

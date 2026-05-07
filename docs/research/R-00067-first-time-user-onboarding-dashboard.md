# R-00067 — First-Time User Onboarding & Discoverability for IW AI Core

| Field | Value |
|-------|-------|
| ID | R-00067 |
| Date | 2026-05-07 |
| Mode | deep |
| Editorial category | functional |
| Status | draft |

**Primary question** — What is the most effective, low-maintenance way to make a complex technical dashboard like IW AI Core understandable to a first-time visitor within seconds, without annoying repeat users, so it can ship as a credible Apache 2.0 OSS project?

---

## Executive Summary

The dominant body of UX research is unambiguous: long forced product tours fail (≈70 % of users skip imposed tours), and the best onboarding for complex applications is **contextual help that the user pulls when they need it**, not pushed at them on first load ([NN/g — Onboarding Tutorials vs. Contextual Help](https://www.nngroup.com/articles/onboarding-tutorials/), [Why Most Product Tours Get Skipped](https://productonboarding.com/articles/why-product-tours-get-skipped)). The patterns that consistently work are: (1) per-page **"What is this?" panels / `?` popovers** with progressive disclosure, (2) **information-rich empty states** that double as one-step tutorials, (3) **pre-populated demo data** that lets users learn by exploring something real (Linear's "anti-onboarding"), and (4) an **optional, ≤5-step micro-tour** offered — never forced — on first visit, with persistent dismissal in `localStorage`.

For IW AI Core's stack (FastAPI + Jinja2 + htmx, Apache 2.0), **Driver.js (MIT, ~5 KB, vanilla JS, full keyboard/ESC/ARIA support)** is the only major tour library whose license is compatible with Apache 2.0; **Shepherd.js is AGPL-3.0 + commercial dual-licensed and is incompatible with an Apache 2.0 OSS release** ([Shepherd license](https://docs.shepherdjs.dev/guides/license/), [Apache 2.0 compatibility](https://licensecheck.io/guides/apache-compatible)). The recommended approach for IW AI Core is a small, **server-rendered help system**: a `?` button in the page header that opens an htmx-loaded popover ("What is this page? · What can I do here? · Common pitfalls · Doc link") plus a **Driver.js opt-in micro-tour** triggered from a "Take the 30-second tour" link inside that popover, gated by a `localStorage` "seen" key. This keeps the implementation in plain Python/Jinja, requires no SPA, no analytics SDK, no commercial license, and is fully OSS-friendly.

---

## Findings

### 1. What first-time users of complex dashboards actually value [HIGH]

NN/g's research on complex applications and dashboards converges on three things first-time users want, in this order ([NN/g — 8 Design Guidelines for Complex Applications](https://www.nngroup.com/articles/complex-application-design/), [NN/g — Empty States in Complex Applications](https://www.nngroup.com/articles/empty-state-interface-design/)):

1. **Orientation** — "What does this page do, and what am I looking at right now?" Empty states must communicate system status: an empty list with no message reads as a bug.
2. **A clear next action** — One primary CTA that lets them produce *something* in seconds. Loggly's empty state offers two paths: connect a real source or load demo data.
3. **Permission to explore safely** — NN/g's #1 guideline for complex apps is "promote learning by doing" — let users click around without fear of breaking state.

What they explicitly do **not** want: a 10-step modal walkthrough they have to dismiss before they can touch the UI. Pendo's data shows the average guide engagement rate across all SaaS is only 28.5 % ([Pendo — onboarding research](https://www.pendo.io/resources/getting-started-with-in-app-onboarding/)), and ~70 % of users skip tours that feel imposed ([Why Most Product Tours Get Skipped](https://productonboarding.com/articles/why-product-tours-get-skipped)).

### 2. Top pain points on arrival [HIGH]

From the dashboard-UX literature ([Smashing — UX Strategies for Real-Time Dashboards](https://www.smashingmagazine.com/2025/09/ux-strategies-real-time-dashboards/), [excited.agency — Effective Dashboard UX](https://excited.agency/blog/dashboard-ux-design), [UXPin — Dashboard Design Principles 2025](https://www.uxpin.com/studio/blog/dashboard-design-principles/)):

- **Information overload / no visual hierarchy** — everything looks equally important, so the user can't tell what matters.
- **Unknown vocabulary** — the page uses domain terms ("worktree", "step", "fix cycle") with no inline definition.
- **Empty screens with no explanation** — user can't tell whether the system is broken, still loading, or just unused.
- **Disjoint mental model** — multiple pages exist (Queue, Jobs, Worktrees, Daemon) but the relationship between them is invisible.
- **Help that is far away** — a top-right "Help" link that opens a 50-page wiki is functionally invisible during first use.

### 3. Pattern landscape — what works, what annoys [HIGH]

Mapping the UX literature against the patterns we listed in scope:

| Pattern | Verdict | Notes |
|---|---|---|
| **Per-page `?` button → popover** | **Recommended** | Pull-revelation, dismissable, recallable, low maintenance. NN/g endorses this as the default for complex apps ([NN/g — Onboarding Tutorials vs. Contextual Help](https://www.nngroup.com/articles/onboarding-tutorials/)). |
| **Forced full-screen welcome modal** | Avoid | Highest skip rate; teaches users to dismiss without reading ([DNSK — "Maybe Later" is the most expensive button](https://dnsk.work/blog/how-one-button-teaches-users-to-ignore-you/)). |
| **Optional 3–5 step guided tour** | Recommended (opt-in) | Tours work *when offered, not imposed*, when they are 3–7 steps, and skippable at any time ([Chameleon — product tours](https://www.chameleon.io/blog/how-to-build-effective-product-tours), [Appcues — product tour patterns](https://www.appcues.com/blog/product-tours-ui-patterns)). |
| **Information-rich empty states** | **Recommended** | NN/g's three rules: communicate status, provide learning cues, offer direct pathways. Linear, Loggly, Datadog cited as exemplars. |
| **Inline tooltips on hover** | Use sparingly | Must be WCAG 2.2 SC 1.4.13 compliant (dismissible / hoverable / persistent) ([W3C — Content on Hover or Focus](https://www.w3.org/WAI/WCAG21/Understanding/content-on-hover-or-focus/)). Don't hide critical info behind hover. |
| **"Info" `i` icon next to fields** | Recommended | Carbon and PatternFly both endorse this for parameter-level explanation ([Carbon — Tooltip](https://carbondesignsystem.com/components/tooltip/usage/)). |
| **Embedded quickstart video** | Optional | Useful in README, low ROI in-app for technical users. |
| **Command palette help (Linear/Vercel-style)** | Nice-to-have | Power-user feature; doesn't replace the basic `?` for first-time users. |
| **Doc-search overlay** | Nice-to-have | Algolia DocSearch-style; valuable once docs exist, but secondary to per-page orientation. |
| **Pre-populated demo data** | **Recommended** | Linear's strongest pattern: lets users learn by exploring something real ([Candu — Linear onboarding teardown](https://www.candu.ai/blog/linear-onboarding-teardown)). |

**The "help fatigue" rule** ([Chameleon — Contextual Help UX](https://www.chameleon.io/blog/contextual-help-ux)): **no more than 3–5 pieces of contextual help in the first session**. Above that, users feel babysat and start blindly dismissing.

### 4. Real-world success cases [HIGH]

| Product | Pattern | Lesson |
|---|---|---|
| **Linear** | Pre-populated demo workspace + animated empty states + keyboard-shortcut hints on hover; *no* welcome tour | "Anti-onboarding" — let constrained UI + smart defaults teach implicitly ([Candu](https://www.candu.ai/blog/linear-onboarding-teardown), [Medium — Linear's onboarding](https://medium.com/design-bootcamp/hands-on-learning-cinematic-transition-linears-thoughtful-onboarding-aa4f16c33d90)). |
| **Stripe** | `ContextView`/`FocusView` modules embedded in the existing workflow; "Learn more" links that progressively disclose | Help arrives where the work is happening, not on a separate help page ([Stripe Apps design](https://docs.stripe.com/stripe-apps/design)). |
| **Datadog** | Empty states like "Star your favorites to list them here"; learning cues double as feature ads | Empty states are prime real estate for in-context teaching ([NN/g — Empty States](https://www.nngroup.com/articles/empty-state-interface-design/)). |
| **Sentry** | Issue-detail pages prioritize "first relevant fact" (frequency, affected releases) at the top | Surface the *one* most useful piece of info above the fold; everything else is progressive disclosure. |
| **Supabase** | Two segmented onboarding paths (Postgres-native vs. database-novice) detected from sign-up signals | When your audience is split, segment the onboarding instead of designing for the average ([Craft Ventures — Inside Supabase](https://www.craftventures.com/articles/inside-supabase-breakout-growth)). |
| **Temporal UI / Prefect / Airflow** | Operational-state-first dashboards; "Where is my workflow stuck?" is the headline question they answer in seconds | Lead with the state the operator most needs to see; everything else is one click away ([Temporal UI overview](https://startupik.com/temporal-ui-monitoring-workflows-in-temporal/)). |
| **Loggly** | Empty state offers two paths: connect real source OR load demo data | Demo-data path is a tour without being a tour. |
| **Vercel + Supabase Marketplace** | Zero-click onboarding — credentials auto-injected, "first database" reachable in seconds | Time-to-first-success > tour length ([Vercel — How Supabase increased signups](https://vercel.com/blog/how-supabase-increased-signups-through-the-vercel-marketplace)). |

### 5. The library landscape [HIGH]

| Library | License | Size / framework | Accessibility | Verdict for IW AI Core |
|---|---|---|---|---|
| **Driver.js** | **MIT** ✅ | ~5 KB gzipped, vanilla JS, zero deps, TypeScript | Full keyboard nav, ESC to close, can be disabled, ARIA-friendly ([context7 — Driver.js docs](https://github.com/nilbuild/driver.js)) | **Recommended primary choice** — Apache 2.0 compatible, htmx-friendly (drop a `<script>` tag) |
| **Shepherd.js** | **AGPL-3.0 + commercial** ❌ | Vanilla + framework wrappers, ~30 KB, Floating UI | Strong ARIA, `exitOnEsc`, `keyboardNavigation`, modal overlay | **Reject** — AGPL-3.0 is incompatible with Apache 2.0 release, and commercial use of revenue-generating tools requires a paid license ([Shepherd license](https://docs.shepherdjs.dev/guides/license/)) |
| **Intro.js** | AGPL + commercial | Vanilla | Decent | Same license issue as Shepherd; reject for Apache OSS |
| **Reactour** | MIT | React-only | Decent | N/A — IW AI Core has no React layer |
| **React Joyride** | MIT | React-only | Strong | N/A — N/A — same reason |
| **Bootstrap-Tour, Hopscotch** | Permissive | Older, less maintained | Weaker | Not worth it vs. Driver.js |

**Net**: Driver.js is the only mature, accessible, Apache-compatible option. The userorbit and Inline Manual comparisons confirm this is the safe default for permissive-license projects ([Userorbit — Best Open-Source Product Tour Libraries](https://userorbit.com/blog/best-open-source-product-tour-libraries), [Inline Manual — Driver.js vs Intro.js vs Shepherd.js vs Reactour](https://inlinemanual.com/blog/driverjs-vs-introjs-vs-shepherdjs-vs-reactour/)).

### 6. Trade-offs of the main approaches [HIGH]

| Approach | Strength | Weakness |
|---|---|---|
| `?` button → popover only | Pull-only, never annoying, low effort | Discoverability of the `?` itself; must be in a consistent corner on every page |
| Guided tour only | Strong "I'm being shown around" feeling | High skip rate, hard to maintain as UI evolves, useless on revisit |
| Empty-state explanations only | Best "in-the-moment" teaching | Doesn't help users on pages that *aren't* empty (already populated by demo data) |
| Dedicated docs page | Authoritative, search-friendly | Far from the work; users won't switch tabs |
| **Layered combination (recommended)** | Each pattern covers the gaps of the others | Slightly more surface area to keep in sync |

### 7. Accessibility & dismissibility — non-negotiables [HIGH]

- **Tooltips/popovers** must satisfy [WCAG 2.2 SC 1.4.13](https://www.w3.org/WAI/WCAG21/Understanding/content-on-hover-or-focus/): dismissible (ESC), hoverable (don't disappear when the pointer enters them), persistent (only dismiss on user action).
- **`?` button** must be a real `<button>` with `aria-label="Help for this page"`, focusable, ESC-dismissible, and reachable by keyboard.
- **Tour modal** must use `role="dialog" aria-modal="true"`, trap focus while open, and release focus to the originating button on close. Driver.js does this out of the box; do not turn off `allowKeyboardControl` ([context7 — Driver.js disable-keyboard-control](https://github.com/nilbuild/driver.js/blob/master/index.html)).
- **Dismissal must persist** — after the user clicks "Don't show again", store a `localStorage` key like `iw.tour.<page>.dismissedAt` and never auto-launch again. Don't use cookies — privacy-policy overhead and unnecessary server traffic ([localStorage vs cookies guidance](https://medium.com/doku-insight/local-storage-vs-session-storage-vs-cookies-how-to-choose-and-best-practices-98bef85ea562)).
- **Localization** — keep help strings in Jinja templates (or a single `help_strings.py` dict), not in JS. This makes future i18n a translation pass on the templates.

### 8. The OSS first-impression layer (outside the app) [MEDIUM]

For an Apache 2.0 release, the in-app onboarding is only half the story. The README is the *literal* first thing every visitor sees ([DEV — Power of the README](https://dev.to/matheussricardoo/the-power-of-the-readme-the-first-impression-that-defines-your-projects-and-profile-49d1), [Make a README](https://www.makeareadme.com/)). Concrete additions worth committing alongside the in-app help:

- **One annotated screenshot per main surface** (Queue, Code, Docs, Jobs) at the top of the README.
- **A 30-second narrated GIF or `asciinema`** of the happy path: design feature → batch run → see it merged.
- **A "What is this thing?" paragraph** at the very top — what problem it solves, who it is for, what it is *not*. Mirror the same wording in the in-app `?` popover for the dashboard root.
- **`docs/architecture.md` linked from the README** with a 1-page system diagram (you already have one — surface it).

---

## Recommendation for IW AI Core

A layered, low-cost approach that fits the FastAPI + Jinja2 + htmx stack and the Apache 2.0 license. **All four layers should ship together** — they each cover a different gap.

### Layer 1 — Per-page `?` popover (the cheapest, biggest win)

- A small `<button class="help-trigger" aria-label="Help for this page">?</button>` placed in the page header, next to the page title, on every project + system page (`templates/pages/project/*.html`, `templates/pages/system/*.html`).
- Click → htmx GET to `/_help/<page-slug>` → Jinja partial renders into a popover (`templates/_partials/help/<page-slug>.html`).
- Popover content follows a 4-section template:
  1. **What is this page?** (1 sentence)
  2. **What can I do here?** (3 bullets max)
  3. **Vocabulary used here** (1–4 term definitions: "worktree", "fix cycle", "step")
  4. **Take a 30-second tour →** (button) and **Open full docs →** (link to `docs/`)
- Keep one help fragment per page; ~15 fragments total. They live in the repo, they get reviewed in PRs, they don't drift.
- **Why this layer first**: NN/g's "pull revelation" pattern, recallable, dismissable, never blocks anyone, and it's the only layer required for the OSS release to feel polished.

### Layer 2 — Information-rich empty states

For every list view (Queue, Batches, Jobs, Worktrees, Tests, Quality, Research, Docs):

- **Heading** — what the empty state means (e.g. "No work items yet").
- **Body** — one sentence explaining what populates it ("This is where features, incidents, and CRs you design will appear once you run `/iw-new-feature`.").
- **Primary CTA** — a button or link to the most likely next action.
- **Secondary CTA** — a "Learn more" link to the relevant doc.

This is a one-time edit to ~10 templates and gives every empty page a tiny built-in tutorial.

### Layer 3 — Optional Driver.js tour ("Take a tour")

- Triggered **only** from the `?` popover's "Take a 30-second tour" button — never auto-launched on first visit. Auto-launch is what produces the 70 % skip rate.
- Per page, 3–5 steps max, defined in a single `static/help/tours.js` file: `{ "queue": [{ element: ".btn-new-item", popover: {...} }, ...], ... }`.
- `localStorage` key `iw.tour.<page>.completed` shown next to the help button as a subtle "✓ tour seen" so users know they've taken it.
- Uses Driver.js's defaults: `allowKeyboardControl: true`, `showProgress: true`, `showButtons: ["next","previous","close"]`.

### Layer 4 — Demo-data mode (Linear-style, the strongest teaching pattern)

The single biggest UX upgrade is **letting a first-time user click a button and see the dashboard *full* of realistic data** — a fully-fleshed example project with finished features, batches, jobs, test runs, and a populated Code page. That converts every empty page into a populated one and lets users learn by exploring real artifacts. It is more work than the other three layers (~1 feature) but is the highest-leverage move for OSS adoption.

Suggested implementation:

- A `seed_demo_project.py` script that registers a fictional project (`example-app`), inserts ~10 work items in various states, ~3 batches, ~5 doc-generation jobs, sample research docs, and demo worktrees.
- Surface it as a "Load demo project" button on the empty `/projects` page.
- Make it idempotent and purgeable so users can clean it out before going live.

### Layer 5 (optional, later) — Command palette help

Once layers 1–4 ship, a `Cmd+K`/`Ctrl+K` palette that searches help fragments + doc titles is a nice power-user feature. Don't gate the OSS release on it.

### What to *not* do

- ❌ No forced welcome modal on first login.
- ❌ No Shepherd.js / Intro.js — license-incompatible with Apache 2.0.
- ❌ No third-party SaaS onboarding tools (Pendo / Appcues / Chameleon) — they require accounts, beacon scripts, and tracking, all of which conflict with a self-hosted OSS posture.
- ❌ No tour > 5 steps. Brevity is a hard rule.
- ❌ No "?" button buried in a menu — it has to be visible in the page header on every page.

### Effort estimate

| Layer | Effort | Files touched | Owner |
|---|---|---|---|
| 1 — `?` popover + 15 help fragments | 1 feature (~2 days) | `dashboard/routers/help.py` (new), `templates/_partials/help/*.html`, `templates/base.html`, `static/styles.css` | Dashboard |
| 2 — Empty-state polish | 0.5 feature (~1 day) | ~10 list templates | Dashboard |
| 3 — Driver.js opt-in tour | 0.5 feature (~1 day) | `static/vendor/driver.js`, `static/help/tours.js`, `templates/base.html` | Dashboard |
| 4 — Demo-data seed script | 1 feature (~2 days) | `orch/cli/seed_demo.py`, registration on `/projects` page | Orch + Dashboard |
| 5 — Command palette (later) | 1 feature | New | Dashboard |

Layers 1–3 alone are ~4 days of work and would dramatically raise the project's first-impression quality before going public.

---

## Limitations

- The literature is heavy on consumer SaaS onboarding (Pendo, Appcues, Chameleon blogs) and lighter on **operator-facing dashboards for OSS infra tools**. We extrapolated from Linear, Stripe, Temporal UI, and Sentry, which are the closest analogues.
- Pendo's quoted "guide engagement = 28.5 %" is a vendor benchmark and may be biased toward customers who deploy guides at all; absolute completion rates for OSS dashboards are unknown.
- Driver.js is well-maintained but a single-maintainer project; if it ever stalls, the tour layer can be removed without breaking layers 1, 2, 4 — they each work standalone, which is intentional.
- We did not run a live a11y audit; the recommendations follow WCAG 2.2 guidelines but a manual screen-reader pass before the OSS release is still required.
- Demo-data design (layer 4) is non-trivial to make *realistic*; bad demo data is worse than no demo data.

---

## Sources

| # | Title | Credibility | URL |
|---|---|---|---|
| 1 | NN/g — Onboarding Tutorials vs. Contextual Help | High (industry standard) | https://www.nngroup.com/articles/onboarding-tutorials/ |
| 2 | NN/g — 8 Design Guidelines for Complex Applications | High | https://www.nngroup.com/articles/complex-application-design/ |
| 3 | NN/g — Empty States in Complex Applications: 3 Guidelines | High | https://www.nngroup.com/articles/empty-state-interface-design/ |
| 4 | NN/g — Progressive Disclosure | High | https://www.nngroup.com/articles/progressive-disclosure/ |
| 5 | NN/g — Tooltip Guidelines | High | https://www.nngroup.com/articles/tooltip-guidelines/ |
| 6 | W3C — Understanding SC 1.4.13: Content on Hover or Focus | High (standard) | https://www.w3.org/WAI/WCAG21/Understanding/content-on-hover-or-focus/ |
| 7 | Why Most Product Tours Get Skipped | Medium | https://productonboarding.com/articles/why-product-tours-get-skipped |
| 8 | DNSK — "Maybe Later" Is the Most Expensive Button | Medium | https://dnsk.work/blog/how-one-button-teaches-users-to-ignore-you/ |
| 9 | Chameleon — Contextual Help UX in 2026 | Medium | https://www.chameleon.io/blog/contextual-help-ux |
| 10 | Chameleon — How to build effective product tours | Medium | https://www.chameleon.io/blog/how-to-build-effective-product-tours |
| 11 | Appcues — Product tours UI patterns | Medium | https://www.appcues.com/blog/product-tours-ui-patterns |
| 12 | Pendo — Getting started with in-app onboarding | Medium (vendor) | https://www.pendo.io/resources/getting-started-with-in-app-onboarding/ |
| 13 | Smashing — UX Strategies for Real-Time Dashboards | High | https://www.smashingmagazine.com/2025/09/ux-strategies-real-time-dashboards/ |
| 14 | UXPin — Effective Dashboard Design Principles 2025 | Medium | https://www.uxpin.com/studio/blog/dashboard-design-principles/ |
| 15 | Candu — Linear Onboarding Teardown | Medium | https://www.candu.ai/blog/linear-onboarding-teardown |
| 16 | Medium — Linear's thoughtful onboarding | Medium | https://medium.com/design-bootcamp/hands-on-learning-cinematic-transition-linears-thoughtful-onboarding-aa4f16c33d90 |
| 17 | Stripe Apps — Design your app | High (primary) | https://docs.stripe.com/stripe-apps/design |
| 18 | Craft Ventures — Inside Supabase's Breakout Growth | Medium | https://www.craftventures.com/articles/inside-supabase-breakout-growth |
| 19 | Vercel — How Supabase increased signups through the Marketplace | High (primary) | https://vercel.com/blog/how-supabase-increased-signups-through-the-vercel-marketplace |
| 20 | Startupik — Temporal UI overview | Low/Medium | https://startupik.com/temporal-ui-monitoring-workflows-in-temporal/ |
| 21 | Userorbit — Best Open-Source Product Tour Libraries 2026 | Medium | https://userorbit.com/blog/best-open-source-product-tour-libraries |
| 22 | Inline Manual — Driver.js vs Intro.js vs Shepherd.js vs Reactour | Medium | https://inlinemanual.com/blog/driverjs-vs-introjs-vs-shepherdjs-vs-reactour/ |
| 23 | Driver.js — official site / GitHub (via context7) | High (primary) | https://github.com/nilbuild/driver.js |
| 24 | Shepherd.js — License & Pricing | High (primary) | https://docs.shepherdjs.dev/guides/license/ |
| 25 | Apache 2.0 Compatible Licenses Guide | Medium | https://licensecheck.io/guides/apache-compatible |
| 26 | Carbon Design System — Tooltip | High (industry standard) | https://carbondesignsystem.com/components/tooltip/usage/ |
| 27 | Carbon Design System — Empty States | High | https://carbondesignsystem.com/patterns/empty-states-pattern/ |
| 28 | PatternFly — Empty State design guidelines | High | https://www.patternfly.org/components/empty-state/design-guidelines/ |
| 29 | PatternFly — Popover design guidelines | High | https://www.patternfly.org/components/popover/design-guidelines/ |
| 30 | Make a README | Medium | https://www.makeareadme.com/ |
| 31 | DEV — The Power of the README | Low/Medium | https://dev.to/matheussricardoo/the-power-of-the-readme-the-first-impression-that-defines-your-projects-and-profile-49d1 |
| 32 | DOKU — Local Storage vs Session Storage vs Cookies | Medium | https://medium.com/doku-insight/local-storage-vs-session-storage-vs-cookies-how-to-choose-and-best-practices-98bef85ea562 |

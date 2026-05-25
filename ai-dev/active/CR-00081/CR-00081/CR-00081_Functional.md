# CR-00081 — Functional Design

<!--
Audience: humans (product owners, support, onboarding engineers).
DO NOT include file paths, class names, SQL, code fences, or implementation
steps. If you need to capture those, they belong in the technical design doc.
Keep the total body at most 500 words (the review skill blocks >500).
-->

## ⛔ Docker is off-limits

Standard policy. This work only touches tests, one baseline list, and one planning document — no Docker changes.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work does not add, modify, or remove any database migrations.

## Why

The project's automated test-quality scanner flags tests that cannot really fail — tests that ship with zero behavioural assertions, or tests that only check their own internal mock scaffolding rather than any user-visible result. When the scanner was first switched on it admitted a backlog of 626 such weak tests so the safety net could land without first cleaning every test; the open follow-up was filed alongside it. This change starts paying down that backlog by addressing the 78 worst entries — the ones with no assertion at all (71 tests) and the ones whose only assertion checks a mock (7 tests). The remaining 548 weaker-but-not-worthless entries are intentionally left for smaller per-area follow-ups.

## What Changed (for the User)

- The 78 worst entries in the project's test-quality backlog list have been resolved: each affected test now either carries a real assertion that would catch a regression in the code it covers, or it has been removed and the report records which existing test covers the same ground.
- The platform's automated quality gate that polices test strength now blocks a slightly bigger slice of the codebase: anyone who later adds a no-assertion or mock-only test is flagged immediately rather than silently joining the backlog.
- The internal test-improvement planning document is updated to record the 78-entry cleanup, with the remaining backlog explicitly carried forward as smaller per-area follow-ups.

## How It Behaves

- Existing test runs (both the developer's local commands and the platform's per-item gates) behave the same on the green path. The strengthened tests still pass; nothing user-visible in the dashboard or daemon changes.
- If a future change to the product accidentally regresses behaviour that one of these 78 tests now covers, the test fires red and the platform's per-item gates block the merge — which is the point of the cleanup.
- If a future contributor writes a brand-new test that has no assertion, or whose only assertion is a mock-call check, the test-strength gate fails immediately and the merge is blocked. Previously the backlog absorbed such cases silently for the entries already on the list.
- The much larger "weak but not worthless" backlog of tautological tests is untouched by this change and continues to be admitted by the scanner — it will be addressed by future per-area cleanups.

## Out of Scope

- The 548 tautological backlog entries — those are deferred to smaller per-area follow-ups.
- Any change to the test-strength rules themselves; this change applies the existing rules, it does not redefine them.
- Any production code change; the cleanup stays inside the test suite, the backlog file, and the planning document.

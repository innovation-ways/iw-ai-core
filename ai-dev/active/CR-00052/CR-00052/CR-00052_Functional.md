# CR-00052 — Functional Design

<!--
Audience: humans (product owners, support, onboarding engineers).
DO NOT include file paths, class names, SQL, code fences, or implementation
steps. If you need to capture those, they belong in the technical design doc.
Keep the total body at most 500 words (the review skill blocks >500).
-->

## ⛔ Docker is off-limits

Standard policy. This work only touches the build system and documentation.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work does not add, modify, or remove any database migrations.

## Why

Two tidy-up items have been outstanding since the test-strategy plan. First, the project has six developer-facing reporting commands advertised but never implemented — they exist as named targets that quietly do nothing when invoked. Second, the fast critical-path test layer has no written contract: sixteen tests today, the marker says "about ten," no documented time budget. This work fixes both: the reporting commands get real implementations, and the fast critical-path layer gets a written contract (≤15 tests, completes in <60 s, covers five documented critical paths, future additions must re-check the contract).

## What Changed (for the User)

- A developer running the reporting commands now gets a real test report at a known location, plus commands to generate an HTML view or serve a local browser dashboard. Previously these commands silently did nothing.
- The fast critical-path test layer has a written contract: ≤15 tests, <60 s wall-clock on a clean dev environment, covering five named critical paths (daemon worktree start; dashboard main pages; the identifier-allocation command; the work-item-queueing flow; the health-check endpoint).
- The marker description states the contract inline, so a future developer reads it directly when adding a test.
- The enhancement plan records what landed: curated count, measured wall-clock, and which critical path each test maps to.
- The reporting artefacts are git-ignored; they live in a known output directory but never get tracked.

## How It Behaves

- A developer wanting a rich test report runs one of the new commands. The runs are local — no effect on continuous integration; per-item merge gates are unchanged.
- The fast critical-path layer continues to run as the first continuous-integration gate as today, but with the contract codified so reviewers catch drift early.
- If someone marks a slow new test as fast-critical, the codified contract triggers either rejecting the marker or trimming a redundant existing test — keeping the layer tight by design.
- The audit trail records the table that justified each kept test, so future readers can see why the layer is its current size.

## Out of Scope

- A mechanical command that fails on contract breach — prose for now; future follow-up adds enforcement if drift happens.
- New tests — the layer is *curated*, not *expanded*.
- CI changes beyond minimum — reports stay a local dev tool.
- Sibling projects — picked up via their own sync cadence.

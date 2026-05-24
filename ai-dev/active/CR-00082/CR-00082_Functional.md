# CR-00082 — Functional Design

<!--
Audience: humans (product owners, support, onboarding engineers).
DO NOT include file paths, class names, SQL, code fences, or implementation
steps. If you need to capture those, they belong in the technical design doc.
Keep the total body at most 500 words (the review skill blocks >500).
-->

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work item adds no database migrations.

## Why

The doc system produces two kinds of finished artefact for users: an in-browser HTML view and a downloadable PDF export. Today the engineering team has no way to notice when a style or template change quietly breaks the layout of those artefacts — the existing test gates check that the pages respond and that the data is right, but nothing looks at the actual pixels. A subtle change to a stylesheet, a template, or the markdown rendering pipeline can ship to production and only be caught when a reader sees a broken page. This change closes that gap by adding a dedicated visual-regression layer.

## What Changed (for the User)

For end users the experience does not change at all. The change is internal to the engineering team and benefits readers indirectly by raising the chance that layout regressions are caught before they reach production.

For engineers and reviewers, two new things show up:

- A new umbrella check the team can run on demand that pixel-compares every editorial-category-representative HTML page and PDF export against a previously approved baseline image. When something has drifted, the check fails and leaves three images per affected page on disk: what the page looks like now, what it looked like at the baseline, and a highlighted diff. A reviewer can open them and decide whether the change is intentional.
- A nightly continuous-integration job that runs the same check, plus an automatic trigger on any pull request that touches the styling, the document templates, or the editorial configuration that drives layout.

## How It Behaves

The check runs in two parts. The first part takes every approved PDF in the baseline set, splits it into one image per page, and compares each page to the matching reference image. The second part opens every approved HTML doc page in a headless browser, takes a screenshot, and compares that to the matching reference image. Both parts share the same comparison code and the same small tolerance budget for tiny rendering differences that are not real regressions.

On a match, the check is silent and the job exits successfully. On a mismatch, the check fails loudly, names every page that drifted, and writes the three diagnostic images per page so a human can review the change. Updating a baseline is a deliberate review act: a pull request that changes a baseline image must justify the diff. Baselines are never auto-accepted.

The baseline set is intentionally small — one PDF and one HTML page per editorial category — to keep the wall-clock cost low while still covering every category the doc system produces.

## Out of Scope

- This is not a per-batch quality gate. The check is too slow to run on every work item; it runs nightly and on pull requests that touch styling or templates only.
- This work does not introduce any user-visible feature, dashboard page, or API change.

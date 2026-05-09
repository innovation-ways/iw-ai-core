# CR-00040 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt. This work item does not touch Docker.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This work item leaves all migrations unchanged — only prompt instructions are edited.)

## Why

A self-review of the previous change request found that our automated code reviewer had to do its job twice: once where it skimmed past the design document and missed a test-update obligation, and a second time on a fix cycle where the design document was finally consulted. The reviewer's instructions told it to read the design doc, but that instruction was buried after a long block of safety banners and was easy to overlook. We want first-pass code reviews to consult the design document before reading any code, every time.

## What Changed (for the User)

- Code reviews running as part of any future work item now begin by reading the design document — specifically the acceptance criteria and the test plan — before they look at the code.
- When a design document explicitly names test files that need updating, the reviewer treats a missing update to those files as a critical finding instead of letting it slide to a fix cycle.
- The change is invisible during normal use; the only observable difference is that fewer change requests will need a second code-review pass to catch test gaps that the design document already called out.
- The improved review instructions are propagated to every project managed by Innovation Ways AI Core, so all projects benefit from the same standard from their next item onwards.

## How It Behaves

When a new code review starts, the reviewer's first action is now to open the design document, read the acceptance criteria and test plan in full, and write down the test files the design says should change. The reviewer then runs the existing lint and format gates, opens the changed files, and scores findings against the design document's expectations. If the design document says a particular test file should have been updated and it has not been, the reviewer flags that as a blocker — same severity as a missing requirement, with the same effect on the merge pipeline.

The same pattern applies to the broader cross-step final review at the end of a work item: it cross-checks every test file the design names against the list of files actually changed by the implementation steps, and any unmatched reference becomes a critical finding.

For everything else — Docker safety, migration policy, the result format the reviewer reports back, the severity scale — nothing changes. The new instruction is purely additive at the front of the existing review process.

## Out of Scope

- The fix-cycle review prompts already anchor on the design document; they are not edited.
- No browser, dashboard, database, or runtime behaviour is changed; this work touches only the markdown instructions consumed by review agents.

# CR-00084 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. Migrations unchanged.

## Why

The project already has an automated check that scans every test for dead-on-arrival patterns: tests with no assertion, tests comparing a constant to itself, tests whose only check is that a mock was called. That gate is structural — it judges the shape of the assertion, not whether it is strong enough to catch a real regression. A test can write one harmless assertion, pass the gate, and still be useless. This work explores whether asking a stronger AI model to read a new test alongside the production code it exercises can flag those semantically-weak tests as a useful second opinion. The plan tracker labels this experimental: no AI judge is uniformly reliable, so the rule is calibrate first, prove worth, then wire in — and never as a blocker.

## What Changed (for the User)

Two operator-facing things exist that did not before. First, a small command-line utility lets a reviewer point at one test and the production code it exercises and get back a score on three axes: assertion specificity, behaviour-versus-mock, and edge coverage. The utility prints the model's reasoning and always prints the token cost. Second, the code-review step that runs on every implementation step gains an optional advisory line: when a step adds new test files, the reviewer can run the judge over each one and paste the score into the review report as informational context. The advisory line is never a blocker — a low score does not fail the review, and a missing judge run does not fail the review either. A small hand-labelled set of real tests from this project, tagged strong or weak by a human, ships alongside the utility so the judge's accuracy is measurable. The measurement decides whether the advisory hook ships enabled or shelved.

## How It Behaves

A reviewer invokes the judge utility for a specific test. The utility builds a prompt with the test code and production code under test, sends it to the stronger model, and emits one record with three axis scores, an overall score, and a short rationale. Token usage and dollar cost go to standard error. If the API key is absent the utility exits with a distinct error code, so callers can tell that apart from a real upstream failure. A calibration command runs the judge over the labelled set and prints a confusion matrix, the recall on weak tests, and the false-positive rate on strong tests. If recall is at least seventy percent and false positives stay below thirty percent, the advisory hook ships live; otherwise the hook ships dormant with a note pointing at the calibration evidence. There is no retry and no automatic loop — one call per test, by design, to keep the spike's cost predictable.

## Out of Scope

- Promoting the judge to a blocking gate. A low score does not fail any quality gate; that promotion is an explicit follow-up once advisory evidence accumulates.
- Touching production code outside the existing code-review agent instructions.

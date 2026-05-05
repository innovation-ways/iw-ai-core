# CR-00032 — Functional Design

## Why

When a recent bug fix ran through the automated pipeline, its very first step
needed three attempts before the regression test ran cleanly. Both wasted
attempts had the same root cause: the template the agent followed when
drafting the bug-fix plan said nothing about *where* dashboard tests should
live or *how* to write assertions that target rendered HTML rather than
incidental string matches in the response body. This change closes that gap so
future bug fixes do not pay the same tax.

## What Changed (for the User)

- Anyone drafting a bug fix from the Issue template now sees a short, explicit
  rule about which test directory applies to which kind of test — UI/template
  tests, plain unit tests, and database-backed integration tests each have
  their own home, and the template now names them.
- The template also explains, with a contrasting good/bad example, how to
  scope an assertion when checking that a CSS class actually reached the
  rendered page, instead of asserting on the bare class name as a substring
  (which can match coincidentally and give a false green).
- Every managed project's local copy of the template is refreshed at the same
  time, so the guidance is uniform across the platform.

## How It Behaves

- An author opening the Issue template to draft a new bug fix encounters the
  two new paragraphs in the same place they would already have been reading —
  the test sections, immediately around the failing-test scaffold.
- Existing bug-fix plans already in flight are untouched — the change is only
  applied to *future* plans drafted from the template.
- A reviewer scanning a draft bug-fix plan can now point to a specific rule in
  the template if a draft puts a UI test in the wrong directory or asserts on
  a bare class name.
- The same content appears identically in the master template and in every
  managed project's local copy after the sync step runs.

## Out of Scope

- The same drift may eventually warrant similar guidance in the feature and
  change-request templates, but those have different audiences and different
  test-strategy sections. They are deliberately left for a separate follow-up
  if and when their own post-mortems show the same pattern.
- This change does not retroactively edit any in-flight or already-completed
  bug-fix plan.

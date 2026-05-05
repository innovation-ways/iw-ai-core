# CR-00034 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This change does not add or modify migrations.)

## Why

The Recent Activity truncation test suite checks that the full message text appears in a hidden attribute on the page. The current check compares the raw fixture string against the rendered page. That works today only because the fixtures happen to contain plain letters. The moment a future contributor uses a fixture that contains a quote, an angle bracket, or an ampersand, the dashboard renders an escaped version of those characters and the check silently stops finding what it is looking for. The follow-up analysis from the previous Recent Activity work flagged this as a low-severity but real piece of test debt and recommended the fix while the context is fresh.

## What Changed (for the User)

There is no change for end users. Operators and contributors gain a more durable safety net: the Recent Activity truncation tests now compare like-for-like with what the dashboard actually renders. Engineers who later add new fixtures with realistic error messages will not have to debug a failing assertion that looks like a template regression but is really an escape-encoding mismatch.

## How It Behaves

Before the change, the test takes the fixture text and looks for an exact match inside the rendered page. After the change, the test takes the same fixture, runs it through the same escaping rules the dashboard template applies, and looks for the escaped form. For the existing fixtures (long runs of plain letters) both forms are identical, so the tests pass exactly as they do today. For any future fixture that contains characters the dashboard escapes, both sides of the comparison are escaped consistently and the test passes if and only if the dashboard truly emitted the right value. The test no longer leans on the accident that the current fixtures avoid every escapable character.

This is a self-contained adjustment to two assertions inside one test file. The dashboard, the database, and every other test continue to behave exactly as before.

## Out of Scope

- Adding new tests, new fixtures, or new escape characters to assert against. The fix only hardens the two assertions flagged by the prior analysis.
- Touching the dashboard template, the activity model, or any production code path. This is a test-file-only change.

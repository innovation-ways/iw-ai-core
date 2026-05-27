# CR-00090 — Functional Design

<!--
Audience: humans (product owners, support, onboarding engineers).
DO NOT include file paths, class names, SQL, code fences, or implementation
steps. If you need to capture those, they belong in the technical design doc.
Keep the total body at most 500 words (the review skill blocks >500).
-->

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

No migration required. This change does not touch the database schema.

## Why

Browser-driven verification steps were producing false failures on every restart of the isolated E2E container. The dashboard's HTMX polling elements were supposed to stop sending background requests when running inside a browser automation context, but the detection mechanism relied on the browser's User-Agent string containing a "headless" marker. Modern versions of the browser automation tool send a normal User-Agent with no such marker, so the detection always returned false, polling always ran, and when the container restarted between fix cycles the browser received connection errors that looked like application bugs. This triggered false verdicts, wasted operator time, and burned fix-cycle slots on problems that were not code defects.

## What Changed (for the User)

- The E2E verification container now carries an explicit flag that tells the application it is running in automated browser mode.
- Pages that contain live-reload indicators no longer fire background network requests when that flag is present, eliminating the spurious connection errors that were causing false failure verdicts.
- Production and development environments are unaffected — the flag is absent outside the verification container, so all live-reload indicators behave exactly as before.
- The old browser-UA detection remains active as a safety fallback for direct browser automation scenarios that run outside the compose-based verification stack.

## How It Behaves

When an automated browser verification run starts, the platform spins up an isolated application container. That container now receives an explicit environment signal indicating it is operating in E2E mode. On startup, the application reads this signal and makes it available to every page it renders. Pages that contain auto-updating indicators check this flag first; when it is set, those indicators are rendered in a quiet state with no automatic refresh behaviour. When the automated browser navigates through the dashboard, no background polling requests are issued, so a container restart or port change during a fix cycle cannot generate network errors in the browser console. A clean console means the verification agent reports an accurate result based on actual application behaviour rather than infrastructure noise.

When the same application runs without the flag — in production, on a developer's machine, or in manual browser sessions — the auto-updating indicators behave identically to before this change: they poll on load and refresh every N seconds as intended.

## Out of Scope

- No change to the polling interval or polling behaviour in non-automated environments.
- No change to the verification steps themselves; this fix operates entirely at the application layer.

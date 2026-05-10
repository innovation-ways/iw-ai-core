# CR-00043 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This change adds, modifies, or removes no database migrations.

## Why

A recent fix changed how the dashboard turns documentation pages into PDF — it now drives a real headless browser so diagram labels render correctly. But it mostly assumed that browser sits at one fixed location, which is only true on the machine where the dashboard normally runs. Inside the throwaway environment the platform spins up to verify changes in a browser, it isn't there — so PDF export quietly reports "unavailable", and the automated browser check for the original fix could never confirm the real PDF path works; it had to settle for confirming the "unavailable" message at least showed cleanly. This change makes the dashboard find a browser wherever it lives, and makes sure that verification environment ships one.

## What Changed (for the User)

- In the live production dashboard: nothing visibly changes — PDF export already worked there and still does.
- In the platform's browser-verification environment: documentation PDF export now produces a real PDF (with diagram labels) instead of an "unavailable" message, so the automated check for the earlier PDF fix can confirm the real thing.
- The existing optional setting that points the dashboard at a specific browser is kept (same name as before); the dashboard now also looks in more places automatically — the bundled-browser cache regardless of its version number, then any system-installed Chrome/Chromium — before giving up.
- If no browser can be found at all, the dashboard still degrades gracefully: the same clean "PDF generation unavailable" response as before rather than an error, and on-page diagrams still render via the existing fallback.

## How It Behaves

When the dashboard needs to produce a PDF (or render a diagram) it looks for a browser in order: the explicitly configured location, if that setting is set and the file is actually there; then the newest browser in the platform's automation-tooling cache (so the exact version number stops mattering); then any system Chrome or Chromium on the machine. The first one that exists wins. If none is found, the PDF request returns the existing "unavailable" response and diagram rendering uses its other path — exactly as today. The browser-verification environment is updated to include a browser, so there the "found" branch is taken and PDFs render for real — which is what lets the automated check for the earlier PDF fix confirm a genuine PDF comes back, not just a polite error.

## Out of Scope

- A wider cleanup to remove every remaining reference to one specific bundled-browser version number — only the reference that affected PDF/diagram rendering is addressed here.
- Putting a browser inside each agent's per-worktree working sandbox — that sandbox runs under a restricted user where the simple install doesn't work, and it isn't the environment the browser check runs against; left as a follow-up.
- Any change to how PDFs look or what they contain — this is purely about reliably finding a browser to make them.

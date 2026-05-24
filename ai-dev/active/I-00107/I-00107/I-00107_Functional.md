# I-00107 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This item adds, modifies, or removes no migration — it is a pure daemon behaviour fix.

## Why

The orchestration daemon offers two operator commands for picking up configuration changes: a lightweight reload and a full restart. The reload is documented as the right way to apply a per-project orchestration-config edit. In practice, when a project's enabled state and registry entry are unchanged, the reload silently fails to apply the new settings — the daemon keeps using the values it loaded at startup. Operators see a log line that says the reload was triggered, conclude that the change is live, and only discover the truth later when the new settings still aren't in effect. This bug cost real debugging time during the BATCH-00127 overlap-gate widening on 2026-05-22.

## What Changed (for the User)

- Editing a project's orchestration config and running the daemon reload command now actually applies the change. The next polling cycle uses the new settings.
- The fix covers all per-project orchestration settings: parallelism cap, fix-cycle limit, overlap-gate block and allow rules, browser-verification settings, and the test/quality command catalogs surfaced in the dashboard.
- Toggling a project from disabled to enabled (or back) now also refreshes the in-memory orchestration state for that project — previously only the registry entry was refreshed.
- A new daemon event records each time a project's config is reloaded, giving operators a positive confirmation on the dashboard that the reload took effect.

## How It Behaves

When the operator sends the reload signal, the daemon re-reads each managed project's orchestration config. For every project whose effective config has actually changed since the last load, the daemon swaps in the new settings for the next polling cycle and writes a config-reloaded event. Projects whose config has not changed are left alone — no needless churn, no spurious events.

If the orchestration config file is malformed during the reload, the daemon keeps the last-known-good config for that project, logs a warning, and continues running the other projects normally. The full restart command continues to behave exactly as before; operators who prefer it can still use it.

Items currently executing in a worktree are unaffected by the reload — their agent subprocesses run independently of the in-memory config snapshot the daemon swaps. Any newly launched item picks up the new config naturally.

## Out of Scope

- This fix does not add automatic file-watching for unsignalled edits to the orchestration config. The operator still needs to send the reload signal explicitly; the change is that the signal now does what it promises.
- This fix does not change the global registry file's reload behaviour, only the per-project config behaviour. The registry path was already working correctly.

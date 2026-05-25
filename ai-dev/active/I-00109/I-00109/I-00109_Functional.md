# I-00109 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This item leaves migrations unchanged.)

## Why

The dashboard's per-document Download PDF button lets users download a freshly rendered PDF of any registered project documentation page. On hosts where the project's working directory is not writable — a hardened container, a read-only mount, a restrictive permission setup — clicking the button currently returns a generic Internal Server Error instead of the PDF, even though the PDF itself was successfully rendered server-side a moment earlier. The failure happens entirely in an optional step that tries to save the rendered PDF under the project's folder for next time; the request should never be allowed to fail because of that. A sibling page in the same area of the dashboard (the in-page PDF preview) already handles the same situation gracefully; the download button simply missed that safety net. An automated route-coverage test introduced earlier this week pins this symptom as a known operator follow-up.

## What Changed (for the User)

- Clicking Download PDF on any project documentation page now always returns the PDF when generation succeeds, even when the server cannot save a cached copy.
- Users no longer see an Internal Server Error on hosts with a read-only working directory.
- When the optional cache cannot be written, the server logs an internal warning so operators can investigate, but the user-facing download still completes normally.
- The in-page PDF preview behaviour is unchanged — it already handled this case correctly. The download button now matches it.

## How It Behaves

When a user clicks Download PDF, the dashboard checks whether a previously rendered PDF for that document version is already on disk:

- If a cached copy exists, it is served as the download immediately.
- If not, the dashboard renders a fresh PDF in memory.
  - If the rendering engine is not available on the server, the user gets a clear "PDF generation unavailable" message (unchanged behaviour).
  - Otherwise the freshly rendered PDF is returned as the download, and the server tries to save a copy for next time.
- If saving succeeds, the next download is served from the cached copy.
- If saving fails for any reason — permissions, full disk, read-only mount — the user still receives their PDF without interruption and the failure is recorded as a warning in the server log. The next download simply re-renders.

The download itself never fails because of a cache-save problem. Only failures of the actual PDF rendering affect what the user sees, and that path is unchanged.

## Out of Scope

- This change does not consolidate the download and in-page preview handlers into a shared helper. Both now use the same safety-net pattern, but the two code paths remain independent. A future, separate change can unify them if desired.
- This change does not introduce a new caching backend, a configurable cache directory, or any user-visible setting for the disk cache.

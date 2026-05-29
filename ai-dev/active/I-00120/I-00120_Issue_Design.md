# I-00120: Codex usage chips silently show 0% when the opencode OAuth token is expired or invalid

**Type**: Issue
**Severity**: Low
**Created**: 2026-05-28
**Reported By**: Operator (dashboard observation — "CODEX usage values stuck at 0%")
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This item adds **no** migrations. It touches a service function, a router, and a Jinja2 fragment only.

## Description

The footer "Codex" usage chips render `5h 0% · 7d 0%` in normal styling whenever the OpenAI OAuth access token in opencode's `auth.json` is expired, missing, or rejected by the upstream endpoint. A genuine "0% usage" state and a "auth is broken" state look identical, so the operator is never told the token needs renewing and assumes the data is live. This is purely a visibility/observability gap — no functional behaviour is broken.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Relevant: the dashboard is server-rendered Jinja2 + htmx; the footer fragment is re-fetched every 60s via `GET /api/usage/llm/fragment`. Routers are thin; usage data is produced by `orch/llm_usage.py`. Tailwind CSS is prebuilt — prefer CSS classes already present in `dashboard/static/styles.css` (`make css` is flaky in worktrees, see I-00067).

## Steps to Reproduce

1. Authenticate opencode for the OpenAI provider so `~/.local/share/opencode/auth.json` has an `openai` entry with `type: "oauth"`.
2. Let the access token lapse (its `expires` epoch-ms passes), or do not run opencode again for long enough that the stored token is no longer valid.
3. Open the dashboard (`http://localhost:9900/`) and look at the footer Codex chips.

**Expected**: The Codex chip surfaces a visible warning (e.g. `Codex ⚠ token expired — re-authenticate`) so the operator knows the value is not live and must re-authenticate.

**Actual**: The Codex chip shows `5h 0% · 7d 0%` in normal (non-warning) styling, indistinguishable from a real zero-usage reading.

## Browser Evidence

Pre-fix screenshot of the buggy state (footer Codex chips at `5h 0% · 7d 0%`, no warning, despite the live token being ~101h past expiry):

- `ai-dev/active/I-00120/evidences/pre/I-00120-bug-evidence.png`

Confirmed at investigation time that `GET https://chatgpt.com/backend-api/wham/usage` with the stored token returns `401` with body `{"error":{"code":"token_expired", ...}}`.

## Browser Verification Script

```bash
playwright-cli kill-all
playwright-cli open http://localhost:9900/
playwright-cli screenshot      # footer shows Codex 5h 0% · 7d 0%, no warning (PRE state)
```

## Root Cause Analysis

`orch/llm_usage.py:_codex_usage()` (lines 370–392) collapses **every** failure mode into the same zeroed dict `_CODEX_ZERO` (`block_pct: 0, week_pct: 0, *_reset: None`):

- `_load_openai_oauth()` returns `None` (missing file / no OAuth entry) → returns `_CODEX_ZERO`.
- `_codex_usage_remote()` raises (the upstream `resp.raise_for_status()` throws `httpx.HTTPStatusError` on the `401 token_expired`, or any transport/decode error) → caught, logged, returns `_CODEX_ZERO`.

The returned dict carries **no status flag**, so the consumer — `dashboard/routers/usage.py:llm_usage_fragment()` (lines 30–58) and `dashboard/templates/fragments/llm_usage_footer.html` (lines 36–52) — cannot distinguish "0% genuine usage" from "auth broken". The template renders the same bars in both cases.

The original design (module docstring, `orch/llm_usage.py:34-40`) deliberately did **not** refresh tokens, assuming opencode would be re-invoked often enough to keep the token fresh. On a host where opencode is not run while the daemon/dashboard poll continuously, that assumption fails and the chip is stuck at 0% indefinitely.

This fix adds a **status** discriminator and surfaces it as a warning. It does **NOT** add token refresh (explicitly out of scope per the reporter).

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/llm_usage.py` (`_codex_usage`) | Returns one undifferentiated zeroed dict for all failure modes; no way to tell "0% usage" from "auth broken" |
| `dashboard/routers/usage.py` (`llm_usage_fragment`) | Cannot pass a warning state to the template because the data lacks one |
| `dashboard/templates/fragments/llm_usage_footer.html` | Always renders Codex bars; no warning affordance |

## Fix Plan

### Agents and Execution Order

> **Step-granularity rule**: each implementation step targets one cohesive concern. See `skills/iw-workflow/SKILL.md`.

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Add a `status` discriminator to `_codex_usage()` (`ok`/`expired`/`unauthenticated`/`error`): proactive `expires` check + 401 detection + auth-missing + catch-all. Never raises. | — |
| S02 | CodeReview | Review S01 output | — |
| S03 | frontend-impl | Map status → warning message in `usage.py`; replace the two Codex bars with inline warning text in the fragment when status ≠ `ok` | — |
| S04 | CodeReview | Review S03 output | — |
| S05 | Tests | Reproduction test + regression tests (backend status logic + router/template rendering) | — |
| S06 | CodeReview | Review S05 output | — |
| S07 | CodeReview_Final | Global cross-agent review | — |
| S08..S15 | QV Gates | lint, format, typecheck, arch-check, security-sast, unit-tests, frontend-tests, integration-tests | — |
| S16 | QV Browser | Verify the warning renders in the footer | — |
| S17 | SelfAssess | Post-execution self-assessment (`self_assess = true`) | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None

### Code Changes

- **Files to modify**: `orch/llm_usage.py`, `dashboard/routers/usage.py`, `dashboard/templates/fragments/llm_usage_footer.html`
- **Nature of change**: Add a `status` field to the Codex usage dict distinguishing the failure modes; map it to a warning message in the router; render warning text in the fragment when status ≠ `ok`.

### Status discriminator contract

`_codex_usage()` always returns a dict with a `"status"` key, one of:

| status | Trigger |
|--------|---------|
| `ok` | Usage fetched successfully from the endpoint |
| `expired` | Stored `expires` epoch-ms is at/before now, OR the endpoint returns HTTP `401` |
| `unauthenticated` | `auth.json` missing, or no valid `openai` OAuth entry (`_load_openai_oauth()` is `None`) |
| `error` | Any other transport/decode/schema failure (non-401 HTTP error, network error, JSON decode) |

When status ≠ `ok`, `block_pct`/`week_pct` are `0` and `*_reset` are `None` (unchanged zeroed shape, plus the new key).

### Warning message mapping (router → template)

| status | Footer warning text |
|--------|---------------------|
| `expired` | `⚠ token expired — re-authenticate` |
| `unauthenticated` | `⚠ not configured — run opencode auth login` |
| `error` | `⚠ usage unavailable` |
| `ok` | (no warning — normal bars) |

Rendered in `text-amber-600` (already present in compiled `styles.css` — no `make css` required).

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00120_Issue_Design.md` | Design | This document |
| `I-00120_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/I-00120_S01_Backend_prompt.md` | Prompt | S01 backend status discriminator |
| `prompts/I-00120_S02_CodeReview_prompt.md` | Prompt | Review S01 |
| `prompts/I-00120_S03_Frontend_prompt.md` | Prompt | S03 router mapping + fragment warning |
| `prompts/I-00120_S04_CodeReview_prompt.md` | Prompt | Review S03 |
| `prompts/I-00120_S05_Tests_prompt.md` | Prompt | Reproduction + regression tests |
| `prompts/I-00120_S06_CodeReview_prompt.md` | Prompt | Review S05 |
| `prompts/I-00120_S07_CodeReview_Final_prompt.md` | Prompt | Global review |
| `prompts/I-00120_S16_BrowserVerification_prompt.md` | Prompt | Browser verification |
| `prompts/I-00120_S17_SelfAssess_prompt.md` | Prompt | Self-assessment |

Reports are created during execution in `ai-dev/work/I-00120/reports/`.

## Test to Reproduce

**Test-file location**: backend status logic is pure Python (no FastAPI / DB) → `tests/unit/test_llm_usage.py`. Fragment rendering drives a FastAPI route via `TestClient` → must live under `tests/dashboard/` (new file `tests/dashboard/test_usage_fragment.py` with its own file-local `client` fixture).

```python
def test_codex_usage_expired_token_reports_expired_status(monkeypatch):
    """FAILS before the fix (no 'status' key); PASSES after.

    A 401 token_expired from the endpoint must surface status == 'expired',
    not an undifferentiated zeroed dict.
    """
    monkeypatch.setattr(llm_usage, "_load_openai_oauth",
                        lambda: {"access": "tok", "accountId": "acct", "expires": 1})
    # _oauth proactively expired (expires=1 epoch-ms is far in the past)
    result = llm_usage._codex_usage()
    assert result["status"] == "expired"
    assert result["block_pct"] == 0
```

## Acceptance Criteria

### AC1: Bug is fixed

```
Given the opencode OAuth access token is expired (or missing, or rejected with 401)
When the dashboard footer fragment is rendered
Then the Codex chip shows a visible warning describing the auth problem
And the silent "0%" bars are not shown for that failure state
```

### AC2: Regression test exists

```
Given the fix is applied
When the test suite runs
Then a reproduction test asserting status == "expired" for an expired token passes
And regression tests cover the unauthenticated, error, and ok states plus the rendered warning text
```

## Regression Prevention

- The `status` discriminator is now part of the Codex usage contract; tests assert a specific value per failure mode (semantic, not shape).
- A dashboard-level test asserts the warning text is rendered (attribute-scoped assertion) for a non-`ok` status and absent for `ok`, so a future regression that drops the warning is caught.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

- `orch/llm_usage.py`
- `dashboard/routers/usage.py`
- `dashboard/templates/fragments/llm_usage_footer.html`
- `tests/unit/test_llm_usage.py`
- `tests/dashboard/test_usage_fragment.py`

## TDD Approach

- Reproducing test: `tests/unit/test_llm_usage.py::test_codex_usage_expired_token_reports_expired_status` — fails before fix (no `status` key), passes after.
- Unit tests: all four statuses from `_codex_usage()` (`ok`, `expired` via proactive expiry AND via 401, `unauthenticated`, `error`); `_oauth_is_expired` boundary (expires in past / future / missing / non-numeric).
- Dashboard tests: `tests/dashboard/test_usage_fragment.py` — fragment renders the correct warning text per status and renders normal bars (no warning) when `ok`.

**Assertion scoping for CSS class names** — assert the warning using an attribute-scoped form, e.g. `assert 'text-amber-600' in html` combined with the specific warning phrase, not a bare substring that could match unrelated tokens.

## Notes

- **Token refresh is explicitly out of scope.** The reporter will re-authenticate manually; this item only surfaces the warning.
- The 60s in-process cache (`get_llm_usage`) means the warning can lag up to 60s behind the actual expiry — acceptable for this chip.
- In the isolated E2E/browser-verification stack the container has no opencode `auth.json`, so `_codex_usage()` naturally returns `status == "unauthenticated"` and the footer shows the "not configured" warning — this is the expected, verifiable state for S16.

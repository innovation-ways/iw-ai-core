# I-00079_S02_CodeReview_prompt

**Work Item**: I-00079 — Empty-state CTA links point to non-existent `/docs/<name>.md` route (404)
**Step Being Reviewed**: S01 (frontend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state.
Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item adds no migrations and touches no database schema. Flag any alembic/migration change as out of scope (CRITICAL).

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00079 --json`.
- `ai-dev/active/I-00079/I-00079_Issue_Design.md` — design document (read Root Cause Analysis, the affected-templates table, AC1–AC3, Notes)
- `ai-dev/active/I-00079/reports/I-00079_S01_frontend-impl_report.md` — S01 report
- All files in S01's `files_changed` (expected: `dashboard/templates/pages/project/queue.html`, `dashboard/templates/pages/project/history.html`, `dashboard/templates/pages/project/batches.html`, `dashboard/templates/pages/system/all_active.html`, `dashboard/templates/docs_library.html`, `dashboard/templates/research_library.html`, possibly `tests/dashboard/test_empty_states.py`)
- `dashboard/routers/help.py` — the `_SLUG_TO_DOC` map; S01's new `primary_href` values must agree with it (AC3)
- `dashboard/routers/system.py` — the doc viewer route (`/system/docs/{doc_path:path}` under the `/system` prefix); use it to sanity-check each new target resolves
- `dashboard/templates/macros/empty_state.html` — confirms `primary_href` is the literal `<a href>` value

## Output Files

- `ai-dev/active/I-00079/reports/I-00079_S02_CodeReview_report.md` — review report

## Context

You are reviewing S01's fix for I-00079: six `empty_state(...)` call sites had `primary_href="/docs/<name>.md"`, which 404s; they should be `/system/docs/<name>` (the dashboard's doc-viewer route, no `.md` suffix). Verify S01 changed exactly those, changed nothing else, and the new targets actually resolve.

## Read the Design Document FIRST

- `## Description` — the affected-templates table lists all six call sites and the exact old→new strings expected.
- `## Acceptance Criteria` — AC1 (CTAs no longer 404), AC2 (regression test exists), AC3 (CTA targets agree with `help.py`'s `_SLUG_TO_DOC`).
- `## TDD Approach` / `## Test to Reproduce` — note that the full regression test is S03's job; S01 only needs a minimal RED→GREEN assertion in `tests/dashboard/test_empty_states.py`. If S01 added zero tests, that's acceptable here (it's deferred to S03) — but if S01 claimed `tests_passed: true` with no test changes and no run, note it (MEDIUM).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on the files in S01's `files_changed`, fix nothing, report only:

```bash
make lint          # ruff + node --check (dashboard JS) + scripts/check_templates.py (Jinja2)
make format        # ruff format --check
```

Any NEW violation in the changed files (not present on `main` pre-S01) → CRITICAL finding with `"category":"conventions"`, `file`, `line`, and the exact code/message. If `make` is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Correctness — all six CTAs fixed, and only those

- `grep -rn 'primary_href="/docs/' dashboard/` returns **nothing** (no remaining bare `/docs/...` empty-state targets).
- `grep -rn '"/docs/[A-Za-z0-9_./-]*\.md' dashboard/templates/` returns nothing (no `/docs/*.md` link targets left in any template).
- Each of the six `empty_state(...)` calls now has exactly:
  - `queue.html` (×2): `primary_href="/system/docs/IW_AI_Core_CLI_Spec#iw-approve"`
  - `history.html`: `primary_href="/system/docs/IW_AI_Core_Architecture"`
  - `batches.html`: `primary_href="/system/docs/IW_AI_Core_Daemon_Design#batches"`
  - `all_active.html`: `primary_href="/system/docs/IW_AI_Core_Daemon_Design"`
  - `docs_library.html`: `primary_href="/system/docs/implementation/00_INDEX"`
  - `research_library.html`: `primary_href="/system/docs/implementation/00_INDEX"`
- Nothing else in those files changed (no `slug`/`heading`/`body`/`primary_label`/`secondary_*` edits, no styling changes, no unrelated link edits). Use `git diff` against `main`.
- **The new targets actually resolve.** Either reason from `system.py` (`_DOC_URL_MAP` keys: `docs/IW_AI_Core_CLI_Spec.md` → `IW_AI_Core_CLI_Spec`; `docs/IW_AI_Core_Architecture.md` → `IW_AI_Core_Architecture`; `docs/IW_AI_Core_Daemon_Design.md` → `IW_AI_Core_Daemon_Design`; `docs/implementation/00_INDEX.md` → `implementation/00_INDEX`), or run the dashboard `client` fixture and `GET /system/docs/<key>` for each — every one must return 200. The `#iw-approve` / `#batches` anchors are best-effort and don't affect the 200; just confirm the path component is right.

### 2. Consistency with `help.py` (AC3)

For each page slug, the empty-state `primary_href` and `help.py`'s `_SLUG_TO_DOC[slug]` must point at the same `/system/docs/<DocName>`:
- `queue` → `/system/docs/IW_AI_Core_CLI_Spec#iw-approve` (exact match including anchor)
- `history` → help.py has `/system/docs/IW_AI_Core_CLI_Spec`; the design deliberately chose `/system/docs/IW_AI_Core_Architecture` for the *empty-state* CTA (the CTA label is "How execution works →"). This is an intentional, documented divergence (see the design's Code Changes note) — **not** a finding. Confirm S01 used `/system/docs/IW_AI_Core_Architecture` as the design specifies.
- `batches` → `/system/docs/IW_AI_Core_Daemon_Design#batches` (matches help.py's `batch_detail`/`batches` doc)
- `all_active` → `/system/docs/IW_AI_Core_Daemon_Design` (matches help.py's `all_active`)
- `docs` / `research` library pages → `/system/docs/implementation/00_INDEX` (the catalogue index; help.py points the `docs`/`research` slugs at the Dashboard Design doc — again the CTA's label is "Doc catalogue →", so the index target is intentional).

Flag only a genuine mismatch (e.g. a `.md` suffix slipped through, a wrong doc name, a `/docs/` instead of `/system/docs/`) — not the deliberate label-driven target choices the design records.

### 3. Project conventions

- Tailwind class idioms unchanged (S01 shouldn't have touched any classes). No dynamically-constructed class strings.
- Jinja2 `format` filter stays `%`-style (only relevant if S01 touched a template with a `format` call — it shouldn't have).
- Read `dashboard/CLAUDE.md` and `CLAUDE.md` for anything else.

### 4. Security

- No hardcoded secrets/URLs/ports introduced. (Relative paths only — none expected.)

### 5. Testing

- If `tests/dashboard/test_empty_states.py` was touched, do the new assertions check **semantics** — that the href resolves to 200 and is not the `/docs/*.md` form — rather than just "the word `IW_AI_Core_CLI_Spec` appears somewhere in the HTML"? Bare-substring checks are a MEDIUM (fixable) finding; href checks should be attribute-scoped on `class="empty-state__cta-primary"`. (The *complete* test set is S03's responsibility — don't fail S02 merely because S01's seed test is minimal.)

## Test Verification (NON-NEGOTIABLE)

Run `make test-unit` (fast, no containers) to confirm no regression, and `uv run pytest tests/dashboard/test_empty_states.py -v`. Report results accurately in the contract.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | A CTA still 404s (wrong path, `.md` suffix left, bare `/docs/`); unrelated files changed materially; lint/format violation introduced; migration sneaked in | Must fix before merge |
| HIGH | A CTA points at the wrong doc; an AC unmet | Must fix before merge |
| MEDIUM (fixable) | Shape-only seed test; minor convention issue | Should fix in fix cycle |
| MEDIUM (suggestion) / LOW | Optional / informational | — |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00079",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {"severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW", "category": "architecture|code_quality|conventions|security|testing", "file": "path", "line": 0, "description": "...", "suggestion": "..."}
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` only if zero CRITICAL/HIGH and zero MEDIUM (fixable). Otherwise `fail`.
- `mandatory_fix_count`: count of CRITICAL + HIGH + MEDIUM (fixable).

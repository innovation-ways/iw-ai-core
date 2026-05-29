# I-00120_S05_Tests_prompt

**Work Item**: I-00120 — Codex usage chips silently show 0% when the opencode OAuth token is expired or invalid
**Step**: S05
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state. Testcontainer
fixtures spun up by pytest are allowed (they self-label and self-destruct via Ryuk). Read-only
introspection and `./ai-core.sh` / `make` targets are allowed.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This item adds no migrations.

## Input Files

- Runtime step state: `uv run iw item-status I-00120 --json`.
- `ai-dev/active/I-00120/I-00120_Issue_Design.md` — design doc (read **Test to Reproduce** and **TDD Approach**).
- S01/S03 reports + their `files_changed`.
- Existing tests: `tests/unit/test_llm_usage.py` (note `TestCodexUsage`, `TestGetLlmUsageCodexIntegration`).
- `tests/dashboard/conftest.py` and an existing `tests/dashboard/test_*.py` for the file-local `client` fixture pattern.

## Output Files

- `ai-dev/work/I-00120/reports/I-00120_S05_Tests_report.md` — step report.

## Context

Write the reproduction test and the regression suite for I-00120. The bug: the Codex usage path
collapsed every failure mode into an undifferentiated zeroed dict, so the dashboard could not tell
"0% usage" from "auth broken". The fix added a `status` discriminator (`ok`/`expired`/`unauthenticated`/
`error`) and a footer warning.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

For this item that means: do NOT merely assert `"status" in result`. Assert
`result["status"] == "expired"` for the expired case, `== "unauthenticated"` for the missing-auth case,
etc., and assert the rendered HTML contains the **specific warning phrase** for each state — and that
the normal bars are **absent** in a warning state (and the warning is **absent** in the `ok` state).

## Requirements

### 1. Reproduction test (backend) — `tests/unit/test_llm_usage.py`

Add a test that FAILS against pre-fix code (no `status` key) and PASSES after:

```python
def test_codex_usage_expired_token_reports_expired_status(monkeypatch):
    monkeypatch.setattr(llm_usage, "_load_openai_oauth",
                        lambda: {"access": "tok", "accountId": "acct", "expires": 1})
    result = llm_usage._codex_usage()
    assert result["status"] == "expired"
    assert result["block_pct"] == 0
```

### 2. Regression tests (backend) — `tests/unit/test_llm_usage.py`

Cover, with monkeypatching (never hit the network):
- `status == "ok"` on a successful `_codex_usage_remote` (monkeypatch the remote to return a valid dict;
  use a non-expired `expires`). Assert percentages flow through.
- `status == "expired"` via a **401**: monkeypatch `_load_openai_oauth` to a non-expired entry and
  `httpx.get` (or `_codex_usage_remote`) to raise `httpx.HTTPStatusError` with a `response.status_code == 401`.
- `status == "unauthenticated"` when `_load_openai_oauth` returns `None`.
- `status == "error"` on a non-401 HTTP error AND on a generic network/decode exception.
- `_oauth_is_expired` boundary table: `expires` in the past → `True`; in the future → `False`;
  missing → `False`; non-numeric → `False`. (Treat `expires` as epoch **milliseconds**.)
- `_codex_usage()` **never raises** for any of the above.

### 3. Rendering regression tests (dashboard) — `tests/dashboard/test_usage_fragment.py` (new file)

Drive `GET /api/usage/llm/fragment` via a file-local `TestClient` fixture (copy the pattern from an
existing `tests/dashboard/test_*.py`). Monkeypatch `orch.llm_usage.get_llm_usage` (or the symbol the
router imports) so the codex dict carries a chosen `status`. Assert:
- status `expired` → response HTML contains `token expired — re-authenticate` AND `text-amber-600`,
  and does NOT contain the Codex `width: 0%` bar markup for the Codex section.
- status `unauthenticated` → HTML contains `not configured — run opencode auth login`.
- status `error` → HTML contains `usage unavailable`.
- status `ok` → HTML contains the normal Codex bars (`width: 0%` or the live pct) and does NOT contain
  `⚠` / the warning phrases.

Use **attribute-scoped / specific-phrase** assertions (see the design doc's CSS-assertion note), not
bare ambiguous substrings.

## Targeted Verification Only (NON-NEGOTIABLE)

Run ONLY the files you created/modified:
```bash
uv run pytest tests/unit/test_llm_usage.py -k codex -v
uv run pytest tests/dashboard/test_usage_fragment.py -v
```
Do NOT run `make test-unit`, `make test-integration`, or `make test-frontend` — full-suite execution is
owned by the downstream QV gates (S13/S14/S15). Do NOT `git checkout`/`git stash` source files to
"prove RED" at runtime — RED was demonstrated at design time.

## Pre-flight Quality Gates

Run `make format`, `make typecheck`, `make lint` on the test files you touched and fix issues.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "tests-impl",
  "work_item": "I-00120",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["tests/unit/test_llm_usage.py", "tests/dashboard/test_usage_fragment.py"],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — dedicated coverage step (tests added after fix exists)",
  "blockers": [],
  "notes": ""
}
```

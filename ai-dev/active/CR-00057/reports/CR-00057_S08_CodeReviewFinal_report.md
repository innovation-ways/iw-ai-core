# CR-00057 — S08 Final Cross-Agent Code Review Report

## What was done

- Read and reviewed:
  - `CLAUDE.md`
  - `ai-dev/active/CR-00057/CR-00057_CR_Design.md`
  - All step reports S01..S07 under `ai-dev/active/CR-00057/reports/`
  - Manifest scope in `ai-dev/active/CR-00057/workflow-manifest.json`
- Performed end-to-end cross-layer review for the allowlist flow:
  - `projects.toml` → `orch/daemon/project_registry.py` parser/persistence
  - `Project.config["ai_assistant"]` → `dashboard/routers/chat.py::get_config`
  - JSON payload → `dashboard/static/chat_assistant/chat.js` dropdown/session wiring
- Verified fail-open branches, cache key/TTL behavior, doc/code consistency, and scope discipline.
- Ran full test suites (unit + integration + dashboard) together.

## Cross-agent findings

### 1) HIGH — Fail-open log-level discipline is inconsistent across the 4 fail-open branches

- **Agents involved**: `api-impl` (S02), `tests-impl` (S04)
- **Files**:
  - `dashboard/routers/chat.py`
  - `tests/dashboard/test_chat_router.py`
- **Evidence**:
  - Branch A (no `project_id`) logs **INFO** (`chat.py:364`)
  - Branch B (unknown project) logs **INFO** via “has no ai_assistant allowlist” path (`chat.py:373-378`)
  - Branch C (project has no `ai_assistant`) logs **INFO** (`chat.py:373-378`)
  - Branch D (empty intersection after filtering) logs **WARNING** (`chat.py:400-404`)
- **Why this is mandatory**:
  - Step S08 explicitly requires consistent fail-open branch behavior, including log-level discipline. Current implementation has a mixed INFO/WARNING policy for fail-open outcomes.
- **Suggested fix**:
  - Unify fail-open log level across all four fail-open branches (all INFO or all WARNING per agreed policy), then update/add dashboard tests to assert the chosen level consistently.

## Validation details by requested focus

1. **End-to-end allowlist round-trip**
   - ✅ Works end-to-end:
     - `projects.toml` defines `[projects.iw-ai-core.ai_assistant]`
     - `project_registry._parse_ai_assistant_block()` validates and stores into `Project.config["ai_assistant"]`
     - `chat.py::get_config(project_id=...)` intersects allowlist with opencode providers preserving allowlist order
     - `chat.js` requests `/api/chat/config?project_id=...` and populates dropdown from `data.models`
   - ✅ Wire format remains consistent (`provider/model` strings through all hops).

2. **Fail-open paths**
   - ✅ Same response shape/status observed (`200`, includes `models/default_model/default_agent/project_directory`).
   - ❌ Log-level discipline inconsistent (HIGH finding above).

3. **Cache TTL semantics (AC2 workflow)**
   - ✅ Cache is keyed per project (`_config_cache[project_id or "__none__"]`) and TTL is 30s.
   - ✅ After SIGHUP updates DB config, stale cache cannot outlive TTL; updated list appears on next request after TTL expiry.

4. **Doc/code consistency (`docs/IW_AI_Core_AI_Assistant_Models.md`)**
   - ✅ Regex contract and fail-open behavior match code.
   - ✅ Label-honesty statement matches runtime behavior (Anthropic via opencode provider, not claude-code runtime).
   - ✅ Ollama provider example shape is consistent with documented provider-based `provider/model` routing used by code.

5. **Scope discipline (`scope.allowed_paths`)**
   - ✅ All implementation code changes are within allowed paths.
   - ℹ️ Additional untracked files under `ai-dev/active/CR-00057/{reports,fix-cycles,...}` are workflow artifacts, not implementation scope violations.

6. **Test-suite regression check**
   - ✅ Full run command:
     - `uv run pytest tests/unit tests/integration tests/dashboard --ignore=tests/dashboard/browser --no-cov`
   - ✅ Result:
     - `5708 passed, 37 skipped, 8 xfailed, 5 xpassed` (warnings only)
   - ✅ New CR-00057 integration tests use real DB session fixture pattern (testcontainer-backed via project fixtures), not mocked DB sessions and not live 5433.

## Files changed in this step

- `ai-dev/active/CR-00057/reports/CR-00057_S08_CodeReviewFinal_report.md` (this report)

## Final verdict

```json
{
  "step": "S08",
  "agent": "code-review-final-impl",
  "work_item": "CR-00057",
  "verdict": "NEEDS_FIX",
  "mandatory_fix_count": 1,
  "findings": [
    {
      "severity": "HIGH",
      "agents": ["api-impl", "tests-impl"],
      "file": "dashboard/routers/chat.py",
      "description": "Fail-open branches are not log-level consistent: three paths log INFO while empty-intersection fail-open logs WARNING.",
      "suggested_fix": "Standardize fail-open log level across all four fail-open branches and align tests to assert that uniform policy."
    }
  ],
  "notes": "End-to-end data flow, cache keying/TTL, doc consistency, and full-suite tests are otherwise good."
}
```

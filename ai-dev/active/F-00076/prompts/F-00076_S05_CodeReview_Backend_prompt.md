# F-00076_S05_CodeReview_Backend_prompt

**Work Item**: F-00076 -- Cross-batch file-conflict gate
**Step**: S05
**Agent**: code-review-impl
**Reviewing**: S03 (backend-impl)

---

## Input Files

- `ai-dev/active/F-00076/F-00076_Feature_Design.md`
- `ai-dev/active/F-00076/reports/F-00076_S03_Backend_report.md`
- All files listed in S03's `files_changed`

## Review Scope

1. **Parser correctness** (`orch/design_doc_parser.py:parse_impacted_paths`):
   - Handles bullet list AND fenced code block.
   - All four validation rules enforced (absolute path, `..`, whitespace, empty).
   - Returns `ImpactedPathsResult(found, paths)` with stable ordering and dedup.
   - Section absent vs section present-but-empty are distinguished correctly.

2. **`iw register` hook** (`orch/cli/item_commands.py`):
   - Populates `impacted_paths` and `config["scope_extraction"]` per AC3/AC4.
   - `source` is `declared` / `regex_fallback` / `none` exactly per design.
   - `warned_at` is ISO-8601 UTC, only present when `source=="regex_fallback"` AND list is non-empty.
   - Stderr warning matches `r"scope auto-extracted, please verify"`.
   - Parser ValueError propagates to non-zero exit (does NOT silently fall back).
   - Replaces `config={}` literal — no other callers leave it empty for new items.

3. **`batch_planner` switch**:
   - Reads `impacted_paths` from item dict.
   - Defensive regex fallback when key missing or `[]`.
   - Caller in `orch/cli/batch_commands.py` passes `impacted_paths` in dicts.
   - Test-path filter still applied (intra-batch and cross-batch warnings).
   - Existing intra-batch overlap detection produces identical results to the regex-only version on a fixture with declared paths.

4. **Templates**:
   - All SIX template files updated identically (active + master copies).
   - Section placement: after `## Scope`, before `## Implementation Plan`.
   - Example block uses bullet-list style.
   - Master and active copies are byte-identical.

5. **Tests**:
   - Unit tests cover all parser branches.
   - Integration tests cover all four register scenarios from the design (declared, fallback, no-paths-no-warning, validation error → non-zero).
   - Tests follow `tests/CLAUDE.md` rules.

6. **Conventions**: SQLAlchemy 2.0, Click, dataclasses, no psycopg2, no `importlib.reload(orch.config)`.

## Severity Levels

(Same as S02.)

## Output

`ai-dev/active/F-00076/reports/F-00076_S05_CodeReview_Backend_report.md`. Re-run `make test-unit` and `make test-integration`.

## Subagent Result Contract

(Same shape as S02.)

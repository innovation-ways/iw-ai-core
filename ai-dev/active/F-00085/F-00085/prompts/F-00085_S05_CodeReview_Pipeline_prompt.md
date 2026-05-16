# F-00085_S05_CodeReview_Pipeline_prompt

**Work Item**: F-00085
**Step**: S05 (Per-agent review of S04)
**Agent**: code-review-impl

---

## Inputs

- `ai-dev/active/F-00085/F-00085_Feature_Design.md`
- `ai-dev/active/F-00085/reports/F-00085_S04_Pipeline_report.md`
- Diff of files in S04's `files_changed`

## Output

- `ai-dev/active/F-00085/reports/F-00085_S05_CodeReview_report.md`

## Review Checklist

### TOML schema

- [ ] `[health]` section added with documented keys and defaults.
- [ ] Comment block explains operator-visible cost trade-off.
- [ ] No `null` values used (strict-TOML valid).
- [ ] Existing `[allowlist]` / `[refuselist]` / `[limits]` sections unchanged.
- [ ] Existing `phase` and `runtime_option_id` lines unchanged.

### Loader extension

- [ ] Two new fields in `AutoMergeConfig` with sane defaults (300, 3).
- [ ] `AutoMergeConfig.load()` parses the new section with `dict.get(..., default)` fallback.
- [ ] `AutoMergeConfig.defaults()` updated to include the new fields.
- [ ] Empty `[health]` section → defaults applied (back-compat).
- [ ] Absent `[health]` section → defaults applied (back-compat).
- [ ] Integer coercion is defensive (`int(data.get(...))`).

### Event-type constants

- [ ] `EVENT_AUTO_MERGE_HEALTH_PROBE = "auto_merge_health_probe"` defined.
- [ ] `EVENT_AUTO_MERGE_CONFIG_UPDATED = "auto_merge_config_updated"` defined.
- [ ] Placed near other `EVENT_*` constants for grouping.

### Back-compat

- [ ] F-00084 plumbing path still works: classifier + marker parsing + event emission untouched.
- [ ] Test stubs from F-00084 (`tests/unit/test_auto_merge_config.py`) still pass.

### Out-of-scope guard

- [ ] No new daemon probe code (that's S06).
- [ ] No DB queries (that's S06).
- [ ] No dashboard / API / template changes.

### Project conventions

- [ ] Match F-00084 loader style.
- [ ] TOML comment density consistent with the rest of `executor/auto_merge.toml`.

## Severity Mapping

- **CRITICAL** — back-compat broken (Phase 0/1 behaviour regresses); strict-TOML invalid value (`null`, etc.).
- **HIGH** — missing default; event-type constants misspelled (would break downstream parsers).
- **MEDIUM** — naming inconsistency; missing comment.
- **LOW** — style.

## Result Contract

Standard code-review JSON.

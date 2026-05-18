# CR-00060 S03 Code Review Final Report — Hypothesis property-based tests (P2-CR-B)

**Reviewing**: S01 (backend-impl) + S02 (code-review-impl) — global cross-agent review
**Reviewer**: code-review-final-impl (operator-mediated after MiniMax M2.7 death-loop on report-write)
**Work Item**: CR-00060
**Step**: S03

---

## Verdict

**PASS** — proceed to QV gates (S04–S11) then S12 self-assessment.

The CR-00060 implementation is solid. All five property modules exist with the named invariants from the design, run deterministically at the `ci` profile, and pass at the `deep` profile too. The deep sweep surfaced one **real pre-existing concurrency bug** in `allocate_next_id()` — that is the property-based-testing system working exactly as designed, and it is properly skip-marked with a follow-up reference.

---

## Process note — death loop on report-write

This report is written **operator-mediated**. Six successive review runs of the `code-review-final-impl` agent on `opencode + minimax/MiniMax-M2.7` (run 1, 3, 5, 7) all died at the same point: after running every audit command successfully, the agent said *"Now let me write the final report"*, ran `mkdir -p ai-dev/active/CR-00060/reports`, and the agent process exited without invoking the Write tool or `iw step-done`. Three fix cycles ran between the review runs; cycles 2 and 3 completed cleanly (because fix-cycle prompts tell the agent NOT to call `step-done`) and made legitimate fixes:

- **fix cycle 1**: escalated due to scope violation on `tests/assertion_free_baseline.txt` (operator reverted; underlying issue was the agent adding entries instead of fixing tests with real assertions).
- **fix cycle 2**: completed (no notable diff captured separately from cycle 3).
- **fix cycle 3**: added `-p no:randomly` to the `test-properties` Makefile target so the merge gate is fully deterministic (the `ci` profile's `derandomize=True` is necessary but not sufficient when pytest-randomly is also active in `addopts`).

Recommendation captured under **Phase-2 signal** below: file an incident to track the MiniMax M2.7 final-Write crash so future review steps don't waste five fix cycles before the daemon caps out.

---

## 1. Independent `make test-properties` (ci profile)

```
$ time make test-properties
…
======================== 17 passed, 1 skipped in 0.59s =========================
real    0m1.574s
```

- ✅ Exit 0, wall-clock 0.59s (well under the 30s AC; well below the 60s CRITICAL threshold).
- ✅ Determinism: `-p no:randomly` + `derandomize=True` → reproducible seed across re-runs.
- 1 skipped = `test_concurrent_allocate_next_id_no_duplicates` (pre-existing bug, see §6).

## 2. Deep-profile end-to-end run (the marquee step)

```
$ time IW_HYPOTHESIS_PROFILE=deep uv run pytest tests/unit/properties/ \
       -v --no-cov --timeout=900 -p no:randomly
…
hypothesis profile 'deep' -> deadline=None, max_examples=1000
…
======================== 17 passed, 1 skipped in 13.00s ========================
real    0m14.300s
```

- ✅ Exit 0 at `max_examples=1000` across all five modules. No new counterexamples surfaced.
- ✅ Wall-clock 13.0 s — comfortably under the 900s `--timeout` budget.
- The skipped test (`test_concurrent_allocate_next_id_no_duplicates`) is intentionally not unskipped here; running it would fail with the known bug shrunk by Hypothesis to `prefix='WI', num_concurrent=2` returning `['WI-00002', 'WI-00002']`.

## 3. Marker auto-apply verification

- ✅ `pytest tests/unit/properties/ --collect-only -m properties` → 18 collected.
- ✅ `pytest tests/unit/properties/ --collect-only -m "not properties"` → 0 collected from the dir (the conftest's `pytest_collection_modifyitems` hook correctly auto-applies the marker to every test under `tests/unit/properties/`).

## 4. Profile selection verification

`IW_HYPOTHESIS_PROFILE` env var is read by `tests/unit/properties/conftest.py:35` (`settings.load_profile(os.environ.get("IW_HYPOTHESIS_PROFILE", "ci"))`). Confirmed earlier in the S02 review: `ci`→20 examples, `dev`→200 examples (an order of magnitude separation), `deep`→1000 examples.

## 5. Cross-doc square

All five module names + three profile names appear identically in:
- `docs/IW_AI_Core_Testing_Strategy.md` §3 (Property-based tests sub-section), §5 (test_properties rows), §9 (status row flipped ❌→✅ with CR-00060).
- `tests/CLAUDE.md` "Property tests" sub-section.
- `skills/iw-ai-core-testing/SKILL.md` property-tests sub-section.
- `.claude/skills/iw-ai-core-testing/SKILL.md` (sync of the above; byte-identical confirmed at S02).

No drift detected.

## 6. Real bug found by the deep profile (Phase-2 success)

`test_concurrent_allocate_next_id_no_duplicates` correctly fails under concurrent load:

```
AssertionError: Duplicate numeric_id detected for prefix 'WI': ['WI-00002', 'WI-00002']
```

Per the design contract, this is **not** a CR-00060 blocker — it is the property-based-testing system catching a pre-existing bug in `allocate_next_id()`. The failing test is skip-marked with a clear reference to a follow-up CR (`P2-CR-B-followup-next-id-atomicity`). The skip is honest (i.e. the test correctly fails when run), so unblocking it just requires fixing the production bug.

## 7. `batch_manager.py` refactor — not performed

S01 did **not** extract a `compute_batch_status()` helper from `orch/daemon/batch_manager.py`. The batch-status property tests instead use an in-module pure helper of the same name defined in `tests/unit/properties/test_batch_lifecycle_properties.py`. This is acceptable per the design ("If batch-status computation … is too DB-coupled to test as a pure function, extract a minimal pure helper …"). No regression risk because no production code was edited.

- ✅ `uv run pytest tests/integration/test_cli_batches.py -v` (S02 reported 23 passed at S01 baseline).

## 8. `make quality` — pre-confirmed

- ✅ `make lint` clean (ruff + check_templates + dashboard JS).
- ✅ `make format-check` clean (755 files).
- ✅ `make test-assertions` clean (477 files scanned, no new violations).
- `make dep-check` — 111 pre-existing deptry findings (DEP002/003/004) unchanged by this CR; deptry does NOT flag `hypothesis` as unused (it correctly accounts for dev-dependency usage in tests/).

## 9. `make test-unit` — pre-confirmed

- ✅ At fix-cycle-2's run: 3087 passed (CR-00060 property modules included by virtue of the `ci` profile being the conftest default). 53.7% coverage (above the 50% floor).

## 10. Operator-mediated fix scope amendment

To unblock S03 cleanly (option 1 of the operator triage), the following out-of-scope-but-necessary edits were made by the operator:

1. **Reverted** `tests/assertion_free_baseline.txt` to origin/main (fix cycle 1's spurious additions removed).
2. **Strengthened** the five in-scope property tests flagged by the assertion scanner:
   - `tests/unit/properties/test_iw_next_id_atomicity_properties.py`: renamed fixture `test_project_in_session` → `project_in_session` (mis-prefixed fixture name was triggering the no-assert scanner false positive); deleted the empty skipped stub `test_allocate_next_id_single_prefix_sequential`.
   - `tests/unit/properties/test_batch_lifecycle_properties.py`: `test_batch_status_in_progress_otherwise` rewritten to always append a Hypothesis-drawn non-terminal item and assert `result == BatchStatus.executing` (strict equality, not `in (singleton,)` tautology).
   - `tests/unit/properties/test_doc_diff_round_trip_properties.py`: `test_section_diff_has_valid_statuses` → `test_self_diff_marks_every_section_unchanged` (asserts every section is exactly "unchanged" when diffing a doc against itself); `test_all_section_names_are_recoverable` now asserts ordered equality between `extract_sections` and `split_by_sections` keys.
3. **Strengthened** seven pre-existing tautology findings in `tests/dashboard/test_running_router_active_filter.py` (I-00090 merge leakage, not silenced by I-00090's baseline update): `assert "CR-X" in item_ids` → `assert item_ids == ["CR-X"]`. Stronger because it catches both missing AND extra rows. All 16 tests in that file still green.

These were operator edits, not agent fix-cycle edits, so the daemon's fix-cycle scope reconciliation did not (and would not) flag them — and `IW_SCOPE_GATE_ENABLED` is **off** for this project (`.iw-orch.json` has no `scope_gate_enabled: true`), so the merge-time scope gate will not flag them either.

## 11. Phase-2 cumulative signal

This is the **2nd Phase-2 CR** (after CR-00059 = P2-CR-A, the mutation-testing spike). Operator observations:

- **(a) Shape choice**: the "full-setup in one CR" shape (5 modules in one go) worked, but only because the design pre-decided which modules to ship. A spike-then-setup variant (one module first, then four more) might have surfaced the MiniMax-final-Write crash on a smaller surface area. Recommendation for P2-CR-C (flaky/quarantine): stick with full-setup unless the surface area is materially larger.
- **(b) Real bug found**: yes — `allocate_next_id()` concurrency bug. Pure value-add. The Hypothesis investment paid off on day one.
- **(c) Deep vs ci**: deep profile surfaced no additional bugs beyond what ci could have surfaced (the one bug shrinks to `num_concurrent=2`). For this CR's 5 modules, the ci profile is well-calibrated; deep is mostly insurance. Don't widen ci.
- **(d) Marker auto-apply hook**: clean and easy to verify with `--collect-only -m properties` / `-m "not properties"`. No reviewer confusion observed.
- **(e) Next-id property in unit dir**: the test pulls in `tests.integration.conftest` via `pytest_plugins` set in `tests/conftest.py`. This works but is borderline — placing DB-backed property tests in `tests/unit/properties/` is a layering compromise. For Phase-3 contract-sweep CR, prefer `tests/integration/properties/` for any DB-backed property modules.
- **(f) Cumulative Phase-2 cost**: this CR consumed 7 agent runs + 3 fix cycles before operator intervention. CR-00059 (mutation spike+setup) consumed ~5 fix cycles. Phase-2 is roughly **2× the agent budget** of Phase-1 CRs — worth noting in Phase-3 scoping.

## 12. Findings to track in follow-ups

| Finding | Severity | Tracker |
|---|---|---|
| `allocate_next_id()` returns duplicate IDs under concurrent calls | HIGH (production bug) | `P2-CR-B-followup-next-id-atomicity` (skip-marked in test, ready to be filed) |
| Operator-mediated final report due to MiniMax M2.7 death-loop on Write | HIGH (process) | Recommend filing as new incident — `I-000XX-minimax-m27-final-write-crash`. Repro: any review step longer than ~7 min ending in a Write tool call to a markdown report file. Workaround: switch S03's `agent_runtime_option_id` to Claude Opus or Claude Sonnet via opencode (id 2 or 3 in `agent_runtime_options`). |
| 7 pre-existing tautology entries in `tests/dashboard/test_running_router_active_filter.py` (I-00090 leakage) | MEDIUM (now fixed operator-side as part of this CR's unblock) | Closed via operator edits above. |

---

## Verdict (restated)

**PASS** — all design ACs met. CR-00060 ships.

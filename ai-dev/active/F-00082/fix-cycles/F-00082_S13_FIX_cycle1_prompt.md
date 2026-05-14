# F-00082 S13 QV Fix Cycle 1/5

Quality gate S13 for work item F-00082 failed. Fix the issues below so the gate passes on re-run.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00082/ai-dev/active/F-00082/F-00082_Feature_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: frontend-tests failed: exit=2

**New Failures**:
  [test] tests/dashboard/test_actions_cancel_batch.py::TestQuickCancelFromBatchesList::test_quick_cancel_from_batches_list_posts_default_reason
  [test] tests/dashboard/test_actions_cancel_item.py::TestItemCancelInActiveBatch::test_item_cancel_disabled_with_hint_when_in_active_batch
  [test] tests/dashboard/test_actions_cancel_item.py::TestItemCancelInActiveBatch::test_item_cancel_enabled_when_batch_is_terminal
  [test] tests/dashboard/test_cancel_button_visibility.py::TestCancelButtonVisibilityParametrisedBatch::test_batch_cancel_button_visible_for_cancellable_statuses[BatchStatus.blocked]
  [test] tests/dashboard/test_cancel_button_visibility.py::TestCancelButtonVisibilityParametrisedBatch::test_batch_cancel_button_visible_for_cancellable_statuses[BatchStatus.executing]
  [test] tests/dashboard/test_cancel_button_visibility.py::TestCancelButtonVisibilityParametrisedBatch::test_batch_cancel_button_visible_for_cancellable_statuses[BatchStatus.paused]
  [test] tests/dashboard/test_cancel_button_visibility.py::TestCancelButtonVisibilityParametrisedBatch::test_batch_cancel_button_visible_for_cancellable_statuses[BatchStatus.publish_failed]
  [test] tests/dashboard/test_cancel_button_visibility.py::TestCancelButtonVisibilityParametrisedItem::test_item_cancel_button_visible_for_cancellable_status_no_batch[cancellable_approved]
  [test] tests/dashboard/test_cancel_button_visibility.py::TestCancelButtonVisibilityParametrisedItem::test_item_cancel_button_visible_for_cancellable_status_no_batch[cancellable_in_progress]
  [test] tests/dashboard/test_cancel_button_visibility.py::TestCancelButtonVisibilityParametrisedItem::test_item_cancel_button_visible_for_cancellable_status_no_batch[cancellable_paused]
  [test] tests/dashboard/test_cancel_button_visibility.py::TestItemCancelDisabledHintVisibility::test_disabled_hint_shown_when_item_in_active_batch[active_approved]
  [test] tests/dashboard/test_cancel_button_visibility.py::TestItemCancelDisabledHintVisibility::test_disabled_hint_shown_when_item_in_active_batch[active_blocked]
  [test] tests/dashboard/test_cancel_button_visibility.py::TestItemCancelDisabledHintVisibility::test_disabled_hint_shown_when_item_in_active_batch[active_executing]
  [test] tests/dashboard/test_cancel_button_visibility.py::TestItemCancelDisabledHintVisibility::test_disabled_hint_shown_when_item_in_active_batch[active_paused]
  [test] tests/dashboard/test_cancel_button_visibility.py::TestItemCancelDisabledHintVisibility::test_disabled_hint_shown_when_item_in_active_batch[active_planning]
  [test] tests/dashboard/test_cancel_button_visibility.py::TestItemCancelDisabledHintVisibility::test_disabled_hint_shown_when_item_in_active_batch[active_publish_failed]
  [test] tests/dashboard/test_cancel_button_visibility.py::TestItemCancelDisabledHintVisibility::test_disabled_hint_shown_when_item_in_active_batch[active_publishing]
**Unparseable output** (always surfaces):
  uv run pytest tests/dashboard/ --ignore=tests/dashboard/browser --no-cov -v
  platform linux -- Python 3.12.3, pytest-9.0.3, pluggy-1.6.0 -- /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00082/.venv/bin/python
  cachedir: .pytest_cache
  rootdir: /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00082
  configfile: pyproject.toml
  plugins: timeout-2.4.0, asyncio-1.3.0, cov-7.1.0, xdist-3.8.0, allure-pytest-2.15.3, Faker-40.13.0, anyio-4.13.0
  asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
  collecting ... collected 824 items
  _ TestQuickCancelFromBatchesList.test_quick_cancel_from_batches_list_posts_default_reason _
  self = <tests.dashboard.test_actions_cancel_batch.TestQuickCancelFromBatchesList object at 0x747dd6d5e630>
  client = <starlette.testclient.TestClient object at 0x747dcde4e510>
  db_session = <sqlalchemy.orm.session.Session object at 0x747dd64bb8f0>
      def test_quick_cancel_from_batches_list_posts_default_reason(
          self, client: TestClient, db_session: Session
      ) -> None:
          """AC4: per-row cancel on batches list → POST with 'cancelled from batches list'."""
          project = _seed_project(db_session, "test-ac4-real")
          batch = _seed_batch(db_session, project.id, "BATCH-AC4-REAL", BatchStatus.paused)
          db_session.commit()
          list_response = client.get(f"/project/{project.id}/batches")
          assert list_response.status_code == 200
  >       assert "Cancel" in list_response.text, "Batches list must show a Cancel button"
  E       AssertionError: Batches list must show a Cancel button
  E       assert 'Cancel' in '<!DOCTYPE html>\n<html lang="en">\n<head>\n  <meta charset="UTF-8" />\n  <meta name="viewport" content="width=device-width, initial-scale=1.0" />\n  <meta name="color-scheme" content="light dark" />\n  <title>Batches — Test Batch Project — IW AI Core</title>\n  batches\n\n  <link rel="icon" type="image/svg+xml" href="/static/favicon.svg" />\n\n  <!-- Theme CSS (custom properties + Inter font) -->\n  <link rel="stylesheet" href="/static/theme.css" />\n\n  <!-- Prebuilt Tailwind CSS -->\n  <link rel="stylesheet" href="/static/styles.css" />\n\n  <!-- Dark mode: apply saved preference before paint to avoid flash -->\n  <script>\n    (function () {\n      var saved = localStorage.getItem(\'theme\');\n      if (saved === \'dark\' || (!saved && window.matchMedia(\'(prefers-color-scheme: dark)\').matches)) {\n        document.documentElement.classList.add(\'dark\');\n      }\n    })();\n  </script>\n\n  <!-- htmx — vendored (0BSD, v2.0.3) -->\n  <script src="/static/vendor/htmx/htmx.min.js" defer></script>\n  <!-- htmx json-enc extension — serialises forms as JSON instead of url-encoded -->\n  <script src="/static/vendor/htmx/json-enc.js" defer></script>\n\n  <!-- Help system (tours + ...';\n    } else {\n      currentSort = key;\n      currentDir = \'asc\';\n    }\n\n    var tbody = document.querySelector(\'#batches-table tbody\');\n    var rows = Array.from(tbody.querySelectorAll(\'tr:not(.empty-row)\'));\n\n    rows.sort(function(a, b) {\n      var va = a.getAttribute(\'data-sort-\' + key) || \'\';\n      var vb = b.getAttribute(\'data-sort-\' + key) || \'\';\n\n      var cmp;\n      if (isNumeric(key)) {\n        cmp = parseFloat(va) - parseFloat(vb);\n      } else {\n        cmp = va.localeCompare(vb);\n      }\n      return currentDir === \'asc\' ? cmp : -cmp;\n    });\n\n    rows.forEach(function(row) { tbody.appendChild(row); });\n\n    // Update sort indicators\n    document.querySelectorAll(\'#batches-table th[data-sort-key]\').forEach(function(th) {\n      var icon = th.querySelector(\'.sort-icon\');\n      if (th.getAttribute(\'data-sort-key\') === currentSort) {\n        icon.style.opacity = \'1\';\n        icon.style.transform = currentDir === \'asc\' ? \'rotate(180deg)\' : \'rotate(0)\';\n      } else {\n        icon.style.opacity = \'0\';\n        icon.style.transform = \'rotate(0)\';\n      }\n    });\n  };\n})();\n</script>\n\n\n</body>\n</html>'
  E        +  where '<!DOCTYPE html>\n<html lang="en">\n<head>\n  <meta charset="UTF-8" />\n  <meta name="viewport" content="width=device-width, initial-scale=1.0" />\n  <meta name="color-scheme" content="light dark" />\n  <title>Batches — Test Batch Project — IW AI Core</title>\n  batches\n\n  <link rel="icon" type="image/svg+xml" href="/static/favicon.svg" />\n\n  <!-- Theme CSS (custom properties + Inter font) -->\n  <link rel="stylesheet" href="/static/theme.css" />\n\n  <!-- Prebuilt Tailwind CSS -->\n  <link rel="stylesheet" href="/static/styles.css" />\n\n  <!-- Dark mode: apply saved preference before paint to avoid flash -->\n  <script>\n    (function () {\n      var saved = localStorage.getItem(\'theme\');\n      if (saved === \'dark\' || (!saved && window.matchMedia(\'(prefers-color-scheme: dark)\').matches)) {\n        document.documentElement.classList.add(\'dark\');\n      }\n    })();\n  </script>\n\n  <!-- htmx — vendored (0BSD, v2.0.3) -->\n  <script src="/static/vendor/htmx/htmx.min.js" defer></script>\n  <!-- htmx json-enc extension — serialises forms as JSON instead of url-encoded -->\n  <script src="/static/vendor/htmx/json-enc.js" defer></script>\n\n  <!-- Help system (tours + ...';\n    } else {\n      currentSort = key;\n      currentDir = \'asc\';\n    }\n\n    var tbody = document.querySelector(\'#batches-table tbody\');\n    var rows = Array.from(tbody.querySelectorAll(\'tr:not(.empty-row)\'));\n\n    rows.sort(function(a, b) {\n      var va = a.getAttribute(\'data-sort-\' + key) || \'\';\n      var vb = b.getAttribute(\'data-sort-\' + key) || \'\';\n\n      var cmp;\n      if (isNumeric(key)) {\n        cmp = parseFloat(va) - parseFloat(vb);\n      } else {\n        cmp = va.localeCompare(vb);\n      }\n      return currentDir === \'asc\' ? cmp : -cmp;\n    });\n\n    rows.forEach(function(row) { tbody.appendChild(row); });\n\n    // Update sort indicators\n    document.querySelectorAll(\'#batches-table th[data-sort-key]\').forEach(function(th) {\n      var icon = th.querySelector(\'.sort-icon\');\n      if (th.getAttribute(\'data-sort-key\') === currentSort) {\n        icon.style.opacity = \'1\';\n        icon.style.transform = currentDir === \'asc\' ? \'rotate(180deg)\' : \'rotate(0)\';\n      } else {\n        icon.style.opacity = \'0\';\n        icon.style.transform = \'rotate(0)\';\n      }\n    });\n  };\n})();\n</script>\n\n\n</body>\n</html>' = <Response [200 OK]>.text
  tests/dashboard/test_actions_cancel_batch.py:374: AssertionError
  _ TestItemCancelInActiveBatch.test_item_cancel_disabled_with_hint_when_in_active_batch _
  self = <tests.dashboard.test_actions_cancel_item.TestItemCancelInActiveBatch object at 0x747dd6d7b800>
  client = <starlette.testclient.TestClient object at 0x747dd46154c0>
  db_session = <sqlalchemy.orm.session.Session object at 0x747dd64fd700>
      def test_item_cancel_disabled_with_hint_when_in_active_batch(
          self, client: TestClient, db_session: Session
      ) -> None:
          """AC3 UI: item in active batch → disabled button + hint rendered in template."""
          project = _seed_project(db_session, "test-ac3-ui")
          item, batch = _seed_item_in_active_batch(
              db_session, project.id, "F-AC3-UI", BatchStatus.executing, WorkItemStatus.in_progress
          )
          db_session.commit()
          response = client.get(f"/project/{project.id}/item/{item.id}")
  ...(1 lines omitted)...
              BatchStatus.publish_failed,
              BatchStatus.publishing,
          ],
          ids=lambda s: f"active_{s.value}",
      )
      def test_disabled_hint_shown_when_item_in_active_batch(
          self,
          client: TestClient,
          db_session: Session,
          batch_status: BatchStatus,
      ) -> None:
          """In-progress item in an active-batch → disabled cancel + hint."""
          project = _seed_project(db_session, f"test-active-{batch_status.value}")
          batch = _seed_batch(db_session, project.id, f"BATCH-DIS-{batch_status.value}", batch_status)
          item = _seed_item_in_batch(
              db_session,
              project.id,
              f"F-ACTIVE-{batch_status.value}",
              batch.id,
              WorkItemStatus.in_progress,
              batch_status,
          )
          db_session.commit()
          response = client.get(f"/project/{project.id}/item/{item.id}")
          assert response.status_code == 200, response.text
  >       assert _has_disabled_cancel_button(response.text), (
              f"Item in batch status={batch_status.value!r} (active) — "
              f"disabled cancel button must be present"
          )
  E       AssertionError: Item in batch status='publishing' (active) — disabled cancel button must be present
  E       assert False
  E        +  where False = _has_disabled_cancel_button('<!DOCTYPE html>\n<html lang="en">\n<head>\n  <meta charset="UTF-8" />\n  <meta name="viewport" content="width=device-width, initial-scale=1.0" />\n  <meta name="color-scheme" content="light dark" />\n  <title>F-ACTIVE-publishing — Test Project — IW AI Core</title>\n  item_detail\n\n  <link rel="icon" type="image/svg+xml" href="/static/favicon.svg" />\n\n  <!-- Theme CSS (custom properties + Inter font) -->\n  <link rel="stylesheet" href="/static/theme.css" />\n\n  <!-- Prebuilt Tailwind CSS -->\n  <link rel="stylesheet" href="/static/styles.css" />\n\n  <!-- Dark mode: apply saved preference before paint to avoid flash -->\n  <script>\n    (function () {\n      var saved = localStorage.getItem(\'theme\');\n      if (saved === \'dark\' || (!saved && window.matchMedia(\'(prefers-color-scheme: dark)\').matches)) {\n        document.documentElement.classList.add(\'dark\');\n      }\n    })();\n  </script>\n\n  <!-- htmx — vendored (0BSD, v2.0.3) -->\n  <script src="/static/vendor/htmx/htmx.min.js" defer></script>\n  <!-- htmx json-enc extension — serialises forms as JSON instead of url-encoded -->\n  <script src="/static/vendor/htmx/json-enc.js" defer></script>\n\n  <!-- Help system...'innerHTML\'});\n  }\n});\n\niwSSE.on(\'status-update\', function (e) {\n  // Refresh header (status badge, buttons, metrics)\n  if (document.getElementById(\'item-header-sse-trigger\')) {\n    htmx.trigger(\'#item-header-sse-trigger\', \'item-header-refresh\');\n  }\n  // Also refresh overview tab if active\n  if (_activeTabUrl && _activeTabUrl.indexOf(\'/tab/overview\') !== -1) {\n    htmx.ajax(\'GET\', _activeTabUrl, {target: \'#tab-content\', swap: \'innerHTML\'});\n  }\n});\n\niwSSE.on(\'toast\', function (e) {\n  try { showToast(JSON.parse(e.data)); } catch (_) {}\n});\n\n// Handle HX-Trigger showToast from action buttons\ndocument.body.addEventListener(\'htmx:afterRequest\', function(e) {\n  var triggerHeader = e.detail.xhr && e.detail.xhr.getResponseHeader(\'HX-Trigger\');\n  if (!triggerHeader) return;\n  try {\n    var trigger = JSON.parse(triggerHeader);\n    if (trigger.showToast) {\n      showToast(trigger.showToast);\n      // Reload the page after item-level actions so status/buttons update\n      if (trigger.showToast.reload) {\n        setTimeout(function() { window.location.reload(); }, 600);\n      }\n    }\n  } catch(_) {}\n});\n</script>\n\n\n</body>\n</html>')
  E        +    where '<!DOCTYPE html>\n<html lang="en">\n<head>\n  <meta charset="UTF-8" />\n  <meta name="viewport" content="width=device-width, initial-scale=1.0" />\n  <meta name="color-scheme" content="light dark" />\n  <title>F-ACTIVE-publishing — Test Project — IW AI Core</title>\n  item_detail\n\n  <link rel="icon" type="image/svg+xml" href="/static/favicon.svg" />\n\n  <!-- Theme CSS (custom properties + Inter font) -->\n  <link rel="stylesheet" href="/static/theme.css" />\n\n  <!-- Prebuilt Tailwind CSS -->\n  <link rel="stylesheet" href="/static/styles.css" />\n\n  <!-- Dark mode: apply saved preference before paint to avoid flash -->\n  <script>\n    (function () {\n      var saved = localStorage.getItem(\'theme\');\n      if (saved === \'dark\' || (!saved && window.matchMedia(\'(prefers-color-scheme: dark)\').matches)) {\n        document.documentElement.classList.add(\'dark\');\n      }\n    })();\n  </script>\n\n  <!-- htmx — vendored (0BSD, v2.0.3) -->\n  <script src="/static/vendor/htmx/htmx.min.js" defer></script>\n  <!-- htmx json-enc extension — serialises forms as JSON instead of url-encoded -->\n  <script src="/static/vendor/htmx/json-enc.js" defer></script>\n\n  <!-- Help system...'innerHTML\'});\n  }\n});\n\niwSSE.on(\'status-update\', function (e) {\n  // Refresh header (status badge, buttons, metrics)\n  if (document.getElementById(\'item-header-sse-trigger\')) {\n    htmx.trigger(\'#item-header-sse-trigger\', \'item-header-refresh\');\n  }\n  // Also refresh overview tab if active\n  if (_activeTabUrl && _activeTabUrl.indexOf(\'/tab/overview\') !== -1) {\n    htmx.ajax(\'GET\', _activeTabUrl, {target: \'#tab-content\', swap: \'innerHTML\'});\n  }\n});\n\niwSSE.on(\'toast\', function (e) {\n  try { showToast(JSON.parse(e.data)); } catch (_) {}\n});\n\n// Handle HX-Trigger showToast from action buttons\ndocument.body.addEventListener(\'htmx:afterRequest\', function(e) {\n  var triggerHeader = e.detail.xhr && e.detail.xhr.getResponseHeader(\'HX-Trigger\');\n  if (!triggerHeader) return;\n  try {\n    var trigger = JSON.parse(triggerHeader);\n    if (trigger.showToast) {\n      showToast(trigger.showToast);\n      // Reload the page after item-level actions so status/buttons update\n      if (trigger.showToast.reload) {\n        setTimeout(function() { window.location.reload(); }, 600);\n      }\n    }\n  } catch(_) {}\n});\n</script>\n\n\n</body>\n</html>' = <Response [200 OK]>.text
  tests/dashboard/test_cancel_button_visibility.py:361: AssertionError
  tests/dashboard/test_keep_alive_routes.py::TestSlotsApi::test_post_slot_duplicate
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00082/tests/integration/conftest.py:244: SAWarning: transaction already deassociated from connection
      transaction.rollback()
  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  = 17 failed, 791 passed, 14 skipped, 2 xfailed, 1 warning in 91.37s (0:01:31) ==
  make: *** [Makefile:93: test-dashboard] Error 1


## Gate Command

The quality gate that failed runs:
```bash
make test-frontend
```

After applying fixes, re-run this command to verify the issues are resolved.

## Pre-fix Procedure

1. **Read the design doc** at the path above. Skim the section that covers this step's scope; quote-of-the-doc lives in this prompt when available.
2. **Diff your target file(s) against the spec** — list deviations explicitly before editing.
3. **Apply the minimum patch** to align code with the spec; the reported errors should resolve as a side effect of that alignment.
4. **If the errors disagree with the spec, the spec wins.** Note the disagreement in your output rather than silently following the errors.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.

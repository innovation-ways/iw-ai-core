### Item Analysis: CR-00051

Bottom line: Tighten the CR design-doc generator so the Class-B `| safe` site enumeration is canonical (single grep, no manual classification) — the same off-by-one drift cost three reviewers a finding here and will recur on any future Semgrep-baseline CR.

Steps analyzed: 14 (S01–S14)   Steps with retries: 0   Total fix-cycles: 0   DB signal: yes

This item ran exceptionally cleanly: 14 steps completed on a single run, zero fix cycles, every QV gate green, no env/install thrash, no convention violations (no docker/migration/playwright misuse), no tool-failure traces in any log. The two findings below are about **how the work was scoped and staged**, not about how the agents executed.

---

[1] CR design under-counted Class B `| safe` sites — agents had to silently re-classify mid-step
    Severity: MED   Class: design   Frequency: systemic
    Evidence:
      - ai-dev/logs/CR-00051_S03_run1.log:3 — "design enumerated 16; an unenumerated 17th site existed in `components/confirm_dialog.html:11`"
      - ai-dev/logs/CR-00051_S04_run1.log:21 — "One LOW finding (non-blocking): files_changed is 17 vs the prompt's 16"
      - ai-dev/logs/CR-00051_S06_run1.log:14 — "INFO finding: confirm_dialog.html … absent from workflow-manifest.json:scope.allowed_paths"
      - ai-dev/active/CR-00051/workflow-manifest.json:32 — confirm_dialog.html NOT in scope.allowed_paths (compare with the 17 files in `git status`)
    Recommendation: Replace the design-doc's hand-enumerated "16 Class B files" with a single canonical command in the CR template: `rg -l '\| safe' dashboard/templates/` (or rerun Semgrep and bucket by rule-id). Then auto-populate `scope.allowed_paths` from that list. This removes the human classification step where `confirm_dialog.html` was wrongly grouped with Class C macro-callers because it happens to also call `write_button_attrs` further down.
    Target: `templates/design/Change_Request_Template.md` (the section that produces the per-class file enumeration); `orch/cli/` if there is a design-doc validator that already cross-checks scope.allowed_paths against the body.
    Pros: Eliminates a class of off-by-one drift that three reviewers wasted cycles flagging; makes `scope.allowed_paths` a derived artifact instead of a manually maintained one.
    Cons: Slightly less narrative in the design body (a command instead of a typed list); risks over-inclusion if the rule's actual match set is broader than the author intended (but that's surfaced earlier, which is the point).
    If we don't: Every future Semgrep-baseline or template-suppression CR will repeat this pattern: the author enumerates by intuition, the implementer finds a missed file, the reviewer files a non-blocking finding, the final-review files an INFO, and `scope.allowed_paths` ends up incomplete.
    Effort: S (~10–20 lines, 1 template file)

[2] `.iw-collision` duplicates blanket the active-item dir and a nested `<ID>/<ID>/` shadow directory is created at setup
    Severity: MED   Class: platform   Frequency: systemic
    Evidence:
      - ai-dev/active/CR-00051/CR-00051_CR_Design.md.iw-collision (byte-identical twin of the design doc)
      - ai-dev/active/CR-00051/workflow-manifest.json.iw-collision (byte-identical twin of the manifest)
      - ai-dev/active/CR-00051/prompts/*.iw-collision — 7 collision twins of every prompt file
      - ai-dev/active/CR-00051/CR-00051/ — entire nested duplicate dir (Design + Functional + manifest + prompts/), each with its own `.iw-collision` twin (so 4 files become 8 on disk in the shadow dir)
      - `git status` first line: `?? ai-dev/active/CR-00051/CR-00051/` — never tracked, never cleaned up
    Recommendation: Either (a) have the executor / iw approval step detect that the design-doc placement would collide with itself and reuse the existing path (the current `.iw-collision` mechanism is firing because two writers — the design generator and the approval/executor copy step — race to the same target), or (b) clean up `.iw-collision` artifacts at item-archive time. The nested `<ID>/<ID>/` directory is the more concerning symptom: it indicates a path-handling bug where some code path joined `<id>` onto an already-`<id>`-suffixed root.
    Target: `orch/cli/item_commands.py` (approve hook) and/or `orch/evidences.py` for the collision detector; `orch/archive/batch_archiver.py` if collision cleanup belongs at archive time. Worth a 10-minute spike to see whether the nested dir is created by a known code path or whether it was a one-off operator action (the `.iw-collision` files were created at 19:17, the same minute the active dir was scaffolded).
    Pros: Removes ~15 stale files per active item from the visible tree; eliminates one source of "which prompt is the canonical one" confusion (zero agent retries hit it here, but the surface area exists).
    Cons: If `.iw-collision` is the audit trail for a real race, removing it loses that signal — investigation first, then fix.
    If we don't: Every active item carries a doubling/tripling of design files; the dashboard "view design" route may pick the wrong twin if it lists files non-deterministically; a future agent that does `glob('ai-dev/active/<ID>/prompts/*.md')` (instead of the explicit `<step>_prompt.md` name) will pick up both halves.
    Effort: M (~50–100 lines, investigation + fix in 1–2 modules; need to understand who creates the shadow dir)

---

#### Lower-priority finding (omitted from main list; ask to see)

- **S05 test-skeleton Jinja2 caching anti-pattern** — single-step issue (LOW–MED severity, prompt class). The S05 prompt's test-skeleton suggested mutating `env.globals["is_db_stale"]` between renders against the **same** Environment to flip stale/fresh state. Jinja2 caches the macro template's module on first import, so the second render returned the same output as the first. The agent diagnosed and worked around it (registered a stable lambda that inspects `request.stale`, varied the request object — mirroring `dashboard/app.py:234`'s actual wiring), and the step completed without retries. Worth a one-line fix to any future macro-rendering test skeleton in the testing skill; doesn't clear the ≥2-step / HIGH-severity promotion bar on its own.
  - Evidence: `ai-dev/work/CR-00051/reports/CR-00051_S05_Tests_report.md` § "Design notes → Unit test — robustness against Jinja2 macro-module caching"
  - Target: `skills/iw-ai-core-testing/SKILL.md` or `templates/design/Change_Request_Template.md` (wherever Jinja2 render-and-assert skeletons live).

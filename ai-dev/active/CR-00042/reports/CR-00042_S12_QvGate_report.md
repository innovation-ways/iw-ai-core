# CR-00042 S12 QvGate Report

## Gate

| Field        | Value           |
|--------------|-----------------|
| Gate         | security-sast      |
| Command      | `make security-sast` |
| Exit code    | 0             |
| Result       | PASS         |
| Duration (s) | 20       |

## Output (tail)

```
[security-deps] pip-audit ...
Found 1 known vulnerability in 1 package
ERROR:pip_audit._cli:iw-ai-core: Dependency not found on PyPI and could not be audited: iw-ai-core (0.1.0)
[security-deps] bandit ...
[main]	INFO	profile include tests: None
[main]	INFO	profile exclude tests: B101
[main]	INFO	cli include tests: None
[main]	INFO	cli exclude tests: None
[manager]	WARNING	Test in comment: shell is not a test name or id, ignoring
[manager]	WARNING	Test in comment: True is not a test name or id, ignoring
[manager]	WARNING	Test in comment: intentional is not a test name or id, ignoring
[manager]	WARNING	Test in comment: command is not a test name or id, ignoring
[manager]	WARNING	Test in comment: from is not a test name or id, ignoring
[manager]	WARNING	Test in comment: trusted is not a test name or id, ignoring
[manager]	WARNING	Test in comment: projects is not a test name or id, ignoring
[manager]	WARNING	Test in comment: toml is not a test name or id, ignoring
[manager]	WARNING	Test in comment: ephemeral is not a test name or id, ignoring
[manager]	WARNING	Test in comment: PID is not a test name or id, ignoring
[manager]	WARNING	Test in comment: file is not a test name or id, ignoring
[manager]	WARNING	Test in comment: owner is not a test name or id, ignoring
[manager]	WARNING	Test in comment: only is not a test name or id, ignoring
[tester]	WARNING	nosec encountered (B108), but no failed test on file dashboard/services/oss_service.py:406
[tester]	WARNING	nosec encountered (B108), but no failed test on file orch/daemon/browser_env.py:637
[tester]	WARNING	nosec encountered (B108), but no failed test on file orch/daemon/browser_env.py:637
Working... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:01
[json]	INFO	JSON output written to file: tests/output/security/bandit.json
[main]	INFO	profile include tests: None
[main]	INFO	profile exclude tests: B101
[main]	INFO	cli include tests: None
[main]	INFO	cli exclude tests: None
[main]	INFO	using config: pyproject.toml
[main]	INFO	running on Python 3.12.3
[manager]	WARNING	Test in comment: shell is not a test name or id, ignoring
[manager]	WARNING	Test in comment: True is not a test name or id, ignoring
[manager]	WARNING	Test in comment: intentional is not a test name or id, ignoring
[manager]	WARNING	Test in comment: command is not a test name or id, ignoring
[manager]	WARNING	Test in comment: from is not a test name or id, ignoring
[manager]	WARNING	Test in comment: trusted is not a test name or id, ignoring
[manager]	WARNING	Test in comment: projects is not a test name or id, ignoring
[manager]	WARNING	Test in comment: toml is not a test name or id, ignoring
[manager]	WARNING	Test in comment: ephemeral is not a test name or id, ignoring
[manager]	WARNING	Test in comment: PID is not a test name or id, ignoring
[manager]	WARNING	Test in comment: file is not a test name or id, ignoring
[manager]	WARNING	Test in comment: owner is not a test name or id, ignoring
[manager]	WARNING	Test in comment: only is not a test name or id, ignoring
[tester]	WARNING	nosec encountered (B108), but no failed test on file dashboard/services/oss_service.py:406
[tester]	WARNING	nosec encountered (B108), but no failed test on file orch/daemon/browser_env.py:637
[tester]	WARNING	nosec encountered (B108), but no failed test on file orch/daemon/browser_env.py:637
Working... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:01
Run started:2026-05-10 18:51:05.085479+00:00

Test results:
>> Issue: [B704:markupsafe_markup_xss] Potential XSS with ``markupsafe.Markup`` detected. Do not use ``Markup`` on untrusted data.
   Severity: Medium   Confidence: High
   CWE: CWE-79 (https://cwe.mitre.org/data/definitions/79.html)
   More Info: https://bandit.readthedocs.io/en/1.9.4/plugins/b704_markupsafe_markup_xss.html
   Location: dashboard/routers/system.py:439:29
438	            "doc_title": doc_slug.replace("_", " "),
439	            "rendered_html": Markup(rendered),  # noqa: S704
440	        },

--------------------------------------------------

Code scanned:
	Total lines of code: 44263
	Total lines skipped (#nosec): 0
	Total potential issues skipped due to specifically being disabled (e.g., #nosec BXXX): 17

Run metrics:
	Total issues (by severity):
		Undefined: 0
		Low: 198
		Medium: 1
		High: 0
	Total issues (by confidence):
		Undefined: 0
		Low: 0
		Medium: 5
		High: 194
Files skipped (0):
[security-deps] OK
[security-sast] complete
```

## Verdict

```
pass
```

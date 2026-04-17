# CR-00006 S11 QV Fix Cycle 1/5

Quality gate S11 for work item CR-00006 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: Timeout after 600s (limit: 600s)

**Command output**:
```
...(truncated)...
in/esbuild --service=0.21.5 --ping
sergiog  1892739  0.1  0.1 11741412 220976 ?     Ssl  Apr11   9:55 /usr/bin/node /home/sergiog/.local/lib/node_modules/@playwright/cli/node_modules/playwright/cli.js run-cli-server --daemon-session=/home/sergiog/.cache/ms-playwright/daemon/7adc7e9b1d592eb8/default.session
sergiog  2041516  0.1  0.1 11667512 145112 ?     Ssl  Apr12   8:27 /usr/bin/node /home/sergiog/.local/lib/node_modules/@playwright/cli/node_modules/playwright/cli.js run-cli-server --daemon-session=/home/sergiog/.cache/ms-playwright/daemon/85e2c3c10d2f0043/default.session
sergiog  2964203  0.1  0.1 11770688 252692 ?     Ssl  Apr14   4:44 /usr/bin/node /home/sergiog/.local/lib/node_modules/@playwright/cli/node_modules/playwright/cli.js run-cli-server --daemon-session=/home/sergiog/.cache/ms-playwright/daemon/0b8ca82e9ae1a8cb/default.session
sergiog  3193600  0.0  0.0 110684 75952 ?        Ss   Apr16   0:10 /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv/bin/python3 -m orch.daemon
70       3193601  0.0  0.0 178332 33896 ?        Ss   Apr16   0:01 postgres: iw_orch iw_orch 172.16.2.1(46676) idle
70       3193613  0.0  0.0 178488 33244 ?        Ss   Apr16   0:01 postgres: iw_orch iw_orch 172.16.2.1(46684) idle
sergiog  3361640  0.1  0.1 11662452 138344 ?     Ssl  08:32   0:14 /usr/bin/node /home/sergiog/.local/lib/node_modules/@playwright/cli/node_modules/playwright/cli.js run-cli-server --daemon-session=/home/sergiog/.cache/ms-playwright/daemon/1a38abec0b168de6/default.session
sergiog  3422909  0.0  0.0 303644 119672 ?       Sl   Apr16   0:00 /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00047/.venv/bin/python /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00047/.venv/bin/pytest tests/integration/test_code_sse.py::TestCodeSSEStream::test_sse_sends_progress_and_done_events -v -s --log-cli-level=DEBUG
sergiog  3759689  0.0  0.2 26018860 264172 ?     Sl   Apr13   1:26 node /home/sergiog/dev/iw-doc-plan/main/iw-doc-plan/frontend/node_modules/.bin/vite
sergiog  3759702  0.0  0.0 1404456 55972 ?       Sl   Apr13   1:49 /home/sergiog/dev/iw-doc-plan/main/iw-doc-plan/frontend/node_modules/@esbuild/linux-x64/bin/esbuild --service=0.21.5 --ping
sergiog  3777477  0.1  0.1 11656532 130944 ?     Ssl  Apr16   1:28 /usr/bin/node /home/sergiog/.local/lib/node_modules/@playwright/cli/node_modules/playwright/cli.js run-cli-server --daemon-session=/home/sergiog/.cache/ms-playwright/daemon/04d335285a634f97/default.session
sergiog  4097098  0.0  0.0   2804  2012 ?        Ss   11:43   0:00 /bin/sh -c opencode run "$(cat /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00006/.tmp/CR-00006_S11.prompt)" --dangerously-skip-permissions --agent QualityValidation
sergiog  4130639  3.3  0.0 11655768 127168 ?     Ssl  11:52   0:00 /usr/bin/node /home/sergiog/.local/lib/node_modules/@playwright/cli/node_modules/playwright/cli.js run-cli-server --daemon-session=/home/sergiog/.cache/ms-playwright/daemon/e2e9b2ab13524521/default.session
[0m

```

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.

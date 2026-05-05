# I-00067 S11 QvGate Report

## Gate

| Field        | Value           |
|--------------|-----------------|
| Gate         | security-sast      |
| Command      | `make security-sast` |
| Exit code    | 0             |
| Result       | PASS         |
| Duration (s) | 8       |

## Output (tail)

```
   Severity: High   Confidence: High
   CWE: CWE-78 (https://cwe.mitre.org/data/definitions/78.html)
   More Info: https://bandit.readthedocs.io/en/1.9.4/plugins/b602_subprocess_popen_with_shell_equals_true.html
   Location: orch/daemon/browser_env.py:421:21
420	                env_up_cmd,
421	                shell=True,
422	                cwd=worktree_path,
423	                stdout=log_fh,
424	                stderr=subprocess.STDOUT,
425	                timeout=600,
426	                env=merged_env,
427	            )
428	        if result.returncode != 0:
429	            logger.warning(
430	                "[%s/%s] browser env_up exited %d — see %s",

--------------------------------------------------
>> Issue: [B108:hardcoded_tmp_directory] Probable insecure usage of temp file/directory.
   Severity: Medium   Confidence: Medium
   CWE: CWE-377 (https://cwe.mitre.org/data/definitions/377.html)
   More Info: https://bandit.readthedocs.io/en/1.9.4/plugins/b108_hardcoded_tmp_directory.html
   Location: orch/daemon/browser_env.py:521:26
520	        # If we can't even create the log path, still try to run the command
521	        log_path = Path(f"/tmp/{item_id}_{step_id}_browser_env_down.log")  # noqa: S108
522	

--------------------------------------------------
>> Issue: [B602:subprocess_popen_with_shell_equals_true] subprocess call with shell=True identified, security issue.
   Severity: High   Confidence: High
   CWE: CWE-78 (https://cwe.mitre.org/data/definitions/78.html)
   More Info: https://bandit.readthedocs.io/en/1.9.4/plugins/b602_subprocess_popen_with_shell_equals_true.html
   Location: orch/daemon/browser_env.py:534:21
533	                env_down_cmd,
534	                shell=True,
535	                cwd=worktree_path,
536	                stdout=log_fh,
537	                stderr=subprocess.STDOUT,
538	                timeout=300,
539	                env=merged_env,
540	            )
541	        if result.returncode != 0:
542	            logger.warning(
543	                "[%s/%s] browser env_down exited %d (non-fatal) — see %s",

--------------------------------------------------
>> Issue: [B602:subprocess_popen_with_shell_equals_true] subprocess call with shell=True identified, security issue.
   Severity: High   Confidence: High
   CWE: CWE-78 (https://cwe.mitre.org/data/definitions/78.html)
   More Info: https://bandit.readthedocs.io/en/1.9.4/plugins/b602_subprocess_popen_with_shell_equals_true.html
   Location: orch/daemon/doc_job_poller.py:170:15
169	            cmd,
170	            shell=True,
171	            cwd=worktree_path,
172	            stdout=log_file.open("w"),
173	            stderr=subprocess.STDOUT,
174	            start_new_session=True,
175	            env=_agent_subprocess_env(),
176	        )
177	
178	        with self._session_factory() as db:
179	            svc = DocService(db)

--------------------------------------------------
>> Issue: [B602:subprocess_popen_with_shell_equals_true] subprocess call with shell=True identified, security issue.
   Severity: High   Confidence: High
   CWE: CWE-78 (https://cwe.mitre.org/data/definitions/78.html)
   More Info: https://bandit.readthedocs.io/en/1.9.4/plugins/b602_subprocess_popen_with_shell_equals_true.html
   Location: orch/daemon/fix_cycle.py:829:17
828	            command,
829	            shell=True,
830	            cwd=worktree_path,
831	            capture_output=True,
832	            text=True,
833	            timeout=900,
834	            env=_agent_subprocess_env(),
835	        )
836	        output = result.stdout + result.stderr
837	        return parser(output)
838	    except Exception as e:

--------------------------------------------------
>> Issue: [B602:subprocess_popen_with_shell_equals_true] subprocess call with shell=True identified, security issue.
   Severity: High   Confidence: High
   CWE: CWE-78 (https://cwe.mitre.org/data/definitions/78.html)
   More Info: https://bandit.readthedocs.io/en/1.9.4/plugins/b602_subprocess_popen_with_shell_equals_true.html
   Location: orch/daemon/fix_cycle.py:1490:11
1489	        shell_command,
1490	        shell=True,
1491	        cwd=worktree_path,
1492	        stdin=subprocess.DEVNULL,
1493	        stdout=Path(log_file).open("w"),  # noqa: SIM115
1494	        stderr=subprocess.STDOUT,
1495	        start_new_session=True,
1496	        env=env,
1497	    )
1498	
1499	    logger.info(
1500	        "Fix agent launched: %s/%s cycle %d (PID %d, timeout %ds)",

--------------------------------------------------
>> Issue: [B701:jinja2_autoescape_false] Using jinja2 templates with autoescape=False is dangerous and can lead to XSS. Use autoescape=True or use the select_autoescape function to mitigate XSS vulnerabilities.
   Severity: High   Confidence: High
   CWE: CWE-94 (https://cwe.mitre.org/data/definitions/94.html)
   More Info: https://bandit.readthedocs.io/en/1.9.4/plugins/b701_jinja2_autoescape_false.html
   Location: orch/daemon/worktree_compose.py:218:10
217	    """
218	    env = jinja2.Environment(
219	        autoescape=False,  # noqa: S701  YAML output, not HTML
220	        undefined=jinja2.StrictUndefined,
221	    )
222	

--------------------------------------------------
>> Issue: [B602:subprocess_popen_with_shell_equals_true] subprocess call with shell=True identified, security issue.
   Severity: High   Confidence: High
   CWE: CWE-78 (https://cwe.mitre.org/data/definitions/78.html)
   More Info: https://bandit.readthedocs.io/en/1.9.4/plugins/b602_subprocess_popen_with_shell_equals_true.html
   Location: orch/test_runner.py:115:23
114	                    command,
115	                    shell=True,
116	                    cwd=execution_dir,
117	                    stdout=log_file,
118	                    stderr=subprocess.STDOUT,
119	                    preexec_fn=os.setsid,
120	                )
121	
122	            # Store PID for kill support
123	            run.pid = proc.pid

--------------------------------------------------
>> Issue: [B602:subprocess_popen_with_shell_equals_true] subprocess call with shell=True identified, security issue.
   Severity: High   Confidence: High
   CWE: CWE-78 (https://cwe.mitre.org/data/definitions/78.html)
   More Info: https://bandit.readthedocs.io/en/1.9.4/plugins/b602_subprocess_popen_with_shell_equals_true.html
   Location: orch/test_runner.py:338:23
337	                    agent_command,
338	                    shell=True,
339	                    cwd=execution_dir,
340	                    stdout=log_file,
341	                    stderr=subprocess.STDOUT,
342	                    preexec_fn=os.setsid,
343	                )
344	
345	            run.pid = proc.pid
346	            db.commit()

--------------------------------------------------
>> Issue: [B602:subprocess_popen_with_shell_equals_true] subprocess call with shell=True identified, security issue.
   Severity: High   Confidence: High
   CWE: CWE-78 (https://cwe.mitre.org/data/definitions/78.html)
   More Info: https://bandit.readthedocs.io/en/1.9.4/plugins/b602_subprocess_popen_with_shell_equals_true.html
   Location: orch/test_runner.py:396:30
395	                    command,
396	                    shell=True,
397	                    cwd=execution_dir,
398	                    stdout=log_file,
399	                    stderr=subprocess.STDOUT,
400	                    timeout=300,
401	                )
402	            final_exit_code = verify_proc.returncode
403	        except Exception as exc:
404	            logger.warning("Final verification run failed for quality-fix %d: %s", run_id, exc)

--------------------------------------------------
>> Issue: [B602:subprocess_popen_with_shell_equals_true] subprocess call with shell=True identified, security issue.
   Severity: High   Confidence: High
   CWE: CWE-78 (https://cwe.mitre.org/data/definitions/78.html)
   More Info: https://bandit.readthedocs.io/en/1.9.4/plugins/b602_subprocess_popen_with_shell_equals_true.html
   Location: orch/test_runner.py:643:8
642	            command,
643	            shell=True,
644	            cwd=cwd,
645	            capture_output=True,
646	            timeout=60,
647	        )
648	
649	
650	def _generate_allure_report(results_dir: str, report_dir: str | None, cwd: str) -> bool:

--------------------------------------------------

Code scanned:
	Total lines of code: 40306
	Total lines skipped (#nosec): 0
	Total potential issues skipped due to specifically being disabled (e.g., #nosec BXXX): 0

Run metrics:
	Total issues (by severity):
		Undefined: 0
		Low: 175
		Medium: 3
		High: 14
	Total issues (by confidence):
		Undefined: 0
		Low: 0
		Medium: 8
		High: 184
Files skipped (0):
[security-deps] OK
[security-sast] complete
```

## Verdict

```
pass
```

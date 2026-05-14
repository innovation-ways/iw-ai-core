# CR-00051 S11 QvGate Report

## Gate

| Field        | Value           |
|--------------|-----------------|
| Gate         | security-sast      |
| Command      | `make security-sast` |
| Exit code    | 0             |
| Result       | PASS         |
| Duration (s) | 12       |

## Output (tail)

```
[security-sast] semgrep ...
               
               
┌─────────────┐
│ Scan Status │
└─────────────┘
  Scanning 463 files tracked by git with 674 Code rules:
                                                                                                                        
  Language      Rules   Files          Origin      Rules                                                                
 ─────────────────────────────        ───────────────────                                                               
  <multilang>      12     463          Community     674                                                                
  python          198     242                                                                                           
  js               78      19                                                                                           
  bash              1       4                                                                                           
  yaml             19       1                                                                                           
                                                                                                                        
                
                
┌──────────────┐
│ Scan Summary │
└──────────────┘
✅ Scan completed successfully.
 • Findings: 0 (0 blocking)
 • Rules run: 308
 • Targets scanned: 463
 • Parsed lines: ~99.9%
 • Scan skipped: 
   ◦ Files matching .semgrepignore patterns: 31
 • Scan was limited to files tracked by git
 • For a detailed list of skipped files and lines, run semgrep with the --verbose flag
Ran 308 rules on 463 files: 0 findings.
(need more rules? `semgrep login` for additional free Semgrep Registry rules)


A new version of Semgrep is available. See https://semgrep.dev/docs/upgrading
If Semgrep missed a finding, please send us feedback to let us know!
See https://semgrep.dev/docs/reporting-false-negatives/
               
               
┌─────────────┐
│ Scan Status │
└─────────────┘
  Scanning 463 files tracked by git with 674 Code rules:
                                                                                                                        
  Language      Rules   Files          Origin      Rules                                                                
 ─────────────────────────────        ───────────────────                                                               
  <multilang>      12     463          Community     674                                                                
  python          198     242                                                                                           
  js               78      19                                                                                           
  bash              1       4                                                                                           
  yaml             19       1                                                                                           
                                                                                                                        
                
                
┌──────────────┐
│ Scan Summary │
└──────────────┘
✅ Scan completed successfully.
 • Findings: 0 (0 blocking)
 • Rules run: 308
 • Targets scanned: 463
 • Parsed lines: ~99.9%
 • Scan skipped: 
   ◦ Files matching .semgrepignore patterns: 31
 • Scan was limited to files tracked by git
 • For a detailed list of skipped files and lines, run semgrep with the --verbose flag
Ran 308 rules on 463 files: 0 findings.
(need more rules? `semgrep login` for additional free Semgrep Registry rules)


A new version of Semgrep is available. See https://semgrep.dev/docs/upgrading
If Semgrep missed a finding, please send us feedback to let us know!
See https://semgrep.dev/docs/reporting-false-negatives/
[security-sast] OK
```

## Verdict

```
pass
```

# F-00082 S11 QvGate Report

## Gate

| Field        | Value           |
|--------------|-----------------|
| Gate         | security-sast      |
| Command      | `make security-sast` |
| Exit code    | 2             |
| Result       | FAIL         |
| Duration (s) | 13       |

## Output (tail)

```
          attacks. If using Flask, use 'url_for()' to safely generate a URL. If using Django, use the 'url' 
          filter to safely generate a URL. If using Mustache, use a URL encoding library, or prepend a slash
          '/' to the variable for relative links (`href="/{{link}}"`). You may also consider setting the    
          Content Security Policy (CSP) header.                                                             
          Details: https://sg.run/x1kP                                                                      
                                                                                                            
            7┆ <a href="{{ primary_href }}" class="empty-state__cta-primary">{{ primary_label }}</a>
            ⋮┆----------------------------------------
            9┆ <a href="{{ secondary_href }}" class="empty-state__cta-secondary">{{ secondary_label }}</a>
                                                       
    dashboard/templates/pages/project/batch_detail.html
    ❯❱ python.flask.security.xss.audit.template-unescaped-with-safe.template-unescaped-with-safe
          ❰❰ Blocking ❱❱
          Detected a segment of a Flask template where autoescaping is explicitly disabled with '| safe'  
          filter. This allows rendering of raw HTML in this segment. Ensure no user data is rendered here,
          otherwise this is a cross-site scripting (XSS) vulnerability.                                   
          Details: https://sg.run/W8og                                                                    
                                                                                                          
          113┆ {{ plan_html | safe }}
                                                
    dashboard/templates/pages/project/queue.html
    ❯❱ generic.html-templates.security.unquoted-attribute-var.unquoted-attribute-var
          ❰❰ Blocking ❱❱
          Detected a unquoted template variable as an attribute. If unquoted, a malicious actor could inject
          custom JavaScript handlers. To fix this, add quotes around the template expression, like this: "{{
          expr }}".                                                                                         
          Details: https://sg.run/weNX                                                                      
                                                                                                            
          117┆ {{ write_button_attrs(request) }}>
            ⋮┆----------------------------------------
          174┆ {{ write_button_attrs(request) }}>
                                                 
    dashboard/templates/pages/system/running.html
    ❯❱ generic.html-templates.security.unquoted-attribute-var.unquoted-attribute-var
          ❰❰ Blocking ❱❱
          Detected a unquoted template variable as an attribute. If unquoted, a malicious actor could inject
          custom JavaScript handlers. To fix this, add quotes around the template expression, like this: "{{
          expr }}".                                                                                         
          Details: https://sg.run/weNX                                                                      
                                                                                                            
          137┆ {{ write_button_attrs(request) }}>
                                                   
    dashboard/templates/pages/system/worktrees.html
    ❯❱ generic.html-templates.security.unquoted-attribute-var.unquoted-attribute-var
          ❰❰ Blocking ❱❱
          Detected a unquoted template variable as an attribute. If unquoted, a malicious actor could inject
          custom JavaScript handlers. To fix this, add quotes around the template expression, like this: "{{
          expr }}".                                                                                         
          Details: https://sg.run/weNX                                                                      
                                                                                                            
           23┆ {{ write_button_attrs(request) }}>
                                        
    dashboard/templates/pdf/doc_pdf.html
    ❯❱ python.flask.security.xss.audit.template-unescaped-with-safe.template-unescaped-with-safe
          ❰❰ Blocking ❱❱
          Detected a segment of a Flask template where autoescaping is explicitly disabled with '| safe'  
          filter. This allows rendering of raw HTML in this segment. Ensure no user data is rendered here,
          otherwise this is a cross-site scripting (XSS) vulnerability.                                   
          Details: https://sg.run/W8og                                                                    
                                                                                                          
          172┆ {{ rendered_content | safe }}
                                         
    dashboard/templates/project_code.html
    ❯❱ generic.html-templates.security.unquoted-attribute-var.unquoted-attribute-var
          ❰❰ Blocking ❱❱
          Detected a unquoted template variable as an attribute. If unquoted, a malicious actor could inject
          custom JavaScript handlers. To fix this, add quotes around the template expression, like this: "{{
          expr }}".                                                                                         
          Details: https://sg.run/weNX                                                                      
                                                                                                            
           52┆ {{ write_button_attrs(request) }}>
            ⋮┆----------------------------------------
           63┆ {{ write_button_attrs(request) }}>
            ⋮┆----------------------------------------
           74┆ {{ write_button_attrs(request) }}>
            ⋮┆----------------------------------------
           85┆ {{ write_button_attrs(request) }}>
                                            
    dashboard/templates/research_detail.html
    ❯❱ python.flask.security.xss.audit.template-unescaped-with-safe.template-unescaped-with-safe
          ❰❰ Blocking ❱❱
          Detected a segment of a Flask template where autoescaping is explicitly disabled with '| safe'  
          filter. This allows rendering of raw HTML in this segment. Ensure no user data is rendered here,
          otherwise this is a cross-site scripting (XSS) vulnerability.                                   
          Details: https://sg.run/W8og                                                                    
                                                                                                          
          131┆ {{ content_html | safe }}
                                  
    orch/archive/batch_archiver.py
   ❯❯❱ python.lang.security.audit.subprocess-shell-true.subprocess-shell-true
          ❰❰ Blocking ❱❱
          Found 'subprocess' function 'run' with 'shell=True'. This is dangerous because this call will spawn
          the command using a shell process. Doing so propagates current shell settings and variables, which 
          makes it much easier for a malicious actor to execute commands. Use 'shell=False' instead.         
          Details: https://sg.run/J92w                                                                       
                                                                                                             
           ▶▶┆ Autofix ▶ False
          325┆ shell=True,  # nosec B602
                                
    orch/daemon/batch_manager.py
   ❯❯❱ python.lang.security.audit.subprocess-shell-true.subprocess-shell-true
          ❰❰ Blocking ❱❱
          Found 'subprocess' function 'Popen' with 'shell=True'. This is dangerous because this call will   
          spawn the command using a shell process. Doing so propagates current shell settings and variables,
          which makes it much easier for a malicious actor to execute commands. Use 'shell=False' instead.  
          Details: https://sg.run/J92w                                                                      
                                                                                                            
           ▶▶┆ Autofix ▶ False
          875┆ shell=True,  # nosec B602
            ⋮┆----------------------------------------
           ▶▶┆ Autofix ▶ False
          1302┆ shell=True,  # nosec B602
                              
    orch/daemon/browser_env.py
   ❯❯❱ python.lang.security.audit.subprocess-shell-true.subprocess-shell-true
          ❰❰ Blocking ❱❱
          Found 'subprocess' function 'run' with 'shell=True'. This is dangerous because this call will spawn
          the command using a shell process. Doing so propagates current shell settings and variables, which 
          makes it much easier for a malicious actor to execute commands. Use 'shell=False' instead.         
          Details: https://sg.run/J92w                                                                       
                                                                                                             
           ▶▶┆ Autofix ▶ False
          421┆ shell=True,  # nosec B602
            ⋮┆----------------------------------------
           ▶▶┆ Autofix ▶ False
          650┆ shell=True,  # nosec B602
                                 
    orch/daemon/doc_job_poller.py
   ❯❯❱ python.lang.security.audit.subprocess-shell-true.subprocess-shell-true
          ❰❰ Blocking ❱❱
          Found 'subprocess' function 'Popen' with 'shell=True'. This is dangerous because this call will   
          spawn the command using a shell process. Doing so propagates current shell settings and variables,
          which makes it much easier for a malicious actor to execute commands. Use 'shell=False' instead.  
          Details: https://sg.run/J92w                                                                      
                                                                                                            
           ▶▶┆ Autofix ▶ False
          248┆ shell=True,  # nosec B602
                            
    orch/daemon/fix_cycle.py
   ❯❯❱ python.lang.security.audit.subprocess-shell-true.subprocess-shell-true
          ❰❰ Blocking ❱❱
          Found 'subprocess' function 'run' with 'shell=True'. This is dangerous because this call will spawn
          the command using a shell process. Doing so propagates current shell settings and variables, which 
          makes it much easier for a malicious actor to execute commands. Use 'shell=False' instead.         
          Details: https://sg.run/J92w                                                                       
                                                                                                             
           ▶▶┆ Autofix ▶ False
          1258┆ shell=True,  # nosec B602
                                   
    orch/daemon/worktree_compose.py
    ❯❱ python.jinja2.security.audit.autoescape-disabled-false.incorrect-autoescape-disabled
          ❰❰ Blocking ❱❱
          Detected a Jinja2 environment with 'autoescaping' disabled. This is dangerous if you are rendering
          to a browser because this allows for cross-site scripting (XSS) attacks. If you are in a web      
          context, enable 'autoescaping' by setting 'autoescape=True.' You may also consider using          
          'jinja2.select_autoescape()' to only enable automatic escaping for certain file extensions.       
          Details: https://sg.run/L2L7                                                                      
                                                                                                            
           ▶▶┆ Autofix ▶ True
          219┆ autoescape=False,  # noqa: S701  YAML output, not HTML
                         
    orch/rag/chat_repo.py
    ❯❱ python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure
          ❰❰ Blocking ❱❱
          Detected a python logger call with a potential hardcoded secret "tiktoken does not support model
          '%s', using heuristic fallback" being logged. This may lead to secret credentials being exposed.
          Make sure that the logger is not logging  sensitive information.                                
          Details: https://sg.run/ydNx                                                                    
                                                                                                          
           53┆ logger.warning(
           54┆     "tiktoken does not support model '%s', using heuristic fallback", model_name
           55┆ )
            ⋮┆----------------------------------------
    ❯❱ python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure
          ❰❰ Blocking ❱❱
          Detected a python logger call with a potential hardcoded secret "tiktoken encode failed for model
          '%s', using heuristic fallback" being logged. This may lead to secret credentials being exposed. 
          Make sure that the logger is not logging  sensitive information.                                 
          Details: https://sg.run/ydNx                                                                     
                                                                                                           
           63┆ logger.warning(
           64┆     "tiktoken encode failed for model '%s', using heuristic fallback", model_name
           65┆ )
                
                
┌──────────────┐
│ Scan Summary │
└──────────────┘
✅ Scan completed successfully.
 • Findings: 91 (91 blocking)
 • Rules run: 312
 • Targets scanned: 463
 • Parsed lines: ~100.0%
 • Scan skipped: 
   ◦ Files matching .semgrepignore patterns: 31
 • Scan was limited to files tracked by git
 • For a detailed list of skipped files and lines, run semgrep with the --verbose flag
Ran 312 rules on 463 files: 91 findings.

make: *** [Makefile:231: security-sast] Error 1
```

## Verdict

```
fail
```

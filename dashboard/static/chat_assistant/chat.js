// dashboard/static/chat_assistant/chat.js
// Dashboard AI Assistant — window.iwChat API
// Ctrl+/ keybinding (no collision with Cmd+\ used by the existing Code Q&A chat).
// All DOM ids are prefixed chat-assistant- to avoid collisions.
(function () {
  'use strict';

  // ── Tab identity ────────────────────────────────────────────────────────────
  var _tabId = sessionStorage.getItem('iw-chat-tab-id');
  if (!_tabId) {
    try {
      _tabId = crypto.randomUUID();
    } catch (_e) {
      // Fallback for environments without crypto.randomUUID
      _tabId = Date.now().toString(36) + Math.random().toString(36).slice(2);
    }
    sessionStorage.setItem('iw-chat-tab-id', _tabId);
  }

  // ── State ───────────────────────────────────────────────────────────────────
  var _sid = null;           // current OpenCode session id
  var _streaming = false;    // is an SSE stream active?
  var _es = null;            // EventSource instance
  var _seenIds = {};         // client-side dedup Set (object as map)
  var _lastSeenId = null;    // most recent event id received
  var _contextPollTimer = null;
  var _modelRefreshTimer = null;
  var _context = null;       // {type, id, title} from setContext / null
  var _chipDismissed = false;
  var _skills = [];          // cached skills list for slash menu
  var _pendingPermissions = {};  // rid -> {event, rid}

  // ── Cookie helpers ──────────────────────────────────────────────────────────
  function _setCookie(name, value, path) {
    document.cookie = name + '=' + value + '; path=' + (path || '/');
  }

  function _getCookie(name) {
    var m = document.cookie.match('(?:^|; )' + name + '=([^;]*)');
    return m ? m[1] : null;
  }

  // ── Panel DOM helpers ───────────────────────────────────────────────────────
  function _panel() { return document.getElementById('chat-assistant-panel'); }

  function _isOpen() {
    var p = _panel();
    return p && p.dataset.collapsed !== 'true';
  }

  function _applyOpenState(open) {
    var p = _panel();
    if (!p) return;
    p.dataset.collapsed = open ? 'false' : 'true';
    if (open) {
      p.style.width = '360px';
    } else {
      p.style.width = '40px';
    }
    _setCookie('iw-chat-assistant-open', open ? '1' : '0', '/');
    if (open) {
      _ensureSession();
      _refreshModels();
    }
  }

  // ── Public API ──────────────────────────────────────────────────────────────
  function open() {
    if (!_isOpen()) _applyOpenState(true);
  }

  function close() {
    if (_isOpen()) _applyOpenState(false);
  }

  function toggle() {
    _applyOpenState(!_isOpen());
  }

  function setContext(ctx) {
    _context = ctx;
    _chipDismissed = false;
    _renderChip();
  }

  function clearContext() {
    _context = null;
    _chipDismissed = false;
    _renderChip();
  }

  function openWith(prefilledText) {
    open();
    var input = document.getElementById('chat-assistant-input');
    if (input) {
      input.value = prefilledText || '';
      input.focus();
    }
  }

  function newSession() {
    _teardownStream();
    _sid = null;
    _seenIds = {};
    _lastSeenId = null;
    _clearMessages();
    sessionStorage.removeItem('iw-chat-session-' + _tabId);
    _ensureSession();
  }

  function switchSession(sid) {
    _teardownStream();
    _sid = sid;
    _seenIds = {};
    _lastSeenId = null;
    _clearMessages();
    sessionStorage.setItem('iw-chat-session-' + _tabId, sid);
    _loadHistory(sid);
    _connectStream(sid);
  }

  window.iwChat = {
    open: open,
    close: close,
    toggle: toggle,
    setContext: setContext,
    clearContext: clearContext,
    openWith: openWith,
    newSession: newSession,
    switchSession: switchSession
  };

  // ── Session management ──────────────────────────────────────────────────────
  function _ensureSession() {
    var cached = sessionStorage.getItem('iw-chat-session-' + _tabId);
    if (cached) {
      _sid = cached;
      _connectStream(_sid);
      _loadHistory(_sid);
      return;
    }
    _createSession();
  }

  function _createSession() {
    var model = _getSelectedModel();
    var body = {};
    if (model) body.model = model;
    fetch('/api/chat/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
      .then(function (r) {
        if (!r.ok) throw new Error('create session failed: ' + r.status);
        return r.json();
      })
      .then(function (data) {
        _sid = data.session_id;
        sessionStorage.setItem('iw-chat-session-' + _tabId, _sid);
        _connectStream(_sid);
      })
      .catch(function (err) {
        _appendSystemMessage('Failed to create session: ' + err.message, 'error');
      });
  }

  // ── SSE streaming ───────────────────────────────────────────────────────────
  function _connectStream(sid) {
    _teardownStream();
    if (!sid) return;
    var url = '/api/chat/sessions/' + sid + '/stream';
    if (_lastSeenId) {
      url += '?last_event_id=' + encodeURIComponent(_lastSeenId);
    }
    _es = new EventSource(url);
    _es.onopen = function () {
      _hideReconnecting();
    };
    _es.onerror = function () {
      _showReconnecting();
    };
    _es.onmessage = function (e) {
      _handleEvent('message', e);
    };
    // Named events from the relay
    var namedEvents = [
      'message.part', 'message.snapshot', 'message.complete', 'message.updated',
      'tool.call', 'tool.result', 'permission.asked',
      'session.idle', 'error', 'gap', 'reconnecting'
    ];
    namedEvents.forEach(function (evName) {
      _es.addEventListener(evName, function (e) {
        _handleEvent(evName, e);
      });
    });
  }

  function _teardownStream() {
    if (_es) {
      _es.close();
      _es = null;
    }
    _streaming = false;
    _stopContextPoll();
    _updateSendAbortButtons();
  }

  function _handleEvent(evName, e) {
    // Track last-event-id for reconnect
    if (e.lastEventId) {
      _lastSeenId = e.lastEventId;
    }

    // Client-side dedup
    var eid = e.lastEventId || null;
    if (eid) {
      if (_seenIds[eid]) return;
      _seenIds[eid] = true;
    }

    var data = null;
    try {
      data = JSON.parse(e.data);
    } catch (_pe) {
      data = { text: e.data };
    }

    if (evName === 'gap') {
      _appendGapWarning();
      return;
    }
    if (evName === 'reconnecting') {
      _showReconnecting();
      return;
    }
    if (evName === 'session.idle') {
      _streaming = false;
      _stopContextPoll();
      _updateSendAbortButtons();
      if (data && data.permission_denied) {
        _appendSystemMessage('Run aborted (permission denied).', 'info');
      } else if (data && data.aborted) {
        _appendSystemMessage('Run aborted.', 'info');
      } else {
        _appendSystemMessage('Session idle.', 'info');
      }
      return;
    }
    if (evName === 'permission.asked') {
      var rid = data && data.request_id;
      if (rid) {
        _pendingPermissions[rid] = data;
        _showApprovalModal(data);
      }
      return;
    }
    if (evName === 'error') {
      var msg = (data && data.message) || 'An error occurred.';
      _appendSystemMessage(msg, 'error');
      _streaming = false;
      _stopContextPoll();
      _updateSendAbortButtons();
      return;
    }
    if (evName === 'message.part' || evName === 'message') {
      if (!_streaming) {
        _streaming = true;
        _updateSendAbortButtons();
        _startContextPoll();
      }
      var text = (data && (data.text || data.content || data.delta)) || '';
      _appendOrUpdateAssistantMessage(eid, text, false);
      return;
    }
    if (evName === 'message.snapshot') {
      var snapshotText = (data && (data.text || data.content)) || '';
      _appendOrUpdateAssistantMessage(eid, snapshotText, false);
      return;
    }
    if (evName === 'message.updated') {
      var status = data && data.status;
      var updatedText = (data && (data.text || data.content || '')) || '';
      var isComplete = status === 'complete';
      _appendOrUpdateAssistantMessage(eid, updatedText, isComplete);
      if (status === 'streaming' && !_streaming) {
        _streaming = true;
        _updateSendAbortButtons();
        _startContextPoll();
      }
      if (isComplete) {
        _streaming = false;
        _stopContextPoll();
        _updateSendAbortButtons();
        _finaliseLastAssistantMessage();
      }
      return;
    }
    if (evName === 'message.complete') {
      _streaming = false;
      _stopContextPoll();
      _updateSendAbortButtons();
      var finalText = (data && (data.text || data.content)) || null;
      if (finalText) {
        _appendOrUpdateAssistantMessage(eid, finalText, true);
      } else {
        _finaliseLastAssistantMessage();
      }
      return;
    }
    if (evName === 'tool.call') {
      var tname = (data && data.tool) || 'unknown';
      var targs = (data && data.args) || {};
      _appendToolCall(tname, targs);
      return;
    }
    if (evName === 'tool.result') {
      var tresult = (data && (data.result || data.output)) || '';
      _appendToolResult(tresult);
      return;
    }
  }

  // ── Approval modal ──────────────────────────────────────────────────────────
  function _showApprovalModal(data) {
    var root = document.getElementById('chat-assistant-approval-root');
    if (!root) return;

    // Build the modal HTML
    var toolName = data.tool || data.tool_name || 'unknown';
    var args = data.args || data.arguments || {};
    var argsStr = '';
    try {
      argsStr = typeof args === 'string' ? args : JSON.stringify(args, null, 2);
    } catch (_e) {
      argsStr = String(args);
    }
    var rationale = data.rationale || data.reason || '';
    var rid = data.request_id || data.rid || '';

    var html = '<div id="chat-assistant-approval-modal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" role="dialog" aria-modal="true" aria-labelledby="chat-assistant-approval-title">';
    html += '<div class="bg-card border border-border rounded-lg shadow-lg max-w-lg w-full mx-4 p-5">';
    html += '<h2 id="chat-assistant-approval-title" class="text-sm font-semibold text-foreground mb-3">Permission Request</h2>';
    html += '<div class="mb-3"><div class="text-xs text-muted-foreground mb-1">Tool</div>';
    html += '<div class="font-mono text-xs bg-muted px-2 py-1 rounded text-foreground">' + _escHtml(toolName) + '</div></div>';
    html += '<div class="mb-3"><div class="text-xs text-muted-foreground mb-1">Arguments</div>';
    html += '<pre class="font-mono text-xs bg-muted px-2 py-2 rounded text-foreground overflow-x-auto whitespace-pre-wrap break-all max-h-48">' + _escHtml(argsStr) + '</pre></div>';
    if (rationale) {
      html += '<div class="mb-4"><div class="text-xs text-muted-foreground mb-1">Rationale</div>';
      html += '<p class="text-sm text-foreground bg-muted/40 px-2 py-1.5 rounded">' + _escHtml(rationale) + '</p></div>';
    }
    html += '<div class="flex items-center gap-3 flex-wrap">';
    html += '<button id="chat-assistant-approval-allow" type="button" class="inline-flex items-center gap-1.5 px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded min-h-[44px]">Allow</button>';
    html += '<button id="chat-assistant-approval-deny" type="button" class="inline-flex items-center gap-1.5 px-4 py-2 border border-destructive text-destructive text-sm font-medium rounded hover:bg-destructive/10 min-h-[44px]">Deny</button>';
    html += '<label class="ml-auto flex items-center gap-2 text-xs text-muted-foreground cursor-pointer"><input type="checkbox" id="chat-assistant-approval-remember" class="rounded border-border" /> Remember for this session</label>';
    html += '</div></div></div>';
    root.innerHTML = html;

    var allowBtn = document.getElementById('chat-assistant-approval-allow');
    var denyBtn = document.getElementById('chat-assistant-approval-deny');
    if (allowBtn) {
      allowBtn.addEventListener('click', function () {
        _replyPermission(rid, 'allow', root);
      });
    }
    if (denyBtn) {
      denyBtn.addEventListener('click', function () {
        _replyPermission(rid, 'deny', root);
      });
    }
  }

  function _replyPermission(rid, decision, root) {
    if (!_sid || !rid) return;
    var remember = false;
    var cb = document.getElementById('chat-assistant-approval-remember');
    if (cb) remember = cb.checked;
    fetch('/api/chat/sessions/' + _sid + '/permissions/' + encodeURIComponent(rid), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ response: decision, remember: remember })
    }).catch(function (err) {
      _appendSystemMessage('Permission reply failed: ' + err.message, 'error');
    });
    delete _pendingPermissions[rid];
    if (root) root.innerHTML = '';
  }

  // ── Message rendering ───────────────────────────────────────────────────────
  var _currentAssistantEl = null;
  var _currentAssistantId = null;

  function _clearMessages() {
    var msgs = document.getElementById('chat-assistant-messages');
    if (!msgs) return;
    var anchor = document.getElementById('chat-assistant-scroll-anchor');
    var empty = document.getElementById('chat-assistant-empty-state');
    msgs.innerHTML = '';
    if (empty) msgs.appendChild(empty);
    if (anchor) msgs.appendChild(anchor);
    _currentAssistantEl = null;
    _currentAssistantId = null;
  }

  function _appendUserMessage(text) {
    var msgs = document.getElementById('chat-assistant-messages');
    if (!msgs) return;
    _hideEmptyState();
    var div = document.createElement('div');
    div.className = 'flex justify-end';
    div.innerHTML = '<div class="max-w-[85%] rounded-lg bg-primary text-primary-foreground px-3 py-2 text-sm">' + _escHtml(text) + '</div>';
    msgs.insertBefore(div, document.getElementById('chat-assistant-scroll-anchor'));
    _scrollToBottom();
  }

  function _appendOrUpdateAssistantMessage(eid, text, isFinal) {
    var msgs = document.getElementById('chat-assistant-messages');
    if (!msgs) return;
    _hideEmptyState();

    // Streaming: accumulate into the same element
    if (!isFinal && _currentAssistantEl && _currentAssistantId !== null) {
      // Append text delta if this looks like a delta (short chunk)
      var bodyEl = _currentAssistantEl.querySelector('.chat-assistant-stream-text');
      if (bodyEl) {
        bodyEl.textContent += text;
        _scrollToBottom();
        return;
      }
    }

    // New assistant message element
    var wrap = document.createElement('div');
    wrap.className = 'flex gap-2 items-start';
    var iconHtml = '<div class="flex-shrink-0 w-5 h-5 rounded-full bg-muted flex items-center justify-center mt-0.5" aria-hidden="true">';
    iconHtml += '<svg class="w-3 h-3 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">';
    iconHtml += '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>';
    iconHtml += '</svg></div>';
    var bodyHtml = '<div class="flex-1 min-w-0"><div class="chat-assistant-stream-text chat-assistant-msg-body text-sm"></div></div>';
    wrap.innerHTML = iconHtml + bodyHtml;
    var bodyEl = wrap.querySelector('.chat-assistant-stream-text');
    if (bodyEl) bodyEl.textContent = text;
    msgs.insertBefore(wrap, document.getElementById('chat-assistant-scroll-anchor'));
    _currentAssistantEl = wrap;
    _currentAssistantId = eid;
    _scrollToBottom();
  }

  function _finaliseLastAssistantMessage() {
    _currentAssistantEl = null;
    _currentAssistantId = null;
  }

  function _appendToolCall(toolName, args) {
    var msgs = document.getElementById('chat-assistant-messages');
    if (!msgs) return;
    _hideEmptyState();
    var argsStr = '';
    try {
      argsStr = typeof args === 'string' ? args : JSON.stringify(args, null, 2);
    } catch (_e) {
      argsStr = String(args);
    }
    var div = document.createElement('div');
    div.className = 'rounded border border-border bg-muted/40 px-3 py-2 text-xs font-mono';
    div.innerHTML = '<span class="text-muted-foreground">tool: </span>'
      + '<span class="font-medium text-foreground">' + _escHtml(toolName) + '</span>'
      + '<pre class="mt-1 text-muted-foreground overflow-x-auto whitespace-pre-wrap break-all">' + _escHtml(argsStr) + '</pre>';
    msgs.insertBefore(div, document.getElementById('chat-assistant-scroll-anchor'));
    _scrollToBottom();
  }

  function _appendToolResult(result) {
    var msgs = document.getElementById('chat-assistant-messages');
    if (!msgs) return;
    var resultStr = typeof result === 'string' ? result : JSON.stringify(result, null, 2);
    var div = document.createElement('div');
    div.className = 'rounded border border-border bg-card px-3 py-2 text-xs font-mono';
    div.innerHTML = '<span class="text-muted-foreground">result: </span>'
      + '<pre class="mt-1 text-foreground overflow-x-auto whitespace-pre-wrap break-all">' + _escHtml(resultStr) + '</pre>';
    msgs.insertBefore(div, document.getElementById('chat-assistant-scroll-anchor'));
    _scrollToBottom();
  }

  function _appendSystemMessage(text, type) {
    var msgs = document.getElementById('chat-assistant-messages');
    if (!msgs) return;
    var cls = type === 'error'
      ? 'text-xs text-destructive border border-destructive/30 bg-destructive/5 rounded px-2 py-1.5'
      : 'text-xs text-muted-foreground border border-border bg-muted/40 rounded px-2 py-1.5';
    var div = document.createElement('div');
    div.className = cls;
    div.textContent = text;
    msgs.insertBefore(div, document.getElementById('chat-assistant-scroll-anchor'));
    _scrollToBottom();
  }

  function _appendGapWarning() {
    _appendSystemMessage('Some events may have been missed during reconnect.', 'info');
  }

  function _hideEmptyState() {
    var el = document.getElementById('chat-assistant-empty-state');
    if (el) el.style.display = 'none';
  }

  function _scrollToBottom() {
    var msgs = document.getElementById('chat-assistant-messages');
    if (msgs) msgs.scrollTop = msgs.scrollHeight;
  }

  // ── Load history on reconnect ───────────────────────────────────────────────
  function _loadHistory(sid) {
    fetch('/api/chat/sessions/' + sid)
      .then(function (r) {
        if (!r.ok) return null;
        return r.json();
      })
      .then(function (data) {
        if (!data || !data.messages) return;
        _clearMessages();
        data.messages.forEach(function (m) {
          if (m.role === 'user') {
            var text = typeof m.content === 'string' ? m.content : JSON.stringify(m.content);
            _appendUserMessage(text);
          } else if (m.role === 'assistant') {
            var atext = typeof m.content === 'string' ? m.content : JSON.stringify(m.content);
            _appendOrUpdateAssistantMessage(null, atext, true);
          }
        });
      })
      .catch(function () { /* silently ignore history load failures */ });
  }

  // ── Context chip rendering ──────────────────────────────────────────────────
  function _renderChip() {
    var container = document.getElementById('chat-assistant-chips');
    if (!container) return;
    container.innerHTML = '';
    if (!_context || _chipDismissed) return;
    var chip = document.createElement('div');
    chip.className = 'chat-assistant-chip';
    chip.innerHTML = '<span class="chat-assistant-chip-text">Currently viewing: ' + _escHtml(_context.title || _context.id || '') + '</span>'
      + '<button type="button" class="chat-assistant-chip-dismiss" aria-label="Dismiss context chip">&#x2715;</button>';
    var dismissBtn = chip.querySelector('.chat-assistant-chip-dismiss');
    if (dismissBtn) {
      dismissBtn.addEventListener('click', function () {
        _chipDismissed = true;
        container.innerHTML = '';
      });
    }
    container.appendChild(chip);
  }

  // ── Reconnecting pill ───────────────────────────────────────────────────────
  function _showReconnecting() {
    var p = document.getElementById('chat-assistant-reconnecting-pill');
    if (p) p.classList.add('visible');
  }

  function _hideReconnecting() {
    var p = document.getElementById('chat-assistant-reconnecting-pill');
    if (p) p.classList.remove('visible');
  }

  // ── Send / Abort ────────────────────────────────────────────────────────────
  function _updateSendAbortButtons() {
    var sendBtn = document.getElementById('chat-assistant-send');
    var abortBtn = document.getElementById('chat-assistant-abort');
    if (sendBtn) sendBtn.disabled = _streaming;
    if (abortBtn) {
      if (_streaming) {
        abortBtn.classList.remove('hidden');
      } else {
        abortBtn.classList.add('hidden');
      }
    }
  }

  function _sendPrompt() {
    var input = document.getElementById('chat-assistant-input');
    if (!input) return;
    var text = input.value.trim();
    if (!text) return;
    if (!_sid) {
      _createSession();
      return;
    }
    var model = _getSelectedModel();
    var ctx = (!_chipDismissed && _context) ? _context : null;
    var body = { text: text };
    if (model) body.model = model;
    if (ctx) body.context = ctx;

    _appendUserMessage(text);
    input.value = '';
    _closeSlashMenu();

    fetch('/api/chat/sessions/' + _sid + '/prompt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }).catch(function (err) {
      _appendSystemMessage('Send failed: ' + err.message, 'error');
      _streaming = false;
      _updateSendAbortButtons();
    });
  }

  function _abort() {
    if (!_sid) return;
    fetch('/api/chat/sessions/' + _sid + '/abort', { method: 'POST' })
      .catch(function () { /* ignore */ });
  }

  // ── Context % polling ───────────────────────────────────────────────────────
  function _startContextPoll() {
    _stopContextPoll();
    _contextPollTimer = setInterval(function () {
      if (!_sid) return;
      fetch('/api/chat/sessions/' + _sid)
        .then(function (r) { return r.json(); })
        .then(function (data) {
          var pct = data && data.context_pct;
          var el = document.getElementById('chat-assistant-context-pct');
          if (el && typeof pct === 'number') {
            el.textContent = pct + '%';
            el.classList.remove('hidden');
          }
        })
        .catch(function () { /* ignore */ });
    }, 5000);
  }

  function _stopContextPoll() {
    if (_contextPollTimer) {
      clearInterval(_contextPollTimer);
      _contextPollTimer = null;
    }
  }

  // ── Model selector ──────────────────────────────────────────────────────────
  function _getSelectedModel() {
    var sel = document.getElementById('chat-assistant-model');
    return sel ? sel.value : '';
  }

  function _refreshModels() {
    fetch('/api/chat/config')
      .then(function (r) {
        if (!r.ok) return null;
        return r.json();
      })
      .then(function (data) {
        if (!data) return;
        var sel = document.getElementById('chat-assistant-model');
        if (!sel) return;
        sel.classList.remove('hidden');
        var current = sel.value;
        sel.innerHTML = '';
        var models = data.models || [];
        var def = data.default_model || '';
        models.forEach(function (m) {
          var opt = document.createElement('option');
          opt.value = m;
          opt.textContent = m;
          if (m === (current || def)) opt.selected = true;
          sel.appendChild(opt);
        });
        if (!current && def) {
          sel.value = def;
        }
      })
      .catch(function () { /* silently ignore */ });
  }

  function _scheduleModelRefresh() {
    if (_modelRefreshTimer) clearInterval(_modelRefreshTimer);
    _modelRefreshTimer = setInterval(function () {
      if (_isOpen()) _refreshModels();
    }, 30000);
  }

  // ── Skills / slash menu ─────────────────────────────────────────────────────
  function _loadSkills() {
    fetch('/api/chat/skills')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        _skills = data || [];
        _populateSkillsTray(data);
      })
      .catch(function () { /* ignore */ });
  }

  function _populateSkillsTray(items) {
    var skillsList = document.getElementById('chat-assistant-skills-list');
    var cmdsList = document.getElementById('chat-assistant-commands-list');
    if (!skillsList && !cmdsList) return;
    var skills = (items || []).filter(function (i) { return i.kind === 'skill'; });
    var cmds = (items || []).filter(function (i) { return i.kind === 'command'; });

    function renderList(list, container) {
      if (!container) return;
      if (!list.length) {
        container.innerHTML = '<p class="text-xs text-muted-foreground italic">None found.</p>';
        return;
      }
      container.innerHTML = '';
      list.forEach(function (item) {
        var div = document.createElement('div');
        div.className = 'chat-assistant-skill-entry';
        div.innerHTML = '<div class="chat-assistant-skill-name">' + _escHtml(item.name) + '</div>'
          + '<div class="chat-assistant-skill-desc">' + _escHtml(item.description || '') + '</div>';
        container.appendChild(div);
      });
    }

    renderList(skills, skillsList);
    renderList(cmds, cmdsList);
  }

  function _openSlashMenu(filter) {
    var menu = document.getElementById('chat-assistant-slash-menu');
    if (!menu) return;
    var filtered = _skills.filter(function (s) {
      var q = filter.toLowerCase();
      return !q || s.name.toLowerCase().indexOf(q) !== -1 || (s.description || '').toLowerCase().indexOf(q) !== -1;
    });
    if (!filtered.length) {
      menu.classList.add('hidden');
      return;
    }
    menu.innerHTML = '';
    filtered.forEach(function (item, idx) {
      var div = document.createElement('div');
      div.className = 'chat-assistant-slash-item';
      div.setAttribute('role', 'option');
      div.setAttribute('aria-selected', idx === 0 ? 'true' : 'false');
      div.innerHTML = '<span class="chat-assistant-slash-item-name">' + _escHtml(item.name) + '</span>'
        + '<span class="chat-assistant-slash-item-desc">' + _escHtml(item.description || '') + '</span>';
      div.addEventListener('mousedown', function (ev) {
        ev.preventDefault();
        _insertSlashItem(item.name);
      });
      menu.appendChild(div);
    });
    menu.classList.remove('hidden');
  }

  function _closeSlashMenu() {
    var menu = document.getElementById('chat-assistant-slash-menu');
    if (menu) menu.classList.add('hidden');
  }

  function _insertSlashItem(name) {
    var input = document.getElementById('chat-assistant-input');
    if (!input) return;
    input.value = name + ' ';
    input.focus();
    _closeSlashMenu();
  }

  // ── Session history ─────────────────────────────────────────────────────────
  function _loadSessionHistory() {
    fetch('/api/chat/sessions')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var list = document.getElementById('chat-assistant-sessions-list');
        if (!list) return;
        var sessions = data || [];
        if (!sessions.length) {
          list.innerHTML = '<p class="text-xs text-muted-foreground italic">No past sessions.</p>';
          return;
        }
        list.innerHTML = '';
        sessions.forEach(function (s) {
          var div = document.createElement('div');
          div.className = 'chat-assistant-session-entry' + (s.id === _sid ? ' active' : '');
          var dateStr = s.created_at ? new Date(s.created_at).toLocaleString() : '';
          div.innerHTML = '<div class="font-mono truncate">' + _escHtml(s.id || '') + '</div>'
            + '<div class="chat-assistant-session-date">' + _escHtml(dateStr) + '</div>';
          div.addEventListener('click', function () {
            switchSession(s.id);
            _hideHistoryDropdown();
          });
          list.appendChild(div);
        });
      })
      .catch(function () { /* ignore */ });
  }

  function _hideHistoryDropdown() {
    var dd = document.getElementById('chat-assistant-history-dropdown');
    if (dd) dd.classList.add('hidden');
  }

  // ── Escape HTML ─────────────────────────────────────────────────────────────
  function _escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // ── Ctrl+/ keybinding ───────────────────────────────────────────────────────
  // Note: the existing Code Q&A chat uses Cmd+\ (backslash) — no collision.
  document.addEventListener('keydown', function (e) {
    if (e.ctrlKey && e.key === '/') {
      e.preventDefault();
      toggle();
    }
  });

  // ── Wire up DOM events on DOMContentLoaded ──────────────────────────────────
  document.addEventListener('DOMContentLoaded', function () {
    // Restore open/closed state from cookie
    var saved = _getCookie('iw-chat-assistant-open');
    if (saved === '1') {
      _applyOpenState(true);
    }

    // Collapse button
    var collapseBtn = document.getElementById('chat-assistant-collapse-btn');
    if (collapseBtn) {
      collapseBtn.addEventListener('click', function () { close(); });
    }

    // Expand rail
    var rail = document.getElementById('chat-assistant-expand-rail');
    if (rail) {
      rail.addEventListener('click', function () { open(); });
    }

    // Nav toggle button (in top bar)
    var navToggle = document.getElementById('chat-assistant-nav-toggle');
    if (navToggle) {
      navToggle.addEventListener('click', function () { toggle(); });
    }

    // New chat button
    var newBtn = document.getElementById('chat-assistant-new-btn');
    if (newBtn) {
      newBtn.addEventListener('click', function () { newSession(); });
    }

    // Send button
    var sendBtn = document.getElementById('chat-assistant-send');
    if (sendBtn) {
      sendBtn.addEventListener('click', function () { _sendPrompt(); });
    }

    // Abort button
    var abortBtn = document.getElementById('chat-assistant-abort');
    if (abortBtn) {
      abortBtn.addEventListener('click', function () { _abort(); });
    }

    // Textarea: Enter sends, Ctrl+Enter also sends, / triggers slash menu
    var input = document.getElementById('chat-assistant-input');
    if (input) {
      input.addEventListener('keydown', function (e) {
        // Cmd/Ctrl+Enter sends
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
          e.preventDefault();
          _sendPrompt();
          return;
        }
        // Enter (without Shift) sends
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          _sendPrompt();
          return;
        }
        // Escape closes slash menu
        if (e.key === 'Escape') {
          _closeSlashMenu();
        }
      });

      input.addEventListener('input', function () {
        var val = input.value;
        if (val.startsWith('/')) {
          var filter = val.slice(1);
          _openSlashMenu(filter);
        } else {
          _closeSlashMenu();
        }
      });
    }

    // Skills tray toggle
    var trayToggle = document.getElementById('chat-assistant-tray-toggle');
    if (trayToggle) {
      trayToggle.addEventListener('click', function () {
        var tray = document.getElementById('chat-assistant-skills-tray');
        if (tray) {
          var hidden = tray.classList.toggle('hidden');
          if (!hidden) {
            _loadSkills();
          }
        }
      });
    }

    // History dropdown toggle
    var histToggle = document.getElementById('chat-assistant-history-toggle');
    if (histToggle) {
      histToggle.addEventListener('click', function () {
        var dd = document.getElementById('chat-assistant-history-dropdown');
        if (dd) {
          var hidden = dd.classList.toggle('hidden');
          if (!hidden) {
            _loadSessionHistory();
          }
        }
      });
    }

    // Model selector change: update per-session default
    var modelSel = document.getElementById('chat-assistant-model');
    if (modelSel) {
      modelSel.addEventListener('change', function () {
        // Model change applies to next prompt only; no abort of in-flight run.
        // No extra action needed — _getSelectedModel() reads it at send time.
      });
    }

    // Initial model load if panel is open
    if (_isOpen()) {
      _refreshModels();
      _ensureSession();
    }

    _scheduleModelRefresh();
  });

})();

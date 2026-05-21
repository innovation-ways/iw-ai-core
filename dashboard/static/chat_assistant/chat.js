// dashboard/static/chat_assistant/chat.js
// Dashboard AI Assistant — window.iwChat API (F-00086 tab-scoped rewrite)
// Ctrl+/ keybinding (no collision with Cmd+\ used by the existing Code Q&A chat).
// All DOM ids are prefixed chat-assistant- to avoid collisions.
(function () {
  'use strict';

  // ── Per-page browser-tab identity (for sessionStorage namespace only) ────────
  // This is the *browser* tab id, not the chat-tab id. Used to scope
  // sessionStorage keys so two browser tabs don't clobber each other.
  var _browserTabId = sessionStorage.getItem('iw-chat-browser-tab-id');
  if (!_browserTabId) {
    try {
      _browserTabId = crypto.randomUUID();
    } catch (_e) {
      _browserTabId = Date.now().toString(36) + Math.random().toString(36).slice(2);
    }
    sessionStorage.setItem('iw-chat-browser-tab-id', _browserTabId);
  }

  // ── Chat-tab state ───────────────────────────────────────────────────────────
  // _tabs: Array of tab objects from the API { id, title, model, runtime, status, ... }
  // _activeTabId: string | null
  // Per-tab EventSource map: _tabEs[tabId] = EventSource | null
  // Per-tab seen-event-id map: _tabSeenIds[tabId] = {}
  // Per-tab streaming flag: _tabStreaming[tabId] = bool

  var _tabs = [];
  var _activeTabId = null;
  var _tabEs = {};
  var _tabSeenIds = {};
  var _tabStreaming = {};
  var _tabRetryTimers = {};
  var _tabRetryCount = {};
  var _tabHasHistory = {};

  // Per-tab assistant message rendering state
  var _tabCurrentAssistantEl = {};
  var _tabCurrentAssistantId = {};

  // Global panel state
  var _contextPollTimer = null;
  var _modelRefreshTimer = null;
  var _lastProjectId = null;
  var _projectDirectory = '';
  var _projectDirectoryProjectId = null;
  var _context = null;
  var _chipDismissed = false;
  var _skills = [];
  var _pendingPermissions = {};

  // Modal-local models

  // Modal-local models: populated from /api/chat/config?runtime=<selected> each
  // time the user opens the modal or changes the runtime dropdown.
  var _modalModels = [];
  var _modalDefaultModel = '';
  // Tracks which runtime the modal dropdown last fetched models for, so a second
  // open without a runtime change skips the fetch.
  var _modalRuntime = 'opencode';

  // Default model for new tabs (kept so _instantCreateTab() can pick the right default).
  var _defaultModel = '';

  // Soft-cap banner: once shown (per page session), re-shows on each POST that returns the header
  // (but can be dismissed once per show). The flag tracks whether it's currently visible.
  var _softCapBannerVisible = false;

  // Context-menu state
  var _ctxMenuTabId = null;

  // Settings panel state
  var _settingsOriginalRuntime = null;

  // ── Cookie helpers ──────────────────────────────────────────────────────────
  function _setCookie(name, value, path) {
    document.cookie = name + '=' + value + '; path=' + (path || '/');
  }

  function _getCookie(name) {
    var m = document.cookie.match('(?:^|; )' + name + '=([^;]*)');
    return m ? m[1] : null;
  }

  function _currentProjectId() {
    // /project/{id}, /project/{id}/, /project/{id}/... -> id; everything else -> null
    var m = /^\/project\/([^\/]+)(?:\/|$)/.exec(window.location.pathname);
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
      _bootstrapTabs();
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

  window.iwChat = {
    open: open,
    close: close,
    toggle: toggle,
    setContext: setContext,
    clearContext: clearContext,
    openWith: openWith
  };

  // ── Tab bootstrap / fetch ───────────────────────────────────────────────────
  function _bootstrapTabs() {
    var projectId = _currentProjectId();
    if (!projectId) {
      // No per-project context; render empty state
      _renderEmptyNoTabs();
      return;
    }
    _fetchTabs(projectId, function (tabs) {
      if (!tabs.length) {
        // First load: retry once after 100ms (server may still be seeding the default tab)
        setTimeout(function () {
          _fetchTabs(projectId, function (tabs2) {
            _tabs = tabs2;
            _renderTabStrip();
            if (_tabs.length) {
              var lastActive2 = sessionStorage.getItem('iw-chat-active-tab-' + _browserTabId);
              var target2 = lastActive2 && _tabs.find(function (t) { return t.id === lastActive2; });
              if (!target2 && _tabs.length > 1) {
                target2 = _tabs.reduce(function (best, t) {
                  if (!best) return t;
                  var bestTs = best.last_active_at ? new Date(best.last_active_at).getTime() : 0;
                  var tTs = t.last_active_at ? new Date(t.last_active_at).getTime() : 0;
                  return tTs > bestTs ? t : best;
                }, null);
              }
              _activateTab(target2 ? target2.id : _tabs[0].id);
            } else {
              _renderEmptyNoTabs();
            }
          });
        }, 100);
        return;
      }
      _tabs = tabs;
      _renderTabStrip();
      // Restore last active tab from sessionStorage
      var lastActive = sessionStorage.getItem('iw-chat-active-tab-' + _browserTabId);
      var target = lastActive && _tabs.find(function (t) { return t.id === lastActive; });
      if (!target && _tabs.length > 1) {
        // sessionStorage cleared — restore the most recently active tab
        target = _tabs.reduce(function (best, t) {
          if (!best) return t;
          var bestTs = best.last_active_at ? new Date(best.last_active_at).getTime() : 0;
          var tTs = t.last_active_at ? new Date(t.last_active_at).getTime() : 0;
          return tTs > bestTs ? t : best;
        }, null);
      }
      _activateTab(target ? target.id : _tabs[0].id);
    });
  }

  function _fetchTabs(projectId, cb) {
    var url = '/api/chat/tabs?' + new URLSearchParams({ project_id: projectId }).toString();
    fetch(url)
      .then(function (r) {
        if (!r.ok) throw new Error('list tabs: ' + r.status);
        return r.json();
      })
      .then(function (data) {
        cb((data && data.tabs) || []);
      })
      .catch(function (err) {
        _appendSystemMessage('Could not load chat tabs: ' + err.message, 'error');
        cb([]);
      });
  }

  // ── Tab activation ──────────────────────────────────────────────────────────
  function _activateTab(tabId) {
    if (_activeTabId === tabId) return;
    _closeSettingsPanel();

    // DELIBERATELY leave the previous tab's EventSource open. Disconnecting
    // it would force a ring-buffer replay on reconnect: all missed events
    // would arrive instantly and the stream would appear complete the moment
    // the user came back — defeating the V5 multi-tab abort scenario
    // ("switch away while Tab A is streaming, switch back, click Abort
    // while Tab A is still streaming"). Background events still update
    // `_tabStreaming[oldId]` so per-tab Send/Abort gating stays correct;
    // the rendering helpers gate on `tabId === _activeTabId` so background
    // tabs don't paint into the visible message area.

    _activeTabId = tabId;
    sessionStorage.setItem('iw-chat-active-tab-' + _browserTabId, tabId);

    // Update tab strip highlighting
    _updateTabStripActiveState();

    // Clear messages and reload for new tab
    _clearMessages();
    _resetAssistantState();

    // Ensure composer is visible (may have been hidden in no-tabs state)
    _showComposer();

    // Load history + start stream for new tab.
    var tab = _tabs.find(function (t) { return t.id === tabId; });
    if (tab && tab.opencode_session_id) {
      _loadTabHistory(tabId);
      // Only open a new EventSource if we don't already have one open for
      // this tab from a prior activation. Re-using avoids the ring-buffer
      // replay-burst that would otherwise compress 30s of streaming into a
      // single frame.
      if (!_tabEs[tabId]) {
        _connectStream(tabId);
      }
    } else if (tab) {
      // Tab exists but has no session yet — show empty state
      _showEmptyState();
    }

    // Refresh models for the model dropdown
    _refreshModels();

    // Sync the composer's Send/Abort state to the newly-active tab's
    // streaming flag.
    _updateSendAbortButtons();
    _updateClearButton();

    // Show context % immediately on tab activation (no waiting for a message)
    _refreshContextPct(tabId);
  }

  // ── SSE per-tab streaming ───────────────────────────────────────────────────
  // NOTE: EventSource only dispatches to listeners whose names appear in this
  // list (default 'message' aside). Pi-runtime events (F-00087) are normalised
  // to 'message.part.added' / 'session.start' / 'tool.execution.*' — these
  // MUST be enumerated here or the browser silently drops them.
  var NAMED_EVENTS = [
    'message.part.updated',
    'message.part.added',
    'tool.execute.before',
    'tool.execute.after',
    'tool.execution.start',
    'tool.execution.update',
    'tool.execution.end',
    'permission.asked',
    'permission.replied',
    'session.start',
    'session.idle',
    'session.updated',
    'session.error',
    'message.part.delta',
    'message.updated',
    'message.part.removed',
    'message.removed',
    'session.status',
    'gap',
    'reconnecting',
    'error',
    'relay.error'
  ];

  function _connectStream(tabId) {
    _teardownStream(tabId);
    var lastId = _getLastEventId(tabId);
    var url = '/api/chat/tabs/' + encodeURIComponent(tabId) + '/stream';
    if (lastId) {
      url += '?last_event_id=' + encodeURIComponent(lastId);
    }
    var es = new EventSource(url);
    _tabEs[tabId] = es;

    es.onopen = function () {
      if (tabId === _activeTabId) {
        _hideReconnecting();
      }
    };

    es.onerror = function () {
      if (tabId === _activeTabId) {
        _showReconnecting();
      }
      // Exponential backoff retry
      _scheduleStreamRetry(tabId);
    };

    es.onmessage = function (e) {
      _handleEvent(tabId, 'message', e);
    };

    NAMED_EVENTS.forEach(function (evName) {
      es.addEventListener(evName, function (e) {
        _handleEvent(tabId, evName, e);
      });
    });
  }

  function _teardownStream(tabId) {
    // Close the client EventSource. The server-side opencode session may
    // still be mid-stream — we deliberately do NOT clear `_tabStreaming`
    // here, because:
    //   * On tab-switch, the user comes back later and reconnects via
    //     `_connectStream`; the Abort button must remain reachable
    //     immediately (V5).
    //   * On true completion (session.idle), the dedicated handler in
    //     `_handleEvent` already clears the flag.
    //   * On tab-close, the caller (`_closeTab`) wipes the per-tab
    //     bookkeeping including the streaming flag.
    if (_tabEs[tabId]) {
      _tabEs[tabId].close();
      _tabEs[tabId] = null;
    }
    if (_tabRetryTimers[tabId]) {
      clearTimeout(_tabRetryTimers[tabId]);
      _tabRetryTimers[tabId] = null;
    }
    if (tabId === _activeTabId) {
      _stopContextPoll();
      _updateSendAbortButtons();
    }
  }

  function _scheduleStreamRetry(tabId) {
    if (_tabRetryTimers[tabId]) return; // already scheduled
    var count = _tabRetryCount[tabId] || 0;
    _tabRetryCount[tabId] = count + 1;
    var delay = Math.min(30000, 1000 * Math.pow(2, count));
    _tabRetryTimers[tabId] = setTimeout(function () {
      _tabRetryTimers[tabId] = null;
      if (_tabEs[tabId]) {
        _tabEs[tabId].close();
        _tabEs[tabId] = null;
      }
      // Only reconnect if this tab is still active or in our tabs list
      var stillKnown = _tabs.some(function (t) { return t.id === tabId; });
      if (stillKnown) {
        _connectStream(tabId);
      }
    }, delay);
  }

  function _getLastEventId(tabId) {
    return sessionStorage.getItem('iw-chat-last-eid-' + tabId) || null;
  }

  function _setLastEventId(tabId, eid) {
    if (eid) {
      sessionStorage.setItem('iw-chat-last-eid-' + tabId, eid);
    }
  }

  // ── Event handler ───────────────────────────────────────────────────────────
  function _handleEvent(tabId, evName, e) {
    // Defensive: ignore events that belong to a different tab
    // (relay already sets tab_id on every event)
    if (e.lastEventId) {
      _setLastEventId(tabId, e.lastEventId);
    }

    // Client-side dedup per tab
    var eid = e.lastEventId || null;
    if (!_tabSeenIds[tabId]) _tabSeenIds[tabId] = {};
    if (eid) {
      if (_tabSeenIds[tabId][eid]) return;
      _tabSeenIds[tabId][eid] = true;
    }

    // Parse data
    var data = null;
    try {
      data = JSON.parse(e.data);
    } catch (_pe) {
      data = { text: e.data };
    }

    // Defensive: check tab_id field if present
    if (data && data.tab_id && data.tab_id !== tabId) {
      console.warn('[iwChat] Ignoring event with mismatched tab_id:', data.tab_id, '!== active:', tabId);
      return;
    }

    // Only render to DOM if this is the active tab
    var isActive = (tabId === _activeTabId);

    // Extract opencode `properties`
    var props = (data && data.properties) || null;

    // ── relay-synthesised events ─────────────────────────────────────────────
    if (evName === 'gap') {
      if (isActive) _appendGapWarning();
      return;
    }
    if (evName === 'reconnecting') {
      if (isActive) _showReconnecting();
      return;
    }
    if (evName === 'error' || evName === 'relay.error') {
      if (isActive) {
        var msg = (data && data.message) || 'An error occurred.';
        _appendSystemMessage(msg, 'error');
      }
      _tabStreaming[tabId] = false;
      if (isActive) {
        _stopContextPoll();
        _updateSendAbortButtons();
      }
      return;
    }

    // ── opencode-native events ───────────────────────────────────────────────

    if (evName === 'message.part.delta') {
      if (!_tabStreaming[tabId]) {
        _tabStreaming[tabId] = true;
        if (isActive) {
          _updateSendAbortButtons();
          _startContextPoll();
        }
      }
      _tabHasHistory[tabId] = true;
      _updateClearButton();
      if (isActive) {
        var deltaText = (props && props.delta) || '';
        var deltaKey = (props && props.messageID) || eid;
        _appendOrUpdateAssistantMessage(tabId, deltaKey, deltaText, false);
      }
      return;
    }

    if (evName === 'message.part.updated') {
      if (!_tabStreaming[tabId]) {
        _tabStreaming[tabId] = true;
        if (isActive) {
          _updateSendAbortButtons();
          _startContextPoll();
        }
      }
      _tabHasHistory[tabId] = true;
      _updateClearButton();
      if (isActive) {
        var partText = (props && props.delta) ||
                       (props && props.part && props.part.text) || '';
        var partKey = (props && props.part && props.part.messageID) ||
                      (props && props.messageID) || eid;
        _appendOrUpdateAssistantMessage(tabId, partKey, partText, false);
      }
      return;
    }

    // F-00087: Pi-runtime streaming text. The Pi event_normalizer maps
    // `message_update`+`text_delta` → `message.part.added` with shape
    // `{data: {part: {type: "text", text: <delta>}}}` (no `properties`
    // wrapper — that is an OpenCode-specific shape). Render the delta into
    // the active assistant bubble identically to message.part.updated.
    if (evName === 'message.part.added') {
      if (!_tabStreaming[tabId]) {
        _tabStreaming[tabId] = true;
        if (isActive) {
          _updateSendAbortButtons();
          _startContextPoll();
        }
      }
      _tabHasHistory[tabId] = true;
      _updateClearButton();
      if (isActive) {
        var addedPart = (data && data.part) || (props && props.part) || {};
        var addedText = (typeof addedPart.text === 'string' ? addedPart.text : '') ||
                        (props && props.delta) || '';
        var addedKey = addedPart.messageID ||
                       (props && props.messageID) || eid;
        _appendOrUpdateAssistantMessage(tabId, addedKey, addedText, false);
      }
      return;
    }

    if (evName === 'message.part.removed') {
      return; // No individual part nodes to remove
    }

    if (evName === 'message.updated') {
      var info = props && props.info;
      if (!info) return;
      if (info.role === 'assistant') {
        if (info.time && info.time.completed) {
          if (isActive) _finaliseLastAssistantMessage(tabId);
          _tabStreaming[tabId] = false;
          if (isActive) {
            _stopContextPoll();
            _updateSendAbortButtons();
          }
        }
        if (info.error) {
          if (isActive) {
            var errMsg = (info.error && info.error.message) || 'Assistant error.';
            _appendSystemMessage(errMsg, 'error');
          }
          _tabStreaming[tabId] = false;
          if (isActive) {
            _stopContextPoll();
            _updateSendAbortButtons();
          }
        }
      }
      return;
    }

    if (evName === 'message.removed') {
      return; // No targeted removal in this implementation
    }

    if (evName === 'tool.execute.before') {
      if (isActive) {
        var toolName = (props && props.tool) || 'unknown';
        _appendToolCall(toolName, {});
      }
      return;
    }

    if (evName === 'tool.execute.after') {
      if (isActive) {
        var doneToolName = (props && props.tool) || '';
        _appendToolResult('✓ ' + doneToolName + (props && props.duration ? ' (' + props.duration + 'ms)' : ''));
      }
      return;
    }

    // F-00087: Pi-runtime tool lifecycle. Pi's event_normalizer maps
    // tool_execution_start/update/end → tool.execution.start/update/end
    // with shape `{data: {tool, args, ...}}` (no `properties` wrapper).
    if (evName === 'tool.execution.start') {
      if (isActive) {
        var piToolName = (data && data.tool) || (props && props.tool) || 'unknown';
        var piToolArgs = (data && data.args) || (props && props.args) || {};
        _appendToolCall(piToolName, piToolArgs);
      }
      return;
    }

    if (evName === 'tool.execution.update') {
      return; // no streaming progress bubble in v1
    }

    if (evName === 'tool.execution.end') {
      if (isActive) {
        var piDoneTool = (data && data.tool) || (props && props.tool) || '';
        var piResult = (data && data.result);
        if (piResult === undefined && props) piResult = props.result;
        var label = piDoneTool ? ('✓ ' + piDoneTool) : '✓ tool';
        if (piResult !== undefined && piResult !== null && piResult !== '') {
          _appendToolResult(label + ' — ' + (typeof piResult === 'string' ? piResult : JSON.stringify(piResult)));
        } else {
          _appendToolResult(label);
        }
      }
      return;
    }

    // F-00087: Pi emits `agent_start` → `session.start`. No visible bubble,
    // but mark the tab as streaming so Send/Abort state flips correctly even
    // before the first text delta arrives.
    if (evName === 'session.start') {
      if (!_tabStreaming[tabId]) {
        _tabStreaming[tabId] = true;
        if (isActive) {
          _updateSendAbortButtons();
          _startContextPoll();
        }
      }
      _tabHasHistory[tabId] = true;
      _updateClearButton();
      return;
    }

    if (evName === 'permission.asked') {
      var permData = props || data;
      var rid = (permData && permData.id) || (permData && permData.request_id);
      if (rid) {
        _pendingPermissions[rid] = { data: permData, tabId: tabId };
        if (isActive) _showApprovalModal(permData, tabId);
      }
      return;
    }

    if (evName === 'permission.replied') {
      if (isActive) {
        var repliedRoot = document.getElementById('chat-assistant-approval-root');
        if (repliedRoot) repliedRoot.innerHTML = '';
      }
      return;
    }

    if (evName === 'session.idle') {
      _tabStreaming[tabId] = false;
      if (isActive) {
        _finaliseLastAssistantMessage(tabId);
        _stopContextPoll();
        _updateSendAbortButtons();
        var idleProps = props || data;
        if (idleProps && idleProps.permission_denied) {
          _appendSystemMessage('Run aborted (permission denied).', 'info');
        } else if (idleProps && idleProps.aborted) {
          _appendSystemMessage('Run aborted.', 'info');
        } else {
          _appendSystemMessage('Session idle.', 'info');
        }
      }
      return;
    }

    if (evName === 'session.status') {
      var status = props && props.status;
      if (status && status.type === 'busy' && !_tabStreaming[tabId]) {
        _tabStreaming[tabId] = true;
        if (isActive) {
          _updateSendAbortButtons();
          _startContextPoll();
        }
      } else if (status && status.type === 'idle' && _tabStreaming[tabId]) {
        _tabStreaming[tabId] = false;
        if (isActive) {
          _stopContextPoll();
          _updateSendAbortButtons();
        }
      }
      return;
    }

    if (evName === 'session.error') {
      if (isActive) {
        var sessErr = (props && props.error) || null;
        var sessErrMsg = (sessErr && sessErr.message) ||
                         (sessErr && sessErr.data && sessErr.data.message) ||
                         'Session error.';
        _appendSystemMessage(sessErrMsg, 'error');
      }
      _tabStreaming[tabId] = false;
      if (isActive) {
        _stopContextPoll();
        _updateSendAbortButtons();
      }
      return;
    }

    if (evName === 'session.updated') {
      return; // No visible bubble needed
    }
  }

  // ── Approval modal ──────────────────────────────────────────────────────────
  function _showApprovalModal(data, tabId) {
    var root = document.getElementById('chat-assistant-approval-root');
    if (!root) return;

    var toolName = data.permission || data.tool || data.tool_name || 'unknown';
    var args = data.patterns || data.args || data.arguments || [];
    var argsStr = '';
    try {
      argsStr = typeof args === 'string' ? args : JSON.stringify(args, null, 2);
    } catch (_e) {
      argsStr = String(args);
    }
    var rationale = data.rationale || data.reason || '';
    var rid = data.id || data.request_id || data.rid || '';

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
        _replyPermission(tabId, rid, 'allow', root);
      });
    }
    if (denyBtn) {
      denyBtn.addEventListener('click', function () {
        _replyPermission(tabId, rid, 'deny', root);
      });
    }
  }

  function _replyPermission(tabId, rid, decision, root) {
    if (!tabId || !rid) return;
    var remember = false;
    var cb = document.getElementById('chat-assistant-approval-remember');
    if (cb) remember = cb.checked;
    fetch('/api/chat/tabs/' + encodeURIComponent(tabId) + '/permissions/' + encodeURIComponent(rid), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ response: decision, remember: remember })
    }).catch(function (err) {
      _appendSystemMessage('Permission reply failed: ' + err.message, 'error');
    });
    delete _pendingPermissions[rid];
    if (root) root.innerHTML = '';
  }

  // ── Tab strip rendering ─────────────────────────────────────────────────────
  function _renderTabStrip() {
    var strip = document.getElementById('chat-assistant-tab-strip');
    var wrap = document.getElementById('chat-assistant-tab-strip-wrap');
    if (!strip) return;

    if (!_tabs.length) {
      if (wrap) wrap.style.display = 'none';
      return;
    }
    if (wrap) wrap.style.display = '';

    strip.innerHTML = '';
    _tabs.forEach(function (tab) {
      strip.appendChild(_buildTabButton(tab));
    });

    // "+" add-tab button at end of the strip (Notepad++-style)
    var addBtn = document.createElement('button');
    addBtn.type = 'button';
    addBtn.id = 'chat-assistant-tab-add-btn';
    addBtn.className = 'chat-assistant-tab-add-btn flex-shrink-0 inline-flex items-center justify-center px-2 text-muted-foreground hover:bg-muted hover:text-foreground';
    addBtn.setAttribute('aria-label', 'New chat tab');
    addBtn.setAttribute('title', 'New chat tab');
    addBtn.textContent = '+';
    addBtn.addEventListener('click', function () { _instantCreateTab(); });
    strip.appendChild(addBtn);
  }

  function _buildTabButton(tab) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'chat-assistant-tab-btn flex-shrink-0 flex items-center gap-1 px-2 py-1.5 text-xs border-r border-border hover:bg-muted';
    btn.setAttribute('role', 'tab');
    btn.setAttribute('data-tab-id', tab.id);
    btn.setAttribute('data-runtime', tab.runtime || 'opencode');
    btn.setAttribute('aria-selected', tab.id === _activeTabId ? 'true' : 'false');
    btn.title = tab.title || 'Chat';
    if (tab.id === _activeTabId) {
      btn.classList.add('chat-assistant-tab-btn-active');
    }

    // Title span
    var titleSpan = document.createElement('span');
    titleSpan.className = 'chat-assistant-tab-title';
    titleSpan.textContent = _truncateStr(tab.title || 'Chat', 20);

    // Model badge
    var modelBadge = document.createElement('span');
    modelBadge.className = 'chat-assistant-tab-model-badge';
    modelBadge.textContent = _modelShortName(tab.model || '');
    modelBadge.title = tab.model || '';

    // Close button
    var closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'chat-assistant-tab-close-btn';
    closeBtn.setAttribute('aria-label', 'Close tab: ' + (tab.title || 'Chat'));
    closeBtn.innerHTML = '&#x2715;';

    btn.appendChild(titleSpan);
    btn.appendChild(modelBadge);
    btn.appendChild(closeBtn);

    // Activate on click (not on close button)
    btn.addEventListener('click', function (e) {
      if (e.target === closeBtn || closeBtn.contains(e.target)) return;
      _activateTab(tab.id);
    });

    // Close on close button click
    closeBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      _closeTab(tab.id);
    });

    // Right-click context menu
    btn.addEventListener('contextmenu', function (e) {
      e.preventDefault();
      _showTabContextMenu(tab.id, e.clientX, e.clientY);
    });

    // Double-click inline rename
    titleSpan.addEventListener('dblclick', function (e) {
      e.stopPropagation();
      _startInlineRename(tab.id, titleSpan);
    });

    return btn;
  }

  function _updateTabStripActiveState() {
    var buttons = document.querySelectorAll('#chat-assistant-tab-strip .chat-assistant-tab-btn');
    buttons.forEach(function (btn) {
      var id = btn.getAttribute('data-tab-id');
      if (id === _activeTabId) {
        btn.classList.add('chat-assistant-tab-btn-active');
        btn.setAttribute('aria-selected', 'true');
      } else {
        btn.classList.remove('chat-assistant-tab-btn-active');
        btn.setAttribute('aria-selected', 'false');
      }
    });
  }

  function _updateTabButtonLabel(tabId, title, model) {
    var btn = document.querySelector('#chat-assistant-tab-strip .chat-assistant-tab-btn[data-tab-id="' + tabId + '"]');
    if (!btn) return;
    var titleSpan = btn.querySelector('.chat-assistant-tab-title');
    var modelBadge = btn.querySelector('.chat-assistant-tab-model-badge');
    var closeBtn = btn.querySelector('.chat-assistant-tab-close-btn');
    if (titleSpan && title !== undefined) {
      titleSpan.textContent = _truncateStr(title || 'Chat', 20);
      btn.title = title || 'Chat';
      if (closeBtn) closeBtn.setAttribute('aria-label', 'Close tab: ' + (title || 'Chat'));
    }
    if (modelBadge && model !== undefined) {
      modelBadge.textContent = _modelShortName(model || '');
      modelBadge.title = model || '';
    }
  }

  // ── Inline rename ───────────────────────────────────────────────────────────
  function _startInlineRename(tabId, titleSpan) {
    var currentTitle = titleSpan.textContent;
    var tab = _tabs.find(function (t) { return t.id === tabId; });
    var fullTitle = tab ? (tab.title || '') : currentTitle;

    var input = document.createElement('input');
    input.type = 'text';
    input.className = 'chat-assistant-tab-rename-input';
    input.value = fullTitle;
    input.maxLength = 20;

    titleSpan.parentNode.insertBefore(input, titleSpan);
    titleSpan.style.display = 'none';
    input.focus();
    input.select();

    function _commit() {
      var newTitle = input.value.trim() || fullTitle;
      titleSpan.style.display = '';
      if (input.parentNode) input.parentNode.removeChild(input);
      if (newTitle !== fullTitle) {
        _renameTab(tabId, newTitle);
      }
    }

    function _cancel() {
      titleSpan.style.display = '';
      if (input.parentNode) input.parentNode.removeChild(input);
    }

    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        _commit();
      } else if (e.key === 'Escape') {
        _cancel();
      }
    });
    input.addEventListener('blur', function () {
      _commit();
    });
  }

  function _renameTab(tabId, newTitle) {
    fetch('/api/chat/tabs/' + encodeURIComponent(tabId), {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: newTitle })
    })
      .then(function (r) {
        if (!r.ok) throw new Error('rename failed: ' + r.status);
        return r.json();
      })
      .then(function (data) {
        var updated = data && data.tab;
        if (!updated) return;
        var idx = _tabs.findIndex(function (t) { return t.id === tabId; });
        if (idx !== -1) _tabs[idx] = updated;
        _updateTabButtonLabel(tabId, updated.title, undefined);
      })
      .catch(function (err) {
        _appendSystemMessage('Rename failed: ' + err.message, 'error');
      });
  }

  // ── Context menu ────────────────────────────────────────────────────────────
  function _showTabContextMenu(tabId, x, y) {
    _ctxMenuTabId = tabId;
    var menu = document.getElementById('chat-assistant-tab-context-menu');
    if (!menu) return;
    menu.style.left = x + 'px';
    menu.style.top = y + 'px';
    menu.classList.remove('hidden');
  }

  function _hideTabContextMenu() {
    var menu = document.getElementById('chat-assistant-tab-context-menu');
    if (menu) menu.classList.add('hidden');
    _ctxMenuTabId = null;
  }

  // ── Close / reopen tabs ─────────────────────────────────────────────────────
  function _closeTab(tabId) {
    fetch('/api/chat/tabs/' + encodeURIComponent(tabId), { method: 'DELETE' })
      .then(function (r) {
        if (!r.ok && r.status !== 204) throw new Error('close tab: ' + r.status);
        _teardownStream(tabId);
        // Wipe per-tab bookkeeping; the tab is gone server-side too.
        delete _tabStreaming[tabId];
        delete _tabSeenIds[tabId];
        delete _tabRetryCount[tabId];
        delete _tabCurrentAssistantEl[tabId];
        delete _tabCurrentAssistantId[tabId];
        _tabs = _tabs.filter(function (t) { return t.id !== tabId; });
        if (_activeTabId === tabId) {
          _activeTabId = null;
        }
        _renderTabStrip();
        if (_tabs.length && _activeTabId === null) {
          _activateTab(_tabs[0].id);
        } else if (!_tabs.length) {
          _activeTabId = null;
          _clearMessages();
          _renderEmptyNoTabs();
          // No active tab — hide stale context %
          _refreshContextPct(null);
        }
      })
      .catch(function (err) {
        _appendSystemMessage('Could not close tab: ' + err.message, 'error');
      });
  }

  function _reopenTab(tabId) {
    fetch('/api/chat/tabs/' + encodeURIComponent(tabId) + '/reopen', { method: 'POST' })
      .then(function (r) {
        if (!r.ok) throw new Error('reopen tab: ' + r.status);
        return r.json();
      })
      .then(function (data) {
        var tab = data && data.tab;
        if (!tab) return;
        _tabs.push(tab);
        _renderTabStrip();
        _activateTab(tab.id);
        _hideClosedTabsDropdown();
      })
      .catch(function (err) {
        _appendSystemMessage('Could not reopen tab: ' + err.message, 'error');
      });
  }

  function _duplicateTab(tabId) {
    var tab = _tabs.find(function (t) { return t.id === tabId; });
    if (!tab) return;
    var projectId = _currentProjectId() || tab.project_id;
    _createTab(projectId, tab.runtime || 'opencode', tab.model || '', (tab.title || 'Chat') + ' (copy)');
  }

  // ── Create tab ──────────────────────────────────────────────────────────────
  function _createTab(projectId, runtime, model, title) {
    var body = { project_id: projectId };
    if (runtime) body.runtime = runtime;
    if (model) body.model = model;
    if (title) body.title = title;

    fetch('/api/chat/tabs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
      .then(function (r) {
        // Check soft-cap header before reading body
        var softCap = r.headers.get('X-Tab-Soft-Cap-Exceeded');
        return r.json().then(function (data) {
          return { data: data, status: r.status, softCap: softCap };
        });
      })
      .then(function (res) {
        if (res.status === 503) {
          _appendSystemMessage('Runtime unavailable; try again later.', 'error');
          return;
        }
        if (res.status >= 400) {
          var errMsg = (res.data && res.data.error)
            || (res.data && Array.isArray(res.data.detail) && res.data.detail[0] && res.data.detail[0].msg)
            || ('Error ' + res.status);
          _appendSystemMessage(errMsg, 'error');
          return;
        }
        var tab = res.data && res.data.tab;
        if (!tab) return;
        if (res.softCap === 'true') {
          _showSoftCapBanner();
        }
        _tabs.push(tab);
        _renderTabStrip();
        _activateTab(tab.id);
      })
      .catch(function (err) {
        _appendSystemMessage('Network error: ' + err.message, 'error');
      });
  }

  // ── Instant tab creation (Notepad++-style, no modal) ────────────────────────
  function _instantCreateTab() {
    var projectId = _currentProjectId();
    if (!projectId) {
      _appendSystemMessage('Navigate to a project page first to create a chat tab.', 'error');
      return;
    }
    var activeTab = _activeTabId ? _tabs.find(function (t) { return t.id === _activeTabId; }) : null;
    var runtime = (activeTab && activeTab.runtime) || 'opencode';
    var model = (activeTab && activeTab.model) || _defaultModel || '';
    // Auto-increment title: "Chat 1", "Chat 2", ...
    var n = _tabs.length + 1;
    var title = 'Chat ' + n;
    while (_tabs.some(function (t) { return (t.title || '') === title; })) {
      n++;
      title = 'Chat ' + n;
    }
    _createTab(projectId, runtime, model, title);
  }

  // ── Settings panel ────────────────────────────────────────────────────────────
  function _openSettingsPanel() {
    if (!_activeTabId) return;
    _loadSettingsPanel();
    var panel = document.getElementById('chat-assistant-settings-panel');
    if (panel) panel.classList.remove('hidden');
  }

  function _closeSettingsPanel() {
    var panel = document.getElementById('chat-assistant-settings-panel');
    if (panel) panel.classList.add('hidden');
    var warn = document.getElementById('chat-assistant-settings-warn');
    if (warn) warn.classList.add('hidden');
    var err = document.getElementById('chat-assistant-settings-error');
    if (err) err.classList.add('hidden');
  }

  function _loadSettingsPanel() {
    var tab = _activeTabId ? _tabs.find(function (t) { return t.id === _activeTabId; }) : null;
    if (!tab) return;
    _settingsOriginalRuntime = tab.runtime || 'opencode';
    var titleInput = document.getElementById('chat-assistant-settings-title');
    if (titleInput) titleInput.value = tab.title || '';
    var runtimeSel = document.getElementById('chat-assistant-settings-runtime');
    if (runtimeSel) runtimeSel.value = tab.runtime || 'opencode';
    var warn = document.getElementById('chat-assistant-settings-warn');
    if (warn) warn.classList.add('hidden');
    var err = document.getElementById('chat-assistant-settings-error');
    if (err) err.classList.add('hidden');
    var saveBtn = document.getElementById('chat-assistant-settings-save');
    if (saveBtn) saveBtn.disabled = false;
    _fetchModelsForSettings(tab.runtime || 'opencode', tab.model || '');
  }

  function _fetchModelsForSettings(runtime, currentModel) {
    var projectId = _currentProjectId();
    var params = {};
    if (projectId) params.project_id = projectId;
    params.runtime = runtime;
    var sel = document.getElementById('chat-assistant-settings-model');
    if (sel) { sel.innerHTML = '<option value="">Loading…</option>'; }
    fetch('/api/chat/config?' + new URLSearchParams(params).toString())
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!sel) return;
        sel.innerHTML = '';
        var models = (data && data.models) || [];
        if (!models.length) {
          var opt = document.createElement('option');
          opt.value = '';
          opt.textContent = 'No models available';
          sel.appendChild(opt);
          return;
        }
        models.forEach(function (m) {
          var opt = document.createElement('option');
          opt.value = m;
          opt.textContent = m;
          sel.appendChild(opt);
        });
        if (currentModel && models.indexOf(currentModel) !== -1) {
          sel.value = currentModel;
        } else if (data && data.default_model && models.indexOf(data.default_model) !== -1) {
          sel.value = data.default_model;
        }
      })
      .catch(function () {});
  }

  function _saveSettings() {
    if (!_activeTabId) return;
    var tabId = _activeTabId;
    var tab = _tabs.find(function (t) { return t.id === tabId; });
    if (!tab) return;

    var titleInput = document.getElementById('chat-assistant-settings-title');
    var runtimeSel = document.getElementById('chat-assistant-settings-runtime');
    var modelSel = document.getElementById('chat-assistant-settings-model');
    var saveBtn = document.getElementById('chat-assistant-settings-save');

    var newTitle = (titleInput ? titleInput.value.trim() : '') || tab.title || 'Chat';
    var newRuntime = runtimeSel ? runtimeSel.value : (tab.runtime || 'opencode');
    var newModel = modelSel ? modelSel.value : (tab.model || '');

    var runtimeChanged = newRuntime !== (tab.runtime || 'opencode');

    if (runtimeChanged) {
      // Runtime change: close current tab and open a new one with the new runtime.
      // The old conversation is lost (new session for new runtime).
      _closeSettingsPanel();
      var projectId = _currentProjectId() || tab.project_id;
      _closeTab(tabId);
      _createTab(projectId, newRuntime, newModel, newTitle);
      return;
    }

    // Simple PATCH for title and/or model
    var patchBody = {};
    if (newTitle !== (tab.title || '')) patchBody.title = newTitle;
    if (newModel && newModel !== (tab.model || '')) patchBody.model = newModel;

    if (!Object.keys(patchBody).length) {
      _closeSettingsPanel();
      return;
    }

    if (saveBtn) saveBtn.disabled = true;
    fetch('/api/chat/tabs/' + encodeURIComponent(tabId), {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patchBody)
    })
      .then(function (r) {
        return r.json().then(function (d) {
          if (!r.ok) throw new Error((d && d.error) || ('Error ' + r.status));
          return d;
        });
      })
      .then(function (data) {
        var updated = data && data.tab;
        if (updated) {
          var idx = _tabs.findIndex(function (t) { return t.id === tabId; });
          if (idx !== -1) _tabs[idx] = updated;
          _updateTabButtonLabel(tabId, updated.title, updated.model);
        }
        _closeSettingsPanel();
      })
      .catch(function (err) {
        var errEl = document.getElementById('chat-assistant-settings-error');
        if (errEl) {
          errEl.textContent = 'Save failed: ' + err.message;
          errEl.classList.remove('hidden');
        }
        if (saveBtn) saveBtn.disabled = false;
      });
  }

  // ── Create-tab modal (kept for compatibility; no longer used by default) ──────
  function _openCreateTabModal() {
    var modal = document.getElementById('chat-assistant-create-tab-modal');
    if (!modal) return;
    modal.style.display = '';
    modal.removeAttribute('hidden');

    // Pre-fill project
    var projInput = document.getElementById('chat-assistant-create-tab-project');
    if (projInput) {
      projInput.value = _currentProjectId() || '';
    }

    // Reset runtime dropdown to opencode (default)
    var runtimeSel = document.getElementById('chat-assistant-create-tab-runtime');
    if (runtimeSel) {
      runtimeSel.value = 'opencode';
    }

    // Clear title
    var titleInput = document.getElementById('chat-assistant-create-tab-title-input');
    if (titleInput) titleInput.value = '';

    // Clear error
    _hideCreateTabError();

    // Fetch models for the default runtime (opencode); always re-fetch on open
    // so a project with no Pi models sees the correct empty state if they switch.
    _modalRuntime = 'opencode';
    _modalModels = [];
    _modalDefaultModel = '';
    _fetchModelsForModal('opencode');

    // Focus title input
    if (titleInput) {
      setTimeout(function () { titleInput.focus(); }, 50);
    }
  }

  function _closeCreateTabModal() {
    var modal = document.getElementById('chat-assistant-create-tab-modal');
    if (modal) {
      modal.style.display = 'none';
    }
  }

  function _showCreateTabError(msg) {
    var el = document.getElementById('chat-assistant-create-tab-error');
    if (el) {
      el.textContent = msg;
      el.classList.remove('hidden');
    }
  }

  function _hideCreateTabError() {
    var el = document.getElementById('chat-assistant-create-tab-error');
    if (el) el.classList.add('hidden');
  }

  function _populateCreateTabModelDropdown() {
    var sel = document.getElementById('chat-assistant-create-tab-model');
    var submitBtn = document.getElementById('chat-assistant-create-tab-submit');
    if (!sel) return;
    sel.innerHTML = '';

    if (!_modalModels.length) {
      var opt = document.createElement('option');
      opt.value = '';
      // Distinguish between "still loading" and "genuinely empty after fetch".
      // _fetchModelsForModal sets _modalModels=[] before the fetch starts, so
      // we use a separate sentinel: the placeholder text changes once we know
      // the runtime has no models.
      // Show a loading indicator initially; _fetchModelsForModal replaces it.
      opt.textContent = 'Loading…';
      sel.appendChild(opt);
      if (submitBtn) submitBtn.disabled = false; // re-enabled after fetch
      return;
    }

    _modalModels.forEach(function (m) {
      var opt = document.createElement('option');
      opt.value = m;
      opt.textContent = m;
      if (m === _modalDefaultModel) opt.selected = true;
      sel.appendChild(opt);
    });
    if (_modalDefaultModel) sel.value = _modalDefaultModel;
    if (submitBtn) submitBtn.disabled = false;
  }

  function _fetchModelsForModal(runtime) {
    var projectId = _currentProjectId();
    var selectedRuntime = runtime || 'opencode';
    var params = {};
    if (projectId) params.project_id = projectId;
    params.runtime = selectedRuntime;
    var url = '/api/chat/config?' + new URLSearchParams(params).toString();

    // Show loading state immediately
    _modalModels = [];
    _modalDefaultModel = '';
    _populateCreateTabModelDropdown();

    var submitBtn = document.getElementById('chat-assistant-create-tab-submit');

    fetch(url)
      .then(function (r) {
        if (!r.ok) {
          throw new Error('config fetch failed: ' + r.status);
        }
        return r.json();
      })
      .then(function (data) {
        if (!data) return;
        // Guard: if the user changed runtime again while this fetch was in-flight,
        // discard the stale result.
        if (_modalRuntime !== selectedRuntime) return;
        _modalModels = data.models || [];
        _modalDefaultModel = data.default_model || '';

        if (!_modalModels.length) {
          // Empty model list: show an inline message and disable Create.
          var sel = document.getElementById('chat-assistant-create-tab-model');
          if (sel) {
            sel.innerHTML = '';
            var opt = document.createElement('option');
            opt.value = '';
            if (selectedRuntime === 'pi') {
              opt.textContent = 'No Pi models configured for this project. See docs/IW_AI_Core_AI_Assistant_Models.md.';
            } else {
              opt.textContent = 'No models available.';
            }
            sel.appendChild(opt);
          }
          if (submitBtn) submitBtn.disabled = true;
          _showCreateTabError(
            selectedRuntime === 'pi'
              ? 'No Pi models configured for this project. See docs/IW_AI_Core_AI_Assistant_Models.md.'
              : 'No models available for the selected runtime.'
          );
          return;
        }

        // Models available: clear any previous error and populate.
        _hideCreateTabError();
        _populateCreateTabModelDropdown();
      })
      .catch(function (err) {
        if (_modalRuntime !== selectedRuntime) return;
        _showCreateTabError('Could not load models: ' + err.message);
        if (submitBtn) submitBtn.disabled = true;
      });
  }

  // ── Soft-cap banner ─────────────────────────────────────────────────────────
  function _showSoftCapBanner() {
    _softCapBannerVisible = true;
    var banner = document.getElementById('chat-assistant-softcap-banner');
    if (banner) {
      banner.style.display = '';
      banner.classList.remove('hidden');
    }
  }

  function _hideSoftCapBanner() {
    _softCapBannerVisible = false;
    var banner = document.getElementById('chat-assistant-softcap-banner');
    if (banner) {
      banner.style.display = 'none';
    }
  }

  // ── Recent-closed dropdown ──────────────────────────────────────────────────
  function _toggleClosedTabsDropdown(triggerEl) {
    var dd = document.getElementById('chat-assistant-closed-tabs-dropdown');
    if (!dd) return;
    if (dd.classList.contains('hidden')) {
      // Position below the trigger button
      if (triggerEl) {
        var rect = triggerEl.getBoundingClientRect();
        dd.style.top = (rect.bottom + 4) + 'px';
        dd.style.right = (window.innerWidth - rect.right) + 'px';
        dd.style.left = 'auto';
      }
      _loadRecentClosedTabs();
      dd.classList.remove('hidden');
    } else {
      dd.classList.add('hidden');
    }
  }

  function _hideClosedTabsDropdown() {
    var dd = document.getElementById('chat-assistant-closed-tabs-dropdown');
    if (dd) dd.classList.add('hidden');
  }

  function _loadRecentClosedTabs() {
    var projectId = _currentProjectId();
    if (!projectId) return;
    var list = document.getElementById('chat-assistant-closed-tabs-list');
    if (list) list.innerHTML = '<p class="text-xs text-muted-foreground italic">Loading&#x2026;</p>';

    var url = '/api/chat/tabs/recent-closed?' + new URLSearchParams({ project_id: projectId, limit: '10' }).toString();
    fetch(url)
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!list) return;
        var tabs = (data && data.tabs) || [];
        if (!tabs.length) {
          list.innerHTML = '<p class="text-xs text-muted-foreground italic">No recently closed tabs.</p>';
          return;
        }
        list.innerHTML = '';
        tabs.forEach(function (tab) {
          var div = document.createElement('div');
          div.className = 'chat-assistant-closed-tab-entry';
          var closedAt = tab.closed_at ? _relativeTime(new Date(tab.closed_at)) : '';
          div.innerHTML = '<div class="chat-assistant-closed-tab-title">' + _escHtml(tab.title || 'Chat') + '</div>'
            + '<div class="chat-assistant-closed-tab-meta">'
            + _escHtml(_modelShortName(tab.model || ''))
            + (closedAt ? ' &middot; Closed ' + _escHtml(closedAt) : '')
            + '</div>';
          div.addEventListener('click', function () {
            _reopenTab(tab.id);
          });
          list.appendChild(div);
        });
      })
      .catch(function () {
        if (list) list.innerHTML = '<p class="text-xs text-destructive italic">Failed to load.</p>';
      });
  }

// ── Message rendering ───────────────────────────────────────────────────────
  function _resetAssistantState() {
    if (_activeTabId) {
      _tabCurrentAssistantEl[_activeTabId] = null;
      _tabCurrentAssistantId[_activeTabId] = null;
    }
  }

  function _clearMessages() {
    var msgs = document.getElementById('chat-assistant-messages');
    if (!msgs) return;
    var anchor = document.getElementById('chat-assistant-scroll-anchor');
    var empty = document.getElementById('chat-assistant-empty-state');
    var noTabs = document.getElementById('chat-assistant-no-tabs-state');
    msgs.innerHTML = '';
    if (noTabs) msgs.appendChild(noTabs);
    if (empty) msgs.appendChild(empty);
    if (anchor) msgs.appendChild(anchor);
    if (_activeTabId) _tabHasHistory[_activeTabId] = false;
  }

  function _showEmptyState() {
    var el = document.getElementById('chat-assistant-empty-state');
    if (el) el.style.display = '';
    var noTabs = document.getElementById('chat-assistant-no-tabs-state');
    if (noTabs) noTabs.classList.add('hidden');
  }

  function _hideEmptyState() {
    var el = document.getElementById('chat-assistant-empty-state');
    if (el) el.style.display = 'none';
    var noTabs = document.getElementById('chat-assistant-no-tabs-state');
    if (noTabs) noTabs.classList.add('hidden');
  }

  function _renderEmptyNoTabs() {
    var wrap = document.getElementById('chat-assistant-tab-strip-wrap');
    if (wrap) wrap.style.display = 'none';

    var noTabs = document.getElementById('chat-assistant-no-tabs-state');
    var empty = document.getElementById('chat-assistant-empty-state');
    if (noTabs) {
      noTabs.classList.remove('hidden');
      noTabs.style.display = '';
    }
    if (empty) empty.style.display = 'none';

    // Hide composer
    var composer = document.getElementById('chat-assistant-composer-wrap');
    if (composer) composer.style.display = 'none';
  }

  function _showComposer() {
    var composer = document.getElementById('chat-assistant-composer-wrap');
    if (composer) composer.style.display = '';
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

  function _appendOrUpdateAssistantMessage(tabId, eid, text, isFinal) {
    var msgs = document.getElementById('chat-assistant-messages');
    if (!msgs) return;
    _hideEmptyState();

    var currentEl = _tabCurrentAssistantEl[tabId];
    var currentId = _tabCurrentAssistantId[tabId];

    if (!isFinal && currentEl) {
      var bodyEl = currentEl.querySelector('.chat-assistant-stream-text');
      if (bodyEl) {
        bodyEl.textContent += text;
        _scrollToBottom();
        return;
      }
    }

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
    _tabCurrentAssistantEl[tabId] = wrap;
    _tabCurrentAssistantId[tabId] = eid;
    _scrollToBottom();
  }

  function _finaliseLastAssistantMessage(tabId) {
    _tabCurrentAssistantEl[tabId] = null;
    _tabCurrentAssistantId[tabId] = null;
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

  function _scrollToBottom() {
    var msgs = document.getElementById('chat-assistant-messages');
    if (msgs) msgs.scrollTop = msgs.scrollHeight;
  }

  // ── Load history for a tab ──────────────────────────────────────────────────
  function _loadTabHistory(tabId) {
    fetch('/api/chat/tabs/' + encodeURIComponent(tabId))
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (data) {
        if (!data || !data.messages) return;
        // Only render if this tab is still active
        if (tabId !== _activeTabId) return;
        _clearMessages();
        var renderedCount = 0;
        data.messages.forEach(function (entry) {
          var info = entry && entry.info;
          var parts = (entry && entry.parts) || [];
          if (!info) return;
          var text = parts
            .filter(function (p) { return p && p.type === 'text' && typeof p.text === 'string'; })
            .map(function (p) { return p.text; })
            .join('');
          if (info.role === 'user') {
            _appendUserMessage(text);
            renderedCount++;
          } else if (info.role === 'assistant') {
            _appendOrUpdateAssistantMessage(tabId, info.id, text, true);
            renderedCount++;
            parts.forEach(function (p) {
              if (!p || !p.type) return;
              var pt = p.type;
              // Handle both opencode 'tool-use' and Pi 'tool_use' conventions
              if (pt === 'tool-use' || pt === 'tool_use') {
                _appendToolCall(p.name || 'tool', p.input || {});
              } else if (pt === 'tool-result' || pt === 'tool_result') {
                _appendToolResult(typeof p.content === 'string' ? p.content : JSON.stringify(p.content));
              }
            });
          }
        });
        _tabCurrentAssistantEl[tabId] = null;
        _tabCurrentAssistantId[tabId] = null;
        _showComposer();
        if (renderedCount > 0) {
          _tabHasHistory[tabId] = true;
          _updateClearButton();
        }
      })
      .catch(function (err) {
        _appendSystemMessage('Could not load chat history \u2014 ' + (err && err.message ? err.message : 'runtime unavailable'), 'error');
      });
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
    var streaming = _activeTabId ? (_tabStreaming[_activeTabId] || false) : false;
    var sendBtn = document.getElementById('chat-assistant-send');
    var abortBtn = document.getElementById('chat-assistant-abort');
    if (sendBtn) sendBtn.disabled = streaming;
    if (abortBtn) {
      // Use CSS opacity (not disabled/hidden) so playwright never sees a
      // mid-click state transition that triggers its actionability retry
      // loop. `_abort()` is a no-op when no stream is in flight, so a stray
      // click while not streaming is harmless.
      abortBtn.style.opacity = streaming ? '1' : '0.45';
      abortBtn.title = streaming ? 'Abort current run' : 'No active run to abort';
    }
  }

  function _sendPrompt() {
    var input = document.getElementById('chat-assistant-input');
    if (!input) return;
    var text = input.value.trim();
    if (!text) return;
    if (!_activeTabId) {
      _appendSystemMessage('No active chat tab. Create one first.', 'error');
      return;
    }
    var tabId = _activeTabId;
    var tab = _tabs.find(function (t) { return t.id === tabId; });
    var ctx = (!_chipDismissed && _context) ? _context : null;
    var body = { text: text };
    if (tab && tab.model) body.model = tab.model;
    if (ctx) body.context = ctx;

    _appendUserMessage(text);
    input.value = '';
    _closeSlashMenu();

    // Enter abortable state immediately after submit so per-tab abort remains
    // reachable even when runtimes emit only a short/fast stream.
    _tabStreaming[tabId] = true;
    _updateSendAbortButtons();
    _startContextPoll();

    fetch('/api/chat/tabs/' + encodeURIComponent(tabId) + '/prompt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
      .then(function (resp) {
        if (!resp.ok) {
          throw new Error('Send failed: ' + resp.status);
        }
      })
      .catch(function (err) {
        _appendSystemMessage(err.message, 'error');
        _tabStreaming[tabId] = false;
        _stopContextPoll();
        _updateSendAbortButtons();
      });
  }

  function _abort() {
    if (!_activeTabId) return;
    var tabId = _activeTabId;
    // Always POST — the dashboard router and the opencode stub both treat
    // an abort against an idle session as a no-op (idle.idle without
    // aborted=True is emitted by the stub; the dashboard returns 204).
    // We previously gated this on `_tabStreaming[tabId]` but that
    // introduced a race: between the user clicking Abort and the click
    // event actually dispatching (playwright auto-wait + DOM-stability
    // retries), `_tabStreaming[tabId]` can flip to false as the stream
    // completes naturally, silently swallowing a real abort intent.
    fetch('/api/chat/tabs/' + encodeURIComponent(tabId) + '/abort', { method: 'POST' })
      .catch(function () { /* ignore */ });
  }

  function _updateClearButton() {
    var btn = document.getElementById('chat-assistant-clear');
    if (!btn) return;
    var hasHistory = _activeTabId ? (_tabHasHistory[_activeTabId] || false) : false;
    btn.disabled = !hasHistory;
  }

  function _clearChat() {
    if (!_activeTabId) return;
    if (!_tabHasHistory[_activeTabId]) return;

    var tabId = _activeTabId;
    fetch('/api/chat/tabs/' + encodeURIComponent(tabId) + '/clear', { method: 'POST' })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (data) {
        // Only act if this tab is still active
        if (tabId !== _activeTabId) return;

        // 1. Update the in-memory tab model with new session ID
        var newTab = data && data.tab;
        if (newTab) {
          _tabs = _tabs.map(function (t) { return t.id === tabId ? newTab : t; });
        }

        // 2. Close old EventSource and reset SSE tracking
        if (_tabEs[tabId]) {
          _tabEs[tabId].close();
          delete _tabEs[tabId];
        }
        sessionStorage.removeItem('iw-chat-last-eid-' + tabId);
        delete _tabSeenIds[tabId];

        // 3. Reset streaming / assistant state
        _tabStreaming[tabId] = false;
        _tabCurrentAssistantEl[tabId] = null;
        _tabCurrentAssistantId[tabId] = null;

        // 4. Clear DOM
        _clearMessages();

        // 5. Reset history flag and update button
        _tabHasHistory[tabId] = false;
        _updateClearButton();
        _updateSendAbortButtons();

        // 6. Show confirmation message
        _appendSystemMessage('Chat cleared.', 'info');

        // 7. Reconnect stream to new session
        _connectStream(tabId);
      })
      .catch(function (err) {
        _appendSystemMessage('Could not clear chat: ' + (err && err.message ? err.message : 'unknown error'), 'error');
      });
  }

  // ── Context % polling ───────────────────────────────────────────────────────
  function _applyContextPct(pct) {
    var el = document.getElementById('chat-assistant-context-pct');
    if (!el) return;
    el.classList.remove('is-warn', 'is-crit');
    if (typeof pct === 'number' && isFinite(pct)) {
      var rounded = Math.round(pct);
      el.textContent = rounded + '%';
      el.title = 'Context window used: ' + rounded + '%';
      el.setAttribute('aria-label', 'Context window used: ' + rounded + '%');
      el.classList.remove('hidden');
      if (rounded >= 90) {
        el.classList.add('is-crit');
      } else if (rounded >= 70) {
        el.classList.add('is-warn');
      }
    } else {
      el.textContent = '';
      el.classList.add('hidden');
    }
  }

  function _refreshContextPct(tabId) {
    if (!tabId) {
      _applyContextPct(NaN); // hide + clear
      return;
    }
    fetch('/api/chat/tabs/' + encodeURIComponent(tabId))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var session = data && data.session;
        _applyContextPct(session && session.context_pct);
      })
      .catch(function () { /* ignore */ });
  }

  function _startContextPoll() {
    _stopContextPoll();
    var tabId = _activeTabId;
    _contextPollTimer = setInterval(function () {
      _refreshContextPct(tabId);
    }, 5000);
  }

  function _stopContextPoll() {
    if (_contextPollTimer) {
      clearInterval(_contextPollTimer);
      _contextPollTimer = null;
    }
  }

  // ── Model selector ──────────────────────────────────────────────────────────
  function _refreshModels() {
    var projectId = _currentProjectId();
    _lastProjectId = projectId;
    // Determine the active tab's runtime so the per-tab model dropdown shows
    // only models that are valid for that runtime (Pi tab → Pi models only;
    // OpenCode tab → OpenCode models only). No cross-runtime model switching;
    // changing runtime requires creating a new tab.
    var activeTab = _activeTabId ? _tabs.find(function (t) { return t.id === _activeTabId; }) : null;
    var activeRuntime = (activeTab && activeTab.runtime) ? activeTab.runtime : 'opencode';
    var params = {};
    if (projectId) params.project_id = projectId;
    params.runtime = activeRuntime;
    var url = '/api/chat/config?' + new URLSearchParams(params).toString();
    fetch(url)
      .then(function (r) {
        if (!r.ok) return null;
        return r.json();
      })
      .then(function (data) {
        if (!data) return;
        _projectDirectoryProjectId = projectId;
        _projectDirectory = typeof data.project_directory === 'string' ? data.project_directory : '';
        _defaultModel = data.default_model || '';
        // _defaultModel is kept current so _instantCreateTab() picks the right default.
      })
      .catch(function () { /* silently ignore */ });
  }

  function _scheduleModelRefresh() {
    if (_modelRefreshTimer) clearInterval(_modelRefreshTimer);
    _modelRefreshTimer = setInterval(function () {
      if (!_isOpen()) return;
      var projectId = _currentProjectId();
      if (projectId !== _lastProjectId) {
        _defaultModel = '';
        _projectDirectory = '';
        _projectDirectoryProjectId = null;
      }
      _refreshModels();
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

  // ── Utility helpers ─────────────────────────────────────────────────────────
  function _escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function _truncateStr(str, maxLen) {
    if (!str || str.length <= maxLen) return str;
    return str.slice(0, maxLen - 1) + '…';
  }

  function _modelShortName(model) {
    // "anthropic/claude-sonnet-4-7" → "claude-sonnet-4-7"
    // Truncate if still long
    var slash = model.lastIndexOf('/');
    var name = slash !== -1 ? model.slice(slash + 1) : model;
    return _truncateStr(name, 14);
  }

  function _relativeTime(date) {
    var now = new Date();
    var diffMs = now - date;
    var diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return 'just now';
    if (diffMin < 60) return diffMin + 'm ago';
    var diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return diffHr + 'h ago';
    var diffDay = Math.floor(diffHr / 24);
    return diffDay + 'd ago';
  }

  // ── Ctrl+/ keybinding ───────────────────────────────────────────────────────
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

    // No-tabs CTA
    var noTabsCta = document.getElementById('chat-assistant-no-tabs-cta');
    if (noTabsCta) {
      noTabsCta.addEventListener('click', function () { _instantCreateTab(); });
    }

    // Hamburger settings button
    var settingsBtn = document.getElementById('chat-assistant-settings-btn');
    if (settingsBtn) {
      settingsBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        var panel = document.getElementById('chat-assistant-settings-panel');
        if (panel && !panel.classList.contains('hidden')) {
          _closeSettingsPanel();
        } else {
          _openSettingsPanel();
        }
      });
    }

    // Settings panel: runtime change → update model list + show/hide warning
    document.addEventListener('change', function (e) {
      var runtimeSel = document.getElementById('chat-assistant-settings-runtime');
      if (runtimeSel && e.target === runtimeSel) {
        var tab = _activeTabId ? _tabs.find(function (t) { return t.id === _activeTabId; }) : null;
        var originalRuntime = tab ? (tab.runtime || 'opencode') : 'opencode';
        var warn = document.getElementById('chat-assistant-settings-warn');
        if (warn) {
          if (runtimeSel.value !== originalRuntime) {
            warn.classList.remove('hidden');
          } else {
            warn.classList.add('hidden');
          }
        }
        var currentModel = tab ? (tab.model || '') : '';
        _fetchModelsForSettings(runtimeSel.value, currentModel);
      }
    });

    // Settings panel: cancel
    document.addEventListener('click', function (e) {
      var cancelBtn = document.getElementById('chat-assistant-settings-cancel');
      if (cancelBtn && (e.target === cancelBtn || cancelBtn.contains(e.target))) {
        _closeSettingsPanel();
      }
    });

    // Settings panel: save
    document.addEventListener('click', function (e) {
      var saveBtn = document.getElementById('chat-assistant-settings-save');
      if (saveBtn && !saveBtn.disabled && (e.target === saveBtn || saveBtn.contains(e.target))) {
        _saveSettings();
      }
    });

    // Settings panel: Enter key on title input submits save
    document.addEventListener('keydown', function (e) {
      var titleInput = document.getElementById('chat-assistant-settings-title');
      var panel = document.getElementById('chat-assistant-settings-panel');
      if (titleInput && e.target === titleInput && e.key === 'Enter') {
        e.preventDefault();
        _saveSettings();
      }
      if (panel && !panel.classList.contains('hidden') && e.key === 'Escape') {
        _closeSettingsPanel();
      }
    });

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

    // Clear button
    var clearBtn = document.getElementById('chat-assistant-clear');
    if (clearBtn) {
      clearBtn.addEventListener('click', function () { _clearChat(); });
    }

    // Textarea
    var input = document.getElementById('chat-assistant-input');
    if (input) {
      input.addEventListener('keydown', function (e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
          e.preventDefault();
          _sendPrompt();
          return;
        }
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          _sendPrompt();
          return;
        }
        if (e.key === 'Escape') {
          _closeSlashMenu();
        }
      });

      input.addEventListener('input', function () {
        var val = input.value;
        if (val.startsWith('/')) {
          _openSlashMenu(val.slice(1));
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
          if (!hidden) _loadSkills();
        }
      });
    }

    // History dropdown toggle (repurposed as "session history" — kept for
    // backwards compat with the header button; loads the recent-closed list)
    var histToggle = document.getElementById('chat-assistant-history-toggle');
    if (histToggle) {
      histToggle.addEventListener('click', function (e) {
        e.stopPropagation();
        _toggleClosedTabsDropdown(histToggle);
      });
    }

    // Soft-cap dismiss
    var softCapDismiss = document.getElementById('chat-assistant-softcap-dismiss');
    if (softCapDismiss) {
      softCapDismiss.addEventListener('click', function () {
        _hideSoftCapBanner();
      });
    }

    // Context menu actions
    var ctxMenu = document.getElementById('chat-assistant-tab-context-menu');
    if (ctxMenu) {
      ctxMenu.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-ctx-action]');
        if (!btn) return;
        var action = btn.getAttribute('data-ctx-action');
        var tabId = _ctxMenuTabId;
        _hideTabContextMenu();
        if (!tabId) return;
        if (action === 'rename') {
          // Find the tab button and trigger inline rename
          var tabBtn = document.querySelector('#chat-assistant-tab-strip .chat-assistant-tab-btn[data-tab-id="' + tabId + '"]');
          if (tabBtn) {
            var titleSpan = tabBtn.querySelector('.chat-assistant-tab-title');
            if (titleSpan) _startInlineRename(tabId, titleSpan);
          }
        } else if (action === 'duplicate') {
          _duplicateTab(tabId);
        } else if (action === 'close') {
          _closeTab(tabId);
        }
      });
    }

    // Close context menu, dropdowns, and settings panel when clicking outside
    document.addEventListener('click', function (e) {
      // Tab context menu
      var ctxM = document.getElementById('chat-assistant-tab-context-menu');
      if (ctxM && !ctxM.classList.contains('hidden')) {
        if (!ctxM.contains(e.target)) {
          _hideTabContextMenu();
        }
      }
      // Closed tabs dropdown
      var closedDd = document.getElementById('chat-assistant-closed-tabs-dropdown');
      var histToggleEl = document.getElementById('chat-assistant-history-toggle');
      if (closedDd && !closedDd.classList.contains('hidden')) {
        if (!closedDd.contains(e.target)
            && !(histToggleEl && histToggleEl.contains(e.target))) {
          closedDd.classList.add('hidden');
        }
      }
      // Settings panel: close when clicking outside the panel and not the settings button
      var settingsPanel = document.getElementById('chat-assistant-settings-panel');
      var settingsBtnEl = document.getElementById('chat-assistant-settings-btn');
      if (settingsPanel && !settingsPanel.classList.contains('hidden')) {
        if (!settingsPanel.contains(e.target)
            && !(settingsBtnEl && settingsBtnEl.contains(e.target))) {
          _closeSettingsPanel();
        }
      }
    });

    // Initial state
    if (_isOpen()) {
      _bootstrapTabs();
      _refreshModels();
    }

    _scheduleModelRefresh();
  });

})();

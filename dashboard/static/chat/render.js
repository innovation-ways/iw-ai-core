(function () {
  'use strict';

  var ALLOWED_LINK_SCHEMES = ['http:', 'https:', 'mailto:'];
  var FORBIDDEN_TAGS = ['script', 'iframe', 'object', 'embed', 'svg', 'math'];
  var FORBIDDEN_ATTRS = ['onload', 'onerror', 'onclick', 'onmouseover', 'onfocus', 'onblur', 'onchange', 'onsubmit'];

  function sanitizeHTML(html) {
    if (typeof DOMPurify === 'undefined') {
      console.warn('[iwChat] DOMPurify not loaded');
      return html;
    }
    return DOMPurify.sanitize(html, {
      ALLOWED_TAGS: ['p', 'br', 'hr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'strong', 'em', 's', 'del', 'a', 'img', 'ul', 'ol', 'li',
        'blockquote', 'pre', 'code', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
        'input', 'span', 'div', 'details', 'summary'],
      ALLOWED_ATTR: ['href', 'src', 'alt', 'title', 'class', 'type', 'disabled',
        'checked', 'target', 'rel', 'data-cite', 'aria-haspopup', 'aria-label',
        'data-language', 'data-partial', 'data-copy-payload', 'open', 'summary'],
      FORBID_TAGS: FORBIDDEN_TAGS,
      FORBID_ATTR: FORBIDDEN_ATTRS,
      ALLOW_DATA_ATTR: false,
      ADD_ATTR: ['target', 'rel'],
      FORBID_SCRIPT: true,
    });
  }

  function walkAndSanitizeLinks(container) {
    var walker = document.createTreeWalker(container, NodeFilter.SHOW_ELEMENT, null, false);
    var nodesToProcess = [];
    var current;
    while ((current = walker.nextNode())) {
      nodesToProcess.push(current);
    }
    for (var i = 0; i < nodesToProcess.length; i++) {
      var node = nodesToProcess[i];
      if (node.tagName === 'A') {
        var href = node.getAttribute('href') || '';
        var scheme = href.split(':')[0].toLowerCase();
        if (ALLOWED_LINK_SCHEMES.indexOf(scheme + ':') === -1 && href !== '#') {
          node.replaceWith(document.createTextNode(node.textContent || href));
          continue;
        }
        if (node.target === '_blank') {
          node.setAttribute('rel', 'noopener noreferrer');
        }
      }
    }
  }

  function escapeHTML(str) {
    return str.replace(/&/g, '&amp;')
              .replace(/</g, '&lt;')
              .replace(/>/g, '&gt;')
              .replace(/"/g, '&quot;')
              .replace(/'/g, '&#39;');
  }

  function buildCSVRow(cells) {
    return cells.map(function (cell) {
      var text = cell.replace(/"/g, '""');
      if (text.indexOf(',') !== -1 || text.indexOf('"') !== -1 || text.indexOf('\n') !== -1) {
        return '"' + text + '"';
      }
      return text;
    }).join(',');
  }

  function tableToCSV(table) {
    var rows = table.querySelectorAll('tr');
    var csv = [];
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i];
      var cells = row.querySelectorAll('th, td');
      var cellTexts = [];
      for (var j = 0; j < cells.length; j++) {
        cellTexts.push(cells[j].textContent || '');
      }
      csv.push(buildCSVRow(cellTexts));
    }
    return csv.join('\n');
  }

  function attachCopyCSVToTable(wrapper) {
    var tables = wrapper.querySelectorAll('table');
    for (var t = 0; t < tables.length; t++) {
      var table = tables[t];
      (function (tbl) {
        var btn = tbl.parentElement && tbl.parentElement.querySelector('.table-copy-csv-btn');
        if (!btn) {
          var wrapper2 = tbl.closest('.table-wrapper');
          if (wrapper2) btn = wrapper2.querySelector('.table-copy-csv-btn');
        }
        if (!btn) return;
        btn.addEventListener('click', function () {
          var csv = tableToCSV(tbl);
          navigator.clipboard.writeText(csv).then(function () {
            var span = btn.querySelector('span') || btn;
            var original = span.textContent;
            span.textContent = 'Copied!';
            setTimeout(function () { span.textContent = original; }, 2000);
          }).catch(function () {});
        });
      })(table);
    }
  }

  function highlightCodeBlock(preEl) {
    var codeEl = preEl.querySelector('code');
    if (!codeEl) return;
    var langClass = codeEl.className.match(/language-(\S+)/);
    var lang = (langClass && langClass[1]) ? langClass[1] : '';
    var raw = codeEl.textContent || '';
    if (typeof hljs !== 'undefined') {
      var result;
      try {
        if (lang && hljs.getLanguage(lang)) {
          result = hljs.highlight(raw, { language: lang });
        } else {
          result = hljs.highlightAuto(raw);
        }
        codeEl.innerHTML = result.value;
      } catch (e) {
        codeEl.textContent = raw;
      }
    }
    preEl.removeAttribute('data-partial');
    preEl.setAttribute('data-highlighted', 'true');
  }

  function attachCopyButton(preEl) {
    var container = preEl.parentElement;
    if (!container) return;
    var btn = container.querySelector('.code-copy-btn');
    if (!btn) return;
    btn.addEventListener('click', function () {
      var payload = btn.getAttribute('data-copy-payload') || preEl.querySelector('code')?.textContent || '';
      navigator.clipboard.writeText(payload).then(function () {
        var span = btn.querySelector('span');
        var original = span ? span.textContent : btn.textContent;
        if (span) span.textContent = 'Copied!';
        else btn.textContent = 'Copied!';
        setTimeout(function () {
          if (span) span.textContent = original;
          else btn.textContent = original;
        }, 2000);
      }).catch(function () {});
    });
  }

  function finalizeCodeBlocks(container) {
    var partialBlocks = container.querySelectorAll('pre[data-partial="true"]');
    for (var i = 0; i < partialBlocks.length; i++) {
      var pre = partialBlocks[i];
      highlightCodeBlock(pre);
      attachCopyButton(pre);
      pre.removeAttribute('data-partial');
    }
  }

  function setupCitationPopovers(container, citationMap) {
    var chips = container.querySelectorAll('[data-cite]');
    chips.forEach(function (chip) {
      if (chip.getAttribute('data-popover-bound')) return;
      chip.setAttribute('data-popover-bound', 'true');
      chip.addEventListener('click', function (e) {
        e.stopPropagation();
        var existing = container.querySelector('.citation-popover');
        if (existing) existing.remove();
        var n = chip.getAttribute('data-cite');
        var cite = citationMap.get(n);
        if (!cite) return;
        var popover = document.createElement('div');
        popover.className = 'citation-popover fixed inset-0 z-50 flex items-center justify-center bg-black/50';
        popover.setAttribute('role', 'dialog');
        popover.setAttribute('aria-label', 'Citation ' + n);
        var inner = '<div class="bg-card border border-border rounded-lg p-4 max-w-sm shadow-lg relative">' +
          '<button class="citation-popover-close absolute top-2 right-2 text-muted-foreground hover:text-foreground text-2xl leading-none" aria-label="Close" type="button">&times;</button>' +
          '<strong class="block mb-1">' + escapeHTML(cite.label) + '</strong>';
        if (cite.snippet) {
          inner += '<p class="text-xs text-muted-foreground mt-1 mb-2 max-h-32 overflow-y-auto">' + escapeHTML(cite.snippet.substring(0, 240)) + '</p>';
        }
        if (cite.url) {
          inner += '<a href="' + escapeHTML(cite.url) + '" class="text-xs text-primary hover:underline" target="_blank" rel="noopener noreferrer">Open source →</a>';
        }
        inner += '</div>';
        popover.innerHTML = inner;
        document.body.appendChild(popover);
        chip.setAttribute('aria-expanded', 'true');
        var closeFn = function (ev) {
          if (ev.target === popover || ev.target.classList.contains('citation-popover-close')) {
            popover.remove();
            chip.removeAttribute('aria-expanded');
            document.removeEventListener('click', closeFn);
          }
        };
        setTimeout(function () { document.addEventListener('click', closeFn); }, 0);
        chip.addEventListener('click', function (ev) { closeFn(ev); });
      });
    });
  }

  function initChatRenderer(smd) {
    var parser = smd.parser;
    var parser_write = smd.parser_write;
    var parser_end = smd.parser_end;
    var default_renderer = smd.default_renderer;

    window.iwChat = window.iwChat || {};

    window.iwChat.createAssistantRenderer = function (messageEl) {
      var bodyEl = messageEl.querySelector('.chat-message-body');
      if (!bodyEl) {
        bodyEl = document.createElement('div');
        bodyEl.className = 'chat-message-body';
        messageEl.insertBefore(bodyEl, messageEl.querySelector('header').nextSibling);
      }
      var buffer = '';
      var renderer = default_renderer(bodyEl);
      var p = parser(renderer);
      var citationMap = new Map();
      var done = false;
      var phaseStrip = null;
      var phaseData = {};
      var feedItems = [];
      var workItemFeedEl = null;

      function updateCitations() {
        var chips = bodyEl.querySelectorAll('[data-cite]');
        chips.forEach(function (chip) {
          var n = chip.getAttribute('data-cite');
          if (n && !chip.getAttribute('data-popover-bound')) {
            chip.setAttribute('data-popover-bound', 'true');
            chip.addEventListener('click', function (e) {
              e.stopPropagation();
              var existing = bodyEl.querySelector('.citation-popover');
              if (existing) existing.remove();
              var cite = citationMap.get(n);
              if (!cite) return;
              var popover = document.createElement('div');
              popover.className = 'citation-popover fixed inset-0 z-50 flex items-center justify-center bg-black/50';
              popover.setAttribute('role', 'dialog');
              popover.setAttribute('aria-label', 'Citation ' + n);
              var inner = '<div class="bg-card border border-border rounded-lg p-4 max-w-sm shadow-lg relative">' +
                '<button class="citation-popover-close absolute top-2 right-2 text-muted-foreground hover:text-foreground text-2xl leading-none" aria-label="Close" type="button">&times;</button>' +
                '<strong class="block mb-1">' + escapeHTML(cite.label || '') + '</strong>';
              if (cite.snippet) {
                inner += '<p class="text-xs text-muted-foreground mt-1 mb-2 max-h-32 overflow-y-auto">' + escapeHTML(cite.snippet.substring(0, 240)) + '</p>';
              }
              if (cite.url) {
                inner += '<a href="' + escapeHTML(cite.url) + '" class="text-xs text-primary hover:underline" target="_blank" rel="noopener noreferrer">Open source →</a>';
              }
              if (cite.work_item_type) {
                var typeLabel = cite.work_item_type === 'feature' ? 'Feature' : (cite.work_item_type === 'change_request' ? 'Change Request' : 'Incident');
                inner += '<p class="text-xs text-muted-foreground mt-1">' + typeLabel + ' · ' + escapeHTML(cite.work_item_id || '') + '</p>';
              }
              inner += '</div>';
              popover.innerHTML = inner;
              document.body.appendChild(popover);
              chip.setAttribute('aria-expanded', 'true');
              var closeFn = function (ev) {
                if (ev.target === popover || ev.target.classList.contains('citation-popover-close')) {
                  popover.remove();
                  chip.removeAttribute('aria-expanded');
                  document.removeEventListener('click', closeFn);
                }
              };
              setTimeout(function () { document.addEventListener('click', closeFn); }, 0);
            });
          }
        });
        var sourcesPanel = messageEl.querySelector('.sources-panel');
        if (sourcesPanel) {
          var summary = sourcesPanel.querySelector('summary');
          if (summary) {
            summary.textContent = 'Sources (' + citationMap.size + ')';
          }
        }
      }

      function createPhaseStrip() {
        phaseStrip = document.createElement('div');
        phaseStrip.className = 'phase-strip';
        phaseStrip.setAttribute('role', 'status');
        phaseStrip.setAttribute('aria-live', 'polite');
        messageEl.insertBefore(phaseStrip, bodyEl);
      }

      function updatePhaseStrip() {
        if (!phaseStrip) return;
        var labels = {
          retrieving: 'Looking up related code\u2026',
          finding_items: 'Finding related items\u2026' + (phaseData.detail && phaseData.detail.count ? ' (' + phaseData.detail.count + ')' : ''),
          reading_docs: 'Reading design documents\u2026' + (phaseData.detail && phaseData.detail.count ? ' (' + phaseData.detail.count + ')' : ''),
          composing: 'Writing answer\u2026',
        };
        phaseStrip.textContent = labels[phaseData.name] || phaseData.name || '';
        if (phaseData.name === 'composing') {
          phaseStrip.classList.add('phase-strip--quiet');
        }
      }

      function collapsePhaseStrip() {
        if (!phaseStrip || phaseStrip.classList.contains('phase-strip--collapsed')) return;
        phaseStrip.classList.add('phase-strip--collapsed');
        var count = phaseData.detail && phaseData.detail.count ? phaseData.detail.count : 0;
        phaseStrip.textContent = 'Based on ' + count + ' work items.';
      }

      function updateWorkItemFeed() {
        if (!workItemFeedEl && feedItems.length > 0) {
          workItemFeedEl = document.createElement('section');
          workItemFeedEl.className = 'work-item-feed';
          workItemFeedEl.setAttribute('aria-label', 'Work item history');
          messageEl.appendChild(workItemFeedEl);
        }
        if (!workItemFeedEl) return;
        var header = '<header class="work-item-feed-header"><h3 class="text-sm font-medium">History</h3></header>';
        var items = feedItems.slice(0, 5);
        var itemsHtml = items.map(function (item) {
          var glyph = item.work_item_type === 'feature' ? 'F' : (item.work_item_type === 'change_request' ? 'CR' : 'I');
          var typeLabel = item.work_item_type === 'feature' ? 'Feature' : (item.work_item_type === 'change_request' ? 'Change Request' : 'Incident');
          var createdAt = item.created_at || item.createdAt || '';
          var projectId = item.project_id || (window.location.pathname.split('/')[2]) || '';
          return '<li class="work-item-feed-item" data-workitem-id="' + escapeHTML(item.work_item_id || item.workItemId || '') + '">' +
            '<div class="work-item-feed-meta">' +
            '<time datetime="' + escapeHTML(createdAt) + '">' + escapeHTML(createdAt) + '</time>' +
            '<a href="/project/' + escapeHTML(projectId) + '/item/' + escapeHTML(item.work_item_id || item.workItemId || '') + '" class="work-item-feed-id">' + escapeHTML(item.work_item_id || item.workItemId || '') + '</a>' +
            '</div>' +
            '<h4 class="work-item-feed-title">' + escapeHTML(item.title || item.label || '') + '</h4>' +
            '<p class="work-item-feed-summary">' + escapeHTML(item.summary || item.snippet || '(no summary available)') + '</p>' +
            '</li>';
        }).join('');
        workItemFeedEl.innerHTML = header + '<ol class="work-item-feed-list">' + itemsHtml + '</ol>';
      }

      function finalizeWorkItemFeed() {
        if (!workItemFeedEl) return;
        workItemFeedEl.classList.add('work-item-feed--done');
      }

      window.iwChat = window.iwChat || {};

      window.iwChat.injectToneSwitchChip = function (messageEl, renderId, currentTone) {
        var existing = messageEl.querySelector('.tone-switch-chip');
        if (existing) existing.remove();
        var chip = document.createElement('button');
        chip.className = 'tone-switch-chip';
        chip.dataset.renderId = renderId;
        chip.dataset.currentTone = currentTone;
        var label = currentTone === 'technical' ? 'Show functional summary' : 'Show implementation details';
        chip.textContent = label;
        chip.setAttribute('aria-label', label);
        chip.setAttribute('disabled', 'true');
        messageEl.appendChild(chip);
        setTimeout(function () { chip.removeAttribute('disabled'); }, 2000);
        chip.addEventListener('click', function () {
          var projectId = window.location.pathname.split('/')[2];
          var url = '/api/projects/' + projectId + '/code/qa/rerender';
          var newTone = chip.dataset.currentTone === 'technical' ? 'functional' : 'technical';
          chip.setAttribute('disabled', 'true');
          chip.textContent = 'Re-running\u2026';
          fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ render_id: renderId, tone: newTone }),
          }).then(function (response) {
            if (response.status === 410) {
              window.location.reload();
              return;
            }
            if (!response.ok) {
              chip.textContent = 'Error';
              return;
            }
            var reader = response.body.getReader();
            var decoder = new TextDecoder('utf-8');
            var buffer = '';
            var rerenderBodyEl = messageEl.querySelector('.chat-message-body');
            if (rerenderBodyEl) rerenderBodyEl.innerHTML = '';
            function read() {
              reader.read().then(function (result) {
                if (result.done) {
                  chip.dataset.currentTone = newTone;
                  chip.textContent = newTone === 'technical' ? 'Show functional summary' : 'Show implementation details';
                  chip.removeAttribute('disabled');
                  return;
                }
                buffer += decoder.decode(result.value, { stream: true });
                var lines = buffer.split('\n');
                buffer = lines.pop();
                lines.forEach(function (line) {
                  if (line.startsWith('event:')) {
                    return;
                  }
                  if (line.startsWith('data: ')) {
                    try {
                      var data = JSON.parse(line.slice(6));
                      if (data.b64) {
                        var txt = atob(data.b64);
                        if (rerenderBodyEl) {
                          rerenderBodyEl.innerHTML += txt;
                        }
                      } else if (data.name !== undefined) {
                        if (renderer && renderer.onPhase) {
                          renderer.onPhase({ name: data.name, detail: data.detail || {} });
                        }
                      } else if (data.n !== undefined) {
                        if (renderer && renderer.onCitation) {
                          renderer.onCitation({ n: data.n, label: data.label, url: data.url, snippet: data.snippet, work_item_type: data.work_item_type, work_item_id: data.work_item_id });
                        }
                      }
                    } catch (err) {}
                  }
                });
                read();
              });
            }
            read();
          }).catch(function () {
            chip.textContent = 'Error';
          });
        });
      };

      return {
        onToken: function (deltaText) {
          buffer += deltaText;
          try {
            parser_write(p, deltaText);
          } catch (err) {
            console.warn('[iwChat] parse error:', err);
          }
          var html = bodyEl.innerHTML;
          var clean = sanitizeHTML(html);
          if (clean !== html) {
            bodyEl.innerHTML = clean;
            walkAndSanitizeLinks(bodyEl);
          }
          finalizeCodeBlocks(bodyEl);
          updateCitations();
          if (phaseStrip) {
            collapsePhaseStrip();
          }
        },
        onCitation: function (data) {
          citationMap.set(String(data.n), data);
          updateCitations();
        },
        onPhase: function (data) {
          phaseData = data;
          if (!phaseStrip) {
            createPhaseStrip();
          }
          updatePhaseStrip();
        },
        onWorkItemCitation: function (data) {
          feedItems.push(data);
          updateWorkItemFeed();
        },
        onDone: function () {
          done = true;
          try { parser_end(p); } catch (err) {}
          bodyEl.innerHTML = sanitizeHTML(bodyEl.innerHTML);
          walkAndSanitizeLinks(bodyEl);
          finalizeCodeBlocks(bodyEl);
          updateCitations();
          var tables = bodyEl.querySelectorAll('table');
          tables.forEach(function (tbl) {
            var wrapper = tbl.closest('.table-wrapper');
            if (wrapper) attachCopyCSVToTable(wrapper);
          });
          if (window.iwChat && window.iwChat.upgradeAllMermaidBlocks) {
            window.iwChat.upgradeAllMermaidBlocks(bodyEl);
          }
          finalizeWorkItemFeed();
        },
        onError: function (data) {
          if (done) return;
          bodyEl.innerHTML = '<div class="chat-error text-destructive text-sm">Error: ' + escapeHTML(data.message) + '</div>';
        },
      };
    };

    window.iwChat.renderMarkdownStatic = function (text) {
      var frag = document.createDocumentFragment();
      var tempDiv = document.createElement('div');
      frag.appendChild(tempDiv);
      var renderer = default_renderer(tempDiv);
      var p = parser(renderer);
      try {
        parser_write(p, text);
        parser_end(p);
      } catch (err) {
        tempDiv.innerHTML = '<p class="text-destructive">Render error</p>';
        return frag;
      }
      var html = tempDiv.innerHTML;
      var clean = sanitizeHTML(html);
      tempDiv.innerHTML = clean;
      walkAndSanitizeLinks(tempDiv);
      finalizeCodeBlocks(tempDiv);
      return frag;
    };
  }

  window.__iwChatOnSMDReady = initChatRenderer;

  if (window.__iwSMD) {
    initChatRenderer(window.__iwSMD);
  }
})();

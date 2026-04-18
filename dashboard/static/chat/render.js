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
        },
        onCitation: function (data) {
          citationMap.set(String(data.n), data);
          updateCitations();
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

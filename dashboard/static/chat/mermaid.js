(function () {
  'use strict';

  var mermaidCounter = 0;

  function getBrandColor(varName) {
    var val = getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
    if (!val) return null;
    if (val.startsWith('#')) return val;
    if (val.startsWith('rgb')) {
      var m = val.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
      if (m) {
        var r = parseInt(m[1], 10).toString(16).padStart(2, '0');
        var g = parseInt(m[2], 10).toString(16).padStart(2, '0');
        var b = parseInt(m[3], 10).toString(16).padStart(2, '0');
        return '#' + r + g + b;
      }
    }
    return null;
  }

  function toRgbHex(cssColor) {
    if (!cssColor) return null;
    if (cssColor.startsWith('#')) {
      if (cssColor.length === 4) {
        var r = cssColor[1], g = cssColor[2], b = cssColor[3];
        return '#' + r + r + g + g + b + b;
      }
      return cssColor;
    }
    if (cssColor.startsWith('rgb')) {
      var m = cssColor.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
      if (m) {
        var rh = parseInt(m[1], 10).toString(16).padStart(2, '0');
        var gh = parseInt(m[2], 10).toString(16).padStart(2, '0');
        var bh = parseInt(m[3], 10).toString(16).padStart(2, '0');
        return '#' + rh + gh + bh;
      }
    }
    return null;
  }

  function buildThemeVariables() {
    var primary = toRgbHex(getBrandColor('--primary')) || '#5865f2';
    var accent = toRgbHex(getBrandColor('--accent')) || '#eeeef0';
    var muted = toRgbHex(getBrandColor('--muted')) || '#f6f6f6';
    var border = toRgbHex(getBrandColor('--border')) || '#dfdfe1';
    var foreground = toRgbHex(getBrandColor('--foreground')) || '#28282d';
    var background = toRgbHex(getBrandColor('--background')) || '#fbfbfb';

    return {
      primaryColor: primary,
      primaryBorderColor: border,
      primaryTextColor: foreground,
      lineColor: foreground,
      tertiaryColor: muted,
      background: background,
      fontFamily: getComputedStyle(document.documentElement).getPropertyValue('--font-sans').trim() || 'Inter, sans-serif',
    };
  }

  function renderMermaidError(preEl, dsl) {
    var container = document.createElement('div');
    container.className = 'mermaid-error rounded-md border border-destructive/20 bg-destructive/5 p-3 text-xs';
    container.innerHTML =
      '<div class="flex items-center justify-between gap-2">' +
        '<span class="text-destructive">⚠ Diagram error</span>' +
        '<button type="button" class="mermaid-retry min-h-[44px] min-w-[44px] inline-flex items-center justify-center" aria-label="Retry diagram render">↻ Retry</button>' +
      '</div>' +
      '<details class="mt-2">' +
        '<summary class="cursor-pointer">Show source</summary>' +
        '<pre class="mt-2 overflow-x-auto"><code></code></pre>' +
      '</details>';

    var codeEl = container.querySelector('code');
    if (codeEl) codeEl.textContent = dsl;

    var retryBtn = container.querySelector('.mermaid-retry');
    if (retryBtn) {
      retryBtn.addEventListener('click', function () {
        var wrapper = container.closest('.mermaid-wrapper');
        if (wrapper) {
          var newPre = document.createElement('pre');
          newPre.setAttribute('data-lang', 'mermaid');
          newPre.setAttribute('data-upgrade-target', 'true');
          var code = document.createElement('code');
          code.textContent = dsl;
          newPre.appendChild(code);
          wrapper.replaceWith(newPre);
          window.iwChat.upgradeMermaidBlock(newPre);
        }
      });
    }

    preEl.replaceWith(container);
    return container;
  }

  function openMermaidModal(iframeEl) {
    var wrapper = iframeEl.closest('.mermaid-wrapper');
    if (!wrapper) return;

    var svgDoc = iframeEl.contentDocument || iframeEl.contentWindow?.document;
    var svgEl = svgDoc ? svgDoc.querySelector('svg') : null;
    if (!svgEl) return;

    var svgHtml = svgEl.outerHTML;

    var overlay = document.createElement('div');
    overlay.className = 'fixed inset-0 z-50 flex items-center justify-center bg-black/70';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', 'Diagram full-screen');

    var modal = document.createElement('div');
    modal.className = 'relative bg-card rounded-lg shadow-2xl max-w-5xl max-h-[90vh] flex flex-col overflow-hidden';
    modal.style.width = '90vw';
    modal.style.height = '90vh';

    modal.innerHTML =
      '<div class="flex items-center justify-between p-4 border-b border-border">' +
        '<span class="text-sm font-medium">Diagram</span>' +
        '<button class="mermaid-modal-close min-h-[44px] min-w-[44px] inline-flex items-center justify-center text-muted-foreground hover:text-foreground text-2xl leading-none" aria-label="Close">&times;</button>' +
      '</div>' +
      '<div class="flex-1 overflow-auto p-4 bg-[var(--background)] flex items-center justify-center">' +
        '<div class="mermaid-modal-svg max-w-full max-h-full" style="background: var(--card); padding: 1rem; border-radius: var(--radius);">' + svgHtml + '</div>' +
      '</div>';

    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    var closeBtn = modal.querySelector('.mermaid-modal-close');
    var closeFn = function (e) {
      if (e.target === overlay || e.target === closeBtn) {
        overlay.remove();
        document.removeEventListener('click', closeFn);
      }
    };
    setTimeout(function () { document.addEventListener('click', closeFn); }, 0);
    closeBtn.addEventListener('click', function () { overlay.remove(); });
  }

  window.iwChat.upgradeMermaidBlock = function (preEl) {
    var codeEl = preEl.querySelector('code');
    var dsl = preEl.textContent || '';

    if (typeof window.mermaid === 'undefined') {
      console.warn('[iwChat] Mermaid not loaded');
      return;
    }

    try {
      var parsed = window.mermaid.parse(dsl, { suppressErrors: true });
      if (!parsed) {
        renderMermaidError(preEl, dsl);
        return;
      }
    } catch (err) {
      renderMermaidError(preEl, dsl);
      return;
    }

    var id = 'iw-mermaid-' + (++mermaidCounter);

    var themeVars = buildThemeVariables();

    var config = {
      securityLevel: 'sandbox',
      elk: {
        layout: 'elk',
        useGles: false,
      },
      look: 'handDrawn',
      theme: 'base',
      themeVariables: themeVars,
    };

    try {
      window.mermaid.initialize(config);
      var insertFn = function (svgCode) {
        var wrapper = document.createElement('div');
        wrapper.className = 'mermaid-wrapper';
        wrapper.setAttribute('data-iw-layout', 'elk');

        var caption = document.createElement('p');
        caption.className = 'text-xs text-muted-foreground mb-1';
        caption.textContent = 'Diagram — click to expand';

        var expandBtn = document.createElement('button');
        expandBtn.type = 'button';
        expandBtn.className = 'text-xs text-primary hover:underline mb-2 min-h-[44px] min-w-[44px] inline-flex items-center';
        expandBtn.setAttribute('aria-label', 'Expand diagram full-screen');
        expandBtn.textContent = 'Expand ↗';

        var container = document.createElement('div');
        container.style.position = 'relative';
        container.style.display = 'inline-block';
        container.style.maxWidth = '100%';

        var iframe = document.createElement('iframe');
        iframe.setAttribute('sandbox', 'allow-scripts allow-same-origin');
        iframe.setAttribute('title', 'Mermaid diagram');
        iframe.style.border = 'none';
        iframe.style.width = '100%';
        iframe.style.maxWidth = '800px';
        iframe.style.borderRadius = 'var(--radius)';
        iframe.style.display = 'block';

        var srcdoc = '<!DOCTYPE html><html><head>' +
          '<meta charset="utf-8">' +
          '<style>' +
            'body{margin:0;padding:1rem;background:transparent;font-family:' + JSON.stringify(themeVars.fontFamily) + '}' +
            '.mermaid{color:' + JSON.stringify(themeVars.primaryTextColor) + '}' +
          '</style>' +
          '</head><body>' +
          '<div class="mermaid">' + svgCode + '</div>' +
          '<script src="/static/vendor/mermaid/mermaid.min.js"><\/script>' +
          '<script>mermaid.initialize({startOnLoad:false,securityLevel:\'sandbox\',theme:\'base\',themeVariables:' + JSON.stringify(themeVars) + ',elk:{layout:\'elk\'},flowchart:{htmlLabels:true}});<\/script>' +
          '</body></html>';
        iframe.srcdoc = srcdoc;

        expandBtn.addEventListener('click', function () { openMermaidModal(iframe); });

        container.appendChild(iframe);
        wrapper.appendChild(caption);
        wrapper.appendChild(expandBtn);
        wrapper.appendChild(container);

        preEl.replaceWith(wrapper);
      };

      window.mermaid.render(id, dsl).then(insertFn)['catch'](function (err) {
        console.warn('[iwChat] Mermaid render error:', err);
        renderMermaidError(preEl, dsl);
      });

    } catch (err) {
      console.warn('[iwChat] Mermaid render error:', err);
      renderMermaidError(preEl, dsl);
    }
  };

  window.iwChat.upgradeAllMermaidBlocks = function (container) {
    var blocks = container.querySelectorAll('pre[data-lang="mermaid"]');
    blocks.forEach(function (block) {
      window.iwChat.upgradeMermaidBlock(block);
    });
  };

})();
(function () {
  window.iwChat = window.iwChat || {};

  window.iwChat.streamAnswer = function (_a) {
    var projectId = _a.projectId, body = _a.body, _b = _a.onToken, onToken = _b === void 0 ? function () {} : _b, _c = _a.onCitation, onCitation = _c === void 0 ? function () {} : _c, _d = _a.onDone, onDone = _d === void 0 ? function () {} : _d, _e = _a.onError, onError = _e === void 0 ? function () {} : _e, _f = _a.onPhase, onPhase = _f === void 0 ? function () {} : _f, _g = _a.onWorkItemCitation, onWorkItemCitation = _g === void 0 ? function () {} : _g;
    var controller = new AbortController();
    window.__iwChatCancel = function () {
      controller.abort();
    };
    var accumulated = '';
    fetch('/api/projects/' + projectId + '/code/qa', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error('HTTP ' + response.status + ' ' + response.statusText);
        }
        var reader = response.body.getReader();
        var decoder = new TextDecoder('utf-8');
        var buffer = '';
        var eventType = '';
        function read() {
          reader.read().then(function (result) {
            if (result.done) {
              onDone({ ok: true });
              return;
            }
            buffer += decoder.decode(result.value, { stream: true });
            var lines = buffer.split('\n');
            buffer = lines.pop();
            lines.forEach(function (line) {
              if (line.startsWith('event:')) {
                eventType = line.slice(6).trim();
                return;
              }
              if (!line.startsWith('data: ')) return;
              var jsonStr = line.slice(6);
              try {
                var data = JSON.parse(jsonStr);
                if (data.b64) {
                  var binary = atob(data.b64);
                  var bytes = new Uint8Array(binary.length);
                  for (var i = 0; i < binary.length; i++) {
                    bytes[i] = binary.charCodeAt(i);
                  }
                  var utf8 = decoder.decode(bytes);
                  accumulated += utf8;
                  onToken(utf8);
                } else if (data.n !== undefined && eventType === 'citation') {
                  var citationData = { n: data.n, label: data.label, url: data.url, snippet: data.snippet, work_item_type: data.work_item_type, work_item_id: data.work_item_id };
                  onCitation(citationData);
                  if (data.work_item_type !== undefined && data.work_item_id !== undefined) {
                    onWorkItemCitation({ work_item_type: data.work_item_type, work_item_id: data.work_item_id, label: data.label, url: data.url, snippet: data.snippet });
                  }
                } else if (data.name !== undefined && eventType === 'phase') {
                  onPhase({ name: data.name, detail: data.detail || {} });
                }
              } catch (err) {}
            });
            eventType = '';
            read();
          }).catch(function (err) {
            if (err.name === 'AbortError') {
              onDone({ ok: false, aborted: true });
            } else {
              onError({ message: err.message });
            }
          });
        }
        read();
      })
      .catch(function (err) {
        if (err.name === 'AbortError') {
          onDone({ ok: false, aborted: true });
        } else {
          onError({ message: err.message });
        }
      });
  };
})();

/* =========================================================================
   sse-client.js
   Global SSE client that multiplexes one upstream EventSource across all
   tabs via a SharedWorker, with a per-tab EventSource fallback when
   SharedWorker is unavailable.
   ========================================================================= */

(function() {
  'use strict';

  var _worker = null;
  var _fallback = null;
  var _tabSubscriptions = {};
  var _readyResolve = null;
  var _readyPromise = new Promise(function(resolve) {
    _readyResolve = resolve;
  });
  var _connected = false;
  var _usingFallback = false;

  function _markEventReceived(eventType) {
    try {
      window.__iwSSELastEventAt = Date.now();
      window.__iwSSELastEventType = eventType;
      window.__iwSSEEventCount = (window.__iwSSEEventCount || 0) + 1;
    } catch (e) {
      /* window frozen or cross-origin — ignore */
    }
  }

  function _getSharedWorker() {
    try {
      return new SharedWorker(
        '/static/sse-shared-worker.js',
        'iw-sse-shared-worker'
      );
    } catch (e) {
      return null;
    }
  }

  function _handleWorkerMessage(msg) {
    var data = msg.data;
    if (!data || typeof data !== 'object') return;

    if (data.type === 'sse') {
      _markEventReceived(data.event);
      var handlers = _tabSubscriptions[data.event];
      if (handlers) {
        for (var i = 0; i < handlers.length; i++) {
          try {
            handlers[i]({ data: data.data, lastEventId: data.id });
          } catch (e) {
            /* handler threw — ignore */
          }
        }
      }
    } else if (data.type === 'pong') {
      _connected = true;
      _readyResolve();
    } else if (data.type === 'sse-error') {
      /* upstream error — browser will auto-reconnect; surface nothing */
    }
  }

  function _setTransport(kind) {
    try {
      window.__iwSSETransport = kind;
    } catch (e) {
      /* window frozen — ignore */
    }
  }

  function _initSharedWorker() {
    var sw = _getSharedWorker();
    if (!sw) {
      _initFallback();
      return;
    }

    _worker = sw;
    _worker.port.addEventListener('message', _handleWorkerMessage);
    _worker.port.start();
    _connected = true;
    _setTransport('shared-worker');

    _worker.port.onmessage = function(msg) {
      _handleWorkerMessage(msg);
    };

    _worker.onerror = function() {
      _initFallback();
    };

    setTimeout(function() {
      _sendToWorker({ type: 'ping' });
    }, 100);
  }

  function _initFallback() {
    _usingFallback = true;
    _connected = true;
    _setTransport('fallback');
    try {
      _fallback = new EventSource('/api/stream/events');

      var events = ['running-update', 'status-update', 'test-update', 'quality-update', 'toast'];
      for (var i = 0; i < events.length; i++) {
        (function(eventType) {
          _fallback.addEventListener(eventType, function(ev) {
            _markEventReceived(eventType);
            var handlers = _tabSubscriptions[eventType];
            if (handlers) {
              for (var j = 0; j < handlers.length; j++) {
                try {
                  handlers[j]({ data: ev.data, lastEventId: ev.lastEventId || null });
                } catch (e) {
                  /* ignore */
                }
              }
            }
          });
        })(events[i]);
      }

      _fallback.onerror = function() {
        /* browser auto-reconnects; no action needed */
      };

      _fallback.onopen = function() {
        _readyResolve();
      };
    } catch (e) {
      _connected = false;
    }
  }

  function _sendToWorker(msg) {
    if (_worker && _worker.port) {
      try {
        _worker.port.postMessage(msg);
      } catch (e) {
        /* SharedWorker unavailable — ignore */
      }
    }
  }

  function _subscribe(eventType) {
    _sendToWorker({ type: 'subscribe', events: [eventType] });
  }

  function _connect() {
    if (_worker === null && _fallback === null) {
      if (typeof SharedWorker !== 'undefined') {
        _initSharedWorker();
      } else {
        _initFallback();
      }
    }
  }

  window.iwSSE = {
    on: function(eventType, handler) {
      if (!eventType || typeof handler !== 'function') return;

      _connect();

      if (!_tabSubscriptions[eventType]) {
        _tabSubscriptions[eventType] = [];
        _subscribe(eventType);
      }

      _tabSubscriptions[eventType].push(handler);
    },

    off: function(eventType, handler) {
      if (!eventType) return;
      var handlers = _tabSubscriptions[eventType];
      if (!handlers) return;

      if (!handler) {
        delete _tabSubscriptions[eventType];
        _sendToWorker({ type: 'unsubscribe', events: [eventType] });
        return;
      }

      for (var i = handlers.length - 1; i >= 0; i--) {
        if (handlers[i] === handler) {
          handlers.splice(i, 1);
        }
      }

      if (handlers.length === 0) {
        delete _tabSubscriptions[eventType];
        _sendToWorker({ type: 'unsubscribe', events: [eventType] });
      }
    },

    ready: _readyPromise,
  };

  window.addEventListener('beforeunload', function() {
    if (_worker && _worker.port) {
      try {
        _worker.port.postMessage({ type: 'close' });
        _worker.port.close();
      } catch (e) {
        /* ignore */
      }
    }
  });

  window.addEventListener('pagehide', function() {
    if (_worker && _worker.port) {
      try {
        _worker.port.postMessage({ type: 'close' });
        _worker.port.close();
      } catch (e) {
        /* ignore */
      }
    }
  });

})();

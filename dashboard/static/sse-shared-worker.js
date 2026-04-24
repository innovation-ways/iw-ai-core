/* =========================================================================
   sse-shared-worker.js
   SharedWorker that maintains ONE upstream EventSource and fans out events
   to all connected browser tabs.
   ========================================================================= */

var SSE_WORKER_URL = '/api/stream/events';

var WATCHED_EVENTS = [
  'running-update',
  'status-update',
  'test-update',
  'quality-update',
  'toast',
];

var upstream = null;
var ports = new Map();

function ensureUpstream() {
  if (upstream !== null) return;
  upstream = new EventSource(SSE_WORKER_URL);

  for (var i = 0; i < WATCHED_EVENTS.length; i++) {
    (function(eventType) {
      upstream.addEventListener(eventType, function(ev) {
        broadcast(eventType, ev);
      });
    })(WATCHED_EVENTS[i]);
  }

  upstream.onerror = function() {
    broadcastError();
  };
}

function broadcast(eventType, ev) {
  var payload = {
    type: 'sse',
    event: eventType,
    data: ev.data,
    id: ev.lastEventId || null,
  };
  ports.forEach(function(subs, port) {
    if (subs.has(eventType) || subs.has('*')) {
      try {
        port.postMessage(payload);
      } catch (e) {
        /* port may already be closed — ignore */
      }
    }
  });
}

function broadcastError() {
  var payload = { type: 'sse-error' };
  ports.forEach(function(subs, port) {
    try {
      port.postMessage(payload);
    } catch (e) {
      /* port may already be closed — ignore */
    }
  });
}

function closeUpstreamIfIdle() {
  if (ports.size === 0 && upstream !== null) {
    upstream.close();
    upstream = null;
  }
}

self.addEventListener('connect', function(e) {
  var port = e.ports[0];
  var subscriptions = new Set();

  port.onmessage = function(msg) {
    var data = msg.data;
    if (!data || typeof data !== 'object') return;

    switch (data.type) {
      case 'subscribe':
        if (Array.isArray(data.events)) {
          for (var i = 0; i < data.events.length; i++) {
            subscriptions.add(data.events[i]);
          }
        } else {
          subscriptions.add(data.events);
        }
        break;

      case 'unsubscribe':
        if (Array.isArray(data.events)) {
          for (var j = 0; j < data.events.length; j++) {
            subscriptions.delete(data.events[j]);
          }
        } else {
          subscriptions.delete(data.events);
        }
        break;

      case 'ping':
        try {
          port.postMessage({ type: 'pong' });
        } catch (e) { /* ignore */ }
        break;

      case 'close':
        ports.delete(port);
        port.close();
        closeUpstreamIfIdle();
        break;
    }
  };

  ports.set(port, subscriptions);
  port.start();
  ensureUpstream();
});

(function () {
  'use strict';

  window.iwChat = window.iwChat || {};

  window.iwChat.citations = {
    _map: new Map(),

    register: function (n, data) {
      this._map.set(String(n), data);
    },

    get: function (n) {
      return this._map.get(String(n));
    },

    getAll: function () {
      return Array.from(this._map.entries()).map(function (_a) {
        var n = _a[0], data = _a[1];
        return { n: Number(n), label: data.label, url: data.url, snippet: data.snippet };
      }).sort(function (a, b) { return a.n - b.n; });
    },

    clear: function () {
      this._map.clear();
    },
  };
})();

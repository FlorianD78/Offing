'use strict';
const { handler, parisDay } = require('./_lib/util');
const { loadEngine } = require('./_lib/engine');

module.exports = handler(['GET'], async (req, res) => {
  res.setHeader('cache-control', 'no-store');
  return { ok: true, day: parisDay(), engine: loadEngine().version };
});

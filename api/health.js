'use strict';
const { handler, parisDay } = require('./_lib/util');
const { loadEngine } = require('./_lib/engine');

module.exports = handler(['GET'], async (req, res) => {
  res.setHeader('cache-control', 'no-store');
  const E = loadEngine(), day = parisDay();
  return { ok: true, day, engine: E.version, pick: E.dailyPick(day) };
});

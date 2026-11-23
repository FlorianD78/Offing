'use strict';
const { handler, parisDay, weekKey } = require('./_lib/util');
const { loadEngine } = require('./_lib/engine');

module.exports = handler(['GET'], async (req, res) => {
  res.setHeader('cache-control', 'no-store');
  const E = loadEngine(), day = parisDay(), week = weekKey();
  return { ok: true, day, week, engine: E.version, pick: E.dailyPick(day), weekly: E.weeklyPick(week) };
});

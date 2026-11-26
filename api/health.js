'use strict';
const { handler, parisDay, weekKey } = require('./_lib/util');
const { loadEngine } = require('./_lib/engine');
const { meta } = require('./_lib/meta');

module.exports = handler(['GET'], async (req, res) => {
  res.setHeader('cache-control', 'no-store');
  const day = parisDay(), week = weekKey(), out = { ok: true, day, week, engine: meta().engine };
  // tirages du jour / de la semaine : seulement sur demande (?full=1), car ils demandent le moteur, long à charger à froid
  if ((req.query || {}).full === '1') { const E = loadEngine(); out.engine = E.version; out.pick = E.dailyPick(day); out.weekly = E.weeklyPick(week); }
  return out;
});

'use strict';
// GET ?course&cls[&day][&player][&week=1] -> top 50 du jour ou de la semaine (+ ta place)
const { handler, HttpError, UUID_RE, parisDay, weekKey } = require('./_lib/util');
const { db } = require('./_lib/db');
const { validCourse } = require('./_lib/meta');

module.exports = handler(['GET'], async (req, res) => {
  const q = req.query || {}, weekly = q.week === '1';
  const day = /^\d{4}-\d{2}-\d{2}$/.test(q.day || '') ? q.day : weekly ? weekKey() : parisDay();
  if (!validCourse(q.course, q.cls, weekly)) throw new HttpError(400, 'parcours invalide');
  const rows = await db().top(day, q.course, q.cls, 50);
  const top = rows.map((x, i) => ({ rank: i + 1, name: x.players?.name || '?', T: x.time_s, attempts: x.attempts, me: !!q.player && x.player_id === q.player }));
  let me = null, total = top.length;
  if (q.player && UUID_RE.test(q.player)) {
    const b = await db().getBest(q.player, day, q.course, q.cls);
    if (b) { const r = await db().rankOf(day, q.course, q.cls, b.time_s); me = { rank: r.rank, T: b.time_s }; total = r.total; }
  }
  if (!me && top.length === 50) total = (await db().rankOf(day, q.course, q.cls, 1e9)).total;
  res.setHeader('cache-control', q.player ? 'private, no-store' : 'public, s-maxage=30, stale-while-revalidate=60');
  return { day, total, top, me };
});

'use strict';
// GET ?course&cls[&player][&mode=top][&week=1] -> 1er essai (ou mode=top) : top 10 ; ensuite : les 10 meilleurs temps les plus proches du tien (hors toi)
const { handler, HttpError, UUID_RE, parisDay, weekKey, thinTrace } = require('./_lib/util');
const { db } = require('./_lib/db');
const { validCourse } = require('./_lib/meta');

const out = (rows, every) => rows.map(x => ({ name: x.players?.name || '?', T: x.time_s, trace: thinTrace(x.trace, every) }));

module.exports = handler(['GET'], async (req, res) => {
  const { course, cls, player, mode, week } = req.query || {}, weekly = week === '1', day = weekly ? weekKey() : parisDay();
  if (!validCourse(course, cls, weekly)) throw new HttpError(400, 'parcours invalide');
  const me = mode !== 'top' && player && UUID_RE.test(player) ? await db().getBest(player, day, course, cls) : null;
  let rows;
  if (!me) {
    rows = await db().ghosts(day, course, cls, { dir: 'top', limit: 10 });
    res.setHeader('cache-control', 'public, s-maxage=60, stale-while-revalidate=120'); // identique pour tous : mis en cache par le CDN Vercel
  } else {
    const [f, s] = await Promise.all([
      db().ghosts(day, course, cls, { dir: 'faster', time: me.time_s, exclude: player, limit: 10 }),
      db().ghosts(day, course, cls, { dir: 'slower', time: me.time_s, exclude: player, limit: 10 }),
    ]);
    rows = f.concat(s).sort((a, b) => Math.abs(a.time_s - me.time_s) - Math.abs(b.time_s - me.time_s)).slice(0, 10);
    res.setHeader('cache-control', 'private, no-store');
  }
  rows.sort((a, b) => a.time_s - b.time_s);
  // rang réel de chaque fantôme dans le classement du jour
  const ranks = await Promise.all(rows.map(x => db().rankOf(day, course, cls, x.time_s)));
  const ghosts = out(rows, weekly ? 600 : 120).map((g, i) => ({ ...g, rank: ranks[i].rank }));
  return { day, mine: me ? { T: me.time_s } : null, ghosts };
});

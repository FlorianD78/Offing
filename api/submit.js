'use strict';
// POST { id, token, log } -> rejoue le journal d'ordres avec le moteur du jeu, enregistre le chrono vérifié
const { handler, HttpError, UUID_RE, LIMITS, acceptedDays, sha256, safeEq, thinTrace } = require('./_lib/util');
const { db } = require('./_lib/db');
const { loadEngine } = require('./_lib/engine');

module.exports = handler(['POST'], async (req) => {
  const b = req.body || {}, log = b.log;
  if (!UUID_RE.test(String(b.id || ''))) throw new HttpError(400, 'identifiant invalide');
  if (!log || typeof log !== 'object' || !Array.isArray(log.ev)) throw new HttpError(400, 'journal invalide');
  if (JSON.stringify(log).length > LIMITS.maxLogBytes || log.ev.length > LIMITS.maxEvents) throw new HttpError(413, 'journal trop volumineux');
  if (!acceptedDays().includes(log.day)) throw new HttpError(400, 'défi d\'un autre jour : journal refusé');

  const E = loadEngine();
  if (log.eng !== E.version) throw new HttpError(409, 'version du jeu différente : recharge la page');
  const pick = E.dailyPick(log.day); // 2 parcours × 2 classes tirés par la date, identiques côté jeu
  if (!pick.courses.includes(log.course) || !pick.classes.includes(log.cls)) throw new HttpError(400, 'parcours ou classe hors du défi du jour');

  const p = await db().getPlayer(b.id);
  if (!p || !safeEq(p.token_hash, sha256(b.token))) throw new HttpError(401, 'profil inconnu');
  const prev = await db().getBest(p.id, log.day, log.course, log.cls);
  if (prev && prev.attempts >= LIMITS.submitsPerDay) throw new HttpError(429, 'trop d\'envois aujourd\'hui sur ce défi');

  // Rejeu déterministe : état de départ officiel, météo du jour, ordres du joueur
  let res;
  try { res = E.serverReplay(log, log.day); } catch (e) { throw new HttpError(422, e.message === 'version' ? 'version du jeu différente : recharge la page' : 'journal illisible'); }
  if (!res || !Number.isFinite(res.T) || res.T <= 0) throw new HttpError(422, 'course non terminée au rejeu');
  const T = Math.round(res.T);

  const ev = log.ev.filter(e => Array.isArray(e) && Number.isInteger(e[0]) && typeof e[1] === 'string').slice(0, LIMITS.maxEvents);
  const r = await db().submitBest({ player: p.id, day: log.day, course: log.course, cls: log.cls, time: T, pens: res.pens | 0, engine: E.version,
    trace: thinTrace(res.trace, 60), log: { v: log.v, eng: log.eng, day: log.day, course: log.course, cls: log.cls, ev } });
  const { rank, total } = await db().rankOf(log.day, log.course, log.cls, r.best);
  const top = (await db().top(log.day, log.course, log.cls, 10)).map((x, i) => ({ rank: i + 1, name: x.players?.name || '?', T: x.time_s, attempts: x.attempts, me: x.player_id === p.id }));
  return { T, improved: !!r.improved, best: r.best, attempts: r.attempts, rank, total, top };
});

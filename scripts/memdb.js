'use strict';
// Base en mémoire au même format que api/_lib/db.js (tests et serveur local sans Supabase)
const { HttpError } = require('../api/_lib/util');
function memDb() {
const players = new Map(), bests = [];
let seq = 0;
const key = (b) => [b.player_id, b.day, b.course, b.cls].join('|');
const withName = (b) => ({ ...b, players: { name: players.get(b.player_id).name } });
const scope = (day, course, cls) => bests.filter(b => b.day === day && b.course === course && b.cls === cls).sort((a, b) => a.time_s - b.time_s || a.seq - b.seq);
return {
  async getPlayer(id) { return players.get(id) || null; },
  async countRecentPlayersByIp(ip) { return [...players.values()].filter(p => p.ip_hash === ip).length; },
  async createPlayer({ name, tokenHash, ipHash }) {
    if ([...players.values()].some(p => p.name.toLowerCase() === name.toLowerCase())) throw new HttpError(409, 'pseudo déjà pris');
    const id = `00000000-0000-4000-8000-${String(++seq).padStart(12, '0')}`; players.set(id, { id, name, token_hash: tokenHash, ip_hash: ipHash }); return { id, name };
  },
  async renamePlayer(id, name) { players.get(id).name = name; return { id, name }; },
  async getBest(p, day, course, cls) { return bests.find(b => key(b) === [p, day, course, cls].join('|')) || null; },
  async submitBest(r) {
    const k = [r.player, r.day, r.course, r.cls].join('|'), cur = bests.find(b => key(b) === k);
    if (!cur) { bests.push({ player_id: r.player, day: r.day, course: r.course, cls: r.cls, time_s: r.time, attempts: 1, trace: r.trace, log: r.log, seq: ++seq }); return { improved: true, best: r.time, attempts: 1 }; }
    cur.attempts++; if (r.time < cur.time_s) { Object.assign(cur, { time_s: r.time, trace: r.trace, log: r.log }); return { improved: true, best: r.time, attempts: cur.attempts }; }
    return { improved: false, best: cur.time_s, attempts: cur.attempts };
  },
  async rankOf(day, course, cls, t) { const s = scope(day, course, cls); return { rank: s.filter(b => b.time_s < t).length + 1, total: s.length }; },
  async top(day, course, cls, n) { return scope(day, course, cls).slice(0, n).map(withName); },
  async ghosts(day, course, cls, { dir = 'top', time = 0, exclude = null, limit = 10 } = {}) {
    let s = scope(day, course, cls).filter(b => b.player_id !== exclude);
    if (dir === 'faster') s = s.filter(b => b.time_s < time).reverse(); else if (dir === 'slower') s = s.filter(b => b.time_s >= time);
    return s.slice(0, limit).map(withName);
  },
  async purge() { return 0; },
};
}
module.exports = { memDb };

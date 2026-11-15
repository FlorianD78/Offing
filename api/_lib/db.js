'use strict';
// Accès Supabase (clé secrète côté serveur uniquement). Remplaçable par un faux en test : setDb().
const { createClient } = require('@supabase/supabase-js');
const { HttpError } = require('./util');

let client = null;
function sb() {
  if (client) return client;
  const url = process.env.SUPABASE_URL, key = process.env.SUPABASE_SECRET_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) throw new Error('SUPABASE_URL / SUPABASE_SECRET_KEY manquants');
  client = createClient(url, key, { auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false } });
  return client;
}
const chk = ({ data, error }) => { if (error) { if (error.code === '23505') throw new HttpError(409, 'pseudo déjà pris'); throw new Error(error.message); } return data; };

const supabaseDb = {
  async getPlayer(id) { return chk(await sb().from('players').select('id,name,token_hash').eq('id', id).maybeSingle()); },
  async countRecentPlayersByIp(ipHash, sinceIso) {
    const { count, error } = await sb().from('players').select('id', { count: 'exact', head: true }).eq('ip_hash', ipHash).gte('created_at', sinceIso);
    if (error) throw new Error(error.message); return count || 0;
  },
  async createPlayer({ name, tokenHash, ipHash }) { return chk(await sb().from('players').insert({ name, token_hash: tokenHash, ip_hash: ipHash }).select('id,name').single()); },
  async renamePlayer(id, name) { return chk(await sb().from('players').update({ name }).eq('id', id).select('id,name').single()); },
  async getBest(player, day, course, cls) {
    return chk(await sb().from('bests').select('time_s,attempts').match({ player_id: player, day, course, cls }).maybeSingle());
  },
  async submitBest(r) {
    const rows = chk(await sb().rpc('submit_best', { p_player: r.player, p_day: r.day, p_course: r.course, p_cls: r.cls, p_time: r.time, p_pens: r.pens, p_engine: r.engine, p_trace: r.trace, p_log: r.log }));
    return rows[0];
  },
  async rankOf(day, course, cls, time) {
    const q = () => sb().from('bests').select('player_id', { count: 'exact', head: true }).match({ day, course, cls });
    const a = await q().lt('time_s', time), b = await q();
    if (a.error || b.error) throw new Error((a.error || b.error).message);
    return { rank: (a.count || 0) + 1, total: b.count || 0 };
  },
  // Classement : sans traces
  async top(day, course, cls, limit) {
    return chk(await sb().from('bests').select('player_id,time_s,attempts,players(name)').match({ day, course, cls }).order('time_s').order('created_at').limit(limit));
  },
  // Fantômes : avec traces. dir = 'top' | 'faster' | 'slower'
  async ghosts(day, course, cls, { dir = 'top', time = 0, exclude = null, limit = 10 } = {}) {
    let q = sb().from('bests').select('player_id,time_s,trace,players(name)').match({ day, course, cls });
    if (exclude) q = q.neq('player_id', exclude);
    if (dir === 'faster') q = q.lt('time_s', time).order('time_s', { ascending: false });
    else if (dir === 'slower') q = q.gte('time_s', time).order('time_s');
    else q = q.order('time_s');
    return chk(await q.limit(limit));
  },
  async purge(keepDays) { return chk(await sb().rpc('purge_old', { p_keep_days: keepDays })); },
};

let impl = supabaseDb;
module.exports = { db: () => impl, setDb: (d) => { impl = d; } };

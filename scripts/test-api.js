'use strict';
// Tests des fonctions /api avec une base en mémoire (pas besoin de Supabase).
process.env.NODE_ENV = 'test';
const assert = require('assert');
const path = require('path');
const fx = require('./fixtures/daily-ref.json'), fw = require('./fixtures/weekly-ref.json');
process.env.TEST_DAY = fx.log.day; process.env.TEST_WEEK = fw.log.week;
process.env.CRON_SECRET = 'test-secret';

const { setDb } = require('../api/_lib/db');
const { loadEngine } = require('../api/_lib/engine');
loadEngine(path.join(__dirname, '..', 'public', 'index.html'));

setDb(require('./memdb').memDb());

// ---- appel d'une fonction comme Vercel ----
async function call(file, { method = 'GET', body, query = {}, headers = {} } = {}) {
  const fn = require(`../api/${file}`);
  let status = 200, json; const hdr = {};
  const res = { headersSent: false, setHeader: (k, v) => { hdr[k] = v; }, status(s) { status = s; return this; }, json(j) { json = j; this.headersSent = true; return this; } };
  await fn({ method, body, query, headers: { 'x-forwarded-for': '1.2.3.4', ...headers } }, res);
  return { status, json, hdr };
}

(async () => {
  let r = await call('health.js'); assert.equal(r.status, 200); assert.equal(r.json.engine, fx.log.eng);
  r = await call('register.js', { method: 'POST', body: { name: 'x' } }); assert.equal(r.status, 400);
  const A = (await call('register.js', { method: 'POST', body: { name: 'Flo' } })).json; assert.ok(A.token);
  r = await call('register.js', { method: 'POST', body: { name: 'flo' } }); assert.equal(r.status, 409, 'pseudo unique (casse ignorée)');
  const B = (await call('register.js', { method: 'POST', body: { name: 'Bob' } })).json;
  r = await call('register.js', { method: 'POST', body: { id: A.id, token: 'faux', name: 'Pirate' } }); assert.equal(r.status, 401);

  // envoi valide
  let t = Date.now(); r = await call('submit.js', { method: 'POST', body: { id: A.id, token: A.token, log: fx.log } });
  assert.equal(r.status, 200, JSON.stringify(r.json)); assert.equal(r.json.T, fx.expectT); assert.equal(r.json.rank, 1); assert.ok(r.json.improved);
  console.log(`✅ submit : ${r.json.T} s vérifié en ${Date.now() - t} ms, rang ${r.json.rank}/${r.json.total}`);
  // mauvais jeton, autre jour, autre version, journal falsifié
  r = await call('submit.js', { method: 'POST', body: { id: A.id, token: B.token, log: fx.log } }); assert.equal(r.status, 401);
  r = await call('submit.js', { method: 'POST', body: { id: A.id, token: A.token, log: { ...fx.log, day: '2020-01-01' } } }); assert.equal(r.status, 400);
  r = await call('submit.js', { method: 'POST', body: { id: A.id, token: A.token, log: { ...fx.log, eng: 999 } } }); assert.equal(r.status, 409);
  r = await call('submit.js', { method: 'POST', body: { id: A.id, token: A.token, log: { ...fx.log, ev: [] } } });
  assert.equal(r.status, 422, 'sans ordres le bateau ne finit pas'); console.log('✅ journal falsifié refusé :', r.json.error);
  // un chrono client mensonger est ignoré : seul le rejeu compte
  r = await call('submit.js', { method: 'POST', body: { id: B.id, token: B.token, log: { ...fx.log, T: 10 } } });
  assert.equal(r.json.T, fx.expectT); assert.equal(r.json.total, 2);

  // fantômes : premier essai = top 10, ensuite les plus proches hors soi
  const C = (await call('register.js', { method: 'POST', body: { name: 'Chloé' } })).json;
  r = await call('ghosts.js', { query: { course: fx.log.course, cls: fx.log.cls, player: C.id } });
  assert.equal(r.json.mine, null); assert.equal(r.json.ghosts.length, 2); assert.match(r.hdr['cache-control'], /s-maxage/);
  r = await call('ghosts.js', { query: { course: fx.log.course, cls: fx.log.cls, player: A.id } });
  assert.equal(r.json.ghosts.length, 1); assert.equal(r.json.ghosts[0].name, 'Bob'); assert.ok(r.json.ghosts[0].trace.length > 10);
  r = await call('leaderboard.js', { query: { course: fx.log.course, cls: fx.log.cls, player: B.id } });
  assert.equal(r.json.top.length, 2); assert.equal(r.json.me.rank, 1);
  r = await call('leaderboard.js', { query: { course: 'nope', cls: 'imoca' } }); assert.equal(r.status, 400);
  // fantôme du n°1 (analyse de course) et hors tirage du jour
  r = await call('ghosts.js', { query: { course: fx.log.course, cls: fx.log.cls, player: A.id, mode: 'top' } }); assert.equal(r.json.ghosts.length, 2);
  const E = require('../api/_lib/engine').loadEngine(), other = E.classes().find(c => !E.dailyPick(fx.log.day).classes.includes(c));
  r = await call('submit.js', { method: 'POST', body: { id: A.id, token: A.token, log: { ...fx.log, cls: other } } }); assert.equal(r.status, 400);
  // course de la semaine : classement à part (même table, jour = lundi), toutes les classes, autre semaine refusée
  t = Date.now(); r = await call('submit.js', { method: 'POST', body: { id: B.id, token: B.token, log: fw.log } });
  assert.equal(r.status, 200, JSON.stringify(r.json)); assert.equal(r.json.T, fw.expectT); assert.equal(r.json.rank, 1); assert.equal(r.json.total, 1);
  console.log(`✅ semaine : ${r.json.T} s vérifiés en ${Date.now() - t} ms (${fw.log.course}/${fw.log.cls})`);
  r = await call('submit.js', { method: 'POST', body: { id: B.id, token: B.token, log: { ...fw.log, week: '2020-01-06', day: '2020-01-06' } } }); assert.equal(r.status, 400);
  r = await call('submit.js', { method: 'POST', body: { id: B.id, token: B.token, log: { ...fw.log, course: 'fastnet' === fw.log.course ? 'horta' : 'fastnet' } } }); assert.equal(r.status, 400);
  r = await call('submit.js', { method: 'POST', body: { id: B.id, token: B.token, log: { ...fw.log, day: fx.log.day } } }); assert.equal(r.status, 400, 'jour ≠ semaine');
  r = await call('leaderboard.js', { query: { course: fw.log.course, cls: fw.log.cls, week: '1', player: B.id } }); assert.equal(r.json.top.length, 1); assert.equal(r.json.me.rank, 1); assert.equal(r.json.day, fw.log.week);
  r = await call('leaderboard.js', { query: { course: fw.log.course, cls: fw.log.cls } }); assert.equal(r.status, 400, 'parcours hebdo absent du défi du jour');
  r = await call('ghosts.js', { query: { course: fw.log.course, cls: fw.log.cls, week: '1', player: A.id } }); assert.equal(r.json.ghosts.length, 1); assert.ok(r.json.ghosts[0].trace.length > 5);
  // code de récupération
  r = await call('me.js', { method: 'POST', body: { id: A.id, token: A.token } }); assert.equal(r.json.name, 'Flo');
  r = await call('me.js', { method: 'POST', body: { id: A.id, token: 'f'.repeat(64) } }); assert.equal(r.status, 401);
  r = await call('cron.js'); assert.equal(r.status, 401);
  r = await call('cron.js', { headers: { authorization: 'Bearer test-secret' } }); assert.equal(r.status, 200);
  console.log('✅ register / submit / ghosts / leaderboard / cron OK');
})().catch(e => { console.error('❌', e); process.exit(1); });

'use strict';
// Vérifie que le moteur se charge hors navigateur et que le rejeu redonne le chrono de référence.
// Si la physique ou la météo change : incrémenter ENGINE_VER dans public/index.html et régénérer la fixture.
const path = require('path');
const { loadEngine } = require('../api/_lib/engine');
const fx = require('./fixtures/daily-ref.json');

const t0 = Date.now();
const E = loadEngine(path.join(__dirname, '..', 'public', 'index.html'));
const t1 = Date.now();
if (fx.log.eng !== E.version) { console.log(`ℹ️  fixture en version ${fx.log.eng}, moteur en version ${E.version} : fixture à régénérer, test ignoré`); process.exit(0); }
const r = E.serverReplay(fx.log, fx.log.day);
let ok = r.T === fx.expectT;
console.log(`${ok ? '✅' : '❌'} rejeu ${fx.log.course}/${fx.log.cls} : ${r.T} s (attendu ${fx.expectT}) · trace ${r.trace.length} pts · chargement ${t1 - t0} ms · rejeu ${Date.now() - t1} ms`);
// course de la semaine : rejeu au pas de 5 s sur plusieurs jours de course
const fw = require('./fixtures/weekly-ref.json');
if (fw.log.eng === E.version) {
  const t2 = Date.now(), w = E.serverReplay(fw.log, fw.log.week), okW = w.T === fw.expectT; ok = ok && okW;
  console.log(`${okW ? '✅' : '❌'} rejeu semaine ${fw.log.week} ${fw.log.course}/${fw.log.cls} : ${w.T} s (attendu ${fw.expectT}, ${(w.T / 3600).toFixed(1)} h de course) · trace ${w.trace.length} pts · rejeu ${Date.now() - t2} ms`);
  let badW = false; try { E.serverReplay({ ...fw.log, course: 'fastnet' }, fw.log.week); badW = true; } catch (e) { /* attendu : parcours hors tirage */ }
  if (badW) { console.log('❌ un parcours hors tirage de la semaine a été accepté'); ok = false; }
} else console.log('ℹ️  fixture semaine à régénérer');
let bad = false;
try { E.serverReplay({ ...fx.log, eng: E.version + 1 }, fx.log.day); bad = true; } catch (e) { /* attendu */ }
if (bad) { console.log('❌ un journal d\'une autre version a été accepté'); process.exit(1); }
process.exit(ok ? 0 : 1);

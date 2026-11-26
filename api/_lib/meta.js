'use strict';
// Métadonnées légères lues dans public/index.html sans charger le moteur (le chargement du moteur prend ≈ 5 s à froid :
// /api/health dépassait le délai du client, qui affichait alors « Hors ligne »)
const fs = require('fs');
const path = require('path');

let META = null;
function meta() {
  if (META) return META;
  const file = [path.join(process.cwd(), 'public', 'index.html'), path.join(__dirname, '..', '..', 'public', 'index.html')].find(f => fs.existsSync(f));
  if (!file) throw new Error('public/index.html introuvable');
  const html = fs.readFileSync(file, 'utf8');
  const v = html.match(/ENGINE_VER\s*=\s*(\d+)/), c = html.match(/const DAILY_CLASSES\s*=\s*\[([^\]]*)\]/), w = html.match(/const WEEKLY_POOL\s*=\s*\[([^\]]*)\]/);
  // parcours côtiers (défi du jour) : identifiants du tableau COASTAL
  const i0 = html.indexOf('const COASTAL = ['), i1 = i0 < 0 ? -1 : html.indexOf('\n];', i0), coastal = i0 < 0 || i1 < 0 ? [] : [...html.slice(i0, i1).matchAll(/^\s*\{ id: '([a-z0-9_-]+)'/gm)].map(m => m[1]);
  META = { engine: v ? +v[1] : 0, classes: c ? c[1].match(/[a-z0-9]+/g) : ['imoca', 'o50', 'c40', 'proto'], weekly: w ? w[1].match(/[a-z0-9_-]+/g) : [], coastal };
  return META;
}
// validation sans moteur : parcours côtier pour le défi du jour, parcours du lot hebdomadaire pour la course de la semaine
const validCourse = (course, cls, weekly) => { const M = meta(); return M.classes.includes(cls) && (weekly ? M.weekly : M.coastal).includes(String(course || '')); };

module.exports = { meta, validCourse };

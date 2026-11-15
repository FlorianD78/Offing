'use strict';
// POST { name } -> crée un joueur ; POST { id, token, name } -> renomme
const { handler, HttpError, NAME_RE, UUID_RE, LIMITS, sha256, newToken, safeEq, clientIpHash } = require('./_lib/util');
const { db } = require('./_lib/db');

module.exports = handler(['POST'], async (req) => {
  const b = req.body || {}, name = String(b.name || '').trim().replace(/\s+/g, ' ');
  if (!NAME_RE.test(name)) throw new HttpError(400, 'pseudo invalide : 3 à 20 lettres, chiffres, espaces, . _ - \'');
  if (b.id) {
    if (!UUID_RE.test(b.id)) throw new HttpError(400, 'identifiant invalide');
    const p = await db().getPlayer(b.id);
    if (!p || !safeEq(p.token_hash, sha256(b.token))) throw new HttpError(401, 'profil inconnu');
    const r = await db().renamePlayer(b.id, name);
    return { id: r.id, name: r.name };
  }
  const ipHash = clientIpHash(req), since = new Date(Date.now() - 86400_000).toISOString();
  if (await db().countRecentPlayersByIp(ipHash, since) >= LIMITS.registersPerIpPerDay) throw new HttpError(429, 'trop de profils créés depuis cette connexion aujourd\'hui');
  const token = newToken();
  const r = await db().createPlayer({ name, tokenHash: sha256(token), ipHash });
  return { id: r.id, name: r.name, token };
});

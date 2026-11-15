'use strict';
// POST { id, token } -> { id, name } : restaure un profil sur un autre appareil (code de récupération)
const { handler, HttpError, UUID_RE, sha256, safeEq } = require('./_lib/util');
const { db } = require('./_lib/db');

module.exports = handler(['POST'], async (req) => {
  const b = req.body || {};
  if (!UUID_RE.test(String(b.id || '')) || !/^[0-9a-f]{64}$/i.test(String(b.token || ''))) throw new HttpError(400, 'code invalide');
  const p = await db().getPlayer(b.id);
  if (!p || !safeEq(p.token_hash, sha256(b.token))) throw new HttpError(401, 'code inconnu');
  return { id: p.id, name: p.name };
});

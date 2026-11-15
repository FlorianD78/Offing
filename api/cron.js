'use strict';
// Cron Vercel quotidien : ménage + activité régulière (évite la mise en pause du projet Supabase gratuit après 7 jours sans requête)
const { handler, HttpError } = require('./_lib/util');
const { db } = require('./_lib/db');

module.exports = handler(['GET'], async (req) => {
  const secret = process.env.CRON_SECRET;
  if (!secret || req.headers.authorization !== `Bearer ${secret}`) throw new HttpError(401, 'non autorisé');
  const deleted = await db().purge(Number(process.env.KEEP_DAYS) || 30);
  return { ok: true, deleted };
});

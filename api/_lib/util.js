'use strict';
const crypto = require('crypto');

const COURSES = ['iroise', 'normandes', 'scilly', 'galante'];
const CLASSES = ['imoca', 'mini', 'proto'];
const LIMITS = { submitsPerDay: 40, registersPerIpPerDay: 5, maxLogBytes: 400_000, maxEvents: 20_000 };

// Jour du défi = date à Paris (comme le client)
function parisDay(d = new Date()) {
  if (process.env.NODE_ENV === 'test' && process.env.TEST_DAY) return process.env.TEST_DAY;
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Paris', year: 'numeric', month: '2-digit', day: '2-digit' }).format(d);
}
// Jour accepté : aujourd'hui, ou hier pendant les 45 premières minutes (course commencée avant minuit)
function acceptedDays(now = new Date()) {
  const today = parisDay(now), early = parisDay(new Date(now.getTime() - 45 * 60_000));
  return early === today ? [today] : [today, early];
}
const sha256 = (s) => crypto.createHash('sha256').update(String(s)).digest('hex');
const newToken = () => crypto.randomBytes(32).toString('hex');
const safeEq = (a, b) => { const A = Buffer.from(String(a)), B = Buffer.from(String(b)); return A.length === B.length && crypto.timingSafeEqual(A, B); };
const NAME_RE = /^[\p{L}\p{N}][\p{L}\p{N} _.'-]{1,18}[\p{L}\p{N}]$/u;
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function clientIpHash(req) {
  const ip = String(req.headers['x-forwarded-for'] || req.headers['x-real-ip'] || '').split(',')[0].trim() || 'unknown';
  return sha256((process.env.IP_SALT || 'gl3d') + '|' + ip).slice(0, 32);
}

class HttpError extends Error { constructor(status, msg) { super(msg); this.status = status; } }

// Enveloppe commune : méthode, JSON, erreurs
function handler(methods, fn) {
  return async (req, res) => {
    res.setHeader('content-type', 'application/json; charset=utf-8');
    if (!methods.includes(req.method)) { res.setHeader('allow', methods.join(', ')); return res.status(405).json({ error: 'méthode non autorisée' }); }
    try {
      const out = await fn(req, res);
      if (!res.headersSent) res.status(200).json(out);
    } catch (e) {
      const status = e.status || 500;
      if (status >= 500) console.error(e);
      if (!res.headersSent) res.status(status).json({ error: status >= 500 ? 'erreur serveur' : e.message });
    }
  };
}

// Trace fantôme allégée : un point toutes les `every` secondes de course (+ le dernier)
function thinTrace(trace, every = 120) {
  if (!Array.isArray(trace) || trace.length < 3) return trace || [];
  const out = []; let last = -Infinity;
  trace.forEach((p, i) => { if (p[0] - last >= every || i === trace.length - 1) { out.push(p); last = p[0]; } });
  return out;
}

module.exports = { COURSES, CLASSES, LIMITS, parisDay, acceptedDays, sha256, newToken, safeEq, NAME_RE, UUID_RE, clientIpHash, HttpError, handler, thinTrace };

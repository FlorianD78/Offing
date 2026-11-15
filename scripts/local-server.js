'use strict';
// Serveur local sans Vercel : `npm run local` -> http://localhost:3000
// Base en mémoire par défaut ; avec SUPABASE_URL + SUPABASE_SECRET_KEY dans l'environnement, utilise ta vraie base.
const http = require('http');
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '..');
const PORT = Number(process.env.PORT) || 3000;

if (!process.env.SUPABASE_URL) { require('../api/_lib/db').setDb(require('./memdb').memDb()); console.log('Base en mémoire (aucune variable SUPABASE_URL)'); }
process.env.CRON_SECRET = process.env.CRON_SECRET || 'local';

const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.json': 'application/json', '.png': 'image/png', '.svg': 'image/svg+xml', '.ico': 'image/x-icon' };

http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const m = url.pathname.match(/^\/api\/([a-z]+)$/);
  if (m) {
    const file = path.join(ROOT, 'api', m[1] + '.js');
    if (!fs.existsSync(file)) { res.writeHead(404); return res.end('{"error":"introuvable"}'); }
    let raw = ''; for await (const c of req) raw += c;
    req.query = Object.fromEntries(url.searchParams);
    try { req.body = raw ? JSON.parse(raw) : undefined; } catch (e) { req.body = undefined; }
    res.status = (s) => { res.statusCode = s; return res; };
    res.json = (j) => { if (!res.getHeader('content-type')) res.setHeader('content-type', 'application/json'); res.end(JSON.stringify(j)); return res; };
    return require(file)(req, res);
  }
  const f = path.join(ROOT, 'public', url.pathname === '/' ? 'index.html' : path.normalize(url.pathname));
  if (!f.startsWith(path.join(ROOT, 'public')) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end('404'); }
  res.writeHead(200, { 'content-type': TYPES[path.extname(f)] || 'application/octet-stream' });
  fs.createReadStream(f).pipe(res);
}).listen(PORT, () => console.log(`Offing : http://localhost:${PORT}`));

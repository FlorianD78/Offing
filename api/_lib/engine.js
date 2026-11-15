// Charge le moteur du jeu (public/index.html) dans une sandbox Node pour rejouer les courses.
// Le rendu 3D, le DOM et l'audio sont remplacés par des « bouchons » neutres : seule la simulation tourne.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

function stub(name = 'stub') {
  const target = function () {};
  return new Proxy(target, {
    get(t, p) {
      if (p === Symbol.toPrimitive) return (hint) => (hint === 'string' ? '' : 0);
      if (p === Symbol.iterator) return function* () {};
      if (p === 'then') return undefined;
      if (typeof p === 'symbol') return undefined;
      if (Object.prototype.hasOwnProperty.call(t, p)) return t[p];
      const v = stub(name + '.' + p);
      try { Object.defineProperty(t, p, { value: v, writable: true, configurable: true }); } catch (e) { /* ignore */ }
      return v;
    },
    set(t, p, v) {
      try { Object.defineProperty(t, p, { value: v, writable: true, configurable: true }); } catch (e) { try { Reflect.set(t, p, v); } catch (e2) { /* ignore */ } }
      return true;
    },
    has() { return true; },
    apply() { return stub(name + '()'); },
    construct() { return stub('new ' + name); },
  });
}

function memStorage() {
  const m = new Map();
  return {
    getItem: (k) => (m.has(k) ? m.get(k) : null),
    setItem: (k, v) => { m.set(k, String(v)); },
    removeItem: (k) => { m.delete(k); },
    clear: () => m.clear(),
    key: (i) => Array.from(m.keys())[i] ?? null,
    get length() { return m.size; },
  };
}

let ENGINE = null;
function loadEngine(htmlPath) {
  if (ENGINE) return ENGINE;
  const file = htmlPath || [path.join(process.cwd(), 'public', 'index.html'), path.join(__dirname, '..', '..', 'public', 'index.html')].find(f => fs.existsSync(f));
  if (!file) throw new Error('public/index.html introuvable');
  const html = fs.readFileSync(file, 'utf8');
  const i = html.indexOf('<script>', html.indexOf('three.min.js'));
  const j = html.lastIndexOf('</script>');
  if (i < 0 || j < 0) throw new Error('script du jeu introuvable');
  const code = html.slice(i + 8, j);
  const noop = () => 0;
  const sandbox = {
    console: { log: noop, warn: noop, error: noop, info: noop },
    THREE: stub('THREE'),
    document: stub('document'),
    navigator: stub('navigator'),
    location: { hostname: 'server', href: 'https://server/', search: '' },
    localStorage: memStorage(),
    sessionStorage: memStorage(),
    performance: { now: () => Date.now() },
    requestAnimationFrame: noop, cancelAnimationFrame: noop,
    setTimeout: noop, clearTimeout: noop, setInterval: noop, clearInterval: noop,
    addEventListener: noop, removeEventListener: noop, dispatchEvent: noop,
    matchMedia: () => ({ matches: false, addEventListener: noop, addListener: noop }),
    getComputedStyle: stub('getComputedStyle'),
    Image: function () { return stub('Image'); },
    devicePixelRatio: 1, innerWidth: 1280, innerHeight: 800,
    structuredClone, atob, btoa, TextEncoder, TextDecoder, URL, URLSearchParams,
    fetch: undefined, AudioContext: undefined, webkitAudioContext: undefined,
  };
  sandbox.window = sandbox; sandbox.self = sandbox; sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(code, sandbox, { filename: 'game.js', timeout: 20000 });
  if (!sandbox.__ENGINE) throw new Error('moteur non exposé (window.__ENGINE)');
  ENGINE = sandbox.__ENGINE;
  return ENGINE;
}

module.exports = { loadEngine };

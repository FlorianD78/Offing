"""Générateur paramétrique des modèles 3D Offing (IMOCA, Class40, Mini 6.50 série, Mini proto).
Coque à bouchains, étrave « scow » (cuillère arrondie), rouf, cockpit, quille + bulbe, safrans jumeaux, foils, accastillage.
Repère jeu : x tribord, y haut (flottaison y = 0), z vers l'arrière (étrave en z = -L/2). Unités : mètres réels
(Class40 : divisé par C40V à l'export car le gréement du jeu est celui du Mini mis à l'échelle non uniforme)."""
import json, math, struct, base64, sys
import numpy as np
from scipy.interpolate import PchipInterpolator as P

def pch(pts):
    a = np.array(pts, float); f = P(a[:, 0], a[:, 1], extrapolate=True); return lambda d: f(np.clip(d, a[0, 0], a[-1, 0]))

class Mesh:
    def __init__(s): s.v = []; s.f = []; s.uv = []
    def add_v(s, p, uv=None): s.v.append(p); s.uv.append(uv if uv is not None else (0, 0)); return len(s.v) - 1
    def grid(s, rings, uvs=None, close=False):
        """rings : liste de polylignes (même nombre de points), reliées deux à deux"""
        base = len(s.v); m = len(rings[0])
        for i, r in enumerate(rings):
            for j, p in enumerate(r): s.add_v(p, None if uvs is None else uvs[i][j])
        for i in range(len(rings) - 1):
            for j in range(m - (0 if close else 1)):
                j2 = (j + 1) % m; a = base + i * m + j; b = base + i * m + j2; c = a + m; d = b + m
                s.f += [(a, c, b), (b, c, d)]
    def fan(s, ring, center):
        c = s.add_v(center); base = len(s.v)
        for p in ring: s.add_v(p)
        n = len(ring)
        for j in range(n): s.f.append((c, base + j, base + (j + 1) % n))
    def merge(s, o):
        b = len(s.v); s.v += o.v; s.uv += o.uv; s.f += [(a + b, c + b, d + b) for a, c, d in o.f]
    def arrays(s): return np.array(s.v, float), np.array(s.f, np.int64), np.array(s.uv, float)

def orient_out(m, ref):
    """oriente chaque face pour que sa normale s'éloigne de ref(centre) (point intérieur)"""
    v, f, _ = m.arrays(); t = v[f]; c = t.mean(1); n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    flip = (n * (c - ref(c))).sum(1) < 0; f[flip] = f[flip][:, [0, 2, 1]]; m.f = [tuple(x) for x in f]

def solid_orient(m):
    v, f, _ = m.arrays(); t = v[f]; vol = np.einsum('ij,ij->i', t[:, 0], np.cross(t[:, 1], t[:, 2])).sum()
    if vol < 0: m.f = [(a, c, b) for a, b, c in m.f]

# ---------------------------------------------------------------- primitives
def frame(tan):
    t = np.array(tan, float); t /= np.linalg.norm(t); up = np.array([0, 1, 0.]) if abs(t[1]) < 0.9 else np.array([1, 0, 0.])
    a = np.cross(t, up); a /= np.linalg.norm(a); b = np.cross(a, t); return a, b

def tube(path, r, n=8, cap=True):
    m = Mesh(); path = np.array(path, float); rings = []
    for i, p in enumerate(path):
        tg = path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]; a, b = frame(tg)
        rr = r(i / (len(path) - 1)) if callable(r) else r
        rings.append([p + rr * (math.cos(k / n * 2 * math.pi) * a + math.sin(k / n * 2 * math.pi) * b) for k in range(n)])
    m.grid(rings, close=True)
    if cap: m.fan(rings[0][::-1], path[0]); m.fan(rings[-1], path[-1])
    solid_orient(m); return m

def cyl(p0, p1, r, n=12): return tube([p0, p1], r, n)

def box(c, s):
    m = Mesh(); c = np.array(c, float); h = np.array(s, float) / 2
    P = [c + h * np.array([x, y, z]) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
    for q in [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]:
        i = [m.add_v(P[k]) for k in q]; m.f += [(i[0], i[1], i[2]), (i[0], i[2], i[3])]
    solid_orient(m); return m

def naca(nc, t):
    """profil symétrique NACA 00xx : nc points sur le contour fermé (x de 0 à 1 le long de la corde)"""
    out = []
    for k in range(nc):
        th = k / nc * 2 * math.pi; x = 0.5 * (1 + math.cos(th)); y = 5 * t * (0.2969 * math.sqrt(x) - 0.126 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - 0.1036 * x ** 4)
        out.append((x, y if th < math.pi else -y))
    return out

def blade(path, chord, thick, nc=16, le_frac=0.3, side=None):
    """aile le long d'une ligne d'envergure path (points 3D) ; corde dans la direction z (bord d'attaque vers -z)"""
    path = np.array(path, float); m = Mesh(); rings = []; prof = naca(nc, thick)
    for i, p in enumerate(path):
        u = i / (len(path) - 1); tg = path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]; tg /= np.linalg.norm(tg)
        zc = np.array([0, 0, 1.]); nrm = np.cross(tg, zc); nrm /= np.linalg.norm(nrm) + 1e-9
        c = chord(u) if callable(chord) else chord
        rings.append([p + zc * (x - le_frac) * c + nrm * y * c for x, y in prof])
    m.grid(rings, close=True); m.fan(rings[0][::-1], path[0]); m.fan(rings[-1], path[-1]); solid_orient(m); return m

def revolve(profile, axis_p, axis_d, n=16):
    """profil (s, r) le long d'un axe"""
    a, b = frame(axis_d); d = np.array(axis_d, float) / np.linalg.norm(axis_d); m = Mesh(); rings = []
    for s, r in profile:
        c = np.array(axis_p) + d * s
        rings.append([c + max(r, 1e-4) * (math.cos(k / n * 2 * math.pi) * a + math.sin(k / n * 2 * math.pi) * b) for k in range(n)])
    m.grid(rings, close=True); solid_orient(m); return m

def bulb(cz, cy, L, D, n=16, ns=18):
    prof = []
    for k in range(ns + 1):
        s = k / ns; r = D / 2 * (math.sin(math.pi * s) ** 0.6 if s < 0.4 else math.sin(math.pi * (0.4 + (s - 0.4) * 0.6 / 0.6 * 0.6 / 0.6)) ** 0.6)
        r = D / 2 * (1 - (1 - min(1, s / 0.38)) ** 2) ** 0.5 * (1 - max(0, (s - 0.45) / 0.55) ** 1.6)
        prof.append((s * L, r))
    return revolve(prof, [0, cy, cz - L * 0.42], [0, 0, 1], n)

def winch(p, r, h, n=14):
    m = cyl(p, [p[0], p[1] + h, p[2]], r, n); m.merge(cyl([p[0], p[1] + h, p[2]], [p[0], p[1] + h * 1.25, p[2]], r * 0.55, n)); return m

# ---------------------------------------------------------------- coque
class Hull:
    def __init__(s, C):
        s.C = C; s.L = C['L']
        s.hB = C['hB']; s.yD = pch(C['yD']); s.yK = pch(C['yK']); s.yC = pch(C['yC']); s.cR = pch(C['cR'])
    def z(s, d): return -s.L / 2 + d
    def sec(s, d):
        C = s.C; bD = float(s.hB(d)); bC = bD * float(s.cR(d)); yD = float(s.yD(d)); yC = min(float(s.yC(d)), yD - 0.02); yK = min(float(s.yK(d)), yC)
        return dict(d=d, z=s.z(d), bD=bD, bC=bC, yD=yD, yC=yC, yK=yK)
    def bottom_pts(s, S, nb):
        e = s.C.get('dead', 1.7); out = []
        for k in range(nb + 1):
            x = S['bC'] * (2 * k / nb - 1); f = abs(x) / max(S['bC'], 1e-6)
            out.append((x, S['yK'] + (S['yC'] - S['yK']) * f ** e))
        return out
    def top_pts(s, S, nt, side):
        bulge = s.C.get('bulge', 0.04) * S['bD'] / max(s.C['B'] / 2, 1e-6); out = []
        for k in range(nt + 1):
            f = k / nt; x = S['bC'] + (S['bD'] - S['bC']) * f + bulge * math.sin(math.pi * f); y = S['yC'] + (S['yD'] - S['yC']) * f ** 1.05
            out.append((side * x, y))
        return out
    def deck_pts(s, S, nd):
        C = s.C; ck = C['cock']; z = S['z']; dep = ck['dep'] * sm(ck['z0'], ck['z0'] + 0.3, z) * (1 - sm(ck['z1'] - 0.3, ck['z1'], z)); out = []
        xi = min(ck['xi'], 0.7 * S['bD'])
        for k in range(nd + 1):
            x = S['bD'] * (1 - 2 * k / nd); ax = abs(x); y = S['yD'] + C['cam'] * (1 - (ax / max(S['bD'], 1e-6)) ** 2)
            edge = 0.05 * S['bD'] / (C['B'] / 2); y -= 0.0 if ax < S['bD'] - edge else 0.03 * (ax - (S['bD'] - edge)) / max(edge, 1e-6)
            if dep > 0 and ax < xi: y -= dep * sm(xi, xi - 0.08 * C['B'] / 5.85, ax)
            out.append((x, y))
        return out

def sm(a, b, x):
    if a == b: return 1.0 if x >= b else 0.0
    t = min(1, max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t)

def hull_parts(C, lod):
    H = Hull(C); L = C['L']; ns, nb, nt, nd = (150, 26, 10, 34) if lod == 'hi' else (56, 12, 4, 16)
    # stations resserrées à l'étrave (nez arrondi)
    u = np.linspace(0, 1, ns + 1); ds = L * (u ** 1.9)
    secs = [H.sec(d) for d in ds]
    parts = {}
    def mk(name, ringfn, uvfn=None):
        m = Mesh(); rings = []; uvs = []
        for S in secs:
            r = ringfn(S); rings.append([(x, y, S['z']) for x, y in r])
            if uvfn: uvs.append([uvfn(S, x, y) for x, y in r])
        m.grid(rings, uvs if uvfn else None); parts[name] = m; return m
    tvu = lambda S, x, y: (1 - S['d'] / L, min(1, max(0, (y - min(S['yC'], 0)) / max(S['yD'] - min(S['yC'], 0), 1e-3))))
    mk('hull_bottom', lambda S: H.bottom_pts(S, nb))
    mk('hull_topS', lambda S: H.top_pts(S, nt, 1), tvu); mk('hull_topP', lambda S: H.top_pts(S, nt, -1), tvu)
    mk('hull_deck', lambda S: H.deck_pts(S, nd))
    # tableau arrière : contour fermé à la dernière station
    S = secs[-1]; ring = [(x, y) for x, y in H.bottom_pts(S, nb)] + [(x, y) for x, y in H.top_pts(S, nt, 1)[1:]] + [(x, y) for x, y in H.deck_pts(S, nd)[1:-1]] + [(x, y) for x, y in H.top_pts(S, nt, -1)[::-1][:-1]]
    e = Mesh(); cx = np.mean([p[0] for p in ring]); cy = np.mean([p[1] for p in ring]); e.fan([(x, y, S['z']) for x, y in ring], (cx, cy, S['z']))
    S0 = secs[0]
    if S0['bD'] > 0.02:   # étrave scow : petit masque frontal arrondi
        ring = [(x, y) for x, y in H.bottom_pts(S0, nb)] + [(x, y) for x, y in H.top_pts(S0, nt, 1)[1:]] + [(x, y) for x, y in H.deck_pts(S0, nd)[1:-1]] + [(x, y) for x, y in H.top_pts(S0, nt, -1)[::-1][:-1]]
        cx = np.mean([p[0] for p in ring]); cy = np.mean([p[1] for p in ring]); e.fan([(x, y, S0['z']) for x, y in ring], (cx, cy, S0['z']))
    parts['hull_ends'] = e
    mid = lambda c: np.stack([np.zeros(len(c)), np.array([(H.sec(min(L, max(0, z + L / 2)))['yK'] + H.sec(min(L, max(0, z + L / 2)))['yD']) / 2 for z in c[:, 2]]), c[:, 2]], 1)
    for k in ('hull_bottom', 'hull_topS', 'hull_topP'): orient_out(parts[k], mid)
    orient_out(parts['hull_deck'], lambda c: c - np.array([0, 5, 0])); orient_out(parts['hull_ends'], lambda c: np.stack([c[:, 0], c[:, 1], np.zeros(len(c))], 1))
    return parts, H

def coach(C, H, lod):
    R = C['roof']; n = 40 if lod == 'hi' else 14; nw = 12 if lod == 'hi' else 6; m = Mesh(); g = Mesh(); rings = []
    zs = np.linspace(R['z0'], R['z1'], n + 1)
    for z in zs:
        d = z + H.L / 2; S = H.sec(d); f = (z - R['z0']) / (R['z1'] - R['z0'])
        hw = R['w0'] + (R['w1'] - R['w0']) * min(1, f / 0.35); hw = min(hw, S['bD'] * 0.85)
        top = S['yD'] + C['cam'] + R['h'] * (sm(0, R['front'], f)) * (1 - R.get('aftdrop', 0) * sm(0.75, 1, f))
        base = S['yD'] + C['cam'] * (1 - (hw / max(S['bD'], 1e-6)) ** 2) - 0.05
        ring = []
        for k in range(nw + 1):           # paroi bâbord -> toit -> paroi tribord
            a = k / nw; x = hw * (1 - 2 * a); crown = R['cam'] * (1 - (x / hw) ** 2); yt = top + crown
            ring.append((x * (1 - 0.06 * (1 - abs(1 - 2 * a))), yt))
        ring = [(hw, base)] + ring + [(-hw, base)]
        rings.append([(x, y, z) for x, y in ring])
    m.grid(rings); orient_out(m, lambda c: np.stack([np.zeros(len(c)), np.full(len(c), -3.0), c[:, 2]], 1))
    # face avant du rouf (fermeture) + vitrages latéraux
    S = H.sec(R['z0'] + H.L / 2); fr = rings[0]; cx = np.mean([p[0] for p in fr]); cy = np.mean([p[1] for p in fr]); m.fan(fr, (cx, cy, R['z0']))
    if R.get('aftclose'): fr = rings[-1]; cx = np.mean([p[0] for p in fr]); cy = np.mean([p[1] for p in fr]); m.fan(fr, (cx, cy, R['z1']))
    for side in (1, -1):
        for (za, zb) in R['win']:
            pts = []
            for z in np.linspace(za, zb, 6):
                i = int(round((z - R['z0']) / (R['z1'] - R['z0']) * n)); r = rings[max(0, min(n, i))]; p1 = r[0] if side > 0 else r[-1]; p2 = r[1] if side > 0 else r[-2]
                lo = np.array(p1) * 0.45 + np.array(p2) * 0.55; hi = np.array(p1) * 0.12 + np.array(p2) * 0.88
                pts.append((lo + [side * 0.012, 0, 0], hi + [side * 0.012, 0, 0]))
            g.grid([[p[0] for p in pts], [p[1] for p in pts]])
    fw = R.get('fwin')
    if fw:   # vitrage frontal
        r = rings[min(n, 2)]; k0 = int(len(r) * 0.22); k1 = int(len(r) * 0.78); a = [np.array(p) + [0, -0.02, -0.03] for p in r[k0:k1]]
        b = [np.array(p) + [0, -fw, -0.03 - fw * 0.6] for p in r[k0:k1]]; g.grid([b, a])
    return m, g

def deck_gear(C, H, lod):
    gear = Mesh(); dark = Mesh(); solar = Mesh(); n = 12 if lod == 'hi' else 7; L = H.L; B = C['B']
    for (x, z, onroof) in C['winches']:
        S = H.sec(z + L / 2); y = (S['yD'] + C['cam'] * 0.6) if not onroof else (S['yD'] + C['cam'] + C['roof']['h'] - 0.02)
        gear.merge(winch([x, y, z], C['wr'], C['wr'] * 1.1, n))
    # filières : chandeliers le long du livet + 2 lignes de vie, balcon avant et arrière
    st = C['stanch']; zs = np.arange(-L / 2 + st['d0'], L / 2 - st['d1'], st['step']); hgt = st['h']; rad = st['r']
    for side in (1, -1):
        tops = []; tops2 = []
        for z in zs:
            S = H.sec(z + L / 2); x = side * (S['bD'] - 0.04 * B / 5.85); y0 = S['yD'] - 0.01
            dark.merge(cyl([x, y0, z], [x * 1.01, y0 + hgt, z], rad, 6)); tops.append([x * 1.01, y0 + hgt, z]); tops2.append([x * 1.005, y0 + hgt * 0.5, z])
        S = H.sec(min(L, max(0.0, C['pulpit_d']))); zb = -L / 2 + C['pulpit_d']; xb = side * max(S['bD'] - 0.06, 0.05)
        path = [[0.0, S['yD'] + hgt, zb - 0.05], [xb * 0.7, S['yD'] + hgt, zb + 0.02], [xb, S['yD'] + hgt, zb + 0.25]] + tops
        dark.merge(tube(path, rad * 0.8, 6, cap=False)); dark.merge(tube([[xb, S['yD'], zb + 0.25], [xb, S['yD'] + hgt, zb + 0.25]], rad, 6))
        dark.merge(tube(tops2, rad * 0.6, 5, cap=False))
        Sb = H.sec(L - 0.05); dark.merge(tube([tops[-1], [side * (Sb['bD'] - 0.1), Sb['yD'] + hgt, L / 2 - 0.15], [side * 0.6 * Sb['bD'], Sb['yD'] + hgt, L / 2 - 0.12]], rad * 0.8, 6, cap=False))
    for (x, z, w, l, onroof) in C.get('solar', []):
        S = H.sec(z + L / 2); y = (S['yD'] + C['cam'] * (1 - (abs(x) / S['bD']) ** 2) + 0.02) if not onroof else (S['yD'] + C['cam'] + C['roof']['h'] * (1 - C['roof'].get('aftdrop', 0) * 0.3) + C['roof']['cam'] * 0.95 + 0.02)
        solar.merge(box([x, y, z], [w, 0.025, l]))
    for spec in C.get('extra', []):
        kind = spec[0]
        if kind == 'pedestal':
            _, z = spec; S = H.sec(z + L / 2); y = S['yD'] + C['cam'] - C['cock']['dep']
            dark.merge(cyl([0, y, z], [0, y + 0.85, z], 0.11, 10)); gear.merge(cyl([-0.32, y + 0.85, z], [0.32, y + 0.85, z], 0.05, 8))
            for k in (1, -1): dark.merge(cyl([k * 0.32, y + 0.85, z], [k * 0.32, y + 1.12, z + 0.08], 0.025, 6))
        if kind == 'hydro':
            _, x = spec; S = H.sec(L); z = L / 2 + 0.05; y = S['yD'] - 0.1
            dark.merge(tube([[x, y, z - 0.25], [x, y + 0.05, z + 0.25], [x, -0.65, z + 0.35]], 0.045, 8)); gear.merge(revolve([(0, 0.0), (0.06, 0.07), (0.4, 0.08), (0.55, 0.02)], [x, -0.65, z + 0.15], [0, 0, 1], 10))
            for a in (0, 2.1, 4.2): dark.merge(box([x + 0.16 * math.cos(a), -0.65 + 0.16 * math.sin(a), z + 0.72], [0.05, 0.05, 0.03]))
        if kind == 'tiller':
            _, z0, z1 = spec; S = H.sec(z1 + L / 2); y = S['yD'] + C['cam'] * 0.5 + 0.12
            dark.merge(box([0, y, (z0 + z1) / 2], [0.05 * B / 3, 0.05 * B / 3, abs(z1 - z0)]))
        if kind == 'hatch':
            _, z, w, l = spec; S = H.sec(z + L / 2); gear.merge(box([0, S['yD'] + C['cam'] + 0.01, z], [w, 0.03, l]))
        if kind == 'nose':   # protection d'étrave (pare-battage carbone)
            S = H.sec(0.25); dark.merge(box([0, S['yD'] - 0.02, -L / 2 + 0.12], [max(0.08, S['bD'] * 1.4), 0.05, 0.25]))
    return gear, dark, solar

def keel_mesh(C, lod):
    K = C['keel']; n = 24 if lod == 'hi' else 10; nc = 18 if lod == 'hi' else 10
    span = K['draft'] - K['root_d']   # du pivot au bas du bulbe
    yb = -span + K['bD'] / 2
    path = [[0, 0.25, 0], [0, yb * 0.5, K['sweep'] * 0.5], [0, yb, K['sweep']]]
    fin = blade(np.array([np.array(path[0]) + (np.array(path[2]) - np.array(path[0])) * k / n for k in range(n + 1)]), lambda u: K['c0'] + (K['c1'] - K['c0']) * u, K['th'], nc, 0.35)
    fin.merge(bulb(K['sweep'] + K['bL'] * 0.05, yb, K['bL'], K['bD'], 16 if lod == 'hi' else 10, 22 if lod == 'hi' else 10))
    if K.get('wings'):
        for s in (1, -1): fin.merge(blade([[0, yb, K['sweep'] + K['bL'] * 0.42], [s * K['wings'], yb + 0.03, K['sweep'] + K['bL'] * 0.5]], lambda u: 0.32 - 0.14 * u, 0.08, 10, 0.3))
    return fin

def rudder_mesh(C, lod):
    R = C['rudder']; n = 16 if lod == 'hi' else 6; x, y0, z = R['root']; ca = math.radians(R['cant']); ra = math.radians(R['rake'])
    p0 = np.array([x, y0, z]); dirv = np.array([math.sin(ca), -math.cos(ca) * math.cos(ra), math.sin(ra)])
    path = [p0 + dirv * R['span'] * k / n for k in range(n + 1)]
    m = blade(path, lambda u: R['c0'] + (R['c1'] - R['c0']) * u ** 1.4, R['th'], 14 if lod == 'hi' else 8, 0.3)
    m.merge(cyl(p0 + [0, R['stock'], 0], p0 + dirv * 0.15, R['th'] * R['c0'] * 0.45, 8))
    return m

def foil_mesh(C, lod):
    F = C['foil']; n = 40 if lod == 'hi' else 14
    pts = np.array(F['path'], float); t = np.linspace(0, 1, len(pts)); tt = np.linspace(0, 1, n + 1)
    path = np.stack([np.interp(tt, t, pts[:, k]) for k in range(3)], 1)
    from scipy.interpolate import CubicSpline
    cs = CubicSpline(t, pts, bc_type='natural'); path = cs(tt)
    return blade(path, lambda u: F['c0'] + (F['c1'] - F['c0']) * u ** 1.3, F['th'], 16 if lod == 'hi' else 8, 0.35)

# ---------------------------------------------------------------- classes (dimensions de jauge / bateaux récents)
def nose_round(W, Dn, p, body):
    """demi-largeur de pont : nez en super-ellipse (W à Dn de l'étrave), puis courbe de corps"""
    b = pch(body)
    def f(d):
        d = np.asarray(d, float)
        return np.where(d < Dn, W * np.clip(1 - np.clip(1 - d / Dn, 0, 1) ** p, 0, 1) ** (1 / p), b(d))
    return f

def nose_imoca(body):
    """IMOCA : largeur ≤ 1,12 m dans le premier mètre (jauge) -> nez parabolique arrondi, puis volume rapide"""
    b = pch(body)
    def f(d):
        d = np.asarray(d, float); return np.where(d < 1.0, 0.555 * (0.36 + 0.64 * np.sqrt(np.clip(d, 0, 1))), b(d))   # nez rond émoussé (0,40 m à l'étrave, 1,11 m à 1 m)
    return f

IMOCA = dict(L=18.28, B=5.85, cam=0.14, dead=1.5, bulge=0.05,
    hB=nose_imoca([(1.0, 0.555), (1.5, 0.86), (2.2, 1.22), (3.2, 1.62), (4.5, 2.0), (6.0, 2.34), (8.0, 2.66), (10.0, 2.85), (12.5, 2.925), (14.5, 2.91), (16.5, 2.82), (18.28, 2.7)]),
    yD=[(0, 1.66), (1.5, 1.6), (4, 1.48), (8, 1.28), (12, 1.1), (15, 1.0), (18.28, 0.94)],
    yK=[(0, 1.42), (0.5, 1.05), (1.2, 0.62), (2.4, 0.18), (4.0, -0.17), (6.5, -0.45), (9.0, -0.56), (11.5, -0.54), (14, -0.42), (16.5, -0.27), (18.28, -0.14)],
    yC=[(0, 1.42), (0.6, 1.25), (1.6, 0.92), (3, 0.6), (5, 0.32), (8, 0.12), (11, 0.06), (14, 0.08), (16.5, 0.14), (18.28, 0.2)],
    cR=[(0, 1.0), (0.8, 0.97), (2.5, 0.93), (6, 0.9), (11, 0.9), (18.28, 0.93)],
    cock=dict(z0=3.4, z1=7.6, dep=0.42, xi=1.25),
    roof=dict(z0=0.15, z1=6.4, w0=1.0, w1=1.55, h=0.62, cam=0.12, front=0.38, aftdrop=0.12, win=[(1.2, 3.0)], fwin=0.36, aftclose=False, mat='hull'),
    winches=[(1.75, 4.6, 0), (-1.75, 4.6, 0), (1.85, 6.6, 0), (-1.85, 6.6, 0), (0.85, 5.6, 1), (-0.85, 5.6, 1), (1.3, -1.2, 0), (-1.3, -1.2, 0)], wr=0.13,
    stanch=dict(d0=1.6, d1=0.5, step=2.2, h=0.62, r=0.022), pulpit_d=0.7,
    solar=[(1.45, -3.2, 0.7, 1.6, 0), (-1.45, -3.2, 0.7, 1.6, 0), (0.0, 3.2, 1.3, 1.6, 1)],
    extra=[('pedestal', 5.2), ('hydro', 1.35), ('hydro', -1.35), ('hatch', -3.6, 0.6, 0.6), ('nose',)],
    keel=dict(pivot=(0, -0.5, 0.35), root_d=0.5, draft=4.5, c0=0.82, c1=0.6, th=0.11, sweep=0.18, bL=3.7, bD=0.46),
    rudder=dict(root=(1.95, -0.15, 8.35), span=2.55, c0=0.46, c1=0.3, th=0.11, cant=12, rake=6, stock=1.1),
    foil=dict(root=(2.15, 0.2, -2.2), retract=(1.3, 0.75), c0=0.72, c1=0.3, th=0.13,
              path=[(-0.4, 0.45, 0), (-0.05, 0.18, 0.02), (1.0, -0.55, 0.05), (2.1, -1.35, 0.08), (2.9, -1.95, 0.1), (3.5, -2.15, 0.12), (4.1, -1.98, 0.14), (4.6, -1.6, 0.15)]),
)
C40 = dict(L=12.19, B=4.5, cam=0.1, dead=1.35, bulge=0.04,
    hB=nose_round(1.55, 1.7, 3.0, [(1.7, 1.55), (3.0, 1.9), (5.0, 2.17), (7.0, 2.25), (9.0, 2.24), (11.0, 2.18), (12.19, 2.1)]),
    yD=[(0, 1.42), (1.5, 1.36), (3.5, 1.26), (6.5, 1.08), (9.5, 0.92), (12.19, 0.8)],
    yK=[(0, 1.12), (0.35, 0.82), (0.9, 0.42), (1.8, 0.05), (3.2, -0.25), (5.5, -0.4), (8, -0.38), (10.5, -0.24), (12.19, -0.1)],
    yC=[(0, 1.12), (0.5, 0.95), (1.4, 0.62), (2.8, 0.32), (5, 0.1), (8, 0.04), (10.5, 0.08), (12.19, 0.14)],
    cR=[(0, 0.99), (1.5, 0.96), (4, 0.92), (8, 0.9), (12.19, 0.93)],
    cock=dict(z0=2.3, z1=5.0, dep=0.42, xi=0.95),
    roof=dict(z0=-1.0, z1=2.5, w0=0.95, w1=1.15, h=0.52, cam=0.07, front=0.25, aftdrop=0.0, win=[(-0.4, 1.4)], fwin=0.28, aftclose=True),
    winches=[(1.45, 3.0, 0), (-1.45, 3.0, 0), (1.55, 4.3, 0), (-1.55, 4.3, 0), (0.6, 2.25, 1), (-0.6, 2.25, 1)], wr=0.1,
    stanch=dict(d0=1.0, d1=0.35, step=1.8, h=0.6, r=0.018), pulpit_d=0.45,
    solar=[(0.0, 0.9, 1.1, 1.3, 1), (1.55, 1.2, 0.6, 1.2, 0), (-1.55, 1.2, 0.6, 1.2, 0)],
    extra=[('hatch', -2.6, 0.5, 0.5), ('nose',)],
    keel=dict(pivot=(0, -0.38, 0.3), root_d=0.38, draft=3.0, c0=0.62, c1=0.5, th=0.12, sweep=0.12, bL=2.5, bD=0.4),
    rudder=dict(root=(1.6, 0.55, 6.18), span=2.35, c0=0.36, c1=0.24, th=0.11, cant=6, rake=3, stock=0.35),
)
MINI = dict(L=6.5, B=3.0, cam=0.06, dead=1.3, bulge=0.025,
    hB=nose_round(0.82, 0.95, 3.0, [(0.95, 0.82), (1.9, 1.13), (3.0, 1.37), (4.2, 1.49), (5.3, 1.48), (6.5, 1.4)]),
    yD=[(0, 0.9), (1, 0.86), (2.5, 0.78), (4.5, 0.66), (6.5, 0.54)],
    yK=[(0, 0.7), (0.2, 0.5), (0.55, 0.22), (1.1, -0.02), (2.2, -0.18), (3.5, -0.22), (5, -0.17), (6.5, -0.05)],
    yC=[(0, 0.7), (0.3, 0.58), (0.9, 0.34), (1.8, 0.14), (3.5, 0.02), (5.5, 0.04), (6.5, 0.08)],
    cR=[(0, 0.99), (1, 0.96), (3, 0.92), (6.5, 0.93)],
    cock=dict(z0=0.45, z1=2.85, dep=0.3, xi=0.78),
    roof=dict(z0=-1.85, z1=0.45, w0=0.62, w1=0.76, h=0.36, cam=0.05, front=0.3, aftdrop=0.0, win=[(-1.3, -0.25)], fwin=0.16, aftclose=True),
    winches=[(0.98, 0.95, 0), (-0.98, 0.95, 0), (0.42, 0.3, 1), (-0.42, 0.3, 1)], wr=0.07,
    stanch=dict(d0=0.7, d1=0.2, step=1.15, h=0.45, r=0.013), pulpit_d=0.25,
    solar=[(0.3, -0.75, 0.5, 0.75, 1), (-0.3, -0.75, 0.5, 0.75, 1)],
    extra=[('nose',)],
    keel=dict(pivot=(0, -0.22, 0.15), root_d=0.22, draft=1.6, c0=0.44, c1=0.36, th=0.12, sweep=0.06, bL=1.25, bD=0.27),
    rudder=dict(root=(0.78, 0.42, 3.31), span=1.38, c0=0.27, c1=0.19, th=0.11, cant=4, rake=3, stock=0.18),
)
PROTO = dict(MINI, hB=nose_round(0.95, 0.85, 3.2, [(0.85, 0.95), (1.8, 1.22), (3.0, 1.43), (4.2, 1.5), (5.3, 1.48), (6.5, 1.42)]),
    yK=[(0, 0.68), (0.2, 0.46), (0.5, 0.2), (1.0, -0.02), (2.2, -0.17), (3.5, -0.2), (5, -0.15), (6.5, -0.04)],
    keel=dict(pivot=(0, -0.2, 0.1), root_d=0.2, draft=2.0, c0=0.4, c1=0.3, th=0.11, sweep=0.05, bL=1.3, bD=0.26),
    foil=dict(root=(1.18, 0.12, -0.85), retract=(0.55, 0.35), c0=0.3, c1=0.14, th=0.13,
              path=[(-0.25, 0.2, 0), (0.08, 0.03, 0.01), (0.5, -0.3, 0.02), (0.85, -0.68, 0.03), (1.05, -0.86, 0.04), (1.45, -0.86, 0.05), (1.75, -0.78, 0.05)]),
    solar=[(0.0, -0.75, 0.6, 0.8, 1)])

C40V = (1.5, 19.0 / 12.05, 12.19 / 6.5)

def build(C, lod, scale=None):
    parts, H = hull_parts(C, lod); roof, glass = coach(C, H, lod); gear, dark, solar = deck_gear(C, H, lod)
    parts.update(hull_roof=roof, glass=glass, gear=gear, dark=dark, solar=solar)
    K = C['keel']; parts['keel'] = keel_mesh(C, lod); parts['rudder'] = rudder_mesh(C, lod)
    if 'foil' in C: parts['foil'] = foil_mesh(C, lod)
    Sb = H.sec(0.0); Sm = H.sec(H.L / 2 - 0.5)
    meta = dict(roofMat=C['roof'].get('mat', 'roof'), keelPivot=list(K['pivot']), deckY=round(Sm['yD'], 3), bowY=round(Sb['yD'], 3), bowZ=round(-H.L / 2, 3), L=H.L, B=C['B'], draft=K['draft'])
    if 'foil' in C: meta['foilRoot'] = list(C['foil']['root']); meta['foilRetract'] = list(C['foil']['retract'])
    out = []
    sc = np.array(scale if scale else (1, 1, 1), float)
    for name, m in parts.items():
        v, f, uv = m.arrays()
        if not len(f): continue
        v = v / sc
        out.append(dict(name=name, v=v, f=f, uv=uv if name.startswith('hull_top') else None))
    if scale:
        for k in ('keelPivot', 'foilRoot'):
            if k in meta: meta[k] = (np.array(meta[k]) / sc).round(4).tolist()
        if 'foilRetract' in meta: meta['foilRetract'] = [meta['foilRetract'][0] / sc[0], meta['foilRetract'][1] / sc[1]]
        meta['bowY'] = round(meta['bowY'] / sc[1], 3); meta['deckY'] = round(meta['deckY'] / sc[1], 3); meta['scaleV'] = list(sc)
    return out, meta

def write(parts, meta):
    head = {'meta': meta, 'parts': []}; blobs = []; off = 0
    for p in parts:
        v = p['v']; mn = v.min(0); mx = v.max(0); q = np.round((v - mn) / np.maximum(mx - mn, 1e-9) * 65535).astype('<u2')
        i32 = len(v) > 65535; idx = p['f'].astype('<u4' if i32 else '<u2').ravel(); b = [q.tobytes(), idx.tobytes()]
        if p['uv'] is not None: b.append(np.round(np.clip(p['uv'], 0, 1) * 65535).astype('<u2').tobytes())
        head['parts'].append({'name': p['name'], 'nv': len(v), 'ni': len(idx), 'min': mn.round(5).tolist(), 'max': mx.round(5).tolist(), 'i32': i32, 'uv': p['uv'] is not None, 'off': off})
        for x in b:
            pad = (-len(x)) % 4; blobs.append(x + b'\0' * pad); off += len(x) + pad
    hj = json.dumps(head, separators=(',', ':')).encode(); hj += b' ' * ((-len(hj)) % 4)
    return struct.pack('<4sI', b'OFM1', len(hj)) + hj + b''.join(blobs)

if __name__ == '__main__':
    import os; od = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/boats/out'; os.makedirs(od, exist_ok=True)
    for cls, C, sc in [('imoca', IMOCA, None), ('c40', C40, C40V), ('mini', MINI, None), ('proto', PROTO, None)]:
        for lod in ('hi', 'lo'):
            parts, meta = build(C, lod, sc); bin_ = write(parts, meta)
            json.dump({'b64': base64.b64encode(bin_).decode()}, open(f'{od}/{cls}-{lod}.json', 'w'))
            print(cls, lod, len(bin_) // 1024, 'kB', {p['name']: len(p['f']) for p in parts})

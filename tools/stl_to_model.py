"""Convertit les STL de l'IMOCA (maquette en mm) en modèles allégés du jeu : public/models/imoca-hi.bin et imoca-lo.bin.
Usage : pip install numpy scipy fast-simplification ; puis, dans le dossier des STL :
  python3 tools/stl_to_model.py      (attend coque_pont.stl et apendice.stl dans le dossier courant)
Format OFM1 : en-tête JSON + positions quantifiées sur 16 bits + index + UV des bordés (lu par parseModelBin dans index.html).
"""
import sys, json, struct, numpy as np, fast_simplification as fs
sys.path.insert(0, __import__('os').path.dirname(__file__))
from stl_load import load, components
S = 18.28 / 973.9          # mm de maquette -> m (longueur IMOCA 18,28 m)
SX = 5.55 / 245.4          # largeur portée à 5,55 m (maquette RC plus étroite que la jauge)
ZWL = -18.5                # flottaison (mm maquette) : tirant d'eau de coque ≈ 0,55 m
YC = 487.0                 # milieu de coque (mm) -> z = 0

def mesh_of(tris):
    p = tris.reshape(-1, 3).astype(np.float64)
    key = np.round(p / 1e-3).astype(np.int64)
    u, idx, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    return p[idx], inv.reshape(-1, 3).astype(np.int64)

def cluster(v, f, cell):  # regroupement de sommets : robuste aux maillages non manifold (le simplificateur seul bloque)
    key = np.floor(v / cell).astype(np.int64); u, inv = np.unique(key, axis=0, return_inverse=True); inv = inv.ravel()
    nv = np.zeros((len(u), 3)); np.add.at(nv, inv, v); nv /= np.bincount(inv)[:, None]
    f2 = inv[f]; ok = (f2[:, 0] != f2[:, 1]) & (f2[:, 1] != f2[:, 2]) & (f2[:, 0] != f2[:, 2]); f2 = f2[ok]
    _, keep = np.unique(np.sort(f2, 1), axis=0, return_index=True); return nv, f2[np.sort(keep)]

def decimate(v, f, target, cell=None):
    if cell: v, f = cluster(v, f, cell)
    if len(f) <= target: return v, f
    v2, f2 = fs.simplify(v.astype(np.float32), f.astype(np.int32), target_reduction=1 - target / len(f))
    return v2.astype(np.float64), f2.astype(np.int64)

def to_game(v):  # (x, y long., z haut) maquette -> (x, y haut, z vers l'arrière) jeu, mètres
    return np.stack([v[:, 0] * SX, (v[:, 2] - ZWL) * S, -(v[:, 1] - YC) * S], 1)

def part(name, v, f, uv=None):
    used = np.unique(f); remap = -np.ones(len(v), np.int64); remap[used] = np.arange(len(used))
    return {'name': name, 'v': v[used], 'f': remap[f], 'uv': None if uv is None else uv[used]}

def hull_parts(target):
    v, f = mesh_of(load('coque_pont.stl'))
    v, f = decimate(v, f, target, 2.0 if target > 15000 else 4.0)
    # livet (hauteur du pont au bord) par tranche de longueur
    bins = np.linspace(0, 974, 50); sheer = np.zeros(len(bins))
    for i, y in enumerate(bins):
        q = v[np.abs(v[:, 1] - y) < 12]
        if len(q): hb = np.abs(q[:, 0]).max(); e = q[np.abs(q[:, 0]) > 0.9 * hb]; sheer[i] = e[:, 2].max()
    shz = lambda y: np.interp(y, bins, sheer)
    tri = v[f]; c = tri.mean(1); n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    cls = np.full(len(f), 'topS', dtype=object)
    cls[c[:, 0] < 0] = 'topP'
    cls[c[:, 2] > shz(c[:, 1]) + 2.5] = 'roof'
    cls[(np.abs(n[:, 2]) > 0.55) & (c[:, 2] > ZWL + 25)] = 'deck'   # orientation des faces non fiable : on prend |nz|
    cls[c[:, 2] < ZWL + 1] = 'bottom'
    cls[(np.abs(n[:, 1]) > 0.8) & (c[:, 1] < 15) & (c[:, 2] >= ZWL + 1)] = 'ends'   # tableau arrière
    g = to_game(v)
    uv = np.stack([v[:, 1] / 974.0, np.clip((v[:, 2] - ZWL) / np.maximum(shz(v[:, 1]) - ZWL, 1), 0, 1)], 1)
    out = []
    for k in ['deck', 'roof', 'topS', 'topP', 'bottom', 'ends']:
        m = cls == k
        if m.any(): out.append(part('hull_' + k, g, f[m], uv if k in ('topS', 'topP') else None))
    return out, sheer

AP = load('apendice.stl'); _, LAB, _, _ = components(AP)
def comp_mesh(ci, target):
    v, f = mesh_of(AP[LAB == ci]); return decimate(v, f, target, 0.8 if target > 1000 else 1.4)

def keel_part(target):
    v, f = comp_mesh(3, target)
    z = v[:, 2].copy(); zb = -385.0; d = 172.0   # voile raccourci : tirant d'eau total ≈ 4,5 m, bulbe conservé
    fin = z > zb; v[fin, 2] = -45 + (z[fin] + 45) * ((zb + d + 45) / (zb + 45)); v[~fin, 2] = z[~fin] + d
    g = to_game(v); piv = to_game(np.array([[0, 475, -45.0]]))[0]
    return part('keel', g - piv, f), piv

def foil_part(target):
    v, f = comp_mesh(4, target)
    g = to_game(v); root = to_game(np.array([[55.0, 546, -9]]))[0]
    return part('foil', g - root, f), root

def rudder_part(target):
    v, f = comp_mesh(5, target); return part('rudder', to_game(v), f)

def write(path, parts, meta):
    head = {'meta': meta, 'parts': []}; blobs = []; off = 0
    for p in parts:
        v = p['v'].astype(np.float64); mn = v.min(0); mx = v.max(0); q = np.round((v - mn) / np.maximum(mx - mn, 1e-9) * 65535).astype('<u2')
        i32 = len(v) > 65535; idx = p['f'].astype('<u4' if i32 else '<u2').ravel()
        b = [q.tobytes(), idx.tobytes()]; uvb = b''
        if p['uv'] is not None: uvb = np.round(np.clip(p['uv'], 0, 1) * 65535).astype('<u2').tobytes(); b.append(uvb)
        e = {'name': p['name'], 'nv': len(v), 'ni': len(idx), 'min': mn.round(5).tolist(), 'max': mx.round(5).tolist(), 'i32': i32, 'uv': p['uv'] is not None, 'off': off}
        for x in b:
            pad = (-len(x)) % 4; blobs.append(x + b'\0' * pad); off += len(x) + pad
        head['parts'].append(e)
    hj = json.dumps(head, separators=(',', ':')).encode(); hj += b' ' * ((-len(hj)) % 4)
    with open(path, 'wb') as fh: fh.write(struct.pack('<4sI', b'OFM1', len(hj))); fh.write(hj); [fh.write(x) for x in blobs]

for lvl, T in [('hi', dict(hull=32000, keel=2500, foil=2500, rud=700)), ('lo', dict(hull=7000, keel=500, foil=600, rud=200))]:
    hp, sheer = hull_parts(T['hull']); kp, kpiv = keel_part(T['keel']); fp, froot = foil_part(T['foil']); rp = rudder_part(T['rud'])
    meta = {'keelPivot': kpiv.round(4).tolist(), 'foilRoot': froot.round(4).tolist(), 'deckY': float(((sheer.max() - ZWL) * S).round(3)), 'bowY': round((79 - ZWL) * S, 3), 'scale': [SX, S], 'zwl': ZWL}
    write(ff'public/models/imoca-{lvl}.bin', hp + [kp, fp, rp], meta)
    print(lvl, {p['name']: len(p['f']) for p in hp + [kp, fp, rp]}, meta)

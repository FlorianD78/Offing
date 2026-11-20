# Conversion du modèle IMOCA (OBJ + MTL) vers les fichiers models/imoca-{hi,lo}.json du jeu.
# Usage : pip install numpy fast-simplification ; python3 scripts/obj2ofm.py assets/models/imoca60_lowpoly.obj assets/models/imoca60_lowpoly.mtl public/models
import collections, numpy as np
def load(path):
    V=[]; parts=collections.OrderedDict(); cur=None; mat={}
    for line in open(path):
        if line.startswith('v '): V.append([float(t) for t in line.split()[1:4]])
        elif line.startswith('o '): cur=line[2:].strip(); parts[cur]=[]
        elif line.startswith('usemtl'): mat[cur]=line.split()[1]
        elif line.startswith('f '):
            idx=[int(t.split('/')[0]) for t in line.split()[1:]]
            idx=[i-1 if i>0 else len(V)+i for i in idx]
            for k in range(1,len(idx)-1): parts[cur].append((idx[0],idx[k],idx[k+1]))
    V=np.array(V)
    G=np.stack([V[:,2], V[:,1], 9.14-V[:,0]],1)  # jeu : x=tribord, y=haut, z=arrière (étrave en -z)
    return G, parts, mat

# OBJ (X avant, Y haut, Z tribord, X=0 à l'arrière) → OFM1 v2 du jeu (x tribord, y haut, z vers l'arrière, étrave en −z)
# Pièces regroupées par (groupe animé, matériau) ; arêtes vives (> 40°) conservées en dupliquant les sommets ;
# version « lo » : petites pièces retirées, grosses simplifiées, matériaux fixes fusionnés en couleurs de sommets.
import sys, json, struct, base64, math, collections, numpy as np
import fast_simplification as fs
OBJ, MTL, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
G, parts, mat = load(OBJ)
# franc-bord réduit : la coque (jusqu'au pont, y ≤ 2,3 m) est écrasée verticalement de FB au-dessus de la flottaison ;
# tout ce qui est plus haut (mât, gréement, bôme) descend d'autant, sans être déformé
FB, YD = 0.8, 2.3
FOIL_S = 1.3  # échelle des foils
def fy(y): return np.where(y <= 0, y, np.where(y <= YD, y * FB, y - YD * (1 - FB)))
G[:, 1] = fy(G[:, 1])
Kd = {}; Ns = {}; cur = None
for line in open(MTL):
    t = line.split()
    if not t: continue
    if t[0] == 'newmtl': cur = t[1]
    elif t[0] == 'Kd': Kd[cur] = [float(x) for x in t[1:4]]
    elif t[0] == 'Ns': Ns[cur] = float(t[1])
SKIP = {'mainsail', 'mainsail_battens', 'mainsail_bands', 'mainsail_patches', 'jib_J2', 'jib_J2_battens', 'jib_J2_bands', 'foil_port'}
GROUP = {'mast': 'mast', 'masthead': 'mast', 'spreaders': 'mast', 'outriggers': 'rig', 'rigging': 'rig', 'boom': 'boom', 'boom_fittings': 'boom',
         'keel_fin': 'keel', 'keel_bulb': 'keel', 'foil_starboard': 'foil'}
MAST_BASE = np.array([0, float(fy(1.23)), 0.94]); MAST_TOP = np.array([0, float(fy(28.79)), 1.87]); RAKE = math.atan2(MAST_TOP[2] - MAST_BASE[2], MAST_TOP[1] - MAST_BASE[1])
PIV = {'mast': MAST_BASE, 'boom': np.array([0, float(fy(3.3)), 1.135]), 'keel': np.array([0, -0.5, 1.24])}
META = {'v': 2, 'keelPivot': PIV['keel'].tolist(), 'boomPivot': PIV['boom'].tolist(), 'mastBase': MAST_BASE.tolist(), 'mastRake': RAKE, 'foilRoot': [0, 0, 0], 'bowY': float(fy(2.1)), 'deckY': float(fy(1.6))}
LO_DROP = {'coachroof_hatch', 'companionway_glass', 'companionway_frame', 'jammers', 'stern_round_hatch', 'stern_round_hatch_glass', 'winches', 'traveller',
           'deck_hatches', 'deck_hatch_glass', 'rudder_stock_pads', 'stern_gear', 'bow_fittings', 'nav_lights', 'masthead', 'boom_fittings', 'cockpit_seats', 'solar_panel', 'coachroof_windows'}
LO_TARGET = {'deck': 0.22, 'bottom': 0.4, 'foil_starboard': 0.28, 'coachroof': 0.35, 'keel_bulb': 0.3, 'outriggers': 0.35, 'mast': 0.45, 'livery_swoosh': 0.5,
             'stern_blocks': 0.3, 'spreaders': 0.5, 'hull': 0.7, 'keel_fin': 0.5, 'rudder_starboard': 0.6, 'rudder_port': 0.6, 'cockpit_coaming': 0.5, 'mast_collar': 0.5, 'keel_fairing': 0.5, 'rigging': 1.0}
PERBOAT = {'Hull_White': 'hull', 'Livery_Coral': 'acc', 'Foil_Coral': 'foil'}

def to_local(P, grp):
    if grp == 'mast':  # repère du mât : axe du mât = +y local (le jeu fait tourner ce groupe autour de son axe)
        Q = P - MAST_BASE; c, s = math.cos(RAKE), math.sin(RAKE)  # inverse de la rotation.x = RAKE
        return np.stack([Q[:, 0], Q[:, 1] * c + Q[:, 2] * s, -Q[:, 1] * s + Q[:, 2] * c], 1)
    if grp in PIV: return P - PIV[grp]
    return P

def crease(V, F, ang=40):
    # duplique les sommets dont les faces voisines forment un angle > ang (arêtes vives), pour des normales nettes
    n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]); ln = np.linalg.norm(n, axis=1, keepdims=True); n = n / np.maximum(ln, 1e-12)
    inc = collections.defaultdict(list)
    for fi, f in enumerate(F):
        for k in range(3): inc[f[k]].append((fi, k))
    cosT = math.cos(math.radians(ang)); NV = []; NF = F.copy()
    for v, lst in inc.items():
        groups = []
        for fi, k in lst:
            for g in groups:
                if np.dot(n[fi], g['n']) > cosT: g['f'].append((fi, k)); g['n'] = g['n'] + n[fi]; g['n'] /= max(np.linalg.norm(g['n']), 1e-12); break
            else: groups.append({'n': n[fi].copy(), 'f': [(fi, k)]})
        for g in groups:
            idx = len(NV); NV.append(V[v])
            for fi, k in g['f']: NF[fi, k] = idx
    return np.array(NV, dtype=np.float64), NF

def part_arrays(name):
    T = np.array(parts[name], dtype=np.int64); ids = np.unique(T); remap = {o: i for i, o in enumerate(ids)}
    V = G[ids]; F = np.vectorize(remap.get)(T); return V, F

def build(level):
    buckets = collections.OrderedDict()  # (grp, key) -> [V list, F list, col list]
    for name in parts:
        if name in SKIP or (level == 'lo' and name in LO_DROP): continue
        grp = GROUP.get(name, 'static'); m = mat[name]; V, F = part_arrays(name)
        if name == 'foil_starboard':  # foils agrandis autour de leur sortie de coque (point le plus intérieur)
            R0 = V[V[:, 0] < V[:, 0].min() + 0.2].mean(0); V = R0 + (V - R0) * FOIL_S
        if level == 'lo' and LO_TARGET.get(name, 1) < 1 and len(F) > 60:
            V2, F2 = fs.simplify(V.astype(np.float32), F.astype(np.int32), target_reduction=1 - LO_TARGET[name])
            if len(F2) > 8: V, F = V2.astype(np.float64), F2.astype(np.int64)
        V = to_local(V, grp)
        if level == 'lo' and m not in PERBOAT: key = 'vcol'
        else: key = PERBOAT.get(m, m)
        if grp == 'foil': key = 'foil'
        b = buckets.setdefault((grp, key), [[], [], []]); off = sum(len(v) for v in b[0])
        b[0].append(V); b[1].append(F + off); b[2].append(np.tile(Kd.get(m, [0.5, 0.5, 0.5]), (len(V), 1)))
    out = []
    for (grp, key), (Vs, Fs, Cs) in buckets.items():
        V = np.concatenate(Vs); F = np.concatenate(Fs); C = np.concatenate(Cs)
        # couleurs par sommet suivies à travers la duplication des arêtes
        V2, F2 = crease(V, F); col = None
        if key == 'vcol':
            col = np.zeros((len(V2), 3)); col[F2.reshape(-1)] = C[F.reshape(-1)]
        out.append((f'{grp}:{key}', grp, key, V2, F2, col))
    return out

def pack(items):
    head = {'meta': META, 'v': 2, 'parts': []}; blob = bytearray()
    pad = lambda: blob.extend(b'\0' * ((4 - len(blob) % 4) % 4))
    for name, grp, key, V, F, col in items:
        mn = V.min(0); mx = V.max(0); rng = np.where(mx - mn > 1e-9, mx - mn, 1)
        q = np.round((V - mn) / rng * 65535).astype('<u2'); i32 = len(V) > 65535
        p = {'name': name, 'grp': grp, 'mat': key, 'nv': len(V), 'ni': int(F.size), 'i32': i32, 'min': mn.tolist(), 'max': mx.tolist(), 'off': len(blob)}
        blob.extend(q.tobytes()); pad(); blob.extend(F.astype('<u4' if i32 else '<u2').reshape(-1).tobytes()); pad()
        if col is not None: p['col'] = True; blob.extend(np.round(np.clip(col, 0, 1) * 255).astype('u1').reshape(-1).tobytes()); pad()
        head['parts'].append(p)
    h = json.dumps(head, separators=(',', ':')).encode(); h += b' ' * ((4 - len(h) % 4) % 4)
    return b'OFM1' + struct.pack('<I', len(h)) + h + bytes(blob)

mats = {k: {'kd': Kd[k], 'ns': Ns.get(k, 100)} for k in Kd}
for level in ['hi', 'lo']:
    items = build(level); buf = pack(items)
    tris = sum(len(it[4]) for it in items)
    json.dump({'format': 'OFM1', 'b64': base64.b64encode(buf).decode(), 'mats': mats}, open(f'{OUT}/imoca-{level}.json', 'w'), separators=(',', ':'))
    print(level, 'meshes', len(items), 'tris', tris, 'verts', sum(len(it[3]) for it in items), 'bytes', len(buf), [(it[0], len(it[4])) for it in items])

# Mini 6.50 et Class40 dérivés du modèle IMOCA (OBJ) : coque, pont, rouf, cockpit et accastillage retaillés station par station
# sur les formes de chaque classe (demi-largeur, hauteur de pont, fond), sans outriggers, foils, arche, mât ni gréement IMOCA
# (le jeu garde le mât, les voiles et le bout-dehors propres à chaque classe). Unités : celles du Mini (Class40 = ×12,19/6,5 au rendu).
import sys, json, struct, base64, math, collections, numpy as np
sys.path.insert(0, '/home/claude/t'); from objload import load
import fast_simplification as fs
OBJ, MTL, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
G0, parts, mat = load(OBJ)
Kd = {}; Ns = {}; cur = None
for line in open(MTL):
    t = line.split()
    if not t: continue
    if t[0] == 'newmtl': cur = t[1]
    elif t[0] == 'Kd': Kd[cur] = [float(x) for x in t[1:4]]
    elif t[0] == 'Ns': Ns[cur] = float(t[1])
DROP = {'mainsail', 'mainsail_battens', 'mainsail_bands', 'mainsail_patches', 'jib_J2', 'jib_J2_battens', 'jib_J2_bands', 'foil_port', 'foil_starboard',
        'outriggers', 'mast', 'masthead', 'spreaders', 'rigging', 'boom', 'boom_fittings', 'bowsprit', 'mast_collar', 'traveller', 'stern_gear', 'rudder_stock_pads'}
LO_DROP = {'coachroof_hatch', 'companionway_glass', 'companionway_frame', 'jammers', 'stern_round_hatch', 'stern_round_hatch_glass', 'winches', 'deck_hatches', 'deck_hatch_glass',
           'bow_fittings', 'nav_lights', 'cockpit_seats', 'solar_panel', 'coachroof_windows'}
LO_TARGET = {'deck': 0.22, 'bottom': 0.4, 'coachroof': 0.35, 'keel_bulb': 0.3, 'livery_swoosh': 0.5, 'stern_blocks': 0.3, 'hull': 0.7, 'keel_fin': 0.5, 'rudder_starboard': 0.6, 'rudder_port': 0.6, 'cockpit_coaming': 0.5, 'keel_fairing': 0.5}
GROUP = {'keel_fin': 'keel', 'keel_bulb': 'keel'}
PERBOAT = {'Hull_White': 'hull', 'Livery_Coral': 'acc'}
L0, LM = 18.28, 6.5
# formes cibles (mêmes clés que le jeu : t = 0 au tableau, 1 à l'étrave)
HKT = [0, 0.15, 0.35, 0.55, 0.75, 0.88, 0.95, 1]
MINI = {'bD': [1.36, 1.44, 1.5, 1.5, 1.45, 1.34, 1.16, 0.78], 'yD': [0.52, 0.55, 0.6, 0.66, 0.72, 0.78, 0.82, 0.86], 'yB': [-0.1, -0.2, -0.27, -0.25, -0.14, 0.04, 0.2, 0.38]}
def hk(A, t):
    t = np.clip(t, 0, 1); i = np.clip(np.searchsorted(HKT, t, side='left'), 1, len(HKT) - 1); T = np.array(HKT); A = np.array(A)
    f = (t - T[i - 1]) / (T[i] - T[i - 1]); p0 = A[np.maximum(0, i - 2)]; p1 = A[i - 1]; p2 = A[i]; p3 = A[np.minimum(len(A) - 1, i + 1)]
    return 0.5 * (2 * p1 + (-p0 + p2) * f + (2 * p0 - 5 * p1 + 4 * p2 - p3) * f * f + (-p0 + 3 * p1 - 3 * p2 + p3) * f ** 3)
# stations du modèle : demi-largeur, livet (haut du bordé), fond
def stations():
    H = G0[np.unique(np.array(parts['hull']))]; B = G0[np.unique(np.array(parts['bottom']))]; D = G0[np.unique(np.array(parts['deck']))]
    zs = np.linspace(-L0 / 2, L0 / 2, 74); hb, sh, bo = [], [], []
    for z in zs:
        m = np.abs(H[:, 2] - z) < 0.35; mb = np.abs(B[:, 2] - z) < 0.35; md = np.abs(D[:, 2] - z) < 0.35
        hb.append(max(np.abs(np.concatenate([H[m, 0], D[md, 0]])).max(initial=0.05), 0.05)); sh.append(H[m, 1].max(initial=1.2)); bo.append(min(B[mb, 1].min(initial=-0.3), -0.05))
    sm = lambda a: np.convolve(np.pad(a, 2, mode='edge'), np.ones(5) / 5, 'valid')
    return zs, sm(np.array(hb)), sm(np.array(sh)), sm(np.array(bo))
ZS, HB, SH, BO = stations()
def transform(V, name, cls):
    kb, ky, kb2 = (1.0, 1.0, 1.0) if cls == 'mini' else (0.8, 1.0, 1.0)   # Class40 (unités Mini) : plus étroit (4,50 m réels pour 12,19)
    draft, rud = (2.0, 1.0) if cls == 'mini' else (1.6, 0.95)          # tirant d'eau (unités Mini) : 2,0 m Mini ; 3,0 m réels Class40
    x, y, z = V[:, 0], V[:, 1], V[:, 2]; t = (L0 / 2 - z) / L0
    hbm = np.interp(z, ZS, HB); shm = np.interp(z, ZS, SH); bom = np.interp(z, ZS, BO)
    rx = np.clip(hk(MINI['bD'], t) * kb / hbm, 0.3, 3.0); ryu = hk(MINI['yD'], t) * ky / shm; ryd = np.clip(np.minimum(hk(MINI['yB'], t), -0.02) / bom, 0.15, 1.5)
    zz = z * LM / L0
    if name in ('keel_fin', 'keel_bulb', 'keel_fairing'):
        return np.stack([x * 0.62, np.where(y < 0, y * draft / 4.5, y * 0.4), zz], 1)
    if name.startswith('rudder'):
        rs = np.interp(L0 / 2 - 0.6, ZS, HB); xr = np.sign(x) * (np.abs(x) * hk(MINI['bD'], 0.02) * kb / rs * 0.92)
        return np.stack([xr, np.where(y < 0, y * rud / 2.5, y * 0.45), zz], 1)
    return np.stack([x * rx, np.where(y >= 0, y * ryu, y * ryd), zz], 1)
def crease(V, F, ang=40):
    n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]); n = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
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
def build(cls, level):
    keelP = transform(np.array([[0, -0.5, 1.24]]), 'keel_fin', cls)[0]; buckets = collections.OrderedDict()
    for name in parts:
        if name in DROP or (level == 'lo' and name in LO_DROP): continue
        T = np.array(parts[name], dtype=np.int64); ids = np.unique(T); remap = {o: i for i, o in enumerate(ids)}; V = G0[ids]; F = np.vectorize(remap.get)(T)
        if level == 'lo' and LO_TARGET.get(name, 1) < 1 and len(F) > 60:
            V2, F2 = fs.simplify(V.astype(np.float32), F.astype(np.int32), target_reduction=1 - LO_TARGET[name])
            if len(F2) > 8: V, F = V2.astype(np.float64), F2.astype(np.int64)
        V = transform(V, name, cls); grp = GROUP.get(name, 'static')
        if grp == 'keel': V = V - keelP
        m = mat[name]; key = 'vcol' if level == 'lo' and m not in PERBOAT else PERBOAT.get(m, m)
        b = buckets.setdefault((grp, key), [[], [], []]); off = sum(len(v) for v in b[0])
        b[0].append(V); b[1].append(F + off); b[2].append(np.tile(Kd.get(m, [0.5, 0.5, 0.5]), (len(V), 1)))
    out = []
    for (grp, key), (Vs, Fs, Cs) in buckets.items():
        V = np.concatenate(Vs); F = np.concatenate(Fs); C = np.concatenate(Cs); V2, F2 = crease(V, F); col = None
        if key == 'vcol': col = np.zeros((len(V2), 3)); col[F2.reshape(-1)] = C[F.reshape(-1)]
        out.append((f'{grp}:{key}', grp, key, V2, F2, col))
    return out, keelP
def pack(items, meta):
    head = {'meta': meta, 'v': 2, 'parts': []}; blob = bytearray(); pad = lambda: blob.extend(b'\0' * ((4 - len(blob) % 4) % 4))
    for name, grp, key, V, F, col in items:
        mn = V.min(0); mx = V.max(0); rng = np.where(mx - mn > 1e-9, mx - mn, 1); q = np.round((V - mn) / rng * 65535).astype('<u2'); i32 = len(V) > 65535
        p = {'name': name, 'grp': grp, 'mat': key, 'nv': len(V), 'ni': int(F.size), 'i32': i32, 'min': mn.tolist(), 'max': mx.tolist(), 'off': len(blob)}
        blob.extend(q.tobytes()); pad(); blob.extend(F.astype('<u4' if i32 else '<u2').reshape(-1).tobytes()); pad()
        if col is not None: p['col'] = True; blob.extend(np.round(np.clip(col, 0, 1) * 255).astype('u1').reshape(-1).tobytes()); pad()
        head['parts'].append(p)
    h = json.dumps(head, separators=(',', ':')).encode(); h += b' ' * ((4 - len(h) % 4) % 4)
    return b'OFM1' + struct.pack('<I', len(h)) + h + bytes(blob)
mats = {k: {'kd': Kd[k], 'ns': Ns.get(k, 100)} for k in Kd}
for cls in ['mini', 'c40']:
    for level in ['hi', 'lo']:
        items, keelP = build(cls, level); allV = np.concatenate([it[3] for it in items if it[1] == 'static'])
        meta = {'v': 2, 'keelPivot': keelP.tolist(), 'deckY': float(np.percentile(allV[:, 1], 90)), 'L': float(allV[:, 2].max() - allV[:, 2].min()), 'beam': float(2 * np.abs(allV[:, 0]).max())}
        buf = pack(items, meta)
        json.dump({'format': 'OFM1', 'b64': base64.b64encode(buf).decode(), 'mats': mats}, open(f'{OUT}/{cls}-{level}.json', 'w'), separators=(',', ':'))
        print(cls, level, 'maillages', len(items), 'triangles', sum(len(it[4]) for it in items), 'octets', len(buf), 'L', round(meta['L'], 2), 'bau', round(meta['beam'], 2), 'quille', [round(v, 2) for v in keelP])

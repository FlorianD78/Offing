import numpy as np, struct, sys
def load(f):
    with open(f,'rb') as fh:
        fh.seek(80); n=struct.unpack('<I',fh.read(4))[0]
        dt=np.dtype([('n','<f4',3),('v','<f4',(3,3)),('a','<u2')])
        d=np.fromfile(fh, dtype=dt, count=n)
    return d['v']

def components(v, q=1e-3):
    import numpy as np
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    p = v.reshape(-1, 3)
    key = np.round(p / q).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1, 3)
    nv = inv.max() + 1
    r = np.concatenate([inv[:, 0], inv[:, 1]]); c = np.concatenate([inv[:, 1], inv[:, 2]])
    g = coo_matrix((np.ones(len(r), dtype=np.int8), (r, c)), shape=(nv, nv))
    n, lab = connected_components(g, directed=False)
    return n, lab[inv[:, 0]], inv, nv

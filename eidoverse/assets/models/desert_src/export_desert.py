"""export_desert.py: the desert the Blender edition makes, as this library's files (plain Python: numpy and Pillow).

The Blender edition (branch `blender`) makes the desert by a chain of steps into a work folder (eidoblend.sets.desert:
make.py runs them); this script takes what the chain made into the three.js edition. In a checkout of the Blender
edition, from its root:

    python blender/eidoblend/sets/desert/make.py --work work/desert --to mesh       # sources, mask, land, mesh

then, from this repository's root, with the same Python (numpy, Pillow):

    python eidoverse/assets/models/desert_src/export_desert.py --work <that checkout>/work/desert --out work/desert_web
    deno run -A --no-lock eidoverse/assets/models/desert_src/pack_glb.mjs work/desert_web eidoverse/assets/models/desert

It reads <work>/build (desert_mesh.npz: the quadtree mesh and its masks; scrub.npz: the shrubs' places; near_marks.png
and mid_marks.png: what is finer than the mesh; land_B.npz: where the two close looks are found; mesh.json, land.json)
and <work>/sources/SOURCES.json, and writes into --out:

  raw/desert_A.glb, raw/desert_B.glb, raw/desert_C.glb
        the land in three rings round the town: A within 2,048 m of its middle, B within 8,192 m, C out to the edge at
        32,768 m, each ring in square tiles (1,024, 4,096 and 16,384 m: a face goes to the tile its middle is in), each
        quad split along its first diagonal as Blender draws it. Per vertex: its normal (Blender's: the faces' normals
        weighted by their corner angles, over the whole mesh, so the tiles meet without a seam), and the land's eight
        masks in two attributes, each mask scaled to 0..1 by the manifest's numbers: _DMA (16-bit: the distance from
        the town, the sand's depth, the escarpment's and the ranges' heights) and _DMB (8-bit: the sand sheet, the wadi
        bed, the bars' and the aprons' heights). Positions are quantized ONE way for every tile (KHR_mesh_quantization,
        the tile node's scale and translation): x and y in steps of 2 m, which is exact (every vertex of the quadtree
        lies on that grid), z in steps of 1/128 m about the land's middle height; so the tiles' shared edges are the
        same numbers on both sides. All in the town's own metres (+Z up) under one node turned into glTF's +Y up.
  raw/desert_scrub.glb
        the four shrubs (look.shrub_templates, numpy's generator seeded 41 as there: the twigs, and the mound of sand
        each caught, drawn in the ground's material) placed by EXT_mesh_gpu_instancing at every place of scrub.npz,
        each with its own number (_RND: look.scrub's per-shrub draw)
  near_marks.png, mid_marks.png
        copied, re-stored losslessly
  desert.json
        the manifest: the files and their tiles, the quantization, the masks' scales, the lenses (look.views(): the
        ring from the town and the two close looks found in the land) and what the chain was run with
pack_glb.mjs then compresses the raw GLBs into the library's (EXT_meshopt_compression) and copies the rest.
"""
import argparse
import json
import math
import os
import shutil
import struct
import sys
import time

import numpy as np
from PIL import Image

ROOT_HALF = 32768.0
RINGS = (('A', 2048.0, 1024.0), ('B', 8192.0, 4096.0), ('C', 32768.0, 16384.0))    # name, half extent, tile side (m)
XY_STEP, Z_STEP = 2.0, 1.0 / 128.0
MASK_A = ('town', 'sand', 'esc', 'mtn')                              # 16-bit
MASK_B = ('sheet', 'bed', 'bar', 'apron')                            # 8-bit
TOWN_REACH = 5000.0                                                  # (land.py keeps the town distance to 5 km)
Z_UP_TO_Y_UP = [-math.sqrt(0.5), 0.0, 0.0, math.sqrt(0.5)]           # -90 degrees about x
# the lenses (eidoblend.sets.desert.look.views): a ring from 75 m over the town, 8 degrees down, 35 mm
RING = ((0.0, 0.0), (-380.0, 0.0), (380.0, 0.0))
LOOKS = (('mY', 270.0), ('pY', 90.0), ('mX', 180.0), ('pX', 0.0))
GROUND_RGB, SCRUB_RGB = [0.45, 0.36, 0.25], [0.12, 0.125, 0.08]      # (the GLBs' own colours, for other viewers)


# ================================================================================================= normals
def vertex_normals(co, polys, chunk=400000):
    """Blender's vertex normals for smooth faces: each face's normal (Newell's: a quad's from its diagonals) times its
    corner's angle, summed per vertex and normalized. polys: a list of (F, k) index arrays"""
    P = co.astype(np.float64)
    acc = np.zeros_like(P)
    for poly in polys:
        k = poly.shape[1]
        for s in range(0, len(poly), chunk):
            f = poly[s:s + chunk]
            V = P[f]                                                 # F, k, 3
            fn = np.cross(V[:, 2] - V[:, 0], V[:, 3] - V[:, 1]) if k == 4 else np.cross(V[:, 1] - V[:, 0], V[:, 2] - V[:, 0])
            fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-30)
            e = np.roll(V, -1, axis=1) - V                           # corner i -> i + 1
            e /= np.maximum(np.linalg.norm(e, axis=2, keepdims=True), 1e-30)
            ang = np.arccos(np.clip(-(np.roll(e, 1, axis=1) * e).sum(2), -1.0, 1.0))
            for c in range(k):
                w = fn * ang[:, c:c + 1]
                for d in range(3):
                    acc[:, d] += np.bincount(f[:, c], weights=w[:, d], minlength=len(P))
    n = acc / np.maximum(np.linalg.norm(acc, axis=1, keepdims=True), 1e-30)
    return n.astype(np.float32)


def snorm8(n):
    return np.clip(np.round(n * 127.0), -127, 127).astype(np.int8)


def pad4(a, fill=0):
    """an (N, 3) array as (N, 4): glTF wants every vertex element on a 4-byte boundary"""
    return np.concatenate([a, np.full((len(a), 1), fill, a.dtype)], 1)


# ================================================================================================= a GLB
class GLB:
    def __init__(self, generator):
        self.j = {'asset': {'version': '2.0', 'generator': generator}, 'scene': 0, 'scenes': [{'nodes': [0]}],
                  'nodes': [], 'meshes': [], 'materials': [], 'accessors': [], 'bufferViews': [], 'buffers': []}
        self.bin = bytearray()

    def view(self, arr, stride=None, target=None):
        while len(self.bin) % 4:
            self.bin += b'\0'
        data = np.ascontiguousarray(arr).tobytes()
        bv = {'buffer': 0, 'byteOffset': len(self.bin), 'byteLength': len(data)}
        if stride:
            bv['byteStride'] = stride
        if target:
            bv['target'] = target
        self.bin += data
        self.j['bufferViews'].append(bv)
        return len(self.j['bufferViews']) - 1

    def accessor(self, arr, ctype, typ, count, normalized=False, stride=None, target=None, minmax=None):
        a = {'bufferView': self.view(arr, stride, target), 'componentType': ctype, 'count': int(count), 'type': typ}
        if normalized:
            a['normalized'] = True
        if minmax is not None:
            a['min'], a['max'] = [float(v) for v in minmax[0]], [float(v) for v in minmax[1]]
        self.j['accessors'].append(a)
        return len(self.j['accessors']) - 1

    def material(self, name, rgb, rough):
        self.j['materials'].append({'name': name, 'pbrMetallicRoughness': {'baseColorFactor': [*rgb, 1.0], 'metallicFactor': 0.0,
                                                                           'roughnessFactor': rough}})
        return len(self.j['materials']) - 1

    def node(self, **kw):
        self.j['nodes'].append(kw)
        return len(self.j['nodes']) - 1

    def write(self, path):
        for k in [k for k, v in self.j.items() if isinstance(v, list) and not v]:
            del self.j[k]
        while len(self.bin) % 4:
            self.bin += b'\0'
        self.j['buffers'] = [{'byteLength': len(self.bin)}]
        js = json.dumps(self.j, separators=(',', ':')).encode('utf-8')
        js += b' ' * ((4 - len(js) % 4) % 4)
        with open(path, 'wb') as f:
            f.write(struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(self.bin)))
            f.write(struct.pack('<II', len(js), 0x4E4F534A) + js)
            f.write(struct.pack('<II', len(self.bin), 0x004E4942) + bytes(self.bin))
        return os.path.getsize(path)


# ================================================================================================= the land
def land(build, out, log=print):
    t0 = time.time()
    z = np.load(os.path.join(build, 'desert_mesh.npz'))
    co, quads, tris = z['co'], z['quads'].astype(np.int64), z['tris'].astype(np.int64)
    off = np.abs(co[:, :2] / XY_STEP - np.round(co[:, :2] / XY_STEP)).max()
    if off > 1e-6:
        raise SystemExit(f'[desert export] the vertices are not on a {XY_STEP} m grid (off by {off * XY_STEP} m): '
                         'this exporter quantizes x and y exactly only on it')
    nrm = vertex_normals(co, [quads, tris])
    log(f'[desert export] {len(co)} vertices, {len(quads)} quads + {len(tris)} triangles; normals in {time.time() - t0:.1f} s')
    zmin, zmax = float(co[:, 2].min()), float(co[:, 2].max())
    z0 = float(round((zmin + zmax) / 2.0))
    qxy = np.round(co[:, :2] / XY_STEP).astype(np.int64)
    qz = np.round((co[:, 2].astype(np.float64) - z0) / Z_STEP).astype(np.int64)
    if np.abs(qxy).max() > 32767 or np.abs(qz).max() > 32767:
        raise SystemExit(f'[desert export] the land does not fit 16-bit steps (z {zmin:.1f}..{zmax:.1f} m)')
    Q = np.stack([qxy[:, 0], qxy[:, 1], qz], 1).astype(np.int16)
    N8 = snorm8(nrm)
    scales = {}
    for m in MASK_A + MASK_B:
        v = float(z['a_' + m].max())
        scales[m] = TOWN_REACH if m == 'town' else (1.0 if m in ('sheet', 'bed') or v <= 1.0 else float(math.ceil(v)))
    DA = np.stack([np.round(np.clip(z['a_' + m] / scales[m], 0, 1) * 65535) for m in MASK_A], 1).astype(np.uint16)
    DB = np.stack([np.round(np.clip(z['a_' + m] / scales[m], 0, 1) * 255) for m in MASK_B], 1).astype(np.uint8)
    # the faces: each quad its two triangles (0 1 2, 0 2 3: Blender's split of a convex quad), then the triangles
    T = np.concatenate([np.stack([quads[:, [0, 1, 2]], quads[:, [0, 2, 3]]], 1).reshape(-1, 3), tris])
    cen = np.concatenate([np.repeat(co[quads].mean(1)[:, :2], 2, axis=0), co[tris].mean(1)[:, :2]]).astype(np.float64)
    reach = np.maximum(np.abs(cen[:, 0]), np.abs(cen[:, 1]))
    ring = np.where(reach < RINGS[0][1], 0, np.where(reach < RINGS[1][1], 1, 2))
    files, tiles = {}, []
    for r, (name, half, side) in enumerate(RINGS):
        g = GLB('eidoverse desert_src/export_desert.py')
        mat = g.material('desert.ground', GROUND_RGB, 0.95)
        root = g.node(name='desert', rotation=Z_UP_TO_Y_UP, children=[])
        n_side = int(round(2 * half / side))
        sel = np.nonzero(ring == r)[0]
        ix = np.clip(np.floor((cen[sel, 0] + half) / side).astype(np.int64), 0, n_side - 1)
        iy = np.clip(np.floor((cen[sel, 1] + half) / side).astype(np.int64), 0, n_side - 1)
        key = iy * n_side + ix
        order = np.argsort(key, kind='stable')
        sel, key = sel[order], key[order]
        starts = np.flatnonzero(np.r_[True, key[1:] != key[:-1]])
        ends = np.r_[starts[1:], len(key)]
        n_v = n_t = 0
        for s, e in zip(starts, ends):
            k = int(key[s])
            tri = T[sel[s:e]]
            used, local = np.unique(tri.ravel(), return_inverse=True)
            idx = local.reshape(-1, 3).astype(np.uint32)
            q = Q[used]
            nm = f'desert_{name}_{k // n_side}{k % n_side}'
            acc = {
                'POSITION': g.accessor(pad4(q), 5122, 'VEC3', len(used), stride=8, target=34962, minmax=(q.min(0), q.max(0))),
                'NORMAL': g.accessor(pad4(N8[used]), 5120, 'VEC3', len(used), normalized=True, stride=4, target=34962),
                '_DMA': g.accessor(DA[used], 5123, 'VEC4', len(used), normalized=True, target=34962),
                '_DMB': g.accessor(DB[used], 5121, 'VEC4', len(used), normalized=True, target=34962),
            }
            ind = g.accessor(idx.ravel(), 5125, 'SCALAR', idx.size, target=34963)
            g.j['meshes'].append({'name': nm, 'primitives': [{'attributes': acc, 'indices': ind, 'material': mat}]})
            nd = g.node(name=nm, mesh=len(g.j['meshes']) - 1, translation=[0.0, 0.0, z0], scale=[XY_STEP, XY_STEP, Z_STEP])
            g.j['nodes'][root]['children'].append(nd)
            x0, y0 = -half + (k % n_side) * side, -half + (k // n_side) * side
            p = co[used]
            tiles.append(dict(name=nm, ring=name, file=f'desert_{name}.glb', square=[x0, y0, side], vertices=int(len(used)),
                              triangles=int(len(idx)), min=[round(float(v), 3) for v in p.min(0)], max=[round(float(v), 3) for v in p.max(0)]))
            n_v += len(used)
            n_t += len(idx)
        g.j['extensionsUsed'] = g.j['extensionsRequired'] = ['KHR_mesh_quantization']
        size = g.write(os.path.join(out, 'raw', f'desert_{name}.glb'))
        files[name] = dict(file=f'desert_{name}.glb', reach=half, tile=side, tiles=len(starts), vertices=n_v, triangles=n_t)
        log(f'[desert export] ring {name}: {len(starts)} tiles, {n_v} vertices, {n_t} triangles, raw {size / 1e6:.1f} MB')
    return dict(rings=files, tiles=tiles, quantization=dict(scale=[XY_STEP, XY_STEP, Z_STEP], offset=[0.0, 0.0, z0]),
                masks={'_DMA': [[m, scales[m]] for m in MASK_A], '_DMB': [[m, scales[m]] for m in MASK_B]},
                vertices=int(len(co)), faces=int(len(quads) + len(tris)), z=[round(zmin, 3), round(zmax, 3)])


# ================================================================================================= the scrub
def shrub_templates(rng, kinds=4):
    """eidoblend.sets.desert.look.shrub_templates, line for line (the same draws in the same order): low desert shrubs,
    each a few irregular lobes of twigs over the low mound of sand it caught: (vertices, faces, material per face)"""
    out = []
    for k in range(kinds):
        V, F, M = [], [], []

        def lobe(cx, cy, cz, r, hz, seg=6, rings=3):
            base = len(V)
            jit = rng.uniform(0.78, 1.22, (rings + 1, seg))
            for i in range(rings + 1):
                th = math.pi * i / rings
                for j in range(seg):
                    ph = 2 * math.pi * j / seg + (0.5 * i)
                    rr = r * math.sin(th) * (jit[i, j] if 0 < i < rings else 1.0)
                    V.append((cx + rr * math.cos(ph), cy + rr * math.sin(ph), cz + hz * math.cos(th) * (jit[i, j] if 0 < i < rings else 1.0)))
            for i in range(rings):
                for j in range(seg):
                    a_, b_ = base + i * seg + j, base + i * seg + (j + 1) % seg
                    c_, d_ = base + (i + 1) * seg + (j + 1) % seg, base + (i + 1) * seg + j
                    if i == 0:
                        F.append((a_, d_, c_))
                    elif i == rings - 1:
                        F.append((a_, b_, d_))
                    else:
                        F.append((a_, b_, c_, d_)[::-1])
                    M.append(0)
        n_l = 2 + k % 3
        for li in range(n_l):
            ang = rng.uniform(0, 6.283)
            d = 0.0 if li == 0 else rng.uniform(0.25, 0.55)
            r = rng.uniform(0.45, 0.62) if li == 0 else rng.uniform(0.28, 0.45)
            lobe(d * math.cos(ang), d * math.sin(ang), 0.42 + r * 0.55, r, r * rng.uniform(0.62, 0.85))
        base = len(V)
        seg = 9
        V.append((0.0, 0.0, 0.32))
        for ring, (rr, zz) in enumerate(((0.75, 0.24), (1.55, 0.0))):
            for j in range(seg):
                ph = 2 * math.pi * j / seg
                q = rng.uniform(0.85, 1.15)
                V.append((rr * q * math.cos(ph) * 1.15, rr * q * math.sin(ph), zz - (0.06 if ring == 1 else 0.0)))
        for j in range(seg):
            F.append((base, base + 1 + j, base + 1 + (j + 1) % seg))
            M.append(1)
            a_, b_ = base + 1 + j, base + 1 + (j + 1) % seg
            F.append((a_, a_ + seg, b_ + seg, b_))
            M.append(1)
        out.append((np.array(V, np.float32), F, M))
    return out


def scrub(build, out, log=print):
    z = np.load(os.path.join(build, 'scrub.npz'))
    pos, rot, sc, kind = z['pos'], z['rot'], z['scale'], z['kind']
    rng = np.random.default_rng(41)
    tpl = shrub_templates(rng)
    rnd = np.array([rng.random() for _ in range(len(pos))], np.float32)   # (look.scrub: one draw a shrub, in order)
    g = GLB('eidoverse desert_src/export_desert.py')
    m_twig = g.material('desert.scrub', SCRUB_RGB, 0.9)
    m_mound = g.material('desert.ground', GROUND_RGB, 0.95)
    root = g.node(name='desert_scrub', rotation=Z_UP_TO_Y_UP, children=[])
    counts = []
    for k, (V, F, M) in enumerate(tpl):
        quads = np.array([f for f in F if len(f) == 4], np.int64).reshape(-1, 4)
        tris3 = np.array([f for f in F if len(f) == 3], np.int64).reshape(-1, 3)
        nrm = vertex_normals(V, [quads, tris3])
        prims = []
        for mi, mat in ((0, m_twig), (1, m_mound)):
            tri = []
            for f, mm in zip(F, M):
                if mm != mi:
                    continue
                tri += [f] if len(f) == 3 else [(f[0], f[1], f[2]), (f[0], f[2], f[3])]
            tri = np.array(tri, np.int64)
            used, local = np.unique(tri.ravel(), return_inverse=True)
            v = V[used]
            acc = {'POSITION': g.accessor(v, 5126, 'VEC3', len(used), target=34962, minmax=(v.min(0), v.max(0))),
                   'NORMAL': g.accessor(nrm[used], 5126, 'VEC3', len(used), target=34962)}
            prims.append({'attributes': acc, 'indices': g.accessor(local.astype(np.uint16), 5123, 'SCALAR', local.size, target=34963),
                          'material': mat})
        g.j['meshes'].append({'name': f'shrub_{k}', 'primitives': prims})
        sel = np.nonzero(kind == k)[0]
        s = sc[sel].astype(np.float32)
        tr = np.stack([pos[sel, 0], pos[sel, 1], pos[sel, 2] - 0.12 * s], 1).astype(np.float32)
        ro = np.stack([np.zeros(len(sel)), np.zeros(len(sel)), np.sin(rot[sel] / 2.0), np.cos(rot[sel] / 2.0)], 1).astype(np.float32)
        inst = {'TRANSLATION': g.accessor(tr, 5126, 'VEC3', len(sel)), 'ROTATION': g.accessor(ro, 5126, 'VEC4', len(sel)),
                'SCALE': g.accessor(np.stack([s, s, s], 1), 5126, 'VEC3', len(sel)), '_RND': g.accessor(rnd[sel], 5126, 'SCALAR', len(sel))}
        nd = g.node(name=f'shrubs_{k}', mesh=k, extensions={'EXT_mesh_gpu_instancing': {'attributes': inst}})
        g.j['nodes'][root]['children'].append(nd)
        counts.append(int(len(sel)))
    g.j['extensionsUsed'] = ['EXT_mesh_gpu_instancing']
    size = g.write(os.path.join(out, 'raw', 'desert_scrub.glb'))
    log(f'[desert export] scrub: {len(pos)} shrubs of {len(tpl)} kinds {counts}, raw {size / 1e3:.0f} KB')
    return dict(file='desert_scrub.glb', shrubs=int(len(pos)), kinds=counts)


# ================================================================================================= the lenses
def views(build, log=print):
    """eidoblend.sets.desert.look.views: [name, pos, target, lens] in the town's metres"""
    out = []
    for (x, y) in RING:
        for nm, az in LOOKS:
            d = np.array([math.cos(math.radians(az)), math.sin(math.radians(az)), -math.tan(math.radians(8.0))])
            p = np.array([x, y, 75.0])
            out.append([f'ring_{"c" if x == 0 else ("w" if x < 0 else "e")}_{nm}', p.tolist(), (p + d * 100.0).tolist(), 35])
    zB = np.load(os.path.join(build, 'land_B.npz'))
    half, cell = float(zB['half']), float(zB['cell'])
    h, esc, sand = zB['h'], zB['esc'], zB['sand']
    gy, gx = np.gradient(h.astype(np.float32), cell)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    c = (np.arange(h.shape[0]) + 0.5) * cell - half
    XX, YY = np.meshgrid(c, c)
    k = np.argmin(np.where((esc > 60) & (slope > 40) & (YY > 0), np.hypot(XX, YY), 1e12))
    tx, ty, tz = float(XX.flat[k]), float(YY.flat[k]), float(h.flat[k])
    dx, dy = tx / math.hypot(tx, ty), ty / math.hypot(tx, ty)
    out.append(['close_cliff_and_talus', [tx - dx * 1300.0, ty - dy * 1300.0, 95.0], [tx, ty, tz * 0.75], 50])
    k = np.argmin(np.where((sand > 25) & (YY < -1500) & (np.abs(XX) < 2500), np.hypot(XX, YY + 1500), 1e12))
    ux, uy, uz = float(XX.flat[k]), float(YY.flat[k]), float(h.flat[k])
    out.append(['close_dunes', [ux + 250.0, uy + 1000.0, 75.0], [ux, uy, uz * 0.6], 45])
    log(f'[desert export] close looks: cliff at ({tx:.0f}, {ty:.0f}), dunes at ({ux:.0f}, {uy:.0f}, {uz:.0f})')
    return [[n, [round(v, 4) for v in p], [round(v, 4) for v in t], L] for n, p, t, L in out]


# ================================================================================================= all of it
def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--work', required=True, help="the Blender edition's work folder (make.py --work)")
    ap.add_argument('--out', required=True, help='where the raw files go (pack_glb.mjs packs them from there)')
    a = ap.parse_args(argv)
    build = os.path.join(os.path.abspath(a.work), 'build')
    out = os.path.abspath(a.out)
    os.makedirs(os.path.join(out, 'raw'), exist_ok=True)
    t0 = time.time()
    rec = {'about': 'The desert round the town, as the Blender edition makes it (eidoblend.sets.desert), exported by '
                    'desert_src/export_desert.py: the land in three rings of tiles, the scrub, the marks finer than the '
                    'mesh, and the lenses. Metres of the town, +Z up.'}
    rec['land'] = land(build, out)
    rec['scrub'] = scrub(build, out)
    rec['marks'] = []
    for name, half in (('near_marks.png', 2048.0), ('mid_marks.png', 8192.0)):
        im = Image.open(os.path.join(build, name))
        im.load()
        im.save(os.path.join(out, name), optimize=True)
        rec['marks'].append(dict(file=name, reach=half, size=list(im.size), channels='R tracks, G wadi beds (0.6) and their bars (to 1), '
                                 'B the floor\'s drainage lines, A the sand sheet'))
    rec['views'] = views(build)
    chain = {}
    for fn in ('mesh.json', 'land.json'):
        p = os.path.join(build, fn)
        if os.path.isfile(p):
            chain[fn[:-5]] = json.load(open(p, encoding='utf-8'))
    p = os.path.join(os.path.abspath(a.work), 'sources', 'SOURCES.json')
    if os.path.isfile(p):
        S = json.load(open(p, encoding='utf-8'))
        chain['sources'] = dict(quality=S.get('quality'), recipes={k: dict(recipe=v.get('recipe'), seed=v.get('seed'), params=v.get('params'))
                                                                   for k, v in S.get('sources', {}).items()})
    rec['chain'] = chain
    with open(os.path.join(out, 'desert.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(rec, f, indent=1)
        f.write('\n')
    print(f'[desert export] done in {time.time() - t0:.1f} s: {out}', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

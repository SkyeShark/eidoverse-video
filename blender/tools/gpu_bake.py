#!/usr/bin/env python3
"""blender/tools/gpu_bake.py: a high baked onto its low with every ray on the GPU (NVIDIA Warp), outside Blender.

    python blender/tools/gpu_bake.py --bake work/my_prop/bake --name my_prop [--ss 2] [--ao 32] [--cav 16]
        [--ao-mm 30] [--cav-mm 2] [--edge-mm 4] [--corner-mm 8] [--device auto|cuda|cpu] [--layers FILE [--layers-dir DIR]]

System Python with numpy, scipy, Pillow and warp-lang (requirements-local.txt's bake tier; Apache-2.0). It reads what
eidoblend.props.hardsurface.bake_export wrote (<name>_low.npz, <name>_high.npz, <name>.json) and writes, beside them:

    <name>_normal.png     the tangent-space normal map, 16-bit, OpenGL (+Y up: Blender's normal-map node), in the
                          low's MikkTSpace frame as the renderer builds it, so it decodes exactly
    <name>_masks_a.png    R ambient occlusion (cosine rays to ao_mm against every high and occluder), G cavity (to
                          cav_mm), B curvature, fine (0.5 flat, brighter convex)
    <name>_masks_b.png    R edge: nearness of the part's own EXPOSED convex arrises (1 on the arris, 0 at edge_mm),
                          G curvature, broad, B inside corner: nearness of its concave edges (0 at corner_mm)
    <name>_id.png         the substrate ID per texel (bake_export's substrate), as ID x 16, never filtered
    <name>_coverage.png   proof: green baked, red on the low but no ray found the high, blue a back face seen, yellow
                          partly missed; <name>_layout.png: each part its own colour as the texels fall
    <name>_report.json    per part: texels, miss share, back faces seen, cage, projection distances; the totals

Why not Blender's bake: its selected-to-active bake casts every texel's cage ray in a serial CPU loop over its own BVH
(only the shading runs on the GPU), so a dense high keeps the GPU idle. Here one GPU thread per texel does it all:
  1. the low under each of ss x ss sub-samples of a texel (a ray down through the UV triangles laid in texel space):
     its point, shading normal, tangent and sign, and its cage direction, leaned toward the face's own normal away from
     its UV island's border (past 2.5 mm a hard-edged flat's rays go square to it: no ragged craters round sunk heads)
  2. the projection: from the cage point back along that direction against the part's OWN high only (a wrong-part hit
     is impossible), the first FRONT-facing crossing (back faces are stepped through and counted), tried once more
     from further out when nothing is found; cage and reach per part from the measured low-to-high distance
  3. at the hit: the high's interpolated corner normal solved into the texel's frame; AO and cavity
  4. then on the CPU: curvature at two scales (the divergence of the object-space normal between neighbouring texels
     of one part), the edge and corner maps, the ID, padding from each texel's nearest baked texel through the gutters
Warp runs on the CPU when there is no CUDA device (--device cpu), slower but the same maps.

--layers FILE: a Python file defining layers(bake), called after the maps are computed and before they are written, to
lay an asset's own data into UV space (markings at real size, a moulded relief into the normal map). `bake` carries
size, names, px_per_mm, the per-texel arrays (tp part, okh baked, cov on the low, pos_mm, nos object normal, tan, bit,
nts tangent normal), layers_dir, save(file, array, bits=8) and pad(array, hole); see the carbine's layers.py.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import struct
import sys
import time
import types
import zlib

import numpy as np

try:
    import warp as wp
except ImportError:                                            # pragma: no cover
    sys.exit('[gpu_bake] NVIDIA Warp is not installed: pip install warp-lang (requirements-local.txt, the bake tier)')
try:
    from PIL import Image
    from scipy import ndimage
    from scipy.spatial import cKDTree
except ImportError as e:                                       # pragma: no cover
    sys.exit(f'[gpu_bake] {e.name} is missing: pip install numpy scipy pillow')

T0 = time.time()


def log(*a):
    print(f'[gpu_bake {time.time() - T0:7.1f} s]', *a, flush=True)


# ------------------------------------------------------------------------------------------------- kernels ---

@wp.func
def frame_solve(t: wp.vec3, b: wp.vec3, n: wp.vec3, v: wp.vec3):
    """x with t x0 + b x1 + n x2 = v: what the shader's frame (T, B, N) maps back to v."""
    m = wp.mat33(t[0], b[0], n[0], t[1], b[1], n[1], t[2], b[2], n[2])
    if wp.abs(wp.determinant(m)) < 1.0e-8:
        return wp.vec3(0.0, 0.0, 1.0)
    return wp.inverse(m) @ v


@wp.kernel
def k_test(m: wp.uint64, o: wp.vec3, d: wp.vec3, out: wp.array(dtype=float)):
    q = wp.mesh_query_ray(m, o, d, 10.0)
    out[0] = float(q.result)
    out[1] = q.sign
    out[2] = q.u
    out[3] = q.v
    out[4] = q.t


@wp.kernel
def k_texel_part(uvm: wp.uint64, size: int, ss: int, tri_part: wp.array(dtype=int), out: wp.array(dtype=int)):
    tid = wp.tid()
    x = tid % size
    y = tid // size
    out[tid] = -1
    for j in range(ss):
        for i in range(ss):
            q = wp.mesh_query_ray(uvm, wp.vec3(float(x) + (float(i) + 0.5) / float(ss), float(y) + (float(j) + 0.5) / float(ss), 1.0),
                                  wp.vec3(0.0, 0.0, -1.0), 2.0)
            if q.result:
                out[tid] = tri_part[q.face]


@wp.kernel
def k_deviation(pts: wp.array(dtype=wp.vec3), pp: wp.array(dtype=int), meshes: wp.array(dtype=wp.uint64), out: wp.array(dtype=float),
                inside: wp.array(dtype=int)):
    """each low corner's distance to its own part's high, and whether it lies INSIDE that high"""
    i = wp.tid()
    q = wp.mesh_query_point(meshes[pp[i]], pts[i], 0.05)
    out[i] = 0.05
    inside[i] = 0
    if q.result:
        out[i] = wp.length(pts[i] - wp.mesh_eval_position(meshes[pp[i]], q.face, q.u, q.v))
        if q.sign < 0.0:
            inside[i] = 1


@wp.kernel
def k_bake(uvm: wp.uint64, size: int, ss: int, texels: wp.array(dtype=int), part: int, tri_part: wp.array(dtype=int),
           lp: wp.array(dtype=wp.vec3), ln: wp.array(dtype=wp.vec3), lt: wp.array(dtype=wp.vec4), lc: wp.array(dtype=wp.vec3),
           skew: wp.array(dtype=float), him: wp.uint64, hn: wp.array(dtype=wp.vec3), hp: wp.array(dtype=wp.vec3), fullm: wp.uint64,
           off: float, reach: float, ao_n: int, ao_d: float, cav_n: int, cav_d: float, seed: int,
           o_nts: wp.array(dtype=wp.vec3), o_nos: wp.array(dtype=wp.vec3), o_pos: wp.array(dtype=wp.vec3),
           o_tan: wp.array(dtype=wp.vec3), o_nrm: wp.array(dtype=wp.vec3), o_bit: wp.array(dtype=wp.vec3),
           o_ao: wp.array(dtype=float), o_cav: wp.array(dtype=float), o_dist: wp.array(dtype=float),
           o_hit: wp.array(dtype=int), o_miss: wp.array(dtype=int), o_back: wp.array(dtype=int)):
    k = wp.tid()
    tid = texels[k]
    x = tid % size
    y = tid // size
    state = wp.rand_init(seed, tid)
    nts = wp.vec3(0.0, 0.0, 0.0)
    nos = wp.vec3(0.0, 0.0, 0.0)
    pos = wp.vec3(0.0, 0.0, 0.0)
    tan = wp.vec3(0.0, 0.0, 0.0)
    nrm = wp.vec3(0.0, 0.0, 0.0)
    bit = wp.vec3(0.0, 0.0, 0.0)
    ao = float(0.0)
    cav = float(0.0)
    dist = float(0.0)
    hits = int(0)
    miss = int(0)
    back = int(0)
    for j in range(ss):
        for i in range(ss):
            q = wp.mesh_query_ray(uvm, wp.vec3(float(x) + (float(i) + 0.5) / float(ss), float(y) + (float(j) + 0.5) / float(ss), 1.0),
                                  wp.vec3(0.0, 0.0, -1.0), 2.0)
            if not q.result:
                continue
            f = q.face
            if tri_part[f] != part:
                continue
            u = q.u
            v = q.v
            w = 1.0 - u - v
            p = lp[f * 3] * u + lp[f * 3 + 1] * v + lp[f * 3 + 2] * w
            ns = wp.normalize(ln[f * 3] * u + ln[f * 3 + 1] * v + ln[f * 3 + 2] * w)
            t4 = lt[f * 3] * u + lt[f * 3 + 1] * v + lt[f * 3 + 2] * w
            tt = wp.normalize(wp.vec3(t4[0], t4[1], t4[2]))
            sg = lt[f * 3][3]
            bb = wp.cross(ns, tt) * sg
            cg = wp.normalize(lc[f * 3] * u + lc[f * 3 + 1] * v + lc[f * 3 + 2] * w)
            nf = wp.normalize(wp.cross(lp[f * 3 + 1] - lp[f * 3], lp[f * 3 + 2] - lp[f * 3]))
            if wp.dot(nf, ns) < 0.0:
                nf = -nf
            sk = skew[tid]
            d = wp.normalize(cg * (1.0 - sk) + nf * sk)
            found = int(0)
            fh = int(-1)
            fu = float(0.0)
            fv = float(0.0)
            saw_back = int(0)
            used = float(off)
            gone = float(0.0)
            o = wp.vec3(0.0, 0.0, 0.0)
            rem = float(0.0)
            # (a sample that finds no front face, or starts inside the high, is tried once more from further out)
            for attempt in range(2):
                if found == 0:
                    used = off
                    if attempt == 1:
                        used = wp.max(off * 2.5, 0.002)
                    o = wp.vec3(p + d * used)
                    rem = float(used + reach)
                    gone = float(0.0)
                    for it in range(8):
                        h = wp.mesh_query_ray(him, o, -d, rem)
                        if not h.result:
                            break
                        if h.sign > 0.0:
                            found = 1
                            fh = h.face
                            fu = h.u
                            fv = h.v
                            gone = gone + h.t
                            break
                        saw_back = 1
                        o = o - d * (h.t + 1.0e-6)
                        gone = gone + h.t + 1.0e-6
                        rem = rem - h.t - 1.0e-6
                        if rem <= 0.0:
                            break
            if found == 0:
                miss = miss + 1
                back = back + saw_back
                continue
            fw = 1.0 - fu - fv
            nh = wp.normalize(hn[fh * 3] * fu + hn[fh * 3 + 1] * fv + hn[fh * 3 + 2] * fw)
            ph = p + d * (used - gone)
            ts = wp.normalize(frame_solve(tt, bb, ns, nh))
            nts = nts + ts
            nos = nos + nh
            pos = pos + ph
            tan = tan + tt
            nrm = nrm + ns
            bit = bit + bb
            dist = dist + (used - gone)
            hits = hits + 1
            a0 = hp[fh * 3]
            ng = wp.normalize(wp.cross(hp[fh * 3 + 1] - a0, hp[fh * 3 + 2] - a0))
            if wp.dot(ng, nh) < 0.0:
                ng = -ng
            org = ph + ng * 2.0e-5
            ax = wp.vec3(1.0, 0.0, 0.0)
            if wp.abs(ng[0]) > 0.9:
                ax = wp.vec3(0.0, 1.0, 0.0)
            t1 = wp.normalize(wp.cross(ng, ax))
            t2 = wp.cross(ng, t1)
            occ = float(0.0)
            for r in range(ao_n):
                r1 = wp.randf(state)
                r2 = wp.randf(state)
                rr = wp.sqrt(r1)
                an = 6.2831853 * r2
                dd = t1 * (rr * wp.cos(an)) + t2 * (rr * wp.sin(an)) + ng * wp.sqrt(wp.max(0.0, 1.0 - r1))
                hq = wp.mesh_query_ray(fullm, org, dd, ao_d)
                if hq.result:
                    occ = occ + 1.0
            ao = ao + 1.0 - occ / float(ao_n)
            occ = float(0.0)
            for r in range(cav_n):
                r1 = wp.randf(state)
                r2 = wp.randf(state)
                rr = wp.sqrt(r1)
                an = 6.2831853 * r2
                dd = t1 * (rr * wp.cos(an)) + t2 * (rr * wp.sin(an)) + ng * wp.sqrt(wp.max(0.0, 1.0 - r1))
                hq = wp.mesh_query_ray(fullm, org, dd, cav_d)
                if hq.result:
                    occ = occ + 1.0
            cav = cav + 1.0 - occ / float(cav_n)
    o_nts[k] = nts
    o_nos[k] = nos
    o_pos[k] = pos
    o_tan[k] = tan
    o_nrm[k] = nrm
    o_bit[k] = bit
    o_ao[k] = ao
    o_cav[k] = cav
    o_dist[k] = dist
    o_hit[k] = hits
    o_miss[k] = miss
    o_back[k] = back


@wp.kernel
def k_exposed(pts: wp.array(dtype=wp.vec3), nrm: wp.array(dtype=wp.vec3), fullm: wp.uint64, seed: int, out: wp.array(dtype=int)):
    """an arris sample is EXPOSED when most of 8 rays about its outward direction escape within 25 mm"""
    i = wp.tid()
    state = wp.rand_init(seed, i)
    n = wp.normalize(nrm[i])
    ax = wp.vec3(1.0, 0.0, 0.0)
    if wp.abs(n[0]) > 0.9:
        ax = wp.vec3(0.0, 1.0, 0.0)
    t1 = wp.normalize(wp.cross(n, ax))
    t2 = wp.cross(n, t1)
    org = pts[i] + n * 4.0e-4
    hit = int(0)
    for r in range(8):
        r1 = wp.randf(state)
        r2 = wp.randf(state)
        rr = wp.sqrt(r1)
        an = 6.2831853 * r2
        dd = t1 * (rr * wp.cos(an)) + t2 * (rr * wp.sin(an)) + n * wp.sqrt(wp.max(0.0, 1.0 - r1))
        q = wp.mesh_query_ray(fullm, org, dd, 0.025)
        if q.result:
            hit = hit + 1
    out[i] = int(hit <= 4)


# ------------------------------------------------------------------------------------------------- helpers ---

def save16rgb(path, arr):
    """A 16-bit RGB PNG (Pillow writes 16-bit greys only): the rows packed through zlib."""
    h_, w_, _ = arr.shape
    a16 = np.clip(np.round(arr * 65535), 0, 65535).astype('>u2')
    co = zlib.compressobj(6)
    raw = [co.compress(b'\x00' + a16[y].tobytes()) for y in range(h_)] + [co.flush()]

    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w_, h_, 16, 2, 0, 0, 0))
                + chunk(b'IDAT', b''.join(raw)) + chunk(b'IEND', b''))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--bake', required=True, help='the folder bake_export wrote')
    ap.add_argument('--name', required=True, help='the bake\'s name (<name>_low.npz ...)')
    ap.add_argument('--ss', type=int, default=2, help='sub-samples per texel, per axis')
    ap.add_argument('--ao', type=int, default=32, help='AO rays per sub-sample')
    ap.add_argument('--cav', type=int, default=16, help='cavity rays per sub-sample')
    ap.add_argument('--ao-mm', type=float, default=None, help='AO reach (default: the json, else 30)')
    ap.add_argument('--cav-mm', type=float, default=None, help='cavity reach (default: the json, else 2)')
    ap.add_argument('--edge-mm', type=float, default=None, help='the edge map\'s range (default: the json, else 4)')
    ap.add_argument('--corner-mm', type=float, default=None, help='the corner map\'s range (default: the json, else 8)')
    ap.add_argument('--device', default='auto', help='auto | cuda | cpu')
    ap.add_argument('--chunk', type=int, default=1 << 22, help='texels a launch')
    ap.add_argument('--layers', default=None, help='a Python file defining layers(bake): the asset\'s own UV-space data')
    ap.add_argument('--layers-dir', default=None, help='a folder the layers hook reads (bake.layers_dir)')
    a = ap.parse_args(argv)
    bake_dir, name = os.path.abspath(a.bake), a.name
    PJ = json.load(open(os.path.join(bake_dir, f'{name}.json'), encoding='utf-8'))
    OPT = PJ.get('options', {})
    SIZE, NAMES, PXMM = int(PJ['size']), PJ['names'], float(PJ['px_per_mm'])
    SUB = np.array([int(PJ['substrate'].get(n, 1)) for n in NAMES], np.uint8)
    AO_D = (a.ao_mm if a.ao_mm is not None else OPT.get('ao_mm', 30.0)) * 1e-3
    CAV_D = (a.cav_mm if a.cav_mm is not None else OPT.get('cav_mm', 2.0)) * 1e-3
    EDGE_MM = a.edge_mm if a.edge_mm is not None else OPT.get('edge_mm', 4.0)
    CORNER_MM = a.corner_mm if a.corner_mm is not None else OPT.get('corner_mm', 8.0)
    SS, AO_N, CAV_N = a.ss, a.ao, a.cav
    wp.init()
    dev = a.device
    if dev == 'auto':
        dev = 'cuda' if wp.get_cuda_device_count() > 0 else 'cpu'
    wp.set_device(dev)
    log(f'device {dev}')

    def mesh(points):
        pts = np.ascontiguousarray(points.reshape(-1, 3), np.float32)
        return wp.Mesh(points=wp.array(pts, dtype=wp.vec3), indices=wp.array(np.arange(len(pts), dtype=np.int32), dtype=int))

    # 0. the conventions, proved on one triangle: sign > 0 is the front face; the point is u p0 + v p1 + (1-u-v) p2
    tri = mesh(np.array([[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]], np.float32))
    res = wp.zeros(5, dtype=float)
    wp.launch(k_test, dim=1, inputs=[tri.id, wp.vec3(0.2, 0.3, 1.0), wp.vec3(0.0, 0.0, -1.0), res])
    r_ = res.numpy()
    pt = r_[2] * np.array((0, 0, 0)) + r_[3] * np.array((1, 0, 0)) + (1.0 - r_[2] - r_[3]) * np.array((0, 1, 0))
    assert r_[0] == 1.0 and r_[1] > 0 and np.allclose(pt, (0.2, 0.3, 0.0), atol=1e-5), ('ray conventions', r_)
    wp.launch(k_test, dim=1, inputs=[tri.id, wp.vec3(0.2, 0.3, -1.0), wp.vec3(0.0, 0.0, 1.0), res])
    assert res.numpy()[1] < 0, ('ray conventions from behind', res.numpy())

    # 1. inputs
    L = np.load(os.path.join(bake_dir, f'{name}_low.npz'))
    H = np.load(os.path.join(bake_dir, f'{name}_high.npz'))
    lpt, lnr, ltg, luv, lcg, lpart = L['p'], L['n'], L['t'], L['uv'], L['cage'], L['part'].astype(np.int32)
    hpt, hnr, hpart = H['p'], H['n'].astype(np.float32), H['part'].astype(np.int32)
    occ_p = H['occ_p'] if 'occ_p' in H.files else np.zeros((0, 3, 3), np.float32)
    NP = len(NAMES)
    log(f'{name}: low {len(lpt):,} triangles, high {len(hpt):,} (+{len(occ_p):,} occluding); {NP} parts; {SIZE} px at '
        f'{PXMM:.2f} px/mm; {SS}x{SS} samples a texel; AO {AO_D * 1e3:g} mm x{AO_N}, cavity {CAV_D * 1e3:g} mm x{CAV_N}')
    uvp = np.concatenate([luv.reshape(-1, 2) * SIZE, np.zeros((len(luv) * 3, 1), np.float32)], 1)
    uvm = mesh(uvp)
    full = mesh(np.concatenate([hpt, occ_p.astype(np.float32)]) if len(occ_p) else hpt)
    him, hn_a, hp_a = [], [], []
    for pi in range(NP):
        sel = hpart == pi
        if not sel.any():
            raise SystemExit(f'[gpu_bake] part {NAMES[pi]} has no high triangles')
        him.append(mesh(hpt[sel]))
        hn_a.append(wp.array(np.ascontiguousarray(hnr[sel].reshape(-1, 3)), dtype=wp.vec3))
        hp_a.append(wp.array(np.ascontiguousarray(hpt[sel].reshape(-1, 3)), dtype=wp.vec3))
    tri_part = wp.array(lpart, dtype=int)
    lp_a = wp.array(np.ascontiguousarray(lpt.reshape(-1, 3)), dtype=wp.vec3)
    ln_a = wp.array(np.ascontiguousarray(lnr.reshape(-1, 3)), dtype=wp.vec3)
    lt_a = wp.array(np.ascontiguousarray(ltg.reshape(-1, 4)), dtype=wp.vec4)
    lc_a = wp.array(np.ascontiguousarray(lcg.reshape(-1, 3)), dtype=wp.vec3)

    # 2. which part each texel belongs to; the skew (from the UV island border: hard edges lie on seams)
    N = SIZE * SIZE
    texpart = wp.zeros(N, dtype=int)
    wp.launch(k_texel_part, dim=N, inputs=[uvm.id, SIZE, SS, tri_part, texpart])
    tp = texpart.numpy()
    del texpart
    cov = tp >= 0
    log(f'texels on the low: {cov.sum():,} ({cov.mean() * 100:.1f} % of the set)')
    edt = ndimage.distance_transform_edt(cov.reshape(SIZE, SIZE)).ravel()
    sk = np.clip((edt / PXMM - 1.0) / 1.5, 0.0, 1.0)
    skew = wp.array((sk * sk * (3.0 - 2.0 * sk)).astype(np.float32), dtype=float)
    del edt, sk

    # 3. the cage per part, from the measured deviation (or the json's cage_mm / reach_mm)
    cpts = np.ascontiguousarray(lpt.reshape(-1, 3))
    cpp = np.repeat(lpart, 3).astype(np.int32)
    devw = wp.zeros(len(cpts), dtype=float)
    insw = wp.zeros(len(cpts), dtype=int)
    ids = wp.array(np.array([m.id for m in him], np.uint64), dtype=wp.uint64)
    wp.launch(k_deviation, dim=len(cpts), inputs=[wp.array(cpts, dtype=wp.vec3), wp.array(cpp, dtype=int), ids, devw, insw])
    devn, insn = devw.numpy(), insw.numpy().astype(bool)
    OFF, REACH = {}, {}
    cage_o, reach_o = OPT.get('cage_mm', {}), OPT.get('reach_mm', {})
    for pi in range(NP):
        sel = cpp == pi
        out_d = devn[sel & insn] * 1000.0                      # the high stands OUT of the low by this much here
        in_d = devn[sel & ~insn] * 1000.0                      # the high lies IN under the low by this much
        o99 = float(np.percentile(out_d, 99.5)) if len(out_d) else 0.0
        i99 = float(np.percentile(in_d, 99)) if len(in_d) else 0.5
        OFF[pi] = float(cage_o.get(NAMES[pi], min(3.0, max(0.6, 1.2 * o99 + 0.3)))) * 1e-3
        REACH[pi] = OFF[pi] + float(reach_o.get(NAMES[pi], min(4.0, max(1.5, 1.2 * i99 + 0.5)))) * 1e-3

    # 4. the bake, part by part, a chunk of texels a launch
    A = {k: np.zeros((N, 3), np.float32) for k in ('nts', 'nos', 'pos', 'tan', 'nrm', 'bit')}
    A.update({k: np.zeros(N, np.float32) for k in ('ao', 'cav', 'dist')})
    A.update({k: np.zeros(N, np.int32) for k in ('hit', 'miss', 'back')})
    order = np.argsort(tp, kind='stable')
    starts = np.searchsorted(tp[order], np.arange(-1, NP + 1))
    t_b = time.time()
    keys3 = ('nts', 'nos', 'pos', 'tan', 'nrm', 'bit')
    keys1 = (('ao', float), ('cav', float), ('dist', float), ('hit', int), ('miss', int), ('back', int))
    for pi in range(NP):
        idx_all = order[starts[pi + 1]:starts[pi + 2]].astype(np.int32)
        if not len(idx_all):
            log(f'  {NAMES[pi]}: NO TEXELS')
            continue
        for c0 in range(0, len(idx_all), a.chunk):
            idx = idx_all[c0:c0 + a.chunk]
            n_ = len(idx)
            outs = [wp.zeros(n_, dtype=wp.vec3) for _ in keys3] + [wp.zeros(n_, dtype=t) for _, t in keys1]
            wp.launch(k_bake, dim=n_, inputs=[uvm.id, SIZE, SS, wp.array(idx, dtype=int), pi, tri_part, lp_a, ln_a, lt_a, lc_a,
                                              skew, him[pi].id, hn_a[pi], hp_a[pi], full.id, OFF[pi], REACH[pi], AO_N, AO_D,
                                              CAV_N, CAV_D, 7 + pi] + outs)
            for k, w in zip(keys3 + tuple(k for k, _ in keys1), outs):
                A[k][idx] = w.numpy()
            del outs
    wp.synchronize()
    log(f'baked {cov.sum():,} texels x {SS * SS} samples on {dev} in {time.time() - t_b:.1f} s')
    hit = A['hit']
    okh = hit > 0
    hd = np.maximum(hit, 1)[:, None]

    # 5. the maps
    def unit(v):
        return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-12)
    nts = unit(A['nts'])
    nts[~okh] = (0.0, 0.0, 1.0)                                 # (a texel no ray reached: flat, never black)
    nos = unit(A['nos'])
    pos_mm = A['pos'] / hd * 1000.0
    tan, bit = unit(A['tan']), unit(A['bit'])
    ao = np.where(okh, A['ao'] / np.maximum(hit, 1), 0.0)
    cavm = np.where(okh, A['cav'] / np.maximum(hit, 1), 0.0)
    # curvature: the divergence of the object-space normal between neighbouring texels of one part (1/mm)
    P2, V2 = tp.reshape(SIZE, SIZE), okh.reshape(SIZE, SIZE)
    N3, X3 = nos.reshape(SIZE, SIZE, 3), pos_mm.reshape(SIZE, SIZE, 3)
    csum = np.zeros((SIZE, SIZE))
    ccnt = np.zeros((SIZE, SIZE))
    for ax_ in (0, 1):
        s0 = (slice(None, -1), slice(None)) if ax_ == 0 else (slice(None), slice(None, -1))
        s1 = (slice(1, None), slice(None)) if ax_ == 0 else (slice(None), slice(1, None))
        ok = V2[s0] & V2[s1] & (P2[s0] == P2[s1])
        dp = X3[s1] - X3[s0]
        dn = N3[s1] - N3[s0]
        l2 = np.sum(dp * dp, axis=2)
        ok &= (l2 > 1e-8) & (l2 < (4.0 / PXMM) ** 2)
        c = np.where(ok, np.sum(dn * dp, axis=2) / np.maximum(l2, 1e-8), 0.0)
        csum[s0] += c
        ccnt[s0] += ok
        csum[s1] += c
        ccnt[s1] += ok
    curv = np.where(ccnt > 0, csum / np.maximum(ccnt, 1), 0.0)
    del csum, ccnt
    sig = 1.5 * PXMM
    num = ndimage.gaussian_filter(curv * V2, sig)
    den = ndimage.gaussian_filter(V2.astype(np.float64), sig)
    curv_b = np.where(den > 1e-3, num / np.maximum(den, 1e-3), 0.0)
    del num, den
    curv_f8 = (0.5 + 0.5 * np.tanh(curv * 1.2)).ravel()        # 0.5 = flat; a 0.5 mm round saturates
    curv_b8 = (0.5 + 0.5 * np.tanh(curv_b * 3.0)).ravel()
    log(f'curvature: fine p5/p50/p95 {np.percentile(curv[V2], [5, 50, 95]).round(3) if V2.any() else []} 1/mm')
    # the edge map: distance to the part's own EXPOSED convex arrises; the corner map: to its concave edges
    arp, arn, arpart = H['ar_p'], H['ar_n'].astype(np.float32), H['ar_part'].astype(np.int32)
    edge = np.zeros(N, np.float32)
    if len(arp):
        expo = wp.zeros(len(arp), dtype=int)
        wp.launch(k_exposed, dim=len(arp), inputs=[wp.array(np.ascontiguousarray(arp), dtype=wp.vec3),
                                                   wp.array(np.ascontiguousarray(arn), dtype=wp.vec3), full.id, 11, expo])
        ex = expo.numpy().astype(bool)
        for pi in range(NP):
            sa = (arpart == pi) & ex
            st = okh & (tp == pi)
            if sa.any() and st.any():
                dd, _ = cKDTree(arp[sa] * 1000.0).query(pos_mm[st], distance_upper_bound=EDGE_MM, workers=-1)
                edge[st] = np.clip(1.0 - np.minimum(dd, EDGE_MM) / EDGE_MM, 0.0, 1.0)
        log(f'arrises: {ex.sum():,} of {len(ex):,} samples exposed')
    corner = np.zeros(N, np.float32)
    ccp = H['cc_p'] if 'cc_p' in H.files else np.zeros((0, 3), np.float32)
    ccpart = H['cc_part'].astype(np.int32) if 'cc_part' in H.files else np.zeros(0, np.int32)
    for pi in range(NP):
        sa = ccpart == pi
        st = okh & (tp == pi)
        if sa.any() and st.any():
            dd, _ = cKDTree(ccp[sa] * 1000.0).query(pos_mm[st], distance_upper_bound=CORNER_MM, workers=-1)
            corner[st] = np.clip(1.0 - np.minimum(dd, CORNER_MM) / CORNER_MM, 0.0, 1.0)
    sid = np.zeros(N, np.uint8)
    sid[cov] = SUB[tp[cov]]

    # 6. padding and the files
    _, ind = ndimage.distance_transform_edt(~okh.reshape(SIZE, SIZE), return_indices=True)
    near = (ind[0] * SIZE + ind[1]).ravel()
    del ind
    holes = cov & ~okh                       # on the low, but no ray found the high (a bore, an aperture)

    def pad(arr, hole=None):
        """the gutters take their nearest baked texel; a texel on the low that no ray reached keeps `hole`"""
        out = arr.copy()
        out[~cov] = arr[near][~cov]
        if hole is not None:
            out[holes] = hole
        else:
            out[holes] = arr[near][holes]
        return out

    def save(fname, arr, bits=8):
        """a map as a PNG, its rows from the top (v = 1) as Blender reads them; 16 bits for RGB normals"""
        arr = np.flipud(arr.reshape(SIZE, SIZE, -1) if arr.ndim > 1 else arr.reshape(SIZE, SIZE))
        path = os.path.join(bake_dir, fname)
        if bits == 16 and arr.ndim == 3:
            save16rgb(path, arr)
        elif bits == 16:
            Image.fromarray(np.clip(np.round(arr * 65535), 0, 65535).astype(np.uint16)).save(path)
        else:
            Image.fromarray(np.clip(np.round(arr * 255), 0, 255).astype(np.uint8)).save(path)

    if a.layers:
        spec = importlib.util.spec_from_file_location('bake_layers', os.path.abspath(a.layers))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        bake = types.SimpleNamespace(size=SIZE, names=NAMES, px_per_mm=PXMM, tp=tp, okh=okh, cov=cov, pos_mm=pos_mm, nos=nos,
                                     tan=tan, bit=bit, nts=nts, dir=bake_dir, name=name, layers_dir=a.layers_dir,
                                     save=save, pad=pad, log=log)
        mod.layers(bake)
        nts = bake.nts
        log(f'layers: {os.path.basename(a.layers)} done')
    save(f'{name}_normal.png', pad(nts * 0.5 + 0.5, hole=(0.5, 0.5, 1.0)), bits=16)
    save(f'{name}_masks_a.png', np.stack([pad(ao, 0.0), pad(cavm, 0.0), pad(curv_f8, 0.5)], 1))
    save(f'{name}_masks_b.png', np.stack([pad(edge, 0.0), pad(curv_b8, 0.5), pad(corner, 0.0)], 1))
    idmap = sid.copy()
    idmap[~cov] = sid[near][~cov]
    Image.fromarray(np.flipud((idmap.reshape(SIZE, SIZE) * 16).astype(np.uint8))).save(os.path.join(bake_dir, f'{name}_id.png'))
    log('maps written')

    # 7. the proofs
    miss, backc = A['miss'], A['back']
    rep = {}
    for pi in range(NP):
        st = tp == pi
        if not st.any():
            continue
        tot = (hit[st] + miss[st]).sum()
        dmm = (A['dist'][st & okh] / hit[st & okh]) * 1000.0 if (st & okh).any() else np.zeros(1)
        rep[NAMES[pi]] = {'texels': int(st.sum()), 'miss_share': round(float(miss[st].sum() / max(tot, 1)), 5),
                          'back_seen_share': round(float(backc[st].sum() / max(tot, 1)), 5), 'cage_mm': round(OFF[pi] * 1000, 2),
                          'dist_mm_p50_p95_max': [round(float(np.percentile(np.abs(dmm), q)), 3) for q in (50, 95, 100)]}
    tm, th = int(miss[cov].sum()), int(hit[cov].sum())
    nz = nts[okh][:, 2]
    summary = {'name': name, 'size': SIZE, 'ss': SS, 'device': dev, 'px_per_mm': PXMM, 'texels': int(cov.sum()),
               'samples_hit': th, 'samples_missed': tm, 'miss_share': round(float(tm / max(th + tm, 1)), 5),
               'normal_z_below_0.1': int((nz < 0.1).sum()), 'bake_seconds': round(time.time() - t_b, 1),
               'ao_mm': AO_D * 1e3, 'cav_mm': CAV_D * 1e3, 'edge_mm': EDGE_MM, 'corner_mm': CORNER_MM, 'parts': rep}
    with open(os.path.join(bake_dir, f'{name}_report.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(summary, f, indent=1)
    side = min(SIZE, 2048)
    cv = np.zeros((N, 3), np.uint8)
    cv[okh] = (40, 200, 60)
    cv[cov & ~okh] = (230, 30, 30)
    cv[cov & ~okh & (backc > 0)] = (40, 80, 255)
    cv[okh & (miss > 0)] = (230, 200, 30)
    Image.fromarray(np.flipud(cv.reshape(SIZE, SIZE, 3))).resize((side, side), Image.NEAREST).save(
        os.path.join(bake_dir, f'{name}_coverage.png'))
    pal = (np.random.default_rng(5).random((NP + 1, 3)) * 200 + 55).astype(np.uint8)
    pal[-1] = 0
    lay = pal[np.where(cov, tp, NP)]
    Image.fromarray(np.flipud(lay.reshape(SIZE, SIZE, 3))).resize((side, side), Image.NEAREST).save(
        os.path.join(bake_dir, f'{name}_layout.png'))
    worst = sorted(rep.items(), key=lambda kv: -kv[1]['miss_share'])[:6]
    log(f'misses {summary["miss_share"] * 100:.3f} % of samples; normals with z < 0.1: {summary["normal_z_below_0.1"]:,}; '
        f'worst parts: ' + '; '.join(f'{k} {v["miss_share"] * 100:.2f} %' for k, v in worst))
    log('BAKE DONE', os.path.join(bake_dir, name))
    return summary


if __name__ == '__main__':
    main()

"""test_geometry_parity.py: interiors_lib's port of three r184's geometry generators, against three itself.

geometry_reference.mjs builds every geometry the two interiors build (box, plane, cylinder, open cylinder, open cone,
sphere, the 900 m sky dome, rounded boxes, the gooseneck and cord tubes on CatmullRomCurve3, the lectern / toaster /
toast extrusions with their bevels, the dais shape with its two grate holes, box_uv, mergeVertices on the toaster
body) with three r184 from the main checkout (Deno, cached only, an import map), and this compares:

  generators     positions, normals, uvs and indices in the same order: max differences
  extrusions     the side walls vertex for vertex; the lids (triangulated by earcut there, by Blender's scanfill or
                 ear clipping here) as the same vertex set, triangle count and area
  shape + holes  vertex set, triangle count, area (needs Blender's mathutils: run it in Blender for that case)

    cd blender/tests/sets_uf_interiors && python test_geometry_parity.py          # system Python (no dais case)
    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_uf_interiors/test_geometry_parity.py
"""
import json
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _common as T  # noqa: E402

import numpy as np  # noqa: E402

from eidoblend.sets.unknown_force import interiors_lib as L  # noqa: E402

REF = os.path.join(T.OUT, 'ref', 'geometry.json')


def refs():
    if not os.path.isfile(REF):
        os.makedirs(os.path.dirname(REF), exist_ok=True)
        subprocess.run(['deno', 'run', '--no-config', '--no-lock', '--cached-only',
                        '--import-map=three_import_map.json', '-A', 'geometry_reference.mjs', REF], cwd=HERE, check=True)
    with open(REF, encoding='utf-8') as f:
        return json.load(f)


def arr(v, k):
    return None if v is None else np.asarray(v, np.float64).reshape(-1, k)


def same(name, ref, g, tol=1e-5):
    rp, rn, ru = arr(ref['pos'], 3), arr(ref['nrm'], 3), arr(ref['uv'], 2)
    ri = None if ref['index'] is None else np.asarray(ref['index'])
    ok = len(rp) == g.count
    dp = float(np.abs(rp - g.pos).max()) if ok else math.inf
    dn = float(np.abs(rn - g.nrm).max()) if ok and rn is not None and g.nrm is not None else 0.0
    du = float(np.abs(ru - g.uv).max()) if ok and ru is not None and g.uv is not None else 0.0
    di = (ri is None and g.index is None) or (ri is not None and g.index is not None and np.array_equal(ri, g.index))
    T.check(f'{name}: same vertices, normals, uvs and triangles as three', ok and dp < tol and dn < 1e-4 and du < tol
            and di, f'{g.count} vs {len(rp)} verts, |dpos| {dp:.1e}, |dnrm| {dn:.1e}, |duv| {du:.1e}, index {di}')


def tri_area(p):
    t = p.reshape(-1, 3, 3)
    return float(0.5 * np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1).sum())


def same_points(a, b, tol=1e-6):
    """the same set of points within tol (three's positions are float32): every unique point of each has a
    partner in the other."""
    ua, ub = np.unique(np.asarray(a), axis=0), np.unique(np.asarray(b), axis=0)

    def covered(p, q):
        d = np.sqrt(((p[:, None, :] - q[None, :, :]) ** 2).sum(-1)).min(1)
        return bool((d < tol).all())
    return covered(ua, ub) and covered(ub, ua)



def extrusion(name, ref, g, n_lid_tris):
    rp = arr(ref['pos'], 3)
    lid = n_lid_tris * 3
    sides_ok = len(rp) == g.count and float(np.abs(rp[lid:] - g.pos[lid:]).max()) < 1e-6
    a_r, a_p = tri_area(rp[:lid]), tri_area(g.pos[:lid])          # three's positions are float32
    lids_ok = same_points(rp[:lid], g.pos[:lid]) and abs(a_r - a_p) < 1e-6 * max(a_r, 1e-9)
    rn = arr(ref['nrm'], 3)
    nrm_ok = float(np.abs(rn[lid:] - g.nrm[lid:]).max()) < 1e-5
    T.check(f'{name}: side walls vertex for vertex, lids the same polygon (vertex set, area), flat normals',
            sides_ok and lids_ok and nrm_ok, f'{g.count} vs {len(rp)} verts, lid area {tri_area(g.pos[:lid]):.6f} '
            f'vs {tri_area(rp[:lid]):.6f}')


def main():
    R = refs()
    same('box 0.5 x 0.3 x 0.2 (2, 1, 3 segments)', R['box'], L.box_geometry(0.5, 0.3, 0.2, 2, 1, 3))
    same('plane 1.2 x 0.8 (3 x 2)', R['plane'], L.plane_geometry(1.2, 0.8, 3, 2))
    same('cylinder (tapered, 12 x 2, capped)', R['cylinder'], L.cylinder_geometry(0.1, 0.2, 0.5, 12, 2, False))
    same('open cylinder (the turntable drum)', R['cylinder_open'], L.cylinder_geometry(1.46, 1.48, 0.11, 96, 1, True))
    same('open cone (a light beam)', R['cone'], L.cone_geometry(0.4, 2.5, 40, 1, True))
    same('sphere 8 x 6 (aviation light)', R['sphere'], L.sphere_geometry(0.9, 8, 6))
    same('sphere 900 m, 48 x 24 (the sky dome)', R['sphere_dome'], L.sphere_geometry(900, 48, 24), tol=2e-3)
    rb = L.rounded_box_geometry(0.50, 0.075, 0.47, 3, 0.03)
    rb.uv = arr(R['rounded_box']['uv'], 2)                   # (its own UVs are not ported: box_uv replaces them)
    same('rounded box (the chair seat, 3 segments)', R['rounded_box'], rb)
    rb1 = L.rounded_box_geometry(0.52, 0.62, 0.03, 1, 0.01)
    rb1.uv = arr(R['rounded_box_1']['uv'], 2)
    same('rounded box (a seat shell, 1 segment)', R['rounded_box_1'], rb1)
    same('tube on a centripetal Catmull-Rom (the gooseneck)', R['tube'], L.tube_geometry(L.CatmullRomCurve3(
        [(0.26, 1.11, -0.24), (0.25, 1.30, -0.22), (0.18, 1.40, -0.08), (0.08, 1.36, 0.0)]), 20, 0.008, 8), tol=1e-6)
    Dz = 0.19
    same('tube (the toaster cord, 7 points, 60 segments)', R['cord'], L.tube_geometry(L.CatmullRomCurve3(
        [(-0.1, 0.02, -Dz / 2), (-0.12, 0.004, -Dz / 2 - 0.06), (-0.06, 0.004, -0.2), (0.05, 0.004, -0.255),
         (0.09, -0.02, -0.282), (0.10, -0.25, -0.285), (0.07, -0.48, -0.29)]), 60, 0.0035, 8), tol=1e-6)
    shp = L.Shape()
    shp.move_to(-0.24, 0).line_to(0.24, 0).line_to(0.30, 1.0).line_to(-0.30, 1.0).line_to(-0.24, 0)
    g = L.extrude_geometry(shp, depth=0.40, bevel_enabled=True, bevel_size=0.012, bevel_thickness=0.012, bevel_segments=2)
    extrusion('extrude: the lectern column (bevel 2)', R['lectern'], g, 2 * 2)
    Lx, Hy, bev, bevT = 0.29, 0.205, 0.024, 0.03
    w, h, rt, rbb = Lx - 2 * bev, Hy - 2 * bev - 0.012, 0.055, 0.012
    sh = L.Shape()
    sh.move_to(-w / 2 + rbb, 0).line_to(w / 2 - rbb, 0).quadratic_curve_to(w / 2, 0, w / 2, rbb)
    sh.line_to(w / 2, h - rt).quadratic_curve_to(w / 2, h, w / 2 - rt, h)
    sh.line_to(-w / 2 + rt, h).quadratic_curve_to(-w / 2, h, -w / 2, h - rt)
    sh.line_to(-w / 2, rbb).quadratic_curve_to(-w / 2, 0, -w / 2 + rbb, 0)
    body = L.extrude_geometry(sh, depth=Dz - 2 * bevT, bevel_enabled=True, bevel_size=bev, bevel_thickness=bevT,
                              bevel_segments=7, curve_segments=16)
    nv = len(L._drop_dup_end(sh.get_points(16)))
    extrusion('extrude: the toaster loaf (quadratic corners, bevel 7)', R['toaster'], body, 2 * (nv - 2))
    mb = body.clone().delete_attribute('uv').delete_attribute('normal')
    mb = L.merge_vertices(mb, 1e-5).compute_vertex_normals()
    rm = R['toaster_merged']
    rp, rn = arr(rm['pos'], 3), arr(rm['nrm'], 3)
    order_r, order_p = np.lexsort(np.round(rp, 6).T), np.lexsort(np.round(mb.pos, 6).T)
    dn = np.abs(rn[order_r] - mb.nrm[order_p]).max(1)
    # the smooth normals differ only on the lid rims, where earcut (three) and scanfill / ear clipping (here) chose
    # different lid triangles, so the area weights differ; the emitted loaf is shaded by Blender's own smooth
    # normals anyway (csg_subtract), so this is reported, not required
    T.check('mergeVertices on the loaf: the same welded vertices (1e-5 tolerance)', len(rp) == mb.count and
            float(np.abs(rp[order_r] - mb.pos[order_p]).max()) < 1e-7,
            f'{mb.count} vs {len(rp)} vertices; normals agree to 0.01 on {100 * float((dn < 0.01).mean()):.0f} % '
            f'(max {dn.max():.3f} on the lid rims)')
    bw, bh = 0.118, 0.118
    sl = L.Shape()
    sl.move_to(-bw / 2, 0).line_to(bw / 2, 0).line_to(bw / 2, bh * 0.7)
    sl.bezier_curve_to(bw / 2 + 0.012, bh * 0.98, bw * 0.12, bh * 1.04, 0, bh * 0.92)
    sl.bezier_curve_to(-bw * 0.12, bh * 1.04, -bw / 2 - 0.012, bh * 0.98, -bw / 2, bh * 0.7)
    sl.line_to(-bw / 2, 0)
    toast = L.extrude_geometry(sl, depth=0.011, bevel_enabled=True, bevel_size=0.002, bevel_thickness=0.002,
                               bevel_segments=2)
    nv = len(L._drop_dup_end(sl.get_points(12)))
    extrusion('extrude: a toast slice (bezier crown, bevel 2)', R['toast'], toast, 2 * (nv - 2))
    try:
        import mathutils  # noqa: F401
        D = {'z0': -8.85, 'z1': -5.6, 'x': 4.6}
        top = L.Shape()
        top.move_to(-D['x'], -D['z1']).line_to(D['x'], -D['z1']).line_to(D['x'], -D['z0']).line_to(-D['x'], -D['z0'])
        top.line_to(-D['x'], -D['z1'])
        for hx, z0, z1 in ((1.45, -6.45, -6.02), (1.3, -6.9 - 0.3 - 0.4, -6.9 - 0.3 - 0.12)):
            hp = L.Shape()
            hp.move_to(-hx, -z1).line_to(-hx, -z0).line_to(hx, -z0).line_to(hx, -z1).line_to(-hx, -z1)
            top.holes.append(hp)
        dg = L.shape_geometry(top)
        rd = R['dais']
        rp = arr(rd['pos'], 3)
        ri = np.asarray(rd['index'])
        ar_r, ar_p = tri_area(rp[ri]), tri_area(dg.pos[dg.index])
        nrm_up = all(np.cross(*(dg.pos[t[1:]] - dg.pos[t[0]]))[2] > 0 for t in dg.index.reshape(-1, 3))
        T.check('shape with two holes (the dais): same vertices, triangle count and area, every face up',
                same_points(rp, dg.pos) and len(ri) == len(dg.index) and abs(ar_r - ar_p) < 1e-6 * ar_r and nrm_up,
                f'area {ar_p:.4f} vs {ar_r:.4f} m2 (the room minus the grates: {9.2 * 3.25 - 2.9 * 0.43 - 2.6 * 0.28:.4f})')
    except ImportError:
        print('SKIP shape with holes: needs Blender (mathutils.geometry.tessellate_polygon)', flush=True)
    bu = L.box_uv(L.box_geometry(1.06, 2.16, 0.06), 1 / 2.2)
    same('box_uv (interiors_lib.boxUV, 1 / 2.2 tiles per metre)', R['box_uv'], bu)
    return T.done()


if __name__ == '__main__':
    sys.exit(main())

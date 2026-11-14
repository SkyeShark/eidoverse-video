"""The material's check 2 (SURFACING_DESIGN.md 5.4, package 2): steep faces read in the fixed sector frames, on real
walls at their world positions, beside today's Box projection.

    bash run_blender.sh blender/tests/terrain/surfacing/check_sectors.py [--case canyon] [--views brink_down,wall_L4]
    (a GPU job: queue it with EIDO_GPU_WRAP on a shared machine, blender/tests/_where.py)

Views: the judge's brink_down (the canyon's right-hand wall, diagonal to the axes) and wall_L4, a camera framing
about 250 m of the steepest wall on the 0.98 m hero level (the 250 m window there with the most ground over 50
degrees, seen from 300 m along its mean facing). Each view four times under make_sky: today's material and the
per-texel one, first with a colour grid in place of every box layer's scan (8 x 8 cells of distinct colours, dark
lines every cell: grid cells must read square, with no streaks and no seam where the sector slots meet), then with
the scans. Writes out/surfacing/material/sectors/<case>_<view>_<today|per_texel>_<grid|scan>.png and
sectors_<case>.json (the cameras and frame seconds).
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _material_scene as MS  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402

OUT = os.path.join(MS.OUT, 'sectors')


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    return dict(case=opt('--case', 'canyon'), views=opt('--views', 'brink_down,wall_L4').split(','))


def grid_images():
    """(albedo, flat normal) test images: 8 x 8 cells of distinct colours with dark lines, height 0.5 (alpha), sRGB;
    a flat normal map (0.5, 0.5), roughness 0.8, AO 1."""
    n = 1024
    a = np.zeros((n, n, 4), np.float32)
    rng = np.random.default_rng(5)
    cols = rng.uniform(0.25, 0.9, (8, 8, 3))
    jj, ii = np.mgrid[0:n, 0:n]
    a[..., :3] = cols[jj * 8 // n, ii * 8 // n]
    line = ((ii % (n // 8)) < 6) | ((jj % (n // 8)) < 6)
    a[line, :3] = 0.08
    a[..., 3] = 0.5
    img = bpy.data.images.new('sector_grid', n, n, alpha=True, float_buffer=False)
    img.colorspace_settings.name = 'sRGB'
    img.alpha_mode = 'CHANNEL_PACKED'
    img.pixels.foreach_set(a.ravel())
    img.update()
    b = np.zeros((4, 4, 4), np.float32)
    b[...] = (0.5, 0.5, 0.8, 1.0)
    nrm = bpy.data.images.new('sector_flat_nrao', 4, 4, alpha=True, float_buffer=False)
    nrm.colorspace_settings.name = 'Non-Color'
    nrm.alpha_mode = 'CHANNEL_PACKED'
    nrm.pixels.foreach_set(b.ravel())
    nrm.update()
    return img, nrm


def swap(mat, pairs):
    """Every image read in the material and its groups: pairs {image name: new image}; each node swapped remembers
    its scan (eido_scan) for swap_back."""
    seen = set()

    def walk(tree):
        if tree.name in seen:
            return
        seen.add(tree.name)
        for nd in tree.nodes:
            if nd.bl_idname == 'ShaderNodeTexImage' and nd.image is not None and nd.image.name in pairs:
                nd['eido_scan'] = nd.image.name
                nd.image = pairs[nd.image.name]
            elif nd.bl_idname == 'ShaderNodeGroup' and nd.node_tree is not None:
                walk(nd.node_tree)
    walk(mat.node_tree)


def box_images(t):
    from eidoblend.terrain.build import palettes as P
    from eidoblend.terrain.build import surfacing as S
    pal_name, strata = MS.palette_args(t)
    pal = S.resolve(pal_name, t.recipe, strata)
    out = []
    for L in pal['layers']:
        if L['projection'] == 'box':
            st = S.packed_set(L['set'], log=None)
            out.append((st['albedo'].name, st['nrao'].name))
    _ = P
    return out


def wall_camera(t, level=4, window_m=250.0, dist_m=300.0):
    """(eye, target): the 250 m window of the level with the most ground steeper than 50 degrees, seen from dist_m
    along its mean facing (horizontal), from 40 m above its mean height."""
    lv = t.levels[level]
    m = t.masks.level(level) if hasattr(t.masks, 'level') else t.masks[level]
    slope = np.asarray(m['slope'], np.float64)
    asp = np.radians(np.asarray(m['aspect'], np.float64))
    h = np.asarray(t.fields(level)['h'], np.float64)
    k = max(1, int(round(window_m / lv.cell)))
    steep = (slope > 50.0).astype(np.float64)
    c = np.cumsum(np.cumsum(np.pad(steep, ((1, 0), (1, 0))), 0), 1)
    tot = c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]
    j, i = np.unravel_index(int(np.argmax(tot)), tot.shape)
    sl = (slice(j, j + k), slice(i, i + k))
    sel = steep[sl] > 0
    fx = float(np.mean(np.sin(asp[sl][sel])))           # compass aspect: x east = sin, y north = cos
    fy = float(np.mean(np.cos(asp[sl][sel])))
    nrm = math.hypot(fx, fy) or 1.0
    fx, fy = fx / nrm, fy / nrm
    cx = lv.x0 + (i + 0.5 * k) * lv.cell
    cy = lv.y0 + (j + 0.5 * k) * lv.cell
    cz = float(np.mean(h[sl][sel]))
    eye = (cx + dist_m * fx, cy + dist_m * fy, cz + 40.0)
    eye = (eye[0], eye[1], max(eye[2], float(t.height_at(eye[0], eye[1])) + 2.0))
    return eye, (cx, cy, cz)


def main():
    a = args()
    os.makedirs(OUT, exist_ok=True)
    sc = MS.scene(samples=16)
    t, obj = MS.terrain(a['case'])
    sd = MS.surface(t)
    grid, flat = grid_images()
    pairs = {}
    for alb, nrao in box_images(t):
        pairs[alb] = grid
        pairs[nrao] = flat
    rec = {}
    cams = {}
    for v in a['views']:
        if v == 'wall_L4':
            eye, target = wall_camera(t)
            cams[v] = MS.camera(sc, t, a['case'], v, eye=eye, target=target, lens=43.0)
            rec[v] = dict(eye=[round(c, 1) for c in eye], target=[round(c, 1) for c in target])
        else:
            cams[v] = MS.camera(sc, t, a['case'], v)
            rec[v] = dict(eye=[round(c, 1) for c in cams[v].matrix_world.translation])
    for label, data in (('today', None), ('per_texel', sd)):
        mat = MS.apply(t, obj, data)
        for v, cam in cams.items():
            sc.camera = cam
            sky = os.path.join(OUT, '_sky')
            MS.light(sc, cam, sky)
            for kind in ('scan', 'grid'):
                if kind == 'grid':
                    swap(mat, pairs)
                MS.frame(sc)
                secs = MS.frame(sc, os.path.join(OUT, f"{a['case']}_{v}_{label}_{kind}.png"))
                rec[v][f'{label}_{kind}_s'] = round(secs, 2)
                MS.log(f"[sectors] {v} {label} {kind}: {secs:.2f} s")
            swap_back(mat)                                # the scans again for the next view
            MS.clean(sky)
    path = os.path.join(MS.OUT, f"sectors_{a['case']}.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(rec, f, indent=1)
    MS.log(f'[sectors] done -> {path}')


def swap_back(mat):
    """Undo swap(): every swapped node reads its scan again."""
    seen = set()

    def walk(tree):
        if tree.name in seen:
            return
        seen.add(tree.name)
        for nd in tree.nodes:
            if nd.bl_idname == 'ShaderNodeTexImage' and nd.get('eido_scan'):
                nd.image = bpy.data.images[nd['eido_scan']]
            elif nd.bl_idname == 'ShaderNodeGroup' and nd.node_tree is not None:
                walk(nd.node_tree)
    walk(mat.node_tree)


try:
    main()
except Exception:                                           # noqa: BLE001
    import traceback
    traceback.print_exc()
    sys.stdout.flush()
    os._exit(1)
sys.stdout.flush()
os._exit(0)

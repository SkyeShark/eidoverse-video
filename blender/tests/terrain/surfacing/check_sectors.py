"""The material's check 2 (SURFACING_DESIGN.md 5.4, package 2): steep faces read in the fixed sector frames, on real
walls at their world positions, beside today's Box projection.

    bash run_blender.sh blender/tests/terrain/surfacing/check_sectors.py [--case canyon] [--views brink_down,wall_L4]
        [--grid brink_down,wall_L4 | none] [--cells 2] [--plain] [--slope] [--only per_texel | today]
        [--options steep_hex_m=0,far_scale=1] [--mesh-res 1024] [--reps 3] [--tag s1]
    (a GPU job: queue it with EIDO_GPU_WRAP on a shared machine, blender/tests/_where.py)

The same runner serves check 8, the stride-1 comparison: --mesh-res 1024 draws the rings at stride 1 (four times the
vertices; with --only per_texel the masks stay off them), --reps 3 takes each view's best of three frames, and the
record holds the vertices, the seconds the terrain and its object took and the process's GPU memory after the
renders (Windows). --options: material options over the palette's, for the per-texel material.

Views: the judge's brink_down (the canyon's right-hand wall, diagonal to the axes) and wall_L4, a camera framing
about 250 m of the steepest wall on the 0.98 m hero level (the 250 m window there with the most ground over 50
degrees, seen from 300 m along its mean facing); any other name is a judge view of the case (approach_walk and
low_oblique: far slopes of one material, before and after). Each view under make_sky in today's material and the
per-texel one with the scans, and the --grid views (default: all) also with a colour grid in place of every box
layer's scan (--cells squares a tile side, default 8, each a distinct colour with dark lines and a pale bar along
its top: grid cells must read square, with no streaks and no seam where the sector slots meet). --plain: both
materials with one read per frame (no second lattice, no far read, no hex tiling), so the grid shows the Box
projection beside the sector frames alone; without it the grid shows the de-tiling too (hex tiling cuts it into
hexagons of a third of a tile). --slope: each view once more as an emission of the baked field normal's
slope (white at 90 degrees), what the layer weights read per texel. --level: each view once more as the per-texel
material's level map (options debug='level': one flat colour per level, so the window edges show). --no-palette:
bake the surface data without the palette (no far colour C or provenance P: the per-texel material then has no far
hand-off), for a palette whose palette bake cannot run. Writes
out/surfacing/material/sectors/<case>_<view>_<today|per_texel>_<grid|scan>.png, <case>_<view>_slope.png,
<case>_<view>_level.png and sectors_<case>.json (the cameras and frame seconds).
"""
import json
import math
import os
import sys
import time

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
    views = opt('--views', 'brink_down,wall_L4').split(',')
    grid = opt('--grid')
    options = {}
    for kv in (opt('--options') or '').split(','):
        if '=' in kv:
            k, v = kv.split('=', 1)
            options[k] = json.loads(v) if v[:1] in '-0123456789tfn"[' else v
    return dict(case=opt('--case', 'canyon'), views=views, options=options,
                grid=views if grid is None else [v for v in grid.split(',') if v and v != 'none'],
                slope='--slope' in a, level='--level' in a, mesh_res=int(opt('--mesh-res', '0')), only=opt('--only'),
                tag=opt('--tag', ''), reps=int(opt('--reps', '1')), plain='--plain' in a,
                cells=int(opt('--cells', '8')), no_palette='--no-palette' in a)


def slope_material(sd):
    """An emission of the baked field normal's slope / 90 degrees, read through eido_terrain_map."""
    from eidoblend.terrain.build import surfacing as S
    mat = bpy.data.materials.new('sector_slope')
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    tm = nt.nodes.new('ShaderNodeGroup')
    tm.node_tree = S.terrain_map_group(sd)
    m = nt.nodes.new('ShaderNodeMath')
    m.operation = 'DIVIDE'
    nt.links.new(tm.outputs['slope'], m.inputs[0])
    m.inputs[1].default_value = 90.0
    em = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(m.outputs[0], em.inputs['Color'])
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
    return mat


def grid_images(cells=8):
    """(albedo, flat normal) test images: cells x cells squares of distinct colours with dark lines, each with a
    pale bar along its top edge (so a turned or mirrored read shows), height 0.5 (alpha), sRGB; a flat normal map
    (0.5, 0.5), roughness 0.8, AO 1."""
    n = 1024
    c = max(1, int(cells))
    a = np.zeros((n, n, 4), np.float32)
    rng = np.random.default_rng(5)
    cols = rng.uniform(0.25, 0.9, (c, c, 3))
    jj, ii = np.mgrid[0:n, 0:n]
    a[..., :3] = cols[jj * c // n, ii * c // n]
    w = max(3, n // (c * 40))
    line = ((ii % (n // c)) < w) | ((jj % (n // c)) < w)
    top = (jj % (n // c)) > (n // c) - 4 * w                # row 0 is the image's bottom: the high rows are the top
    a[top, :3] = 0.95
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
    t0 = time.time()
    t, obj = MS.terrain(a['case'], mesh_res=a['mesh_res'] or None, mask_attributes=a['only'] != 'per_texel')
    t_obj = time.time() - t0
    sd = MS.surface(t, palette=None if a['no_palette'] else 'auto')
    grid, flat = grid_images(a['cells'])
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
    tag = f"_{a['tag']}" if a['tag'] else ''
    rec['mesh'] = dict(mesh_res=a['mesh_res'] or 512, vertices=len(obj.data.vertices),
                       triangles=len(obj.data.polygons), terrain_and_object_s=round(t_obj, 1))
    # --plain: one read per frame in both materials (no second lattice, no far read, no hex tiling), so the grid
    # shows the projections alone: the Box projection beside the sector frames
    plain = {None: dict(anti_tile=False, far_scale=1.0, far_detile=False, macro_mod=0.0),
             'data': dict(detile='offset', far_scale=1.0)}
    for label, data in (('today', None), ('per_texel', sd)):
        if a['only'] and label != a['only']:
            continue
        opts = dict(plain[None if data is None else 'data']) if a['plain'] else {}
        if data is not None:
            opts.update(a['options'])
        mat = MS.apply(t, obj, data, options=opts or None)
        for v, cam in cams.items():
            sc.camera = cam
            sky = os.path.join(OUT, '_sky')
            MS.light(sc, cam, sky)
            for kind in ('scan', 'grid'):
                if kind == 'grid':
                    if v not in a['grid']:
                        continue
                    swap(mat, pairs)
                MS.frame(sc)
                path = os.path.join(OUT, f"{a['case']}_{v}_{label}_{kind}{tag}.png")
                secs = min(MS.frame(sc, path if k == a['reps'] - 1 else None) for k in range(a['reps']))
                rec[v][f'{label}_{kind}_s'] = round(secs, 2)
                MS.log(f"[sectors] {v} {label} {kind}: {secs:.2f} s")
            swap_back(mat)                                # the scans again for the next view
            MS.clean(sky)
    if a['slope']:
        obj.data.materials.clear()
        obj.data.materials.append(slope_material(sd))
        for v, cam in cams.items():
            sc.camera = cam
            MS.frame(sc, os.path.join(OUT, f"{a['case']}_{v}_slope{tag}.png"))
    if a['level']:
        MS.apply(t, obj, sd, options=dict(a['options'], debug='level'))
        for v, cam in cams.items():
            sc.camera = cam
            MS.frame(sc, os.path.join(OUT, f"{a['case']}_{v}_level{tag}.png"))
    rec['mesh']['vram_mib'] = MS.vram_mib()               # this process's GPU memory after the renders
    path = os.path.join(MS.OUT, f"sectors_{a['case']}{tag}.json")
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

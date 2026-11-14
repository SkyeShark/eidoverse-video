"""The material's checks 6 and 7 (SURFACING_DESIGN.md 5.4, package 2): the hand-off to the far colour, and views that
stand on context rings.

    bash run_blender.sh blender/tests/terrain/surfacing/check_far.py [--case canyon]
        [--views aerial_down_canyon,low_oblique] [--old]
    (a GPU job: queue it with EIDO_GPU_WRAP on a shared machine, blender/tests/_where.py)

Per view, under make_sky, the per-texel material three times with only its hand-off distance moved
(surfacing.set_far_distance: a node value, nothing recompiles): as built (D0), near only (D0 beyond everything: the
layers to the horizon) and far only (D0 at 1 cm: the baked far colour C wherever the hand-off allows it, which is
never inside the hero windows). The same pixels drawn by the near material and by C are the hand-off's two sides,
so their difference is what a ring would show:
  - over the ground the far colour may draw (more than 64 main cells outside the outermost hero window): the CIELAB
    difference of the two renders' mean colours, and per pixel its median and 90th percentile;
  - the same over the pixels whose view distance lies in the band D0..1.5 D0, where the hand-off happens as built;
  - the share of the frame the far colour takes as built.
The region comes from an emission render of the level reader's Hero Outside and the view distance. --old adds
today's material (mesh attributes) on the same views, for the eye. Writes
out/surfacing/material/far/<case>_<view>_<as_built|near|far|old>.png, a 4x difference image, and far_<case>.json.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _material_scene as MS  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from eidoblend.terrain.build import surfacing as S  # noqa: E402

OUT = os.path.join(MS.OUT, 'far')
DIST_UNIT = 20000.0                       # the emission's view distance scale, metres
OUTSIDE_UNIT = 4000.0                     # ... and the Hero Outside scale


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    return dict(case=opt('--case', 'canyon'), views=opt('--views', 'aerial_down_canyon,low_oblique').split(','),
                old='--old' in a)


def srgb_to_lab(rgb):
    """CIELAB (D65) of display sRGB values 0..1, (..., 3)."""
    c = np.asarray(rgb, np.float64)
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = lin @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216.0 / 24389.0, np.cbrt(xyz), (24389.0 / 27.0 * xyz + 16.0) / 116.0)
    return np.stack([116.0 * f[..., 1] - 16.0, 500.0 * (f[..., 0] - f[..., 1]), 200.0 * (f[..., 1] - f[..., 2])], -1)


def read_png(path):
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)[::-1, :, :3]


def region_material(sd):
    """An emission of (Hero Outside / OUTSIDE_UNIT, view distance / DIST_UNIT, 1) through the terrain's reader."""
    mat = bpy.data.materials.new('far_region')
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    rd = nt.nodes.new('ShaderNodeGroup')
    rd.node_tree = S.reader_group(sd)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    nt.links.new(tc.outputs['Object'], rd.inputs['Position'])
    rd.inputs['Footprint'].default_value = 1.0
    cam = nt.nodes.new('ShaderNodeCameraData')
    comb = nt.nodes.new('ShaderNodeCombineColor')
    for k, (sock, unit) in enumerate(((rd.outputs['Hero Outside'], OUTSIDE_UNIT), (cam.outputs['View Distance'],
                                                                                 DIST_UNIT))):
        m = nt.nodes.new('ShaderNodeMath')
        m.operation = 'DIVIDE'
        nt.links.new(sock, m.inputs[0])
        m.inputs[1].default_value = unit
        nt.links.new(m.outputs[0], comb.inputs[k])
    comb.inputs[2].default_value = 1.0
    em = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(comb.outputs[0], em.inputs['Color'])
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
    return mat


def region_render(sc, me, mat, path):
    """(hero_outside metres, view distance metres, ground mask) per pixel, top row first: a one-sample float render
    with a black world and the Standard view, then the scene's own settings back."""
    slots = list(me.materials)
    me.materials.clear()
    me.materials.append(mat)
    idx = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get('material_index', idx)
    me.polygons.foreach_set('material_index', np.zeros(len(me.polygons), np.int32))
    vs, im = sc.view_settings, sc.render.image_settings
    keep = (sc.world, vs.view_transform, vs.look, vs.exposure, sc.eevee.taa_render_samples, im.file_format,
            im.color_depth, im.color_mode, sc.render.film_transparent)
    sc.world = bpy.data.worlds.get('far_black') or bpy.data.worlds.new('far_black')
    sc.world.color = (0.0, 0.0, 0.0)
    vs.view_transform, vs.look, vs.exposure = 'Standard', 'None', 0.0
    sc.eevee.taa_render_samples = 1
    sc.render.film_transparent = True
    im.file_format, im.color_depth, im.color_mode = 'OPEN_EXR', '32', 'RGBA'
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    px = px.reshape(h, w, 4)[::-1]
    (sc.world, vs.view_transform, vs.look, vs.exposure, sc.eevee.taa_render_samples, im.file_format, im.color_depth,
     im.color_mode, sc.render.film_transparent) = keep
    me.materials.clear()
    for m in slots:
        me.materials.append(m)
    me.polygons.foreach_set('material_index', idx)
    me.update()
    return px[..., 0] * OUTSIDE_UNIT, px[..., 1] * DIST_UNIT, px[..., 3] > 0.5


def compare(near, far, sel):
    if int(sel.sum()) < 50:
        return dict(pixels=int(sel.sum()))
    la, lb = srgb_to_lab(near[sel]), srgb_to_lab(far[sel])
    de = np.linalg.norm(la - lb, axis=-1)
    return dict(pixels=int(sel.sum()), mean_colour_dE=round(float(np.linalg.norm(la.mean(0) - lb.mean(0))), 2),
                pixel_dE_median=round(float(np.median(de)), 2), pixel_dE_p90=round(float(np.percentile(de, 90)), 2),
                near_mean_lab=[round(float(v), 1) for v in la.mean(0)],
                far_mean_lab=[round(float(v), 1) for v in lb.mean(0)])


def main():
    a = args()
    case = a['case']
    os.makedirs(OUT, exist_ok=True)
    sc = MS.scene(samples=16)
    t, obj = MS.terrain(case)
    sd = MS.surface(t)
    me = obj.data
    cams = {v: MS.camera(sc, t, case, v) for v in a['views']}
    mat = MS.apply(t, obj, sd)
    d0 = float(mat['eido_far_m'])
    cm = S._main_cell(sd)
    region = region_material(sd)
    rec = dict(case=case, far_m=d0, main_cell=cm, views={})
    sky = os.path.join(OUT, '_sky')
    for v, cam in cams.items():
        sc.camera = cam
        MS.light(sc, cam, sky)
        MS.frame(sc)
        imgs = {}
        for label, dist in (('as_built', d0), ('near', 1.0e7), ('far', 0.01)):
            S.set_far_distance(mat, dist)
            path = os.path.join(OUT, f'{case}_{v}_{label}.png')
            secs = MS.frame(sc, path)
            imgs[label] = read_png(path)
            MS.log(f'[far] {case} {v} {label}: {secs:.2f} s')
        S.set_far_distance(mat, d0)
        outside, dist, ground = region_render(sc, me, region, os.path.join(OUT, f'{case}_{v}_region.exr'))
        allowed = ground & (outside > S.FAR_FADE_MAIN_CELLS * cm)
        band = allowed & (dist > d0) & (dist < 1.5 * d0)
        beyond = allowed & (dist >= 1.5 * d0)
        r = dict(ground_px=int(ground.sum()), far_allowed_share=round(float(allowed.sum() / max(ground.sum(), 1)), 3),
                 far_as_built_share=round(float(beyond.sum() / max(ground.sum(), 1)), 3),
                 where_far_may_draw=compare(imgs['near'], imgs['far'], allowed),
                 in_the_band=compare(imgs['near'], imgs['far'], band),
                 beyond_the_band=compare(imgs['near'], imgs['far'], beyond),
                 view_distance_m=[round(float(dist[ground].min()), 0), round(float(dist[ground].max()), 0)])
        diff = np.clip(np.abs(imgs['near'] - imgs['far']) * 4.0, 0.0, 1.0)
        dimg = bpy.data.images.new('far_diff', diff.shape[1], diff.shape[0], alpha=False)
        dimg.pixels.foreach_set(np.concatenate([diff[::-1], np.ones(diff.shape[:2] + (1,), np.float32)], -1)
                                .astype(np.float32).ravel())
        dimg.filepath_raw = os.path.join(OUT, f'{case}_{v}_near_minus_far_x4.png')
        dimg.file_format = 'PNG'
        dimg.save()
        bpy.data.images.remove(dimg)
        rec['views'][v] = r
        MS.log(f'[far] {case} {v}: {json.dumps(r)}')
        MS.clean(sky)
    if a['old']:
        MS.apply(t, obj, None)
        for v, cam in cams.items():
            sc.camera = cam
            MS.light(sc, cam, sky)
            MS.frame(sc)
            secs = MS.frame(sc, os.path.join(OUT, f'{case}_{v}_old.png'))
            MS.log(f'[far] {case} {v} old: {secs:.2f} s')
            MS.clean(sky)
    path = os.path.join(MS.OUT, f'far_{case}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(rec, f, indent=1)
    MS.log(f'[far] done -> {path}')


try:
    main()
except Exception:                                           # noqa: BLE001
    import traceback
    traceback.print_exc()
    sys.stdout.flush()
    os._exit(1)
sys.stdout.flush()
os._exit(0)

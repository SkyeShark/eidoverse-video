"""tests/post_effects/test_verify_probes.py: the verifier's probes of the post effects, beside the porter's suite.

  --stage simplex    old_bw_film's simplex field (the shader's lattice and kernel, corner gradients from White Noise)
                     rendered alone: its statistics against the shader's simplex with random gradients (numpy), and
                     the thresholded dust it makes, looked at (no axis-aligned grid)
  --stage film       old_bw_film over 48 distinct 12 fps frames of the held still life: which frames carry dust (its
                     per-frame seed band), the dust looked at full size
  --stage portrait   underwater on a PORTRAIT frame (304 x 540, sensor fit AUTO: the sensor width spans the height),
                     the camera-ray rebuild's other branch, against numpy
  --stage live       on live renders of the still life: underwater's bubbles kept out of the Depth pass (WebGPU's
                     depthWrite false), their look; godrays in a closed room lit through gaps in one wall, at two
                     strengths; focus_blur's screen mode beside the lens, focus_objects keyed per frame and its saved
                     .blend in a fresh Blender; nuclear_explosion through the registry (built without a bake, removed)
  --stage godrays    the godrays room alone
Run from the main checkout (the GPU slot), after test_parity.py --stage sources:
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <worktree>/blender/tests/post_effects/test_verify_probes.py --stage simplex
"""
import json
import math
import os
import subprocess
import sys
import traceback

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ref_effects as REF                                        # noqa: E402
import still_life as SL                                          # noqa: E402

from eidoblend.look import frame_stats as FS                     # noqa: E402

A = SL.args()
STAGE = SL.arg(A, '--stage', 'simplex')
CHK = SL.Checks('verify')
OUT = os.path.join(SL.OUT, 'verify')
os.makedirs(OUT, exist_ok=True)


def _png(img, path):
    from PIL import Image
    Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(path)
    return path


def _probe_stage(sc, name, body):
    """A compositor group from body(g, a) -> {'Image': ...} put in the chain as stage `name`."""
    from eidoblend.look.post import chain
    from eidoblend.look.post._graph import fn
    grp = fn(f'verify_{name}', [('Image', 'C', (0, 0, 0, 1))], [('Image', 'C')], body, rebuild=True)
    t = chain.tree(sc)
    n = t.nodes.new('CompositorNodeGroup')
    n.node_tree = grp
    chain.add_stage(sc, 'over', name, n)
    return n


# ------------------------------------------------------------------------------------------------- simplex
def simplex():
    from eidoblend.look.post import screen_effects as SE
    m = SL.meta('opaque')
    stats = {}
    for tag, k, off in (('stats', 0.25, (1234.5, 777.25)), ('look', 0.045, (310.0, 95.0))):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sc = SL.post_scene(m, name=f'simplex_{tag}')

        def body(g, a, k=k, off=off):
            co = g.coords(a['Image'])
            v = g.call(SE._simplex_fn(), p=g.vec(co.fx * k + off[0], co.fy * k + off[1]))['v']
            return {'Image': g.rgba(g.splat(v), 1.0)}
        _probe_stage(sc, 'simplex', body)
        stats[tag] = SL.render_exr(sc, 1)[..., 0].astype(np.float64)
    v = stats['stats']
    got = (v.mean(), v.std(), (v > 0.7).mean(), REF.smoothstep(0.70, 0.88, v).mean(), (v < 0.3).mean())
    want = REF.simplex_stats(120000)
    names = ('mean', 'std', 'share > 0.7', 'region band mean', 'share < 0.3')
    rel = [abs(a - b) / max(abs(b), 1e-6) for a, b in zip(got, want)]
    CHK(np.isfinite(v).all() and v.min() >= -0.05 and v.max() <= 1.05,
        f'simplex field finite, in [0, 1] (min {v.min():.3f}, max {v.max():.3f})')
    CHK(max(rel) < 0.12, 'simplex statistics as the shader\'s (random gradients, numpy): ' + ', '.join(
        f'{n} {a:.4f} vs {b:.4f}' for n, a, b in zip(names, got, want)))
    look = stats['look']
    dust = 1.0 - REF.smoothstep(0.10, 0.30, look)                     # where a speck would darken the frame
    region = REF.smoothstep(0.70, 0.88, look)
    _png(np.stack([look, look, look], -1), os.path.join(OUT, 'simplex_field.png'))
    _png(np.stack([1.0 - dust, 1.0 - dust * 0.6, 1.0 - region * 0.5], -1), os.path.join(OUT, 'simplex_dust.png'))
    FS.sheet([os.path.join(OUT, 'simplex_field.png'), os.path.join(OUT, 'simplex_dust.png')],
             os.path.join(OUT, 'sheet_simplex.jpg'), cols=2, tile=640,
             labels=['old_bw_film simplex field (0.045 cells per px)',
                     'its specks (dark: v < 0.3) and dust regions (yellow: v > 0.7)'])
    # three's gaussianBlur kernel (vhs_tape's soft focus, sigma 1; the depth of field's near CoC, sigma 2) alone
    src = SL.source_arrays(m)[0].astype(np.float64)
    for sigma in (1, 2):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sc = SL.post_scene(m, name=f'gauss{sigma}')

        def body(g, a, sigma=sigma):
            co = g.coords(a['Image'])
            return {'Image': g.rgba(SE.three_gauss(g, a['Image'], co, sigma), 1.0)}
        _probe_stage(sc, f'gauss{sigma}', body)
        got = SL.render_exr(sc, 1)[..., :3].astype(np.float64)
        want = REF.three_gauss(src[..., :3], sigma)
        err = np.abs(got - want)
        CHK(err.mean() < 1e-4 and err.max() < 0.02, f"three's gaussianBlur(tex, null, {sigma}) (taps to "
                                                     f"+-{2 + 2 * sigma} px, s = {(3 + 2 * sigma) / 3:.2f} px): "
                                                     f"mean |blender - numpy| {err.mean():.2e}, max {err.max():.2e}")


# ------------------------------------------------------------------------------------------------- film dust
def film():
    from eidoblend.look.post import custom_effects as CFX
    m = SL.meta('opaque')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = SL.post_scene(m, name='film')
    CFX.apply_to(sc, 'old_bw_film')
    src = SL.source_arrays(m)[0][..., :3].astype(np.float64)
    H, W = src.shape[:2]
    u, v = REF.grid(H, W)
    scores = []
    for f in range(2, 98, 2):                                      # 48 distinct 12 fps frames, t 1/12 .. 4 s
        out = SL.render_exr(sc, f)[..., 0].astype(np.float64)      # (grey: r = g = b = the luma)
        # the clean frame, predicted from the shader's own weave and vignette; its exposure (the per-frame seed's
        # flicker, a fract(sin) hash) is one factor for the whole frame, read off as the median ratio
        t = math.floor(math.fmod(f / m['fps'], 24.0) * 12.0) / 12.0
        mx = 0.002 * math.cos(t * 3.0) * math.sin(t * 12.0 + 0.25)
        my = 0.002 * math.sin(t + 0.5) * math.cos(t * 15.0 + 0.25)
        vig = (u * (1 - v) * v * (1 - u) * 15.0) ** (0.4 + math.sin(t * 23.0) * math.cos(t * 8.0 + 0.5) * 0.05)
        pred = (REF.sample(src, u + mx, v + my) @ REF.LUM601) * vig
        ok = pred > 0.02
        ratio = out[ok] / pred[ok]
        specks = float((ratio < 0.7 * np.median(ratio)).mean())   # a speck: 30 % darker than the clean frame
        scores.append((specks, f))
    dusty = sorted([s for s in scores if s[0] > 2e-5], reverse=True)
    clean = sorted([s for s in scores if s[0] <= 2e-5])
    CHK(1 <= len(dusty) <= 18, f'old_bw_film: dust on {len(dusty)} of 48 frames (its seed bands are 15 % of frames; '
                               f'specked share of the frame: {[(f, round(s * 100, 3)) for s, f in dusty[:8]]} %); '
                               f'the clean frames {max(s for s, _f in clean) * 100 if clean else 0:.4f} % at most')
    shots = [SL.render_png(sc, os.path.join(OUT, 'film', f'film_f{f:03d}.png'), f) for _s, f in dusty[:4]]
    shots += [SL.render_png(sc, os.path.join(OUT, 'film', f'film_f{f:03d}.png'), f) for _s, f in clean[:2]]
    labels = [f'frame {f}: dust ({s * 100:.2f} % of the frame specked)' for s, f in dusty[:4]] + \
             [f'frame {f}: a clean frame' for _s, f in clean[:2]]
    FS.sheet(shots, os.path.join(OUT, 'sheet_film.jpg'), cols=3, tile=480, labels=labels)
    if dusty:
        FS.sheet(shots[:1], os.path.join(OUT, 'sheet_film_full.jpg'), cols=1, tile=960,
                 labels=[f'old_bw_film frame {dusty[0][1]}, its dust at full size'])


# ------------------------------------------------------------------------------------------------- portrait
def portrait():
    from eidoblend.look.post import chain
    from eidoblend.look.post import custom_effects as CFX
    res = (304, 540)
    d = os.path.join(OUT, 'src_portrait')
    os.makedirs(d, exist_ok=True)
    sc = SL.build()
    sc.render.resolution_x, sc.render.resolution_y = res
    pats = chain.save_frames_passes(sc, d, ('Depth', 'Normal'), name='src')
    sc.frame_set(1)
    s = sc.render.image_settings
    s.media_type, s.file_format, s.color_depth, s.color_mode = 'IMAGE', 'PNG', '8', 'RGB'
    sc.render.filepath = os.path.join(d, 'src_plain_0001.png')
    bpy.ops.render.render(write_still=True)
    meta = SL.camera_meta(sc)
    meta['res'] = list(res)
    meta['paths'] = {p: os.path.join(d, pat.replace('####', '0001')) for p, pat in pats.items()}
    with open(os.path.join(d, 'meta.json'), 'w') as fh:
        json.dump(meta, fh, indent=1)
    src, dep, nrm = SL.source_arrays(meta)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ps = SL.post_scene(meta, name='portrait')
    o = {'bubble_count': 0, 'fog_density': 0.12, 'caustic_scale': 1.0}
    CFX.apply_to(ps, 'underwater', {'underwater': dict(o)})
    from eidoblend.look.post import screen_effects as SE
    cam = REF.Cam(meta)
    CHK(abs(SE.tan_half_fov_y(ps) - cam.tan_y) < 1e-6,
        f'portrait AUTO fit: tan_half_fov_y {SE.tan_half_fov_y(ps):.4f}, {cam.tan_y:.4f} expected (sensor width / '
        f'2 lens: the width spans the taller side); the driver is held to it by the render below')
    frame = 30
    got = SL.render_exr(ps, frame).astype(np.float64)
    want = REF.underwater(src.astype(np.float64), dep.astype(np.float64), nrm.astype(np.float64), cam,
                          frame / meta['fps'], o, res[0] / res[1])
    err = np.abs(got[..., :3] - want[..., :3])
    big = float((err.max(axis=2) > 0.02).mean())
    CHK(err.mean() < 2e-3 and big < 0.005, f'underwater on a portrait frame: mean |blender - numpy| {err.mean():.2e}, '
                                           f'{big * 100:.3f}% of pixels off by > 0.02')
    p = SL.render_png(ps, os.path.join(OUT, 'portrait_underwater.png'), frame)
    FS.sheet([meta['paths']['Combined'].replace('src_0001_combined.exr', 'src_plain_0001.png'), p],
             os.path.join(OUT, 'sheet_portrait.jpg'), cols=2, tile=300,
             labels=['portrait still life (plain)', 'underwater, portrait (AUTO fit)'])


# ------------------------------------------------------------------------------------------------- live
def _render(sc, name, frame=1):
    sc.frame_set(frame)
    s = sc.render.image_settings
    s.media_type, s.file_format, s.color_depth, s.color_mode = 'IMAGE', 'PNG', '8', 'RGB'
    sc.render.filepath = os.path.join(OUT, name + '.png')
    bpy.ops.render.render(write_still=True)
    return sc.render.filepath


def bubbles():
    from eidoblend.look.post import chain
    from eidoblend.look.post import custom_effects as CFX
    from eidoblend.look.post import screen_effects as SE
    d = os.path.join(OUT, 'bubbles_passes')
    sc = SL.build()
    chain.save_frames_passes(sc, d, ('Depth',), name='plain')
    _render(sc, 'bubbles_plain')
    SE.underwater_bubbles(sc, sc.camera, 600, 6.0, 8.0)
    chain.save_frames_passes(sc, d, ('Depth',), name='bubbles')
    _render(sc, 'bubbles_only')
    d0 = SL.load_exr(os.path.join(d, 'plain_0001_depth.exr'))[..., 0]
    d1 = SL.load_exr(os.path.join(d, 'bubbles_0001_depth.exr'))[..., 0]
    c0 = SL.load_exr(os.path.join(d, 'plain_0001_combined.exr'))[..., :3]
    c1 = SL.load_exr(os.path.join(d, 'bubbles_0001_combined.exr'))[..., :3]
    seen = float((np.abs(c1 - c0).max(axis=2) > 0.02).mean())
    dd = float((np.abs(d1 - d0) > 1e-3 * np.maximum(d0, 1.0)).mean())
    CHK(seen > 0.002 and dd < 1e-4, f'bubbles: in the colour ({seen * 100:.2f}% of pixels changed) and not in the '
                                    f'Depth pass ({dd * 100:.4f}% of depth pixels changed): WebGPU\'s depthWrite false')
    bpy.data.objects.remove(bpy.data.objects['uw_bubbles'], do_unlink=True)
    for k in [n for n in sc.compositing_node_group.nodes if n.name.startswith('look:save:')]:
        sc.compositing_node_group.nodes.remove(k)
    e = CFX.apply_to(sc, 'underwater', {'underwater': {'bubble_count': 600}})
    anchor = tuple(e.uniforms['cam_pos'].default_value) if 'cam_pos' in e.uniforms else None
    CHK(anchor is not None and max(abs(a - b) for a, b in zip(anchor, sc.camera.matrix_world.translation)) < 1e-5,
        f"underwater uniforms['cam_pos']: the bubbles' anchor (WebGPU's camPosUniform) at the camera when applied "
        f"({anchor})")
    ps = [_render(sc, f'bubbles_underwater_f{f:02d}', f) for f in (1, 36)]
    before = [os.path.join(OUT, 'before', 'underwater_f01_dithered_bubbles.png'),
              os.path.join(OUT, 'before', 'underwater_f36_dithered_bubbles.png')]
    paths = [p for p in before if os.path.exists(p)] + ps
    FS.sheet(paths, os.path.join(OUT, 'sheet_bubbles.jpg'), cols=2, tile=640,
             labels=['before: dithered bubbles in the depth (frame 1)', 'before: frame 36',
                     'now: bubbles out of the depth, as WebGPU (frame 1)', 'now: frame 36'][-len(paths):])


def godrays():
    import bmesh
    from eidoblend.look.post import custom_effects as CFX
    shots = []
    from mathutils import Matrix
    for strength in (0.5, 1.5):
        sc = SL.build()
        # a closed room round the still life: a roof, the back, right and front walls, and on the sun's side (the
        # camera's left: the sun is low at the front left) a wall of posts 1.1 m apart, the only way light comes in
        me = bpy.data.meshes.new('slit_wall')
        bm = bmesh.new()
        for k in range(9):
            y0 = -9.0 + k * 3.6
            bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.LocRotScale((-3.4, y0 + 1.25, 3.0), None, (0.3, 2.5, 6.0)))
        for loc, size in (((2.5, 6.0, 6.15), (12.6, 30.6, 0.3)), ((8.65, 6.0, 3.0), (0.3, 30.6, 6.0)),
                          ((2.5, 21.15, 3.0), (12.6, 0.3, 6.0)), ((2.5, -9.15, 3.0), (12.6, 0.3, 6.0))):
            bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.LocRotScale(loc, None, size))
        bm.to_mesh(me)
        bm.free()
        wall = bpy.data.objects.new('slit_wall', me)
        sc.collection.objects.link(wall)
        wall.data.materials.append(bpy.data.materials['pillar'])
        # the sky dark: EEVEE lights a volume (and a room) with the world unoccluded unless a volume probe is baked,
        # and that haze would swamp the shafts (WebGPU's godrays added the light's shafts alone)
        next(n for n in sc.world.node_tree.nodes if n.type == 'BACKGROUND').inputs['Strength'].default_value = 0.0
        CFX.apply_to(sc, 'godrays', {'godrays': {'strength': strength, 'density': 0.03,
                                                 'size': (60.0, 60.0, 12.0), 'far': 80.0}})
        lt = next(o for o in sc.objects if o.type == 'LIGHT')
        CHK(abs(lt.data.volume_factor - strength / 0.5) < 1e-6,
            f'godrays strength {strength}: the sun\'s volume factor {lt.data.volume_factor:.2f}')
        shots.append(_render(sc, f'godrays_slits_s{strength:g}'))
    a, b = (FS.read_rgb(p).astype(float) for p in shots)
    CHK(b.mean() > a.mean() + 2.0, f'godrays: strength 1.5 brightens the beams over strength 0.5 (mean {a.mean():.1f} '
                                   f'-> {b.mean():.1f} levels)')
    FS.sheet(shots, os.path.join(OUT, 'sheet_godrays.jpg'), cols=2, tile=640,
             labels=['godrays in a closed room, the sun through gaps in its wall, the sky dark, strength 0.5 (fog '
                     '0.03 / m)', 'strength 1.5 (the sun\'s volume factor 3)'])


def focus():
    from eidoblend.look.post import custom_effects as CFX
    shots, labels = [], []
    sc = SL.build()
    suz = bpy.data.objects['suzanne']
    CFX.apply_to(sc, 'focus_blur', {'focus_blur': {'mode': 'screen', 'focus_objects': [suz], 'focal_length': 1.0,
                                                   'bokeh_scale': 2.0}})
    shots.append(_render(sc, 'focus_screen_suzanne_f1_b2'))
    labels.append("focus_blur 'screen' on Suzanne, focal_length 1, bokeh_scale 2 (three's DOF)")
    before = os.path.join(OUT, 'before', 'focus_lens_suzanne.png')
    if os.path.exists(before):
        shots.append(before)
        labels.append("focus_blur 'lens' (the default), the same knobs: f/0.053 (round one's)")
    CFX.clear(sc)
    # a target walking away from the camera: the keyed focus follows it, as WebGPU's update() recomputed it
    tgt = bpy.data.objects.new('focus_target', None)
    sc.collection.objects.link(tgt)
    for f, y in ((1, 0.0), (48, 22.0)):
        tgt.location = (0.0, y, 1.0)
        tgt.keyframe_insert('location', frame=f)
    e = CFX.apply_to(sc, 'focus_blur', {'focus_blur': {'mode': 'screen', 'focus_objects': [tgt], 'focal_length': 3.0,
                                                       'bokeh_scale': 10.0}})
    sock = e.uniforms['focus_distance']
    errs = []
    from mathutils import Vector
    for f in (1, 24, 48):
        sc.frame_set(f)
        cm = sc.camera.matrix_world
        want = (tgt.matrix_world.translation - cm.translation).dot((cm.to_3x3() @ Vector((0, 0, -1))).normalized())
        errs.append(abs(sock.default_value - want))
    CHK(max(errs) < 1e-3, f'focus_objects: focus_distance keyed every frame to the target\'s distance along the view '
                          f'(max error {max(errs):.2e} m at frames 1, 24, 48)')
    for f in (1, 48):
        shots.append(_render(sc, f'focus_screen_target_f{f:02d}', f))
        labels.append(f"focus_blur 'screen' following a target, frame {f} (focal_length 3, bokeh_scale 10)")
    blend = os.path.join(OUT, 'focus_keyed.blend')
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    exe = bpy.app.binary_path
    out = os.path.join(OUT, 'focus_reopened_')
    subprocess.run([exe, '-b', '--factory-startup', blend, '-o', out + '#', '-F', 'PNG', '-f', '48'],
                   capture_output=True, text=True, timeout=600)
    got = out + '48.png'
    if os.path.exists(got):
        dd = float(np.abs(FS.read_rgb(got).astype(float) - FS.read_rgb(shots[-1]).astype(float)).mean())
        CHK(dd < 1.0, f'focus_blur screen saved .blend, frame 48 in a fresh Blender: the same picture (mean diff '
                      f'{dd:.2f})')
    else:
        CHK(False, 'focus_blur screen saved .blend did not render in a fresh Blender')
    for k in ('focus_keyed.blend1',):
        if os.path.exists(os.path.join(OUT, k)):
            os.remove(os.path.join(OUT, k))
    FS.sheet(shots, os.path.join(OUT, 'sheet_focus.jpg'), cols=2, tile=640, labels=labels)


def nuclear():
    from eidoblend.look.post import custom_effects as CFX
    sc = SL.build()
    e = CFX.apply_to(sc, 'nuclear_explosion', {'nuclear_explosion': {'disable_for_perf_test': True, 'bake': None,
                                                                    'scale': 0.2}})
    names = [n for _s, n, _x in CFX.applied(sc)]
    objs = [str(x) for x in sc.get('eido_nuclear_explosion', [])]
    CHK('nuclear_explosion' in names and objs and all(x in bpy.data.objects for x in objs),
        f'nuclear_explosion through the registry: the SDF volumes\' cloud built ({objs}), listed by applied(); '
        f'uniforms {sorted(e.uniforms)}')
    CFX.remove(sc, 'nuclear_explosion')
    CHK(not any(x in bpy.data.objects for x in objs) and 'eido_nuclear_explosion' not in sc
        and 'nuclear_explosion' not in [n for _s, n, _x in CFX.applied(sc)],
        'remove(): the cloud\'s volumes and lights gone')


def live():
    for fn_ in (bubbles, godrays, focus, nuclear):
        try:
            fn_()
        except Exception as ex:                                   # noqa: BLE001
            traceback.print_exc()
            CHK(False, f'{fn_.__name__}: {ex!r}')


try:
    {'simplex': simplex, 'film': film, 'portrait': portrait, 'live': live, 'godrays': godrays}[STAGE]()
except Exception:                                                # noqa: BLE001
    traceback.print_exc()
    CHK.fail.append('exception: ' + traceback.format_exc().splitlines()[-1])
CHK.save('verify_' + STAGE)

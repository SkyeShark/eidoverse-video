"""tests/post_era/test_screen_effects.py: the registry's smaller screen-space effects (look/post/screen_effects.py) on
real frames: each at its WebGPU defaults and with options turned, sheets; opacity 0 gives the plain frame; the
deterministic ones against their shaders in numpy (wavy, kaleidoscope, dithering, chromatic_aberration_alpha,
bw_halftone, bleach_bypass); the time-driven ones change from frame to frame.

  --stage saved   every effect over test_era_looks.py's saved sources (run its --stage sources first)
  --stage live    on a live render of the era probe scene: underwater with its bubbles (frames 1 and 24), the
                  registry's own two-effect example (effects ['underwater', 'vhs_tape']: world under, signal over),
                  retro_wireframe in green, amber and multicolor, and its cleanup
Run from the main checkout (GPU jobs; on a shared machine queue them with EIDO_GPU_WRAP: blender/tests/_where.py), each
stage in its own Blender:
    bash run_blender.sh <worktree>/blender/tests/post_era/test_screen_effects.py --stage saved
    bash run_blender.sh <worktree>/blender/tests/post_era/test_screen_effects.py --stage live
"""
import json
import os
import sys
import traceback

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scenes as SC                                            # noqa: E402
import ref_era as REF                                          # noqa: E402

from eidoblend.look import frame_stats as FS                    # noqa: E402

A = SC.args()
STAGE = SC.arg(A, '--stage', 'saved')
OUT = os.path.join(SC.OUT, 'screen')
SRC = os.path.join(SC.OUT, 'era', 'src')
FAIL, REPORT = [], {}
os.makedirs(OUT, exist_ok=True)
CASES = [
    ('wavy', {}, {'amplitude': 18, 'frequency': 0.05, 'phase': 1.0}),
    ('kaleidoscope', {}, {'segments': 9, 'rotate': 0.4}),
    ('jitter', {}, {'speed': 3.0, 'amplitude': 0.35}),
    ('melt', {}, {'speed': 1.5, 'swirl': 0.6}),
    ('dithering', {}, {'levels': 3}),
    ('chromatic_aberration_alpha', {}, {'amount': 0.012, 'angle': 0.6}),
    ('bw_halftone', {}, {'dot_size': 3.0, 'angle': 15, 'ink_color': (0.05, 0.02, 0.12), 'paper_color': (0.9, 0.85, 0.7)}),
    ('bleach_bypass', {}, {'amount': 0.6}),
    ('hash_blur', {}, {'amount': 0.02, 'repeats': 24}),
    ('crt', {}, {'opacity': 0.85}),
    ('vhs_tape', {}, {'intensity': 2.0}),
    ('rain_on_camera', {}, {'amount': 1.5, 'drop_size': 0.3, 'speed': 2.0}),
    ('full_toon', {}, {'near_levels': 5, 'hue_shift': 0.8, 'outline_threshold': 0.3, 'saturation': 1.1}),
    ('blueprint', {}, {'cell_px': 30, 'paper_color': (0.03, 0.08, 0.2), 'rim_weight': 0.5}),
    ('cross_hatch', {}, {'hatch_strength': 1.0, 'wiggle': 0.6, 'outline_strength': 1.8}),
    ('underwater', {'bubble_count': 0}, {'bubble_count': 0, 'fog_density': 0.12, 'caustic_scale': 1.0}),
]
MEADOW = os.path.join(SC.WORKTREE, 'blender', 'tests', 'look', 'out', 'meadow', 'meadow_camera.blend')


def source_camera(name, frame):
    """The source render's camera at `frame`: (matrix, vertical fov, clip start, clip end). blueprint and cross_hatch
    turn the Normal pass to view space with it, underwater rebuilds positions along its rays. The era probe's fixed
    camera is rebuilt as scenes.era_probe placed it; the meadow's is read from its .blend."""
    import math
    from mathutils import Matrix, Vector
    if name == 'era_probe':
        pos, aim = SC.t2b(1.2, 1.4, 2.2), SC.t2b(0.0, 1.1, 0.0)
        rot = (Vector(aim) - Vector(pos)).to_track_quat('-Z', 'Y').to_matrix().to_4x4()
        return Matrix.Translation(pos) @ rot, math.radians(50.0), 0.05, 100.0
    bpy.ops.wm.open_mainfile(filepath=MEADOW, load_ui=False)
    sc = bpy.context.scene
    sc.frame_set(frame)
    cd = sc.camera.data
    cd.sensor_fit = 'VERTICAL'
    return sc.camera.matrix_world.copy(), cd.angle_y, cd.clip_start, cd.clip_end


def _png(p):
    return np.asarray(__import__('PIL.Image', fromlist=['Image']).open(p).convert('RGB')).astype(float)


def live_underwater():
    """underwater on a live render (not saved frames): the era probe scene with the pass, its Depth and Normal from the
    Render Layers, and the bubbles rising round the camera (Geometry Nodes), frames 1 and 24; then the registry's own
    example, effects ['underwater', 'vhs_tape'] in one call (custom_effects_deno.js's header), then retro_wireframe."""
    from eidoblend.look.post import chain
    from eidoblend.look.post import custom_effects as CFX
    from eidoblend.look.post import history as HI
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc, _h = SC.era_probe(frames=(1, 48))
    HI.set_history_dir(sc, os.path.join(OUT, 'history'))
    e = CFX.apply_to(sc, 'underwater', {'underwater': {'bubble_count': 600}})
    check(e.effects[0]['layer'] == 'under' and 'uw_bubbles' in bpy.data.objects,
          'underwater (live): locked under the overlay, the bubbles object added')
    paths = []
    for f in (1, 24):
        p = os.path.join(OUT, f'live_underwater_f{f:02d}.png')
        SC.render_png(sc, p, f)
        paths.append(p)
    a = [_png(p) for p in paths]
    moved = float((np.abs(a[0] - a[1]).max(axis=2) > 6).mean())
    check(moved > 0.02, f'underwater (live): caustics, rays and bubbles move between frames 1 and 24 ({moved * 100:.1f}% '
                        f'of pixels)')
    # the registry's own example (custom_effects_deno.js header): effects: ['underwater', 'vhs_tape'] with opts for
    # both, in one call. The world effect goes under the overlay, the signal effect over it, each in the given order.
    CFX.clear(sc)
    e2 = CFX.apply_to(sc, ['underwater', 'vhs_tape'], {'underwater': {'bubble_count': 600, 'fog_density': 0.1},
                                                         'vhs_tape': {'intensity': 1.0}})
    st = [(s, n) for s, n, _x in chain.stages(sc)]
    check(st == [('under', 'underwater'), ('over', 'vhs_tape')] and set(e2.uniforms) == {'underwater', 'vhs_tape'},
          f"effects ['underwater', 'vhs_tape']: underwater under the overlay, vhs_tape over it ({st}); uniforms by "
          f"effect name")
    p2 = os.path.join(OUT, 'live_underwater_vhs_tape_f24.png')
    SC.render_png(sc, p2, 24)
    paths.append(p2)
    d = float((np.abs(_png(p2) - a[1]).max(axis=2) > 6).mean())
    check(d > 0.05, f"['underwater', 'vhs_tape'] differs from underwater alone at frame 24 on {d * 100:.1f}% of pixels "
                    f"(the tape's wobble, noise and tint over the water)")
    FS.sheet(paths, os.path.join(OUT, 'live_underwater_sheet.jpg'), cols=3, tile=560,
             labels=['underwater live, frame 1', 'underwater live, frame 24 (the bubbles have risen)',
                     "effects ['underwater', 'vhs_tape'], frame 24 (the registry's example)"])
    # retro_wireframe: a material override on the live scene (geometry-side: no compositor stage). The same scene,
    # the water taken off (one character build per Blender session: hooks_needed, the characters' clip cache)
    from eidoblend.look.post import screen_effects as SE
    CFX.clear(sc)
    check('uw_bubbles' not in bpy.data.objects and not chain.stages(sc),
          'clear(): the passes and the bubbles round the camera are gone (the scene as it was)')
    w = CFX.apply_to(sc, 'retro_wireframe', {'retro_wireframe': {'color': 'green', 'line_width': 1.5}})
    wp = []
    for name in ('green', 'amber', 'multicolor'):
        SE.set_wire_color(sc, w.uniforms, name)
        p = os.path.join(OUT, f'live_retro_wireframe_{name}.png')
        SC.render_png(sc, p, 8)
        wp.append(p)
    lit = np.asarray(__import__('PIL.Image', fromlist=['Image']).open(wp[0]).convert('RGB')).astype(float)
    green_px = float(((lit[..., 1] > 60) & (lit[..., 0] < lit[..., 1] * 0.5)).mean())
    check(0.01 < green_px < 0.6, f'retro_wireframe green: {green_px * 100:.1f}% of pixels are green lines on black')
    SE.retro_wireframe_cleanup(sc)
    p = os.path.join(OUT, 'live_retro_wireframe_cleanup.png')
    SC.render_png(sc, p, 8)
    wp.append(p)
    check(bpy.context.view_layer.material_override is None and not any('retro_wireframe_tris' in o.modifiers
                                                                       for o in sc.objects if o.type == 'MESH'),
          'retro_wireframe cleanup: the override and the per-triangle modifiers are gone')
    FS.sheet(wp, os.path.join(OUT, 'live_retro_wireframe_sheet.jpg'), cols=2, tile=640,
             labels=['retro_wireframe green', 'amber (set_wire_color)', 'multicolor (per triangle)',
                     'after retro_wireframe_cleanup()'])


def check(ok, what):
    print(f"[screen] {'PASS' if ok else 'FAIL'}: {what}", flush=True)
    if not ok:
        FAIL.append(what)


def meta(name):
    with open(os.path.join(SRC, name, 'meta.json')) as f:
        return json.load(f)


def load_exr(path):
    im = bpy.data.images.load(path, check_existing=False)
    a = np.array(im.pixels[:], np.float32).reshape(im.size[1], im.size[0], 4)[::-1]
    bpy.data.images.remove(im)
    return a


def exr(scene, frame):
    scene.frame_set(frame)
    with bpy.context.temp_override(scene=scene):
        bpy.ops.render.render(write_still=False, scene=scene.name)
    p = os.path.join(OUT, '_tmp.exr')
    s = scene.render.image_settings
    s.media_type, s.file_format, s.color_depth, s.exr_codec = 'IMAGE', 'OPEN_EXR', '32', 'ZIP'
    bpy.data.images['Render Result'].save_render(p, scene=scene)
    return load_exr(p)


# ------------------------------------------------------------------------------------------------- numpy references
def ref(name, src, o):
    """The shader in numpy (top-down, uv y down), for the deterministic effects; None for the others."""
    H, W = src.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    u, v = (xx + 0.5) / W, (yy + 0.5) / H
    c, al = src[..., :3].astype(np.float64), src[..., 3:4].astype(np.float64)
    op = o.get('opacity', 1.0)
    if name == 'wavy':
        amp, fr, ph = o.get('amplitude', 10), o.get('frequency', 0.1), o.get('phase', 0.0)
        sh = amp * np.sin(fr * (v * H) + ph)
        e = REF.sample(src.astype(np.float64), u + sh / W, v)
        return c + (e[..., :3] - c) * op
    if name == 'kaleidoscope':
        seg = 2 * np.pi / o.get('segments', 6)
        px, py = u - 0.5, v - 0.5
        r = np.sqrt(px * px + py * py)
        a1 = np.mod(np.arctan2(py, px) + o.get('rotate', 0.0), seg)
        aa = np.abs(a1 - seg / 2)
        nx, ny = np.clip(np.cos(aa) * r + 0.5, 0.001, 0.999), np.clip(np.sin(aa) * r + 0.5, 0.001, 0.999)
        e = REF.sample(c, nx, ny)
        return c + (e - c) * op
    if name == 'dithering':
        lv = o.get('levels', 8.0)
        x, y = np.mod(np.floor(xx + 0.5), 4), np.mod(np.floor(yy + 0.5), 4)
        bayer = np.mod(np.floor(x + 1) * np.floor(y + 1) * 17, 16) / 16 - 0.5
        q = np.floor((np.sqrt(np.maximum(c, 0)) + (bayer / lv)[..., None]) * (lv - 1) + 0.5) / (lv - 1)
        return c + (q * q - c) * op
    if name == 'chromatic_aberration_alpha':
        amt, ang = o.get('amount', 0.005), o.get('angle', 0.0)
        ox, oy = np.cos(ang) * amt, np.sin(ang) * amt
        cr, cb = REF.sample(src.astype(np.float64), u + ox, v + oy), REF.sample(src.astype(np.float64), u - ox, v - oy)
        r = c[..., 0] + (cr[..., 0] - c[..., 0]) * cr[..., 3]
        b = c[..., 2] + (cb[..., 2] - c[..., 2]) * cb[..., 3]
        sh = np.stack([r, c[..., 1], b], -1)
        return c + (sh - c) * op
    if name == 'bw_halftone':
        ratio = H / W
        shx, shy = u - 0.5, v * ratio - ratio * 0.5
        ang = np.radians(o.get('angle', 45.0))
        sa, ca = np.sin(ang), np.cos(ang)
        d = np.pi / o.get('dot_size', 1.8) * 680.0
        t1, t2 = (shx * sa + shy * ca + 0.5) * d, (shx * ca - shy * sa + ratio * 0.5) * d
        raster = 0.5 + np.cos(t1) * 0.25 + np.cos(t2) * 0.25
        avg = c[..., 0] * 0.2125 + c[..., 1] * 0.7154 + c[..., 2] * 0.0721
        th = o.get('threshold', 0.4)
        gray = np.clip((raster * th + avg - th) / max(1 - th, 1e-4), 0, 1)[..., None]
        ink, paper = np.array(o.get('ink_color', (0, 0, 0))), np.array(o.get('paper_color', (1, 1, 1)))
        col = ink + (paper - ink) * gray
        return c + (col - c) * op
    if name == 'bleach_bypass':
        lum = c @ REF.LUM
        L = np.clip((lum - 0.45) * 10, 0, 1)[..., None]
        blend = lum[..., None]
        r1, r2 = blend * c * 2, 1 - 2 * (1 - blend) * (1 - c)
        new = r1 + (r2 - r1) * L
        A2 = al * o.get('amount', 1.0)
        bl = new * A2 + c * (1 - A2)
        return c + (bl - c) * op
    return None


def run():
    from eidoblend.look.post import custom_effects as CFX
    from eidoblend.look.post import history as HI
    for name, frame in (('meadow', 60), ('era_probe', 8)):
        cam_m, fov, c_start, c_end = source_camera(name, frame)
        m = meta(name)
        src = load_exr(m['paths']['Combined'].replace(f"{m['frames'][0]:04d}", f'{frame:04d}'))
        plain = os.path.join(SRC, name, f'src_plain_{frame:04d}.png')
        paths, labels = [plain], [f'{name} plain, frame {frame}']
        for eff, o_def, o_alt in CASES:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            sc = SC.post_scene(m['paths'], tuple(m['view']), fps=int(m['fps']), frames=(1, 400),
                               res=tuple(m['res']), name=f'post_{eff}',
                               clip_end=m.get('clip_end', {'meadow': 2000.0, 'era_probe': 100.0}[name]))
            sc.camera.matrix_world = cam_m                       # the source camera (view space, rays)
            sc.camera.data.sensor_fit = 'VERTICAL'
            sc.camera.data.angle_y = fov
            sc.camera.data.clip_start, sc.camera.data.clip_end = c_start, c_end
            HI.set_history_dir(sc, os.path.join(OUT, 'history'))
            for tag, o in (('defaults', o_def), ('options', o_alt)):
                e = CFX.apply_to(sc, eff, {eff: dict(o)})
                p = os.path.join(OUT, f'{name}_{eff}_{tag}.png')
                SC.render_png(sc, p, frame)
                paths.append(p)
                labels.append(f'{eff} {o if o else "(WebGPU defaults)"}')
                if name == 'meadow' and eff == 'full_toon' and tag == 'defaults':
                    # the sky (nothing drawn: the Normal pass is 0 there) is cel-shaded, not inked in the outline
                    # colour: WebGPU's cleared normal buffer gave no normal edge between background pixels
                    dep = load_exr(m['paths']['Depth'].replace(f"{m['frames'][0]:04d}", f'{frame:04d}'))[..., 0]
                    sky = dep > 0.99 * c_end
                    got = exr(sc, frame)[..., :3]
                    ink = np.abs(got - np.array([0.05, 0.05, 0.08])).max(axis=2) < 0.01
                    share = float(ink[sky].mean()) if sky.any() else 1.0
                    REPORT['full_toon_sky_inked'] = {'sky_share_of_frame': round(float(sky.mean()), 4),
                                                     'inked_share_of_sky': round(share, 5)}
                    check(sky.mean() > 0.1 and share < 0.01, f'full_toon: the sky ({sky.mean() * 100:.0f}% of the '
                                                             f'frame) is cel-shaded, not inked: {share * 100:.2f}% '
                                                             f'of it in the outline colour')
                if name == 'meadow':
                    want = ref(eff, src, {k: v for k, v in o.items() if k != 'repeats'})
                    if want is not None:
                        got = exr(sc, frame)[..., :3].astype(np.float64)
                        err = np.abs(got - want)
                        big = float((err.max(axis=2) > 0.02).mean())
                        REPORT.setdefault('parity', {})[f'{eff} {tag}'] = {'mean': round(float(err.mean()), 6),
                                                                           'over_0.02': round(big, 5)}
                        check(err.mean() < 2e-3 and big < 0.005, f'parity {eff} {tag}: mean |blender - numpy| '
                                                                 f'{err.mean():.2e}, {big * 100:.3f}% off by > 0.02')
                    if tag == 'options':
                        if 'opacity' in e.uniforms:                   # (rain_on_camera has none, as WebGPU's)
                            e.uniforms['opacity'].default_value = 0.0
                            z = exr(sc, frame)[..., :3]
                            d0 = float(np.abs(z - src[..., :3]).max())
                            check(d0 < 1e-4, f'{eff}: opacity 0 is the plain frame (max diff {d0:.1e})')
                            e.uniforms['opacity'].default_value = 1.0
                        if eff in ('jitter', 'melt', 'wavy', 'crt', 'vhs_tape', 'rain_on_camera', 'underwater'):
                            if eff == 'wavy':
                                e.uniforms['animate'].default_value = 1.0
                                e.uniforms['anim_speed'].default_value = 3.0
                            a1 = exr(sc, frame)[..., :3]
                            from eidoblend.look.post import chain
                            chain.source(sc).frame_offset = -3          # hold the source: frame + 3 reads frame
                            a2 = exr(sc, frame + 3)[..., :3]
                            chain.source(sc).frame_offset = 0
                            moved = float((np.abs(a1 - a2).max(axis=2) > 0.01).mean())
                            check(moved > 0.01, f'{eff}: time drives it (frames {frame} and {frame + 3} over the '
                                                f'same source frame differ on {moved * 100:.1f}% of pixels)')
                CFX.clear(sc)
        FS.sheet(paths[:12], os.path.join(OUT, f'{name}_screen_sheet_a.jpg'), cols=3, tile=560, labels=labels[:12])
        FS.sheet(paths[12:24], os.path.join(OUT, f'{name}_screen_sheet_b.jpg'), cols=3, tile=560,
                 labels=labels[12:24])
        FS.sheet(paths[24:], os.path.join(OUT, f'{name}_screen_sheet_c.jpg'), cols=3, tile=560, labels=labels[24:])


if STAGE not in ('saved', 'live'):
    raise SystemExit(f'test_screen_effects: --stage saved | live, not {STAGE!r}')
if not SC.already_done(OUT, STAGE, os.path.abspath(__file__)):
    try:
        run() if STAGE == 'saved' else live_underwater()
    except Exception:
        traceback.print_exc()
        FAIL.append('exception: ' + traceback.format_exc().splitlines()[-1])
    REPORT['fail'] = FAIL
    with open(os.path.join(OUT, f'report_{STAGE}.json'), 'w') as f:
        json.dump(REPORT, f, indent=1, default=str)
    SC.mark_done(OUT, STAGE)
    print(f"[screen] {'FAIL ' + str(len(FAIL)) if FAIL else 'PASS'}", flush=True)

"""tests/post_era/test_era_looks.py: every era-looks preset rendered on real scene frames, checked against a numpy
transcription of era_looks.js, and looked at.

  --stage sources   renders the source frames once (EEVEE; Combined, Depth and Normal saved as EXR sequences):
                    era_probe   the WebGPU era probe rebuilt (work/fx_probe/era_new.js: the claudesona idle on a dark
                                metal floor): frames 1-8
                    meadow      round one's meadow (tests/look/out/meadow/meadow_camera.blend, my robot walking in
                                daylight): frames 53-60
                    night       the neon street: frames 1-8
  --stage looks     composites the era pass over the saved frames (the compositor only):
                    - all 23 presets on the meadow (frame 60) and on the era probe (frame 8), sheets; the five the
                      WebGPU probe rendered beside its renders (work/fx_probe/new_1..5.png); the night presets
                    - parity: single looks against ref_era.py (the shader in numpy) on the meadow frame
                    - numeric: clean = the plain frame; c64 = the palette; mac = two levels on its 3 px grid;
                      websafe = 6 levels a channel; every look alone stays finite; an unknown option raises
                    - a crossfade keyed over frames 1-8 (bell1961 -> mac1984), the px snap at its middle
                    - the CRT persistence: a trail where the robot moves; restarting when the tube comes on
                    - the NaN clamp: a frame with NaN and Inf pixels through every look stays finite
                    - the registry: era_looks under a HUD overlay, glitch_bars and rgb_shift over it
                    - cost: build time, and per-frame time on the GPU and the CPU compositor
Run from the main checkout (the GPU slot):
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <worktree>/blender/tests/post_era/test_era_looks.py --stage sources
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <worktree>/blender/tests/post_era/test_era_looks.py --stage looks
"""
import json
import os
import shutil
import sys
import time
import traceback

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scenes as SC                                            # noqa: E402
import ref_era as REF                                          # noqa: E402

from eidoblend.look import frame_stats as FS                    # noqa: E402

A = SC.args()
STAGE = SC.arg(A, '--stage', 'looks')
OUT = os.path.join(SC.OUT, 'era')
SRC = os.path.join(OUT, 'src')
MEADOW = os.path.join(SC.WORKTREE, 'blender', 'tests', 'look', 'out', 'meadow', 'meadow_camera.blend')
SETS = {'era_probe': (1, 8), 'meadow': (53, 60), 'night': (1, 8)}
CLIP_END = {'era_probe': 100.0, 'meadow': 2000.0, 'night': 500.0}        # the source cameras' far planes
FAIL, REPORT = [], {}
os.makedirs(OUT, exist_ok=True)


def check(ok, what):
    print(f"[era] {'PASS' if ok else 'FAIL'}: {what}", flush=True)
    if not ok:
        FAIL.append(what)


# ------------------------------------------------------------------------------------------------- sources
def sources():
    from eidoblend.look import render_settings as RS
    for name, (f0, f1) in SETS.items():
        t0 = time.perf_counter()
        bpy.ops.wm.read_factory_settings(use_empty=True)
        if name == 'era_probe':
            sc, _h = SC.era_probe(frames=(1, 48))
        elif name == 'night':
            sc, _h = SC.neon_night(frames=(1, 48))
        else:
            bpy.ops.wm.open_mainfile(filepath=MEADOW, load_ui=False)
            sc = bpy.context.scene
            RS.apply_auto_enhance(sc, 'probe', exposure=0.5, motion_blur=False)
            sc.render.use_compositing = True
        view = (sc.view_settings.view_transform, sc.view_settings.look, sc.view_settings.exposure)
        paths = SC.render_sources(sc, os.path.join(SRC, name), range(f0, f1 + 1), name='src')
        meta = {'view': view, 'fps': sc.render.fps / sc.render.fps_base, 'frames': [f0, f1], 'paths': paths,
                'res': [sc.render.resolution_x, sc.render.resolution_y], 'clip_end': sc.camera.data.clip_end,
                'seconds': round(time.perf_counter() - t0, 1)}
        with open(os.path.join(SRC, name, 'meta.json'), 'w') as f:
            json.dump(meta, f, indent=1)
        print(f'[era] sources {name}: {meta}', flush=True)


# ------------------------------------------------------------------------------------------------- helpers
def load_meta(name):
    with open(os.path.join(SRC, name, 'meta.json')) as f:
        m = json.load(f)
    m.setdefault('clip_end', CLIP_END[name])
    return m


def post(name, effects='era_looks', opts=None, scene_name=None):
    from eidoblend.look.post import custom_effects as CFX
    from eidoblend.look.post import history as HI
    m = load_meta(name)
    sc = SC.post_scene(m['paths'], tuple(m['view']), fps=int(m['fps']), frames=(1, 400), res=tuple(m['res']),
                       name=scene_name or f'post_{name}', clip_end=m['clip_end'])
    hd = os.path.join(OUT, 'history', sc.name)
    shutil.rmtree(hd, ignore_errors=True)
    HI.set_history_dir(sc, hd)                     # the history writes go beside the test's outputs
    t0 = time.perf_counter()
    fx = CFX.apply_to(sc, effects, opts or {})
    REPORT.setdefault('build_s', {})[sc.name] = round(time.perf_counter() - t0, 2)
    return sc, fx, m


def exr(scene, frame):
    """The composited frame, scene-linear (before the view transform), top-down."""
    scene.frame_set(frame)
    with bpy.context.temp_override(scene=scene):
        bpy.ops.render.render(write_still=False, scene=scene.name)
    p = os.path.join(OUT, '_tmp.exr')
    s = scene.render.image_settings
    s.media_type, s.file_format, s.color_depth, s.exr_codec = 'IMAGE', 'OPEN_EXR', '32', 'ZIP'
    bpy.data.images['Render Result'].save_render(p, scene=scene)
    im = bpy.data.images.load(p, check_existing=False)
    a = np.array(im.pixels[:], np.float32).reshape(im.size[1], im.size[0], 4)[::-1]
    bpy.data.images.remove(im)
    return a


def load_exr(path):
    im = bpy.data.images.load(path, check_existing=False)
    a = np.array(im.pixels[:], np.float32).reshape(im.size[1], im.size[0], 4)[::-1]
    bpy.data.images.remove(im)
    return a


def diff(a, b):
    x, y = FS.read_rgb(a).astype(np.int16), FS.read_rgb(b).astype(np.int16)
    d = np.abs(x - y)
    return {'max': int(d.max()), 'mean': round(float(d.mean()), 3)}


def warm(sc, frames):
    """Composite `frames` in order (the history the CRT persistence reads)."""
    for f in frames:
        SC.render_png(sc, os.path.join(OUT, '_warm.png'), f)


# ------------------------------------------------------------------------------------------------- presets
def presets_on(name, frame, tag):
    from eidoblend.look.post import era_looks as EL
    sc, fx, m = post(name)
    U = fx.uniforms
    paths, labels = [], []
    plain = os.path.join(SRC, name, f'src_plain_{frame:04d}.png')
    EL.set_look(U, EL.ERA_LOOKS['crt'])
    warm(sc, range(m['frames'][0], frame))          # the frames before, in order: the CRT's persistence reads them
    timings = {}
    for preset, look in EL.ERA_LOOKS.items():
        EL.set_look(U, look)
        p = os.path.join(OUT, f'{tag}_{preset}.png')
        t0 = time.perf_counter()
        SC.render_png(sc, p, frame)
        timings[preset] = round(time.perf_counter() - t0, 3)
        paths.append(p)
        labels.append(preset + (f" {dict((k, v) for k, v in look.items())}" if look else ''))
        d = diff(p, plain)
        st = FS.frame_stats(FS.read_rgb(p))
        REPORT.setdefault(tag, {})[preset] = {'vs_plain': d, 'luma_median': st['luma_median'], 's': timings[preset]}
        if preset == 'clean':
            check(d['max'] <= 2, f'{tag}: clean (every weight 0) is the plain frame (max diff {d["max"]})')
        else:
            check(d['mean'] > 1.0, f'{tag}: {preset} changes the frame (mean diff {d["mean"]})')
    FS.sheet(paths[:12], os.path.join(OUT, f'{tag}_sheet_a.jpg'), cols=3, tile=640, labels=labels[:12])
    FS.sheet(paths[12:], os.path.join(OUT, f'{tag}_sheet_b.jpg'), cols=3, tile=640, labels=labels[12:])
    print(f'[era] {tag}: composite times (s) {timings}', flush=True)
    return sc, fx, m


# ------------------------------------------------------------------------------------------------- numeric
def numeric(sc, fx, frame):
    """In scene-linear light: the palette, the dither levels, the identity, finiteness."""
    from eidoblend.look.post import era_looks as EL
    U = fx.uniforms
    EL.set_look(U, {'c64': 1.0})
    a = exr(sc, frame)[..., :3]
    pal = np.array([np.array(p) ** 2 for p in EL.PAL])
    d = np.min(np.linalg.norm(a.reshape(-1, 1, 3) - pal[None], axis=2), axis=1)
    share = float((d < 1e-3).mean())
    check(share > 0.999, f'c64 alone: {share * 100:.2f}% of pixels are a C64 palette colour (squared, as WebGPU)')
    EL.set_look(U, {'mac': 1.0, 'px': 3})
    a = exr(sc, frame)[..., :3]
    lv = np.unique(np.round(a, 4))
    check(len(lv) <= 2 and all(min(abs(v), abs(v - 0.92)) < 1e-4 for v in lv.tolist()),
          f'mac alone: the levels are {[round(v, 4) for v in lv.tolist()[:6]]} (0 and 0.92: 1-bit)')
    blocks = a[:, :, 0][: (a.shape[0] // 3) * 3, : (a.shape[1] // 3) * 3]
    bl = blocks.reshape(blocks.shape[0] // 3, 3, blocks.shape[1] // 3, 3)
    uniform = float((bl.max(axis=(1, 3)) == bl.min(axis=(1, 3))).mean())
    check(uniform > 0.97, f'mac px 3: {uniform * 100:.1f}% of 3x3 blocks are one value (the pixel grid)')
    EL.set_look(U, {'websafe': 1.0})
    a = exr(sc, frame)[..., :3]
    q = np.sqrt(np.clip(a, 0, None)) * 5.0
    on_grid = float((np.abs(q - np.round(q)) < 2e-3).mean())
    check(on_grid > 0.999, f'websafe: {on_grid * 100:.2f}% of channel values on the 6-level grid (0, 51 .. 255)')
    for k in EL.KEYS:
        EL.set_look(U, {k: 1.0} if k != 'lift' else {'halftone': 1.0, 'lift': 2.0})
        a = exr(sc, frame)
        bad = int((~np.isfinite(a)).sum())
        check(bad == 0, f'{k} alone at weight 1: no NaN / Inf ({bad} bad values)')


def parity(sc, fx, name, frame):
    """Single looks against ref_era.py, the shader transcribed in numpy, on the same saved frame."""
    from eidoblend.look.post import era_looks as EL
    m = load_meta(name)
    src = load_exr(m['paths']['Combined'].replace(f"{m['frames'][0]:04d}", f'{frame:04d}'))[..., :3]
    atlas = np.array(bpy.data.images['eido_era_glyphs'].pixels[:], np.float32).reshape(56, 320, 4)[::-1, :, 0]
    t = frame / m['fps']
    cases = [('sepia', {'sepia': 1}), ('deco', {'deco': 1}), ('bw', {'bw': 1}), ('vector', {'vector': 1}),
             ('vfd', {'vfd': 1}), ('amber', {'amber': 1}), ('mac px3', {'mac': 1, 'px': 3}),
             ('websafe px2', {'websafe': 1, 'px': 2}), ('c64 + raster px4', {'c64': 1, 'raster': 1, 'px': 4}),
             # riso adds film grain (grain + riso x 0.6, an integer hash the reference leaves out): grain -0.6 cancels
             ('riso (its grain cancelled)', {'riso': 1, 'grain': -0.6}), ('kuwahara', {'kuwahara': 1}),
             ('feature', {'feature': 1}),
             ('ascii', {'ascii': 1}), ('scan + vignette', {'scan': 1, 'vignette': 1}),
             ('mix: bw .6 sepia .4 vignette .4', {'bw': 0.6, 'sepia': 0.4, 'vignette': 0.4}),
             ('voder1939 minus its hashes', {'deco': 0.85, 'sepia': 0.15, 'vignette': 0.8})]
    res = {}
    for label, w in cases:
        EL.set_look(fx.uniforms, w)
        got = exr(sc, frame)[..., :3].astype(np.float64)
        want = REF.era(src, w, t, atlas)
        err = np.abs(got - want)
        big = float((err.max(axis=2) > 0.02).mean())
        res[label] = {'mean': round(float(err.mean()), 5), 'max': round(float(err.max()), 4),
                      'over_0.02': round(big, 5)}
        # quantizing looks flip a level where the threshold lands within float error: allow a sliver of pixels
        check(err.mean() < 2e-3 and big < 0.004,
              f'parity {label}: mean |blender - numpy| {err.mean():.2e}, {big * 100:.3f}% of pixels off by > 0.02')
    REPORT['parity'] = res


# ------------------------------------------------------------------------------------------------- persistence
def persistence(name='meadow'):
    """The CRT's persistence (three's AfterImage of the input): a trail where the robot moves, none on still
    ground; restarting clean on the first frame the tube is on."""
    from eidoblend.look.post import era_looks as EL
    sc, fx, m = post(name, scene_name='post_persist')
    U = fx.uniforms
    f0, f1 = m['frames']
    # the tube off for f0..f0+3, on from f0+4 (keyed CONSTANT): the first on-frame starts clean
    on_at = f0 + 4
    EL.set_look(U, {}, frame=f0)
    EL.set_look(U, {'phosphor': 1.0}, frame=on_at)
    ad = sc.compositing_node_group.animation_data
    from eidoblend.look.post.history import _fcurves
    for fc in _fcurves(ad.action, sc.compositing_node_group):
        if '.inputs[' in fc.data_path:                 # the weights (not the history taps' offset ramps)
            for k in fc.keyframe_points:
                k.interpolation = 'CONSTANT'
    outs = {}
    for f in range(f0, f1 + 1):
        outs[f] = exr(sc, f)
    sc2, fx2, _m = post(name, opts={'era_looks': {'persist_frames': 0}}, scene_name='post_nopersist')
    EL.set_look(fx2.uniforms, {'phosphor': 1.0})
    ref_first = exr(sc2, on_at)
    ref_last = exr(sc2, f1)
    d_first = float(np.abs(outs[on_at][..., :3] - ref_first[..., :3]).max())
    check(d_first < 1e-4, f'persistence restarts when the tube comes on: frame {on_at} = no persistence '
                          f'(max diff {d_first:.2e})')
    dl = np.abs(outs[f1][..., :3] - ref_last[..., :3]).max(axis=2)
    moved = float((dl > 0.01).mean())
    REPORT['persistence'] = {'first_on_maxdiff': d_first, 'trail_share_last': round(moved, 4),
                             'K': len(fx.histories['era_looks'][0].taps())}
    check(0.0005 < moved < 0.9, f'persistence at frame {f1}: {moved * 100:.2f}% of pixels hold a trail (where '
                                f'the picture moved and was brighter a moment ago), the rest unchanged')
    p_on, p_off = os.path.join(OUT, 'persist_trail.png'), os.path.join(OUT, 'persist_none.png')
    SC.render_png(sc, p_on, f1)
    SC.render_png(sc2, p_off, f1)
    heat = np.clip(dl / max(dl.max(), 1e-6), 0, 1)
    from PIL import Image
    Image.fromarray((heat * 255).astype(np.uint8)).save(os.path.join(OUT, 'persist_diff.png'))
    FS.sheet([p_on, p_off, os.path.join(OUT, 'persist_diff.png')], os.path.join(OUT, 'persist_sheet.jpg'), cols=3,
             tile=640, labels=[f'crt, persistence, frame {f1}', 'crt, persist_frames=0', '|difference| (scaled)'])


# ------------------------------------------------------------------------------------------------- the NaN clamp
def hazard(name='meadow', frame=60):
    """A frame with NaN and +Inf pixels: every look stays finite (the WebGPU pass skipped looks that were off; here
    every look is evaluated and mixed by weight, and 0 x Inf = NaN would spread through the blur pyramids)."""
    from eidoblend.look.post import chain
    from eidoblend.look.post import era_looks as EL
    m = load_meta(name)
    src = load_exr(m['paths']['Combined'].replace(f"{m['frames'][0]:04d}", f'{frame:04d}'))
    bad = src.copy()
    H, W = bad.shape[:2]
    bad[H // 3, W // 3, :3] = np.nan
    bad[H // 2, W // 2, :3] = np.inf
    bad[2 * H // 3, W // 4, 0] = np.inf
    hz = os.path.join(OUT, 'hazard')
    os.makedirs(hz, exist_ok=True)
    im = bpy.data.images.new('hazard_src', W, H, float_buffer=True, alpha=True)
    im.pixels.foreach_set(bad[::-1].astype(np.float32).ravel())
    im.filepath_raw = os.path.join(hz, 'nan_0001.exr')
    im.file_format = 'OPEN_EXR'
    im.save()
    back = load_exr(os.path.join(hz, 'nan_0001.exr'))
    n_bad_in = int((~np.isfinite(back[..., :3])).sum())
    check(n_bad_in >= 7, f'the hazard frame carries {n_bad_in} non-finite values (NaN and Inf)')
    sc, fx, _m = post(name, scene_name='post_hazard')
    chain.use_saved_frames(sc, os.path.join(hz, 'nan_0001.exr'), frame_start=1)
    worst = {}
    for k in ['clean'] + [k for k in EL.KEYS if k != 'lift']:
        EL.set_look(fx.uniforms, {} if k == 'clean' else {k: 1.0})
        a = exr(sc, 1)[..., :3]
        nb = int((~np.isfinite(a)).sum())
        worst[k] = nb
    REPORT['hazard'] = worst
    check(all(v == 0 for v in worst.values()), f'NaN / Inf in the input: every look alone and none at all give a '
                                               f'finite frame (non-finite counts {worst})')
    EL.set_look(fx.uniforms, EL.ERA_LOOKS['candle_film'])
    SC.render_png(sc, os.path.join(OUT, 'hazard_candle_film.png'), 1)


# ------------------------------------------------------------------------------------------------- the registry
def registry_chain(name='era_probe', frame=8):
    """era_looks 'under' a HUD overlay, glitch_bars and rgb_shift 'over' it: the HUD stays crisp under the era look and
    is split by the signal effects (custom_effects_deno.js's layering)."""
    from eidoblend.look.post import chain
    sc, fx, m = post(name, effects='era_looks,glitch_bars,rgb_shift',
                     opts={'era_looks': {'layer': 'under', 'c64': 1, 'raster': 1, 'px': 4},
                           'glitch_bars': {'barFreq': 22, 'shift': 0.03, 'opacity': 0.85},
                           'rgb_shift': {'amount': 0.004}}, scene_name='post_chain')
    W, H = m['res']
    hud = bpy.data.images.new('hud', W, H, alpha=True, float_buffer=True)
    px = np.zeros((H, W, 4), np.float32)
    px[int(H * 0.82):int(H * 0.92), int(W * 0.06):int(W * 0.5)] = (0.9, 0.9, 0.9, 1.0)    # a lower third
    px[int(H * 0.84):int(H * 0.90), int(W * 0.08):int(W * 0.12)] = (0.02, 0.6, 0.7, 1.0)  # a teal badge on it
    hud.pixels.foreach_set(px[::-1].ravel())
    hn = sc.compositing_node_group.nodes.new('CompositorNodeImage')
    hn.image = hud
    chain.set_overlay(sc, hn)
    st = [(s, n) for s, n, _x in chain.stages(sc)]
    check(st == [('under', 'era_looks'), ('overlay', 'overlay'), ('over', 'glitch_bars'), ('over', 'rgb_shift')],
          f'chain order: {st}')
    check(set(fx.uniforms) == {'era_looks', 'glitch_bars', 'rgb_shift'} and 'c64' in fx.uniforms['era_looks'],
          'three effects: uniforms keyed by effect name')
    p = os.path.join(OUT, 'chain_era_under_hud_signal_over.png')
    SC.render_png(sc, p, frame)
    # the signal effects off for the numbers: the HUD exactly as drawn (era under it), the film C64-quantized
    U = fx.uniforms
    U['glitch_bars']['opacity'].default_value = 0.0
    U['rgb_shift']['amount'].default_value = 0.0
    a = exr(sc, frame)
    y0, y1, x0, x1 = int(H * 0.845), int(H * 0.895), int(W * 0.085), int(W * 0.115)
    teal = a[y0:y1, x0:x1, :3].reshape(-1, 3).mean(0)
    check(np.abs(teal - np.array([0.02, 0.6, 0.7])).max() < 0.01, f'era_looks under the overlay: the HUD badge is '
                                                                  f'its own teal {np.round(teal, 3).tolist()}')
    # the film above the HUD against the numpy reference of the same look on the same saved frame. (Not a palette
    # count: the bars mix into the film over the dark mask's soft edge, 0.015 < lum < 0.07, and overlapping bars take
    # a per-channel max, so a quarter of this frame is off the palette in the reference too: 74.0%, as here.)
    src = load_exr(m['paths']['Combined'].replace(f"{m['frames'][0]:04d}", f'{frame:04d}'))[..., :3]
    want = REF.era(src, {'c64': 1, 'raster': 1, 'px': 4}, frame / m['fps'])
    film = int(H * 0.8)
    err = np.abs(a[:film, :, :3].astype(np.float64) - want[:film])
    off = float((err.max(axis=2) > 0.02).mean())
    check(float(err.mean()) < 1e-4 and off < 1e-3,
          f'era_looks under the overlay: the film above the HUD is the c64 look exactly (mean |blender - numpy| '
          f'{float(err.mean()):.1e}, {off * 100:.3f}% of pixels off by > 0.02)')
    U['glitch_bars']['opacity'].default_value = 0.85
    U['rgb_shift']['amount'].default_value = 0.004
    FS.sheet([os.path.join(SRC, name, f'src_plain_{frame:04d}.png'), p], os.path.join(OUT, 'chain_sheet.jpg'),
             cols=2, tile=800, labels=['plain', "era_looks (c64_1982) under a HUD; glitch_bars + rgb_shift over it"])


# ------------------------------------------------------------------------------------------------- cost
def cost(name='era_probe', frame=8):
    """Per-frame composite time of the whole era pass, GPU and CPU compositor (every look is evaluated whatever the
    weights, so one preset's cost is every preset's)."""
    from eidoblend.look.post import era_looks as EL
    sc, fx, m = post(name, scene_name='post_cost')
    EL.set_look(fx.uniforms, EL.ERA_LOOKS['crt'])
    out = {}
    plain_sc = SC.post_scene(m['paths'], tuple(m['view']), fps=int(m['fps']), frames=(1, 400),
                             res=tuple(m['res']), name='post_plain_cost', clip_end=m['clip_end'])
    for dev in ('GPU', 'CPU'):
        for s in (sc, plain_sc):
            s.render.compositor_device = dev
        times, base = [], []
        last = m['frames'][1] if dev == 'GPU' else m['frames'][0] + 2      # the CPU compositor: three frames
        for i, f in enumerate(range(m['frames'][0], last + 1)):
            t0 = time.perf_counter()
            SC.render_png(sc, os.path.join(OUT, '_warm.png'), f)
            times.append(time.perf_counter() - t0)
            t0 = time.perf_counter()
            SC.render_png(plain_sc, os.path.join(OUT, '_warm.png'), f)
            base.append(time.perf_counter() - t0)
        out[dev] = {'first_s': round(times[0], 2), 'median_s': round(float(np.median(times[1:])), 3),
                    'plain_median_s': round(float(np.median(base[1:])), 3)}
    REPORT['cost'] = out
    REPORT['cost']['res'] = m['res']
    print(f'[era] cost {out}', flush=True)


# ------------------------------------------------------------------------------------------------- looks
def looks():
    from eidoblend.look.post import custom_effects as CFX
    t_all = time.perf_counter()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    m = load_meta('era_probe')
    sc0 = SC.post_scene(m['paths'], tuple(m['view']), fps=int(m['fps']), frames=(1, 48), res=tuple(m['res']),
                        name='opts', clip_end=m['clip_end'])
    try:
        CFX.apply_to(sc0, 'era_looks', {'era_looks': {'sepiaa': 1.0}})
        check(False, "era_looks: an unknown option 'sepiaa' raises")
    except KeyError as e:
        check('sepia' in str(e), f"era_looks: an unknown option raises, naming the real ones ({str(e)[:90]}...)")
    # the meadow: every preset, the numbers, the parity
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc, fx, _m = presets_on('meadow', 60, 'meadow')
    section('numeric', numeric, sc, fx, 60)
    section('parity', parity, sc, fx, 'meadow', 60)
    section('persistence', persistence, 'meadow')
    section('hazard', hazard, 'meadow', 60)
    section('probe', probe_part)
    section('night', night_part)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    section('registry_chain', registry_chain)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    section('cost', cost)
    REPORT['total_s'] = round(time.perf_counter() - t_all, 1)
    REPORT['history_mb'] = round(sum(os.path.getsize(os.path.join(dp, f)) for dp, _d, fs in
                                     os.walk(os.path.join(OUT, 'history')) for f in fs) / 1e6, 1)


def section(name, f, *a):
    """One part of the looks stage: an exception fails it (and is reported) without losing the rest; the report is
    written after each part."""
    try:
        f(*a)
    except Exception:                                  # noqa: BLE001
        traceback.print_exc()
        FAIL.append(f'{name}: exception: ' + traceback.format_exc().splitlines()[-1])
    REPORT['fail'] = FAIL
    with open(os.path.join(OUT, 'report_looks.json'), 'w') as fh:
        json.dump(REPORT, fh, indent=1, default=str)


def probe_part():
    from eidoblend.look.post import era_looks as EL
    # the era probe: every preset, and the WebGPU five side by side
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc, fx, _m = presets_on('era_probe', 8, 'probe')
    pairs, labs = [], []
    for i, preset in enumerate(['c64_1982', 'poster_night', 'watercolor', 'crt', 'printer1961'], 1):
        ref = os.path.join(SC.REF, f'new_{i}.png')
        if os.path.exists(ref):
            pairs += [ref, os.path.join(OUT, f'probe_{preset}.png')]
            labs += [f'WebGPU {preset} (work/fx_probe/new_{i}.png)', f'Blender {preset}']
    if pairs:
        FS.sheet(pairs, os.path.join(OUT, 'probe_vs_webgpu.jpg'), cols=2, tile=800, labels=labs)
    # a crossfade keyed over frames 1-8 (bell1961 -> mac1984): its ends, either side of its middle
    U = fx.uniforms
    EL.crossfade(U, EL.ERA_LOOKS['bell1961'], EL.ERA_LOOKS['mac1984'], 1, 8)
    xp = []
    for f in (1, 4, 5, 8):
        p = os.path.join(OUT, f'probe_crossfade_f{f}.png')
        SC.render_png(sc, p, f)
        xp.append(p)
    vals = {}
    for f in (1, 4, 5, 8):
        sc.frame_set(f)
        vals[f] = {k: round(U[k].default_value, 3) for k in ('bw', 'mac', 'px', 'grain')}
    REPORT['crossfade'] = vals
    check(vals[4]['px'] == 1.0 and vals[5]['px'] == 3.0 and vals[1]['bw'] == 1.0 and vals[8]['mac'] == 1.0
          and 0.0 < vals[4]['mac'] < 0.5 < vals[5]['mac'] < 1.0,
          f'crossfade keyed: bw 1 at 1, mac 1 at 8, px 1 -> 3 between 4 and 5, smoothstepped ({vals})')
    FS.sheet(xp, os.path.join(OUT, 'probe_crossfade_sheet.jpg'), cols=4, tile=480,
             labels=['f1 bell1961', 'f4 (s 0.43)', 'f5 (s 0.57: px snaps)', 'f8 mac1984'])


def night_part():
    from eidoblend.look.post import era_looks as EL
    # the night presets on the neon street
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc, fx, _m = post('night')
    np_paths = []
    for preset in ('clean', 'poster_night', 'watercolor_night', 'candle_film', 'crt', 'storybook'):
        EL.set_look(fx.uniforms, EL.ERA_LOOKS[preset])
        p = os.path.join(OUT, f'night_{preset}.png')
        SC.render_png(sc, p, 8)
        np_paths.append(p)
    FS.sheet(np_paths, os.path.join(OUT, 'night_sheet.jpg'), cols=3, tile=640,
             labels=['night clean', 'poster_night (lift 1.6)', 'watercolor_night (lift 1.1)', 'candle_film', 'crt',
                     'storybook'])


if not SC.already_done(OUT, STAGE, os.path.abspath(__file__)):
    try:
        if STAGE == 'sources':
            sources()
        else:
            looks()
    except Exception:
        traceback.print_exc()
        FAIL.append('exception: ' + traceback.format_exc().splitlines()[-1])
    REPORT['fail'] = FAIL
    with open(os.path.join(OUT, f'report_{STAGE}.json'), 'w') as f:
        json.dump(REPORT, f, indent=1, default=str)
    SC.mark_done(OUT, STAGE)
    print(f"[era] {STAGE}: {'FAIL ' + str(len(FAIL)) if FAIL else 'PASS'}", flush=True)

"""tests/post_era/test_after_image.py: three's afterImage() (effects_tsl/after_image.js) as a compositor pass whose
previous frame is its own trail, written to disk every frame and read back on the next (look/post/history.py).

  --stage sources   renders the mover (an emissive sphere and a lit cube crossing a dark wall) frames 1-24 once
                    (EEVEE, Combined as EXR)
  --stage post      composites after_image over the saved frames in order and checks every frame against the
                    feedback computed in numpy from the plain frames (trail = max(new, old x damp, old masked below
                    0.1)); opacity 0.5; damp keyed down mid-shot; a cut restarts the trail; the trail's disk and time
                    cost per frame; a sheet of the trail beside the plain frames.
Run from the main checkout (the GPU slot):
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <worktree>/blender/tests/post_era/test_after_image.py --stage sources
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <worktree>/blender/tests/post_era/test_after_image.py --stage post
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

from eidoblend.look import frame_stats as FS                    # noqa: E402

A = SC.args()
STAGE = SC.arg(A, '--stage', 'post')
OUT = os.path.join(SC.OUT, 'after_image')
SRC = os.path.join(OUT, 'src')
F0, F1 = 1, 24
FAIL, REPORT = [], {}
os.makedirs(OUT, exist_ok=True)


def check(ok, what):
    print(f"[after_image] {'PASS' if ok else 'FAIL'}: {what}", flush=True)
    if not ok:
        FAIL.append(what)


def sources():
    shutil.rmtree(SRC, ignore_errors=True)
    sc = SC.mover(frames=(F0, F1))
    paths = SC.render_sources(sc, SRC, range(F0, F1 + 1), name='src', passes=())
    meta = {'view': (sc.view_settings.view_transform, sc.view_settings.look, sc.view_settings.exposure),
            'fps': sc.render.fps / sc.render.fps_base, 'frames': [F0, F1], 'paths': paths,
            'res': [sc.render.resolution_x, sc.render.resolution_y]}
    with open(os.path.join(SRC, 'meta.json'), 'w') as f:
        json.dump(meta, f, indent=1)


def load_meta():
    with open(os.path.join(SRC, 'meta.json')) as f:
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


def expected(srcs, damp_at, opacity=1.0, cuts=()):
    """three's AfterImageNode, frame by frame: comp = max(new, old * damp * (old > 0.1)); shown = mix(new, comp,
    opacity) (rgb; the frame's own alpha). A cut (and the first frame) starts from an empty buffer."""
    out, old = {}, None
    for f in sorted(srcs):
        new = srcs[f][..., :3].astype(np.float64)
        if old is None or f in cuts:
            comp = new.copy()
        else:
            comp = np.maximum(new, old * damp_at(f) * (old > 0.1))
        out[f] = new + (comp - new) * opacity
        old = comp.astype(np.float16).astype(np.float64)       # the trail is stored as half float on disk
    return out


def post():
    from eidoblend.look.post import custom_effects as CFX
    from eidoblend.look.post import history as HI
    m = load_meta()
    srcs = {f: load_exr(m['paths']['Combined'].replace(f'{F0:04d}', f'{f:04d}')) for f in range(F0, F1 + 1)}
    sc = SC.post_scene(m['paths'], tuple(m['view']), fps=int(m['fps']), frames=(F0, F1), res=tuple(m['res']),
                       name='post_after')
    hd = os.path.join(OUT, 'history')
    shutil.rmtree(hd, ignore_errors=True)
    HI.set_history_dir(sc, hd)
    e = CFX.apply_to(sc, 'after_image', {'after_image': {'damp': 0.96, 'opacity': 1.0}})
    U = e.uniforms
    check(abs(U['damp'].default_value - 0.96) < 1e-6 and abs(U['opacity'].default_value - 1.0) < 1e-6,
          'options damp and opacity reach the pass (one effect: its uniforms at the top level)')
    plain_sc = SC.post_scene(m['paths'], tuple(m['view']), fps=int(m['fps']), frames=(F0, F1), res=tuple(m['res']),
                             name='post_plain')
    # 1. damp 0.96, opacity 1, frames in order
    want = expected(srcs, lambda f: 0.96)
    errs, t_fx, t_plain = [], [], []
    outs = {}
    for f in range(F0, F1 + 1):
        t0 = time.perf_counter()
        outs[f] = exr(sc, f)
        t_fx.append(time.perf_counter() - t0)
        t0 = time.perf_counter()
        exr(plain_sc, f)
        t_plain.append(time.perf_counter() - t0)
        errs.append(float(np.abs(outs[f][..., :3] - want[f]).max() / max(1.0, float(np.abs(want[f]).max()))))
    check(max(errs) < 2e-3, f'every frame = the numpy feedback (worst relative error {max(errs):.1e}, frames '
                            f'{F0}-{F1})')
    trail_px = float((np.abs(outs[F1][..., :3] - srcs[F1][..., :3]).max(axis=2) > 0.05).mean())
    check(trail_px > 0.005, f'frame {F1}: {trail_px * 100:.2f}% of pixels hold the trail of the sphere and cube')
    files = e.histories['after_image'][0].files()
    REPORT['cost'] = {'composite_median_s': round(float(np.median(t_fx[1:])), 3),
                      'plain_median_s': round(float(np.median(t_plain[1:])), 3),
                      'trail_mb_per_frame': round(sum(os.path.getsize(p) for p in files) / len(files) / 1e6, 2),
                      'res': m['res']}
    paths, labels = [], []
    for f in (6, 12, 18, 24):
        p = os.path.join(OUT, f'trail_f{f:02d}.png')
        SC.render_png(sc, p, f)
        paths += [os.path.join(SRC, f'src_plain_{f:04d}.png'), p]
        labels += [f'plain, frame {f}', f'after_image damp 0.96, frame {f}']
    FS.sheet(paths, os.path.join(OUT, 'after_image_sheet.jpg'), cols=2, tile=640, labels=labels)
    # 2. opacity 0.5 (the trail half mixed in)
    shutil.rmtree(hd, ignore_errors=True)
    U['opacity'].default_value = 0.5
    want = expected(srcs, lambda f: 0.96, opacity=0.5)
    errs = [float(np.abs(exr(sc, f)[..., :3] - want[f]).max() / max(1.0, float(np.abs(want[f]).max())))
            for f in range(F0, F1 + 1)]
    check(max(errs) < 2e-3, f'opacity 0.5: every frame = mix(frame, trail, 0.5) (worst {max(errs):.1e})')
    U['opacity'].default_value = 1.0
    # 3. damp keyed down to 0.5 from frame 12 (a shorter trail; keyed, so it lives in the .blend)
    shutil.rmtree(hd, ignore_errors=True)
    e.key('after_image', 'damp', 11, 0.96)
    e.key('after_image', 'damp', 12, 0.5)
    from eidoblend.look.post.history import _fcurves
    for fc in _fcurves(sc.compositing_node_group.animation_data.action, sc.compositing_node_group):
        for k in fc.keyframe_points:
            if 'inputs' in fc.data_path:
                k.interpolation = 'CONSTANT'
    want = expected(srcs, lambda f: 0.96 if f < 12 else 0.5)
    errs = [float(np.abs(exr(sc, f)[..., :3] - want[f]).max() / max(1.0, float(np.abs(want[f]).max())))
            for f in range(F0, F1 + 1)]
    check(max(errs) < 2e-3, f'damp keyed 0.96 -> 0.5 at frame 12: every frame matches (worst {max(errs):.1e})')
    p = os.path.join(OUT, 'trail_damp05_f24.png')
    SC.render_png(sc, p, F1)
    # 4. a cut at 16: the trail restarts there
    shutil.rmtree(hd, ignore_errors=True)
    U.cut(16)
    want = expected(srcs, lambda f: 0.96 if f < 12 else 0.5, cuts=(16,))
    errs, at_cut = [], None
    for f in range(F0, F1 + 1):
        o = exr(sc, f)
        errs.append(float(np.abs(o[..., :3] - want[f]).max() / max(1.0, float(np.abs(want[f]).max()))))
        if f == 16:
            at_cut = float(np.abs(o[..., :3] - srcs[16][..., :3]).max())
    check(max(errs) < 2e-3 and at_cut < 1e-3, f'cut at 16: the trail restarts (frame 16 = the plain frame, max diff '
                                              f'{at_cut:.1e}; every frame matches, worst {max(errs):.1e})')
    FS.sheet([os.path.join(OUT, 'trail_f24.png'), p], os.path.join(OUT, 'after_image_damp_sheet.jpg'), cols=2,
             tile=640, labels=['damp 0.96, frame 24', 'damp keyed to 0.5 from frame 12, frame 24'])
    REPORT['history_files'] = len(os.listdir(os.path.join(hd, 'after_image_trail')))


if not SC.already_done(OUT, STAGE, os.path.abspath(__file__)):
    try:
        if STAGE == 'sources':
            sources()
        else:
            post()
    except Exception:
        traceback.print_exc()
        FAIL.append('exception: ' + traceback.format_exc().splitlines()[-1])
    REPORT['fail'] = FAIL
    with open(os.path.join(OUT, f'report_{STAGE}.json'), 'w') as f:
        json.dump(REPORT, f, indent=1, default=str)
    SC.mark_done(OUT, STAGE)
    print(f"[after_image] {STAGE}: {'FAIL ' + str(len(FAIL)) if FAIL else 'PASS'}", flush=True)

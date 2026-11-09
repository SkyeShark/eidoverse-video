"""tests/post_era/test_film_render.py: the temporal passes rendered the way a film is rendered, not frame by frame.

The other tests composite one still at a time (frame_set + render). A film is an animation render: the harness's
output.render_video calls bpy.ops.render.render(animation=True) in the session that built the scene, and a saved
.blend is rendered again from the command line (blender -b film.blend -S scene -a) by a Blender with no Python
session behind it (factory settings: no add-on, no handler, Python drivers not trusted). Both must give the frames
the stills give, reading the earlier frames back from disk (look/post/history.py). Checked here, every frame:

  - after_image (the mover, 24 frames, damp 0.96): the animation render in this session and the saved .blend rendered
    by a fresh Blender, each frame against three's feedback computed in numpy; with history.auto_prune keeping only
    the frame each one needs, the disk holds two frames at the end and every frame still matches;
    a frame rendered alone with no history on disk is the plain frame (the pass starts clean, no stale or missing-file
    colour)
  - aeropittura storm (THE HOLE, 12 frames: the echoes read 1-4 gaps back): the animation render and the fresh
    Blender's against stills composited one after another in order; a frame rendered alone with no history equals
    the same frame after a cut (the echoes fall back to the current frame)
  - era_looks crt (the meadow, frames 53-60: the CRT persistence reads K = 7 frames back): the same

Run after the sources of test_after_image.py, test_aeropittura.py and test_era_looks.py, from the main checkout:
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <worktree>/blender/tests/post_era/test_film_render.py
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import time
import traceback

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scenes as SC                                            # noqa: E402

OUT = os.path.join(SC.OUT, 'film_render')
FAIL, REPORT = [], {}
os.makedirs(OUT, exist_ok=True)


def check(ok, what):
    print(f"[film] {'PASS' if ok else 'FAIL'}: {what}", flush=True)
    if not ok:
        FAIL.append(what)


def load_meta(sub, name=None):
    p = os.path.join(SC.OUT, sub, 'src', *(name,) if name else (), 'meta.json')
    with open(p) as f:
        return json.load(f)


def load_exr(path):
    im = bpy.data.images.load(path, check_existing=False)
    a = np.array(im.pixels[:], np.float32).reshape(im.size[1], im.size[0], 4)[::-1]
    bpy.data.images.remove(im)
    return a


def src_frame(m, f):
    return load_exr(m['paths']['Combined'].replace(f"{m['frames'][0]:04d}", f'{f:04d}'))


def still(scene, frame):
    """One composited frame as a still (the other tests' way), scene-linear, top-down."""
    scene.frame_set(frame)
    with bpy.context.temp_override(scene=scene):
        bpy.ops.render.render(write_still=False, scene=scene.name)
    p = os.path.join(OUT, '_still.exr')
    s = scene.render.image_settings
    s.media_type, s.file_format, s.color_depth, s.exr_codec = 'IMAGE', 'OPEN_EXR', '32', 'ZIP'
    bpy.data.images['Render Result'].save_render(p, scene=scene)
    return load_exr(p)


def set_output(scene, folder):
    """The animation's own output: 32-bit RGBA EXR frames <folder>/f_####.exr (scene-linear, the view's input)."""
    shutil.rmtree(folder, ignore_errors=True)
    os.makedirs(folder, exist_ok=True)
    s = scene.render.image_settings
    s.media_type, s.file_format, s.color_depth, s.exr_codec, s.color_mode = 'IMAGE', 'OPEN_EXR', '32', 'ZIP', 'RGBA'
    scene.render.filepath = os.path.join(folder, 'f_')
    scene.render.use_file_extension = True


def animation_here(scene, folder):
    """bpy.ops.render.render(animation=True) in this session, as harness/output.render_video renders a film."""
    set_output(scene, folder)
    t0 = time.perf_counter()
    with bpy.context.temp_override(scene=scene):
        bpy.ops.render.render(animation=True, scene=scene.name)
    return time.perf_counter() - t0


def animation_fresh(scene, folder, blend):
    """Save the .blend and render it with a fresh Blender from the command line: blender -b film.blend -S scene -a."""
    set_output(scene, folder)
    bpy.ops.wm.save_as_mainfile(filepath=blend, copy=True)
    cmd = [bpy.app.binary_path, '--background', '--factory-startup', blend, '--scene', scene.name, '--render-anim']
    t0 = time.perf_counter()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800, env=dict(os.environ))
    log = os.path.join(OUT, os.path.basename(blend) + '.log')
    with open(log, 'w', encoding='utf-8') as fh:
        fh.write(r.stdout + '\n----- stderr\n' + r.stderr)
    bad = [ln for ln in (r.stdout + r.stderr).splitlines() if 'Error' in ln or 'Traceback' in ln]
    return time.perf_counter() - t0, r.returncode, bad[:5]


def frames_in(folder, f0, f1):
    out = {}
    for f in range(f0, f1 + 1):
        p = os.path.join(folder, f'f_{f:04d}.exr')
        out[f] = load_exr(p) if os.path.exists(p) else None
    return out


def rel_err(a, b):
    return float(np.abs(a[..., :3].astype(np.float64) - b[..., :3]).max() / max(1.0, float(np.abs(b[..., :3]).max())))


def history_clear(scene):
    from eidoblend.look.post import history as HI
    d = HI.history_dir(scene)
    shutil.rmtree(d, ignore_errors=True)
    return d


# ------------------------------------------------------------------------------------------------- after_image
def expected_after_image(srcs, damp, cuts=()):
    """three's AfterImageNode, frame by frame (as test_after_image.py): comp = max(new, old damp (old > 0.1)); the
    first frame and a cut start from an empty buffer; the trail is stored as half float."""
    out, old = {}, None
    for f in sorted(srcs):
        new = srcs[f][..., :3].astype(np.float64)
        comp = new.copy() if (old is None or f in cuts) else np.maximum(new, old * damp * (old > 0.1))
        out[f] = comp
        old = comp.astype(np.float16).astype(np.float64)
    return out


def after_image_part():
    from eidoblend.look.post import custom_effects as CFX
    from eidoblend.look.post import history as HI
    m = load_meta('after_image')
    f0, f1 = m['frames']
    srcs = {f: src_frame(m, f) for f in range(f0, f1 + 1)}
    want = expected_after_image(srcs, 0.96)
    sc = SC.post_scene(m['paths'], tuple(m['view']), fps=int(m['fps']), frames=(f0, f1), res=tuple(m['res']),
                       name='film_after')
    HI.set_history_dir(sc, os.path.join(OUT, 'history', sc.name))
    history_clear(sc)
    e = CFX.apply_to(sc, 'after_image', {'after_image': {'damp': 0.96, 'opacity': 1.0}})
    HI.auto_prune(sc, {'after_image_trail': 1})                       # keep only the frame the next one reads
    t = animation_here(sc, os.path.join(OUT, 'after_here'))
    got = frames_in(os.path.join(OUT, 'after_here'), f0, f1)
    missing = [f for f, a in got.items() if a is None]
    errs = {f: rel_err(a, want[f]) for f, a in got.items() if a is not None}
    worst = max(errs.values()) if errs else 1.0
    left = len(e.histories['after_image'][0].files())
    REPORT['after_image_here'] = {'seconds': round(t, 1), 'worst_rel': worst, 'missing': missing, 'files_left': left}
    check(not missing and worst < 2e-3, f'after_image, animation render in this session: every frame {f0}-{f1} = the '
                                        f'numpy feedback (worst relative error {worst:.1e}; missing {missing})')
    check(left <= 2, f'auto_prune kept {left} trail file(s) on disk at the end (each frame needs only the one before)')
    bpy.app.handlers.render_post.clear()                              # the fresh Blender has no handler either
    history_clear(sc)
    t, rc, bad = animation_fresh(sc, os.path.join(OUT, 'after_fresh'), os.path.join(OUT, 'film_after.blend'))
    got = frames_in(os.path.join(OUT, 'after_fresh'), f0, f1)
    missing = [f for f, a in got.items() if a is None]
    errs = {f: rel_err(a, want[f]) for f, a in got.items() if a is not None}
    worst = max(errs.values()) if errs else 1.0
    REPORT['after_image_fresh'] = {'seconds': round(t, 1), 'returncode': rc, 'errors': bad, 'worst_rel': worst,
                                   'missing': missing}
    check(rc == 0 and not missing and worst < 2e-3,
          f'after_image, the saved .blend rendered by a fresh Blender (-b -S -a): every frame = the numpy feedback '
          f'(worst {worst:.1e}; missing {missing}; exit {rc}; errors {bad})')
    # one frame alone, nothing on disk: the trail starts from the frame itself (no stale, no missing-file colour)
    history_clear(sc)
    one = still(sc, 10)
    d = float(np.abs(one[..., :3] - srcs[10][..., :3]).max())
    REPORT['after_image_alone_f10'] = d
    check(d < 1e-3, f'after_image, frame 10 rendered alone with no history on disk = the plain frame (max diff {d:.1e})')
    history_clear(sc)


# ------------------------------------------------------------------------------------------------- the stills reference
def stills_in_order(sc, f0, f1):
    history_clear(sc)
    out = {f: still(sc, f) for f in range(f0, f1 + 1)}
    return out


def compare(name, got, ref, tol):
    missing = [f for f, a in got.items() if a is None]
    errs = {f: rel_err(a, ref[f]) for f, a in got.items() if a is not None}
    worst = max(errs.values()) if errs else 1.0
    return worst, missing, errs


def temporal_part(tag, sc, f0, f1, alone_frame, alone_ref_fn, tol=2e-3):
    """sc: a post scene with its temporal pass applied. Stills in order are the reference; the animation render here
    and the fresh Blender's must give the same frames."""
    t0 = time.perf_counter()
    ref = stills_in_order(sc, f0, f1)
    t_stills = time.perf_counter() - t0
    history_clear(sc)
    t_here = animation_here(sc, os.path.join(OUT, f'{tag}_here'))
    worst, missing, _e = compare(tag, frames_in(os.path.join(OUT, f'{tag}_here'), f0, f1), ref, tol)
    check(not missing and worst < tol, f'{tag}, animation render in this session: every frame {f0}-{f1} = the stills '
                                       f'composited in order (worst relative difference {worst:.1e}; missing {missing})')
    rep = {'stills_s': round(t_stills, 1), 'here_s': round(t_here, 1), 'here_worst': worst}
    history_clear(sc)
    t_f, rc, bad = animation_fresh(sc, os.path.join(OUT, f'{tag}_fresh'), os.path.join(OUT, f'film_{tag}.blend'))
    worst, missing, _e = compare(tag, frames_in(os.path.join(OUT, f'{tag}_fresh'), f0, f1), ref, tol)
    check(rc == 0 and not missing and worst < tol,
          f'{tag}, the saved .blend rendered by a fresh Blender: every frame = the stills (worst {worst:.1e}; '
          f'missing {missing}; exit {rc}; errors {bad})')
    rep.update({'fresh_s': round(t_f, 1), 'fresh_rc': rc, 'fresh_worst': worst, 'fresh_errors': bad})
    # one frame alone with nothing on disk
    history_clear(sc)
    one = still(sc, alone_frame)
    want = alone_ref_fn()
    d = rel_err(one, want)
    check(d < tol, f'{tag}, frame {alone_frame} rendered alone with no history on disk = the same frame starting '
                   f'clean (worst {d:.1e})')
    rep['alone_worst'] = d
    REPORT[tag] = rep
    history_clear(sc)


def aero_part():
    from eidoblend.look.post import aeropittura as AP
    from eidoblend.look.post import custom_effects as CFX
    from eidoblend.look.post import history as HI
    m = load_meta('aero')
    f0, f1 = m['frames']
    sc = SC.post_scene(m['paths'], tuple(m['view']), fps=int(m['fps']), frames=(f0, f1), res=tuple(m['res']),
                       name='film_aero')
    HI.set_history_dir(sc, os.path.join(OUT, 'history', sc.name))
    e = CFX.apply_to(sc, 'aeropittura', {'aeropittura': {'layer': 'under'}})
    AP.apply_look(e.uniforms, AP.LOOKS['storm'], 1.0)
    AP.set_planes(e.uniforms, AP.PLANES['balla_sun'])
    kf = {int(k): v for k, v in m['key_focal'].items()}
    for f in range(f0, f1 + 1):
        AP.set_focal(e.uniforms, *kf[f], frame=f)
    # the reference for a frame alone: the same frame with a cut on it (the echoes start from the frame itself)
    sc2 = SC.post_scene(m['paths'], tuple(m['view']), fps=int(m['fps']), frames=(f0, f1), res=tuple(m['res']),
                        name='film_aero_cut')
    HI.set_history_dir(sc2, os.path.join(OUT, 'history', sc2.name))
    e2 = CFX.apply_to(sc2, 'aeropittura', {'aeropittura': {'layer': 'under', 'cuts': [9]}})
    AP.apply_look(e2.uniforms, AP.LOOKS['storm'], 1.0)
    AP.set_planes(e2.uniforms, AP.PLANES['balla_sun'])
    for f in range(f0, f1 + 1):
        AP.set_focal(e2.uniforms, *kf[f], frame=f)

    def alone_ref():
        history_clear(sc2)
        return still(sc2, 9)
    temporal_part('aero', sc, f0, f1, 9, alone_ref)


def era_part():
    from eidoblend.look.post import custom_effects as CFX
    from eidoblend.look.post import era_looks as EL
    from eidoblend.look.post import history as HI
    m = load_meta('era', 'meadow')
    f0, f1 = m['frames']
    sc = SC.post_scene(m['paths'], tuple(m['view']), fps=int(m['fps']), frames=(f0, f1), res=tuple(m['res']),
                       name='film_era', clip_end=m.get('clip_end', 2000.0))
    HI.set_history_dir(sc, os.path.join(OUT, 'history', sc.name))
    e = CFX.apply_to(sc, 'era_looks')
    EL.set_look(e.uniforms, EL.ERA_LOOKS['crt'])
    sc2 = SC.post_scene(m['paths'], tuple(m['view']), fps=int(m['fps']), frames=(f0, f1), res=tuple(m['res']),
                        name='film_era_nopersist', clip_end=m.get('clip_end', 2000.0))
    e2 = CFX.apply_to(sc2, 'era_looks', {'era_looks': {'persist_frames': 0}})
    EL.set_look(e2.uniforms, EL.ERA_LOOKS['crt'])
    temporal_part('era_crt', sc, f0, f1, f1, lambda: still(sc2, f1))
    # the glyph atlas travels packed in the .blend: printer1961 rendered by a fresh Blender = the still here
    EL.set_look(e2.uniforms, EL.ERA_LOOKS['printer1961'])
    want = still(sc2, f1)
    set_output(sc2, os.path.join(OUT, 'printer_fresh'))
    blend = os.path.join(OUT, 'film_era_printer.blend')
    bpy.ops.wm.save_as_mainfile(filepath=blend, copy=True)
    r = subprocess.run([bpy.app.binary_path, '--background', '--factory-startup', blend, '--scene', sc2.name,
                        '--render-frame', str(f1)], capture_output=True, text=True, timeout=900, env=dict(os.environ))
    p = os.path.join(OUT, 'printer_fresh', f'f_{f1:04d}.exr')
    got = load_exr(p) if os.path.exists(p) else None
    d = rel_err(got, want) if got is not None else 1.0
    REPORT['printer_fresh'] = {'returncode': r.returncode, 'worst': d}
    check(r.returncode == 0 and got is not None and d < 2e-3,
          f'printer1961 from the saved .blend in a fresh Blender: the packed glyph atlas prints the same page '
          f'(worst relative difference {d:.1e}; exit {r.returncode})')


def section(name, f):
    try:
        f()
    except Exception:                                  # noqa: BLE001
        traceback.print_exc()
        FAIL.append(f'{name}: exception: ' + traceback.format_exc().splitlines()[-1])
    REPORT['fail'] = FAIL
    with open(os.path.join(OUT, 'report.json'), 'w') as fh:
        json.dump(REPORT, fh, indent=1, default=str)


if __name__ == '__main__' or True:
    t_all = time.perf_counter()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    section('after_image', after_image_part)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    section('aero', aero_part)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    section('era', era_part)
    REPORT['total_s'] = round(time.perf_counter() - t_all, 1)
    REPORT['fail'] = FAIL
    with open(os.path.join(OUT, 'report.json'), 'w') as fh:
        json.dump(REPORT, fh, indent=1, default=str)
    for d in glob.glob(os.path.join(OUT, '*_here')) + glob.glob(os.path.join(OUT, '*_fresh')) + \
            [os.path.join(OUT, 'history')]:
        shutil.rmtree(d, ignore_errors=True)                           # regenerable: frames and histories
    for p in glob.glob(os.path.join(OUT, '*.blend1')) + [os.path.join(OUT, '_still.exr')]:
        try:
            os.remove(p)                                               # save backups, the scratch still
        except OSError:
            pass
    print(f"[film] {'FAIL ' + str(len(FAIL)) if FAIL else 'PASS'}", flush=True)

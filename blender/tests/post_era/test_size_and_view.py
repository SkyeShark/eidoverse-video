"""tests/post_era/test_size_and_view.py: the passes under what the harness changes after a scene applied them.

The runner builds a film (setup() applies the effects), then applies the config's "render" block (it may set the
view's look) and, for a probe, caps the frame at 960 x 540 at render time (harness/settings.apply_probe_caps). So a
pass must paint the same picture at a size other than the one it was built at, and its display-space looks must
follow a view set after it:

  - aeropittura built for 1920 x 1080 and composited at 960 x 540 (the probe of a 1080p film) against the pass built
    for 960 x 540: the stroke cells and the underpainting's reach follow the frame, so the two pictures agree (THE
    HOLE, storm, frames 1-6 in order); a sheet with their difference
  - era_looks' poster on an HDR white frame prints bare newsprint, which must land on screen as authored (#ebe5d5)
    through AgX; set the look to 'AgX - Punchy' after applying: display.stale() names the display nodes, and with
    nothing synced the paper comes out wrong; display.keep_synced (on once a pass is applied) copies the view before
    the render, and e.update() (display.sync) does it by hand: both land the paper as authored again
Run from the main checkout (the GPU slot), after test_aeropittura.py --stage sources:
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <worktree>/blender/tests/post_era/test_size_and_view.py
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

OUT = os.path.join(SC.OUT, 'size_view')
FAIL, REPORT = [], {}
os.makedirs(OUT, exist_ok=True)


def check(ok, what):
    print(f"[size_view] {'PASS' if ok else 'FAIL'}: {what}", flush=True)
    if not ok:
        FAIL.append(what)


def load_meta(sub):
    with open(os.path.join(SC.OUT, sub, 'src', 'meta.json')) as f:
        return json.load(f)


def rgb(path):
    return FS.read_rgb(path).astype(np.float64)


# ------------------------------------------------------------------------------------------------- render size
def aero_scene(m, name, build_res):
    """A post scene over THE HOLE's frames at their size, with aeropittura built while the scene was build_res."""
    from eidoblend.look.post import aeropittura as AP
    from eidoblend.look.post import custom_effects as CFX
    from eidoblend.look.post import history as HI
    sc = SC.post_scene(m['paths'], tuple(m['view']), fps=int(m['fps']), frames=(1, 12), res=tuple(m['res']),
                       name=name)
    shutil.rmtree(os.path.join(OUT, 'history', name), ignore_errors=True)
    HI.set_history_dir(sc, os.path.join(OUT, 'history', name))
    r = sc.render
    keep = r.resolution_x, r.resolution_y
    r.resolution_x, r.resolution_y = build_res                    # the film's size when setup() applies the pass
    e = CFX.apply_to(sc, 'aeropittura', {'aeropittura': {'layer': 'under'}})
    r.resolution_x, r.resolution_y = keep                         # the probe cap, at render time
    AP.apply_look(e.uniforms, AP.LOOKS['storm'], 1.0)
    AP.set_planes(e.uniforms, AP.PLANES['balla_sun'])
    kf = {int(k): v for k, v in m['key_focal'].items()}
    for f in range(1, 13):
        AP.set_focal(e.uniforms, *kf[f], frame=f)
    return sc, e


def size_part():
    m = load_meta('aero')
    W, H = m['res']
    a, ea = aero_scene(m, 'aero_built_1080', (2 * W, 2 * H))
    b, eb = aero_scene(m, 'aero_built_540', (W, H))
    grp_a, grp_b = ea.nodes['aeropittura'].node_tree.name, eb.nodes['aeropittura'].node_tree.name
    check(grp_a != grp_b, f'two builds: {grp_a} (for {2 * W}x{2 * H}) and {grp_b} (for {W}x{H})')
    pa = pb = None
    for f in range(1, 7):                                         # in order: the echoes read the frames before
        pa = SC.render_png(a, os.path.join(OUT, f'aero_built_1080_at_540_f{f:02d}.png'), f)
        pb = SC.render_png(b, os.path.join(OUT, f'aero_built_540_at_540_f{f:02d}.png'), f)
    x, y = rgb(pa), rgb(pb)
    d = np.abs(x - y)
    plain = rgb(os.path.join(SC.OUT, 'aero', 'src', 'src_plain_0006.png'))
    paint = float(np.abs(y - plain).mean())
    REPORT['size'] = {'mean_levels': round(float(d.mean()), 3), 'over_16_share': round(float((d.max(axis=2) > 16).mean()), 4),
                      'paint_vs_plain_levels': round(paint, 2), 'groups': [grp_a, grp_b]}
    # the two builds differ only in how densely the underpainting samples the same reach (17 x 17 taps 0.5 px apart
    # against 9 x 9 taps 1 px apart): a small fraction of the painting itself
    check(float(d.mean()) < 0.15 * paint, f'built for 1080p, composited at 540p = built for 540p: mean |difference| '
                                          f'{d.mean():.2f} sRGB levels, against {paint:.1f} between the painting and '
                                          f'the plain frame ({(d.max(axis=2) > 16).mean() * 100:.2f}% of pixels '
                                          f'off by more than 16)')
    heat = os.path.join(OUT, 'aero_size_diff.png')
    from PIL import Image
    Image.fromarray(np.clip(d.max(axis=2) * 4, 0, 255).astype(np.uint8)).save(heat)
    FS.sheet([pa, pb, heat], os.path.join(OUT, 'aero_size_sheet.jpg'), cols=3, tile=640,
             labels=['storm, built for 1920x1080, composited at 960x540 (a probe of a 1080p film)',
                     'storm, built for 960x540', '|difference| x 4'])


# ------------------------------------------------------------------------------------------------- the view
def white_source():
    """One saved frame of scene-linear 100 everywhere: brighter than any view shows, so the poster prints bare paper."""
    d = os.path.join(OUT, 'white_src')
    os.makedirs(d, exist_ok=True)
    W, H = 960, 540
    im = bpy.data.images.new('white_src', W, H, float_buffer=True, alpha=True)
    px = np.full((H, W, 4), 100.0, np.float32)
    px[..., 3] = 1.0
    im.pixels.foreach_set(px.ravel())
    p = os.path.join(d, 'white_0001.exr')
    im.filepath_raw = p
    im.file_format = 'OPEN_EXR'
    im.save()
    return {'Combined': p}


def view_part():
    from eidoblend.look.post import custom_effects as CFX
    from eidoblend.look.post import display as D
    from eidoblend.look.post import era_looks as EL
    from eidoblend.look.post._graph import hex_lin
    paths = white_source()
    sc = SC.post_scene(paths, ('AgX', 'AgX - Base Contrast', 0.0), fps=24, frames=(1, 1), res=(960, 540),
                       name='poster_view', clip_end=100.0)
    e = CFX.apply_to(sc, 'era_looks', {'era_looks': {'persist_frames': 0}})
    EL.set_look(e.uniforms, {'halftone': 1.0})
    want = np.array([int('#ebe5d5'[i:i + 2], 16) for i in (1, 3, 5)], np.float64)
    REPORT['paper_authored'] = want.tolist()
    res = {}

    def paper(tag):
        p = SC.render_png(sc, os.path.join(OUT, f'poster_paper_{tag}.png'), 1)
        a = rgb(p)[60:-60, 60:-60].reshape(-1, 3)
        res[tag] = {'mean': a.mean(0).round(2).tolist(), 'err': round(float(np.abs(a.mean(0) - want).max()), 2)}
        return res[tag]['err']
    err0 = paper('base_contrast')
    check(err0 < 2.0 and not D.stale(sc), f"poster on HDR white prints bare newsprint as authored (#ebe5d5) through "
                                          f"AgX Base Contrast: mean {res['base_contrast']['mean']}, worst channel off "
                                          f"by {err0} levels")
    # a look set after the pass was applied (the harness's config render block does this after setup())
    D.keep_synced(False)                                          # without the render-time sync: the problem
    sc.view_settings.look = 'AgX - Punchy'
    st = D.stale(sc)
    err1 = paper('punchy_stale')
    check(len(st) > 0 and err1 > err0 + 2.0, f"the look changed to AgX - Punchy after applying, nothing synced: "
                                             f"display.stale() names {len(st)} display nodes, and the paper lands off "
                                             f"by {err1} levels")
    D.keep_synced(True)                                           # as the era and aeropittura passes leave it
    err2 = paper('punchy_render_synced')
    check(not D.stale(sc) and err2 < 2.0, f'with keep_synced (render_pre), the render itself copies the view first: '
                                          f"the paper lands as authored through AgX Punchy (mean "
                                          f"{res['punchy_render_synced']['mean']}, off by {err2} levels)")
    D.keep_synced(False)
    sc.view_settings.look = 'AgX - Base Contrast'
    e.update()                                                    # display.sync by hand, as WebGPU's update(t)
    err3 = paper('base_contrast_update')
    D.keep_synced(True)
    check(not D.stale(sc) and err3 < 2.0, f'e.update() copies the view by hand too: back on Base Contrast, the paper '
                                          f'off by {err3} levels')
    REPORT['paper'] = res
    REPORT['paper_linear'] = hex_lin('#ebe5d5')


def section(name, f):
    try:
        f()
    except Exception:                                  # noqa: BLE001
        traceback.print_exc()
        FAIL.append(f'{name}: exception: ' + traceback.format_exc().splitlines()[-1])
    REPORT['fail'] = FAIL
    with open(os.path.join(OUT, 'report.json'), 'w') as fh:
        json.dump(REPORT, fh, indent=1, default=str)


t_all = time.perf_counter()
bpy.ops.wm.read_factory_settings(use_empty=True)
section('view', view_part)
bpy.ops.wm.read_factory_settings(use_empty=True)
section('size', size_part)
REPORT['total_s'] = round(time.perf_counter() - t_all, 1)
REPORT['fail'] = FAIL
with open(os.path.join(OUT, 'report.json'), 'w') as fh:
    json.dump(REPORT, fh, indent=1, default=str)
shutil.rmtree(os.path.join(OUT, 'history'), ignore_errors=True)
print(f"[size_view] {'FAIL ' + str(len(FAIL)) if FAIL else 'PASS'}", flush=True)

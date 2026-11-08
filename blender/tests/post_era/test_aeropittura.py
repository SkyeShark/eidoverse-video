"""tests/post_era/test_aeropittura.py: the futurist pass on a real UNKNOWN FORCE frame: every look, every plane family,
the reading-shot ease, focal / spare / vortex / spin / chevrons, the HAZARD guards, and the time echoes across a cut.

  --stage sources   builds THE HOLE (the film's own set, ported by the city family) with the claudesona dancing
                    and the closeSing camera, and renders frames 1-12 once (EEVEE, Combined as EXR); records where
                    her head and face project on every frame. If the set does not build, the neon street stands in
                    (scenes.neon_night) and the report says so.
  --stage looks     composites the pass over the saved frames, in order (the echoes read the frames before):
                    LOOKS off / hush / argue / storm at frame 12; the six PLANES families under storm; the reading ease
                    (keyed); focal and spare keyed on her every frame; Crali's vortex (dive); spin by a time driver;
                    chevrons turned; a cut at 8 (the cut frame equals the same frame with no echo); the echo split where
                    she moves; a non-finite focal refused, and a NaN keyed into the socket survived; NaN / Inf input
                    pixels; the WebGPU lab's storm frame beside mine; the per-frame cost.
Run from the main checkout (the GPU slot):
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <worktree>/blender/tests/post_era/test_aeropittura.py --stage sources
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <worktree>/blender/tests/post_era/test_aeropittura.py --stage looks
"""
import json
import math
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
STAGE = SC.arg(A, '--stage', 'looks')
OUT = os.path.join(SC.OUT, 'aero')
SRC = os.path.join(OUT, 'src')
F0, F1 = 1, 12
CUT = 8
LAB = os.path.join(SC.MAIN, 'work', 'unknown_force', 'lab', 'lab1080_probe2.png')
FAIL, REPORT = [], {}
os.makedirs(OUT, exist_ok=True)


def check(ok, what):
    print(f"[aero] {'PASS' if ok else 'FAIL'}: {what}", flush=True)
    if not ok:
        FAIL.append(what)


# ------------------------------------------------------------------------------------------------- sources
def sources():
    from eidoblend.look.post import aeropittura as AP
    shutil.rmtree(SRC, ignore_errors=True)
    t0 = time.perf_counter()
    try:
        sc, h, pre = SC.uf_hole(frames=(F0, F1))
        where = 'THE HOLE (eidoblend.sets.unknown_force), closeSing'
    except Exception:                                   # noqa: BLE001
        traceback.print_exc()
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sc, h = SC.neon_night(frames=(F0, 48))
        pre = None
        where = 'the neon street (scenes.neon_night): THE HOLE did not build'
    build_s = time.perf_counter() - t0
    head = h.humanoid.get('head')
    heads, faces = {}, {}
    for f in range(F0, F1 + 1):
        sc.frame_set(f)
        p = h.arm.matrix_world @ h.arm.pose.bones[head].head
        heads[f] = tuple(p)
        faces[f] = AP.project_focal(sc, p + (h.arm.matrix_world.to_3x3() @ h.arm.pose.bones[head].vector) * 0.5)
    paths = SC.render_sources(sc, SRC, range(F0, F1 + 1), name='src', passes=('Depth', 'Normal'), pre=pre)
    # the film's per-frame projections as keys, through the real camera: focal on her head, the spared face (head
    # + 0.12 m, UNKNOWN FORCE's radius rule). The pass is applied here only to key them (after the renders).
    from eidoblend.look.post import custom_effects as CFX
    from eidoblend.look.post import history as HI
    HI.set_history_dir(sc, os.path.join(OUT, 'history_src'))
    e = CFX.apply_to(sc, 'aeropittura', {'aeropittura': {'cuts': []}})
    kf = AP.key_focal(e.uniforms, sc, (h.arm, head), range(F0, F1 + 1))
    ks = AP.key_spare(e.uniforms, sc, (h.arm, head), range(F0, F1 + 1))
    shutil.rmtree(os.path.join(OUT, 'history_src'), ignore_errors=True)
    meta = {'view': (sc.view_settings.view_transform, sc.view_settings.look, sc.view_settings.exposure),
            'fps': sc.render.fps / sc.render.fps_base, 'frames': [F0, F1], 'paths': paths,
            'res': [sc.render.resolution_x, sc.render.resolution_y], 'face_uv': faces, 'head': heads,
            'key_focal': kf, 'key_spare': ks,
            'scene': where, 'build_s': round(build_s, 1), 'total_s': round(time.perf_counter() - t0, 1)}
    with open(os.path.join(SRC, 'meta.json'), 'w') as f:
        json.dump(meta, f, indent=1)
    print(f'[aero] sources: {where}; {meta["total_s"]} s', flush=True)


def load_meta():
    with open(os.path.join(SRC, 'meta.json')) as f:
        return json.load(f)


def exr(scene, frame):
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


def _drop_keys(tree, sock):
    from eidoblend.look.post import history as HI
    ad = tree.animation_data
    if not ad or not ad.action:
        return
    path = sock.path_from_id('default_value')
    for fc in [f for f in HI._fcurves(ad.action, tree) if f.data_path == path]:
        HI._remove_fcurve(ad.action, tree, fc)


# ------------------------------------------------------------------------------------------------- looks
def looks():
    from eidoblend.look.post import aeropittura as AP
    from eidoblend.look.post import custom_effects as CFX
    from eidoblend.look.post import history as HI
    m = load_meta()
    REPORT['scene'] = m['scene']
    face = {int(k): v for k, v in m['face_uv'].items()}
    sc = SC.post_scene(m['paths'], tuple(m['view']), fps=int(m['fps']), frames=(F0, 400), res=tuple(m['res']),
                       name='post_aero')
    shutil.rmtree(os.path.join(OUT, 'history'), ignore_errors=True)
    HI.set_history_dir(sc, os.path.join(OUT, 'history'))
    t0 = time.perf_counter()
    e = CFX.apply_to(sc, 'aeropittura', {'aeropittura': {'layer': 'under'}})
    REPORT['build_s'] = round(time.perf_counter() - t0, 2)
    U = e.uniforms
    check('force' in U and 'chev_dir' in U and 'echo' in U and U['chevDir'] is U['chev_dir'],
          'one effect: its uniforms at the top level, camelCase too (U.force, U.echo, U.chevDir)')
    check(e.effects[0]['layer'] == 'under', "layer 'under' (the film's: captions composite after the paint)")
    # HAZARD: a non-finite focal or spare is refused
    ok = AP.set_focal(U, float('nan'), 0.4)
    check(ok is False and all(math.isfinite(v) for v in U['focal'].default_value),
          f"set_focal(NaN) refused, focal kept finite {tuple(round(v, 3) for v in U['focal'].default_value)}")
    check(AP.set_spare(U, float('inf'), 0.4, 0.1) is False, 'set_spare(Inf) refused')
    AP.set_planes(U, AP.PLANES['balla_sun'])

    def frame_png(name, f):
        p = os.path.join(OUT, f'{name}.png')
        SC.render_png(sc, p, f)
        return p

    def focal_at(f):
        fu = face.get(f)
        if fu:
            AP.set_focal(U, fu[0], fu[1])
    # the echoes read the frames before: composite them first, in order (storm)
    AP.apply_look(U, AP.LOOKS['storm'], 1.0)
    times = []
    for f in range(F0, F1):
        focal_at(f)
        t1 = time.perf_counter()
        SC.render_png(sc, os.path.join(OUT, '_warm.png'), f)
        times.append(time.perf_counter() - t1)
    REPORT['frame_s'] = {'first': round(times[0], 2), 'median': round(float(np.median(times[1:])), 3),
                         'res': m['res']}
    print(f"[aero] composite times: first {times[0]:.2f}s (compile), then median {np.median(times[1:]):.3f}s",
          flush=True)
    focal_at(F1)
    plain = os.path.join(SRC, f'src_plain_{F1:04d}.png')
    paths, labels = [plain], [f'plain ({m["scene"]}, frame {F1})']
    for name, look in AP.LOOKS.items():
        AP.apply_look(U, look, 1.0)
        paths.append(frame_png(f'look_{name}', F1))
        labels.append(f'LOOKS.{name}')
        d = np.abs(FS.read_rgb(paths[-1]).astype(int) - FS.read_rgb(plain).astype(int))
        REPORT.setdefault('looks', {})[name] = round(float(d.mean()), 2)
    if os.path.exists(LAB):
        paths.append(LAB)
        labels.append('WebGPU storm on its lab set (work/unknown_force/lab/lab1080_probe2.png)')
    FS.sheet(paths, os.path.join(OUT, 'aero_looks_sheet.jpg'), cols=3, tile=640, labels=labels)
    check(REPORT['looks']['hush'] < REPORT['looks']['argue'] < REPORT['looks']['storm'],
          f"the looks rise hush < argue < storm (mean change from the plain frame {REPORT['looks']})")
    # the plane families under storm
    AP.apply_look(U, AP.LOOKS['storm'], 1.0)
    pp, pl = [], []
    for fam, w in AP.PLANES.items():
        AP.set_planes(U, w)
        pp.append(frame_png(f'planes_{fam}', F1))
        pl.append(f'PLANES.{fam} (storm)')
    FS.sheet(pp, os.path.join(OUT, 'aero_planes_sheet.jpg'), cols=3, tile=640, labels=pl)
    AP.set_planes(U, AP.PLANES['balla_sun'])
    # the reading shot: the brush eased toward READ (keyed over a long shot around frame 12)
    AP.apply_look(U, AP.LOOKS['argue'], 1.0)
    xp, xl = [frame_png('argue', F1)], [f'argue, frame {F1}']
    AP.ease_reading(U, -30, 60, fps=24)
    sc.frame_set(F1)
    REPORT['reading_at_f1'] = {k: round(U[k].default_value, 3) for k in AP.READ}
    check(all(abs(U[k].default_value - v) < 1e-4 for k, v in AP.READ.items()),
          f'ease_reading keyed: frame {F1} is at READ {REPORT["reading_at_f1"]}')
    xp.append(frame_png('argue_reading', F1))
    xl.append('argue eased to READ (keyed): the words and her face come back')
    for k in AP.READ:
        _drop_keys(sc.compositing_node_group, U[k])
    AP.apply_look(U, AP.LOOKS['storm'], 1.0)
    # focal on her head and spare on her face, keyed on every frame: key_focal / key_spare ran in the sources stage
    # through the real camera (her head bone, the film's radius rule); their keys, copied onto this scene's pass
    kf = {int(k): v for k, v in m['key_focal'].items()}
    ks = {int(k): v for k, v in m['key_spare'].items()}
    for f in range(F0, F1 + 1):
        AP.set_focal(U, *kf[f], frame=f)
        AP.set_spare(U, *ks[f], frame=f)
    sc.frame_set(F1)
    ok_fin = all(all(math.isfinite(v) for v in kf[f]) and all(math.isfinite(v) for v in ks[f]) for f in kf)
    check(ok_fin and 0.0 < ks[F1][2] < 0.9 and abs(U['focal'].default_value[0] - kf[F1][0]) < 1e-5,
          f'key_focal / key_spare: finite every frame, keyed (frame {F1}: focal {[round(v, 3) for v in kf[F1]]}, '
          f'spare {[round(v, 3) for v in ks[F1]]})')
    xp.append(frame_png('storm_focal_spare_keyed', F1))
    xl.append(f'storm, focal on her head + her face spared (r {ks[F1][2]:.2f}), keyed')
    for k in ('focal', 'spare'):
        _drop_keys(sc.compositing_node_group, U[k])
    AP.set_spare(U, 0.5, 0.4, 0.0)
    focal_at(F1)
    AP.set_planes(U, AP.PLANES['dive'])
    U['swirl'].default_value, U['swirl_r'].default_value = 1.2, 0.5
    xp.append(frame_png('storm_dive_swirl', F1))
    xl.append('storm, PLANES.dive, swirl 1.2 rad over swirl_r 0.5 (Crali)')
    U['swirl'].default_value = 0.0
    AP.set_planes(U, AP.PLANES['balla_sun'])
    AP.drive_time(U['spin'], 0.6 * 24 / F1)          # spin = 0.6 rad at frame 12 (the film drove 0.03 rad/s)
    sc.frame_set(F1)
    check(abs(U['spin'].default_value - 0.6) < 1e-3, f"drive_time: spin {U['spin'].default_value:.4f} at frame {F1}")
    xp.append(frame_png('storm_spin', F1))
    xl.append('storm, spin 0.6 rad (a time driver)')
    U['spin'].driver_remove('default_value')
    U['spin'].default_value = 0.0
    U['chev_dir'].default_value = (0.0, 1.0, 0.0)
    AP.set_planes(U, AP.PLANES['revolt'])
    xp.append(frame_png('storm_revolt_chevdown', F1))
    xl.append('storm, PLANES.revolt, chev_dir (0, 1): the wedges point down')
    U['chev_dir'].default_value = (1.0, 0.0, 0.0)
    U['brush_angle'].default_value = -0.5
    AP.set_planes(U, AP.PLANES['quiet'])
    xp.append(frame_png('storm_quiet_brush', F1))
    xl.append('storm, PLANES.quiet, brush_angle -0.5 rad')
    U['brush_angle'].default_value = 1.05
    AP.set_planes(U, AP.PLANES['balla_sun'])
    FS.sheet(xp, os.path.join(OUT, 'aero_uniforms_sheet.jpg'), cols=3, tile=640, labels=xl)
    # the ingredients one at a time (force 1), so each is seen on its own
    ip, il = [], []
    for k in AP.KEYS:
        AP.apply_look(U, AP.LOOKS['off'], 1.0)
        U[k].default_value = 1.0
        ip.append(frame_png(f'only_{k}', F1))
        il.append(f'only {k} = 1')
    FS.sheet(ip, os.path.join(OUT, 'aero_ingredients_sheet.jpg'), cols=4, tile=480, labels=il)
    # the echoes: where she moves, R, G and B show different instants (storm: echo 1)
    AP.apply_look(U, AP.LOOKS['storm'], 1.0)
    a_echo = exr(sc, F1)
    U['echo'].default_value, U['multi'].default_value = 0.0, 0.0
    a_none = exr(sc, F1)
    dch = np.abs(a_echo[..., :3] - a_none[..., :3])
    moving = float((dch.max(axis=2) > 0.02).mean())
    REPORT['echo_changed_share'] = round(moving, 4)
    check(moving > 0.003, f'echo 1 vs 0 at frame {F1}: {moving * 100:.2f}% of pixels change (where she moves)')
    # a cut: the echoes restart, so the cut frame is the same frame with no echo; the frame after has them back
    AP.apply_look(U, AP.LOOKS['storm'], 1.0)
    U.cut(CUT)                                         # WebGPU's U.cut(), keyed at the frame
    for f in range(CUT - 4, CUT):
        SC.render_png(sc, os.path.join(OUT, '_warm.png'), f)
    a_cut = exr(sc, CUT)
    U['echo'].default_value, U['multi'].default_value = 0.0, 0.0
    a_cut0 = exr(sc, CUT)
    d = float(np.abs(a_cut[..., :3] - a_cut0[..., :3]).max())
    check(d < 1e-3, f'cut at {CUT}: storm with echoes = storm without at the cut frame (max diff {d:.2e})')
    AP.apply_look(U, AP.LOOKS['storm'], 1.0)
    a9 = exr(sc, CUT + 1)
    U['echo'].default_value, U['multi'].default_value = 0.0, 0.0
    a9n = exr(sc, CUT + 1)
    d9 = float((np.abs(a9[..., :3] - a9n[..., :3]).max(axis=2) > 0.02).mean())
    check(d9 > 0.001, f'frame {CUT + 1} (one after the cut): the echoes are back ({d9 * 100:.2f}% of pixels differ)')
    # the HAZARD inside the graph: a NaN keyed straight into the socket (past set_focal) still gives a finite frame
    AP.apply_look(U, AP.LOOKS['storm'], 1.0)
    U['focal'].default_value = (float('nan'), 0.4, 0.0)
    a_nan = exr(sc, F1)
    nb = int((~np.isfinite(a_nan[..., :3])).sum())
    lum = float((a_nan[..., :3] @ np.array([0.2126, 0.7152, 0.0722])).mean())
    check(nb == 0 and lum > 1e-4, f'a NaN focal set on the socket directly: the frame stays finite and painted '
                                  f'({nb} bad values, mean luminance {lum:.4f})')
    focal_at(F1)
    REPORT['history_files'] = len(os.listdir(os.path.join(OUT, 'history', 'aeropittura_in')))
    for part in (hazard_input, era_night):              # each on its own: one failing keeps the other
        try:
            part(m)
        except Exception:                               # noqa: BLE001
            traceback.print_exc()
            FAIL.append(f'{part.__name__}: exception: ' + traceback.format_exc().splitlines()[-1])
    REPORT['history_mb'] = round(sum(os.path.getsize(os.path.join(OUT, 'history', 'aeropittura_in', f)) for f in
                                     os.listdir(os.path.join(OUT, 'history', 'aeropittura_in'))) / 1e6, 1)


def era_night(m):
    """The era looks' night presets on the same real night set (the film's own city at night), with its Depth and
    Normal for the storybook lines."""
    from eidoblend.look.post import custom_effects as CFX
    from eidoblend.look.post import era_looks as EL
    from eidoblend.look.post import history as HI
    sc = SC.post_scene(m['paths'], tuple(m['view']), fps=int(m['fps']), frames=(F0, 400), res=tuple(m['res']),
                       name='post_era_hole', clip_end=6000.0)
    HI.set_history_dir(sc, os.path.join(OUT, 'history_era'))
    e = CFX.apply_to(sc, 'era_looks')
    EL.set_look(e.uniforms, EL.ERA_LOOKS['crt'])
    for f in range(F0, F1):
        SC.render_png(sc, os.path.join(OUT, '_warm.png'), f)
    paths, labels = [os.path.join(SRC, f'src_plain_{F1:04d}.png')], ['plain']
    for preset in ('poster_night', 'watercolor_night', 'candle_film', 'crt', 'storybook', 'crt_8bit', 'printer1961',
                   'zine'):
        EL.set_look(e.uniforms, EL.ERA_LOOKS[preset])
        p = os.path.join(OUT, f'era_hole_{preset}.png')
        SC.render_png(sc, p, F1)
        paths.append(p)
        labels.append(f'era_looks {preset}')
    FS.sheet(paths, os.path.join(OUT, 'era_on_hole_sheet.jpg'), cols=3, tile=640, labels=labels)
    shutil.rmtree(os.path.join(OUT, 'history_era'), ignore_errors=True)


def hazard_input(m):
    """NaN and +Inf pixels in the HDR input: the pass clamps its input (the WebGPU san()), so the halos' blur pyramid
    cannot spread them."""
    from eidoblend.look.post import aeropittura as AP
    from eidoblend.look.post import custom_effects as CFX
    from eidoblend.look.post import history as HI
    src = m['paths']['Combined']
    im = bpy.data.images.load(src, check_existing=False)
    W, H = im.size
    a = np.array(im.pixels[:], np.float32).reshape(H, W, 4)
    bpy.data.images.remove(im)
    a[H // 3, W // 3, :3] = np.nan
    a[H // 2, W // 2, :3] = np.inf
    hz = os.path.join(OUT, 'hazard')
    os.makedirs(hz, exist_ok=True)
    out = bpy.data.images.new('aero_hazard', W, H, float_buffer=True, alpha=True)
    out.pixels.foreach_set(a.ravel())
    out.filepath_raw = os.path.join(hz, 'nan_0001.exr')
    out.file_format = 'OPEN_EXR'
    out.save()
    sc = SC.post_scene({'Combined': os.path.join(hz, 'nan_0001.exr')}, tuple(m['view']), fps=int(m['fps']),
                       frames=(1, 10), res=tuple(m['res']), name='post_aero_hazard')
    HI.set_history_dir(sc, os.path.join(OUT, 'history_hazard'))
    e = CFX.apply_to(sc, 'aeropittura')
    AP.apply_look(e.uniforms, AP.LOOKS['storm'], 1.0)
    r = exr(sc, 1)[..., :3]
    nb = int((~np.isfinite(r)).sum())
    black = float((r.max(axis=2) < 1e-6).mean())
    REPORT['hazard_input'] = {'bad': nb, 'black_share': round(black, 4)}
    check(nb == 0 and black < 0.5, f'NaN / Inf input pixels under storm: {nb} bad values, {black * 100:.1f}% '
                                   f'of the frame black (not the WebGPU blackout)')
    SC.render_png(sc, os.path.join(OUT, 'hazard_storm.png'), 1)
    shutil.rmtree(os.path.join(OUT, 'history_hazard'), ignore_errors=True)


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
    print(f"[aero] {STAGE}: {'FAIL ' + str(len(FAIL)) if FAIL else 'PASS'}", flush=True)

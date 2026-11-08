"""Probe: the overlay's two routes around the post chain, LyricRenderer on the frame, and an engine sprite atlas on a
screen. From the main checkout (DAISY's timeline first: run_daisy.py song, see test_era_screens.py):

    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/media2/test_overlay_routes.py [-- --only routes,atlas]

routes   the voder_1939 wall at DAISY's 24.5 s ("I was a hiss and a buzz..."), six frames at 24 fps, with an overlay
         layer holding a lower third (solid teal, white, #ffd400 and #101418 ink) and DAISY's lyrics through
         lyrics.make_lyric_layer (LyricRenderer, mono, teal glow). Rendered five ways at frame 3:
           display   film PNGs + overlay PNGs in the edit scene (make_edit_scene): ink exact
           burn      LyricRenderer.burn over the film PNGs, compared with the display route's lyric
           authored  overlay.chain_overlay(ov, film): the overlay in the film's post chain, laid over the film in
                     display space and brought back through the inverse view transform: the solid ink, the lyric's
                     glow ring and its 160/255 pill against the display route
           graded    chain_overlay(..., authored=False): the HUD's linear light graded by AgX with the film
           layered   + sepia 'under' and rgb_shift 'over' (look/post custom_effects): the HUD keeps its ink, its
                     edges split; then sepia moved 'over': the HUD goes sepia with the film
         -> out/overlay_routes_sheet.png and one PNG per route
fade     a white and a teal box fading in (alpha 0, 0.1 .. 1 over frames 1..11) over a dark backdrop and over a lamp
         band brighter than AgX's white: the display route's blend against chain_overlay (authored, graded, and at
         factor 0.5), and chain_overlay(source=PNGs) from an overlay rendered over frames 4..8 only (clear before
         and after its range) -> out/overlay_fade_strip.png
atlas    eidoverse/video_to_sprite.mjs (node, unchanged) turns test_era_screens.py's EEVEE film into a sprite atlas;
         screens.make_atlas_screen plays it on c64.glb's monitor by screen.js's rule -> out/atlas_tv_f*.png
Prints PASS/FAIL lines for what it measures.
"""
import shutil
import subprocess
import sys
from pathlib import Path

import bpy
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'media'))
import _stage as S  # noqa: E402  (round one's stage helpers)
from eidoblend.look.post import chain  # noqa: E402
from eidoblend.media import canvas_scenes as cs  # noqa: E402
from eidoblend.media import lyrics, overlay, raster, screens  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ONLY = set(argv[argv.index('--only') + 1].split(',')) if '--only' in argv else {'routes', 'fade', 'atlas'}
OUT = HERE / 'out'
WORK = OUT / 'overlay_work'
TIMELINE = OUT / 'daisy' / 'out' / 'daisy_timeline_upto_chorus2.json'
FONT = HERE.parents[2] / 'eidoverse' / 'assets' / 'fonts' / 'ShareTechMono-Regular.ttf'
FPS, T_START, N, F = 24, 24.5, 6, 3
W, H = 960, 540
INK = {'teal': '#27e0a0', 'white': '#ffffff', 'yellow': '#ffd400', 'box': '#101418'}
LT = dict(x=-0.25, y=0.33, w=0.42, h=0.16)                 # the lower third on the frame (fractions, centre origin)
FAILS = []


def check(ok, what):
    print(f"{'PASS' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        FAILS.append(what)


def rgb(png):
    return np.asarray(Image.open(png).convert('RGB')).astype(float)


def hud_px(fx_, fy_):
    """A point of the lower third (fractions from its top left) -> output pixel (x, y)."""
    x = (0.5 + LT['x'] - LT['w'] / 2 + fx_ * LT['w']) * W
    y = (0.5 - LT['y'] - LT['h'] / 2 + fy_ * LT['h']) * H
    return int(round(x)), int(round(y))


SPOTS = {'white': (0.18, 0.30), 'yellow': (0.18, 0.70), 'teal': (0.015, 0.5), 'box': (0.70, 0.86)}


def ink_at(a, name, r=2):
    x, y = hud_px(*SPOTS[name])
    return a[y - r:y + r + 1, x - r:x + r + 1].reshape(-1, 3).mean(axis=0)


def lower_third(c, t, w, h):
    d = c.draw
    c.clear(INK['box'])
    d.rectangle([0, 0, int(w * 0.03), h], fill=raster.color(INK['teal']))
    d.rectangle([int(w * 0.06), int(h * 0.12), int(w * 0.30), int(h * 0.48)], fill=raster.color(INK['white']))
    d.rectangle([int(w * 0.06), int(h * 0.55), int(w * 0.30), int(h * 0.85)], fill=raster.color(INK['yellow']))
    d.text((int(w * 0.36), int(h * 0.14)), 'THE VODER  1939', font=raster.font('Share Tech Mono', h * 0.30),
           fill=raster.color(INK['white']))
    d.text((int(w * 0.36), int(h * 0.50)), 'Bell Telephone Laboratories', font=raster.font('Share Tech Mono', h * 0.2),
           fill=raster.color(INK['teal']))


def stage(sc):
    S.box(sc, 'floor', (14, 12, 0.04), (0, -3.0, -0.02),
          S.pbr_material('stage_floor', S.cached('textures', 'Planks039_2k'), scale=0.45))
    S.box(sc, 'drape', (14, 0.1, 6), (0, 0.6, 3), S.plain_material('drape', (0.012, 0.012, 0.014), 0.95))
    S.box(sc, 'cabinet', (4.92, 0.14, 2.12), (0, 0.09, 1.6), S.plain_material('cabinet', (0.02, 0.02, 0.022), 0.45, 0.6))
    S.box(sc, 'riser', (5.4, 1.4, 0.5), (0, -0.4, 0.25), S.plain_material('riser', (0.03, 0.03, 0.032), 0.7))
    stool = S.cached('models', 'wooden_stool_01_1k')
    if stool:
        for o in S.import_gltf(stool / 'wooden_stool_01_embedded.gltf'):
            if o.parent is None:
                o.location = (1.25, -1.9, 0)


def render_frames(sc, pattern, a, b):
    sc.frame_start, sc.frame_end = a, b
    r = sc.render
    r.image_settings.media_type = 'IMAGE'
    r.image_settings.file_format = 'PNG'
    r.image_settings.color_mode = 'RGB'
    r.filepath = str(pattern)
    bpy.ops.render.render(animation=True, scene=sc.name)
    files = [Path(str(pattern).replace('####', f'{f:04d}')) for f in range(a, b + 1)]
    if not all(f.exists() for f in files):
        raise RuntimeError(f'missing frames for {pattern}')
    return files


def render_still(sc, frame, path):
    sc.frame_set(frame)
    r = sc.render
    r.image_settings.media_type = 'IMAGE'
    r.image_settings.file_format = 'PNG'
    r.image_settings.color_mode = 'RGB'
    r.filepath = str(path)
    bpy.ops.render.render(write_still=True, scene=sc.name)
    if not Path(path).exists():
        raise RuntimeError(f'no {path}')
    return Path(path)


def probe_routes():
    sc = S.fresh_scene(res=(W, H), samples=16, fps=FPS, frames=(1, N))
    sc.name = 'film'
    sc['eido_frame0'] = 1 - round(T_START * FPS)              # frame 1 = 24.5 s of the song
    stage(sc)
    info = screens.bake_canvas_scene(WORK / 'voder', (1, N), scene_name='voder_1939', t0=cs.DAISY_CUES['voder_1939'],
                                     W=1440, H=600, lyrics=TIMELINE, bpm=128)
    wall = screens.make_screen(width=4.8, height=2.0, source=info['first'], frames=(1, N), name='voder_wall',
                               strength=1.25, spill=0.75)
    wall.obj.location = (0, 0.0, 1.6)
    S.area_light(sc, (0.5, -4.0, 4.5), (0, -1.6, 0.5), 45.0, size=2.0, color=(1.0, 0.86, 0.72), name='front_wash')
    S.camera(sc, (-0.9, -7.4, 1.55), (0.0, 0.0, 1.45), lens=40)

    ov = overlay.make_overlay_layer(sc, filter_size=0.0)    # drawn graphics at their own pixels
    ov.panel(draw=lower_third, px=800, frames=(1, N), name='lower_third', out_dir=WORK / 'lower_third', **LT)
    r = lyrics.LyricRenderer(TIMELINE, width=W, height=H, font='mono', font_size=30, glow=True,
                             glow_color=(39, 224, 160))
    lay = lyrics.make_lyric_layer(ov, r, frames=(1, N), out_dir=WORK / 'lyric_layer')
    t3 = (F - sc['eido_frame0']) / FPS
    text, alpha = r.get_line_at(t3)
    check(text is not None and alpha > 0.99, f'the lyric at frame {F} ({t3:.3f} s): {text!r}, alpha {alpha:.2f}')
    check(lay.obj.name in ov.scene.objects, 'make_lyric_layer: one full-frame panel on the overlay layer')

    # display route: film PNGs + overlay PNGs in the edit scene
    film_files = render_frames(sc, WORK / 'film' / 'f_####.png', 1, N)
    ov_dir = overlay.render_overlay(ov, WORK / 'ov')
    edit = overlay.make_edit_scene(film=film_files[0], overlays=[ov_dir], like=sc)
    overlay.render_edit(edit, WORK / 'edit', video=False)
    disp = OUT / 'overlay_route_display_f003.png'
    shutil.copyfile(WORK / 'edit' / f'edit_{F:04d}.png', disp)
    a = rgb(disp)
    for k in ('teal', 'white', 'yellow', 'box'):
        want = np.array(raster.color(INK[k])[:3], float)
        got = ink_at(a, k)
        check(np.abs(got - want).max() <= 2.0, f'display route: {k} ink {np.round(got, 1).tolist()} vs authored '
                                               f'{want.tolist()}')

    # burn: LyricRenderer.burn over the film frames (the original's use) against the edit scene's lyric
    burned = r.burn(film_files, WORK / 'burn', fps=FPS, first_frame=1, frame0=sc['eido_frame0'])
    b = rgb(burned[F - 1])
    y0 = int(r.y_pos - 40)
    band = (slice(y0, int(r.y_pos + 40)), slice(int(W * 0.1), int(W * 0.9)))
    d = np.abs(b[band] - a[band])
    check(d.mean() < 0.5 and np.percentile(d, 99) <= 3, f'burn vs the overlay route over the lyric band (overlay '
                                                        f'filter_size 0): mean |diff| {d.mean():.2f}, p99 '
                                                        f'{np.percentile(d, 99):.1f}, max {d.max():.0f}')
    lay_rgba = np.asarray(r.layer(t3)).astype(float)
    core = (lay_rgba[..., 3] >= 250) & (lay_rgba[..., :3].min(axis=-1) >= 250)       # the white text's solid core
    shutil.copyfile(burned[F - 1], OUT / 'overlay_route_burn_f003.png')

    # signal route: the overlay in the film's post chain, laid over the film in display space
    sc.frame_start, sc.frame_end = 1, N
    nodes = overlay.chain_overlay(ov, sc)
    st = [(s, n) for s, n, _x in chain.stages(sc)]
    check(st == [('overlay', 'overlay')] and nodes['stage'] is nodes['authored'],
          f'chain after chain_overlay: {st}, the overlay stage is the display-space group')
    auth = render_still(sc, F, OUT / 'overlay_route_authored_f003.png')
    a2 = rgb(auth)
    for k, tol in (('teal', 3.0), ('white', 3.0), ('box', 3.0), ('yellow', 60.0)):
        want = np.array(raster.color(INK[k])[:3], float)
        got = ink_at(a2, k)
        err = np.abs(got - want).max()
        note = ' (AgX cannot show it: measured beforehand, 50/255)' if k == 'yellow' else ''
        check(err <= tol, f'signal route, authored: {k} ink {np.round(got, 1).tolist()} vs {want.tolist()}, '
                          f'max err {err:.1f}{note}')
    film_only = np.abs(a2[300:420, 120:840] - a[300:420, 120:840]).mean()
    check(film_only < 2.5, f'signal route: the film under the HUD matches the display route (mean |diff| '
                           f'{film_only:.2f} away from the graphics)')
    lyr = np.abs(a2[core] - a[core]).mean()
    check(core.sum() > 200 and lyr < 3.0,
          f'signal route: the lyric text core ({int(core.sum())} px) lands as in the display route (mean |diff| '
          f'{lyr:.2f})')
    al = lay_rgba[..., 3]
    pill = (al >= 155) & (al <= 165)                                # the backing pill alone, 160/255
    ring = (al > 170) & (al < 245)                                  # the teal glow over the pill: soft pixels
    for nm, m, tol in (('the 160/255 pill', pill, 1.5), ('the teal glow ring', ring, 2.0)):
        d = np.abs(a2[m] - a[m])
        check(m.sum() > 500 and d.mean() < tol and np.percentile(d, 95) <= 6,
              f'signal route: {nm} ({int(m.sum())} px) lands as in the display route: mean |diff| {d.mean():.2f}, '
              f'p95 {np.percentile(d, 95):.1f} (means {np.round(a2[m].mean(axis=0), 1).tolist()} vs '
              f'{np.round(a[m].mean(axis=0), 1).tolist()})')
    d = np.abs(a2[band] - a[band])
    check(d.mean() < 1.0 and np.percentile(d, 99) <= 8, f'signal route over the whole lyric band: mean |diff| '
                                                        f'{d.mean():.2f}, p99 {np.percentile(d, 99):.1f}')
    side = np.concatenate([a[band], a2[band]], axis=0)
    Image.fromarray(np.repeat(np.repeat(side, 2, 0), 2, 1).astype(np.uint8)).save(OUT / 'overlay_lyric_glow_ab_x2.png')

    # graded: the overlay's linear light alpha-overs the film and AgX grades it (authored=False)
    g = overlay.chain_overlay(ov, sc, authored=False)
    st = [(s, n) for s, n, _x in chain.stages(sc)]
    check(st == [('overlay', 'overlay')] and g['stage'].bl_idname == 'CompositorNodeAlphaOver'
          and g['authored'] is None, f'chain_overlay(authored=False) replaces the stage with an Alpha Over: {st}')
    graded = render_still(sc, F, OUT / 'overlay_route_graded_f003.png')
    a3 = rgb(graded)
    g_teal = ink_at(a3, 'teal')
    check(np.abs(g_teal - ink_at(a2, 'teal')).max() > 10, f'graded: teal lands at {np.round(g_teal, 1).tolist()} '
                                                         f'(AgX on linear ink), not the authored ink')
    overlay.chain_overlay(ov, sc)
    shots = [(disp, 'display route: edit scene, ink exact'), (OUT / 'overlay_route_burn_f003.png',
                                                             'LyricRenderer.burn over the film'),
             (auth, 'signal route: chain_overlay, authored'), (graded, 'signal route, authored=False (AgX grades it)')]
    try:                    # the look family's effect registry (being extended in parallel): its own import can fail
        from eidoblend.look.post import custom_effects as fx
    except Exception as e:  # noqa: BLE001
        check(False, f'layering not probed: eidoblend.look.post.custom_effects does not import ({type(e).__name__}: '
                     f'{e})')
        fx = None
    if fx is not None:
        shots += probe_layering(sc, fx, a, a2)
    sheet(shots, OUT / 'overlay_routes_sheet.png', 'the overlay around the post chain (frame 3, DAISY 24.58 s)')
    shutil.rmtree(WORK / 'film', ignore_errors=True)
    shutil.rmtree(WORK / 'edit', ignore_errors=True)
    shutil.rmtree(WORK / 'burn', ignore_errors=True)


def probe_layering(sc, fx, a, a2):
    """sepia 'under' the overlay and rgb_shift 'over' it, then sepia moved 'over'. a: the display route's frame,
    a2: the authored signal route's."""
    fx.apply_to(sc, 'sepia,rgb_shift', {'sepia': {'layer': 'under'}, 'rgb_shift': {'layer': 'over', 'amount': 0.004}})
    st = [(s, n) for s, n, _x in chain.stages(sc)]
    check(st == [('under', 'sepia'), ('overlay', 'overlay'), ('over', 'rgb_shift')], f'chain order: {st}')
    lay_png = render_still(sc, F, OUT / 'overlay_route_layered_f003.png')
    a4 = rgb(lay_png)
    t4 = ink_at(a4, 'teal', r=1)
    check(t4[1] > t4[0] + 80, f'layered: the HUD teal stays teal under the world sepia ({np.round(t4, 1).tolist()})')
    wall_c = a4[150:330, 250:700].reshape(-1, 3).mean(axis=0)
    wall_d = a[150:330, 250:700].reshape(-1, 3).mean(axis=0)
    check(wall_c[0] > wall_c[2] + 15 and wall_d[2] > wall_d[0], f'layered: the wall goes sepia (mean '
                                                                 f'{np.round(wall_c, 1).tolist()}, was '
                                                                 f'{np.round(wall_d, 1).tolist()})')
    # rgb_shift over the HUD: at the white block's left edge red reaches white early and blue late (where each
    # channel first reaches 245: AgX's path to white lifts the other channels beside an over-bright one)
    x0, y = hud_px(0.06, 0.30)
    row4, row2 = a4[y, x0 - 10:x0 + 10], a2[y, x0 - 10:x0 + 10]
    full = lambda ch, row: int(np.argmax(row[:, ch] >= 245))              # noqa: E731
    e4, e2 = [full(c, row4) for c in range(3)], [full(c, row2) for c in range(3)]
    check(e4[0] < e4[1] < e4[2] and e4[2] - e4[0] >= 6 and len(set(e2)) == 1,
          f'layered: rgb_shift splits the HUD white block edge: red, green, blue reach white at {e4} px '
          f'(amount 0.004 = {0.004 * W:.2f} px each way; {e2} without it)')
    chain.remove_stage(sc, 'sepia')
    fx.apply_to(sc, 'sepia', {'sepia': {'layer': 'over'}})
    over_png = render_still(sc, F, OUT / 'overlay_route_sepia_over_f003.png')
    a5 = rgb(over_png)
    t5 = ink_at(a5, 'teal', r=1)
    check(t5[0] >= t5[1] - 25, f'sepia moved over: the HUD teal goes sepia with the film ({np.round(t5, 1).tolist()})')
    return [(lay_png, "sepia 'under' + rgb_shift 'over'"), (over_png, "sepia moved 'over': HUD in the signal")]


def probe_fade():
    """Soft overlay pixels through the signal route: two boxes fading in over a dark backdrop and a lamp band."""
    fw, fh = 480, 270
    sc = S.fresh_scene(res=(fw, fh), samples=4, fps=24, frames=(1, 11))
    sc.name = 'fade_film'
    sc['eido_frame0'] = 1
    S.box(sc, 'backdrop', (8, 0.1, 5), (0, 1.5, 0), S.plain_material('backdrop', (0.05, 0.05, 0.05), 0.8))
    lamp = bpy.data.materials.new('lamp_band')
    em = lamp.node_tree.nodes.new('ShaderNodeEmission')
    em.inputs['Strength'].default_value = 60.0                  # far past AgX's white (16.5 scene-linear)
    lamp.node_tree.links.new(em.outputs[0], lamp.node_tree.nodes['Material Output'].inputs['Surface'])
    S.box(sc, 'lamp_band', (8, 0.05, 0.36), (0, 1.4, -0.33), lamp)
    S.area_light(sc, (0, -2, 1), (0, 1.5, 0), 20.0, size=3.0, name='key')
    S.camera(sc, (0, -4, 0), (0, 0, 0), lens=35)
    ov = overlay.make_overlay_layer(sc, filter_size=0.0)
    wd = WORK / 'fade'
    shutil.rmtree(wd, ignore_errors=True)

    def box(color):
        def draw(c, t, w, h):
            c.clear((*color, int(round(min(1.0, max(0.0, t * 24 / 10)) * 255))))   # frame 1: 0 .. frame 11: 255
        return draw

    teal = raster.color(INK['teal'])[:3]
    ov.panel(draw=box((255, 255, 255)), x=-0.22, y=0.0, w=0.3, h=0.4, px=200, frames=(1, 11), name='white_box',
             out_dir=wd / 'white', supersample=1)
    ov.panel(draw=box(teal), x=0.22, y=0.0, w=0.3, h=0.4, px=200, frames=(1, 11), name='teal_box',
             out_dir=wd / 'teal', supersample=1)
    xs = {'white': int((0.5 - 0.22) * fw), 'teal': int((0.5 + 0.22) * fw)}
    ys = {'dark': int(0.40 * fh), 'lamp': int(0.615 * fh)}
    pick = lambda a, k, r: a[ys[r] - 3:ys[r] + 4, xs[k] - 3:xs[k] + 4].reshape(-1, 3).mean(axis=0)   # noqa: E731
    frames = (2, 3, 4, 6, 11)
    film = {f: rgb(render_still(sc, f, wd / f'film_{f:03d}.png')) for f in (1, 2, 3, 4, 6, 10, 11)}
    lamp_px = pick(film[2], 'white', 'lamp')
    check(lamp_px.min() >= 250, f'fade: the lamp band displays white ({np.round(lamp_px, 1).tolist()})')
    ov_dir = overlay.render_overlay(ov, wd / 'ov')
    disp = {}
    for f in frames:
        o = np.asarray(Image.open(ov_dir / f'ov_{f:04d}.png').convert('RGBA')).astype(float)
        al = o[..., 3:] / 255.0
        disp[f] = o[..., :3] * al + film[f] * (1 - al)          # the display route's blend (the edit scene's)
    nodes = overlay.chain_overlay(ov, sc)
    auth = {f: rgb(render_still(sc, f, wd / f'authored_{f:03d}.png')) for f in frames}
    worst = 0.0
    for f in frames:
        al = (f - 1) / 10
        for k in ('white', 'teal'):
            d = np.abs(pick(auth[f], k, 'dark') - pick(disp[f], k, 'dark')).max()
            worst = max(worst, d)
            print(f'[fade] alpha {al:.1f} {k:5s} over the backdrop: display '
                  f'{np.round(pick(disp[f], k, "dark"), 1).tolist()} authored '
                  f'{np.round(pick(auth[f], k, "dark"), 1).tolist()} | over the lamp: display '
                  f'{np.round(pick(disp[f], k, "lamp"), 1).tolist()} authored '
                  f'{np.round(pick(auth[f], k, "lamp"), 1).tolist()}', flush=True)
    check(worst <= 3.0, f'fade: white and teal at alpha 0.1, 0.2, 0.3, 0.5, 1.0 over the backdrop land as the '
                        f'display route blends them (worst channel {worst:.1f} levels)')
    t_lamp = pick(auth[11], 'teal', 'lamp')
    check(np.abs(t_lamp - np.array(teal, float)).max() <= 3.0,
          f'fade: solid teal over the lamp lands exactly ({np.round(t_lamp, 1).tolist()} vs {list(teal)})')
    a0 = rgb(render_still(sc, 1, wd / 'authored_001.png'))
    check(np.abs(a0 - film[1]).max() <= 1.0, f'fade: alpha 0 leaves the film untouched, lamp included (max |diff| '
                                              f'{np.abs(a0 - film[1]).max():.0f})')
    t_soft = pick(auth[6], 'teal', 'lamp')
    print(f'[fade] teal at alpha 0.5 over the lamp: authored {np.round(t_soft, 1).tolist()}, display '
          f'{np.round(pick(disp[6], "teal", "lamp"), 1).tolist()} (the lamp light AgX cannot show keeps (1 - a) of '
          f'its excess under soft pixels)', flush=True)

    # the factor: alpha 1 at factor 0.5 = alpha 0.5
    nodes['factor'].default_value = 0.5
    half = rgb(render_still(sc, 11, wd / 'authored_factor05_011.png'))
    d = max(np.abs(pick(half, k, 'dark') - pick(disp[6], k, 'dark')).max() for k in ('white', 'teal'))
    check(d <= 3.0, f'fade: factor 0.5 on solid boxes lands as alpha 0.5 does on the display route ({d:.1f} levels)')
    nodes['factor'].default_value = 1.0

    # graded (authored=False): the old linear over, for the table
    overlay.chain_overlay(ov, sc, authored=False)
    grad = {f: rgb(render_still(sc, f, wd / f'graded_{f:03d}.png')) for f in (2, 6)}
    for f in (2, 6):
        print(f'[fade] graded alpha {(f - 1) / 10:.1f}: white {np.round(pick(grad[f], "white", "dark"), 1).tolist()} '
              f'teal {np.round(pick(grad[f], "teal", "dark"), 1).tolist()}', flush=True)

    # a PNG source covering frames 4..8 only: clear before and after its range, as drawn inside it
    late = overlay.render_overlay(ov, wd / 'ov_late', frames=(4, 8))
    overlay.chain_overlay(ov, sc, source=late)
    holds = sorted(p.name for p in late.glob('*.png') if screens._is_hold(p))
    out_before = rgb(render_still(sc, 2, wd / 'late_002.png'))
    out_in = rgb(render_still(sc, 6, wd / 'late_006.png'))
    out_after = rgb(render_still(sc, 10, wd / 'late_010.png'))
    d_before, d_after = np.abs(out_before - film[2]).max(), np.abs(out_after - film[10]).max()
    d_in = max(np.abs(pick(out_in, k, r) - pick(auth[6], k, r)).max() for k in ('white', 'teal') for r in ('dark', 'lamp'))
    check(holds == ['ov_0003.png', 'ov_0009.png'] and d_before <= 1.0 and d_after <= 1.0 and d_in <= 2.0,
          f'fade: chain_overlay(source=PNGs of frames 4..8): clear holds {holds}; frames 2 and 10 are the bare film '
          f'(max |diff| {d_before:.0f}, {d_after:.0f}: nothing before the range, nothing frozen after it), frame 6 '
          f'the overlay ({d_in:.1f} levels from the Render Layers source)')

    # the strip to look at: display (top), authored (middle), graded (bottom where rendered)
    rows = [np.concatenate([disp[f] for f in frames], axis=1), np.concatenate([auth[f] for f in frames], axis=1)]
    strip = np.concatenate(rows, axis=0).astype(np.uint8)
    Image.fromarray(strip).save(OUT / 'overlay_fade_strip.png')
    print(f'[sheet] {OUT / "overlay_fade_strip.png"}', flush=True)


def probe_atlas():
    movie = OUT / 'era_film_silent.mp4'
    if not movie.exists():
        check(False, f'{movie.name} missing: run test_era_screens.py --only film first')
        return
    node = shutil.which('node') or 'C:/Program Files/nodejs/node.exe'
    adir = WORK / 'atlas'
    adir.mkdir(parents=True, exist_ok=True)
    res = subprocess.run([node, str(HERE.parents[2] / 'eidoverse' / 'video_to_sprite.mjs'), str(movie), '--fps', '12',
                          '--width', '256', '--height', '144', '--max-frames', '48', '--output',
                          str(adir / 'era_film_sprite')], capture_output=True, text=True)
    print(res.stdout[-800:], res.stderr[-800:])
    jpg, info_p = adir / 'era_film_sprite.jpg', adir / 'era_film_sprite_info.json'
    check(res.returncode == 0 and jpg.exists() and info_p.exists(), 'video_to_sprite.mjs (node, unchanged) wrote '
                                                                    'the atlas and its info')
    info = screens.read_atlas_info(info_p)
    print('[atlas] info', info)
    # the reader's tiles against the movie's own frames (the tool samples at --fps from the movie)
    tmp = adir / 'ref'
    tmp.mkdir(exist_ok=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(movie), '-vf', 'scale=256:144', '-frames:v', '48',
                    str(tmp / 'm_%03d.png')], check=True)
    errs = []
    for i in (0, 7, 23, 47):
        tile = np.asarray(screens.atlas_tile(jpg, info, i).convert('RGB')).astype(float)
        ref = np.asarray(Image.open(tmp / f'm_{i + 1:03d}.png').convert('RGB')).astype(float)
        errs.append(np.abs(tile - ref).mean())
    check(max(errs) < 6.0, f'atlas tiles 0/7/23/47 match the movie frames (mean |diff| {[round(e, 2) for e in errs]}: '
                           f'JPEG)')
    sc = S.fresh_scene(res=(W, H), samples=16, fps=24, frames=(1, 60))
    S.box(sc, 'desk', (1.8, 1.0, 0.04), (0, 0.05, -0.02),
          S.pbr_material('desk_wood', S.cached('textures', 'PaintedWood009C_2k'), scale=1.6))
    S.box(sc, 'wall', (3.0, 0.05, 2.0), (0, 0.62, 0.8), S.plain_material('wall', (0.30, 0.29, 0.27), 0.85))
    objs = S.import_gltf(S.ASSETS / 'models' / 'voice_machines' / 'c64.glb')
    tube = next(o for o in objs if o.name.startswith('screen_crt'))
    scr = screens.make_atlas_screen(jpg, info, width=0.3, start_frame=1, speed=1.0, loop=True,
                                    out_dir=WORK / 'atlas_frames', name='atlas_tv', standalone=False, strength=1.6,
                                    spill=0.5)
    scr.apply_to(tube, glass=True, window=(0.0, 0.125, 1.0, 0.875))   # 16:9 tiles letterboxed on the 4:3 tube
    want = [screens.engine_movie_frame(f - 1, 24, info['fps'], 1.0, info['totalFrames'], True) for f in (1, 2, 30, 60)]
    got = []
    for f in (1, 2, 30, 60):
        p = WORK / 'atlas_frames' / f'atlas_tv_{f:04d}.png'
        a = np.asarray(Image.open(p).convert('RGB')).astype(float)
        got.append(int(np.argmin([np.abs(a - np.asarray(screens.atlas_tile(jpg, info, i).convert('RGB'))).mean()
                                  for i in range(info['totalFrames'])])))
    check(got == want, f'atlas screen frames 1/2/30/60 show tiles {got} (screen.js rule: {want})')
    S.area_light(sc, (-0.8, -0.7, 1.0), (0, 0, 0.2), 30.0, size=0.7, color=(1.0, 0.86, 0.70), name='lamp')
    S.area_light(sc, (1.0, -1.0, 1.5), (0, 0, 0.2), 8.0, size=1.2, color=(0.75, 0.82, 1.0), name='fill')
    S.camera(sc, (0.42, -1.05, 0.55), (0.0, 0.0, 0.26), lens=40)
    stills = [render_still(sc, f, OUT / f'atlas_tv_f{f:03d}.png') for f in (2, 40)]
    for s in stills:
        a = rgb(s)
        check(a.std() > 10, f'{s.name}: rendered (std {a.std():.1f})')
    shutil.rmtree(tmp, ignore_errors=True)


def sheet(items, path, title):
    tw, th, pad = 480, 270, 8
    im = Image.new('RGB', (pad + 2 * (tw + pad), 40 + 3 * (th + 28 + pad)), (18, 18, 22))
    d = ImageDraw.Draw(im)
    fnt, big = ImageFont.truetype(str(FONT), 15), ImageFont.truetype(str(FONT), 19)
    d.text((pad, 10), title, font=big, fill=(232, 228, 216))
    for i, (p, label) in enumerate(items):
        x, y = pad + (i % 2) * (tw + pad), 40 + (i // 2) * (th + 28 + pad)
        d.text((x, y + 4), label, font=fnt, fill=(232, 228, 216))
        im.paste(Image.open(p).convert('RGB').resize((tw, th), Image.Resampling.LANCZOS), (x, y + 26))
    im.save(path)
    print(f'[sheet] {path}')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    check(TIMELINE.exists(), f'DAISY timeline present ({TIMELINE.name})')
    if 'routes' in ONLY:
        probe_routes()
    if 'fade' in ONLY:
        probe_fade()
    if 'atlas' in ONLY:
        probe_atlas()
    print(f'[test_overlay_routes] {"ALL OK" if not FAILS else f"{len(FAILS)} FAILED"}', flush=True)


main()

"""Probe: the contract that a saved .blend plays and renders any frame on its own, for this package's keyed systems.
Two Blender processes, through the GPU slot, from the main checkout:

    bash run_blender.sh <worktree>/blender/tests/media2/test_reopen.py              # build, render, save
    bash run_blender.sh <worktree>/blender/tests/media2/test_reopen.py -- --reopen  # a fresh Blender: open, render

build    1. film: DAISY verse 1 as 96 frames at 24 fps from 26.0 s in the song: bake_canvas_playlist (voder_1939 ->
            bell_1961 at 27.9773 s) on the LED wall with spill, and an overlay panel in the post chain
            (chain_overlay, a Render Layers node of the overlay scene) that draws its film frame as a 10-bit code.
            Rendered out of order (60, 10, 49, 48); the code must read the frame each time. Then the same frame with
            motion blur on (shutter 0.5, 1 and 4 steps): a still wall must come through the shutter unchanged.
            Saved as out/reopen/reopen_film.blend.
         2. book: makeBook(gltf) (the janus GLB) opening, turning a leaf and closing; frames 64 and 41 rendered,
            saved as out/reopen/reopen_book.blend.
         3. atlas: make_atlas_screen with a bit-coded 30-tile atlas, once at 1.5x from frame 10 and looping at
            0.5x from frame 20, the tiles decoded from the renders against screen.js's rule.
--reopen opens both files in a fresh process and renders frames in a new order from the file alone: the HUD code
         and every pixel against the building session's renders.
Prints PASS/FAIL lines.
"""
import json
import math
import shutil
import sys
from pathlib import Path

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'media'))
import _stage as S  # noqa: E402
from eidoblend.media import book, canvas_scenes as cs, overlay, raster, screens  # noqa: E402

OUT = HERE / 'out'
WORK = OUT / 'reopen'
TL = OUT / 'daisy' / 'out' / 'daisy_timeline_upto_chorus2.json'
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
REOPEN = '--reopen' in argv
HUD = dict(x=-0.28, y=0.40, w=0.40, h=0.12)
NBITS = 10
FAILS = []


def check(ok, what):
    print(f"{'PASS' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        FAILS.append(what)


def still(sc, frame, path):
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


def rgb(p):
    return np.asarray(Image.open(p).convert('RGB')).astype(float)


def draw_code(c, value, w, h):
    """value as NBITS cells across the panel (MSB first): white = 1, black = 0, under a teal stripe."""
    d = c.draw
    c.clear('#000000')
    d.rectangle([0, 0, w, int(h * 0.18)], fill=raster.color('#27e0a0'))
    cw = w / NBITS
    for j in range(NBITS):
        if (value >> (NBITS - 1 - j)) & 1:
            d.rectangle([int(j * cw + cw * 0.15), int(h * 0.3), int((j + 1) * cw - cw * 0.15), int(h * 0.95)],
                        fill=(255, 255, 255, 255))


def read_code(a, x0, y0, x1, y1):
    """Decode NBITS cells inside the pixel rect of a grey image: (value, cell means)."""
    cw = (x1 - x0) / NBITS
    yc = int(round(y0 + (y1 - y0) * 0.62))
    means = []
    for j in range(NBITS):
        xc = int(round(x0 + (j + 0.5) * cw))
        means.append(float(a[yc - 1:yc + 2, xc - 1:xc + 2].mean()))
    lo, hi = min(means), max(means)
    thr = (lo + hi) / 2 if hi - lo > 40 else 128
    v = 0
    for m in means:
        v = (v << 1) | (1 if m > thr else 0)
    return v, [round(m) for m in means]


def hud_rect(W, H):
    return ((0.5 + HUD['x'] - HUD['w'] / 2) * W, (0.5 - HUD['y'] - HUD['h'] / 2) * H,
            (0.5 + HUD['x'] + HUD['w'] / 2) * W, (0.5 - HUD['y'] + HUD['h'] / 2) * H)


# ---------------------------------------------------------------------------------------------------- build
def build_film():
    W, H = 640, 360
    sc = S.fresh_scene(res=(W, H), samples=16, fps=24, frames=(1, 96))
    sc.name = 'film'
    t_start = 26.0
    sc['eido_frame0'] = 1 - round(t_start * 24)
    S.box(sc, 'floor', (14, 12, 0.04), (0, -3.0, -0.02), S.plain_material('floor', (0.05, 0.045, 0.04), 0.6))
    S.box(sc, 'drape', (14, 0.1, 6), (0, 0.6, 3), S.plain_material('drape', (0.012, 0.012, 0.014), 0.95))
    S.box(sc, 'cabinet', (4.92, 0.14, 2.12), (0, 0.09, 1.6), S.plain_material('cabinet', (0.02, 0.02, 0.022), 0.45, 0.6))
    S.box(sc, 'riser', (5.4, 1.4, 0.5), (0, -0.4, 0.25), S.plain_material('riser', (0.03, 0.03, 0.032), 0.7))
    pl = screens.bake_canvas_playlist(WORK / 'wall', (1, 96), {k: cs.DAISY_CUES[k] for k in ('voder_1939', 'bell_1961')},
                                      W=720, H=300, lyrics=TL, bpm=128, prefix='v1')
    want = 1 + math.ceil((cs.DAISY_CUES['bell_1961'] - t_start) * 24 - 1e-9)
    check(pl['spans'][1][1] == want, f"film: bell_1961 takes the wall at frame {pl['spans'][1][1]} (its cue -> {want})")
    wall = screens.make_screen(width=4.8, height=2.0, source=pl['first'], frames=(1, 96), name='verse_wall',
                               strength=1.25, spill=0.75)
    wall.obj.location = (0, 0.0, 1.6)
    S.area_light(sc, (0.5, -4.0, 4.5), (0, -1.6, 0.5), 45.0, size=2.0, color=(1.0, 0.86, 0.72), name='front_wash')
    S.camera(sc, (-0.9, -7.4, 1.55), (0.0, 0.0, 1.45), lens=40)
    ov = overlay.make_overlay_layer(sc, filter_size=0.0)
    f0 = sc['eido_frame0']

    def hud(c, t, w, h):
        draw_code(c, int(round(t * 24)) + f0, w, h)          # the film frame this drawing belongs to

    ov.panel(draw=hud, px=400, frames=(1, 96), name='frame_code', out_dir=WORK / 'hud', supersample=1, **HUD)
    overlay.chain_overlay(ov, sc)
    rect = hud_rect(W, H)
    for f in (60, 10, 49, 48):                                # out of order on purpose
        p = still(sc, f, WORK / f'session_f{f:03d}.png')
        v, means = read_code(rgb(p).mean(axis=-1), *rect)
        check(v == f, f'film in session, frame {f}: the HUD (chain_overlay) reads {v} {means}')
    # motion blur, shutter 0.5 centred on frame 60: the wall's image through the shutter. One time step shades the
    # frame's own drawing; four steps sit at 59.81, 59.94, 60.06, 60.19, so two show drawing 59 and two drawing 60
    # (a sequence shows floor(t)): what a camera filming a display through that shutter records
    f59 = rgb(still(sc, 59, WORK / 'session_f059.png'))
    f60 = rgb(WORK / 'session_f060.png')
    r = sc.render
    r.use_motion_blur, r.motion_blur_shutter, r.motion_blur_position = True, 0.5, 'CENTER'
    wall_px = (slice(110, 260), slice(130, 520))
    for steps, want, what in ((1, f60, 'drawing 60'), (4, (f59 + f60) / 2, 'the mean of drawings 59 and 60')):
        sc.eevee.motion_blur_steps = steps
        a = rgb(still(sc, 60, WORK / f'mblur_steps{steps}_f060.png'))
        d = np.abs(a[wall_px] - want[wall_px])
        d60 = np.abs(a[wall_px] - f60[wall_px]).mean()
        check(d.mean() < 1.5 and np.percentile(d, 99) < 14,
              f'motion blur ({steps} step{"s" if steps > 1 else ""}, shutter 0.5): the still wall shows {what} '
              f'(mean |diff| {d.mean():.2f}, p99 {np.percentile(d, 99):.1f}; against drawing 60 alone {d60:.2f}; '
              f'drawings 59 and 60 differ by {np.abs(f59 - f60)[wall_px].mean():.2f})')
    r.use_motion_blur = False
    bpy.ops.wm.save_as_mainfile(filepath=str(WORK / 'reopen_film.blend'))


def build_book():
    sc = S.fresh_scene(res=(640, 360), samples=16, fps=24, frames=(1, 72))
    sc.name = 'bookshot'
    sc.eevee.shadow_ray_count = 4
    sc.eevee.shadow_step_count = 12
    glb = S.ASSETS / 'models' / 'simulacra_and_simulators_book_janus_repligate_crimson_bookcloth_hardcover_readable_pages.glb'
    plan = book.schedule((1, 72), open=[(1, 0.0), (24, 1.0), (56, 1.0), (72, 0.0)], turns=[(32, 50)],
                         side=[(1, 'front'), (56, 'back')])
    b = book.make_book(WORK / 'book', plan, gltf=glb, spreads=sorted((S.ASSETS / 'book_spreads').glob('*.jpg')),
                       name='janus')
    S.box(sc, 'desk', (1.4, 0.9, 0.04), (0.05, 0.1, -0.02), S.plain_material('desk', (0.35, 0.3, 0.25), 0.6))
    b.root.rotation_euler.z = 0.12
    S.area_light(sc, (-0.6, -0.4, 0.75), (0, 0, 0), 30.0, size=0.7, color=(1.0, 0.93, 0.84), name='window')
    S.area_light(sc, (0.7, 0.3, 0.6), (0, 0, 0), 6.0, size=0.8, color=(0.8, 0.86, 1.0), name='fill')
    S.camera(sc, (0.05, -0.40, 0.38), (0.0, 0.0, 0.0), lens=35)
    for f in (64, 41):
        still(sc, f, WORK / f'session_book_f{f:03d}.png')
    bpy.ops.wm.save_as_mainfile(filepath=str(WORK / 'reopen_book.blend'))


def coded_atlas(path, cols=6, rows=5, fw=128, fh=72):
    im = Image.new('RGB', (cols * fw, rows * fh), (0, 0, 0))
    d = ImageDraw.Draw(im)
    for i in range(cols * rows):
        x0, y0 = (i % cols) * fw, (i // cols) * fh
        d.rectangle([x0, y0, x0 + fw - 1, y0 + int(fh * 0.15)], fill=(39, 224, 160))
        cw = fw / NBITS
        for j in range(NBITS):
            if (i >> (NBITS - 1 - j)) & 1:
                d.rectangle([int(x0 + j * cw + cw * 0.15), int(y0 + fh * 0.3), int(x0 + (j + 1) * cw - cw * 0.15),
                             int(y0 + fh * 0.95)], fill=(255, 255, 255))
    im.save(path, quality=95)
    info = {'cols': cols, 'rows': rows, 'totalFrames': cols * rows, 'fps': 12, 'frameWidth': fw, 'frameHeight': fh,
            'atlasWidth': cols * fw, 'atlasHeight': rows * fh}
    path.with_name(path.stem + '_info.json').write_text(json.dumps(info), encoding='utf-8')
    return info


def panel_rect(sc, obj):
    W, H = sc.render.resolution_x, sc.render.resolution_y
    uv = [world_to_camera_view(sc, sc.camera, obj.matrix_world @ v.co) for v in obj.data.vertices]
    return min(u.x * W for u in uv), min((1 - u.y) * H for u in uv), max(u.x * W for u in uv), max((1 - u.y) * H for u in uv)


def build_atlas():
    sc = S.fresh_scene(res=(640, 360), samples=8, fps=24, frames=(1, 60))
    jpg = WORK / 'coded_atlas.jpg'
    info = coded_atlas(jpg)
    once = screens.make_atlas_screen(jpg, info, width=1.2, start_frame=10, speed=1.5, loop=False,
                                     out_dir=WORK / 'atlas_once', name='atlas_once')
    once.obj.location = (-0.7, 0, 0)
    loop = screens.make_atlas_screen(jpg, info, width=1.2, start_frame=20, speed=0.5, loop=True,
                                     out_dir=WORK / 'atlas_loop', name='atlas_loop')
    loop.obj.location = (0.7, 0, 0)
    S.camera(sc, (0, -5.0, 0), (0, 0, 0), lens=50)
    sc.view_settings.view_transform = 'Standard'          # read the code cleanly
    r1, r2 = panel_rect(sc, once.obj), panel_rect(sc, loop.obj)
    n = info['totalFrames']
    bad = []
    for f in (1, 5, 9, 10, 11, 30, 49, 50, 55, 60):
        a = rgb(still(sc, f, WORK / f'atlas_f{f:03d}.png')).mean(axis=-1)
        v1, _ = read_code(a, r1[0], r1[1] + 0.3 * (r1[3] - r1[1]), r1[2], r1[3])
        v2, _ = read_code(a, r2[0], r2[1] + 0.3 * (r2[3] - r2[1]), r2[2], r2[3])
        w1 = screens.engine_movie_frame(f - 10, 24, 12, 1.5, n, False)
        w2 = screens.engine_movie_frame(f - 20, 24, 12, 0.5, n, True)
        print(f'[atlas] frame {f}: once {v1} (rule {w1}), loop {v2} (rule {w2})', flush=True)
        if (v1, v2) != (w1, w2):
            bad.append(f)
    check(not bad, f'atlas, decoded from 10 renders: once at 1.5x from frame 10 and looping at 0.5x from frame 20 '
                   f'follow screen.js\'s rule on every frame{"" if not bad else f" except {bad}"}')


# ---------------------------------------------------------------------------------------------------- reopen
def reopen():
    bpy.ops.wm.open_mainfile(filepath=str(WORK / 'reopen_film.blend'))
    sc = bpy.data.scenes['film']
    rect = hud_rect(sc.render.resolution_x, sc.render.resolution_y)
    for f in (10, 48, 49, 60):
        p = still(sc, f, WORK / f'reopened_f{f:03d}.png')
        a, b = rgb(p), rgb(WORK / f'session_f{f:03d}.png')
        d = np.abs(a - b)
        v, _ = read_code(a.mean(axis=-1), *rect)
        check(v == f and d.mean() < 1.0, f'reopened film, frame {f}: the HUD reads {v}; against the building '
                                         f'session mean |diff| {d.mean():.3f}, p99 {np.percentile(d, 99):.1f}')
    bpy.ops.wm.open_mainfile(filepath=str(WORK / 'reopen_book.blend'))
    sc = bpy.data.scenes['bookshot']
    for f in (41, 64):
        a, b = rgb(still(sc, f, WORK / f'reopened_book_f{f:03d}.png')), rgb(WORK / f'session_book_f{f:03d}.png')
        d = np.abs(a - b)
        check(d.mean() < 1.0, f'reopened book, frame {f}: against the building session mean |diff| {d.mean():.3f}, '
                              f'p99 {np.percentile(d, 99):.1f}')
    side = np.concatenate([rgb(WORK / 'reopened_f049.png'), rgb(WORK / 'reopened_book_f041.png')], axis=1)
    Image.fromarray(side.astype(np.uint8)).save(OUT / 'reopen_sheet.png')
    print(f'[sheet] {OUT / "reopen_sheet.png"}', flush=True)


def main():
    if REOPEN:
        reopen()
    else:
        if WORK.exists():
            shutil.rmtree(WORK)
        WORK.mkdir(parents=True)
        build_film()
        build_book()
        build_atlas()
    print(f'[test_reopen{" --reopen" if REOPEN else ""}] {"ALL OK" if not FAILS else f"{len(FAILS)} FAILED"}',
          flush=True)


main()

"""Probe: in-world screens in Blender 5.2 EEVEE (eidoblend.media.screens).

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/media/test_screens.py [--only mac,wall,av]
    (a GPU job; on a shared machine queue it with EIDO_GPU_WRAP: blender/tests/_where.py)

mac   the Macintosh 1984 GLB on a wooden desk; a Python-drawn 1-bit screen (Pillow, typed text, blinking cursor)
      taken over onto its own screen_crt mesh, inside the tube's raster window (mac1984.js's), under its glass
      -> 2 stills
wall  a 2.4 x 1 m wall panel playing the 1939 Voder era screen, baked from the engine's own canvas code in Deno,
      with the spill light keyed to the frames' mean colour, a stool and a plank floor in its light -> 2 stills,
      plus the room at frame 60 with the ceiling off, spill at gain 1 on and off
av    an ASCII panel (teletype reveal, cursor) beside two video screens made from a movie: one as a native movie
      image, one retimed to half speed -> 1 still; then numbered panels at frame 37 (expect 37 | 37 | 19)
hold  screens whose range starts mid-film (frames 10..20 of 1..30), at frames 5, 15 and 25: a drawn screen, a
      source sequence, a native movie, a half-speed retime and a looping 30 fps retime -> 3 stills; and an overlay
      panel over the same range, rendered 5..25 (it must exist only on 10..20)
spill the spill light: a 1.0 x 0.6 m screen (strength 1, spill 1) over a white floor, three frame colours; its
      power and colour from the frame, the floor it lights with the screen in view and out of view -> numbers
      (PASS / FAIL) and a contact sheet
playhead  the scene driving a video's playhead: a native movie frozen by set_frame, frame_map backwards and
      jumping to a cue, counter movies read at frames 20 and 37 -> screens_playhead_f020.png, _f037.png
Writes blender/tests/media/out/screens_*.png and prints what each probe checked.
"""
import math
import subprocess
import sys
from pathlib import Path

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _stage as S  # noqa: E402
from eidoblend.media import overlay, raster, screens  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ONLY = set(argv[argv.index('--only') + 1].split(',')) if '--only' in argv else {'mac', 'wall', 'av', 'hold', 'spill',
                                                                                'playhead'}
OUT = S.OUT
WORK = OUT / 'screens_work'


def counter_frames(d, n, label=str, prefix='c_', size=(640, 360), bg=(12, 20, 28)):
    """n numbered PNGs <prefix>0001.png … reading label(k), k = 1 … n."""
    d.mkdir(parents=True, exist_ok=True)
    big = raster.font('Anton', size[1] * 0.62)
    for k in range(1, n + 1):
        s = label(k)
        fnt = big if big.getlength(s) <= size[0] * 0.9 else raster.font(
            'Anton', size[1] * 0.62 * size[0] * 0.9 / big.getlength(s))
        im = Image.new('RGB', size, bg)
        ImageDraw.Draw(im).text((size[0] / 2, size[1] / 2), s, font=fnt, fill=(240, 236, 220), anchor='mm')
        im.save(d / f'{prefix}{k:04d}.png')
    return d


def counter_movie(path, n=72, fps=24):
    """An H.264 movie whose frame i (0-based) reads i + 1."""
    d = counter_frames(path.parent / (path.stem + '_frames'), n)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', str(fps), '-start_number', '1', '-i',
                    str(d / 'c_%04d.png'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '12', str(path)],
                   check=True)
    return path


def mac_draw(c, t, w, h):
    """A 1-bit Macintosh desktop: menu bar, a window, 'Hello, I am Macintosh.' typed in, a blinking I-beam."""
    yy, xx = np.mgrid[0:h, 0:w]
    c.image.paste(Image.fromarray(np.where((xx + yy) % 2 == 0, 255, 0).astype(np.uint8), 'L').convert('RGBA'))
    d = ImageDraw.Draw(c.image)
    W, B = (255, 255, 255, 255), (0, 0, 0, 255)
    d.rectangle([0, 0, w - 1, 19], fill=W)
    d.line([(0, 19), (w, 19)], fill=B)
    mf = raster.font('Silkscreen-Bold', 10)
    d.text((12, 5), '@   File   Edit   View   Special', font=mf, fill=B)
    x0, y0, x1, y1 = 58, 48, 454, 292
    d.rectangle([x0 + 3, y0 + 3, x1 + 3, y1 + 3], fill=B)
    d.rectangle([x0, y0, x1, y1], fill=W, outline=B)
    for yl in range(y0 + 4, y0 + 17, 2):
        d.line([(x0 + 2, yl), (x1 - 2, yl)], fill=B)
    d.line([(x0, y0 + 19), (x1, y0 + 19)], fill=B)
    title = 'hello'
    tw = mf.getlength(title)
    cx = (x0 + x1) / 2
    d.rectangle([cx - tw / 2 - 8, y0 + 2, cx + tw / 2 + 8, y0 + 17], fill=W)
    d.text((cx, y0 + 10), title, font=mf, fill=B, anchor='mm')
    d.rectangle([x0 + 9, y0 + 4, x0 + 21, y0 + 15], fill=W, outline=B)
    msg = 'Hello, I am Macintosh.'
    n = max(0, min(len(msg), int((t - 0.25) * 11)))
    tf = raster.font('VT323', 34)
    d.text((x0 + 22, y0 + 46), msg[:n], font=tf, fill=B)
    cxr = x0 + 22 + tf.getlength(msg[:n]) + 3
    if int(math.floor(t * 2.2)) % 2 == 0:
        d.line([(cxr, y0 + 50), (cxr, y0 + 78)], fill=B, width=2)
    sub = raster.font('VT323', 22)
    d.text((x0 + 22, y0 + 100), 'MacinTalk  1984', font=sub, fill=B)
    d.rectangle([x0 + 22, y1 - 46, x0 + 122, y1 - 18], outline=B, width=2)
    d.text((x0 + 72, y1 - 32), 'Speak', font=sub, fill=B, anchor='mm')
    g = c.image.convert('L').point(lambda v: 255 if v >= 128 else 0)
    tint = Image.new('RGBA', g.size, (238, 243, 255, 255))           # the tube's slightly blue white
    c.image = Image.composite(tint, Image.new('RGBA', g.size, (0, 0, 0, 255)), g)


def probe_mac():
    sc = S.fresh_scene(frames=(1, 48))
    desk = S.box(sc, 'desk', (1.6, 0.9, 0.04), (0, 0.05, -0.02),
                 S.pbr_material('desk_wood', S.cached('textures', 'PaintedWood009C_2k'), scale=1.6), uv_scale=1.0)
    wall = S.box(sc, 'wall', (3.0, 0.05, 2.0), (0, 0.55, 0.8), S.plain_material('wall', (0.32, 0.30, 0.27), 0.85))
    objs = S.import_gltf(S.ASSETS / 'models' / 'voice_machines' / 'mac1984.glb')
    tube = next(o for o in objs if o.name.startswith('screen_crt'))
    scr = screens.make_screen(px=512, width=0.1806, height=0.1207, draw=mac_draw, frames=(1, 48), fps=0,
                              out_dir=WORK / 'mac', name='mac_screen', standalone=False, interpolation='Closest',
                              strength=2.0, spill=0.6)
    # mac1984.js's window: the 512 x 342 raster (RW x RH) centred in the TW x TH tube, raised 0.004 in v. Its UVs
    # are flipUV'd glTF UVs, which is what Blender's glTF importer gives, so the window carries over unchanged.
    TW, TH, RW, RH = 0.200, 0.152, 0.1806, 0.1207
    u0, v0 = (TW - RW) / 2 / TW, (TH - RH) / 2 / TH
    window = (u0, v0 + 0.004, 1 - u0, 1 - v0 + 0.004)
    scr.apply_to(tube, window=window, glass=True)
    print('[mac] raster window', tuple(round(v, 5) for v in window))
    S.area_light(sc, (-0.7, -0.6, 0.9), (0, 0, 0.15), 22.0, size=0.6, color=(1.0, 0.86, 0.70), name='lamp')
    S.area_light(sc, (0.9, -0.9, 1.4), (0, 0, 0.2), 6.0, size=1.2, color=(0.75, 0.82, 1.0), name='fill')
    S.camera(sc, (0.42, -0.98, 0.42), (0.0, -0.08, 0.15), lens=40)
    print('[mac] screen image', scr.image.name, scr.image.source, 'frames', scr.frame_start, '+', scr.frame_duration,
          '| material', scr.material.name, '| spill', scr.light.name if scr.light else None)
    for f in (6, 40):
        S.render_still(sc, f, OUT / f'screens_mac_f{f:03d}.png')


def probe_wall():
    sc = S.fresh_scene(frames=(1, 72))
    floor = S.box(sc, 'floor', (8, 8, 0.04), (0, -2, -0.02),
                  S.pbr_material('planks', S.cached('textures', 'Planks039_2k'), scale=0.5))
    S.box(sc, 'backwall', (8, 0.1, 4), (0, 0.15, 2), S.plain_material('backwall', (0.18, 0.18, 0.19), 0.8))
    info = screens.bake_canvas_scene(WORK / 'voder', (1, 72), scene_name='voder_1939',
                                     modules=['eidoverse/graphics/era_screens_1939_1984.js'], t0=0.0, W=1440, H=600)
    print('[wall] deno bake', info)
    scr = screens.make_screen(width=2.4, height=1.0, source=info['first'], frames=(1, 72), name='voder_wall',
                              strength=1.6, spill=1.0)
    scr.obj.location = (0, 0.05, 1.65)
    stool = S.cached('models', 'wooden_stool_01_1k')
    if stool:
        objs = S.import_gltf(stool / 'wooden_stool_01_embedded.gltf')
        for o in objs:
            if o.parent is None:
                o.location = (0.7, -1.3, 0)
    S.area_light(sc, (0, -2.5, 3.6), (0, -1.5, 0), 60.0, size=1.5, color=(1.0, 0.9, 0.8), name='ceiling')
    sc.view_settings.exposure = 1.0
    S.camera(sc, (-1.5, -4.6, 1.45), (0.1, 0, 1.25), lens=32)
    lm = scr.light.matrix_world
    ld = scr.light.data
    sc.frame_set(60)
    print('[wall] image', scr.image.name, scr.image.source, scr.frame_start, '+', scr.frame_duration,
          '| spill keys', len(scr.means), '| spill shines along', tuple(round(v, 3) for v in -lm.col[2].xyz),
          '(the panel faces -Y)', 'size', round(ld.size, 3), round(ld.size_y, 3), '| cutoff', ld.use_custom_distance,
          ld.cutoff_distance, '| at frame 60:', round(ld.energy, 3), 'W', tuple(round(c, 3) for c in ld.color))
    for f in (12, 60):
        S.render_still(sc, f, OUT / f'screens_wall_f{f:03d}.png')
    # the room lit by the screen alone (the ceiling off), spill at gain 1 on and off: what the spill adds
    sc.objects['ceiling'].hide_render = True
    S.render_still(sc, 60, OUT / 'screens_wall_spill_only_f060.png')
    scr.light.hide_render = True
    S.render_still(sc, 60, OUT / 'screens_wall_no_spill_f060.png')


def probe_av():
    sc = S.fresh_scene(frames=(1, 72))
    S.box(sc, 'floor', (8, 8, 0.04), (0, -2, -0.02), S.pbr_material('planks', S.cached('textures', 'Planks039_2k'), 0.5))
    S.box(sc, 'backwall', (8, 0.1, 4), (0, 0.15, 2), S.plain_material('backwall', (0.18, 0.18, 0.19), 0.8))
    seq = WORK / 'voder'
    if not (seq / 'voder_1939_0001.png').exists():
        screens.bake_canvas_scene(seq, (1, 72), scene_name='voder_1939',
                                  modules=['eidoverse/graphics/era_screens_1939_1984.js'], t0=0.0, W=1440, H=600)
    mp4 = WORK / 'voder.mp4'
    # -start_number 1: make_screen wrote voder_1939_0000.png (the hold) beside the bake, and ffmpeg's image2
    # reader starts at file 0 by default (it made a 73-frame movie of the 72 frames, 11-07)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', '24', '-start_number', '1', '-i',
                    str(seq / 'voder_1939_%04d.png'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '16', str(mp4)],
                   check=True)
    asc = screens.make_ascii_panel('EIDOVERSE / BLENDER EDITION\n> import eidoblend.media\n> make_screen(...)\nREADY.',
                                   width=1.1, reveal=24, frames=(1, 72), out_dir=WORK / 'ascii', name='ascii',
                                   font='VT323', strength=1.4)
    asc.obj.location = (-1.35, 0.05, 1.5)
    v1 = screens.make_video_screen(mp4, width=1.2, start_frame=1, name='video_native', strength=1.4)
    v1.obj.location = (0.0, 0.05, 1.5)
    v2 = screens.make_video_screen(mp4, width=1.2, start_frame=1, speed=0.5, name='video_half',
                                   out_dir=WORK / 'video_half', strength=1.4)
    v2.obj.location = (1.35, 0.05, 1.5)
    S.area_light(sc, (0, -2.5, 3.6), (0, -1.5, 0), 20.0, size=1.5, name='ceiling')
    S.camera(sc, (0, -4.4, 1.5), (0, 0, 1.4), lens=35)
    print('[av] ascii', asc.image.source, asc.frame_duration, '| native', v1.image.source, v1.frame_duration,
          v1.image.get('eido_cyclic'), '| half', v2.image.source, v2.frame_duration)
    S.render_still(sc, 48, OUT / 'screens_av_f048.png')

    # frame-exactness: every panel shows a frame number; at scene frame 37 a drawn panel and a native movie must
    # read 37, the half-speed movie 19 (film frame k shows movie frame floor((k - 1) / 2) + 1)
    for o in list(sc.objects):
        if o.name.startswith(('ascii', 'video_')):
            bpy.data.objects.remove(o)
    cmp4 = counter_movie(WORK / 'counter.mp4', 72, 24)

    def counter(c, t, w, h):
        c.clear((12, 20, 28))
        c.draw.text((w / 2, h / 2), str(round(t * 24) + 1), font=raster.font('Anton', h * 0.83), fill=(240, 236, 220),
                    anchor='mm')
    p1 = screens.make_screen(width=1.2, height=0.675, px=640, draw=counter, frames=(1, 72), out_dir=WORK / 'cdraw',
                             name='idx_drawn')
    p2 = screens.make_video_screen(cmp4, width=1.2, start_frame=1, name='idx_native')
    p3 = screens.make_video_screen(cmp4, width=1.2, start_frame=1, speed=0.5, name='idx_half', out_dir=WORK / 'chalf')
    for p, x in ((p1, -1.35), (p2, 0.0), (p3, 1.35)):
        p.obj.location = (x, 0.05, 1.5)
    S.render_still(sc, 37, OUT / 'screens_index_f037.png')
    print('[av] index probe at frame 37: expect drawn 37 | native movie 37 | half speed 19')


def probe_hold():
    """Screens whose range starts mid-film: before it the first frame holds (a looping movie wraps), after it the
    last holds. Top row: drawn (frames 10..20), source sequence (files 1..11 at 10..20), native 24 fps movie (from
    10, no loop); bottom row: the same movie at half speed (no loop), a 30 fps movie at speed 1 looping from 10."""
    sc = S.fresh_scene(frames=(1, 30))
    S.box(sc, 'backwall', (8, 0.1, 5), (0, 0.15, 1.6), S.plain_material('backwall', (0.18, 0.18, 0.19), 0.8))
    H = WORK / 'hold'

    def drawn(c, t, w, h):
        c.clear((44, 18, 24))
        c.draw.text((w / 2, h / 2), str(round(t * 24) + 1), font=raster.font('Anton', h * 0.62),
                    fill=(240, 236, 220), anchor='mm')
    m24 = counter_movie(H / 'counter24.mp4', 72, 24)
    m30 = counter_movie(H / 'counter30.mp4', 72, 30)
    m12 = counter_movie(H / 'counter12.mp4', 12, 24)
    src = counter_frames(H / 'src', 30, label=lambda k: f'file {k}', prefix='s_', bg=(16, 34, 52))
    panels = [
        (screens.make_screen(width=1.2, height=0.675, px=640, draw=drawn, frames=(10, 20), out_dir=H / 'drawn',
                             name='hold_drawn'), (-1.35, 2.15), ('10', '15', '20')),
        (screens.make_screen(width=1.2, height=0.675, source=src, frames=(10, 20), name='hold_source'),
         (0.0, 2.15), ('file 1', 'file 6', 'file 11')),
        (screens.make_video_screen(m24, width=1.2, start_frame=10, loop=False, name='hold_native'),
         (1.35, 2.15), ('1', '6', '16')),
        (screens.make_video_screen(m24, width=1.2, start_frame=10, speed=0.5, loop=False, out_dir=H / 'half',
                                   name='hold_half'), (-0.675, 1.35), ('1', '3', '8')),
        (screens.make_video_screen(m30, width=1.2, start_frame=10, loop=True, out_dir=H / 'loop30',
                                   name='hold_loop30'), (0.675, 1.35), ('66', '7', '19')),
        # a native movie of 12 frames looping from frame 10: it wraps before (k = -5 -> 7) and after (k = 15 -> 3)
        (screens.make_video_screen(m12, width=1.2, start_frame=10, loop=True, name='hold_loop12'),
         (2.025, 1.35), ('8', '6', '4')),
    ]
    for scr, (x, z), _ in panels:
        scr.obj.location = (x, 0.05, z)
        im = scr.image
        print(f'[hold] {scr.name}: {im.source} start {scr.frame_start} + {scr.frame_duration} offset '
              f'{im.get("eido_frame_offset")} cyclic {im.get("eido_cyclic")} | {Path(bpy.path.abspath(im.filepath)).name}'
              + (f' (Blender\'s own frame_duration {im.frame_duration})' if im.source == 'MOVIE' else ''))
    hold_file = H / 'drawn' / 'hold_drawn_0000.png'
    print('[hold] hold file', hold_file.name, 'exists', hold_file.exists(), 'marked', screens._is_hold(hold_file))
    S.area_light(sc, (0, -2.5, 3.6), (0, -1.5, 0), 20.0, size=1.5, name='ceiling')
    cam = S.camera(sc, (0.34, -3.0, 1.75), (0.34, 0, 1.75), lens=50)
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = 4.9
    for i, f in enumerate((5, 15, 25)):
        S.render_still(sc, f, OUT / f'screens_hold_f{f:03d}.png')
        print(f'[hold] frame {f}: expect', ' | '.join(p[2][i] for p in panels))

    # an overlay lower third over frames 10..20: a graphic on the frame exists only in its range
    ov = overlay.make_overlay_layer(sc)

    def lower_third(c, t, w, h):
        c.clear((0, 0, 0, 0))
        c.draw.rectangle([0, 0, int(w * 0.06), h], fill=raster.color('#27e0a0'))
        c.draw.rectangle([int(w * 0.06), 0, w, h], fill=(16, 24, 32, 222))
        raster.draw_text_fit(c, 'HOLD 10..20', x=w * 0.1, y=h * 0.15, max_width=w * 0.8, max_height=h * 0.6,
                             font='Anton', px=h * 0.5, align='left', fill='#ffffff')
    bar = ov.panel(draw=lower_third, x=-0.2, y=-0.33, w=0.5, h=0.12, px=800, frames=(10, 20), out_dir=H / 'lt',
                   name='hold_lt')
    d = overlay.render_overlay(ov, H / 'ov', frames=(5, 25))
    seen = []
    for f in range(5, 26):
        a = np.asarray(Image.open(Path(d) / f'ov_{f:04d}.png').convert('RGBA'))[..., 3]
        if a.max() > 0:
            seen.append(f)
    print(f'[hold] overlay panel {bar.name}: drawn on frames {seen[0] if seen else None}..'
          f'{seen[-1] if seen else None} ({len(seen)} frames; expect 10..20, 11 frames)')
    for f in (5, 15, 25):
        Image.open(Path(d) / f'ov_{f:04d}.png').save(OUT / f'screens_hold_overlay_f{f:03d}.png')


def probe_playhead():
    """The scene drives the playhead (makeVideoScreen's setFrame): three panels of a counter movie (movie frame i
    reads i + 1), rendered at frames 20 and 37: a native movie frozen by set_frame((30, 45), 4), frame_map playing
    it backwards [(1, 71), (72, 0)], and frame_map jumping to frame 50 on a cue at film frame 30 (a function)."""
    sc = S.fresh_scene(frames=(1, 72))
    S.box(sc, 'backwall', (8, 0.1, 5), (0, 0.15, 1.6), S.plain_material('backwall', (0.18, 0.18, 0.19), 0.8))
    P = WORK / 'playhead'
    m24 = counter_movie(P / 'counter24.mp4', 72, 24)
    nat = screens.make_video_screen(m24, width=1.2, start_frame=1, name='ph_native')
    nat.set_frame((30, 45), 4)
    rev = screens.make_video_screen(m24, width=1.2, frame_map=[(1, 71), (72, 0)], out_dir=P / 'reverse',
                                    name='ph_reverse')
    cue = screens.make_video_screen(m24, width=1.2, frame_map=lambda f: f - 1 if f < 30 else 50 + (f - 30),
                                    out_dir=P / 'cue', name='ph_cue')
    for scr, x in ((nat, -1.35), (rev, 0.0), (cue, 1.35)):
        scr.obj.location = (x, 0.05, 1.75)
    S.area_light(sc, (0, -2.5, 3.6), (0, -1.5, 0), 20.0, size=1.5, name='ceiling')
    cam = S.camera(sc, (0.0, -3.0, 1.75), (0.0, 0, 1.75), lens=50)
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = 4.2
    for f, want in ((20, '20 | 53 | 20'), (37, '5 | 36 | 58')):
        S.render_still(sc, f, OUT / f'screens_playhead_f{f:03d}.png')
        print(f'[playhead] frame {f}: expect native set_frame | frame_map reverse | frame_map cue = {want}')


def _render(sc, path, exr=True):
    """Render a still: an EXR read back as scene-linear RGB (rows top-down), or a display PNG."""
    r = sc.render
    r.image_settings.media_type = 'IMAGE'
    r.image_settings.file_format = 'OPEN_EXR' if exr else 'PNG'
    r.image_settings.color_mode = 'RGB'
    r.image_settings.color_depth = '32' if exr else '8'
    r.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    if not Path(path).exists():
        raise RuntimeError(f'render did not write {path}')
    if not exr:
        return None
    im = bpy.data.images.load(str(path), check_existing=False)
    w, h = im.size
    px = np.empty(w * h * 4, dtype=np.float32)
    im.pixels.foreach_get(px)
    bpy.data.images.remove(im)
    return px.reshape(h, w, 4)[::-1, :, :3]


def probe_spill():
    """The spill light: a 1.0 x 0.6 m screen (strength 1, spill 1) over a white floor in a dark world, three frame
    colours. Its power is a Lambertian panel's (pi x area x the display's radiance) and its colour the frame's mean;
    in EEVEE the floor patch in front of the screen (x -0.4..0.4, y -1.0..-0.4), seen from camera A (the screen in
    view) and camera B (straight down, the screen out of view), takes the screen's colour from the spill light, and
    keeps only what fast GI gathers from the panel's emission without it."""
    res = (480, 270)
    W = WORK / 'spill'
    W.mkdir(parents=True, exist_ok=True)
    sheet_rows = []
    for tag, hexcol in (('white', '#ffffff'), ('blue', '#2050ff'), ('orange', '#ff8a2a')):
        sc = S.fresh_scene(res=res, frames=(1, 1))
        sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.0
        S.box(sc, 'floor', (6, 6, 0.02), (0, -1.5, -0.01), S.plain_material('floor', (0.8, 0.8, 0.8), 1.0))
        scr = screens.make_screen(width=1.0, height=0.6, px=64, draw=lambda c, t, w, h, col=hexcol: c.clear(col),
                                  frames=(1, 1), out_dir=W / tag, name=f'spill_{tag}', strength=1.0, spill=1.0)
        scr.obj.location = (0, 0, 0.8)
        lt = scr.light
        m = np.asarray(scr.means[0], np.float64)
        want_w = math.pi * lt.data.size * lt.data.size_y * float(m.max())
        want_c = m / max(float(m.max()), 1e-9)
        ok = abs(lt.data.energy - want_w) <= 1e-3 * want_w and np.allclose(lt.data.color, want_c, atol=1e-3)
        print(f'[spill] {"PASS" if ok else "FAIL"} {tag} {hexcol}: frame mean linear {np.round(m, 4).tolist()} -> '
              f'light {lt.data.energy:.4f} W (pi x area x radiance: {want_w:.4f}), colour '
              f'{tuple(round(c, 3) for c in lt.data.color)}, cutoff {lt.data.cutoff_distance} m '
              f'(custom {lt.data.use_custom_distance})')
        cams = {'A': S.camera(sc, (1.7, -2.6, 1.4), (0, -0.6, 0.35), lens=32, name='camA'),
                'B': S.camera(sc, (0, -0.7, 2.0), (0, -0.66, 0), lens=35, name='camB')}
        bpy.context.view_layer.update()
        row = []
        for cname, cam in cams.items():
            sc.camera = cam
            pts = [world_to_camera_view(sc, cam, Vector((x, y, 0))) for x in (-0.4, 0.4) for y in (-1.0, -0.4)]
            xs, ys = [p.x * res[0] for p in pts], [(1 - p.y) * res[1] for p in pts]
            x0, y0, x1, y1 = int(min(xs)) + 3, int(min(ys)) + 3, int(max(xs)) - 3, int(max(ys)) - 3

            def patch(a):
                return a[y0:y1, x0:x1].reshape(-1, 3).mean(axis=0)
            lt.hide_render = True
            off = patch(_render(sc, W / f'{tag}_{cname}_no_spill.exr'))
            lt.hide_render = False
            on = patch(_render(sc, W / f'{tag}_{cname}_spill.exr'))
            _render(sc, W / f'{tag}_{cname}_spill.png', exr=False)
            hue = (on - off) / max(float((on - off).max()), 1e-9)
            ok = float((on - off).max()) > 0 and np.allclose(hue, want_c, atol=0.08)
            print(f'[spill] {"PASS" if ok else "FAIL"} {tag}, camera {cname} '
                  f'({"screen in view" if cname == "A" else "screen out of view"}): floor patch linear '
                  f'{np.round(off, 5).tolist()} without the spill -> {np.round(on, 5).tolist()} with it; the spill\'s '
                  f'light in the screen\'s colour {np.round(hue, 3).tolist()}')
            row.append(W / f'{tag}_{cname}_spill.png')
        sheet_rows.append((tag, row))
    # contact sheet: per colour, camera B | camera A
    tw, th = res
    sheet = Image.new('RGB', (tw * 2, (th + 22) * len(sheet_rows) + 22), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    f = raster.font('Share Tech Mono', 16)
    order = (1, 0)
    for j, name in enumerate(('B: the screen out of view', 'A: the screen in view')):
        d.text((j * tw + 6, 3), name, font=f, fill=(230, 230, 230))
    for i, (tag, row) in enumerate(sheet_rows):
        y = 22 + i * (th + 22)
        d.text((6, y + 2), tag, font=f, fill=(230, 230, 230))
        for j, k in enumerate(order):
            sheet.paste(Image.open(row[k]).convert('RGB'), (j * tw, y + 22))
    sheet.save(OUT / 'screens_spill.png')
    print('[spill] contact sheet', OUT / 'screens_spill.png')


if 'mac' in ONLY:
    probe_mac()
if 'wall' in ONLY:
    probe_wall()
if 'av' in ONLY:
    probe_av()
if 'hold' in ONLY:
    probe_hold()
if 'spill' in ONLY:
    probe_spill()
if 'playhead' in ONLY:
    probe_playhead()
print('[test_screens] done', sorted(ONLY))

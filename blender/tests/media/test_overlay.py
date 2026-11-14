"""Probe: graphics on the frame (eidoblend.media.overlay): the overlay layer, subtitles, the edit scene, sound.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/media/test_overlay.py
    (a GPU job; on a shared machine queue it with EIDO_GPU_WRAP: blender/tests/_where.py)

1. a sound-only sequencer on the film scene must leave the 3D render in place (Blender renders the sequencer
   instead of the scene as soon as it holds a picture strip);
2. the film (the Voder wall, AgX) rendered to H.264 as the lead's films are;
3. a lower third drawn in the overlay scene (view Standard, transparent film), rendered to RGBA PNGs;
4. the edit scene: film + overlay ALPHA_OVER + two subtitle styles (TEXT strips) + a page-turn sound, rendered to
   PNG frames (measured: the solid ink must come back as the authored hex) and to an MP4 with AAC (ffprobe).
Stills: out/overlay_edit_f008.png, out/overlay_edit_f020.png; movie: out/overlay_edit.mp4.
"""
import json
import subprocess
import sys
from pathlib import Path

import bpy
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _stage as S  # noqa: E402
from eidoblend.media import overlay, raster, screens  # noqa: E402

OUT = S.OUT
WORK = OUT / 'overlay_work'
WORK.mkdir(parents=True, exist_ok=True)
WAV = S.ASSETS / 'book_sfx' / 'page_turn.wav'

# ---- the film scene: the Voder wall
sc = S.fresh_scene(frames=(1, 24))
sc.name = 'film'
S.box(sc, 'floor', (8, 8, 0.04), (0, -2, -0.02), S.pbr_material('planks', S.cached('textures', 'Planks039_2k'), 0.5))
S.box(sc, 'backwall', (8, 0.1, 4), (0, 0.15, 2), S.plain_material('backwall', (0.18, 0.18, 0.19), 0.8))
seq = OUT / 'screens_work' / 'voder'
if not (seq / 'voder_1939_0024.png').exists():
    screens.bake_canvas_scene(seq, (1, 72), scene_name='voder_1939',
                              modules=['eidoverse/graphics/era_screens_1939_1984.js'], t0=0.0, W=1440, H=600)
scr = screens.make_screen(width=2.4, height=1.0, source=seq / 'voder_1939_0001.png', frames=(1, 72), name='voder_wall',
                          strength=1.6, spill=1.0)
scr.obj.location = (0, 0.05, 1.65)
S.area_light(sc, (0, -2.5, 3.6), (0, -1.5, 0), 60.0, size=1.5, color=(1.0, 0.9, 0.8), name='ceiling')
sc.view_settings.exposure = 1.0
S.camera(sc, (-1.5, -4.6, 1.45), (0.1, 0, 1.25), lens=32)

# 1. a sound-only sequencer leaves the 3D render in place
sc.sequence_editor_create()
sc.sequence_editor.strips.new_sound(name='sfx', filepath=str(WAV), channel=1, frame_start=6)
p = S.render_still(sc, 12, WORK / 'film_with_sound_strip_f012.png')
im = Image.open(p).convert('RGB')
mean = sum(im.resize((1, 1), Image.Resampling.BOX).getpixel((0, 0))) / 3
print(f'[1] film scene with only a sound strip renders the 3D scene: mean {mean:.1f} -> {"OK" if mean > 20 else "FAIL"}')
sc.sequence_editor_clear()

# 2. the film to H.264 (video only, as render_h264.py)
r = sc.render
r.image_settings.media_type = 'VIDEO'
r.image_settings.file_format = 'FFMPEG'
r.ffmpeg.format, r.ffmpeg.codec = 'MPEG4', 'H264'
r.ffmpeg.constant_rate_factor = 'PERC_LOSSLESS'
r.ffmpeg.audio_codec = 'NONE'
r.use_file_extension = False
r.filepath = str(WORK / 'film.mp4')
bpy.ops.render.render(animation=True, scene=sc.name)
print('[2] film', (WORK / 'film.mp4').exists(), (WORK / 'film.mp4').stat().st_size)

# 3. the overlay: a lower third (a solid teal block, a slate plate, the name and role)
TEAL, GOLD, SLATE = '#27e0a0', '#e6b85c', (16, 24, 32, 222)
ov = overlay.make_overlay_layer(sc)


def lower_third(c, t, w, h):
    c.clear((0, 0, 0, 0))
    k = min(1.0, max(0.0, t / 0.3))                       # slides open over 0.3 s
    d = c.draw
    d.rectangle([0, 0, int(w * 0.06), h], fill=raster.color(TEAL))
    d.rectangle([int(w * 0.06), 0, int(w * (0.06 + 0.94 * k)), h], fill=SLATE)
    if k > 0.6:
        raster.draw_text_fit(c, 'CLAUDE', x=w * 0.1, y=h * 0.12, max_width=w * 0.5, max_height=h * 0.5, font='Anton',
                             px=h * 0.48, align='left', fill='#ffffff')
        raster.draw_text_fit(c, 'THE LEAD  /  EIDOVERSE', x=w * 0.1, y=h * 0.62, max_width=w * 0.85,
                             max_height=h * 0.3, font='Share Tech Mono', px=h * 0.24, align='left', fill=GOLD)


bar = ov.panel(draw=lower_third, x=-0.25, y=-0.33, w=0.42, h=0.1, px=1000, frames=(1, 24), out_dir=WORK / 'lt',
               name='lower_third')
ovdir = overlay.render_overlay(ov, WORK / 'ov')
print('[3] overlay frames', len(list(ovdir.glob('ov_*.png'))), 'half extents at z=-1', ov.half_w, ov.half_h)

# 4. the edit scene
edit = overlay.make_edit_scene(film=WORK / 'film.mp4', overlays=[ovdir], sounds=[(WAV, 6, 0.8)], like=sc)
overlay.add_subtitles(edit, [('Hello, I am Macintosh.', 0.0, 0.5)], channel=6, font='Share Tech Mono', size=0.055,
                      color='#ffffff', outline='#000000')
overlay.add_subtitles(edit, [('THE VODER, 1939', 0.5, 1.0)], channel=7, font='Anton', size=0.06, color='#ffd400',
                      outline=None, box='#101418', box_margin=0.01)
pngdir = overlay.render_edit(edit, WORK / 'edit_png', video=False)
mp4 = overlay.render_edit(edit, OUT / 'overlay_edit.mp4', video=True)
for f in (8, 20):
    Image.open(pngdir / f'edit_{f:04d}.png').save(OUT / f'overlay_edit_f{f:03d}.png')

# measurements: the solid ink against the authored values
W, H = sc.render.resolution_x, sc.render.resolution_y
im8 = Image.open(pngdir / 'edit_0008.png').convert('RGB')
im20 = Image.open(pngdir / 'edit_0020.png').convert('RGB')
cx, cy = (0.5 - 0.25) * W, (0.5 + 0.33) * H                # the lower third's centre in pixels
x_teal = int(cx - 0.21 * W + 0.03 * 0.42 * W)
got = im8.getpixel((x_teal, int(cy)))
print(f'[4] lower-third teal at ({x_teal},{int(cy)}): {got} want {raster.color(TEAL)[:3]}')


def dominant(im, box, near, tol=40):
    """The most common colour within tol of ``near`` inside box."""
    import numpy as np
    px = np.asarray(im.crop(box)).reshape(-1, 3).astype(int)
    px = px[(np.abs(px - np.array(near)) <= tol).all(axis=1)]
    if not len(px):
        return (None, 0)
    cols, n = np.unique(px, axis=0, return_counts=True)
    i = int(n.argmax())
    return (tuple(int(v) for v in cols[i]), int(n[i]))


sub_box = (int(W * 0.47), int(H * 0.80), int(W * 0.75), H)       # the subtitles only (the lower third ends at 0.46 W)
print('[4] subtitle white (frame 8):', dominant(im8, sub_box, (255, 255, 255)), 'want (255, 255, 255)')
print('[4] subtitle yellow (frame 20):', dominant(im20, sub_box, (255, 212, 0)), 'want (255, 212, 0)')
print('[4] subtitle box (frame 20):', dominant(im20, sub_box, (16, 20, 24), tol=12), 'want (16, 20, 24)')
pr = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,codec_name,width,height,r_frame_rate,'
                     'sample_rate,channels', '-of', 'json', str(mp4)], capture_output=True, text=True)
print('[4] mp4 streams', json.dumps(json.loads(pr.stdout)['streams']))
print('[test_overlay] done')

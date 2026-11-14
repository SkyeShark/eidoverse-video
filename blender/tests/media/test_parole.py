"""Probe: parole in liberta in Blender (eidoblend.media.parole) over a film, through the overlay layer and edit scene.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/media/test_parole.py
    (a GPU job; on a shared machine queue it with EIDO_GPU_WRAP: blender/tests/_where.py)

A title thrown in ("UNKNOWN FORCE", rows), then the first chorus line "I'm the unknown force" with its default
pre-heard guesses (the camps' answers, struck through as she sings), over 4 s of the Voder wall film. Stills of the
edit at frames 14, 44, 62, 80 -> out/parole_edit_f0NN.png, and the exported atlases beside them for comparison.
"""
import shutil
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _stage as S  # noqa: E402
from eidoblend.media import overlay, parole, screens  # noqa: E402

OUT = S.OUT
WORK = OUT / 'parole_work'
WORK.mkdir(parents=True, exist_ok=True)

# the film: the Voder wall, 96 frames
sc = S.fresh_scene(frames=(1, 96), samples=8)
sc.name = 'film'
S.box(sc, 'floor', (8, 8, 0.04), (0, -2, -0.02), S.pbr_material('planks', S.cached('textures', 'Planks039_2k'), 0.5))
S.box(sc, 'backwall', (8, 0.1, 4), (0, 0.15, 2), S.plain_material('backwall', (0.18, 0.18, 0.19), 0.8))
seq = WORK / 'voder'
info = screens.bake_canvas_scene(seq, (1, 96), scene_name='voder_1939',
                                 modules=['eidoverse/graphics/era_screens_1939_1984.js'], t0=0.0, W=1440, H=600)
scr = screens.make_screen(width=2.4, height=1.0, source=info['first'], frames=(1, 96), name='voder_wall',
                          strength=1.6, spill=1.0)
scr.obj.location = (0, 0.05, 1.65)
S.area_light(sc, (0, -2.5, 3.6), (0, -1.5, 0), 60.0, size=1.5, color=(1.0, 0.9, 0.8), name='ceiling')
sc.view_settings.exposure = 1.0
S.camera(sc, (-1.5, -4.6, 1.45), (0.1, 0, 1.25), lens=32)
r = sc.render
r.image_settings.media_type = 'VIDEO'
r.image_settings.file_format = 'FFMPEG'
r.ffmpeg.format, r.ffmpeg.codec = 'MPEG4', 'H264'
r.ffmpeg.constant_rate_factor = 'PERC_LOSSLESS'
r.ffmpeg.audio_codec = 'NONE'
r.use_file_extension = False
r.filepath = str(WORK / 'film.mp4')
bpy.ops.render.render(animation=True, scene=sc.name)

# the parole layer in the overlay
ov = overlay.make_overlay_layer(sc)
timing = [{'text': "I'm the unknown force", 'start': 1.6, 'end': 3.2,
           'words': [{'w': "I'm", 's': 1.6, 'e': 1.85}, {'w': 'the', 's': 1.9, 'e': 2.05},
                     {'w': 'unknown', 's': 2.1, 'e': 2.6}, {'w': 'force', 's': 2.65, 'e': 3.2}]}]
layer = parole.make_parole(ov, WORK / 'parole', timing,
                           add_lines=[{'text': 'UNKNOWN FORCE', 'start': 0.2, 'end': 1.2, 'template': 'rows',
                                       'sizeScale': 1.4}])
print('[parole] groups', len(layer.data['groups']), '| sprite objects', len(layer.objects), '| F', round(layer.data['F'], 4),
      'PX', layer.data['PX'], '| fov', round(ov.half_h, 4))
for g in layer.data['groups']:
    shutil.copy(layer.out / g['atlas'], OUT / f'parole_{g["atlas"]}')
ovdir = overlay.render_overlay(ov, WORK / 'ov')
edit = overlay.make_edit_scene(film=WORK / 'film.mp4', overlays=[ovdir], like=sc)
pngs = overlay.render_edit(edit, WORK / 'edit_png', video=False)
from PIL import Image  # noqa: E402
for f in (14, 44, 62, 80):
    Image.open(pngs / f'edit_{f:04d}.png').save(OUT / f'parole_edit_f{f:03d}.png')
    print('[parole] frame', f, '->', OUT / f'parole_edit_f{f:03d}.png')
print('[test_parole] done')

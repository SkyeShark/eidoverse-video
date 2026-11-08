"""Probe: a voicebox line sung by claude.vrm in Blender (eidoblend.media.audio).

    python -B blender/tests/media/audio_host.py            # host side first (voicebox: system Python)
    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/media/test_audio.py

- the line's phoneme-exact visemes (24 fps, 0..1, gated to the sung window) keyed onto the VRM's expression shape
  keys and previews; read back at sampled frames;
- stills of the face: before the line (shut), the widest 'oh', an 'ee' / 'ih' frame;
- the voice as a sound strip, carried by a one-pass H.264 + AAC render of a second of the line (ffprobe);
- the strip's mixdown to WAV.
"""
import json
import subprocess
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _stage as S  # noqa: E402
from eidoblend.media import audio  # noqa: E402

OUT = S.OUT
WORK = OUT / 'audio_work'
if not (WORK / 'daisy_visemes.json').exists():
    raise SystemExit('run python -B blender/tests/media/audio_host.py first (voicebox runs in the system Python)')

sc = S.fresh_scene(frames=(1, 190))
bpy.ops.preferences.addon_enable(module='bl_ext.blender_org.vrm')
before = set(bpy.data.objects)
bpy.ops.import_scene.vrm(filepath=str(S.ASSETS / 'vrms' / 'claude.vrm'))
arm = next(o for o in bpy.data.objects if o not in before and o.type == 'ARMATURE')
head = next(b for b in arm.data.bones if b.name.lower().endswith('head'))
hp = arm.matrix_world @ head.head_local
print('[vrm] armature', arm.name, '| head bone', head.name, 'at', tuple(round(v, 3) for v in hp))

vj = json.loads((WORK / 'daisy_visemes.json').read_text())
vis = audio.load_visemes(vj)
wins = audio.viseme_windows(vj['lines'])
keys = audio.prepare_visemes(vis, sc, start_t=0.0, divide=1.0, windows=wins)
binds = audio.morph_binds(arm)
print('[visemes] binds', {e: [(o.name, k, round(w, 2)) for o, k, w in lst] for e, lst in binds.items()})
counts = audio.key_expressions(arm, keys, binds)
print('[visemes] keyed', counts, '| windows', wins)

# read back: the shape keys at sampled frames against the prepared values
worst = 0.0
for e, ks in keys.items():
    for f, v in ks[::17]:
        sc.frame_set(f)
        for o, key, w in binds.get(e, []):
            worst = max(worst, abs(o.data.shape_keys.key_blocks[key].value - v * w))
print(f'[visemes] read-back worst difference {worst:.5f}')

frames = {f: {e: v for e, ks in keys.items() for ff, v in ks if ff == f} for f in range(1, 190)}
f_oh = max(frames, key=lambda f: frames[f].get('oh', 0) + frames[f].get('aa', 0))
f_ee = max(frames, key=lambda f: frames[f].get('ee', 0) + frames[f].get('ih', 0))
print('[visemes] widest frame', f_oh, frames[f_oh], '| ee/ih frame', f_ee, frames[f_ee])

# the face, lit: aimed at the mouth mesh itself (claude.vrm's face disc sits well above its head bone)
mouth = binds['aa'][0][0]
corners = [mouth.matrix_world @ Vector(c) for c in mouth.bound_box]
mp = sum(corners, Vector()) / 8
print('[vrm] mouth', mouth.name, 'centre', tuple(round(v, 3) for v in mp))
S.area_light(sc, mp + Vector((-0.9, -1.2, 0.6)), mp, 60.0, size=0.8, color=(1.0, 0.93, 0.85), name='key')
S.area_light(sc, mp + Vector((1.0, -0.8, 0.1)), mp, 20.0, size=1.0, color=(0.8, 0.86, 1.0), name='fill')
S.area_light(sc, mp + Vector((0.2, 1.0, 0.6)), mp, 30.0, size=0.6, name='rim')
w = sc.world.node_tree.nodes['Background']
w.inputs['Color'].default_value = (0.05, 0.055, 0.06, 1)
S.camera(sc, mp + Vector((0.0, -1.1, 0.03)), mp + Vector((0, 0, 0.02)), lens=60)
for f in (5, f_oh, f_ee):
    S.render_still(sc, f, OUT / f'audio_face_f{f:03d}.png')

# the sound: a strip, a one-pass render with AAC, a mixdown
strip = audio.add_sound(sc, WORK / 'daisy.wav', t=0.0)
audio.add_markers(sc, [l['t0'] for l in vj['lines']], prefix='line')
r = sc.render
r.resolution_x, r.resolution_y = 480, 270
sc.eevee.taa_render_samples = 4
r.image_settings.media_type = 'VIDEO'
r.image_settings.file_format = 'FFMPEG'
r.ffmpeg.format, r.ffmpeg.codec = 'MPEG4', 'H264'
audio.mux_settings(sc)
r.use_file_extension = False
mp4 = OUT / 'audio_face_sound.mp4'
r.filepath = str(mp4)
sc.frame_start, sc.frame_end = f_oh - 12, f_oh + 11
bpy.ops.render.render(animation=True, scene=sc.name)
pr = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,codec_name,sample_rate,channels:'
                     'format=duration', '-of', 'json', str(mp4)], capture_output=True, text=True)
print('[sound] one-pass render', json.dumps(json.loads(pr.stdout)))
sc.frame_start, sc.frame_end = 1, 190
wav = audio.mixdown(sc, WORK / 'mixdown.wav')
pr = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=sample_rate,channels', '-of',
                     'json', str(wav)], capture_output=True, text=True)
print('[sound] mixdown', json.dumps(json.loads(pr.stdout)), '| strip', strip.name, strip.frame_start, strip.volume)
print('[test_audio] done')

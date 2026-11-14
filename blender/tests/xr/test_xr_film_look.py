"""tests/xr/test_xr_film_look.py: a piece in the headset with the film's look: MToon, animated material values, a camera
lens, a sky that changes and the film's sound, through export_xr and the page, against EEVEE.

    bash run_blender.sh blender/tests/xr/test_xr_film_look.py
    # a GPU job of an estimated 6 GB of VRAM and up to 16 GB of RAM; on a shared machine queue it with
    # EIDO_GPU_WRAP (blender/tests/_where.py)

The film (2 s at 24 fps, Standard view): Aletheia (aletheia.vrm, MToon with outlines) turning on the spot; a swatch whose
Principled base colour is keyed red -> blue and its roughness 0.2 -> 0.8; a checker whose Mapping node's offset is keyed
(a texture sliding); cam_film whose lens is keyed 35 -> 70 mm; a world whose colour is keyed dusk blue -> amber; a sound
strip (a 440 Hz tone written here); the page casts its sun's shadows (set_xr shadows=True), as the film does. Checked:
  the bundle   the GLB's KHR_animation_pointer channels (base colour, roughness, texture offset, the camera's yfov),
               vrm/aletheia.vrm with her MToon materials, the world as a timed sequence (3 images, a second apart),
               audio.mp3
  the page     (headless Chrome, through cam_film at 0.25 s and 1.75 s) every pointer track played, her stand-ins
               drawn with three-vrm's MToon (outlines included), the sky at the sequence's place, the sound loaded at
               the film's length, the camera's fov the keyed lens's
  against EEVEE  the swatch's colour turns from red to blue in both (the page within 0.08 of EEVEE), the sky's colour
               is EEVEE's at both times (within 0.03: the dome's cross-fade between the sequence's images)
Writes out/film_look/ (EEVEE stills, the bundle in vr/, the page stills in shots/, a side-by-side sheet).
"""
import json
import math
import os
import shutil
import struct
import sys
import wave

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
WORKTREE = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(WORKTREE, 'blender'))
sys.dont_write_bytecode = True
OUT = os.path.join(HERE, 'out', 'film_look')
shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT, exist_ok=True)
VR = os.path.join(OUT, 'vr')
SIZE = (960, 540)
FAILS = []

from eidoblend.characters import load_vrm  # noqa: E402
from eidoblend.xr import export as X  # noqa: E402
from eidoblend.xr import glb as G  # noqa: E402
from eidoblend.xr import server, shots  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402


def check(name, ok, detail=''):
    print(f"{'PASS' if ok else 'FAIL'} {name}{'  (' + str(detail) + ')' if detail else ''}", flush=True)
    if not ok:
        FAILS.append(name)


# ------------------------------------------------------------------------------------------------ the film ---
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
sc = bpy.context.scene
sc.render.fps, sc.render.fps_base = 24, 1.0
sc.frame_start, sc.frame_end = 1, 49
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = SIZE[0], SIZE[1], 100
sc.eevee.taa_render_samples = 16
sc.eevee.use_fast_gi = True
sc.view_settings.view_transform = 'Standard'
sc.view_settings.look = 'None'
sc.world = bpy.data.worlds.new('changing sky')
sc.world.use_nodes = True
bg = next(n for n in sc.world.node_tree.nodes if n.type == 'BACKGROUND')
bg.inputs['Strength'].default_value = 1.0
for f, c in ((1, (0.05, 0.08, 0.30, 1)), (49, (0.90, 0.45, 0.08, 1))):
    bg.inputs['Color'].default_value = c
    bg.inputs['Color'].keyframe_insert('default_value', frame=f)

sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(50), 0, math.radians(30))
sc.collection.objects.link(sun)
ground = bpy.data.objects.new('ground', bpy.data.meshes.new('ground'))
ground.data.from_pydata([(-6, -6, 0), (6, -6, 0), (6, 6, 0), (-6, 6, 0)], [], [(0, 1, 2, 3)])
gm = bpy.data.materials.new('ground')
gm.use_nodes = True
gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.35, 0.35, 0.35, 1)
ground.data.materials.append(gm)
sc.collection.objects.link(ground)

# the swatch: base colour and roughness keyed
bpy.ops.mesh.primitive_plane_add(size=0.8, location=(-1.1, 0.6, 0.9), rotation=(math.radians(90), 0, 0))
swatch = bpy.context.active_object
swatch.name = 'swatch'
sm = bpy.data.materials.new('swatch')
sm.use_nodes = True
pb = sm.node_tree.nodes['Principled BSDF']
for f, c, r in ((1, (0.85, 0.05, 0.04, 1), 0.2), (49, (0.04, 0.10, 0.85, 1), 0.8)):
    pb.inputs['Base Color'].default_value = c
    pb.inputs['Roughness'].default_value = r
    pb.inputs['Base Color'].keyframe_insert('default_value', frame=f)
    pb.inputs['Roughness'].keyframe_insert('default_value', frame=f)
swatch.data.materials.append(sm)

# the checker: its texture slides (a Mapping node's offset keyed)
bpy.ops.mesh.primitive_plane_add(size=0.8, location=(1.1, 0.6, 0.9), rotation=(math.radians(90), 0, 0))
checker = bpy.context.active_object
checker.name = 'checker'
cm = bpy.data.materials.new('checker')
cm.use_nodes = True
nt = cm.node_tree
img = bpy.data.images.new('checker grid', 256, 256)
img.generated_type = 'COLOR_GRID'
tex = nt.nodes.new('ShaderNodeTexImage')
tex.image = img
uvn = nt.nodes.new('ShaderNodeUVMap')
mp = nt.nodes.new('ShaderNodeMapping')
nt.links.new(uvn.outputs['UV'], mp.inputs['Vector'])
nt.links.new(mp.outputs['Vector'], tex.inputs['Vector'])
nt.links.new(tex.outputs['Color'], nt.nodes['Principled BSDF'].inputs['Base Color'])
for f, x in ((1, 0.0), (49, 0.5)):
    mp.inputs['Location'].default_value[0] = x
    mp.inputs['Location'].keyframe_insert('default_value', frame=f, index=0)
checker.data.materials.append(cm)

# Aletheia, MToon, turning on the spot
h = load_vrm('aletheia', location=(0, 0.4, 0), scene=sc)
arm = h.arm
arm.rotation_mode = 'XYZ'
for f, a in ((1, 0.0), (49, math.radians(90))):
    arm.rotation_euler = (0, 0, a)
    arm.keyframe_insert('rotation_euler', frame=f, index=2)

# the camera: its lens keyed 35 -> 70 mm
cam = bpy.data.objects.new('cam_film', bpy.data.cameras.new('cam_film'))
sc.collection.objects.link(cam)
cam.location = (0, -5.5, 1.5)
cam.rotation_euler = (math.radians(84), 0, 0)
for f, lens in ((1, 35.0), (49, 70.0)):
    cam.data.lens = lens
    cam.data.keyframe_insert('lens', frame=f)
sc.camera = cam
for idb in (bg.id_data, sm.node_tree, cm.node_tree, arm, cam.data):
    ad = idb.animation_data
    if ad and ad.action:
        from eidoblend.xr import _bl
        for fc in _bl.fcurves(idb):
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'

# the sound: a 440 Hz tone, 2 s, on a sound strip
tone = os.path.join(OUT, 'tone.wav')
with wave.open(tone, 'wb') as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(48000)
    w.writeframes(b''.join(struct.pack('<h', int(9000 * math.sin(2 * math.pi * 440 * i / 48000)))
                           for i in range(96000)))
se = sc.sequence_editor_create()
strips = se.strips if hasattr(se, 'strips') else se.sequences
strips.new_sound('tone', tone, channel=1, frame_start=1)
X.set_xr(sc, street=1.0, start=(0, -3.5, 0), facing=(0, 1, 0), landmarks=False, shadows=True)   # the film's sun shadows

TIMES = (0.25, 1.75)


def frame_of(t):
    return sc.frame_start + t * 24


def eevee_still(t):
    f = frame_of(t)
    sc.frame_set(int(math.floor(f)), subframe=f - math.floor(f))
    p = os.path.join(OUT, f'eevee_t{t}.png')
    sc.render.filepath = p
    sc.render.image_settings.media_type = 'IMAGE'
    sc.render.image_settings.file_format = 'PNG'
    bpy.ops.render.render(write_still=True)
    px = world_to_camera_view(sc, cam, swatch.matrix_world.translation)
    # the frame's vertical field of view (the sensor fits the 16:9 frame's width; angle_y is the sensor height's)
    return p, (px.x, 1 - px.y), 2 * math.atan(math.tan(cam.data.angle_x / 2) * SIZE[1] / SIZE[0])


eevee = {t: eevee_still(t) for t in TIMES}

# ------------------------------------------------------------------------------------------------ the export ---
man = X.export_xr(VR, sc, name='scene', world_width=1024, world_sequence_width=512, texel_density=32)
g = G.read(os.path.join(VR, 'scene.glb'))
pt = X.pointer_targets(g)
ptrs = sorted({ch['target']['extensions']['KHR_animation_pointer']['pointer'].split('/', 3)[-1]
               for a in g.json.get('animations', []) for ch in a['channels'] if ch['target'].get('path') == 'pointer'})
check(f"the GLB carries the animated values as KHR_animation_pointer channels ({pt['count']}: {ptrs})",
      'swatch' in pt['materials'] and 'checker' in pt['materials'] and 'cam_film' in pt['cameras']
      and any('baseColorFactor' in p for p in ptrs) and any('roughnessFactor' in p for p in ptrs)
      and any('KHR_texture_transform/offset' in p for p in ptrs) and any('yfov' in p for p in ptrs))
v = man['vrm'][0] if man['vrm'] else {}
check(f"Aletheia's .vrm beside the GLB with her MToon materials ({v.get('file')}, {len(v.get('materials', []))} "
      f"materials, {v.get('bytes', 0) / 1e6:.1f} MB)", v and os.path.exists(os.path.join(VR, v['file']))
      and len(v['materials']) > 0)
seq = (man['world'] or {}).get('sequence') or []
check(f"the changing sky as a timed sequence ({[(s['t'], s['file']) for s in seq]})",
      len(seq) == 3 and all(os.path.exists(os.path.join(VR, s['file'])) for s in seq)
      and seq[0]['mean'][2] > seq[0]['mean'][0] and seq[-1]['mean'][0] > seq[-1]['mean'][2])
wmb = man['counts'].get('world_mb_gpu')
check(f"the sky's GPU memory counted with the textures: {wmb} MB for 3 images 512 wide and their prefiltered light "
      f"(Quest textures {man['quest']['textures']} for {man['counts']['texture_mb_gpu']} + {wmb} MB)",
      wmb == X.world_gpu_mb(512, 3) and wmb > 0)
check(f"the film's sound mixed down ({man['audio']})", man['audio'] and os.path.getsize(os.path.join(VR, 'audio.mp3')) > 10000)
check('no warning that an animated value is not played (' + '; '.join(w for w in man['warnings'] if 'animated' in w)
      + ')', not any('is animated' in w for w in man['warnings']))

# ------------------------------------------------------------------------------------------------ the page ---
log = os.path.join(OUT, 'reports.jsonl')
srv = server.start(http_port=0, log=log)
try:
    qs = [f't={t}&camera=cam_film' for t in TIMES]
    rows = shots.shoot(srv.url + '/blender/tests/xr/out/film_look/vr/index.html', os.path.join(OUT, 'shots'), qs,
                       size=SIZE, timeout=120)
finally:
    srv.stop()
by = {r['query']: r for r in rows}
check('every page still rendered, no exception or console error',
      all(r['status'] == 'ready' for r in rows) and not any('EXCEPTION' in e or 'console.error' in e
                                                            for r in rows for e in r['errors']),
      '; '.join(f"{r['query']}={r['status']} {r['errors'][:2]}" for r in rows))


def rgb(path, uv, r=6):
    from PIL import Image
    im = np.asarray(Image.open(path).convert('RGB').resize(SIZE), np.float64) / 255
    x, y = int(uv[0] * SIZE[0]), int(uv[1] * SIZE[1])
    return im[max(0, y - r):y + r, max(0, x - r):x + r].reshape(-1, 3).mean(0)


for t in TIMES:
    q = f't={t}&camera=cam_film'
    info = (by.get(q) or {}).get('info') or {}
    mt = info.get('mtoon') or {}
    fov = math.degrees(eevee[t][2])
    check(f"t={t}: every pointer track played ({info.get('pointersPlayed')} of {info.get('pointers')}; unknown "
          f"{info.get('unknownPointers')})", info.get('pointers', 0) >= 4 and info.get('pointersPlayed') == info.get('pointers'))
    check(f"t={t}: Aletheia drawn in three-vrm's MToon ({mt.get('materials')} materials, {mt.get('outlines')} with "
          'outlines)', mt.get('materials', 0) > 0 and mt.get('outlines', 0) > 0)
    check(f"t={t}: the sky at its place in the sequence ({info.get('sky')})",
          info.get('sky') and info['sky']['images'] == 3 and abs(info['sky']['at'] - t) < 1e-3)
    check(f"t={t}: the sound loaded, the film's length ({info.get('audio')})",
          info.get('audio') and abs(info['audio']['duration'] - 2.0) < 0.1 and info['audio']['ready'] >= 1)
    check(f"t={t}: the camera's fov is the keyed lens's ({info.get('cameraFov')} vs EEVEE's {fov:.4f} deg)",
          info.get('cameraFov') is not None and abs(info['cameraFov'] - fov) < 0.05)
cols = {}
for t in TIMES:
    q = f't={t}&camera=cam_film'
    if by.get(q, {}).get('path'):
        cols[t] = (rgb(eevee[t][0], eevee[t][1]), rgb(by[q]['path'], eevee[t][1]),
                   rgb(eevee[t][0], (0.1, 0.06)), rgb(by[q]['path'], (0.1, 0.06)))     # the sky, clear of her


def linear(c):
    """sRGB-encoded 0..1 to linear"""
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


if len(cols) == 2:
    a, b = ([linear(c) for c in cols[t]] for t in TIMES)
    check(f'the swatch turns from red to blue in EEVEE and on the page, the page within 0.08 of EEVEE (linear: EEVEE '
          f'{a[0].round(3)} -> {b[0].round(3)}, page {a[1].round(3)} -> {b[1].round(3)})',
          a[0][0] > a[0][2] and b[0][2] > b[0][0] and a[1][0] > a[1][2] and b[1][2] > b[1][0]
          and np.abs(a[1] - a[0]).max() < .08 and np.abs(b[1] - b[0]).max() < .08)
    check(f"the sky is EEVEE's at both times, within 0.03 (linear: EEVEE {a[2].round(3)} -> {b[2].round(3)}, page "
          f'{a[3].round(3)} -> {b[3].round(3)})', np.abs(a[3] - a[2]).max() < .03 and np.abs(b[3] - b[2]).max() < .03)
    from PIL import Image, ImageDraw
    sheet = Image.new('RGB', (SIZE[0], SIZE[1]), (12, 12, 12))
    for i, t in enumerate(TIMES):
        for j, p in enumerate((eevee[t][0], by[f't={t}&camera=cam_film']['path'])):
            im = Image.open(p).convert('RGB').resize((SIZE[0] // 2, SIZE[1] // 2))
            sheet.paste(im, (j * SIZE[0] // 2, i * SIZE[1] // 2))
            ImageDraw.Draw(sheet).text((j * SIZE[0] // 2 + 6, i * SIZE[1] // 2 + 4),
                                       f"{'EEVEE' if j == 0 else 'page'} t={t}", fill=(255, 255, 255))
    sheet.save(os.path.join(OUT, 'film_look_sheet.png'))
with open(os.path.join(OUT, 'results.json'), 'w', encoding='utf-8') as f:
    json.dump({'fails': FAILS, 'manifest': {k: man[k] for k in ('pointer_tracks', 'vrm', 'audio', 'world')}}, f,
              indent=1, default=str)
print('\n%d FAIL' % len(FAILS) if FAILS else '\nALL PASS', flush=True)

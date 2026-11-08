"""tests/xr/test_xr_city.py: the kit's example city built in Blender, rendered with EEVEE, exported for the XR page.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \\
        <worktree>/blender/tests/xr/test_xr_city.py

Checks (PASS / FAIL lines):
  - EXAMPLES['city'] builds the page's 36 towers from its Park-Miller generator (180 faces, g0 / tower attributes) and
    its 24 walkers, whose Geometry Nodes positions at t = 4 s equal example.html's formula
  - the scene's XR settings and Blender's VR landmarks: the street landmark's head is cam_street's eye (stage (0, 0, 10),
    eyes 1.6 m at 0.25 m a unit = 6.4 units up), base scale 4; the table landmark 1:100, the centre 0.45 m ahead
    and 0.75 m below the eyes
  - EEVEE stills at t = 4 s (frame 97): cam_street (the page's street still), cam_table (the page's desktop table
    view), and the two landmarks' start views, into out/city/
  - export_xr: the walkers become 24 keyed objects, the towers' procedural windows a baked unlit texture, the ground
    the page's grid (extras), the world an .hdr; the GLB read back: one 30 s clip, every walker at t = 4 where the
    Geometry Nodes put it (the page plays that), the cameras, the Quest budgets
Writes out/city/city.blend (the built scene, before the export) and out/city/vr/ (the bundle the page test serves).
"""
import json
import math
import os
import sys
import time

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
WORKTREE = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(WORKTREE, 'blender'))
# --no-render: an API run (no EEVEE still, no Cycles bake or world image) into out/city_norender/: everything else
# is checked; what needs a render is left to the GPU run
NO_RENDER = '--no-render' in sys.argv
OUT = os.path.join(HERE, 'out', 'city_norender' if NO_RENDER else 'city')
os.makedirs(OUT, exist_ok=True)

from eidoblend.xr import examples as E          # noqa: E402
from eidoblend.xr import export as X            # noqa: E402
from eidoblend.xr import glb as G               # noqa: E402
from eidoblend.xr import landmarks as LM        # noqa: E402

RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok), detail))
    print(f"[check] {'PASS' if ok else 'FAIL'} {name}{': ' + str(detail) if detail else ''}", flush=True)


def render(sc, cam, frame, path, samples=16):
    if NO_RENDER:
        return None
    sc.camera = cam
    E.grid_pixel_angle(sc, camera=cam)
    sc.frame_set(frame)
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = samples
    sc.render.image_settings.media_type = 'IMAGE'
    sc.render.image_settings.file_format = 'PNG'
    sc.render.filepath = path
    sc.render.use_file_extension = False
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    ok = os.path.exists(path)
    check(f'EEVEE still {os.path.basename(path)}', ok, f'{time.time() - t0:.1f} s')
    return path


# ------------------------------------------------------------------------------------------------- build ---
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
sc = bpy.context.scene
city = E.EXAMPLES['city'](sc)
T4 = 4.0
F4 = sc.frame_start + int(round(T4 * city['fps']))

towers = city['towers']
check('towers: one mesh of 36 boxes (5 faces each, the bottom never shows)', len(towers.data.polygons) == 180,
      f"{len(towers.data.polygons)} faces")
lay = E.tower_layout()
x0, z0, w0, h0 = lay[0]
vs = [towers.matrix_world @ v.co for v in towers.data.vertices[:20]]
top = max(v.z for v in vs)
check("tower 0 is the page's (Park-Miller seed 11): height and centre", abs(top - h0) < 1e-4
      and abs(sum(v.x for v in vs) / len(vs) - x0) < w0, f'height {top:.3f} vs {h0:.3f}, x {x0:.2f}, z {z0:.2f}')
check('towers carry g0 and tower attributes', 'g0' in towers.data.attributes and 'tower' in towers.data.attributes)


def page_towers_js():
    """example.html's own tower generator, cut out of the page and run by node: [x, z, width, height] x 36 (float32,
    as the page's Float32Array holds them), or None without node."""
    import re
    import shutil
    import subprocess
    node = shutil.which('node')
    if not node:
        return None
    html = open(os.path.join(WORKTREE, 'eidoverse', 'xr', 'example.html'), encoding='utf-8').read()
    m = re.search(r'\{ // towers.*?\n(.*?)\n\s*const geo = new THREE\.BoxGeometry\(1, 1, 1\)', html, re.S)
    if not m:
        return None
    code = m.group(1) + '\nconsole.log(JSON.stringify(Array.from(off)));'
    r = subprocess.run([node, '-e', code], capture_output=True, text=True, timeout=60)
    return json.loads(r.stdout) if r.returncode == 0 else None


js = page_towers_js()
if js is None:
    check("towers: the page's own generator ran (node)", False, 'node missing or the page changed')
else:
    worst = max(abs(a - b) / max(1.0, abs(b)) for row, i in zip(E.tower_layout(), range(36))
                for a, b in zip(row, js[i * 4:i * 4 + 4]))
    check("towers: tower_layout() equals example.html's own generator (run by node), all 36 x (x, z, w, h)",
          len(js) == 144 and worst < 1e-6, f'max relative difference {worst:.1e} (float32 in the page)')

sc.frame_set(F4)
dg = bpy.context.evaluated_depsgraph_get()
inst = [(tuple(i.persistent_id), i.matrix_world.translation.copy()) for i in dg.object_instances
        if i.is_instance and i.parent and i.parent.original == city['walkers']]     # (copied: they die with the loop)
check('walkers: 24 Geometry Nodes instances', len(inst) == 24, len(inst))
err = 0.0
for k, (_pid, at) in enumerate(sorted(inst)):
    px, py, pz = E.walker_position(k, T4)
    want = Vector((px, -pz, py))
    err = max(err, (at - want).length)
check("walkers at t = 4 s stand where example.html's formula puts them", err < 1e-4, f'max error {err:.2e} m')

# ------------------------------------------------------------------------------------- XR settings, landmarks ---
xr = X.get_xr(sc)
check('XR settings saved with the scene', xr['street'] == 0.25 and xr['table'] == 0.01 and xr['name'] == 'city', xr)
lms = {d['name']: d for d in LM.read(sc)}
check('VR landmarks xr_street and xr_table written', 'xr_street' in lms and 'xr_table' in lms, sorted(lms))
eye, fwd, s = LM.head_pose(sc, 'xr_street')
cam_street = bpy.data.objects['cam_street']
check("street landmark: the head starts at cam_street's eye, looking +Y, base scale 4",
      (eye - cam_street.location).length < 1e-5 and fwd.dot(Vector((0, 1, 0))) > 0.99999 and abs(s - 4) < 1e-6,
      f'eye {tuple(round(v, 3) for v in eye)} scale {s}')
eye_t, fwd_t, s_t = LM.head_pose(sc, 'xr_table')
rel = (Vector((0, 0, 0)) - eye_t) * (1 / s_t)          # the centre from the eyes, in room metres
check('table landmark: 1:100, the centre 0.45 m ahead and 0.75 m below the eyes',
      abs(s_t - 100) < 1e-6 and abs(rel.dot(fwd_t) - 0.45) < 1e-6 and abs(rel.z + 0.75) < 1e-6,
      f'{rel.dot(fwd_t):.3f} m ahead, {rel.z:.3f} m up')
wm = bpy.context.window_manager
ss = wm.xr_session_settings
check('the street landmark is active in the session settings',
      abs(ss.base_scale - 4) < 1e-6 and ss.base_pose_type == 'CUSTOM'
      and (Vector(ss.base_pose_location) - eye).length < 1e-6 and sc.vr_landmarks[sc.vr_landmarks_active].name == 'xr_street')
check("session settings: the page's view at the landmark's scale (rays, no floor, 2 cm - 400 m, 2.6 m/s, "
      'the head at the landmark)', ss.show_controllers and ss.controller_draw_style == 'LIGHT_RAY' and not ss.show_floor
      and abs(ss.clip_start - 0.08) < 1e-6 and abs(ss.clip_end - 1600) < 1e-3 and abs(ss.fly_speed - 10.4) < 1e-5
      and ss.use_positional_tracking and not ss.use_absolute_tracking,
      (ss.controller_draw_style, round(ss.clip_start, 4), round(ss.clip_end, 1), round(ss.fly_speed, 3)))
# toTable's height rule for other viewers: kept between 0.6 and 1.05 m off the floor, or exactly `height`
for eh, h, want_drop in ((1.2, None, 0.6), (2.1, None, 1.05), (1.6, 0.7, 0.9)):
    LM.to_table(sc, (0, 0, 0), 0.01, eye_height=eh, height=h, name='_probe_table')
    e_, f_, s_ = LM.head_pose(sc, '_probe_table')
    r_ = (Vector((0, 0, 0)) - e_) * (1 / s_)
    check(f'to_table(eye_height={eh}, height={h}): the centre {want_drop} m below the eyes, 0.45 m ahead',
          abs(r_.z + want_drop) < 1e-6 and abs(r_.dot(f_) - 0.45) < 1e-6, f'{r_.z:.3f} m up')
sc.vr_landmarks.remove(LM._get(sc, '_probe_table')[0])
LM.activate(sc, 'xr_street')

# ----------------------------------------------------------------------------------------------- EEVEE ---
cam_table = bpy.data.objects['cam_table']
render(sc, cam_street, F4, os.path.join(OUT, 'eevee_cam_street_t4.png'))
render(sc, cam_table, F4, os.path.join(OUT, 'eevee_cam_table_t4.png'))
vr_s = LM.view_camera(sc, 'xr_street', fov_v=70.0)
vr_t = LM.view_camera(sc, 'xr_table', fov_v=70.0)
render(sc, vr_s, F4, os.path.join(OUT, 'eevee_vr_landmark_street_t4.png'))
render(sc, vr_t, F4, os.path.join(OUT, 'eevee_vr_landmark_table_t4.png'))
for c in (vr_s, vr_t):
    d = c.data
    bpy.data.objects.remove(c, do_unlink=True)
    bpy.data.cameras.remove(d)
sc.camera = cam_street
sc.frame_set(sc.frame_start)
blend = os.path.join(OUT, 'city.blend')
bpy.ops.wm.save_as_mainfile(filepath=blend, check_existing=False)
check('saved the built city', os.path.exists(blend), blend)

# ----------------------------------------------------------------------------------------------- export ---
vr = os.path.join(OUT, 'vr')
man = X.export_xr(vr, sc, name='scene', world_width=1024, bake_materials=not NO_RENDER, world=not NO_RENDER)
rep = man['report']
s_ = man['summary']
check('export: the walkers became 24 keyed objects', rep['motion'].get('xr_city_walkers', {}).get('instances') == 24
      and rep['motion']['xr_city_walkers'].get('moving'), rep['motion'].get('xr_city_walkers'))
check('export: no GLB animation problem (channels on their own nodes)', not rep.get('channel_problems'),
      rep.get('channel_problems'))
if not NO_RENDER:
    baked = rep['materials'].get('baked', {})
    check("export: the towers' procedural windows baked to an unlit texture",
          'xr_city_towers' in baked and baked['xr_city_towers']['kind'] == 'unlit', baked.get('xr_city_towers'))
    check("export: the walkers' normal-shaded colour baked once for the 24 (one shared mesh)",
          any(set(v.get('shared_by', [])) >= {f'xr_city_walkers_{k:03d}' for k in range(24)} for v in baked.values()),
          [k for k in baked])
    check('export: the ground is the page\'s grid (fallback material, xr_material extras)',
          'xr_city_ground' in rep['materials'].get('fallback', []) and 'xr_city_ground' in man['page_materials'])
for f in ('scene.glb', 'scene.xr.json', 'index.html') + (() if NO_RENDER else ('world.hdr',)):
    check(f'bundle has {f}', os.path.exists(os.path.join(vr, f)))

g = G.read(os.path.join(vr, 'scene.glb'))
check('GLB: one clip of the whole 30 s', len(s_['animations']) == 1 and abs(s_['duration'] - 30.0) < 0.05,
      [(a['name'], round(a['duration'], 3), a['channels']) for a in s_['animations']])
sc.frame_set(F4)
dg = bpy.context.evaluated_depsgraph_get()
worst, n = 0.0, 0
for k in range(24):
    name = f'xr_city_walkers_{k:03d}'
    if name not in bpy.data.objects:
        continue
    want = bpy.data.objects[name].matrix_world.translation
    got = Vector(G.node_position(g, name, t=T4, blender_axes=True))
    px, py, pz = E.walker_position(k, T4)
    page = Vector((px, -pz, py))
    worst = max(worst, (got - want).length, (got - page).length)
    n += 1
check('GLB: every walker at t = 4 s where Blender and the page formula put it', n == 24 and worst < 2e-3,
      f'{n} walkers, max error {worst * 1000:.2f} mm')
wnodes = [n for n in g.json['nodes'] if n.get('name', '').startswith('xr_city_walkers_') and 'mesh' in n]
check('GLB: the 24 walkers are drawn (a mesh each, one shared mesh)', len(wnodes) == 24
      and len({n['mesh'] for n in wnodes}) == 1, f'{len(wnodes)} walker mesh nodes')
if not NO_RENDER:
    tm = next((m for m in s_['materials'] if m['name'] and m['name'].startswith('gltf_xr_city_towers')), None)
    check('GLB: the towers\' material is unlit with a base colour texture', tm and tm['unlit'] and tm['baseColorTexture'],
          tm)
gn = g.json['nodes'][g.node_by_name('xr_city_ground')]
check('GLB: the ground node carries xr_material = grid', gn.get('extras', {}).get('xr_material') == 'grid',
      gn.get('extras'))
check('GLB: cam_street and cam_table exported', {'cam_street', 'cam_table'} <= set(man['cameras']), man['cameras'])
check('GLB: within the Quest budgets', all(v == 'ok' for v in s_['quest'].values()),
      f"{s_['triangles']} triangles, {s_['draws']} draws, {s_['texture_mb_gpu']} MB textures: {s_['quest']}")
check('manifest: three-axis start (0, 0, 10) facing (0, 0, -1), street 0.25, table 0.01, Standard view',
      man['start'] == [0.0, 0.0, 10.0] and man['facing'] == [0.0, 0.0, -1.0] and man['street'] == 0.25
      and man['table'] == 0.01 and man['view']['tone_mapping'] == 'None', (man['start'], man['facing']))
with open(os.path.join(OUT, 'export_report.json'), 'w') as f:
    json.dump({k: v for k, v in man.items()}, f, indent=1, default=str)

n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
print(f'[check] {len(RESULTS) - n_fail} passed, {n_fail} failed', flush=True)
sys.exit(1 if n_fail else 0)

"""tests/xr/test_xr_films.py: real films built by round one's tests, exported for the headset page.

    cd <main checkout> && HEAVY_VRAM_GB=6 bash work/claude_body/work/tmp/heavy.sh 16 bash run_blender.sh \\
        <worktree>/blender/tests/xr/test_xr_films.py [example] [crows] [robot_walk]

The .blends are other tests' outputs (built by eido_blender / the characters suite), opened here READ ONLY: each is
rendered with EEVEE at a few times through its camera, then changed by export_xr into out/films/<film>/vr/ and never
saved. Films:
  example     tests/pipeline/out/example.blend     Poly Haven product shot: image-textured PBR, two area lights, a world
  crows       tests/pipeline/out/crows.blend       two skinned crows pecking and cawing on a textured floor, dusk world
  robot_walk  tests/characters/out/robot_walk.blend  my robot body walking a path (keyed every frame), studio suns
              (it has no camera: the test adds one following the walk, for the EEVEE stills and the page)
Checks per film: the bundle is written; one glTF clip as long as the film; at each check time every exported object,
every armature's bones and the camera stand in the GLB where Blender has them; image textures went through as they
are (no bake); the Quest grades. out/films/films.json tells test_xr_pages.py what to photograph.
"""
import json
import math
import os
import sys
import time

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
WORKTREE = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(WORKTREE, 'blender'))
TESTS = os.path.join(WORKTREE, 'blender', 'tests')
# --no-render: an API run (no EEVEE still, no world image) into out/films_norender/: the motion checks only
NO_RENDER = '--no-render' in sys.argv
OUT = os.path.join(HERE, 'out', 'films_norender' if NO_RENDER else 'films')
os.makedirs(OUT, exist_ok=True)

from eidoblend.common import script_args  # noqa: E402
from eidoblend.xr import export as X      # noqa: E402
from eidoblend.xr import glb as G         # noqa: E402

FILMS = {
    'example': {'blend': os.path.join(TESTS, 'pipeline', 'out', 'example.blend'), 'times': (0.0, 1.5, 2.9)},
    'crows': {'blend': os.path.join(TESTS, 'pipeline', 'out', 'crows.blend'), 'times': (0.5, 1.58, 2.58)},
    'robot_walk': {'blend': os.path.join(TESTS, 'characters', 'out', 'robot_walk.blend'), 'times': (1.0, 3.0, 5.0)},
}
RESULTS = []
C = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))       # glTF (Y-up) -> Blender


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok), detail))
    print(f"[check] {'PASS' if ok else 'FAIL'} {name}{': ' + str(detail) if detail else ''}", flush=True)


def frame_of(sc, t):
    return sc.frame_start + int(round(t * sc.render.fps / sc.render.fps_base))


def gltf_world(g, i, t):
    return C @ Matrix(G.world_matrices(g, t)[i]) @ C.inverted()


def joint_index(g, arm_name, bone):
    """The node of an armature's bone (glTF skins are named after the armature; bones may repeat across armatures)."""
    for sk in g.json.get('skins', []):
        if sk.get('name') == arm_name:
            for j in sk['joints']:
                if g.json['nodes'][j].get('name') == bone:
                    return j
    try:
        stack = [g.node_by_name(arm_name)]
    except KeyError:
        return None
    while stack:
        i = stack.pop()
        if g.json['nodes'][i].get('name') == bone:
            return i
        stack += g.json['nodes'][i].get('children', [])
    return None


def add_follow_camera(sc):
    """robot_walk has no camera: one 6 m to the side of the walk, tracking the robot's hips, lens 28 mm."""
    arm = next(o for o in sc.objects if o.type == 'ARMATURE')
    hips = next((b.name for b in arm.pose.bones if 'hips' in b.name.lower()), arm.pose.bones[0].name)
    pts = []
    for f in range(sc.frame_start, sc.frame_end + 1, 4):
        sc.frame_set(f)
        pts.append(arm.matrix_world @ arm.pose.bones[hips].head)
    c = sum(pts, Vector()) / len(pts)
    aim = bpy.data.objects.new('cam_aim_xr', None)
    sc.collection.objects.link(aim)
    con = aim.constraints.new('CHILD_OF')
    con.target, con.subtarget = arm, hips
    cd = bpy.data.cameras.new('cam_follow')
    cd.lens = 28.0
    cd.clip_start, cd.clip_end = 0.05, 300.0
    cam = bpy.data.objects.new('cam_follow', cd)
    sc.collection.objects.link(cam)
    cam.location = (c.x + 0.5, c.y - 6.5, 1.6)
    tt = cam.constraints.new('TRACK_TO')
    tt.target, tt.track_axis, tt.up_axis = aim, 'TRACK_NEGATIVE_Z', 'UP_Y'
    sc.camera = cam
    sc.frame_set(sc.frame_start)
    return cam


def film(name, spec):
    print(f'=== {name}: {spec["blend"]}', flush=True)
    if not os.path.exists(spec['blend']):
        check(f'{name}: the built .blend exists (run its family test first)', False, spec['blend'])
        return None
    bpy.ops.wm.open_mainfile(filepath=spec['blend'], load_ui=False)
    sc = bpy.context.scene
    out = os.path.join(OUT, name)
    os.makedirs(out, exist_ok=True)
    if sc.camera is None:
        add_follow_camera(sc)
    cam = sc.camera
    dur = (sc.frame_end - sc.frame_start) / (sc.render.fps / sc.render.fps_base)
    # EEVEE stills through the film's camera at the check times (the film's own settings, probe quality)
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 960, 540, 100
    sc.eevee.taa_render_samples = 16
    sc.render.image_settings.media_type = 'IMAGE'
    sc.render.image_settings.file_format = 'PNG'
    sc.render.use_file_extension = False
    if sc.compositing_node_group is not None:
        sc.render.use_compositing = False          # the page has no post: compare the plain render
    stills = {}
    for t in (() if NO_RENDER else spec['times']):
        sc.frame_set(frame_of(sc, t))
        p = os.path.join(out, f'eevee_{cam.name}_t{t:g}.png')
        sc.render.filepath = p
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        check(f'{name}: EEVEE still at t = {t:g}', os.path.exists(p), f'{time.time() - t0:.1f} s')
        stills[t] = p
    # what Blender says at the check times
    arms = [o for o in sc.objects if o.type == 'ARMATURE' and not o.hide_render]
    truth = {}
    for t in spec['times']:
        sc.frame_set(frame_of(sc, t))
        d = {'objects': {}, 'bones': {}, 'cam': cam.matrix_world.copy()}
        for o in X.export_objects(sc):
            skinned = o.type == 'MESH' and any(m.type == 'ARMATURE' for m in o.modifiers)
            if o.type in ('MESH', 'EMPTY') and not skinned and o.parent is None:
                d['objects'][o.name] = o.matrix_world.translation.copy()
        for a in arms:
            names = [b.name for b in a.pose.bones]
            pick = [names[0], names[len(names) // 2], names[-1]] + [n for n in names if any(
                k in n.lower() for k in ('head', 'hand', 'foot'))][:4]
            for b in dict.fromkeys(pick):
                d['bones'][(a.name, b)] = a.matrix_world @ a.pose.bones[b].head
        truth[t] = d
    sc.frame_set(sc.frame_start)
    # the export (the scene's XR settings, else the defaults: life size from the camera's ground point)
    if not sc.get('eido_xr'):
        X.set_xr(sc, street=1.0, name=name, landmarks=False)
    vr = os.path.join(out, 'vr')
    t0 = time.time()
    man = X.export_xr(vr, sc, name='scene', world_width=1024, world=not NO_RENDER)
    s = man['summary']
    check(f'{name}: no GLB animation problem (channels on their own nodes)', not man['report'].get('channel_problems'),
          man['report'].get('channel_problems'))
    check(f'{name}: the bundle (scene.glb, scene.xr.json, index.html)', all(os.path.exists(os.path.join(vr, f)) for f in
          ('scene.glb', 'scene.xr.json', 'index.html')), f'{time.time() - t0:.1f} s, {s["bytes"] / 1e6:.1f} MB')
    g = G.read(os.path.join(vr, 'scene.glb'))
    moving = bool(s['animations'])
    check(f'{name}: one clip as long as the film ({dur:.2f} s), or none for a still set',
          (len(s['animations']) == 1 and abs(s['duration'] - dur) < 0.05) or not moving,
          [(a['name'], round(a['duration'], 3), a['paths']) for a in s['animations']])
    for t in spec['times']:
        d = truth[t]
        worst, n = 0.0, 0
        for on, want in d['objects'].items():
            try:
                i = g.node_by_name(on)
            except KeyError:
                continue
            worst = max(worst, (gltf_world(g, i, t).translation - want).length)
            n += 1
        check(f'{name} t = {t:g}: {n} objects where Blender has them', n > 0 and worst < 2e-3, f'max {worst * 1000:.2f} mm')
        if d['bones']:
            worst, n, missing = 0.0, 0, []
            for (an, bn), want in d['bones'].items():
                j = joint_index(g, an, bn)
                if j is None:
                    missing.append(bn)
                    continue
                worst = max(worst, (gltf_world(g, j, t).translation - want).length)
                n += 1
            check(f'{name} t = {t:g}: {n} bones of {len(arms)} armature(s) where Blender poses them', n > 0
                  and not missing and worst < 0.01, f'max {worst * 1000:.2f} mm' + (f', missing {missing}' if missing else ''))
        ci = g.node_by_name(cam.name)
        if 'camera' not in g.json['nodes'][ci]:
            ci = next(c for c in g.json['nodes'][ci].get('children', []) if 'camera' in g.json['nodes'][c])
        mg = gltf_world(g, ci, t)
        vx, vy, vz = Matrix(G.world_matrices(g, t)[ci]).to_3x3() @ Vector((0, 0, -1))   # a glTF camera looks down -z
        fw_g = Vector((vx, -vz, vy))                                                      # (its own axes: no C^-1)
        fw_b = d['cam'].to_3x3() @ Vector((0, 0, -1))
        dp = (mg.translation - d['cam'].translation).length
        check(f'{name} t = {t:g}: the camera ({cam.name}) where Blender has it, aimed the same',
              dp < 2e-3 and math.degrees(fw_g.angle(fw_b)) < 0.5, f'{dp * 1000:.2f} mm, {math.degrees(fw_g.angle(fw_b)):.2f} deg')
    baked = man['report']['materials'].get('baked', {})
    textured = [m['name'] for m in s['materials'] if m['baseColorTexture']]
    check(f'{name}: image-textured materials went through as they are (none baked)', not baked,
          f'{len(textured)} textured materials; baked: {sorted(baked)}')
    check(f'{name}: Quest grades reported', set(s['quest']) == {'triangles', 'draws', 'textures'},
          f"{s['triangles']} triangles, {s['draws']} draws, {s['texture_mb_gpu']} MB textures: {s['quest']}")
    with open(os.path.join(out, 'export_report.json'), 'w') as f:
        json.dump(man, f, indent=1, default=str)
    return {'bundle': os.path.relpath(vr, WORKTREE).replace('\\', '/'), 'camera': cam.name,
            'times': list(spec['times']), 'eevee': {f'{t:g}': os.path.relpath(p, WORKTREE).replace('\\', '/')
                                                     for t, p in stills.items()},
            'duration': dur, 'counts': man['counts'], 'quest': man['quest'], 'warnings': man['warnings'],
            'tone_mapping': man['view']['tone_mapping'], 'rect_lights': len(man['rect_lights'])}


want = [a for a in script_args() if a in FILMS] or list(FILMS)
index_path = os.path.join(OUT, 'films.json')
index = json.load(open(index_path)) if os.path.exists(index_path) else {}
for n in want:
    r = film(n, FILMS[n])
    if r is not None:
        index[n] = r
with open(index_path, 'w') as f:
    json.dump(index, f, indent=1)
n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
print(f'[check] {len(RESULTS) - n_fail} passed, {n_fail} failed', flush=True)
sys.exit(1 if n_fail else 0)

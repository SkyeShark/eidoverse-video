"""tests/xr/test_xr_films.py: real films, exported for the headset page.

    cd <main checkout> && HEAVY_VRAM_GB=6 bash work/claude_body/work/tmp/heavy.sh 16 bash run_blender.sh \\
        <worktree>/blender/tests/xr/test_xr_films.py [example] [crows] [robot_walk] [stage]

Three films are other families' test outputs (eido_blender through the pipeline suite, the look family's stage),
opened here READ ONLY when they are built and skipped, with the test that builds them, when they are not; my robot's
walk the test builds itself (tests/xr/_inputs.py). Each is rendered with EEVEE at a few times through its camera,
then changed by export_xr into out/films/<film>/vr/ and never saved. Films:
  example     tests/pipeline/out/example.blend     Poly Haven product shot: image-textured PBR, two area lights, a world
  crows       tests/pipeline/out/crows.blend       two skinned crows pecking and cawing on a textured floor, dusk world
  robot_walk  built here: my robot body walking 7 m across a level floor (the characters family's walk, keyed every
              frame), two suns (it has no camera: the test adds one following the walk, for the EEVEE stills and the
              page)
  stage       tests/look/out/stage/stage.blend   the look family's theatre: five spot lights (coloured PARs, follow-spot
              keys), my robot body on the boards, a haze box (a volume material: left out), and a camera cut at a marker
              (cam_house, then cam_reverse from frame 25)
Checks per film: the bundle is written; one glTF clip as long as the film; at each check time every exported object,
every armature's bones and the camera the film cuts to at that time stand in the GLB where Blender has them; each area
light's RectAreaLight shines down the light's own -z with its width along its x; image textures went through as they
are (no bake); meshes of volume materials are left out and named; the Quest grades; robot_walk is exported with the
image cap (max_image 2048: its 4096 px maps no longer grade it over). The EEVEE stills are like for like with the page:
no compositor, and no volumes (the page has neither). out/films/films.json tells test_xr_pages.py what to photograph,
through which camera at each time.
"""
import json
import math
import os
import sys
import time

import bpy
from mathutils import Matrix, Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
WORKTREE = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(WORKTREE, 'blender'))
TESTS = os.path.join(WORKTREE, 'blender', 'tests')
# --no-render: an API run (no EEVEE still, no world image) into out/films_norender/: the motion checks only
NO_RENDER = '--no-render' in sys.argv
OUT = os.path.join(HERE, 'out', 'films_norender' if NO_RENDER else 'films')
os.makedirs(OUT, exist_ok=True)

sys.path.insert(0, HERE)
from eidoblend.common import script_args, to_three  # noqa: E402
from eidoblend.xr import export as X      # noqa: E402
from eidoblend.xr import glb as G         # noqa: E402
import _inputs as I                       # noqa: E402

FILMS = {
    'example': {'built': 'example', 'times': (0.0, 1.5, 2.9)},
    'crows': {'built': 'crows', 'times': (0.5, 1.58, 2.58)},
    # my robot body's maps are 4096 px: as they are they grade the walk 'over' the headset's texture budget, so this
    # film is exported with export_xr's image cap (max_image), the headset's option
    'robot_walk': {'build': I.robot_walk, 'times': (1.0, 2.5, 4.0), 'export': {'max_image': 2048}},
    # the look family's theatre: spot lights, a haze volume, a camera cut at frame 25 (t = 1.0)
    'stage': {'built': 'stage', 'times': (0.5, 1.0, 1.9)},
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
    # on the hips' head (a Child Of would take its inverse at the first evaluation and hold the Empty on the floor
    # under the walk's start, swinging with the hips' turn)
    con = aim.constraints.new('COPY_LOCATION')
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
    if 'build' in spec:
        print(f'=== {name}: built here ({spec["build"].__doc__})', flush=True)
        spec['build']()
    else:
        path, why = I.built(spec['built'])
        if path is None:
            print(f'[SKIP] {name}: {why}', flush=True)
            return None
        print(f'=== {name}: {path}', flush=True)
        bpy.ops.wm.open_mainfile(filepath=path, load_ui=False)
    sc = bpy.context.scene
    out = os.path.join(OUT, name)
    os.makedirs(out, exist_ok=True)
    if sc.camera is None:
        add_follow_camera(sc)
    sc.frame_set(sc.frame_start)
    cam = sc.camera                                # the film's first camera (markers may cut to others: cams below)
    cams = {}
    for t in spec['times']:                        # the camera the film shows at each check time (frame_set follows
        sc.frame_set(frame_of(sc, t))              # the timeline's camera markers)
        cams[t] = sc.camera
    dur = (sc.frame_end - sc.frame_start) / (sc.render.fps / sc.render.fps_base)
    # EEVEE stills through the film's camera at the check times (the film's own settings, probe quality), like for like
    # with the page: no compositor and no volumes (a volume object, a haze box's volume material), which the page has not
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 960, 540, 100
    sc.eevee.taa_render_samples = 16
    sc.render.image_settings.media_type = 'IMAGE'
    sc.render.image_settings.file_format = 'PNG'
    sc.render.use_file_extension = False
    if sc.compositing_node_group is not None:
        sc.render.use_compositing = False          # the page has no post: compare the plain render
    objs0 = X.export_objects(sc)
    no_page = [o for o in objs0 if o.type == 'VOLUME'] + X.volume_meshes(objs0)
    for o in no_page:
        o.hide_render = True
    stills = {}
    for t in (() if NO_RENDER else spec['times']):
        sc.frame_set(frame_of(sc, t))
        p = os.path.join(out, f'eevee_{cams[t].name}_t{t:g}.png')
        sc.render.filepath = p
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        check(f'{name}: EEVEE still at t = {t:g} (through {cams[t].name}' + (f'; {len(no_page)} volume(s) off'
              if no_page else '') + ')', os.path.exists(p), f'{time.time() - t0:.1f} s')
        stills[t] = p
    for o in no_page:                              # back as the film has them: the export must leave them out itself
        o.hide_render = False
    # what Blender says at the check times
    arms = [o for o in sc.objects if o.type == 'ARMATURE' and not o.hide_render]
    truth = {}
    for t in spec['times']:
        sc.frame_set(frame_of(sc, t))
        d = {'objects': {}, 'bones': {}, 'cam': cams[t].matrix_world.copy(), 'cam_name': cams[t].name}
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
    # the export (the scene's XR settings, else the defaults: life size, standing where the camera stands, looking where
    # it looks, levelled)
    own_settings = bool(sc.get('eido_xr'))
    if not own_settings:
        X.set_xr(sc, street=1.0, name=name, landmarks=False)
        cv = sc.camera.matrix_world.to_3x3() @ Vector((0.0, 0.0, -1.0))
        want_facing = Vector((cv.x, cv.y, 0.0)).normalized()
    vr = os.path.join(out, 'vr')
    t0 = time.time()
    opts = spec.get('export', {})
    man = X.export_xr(vr, sc, name='scene', world_width=1024, world=not NO_RENDER, **opts)
    s = man['summary']
    if opts.get('max_image'):
        cap = opts['max_image']
        sizes = [im['size'] for im in s['images'] if im['size']]
        capped = man['report'].get('images_capped') or []
        check(f'{name}: the image cap ({cap} px): images scaled, every texture in the GLB within it, the texture grade '
              'no longer over', capped and sizes and max(max(wh) for wh in sizes) <= cap and s['quest']['textures'] != 'over',
              f"{len(capped)} scaled (e.g. {capped[0][1]} -> {capped[0][2]}), largest in the GLB "
              f"{max(max(wh) for wh in sizes) if sizes else None}, {s['texture_mb_gpu']} MB: {s['quest']['textures']}"
              if capped else f'nothing scaled; {s["texture_mb_gpu"]} MB')
    check(f'{name}: no GLB animation problem (channels on their own nodes)', not man['report'].get('channel_problems'),
          man['report'].get('channel_problems'))
    check(f'{name}: the bundle (scene.glb, scene.xr.json, index.html)', all(os.path.exists(os.path.join(vr, f)) for f in
          ('scene.glb', 'scene.xr.json', 'index.html')), f'{time.time() - t0:.1f} s, {s["bytes"] / 1e6:.1f} MB')
    if not own_settings:
        got = Vector(man['facing'])
        check(f'{name}: no XR settings of its own: you start where its camera stands, facing where it looks (levelled)',
              (got - Vector(to_three(*want_facing))).length < 1e-4, (man['facing'], man['start']))
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
        ci = g.node_by_name(d['cam_name'])
        if 'camera' not in g.json['nodes'][ci]:
            ci = next(c for c in g.json['nodes'][ci].get('children', []) if 'camera' in g.json['nodes'][c])
        mg = gltf_world(g, ci, t)
        vx, vy, vz = Matrix(G.world_matrices(g, t)[ci]).to_3x3() @ Vector((0, 0, -1))   # a glTF camera looks down -z
        fw_g = Vector((vx, -vz, vy))                                                      # (its own axes: no C^-1)
        fw_b = d['cam'].to_3x3() @ Vector((0, 0, -1))
        dp = (mg.translation - d['cam'].translation).length
        check(f"{name} t = {t:g}: the camera ({d['cam_name']}) where Blender has it, aimed the same",
              dp < 2e-3 and math.degrees(fw_g.angle(fw_b)) < 0.5, f'{dp * 1000:.2f} mm, {math.degrees(fw_g.angle(fw_b)):.2f} deg')
    # area lights (three RectAreaLights from the manifest): each shines down the light's own -z, its width along its x
    for r in man['rect_lights']:
        lo = bpy.data.objects[r['name']]
        rb = lo.matrix_world.to_3x3().normalized()
        qr = Quaternion((r['quaternion'][3], *r['quaternion'][:3]))
        a_dir = math.degrees((qr @ Vector((0, 0, -1))).angle(Vector(to_three(*(rb @ Vector((0, 0, -1)))))))
        a_x = math.degrees((qr @ Vector((1, 0, 0))).angle(Vector(to_three(*(rb @ Vector((1, 0, 0)))))))
        check(f"{name}: area light {r['name']} -> a RectAreaLight shining where it shines in Blender",
              a_dir < 0.05 and a_x < 0.05, f'{a_dir:.3f} deg off its -z, {a_x:.3f} deg off its x; '
              f"{r['width']:.2f} x {r['height']:.2f} m, {r['intensity']:.1f} W/sr/m2")
    baked = man['report']['materials'].get('baked', {})
    textured = [m['name'] for m in s['materials'] if m['baseColorTexture']]
    if name != 'stage':                            # (the theatre's boards and velvet are procedural: baked)
        check(f'{name}: image-textured materials went through as they are (none baked)', not baked,
              f'{len(textured)} textured materials; baked: {sorted(baked)}')
    vols = [o.name for o in no_page if o.type == 'MESH']
    if vols:
        nodes = {n.get('name') for n in g.json.get('nodes', [])}
        check(f'{name}: meshes of volume materials ({", ".join(vols)}) left out of the GLB and named in the warnings '
              '(not an opaque box round the set)', not (set(vols) & nodes) and all(
                  any(w.startswith(f'{v}: a volume material') for w in man['warnings']) for v in vols),
              [w for w in man['warnings'] if 'volume' in w])
    check(f'{name}: Quest grades reported', set(s['quest']) == {'triangles', 'draws', 'textures'},
          f"{s['triangles']} triangles, {s['draws']} draws, {s['texture_mb_gpu']} MB textures: {s['quest']}")
    with open(os.path.join(out, 'export_report.json'), 'w') as f:
        json.dump(man, f, indent=1, default=str)
    return {'bundle': os.path.relpath(vr, WORKTREE).replace('\\', '/'), 'camera': cam.name,
            'cameras': {f'{t:g}': c.name for t, c in cams.items()},
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

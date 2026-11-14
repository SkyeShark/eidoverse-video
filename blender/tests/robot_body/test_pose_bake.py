"""eidoblend.characters.pose_bake against eidoverse/pose_bake.js, and playing a shipped bake.

  1. bake_key: the Python key equals the JS bakeKey for the same files and extra (a .js with skip markers, a 38 MB VRM
     keyed by size + mtime, a missing path); a Python scene file's `# bake-key: skip` region drops out of its key
  2. Python writes, JS reads: my body's example performance (3 s, every humanoid bone, the armature, a keyed prop, the
     face's shape keys) recorded frame by frame from the keyed scene and saved; pose_bake.js load()s the file (its own
     refusals: a wrong key, a renamed track) and applies frames; every value equals Python's (float32)
  3. JS writes, Python reads: a synthetic bake saved by pose_bake.js loads here and applies to the same values
  4. the axes: apply(k) then record(k) gives back the stored row (the change of axes is its own inverse)
  5. key(): the bake keyed onto a SECOND copy of my body reproduces the first one's pose (bone heads, mm)
  6. the shipped eidoverse/assets/animations/ska_band/band_30fps.bin: its header, and the trumpet player (claudesona,
     claude_suit.vrm: the band's body without the wardrobe's outfit) with the trumpet (ska_trumpet.glb) played from it: the fingertips on the valve caps (mm),
     stills out/pose_bake_ska_trumpet_f<k>.png

    bash run_blender.sh blender/tests/robot_body/test_pose_bake.py [--no-render]
    # a GPU job; on a shared machine queue it with EIDO_GPU_WRAP (blender/tests/_where.py)
"""

import json
import math
import os
import sys
import time
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Quaternion, Vector  # noqa: E402

from eidoblend.characters import load_vrm  # noqa: E402
from eidoblend.characters import pose_bake as PB  # noqa: E402
from eidoblend.characters.robot import claude_robot_example  # noqa: E402
from eidoblend.characters.robot.example import directional, studio_environment  # noqa: E402

ARGS = S.argv()
RENDER = '--no-render' not in ARGS
R = {'started': time.strftime('%Y-%m-%d %H:%M:%S')}
T0 = time.time()
OK = True
DIR = os.path.join(S.OUT, 'pose_bake')
os.makedirs(DIR, exist_ok=True)
MJS = os.path.join(S.HERE, 'pose_bake_parity.mjs')
PBJS = os.path.join(S.REPO, 'eidoverse', 'pose_bake.js')


def log(*a):
    print('[pose_bake]', *a, flush=True)


def check(name, good, detail):
    global OK
    OK &= bool(good)
    R.setdefault('checks', {})[name] = {'pass': bool(good), 'detail': detail}
    print(f'{"PASS" if good else "FAIL"} {name}: {detail}', flush=True)


def js(*args):
    return S.run_deno(MJS, S.THREE_JS, PBJS, *args)


try:
    # ---- 1. the key
    jsf = os.path.join(DIR, 'scene_with_markers.js')
    with open(jsf, 'w', encoding='utf-8') as f:
        f.write('const solve = 1;\n/* bake-key: skip */ const camera = 2; /* bake-key: end */\nexport { solve };\n')
    pyf = os.path.join(DIR, 'scene_with_markers.py')
    vrm = os.path.join(S.REPO, 'eidoverse', 'assets', 'vrms', 'claude_robot.vrm')
    files = [jsf, vrm, os.path.join(DIR, 'not_there.json'), os.path.join(S.REPO, 'eidoverse', 'pose_bake.js')]
    extra = 'fps=30 MIC_ANG='
    spec = os.path.join(DIR, 'key_spec.json')
    with open(spec, 'w', encoding='utf-8') as f:
        json.dump({'files': files, 'extra': extra}, f)
    k_js = json.loads(js('key', spec).strip().splitlines()[-1])['key']
    k_py = PB.bake_key(files, extra)
    with open(jsf, 'w', encoding='utf-8') as f:            # an edit inside the skip region: the key must not change
        f.write('const solve = 1;\n/* bake-key: skip */ const camera = 3; const light = 4; /* bake-key: end */\nexport { solve };\n')
    k_py2 = PB.bake_key(files, extra)

    def write_py(body):
        with open(pyf, 'w', encoding='utf-8') as f:
            f.write(body)
        return PB.bake_key([pyf])
    kp1 = write_py('solve = 1\n# bake-key: skip\ncamera = 2\n# bake-key: end\n')
    kp2 = write_py('solve = 1\n# bake-key: skip\ncamera = 9\nlight = 1\n# bake-key: end\n')
    kp3 = write_py('solve = 2\n# bake-key: skip\ncamera = 9\nlight = 1\n# bake-key: end\n')
    R['keys'] = {'js': k_js, 'py': k_py, 'py_after_skip_edit': k_py2, 'py_scene': [kp1, kp2, kp3]}
    check('bake_key_matches_js', k_js == k_py == k_py2,
          f'JS {k_js}, Python {k_py}; after an edit inside the skip markers {k_py2}')
    check('bake_key_python_markers', kp1 == kp2 != kp3, f'a .py scene: {kp1} -> {kp2} (edit inside the skip) -> {kp3} (edit outside)')

    # ---- 2. Python writes, JS reads
    sc = S.C.clean_scene(30)
    ex = claude_robot_example(sc, duration=3.0, bloom=False)
    h = ex['h']
    prop = bpy.data.objects.new('prop_cube', bpy.data.meshes.new('prop_cube'))
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=0.1)
    bm.to_mesh(prop.data)
    bm.free()
    sc.collection.objects.link(prop)
    prop.rotation_mode = 'QUATERNION'
    for f in range(1, 91):
        a = f / 90 * 2 * math.pi
        prop.location = (0.6 * math.cos(a), 0.6 * math.sin(a), 1.0 + 0.1 * math.sin(2 * a))
        prop.rotation_quaternion = Quaternion((0.3, 0.5, 0.8), a)
        prop.scale = (1.0, 1.0 + 0.3 * math.sin(a), 1.0)
        prop.keyframe_insert('location', frame=f)
        prop.keyframe_insert('rotation_quaternion', frame=f)
        prop.keyframe_insert('scale', frame=f)
    face_mesh = next(o for o, _k, _w in h.expr['happy'])
    tracks = [PB.track(f'claude:{n}', (h, n)) for n in h.humanoid] + [PB.track('claude:scene', h.arm),
                                                                       PB.track('prop', prop)]
    morphs = [PB.morph('face', face_mesh)]
    N = 90
    key = PB.bake_key([os.path.join(S.REPO, 'blender', 'eidoblend', 'characters', 'robot', 'rig.py')], 'test')
    bfile = os.path.join(DIR, f'robot_example_{key}.bin')
    stale = os.path.join(DIR, 'robot_example_' + 'a' * 24 + '.bin')
    with open(stale, 'wb') as f:
        f.write(b'old')
    bake = PB.create_pose_bake(tracks=tracks, morphs=morphs, frames=N, fps=30, file=bfile, key=key)
    for k in range(N):
        sc.frame_set(k + 1)
        bake.record(k)
    info = bake.save()
    R['python_bake'] = info
    check('save_supersedes_stale', os.path.exists(bfile) and not os.path.exists(stale),
          f'{os.path.basename(bfile)} written ({info}); the older bake of the same name removed')
    ks = [0, 1, 10, 45, 89]
    fspec = os.path.join(DIR, 'frames.json')
    with open(fspec, 'w', encoding='utf-8') as f:
        json.dump({'frames': ks}, f)
    jout = os.path.join(DIR, 'js_read.json')
    js('read', bfile, fspec, jout)
    with open(jout, encoding='utf-8') as f:
        J = json.load(f)
    worst = 0.0
    for k in ks:
        a = np.array(J['frames'][str(k)], dtype=np.float64)
        b = bake.values(k).astype(np.float64)
        worst = max(worst, float(np.max(np.abs(a - b))))
    check('js_reads_python_bake', J['ok'] and worst == 0.0 and all(J['refused'].values()),
          f'pose_bake.js load() {J["ok"]}, {len(ks)} frames applied, largest difference {worst} (float32 exact); '
          f'refused {J["refused"]}; header {J["header"]}')

    # ---- 4. the axes: apply then record gives back the row
    rt = 0.0
    for k in ks:
        sc.frame_set(1)
        want = bake.values(k).copy()
        bake.apply(k)
        bake.apply_morphs(k)
        bpy.context.view_layer.update()
        rows = []
        for t in bake.tracks:
            rows.extend(t['target'].read())
        for m, n in zip(bake.morphs, bake.mN):
            rows.extend(kb.value for kb in PB._keys(m['mesh'])[:n])
        got = np.array(rows, dtype=np.float32)
        d = np.abs(got.astype(np.float64) - want.astype(np.float64))
        # a quaternion and its negation are one turn
        for i in range(bake.T):
            q1, q2 = got[i * 10 + 3:i * 10 + 7], want[i * 10 + 3:i * 10 + 7]
            if float(np.dot(q1, q2)) < 0:
                d[i * 10 + 3:i * 10 + 7] = np.abs(-q1.astype(np.float64) - q2.astype(np.float64))
        rt = max(rt, float(d.max()))
    check('apply_record_roundtrip', rt < 2e-6, f'apply(k) then record(k): largest difference {rt:.2e}')

    # ---- 3. JS writes, Python reads
    rng = np.random.default_rng(7)
    names = ['a', 'b', 'c']
    vals = []
    for k in range(12):
        row = []
        for i in range(3):
            q = rng.normal(size=4)
            q /= np.linalg.norm(q)
            row += list(rng.normal(size=3)) + list(q) + list(1 + 0.2 * rng.random(3))
        row += [float(rng.random()), 0.25]
        vals.append([float(x) for x in row])
    wspec = os.path.join(DIR, 'js_write_spec.json')
    with open(wspec, 'w', encoding='utf-8') as f:
        json.dump({'tracks': names, 'morphs': [{'name': 'm', 'n': 2}], 'frames': 12, 'fps': 24, 'key': 'c' * 24,
                   'values': vals}, f)
    jfile = os.path.join(DIR, 'js_written_' + 'c' * 24 + '.bin')
    js('write', wspec, jfile)
    empties = []
    for n in names:
        e = bpy.data.objects.new('js_' + n, None)
        sc.collection.objects.link(e)
        empties.append(e)
    mobj = bpy.data.objects.new('js_m', bpy.data.meshes.new('js_m'))
    sc.collection.objects.link(mobj)
    mobj.shape_key_add(name='Basis')
    mobj.shape_key_add(name='k0')
    mobj.shape_key_add(name='k1')
    hdr = PB.bake_header(jfile)
    b2 = PB.create_pose_bake(tracks=[PB.track(n, e) for n, e in zip(names, empties)], morphs=[PB.morph('m', mobj)],
                             frames=hdr['frames'], fps=hdr['fps'], file=jfile, key=hdr['key'])
    loaded = b2.load()
    w2 = 0.0
    for k in range(12):
        b2.apply(k)
        b2.apply_morphs(k)
        row = []
        for t in b2.tracks:
            row.extend(t['target'].read())
        row.extend(kb.value for kb in mobj.data.shape_keys.key_blocks[1:])
        want = np.array(vals[k], dtype=np.float32).astype(np.float64)
        got = np.array(row, dtype=np.float64)
        for i in range(3):
            if float(np.dot(got[i * 10 + 3:i * 10 + 7], want[i * 10 + 3:i * 10 + 7])) < 0:
                got[i * 10 + 3:i * 10 + 7] *= -1
        w2 = max(w2, float(np.max(np.abs(got - want))))
    check('python_reads_js_bake', loaded and w2 < 2e-6,
          f'load() {loaded}; header cols {len(hdr["cols"])}, consts {len(hdr["consts"])}; applied and read back within {w2:.2e}')

    # ---- 5. key(): the bake keyed onto a second copy of my body
    h2 = load_vrm('claude_robot', name='claude_copy', location=(1.5, 0.0, 0.0))
    tracks2 = [PB.track(f'claude:{n}', (h2, n)) for n in h2.humanoid] + [PB.track('claude:scene', None), PB.track('prop', None)]
    fm2 = next(o for o, _k, _w in h2.expr['happy'])
    b3 = PB.create_pose_bake(tracks=tracks2, morphs=[PB.morph('face', fm2)], frames=N, fps=30, file=bfile, key=key)
    ok3 = b3.load()
    kk = b3.key(frame_start=1, name='claude_copy|bake') if ok3 else None
    worst_mm = 0.0
    for f in (1, 30, 61, 90):
        sc.frame_set(f)
        for n in ('head', 'leftHand', 'rightIndexDistal', 'leftFoot', 'rightToes'):
            p1 = h.arm.matrix_world @ h.arm.pose.bones[h.humanoid[n]].head
            p2 = h2.arm.matrix_world @ h2.arm.pose.bones[h2.humanoid[n]].head
            # in each armature's own frame: the first body's place (its set-down) rides its 'claude:scene' track,
            # which the copy leaves unbound (it stands where it was loaded)
            worst_mm = max(worst_mm, 1000 * ((h2.arm.matrix_world.inverted() @ p2) - (h.arm.matrix_world.inverted() @ p1)).length)
    R['key_onto_copy'] = kk
    check('key_onto_second_body', ok3 and worst_mm < 0.05,
          f'the copy keyed from the file ({kk}) holds the first body\'s pose: bone heads (in each armature\'s frame) within '
          f'{worst_mm:.4f} mm at frames 1, 30, 61, 90')

    # ---- 6. the shipped ska bake: the trumpet player
    ska = os.path.join(S.REPO, 'eidoverse', 'assets', 'animations', 'ska_band', 'band_30fps.bin')
    H = PB.bake_header(ska)
    R['ska_header'] = {k: (v if not isinstance(v, (list, dict)) else len(v)) for k, v in H.items()}
    bpy.ops.wm.read_homefile(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = 30
    studio_environment(sc, 0.8, 0x121214)
    directional('key', (-2.2, 3.2, 3.0), 0xfff4e8, 2.2)
    directional('rim', (2.5, 2.0, -3.0), 0xdfe8ff, 1.0)
    from eidoblend.characters.robot.example import floor_disc
    floor_disc(radius=8.0)
    player = 'trumpet'
    # the band's VRM is claude_suit_wardrobe.vrm wearing the wardrobe's two-tone outfit (the wardrobe is not ported: its
    # garments would all show at once); claude_suit.vrm is the same body (its humanoid rest matches to 1.3e-6 m)
    pv = load_vrm('claude_suit', name='player_' + player)
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(S.REPO, 'eidoverse', 'assets', 'models', f'ska_{player}.glb'))
    inst = {o.name.split('.')[0]: o for o in bpy.data.objects if o not in before}
    holder = bpy.data.objects.new('holder_' + player, None)
    holder_scene = bpy.data.objects.new('holder_scene_' + player, None)
    sc.collection.objects.link(holder)
    sc.collection.objects.link(holder_scene)
    holder_scene.parent = holder
    roots = [o for o in inst.values() if o.parent is None]
    for o in roots:
        o.parent = holder_scene
        o.matrix_parent_inverse = Matrix()
    mark = {'trumpet': (-1.7, 0.5, 16.0)}[player]
    root = bpy.data.objects.new('root_' + player, None)
    sc.collection.objects.link(root)
    root.location = (mark[0], -mark[1], 0.0)
    root.rotation_euler = (0.0, 0.0, math.radians(mark[2]))
    pv.arm.parent = root
    pv.arm.matrix_parent_inverse = Matrix()
    tr = []
    for name in H['tracks']:
        obj = None
        if name.startswith(player + ':'):
            part = name[len(player) + 1:]
            if part in pv.humanoid:
                obj = (pv, part)
            elif part == 'scene':
                obj = pv.arm
            elif part.startswith('holder#'):
                i, nn = part[len('holder#'):].split(':', 1)
                obj = holder if i == '0' else holder_scene if i == '1' else inst.get(nn)
        tr.append(PB.track(name, obj))
    ska_bake = PB.create_pose_bake(tracks=tr, frames=H['frames'], fps=H['fps'], file=ska, key=H['key'])
    ok_ska = ska_bake.load()
    # a window where the valves move most: the tp_v1..3 tracks' columns
    vi = [i for i, n in enumerate(H['tracks']) if n.startswith(player + ':holder#') and n.split(':')[-1] in ('tp_v1', 'tp_v2', 'tp_v3')]
    tab = ska_bake._play['table']
    act = np.zeros(H['frames'])
    for i in vi:
        act[1:] += np.abs(np.diff(tab[:, i * 10 + 1]))
    win = 120
    cs = np.convolve(act, np.ones(win), 'valid')
    k0 = int(np.argmax(cs))
    keyed = ska_bake.key(frame_start=1, frames=range(k0, k0 + win), name='ska_' + player)
    sc.frame_start, sc.frame_end = 1, win
    R['ska'] = {'loaded': ok_ska, 'window_frames': [k0, k0 + win], 'window_s': [round(k0 / 30, 2), round((k0 + win) / 30, 2)],
                'keyed': keyed, 'bound_tracks': sum(1 for t in tr if t['obj'] is not None)}
    # the fingertips on the valve caps (index, middle, ring on tp_v1, tp_v2, tp_v3), the hand's bones' tails vs the caps' tops
    dists = {'index': [], 'middle': [], 'ring': []}
    for f in range(1, win + 1, 3):
        sc.frame_set(f)
        for fing, valve in (('index', 'tp_v1'), ('middle', 'tp_v2'), ('ring', 'tp_v3')):
            pb = pv.arm.pose.bones[pv.humanoid['right' + fing.capitalize() + 'Distal']]
            tip = pv.arm.matrix_world @ pb.tail
            v = inst[valve]
            bb = [v.matrix_world @ Vector(c) for c in v.bound_box]
            top = max(bb, key=lambda p: p.z)
            cap = sum(bb, Vector()) / 8
            cap.z = top.z
            dists[fing].append(1000 * (tip - cap).length)
    R['ska']['fingertip_to_cap_mm'] = {k: [round(float(np.min(v)), 1), round(float(np.median(v)), 1), round(float(np.max(v)), 1)]
                                        for k, v in dists.items()}
    check('ska_trumpet_fingers_on_valves', ok_ska and all(np.median(v) < 30 for v in dists.values()),
          f'the shipped bake loads ({R["ska"]["bound_tracks"]} of {len(tr)} tracks bound) and plays s {R["ska"]["window_s"]}; '
          f'fingertip (distal bone tail) to valve cap top, min / median / max mm: {R["ska"]["fingertip_to_cap_mm"]}')
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, 'pose_bake_ska_trumpet.blend'), compress=True)
    if RENDER:
        from eidoblend.look import render_settings as rs
        rs.apply_auto_enhance(sc, 'probe')
        sc.view_settings.exposure = 0.0
        cam = S.C.camera('cam', 50.0)
        Rz = Quaternion((0, 0, 1), math.radians(mark[2]))
        base = Vector((mark[0], -mark[1], 0.0))
        out = {}
        for f, (off, aimz, lens) in ((1, ((0.9, -2.6, 1.55), 1.2, 50.0)), (60, ((0.7, -1.7, 1.6), 1.4, 60.0)),
                                     (100, ((-1.0, -1.5, 1.75), 1.4, 60.0))):
            cam.data.lens = lens
            S.C.aim(cam, base + Rz @ Vector(off), base + Vector((0.0, 0.0, aimz)) + Rz @ Vector((0.0, -0.25, 0.0)))
            p = os.path.join(S.OUT, f'pose_bake_ska_trumpet_f{f:03d}.png')
            out[os.path.basename(p)] = S.C.still(sc, cam, f, p)
        R['renders'] = out
    R['ok'] = OK
except Exception:  # noqa: BLE001
    R['ok'] = False
    R['error'] = traceback.format_exc()
    log(R['error'])
R['seconds'] = round(time.time() - T0, 1)
S.write_json('pose_bake.json', R)
log('done', R['ok'], R['seconds'], 's')

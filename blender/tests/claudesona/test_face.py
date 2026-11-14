"""The claudesona's face (claudesona_face.js ported): both mouths installed on claude_suit.vrm at the films' 0.87,
measured on the evaluated mesh against the face dome, the drivers run beside the JS module itself, and probe stills
from the front, 40 and 70 degrees (every hovering mouth on this rig passed a front view).

Checks:
    the mouth plate has the vertices three-vrm's isMouthPlate finds (the same primitive, the same space)
    mouth.seat / wide / round put every plate vertex 1.5 mm proud of the dome (the raycast standoff), where the rig's
        own 'show MMD mouth' at 1.25 floats it off the face (the reason for the port)
    the painted features sit 1.8 mm proud at rest, and their expression targets end on the dome
    the viseme mouth: 10 viseme keys + the seat, every opening on the dome
    makeSuitMouth, makeVisemeTrack, makeFaceTrack, mergeMax and the constants equal the JS module's on the same input
Stills: out/face_suit_sheet.png (rows rest / aa / oh / the rig's own mouth at 1.25; columns 0, 40, 70 deg),
out/face_expr_sheet.png (smile, soft, blush, frown, blink at 40 deg; the raw rig beside the re-seated one at 70 deg),
out/face_visemes_sheet.png (the ten visemes at 0 and 40 deg).

    bash run_blender.sh blender/tests/claudesona/test_face.py [--no-render]
    # a GPU job; on a shared machine queue it with EIDO_GPU_WRAP (blender/tests/_where.py)
"""

import json
import math
import os
import random
import sys
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.characters import load_vrm  # noqa: E402
from eidoblend.characters.claudesona import _mesh as MM  # noqa: E402
from eidoblend.characters.claudesona import face as F  # noqa: E402

ARGS = S.argv()
RENDER = '--no-render' not in ARGS
SCALE = 0.87


def evaluated_g(o, plate):
    """o's evaluated (shape-keyed) vertices in the plate's glTF geometry space"""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    P = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', P)
    ev.to_mesh_clear()
    return MM.apply(MM.to_space(o, plate), P.reshape(-1, 3))


def set_keys(o, values):
    for kb in o.data.shape_keys.key_blocks[1:]:
        kb.value = values.get(kb.name, 0.0)
    bpy.context.view_layer.update()


def proud(face, P):
    """height above the dome (m) of points P (plate space) by the face's own ray, nan where the ray misses"""
    out = []
    for x, y, z in P:
        hz = face.parts.ray(x, y)
        out.append(np.nan if hz is None else z - hz)
    return np.array(out)


def drivers(C, R):
    """the drivers against the JS module on the same input"""
    rng = random.Random(7)
    times, vis = [], []
    t = 0.0
    while t < 6.0:                                   # syllables with consonant dips, rests, vowel changes
        seg = int(t / 0.45) % 7
        v = {k: 0.0 for k in F.VOWELS}
        if seg not in (3, 6):
            k = F.VOWELS[(int(t / 0.45) * 3) % 5]
            dip = (t % 0.45) > 0.38
            v[k] = (0.06 if dip else 0.33) * (0.8 + 0.2 * rng.random())
            v[F.VOWELS[(F.VOWELS.index(k) + 1) % 5]] = 0.05 * rng.random()
        times.append(round(t, 6))
        vis.append(v)
        t += 1 / 30
    events = [{'t0': 0.2, 't1': 0.5, 'v': 'AA'}, {'t0': 0.52, 't1': 0.6, 'v': 'MBP'}, {'t0': 0.62, 't1': 1.4, 'v': 'O'},
              {'t0': 1.45, 't1': 1.55, 'v': None}, {'t0': 1.6, 't1': 1.7, 'v': 'FV'}, {'t0': 1.75, 't1': 2.6, 'v': 'E'},
              {'t0': 3.0, 't1': 3.3, 'v': 'U'}, {'t0': 3.32, 't1': 3.5, 'v': 'CH'}, {'t0': 3.52, 't1': 4.4, 'v': 'I'}]
    TL = {'sections': [{'name': 'verse', 't0': 0.5, 't1': 2.5}, {'name': 'chorus', 't0': 2.5, 't1': 4.5}],
          'captions': [{'text': 'daisy daisy', 't0': 0.6, 't1': 1.8}, {'text': 'give me your answer', 't0': 2.6, 't1': 3.9},
                       {'text': 'goodbye', 't0': 4.0, 't1': 4.6}]}
    face_opts = {'sectionBase': {'verse': {'smile': 0.3}, 'chorus': {'smile': 0.6, 'wide': 0.2}},
                 'lineCues': [['goodbye', 'i', {'soft': 0.8, 'frown': 0.2}], ['answer', '', {'blush': 0.5, 'jaw': 0.4}]],
                 'closeAfterLast': True}
    merge = [[{'a': 0.2, 'b': 0.5}, {'a': 0.7}, {}], [{'Blink': 1}, {'Blink': 0.3, 'Smile': 0.2}]]
    job = {'root': S.REPO, 'times': times, 'visemes': vis, 'suit': {'inputMax': 0.35}, 'events': events, 'TL': TL,
           'face': face_opts, 'merge': merge}
    ref = S.run_mjs('face_parity.mjs', job, 'face_drivers')
    m = F.make_suit_mouth(input_max=0.35)
    suit = [m.update(t, v) for t, v in zip(times, vis)]
    tr = F.make_viseme_track(events)
    track = [tr.at(t) for t in times]
    ft = F.make_face_track(TL, section_base=face_opts['sectionBase'],
                           line_cues=[(__import__('re').compile(s, __import__('re').I if 'i' in fl else 0), feel)
                                      for s, fl, feel in face_opts['lineCues']], close_after_last=True)
    feel = [ft.at(t) for t in times]
    mg = [F.merge_max(*ws) for ws in merge]

    def diff(a, b):
        if isinstance(a, dict):
            ks = set(a) | set(b)
            return max([diff(a.get(k, 0), b.get(k, 0)) for k in ks] or [0.0])
        return abs(float(a) - float(b))
    d_suit = max(diff(a, b) for a, b in zip(suit, ref['suit']))
    d_track = max(diff(a, b) for a, b in zip(track, ref['track']))
    d_feel = max(diff(a, b) for a, b in zip(feel, ref['feel']))
    d_merge = max(diff(a, b) for a, b in zip(mg, ref['merge']))
    opened = sum(1 for w in suit if w.get(F.MOUTH_OPEN, 0) > 0)
    R['drivers'] = {'frames': len(times), 'suit_max_diff': d_suit, 'track_max_diff': d_track, 'feel_max_diff': d_feel,
                    'merge_max_diff': d_merge, 'suit_open_frames': opened}
    C.check('makeSuitMouth: identical to the JS module on 180 frames', d_suit < 1e-9, f'max diff {d_suit:.2e}, open {opened} frames')
    C.check('makeVisemeTrack: identical to the JS module', d_track < 1e-9, f'max diff {d_track:.2e}')
    C.check('makeFaceTrack: identical to the JS module', d_feel < 1e-9, f'max diff {d_feel:.2e}')
    C.check('mergeMax: identical', d_merge < 1e-12, f'{d_merge:.2e}')
    cst = ref['constants']
    same = (cst['SUIT_VISEMES'] == F.SUIT_VISEMES and cst['VISEME_SHAPES'] == {k: {kk: vv for kk, vv in v.items()} for k, v in F.VISEME_SHAPES.items()}
            and cst['LINE_WARP'] == F.LINE_WARP and cst['VISEMES'] == F.VISEMES and cst['PHONE_VISEME'] == F.PHONE_VISEME
            and cst['MOUTH_OPEN'] == F.MOUTH_OPEN and cst['MOUTH_ROUND'] == F.MOUTH_ROUND)
    C.check('the constants (SUIT_VISEMES, VISEME_SHAPES, LINE_WARP, VISEMES, PHONE_VISEME) equal the JS module', same)


def suit_mouth(C, R, h):
    ref = S.three_vrm({'vrm': h.path.replace('\\', '/'), 'scale': SCALE, 'fps': 30, 'frames': 1, 'turn': [[0, 0]],
                       'nod': [[0, 0]], 'tie': None, 'faces': True}, 'face_claude_suit')
    three_plate = [m for m in ref['face']['meshes'] if 'Material' in m['mats']]
    face = F.install_suit_mouth(h)
    R['suit_install'] = face.report
    n3 = three_plate[0]['mouthPlate'] if three_plate else None
    C.check("the mouth plate: three-vrm's isMouthPlate vertex count", face.report['mouth_plate_vertices'] == n3,
            f"blender {face.report['mouth_plate_vertices']} / three {n3}")
    plate = face.plate
    mouth = face.parts.plate_idx[F.is_mouth_plate(MM.apply(MM.to_space(plate, plate), MM.coords(plate)[face.parts.plate_idx]))]
    res = {}
    for name, vals in (('rest', {}), ('seat', {F.KEY_PREFIX + 'mouth.seat': 1.0}),
                       ('aa', face.values({F.MOUTH_OPEN: 1.0, F.MOUTH_ROUND: 0.0})),
                       ('oh', face.values({F.MOUTH_OPEN: 0.95, F.MOUTH_ROUND: 0.8})),
                       ('rig_show_1.25', {'show MMD mouth': 1.25}),
                       ('rig_1.25', {'show MMD mouth': 1.25, 'あ': 2.0, 'JawOpen': 1.5})):
        if name in ('aa', 'oh'):
            vals = {kn: v for (on, kn), v in vals.items() if on == plate.name}
        set_keys(plate, vals)
        G = evaluated_g(plate, plate)[mouth]
        pr = proud(face, G)
        res[name] = {'proud_mm_median': round(float(np.nanmedian(pr)) * 1000, 3),
                     'proud_mm_min': round(float(np.nanmin(pr)) * 1000, 3), 'proud_mm_max': round(float(np.nanmax(pr)) * 1000, 3),
                     'on_dome': int(np.sum(~np.isnan(pr)))}
    set_keys(plate, {})
    R['mouth_proud'] = res
    for k in ('seat', 'aa', 'oh'):
        r = res[k]
        C.check(f'mouth {k}: every plate vertex on the dome, 1.5 mm proud',
                abs(r['proud_mm_min'] - 1.5) < 0.2 and abs(r['proud_mm_max'] - 1.5) < 0.2,
                f"{r['proud_mm_min']}..{r['proud_mm_max']} mm over {r['on_dome']} vertices")
    sp = {k: res[k]['proud_mm_max'] - res[k]['proud_mm_min'] for k in ('aa', 'rig_show_1.25', 'rig_1.25')}
    C.check("the rig's own flat mouth cuts through the dome instead of following it (why it is never driven)",
            sp['rig_show_1.25'] > 3.0 and sp['rig_1.25'] > 3.0 and sp['aa'] < 0.5,
            f"depth spread over the plate: rig show 1.25 {sp['rig_show_1.25']:.1f} mm "
            f"({res['rig_show_1.25']['proud_mm_min']}..{res['rig_show_1.25']['proud_mm_max']}), the recipe's aa "
            f"{sp['rig_1.25']:.1f} mm, the port's aa {sp['aa']:.2f} mm")
    # the painted features at rest and at the end of their targets
    idx = face.parts.plate_idx
    G0 = evaluated_g(plate, plate)[idx]
    feat = ~F.is_mouth_plate(G0)
    pr0 = proud(face, G0[feat])
    near = np.abs(pr0 - 0.0018) < 0.012
    R['features_rest_proud_mm'] = [round(float(np.nanmin(pr0[near])) * 1000, 3), round(float(np.nanmax(pr0[near])) * 1000, 3)]
    C.check('the painted features rest 1.8 mm proud of the dome',
            abs(R['features_rest_proud_mm'][0] - 1.8) < 0.2 and abs(R['features_rest_proud_mm'][1] - 1.8) < 0.2,
            f"{R['features_rest_proud_mm']} mm over {int(near.sum())} vertices")
    ends = {}
    for kn in ('EyeClosedLeft', 'EyeWide', 'MouthFrown', 'EyeLookDownLeft', 'Smile'):
        if kn not in plate.data.shape_keys.key_blocks:
            continue
        set_keys(plate, {kn: 1.0})
        G1 = evaluated_g(plate, plate)[idx]
        moved = np.linalg.norm(G1 - G0, axis=1) > 1e-6
        pr = proud(face, G1[moved & feat])
        ends[kn] = [round(float(np.nanmin(pr)) * 1000, 2), round(float(np.nanmax(pr)) * 1000, 2), int((moved & feat).sum())]
    set_keys(plate, {})
    R['target_ends_proud_mm'] = ends
    worst = max(max(abs(a - 1.8), abs(b - 1.8)) for a, b, _n in ends.values())
    C.check("expression targets end on the dome (blink, wide, frown, look, smile)", worst < 0.5,
            f'worst {worst:.2f} mm off 1.8: {ends}')
    return face


def viseme_mouth(C, R, h):
    face = F.install_viseme_mouth(h)
    R['viseme_install'] = face.report
    keys = face.plate.data.shape_keys.key_blocks
    C.check('the viseme mouth: seat + 10 viseme keys', all((F.KEY_PREFIX + 'viseme.' + k) in keys for k in ['seat'] + F.VISEMES),
            ', '.join(F.VISEMES))
    plate = face.plate
    idx = face.parts.plate_idx
    G0 = evaluated_g(plate, plate)[idx]
    mp = F.is_mouth_plate(G0)
    res = {}
    for v in F.VISEMES:
        vals = {kn: x for (on, kn), x in face.values({'viseme': {v: 1.0}, 'mouth': 1.0}).items() if on == plate.name}
        set_keys(plate, vals)
        G = evaluated_g(plate, plate)[idx]
        pr = proud(face, G[mp])
        res[v] = [round(float(np.nanmin(pr)) * 1000, 2), round(float(np.nanmax(pr)) * 1000, 2)]
    set_keys(plate, {})
    R['viseme_proud_mm'] = res
    opens = [v for v in F.VISEMES if v != 'MBP']
    ok = all(-0.5 < res[v][0] and res[v][1] < 3.5 for v in opens)
    C.check('every viseme opening lies on the dome (front surface 1.5 mm proud, the lens behind it)', ok,
            '; '.join(f'{v} {res[v][0]}..{res[v][1]}' for v in opens))
    return face


def studio_shots(h, face, tag, states, yaws, size, paths):
    """stills of one character's face: states [(name, weights or callable)] x yaws (camera orbiting the head)"""
    sc = bpy.context.scene
    hb = h.arm.matrix_world @ h.arm.pose.bones[h.humanoid['head']].head
    fo = MM.find(h, 'face')[0]
    centre = sum((fo.matrix_world @ Vector(c) for c in fo.bound_box), Vector()) / 8
    cam = S.camera(f'{tag}_cam', lens=85)
    S.probe_render(sc, res=size, samples=16)
    for name, w in states:
        for yaw in yaws:
            if callable(w):
                w()
            else:
                face.set(w)
            a = math.radians(yaw)
            d = 0.78
            pos = Vector((centre.x - d * math.sin(a), centre.y - d * math.cos(a), centre.z + 0.01))
            S.aim(cam, pos, centre)
            p = os.path.join(S.OUT, f'face_{tag}_{name}_y{yaw:02d}.png')
            sc.camera = cam
            sc.render.filepath = p
            bpy.ops.render.render(write_still=True)
            paths.append(p)
    _ = hb


def main():
    R, C = {}, S.Checks('face')
    try:
        drivers(C, R)
        sc = S.clean_scene(30)
        hA = load_vrm('claude_suit', name='suit_mouth', location=(0.0, 0.0, 0.0))
        hB = load_vrm('claude_suit', name='viseme_mouth', location=(3.0, 0.0, 0.0))
        hC = load_vrm('claude_suit', name='raw_rig', location=(-3.0, 0.0, 0.0))
        for h in (hA, hB, hC):
            h.arm.scale = (SCALE,) * 3
        bpy.context.view_layer.update()
        fA = suit_mouth(C, R, hA)
        fB = viseme_mouth(C, R, hB)
        if RENDER:
            S.turntable_studio(sc, light=0.7)
            paths = []
            states = [('rest', {}), ('aa', {F.MOUTH_OPEN: 1.0}), ('oh', {F.MOUTH_OPEN: 0.95, F.MOUTH_ROUND: 0.8}),
                      ('rig125', lambda: set_keys(fA.plate, {'show MMD mouth': 1.25, 'あ': 2.0, 'JawOpen': 1.5}))]
            studio_shots(hA, fA, 'suit', states, (0, 40, 70), (360, 360), paths)
            R['suit_sheet'] = S.sheet(paths, os.path.join(S.OUT, 'face_suit_sheet.png'), cols=3)
            fA.set({})
            ex = [('smile', {'Smile': 0.6, 'MouthSmileLeft': 0.6, 'MouthSmileRight': 0.6}),
                  ('soft', {'EyeClosedLeft': 0.8, 'EyeClosedRight': 0.8}), ('blush', {'Blush': 1.0}),
                  ('frown', {'MouthFrown': 0.7}), ('blink', {'Blink': 1.0})]
            p2 = []
            studio_shots(hA, fA, 'expr', ex, (40,), (300, 300), p2)
            fA.set({'EyeClosedLeft': 0.8, 'EyeClosedRight': 0.8, 'Blush': 1.0})
            studio_shots(hA, fA, 'fixed', [('softblush', lambda: None)], (70,), (300, 300), p2)
            raw = [o for o in hC.meshes if o.data.shape_keys and 'Blush' in o.data.shape_keys.key_blocks][0]
            studio_shots(hC, None, 'raw', [('softblush', lambda: set_keys(raw, {'EyeClosedLeft': 0.8, 'EyeClosedRight': 0.8,
                                                                                'Blush': 1.0}))], (70,), (300, 300), p2)
            R['expr_sheet'] = S.sheet(p2, os.path.join(S.OUT, 'face_expr_sheet.png'), cols=7)
            fA.set({})
            p3 = []
            vstates = [(v, {'viseme': {v: 1.0}, 'mouth': 1.0}) for v in F.VISEMES]
            studio_shots(hB, fB, 'vis', vstates, (0, 40), (260, 260), p3)
            order = [p3[2 * i] for i in range(10)] + [p3[2 * i + 1] for i in range(10)]
            R['viseme_sheet'] = S.sheet(order, os.path.join(S.OUT, 'face_visemes_sheet.png'), cols=10)
    except Exception:
        traceback.print_exc()
        R['error'] = traceback.format_exc()
        C.check('ran without an exception', False)
    R['checks'] = C.rows
    R['all_pass'] = C.all_pass and 'error' not in R
    with open(os.path.join(S.OUT, 'face.json'), 'w', encoding='utf-8') as f:
        json.dump(R, f, indent=1, default=str)
    print('[face] ALL PASS' if R['all_pass'] else '[face] SOME FAILED', flush=True)


main()

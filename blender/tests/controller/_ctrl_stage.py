"""The controller tests' shared stage (tests only): courses from the course package (eidoblend.course, the port of
terrain_base.js) dressed in CC0 sets from the shared texture cache, round one's probe light (tests/characters/_stage.py),
PASS / FAIL bookkeeping, and the shot list a test saves beside its .blend for render_shots.py, so a bake runs on the CPU
and only the stills take the shared GPU slot:

    import _ctrl_stage as T
    sc = T.S.clean_scene(fps=30)
    course = T.course({'type': 'obstacle_course', 'segments': [...]})
    R = T.Report('course_claude_robot')
    R.check('the walk stops on its mark', d < 0.05, f'{d * 100:.1f} cm')
    T.save(R, sc, shots)          # out/<tag>.blend + out/<tag>_shots.json + out/<tag>.json
"""

import json
import math
import os
import sys
import time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'characters'))
import _stage as S  # noqa: E402,F401  (round one's probe stage)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)


def argv():
    return S.argv()


def arg(args, name, default=None):
    return args[args.index(name) + 1] if name in args else default


# ------------------------------------------------------------------------------------------------ materials
def pbr_material(name, set_name, tint=None, tint_mix=0.0, tile=1.0, roughness=0.7, metallic=None):
    """a Principled material from a CC0 set of the shared cache on the mesh's metre UVs (tile: metres per repeat);
    tint mixes a colour (hex) into the albedo. Without the set: a plain material."""
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes['Principled BSDF']
    ts = S.texture_set(set_name) if set_name else None
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (1.0 / tile, 1.0 / tile, 1.0)
    nt.links.new(tc.outputs['UV'], mp.inputs['Vector'])
    rgb = None
    if tint is not None:
        rgb = tuple((((tint >> sh) & 255) / 255.0) ** 2.2 for sh in (16, 8, 0))

    def img(path, colour):
        n = nt.nodes.new('ShaderNodeTexImage')
        n.image = bpy.data.images.load(path, check_existing=True)
        n.image.colorspace_settings.name = 'sRGB' if colour else 'Non-Color'
        nt.links.new(mp.outputs['Vector'], n.inputs['Vector'])
        return n
    if ts and ts.get('color'):
        out = img(ts['color'], True).outputs['Color']
        if ts.get('ao'):
            mul = nt.nodes.new('ShaderNodeMix')
            mul.data_type, mul.blend_type = 'RGBA', 'MULTIPLY'
            mul.inputs['Factor'].default_value = 0.6
            nt.links.new(out, mul.inputs['A'])
            nt.links.new(img(ts['ao'], False).outputs['Color'], mul.inputs['B'])
            out = mul.outputs['Result']
        if rgb is not None and tint_mix > 0:
            tm = nt.nodes.new('ShaderNodeMix')
            tm.data_type, tm.blend_type = 'RGBA', 'MULTIPLY'
            tm.inputs['Factor'].default_value = tint_mix
            nt.links.new(out, tm.inputs['A'])
            tm.inputs['B'].default_value = rgb + (1.0,)
            out = tm.outputs['Result']
        nt.links.new(out, bsdf.inputs['Base Color'])
        if ts.get('rough'):
            nt.links.new(img(ts['rough'], False).outputs['Color'], bsdf.inputs['Roughness'])
        if ts.get('normal'):
            nm = nt.nodes.new('ShaderNodeNormalMap')
            nt.links.new(img(ts['normal'], False).outputs['Color'], nm.inputs['Color'])
            nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    else:
        bsdf.inputs['Base Color'].default_value = (rgb or (0.35, 0.35, 0.35)) + (1.0,)
        bsdf.inputs['Roughness'].default_value = roughness
    if metallic is not None:
        bsdf.inputs['Metallic'].default_value = metallic
        bsdf.inputs['Roughness'].default_value = roughness
    return mat


def course_materials():
    """the course pieces in CC0 sets: paving on the ground, the engine's terracotta (0xd97550) over concrete on the
    solids, brushed metal on the ladder"""
    return {'ground': pbr_material('ctrl_paving', 'PavingStones128_1k', tile=1.5),
            'obstacle': pbr_material('ctrl_concrete', 'Concrete034_2k', tint=0xd97550, tint_mix=0.55, tile=1.0),
            'rail': pbr_material('ctrl_metal', 'Metal009_1k', tint=0xb8c2cc, tint_mix=0.3, tile=0.5, metallic=0.9,
                                 roughness=0.35),
            'bench': pbr_material('ctrl_wood', 'Wood027_1k', tint=0x7a5a3a, tint_mix=0.4, tile=0.6)}


def course(config, name='course'):
    """terrain_base.js's TERRAIN_CONFIG through the course package, dressed for the probes -> its Course"""
    from eidoblend.course import build_course
    mats = course_materials()
    return build_course(config, materials={k: mats[k] for k in ('ground', 'obstacle', 'rail')}, name=name)


def light(sc, strength=0.7, sun_strength=3.0):
    """round one's probe settings and studio light, and a key sun from the front left"""
    S.probe_render(sc, res=(960, 540), samples=16)
    S.studio_world(sc, strength=strength)
    S.sun('key', (4, 8, 4), 0xffffee, sun_strength, target=(0.0, 0.0, 0.0))


# ------------------------------------------------------------------------------------------------ checks
class Report:
    def __init__(self, tag):
        self.tag = tag
        self.R = {'started': time.strftime('%Y-%m-%d %H:%M:%S'), 'checks': [], 'timing_s': {}}
        self.fails = []
        self.t0 = time.time()

    def log(self, *a):
        print(f'[{self.tag}]', *a, flush=True)

    def check(self, name, ok, detail=''):
        line = f'{"PASS" if ok else "FAIL"} {name}' + (f': {detail}' if detail else '')
        print(line, flush=True)
        self.R['checks'].append(line)
        if not ok:
            self.fails.append(line)
        return ok

    def __setitem__(self, k, v):
        self.R[k] = v

    def __getitem__(self, k):
        return self.R[k]

    def finish(self):
        self.R['fails'] = self.fails
        self.R['total_s'] = round(time.time() - self.t0, 1)
        with open(os.path.join(OUT, f'{self.tag}.json'), 'w', encoding='utf-8') as fh:
            json.dump(self.R, fh, indent=1, default=str)
        print(f'[{self.tag}] {"ALL PASS" if not self.fails else f"{len(self.fails)} FAIL"} in {self.R["total_s"]} s',
              flush=True)


def gait_checks(R, rep, min_frames=4):
    """checks.feet on every gait's frames of a bake's report (film.check_segment: a run's flight waived; a stance or a
    swing that crosses into the next gait is judged in both), then the whole take's swings: none into the ground"""
    for s_ in rep['segments']:
        if s_['frames'][1] - s_['frames'][0] < min_frames - 1 or 'checks_feet' not in s_:
            continue
        cf = s_['checks_feet']
        R.check(f'checks.feet {s_["gait"]} frames {s_["frames"]}', cf['ok'], '; '.join(cf['failures'][:3]) +
                (f' (waived: {len(s_.get("waived", []))} walk rules of a run)' if s_.get('waived') else ''))
    deep = [(s, r['frames'], r['clearance_mm']) for s in ('left', 'right') for r in rep['swings'][s]
            if r['clearance_mm'] < -1.5]
    R['swing_issues'] = {'into_ground': deep[:10],
                         'worst_swing_ankle_err_mm': sorted(rep.get('swing_ankle_err_mm', []), key=lambda x: -x[1])[:6],
                         'touching': [(s, r['frames'], r['touch_frames'][:3]) for s in ('left', 'right')
                                      for r in rep['swings'][s] if r['touch_frames']][:10]}
    R['stance_issues'] = [(s, r['frames'], r['modes'], r['slip_mm_per_frame_max'], r['yaw_deg_per_frame_max'],
                           r['gap_mm'], r['rocks'][:2]) for s in ('left', 'right') for r in rep['stances'][s]
                          if r['slip_mm_per_frame_max'] > 1.0 or r['yaw_deg_per_frame_max'] > 0.5 or
                          r['gap_mm'][0] < -1.5 or r['gap_mm'][1] > 2.0 or r['rocks']][:12]
    R.check('the whole take: no swinging foot goes into the ground', not deep,
            '; '.join(f'{s} swing {fr}: {c} mm' for s, fr, c in deep[:4]) or
            f'{sum(len(rep["swings"][s]) for s in ("left", "right"))} swings')


def keyed_matches(R, me, frames, every=None):
    """the keyed armature against the bake's own measures: the soles where Blender's evaluated pose puts them"""
    import numpy as np
    from eidoblend.characters.controller.plant import sole_subset
    from eidoblend.characters.ground import SIDES, posed_foot_world
    feet = sole_subset(me)
    sc = bpy.context.scene
    f0, f1 = frames[0]['f'], frames[-1]['f']
    byf = {fr['f']: fr for fr in frames if fr.get('meas')}
    worst = 0.0
    n = 0
    for f in range(f0, f1 + 1, every or max(1, (f1 - f0) // 25)):
        if f not in byf:
            continue
        sc.frame_set(f)
        n += 1
        for s in SIDES:
            P = posed_foot_world(me, feet, s)
            worst = max(worst, float(np.max(np.linalg.norm(P - byf[f]['meas'][s]['P'], axis=1))))
    R.check(f'the keyed armature matches the bake (soles, {n} frames)', worst < 0.0005, f'{worst * 1000:.3f} mm')
    return worst


def dump_frames(R, rep, ranges):
    """a compact per-frame table of the bake over frame ranges [(f0, f1), ...] into the report: what led, the support,
    each foot's planted flag, gap, slip from the last frame and yaw, the ankle's miss (diagnosis)"""
    import numpy as np
    recs = {r['f']: r for r in rep['_records']}
    frs = {fr['f']: fr for fr in rep['_frames']}
    f_first = rep['_records'][0]['f']
    root = rep.get('_root') or {}
    out = []
    for a, b in ranges:
        for f in range(a, b + 1):
            r, fr, fp = recs.get(f), frs.get(f), frs.get(f - 1)
            if r is None or fr is None:
                continue
            i = f - f_first
            row = {'f': f, 'lead': r['lead'], 'mode': r['mode'], 'sup': r['support_mode'], 'grounded': r['grounded'],
                   'w': {k: round(v, 2) for k, v in r['weights'].items() if v > 0.05},
                   'st': {s: round(v, 2) for s, v in r['stance'].items()}, 'speed': round(r['speed'], 3),
                   'feet_world': [round(c, 3) for c in r['feet_world']], 'root_z': round(fr['M'].translation.z, 3),
                   'dz': round(root['dz'][i], 3) if 'dz' in root else None,
                   'cap': round(root['cap'][i], 3) if 'cap' in root else None}
            for s in ('left', 'right'):
                m = fr['meas'][s]
                d = {'planted': m['stance'], 'gap_mm': round(1000 * m['gap'], 2), 'yaw': round(math.degrees(m['yaw']), 2),
                     'ankle_err_mm': round(1000 * m['ankle_err'], 2), 'free': m['free'],
                     'T': [round(c, 3) for c in m['T']] if 'T' in m else None,
                     'ankle': [round(c, 3) for c in m['ankle']] if 'ankle' in m else None}
                if fp is not None:
                    mv = np.linalg.norm(m['P'][:, :2] - fp['meas'][s]['P'][:, :2], axis=1)
                    k = int(np.argmin(m['gaps']))
                    d['low_move_mm'] = round(1000 * float(mv[k]), 2)
                    d['min_move_mm'] = round(1000 * float(mv.min()), 2)
                row[s] = d
            out.append(row)
    R['frame_dump'] = out


# ------------------------------------------------------------------------------------------------ shots
def side_shot(me, rec, name, dist=4.2, lens=35.0, side=1.0, height=0.25, lead=0.5, look_drop=0.05):
    """a camera `dist` to the body's left (side=-1: its right), level with the hips, looking at them: the whole body and
    the ground it stands on in frame"""
    hb = me.humanoid['hips']
    hp = me.arm.matrix_world @ me.arm.pose.bones[hb].head
    h = rec['heading']
    fwd = Vector((math.sin(h), -math.cos(h), 0.0))
    left = Vector((-fwd.y, fwd.x, 0.0))
    pos = hp + left * dist * side + fwd * lead + Vector((0.0, 0.0, height))
    tgt = hp + Vector((0.0, 0.0, -look_drop)) + fwd * 0.15
    return {'name': name, 'frame': rec['f'], 'pos': tuple(pos), 'target': tuple(tgt), 'lens': lens}


def fixed_shot(name, frame, pos, target, lens=50.0):
    return {'name': name, 'frame': frame, 'pos': tuple(pos), 'target': tuple(target), 'lens': lens}


def save(R, sc, shots, sheets=None, blend=True):
    """out/<tag>.blend (the keyed scene, lit) and out/<tag>_shots.json for render_shots.py; sheets: {sheet name:
    [shot names]} composed after the render"""
    path = os.path.join(OUT, f'{R.tag}.blend')
    if blend:
        bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
        if os.path.exists(path + '1'):
            os.remove(path + '1')                    # the previous save's backup: regenerable
    with open(os.path.join(OUT, f'{R.tag}_shots.json'), 'w', encoding='utf-8') as fh:
        json.dump({'blend': path, 'tag': R.tag, 'shots': shots, 'sheets': sheets or {}}, fh, indent=1)
    R['shots'] = len(shots)

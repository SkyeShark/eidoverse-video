"""The robot_body tests' stage: the characters family's probe stage (tests/characters/_stage.py: probe EEVEE settings,
the claude_robot example's studio light, floors, cameras), loaded by path, with this folder's own out/ for outputs, plus
a few helpers these tests share (deno for the JS originals, a clip's raw normalized pose, textured boxes and bars for
the sets, the PASS / FAIL report, the keyed body's feet against the solids, the senses against the keyed head)."""

import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'blender'))
_spec = importlib.util.spec_from_file_location('characters_stage', os.path.join(REPO, 'blender', 'tests', 'characters', '_stage.py'))
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)
C.OUT = OUT

MAIN = os.path.join(os.path.dirname(REPO), 'eidoverse-video-prealpha-0.01')
THREE_JS = next((p for p in (os.path.join(REPO, 'node_modules', 'three', 'build', 'three.module.js'),
                             os.path.join(MAIN, 'node_modules', 'three', 'build', 'three.module.js')) if os.path.exists(p)), None)


def argv():
    return sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def deno():
    d = shutil.which('deno')
    if d:
        return d
    p = os.path.expandvars(r'%LOCALAPPDATA%\Microsoft\WinGet\Packages\DenoLand.Deno_Microsoft.Winget.Source_8wekyb3d8bbwe\deno.exe')
    return p if os.path.exists(p) else None


def run_deno(mjs, *args, timeout=900):
    exe = deno()
    if exe is None:
        raise RuntimeError('deno not found')
    r = subprocess.run([exe, 'run', '--no-config', '--no-lock', '-A', mjs, *args], capture_output=True, text=True,
                       timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f'deno {os.path.basename(mjs)} failed ({r.returncode}):\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}')
    return r.stdout


def write_json(name, obj):
    p = os.path.join(OUT, name)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=1, default=str)
    return p


def solids_bvh(objs):
    """one BVH over objects' evaluated meshes in world space (walls, furniture: what a camera must stay in front of)"""
    import bpy
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys = [], []
    for ob in objs:
        if ob.type != 'MESH':
            continue
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        b0 = len(verts)
        verts.extend(ev.matrix_world @ v.co for v in me.vertices)
        polys.extend([b0 + i for i in p.vertices] for p in me.polygons)
        ev.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys, all_triangles=False)


def clear_view(bvh, target, want, margin=0.25):
    """a camera place on the line from `target` toward `want` with nothing between them: where a wall or a solid
    stands on that line, the camera comes in to `margin` in front of it (so a probe never looks at a wall's back)"""
    from mathutils import Vector
    t, w = Vector(target), Vector(want)
    d = w - t
    L = d.length
    if L < 1e-6:
        return w
    d /= L
    hit = bvh.ray_cast(t, d, L + margin)
    if hit[0] is None:
        return w
    return t + d * max(0.3, hit[3] - margin)


def best_view(bvh, target, wants, margin=0.25):
    """of several wanted camera places, the one that keeps the most of its distance in front of the solids (clear_view
    applied to each; ties go to the earlier)"""
    from mathutils import Vector
    best = None
    for w in wants:
        c = clear_view(bvh, target, w, margin)
        keep = (c - Vector(target)).length / max(1e-6, (Vector(w) - Vector(target)).length)
        if best is None or keep > best[0] + 1e-3:
            best = (keep, c)
    return best[1]


def side_view(bvh, frames, f0, fa, fb, height=0.45, lens=28.0, up=1.85):
    """a low camera beside a stretch of a keyed take (film frames fa..fb), held for the stretch: square to the body's
    travel over it (to its facing where it stays put), `height` over the ground under the camera (a tread of the flight
    beside me, the top of the cover I vault; never under the lowest my root goes), far enough back for the whole body
    from the stretch's first frame to its last at `lens` (mm, 36 mm film). A camera that has to come in front of a solid
    (a hall's wall) takes a wider lens for the same framing (12 mm at most); where the square place keeps under 30 % of
    its distance, its sightlines to the body (its feet, middle and head at the stretch's ends and middle) are cut, or
    something stands right by its lens (a chair's leg, a crate), it swings round toward the travel's ends (30 and 55
    deg) or goes up (0.9 m) -> {'cam', 'target', 'lens'}"""
    from mathutils import Vector
    idx = list(range(max(0, fa - f0), min(len(frames), fb - f0 + 1))) or [min(len(frames) - 1, max(0, fa - f0))]
    P = [frames[i]['M'].translation.copy() for i in idx]
    lo = Vector((min(p.x for p in P), min(p.y for p in P), min(p.z for p in P)))
    hi = Vector((max(p.x for p in P), max(p.y for p in P), max(p.z for p in P)))
    trav = (P[-1] - P[0]).xy
    if trav.length < 0.3:
        trav = (frames[idx[len(idx) // 2]]['M'].to_quaternion() @ Vector((0.0, -1.0, 0.0))).xy
    d = trav.normalized()
    n = Vector((-d.y, d.x))
    # aimed at where the body is in the stretch's middle frame (a path round a pillar has the pillar at its box's middle)
    pm = P[len(P) // 2]
    tgt = Vector((pm.x, pm.y, lo.z + 0.5 * (hi.z - lo.z + up)))
    along = 2.0 * max(abs((p.xy - pm.xy).dot(d)) for p in P) + 1.2
    tall = (hi.z - lo.z) + up + 0.3
    tan_h = 18.0 / lens
    dist = max(along / 2.0 / tan_h, tall / 2.0 / (tan_h * 9.0 / 16.0)) + 0.3
    down = Vector((0.0, 0.0, -1.0))
    body_pts = [p + Vector((0.0, 0.0, z)) for p in (P[0], pm, P[-1]) for z in (0.1, 0.9, up - 0.15)]

    def seen(cam):
        """the share of the body's sightlines from cam that no solid cuts"""
        ok = 0
        for q in body_pts:
            v = q - cam
            h = bvh.ray_cast(cam, v.normalized(), v.length - 0.05) if v.length > 0.1 else (None,)
            ok += h[0] is None
        return ok / len(body_pts)

    def near_clear(cam, lens_c):
        """the share of rays over the frame (5 x 3, at the camera's lens) that meet no upright face within 1.2 m of the
        lens: a chair's leg or a crate right by the camera fills the frame though every sightline to the body passes it
        (the floor or a tread under the camera is ground in the frame, not in the way)"""
        f = (tgt - cam).normalized()
        r = f.cross(Vector((0.0, 0.0, 1.0)))
        r = r.normalized() if r.length > 1e-6 else Vector((1.0, 0.0, 0.0))
        u = r.cross(f)
        th = 18.0 / lens_c
        ok = 0
        for a in (-1.0, -0.5, 0.0, 0.5, 1.0):
            for b in (-1.0, 0.0, 1.0):
                h = bvh.ray_cast(cam, (f + r * (a * th) + u * (b * th * 9.0 / 16.0)).normalized(), 1.2)
                ok += h[0] is None or abs(h[1].z) > 0.7
        return ok / 15.0
    best = None
    # square to the travel is the view the feet read in; a swing toward the travel's ends, or the higher place, only
    # where the square one keeps under 30 % of its distance (a narrow hall: its lens widens to 12 mm at most)
    pref = {0.0: 1.0, 30.0: 0.85, -30.0: 0.85, 55.0: 0.65, -55.0: 0.65}
    for z in (height, 0.9):
        for a in (0.0, 30.0, -30.0, 55.0, -55.0):
            for s in (1.0, -1.0):
                r = math.radians(a)
                w = n * s * math.cos(r) + d * math.sin(r)
                x, y = tgt.x + w.x * dist, tgt.y + w.y * dist
                g = bvh.ray_cast(Vector((x, y, hi.z + up + 0.2)), down, 50.0)[0]     # (under a lintel, a beam)
                base = lo.z if g is None else max(lo.z, g.z)
                want = Vector((x, y, base + z))
                cam = clear_view(bvh, tgt, want, 0.25)
                keep = (cam - tgt).length / max(1e-6, (want - tgt).length)
                score = (min(1.0, keep / 0.3) * seen(cam) * near_clear(cam, max(12.0, lens * keep)) * pref[a]
                         * (1.0 if z == height else 0.9))
                if best is None or score > best[0] + 0.05:
                    best = (score, keep, cam)
    _score, keep, cam = best
    return {'cam': list(cam), 'target': list(tgt), 'lens': max(12.0, lens * keep)}


def strip(name, view, fa, fb, n=9):
    """n stills over film frames fa..fb from one held camera (side_view's) -> the shots"""
    import numpy as np
    return [dict(view, name=f'{name}_{k}', frame=int(f)) for k, f in enumerate(np.linspace(fa, fb, n).round().astype(int))]


def raw_pose(h, clip, tc):
    """the clip's NORMALIZED pose at clip time tc before any DOF pass: ({name: Quaternion three}, hips position three)"""
    from mathutils import Quaternion
    from eidoblend.characters._math import q_to_three, v_to_three
    rot, loc = clip.sample(tc)
    N = {}
    for n, b in h.humanoid.items():
        q = rot.get(b)
        N[n] = q_to_three(h.normalized_from_basis(b, q)) if q is not None else Quaternion()
    off = h.hips_location_offset(loc.get(h.humanoid['hips'], (0.0, 0.0, 0.0)))
    return N, v_to_three(h.rest_head[h.humanoid['hips']] + off)


# ------------------------------------------------------------------------------------------------ the sets
def textured(name, tex, scale=1.0, tint=None, rough=None):
    """a Principled material from a CC0 set of the shared texture cache, box-projected on the object's coordinates
    (scale: repeats per metre); tint multiplies the albedo. Without the set: a plain grey (or the tint)"""
    import bpy
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes['Principled BSDF']
    ts = C.texture_set(tex)
    if not ts:
        bsdf.inputs['Base Color'].default_value = tint or (0.5, 0.5, 0.5, 1.0)
        return mat
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (scale, scale, scale)
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])

    def img(role, colour):
        if not ts.get(role):
            return None
        n = nt.nodes.new('ShaderNodeTexImage')
        n.image = bpy.data.images.load(ts[role], check_existing=True)
        n.image.colorspace_settings.name = 'sRGB' if colour else 'Non-Color'
        n.projection = 'BOX'
        n.projection_blend = 0.2
        nt.links.new(mp.outputs['Vector'], n.inputs['Vector'])
        return n
    c, r, nrm = img('color', True), img('rough', False), img('normal', False)
    if c:
        if tint:
            mul = nt.nodes.new('ShaderNodeMix')
            mul.data_type, mul.blend_type = 'RGBA', 'MULTIPLY'
            mul.inputs['Factor'].default_value = 1.0
            nt.links.new(c.outputs['Color'], mul.inputs['A'])
            mul.inputs['B'].default_value = tint
            nt.links.new(mul.outputs['Result'], bsdf.inputs['Base Color'])
        else:
            nt.links.new(c.outputs['Color'], bsdf.inputs['Base Color'])
    if r and rough is None:
        nt.links.new(r.outputs['Color'], bsdf.inputs['Roughness'])
    elif rough is not None:
        bsdf.inputs['Roughness'].default_value = rough
    if nrm:
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nt.links.new(nrm.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    return mat


def box(name, x0, x1, y0, y1, z0, z1, mat, bevel=0.0):
    """an axis-aligned box object (its own mesh, linked to the scene)"""
    import bmesh
    import bpy
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(x1 - x0, y1 - y0, z1 - z0), verts=bm.verts)
    bmesh.ops.translate(bm, vec=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), verts=bm.verts)
    if bevel:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=2, affect='EDGES')
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(mat)
    return ob


def stairs(name, x0, run, rise, n, y0, y1, mat, down=False, base=0.0):
    """a flight of n treads along +X from x0 (each `run` deep, `rise` higher than the one before), one closed solid (its
    side profile extruded across y0..y1), flagged as shaped ground (ob['trimesh_collider']: the walkable world takes its
    own triangles, not its box). Up: the treads at base + rise .. base + n rise. down=True: from base + n rise (the first
    tread) down to base + rise (the last), the floor at base after it"""
    import bmesh
    import bpy
    from mathutils import Vector
    tops = [base + (n - k) * rise for k in range(n)] if down else [base + (k + 1) * rise for k in range(n)]
    prof = [(x0, base)]
    for k, z in enumerate(tops):
        prof += [(x0 + k * run, z), (x0 + (k + 1) * run, z)]
    prof.append((x0 + n * run, base))
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    vs = [bm.verts.new((x, y0, z)) for x, z in prof]
    face = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[face])
    bmesh.ops.translate(bm, vec=Vector((0.0, y1 - y0, 0.0)),
                        verts=[g for g in ext['geom'] if isinstance(g, bmesh.types.BMVert)])
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(mat)
    ob['trimesh_collider'] = True
    return ob


def render_shots(sc, tag, shots):
    """a test's stills rendered now (render_stills.py renders the same list from the saved .blend through the GPU slot):
    out/<tag>_<name>_f<frame>.png at the probe settings (960 x 540, 16 samples, EEVEE ray tracing and Fast GI on). A
    shot's 'hide': the names of objects left out of that still (the debug overlays, for a still of the body's feet)"""
    import bpy
    from eidoblend.look import render_settings as rs
    rs.apply_auto_enhance(sc, 'probe')
    sc.view_settings.exposure = 0.0
    cam = C.camera('still_cam', 35.0)
    done = {}
    for s in shots:
        cam.data.lens = s.get('lens', 35.0)
        C.aim(cam, s['cam'], s['target'])
        hid = [o for o in (bpy.data.objects.get(n) for n in s.get('hide', ())) if o is not None and not o.hide_render]
        for o in hid:
            o.hide_render = True
        path = os.path.join(OUT, f'{tag}_{s["name"]}_f{int(s["frame"]):04d}.png')
        done[os.path.basename(path)] = C.still(sc, cam, int(s['frame']), path)
        for o in hid:
            o.hide_render = False
    return done


def area_light(sc, name, loc, energy, size=2.0, colour=(1.0, 0.95, 0.88)):
    import bpy
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy, ld.size, ld.color = energy, size, colour
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    sc.collection.objects.link(ob)
    return ob


# ------------------------------------------------------------------------------------------------ the report
class Report(dict):
    """PASS / FAIL lines and the JSON (out/<name>.json) a test writes"""

    def __init__(self, name):
        import time
        super().__init__(started=time.strftime('%Y-%m-%d %H:%M:%S'))
        self.name, self.ok, self.t0 = name, True, time.time()

    def check(self, name, good, detail):
        self.ok &= bool(good)
        self.setdefault('checks', {})[name] = {'pass': bool(good), 'detail': detail}
        print(f'{"PASS" if good else "FAIL"} {name}: {detail}', flush=True)

    def log(self, *a):
        print(f'[{self.name}]', *a, flush=True)

    def finish(self, error=None):
        import time
        if error:
            self['error'] = error
            self.ok = False
            print(error, flush=True)
        self['ok'] = self.ok
        self['seconds'] = round(time.time() - self.t0, 1)
        write_json(self.name + '.json', self)
        self.log('done', self.ok, self['seconds'], 's')


# ------------------------------------------------------------------------------------------------ the keyed body
def depth_in(bvh, p):
    """how far p is inside the closed solids of bvh (m, 0 outside): the nearest face's side, then an upward ray's
    crossings (a point beside a concave corner is outside)"""
    from mathutils import Vector
    q, n, _i, d = bvh.find_nearest(p)
    if q is None or (p - q).dot(n) >= 0:
        return 0.0
    hits, o = 0, p.copy()
    for _ in range(16):
        h = bvh.ray_cast(o, Vector((0.0, 0.0, 1.0)), 50.0)
        if h[0] is None:
            break
        hits += 1
        o = h[0] + Vector((0.0, 0.0, 1e-4))
    return d if hits % 2 == 1 else 0.0


def feet_in_solids(rig, frames, bvh, every=3):
    """the deepest sole point inside the solids over the keyed frames -> (depth m, frame, side, mode)"""
    from mathutils import Vector
    deep = (0.0, None, None, None)
    for fr in frames:
        for s, P in rig.feet_world(fr).items():
            for p in P[::every]:
                d = depth_in(bvh, Vector(p))
                if d > deep[0]:
                    deep = (d, fr['f'], s, fr.get('mode'))
    return deep


def sense_heads(body, rep):
    """each sense's origin (the head the live run sensed from: the frame last stepped) against my keyed head bone in
    that film frame, across and up, and the plant's pelvis there (the keyed root's height less the controller's) ->
    [(across m, up m, pelvis m, film frame)], sorted by across"""
    rig = body.controller.char_ctrl.rig
    frames, recs = rep['_frames'], rep['_records']
    f0 = rep['frames'][0]
    out = []
    for fc, _t, reading in body.readings:
        j = fc - 2                          # update fc senses before its step: the frame last stepped is the one before
        if 0 <= j < len(frames):
            p, _W = rig.bone_world(frames[j], 'head')
            d = p - reading['origin']
            dz = frames[j]['M'].translation.z - recs[j]['M'].translation.z
            out.append((d.xy.length, d.z, dz, f0 + j))
    return sorted(out)


def feet_slide(rig, frames, sel, low=0.0025):
    """over the keyed frames `sel` picks: per side, the largest move of the least-moving sole point in contact (lower
    than `low`) two frames running -> {side: (mm, film frame)}"""
    import numpy as np
    out = {}
    for s in ('left', 'right'):
        prev = None
        worst = (0.0, None)
        for fr in frames:
            P = rig.feet_world(fr)[s]
            lo = P[:, 2] < low
            if sel(fr) and prev is not None and prev[1].any() and lo.any():
                both = lo & prev[1]
                if both.any():
                    d = float(np.min(np.linalg.norm(P[both, :2] - prev[0][both, :2], axis=1)))
                    if d > worst[0]:
                        worst = (d, fr['f'])
            prev = (P, lo)
        out[s] = (round(1000 * worst[0], 3), worst[1])
    return out


def resense_keyed(body, rep, start, goal):
    """what sensing from my KEYED head would have made of the world: every sense of the run cast again from my keyed
    head bone in that film frame (the sense's own heading and pitch), into a fresh memory, beside one rebuilt the same
    way from the live senses (each with the standing footprints the run marked, in the run's order); a static scene's.
    -> {'known_cells', 'differ_cells', 'differ_frac', 'route_live', 'route_keyed', 'route_apart_m'}: the cells the two
    memories disagree on, and the planner's route from start to goal through each (how far apart, at most)"""
    from mathutils import Vector
    from eidoblend.harness.navigation import RobotMemory
    rig = body.controller.char_ctrl.rig
    frames, recs = rep['_frames'], rep['_records']
    m0 = body.memory

    def fresh():
        return RobotMemory(size=m0.size, cell_size=m0.cell_size, origin_x=m0.origin_x, origin_y=m0.origin_y,
                           bayesian=m0.bayesian, cliff_threshold=m0.cliff_threshold,
                           step_up_tolerance=m0.step_up_tolerance)
    live, keyed = fresh(), fresh()
    senses = {fc: rd for fc, _t, rd in body.readings}
    r_foot = body.agent_radius * 1.2
    for fc in range(1, body.frame_count + 1):
        j = max(0, fc - 2)                    # update fc senses before its step: the frame last stepped
        if j >= len(recs):
            break
        fx, fy, fz = recs[j]['feet_world']
        rd = senses.get(fc)
        if rd is not None:
            head, _W = rig.bone_world(frames[j], 'head')
            rk = body.sensors.sense(Vector(head), rd['heading'], rd['pitch'])
            live.apply_sensor_reading(rd, floor_z=fz, agent_height=body.agent_height)
            keyed.apply_sensor_reading(rk, floor_z=fz, agent_height=body.agent_height)
        live.mark_standing_footprint(fx, fy, r_foot, fz)
        keyed.mark_standing_footprint(fx, fy, r_foot, fz)
    a, b = live.cells & 0x0F, keyed.cells & 0x0F
    known = int(((a != 0) | (b != 0)).sum())
    differ = int((a != b).sum())
    p_l = body.planner.find_path(live, start[0], start[1], goal[0], goal[1])
    p_k = body.planner.find_path(keyed, start[0], start[1], goal[0], goal[1])

    def apart(p, q):
        if not p or not q:
            return None
        P = [Vector((w['x'], w['y'])) for w in p]
        Q = [Vector((w['x'], w['y'])) for w in q]

        def dist(x, L):
            best = math.inf
            for u, v in zip(L, L[1:]):
                e = v - u
                t = 0.0 if e.length_squared < 1e-12 else max(0.0, min(1.0, (x - u).dot(e) / e.length_squared))
                best = min(best, (u + e * t - x).length)
            return best if len(L) > 1 else (L[0] - x).length
        pts = [u.lerp(v, k / 10) for u, v in zip(P, P[1:]) for k in range(11)] or P
        return round(max(dist(x, Q) for x in pts), 3)
    return {'known_cells': known, 'differ_cells': differ, 'differ_frac': round(differ / max(1, known), 4),
            'route_live': None if not p_l else len(p_l), 'route_keyed': None if not p_k else len(p_k),
            'route_apart_m': apart(p_l, p_k)}


def dump(R, recs, frames, spans):
    """the records over frame spans [(a, b)] (film frames from 1) into R['dump']: what the controller did and the plant
    made of it"""
    rows = []
    for a, b in spans:
        for i in range(max(0, a - 1), min(len(recs), b)):
            r, fr = recs[i], frames[i]
            rows.append({'f': r['f'], 'mode': r['mode'], 'lead': r.get('lead'), 'cmd': r.get('cmd'),
                         'heading_deg': round(math.degrees(r['heading']), 2),
                         'feet': [round(v, 3) for v in r['feet_world']], 'speed': round(r['speed'], 3),
                         'support': r.get('support_mode'), 'stance': {k: round(v, 2) for k, v in r['stance'].items()},
                         'dz': round(fr['M'].translation.z - r['M'].translation.z, 4),
                         'meas': {s: {'gap_mm': round(1000 * m['gap'], 1), 'yaw_deg': round(math.degrees(m['yaw']), 2),
                                      'stance': m['stance']} for s, m in (fr.get('meas') or {}).items()}})
    R['dump'] = rows


def live_heads(rig, body, recs, frames):
    """every recorded frame's head as the live run could read it (the controller's pose before its foot IK, 'anim', and
    after it, 'ik'; my torso rehomed as my hardware holds it) against my keyed head -> {kind: [median, p95, max] m}"""
    import numpy as np
    from eidoblend.characters import robot_dof as dof
    from eidoblend.characters._math import q_from_three, q_to_three
    from eidoblend.characters.controller.pose import Pose
    acc = {'anim': [], 'ik': []}
    for r, fr in zip(recs, frames):
        kp, _W = rig.bone_world(fr, 'head')
        for kind, M, N in (('anim', r['M'], r['N']), ('ik', r['M_ik'], r['N_ik'])):
            p3 = {n: q_to_three(q) for n, q in N.items()}
            if rig.hardware:
                dof.rehome_body(p3)
            P = Pose(body, M, {n: q_from_three(q) for n, q in p3.items()}, r['off'])
            acc[kind].append((P.world_pos('head') - kp).length)
    return {k: [round(float(np.median(v)), 4), round(float(np.percentile(v, 95)), 4), round(float(max(v)), 4)]
            for k, v in acc.items() if v}


def plant_failures(rep):
    """the controller family's checks.feet failures per gait segment of the bake -> [(gait, frames, failures)]"""
    return [(s['gait'], s['frames'], s['checks_feet']['failures']) for s in rep.get('segments', [])
            if not s.get('checks_feet', {}).get('ok', True)]

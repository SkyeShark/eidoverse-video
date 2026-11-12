"""look/camera_safety.py: CameraSafety for Blender scenes. Sightlines, clearance, and the whole animated path checked.

The WebGPU CameraSafety raycast sightlines from the target to the camera and suggested clear positions; checking every
frame cost too much there. In Blender the camera's animated path is cheap to walk, so check_camera does exactly that:
at every frame of a shot it asks
  - is the camera behind a surface (inside a closed mesh, under the ground)?             'inside'
  - is a surface closer than the lens's near clip plane (the frame would show a cut)?    'clip'
  - is a surface closer than min_distance (a camera brushing a wall or a body)?           'tight'
  - is the sightline from what it looks at back to the lens blocked?                     'blocked' / 'tight_sightline'
and reports each problem once, as a run of frames.

    from eidoblend.look.camera_safety import CameraSafety
    cs = CameraSafety(scene, padding=0.5, min_distance=0.3)
    cs.exclude(*grass_scatters)          # foliage the camera may look through (a Geometry Nodes scatter: its instances
                                         # go with it), a sky dome, a haze volume
    cs.exclude(arm, sightline_only=True) # the subject: never an obstruction of its own sightline, still needs clearance
    issues = cs.check_camera(cam, (1, 240))                     # the real, keyed path
    issues = cs.check_path([{'time': 0, 'position': (3, -4, 2), 'target': (0, 0, 1)},
                            {'time': 3, 'position': (1, -4, 2), 'target': (0, 0, 1)}], samples_per_segment=12)
    pos = cs.safe_position(desired, target)

Sightlines use scene.ray_cast on the evaluated scene (instances included; an excluded hit is stepped past). A ray that
meets an instance reports the INSTANCED object (a scatter's grass source, 'grass_medium_02_d') with the instance's
matrix, never the instancer, so excluding an instancer (a Geometry Nodes scatter, a collection instance, particles)
excludes what it instances: the depsgraph's instance list says which objects those are. When such an object also
renders on its own, or through an instancer that is not excluded, its hits are told apart by the instance's matrix,
per frame. Clearance uses mathutils BVH trees of the evaluated meshes near the camera that render (an object in an
excluded collection, such as a scatter's sources, is not there), deforming meshes rebuilt per frame when the camera is
near them. Instanced geometry has no clearance test: exclude it, or check it in the probe stills.

CameraSafety.help() prints (and returns) the API reference below, as the WebGPU CameraSafety.help() did.
"""
import math

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from . import camera as C

DEFORMING = {'ARMATURE', 'CLOTH', 'SOFT_BODY', 'MESH_CACHE', 'MESH_SEQUENCE_CACHE', 'NODES', 'OCEAN', 'WAVE',
             'SURFACE_DEFORM', 'MESH_DEFORM', 'LATTICE', 'HOOK', 'DYNAMIC_PAINT', 'FLUID'}


def _deforms(o):
    if any(m.type in DEFORMING for m in o.modifiers):
        return True
    sk = getattr(o.data, 'shape_keys', None)
    return bool(sk and sk.animation_data)


HELP = """---------- eidoblend.look.camera_safety (CameraSafety) API reference ----------

Checks a camera against the scene before anything renders: sightlines (scene.ray_cast on the evaluated scene,
instances included) and clearance (the nearest rendering surface to the lens). It catches a camera inside a wall,
under the ground, closer to a surface than its near clip, or looking at its subject through a prop.

-- Construction --
  from eidoblend.look.camera_safety import CameraSafety
  cs = CameraSafety(scene, padding=0.5, min_distance=0.3)
  cs.exclude(*grass_scatters, haze_box)       # never an obstruction, never a clearance hit (with what they instance)
  cs.exclude(subject, sightline_only=True)    # the subject: not an obstruction of its own sightline, still clearance

-- check_camera: the real, keyed path, walked frame by frame --
  issues = cs.check_camera(cam, (1, 240), target=chest, every=1)
  # issues = [{kind, object, frames: [first, last], worst, at}], one per run of frames:
  #   'inside'  the lens is behind a surface (inside a closed mesh, under the ground)
  #   'clip'    a surface is nearer than the lens's near clip (the frame would show a cut)
  #   'tight'   a surface is nearer than min_distance
  #   'blocked' / 'tight_sightline'   something sits on the sightline from the target back to the lens
  # target: a point, an Object, (armature, 'bone'), {'object': o, 'y_bias': b}, {'point': p} or a callable;
  # default: the camera's DOF focus object, else the point focus_distance (or 3 m) down its view axis.

-- check_path: a planned path, before it is keyed --
  issues = cs.check_path([{'time': 0, 'position': (2, -7, 1.6), 'target': (0, -3, 1.2)},
                          {'time': 2, 'position': (0, 3, 1.6), 'target': (0, -3, 1.2)}], samples_per_segment=12)
  # issues = [{index (-1 between keys), time, position, target, obstruction, hit_distance, desired_distance,
  #            severity 'blocked' | 'tight', suggestion}]; [] = clear. suggestion: the nearest clear position at
  #            the same distance round the target (None when there is none). Fix the keys, then key the path.

-- safe_position: a last resort for a move you cannot plan --
  pos = cs.safe_position(desired, target)     # pulled in toward the target until its sightline is clear

-- Other methods --
  cs.is_clear(pos, target)      {clear, distance, object}: one sightline
  cs.clearance(pos, radius=)    {distance, object, behind, point} of the nearest surface, or None
  cs.refresh()                  forget the cached trees and the instance index (after adding or moving meshes or
                                scatters, or changing what they instance)

-- Common gotchas --
  * Exclude what the camera may pass through: grass and plant scatters (their instances go with them), sky
    domes and haze or fog volumes (a camera is always inside those). Keep the ground: it is what flags a camera
    under the ground.
  * Give the subject sightline_only=True: excluded outright it would also lose its clearance test.
  * Instanced geometry has no clearance test (a camera inside a scattered rock is not 'inside'); sightlines do see
    instances. Check those shots in the probe stills.
  * Check the path in setup and fix the keys (check_path, then check_camera on the keyed shot). safe_position
    jumps as occluders change: use it only for moves you cannot plan, then review the rendered sequence.
"""


def _tkey(m):
    """An instance's identity at one frame: its matrix's translation, rounded (ray_cast hands back the very matrix the
    depsgraph holds for the instance it hit)."""
    t = m.translation
    return (round(t.x, 4), round(t.y, 4), round(t.z, 4))


def _rendered_names(view_layer):
    """Objects that render in a view layer: in a collection that is neither excluded nor hidden from renders, and
    not hidden from renders themselves."""
    names = set()

    def walk(lc, hidden):
        if lc.exclude:
            return
        h = hidden or lc.collection.hide_render
        if not h:
            names.update(o.name for o in lc.collection.objects if not o.hide_render)
        for c in lc.children:
            walk(c, h)
    walk(view_layer.layer_collection, False)
    return names


class CameraSafety:
    def __init__(self, scene, padding=0.5, min_distance=0.3):
        self.scene = scene
        self.padding = float(padding)
        self.min_distance = float(min_distance)
        self._excluded = set()          # names never hit: neither sightline nor clearance
        self._sight_only = set()        # names ignored by sightlines, kept for clearance (the subject)
        self._trees = {}
        self.refresh()

    @staticmethod
    def help():  # noqa: A003 - the engine's CameraSafety.help()
        """Print (and return) the API reference (HELP)."""
        print(HELP)
        return HELP

    # ------------------------------------------------------------------ scene
    def exclude(self, *items, sightline_only=False):
        """Exclude objects / collections (children included) from the checks, with everything they instance: a
        collection instance's collection, a Geometry Nodes scatter's or a particle system's instanced objects.
        sightline_only=True keeps them for clearance: the subject itself."""
        for o in C._collect(list(items)):
            names = {o.name}
            if o.instance_type == 'COLLECTION' and o.instance_collection:
                names |= {x.name for x in o.instance_collection.all_objects}
            (self._sight_only if sightline_only else self._excluded).update(names)
        self.refresh()
        return self

    def refresh(self):
        """Forget the cached trees and the instance index (call after adding or changing scene meshes or scatters)."""
        self._trees = {}
        self._dg = bpy.context.evaluated_depsgraph_get()
        self._inst = None               # what excluded instancers instance (built on the first ray)
        self._amb_keys = None           # (frame, {(name, translation): 'excl'|'sight'}) for the ambiguous names
        self._vis = None                # the names that render (clearance looks only at those)

    def _view_layer(self):
        vl = bpy.context.view_layer
        return vl if bpy.context.scene == self.scene and vl is not None else self.scene.view_layers[0]

    def _index(self):
        """Which object names a ray reports for geometry an excluded instancer makes. Names hit ONLY that way are
        ignored by name; names that also render on their own or through an instancer that is not excluded are
        'ambiguous', told apart per hit by the instance's matrix."""
        if self._inst is not None:
            return self._inst
        excl, sight, other = set(), set(), set()
        if self._excluded or self._sight_only:
            for inst in bpy.context.evaluated_depsgraph_get().object_instances:
                n = inst.object.original.name
                if not inst.is_instance:
                    other.add(n)
                    continue
                p = inst.parent.original.name if inst.parent else None
                if p in self._excluded:
                    excl.add(n)
                elif p in self._sight_only:
                    sight.add(n)
                else:
                    other.add(n)
        named = self._excluded | self._sight_only
        amb = (excl | sight) & other
        self._inst = {'excl': excl - amb, 'sight': sight - amb - excl, 'amb': amb - named}
        return self._inst

    def _ambiguous(self):
        """{(name, translation): 'excl'|'sight'} for this frame's instances of ambiguous names made by excluded
        instancers (rebuilt when the frame changes: a scatter may move)."""
        f = self.scene.frame_current
        if self._amb_keys is not None and self._amb_keys[0] == f:
            return self._amb_keys[1]
        amb = self._index()['amb']
        keys = {}
        for inst in bpy.context.evaluated_depsgraph_get().object_instances:
            if not inst.is_instance or inst.parent is None:
                continue
            n = inst.object.original.name
            if n not in amb:
                continue
            p = inst.parent.original.name
            if p in self._excluded:
                keys[(n, _tkey(inst.matrix_world))] = 'excl'
            elif p in self._sight_only:
                keys.setdefault((n, _tkey(inst.matrix_world)), 'sight')
        self._amb_keys = (f, keys)
        return keys

    def _ignored(self, obj, sightline, matrix=None):
        if obj is None:
            return True
        n = getattr(obj, 'original', obj).name
        if n in self._excluded or (sightline and n in self._sight_only):
            return True
        idx = self._index()
        if n in idx['excl'] or (sightline and n in idx['sight']):
            return True
        if n in idx['amb'] and matrix is not None:
            kind = self._ambiguous().get((n, _tkey(matrix)))
            return kind == 'excl' or (sightline and kind == 'sight')
        return False

    # ------------------------------------------------------------------ rays
    def _ray(self, origin, direction, distance, sightline=True):
        """First non-excluded hit along a ray: (distance, object name) or None. Excluded hits are stepped past (a ray
        through a metre of excluded grass meets dozens of blade faces)."""
        dg = bpy.context.evaluated_depsgraph_get()
        d = Vector(direction).normalized()
        o = Vector(origin)
        travelled = 0.0
        for _ in range(4096):
            ok, loc, _n, _i, obj, mat = self.scene.ray_cast(dg, o, d, distance=distance - travelled)
            if not ok:
                return None
            step = (loc - o).length
            travelled += step
            if not self._ignored(obj, sightline, mat):
                return travelled, getattr(obj, 'original', obj).name
            o = loc + d * 1e-4
            travelled += 1e-4
            if travelled >= distance:
                return None
        print(f'[camera-safety] a ray passed 4096 excluded surfaces in {travelled:.2f} m and was called clear', flush=True)
        return None

    def is_clear(self, pos, target, padding=None):
        """The sightline from `target` back to `pos`: dict(clear, distance, object). Blocked when something sits on it
        more than padding / 2 short of the camera (the WebGPU rule)."""
        pad = self.padding if padding is None else padding
        pos, target = Vector(pos), Vector(target)
        v = pos - target
        dist = v.length
        if dist < 1e-3:
            return {'clear': False, 'distance': 0.0, 'object': None}
        hit = self._ray(target, v, dist)
        if hit and hit[0] < dist - pad * 0.5:
            return {'clear': False, 'distance': hit[0], 'object': hit[1]}
        return {'clear': True, 'distance': dist, 'object': None}

    # ------------------------------------------------------------------ clearance
    def _tree(self, o, dg):
        dyn = _deforms(o)
        key = o.name
        if key in self._trees and not dyn:
            return self._trees[key]
        ev = o.evaluated_get(dg)
        try:
            t = BVHTree.FromObject(ev, dg)
        except Exception:          # objects without mesh data
            t = None
        self._trees[key] = t
        return t

    def clearance(self, pos, radius=None):
        """The nearest surface to `pos` among the meshes whose bounds come within `radius`: dict(distance, object,
        behind) or None when nothing is that near. behind=True: pos is on the back side of that surface (inside a
        closed mesh, under a ground plane)."""
        pos = Vector(pos)
        r = radius if radius is not None else max(self.min_distance, 0.05) * 2 + 0.25
        dg = bpy.context.evaluated_depsgraph_get()
        if self._vis is None:
            self._vis = _rendered_names(self._view_layer())
        best = None
        for o in self.scene.objects:
            if o.type not in ('MESH', 'CURVE', 'SURFACE', 'META', 'FONT') or o.name not in self._vis \
                    or o.name in self._excluded:
                continue
            ev = o.evaluated_get(dg)
            mw = ev.matrix_world
            cs = [mw @ Vector(c) for c in ev.bound_box]
            lo = Vector((min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs)))
            hi = Vector((max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs)))
            dx = max(lo.x - pos.x, 0, pos.x - hi.x)
            dy = max(lo.y - pos.y, 0, pos.y - hi.y)
            dz = max(lo.z - pos.z, 0, pos.z - hi.z)
            if math.sqrt(dx * dx + dy * dy + dz * dz) > r:
                continue
            t = self._tree(o, dg)
            if t is None:
                continue
            inv = mw.inverted_safe()
            loc, nor, _i, _d = t.find_nearest(inv @ pos)
            if loc is None:
                continue
            w = mw @ loc
            n = (inv.transposed().to_3x3() @ nor).normalized()
            d = (pos - w).length
            if best is None or d < best['distance']:
                best = {'distance': d, 'object': o.name, 'behind': (pos - w).dot(n) < 0, 'point': w}
        return best

    # ------------------------------------------------------------------ the keyed path
    def check_camera(self, cam, span=None, target=None, every=1, min_distance=None, padding=None, log=True):
        """Walk the camera's real animated path (frame_set at every `every` frame of span; default the scene range)
        and report problems as runs: [{kind, object, frames: [a, b], worst, at}]. target: what the camera looks at
        (a target spec); default its DOF focus object, else the point focus_distance (or 3 m) down its view axis."""
        sc = self.scene
        fa, fb = span if span else (sc.frame_start, sc.frame_end)
        mind = self.min_distance if min_distance is None else min_distance
        tfn = C.target_fn(target) if target is not None else None
        keep = sc.frame_current
        per = []
        for f in range(int(fa), int(fb) + 1, max(1, int(every))):
            sc.frame_set(f)
            m = cam.matrix_world
            pos = m.translation.copy()
            fwd = -(m.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
            if tfn is not None:
                tgt = Vector(tfn())
            elif cam.data.dof.focus_object is not None:
                tgt = cam.data.dof.focus_object.matrix_world.translation.copy()
            else:
                tgt = pos + fwd * (cam.data.dof.focus_distance or 3.0)
            near = self.clearance(pos, radius=max(mind, cam.data.clip_start) + 0.25)
            if near:
                if near['behind']:
                    per.append((f, 'inside', near['object'], near['distance']))
                elif near['distance'] < cam.data.clip_start * 1.5:
                    per.append((f, 'clip', near['object'], near['distance']))
                elif near['distance'] < mind:
                    per.append((f, 'tight', near['object'], near['distance']))
            sl = self.is_clear(pos, tgt, padding)
            if not sl['clear']:
                want = (pos - tgt).length
                kind = 'blocked' if sl['distance'] < want * 0.5 else 'tight_sightline'
                per.append((f, kind, sl['object'], sl['distance']))
        sc.frame_set(keep)
        issues = _runs(per, every)
        if log:
            tag = f'[camera-safety] {cam.name} {fa}-{fb}'
            if issues:
                for i in issues:
                    print(f"{tag}: {i['kind'].upper()} by {i['object']!r} frames {i['frames'][0]}-{i['frames'][1]} "
                          f"(worst {i['worst']:.3f} m at {i['at']})", flush=True)
            else:
                print(f'{tag}: clear at every {every} frame(s)', flush=True)
        return issues

    # ------------------------------------------------------------------ planned paths (the WebGPU API)
    def check_path(self, shots, samples_per_segment=12, padding=None, log=True):
        """checkPath: sightlines at planned keyframes and smoothstep points between them. shots: [{time (or frame),
        position, target}]. Issues: {index (-1 between keys), time, position, target, obstruction, hit_distance,
        desired_distance, severity 'blocked'|'tight', suggestion (a clear position at the same distance, or None)}."""
        pad = self.padding if padding is None else padding
        issues = []

        def at(i):
            s = shots[i]
            return Vector(s['position']), Vector(s['target']), s.get('time', s.get('frame', i))

        def point(pos, tgt, index, time):
            chk = self.is_clear(pos, tgt, pad)
            if chk['clear']:
                return
            want = (pos - tgt).length
            issues.append({'index': index, 'time': round(float(time), 3), 'position': [round(v, 2) for v in pos],
                           'target': [round(v, 2) for v in tgt], 'obstruction': chk['object'],
                           'hit_distance': round(chk['distance'], 3), 'desired_distance': round(want, 3),
                           'severity': 'blocked' if chk['distance'] < want * 0.5 else 'tight',
                           'suggestion': self._suggest(pos, tgt, pad)})

        for i in range(len(shots)):
            p, t, tm = at(i)
            point(p, t, i, tm)
        for i in range(len(shots) - 1):
            pa, ta, tma = at(i)
            pb, tb, tmb = at(i + 1)
            for s in range(1, samples_per_segment + 1):
                a = s / (samples_per_segment + 1)
                k = C.ease(a, 'smooth')
                point(pa.lerp(pb, k), ta.lerp(tb, k), -1, tma + (tmb - tma) * a)
        issues.sort(key=lambda x: x['time'])
        if log:
            if issues:
                print(f'[camera-safety] check_path found {len(issues)} issue(s):', flush=True)
                for x in issues:
                    lab = f"keyframe {x['index']}" if x['index'] >= 0 else 'interpolated'
                    print(f"  t={x['time']} ({lab}) {x['severity']} by {x['obstruction']!r} at {x['hit_distance']} m / "
                          f"{x['desired_distance']} m" + (f" -- try {x['suggestion']}" if x['suggestion'] else
                                                          ' -- no clear alternative found'), flush=True)
            else:
                print('[camera-safety] check_path: all clear', flush=True)
        return issues

    def _suggest(self, pos, tgt, pad, n=24):
        """The clear position nearest `pos` on a Fibonacci sphere round the target at the same distance (not more than
        0.5 m below the target)."""
        rad = (pos - tgt).length
        best, bd = None, math.inf
        phi = (1 + 5 ** 0.5) / 2
        for i in range(n):
            z = 1 - 2 * i / (n - 1)
            r = math.sqrt(max(0.0, 1 - z * z))
            th = 2 * math.pi * i / phi
            c = Vector((tgt.x + r * math.cos(th) * rad, tgt.y + r * math.sin(th) * rad, tgt.z + z * rad))
            if c.z < tgt.z - 0.5:
                continue
            if self.is_clear(c, tgt, pad)['clear']:
                d = (c - pos).length
                if d < bd:
                    best, bd = c, d
        return [round(v, 1) for v in best] if best else None

    def safe_position(self, desired, target, padding=None, min_distance=None):
        """safePosition: `desired` pulled in toward the target until its sightline is clear (a last resort; prefer
        fixing the path: independent corrections jump as occluders change)."""
        pad = self.padding if padding is None else padding
        mind = self.min_distance if min_distance is None else min_distance
        desired, target = Vector(desired), Vector(target)
        v = desired - target
        dist = v.length
        if dist < 1e-3:
            return desired.copy()
        hit = self._ray(target, v, dist)
        if hit:
            safe = max(mind, hit[0] - pad)
            if safe < dist:
                return target + v.normalized() * safe
        return desired.copy()


def _runs(per, every):
    """Per-frame findings -> runs of consecutive frames with the same kind and object."""
    open_, out = {}, []
    for f, kind, obj, d in per:
        r = open_.get((kind, obj))
        if r and f - r['frames'][1] <= every:
            r['frames'][1] = f
            if d < r['worst']:
                r['worst'], r['at'] = d, f
        else:
            r = {'kind': kind, 'object': obj, 'frames': [f, f], 'worst': d, 'at': f}
            open_[(kind, obj)] = r
            out.append(r)
    out.sort(key=lambda r: (r['frames'][0], r['kind']))
    return out

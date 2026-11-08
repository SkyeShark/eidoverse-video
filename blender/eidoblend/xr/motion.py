"""eidoblend.xr.motion: animation that survives Blender's glTF exporter, for an XR page.

What the exporter carries by itself (export_animation_mode 'SCENE', sampled every frame, which this package uses):
object transforms from keys, NLA strips, drivers, constraints and parenting (it samples the evaluated scene), armature
poses (skins, VRMA clips included), shape-key values (morph target weights). What it cannot carry:
  - motion that lives in a Geometry Nodes tree or a particle system (instances moved by the scene time, a scatter):
    instances_to_objects() samples the instances every frame and makes each a real object with keyed transforms
    (the instanced mesh shared); still instances become linked duplicates under one empty, which the exporter writes as
    EXT_mesh_gpu_instancing (one draw, three's InstancedMesh);
  - a mesh that deforms by anything but its armature (Geometry Nodes, Wave, Displace, a cloth or ocean cache):
    deform_to_shape_keys() samples the evaluated surface into shape keys, one per sampled frame, and keys their
    weights to cross-fade from one to the next: glTF morph targets with an animated weight per target;
  - a light's energy and colour, a material value, visibility (KHR_animation_pointer, which three.js's GLTFLoader does
    not read): property_tracks() samples them into the choreography JSON the page applies each frame.
detect() finds which objects need which, by comparing the evaluated scene at a few frames.
"""
from __future__ import annotations

import math

import bpy
from mathutils import Matrix

from . import _bl


def _frames(scene, step=1, frames=None):
    if frames is not None:
        return list(frames)
    return list(range(scene.frame_start, scene.frame_end + 1, max(1, int(step))))


def _probe_frames(scene, n=5):
    a, b = scene.frame_start, scene.frame_end
    if b <= a:
        return [a]
    return sorted({a + round((b - a) * k / (n - 1)) for k in range(n)})


def _has_geometry_motion(ob):
    """Modifiers other than the armature that can move vertices over time."""
    for m in ob.modifiers:
        if m.type in ('ARMATURE',) or not m.show_render:
            continue
        return True
    return False


def detect(scene, objects=None, probe=5):
    """{'instances': [objects whose instances move], 'still_instances': [objects with still instances],
    'deforming': [meshes whose evaluated vertices move other than by an armature], 'skinned': [...]}"""
    objs = [o for o in (objects or scene.objects) if o.visible_get() or not o.hide_render]
    keep = scene.frame_current
    frames = _probe_frames(scene, probe)
    inst_pose = {}
    verts = {}
    # a skinned mesh moves by its armature (glTF's skin); an extra modifier on it (a VRM's MToon outline) is applied
    # at the rest pose by the exporter and skinned with it, so it is never "deforming" here
    cand_deform = [o for o in objs if o.type == 'MESH' and _has_geometry_motion(o)
                   and not any(m.type == 'ARMATURE' for m in o.modifiers)]
    try:
        for f in frames:
            scene.frame_set(f)
            dg = bpy.context.evaluated_depsgraph_get()
            for inst in dg.object_instances:
                if not inst.is_instance or inst.parent is None:
                    continue
                par = inst.parent.original
                if objects is not None and par not in objects:
                    continue
                if par.type == 'MESH' and any(m.type == 'ARMATURE' for m in par.modifiers):
                    continue                           # a skinned mesh's own instances (a VRM's MToon outline)
                if par.type == 'META' or (par.type in ('CURVE', 'FONT', 'SURFACE')
                                          and not any(m.type == 'NODES' for m in par.modifiers)):
                    continue                           # the object's own surface (the exporter meshes curves, text)
                key = (par.name, inst.persistent_id[:])
                inst_pose.setdefault(par.name, {}).setdefault(tuple(key[1]), []).append(
                    tuple(round(x, 5) for row in inst.matrix_world for x in row))
            for o in cand_deform:
                ev = o.evaluated_get(dg)
                me = ev.data
                n = len(me.vertices)
                co = [0.0] * (3 * n)
                me.vertices.foreach_get('co', co)
                verts.setdefault(o.name, []).append((n, co[: 3 * min(n, 2000)], sum(co[::7]) if co else 0.0))
    finally:
        scene.frame_set(keep)
    moving, still = [], []
    for name, d in inst_pose.items():
        mv = any(len(set(v)) > 1 for v in d.values()) or len({len(v) for v in d.values()}) > 1
        (moving if mv else still).append(bpy.data.objects[name])
    deforming = []
    for name, rows in verts.items():
        counts = {r[0] for r in rows}
        if len(counts) > 1:
            deforming.append((bpy.data.objects[name], 'topology changes'))
            continue
        base = rows[0]
        if base[0] == 0:
            continue                                   # nothing realized (a tree that only makes instances)
        if any(max((abs(a - b) for a, b in zip(base[1], r[1])), default=0.0) > 1e-5 or abs(base[2] - r[2]) > 1e-4
               for r in rows[1:]):
            deforming.append((bpy.data.objects[name], 'deforms'))
    skinned = [o for o in objs if o.type == 'MESH' and any(m.type == 'ARMATURE' for m in o.modifiers)]
    return {'instances': moving, 'still_instances': still, 'deforming': deforming, 'skinned': skinned}


# ---------------------------------------------------------------------------------------- instances to objects ---

def _key_matrix(ob, mat, frame):
    loc, rot, sca = mat.decompose()
    ob.location, ob.rotation_quaternion, ob.scale = loc, rot, sca
    ob.keyframe_insert('location', frame=frame)
    ob.keyframe_insert('rotation_quaternion', frame=frame)
    ob.keyframe_insert('scale', frame=frame)


def instances_to_objects(source, scene=None, frames=None, step=1, collection=None, max_instances=4000,
                         still=False, max_still=100000, log=print):
    """Real objects for the instances `source` makes (Geometry Nodes, particles, collection instancing).

    Moving instances: one object per instance (by persistent id), the instanced mesh shared, transforms keyed at every
    sampled frame (LINEAR), scale 0 while an instance does not exist; at most max_instances of them (each is a node,
    a draw and its own animation channels in the GLB). Still instances (still=True, as detect() found them: one frame
    is sampled): linked duplicates under one empty, which the exporter writes as EXT_mesh_gpu_instancing (one draw per
    mesh), at most max_still. The source stops rendering. Returns {'objects': [...], 'moving': bool, 'meshes': n,
    'frames': n, 'instances': n, 'dropped': instances over the cap, not exported}."""
    sc = scene or bpy.context.scene
    fr = [sc.frame_current] if still and frames is None else _frames(sc, step, frames)
    cap = max_still if still else max_instances
    col = collection or (source.users_collection[0] if source.users_collection else sc.collection)
    keep = sc.frame_current
    tracks, meshes, mats, over = {}, {}, {}, set()
    own = False                # the source's own geometry beside its instances (a ground and the rocks on it)
    try:
        for f in fr:
            sc.frame_set(f)
            dg = bpy.context.evaluated_depsgraph_get()
            if f == fr[0] and source.type == 'MESH':
                own = len(source.evaluated_get(dg).data.vertices) > 0
            for inst in dg.object_instances:
                if not inst.is_instance or inst.parent is None or inst.parent.original != source:
                    continue
                pid = tuple(inst.persistent_id[:])
                io = inst.object
                if pid not in tracks:
                    if len(tracks) >= cap:
                        over.add(pid)
                        continue
                    tracks[pid] = {}
                    if io.type == 'MESH':
                        # the instanced geometry's evaluated mesh (one per distinct geometry in a frame); copied:
                        # meshes.new_from_object() returns an EMPTY mesh for a Geometry Nodes instance (5.2)
                        dkey = io.data.as_pointer()
                        if dkey not in meshes:
                            me = io.data.copy()
                            me.name = f'{source.name}_inst_{len(meshes)}'
                            meshes[dkey] = me
                        mats[pid] = meshes[dkey]
                    else:
                        mats[pid] = None
                tracks[pid][f] = inst.matrix_world.copy()
    finally:
        sc.frame_set(keep)
    moving = not still and any(len({tuple(round(x, 5) for row in m for x in row) for m in d.values()}) > 1
                               or len(d) < len(fr) for d in tracks.values())
    made = []
    if moving:
        for k, (pid, d) in enumerate(sorted(tracks.items())):
            me = mats[pid]
            ob = bpy.data.objects.new(f'{source.name}_{k:03d}', me)
            col.objects.link(ob)
            ob.rotation_mode = 'QUATERNION'
            zero = Matrix.Diagonal((1e-4, 1e-4, 1e-4, 1.0))
            last = None
            for f in fr:
                m = d.get(f)
                if m is None:
                    m = (last or Matrix.Identity(4)) @ zero
                else:
                    last = m
                _key_matrix(ob, m, f)
            _bl.set_interpolation(ob, 'LINEAR')
            made.append(ob)
    else:
        root = bpy.data.objects.new(f'{source.name}_instances', None)
        col.objects.link(root)
        root.matrix_world = Matrix.Identity(4)
        for k, (pid, d) in enumerate(sorted(tracks.items())):
            m = next(iter(d.values()))
            ob = bpy.data.objects.new(f'{source.name}_{k:04d}', mats[pid])
            col.objects.link(ob)
            ob.parent = root
            ob.matrix_world = m
            made.append(ob)
        made.insert(0, root)
    if not own:
        # nothing of its own to draw: the source goes (an object with geometry beside its instances stays, and the
        # export, which then writes only realized geometry, writes that geometry without the instances)
        source.hide_render = True
        source.hide_viewport = True
    source['xr_replaced_by'] = f'{len(tracks)} instance objects'
    if log:
        log(f'[xr.motion] {source.name}: {len(tracks)} instances -> objects '
            f'({"keyed every sampled frame" if moving else "still, under one empty"}), {len(meshes)} mesh(es), '
            f'{len(fr)} frames' + (', its own geometry kept' if own else '')
            + (f'; {len(over)} over the cap of {cap} NOT exported' if over else ''))
    return {'objects': made, 'moving': moving, 'meshes': len(meshes), 'frames': len(fr), 'instances': len(tracks),
            'dropped': len(over), 'own_geometry': own}


# -------------------------------------------------------------------------------------- deformation to morphs ---

def deform_to_shape_keys(ob, scene=None, frames=None, step=1, max_keys=48, max_mb=64.0, log=print):
    """Bake a deforming mesh (not by its armature) into shape keys keyed to cross-fade frame to frame.

    The mesh becomes its evaluated self at the first frame (modifiers applied, the deforming ones removed); a key per
    sampled frame holds that frame's vertex positions; weights are keyed 1 at their own frame and 0 at the
    neighbours', LINEAR, so the surface moves linearly between samples, as glTF's morph targets play. The number of
    keys is capped at max_keys (the step grows to fit), and the morph data (positions and normals, 24 bytes a vertex a
    key) at max_mb: a bigger mesh gets fewer keys; one too big for two raises RuntimeError before anything changes
    (export_xr then writes it still, at its first frame, and warns). Returns {'keys', 'step', 'vertices'}."""
    sc = scene or bpy.context.scene
    fr_all = _frames(sc, 1, frames)
    keep = sc.frame_current
    try:
        sc.frame_set(fr_all[0])
        nv0 = len(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.vertices)
    finally:
        sc.frame_set(keep)
    budget = int(max_mb * 1e6 // max(1, nv0 * 24))
    if budget < 2:
        raise RuntimeError(f'{ob.name}: {nv0} deforming vertices are over {max_mb:g} MB as two morph targets: '
                           'exported still, at its first frame')
    max_keys = min(int(max_keys), budget)
    n_frames = len(fr_all)
    st = max(int(step), math.ceil((n_frames - 1) / max(1, max_keys - 1)) if n_frames > 1 else 1)
    fr = fr_all[::st]
    if fr[-1] != fr_all[-1]:
        fr.append(fr_all[-1])
    keep = sc.frame_current
    positions = []
    try:
        sc.frame_set(fr[0])
        dg = bpy.context.evaluated_depsgraph_get()
        base = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        nv = len(base.vertices)
        for f in fr:
            sc.frame_set(f)
            dg = bpy.context.evaluated_depsgraph_get()
            me = ob.evaluated_get(dg).data
            if len(me.vertices) != nv:
                raise RuntimeError(f'{ob.name}: vertex count changes at frame {f} ({len(me.vertices)} vs {nv}); '
                                   'a mesh whose topology changes cannot become morph targets')
            co = [0.0] * (3 * nv)
            me.vertices.foreach_get('co', co)
            positions.append(co)
    finally:
        sc.frame_set(keep)
    old = ob.data
    base.name = f'{ob.name}_morphs'
    ob.data = base
    for m in list(ob.modifiers):
        if m.type != 'ARMATURE':
            ob.modifiers.remove(m)
    if old.users == 0:
        bpy.data.meshes.remove(old)
    ob.shape_key_add(name='Basis', from_mix=False)
    keys = []
    for k, (f, co) in enumerate(zip(fr, positions)):
        kb = ob.shape_key_add(name=f'f{f:05d}', from_mix=False)
        kb.data.foreach_set('co', co)
        keys.append(kb)
    sk = ob.data.shape_keys
    sk.use_relative = True
    for k, kb in enumerate(keys):
        for j, f in enumerate(fr):
            if abs(j - k) <= 1:
                kb.value = 1.0 if j == k else 0.0
                kb.keyframe_insert('value', frame=f)
        if k == 0:
            kb.value = 1.0
            kb.keyframe_insert('value', frame=sc.frame_start)
    _bl.set_interpolation(sk, 'LINEAR')
    if log:
        log(f'[xr.motion] {ob.name}: deformation -> {len(keys)} morph targets (every {st} frame(s)), {nv} vertices')
    return {'keys': len(keys), 'step': st, 'vertices': nv}


# ------------------------------------------------------------------------------- what glTF cannot carry: tracks ---

def animated_properties(scene):
    """[(kind, owner, data_path)] of keyed or driven values the glTF export cannot carry to three.js: light energy /
    colour, material node values, the world, object visibility, camera lens."""
    out = []

    def scan(kind, idb):
        ad = getattr(idb, 'animation_data', None)
        if ad is None:
            return
        paths = {fc.data_path for fc in _bl.fcurves(idb)} | {d.data_path for d in ad.drivers}
        for p in sorted(paths):
            out.append((kind, idb, p))
    seen = set()
    for ob in scene.objects:
        if ob.type == 'LIGHT' and ob.data.name not in seen:
            seen.add(ob.data.name)
            scan('light', ob.data)
        if ob.type == 'CAMERA' and ob.data.name not in seen:
            seen.add(ob.data.name)
            scan('camera', ob.data)
        for p in ('hide_render', 'hide_viewport'):
            if any(fc.data_path == p for fc in _bl.fcurves(ob)):
                out.append(('visibility', ob, p))
    # only the materials the scene's renderable meshes use: a material the export replaced (a VRM's MToon, whose
    # add-on drives its UV nodes) or one nothing draws is not the page's business
    used = []
    for ob in scene.objects:
        if ob.type != 'MESH' or ob.hide_render:
            continue
        for s in ob.material_slots:
            if s.material is not None and s.material.node_tree is not None and s.material not in used:
                used.append(s.material)
    for m in used:
        scan('material', m.node_tree)
    if scene.world is not None and scene.world.node_tree is not None:
        scan('world', scene.world.node_tree)
    return out


def emission_socket(tree, data_path):
    """The Principled 'Emission Strength' (or an Emission node's 'Strength') socket an F-curve path animates, or None."""
    try:
        sock = tree.path_resolve(data_path.rsplit('.', 1)[0])
    except (ValueError, AttributeError):
        return None
    if not isinstance(sock, bpy.types.NodeSocket):
        return None
    if (sock.node.type == 'BSDF_PRINCIPLED' and sock.name == 'Emission Strength') or \
            (sock.node.type == 'EMISSION' and sock.name == 'Strength'):
        return sock
    return None


def property_tracks(scene, frames=None, step=1):
    """Sample the values glTF cannot carry into tracks the page applies by name:
    {'lights': {light object: {'t': [...], 'intensity': [...] (glTF units, COMPAT), 'color': [[r, g, b], ...]}},
     'emission': {material: {'t': [...], 'strength': [...]}}, 'visible': {object: {'t': [...], 'v': [0/1 ...]}}}"""
    sc = scene
    fr = _frames(sc, step, frames)
    fps = sc.render.fps / sc.render.fps_base
    props = animated_properties(sc)
    lights = {}
    for ob in sc.objects:
        if ob.type == 'LIGHT' and any(k == 'light' and o == ob.data for k, o, _ in props):
            lights[ob.name] = ob
    mats = {}
    for k, o, p in props:
        if k != 'material':
            continue
        sock = emission_socket(o, p)
        if sock is not None:
            for m in bpy.data.materials:
                if m.node_tree == o:
                    mats[m.name] = (m, sock)
    vis = list(dict.fromkeys(o for k, o, p in props if k == 'visibility'))   # once each (hide_render + hide_viewport)
    out = {'lights': {}, 'emission': {}, 'visible': {}, 'fps': fps}
    if not (lights or mats or vis):
        return out
    keep = sc.frame_current
    try:
        for f in fr:
            sc.frame_set(f)
            t = (f - sc.frame_start) / fps
            for name, ob in lights.items():
                li = ob.data
                e = li.energy * (2 ** li.exposure if hasattr(li, 'exposure') else 1.0)
                inten = e if li.type == 'SUN' else e / (4 * math.pi)
                c = list(li.color)
                if getattr(li, 'use_temperature', False):
                    tc = li.temperature_color
                    c = [c[0] * tc[0], c[1] * tc[1], c[2] * tc[2]]
                d = out['lights'].setdefault(name, {'t': [], 'intensity': [], 'color': []})
                d['t'].append(round(t, 4))
                d['intensity'].append(round(inten, 5))
                d['color'].append([round(x, 4) for x in c])
            for name, (m, sock) in mats.items():
                d = out['emission'].setdefault(name, {'t': [], 'strength': []})
                d['t'].append(round(t, 4))
                d['strength'].append(round(float(sock.default_value), 5))
            for ob in vis:
                d = out['visible'].setdefault(ob.name, {'t': [], 'v': []})
                d['t'].append(round(t, 4))
                d['v'].append(0 if ob.hide_render else 1)
    finally:
        sc.frame_set(keep)
    return out

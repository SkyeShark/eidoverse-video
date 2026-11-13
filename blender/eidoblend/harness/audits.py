"""eidoblend.harness.audits: the runner's checks on a built scene, each one a ledger record.

The WebGPU runner sampled its trackers while it rendered; here the scene is keyed and baked before anything renders, so
every tracker samples the timeline with scene.frame_set at build time, and a long render never starts on a scene a
check can already see is wrong.

    preflight(scene, cfg)          missing images and libraries (Blender renders those pink), no camera, the frame range,
                                   colour management left non-AgX (a VRM import's usual side effect), no world, nothing
                                   lighting the scene, VRM-importer leftovers, simulation caches unbaked or baked short
                                   of the film's last frame (the simulation would freeze there)
    coverage(scene, policy)        audit_core.js on the scene: the body inventory (build_inventory: each object's own
                                   geometry and each instance a leaf), every object-flag declaration (map_declarations)
                                   and the global disables, as ledger records (ledger.coverage_records)
    motion(scene, cfg, policy)     every 3 frames: the animation envelope (wrong-pivot spin, sinking below the ground,
                                   teleports, scale drift) and the swept clearance of parts that turn in place (a rotor
                                   seated in its mount, or sweeping through a neighbour at some angles), sideways
                                   travellers; every frame: camera bounce; humanoid
                                   rigs that never leave their pose; humanoids that travel on sliding feet (locomotion);
                                   VRMs whose mouth never moves (lipsync); VRMs whose spring chains nothing keys
                                   (springs: no baked springs track, so their hair and tails hang still)
    framing(scene, cfg)            per shot (camera markers), at its middle frame: how much of the frame the dominant
                                   mass cluster among what that shot's camera sees covers (a speck warns; a camera that
                                   sees no subject at all warns)
    palette(scene, script_ns)      what the scene used (meshes, materials, lights, the eidoblend modules imported): info
    assets_used(assets, cfg)       declared assets the script never read; models beside the script it never declared

Detection never breaks a run: a check that fails is recorded SKIPPED with its error.
"""

from __future__ import annotations

import math
import os
import re
import sys
import traceback

import bpy
from mathutils import Vector

from . import ledger as L
from .config import frame_range, is_url

GEOMETRY_TYPES = {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'}


def _err(e):
    return f'{type(e).__name__}: {e}'


def _guard(led, check):
    """Decorator-free guard: use as `with _Guard(led, 'motion'):`."""
    return _Guard(led, check)


class _Guard:
    def __init__(self, led, check):
        self.led, self.check = led, check

    def __enter__(self):
        return self

    def __exit__(self, et, ev, tb):
        if et is None:
            return False
        if issubclass(et, (KeyboardInterrupt, SystemExit)):
            return False
        self.led.record(check=self.check, outcome='SKIPPED', cls='CORRECTNESS',
                        message=f'the check itself failed ({_err(ev)}); its obligations are UNOBSERVED. '
                                + ''.join(traceback.format_exception_only(et, ev)).strip()[:300])
        print(f'[audit:{self.check}] SKIPPED, the check failed:', ''.join(traceback.format_exception(et, ev, tb))[-1500:],
              flush=True)
        return True


# ------------------------------------------------------------------------------------------------ helpers ---

_VIS_CACHE = {}


def _visible_collections(scene):
    """Names of the scene's collections that render: not hidden for render themselves or above, not excluded from
    the view layer. (Blender hides an object through its collections, never through its parent.)"""
    vl = scene.view_layers[0] if scene.view_layers else None
    out = {scene.collection.name}

    def walk(lc, ok):
        for ch in lc.children:
            vis = ok and not ch.exclude and not ch.collection.hide_render
            if vis:
                out.add(ch.collection.name)
            walk(ch, vis)
    if vl is not None:
        walk(vl.layer_collection, True)
    return out


def render_visible(ob, scene=None) -> bool:
    """Would this object render: its own hide_render, and at least one of its collections visible to the render."""
    if ob.hide_render:
        return False
    scene = scene or bpy.context.scene
    key = (scene.name, scene.frame_current, len(bpy.data.collections))
    vis = _VIS_CACHE.get(key)
    if vis is None:
        _VIS_CACHE.clear()
        vis = _VIS_CACHE[key] = _visible_collections(scene)
    return any(c.name in vis for c in ob.users_collection)


def world_box(ob):
    """World-space AABB (min, max) of an object's own evaluated geometry, or None."""
    if ob.type not in GEOMETRY_TYPES:
        return None
    try:
        mw = ob.matrix_world
        pts = [mw @ Vector(c) for c in ob.bound_box]
    except (AttributeError, ReferenceError):
        return None
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    if not all(math.isfinite(v) for v in (*lo, *hi)):
        return None
    return lo, hi


def union(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return (Vector((min(a[0].x, b[0].x), min(a[0].y, b[0].y), min(a[0].z, b[0].z))),
            Vector((max(a[1].x, b[1].x), max(a[1].y, b[1].y), max(a[1].z, b[1].z))))


def armature_box(arm, margin=0.12):
    """A rig's bounds from its bone joints plus a flesh margin (cheap, centimetre-true for the motion checks)."""
    mw = arm.matrix_world
    pts = []
    for pb in arm.pose.bones:
        pts.append(mw @ pb.head)
        pts.append(mw @ pb.tail)
    if not pts:
        return None
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))) - Vector((margin,) * 3)
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))) + Vector((margin,) * 3)
    return lo, hi


def subtree_box(root):
    """Bounds of an object and everything parented under it; skinned meshes count through their rig's joints."""
    box = None
    obs = [root] + list(root.children_recursive)
    rigs = set()
    for ob in obs:
        if not render_visible(ob):
            continue
        if ob.type == 'ARMATURE':
            rigs.add(ob)
            box = union(box, armature_box(ob))
            continue
        if ob.type == 'MESH' and any(m.type == 'ARMATURE' and m.object for m in ob.modifiers):
            for m in ob.modifiers:
                if m.type == 'ARMATURE' and m.object and m.object not in rigs:
                    rigs.add(m.object)
                    box = union(box, armature_box(m.object))
            continue
        box = union(box, world_box(ob))
    return box


def scene_box(scene):
    box = None
    for ob in scene.objects:
        if render_visible(ob) and ob.type in GEOMETRY_TYPES:
            box = union(box, world_box(ob))
    return box


def is_humanoid_rig(ob) -> bool:
    if ob.type != 'ARMATURE' or len(ob.pose.bones) < 15:
        return False
    names = [b.name.lower() for b in ob.pose.bones]
    return any('hips' in n or n.endswith('pelvis') for n in names)


# ---- the locomotion and lipsync trackers' readings of a rig (the VRM add-on's data when it is there, names when not)
_VRM1_VISEMES = ('aa', 'ih', 'ou', 'ee', 'oh')
_VRM0_VISEMES = ('a', 'i', 'u', 'e', 'o')
_MOUTH_KEY = re.compile(r'mouth|mth|jaw|lip|viseme|vis_|^[aiueo]$|^vrc\.v_|[あいうえお]', re.I)
_CONTROL = re.compile(r'(^|[._\-])(ik|fk|mch|org|tweak|pole|target|ctrl)([._\-]|$)|toe', re.I)
_LEFT = re.compile(r'left|(^|[._\-\s])l([._\-\s]|$)', re.I)
_RIGHT = re.compile(r'right|(^|[._\-\s])r([._\-\s]|$)', re.I)


def _vrm_ext(arm):
    return getattr(arm.data, 'vrm_addon_extension', None) if arm.type == 'ARMATURE' else None


def human_bone(arm, key):
    """The bone the VRM add-on maps to a human bone ('hips', 'left_foot', 'right_foot', ...), VRM 1.0 or 0.x; None
    when the rig carries no VRM data or does not map it."""
    ext = _vrm_ext(arm)
    if ext is None:
        return None
    try:
        n = getattr(ext.vrm1.humanoid.human_bones, key).node.bone_name
        if n and n in arm.pose.bones:
            return n
    except Exception:                                              # noqa: BLE001 - another add-on version
        pass
    camel = key.split('_')[0] + ''.join(w.title() for w in key.split('_')[1:])
    try:
        for b in ext.vrm0.humanoid.human_bones:
            if b.bone == camel and b.node.bone_name in arm.pose.bones:
                return b.node.bone_name
    except Exception:                                              # noqa: BLE001
        pass
    return None


def rig_feet(arm):
    """(hips, left foot, right foot) bone names: the VRM mapping first, else by name (a bone named for the hips or
    pelvis; per side the plainest bone named 'foot': no IK / MCH / ORG / pole / toe parts). Any may be None."""
    hips = human_bone(arm, 'hips')
    left, right = human_bone(arm, 'left_foot'), human_bone(arm, 'right_foot')
    names = [b.name for b in arm.pose.bones]
    if hips is None:
        c = sorted((n for n in names if 'hips' in n.lower() or n.lower().endswith('pelvis')), key=len)
        hips = c[0] if c else None
    if left is None or right is None:
        feet = [n for n in names if 'foot' in n.lower() and not _CONTROL.search(n)]
        lc = sorted((n for n in feet if _LEFT.search(n) and not _RIGHT.search(n)), key=len)
        rc = sorted((n for n in feet if _RIGHT.search(n) and not _LEFT.search(n)), key=len)
        left = left or (lc[0] if lc else None)
        right = right or (rc[0] if rc else None)
    return hips, left, right


def mouth_channels(arm):
    """What can move a rig's mouth, as (label, getter) pairs read at the current frame: the viseme expressions' bound
    shape keys and the add-on's preview values (VRM 1.0 aa/ih/ou/ee/oh, VRM 0.x a/i/u/e/o), and any shape key named for
    a mouth on the meshes under the rig (a face plate's own 'mouth.wide' / 'mouth.round', MMD 'あ', 'JawOpen' ...)."""
    out, seen = [], set()

    def add_key(ob, kn):
        if (ob.name, kn) in seen or ob.type != 'MESH' or not ob.data.shape_keys or kn not in ob.data.shape_keys.key_blocks:
            return
        seen.add((ob.name, kn))
        kb = ob.data.shape_keys.key_blocks[kn]
        if kb == ob.data.shape_keys.reference_key:
            return
        out.append((f'{ob.name}:{kn}', lambda kb=kb: kb.value))
    ext = _vrm_ext(arm)
    if ext is not None:
        try:
            pre = ext.vrm1.expressions.preset
            for v in _VRM1_VISEMES:
                e = getattr(pre, v, None)
                if e is None:
                    continue
                for b in e.morph_target_binds:
                    o = bpy.data.objects.get(b.node.mesh_object_name or '')
                    if o is not None:
                        add_key(o, b.index)
                if hasattr(e, 'preview'):
                    out.append((f'expression {v}', lambda e=e: float(e.preview)))
        except Exception:                                          # noqa: BLE001
            pass
        try:
            for g in ext.vrm0.blend_shape_master.blend_shape_groups:
                if g.preset_name in _VRM0_VISEMES:
                    for b in g.binds:
                        o = bpy.data.objects.get(b.mesh.mesh_object_name or '')
                        if o is not None:
                            add_key(o, b.index)
                    if hasattr(g, 'preview'):
                        out.append((f'blend shape {g.preset_name}', lambda g=g: float(g.preview)))
        except Exception:                                          # noqa: BLE001
            pass
    for ob in arm.children_recursive:
        if ob.type == 'MESH' and ob.data.shape_keys:
            for kb in ob.data.shape_keys.key_blocks:
                if _MOUTH_KEY.search(kb.name):
                    add_key(ob, kb.name)
    return out


def is_vrm(arm) -> bool:
    """An armature the VRM add-on imported (its extension data names the hips)."""
    return _vrm_ext(arm) is not None and human_bone(arm, 'hips') is not None


def shots(scene):
    """[(first frame, last frame, camera)] from markers bound to cameras, or the whole range with scene.camera."""
    fs, fe = scene.frame_start, scene.frame_end
    ms = sorted([m for m in scene.timeline_markers if m.camera is not None], key=lambda m: m.frame)
    if not ms:
        return [(fs, fe, scene.camera)]
    out = []
    cur_cam = scene.camera
    start = fs
    for m in ms:
        if m.frame <= fs:
            cur_cam = m.camera
            continue
        if m.frame > fe:
            break
        out.append((start, m.frame - 1, cur_cam))
        start, cur_cam = m.frame, m.camera
    out.append((start, fe, cur_cam))
    return [s for s in out if s[0] <= s[1] and s[2] is not None]


# ---------------------------------------------------------------------------------------------- preflight ---

def preflight(led, scene, cfg, notes=()):
    """Checks before any frame renders. Returns False if the scene cannot render at all (no camera)."""
    ok = True
    with _guard(led, 'preflight'):
        for n in notes:
            led.record(check='preflight.settings', outcome='PASS', cls='INFO', message=n)
        cams = [m.camera for m in scene.timeline_markers if m.camera]
        if scene.camera is None and not cams:
            led.record(check='preflight.camera', outcome='WARN', cls='CORRECTNESS',
                       message='no camera: setup() must set scene.camera (or bind cameras to timeline markers)')
            ok = False
        else:
            cam = scene.camera or cams[0]
            led.record(check='preflight.camera', outcome='PASS', cls='INFO',
                       message=f"camera '{cam.name}'" + (f' + {len(cams)} marker-bound cuts' if cams else ''))
        se = scene.sequence_editor
        shown = [s for s in (getattr(se, 'strips_all', None) or getattr(se, 'sequences_all', None) or [])
                 if s.type != 'SOUND' and not s.mute] if se is not None else []
        if shown and scene.render.use_sequencer:
            led.record(check='preflight.sequencer', outcome='WARN', cls='CORRECTNESS', metrics={'strips': len(shown)},
                       message=f'the film scene has {len(shown)} picture strip(s) in its sequencer and '
                               'render.use_sequencer is on: the film renders the STRIPS, not the 3D view. Set '
                               'scene.render.use_sequencer = False, or edit in a scene of its own '
                               '(media.overlay.make_edit_scene)')
        fs, fe = frame_range(cfg)
        if (scene.frame_start, scene.frame_end) != (fs, fe):
            led.record(check='preflight.frames', outcome='WARN', cls='CORRECTNESS',
                       message=f'setup() changed the frame range to {scene.frame_start}-{scene.frame_end}; the config '
                               f'({cfg["duration"]} s at {cfg["fps"]} fps) says {fs}-{fe}: the config wins (it was reset)')
            scene.frame_start, scene.frame_end = fs, fe
        missing = []
        for img in bpy.data.images:
            if img.source not in ('FILE', 'SEQUENCE', 'TILED') or img.packed_file is not None or not img.filepath:
                continue
            if img.library is not None:
                continue
            p = bpy.path.abspath(img.filepath)
            if img.source == 'TILED' or '<UDIM>' in p:
                continue
            if not os.path.exists(p):
                missing.append(f"'{img.name}' ({p})")
        if missing:
            led.record(check='preflight.images', outcome='WARN', cls='CORRECTNESS',
                       metrics={'missing': len(missing)},
                       message=f'{len(missing)} image file(s) missing (they render pink): ' + ', '.join(missing[:6])
                       + (' ...' if len(missing) > 6 else ''))
        else:
            led.record(check='preflight.images', outcome='PASS', cls='INFO',
                       message=f'{len([i for i in bpy.data.images if i.source == "FILE"])} image file(s), all found')
        libs = [lib for lib in bpy.data.libraries if not os.path.exists(bpy.path.abspath(lib.filepath))]
        if libs:
            led.record(check='preflight.libraries', outcome='WARN', cls='CORRECTNESS',
                       message='linked libraries missing: ' + ', '.join(bpy.path.abspath(l.filepath) for l in libs))
        vs = scene.view_settings
        if vs.view_transform != 'AgX':
            led.record(check='preflight.colour', outcome='WARN', cls='REVIEW',
                       message=f"view transform is '{vs.view_transform}' (look '{vs.look}'), not AgX: an importer "
                               "(the VRM add-on sets Standard unless set_view_transform_to_standard_on_import=False) "
                               'or a deliberate choice. Say which.')
        else:
            led.record(check='preflight.colour', outcome='PASS', cls='INFO',
                       message=f"AgX, look '{vs.look}', exposure {vs.exposure:+.2f}")
        leftovers = [o.name for o in scene.objects if o.name.startswith('BlenderVrmAddonImport')]
        if leftovers:
            led.record(check='preflight.vrm_import', outcome='WARN', cls='CORRECTNESS',
                       message=f'VRM importer leftovers in the scene: {", ".join(leftovers[:5])}: remove them')
        lights = [o for o in scene.objects if o.type == 'LIGHT' and render_visible(o) and o.data.energy > 0]
        emissive = _emissive_materials(scene)
        w = scene.world
        world_lit = bool(w) and _world_emits(w)
        if w is None:
            led.record(check='preflight.world', outcome='WARN', cls='REVIEW',
                       message='no world: the background renders black and no light comes from the sky. A set that '
                               'needs a sky uses the sky family\'s make_sky; a studio may choose none. Say which.')
        if not lights and not emissive and not world_lit:
            led.record(check='preflight.light', outcome='WARN', cls='CORRECTNESS',
                       message='nothing lights this scene: no lights, no emissive materials, no world light')
        else:
            led.record(check='preflight.light', outcome='PASS', cls='INFO',
                       message=f'{len(lights)} light(s), {len(emissive)} emissive material(s), world '
                               + ('emits' if world_lit else ('dark' if w else 'none')))
        unbaked, short = [], []
        fe = scene.frame_end

        def judge(name, pc, ranged=True):
            if not pc.is_baked:
                unbaked.append(name)
            elif ranged and pc.frame_end < fe:
                short.append(f'{name} ends at frame {pc.frame_end}')
        for ob in scene.objects:
            for m in ob.modifiers:
                pc = getattr(m, 'point_cache', None)
                if pc is not None:
                    judge(f'{ob.name}/{m.name}', pc)
                if m.type == 'FLUID' and m.fluid_type == 'DOMAIN' and m.domain_settings is not None:
                    ds = m.domain_settings
                    if not ds.has_cache_baked_any:
                        unbaked.append(f'{ob.name}/{m.name} (fluid domain: the harness does not bake fluids)')
                    elif ds.cache_frame_end < fe:
                        short.append(f'{ob.name}/{m.name} (fluid) ends at frame {ds.cache_frame_end}')
            for ps in getattr(ob, 'particle_systems', []):
                judge(f'{ob.name}/{ps.name}', ps.point_cache, ranged=False)   # emission + lifetime set its range
        rbw = scene.rigidbody_world
        if rbw is not None and rbw.point_cache is not None and rbw.collection is not None:
            judge('rigid body world', rbw.point_cache)
        if unbaked:
            led.record(check='preflight.caches', outcome='WARN', cls='CORRECTNESS',
                       message=f'unbaked simulation caches (a jumped frame would differ from the film): '
                               + ', '.join(unbaked[:6]))
        if short:
            led.record(check='preflight.caches', outcome='WARN', cls='CORRECTNESS',
                       message=f'simulation cache(s) baked short of the film, which ends at frame {fe}: '
                               + ', '.join(short[:6]) + '. The simulation HOLDS STILL after that frame. Leave the '
                               "baking to the build (it stretches unbaked caches to the film's end), or set "
                               f'frame_end = {fe} before baking.')
        if not unbaked and not short:
            n = len([1 for ob in scene.objects for m in ob.modifiers if getattr(m, 'point_cache', None) is not None]) \
                + len([1 for ob in scene.objects for _ in getattr(ob, 'particle_systems', [])]) \
                + (1 if rbw is not None and rbw.collection is not None else 0)
            if n:
                led.record(check='preflight.caches', outcome='PASS', cls='INFO',
                           message=f"{n} simulation cache(s), baked to the film's last frame ({fe})")
    return ok


def _emissive_materials(scene):
    found = set()
    for ob in scene.objects:
        if not render_visible(ob) or ob.type not in GEOMETRY_TYPES:
            continue
        for slot in ob.material_slots:
            m = slot.material
            if not m or m.name in found or not m.use_nodes or not m.node_tree:
                continue
            for n in m.node_tree.nodes:
                if n.bl_idname == 'ShaderNodeEmission':
                    s = n.inputs.get('Strength')
                    if s is None or s.is_linked or s.default_value > 0:
                        found.add(m.name)
                elif n.bl_idname == 'ShaderNodeBsdfPrincipled':
                    s = n.inputs.get('Emission Strength')
                    c = n.inputs.get('Emission Color')
                    if s is not None and (s.is_linked or s.default_value > 0) and c is not None and \
                            (c.is_linked or max(c.default_value[:3]) > 0):
                        found.add(m.name)
    return sorted(found)


def _world_emits(world) -> bool:
    if not world.use_nodes or not world.node_tree:
        return max(world.color) > 0
    for n in world.node_tree.nodes:
        if n.bl_idname == 'ShaderNodeBackground':
            s, c = n.inputs.get('Strength'), n.inputs.get('Color')
            if (s.is_linked or s.default_value > 0) and (c.is_linked or max(c.default_value[:3]) > 0):
                return True
    return False


# ------------------------------------------------------------------------------------------------ coverage ---

def _flags_of(idblock):
    out = {}
    for k in idblock.keys():
        c = L.canonical_flag(k, L.OBJECT_FLAG_ALIASES)
        if c in L.OBJECT_FLAGS or c == 'assembly':
            v = idblock[k]
            if v:
                out[c] = v
    return out


def _provenance(ob):
    p = ob
    while p is not None:
        v = p.get('eido_src_asset')
        if v:
            return str(v)
        p = p.parent
    for c in ob.users_collection:
        v = c.get('eido_src_asset')
        if v:
            return str(v)
    return None


MAX_INSTANCES = 20000      # instances beyond this many are recorded UNAUDITED (never passed)
_UNUSED_ID = 2147483647


def _local_geometry(ob, ev):
    """(local bbox (min, max) as tuples, triangle count) of an object's OWN evaluated geometry, or None when it has
    none. A Geometry Nodes object's bound_box would include the instances it makes (the engine's 'aggregate AABB',
    empty space included): its own mesh is read instead, and its instances become leaves of their own."""
    import numpy as np
    own_mesh = ob.type == 'MESH' and not any(m.type == 'NODES' and m.show_render for m in ob.modifiers)
    if own_mesh and ev.data is not None:
        me = ev.data
        if not len(me.vertices):
            return None
        bb = [tuple(c) for c in ev.bound_box]
        lt = np.empty(len(me.polygons), np.int32)
        me.polygons.foreach_get('loop_total', lt)
        return (tuple(min(c[k] for c in bb) for k in range(3)), tuple(max(c[k] for c in bb) for k in range(3))), \
            int(np.maximum(lt - 2, 0).sum())
    try:
        me = ev.to_mesh()
    except RuntimeError:
        return None
    try:
        if me is None or not len(me.vertices):
            return None
        co = np.empty(len(me.vertices) * 3, np.float64)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        me.calc_loop_triangles()
        return (tuple(co.min(0)), tuple(co.max(0))), len(me.loop_triangles)
    finally:
        ev.to_mesh_clear()


def _leaf(lid, label, local_box, mw, tris, visible, deforming, prov, owner):
    lo, hi = local_box
    pts = [mw @ Vector((x, y, z)) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    wlo = tuple(min(p[k] for p in pts) for k in range(3))
    whi = tuple(max(p[k] for p in pts) for k in range(3))
    sc = mw.to_scale()
    dims = [(hi[k] - lo[k]) * abs(sc[k]) for k in range(3)]
    return L.make_leaf(lid, label, (wlo, whi), dims, tris, visible, deforming, prov, owner)


def _deforming(ob):
    if any(m.type == 'ARMATURE' and m.object for m in ob.modifiers):
        return True
    sk = getattr(getattr(ob, 'data', None), 'shape_keys', None)
    return bool(sk and len(sk.key_blocks) > 1)


def scene_leaves(scene, provenance_of=None, max_instances=MAX_INSTANCES):
    """audit_core's leaves for a Blender scene: every geometry object's own geometry (hidden ones included: they are
    leaves that are not physical, so hidden ballast can never dilute a coverage fraction), and every instance it
    makes (collection instances, Geometry Nodes instances) as a virtual leaf of its own. Returns (leaves, notes,
    source_leaf_ids: {instanced object name: [instance leaf ids]})."""
    prov_of = provenance_of or _provenance
    dg = bpy.context.evaluated_depsgraph_get()
    leaves, notes, by_source = [], [], {}
    for ob in scene.objects:
        if ob.type not in GEOMETRY_TYPES:
            continue
        try:
            ev = ob.evaluated_get(dg)
        except (RuntimeError, ReferenceError):
            ev = ob
        geo = _local_geometry(ob, ev)
        if geo is None:
            continue
        box, tris = geo
        if not all(math.isfinite(v) for v in (*box[0], *box[1])):
            notes.append({'kind': 'SKIPPED', 'message': f"'{ob.name}' has non-finite local bounds: UNAUDITED."})
            continue
        leaves.append(_leaf(ob.name, ob.name, box, ev.matrix_world, tris, render_visible(ob, scene), _deforming(ob),
                            prov_of(ob), ob.name))
    n = 0
    for inst in dg.object_instances:
        if not inst.is_instance or inst.parent is None:
            continue
        o = inst.object
        if o.type not in GEOMETRY_TYPES:
            continue
        instancer = inst.parent.original
        if instancer == o.original and not any(m.type == 'NODES' for m in instancer.modifiers):
            continue                                   # an object's own realized geometry: counted above
        # (a Geometry Nodes object's instances report the object itself as their original: they are leaves)
        n += 1
        if n > max_instances:
            continue
        bb = [tuple(c) for c in o.bound_box]
        box = (tuple(min(c[k] for c in bb) for k in range(3)), tuple(max(c[k] for c in bb) for k in range(3)))
        if not all(math.isfinite(v) for v in (*box[0], *box[1])):
            notes.append({'kind': 'SKIPPED', 'message': f"an instance of '{o.original.name}' under "
                                                        f"'{instancer.name}' has non-finite bounds: UNAUDITED."})
            continue
        tris = 0
        if o.type == 'MESH' and o.data is not None:
            import numpy as np
            lt = np.empty(len(o.data.polygons), np.int32)
            o.data.polygons.foreach_get('loop_total', lt)
            tris = int(np.maximum(lt - 2, 0).sum())
        pid = '.'.join(str(i) for i in inst.persistent_id if i != _UNUSED_ID)
        lid = f'{instancer.name}#{pid}'
        leaves.append(_leaf(lid, f'{instancer.name}/{o.original.name}', box, inst.matrix_world.copy(), tris,
                            render_visible(instancer, scene), _deforming(o.original), prov_of(instancer),
                            instancer.name))
        by_source.setdefault(o.original.name, []).append(lid)
    if n > max_instances:
        notes.append({'kind': 'SKIPPED', 'message': f'{n - max_instances} instances beyond {max_instances} are '
                                                    'UNAUDITED, not passed.'})
    return leaves, notes, by_source


def build_inventory(scene, embed_frac=0.25, explicit_bodies=(), provenance_of=None, max_instances=MAX_INSTANCES):
    """audit_core's buildInventory on a Blender scene: canonical bodies from the scene's leaves.
    explicit_bodies: objects whose subtree a caller claims is ONE body (recorded as a coalescence declaration when
    the geometry does not join them, never honoured)."""
    leaves, notes, by_source = scene_leaves(scene, provenance_of, max_instances)
    reg = [(r.name, {o.name for o in [r] + list(r.children_recursive)}) for r in explicit_bodies or ()]
    inv = L.build_inventory(leaves, embed_frac, reg, notes)
    inv['source_leaf_ids'] = by_source
    return inv


def _leaves_under(ob, inv):
    out = set()
    for o in [ob] + list(ob.children_recursive):
        out.update(inv['owner_leaf_ids'].get(o.name, ()))
        out.update(inv.get('source_leaf_ids', {}).get(o.name, ()))
    return out


def map_declarations(scene, inventory, seated_objects=None):
    """audit_core's mapDeclarations on a Blender scene: every object custom property in ledger.OBJECT_FLAGS (or
    'assembly') declares over the leaves under it; seated characters (eido_seated, or seated_objects) join the
    support sensor."""
    nodes, seated = [], []
    for ob in scene.objects:
        fl = _flags_of(ob)
        if fl:
            nodes.append({'label': ob.name, 'flags': fl, 'leaf_ids': _leaves_under(ob, inventory)})
    seat = list(seated_objects) if seated_objects is not None else [o for o in scene.objects if o.get('eido_seated')]
    for ob in seat:
        seated.append({'label': ob.name, 'leaf_ids': _leaves_under(ob, inventory)})
    return L.map_declarations(inventory, nodes, seated)


def coverage(led, scene, policy=None, missing_checks=(), embed_frac=0.25):
    """The body inventory (leaves = each object's own geometry and each instance) and every declaration, as
    ledger records; the policy's global disables come with them, as in the engine."""
    with _guard(led, 'coverage'):
        inv = build_inventory(scene, embed_frac)
        decl = map_declarations(scene, inv)
        for r in L.coverage_records(decl, inv, policy, missing_checks):
            led.record(**_rec(r))
        return {'inventory': {'bodies': len(inv['bodies']), 'leaves': len(inv['leaves'])},
                'declarations': sorted(f"{d['flag']}@{d['source_label']}" for d in decl['declarations'])}
    return None


def _rec(r):
    r = dict(r)
    r['cls'] = r.pop('class', 'CORRECTNESS')
    return r


# -------------------------------------------------------------------------------------------------- motion ---

def _consider(scene):
    out = []
    for ob in scene.objects:
        if ob.parent is not None or ob.type in ('CAMERA', 'LIGHT', 'LIGHT_PROBE', 'SPEAKER'):
            continue
        if not render_visible(ob) and ob.type != 'EMPTY':
            continue
        out.append(ob)
        for c in ob.children:
            if c.type not in ('CAMERA', 'LIGHT', 'LIGHT_PROBE', 'SPEAKER') and render_visible(c):
                out.append(c)
    return out


def _no_motion(ob):
    p = ob
    while p is not None:
        if p.get('no_motion_check') or p.get('noMotionCheck'):
            return True
        p = p.parent
    return False


def motion(led, scene, cfg, policy):
    """The motion trackers, sampled with frame_set. Leaves the scene at its first frame."""
    fs, fe = scene.frame_start, scene.frame_end
    n = fe - fs + 1
    fps = float(cfg['fps'])
    no_motion = policy['flags'].get('_no_motion_check')
    no_loco = policy['flags'].get('_no_locomotion_check')
    env, side, cam_track, rigs = {}, {}, [], {}
    ground = None
    with _guard(led, 'motion'):
        sampled = list(range(fs, fe + 1, 3))
        if sampled[-1] != fe:
            sampled.append(fe)
        cand = [] if no_motion else [ob for ob in _consider(scene) if not _no_motion(ob)]
        humanoids = [ob for ob in scene.objects if is_humanoid_rig(ob)]
        loco = {} if no_loco else {r.name: {'rig': r, 'bones': rig_feet(r), 'last': None, 'path': 0.0, 'planted': 0.0,
                                            'peak': 0.0} for r in humanoids}
        mouths = {r.name: {'ch': mouth_channels(r), 'lo': {}, 'hi': {}} for r in scene.objects
                  if r.type == 'ARMATURE' and is_vrm(r)}
        for f in range(fs, fe + 1):
            scene.frame_set(f)
            cam = scene.camera
            if cam is not None:
                p = cam.matrix_world.translation
                fov = math.degrees(cam.data.angle) if cam.type == 'CAMERA' else 0.0
                cam_track.append((f, cam.name, p.x, p.y, p.z, fov))
            for rec in loco.values():
                _sample_locomotion(rec)
            for rec in mouths.values():
                for label, get in rec['ch']:
                    v = get()
                    rec['lo'][label] = min(rec['lo'].get(label, v), v)
                    rec['hi'][label] = max(rec['hi'].get(label, v), v)
            if f not in sampled:
                continue
            if ground is None:
                sb = scene_box(scene)
                ground = sb[0].z if sb else 0.0
            for ob in cand:
                _sample_envelope(env, ob)
                if ob.parent is None and ob.type in ('MESH', 'EMPTY') and not is_humanoid_rig(ob) and \
                        not any(c.type == 'ARMATURE' for c in ob.children_recursive):
                    _sample_sideways(side, ob)
            for rig in humanoids:
                sig = tuple(round(v, 5) for pb in rig.pose.bones for row in pb.matrix_basis for v in row)
                rec = rigs.setdefault(rig.name, {'first': sig, 'moved': False})
                if sig != rec['first']:
                    rec['moved'] = True
        _summarize_envelope(led, env, ground or 0.0)
        with _guard(led, 'motion.swept_clearance'):    # its own guard: a failure here leaves the others standing
            _summarize_swept(led, scene, env)
        _summarize_sideways(led, side)
        if no_motion:
            pass                                       # coverage() records the global disable as SKIPPED
        _summarize_camera(led, cam_track, fps)
        dur = n / fps
        for name, rec in rigs.items():
            if rec['moved']:
                led.record(check='motion.rig_pose', outcome='PASS', cls='INFO', message=f"rig '{name}' animates")
            elif dur > 1.0:
                led.record(check='motion.rig_pose', outcome='WARN', cls='CORRECTNESS',
                           message=f"humanoid rig '{name}' NEVER left its pose across {dur:.1f} s: a statue for the "
                                   'whole film. Key or play an action on it (or say it is meant to be still).')
        _summarize_locomotion(led, loco, fps, policy['flags'].get('_allow_manual_locomotion'))
        _summarize_lipsync(led, mouths)
        with _guard(led, 'motion.springs'):
            _summarize_springs(led, scene)
    scene.frame_set(fs)


LOCO_TRAVEL = 1.5          # m of travel: walking, not a sway (render_scene.mjs)
LOCO_STEP = 0.004          # m a frame: sub-mm jitter is not travel (render_scene.mjs)
LOCO_SLIDE = 0.6           # the planted foot's share of the body's travel past which the feet slide with it


def _sample_locomotion(rec):
    """One frame of a rig's travel: the hips' horizontal step, and the smaller of its two feet's steps (the planted
    foot of a walk stays put while the body moves over it; a slid body carries both feet with it)."""
    rig = rec['rig']
    hips, lf, rf = rec['bones']
    if hips is None:
        return
    mw = rig.matrix_world
    pts = [mw @ rig.pose.bones[b].head if b else None for b in (hips, lf, rf)]
    last, rec['last'] = rec['last'], pts
    if last is None:
        return
    d = [math.hypot(a.x - b.x, a.y - b.y) if a is not None and b is not None else None for a, b in zip(pts, last)]
    if d[0] <= LOCO_STEP:
        return
    rec['path'] += d[0]
    rec['peak'] = max(rec['peak'], d[0])
    if d[1] is not None and d[2] is not None:
        rec['planted'] += min(d[1], d[2])


def _summarize_locomotion(led, loco, fps, allow_manual):
    """render_scene.mjs's locomotion check: a humanoid that travels more than 1.5 m on its own feet without a
    controller slides while it plays a clip. The WebGPU runner knew which VRMs a controller registered; a built scene
    keeps no such registry, so this measures what the controller guarantees: a walking body's planted foot stays put
    while the body moves over it. A rig the controller keyed has planted feet; a rig moved by keyed location while a
    clip plays carries its feet along with it. A rig marked rig['eido_controller'] = True counts as driven."""
    moving = []
    for name, rec in loco.items():
        if rec['path'] <= LOCO_TRAVEL:
            continue
        moving.append(name)
        _h, lf, rf = rec['bones']
        frac = rec['planted'] / rec['path'] if lf and rf else None
        peak = rec['peak'] * fps
        driven = bool(rec['rig'].get('eido_controller')) or (frac is not None and frac < LOCO_SLIDE)
        m = {'travel_m': round(rec['path'], 2), 'peak_m_s': round(peak, 2),
             'planted_foot_share': None if frac is None else round(frac, 3)}
        if allow_manual:
            led.record(check='motion.locomotion', outcome='PASS', cls='INFO', bodies=[name], metrics=m,
                       message=f"'{name}' travelled {rec['path']:.1f} m (sampled; _allow_manual_locomotion leaves its "
                               'disposition to you)')
        elif driven:
            led.record(check='motion.locomotion', outcome='PASS', cls='INFO', bodies=[name], metrics=m,
                       message=f"'{name}' travelled {rec['path']:.1f} m on planted feet"
                               + (f' (the planted foot moved {frac:.0%} of the body\'s travel)' if frac is not None else
                                  ' (marked eido_controller)'))
        else:
            how = (f'its feet slide along with it (the planted foot moved {frac:.0%} of the body\'s travel)'
                   if frac is not None else 'and no feet were found to show it walks, nor an eido_controller mark')
            led.record(check='motion.locomotion', outcome='WARN', cls='CORRECTNESS', bodies=[name], metrics=m,
                       message=f"RE-RENDER REQUIRED: '{name}' travelled {rec['path']:.1f} m (peak {peak:.1f} m/s) and "
                               f'{how}: a body moved by keyed location while it plays a clip. Walk it with the '
                               'characters family (walk_path, or controller.Locomotion: they key the stride to the '
                               'speed and plant the feet with IK); never key a walking rig\'s location by hand. If it is '
                               'meant to be carried (a vehicle, a teleport), set _allow_manual_locomotion = True.')
    if loco and not moving:
        led.record(check='motion.locomotion', outcome='PASS', cls='INFO',
                   message=f'no humanoid travelled more than {LOCO_TRAVEL} m: no hand-rolled travel')


def _summarize_lipsync(led, mouths):
    """render_scene.mjs's [lipsync] tracker: a VRM whose mouth NEVER moved across the film. Advisory: a silent
    character never moves its mouth either. Read here on every channel that moves a mouth (mouth_channels): the
    viseme expressions and any mouth shape key, so a face driven past the expressions (the claudesona's) counts."""
    for name, rec in mouths.items():
        if not rec['ch']:
            led.record(check='motion.lipsync', outcome='PASS', cls='INFO', bodies=[name],
                       message=f"VRM '{name}': no viseme expressions or mouth shapes to read")
            continue
        span = {k: rec['hi'][k] - rec['lo'][k] for k in rec['hi']}
        best = max(span, key=span.get)
        if span[best] > 0.06:
            led.record(check='motion.lipsync', outcome='PASS', cls='INFO', bodies=[name],
                       metrics={'channel': best, 'range': round(span[best], 3)},
                       message=f"VRM '{name}' mouth animated ({best} spans {span[best]:.2f})")
        else:
            led.record(check='motion.lipsync', outcome='WARN', cls='REVIEW', bodies=[name],
                       metrics={'channels': len(span)},
                       message=f"VRM '{name}' mouth NEVER moved across the film ({len(span)} mouth channel(s) read). If "
                               'this character SPEAKS, you forgot to drive lipsync: eidoblend.characters.lipsync '
                               '(visemes_from_audio -> key_lipsync) keys aa/ih/ou/ee/oh from the vocals. A talking head '
                               'with a frozen mouth reads as broken. If the character is meant to be silent, ignore.')


def _keyed_bones(arm):
    """the pose bones keyed in the armature's playing actions: its active action and its unmuted NLA strips', each
    read through its own slot (Blender 5's layered actions)"""
    from bpy_extras import anim_utils
    ad = arm.animation_data
    if ad is None:
        return set()
    plays = [(ad.action, getattr(ad, 'action_slot', None))]
    plays += [(st.action, getattr(st, 'action_slot', None)) for tr in ad.nla_tracks if not tr.mute
              for st in tr.strips if not st.mute]
    out = set()
    for act, slot in plays:
        if act is None or slot is None:
            continue
        cb = anim_utils.action_get_channelbag_for_slot(act, slot)
        for fc in (cb.fcurves if cb is not None else ()):
            m = re.match(r'pose\.bones\["(.+?)"\]', fc.data_path)
            if m:
                out.add(m.group(1))
    return out


def _summarize_springs(led, scene):
    """A VRM whose spring chains (hair, tails, a tie: its VRMC_springBone) nothing keys hangs them in their rest shape
    for the whole film: characters.springs.bake_springs simulates them over the keyed body and keys them on the
    armature's '<name>|springs' NLA track (controller.Locomotion.bake and the robot body's bake do it by default). A
    track named so (as characters.springs.use_springs finds one), or keys on the spring bones themselves (a body keyed
    by hand), count as moving them. Advisory (REVIEW): a character may be meant to stand still."""
    import types
    for arm in scene.objects:
        if arm.type != 'ARMATURE' or not is_vrm(arm) or not any(
                c.type == 'MESH' and render_visible(c) for c in arm.children_recursive):
            continue
        springs = arm.data.vrm_addon_extension.spring_bone1.springs
        chains = sum(1 for s in springs if any(j.node.bone_name for j in list(s.joints)[:-1]))
        if not chains:
            continue
        from ..characters.springs import spring_bones
        bones = set(spring_bones(types.SimpleNamespace(arm=arm)))
        ad = arm.animation_data
        track = next((t for t in (ad.nla_tracks if ad is not None else ()) if t.name.endswith('|springs')
                      and not t.mute and any(st.action is not None and not st.mute for st in t.strips)), None)
        keyed = bones & _keyed_bones(arm)
        name = arm.name
        m = {'chains': chains, 'bones': len(bones), 'keyed_bones': len(keyed), 'track': track.name if track else None}
        if track is not None or keyed:
            how = f"baked on its track '{track.name}'" if track is not None else \
                f'keyed on {len(keyed)} of its {len(bones)} spring bones'
            led.record(check='motion.springs', outcome='PASS', cls='INFO', bodies=[name], metrics=m,
                       message=f"VRM '{name}': {chains} spring chain{'s' if chains != 1 else ''} {how}")
        else:
            led.record(check='motion.springs', outcome='WARN', cls='REVIEW', bodies=[name], metrics=m,
                       message=f"VRM '{name}': {chains} spring chain{'s' if chains != 1 else ''} and no baked springs "
                               'track: its hair and tails will not move; Locomotion.bake bakes them by default, '
                               'characters.springs.bake_springs for a hand-keyed body')


def _sample_envelope(S, ob):
    rec = S.get(ob.name)
    if rec is None:
        box = subtree_box(ob)
        if box is None:
            return
        size = max(box[1] - box[0])
        ml = ob.matrix_local if ob.parent else ob.matrix_world
        q0 = ml.to_quaternion()
        S[ob.name] = {'ob': ob, 'q0': q0, 'p0': ml.translation.copy(),
                      's0': ob.matrix_world.to_scale().x or 1.0, 'size': size, 'rotated': False, 'moving': False,
                      'drift': 0.0, 'centers': [], 'min_z': box[0].z, 'steps': [], 'last': None, 'scale': 1.0,
                      'quats': [q0]}
        return
    ml = ob.matrix_local if ob.parent else ob.matrix_world
    q = ml.to_quaternion()
    rec['quats'].append(q)                             # its turn, sample by sample (the swept-clearance check)
    ang = 2 * math.acos(min(1.0, abs(q.dot(rec['q0']))))
    if ang > 0.35:
        rec['rotated'] = True
    rec['drift'] = max(rec['drift'], (ml.translation - rec['p0']).length)
    grown = abs((ob.matrix_world.to_scale().x or 1.0) / (rec['s0'] or 1.0) - 1.0) > 0.05
    if not rec['moving'] and (rec['rotated'] or rec['drift'] > 0.1 or grown):
        rec['moving'] = True                           # a keyed `scale *= k` grows in place: a mover too
    if rec['moving']:
        box = subtree_box(ob)
        if box is not None:
            c = (box[0] + box[1]) / 2
            if rec['last'] is not None:
                rec['steps'].append((c - rec['last']).length)
            rec['last'] = c
            rec['centers'].append(c)
            rec['min_z'] = min(rec['min_z'], box[0].z)
            rec['scale'] = ob.matrix_world.to_scale().x or 1.0


def _summarize_envelope(led, S, ground):
    movers = warned = 0
    for name, rec in S.items():
        if not rec['moving'] or len(rec['centers']) < 3:
            continue
        ob = rec['ob']
        if any(S.get(p.name, {}).get('moving') for p in _ancestors(ob)):
            continue                                   # the topmost mover owns the warning
        movers += 1
        size = rec['size']
        if rec['rotated'] and rec['drift'] < max(0.1, 0.2 * size):
            mean = sum(rec['centers'], Vector()) / len(rec['centers'])
            orbit = max((c - mean).length for c in rec['centers'])
            if orbit > max(0.15, 0.08 * size):
                warned += 1
                led.record(check='motion.envelope', outcome='WARN', cls='CORRECTNESS', bodies=[name],
                           metrics={'orbit_m': round(orbit, 3)},
                           message=f"'{name}' ROTATES ABOUT THE WRONG PIVOT: its visual centre orbits a ~{orbit:.2f} m "
                                   'radius while it spins. Put the origin on the spin axis (parent the geometry to an '
                                   "empty AT the axis and rotate that). Intentional orbit: obj['no_motion_check'] = True.")
        sank = ground - rec['min_z']
        if sank > 0.25:
            warned += 1
            led.record(check='motion.envelope', outcome='WARN', cls='CORRECTNESS', bodies=[name],
                       metrics={'below_ground_m': round(sank, 3)},
                       message=f"'{name}' sweeps {sank:.2f} m BELOW the ground level of the scene during its motion "
                               "(through the floor at its lowest point). Intentional (a drill, a dive): "
                               "obj['no_motion_check'] = True.")
        if len(rec['steps']) > 4:
            st = sorted(rec['steps'])
            med, mx = st[len(st) // 2], st[-1]
            if mx > max(2.0, 4 * med, 1.5 * size):
                warned += 1
                led.record(check='motion.envelope', outcome='WARN', cls='CORRECTNESS', bodies=[name],
                           metrics={'max_step_m': round(mx, 3), 'median_step_m': round(med, 3)},
                           message=f"'{name}' TELEPORTS: one jump of ~{mx:.1f} m between samples against its typical "
                                   f'~{med:.2f} m step. Usually a wrapped time or a re-seeded path; ease it or hide the '
                                   "cut. Intentional: obj['no_motion_check'] = True.")
        ratio = rec['scale'] / (rec['s0'] or 1.0)
        if ratio > 1.5 or ratio < 0.67:
            warned += 1
            led.record(check='motion.envelope', outcome='WARN', cls='CORRECTNESS', bodies=[name],
                       metrics={'scale_ratio': round(ratio, 3)},
                       message=f"'{name}' scale drifted x{ratio:.2f} over the film. Intentional growth: "
                               "obj['no_motion_check'] = True.")
    if not warned:
        led.record(check='motion.envelope', outcome='PASS', cls='INFO', metrics={'movers': movers},
                   message=f'{movers} moving bod{"y" if movers == 1 else "ies"}: pivots, ground, steps and scale hold')


def _ancestors(ob):
    p = ob.parent
    while p is not None:
        yield p
        p = p.parent


# ---- swept-rotation clearance: a part that turns in place clears its static neighbours at every angle it turns through

SWEEP_SAMPLES = 240        # points over a turning part's surface, area-weighted (render_scene.mjs's N_SAMP)
SWEEP_OUTER = 40           # of those, the ones past 30 % of its reach, turned about its axis
SWEEP_ANGLES = 12          # angles of a full revolution tested (every 30 degrees)
SWEEP_STEP = math.pi / 6   # the widest gap between two tested angles of a part that turns through less than a revolution


def _twist(q, q0, axis):
    """The signed angle (rad, -pi..pi) the turn from q0 to q makes about `axis` (the twist part of q @ q0^-1)."""
    d = q @ q0.inverted()
    a = 2.0 * math.atan2(d.x * axis.x + d.y * axis.y + d.z * axis.z, d.w)
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def _spin_of(rec):
    """(spin axis in the parent's frame, the angles to test relative to the part's pose at the last frame, a full
    revolution?) for a part the envelope sampled turning, or None. The axis is that of the turn from the first sample to
    the sample turned furthest from it (the engine took the last frame's turn, which is none at all after a whole number
    of revolutions: a turntable keyed 0 -> 360 degrees). A part whose turn spans a revolution, or that turns more than a
    quarter turn between two samples (a fan seen every 3 frames passes through every angle), is tested at 12 angles of
    the whole revolution, as the engine tested every spinner; a part that turns through less (a scanning radar, a
    lever) is tested over the angles it turns through, every 30 degrees and both ends."""
    qs, q0 = rec['quats'], rec['q0']
    far = min(qs, key=lambda q: abs(q.dot(q0)))
    if 2 * math.acos(min(1.0, abs(far.dot(q0)))) < 0.35:
        return None
    rel = far @ q0.inverted()
    axis = Vector(rel.axis).normalized()
    turn = [_twist(qs[0], q0, axis)]
    for q in qs[1:]:
        t = _twist(q, q0, axis)
        turn.append(turn[-1] + (t - turn[-1] + math.pi) % (2.0 * math.pi) - math.pi)   # unwrapped, sample to sample
    lo, hi, cur = min(turn), max(turn), turn[-1]
    full = hi - lo >= 2.0 * math.pi * 11 / 12 or max((abs(b - a) for a, b in zip(turn, turn[1:])), default=0.0) \
        > math.pi / 2
    if full:
        return axis, [2.0 * math.pi * k / SWEEP_ANGLES for k in range(SWEEP_ANGLES)], True
    n = max(2, int(math.ceil((hi - lo) / SWEEP_STEP)) + 1)
    return axis, [lo + (hi - lo) * k / (n - 1) - cur for k in range(n)], False


def _surface_points(objs, seed, n=SWEEP_SAMPLES, dg=None):
    """n points spread over the world-space surface of objs by area (render_scene.mjs's barycentric walk: a point
    every 1/n of the total area, at a random place in its triangle), seeded so a build measures the same points."""
    import numpy as np
    from ..placement import _world as W
    parts = []
    for m in objs:
        co, tri = W.world_tris(m, dg)
        if len(tri):
            parts.append(co[tri])
    if not parts:
        return None
    P = np.concatenate(parts)
    area = 0.5 * np.linalg.norm(np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]), axis=1)
    P, area = P[area > 1e-10], area[area > 1e-10]
    if not len(P):
        return None
    cum = np.cumsum(area)
    idx = np.minimum(np.searchsorted(cum, (np.arange(n) + 0.5) * cum[-1] / n), len(P) - 1)
    rng = np.random.default_rng(seed)
    u, w = rng.random(n), rng.random(n)
    flip = u + w > 1.0
    u[flip], w[flip] = 1.0 - u[flip], 1.0 - w[flip]
    T = P[idx]
    return T[:, 0] + (T[:, 1] - T[:, 0]) * u[:, None] + (T[:, 2] - T[:, 0]) * w[:, None]


def _summarize_swept(led, scene, S):
    """render_scene.mjs's swept-rotation clearance, at the film's last frame: every part that turns in place (the
    envelope's spinners: turned past 0.35 rad while its origin drifted under max(0.1 m, a fifth of its size)) must
    clear its static neighbours at every angle it turns through, touching the world only at its bearing. Its surface
    points past 30 % of its reach (bearing and hub contact excluded by construction) are turned about the measured spin
    axis through the pivot, analytically (the scene is never moved), and each one inside a neighbour's box is tested
    for being enclosed by it: 5 of 6 axis rays hit the neighbour, the placement family's deep-clipping test. Neighbours
    are the other top-level objects that never move, unrelated to the part, whose box meets the part's swept box
    without holding all of it (a room or a dome around a mechanism is its setting, not its mount). A body that bends
    as it turns (a rig, a skinned or shape-keyed mesh) is left out: one pose turned through the turn proves nothing."""
    from mathutils import Matrix
    import numpy as np
    import zlib
    from ..placement import _world as W
    from ..placement.audits import _AXES
    dg = W.depsgraph()
    spinners = []
    for rec in S.values():
        if not rec['rotated'] or not rec['moving'] or rec['drift'] >= max(0.1, 0.2 * rec['size']):
            continue
        ob = rec['ob']
        sub = [ob] + list(ob.children_recursive)
        if any(o.type == 'ARMATURE' or (o.type == 'MESH' and _deforming(o)) for o in sub):
            continue
        spin = _spin_of(rec)
        if spin is not None:
            spinners.append((ob,) + spin)
    turning = {sp[0] for sp in spinners}
    neighbours = []                                    # (root, its geometry, its world box), measured once
    for o in (scene.objects if spinners else ()):
        if o.parent is not None or o.type in ('CAMERA', 'LIGHT', 'LIGHT_PROBE', 'SPEAKER') or o in turning \
                or not render_visible(o) or (S.get(o.name) or {}).get('moving'):
            continue
        meshes = W.collect(o)
        if not meshes:
            continue
        nb = None
        for m in meshes:
            b = W.box_of_object(m, dg)
            nb = b if nb is None else (Vector(map(min, nb[0], b[0])), Vector(map(max, nb[1], b[1])))
        neighbours.append((o, meshes, nb))
    found, full_n = 0, 0
    for ob, axis_l, angles, full in spinners:
        full_n += int(full)
        pivot = ob.matrix_world.translation.copy()
        axis = ((ob.parent.matrix_world.to_quaternion() @ axis_l) if ob.parent else axis_l).normalized()
        pts = _surface_points(W.collect(ob), zlib.crc32(ob.name.encode('utf-8')), dg=dg)
        if pts is None:
            continue
        piv, a = np.array(pivot), np.array(axis)
        rel = pts - piv
        radial = np.linalg.norm(rel - np.outer(rel @ a, a), axis=1)
        reach = float(radial.max())
        outer = pts[radial > 0.3 * reach]
        if len(outer) > SWEEP_OUTER:                   # spread over the whole part (the engine took the first 40)
            outer = outer[np.unique(np.linspace(0, len(outer) - 1, SWEEP_OUTER).round().astype(int))]
        if len(outer) < 6 or reach < 1e-4:
            continue
        r = Vector((reach * 1.05,) * 3)
        sweep = (pivot - r, pivot + r)
        turned = [[pivot + Matrix.Rotation(th, 3, axis) @ (Vector(p) - pivot) for p in outer] for th in angles]
        for root, meshes, nb in neighbours:
            if W.is_ancestor(root, ob) or not W.boxes_intersect(nb, sweep) or \
                    all(nb[0][k] <= sweep[0][k] and nb[1][k] >= sweep[1][k] for k in range(3)):
                continue                               # its own assembly, apart, or a shell around the whole sweep
            rays, far = W.Rays(meshes, dg), (nb[1] - nb[0]).length
            hit, worst = 0, 0.0
            for at in turned:
                inside = sum(1 for p in at if all(nb[0][k] <= p[k] <= nb[1][k] for k in range(3))
                             and sum(1 for d in _AXES if rays.cast(p, d, far)) >= 5)
                if inside:
                    hit += 1
                    worst = max(worst, inside / len(outer))
            if not hit:
                continue
            found += 1
            span = f"{len(angles)} angles of its revolution" if full else \
                f"{len(angles)} angles it turns through ({math.degrees(max(angles) - min(angles)):.0f} degrees)"
            m = {'angles_hit': hit, 'angles': len(angles), 'full_revolution': bool(full), 'enclosed_max': round(worst, 3)}
            if hit == len(angles):
                msg = (f"'{ob.name}' sits inside '{root.name}' at every one of the {span} (up to "
                       f"{round(worst * 100)}% of its outer points enclosed): it reads as seated INTO its mount, not "
                       'turning on a bearing. Stand it off along its spin axis: eidoblend.placement.mount_on(part, '
                       "mount, standoff=...) seats exactly that joint. Intentional: obj['no_motion_check'] = True.")
            else:
                msg = (f"'{ob.name}' sweeps through '{root.name}' at {hit} of the {span}: it clears at some angles "
                       'and cuts through at others; a small shift along its spin axis (or more standoff at the '
                       "bearing) frees the whole turn. Intentional: obj['no_motion_check'] = True.")
            led.record(check='motion.swept_clearance', outcome='WARN', cls='CORRECTNESS', bodies=[ob.name, root.name],
                       metrics=m, message=msg)
    if not found:
        led.record(check='motion.swept_clearance', outcome='PASS', cls='INFO',
                   metrics={'parts': len(spinners), 'full_revolution': full_n},
                   message=(f'{len(spinners)} part(s) turning in place clear their static neighbours at every angle '
                            f'they turn through ({full_n} through a full revolution)') if spinners else
                   'no part turns in place')


def _sample_sideways(M, ob):
    mw = ob.matrix_world
    rec = M.get(ob.name)
    if rec is None:
        box = subtree_box(ob)
        if box is None:
            return
        sx, sy = box[1].x - box[0].x, box[1].y - box[0].y
        elong = max(sx, sy) / max(0.001, min(sx, sy))
        axis_w = Vector((1, 0, 0)) if sx >= sy else Vector((0, 1, 0))
        axis_l = mw.to_quaternion().inverted() @ axis_w
        M[ob.name] = {'elong': elong, 'axis_l': axis_l, 'last': mw.translation.copy(), 'path': 0.0, 'move': 0, 'side': 0}
        return
    p = mw.translation
    d = p - rec['last']
    seg = math.hypot(d.x, d.y)
    if seg > 0.05:
        rec['path'] += seg
        rec['move'] += 1
        ax = mw.to_quaternion() @ rec['axis_l']
        ax.z = 0
        if ax.length_squared > 1e-6:
            ax.normalize()
            if abs((ax.x * d.x + ax.y * d.y) / seg) < 0.5:
                rec['side'] += 1
    rec['last'] = p.copy()


def _summarize_sideways(led, M):
    bad = 0
    for name, rec in M.items():
        if rec['path'] > 2.5 and rec['elong'] >= 1.35 and rec['move'] >= 4 and rec['side'] / rec['move'] > 0.6:
            bad += 1
            led.record(check='motion.sideways', outcome='WARN', cls='CORRECTNESS', bodies=[name],
                       metrics={'path_m': round(rec['path'], 2), 'side_fraction': round(rec['side'] / rec['move'], 2)},
                       message=f"'{name}' travelled {rec['path']:.1f} m SIDEWAYS (its long axis ~perpendicular to its "
                               f"travel for {round(100 * rec['side'] / rec['move'])}% of the trip). A vehicle or "
                               'creature faces where it goes: key its heading with its path. Intentional (a conveyor, '
                               "a crab): obj['no_motion_check'] = True.")
    if not bad and M:
        led.record(check='motion.sideways', outcome='PASS', cls='INFO', message='no sideways travellers')


def _summarize_camera(led, tr, fps):
    if len(tr) <= 8:
        led.record(check='motion.camera', outcome='PASS', cls='INFO', message='camera: too few frames to judge motion')
        return
    segs = []
    for row in tr:                                     # one segment per continuous run of one camera (cuts split)
        if not segs or segs[-1][-1][1] != row[1]:
            segs.append([])
        segs[-1].append(row)
    pos_rev = fov_rev = 0
    max_pos = max_fov = 0.0
    for seg in segs:
        pv = pf = None
        for k in range(1, len(seg)):
            v = (seg[k][2] - seg[k - 1][2], seg[k][3] - seg[k - 1][3], seg[k][4] - seg[k - 1][4])
            vm = math.sqrt(sum(c * c for c in v))
            if pv is not None:
                pm = math.sqrt(sum(c * c for c in pv))
                if sum(a * b for a, b in zip(v, pv)) < 0 and vm > 0.01 and pm > 0.01:
                    pos_rev += 1
                    max_pos = max(max_pos, min(vm, pm))
            pv = v
            fd = seg[k][5] - seg[k - 1][5]
            if pf is not None and fd * pf < 0 and abs(fd) > 0.05:
                fov_rev += 1
                max_fov = max(max_fov, min(abs(fd), abs(pf)))
            pf = fd
    dur = max(0.1, len(tr) / fps)
    pos_rate, fov_rate = pos_rev / dur, fov_rev / dur
    pos_bad, fov_bad = pos_rate > 5 and max_pos > 0.02, fov_rate > 5 and max_fov > 0.3
    if pos_bad or fov_bad:
        parts = []
        if pos_bad:
            parts.append(f'{pos_rev} position reversals ({pos_rate:.1f}/s)')
        if fov_bad:
            parts.append(f'{fov_rev} zoom reversals ({fov_rate:.1f}/s)')
        led.record(check='motion.camera', outcome='WARN', cls='CORRECTNESS',
                   metrics={'pos_reversals_per_s': round(pos_rate, 2), 'fov_reversals_per_s': round(fov_rate, 2)},
                   message='camera BOUNCES: ' + ', '.join(parts) + '. One eased move per shot; cut between shots, '
                           "don't bounce within one. (Subtle handheld is fine: this is large rapid oscillation.)")
    else:
        led.record(check='motion.camera', outcome='PASS', cls='INFO',
                   metrics={'pos_reversals_per_s': round(pos_rate, 2), 'shots': len(segs)},
                   message=f'smooth camera ({pos_rate:.1f} position reversals/s over {len(segs)} shot(s))')


# ------------------------------------------------------------------------------------------------- framing ---

IN_SHOT = 0.2              # a framing candidate counts as in a shot when this share of it is inside the frame


def view_fraction(scene, cam, box, n=5) -> float:
    """The share of a box inside this camera's frame and in front of its near clip, measured on an n x n x n
    lattice of points through it. (The rectangle around its projected corners would also take in a box that only
    passes beside a corner of the frame: shot B of test T16, a crate next to the camera, 1 % of it in a corner.)"""
    from bpy_extras.object_utils import world_to_camera_view
    near = cam.data.clip_start
    lo, hi = box
    corners = [world_to_camera_view(scene, cam, Vector((x, y, z)))
               for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    if all(v.z > near for v in corners) and (max(v.x for v in corners) < 0.0 or min(v.x for v in corners) > 1.0
                                             or max(v.y for v in corners) < 0.0 or min(v.y for v in corners) > 1.0):
        return 0.0                                     # wholly in front and wholly beside the frame
    if not any(v.z > near for v in corners):
        return 0.0                                     # wholly behind the camera
    steps = [k / (n - 1) for k in range(n)]
    inside = 0
    for a in steps:
        for b in steps:
            for c in steps:
                p = Vector((lo.x + (hi.x - lo.x) * a, lo.y + (hi.y - lo.y) * b, lo.z + (hi.z - lo.z) * c))
                v = world_to_camera_view(scene, cam, p)
                if v.z > near and 0.0 <= v.x <= 1.0 and 0.0 <= v.y <= 1.0:
                    inside += 1
    return inside / float(n ** 3)


def _centre_ray_hits(cam, box) -> bool:
    """Does the line of sight through the centre of the frame pass through the box (in front of the camera)?"""
    mw = cam.matrix_world
    o = mw.translation
    d = (mw.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized()
    t0, t1 = -math.inf, math.inf
    for ax in range(3):
        if abs(d[ax]) < 1e-12:
            if not box[0][ax] <= o[ax] <= box[1][ax]:
                return False
            continue
        a, b = (box[0][ax] - o[ax]) / d[ax], (box[1][ax] - o[ax]) / d[ax]
        t0, t1 = max(t0, min(a, b)), min(t1, max(a, b))
    return t0 <= t1 and t1 > cam.data.clip_start


def _in_view(scene, cam, box) -> bool:
    """A framing candidate is in a shot when a fifth of it is inside the frame, or when the camera looks straight
    at it (a close-up of something bigger than the frame)."""
    return view_fraction(scene, cam, box) >= IN_SHOT or _centre_ray_hits(cam, box)


def framing(led, scene):
    """For each shot: the share of the frame covered by the dominant mass cluster among what its camera sees, at
    the shot's middle frame."""
    from bpy_extras.object_utils import world_to_camera_view
    with _guard(led, 'framing'):
        for f0, f1, cam in shots(scene):
            mid = (f0 + f1) // 2
            scene.frame_set(mid)
            if cam is None or cam.type != 'CAMERA':
                led.record(check='framing', outcome='SKIPPED', cls='REVIEW', message=f'frames {f0}-{f1}: no camera')
                continue
            if cam.data.type != 'PERSP':
                led.record(check='framing', outcome='SKIPPED', cls='REVIEW',
                           message=f"frames {f0}-{f1}: camera '{cam.name}' is not perspective; VIEW the frames")
                continue
            cands = []
            for ob in scene.objects:
                if ob.type not in GEOMETRY_TYPES or not render_visible(ob):
                    continue
                b = world_box(ob)
                if b is None:
                    continue
                s = b[1] - b[0]
                span = max(s.x, s.y)
                if span > 150 and s.z < span * 0.05:
                    continue                           # ground/ocean slabs are backdrop, not subject
                dims = sorted((s.x, s.y, s.z), reverse=True)
                if dims[0] > 2.0 and dims[2] < 0.03 * dims[0]:
                    continue                           # floors, walls, ceilings as sheets: the set, not the subject
                cands.append({'box': b, 'c': (b[0] + b[1]) / 2,
                              'm': max(s.x, 0.01) * max(s.y, 0.01) * max(s.z, 0.01),
                              'run': dims[0] > 12 * max(dims[1], 0.01), 'name': ob.name})
            # the subject of THIS shot is chosen among what its camera sees (at least a fifth of each candidate in
            # frame): in a film of several shots the scene's dominant mass may be in another shot entirely
            seen = [k for k in cands if _in_view(scene, cam, k['box'])]
            if cands and not seen:
                near = min(cands, key=lambda k: (k['c'] - cam.matrix_world.translation).length)
                led.record(check='framing', outcome='WARN', cls='REVIEW',
                           message=f"frames {f0}-{f1} ('{cam.name}', frame {mid}): none of the scene's {len(cands)} "
                                   f"subject candidates is in view (the nearest is '{near['name']}'): the camera may "
                                   'be aimed away from the action. VIEW the frames; say so if the shot is meant to '
                                   'hold on the set alone.')
                continue
            kept = seen
            for _ in range(3):
                if len(kept) <= 1:
                    break
                M = sum(k['m'] for k in kept)
                if M <= 0:
                    break
                C = sum((k['c'] * k['m'] for k in kept), Vector()) / M
                var = sum(k['m'] * (k['c'] - C).length_squared for k in kept)
                keep_r = max(math.sqrt(var / M) * 1.25, 1e-3)
                nxt = [k for k in kept if (k['c'] - C).length <= keep_r]
                if len(nxt) in (0, len(kept)):
                    break
                kept = nxt
            subj = None
            for k in kept:
                if not k['run']:
                    subj = union(subj, k['box'])
            if subj is None:
                for k in kept:
                    subj = union(subj, k['box'])
            if subj is None:
                led.record(check='framing', outcome='SKIPPED', cls='REVIEW',
                           message=f'frames {f0}-{f1}: no subject found above backdrop scale; VIEW the frames')
                continue
            xs, ys, front = [], [], 0
            for cx in (subj[0].x, subj[1].x):
                for cy in (subj[0].y, subj[1].y):
                    for cz in (subj[0].z, subj[1].z):
                        v = world_to_camera_view(scene, cam, Vector((cx, cy, cz)))
                        if v.z > 0:
                            front += 1
                        xs.append(v.x)
                        ys.append(v.y)
            if front < 4:
                led.record(check='framing', outcome='SKIPPED', cls='REVIEW',
                           message=f"frames {f0}-{f1} ('{cam.name}'): the subject is mostly behind the camera; VIEW the frames")
                continue
            w = min(1.0, max(xs)) - max(0.0, min(xs))
            h = min(1.0, max(ys)) - max(0.0, min(ys))
            cover = max(0.0, w) * max(0.0, h)
            names = ', '.join(k['name'] for k in kept[:4]) + (' ...' if len(kept) > 4 else '')
            if cover < 0.06:
                led.record(check='framing', outcome='WARN', cls='CORRECTNESS', metrics={'coverage': round(cover, 4)},
                           message=f"frames {f0}-{f1} ('{cam.name}', frame {mid}): the subject ({names}) covers only "
                                   f'~{cover * 100:.1f}% of the frame (a speck). Frame the subject, not the whole set.')
            else:
                led.record(check='framing', outcome='PASS', cls='REVIEW', metrics={'coverage': round(cover, 4)},
                           message=f"frames {f0}-{f1} ('{cam.name}', frame {mid}): the subject ({names}) covers "
                                   f'~{round(cover * 100)}% of the frame')
        scene.frame_set(scene.frame_start)


# ------------------------------------------------------------------------------------------------- palette ---

def palette(led, scene, modules=(), cfg=None):
    with _guard(led, 'palette'):
        meshes = [o for o in scene.objects if o.type in GEOMETRY_TYPES and render_visible(o)]
        data = {o.data.name for o in meshes if o.data}
        mats = {s.material.name for o in meshes for s in o.material_slots if s.material}
        lights = [o for o in scene.objects if o.type == 'LIGHT' and render_visible(o)]
        probes = [o for o in scene.objects if o.type == 'LIGHT_PROBE']
        imgs = [i for i in bpy.data.images if i.users and i.source == 'FILE']
        own = {'eidoblend', 'eidoblend.common', 'eidoblend.harness'} | {
            f'eidoblend.harness.{m}' for m in ('audits', 'config', 'context', 'ledger', 'output', 'runner', 'settings',
                                              'run_scene', 'keying', 'post', 'showpiece', 'render_common')}
        mods = sorted({('.'.join(m.split('.')[1:3]) if m.startswith('eidoblend.harness.') else m.split('.')[1])
                       for m in modules if m.startswith('eidoblend.') and m not in own})
        led.record(check='palette', outcome='PASS', cls='INFO',
                   metrics={'objects': len(meshes), 'mesh_data': len(data), 'materials': len(mats),
                            'lights': len(lights), 'light_probes': len(probes), 'images': len(imgs)},
                   message=f'{len(meshes)} visible geometry objects ({len(data)} distinct), {len(mats)} materials, '
                           f'{len(imgs)} image textures, {len(lights)} lights, {len(probes)} light probes; toolkit '
                           f"used: {', '.join(mods) if mods else 'none'}")
        from .. import common
        from .showpiece import brief_text, showpiece_nudge
        dur = float(cfg['duration']) if cfg and cfg.get('duration') is not None else 0.0
        nudge = showpiece_nudge(scene, dur, list(modules), brief_text(cfg.get('_scene_json') if cfg else None,
                                                                       common.REPO))
        if nudge:
            msg, hits = nudge
            led.record(check='palette.showpiece', outcome='PASS', cls='INFO', metrics={'fits': hits},
                       message=msg)


# -------------------------------------------------------------------------------------------------- assets ---

def assets_used(led, assets, cfg):
    with _guard(led, 'assets'):
        unread = sorted(set(assets.keys()) - set(assets.reads))
        if unread:
            led.record(check='assets.reads', outcome='WARN', cls='REVIEW', metrics={'unread': len(unread)},
                       message=f"declared but never read by the script: {', '.join(unread)} (declare only what the "
                               'scene uses, or use it)')
        elif assets:
            led.record(check='assets.reads', outcome='PASS', cls='INFO',
                       message=f'all {len(assets)} declared asset(s) were read')
        sdir = os.path.dirname(cfg['_script'])
        declared = {os.path.normcase(os.path.abspath(p)) for p in cfg['_assets'].values() if not is_url(p)}
        orphans = []
        try:
            for name in sorted(os.listdir(sdir)):
                if name.lower().endswith(('.glb', '.gltf', '.vrm')):
                    if os.path.normcase(os.path.join(sdir, name)) not in declared:
                        orphans.append(name)
        except OSError:
            pass
        if orphans:
            led.record(check='assets.orphans', outcome='WARN', cls='REVIEW',
                       message=f"model(s) beside the script that the config never declares: {', '.join(orphans[:8])}. "
                               'Wire them into "assets" and use them, or delete them (tools-guides/assets.md).')


def eidoblend_modules():
    return sorted(m for m in sys.modules if m == 'eidoblend' or m.startswith('eidoblend.'))

"""eidoblend.characters.vrm: load_vrm and the VRM handle (characters.md, "Loading a VRM").

    from eidoblend.characters import load_vrm
    me = load_vrm('claude_robot', location=(0, 0, 0), rotation=90)    # a cast name or a path; heading deg about +Z

The VRM goes in through the VRM Add-on for Blender (bl_ext.blender_org.vrm) with the colour management left alone (AgX
stays), the add-on's temporary import objects deleted, every object in one collection named after the character, the
armature placed (location, heading) and its pose zeroed. The handle (VRMHandle) carries what the other modules need:

    h.arm, h.meshes, h.collection, h.name, h.path
    h.humanoid        {'hips': 'hips', 'leftUpperLeg': ...}   VRM 1.0 humanoid name (camelCase, as three-vrm) -> bone
    h.expr            {'happy': [(mesh, shape key, weight)], 'aa': ..., 'blinkLeft': ...}  the expressions' morph binds
    h.preview(name)   the add-on's preview property owner for an expression (keyed beside the shape keys)
    h.read_pose()     {humanoid name: Quaternion}  the NORMALIZED rotations (three's frame), from the current basis
    h.write_pose(p)   the reverse: basis = R_rest^-1 * N * R_rest (N in Blender's axes), for every name in p
    h.node_frame_three(bone)  a bone's glTF node rest frame in three's axes (the add-on's bone = node * Rx(+90))

NORMALIZED rotations are three-vrm's: rest = identity, world-aligned axes, composed down the humanoid chain, so a clip's
pose and every robot_dof table read the same here as in the WebGPU edition. (Proof: the add-on's own VRMA import, read back
through read_pose, bends the knees about +X; tests/characters/test_robot_walk.py records it.)

Materials: the robot (claude_robot.vrm) is plain glTF PBR (Principled, normal map, ORM), which EEVEE lights as it is.
The MToon cast keeps the add-on's MToon node setup (look='mtoon'); look='pbr' renders them through a Principled BSDF
(claudesona.look.set_look). Their shadows are set up at load (mtoon_shadows): the add-on's MToon output shows the
surface to camera rays only, so its shadow rays are given the material's own opacity as well.
"""

import json
import math
import os
import struct

import bpy
from mathutils import Matrix, Quaternion, Vector

from ._math import D2R, q_from_three, q_to_three

ADDON = 'bl_ext.blender_org.vrm'
REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
VRM_DIR = os.path.join(REPO, 'eidoverse', 'assets', 'vrms')
CAST = ('aletheia', 'aporia', 'claude_suit', 'claude_suit_wardrobe', 'claude', 'claude_robot', 'claude_robot_2k')
_RX90 = Quaternion((1.0, 0.0, 0.0), math.pi / 2)


def snake_to_camel(s):
    head, *rest = s.split('_')
    return head + ''.join(w[:1].upper() + w[1:] for w in rest)


def enable_addon():
    import addon_utils
    if not addon_utils.check(ADDON)[1]:
        bpy.ops.preferences.addon_enable(module=ADDON)


def vrm_path(name_or_path):
    if os.path.exists(name_or_path):
        return os.path.abspath(name_or_path)
    p = os.path.join(VRM_DIR, name_or_path if name_or_path.endswith('.vrm') else name_or_path + '.vrm')
    if not os.path.exists(p):
        raise FileNotFoundError(f'load_vrm: no VRM {name_or_path!r} (the cast: {", ".join(CAST)})')
    return p


def _turn(rotation):
    """a heading (deg about +Z), an Euler (deg, 3 values) or a Quaternion -> Quaternion"""
    if rotation is None:
        return Quaternion()
    if isinstance(rotation, Quaternion):
        return rotation.copy()
    if isinstance(rotation, (int, float)):
        return Quaternion((0.0, 0.0, 1.0), rotation * D2R)
    from mathutils import Euler
    return Euler([a * D2R for a in rotation], 'XYZ').to_quaternion()


class VRMHandle:
    def __init__(self, arm, objects, collection, path, name):
        self.arm, self.objects, self.collection, self.path, self.name = arm, objects, collection, path, name
        self.meshes = [o for o in objects if o.type == 'MESH']
        ext = arm.data.vrm_addon_extension
        hb = ext.vrm1.humanoid.human_bones
        self.humanoid = {}
        for k in hb.bl_rna.properties.keys():
            v = getattr(hb, k, None)
            if hasattr(v, 'node') and getattr(v.node, 'bone_name', ''):
                self.humanoid[snake_to_camel(k)] = v.node.bone_name
        self.bone_of = self.humanoid
        self.rest_q = {b.name: b.matrix_local.to_quaternion() for b in arm.data.bones}
        self.rest_head = {b.name: b.head_local.copy() for b in arm.data.bones}
        self.expr, self._preview = self._binds(ext.vrm1.expressions)

    # -------------------------------------------------------------------------------------------- the expressions
    def _binds(self, ex):
        binds, preview = {}, {}

        def read(e):
            out = []
            for b in e.morph_target_binds:
                o = bpy.data.objects.get(b.node.mesh_object_name) if b.node.mesh_object_name else None
                if o is not None and o.data.shape_keys and b.index in o.data.shape_keys.key_blocks:
                    out.append((o, b.index, float(b.weight)))
            return out
        for k in ex.preset.bl_rna.properties.keys():
            e = getattr(ex.preset, k, None)
            if e is None or not hasattr(e, 'morph_target_binds'):
                continue
            for n in {k, snake_to_camel(k)}:
                binds[n] = read(e)
                preview[n] = e
        for e in ex.custom:
            binds[e.custom_name] = read(e)
            preview[e.custom_name] = e
        return binds, preview

    def preview(self, name):
        return self._preview.get(name)

    # -------------------------------------------------------------------------------------------- the pose
    def pb(self, name):
        b = self.humanoid.get(name, name)
        return self.arm.pose.bones.get(b)

    def zero_pose(self):
        for p in self.arm.pose.bones:
            p.rotation_mode = 'QUATERNION'
            p.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
            p.location = (0.0, 0.0, 0.0)
            p.scale = (1.0, 1.0, 1.0)

    def basis_from_normalized(self, bone, n_bl):
        r = self.rest_q[bone]
        return r.inverted() @ n_bl @ r

    def normalized_from_basis(self, bone, b):
        r = self.rest_q[bone]
        return r @ b @ r.inverted()

    def read_pose(self, names=None):
        out = {}
        for n, b in self.humanoid.items():
            if names is not None and n not in names:
                continue
            out[n] = q_to_three(self.normalized_from_basis(b, self.arm.pose.bones[b].rotation_quaternion))
        return out

    def write_pose(self, pose):
        for n, q in pose.items():
            b = self.humanoid.get(n)
            if b is None:
                continue
            self.arm.pose.bones[b].rotation_quaternion = self.basis_from_normalized(b, q_from_three(q))

    def node_frame(self, bone):
        """the bone's glTF node rest frame (world-aligned, Blender's axes): the add-on's bone frame is the node's * Rx(+90)"""
        return self.rest_q[bone] @ _RX90.inverted()

    def node_frame_three(self, bone):
        return q_to_three(self.node_frame(bone))

    def hips_location_offset(self, loc_basis):
        """the hips' basis location (in its rest frame) as an armature-space offset"""
        return self.rest_q[self.humanoid['hips']] @ Vector(loc_basis)


def load_vrm(path, name=None, location=(0.0, 0.0, 0.0), rotation=0.0, collection=None, scene=None, look='asis'):
    """import a VRM (a cast name or a path) and return its VRMHandle; rotation: heading deg about +Z (0 faces -Y), an
    Euler in deg, or a Quaternion. look: 'asis' (the file's own materials: PBR for the robot, MToon for the rest),
    'mtoon', or 'pbr' (an MToon VRM through a Principled BSDF: claudesona.look.set_look)."""
    if look not in ('asis', 'mtoon', 'pbr'):
        raise NotImplementedError(f"load_vrm look={look!r}: one of 'asis', 'mtoon', 'pbr'")
    enable_addon()
    scene = scene or bpy.context.scene
    path = vrm_path(path)
    name = name or os.path.splitext(os.path.basename(path))[0]
    view0 = (scene.view_settings.view_transform, scene.view_settings.look)
    col = collection or bpy.data.collections.new(name)
    if col.name not in scene.collection.children and col is not scene.collection:
        scene.collection.children.link(col)
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    before = set(bpy.data.objects)
    op = bpy.ops.import_scene.vrm
    props = {p.identifier for p in op.get_rna_type().properties}
    kw = {k: v for k, v in (('set_view_transform_to_standard_on_import', False), ('set_shading_type_to_material_on_import', False),
                            ('extract_textures_into_folder', False), ('make_new_texture_folder', False)) if k in props}
    res = op(filepath=path, **kw)
    if 'FINISHED' not in res:
        raise RuntimeError(f'load_vrm: the add-on refused {path}: {res}')
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    new = [o for o in bpy.data.objects if o not in before]
    for o in list(new):
        if o.name.startswith('BlenderVrmAddonImport'):
            bpy.data.objects.remove(o, do_unlink=True)
    new = [o for o in bpy.data.objects if o not in before]
    arm = next(o for o in new if o.type == 'ARMATURE')
    arm.name = name
    arm.data.name = name
    for o in new:
        for c in list(o.users_collection):
            if c is not col:
                c.objects.unlink(o)
        if col not in o.users_collection:
            col.objects.link(o)
    arm.matrix_world = Matrix.Translation(Vector(location)) @ _turn(rotation).to_matrix().to_4x4()
    h = VRMHandle(arm, new, col, path, name)
    mtoon_shadows(h.meshes)
    if look == 'pbr':
        from .claudesona.look import set_look
        set_look(h, 'pbr')
    h.zero_pose()
    bpy.context.view_layer.update()
    if (scene.view_settings.view_transform, scene.view_settings.look) != view0:
        raise RuntimeError(f'load_vrm: the import changed the colour management {view0}')
    return h


MTOON_OUTPUT = 'VRM Add-on MToon 1.0 Output'     # the add-on's MToon output node group (its name, before the revision)


def mtoon_shadows(meshes):
    """A VRM's MToon materials set up for EEVEE's shadows. The add-on's MToon output mixes the surface with a
    Transparent BSDF by its opacity x Is Camera Ray, so every other ray sees it fully transparent, the shadow pass
    included, and with Transparent Shadows on (Blender's default) the character would cast no shadow. Here the
    output's shadow rays see the material's opacity too (_shadow_rays: once per output group; the outline shells cast
    none), and each material takes the shadow flag its alpha mode needs: an alpha-clipped one (MASK: the skin, the
    clothes and the hair hide their unused parts this way) keeps Transparent Shadows, so it casts the clipped shape;
    a blended one (BLEND: lashes, brows, highlights) casts its alpha; an opaque one (OPAQUE) takes opaque shadows,
    Transparent Shadows off. Other rays (the probe bakes, the probes' reflections) still see the surface transparent,
    as the add-on made it. Returns {'groups': [output groups changed], 'opaque' / 'clipped' / 'blended': [materials]}."""
    out = {'groups': [], 'opaque': [], 'clipped': [], 'blended': []}
    seen = set()
    for ob in meshes:
        for slot in ob.material_slots:
            m = slot.material
            if m is None or m.name in seen or m.node_tree is None:
                continue
            seen.add(m.name)
            mt = getattr(getattr(m, 'vrm_addon_extension', None), 'mtoon1', None)
            if mt is None or not mt.enabled:
                continue
            for n in m.node_tree.nodes:
                g = n.node_tree if n.bl_idname == 'ShaderNodeGroup' else None
                if g is not None and g.name.startswith(MTOON_OUTPUT) and _shadow_rays(g):
                    out['groups'].append(g.name)
            m.use_transparent_shadow = mt.alpha_mode != 'OPAQUE'
            out[{'OPAQUE': 'opaque', 'MASK': 'clipped'}.get(mt.alpha_mode, 'blended')].append(m)
    return out


def _shadow_rays(g):
    """In the add-on's MToon output group: every use of Light Path's Is Camera Ray becomes
    max(Is Camera Ray, Is Shadow Ray x (1 - Is Outline)), so the shadow pass sees the opacity the camera sees and the
    outline shells (Is Outline) stay out of it. Once per group (g['eido_shadow_rays']); True when it changed g."""
    if g.get('eido_shadow_rays'):
        return False
    uses = [lk for lk in g.links if lk.from_node.bl_idname == 'ShaderNodeLightPath'
            and lk.from_socket.name == 'Is Camera Ray']
    gi = next((n for n in g.nodes if n.bl_idname == 'NodeGroupInput' and n.outputs.get('Is Outline') is not None), None)
    for lk in uses:
        lp, dst = lk.from_node, lk.to_socket
        shadow = lp.outputs['Is Shadow Ray']
        if gi is not None:
            keep = g.nodes.new('ShaderNodeMath')
            keep.operation = 'SUBTRACT'
            keep.label = 'not an outline'
            keep.inputs[0].default_value = 1.0
            keep.location = (lp.location.x + 200, lp.location.y - 220)
            g.links.new(gi.outputs['Is Outline'], keep.inputs[1])
            mul = g.nodes.new('ShaderNodeMath')
            mul.operation = 'MULTIPLY'
            mul.label = 'shadow ray, not an outline'
            mul.location = (lp.location.x + 380, lp.location.y - 160)
            g.links.new(shadow, mul.inputs[0])
            g.links.new(keep.outputs[0], mul.inputs[1])
            shadow = mul.outputs[0]
        seen = g.nodes.new('ShaderNodeMath')
        seen.operation = 'MAXIMUM'
        seen.label = 'camera or shadow ray'
        seen.location = (lp.location.x + 560, lp.location.y)
        g.links.remove(lk)
        g.links.new(lp.outputs['Is Camera Ray'], seen.inputs[0])
        g.links.new(shadow, seen.inputs[1])
        g.links.new(seen.outputs[0], dst)
    g['eido_shadow_rays'] = True
    return bool(uses)


def joints_record(h):
    """the exporter's joints file beside the VRM (<name>.joints.json), or None"""
    base = os.path.splitext(h.path)[0]
    for p in (base + '.joints.json', base.replace('_2k', '') + '.joints.json'):
        if os.path.exists(p):
            with open(p, encoding='utf-8') as f:
                return json.load(f)
    return None


def glb_json(path):
    """the JSON chunk of a .vrm / .vrma (GLB)"""
    with open(path, 'rb') as f:
        f.read(12)
        n, _t = struct.unpack('<II', f.read(8))
        return json.loads(f.read(n))

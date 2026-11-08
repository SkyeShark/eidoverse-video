"""eidoblend.xr._bl: small Blender helpers the xr modules share (node building, colours, keys, Cycles on the GPU)."""
from __future__ import annotations

import math

import bpy


def srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_rgb(h: str, scale: float = 1.0, alpha=None):
    """'#rrggbb' -> linear RGB(A), as three.js's color('#rrggbb') reads it (sRGB hex, linear working space)."""
    h = h.lstrip('#')
    rgb = tuple(srgb_to_linear(int(h[i:i + 2], 16) / 255.0) * scale for i in (0, 2, 4))
    return rgb + ((alpha,) if alpha is not None else ())


class Tree:
    """A node tree under construction: n = T.node('ShaderNodeMath', operation='ADD', inputs={0: 1.0}); T.link(a, b)."""

    def __init__(self, tree, clear=True):
        self.tree = tree
        if clear:
            tree.nodes.clear()
        self.x = 0

    def node(self, kind, label=None, inputs=None, **props):
        n = self.tree.nodes.new(kind)
        n.location = (self.x, 0)
        self.x += 180
        if label:
            n.label = n.name = label
        for k, v in props.items():
            setattr(n, k, v)
        for k, v in (inputs or {}).items():
            if isinstance(v, bpy.types.NodeSocket):
                self.tree.links.new(v, n.inputs[k])
            else:
                n.inputs[k].default_value = v
        return n

    def link(self, a, b):
        return self.tree.links.new(a, b)

    def math(self, op, a, b=None, c=None, clamp=False):
        n = self.node('ShaderNodeMath', operation=op, use_clamp=clamp)
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, bpy.types.NodeSocket):
                self.link(v, n.inputs[i])
            else:
                n.inputs[i].default_value = v
        return n.outputs[0]

    def vmath(self, op, a, b=None, scale=None):
        n = self.node('ShaderNodeVectorMath', operation=op)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, bpy.types.NodeSocket):
                self.link(v, n.inputs[i])
            else:
                n.inputs[i].default_value = v
        if scale is not None:
            if isinstance(scale, bpy.types.NodeSocket):
                self.link(scale, n.inputs['Scale'])
            else:
                n.inputs['Scale'].default_value = scale
        return n.outputs['Value' if op in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE') else 'Vector']

    def mix_rgb(self, fac, a, b, blend='MIX', clamp=False):
        n = self.node('ShaderNodeMix', data_type='RGBA', blend_type=blend, clamp_result=clamp)
        for sock, v in ((n.inputs[0], fac), (n.inputs[6], a), (n.inputs[7], b)):
            if isinstance(v, bpy.types.NodeSocket):
                self.link(v, sock)
            else:
                sock.default_value = v
        return n.outputs[2]

    def rgb(self, c):
        n = self.node('ShaderNodeRGB')
        n.outputs[0].default_value = tuple(c[:3]) + (1.0,)
        return n.outputs[0]

    def value(self, v, label=None):
        n = self.node('ShaderNodeValue', label=label)
        n.outputs[0].default_value = float(v)
        return n.outputs[0]


def new_material(name, replace=True):
    m = bpy.data.materials.get(name)
    if m is not None and replace:
        bpy.data.materials.remove(m)
        m = None
    if m is None:
        m = bpy.data.materials.new(name)
    if not m.use_nodes:
        m.use_nodes = True
    return m


def unlit_output(T, colour_socket):
    """The unlit hookup Blender's glTF exporter reads as KHR_materials_unlit and EEVEE draws as the colour itself: a
    colour linked straight into the Material Output's Surface (Blender converts it to an emission of strength 1)."""
    out = T.node('ShaderNodeOutputMaterial')
    out.is_active_output = True
    T.link(colour_socket, out.inputs['Surface'])
    return out


def set_interpolation(idb, kind='LINEAR', data_paths=None):
    """Keys of an ID's action set to `kind` (Python's keyframe_insert ignores the user preference)."""
    ad = getattr(idb, 'animation_data', None)
    if ad is None or ad.action is None:
        return 0
    from bpy_extras import anim_utils
    try:
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    except Exception:
        cb = None
    curves = cb.fcurves if cb is not None else getattr(ad.action, 'fcurves', [])
    n = 0
    for fc in curves:
        if data_paths and fc.data_path not in data_paths:
            continue
        for kp in fc.keyframe_points:
            kp.interpolation = kind
            n += 1
    return n


def fcurves(idb):
    ad = getattr(idb, 'animation_data', None)
    if ad is None or ad.action is None:
        return []
    from bpy_extras import anim_utils
    try:
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    except Exception:
        cb = None
    return list(cb.fcurves) if cb is not None else list(getattr(ad.action, 'fcurves', []))


def cycles_gpu(scene, log=print):
    """Cycles on the GPU (OptiX, then CUDA, HIP, Metal, oneAPI), else the CPU. Returns the device kind used."""
    scene.render.engine = 'CYCLES'
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        for kind in ('OPTIX', 'CUDA', 'HIP', 'METAL', 'ONEAPI'):
            try:
                prefs.compute_device_type = kind
            except TypeError:
                continue
            prefs.get_devices()
            if any(d.type == kind for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type != 'CPU'
                scene.cycles.device = 'GPU'
                return kind
    except Exception as e:                                  # no GPU backend: the CPU, slower, same answer
        if log:
            log(f'[xr] Cycles GPU unavailable ({e}); using the CPU')
    scene.cycles.device = 'CPU'
    return 'CPU'


def look_at_rotation(eye, target):
    """A camera rotation (Euler) at `eye` looking at `target` (Blender's camera looks down its -Z, up +Y)."""
    from mathutils import Vector
    d = Vector(target) - Vector(eye)
    return d.to_track_quat('-Z', 'Y').to_euler()


def vertical_fov_lens(cam_data, fov_deg, aspect):
    """Set a camera's lens for a VERTICAL field of view (three.js's PerspectiveCamera.fov) at a frame aspect."""
    cam_data.sensor_fit = 'VERTICAL'
    cam_data.sensor_height = 24.0
    cam_data.lens = 12.0 / math.tan(math.radians(fov_deg) / 2)
    return cam_data

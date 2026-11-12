"""The free-surface water's look in EEVEE: fluid_water.js's surface shading, as a film material or as the engine's own.

Two shadings read the same baked per-vertex inputs (surface.py: thick = water thickness behind the point, ring =
solid proximity, speed = flow speed) and the same look values:

shading='lit' (the default, the film material). The scene's lights and world light the water: IOR 1.333,
ray-traced refraction and reflections, real fresnel. The engine's terms keep their formulas:

    water    body='tint' (the default): all of it refracts (transmission 1, IOR 1.333) and the engine's depth tint
             mix(shallow, deep, 1 - exp(-thick * absorption)), weighted by opacity = clamp(surface_opacity + glow *
             emissive_strength * 0.3), colours the light that passes: thick water deep, thin water near clear.
             body='stochastic' is the shallow-water port's split instead: an opaque depth-tinted body with
             probability (1 - exp(-thick * absorption)) * opacity, else clear water tinted as it thickens (picked
             per sample, so a middling probability needs more samples to settle, as dithered transparency does)
    foam     band = max(ring^2, shore^2 * foam_shore), shore = 1 - smoothstep(0, foam_width, thick), times
             foam_strength (the engine's contact and shore foam), plus the Blender edition's churn foam,
             smoothstep(0.25, 1, shear / churn_speed) * foam_churn: rough white water where the flow shears (fast
             water meeting slow: a plunge, a landing), which is where water entrains air
    glow     emission emissive_color * strength over the body by (1 - exp(-thick * falloff)) * min(strength, 1)
    sparkle  the engine's hash glints on uvw * sparkle_scale, animated by time * sparkle_speed, gated by fresnel

    EEVEE renders a pixel's refraction or its opaque closures, not a blend of the two: a fractional Transmission
    Weight, or a Mix Shader of a refracting and an opaque BSDF, shows a fixed per-pixel pattern and loses the
    refraction at any sample count (tests/water3d/probe_partial_transmission.py). So water and foam (and the body)
    are picked, as EEVEE's own dithered transparency picks: one Principled renders the pick with transmission
    exactly 0 or 1, and the samples average the picks. foam_pick='lace' (the default) fixes the pick per surface
    point with a 3D noise of the position (foam_scale per metre), so foam forms coherent lace whose edges alone
    dither; 'dither' picks per sample with a white-noise hash, which needs more samples under churn foam.
    body='stochastic' always picks per sample. With body='tint' only foam is picked, so open water renders clean.

    thickness  the material output's Thickness is the baked water path to where it leaves the water (surface.py's
             'exit'), cut to BED_SHARE of it where the path ends on a solid ('bed'): EEVEE refracts through a slab
             (refraction_thickness='slab', or 'sphere') of that thickness, so a settled pool shows its bed at the
             depth the water has, frame after frame.

shading='engine' (the WebGPU look, unlit, for matching the engine's frames). fluid_water.js's colorNode, term for
term, on the mesh: fresnel = (1 - max(n.v, 0))^3 * 0.85 + 0.04, depthTint = mix(shallow, deep, 1 - exp(-thick *
absorption)), the key-light specular pow(max(reflect(-key_light_dir, n).v, 0), 90) * 0.9, surface = mix(depthTint,
sky_color, fresnel) + spec, the emissive mix, the contact/shore foam, the sparkle, alpha = the engine's op. Alpha
blended with only the nearest surface drawn (the engine's first hit), back faces culled. thickness_mode='view'
gives the engine's view-ray thickness. The engine drew to an sRGB canvas with no tone mapping; the palette is
display-matched so the scene's view (AgX) shows the engine's colours (engine_display='standard'; None turns it off).

Every look value is a named node ('w3d.<name>'), so WaterSim.uniforms writes through and key_look() keys them.
"""

from __future__ import annotations

import numpy as np

from .._util import color

LOOK_KEYS = ('deep_color', 'shallow_color', 'sky_color', 'absorption', 'surface_opacity', 'key_light_dir',
             'emissive_color', 'emissive_strength', 'emissive_falloff', 'foam_color', 'foam_strength', 'foam_width',
             'foam_shore', 'foam_churn', 'churn_speed', 'foam_scale', 'sparkle_strength', 'sparkle_scale',
             'sparkle_speed', 'roughness')
COLOR_KEYS = ('deep_color', 'shallow_color', 'sky_color', 'emissive_color', 'foam_color')
VECTOR_KEYS = ('key_light_dir',)


def _srgb_encode(c):
    c = np.clip(np.asarray(c, dtype=np.float64), 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def display_matched(scene, rgb_linear):
    """The scene-linear colour the scene's view shows as the engine's sRGB canvas showed `rgb_linear` (no tone
    mapping there): SceneView's inverse of the view (fx/_look.py)."""
    from .._look import SceneView
    view = SceneView(scene)
    x = view.from_display(_srgb_encode(rgb_linear).reshape(1, 3))
    return tuple(float(v) for v in x.reshape(3))


class _Palette:
    """Colour values as the material sees them: linear, display-matched in the engine shading."""

    def __init__(self, scene, shading, engine_display):
        self.match = scene if (shading == 'engine' and engine_display == 'standard') else None
        self._cache = {}

    def __call__(self, value):
        lin = color(value)
        if self.match is None:
            return lin
        key = tuple(round(v, 6) for v in lin)
        if key not in self._cache:
            self._cache[key] = display_matched(self.match, lin)
        return self._cache[key]


def key_light_blender(v3):
    """The engine's keyLightDir (three axes, normalised) in Blender axes."""
    v = np.asarray(v3, dtype=np.float64)
    v = v / max(np.linalg.norm(v), 1e-9)
    return (float(v[0]), float(-v[2]), float(v[1]))


def build_water_material(name, o, world3, center3, fps, frame_start, time_offset=0.0, scene=None):
    import bpy
    from .._nodes import Builder
    shading = o.get('shading', 'lit')
    if shading not in ('lit', 'engine'):
        raise ValueError(f"water3d: shading must be 'lit' or 'engine', not {shading!r}")
    pal = _Palette(scene or bpy.context.scene, shading, o.get('engine_display', 'standard'))
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat['w3d_shading'] = shading
    mat['w3d_palette_matched'] = pal.match is not None
    # a camera under the water (inside_domain) sees the back faces
    mat.use_backface_culling = not o.get('inside_domain', False)
    if shading == 'lit':
        mat.surface_render_method = 'DITHERED'
        mat.use_raytrace_refraction = True
    else:
        mat.surface_render_method = 'BLENDED'
        mat.use_transparency_overlap = False          # only the nearest surface: the engine's first hit
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (1700, 0)
    b = Builder(nt, x0=-2100, y0=800)

    def val(key):
        n = b.node('ShaderNodeValue')
        n.name = n.label = 'w3d.' + key
        n.hide = False
        n.outputs[0].default_value = float(o[key])
        return b.s(n.outputs[0])

    def rgb(key):
        n = b.node('ShaderNodeRGB')
        n.name = n.label = 'w3d.' + key
        n.hide = False
        n.outputs[0].default_value = (*pal(o[key]), 1.0)
        return b.vec(n.outputs[0])

    def vec3(key, v):
        n = b.node('ShaderNodeCombineXYZ')
        n.name = n.label = 'w3d.' + key
        n.hide = False
        for i in range(3):
            n.inputs[i].default_value = v[i]
        return b.vec(n.outputs[0])

    def attr(nm):
        n = b.node('ShaderNodeAttribute', attribute_name=nm, attribute_type='GEOMETRY')
        return b.s(n.outputs['Fac'])

    thick, ring, shear = attr('thick'), attr('ring'), attr('shear')
    absorption, opacity = val('absorption'), val('surface_opacity')
    shallow, deep, sky = rgb('shallow_color'), rgb('deep_color'), rgb('sky_color')
    e_col, e_str, e_fall = rgb('emissive_color'), val('emissive_strength'), val('emissive_falloff')
    f_col, f_str, f_w, f_sh = rgb('foam_color'), val('foam_strength'), val('foam_width'), val('foam_shore')
    f_churn, c_speed = val('foam_churn'), val('churn_speed')
    s_str, s_scale, s_speed = val('sparkle_strength'), val('sparkle_scale'), val('sparkle_speed')
    rough = val('roughness')
    key = vec3('key_light_dir', key_light_blender(o['key_light_dir']))

    absorb = 1.0 - b.exp(-thick * absorption)                       # the engine's depth tint factor
    tint = b.rgb_mix(shallow, deep, absorb)
    glow = 1.0 - b.exp(-thick * e_fall)
    op = b.clamp(opacity + glow * e_str * 0.30)                      # an emissive pool grows more opaque
    shore = 1.0 - b.smoothstep(0.0, f_w, thick)
    band = b.max(ring * ring, shore * shore * f_sh)
    churn = b.smoothstep(0.25, 1.0, shear / b.max(c_speed, 1e-3)) * f_churn
    foam_amt = b.clamp(band * f_str + churn)

    geo = b.node('ShaderNodeNewGeometry')
    N = b.vec(geo.outputs['Normal'])
    V = b.vec(geo.outputs['Incoming'])
    ndv = b.max(b.vmath('DOT_PRODUCT', N, V), 0.0)
    fres = (1.0 - ndv) * (1.0 - ndv) * (1.0 - ndv) * 0.85 + 0.04     # the engine's fresnel

    # sparkle: h = fract(sin(dot(uvw * scale, (127.1, 74.7, 311.7))) * 43758.5453), tw = fract(h + time * speed),
    # glint = pow(max(1 - |2 tw - 1|, 0), 40) * (fresnel * 0.7 + 0.3) * strength, uvw in the engine's axes
    pos = b.vec(geo.outputs['Position'])
    px, py, pz = pos.xyz()
    W = world3
    u = (px - center3[0]) / W[0] + 0.5                             # three x
    v = (pz - center3[1]) / W[1] + 0.5                             # three y = Blender z
    w = (-py - center3[2]) / W[2] + 0.5                            # three z = -Blender y
    h = b.fract(b.sin(u * s_scale * 127.1 + w * s_scale * 311.7 + v * s_scale * 74.7) * 43758.5453)
    tnode = b.node('ShaderNodeValue')
    tnode.name = tnode.label = 'w3d.time'
    tnode.hide = False
    drv = tnode.outputs[0].driver_add('default_value').driver
    drv.type = 'SCRIPTED'
    drv.expression = f'(frame - {int(frame_start)}) / {float(fps):.6g} + {float(time_offset):.6g}'
    tw = b.fract(h + b.s(tnode.outputs[0]) * s_speed)
    glint = b.pow(b.max(1.0 - b.abs(tw * 2.0 - 1.0), 0.0), 40.0) * (fres * 0.7 + 0.3) * s_str

    if shading == 'engine':
        # spec = pow(max(dot(reflect(-L, n), viewD), 0), 90): the engine's key light, fixed in the domain's frame
        R = b.vmath('REFLECT', b.vscale(key, -1.0), N)
        spec = b.pow(b.max(b.vmath('DOT_PRODUCT', R, V), 0.0), 90.0)
        surface = b.rgb_mix(tint, sky, fres) + b.vscale(b.combine(1.0, 1.0, 1.0), spec * 0.9)
        lit = b.vscale(e_col, e_str)
        col = b.rgb_mix(surface, lit, glow * b.min(e_str, 1.0))
        col = col + b.vscale(f_col, band * f_str)                   # the engine adds its foam band
        col = col + b.vscale(b.combine(1.0, 1.0, 1.0), glint)
        em = b.node('ShaderNodeEmission')
        b.link(col, em.inputs['Color'])
        em.inputs['Strength'].default_value = 1.0
        tr = b.node('ShaderNodeBsdfTransparent')
        mx = b.node('ShaderNodeMixShader')
        b.link(op, mx.inputs['Fac'])
        nt.links.new(tr.outputs[0], mx.inputs[1])
        nt.links.new(em.outputs[0], mx.inputs[2])
        nt.links.new(mx.outputs[0], out.inputs['Surface'])
        return mat

    if o.get('body', 'tint') == 'stochastic' or o.get('foam_pick', 'lace') == 'dither':
        # a white-noise hash of the position: a new pick at every sample under EEVEE's jitter
        pick = b.node('ShaderNodeTexWhiteNoise', noise_dimensions='3D')
        nt.links.new(geo.outputs['Position'], pick.inputs['Vector'])
        pick_v = b.s(pick.outputs['Value'])
    else:
        # 'lace': the pick is fixed per surface point (a 3D noise of the position, its central spread stretched to
        # 0..1), so foam forms coherent lace whose share follows the foam amount and only its edges dither
        lace = b.node('ShaderNodeTexNoise', noise_dimensions='3D')
        nt.links.new(geo.outputs['Position'], lace.inputs['Vector'])
        b.link(val('foam_scale'), lace.inputs['Scale'])
        lace.inputs['Detail'].default_value = 3.0
        lace.inputs['Roughness'].default_value = 0.55
        pick_v = b.clamp((b.s(lace.outputs['Fac']) - 0.32) / 0.36)
    if o.get('body', 'tint') == 'stochastic':
        # the shallow-water port's split: an opaque depth-tinted body with probability absorb * opacity, picked per
        # shading sample (a middling probability needs more samples to settle)
        body = absorb * op
        clear_tint = b.rgb_mix((1, 1, 1, 1), tint, b.min(absorb * 1.6, 1.0))
    else:
        # 'tint': all the water refracts; the engine's depth tint, weighted by surface_opacity, colours the light
        # that passes (thick water deep, thin water near clear). Only foam is picked per sample, so the water itself
        # renders clean at film sample counts
        body = 0.0
        clear_tint = b.rgb_mix((1, 1, 1, 1), tint, op)
    share_foam = foam_amt / b.max(foam_amt + body * (1.0 - foam_amt), 1e-4)
    clear = b.math('LESS_THAN', pick_v, (1.0 - body) * (1.0 - foam_amt))
    opaque_col = b.rgb_mix(tint, f_col, share_foam)
    P = b.node('ShaderNodeBsdfPrincipled')
    P.hide = False
    P.inputs['IOR'].default_value = 1.333
    b.link(b.rgb_mix(opaque_col, clear_tint, clear), P.inputs['Base Color'])
    b.link(clear, P.inputs['Transmission Weight'])
    b.link(rough + share_foam * (1.0 - clear) * (0.65 - rough), P.inputs['Roughness'])
    shader = P.outputs[0]
    # glow: mix(surface, emissive * strength, glow * min(strength, 1)) under the foam (emission is no G-buffer
    # closure, so the mix costs no extra closure)
    em = b.node('ShaderNodeEmission')
    b.link(b.vscale(e_col, e_str), em.inputs['Color'])
    em.inputs['Strength'].default_value = 1.0
    mg = b.node('ShaderNodeMixShader')
    b.link(glow * b.min(e_str, 1.0) * (1.0 - foam_amt), mg.inputs['Fac'])
    nt.links.new(shader, mg.inputs[1])
    nt.links.new(em.outputs[0], mg.inputs[2])
    shader = mg.outputs[0]
    sp = b.node('ShaderNodeEmission')
    b.link(glint, sp.inputs['Strength'])
    sp.inputs['Color'].default_value = (1, 1, 1, 1)
    add = b.node('ShaderNodeAddShader')
    nt.links.new(shader, add.inputs[0])
    nt.links.new(sp.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs['Surface'])
    _link_refraction_thickness(mat, b, out, o.get('refraction_thickness', 'slab'), attr)
    # under the water: a volume absorption inside the mesh, so what a camera there sees through the water takes the
    # depth tint by distance, as the engine's march from inside the box tinted it (linked by set_inside_domain)
    va = b.node('ShaderNodeVolumeAbsorption')
    va.name = va.label = 'w3d.under_water'
    b.link(shallow, va.inputs['Color'])
    b.link(absorption, va.inputs['Density'])
    mat.volume_intersection_method = 'ACCURATE'
    set_inside_domain(mat, bool(o.get('inside_domain', False)))
    return mat


def set_inside_domain(mat, on):
    """The camera inside the water (the engine's insideDomain): draw the back faces and absorb along the view inside
    the mesh (a Volume Absorption of the shallow colour at the absorption density); off: front faces only, no
    volume."""
    nt = mat.node_tree
    out = [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'][0]
    va = nt.nodes.get('w3d.under_water')
    for lk in list(out.inputs['Volume'].links):
        nt.links.remove(lk)
    if on and va is not None:
        nt.links.new(va.outputs[0], out.inputs['Volume'])
    mat.use_backface_culling = not on
    return mat


# where the water path ends on a solid (a basin's floor) or runs deep, the slab is cut to this share of it, so EEVEE's
# trace leaves the slab just above the floor and finds it, as a refracted view of the bed should
BED_SHARE = 0.75


def _link_refraction_thickness(mat, b, out, mode, attr):
    """The material output's Thickness from the baked water path (surface.py's 'exit' and 'bed'): EEVEE models the
    refraction through it as a slab (or a sphere) of that thickness, the water's own. 'none' leaves it unlinked
    (EEVEE then estimates a thickness of its own, which knows nothing of the water behind the surface)."""
    if mode in (None, 'none'):
        return
    if mode not in ('slab', 'sphere'):
        raise ValueError(f"water3d: refraction_thickness must be 'slab', 'sphere' or 'none', not {mode!r}")
    mat.thickness_mode = 'SLAB' if mode == 'slab' else 'SPHERE'
    ex, bed = attr('exit'), attr('bed')
    b.link(ex * (1.0 - bed * (1.0 - BED_SHARE)), out.inputs['Thickness'])


def set_look(mat, key, value, scene=None):
    """Write one look uniform through to the material's named node (colours display-matched as built)."""
    n = mat.node_tree.nodes.get('w3d.' + key)
    if n is None:
        return False
    if key in COLOR_KEYS:
        if mat.get('w3d_palette_matched'):
            import bpy
            rgb = display_matched(scene or bpy.context.scene, color(value))
        else:
            rgb = color(value)
        n.outputs[0].default_value = (*rgb, 1.0)
    elif key in VECTOR_KEYS:
        v = key_light_blender(value)
        for i in range(3):
            n.inputs[i].default_value = v[i]
    else:
        n.outputs[0].default_value = float(value)
    return True


def key_look(mat, key, frame, value=None, scene=None):
    """Keyframe one look value at `frame` (writing `value` first when given): a look change that plays."""
    n = mat.node_tree.nodes.get('w3d.' + key)
    if n is None:
        raise KeyError(key)
    if value is not None:
        set_look(mat, key, value, scene)
    sockets = list(n.inputs)[:3] if key in VECTOR_KEYS else [n.outputs[0]]
    for s in sockets:
        s.keyframe_insert('default_value', frame=frame)
        fc = _fcurve_for(mat, s)
        if fc is not None:
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
    return n


def _fcurve_for(mat, socket):
    """The F-curve a socket's keyframe_insert just made (Python inserts ignore the interpolation preference)."""
    ad = mat.node_tree.animation_data
    if ad is None or ad.action is None:
        return None
    path = socket.path_from_id('default_value')
    try:
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
        curves = cb.fcurves if cb is not None else []
    except Exception:
        curves = getattr(ad.action, 'fcurves', [])
    for fc in curves:
        if fc.data_path == path:
            return fc
    return None

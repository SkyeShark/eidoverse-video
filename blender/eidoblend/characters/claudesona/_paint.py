"""eidoblend.characters.claudesona._paint: the wardrobe's paints as shader nodes, switched by a keyed property.

claudesona_wardrobe.js repaints MToon materials at wear(): a hex sets the colour (an untextured garment) or replaces
the print (a textured one; the normal map keeps the weave), a pattern becomes the colour node, the shade follows at
0.55 and the outline at 0.22. Here every paint a material is ever given becomes a SLOT of that material: slot 0 is the
material as imported, slot k a paint. The MToon output's four colour inputs (Lit Color, Lit Color Texture Color, Shade
Color, Shade Color Texture) and the outline material's Outline Color each read a chain that picks the slot whose
number equals a custom property on the armature, 'cs_paint.<material>', read by a driver. Keying that number (a float
holding whole slot numbers, CONSTANT) is keying the paint: a saved .blend changes outfits on its frames with no
handler. Every such property is made with new_prop() (which tags the armature, so the evaluated copy has it before a
key or a driver needs it) and every driver goes through drive(), which clears a stale driver and marks the new one
valid (Blender never re-evaluates a driver once it is flagged invalid).

Patterns are procedural in the model's rest space, as positionGeometry is in TSL: the 'rest_position' attribute
(Object.add_rest_position_attribute, the pose-free position before shape keys and the armature) read in three's axes
(x, y, z) = Blender (x, z, -y). The integer cell hash the WebGPU edition uses for flecks and slubs becomes Blender's
White Noise of the same integer cell (a different but equally uniform hash: the pattern statistics match, not the
exact fleck positions). perPetal colours by each vertex's petal, as the WebGPU edition does it: each vertex's petal
id (its strongest petal bone, the JS's petalId) picks its colour once, into a per-vertex colour attribute per perPetal
paint ('cs_petal_rgb.<hash>', the JS's petalColor), which the surface interpolates. (Looking the palette up in the
shader from an interpolated id does not work: a constant id of 3 arrives as 2.9999998 on part of a triangle, and the
floor picks the neighbouring colour there, a speckle all over the petals.)
"""

import json
import math

import bpy

from ...fx._nodes import Builder, Vec, new_group

HEAD_Y = 1.524                     # the petal-ring centre (glTF y), bind pose: the sweep's pivot
PETAL_ATTR = 'cs_petal_id'


class CSBuilder(Builder):
    """fx's node Builder, naming every node it makes 'cs.*' so a rebuild removes exactly its own nodes"""

    def node(self, kind, **props):
        n = super().node(kind, **props)
        if not n.name.startswith('cs.'):
            n.name = f'cs.{kind[-12:]}.{self.count}'
        return n


def clear_cs(nt):
    """remove this package's nodes ('cs.*') from a node tree, and the drivers on them (a driver left on a removed
    node is flagged invalid, and a rebuilt node of the same name would inherit it)"""
    ad = nt.animation_data
    if ad is not None:
        for fc in [fc for fc in ad.drivers if fc.data_path.startswith('nodes["cs.')]:
            ad.drivers.remove(fc)
    for n in [n for n in nt.nodes if n.name.startswith('cs.')]:
        nt.nodes.remove(n)


def new_prop(arm, prop, value=0.0):
    """a float custom property on the armature, made visible to the depsgraph at once. A property added from Python is
    not copied to the evaluated armature until something tags the armature, and keying it on an action the armature
    already has does not: its keys then never apply, and every driver reading it fails and is flagged invalid for
    good (measured: a keyed switch stuck on its last Python value, the outfit's paints all at slot 0)."""
    if prop not in arm:
        arm[prop] = float(value)
        arm.update_tag()
    return prop


def drive(owner, path, arm, prop, var='v', expression=None):
    """owner.path driven by the armature's custom property `prop` (a SUM driver, or a SCRIPTED `expression` of `var`):
    any older driver on that path is removed first and the new one marked valid. Blender stops evaluating a driver
    once it has been flagged invalid (as one is when it is evaluated before its target is set, when its target
    property has not reached the evaluated armature yet, or when its node is removed and rebuilt), so a switch driven
    that way silently stays at its default."""
    arm.update_tag()
    try:
        owner.driver_remove(path)
    except (TypeError, RuntimeError):
        pass
    fc = owner.driver_add(path)
    d = fc.driver
    d.type = 'SCRIPTED' if expression else 'SUM'
    for v in list(d.variables):
        d.variables.remove(v)
    v = d.variables.new()
    v.name, v.type = var, 'SINGLE_PROP'
    v.targets[0].id_type = 'OBJECT'
    v.targets[0].id = arm
    v.targets[0].data_path = f'["{prop}"]'
    if expression:
        d.expression = expression
    d.is_valid = True
    return fc


def lin(h):
    """'#rrggbb' -> linear rgb (three's Color(hex): sRGB to the linear working space)"""
    h = h.lstrip('#')
    out = []
    for i in (0, 2, 4):
        s = int(h[i:i + 2], 16) / 255.0
        out.append(s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4)
    return tuple(out)


def shade_of(spec):
    """claudesona_wardrobe.js shadeOf: the colour the shade and outline follow"""
    if isinstance(spec, str):
        return lin(spec)
    if spec.get('colors'):
        cs = spec['colors']
        return lin(cs[len(cs) // 2])
    a, b = lin(spec['a']), lin(spec.get('b', spec['a']))
    return tuple(x + (y - x) * 0.5 for x, y in zip(a, b))


def _rest_P(b):
    """the rest position in three's axes: (x, y, z) = Blender (x, z, -y), as three scalars"""
    at = b.node('ShaderNodeAttribute', attribute_type='GEOMETRY', attribute_name='rest_position')
    x, y, z = b.vec(at.outputs['Vector']).xyz()
    return x, z, -y


def _hash3(b, x, y, z):
    """a uniform 0..1 value per integer cell (White Noise of the cell vector)"""
    wn = b.node('ShaderNodeTexWhiteNoise', noise_dimensions='3D')
    b.link(b.combine(x, y, z), wn.inputs['Vector'])
    return b.s(wn.outputs['Value'])


def _const(b, rgb):
    n = b.node('ShaderNodeRGB')
    n.outputs[0].default_value = tuple(rgb) + (1.0,)
    return Vec(b, n.outputs[0])


def _palette(b, index, colors):
    """colors[int(index)] for a continuous index (the rainbow's bands: TSL's int() truncation), a chain of compares"""
    v = _const(b, colors[0])
    for i, c in enumerate(colors[1:], 1):
        eq = b.math('COMPARE', b.floor(index), float(i), 0.5)
        v = b.rgb_mix(v, _const(b, c), eq)
    return v


def _spec_hash(spec):
    import hashlib
    return hashlib.md5(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:8]


def petal_rgb_attr(spec):
    """the per-vertex colour attribute a perPetal paint reads (written by petal_rgb_colors on the flower mesh)"""
    return 'cs_petal_rgb.' + _spec_hash(spec)


def petal_rgb_colors(spec, ids):
    """claudesona_wardrobe.js writePetalColors: (n, 4) linear RGBA per vertex from its petal id (0..11 = petal N-1,
    12 = not a petal) and the paint's colours + centre"""
    import numpy as np
    pal = np.array([lin(c) for c in spec['colors']] + [lin(spec.get('center') or '#e0e0e0')], dtype=np.float32)
    k = np.minimum(np.asarray(ids).astype(np.int64), len(pal) - 1)
    out = np.ones((len(k), 4), dtype=np.float32)
    out[:, :3] = pal[k]
    return out


def pattern_group(spec):
    """the node group computing a pattern's colour (cached per spec)"""
    name = 'cs.pat.' + spec.get('pattern', 'x') + '.' + _spec_hash(spec)
    if name in bpy.data.node_groups:
        return bpy.data.node_groups[name]
    tree, gi, go = new_group(name, 'ShaderNodeTree', outputs=(('Color', 'NodeSocketColor'),))
    b = Builder(tree)
    p = spec['pattern']
    if p == 'perPetal':
        at = b.node('ShaderNodeAttribute', attribute_type='GEOMETRY', attribute_name=petal_rgb_attr(spec))
        out = Vec(b, at.outputs['Color'])
    else:
        X, Y, Z = _rest_P(b)
        if p == 'rainbow':
            top, bot, n = spec.get('top', 1.93), spec.get('bottom', 1.12), len(spec['colors'])
            k = b.clamp((top - Y) / (top - bot) * n, 0.0, n - 0.001)
            out = _palette(b, k, [lin(c) for c in spec['colors']])
        elif p == 'sweep':
            ang = b.math('ARCTAN2', X, Y - HEAD_Y, fold=False) / (math.pi * 2) + 0.5
            out = b.rgb_mix(_const(b, lin(spec['a'])), _const(b, lin(spec['b'])), b.smoothstep(0.0, 1.0, b.abs(ang * 2.0 - 1.0)))
        else:
            A, B = _const(b, lin(spec['a'])), _const(b, lin(spec.get('b', spec['a'])))
            if p == 'stripes':
                s, w = spec.get('scale', 0.08), spec.get('width', 0.5)
                q = (X if spec.get('axis') == 'x' else Y) / s
                out = b.rgb_mix(A, B, b.smoothstep(1 - w - 0.05, 1 - w + 0.05, b.abs(b.fract(q) - 0.5) * 2.0))
            elif p == 'blocks':
                Cc = _const(b, lin(spec.get('c') or spec['a']))
                out = b.rgb_mix(b.rgb_mix(A, B, b.step(0.0, X)), Cc, b.step(1.28, Y))
            elif p == 'herringbone':
                s = spec.get('scale', 0.012)
                d = b.fract(b.floor(X / s) * 0.5) * 4.0 - 1.0
                tw = b.fract((Y + X * d) / (s * 0.5))
                fl = b.step(0.9, _hash3(b, b.floor(X * 420.0) + 10000.0, b.floor(Y * 420.0) + 10000.0,
                                        b.floor(Z * 420.0) + 10000.0))
                base = b.rgb_mix(A, B, b.smoothstep(0.25, 0.75, b.abs(tw - 0.5) * 2.0))
                out = b.rgb_mix(base, _const(b, lin(spec.get('c') or spec['b'])), fl * 0.55)
            elif p == 'gradient':
                out = b.rgb_mix(A, B, b.clamp((Y - 0.85) / 0.55, 0.0, 1.0))
            elif p == 'canvas':
                s = spec.get('scale', 0.0045)
                wx = b.smoothstep(0.08, 0.5, b.abs(b.fract(X / s) - 0.5))
                wy = b.smoothstep(0.08, 0.5, b.abs(b.fract(Y / s) - 0.5))
                slub = _hash3(b, b.floor(X * 150.0) + 10000.0, b.floor(Y * 150.0) + 10000.0, b.floor(Z * 150.0) + 10000.0)
                out = b.rgb_mix(A, B, wx * 0.35 + wy * 0.35 + slub * 0.3)
            else:
                out = A
    b.link(out, go.inputs['Color'])
    return tree


class PaintRig:
    """one material's paint slots and their switch (see the module docstring)"""

    CHANNELS = (('lit', 'Lit Color'), ('lit_tex', 'Lit Color Texture Color'), ('shade', 'Shade Color'),
                ('shade_tex', 'Shade Color Texture'))

    def __init__(self, arm, gltf_name, mats, outline_mats):
        self.arm, self.name = arm, gltf_name
        self.mats, self.outline_mats = list(mats), list(outline_mats)
        self.prop = new_prop(arm, f'cs_paint.{gltf_name}', 0.0)     # a float holding the slot number
        self.slots = [None]                   # specs; 0 = as imported
        self.textured = any(self._out(m) and self._out(m).inputs['Lit Color Texture Color'].is_linked for m in self.mats)
        self.orig = {}
        for m in self.mats:
            o = self._out(m)
            if o is None:
                continue
            rec = {}
            for ch, sock in self.CHANNELS:
                s = o.inputs[sock]
                rec[ch] = s.links[0].from_socket if s.is_linked else tuple(s.default_value)[:3]
            self.orig[m.name] = rec
        self.orig_outline = {}
        for m in self.outline_mats:
            o = self._out(m)
            if o is not None:
                s = o.inputs['Outline Color']
                self.orig_outline[m.name] = s.links[0].from_socket if s.is_linked else tuple(s.default_value)[:3]

    @staticmethod
    def _out(m):
        return m.node_tree.nodes.get('Mtoon1Material.Mtoon1Output') if m.node_tree else None

    def slot(self, spec):
        """the slot number of a paint spec (added on first use)"""
        for i, s in enumerate(self.slots):
            if s is not None and s == spec:
                return i
        self.slots.append(spec)
        self._build()
        return len(self.slots) - 1

    def _driver_value(self, b):
        v = b.value(0.0, label='cs.paint')
        drive(v.v.node.outputs[0], 'default_value', self.arm, self.prop, var='paint')
        return v

    def _values(self, b, spec, orig):
        """(lit, lit_tex, shade, shade_tex) for one slot: constants (tuples) or Vec"""
        if spec is None:
            return orig['lit'], orig['lit_tex'], orig['shade'], orig['shade_tex']
        sh = shade_of(spec)
        if isinstance(spec, str) and not self.textured:
            c = lin(spec)
            return c, orig['lit_tex'], tuple(x * 0.55 for x in sh), orig['shade_tex']
        if isinstance(spec, str):                      # a hex on a textured garment replaces the print
            pat = _const(b, lin(spec))
        else:
            g = b.node('ShaderNodeGroup')
            g.node_tree = pattern_group(spec)
            pat = Vec(b, g.outputs['Color'])
        return (1.0, 1.0, 1.0), pat, (1.0, 1.0, 1.0), b.vscale(pat, 0.55)

    def _build(self):
        for m in self.mats:
            o = self._out(m)
            if o is None:
                continue
            nt = m.node_tree
            clear_cs(nt)
            b = CSBuilder(nt, x0=-2600, y0=-1400)
            sel = self._driver_value(b)
            orig = self.orig[m.name]
            chans = {ch: [] for ch, _s in self.CHANNELS}
            for spec in self.slots:
                for (ch, _s), v in zip(self.CHANNELS, self._values(b, spec, orig)):
                    chans[ch].append(v)
            for ch, sock in self.CHANNELS:
                vals = chans[ch]
                cur = vals[0]
                for k, v in enumerate(vals[1:], 1):
                    eq = b.math('COMPARE', sel, float(k), 0.5)
                    cur = b.rgb_mix(_as_vec(b, cur), _as_vec(b, v), eq)
                if isinstance(cur, tuple):
                    for l in list(o.inputs[sock].links):
                        nt.links.remove(l)
                    o.inputs[sock].default_value = tuple(cur) + (1.0,)
                else:
                    b.link(cur, o.inputs[sock])
            from .look import refresh_pbr
            refresh_pbr(m)
        for m in self.outline_mats:
            o = self._out(m)
            if o is None:
                continue
            nt = m.node_tree
            clear_cs(nt)
            b = CSBuilder(nt, x0=-2600, y0=-1400)
            sel = self._driver_value(b)
            cur = self.orig_outline[m.name]
            for k, spec in enumerate(self.slots[1:], 1):
                eq = b.math('COMPARE', sel, float(k), 0.5)
                cur = b.rgb_mix(_as_vec(b, cur), _const(b, tuple(x * 0.22 for x in shade_of(spec))), eq)
            if isinstance(cur, tuple):
                o.inputs['Outline Color'].default_value = tuple(cur) + (1.0,)
            else:
                b.link(cur, o.inputs['Outline Color'])

    def set(self, slot, frame=None):
        self.arm[self.prop] = float(int(slot))
        if frame is not None:
            self.arm.keyframe_insert(f'["{self.prop}"]', frame=frame)
            _constant_path(self.arm, f'["{self.prop}"]')
            tag_keyed(self.arm)


def tag_keyed(idb):
    """tag an ID after keying it. An action that keyframe_insert CREATES on an ID which already has animation data
    (the armature carries its clips as NLA strips) is not evaluated by the session's depsgraph until the ID is tagged
    (measured: a TuTa bake after play_vrma_default read its own glow keys back as the last Python value on every
    frame). Renders build their own depsgraph and were right; Python reads after frame_set, and any bake that reads
    the evaluated scene (the springs, the gaze, the TuTa's neon), were not."""
    idb.update_tag()


def _as_vec(b, v):
    if isinstance(v, tuple):
        return _const(b, v)
    if isinstance(v, Vec):
        return v
    return Vec(b, v)                 # an original socket


def _constant_path(idb, path):
    """every key on `path` CONSTANT, EVERY array index of it (fcurves.find(path) is index 0 alone: the boater's
    location y/z, rotation and scale then eased Bezier toward the next outfit's hat, sliding and squashing it
    through the cyclist's block)"""
    from bpy_extras import anim_utils
    ad = idb.animation_data
    if ad is None or ad.action is None:
        return
    for slot in ad.action.slots:
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, slot)
        for fc in (cb.fcurves if cb else []):
            if fc.data_path == path:
                for kp in fc.keyframe_points:
                    kp.interpolation = 'CONSTANT'

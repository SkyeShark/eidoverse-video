"""The four vehicles' make(): the engine's EXAMPLES.x.make(opts), built as a film-ready Blender object.

    from eidoblend.sdf import EXAMPLES
    car = EXAMPLES['stylized_cyberpunk_sedan'].make(paint_color=0xff2bd6, paint_roughness=0.12, decal_text='ALETH8APO',
                                                     location=(0, 0, 0), rotation=(0, 0, -0.45))
    car.place_on_ground(0.0)
    car.set_paint('acid')                         # live: the materials and the underglow lamps follow
    car.key_uniform('uPaint', frame=48, value=0xff8a1a)

What make() builds (shading='parts', the default):
  * the mesh: the engine's map() dual-contoured at VEHICLE_VOXEL (a few millimetres: the shut-lines, louvers, trim
    and badge plate are 12 to 20 mm features), crease-keeping corner normals;
  * one Blender material per part (vehicles/shading.py), assigned per face by the map()'s material id: every
    pattern the engine's shade() drew per pixel is drawn per pixel again (the paint fleck, the racing stripes, the hex
    grille, the hex hubcaps, the badge glyphs, the camo edges, the lamps' view-dependent cores), and EEVEE's own
    ray-traced and probe reflections replace the engine's sampleEnvMap / procedural sky lookups;
  * the live uniforms as custom properties on the object (obj['uPaint'], obj['uRough'], obj['uMetalColor'],
    obj['uCamoMode']), read by the materials through Attribute nodes: set them (set_uniform, live_uniforms[...]) or
    key them (key_uniform, or ctx.key(car.object, '["uPaint"]')) and the render follows, no rebuild. Each object
    owns its own (as the GLSL original's per-instance uniforms; the TSL port's were shared by every instance);
  * real lamps (vehicles/lamps.py) parented to the body: headlight spots, tail lamps, the cyberpunk's underglow
    (coloured by uPaint through drivers) and the jet's afterburner glow. lamps=False leaves them out.

shading='baked' builds the engine's generic path instead (create_sdf_object with the example's surface() baked).

Options (snake_case or the engine's camelCase): paint_color / paintColor, paint_roughness / paintRoughness,
decal_text / decalText (cyberpunk), metal_color / metalColor (sleek car), camo (jet), plus every create_sdf_object
option (voxel, quality, cells, cache_dir, name, location, rotation, scale, scene, collection, build, ...) and
shading, lamps, lamp_power, stripe_glow (cyberpunk).
"""

from __future__ import annotations

import os

import numpy as np

from ..solid import SdfObject
from ..spec import SdfSpec
from . import parts as P

# the mesh voxel per vehicle at quality 'high' (the examples' preset): each one's finest feature over ~3 voxels (the
# sedans' 12 mm shut-lines and 16 mm louvers and trim, the sleek car's 18 mm glass patches, the jet's 20 mm missile
# fins and 30 mm struts). make(quality=...) without voxel= / cells= scales it: 'fast' a quick look (features under
# ~5 cm close up), 'balanced' a car seen whole, 'high' film close-ups, 'ultra' macro shots.
VEHICLE_VOXEL = {'modern': 0.004, 'cyber': 0.004, 'sleek': 0.005, 'jet': 0.006}
QUALITY_VOXEL_SCALE = {'fast': 4.0, 'balanced': 2.0, 'high': 1.0, 'ultra': 0.75}

KIND_OF = {'stylized_modern_sedan': 'modern', 'stylized_cyberpunk_sedan': 'cyber',
           'stylized_sci_fi_sleek_car': 'sleek', 'stylized_fighter_jet': 'jet'}

# a surface with every channel constant: the part materials draw the look, so the mesh stores no channels
FLAT_SURFACE = 'SdfSurface surface(vec3 p, vec3 n, float mat) { return sdfSurface(vec3(0.5), 0.5); }'

_ALIASES = {'paintColor': 'paint_color', 'paintRoughness': 'paint_roughness', 'decalText': 'decal_text',
            'metalColor': 'metal_color', 'lampPower': 'lamp_power', 'stripeGlow': 'stripe_glow'}

# the uniforms that are colours (set from hex / names / tuples) and the ones the object carries as properties
COLOR_UNIFORMS = ('uPaint', 'uMetalColor')
LIVE_UNIFORMS = {'modern': ('uPaint', 'uRough'), 'cyber': ('uPaint', 'uRough'),
                 'sleek': ('uMetalColor', 'uRough'), 'jet': ('uCamoMode',)}


class LiveUniforms:
    """The engine's mesh.userData.sdfLiveUniforms: car.live_uniforms['uPaint'] reads the live value (linear), and
    car.live_uniforms['uPaint'] = 0xff2d95 sets it (the materials, the lamps and the SDF program follow)."""

    def __init__(self, car):
        self._car = car

    def __getitem__(self, name):
        return self._car.get_uniform(name)

    def __setitem__(self, name, value):
        self._car.set_uniform(name, value)

    def keys(self):
        return list(LIVE_UNIFORMS[self._car.kind]) + (['uDecal'] if self._car.kind == 'cyber' else [])

    def __iter__(self):
        return iter(self.keys())

    def __contains__(self, name):
        return name in self.keys()

    def items(self):
        return [(k, self[k]) for k in self.keys()]

    def __repr__(self):
        return f'<LiveUniforms {dict(self.items())}>'


class VehicleSdf(SdfObject):
    """An SdfObject that is one of the four vehicles: its part materials, live uniforms and lamps."""

    def __init__(self, spec, kind, shading='parts', name=None, **kw):
        super().__init__(spec, name=name, **kw)
        self.kind = kind
        self.shading = shading
        self.parts = {}               # part name -> bpy Material
        self.lamps = []               # light objects parented to the body
        self.decal_text = P.DEFAULT_DECAL_TEXT
        self.stripe_glow = P.CYBER['paint']['stripe_glow']
        self.object['sdf_vehicle'] = kind

    # ------------------------------------------------------------------------------------------ uniforms ----
    @property
    def live_uniforms(self):
        return LiveUniforms(self)

    def get_uniform(self, name):
        if name == 'uDecal':
            return self.decal_text
        if name in self.object.keys():
            v = self.object[name]
            return tuple(float(x) for x in v) if hasattr(v, '__len__') else float(v)
        v = self.program.values[name]
        return v

    def set_uniform(self, name, value):
        """Set a live uniform by its GLSL name ('uPaint') or the engine's option style ('paint', 'paintColor',
        'paint_color', 'camo', 'decal_text'). Colours take hex ints, '#rrggbb', preset names or linear tuples."""
        name = _uniform_name(self.kind, name)
        if name == 'uDecal':
            return self.set_decal_text(value)
        if name == 'uCamoMode':
            value = float(P.camo_id(value))
        if name in COLOR_UNIFORMS:
            value = P.linear_color(value)
            self.program.set_uniform(name, value)          # linear already: _coerce keeps a tuple as given
            self.object[name] = list(value)
            _color_ui(self.object, name)
        else:
            self.program.set_uniform(name, float(value))
            self.object[name] = float(value)
        self.object.update_tag()
        return self

    def set_paint(self, color):
        return self.set_uniform('uPaint', color)

    def set_paint_roughness(self, r):
        return self.set_uniform('uRough', r)

    def set_metal_color(self, color):
        return self.set_uniform('uMetalColor', color)

    def set_camo(self, camo):
        return self.set_uniform('uCamoMode', camo)

    def set_decal_text(self, text):
        """make({decalText}) after the fact: redraw the badge canvas, for the material and the SDF program."""
        if self.kind != 'cyber':
            raise ValueError(f'{self.name}: only the cyberpunk sedan has a badge decal')
        from .badge import badge_image, decal_texture_array
        self.decal_text = str(text)
        self.program.textures['uDecal'] = decal_texture_array(self.decal_text)
        self.program._gpu_textures.pop('uDecal', None)
        mat = self.parts.get('badge')
        if mat is not None:
            img = badge_image(self.decal_text, name=f'{self.object.name}_badge')
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.get('badge_decal'):
                    node.image = img
        self.object['decal_text'] = self.decal_text
        return self

    def key_uniform(self, name, frame=None, value=None, interpolation=None, ctx=None):
        """Key a live uniform (the object's custom property) at `frame`, after setting it to `value` if given.
        Keys are LINEAR, except the jet's camo: a scheme is a switch (the engine set uCamoMode to 0..3, never between),
        and a LINEAR silver -> forest key would pass through sky and desert, so its keys hold (CONSTANT) unless
        `interpolation` says otherwise. With the harness's ctx the key goes through ctx.key (logged, and given its
        interpolation after render_frame)."""
        import bpy
        name = _uniform_name(self.kind, name)
        if name == 'uDecal':
            raise ValueError('the badge text is an image, not a keyable value: key a cut instead')
        if interpolation is None:
            interpolation = 'CONSTANT' if name == 'uCamoMode' else 'LINEAR'
        if value is not None:
            self.set_uniform(name, value)
        f = bpy.context.scene.frame_current if frame is None else frame
        path = f'["{name}"]'
        if ctx is not None:
            return ctx.key(self.object, path, frame=f, interpolation=interpolation)
        ok = self.object.keyframe_insert(path, frame=f)
        _set_interpolation(self.object, path, f, interpolation)
        return ok

    # ----------------------------------------------------------------------------------------- building ----
    def build(self, t=None, log=print):
        super().build(t=t, log=log)
        if self.shading == 'parts' and self.kind == 'jet' and self.contour is not None and len(self.contour.verts):
            self._camo_field()
        return self

    def bake(self, *args, **kw):
        """Not for the vehicles: their map() reads neither uTime nor a uniform, so every frame would be the same
        mesh (and the per-frame player would drop the part materials). Animate the object and the live uniforms."""
        raise ValueError(f'{self.name}: a vehicle does not change shape over time; key car.object\'s transform and '
                         f'the live uniforms (key_uniform) instead of bake()')

    def _camo_field(self):
        """The jet's camo blobs are smoothstep(0.50, 0.52, fbm(p * 1.6)): the smooth fbm is stored per vertex
        (exact, from the engine's GLSL fbm on the GPU) and the material thresholds it per pixel, so the camo edges
        stay sharp at any distance."""
        from .livery import eval_glsl
        vals = eval_glsl(self.program.extra, 'fbm(p * 1.6)', self.contour.verts, label=self.name + '.camo')
        me = self.object.data
        if 'jet_camo_fbm' in me.attributes:
            me.attributes.remove(me.attributes['jet_camo_fbm'])
        at = me.attributes.new('jet_camo_fbm', 'FLOAT', 'POINT')
        at.data.foreach_set('value', np.ascontiguousarray(vals, np.float32))
        self.stats['camo_field'] = (round(float(vals.min()), 3), round(float(vals.max()), 3))

    def set_lamps(self, on=True):
        """Switch the real lamps on or off (render and viewport)."""
        for ob in self.lamps:
            ob.hide_render = not on
            ob.hide_viewport = not on
        return self


def _uniform_name(kind, name):
    alias = {'paint': 'uPaint', 'paint_color': 'uPaint', 'paintColor': 'uPaint',
             'rough': 'uRough', 'paint_roughness': 'uRough', 'paintRoughness': 'uRough',
             'metal': 'uMetalColor', 'metal_color': 'uMetalColor', 'metalColor': 'uMetalColor',
             'camo': 'uCamoMode', 'camo_mode': 'uCamoMode', 'decal': 'uDecal', 'decal_text': 'uDecal',
             'decalText': 'uDecal'}
    name = alias.get(name, name)
    allowed = LIVE_UNIFORMS[kind] + (('uDecal',) if kind == 'cyber' else ())
    if name not in allowed:
        raise KeyError(f'{kind}: no live uniform {name!r} (has {list(allowed)})')
    return name


def _color_ui(ob, name):
    try:
        ui = ob.id_properties_ui(name)
        ui.update(subtype='COLOR', min=0.0, soft_max=1.0)
    except (TypeError, AttributeError):
        pass


def _set_interpolation(idb, path, frame, interpolation):
    """Python's keyframe_insert makes BEZIER keys whatever the preference says: give the new ones their interpolation."""
    ad = getattr(idb, 'animation_data', None)
    if ad is None or ad.action is None:
        return
    try:
        from bpy_extras import anim_utils
        bag = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
        curves = bag.fcurves if bag is not None else []
    except (AttributeError, TypeError, RuntimeError):
        curves = getattr(ad.action, 'fcurves', [])
    for fc in curves:
        if fc.data_path != path:
            continue
        for kp in fc.keyframe_points:
            if abs(kp.co.x - frame) < 1e-3:
                kp.interpolation = interpolation


def _options(opts):
    o = {}
    for k, v in opts.items():
        o[_ALIASES.get(k, k)] = v
    return o


def make_vehicle(example, opts=None, **kw):
    """Build one of the four vehicles from its EXAMPLES entry (the make factory behind EXAMPLES[...].make)."""
    import bpy
    o = _options(dict(opts or {}, **kw))
    kind = KIND_OF[example.name]
    shading = o.pop('shading', 'parts')
    if shading not in ('parts', 'baked'):
        raise ValueError(f"shading must be 'parts' or 'baked', not {shading!r}")
    lamps = o.pop('lamps', True)
    lamp_power = float(o.pop('lamp_power', 1.0))
    stripe_glow = o.pop('stripe_glow', None)
    uniforms = dict(example.get('uniforms') or {})
    # createSdfObject({...spec, uniforms}) overrides, in the engine's {uPaint: {value: colour}} style or any other: a
    # colour uniform takes every colour form linear_color reads (the GLSL declares it vec3, so a bare hex would
    # otherwise arrive as one float)
    for k, v in (o.pop('uniforms', {}) or {}).items():
        if k in COLOR_UNIFORMS:
            if isinstance(v, dict):
                v = v.get('value')
            elif isinstance(v, tuple) and len(v) == 2 and isinstance(v[0], str):
                v = v[1]
            uniforms[k] = ('color', P.linear_color(v))
        else:
            uniforms[k] = v
    # the engine's make() options -> uniforms
    if 'paint_color' in o:
        if kind == 'sleek':
            raise TypeError("stylized_sci_fi_sleek_car takes metal_color (its body is metal), not paint_color")
        if kind == 'jet':
            raise TypeError('stylized_fighter_jet takes camo, not paint_color')
        uniforms['uPaint'] = ('color', P.linear_color(o.pop('paint_color')))
    if 'paint_roughness' in o:
        if kind == 'jet':
            raise TypeError('stylized_fighter_jet takes camo, not paint_roughness')
        uniforms['uRough'] = float(o.pop('paint_roughness'))
    if 'metal_color' in o:
        if kind != 'sleek':
            raise TypeError(f'{example.name} has no metal_color (the sleek car does)')
        uniforms['uMetalColor'] = ('vec3', P.linear_color(o.pop('metal_color')))
    if 'camo' in o:
        if kind != 'jet':
            raise TypeError(f'{example.name} has no camo (the fighter jet does)')
        uniforms['uCamoMode'] = float(P.camo_id(o.pop('camo')))
    decal_text = o.pop('decal_text', None)
    if decal_text is not None and kind != 'cyber':
        raise TypeError(f'{example.name} has no badge decal (the cyberpunk sedan does)')

    spec = dict(example.as_dict())
    if 'quality' in o and 'voxel' not in o and 'cells' not in o:
        q = o['quality'] if o['quality'] in QUALITY_VOXEL_SCALE else 'balanced'
        o['voxel'] = VEHICLE_VOXEL[kind] * QUALITY_VOXEL_SCALE[q]
    if 'cells' in o and 'voxel' not in o:
        spec.pop('voxel', None)                    # cells= along the longest side replaces the vehicle's voxel
    spec.update(o)
    spec['uniforms'] = uniforms
    if kind == 'cyber':
        from .badge import decal_texture_array
        tex = dict(spec.get('textures') or {})
        tex['uDecal'] = decal_texture_array(decal_text if decal_text is not None else P.DEFAULT_DECAL_TEXT)
        spec['textures'] = tex
    build = spec.pop('build', True)
    t = spec.pop('time', None)
    scene = spec.pop('scene', None)
    collection = spec.pop('collection', None)
    name = spec.pop('name', None)
    location = spec.pop('location', (0, 0, 0))
    rotation = spec.pop('rotation', (0, 0, 0))
    scale = spec.pop('scale', 1.0)
    log = spec.pop('log', print)
    if shading == 'parts':
        spec['surface'] = FLAT_SURFACE
        spec['carrier'] = 'vertex'
    sp = SdfSpec.from_options(spec)
    car = VehicleSdf(sp, kind, shading=shading, scene=scene, collection=collection, name=name or sp.name,
                     location=location, rotation=rotation, scale=scale)
    if decal_text is not None:
        car.decal_text = str(decal_text)
    if stripe_glow is not None:
        car.stripe_glow = float(stripe_glow)
    # the live uniforms on the object, where the materials read them
    for uname in LIVE_UNIFORMS[kind]:
        v = car.program.values[uname]
        car.object[uname] = list(v) if isinstance(v, tuple) else float(v)
        if uname in COLOR_UNIFORMS:
            _color_ui(car.object, uname)
    if kind == 'cyber':
        car.object['decal_text'] = car.decal_text
    if shading == 'parts':
        from .shading import part_materials
        car.parts = part_materials(car)
        ids = P.IDS[kind]
        car.materials_by_id = {mid: car.parts[pname] for mid, pname in ids.items()}
    if build and sp.map is not None:
        car.build(t=t if t is not None else sp.time, log=log)
    if lamps:
        from .lamps import add_lamps
        car.lamps = add_lamps(car, power=lamp_power)
    bpy.context.view_layer.update()
    return car


def make_modern_sedan(example, opts=None, **kw):
    """EXAMPLES.stylizedModernSedan.make({paintColor, paintRoughness}): paint_color (default pewter 0xc8c8d2),
    paint_roughness (0 mirror-smooth wax, ~0.18 factory semi-gloss, ~0.4 matte / wrap; default 0.45)."""
    return make_vehicle(example, opts, **kw)


def make_cyberpunk_sedan(example, opts=None, **kw):
    """EXAMPLES.stylizedCyberpunkSedan.make({paintColor, paintRoughness, decalText}): paint_color drives the rim
    glow, underglow, accent strips and grille (default electric cyan 0x00e7ff; the body stays near-black),
    paint_roughness (default 0.18, floored at 0.20 on the body), decal_text (default 'ALETH8APO')."""
    return make_vehicle(example, opts, **kw)


def make_sci_fi_sleek_car(example, opts=None, **kw):
    """EXAMPLES.stylizedSciFiSleekCar.make({metalColor, paintRoughness}): metal_color is the body's F0 (silver
    0xf3eee0, gold 0xffb44a, copper 0xf2a387, aluminum 0xe7e7e7, anodized blue 0x4d80e6, anodized purple 0x8b4dcc,
    or a METAL_PRESETS name), paint_roughness (0 perfect mirror, ~0.10 polished, ~0.35 brushed, 0.6+ matte)."""
    return make_vehicle(example, opts, **kw)


def make_fighter_jet(example, opts=None, **kw):
    """EXAMPLES.stylizedFighterJet.make({camo}): 'silver' | 'sky' | 'desert' | 'forest' or 0..3 (default 'sky');
    an unknown name raises, as the engine did."""
    return make_vehicle(example, opts, **kw)


def cache_folder(car, *parts):
    d = os.path.join(car.cache_dir, 'vehicles', *parts)
    os.makedirs(d, exist_ok=True)
    return d

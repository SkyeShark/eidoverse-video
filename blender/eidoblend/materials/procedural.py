"""eidoblend.materials.procedural: the Blender edition of eidoverse/procedural_materials.js.

    from eidoblend.materials import procedural as PM
    noise_tx = PM.noise(512, 512, scale=12, octaves=5, contrast=0.7)          # a bpy Image (Non-Color), packed
    normal_tx = PM.height_to_normal(PM.composite(noise_tx, PM.scratches(512, 512, density=0.5, depth=0.6), 'add',
                                                 strength=0.5), strength=1.4)
    mat = PM.create_painted_metal(color=0x8a1c1c, scratches=True, smudges=True, repeat=(3, 3))
    obj.data.materials.append(mat)

Generators make textures the way the engine's canvas does (eidoblend/materials/_gen.py: the maths ones are
byte-identical to the engine's, the drawn ones replay its draw list) and hand back a Blender image, packed into the
.blend (a saved file renders on its own) and flagged `eido_procedural` = the generator's name. Rows are flipped
from canvas order into Blender's (row 0 at the bottom), as three's flipY puts the canvas's top row at v = 1, so a
texture sits on the UVs as it did in the engine. Each generator also takes the engine's call shape:
PM.noise(512, 512, {'scale': 12, 'octaves': 5}) with the engine's camelCase keys works as well as keywords.

Factories return a Principled BSDF material wired as three's MeshStandardMaterial / MeshPhysicalMaterial reads
its maps: color times map (the engine's gotcha: color multiplies the map), roughness times the roughness map's
green channel, metalness times the metalness map's blue, clearcoat roughness times its map's green, the normal map
through a tangent-space Normal Map node at normalScale's strength. Blender-only options on every factory:
repeat=(u, v) (three's texture.repeat: a Mapping node on the UVs), uv_map (the UV layer; default the active one)
and name.

Colours: 0xRRGGBB, '#rrggbb', {'r', 'g', 'b'} (0-1) or an (r, g, b) tuple (0-1), sRGB as in the engine; material
colours are converted to Blender's linear values, as three's ColorManagement does.
"""
import bpy
import numpy as np

from . import _gen
from ..terrain._nodes import Graph, new_material, output, principled

TEX_SIZE = 512
_PIXELS = {}                       # image name -> canvas-order uint8 (h, w, 3): composites skip a pixel read-back


# ------------------------------------------------------------------------------------------------- utils ---

def _snake(k):
    out = ''
    for ch in k:
        out += ('_' + ch.lower()) if ch.isupper() else ch
    return out


def _opts(opts, kw):
    """the engine's opts dict (camelCase allowed) merged under keyword arguments"""
    out = {}
    for k, v in (opts or {}).items():
        out[_snake(k)] = v
    for k, v in kw.items():
        out[_snake(k)] = v
    return out


def srgb_to_linear(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_color(c):
    """an engine colour (hex / '#hex' / dict / 0-1 tuple, sRGB) -> Blender linear RGBA"""
    r, g, b = _gen.parse_color(c)
    lin = srgb_to_linear((r, g, b))
    return (float(lin[0]), float(lin[1]), float(lin[2]), 1.0)


def _unique(base):
    name = base
    i = 1
    while name in bpy.data.images:
        i += 1
        name = '%s.%03d' % (base, i)
    return name


def image_from_canvas(px, name, srgb=False, kind=None):
    """(h, w, 3|4) uint8 in canvas order -> a packed bpy Image (sRGB or Non-Color)."""
    px = np.ascontiguousarray(np.asarray(px)[..., :3])
    h, w = px.shape[:2]
    img = bpy.data.images.new(_unique(name), w, h, alpha=False, float_buffer=False)
    img.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[..., :3] = np.flipud(px).astype(np.float32) / 255.0
    img.pixels.foreach_set(rgba.ravel())
    img.update()
    img.pack()
    img['eido_procedural'] = kind or name
    _PIXELS[img.name] = px
    return img


def canvas_bytes(img):
    """a bpy Image (any: generated here, or a loaded texture) or an array -> canvas-order uint8 (h, w, 3), the bytes
    the engine's drawImage + getImageData would see (a byte image's stored values; a float image clamped)."""
    if isinstance(img, np.ndarray):
        return img[..., :3]
    px = _PIXELS.get(img.name)
    if px is not None and px.shape[:2] == (img.size[1], img.size[0]):
        return px
    w, h = img.size
    buf = np.empty(w * h * img.channels, dtype=np.float32)
    img.pixels.foreach_get(buf)
    a = buf.reshape(h, w, img.channels)
    if img.channels < 3:
        a = np.repeat(a[..., :1], 3, axis=-1)
    return np.flipud(np.clip(np.floor(a[..., :3] * 255.0 + 0.5), 0, 255).astype(np.uint8))


# ---------------------------------------------------------------------------------------------- generators ---

def scratches(w=512, h=512, opts=None, name='pm_scratches', **kw):
    """Directional scratch marks for roughness maps: white = scratched, black = clean.
    density 0.3, depth 0.5, direction None (radians; None = random per stroke), seed 42."""
    o = _opts(opts, kw)
    return image_from_canvas(_gen.scratches(w, h, o.get('density'), o.get('depth'), o.get('direction'),
                                            o.get('seed')), name, kind='scratches')


def smudges(w=512, h=512, opts=None, name='pm_smudges', **kw):
    """Blotchy smudge / fingerprint marks for roughness maps: white = smudged. amount 0.3, scale 1, seed 123."""
    o = _opts(opts, kw)
    return image_from_canvas(_gen.smudges(w, h, o.get('amount'), o.get('scale'), o.get('seed')), name,
                             kind='smudges')


def noise(w=512, h=512, opts=None, name='pm_noise', **kw):
    """fBm value noise (grayscale). scale 5, octaves 6, contrast 1, offset 0, warp False (domain warping)."""
    o = _opts(opts, kw)
    return image_from_canvas(_gen.noise(w, h, o.get('scale'), o.get('octaves'), o.get('contrast'), o.get('offset'),
                                        o.get('warp')), name, kind='noise')


def voronoi(w=512, h=512, opts=None, name='pm_voronoi', **kw):
    """Voronoi cells (grayscale). scale 8, mode 'cells' (a grey per cell) | 'edges' (white borders narrower than
    edge_width) | 'distance' (to the nearest feature, x2), edge_width 0.08."""
    o = _opts(opts, kw)
    return image_from_canvas(_gen.voronoi_tex(w, h, o.get('scale'), o.get('mode'), o.get('edge_width')), name,
                             kind='voronoi')


def patches(w=512, h=512, opts=None, name='pm_patches', **kw):
    """Colour patches (sRGB): cow spots, giraffe polygons, camo, frog splotches. base_color 0xfff0e0,
    patch_color 0x1a1a1a, scale 4, threshold 0.55, softness 0.05, shape 'blob' | 'voronoi' | 'spots'."""
    o = _opts(opts, kw)
    return image_from_canvas(_gen.patches(w, h, o.get('base_color'), o.get('patch_color'), o.get('scale'),
                                          o.get('threshold'), o.get('softness'), o.get('shape')), name, srgb=True,
                             kind='patches')


def pores(w=512, h=512, opts=None, name='pm_pores', **kw):
    """Skin-pore normal map (flat = rgb(128, 128, 255)). density 0.5, depth 0.3, seed 77."""
    o = _opts(opts, kw)
    return image_from_canvas(_gen.pores(w, h, o.get('density'), o.get('depth'), o.get('seed')), name, kind='pores')


def weave(w=512, h=512, opts=None, name='pm_weave', **kw):
    """Fabric crosshatch for roughness. density 20 (threads), variation 0.3."""
    o = _opts(opts, kw)
    return image_from_canvas(_gen.weave(w, h, o.get('density'), o.get('variation')), name, kind='weave')


def grain(w=512, h=512, opts=None, name='pm_grain', **kw):
    """Directional grain: wood, leather, brushed metal. scale 4, stretch 8 (the fBm's frequency along v times
    stretch: the grain runs along u), contrast 1.2."""
    o = _opts(opts, kw)
    return image_from_canvas(_gen.grain(w, h, o.get('scale'), o.get('stretch'), o.get('contrast')), name,
                             kind='grain')


def height_to_normal(height_tex, opts=None, name='pm_normal', **kw):
    """A normal map from any grayscale height texture (its red channel), by central differences, wrapped at the
    borders. strength 1. The engine's channel signs are kept by default: red is right (a bump's left flank faces
    -u), but green is the engine's inverse of three's green-up reading, so a bump's upper and lower flanks swap
    their light. flip_green=True (Blender edition only) writes green-up maps."""
    o = _opts(opts, kw)
    return image_from_canvas(_gen.height_to_normal(canvas_bytes(height_tex), o.get('strength'),
                                                   bool(o.get('flip_green'))), name, kind='height_to_normal')


def composite(tex_a, tex_b, mode='multiply', opts=None, name='pm_composite', **kw):
    """Blend two textures: mode 'multiply' | 'add' | 'screen' | 'overlay' | 'max' | 'min'; strength (0-1) mixes
    the result over a. b is resampled to a's size. The result is Non-Color unless a was sRGB."""
    o = _opts(opts, kw)
    srgb = isinstance(tex_a, bpy.types.Image) and tex_a.colorspace_settings.name == 'sRGB'
    return image_from_canvas(_gen.composite(canvas_bytes(tex_a), canvas_bytes(tex_b), mode, o.get('strength')),
                             name, srgb=srgb, kind='composite_' + (mode or 'multiply'))


# ------------------------------------------------------------------------------------------ the material ---

class _Mat:
    """A Principled material wired from three's material options (the factories' common back end)."""

    def __init__(self, name, repeat=(1.0, 1.0), uv_map=None):
        self.mat = new_material(name)
        self.g = Graph(self.mat.node_tree)
        self.bsdf = principled(self.mat)
        self.out = output(self.mat)
        uvn = self.g.node('ShaderNodeUVMap')
        if uv_map:
            uvn.uv_map = uv_map
        su, sv = (repeat, repeat) if isinstance(repeat, (int, float)) else repeat
        self.vec = uvn.outputs['UV']
        if (su, sv) != (1, 1):
            self.vec = self.g.vmath('MULTIPLY', self.vec, (float(su), float(sv), 1.0))
        self.uv_map = uv_map or ''
        self.mat['eido_procedural'] = name

    def tex(self, img):
        return self.g.tex(img, self.vec, 'Linear')

    def channel(self, img, idx):
        r, g, b = self.g.separate_rgb(self.tex(img).outputs['Color'])
        return (r, g, b)[idx]

    def color(self, color=None, map_img=None):
        sock = self.bsdf.inputs['Base Color']
        if map_img is None:
            sock.default_value = linear_color(color if color is not None else 0xffffff)
            return
        c = self.tex(map_img).outputs['Color']
        if color is not None and linear_color(color)[:3] != (1.0, 1.0, 1.0):
            c = self.g.mix('RGBA', 1.0, c, linear_color(color), blend='MULTIPLY')
        self.g.set(sock, c)

    def scalar(self, socket, value, map_img=None, channel=1):
        sock = self.bsdf.inputs[socket]
        if map_img is None:
            sock.default_value = float(value)
        else:
            self.g.set(sock, self.g.mul(self.channel(map_img, channel), float(value), clamp=True))

    def normal(self, img, scale=1.0):
        nm = self.g.node('ShaderNodeNormalMap', space='TANGENT', uv_map=self.uv_map)
        nm.inputs['Strength'].default_value = float(scale)
        self.g.set(nm.inputs['Color'], self.tex(img).outputs['Color'])
        self.g.set(self.bsdf.inputs['Normal'], nm.outputs['Normal'])
        return nm


MESH_MATERIAL_KEYS = ('color', 'map', 'roughness', 'roughness_map', 'metalness', 'metalness_map', 'normal_map',
                      'normal_scale', 'clearcoat', 'clearcoat_roughness', 'clearcoat_roughness_map', 'transmission',
                      'thickness', 'ior', 'ao_map')


def mesh_material(opts=None, name='pm_material', repeat=(1.0, 1.0), uv_map=None, **kw):
    """three's MeshStandardMaterial / MeshPhysicalMaterial options -> a Principled material (what a recipe that
    builds its own material from generated maps uses). Takes: color, map, roughness, roughness_map, metalness,
    metalness_map, normal_map, normal_scale (number or (x, y): Blender's Normal Map has one strength, x is used),
    clearcoat, clearcoat_roughness, clearcoat_roughness_map, transmission (made subsurface: see create_skin),
    thickness, ior, ao_map (unwired: EEVEE shades its own occlusion). Any other key is ignored with three's warning
    ("'rougness' is not a property")."""
    o = _opts(opts, kw)
    for k in o:
        if k not in MESH_MATERIAL_KEYS:
            print("[procedural] mesh_material: '%s' is not a property of the material (ignored)" % k)
    m = _Mat(name, repeat, uv_map)
    m.color(o.get('color'), o.get('map'))
    m.scalar('Roughness', o.get('roughness', 1.0), o.get('roughness_map'), 1)
    m.scalar('Metallic', o.get('metalness', 0.0), o.get('metalness_map'), 2)
    if o.get('normal_map') is not None:
        ns = o.get('normal_scale', 1.0)
        if isinstance(ns, (tuple, list)):
            ns = ns[0]
        elif hasattr(ns, 'x'):
            ns = ns.x
        m.normal(o['normal_map'], ns)
    if o.get('clearcoat'):
        m.bsdf.inputs['Coat Weight'].default_value = float(o['clearcoat'])
        m.scalar('Coat Roughness', o.get('clearcoat_roughness', 0.0), o.get('clearcoat_roughness_map'), 1)
        m.bsdf.inputs['Coat IOR'].default_value = 1.5          # three's clearcoat layer
    if o.get('ior') is not None:
        m.bsdf.inputs['IOR'].default_value = float(o['ior'])
    if o.get('transmission'):
        _subsurface(m, float(o['transmission']), float(o.get('thickness', 0.8)), o.get('color'))
    return m.mat


def _subsurface(m, weight, thickness, color):
    """three's partial transmission (createSkin's 'subsurface approximation') as Blender's own subsurface: EEVEE
    draws partial transmission as grain at any sample count, and its option says what it stands for. The scatter
    distance grows with the engine's thickness (0.8 -> 8 mm), skin-red falloff."""
    m.bsdf.inputs['Subsurface Weight'].default_value = min(1.0, weight)
    m.bsdf.inputs['Subsurface Scale'].default_value = 0.01 * thickness
    m.bsdf.inputs['Subsurface Radius'].default_value = (1.0, 0.35, 0.2)
    m.mat['eido_subsurface_from_transmission'] = weight


# --------------------------------------------------------------------------------------------- factories ---

def create_painted_metal(opts=None, name='pm_painted_metal', repeat=(1.0, 1.0), uv_map=None, **kw):
    """Painted metal: car paint, appliances, painted panels, server racks (physical, clearcoated).
    color 0x1a3a6a, metalness 0.4, roughness 0.3, clearcoat 0.8, clearcoat_roughness 0.1,
    scratches {density, depth, direction, seed} | True (they roughen the clearcoat),
    smudges {amount, scale, seed} | True (added at 0.4 over the scratches), tex_size 512."""
    o = _opts(opts, kw)
    ts = o.get('tex_size') or TEX_SIZE
    ccmap = None
    if o.get('scratches'):
        so = o['scratches'] if isinstance(o['scratches'], dict) else {}
        ccmap = scratches(ts, ts, so, name=name + '_scratches')
    if o.get('smudges'):
        smo = o['smudges'] if isinstance(o['smudges'], dict) else {}
        sm = smudges(ts, ts, smo, name=name + '_smudges')
        ccmap = composite(ccmap, sm, 'add', strength=0.4, name=name + '_coat_rough') if ccmap is not None else sm
    return mesh_material(name=name, repeat=repeat, uv_map=uv_map, color=o.get('color') or 0x1a3a6a,
                         metalness=_gen._nn(o.get('metalness'), 0.4), roughness=_gen._nn(o.get('roughness'), 0.3),
                         clearcoat=_gen._nn(o.get('clearcoat'), 0.8),
                         clearcoat_roughness=_gen._nn(o.get('clearcoat_roughness'), 0.1),
                         clearcoat_roughness_map=ccmap)


def create_rubber(opts=None, name='pm_rubber', repeat=(1.0, 1.0), uv_map=None, **kw):
    """Rubber: tyres, boots, gaskets, grips. color 0x222222, grain_scale 20, bump_strength 0.5, tex_size 512.
    Roughness 0.95 times an fBm map; the normal map is that map's height_to_normal at normalScale 0.3."""
    o = _opts(opts, kw)
    ts = o.get('tex_size') or TEX_SIZE
    nt = noise(ts, ts, scale=o.get('grain_scale') or 20, octaves=4, contrast=0.5, name=name + '_grain')
    nm = height_to_normal(nt, strength=o.get('bump_strength') or 0.5, name=name + '_normal')
    return mesh_material(name=name, repeat=repeat, uv_map=uv_map, color=o.get('color') or 0x222222, roughness=0.95,
                         metalness=0.0, roughness_map=nt, normal_map=nm, normal_scale=0.3)


def create_skin(opts=None, name='pm_skin', repeat=(1.0, 1.0), uv_map=None, **kw):
    """Organic skin: humans, creatures, aliens. color 0xcc8866, roughness 0.6, subsurface 0.15, thickness 0.8,
    variation {scale 3} | False (an fBm blotch map), pores {density, depth, seed} | False (normal map at
    pore_strength 0.2), patches {base_color, patch_color, scale, threshold, softness, shape} (replaces the
    variation map; base_color defaults to color), tex_size 512. ior 1.3. The engine's transmission is Blender's
    subsurface here (see mesh_material)."""
    o = _opts(opts, kw)
    ts = o.get('tex_size') or TEX_SIZE
    base = o.get('color') or 0xcc8866
    var = o.get('variation', None)
    mp = None
    if var is not False:
        vs = (var.get('scale') if isinstance(var, dict) else None) or 3
        mp = image_from_canvas(_gen.skin_variation(ts, base, vs), name + '_variation', srgb=True,
                               kind='skin_variation')
    if o.get('patches'):
        po = _opts(o['patches'], {})
        if not po.get('base_color'):
            po['base_color'] = base
        mp = patches(ts, ts, po, name=name + '_patches')
    nm = None
    pore_strength = o.get('pore_strength') or 0.2
    if o.get('pores', None) is not False:
        po = o.get('pores') if isinstance(o.get('pores'), dict) else {}
        nm = pores(ts, ts, po, name=name + '_pores')
    return mesh_material(name=name, repeat=repeat, uv_map=uv_map, color=base, map=mp,
                         roughness=_gen._nn(o.get('roughness'), 0.6), metalness=0.0,
                         transmission=_gen._nn(o.get('subsurface'), 0.15),
                         thickness=_gen._nn(o.get('thickness'), 0.8), ior=1.3, normal_map=nm,
                         normal_scale=pore_strength)


def create_scaly(opts=None, name='pm_scaly', repeat=(1.0, 1.0), uv_map=None, **kw):
    """Scales: reptile, fish, dragon, sea monster. Voronoi cells, a shade per cell with dark edges, raised centres
    in the normal map. color 0x2a5a3a, cell_size 12, roughness 0.4, metalness 0.1, clearcoat 0.3,
    bump_strength 2, tex_size 512. flip_green=True (Blender edition only): the normal map green-up, so the cells'
    upper flanks catch a light from above (the engine's map has them swapped; see height_to_normal)."""
    o = _opts(opts, kw)
    ts = o.get('tex_size') or TEX_SIZE
    col, nor = _gen.scaly_maps(ts, o.get('color') or 0x2a5a3a, o.get('cell_size') or 12, o.get('bump_strength'),
                               bool(o.get('flip_green')))
    cimg = image_from_canvas(col, name + '_color', srgb=True, kind='scaly_color')
    nimg = image_from_canvas(nor, name + '_normal', kind='scaly_normal')
    return mesh_material(name=name, repeat=repeat, uv_map=uv_map, map=cimg, normal_map=nimg, normal_scale=1.0,
                         roughness=_gen._nn(o.get('roughness'), 0.4), metalness=_gen._nn(o.get('metalness'), 0.1),
                         clearcoat=_gen._nn(o.get('clearcoat'), 0.3), clearcoat_roughness=0.4)


def create_fabric(opts=None, name='pm_fabric', repeat=(1.0, 1.0), uv_map=None, **kw):
    """Fabric: cloth, clothing, upholstery. color 0x4a4a6a, thread_density 30, variation 0.2, roughness 1 times
    the weave; diffuse_map / normal_map / roughness_map: loaded textures (bpy Images, e.g. a Poly Haven set from
    eidoblend.terrain.load_set) layered under the weave (the roughness map multiplied by it); wear {amount 0.5,
    seed 99}: smudges added at 0.2 over the roughness; tex_size 512."""
    o = _opts(opts, kw)
    ts = o.get('tex_size') or TEX_SIZE
    wv = weave(ts, ts, density=o.get('thread_density') or 30, variation=_gen._nn(o.get('variation'), 0.2),
               name=name + '_weave')
    rough = wv
    mp = o.get('diffuse_map')
    if mp is not None:
        mp.colorspace_settings.name = 'sRGB'
    if o.get('roughness_map') is not None:
        rough = composite(o['roughness_map'], wv, 'multiply', name=name + '_rough')
    if o.get('wear'):
        wo = o['wear'] if isinstance(o['wear'], dict) else {}
        wt = smudges(ts, ts, amount=wo.get('amount') or 0.5, seed=wo.get('seed') or 99, name=name + '_wear')
        rough = composite(rough, wt, 'add', strength=0.2, name=name + '_worn_rough')
    return mesh_material(name=name, repeat=repeat, uv_map=uv_map, color=o.get('color') or 0x4a4a6a, map=mp,
                         roughness=1.0, metalness=0.0, roughness_map=rough, normal_map=o.get('normal_map'))


def create_worn_metal(opts=None, name='pm_worn_metal', repeat=(1.0, 1.0), uv_map=None, **kw):
    """Worn, aged metal: chipped paint over bare metal. One fBm field drives colour, roughness (0.3 paint / 0.6
    metal) and metalness (0.3 / 0.9) maps. paint_color 0x3a5a3a, metal_color 0x888888, wear_amount 0.4 (0-1),
    wear_scale 4, tex_size 512."""
    o = _opts(opts, kw)
    ts = o.get('tex_size') or TEX_SIZE
    col, ro, me = _gen.worn_metal_maps(ts, o.get('paint_color') or 0x3a5a3a, o.get('metal_color') or 0x888888,
                                       _gen._nn(o.get('wear_amount'), 0.4), o.get('wear_scale') or 4)
    cimg = image_from_canvas(col, name + '_color', srgb=True, kind='worn_metal_color')
    rimg = image_from_canvas(ro, name + '_rough', kind='worn_metal_roughness')
    mimg = image_from_canvas(me, name + '_metal', kind='worn_metal_metalness')
    return mesh_material(name=name, repeat=repeat, uv_map=uv_map, map=cimg, roughness=1.0, roughness_map=rimg,
                         metalness=1.0, metalness_map=mimg)


def computer_plastic_90s(repeat=(3.0, 3.0), name='pm_plastic_90s', tex_size=512, uv_map=None):
    """The help's recipe, 90s computer plastic (no Poly Haven texture exists for it), step for step: fBm plus
    scratches as the height, its normal map at strength 1.4 (normalScale 0.7), smudges plus fBm as roughness,
    colour 0xc8c4b8, roughness 0.8, metalness 0.05, the maps repeated 3 x 3."""
    s = tex_size
    noise_tx = noise(s, s, scale=12, octaves=5, contrast=0.7, name=name + '_noise')
    scratch_tx = scratches(s, s, density=0.5, depth=0.6, name=name + '_scratches')
    height_tx = composite(noise_tx, scratch_tx, 'add', strength=0.5, name=name + '_height')
    normal_tx = height_to_normal(height_tx, strength=1.4, name=name + '_normal')
    rough_tx = composite(smudges(s, s, amount=0.5, name=name + '_smudges'), noise_tx, 'add', name=name + '_rough')
    return mesh_material(name=name, repeat=repeat, uv_map=uv_map, color=0xc8c4b8, roughness=0.8, metalness=0.05,
                         normal_map=normal_tx, roughness_map=rough_tx, normal_scale=0.7)


FACTORIES = {'painted_metal': create_painted_metal, 'rubber': create_rubber, 'skin': create_skin,
             'scaly': create_scaly, 'fabric': create_fabric, 'worn_metal': create_worn_metal,
             'computer_plastic_90s': computer_plastic_90s}


HELP = """---------- eidoblend.materials.procedural (ProceduralMaterials) API reference ----------

Texture generators + PBR material factories, for when no fetched texture set fits (most often plastic).

-- Texture generators (return a packed bpy Image; Non-Color unless noted) --
  scratches(w, h, density=, depth=, direction=, seed=)      grayscale scratch marks
  smudges(w, h, amount=, scale=, seed=)                    grayscale roughness blotches
  noise(w, h, scale=, octaves=, contrast=, offset=, warp=) fBm grayscale
  voronoi(w, h, scale=, mode=, edge_width=)                cellular: 'cells' | 'edges' | 'distance'
  patches(w, h, base_color=, patch_color=, scale=, threshold=, softness=, shape=)   colour (sRGB): cow / giraffe
  pores(w, h, density=, depth=, seed=)                     skin normal map
  weave(w, h, density=, variation=)                        fabric roughness
  grain(w, h, scale=, stretch=, contrast=)                 wood / leather grain
  height_to_normal(image, strength=)                       height -> normal map
  composite(a, b, mode, strength=)                         blend two images: multiply | add | screen | overlay | max | min
  (each also takes the engine's call shape: noise(512, 512, {'scale': 12, 'octaves': 5}))

-- PBR material factories (return a Principled BSDF material) --
  create_painted_metal(color=, scratches=, smudges=, clearcoat=)   car paint, server racks
  create_rubber(color=, grain_scale=, bump_strength=)              tyres, gaskets
  create_skin(color=, subsurface=, pores=, variation=, patches=)   organic / animals
  create_scaly(color=, cell_size=, clearcoat=, bump_strength=)     reptile, fish
  create_fabric(color=, thread_density=, diffuse_map=, wear=)      clothing
  create_worn_metal(paint_color=, metal_color=, wear_amount=, wear_scale=)   chipped paint
  mesh_material(color=, map=, roughness=, roughness_map=, normal_map=, normal_scale=, ...)   your own recipe
  every factory also takes repeat=(u, v) (three's texture.repeat), uv_map= and name=

-- Recipe: 90s computer plastic (no Poly Haven texture exists for this) --
  from eidoblend.materials import procedural as PM
  noise_tx   = PM.noise(512, 512, scale=12, octaves=5, contrast=0.7)
  scratch_tx = PM.scratches(512, 512, density=0.5, depth=0.6)
  height_tx  = PM.composite(noise_tx, scratch_tx, 'add', strength=0.5)
  normal_tx  = PM.height_to_normal(height_tx, strength=1.4)
  rough_tx   = PM.composite(PM.smudges(512, 512, amount=0.5), noise_tx, 'add')
  plastic = PM.mesh_material(color=0xc8c4b8, roughness=0.8, metalness=0.05, normal_map=normal_tx,
                             roughness_map=rough_tx, normal_scale=0.7, repeat=(3, 3))
  (or PM.computer_plastic_90s(repeat=(3, 3)): the same, in one call)

-- Common gotchas --
  * Set repeat=(N, N) on large surfaces, or one 512 px tile spreads as a giant blur across the mesh.
  * The factories' roughness and metalness scale their maps: roughness=0.5 halves the whole roughness map.
  * color multiplies the colour map (the engine's rule): to shift a baked-in hue you mostly only darken it.
  * Generation is CPU work (numpy): make the materials once in setup(), not per frame. Images are packed.
"""


def help():
    print(HELP)
    return HELP

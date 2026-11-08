"""make_terrain: the engine's procedural heightfield ground, in Blender.

    from eidoblend.terrain import make_terrain
    terrain, height_at = make_terrain(size=80, segments=256, amplitude=3, seed=7, flat_radius=8,
        layers=[{'set': 'Ground106', 'tile_metres': 2.2},     # base: low and flat ground
                {'set': 'withered_grass', 'tile_metres': 2.0},  # mid: high ground, noise broken
                {'set': 'coast_sand_01', 'tile_metres': 2.5}])  # steep: slopes
    z = height_at(x, y)        # exact ground height anywhere (Blender axes, metres)

The heights are the WebGPU engine's to the bit (tests/terrain/test_parity.py runs terrain.js under
Node and compares): the same mulberry32 lattice, fbm, clearing blend, plane grid and b-d triangle
split. Axes: three (x, y, z) -> Blender (x, -z, y), so height_at(x, y) == heightAt(x, -y).

The blend weights are baked like the engine's (R base, G mid by height with noise breakup, B steep
by slope) into the colour attribute `eido_blend`. Two ways to shade them:
  shading='film'   (default) every layer's albedo, normal, roughness, AO and height map, height
                   blended so the layers interlock at their own detail, a second offset sample per
                   map so tiles do not repeat, world-scale colour variation and damp patches;
                   full-resolution (Cubic) texture reads near the camera, mipmapped further out
                   so distant ground holds still when the camera moves;
  shading='parity' exactly the WebGPU material: albedo blended by the weights, layer 0's normal
                   map, roughness 0.95, colour 0x6b6f5e when there are no layers.
"""
import math

import bpy
import numpy as np

from . import _noise
from ._nodes import Graph, new_material, principled, output
from ._pbr import load_image, load_set

_ROLE_KEYS = (('map', 'color'), ('normal_map', 'normal'), ('roughness_map', 'roughness'),
              ('ao_map', 'ao'), ('displacement_map', 'displacement'))


def _srgb_to_linear(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _hex_linear(h):
    return (_srgb_to_linear((h >> 16) & 255), _srgb_to_linear((h >> 8) & 255), _srgb_to_linear(h & 255), 1.0)


def _layer(spec, size):
    """A layer spec -> {'imgs': {role: Image}, 'repeat', ...}.

    spec: a texture-set name ('Ground106'), or a dict with any of
      set            texture-set name (all its maps)
      map / normal_map / roughness_map / ao_map / displacement_map   path or bpy Image (override)
      repeat         tiles across the whole terrain (the engine's key; default 12)
      tile_metres    alternative to repeat: one tile spans this many metres
      roughness      multiplier on the roughness map (film) (default 1)
      tint           (r, g, b) linear multiplier on the albedo (film)
      normal_strength  (film; default 1)
    """
    if spec is None:
        spec = {}
    if isinstance(spec, str):
        spec = {'set': spec}
    L = dict(spec)
    imgs = {}
    if L.get('set'):
        imgs.update({k: v for k, v in load_set(L['set']).items() if k != 'name'})
    for key, role in _ROLE_KEYS:
        if L.get(key) is not None:
            imgs[role] = load_image(L[key], role)
    rep = L.get('repeat')
    if rep is None:
        rep = size / float(L['tile_metres']) if L.get('tile_metres') else 12.0
    hstats = _height_stats(imgs['displacement']) if imgs.get('displacement') is not None else None
    return {'imgs': imgs, 'repeat': float(rep), 'tile_m': size / float(rep), 'roughness': float(L.get('roughness', 1.0)),
            'tint': L.get('tint'), 'normal_strength': float(L.get('normal_strength', 1.0)),
            'hstats': hstats, 'label': L.get('set') or L.get('name') or 'layer'}


def _height_stats(img):
    """(mean, std) of a height map, cached on the image: scans sit at different mean heights and
    contrasts (Ground106 ~0.65, withered_grass ~0.36), so the height blend normalises them."""
    if 'eido_hstats' in img:
        return tuple(img['eido_hstats'])
    n = img.size[0] * img.size[1] * img.channels
    if n == 0:
        return (0.5, 0.1)
    px = np.empty(n, dtype=np.float32)
    img.pixels.foreach_get(px)
    v = px.reshape(-1, img.channels)[:, 0]
    st = (float(v.mean()), float(max(v.std(), 1e-3)))
    img['eido_hstats'] = st
    return st


def _parity_material(mat, layers):
    g = Graph(mat.node_tree)
    bsdf = principled(mat)
    bsdf.inputs['Roughness'].default_value = 0.95
    bsdf.inputs['Metallic'].default_value = 0.0
    if not layers:
        bsdf.inputs['Base Color'].default_value = _hex_linear(0x6b6f5e)
        return mat
    uv = g.node('ShaderNodeUVMap', uv_map='UVMap').outputs['UV']
    w = g.separate_rgb(g.attribute('eido_blend').outputs['Color'])
    acc = None
    for i, L in enumerate(layers[:3]):
        img = L['imgs'].get('color')
        if img is None:                  # the engine skips a layer without a map (its weight adds black)
            continue
        c = g.tex(img, g.vmath('SCALE', uv, scale=L['repeat'])).outputs['Color']
        term = g.vmath('SCALE', c, scale=w[i])
        acc = term if acc is None else g.vmath('ADD', acc, term)
    if acc is not None:
        g.set(bsdf.inputs['Base Color'], acc)
    nimg = layers[0]['imgs'].get('normal')
    if nimg is not None:
        nm = g.node('ShaderNodeNormalMap', uv_map='UVMap')
        g.set(nm.inputs['Color'], g.tex(nimg, g.vmath('SCALE', uv, scale=layers[0]['repeat'])).outputs['Color'])
        g.set(bsdf.inputs['Normal'], nm.outputs['Normal'])
    return mat


def _film_material(mat, layers, opt):
    """Every layer's full PBR set, height blended, de-tiled, with world-scale variation."""
    g = Graph(mat.node_tree)
    bsdf = principled(mat)
    bsdf.inputs['Metallic'].default_value = 0.0
    if not layers:
        bsdf.inputs['Base Color'].default_value = _hex_linear(0x6b6f5e)
        bsdf.inputs['Roughness'].default_value = 0.95
        return mat
    uv = g.node('ShaderNodeUVMap', uv_map='UVMap').outputs['UV']
    pos = g.geometry().outputs['Position']
    w = g.separate_rgb(g.attribute('eido_blend').outputs['Color'])
    anti = opt['anti_tile']
    interp = opt['interpolation']
    if interp not in ('Auto', 'Cubic', 'Linear', 'Closest'):
        raise ValueError("material_options interpolation must be 'Auto', 'Cubic', 'Linear' or 'Closest'")
    # 'Auto': EEVEE's 'Cubic' reads the full-resolution image (no mipmaps): sharp at grazing angles
    # near the camera, but further out every pixel covers many texels and the 16-64 TAA samples
    # cannot average them, so the ground crawls when the camera moves. 'Linear' is mipmapped
    # (stable in motion) but isotropic, so it blurs at grazing angles. Hand over from one to the
    # other across detail_distance (metres from the camera).
    far = g.handover(*opt['detail_distance']) if interp == 'Auto' else None

    def tex(img, vec):
        return g.read(img, vec, interp, far)

    per = []
    for i, L in enumerate(layers[:3]):
        rep = L['repeat']
        va = g.vmath('SCALE', uv, scale=rep)
        if anti:
            # a second sample at an unrelated scale and offset, switched in by world-space noise:
            # two lattices that never line up. The switch patches are about a tile across
            # (detile_patch tiles), so a tile seldom repeats inside one patch (measured 11-07 on
            # the meadow's clearing, straight down: 1.7 m windows matching themselves one tile
            # over, 86 % de-tiling off, 11 % with 3.35-tile patches, 8 % with 1.2).
            vb = g.vmath('ADD', g.vmath('SCALE', uv, scale=rep * 0.7071),
                         (0.37 + 0.21 * i, 0.71 - 0.17 * i, 0.0))
            # a narrow switch: a 50/50 mix of two unrelated samples halves the texture's contrast
            # (the ground goes flat and sandy), so each spot shows one sample or the other
            sw = 1.0 / (opt['detile_patch'] * L['tile_m'])
            m = g.smoothstep(0.47, 0.53, g.noise(pos, sw, detail=2.0, w=3.1 * i + 0.5))

        def sample(role, va=va, vb=(vb if anti else None), m=(m if anti else None), L=L):
            img = L['imgs'].get(role)
            if img is None:
                return None
            a = tex(img, va)
            if not anti:
                return a
            return g.mix('RGBA', m, a, tex(img, vb))

        col = sample('color')
        if col is None:
            col = (0.18, 0.17, 0.14, 1.0)
        if L['tint'] is not None:
            col = g.mix('RGBA', 1.0, col, tuple(L['tint'])[:3] + (1.0,), blend='MULTIPLY')
        nrm = sample('normal')
        rough = sample('roughness')
        ao = sample('ao') if opt['ao'] > 0 else None
        disp = sample('displacement')
        per.append(dict(col=col, nrm=nrm, rough=rough, ao=ao, disp=disp, L=L))

    # height blend: a_i = w_i + h_i * k (+ a ragged-edge noise for the upper layers); keep what is
    # within `depth` of the tallest. h_i is each scan's height normalised to mean 0.5, std 0.15, so
    # one scan sitting higher on average does not swallow the others.
    k = opt['height_blend']
    e = opt['edge_noise']
    a = []
    for i, p in enumerate(per):
        h = 0.5
        if p['disp'] is not None and k > 0:
            mean, std = p['L']['hstats'] or (0.5, 0.15)
            h = g.math('MULTIPLY_ADD', g.sub(p['disp'], mean), 0.15 / std, 0.5)
        ai = g.add(w[i], g.mul(h, k)) if k > 0 else w[i]
        if e > 0 and i > 0:
            # the engine's weights are smooth at the vertex scale: break the edges at ~1 m so a
            # patch boundary is ragged ground, not a painted outline
            n = g.noise(pos, 0.85, detail=5.0, roughness=0.62, w=11.1 + 7.3 * i)
            ai = g.add(ai, g.mul(g.sub(n, 0.5), 2.0 * e))
        a.append(ai)
    if len(a) == 1:
        wn = [1.0]
    else:
        ma = a[0]
        for x in a[1:]:
            ma = g.math('MAXIMUM', ma, x)
        ma = g.sub(ma, opt['blend_depth'])
        b = [g.math('MAXIMUM', g.sub(x, ma), 0.0) for x in a]
        s = b[0]
        for x in b[1:]:
            s = g.add(s, x)
        s = g.math('MAXIMUM', s, 1e-5)
        wn = [g.math('DIVIDE', x, s) for x in b]

    def wsum(key, default, as_vec):
        acc = None
        for i, p in enumerate(per):
            v = p[key]
            if v is None:
                v = default
            if as_vec:
                term = g.vmath('SCALE', v, scale=wn[i])
            else:
                term = g.mul(v, wn[i])
            acc = term if acc is None else (g.vmath('ADD', acc, term) if as_vec else g.add(acc, term))
        return acc

    albedo = wsum('col', (0.18, 0.17, 0.14), True)
    nrm = wsum('nrm', (0.5, 0.5, 1.0), True)
    rough_terms = []
    for i, p in enumerate(per):
        r = p['rough'] if p['rough'] is not None else 0.9
        rough_terms.append(g.mul(g.mul(r, p['L']['roughness']), wn[i]))
    rough = rough_terms[0]
    for t in rough_terms[1:]:
        rough = g.add(rough, t)

    # map AO, partly: the scan's own crevices (EEVEE adds the scene's occlusion on top)
    if opt['ao'] > 0 and any(p['ao'] is not None for p in per):
        aov = wsum('ao', 1.0, False)
        aof = g.add(1.0 - opt['ao'], g.mul(aov, opt['ao']))
        albedo = g.vmath('SCALE', albedo, scale=aof)

    # world-scale variation: brightness and a little hue/saturation drift over ~10-20 m
    if opt['macro'] > 0:
        n1 = g.noise(pos, 0.07, detail=4.0, roughness=0.5)
        n2 = g.noise(pos, 0.045, detail=2.0, w=7.7)
        hs = g.node('ShaderNodeHueSaturation')
        g.set(hs.inputs['Hue'], g.map_range(n2, 0.3, 0.7, 0.5 - 0.012, 0.5 + 0.012))
        g.set(hs.inputs['Saturation'], g.map_range(n2, 0.3, 0.7, 0.88, 1.08))
        g.set(hs.inputs['Value'], g.map_range(n1, 0.3, 0.7, 1.0 - opt['macro'], 1.0 + opt['macro']))
        g.set(hs.inputs['Fac'], 1.0)
        g.set(hs.inputs['Color'], albedo)
        albedo = hs.outputs['Color']

    # damp patches: wet soil darkens and loses some roughness
    if opt['damp'] > 0:
        n3 = g.noise(pos, 0.16, detail=3.0, roughness=0.6, w=13.3)
        dm = g.mul(g.smoothstep(0.5, 0.68, n3), opt['damp'])
        albedo = g.vmath('SCALE', albedo, scale=g.sub(1.0, g.mul(dm, 0.38)))
        rough = g.mul(rough, g.sub(1.0, g.mul(dm, 0.32)))

    g.set(bsdf.inputs['Base Color'], albedo)
    g.set(bsdf.inputs['Roughness'], g.math('MINIMUM', g.math('MAXIMUM', rough, 0.02), 1.0))
    bsdf.inputs['Specular IOR Level'].default_value = opt['specular']
    normal = None
    if any(p['nrm'] is not None for p in per):
        nm = g.node('ShaderNodeNormalMap', uv_map='UVMap')
        nm.inputs['Strength'].default_value = max(p['L']['normal_strength'] for p in per)
        g.set(nm.inputs['Color'], nrm)
        normal = nm.outputs['Normal']
    if opt['bump'] > 0 and any(p['disp'] is not None for p in per):
        # the scans' own height as bump on top of their normal maps: shading from the clods'
        # broad shapes, which the normal maps (fine detail) under-state from eye height
        hsum = wsum('disp', 0.5, False)
        bp = g.node('ShaderNodeBump')
        bp.inputs['Strength'].default_value = 1.0
        bp.inputs['Distance'].default_value = opt['bump']
        g.set(bp.inputs['Height'], hsum)
        if normal is not None:
            g.set(bp.inputs['Normal'], normal)
        normal = bp.outputs['Normal']
    if normal is not None:
        g.set(bsdf.inputs['Normal'], normal)
    return mat


def _mesh(name, b):
    n_side = b['X'].shape[0]
    N = n_side * n_side
    co = np.empty((N, 3), dtype=np.float32)
    co[:, 0] = b['X'].ravel()
    co[:, 1] = -b['Z'].ravel()            # three z -> Blender -y
    co[:, 2] = b['H'].ravel()
    tris = b['tris'].astype(np.int32)
    me = bpy.data.meshes.new(name)
    me.vertices.add(N)
    me.vertices.foreach_set('co', co.ravel())
    me.loops.add(tris.size)
    me.loops.foreach_set('vertex_index', tris.ravel())
    me.polygons.add(len(tris))
    me.polygons.foreach_set('loop_start', np.arange(0, tris.size, 3, dtype=np.int32))
    me.update(calc_edges=True)
    uvl = me.uv_layers.new(name='UVMap')
    uvl.uv.foreach_set('vector', b['uv'][tris.ravel()].ravel())
    ca = me.color_attributes.new('eido_blend', 'FLOAT_COLOR', 'POINT')
    rgba = np.ones((N, 4), dtype=np.float32)
    rgba[:, :3] = b['weights']
    ca.data.foreach_set('color', rgba.ravel())
    me.shade_smooth()
    me.validate()
    return me


def make_terrain(size=80, segments=128, amplitude=3, seed=1, layers=(), flat_radius=0, flat_height=0,
                 slope_steep=(0.25, 0.55), high_start=None, octaves=4, frequency=2.5,
                 shading='film', name='terrain', collection=None, material_options=None):
    """Build the terrain object. Returns (obj, height_at).

    The engine's options, snake_cased: size (m), segments, amplitude (m), seed, layers (up to 3:
    base, mid, steep), flat_radius / flat_height (a level clearing at the origin), slope_steep
    ((1 - normal.z) range where the steep layer fades in), high_start (height where the mid layer
    starts; default 0.45 * amplitude), octaves, frequency.

    shading: 'film' (default) or 'parity' (see the module notes). material_options (film): dict of
      anti_tile (True), detile_patch (1.2: the de-tile switch's patches, in tiles), height_blend
      (0.5), blend_depth (0.2), edge_noise (0.3), ao (0.5), macro (0.14), damp (0.5), specular
      (0.5), bump (0 m: off), interpolation ('Auto': full-resolution Cubic near the camera,
      mipmapped Linear past it, handing over across detail_distance (4, 9) metres; 'Cubic' or
      'Linear' everywhere; Cubic alone crawls in motion past ~10 m).

    The object carries obj['eido_terrain'] (the options, so terrain_height_at(obj) can rebuild
    height_at after a reload) and obj['trimesh_collider'] = True (the engine's trimeshCollider).
    """
    layers = list(layers or [])
    if len(layers) > 3:
        print('[make_terrain] %d layers given; the terrain blends 3 (base, mid, steep): the rest are ignored'
              % len(layers))
    hf = _noise.Heightfield(size=size, amplitude=amplitude, seed=seed, flat_radius=flat_radius,
                            flat_height=flat_height, octaves=octaves, frequency=frequency,
                            slope_steep=slope_steep, high_start=high_start)
    b = hf.build(segments, n_layers=len(layers))
    me = _mesh(name, b)
    obj = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(obj)

    Ls = [_layer(s, size) for s in layers[:3]]
    mat = new_material(name + '_ground')
    if shading == 'parity':
        _parity_material(mat, Ls)
    elif shading == 'film':
        # interpolation 'Auto' (measured 11-07, the meadow's edge view, camera turned by half a pixel):
        # EEVEE's 'Linear' is mipmapped without anisotropy (preferences.system.anisotropic_filter
        # does not reach EEVEE renders, even set before the GPU starts), so ground at eye height
        # blurs into sand; 'Cubic' keeps twice the detail at grazing angles but reads mip 0 only, so
        # ground past ~10 m crawls in motion. 'Auto' is Cubic near the camera and Linear past it.
        opt = dict(anti_tile=True, height_blend=0.5, blend_depth=0.2, edge_noise=0.3, ao=0.5,
                   macro=0.14, damp=0.5, specular=0.5, bump=0.0, interpolation='Auto',
                   detail_distance=(4.0, 9.0), detile_patch=1.2)
        opt.update(material_options or {})
        _film_material(mat, Ls, opt)
    else:
        raise ValueError("shading must be 'film' or 'parity'")
    me.materials.append(mat)

    obj['eido_terrain'] = dict(size=float(size), segments=int(segments), amplitude=float(amplitude),
                               seed=float(seed), flat_radius=float(flat_radius), flat_height=float(flat_height),
                               slope_steep=[float(slope_steep[0]), float(slope_steep[1])],
                               high_start=(-1.0 if high_start is None else float(high_start)),
                               has_high_start=high_start is not None, octaves=int(octaves),
                               frequency=float(frequency), shading=shading,
                               layers=[L['label'] for L in Ls])
    obj['trimesh_collider'] = True
    return obj, _height_fn(hf)


def _height_fn(hf):
    def height_at(x, y):
        """Ground height (Blender Z, metres) at Blender (x, y). Scalars or numpy arrays."""
        h = hf.height_three(x, -np.asarray(y, dtype=np.float64))
        return float(h) if np.ndim(h) == 0 else h
    height_at.heightfield = hf
    return height_at


def terrain_height_at(obj):
    """height_at for a terrain made by make_terrain (e.g. after reopening the .blend)."""
    p = obj.get('eido_terrain')
    if p is None:
        raise ValueError("'%s' was not made by make_terrain (no eido_terrain property)" % obj.name)
    hf = _noise.Heightfield(size=p['size'], amplitude=p['amplitude'], seed=p['seed'],
                            flat_radius=p['flat_radius'], flat_height=p['flat_height'],
                            octaves=p['octaves'], frequency=p['frequency'],
                            slope_steep=tuple(p['slope_steep']),
                            high_start=(p['high_start'] if p.get('has_high_start') else None))
    return _height_fn(hf)

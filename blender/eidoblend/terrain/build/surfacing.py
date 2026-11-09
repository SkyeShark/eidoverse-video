"""The terrain's material (design section 7): one node group, eido_terrain_surface, built from a palette
(build/palettes.py). The material is part of the landform: its layers are placed by the masks the processes leave
(slope, rock, talus, snow, vegetation, ...), read as the mesh's eido_<mask> point attributes.

    from eidoblend.terrain.build import surfacing as S
    mat = S.surface_material('alpine')                 # a palette name, 'auto' (+ recipe=), a palette dict
    mat = S.surface_material('desert_sandstone', strata=dict(column='toroweap', faults=[...]))
    S.apply_surface(obj, 'alpine')                     # the same, assigned to obj (replacing its materials)
    S.clay_material()                                  # palette=None: grey clay, albedo 0.18 (the reference rig's)
    S.missing_masks(obj, 'alpine')                     # masks the palette reads that obj does not carry
    S.packed_set('Rock051')                            # a scan packed into two images (below), cached on disk

What the node group does, per pixel:
  1. Each layer's coverage is its weight expression over the masks (palettes.py), clamped to 0..1. Coverage
     composites in order (a layer covers what lies below it), giving exclusive weights that sum to 1.
  2. Those weights are height blended exactly as the old film material did: a_i = w_i + height_i * height_blend
     (+ ragged ~1 m edge noise on the upper layers), keep what is within blend_depth of the tallest, normalise. Every
     scan's height is normalised to mean 0.5 and std 0.15 when it is packed, so a scan that sits higher on average does
     not swallow the others (the old _height_stats, done once at pack time).
  3. Each map is read twice, at an unrelated scale and offset, switched by world noise in patches detile_patch tiles
     across (the old two-sample de-tiling). Albedo and height are 'Auto' filtered: Cubic (the full-resolution image,
     sharp at grazing angles) within detail_distance of the camera, mipmapped Linear beyond, so distant ground holds
     still in motion (the old interpolation='Auto', measured with the shimmer probe, which moved to
     tests/terrain_new/surfacing/). Normal, roughness and AO are mipmapped Linear (half the texture reads; see the
     package report for the cost). With far_scale, the albedo and height are read once more at far_scale x the tile,
     blended in over far_distance, so slopes hundreds of metres off do not show a fine regular knit of repeats.
  4. Planar layers read world XY and their normal maps in that tangent frame (built in the shader from the shading
     normal, so no UV map is needed). Box layers read planar on gentle ground and the Image Texture node's Box
     projection with blend (a cheap triplanar) on faces steeper than about 40 degrees, blended over 37-47 degrees;
     their normal comes from the bump of their own height map, which is right in any projection. Optional per layer:
     streaks (vertical stains or varnish on walls) and ripples (wind ripples on sand, as bump).
  5. A layer's albedo is rescaled from its scan's own mean to the palette's colour, channel by channel, so the scan's
     detail stays and its colour cast goes. A strata layer is recoloured by the rock column instead: a 1D image of
     the column (formations and their beds, colour and roughness, 2 pixels per metre) read at the stratigraphic
     height zs (the eido_strata attribute, or Position.z with a dip), offset across faults and warped by world noise,
     so bands are level, continuous across ridges and sit on the benches.
  6. The old material's macro variation (brightness, hue and saturation drift, now with landscape octaves at hundreds
     and thousands of metres), damp patches (plus damp_where, e.g. along wet ground) and partial map AO.

Images per material: two per layer and one for the strata. EEVEE here allows 30 images in one material (32 samplers,
2 kept by the engine: 'uses too many samplers (34/32)' at 32 images, measured 11-08). A Cubic and a Linear read of one
image share its sampler, so 'Auto' costs nothing there; packing five maps into two is what makes six layers fit.

The packed images (cache: eidoverse/assets/cache/terrain/surface_sets/<set>_v<PACK_VERSION>/):
  albedo_height.png    RGB the scan's albedo (sRGB), A its height normalised to mean 0.5 std 0.15
  normal_rough_ao.png  R, G the OpenGL normal's x, y (z is rebuilt), B roughness, A ambient occlusion (Non-Color)
  stats.json           the scan's mean linear albedo (for the colour rescale), mean roughness, its height mean/std
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

import bpy
import numpy as np

from .. import _pbr
from .._nodes import Graph, new_material, principled
from . import palettes as P

PACK_VERSION = 1
MAX_IMAGES = 28                       # EEVEE's 30 per material (measured), less two spare
GROUP_NAME = 'eido_terrain_surface'
CLAY_ALBEDO = 0.18                    # the reference rig's grey clay (photographic mid grey, matte)
STRATA_PX_PER_M = 2.0                 # the strata image's resolution: 0.5 m per pixel


def cache_root():
    """eidoverse/assets/cache/terrain/surface_sets/ of this checkout (git-ignored, like the terrain cache)."""
    return Path(__file__).resolve().parents[4] / 'eidoverse' / 'assets' / 'cache' / 'terrain' / 'surface_sets'


# ------------------------------------------------------------------------------------------ packed scans ---

def _read_pixels(path, colorspace):
    """(H, W, C) float32 pixels of an image file and whether Blender holds it as float. Byte images come back as their
    stored values / 255 (an sRGB colour map stays sRGB-encoded); float images as linear values."""
    img = bpy.data.images.load(str(path), check_existing=False)
    try:
        img.colorspace_settings.name = colorspace
    except TypeError:
        pass
    w, h = img.size
    c = img.channels
    px = np.empty(w * h * c, np.float32)
    img.pixels.foreach_get(px)
    is_float = bool(img.is_float)
    bpy.data.images.remove(img)
    return px.reshape(h, w, c), is_float


def _fit(a, h, w):
    """Nearest-neighbour resample of an (H', W', C) array to (h, w, C) (maps of one set seldom differ in size)."""
    if a.shape[0] == h and a.shape[1] == w:
        return a
    ri = (np.arange(h) * a.shape[0] // h).clip(0, a.shape[0] - 1)
    ci = (np.arange(w) * a.shape[1] // w).clip(0, a.shape[1] - 1)
    return a[ri][:, ci]


def _write_png(arr, path):
    """Write an (H, W, 4) array of 0..1 floats as an 8-bit RGBA PNG through Blender (the values go to bytes as they
    are: no colour transform on a byte image)."""
    h, w, _ = arr.shape
    img = bpy.data.images.new('eido_pack_tmp', w, h, alpha=True, float_buffer=False)
    try:
        img.alpha_mode = 'CHANNEL_PACKED'
    except TypeError:
        pass
    img.pixels.foreach_set(np.clip(arr, 0.0, 1.0).astype(np.float32).ravel())
    img.filepath_raw = str(path)
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)


def pack_set(name, prefer='2k', force=False, log=print):
    """Pack a scan set into albedo_height.png and normal_rough_ao.png (+ stats.json) in the cache, once. Returns the
    folder. Missing maps fall back: roughness from the ARM map's G, else 0.8; AO from ARM's R, else 1; a missing
    height map packs as a flat 0.5 (the layer then height-blends by weight only)."""
    src = _pbr.find_set(name, prefer)
    d = cache_root() / f"{src['name']}_v{PACK_VERSION}"
    a_path, b_path, s_path = d / 'albedo_height.png', d / 'normal_rough_ao.png', d / 'stats.json'
    newest = max(Path(src[r]).stat().st_mtime for r in ('color', 'normal', 'roughness', 'ao', 'displacement', 'arm')
                 if r in src)
    if not force and a_path.exists() and b_path.exists() and s_path.exists() \
            and min(a_path.stat().st_mtime, b_path.stat().st_mtime) >= newest:
        return d
    t0 = time.time()
    d.mkdir(parents=True, exist_ok=True)
    if 'color' not in src:
        raise FileNotFoundError(f"texture set {src['name']} has no colour map in {src['dir']}")
    col, col_float = _read_pixels(src['color'], 'sRGB')
    H, W = col.shape[:2]
    rgb = col[..., :3]
    if col_float:                                        # a float colour map loads linear: store it sRGB-encoded
        rgb = P.linear_to_srgb(rgb).astype(np.float32)
    arm = None
    if 'arm' in src:
        arm = _fit(_read_pixels(src['arm'], 'Non-Color')[0], H, W)
    if 'normal' in src:
        nrm = _fit(_read_pixels(src['normal'], 'Non-Color')[0], H, W)[..., :2]
    else:
        nrm = np.full((H, W, 2), 0.5, np.float32)
    if 'roughness' in src:
        rough = _fit(_read_pixels(src['roughness'], 'Non-Color')[0], H, W)[..., 0]
    elif arm is not None:
        rough = arm[..., 1]
    else:
        rough = np.full((H, W), 0.8, np.float32)
    if 'ao' in src:
        ao = _fit(_read_pixels(src['ao'], 'Non-Color')[0], H, W)[..., 0]
    elif arm is not None:
        ao = arm[..., 0]
    else:
        ao = np.ones((H, W), np.float32)
    if 'displacement' in src:
        disp = _fit(_read_pixels(src['displacement'], 'Non-Color')[0], H, W)[..., 0].astype(np.float64)
        hm, hs = float(disp.mean()), float(max(disp.std(), 1e-3))
        hn = 0.5 + 0.15 * (disp - hm) / hs
    else:
        hm, hs = 0.5, 0.0
        hn = np.full((H, W), 0.5)
    A = np.concatenate([rgb, hn[..., None].astype(np.float32)], -1)
    B = np.concatenate([nrm, rough[..., None], ao[..., None]], -1)
    _write_png(A, a_path)
    _write_png(B, b_path)
    lin = P.srgb_to_linear(np.clip(rgb, 0, 1)).reshape(-1, 3)
    stats = dict(version=PACK_VERSION, set=src['name'], size=[W, H],
                 mean_albedo_linear=[float(v) for v in lin.mean(0)],
                 mean_albedo_srgb='#%02x%02x%02x' % tuple(int(round(v * 255)) for v in P.linear_to_srgb(lin.mean(0))),
                 mean_roughness=float(rough.mean()), mean_ao=float(ao.mean()),
                 height_mean=hm, height_std=hs, has_height='displacement' in src, has_normal='normal' in src,
                 sources={k: str(src[k]) for k in ('color', 'normal', 'roughness', 'ao', 'displacement', 'arm')
                          if k in src})
    s_path.write_text(json.dumps(stats, indent=1))
    if log:
        log(f"[surfacing] packed {src['name']} ({W}x{H}) in {time.time() - t0:.1f} s -> {d}")
    return d


def _load_image(path, colorspace):
    img = bpy.data.images.load(str(path), check_existing=True)
    try:
        if img.colorspace_settings.name != colorspace:
            img.colorspace_settings.name = colorspace
    except TypeError:
        pass
    try:
        img.alpha_mode = 'CHANNEL_PACKED'
    except TypeError:
        pass
    return img


def packed_set(name, prefer='2k', log=print):
    """{'albedo': Image (sRGB; alpha = normalised height), 'nrao': Image (Non-Color), 'stats': dict, 'name'} for a
    scan set, packing it first if the cache lacks it."""
    d = pack_set(name, prefer, log=log)
    stats = json.loads((d / 'stats.json').read_text())
    return dict(albedo=_load_image(d / 'albedo_height.png', 'sRGB'),
                nrao=_load_image(d / 'normal_rough_ao.png', 'Non-Color'), stats=stats, name=stats['set'])


# ------------------------------------------------------------------------------------------- the strata ---

def strata_image(column, name='eido_strata', px_per_m=STRATA_PX_PER_M, seed=0):
    """(Image, z_lo, z_hi): the column as a 1-pixel-tall float image, linear RGB the bed colour and A its roughness
    multiplier, z_lo..z_hi metres across its width. Formations are split into beds of random thickness around their
    mean bed thickness, each with a little colour jitter, so a wall shows bedding. Deterministic per column."""
    layers = P.column_layers(column)
    z_lo, z_hi = layers[0][1], layers[-1][2]
    W = int(min(16384, max(64, math.ceil((z_hi - z_lo) * px_per_m))))
    zc = z_lo + (np.arange(W) + 0.5) / W * (z_hi - z_lo)
    rgba = np.zeros((W, 4), np.float64)
    rng = np.random.default_rng(seed + sum(ord(c) for c in ''.join(L[0] for L in layers)) % 9973)
    for _nm, b, t, col, rough, bed, jit in layers:
        z = b
        while z < t:
            th = max(0.3, float(rng.exponential(bed)))
            sel = (zc >= z) & (zc < min(z + th, t))
            v = math.exp(jit * float(rng.standard_normal()))
            hue = 1.0 + 0.3 * jit * rng.standard_normal(3)
            if isinstance(col, list):                    # a bed colour drawn by weight (the Brule's pinks and reds)
                w = np.array([c[1] for c in col])
                base = col[int(rng.choice(len(col), p=w / w.sum()))][0]
            else:
                base = col
            rgba[sel, :3] = np.clip(base * v * hue, 0.0, 0.95)
            rgba[sel, 3] = rough * (1.0 + 0.4 * jit * float(rng.standard_normal()))
            z += th
    img = bpy.data.images.get(name)
    if img is not None and tuple(img.size) == (W, 1):
        bpy.data.images.remove(img)
        img = None
    img = bpy.data.images.new(name, W, 1, alpha=True, float_buffer=True)
    try:
        img.colorspace_settings.name = 'Non-Color'
    except TypeError:
        pass
    img.pixels.foreach_set(rgba.astype(np.float32).ravel())
    try:
        img.pack()                                       # so a saved .blend keeps it
    except RuntimeError:
        pass
    return img, float(z_lo), float(z_hi)


# --------------------------------------------------------------------------- expressions compiled to nodes ---

class _Compiler:
    """Mask expressions (palettes.parse trees) -> node sockets or folded floats, sharing attribute and noise nodes."""

    def __init__(self, g, pos):
        self.g = g
        self.pos = pos
        self.attrs = {}
        self.noises = {}

    def attr(self, name):
        if name not in self.attrs:
            self.attrs[name] = self.g.attribute('eido_' + name).outputs['Fac']
        return self.attrs[name]

    def noise(self, scale_m, seed=0):
        key = (float(scale_m), int(seed))
        if key not in self.noises:
            n = self.g.noise(self.pos, 1.0 / max(float(scale_m), 1e-6), detail=2.0, roughness=0.5,
                             w=0.37 + 7.31 * int(seed) + 0.013 * float(scale_m))
            # the shader noise's spread is narrow (mostly 0.3-0.7): stretch it to about 0..1
            self.noises[key] = self.g.math('MULTIPLY_ADD', self.g.sub(n, 0.5), 2.5, 0.5, clamp=True)
        return self.noises[key]

    def cells(self, scale_m, seed=0):
        """A random value per cell of a world-space (x, y) Voronoi partition, cells about scale_m across."""
        key = ('cells', float(scale_m), int(seed))
        if key not in self.noises:
            v = self.g.node('ShaderNodeTexVoronoi', voronoi_dimensions='2D', feature='F1')
            off = self.g.vmath('ADD', self.pos, (97.13 * int(seed), -61.7 * int(seed), 0.0))
            self.g.set(v.inputs['Vector'], off)
            self.g.set(v.inputs['Scale'], 1.0 / max(float(scale_m), 1e-6))
            self.g.set(v.inputs['Randomness'], 1.0)
            self.noises[key] = self.g.separate_rgb(v.outputs['Color'])[0]
        return self.noises[key]

    def _bin(self, op, a, b):
        if isinstance(a, float) and isinstance(b, float):
            return {'+': a + b, '-': a - b, '*': a * b, '/': a / (b if abs(b) > 1e-12 else 1e-12)}[op]
        if op == '*' and (a == 1.0 or b == 1.0):
            return b if a == 1.0 else a
        if op == '+' and (a == 0.0 or b == 0.0):
            return b if a == 0.0 else a
        return self.g.math({'+': 'ADD', '-': 'SUBTRACT', '*': 'MULTIPLY', '/': 'DIVIDE'}[op], a, b)

    def __call__(self, t):
        k = t[0]
        if k == 'num':
            return float(t[1])
        if k == 'mask':
            return self.attr(t[1])
        if k == 'neg':
            a = self(t[1])
            return -a if isinstance(a, float) else self.g.mul(a, -1.0)
        if k == 'op':
            return self._bin(t[1], self(t[2]), self(t[3]))
        f, args = t[1], t[2]
        if f == 'noise':
            return self.noise(args[0][1], int(args[1][1]) if len(args) > 1 else 0)
        if f == 'cells':
            return self.cells(args[0][1], int(args[1][1]) if len(args) > 1 else 0)
        v = [self(a) for a in args]
        g = self.g
        if f == 'smoothstep':
            if all(isinstance(e, float) for e in v):
                return float(P._smooth(v[0], v[1], v[2]))
            return g.smoothstep(v[0], v[1], v[2])
        if f in ('min', 'max'):
            if all(isinstance(e, float) for e in v):
                return float(min(v) if f == 'min' else max(v))
            out = v[0]
            for e in v[1:]:
                out = g.math('MINIMUM' if f == 'min' else 'MAXIMUM', out, e)
            return out
        if f == 'clamp':
            return g.math('MAXIMUM', g.math('MINIMUM', v[0], v[2]), v[1])
        if f == 'abs':
            return abs(v[0]) if isinstance(v[0], float) else g.math('ABSOLUTE', v[0])
        if f == 'pow':
            return g.math('POWER', g.math('MAXIMUM', v[0], 0.0), v[1])
        if f == 'mix':
            return g.add(v[0], g.mul(g.sub(v[1], v[0]), v[2]))
        raise P.ExprError(f)


# ------------------------------------------------------------------------------------------ the node group ---

def _clamp01(g, x):
    return max(0.0, min(1.0, x)) if isinstance(x, float) else g.math('MAXIMUM', g.math('MINIMUM', x, 1.0), 0.0)


def _one_minus(g, x):
    return 1.0 - x if isinstance(x, float) else g.sub(1.0, x)


def _mul(g, a, b):
    if isinstance(a, float) and isinstance(b, float):
        return a * b
    if a == 1.0:
        return b
    if b == 1.0:
        return a
    if a == 0.0 or b == 0.0:
        return 0.0
    return g.mul(a, b)


class _Reader:
    """Image reads with the old material's filtering and de-tiling: each read is two Image Texture nodes (Cubic near,
    Linear far, mixed by the handover) and, with anti_tile, a second sample at 0.7071 x the scale and an offset,
    switched in by world noise. Returns (Color socket, Alpha socket)."""

    def __init__(self, g, opt, far):
        self.g, self.opt, self.far = g, opt, far
        self.interp = opt['interpolation']

    def _tex(self, img, vec, interp, box):
        n = self.g.node('ShaderNodeTexImage', interpolation=interp, extension='REPEAT')
        n.image = img
        if box:
            n.projection = 'BOX'
            n.projection_blend = 0.3
        self.g.set(n.inputs['Vector'], vec)
        return n.outputs['Color'], n.outputs['Alpha']

    def one(self, img, vec, box):
        if self.interp != 'Auto':
            return self._tex(img, vec, self.interp, box)
        c1, a1 = self._tex(img, vec, 'Cubic', box)
        c2, a2 = self._tex(img, vec, 'Linear', box)
        g = self.g
        return g.mix('RGBA', self.far, c1, c2), g.mix('FLOAT', self.far, a1, a2)

    def read(self, img, va, vb, m, box):
        ca, aa = self.one(img, va, box)
        if vb is None:
            return ca, aa
        cb, ab = self.one(img, vb, box)
        g = self.g
        return g.mix('RGBA', m, ca, cb), g.mix('FLOAT', m, aa, ab)


def _strata_zs(g, comp, st, coords):
    """The stratigraphic height socket: eido_strata (source 'attribute') or object z with a dip (source 'position'),
    plus z_offset_m, fault throws and world-noise warps."""
    x, y, z = g.separate_xyz(coords)
    if st.get('source', 'attribute') == 'attribute':
        zs = comp.attr('strata')
    else:
        dip = math.tan(math.radians(float(st.get('dip_deg', 0.0))))
        az = math.radians(float(st.get('dip_azimuth_deg', st.get('azimuth_deg', 0.0))))
        zs = z
        if dip:
            zs = g.sub(zs, g.mul(g.add(g.mul(x, math.cos(az)), g.mul(y, math.sin(az))), dip))
    off = float(st.get('z_offset_m', 0.0))
    if off:
        zs = g.add(zs, off)
    for f in st.get('faults', []) or []:
        s = math.radians(float(f.get('strike_deg', 0.0)))
        nx, ny = math.cos(s), -math.sin(s)               # a normal of the strike direction (sin s, cos s)
        want = {'west': (-1, 0), 'east': (1, 0), 'north': (0, 1), 'south': (0, -1)}[f.get('down', 'west')]
        if nx * want[0] + ny * want[1] < 0:
            nx, ny = -nx, -ny                            # the normal points to the downthrown side
        dist = g.add(g.mul(g.sub(x, float(f.get('x', 0.0))), nx), g.mul(g.sub(y, float(f.get('y', 0.0))), ny))
        w = max(float(f.get('width_m', 50.0)), 1e-3)
        zs = g.add(zs, g.mul(g.smoothstep(-0.5 * w, 0.5 * w, dist), float(f.get('throw_m', 0.0))))
    for k, (scale, amp) in enumerate(st.get('warp', []) or []):
        n = g.noise(coords, 1.0 / float(scale), detail=2.0, roughness=0.5, w=41.3 + 3.7 * k)
        zs = g.add(zs, g.mul(g.sub(n, 0.5), 2.0 * float(amp)))
    return zs


def _macro(g, coords, albedo, octaves):
    """The old material's world-scale variation, generalised to octaves: brightness (value), hue and saturation
    drift, each octave its own noise `scale_m` metres across."""
    if not octaves:
        return albedo
    val, hue, sat = None, None, None
    for k, o in enumerate(octaves):
        n = g.noise(coords, 1.0 / float(o['scale_m']), detail=float(o.get('detail', 2.0)),
                    roughness=float(o.get('roughness', 0.5)), w=o.get('w', 1.7 + 2.9 * k))
        if o.get('value'):
            v = g.map_range(n, 0.3, 0.7, 1.0 - o['value'], 1.0 + o['value'])
            val = v if val is None else g.mul(val, v)
        if o.get('hue'):
            h = g.map_range(n, 0.3, 0.7, -o['hue'], o['hue'])
            hue = h if hue is None else g.add(hue, h)
        if o.get('saturation'):
            lo, hi = o['saturation']
            s = g.map_range(n, 0.3, 0.7, lo, hi)
            sat = s if sat is None else g.mul(sat, s)
    hs = g.node('ShaderNodeHueSaturation')
    g.set(hs.inputs['Hue'], 0.5 if hue is None else g.add(hue, 0.5))
    g.set(hs.inputs['Saturation'], 1.0 if sat is None else sat)
    g.set(hs.inputs['Value'], 1.0 if val is None else val)
    g.set(hs.inputs['Fac'], 1.0)
    g.set(hs.inputs['Color'], albedo)
    return hs.outputs['Color']


def _ripples(g, coords, rp, i):
    """Wind ripples as a bump height (metres): an asymmetric sawtooth across the wind (a gentle stoss side rising over
    80 % of the wavelength, a steep lee over 20 %), its crests bent by noise at 6 and 40 wavelengths, faded out between
    fade_m (they alias past a few tens of metres). rp: dict(wavelength_m=0.12, height_m=0.012, azimuth_deg (the
    compass bearing the wind blows toward), fade_m=(12, 35))."""
    wl = float(rp.get('wavelength_m', 0.12))
    hgt = float(rp.get('height_m', 0.012))
    az = math.radians(float(rp.get('azimuth_deg', 45.0)))
    f0, f1 = rp.get('fade_m', (12.0, 35.0))
    x, y, _z = g.separate_xyz(coords)
    s = g.math('MULTIPLY_ADD', x, math.sin(az) / wl, g.mul(y, math.cos(az) / wl))
    d1 = g.mul(g.sub(g.noise(coords, 1.0 / (6.0 * wl), detail=2.0, w=23.1 + i), 0.5), 1.6)
    d2 = g.mul(g.sub(g.noise(coords, 1.0 / (40.0 * wl), detail=2.0, w=29.3 + i), 0.5), 5.0)
    f = g.math('FRACT', g.add(s, g.add(d1, d2)))
    prof = g.math('MINIMUM', g.mul(f, 1.0 / 0.8), g.mul(g.sub(1.0, f), 1.0 / 0.2))
    fade = g.sub(1.0, g.smoothstep(float(f0), float(f1), g.view_distance()))
    return g.mul(g.mul(g.sub(prof, 0.5), hgt), fade)


def _xy_tangent_normal(g, nx, ny, N):
    """World normal from a tangent-space (nx, ny) in the planar frame: T = X made perpendicular to N, B = N x T,
    n = normalize(T nx + B ny + N sqrt(1 - nx^2 - ny^2))."""
    dot = g.vmath('DOT_PRODUCT', N, (1.0, 0.0, 0.0))
    T = g.vmath('NORMALIZE', g.vmath('SUBTRACT', (1.0, 0.0, 0.0), g.vmath('SCALE', N, scale=dot)))
    B = g.vmath('CROSS_PRODUCT', N, T)
    nz = g.math('SQRT', g.math('MAXIMUM', g.sub(g.sub(1.0, g.mul(nx, nx)), g.mul(ny, ny)), 0.0))
    v = g.vmath('ADD', g.vmath('ADD', g.vmath('SCALE', T, scale=nx), g.vmath('SCALE', B, scale=ny)),
                g.vmath('SCALE', N, scale=nz))
    return g.vmath('NORMALIZE', v)


def surface_group(palette, name=GROUP_NAME, prefer='2k', log=print):
    """The eido_terrain_surface shader node group of a palette (palettes.get resolves it). Outputs: BSDF, Base Color,
    Roughness, Normal. The group carries the palette name and its layers' sets as custom properties."""
    pal = P.get(palette) if not (isinstance(palette, dict) and 'options' in palette) else palette
    opt = pal['options']
    layers = pal['layers']
    sets = [packed_set(L['set'], prefer, log=log) for L in layers]
    ng = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    ng.interface.new_socket('BSDF', in_out='OUTPUT', socket_type='NodeSocketShader')
    ng.interface.new_socket('Base Color', in_out='OUTPUT', socket_type='NodeSocketColor')
    ng.interface.new_socket('Roughness', in_out='OUTPUT', socket_type='NodeSocketFloat')
    ng.interface.new_socket('Normal', in_out='OUTPUT', socket_type='NodeSocketVector')
    g = Graph(ng)
    gout = g.node('NodeGroupOutput')
    coords = g.node('ShaderNodeTexCoord').outputs['Object']        # metres: the terrain keeps an identity transform
    N = g.geometry().outputs['Normal']
    comp = _Compiler(g, coords)
    interp = opt['interpolation']
    if interp not in ('Auto', 'Cubic', 'Linear', 'Closest'):
        raise ValueError("options interpolation must be 'Auto', 'Cubic', 'Linear' or 'Closest'")
    far = g.handover(*opt['detail_distance']) if interp == 'Auto' else None
    rd = _Reader(g, opt, far)
    images = set()
    # the far scale: past far_distance the albedo and height are read again at far_scale x the tile, so a slope a few
    # hundred metres off shows the scan's patterns at a larger size instead of a fine regular knit of repeats
    far_k = float(opt.get('far_scale', 1.0) or 1.0)
    fd = g.smoothstep(*opt['far_distance'], g.view_distance()) if far_k > 1.0 else None
    rd_lin = _Reader(g, dict(opt, interpolation='Linear'), None)      # mipmapped only (and the far reads)
    rd_far = rd_lin
    # box layers: planar (with 'Auto' filtering) on gentle ground, the Box projection (mipmapped) on steep faces, so
    # rock seen at a grazing angle near the camera stays sharp (design 7: planar on gentle ground, box above ~35-45
    # degrees). The planar read turns the coordinates to (-y, x), the frame Blender's Box projection gives an up-facing
    # surface (uv = (1 - y, x)), so the two agree where they blend.
    steep = None
    if any(L['projection'] == 'box' for L in layers):
        steep = g.smoothstep(0.80, 0.68, g.separate_xyz(N)[2])
        cx, cy, cz = g.separate_xyz(coords)
        coords_rot = g.combine_xyz(g.mul(cy, -1.0), cx, cz)

    # the strata band (one read, shared by every strata layer)
    band, band_rough = None, None
    if any(L['strata'] for L in layers):
        st = pal['strata']
        img, z_lo, z_hi = strata_image(st['column'], name=f"eido_strata_{pal['name']}")
        images.add(img.name)
        zs = _strata_zs(g, comp, st, coords)
        u = g.math('MULTIPLY_ADD', zs, 1.0 / (z_hi - z_lo), -z_lo / (z_hi - z_lo))
        n = g.node('ShaderNodeTexImage', interpolation='Linear', extension='EXTEND')
        n.image = img
        g.set(n.inputs['Vector'], g.combine_xyz(u, 0.5, 0.0))
        band, band_rough = n.outputs['Color'], n.outputs['Alpha']

    # per layer: coverage, then the reads
    per = []
    for i, (L, S) in enumerate(zip(layers, sets)):
        cov = _clamp01(g, comp(P.parse(L['weight'])))
        box = L['projection'] == 'box'
        tile = float(L['tile_m'])
        va = g.vmath('SCALE', coords, scale=1.0 / tile)
        vb = m = None
        if opt['anti_tile']:
            # a second sample at an unrelated scale and offset, switched in by world noise in patches detile_patch
            # tiles across: two lattices that never line up (the old film material's, unchanged)
            vb = g.vmath('ADD', g.vmath('SCALE', coords, scale=0.7071 / tile),
                         (0.37 + 0.21 * i, 0.71 - 0.17 * i, 0.13 + 0.11 * i))
            sw = 1.0 / (opt['detile_patch'] * tile)
            m = g.smoothstep(0.47, 0.53, g.noise(coords, sw, detail=2.0, w=3.1 * i + 0.5))
        if not box:
            # albedo and height filtered as the old material ('Auto'); normal, roughness and AO mipmapped
            col, h = rd.read(S['albedo'], va, vb, m, False)
            nrao, ao = rd_lin.read(S['nrao'], va, vb, m, False)
        else:
            ra = g.vmath('SCALE', coords_rot, scale=1.0 / tile)
            rb = None
            if vb is not None:                           # the same second sample, turned like ra
                bx, by, bz = g.separate_xyz(vb)
                rb = g.combine_xyz(g.mul(by, -1.0), bx, bz)
            cp, hp = rd.read(S['albedo'], ra, rb, m, False)
            cbx, hbx = rd_lin.read(S['albedo'], va, vb, m, True)
            col, h = g.mix('RGBA', steep, cp, cbx), g.mix('FLOAT', steep, hp, hbx)
            nrao, ao = rd_lin.read(S['nrao'], va, vb, m, True)
        images.update((S['albedo'].name, S['nrao'].name))
        h_bump = h
        if fd is not None:
            tf = tile * far_k
            fa = g.vmath('SCALE', coords, scale=1.0 / tf)
            colf, hf = rd_far.read(S['albedo'], fa, None, None, box)
            fc = float(L.get('far_contrast', opt.get('far_contrast', 0.65)))
            if fc != 1.0:                                # the larger pattern, toned down around the scan's mean
                mean_lin = [float(v) for v in S['stats']['mean_albedo_linear']]
                colf = g.vmath('ADD', g.vmath('SCALE', colf, scale=fc), tuple((1.0 - fc) * v for v in mean_lin))
            col = g.mix('RGBA', fd, col, colf)
            # the far height blends and bumps at its own (larger) scale
            h_bump = g.mix('FLOAT', fd, g.sub(h, 0.5), g.mul(g.sub(hf, 0.5), float(opt.get('far_bump', 0.5)) * far_k))
            h = g.mix('FLOAT', fd, h, hf)
        else:
            h_bump = g.sub(h, 0.5)
        nr, ng_, rough = g.separate_rgb(nrao)
        mean = np.maximum(np.array(S['stats']['mean_albedo_linear'], np.float64), 1e-4)
        contrast = float(L.get('contrast', 1.0))
        own = tuple(P.hex_linear(L['colour'])) if L['colour'] else None
        smix = float(L['strata']) if L['strata'] is not True else 1.0
        if smix > 0 and band is not None:
            # the rock column's colour at this height; a float `strata` mixes it with the layer's own colour (talus:
            # the debris of the beds above, mostly their colour)
            target = band if (smix >= 1.0 or own is None) else g.mix('RGBA', smix, own + (1.0,), band)
        elif own is not None:
            target = own
        else:
            target = None
        if target is not None:
            # rescale from the scan's mean to the target, channel by channel: target * (1 + c (scan / mean - 1))
            rel = g.vmath('MULTIPLY', col, tuple(1.0 / mean))
            if contrast != 1.0:
                rel = g.vmath('ADD', g.vmath('SCALE', rel, scale=contrast), (1.0 - contrast,) * 3)
            col = g.vmath('MULTIPLY', rel, target)
        if L['tint'] is not None:
            col = g.vmath('MULTIPLY', col, tuple(L['tint'])[:3])
        pt = L.get('patches')
        if pt and L['colour']:
            # a second tone in world-noise patches scale_m across (drier grass, a different soil): what breaks a
            # lawn-like scan up at the 3-10 m scale it mipmaps away at, from eye height
            ratio = np.array(P.hex_linear(pt['colour'])) / np.maximum(np.array(P.hex_linear(L['colour'])), 1e-4)
            pm = g.mul(g.smoothstep(0.42, 0.62, g.noise(coords, 1.0 / float(pt.get('scale_m', 6.0)), detail=3.0,
                                                          roughness=0.55, w=33.7 + 2.3 * i)),
                       float(pt.get('amount', 0.6)))
            col = g.mix('RGBA', pm, col, g.vmath('MULTIPLY', col, tuple(float(v) for v in ratio)))
        if L.get('streaks'):
            # vertical streaks on walls (water stains on limestone, desert varnish on sandstone): a noise `width` metres
            # across and eight times as tall, darkening the albedo by up to `amount`
            width, amount = (float(v) for v in L['streaks'][:2])
            sv = g.vmath('MULTIPLY', coords, (1.0 / width, 1.0 / width, 1.0 / (8.0 * width)))
            sn = g.noise(sv, 1.0, detail=3.0, roughness=0.55, w=19.7 + 3.3 * i)
            dark = g.mul(g.smoothstep(0.45, 0.68, sn), amount)
            col = g.vmath('SCALE', col, scale=g.sub(1.0, dark))
        col = g.vmath('MINIMUM', g.vmath('MAXIMUM', col, (0.0, 0.0, 0.0)), (0.95, 0.95, 0.95))
        r = g.mul(rough, float(L['roughness']))
        if smix > 0 and band_rough is not None:
            r = g.mul(r, band_rough if smix >= 1.0 else g.mix('FLOAT', smix, 1.0, band_rough))
        ripple = _ripples(g, coords, L['ripples'], i) if L.get('ripples') else None
        per.append(dict(L=L, cov=cov, col=col, h=h, hb=h_bump, nx=nr, ny=ng_, rough=r, ao=ao, box=box, ripple=ripple))

    if len(images) > MAX_IMAGES:
        raise ValueError(f'palette {pal["name"]!r} reads {len(images)} images; EEVEE allows about 30 in one '
                         f'material ({MAX_IMAGES} with a margin): use fewer layers')

    # coverage composites in order: e_i = c_i * prod_{j > i} (1 - c_j)
    excl = [None] * len(per)
    rem = 1.0
    for i in range(len(per) - 1, -1, -1):
        excl[i] = _mul(g, per[i]['cov'], rem)
        rem = _mul(g, rem, _one_minus(g, per[i]['cov']))

    # the height blend (the old film material's, unchanged): a_i = w_i + h_i k (+ edge noise), keep what is within
    # blend_depth of the tallest, normalise
    k = float(opt['height_blend'])
    a = []
    for i, p in enumerate(per):
        ai = excl[i]
        if k > 0:
            ai = g.add(ai, g.mul(p['h'], k))
        e = p['L']['edge_noise'] if p['L']['edge_noise'] is not None else float(opt['edge_noise'])
        if e > 0 and i > 0:
            n = g.noise(coords, 0.85, detail=5.0, roughness=0.62, w=11.1 + 7.3 * i)
            ai = g.add(ai, g.mul(g.sub(n, 0.5), 2.0 * e))
        a.append(ai)
    if len(a) == 1:
        wn = [1.0]
    else:
        ma = a[0]
        for x in a[1:]:
            ma = g.math('MAXIMUM', ma, x)
        ma = g.sub(ma, float(opt['blend_depth']))
        b = [g.math('MAXIMUM', g.sub(x, ma), 0.0) for x in a]
        s = b[0]
        for x in b[1:]:
            s = g.add(s, x)
        s = g.math('MAXIMUM', s, 1e-5)
        wn = [g.math('DIVIDE', x, s) for x in b]

    def wsum_vec(vals):
        acc = None
        for v, w in zip(vals, wn):
            term = g.vmath('SCALE', v, scale=w)
            acc = term if acc is None else g.vmath('ADD', acc, term)
        return acc

    def wsum(vals):
        acc = None
        for v, w in zip(vals, wn):
            if v is None:
                continue
            term = _mul(g, v, w)
            acc = term if acc is None else g.add(acc, term)
        return 0.0 if acc is None else acc

    albedo = wsum_vec([p['col'] for p in per])
    rough = wsum([p['rough'] for p in per])
    if opt['ao'] > 0:
        aof = g.add(1.0 - opt['ao'], g.mul(wsum([p['ao'] for p in per]), opt['ao']))
        albedo = g.vmath('SCALE', albedo, scale=aof)
    albedo = _macro(g, coords, albedo, opt.get('macro') or [])
    # damp patches: wet soil darkens and loses some roughness (the old noise patches, plus damp_where)
    if opt['damp'] > 0 or opt.get('damp_where'):
        dm = 0.0
        if opt['damp'] > 0:
            n3 = g.noise(coords, 1.0 / float(opt.get('damp_scale_m', 6.25)), detail=3.0, roughness=0.6, w=13.3)
            dm = g.mul(g.smoothstep(0.5, 0.68, n3), float(opt['damp']))
        if opt.get('damp_where'):
            dw = _clamp01(g, comp(P.parse(opt['damp_where'])))
            dm = dw if isinstance(dm, float) and dm == 0.0 else g.math('MAXIMUM', dm, dw)
        albedo = g.vmath('SCALE', albedo, scale=g.sub(1.0, g.mul(dm, 0.38)))
        rough = g.mul(rough, g.sub(1.0, g.mul(dm, 0.32)))

    # normals: planar layers' maps in the world-XY tangent frame, box layers flat there (their relief is bumped)
    nx = wsum([g.mul(g.sub(g.mul(p['nx'], 2.0), 1.0), float(p['L']['normal'])) if not p['box'] else None for p in per])
    ny = wsum([g.mul(g.sub(g.mul(p['ny'], 2.0), 1.0), float(p['L']['normal'])) if not p['box'] else None for p in per])
    normal = N if (isinstance(nx, float) and isinstance(ny, float)) else _xy_tangent_normal(g, nx, ny, N)
    bump_terms = []
    for p, w in zip(per, wn):
        bm = float(p['L']['bump_m'])
        if bm > 0:
            bump_terms.append(_mul(g, g.mul(p['hb'], bm), w))
        if p['ripple'] is not None:
            bump_terms.append(_mul(g, p['ripple'], w))
    if opt.get('bump', 0.0) > 0:
        bump_terms.append(g.mul(wsum([p['h'] for p in per]), float(opt['bump'])))
    if bump_terms:
        hsum = bump_terms[0]
        for t in bump_terms[1:]:
            hsum = g.add(hsum, t)
        bp = g.node('ShaderNodeBump')
        bp.inputs['Strength'].default_value = 1.0
        bp.inputs['Distance'].default_value = 1.0
        g.set(bp.inputs['Height'], hsum)
        g.set(bp.inputs['Normal'], normal)
        normal = bp.outputs['Normal']

    bsdf = g.node('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Metallic'].default_value = 0.0
    specs = [float(p['L'].get('specular', opt['specular'])) for p in per]
    if len(set(specs)) == 1:
        bsdf.inputs['Specular IOR Level'].default_value = specs[0]
    else:                                                # per-layer specular (grass is not glossy, wet rock is)
        g.set(bsdf.inputs['Specular IOR Level'], wsum(specs))
    albedo = g.vmath('MINIMUM', albedo, (0.95, 0.95, 0.95))
    g.set(bsdf.inputs['Base Color'], albedo)
    rough_c = g.math('MINIMUM', g.math('MAXIMUM', rough, 0.02), 1.0) if not isinstance(rough, float) else rough
    g.set(bsdf.inputs['Roughness'], rough_c)
    g.set(bsdf.inputs['Normal'], normal)
    g.set(gout.inputs['BSDF'], bsdf.outputs['BSDF'])
    dbg = opt.get('debug')
    if dbg:
        # options debug='weights': the top three layers' final weights as red, green, blue; 'albedo': the albedo;
        # both unlit (an Emission), to see what covers each pixel
        em = g.node('ShaderNodeEmission')
        if dbg == 'weights':
            cols = [wn[-1], wn[-2] if len(wn) > 1 else 0.0, wn[-3] if len(wn) > 2 else 0.0]
            g.set(em.inputs['Color'], g.combine_xyz(*cols))
        else:
            g.set(em.inputs['Color'], albedo)
        g.set(gout.inputs['BSDF'], em.outputs['Emission'])
    g.set(gout.inputs['Base Color'], albedo)
    g.set(gout.inputs['Roughness'], rough_c)
    g.set(gout.inputs['Normal'], normal)
    ng['eido_palette'] = pal['name']
    ng['eido_sets'] = [S['name'] for S in sets]
    ng['eido_images'] = len(images)
    return ng


# ------------------------------------------------------------------------------------------ materials ---

def clay_material(name='terrain_clay'):
    """palette=None: grey clay, albedo 0.18, roughness 0.9, no specular (the reference rig's, for shape comparisons)."""
    mat = new_material(name)
    b = principled(mat)
    b.inputs['Base Color'].default_value = (CLAY_ALBEDO, CLAY_ALBEDO, CLAY_ALBEDO, 1.0)
    b.inputs['Roughness'].default_value = 0.9
    b.inputs['Specular IOR Level'].default_value = 0.0
    mat['eido_palette'] = 'clay'
    return mat


def resolve(palette='auto', recipe=None, strata=None, options=None):
    """The filled-in palette dict surface_material builds: palette (name, 'auto', dict) with a strata override (a
    column name, a column, or a strata dict merged over the palette's) and material options merged in."""
    pal = P.get(palette, recipe)
    if strata is not None:
        if isinstance(strata, dict) and ('column' in strata or 'faults' in strata or 'source' in strata):
            pal['strata'] = dict(pal.get('strata') or {}, **strata)
        else:
            pal['strata'] = dict(pal.get('strata') or {'source': 'attribute'}, column=strata)
    if options:
        pal['options'].update(options)
    problems = P.check(pal)
    if problems:
        raise ValueError(f'palette {pal["name"]!r}: ' + '; '.join(problems))
    return pal


def surface_material(palette='auto', recipe=None, strata=None, options=None, name='terrain_ground', prefer='2k',
                     log=print):
    """A material whose surface is the eido_terrain_surface group of a palette; palette=None gives clay_material().

    palette   a name (palettes.names()), 'auto' (the recipe's: palettes.RECIPE_PALETTES), or a palette dict
    recipe    the recipe (name, Recipe or dict), for 'auto'
    strata    the rock column for the palette's strata layers: a STRATA_COLUMNS name, the solver's column list, or a
              dict (column, source 'attribute' | 'position', z_offset_m, dip_deg, dip_azimuth_deg, faults, warp)
    options   material options over the palette's (palettes.DEFAULT_OPTIONS)
    """
    if palette is None:
        return clay_material(name)
    t0 = time.time()
    pal = resolve(palette, recipe, strata, options)
    ng = surface_group(pal, prefer=prefer, log=log)
    mat = new_material(name)
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    grp = nt.nodes.new('ShaderNodeGroup')
    grp.node_tree = ng
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (300, 0)
    nt.links.new(grp.outputs['BSDF'], out.inputs['Surface'])
    mat['eido_palette'] = pal['name']
    mat['eido_masks'] = sorted(P.masks_used(pal))
    if log:
        log(f"[surfacing] {pal['name']}: {len(pal['layers'])} layers, {ng['eido_images']} images, "
            f"{len(ng.nodes)} nodes in {time.time() - t0:.1f} s")
    return mat


def apply_surface(obj, palette='auto', recipe=None, strata=None, options=None, name=None, log=print):
    """surface_material(...) assigned to obj (its material slots replaced). Warns about masks the palette reads that
    obj's mesh lacks (they read as 0). Returns the material."""
    mat = surface_material(palette, recipe, strata, options, name=name or (obj.name + '_ground'), log=log)
    me = obj.data
    me.materials.clear()
    me.materials.append(mat)
    if palette is not None and log:
        miss = missing_masks(obj, mat.get('eido_masks', []))
        if miss:
            log(f"[surfacing] {obj.name}: no attribute for {', '.join(miss)} (read as 0)")
    return mat


def missing_masks(obj, palette_or_names):
    """The masks a palette (a name or dict) or a collection of mask names reads that obj's mesh does not carry as
    eido_<name>. (A material's eido_masks property comes back as an IDProperty array, empty for a palette that reads
    no mask: any iterable of names is taken as names.)"""
    if isinstance(palette_or_names, (str, dict)):
        names = P.masks_used(P.get(palette_or_names))
    else:
        names = {str(n) for n in palette_or_names}
    have = {a.name for a in obj.data.attributes}
    return sorted(n for n in names if 'eido_' + n not in have)


__all__ = ['surface_material', 'surface_group', 'apply_surface', 'clay_material', 'missing_masks', 'packed_set',
           'pack_set', 'strata_image', 'resolve', 'cache_root', 'GROUP_NAME', 'PACK_VERSION', 'MAX_IMAGES']

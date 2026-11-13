"""The terrain's material (design section 7): one node group, eido_terrain_surface, built from a palette
(build/palettes.py). The material is part of the landform: its layers are placed by the masks the processes leave
(slope, curvature, flow, wetness, aspect, talus, deposit, snow, ...), read as the mesh's eido_<mask> point attributes.

    from eidoblend.terrain.build import surfacing as S
    mat = S.surface_material('alpine')                 # a palette name, 'auto' (+ recipe=), a palette dict
    mat = S.surface_material('desert_sandstone', strata=dict(column='toroweap', faults=[...]))
    S.apply_surface(obj, 'alpine')                     # the same, assigned to obj (replacing its materials), with
                                                       # the terrain's own constants (terrain_constants(obj))
    S.clay_material()                                  # palette=None: grey clay, albedo 0.18 (the reference rig's)
    S.missing_masks(obj, 'alpine')                     # masks the palette reads that obj does not carry
    S.pack_masks(obj, mat)                             # a surface_material assigned by hand: its packed masks
    S.packed_set('Rock051')                            # a scan packed into two images (below), cached on disk

What the node group does, per pixel:
  1. Each layer's coverage is its weight expression over the masks and the terrain constants (palettes.py), clamped
     to 0..1. Coverage composites in order (a layer covers what lies below it), giving exclusive weights that sum to 1.
  2. Those weights are height blended exactly as the old film material did: a_i = w_i + height_i * height_blend
     (+ ragged ~1 m edge noise on the upper layers), keep what is within blend_depth of the tallest, normalise. Every
     scan's height is normalised to mean 0.5 and std 0.15 when it is packed, so a scan that sits higher on average does
     not swallow the others (the old _height_stats, done once at pack time).
  3. Each map is read twice and switched by world noise in patches detile_patch tiles across. options detile 'offset'
     is the old two-sample de-tiling (the second read at 0.7071 x the scale and an offset); 'rotate' also turns the
     second read (by a different angle per layer; its normal map turned back with it) and lets the switch follow the
     two reads' heights, so its edge runs along the texture's own features (box layers keep 'offset': turning a box
     projection about z smears its side faces). Albedo and height are 'Auto' filtered: Cubic (the full-resolution
     image, sharp at grazing angles) within detail_distance of the camera, mipmapped Linear beyond, so distant ground
     holds still in motion (the old interpolation='Auto', measured with the shimmer probe, which moved to
     tests/terrain/surfacing/). Normal, roughness and AO are mipmapped Linear. With far_scale, the albedo and height
     are read once more at far_scale x the tile (de-tiled the same way with far_detile), blended in over far_distance,
     so slopes hundreds of metres off do not show a fine regular knit of repeats; with macro_mod, that far read's
     brightness also modulates the near one (the scan as its own macro variation map: no two repeats alike).
  4. Planar layers read world XY and their normal maps in that tangent frame (built in the shader from the shading
     normal, so no UV map is needed). Box layers read planar on gentle ground and the Image Texture node's Box
     projection with blend (a cheap triplanar) on faces steeper than about 40 degrees, blended over 37-47 degrees;
     their normal comes from the bump of their own height map, which is right in any projection. Optional per layer:
     streaks (vertical stains or varnish on steep faces, gathered where the water runs with streaks_where), ripples
     (wind ripples on sand, as bump), patches (second tones at several scales, optionally limited by a mask
     expression), ledges (plants and debris on the ledges of a strata layer's beds) and canopy (a forest seen from
     afar: tree crowns from a world-space Voronoi, one tone per tree, gaps of shadow, a bump for their relief, each
     tree in or out as a whole at the forest's edge, faded in beyond near_m; with clump_m the crowns cluster in clumps
     with shadowed gaps, one tone and relief per clump, whole clumps in or out at the edge: the grain a canopy keeps
     from the air).
  5. A layer's albedo is rescaled from its scan's own mean to the palette's colour, channel by channel, so the scan's
     detail stays and its colour cast goes. A strata layer is recoloured by the rock column instead: a 2D image of the
     column (formations and their beds, colour and roughness, 2 pixels per metre along u; along v, `rows`
     realisations of the beds, read at a world-noise facies coordinate, so beds thin, thicken and change colour along
     a wall) read at the stratigraphic height zs (the eido_strata attribute, or Position.z with a dip), offset across
     faults, warped by world noise at several scales and dragged down the walls by runnels (smear), with darker
     bedding planes (parting). Bands follow the dip and warp of the beds, continuous across ridges, on the benches the
     solver made; a layer's strata_offset_m reads the beds above it (talus is the debris of the cliff over it). With
     the strata's relief_m the beds stand in relief: each bed a hardness (a second image of the same beds), hard beds
     out as ledges and soft ones back in darker recesses, by bump, so a layered wall shows ledge-and-recess striping,
     not painted bands.
  6. The old material's macro variation (brightness, hue and saturation drift, now with landscape octaves from tens to
     thousands of metres), the tone expression (hollows and gorges darker, convex edges paler), damp patches (plus
     damp_where, e.g. along wet ground) and partial map AO.

Mesh attributes per material: EEVEE fails a material that reads 15 of them ('uses too many attributes'), so a palette
reading more than ATTRS_DIRECT masks reads them packed three to a FLOAT_VECTOR point attribute (mask_packs), which
apply_surface writes onto the mesh (pack_masks).

Images per material: two per layer and one for the strata (two with relief). EEVEE here allows 30 images in one
material (32 samplers, 2 kept by the engine: 'uses too many samplers (34/32)' at 32 images, measured 11-08). A Cubic
and a Linear read of one image share its sampler, so 'Auto' costs nothing there, and neither does a second or far
read of the same image;
packing five maps into two is what makes six layers fit.

The packed images (cache: eidoverse/assets/cache/terrain_surface_sets/<set>_v<PACK_VERSION>/, cache_root()):
  albedo_height.png    RGB the scan's albedo (sRGB), A its height normalised to mean 0.5 std 0.15
  normal_rough_ao.png  R, G the OpenGL normal's x, y (z is rebuilt), B roughness, A ambient occlusion (Non-Color)
  stats.json           the scan's mean linear albedo (for the colour rescale), mean roughness, its height mean/std
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
from pathlib import Path

import bpy
import numpy as np

from .. import _pbr
from .._nodes import Graph, new_material, principled
from . import palettes as P

PACK_VERSION = 1
MAX_IMAGES = 28                       # EEVEE's 30 per material (measured), less two spare
# EEVEE compiles a material with a limited number of mesh attributes: at 15 masks the alpine palette failed with
# 'Material ... uses too many attributes' (measured 11-13; the shader reads them all as undefined variables). A
# material reading more masks than ATTRS_DIRECT reads them packed three to a FLOAT_VECTOR point attribute
# (mask_packs, written onto the mesh by pack_masks; apply_surface does it)
ATTRS_DIRECT = 10
GROUP_NAME = 'eido_terrain_surface'
CLAY_ALBEDO = 0.18                    # the reference rig's grey clay (photographic mid grey, matte)
STRATA_PX_PER_M = 2.0                 # the strata image's resolution: 0.5 m per pixel
# options debug='layers': one flat colour per layer (bottom first), the same as tests/terrain/surfacing/layer_map.py
DEBUG_COLOURS = [(0.55, 0.38, 0.25), (0.35, 0.55, 0.2), (0.85, 0.75, 0.45), (0.6, 0.35, 0.6), (0.2, 0.55, 0.85),
                 (0.95, 0.95, 0.95)]
_LUMA = (0.2126, 0.7152, 0.0722)


def cache_root():
    """eidoverse/assets/cache/terrain_surface_sets/ of this checkout (git-ignored, like the terrain cache). Beside the
    terrain cache, not inside it: the terrain cache's prune (core/cache.py, which make_terrain runs on every cache
    miss) takes every folder in its root for a terrain entry, and surface_sets/, all subfolders, counted 0 bytes and
    the oldest, so every miss anywhere deleted the packed scans while other renders were loading them (the magenta
    ground of 11-13 04:05: 'Failed to create GPU texture from Blender image' for all twelve scans)."""
    return Path(__file__).resolve().parents[4] / 'eidoverse' / 'assets' / 'cache' / 'terrain_surface_sets'


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
    are: no colour transform on a byte image). Written to a temporary name and moved into place, so a render in
    another process loading the pack never reads a half-written file."""
    h, w, _ = arr.shape
    path = Path(path)
    tmp = path.with_name(f'{path.stem}.{os.getpid()}.tmp.png')
    img = bpy.data.images.new('eido_pack_tmp', w, h, alpha=True, float_buffer=False)
    try:
        img.alpha_mode = 'CHANNEL_PACKED'
    except TypeError:
        pass
    img.pixels.foreach_set(np.clip(arr, 0.0, 1.0).astype(np.float32).ravel())
    img.filepath_raw = str(tmp)
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)
    os.replace(tmp, path)


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
    s_tmp = s_path.with_name(f'stats.{os.getpid()}.tmp')
    s_tmp.write_text(json.dumps(stats, indent=1))
    os.replace(s_tmp, s_path)
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

def strata_image(column, name='eido_strata', px_per_m=STRATA_PX_PER_M, seed=0, rows=1, parting=0.0, pad_m=0.0,
                 looks=False, repeat=None, relief=False):
    """(Image, z_lo, z_hi): the column as a float image `rows` pixels tall, linear RGB the bed colour and A its
    roughness multiplier, z_lo..z_hi metres across its width. Formations are split into beds of random thickness
    around their mean bed thickness, each with a little colour jitter, so a wall shows bedding; each row draws its own
    beds (the same formations: the material reads the rows at a world-noise facies coordinate, so beds thin, thicken
    and change colour along a wall). parting darkens each bed's lowest half metre (the bedding plane) by about that
    fraction; pad_m runs the end formations on past the column's ends (a wall above the column's top keeps its
    bedding instead of one flat colour); a repeating column (palettes.column_repeats) spans one period and is read
    with REPEAT. looks: colour the formations by palettes.FORMATION_LOOKS. Deterministic per column.

    relief=True also makes `name`_relief, the same beds as relief (the image's custom property eido_relief names it):
    R how far each bed stands out of the wall, 0..1 (each bed a hardness: hard beds stand as ledges, soft ones weather
    back into recesses; a formation's beds lean hard when its roughness multiplier is under 1, the massive limestones
    and sandstones), G 1 on the top metre of a bed that stands out over the bed above it (a ledge, where debris, soil
    and plants lodge). Its beds are the colour image's, pixel for pixel (their own random draws, so the colours
    are the same with or without it)."""
    layers = P.column_layers(column, looks=looks)
    rep = P.column_repeats(column) if repeat is None else bool(repeat)
    z_lo, z_hi = layers[0][1], layers[-1][2]
    if not rep and pad_m > 0:
        z_lo, z_hi = z_lo - pad_m, z_hi + pad_m
        first, last = layers[0], layers[-1]
        if len(layers) == 1:
            layers = [(first[0], z_lo, z_hi) + tuple(first[3:])]
        else:
            layers = [(first[0], z_lo) + tuple(first[2:])] + layers[1:-1] + [tuple(last[:2]) + (z_hi,) + tuple(last[3:])]
    W = int(min(16384, max(64, math.ceil((z_hi - z_lo) * px_per_m))))
    R = max(1, int(rows))
    zc = z_lo + (np.arange(W) + 0.5) / W * (z_hi - z_lo)
    rgba = np.zeros((R, W, 4), np.float64)
    rel = np.zeros((R, W, 4), np.float64) if relief else None
    seed0 = seed + sum(ord(c) for c in ''.join(L[0] for L in layers)) % 9973
    for r in range(R):
        rng = np.random.default_rng(seed0 + 7919 * r)
        hrng = np.random.default_rng(seed0 + 104729 + 7919 * r)  # the beds' hardness: its own draws
        beds = []
        for _nm, b, t, col, rough, bed, jit in layers:
            z = b
            while z < t:
                th = max(0.3, float(rng.exponential(bed)))
                top = min(z + th, t)
                sel = (zc >= z) & (zc < top)
                v = math.exp(jit * float(rng.standard_normal()))
                hue = 1.0 + 0.3 * jit * rng.standard_normal(3)
                if isinstance(col, list):                # a bed colour drawn by weight (the Brule's pinks and buffs)
                    w = np.array([c[1] for c in col])
                    base = col[int(rng.choice(len(col), p=w / w.sum()))][0]
                else:
                    base = col
                rgba[r, sel, :3] = np.clip(base * v * hue, 0.0, 0.95)
                rgba[r, sel, 3] = rough * (1.0 + 0.4 * jit * float(rng.standard_normal()))
                if parting > 0.0 and sel.any():          # the bedding plane: the bed's lowest pixel darker
                    i0 = int(np.argmax(sel))
                    rgba[r, i0, :3] *= max(0.0, 1.0 - parting * float(rng.uniform(0.5, 1.5)))
                if relief:
                    # hard or soft: a massive formation (roughness multiplier under 1) leans hard, and a bed thicker
                    # than its formation's mean stands out more (the thick beds make the ledges)
                    lean = 0.62 if rough < 0.975 else 0.42
                    hard = float(hrng.random()) < lean + 0.25 * math.tanh(th / max(bed, 0.3) - 1.0)
                    hb = float(hrng.uniform(0.7, 1.0)) if hard else float(hrng.uniform(0.0, 0.35))
                    beds.append((sel, hb))
                z = top
        if relief:
            for sel, hb in beds:
                rel[r, sel, 0] = hb
            # a ledge: the top metre of a bed that stands out over the bed above it, read from the image's own runs
            # of one bed (a bed thinner than a pixel draws none, so the bed drawn above is not always the next drawn)
            rr = rel[r, :, 0]
            k = int(round(1.0 * px_per_m))
            for e in np.flatnonzero(np.diff(rr) != 0.0):
                if rr[e] - rr[e + 1] > 0.3:
                    rel[r, max(e - k + 1, 0):e + 1, 1] = 1.0
            rel[r, :, 3] = 1.0
    img = _float_image(name, rgba)
    img['eido_rows'] = R
    img['eido_repeat'] = rep
    if relief:
        ri = _float_image(name + '_relief', rel)
        ri['eido_rows'] = R
        img['eido_relief'] = ri.name
    return img, float(z_lo), float(z_hi)


def _float_image(name, rgba):
    """A packed Non-Color float image from an (H, W, 4) array (replacing one of that name)."""
    img = bpy.data.images.get(name)
    if img is not None:
        bpy.data.images.remove(img)
    img = bpy.data.images.new(name, rgba.shape[1], rgba.shape[0], alpha=True, float_buffer=True)
    try:
        img.colorspace_settings.name = 'Non-Color'
    except TypeError:
        pass
    img.pixels.foreach_set(rgba.astype(np.float32).ravel())
    try:
        img.pack()                                       # so a saved .blend keeps it
    except RuntimeError:
        pass
    return img


# --------------------------------------------------------------------------- expressions compiled to nodes ---

def _noise3(g, pos, scale_m, detail=2.0, roughness=0.5, seed=0.0):
    """A 3D world noise (Fac) with features about scale_m metres across, decorrelated by an offset of the position per
    seed: about half the cost of the 4D noise the old material's nodes use (a W input doubles the lattice corners)."""
    off = (37.7 * seed + 11.3, -51.9 * seed + 7.1, 23.3 * seed - 3.7)
    n = g.node('ShaderNodeTexNoise', noise_dimensions='3D')
    g.set(n.inputs['Vector'], g.vmath('ADD', pos, tuple(o * float(scale_m) for o in off)))
    g.set(n.inputs['Scale'], 1.0 / max(float(scale_m), 1e-6))
    g.set(n.inputs['Detail'], float(detail))
    g.set(n.inputs['Roughness'], float(roughness))
    return n.outputs['Fac']


def mask_packs(names):
    """[(attribute name, [mask, ...]), ...]: a set of mask names, sorted, three to a FLOAT_VECTOR attribute named
    eido_pk<hash>_<k> by the set (two palettes' packs on one mesh never collide)."""
    names = sorted(names)
    h = hashlib.sha1(','.join(names).encode()).hexdigest()[:6]
    return [(f'eido_pk{h}_{k}', names[3 * k:3 * k + 3]) for k in range((len(names) + 2) // 3)]


class _Compiler:
    """Mask expressions (palettes.parse trees) -> node sockets or folded floats, sharing attribute and noise nodes and
    equal sub-expressions (a derived name every layer reads is built once). Terrain constants fold in as numbers.
    noise3: the landscape palettes' noise() as 3D noise (cheaper; the old meadow material keeps its 4D noise).
    flat: noise(), fbm() and cells() read their mean 0.5 (the cheap coverage the bump is weighted by); attrs shares
    another compiler's attribute nodes; packs (mask_packs): the masks read from packed attributes."""

    def __init__(self, g, pos, consts=None, noise3=False, flat=False, attrs=None, packs=None):
        self.g = g
        self.pos = pos
        self.attrs = attrs if attrs is not None else {}
        self.noises = {}
        self.memo = {}
        self.noise3 = bool(noise3)
        self.flat = bool(flat)
        self.consts = dict(P.CONSTANTS)
        self.consts.update(consts or {})
        self.pack_of = {m: (an, c) for an, ms in (packs or []) for c, m in enumerate(ms)}

    def attr(self, name):
        if name not in self.attrs:
            if name in self.pack_of:
                an, c = self.pack_of[name]
                if ('pack', an) not in self.attrs:
                    self.attrs[('pack', an)] = self.g.separate_xyz(self.g.attribute(an).outputs['Vector'])
                self.attrs[name] = self.attrs[('pack', an)][c]
            else:
                self.attrs[name] = self.g.attribute('eido_' + name).outputs['Fac']
        return self.attrs[name]

    def noise(self, scale_m, seed=0):
        if self.flat:
            return 0.5
        key = (float(scale_m), int(seed))
        if key not in self.noises:
            if self.noise3:
                n = _noise3(self.g, self.pos, scale_m, detail=2.0, roughness=0.5, seed=0.37 + 7.31 * int(seed))
            else:
                n = self.g.noise(self.pos, 1.0 / max(float(scale_m), 1e-6), detail=2.0, roughness=0.5,
                                 w=0.37 + 7.31 * int(seed) + 0.013 * float(scale_m))
            # the shader noise's spread is narrow (mostly 0.3-0.7): stretch it to about 0..1
            self.noises[key] = self.g.math('MULTIPLY_ADD', self.g.sub(n, 0.5), 2.5, 0.5, clamp=True)
        return self.noises[key]

    def fbm(self, scale_m, seed=0):
        """Five octaves of 3D world noise (features from scale_m down to a thirtieth of it), about 0..1, one noise
        node per (scale, seed) reading its Fac only (a 4D node's three colour channels cost three noises each)."""
        if self.flat:
            return 0.5
        key = ('fbm', float(scale_m), int(seed))
        if key not in self.noises:
            n = _noise3(self.g, self.pos, scale_m, detail=5.0, roughness=0.6, seed=5.3 + 1.9 * int(seed))
            self.noises[key] = self.g.math('MULTIPLY_ADD', self.g.sub(n, 0.5), 3.0, 0.5, clamp=True)
        return self.noises[key]

    def cells(self, scale_m, seed=0, z_stretch=0.0):
        """A random value per cell of a world-space (x, y) Voronoi partition, cells about scale_m across; with
        z_stretch k > 0 of (x, y, k z) in 3D, so cells run along the contours (palettes.voronoi_cells)."""
        if self.flat:
            return 0.5
        k = float(z_stretch)
        key = ('cells', float(scale_m), int(seed), k)
        if key not in self.noises:
            v = self.g.node('ShaderNodeTexVoronoi', voronoi_dimensions='3D' if k > 0.0 else '2D', feature='F1')
            off = self.g.vmath('ADD', self.pos, (97.13 * int(seed), -61.7 * int(seed), 0.0))
            if k > 0.0:
                off = self.g.vmath('MULTIPLY', off, (1.0, 1.0, k))
            self.g.set(v.inputs['Vector'], off)
            self.g.set(v.inputs['Scale'], 1.0 / max(float(scale_m), 1e-6))
            self.g.set(v.inputs['Randomness'], 1.0)
            self.noises[key] = self.g.separate_rgb(v.outputs['Color'])[0]
        return self.noises[key]

    def _bin(self, op, a, b):
        if isinstance(a, float) and isinstance(b, float):
            return {'+': a + b, '-': a - b, '*': a * b, '/': a / (b if abs(b) > 1e-12 else 1e-12)}[op]
        if op == '*' and (isinstance(a, float) and a == 1.0 or isinstance(b, float) and b == 1.0):
            return b if isinstance(a, float) and a == 1.0 else a
        if op == '*' and (isinstance(a, float) and a == 0.0 or isinstance(b, float) and b == 0.0):
            return 0.0
        if op == '+' and (isinstance(a, float) and a == 0.0 or isinstance(b, float) and b == 0.0):
            return b if isinstance(a, float) and a == 0.0 else a
        return self.g.math({'+': 'ADD', '-': 'SUBTRACT', '*': 'MULTIPLY', '/': 'DIVIDE'}[op], a, b)

    def __call__(self, t):
        key = P.tree_key(t)
        if key not in self.memo:
            self.memo[key] = self._compile(t)
        return self.memo[key]

    def _compile(self, t):
        k = t[0]
        if k == 'num':
            return float(t[1])
        if k == 'const':
            return float(self.consts.get(t[1], P.CONSTANTS[t[1]]))
        if k == 'mask':
            return self.attr(t[1])
        if k == 'neg':
            a = self(t[1])
            return -a if isinstance(a, float) else self.g.mul(a, -1.0)
        if k == 'op':
            return self._bin(t[1], self(t[2]), self(t[3]))
        f, args = t[1], t[2]
        if f in ('noise', 'fbm', 'cells'):
            seed = int(args[1][1]) if len(args) > 1 else 0
            if f == 'cells':
                return self.cells(args[0][1], seed, float(args[2][1]) if len(args) > 2 else 0.0)
            return {'noise': self.noise, 'fbm': self.fbm}[f](args[0][1], seed)
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
            if all(isinstance(e, float) for e in v):
                return float(min(max(v[0], v[1]), v[2]))
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
    if isinstance(a, float) and a == 1.0:
        return b
    if isinstance(b, float) and b == 1.0:
        return a
    if isinstance(a, float) and a == 0.0 or isinstance(b, float) and b == 0.0:
        return 0.0
    return g.mul(a, b)


class _Reader:
    """Image reads with the old material's filtering and de-tiling. one(): an 'Auto' read (Cubic near, Linear far,
    mixed by the handover) or a fixed interpolation; lattices(): a layer's two read coordinates (and the turn of the
    second); switch(): the noise that picks between them. Returns sockets (Color, Alpha)."""

    def __init__(self, g, coords, opt, far):
        self.g, self.coords, self.opt, self.far = g, coords, opt, far
        self.interp = opt['interpolation']
        self.mode = (opt.get('detile') or 'offset') if opt['anti_tile'] else None
        self._xyz = None

    def xyz(self):
        if self._xyz is None:
            self._xyz = self.g.separate_xyz(self.coords)
        return self._xyz

    def tex(self, img, vec, interp, box):
        n = self.g.node('ShaderNodeTexImage', interpolation=interp, extension='REPEAT')
        n.image = img
        if box:
            n.projection = 'BOX'
            n.projection_blend = 0.3
        self.g.set(n.inputs['Vector'], vec)
        return n.outputs['Color'], n.outputs['Alpha']

    def one(self, img, vec, box, interp=None):
        interp = interp or self.interp
        if interp != 'Auto':
            return self.tex(img, vec, interp, box)
        c1, a1 = self.tex(img, vec, 'Cubic', box)
        c2, a2 = self.tex(img, vec, 'Linear', box)
        g = self.g
        return g.mix('RGBA', self.far, c1, c2), g.mix('FLOAT', self.far, a1, a2)

    def lattices(self, i, tile, box, scale=1.0, salt=0):
        """(va, vb, turn) for layer i's reads of a tile `tile` metres (x scale): lattice A world-aligned; B at 0.7071
        the frequency with an offset (the old material's), and with detile 'rotate' on a planar layer also turned by
        an angle that differs per layer (turn = (cos, sin) to turn its normal map back), None without de-tiling."""
        g = self.g
        f = 1.0 / (float(tile) * float(scale))
        va = g.vmath('SCALE', self.coords, scale=f)
        if self.mode is None:
            return va, None, None
        off = (0.37 + 0.21 * i + 0.13 * salt, 0.71 - 0.17 * i + 0.29 * salt, 0.13 + 0.11 * i)
        if self.mode == 'rotate' and not box:
            th = 0.61 + 2.39996 * i + 1.1 * salt
            c, s = math.cos(th), math.sin(th)
            k = 0.7071 * f
            x, y, z = self.xyz()
            u = g.math('MULTIPLY_ADD', x, c * k, g.math('MULTIPLY_ADD', y, -s * k, off[0]))
            v = g.math('MULTIPLY_ADD', x, s * k, g.math('MULTIPLY_ADD', y, c * k, off[1]))
            return va, g.combine_xyz(u, v, g.mul(z, k)), (c, s)
        vb = g.vmath('ADD', g.vmath('SCALE', self.coords, scale=0.7071 * f), off)
        return va, vb, None

    def switch(self, i, tile, hA=None, hB=None, scale=1.0, salt=0):
        """0..1: lattice B's share, in world-noise patches detile_patch tiles across. With detile 'rotate' the two
        reads' heights move the edge (the taller texel wins near it), so it runs along the texture's features."""
        g = self.g
        size = self.opt['detile_patch'] * float(tile) * float(scale)
        if self.mode == 'rotate':
            n = _noise3(g, self.coords, size, detail=2.0, seed=3.1 * i + 0.5 + 5.3 * salt)
            if hA is not None:
                return g.smoothstep(0.43, 0.57, g.add(n, g.mul(g.sub(hB, hA), 0.6)))
            return g.smoothstep(0.47, 0.53, n)
        n = g.noise(self.coords, 1.0 / size, detail=2.0, w=3.1 * i + 0.5 + 5.3 * salt)
        return g.smoothstep(0.47, 0.53, n)


def _strata_zs(g, comp, st, coords):
    """The stratigraphic height socket: eido_strata (source 'attribute') or object z with a dip (source 'position'),
    plus z_offset_m, fault throws, world-noise warps and the runnels' smear."""
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
    sm = st.get('smear')
    if sm:
        # runnels: a noise width_m across and ten times as tall drags the bands up to `metres` down the walls
        width, amp = float(sm[0]), float(sm[1])
        sv = g.vmath('MULTIPLY', coords, (1.0 / width, 1.0 / width, 1.0 / (10.0 * width)))
        n = g.noise(sv, 1.0, detail=3.0, roughness=0.55, w=61.7)
        zs = g.add(zs, g.mul(g.sub(n, 0.5), 2.5 * amp))
    return zs


class _Strata:
    """The rock column's reads: band(offset_m) -> (colour, roughness) at the stratigraphic height plus offset_m, each
    distinct offset one more read of the one strata image (no extra sampler); relief() -> (relief 0..1, ledge 0..1)
    of the beds there (the relief image, one more image), when the spec's relief_m is over 0."""

    def __init__(self, g, comp, st, coords, pal_name):
        self.g = g
        rows = int(st.get('rows', 1))
        self.relief_m = float(st.get('relief_m', 0.0) or 0.0)
        self.img, self.z_lo, self.z_hi = strata_image(
            st['column'], name=f'eido_strata_{pal_name}', rows=rows, parting=float(st.get('parting', 0.0)),
            pad_m=float(st.get('pad_m', 0.0)), looks=bool(st.get('looks', False)), relief=self.relief_m > 0.0)
        self.relief_img = bpy.data.images.get(self.img.get('eido_relief', '')) if self.relief_m > 0.0 else None
        self.rep = bool(self.img.get('eido_repeat', False))
        self.zs = _strata_zs(g, comp, st, coords)
        self.v = 0.5
        if rows > 1:
            n = g.noise(coords, 1.0 / float(st.get('facies_m', 700.0)), detail=2.0, roughness=0.5, w=17.3)
            t = g.math('MULTIPLY_ADD', g.sub(n, 0.5), 2.4, 0.5, clamp=True)
            self.v = g.math('MULTIPLY_ADD', t, (rows - 1.0) / rows, 0.5 / rows)
        self.reads = {}
        self._uv = {}
        self._relief = None

    def uv(self, offset_m=0.0):
        key = round(float(offset_m), 3)
        if key not in self._uv:
            g = self.g
            span = self.z_hi - self.z_lo
            zs = g.add(self.zs, key) if key else self.zs
            u = g.math('MULTIPLY_ADD', zs, 1.0 / span, -self.z_lo / span)
            self._uv[key] = g.combine_xyz(u, self.v, 0.0)
        return self._uv[key]

    def _read(self, img, vec):
        n = self.g.node('ShaderNodeTexImage', interpolation='Linear', extension='REPEAT' if self.rep else 'EXTEND')
        n.image = img
        self.g.set(n.inputs['Vector'], vec)
        return n.outputs['Color'], n.outputs['Alpha']

    def band(self, offset_m=0.0):
        key = round(float(offset_m), 3)
        if key not in self.reads:
            self.reads[key] = self._read(self.img, self.uv(key))
        return self.reads[key]

    def relief(self):
        """(relief, ledge) sockets of the beds at the stratigraphic height, or None without a relief image."""
        if self.relief_img is None:
            return None
        if self._relief is None:
            col, _a = self._read(self.relief_img, self.uv(0.0))
            r, ledge, _b = self.g.separate_rgb(col)
            self._relief = (r, ledge)
        return self._relief


def _macro(g, coords, albedo, octaves, noise3=False):
    """The old material's world-scale variation, generalised to octaves: brightness (value), hue and saturation
    drift, each octave its own noise `scale_m` metres across (3D noise on a landscape, the old 4D otherwise)."""
    if not octaves:
        return albedo
    val, hue, sat = None, None, None
    for k, o in enumerate(octaves):
        if noise3:
            n = _noise3(g, coords, float(o['scale_m']), detail=float(o.get('detail', 2.0)),
                        roughness=float(o.get('roughness', 0.5)), seed=o.get('w', 1.7 + 2.9 * k))
        else:
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


def _decode_normal(g, nrao, turn=None, scale=1.0):
    """(nx, ny, roughness) of a normal_rough_ao read: x, y from 0..1 to -1..1 (times scale), turned back by `turn`
    ((cos, sin) of a turned lattice: the texture's +u runs along world (cos, -sin), its +v along (sin, cos))."""
    r, gr, rough = g.separate_rgb(nrao)
    nx = g.math('MULTIPLY_ADD', r, 2.0 * scale, -scale)
    ny = g.math('MULTIPLY_ADD', gr, 2.0 * scale, -scale)
    if turn is not None:
        c, s = turn
        nx, ny = (g.math('MULTIPLY_ADD', nx, c, g.mul(ny, s)), g.math('MULTIPLY_ADD', nx, -s, g.mul(ny, c)))
    return nx, ny, rough


def _patch_list(L):
    p = L.get('patches')
    if not p:
        return []
    return [p] if isinstance(p, dict) else list(p)


def _layer_reads(g, rd, S, L, i, coords_rot, steep):
    """The near reads of one layer: dict(col, h, nx, ny (None for box layers), rough, ao)."""
    tile = float(L['tile_m'])
    box = L['projection'] == 'box'
    va, vb, turn = rd.lattices(i, tile, box)
    ns = float(L['normal'])
    if not box:
        cA, hA = rd.one(S['albedo'], va, False)
        nA, aoA = rd.tex(S['nrao'], va, 'Linear', False)
        nxA, nyA, rA = _decode_normal(g, nA, None, ns)
        if vb is None:
            return dict(col=cA, h=hA, nx=nxA, ny=nyA, rough=rA, ao=aoA)
        cB, hB = rd.one(S['albedo'], vb, False)
        m = rd.switch(i, tile, hA, hB)
        nB, aoB = rd.tex(S['nrao'], vb, 'Linear', False)
        nxB, nyB, rB = _decode_normal(g, nB, turn, ns)
        return dict(col=g.mix('RGBA', m, cA, cB), h=g.mix('FLOAT', m, hA, hB), nx=g.mix('FLOAT', m, nxA, nxB),
                    ny=g.mix('FLOAT', m, nyA, nyB), rough=g.mix('FLOAT', m, rA, rB), ao=g.mix('FLOAT', m, aoA, aoB))
    # box: planar (with 'Auto' filtering) on gentle ground, in the frame Blender's Box projection gives an up-facing
    # surface (uv = (1 - y, x): the coordinates turned to (-y, x)), and the Box projection (mipmapped) on steep faces
    ra = g.vmath('SCALE', coords_rot, scale=1.0 / tile)
    cpA, hpA = rd.one(S['albedo'], ra, False)
    cbA, hbA = rd.tex(S['albedo'], va, 'Linear', True)
    nA, aoA = rd.tex(S['nrao'], va, 'Linear', True)
    rA = g.separate_rgb(nA)[2]
    if vb is None:
        return dict(col=g.mix('RGBA', steep, cpA, cbA), h=g.mix('FLOAT', steep, hpA, hbA), nx=None, ny=None, rough=rA,
                    ao=aoA, hbox=hbA)
    bx, by, bz = g.separate_xyz(vb)
    rb = g.combine_xyz(g.mul(by, -1.0), bx, bz)
    cpB, hpB = rd.one(S['albedo'], rb, False)
    cbB, hbB = rd.tex(S['albedo'], vb, 'Linear', True)
    mp = rd.switch(i, tile, hpA, hpB)
    mb = rd.switch(i, tile, hbA, hbB) if rd.mode == 'rotate' else mp
    cp, hp = g.mix('RGBA', mp, cpA, cpB), g.mix('FLOAT', mp, hpA, hpB)
    cb, hb = g.mix('RGBA', mb, cbA, cbB), g.mix('FLOAT', mb, hbA, hbB)
    nB, aoB = rd.tex(S['nrao'], vb, 'Linear', True)
    rB = g.separate_rgb(nB)[2]
    return dict(col=g.mix('RGBA', steep, cp, cb), h=g.mix('FLOAT', steep, hp, hb), nx=None, ny=None,
                rough=g.mix('FLOAT', mb, rA, rB), ao=g.mix('FLOAT', mb, aoA, aoB), hbox=hb)


def _far_reads(g, rd, S, L, i, opt, far_k):
    """The far read of one layer at far_k x its tile (mipmapped), de-tiled with far_detile: (Color, Alpha, the A
    lattice's Alpha alone: what the bump reads, cheaply, at that scale)."""
    tile = float(L['tile_m'])
    box = L['projection'] == 'box'
    if not opt.get('far_detile') or rd.mode is None:
        fa = g.vmath('SCALE', rd.coords, scale=1.0 / (tile * far_k))
        c, h = rd.tex(S['albedo'], fa, 'Linear', box)
        return c, h, h
    va, vb, _turn = rd.lattices(i, tile, box, scale=far_k, salt=1)
    cA, hA = rd.tex(S['albedo'], va, 'Linear', box)
    cB, hB = rd.tex(S['albedo'], vb, 'Linear', box)
    m = rd.switch(i, tile, hA, hB, scale=far_k, salt=1)
    return g.mix('RGBA', m, cA, cB), g.mix('FLOAT', m, hA, hB), hA


def _canopy(g, cn, coords, i):
    """A forest seen from afar (palettes' canopy): dict(col, h (for the height blend), crown (0..1), r_edge (each
    tree's 0..1 threshold for the ragged edge), far (the fade-in), bump (metres))."""
    crown_m = float(cn.get('crown_m', 4.5))
    # a 3D partition, so crowns keep their size on a steep flank (a planar one stretched them into vertical streaks
    # on a 70-degree karst tower)
    vor = g.node('ShaderNodeTexVoronoi', voronoi_dimensions='3D', feature='F1')
    g.set(vor.inputs['Vector'], g.vmath('ADD', coords, (13.7 * (i + 1), -29.1 * (i + 1), 0.0)))
    g.set(vor.inputs['Scale'], 1.0 / crown_m)
    g.set(vor.inputs['Randomness'], 0.85)
    r1, r2, r3 = g.separate_rgb(vor.outputs['Color'])
    # crowns of differing size and ragged outline (a smooth round dome per cell read as scales at 30-100 m)
    rag = _noise3(g, coords, crown_m / 2.2, detail=2.0, roughness=0.5, seed=71.3 + i)
    d = g.mul(vor.outputs['Distance'], g.add(g.math('MULTIPLY_ADD', r3, 0.45, 0.62), g.mul(rag, 0.45)))
    crown = g.sub(1.0, g.smoothstep(0.08, 0.6, d))
    lin = lambda h: tuple(P.hex_linear(h)) + (1.0,)                                # noqa: E731
    tone = g.mix('RGBA', r1, lin(cn.get('colour', '#26371f')), lin(cn.get('light', '#3d522c')))
    bump = g.mul(g.math('POWER', crown, 0.6), float(cn.get('height_m', 3.0)))
    r_edge = g.math('MULTIPLY_ADD', r2, 0.76, 0.12)
    h = g.math('MULTIPLY_ADD', crown, 0.6, 0.25)
    shade = g.math('MULTIPLY_ADD', crown, 0.4, 0.72)
    clump_m = float(cn.get('clump_m', 0.0) or 0.0)
    if clump_m > 0.0:
        # clumps: crowns grow in clusters a few trees across, with shadowed gaps between them, each cluster its own
        # tone (older dark spruce, younger paler stands) and its own relief, so the canopy seen from the air (a crown
        # finer than a pixel) keeps a grain of lit and shaded clusters; at the forest's edge whole clusters stand in or
        # out, a ragged edge at the scale an aerial resolves
        cv = g.node('ShaderNodeTexVoronoi', voronoi_dimensions='3D', feature='F1')
        g.set(cv.inputs['Vector'], g.vmath('ADD', coords, (-41.3 * (i + 1), 17.9 * (i + 1), 5.3)))
        g.set(cv.inputs['Scale'], 1.0 / clump_m)
        g.set(cv.inputs['Randomness'], 1.0)
        k1, k2, _k3 = g.separate_rgb(cv.outputs['Color'])
        rag2 = _noise3(g, coords, clump_m / 2.5, detail=2.0, roughness=0.5, seed=83.1 + i)
        cd = g.mul(cv.outputs['Distance'], g.math('MULTIPLY_ADD', rag2, 0.5, 0.75))
        gap = float(cn.get('clump_gap', 0.25))           # about the share of the ground in the gaps
        clump = g.sub(1.0, g.smoothstep(0.62 - 0.4 * gap, 0.9 - 0.4 * gap, cd))
        tone = g.vmath('SCALE', tone, scale=g.math('MULTIPLY_ADD', k1, 0.5, 0.76))
        shade = g.mul(shade, g.math('MULTIPLY_ADD', clump, 0.42, 0.68))       # 0.68 in the gaps, 1.1 on a clump:
        #                                                                       about 1 on average (grain, not darker)
        bump = g.add(bump, g.mul(g.math('POWER', clump, 0.8), float(cn.get('clump_height_m', 4.0))))
        r_edge = g.mix('FLOAT', 0.65, r_edge, g.math('MULTIPLY_ADD', k2, 0.76, 0.12))
        h = g.mul(h, g.math('MULTIPLY_ADD', clump, 0.45, 0.55))
        crown = g.mul(crown, g.math('MULTIPLY_ADD', clump, 0.6, 0.4))
    lit = g.vmath('SCALE', tone, scale=shade)
    col = g.mix('RGBA', g.smoothstep(0.0, 0.32, crown), lin(cn.get('gap', '#11160d')), lit)
    near0, near1 = cn.get('near_m', (25.0, 90.0))
    far = g.smoothstep(float(near0), float(near1), g.view_distance())
    return dict(col=col, h=h, crown=crown, r_edge=r_edge, far=far, bump=bump)


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
    # landscape palettes (detile 'rotate') build their breakup from 3D noise, half the cost of the old material's 4D
    # noise; the old meadow material keeps its nodes as they were (the shimmer probe's numbers)
    n3 = opt.get('detile') == 'rotate'

    def noise(pos, scale_m, detail, roughness, seed):
        if n3:
            return _noise3(g, pos, scale_m, detail=detail, roughness=roughness, seed=seed)
        return g.noise(pos, 1.0 / float(scale_m), detail=detail, roughness=roughness, w=seed)
    used = P.material_masks(pal)
    packs = mask_packs(used) if len(used) > ATTRS_DIRECT else []
    comp = _Compiler(g, coords, pal.get('constants'), noise3=n3, packs=packs)
    interp = opt['interpolation']
    if interp not in ('Auto', 'Cubic', 'Linear', 'Closest'):
        raise ValueError("options interpolation must be 'Auto', 'Cubic', 'Linear' or 'Closest'")
    far = g.handover(*opt['detail_distance']) if interp == 'Auto' else None
    rd = _Reader(g, coords, opt, far)
    images = set()
    # the far scale: past far_distance the albedo and height are read again at far_scale x the tile, so a slope a few
    # hundred metres off shows the scan's patterns at a larger size instead of a fine regular knit of repeats
    far_k = float(opt.get('far_scale', 1.0) or 1.0)
    fd = g.smoothstep(*opt['far_distance'], g.view_distance()) if far_k > 1.0 else None
    nz = g.separate_xyz(N)[2]
    # box layers: planar (with 'Auto' filtering) on gentle ground, the Box projection (mipmapped) on steep faces, so
    # rock seen at a grazing angle near the camera stays sharp (design 7: planar on gentle ground, box above ~35-45
    # degrees). The planar read turns the coordinates to (-y, x), the frame Blender's Box projection gives an up-facing
    # surface (uv = (1 - y, x)), so the two agree where they blend.
    steep, coords_rot = None, None
    if any(L['projection'] == 'box' for L in layers):
        steep = g.smoothstep(0.80, 0.68, nz)
        cx, cy, cz = rd.xyz()
        coords_rot = g.combine_xyz(g.mul(cy, -1.0), cx, cz)
    steep_face = None                                    # streaks: only on faces steeper than about 40-60 degrees

    # the strata reads (one image, shared by every strata layer)
    strata = None
    if pal.get('strata') and any(L['strata'] for L in layers):
        strata = _Strata(g, comp, pal['strata'], coords, pal['name'])
        images.add(strata.img.name)

    # per layer: coverage, then the reads
    per = []
    for i, (L, S) in enumerate(zip(layers, sets)):
        cov = _clamp01(g, comp(P.parse(L['weight'])))
        r = _layer_reads(g, rd, S, L, i, coords_rot, steep)
        images.update((S['albedo'].name, S['nrao'].name))
        col, h = r['col'], r['h']
        # the bump's own height: the box reads on a box layer (the planar read is the same texture in the frame the
        # box gives an up-facing surface), the near reads on a planar one; at a distance the far A lattice alone
        bump_near = g.sub(r.get('hbox', h), 0.5)
        bump_h = bump_near
        mean_lin = [float(v) for v in S['stats']['mean_albedo_linear']]
        if fd is not None:
            colf, hf, hfA = _far_reads(g, rd, S, L, i, opt, far_k)
            bump_h = g.mix('FLOAT', fd, bump_near, g.mul(g.sub(hfA, 0.5), float(opt.get('far_bump', 0.5)) * far_k))
            mm = float(L.get('macro_mod', opt.get('macro_mod', 0.0)) or 0.0)
            if mm > 0.0:
                # the scan as its own macro variation map: the near read's brightness follows the far read's
                ml = max(sum(a * b for a, b in zip(mean_lin, _LUMA)), 1e-4)
                lum = g.vmath('DOT_PRODUCT', colf, _LUMA)
                mod = g.math('MINIMUM', g.math('MAXIMUM', g.math('MULTIPLY_ADD', lum, mm / ml, 1.0 - mm), 0.55), 1.6)
                col = g.vmath('SCALE', col, scale=mod)
            fc = float(L.get('far_contrast', opt.get('far_contrast', 0.65)))
            if fc != 1.0:                                # the larger pattern, toned down around the scan's mean
                colf = g.vmath('ADD', g.vmath('SCALE', colf, scale=fc), tuple((1.0 - fc) * v for v in mean_lin))
            col = g.mix('RGBA', fd, col, colf)
            if L.get('far_height', True):
                h = g.mix('FLOAT', fd, h, hf)            # the far height blends at its own (larger) scale
            # (far_height False: a speckle layer, shrubs or tufts, keeps its own scale in the height blend; the far
            # height's eight-times magnified features drew its edges as 16 m blobs, camouflage on a desert plateau)
        mean = np.maximum(np.array(mean_lin, np.float64), 1e-4)
        contrast = float(L.get('contrast', 1.0))
        own = tuple(P.hex_linear(L['colour'])) if L['colour'] else None
        smix = float(L['strata']) if L['strata'] is not True else 1.0
        band_rough = None
        if smix > 0 and strata is not None:
            # the rock column's colour at this height (strata_offset_m: the beds above, for debris); a float `strata`
            # mixes it with the layer's own colour (talus: the debris of the beds above, mostly their colour)
            band, band_rough = strata.band(float(L.get('strata_offset_m', 0.0)))
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
        rough = g.mul(r['rough'], float(L['roughness']))
        if band_rough is not None:
            rough = g.mul(rough, band_rough if smix >= 1.0 else g.mix('FLOAT', smix, 1.0, band_rough))
        # a rock layer's beds in relief: hard beds stand as ledges (the bump lights their tops and shades their
        # undersides), soft ones weather back into darker recesses (relief_shade keeps that banding where the bump is
        # finer than a pixel): the ledge-and-recess striping of a layered wall, not painted bands
        relief_rv = relief_lv = None
        if smix >= 1.0 and strata is not None and L.get('relief', True) and strata.relief() is not None:
            relief_rv, relief_lv = strata.relief()
            images.add(strata.relief_img.name)
            shade = float(pal['strata'].get('relief_shade', 0.15))
            if shade > 0.0:
                col = g.vmath('SCALE', col, scale=g.math('MULTIPLY_ADD', relief_rv, shade, 1.0 - shade))
        nx, ny = r['nx'], r['ny']
        canopy_bump = None
        if L.get('canopy'):
            # the canopy before the patches, so a forest's tone patches (tints) vary the crowns seen from afar too
            cn = _canopy(g, L['canopy'], coords, i)
            kf = cn['far']
            col = g.mix('RGBA', kf, col, cn['col'])
            h = g.mix('FLOAT', kf, h, cn['h'])
            bump_h = g.mix('FLOAT', kf, bump_h, 0.0)
            rough = g.mix('FLOAT', kf, rough, 0.9)
            if nx is not None:
                nx, ny = g.mul(nx, g.sub(1.0, kf)), g.mul(ny, g.sub(1.0, kf))
            canopy_bump = g.mul(cn['bump'], kf) if float(L['canopy'].get('height_m', 3.0)) > 0 else None
            if L['canopy'].get('edge') and not isinstance(cov, float):
                # each tree in or out as a whole where the forest thins: a ragged edge of single crowns
                t = cn['r_edge']
                cov = g.mix('FLOAT', kf, cov, g.smoothstep(g.sub(t, 0.05), g.add(t, 0.05), cov))
        for k, pt in enumerate(_patch_list(L)):
            # a second tone in world-noise patches scale_m across (drier grass, a different soil, ochre stains): what
            # breaks a lawn-like scan up at the scales it mipmaps away at; `where` limits it by the masks
            amount = float(pt.get('amount', 0.6))
            if pt.get('scale_m') is None:
                pm = amount
            else:
                pn = noise(coords, float(pt['scale_m']), float(pt.get('detail', 3.0)), 0.55, 33.7 + 2.3 * i + 5.1 * k)
                pm = g.mul(g.smoothstep(float(pt.get('lo', 0.42)), float(pt.get('hi', 0.62)), pn), amount)
            if pt.get('where'):
                pm = _mul(g, pm, _clamp01(g, comp(P.parse(pt['where']))))
            if pt.get('tint'):
                ratio = np.array(pt['tint'][:3], np.float64)
            else:
                ref = np.array(P.hex_linear(L['colour'])) if L['colour'] else mean
                ratio = np.array(P.hex_linear(pt['colour'])) / np.maximum(ref, 1e-4)
            col = g.mix('RGBA', pm, col, g.vmath('MULTIPLY', col, tuple(float(v) for v in ratio)))
        if L.get('streaks'):
            # vertical streaks on steep faces (water stains on limestone, desert varnish on sandstone): a noise
            # `width` metres across and eight times as tall, darkening the albedo by up to `amount`
            if steep_face is None:
                steep_face = g.smoothstep(0.78, 0.5, nz)
            st = [float(v) for v in L['streaks']]
            width, amount = st[0], st[1]
            lo, hi = (st[2], st[3]) if len(st) >= 4 else (0.45, 0.68)     # (lo, hi): how sparse they are
            sv = g.vmath('MULTIPLY', coords, (1.0 / width, 1.0 / width, 1.0 / (8.0 * width)))
            sn = noise(sv, 1.0, 3.0, 0.55, 19.7 + 3.3 * i)
            dark = g.mul(g.mul(g.smoothstep(lo, hi, sn), amount), steep_face)
            if L.get('streaks_where'):
                # where the water runs: the stains gather in the chutes and under the pour-overs (flow), not
                # evenly over a wall
                dark = _mul(g, dark, _clamp01(g, comp(P.parse(L['streaks_where']))))
            col = g.vmath('SCALE', col, scale=g.sub(1.0, dark))
        relief_h = None
        if relief_rv is not None:
            relief_h = g.mul(relief_rv, strata.relief_m)
            ld = L.get('ledges')
            if ld:
                # plants and debris lodged on the ledges (the tops of the beds that stand out): tufts along each
                # ledge, broken at a few metres, the layer's own scan tinted, so up close they keep its grain
                pn = noise(coords, float(ld.get('scale_m', 5.0)), 3.0, 0.55, 51.3 + 3.1 * i)
                pm = g.mul(g.mul(relief_lv, g.smoothstep(float(ld.get('lo', 0.38)), float(ld.get('hi', 0.6)), pn)),
                           float(ld.get('amount', 0.75)))
                if ld.get('where'):
                    pm = _mul(g, pm, _clamp01(g, comp(P.parse(ld['where']))))
                col = g.mix('RGBA', pm, col, g.vmath('MULTIPLY', col, tuple(float(v) for v in ld['tint'][:3])))
        if float(L.get('value', 1.0)) != 1.0:
            col = g.vmath('SCALE', col, scale=float(L['value']))
        col = g.vmath('MINIMUM', g.vmath('MAXIMUM', col, (0.0, 0.0, 0.0)), (0.95, 0.95, 0.95))
        ripple = _ripples(g, coords, L['ripples'], i) if L.get('ripples') else None
        per.append(dict(L=L, cov=cov, col=col, h=h, hb=bump_h, nx=nx, ny=ny, rough=rough, ao=r['ao'],
                        box=L['projection'] == 'box', ripple=ripple, canopy_bump=canopy_bump, relief=relief_h))

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
            if n3:                                       # 3D and three octaves on a landscape (the old: 4D, five)
                n = _noise3(g, coords, 1.0 / 0.85, detail=3.0, roughness=0.62, seed=11.1 + 7.3 * i)
            else:
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
    if opt.get('tone'):
        # the tone expression: hollows, gorges and slots darker, convex edges paler (x (1 + tone), 0.4..1.6)
        tv = comp(P.parse(opt['tone']))
        if not isinstance(tv, float):
            albedo = g.vmath('SCALE', albedo, scale=g.math('MINIMUM', g.math('MAXIMUM', g.add(tv, 1.0), 0.4), 1.6))
        elif tv != 0.0:
            albedo = g.vmath('SCALE', albedo, scale=min(max(1.0 + tv, 0.4), 1.6))
    albedo = _macro(g, coords, albedo, opt.get('macro') or [], n3)
    # damp patches: wet soil darkens and loses some roughness (the old noise patches, plus damp_where)
    if opt['damp'] > 0 or opt.get('damp_where'):
        dm = 0.0
        if opt['damp'] > 0:
            dn = noise(coords, float(opt.get('damp_scale_m', 6.25)), 3.0, 0.6, 13.3)
            dm = g.mul(g.smoothstep(0.5, 0.68, dn), float(opt['damp']))
        if opt.get('damp_where'):
            dw = _clamp01(g, comp(P.parse(opt['damp_where'])))
            dm = dw if isinstance(dm, float) and dm == 0.0 else g.math('MAXIMUM', dm, dw)
        if not (isinstance(dm, float) and dm == 0.0):
            albedo = g.vmath('SCALE', albedo, scale=g.sub(1.0, g.mul(dm, 0.38)))
            rough = g.mul(rough, g.sub(1.0, g.mul(dm, 0.32)))

    # normals: planar layers' maps in the world-XY tangent frame, box layers flat there (their relief is bumped)
    nx = wsum([p['nx'] if not p['box'] else None for p in per])
    ny = wsum([p['ny'] if not p['box'] else None for p in per])
    normal = N if (isinstance(nx, float) and isinstance(ny, float)) else _xy_tangent_normal(g, nx, ny, N)
    # the bump. EEVEE evaluates a Bump node's height input three times (at the shading point and a pixel over in x and
    # in y), everything upstream of it included: weighted by the blended layer weights, the whole material (every
    # weight expression, noise and read) ran three times (measured 11-12: a landscape palette cost 5-10 x the old
    # material per frame). On a landscape the height is weighted instead by cheap coverages: each layer's weight
    # expression with its noise terms at their mean, composited in order (no height blend), over the bumped layers'
    # own height reads; the old material keeps its weights.
    bw = wn
    if n3:
        cheap = _Compiler(g, coords, pal.get('constants'), noise3=True, flat=True, attrs=comp.attrs, packs=packs)
        bumped = [float(p['L']['bump_m']) > 0 or p['ripple'] is not None or p['canopy_bump'] is not None
                  or p['relief'] is not None for p in per]
        # (a bumped layer's share needs the coverage of every layer above it)
        ccov = [_clamp01(g, cheap(P.parse(p['L']['weight']))) if bumped[i] or any(bumped[:i]) else 0.0
                for i, p in enumerate(per)]
        bw = [None] * len(per)
        crem = 1.0
        for i in range(len(per) - 1, -1, -1):
            bw[i] = _mul(g, ccov[i], crem) if bumped[i] else 0.0
            crem = _mul(g, crem, _one_minus(g, ccov[i]))
    bump_terms = []
    for p, w in zip(per, bw):
        bm = float(p['L']['bump_m'])
        if bm > 0:
            bump_terms.append(_mul(g, g.mul(p['hb'], bm), w))
        if p['ripple'] is not None:
            bump_terms.append(_mul(g, p['ripple'], w))
        if p['canopy_bump'] is not None:
            bump_terms.append(_mul(g, p['canopy_bump'], w))
        if p['relief'] is not None:
            bump_terms.append(_mul(g, p['relief'], w))
    bump_terms = [t for t in bump_terms if not (isinstance(t, float) and t == 0.0)]
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
        # options debug='weights': the top three layers' final weights as red, green, blue; 'layers': each layer's
        # flat debug colour (DEBUG_COLOURS, bottom first) mixed by its weight; 'albedo': the albedo; all unlit (an
        # Emission), to see what covers each pixel
        em = g.node('ShaderNodeEmission')
        if dbg == 'weights':
            cols = [wn[-1], wn[-2] if len(wn) > 1 else 0.0, wn[-3] if len(wn) > 2 else 0.0]
            g.set(em.inputs['Color'], g.combine_xyz(*cols))
        elif dbg == 'layers':
            g.set(em.inputs['Color'], wsum_vec([DEBUG_COLOURS[i % len(DEBUG_COLOURS)] for i in range(len(per))])
                  if len(per) > 1 else DEBUG_COLOURS[0] + (1.0,))
        else:
            g.set(em.inputs['Color'], albedo)
        g.set(gout.inputs['BSDF'], em.outputs['Emission'])
    g.set(gout.inputs['Base Color'], albedo)
    g.set(gout.inputs['Roughness'], rough_c)
    g.set(gout.inputs['Normal'], normal)
    ng['eido_palette'] = pal['name']
    ng['eido_sets'] = [S['name'] for S in sets]
    ng['eido_images'] = len(images)
    ng['eido_mask_packs'] = json.dumps(packs)
    ng['eido_attributes'] = len(packs) if packs else len([k for k in comp.attrs if isinstance(k, str)])
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


def terrain_constants(obj):
    """The terrain constants (palettes.CONSTANTS) of a make_terrain object, from its eido_terrain record: its base
    elevation, and its snowline and treeline (its recipe's knobs, its recipe's mask parameters, or its real place's,
    palettes.PLACES). {} for an object make_terrain did not make."""
    raw = obj.get('eido_terrain') if obj is not None else None
    if not raw:
        return {}
    try:
        info = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except (TypeError, ValueError):
        return {}
    out = {}
    if info.get('base_elevation_m') is not None:
        out['base_elevation_m'] = float(info['base_elevation_m'])
    knobs = info.get('knobs') or {}
    mp = {}
    rec = info.get('recipe') or {}
    dfl = rec.get('defaults') if isinstance(rec, dict) else None
    if isinstance(dfl, dict):
        mp.update(dfl.get('mask_params') or {})
    dem = knobs.get('dem')
    if isinstance(dem, str) and dem in P.PLACES:
        mp.update(P.PLACES[dem].get('mask_params') or {})
    for key in ('snowline_m', 'treeline_m'):
        if knobs.get(key) is not None:
            mp[key] = knobs[key]
        if mp.get(key) is not None:
            out[key] = float(mp[key])
    return out


def resolve(palette='auto', recipe=None, strata=None, options=None, constants=None):
    """The filled-in palette dict surface_material builds: palette (name, 'auto', dict) with a strata override (a
    column name, a column, or a strata dict merged over the palette's), material options and terrain constants
    merged in."""
    pal = P.get(palette, recipe)
    if strata is not None:
        if isinstance(strata, dict) and ('column' in strata or 'faults' in strata or 'source' in strata):
            pal['strata'] = dict(pal.get('strata') or {}, **strata)
        else:
            pal['strata'] = dict(pal.get('strata') or {'source': 'attribute'}, column=strata)
        for k, v in P.STRATA_DEFAULTS.items():
            pal['strata'].setdefault(k, v)
    if options:
        pal['options'].update(options)
    if constants:
        pal['constants'].update({k: float(v) for k, v in constants.items() if k in P.CONSTANTS and v is not None})
    problems = P.check(pal)
    if problems:
        raise ValueError(f'palette {pal["name"]!r}: ' + '; '.join(problems))
    return pal


def surface_material(palette='auto', recipe=None, strata=None, options=None, name='terrain_ground', prefer='2k',
                     log=print, constants=None):
    """A material whose surface is the eido_terrain_surface group of a palette; palette=None gives clay_material().

    palette   a name (palettes.names()), 'auto' (the recipe's: palettes.RECIPE_PALETTES), or a palette dict
    recipe    the recipe (name, Recipe or dict), for 'auto'
    strata    the rock column for the palette's strata layers: a STRATA_COLUMNS name, the solver's column list, or a
              dict (column, source 'attribute' | 'position', z_offset_m, dip_deg, dip_azimuth_deg, faults, warp,
              facies_m, smear, parting, looks)
    options   material options over the palette's (palettes.DEFAULT_OPTIONS)
    constants the terrain constants over the palette's (palettes.CONSTANTS: base_elevation_m, snowline_m, treeline_m)
    """
    if palette is None:
        return clay_material(name)
    t0 = time.time()
    pal = resolve(palette, recipe, strata, options, constants)
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
    mat['eido_constants'] = json.dumps(pal['constants'])
    mat['eido_mask_packs'] = ng['eido_mask_packs']
    if log:
        packed = json.loads(ng['eido_mask_packs'])
        log(f"[surfacing] {pal['name']}: {len(pal['layers'])} layers, {ng['eido_images']} images, "
            f"{ng['eido_attributes']} mesh attributes" + (f" ({sum(len(m) for _a, m in packed)} masks packed three to "
                                                         f"one: pack_masks writes them)" if packed else '')
            + f", {len(ng.nodes)} nodes in {time.time() - t0:.1f} s")
    return mat


def apply_surface(obj, palette='auto', recipe=None, strata=None, options=None, name=None, log=print, constants=None):
    """surface_material(...) assigned to obj (its material slots replaced), with the terrain's own constants
    (terrain_constants(obj): base elevation, snowline, treeline) under any given here. Warns about masks the palette
    reads that obj's mesh lacks (they read as 0). Returns the material."""
    consts = terrain_constants(obj)
    consts.update(constants or {})
    mat = surface_material(palette, recipe, strata, options, name=name or (obj.name + '_ground'), log=log,
                           constants=consts)
    me = obj.data
    me.materials.clear()
    me.materials.append(mat)
    if palette is not None:
        pack_masks(obj, mat)
        if log:
            miss = missing_masks(obj, mat.get('eido_masks', []))
            if miss:
                log(f"[surfacing] {obj.name}: no attribute for {', '.join(miss)} (read as 0)")
    return mat


def pack_masks(obj, mat=None):
    """Write the packed mask attributes a terrain material reads (its eido_mask_packs: a material reading more than
    ATTRS_DIRECT masks reads them three to a FLOAT_VECTOR point attribute, so its shader compiles) onto obj's mesh,
    from the mesh's eido_<mask> point attributes (a mask the mesh lacks packs as 0). apply_surface calls it; call it
    yourself after assigning a surface_material() to a mesh. Returns the attribute names written."""
    mat = mat if mat is not None else obj.active_material
    packs = json.loads((mat.get('eido_mask_packs') if mat is not None else None) or '[]')
    if not packs:
        return []
    me = obj.data
    n = len(me.vertices)
    buf = np.zeros(n, np.float32)
    for an, masks in packs:
        arr = np.zeros((n, 3), np.float32)
        for c, m in enumerate(masks):
            a = me.attributes.get('eido_' + m)
            if a is not None and a.domain == 'POINT' and a.data_type == 'FLOAT':
                a.data.foreach_get('value', buf)
                arr[:, c] = buf
        old = me.attributes.get(an)
        if old is not None:
            me.attributes.remove(old)
        me.attributes.new(an, 'FLOAT_VECTOR', 'POINT').data.foreach_set('vector', arr.ravel())
    return [an for an, _m in packs]


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
           'pack_set', 'pack_masks', 'mask_packs', 'strata_image', 'resolve', 'terrain_constants', 'cache_root',
           'GROUP_NAME', 'PACK_VERSION', 'MAX_IMAGES', 'ATTRS_DIRECT', 'DEBUG_COLOURS']

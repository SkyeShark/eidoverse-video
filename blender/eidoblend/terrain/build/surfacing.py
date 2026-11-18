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

With baked surface data (data=SurfaceData, terrain/surface; SURFACING_DESIGN.md 2.4-2.6, 3.3-3.7) the same palette
builds the per-texel material instead:
  - every map is read from its atlas through the two-slot level reader (reader_group): per pixel the finest window
    holding it, the even levels in one slot and the odd levels in the other, each slot changing level only where its
    weight is exactly 0 (a dead band of three footprints inside every window edge), so no 2 x 2 quad on a window edge
    reads the atlas' coarsest mips; slope, aspect, northness, eastness and insolation come from the baked field
    normal (D), height from the object z;
  - the shading normal is the field normal plus the relief below the cell (D's gradient, detail_strength), the scans'
    normal maps in its tangent frame, the strata's bed relief as an analytic tilt (the relief image differentiated
    along the stratigraphic height: no Bump node, which would evaluate the level reader three times), and the bump
    of ripples and canopy on top (each bump's weight in its Distance, read once outside the bump's height);
  - planar reads are hex-tiled ('hex': three reads on a triangle grid, each turned and offset, sharpened by w^7
    and their heights; a read's coordinate changes only where its weight is 0). The grid is one node group,
    eido_hex_grid, placed once per lattice: a layer's lattice is its hex_m, by default its tile snapped to
    2.5 x 2^n metres (hex_class), so layers of like tiles share one grid. With 'Auto' filtering the hex reads are
    mipmapped Linear, and within detail_distance one read at the plain world coordinate (albedo Cubic, normal map
    Linear) takes over (design 8.1's first lever; near_hex True: Cubic in every hex read). Where a hexagon is
    narrower than a 2 x 2 pixel quad (a 2.5 m lattice from about 100-300 m on), every quad straddles a read's jump
    and the hex reads fall to the scan's coarsest mips: the ground there shows the scan's mean, and its variation
    comes from the terrain's data;
  - box layers read eight fixed sector frames on faces steeper than 47 degrees (u along the strike, v up a fixed
    65-degree dip, two slots by the face's own bearing; hex-tiled inside each on one lattice, steep_hex_m, without
    turning: rock on a wall is directional, for the box layers of the largest tiles, the cliffs; a smaller box tile
    under a cliff layer reads each frame once, steep_hex_share), planar below 37 degrees, their scans'
    normal maps in each frame's tangent plane; the Box projection is not used. With the palette's far_scale they
    keep the far read on steep faces (the scan at far_scale x the tile in the same frames, the two slots height
    blended, over far_distance: the joints and blocks a wall shows from 100 m on); planar reads have none;
  - every noise term fades with the pixel's footprint (and a smoothstep around a faded term widens by the spread it
    lost, so a layer's cover holds as the noise fades), and fbm drops the octaves finer than two footprints;
  - a layer's ramp and the satmap are read from the palette's ramp image (one row each, Closest); the patches get()
    wrote for them are skipped;
  - past D0 (a main-level texel spanning 2.5 pixels, or the option far_m) the ground fades over D0..1.5 D0 to the
    baked far colour C (its own data per texel to the horizon) and its roughness, never inside the hero windows;
    each layer keeps its own specular there (the near weights are evaluated anyway); rings beyond 1.5 D0 from every
    camera passed to apply_surface take the far material (slot 1), a cost saving only, with the palette's one
    specular (C carries no specular).
The layer key `fallback` (a weight for a material without baked data) is taken in place of `weight` without data, or
where the weight reads a map the data lacks.

Mesh attributes per material: EEVEE fails a material that reads 15 of them ('uses too many attributes'), so a palette
reading more than ATTRS_DIRECT masks reads them packed three to a FLOAT_VECTOR point attribute (mask_packs), which
apply_surface writes onto the mesh (pack_masks). A material with baked data reads no mesh attribute.

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
# a material with baked data counts samplers, not images: an image read with one state (Linear and Cubic share; the
# atlases are read Linear EXTEND in both reader slots, the scans Linear or Cubic REPEAT) is one sampler, and each
# other state (Closest, EXTEND against REPEAT) one more (SURFACING_DESIGN.md 1.3, probe A)
MAX_SAMPLERS = 28
SECTOR_DIP_DEG = 65.0                 # the sector frames' fixed up-dip axis (SURFACING_DESIGN.md 3.4, probe C)
STEEP_DEG = (37.0, 47.0)              # box layers: planar below, sector frames above
HEX_POWER = 7.0                       # hex tiling's sharpening of the barycentric weights
HEX_CONTRAST = 0.6                    # ... and how much each read's own height weighs (mix(1, 2 h, 0.6))
HEX_LADDER = 2.5                      # default hex lattices are this x 2^n metres (hex_class): like tiles share one
STEEP_HEX = 2.0                       # the sector reads' hex lattice, in hex_class(the largest box tile); 0: one
#                                       read per sector frame (a layer's steep_hex_m sets its own)
STEEP_HEX_SHARE = 0.5                 # ... for box layers whose tile is at least this share of the largest box tile;
#                                       smaller ones (talus and scree under a cliff layer, which covers the faces
#                                       over 47 degrees) read each sector frame once (option steep_hex_share; 0: all)
HEX_PATCH = 0.29                      # a hexagon's width in hex_m (the lattice unit, 1 / (2 sqrt 3))
BLEND_PATCH_M = 1.0                   # hexagons wider than this lend a layer edge less of their height's swing
CUBIC_FAMILIES = ('D',)               # the atlases also read bicubic where a texel is magnified (_Data.fam)
CUBIC_PX = (0.3, 0.6)                 # ... from a pixel spanning this share of a texel (bicubic) to this (mipmapped)
DEAD_FOOTPRINTS = 3.0                 # the reader's dead band inside a window edge, in footprints
FADE_CELLS = 8.0                      # a level fades in over this many of its own cells
FAR_TEXEL_PX = 2.5                    # D0: where a main-level texel spans this many pixels
FAR_FADE_MAIN_CELLS = 64.0            # the far colour fades in over this many main cells beyond the hero windows
FAR_GRAIN = 0.25                      # how much of the base layer's scan luminance the far colour keeps
FAR_FADE_NODE = 'eido_far_fade'       # the near material's hand-off smoothstep over D0..1.5 D0 (set_far_distance)
DETAIL_STRENGTH = 0.5                 # the relief below the cell, by default (options detail_strength)
# the 5-95 % half-range of (n - 0.5) of the mask language's noise() and fbm() (Blender's Noise Texture, stretched
# x2.5 and x3; measured with surface/noise.py over 2e5 points): what a faded term's smoothstep widens by
NOISE_HALF = {'noise': 0.358, 'fbm': 0.344}
# ... and of the raw Noise Texture's Fac (patches, streaks, damp, ledges), by detail 0..5
RAW_HALF = (0.2, 0.163, 0.143, 0.134, 0.130, 0.128)
CANOPY_COVER, CANOPY_SHADE = 0.72, 0.92   # a canopy's mean far away: lit crowns' share, and their shade (the far
#                                           colour C's, surface/far_colour.py)
HEX_VERSION = 4
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
    are the same with or without it). The pixels are strata_array's."""
    out = strata_array(column, px_per_m=px_per_m, seed=seed, rows=rows, parting=parting, pad_m=pad_m, looks=looks,
                       repeat=repeat, relief=relief)
    rgba, z_lo, z_hi = out[:3]
    rep = P.column_repeats(column) if repeat is None else bool(repeat)
    img = _float_image(name, rgba)
    img['eido_rows'] = int(rgba.shape[0])
    img['eido_repeat'] = rep
    if relief:
        ri = _float_image(name + '_relief', out[3])
        ri['eido_rows'] = int(rgba.shape[0])
        img['eido_relief'] = ri.name
    return img, float(z_lo), float(z_hi)


def strata_array(column, px_per_m=STRATA_PX_PER_M, seed=0, rows=1, parting=0.0, pad_m=0.0, looks=False, repeat=None,
                 relief=False):
    """The numpy half of strata_image (no bpy): (rgba, z_lo, z_hi), rgba (rows, W, 4) float64, linear RGB the bed
    colour and A its roughness multiplier, z_lo..z_hi metres across W (a repeating column, palettes.column_repeats,
    spans one period: read it with wrap). relief=True adds a fourth item, the relief image's pixels (R how far each
    bed stands out, G the ledges, A 1). Deterministic per column: the beds strata_image draws, pixel for pixel."""
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
    if relief:
        return rgba, float(z_lo), float(z_hi), rel
    return rgba, float(z_lo), float(z_hi)


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
    g.set(n.inputs['Detail'], detail if isinstance(detail, bpy.types.NodeSocket) else float(detail))
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
    another compiler's attribute nodes; packs (mask_packs): the masks read from packed attributes.
    data (_Data): baked surface maps, read before any attribute. fp (a footprint socket, metres): every noise() and
    fbm() term's deviation from its mean is scaled by smoothstep(1, 4, scale / footprint), their detail drops to
    log2(scale / (2 footprint)), and a smoothstep whose argument holds a faded term widens its edges by the spread
    the term lost (NOISE_HALF), so its expected cover stays put as the noise fades (SURFACING_DESIGN.md 3.2, rule 4).
    cells() has no mean to fade to and is kept as it is."""

    def __init__(self, g, pos, consts=None, noise3=False, flat=False, attrs=None, packs=None, data=None, fp=None):
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
        self.data = data
        self.fp = None if flat else fp
        self._fades = {}
        self._details = {}
        self._inv_fp = None
        self._log_fp = None

    def fade(self, scale_m):
        """smoothstep(1, 4, scale / footprint): 1 where a term of that scale spans 4 pixels or more, 0 under one
        (1.0 without a footprint)."""
        if self.fp is None:
            return 1.0
        key = max(float(scale_m), 1e-6)
        if key not in self._fades:
            # (the edges divided by the scale instead of the footprint multiplied by it: one node per scale)
            self._fades[key] = self.g.smoothstep(1.0 / key, 4.0 / key, self._per_fp())
        return self._fades[key]

    def _per_fp(self):
        """1 / footprint, once."""
        if self._inv_fp is None:
            self._inv_fp = self.g.math('DIVIDE', 1.0, self.fp)
        return self._inv_fp

    def detail(self, scale_m, detail):
        """The Noise Texture's detail for a term of scale_m: min(detail, log2(scale / (2 footprint))), at least 0."""
        if self.fp is None or float(detail) <= 0.0:
            return float(detail)
        key = (max(float(scale_m), 1e-6), float(detail))
        if key not in self._details:
            g = self.g
            if self._log_fp is None:                       # log2(1 / (2 footprint)), once
                self._log_fp = g.math('LOGARITHM', g.math('MAXIMUM', g.mul(self._per_fp(), 0.5), 1e-9), 2.0)
            ls = math.log2(key[0])
            # clamp(log2(scale) + log2(1 / (2 footprint)), 0, detail), as one clamped linear map per scale
            self._details[key] = g.map_range(self._log_fp, -ls, key[1] - ls, 0.0, key[1])
        return self._details[key]

    def lost_spread(self, t):
        """The half-spread the faded noise terms of an expression tree lost (a float 0.0 or a socket): sum over its
        additive noise and fbm terms of |coefficient| x NOISE_HALF x (1 - fade). Products of two non-constant terms
        and the nonlinear functions count 0 (their inner smoothsteps widen themselves)."""
        if self.fp is None:
            return 0.0
        k = t[0]
        if k in ('num', 'const', 'mask'):
            return 0.0
        if k == 'neg':
            return self.lost_spread(t[1])
        g = self.g

        def add(a, b):
            if isinstance(a, float) and a == 0.0:
                return b
            if isinstance(b, float) and b == 0.0:
                return a
            return g.add(a, b)

        def scale(c, s):
            if isinstance(s, float):
                return abs(c) * s
            return s if abs(c) == 1.0 else g.mul(s, abs(c))
        if k == 'op':
            o = t[1]
            if o in '+-':
                return add(self.lost_spread(t[2]), self.lost_spread(t[3]))
            if o == '*':
                a, b = self(t[2]), self(t[3])
                if isinstance(a, float):
                    return scale(a, self.lost_spread(t[3]))
                if isinstance(b, float):
                    return scale(b, self.lost_spread(t[2]))
                return 0.0
            if o == '/':
                b = self(t[3])
                if isinstance(b, float) and abs(b) > 1e-12:
                    return scale(1.0 / b, self.lost_spread(t[2]))
                return 0.0
            return 0.0
        if k == 'call' and t[1] in ('noise', 'fbm'):
            f = self.fade(float(t[2][0][1]))
            hs = NOISE_HALF[t[1]]
            return 0.0 if isinstance(f, float) else g.math('MULTIPLY_ADD', f, -hs, hs)
        return 0.0

    def attr(self, name):
        if name not in self.attrs:
            if self.data is not None and self.data.has(name):
                self.attrs[name] = self.data.value(name)
            elif name in self.pack_of:
                an, c = self.pack_of[name]
                if ('pack', an) not in self.attrs:
                    self.attrs[('pack', an)] = self.g.separate_xyz(self.g.attribute(an).outputs['Vector'])
                self.attrs[name] = self.attrs[('pack', an)][c]
            else:
                self.attrs[name] = self.g.attribute('eido_' + name).outputs['Fac']
        return self.attrs[name]

    def _stretch(self, n, k, scale_m):
        """clamp((n - 0.5) k f + 0.5, 0, 1): the stretched noise, faded by the footprint (the far colour's form)."""
        f = self.fade(scale_m)
        kk = k if isinstance(f, float) else self.g.mul(f, k)
        return self.g.math('MULTIPLY_ADD', self.g.sub(n, 0.5), kk, 0.5, clamp=True)

    def noise(self, scale_m, seed=0):
        if self.flat:
            return 0.5
        key = (float(scale_m), int(seed))
        if key not in self.noises:
            if self.noise3:
                n = _noise3(self.g, self.pos, scale_m, detail=self.detail(scale_m, 2.0), roughness=0.5,
                            seed=0.37 + 7.31 * int(seed))
            else:
                n = self.g.noise(self.pos, 1.0 / max(float(scale_m), 1e-6), detail=self.detail(scale_m, 2.0),
                                 roughness=0.5, w=0.37 + 7.31 * int(seed) + 0.013 * float(scale_m))
            # the shader noise's spread is narrow (mostly 0.3-0.7): stretch it to about 0..1
            self.noises[key] = self._stretch(n, 2.5, scale_m)
        return self.noises[key]

    def fbm(self, scale_m, seed=0):
        """Five octaves of 3D world noise (features from scale_m down to a thirtieth of it), about 0..1, one noise
        node per (scale, seed) reading its Fac only (a 4D node's three colour channels cost three noises each)."""
        if self.flat:
            return 0.5
        key = ('fbm', float(scale_m), int(seed))
        if key not in self.noises:
            n = _noise3(self.g, self.pos, scale_m, detail=self.detail(scale_m, 5.0), roughness=0.6,
                        seed=5.3 + 1.9 * int(seed))
            self.noises[key] = self._stretch(n, 3.0, scale_m)
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
            e0, e1 = v[0], v[1]
            if isinstance(e0, float) and isinstance(e1, float):
                sp = self.lost_spread(args[2])
                if not isinstance(sp, float):
                    sgn = 1.0 if e1 >= e0 else -1.0
                    e0, e1 = g.math('MULTIPLY_ADD', sp, -sgn, e0), g.math('MULTIPLY_ADD', sp, sgn, e1)
            return g.smoothstep(e0, e1, v[2])
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


def _sat(g, x):
    """clamp(x, 0, 1) as one node (a Math node's own clamp): the material with baked data counts its nodes."""
    return max(0.0, min(1.0, x)) if isinstance(x, float) else g.math('ADD', x, 0.0, clamp=True)


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


def _strata_zs(g, comp, st, coords, base=None):
    """The stratigraphic height socket: eido_strata (source 'attribute') or object z with a dip (source 'position'),
    plus z_offset_m, fault throws, world-noise warps and the runnels' smear. base: a height socket that stands for
    the strata attribute or the object z (a debris' source height, src_strata), through the same offsets."""
    x, y, z = g.separate_xyz(coords)
    if base is not None and st.get('source', 'attribute') == 'attribute':
        zs = base
    elif st.get('source', 'attribute') == 'attribute':
        zs = comp.attr('strata')
    else:
        z = base if base is not None else z
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
        self._slope = None
        self._g_st = (g, comp, st, coords)
        self._at = {}

    def band_at(self, base):
        """(colour, roughness) of the column at another height socket that stands for the strata attribute or the
        object z (src_strata: a debris' source bed), through the same offsets, faults and warps: one more read of
        the same image."""
        key = base.node.name + ':' + base.identifier
        if key not in self._at:
            g, comp, st, coords = self._g_st
            zs = _strata_zs(g, comp, st, coords, base=base)
            span = self.z_hi - self.z_lo
            u = g.math('MULTIPLY_ADD', zs, 1.0 / span, -self.z_lo / span)
            self._at[key] = self._read(self.img, g.combine_xyz(u, self.v, 0.0))
        return self._at[key]

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

    def relief_slope(self):
        """(d relief / d zs per metre, the direction zs rises in): the beds' relief differentiated along the
        stratigraphic height, a central difference half a pixel of the relief image either side (two more reads of
        that image, mipmapped, so beds finer than a pixel fade to no slope), and the unit-rise direction of zs: +z,
        tilted by the dip of a 'position' source (the warps' and runnels' own gradients are a few per cent and
        left out). What an analytic tilt of the normal needs: a Bump node would evaluate the whole stratigraphic
        height, the level reader under it included, three times."""
        if self.relief_img is None:
            return None
        if self._slope is None:
            g, _comp, st, _coords = self._g_st
            span = self.z_hi - self.z_lo
            d = 0.5 * span / float(self.relief_img.size[0])
            r = []
            for off in (d, -d):
                u = g.math('MULTIPLY_ADD', self.zs, 1.0 / span, (off - self.z_lo) / span)
                col, _a = self._read(self.relief_img, g.combine_xyz(u, self.v, 0.0))
                r.append(g.separate_rgb(col)[0])
            up = (0.0, 0.0, 1.0)
            if st.get('source', 'attribute') != 'attribute':
                dip = math.tan(math.radians(float(st.get('dip_deg', 0.0))))
                az = math.radians(float(st.get('dip_azimuth_deg', st.get('azimuth_deg', 0.0))))
                up = (-dip * math.cos(az), -dip * math.sin(az), 1.0)
            self._slope = (g.mul(g.sub(r[0], r[1]), 1.0 / (2.0 * d)), up)
        return self._slope


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


# ------------------------------------------------------------------------------------ baked surface data ---

def _sock(ng, name, io, kind):
    t = {'f': 'NodeSocketFloat', 'v': 'NodeSocketVector', 'c': 'NodeSocketColor', 's': 'NodeSocketShader'}[kind]
    return ng.interface.new_socket(name, in_out=io, socket_type=t)


def _new_group(name, sig):
    """(group, fresh): the shader node group `name` when one with this signature exists (fresh False), else a new
    one (an older group of that name is replaced)."""
    old = bpy.data.node_groups.get(name)
    if old is not None:
        if old.get('eido_sig') == sig:
            return old, False
        bpy.data.node_groups.remove(old)
    ng = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    ng['eido_sig'] = sig
    return ng, True


def _tex(g, img, vec, interp='Linear', ext='REPEAT'):
    n = g.node('ShaderNodeTexImage', interpolation=interp, extension=ext)
    n.image = img
    g.set(n.inputs['Vector'], vec)
    return n


def reader_group(sd):
    """The two-slot level reader of a terrain's surface data (SURFACING_DESIGN.md 2.4): one shader node group per
    terrain, eido_terrain_reader_<hash of its windows and atlas layouts>, shared by its near and far materials and by
    eido_terrain_map.

    In:  Position (object metres: the terrain keeps an identity transform), Footprint (metres a pixel spans there).
    Out: Detail Even, Detail Odd, Cell Even, Cell Odd: the atlas coordinates of the even and odd slots on the detail
         layout (D, E) and the cell layout (M, F, C, P); Odd Weight (the even slot takes the rest); Level (the finest
         window holding the pixel: the level of the ring that draws it); Even Level, Odd Level (what each slot
         reads); Hero Outside (metres outside the outermost hero window, Chebyshev; 1e6 without hero levels);
         Sel <k> (1 inside window k, for k >= 1).

    Per pixel: L counts the windows k >= 1 holding it; the even slot reads the finest even level holding it (else
    level 0), the odd slot the finest odd one (else level 1), so the slot of L's parity reads L and the other L - 1.
    L fades in over FADE_CELLS of its own cells behind a dead band of DEAD_FOOTPRINTS footprints inside its edge,
    capped by the room before the next finer window: w_L = smoothstep(z, z + 8 c_L, d_L), z = min(3 footprints,
    margin_{L+1} - 8 c_L), d_L the distance inside L's edge. A slot changes level only at a window edge, where its
    weight is exactly 0 on both sides, so the coarse mips a 2 x 2 quad straddling the jump reads count for nothing.
    Every per-level constant is a telescoping sum over the windows: q = q_first + sum_k sel_k (q_k - q_{k-step})."""
    rc = sd.reader_constants()
    lv = list(sd.levels)
    K = len(lv)
    geo = [[float(v.x0), float(v.y0), float(v.side), float(v.cell), str(getattr(v, 'role', ''))] for v in lv]
    sig = hashlib.sha1(json.dumps([rc, geo, DEAD_FOOTPRINTS, FADE_CELLS, 1], sort_keys=True,
                                  default=float).encode()).hexdigest()[:12]
    ng, fresh = _new_group(f'eido_terrain_reader_{sig}', sig)
    if not fresh:
        return ng
    for nm, kd in (('Position', 'v'), ('Footprint', 'f')):
        _sock(ng, nm, 'INPUT', kd)
    for nm in ('Detail Even', 'Detail Odd', 'Cell Even', 'Cell Odd'):
        _sock(ng, nm, 'OUTPUT', 'v')
    for nm in ('Odd Weight', 'Level', 'Even Level', 'Odd Level', 'Hero Outside'):
        _sock(ng, nm, 'OUTPUT', 'f')
    for k in range(1, K):
        _sock(ng, f'Sel {k}', 'OUTPUT', 'f')
    g = Graph(ng)
    gi, go = g.node('NodeGroupInput'), g.node('NodeGroupOutput')
    x, y, _z = g.separate_xyz(gi.outputs['Position'])
    fp = gi.outputs['Footprint']
    cx = [float(v.x0) + 0.5 * float(v.side) for v in lv]
    cy = [float(v.y0) + 0.5 * float(v.side) for v in lv]

    def cheb(ax, ay):
        return g.math('MAXIMUM', g.math('ABSOLUTE', g.sub(x, ax)), g.math('ABSOLUTE', g.sub(y, ay)))
    sel = [None] + [g.math('LESS_THAN', cheb(cx[k], cy[k]), 0.5 * float(lv[k].side)) for k in range(1, K)]

    def tele(vals, step=1, first=0):
        vals = [float(v) for v in vals]
        acc = vals[first]
        for k in range(first + step, K, step):
            d = vals[k] - vals[k - step]
            if d != 0.0:
                acc = g.math('MULTIPLY_ADD', sel[k], d, acc)
        return acc
    for k in range(1, K):
        g.set(go.inputs[f'Sel {k}'], sel[k])
    g.set(go.inputs['Level'], tele(range(K)))
    if K > 1:
        # L's centre, half side (level 0's: its whole side, more than any of its pixels lies inside it), cell,
        # parity, and the cap on its dead band (the room before the next finer window, less the fade)
        R = [float(lv[0].side)] + [0.5 * float(v.side) for v in lv[1:]]
        cap = []
        for k in range(K):
            if k + 1 < K:
                a, b = lv[k], lv[k + 1]
                m = min(b.x0 - a.x0, b.y0 - a.y0, a.x0 + a.side - b.x0 - b.side, a.y0 + a.side - b.y0 - b.side)
                cap.append(max(float(m) - FADE_CELLS * float(a.cell), 0.0))
            else:
                cap.append(1.0e6)
        d_in = g.sub(tele(R), cheb(tele(cx), tele(cy)))
        z = g.math('MINIMUM', g.mul(fp, DEAD_FOOTPRINTS), tele(cap))
        om = g.smoothstep(z, g.math('MULTIPLY_ADD', tele([v.cell for v in lv]), FADE_CELLS, z), d_in)
        par = tele([k % 2 for k in range(K)])
        g.set(go.inputs['Odd Weight'],
              g.math('MULTIPLY_ADD', par, g.math('MULTIPLY_ADD', om, 2.0, -1.0), g.sub(1.0, om)))
    else:
        g.set(go.inputs['Odd Weight'], 0.0)
    g.set(go.inputs['Even Level'], tele(range(K), 2, 0))
    g.set(go.inputs['Odd Level'], tele(range(K), 2, 1) if K > 1 else 0.0)
    for lay, tag in (('detail', 'Detail'), ('cell', 'Cell')):
        T = rc[lay]
        au = [t['du'] / t['side'] for t in T]
        bu = [t['u0'] - t['du'] * t['x0'] / t['side'] for t in T]
        av = [t['dv'] / t['side'] for t in T]
        bv = [t['v0'] - t['dv'] * t['y0'] / t['side'] for t in T]
        for first, slot in ((0, 'Even'), (1, 'Odd')):
            f0 = first if K > first else 0
            u = g.math('MULTIPLY_ADD', x, tele(au, 2, f0), tele(bu, 2, f0))
            v = g.math('MULTIPLY_ADD', y, tele(av, 2, f0), tele(bv, 2, f0))
            g.set(go.inputs[f'{tag} {slot}'], g.combine_xyz(u, v, 0.0))
    roles = [str(getattr(v, 'role', '')) for v in lv]
    if 'hero' in roles:
        h = roles.index('hero')
        g.set(go.inputs['Hero Outside'], g.sub(cheb(cx[h], cy[h]), 0.5 * float(lv[h].side)))
    else:
        g.set(go.inputs['Hero Outside'], 1.0e6)
    return ng


def hex_class(tile_m):
    """A layer's default hex lattice size, metres: its tile snapped to the ladder HEX_LADDER x 2^n (2.5, 5, 10,
    20, ...), so layers of like tiles share one lattice, and with it one hex grid in the shader (a grid placed per
    layer was a third of the shader's source). A hexagon then shows 0.2 to 0.4 of the tile's width."""
    return HEX_LADDER * 2.0 ** round(math.log2(max(float(tile_m), 1e-3) / HEX_LADDER))


def hex_grid_group(rotate=True):
    """eido_hex_grid (rotate False: eido_hex_grid_plain): hex tiling's triangle grid (SURFACING_DESIGN.md 3.3;
    Mikkelsen 2022, written from the published description), placed once per lattice (a frame and a size) and shared
    by every layer read on it.

    In:  Position (its x, y: metres along the frame's axes: world x, y for a planar read, a sector frame's strike and
         dip), Inverse Size (1 / hex_m), Seed.
    Out: per slot c = 0, 1, 2: RD<c> (the position from the slot's grid vertex, metres, turned by the slot's random
         angle), O<c> (its random offset, in tiles: x, y), W<c> (its barycentric weight) and, with rotate, CS<c>
         ((cos, sin, 0) of that angle). A read's coordinate is RD x (1 / tile) + O; its normal map's (nx, ny) turned
         back into the frame is (dot(n, CS), cross(CS, n).z).

    The grid is a triangle lattice of edge hex_m / (2 sqrt 3) (Mikkelsen's scaling): a point lies in one triangle,
    whose three vertices are its three reads. Reads go to slots by the vertex's class (i - j) mod 3 on the skewed
    lattice, which differs at the three corners of every triangle, so a slot's vertex changes only across the far
    edges of its hexagon of six triangles, where its weight is 0: the implicit derivatives' mip jump falls where the
    read counts for nothing. A read's coordinates are R (P - vertex) / tile + offset, small numbers near every
    vertex, so float32 keeps them exact far from the origin."""
    sig = f'hex{HEX_VERSION}{"r" if rotate else "p"}'
    ng, fresh = _new_group('eido_hex_grid' if rotate else 'eido_hex_grid_plain', sig)
    if not fresh:
        return ng
    _sock(ng, 'Position', 'INPUT', 'v')
    for nm in ('Inverse Size', 'Seed'):
        _sock(ng, nm, 'INPUT', 'f')
    for c in range(3):
        for nm, kd in (('RD', 'v'), ('O', 'v'), ('W', 'f')) + ((('CS', 'v'),) if rotate else ()):
            _sock(ng, f'{nm}{c}', 'OUTPUT', kd)
    g = Graph(ng)
    gi, go = g.node('NodeGroupInput'), g.node('NodeGroupOutput')
    P_in = gi.outputs['Position']
    U, V, _z = g.separate_xyz(P_in)
    k = g.mul(gi.outputs['Inverse Size'], 2.0 * math.sqrt(3.0))
    su, sv = g.mul(U, k), g.mul(V, k)
    a = g.math('MULTIPLY_ADD', sv, -0.57735027, su)        # skewed onto the triangle grid
    b = g.mul(sv, 1.15470054)
    bx, by = g.math('FLOOR', a), g.math('FLOOR', b)
    fx, fy = g.sub(a, bx), g.sub(b, by)
    t = g.add(fx, fy)
    s = g.math('GREATER_THAN', t, 1.0)                     # the upper triangle of the cell
    u1 = g.sub(1.0, t)
    W = (g.math('ABSOLUTE', u1), g.math('MULTIPLY_ADD', s, u1, fx), g.math('MULTIPLY_ADD', s, u1, fy))
    # the vertices: P0 = base + s (1, 1) of class k0, P1 = base + (1, 0) of class k0 + 1, P2 = base + (0, 1) of class
    # k0 + 2 (k0 = (i - j) mod 3 of the base); slot c takes P_j with j = (c - k0) mod 3
    k0 = g.math('FLOORED_MODULO', g.sub(bx, by), 3.0)
    e0 = g.math('LESS_THAN', k0, 0.5)
    e2 = g.math('GREATER_THAN', k0, 1.5)
    E = (e0, g.sub(g.sub(1.0, e0), e2), e2)
    hm = g.math('DIVIDE', 1.0, k)                          # a lattice unit in metres
    hv = g.mul(hm, 0.8660254)
    for c in range(3):
        ea, eb, ec = E[c], E[(c - 1) % 3], E[(c - 2) % 3]
        vx = g.add(bx, g.math('MULTIPLY_ADD', ea, s, eb))
        vy = g.add(by, g.math('MULTIPLY_ADD', ea, s, ec))
        w = g.math('MULTIPLY_ADD', ec, W[2], g.math('MULTIPLY_ADD', eb, W[1], g.mul(ea, W[0])))
        cu = g.mul(g.math('MULTIPLY_ADD', vy, 0.5, vx), hm)
        cv = g.mul(vy, hv)
        D = g.vmath('SUBTRACT', P_in, g.combine_xyz(cu, cv, 0.0))
        wn = g.node('ShaderNodeTexWhiteNoise', noise_dimensions='3D')
        g.set(wn.inputs['Vector'], g.combine_xyz(vx, vy, gi.outputs['Seed']))
        g.set(go.inputs[f'O{c}'], wn.outputs['Color'])     # (its third channel rides along: an image read takes x, y)
        g.set(go.inputs[f'W{c}'], w)
        if not rotate:
            g.set(go.inputs[f'RD{c}'], D)
            continue
        # the turn: u = du cos - dv sin, v = du sin + dv cos, as a dot and a cross product with (cos, -sin, 0)
        th = g.math('MULTIPLY_ADD', g.separate_rgb(wn.outputs['Color'])[2], 2.0 * math.pi, -math.pi)
        cs, sn = g.math('COSINE', th), g.math('SINE', th)
        csn = g.combine_xyz(cs, g.mul(sn, -1.0), 0.0)
        g.set(go.inputs[f'RD{c}'], g.combine_xyz(g.vmath('DOT_PRODUCT', D, csn),
                                                 g.separate_xyz(g.vmath('CROSS_PRODUCT', csn, D))[2], 0.0))
        g.set(go.inputs[f'CS{c}'], g.combine_xyz(cs, sn, 0.0))
    return ng


def _vmadd(g, a, b, c):
    """a x b + c on vectors (each a socket or a constant)."""
    n = g.node('ShaderNodeVectorMath', operation='MULTIPLY_ADD')
    g.set(n.inputs[0], a)
    g.set(n.inputs[1], b)
    g.set(n.inputs[2], c)
    return n.outputs[0]


def _hex_plan(layers, hexed, opt=None):
    """Per layer (planar lattice, turned, sector lattice, turned): its hex lattices in metres, 0 for one read.

    The planar lattice is hex_m (a layer's key, else the material option), by default hex_class(tile): Mikkelsen's
    scaling, a hexagon about 0.29 hex_m across showing 0.2 to 0.4 of the tile's width, turned at random (hex_rotate
    False: offsets only). On steep faces rock is directional (beds lie flat, stains and cracks run down the dip) and
    structured at the tile's scale: thirds of a 12 m cliff scan turned at random read as confetti on the canyon's
    walls (11-14). So the sector reads' lattice is steep_hex_m, by default STEEP_HEX x the class of the material's
    largest box tile (hexagons about half that tile across), not turned unless steep_rotate is set, for the box
    layers whose tile is at least steep_hex_share (STEEP_HEX_SHARE) of the largest: the cliff layers, which cover
    the faces over 47 degrees. A smaller box tile (talus, scree, slickrock under a cliff layer) reads each sector
    frame once: the sector reads were most of the compile (the canyon's three box layers, 11-18). Layers with the
    same lattice share one hex grid."""
    opt = opt or {}

    def pick(L, key, default):
        v = L.get(key) if L.get(key) is not None else opt.get(key)
        return default if v is None else v
    box_tiles = [float(L['tile_m']) for L in layers if L['projection'] == 'box']
    steep = STEEP_HEX * hex_class(max(box_tiles)) if box_tiles else 0.0
    share = float(opt.get('steep_hex_share', STEEP_HEX_SHARE) or 0.0)
    out = []
    for L in layers:
        ph = float(pick(L, 'hex_m', hex_class(L['tile_m'])))
        big = not box_tiles or float(L['tile_m']) >= share * max(box_tiles)
        sh = float(pick(L, 'steep_hex_m', steep if big else 0.0))
        if not hexed:
            ph = sh = 0.0
        if L['projection'] != 'box':
            sh = 0.0
        out.append((max(ph, 0.0), bool(pick(L, 'hex_rotate', True)), max(sh, 0.0), bool(pick(L, 'steep_rotate', False))))
    return out


def _layer_group(L, S, i, opt, box, plan):
    """One layer's scan reads as a node group (eido_layer_<hash>, shared by materials that read the same scan the same
    way). Out: Color (the scan's albedo), Height (its normalised height), Soft Height (the same reads' heights by
    their plain weights: continuous where the sharpened blend steps from one hexagon's read to the next, so a layer
    edge blended on it does not run along the hexagons), NX, NY (its normal in the world-XY tangent frame: the
    planar reads), Pert (box layers: the world-space tilt of the sector reads' normals), Rough, AO.

    plan: the layer's (planar lattice, turned, sector lattice, turned) of _hex_plan. A hex-tiled frame takes a hex
    grid's outputs as inputs (planar: P RD<c>, P O<c>, P W<c> and, turned, P CS<c>, for c = 0, 1, 2; the sector
    slots s = 0, 1: S<s> RD<c>, ...), so one grid serves every layer on its lattice; a frame with lattice 0 is read
    once. Planar reads: world (x, y) / tile, the albedo 'Auto' filtered (Cubic near, Linear far). Box layers (in:
    S0, S1 the two sector slots' frame coordinates (u, v, 0), W0 the even slot's weight, T0, B0, T1, B1 their
    tangent frames on the surface, Steep): planar on gentle ground and the two sector slots on steep faces, each
    slot in its own frame and mipmapped Linear; the slots and then planar against steep are height blended
    (a_i = w_i + h_i / 2, kept within 0.2 of the tallest), so a read with weight 0 counts for nothing and the switch
    follows the scan's own features rather than ghosting two layouts."""
    tile = float(L['tile_m'])
    hex_m, p_rot, s_hex_m, s_rot = plan
    ns = float(L['normal'])
    interp = opt['interpolation']
    dd = [float(v) for v in opt['detail_distance']]
    # 'Auto' with hex tiling: by default the hex reads are mipmapped Linear and one read at the plain world coordinate
    # takes over within detail_distance, its albedo Cubic (SURFACING_DESIGN.md 8.1's first lever: three Cubic reads
    # per planar layer took the canyon's compile to 1.6 x today's); near_hex True reads Cubic in every hex read
    near_hex = bool(opt.get('near_hex', False))
    # a box layer's far read on steep faces (the palette's far_scale, far_distance, far_contrast, far_bump and
    # macro_mod, as the material without baked data reads them): the scan once more at far_scale x the tile in each
    # sector frame, its brightness modulating the near read and its colour, height and normal taking over across
    # far_distance. A cliff's scan at its true 12 m tile is a fine grain from 100 m on; the larger joints and blocks
    # a wall shows at that distance are this read's (the canyon's walls, 11-14: without it they read as sandpaper).
    # Planar reads take none: flat ground's variation at those scales comes from the terrain's data
    far_k = float(opt.get('far_scale', 1.0) or 1.0) if box else 1.0
    wall = dict(k=far_k, d=[float(v) for v in opt.get('far_distance', (40.0, 200.0))],
                mm=float(L.get('macro_mod', opt.get('macro_mod', 0.0)) or 0.0),
                fc=float(L.get('far_contrast', opt.get('far_contrast', 0.65))),
                fb=float(opt.get('far_bump', 0.5)), fh=bool(L.get('far_height', True))) if far_k > 1.0 else None
    sig = json.dumps([S['albedo'].name, S['nrao'].name, tile, hex_m, p_rot, s_hex_m, s_rot, ns, interp, dd,
                      bool(box), i, wall, near_hex, HEX_VERSION])
    ng, fresh = _new_group('eido_layer_' + hashlib.sha1(sig.encode()).hexdigest()[:12], sig)
    if not fresh:
        return ng
    for prefix, size, turned in (('P', hex_m, p_rot),) + ((('S0', s_hex_m, s_rot), ('S1', s_hex_m, s_rot))
                                                           if box else ()):
        if size > 0.0:
            for c in range(3):
                for nm, kd in (('RD', 'v'), ('O', 'v'), ('W', 'f')) + ((('CS', 'v'),) if turned else ()):
                    _sock(ng, f'{prefix} {nm}{c}', 'INPUT', kd)
    if box:
        for nm in ('S0', 'S1', 'T0', 'B0', 'T1', 'B1'):
            _sock(ng, nm, 'INPUT', 'v')
        for nm in ('W0', 'Steep'):
            _sock(ng, nm, 'INPUT', 'f')
    _sock(ng, 'Color', 'OUTPUT', 'c')
    for nm in ('Height', 'Soft Height', 'NX', 'NY', 'Rough', 'AO'):
        _sock(ng, nm, 'OUTPUT', 'f')
    _sock(ng, 'Pert', 'OUTPUT', 'v')
    g = Graph(ng)
    gi, go = g.node('NodeGroupInput'), g.node('NodeGroupOutput')
    far = g.handover(*dd) if interp == 'Auto' else None
    inv = 1.0 / tile

    def albedo(vec, auto):
        if auto and interp == 'Auto':
            c1 = _tex(g, S['albedo'], vec, 'Cubic')
            c2 = _tex(g, S['albedo'], vec, 'Linear')
            return (g.mix('RGBA', far, c1.outputs['Color'], c2.outputs['Color']),
                    g.mix('FLOAT', far, c1.outputs['Alpha'], c2.outputs['Alpha']))
        n = _tex(g, S['albedo'], vec, 'Linear' if interp == 'Auto' else interp)
        return n.outputs['Color'], n.outputs['Alpha']

    def one(vec, auto, cs=None):
        """One read of the scan at vec. cs: the (cos, sin, 0) of a turned read, whose normal is turned back into
        the frame: (nx cos + ny sin, ny cos - nx sin) = (dot(n, cs), cross(cs, n).z)."""
        col, h = albedo(vec, auto)
        nr = _tex(g, S['nrao'], vec, 'Linear')
        r, gg, rough = g.separate_rgb(nr.outputs['Color'])
        if cs is None:
            nx = g.math('MULTIPLY_ADD', r, 2.0 * ns, -ns)
            ny = g.math('MULTIPLY_ADD', gg, 2.0 * ns, -ns)
        else:
            nv = _vmadd(g, nr.outputs['Color'], (2.0 * ns, 2.0 * ns, 0.0), (-ns, -ns, 0.0))
            nx = g.vmath('DOT_PRODUCT', nv, cs)
            ny = g.separate_xyz(g.vmath('CROSS_PRODUCT', cs, nv))[2]
        return dict(col=col, h=h, hs=h, nx=nx, ny=ny, rough=rough, ao=nr.outputs['Alpha'])

    def blend(reads, ws):
        """sum w_k read_k over reads (dicts), the weights sockets summing to 1."""
        out = {}
        for key in ('h', 'nx', 'ny', 'rough', 'ao'):
            acc = g.mul(reads[0][key], ws[0])
            for r, w in zip(reads[1:], ws[1:]):
                acc = g.math('MULTIPLY_ADD', r[key], w, acc)
            out[key] = acc
        acc = g.vmath('SCALE', reads[0]['col'], scale=ws[0])
        for r, w in zip(reads[1:], ws[1:]):
            acc = g.vmath('ADD', acc, g.vmath('SCALE', r['col'], scale=w))
        out['col'] = acc
        return out

    def frame(prefix, pos, auto, size, turned):
        """A frame's read: one read at pos x (1 / tile) (lattice 0), or the three reads of its hex grid (the group's
        inputs `prefix` RD<c>, O<c>, W<c>, CS<c>), sharpened by w^7 and their heights; with 'Auto' filtering and
        near_hex off, the hex reads mipmapped Linear and, within detail_distance, one read at the plain world
        coordinate cross-faded over them (near_read)."""
        if size <= 0.0:
            return one(g.vmath('SCALE', pos, scale=inv), auto)
        near_one = auto and interp == 'Auto' and not near_hex
        o = gi.outputs
        reads, ws = [], []
        for c in range(3):
            r = one(_vmadd(g, o[f'{prefix} RD{c}'], (inv, inv, 0.0), o[f'{prefix} O{c}']), auto and not near_one,
                    o[f'{prefix} CS{c}'] if turned else None)
            reads.append(r)
            ws.append(g.mul(g.math('POWER', o[f'{prefix} W{c}'], HEX_POWER),
                            g.math('MULTIPLY_ADD', r['h'], 2.0 * HEX_CONTRAST, 1.0 - HEX_CONTRAST)))
        tot = g.math('DIVIDE', 1.0, g.math('MAXIMUM', g.add(g.add(ws[0], ws[1]), ws[2]), 1e-6))
        out = blend(reads, [g.mul(w, tot) for w in ws])
        # the soft height: the three reads' heights by their plain barycentric weights (they sum to 1), a continuous
        # field with no step at a hexagon's border. Each hexagon still shows another part of the scan, whose height
        # stands a little higher or lower on average, and a layer edge blended on that follows the lattice (teeth
        # of 1.5 to 3.5 m along the cliff's edge on the canyon's brink wall): so the soft height's swing about 0.5
        # is scaled down where a hexagon is wider than BLEND_PATCH_M, to the swing a hexagon of that width gives
        hs = g.math('MULTIPLY_ADD', reads[2]['h'], o[f'{prefix} W2'],
                    g.math('MULTIPLY_ADD', reads[1]['h'], o[f'{prefix} W1'], g.mul(reads[0]['h'], o[f'{prefix} W0'])))
        f = min(1.0, BLEND_PATCH_M / (HEX_PATCH * size))
        out['hs'] = hs if f >= 1.0 else g.math('MULTIPLY_ADD', g.sub(hs, 0.5), f, 0.5)
        if near_one:
            out = near_read(out)
        return out

    def near_read(hexed_out):
        """Within detail_distance: one read at the plain world coordinate, its albedo Cubic (sharp at grazing angles
        at the walker's feet) and its normal map Linear at the same coordinate (so colour and shading stay one
        stone), cross-faded to the hex blend over detail_distance (Linear beyond: still in motion far off)."""
        P0 = g.vmath('SCALE', g.node('ShaderNodeTexCoord').outputs['Object'], scale=inv)
        cn = _tex(g, S['albedo'], P0, 'Cubic')
        nr = _tex(g, S['nrao'], P0, 'Linear')
        r, gg, rough = g.separate_rgb(nr.outputs['Color'])
        near = dict(col=cn.outputs['Color'], h=cn.outputs['Alpha'], hs=cn.outputs['Alpha'],
                    nx=g.math('MULTIPLY_ADD', r, 2.0 * ns, -ns), ny=g.math('MULTIPLY_ADD', gg, 2.0 * ns, -ns),
                    rough=rough, ao=nr.outputs['Alpha'])
        return {key: g.mix('RGBA' if key == 'col' else 'FLOAT', far, near[key], v) for key, v in hexed_out.items()}

    def height_pair(wa, ha, hb):
        """(a's share, b's share) of two reads by weight wa (b's 1 - wa) and height: a_i = w_i + h_i / 2, kept within
        0.2 of the taller, normalised."""
        aa = g.math('MULTIPLY_ADD', ha, 0.5, wa)
        ab = g.math('MULTIPLY_ADD', hb, 0.5, g.sub(1.0, wa))
        ma = g.sub(g.math('MAXIMUM', aa, ab), 0.2)
        ba = g.math('MAXIMUM', g.sub(aa, ma), 0.0)
        bb = g.math('MAXIMUM', g.sub(ab, ma), 0.0)
        tot = g.math('DIVIDE', 1.0, g.math('MAXIMUM', g.add(ba, bb), 1e-5))
        return g.mul(ba, tot), g.mul(bb, tot)
    p = frame('P', None if hex_m > 0.0 else g.node('ShaderNodeTexCoord').outputs['Object'], True, hex_m, p_rot)
    if not box:
        for nm, key in (('Color', 'col'), ('Height', 'h'), ('Soft Height', 'hs'), ('NX', 'nx'), ('NY', 'ny'),
                        ('Rough', 'rough'), ('AO', 'ao')):
            g.set(go.inputs[nm], p[key])
        g.set(go.inputs['Pert'], (0.0, 0.0, 0.0))
        return ng
    sec = [frame(f'S{s}', gi.outputs[f'S{s}'], False, s_hex_m, s_rot) for s in (0, 1)]
    we, wo = height_pair(gi.outputs['W0'], sec[0]['h'], sec[1]['h'])
    sb = blend(sec, [we, wo])
    hs_steep = g.mix('FLOAT', gi.outputs['W0'], sec[1]['hs'], sec[0]['hs'])
    pert = None
    for s, w in ((0, we), (1, wo)):
        t = g.vmath('ADD', g.vmath('SCALE', gi.outputs[f'T{s}'], scale=sec[s]['nx']),
                    g.vmath('SCALE', gi.outputs[f'B{s}'], scale=sec[s]['ny']))
        t = g.vmath('SCALE', t, scale=w)
        pert = t if pert is None else g.vmath('ADD', pert, t)
    if wall is not None:
        # the far read, one per sector slot (a slot's frame changes only where its plain weight is 0), albedo and
        # height from one image, the normal from the other at far_bump of its slopes; the two slots height blended
        # as the near reads are (a plain blend ghosted the two frames' patterns where a face's bearing lies between
        # sectors: the 0.98 m wall's grid at 300 m, 11-18)
        fd = g.smoothstep(wall['d'][0], wall['d'][1], g.view_distance())
        inv_f = inv / wall['k']
        nsf = ns * wall['fb']
        slot = []
        for s in (0, 1):
            vec = _vmadd(g, gi.outputs[f'S{s}'], (inv_f, inv_f, 0.0),
                         (0.37 + 0.21 * i + 0.5 * s, 0.71 - 0.17 * i + 0.3 * s, 0.0))
            a = _tex(g, S['albedo'], vec, 'Linear')
            nr = _tex(g, S['nrao'], vec, 'Linear')
            r, gg, _b = g.separate_rgb(nr.outputs['Color'])
            t = g.vmath('ADD', g.vmath('SCALE', gi.outputs[f'T{s}'], scale=g.math('MULTIPLY_ADD', r, 2.0 * nsf, -nsf)),
                        g.vmath('SCALE', gi.outputs[f'B{s}'], scale=g.math('MULTIPLY_ADD', gg, 2.0 * nsf, -nsf)))
            slot.append((a.outputs['Color'], a.outputs['Alpha'], t))
        fwe, fwo = height_pair(gi.outputs['W0'], slot[0][1], slot[1][1])
        fcol = g.vmath('ADD', g.vmath('SCALE', slot[0][0], scale=fwe), g.vmath('SCALE', slot[1][0], scale=fwo))
        fh = g.math('MULTIPLY_ADD', slot[1][1], fwo, g.mul(slot[0][1], fwe))
        fpert = g.vmath('ADD', g.vmath('SCALE', slot[0][2], scale=fwe), g.vmath('SCALE', slot[1][2], scale=fwo))
        mean_lin = [float(v) for v in S['stats']['mean_albedo_linear']]
        near = sb['col']
        if wall['mm'] > 0.0:                              # the scan as its own macro variation map
            ml = max(sum(a_ * b_ for a_, b_ in zip(mean_lin, _LUMA)), 1e-4)
            lum = g.vmath('DOT_PRODUCT', fcol, _LUMA)
            mod = g.math('MINIMUM', g.math('MAXIMUM', g.math('MULTIPLY_ADD', lum, wall['mm'] / ml, 1.0 - wall['mm']),
                                           0.55), 1.6)
            near = g.vmath('SCALE', near, scale=mod)
        if wall['fc'] != 1.0:                             # the larger pattern, toned down around the scan's mean
            fcol = g.vmath('ADD', g.vmath('SCALE', fcol, scale=wall['fc']),
                           tuple((1.0 - wall['fc']) * v for v in mean_lin))
        sb['col'] = g.mix('RGBA', fd, near, fcol)
        if wall['fh']:
            sb['h'] = g.mix('FLOAT', fd, sb['h'], fh)
            hs_steep = g.mix('FLOAT', fd, hs_steep, fh)
        pert = g.mix('VECTOR', fd, pert, fpert)
    g.set(go.inputs['Soft Height'], g.mix('FLOAT', gi.outputs['Steep'], p['hs'], hs_steep))
    wp, ws_ = height_pair(g.sub(1.0, gi.outputs['Steep']), p['h'], sb['h'])
    out = blend([p, sb], [wp, ws_])
    g.set(go.inputs['Color'], out['col'])
    for nm, key in (('Height', 'h'), ('Rough', 'rough'), ('AO', 'ao')):
        g.set(go.inputs[nm], out[key])
    g.set(go.inputs['NX'], g.mul(p['nx'], wp))
    g.set(go.inputs['NY'], g.mul(p['ny'], wp))
    g.set(go.inputs['Pert'], g.vmath('SCALE', pert, scale=ws_))
    return ng


_SHADER_NAMES = ('slope', 'aspect', 'northness', 'eastness', 'insolation', 'height', 'slope_20m')


class _Data:
    """A material's reads of baked surface data (terrain/surface SurfaceData) through the two-slot reader: has(name),
    value(name) (a decoded map: the even and odd slots' reads mixed by the reader's weight), colour(family) (C or P,
    linear), the field normal and the macro normal (the field normal plus the relief below the cell)."""

    def __init__(self, g, sd, names, coords, fp, consts, tile_m=4.0, detail_strength=DETAIL_STRENGTH, cubic=True):
        from ..surface import maps as MP
        self.g, self.sd, self.MP = g, sd, MP
        self.coords = coords
        self.consts = consts
        self.fp = fp
        self.cubic = bool(cubic)
        self._mini = {}
        want = set()
        for n in names:
            for m in (MP.PAIRS.get(n) or (n,)):
                try:
                    if MP.spec(m).family == 'M' and sd.has(m):
                        want.add(m)
                except KeyError:
                    pass
        have = {n for grp in sd.packing() for n in grp}
        if not want <= have:
            sd.pack(sorted(have | want))
        self.images = sd.images()
        self.rd = g.node('ShaderNodeGroup')
        self.rd.node_tree = reader_group(sd)
        g.set(self.rd.inputs['Position'], coords)
        g.set(self.rd.inputs['Footprint'], fp)
        self.w_odd = self.rd.outputs['Odd Weight']
        self.K = len(sd.levels)
        self._fam, self._sep, self._chan, self._val = {}, {}, {}, {}
        self.tile_m = float(tile_m)
        self.detail_strength = float(detail_strength)
        self._nf = None
        self._nm = None

    # ---- what there is
    def has(self, name):
        if name in _SHADER_NAMES:
            if name == 'slope_20m':
                return 'n20_x' in self._packed() and 'n20_y' in self._packed()
            return 'D' in self.images
        try:
            fam, _ch, _rule = self.sd.channel(name)
        except KeyError:
            return False
        return fam in self.images

    def has_family(self, fam):
        return fam in self.images

    def _packed(self):
        return {n for grp in self.sd.packing() for n in grp}

    # ---- reads
    def fam(self, f):
        """A family's two slot reads, [(Color, Alpha) even, (Color, Alpha) odd]: mipmapped Linear. The families in
        CUBIC_FAMILIES (with cubic) are also read bicubic, and that read is taken where a texel is magnified (a
        pixel spans under CUBIC_PX[0] of it; the mipmapped read past CUBIC_PX[1]): a threshold on a bilinear read
        of a sharp slope break follows the texel grid in a staircase, which a steep face stretches by 1 / cos(its
        slope) into teeth down the dip (the canyon's brink wall: a 0.98 m texel, teeth of 1 by 3 m, 11-14). The
        bicubic read is the same image in the same sampler."""
        if f not in self._fam:
            g = self.g
            lay = 'Detail' if f in ('D', 'E') else 'Cell'
            out = []
            for s, slot in enumerate(('Even', 'Odd')):
                lin = _tex(g, self.images[f], self.rd.outputs[f'{lay} {slot}'], 'Linear', 'EXTEND')
                col, alpha = lin.outputs['Color'], lin.outputs['Alpha']
                if self.cubic and f in CUBIC_FAMILIES:
                    cub = _tex(g, self.images[f], self.rd.outputs[f'{lay} {slot}'], 'Cubic', 'EXTEND')
                    w = self._minified(lay, s)
                    col = g.mix('RGBA', w, cub.outputs['Color'], col)
                    alpha = g.mix('FLOAT', w, cub.outputs['Alpha'], alpha)
                out.append((col, alpha))
            self._fam[f] = out
        return self._fam[f]

    def _minified(self, lay, s):
        """0 where a pixel spans under CUBIC_PX[0] of slot s's texel on the layout, 1 past CUBIC_PX[1]."""
        key = (lay, s)
        if key not in self._mini:
            tex = [float(t['texel']) for t in self.sd.reader_constants()['detail' if lay == 'Detail' else 'cell']]
            r = self.g.math('DIVIDE', self.fp, self.slot_const(tex, s))
            self._mini[key] = self.g.smoothstep(CUBIC_PX[0], CUBIC_PX[1], r)
        return self._mini[key]

    def chan(self, f, c):
        key = (f, c)
        if key not in self._chan:
            pair = []
            for s, (col, alpha) in enumerate(self.fam(f)):
                if c == 3:
                    pair.append(alpha)
                else:
                    if (f, s) not in self._sep:
                        self._sep[(f, s)] = self.g.separate_rgb(col)
                    pair.append(self._sep[(f, s)][c])
            self._chan[key] = tuple(pair)
        return self._chan[key]

    def mix(self, e, o):
        return self.g.mix('FLOAT', self.w_odd, e, o)

    def slot_const(self, vals, slot):
        """A per-level constant as the slot (0 even, 1 odd) reads it: telescoped over that parity's windows."""
        g = self.g
        vals = [float(v) for v in vals]
        first = slot if self.K > slot else 0
        acc = vals[first]
        for k in range(first + 2, self.K, 2):
            d = vals[k] - vals[k - 2]
            if d != 0.0:
                acc = g.math('MULTIPLY_ADD', self.rd.outputs[f'Sel {k}'], d, acc)
        return acc

    def value(self, name):
        if name in self._val:
            return self._val[name]
        if name in _SHADER_NAMES:
            v = self._derived(name)
        else:
            fam, ch, (kind, a, b) = self.sd.channel(name)
            if isinstance(ch, tuple):
                raise KeyError(f'{name!r} is a pair: read its channels by their own names')
            v = self._decode(fam, ch, kind, a, b)
        self._val[name] = v
        return v

    def _decode(self, fam, ch, kind, a, b):
        g = self.g
        e, o = self.chan(fam, ch)
        if kind == 'affine':
            if not isinstance(a, (tuple, list)) and not isinstance(b, (tuple, list)):
                m = self.mix(e, o)
                return m if (float(a) == 1.0 and float(b) == 0.0) else g.math('MULTIPLY_ADD', m, float(a), float(b))
            av = a if isinstance(a, (tuple, list)) else [a] * self.K
            bv = b if isinstance(b, (tuple, list)) else [b] * self.K
            return self.mix(g.math('MULTIPLY_ADD', e, self.slot_const(av, 0), self.slot_const(bv, 0)),
                            g.math('MULTIPLY_ADD', o, self.slot_const(av, 1), self.slot_const(bv, 1)))
        if kind == 'square':
            return self.mix(g.mul(g.mul(e, e), float(a)), g.mul(g.mul(o, o), float(a)))
        if kind == 'z_plus':
            bv = b if isinstance(b, (tuple, list)) else [b] * self.K
            z = g.separate_xyz(self.coords)[2]
            return g.add(z, self.mix(g.add(e, self.slot_const(bv, 0)), g.add(o, self.slot_const(bv, 1))))
        raise ValueError(f'decode rule {kind!r}')

    def colour(self, fam):
        """The linear colour of C or P (the images are sRGB: the GPU hands the shader linear values)."""
        key = ('colour', fam)
        if key not in self._val:
            (e, _ea), (o, _oa) = self.fam(fam)
            self._val[key] = self.g.mix('RGBA', self.w_odd, e, o)
        return self._val[key]

    # ---- normals and the derived names
    def n_field(self):
        """(nx, ny, nz, N): the field normal from D (the two slots' x, y mixed, z rebuilt)."""
        if self._nf is None:
            g = self.g
            nx, ny = self.value_raw('normal_x'), self.value_raw('normal_y')
            nz = g.math('SQRT', g.math('MAXIMUM', g.sub(g.sub(1.0, g.mul(nx, nx)), g.mul(ny, ny)), 1e-4))
            N = g.vmath('NORMALIZE', g.combine_xyz(nx, ny, nz))
            self._nf = (nx, ny, nz, N)
        return self._nf

    def value_raw(self, name):
        if name not in self._val:
            fam, ch, (kind, a, b) = self.sd.channel(name)
            self._val[name] = self._decode(fam, ch, kind, a, b)
        return self._val[name]

    def n_macro(self):
        """The macro normal: the field normal tilted by the relief below the cell, normalize(nx / nz - s k gx,
        ny / nz - s k gy, 1) with s the detail strength and k the level's fade (the relief's finest octave, two of
        D's texels, against the scans' tile: under one tile the scans' own normals carry that band)."""
        if self._nm is None:
            g = self.g
            nx, ny, nz, _N = self.n_field()
            if self.detail_strength > 0.0 and self.has('detail_gx'):
                lam = [2.0 * float(t['texel']) for t in self.sd.reader_constants()['detail']]
                kl = [float(P._smooth(self.tile_m, 2.0 * self.tile_m, v)) * self.detail_strength for v in lam]
                ks = self.mix(self.slot_const(kl, 0), self.slot_const(kl, 1)) if len(set(kl)) > 1 else kl[0]
                gx, gy = self.value_raw('detail_gx'), self.value_raw('detail_gy')
                if isinstance(ks, float) and ks == 0.0:
                    hx, hy = g.math('DIVIDE', nx, nz), g.math('DIVIDE', ny, nz)
                else:
                    hx = g.sub(g.math('DIVIDE', nx, nz), _mul(g, gx, ks))
                    hy = g.sub(g.math('DIVIDE', ny, nz), _mul(g, gy, ks))
                self._nm = g.vmath('NORMALIZE', g.combine_xyz(hx, hy, 1.0))
            else:
                self._nm = self.n_field()[3]
        return self._nm

    def _derived(self, name):
        g = self.g
        if name == 'height':
            return g.separate_xyz(self.coords)[2]
        if name == 'slope_20m':
            ax, ay = self.value('n20_x'), self.value('n20_y')
            nz = g.math('SQRT', g.math('MAXIMUM', g.sub(g.sub(1.0, g.mul(ax, ax)), g.mul(ay, ay)), 1e-6))
            return g.math('DEGREES', g.math('ARCCOSINE', g.math('MINIMUM', nz, 1.0)))
        nx, ny, nz, N = self.n_field()
        if name == 'slope':
            return g.math('DEGREES', g.math('ARCCOSINE', g.math('MINIMUM', g.separate_xyz(N)[2], 1.0)))
        if name == 'aspect':
            return g.math('FLOORED_MODULO', g.math('DEGREES', g.math('ARCTAN2', nx, ny)), 360.0)
        if name in ('northness', 'eastness'):
            r = g.math('SQRT', g.math('MAXIMUM', g.add(g.mul(nx, nx), g.mul(ny, ny)), 1e-12))
            fade = g.math('DIVIDE', g.smoothstep(1.0, 3.0, self.value('slope')), r)
            return g.mul(ny if name == 'northness' else nx, fade)
        if name == 'insolation':
            az, el = (math.radians(v) for v in P.climate_sun(self.consts))
            s = (math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el))
            return g.math('MAXIMUM', g.vmath('DOT_PRODUCT', N, s), 0.0)
        raise KeyError(name)


def _data_names(pal, weights):
    """The map names a palette's material reads with baked data (its weights as chosen, the patches it still draws,
    ramps, streaks, ledges, damp, tone, satmap, dusting, strata and provenance, patina, canopy)."""
    out = set()
    for L, w in zip(pal['layers'], weights):
        out |= P.names_in(w)
        for pt in _patch_list(L):
            if pt.get('where') and not pt.get('from_ramp'):
                out |= P.names_in(pt['where'])
        if L.get('ramp'):
            out |= P.names_in(L['ramp']['t'])
        for key in ('streaks_where',):
            if L.get(key):
                out |= P.names_in(L[key])
        if isinstance(L.get('ledges'), dict) and L['ledges'].get('where'):
            out |= P.names_in(L['ledges']['where'])
        prov = L.get('provenance') or {}
        if prov.get('src'):
            out.add('src_strata')
        if prov.get('down'):
            out.add('deposit')
        if L.get('patina') is not None:
            out.add('fresh')
        if L.get('canopy'):
            out |= {'canopy_far', 'canopy_expected'}
    o = pal['options']
    for key in ('damp_where', 'tone'):
        if o.get(key):
            out |= P.names_in(o[key])
    for key in ('satmap', 'dusting'):
        d = o.get(key)
        if isinstance(d, dict):
            for k in ('t', 'where'):
                if d.get(k):
                    out |= P.names_in(d[k])
    st = pal.get('strata')
    if st and st.get('source', 'attribute') == 'attribute' and any(L.get('strata') for L in pal['layers']):
        out.add('strata')
    if 'slope_20m' in out:
        out |= {'n20_x', 'n20_y'}
    return out


def _rgb3(v, default=1.0):
    """A multiplier as linear (r, g, b): a number, an (r, g, b), or an sRGB '#rrggbb' colour."""
    if v is None:
        v = default
    if isinstance(v, str):
        return tuple(P.hex_linear(v))
    if isinstance(v, (int, float)):
        return (float(v),) * 3
    return tuple(float(c) for c in v)[:3]


def _amount(v):
    return 1.0 if v is True else (0.0 if not v else float(v))


def _v3(c):
    """A colour for a vector socket: a constant as (r, g, b), a socket as it is."""
    return tuple(float(v) for v in c)[:3] if isinstance(c, (tuple, list)) else c


def _v4(c):
    """A colour for an RGBA socket: a constant as (r, g, b, 1), a socket as it is."""
    return tuple(float(v) for v in c)[:3] + (1.0,) if isinstance(c, (tuple, list)) else c


def _lut_image(pal):
    """(Image or None, {key: row info}): the palette's ramps (palettes.ramp_rows) as a 256 x R sRGB image, one row each,
    made once per content (eido_ramps_<hash>), read Closest (SURFACING_DESIGN.md 2.6: a filtered read bleeds rows)."""
    rows, index = P.ramp_rows(pal)
    if not len(rows):
        return None, {}
    rows = np.ascontiguousarray(rows, np.float32)
    nm = 'eido_ramps_' + hashlib.sha1(rows.tobytes()).hexdigest()[:10]
    img = bpy.data.images.get(nm)
    if img is None:
        R, W = rows.shape[:2]
        img = bpy.data.images.new(nm, W, R, alpha=True, float_buffer=False)
        img.colorspace_settings.name = 'sRGB'             # before the pixels (SURFACING_DESIGN.md 1.3, probe A3)
        img.alpha_mode = 'CHANNEL_PACKED'
        img.pixels.foreach_set(rows.ravel())
        img.update()
        try:
            img.pack()                                    # a saved .blend keeps it
        except RuntimeError:
            pass
    return img, index


def _sector_frames(g, dat, coords, Nm):
    """The two sector slots (SURFACING_DESIGN.md 3.4): per slot dict(U, V, w, T, B). The bearing phi is the azimuth of
    the field normal (the face's own, from D); the even slot reads the even sector nearest it (phi_k = k 45 degrees,
    k even), the odd slot the odd one; the even slot's weight is smoothstep(0.1, 0.9, s), s = |2 frac(phi / 90) - 1|
    (1 at an even sector's centre), so a slot changes sector only where its weight is exactly 0. Frame k: u = P . t_k
    along the strike, t_k = (-sin phi_k, cos phi_k, 0); v = P . b_k up the fixed dip, b_k = (-cos d cos phi_k,
    -cos d sin phi_k, sin d), d = SECTOR_DIP_DEG: constant linear maps of the world position, so a scan keeps its
    scale (at most 1/cos(25 deg) = 1.10 along the dip from 47 to 90 degrees). T, B: t_k and b_k on the shading
    normal's tangent plane, the frame of the slot's normal maps."""
    nx, ny, _nz, _N = dat.n_field()
    x, y, z = g.separate_xyz(coords)
    q = g.math('DIVIDE', g.math('ARCTAN2', ny, nx), 0.5 * math.pi)
    fl = g.math('FLOOR', q)
    s = g.math('ABSOLUTE', g.math('MULTIPLY_ADD', g.sub(q, fl), 2.0, -1.0))
    w_even = g.smoothstep(0.1, 0.9, s)
    cd, sd_ = math.cos(math.radians(SECTOR_DIP_DEG)), math.sin(math.radians(SECTOR_DIP_DEG))
    out = []
    for phi in (g.mul(g.math('ROUND', q), 0.5 * math.pi), g.mul(g.add(fl, 0.5), 0.5 * math.pi)):
        c, sn = g.math('COSINE', phi), g.math('SINE', phi)
        U = g.math('MULTIPLY_ADD', y, c, g.mul(x, g.mul(sn, -1.0)))
        V = g.math('MULTIPLY_ADD', z, sd_, g.mul(g.math('MULTIPLY_ADD', x, c, g.mul(y, sn)), -cd))
        T = g.combine_xyz(g.mul(sn, -1.0), c, 0.0)
        Tp = g.vmath('NORMALIZE', g.vmath('SUBTRACT', T, g.vmath('SCALE', Nm, scale=g.vmath('DOT_PRODUCT', T, Nm))))
        out.append(dict(P=g.combine_xyz(U, V, 0.0), T=Tp, B=g.vmath('CROSS_PRODUCT', Nm, Tp)))
    out[0]['w'] = w_even
    out[1]['w'] = g.sub(1.0, w_even)
    return out


def _count_samplers(ng):
    """(distinct images, samplers) a node group's image reads take, its subgroups included: one sampler per image
    and state, Linear and Cubic sharing (SURFACING_DESIGN.md 1.3, probe A)."""
    states = set()
    seen = set()

    def walk(tree):
        if tree.name in seen:
            return
        seen.add(tree.name)
        for n in tree.nodes:
            if n.bl_idname == 'ShaderNodeTexImage' and n.image is not None:
                states.add((n.image.name, 'closest' if n.interpolation == 'Closest' else 'filtered', n.extension))
            elif n.bl_idname == 'ShaderNodeGroup' and n.node_tree is not None:
                walk(n.node_tree)
    walk(ng)
    return len({s[0] for s in states}), len(states)


def _faded_smooth(g, comp, lo, hi, n, scale_m, detail):
    """smoothstep(lo, hi, n) of a raw Noise Texture Fac n (a patch, streak, damp or ledge noise of scale_m), the noise
    faded to its mean with the footprint and the edges widened by the spread it lost (RAW_HALF), so its mean cover
    stays put; as it was without a footprint."""
    f = comp.fade(scale_m)
    if isinstance(f, float):
        return g.smoothstep(lo, hi, n)
    nf = g.math('MULTIPLY_ADD', g.sub(n, 0.5), f, 0.5)
    hs = RAW_HALF[int(max(0, min(5, round(float(detail)))))]
    sp = g.math('MULTIPLY_ADD', f, -hs, hs)
    sgn = 1.0 if hi >= lo else -1.0
    return g.smoothstep(g.math('MULTIPLY_ADD', sp, -sgn, float(lo)), g.math('MULTIPLY_ADD', sp, sgn, float(hi)), nf)


def _layer_weights(pal, sd, log=None):
    """Each layer's weight expression with baked data: its weight, or its fallback where the weight reads a map the
    data lacks (SURFACING_DESIGN.md 5.3)."""
    out = []
    for L in pal['layers']:
        w = L['weight']
        miss = sorted(n for n in P.names_in(w) if not sd.has(n))
        if miss and L.get('fallback') is not None:
            if log:
                log(f"[surfacing] {pal['name']}/{L['name']}: the data lacks {', '.join(miss)}: its fallback weight")
            w = L['fallback']
        out.append(w)
    return out


def _main_cell(sd):
    lv = list(sd.levels)
    mains = [v for v in lv if getattr(v, 'role', '') == 'main']
    return float((mains[-1] if mains else lv[min(len(lv) - 1, 0)]).cell)


def far_distance(pal, sd):
    """D0, metres (SURFACING_DESIGN.md 3.7): where the near material hands off to the far colour C, the distance at
    which a main-level texel spans FAR_TEXEL_PX pixels (c_main / (2.5 pixel_angle)), or the option far_m."""
    opt = pal['options']
    if opt.get('far_m'):
        return float(opt['far_m'])
    consts = dict(P.CONSTANTS)
    consts.update(pal.get('constants') or {})
    return _main_cell(sd) / (FAR_TEXEL_PX * float(consts.get('pixel_angle') or P.CONSTANTS['pixel_angle']))


def set_far_distance(material, far_m):
    """Move a per-texel terrain material's hand-off to the far colour to far_m metres (D0: it fades over
    D0..1.5 D0), in place: a node value, so nothing is rebuilt or recompiled. material: a surface_material(data=...)
    or its node group. The far material's rings are chosen at apply_surface: call it again when D0 moves a camera's
    1.5 D0 across a ring. Returns the group."""
    ng = material if isinstance(material, bpy.types.NodeTree) else next(
        n.node_tree for n in material.node_tree.nodes if n.bl_idname == 'ShaderNodeGroup')
    nd = ng.nodes.get(FAR_FADE_NODE)
    if nd is None:
        raise ValueError(f'{ng.name}: no far hand-off (a material without baked data, or a bake without a palette)')
    nd.inputs['From Min'].default_value = float(far_m)
    nd.inputs['From Max'].default_value = 1.5 * float(far_m)
    ng['eido_far_m'] = float(far_m)
    if not isinstance(material, bpy.types.NodeTree):
        material['eido_far_m'] = float(far_m)
    return ng


def _surface_group_data(pal, sd, name, prefer, log):
    """surface_group with baked surface data (the module doc's second part)."""
    opt = pal['options']
    layers = pal['layers']
    sets = [packed_set(L['set'], prefer, log=log) for L in layers]
    ng = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    for nm, kd in (('BSDF', 's'), ('Base Color', 'c'), ('Roughness', 'f'), ('Normal', 'v')):
        _sock(ng, nm, 'OUTPUT', kd)
    g = Graph(ng)
    gout = g.node('NodeGroupOutput')
    coords = g.node('ShaderNodeTexCoord').outputs['Object']
    geo = g.geometry()
    Ng, Vin = geo.outputs['Normal'], geo.outputs['Incoming']
    consts = dict(P.CONSTANTS)
    consts.update(pal.get('constants') or {})
    pix = float(consts.get('pixel_angle') or P.CONSTANTS['pixel_angle'])
    vd = g.view_distance()
    ndv = g.math('ABSOLUTE', g.vmath('DOT_PRODUCT', Ng, Vin))
    vpix = g.mul(vd, pix)
    fp_read = g.math('DIVIDE', vpix, g.math('MAXIMUM', ndv, 0.05))     # the reader's dead band (2.4)
    fp = g.math('DIVIDE', vpix, g.math('MAXIMUM', ndv, 0.25))          # the noise terms' fade (3.2)
    detile = opt.get('detile') or 'offset'
    n3 = detile != 'offset'
    hexed = bool(opt['anti_tile']) and detile in ('rotate', 'hex')
    weights = _layer_weights(pal, sd, log)
    tiles = sorted(float(L['tile_m']) for L in layers)
    dat = _Data(g, sd, _data_names(pal, weights), coords, fp_read, consts, tile_m=tiles[len(tiles) // 2],
                detail_strength=float(opt.get('detail_strength', DETAIL_STRENGTH)))
    comp = _Compiler(g, coords, pal.get('constants'), noise3=n3, data=dat, fp=fp)
    nfx, nfy, nfz, Nf = dat.n_field()
    Nm = dat.n_macro()
    lut_img, lut_idx = _lut_image(pal)

    def lut(info, t):
        R = lut_img.size[1]
        W = lut_img.size[0]
        u = g.math('MULTIPLY_ADD', _clamp01(g, t), (W - 1.0) / W, 0.5 / W)
        n = _tex(g, lut_img, g.combine_xyz(u, (info['row'] + 0.5) / R, 0.0), 'Closest', 'EXTEND')
        return n.outputs['Color']

    def noise(pos, scale_m, detail, roughness, seed):
        return _noise3(g, pos, scale_m, detail=detail, roughness=roughness, seed=seed) if n3 else \
            g.noise(pos, 1.0 / float(scale_m), detail=detail, roughness=roughness, w=seed)
    box_any = any(L['projection'] == 'box' for L in layers)
    sec = _sector_frames(g, dat, coords, Nm) if box_any else None
    steep = g.smoothstep(math.cos(math.radians(STEEP_DEG[0])), math.cos(math.radians(STEEP_DEG[1])), nfz) \
        if box_any else None
    steep_face = None
    strata = None
    if pal.get('strata') and any(L['strata'] for L in layers):
        strata = _Strata(g, comp, pal['strata'], coords, pal['name'])
    # the hex grids: one per lattice (a frame: planar or a sector slot; a size; turned or not), shared by every
    # layer read on it (SURFACING_DESIGN.md 8.1: a grid placed per layer was a third of the shader's source)
    plan = _hex_plan(layers, hexed, opt)
    grids = {}

    def grid(frame, pos, size, turned):
        key = (frame, round(float(size), 6), bool(turned))
        if key not in grids:
            nd = g.node('ShaderNodeGroup')
            nd.node_tree = hex_grid_group(turned)
            g.set(nd.inputs['Position'], pos)
            nd.inputs['Inverse Size'].default_value = 1.0 / float(size)
            nd.inputs['Seed'].default_value = 7.1 + 13.7 * len(grids)
            grids[key] = nd
        return grids[key]
    per = []
    for i, (L, S) in enumerate(zip(layers, sets)):
        cov = _clamp01(g, comp(P.parse(weights[i])))
        box = L['projection'] == 'box'
        lg = g.node('ShaderNodeGroup')
        lg.node_tree = _layer_group(L, S, i, opt, box, plan[i])
        p_hex, p_rot, s_hex, s_rot = plan[i]
        frames = [('P', 'planar', coords, p_hex, p_rot)]
        if box:
            frames += [(f'S{s}', f'sector {s}', sec[s]['P'], s_hex, s_rot) for s in (0, 1)]
            for s in (0, 1):
                g.set(lg.inputs[f'S{s}'], sec[s]['P'])
                g.set(lg.inputs[f'T{s}'], sec[s]['T'])
                g.set(lg.inputs[f'B{s}'], sec[s]['B'])
            g.set(lg.inputs['W0'], sec[0]['w'])
            g.set(lg.inputs['Steep'], steep)
        for prefix, frame, pos, size, turned in frames:
            if size > 0.0:
                gn = grid(frame, pos, size, turned)
                for c in range(3):
                    for nm in ('RD', 'O', 'W') + (('CS',) if turned else ()):
                        g.set(lg.inputs[f'{prefix} {nm}{c}'], gn.outputs[f'{nm}{c}'])
        col, h, hs = lg.outputs['Color'], lg.outputs['Height'], lg.outputs['Soft Height']
        mean_lin = [float(v) for v in S['stats']['mean_albedo_linear']]
        mean = np.maximum(np.array(mean_lin, np.float64), 1e-4)
        contrast = float(L.get('contrast', 1.0))
        own = tuple(P.hex_linear(L['colour'])) if L['colour'] else None
        rp = lut_idx.get(L['name']) if (L.get('ramp') and lut_img is not None) else None
        base = own
        if rp is not None and rp['kind'] == 'colour':
            base = lut(rp, comp(P.parse(rp['t'])))         # the ramp's colour stands where `colour` stands
        smix = float(L['strata']) if L['strata'] is not True else 1.0
        prov = L.get('provenance') or {}
        band_rough = None
        if smix > 0 and strata is not None:
            band, band_rough = strata.band(float(L.get('strata_offset_m', 0.0)))
            src = _amount(prov.get('src'))
            if src > 0.0 and dat.has('src_strata'):
                # debris takes the column at its source's stratigraphic height: a red cone below red beds runs
                # down over grey ones, and the bands no longer climb the debris
                sb, sr = strata.band_at(dat.value('src_strata'))
                band = sb if src >= 1.0 else g.mix('RGBA', src, band, sb)
                band_rough = sr if src >= 1.0 else g.mix('FLOAT', src, band_rough, sr)
            target = band if (smix >= 1.0 or base is None) else g.mix('RGBA', smix, _v4(base), band)
        else:
            target = base
        tint_mult = None
        if rp is not None and rp['kind'] == 'tint':
            tint_mult = g.vmath('SCALE', lut(rp, comp(P.parse(rp['t']))), scale=float(rp['gain']))
            if target is not None:
                target = g.vmath('MULTIPLY', _v3(target), tint_mult)
                tint_mult = None
        down = _amount(prov.get('down'))
        if down > 0.0 and target is not None:
            cd = None
            share = 1.0
            if dat.has_family('P'):
                cd = dat.colour('P')
                share = dat.value('down_share')
            elif strata is not None and dat.has('src_strata'):
                cd = strata.band_at(dat.value('src_strata'))[0]      # P deferred: the debris' own provenance
            if cd is not None:
                k = _mul(g, _mul(g, g.smoothstep(0.1, 1.5, comp.attr('deposit')), share), down)
                pale = _rgb3(prov.get('pale'), 1.0)
                if pale != (1.0, 1.0, 1.0):
                    cd = g.vmath('MULTIPLY', cd, pale)
                target = g.mix('RGBA', k, _v4(target), cd)
        if target is not None:
            rel = g.vmath('MULTIPLY', col, tuple(1.0 / mean))
            if contrast != 1.0:
                rel = g.vmath('ADD', g.vmath('SCALE', rel, scale=contrast), (1.0 - contrast,) * 3)
            col = g.vmath('MULTIPLY', rel, _v3(target))
        if tint_mult is not None:
            col = g.vmath('MULTIPLY', col, tint_mult)
        if L['tint'] is not None:
            col = g.vmath('MULTIPLY', col, tuple(L['tint'])[:3])
        if L.get('patina') is not None and dat.has('fresh'):
            # weathered rock against fresh: the patina (varnish, lichen, iron stain) where the face stands, the
            # fresh gain where it fails
            pa, fg = _rgb3(L['patina']), _rgb3(L.get('fresh_gain'), 1.0)
            col = g.vmath('MULTIPLY', col, g.mix('VECTOR', dat.value('fresh'), pa, fg))
        rough = g.mul(lg.outputs['Rough'], float(L['roughness']))
        if band_rough is not None:
            rough = g.mul(rough, band_rough if smix >= 1.0 else g.mix('FLOAT', smix, 1.0, band_rough))
        relief_rv = relief_lv = None
        if smix >= 1.0 and strata is not None and L.get('relief', True) and strata.relief() is not None:
            relief_rv, relief_lv = strata.relief()
            shade = float(pal['strata'].get('relief_shade', 0.15))
            if shade > 0.0:
                col = g.vmath('SCALE', col, scale=g.math('MULTIPLY_ADD', relief_rv, shade, 1.0 - shade))
        nx, ny = lg.outputs['NX'], lg.outputs['NY']
        canopy_bump = None
        if L.get('canopy'):
            cn = _canopy(g, L['canopy'], coords, i)
            crown_m = float(L['canopy'].get('crown_m', 4.5))
            fc = comp.fade(crown_m)
            ccol = cn['col']
            if not isinstance(fc, float):
                # finer than a few pixels the crowns read their mean tone (the far colour's), not an aliasing
                # Voronoi
                cl = [0.5 * (a + b) * CANOPY_SHADE for a, b in zip(P.hex_linear(L['canopy'].get('colour', '#26371f')),
                                                                      P.hex_linear(L['canopy'].get('light', '#3d522c')))]
                gp = P.hex_linear(L['canopy'].get('gap', '#11160d'))
                mc = tuple(float(gq + (c - gq) * CANOPY_COVER) for gq, c in zip(gp, cl)) + (1.0,)
                ccol = g.mix('RGBA', fc, mc, ccol)
            kf = cn['far']
            if dat.has('canopy_far') and dat.has('canopy_expected'):
                # the stand-in crowns cover what the instances leave to the material: off where trees stand
                kf = _mul(g, kf, _clamp01(g, g.math('DIVIDE', dat.value('canopy_far'),
                                                    g.math('MAXIMUM', dat.value('canopy_expected'), 0.02))))
            col = g.mix('RGBA', kf, col, ccol)
            h = g.mix('FLOAT', kf, h, cn['h'])
            hs = g.mix('FLOAT', kf, hs, cn['h'])
            rough = g.mix('FLOAT', kf, rough, 0.9)
            nx, ny = g.mul(nx, g.sub(1.0, kf)), g.mul(ny, g.sub(1.0, kf))
            if float(L['canopy'].get('height_m', 3.0)) > 0:
                canopy_bump = _mul(g, _mul(g, cn['bump'], kf), fc)
            if L['canopy'].get('edge') and not isinstance(cov, float):
                t = cn['r_edge']
                cov = g.mix('FLOAT', kf, cov, g.smoothstep(g.sub(t, 0.05), g.add(t, 0.05), cov))
        for k, pt in enumerate(_patch_list(L)):
            if pt.get('from_ramp'):
                continue                                  # the ramp image draws it
            amount = float(pt.get('amount', 0.6))
            if pt.get('scale_m') is None:
                pm = amount
            else:
                det = float(pt.get('detail', 3.0))
                pn = noise(coords, float(pt['scale_m']), det, 0.55, 33.7 + 2.3 * i + 5.1 * k)
                pm = g.mul(_faded_smooth(g, comp, float(pt.get('lo', 0.42)), float(pt.get('hi', 0.62)), pn,
                                         float(pt['scale_m']), det), amount)
            if pt.get('where'):
                pm = _mul(g, pm, _clamp01(g, comp(P.parse(pt['where']))))
            if pt.get('tint'):
                ratio = np.array(pt['tint'][:3], np.float64)
            else:
                ref = np.array(P.hex_linear(L['colour'])) if L['colour'] else mean
                ratio = np.array(P.hex_linear(pt['colour'])) / np.maximum(ref, 1e-4)
            col = g.mix('RGBA', pm, col, g.vmath('MULTIPLY', col, tuple(float(v) for v in ratio)))
        if L.get('streaks'):
            if steep_face is None:
                steep_face = g.smoothstep(0.78, 0.5, nfz)
            st = [float(v) for v in L['streaks']]
            width, amount = st[0], st[1]
            lo, hi = (st[2], st[3]) if len(st) >= 4 else (0.45, 0.68)
            sv = g.vmath('MULTIPLY', coords, (1.0 / width, 1.0 / width, 1.0 / (8.0 * width)))
            sn = noise(sv, 1.0, 3.0, 0.55, 19.7 + 3.3 * i)
            dark = g.mul(g.mul(_faded_smooth(g, comp, lo, hi, sn, width, 3.0), amount), steep_face)
            if L.get('streaks_where'):
                dark = _mul(g, dark, _clamp01(g, comp(P.parse(L['streaks_where']))))
            col = g.vmath('SCALE', col, scale=g.sub(1.0, dark))
        relief_h = None
        if relief_rv is not None:
            relief_h = relief_rv
            ld = L.get('ledges')
            if ld:
                sc = float(ld.get('scale_m', 5.0))
                pn = noise(coords, sc, 3.0, 0.55, 51.3 + 3.1 * i)
                pm = g.mul(g.mul(relief_lv, _faded_smooth(g, comp, float(ld.get('lo', 0.38)), float(ld.get('hi', 0.6)),
                                                          pn, sc, 3.0)), float(ld.get('amount', 0.75)))
                if ld.get('where'):
                    pm = _mul(g, pm, _clamp01(g, comp(P.parse(ld['where']))))
                col = g.mix('RGBA', pm, col, g.vmath('MULTIPLY', col, tuple(float(v) for v in ld['tint'][:3])))
        if float(L.get('value', 1.0)) != 1.0:
            col = g.vmath('SCALE', col, scale=float(L['value']))
        col = g.vmath('MINIMUM', g.vmath('MAXIMUM', col, (0.0, 0.0, 0.0)), (0.95, 0.95, 0.95))
        ripple = None
        if L.get('ripples'):
            ripple = _ripples(g, coords, L['ripples'], i)
        bump_own = None
        if float(L['bump_m']) > 0 and (not box or not S['stats'].get('has_normal', True)):
            bump_own = float(L['bump_m'])                 # a set without a normal map keeps its height's bump
        per.append(dict(L=L, cov=cov, col=col, h=h, hs=hs, nx=nx, ny=ny, pert=lg.outputs['Pert'] if box else None,
                        rough=rough, ao=lg.outputs['AO'], box=box, ripple=ripple, canopy_bump=canopy_bump,
                        relief=relief_h, bump_own=bump_own))

    # the overlay of the macro data and the scans' heights (SURFACING_DESIGN.md 3.2 rule 2), then the composite: a
    # layer's coverage pushed up where d > 0.5 and down where d < 0.5, unchanged at 0 and 1 and in the mean when d's
    # mean is 0.5; d = 0.5 + height (h - 0.5) + crest crest + crest_fine crest_fine + crease crease (a layer's
    # overlay dict; by default its scan's height alone, so its edge follows the scan's grain). The height here and
    # in the height blend is the layer's soft height: on the sharpened hex blend's height a layer edge ran along
    # the hexagons' borders (a sawtooth of triangles on the canyon's brink wall)
    if opt.get('overlay', True):
        for p in per:
            if isinstance(p['cov'], float):
                continue
            ov = dict(height=1.0)
            ov.update(p['L'].get('overlay') or {})
            d = g.math('MULTIPLY_ADD', g.sub(p['hs'], 0.5), float(ov.get('height', 0.0)), 0.5) \
                if float(ov.get('height', 0.0)) else 0.5
            for key in ('crest', 'crest_fine', 'crease'):
                amt = float(ov.get(key, 0.0) or 0.0)
                if amt and dat.has(key):
                    term = dat.value(key)
                    if key != 'crest':                    # the texel-scale terms fade with the footprint
                        term = _mul(g, term, comp.fade(2.0 * _main_cell(sd) / 8.0))
                    d = g.math('MULTIPLY_ADD', term, amt, d)
            if isinstance(d, float):
                continue
            d = _clamp01(g, d)
            cv = p['cov']
            a_lo = g.mul(g.mul(cv, d), 2.0)
            a_hi = g.sub(1.0, g.mul(g.mul(g.sub(1.0, cv), g.sub(1.0, d)), 2.0))
            p['cov'] = g.mix('FLOAT', g.math('LESS_THAN', cv, 0.5), a_hi, a_lo)
    excl = [None] * len(per)
    rem = 1.0
    for i in range(len(per) - 1, -1, -1):
        excl[i] = _mul(g, per[i]['cov'], rem)
        rem = _mul(g, rem, _one_minus(g, per[i]['cov']))
    kb = float(opt['height_blend'])
    a = []
    for i, p in enumerate(per):
        ai = excl[i]
        if kb > 0:
            ai = g.add(ai, g.mul(p['hs'], kb))
        e = p['L']['edge_noise'] if p['L']['edge_noise'] is not None else float(opt['edge_noise'])
        if e > 0 and i > 0:
            n = noise(coords, 1.0 / 0.85, 3.0, 0.62, 11.1 + 7.3 * i)
            f = comp.fade(1.0 / 0.85)
            ai = g.add(ai, g.mul(g.sub(n, 0.5), _mul(g, f, 2.0 * e)))
        a.append(ai)
    if len(a) == 1:
        wn = [1.0]
    else:
        ma = a[0]
        for v in a[1:]:
            ma = g.math('MAXIMUM', ma, v)
        ma = g.sub(ma, float(opt['blend_depth']))
        b = [g.math('MAXIMUM', g.sub(v, ma), 0.0) for v in a]
        s = b[0]
        for v in b[1:]:
            s = g.add(s, v)
        s = g.math('MAXIMUM', s, 1e-5)
        wn = [g.math('DIVIDE', v, s) for v in b]

    def wsum(vals):
        acc = None
        for v, w in zip(vals, wn):
            if v is None:
                continue
            term = _mul(g, v, w)
            acc = term if acc is None else g.add(acc, term)
        return 0.0 if acc is None else acc

    def wsum_vec(vals):
        acc = None
        for v, w in zip(vals, wn):
            if v is None:
                continue
            term = g.vmath('SCALE', v, scale=w)
            acc = term if acc is None else g.vmath('ADD', acc, term)
        return acc
    albedo = wsum_vec([p['col'] for p in per])
    rough = wsum([p['rough'] for p in per])
    if opt['ao'] > 0:
        albedo = g.vmath('SCALE', albedo, scale=g.add(1.0 - opt['ao'], g.mul(wsum([p['ao'] for p in per]), opt['ao'])))
    if opt.get('tone'):
        tv = comp(P.parse(opt['tone']))
        if not isinstance(tv, float):
            albedo = g.vmath('SCALE', albedo, scale=g.math('MINIMUM', g.math('MAXIMUM', g.add(tv, 1.0), 0.4), 1.6))
        elif tv != 0.0:
            albedo = g.vmath('SCALE', albedo, scale=min(max(1.0 + tv, 0.4), 1.6))
    albedo = _macro(g, coords, albedo, opt.get('macro') or [], n3)
    if lut_img is not None and 'satmap' in lut_idx:
        si = lut_idx['satmap']
        albedo = g.vmath('MULTIPLY', albedo, g.vmath('SCALE', lut(si, comp(P.parse(si['t']))), scale=float(si['gain'])))
    if opt['damp'] > 0 or opt.get('damp_where'):
        dm = 0.0
        if opt['damp'] > 0:
            sc = float(opt.get('damp_scale_m', 6.25))
            dn = noise(coords, sc, 3.0, 0.6, 13.3)
            dm = g.mul(_faded_smooth(g, comp, 0.5, 0.68, dn, sc, 3.0), float(opt['damp']))
        if opt.get('damp_where'):
            dw = _clamp01(g, comp(P.parse(opt['damp_where'])))
            dm = dw if isinstance(dm, float) and dm == 0.0 else g.math('MAXIMUM', dm, dw)
        if not (isinstance(dm, float) and dm == 0.0):
            albedo = g.vmath('SCALE', albedo, scale=g.sub(1.0, g.mul(dm, 0.38)))
            rough = g.mul(rough, g.sub(1.0, g.mul(dm, 0.32)))

    # the far hand-off (SURFACING_DESIGN.md 3.7): past D0 the ground fades to its baked far colour C (x a faint grain
    # of the base layer's scan) over D0..1.5 D0 of view distance, never inside the hero windows (the second factor
    # fades it in over 64 main cells beyond the outermost one); both factors are continuous, so nothing steps at a
    # window edge, and a pixel's distance decides it whichever ring draws it
    D0 = far_distance(pal, sd)
    w_far = None
    if dat.has_family('C'):
        cm = _main_cell(sd)
        fade = g.smoothstep(D0, 1.5 * D0, vd)
        fade.node.name = FAR_FADE_NODE                    # set_far_distance moves it without a rebuild
        w_far = g.mul(fade, g.smoothstep(0.0, FAR_FADE_MAIN_CELLS * cm, dat.rd.outputs['Hero Outside']))
        fc_col = g.vmath('SCALE', dat.colour('C'), scale=_far_grain(g, layers[0], sets[0], coords))
        albedo = g.mix('RGBA', w_far, albedo, fc_col)
        rough = g.mix('FLOAT', w_far, rough, dat.value('far_roughness'))
    elif log:
        log(f"[surfacing] {pal['name']}: no far colour in the data (no palette bake): no far hand-off")

    # normals: the macro normal (field normal + relief below the cell), the planar reads' normal maps in its world-XY
    # tangent frame, the sector reads' tilts in their own frames, then the bumps
    nxs = wsum([p['nx'] for p in per])
    nys = wsum([p['ny'] for p in per])
    dot = g.vmath('DOT_PRODUCT', Nm, (1.0, 0.0, 0.0))
    Txy = g.vmath('NORMALIZE', g.vmath('SUBTRACT', (1.0, 0.0, 0.0), g.vmath('SCALE', Nm, scale=dot)))
    Bxy = g.vmath('CROSS_PRODUCT', Nm, Txy)
    nzs = g.math('SQRT', g.math('MAXIMUM', g.sub(g.sub(1.0, g.mul(nxs, nxs)), g.mul(nys, nys)), 0.0))
    nvec = g.vmath('ADD', g.vmath('ADD', g.vmath('SCALE', Txy, scale=nxs), g.vmath('SCALE', Bxy, scale=nys)),
                   g.vmath('SCALE', Nm, scale=nzs))
    pert = wsum_vec([p['pert'] for p in per])
    if pert is not None:
        nvec = g.vmath('ADD', nvec, pert)
    normal = g.vmath('NORMALIZE', nvec)
    keep = 1.0 if w_far is None else g.sub(1.0, w_far)
    # the beds in relief (hard beds out as ledges, soft ones back): an analytic tilt of the normal by the relief's
    # slope along the stratigraphic height, n' = normalize(n - k (up - (up . n) n)), k = weight x relief_m x
    # d(relief)/d(zs), weighted by the strata layers' own blended weights. No Bump node: a Bump evaluates its whole
    # height input three times, and the stratigraphic height reads the F atlas through the level reader
    if strata is not None and any(p['relief'] is not None for p in per):
        slope, up = strata.relief_slope()
        k = g.mul(_mul(g, _mul(g, wsum([1.0 if p['relief'] is not None else None for p in per]), keep),
                       strata.relief_m), slope)
        sg = g.vmath('SUBTRACT', up, g.vmath('SCALE', normal, scale=g.vmath('DOT_PRODUCT', normal, up)))
        normal = g.vmath('NORMALIZE', g.vmath('SUBTRACT', normal, g.vmath('SCALE', sg, scale=k)))
    # the bumps: ripples, canopy (and a scan without a normal map), each its own Bump node with its weight (cheap
    # coverages: every weight with its noise at its mean, composited) and the far fade in its Distance, computed
    # once outside the bump's height, so EEVEE's three evaluations of the height read only the height
    cheap = _Compiler(g, coords, pal.get('constants'), noise3=True, flat=True, attrs=comp.attrs, data=dat)
    bumped = [p['bump_own'] is not None or p['ripple'] is not None or p['canopy_bump'] is not None for p in per]
    if any(bumped):
        ccov = [_clamp01(g, cheap(P.parse(weights[i]))) if bumped[i] or any(bumped[:i]) else 0.0
                for i in range(len(per))]
        bw = [None] * len(per)
        crem = 1.0
        for i in range(len(per) - 1, -1, -1):
            bw[i] = _mul(g, ccov[i], crem) if bumped[i] else 0.0
            crem = _mul(g, crem, _one_minus(g, ccov[i]))
        for p, w in zip(per, bw):
            terms = []
            if p['bump_own'] is not None:
                terms.append((g.sub(p['h'], 0.5), p['bump_own']))
            if p['ripple'] is not None:
                terms.append((p['ripple'], 1.0))
            if p['canopy_bump'] is not None:
                terms.append((p['canopy_bump'], 1.0))
            for hgt, scale in terms:
                dist = _mul(g, _mul(g, w, keep), scale)
                if isinstance(dist, float) and dist == 0.0:
                    continue
                bp = g.node('ShaderNodeBump')
                bp.inputs['Strength'].default_value = 1.0
                g.set(bp.inputs['Distance'], dist)
                g.set(bp.inputs['Height'], hgt)
                g.set(bp.inputs['Normal'], normal)
                normal = bp.outputs['Normal']
    # a grazing pixel whose shading normal turns away from the camera is pulled toward the mesh's own normal, so it
    # never shades black (shadows stay geometric)
    facing = g.smoothstep(0.0, 0.1, g.vmath('DOT_PRODUCT', normal, Vin))
    normal = g.vmath('NORMALIZE', g.mix('VECTOR', facing, Ng, normal))
    if opt.get('dusting'):
        # powder and ash on every ledge and grain the scans and the macro normal draw, by the final normal
        du = opt['dusting']
        t0, t1 = du.get('slope_deg', (25.0, 45.0))
        nzf = g.separate_xyz(normal)[2]
        dm = g.mul(g.smoothstep(math.cos(math.radians(float(t1))), math.cos(math.radians(float(t0))), nzf),
                   float(du.get('amount', 0.6)))
        if du.get('where'):
            dm = _mul(g, dm, _clamp01(g, comp(P.parse(du['where']))))
        if w_far is not None:
            dm = _mul(g, dm, g.sub(1.0, w_far))
        albedo = g.mix('RGBA', dm, albedo, tuple(P.hex_linear(du.get('colour', '#f2f4f6'))) + (1.0,))

    bsdf = g.node('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Metallic'].default_value = 0.0
    # each layer's own specular, past D0 as well: the near weights are evaluated there anyway, and the palette's
    # default in their place (0.5 against the plant layers' 0.08-0.12) lit the far ground with sky reflection, 1.5 L
    # brighter and bluer than the near material across the hand-off (the canyon's band, 11-18)
    specs = [float(p['L'].get('specular', opt['specular'])) for p in per]
    spec = specs[0] if len(set(specs)) == 1 else wsum(specs)
    g.set(bsdf.inputs['Specular IOR Level'], spec)
    albedo = g.vmath('MINIMUM', albedo, (0.95, 0.95, 0.95))
    g.set(bsdf.inputs['Base Color'], albedo)
    rough_c = g.math('MINIMUM', g.math('MAXIMUM', rough, 0.02), 1.0) if not isinstance(rough, float) else rough
    g.set(bsdf.inputs['Roughness'], rough_c)
    g.set(bsdf.inputs['Normal'], normal)
    g.set(gout.inputs['BSDF'], bsdf.outputs['BSDF'])
    dbg = opt.get('debug')
    if dbg:
        em = g.node('ShaderNodeEmission')
        if dbg == 'weights':
            cols = [wn[-1], wn[-2] if len(wn) > 1 else 0.0, wn[-3] if len(wn) > 2 else 0.0]
            g.set(em.inputs['Color'], g.combine_xyz(*cols))
        elif dbg == 'layers':
            g.set(em.inputs['Color'], wsum_vec([DEBUG_COLOURS[i % len(DEBUG_COLOURS)] for i in range(len(per))])
                  if len(per) > 1 else DEBUG_COLOURS[0] + (1.0,))
        elif dbg == 'level':
            lvl = dat.rd.outputs['Level']
            g.set(em.inputs['Color'], g.combine_xyz(g.math('FRACT', g.mul(lvl, 0.37)), g.math('FRACT', g.mul(lvl, 0.61)),
                                                    g.math('FRACT', g.mul(lvl, 0.83))))
        else:
            g.set(em.inputs['Color'], albedo)
        g.set(gout.inputs['BSDF'], em.outputs['Emission'])
    g.set(gout.inputs['Base Color'], albedo)
    g.set(gout.inputs['Roughness'], rough_c)
    g.set(gout.inputs['Normal'], normal)
    nimg, nsamp = _count_samplers(ng)
    if nsamp > MAX_SAMPLERS:
        fams = sorted(f for f in dat.images if f.startswith('M'))
        raise ValueError(f"palette {pal['name']!r} with baked data takes {nsamp} samplers ({nimg} images); EEVEE "
                         f"allows about 30 ({MAX_SAMPLERS} with a margin): drop a layer, or read fewer masks (its "
                         f"{len(fams)} mask atlases, {', '.join(fams)}, take one each)")
    ng['eido_palette'] = pal['name']
    ng['eido_sets'] = [S['name'] for S in sets]
    ng['eido_images'] = nimg
    ng['eido_samplers'] = nsamp
    ng['eido_mask_packs'] = '[]'
    ng['eido_attributes'] = 0
    ng['eido_surface_key'] = str(sd.key)
    ng['eido_far_m'] = float(D0)
    ng['eido_hex'] = bool(hexed)
    return ng


def _far_grain(g, L, S, coords):
    """1 + FAR_GRAIN (luminance / mean - 1) of the base layer's scan read once (mipmapped, planar): the faint grain the
    far colour keeps of the ground it stands for."""
    mean_lin = [float(v) for v in S['stats']['mean_albedo_linear']]
    ml = max(sum(a * b for a, b in zip(mean_lin, _LUMA)), 1e-4)
    n = _tex(g, S['albedo'], g.vmath('SCALE', coords, scale=1.0 / float(L['tile_m'])), 'Linear')
    lum = g.vmath('DOT_PRODUCT', n.outputs['Color'], _LUMA)
    return g.math('MULTIPLY_ADD', lum, FAR_GRAIN / ml, 1.0 - FAR_GRAIN)


def far_group(palette, data, name='eido_terrain_far', prefer='2k', log=print):
    """The far material's node group (SURFACING_DESIGN.md 3.7): the baked far colour C and its roughness, the macro
    normal from D, the base layer's faint grain, no layers. What the near material shows past 1.5 D0, for rings
    lying beyond that from every camera: a cost saving only."""
    pal = P.get(palette) if not (isinstance(palette, dict) and 'options' in palette) else palette
    opt = pal['options']
    L0 = pal['layers'][0]
    S0 = packed_set(L0['set'], prefer, log=log)
    ng = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    for nm, kd in (('BSDF', 's'), ('Base Color', 'c'), ('Roughness', 'f'), ('Normal', 'v')):
        _sock(ng, nm, 'OUTPUT', kd)
    g = Graph(ng)
    gout = g.node('NodeGroupOutput')
    coords = g.node('ShaderNodeTexCoord').outputs['Object']
    geo = g.geometry()
    consts = dict(P.CONSTANTS)
    consts.update(pal.get('constants') or {})
    pix = float(consts.get('pixel_angle') or P.CONSTANTS['pixel_angle'])
    ndv = g.math('ABSOLUTE', g.vmath('DOT_PRODUCT', geo.outputs['Normal'], geo.outputs['Incoming']))
    fp = g.math('DIVIDE', g.mul(g.view_distance(), pix), g.math('MAXIMUM', ndv, 0.05))
    tiles = sorted(float(L['tile_m']) for L in pal['layers'])
    dat = _Data(g, data, set(), coords, fp, consts, tile_m=tiles[len(tiles) // 2],
                detail_strength=float(opt.get('detail_strength', DETAIL_STRENGTH)), cubic=False)
    if not dat.has_family('C'):
        raise ValueError('far_group: the surface data has no far colour (bake it with a palette)')
    normal = dat.n_macro()
    albedo = g.vmath('MINIMUM', g.vmath('SCALE', dat.colour('C'), scale=_far_grain(g, L0, S0, coords)),
                     (0.95, 0.95, 0.95))
    rough = g.math('MINIMUM', g.math('MAXIMUM', dat.value('far_roughness'), 0.02), 1.0)
    bsdf = g.node('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Metallic'].default_value = 0.0
    bsdf.inputs['Specular IOR Level'].default_value = float(opt['specular'])
    g.set(bsdf.inputs['Base Color'], albedo)
    g.set(bsdf.inputs['Roughness'], rough)
    g.set(bsdf.inputs['Normal'], normal)
    g.set(gout.inputs['BSDF'], bsdf.outputs['BSDF'])
    g.set(gout.inputs['Base Color'], albedo)
    g.set(gout.inputs['Roughness'], rough)
    g.set(gout.inputs['Normal'], normal)
    nimg, nsamp = _count_samplers(ng)
    ng['eido_palette'] = pal['name']
    ng['eido_images'] = nimg
    ng['eido_samplers'] = nsamp
    ng['eido_surface_key'] = str(data.key)
    ng['eido_far'] = True
    return ng


def terrain_map_group(data, names=None, name='eido_terrain_map'):
    """eido_terrain_map (SURFACING_DESIGN.md 2.7): a terrain's baked maps per pixel through the same two-slot reader,
    for agents' own shaders. One output per map, named by it (decoded to its unit: maps.MAPS): the masks and new maps
    in the M atlases (by default the current packing: the palette's reads), D's normal_x, normal_y, detail_gx,
    detail_gy, E's crease, cavity, crest_fine, grain, F's strata and src_strata, C's far_colour and far_roughness and
    P's down_colour and down_share where baked, and the derived slope, aspect, northness, eastness, insolation,
    height, plus Level (the finest window holding the pixel). Link the output you want; the rest compile to nothing.
    names: pack these maps into the M atlases first (call it before building materials on the same data: a repack
    remakes the M images). A second terrain's group is named eido_terrain_map_<key>."""
    from ..surface import maps as MP
    if names:
        data.pack(list(names))
    other = bpy.data.node_groups.get(name)
    if other is not None and other.get('eido_surface_key') not in (None, str(data.key)):
        name = f'{name}_{str(data.key)[:8]}'
    old = bpy.data.node_groups.get(name)
    if old is not None:
        bpy.data.node_groups.remove(old)
    ng = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    g = Graph(ng)
    coords = g.node('ShaderNodeTexCoord').outputs['Object']
    geo = g.geometry()
    ndv = g.math('ABSOLUTE', g.vmath('DOT_PRODUCT', geo.outputs['Normal'], geo.outputs['Incoming']))
    fp = g.math('DIVIDE', g.mul(g.view_distance(), float(P.CONSTANTS['pixel_angle'])), g.math('MAXIMUM', ndv, 0.05))
    dat = _Data(g, data, set(), coords, fp, dict(P.CONSTANTS))
    outs = []
    packed = sorted({n for grp in data.packing() for n in grp})
    fixed = [n for f in ('D', 'E', 'F') if f in dat.images for n in MP.FAMILIES[f]['channels'] if n is not None]
    for n in packed + fixed:
        if dat.has(n):
            outs.append((n, dat.value(n) if n not in ('normal_x', 'normal_y', 'detail_gx', 'detail_gy')
                         else dat.value_raw(n), 'f'))
    for f, (cn, an) in (('C', ('far_colour', 'far_roughness')), ('P', ('down_colour', 'down_share'))):
        if dat.has_family(f):
            outs.append((cn, dat.colour(f), 'c'))
            outs.append((an, dat.value(an), 'f'))
    for n in ('slope', 'aspect', 'northness', 'eastness', 'insolation', 'height'):
        outs.append((n, dat.value(n), 'f'))
    if dat.has('slope_20m'):
        outs.append(('slope_20m', dat.value('slope_20m'), 'f'))
    outs.append(('Level', dat.rd.outputs['Level'], 'f'))
    for n, _v, kd in outs:
        _sock(ng, n, 'OUTPUT', kd)
    go = g.node('NodeGroupOutput')
    for n, v, _kd in outs:
        g.set(go.inputs[n], v)
    ng['eido_surface_key'] = str(data.key)
    return ng


def surface_group(palette, name=GROUP_NAME, prefer='2k', log=print, data=None):
    """The eido_terrain_surface shader node group of a palette (palettes.get resolves it). Outputs: BSDF, Base Color,
    Roughness, Normal. The group carries the palette name and its layers' sets as custom properties. data: a
    SurfaceData (terrain/surface): the per-texel material of the module doc's second part."""
    pal = P.get(palette) if not (isinstance(palette, dict) and 'options' in palette) else palette
    if data is not None:
        return _surface_group_data(pal, data, name, prefer, log)
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

    # per layer: coverage, then the reads. Without baked data a layer's fallback stands for its weight (a canopy
    # layer's weight reads the plant layer's canopy_expected, which only baked data holds)
    wexpr = [L['fallback'] if L.get('fallback') is not None else L['weight'] for L in layers]
    per = []
    for i, (L, S) in enumerate(zip(layers, sets)):
        cov = _clamp01(g, comp(P.parse(wexpr[i])))
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
        ccov = [_clamp01(g, cheap(P.parse(wexpr[i]))) if bumped[i] or any(bumped[:i]) else 0.0
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


def _group_material(ng, name):
    mat = new_material(name)
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    grp = nt.nodes.new('ShaderNodeGroup')
    grp.node_tree = ng
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (300, 0)
    nt.links.new(grp.outputs['BSDF'], out.inputs['Surface'])
    return mat


def _nodes_in(ng, _memo=None):
    """Nodes of a group with its subgroups expanded, every instance counted: what the shader is compiled from (a
    group placed twelve times is twelve copies of its nodes in the shader's source)."""
    memo = {} if _memo is None else _memo
    if ng.name not in memo:
        n = 0
        for nd in ng.nodes:
            if nd.bl_idname == 'ShaderNodeGroup' and nd.node_tree is not None:
                n += _nodes_in(nd.node_tree, memo)
            else:
                n += 1
        memo[ng.name] = n
    return memo[ng.name]


def surface_material(palette='auto', recipe=None, strata=None, options=None, name='terrain_ground', prefer='2k',
                     log=print, constants=None, data=None):
    """A material whose surface is the eido_terrain_surface group of a palette; palette=None gives clay_material().

    palette   a name (palettes.names()), 'auto' (the recipe's: palettes.RECIPE_PALETTES), or a palette dict
    recipe    the recipe (name, Recipe or dict), for 'auto'
    strata    the rock column for the palette's strata layers: a STRATA_COLUMNS name, the solver's column list, or a
              dict (column, source 'attribute' | 'position', z_offset_m, dip_deg, dip_azimuth_deg, faults, warp,
              facies_m, smear, parting, looks)
    options   material options over the palette's (palettes.DEFAULT_OPTIONS), and with baked data: detile 'hex'
              (the landscape palettes' 'rotate' reads as hex; 'offset' keeps one read per frame), detail_strength
              (the relief below the cell, default 0.5), far_m (D0, metres; default where a main-level texel spans
              2.5 pixels), overlay (False: no overlay before the height blend), dusting dict(colour, amount,
              slope_deg, where), debug 'level' (the level each pixel reads); hex_m (a planar read's hex lattice,
              metres: by default the layer's tile snapped to 2.5 x 2^n, hex_class; 0: one read), hex_rotate
              (False for directional scans), steep_hex_m and steep_rotate (the sector reads of box layers: by
              default one lattice for all of them, twice the class of the largest box tile, not turned; 0: one
              read per sector frame), each a material option or a layer's own key; steep_hex_share (box layers
              with a tile under this share of the largest read each sector frame once, default 0.5; 0: every box
              layer hex-tiled in its sector frames); near_hex (True: every hex read
              of a planar frame 'Auto' filtered; by default one Cubic read at the plain coordinate within
              detail_distance, design 8.1's first lever); a layer's overlay
              dict(height, crest, crest_fine, crease), provenance dict(src, down, pale), patina and fresh_gain
              (multipliers on rock by `fresh`)
    constants the terrain constants over the palette's (palettes.CONSTANTS: base_elevation_m, snowline_m, treeline_m,
              pixel_angle, ...)
    data      a SurfaceData (terrain/surface.bake_surface) of the terrain the material is for: the per-texel
              material (module doc); its far colour C needs the bake to have had a palette
    """
    if palette is None:
        return clay_material(name)
    t0 = time.time()
    pal = resolve(palette, recipe, strata, options, constants)
    ng = surface_group(pal, prefer=prefer, log=log, data=data)
    mat = _group_material(ng, name)
    mat['eido_palette'] = pal['name']
    mat['eido_masks'] = sorted(P.masks_used(pal)) if data is None else []
    mat['eido_constants'] = json.dumps(pal['constants'])
    mat['eido_mask_packs'] = ng['eido_mask_packs']
    mat['eido_build_s'] = round(time.time() - t0, 2)
    if data is not None:
        mat['eido_surface_key'] = str(data.key)
        mat['eido_far_m'] = float(ng['eido_far_m'])
        mat['eido_samplers'] = int(ng['eido_samplers'])
    if log:
        if data is not None:
            log(f"[surfacing] {pal['name']} (baked data {str(data.key)[:10]}): {len(pal['layers'])} layers, "
                f"{ng['eido_images']} images, {ng['eido_samplers']} samplers, {_nodes_in(ng)} nodes "
                f"(groups expanded) in {time.time() - t0:.1f} s; far hand-off at {ng['eido_far_m']:.0f} m")
        else:
            packed = json.loads(ng['eido_mask_packs'])
            log(f"[surfacing] {pal['name']}: {len(pal['layers'])} layers, {ng['eido_images']} images, "
                f"{ng['eido_attributes']} mesh attributes" + (f" ({sum(len(m) for _a, m in packed)} masks packed "
                                                             f"three to one: pack_masks writes them)" if packed else '')
                + f", {len(ng.nodes)} nodes in {time.time() - t0:.1f} s")
    return mat


def far_material(palette='auto', recipe=None, strata=None, options=None, name='terrain_far', prefer='2k', log=print,
                 constants=None, data=None):
    """The far material of a terrain with baked data (material slot 1: its far colour C, the macro normal, a faint
    grain; SURFACING_DESIGN.md 3.7). apply_surface(cameras=...) gives it to the rings beyond 1.5 D0 of every camera."""
    if data is None:
        raise ValueError('far_material needs the terrain\'s surface data (data=)')
    t0 = time.time()
    pal = resolve(palette, recipe, strata, options, constants)
    ng = far_group(pal, data, prefer=prefer, log=log)
    mat = _group_material(ng, name)
    mat['eido_palette'] = pal['name']
    mat['eido_far'] = True
    mat['eido_surface_key'] = str(data.key)
    if log:
        log(f"[surfacing] {pal['name']} far material: {ng['eido_samplers']} samplers, {_nodes_in(ng)} nodes in "
            f"{time.time() - t0:.1f} s")
    return mat


def _camera_points(cameras):
    """(N, 2) world x, y of camera positions: camera objects (their world location), (x, y[, z]) points, or arrays of
    them (points along a camera path)."""
    pts = []
    for c in cameras or []:
        if hasattr(c, 'matrix_world'):
            t = c.matrix_world.translation
            pts.append((float(t[0]), float(t[1])))
            continue
        a = np.asarray(c, np.float64)
        if a.ndim == 2:
            pts.extend((float(r[0]), float(r[1])) for r in a)
        else:
            pts.append((float(a[0]), float(a[1])))
    return np.asarray(pts, np.float64).reshape(-1, 2)


def _ring_table(obj):
    """[dict(ring, level, start, count, window (x0, y0, x1, y1), hole or None)] of a ring mesh object: what
    mesh.make_object stores (eido_terrain_rings), else rebuilt from its layout."""
    raw = obj.get('eido_terrain_rings')
    if raw:
        return json.loads(raw)
    lay = obj.get('eido_terrain_mesh')
    if not lay:
        return []
    from . import mesh as _mesh
    return _mesh.ring_table(json.loads(lay) if isinstance(lay, str) else dict(lay))


def far_rings(obj, data, cameras, far_m=None, palette=None):
    """The rings of a terrain object that lie beyond 1.5 D0 (horizontal metres) from every camera point: those the far
    material may draw (SURFACING_DESIGN.md 3.7). D0: far_m, else the palette's far_distance. No cameras, no rings."""
    pts = _camera_points(cameras)
    if not len(pts):
        return []
    if far_m is None:
        far_m = far_distance(P.get(palette or 'auto') if not isinstance(palette, dict) else palette, data)
    lim = 1.5 * float(far_m)
    out = []
    for r in _ring_table(obj):
        x0, y0, x1, y1 = r['window']
        dx = np.maximum(np.maximum(x0 - pts[:, 0], pts[:, 0] - x1), 0.0)
        dy = np.maximum(np.maximum(y0 - pts[:, 1], pts[:, 1] - y1), 0.0)
        d = np.hypot(dx, dy)
        if r.get('hole'):
            hx0, hy0, hx1, hy1 = r['hole']
            inside = (pts[:, 0] > hx0) & (pts[:, 0] < hx1) & (pts[:, 1] > hy0) & (pts[:, 1] < hy1)
            dh = np.minimum(np.minimum(pts[:, 0] - hx0, hx1 - pts[:, 0]), np.minimum(pts[:, 1] - hy0, hy1 - pts[:, 1]))
            d = np.where(inside, dh, d)
        if float(d.min()) > lim:
            out.append(int(r['ring']))
    return out


def _set_far_rings(obj, rings):
    """material_index 1 on the triangles of these rings (the far material), 0 elsewhere."""
    me = obj.data
    idx = np.zeros(len(me.polygons), np.int32)
    if rings:
        tab = {int(r['ring']): r for r in _ring_table(obj)}
        for k in rings:
            r = tab[int(k)]
            idx[int(r['start']):int(r['start']) + int(r['count'])] = 1
    me.polygons.foreach_set('material_index', idx)
    me.update()
    return int(idx.sum())


def apply_surface(obj, palette='auto', recipe=None, strata=None, options=None, name=None, log=print, constants=None,
                  data=None, cameras=None):
    """surface_material(...) assigned to obj (its material slots replaced), with the terrain's own constants
    (terrain_constants(obj): base elevation, snowline, treeline) under any given here. Without data, warns about
    masks the palette reads that obj's mesh lacks (they read as 0). Returns the (near) material.

    data      the terrain's SurfaceData: the per-texel material
    cameras   with data: camera objects, (x, y[, z]) points or arrays of points along a camera path; rings lying
              beyond 1.5 D0 of all of them take the far material (slot 1). None: every ring the near material, which
              hands off to the same far colour by itself past D0 (the far material is a cost saving only)"""
    consts = terrain_constants(obj)
    consts.update(constants or {})
    mat = surface_material(palette, recipe, strata, options, name=name or (obj.name + '_ground'), log=log,
                           constants=consts, data=data)
    me = obj.data
    me.materials.clear()
    me.materials.append(mat)
    if palette is not None and data is not None:
        far = far_rings(obj, data, cameras, far_m=mat.get('eido_far_m')) if cameras else []
        if far and data.families() and 'C' in data.families():
            me.materials.append(far_material(palette, recipe, strata, options, name=(name or obj.name) + '_far',
                                             log=log, constants=consts, data=data))
            n = _set_far_rings(obj, far)
            if log:
                log(f"[surfacing] {obj.name}: rings {far} ({n:,} triangles) beyond {1.5 * mat['eido_far_m']:.0f} m of "
                    f"every camera take the far material")
        elif len(me.polygons):
            _set_far_rings(obj, [])
    elif palette is not None:
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
           'pack_set', 'pack_masks', 'mask_packs', 'strata_image', 'strata_array', 'resolve', 'terrain_constants',
           'cache_root', 'far_material', 'far_group', 'far_rings', 'far_distance', 'set_far_distance', 'reader_group',
           'hex_grid_group', 'hex_class',
           'terrain_map_group', 'GROUP_NAME', 'PACK_VERSION', 'MAX_IMAGES', 'MAX_SAMPLERS', 'ATTRS_DIRECT',
           'DEBUG_COLOURS']

"""The ringworld band in EEVEE: makeRingworld (eidoverse/ringworld.js, newest in Eanpa Engine engine/ringworld.js with
ring_terrain_geometry.js, ring_cloud_field.js and ring_eclipse.js).

The authored RINGWORLDskyelement.glb is dressed for alien skies, as in WebGPU:
  - TERRAIN: Eanpa's stitched displacement of the band's height field (real relief, rows concentrated toward the
    observer, closed edge skirts), the authored colour map, the land mask's BLACK blobs as reflective lakes held
    level, baked cavity AO, the analytic cylinder normal frame with the band normal map, animated water normals;
  - WALLS: fresh cylindrical-planar UVs in panel units with the tiled solar-panel PBR set, shaded as the authored
    emissive panel look (black albedo, the arc terms in emission);
  - the RING CLOUD SHEET: a cylinder 280 m above the band carrying the satellite-scale cloud field (macro systems,
    a domain warp, five filament octaves, all exact around the ring), coupled to the sky's own cloud uniforms;
  - the FOG BOUNDARY and RAIN WALLS: soft haze cylinders in the weathered horizon colour around the local scene;
  - the band's OWN TWO LIGHTS, the underground sun at full strength and the planetshine: Blender sun lamps,
    light-linked to the band alone (WebGPU's per-material lightsNode), while the scene's sun is linked away from it;
  - the ARC LIGHT + AERIAL PERSPECTIVE (arcShade): per pixel in every ring material, from keyed per-frame values.
EEVEE renders the band, its walls and its cloud sheet as real geometry in a scene of their own, the PLATE
(make_plate): Sky.bake renders it per frame from the bake camera and composites it into the sky's camera layer, the
local clouds over it. So the band sits behind every local object and under the clouds, as WebGPU's depthless band
(renderOrder -99, drawn before the cloud dome and every local opaque) and Eanpa's private sky depth layer have it.
The fog and rain walls stay in the main scene: local haze, depth-tested against the local geometry.

    ring = make_ringworld(scene, assets, opts, cache_dir)    # built by make_sky(world='ringworld')
    ring.bind_weather(wx, sky)
    vals = ring.update(t)        # per frame: arc light, haze, cloud coupling, band lamps
    ring.key(frame, vals)        # keyed data: the .blend plays any frame on its own
    ring.make_plate()            # make_sky does this: the band, walls, sheet and lamps move to 'eido_ring_plate'
"""
import math
import os

import numpy as np

from . import palette as P

R_REF = 5000.0
HALF_WIDTH = 483.0
CLOUD_H = 280.0                    # Eanpa: the sheet clears the displaced relief
PROXY_OFFSET = 25.0                # the eclipse proxy's radius over the band's
DAYLIGHT = (1.0, 0.97, 0.92)       # the colour the band's sun holds at local night
RING_GROUP = 'eido_ring_keys'
PLATE_SCENE = 'eido_ring_plate'    # the scene the band, walls, sheet and band lamps render in (make_plate)
PLATE_COLLECTION = 'eido_ring_plate_elements'
PLATE_CAMERA = 'eido_ring_plate_camera'
PLATE_NEAR = 20.0                  # Eanpa's sky depth layer near plane: the nearest ring element is 800 m out


def _smooth(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def _mix(a, b, k):
    if isinstance(a, (tuple, list)):
        return tuple(a[i] + (b[i] - a[i]) * k for i in range(len(a)))
    return a + (b - a) * k


# ------------------------------------------------------------------------------------------------- eclipse ---

def ring_solar_visibility(point, sun, radius=R_REF, center=(0.0, 4940.0, 0.0), half_width=HALF_WIDTH,
                          angular_radius=0.00465):
    """Eanpa ring_eclipse.js: solar-disc visibility (0 blocked .. 1 clear) from inside a finite opaque cylinder about
    X, three.js space. Its exit is the opposite arc when the sun is above the receiver's horizon."""
    twilight = 0.05
    if sun[1] <= 0:
        return 1.0
    y, z = point[1] - center[1], point[2] - center[2]
    a = sun[1] * sun[1] + sun[2] * sun[2]
    if a < 1e-10:
        return 1.0
    b = y * sun[1] + z * sun[2]
    c = y * y + z * z - radius * radius
    disc = b * b - a * c
    inside = c <= 2 * radius * max(0.001, radius * 1e-6)
    if disc < 0 and not inside:
        return 1.0
    exit_d = (-b + math.sqrt(max(0.0, disc))) / a
    if exit_d < 0 and not inside:
        return 1.0
    d = max(0.0, exit_d)
    across = abs(point[0] - center[0] + sun[0] * d)
    pen = max(1.0, d * math.tan(angular_radius) / math.sqrt(a))
    k = max(0.0, min(1.0, (across - half_width + pen) / (2 * pen)))
    day = min(1.0, sun[1] / twilight)
    daylight = day * day * (3 - 2 * day)
    return 1 - (1 - k * k * (3 - 2 * k)) * daylight


def eclipse_k(direction, origin_y=0.0, group_y=4940.0, group_x=0.0, radius=R_REF, half_width=HALF_WIDTH):
    """eidoverse ringworld.js eclipseK: 0 = light fully eclipsed by the band, 1 = clear (70 m penumbra), three.js."""
    oy = origin_y - group_y
    a = direction[1] ** 2 + direction[2] ** 2
    if a < 1e-9:
        return 1.0
    b = 2 * oy * direction[1]
    c = oy * oy - radius * radius
    disc = b * b - 4 * a * c
    if disc <= 0:
        return 1.0
    t = (-b + math.sqrt(disc)) / (2 * a)
    if t <= 0:
        return 1.0
    hx = direction[0] * t - group_x
    pen = 70.0
    return min(1.0, max(0.0, (abs(hx) - (half_width - pen)) / (2 * pen)))


# ------------------------------------------------------------------------------------------- geometry data ---

def _sample(img, u, v):
    """Bilinear sample of an image (rows top-down as displayed) at texture coords u (wraps) and v (row from top)."""
    H, W = img.shape[:2]
    x = np.mod(u, 1.0) * W - 0.5
    y = np.clip(v, 0.0, 1.0) * H - 0.5
    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    fx, fy = x - x0, y - y0
    x1 = (x0 + 1) % W
    x0 = x0 % W
    y1 = np.clip(y0 + 1, 0, H - 1)
    y0 = np.clip(y0, 0, H - 1)
    return ((img[y0, x0] * (1 - fx) + img[y0, x1] * fx) * (1 - fy)
            + (img[y1, x0] * (1 - fx) + img[y1, x1] * fx) * fy)


def soft_landmask(mask, shore_texels=3.0):
    """The shader's 3x3 shoreline blur of the land mask (weights 0.36 / 0.11 / 0.05 at shore_texels), at texel
    centres: 1 = land, 0 = water (mask BLACK)."""
    s = int(round(shore_texels))
    r = lambda dy, dx: np.roll(np.roll(mask, dy, 0), dx, 1)
    return (mask * 0.36 + (r(0, s) + r(0, -s) + r(s, 0) + r(-s, 0)) * 0.11
            + (r(s, s) + r(s, -s) + r(-s, s) + r(-s, -s)) * 0.05)


def _box_blur(img, r):
    """A box blur of radius r texels, wrapping around the ring (axis 1) and clamped across the band (axis 0)."""
    if r < 1:
        return img
    k = 2 * r + 1
    pad = np.concatenate([img[:, -r:], img, img[:, :r]], axis=1)
    c = np.concatenate([np.zeros((img.shape[0], 1)), np.cumsum(pad, axis=1)], axis=1)
    h = (c[:, k:] - c[:, :-k]) / k
    pad = np.concatenate([np.repeat(h[:1], r, 0), h, np.repeat(h[-1:], r, 0)], axis=0)
    c = np.concatenate([np.zeros((1, h.shape[1])), np.cumsum(pad, axis=0)], axis=0)
    return (c[k:] - c[:-k]) / k


PREFILTER_RADII = (0, 1, 2, 4, 6)       # texels: the relief's filter levels, picked per row by its vertex spacing


def ring_terrain_arrays(height, land, radius=R_REF, half_width=HALF_WIDTH, height_meters=85.0, around=4096,
                        across=512, repeat=8, local_relief_blend=(700.0, 2000.0), phase=0.0, prefilter=True):
    """Eanpa makeRingTerrainGeometry, as arrays. height, land: images (rows top-down) 0..1, land 1 on land.

    Rows concentrate toward the observer (s = sign(t)|t|^1.8) and coarsen across the band with distance, stitched
    so transitions share every edge. Land is displaced inward by height * height_meters, eased in over
    local_relief_blend (arc metres) so the relief clears the local stage; water (land 0) stays level at the band
    radius. Two skirt strips close the band's edges under the relief.

    prefilter (the Blender edition's own): each row samples the relief filtered to its own vertex spacing, from
    full detail at the observer to a 6-texel blur on the far arc, blended continuously with distance. The repo's
    height field steps up at every shoreline within a few metres, and the far rows sample it every 7 to 15 m: unfiltered,
    the step lands on the vertex grid as saw teeth along every coast. The band normal map carries the fine relief in
    the shading either way. Returns (verts (n, 3) three.js local about the ring axis, uv (n, 2) per vertex,
    tris (m, 3), info)."""
    around = max(16, int(round(around)))
    across = max(8, int(round(across / 8)) * 8)
    rows = []
    count = 0
    H_img, W_img = height.shape[:2]
    tex_along = 2 * math.pi * radius / repeat / W_img          # metres per height texel around the ring
    tex_across = 2 * half_width / H_img
    for i in range(around + 1):
        t = i / around * 2 - 1
        s = math.copysign(abs(t) ** 1.8, t)
        dist = abs(s) * math.pi * radius
        seg = max(8, across // (1 if dist < 300 else 2 if dist < 1000 else 4 if dist < 3500 else 8))
        # this row's vertex spacing, along (the row pitch, smooth in t) and across (the LOD's segments)
        pitch = math.pi * radius * 1.8 * max(abs(t), 1e-6) ** 0.8 * (2.0 / around)
        spacing = max(pitch / tex_along, (2 * half_width / max(seg, 1)) / tex_across)
        rows.append(dict(u=s * 0.5 + phase / (2 * math.pi), angle=math.pi - s * math.pi, seg=seg, off=count,
                         r=min(max(spacing * 0.5 - 0.5, 0.0), float(PREFILTER_RADII[-1]))))
        count += seg + 1
    relief = height * land
    levels = [_box_blur(_box_blur(relief, r), r) for r in PREFILTER_RADII] if prefilter else [relief]
    skirt_off = count
    total = count + (around + 1) * 4
    verts = np.zeros((total, 3), np.float64)
    uv = np.zeros((total, 2), np.float64)
    elev = np.zeros(total, np.float64)
    lb0, lb1 = local_relief_blend
    for i, row in enumerate(rows):
        u, a, seg, off = row['u'], row['angle'], row['seg'], row['off']
        cy, cz = math.cos(a), math.sin(a)
        arc = abs(math.atan2(cz, -cy)) * radius
        w = max(0.0, min(1.0, (arc - lb0) / (lb1 - lb0))) if lb1 > lb0 else 1.0
        w = w * w * (3 - 2 * w)
        v = np.arange(seg + 1) / seg
        uu = np.full_like(v, u * repeat)
        if prefilter:
            # blend the two filter levels around this row's radius (continuous with distance: no LOD seams)
            r = row['r']
            j = max(k for k, rr in enumerate(PREFILTER_RADII) if rr <= r)
            j1 = min(j + 1, len(PREFILTER_RADII) - 1)
            f = 0.0 if j1 == j else (r - PREFILTER_RADII[j]) / (PREFILTER_RADII[j1] - PREFILTER_RADII[j])
            rel = _sample(levels[j], uu, v) * (1 - f) + _sample(levels[j1], uu, v) * f
        else:
            rel = _sample(levels[0], uu, v)
        h = rel * height_meters * w
        sl = slice(off, off + seg + 1)
        verts[sl, 0] = (v - 0.5) * half_width * 2
        verts[sl, 1] = (radius - h) * cy
        verts[sl, 2] = (radius - h) * cz
        uv[sl, 0] = u
        uv[sl, 1] = v
        elev[sl] = h
        for side in (0, 1):
            top = off + (seg if side else 0)
            e = skirt_off + i * 4 + side * 2
            verts[e] = verts[top]
            verts[e + 1] = ((side - 0.5) * half_width * 2, (radius + 2.0) * cy, (radius + 2.0) * cz)
            uv[e] = (u, side)
            uv[e + 1] = (u, side)
            elev[e], elev[e + 1] = elev[top], -2.0
    tris = []
    for i in range(around):
        A, B = rows[i], rows[i + 1]
        if A['seg'] == B['seg']:
            j = np.arange(A['seg'])
            a0, b0 = A['off'] + j, B['off'] + j
            tris.append(np.stack([a0, b0, a0 + 1], 1))
            tris.append(np.stack([a0 + 1, b0, b0 + 1], 1))
        else:                                   # a level-of-detail change: walk both rows, sharing every edge
            out = []
            j = k = 0
            while j < A['seg'] or k < B['seg']:
                na, nb = (j + 1) / A['seg'], (k + 1) / B['seg']
                if na <= nb and j < A['seg']:
                    out.append((A['off'] + j, B['off'] + k, A['off'] + j + 1))
                    j += 1
                else:
                    out.append((A['off'] + j, B['off'] + k, B['off'] + k + 1))
                    k += 1
            tris.append(np.array(out, np.int64))
        for side in (0, 1):
            a = skirt_off + i * 4 + side * 2
            b = a + 4
            if side:
                tris.append(np.array([(a, a + 1, b), (b, a + 1, b + 1)], np.int64))
            else:
                tris.append(np.array([(a, b, a + 1), (b, b + 1, a + 1)], np.int64))
    tris = np.concatenate(tris, 0)
    info = dict(around=around, across=across, vertices=total, triangles=len(tris), height_meters=height_meters,
                min_height=float(elev.min()), max_height=float(elev.max()), phase=phase,
                local_relief_blend=tuple(local_relief_blend), prefilter=bool(prefilter))
    return verts, uv, tris, info


def ring_cloud_field(width=8192, height=256):
    """Eanpa ring_cloud_field.js's field, baked once: macro systems (6 cells around), a vec2 domain warp (10 cells)
    and filament octaves 40..640, all integer cell counts around (an exact wrap), cells isotropic on the band
    (v cells = u cells / 33.4). The wind's drift offsets the whole field together, so it is applied in the material.
    Returns (height, width) float32, rows top-down (v = 0 is the first row)."""
    u = (np.arange(width) + 0.5) / width
    v = (np.arange(height) + 0.5) / height
    U, V = np.meshgrid(u, v)

    def h21(px, py):
        ax = np.mod(px * 0.1031, 1.0)
        ay = np.mod(py * 0.1031, 1.0)
        az = ax.copy()
        d = ax * (ay + 33.33) + ay * (az + 33.33) + az * (ax + 33.33)
        bx, by, bz = ax + d, ay + d, az + d
        return np.mod((bx + by) * bz, 1.0)

    def noise(px, py, rep):
        ix, iy = np.floor(px), np.floor(py)
        fx, fy = px - ix, py - iy
        sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        at = lambda dx, dy: h21(np.mod(ix + dx, rep), iy + dy)
        a, b, c, d = at(0, 0), at(1, 0), at(0, 1), at(1, 1)
        return (a + (b - a) * sx) * (1 - sy) + (c + (d - c) * sx) * sy

    def octave(n, weight, warp=None):
        px, py = U * n, V * (n / 33.4)
        if warp is not None:
            px = px + warp[0] * (n * 0.012)
            py = py + warp[1] * (n * 0.012)
        return noise(px, py, n) * weight

    macro = octave(6, 1.0)
    warp = (octave(10, 1.0) - 0.5, octave(10, 1.0) - 0.5)
    fil = (octave(40, 0.38, warp) + octave(80, 0.26, warp) + octave(160, 0.19, warp) + octave(320, 0.12, warp)
           + octave(640, 0.07, warp))
    return (macro * 0.62 + fil * 0.55).astype(np.float32)


# ----------------------------------------------------------------------------------- Eanpa's v4 band relief ---

RELIEF_MAGIC = 0x464C5245              # 'ERLF', little endian
RELIEF_FILES = dict(relief='ring_relief_v4.bin.gz', albedo='ring_albedo_v4.png', water='ring_relief_v3.bin.gz')


def decode_ring_relief(buffer):
    """Eanpa src/ring_relief.js decodeRingRelief: the ERLF v1 container, a 16-byte header (magic, version, width,
    height) then r16float heights and rgba8 normal + AO, rows bottom-to-top as stored. Raises on a truncated or foreign
    buffer, as the JS does. Returns dict(width, height, height_data (h, w) float32, normal_ao_data (h, w, 4) uint8)."""
    import struct
    b = bytes(buffer)
    if len(b) < 16:
        raise ValueError('Truncated ring relief header')
    magic, version, w, h = struct.unpack('<4I', b[:16])
    if magic != RELIEF_MAGIC or version != 1:
        raise ValueError('Unsupported ring relief format')
    if not w or not h or w > 8192 or h > 8192 or len(b) != 16 + w * h * 6:
        raise ValueError('Invalid ring relief dimensions or payload length')
    heights = np.frombuffer(b, np.float16, w * h, 16).astype(np.float32).reshape(h, w)
    normal_ao = np.frombuffer(b, np.uint8, w * h * 4, 16 + w * h * 2).reshape(h, w, 4)
    return dict(width=w, height=h, height_data=heights, normal_ao_data=normal_ao)


def _read_relief(path):
    import gzip
    raw = open(path, 'rb').read()
    return decode_ring_relief(gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw)


def _write_png_rgba8(path, data_bottom_up):
    """uint8 (h, w, 4), rows bottom-up (Blender's pixel order), to a PNG exactly as given (OpenImageIO, bundled with
    Blender): no alpha association, so a packed AO in alpha stays data."""
    import OpenImageIO as oiio
    data = np.ascontiguousarray(data_bottom_up[::-1])                  # PNG rows run top-down
    h, w, c = data.shape
    out = oiio.ImageOutput.create(path)
    if out is None:
        raise RuntimeError('cannot write ' + path)
    out.open(path, oiio.ImageSpec(w, h, c, 'uint8'))
    out.write_image(data)
    out.close()


def load_ring_relief(folder, cache_dir):
    """Eanpa src/ring_relief.js loadRingRelief: Eanpa's newest band, the eroded v4 relief (ring_relief_v4.bin.gz: 4344 x
    1448 heights with its own normals and AO, 8 repeats around as the colour map), its matching albedo
    (ring_albedo_v4.png) and the v3 relief's normals, kept for the water waves (ring_relief_v3.bin.gz). Gzip or raw.

    The normal + AO maps are written once into cache_dir as PNGs: the stored bottom-to-top rows are Blender's pixel
    order, and their convention (x = -dH/du, y = +dH/drow, AO in alpha) is the repo's band maps', so the band
    material reads them unchanged. Returns the JS keys: bandHeight (heights, rows top-down as displayed), bandNormal and
    bandAO (the same RGBA PNG), bandColor (the albedo PNG), waterWaveNormal (a PNG, or None without the v3 file)."""
    rel = _read_relief(os.path.join(folder, RELIEF_FILES['relief']))
    albedo = os.path.join(folder, RELIEF_FILES['albedo'])
    if not os.path.exists(albedo):
        raise FileNotFoundError('load_ring_relief: %s has the v4 relief but not its albedo %s'
                                % (folder, RELIEF_FILES['albedo']))
    os.makedirs(cache_dir, exist_ok=True)
    nrm = os.path.join(cache_dir, 'ring_relief_v4_normal_ao.png')
    if not os.path.exists(nrm):
        _write_png_rgba8(nrm, rel['normal_ao_data'])
    water = None
    wpath = os.path.join(folder, RELIEF_FILES['water'])
    if os.path.exists(wpath):
        water = os.path.join(cache_dir, 'ring_relief_v3_water_normal.png')
        if not os.path.exists(water):
            _write_png_rgba8(water, _read_relief(wpath)['normal_ao_data'])
    return dict(bandHeight=np.ascontiguousarray(rel['height_data'][::-1]), bandNormal=nrm, bandAO=nrm,
                bandColor=albedo, waterWaveNormal=water, width=rel['width'], height=rel['height'], folder=folder)


def _upsample_to(img, shape):
    """Bilinear resample of a (rows top-down) field to another shape, wrapping around the ring (axis 1)."""
    if img.shape[:2] == tuple(shape[:2]):
        return img
    H, W = shape[:2]
    u = (np.arange(W) + 0.5) / W
    v = (np.arange(H) + 0.5) / H
    U, V = np.meshgrid(u, v)
    return _sample(img, U, V)


# ---------------------------------------------------------------------------------------------- the system ---

class Ringworld:
    """The ringworld band in a Blender scene. Built by make_ringworld; see the module docstring."""

    def __init__(self, scene, assets, opts=None, cache_dir=None, collection=None):
        self.scene = scene
        self.A = assets
        self.opts = dict(opts or {})
        self.cache_dir = cache_dir
        self.collection = collection
        o = self.opts
        self.center_y = float(o.get('centerY', 4940.0))
        self.planet_shine = tuple(o.get('planetShineColor') or (1.00, 0.92, 0.82))
        mx = max(max(self.planet_shine), 1e-4)
        self.ps_haze = tuple(c / mx for c in self.planet_shine)
        self.haze_night_level = float(o.get('hazeNightLevel', 0.055))
        self.tile = float(o.get('panelTile', 60))
        self.band_sun_intensity = float(o.get('bandSunIntensity', 3.2))
        self.band_shine_intensity = float(o.get('bandShineIntensity', 0.55))
        self.cloud_h = float(o.get('cloudHeight', CLOUD_H))
        self.foot_width_night = float(o.get('footWidthNight', 0.075))
        self.insc_night_level = float(o.get('inscatterNightLevel', 0.28))
        self.lit_band = _opt_on(o, 'litBand', True)
        self.wx = None
        self.sky = None
        self.objects = {}
        self.info = dict(radius=R_REF, tile=self.tile, halfWidth=HALF_WIDTH, repeat=8)
        self.plate_scene = self.plate_camera = self.plate_collection = None     # make_plate
        self._build()

    # ---- build ----
    def _build(self):
        import bpy
        from mathutils import Vector
        from . import ring_materials as RM
        sc = self.scene
        coll = self.collection or bpy.data.collections.new('eido_ringworld')
        if coll.name not in sc.collection.children:
            sc.collection.children.link(coll)
        self.collection = coll
        # import the authored GLB into the ring collection
        before = set(bpy.data.objects)
        lc = _find_layer_collection(bpy.context.view_layer.layer_collection, coll)
        prev = bpy.context.view_layer.active_layer_collection
        if lc:
            bpy.context.view_layer.active_layer_collection = lc
        bpy.ops.import_scene.gltf(filepath=self.A['glb'])
        if lc:
            bpy.context.view_layer.active_layer_collection = prev
        new = [ob for ob in bpy.data.objects if ob not in before]
        walls = terrain = None
        for ob in new:
            if ob.type == 'MESH' and 'wall' in ob.name.lower():
                walls = ob
            elif ob.type == 'MESH' and any(k in ob.name.lower() for k in ('terrain', 'band', 'ground')):
                terrain = ob
        if walls is None or terrain is None:
            raise RuntimeError('[ringworld] expected "walls" + "terrain" meshes in %s' % self.A['glb'])
        # keep ONLY the two known meshes: stray helper objects ship in the GLB
        src_mat = terrain.data.materials[0] if terrain.data.materials else None
        for ob in new:
            if ob not in (walls, terrain):
                bpy.data.objects.remove(ob, do_unlink=True)
        # the export frames the ring lifted into the sky: recentre on the WALLS' bounds (Eanpa: displaced mountains
        # must not move the axis), then place the group at its authored height
        bb = [walls.matrix_world @ Vector(c) for c in walls.bound_box]
        ctr = sum(bb, Vector()) / 8.0
        group = bpy.data.objects.new('eido_ringworld', None)
        coll.objects.link(group)
        group.location = (0.0, 0.0, self.center_y)
        for ob in (terrain, walls):
            loc = ob.matrix_world.translation - ctr
            ob.parent = group
            ob.matrix_parent_inverse.identity()
            ob.location = loc
        bpy.context.view_layer.update()          # world matrices now hold the placement (ring_center_three reads it)
        self.group = group
        # the authored colour map and its tiling (KHR transform 8 x 1 around the ring), and the UV phase that keeps
        # the continents where the export put them relative to the walls (Eanpa)
        self.map_image, self.info['repeat'] = _authored_map(src_mat)
        phase = _uv_phase(terrain)
        self.info['phase'] = phase
        cache = self.cache_dir
        os.makedirs(cache, exist_ok=True)
        # Eanpa's newest band (src/ring_relief.js loadRingRelief): the eroded v4 relief with its own normals and AO, its
        # matching albedo and the v3 water normals, from reliefDir when the set is there (make_sky looks in the repo's
        # celestial folder). Without it the band keeps the repo's v1 height, normal and AO maps and the GLB's colour
        # map, as sky_worlds.js has it.
        self.relief = None
        rd = self.opts.get('reliefDir', self.A.get('reliefDir'))
        if rd and os.path.exists(os.path.join(rd, RELIEF_FILES['relief'])):
            self.relief = load_ring_relief(rd, cache)
            self.A = dict(self.A, bandNormal=self.relief['bandNormal'], bandAO=self.relief['bandAO'],
                          bandColor=self.relief['bandColor'])
            if self.relief['waterWaveNormal']:
                self.A['waterWaveNormal'] = self.relief['waterWaveNormal']
            # Eanpa's ringsky host reads the v4 maps at their own strength, the AO packed in the normal map's alpha
            self.opts.setdefault('bandNormalScale', 1.0)
            self.opts.setdefault('bandAOPackedNormal', True)
        self.info['relief'] = 'v4' if self.relief is not None else 'v1'
        self.map_path = os.path.join(cache, 'ring_band_albedo.png')
        if self.map_image is not None and not os.path.exists(self.map_path):
            self.map_image.save(filepath=self.map_path)
        # the land mask's shoreline blur, precomputed once (the shader's 9 taps)
        from .bake.baker import load_image_rgba
        mask = load_image_rgba(self.A['landmask'], srgb=False)[::-1, :, 0].astype(np.float64)
        shore = float(self.opts.get('shoreTexels', 3.0))
        soft = soft_landmask(mask, shore)
        # cached per shoreline width: a cache made with another shoreTexels must not answer for this one
        self.mask_soft_path = os.path.join(cache, 'ring_landmask_soft_%g.exr' % shore)
        if not os.path.exists(self.mask_soft_path):
            from .bake.baker import write_exr
            arr = np.repeat(soft[::-1, :, None].astype(np.float32), 4, axis=2)
            arr[..., 3] = 1.0
            write_exr(self.mask_soft_path, arr, half=False)
        lrb = tuple(self.opts.get('localReliefBlend', (700.0, 2000.0)))
        self.info['localReliefBlend'] = lrb
        # GEOMETRY RELIEF (Eanpa's default): the band's height field displaced into real stitched geometry. With
        # geometryRelief=False the GLB's own flat terrain mesh stays, shaded by its normal map alone.
        self.authored_band = not (_opt_on(self.opts, 'geometryRelief', True)
                                  and (self.A.get('bandHeight') or self.relief is not None))
        if not self.authored_band:
            land = np.clip((soft - 0.30) / 0.40, 0.0, 1.0)
            land = land * land * (3 - 2 * land)
            if self.relief is not None:
                # the v4 heights as stored (x heightMeters, as Eanpa's geometry reads them), at twice the mask's
                # resolution: the land mask follows them there and still holds the lakes level
                height = self.relief['bandHeight'].astype(np.float64)
                land = _upsample_to(land, height.shape)
            else:
                height = load_image_rgba(self.A['bandHeight'], srgb=False)[::-1, :, 0].astype(np.float64)
                height = (height - height.min()) / max(1e-9, height.max() - height.min())
            hm = float(self.opts.get('terrainHeightMeters', self.opts.get('heightMeters', 85.0)))
            verts, uv, tris, ginfo = ring_terrain_arrays(
                height, land, height_meters=hm,
                around=int(self.opts.get('around', 4096)), across=int(self.opts.get('across', 512)),
                repeat=self.info['repeat'], local_relief_blend=lrb, phase=phase,
                prefilter=_opt_on(self.opts, 'reliefPrefilter', True))
            self.info['geometryRelief'] = ginfo
            old = terrain.data
            terrain.data = _mesh_from_arrays('eido_ring_band', _three_to_blender_arr(verts), tris, uv)
            bpy.data.meshes.remove(old)
        else:
            self.info['geometryRelief'] = None
        terrain.name = 'eido_ring_band'
        walls.name = 'eido_ring_walls'
        _wall_uvs(walls, self.tile)
        self.band, self.walls = terrain, walls
        # the ring cloud field, baked once per atlas size (Eanpa's cloudAtlas {width, height}, or a pair)
        ca = self.opts.get('cloudAtlas') or (8192, 256)
        fw, fh = (ca.get('width', 2048), ca.get('height', 64)) if isinstance(ca, dict) else ca
        self.info['cloudAtlas'] = (int(fw), int(fh))
        self.cloud_field_path = os.path.join(cache, 'ring_cloud_field_%dx%d.exr' % (int(fw), int(fh)))
        if not os.path.exists(self.cloud_field_path):
            from .bake.baker import write_exr
            f = ring_cloud_field(int(fw), int(fh))
            arr = np.repeat(f[::-1, :, None], 4, axis=2)
            arr[..., 3] = 1.0
            write_exr(self.cloud_field_path, arr, half=False)
        clouds = fog = rain = None
        if _opt_on(self.opts, 'ringClouds', True):
            clouds = _cylinder_x('eido_ring_clouds', R_REF - self.cloud_h, 940.0, 512, coll)
            clouds.parent = group
        if _opt_on(self.opts, 'fogWall', True):
            fw_r = float(self.opts.get('fogWallRadius', 1250.0))
            fog = _cylinder_z('eido_ring_fog_wall', fw_r, 90.0, 96, coll)
            fog.parent = group
            fog.location = (0.0, 0.0, -4915.0)
            if _opt_on(self.opts, 'rainWall', True):
                rain = _cylinder_z('eido_ring_rain_wall', fw_r + 130.0, 730.0, 96, coll)
                rain.parent = group
                rain.location = (0.0, 0.0, -4620.0)
        self.clouds, self.fog_wall, self.rain_wall = clouds, fog, rain
        # THE ECLIPSE PROXY: Eanpa ring_eclipse.js's finite opaque cylinder about the band's axis (radius 5000, half
        # width 483), as a shadow-only object. It casts the arch's eclipse for the band's own sun and for the scene's
        # sun, per receiver (Eanpa's solarVisibilityNode on every local PBR receiver: sky.setSolarOcclusion), with
        # EEVEE's penumbra from the sun's 0.53 deg disc, the analytic penumbra's width
        # 25 m outside the band (its skirts reach 2 m out): a lit band point's own depth stays clear of the
        # proxy wall behind it at the band sun's 2.8 m texels; the eclipse edge moves by under 0.2 deg
        proxy = _cylinder_x('eido_ring_eclipse_proxy', R_REF + PROXY_OFFSET, HALF_WIDTH * 2.0, 1024, coll)
        proxy.parent = group
        proxy.location = terrain.location.copy()
        for attr in ('visible_camera', 'visible_diffuse', 'visible_glossy', 'visible_transmission',
                     'visible_volume_scatter'):
            setattr(proxy, attr, False)
        proxy.visible_shadow = True
        for attr in ('hide_probe_volume', 'hide_probe_sphere', 'hide_probe_plane'):
            if hasattr(proxy, attr):
                setattr(proxy, attr, True)
        from .ring_materials import eclipse_proxy_material
        proxy.data.materials.append(eclipse_proxy_material())
        self.eclipse_proxy = proxy
        # the band's own two lights, linked to the band alone
        self.band_sun = self.band_shine = None
        self.cast_relief = _opt_on(self.opts, 'bandCastShadow', False)
        if self.lit_band and _opt_on(self.opts, 'bandLights', True):
            recv = bpy.data.collections.new('eido_ring_band_receivers')
            recv.objects.link(terrain)
            for co in recv.collection_objects:
                co.light_linking.link_state = 'INCLUDE'
            # the band sun is shadowed by the ring alone: the eclipse proxy and the cloud sheet always (Eanpa's
            # custom light model: eclipse x sheet transmission), the band's relief and walls only with
            # bandCastShadow (Eanpa's default is off). Nothing of the local scene, nor its cloud-shadow caster.
            blockers = bpy.data.collections.new('eido_ring_band_sun_blockers')
            for ob in (proxy, clouds) + ((terrain, walls) if self.cast_relief else ()):
                if ob is not None:
                    blockers.objects.link(ob)
            for co in blockers.collection_objects:
                co.light_linking.link_state = 'INCLUDE'
            self.band_sun = _sun_lamp('eido_ring_band_sun', self.band_sun_intensity, coll, shadow=True)
            # kilometre-scale shadows: Eanpa's map spans 2 x 1.15 R over bandShadowMapSize texels (2.8 m at 4096)
            size = float(self.opts.get('bandShadowMapSize', 4096))
            self.band_sun.data.shadow_maximum_resolution = float(
                self.opts.get('bandShadowTexel', 2.0 * 1.15 * R_REF / max(size, 1.0)))
            if int(sc.eevee.shadow_pool_size) < 1024:
                sc.eevee.shadow_pool_size = '1024'
            self.band_sun.light_linking.blocker_collection = blockers
            # planetshine: shadowed by the cloud sheet alone (the sheet transmission of Eanpa's light model)
            self.band_shine = _sun_lamp('eido_ring_band_shine', self.band_shine_intensity, coll,
                                        shadow=clouds is not None)
            self.band_shine.data.color = self.planet_shine
            if clouds is not None:
                sb = bpy.data.collections.new('eido_ring_band_shine_blockers')
                sb.objects.link(clouds)
                for co in sb.collection_objects:
                    co.light_linking.link_state = 'INCLUDE'
                self.band_shine.light_linking.blocker_collection = sb
                self.band_shine.data.shadow_maximum_resolution = self.band_sun.data.shadow_maximum_resolution
            for lamp in (self.band_sun, self.band_shine):
                lamp.light_linking.receiver_collection = recv
            self.receivers = recv
        # materials (and the per-frame keys they read)
        self.keys_tree, self.key_handles = RM.ring_keys_group(self)
        RM.band_material(self, terrain, authored=self.authored_band)
        RM.walls_material(self, walls)
        if clouds:
            RM.cloud_sheet_material(self, clouds)
        if fog:
            RM.haze_wall_material(self, fog, rain=False)
        if rain:
            RM.haze_wall_material(self, rain, rain=True)
        for ob in (terrain, walls, clouds, fog, rain, proxy):
            if ob is not None:
                ob['eido_sky_element'] = 'ringworld'
        bpy.context.view_layer.update()          # world matrices of everything built after the recentring
        self.objects = dict(group=group, band=terrain, walls=walls, clouds=clouds, fog_wall=fog, rain_wall=rain,
                            band_sun=self.band_sun, band_shine=self.band_shine, eclipse_proxy=proxy)
        self.info.update(map_path=self.map_path, mask_path=self.A['landmask'], cloud_field=self.cloud_field_path,
                         waterWaveMode=_wave_mode(self.opts), litBand=self.lit_band, bandCastShadow=self.cast_relief,
                         waterWavesActive=_wave_mode(self.opts) == 'full' or (
                             _wave_mode(self.opts) == 'lightweight' and bool(self.A.get('bandNormal'))),
                         mapTex=self.map_image, maskTex=self.A['landmask'], authoredBand=self.authored_band)

    # ---- the haze walls under the cloud dome (WebGPU's draw order) ----
    def order_walls_under_dome(self, camera, on=True, origin_ahead=2.0e6):
        """With the cloud dome on, draw the fog and rain walls BEFORE it, as WebGPU does: the walls hang from the band
        group (renderOrder -99) and the cloud dome draws after them (-98). The dome then lays the clouds over the
        walls wherever it shows (the sky, and geometry past its radius), and the walls still veil the geometry
        between them and the dome. EEVEE draws Blended objects farthest ORIGIN first (probe_eevee_facts.py F4), and
        the dome's origin rides 1000 km down the view axis, so each wall is drawn by a copy whose origin rides
        `origin_ahead` (2000 km) down it: its Geometry Nodes take the wall's surface through an Object Info in
        RELATIVE space, so it stays exactly where the wall is. The walls themselves stay as the source, out of the
        render. on=False removes the copies and gives the walls back to the render. Returns the copies."""
        import bpy
        copies = []
        for wall in (self.fog_wall, self.rain_wall):
            if wall is None:
                continue
            name = wall.name + '_under_dome'
            old = bpy.data.objects.get(name)
            if old is not None:
                me = old.data
                bpy.data.objects.remove(old, do_unlink=True)
                if me is not None and me.users == 0:
                    bpy.data.meshes.remove(me)
            wall.hide_render = bool(on)
            if not on:
                continue
            ob = bpy.data.objects.new(name, bpy.data.meshes.new(name))
            for c in wall.users_collection:
                c.objects.link(ob)
            ob.parent = camera
            ob.matrix_parent_inverse.identity()
            ob.location = (0.0, 0.0, -float(origin_ahead))
            for attr in ('visible_shadow', 'visible_diffuse', 'visible_glossy', 'visible_transmission',
                         'visible_volume_scatter'):
                if hasattr(ob, attr):
                    setattr(ob, attr, getattr(wall, attr))
            mod = ob.modifiers.new('eido_world_anchored', 'NODES')
            mod.node_group = _world_anchored_tree()
            ident = mod.node_group.interface.items_tree['Source'].identifier
            getattr(mod.properties.inputs, ident).value = wall      # Blender 5.2: a nodes modifier's inputs live here
            ob['eido_sky_element'] = 'ringworld'
            copies.append(ob)
        self.wall_copies = copies
        return copies

    # ---- the scene's own sun: linked away from the band, as the band's lights are linked to it alone ----
    def unlink_scene_sun(self, sun_obj):
        """The scene's sun lights everything but the band, and the ring's visible sky elements cast no shadow from
        it: WebGPU's band material names its own lights; here the scene sun's receiver and blocker collections
        exclude the band, walls and cloud sheet (the walls keep the scene sun's specular, as WebGPU's did). The
        eclipse proxy stays a blocker: it is the arch's eclipse on every local receiver (Eanpa's
        setSolarOcclusion), so the sun lamp itself is not dimmed by the camera's visibility (sky.solar_occlusion)."""
        import bpy
        ll = sun_obj.light_linking
        recv = ll.receiver_collection or bpy.data.collections.new('eido_scene_sun_receivers')
        ll.receiver_collection = recv
        if self.band.name not in recv.objects:
            recv.objects.link(self.band)
        block = ll.blocker_collection or bpy.data.collections.new('eido_scene_sun_blockers')
        ll.blocker_collection = block
        for ob in (self.band, self.walls, self.clouds):
            if ob is not None and ob.name not in block.objects:
                block.objects.link(ob)
        ours = {o.name for o in (self.band, self.walls, self.clouds) if o is not None}
        for coll in (recv, block):
            # collection_objects runs in the order of collection.objects (one settings entry per object)
            for ob, co in zip(coll.objects, coll.collection_objects):
                if ob.name in ours:
                    co.light_linking.link_state = 'EXCLUDE'
        return self

    # ---- per frame ----
    def bind_weather(self, wx, sky):
        self.wx, self.sky = wx, sky
        return self

    def attach_lights(self, root=None):
        """WebGPU parents the band lights to the scene root on the first update; here they are linked into the
        ring's collection at build time, so there is nothing left to attach."""
        return self

    def dispose_lights(self):
        """Remove the band's two lamps (a host that tears the ring down; safe to call twice)."""
        import bpy
        for lamp in (self.band_sun, self.band_shine):
            if lamp is not None and lamp.name in bpy.data.objects:
                data = lamp.data
                bpy.data.objects.remove(lamp, do_unlink=True)
                if data.users == 0:
                    bpy.data.lights.remove(data)
        self.band_sun = self.band_shine = None
        return self

    # ---- the plate: the band behind every local object ----
    def make_plate(self):
        """Move the ring's visible sky elements into a scene of their own, which Sky.bake renders per frame as a
        PLATE into the sky's camera layer, so every local object draws over the band. WebGPU draws the band without
        depth before every local opaque (sky_worlds.js: "foreground opaques draw later, painting over the depthless
        band"); Eanpa composites its private sky depth layer behind local geometry. In EEVEE's one depth buffer the band,
        at its authored placement, meets an eye-level view about 875 m out along the ring (its walls about 960 m out
        at 30 degrees), so a terrain or a set reaching past that inside a 60 degree wedge each way along the ring
        would lie behind it.

        The plate scene ('eido_ring_plate') holds the band, its walls and cloud sheet, the band's two lamps and the
        plate camera, and shares two objects with the main scene: the group they hang from and the eclipse proxy, which
        shadows both suns. The fog and rain walls stay in the main scene: local haze, depth-tested against the local
        geometry, over the band. Its film is transparent and it takes the main scene's world, which lights the band as
        before. Returns the plate scene."""
        import bpy
        plate = bpy.data.scenes.get(PLATE_SCENE) or bpy.data.scenes.new(PLATE_SCENE)
        coll = bpy.data.collections.get(PLATE_COLLECTION) or bpy.data.collections.new(PLATE_COLLECTION)
        if coll.name not in plate.collection.children:
            plate.collection.children.link(coll)
        moving = [o for o in (self.band, self.walls, self.clouds, self.band_sun, self.band_shine) if o is not None]
        for ob in moving + [o for o in (self.group, self.eclipse_proxy) if o is not None]:
            if ob.name not in coll.objects:
                coll.objects.link(ob)
        # out of the main scene's collections only: the light-linking collections (the band lamps' receivers, the
        # suns' blockers) hold these objects too, and stay as they are
        main = {self.scene.collection} | set(self.scene.collection.children_recursive)
        for ob in moving:
            for c in list(ob.users_collection):
                if c in main:
                    c.objects.unlink(ob)
        cam = bpy.data.objects.get(PLATE_CAMERA)
        if cam is None:
            cam = bpy.data.objects.new(PLATE_CAMERA, bpy.data.cameras.new(PLATE_CAMERA))
        if cam.name not in coll.objects:
            coll.objects.link(cam)
        cd = cam.data
        cd.type = 'PERSP'
        cd.sensor_fit = 'HORIZONTAL'
        cd.shift_x = cd.shift_y = 0.0
        cd.clip_start, cd.clip_end = PLATE_NEAR, 4.0 * R_REF
        plate.camera = cam
        r = plate.render
        r.engine = 'BLENDER_EEVEE'
        r.film_transparent = True
        r.use_compositing = False
        r.use_sequencer = False
        r.use_motion_blur = False
        r.resolution_percentage = 100
        ims = r.image_settings
        ims.media_type = 'IMAGE'
        ims.file_format = 'OPEN_EXR'
        ims.color_mode = 'RGBA'
        ims.color_depth = '16'
        self.plate_scene, self.plate_camera, self.plate_collection = plate, cam, coll
        return plate

    def ring_center_three(self):
        c = self.band.matrix_world.translation
        return P.blender_to_three((c.x, c.y, c.z))

    def eclipse_k(self, direction, origin=None):
        """Eanpa eclipseK: the band's solar visibility at a receiver (three.js point, default the origin)."""
        p = origin if origin is not None else (0.0, 0.0, 0.0)
        if isinstance(p, (int, float)):
            p = (0.0, float(p), 0.0)
        return ring_solar_visibility(p, direction, center=self.ring_center_three())

    def update(self, t):
        """One frame of the band's engine-owned state (ringworld.js update(t)): returns the values to key."""
        sk, wx = self.sky, self.wx
        U = sk.U
        o = self.opts                     # read live: a re-bake after changing these options keys the new values
        self.haze_night_level = float(o.get('hazeNightLevel', 0.055))
        self.foot_width_night = float(o.get('footWidthNight', 0.075))
        self.insc_night_level = float(o.get('inscatterNightLevel', 0.28))
        sun = P.norm3(sk.sun_dir)
        moon = P.norm3(sk.moon_dir)
        el = sun[1]
        pal = sk.state.get('palette') or {}
        day_f = _smooth(-0.10, 0.15, el)
        gain = (0.15 + 0.85 * day_f) * (0.4 + 0.6 * _smooth(-0.05, 0.12, el))
        arch = _smooth(0.10, -0.06, el)
        sun_col = tuple(_mix(tuple(pal.get('sun', (1, 1, 1))), (1, 1, 1), 0.35))
        # haze from the WEATHERED sky (the uniform horizon), dimmed by the eclipse (Eanpa), with the night floor
        ssv = U.get('solarSkyVisibility', 1.0)
        haze = tuple(c * ssv for c in U['horizon'])
        n_k = max(0.0, min(1.0, (0.06 - el) / 0.24))
        if n_k > 0:
            L = self.haze_night_level * n_k
            haze = tuple(max(haze[i], self.ps_haze[i] * L) for i in range(3))
        rain_haze = 0.0
        if wx is not None:
            d, k = wx.state['def_'], wx.state['k']
            rk = d.get('rain', 0.0) * k
            rg = min(1.0, max(0.0, (rk - 0.45) / 0.5))
            rain_haze = rg * rg * (3 - 2 * rg)
            grey = d.get('grey', 0.0) * k
        else:
            grey = 0.0
        # the cloud sheet matches the local volumetrics through their own uniforms (no parallel table)
        cover = max(0.0, min(1.0, 1 - U['largeT']))
        dens = max(0.0, min(1.5, U['finalMul'] / 0.24))
        tint_sun = tuple(c * 0.42 / 7 for c in U['cloudLightColor'])
        a = U['cloudAmbSky']
        kl = U['cloudLightColor']
        lum = a[0] * 0.2126 + a[1] * 0.7152 + a[2] * 0.0722
        peak = max(kl[0], kl[1], kl[2], 1e-4)
        wg = U.get('cloudWeatherGrey', 0.0)
        tint_amb = tuple(a[i] + (lum * kl[i] / peak - a[i]) * wg for i in range(3))
        disp = U['cloudDisplacement']
        # the band's sun: the TRUE sun at full strength, the local palette's colour while it is up, handing over to
        # daylight white as it sets (never to the night palette)
        arch2 = max(0.0, min(1.0, (0.10 - el) / 0.16))
        band_sun_col = _mix(tuple(pal.get('sun', (1, 1, 1))), DAYLIGHT, arch2)
        vals = dict(
            sun_dir=P.three_to_blender(sun), moon_dir=P.three_to_blender(moon), day_f=day_f, gain=gain,
            arch=arch, sun_col=sun_col, haze=haze, rain_haze=rain_haze, time=float(t),
            insc_night=self.insc_night_level + (1.0 - self.insc_night_level) * day_f, veil=0.35 + day_f * 0.65,
            foot_w=self.foot_width_night + (0.022 - self.foot_width_night) * day_f,
            cover=cover, grey=grey, dens=dens, tint_sun=tint_sun, tint_amb=tint_amb, rad=U['cloudRadiance'],
            disp=(disp[2] / (math.pi * 2 * R_REF), disp[0] / 940.0, 0.0),
            band_sun_dir=P.three_to_blender(sun), band_sun_col=band_sun_col,
            band_shine_dir=P.three_to_blender(moon))
        self.last = vals
        return vals

    def key(self, frame, vals):
        """Key one frame: the material values (LINEAR) and the two band lamps."""
        from mathutils import Vector
        from .nodes import key_values
        key_values(self.key_handles, frame, {
            'sun_dir': vals['sun_dir'], 'moon_dir': vals['moon_dir'], 'day_f': vals['day_f'], 'gain': vals['gain'],
            'sun_col': vals['sun_col'], 'haze': vals['haze'], 'rain_haze': vals['rain_haze'],
            'time': vals['time'], 'insc_night': vals['insc_night'], 'veil': vals['veil'], 'foot_w': vals['foot_w'],
            'cover': vals['cover'], 'grey': vals['grey'], 'dens': vals['dens'], 'tint_sun': vals['tint_sun'],
            'tint_amb': vals['tint_amb'], 'rad': vals['rad'], 'disp': vals['disp']})
        for lamp, dkey in ((self.band_sun, 'band_sun_dir'), (self.band_shine, 'band_shine_dir')):
            if lamp is None:
                continue
            d = Vector(vals[dkey]).normalized()
            lamp.rotation_mode = 'QUATERNION'
            lamp.rotation_quaternion = d.to_track_quat('Z', 'Y')
            lamp.keyframe_insert('rotation_quaternion', frame=frame)
        if self.band_sun is not None:
            self.band_sun.data.color = vals['band_sun_col']
            self.band_sun.data.keyframe_insert('color', frame=frame)

    def finish_keys(self):
        from .nodes import set_interpolation
        set_interpolation(self.keys_tree, 'LINEAR')
        for lamp in (self.band_sun, self.band_shine):
            if lamp is not None:
                set_interpolation(lamp, 'LINEAR')
                set_interpolation(lamp.data, 'LINEAR')


# ------------------------------------------------------------------------------------------------ helpers ---

def _find_layer_collection(lc, coll):
    if lc.collection == coll:
        return lc
    for ch in lc.children:
        r = _find_layer_collection(ch, coll)
        if r:
            return r
    return None


def _authored_map(mat):
    """The GLB material's colour image and its around-the-ring repeat (the Mapping node's x scale)."""
    if mat is None or not mat.node_tree:
        return None, 8
    img, rep = None, 8
    for n in mat.node_tree.nodes:
        if n.type == 'TEX_IMAGE' and n.image and n.image.colorspace_settings.name.lower().startswith('srgb'):
            img = n.image
        if n.type == 'MAPPING':
            rep = int(round(n.inputs['Scale'].default_value[0])) or 8
    return img, rep


def _uv_phase(terrain):
    """Eanpa: keep the export's angular UV origin. delta = angle(vertex) - (0.5 - u) * 2pi, circular mean."""
    me = terrain.data
    uvl = me.uv_layers.active
    sx = sy = 0.0
    for loop in me.loops:
        co = me.vertices[loop.vertex_index].co               # local, axis at the origin (Blender: y3 = z, z3 = -y)
        ang = math.atan2(-co.y, co.z)
        u = uvl.data[loop.index].uv[0]
        d = ang - (0.5 - u) * math.pi * 2
        sx += math.cos(d)
        sy += math.sin(d)
    return math.atan2(sy, sx)


def _three_to_blender_arr(v):
    out = np.empty_like(v)
    out[:, 0] = v[:, 0]
    out[:, 1] = -v[:, 2]
    out[:, 2] = v[:, 1]
    return out


def _mesh_from_arrays(name, verts, tris, uv=None):
    import bpy
    me = bpy.data.meshes.new(name)
    nv, nf = len(verts), len(tris)
    me.vertices.add(nv)
    me.vertices.foreach_set('co', np.ascontiguousarray(verts, np.float32).ravel())
    me.loops.add(nf * 3)
    me.loops.foreach_set('vertex_index', np.ascontiguousarray(tris, np.int32).ravel())
    me.polygons.add(nf)
    me.polygons.foreach_set('loop_start', np.arange(0, nf * 3, 3, dtype=np.int32))
    if uv is not None:
        layer = me.uv_layers.new(name='UVMap')
        layer.data.foreach_set('uv', np.ascontiguousarray(uv[tris.ravel()], np.float32).ravel())
    me.update(calc_edges=True)
    me.polygons.foreach_set('use_smooth', np.ones(nf, bool))
    me.validate(clean_customdata=False)
    return me


def _wall_uvs(walls, tile):
    """Cylindrical-planar wall UVs in panel-tile units: u = arc length around / tile, v = radius / tile, each face
    unwrapped across the +-pi seam on its own (the authored wall UVs were smeared band UVs)."""
    me = walls.data
    uvl = me.uv_layers.active or me.uv_layers.new(name='UVMap')
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    # the walls' own axis: their bounds centre (local)
    c = (co.max(0) + co.min(0)) * 0.5
    y3 = co[:, 2] - c[2]
    z3 = -(co[:, 1] - c[1])
    th = np.arctan2(z3, y3)
    rr = np.hypot(y3, z3)
    out = np.zeros((len(me.loops), 2), np.float32)
    for poly in me.polygons:
        idx = [me.loops[li].vertex_index for li in poly.loop_indices]
        a = th[idx].copy()
        if a.max() - a.min() > math.pi:
            a[a < 0] += math.pi * 2
        for k, li in enumerate(poly.loop_indices):
            out[li] = (a[k] * R_REF / tile, rr[idx[k]] / tile)
    uvl.data.foreach_set('uv', out.ravel())


def _cylinder_x(name, radius, length, segments, coll):
    """An open cylinder about X (three's CylinderGeometry rotated onto the ring axis): u = atan2(y3, z3) / 2pi
    around (Eanpa's cloud-shadow convention), v = x / length + 0.5. Two-sided."""
    import bpy
    th = np.arange(segments + 1) / segments * math.pi * 2
    verts, uvs = [], []
    for side in (0, 1):
        x = (side - 0.5) * length
        for k, a in enumerate(th):
            y3, z3 = radius * math.sin(a), radius * math.cos(a)
            verts.append((x, -z3, y3))
            uvs.append((k / segments, side))
    n = segments + 1
    tris = []
    for k in range(segments):
        tris.append((k, k + 1, n + k + 1))
        tris.append((k, n + k + 1, n + k))
    me = _mesh_from_arrays(name, np.array(verts), np.array(tris), np.array(uvs))
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def _cylinder_z(name, radius, height, segments, coll):
    """An open vertical cylinder facing inward (WebGPU BackSide): v = 0 at the bottom, 1 at the top."""
    import bpy
    verts, uvs = [], []
    for side in (0, 1):
        z = (side - 0.5) * height
        for k in range(segments + 1):
            a = k / segments * math.pi * 2
            verts.append((radius * math.cos(a), radius * math.sin(a), z))
            uvs.append((k / segments, side))
    n = segments + 1
    tris = []
    for k in range(segments):
        tris.append((k, n + k + 1, k + 1))          # wound so the normals face the axis
        tris.append((k, n + k, n + k + 1))
    me = _mesh_from_arrays(name, np.array(verts), np.array(tris), np.array(uvs))
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def _world_anchored_tree():
    """Geometry Nodes that draw another object's surface where that object is (Object Info in RELATIVE space),
    whatever this object's own transform: the haze walls' copies under the cloud dome (order_walls_under_dome)."""
    import bpy
    name = 'eido_world_anchored'
    tree = bpy.data.node_groups.get(name)
    if tree is not None:
        return tree
    tree = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    tree.is_modifier = True
    tree.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    tree.interface.new_socket('Source', in_out='INPUT', socket_type='NodeSocketObject')
    tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    gi = tree.nodes.new('NodeGroupInput')
    go = tree.nodes.new('NodeGroupOutput')
    info = tree.nodes.new('GeometryNodeObjectInfo')
    info.transform_space = 'RELATIVE'
    gi.location, info.location, go.location = (-400, 0), (-150, 0), (150, 0)
    tree.links.new(gi.outputs['Source'], info.inputs['Object'])
    tree.links.new(info.outputs['Geometry'], go.inputs['Geometry'])
    return tree


def _opt_on(o, key, default=True):
    from .ring_materials import opt_on
    return opt_on(o, key, default)


def _wave_mode(o):
    w = o.get('waves', 'lightweight')
    if w is False or w in ('off', 'false', 0):
        return 'off'
    return 'lightweight' if w == 'lightweight' else 'full'


def _sun_lamp(name, energy, coll, shadow):
    import bpy
    ld = bpy.data.lights.new(name, 'SUN')
    ld.energy = energy
    ld.angle = math.radians(0.53)
    ld.use_shadow = bool(shadow)
    ob = bpy.data.objects.new(name, ld)
    coll.objects.link(ob)
    return ob


def make_ringworld(scene, assets, opts=None, cache_dir=None, collection=None):
    """makeRingworld({glbBytes, textures, opts}): assets = {glb, landmask, solarColor, solarNormal, solarRough,
    solarMetal, bandNormal, bandAO, bandHeight, waterWaveNormal (optional)} file paths. Options (the JS names):

      look       planetShineColor, hazeNightLevel (0.055), shoreTexels (3; the blur is cached per width),
                 shoreWetness (0.2), waterWhite (False), bandAOFloor (0.62), bandAOPackedNormal (False),
                 bandNormalScale (1.4), analyticBandNormal (True), inscatterEnabled, inscatterNightLevel (0.28),
                 footVeil, footWidthNight (0.075)
      water      waves ('lightweight' | 'full' | False), lightweightWaveSpeed (0.0065), lightweightWaveAmp (0.26),
                 waveAmp (0.55)
      analytic   litBand (True; False: the emissive comparison path), nightTint, nightSat (1.3), nightLevel (1.2)
      geometry   geometryRelief (True), terrainHeightMeters / heightMeters (85), localReliefBlend ((700, 2000) m of
                 arc), around (4096), across (512), panelTile (60), centerY; reliefPrefilter (True, the Blender
                 edition's: the relief filtered to each row's vertex spacing, see ring_terrain_arrays); reliefDir (a
                 folder holding Eanpa's v4 set, ring_relief_v4.bin.gz + ring_albedo_v4.png [+ ring_relief_v3.bin.gz]:
                 load_ring_relief; the band then displaces the eroded v4 heights and wears its albedo, normals and AO,
                 with bandNormalScale 1 and bandAOPackedNormal as Eanpa's host sets them)
      lamps      bandLights, bandSunIntensity (3.2), bandShineIntensity (0.55), bandCastShadow (False, Eanpa's),
                 bandShadowMapSize (4096) or bandShadowTexel (metres)
      elements   ringClouds, cloudHeight (280), cloudAtlas ((8192, 256) or {width, height}), fogWall, rainWall,
                 fogWallRadius (1250)
      look-dev   debugBand ('basic' | 'lighting')
    No counterpart: bandEnvIntensity (no per-material environment intensity in EEVEE), bandLightLayer (light linking
    isolates exactly), the SPOM options (superseded by the displaced relief, as in Eanpa)."""
    return Ringworld(scene, assets, opts, cache_dir, collection)

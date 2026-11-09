"""Render the real landform references like terrain probes, in Blender 5.2 EEVEE: grey clay (albedo 0.18, matte)
under make_sky daylight (Earth, 15:30, cumulus, no cloud shadows on the ground; AgX Medium High Contrast,
exposure +0.5), three views per landform, into renders/:

  <name>_top_hillshade.png   straight down over the whole tile, north up, the sun from the north-west (540 x 540)
  <name>_aerial_45deg.png    a 45-degree aerial over the whole tile, the sun 70 degrees to the left of the view
  <name>_eye_1p7m.png        a camera 1.7 m above the ground at a real viewpoint, standing in the wider context
                             surround (so the horizon is real terrain, with the Earth's curvature), the sun 70 degrees
                             to the left of the view
  <name>_views.json          every camera and the sun, in the tile's local metres, to frame a generated terrain alike

The sun's elevation is the same in every view (make_sky's 15:30: 37.7 degrees); its azimuth is set per view through
make_sky's `azimuth` option, so the light falls the same way relative to every camera and the tile stays
geographically oriented (x east, y north, z up, heights in metres above the tile's lowest point).

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \\
        <worktree>/blender/tests/terrain_new/reference/render_references.py [--only a,b] [--views top,aerial,eye] \\
        [--sky-cache <temp folder>]

render_probe() takes any heightfield, so a generated terrain renders exactly as the references do, from a
Blender script of its own:

    sys.path.insert(0, '<worktree>/blender/tests/terrain_new/reference')
    from render_references import render_probe
    render_probe('gen_volcano', h, pixel_m, out_dir, cache_root=<temp folder>,      # h: float metres, row 0 north
                 eye=dict(x=-6000, y=2000, look_x=0, look_y=0, look_dz=-500, lens_mm=35))   # local metres
"""
import argparse
import json
import math
import os
import shutil
import sys
import tempfile
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
WORKTREE_BLENDER = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, WORKTREE_BLENDER)
sys.path.insert(0, HERE)
import landform_refs as R  # noqa: E402
from sites import SITES  # noqa: E402
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.sky import palette as P  # noqa: E402

OUT = os.path.join(HERE, 'renders')
EYE_HEIGHT = 1.7
R_EFF = R.EARTH_R * 7.0 / 6.0              # the Earth's radius with standard refraction (k = 1/7), for the horizon
CLAY = (0.18, 0.18, 0.18)                  # linear albedo of the grey clay: photographic mid grey, pure diffuse
LOOK = 'AgX - Medium High Contrast'        # base AgX flattened the forms under the sky's blue fill (first pass)
EXPOSURE = 0.5                             # sunlit level clay lands just above mid grey
SUN_ELEV_HOURS = 15.5                      # make_sky's time of day: the sun 37.7 degrees up
SUN_LEFT_DEG = 70.0                        # aerial and eye views: the sun this far left of the view heading
TOP_SUN_AZIMUTH = 315.0                    # top view: the sun from the north-west (compass degrees)


# ---------------------------------------------------------------- scene
def new_scene(res, samples, exposure):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = samples
    sc.eevee.use_raytracing = True
    sc.eevee.use_shadows = True
    sc.view_settings.view_transform = 'AgX'
    try:
        sc.view_settings.look = LOOK
    except TypeError:
        print(f'[refs] no look {LOOK!r} in this Blender: base AgX', flush=True)
    sc.view_settings.exposure = exposure
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    sc.frame_start = sc.frame_end = 1
    sc.frame_set(1)
    return sc


def material(name, rgb, roughness, specular=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgb, 1.0)
    b.inputs['Roughness'].default_value = roughness
    b.inputs['Specular IOR Level'].default_value = specular
    return m


def grid_mesh(name, z, xs, ys, face_keep=None, skirt_m=0.0, mat=None):
    """A grid object: z (rows, cols) over pixel-centre axes xs (west to east) and ys (north to south), quads
    wound to face +Z; face_keep (rows-1, cols-1) drops quads; skirt_m hangs a vertical skirt from the border."""
    rows, cols = z.shape
    X, Y = np.meshgrid(np.asarray(xs, np.float64), np.asarray(ys, np.float64))
    co = [np.stack([X, Y, z], -1).reshape(-1, 3)]
    idx = np.arange(rows * cols).reshape(rows, cols)
    quads = np.stack([idx[:-1, :-1], idx[1:, :-1], idx[1:, 1:], idx[:-1, 1:]], -1).reshape(-1, 4)
    if face_keep is not None:
        quads = quads[np.asarray(face_keep, bool).ravel()]
    quads = [quads]
    if skirt_m > 0:                                       # its own vertices, so smooth shading stays off the border
        ring = np.concatenate([idx[0, :], idx[1:, -1], idx[-1, -2::-1], idx[-2:0:-1, 0]])   # clockwise from above
        top = co[0][ring]
        bot = top.copy()
        bot[:, 2] -= skirt_m
        base = rows * cols
        k = len(ring)
        a = base + np.arange(k)
        b = base + (np.arange(k) + 1) % k
        quads.append(np.stack([a, b, b + k, a + k], -1))
        co += [top, bot]
    co = np.concatenate(co).astype(np.float32)
    quads = np.concatenate(quads).astype(np.int32)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(co))
    me.vertices.foreach_set('co', co.ravel())
    me.loops.add(quads.size)
    me.loops.foreach_set('vertex_index', quads.ravel())
    me.polygons.add(len(quads))
    me.polygons.foreach_set('loop_start', np.arange(len(quads), dtype=np.int32) * 4)
    me.update(calc_edges=True)
    me.polygons.foreach_set('use_smooth', np.ones(len(quads), dtype=bool))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if mat is not None:
        me.materials.append(mat)
    return ob


def axes(rows, cols, pixel_m):
    return (np.arange(cols) + 0.5 - cols / 2.0) * pixel_m, (rows / 2.0 - np.arange(rows) - 0.5) * pixel_m


def place_camera(cam, eye, target, up=(0.0, 0.0, 1.0)):
    eye, target, up = Vector(eye), Vector(target), Vector(up)
    back = (eye - target).normalized()
    right = up.cross(back)
    if right.length < 1e-6:
        right = Vector((1.0, 0.0, 0.0))
    right.normalize()
    upc = back.cross(right)
    rot = Matrix((right, upc, back)).transposed()
    cam.matrix_world = Matrix.Translation(eye) @ rot.to_4x4()


def sun_azimuth_option(direction_xy):
    """make_sky's `azimuth` (SkySystem azBase) that puts the sun toward a Blender horizontal direction at
    SUN_ELEV_HOURS: the sun's three.js azimuth is azBase + arc_az(hours); Blender (x, y) = (cos az, -sin az)."""
    phi = math.atan2(direction_xy[1], direction_xy[0])
    return -phi - P.arc_az(SUN_ELEV_HOURS, 0.9)


def compass(deg):
    a = math.radians(deg)
    return (math.sin(a), math.cos(a))


def frame_points(z, xs, ys):
    """What must stay in an aerial frame: the tile's border at its real heights and the highest point of each
    eighth-by-eighth block (a summit stands up out of the frame before any border does)."""
    rows, cols = z.shape
    pts = []
    for t in np.linspace(0, 1, 33):
        c, r = int(round(t * (cols - 1))), int(round(t * (rows - 1)))
        pts += [(xs[c], ys[0], z[0, c]), (xs[c], ys[-1], z[-1, c]), (xs[0], ys[r], z[r, 0]), (xs[-1], ys[r], z[r, -1])]
    for br in range(8):
        for bc in range(8):
            blk = z[br * rows // 8:(br + 1) * rows // 8, bc * cols // 8:(bc + 1) * cols // 8]
            r, c = np.unravel_index(int(np.argmax(blk)), blk.shape)
            pts.append((xs[bc * cols // 8 + c], ys[br * rows // 8 + r], blk[r, c]))
    return np.array(pts, np.float64)


def fit_aerial(pts, zmid, azimuth_deg, elev_deg=45.0, lens=35.0, aspect=16 / 9, margin=0.94):
    """The camera of the 45-degree aerial: it stands on the line rising at elev_deg from the tile centre toward
    azimuth_deg, as close as it can while every frame point stays inside `margin` of the frame, aimed along the
    heading so the tile sits centred top to bottom. Returns (position, target)."""
    bx, by = compass(azimuth_deg)
    ce, se = math.cos(math.radians(elev_deg)), math.sin(math.radians(elev_deg))
    tan_h = 18.0 / lens
    tan_v = tan_h / aspect
    span = float(np.ptp(pts[:, 0]) + np.ptp(pts[:, 1]))
    best = None
    for D in np.geomspace(0.3 * span, 4.0 * span, 160):
        pos = np.array([bx * D * ce, by * D * ce, zmid + D * se])
        for delta in np.linspace(-0.4 * span, 0.4 * span, 81):
            tgt = np.array([bx * delta, by * delta, zmid])
            f = tgt - pos
            f /= np.linalg.norm(f)
            r = np.cross(f, (0.0, 0.0, 1.0))
            r /= np.linalg.norm(r)
            u = np.cross(r, f)
            v = pts - pos
            dep = v @ f
            if np.any(dep <= 0):
                continue
            x, y = (v @ r) / dep / tan_h, (v @ u) / dep / tan_v
            if np.abs(x).max() <= margin and y.min() >= -margin and y.max() <= margin:
                off = abs(y.max() + y.min())
                if best is None or off < best[0]:
                    best = (off, pos, tgt)
        if best is not None:
            return best[1], best[2]
    return pos, np.array([0.0, 0.0, zmid])


# ---------------------------------------------------------------- one view
def render_view(kind, h, pixel_m, out_png, cache_dir, exposure, samples, water=None, context=None, eye=None,
                aerial_azimuth=200.0, clouds='cumulus', log=print, dry=False):
    """Build the scene for one view of heightfield h (metres, north-up rows) and render it; returns the view's
    record (cameras, sun) for <name>_views.json. water: (mask uint8 rows x cols, [bodies with level_m]) or None.
    context: (hc, pixel_c) centred on the same point, eye view only. eye: dict(x, y, look_x, look_y, look_dz,
    lens_mm) in local metres."""
    t0 = time.time()
    rows, cols = h.shape
    ext = (cols * pixel_m, rows * pixel_m)
    z0 = float(h.min())
    res = (540, 540) if kind == 'top' else (960, 540)
    sc = new_scene(res, samples, exposure)
    clay = material('grey_clay', CLAY, 0.9, specular=0.0)     # no grazing sheen: it read as haze on the DEM
    wmat = material('water', (0.02, 0.05, 0.07), 0.15)       # a breeze on it: no mirror doubling the terrain
    xs, ys = axes(rows, cols, pixel_m)
    z = h.astype(np.float64) - z0
    X, Y = np.meshgrid(xs, ys)
    sea = [w for w in (water[1] if water else []) if w['kind'] == 'sea']
    lakes = [w for w in (water[1] if water else []) if w['kind'] == 'lake']
    wmask = water[0] >= 128 if water else np.zeros(h.shape, bool)
    z = np.where(wmask, z - 10.0, z)                      # the ground under water drops away from the water plane
    cam_xy = None
    if kind == 'eye':
        cam_xy = (eye['x'], eye['y'])
        z = z - ((X - cam_xy[0]) ** 2 + (Y - cam_xy[1]) ** 2) / (2 * R_EFF)
    grid_mesh('terrain', z, xs, ys, skirt_m=(15.0 if kind == 'eye' else 0.0), mat=clay)
    for w in lakes:                                       # one flat water sheet per lake, over its mask
        m = water[0] == w['mask_value']
        if not m.any():
            continue
        r_idx, c_idx = np.nonzero(m)
        r0, r1, c0, c1 = max(r_idx.min() - 1, 0), min(r_idx.max() + 2, rows), max(c_idx.min() - 1, 0), min(c_idx.max() + 2, cols)
        sub = m[r0:r1, c0:c1]
        keep = sub[:-1, :-1] | sub[1:, :-1] | sub[1:, 1:] | sub[:-1, 1:]
        wz = np.full(sub.shape, w['level_m'] - z0 + 0.1)
        if kind == 'eye':
            wz = wz - ((X[r0:r1, c0:c1] - cam_xy[0]) ** 2 + (Y[r0:r1, c0:c1] - cam_xy[1]) ** 2) / (2 * R_EFF)
        grid_mesh('lake_' + w['name'].replace(' ', '_'), wz, xs[c0:c1], ys[r0:r1], face_keep=keep, mat=wmat)
    if context is not None and kind == 'eye':
        hc, pc = context
        rc, cc = hc.shape
        xcs, ycs = axes(rc, cc, pc)
        XC, YC = np.meshgrid(xcs, ycs)
        zc = hc.astype(np.float64) - z0
        inside = (np.abs(XC) < ext[0] / 2) & (np.abs(YC) < ext[1] / 2)
        meta_t = dict(rows=rows, cols=cols, pixel_size_m=pixel_m)
        # under the tile the surround follows the tile's own ground, 8 m down, and its quads wholly inside are cut
        zc[inside] = R.sample(z, meta_t, XC[inside], YC[inside]) - 8.0
        if sea:
            zc = np.where(hc <= sea[0]['level_m'] + 0.3, zc - 10.0, zc)
        zc = zc - ((XC - cam_xy[0]) ** 2 + (YC - cam_xy[1]) ** 2) / (2 * R_EFF) * (~inside)
        shrink = (np.abs(XC) < ext[0] / 2 - pc) & (np.abs(YC) < ext[1] / 2 - pc)
        keep = ~(shrink[:-1, :-1] & shrink[1:, :-1] & shrink[1:, 1:] & shrink[:-1, 1:])
        grid_mesh('context', zc, xcs, ycs, face_keep=keep, mat=clay)
        span = (cc * pc, rc * pc)
    else:
        span = ext
    for w in sea:
        bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0.0, 0.0, w['level_m'] - z0 + 0.1))
        p = bpy.context.active_object
        p.name = 'sea'
        p.scale = (span[0], span[1], 1.0)
        p.data.materials.append(wmat)

    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    zmax, zmid = float(z.max()), float(np.median(z))
    rec = dict(view=kind, resolution=list(res), tile_extent_m=list(ext), z_origin_m=z0)
    if kind == 'top':
        alt = 4.0 * max(ext)
        cam.data.lens = 18.0 * alt / (0.49 * max(ext))      # framed at the lowest ground: no edge shows anywhere
        cam.data.clip_start, cam.data.clip_end = max(alt - zmax - 50.0, 1.0), alt + 50.0
        place_camera(cam, (0.0, 0.0, alt), (0.0, 0.0, 0.0), up=(0.0, 1.0, 0.0))
        sun_xy = compass(TOP_SUN_AZIMUTH)
        rec.update(camera=[0.0, 0.0, alt], target=[0.0, 0.0, 0.0], up='north', lens_mm=cam.data.lens,
                   sun_compass_deg=TOP_SUN_AZIMUTH)
    elif kind == 'aerial':
        bx, by = compass(aerial_azimuth)
        p, t = fit_aerial(frame_points(z, xs, ys), zmid, aerial_azimuth)
        pos, tgt = Vector(p), Vector(t)
        dist = (pos - tgt).length
        cam.data.lens = 35.0
        cam.data.clip_start, cam.data.clip_end = dist * 0.02, dist * 6
        place_camera(cam, pos, tgt)
        hd = math.atan2(-by, -bx) + math.radians(SUN_LEFT_DEG)
        sun_xy = (math.cos(hd), math.sin(hd))
        rec.update(camera=list(pos), target=list(tgt), lens_mm=35.0, azimuth_deg=aerial_azimuth,
                   elevation_deg=45.0, sun_left_of_view_deg=SUN_LEFT_DEG)
    else:
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        hit, loc, *_ = sc.ray_cast(dg, Vector((eye['x'], eye['y'], 1.0e5)), Vector((0.0, 0.0, -1.0)))
        gz = loc.z if hit else float(R.sample(z, dict(rows=rows, cols=cols, pixel_size_m=pixel_m), eye['x'], eye['y']))
        pos = Vector((eye['x'], eye['y'], gz + EYE_HEIGHT))
        if context is not None and (abs(eye['look_x']) > ext[0] / 2 or abs(eye['look_y']) > ext[1] / 2):
            hc, pc = context
            lz = float(R.sample(hc.astype(np.float64) - z0, dict(rows=hc.shape[0], cols=hc.shape[1], pixel_size_m=pc),
                                eye['look_x'], eye['look_y']))
        else:
            lz = float(R.sample(z, dict(rows=rows, cols=cols, pixel_size_m=pixel_m), eye['look_x'], eye['look_y']))
        tgt = Vector((eye['look_x'], eye['look_y'], lz + eye.get('look_dz', 0.0)))
        cam.data.lens = eye.get('lens_mm', 35.0)
        cam.data.clip_start = 1.0
        cam.data.clip_end = 2.5 * max(span)
        place_camera(cam, pos, tgt)
        d = tgt - pos
        hd = math.atan2(d.y, d.x) + math.radians(SUN_LEFT_DEG)
        sun_xy = (math.cos(hd), math.sin(hd))
        rec.update(camera=list(pos), ground_z=gz, target=list(tgt), lens_mm=cam.data.lens,
                   sun_left_of_view_deg=SUN_LEFT_DEG, earth_curvature_R_eff_m=R_EFF)
    if dry:                                               # the scene only: no sky bake, no render (no GPU)
        log(f'[refs] dry {kind}: camera {tuple(round(v, 1) for v in cam.location)} lens {cam.data.lens:.1f} '
            f'objects {[o.name for o in sc.objects]} {time.time() - t0:.1f}s', flush=True)
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        frame = [cam.matrix_world @ v for v in cam.data.view_frame(scene=sc)]   # tr, br, bl, tl corners
        o = cam.matrix_world.translation
        for name, (u, v) in (('centre', (0.5, 0.5)), ('bottom', (0.5, 0.95)), ('bottom-left', (0.1, 0.9)),
                             ('mid-right', (0.9, 0.6))):
            top = frame[3].lerp(frame[0], u)
            bot = frame[2].lerp(frame[1], u)
            p = top.lerp(bot, v)
            hit, loc, _n, _i, ob, _m = sc.ray_cast(dg, o, (p - o).normalized())
            log(f'[refs]   ray {name}: ' + (f'{ob.name} at {(loc - o).length:.0f} m, z {loc.z:.1f}' if hit else 'sky'),
                flush=True)
        return rec
    os.makedirs(cache_dir, exist_ok=True)
    sky = make_sky(sc, camera=cam, world='earth', hours=SUN_ELEV_HOURS, clouds=clouds, cache_dir=cache_dir,
                   quality='film', shadows=False, azimuth=sun_azimuth_option(sun_xy))
    s = Vector(sky.sun_dir)
    got = math.atan2(s.y, s.x)
    want = math.atan2(sun_xy[1], sun_xy[0])
    err = math.degrees(abs((got - want + math.pi) % (2 * math.pi) - math.pi))
    if err > 0.5:
        raise RuntimeError(f'make_sky put the sun {err:.2f} degrees off the asked direction')
    rec.update(sun_dir=list(s), sun_elevation_deg=math.degrees(math.asin(max(-1.0, min(1.0, s.z)))),
               sky=dict(world='earth', hours=SUN_ELEV_HOURS, clouds=clouds, shadows=False))
    sky.bake(frame_start=1, frame_end=1, log=lambda *a, **k: None)
    sc.render.filepath = out_png
    bpy.ops.render.render(write_still=True)
    log(f'[refs] {os.path.basename(out_png)} {time.time() - t0:.1f}s', flush=True)
    rec['camera'] = [round(v, 3) for v in rec['camera']]
    rec['target'] = [round(v, 3) for v in rec['target']]
    return rec


def render_probe(name, h, pixel_m, out_dir, cache_root, views=('top', 'aerial', 'eye'), water=None, context=None,
                 eye=None, aerial_azimuth=200.0, exposure=EXPOSURE, samples=16, clouds='cumulus', dry=False):
    """The three probe views of one heightfield (float metres, row 0 = north) into out_dir/<name>_*.png and
    <name>_views.json. A generated terrain passes its own eye dict (local metres) and, if it has one, a context."""
    os.makedirs(out_dir, exist_ok=True)
    files = dict(top='top_hillshade', aerial='aerial_45deg', eye='eye_1p7m')
    recs = {}
    for v in views:
        if v == 'eye' and eye is None:
            continue
        recs[v] = render_view(v, h, pixel_m, os.path.join(out_dir, f'{name}_{files[v]}.png'),
                              os.path.join(cache_root, f'{name}_{v}'), exposure, samples, water=water,
                              context=context, eye=eye, aerial_azimuth=aerial_azimuth, clouds=clouds, dry=dry)
    if dry:
        return recs
    path = os.path.join(out_dir, f'{name}_views.json')
    old = {}
    if os.path.exists(path):
        with open(path) as f:
            old = json.load(f)
    old.update(recs)
    with open(path, 'w') as f:
        json.dump(old, f, indent=1)
    return recs


# ---------------------------------------------------------------- the references
def reference_inputs(name):
    s = SITES[name]
    h, meta = R.load(name)
    ctx = None
    try:
        hc, mc = R.load(name, context=True)
        ctx = (hc, mc['pixel_size_m'])
    except FileNotFoundError:
        pass
    water = None
    if meta.get('water_mask_png'):
        water = (R.read_png(os.path.join(R.DATA, meta['water_mask_png'])), meta['water'])
    ev = s['views']['eye']
    ex, ey = R.latlon_to_xy(meta, *ev['at'])
    lx, ly = R.latlon_to_xy(meta, *ev['look'])
    eye = dict(x=float(ex), y=float(ey), look_x=float(lx), look_y=float(ly), look_dz=ev.get('look_dz', 0.0),
               lens_mm=ev.get('lens_mm', 35.0))
    return h, meta, ctx, water, eye, s['views']['aerial'].get('azimuth_deg', 200.0)


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='')
    ap.add_argument('--views', default='top,aerial,eye')
    ap.add_argument('--samples', type=int, default=16)
    ap.add_argument('--exposure', type=float, default=EXPOSURE)
    ap.add_argument('--clouds', default='cumulus')
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--sky-cache', default=None, help='a temp folder for the sky layers (removed after each view)')
    ap.add_argument('--dry', action='store_true', help='build every scene, no sky bake and no render (no GPU)')
    a = ap.parse_args(argv)
    names = [n for n in (a.only.split(',') if a.only else R.names()) if n]
    cache_root = a.sky_cache or tempfile.mkdtemp(prefix='landform_refs_sky_')
    for name in names:
        h, meta, ctx, water, eye, az = reference_inputs(name)
        render_probe(name, h, meta['pixel_size_m'], a.out, cache_root, views=a.views.split(','), water=water,
                     context=ctx, eye=eye, aerial_azimuth=az, exposure=a.exposure, samples=a.samples,
                     clouds=a.clouds, dry=a.dry)
        for v in ('top', 'aerial', 'eye'):
            shutil.rmtree(os.path.join(cache_root, f'{name}_{v}'), ignore_errors=True)
    print('[refs] done', flush=True)


if __name__ == '__main__':
    main()

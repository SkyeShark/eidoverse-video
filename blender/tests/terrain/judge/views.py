"""The judge's views (DESIGN.md section 10 items 5-6): the reference rig's three grey-clay probes of a generated
terrain, its eye-level spot matched to the reference's kind of view, and (on a Terrain built in Blender) the hero
and textured views of its ring mesh.

Numpy (any Python):
    eye = eye_spot(h, cell, ref)              # render_probe's eye dict in the tile's local metres, matched to the
                                              # reference's kind of view (refs.EYE_KIND) and its distance and lens
Blender (bpy):
    render_field(name, h, cell, ref, out_dir, cache_root, context=None, water=None)
                                              # top / aerial / eye through reference/render_references.render_probe
    render_object_views(t.height_at, side, centre, ref, eye, out_dir, cache_root, name, views=('aerial', 'eye'))
                                              # a built Terrain's ring mesh (hero levels, palette, rocks) under the
                                              # same sky, sun and cameras as the probes

The eye search mirrors Terrain.viewpoint (api.py): candidates every 5 degrees around the target at 0.55-1.5 x the
distance, the sight line from 3 m out clearing the ground by a metre, the footing under 30 degrees, ranked by
'low' or 'high' ground, then by the distance asked for. A Terrain uses its own viewpoint().
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np

from . import family as F
from .refs import REFERENCE_DIR, grid

PREFER = {'plain': 'low', 'rim': 'high', 'floor': 'low', 'ridge': 'high', 'interdune': 'low', 'inside': 'low',
          'shore': 'low'}


def local_xy(n, cell):
    """Cell-centre coordinates (x east, y north) of a square tile centred on (0, 0), the terrain frame."""
    c = (np.arange(n) + 0.5 - n / 2.0) * cell
    return np.meshgrid(c, c)


def _sample(h, cell, x, y):
    n = h.shape[0]
    return F.sample(h, np.asarray(x) / cell + n / 2.0 - 0.5, np.asarray(y) / cell + n / 2.0 - 0.5)


def target_for(kind, h, cell):
    """The point the eye looks at, by kind of view: (x, y) local metres."""
    n = h.shape[0]
    hb = F.blur(h, 2.0)
    X, Y = local_xy(n, cell)
    inner = (np.abs(X) < 0.3 * n * cell) & (np.abs(Y) < 0.3 * n * cell)
    if kind in ('rim', 'inside'):
        k = int(np.argmin(np.where(inner, hb, np.inf)))
    elif kind == 'floor':
        path = F.trunk(h, cell)
        if path:
            i, j = path[int(0.6 * (len(path) - 1))]
            return float(X[j, i]), float(Y[j, i])
        k = int(np.argmin(np.where(inner, hb, np.inf)))
    else:                                                              # plain, ridge, interdune, shore
        k = int(np.argmax(np.where(inner, hb, -np.inf)))
    j, i = np.unravel_index(k, h.shape)
    return float(X[j, i]), float(Y[j, i])


def reference_pitch(ref):
    """The pitch (degrees) of the reference's own eye view: its camera, 1.7 m over its ground, toward its look point
    (that ground plus look_dz). The generated view takes the same pitch: a look_dz means nothing on another terrain
    (Fuji's -1450 m aims below its summit; on a lower cone it would aim into the mountain)."""
    rev = ref.eye()
    if not rev:
        return 5.0
    n = ref.h.shape[0]
    ez = float(_sample(ref.h, ref.pixel, rev['x'], rev['y'])) + 1.7
    lz = float(_sample(ref.h, ref.pixel, np.clip(rev['look_x'], -0.5 * n * ref.pixel, 0.5 * n * ref.pixel),
                       np.clip(rev['look_y'], -0.5 * n * ref.pixel, 0.5 * n * ref.pixel))) + rev.get('look_dz', 0.0)
    return math.degrees(math.atan2(lz - ez, math.hypot(rev['look_x'] - rev['x'], rev['look_y'] - rev['y'])))


def eye_spot(h, cell, ref, kind=None, distance=None, pitch_deg=None, lens_mm=None, clearance_m=1.0):
    """render_probe's eye dict (x, y, look_x, look_y, look_dz, lens_mm, ...) for a heightfield (row 0 = south,
    metres, centred on the tile centre), matched to the reference's kind of view: the target by kind
    (target_for), the eye where it sees the target's ground (+2 m), the camera at the reference's own pitch and
    lens, its distance the reference's (capped inside the tile). The footing limit relaxes from 30 to 45 and 60
    degrees when nothing gentler sees the target; failing that the best clearance is taken ('best_effort')."""
    h = np.asarray(h, np.float64)
    n = h.shape[0]
    kind = kind or ref.eye_kind
    rev = ref.eye() or dict(x=-0.3 * ref.extent, y=-0.3 * ref.extent, look_x=0, look_y=0, look_dz=0, lens_mm=35)
    d_ref = math.hypot(rev['look_x'] - rev['x'], rev['look_y'] - rev['y'])
    distance = float(distance or min(max(d_ref, 30.0), 0.42 * n * cell))
    pitch = float(reference_pitch(ref) if pitch_deg is None else pitch_deg)
    lens_mm = float(lens_mm or rev.get('lens_mm', 35.0))
    tx, ty = target_for(kind, h, cell)
    tz0 = float(_sample(h, cell, tx, ty))
    tz = tz0 + max(2.0, 0.01 * distance)        # the sight line's end: over a flat floor a 2 m target only grazes
    half = 0.5 * n * cell - 2 * cell
    px = np.zeros(0)
    if kind == 'floor':                       # stand on the valley floor itself: the trunk's cells, up or down valley
        path = F.trunk(h, cell)
        if path:
            X, Y = local_xy(n, cell)
            pp = np.array([(X[j, i], Y[j, i]) for i, j in path[::2]])
            dd = np.hypot(pp[:, 0] - tx, pp[:, 1] - ty)
            sel = (dd > 0.3 * distance) & (dd < 1.5 * distance)
            px, py, D = pp[sel, 0], pp[sel, 1], dd[sel]
    if not px.size:
        az = np.radians(np.arange(0.0, 360.0, 5.0))
        fac = np.array([1.0, 0.85, 1.15, 0.7, 1.3, 0.55, 1.5])
        A, Fm = np.meshgrid(az, fac)
        A, D = A.ravel(), Fm.ravel() * distance
        px, py = tx + D * np.sin(A), ty + D * np.cos(A)
    ok = (np.abs(px) < half) & (np.abs(py) < half)
    if not ok.any():
        raise ValueError(f'eye_spot: no point {distance:.0f} m from the target lies inside the tile')
    px, py, D = px[ok], py[ok], D[ok]
    gz = _sample(h, cell, px, py)
    s = grid.slope_deg(h, cell)
    sl = _sample(s, cell, px, py)
    ez = gz + 1.7
    t0 = np.minimum(3.0 / np.maximum(D, 3.0), 0.5)[:, None]
    t = t0 + (0.97 - t0) * np.linspace(0.0, 1.0, 160)[None, :]
    lx, ly = px[:, None] + (tx - px[:, None]) * t, py[:, None] + (ty - py[:, None]) * t
    lz = ez[:, None] + (tz - ez[:, None]) * t
    clear = (lz - _sample(h, cell, lx, ly)).min(1)
    best_effort = False
    for slope_max in (30.0, 45.0, 60.0):
        good = (sl <= slope_max) & (clear >= clearance_m)
        if good.any():
            break
    else:
        good = clear >= clear.max() - 1e-9
        best_effort = True
    rel = (gz - gz.min()) / max(float(np.ptp(gz)), 1e-6)
    score = (1.0 - rel if PREFER.get(kind, 'low') == 'low' else rel) * 6.0
    score = score - np.abs(D / distance - 1.0) * 4.0 + np.minimum(clear, 50.0) / 50.0
    score[~good] = -np.inf
    b = int(np.argmax(score))
    d = math.hypot(tx - px[b], ty - py[b])
    look_dz = float(ez[b] + d * math.tan(math.radians(pitch)) - tz0)            # the reference's pitch
    return dict(x=float(px[b]), y=float(py[b]), look_x=tx, look_y=ty, look_dz=look_dz, lens_mm=lens_mm, kind=kind,
                pitch_deg=pitch, clearance_m=float(clear[b]), distance_m=float(d), footing_deg=float(sl[b]),
                best_effort=best_effort)


def terrain_eye(t, ref, kind=None):
    """The eye spot of a built Terrain through its own viewpoint() (world metres), as render_probe's dict in the main
    tile's local metres plus 'world' (the Viewpoint)."""
    kind = kind or ref.eye_kind
    lv = t.main
    h = np.asarray(t.fields('main')['h'], np.float64)
    cx, cy = lv.x0 + lv.side / 2.0, lv.y0 + lv.side / 2.0
    tx, ty = target_for(kind, h, lv.cell)
    rev = ref.eye() or {}
    d_ref = math.hypot(rev.get('look_x', 0) - rev.get('x', 0), rev.get('look_y', 0) - rev.get('y', 0)) or 0.3 * lv.side
    vp = t.viewpoint((cx + tx, cy + ty), min(d_ref, 0.42 * lv.side), look_dz=2.0, prefer=PREFER.get(kind, 'low'),
                     lens_mm=rev.get('lens_mm', 35.0))
    pitch = reference_pitch(ref)
    d = math.hypot(vp.eye[0] - cx - tx, vp.eye[1] - cy - ty)
    look_dz = float(vp.eye[2] + d * math.tan(math.radians(pitch)) - float(t.height_at(cx + tx, cy + ty)))
    return dict(x=vp.eye[0] - cx, y=vp.eye[1] - cy, look_x=tx, look_y=ty, look_dz=look_dz,
                lens_mm=float(rev.get('lens_mm', 35.0)), kind=kind, pitch_deg=pitch, world=vp)


# ------------------------------------------------------------------------------------------------- Blender ---

def _rig():
    if REFERENCE_DIR not in sys.path:
        sys.path.insert(0, REFERENCE_DIR)
    import render_references as RR                                     # bpy: Blender only
    return RR


def render_field(name, h, cell, ref, out_dir, cache_root, context=None, water=None, eye=None,
                 views=('top', 'aerial', 'eye'), samples=16):
    """The reference rig's three probes of a heightfield (row 0 = south) into out_dir/<name>_*.png: the grey clay,
    sky, sun and cameras of the references' own renders, the aerial from the reference's azimuth, the eye at the
    matched spot. context: (h_context row 0 = south, cell) centred on the same point. Returns (records, eye)."""
    RR = _rig()
    if eye is None and 'eye' in views:
        eye = eye_spot(h, cell, ref)
    ctx = None
    if context is not None:
        ctx = (grid.to_north_up(np.asarray(context[0], np.float32)), float(context[1]))
    recs = RR.render_probe(name, grid.to_north_up(np.asarray(h, np.float32)), float(cell), out_dir, cache_root,
                           views=views, water=water, context=ctx,
                           eye={k: eye[k] for k in ('x', 'y', 'look_x', 'look_y', 'look_dz', 'lens_mm')} if eye else None,
                           aerial_azimuth=ref.aerial_azimuth(), samples=samples)
    return recs, eye


def render_object_views(height_at, side, centre, ref, eye, out_dir, cache_root, name, views=('aerial', 'eye'),
                        samples=16, exposure=None):
    """A built Terrain's object (its ring mesh with hero levels, its material, its rocks) under the probes' sky and
    cameras. Every height comes from the terrain's own height_at (world metres, exact on the rendered triangles: the
    mesh's z datum is the terrain's, not the DEM's): the aerial framed on the main window (`side` metres square,
    centred at `centre`), the eye at `eye` (render_probe's dict, local metres). The scene must already hold the
    object; this adds the camera and the sky and renders out_dir/<name>_<view>.png. Returns the records."""
    import bpy
    from mathutils import Vector
    RR = _rig()
    from eidoblend.sky import make_sky
    cx, cy = centre
    m = 256                                                           # the main window sampled for the framing
    loc_axis = (np.arange(m) + 0.5 - m / 2.0) * (side / m)
    xs, ys = loc_axis, loc_axis[::-1]                                 # render_references' axes: ys north to south
    XW, YW = np.meshgrid(xs + cx, ys + cy)
    hn = np.asarray(height_at(XW, YW), np.float64)                    # north-up, the mesh's own z
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = samples
    sc.view_settings.view_transform = 'AgX'
    try:
        sc.view_settings.look = RR.LOOK
    except TypeError:
        pass
    sc.view_settings.exposure = RR.EXPOSURE if exposure is None else exposure
    sc.render.resolution_x, sc.render.resolution_y = 960, 540
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    recs = {}
    for view in views:
        cam = bpy.data.objects.get('judge_cam') or bpy.data.objects.new('judge_cam', bpy.data.cameras.new('judge_cam'))
        if cam.name not in sc.collection.objects:
            sc.collection.objects.link(cam)
        sc.camera = cam
        if view == 'aerial':
            pts = RR.frame_points(hn, xs, ys)
            pos, tgt = RR.fit_aerial(pts, float(np.median(hn)), ref.aerial_azimuth())
            pos, tgt = Vector((pos[0] + cx, pos[1] + cy, pos[2])), Vector((tgt[0] + cx, tgt[1] + cy, tgt[2]))
            cam.data.lens = 35.0
            dist = (pos - tgt).length
            cam.data.clip_start, cam.data.clip_end = dist * 0.02, dist * 6
            bx, by = RR.compass(ref.aerial_azimuth())
            hd = math.atan2(-by, -bx) + math.radians(RR.SUN_LEFT_DEG)
        else:
            ex, ey = eye['x'] + cx, eye['y'] + cy
            pos = Vector((ex, ey, float(height_at(ex, ey)) + RR.EYE_HEIGHT))
            lx, ly = eye['look_x'] + cx, eye['look_y'] + cy
            tgt = Vector((lx, ly, float(height_at(lx, ly)) + eye.get('look_dz', 0.0)))
            cam.data.lens = eye.get('lens_mm', 35.0)
            cam.data.clip_start, cam.data.clip_end = 0.1, 2.5 * side * 4
            d = tgt - pos
            hd = math.atan2(d.y, d.x) + math.radians(RR.SUN_LEFT_DEG)
        RR.place_camera(cam, pos, tgt)
        sun_xy = (math.cos(hd), math.sin(hd))
        cache_dir = os.path.join(cache_root, f'{name}_{view}')
        os.makedirs(cache_dir, exist_ok=True)
        sky = make_sky(sc, camera=cam, world='earth', hours=RR.SUN_ELEV_HOURS, clouds='cumulus', cache_dir=cache_dir,
                       quality='film', shadows=False, azimuth=RR.sun_azimuth_option(sun_xy))
        sky.bake(frame_start=1, frame_end=1, log=lambda *a, **k: None)
        png = os.path.join(out_dir, f'{name}_{view}.png')
        sc.render.filepath = png
        bpy.ops.render.render(write_still=True)
        recs[view] = dict(camera=list(pos), target=list(tgt), lens_mm=cam.data.lens, png=png)
    return recs

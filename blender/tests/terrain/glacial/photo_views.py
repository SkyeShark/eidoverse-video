"""Photo-matched views: each reference photograph's camera on the real elevation data, and the same view transferred
to a generated terrain, written as a render job for render_views.py (plain Python, numpy).

    python blender/tests/terrain/glacial/photo_views.py --gen <out/glacial/gen/TAG.npz> [--gen ...]
           [--photos lb_floor,lb_rail] [--job out/glacial/photo_views/job.json]

The photographs and their cameras are out/glacial/photos/sources.json (GPS, lens from the focal length and sensor
width, the view's pitch and its heading: absolute, or relative to the valley's up-valley direction there).

On the reference, the camera stands at the photo's GPS position, 1.7 m above the ground (the DEM, or its context
beyond the tile). On a generated terrain it stands at the same place in the valley's own frame: the same fraction
along the trunk (the judge's trunk path, from its head to its outlet; beyond the outlet, the same distance past it),
the same side, at the same height above the trunk floor (walking out along the normal until the ground reaches it),
looking the same way relative to up-valley, with the same lens and pitch. So a view from 150 m up the east wall
looking up-valley is the same view of both places, whatever their orientation or trough width.
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(TN, 'core'))
import plain_import  # noqa: E402

plain_import.install()
sys.path.insert(0, TN)
sys.path.insert(0, os.path.join(TN, 'reference'))

import numpy as np  # noqa: E402

import landform_refs as LR  # noqa: E402
from judge import family as FA  # noqa: E402
from judge import refs  # noqa: E402

PHOTOS = os.path.join(TN, 'out', 'glacial', 'photos')
OUT = os.path.join(TN, 'out', 'glacial', 'photo_views')
EYE = 1.7


class Field:
    """A heightfield in the terrain frame (row 0 = south; x east, y north, metres) with an optional wider context
    centred on the same point: bilinear height anywhere either covers."""

    def __init__(self, h, cell, x0, y0, context=None):
        self.h, self.cell, self.x0, self.y0 = np.asarray(h, np.float64), float(cell), float(x0), float(y0)
        self.context = context

    def height(self, x, y):
        n0, n1 = self.h.shape
        i = (x - self.x0) / self.cell - 0.5
        j = (y - self.y0) / self.cell - 0.5
        if (0 <= i <= n1 - 1 and 0 <= j <= n0 - 1) or self.context is None:
            return float(FA.sample(self.h, np.array([i]), np.array([j]))[0])
        return self.context.height(x, y)

    def xy(self, col, row):
        return self.x0 + (col + 0.5) * self.cell, self.y0 + (row + 0.5) * self.cell


def ref_field(name):
    r = refs.load(name)
    n = r.h.shape[0]
    ctx = refs.load_context(name)
    c = None
    if ctx is not None:
        hc, pc, _ = ctx
        c = Field(hc, pc, -hc.shape[1] * pc / 2.0, -hc.shape[0] * pc / 2.0)
    return Field(r.h, r.pixel, -n * r.pixel / 2.0, -n * r.pixel / 2.0, c), r


def gen_field(path):
    d = np.load(path)
    h = np.asarray(d['h'], np.float64)
    cell = float(d['cell'])
    n = h.shape[0]
    c = None
    if 'context_h' in d.files:
        hc = np.asarray(d['context_h'], np.float64)
        pc = float(d['context_cell'])
        c = Field(hc, pc, -hc.shape[1] * pc / 2.0, -hc.shape[0] * pc / 2.0)
    return Field(h, cell, -n * cell / 2.0, -n * cell / 2.0, c)


def trunk(f):
    """The trunk's path in world metres, head first: (P (k, 2), s (k,) distance from the head, floor (k,))."""
    area, recv, _ = FA.drainage(f.h, f.cell)
    path = FA.trunk(f.h, f.cell, area, recv)
    p = np.array([f.xy(c, r) for c, r in path], np.float64)
    hs = FA.blur(f.h, 1.0)
    floor = FA.sample(hs, np.array([c for c, _ in path], float), np.array([r for _, r in path], float))
    s = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(p, axis=0).T))])
    return p, s, floor


def frame_at(P, s, at, half=150.0):
    """(point, unit up-valley direction, unit right normal looking up-valley) at distance `at` from the head; beyond
    the outlet the path is extended straight."""
    L = s[-1]
    k = int(np.clip(np.searchsorted(s, min(at, L)), 0, len(s) - 1))
    a = P[int(np.clip(np.searchsorted(s, min(at, L) - half), 0, len(s) - 1))]
    b = P[int(np.clip(np.searchsorted(s, min(at, L) + half), 0, len(s) - 1))]
    up = a - b
    up = up / max(np.hypot(*up), 1e-9)
    pt = P[k] + (max(at - L, 0.0)) * (-up)
    right = np.array([up[1], -up[0]])
    return pt, up, right


def heading_of(v):
    return math.degrees(math.atan2(v[0], v[1])) % 360.0


def ref_camera(ph, f, P, s, floor, meta):
    x, y = (float(v) for v in LR.latlon_to_xy(meta, ph['lat'], ph['lon']))
    ground = f.height(x, y)
    cam_h = float(ph.get('height_m', EYE))
    d = np.hypot(P[:, 0] - x, P[:, 1] - y)
    k = int(np.argmin(d))
    pt, up, right = frame_at(P, s, s[k])
    off = np.array([x, y]) - pt
    along = float(s[k] - np.dot(off, up))
    side = 1.0 if np.dot(off, right) >= 0 else -1.0
    if ph.get('heading_deg') is not None:
        hd = float(ph['heading_deg'])
    else:
        hd = (heading_of(up) + float(ph.get('rel_heading_deg', 0.0))) % 360.0
    rel = (hd - heading_of(up) + 180.0) % 360.0 - 180.0
    floor_k = float(np.interp(min(max(along, 0.0), s[-1]), s, floor))
    mid = frame_at(P, s, 0.5 * s[-1])[0]
    to_mid = heading_of(mid - np.array([x, y]))
    return dict(x=float(x), y=float(y), z=float(ground + cam_h), heading_deg=hd, pitch_deg=float(ph['pitch_deg']),
                lens_mm=float(ph['lens_mm_36'])), dict(frac=along / s[-1], side=side,
                                                       across_m=float(abs(np.dot(off, right))),
                                                       ground_above_floor_m=float(ground - floor_k), height_m=cam_h,
                                                       rel_heading_deg=rel, past_outlet_m=float(max(along - s[-1], 0.0)),
                                                       rel_to_mid_deg=(hd - to_mid + 180.0) % 360.0 - 180.0)


def clear_view(f, q, z, heading, pitch, lens, near_m=800.0):
    """True when the ground within near_m ahead stays out of the frame's upper three quarters (the camera is not
    looking into a slope in front of it)."""
    vfov = 2.0 * math.degrees(math.atan(18.0 / lens * 9.0 / 16.0))
    a = math.radians(heading)
    for d in np.arange(20.0, near_m, 0.5 * f.cell + 10.0):
        g = f.height(q[0] + d * math.sin(a), q[1] + d * math.cos(a))
        if math.degrees(math.atan2(g - z, d)) > pitch - 0.25 * vfov:
            return False
    return True


def transfer(vf, f, P, s, floor, cam):
    """The reference view's valley-frame coordinates on another terrain's trunk (cam: the reference camera, for its
    pitch and lens)."""
    L = s[-1]
    at = vf['frac'] * L if vf['past_outlet_m'] <= 0 else L + vf['past_outlet_m']
    pt, up, right = frame_at(P, s, at)
    fl = float(np.interp(min(max(at, 0.0), L), s, floor))
    want = vf['ground_above_floor_m']
    far = vf['past_outlet_m'] > 0 or vf['across_m'] > 2000.0
    # walk out along the normal on the same side until the ground stands as high above the floor as the reference
    # camera's ground (a floor view stays where the reference camera was)
    best = None
    for a in np.arange(0.0, 6000.0, 0.25 * f.cell):
        q = pt + vf['side'] * a * right
        g = f.height(q[0], q[1])
        if g - fl >= want:
            best = (q, g, a)
            break
    if best is None or want < 20.0:
        across = vf['across_m']
        if want < 20.0:
            # a floor view stays on the floor's middle half: walking out to the reference camera's distance from its
            # trunk put the camera against a wall where the floor is narrower, and the wall filled the frame
            edge = next((a for a in np.arange(0.0, 3000.0, 0.25 * f.cell)
                         if f.height(*(pt + vf['side'] * a * right)) - fl > 10.0), 3000.0)
            across = min(across, 0.5 * edge)
        q = pt + vf['side'] * across * right
        best = (q, f.height(q[0], q[1]), across)
    q, g, a0 = best
    z = g + vf['height_m']
    if want > 20.0 and vf['past_outlet_m'] > 0:            # a mountain viewpoint beyond the tile: the same height
        z = max(z, fl + want + vf['height_m'])
    if far:                                              # look at the valley the way the reference camera does
        mid = frame_at(P, s, 0.5 * L)[0]
        hd = (heading_of(mid - q) + vf['rel_to_mid_deg']) % 360.0
    elif vf.get('aim_up_m'):
        # a view along the trough aims at its floor this far up the trunk (the local direction looked into the
        # next bend's wall)
        hd = heading_of(frame_at(P, s, max(at - float(vf['aim_up_m']), 0.0))[0] - q)
    else:
        hd = (heading_of(up) + vf['rel_heading_deg']) % 360.0
    if want > 20.0 and not clear_view(f, q, z, hd, cam['pitch_deg'], cam['lens_mm']):
        # an elevated view looking into the slope in front: step along the normal (inward first) to the nearest
        # stance with a clear view
        for step in np.arange(20.0, 600.0, 20.0):
            for sgn in (-1.0, 1.0):
                q2 = pt + vf['side'] * (a0 + sgn * step) * right
                z2 = f.height(q2[0], q2[1]) + vf['height_m']
                if clear_view(f, q2, z2, hd, cam['pitch_deg'], cam['lens_mm']):
                    return dict(x=float(q2[0]), y=float(q2[1]), z=float(z2), heading_deg=hd, moved_m=float(sgn * step))
    return dict(x=float(q[0]), y=float(q[1]), z=float(z), heading_deg=hd)


def horizon(f, cam, half_deg=70.0, step_deg=0.25, r_eff=6371000.0 * 7.0 / 6.0):
    """The skyline from a camera: (azimuths, elevation angles in degrees) of the highest terrain along each ray out
    to 40 km, the Earth's curvature (with refraction) dropping the far ground. The cameras' headings and pitches in
    sources.json were set on it: a photo's landmarks (the far valley notch, a wall's rim) at their azimuths."""
    az = np.arange(cam['heading_deg'] - half_deg, cam['heading_deg'] + half_deg, step_deg)
    d = np.concatenate([np.arange(30.0, 2000.0, 8.0), np.arange(2000.0, 40000.0, 30.0)])
    el = np.full(az.size, -90.0)
    for k, a in enumerate(az):
        ar = math.radians(a)
        hs = np.array([f.height(cam['x'] + r * math.sin(ar), cam['y'] + r * math.cos(ar)) for r in d])
        el[k] = float(np.degrees(np.arctan2(hs - d * d / (2.0 * r_eff) - cam['z'], d)).max())
    return az, el


# views along the trough, placed by their valley frame (photo_views' transfer) on every terrain: (key, the photograph
# shown beside them, valley frame, lens and pitch). floor_axis: on the trunk's floor 62 % of the way down the valley,
# looking at the floor 3 km up it (Lauterbrunnen from the meadows south of the village, photograph 12); aerial_axis:
# 1.5 km over the floor near the outlet, looking at the floor 3.5 km up the trough (photograph 14 looks down into the
# cleft from high on its side)
AXIS_VIEWS = [
    ('floor_axis', 'raw/lauterbrunnen_12.jpg',
     dict(frac=0.62, side=1.0, across_m=0.0, ground_above_floor_m=0.0, height_m=EYE, rel_heading_deg=0.0,
          past_outlet_m=0.0, rel_to_mid_deg=0.0, aim_up_m=3000.0), dict(pitch_deg=4.0, lens_mm=30.0)),
    ('aerial_axis', 'raw/lauterbrunnen_14.jpg',
     dict(frac=0.97, side=1.0, across_m=0.0, ground_above_floor_m=0.0, height_m=1500.0, rel_heading_deg=0.0,
          past_outlet_m=0.0, rel_to_mid_deg=0.0, aim_up_m=3500.0), dict(pitch_deg=-18.0, lens_mm=35.0)),
]


def textured_view(name, cam, field, recipe, params, seed, photo, half=4000.0):
    """A render_textured.py view of a camera: x, y and its height over the field's ground there (agl); hero levels
    (focus) when it stands near the ground inside the main tile."""
    agl = float(cam['z'] - field.height(cam['x'], cam['y']))
    inside = abs(cam['x']) < half - 300.0 and abs(cam['y']) < half - 300.0
    return dict(name=name, recipe=recipe, params=params, seed=seed, photo=photo, focus=bool(inside and agl < 30.0),
                camera=dict(x=float(cam['x']), y=float(cam['y']), agl=agl, heading_deg=float(cam['heading_deg']),
                            pitch_deg=float(cam['pitch_deg']), lens_mm=float(cam['lens_mm'])))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gen', action='append', default=[])
    ap.add_argument('--photos')
    ap.add_argument('--job', default=os.path.join(OUT, 'job.json'))
    ap.add_argument('--tag', default='v')
    ap.add_argument('--textured', help='also write a render_textured.py job here: the same cameras on make_terrain '
                                       "(the generated npz's recipe and seed from its gen.py record; the reference as "
                                       'real_place), with palettes and rocks')
    ap.add_argument('--out', default=OUT, help="the render jobs' out_dir")
    ap.add_argument('--axis', action='store_true', help='also the views along the trough (AXIS_VIEWS): the same '
                                                        'place in the valley frame on the reference and every --gen')
    a = ap.parse_args()
    meta = json.load(open(os.path.join(PHOTOS, 'sources.json'), encoding='utf-8'))['photos']
    keys = a.photos.split(',') if a.photos else list(meta)
    views, tex = [], []
    cache = {}
    for key in keys:
        ph = meta[key]
        if ph['reference'] not in cache:
            f, r = ref_field(ph['reference'])
            cache[ph['reference']] = (f, r, trunk(f))
        f, r, (P, s, floor) = cache[ph['reference']]
        cam, vf = ref_camera(ph, f, P, s, floor, r.meta)
        views.append(dict(name=f'{a.tag}_{key}_reference', source=dict(reference=ph['reference']), camera=cam,
                          photo=ph['file'], valley_frame=vf))
        tex.append(textured_view(f'{a.tag}_{key}_reference', cam, f, 'real_place', {'dem': ph['reference']}, 1,
                                 ph['file']))
        for g in a.gen:
            gf = gen_field(g)
            Pg, sg, flg = trunk(gf)
            c2 = dict(cam, **transfer(vf, gf, Pg, sg, flg, cam))
            label = os.path.splitext(os.path.basename(g))[0]
            views.append(dict(name=f'{a.tag}_{key}_{label}', source=dict(npz=os.path.abspath(g)), camera=c2,
                              photo=ph['file'], valley_frame=vf))
            rp = os.path.splitext(os.path.abspath(g))[0] + '_record.json'
            item = json.load(open(rp, encoding='utf-8'))['item'] if os.path.exists(rp) else {}
            tex.append(textured_view(f'{a.tag}_{key}_{label}', c2, gf, item.get('recipe', 'alpine_valley'),
                                     item.get('params') or {}, int(item.get('seed', 1)), ph['file']))
        print(f"{key}: reference camera ({cam['x']:.0f}, {cam['y']:.0f}) z {cam['z']:.0f} heading "
              f"{cam['heading_deg']:.0f} lens {cam['lens_mm']:.1f}; valley frame {vf}", flush=True)
    if a.axis:
        # views placed in the valley frame on every terrain alike (the reference included): the photographs beside
        # them show the same kind of view of the real place
        ref_name = meta[keys[0]]['reference']
        f, r, (P, s, floor) = cache[ref_name]
        for key, ph_file, vf, look in AXIS_VIEWS:
            for label, fld, src, tex_args in [('reference', f, dict(reference=ref_name),
                                               ('real_place', {'dem': ref_name}, 1))] + \
                    [(os.path.splitext(os.path.basename(g))[0], gen_field(g), dict(npz=os.path.abspath(g)), None)
                     for g in a.gen]:
                Pg, sg, flg = (P, s, floor) if label == 'reference' else trunk(fld)
                c2 = dict(look, **transfer(vf, fld, Pg, sg, flg, look))
                views.append(dict(name=f'{a.tag}_{key}_{label}', source=src, camera=c2, photo=ph_file,
                                  valley_frame=vf))
                if tex_args is None:
                    g = src['npz']
                    rp = os.path.splitext(g)[0] + '_record.json'
                    item = json.load(open(rp, encoding='utf-8'))['item'] if os.path.exists(rp) else {}
                    tex_args = (item.get('recipe', 'alpine_valley'), item.get('params') or {}, int(item.get('seed', 1)))
                tex.append(textured_view(f'{a.tag}_{key}_{label}', c2, fld, tex_args[0], tex_args[1], tex_args[2],
                                         ph_file))
    os.makedirs(os.path.dirname(os.path.abspath(a.job)), exist_ok=True)
    with open(a.job, 'w', encoding='utf-8') as fh:
        json.dump(dict(out_dir=a.out, views=views), fh, indent=1)
    print(a.job)
    if a.textured:
        with open(a.textured, 'w', encoding='utf-8') as fh:
            json.dump(dict(out_dir=a.out, views=tex), fh, indent=1)
        print(a.textured)


if __name__ == '__main__':
    main()

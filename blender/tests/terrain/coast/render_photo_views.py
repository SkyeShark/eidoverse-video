"""Photo-matched views of sea_cliffs (Blender, a GPU slot): each photograph in out/coast/photos/ (sources.json) is
matched by a camera on the generated coast at the photo's height above the sea, its direction relative to the
coastline and its lens (EXIF focal length, as a 35 mm equivalent), under make_sky daylight with the sun on the side
the photo was lit from. Clay and the chalk_coast palette, 960 x 540, 16 samples.

    python blender/tests/terrain/coast/slot.py blender/tests/terrain/coast/render_photo_views.py -- \
        --rock chalk --seed 1 --tag p1 [--views ss_seaford_head,ss_beach_birling_gap] [--variant '{...}']

The photographed places are not the generated ones, so a view is matched in kind (the coast frame below), not in
position. The coast frame of the main level: n the seaward normal (the recipe's azimuth_deg), t along the shore to
the right when facing the sea (chalk: t points west-north-west, as the Seven Sisters run; layered: north-north-east,
as Moher does). An anchor is a shore cell (land beside the sea, at the cliff foot) picked by its along-shore
coordinate; positions are anchor + along t + out n, heights absolute, above the ground there, or relative to the
anchor's cliff top. The hero levels' focus covers the near subject, so the faces seen are resolved.
Writes out/coast/views/<tag>_<view>_clay.png and _tex.png and <tag>_<rock>_views.json (cameras, anchors, seconds).
"""
import json
import math
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(TN, 'core'))
import plain_import  # noqa: E402

plain_import.install()
sys.path.insert(0, os.path.join(TN, 'reference'))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

import render_references as RR  # noqa: E402
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.terrain import api as A  # noqa: E402
from variants import recipe_for  # noqa: E402

OUT = os.path.normpath(os.path.join(TN, 'out', 'coast', 'views'))
SIZE = 6000.0

# The views, one per photograph (sources.json holds each photo's author, licence and camera). along / out in metres
# from the anchor; z: ('abs', m) above sea level, ('ground', m) above the ground there, ('top', m) relative to the
# anchor's cliff top. lens: the photo's 35 mm equivalent focal length for its horizontal field of view.
VIEWS = {
    # Seaford Head, ~70 m up, across Cuckmere Haven: the row of sisters 2.5-5 km off, faces seen 70 degrees off their
    # normal (IXUS 285 at 16.2 mm = 91 mm equivalent, 22 degrees)
    'ss_seaford_head': dict(rock='chalk', anchor=('along', 0.0), cam=(2900.0, 900.0, ('abs', 72.0)),
                            tgt=(-300.0, -60.0, ('top', -30.0)), lens=91.0, sun=190.0,
                            focus=[(-1300.0, -100.0), (900.0, -100.0)]),
    # Along-coast views (mode 'along', along_view): the photographer stood across a bay from the faces he shot (from
    # on top of a straight cliff, or at its foot, the faces ahead are seen edge-on and hidden), so the camera's
    # anchor is searched along the coast: on the turf `back` metres behind the top edge ('top') or `out` metres out
    # on the beach ('beach'), looking `sign` x t along the coast at the face `dist` metres ahead, with a clear sight
    # line, the face seen as frontally as the coast allows, near `prefer` (with `cos`: seen at that obliquity, the
    # cosine of the sight line from the face's normal: a photograph along a straight run of cliffs).
    # on a sister's top just back from the edge, along the cliffs east-south-east toward Belle Tout (no EXIF: ~36 mm);
    # 4 m back: the photograph has the near edge and its face in the left of the frame (10 m back hid them); the face
    # 600 m ahead seen 70 degrees off its normal (the most frontal view stood across a bay from a headland)
    'ss_clifftop_east': dict(rock='chalk', mode='along', sign=-1, where='top', back=4.0, dist=600.0, cos=0.3,
                             prefer=-200.0, min_top=40.0, aim=0.3, lens=36.0, sun=200.0),
    # the beach at Birling Gap, looking west-north-west along the foot of the cliffs (S200EXR 9.8 mm = 42 mm): on the
    # shingle 14 m in from the water's edge, the camera 4 m above it (the photograph looks down the beach from the
    # steps); out=+25 m stood it in the sea before the coast had a beach
    'ss_beach_birling_gap': dict(rock='chalk', mode='along', sign=1, where='beach', out=-14.0, eye=4.0, dist=500.0,
                                 prefer=300.0, min_top=20.0, aim=0.35, lens=42.0, sun=200.0),
    # at a sister's edge looking west-north-west along the coast and down (5D Mk III at 53 mm)
    # (on a sister's summit, `high`: the next sister along the cliff top hid a face 500 m ahead from a lower top; the
    # face 350 m ahead, a sight line clear by 0.3 m: looking down along the coast from the edge found no anchor at 1 m)
    'ss_clifftop_west_high': dict(rock='chalk', mode='along', sign=1, where='top', back=2.0, dist=350.0, cos=0.35,
                                  margin=0.3, high=True, prefer=200.0, min_top=35.0, aim=0.25, lens=53.0, sun=190.0),
    # Moher's cliff top looking south-south-west along the coves and headlands (RX10 IV, 34 mm equivalent)
    'moher_clifftop_south': dict(rock='layered', mode='along', sign=-1, where='top', back=12.0, dist=900.0,
                                 prefer=300.0, min_top=80.0, aim=0.6, lens=34.0, sun=240.0),
    # from the cliff top ~1 km south of a headland with a sea stack in front (600D at 55 mm = 88 mm)
    'moher_stack_obriens': dict(rock='layered', mode='stack', sign=1, where='top', back=12.0, dist=1000.0,
                                min_top=60.0, aim=0.5, lens=88.0, sun=265.0),
    # from a boat 700 m out, 1.5 m above the water, facing the wall (iPhone tele 77 mm, a 16:9 crop of its
    # panorama spans about 43 degrees)
    'moher_from_sea': dict(rock='layered', anchor=('summit', 0.0), cam=(0.0, 700.0, ('abs', 1.5)),
                           tgt=(0.0, 0.0, ('top', -0.65)), lens=46.0, sun=210.0,
                           focus=[(-700.0, -50.0), (700.0, 50.0)]),
    # Hag's Head: a headland's top at the south end looking north-north-east along 4-5 km of cliffs (450D, 29 mm)
    'moher_from_hags_head': dict(rock='layered', mode='along', sign=1, where='top', back=8.0, dist=2000.0,
                                 prefer=-1200.0, min_top=60.0, aim=0.6, lens=29.0, sun=250.0),
}
# A position (along, out, z[, 'top']): from the anchor's shore cell (the cliff foot), or with 'top' from its cliff top
# edge, so a camera "10 m back from the edge" stands on the turf, not on the face. The textured shots are exposed a
# stop under the clay's (the rig's exposure is set for albedo 0.18 clay; chalk at 0.75 clipped to flat white), and
# the sea's material is roughened to 0.2 as the reference rig's water is ("a breeze on it: no mirror doubling the
# terrain"; build/water.py's 0.06 doubled the cliffs).
TEX_EXPOSURE = RR.EXPOSURE - 1.0
SEA_ROUGHNESS = 0.2
AZIMUTH = {'chalk': 200.0, 'layered': 300.0}


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    return dict(rock=opt('--rock', 'chalk'), seed=int(opt('--seed', '1')), tag=opt('--tag', 'p'),
                views=[v for v in (opt('--views') or '').split(',') if v], variant=json.loads(opt('--variant', '{}')),
                params=json.loads(opt('--params', '{}')))


def compass(deg):
    r = math.radians(deg)
    return np.array([math.sin(r), math.cos(r)])


class CoastFrame:
    """The main level's shore cells in the coast frame (module doc)."""

    def __init__(self, t, azimuth_deg):
        lv = t.main
        f = t.fields('main')
        h = np.asarray(f['h'], np.float64)
        self.t = t
        self.cell = float(lv.cell)
        sea = h <= 0.3
        nb = np.zeros_like(sea)
        for dj in (-1, 0, 1):
            for di in (-1, 0, 1):
                nb |= np.roll(np.roll(sea, dj, 0), di, 1)
        shore = (~sea) & nb
        shore[0, :] = shore[-1, :] = shore[:, 0] = shore[:, -1] = False
        # the mainland: the largest land body (a stack is land the retreat cut off)
        from eidoblend.terrain.core.metrics import label
        lab, n = label(~sea)
        counts = np.bincount(lab.ravel(), minlength=n + 1)
        counts[0] = 0
        self.main_label = int(np.argmax(counts))
        X, Y = lv.xy()
        self.centre = np.array([lv.x0 + lv.side / 2, lv.y0 + lv.side / 2])
        self.n0 = compass(azimuth_deg)
        self.t0 = np.array([self.n0[1], -self.n0[0]])
        jj, ii = np.nonzero(shore)
        P = np.stack([X[jj, ii], Y[jj, ii]], 1)
        d = P - self.centre
        self.P, self.lab = P, lab[jj, ii]
        self.along, self.out = d @ self.t0, d @ self.n0
        self.lab_full, self.h, self.sea, self.X, self.Y = lab, h, sea, X, Y

    def shore_at(self, a, mainland=True):
        m = np.abs(self.along - a) < 1.5 * self.cell
        if mainland:
            m &= self.lab == self.main_label
        if not m.any():
            k = int(np.argmin(np.abs(self.along - a) + (0 if not mainland else 1e6 * (self.lab != self.main_label))))
            return self.P[k]
        idx = np.nonzero(m)[0]
        return self.P[idx[np.argsort(self.out[idx])[len(idx) // 2]]]

    def local_frame(self, p):
        """(t, n) from the mainland shore cells within 300 m (their principal direction), oriented as t0, n0."""
        m = (np.hypot(*(self.P - p).T) < 300.0) & (self.lab == self.main_label)
        if m.sum() < 5:
            return self.t0, self.n0
        Q = self.P[m] - self.P[m].mean(0)
        t = np.linalg.svd(Q, full_matrices=False)[2][0]
        if t @ self.t0 < 0:
            t = -t
        n = np.array([-t[1], t[0]])
        if n @ self.n0 < 0:
            n = -n
        return t, n

    def top_of(self, p, n):
        """The cliff top inland of shore point p: the first point (2 m steps) past a 10 m climb where the slope over
        4 m falls under 25 degrees, and its height."""
        s = np.arange(0.0, 160.0, 2.0)
        pts = p[None, :] - s[:, None] * n[None, :]
        z = np.asarray(self.t.height_at(pts[:, 0], pts[:, 1]), np.float64)
        z0 = z[0]
        for k in range(2, len(s)):
            if z[k] - z0 > 10.0 and (z[k] - z[k - 2]) / 4.0 < math.tan(math.radians(25.0)):
                return pts[k], float(z[k])
        k = int(np.argmax(z))
        return pts[k], float(z[k])

    def anchor(self, kind, a):
        if kind == 'along':
            p = self.shore_at(a)
        elif kind in ('summit', 'headland'):
            cands = [a + d for d in np.arange(-500.0, 501.0, 25.0)]
            best, bv = None, -1e9
            for c in cands:
                q = self.shore_at(c)
                if kind == 'summit':
                    t, n = self.local_frame(q)
                    v = self.top_of(q, n)[1]
                else:
                    v = (q - self.centre) @ self.n0
                if v > bv:
                    best, bv = q, v
            p = best
        elif kind == 'stack':
            p = self.stack()
        else:
            raise ValueError(kind)
        t, n = self.local_frame(p) if kind != 'stack' else (self.t0, self.n0)
        if kind == 'stack':
            top_p, top_z = p, float(self.t.height_at(np.array([p[0]]), np.array([p[1]]))[0])
        else:
            top_p, top_z = self.top_of(p, n)
        return dict(p=p, t=t, n=n, top=top_p, top_z=top_z)

    def stack(self):
        """The highest land body cut off from the mainland (at least 20 m high), nearest the centre."""
        best, bd = None, 1e18
        for k in np.unique(self.lab_full):
            if k in (0, self.main_label):
                continue
            m = self.lab_full == k
            if m.sum() > 4000 or self.h[m].max() < 20.0:
                continue
            j = np.argmax(np.where(m, self.h, -1e9))
            q = np.array([self.X.ravel()[j], self.Y.ravel()[j]])
            d = np.hypot(*(q - self.centre))
            if d < bd:
                best, bd = q, d
        if best is None:
            raise RuntimeError('no sea stack on the main level')
        return best


def _ground(t, xy):
    return float(t.height_at(np.array([xy[0]]), np.array([xy[1]]))[0])


def _clearance(t, eye, tgt, k=240, start_m=1.5):
    """The least height of the sight line from eye to tgt over the ground, sampled from start_m out to 95 % of the
    way (denser near the eye, where a rise of the turf ahead hides everything)."""
    e, g = np.asarray(eye, np.float64), np.asarray(tgt, np.float64)
    d = float(np.hypot(*(g[:2] - e[:2])))
    s0 = min(start_m / max(d, start_m), 0.5)
    s = s0 + (0.95 - s0) * np.linspace(0.0, 1.0, k) ** 1.6
    P = e[None, :] + (g - e)[None, :] * s[:, None]
    return float((P[:, 2] - np.asarray(t.height_at(P[:, 0], P[:, 1]), np.float64)).min())


def _clear(t, eye, tgt, margin=1.0):
    """The sight line clears the ground by `margin` from 1.5 m out (a hero level resolves the turf a metre or so
    higher or lower than the main level the views are planned on: checked from 8 m out with 0.3 m, a 4 m rise
    10 m ahead of a clifftop camera filled the whole shot with grass)."""
    return _clearance(t, eye, tgt) >= margin


def along_view(fr, spec, t):
    """(cam, tgt, focus, info) for an along-coast view (VIEWS' doc): every 50 m of the main tile's coast is tried
    as the anchor; a candidate needs its camera on high turf (or the beach), the face ahead in clear sight and the
    whole shot's focus inside the main tile; the best sees the face most frontally, near `prefer`."""
    sign = float(spec['sign'])
    lim = SIZE / 2 - 150.0
    best = None
    if spec['mode'] == 'stack':
        S = fr.stack()
        a_stack = float((S - fr.centre) @ fr.t0)
        s_top = _ground(t, S)
        # from either side along the coast (the stack nearest the centre may lie toward the tile's edge)
        cands = np.concatenate([np.arange(a_stack - sg * (spec['dist'] + 400.0), a_stack - sg * (spec['dist'] - 400.0),
                                          sg * 50.0) for sg in (sign, -sign)])
    else:
        cands = np.arange(-lim, lim, 50.0)
    for a in cands:
        q = fr.shore_at(a)
        tq, nq = fr.local_frame(q)
        if spec['where'] == 'top':
            top_p, top_z = fr.top_of(q, nq)
            if top_z < spec['min_top']:
                continue
            cxy = top_p - spec['back'] * nq
            g = _ground(t, cxy)
            if g < 0.8 * top_z:
                continue
            cz = g + 1.7
        else:
            cxy = q + spec['out'] * nq
            cz = max(_ground(t, cxy), 0.0) + float(spec.get('eye', 1.7))
        if spec['mode'] == 'stack':
            sxy, sz = S, spec['aim'] * s_top
            ns = (cxy - S) / max(float(np.hypot(*(cxy - S))), 1e-6)
        else:
            s = fr.shore_at(a + sign * spec['dist'])
            ts, ns = fr.local_frame(s)
            s_top = fr.top_of(s, ns)[1]
            if s_top < 0.5 * spec['min_top']:
                continue
            sxy = s - 0.12 * s_top * ns                    # the face at mid-height, inland of its foot
            sz = spec['aim'] * s_top
        if max(abs(cxy[0]), abs(cxy[1]), abs(sxy[0]), abs(sxy[1])) > lim:
            continue
        if not _clear(t, (cxy[0], cxy[1], cz), (sxy[0], sxy[1], sz), margin=float(spec.get('margin', 1.0))):
            continue
        d = cxy - sxy
        cosv = float(d @ ns / max(float(np.hypot(*d)), 1e-6))
        if spec['mode'] != 'stack' and cosv < 0.1:
            continue
        front = -abs(cosv - spec['cos']) if 'cos' in spec else cosv
        score = front - (abs(a - spec['prefer']) / 3000.0 if 'prefer' in spec else 0.0)
        if spec.get('high'):
            score += cz / 100.0                          # the highest top along the coast
        if best is None or score > best[0]:
            best = (score, a, cxy, cz, sxy, sz, cosv, q)
    if best is None:
        raise RuntimeError('no anchor along the coast sees the faces ahead')
    score, a, cxy, cz, sxy, sz, cosv, q = best
    mid = 0.5 * (cxy + sxy)
    focus = [(float(cxy[0]), float(cxy[1])), (float(sxy[0]), float(sxy[1])), (float(mid[0]), float(mid[1]))]
    info = dict(p=q, t=fr.t0, n=fr.n0, top_z=float(sz / max(spec['aim'], 1e-6)) if spec['aim'] else float(sz),
                along=float(a), face_cos=round(cosv, 3))
    return (float(cxy[0]), float(cxy[1]), float(cz)), (float(sxy[0]), float(sxy[1]), float(sz)), focus, info


def resolve_view(fr, spec, t):
    if spec.get('mode') in ('along', 'stack'):
        return along_view(fr, spec, t)
    an = fr.anchor(*spec['anchor'])
    p, tv, nv = an['p'], an['t'], an['n']

    def at(along, out, z, base='foot'):
        xy = (an['top'] if base == 'top' else p) + along * tv + out * nv
        kind, v = z
        if kind == 'abs':
            zz = v
        elif kind == 'ground':
            zz = max(float(t.height_at(np.array([xy[0]]), np.array([xy[1]]))[0]), 0.0) + v
        elif kind == 'top':                      # metres from the cliff top, or a share of its height (|v| < 1)
            zz = an['top_z'] * (1.0 + v) if abs(v) < 1.0 else an['top_z'] + v
        elif kind == 'stack':
            zz = an['top_z'] * v
        else:
            raise ValueError(kind)
        return (float(xy[0]), float(xy[1]), float(zz))
    cam = at(*spec['cam'])
    tgt = at(*spec['tgt'])
    focus = [tuple(float(c) for c in (p + a * tv + o * nv)) for a, o in spec['focus']]
    return cam, tgt, focus, an


def render(sc, cam, path, sky_dir, sun_deg):
    os.makedirs(sky_dir, exist_ok=True)
    sky = make_sky(sc, camera=cam, world='earth', hours=RR.SUN_ELEV_HOURS, clouds='cumulus', cache_dir=sky_dir,
                   quality='film', shadows=False, azimuth=RR.sun_azimuth_option(tuple(compass(sun_deg))))
    sky.bake(frame_start=1, frame_end=1, log=lambda *a, **k: None)
    # a small warm-up render first: once a new terrain material was drawn before its shaders had compiled, and the
    # ground was missing from the shot (its rocks floating where the cliff stood)
    pct = sc.render.resolution_percentage
    sc.render.resolution_percentage = 10
    bpy.ops.render.render(write_still=False)
    sc.render.resolution_percentage = pct
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def main():
    a = args()
    os.makedirs(OUT, exist_ok=True)
    R = recipe_for(a['variant'])
    params = dict(a['params'], rock=a['rock'])
    names = a['views'] or [k for k, v in VIEWS.items() if v['rock'] == a['rock']]
    rec = dict(args=a, views={})
    t0 = time.time()
    base = A.generate(R, size=SIZE, seed=a['seed'], params=params, quality='film', cache=not a['variant'].get('rocks'))
    fr = CoastFrame(base, AZIMUTH[a['rock']])
    sky_root = tempfile.mkdtemp(prefix='coast_sky_')
    for name in names:
        spec = VIEWS[name]
        try:
            cam_p, tgt_p, focus, an = resolve_view(fr, spec, base)
        except Exception as e:                                          # noqa: BLE001 - recorded, the others go on
            rec['views'][name] = dict(error=f'{type(e).__name__}: {e}')
            print(f'[coast.views] {name}: not rendered: {e}', flush=True)
            continue
        tv = time.time()
        RR.new_scene((960, 540), 16, RR.EXPOSURE)
        sc = bpy.context.scene
        cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
        sc.collection.objects.link(cam)
        sc.camera = cam
        cam.data.clip_start, cam.data.clip_end = 0.1, 80000.0
        # (palette 'auto' resolves from the recipe's static defaults, chalk_coast: Moher's comes from the recipe's
        # defaults_for, which api.py applies only to real places, so it is passed here)
        from eidoblend.terrain.recipes import sea_cliffs as SCR
        pal = SCR.layered_palette() if a['rock'] == 'layered' else 'auto'
        tt = A.make_terrain(R, size=SIZE, seed=a['seed'], params=params, focus=focus, palette=pal, dress=True,
                            quality='film', cache=not a['variant'].get('rocks'), name='terrain')
        # the camera's height again on the built terrain (the hero levels refine the ground under it)
        g = float(tt.height_at(np.array([cam_p[0]]), np.array([cam_p[1]]))[0])
        if spec.get('mode') in ('along', 'stack'):
            cam_p = (cam_p[0], cam_p[1], (max(g, 0.0) if spec['where'] == 'beach' else g) + float(spec.get('eye', 1.7)))
        elif spec['cam'][2][0] == 'ground':
            cam_p = (cam_p[0], cam_p[1], max(g, 0.0) + spec['cam'][2][1])
        # the sight line on the built terrain (its hero levels): recorded, so a shot the turf hides is caught
        built_clear = _clearance(tt, cam_p, tgt_p)
        RR.place_camera(cam, cam_p, tgt_p)
        cam.data.lens = spec['lens']
        stem = os.path.join(OUT, f"{a['tag']}_{name}")
        for wobj in [tt.water.get('sea')] + list(tt.water.get('lakes') or []):
            if wobj is not None and wobj.active_material is not None:
                b = wobj.active_material.node_tree.nodes.get('Principled BSDF')
                if b is not None:
                    b.inputs['Roughness'].default_value = SEA_ROUGHNESS
        sc.view_settings.exposure = TEX_EXPOSURE
        render(sc, cam, stem + '_tex.png', os.path.join(sky_root, name), spec['sun'])
        sc.view_settings.exposure = RR.EXPOSURE
        # the same shot in grey clay (the references' albedo 0.18), rocks hidden
        from eidoblend.terrain.build import surfacing as S
        tt.obj.data.materials.clear()
        tt.obj.data.materials.append(S.clay_material('coast_clay'))
        if isinstance(getattr(tt, 'rocks', None), dict) and tt.rocks.get('object') is not None:
            tt.rocks['object'].hide_render = True
        sc.render.filepath = stem + '_clay.png'
        bpy.ops.render.render(write_still=True)
        rec['views'][name] = dict(camera=[round(v, 1) for v in cam_p], target=[round(v, 1) for v in tgt_p],
                                  lens_mm=spec['lens'], sun_compass_deg=spec['sun'],
                                  anchor=[round(float(v), 1) for v in an['p']],
                                  anchor_top_m=round(an['top_z'], 1),
                                  t=[round(float(v), 3) for v in an['t']], n=[round(float(v), 3) for v in an['n']],
                                  focus=[[round(c, 1) for c in f] for f in focus],
                                  sight_clearance_m=round(built_clear, 2),
                                  levels=[str(lv) for lv in tt.levels], seconds=round(time.time() - tv, 1))
        print(f"[coast.views] {name}: camera {rec['views'][name]['camera']} -> {rec['views'][name]['target']}, "
              f"{spec['lens']} mm, top {an['top_z']:.0f} m, {rec['views'][name]['seconds']} s", flush=True)
    shutil.rmtree(sky_root, ignore_errors=True)
    rec['seconds'] = round(time.time() - t0, 1)
    path = os.path.join(OUT, f"{a['tag']}_{a['rock']}_views.json")
    if os.path.exists(path):                     # a re-render of some views keeps the record of the others
        try:
            old = json.load(open(path, encoding='utf-8'))
            rec['views'] = dict(old.get('views', {}), **rec['views'])
        except (OSError, ValueError):
            pass
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(rec, fh, indent=1, default=str)
    os._exit(0)


main()

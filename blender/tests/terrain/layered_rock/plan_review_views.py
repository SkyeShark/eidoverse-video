"""The review's matched cameras on this package's new fields (plain Python, numpy): the independent review placed
its cameras by each photograph's relation to the landform (the canyon overlook 780 m from the river and as high over
it, the Goosenecks rim 330 m from the river and 280 m over it, the valley floor 2.2 km from the highest butte, the
prairie 420 m from the Badlands Wall...) on the fields it judged. The landforms have moved since, so a camera kept at
its old metres can stand inside a side canyon or face a slope; this applies the review's own planning rules
(out/review/scripts/plan_views.py, read only) to the fields gen.py writes, so the new renders stand in the same
relation to the new landforms as the review's did to the old. The canyon also gets the review's hand-placed
brink_down view, placed by rule (brink_view: the Toroweap Overlook photograph's relation to the river, measured on
the real DEM, found on the generated field).

    python plan_review_views.py [--plan <json>] <gen_dir> canyon=<tag> incised_meanders=<tag> mesas_buttes=<tag> ...

Writes blender/tests/terrain/out/layered_rock/review/views_plan.json (or --plan: the review's schema, per recipe its
views, every camera in the main tile's local metres; recipes already in the file are kept) and
camera_map_<recipe>.png (each view's camera and aim over the hillshade).
"""
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
sys.path.insert(0, os.path.join(TN, 'glacial'))
sys.path.insert(0, os.path.join(TN, 'out', 'review', 'scripts'))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

import photo_views as GP  # noqa: E402
import plan_views as PV  # noqa: E402
from eidoblend.terrain.core import io as IO  # noqa: E402

OUT = os.path.join(TN, 'out', 'layered_rock', 'review')


def camera_map(recipe, f, views, path):
    hs = IO.hillshade(f.h, f.cell)
    img = Image.fromarray(np.ascontiguousarray(IO.to_u8(hs)[::-1])).convert('RGB').resize((800, 800))
    d = ImageDraw.Draw(img)
    side = f.h.shape[0] * f.cell
    s = 800.0 / side

    def px(x, y):
        return (x + side / 2) * s, 800 - (y + side / 2) * s
    for v in views:
        c, a = px(*v['cam']), px(*v['aim'][:2])
        d.line([c, a], fill=(255, 200, 60), width=2)
        d.ellipse([c[0] - 5, c[1] - 5, c[0] + 5, c[1] + 5], outline=(255, 80, 40), width=2)
        d.text((c[0] + 7, c[1] - 7), v['name'], fill=(255, 255, 255))
    d.text((6, 6), recipe, fill=(255, 255, 120))
    img.save(path)


def brink_view(f, recipe):
    """The review's hand-placed canyon view (out/review/scripts/extra_views.py brink_down: on the brink of the
    inner gorge's wall looking down the gorge, the Toroweap Overlook photograph's framing), placed by rule: the
    photograph's relation to the river measured on the real DEM (views_match.relation: its distance from and height
    over the river, slid to the brink, looking downstream), and the spot with that relation on the generated field
    (views_match.match_river), its view axis coming down near the river."""
    import landform_refs as LR
    import views_match as VM
    from judge import refs
    view = dict(name='overlook_down', photo='tw_03', kind='river', at=(36.215306, -113.056386), look='downstream',
                toward_deg=20.0, az=225.0, pitch=-16.0, lens=24.0, edge=True, hit_river_m=300.0)
    ref = refs.load('grand_canyon_toroweap')
    half = ref.extent / 2.0
    x, y = LR.latlon_to_xy(ref.meta, *view['at'])
    rel = VM.relation(ref.h, ref.pixel, -half, -half, dict(x=float(x), y=float(y), az=view['az'],
                                                            pitch=view['pitch'], lens=view['lens']), view)
    n = f.h.shape[0]
    m = VM.match_river(f.h, f.cell, -n * f.cell / 2.0, -n * f.cell / 2.0, rel)
    a = math.radians(m['az'])
    p = math.radians(m['pitch'])
    aim = [m['x'] + 1500.0 * math.sin(a) * math.cos(p), m['y'] + 1500.0 * math.cos(a) * math.cos(p),
           m['z'] + 1500.0 * math.sin(p)]
    return PV.V('brink_down', (m['x'], m['y']), ['ground', VM.EYE], aim, 24.0, (0.5, 0.5),
                photo=os.path.join(TN, 'out', 'layered_rock', 'photos', 'tw_03.jpg'),
                caption=f"on the brink of the inner gorge {m['above']:.0f} m over the river and {m['dist']:.0f} m from "
                        f"it (the Toroweap Overlook photograph's relation: {rel['above']:.0f} m over, "
                        f"{rel['dist']:.0f} m from the river), looking down the gorge, 24 mm")


BRINK_VIEWS = {'canyon': ('overlook_down',), 'incised_meanders': ('overlook', 'rim_walk')}


def slide_to_brink(f, cam, aim, max_m=500.0):
    """From the camera toward its aim in 2 m steps to the first spot whose eye (1.7 m up) sees the aim point (the
    river) over the ground in front (plan_views.los), at most max_m: ((x, y), metres slid). The review's overlook rule
    (a distance from the river and a height over it) stands on a bench or a slope back from the edge on a generated
    canyon, and at 30-40 degrees down the frame was the ground at the camera's feet (the review's own overlook renders
    too: "neither the river nor the gorge is in view"); the photographs are taken where the river is in sight. (A
    slide to where the ground 10-25 m ahead drops 20 m stopped short of the lip, on a slope.)"""
    dx, dy = aim[0] - cam[0], aim[1] - cam[1]
    d = math.hypot(dx, dy)
    if d < 1.0:
        return (cam[0], cam[1]), 0.0
    ux, uy = dx / d, dy / d
    for s in np.arange(0.0, min(max_m, d - 30.0), 2.0):
        px, py = cam[0] + s * ux, cam[1] + s * uy
        eye = (px, py, PV.hz(f, px, py) + PV.EYE)
        if sight_clear(f, eye, (aim[0], aim[1], aim[2] + 2.0)):
            return (float(px), float(py)), float(s)
    return (cam[0], cam[1]), 0.0


def sight_clear(f, eye, target, margin=0.03, min_m=2.0, start=4.0, far=0.97, n=300):
    """The sight line from eye to target passes at least max(min_m, margin x distance) above the main level's ground
    from `start` metres out to `far` of the way: the hero levels' finer ground (rock breakup, ledges, the lip's
    talus) stands up to a few metres above the main level's, and a bare line of sight on the 6 m main level still
    rendered as a frame of near ground."""
    d = math.dist(eye[:2], target[:2])
    for t in np.linspace(min(start / max(d, 1.0), 0.5 * far), far, n):
        x = eye[0] + t * (target[0] - eye[0])
        y = eye[1] + t * (target[1] - eye[1])
        z = eye[2] + t * (target[2] - eye[2])
        if PV.hz(f, x, y) > z - max(min_m, margin * t * d):
            return False
    return True


def overlook_spot(f, cam, aim, max_move=400.0):
    """The nearest spot to the planned camera, at the same distance from the aim (+-40 %) and within 70 degrees of the
    same bearing round it, standing at least 0.6 of the planned spot's height over the aim, whose eye sees the aim
    (sight_clear): an overlook above a steep wall (a cut bank) rather than above the gentler flank of a spur, where
    no spot on the straight line sees the river. ((x, y), metres moved) or None."""
    r0 = math.dist(cam, aim[:2])
    b0 = math.atan2(cam[1] - aim[1], cam[0] - aim[0])
    h0 = PV.hz(f, *cam) - aim[2]
    best = None
    for r in np.linspace(0.6 * r0, 1.4 * r0, 9):
        for db in np.radians(np.arange(-70.0, 70.1, 5.0)):
            x, y = aim[0] + r * math.cos(b0 + db), aim[1] + r * math.sin(b0 + db)
            if not PV.inside(f, x, y, 200.0):
                continue
            z = PV.hz(f, x, y)
            if z - aim[2] < 0.6 * h0:
                continue
            moved = math.dist((x, y), cam)
            if moved > max_move or (best is not None and moved >= best[1]):
                continue
            if sight_clear(f, (x, y, z + PV.EYE), (aim[0], aim[1], aim[2] + 2.0)):
                best = ((float(x), float(y)), float(moved))
    return best


def brink_views(recipe, f, views):
    """The recipe's overlook views moved to where the river is in sight: slid toward the aim to the brink
    (slide_to_brink), else the nearest overlook round the aim (overlook_spot); the others that share its camera in
    the review's plan (the rim walk) move with it."""
    names = BRINK_VIEWS.get(recipe, ())
    if not names:
        return views
    first = [v for v in views if v['name'] == names[0]]
    if not first:
        return views
    v0 = first[0]
    (nx, ny), s = slide_to_brink(f, v0['cam'], v0['aim'])
    how = f'slid {s:.0f} m to the brink'
    if s <= 0.0 and not sight_clear(f, (v0['cam'][0], v0['cam'][1], PV.hz(f, *v0['cam']) + PV.EYE),
                                    (v0['aim'][0], v0['aim'][1], v0['aim'][2] + 2.0)):
        spot = overlook_spot(f, v0['cam'], v0['aim'])
        if spot is None:
            print(f'{recipe}: no overlook round the aim sees it; {names} kept', flush=True)
            return views
        (nx, ny), s = spot
        how = f'moved {s:.0f} m round the bend to an overlook that sees the river'
    if s <= 0.0:
        return views
    old = list(v0['cam'])
    for v in views:
        if v['name'] in names and math.dist(v['cam'], old) < 1.0:
            v['cam'] = [nx, ny]
            v['caption'] = v['caption'] + f' ({how})'
    print(f'{recipe}: {", ".join(names)} {how}', flush=True)
    return views


def butte_target(f, min_ha=2.0):
    """The largest free-standing butte or mesa: an island of high ground (over 0.4 of the top relief above the local
    floor, judge/family.mesas' floor) that touches no edge of the tile and carries a cap (some of it under 12
    degrees), as (x, y) of its highest point and its cap's area in hectares, or None. The photographs the mesa views
    stand beside (mv_02 the West Mitten over its talus, mv_04 the Mittens and Merrick Butte) are of buttes; the
    review's rule aimed at the highest ground, which on a floor rising to the west can be the plateau's edge (and a
    flat patch of an escarpment's top is not a butte: the island test is)."""
    import cv2
    from judge import family as Fm
    h = np.asarray(f.h, np.float64)
    n = h.shape[0]
    rel = h - Fm._floor_surface(h, f.cell)
    gy, gx = np.gradient(h, f.cell)
    s = np.degrees(np.arctan(np.hypot(gx, gy)))
    top = np.percentile(rel, 99.9)
    high = rel > 0.4 * top
    m, lab, st, _c = cv2.connectedComponentsWithStats(high.astype(np.uint8), connectivity=8)
    best = None
    for k in range(1, m):
        x0, y0, w, hh, _area = (int(v) for v in st[k])
        if x0 <= 2 or y0 <= 2 or x0 + w >= n - 2 or y0 + hh >= n - 2:
            continue                                    # joined to ground off the tile: not free-standing
        isl = lab == k
        cap = isl & (s < 12.0) & (rel > 0.6 * top)
        ha = cap.sum() * f.cell * f.cell / 1e4
        if ha >= min_ha and (best is None or ha > best[1]):
            jj, ii = np.nonzero(isl)
            t = int(np.argmax(h[jj, ii]))
            best = (((ii[t] + 0.5 - n / 2) * f.cell, (jj[t] + 0.5 - n / 2) * f.cell), ha)
    return best


def plan_mesas(f):
    """The review's mesa views (plan_views.plan_mesas_buttes: the valley floor 2.2 km from the target, under the
    wall 700 m from it, the aerial), aimed at the largest free-standing butte when there is one."""
    views = PV.plan_mesas_buttes(f)
    bt = butte_target(f)
    if bt is None:
        return views
    (tx, ty), ha = bt
    tz = PV.hz(f, tx, ty)
    out = []
    names = [v['name'] for v in views]
    base = {v['name']: v for v in views}
    for name, d, lens, frame, dz, photo, cap in (
            ('valley_view', 2200.0, 45.0, (0.5, 0.55), 60.0, 'mv_04.jpg',
             f'from the valley floor 2.2 km from a butte ({ha:.0f} ha top), 1.7 m, 45 mm (photo mv_04: the Mittens '
             'and Merrick Butte)'),
            ('under_the_wall', 700.0, 28.0, (0.5, 0.45), 80.0, 'mv_02.jpg',
             f'700 m from a butte ({ha:.0f} ha top) at 1.7 m, 28 mm (photo mv_02: the West Mitten over its talus)')):
        # the sight line to a point just over the cap (the review's rule tests a point 40 m under the target, which on
        # a flat-topped butte 300 m across lies inside the rock: every spot was blocked); the camera still aims at
        # the wall under the cap's edge
        spot = PV.floor_spot_toward(f, (tx, ty), d, tz + 5.0)
        if spot is not None:
            out.append(PV.V(name, spot, ['ground', PV.EYE], (tx, ty, tz - dz), lens, frame,
                            photo=os.path.join(PV.PH['rock'], photo), caption=cap))
        elif name in base:
            out.append(base[name])
    out += [v for v in views if v['name'] not in ('valley_view', 'under_the_wall')]
    print('mesas: butte target', [round(tx), round(ty)], f'{ha:.1f} ha; review views were {names}', flush=True)
    return out


def main():
    a = sys.argv[1:]
    path = os.path.join(OUT, 'views_plan.json')
    if '--plan' in a:
        path = a[a.index('--plan') + 1]
        a = [x for i, x in enumerate(a) if x != '--plan' and (i == 0 or a[i - 1] != '--plan')]
    gen_dir = a[0]
    want = dict(x.split('=', 1) for x in a[1:])
    os.makedirs(OUT, exist_ok=True)
    plan = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {}
    for recipe, tag in want.items():
        f = GP.gen_field(os.path.join(gen_dir, tag + '.npz'))
        views = plan_mesas(f) if recipe == 'mesas_buttes' else getattr(PV, 'plan_' + recipe)(f)
        views = brink_views(recipe, f, views)
        if recipe == 'canyon':
            try:
                views.append(brink_view(f, recipe))
            except ValueError as e:
                print('canyon brink_down:', e)
        plan[recipe] = dict(views=views, size=float(f.h.shape[0] * f.cell), field=tag)
        print(recipe, tag, [(v['name'], [round(c) for c in v['cam']], v['cam_z'][0], round(v['cam_z'][1]))
                            for v in views], flush=True)
        camera_map(recipe, f, views, os.path.join(OUT, f'camera_map_{recipe}.png'))
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(plan, fh, indent=1)
    print('wrote', path)


if __name__ == '__main__':
    main()

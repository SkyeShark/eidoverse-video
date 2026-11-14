"""The judge's views (views.json), made from the review's matched cameras (system Python: numpy, Pillow):

    python blender/tests/terrain/surfacing_judge/make_views.py [--plan <the review's views_plan.json>]
           [--recipes a,b] [--write] [--terrains <json>]

Every camera of the review's plan is checked on the recipe's saved terrain of today (views.check). A camera that
fails is moved by the rule FIXES gives it, and a recipe that has no establishing aerial or no low oblique gets one
(ADDED, the rule in `added`); every recipe already has an eye view. Without --write the moves are proposed: each is
printed with its check, and out/surfacing_judge/views_fix.jpg shows per moved or added view the photograph, the
review's camera and the judge's camera as grey clay on the saved terrain. With --write, views.json is written.

The terrain moves when a solver changes, and a camera placed on yesterday's field can face a wall on today's: run
this again then (check_views.py says which views fail). A move keeps what the photograph shows: a view whose aim is
a feature (a river, an island, a butte) keeps the feature and is moved, by Terrain.viewpoint's rule
(views.viewpoint), to a standing point that sees it from about the same heading and distance; a view whose aim only
gives the photograph's heading and pitch keeps both and is moved to the nearest standing point of the kind the
photograph was taken from (a summit, a crest, a floor) where nothing rises in front of it.
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..')))

from surfacing_judge import OUT, TN  # noqa: E402
from surfacing_judge import views as V  # noqa: E402
from surfacing_judge.check_views import load_terrain, terrain_sources  # noqa: E402

REVIEW_PLAN = os.path.join(TN, 'out', 'review', 'views_plan.json')
# the reference each recipe's extent comes from, and its knobs (surfacing/review_views.py's tables)
REFERENCES = {'fluvial_range': 'san_gabriel_mountains', 'alpine_valley': 'lauterbrunnen',
              'stratovolcano': 'mount_fuji', 'caldera': 'crater_lake', 'cinder_cones': 'sp_crater',
              'impact_crater': 'meteor_crater', 'canyon': 'grand_canyon_toroweap', 'incised_meanders': 'goosenecks',
              'mesas_buttes': 'monument_valley', 'badlands': 'badlands_sd', 'dunes': 'namib_star_dunes',
              'tower_karst': 'guilin_karst', 'sea_cliffs': 'seven_sisters', 'rolling_hills': 'palouse_hills',
              'real_place': 'lauterbrunnen', 'meadow': None}
PARAMS = {'real_place': {'dem': 'lauterbrunnen'}}

# How each failing view of the review is moved, and why (checked on the saved terrains of 11-13 evening).
#   see:   the aim is a feature: keep it (target 'aim'; 'low' or 'high': the lowest or highest ground within r
#          metres of the aim, plus dz) and stand where it is seen from about the view's heading and distance,
#          preferring the kind of spot the photograph was taken from
#   spot:  the aim is a direction: keep the heading and pitch (pitch: the photograph's, where today's ground moved
#          the review's), stand within `radius` of the review's spot on the kind of ground the photograph was taken
#          from, where nothing rises in front
#   by_eye: moved though the check passes it (its clay does not read as the photograph)
FIXES = {
    ('fluvial_range', 'summit_over_ridges'): dict(
        how='spot', radius=3000.0, prefer='high', pitch=-6.0,
        why='a slope rises in front of the camera; the photograph looks south over ridges from a summit, 6 degrees '
            'down'),
    ('alpine_valley', 'floor_lischmaad'): dict(
        how='see', target='aim', prefer='low',
        why='the camera stands against the trough wall (rock fills the picture); the photograph looks across the '
            'floor at the Staubbach wall'),
    ('alpine_valley', 'shoulder_wengen'): dict(
        how='see', target='low', r=1500.0, dz=60.0, prefer='high', ring='context',
        why='the camera faces a slope; the photograph looks down the trough from Wengen\'s shoulder. It stays on a '
            'context ring: one of the three eye views that show the near material there (SURFACING_DESIGN.md 5.4, '
            'package 2, item 7)'),
    ('alpine_valley', 'ridge_schynige'): dict(
        how='spot', radius=1500.0, prefer='high', keep_height=True, within='outer',
        why='the near ridge hides the valley the camera looks down into; the photograph looks across the valley '
            'from a high ridge'),
    ('alpine_valley', 'trough_lip'): dict(
        how='spot', radius=1500.0, prefer='high',
        why='a slope fills the picture; the photograph looks down the trough from its lip'),
    ('stratovolcano', 'walk_upper_flank'): dict(
        how='see', target='high', r=600.0, dz=0.0, prefer='high', distance=1500.0,
        why='the convex flank hides the summit the camera looks up at from 3.8 km'),
    ('caldera', 'rim_east'): dict(
        how='see', target='high', r=1500.0, dz=0.0, prefer='high',
        why='the rim rises in front of the camera; the photograph looks over the lake at Wizard Island from the '
            'east rim'),
    ('caldera', 'rim_west_down'): dict(
        how='see', target='high', r=1500.0, dz=0.0, prefer='high',
        why='the camera faces a slope; the photograph looks down at Wizard Island from the west rim'),
    ('canyon', 'overlook_down'): dict(
        how='see', target='low', r=400.0, dz=2.0, prefer='high',
        why='the camera looks down at the plateau in front of the brink; the photograph looks down at the river '
            'from the overlook'),
    ('incised_meanders', 'overlook'): dict(
        how='see', target='low', r=500.0, dz=2.0, prefer='high',
        why='a wall rises in front of the camera; the photograph looks down at the river from the rim'),
    ('incised_meanders', 'rim_walk'): dict(
        how='see', target='low', r=500.0, dz=2.0, prefer='high',
        why='a slope fills the picture; the photograph walks the rim with the gorge beside it'),
    ('mesas_buttes', 'valley_view'): dict(
        how='see', target='high', r=1200.0, dz=-40.0, prefer='low',
        why='a near mesa hides the buttes; the photograph looks across the valley floor at three buttes'),
    ('mesas_buttes', 'under_the_wall'): dict(
        how='see', target='high', r=1200.0, dz=-60.0, prefer='low',
        why='the camera looks up at sky where a butte stood; the photograph stands under a butte'),
    ('dunes', 'crest'): dict(
        how='spot', radius=900.0, prefer='high', pitch=-7.0,
        why='a dune face rises in front of the camera; the photograph looks along a crest down to the plain'),
    ('tower_karst', 'riverbank'): dict(
        how='spot', radius=1200.0, prefer='low',
        why='a tower fills the picture; the photograph looks over the river at towers in the distance'),
    ('tower_karst', 'plain_fields'): dict(
        how='see', target='high', r=600.0, dz=-30.0, prefer='low',
        why='a nearer tower hides the one the camera looks up at; the photograph looks up a valley between towers'),
    ('sea_cliffs', 'clifftop_along'): dict(
        how='see', target='aim_ground', dz=5.0, prefer='high',
        why='a grass slope rises in front of the camera; the photograph walks the clifftop with the sea beside it'),
    ('sea_cliffs', 'headland_tele'): dict(
        how='see', target='aim_ground', dz=5.0, prefer='high',
        why='a nearer rise hides the cliff line; the photograph looks along the Seven Sisters from Seaford Head'),
    ('rolling_hills', 'hilltop_walk'): dict(
        how='spot', radius=1500.0, prefer='high', pitch=-3.0,
        why='a nearer rise hides the hills; the photograph looks out over the fields from a hilltop'),
}
# a view the check passes but the design needs as it is
KEEP = {('canyon', 'brink_down'): 'the near right-hand wall is the material package\'s test case for the Box '
                                  'projection\'s smear (SURFACING_DESIGN.md 5.4, package 2, item 2)',
        ('impact_crater', 'plain_north'): 'an eye view on a context ring, one of the three that show the near '
                                          'material there (SURFACING_DESIGN.md 5.4, package 2, item 7)',
        ('real_place', 'ridge_schynige'): 'an eye view on a context ring, one of the three that show the near '
                                          'material there (SURFACING_DESIGN.md 5.4, package 2, item 7)'}
# the two places the board enlarges, where the review's renders showed what section 1.4 names (render pixels; the
# board picks its own for every other view)
CROPS = {('canyon', 'brink_down'): [[700, 100, 940, 235], [380, 300, 620, 435]],          # the smeared wall; the gorge
         ('canyon', 'approach_walk'): [[360, 405, 600, 540], [380, 250, 620, 385]],      # the plateau; far talus
         ('impact_crater', 'rim_north'): [[300, 160, 540, 295], [120, 300, 360, 435]],   # wall ribs; the floor ring
         ('real_place', 'floor_lischmaad'): [[0, 405, 240, 540], [560, 60, 800, 195]],   # the floor; the wall
         ('badlands', 'prairie_walk'): [[0, 160, 240, 295], [360, 405, 600, 540]]}       # the bands; the prairie
# headings (compass degrees looked toward) of the added aerials where 45 does not show the landform
ADD_HEADING = {'real_place': 180.0, 'sea_cliffs': 350.0, 'alpine_valley': 180.0}
# how far from the main tile's centre the low oblique's target is sought, a share of the side (default 0.05: the
# landform at the centre), where the centre holds no ground worth the view (the caldera's centre is its lake)
LOW_TARGET_R = {'caldera': 0.4}


def level_kind(c, side):
    """'eye' (within 10 m of the ground), 'low' (a low oblique: under a tenth of the main tile's side over the
    ground) or 'high' (an establishing aerial)."""
    h = c['height_m']
    if h <= 10.0:
        return 'eye'
    return 'high' if h >= 0.1 * side else 'low'


def _rel(stack, p):
    cx, cy = V.main_centre(stack)
    return [round(float(p[0]) - cx, 3), round(float(p[1]) - cy, 3)]


def _extreme_near(stack, x, y, r, which):
    """The lowest or highest ground of the main level within r metres of (x, y): (x, y, z)."""
    h = np.asarray(stack.fields[stack.main]['h'], np.float64)
    X, Y = stack.xy('main')
    m = (X - x) ** 2 + (Y - y) ** 2 <= r * r
    if not m.any():
        return x, y, float(stack.height_at(x, y))
    hm = np.where(m, h, np.inf if which == 'low' else -np.inf)
    k = int(np.argmin(hm) if which == 'low' else np.argmax(hm))
    j, i = np.unravel_index(k, h.shape)
    return float(X[j, i]), float(Y[j, i]), float(h[j, i])


def fix_see(stack, v, f):
    cam, ground, aim = V.camera_of(stack, v)
    dist = float(f.get('distance') or math.hypot(aim[0] - cam.eye[0], aim[1] - cam.eye[1]))
    if f['target'] == 'aim':
        tgt = (float(aim[0]), float(aim[1]), float(aim[2]))
    elif f['target'] == 'aim_ground':
        tgt = (float(aim[0]), float(aim[1]), float(stack.height_at(aim[0], aim[1])) + f.get('dz', 0.0))
    else:
        x, y, z = _extreme_near(stack, aim[0], aim[1], f['r'], f['target'])
        tgt = (x, y, z + f.get('dz', 0.0))
    eye_h = float(v['cam_z'][1]) if v['cam_z'][0] == 'ground' else 1.7
    within, exclude = 'main', None
    if f.get('ring') == 'context':                     # an eye view that stands on a context ring, as its spot does
        main = stack.levels[stack.main]
        within, exclude = 0, (main['x0'], main['y0'], main['x0'] + main['side'], main['y0'] + main['side'])
    for scale in (1.0, 0.75, 1.35, 0.55, 1.8):
        vp = V.viewpoint(stack, tgt, dist * scale, eye_height=eye_h, heading=cam.heading_deg,
                         prefer=f.get('prefer'), lens_mm=v['lens'], within=within, exclude=exclude)
        if vp is None:
            continue
        w = dict(v, cam=_rel(stack, vp['eye']), cam_z=['ground', round(eye_h, 3)],
                 aim=_rel(stack, tgt) + [round(tgt[2], 3)])
        c = V.check(stack, w)
        if not c['fails']:
            return w, c, (f"stands {math.hypot(vp['eye'][0] - cam.eye[0], vp['eye'][1] - cam.eye[1]):.0f} m from "
                          f"the review's spot{' on a context ring' if exclude else ''}, sees the target from "
                          f"{vp['distance']:.0f} m at heading {vp['heading_deg']:.0f}")
    return None, None, 'no standing point sees the target'


def fix_spot(stack, v, f, n=15):
    cam, ground, aim = V.camera_of(stack, v)
    d = aim - cam.eye
    dist = float(np.linalg.norm(d))
    dirn = d / dist
    if f.get('pitch') is not None:                     # the photograph's own pitch where today's ground changed it
        hd, pt = math.radians(cam.heading_deg), math.radians(float(f['pitch']))
        dirn = np.array([math.sin(hd) * math.cos(pt), math.cos(hd) * math.cos(pt), math.sin(pt)])
    # an eye stands in the main tile (its hero levels); a high view may stand over the context levels
    lv = stack.levels[stack.main if f.get('within', 'main') == 'main' else 0]
    r = float(f['radius'])
    g = np.linspace(-r, r, n)
    xs, ys = np.meshgrid(cam.eye[0] + g, cam.eye[1] + g)
    xs, ys = xs.ravel(), ys.ravel()
    m = 2.0 * lv['cell']
    ok = ((xs - cam.eye[0]) ** 2 + (ys - cam.eye[1]) ** 2 <= r * r) & (xs >= lv['x0'] + m) & \
         (xs <= lv['x0'] + lv['side'] - m) & (ys >= lv['y0'] + m) & (ys <= lv['y0'] + lv['side'] - m)
    xs, ys = xs[ok], ys[ok]
    keep = V.dry(stack, xs, ys) if len(xs) else np.zeros(0, bool)
    xs, ys = xs[keep], ys[keep]
    if not len(xs):
        return None, None, f'no dry ground within {r:.0f} m inside the level'
    gz = np.asarray(stack.height_at(xs, ys), np.float64)
    slope = np.degrees(np.arccos(np.clip(V._normals(stack.height_at, xs, ys, lv['cell'])[:, 2], -1, 1)))
    rank = (gz - gz.min()) / max(float(np.ptp(gz)), 1e-6)
    # the camera's height over the ground: an eye stays an eye; a high view keeps its height (keep_height) or
    # becomes an eye on the spot (the photograph's standing point)
    eye_h = float(v['cam_z'][1]) if v['cam_z'][0] == 'ground' and (f.get('keep_height') or
                                                                    float(v['cam_z'][1]) <= 10.0) else 1.7
    best = None
    for x, y, z, s, rk in zip(xs, ys, gz, slope, rank):
        if s > 30.0:
            continue
        if f.get('prefer') == 'high' and rk < 0.6:                     # summits, crests and rims only
            continue
        eye = np.array([x, y, z + eye_h])
        a = eye + dirn * dist
        w = dict(v, cam=_rel(stack, eye), cam_z=['ground', round(eye_h, 3)], aim=_rel(stack, a) + [round(a[2], 3)])
        c = V.check(stack, w, grid=(64, 36))
        if c['fails']:
            continue
        # a summit, crest or floor as the photograph's; near the review's spot; nothing rising in front; the ray
        # along the photograph's heading and pitch reaching far before it meets the ground (an open view)
        score = (rk if f.get('prefer') == 'high' else 1.0 - rk) * 6.0 - math.hypot(x - cam.eye[0],
                                                                                y - cam.eye[1]) / r * 2.0 \
            - 8.0 * c['blocked'] + 3.0 * c['aim_seen']
        if best is None or score > best[0]:
            best = (score, w, x, y)
    if best is None:
        return None, None, f'no standing point within {r:.0f} m keeps the heading clear'
    w = best[1]
    c = V.check(stack, w)
    if c['fails']:
        return None, None, 'the best spot fails the full check: ' + '; '.join(c['fails'])
    pitch = f.get('pitch')
    return w, c, (f"stands {math.hypot(best[2] - cam.eye[0], best[3] - cam.eye[1]):.0f} m from the review's spot, "
                  f"keeps heading {cam.heading_deg:.0f}"
                  + (f", looks {pitch:+.0f} degrees as the photograph does" if pitch is not None
                     else f" and pitch {cam.pitch_deg:.1f}"))


def added(stack, recipe, kind, side):
    """An establishing aerial ('high': 0.9 x the main tile's side from its centre, 30 degrees down at it, 35 mm) or
    a low oblique ('low': Terrain.viewpoint's rule at 0.3 x the side from the centre, 0.05 x the side over the
    ground, 35 mm), looking toward ADD_HEADING (default 45: north-east)."""
    cx, cy = V.main_centre(stack)
    zc = float(stack.height_at(cx, cy))
    hd = ADD_HEADING.get(recipe, 45.0)
    bearing = math.radians((hd + 180.0) % 360.0)                   # from the centre to the camera
    if kind == 'high':
        D = 0.9 * side
        ex, ey = cx + D * math.sin(bearing), cy + D * math.cos(bearing)
        ez = zc + D * math.tan(math.radians(30.0))
        w = dict(name='establishing', kind='aerial', origin='judge: an establishing aerial',
                 cam=_rel(stack, (ex, ey)), cam_z=['abs', round(ez, 3)], aim=[0.0, 0.0, round(zc, 3)], lens=35.0,
                 frame=[0.5, 0.55], focus=False, photo=None,
                 caption=f'the judge\'s establishing aerial: {D / 1000:g} km from the main tile\'s centre, 30 '
                         f'degrees down at it, looking {hd:.0f} degrees, 35 mm')
        return w
    # the low oblique looks at the highest ground near the centre (a crater's floor at the centre hides behind its
    # rim from a low camera; the rim and what stands on it do not)
    tx, ty, tz = _extreme_near(stack, cx, cy, LOW_TARGET_R.get(recipe, 0.05) * side, 'high')
    vp = None
    for scale in (1.0, 0.8, 1.25, 0.6, 1.6):
        vp = V.viewpoint(stack, (tx, ty, tz), 0.3 * side * scale, eye_height=0.05 * side, heading=hd, lens_mm=35.0)
        if vp is not None:
            break
    if vp is None:                                     # no candidate: straight back from the target along the heading
        D = 0.3 * side
        ex, ey = tx + D * math.sin(bearing), ty + D * math.cos(bearing)
        gz = float(stack.height_at(ex, ey))
        vp = dict(eye=(ex, ey, gz + 0.05 * side), distance=D, heading_deg=hd)
    return dict(name='low_oblique', kind='aerial', origin='judge: a low oblique',
                cam=_rel(stack, vp['eye']), cam_z=['ground', round(0.05 * side, 3)],
                aim=_rel(stack, (tx, ty)) + [round(tz, 3)],
                lens=35.0, frame=[0.5, 0.5], focus=False, photo=None,
                caption=f"the judge's low oblique: {0.05 * side:g} m over the ground, {vp['distance']:.0f} m from the "
                        f"highest ground near the main tile's centre, looking {vp['heading_deg']:.0f} degrees, 35 mm")


def main(argv):
    def opt(k, d=None):
        return argv[argv.index(k) + 1] if k in argv else d
    only = set(opt('--recipes').split(',')) if opt('--recipes') else None
    review = V.import_review_plan(opt('--plan', REVIEW_PLAN), REFERENCES, PARAMS)
    src = terrain_sources(opt('--terrains'))
    current = V.load() if os.path.exists(V.VIEWS_JSON) else {}
    out, sheet_rows = {}, []
    for recipe, rec in review.items():
        if only and recipe not in only:
            out[recipe] = current.get(recipe, rec)
            continue
        if recipe not in src:
            print(f'{recipe}: no saved terrain: its views are copied unchecked')
            out[recipe] = rec
            continue
        st = load_terrain(recipe, src[recipe])
        side = st.levels[st.main]['side']
        views, kinds = [], set()
        for v in rec['views']:
            c = V.check(st, v)
            key = (recipe, v['name'])
            if key in KEEP:
                v = dict(v, origin=f'review, kept: {KEEP[key]}')
            if key in FIXES and (c['fails'] or FIXES[key].get('by_eye')):
                f = FIXES[key]
                w, c2, how = (fix_see if f['how'] == 'see' else fix_spot)(st, v, f)
                if w is None:
                    print(f'{recipe}/{v["name"]}: FAILS ({"; ".join(c["fails"])}) and the fix found nothing: {how}')
                    v = dict(v, origin=f"review, failing: {f['why']}; no move found ({how})")
                else:
                    w['origin'] = f"review, moved: {f['why']}; the judge's camera {how}"
                    w['focus'] = bool(V.kind_of(w) == 'eye' and c2['stands'] == 'main')
                    print(f'{recipe}/{v["name"]}: moved, {how}; blocked {100 * c2["blocked"]:.0f} %, ground '
                          f'{100 * c2["ground"]:.0f} %, aim ray {100 * c2["aim_seen"]:.0f} %')
                    sheet_rows.append((recipe, v, w, st))
                    v = w
                    c = c2
            elif c['fails']:
                print(f'{recipe}/{v["name"]}: FAILS with no fix written: {"; ".join(c["fails"])}')
            kinds.add(level_kind(c, side))
            if key in CROPS and not v.get('origin', '').startswith('review, moved'):
                v = dict(v, crops=CROPS[key])
            views.append(v)
        for kind in ('high', 'low'):
            if kind in kinds:
                continue
            w = added(st, recipe, kind, side)
            if w is None:
                print(f'{recipe}: no {kind} view could be placed')
                continue
            c = V.check(st, w)
            print(f"{recipe}/{w['name']}: added; " + ('ok' if not c['fails'] else 'FAILS: ' + '; '.join(c['fails'])))
            if not c['fails']:
                views.append(w)
                sheet_rows.append((recipe, None, w, st))
        out[recipe] = dict(reference=rec['reference'], params=rec['params'], views=views)
    if sheet_rows:
        from PIL import Image, ImageDraw
        from surfacing_judge.check_views import TILE, _tile
        cw, ch = 3 * TILE[0] + 8, TILE[1] + 18
        cols = 2
        n = (len(sheet_rows) + cols - 1) // cols
        sheet = Image.new('RGB', (cols * cw, n * ch), (16, 16, 16))
        d = ImageDraw.Draw(sheet)
        for k, (recipe, v0, w, st) in enumerate(sheet_rows):
            x, y = (k % cols) * cw, (k // cols) * ch
            tiles = [_tile(V.photo_path(w), 'no photograph'),
                     Image.fromarray(V.preview(st, v0, (192, 108))).resize(TILE) if v0 else _tile(None, 'added'),
                     Image.fromarray(V.preview(st, w, (192, 108))).resize(TILE)]
            for j, im in enumerate(tiles):
                sheet.paste(im, (x + j * TILE[0], y + 16))
            d.text((x + 4, y + 2), f"{recipe}/{w['name']}: photograph | the review's camera | the judge's camera",
                   fill=(230, 220, 160))
        os.makedirs(OUT, exist_ok=True)
        sheet.save(os.path.join(OUT, 'views_fix.jpg'), quality=88)
        print('sheet:', os.path.join(OUT, 'views_fix.jpg'))
    if '--write' in argv:
        with open(V.VIEWS_JSON, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(V.dumps(out))
        print('wrote', V.VIEWS_JSON, sum(len(r['views']) for r in out.values()), 'views')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

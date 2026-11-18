"""Every measure on one state of the surfacing, written down so the next state is measured the same way (system
Python: numpy, Pillow; no render):

    python blender/tests/terrain/surfacing_judge/baseline.py [--state before] [--terrains <json>] [--recipes a,b]
           [--views a,b] [--plan <views.json>] [--ref-state before] [--audit <folder>] [--snap <dir>]
           [--skip tile,frames,splat,audit_frames]
    (a run adds to the state's json: --skip tile keeps the tiles measured before, --skip audit_frames the audit's
    frame splats; --skip splat leaves the frames that have no layer map without layers, which saves minutes a view;
    --ref-state: today's renders the repetition energy is read against, default the frozen state 'before';
    --snap: where the renders' own terrains are saved (review_views.py --snap): a view whose record names its
    terrain file there is measured on it, hero levels and all, so the window edges a seam is read along land on the
    ground the render drew; else on the recipe's listed terrain, whose main level hero levels refine by metres to
    tens of metres)

The tile    per recipe, on the main level of the terrain listed for the state (--terrains; default
            out/surfacing_judge/terrains_<state>.json when it exists, else terrains.json), the palette's layers
            evaluated on its masks and composited as the material does (layers.py):
              the one-material share: where one layer holds 90 % of the weight (pure), and the largest connected
              region one layer dominates (largest), on the tile less its outer 8 cells
              each layer's share, pure share, largest region and height-line index (the whole tile)
              the height-line index over all layers' edges, on all ground and on slopes over 25 degrees, and again
              with the rock column's bed edges left out where a palette places layers by them (none does today)
              the height-line index of the masks the palette reads, and of the audit's masks, on the steep ground
The frames  per view of views.json the state rendered (states.py):
              the layers per pixel: the state's layer-map render decoded (review_views.py --layers), else for an
              aerial view the layers splatted into its camera from the saved levels (no render; layers.frame_splat)
              the frame's one-material share; within-layer variation (32 px blocks) against the photograph's ground
              the ground's colour against the photograph's (CIELAB mean and the spread of 32 px blocks), where
              photos.json marks the photograph's ground and the layer map marks the render's
              repetition in ground windows (eye views: rows 12-25, 25-50 and 50-100 m out; aerials: three windows
              in the lower picture); the colour step across each level window's edge (seams); the render's seconds
The audit   with --audit <folder> (the audit's coverage.json, curv_contour.json, repeat.json, repeat_walls.json,
            frame_fraction.json): the audit's own windows and terrains measured again, each number beside the
            audit's and the difference (the acceptance: within 10 %)

Writes out/surfacing_judge/baseline_<state>.json and baseline_<state>.md. To measure the palettes of another commit
(the state before a round), see this package's __init__: EIDO_JUDGE_BLENDER_DIR.
"""
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..')))

from surfacing_judge import OUT, OUT_ROOT, rel  # noqa: E402
from surfacing_judge import cost as C  # noqa: E402
from surfacing_judge import layers as LY  # noqa: E402
from surfacing_judge import measures as M  # noqa: E402
from surfacing_judge import states as S  # noqa: E402
from surfacing_judge import views as V  # noqa: E402
from surfacing_judge.check_views import load_terrain, terrain_sources  # noqa: E402

# the masks the audit's curv_contour.py measured
AUDIT_MASKS = ('convex_20m', 'concave_20m', 'curv_plan_20m', 'curv_profile_20m', 'convex', 'concave', 'slope', 'flow',
               'wetness', 'strata', 'talus', 'rock_toe', 'channels')
BANDS_M = ((12, 25), (25, 50), (50, 100))


# ------------------------------------------------------------------------------------------------- the tile ---

def tile_measures(stack, log=print):
    t0 = time.time()
    t = LY.main_tile(stack)
    E, names, h, cell = t['E'], t['names'], t['h'], t['cell']
    n = h.shape[0]
    s = slice(8, n - 8)
    om = M.one_material(E[:, s, s], names=names)
    lc = M.layer_contours(E, h, cell, t['slope'], names)
    out = dict(palette=t['pal']['name'], cell_m=cell, side_m=cell * n, pure_total=om['pure_total'],
               largest=om['largest'], largest_layer=om['largest_layer'], height_line_all=lc['all'],
               height_line_steep=lc['steep'], steep_share=lc['steep_share'], layers=[])
    for row, crow, L in zip(om['layers'], lc['layers'], t['pal']['layers']):
        out['layers'].append(dict(name=row['name'], set=L['set'], share=row['share'], pure=row['pure'],
                                  largest=row['largest'], height_line=crow['all'], height_line_steep=crow['steep']))
    strata = LY.reads_strata(t['pal'])
    out['reads_strata'] = strata
    if strata:
        Ef = LY.weights(t['pal'], stack.masks('main'), *stack.xy('main'), stack.constants(t['pal']),
                        freeze=LY.STRATA_MASKS)
        lf = M.layer_contours(Ef, h, cell, t['slope'], names)
        out['height_line_all_beds_out'], out['height_line_steep_beds_out'] = lf['all'], lf['steep']
    else:                                              # the column colours layers, it does not place them
        out['height_line_all_beds_out'], out['height_line_steep_beds_out'] = lc['all'], lc['steep']
    mk = stack.masks('main')
    inner = np.zeros(h.shape, bool)
    inner[s, s] = True
    steep = inner & (np.asarray(mk['slope'], np.float64) > 25.0)
    from eidoblend.terrain.build import palettes as P
    names_m = sorted(set(AUDIT_MASKS) | (set(P.material_masks(t['pal'])) - {'height'}))
    out['mask_height_line_steep'] = {k: M.contour_index(np.asarray(mk[k], np.float64), h, cell, steep, min_grad=1e-9)
                                     for k in names_m if k in mk}
    out['mask_height_line_all'] = {k: M.contour_index(np.asarray(mk[k], np.float64), h, cell, inner, min_grad=1e-9)
                                   for k in names_m if k in mk}
    # diagnostics with no reference on the tile until orthophotos of the places are fetched (section 6): read
    # against the state before (baseline_<before>.json) and random (0.64), and against the boards
    out['seconds'] = round(time.time() - t0, 1)
    return out


# ----------------------------------------------------------------------------------------------- the frames ---

def _upsample(a, shape):
    """A (k, h, w) or (h, w) grid repeated up to shape (H, W) (the splat's pixels as blocks of the render's)."""
    a = np.asarray(a)
    H, W = shape
    hh, ww = a.shape[-2:]
    iy = np.minimum((np.arange(H) * hh) // H, hh - 1)
    ix = np.minimum((np.arange(W) * ww) // W, ww - 1)
    return a[..., iy[:, None], ix[None, :]]


def frame_layers(stack, pal, v, rec, layers_png, shape, log=None, splat=True):
    """(weights (layers, H, W), ground (H, W) bool, source) for a render: its layer map when there is one, else the
    splat for an aerial view (splat=False: none), else (None, None, None)."""
    n = len(pal['layers'])
    if layers_png:
        w, ground, _water, info = LY.decode_layer_map(M.load_rgba(layers_png), n)
        return w, ground, dict(source='layer map', **info)
    cam = V.Camera.from_record(rec)
    if cam is None or V.kind_of(v) == 'eye' or stack is None or not splat:
        return None, None, None
    w, seen = LY.frame_splat(stack, pal, cam, size=(240, 135), log=log)
    return _upsample(w, shape), _upsample(seen, shape).astype(bool), dict(source='splat (240 x 135, no render)')


def rows_for_band(cam, d0, d1, H=540, W=960):
    """The picture rows where level ground 1.7 m under a camera of this pitch lies d0..d1 metres out (the audit's
    rule for eye views): (row0, row1) or None."""
    f = cam.lens / V.SENSOR_MM * W
    pitch = math.radians(cam.pitch_deg)
    out = []
    for d in (d1, d0):
        ang = math.asin(min(1.7 / d, 1.0))
        out.append(H / 2 + f * math.tan(ang + pitch))
    r0, r1 = int(round(out[0])), int(round(out[1]))
    if r1 - r0 < 3 or r0 < 0 or r1 > H:
        return None
    return r0, r1


def frame_windows(v, cam, ground):
    """The ground windows a frame's repetition is read in: eye views, the rows of each distance band (rows mode);
    aerials, three 300 x 160 windows in the lower picture that lie wholly on the ground (2-D)."""
    wins = []
    if V.kind_of(v) == 'eye' and cam is not None:
        for d0, d1 in BANDS_M:
            rr = rows_for_band(cam, d0, d1)
            if rr and (ground is None or ground[rr[0]:rr[1]].mean() > 0.95):
                wins.append((f'{d0}-{d1} m', (0, rr[0], 960, rr[1]), 'rows'))
    else:
        for x0 in (0, 330, 660):
            box = (x0, 380, x0 + 300, 540)
            if ground is None or ground[380:540, x0:x0 + 300].mean() > 0.95:
                wins.append((f'lower {x0}', box, '2d'))
    return wins


def seams(stack, rec, cam, img, ground=None, weights=None):
    """The colour step across each level window's edge the render shows (measures.seam_delta along the projected
    edge, the hidden parts left out; with a layer map, only where both sides are terrain holding the same layers):
    [dict(level, role, delta_e, control, excess, n)]."""
    out = []
    if cam is None or stack is None:
        return out
    for L in S.levels(rec):
        if L['role'] not in ('main', 'hero'):
            continue
        x0, y0, sd = L['x0'], L['y0'], L['side']
        t = np.linspace(0.0, 1.0, 241)
        pts = np.concatenate([np.stack([x0 + sd * t, np.full_like(t, y0)], 1),
                              np.stack([np.full_like(t, x0 + sd), y0 + sd * t], 1),
                              np.stack([x0 + sd * t[::-1], np.full_like(t, y0 + sd)], 1),
                              np.stack([np.full_like(t, x0), y0 + sd * t[::-1]], 1)])
        z = np.asarray(stack.height_at(pts[:, 0], pts[:, 1]), np.float64)
        px, py, zc = cam.project(pts[:, 0], pts[:, 1], z)
        d = np.stack([pts[:, 0] - cam.eye[0], pts[:, 1] - cam.eye[1], z - cam.eye[2]], 1)
        dist = np.linalg.norm(d, axis=1)
        front = (zc > 1.0) & (px >= 0) & (px < 960) & (py >= 0) & (py < 540)
        vis = np.zeros(len(pts), bool)
        if front.any():
            dirs = d[front] / dist[front][:, None]
            hit = V.raycast(stack.height_at, cam.eye, dirs, float(dist[front].max()) * 1.02, near=1.0)
            vis[front] = hit >= dist[front] * 0.97 - 2.0
        P, N, ok = M.line_samples(np.stack([px, py], 1), vis)
        r = M.seam_delta(img, P, N, ok, ground=ground, weights=weights) if len(P) else None
        if r:
            out.append(dict(level=L['index'], role=L['role'], side_m=sd, **r))
    return out


def frame_measures(recipe, v, state, stack, pal, ref_state=None, splat=True, log=print):
    path = S.render(recipe, v['name'], state)
    if not path:
        return None
    rec = S.record(recipe, v['name'], state)
    img = M.load_rgb(path)
    shape = img.shape[:2]
    cam = V.Camera.from_record(rec)
    w, ground, src = frame_layers(stack, pal, v, rec, S.layers(recipe, v['name'], state), shape, log=None,
                                  splat=splat)
    out = dict(render=rel(path), kind=V.kind_of(v), layers_from=src, cost=C.render_cost(rec, V.kind_of(v)))
    names = [L['name'] for L in pal['layers']]
    photo_path = V.photo_path(v)
    photo = M.load_rgb(photo_path, width=960) if photo_path else None
    pg = V.photo_ground(v, photo.shape) if photo is not None else None
    if w is not None:
        om = M.one_material(w, ground, names)
        ref = None
        if pg is not None:                             # the photograph's own: as many classes as the frame has layers
            k = max(1, sum(1 for r in om['layers'] if r['share'] >= 0.02))
            ref = M.reference_one_material(photo, pg, k)
        out['one_material'] = dict(pure_total=om['pure_total'], largest=om['largest'],
                                   largest_layer=om['largest_layer'],
                                   shares={r['name']: r['share'] for r in om['layers']},
                                   photo_largest=None if ref is None else ref['largest'],
                                   flag=M.flag('largest_region', om['largest'], None if ref is None else
                                               ref['largest']))
        pst = M.block_stats(photo, pg) if pg is not None else None
        lv = M.layer_variation(img, w, ground, names, pst)
        out['variation'] = [dict(name=r['name'], blocks=r['n'], L_std=r['L_std'], ratio=r['ratio'],
                                 flag=M.flag('variation_ratio', r['ratio'])) for r in lv if r['n']]
        if pg is not None:
            cc = M.colour_compare(img, ground, photo, pg)
            out['colour'] = dict(delta_e=cc['delta_e'], delta_e_raw=cc['delta_e_raw'],
                                 exposure_scale=cc['exposure_scale'], spread_ratio_L=cc['spread_ratio_L'],
                                 spread_ratio_ab=cc['spread_ratio_ab'], render_lab=cc['render']['lab_mean'],
                                 photo_lab=cc['photo']['lab_mean'])
    lum = M.luma(img)
    # today's render of the same camera: the repetition windows' energy is read against it (blur cannot pass)
    ref_path = S.render(recipe, v['name'], ref_state) if ref_state else None
    ref_lum = M.luma(M.load_rgb(ref_path)) if ref_path and S.same_camera(
        v, S.record(recipe, v['name'], ref_state)) is not False else None
    reps = []
    for label, box, mode in frame_windows(v, cam, ground):
        r = M.repetition(lum, box, mode)
        row = dict(window=label, box=list(box), mode=mode, peak=r['peak'], lag=r['lag'], energy=r['energy'],
                   flag=M.flag('repetition', r['peak']))
        if ref_lum is not None:
            e0 = M.repetition(ref_lum, box, mode)['energy']
            row['energy_ratio'] = r['energy'] / max(e0, 1e-9)
            row['energy_flag'] = M.flag('repetition_energy', row['energy_ratio'])
        if w is not None:                              # the layer the window shows, and how it is projected
            x0, y0, x1, y1 = box
            k = int(np.argmax(w[:, y0:y1, x0:x1].mean((1, 2))))
            row['layer'] = names[k]
            row['projection'] = pal['layers'][k].get('projection', 'planar')
        reps.append(row)
    out['repetition'] = reps
    # section 6 reads repetition in ground crops: the worst over windows a planar layer holds (a wall's strata
    # bands repeat by design, and the box-projected layers are reported apart)
    ground_reps = [(r['peak'] or 0.0) for r in reps if r.get('projection', 'planar') == 'planar']
    steep_reps = [(r['peak'] or 0.0) for r in reps if r.get('projection', 'planar') != 'planar']
    if ground_reps:
        out['repetition_worst'] = max(ground_reps)
    if steep_reps:
        out['repetition_worst_steep'] = max(steep_reps)
    if photo is not None and pg is not None:
        H = photo.shape[0]
        rows = np.flatnonzero(pg.any(1))
        if rows.size:
            r = M.repetition(M.luma(photo), (0, int(rows.min()), 960, min(int(rows.max()) + 1, H)), '2d')
            out['photo_repetition'] = r['peak']
    lm = (src or {}).get('source') == 'layer map'
    out['seams'] = []
    if lm:                                             # only with the layer map: on planar ground holding the same
        planar = [i for i, L in enumerate(pal['layers']) if L.get('projection', 'planar') == 'planar']   # layers
        flat = ground & (w[planar].sum(0) > 0.5) if planar else ground       # on both sides (a wall's strata bands
        out['seams'] = seams(stack, rec, cam, img, flat, w)                  # and a landform's edge are no seam)
    if out['seams']:
        worst = max(out['seams'], key=lambda s: s['excess'])
        out['seam_worst_delta_e'] = worst['excess']
        out['seam_worst'] = dict(level=worst['level'], side_m=worst['side_m'], delta_e=worst['delta_e'],
                                 control=worst['control'], n=worst['n'])
        out['seam_verdict'] = M.verdict('seam_delta_e', worst['excess'])
    return out


# ------------------------------------------------------------------------------------------------ the audit ---

def _band(H_eye, pitch, lens, d0, d1, H=540, W=960):
    f = lens / 36.0 * W
    rows = []
    for d in (d1, d0):
        ang = math.asin(min(H_eye / d, 1.0))
        rows.append(H / 2 + f * math.tan(ang + math.radians(pitch)))
    return int(round(rows[0])), int(round(rows[1]))


def audit_windows():
    """The audit's repetition windows (its audit_repeat2.py and audit_walls.py), on the same images: (label, image,
    box, mode). Two rows read frames of the 11-12 videos the audit kept outside the repository: left out."""
    rv, out = 'surfacing/review', []
    eye = [('real_place floor v9', f'{rv}/real_place/floor_lischmaad_v9.png', 1.7, 6.0, 36.6),
           ('canyon approach_walk v5', f'{rv}/canyon/approach_walk_v5.png', 1.7, 2.98, 35.0),
           ('badlands prairie_walk v6', f'{rv}/badlands/prairie_walk_v6.png', 1.7, 10.56, 28.0),
           ('rolling_hills hilltop_walk v5', f'{rv}/rolling_hills/hilltop_walk_v5.png', 1.7, 0.76, 35.0),
           ('impact walk_floor v5', f'{rv}/impact_crater/walk_floor_v5.png', 1.7, 14.55, 24.0),
           ('meadow eye_swales', 'fluvial/review/renders/meadow/eye_swales.png', 1.7, -5.49, 35.0)]
    for label, img, h, pitch, lens in eye:
        for d0, d1 in BANDS_M:
            r0, r1 = _band(h, pitch, lens, d0, d1)
            if r1 - r0 < 3 or r0 < 0 or r1 > 540:
                continue
            out.append((f'{label} {d0}-{d1} m', img, (0, r0, 960, r1), 'rows'))
    for label, img, box in (('meadow drone near', 'fluvial/review/renders/meadow/drone.png', (0, 330, 480, 520)),
                            ('mesas aerial v6 floor near', f'{rv}/mesas_buttes/aerial_v6.png', (0, 380, 480, 540)),
                            ('impact rim_north v5 floor', f'{rv}/impact_crater/rim_north_v5.png', (260, 300, 700, 400)),
                            ('dunes review_final crest near slope', 'wind_sand/review_final/crest.png',
                             (0, 330, 330, 540)),
                            ('dunes review_final crest pan floor', 'wind_sand/review_final/crest.png',
                             (420, 230, 900, 300)),
                            ('canyon aerial v5 bench right', f'{rv}/canyon/aerial_down_canyon_v5.png',
                             (600, 380, 900, 520)),
                            ('real_place ridge v9 foreground slope', f'{rv}/real_place/ridge_schynige_v9.png',
                             (0, 380, 300, 540)),
                            ('real_place floor v9: Staubbach wall', f'{rv}/real_place/floor_lischmaad_v9.png',
                             (560, 40, 900, 250)),
                            ('canyon brink_down v5: far left walls', f'{rv}/canyon/brink_down_v5.png',
                             (0, 150, 330, 400)),
                            ('canyon brink_down v5: near right wall', f'{rv}/canyon/brink_down_v5.png',
                             (700, 60, 960, 400)),
                            ('impact rim_north v5: far walls', f'{rv}/impact_crater/rim_north_v5.png',
                             (100, 140, 860, 260)),
                            ('badlands prairie_walk v6: wall', f'{rv}/badlands/prairie_walk_v6.png',
                             (0, 150, 960, 380)),
                            ('alpine_valley aerial_axis v5: trough wall', f'{rv}/alpine_valley/aerial_axis_v5.png',
                             (260, 40, 800, 260)),
                            ('incised_meanders aerial_loops v3: walls',
                             f'{rv}/incised_meanders/aerial_loops_v3.png', (40, 160, 600, 400))):
        out.append((label, img, box, '2d'))
    return out


AUDIT_PHOTOS = {  # the photographs of the audit's repetition table: (file under out/, rows-mode bands, columns)
    'lauterbrunnen_01': ('glacial/photos/raw/lauterbrunnen_01.jpg', [(560, 600), (600, 640), (640, 680)], (0, 330)),
    'bl_01': ('layered_rock/photos/bl_01.jpg', [(560, 600), (600, 640), (640, 700)], (430, 960)),
    'tw_04': ('layered_rock/photos/tw_04.jpg', [(200, 260), (300, 360), (400, 460), (500, 560)], (0, 960)),
    'mv_02': ('layered_rock/photos/mv_02.jpg', [(480, 520), (520, 560), (560, 620)], (0, 960)),
    'namib_star_dunes_03': ('integration/photos/namib_star_dunes/namib_star_dunes_03.jpg',
                            [(560, 620), (620, 700)], (100, 520)),
    'ss_clifftop_east': ('coast/photos/ss_clifftop_east.jpg', [(450, 500), (500, 560), (560, 640)], (0, 300)),
    'palouse_hills_03': ('integration/photos/palouse_hills/palouse_hills_03.jpg',
                         [(330, 380), (380, 430), (430, 480)], (0, 440)),
    'meteor_crater_01_rim_north': ('volcanoes_craters/photos/meteor_crater/meteor_crater_01_rim_north.jpg',
                                   [(245, 270), (270, 295), (295, 320)], (250, 700)),
}
AUDIT_PHOTO_WALLS = {'lauterbrunnen_01': ('glacial/photos/raw/lauterbrunnen_01.jpg', (380, 40, 900, 330)),
                     'tw_03': ('layered_rock/photos/tw_03.jpg', (0, 300, 500, 650)),
                     'meteor_crater_01': ('volcanoes_craters/photos/meteor_crater/meteor_crater_01_rim_north.jpg',
                                          (60, 170, 900, 245)),
                     'bl_01': ('layered_rock/photos/bl_01.jpg', (0, 250, 960, 520)),
                     'gn_05': ('layered_rock/photos/gn_05.jpg', (0, 120, 480, 380))}


def _cmp(a, b, floor=0.005, rel_tol=0.10):
    """The judge's number a against the audit's b: dict(judge, audit, diff, within) - within 10 % of the audit's,
    or within `floor` where the audit's number is that small (a share of 0.001)."""
    if a is None or b is None:
        return dict(judge=a, audit=b, diff=None, within=None)
    d = float(a) - float(b)
    return dict(judge=round(float(a), 4), audit=float(b), diff=round(d, 4),
                within=bool(abs(d) <= max(rel_tol * abs(float(b)), floor)))


def audit(folder, before_src, recipes=None, tiles=None, old=None, log=print):
    """The audit's numbers measured again (see the module doc). tiles: tile_measures already made on the same
    terrains ({recipe: result}), reused; old: a previous audit result whose frame splats are reused (the slow part:
    --skip audit_frames)."""
    def load(name):
        p = os.path.join(folder, name)
        if not os.path.exists(p):
            return None
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    out = dict(coverage={}, contour_masks={}, repetition=[], frames={})
    cov, cc, rep, walls, frf = (load('coverage.json'), load('curv_contour.json'), load('repeat.json'),
                                load('repeat_walls.json'), load('frame_fraction.json'))
    stacks = {}

    def stack(recipe):
        if recipe not in stacks:
            stacks.clear()                                  # one terrain in memory at a time
            stacks[recipe] = load_terrain(recipe, before_src[recipe])
        return stacks[recipe]
    for recipe in sorted(before_src):
        if recipe == 'note' or (recipes and recipe not in recipes):
            continue
        a = (cov or {}).get(recipe)
        m = (cc or {}).get(recipe)
        if not a and not m:
            continue
        tm = (tiles or {}).get(recipe)
        if not tm or 'error' in tm:
            log(f'[baseline] the audit, {recipe}: the tile')
            tm = tile_measures(stack(recipe), log=log)
        if a and 'layers' in a:
            rows = [dict(name='pure_total', **_cmp(tm['pure_total'], a['pure_total']))]
            mine = {L['name']: L for L in tm['layers']}
            for la in a['layers']:                     # matched by name: a palette can gain or lose a layer
                lj = mine.get(la['name'])
                if lj is None:
                    rows.append(dict(name=f"{la['name']}: not a layer of the judge's palette ({tm['palette']})",
                                     judge=None, audit=la['share'], diff=None, within=None))
                    continue
                for k, kj in (('share', 'share'), ('pure', 'pure'), ('largest', 'largest'),
                              ('contour', 'height_line')):
                    rows.append(dict(name=f"{la['name']} {k}", **_cmp(lj[kj], la[k])))
            out['coverage'][recipe] = rows
        if m:
            out['contour_masks'][recipe] = [dict(name=f'{k} steep', **_cmp(tm['mask_height_line_steep'].get(k), val))
                                            for k, val in (m.get('steep') or {}).items()]
            out['contour_masks'][recipe].append(dict(name='steep_share',
                                                     **_cmp(tm['steep_share'], m.get('steep_share'))))
    # repetition: the same windows of the same pictures
    want = {r['label']: r for r in (rep or []) + (walls or [])}
    for label, img, box, mode in audit_windows():
        p = os.path.join(OUT_ROOT, img.replace('/', os.sep))
        band = next((f'{d0}-{d1} m' for d0, d1 in BANDS_M if label.endswith(f' {d0}-{d1} m')), None)
        if band:                                       # the audit's eye rows name the base scan between view and band
            pre = label[:-len(band)].strip()
            key = next((k for k in want if k.startswith(pre) and k.endswith(band)), None)
        else:
            key = next((k for k in want if k.startswith(label)), None)
        if key is None or not os.path.exists(p):
            continue
        r = M.repetition(M.luma(M.load_rgb(p)), box, mode)
        out['repetition'].append(dict(name=key, mode=mode, box=list(box), lag=r['lag'],
                                      **_cmp(r['peak'], want[key]['peak'])))
    for name, (f, bands, (xa, xb)) in AUDIT_PHOTOS.items():
        key = f'PHOTO {name}'
        p = os.path.join(OUT_ROOT, f.replace('/', os.sep))
        if key not in want or not os.path.exists(p):
            continue
        L = M.luma(M.load_rgb(p, width=960))
        worst = None
        for a0, a1 in bands:
            r = M.repetition(L, (xa, a0, xb, a1), 'rows')
            if worst is None or (r['peak'] or 0) > (worst['peak'] or 0):
                worst = dict(r, box=[xa, a0, xb, a1])
        r2 = M.repetition(L, (xa, bands[0][0], xb, bands[-1][1]), '2d')
        out['repetition'].append(dict(name=key + ' (rows, worst band)', mode='rows', box=worst['box'],
                                      lag=worst['lag'], **_cmp(worst['peak'], want[key]['peak'])))
        out['repetition'].append(dict(name=key + ' (2-D)', mode='2d', lag=r2['lag'],
                                      **_cmp(r2['peak'], want[key].get('peak2d'))))
    for name, (f, box) in AUDIT_PHOTO_WALLS.items():
        key = next((k for k in want if k.startswith(f'PHOTO {name}:')), None)      # the walls' rows ('PHOTO x: ...')
        p = os.path.join(OUT_ROOT, f.replace('/', os.sep))
        if key is None or not os.path.exists(p):
            continue
        r = M.repetition(M.luma(M.load_rgb(p, width=960)), box, '2d')
        out['repetition'].append(dict(name=key, mode='2d', box=list(box), lag=r['lag'],
                                      **_cmp(r['peak'], want[key]['peak'])))
    # frame shares: the audit's splat (the camera aimed straight at the aim, as frame_fraction.py placed it)
    if old and old.get('frames'):
        out['frames'] = old['frames']
        frf = {}
    for spec, a in (frf or {}).items():
        recipe, view = spec.split(':')
        if (recipes and recipe not in recipes) or recipe not in before_src or 'shares' not in a:
            continue
        rv = os.path.join(OUT_ROOT, 'surfacing', 'review', recipe)
        rp = os.path.join(rv, f"{recipe}_{a['record'].rsplit('_', 1)[1]}_record.json")
        if not os.path.exists(rp):
            continue
        with open(rp, encoding='utf-8') as f:
            r = json.load(f)[a['record']]
        log(f'[baseline] the audit, {spec}: the layers splatted into the camera')
        st = stack(recipe)
        pal = LY.palette(st)
        cam = V.Camera.from_aim(r['camera'], r['aim'], (0.5, 0.5), r['lens'], size=(240, 135))
        w, seen = LY.frame_splat(st, pal, cam, size=(240, 135))
        top, topw = w.argmax(0), w.max(0)
        rows = []
        for i, L in enumerate(pal['layers']):
            share = float(w[i][seen].mean()) if seen.any() else None
            dom = float(((top == i) & seen & (topw > 0.9)).sum() / max(int(seen.sum()), 1))
            rows.append(dict(name=f"{L['name']} share", **_cmp(share, a['shares'].get(L['name']))))
            rows.append(dict(name=f"{L['name']} at 90 %", **_cmp(dom, a['dominant_90'].get(L['name']))))
        rows.append(dict(name='ground in the frame', **_cmp(float(seen.mean()), a.get('ground_share'))))
        out['frames'][spec] = rows
    allrows = [r for v in out['coverage'].values() for r in v] + \
              [r for v in out['contour_masks'].values() for r in v] + out['repetition'] + \
              [r for v in out['frames'].values() for r in v]
    judged = [r for r in allrows if r['within'] is not None]
    out['summary'] = dict(numbers=len(judged), within=sum(r['within'] for r in judged),
                          outside=[f"{r['name']}: {r['judge']} against {r['audit']}" for r in judged
                                   if not r['within']])
    return out


# ------------------------------------------------------------------------------------------------- the report ---

def file_name(state):
    """A state's name as a file name ('surface_look:base' -> 'surface_look-base': no colon on Windows)."""
    return str(state).replace(':', '-').replace('/', '-').replace('\\', '-')


def _f(x, k=3):
    return '-' if x is None else (f'{x:.{k}f}' if isinstance(x, float) else str(x))


def markdown(res):
    L = [f"# The surfacing judge's numbers: state `{res['state']}`", '',
         f"Measured {res['when']} by `blender/tests/terrain/surfacing_judge/baseline.py`. The look measures are "
         "diagnostics beside the boards, each read against the place's reference (SURFACING_DESIGN.md section 6); "
         "the board read is the pass. A flag (!) marks a value to name in the read. Seams gate.", '']
    if res.get('tile'):
        L += ['## The tile (the main level, the palette evaluated on the masks)', '',
              'Read against the state before and random (0.64); no orthophoto reference yet.', '',
              '| recipe | palette | pure | largest region (layer) | height-line all | on slopes > 25 deg |',
              '|---|---|---|---|---|---|']
        for r, t in res['tile'].items():
            if 'error' in t:
                L.append(f"| {r} | error: {t['error']} | | | | |")
                continue
            L.append(f"| {r} | {t['palette']} | {_f(t['pure_total'])} | {_f(t['largest'])} ({t['largest_layer']}) | "
                     f"{_f(t['height_line_all'])} | {_f(t['height_line_steep'])} |")
        L.append('')

    def fl(x):
        return ' !' if x else ''
    if res.get('frames'):
        L += ['## The frames', '',
              f"Repetition energy against `{res.get('energy_reference')}`'s render of the same camera.", '',
              '| view | layers from | largest region / the photograph\'s | repetition, ground (energy) | '
              'repetition, walls | colour dE matched (raw) | spread L | seam dE over its control | frame s |',
              '|---|---|---|---|---|---|---|---|---|']
        for k, f in res['frames'].items():
            if f is None or 'error' in f:
                continue
            om = f.get('one_material') or {}
            col = f.get('colour') or {}
            src = (f.get('layers_from') or {}).get('source', '-')
            gr = [r for r in f.get('repetition') or [] if r.get('projection', 'planar') == 'planar']
            worst = max(gr, key=lambda r: r['peak'] or 0.0) if gr else {}
            rep = (f"{_f(worst.get('peak'))}{fl(worst.get('flag'))} ({_f(worst.get('energy_ratio'), 2)}"
                   f"{fl(worst.get('energy_flag'))})") if worst else '-'
            L.append(f"| {k} | {src} | {_f(om.get('largest'))} / {_f(om.get('photo_largest'))}{fl(om.get('flag'))} | "
                     f"{rep} | {_f(f.get('repetition_worst_steep'))} | {_f(col.get('delta_e'), 1)} "
                     f"({_f(col.get('delta_e_raw'), 1)}) | {_f(col.get('spread_ratio_L'), 2)} | "
                     f"{_f(f.get('seam_worst_delta_e'), 2)}{' FAIL' if f.get('seam_verdict') == 'fail' else ''} | "
                     f"{_f((f.get('cost') or {}).get('frame_s'), 2)} |")
        L.append('')
    a = res.get('audit')
    if a:
        s = a['summary']
        L += ["## Against the audit's numbers (11-13)", '',
              f"{s['within']} of {s['numbers']} numbers within 10 % of the audit's (or within 0.005 where the "
              "audit's is that small).", '']
        if s['outside']:
            L += ['Outside:', ''] + [f'- {x}' for x in s['outside']] + ['']
    return '\n'.join(L) + '\n'


def main(argv):
    def opt(k, d=None):
        return argv[argv.index(k) + 1] if k in argv else d
    state = opt('--state', 'before')
    ref_state = opt('--ref-state', 'before' if os.path.isdir(os.path.join(S.STATES, 'before')) else None)
    skip = set((opt('--skip') or '').split(',')) - {''}
    only = set(opt('--recipes').split(',')) if opt('--recipes') else None
    only_views = set(opt('--views').split(',')) if opt('--views') else None
    tpath = opt('--terrains')
    if not tpath:
        cand = os.path.join(OUT, f'terrains_{state}.json')
        tpath = cand if os.path.exists(cand) else None
    src = terrain_sources(tpath)
    plan = V.load(opt('--plan'))
    res = dict(state=state, when=time.strftime('%Y-%m-%d %H:%M'), terrains=tpath and rel(tpath), tile={},
               frames={}, energy_reference=ref_state)
    out_json = os.path.join(OUT, f'baseline_{file_name(state)}.json')
    if os.path.exists(out_json):                      # a partial run (--recipes) adds to what is there
        with open(out_json, encoding='utf-8') as f:
            old = json.load(f)
        res['tile'].update(old.get('tile') or {})
        res['frames'].update(old.get('frames') or {})
        if old.get('audit'):
            res['audit'] = old['audit']
    for recipe, rec in plan.items():
        if only and recipe not in only:
            continue
        st = None
        if recipe in src:
            try:
                st = load_terrain(recipe, src[recipe])
            except Exception as e:                    # noqa: BLE001 - reported, the run goes on
                print(f'[baseline] {recipe}: its terrain does not load: {type(e).__name__}: {e}')
        if 'tile' not in skip and st is not None:
            print(f'[baseline] {recipe}: the tile', flush=True)
            try:
                res['tile'][recipe] = tile_measures(st)
            except Exception as e:                    # noqa: BLE001
                import traceback
                traceback.print_exc()
                res['tile'][recipe] = dict(error=f'{type(e).__name__}: {e}')
        if 'frames' not in skip:
            pal = LY.palette(st if st is not None else recipe)
            for v in rec['views']:
                if only_views and v['name'] not in only_views:
                    continue
                print(f"[baseline] {recipe}/{v['name']}: the frame", flush=True)
                try:
                    vst = st
                    tf = (S.record(recipe, v['name'], state) or {}).get('terrain')
                    snap = opt('--snap')
                    if snap and isinstance(tf, str) and tf.endswith('.npz') and os.path.exists(os.path.join(snap, tf)):
                        from surfacing_judge import terrain_data as TD
                        vst = TD.load(os.path.join(snap, tf), recipe=recipe, heroes=True)   # the render's own
                    res['frames'][f"{recipe}/{v['name']}"] = frame_measures(recipe, v, state, vst, pal, ref_state,
                                                                            splat='splat' not in skip)
                    del vst
                except Exception as e:                # noqa: BLE001
                    import traceback
                    traceback.print_exc()
                    res['frames'][f"{recipe}/{v['name']}"] = dict(error=f'{type(e).__name__}: {e}')
        del st
        with open(out_json, 'w', encoding='utf-8') as f:
            json.dump(res, f, indent=1, default=float)
    if opt('--audit') and 'audit' not in skip:
        res['audit'] = audit(opt('--audit'), src, only, tiles=res['tile'],
                             old=res.get('audit') if 'audit_frames' in skip else None)
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(res, f, indent=1, default=float)
    with open(os.path.join(OUT, f'baseline_{file_name(state)}.md'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(markdown(res))
    print('[baseline] wrote', rel(out_json))
    if res.get('audit'):
        s = res['audit']['summary']
        print(f"[baseline] against the audit: {s['within']} of {s['numbers']} within 10 %")
        for x in s['outside']:
            print('   outside:', x)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

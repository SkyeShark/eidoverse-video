"""W2d: the photographs' SIDE-view skin lines on the clay (the OUTER limits that carve the wolf's body volume,
species/wolf_body.py, and the lines its silhouette errors are measured against).

THE SOURCES (work/bestiary/research/wolf_work/data, traced by WOLF_BODY_PHOTOS' study and the W2 rounds):
  w01  summer (July), level telephoto, square stance: the skin estimates (dorsal, underline, throat and chest, the
       caudal thigh) and the leg edges over its 9-18 mm summer coat (the forelegs' edges are the near and far legs
       together, so they are a union: an outer limit still)
  w02, w03, w05  winter: the skin estimates of the back and the underline (+-15 mm; w03's throat follows its stretched
       neck and its legs stand staggered: not used)
  r05  a coyote with severe mange (Año Nuevo), trotting: its traced skin lines (the chest's front, the planted foreleg;
       not its back, a trotting coyote's), in its chest depth (a coyote's ratios, not its sizes)
COAT REMOVED: the skin estimates are already under the coat (their tracer's per-region depths, WOLF_BODY_PHOTOS §2);
w01's leg edges are over the summer leg coat, 5 mm a side [E] (the plan's coat table gives the winter leg coat as short
as the muzzle's; the summer coat 0.35-0.4 of winter, §3.5).
THE MAPPING: side_xform (as w02_clay's overlays): the ground through the near pads on y 0, the withers height at the
skin -> the clay's WH, the withers on the clay's withers. The legs then per height (leg_map): the photo's leg column
(the middle of its two edges) onto the composed program's own leg column, the photo's heights stretched piecewise
through its landmarks (the elbow's point, the carpus; the hock's point) onto the clay's, so a leg's WIDTH profile is
applied where the clay's leg stands (the stances differ: w01's forepaw lands 65 mm ahead of the clay's).
Each line: the polyline (z, y mm), the side its outside lies on, its tolerance (the skin estimate's: summer 6, winter
12, r05 10 mm), the x range it holds over, its reach (mm on either side), trims at its ends (the junctions with the
neck, the limbs and the tail are left to the program), and which levels and limb it limits.
"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
DATA = os.path.join(REPO, 'work', 'bestiary', 'research', 'wolf_work', 'data')
LEG_COAT = 5.0          # mm, w01's summer leg coat a side [E]

# (photo, line, outside direction (z, y), tolerance mm, trims (front-end mm, back-end mm), keep (z or y window, mm),
#  x range mm, reach mm, levels, limb)
# the windows (W2d b1: a line's shadow must hold only over the stretch it traces): 'back' to 30 mm past the withers (the
# neck's carriage differs per photo), 'belly' between the stifle and the elbow (an underline's front ran across the clay's
# forelimb and carved its top: the photos' elbows stand elsewhere; the chest floor near the elbow is the stance gate's),
# 'chest' the chest's front between y 400 and CHEST_TOP mm (the throat follows the head's carriage; under 400 mm the line
# ran in front of the forelimb).
# W2d check: CHEST_TOP 590 (was 520). Ending at 520, the window's taper released the limit over y 480-520 while the
# composed chest stood 9-19 mm ahead of w01's line at y 490-560: the carved front (pinned at the line, y 455-485) met the
# released bulge in a ledge, the horizontal band (a slot with a lip) across the chest's front in every front view
# (check_w2d/out/look_base_chest.png). Over 520-590 the line is still the chest's front under the neck's base (the
# carriage acts above C7, y 584 at the bind) and the clay meets it by y 590 (+2 mm): the limit now ends where the clay
# already agrees. 'belly' lines end in front with a 160 mm ramp (wolf_body.line_field; BELLY_FRONT_RAMP)
CHEST_TOP = 590.0
BELLY_FRONT_RAMP = 160.0
CHEST_SLACK = (35.0, 0.6)        # W2f: the chest lines' limit leans away 0.6 mm per mm past |x| 35 mm (line_field slack)
TRUNK_LINES = (
    ('w01', 'dorsal_skin', (0.0, 1.0), 6.0, None, 'back', (0.0, 200.0), 30.0),
    ('w01', 'underline_skin', (0.0, -1.0), 8.0, (0.0, 25.0), 'belly', (0.0, 200.0), 30.0),
    ('w01', 'throat_chest_skin', (1.0, -0.3), 6.0, None, 'chest', (0.0, 200.0), 30.0),
    ('w01', 'hind_near_caudal_skin', (-1.0, 0.0), 6.0, (10.0, 20.0), None, (0.0, 200.0), 30.0),
    # the winter skin estimates at their stated uncertainty, +-15 mm (WOLF_BODY_PHOTOS §2); r05's back is a trotting
    # coyote's in its chest depth (W2d b3: its line carved the croup 10-20 mm under the croup mass, a clash the inner
    # limit won with a crease): its chest's front and its foreleg only
    ('w02', 'dorsal_skin', (0.0, 1.0), 15.0, None, 'back', (0.0, 200.0), 30.0),
    ('w02', 'underline_skin', (0.0, -1.0), 15.0, (0.0, 25.0), 'belly', (0.0, 200.0), 30.0),
    ('w03', 'dorsal_skin', (0.0, 1.0), 15.0, None, 'back', (0.0, 200.0), 30.0),
    ('w03', 'underline_skin', (0.0, -1.0), 15.0, (0.0, 25.0), 'belly', (0.0, 200.0), 30.0),
    ('w05', 'dorsal_skin', (0.0, 1.0), 15.0, None, 'back', (0.0, 200.0), 30.0),
    ('w05', 'underline_skin', (0.0, -1.0), 15.0, (0.0, 25.0), 'belly', (0.0, 200.0), 30.0),
    ('r05', 'throat_chest_skin', (1.0, -0.3), 10.0, None, 'chest', (0.0, 200.0), 30.0),
)
# the photos whose lines CARVE (the lead's W2d list: w01 / w03 / w10 / w11 and the wet / mange side views; w10 / w11
# are heads); w02's and w05's winter estimates are MEASURED only (their errors reported, no limit): W2d b4's w05 back
# ran 15 / 24 / 38 mm under the composed loin at z 60 / 40 / 20 mm and ended inside the croup (z 11), its carve the
# croup's slot
CARVE = ('w01', 'w03', 'r05')
# the legs: (photo, line, outside (z, y), tolerance, the coat a side, limb)
LEG_LINES = (
    ('w01', 'fore_near_cranial', (1.0, 0.0), 6.0, LEG_COAT, 'fore'),
    ('w01', 'fore_near_caudal', (-1.0, 0.0), 6.0, LEG_COAT, 'fore'),
    ('w01', 'hind_near_cranial', (1.0, 0.0), 6.0, LEG_COAT, 'hind'),
    ('w01', 'hind_near_caudal', (-1.0, 0.0), 6.0, LEG_COAT, 'hind'),
    ('r05', 'fore_near_cranial_skin', (1.0, 0.0), 10.0, 0.0, 'fore'),
    ('r05', 'fore_near_caudal_skin', (-1.0, 0.0), 10.0, 0.0, 'fore'),
)


def load(pid):
    if pid.startswith('r'):
        with open(os.path.join(DATA, 'src', f'ref_{pid}.json'), encoding='utf-8') as f:
            return json.load(f), None
    with open(os.path.join(DATA, f'lm_{pid}.json'), encoding='utf-8') as f:
        L = json.load(f)
    with open(os.path.join(DATA, f'res_{pid}.json'), encoding='utf-8') as f:
        R = json.load(f)
    return L, R


def side_xform(L, R, WH, z_withers):
    """photo px -> the clay's (z, y) mm (w02_clay.side_xform): the ground through the near pads on y 0, WH_px -> WH,
    the withers on the clay's"""
    Pt = L['points']
    o = np.array(Pt['fore_pad'], float)
    g = o - np.array(Pt['hind_pad'], float)
    g /= np.linalg.norm(g)
    n = np.array([g[1], -g[0]])
    n = n if n[1] < 0 else -n
    s = WH / R['rows']['WH_px']['value']
    xw = (np.array(Pt['withers_skin'], float) - o) @ g
    z0 = z_withers - xw * s
    return (lambda Q: np.stack([z0 + ((np.asarray(Q, float) - o) @ g) * s, ((np.asarray(Q, float) - o) @ n) * s], -1)), s


def r05_xform(L, clay_cd, z_withers, y_withers):
    """the mange coyote r05 by its chest depth (the withers' skin to the chest floor under it) on the clay's, its withers
    on the clay's (w02_clay's T5)"""
    p = L['points']
    cd_px = float(np.hypot(*np.subtract(p['chest_floor'], p['withers'])))
    s = clay_cd / cd_px
    fs = -1.0 if L['facing'] == 'left' else 1.0
    return (lambda Q: np.stack([z_withers + fs * (np.asarray(Q, float)[..., 0] - p['withers'][0]) * s,
                                y_withers - (np.asarray(Q, float)[..., 1] - p['withers'][1]) * s], -1)), s


def resample(P, step=3.0):
    P = np.asarray(P, float)
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    if s[-1] < step:
        return P
    t = np.arange(0.0, s[-1] + 1e-9, step)
    return np.column_stack([np.interp(t, s, P[:, 0]), np.interp(t, s, P[:, 1])])


def trim(P, a, b):
    P = resample(P, 1.0)
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    m = (s >= a) & (s <= s[-1] - b)
    return P[m]


def out_sign(P, od):
    """+1 if the outside direction od lies on the left of the polyline's direction at its middle, else -1"""
    i = max(0, min(len(P) - 2, len(P) // 2))
    ab = P[i + 1] - P[i]
    nrm = np.array([-ab[1], ab[0]])
    return 1.0 if float(np.dot(nrm, od)) > 0 else -1.0


def program_column(prog, x_rng, z_rng, y_rng, res=1.0):
    """the composed program's leg column in the side view: per height y (mm) the middle of the solid's z extent within
    the window (min over x in x_rng); returns (y, z_mid, z_lo, z_hi) arrays"""
    zs = np.arange(z_rng[0], z_rng[1] + 1e-9, res)
    ys = np.arange(y_rng[0], y_rng[1] + 1e-9, res)
    xs = np.arange(x_rng[0], x_rng[1] + 1e-9, 2.0)
    Z, Y, X = np.meshgrid(zs, ys, xs, indexing='ij')
    f = prog.eval(np.stack([X, Y, Z], -1).reshape(-1, 3) * 1.0e-3).reshape(Z.shape).min(axis=2)
    out = []
    for j, y in enumerate(ys):
        m = f[:, j] < 0
        if m.any():
            zz = zs[m]
            out.append((y, 0.5 * (zz.min() + zz.max()), zz.min(), zz.max()))
    return np.array(out)


def photo_column(cr, ca, ys):
    """a photo leg's column: the middle of its cranial and caudal edges at heights ys (each edge's z by height)"""
    def z_at(P, y):
        P = P[np.argsort(P[:, 1])]
        return np.interp(y, P[:, 1], P[:, 0])
    return 0.5 * (z_at(cr, ys) + z_at(ca, ys))


def side_silhouettes(spec, chain, prog, log=print):
    """the side lines (module docstring) as dicts for wolf_body: name, zy (the limit's stretch), zy_full (the measured
    stretch), out_sign, out_sign_err, tol, x, reach, level, limb; plus err_lines (every line, for the errors)"""
    P = {k: np.asarray(v, float) * 1000.0 for k, v in chain['pos'].items()}
    WH = chain['WH'] * 1000.0
    zw = chain['withers_z'] * 1000.0
    # the clay's chest depth under the withers (r05's scale): the composed program's vertical run there
    ys = np.arange(900.0, 0.0, -0.5)
    f = prog.eval(np.column_stack([np.zeros_like(ys), ys, np.full_like(ys, zw)]) * 1.0e-3)
    ins = np.nonzero(f < 0)[0]
    y_top, y_floor = ys[ins[0]], ys[ins[-1]]
    lines, err_lines = [], []
    xf = {}
    for pid in ('w01', 'w02', 'w03', 'w05', 'r05'):
        L, R = load(pid)
        if pid == 'r05':
            xf[pid] = (r05_xform(L, y_top - y_floor, zw, y_top)[0], L)
        else:
            xf[pid] = (side_xform(L, R, WH, zw)[0], L)
    for pid, nm, od, tol, trims, keep, xr, reach in TRUNK_LINES:
        T, L = xf[pid]
        if nm not in L['polylines']:
            continue
        Pf = resample(T(np.asarray(L['polylines'][nm], float)), 1.0)
        Pl = Pf.copy()
        if keep == 'back':
            # 30 mm past the withers (W2d b5: ending AT the withers, the line's end taper released the withers' top
            # 8-13 mm over the measured back within 20 mm, a bar across the withers seen from the top; the neck's
            # carriage, which differs per photo, begins in front of it)
            Pl = Pl[Pl[:, 0] < zw + 30.0]
            # its caudal end is the photo's tail root, where the skin goes on into the tail: carried 25 mm on along
            # its last 10 mm's direction, so the end taper opens behind the root (W2d b6: opening at the root, the
            # composed croup's rear stood up to 10 mm over the line there, a ledge round the tail's root)
            if len(Pl) > 12:
                o_ = np.argsort(Pl[:, 0])
                Pl = Pl[o_]
                dv = Pl[0] - Pl[10]
                dv = dv / max(np.linalg.norm(dv), 1e-9)
                Pl = np.vstack([Pl[0] + np.outer(np.arange(25.0, 0.0, -1.0), dv), Pl])
        elif keep == 'belly':
            Pl = Pl[(Pl[:, 0] > P['stifle_L'][2] + 60.0) & (Pl[:, 0] < P['elbow_L'][2] - 120.0)]
        elif keep == 'chest':
            Pl = Pl[(Pl[:, 1] > 400.0) & (Pl[:, 1] < CHEST_TOP)]
        if trims is not None and len(Pl) > 2:
            Pl = trim(Pl, *trims)
        if len(Pl) < 3:
            continue
        rec = dict(name=f'{pid} {nm}', zy=resample(Pl, 3.0), zy_full=Pl, tol=tol, x=xr, reach=reach, level='body',
                   limb=None, out_sign_err=1.0)
        if keep == 'belly':
            # the front end (toward the elbow, the larger z) ramps over BELLY_FRONT_RAMP: wolf_body.line_field
            front_first = rec['zy'][0][0] > rec['zy'][-1][0]
            rec['ramp'] = (BELLY_FRONT_RAMP, None) if front_first else (None, BELLY_FRONT_RAMP)
        if keep == 'chest':
            # W2f: the chest's front lines lean away past CHEST_SLACK's |x| (wolf_body.line_field): the silhouette is the
            # keel's; held at every x they cut the lateral chest (a crease above the forelegs)
            rec['slack'] = CHEST_SLACK
        rec['out_sign'] = out_sign(rec['zy'], np.asarray(od, float))
        if pid in CARVE:
            lines.append(rec)
        err_lines.append(rec)
    # ---- the legs: each photo's edges re-stood on the clay's leg column, its heights stretched through its landmarks
    cols = {'fore': program_column(prog, (P['elbow_L'][0] - 45.0, P['elbow_L'][0] + 45.0),
                                   (P['carpus_L'][2] - 120.0, P['carpus_L'][2] + 120.0), (40.0, P['elbow_L'][1] + 5.0)),
            'hind': program_column(prog, (P['hock_L'][0] - 45.0, P['hock_L'][0] + 45.0),
                                   (P['hock_L'][2] - 120.0, P['hock_L'][2] + 160.0), (40.0, P['stifle_L'][1] - 10.0))}
    clay_lm = {'fore': ((P['elbow_L'][1] - 8.0), P['carpus_L'][1]),                 # the elbow's point, the carpus
               'hind': (P['stifle_L'][1] - 25.0, P['hock_L'][1] + 30.0)}           # the tibial crest, the hock's point
    by_photo = {}
    for pid, nm, od, tol, coat, limb in LEG_LINES:
        by_photo.setdefault((pid, limb), []).append((nm, od, tol, coat))
    for (pid, limb), rows in by_photo.items():
        T, L = xf[pid]
        Pt = L['points']
        if pid == 'r05':
            lm_hi, lm_lo = T(np.asarray(Pt['elbow_point'], float))[1], T(np.asarray(Pt['carpus'], float))[1]
        elif limb == 'fore':
            lm_hi, lm_lo = T(np.asarray(Pt['elbow'], float))[1], T(np.asarray(Pt['carpus'], float))[1]
        else:
            lm_hi, lm_lo = T(np.asarray(Pt['stifle'], float))[1], T(np.asarray(Pt['hock'], float))[1]
        c_hi, c_lo = clay_lm[limb]
        vmap = lambda y: np.interp(y, [0.0, lm_lo, lm_hi, lm_hi + 400.0], [0.0, c_lo, c_hi, c_hi + 400.0])
        edges = {nm: T(np.asarray(L['polylines'][nm], float)) for nm, _, _, _ in rows if nm in L['polylines']}
        names = sorted(edges)
        if len(names) < 2:
            continue
        cr = edges[[n for n in names if 'cranial' in n][0]]
        ca = edges[[n for n in names if 'caudal' in n][0]]
        col = cols[limb]
        for nm, od, tol, coat in rows:
            if nm not in edges:
                continue
            E = resample(edges[nm], 1.0)
            ylo_ = max(cr[:, 1].min(), ca[:, 1].min())
            yhi_ = min(cr[:, 1].max(), ca[:, 1].max())
            E = E[(E[:, 1] >= ylo_) & (E[:, 1] <= yhi_)]
            if len(E) < 3:
                continue
            zc_p = photo_column(cr, ca, E[:, 1])
            yv = vmap(E[:, 1])
            zc_c = np.interp(yv, col[:, 0], col[:, 1])
            off = E[:, 0] - zc_p
            off = np.sign(off) * np.maximum(np.abs(off) - coat, 0.0)
            Q = np.column_stack([zc_c + off, yv])
            # held between the paw and 5 mm under the photo's top landmark (the elbow's point, the tibial crest): above
            # it the height map extrapolates and the clay's column ends (W2d b2: w01's thigh line landed on the stifle)
            Q = Q[(Q[:, 1] > 45.0) & (Q[:, 1] < min(c_hi - 5.0, col[:, 0].max() - 5.0))]
            if len(Q) < 3:
                continue
            rec = dict(name=f'{pid} {nm}', zy=resample(Q, 2.0), zy_full=Q, tol=tol,
                       x=(P[f'{"elbow" if limb == "fore" else "hock"}_L'][0] - 50.0,
                          P[f'{"elbow" if limb == "fore" else "hock"}_L'][0] + 50.0), reach=20.0,
                       level='all', limb=limb, out_sign_err=1.0)
            rec['out_sign'] = out_sign(rec['zy'], np.asarray(od, float))
            lines.append(rec)
            err_lines.append(rec)
    log(f'[body] side lines: {len(lines)} ({", ".join(ln["name"] for ln in lines)}); the clay\'s chest depth under the '
        f'withers {y_top - y_floor:.0f} mm (r05\'s scale)')
    return dict(lines=lines, err_lines=err_lines, chest=(y_top, y_floor))

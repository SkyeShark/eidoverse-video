"""W2h (the lead's call 1, THE HEAD SKULL-FIRST): THE SKIN over the wolf skull (canid_skull.py), the forensic
reconstruction's method: the skull, the masses that fill its fossae, and the soft tissue at depths read at landmarks and
interpolated smoothly over the surface. It replaces the visual hull of the furred silhouettes as the head's base volume
(canid_hull.head_volume, canid.HEAD method 'skull'); the furred silhouettes stay OUTER limits only.

THE FRAME: canid's palate frame, millimetres (d back from the nose tip, q dorsal, x lateral), on the head's own grid.

1. THE DEEP FORM: the skull (canid_skull.Skull.field), the SPEC's eyeballs, and per d-slice the convex hull of the bone's
   section within each muscle's reach, which no single bone surface carries:
     TEMPORALIS  behind the orbital ligament (d >= DEEP temporalis), the section above the arch's ventral edge: the
                 temporal fossa filled from the sagittal crest to the arch (the muscle's attachment lines bound it)
     MASSETER    from the zygomatic root back to the mandible's angle, the section under the arch's dorsal edge: from the
                 arch's ventral border to the mandible's lateral face
     LIPS        along the muzzle, the section under the upper alveolar margin (+ DEEP lips q_add): the lips and the cheek
                 over the teeth, the chin over the incisors, the floor between the mandible's bodies
     NOSE        (W2h k7) the nasal cartilages from the leather's back to the nasal bones: the upper jaw's section and a
                 half-ellipse up to the profile photos' dorsal line less the skin (DEEP nose)
   Each hull is an exact 2D signed distance per slice (its polygon, not a voxel mask), faded in and out along d, smoothed
   along d, unioned with the bone and the globes; the eye's region keeps no hull (the brow, the globe and the arch each
   carry their own depth, so the eye sits in its orbit instead of under a bridge from the brow to the arch).
2. THE TISSUE DEPTHS (DEPTHS): (name, the landmark on the deep form (d, q, |x|) mm, depth mm, its reach sigma mm, the
   source): interpolated over the deep form's surface by a normalised Gaussian of each surface point's distance to the
   landmarks (the foot point of the deep form's distance field), BASE depth where no landmark reaches.
3. THE SKIN: the deep form offset by the interpolated depth (its distance less the depth at its foot point), redistanced,
   blurred (the offset's concave creases where the offsets of two parts meet), redistanced. W2i (the lead's call 1:
   "the skin's smoothing radius grows with the local tissue depth (at least 2.5 mm, about half the depth)"): the blur's
   sigma at each voxel max(SMOOTH[0], SMOOTH[1] x the depth there), the depth field low-passed SMOOTH_DEPTH mm first,
   the field blended between its copies blurred at SMOOTH_SIGMAS (piecewise linear in sigma): thin skin over bone keeps
   the bone's forms at 2.5 mm, the 10-12 mm lips and pads soften over 5-6 mm (W2h blurred 2.5 mm everywhere).

W2i (the lead's call 4: "no lobes and no lump; the upper lip one continuous form along the side ..., the whisker-pad
width coming from that form and the sourced tissue, never a mass tuned to a width"): DEPTHS' whisker_pad_caudal (27 mm
at a 6 mm reach, tuned to r03's width at d 40) removed; the lower lip back to its sourced depth (W2h thinned it to 3.5 to
hide the mandible standing 10 mm deep; the bone is fixed now, canid_skull SHAPE jaw_close and chin_tissue); the lips'
hull bulged less (its floor between the mandible's bodies sagged 2-3 mm under them).
"""
import numpy as np

from ..hullflow import Grid, cache_key, cached, redistance
from . import canid_skull as SK

VERSION = 'w2p-k3'

# ============================================================================================ the deep form
# d ranges (mm): (fade-in start, full, full end, fade-out end); the hull's q limit from the skull's measured lines (W2p:
# the arch's edges as the skull uses them, canid_skull ARCH_DORSAL_W2P / ARCH_VENTRAL_W2P: MWNH 358's over the orbit)
DEEP = dict(
    temporalis=dict(d=(138.0, 156.0, 248.0, 262.0)),          # the orbital ligament (141-145) to the nuchal crest
    masseter=dict(d=(94.0, 122.0, 206.0, 218.0)),             # the zygomatic root (116 [P]) to the angle (201 [P])
    lips=dict(d=(-20.0, -10.0, 98.0, 124.0), q_add=4.0,       # the muzzle to the commissure (d ~97, LIP_LINE); the
              bulge=(0.04, 2.5)),                              # fades long and overlapping (10 mm printed a step);
                                                              # W2i: bulged less (the floor between the mandible's
                                                              # bodies hung 2-3 mm under them at 0.08 / 7)
    smooth_d=6.0,                                              # each hull's 2D field smoothed along d (mm; at 1.5 the
                                                               # slices' hull changes printed vertical streaks; W2i 6:
                                                               # the ripple gate's 0.3 mm over a 20 mm running mean)
    # each hull edge BULGED outward as a parabola of sagitta bulge x its length (capped at bulge_max mm): a muscle's
    # belly is convex; the hull's straight edges printed the masseter as a flat panel and the crown as a ridged roof
    bulge=0.08, bulge_max=7.0,
    # W2h k7: THE NASAL CARTILAGES (the dorsal and lateral nasal cartilages and the alar cartilages: the nose's tube from
    # the bony aperture forward to the rhinarium, which no bone carries): per slice the convex hull of the upper jaw's
    # bone section and the cartilage's own, a half-ellipse on `bottom` (q mm by d) up to the profile photos' dorsal line
    # (canid_hull PROFILE's dorsal run) less `top_less` mm of skin, its half-width `half` (d, mm); faded in ahead of the
    # leather's back and out where the nasal bones carry the line. The k6 skin over the bone alone sagged 16 mm under
    # the photos' dorsal line at d 24-32 (q 7 against 23-25), so the traced leather stood ahead of the muzzle as a plug
    # W2i: the dorsal and lateral nasal cartilages run back over the nasal bones' tips (the profile photos' skin stands 9.8
    # mm over the bone at d 40 and 7.6 at d 45: canid_skin DEPTHS nasal_tip's note), so the fill fades out by d 52, not 38
    # (at 38 the skin dipped 4-5 mm under the photos' dorsal line behind the nose: a knob on a neck, the W2i k1 probe)
    nose=dict(d=(0.0, 8.0, 32.0, 52.0), half=((0.0, 19.0), (10.0, 19.0), (26.0, 16.5), (38.0, 15.0), (52.0, 12.0)),
              top_less=5.0, bottom=((0.0, -2.0), (8.0, -8.0), (16.0, -14.0), (52.0, -14.0))),
)

# ============================================================================================ the tissue depths
# (name, (d, q, |x|) on the deep form, depth mm, sigma mm, source): each row carries its own source tag ([P] measured
# on the named photos in their solved cameras or matched frames, [L] canid soft-tissue anatomy where no photo shows the
# skin); the r03-derived bands the w02 gates hold the skin to are SPEC skin.head_bands (wolf.TAGS carries their evidence)
DEPTHS = (
    # W2h k7: the skin over the nasal cartilages' front, under the rhinarium (DEEP nose)
    ('nose_front', (2.0, 10.0, 0.0), 4.0, 8.0, '[L] the rhinarium\'s skin over the alar and septal cartilages: thin, the '
                                               'traced leather\'s relief (canid_hull STROKES_SKULL) on it'),
    # W2h k6: 5.5 (W2h k5 6.0): the muzzle's depth at d 40 read 80 against the gate's 62-79 (with lip_lower); the photos'
    # 9.8 at d 40 is over the leather's cartilages, which the rhinarium carries ahead of d 34
    ('nasal_tip', (40.0, 17.0, 0.0), 5.5, 7.0, '[P] the profile photos (canid_hull PROFILE, w01 w03 w10 w11 less their '
                                                 'coat) over the skull\'s dorsal line: 9.8 at d 40, 7.6 at d 45'),
    ('nasal_bridge', (60.0, 24.0, 0.0), 4.5, 12.0, '[P] the profile photos over the nasal bones: 5.5-5.7 at d 55-70, '
                                                    'less the muzzle\'s ~1 mm of short hair'),
    ('nasal_flank', (62.0, 15.0, 14.0), 4.5, 10.0, '[L] the levator nasolabialis over the maxilla\'s dorsal flank: thin'),
    # W2h k6: the stop 6.5 and the frontal 7.0 (k5 6.0 / 6.0): the skin's stop read 0.811 NE (the photos 0.73-0.80) at d
    # 106; the frontalis' base fuller brings the forehead's rise forward
    ('stop', (92.0, 31.0, 0.0), 6.5, 9.0, '[P] the profile photos: 7.3 at d 90, 6.1 at d 95, 6.4 at d 100, less ~1 '
                                           'mm of hair'),
    ('frontal', (125.0, 51.0, 0.0), 7.0, 14.0, '[L] skin and the frontalis over the frontal (the profile photos there '
                                                'are the skull plus an assumed 5: no measure)'),
    ('brow', (139.0, 50.0, 34.0), 5.5, 8.0, '[L] the supraorbital margin and the postorbital process under the skin '
                                            'and the orbicularis oculi\'s upper part'),
    ('crest', (200.0, 64.0, 0.0), 5.0, 14.0, '[L] the sagittal crest under the skin and the temporal fascia'),
    ('temporalis', (198.0, 42.0, 34.0), 12.0, 18.0, '[L] the temporalis over the fossa\'s fill (the fill bulged, DEEP '
                                                    'bulge; the w02 cranial width at d 215 q 40: 94-124)'),
    # (W2p: at the arch's mid-height, (20.6 + 8.6) / 2, with its edges MWNH 358's; W2h-W2o q 21, s12092001's mid-height)
    ('zygion', (171.0, 15.0, 72.0), 5.0, 10.0, '[L] skin over the zygomatic arch\'s lateral face (subcutaneous bone)'),
    ('masseter', (172.0, -18.0, 52.0), 9.0, 16.0, '[L] the masseter bulging over the arch-to-angle fill'),
    ('masseter_front', (125.0, -8.0, 44.0), 7.0, 12.0, '[L] the masseter\'s front under the zygomatic root'),
    ('infraorbital', (110.0, 14.0, 37.0), 6.5, 9.0, '[L] skin, the zygomaticus and the levator labii over the zygomatic '
                                                   'root and the maxilla under the eye'),
    ('muzzle_flank', (65.0, 2.0, 21.0), 5.5, 12.0, '[L] the levator labii superioris and the caninus over the maxilla'),
    # (W2h k10: 12, k5-k9 13: the canine's skin read 12.7 against r03's 8-13 with the caudal pad fuller)
    ('whisker_pad', (34.0, -6.0, 23.0), 12.0, 10.0, '[P] the wet r03 in its solved camera: its outline beside the '
                                                     'leather 13-16 mm outside the skull\'s silhouette (the mystacial '
                                                     'pad over the canine eminence)'),
    ('lip_canine', (38.0, -24.0, 22.0), 10.0, 9.0, '[P] the wet r03: the upper lip over the canine crown'),
    # W2i (the lead's call 4: "no lobes and no lump ... never a mass tuned to a width"): W2h k13's whisker_pad_caudal (27
    # mm at a 6 mm reach at (44, -14, 26), tuned to r03's 78-81 mm at d 40) removed: it stood as a round lump over the
    # lip line; the upper lip is the lips' hull over the teeth (DEEP lips) plus the rows here, one form from the pad to
    # the commissure, and the face's width is judged against the individuals' spread (w02 the face's front outline)
    ('lip_premolar', (70.0, -26.0, 19.0), 6.5, 14.0, '[L] the upper lip over the premolars, hanging over the mandible'),
    ('commissure', (96.0, -40.0, 27.0), 5.0, 9.0, '[L] the lips\' corner'),
    ('lip_lower', (42.0, -42.0, 16.0), 5.0, 10.0, '[L] the lower lip over the mandible\'s body (W2i: 5.0, its W2h k5 '
                                                  'value; W2h k7 thinned it to 3.5 to hide the mandible standing 10 mm '
                                                  'deep at d 40, now fixed at the bone: canid_skull SHAPE jaw_close, '
                                                  'chin_tissue)'),
    ('chin', (22.0, -40.0, 0.0), 5.0, 8.0, '[L] the chin\'s skin over the symphysis (the profile photos\' chin line '
                                           'lies within 1-4 mm of the skull\'s: a thin chin)'),
    ('jaw_ventral', (95.0, -59.0, 12.0), 6.0, 20.0, '[L] skin and the digastric under the mandible\'s ventral border'),
    ('throat', (150.0, -50.0, 0.0), 8.0, 25.0, '[L] the intermandibular soft tissue'),
    # (W2k: at the globe's centre, raised with canid.EYE_Q 28 -> 32 into MWNH 358's orbit rim; W2m: moved with the globe,
    # canid.EYE_SEAT, from (145.2, 32.0, 36.0); W2n: with the globe 4 mm forward, from (143.2, 35.0, 37.5))
    ('lid', (139.2, 35.0, 37.5), 2.0, 9.0, '[L] the eyelids over the globe (skin, the orbicularis oculi, the tarsus)'),
)
BASE = 5.0                  # the depth where no landmark reaches (mm)
BASE_W = 0.02               # its weight against the landmarks' Gaussians
SMOOTH = (2.5, 0.5)         # W2i: the skin's blur sigma max(2.5, 0.5 x the local depth) (mm; W2h 2.5 everywhere)
SMOOTH_SIGMAS = (2.5, 3.5, 5.0, 6.5)    # the blurred copies the field is blended between (mm)
SMOOTH_DEPTH = 3.0          # the depth field low-passed before it picks the blur (mm: the foot points jump at creases)


def _fade(d, r):
    a, b, c, e = r
    return np.clip(np.minimum((d - a) / max(b - a, 1e-6), (e - d) / max(e - c, 1e-6)), 0.0, 1.0)


def _bulged(V, beta, cap, step=1.0):
    """the convex polygon V (k, 2, counter-clockwise) with each edge pushed outward as a parabola of sagitta
    min(beta |AB|, cap) (the edge's midpoint moved that far along its outward normal, the ends kept): (m, 2)"""
    out = []
    area2 = float(np.sum(V[:, 0] * np.roll(V[:, 1], -1) - np.roll(V[:, 0], -1) * V[:, 1]))
    sgn = 1.0 if area2 > 0 else -1.0
    for a, b in zip(V, np.roll(V, -1, axis=0)):
        e = b - a
        L = float(np.linalg.norm(e))
        if L < 1e-9:
            continue
        n = sgn * np.array([e[1], -e[0]]) / L
        s = min(beta * L, cap)
        t = np.linspace(0.0, 1.0, max(2, int(L / step) + 1))[:-1]
        out.append(a[None] + t[:, None] * e[None] + (4.0 * s * t * (1.0 - t))[:, None] * n[None])
    return np.vstack(out)


def _poly_sd(P, pts):
    """the exact signed distance (negative inside) from 2D points pts (n, 2) to the closed polygon P (k, 2)"""
    from matplotlib.path import Path
    A = P
    B = np.roll(P, -1, axis=0)
    AB = B - A
    L2 = np.maximum(np.sum(AB * AB, axis=1), 1e-12)
    best = np.full(len(pts), np.inf)
    for a, ab, l2 in zip(A, AB, L2):
        t = np.clip(((pts - a) @ ab) / l2, 0.0, 1.0)
        dv = pts - (a + t[:, None] * ab)
        best = np.minimum(best, np.einsum('ij,ij->i', dv, dv))
    s = np.sqrt(best)
    inside = Path(P).contains_points(pts)
    return np.where(inside, -s, s)


def deep_form(G, bone, eye_c, eye_r, skull, log=print):
    """the deep form on the grid G (module docstring, 1): (field mm, per-hull fields)"""
    from scipy.ndimage import gaussian_filter1d
    from scipy.spatial import ConvexHull, QhullError
    Q, X = np.meshgrid(G.q, G.x, indexing='ij')
    pts = np.column_stack([Q.ravel(), X.ravel()])
    ad = SK._interp(SK.ARCH_DORSAL_W2P, G.d)
    av = SK._interp(SK.ARCH_VENTRAL_W2P, G.d)
    qa = SK._interp(SK.ALVEOLAR, G.d)
    hulls = {}
    for nm, sel in (('temporalis', lambda i: Q > av[i] - 2.0), ('masseter', lambda i: Q < ad[i] + 2.0),
                    ('lips', lambda i: Q < qa[i] + DEEP['lips']['q_add'])):
        w = _fade(G.d, DEEP[nm]['d'])
        w = w * w * (3.0 - 2.0 * w)
        H = np.array(bone, np.float32, copy=True)
        for i in range(G.n[0]):
            if w[i] <= 0.0:
                continue
            m = (bone[i] < 0.0) & sel(i)
            if m.sum() < 6:
                continue
            P = np.column_stack([Q[m], X[m]])
            try:
                hv = ConvexHull(P)
            except QhullError:
                continue
            bg = DEEP[nm].get('bulge', (DEEP['bulge'], DEEP['bulge_max']))
            sd = _poly_sd(_bulged(P[hv.vertices], bg[0], bg[1]), pts).reshape(Q.shape)
            # faded by MORPHING from the bone's own section to the hull's (a hull slid in from outside stood as a wall
            # across the head where its fade began)
            H[i] = w[i] * sd + (1.0 - w[i]) * bone[i]
        H = gaussian_filter1d(H, DEEP['smooth_d'] / G.h, axis=0, mode='nearest')
        hulls[nm] = H
        log(f'[skin] deep form: the {nm} fill on {int((w > 0).sum())} slices')
    # W2h k7: the nasal cartilages (DEEP nose)
    from . import canid_hull as CH_
    nz = DEEP['nose']
    dors = np.asarray(CH_.PROFILE, float)[CH_.PROFILE_BACK[1]:][::-1]
    hd, bt = np.asarray(nz['half'], float), np.asarray(nz['bottom'], float)
    w = _fade(G.d, nz['d'])
    w = w * w * (3.0 - 2.0 * w)
    H = np.array(bone, np.float32, copy=True)
    ang = np.linspace(0.0, np.pi, 25)
    for i in range(G.n[0]):
        if w[i] <= 0.0:
            continue
        d = float(G.d[i])
        qt = float(np.interp(d, dors[:, 0], dors[:, 1])) - nz['top_less']
        qb = float(np.interp(d, bt[:, 0], bt[:, 1]))
        a = float(np.interp(d, hd[:, 0], hd[:, 1]))
        E = np.column_stack([qb + (qt - qb) * np.sin(ang), a * np.cos(ang)])
        m = (bone[i] < 0.0) & (Q > qa[i] - 2.0)
        P = np.vstack([np.column_stack([Q[m], X[m]]), E]) if m.any() else E
        try:
            hv = ConvexHull(P)
        except QhullError:
            continue
        sd = _poly_sd(P[hv.vertices], pts).reshape(Q.shape)
        H[i] = w[i] * sd + (1.0 - w[i]) * bone[i]
    hulls['nose'] = gaussian_filter1d(H, DEEP['smooth_d'] / G.h, axis=0, mode='nearest')
    log(f'[skin] deep form: the nasal cartilages on {int((w > 0).sum())} slices')
    D_, Q_, X_ = G.mesh()
    glob = np.minimum(np.sqrt((D_ - eye_c[0]) ** 2 + (Q_ - eye_c[1]) ** 2 + (X_ - eye_c[2]) ** 2),
                      np.sqrt((D_ - eye_c[0]) ** 2 + (Q_ - eye_c[1]) ** 2 + (X_ + eye_c[2]) ** 2)) - eye_r
    del D_, Q_, X_
    df = np.minimum(bone, glob.astype(np.float32))
    for H in hulls.values():
        df = np.minimum(df, H)
    return df, hulls


def depth_at(F):
    """the interpolated depth (mm) at deep-form surface points F (n, 3) (d, q, x): the landmarks' normalised Gaussians,
    mirrored (|x|), BASE with weight BASE_W"""
    Fm = np.column_stack([F[:, 0], F[:, 1], np.abs(F[:, 2])])
    num = np.full(len(F), BASE * BASE_W)
    den = np.full(len(F), BASE_W)
    for _, c, dep, sig, _ in DEPTHS:
        w = np.exp(-np.sum((Fm - np.asarray(c, float)) ** 2, axis=1) / (2.0 * sig * sig))
        num += w * dep
        den += w
    return num / den


def skin_from_skull(spec, G, log=print):
    """the skin on the head grid G (module docstring): dict(phi (the skin, mm), deep (the deep form), bone (the skull),
    depth (the interpolated depth at each voxel's foot point, nan off the band))"""
    import time
    from scipy import ndimage as nd
    t0 = time.time()
    S = SK.Skull()
    eye_c, eye_r = SK.eye_globe(spec)
    bone = np.empty(G.n, np.float32)
    Qm, Xm = np.meshgrid(G.q, G.x, indexing='ij')
    for i in range(G.n[0]):
        P = np.column_stack([np.full(Qm.size, G.d[i]), Qm.ravel(), Xm.ravel()])
        bone[i] = S.field(P, eye_c, eye_r).reshape(Qm.shape)
    bone = redistance(bone, G.h)
    log(f'[skin] the skull on the head grid {G.n} at {G.h} mm ({time.time() - t0:.0f}s)')
    df, hulls = deep_form(G, bone, eye_c, eye_r, S, log)
    df = redistance(df, G.h)
    log(f'[skin] the deep form redistanced ({time.time() - t0:.0f}s)')
    # the depth at each band voxel's foot point on the deep form
    g = np.stack(np.gradient(df, G.h), -1)
    band = np.abs(df) < 40.0
    idx = np.nonzero(band)
    P = np.column_stack([G.d[idx[0]], G.q[idx[1]], G.x[idx[2]]])
    gn = g[idx]
    gn /= np.maximum(np.linalg.norm(gn, axis=1, keepdims=True), 1e-6)
    foot = P - df[idx][:, None] * gn
    dep = np.full(G.n, BASE, np.float32)
    dep[idx] = depth_at(foot).astype(np.float32)
    T = df - dep
    T = redistance(T, G.h)
    # W2i: the blur's sigma grows with the depth (module docstring, 3): the field blended between its blurred copies
    sig = np.clip(np.maximum(SMOOTH[0], SMOOTH[1] * nd.gaussian_filter(dep, SMOOTH_DEPTH / G.h, mode='nearest')),
                  SMOOTH_SIGMAS[0], SMOOTH_SIGMAS[-1]).astype(np.float32)
    out = np.zeros(G.n, np.float32)
    ss = SMOOTH_SIGMAS
    for k, s_ in enumerate(ss):
        lo_ = ss[k - 1] if k > 0 else s_ - 1.0
        hi_ = ss[k + 1] if k + 1 < len(ss) else s_ + 1.0
        w = np.where(sig <= s_, np.clip((sig - lo_) / (s_ - lo_), 0.0, 1.0), np.clip((hi_ - sig) / (hi_ - s_), 0.0, 1.0))
        if k == 0:
            w = np.where(sig <= s_, 1.0, w)
        if k == len(ss) - 1:
            w = np.where(sig >= s_, 1.0, w)
        if float(w.max()) <= 0.0:
            continue
        out += (w * nd.gaussian_filter(T, s_ / G.h, mode='nearest')).astype(np.float32)
    skin = redistance(out, G.h)
    log(f'[skin] the skin: the deep form offset by the depths, blurred {SMOOTH[0]}-{SMOOTH_SIGMAS[-1]} mm by depth '
        f'({time.time() - t0:.0f}s)')
    return dict(phi=skin, deep=df, bone=bone, depth=np.where(band, dep, np.nan).astype(np.float32), sigma=sig)


def skin_volume(spec, lo, hi, h=1.0, log=print):
    """skin_from_skull on the grid [lo, hi] at h, cached by the skull's and the skin's tables"""
    from . import canid_hull as CH_
    G = Grid(lo, hi, h)
    eye_c, eye_r = SK.eye_globe(spec)
    key = cache_key(dict(v=VERSION, sv=SK.VERSION, lat=SK.LAT, top=SK.TOP_OUT, holes=SK.TOP_HOLES, occ=SK.OCCLUSAL,
                         alv=SK.ALVEOLAR, ad=SK.ARCH_DORSAL, av=SK.ARCH_VENTRAL, lm=SK.LANDMARKS, can=SK.CANINE_UP,
                         dors=SK.DORSUM_HALF, shape=SK.SHAPE, sm=(SK.SMOOTH_IMG, SK.SMOOTH_PROF), deep=DEEP,
                         depths=DEPTHS, base=(BASE, BASE_W, SMOOTH, SMOOTH_SIGMAS, SMOOTH_DEPTH),
                         eye=(eye_c.tolist(), eye_r), lo=lo, hi=hi, h=h, prof=(CH_.PROFILE, CH_.PROFILE_BACK),
                         ad2=SK.ARCH_DORSAL_W2P, av2=SK.ARCH_VENTRAL_W2P))
    out = cached('wolf_skin', key, lambda: skin_from_skull(spec, G, log), log)
    out['grid'] = G
    return out

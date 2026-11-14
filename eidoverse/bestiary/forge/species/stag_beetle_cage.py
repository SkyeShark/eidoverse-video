"""B4 (the Bestiary lead's B4 body round, 10-27): THE STAG BEETLE'S BODY CAGES. Every body sclerite that is not the head or a
mandible becomes ONE closed quad CAGE whose edge loops run along its measured features, creased SEMI-SHARP
(forge/subdiv_sharp.py: DeRose, Kass & Truong 1998) so each edge's limit radius meets the photos' bound, the surfaces between
them curved by construction (the head's and the mandible's way: heads/insect_cage.py, heads/insect_mcage.py, which this module
reads and never edits). Each cage's TARGETS lie on the CLAY (the part's own sdf.Program, built exactly as b03 builds it:
reference()), so its limit surface is the clay's shape with the photos' edges; the controls are fitted so the limit passes
through them (subdiv_sharp.fit_controls). THE LOW is the cage's own topology at the limit positions (every low vertex on the
high); its triangle count is the plan's budget (BEETLE_PLAN §4.6, BUDGET).

THE PARTS (BEETLE_PLAN §4.2, §4.6; arthropod_parts.build_parts' shells):
  pronotum   a tube along z (the half mirrored and welded at x 0): the hind face a cap, the outer rings (the CARINA a crease
             along the side, on the clay's widest point of every section, M1l's 62 um line: r <= 0.10), the FRONT and HIND
             MARGINS crease rings, the front face's annulus, the head's SOCKET (the head shrunk by HEAD_SINK) as rings going in,
             its floor a cap; the PROCOXAL CAVITY a square-ring PORT in the underside (the fore coxa's socket its plug); the
             NECK graft ring (CROSSBREED §7.3, R10: the sleeve's proximal ring, on the parent) a socket ring at equal angles
  venter     a tube along z: the abdominal end a cap, the outer rings, the front face and the pronotum's socket, its floor a
             cap; the MESO- and METACOXAL CAVITIES square-ring ports, the scutellum's seat a port (its plug the seat), the
             STERNITE sutures (M3v: four transverse grooves on the abdomen, the metacoxae's hind border among them) as lip /
             foot loop pairs creased on the ventral half, the PLEURAL suture (M3v: the metepisternum's medial edge) and the
             metaventral midline groove creased; the WING and ELYTRON graft ports on the dorsum under the elytra
  scutellum  a small tube along z (the half mirrored)
  elytron    a closed plate: the outer face and the inner face on one grid (the clay's mid-surface patch offset by its
             half-thickness both ways, arthropod_parts.elytron_patch), the rim round its boundary (the sutural edge, the base, the
             apex, the epipleuron's inner edge) creased at both edges, the lateral MARGIN (the epipleural fold) a crease line;
             the right elytron the left's exact mirror (x -> -x, the winding flipped)
  scape, funicle (one tube through its five beads), lamella_0..3 (each a flattened tube, its stalk at the root), palp_max,
             palp_lab: tubes along their axes, K vertices a ring at equal angles, the ends capped
THE FRAME: the plan frame in LIFE mm, (x, h, z): x the creature's left, h above the venter's lowest point (world y - the
clearance), z forward from the clypeal tip; the clay's programs run at the author scale (metres, x10) and world y.

RINGS AND PORTS (CROSSBREED §2.2, §7.1, §7.3 as corrected by R10 and the lead's decision 9): K = 0 mod 4 from the measured
radius (the chord sag r_max (1 - cos pi / K) at most 2 texels at 9,257 px/m at x10: 0.216 mm at x10), vertex 0 on the port
frame's X (its tangent), equal parametric angles about its Z (distal), right-handed on L and unsided sites, left-handed on R;
planarity within 0.02 r_bar. The records are the legs round's schema (families/arthropod_cage.ring_record), at the author
scale in metres, in the WORLD frame (the plan frame's h + the clearance), the frame and origin also in the parent joint's bind
frame: the NECK (the cervical sleeve, its proximal ring the pronotum's neck ring), the ANTENNA sites (the antennal sleeves where
the scapes leave the head: arthropod_cage.sleeve itself), the ELYTRA / HINDWING ports (a planar loop on the venter's dorsum).
The coxal cavities are the body's PORTS (sockets); their graft rings are the legs round's coxa sleeves (arthropod_cage).

b4-3 (the third build:body agent, 10-28; the first two were cut by the account's session limit, b4-1 at 18:50, b4-2 at 00:00):
  - the timing gate: check:b3h's result line exists (B3h's files unchanged since: insect_cage b170b547, insect_mcage cc0e01e7,
    arthropod_parts 642d7161, insect 776a4519, b03_clay 42ba53d3); B4 reads them only
  - THE VENTER rebuilt (VEN_CAGE, build_venter): the front ONE flat face on the plane z_front = the pronotum's hind face + SINK
    (the clay's ledge folded the cage); the coxal pockets INSET ports (TubeCage.inset) bracketing their measured footprints;
    the elytra / hindwing port a planar K 12 loop inset in a square block; the tip an O-GRID (TubeCage.inset_open: its cap's
    corners off its smooth ring), its rings by arc length, its cap relaxed on the surface (relax_cap); a light regularised fit
    (FIT_LAM 0.01, the pockets and the ring held: VEN_FIT_W). Gates (f2): the meso / meta joints 0.342 / 0.392 (b4-2 0.61 /
    0.65), the waist 0.320, the limit p99 0.093 (0.22), 70 limit folds (550), every one on the coxal pockets' creased undercut
    lips (inside the coxae), 3,040 triangles (the plan's row 3,024)
  - THE PRONOTUM: a ring moved from the outer run onto the socket's side wall (n_out 23, n_f1 4: the head sank 0.42 -> 0.344),
    the socket held in the fit (fit_w socket 20), the procoxal cavity an inset pocket (the fore coxa 0.417 -> 0.326); 0 limit
    folds (8), 3,280 triangles
  - THE RINGS: the antenna's a sleeve ring (b4-2's loop on the head was 0.72 r_bar off planar), the wing's planar (0.076), the
    neck's the cervical sleeve's proximal ring; the records in the world frame (b4-2 wrote the plan frame), the body's coxa ring
    records dropped (the legs own them); port_socket / port_cavity / socket_ring removed (unused)
  - left as found: the elytron (7 limit folds at the epipleural strip's end, b4-2's best), the scutellum, the antennae, palps
  - the re-run: work/bestiary/beetle/scratch_b4_body/run_b4.py (its docstring), views p08_views.py, probes p10 / p20 / p21
"""
import hashlib
import json
import os
import time

import numpy as np

from ..mesh import QuadMesh
from .. import subdiv_sharp as SS

VERSION = 'b4-3'
REF_VERSION = 'ref-1'             # bumped whenever reference() / layout_fields() change what the sampled grids hold (their cache key)
# the files whose content decides the clay's body shells (the sampled grids' cache key): the descriptors and carves
# (arthropod_parts, arthropod, the SPEC), the antenna / palp descriptors and the head's capsule (insect), the head cache's key
# (insect_cage.head_key)
REF_FILES = ('eidoverse/bestiary/forge/families/arthropod_parts.py', 'eidoverse/bestiary/forge/families/arthropod.py',
             'eidoverse/bestiary/forge/species/stag_beetle.py', 'eidoverse/bestiary/forge/heads/insect.py',
             'eidoverse/bestiary/forge/heads/insect_cage.py')
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
HEAD_CACHE = os.path.join(REPO, 'work', 'bestiary', 'beetle', 'cache_hull')

# ============================================================================================ the plan's numbers
# BEETLE_PLAN §4.6: the cage (the designed low) per part, triangles over all copies; §4.7: the BODY / HEAD sets' one density
BUDGET = dict(pronotum=3280, scutellum=352, elytron=8032, venter=3024, scape=600, funicle=1120, lamella=768, palp=1056)
FIT_LAM = dict(pronotum=0.05, venter=0.01, scutellum=0.0, elytron=0.02, scape=0.0, funicle=0.0, lamella=0.05, palp=0.0)
VEN_FIT_W = dict(pocket=50.0, ring=1.0e3)   # b4-3: the venter's regularised fit, its pockets' and its wing ring's weights
#                                   the controls' fit per part (fit_limit): 0 interpolates the targets exactly, > 0 regularises
PX_PER_M = 9257.0                 # BEETLE_PLAN §4.7: the one density at x10 (0.108 mm a texel at x10)
SAG_MAX = 2.0 / PX_PER_M          # CROSSBREED §2.2's check: the chord sag at most 2 texels (metres at x10)


# ============================================================================================ small helpers
def smooth01(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def cache_key(obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=lambda o: np.asarray(o).tolist()).encode()).hexdigest()[:16]


def unit(v):
    v = np.asarray(v, np.float64)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def file_sha1(path):
    with open(path, 'rb') as f:
        return hashlib.sha1(f.read()).hexdigest()


# ============================================================================================ the reference: the clay
class Field:
    """a clay shell's signed distance in the plan frame, life mm in and out: the part's own sdf.Program (author scale, metres,
    world y = h + clear); mirror: the right part reads its left program at M p (arthropod_parts.Part.eval)"""

    def __init__(self, prog, s, clear, mirror=False, name=''):
        self.prog, self.s, self.clear, self.mirror, self.name = prog, float(s), float(clear), mirror, name

    def world(self, P):
        P = np.atleast_2d(np.asarray(P, np.float64))
        W = np.column_stack([P[:, 0] * (-1.0 if self.mirror else 1.0), P[:, 1] + self.clear, P[:, 2]]) * self.s
        return W

    def __call__(self, P):
        P = np.atleast_2d(np.asarray(P, np.float64))
        out = np.empty(len(P))
        for a in range(0, len(P), 1_000_000):
            out[a:a + 1_000_000] = self.prog.eval(self.world(P[a:a + 1_000_000])).astype(np.float64) / self.s
        return out

    def grad(self, P, e=0.004):
        P = np.atleast_2d(np.asarray(P, np.float64))
        g = np.zeros_like(P)
        for k in range(3):
            d = np.zeros(3)
            d[k] = e
            g[:, k] = (self(P + d) - self(P - d)) / (2.0 * e)
        return g

    def project(self, P, it=8):
        """Newton steps onto the zero set along the gradient"""
        P = np.atleast_2d(np.asarray(P, np.float64)).copy()
        for _ in range(it):
            f = self(P)
            g = self.grad(P)
            P -= (f / np.maximum((g * g).sum(1), 1e-9))[:, None] * g
        return P

    def ray(self, A, D, reach=6.0, step=0.01, enter=False, last=False):
        """the first EXIT (enter: ENTRY) of the solid along A + t D, t in [0, reach] (last: the last such crossing), refined by
        bisection; NaN where none"""
        A = np.atleast_2d(np.asarray(A, np.float64))
        D = unit(np.atleast_2d(np.asarray(D, np.float64)))
        ts = np.arange(0.0, reach + 1e-9, step)
        Q = A[:, None, :] + ts[None, :, None] * D[:, None, :]
        f = self(Q.reshape(-1, 3)).reshape(len(A), len(ts))
        cond = (f[:, :-1] >= 0) & (f[:, 1:] < 0) if enter else (f[:, :-1] < 0) & (f[:, 1:] >= 0)
        out = np.full((len(A), 3), np.nan)
        rows = np.nonzero(cond.any(1))[0]
        if not len(rows):
            return out
        idx = np.array([np.nonzero(cond[j])[0][-1 if last else 0] for j in rows])
        a_, b_ = ts[idx].copy(), ts[idx + 1].copy()
        fa = f[rows, idx]
        for _ in range(26):
            m_ = 0.5 * (a_ + b_)
            fm = self(A[rows] + m_[:, None] * D[rows])
            same = (fm < 0) == (fa < 0)
            a_ = np.where(same, m_, a_)
            b_ = np.where(same, b_, m_)
        out[rows] = A[rows] + (0.5 * (a_ + b_))[:, None] * D[rows]
        return out


class CutField:
    """b4-3: a field cut flat at z = z_f (kept: z <= z_f), max(f, z - z_f), life mm in and out (the venter's front)"""

    def __init__(self, f, z_f, name=''):
        self.f, self.z_f, self.name = f, float(z_f), name

    def __call__(self, P):
        P = np.atleast_2d(np.asarray(P, np.float64))
        return np.maximum(self.f(P), P[:, 2] - self.z_f)

    grad = Field.grad
    project = Field.project
    ray = Field.ray


def head_cache_path(spec):
    """the B3h head's cached GRID (heads/insect_cage.head_volume's npz) for the head as the live insect_cage.py defines it; this
    module never builds it (cache_hull is B3h's): a missing cache is an error"""
    from ..heads import insect_cage as IC
    key = IC.head_key(spec)
    path = os.path.join(HEAD_CACHE, f'beetle_subd_head_{key}.npz')
    if not os.path.exists(path):
        raise FileNotFoundError(f'the head cache {os.path.relpath(path, REPO)} (insect_cage {IC.VERSION}) is not built: B4 '
                                f'reads the head, it never builds it')
    return path, key


def reference(spec, log=print, head_npz=None):
    """THE CLAY's body shells as b03 builds them (families/arthropod_parts.build_parts, its code for these parts and their
    carves, rebuilt here without the head's, the eye's or the mandible's own programs, whose caches B3h owns): the pronotum
    (carved by the head's coarse capsule shrunk by HEAD_SINK, blended COLLAR_K, and by both fore coxae shrunk by SINK), the venter
    (carved by the mid and hind coxae and by the pronotum and the scutellum, shrunk by SINK), the scutellum, the elytron, the
    left antenna (the scape and the palps seated on the head's coarse field, the funicle on the scape, each lamella on the one
    before) and palps. Returns dict(fields={name: Field (life mm)}, descs, chain, head=dict(path, key, values, lo, h), coxae
    descs, elytron info, carves)"""
    from .. import sdf as S_
    from ..families import arthropod as AR
    from ..families import arthropod_parts as AP
    from ..heads import insect as HEAD
    t0 = time.time()
    chain = AR.rest_chain(spec)
    s, clear, lmw = chain['scale_m'], chain['clearance'], chain['head']['lm']
    if head_npz is None:
        head_npz, hkey = head_cache_path(spec)
    else:
        hkey = os.path.basename(head_npz)
    Z = np.load(head_npz, allow_pickle=False)
    hv_lo, hv_h = np.asarray(Z['lo'], np.float64), float(Z['h'])
    hv_c = np.ascontiguousarray(Z['values'][::2, ::2, ::2])
    del Z
    # build_parts' cap_c (insect.capsule_descs coarse=True): every second sample, the plan frame's h shifted by the clearance
    cap_c = [AP.grid((hv_lo[0], hv_lo[1] + clear, hv_lo[2]), 2.0 * hv_h, hv_c, name='head capsule (volume, coarse)')]
    f_head = AP.field_mm(cap_c, s)
    raw = {}
    ant, ant_axes = HEAD.antenna_descs(spec, lmw)
    palps = HEAD.palp_descs(lmw)
    for nm, descs in list(ant.items()) + list(palps.items()):
        if nm.startswith('lamella') or nm == 'funicle':
            continue
        d0 = descs[0]
        u = AP.unit(d0['b'] - d0['a'])
        s_ = AP.seat_along(f_head, d0['a'], u, start=-3.0, end=4.0)
        if s_ is not None:
            descs[0] = dict(d0, a=d0['a'] + (s_ - AP.HEAD_SINK + d0['ra']) * u)
    raw['scape'] = ant['scape']
    f_sc = AP.field_mm(ant['scape'], s)
    e1, d1 = ant_axes['funicle']
    s_ = AP.seat_along(f_sc, e1, d1, start=-1.0, end=1.5)
    b0 = ant['funicle'][0]
    sh = (s_ - AP.SINK + b0['ra']) - float((b0['a'] - e1) @ d1)
    ant['funicle'][0] = dict(b0, a=b0['a'] + sh * d1)
    raw['funicle'] = ant['funicle']
    prev = ant['funicle']
    e3, d2 = ant_axes['club']
    for k in range(4):
        dd = ant[f'lamella_{k}']
        f_par = AP.field_mm(prev, s)
        st = dd[0]
        s_ = AP.seat_along(f_par, st['a'], d2, start=-1.0, end=1.5)
        if s_ is not None:
            a_new = st['a'] + (s_ - AP.SINK + st['ra']) * d2
            if float((st['b'] - a_new) @ d2) < 0.05:
                a_new = st['b'] - 0.05 * d2
            dd[0] = dict(st, a=a_new)
        raw[f'lamella_{k}'] = dd
        prev = dd
    raw['palp_max'] = palps['palp_max']
    raw['palp_lab'] = palps['palp_lab']
    ely_V, ely_F, ely = AP.elytron_patch(spec, clear)
    raw['elytron'] = [AP.shell(ely_V, ely_F, ely['ht'], name='elytron')]
    raw['pronotum'] = AP.pronotum_descs(spec, clear)
    raw['venter'] = AP.venter_descs(spec, clear, ely)
    raw['scutellum'] = AP.scutellum_descs(spec, clear, ely)
    f_ven = AP.field_mm(raw['venter'], s)
    coxa = {}
    for c, pair, cox, i in AR.LEGS:
        lp = AP.leg_parts(spec, chain, c, pair, dict(venter=f_ven))
        coxa[c] = lp[f'coxa_{c}'][0]
    carve = {k: [] for k in raw}
    carve['pronotum'] += [(d, -AP.HEAD_SINK, S_.SUBTRACT, AP.COLLAR_K) for d in cap_c if AP.carvable(d, -AP.HEAD_SINK)]
    for c in ('f', 'm', 'h'):
        tgt = 'pronotum' if c == 'f' else 'venter'
        for ds in (coxa[c], [AP.mirror_desc(d) for d in coxa[c]]):
            carve[tgt] += [(d, -AP.SINK, S_.SUBTRACT) for d in ds if AP.carvable(d, -AP.SINK)]
    for ch in ('pronotum', 'scutellum'):
        carve['venter'] += [(d, -AP.SINK, S_.SUBTRACT) for d in raw[ch] if AP.carvable(d, -AP.SINK)]
    fields = {}
    for nm, descs in raw.items():
        fields[nm] = Field(AP.program_of(descs, s, carve.get(nm, [])), s, clear, name=nm)
    for c in ('f', 'm', 'h'):
        fields[f'coxa_{c}'] = Field(AP.program_of(coxa[c], s), s, clear, name=f'coxa_{c}')
    fields['head_coarse'] = Field(AP.program_of(cap_c, s), s, clear, name='head (coarse)')
    # b4-3: THE VENTER'S FRONT is the plane z_front, SINK inside the pronotum's flat HIND FACE (VEN_CAGE's comment): the
    # venter's fields without the pronotum's carve, 'venter_unc' (no carve: the layout) and 'venter_seats' (the coxal and
    # scutellar seats only: with the cut, the gates' reference)
    zt = fields['pronotum'].ray(np.array([[0.0, 6.0, -19.5]]), np.array([[0.0, 0.0, 1.0]]), reach=3.0, step=0.002,
                                enter=True)[0]
    z_hind = float(zt[2])
    seats = [c for c in carve['venter'] if not any(c[0] is d for d in raw['pronotum'])]
    fields['venter_unc'] = Field(AP.program_of(raw['venter'], s, []), s, clear, name='venter (uncarved)')
    fields['venter_seats'] = Field(AP.program_of(raw['venter'], s, seats), s, clear,
                                   name='venter (the coxal and scutellar seats)')
    log(f'[b4] the clay\'s body shells rebuilt (arthropod_parts\' descriptors and carves) on the head cache {hkey} in '
        f'{time.time() - t0:.1f}s; the pronotum\'s hind face z {z_hind:.3f}, the venter\'s front plane z '
        f'{z_hind + AP.SINK:.3f}')
    return dict(fields=fields, descs=raw, chain=chain, clear=clear, s=s, elytron=ely, coxa=coxa, ant_axes=ant_axes,
                head=dict(path=head_npz, key=hkey, lo=hv_lo, h=hv_h), carve=carve, z_hind=z_hind,
                z_front=z_hind + AP.SINK)


def layout_fields(R):
    """the fields the cages are LAID on (their rings and stations), without the seats a port's plug takes: the pronotum without
    its procoxal sockets (the head's socket kept), the venter without its coxal and scutellar seats (the pronotum's socket kept)"""
    from ..families import arthropod_parts as AP
    s, clear = R['s'], R['clear']
    cv_p = [c for c in R['carve']['pronotum'] if c[0]['kind'] == 'grid']
    pdesc = [d for d in R['descs']['pronotum'] if AP.carvable(d, -AP.SINK)]
    cv_v = [c for c in R['carve']['venter'] if any(c[0] is d for d in pdesc)]
    zf = R['z_front']
    return dict(pron_nc=Field(AP.program_of(R['descs']['pronotum'], s, cv_p), s, clear, name='pronotum (no coxal seats)'),
                ven_nc=Field(AP.program_of(R['descs']['venter'], s, cv_v), s, clear, name='venter (no coxal / scutellar seats)'),
                ven_lay=CutField(R['fields']['venter_unc'], zf, name='venter (uncarved, its front the plane z_front)'),
                ven_ref=CutField(R['fields']['venter_seats'], zf, name='venter (its seats carved, its front the plane z_front)'))


# the sampled grids: (name, field, lo, hi, h (life mm), half)
GRIDS = (('pron', 'pronotum', (0.0, 2.2, -18.75), (8.1, 14.15, -8.75), 0.025, True),
         ('pron_nc', 'pron_nc', (0.0, 2.2, -18.75), (8.1, 14.15, -8.75), 0.025, True),
         ('ven', 'venter', (0.0, -0.3, -42.65), (9.1, 11.4, -17.45), 0.035, True),
         ('ven_nc', 'ven_nc', (0.0, -0.3, -42.65), (9.1, 11.4, -17.45), 0.035, True),
         ('ven_lay', 'ven_lay', (0.0, -0.3, -42.65), (9.1, 11.4, -17.45), 0.035, True),
         ('ven_ref', 'ven_ref', (0.0, -0.3, -42.65), (9.1, 11.4, -17.45), 0.035, True),
         ('scut', 'scutellum', (0.0, 10.2, -21.4), (1.7, 11.8, -18.2), 0.008, True))


def part_grids(R, cache_dir, log=print, names=None):
    """the clay sampled on its grids (GRIDS), cached in cache_dir under the reference's key (the venter's cut grids also under
    their front plane)"""
    lf = layout_fields(R)
    out = {}
    for nm, src, lo, hi, h, half in GRIDS:
        if names is not None and nm not in names:
            continue
        f = R['fields'][src] if src in R['fields'] else lf[src]
        extra = dict(z_f=round(R['z_front'], 6)) if nm in ('ven_lay', 'ven_ref') else {}
        key = cache_key(dict(v='grid-1', ref=R['key'], nm=nm, lo=lo, hi=hi, h=h, half=half, **extra))
        out[nm] = grid_cached(os.path.join(cache_dir, f'grid_{nm}_{key}.npz'), f, lo, hi, h, half=half, log=log, name=nm)
    return out


# ============================================================================================ sections
def field_slice(field, axis, val, lo2, hi2, res):
    """the field on a 2D grid in the plane coordinate[axis] = val: returns (U, V grids of the two other coordinates in order,
    values)"""
    ax = [a for a in range(3) if a != axis]
    us = np.arange(lo2[0], hi2[0] + 1e-9, res)
    vs = np.arange(lo2[1], hi2[1] + 1e-9, res)
    U, Vv = np.meshgrid(us, vs, indexing='ij')
    P = np.zeros((U.size, 3))
    P[:, ax[0]] = U.ravel()
    P[:, ax[1]] = Vv.ravel()
    P[:, axis] = val
    return us, vs, field(P).reshape(U.shape)


def contours(us, vs, F):
    """the zero contours of F (on the us x vs grid) as closed polylines (n, 2) in (u, v), counter-clockwise for an outer
    boundary, clockwise for a hole"""
    from skimage.measure import find_contours
    out = []
    for C in find_contours(F, 0.0):
        P = np.column_stack([np.interp(C[:, 0], np.arange(len(us)), us), np.interp(C[:, 1], np.arange(len(vs)), vs)])
        if np.allclose(P[0], P[-1]):
            P = P[:-1]
        if len(P) < 8:
            continue
        out.append(P)
    return out


def poly_area(P):
    return 0.5 * float(np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1]))


def arclen(P, closed=False):
    Q = np.vstack([P, P[:1]]) if closed else P
    return np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Q, axis=0), axis=1))])


def resample_open(P, s_new):
    """an open polyline P at the arc lengths s_new"""
    s = arclen(P)
    return np.column_stack([np.interp(s_new, s, P[:, k]) for k in range(P.shape[1])])


# ============================================================================================ the clay sampled on a grid
class GridField:
    """a clay field sampled on a dense grid (life mm, plan frame), read trilinearly: the clay's programs cost ~1e-5 s a point
    on Warp's CPU device, the cages read them ~1e8 times. half: the grid holds x >= -pad only and |x| is read (a midline
    part, symmetric by construction)"""

    def __init__(self, values, lo, h, half=False, name=''):
        self.v = np.asarray(values, np.float32)
        self.lo = np.asarray(lo, np.float64)
        self.h = float(h)
        self.half = half
        self.name = name
        self.hi = self.lo + (np.array(self.v.shape) - 1) * self.h

    def __call__(self, P):
        from scipy import ndimage as nd
        P = np.atleast_2d(np.asarray(P, np.float64))
        x = np.abs(P[:, 0]) if self.half else P[:, 0]
        q = [(x - self.lo[0]) / self.h, (P[:, 1] - self.lo[1]) / self.h, (P[:, 2] - self.lo[2]) / self.h]
        out = nd.map_coordinates(self.v, q, order=1, mode='nearest').astype(np.float64)
        # outside the box: at least the distance to it (the box holds the part with a pad, so outside is outside)
        d_out = np.maximum.reduce([self.lo[0] - x, x - self.hi[0], self.lo[1] - P[:, 1], P[:, 1] - self.hi[1],
                                   self.lo[2] - P[:, 2], P[:, 2] - self.hi[2]])
        return np.where(d_out > 0, np.maximum(out, d_out), out)

    grad = Field.grad
    project = Field.project
    ray = Field.ray


def sample_grid(field, lo, hi, h, half=False, levels=(4, 2, 2), log=print, name=''):
    """the field on a dense grid at h over [lo, hi] (life mm), exact only in a narrow band round the surface (b03_clay.nb_grid's
    scheme: a coarse grid, refined where a cell's corners come within ~2.8 cells of the surface); half: x from -2 h only"""
    from scipy import ndimage as nd
    t0 = time.time()
    lo, hi = np.asarray(lo, np.float64).copy(), np.asarray(hi, np.float64)
    if half:
        lo[0] = -2.0 * h
    hc = h * int(np.prod(levels))
    n = np.ceil((hi - lo) / hc).astype(int) + 1
    xs = [lo[k] + np.arange(n[k]) * hc for k in range(3)]
    G = np.stack(np.meshgrid(*xs, indexing='ij'), -1).reshape(-1, 3)
    A = field(G).reshape(n).astype(np.float32)
    nev = len(G)
    hh = hc
    for fct in levels:
        hn = hh / fct
        nn = (n - 1) * fct + 1
        Up = nd.zoom(A, [nn[k] / n[k] for k in range(3)], order=1, grid_mode=False, mode='nearest')
        near = np.abs(A) <= hh * np.sqrt(3.0) * 1.6
        cell = near[:-1, :-1, :-1] | near[1:, :-1, :-1] | near[:-1, 1:, :-1] | near[:-1, :-1, 1:] | \
            near[1:, 1:, :-1] | near[1:, :-1, 1:] | near[:-1, 1:, 1:] | near[1:, 1:, 1:]
        ci = np.argwhere(cell)
        o = np.stack(np.meshgrid(*[np.arange(fct + 1)] * 3, indexing='ij'), -1).reshape(-1, 3)
        key = np.unique(((ci[:, None, :] * fct + o[None]).reshape(-1, 3) * np.array([nn[1] * nn[2], nn[2], 1])).sum(1))
        ii = np.stack([key // (nn[1] * nn[2]), (key // nn[2]) % nn[1], key % nn[2]], -1)
        pts = lo + ii * hn
        vals = np.concatenate([field(pts[s:s + 1_000_000]) for s in range(0, len(pts), 1_000_000)]) if len(pts) else []
        Up[ii[:, 0], ii[:, 1], ii[:, 2]] = vals
        nev += len(pts)
        A, n, hh = Up, nn, hn
    log(f'[b4] {name or field.name}: sampled on {tuple(A.shape)} at {hh:.4f} mm ({nev:,} exact evaluations, narrow band) in '
        f'{time.time() - t0:.0f}s')
    return GridField(A, lo, hh, half=half, name=name or field.name)


def grid_cached(path, field, lo, hi, h, half=False, log=print, name=''):
    if os.path.exists(path):
        Z = np.load(path)
        return GridField(Z['v'], Z['lo'], float(Z['h']), half=bool(Z['half']), name=name)
    g = sample_grid(field, lo, hi, h, half=half, log=log, name=name)
    np.savez(path, v=g.v, lo=g.lo, h=np.float64(g.h), half=np.bool_(g.half))
    return g


# ============================================================================================ the tube cage (midline parts)
class TubeCage:
    """a midline part's HALF cage (x >= 0), mirrored and welded at x 0: a tube along z, the T cap at its back (facing -z), rings
    R0 .. RK forward, the B cap at its front (facing +z); heads/insect_cage.Cage's box turned onto z. Each half ring runs from
    the top midline (i 0) out along the TOP (nA intervals), down the SIDE (nB), back along the BOTTOM (nA) to the bottom
    midline (i M - 1 = 2 nA + nB); a cap's half is an (nA + 1) x (nB + 1) grid, a across (a 0 the midline), b down. The only
    extraordinary vertices are the caps' corners. Quads wind outward (the derivation in BEETLE B4's notes: T faces -z, the
    rings out, B +z)"""

    def __init__(self, nA, nB, K):
        self.nA, self.nB, self.K = nA, nB, K
        self.M = 2 * nA + nB + 1
        self.T = np.arange((nA + 1) * (nB + 1)).reshape(nA + 1, nB + 1)
        cnt = self.T.size
        self.R = np.full((K + 1, self.M), -1, int)
        for i in range(self.M):
            self.R[0, i] = self.boundary(self.T, i)
        for k in range(1, K):
            self.R[k] = cnt + np.arange(self.M)
            cnt += self.M
        self.B = cnt + np.arange((nA + 1) * (nB + 1)).reshape(nA + 1, nB + 1)
        cnt += self.B.size
        for i in range(self.M):
            self.R[K, i] = self.boundary(self.B, i)
        self.n_half = cnt
        Q = []
        for a in range(nA):
            for b in range(nB):
                Q.append((self.T[a, b], self.T[a + 1, b], self.T[a + 1, b + 1], self.T[a, b + 1]))
        for k in range(K):
            for i in range(self.M - 1):
                Q.append((self.R[k, i], self.R[k + 1, i], self.R[k + 1, i + 1], self.R[k, i + 1]))
        for a in range(nA):
            for b in range(nB):
                Q.append((self.B[a, b], self.B[a, b + 1], self.B[a + 1, b + 1], self.B[a + 1, b]))
        self.Qh = np.array(Q, int)
        self.P = np.full((self.n_half, 3), np.nan)
        self.src = {}
        self.sharp_h = {}
        self.loops = {}
        self.plug = np.zeros(self.n_half, bool)          # the ports' native plugs (faces inside a port loop)
        self.ports = {}
        self.extra_mid = []                               # b4-3: inset loops' ends on the midline (inset_open)

    def boundary(self, G, i):
        nA, nB = self.nA, self.nB
        if i <= nA:
            return G[i, 0]
        if i <= nA + nB:
            return G[nA, i - nA]
        return G[2 * nA + nB - i, nB]

    def midline(self):
        ids = set(self.T[0, :].tolist()) | set(self.B[0, :].tolist()) | set(self.R[:, 0].tolist()) | \
            set(self.R[:, -1].tolist()) | set(self.extra_mid)
        return np.array(sorted(ids), int)

    def put(self, v, p, tag):
        self.P[v] = p
        self.src[int(v)] = tag

    def crease(self, ids, s, closed=False):
        ids = list(ids)
        pairs = list(zip(ids[:-1], ids[1:])) + ([(ids[-1], ids[0])] if closed else [])
        ss = np.broadcast_to(np.asarray(s, np.float64), (len(pairs),))
        for (a, b), v in zip(pairs, ss):
            if v > 0:
                self.sharp_h[(min(a, b), max(a, b))] = float(v)

    def inset(self, walk, block_ids, n_in, tag=''):
        """b4-3: INSET a port block (a pocket's walls): `walk` its boundary (half-cage ids in order round it), `block_ids` the
        boundary and every vertex it encloses; every quad with its four corners in the block is the block's. n_in new loops of
        len(walk) vertices each are put between the boundary and the block's quads (those re-pointed from the boundary onto the
        innermost loop), joined by strips of quads wound as the quads outside the boundary are, so the cage stays closed and
        consistently wound. The new vertices are appended (off the midline: the mirror takes them as any other). Returns the
        loops' ids, outer to inner"""
        walk = [int(v) for v in walk]
        K = len(walk)
        bset = {int(v) for v in block_ids}
        inq = np.array([all(int(v) in bset for v in q) for q in self.Qh])
        a, b = walk[0], walk[1]
        fwd = None
        for q in self.Qh[~inq]:
            ql = [int(v) for v in q]
            if a in ql and b in ql:
                fwd = ql[(ql.index(a) + 1) % 4] == b
                break
        if fwd is None:
            raise RuntimeError(f'{tag}: no quad outside the block holds its boundary edge {a}-{b}')
        base = self.n_half
        loops = [list(range(base + j * K, base + (j + 1) * K)) for j in range(n_in)]
        self.P = np.vstack([self.P, np.full((n_in * K, 3), np.nan)])
        self.plug = np.concatenate([self.plug, np.ones(n_in * K, bool)])
        self.n_half += n_in * K
        remap = {walk[m]: loops[-1][m] for m in range(K)}
        Qb = np.array([[remap.get(int(v), int(v)) for v in q] for q in self.Qh[inq]], int).reshape(-1, 4)
        strips = []
        rings = [walk] + loops
        for j in range(n_in):
            o, n_ = rings[j], rings[j + 1]
            for m in range(K):
                m1 = (m + 1) % K
                strips.append((o[m1], o[m], n_[m], n_[m1]) if fwd else (o[m], o[m1], n_[m1], n_[m]))
        self.Qh = np.vstack([self.Qh[~inq], Qb, np.array(strips, int)])
        return loops

    def inset_open(self, walk, block_ids, n_in, tag=''):
        """b4-3: inset() for a block cut by the midline (a cap: its boundary in the half cage an OPEN walk from the top midline to
        the bottom midline, ring 0 or ring K): the strips run between consecutive walk vertices only and each new loop's two end
        vertices are midline vertices (mirrored onto themselves: the full loop closes across x 0), so a cap becomes an O-GRID (its
        grid's corners interior vertices, not on its smooth boundary ring). Returns the loops' ids, outer to inner"""
        walk = [int(v) for v in walk]
        K = len(walk)
        bset = {int(v) for v in block_ids}
        inq = np.array([all(int(v) in bset for v in q) for q in self.Qh])
        a, b = walk[0], walk[1]
        fwd = None
        for q in self.Qh[~inq]:
            ql = [int(v) for v in q]
            if a in ql and b in ql:
                fwd = ql[(ql.index(a) + 1) % 4] == b
                break
        if fwd is None:
            raise RuntimeError(f'{tag}: no quad outside the block holds its boundary edge {a}-{b}')
        base = self.n_half
        loops = [list(range(base + j * K, base + (j + 1) * K)) for j in range(n_in)]
        self.P = np.vstack([self.P, np.full((n_in * K, 3), np.nan)])
        self.plug = np.concatenate([self.plug, np.zeros(n_in * K, bool)])
        self.n_half += n_in * K
        remap = {walk[m]: loops[-1][m] for m in range(K)}
        Qb = np.array([[remap.get(int(v), int(v)) for v in q] for q in self.Qh[inq]], int).reshape(-1, 4)
        strips = []
        rings = [walk] + loops
        for j in range(n_in):
            o, n_ = rings[j], rings[j + 1]
            for m in range(K - 1):
                m1 = m + 1
                strips.append((o[m1], o[m], n_[m], n_[m1]) if fwd else (o[m], o[m1], n_[m1], n_[m]))
            self.extra_mid += [n_[0], n_[-1]]
        self.Qh = np.vstack([self.Qh[~inq], Qb, np.array(strips, int)])
        return loops

    def full(self, P_half=None):
        """the full mesh (the half and its mirror x -> -x, welded on the midline): QuadMesh, the half -> mirror id map, the
        full sharpness dict"""
        P_half = self.P if P_half is None else P_half
        mid = self.midline()
        is_mid = np.zeros(self.n_half, bool)
        is_mid[mid] = True
        off = np.cumsum(~is_mid) - 1 + self.n_half
        mir = np.where(is_mid, np.arange(self.n_half), off)
        n = self.n_half + int((~is_mid).sum())
        V = np.zeros((n, 3))
        V[:self.n_half] = P_half
        V[mid, 0] = 0.0
        Pm = P_half.copy()
        Pm[:, 0] *= -1.0
        V[mir[~is_mid]] = Pm[~is_mid]
        Q = np.vstack([self.Qh, mir[self.Qh][:, ::-1]])
        sharp = {}
        for (a, b), s in self.sharp_h.items():
            sharp[(min(a, b), max(a, b))] = s
            sharp[(min(mir[a], mir[b]), max(mir[a], mir[b]))] = s
        return QuadMesh(V, Q), mir, sharp


# ============================================================================================ the tube cage (sided parts)
class RoundTube:
    """a sided part's FULL cage: a tube of rings of K = 4 n vertices at equal angles about its axis (counter-clockwise about the
    axis direction t: e1 x e2 = t), each end capped by an (n + 1) x (n + 1) grid whose boundary is the end ring (walked
    counter-clockwise about t); quads wind outward"""

    def __init__(self, K, nring):
        assert K % 4 == 0
        self.K, self.n, self.nr = K, K // 4, nring
        n = self.n
        self.R = np.arange(nring * K).reshape(nring, K)
        cnt = self.R.size
        self.C0 = np.full((n + 1, n + 1), -1, int)
        self.C1 = np.full((n + 1, n + 1), -1, int)
        for C, ring in ((self.C0, self.R[0]), (self.C1, self.R[-1])):
            walk = self.walk_idx()
            for j, (p, q) in enumerate(walk):
                C[p, q] = ring[j]
            for p in range(1, n):
                for q in range(1, n):
                    C[p, q] = cnt
                    cnt += 1
        self.n_v = cnt
        Q = []
        for k in range(nring - 1):
            for j in range(K):
                j1 = (j + 1) % K
                Q.append((self.R[k, j], self.R[k, j1], self.R[k + 1, j1], self.R[k + 1, j]))
        for p in range(n):
            for q in range(n):
                Q.append((self.C0[p, q], self.C0[p, q + 1], self.C0[p + 1, q + 1], self.C0[p + 1, q]))
                Q.append((self.C1[p, q], self.C1[p + 1, q], self.C1[p + 1, q + 1], self.C1[p, q + 1]))
        self.Q = np.array(Q, int)
        self.P = np.full((self.n_v, 3), np.nan)
        self.sharp = {}
        self.src = {}

    def walk_idx(self):
        n = self.n
        return [(p, 0) for p in range(n)] + [(n, q) for q in range(n)] + [(n - p, n) for p in range(n)] + \
            [(0, n - q) for q in range(n)]

    def crease(self, ids, s, closed=False):
        ids = list(ids)
        pairs = list(zip(ids[:-1], ids[1:])) + ([(ids[-1], ids[0])] if closed else [])
        ss = np.broadcast_to(np.asarray(s, np.float64), (len(pairs),))
        for (a, b), v in zip(pairs, ss):
            if v > 0:
                self.sharp[(min(a, b), max(a, b))] = float(v)


# ============================================================================================ meridian traces
def meridian_traces(gf, hc, thetas, zlo, zhi, rmax, res, log=print):
    """the part's surface in its MERIDIAN half-planes: for each angle theta (degrees, 0 = +x, 90 = up, counter-clockwise about
    +z), the surface {(r cos t, hc(z) + r sin t, z)} (hc a function of z: the axis may bend) cut by the solid, its boundary's
    trace from the axis at its back end round to the axis at its front end (the open contour touching r = 0 at both ends,
    the longest), ordered by z at its ends; returns a list of dicts (rz (n, 2), P (n, 3) plan points, s arc length)"""
    from skimage.measure import find_contours
    rs = np.arange(0.0, rmax + 1e-9, res)
    zs = np.arange(zlo, zhi + 1e-9, res)
    Rg, Zg = np.meshgrid(rs, zs, indexing='ij')
    hz = hc(zs)
    out = []
    for th in thetas:
        t = np.radians(th)
        P = np.column_stack([(Rg * np.cos(t)).ravel(), (hz[None, :] + Rg * np.sin(t)).ravel(), Zg.ravel()])
        F = gf(P).reshape(Rg.shape)
        best = None
        for C in find_contours(F, 0.0):
            rz = np.column_stack([np.interp(C[:, 0], np.arange(len(rs)), rs), np.interp(C[:, 1], np.arange(len(zs)), zs)])
            if rz[0, 0] > 2 * res or rz[-1, 0] > 2 * res:
                continue
            L = arclen(rz)[-1]
            if best is None or L > best[1]:
                best = (rz, L)
        if best is None:
            raise RuntimeError(f'{gf.name}: no axis-to-axis trace at theta {th}')
        rz = best[0]
        if rz[0, 1] > rz[-1, 1]:
            rz = rz[::-1]
        rz = rz.copy()
        rz[0, 0] = rz[-1, 0] = 0.0
        P3 = np.column_stack([rz[:, 0] * np.cos(t), hc(rz[:, 1]) + rz[:, 0] * np.sin(t), rz[:, 1]])
        out.append(dict(theta=th, rz=rz, P=P3, s=arclen(P3)))
    return out


def support_s(tr, d, s_lo=None, s_hi=None):
    """the arc length on a trace of its support point in the (r, z) direction d (a unit 2-vector (dr, dz)), within [s_lo, s_hi]"""
    rz, s = tr['rz'], tr['s']
    m = np.ones(len(s), bool)
    if s_lo is not None:
        m &= s >= s_lo
    if s_hi is not None:
        m &= s <= s_hi
    v = np.where(m, rz[:, 0] * d[0] + rz[:, 1] * d[1], -np.inf)
    j = int(np.argmax(v))
    # (the support point refined on a parabola through its neighbours)
    if 0 < j < len(s) - 1 and m[j - 1] and m[j + 1]:
        y0, y1, y2 = v[j - 1], v[j], v[j + 1]
        den = y0 - 2 * y1 + y2
        if abs(den) > 1e-12:
            f = 0.5 * (y0 - y2) / den
            f = float(np.clip(f, -1.0, 1.0))
            return float(s[j] + f * (s[j + 1] - s[j] if f > 0 else s[j] - s[j - 1]))
    return float(s[j])


def trace_at(tr, s):
    """the plan point at arc length s on a trace"""
    return np.array([np.interp(s, tr['s'], tr['P'][:, k]) for k in range(3)])


def place_on_curve(C, anchors, M):
    """M points along the dense curve C (n, 3) (C[0] is point 0, C[-1] point M - 1): anchors {i: arc length} pin points, the
    rest evenly by arc length between their anchors. Returns (M, 3) points and their parameters along C (fractional index)"""
    s = arclen(C)
    a = dict(anchors)
    a.setdefault(0, 0.0)
    a.setdefault(M - 1, float(s[-1]))
    ks = sorted(a)
    ss = np.zeros(M)
    for k0, k1 in zip(ks[:-1], ks[1:]):
        ss[k0:k1 + 1] = np.linspace(a[k0], a[k1], k1 - k0 + 1)
    if np.any(np.diff(ss) <= 0):
        raise ValueError(f'anchors out of order along the curve: {[(k, round(a[k], 3)) for k in ks]}')
    P = np.column_stack([np.interp(ss, s, C[:, k]) for k in range(3)])
    return P, np.interp(ss, s, np.arange(len(C), dtype=np.float64))


def coons(top, bot, left, right):
    """a Coons patch: top (nA+1) at v 0, bot (nA+1) at v 1, left (nB+1) at u 0, right (nB+1) at u 1 (corners shared); returns
    (nA+1, nB+1, d)"""
    nA, nB = len(top) - 1, len(left) - 1
    u = np.linspace(0, 1, nA + 1)[:, None, None]
    v = np.linspace(0, 1, nB + 1)[None, :, None]
    P = (1 - v) * top[:, None, :] + v * bot[:, None, :] + (1 - u) * left[None, :, :] + u * right[None, :, :]
    P -= ((1 - u) * (1 - v) * top[0] + u * (1 - v) * top[-1] + (1 - u) * v * bot[0] + u * v * bot[-1])
    return P


def fit_limit(mesh, sharp, levels_fit=5, levels_out=3, log=print, name='', lam=0.0, weights=None):
    """the controls whose limit surface passes through mesh.V (the targets) at the cage's vertices, and the limit mesh
    subdivided levels_out levels (subdiv_sharp: DeRose, Kass & Truong 1998 semi-sharp Catmull-Clark). lam > 0: the REGULARISED
    fit, min |W^1/2 (A V - T)|^2 + lam |D (V - T)|^2 (A the limit operator, D the cage's edge differences, W per-vertex
    weights): the controls' displacement from their targets is kept smooth, so a feature tighter than the cage spacing cannot
    make the interpolation overshoot (b4-1's venter: controls 0.3-2.7 mm off their targets, the limit folded over between rings
    0.12 mm apart); the low is then the limit at the cage's own vertices (A V), on the high by construction. Returns (the
    control cage, the limit mesh, the residual's max, the limit quads' ancestors, the low's vertices)"""
    import scipy.sparse as sps
    import scipy.sparse.linalg as spla
    t0 = time.time()
    if lam > 0.0:
        A, _ = SS.limit_operator(mesh, sharp, levels_fit)
        T = mesh.V
        E, _ = mesh.edges()
        m = len(E)
        D = sps.csr_matrix((np.r_[np.ones(m), -np.ones(m)], (np.r_[np.arange(m), np.arange(m)], np.r_[E[:, 0], E[:, 1]])),
                           shape=(m, len(T)))
        W = sps.diags(np.ones(len(T)) if weights is None else np.asarray(weights, np.float64))
        Lp = (D.T @ D).tocsc()
        lu = spla.splu((A.T @ W @ A + lam * Lp).tocsc())
        rhs = A.T @ (W @ T) + lam * (Lp @ T)
        V0 = np.column_stack([lu.solve(np.ascontiguousarray(rhs[:, k])) for k in range(3)])
        low = A @ V0
        res = float(np.abs(low - T).max())
    else:
        V0, res = SS.fit_controls(mesh, sharp, mesh.V, levels_fit)
        low = mesh.V.copy()
    cage = QuadMesh(V0, mesh.Q)
    lim, s_e, par, _ = SS.subdivide(cage, sharp, levels_out)
    log(f'[b4] {name}: {len(mesh.V)} cage vertices, {len(mesh.Q)} quads, {len(sharp)} crease edges; controls fitted '
        f'({"regularised, lam " + format(lam, "g") + ": " if lam > 0 else ""}residual {res:.1e} mm), the limit at '
        f'{levels_out} levels {len(lim.Q):,} quads, {time.time() - t0:.1f}s')
    return cage, lim, res, par, low


def quad_metrics(mesh):
    V, Q = mesh.V, mesh.Q
    e = [V[Q[:, (k + 1) % 4]] - V[Q[:, k]] for k in range(4)]
    el = np.stack([np.linalg.norm(x, axis=1) for x in e], 1)
    ang = []
    for k in range(4):
        a_, b_ = -e[(k - 1) % 4], e[k]
        cs = (a_ * b_).sum(1) / np.maximum(np.linalg.norm(a_, axis=1) * np.linalg.norm(b_, axis=1), 1e-20)
        ang.append(np.degrees(np.arccos(np.clip(cs, -1, 1))))
    n = np.cross(V[Q[:, 2]] - V[Q[:, 0]], V[Q[:, 3]] - V[Q[:, 1]])
    return dict(min_angle=np.stack(ang, 1).min(1), aspect=el.max(1) / np.maximum(el.min(1), 1e-12),
                centre=V[Q].mean(1), normal=n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-20))


def fold_dots(gf, C, N, skip=None, pad=0.02, reach=0.12):
    """the quads' normals N against the clay's own normal at their centres C projected onto it ALONG THE QUAD'S NORMAL
    (gates.quad_quality's rule, its 0.004 m start at the octopus's scale taken here as pad life mm; b4-1 projected along the
    field's gradient, which on a thin part reads the far side: the elytron is 0.27 mm thick): from C + (pad + the centre's
    depth inside the clay) N back along -N to the first crossing into the clay, the clay's normal there; where none is met (a
    truly folded quad's normal points in) the gradient at the centre's own projection judges it, as before"""
    C = np.atleast_2d(np.asarray(C, np.float64))
    N = np.atleast_2d(np.asarray(N, np.float64))
    f0 = gf(C)
    dl = pad + np.maximum(-f0, 0.0)
    out = np.full(len(C), np.nan)
    hit = gf.ray(C + dl[:, None] * N, -N, reach=float(dl.max()) + reach, step=0.004, enter=True)
    ok = np.isfinite(hit[:, 0])
    if ok.any():
        g = gf.grad(hit[ok])
        out[ok] = (N[ok] * g).sum(1) / np.maximum(np.linalg.norm(g, axis=1), 1e-12)
    if (~ok).any():
        g = gf.grad(gf.project(C[~ok], it=6))
        out[~ok] = (N[~ok] * g).sum(1) / np.maximum(np.linalg.norm(g, axis=1), 1e-12)
    if skip is not None:
        out = np.where(skip, 1.0, out)
    return out


def self_cross(lim, eps=0.01):
    """whether the limit surface crosses itself (or turns inside out): every limit vertex offset by +eps and -eps along the
    limit's vertex normal reads its side by the limit mesh's own winding number (mesh_signed); a sheet passing through
    another puts offsets on the wrong side. Returns the vertex ids whose outward / inward offsets read wrong"""
    F = lim.tris()
    n = lim.vertex_normals()
    so = mesh_signed(lim.V, F, lim.V + eps * n)
    si = mesh_signed(lim.V, F, lim.V - eps * n)
    return np.nonzero(so < 0)[0], np.nonzero(si > 0)[0]


def low_fold_dots(low, lim):
    """the LOW's quads against the HIGH it stands for: each low quad's normal against the mean of the limit surface's normals
    at its four corners (the low's vertices are the limit at the cage's own vertices: subdiv_sharp keeps the cage's vertex
    points first). A low quad is a chord of the high, its centre up to the chord's sag inside the clay (a quad over the
    elytron's fold sits 0.12 mm inside a 0.27 mm plate), so the clay's own normal at its centre can be the far side's"""
    n0 = len(low.V)
    vn = lim.vertex_normals()[:n0]
    qm = quad_metrics(low)
    ref = unit(vn[low.Q].sum(1))
    return (qm['normal'] * ref).sum(1)


def slice_tris(V, F, p0, n):
    """the segments where the plane through p0 with normal n cuts the triangles (vectorised): (m, 2, 3)"""
    d = (V - p0) @ n
    dt = d[F]
    m = (dt.min(1) < 0) & (dt.max(1) > 0)
    F, dt = F[m], dt[m]
    segs = []
    for a, b in ((0, 1), (1, 2), (2, 0)):
        da, db = dt[:, a], dt[:, b]
        c = (da > 0) != (db > 0)
        t = np.where(c, da / np.where(c, da - db, 1.0), 0.0)
        P = V[F[:, a]] + t[:, None] * (V[F[:, b]] - V[F[:, a]])
        segs.append((c, P))
    out = []
    for i in range(len(F)):
        pts = [segs[k][1][i] for k in range(3) if segs[k][0][i]]
        if len(pts) == 2:
            out.append(pts)
    return np.array(out).reshape(-1, 2, 3)


def chain_segments(S):
    """segments (m, 2, 3) chained into polylines (shared end points welded at 1e-7 mm)"""
    if not len(S):
        return []
    P = S.reshape(-1, 3)
    key = np.round(P / 1e-7).astype(np.int64)
    uq, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1, 2)
    pos = np.zeros((len(uq), 3))
    pos[inv.ravel()] = P
    adj = [[] for _ in range(len(uq))]
    for a, b in inv:
        if a != b:
            adj[a].append(b)
            adj[b].append(a)
    seen = np.zeros(len(uq), bool)
    lines = []
    for start in range(len(uq)):
        if seen[start] or not adj[start]:
            continue
        seen[start] = True
        runs = []
        for _ in range(2):
            run, cur = [], start
            while True:
                nxt = [q for q in adj[cur] if not seen[q]]
                if not nxt:
                    break
                cur = nxt[0]
                seen[cur] = True
                run.append(cur)
            runs.append(run)
        lines.append(pos[runs[1][::-1] + [start] + runs[0]])
    return lines


def edge_radius(lim, p, t, half_arc=0.06, near=0.4):
    """the limit surface's EDGE RADIUS at the crease point p (its tangent t): the section in the plane through p normal to t, the
    sharpest turning within `near` of p, a circle fitted to the section over +-half_arc mm of arc there (BEETLE_BODY_PHOTOS 7b's
    bound, the B3e checker's k01 apex rule); returns (r, the turning in degrees over the window, the apex point)"""
    V, F = lim.V, lim.tris()
    sel = np.nonzero(np.linalg.norm(V - p, axis=1) < near + 0.3)[0]
    if not len(sel):
        return np.nan, np.nan, p
    keep = np.isin(F, sel).all(1)
    S = slice_tris(V, F[keep], p, unit(t))
    lines = chain_segments(S)
    if not lines:
        return np.nan, np.nan, p
    L = min(lines, key=lambda c: np.min(np.linalg.norm(c - p, axis=1)))
    s = arclen(L)
    if s[-1] < 2 * half_arc + 0.01:
        return np.nan, np.nan, p
    ss = np.arange(0.0, s[-1], 0.002)
    C = np.column_stack([np.interp(ss, s, L[:, k]) for k in range(3)])
    tg = np.gradient(C, axis=0)
    tg /= np.maximum(np.linalg.norm(tg, axis=1, keepdims=True), 1e-12)
    w = int(round(0.01 / 0.002))
    turn = np.full(len(C), 0.0)
    turn[w:-w] = np.degrees(np.arccos(np.clip((tg[2 * w:] * tg[:-2 * w]).sum(1), -1, 1)))
    dp = np.linalg.norm(C - p, axis=1)
    cand = np.nonzero(dp < near)[0]
    if not len(cand):
        return np.nan, np.nan, p
    j = cand[np.argmax(turn[cand])]
    m = np.abs(ss - ss[j]) <= half_arc
    Pw = C[m]
    # the circle in the section plane: an algebraic (Kasa) fit in 2D coordinates
    e1 = unit(np.cross(unit(t), [0.0, 0.0, 1.0] if abs(unit(t)[2]) < 0.9 else [1.0, 0.0, 0.0]))
    e2 = np.cross(unit(t), e1)
    X = np.column_stack([(Pw - p) @ e1, (Pw - p) @ e2])
    A = np.column_stack([2 * X, np.ones(len(X))])
    sol, *_ = np.linalg.lstsq(A, (X ** 2).sum(1), rcond=None)
    r = float(np.sqrt(max(sol[2] + sol[0] ** 2 + sol[1] ** 2, 0.0)))
    t0_, t1_ = tg[np.argmax(m)], tg[len(m) - 1 - np.argmax(m[::-1])]
    return r, float(np.degrees(np.arccos(np.clip(t0_ @ t1_, -1, 1)))), C[j]


def ring_curves(T, stations):
    """the dense ring curves: stations (n_theta, K + 1) arc lengths per meridian -> (K + 1, n_theta, 3)"""
    out = np.zeros((stations.shape[1], len(T), 3))
    for j, tr in enumerate(T):
        for k in range(stations.shape[1]):
            out[k, j] = trace_at(tr, stations[j, k])
    return out


def curve_at(C, fj):
    """the dense curve C (n, 3) at fractional indices fj"""
    fj = np.clip(np.asarray(fj, np.float64), 0.0, len(C) - 1.0)
    j0 = np.minimum(np.floor(fj).astype(int), len(C) - 2)
    f = (fj - j0)[:, None]
    return (1 - f) * C[j0] + f * C[j0 + 1]


def refine_extreme(gf, p, axis_u, axis_v, plane_axis, sign_u=1.0, half=0.25, res=0.004, prefer_v=None):
    """the clay's extreme point along +sign_u axis_u in the coordinate plane through p (plane_axis held at p's value), near p:
    the zero contour of a small 2D slice, its farthest point along u (the carina's apex on a section); prefer_v: among
    points within 0.002 mm of the extreme, the one nearest this v"""
    lo2 = (p[axis_u] - half, p[axis_v] - half)
    hi2 = (p[axis_u] + half, p[axis_v] + half)
    us, vs, F = field_slice(gf, plane_axis, p[plane_axis], lo2, hi2, res)
    best = None
    for C in contours(us, vs, F):
        j = int(np.argmax(sign_u * C[:, 0]))
        if best is None or sign_u * C[j, 0] > sign_u * best[0]:
            best = C[j]
    if best is None:
        return p.copy()
    q = p.copy()
    q[axis_u], q[axis_v] = best[0], best[1]
    return q


def mesh_closest(V, F, P):
    """the closest points on the triangle mesh (V, F) to P and the unsigned distances (Warp BVH on the preferred device)"""
    import warp as wp
    dev = wp.get_preferred_device()
    m = wp.Mesh(points=wp.array(np.asarray(V, np.float32), dtype=wp.vec3, device=dev),
                indices=wp.array(np.asarray(F, np.int32).ravel(), dtype=wp.int32, device=dev))
    k = _kernels()['closest']
    P = np.asarray(P, np.float32)
    out = wp.zeros(len(P), dtype=wp.vec3, device=dev)
    wp.launch(k, dim=len(P), inputs=[m.id, wp.array(P, dtype=wp.vec3, device=dev), 1.0e3, out], device=dev)
    C = out.numpy().astype(np.float64)
    return C, np.linalg.norm(C - P, axis=1)


def mesh_signed(V, F, P):
    """the signed distance of P to the closed triangle mesh (V, F): the closest point's distance, the winding number's sign"""
    import warp as wp
    dev = wp.get_preferred_device()
    m = wp.Mesh(points=wp.array(np.asarray(V, np.float32), dtype=wp.vec3, device=dev),
                indices=wp.array(np.asarray(F, np.int32).ravel(), dtype=wp.int32, device=dev), support_winding_number=True)
    k = _kernels()['signed']
    P = np.asarray(P, np.float32)
    out = wp.zeros(len(P), dtype=wp.float32, device=dev)
    wp.launch(k, dim=len(P), inputs=[m.id, wp.array(P, dtype=wp.vec3, device=dev), 1.0e3, out], device=dev)
    return out.numpy().astype(np.float64)


_K = {}


def _kernels():
    if _K:
        return _K
    import warp as wp

    @wp.kernel
    def k_closest(mesh: wp.uint64, pts: wp.array(dtype=wp.vec3), maxd: float, out: wp.array(dtype=wp.vec3)):
        tid = wp.tid()
        q = wp.mesh_query_point_no_sign(mesh, pts[tid], maxd)
        if q.result:
            out[tid] = wp.mesh_eval_position(mesh, q.face, q.u, q.v)
        else:
            out[tid] = pts[tid]

    @wp.kernel
    def k_signed(mesh: wp.uint64, pts: wp.array(dtype=wp.vec3), maxd: float, out: wp.array(dtype=wp.float32)):
        tid = wp.tid()
        p = pts[tid]
        q = wp.mesh_query_point_sign_winding_number(mesh, p, maxd, 2.0, 0.5)
        if q.result:
            c = wp.mesh_eval_position(mesh, q.face, q.u, q.v)
            out[tid] = wp.length(p - c) * q.sign
        else:
            out[tid] = maxd
    _K['closest'] = k_closest
    _K['signed'] = k_signed
    return _K


def even_ring_stations(n, space):
    """n interval fractions over [0, 1], denser at both ends: (1 - space) even + space half-cosine"""
    k = np.arange(n + 1) / n
    return (1.0 - space) * k + space * 0.5 * (1.0 - np.cos(np.pi * k))


def port_frame(Z, X0):
    """a port's frame: Z unit, X the projection of X0 off Z, Y = Z x X"""
    Z = unit(Z)
    X = unit(np.asarray(X0, np.float64) - Z * (Z @ np.asarray(X0, np.float64)))
    return Z, X, np.cross(Z, X)


def block_walk(ii, kk):
    """a square-ring block's boundary walk in a (k, i) grid: k from kk[0] to kk[1], i from ii[0] to ii[1]: [(k, i), ...]"""
    (k0, k1), (i0, i1) = kk, ii
    w = [(k0, i) for i in range(i0, i1)] + [(k, i1) for k in range(k0, k1)] + [(k1, i) for i in range(i1, i0, -1)] + \
        [(k, i0) for k in range(k1, k0, -1)]
    return w


def cavity_rim(gc, gn, c, Z, X, K, reach=3.0, step=0.01, margin=0.04, phi=None):
    """the rim of a cavity carved into a surface: from its centre c (on the uncarved surface gn), along K equal-angle tangent
    directions (or the angles phi) in the frame (Z out, X), the first point (projected onto the uncarved surface along Z) where
    the carved field gc meets the uncarved one again, `margin` further out; returns (K, 3) and their angles"""
    Z, X, Y = port_frame(Z, X)
    phi = 2.0 * np.pi * np.arange(K) / K if phi is None else np.asarray(phi, np.float64)
    ts = np.arange(0.0, reach + 1e-9, step)
    out = np.zeros((K, 3))
    for k, ph in enumerate(phi):
        d = np.cos(ph) * X + np.sin(ph) * Y
        A = c[None, :] + ts[:, None] * d[None, :] + 0.6 * Z[None, :]
        Pn = gn.ray(A, np.tile(-Z, (len(A), 1)), reach=1.5, step=0.005, enter=True)
        ok = np.isfinite(Pn[:, 0])
        dd = np.full(len(A), 1.0)
        dd[ok] = np.abs(gc(Pn[ok]) - gn(Pn[ok]))
        outside = np.nonzero(ok & (dd < 0.002) & (ts > 0.05))[0]
        j = outside[0] if len(outside) else len(ts) - 1
        q = c + min(ts[j] + margin, reach) * d + 0.6 * Z
        out[k] = gn.ray(q[None], -Z[None], reach=1.5, step=0.005, enter=True)[0]
    return out, phi


def orient_walk(walk, fp, c0, X, Y):
    """a port's block walk ordered counter-clockwise about its Z (X, Y its tangent axes), starting at the vertex nearest angle 0"""
    ang = np.arctan2((fp - c0) @ Y, (fp - c0) @ X)
    if np.sum(np.sin(np.diff(np.unwrap(ang)))) < 0:
        walk, ang = walk[::-1], ang[::-1]
    s0 = int(np.argmin(np.abs(np.angle(np.exp(1j * ang)))))
    return walk[s0:] + walk[:s0]


def s_at_z(tr, z, s_lo, s_hi, first=True):
    """the arc length where the trace crosses plane z within [s_lo, s_hi] (the first or the last crossing)"""
    s, zz = tr['s'], tr['P'][:, 2]
    m = (s >= s_lo) & (s <= s_hi)
    idx = np.nonzero(m[:-1] & m[1:] & (np.sign(zz[:-1] - z) != np.sign(zz[1:] - z)))[0]
    if not len(idx):
        return None
    j = idx[0] if first else idx[-1]
    f = (z - zz[j]) / (zz[j + 1] - zz[j])
    return float(s[j] + f * (s[j + 1] - s[j]))


def section_hole_centroid(gf, z, lo2, hi2, res=0.01):
    """the area centroid (x, h) of the HOLE in the clay's section at z (a socket), from a 2D slice (full width: the grid mirrors)"""
    us, vs, F = field_slice(gf, 2, z, lo2, hi2, res)
    best = None
    for C in contours(us, vs, F):
        a = poly_area(C)
        # (a hole is wound the other way round from the outer boundary; the inside of a hole is air: F > 0 at its centroid)
        cx, cy = C.mean(0)
        inside_air = gf(np.array([[cx, cy, z]]))[0] > 0
        if inside_air and (best is None or abs(a) > abs(best[1])):
            best = (C, a)
    if best is None:
        raise RuntimeError(f'{gf.name}: no hole in the section at z {z}')
    C = best[0]
    x, y = C[:, 0], C[:, 1]
    cr = x * np.roll(y, -1) - np.roll(x, -1) * y
    A = 0.5 * cr.sum()
    return np.array([((x + np.roll(x, -1)) * cr).sum() / (6 * A), ((y + np.roll(y, -1)) * cr).sum() / (6 * A)]), C


# ============================================================================================ THE PRONOTUM
# The pronotum (arthropod_parts.pronotum_descs: a loft through 40 station sections, the CARINA the margin's ridge, the hypomeron
# set in under it; the hind angles cut; the head's SOCKET carved by the head shrunk by HEAD_SINK, blended COLLAR_K: at the front
# the shell is a COLLAR round the head's back, its top a thin LIP over it from z -9.2 at the midline, the socket opening to the
# side between the lip's end (z -9.95) and the ANTERIOR ANGLE's tip (z -9.05), the front face a crescent below; the procoxae's
# sockets in the underside). The cage is a tube of MERIDIAN TRACES about the line (x 0, h hc): each trace runs from the axis on
# the hind face over the hind margin, the outer surface and the anterior margin round into the socket to its floor; rings
# stand at stations along every trace (R0 the HIND MARGIN, the 45 deg support point backward-outward; R n_out the ANTERIOR
# MARGIN, forward-outward: over the top the lip's edge, at the side the socket opening's edge, then the anterior angle, below
# the front face's outer edge; then the front face / the socket's wall to the NECK ring at z_neck and the deep ring at z_deep,
# the floor's rim); each ring's points by arc length with the features as anchors (the carina, its lip and cove, the
# procoxal port's columns), the front rings turning to equal angles by the neck ring (CROSSBREED §2.2).
PRON_CAGE = dict(nA=8, nB=8, n_out=23, n_f1=4, n_f2=1, z_neck=-10.55, z_deep=-10.75, theta_step=1.0,
                 # (b4-3: n_out 24 -> 23 and n_f1 3 -> 4: a ring moved from the outer run (0.35 -> 0.36 mm apart) onto the
                 # socket's side wall, the budget kept)
                 # (n_f2 1: the B cap spans the socket's bowl from the deep ring; b4 p2's deep ring at -10.80 behind two rings
                 # left a cap of 0.3 mm quads on a nearly flat floor, its fit overshooting 1.2 mm behind the floor)
                 # (M 25, the ring's 48 vertices at 7.5 deg on the neck ring and the deep one; nA 8 puts the caps' corners at
                 # +-30 deg: the hind face's top-lateral corner, and nearer the socket floor's narrow ends (an oval 9.5 x 3.8
                 # mm: its corners at 45 deg sat on its smooth long side, the corner quads 6-7 deg, b4 p3); b4-1 p1's M 21 with
                 # 32 outer rings made quads 0.3 x 1.1 mm: aspect p99 7.7)
                 # (z_neck: behind the anterior margin everywhere: at the socket's side opening (theta 12-27 deg, between the
                 # lip's end and the anterior angle) the margin stands back at z -9.91, p05; n_f1 3: the front face's middle and
                 # the SOCKET RIM where the front face lies (the crescent below the head; its 2 mm in one interval made quads of
                 # aspect 7, b4 p3), else a third and two thirds of the way to the neck)
                 hind_band=0.30,         # the hind margin sought within this much of the hind face's plane (else the
                 #                         45 deg support point jumps forward to the hind angle's tip on the cut face, p05)
                 res=0.02, rmax=9.6, zlo=-18.9, zhi=-8.6, space=0.15,
                 i_car=12, i_lip=13, i_cove=14, car_window=(-55.0, 45.0), cove_arc=1.4,
                 # (b4-2: 12 intervals over the disc (0.8 mm), 5 from the cove down the hypomeron to the port, 3 across the
                 # cavity, 2 to the midline: b4-1's 13 / 2 / 6 / 1 left the hypomeron's run 1.8-2.3 mm a quad, aspect 7)
                 car_z=(-17.45, -17.05),  # the carina's crease faded in over this z: behind it the hind angle's oblique cut
                 #                          face (PRON's 0.90 / 0.97 cut stations, z -17.20 / -17.77) has no edge
                 # the procoxal port: the underside's columns cox_cols anchored on every outer ring at cox_pad outside the
                 # cavity's measured footprint (lateral and medial), 4 intervals across it, the rest of the underside by arc
                 # length; the block those columns x the rings round the footprint (a teardrop ~1 x 2.5 mm, 0.3-0.5 mm deep,
                 # under the coxa); b4-3: an INSET pocket (port_pocket, the venter's): its rim at each vertex's own angle
                 # (cox_margin outside it, creased cox_rim_s), one wall loop at cox_insets of its depth, the floor; the GRAFT
                 # RING is the legs round's coxa sleeve (arthropod_cage). (b4-1 anchored 6 columns over the 1.5 mm cavity:
                 # the underside's other intervals 2.3-3.4 mm, aspect 18; a loop at equal angles twisted the block's corners
                 # and its wall ring folded: 1,254 limit folds; b4-2's plug laid flat on the dimple: the fore coxa sank 0.417)
                 cox_cols=(19, 22), cox_pad=0.15, cox_margin=0.03, cox_insets=(0.5,), cox_rim_s=1.5,
                 fit_w=dict(plug=1.0, socket=20.0),      # the regularised fit's weights there (run_b4: the rest 1; b4-3:
                 #                                         the socket held, b4-2's 1 let its wall stand 0.1 proud: the head
                 #                                         sank 0.414, c0)
                 # SHARPNESS (DKT): the carina's limit radius at most M1l's 0.10 (BEETLE_BODY_PHOTOS 7b: the pronotal carina one
                 # unresolved 62 um line, r <= 0.10 (0.083)); the hind and anterior margins the same class [E: the marginal bead,
                 # unmeasured]; over the lip and the socket opening's edge the clay's COLLAR_K blend rounds it [E]; the socket
                 # rim (a blend) lightly, where a front face lies; the coxal cavity's rim (a hard carve)
                 sharp=dict(carina=3.0, hind=3.5, ant_face=3.5, ant_lip=1.5, ant_lip_theta=(8.0, 30.0), rim=1.5,
                            corner_turn=(25.0, 55.0), corner_min=0.4))


def build_pronotum(R, grids, log=print):
    """the pronotum's half cage on the clay (the module's PRON_CAGE comment): returns dict(cage TubeCage with targets, creases,
    loops and the port; T traces; stations; hc; the neck / port records' raw data)"""
    pc = PRON_CAGE
    t0 = time.time()
    g, gn = grids['pron'], grids['pron_nc']
    # the meridians' axis at the NECK section's hole centroid (the neck ring's vertices at equal angles about its centroid)
    cn, hole = section_hole_centroid(g, pc['z_neck'], (-8.2, 5.5), (8.2, 14.0))
    hc = float(cn[1])
    th = np.arange(90.0, -90.0 - 1e-9, -pc['theta_step'])
    T = meridian_traces(gn, lambda z: np.full_like(np.asarray(z, np.float64), hc), th, pc['zlo'], pc['zhi'], pc['rmax'],
                        pc['res'])
    nt = len(T)
    n_out, n_f1, n_f2 = pc['n_out'], pc['n_f1'], pc['n_f2']
    K = n_out + n_f1 + n_f2
    k_neck = n_out + n_f1
    d_hm, d_am = np.array([1.0, -1.0]) / np.sqrt(2.0), np.array([1.0, 1.0]) / np.sqrt(2.0)
    U = even_ring_stations(n_out, pc['space'])
    ST = np.zeros((nt, K + 1))
    anch = np.zeros((nt, 4))
    face_w = np.zeros(nt)
    for j, tr in enumerate(T):
        se = tr['s'][-1]
        zb = tr['P'][0, 2]
        off = np.nonzero(tr['P'][:, 2] > zb + pc['hind_band'])[0]
        sh = support_s(tr, d_hm, s_hi=tr['s'][off[0]] if len(off) else 0.5 * se)
        sa = support_s(tr, d_am, s_lo=sh)
        sn = s_at_z(tr, pc['z_neck'], sa, se)
        sd = s_at_z(tr, pc['z_deep'], sn, se) if sn is not None else None
        if sn is None or sd is None:
            raise RuntimeError(f'pronotum: the trace at theta {tr["theta"]} never reaches the neck / deep planes')
        # the socket rim: where the trace past the margin leaves the front face's plane (the crescent below the head; over the
        # lip and at the socket's side opening the trace turns back at once, so half way to the neck there)
        za = trace_at(tr, sa)[2]
        ss_ = np.linspace(sa, sn, 400)
        zz_ = np.array([trace_at(tr, q)[2] for q in ss_])
        back = np.nonzero(zz_ < za - 0.08)[0]
        L_ = sn - sa
        s_rim = float(ss_[back[0]]) if len(back) else sa + 0.5 * L_
        face_w[j] = float(smooth01(((s_rim - sa) / L_ - 0.15) / 0.2))      # 1 where a front face lies before the rim
        anch[j] = (sh, sa, sn, sd)
        ST[j, :n_out + 1] = sh + U * (sa - sh)
        if n_f1 in (3, 4):
            # the face's middle and its rim where the face lies; a third and two thirds of the way elsewhere, blended by face_w;
            # (n_f1 4, b4-3: one more ring half way down the socket's wall from the rim to the neck ring: with 3 a quad spanned
            # the side wall's bulge behind the side opening, 1.9 mm, the limit stood 0.2 into the socket, the head sank 0.42, c7)
            s_r = face_w[j] * min(s_rim, sn - 0.15 * L_) + (1 - face_w[j]) * (sa + (2.0 / 3.0) * L_)
            if n_f1 == 4:
                s_r = face_w[j] * min(s_rim, sn - 0.3 * L_) + (1 - face_w[j]) * (sa + 0.45 * L_)
                ST[j, n_out:k_neck + 1] = (sa, 0.5 * (sa + s_r), s_r, 0.5 * (s_r + sn), sn)
            else:
                ST[j, n_out:k_neck + 1] = (sa, 0.5 * (sa + s_r), s_r, sn)
        elif n_f1 == 2:
            ST[j, n_out:k_neck + 1] = (sa, min(max(s_rim, sa + 0.5 * L_), sn - 0.25 * L_), sn)
        else:
            ST[j, n_out:k_neck + 1] = sa + np.linspace(0.0, 1.0, n_f1 + 1) * (sn - sa)
        ST[j, k_neck:] = sn + np.linspace(0.0, 1.0, n_f2 + 1) * (sd - sn)
    C = ring_curves(T, ST)
    log(f'[b4] pronotum: {nt} meridian traces about (x 0, h {hc:.3f}) (the neck section\'s hole centroid), stations placed, '
        f'{time.time() - t0:.1f}s')
    # the PROCOXAL CAVITY's footprint on the uncarved underside (the carved clay off the uncarved where they differ): rays from
    # below over the underside
    xs_, zs_ = np.arange(0.05, 4.0, 0.04), np.arange(-18.0, -11.0, 0.04)
    Xg, Zg = np.meshgrid(xs_, zs_, indexing='ij')
    A0 = np.column_stack([Xg.ravel(), np.full(Xg.size, -0.5), Zg.ravel()])
    Pu = gn.ray(A0, np.tile([0.0, 1.0, 0.0], (len(A0), 1)), reach=8.0, step=0.02, enter=True)
    ok_ = np.isfinite(Pu[:, 0])
    cav = np.zeros(len(A0), bool)
    cav[ok_] = (g(Pu[ok_]) - gn(Pu[ok_])) > 0.005
    if not cav.any():
        raise RuntimeError('pronotum: the procoxal cavity was not found on the underside')
    Pc_ = Pu[cav]
    cav_x, cav_z, cav_c = (Pc_[:, 0].min(), Pc_[:, 0].max()), (Pc_[:, 2].min(), Pc_[:, 2].max()), Pc_.mean(0)
    x_lat, x_med = cav_x[1] + pc['cox_pad'], max(cav_x[0] - pc['cox_pad'], 0.3)
    log(f'[b4] pronotum: the procoxal cavity x {cav_x[0]:.2f}..{cav_x[1]:.2f}, z {cav_z[0]:.2f}..{cav_z[1]:.2f}; the port\'s '
        f'columns at x {x_lat:.2f} / {x_med:.2f} on every ring')
    cage = TubeCage(pc['nA'], pc['nB'], K)
    M = cage.M
    j_of = np.zeros((K + 1, M))
    pos = np.zeros((K + 1, M, 3))
    i_car, i_lip, i_cove = pc['i_car'], pc['i_lip'], pc['i_cove']
    j_eq = 180.0 * np.arange(M) / (M - 1) / pc['theta_step']        # equal angles: theta_i = 90 - 180 i / (M - 1)
    for k in range(K + 1):
        Ck = C[k]
        s_ = arclen(Ck)
        if k <= n_out:
            # the ring points in ANGLE (fractional meridian index) space: equal angles, with the features as anchors (the
            # carina at the section's widest point, its lip and cove below it, the procoxal port's columns), linear in the
            # index between anchors
            jw = np.nonzero((th <= pc['car_window'][1]) & (th >= pc['car_window'][0]))[0]
            jc = jw[np.argmax(Ck[jw, 0])]
            sc = s_[jc]
            below = np.nonzero((s_ > sc) & (s_ < sc + pc['cove_arc']))[0]
            jv = below[np.argmin(Ck[below, 0])] if len(below) else min(jc + 3, nt - 1)
            sv = max(s_[jv], sc + 0.15)
            fjs = lambda sq: float(np.interp(sq, s_, np.arange(nt, dtype=np.float64)))   # noqa: E731
            an = {0: 0.0, M - 1: float(nt - 1), i_car: float(jc), i_lip: fjs(0.5 * (sc + sv)), i_cove: fjs(sv)}
            ks_ = sorted(an)
            fj = np.interp(np.arange(M), ks_, [an[q] for q in ks_])
            # (b4-2: the UNDERSIDE by arc length in three runs, the cove to the port's lateral column, across the cavity to its
            # medial column, then to the bottom midline: b4-1 anchored 6 of the 9 intervals over the cavity's 1.5 mm, so the
            # hypomeron and the prosternum's sides took 2 intervals of 2.3-3.4 mm, aspect 18)
            i0c, i1c = pc['cox_cols']
            s_x = []
            for xv in (x_lat, x_med):
                cr_ = np.nonzero((Ck[:-1, 0] - xv) * (Ck[1:, 0] - xv) <= 0)[0]
                cr_ = cr_[s_[cr_] > sv + 0.2]
                if not len(cr_):
                    raise RuntimeError(f'pronotum ring {k}: no crossing of x {xv:.2f} on the underside')
                jj = cr_[-1]
                f_ = (xv - Ck[jj, 0]) / (Ck[jj + 1, 0] - Ck[jj, 0])
                s_x.append(float(s_[jj] + f_ * (s_[jj + 1] - s_[jj])))
            s_run = np.concatenate([np.linspace(sv, s_x[0], i0c - i_cove + 1)[:-1], np.linspace(s_x[0], s_x[1], i1c - i0c + 1)[:-1],
                                    np.linspace(s_x[1], s_[-1], M - i1c)])
            fj[i_cove:] = np.interp(s_run, s_, np.arange(nt, dtype=np.float64))
            if np.any(np.diff(fj) <= 0):
                raise RuntimeError(f'pronotum ring {k}: anchors out of order {[(q, round(an[q], 2)) for q in ks_]}')
            P = curve_at(Ck, fj)
            if k == n_out:
                fj_am = fj.copy()
        else:
            w = min((k - n_out) / n_f1, 1.0)
            fj = (1.0 - w) * fj_am + w * j_eq
            P = curve_at(Ck, fj)
        j_of[k], pos[k] = fj, P
    # the CARINA's apex refined on the clay's own section at each outer ring (the dense curve's 1 deg chords cut its corner)
    for k in range(n_out + 1):
        pos[k, i_car] = refine_extreme(g, pos[k, i_car], 0, 1, 2, sign_u=1.0)
    for k in range(K + 1):
        for i in range(M):
            tag = ('R0 the hind margin (45 deg support point)' if k == 0 else
                   'the anterior margin (45 deg support point)' if k == n_out else
                   f'the neck ring z {pc["z_neck"]} (equal angles)' if k == k_neck else
                   f'the deep ring z {pc["z_deep"]}' if k == K else
                   'the outer surface (meridian stations)' if k < n_out else 'the front face / the socket wall')
            if i == i_car and k <= n_out:
                tag = 'the CARINA (the section\'s widest point, refined on the clay)'
            cage.put(cage.R[k, i], pos[k, i], tag)
    # ---- the T cap (the hind face) and the B cap (the socket's floor): Coons in (x, h), then onto the clay along z
    nA, nB = cage.nA, cage.nB
    for capG, kr, z0, dz, tag in ((cage.T, 0, None, 1.0, 'the hind face (T cap)'), (cage.B, K, None, -1.0,
                                                                                    'the socket floor (B cap)')):
        ring = pos[kr]
        top = ring[0:nA + 1]
        right = ring[nA:nA + nB + 1]
        bot = ring[nA + nB:M][::-1]
        hl = np.linspace(ring[0, 1], ring[M - 1, 1], nB + 1)
        left = np.column_stack([np.zeros(nB + 1), hl, np.linspace(ring[0, 2], ring[M - 1, 2], nB + 1)])
        PP = coons(top, bot, left, right)
        for a in range(nA + 1):
            for b in range(nB + 1):
                v = capG[a, b]
                if a in (0,) and b in (0, nB) or a == nA or b in (0, nB):
                    if not np.isnan(cage.P[v, 0]):
                        continue
                p = PP[a, b].copy()
                if a == 0:
                    p[0] = 0.0
                if dz > 0:
                    A_ = np.array([[p[0], p[1], ring[:, 2].min() - 0.6]])
                    q = g.ray(A_, np.array([[0.0, 0.0, 1.0]]), reach=2.0, step=0.005, enter=True)[0]
                else:
                    A_ = np.array([[p[0], p[1], ring[:, 2].max() + 0.25]])
                    q = g.ray(A_, np.array([[0.0, 0.0, -1.0]]), reach=2.0, step=0.005, enter=True)[0]
                if not np.isfinite(q[0]):
                    raise RuntimeError(f'pronotum {tag}: no surface under ({p[0]:.3f}, {p[1]:.3f})')
                cage.put(v, q, tag)
    # ---- the PROCOXAL CAVITY: an inset port in the underside (port_pocket): its columns the anchored ones (cox_cols), its rings
    # the outer rings round the footprint's z (one outside each end)
    i0, i1 = pc['cox_cols']
    zr_ = pos[:n_out + 1, (i0 + i1) // 2, 2]
    k_a = int(np.nonzero(zr_ < cav_z[0] - 0.05)[0].max())
    k_b = int(np.nonzero(zr_ > cav_z[1] + 0.05)[0].min())
    sp = pc['sharp']
    # (b4-3: an INSET pocket as the venter's, one wall loop: b4-2's plug laid flat on the dimple left its limit 0.13 mm shallow
    # and the fore coxa sank 0.417 at the fit's weight 1, while holding the plug overshot: 42 limit folds, c10)
    po_ = port_pocket(cage, g, gn, (i0, i1), (k_a, k_b), 'the procoxal pocket', 'procoxa_L', 'pronotum', pc['cox_insets'],
                      pc['cox_margin'], pc['cox_rim_s'], cav_c)
    rim_loop = cage.P[po_['walk']]
    rim_in = []
    rim = rim_loop
    # ---- creases: the carina (faded in ahead of the hind angle's cut face), the hind margin, the anterior margin (lighter over
    # the lip and the socket's side opening), the socket rim where a front face lies
    zc = np.array([cage.P[cage.R[k, i_car], 2] for k in range(n_out + 1)])
    zm = 0.5 * (zc[:-1] + zc[1:])
    s_car = sp['carina'] * smooth01((zm - pc['car_z'][0]) / (pc['car_z'][1] - pc['car_z'][0]))
    cage.crease([cage.R[k, i_car] for k in range(n_out + 1)], s_car)

    def corner_ease(ring_ids):
        """per edge of a crease ring: 1, falling to sp['corner_min'] where the ring turns sharply (its turn over the two
        vertices beyond corner_turn deg: the hind angle, the anterior angle), so a creased loop does not fold the limit as
        it turns the corner (b4-2: 5-8 limit quads folded at each at s 3.1-3.5)"""
        Pr = cage.P[np.asarray(ring_ids)]
        d1 = unit(np.gradient(Pr, axis=0))
        turn = np.degrees(np.arccos(np.clip((np.roll(d1, -1, 0) * np.roll(d1, 1, 0)).sum(1), -1, 1)))
        turn[0], turn[-1] = turn[1], turn[-2]
        tv = smooth01((turn - sp['corner_turn'][0]) / (sp['corner_turn'][1] - sp['corner_turn'][0]))
        te = np.maximum(tv[:-1], tv[1:])
        return 1.0 - (1.0 - sp['corner_min']) * te
    cage.crease(cage.R[0], sp['hind'] * corner_ease(cage.R[0]))
    tha = 90.0 - j_of[n_out] * pc['theta_step']
    tm = 0.5 * (tha[:-1] + tha[1:])
    lo_, hi_ = sp['ant_lip_theta']
    s_am = sp['ant_face'] + (sp['ant_lip'] - sp['ant_face']) * smooth01((tm - lo_) / (hi_ - lo_))
    cage.crease(cage.R[n_out], s_am * corner_ease(cage.R[n_out]))
    k_rim = n_out + (2 if n_f1 in (3, 4) else 1)
    jr = j_of[k_rim]
    fw = np.interp(0.5 * (jr[:-1] + jr[1:]), np.arange(nt, dtype=np.float64), face_w)
    cage.crease(cage.R[k_rim], sp['rim'] * fw)
    cage.loops = {'R0 hind margin': cage.R[0].tolist(), 'carina': [int(cage.R[k, i_car]) for k in range(n_out + 1)],
                  'anterior margin': cage.R[n_out].tolist(), 'socket rim': cage.R[k_rim].tolist(),
                  'neck ring': cage.R[k_neck].tolist(), 'deep ring': cage.R[K].tolist(),
                  'procoxal port L': cage.ports['procoxa_L']['walk'], 'procoxal rim L': rim_in}
    assert not np.isnan(cage.P).any(), 'pronotum: a cage vertex without a target'
    log(f'[b4] pronotum: the half cage {cage.n_half} vertices (M {M}, K {K}: {n_out} outer rings, the anterior margin, '
        f'{n_f1} to the neck ring, {n_f2} to the deep ring), the procoxal port on rings {k_a}..{k_b} x points {i0}..{i1}, '
        f'{time.time() - t0:.1f}s')
    return dict(cage=cage, T=T, stations=ST, anchors=anch, hc=hc, k_neck=k_neck, n_out=n_out, K=K, j_of=j_of,
                hole=hole, rim=rim)


# ============================================================================================ THE ELYTRON
# The clay's elytron is a SHELL of half-thickness ht (body.ely_plate / 2 = 0.135) round a mid-surface patch
# (arthropod_parts.elytron_patch: rows along z from the base to the apex, each the section from the sutural edge over the dome
# (a superellipse quadrant, ELY_SE) down to the lateral MARGIN, where it folds 90 deg inward into the EPIPLEURON), so its outer
# surface is the patch offset by +ht, its inner by -ht, and round its boundary a half-round rim of radius ht; at the margin the
# outer surface turns round the fold on an arc of radius ht, the inner one meets in a concave corner.
# THE LAYOUT (b4-2). In plan the dome is a region of THREE corners: the scutellar corner (the base meets the sutural edge), the
# humeral angle (the base meets the margin) and the SUTURAL ANGLE at the apex (BEETLE_BODY_PHOTOS 7c: the pair's outline one
# broad arc meeting the suture almost square; the clay's last row is 0.6 mm across). One (row, column) grid over it ends in
# columns 0.03 mm apart (b4-1: the low's aspect max 70.8, its apex quads folded). So the dome is three quad patches meeting at
# one valence-3 vertex P_O in the apex region (a Y): Q1 (the sutural part: the base's first n1 intervals, the sutural edge,
# the split line, the Y's left arm) and Q2 (the lateral part: the base's last n2, the split line, the margin, the right arm)
# make one grid of transverse rows and longitudinal columns over the body (the dome's principal directions); Q3 (n2 x n1) is
# the apex, its sides the two arms, the margin's last stretch round the apex (the last row included) and the sutural edge's
# last ELY_CAGE tip_suture mm; the arms leave P_O at +-arm_deg from the split line's backward direction (120 deg apart).
# Each patch is a Coons patch in a CHART (z, a) (ElyChart: z the row's plan z, a the arc length across the row from the sutural
# edge), its sides spaced evenly by 3D arc length. The EPIPLEURON is one column of quads along the margin from the base to the
# margin's end. The RIM is one loop of crest vertices on the half-round round the whole boundary (the base, the epipleuron's
# inner edge and its end, the last row, the sutural edge). Every face vertex lies on the clay exactly (the patch's point +- ht
# along its normal; at the fold the outer arc's middle and the inner corner); the right elytron is the left's exact mirror.
ELY_CAGE = dict(n1=12, n2=6, n6=41, tip_suture=3.5, arm_deg=60.0, kz=1.12,
                # THE EPIPLEURON'S END (the one clay fix of this round): elytron_patch folds every row's last points toward
                # -x (ELY_EPI wide, narrowing over the last 4 mm); where the margin runs along z that is the inflexed
                # margin, but over the apex's last ~3 mm the margin turns past 45 deg toward the suture, so those points
                # lie ALONG the margin and the shell round them is a lump with a fin (b4-2's strip followed them to the
                # tip: a fin standing up over the dome, two folds of the low, 335 limit folds). Rebuilt as a flange
                # perpendicular to the margin it runs under the apex's dome, which there stands only ~0.2 mm over the
                # margin, and the plate's two faces cross (158 limit vertices, p15). So the strip ENDS where the clay's
                # epipleuron narrows under epi_min (z ~ -40.9), square (eased toward its end, taper_end < 1, the strip
                # grew thinner than the plate and its faces crossed: 34 vertices at taper_end 0.4); past it the plate's rim
                # runs along the margin. The gates read the shell round the clay's patch with the same end (its epipleuron
                # cells dropped behind the end), the departure from the whole clay printed beside them
                epi_min=0.6, taper_segs=3, taper_end=1.0, notch_steps=2, notch_w=1.0,
                # SHARPNESS: the MARGIN (the fold) creased on the outer face toward the clay's radius ht there (the ~0.55 mm
                # columns alone round it wider) and on the inner face (the clay's concave corner); the rim none (its crest
                # vertex holds the half-round; the elytral edges' radii are not measured on the photos [E: the clay's ht])
                sharp=dict(margin_out=1.5, margin_in=2.0, rim=0.0, notch=0.0))


def elytron_grid(R):
    """the clay's mid-surface patch as (ns, nt, 3) plan points and its one-sided normals (outward: up on the dome, out on the
    side wall, down under the epipleuron)"""
    d = R['descs']['elytron'][0]
    ely = R['elytron']
    ns = len(ely['zs'])
    V = np.asarray(d['V'], np.float64).copy()
    V[:, 1] -= R['clear']
    nt = len(V) // ns
    G = V.reshape(ns, nt, 3)
    # the margin column: elytron_patch's dome is nd points (0 .. nd - 1, the last ON the fold at the row's widest x, wm), then the
    # epipleuron's points fold inward: the fold is each row's widest point
    c_m = int(np.bincount(np.argmax(G[ns // 8: ns - ns // 8, :, 0], axis=1)).argmax())
    return G, ely, c_m


class ElyChart:
    """the clay elytron's mid-surface as a chart: (z, a) on the dome (z the row's plan z, a the arc length across the row from
    the sutural edge; the fold at a = A(z)) and (z, t) on the epipleuron (t 0 at the fold, 1 at its inner edge). Points and
    one-sided normals from bicubic splines over the patch's (row, column) grid, the dome's and the epipleuron's apart (the fold is
    a corner)"""

    def __init__(self, R):
        G, ely, c_m = elytron_grid(R)
        ns, nt = G.shape[:2]
        self.G, self.ely, self.c_m, self.ns, self.nt = G.copy(), ely, c_m, ns, nt
        self.ht = float(ely['ht'])
        self.rr = np.arange(ns, dtype=np.float64)
        self.zs = G[:, 0, 2].copy()
        self._tables()

    def _tables(self):
        """the splines, arc tables and normals of the (current) patch"""
        from scipy.interpolate import RectBivariateSpline
        G, c_m, ns, nt = self.G, self.c_m, self.ns, self.nt
        cc = np.arange(nt, dtype=np.float64)
        self.spl_d = [RectBivariateSpline(self.rr, cc[:c_m + 1], G[:, :c_m + 1, k], kx=3, ky=3) for k in range(3)]
        self.spl_e = [RectBivariateSpline(self.rr, cc[c_m:], G[:, c_m:, k], kx=3, ky=min(3, nt - c_m - 1))
                      for k in range(3)]
        seg = np.linalg.norm(np.diff(G, axis=1), axis=2)
        self.ad = np.concatenate([np.zeros((ns, 1)), np.cumsum(seg[:, :c_m], 1)], 1)          # (ns, c_m + 1)
        self.ae = np.concatenate([np.zeros((ns, 1)), np.cumsum(seg[:, c_m:], 1)], 1)          # (ns, nt - c_m)
        self.A, self.E = self.ad[:, -1].copy(), self.ae[:, -1].copy()
        # the NORMALS from the patch's own points (differences across and along its grid, one-sided at its edges and on the
        # fold), read bilinearly: elytron_patch spaces its rows by a cosine, so at the base and the apex the rows almost
        # coincide and the spline's row derivative there is noise (b4-2's first build: the base row's normals pointed
        # forward, its inner face vertices lay on the mid-surface, the base rim folded)
        gn = lambda B: unit(np.cross(np.gradient(B, axis=1), np.gradient(B, axis=0)))        # noqa: E731
        self.Nd, self.Ne = gn(G[:, :c_m + 1]), gn(G[:, c_m:])

    def ease_epipleuron(self, z0, z1, f_end):
        """the epipleuron's width eased (each row's epipleuron points drawn toward the fold) from 1 at z0 to f_end at z1 and held
        there behind z1 (ELY_CAGE: the strip's end); the tables rebuilt"""
        f = 1.0 - (1.0 - f_end) * smooth01((z0 - self.zs) / max(z0 - z1, 1e-9))
        c_m = self.c_m
        self.G[:, c_m + 1:] = self.G[:, c_m][:, None, :] + f[:, None, None] * (self.G[:, c_m + 1:] - self.G[:, c_m][:, None, :])
        self._tables()

    def row(self, z):
        return np.interp(-np.asarray(z, np.float64), -self.zs, self.rr)

    def A_of(self, z):
        return np.interp(self.row(np.atleast_1d(np.asarray(z, np.float64))), self.rr, self.A)

    def _rc(self, z, frac, table, total, c0):
        z, frac = np.broadcast_arrays(np.atleast_1d(np.asarray(z, np.float64)), np.atleast_1d(np.asarray(frac, np.float64)))
        r = self.row(z)
        r0 = np.clip(np.floor(r).astype(int), 0, self.ns - 2)
        f = r - r0
        cols = c0 + np.arange(table.shape[1], dtype=np.float64)
        q = np.clip(frac, 0.0, 1.0)
        c = np.array([(1.0 - f_) * np.interp(q_ * total[i], table[i], cols) +
                      f_ * np.interp(q_ * total[i + 1], table[i + 1], cols) for i, f_, q_ in zip(r0, f, q)])
        return r, c

    def rc_dome(self, z, a):
        """the (row, column) of the dome's point (z, a): a as the fraction of the row's arc, the column by arc length in the
        rows either side, blended"""
        z = np.atleast_1d(np.asarray(z, np.float64))
        return self._rc(z, np.asarray(a, np.float64) / np.maximum(self.A_of(z), 1e-9), self.ad, self.A, 0.0)

    def rc_epi(self, z, t):
        return self._rc(z, t, self.ae, self.E, float(self.c_m))

    def at(self, r, c, epi=False):
        """points, unit outward normals (up on the dome, out on the side wall, down under the epipleuron) and the row /
        column derivatives at (r, c)"""
        sp = self.spl_e if epi else self.spl_d
        r, c = np.atleast_1d(r).astype(np.float64), np.atleast_1d(c).astype(np.float64)
        P = np.stack([s.ev(r, c) for s in sp], -1)
        Dr = np.stack([s.ev(r, c, dx=1) for s in sp], -1)
        Dc = np.stack([s.ev(r, c, dy=1) for s in sp], -1)
        Nn = self.Ne if epi else self.Nd
        cr = c - (self.c_m if epi else 0.0)
        r0 = np.clip(np.floor(r).astype(int), 0, self.ns - 2)
        c0 = np.clip(np.floor(cr).astype(int), 0, Nn.shape[1] - 2)
        fr, fc = np.clip(r - r0, 0.0, 1.0)[:, None], np.clip(cr - c0, 0.0, 1.0)[:, None]
        n = (1 - fr) * (1 - fc) * Nn[r0, c0] + (1 - fr) * fc * Nn[r0, c0 + 1] + fr * (1 - fc) * Nn[r0 + 1, c0] + \
            fr * fc * Nn[r0 + 1, c0 + 1]
        return P, unit(n), Dr, Dc

    def dome3(self, z, a):
        r, c = self.rc_dome(z, a)
        return self.at(r, c)[0]

    def even(self, Zd, Ad, n):
        """n + 1 chart points along the dense chart curve (Zd, Ad), evenly spaced by 3D arc length on the dome"""
        s = arclen(self.dome3(Zd, Ad))
        t = np.linspace(0.0, s[-1], n + 1)
        return np.column_stack([np.interp(t, s, Zd), np.interp(t, s, Ad)])


def orient_quads(Q):
    """the quads' windings made consistent (each shared edge run once each way) by a breadth-first walk across shared edges;
    the global sign is the caller's"""
    from collections import deque
    Q = np.array(Q, np.int64)
    edge_q = {}
    for f in range(len(Q)):
        for k in range(4):
            a, b = int(Q[f, k]), int(Q[f, (k + 1) % 4])
            edge_q.setdefault((min(a, b), max(a, b)), []).append(f)
    seen = np.zeros(len(Q), bool)
    for s0 in range(len(Q)):
        if seen[s0]:
            continue
        seen[s0] = True
        dq = deque([s0])
        while dq:
            f = dq.popleft()
            for k in range(4):
                a, b = int(Q[f, k]), int(Q[f, (k + 1) % 4])
                for g in edge_q[(min(a, b), max(a, b))]:
                    if g == f or seen[g]:
                        continue
                    if any(int(Q[g, j]) == a and int(Q[g, (j + 1) % 4]) == b for j in range(4)):
                        Q[g] = Q[g, ::-1]
                    seen[g] = True
                    dq.append(g)
    return Q


def build_elytron(R, log=print):
    """the left elytron's plate cage (the ELY_CAGE comment): returns dict(mesh QuadMesh of targets, sharp, loops, info)"""
    ec = ELY_CAGE
    t0 = time.time()
    ch = ElyChart(R)
    ht, c_m = ch.ht, ch.c_m
    n1, n2, n6 = ec['n1'], ec['n2'], ec['n6']
    NI = n1 + n2
    al = n1 / NI
    z0, zl = float(ch.zs[0]), float(ch.zs[-1])
    A0, Al = float(ch.A[0]), float(ch.A[-1])
    th, kz = np.radians(ec['arm_deg']), ec['kz']
    # ---- the Y: M_TA on the sutural edge tip_suture (3D) from the sutural angle; P_O on the split line (a = al A(z)) where the
    # left arm leaving it at arm_deg (chart z scaled by kz, the dome's mean slope along z) reaches M_TA; M_BT where the right
    # arm reaches the margin
    sut = ch.G[:, 0]
    s_tip = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(sut[::-1], axis=0), axis=1))])[::-1]
    z_TA = float(np.interp(ec['tip_suture'], s_tip[::-1], ch.zs[::-1]))
    zta_of = lambda zo: zo - al * float(ch.A_of(zo)[0]) / np.tan(th) / kz        # noqa: E731
    lo_, hi_ = z_TA, z0 - 0.5
    for _ in range(60):
        m_ = 0.5 * (lo_ + hi_)
        lo_, hi_ = (m_, hi_) if zta_of(m_) < z_TA else (lo_, m_)
    z_O = 0.5 * (lo_ + hi_)
    a_O = al * float(ch.A_of(z_O)[0])
    ts = np.linspace(0.0, 25.0, 25001)
    zz = z_O - ts * np.cos(th) / kz
    gap = a_O + ts * np.sin(th) - ch.A_of(zz)
    k_ = int(np.nonzero(gap >= 0.0)[0][0])
    t_BT = float(np.interp(0.0, gap[k_ - 1:k_ + 1], ts[k_ - 1:k_ + 1]))
    z_BT = z_O - t_BT * np.cos(th) / kz
    a_BT = float(ch.A_of(z_BT)[0])
    # ---- the sides in the chart (dense, then evenly by 3D arc length)
    dense = 600
    base1 = np.column_stack([np.full(n1 + 1, z0), np.linspace(0.0, al * A0, n1 + 1)])     # (a IS the arc on row 0)
    base2 = np.column_stack([np.full(n2 + 1, z0), np.linspace(al * A0, A0, n2 + 1)])
    zd = np.linspace(z0, z_TA, dense)
    sut1 = ch.even(zd, np.zeros(dense), n6)
    zd = np.linspace(z0, z_O, dense)
    split = ch.even(zd, al * ch.A_of(zd), n6)
    zd = np.linspace(z0, z_BT, dense)
    marg1 = ch.even(zd, ch.A_of(zd), n6)
    armL = ch.even(np.linspace(z_O, z_TA, dense), np.linspace(a_O, 0.0, dense), n1)        # P_O -> M_TA
    armR = ch.even(np.linspace(z_O, z_BT, dense), np.linspace(a_O, a_BT, dense), n2)       # P_O -> M_BT
    zd = np.linspace(z_BT, zl, dense)
    m3 = ch.even(zd, ch.A_of(zd), n1 - 1)                                                  # M_BT -> the margin's end
    marg3 = np.vstack([m3, [[zl, 0.0]]])                                                   # ... then the last row -> P_T
    sut3 = ch.even(np.linspace(z_TA, zl, dense), np.zeros(dense), n2)                       # M_TA -> P_T
    # ---- the patches (chart)
    Q1 = coons(base1, armL[::-1], sut1, split)            # (n1 + 1, n6 + 1): i from the sutural edge, j from the base
    Q2 = coons(base2, armR, split, marg1)                 # (n2 + 1, n6 + 1)
    Q3 = coons(armR, sut3, armL, marg3)                   # (n2 + 1, n1 + 1): p from P_O toward M_BT, q from P_O toward M_TA
    main = np.concatenate([Q1, Q2[1:]], 0)                # (NI + 1, n6 + 1)
    # ---- the face vertices: the main grid, Q3's interior, the epipleuron's inner edge
    Nm = (NI + 1) * (n6 + 1)
    vm = np.arange(Nm).reshape(NI + 1, n6 + 1)
    vq = np.full((n2 + 1, n1 + 1), -1, np.int64)
    vq[1:, 1:] = Nm + np.arange(n2 * n1).reshape(n2, n1)
    vq[:, 0] = vm[n1 + np.arange(n2 + 1), n6]
    vq[0, :] = vm[n1 - np.arange(n1 + 1), n6]
    marg = [int(vm[NI, k]) for k in range(n6 + 1)] + [int(vq[n2, q]) for q in range(1, n1 + 1)]
    # the strip runs along the margin from the humeral angle while the clay's epipleuron is at least epi_min wide, its width
    # eased to taper_end over its last taper_segs intervals (ELY_CAGE's comment)
    zmg = np.concatenate([main[NI, :, 0], Q3[n2, 1:, 0]])
    Emg = np.interp(ch.row(zmg), ch.rr, ch.E)
    Ks = int(np.nonzero(Emg < ec['epi_min'])[0][0]) - 1 if (Emg < ec['epi_min']).any() else n6 + n1 - 1
    Ks = int(np.clip(Ks, n6, n6 + n1 - 1))
    ch.ease_epipleuron(float(zmg[Ks - ec['taper_segs']]), float(zmg[Ks]), ec['taper_end'])
    ve = Nm + n2 * n1 + np.arange(Ks + 1)
    Nf = Nm + n2 * n1 + Ks + 1
    ZA = np.zeros((Nf, 2))
    ZA[vm.ravel()] = main.reshape(-1, 2)
    ZA[vq[1:, 1:].ravel()] = Q3[1:, 1:].reshape(-1, 2)
    fold = np.zeros(Nf, bool)
    fold[marg[:Ks + 1]] = True
    epi = np.zeros(Nf, bool)
    epi[ve] = True
    mid_p, nrm, outer, inner = np.zeros((Nf, 3)), np.zeros((Nf, 3)), np.zeros((Nf, 3)), np.zeros((Nf, 3))
    dom = ~epi
    r_, c_ = ch.rc_dome(ZA[dom, 0], ZA[dom, 1])
    c_[fold[dom]] = float(c_m)                            # (the fold vertices exactly on the fold column)
    P, n, _, _ = ch.at(r_, c_)
    mid_p[dom], nrm[dom] = P, n
    # the epipleuron's inner edge at each strip vertex's row
    zk = ZA[marg[:Ks + 1], 0]
    re_, ce_ = ch.rc_epi(zk, np.ones(Ks + 1))
    Pe, ne, _, _ = ch.at(re_, ce_, epi=True)
    mid_p[ve], nrm[ve] = Pe, ne
    outer[:], inner[:] = mid_p + ht * nrm, mid_p - ht * nrm
    # the fold: the outer arc's middle and the inner corner (the point ht from both faces)
    fi = np.nonzero(fold)[0]
    rf_ = ch.row(mid_p[fi, 2])
    _, nd_, _, _ = ch.at(rf_, np.full(len(fi), float(c_m)))
    _, nE_, _, _ = ch.at(rf_, np.full(len(fi), float(c_m)), epi=True)
    bis = unit(nd_ + nE_)
    cs = np.clip((nd_ * nE_).sum(1), -0.95, 1.0)
    outer[fi] = mid_p[fi] + ht * bis
    inner[fi] = mid_p[fi] - ht * (nd_ + nE_) / (1.0 + cs)[:, None]
    nrm[fi] = bis
    # ---- the face quads (one winding; orient_quads fixes the rest)
    FQ = []
    for i in range(NI):
        for j in range(n6):
            FQ.append((vm[i, j], vm[i + 1, j], vm[i + 1, j + 1], vm[i, j + 1]))
    for p in range(n2):
        for q in range(n1):
            FQ.append((vq[p, q], vq[p + 1, q], vq[p + 1, q + 1], vq[p, q + 1]))
    for k in range(Ks):
        FQ.append((marg[k], ve[k], ve[k + 1], marg[k + 1]))
    FQ = np.array(FQ, np.int64)
    # ---- the boundary walk (face vertex ids): the base, the strip's base edge and inner edge, its end edge back to the
    # margin's end, the last row to the sutural angle, the sutural edge back to the scutellar corner
    walk = [int(v) for v in vm[:, 0]] + [int(v) for v in ve] + marg[Ks:] + \
        [int(vq[p, n1]) for p in range(n2 - 1, -1, -1)] + [int(vm[0, j]) for j in range(n6 - 1, 0, -1)]
    assert len(set(walk)) == len(walk), 'elytron: the boundary walk repeats a vertex'
    onb = np.zeros(Nf, bool)
    onb[walk] = True
    # each boundary vertex's outward in-surface direction: away from the mean of its quads' interior vertices
    acc, cnt = np.zeros((Nf, 3)), np.zeros(Nf)
    for qd in FQ:
        inn = [v for v in qd if not onb[v]]
        if not inn:
            inn = list(qd)
        cpt = mid_p[inn].mean(0)
        for v in qd:
            acc[v] += cpt
            cnt[v] += 1
    crest = []
    for v in walk:
        o = mid_p[v] - acc[v] / max(cnt[v], 1)
        o = unit(o - nrm[v] * (nrm[v] @ o))
        crest.append(mid_p[v] + ht * o)
    crest = np.array(crest)
    L = len(walk)
    V = np.vstack([outer, inner, crest])
    Q = [tuple(q) for q in FQ] + [tuple(q[::-1] + Nf) for q in FQ]
    for b in range(L):
        b1 = (b + 1) % L
        u, w = walk[b], walk[b1]
        Q.append((u, w, 2 * Nf + b1, 2 * Nf + b))
        Q.append((2 * Nf + b, 2 * Nf + b1, Nf + w, Nf + u))
    Q = orient_quads(Q)
    mesh = QuadMesh(V, Q)
    # the global sign: the outer face's quads against the clay's outward normal
    mq = quad_metrics(mesh)
    if np.mean((mq['normal'][:len(FQ)] * nrm[FQ].mean(1)).sum(1)) < 0:
        mesh = QuadMesh(V, Q[:, ::-1].copy())
    sp = ec['sharp']
    sharp = {}
    for ids, s_v in (([marg[k] for k in range(Ks + 1)], sp['margin_out']), ([Nf + marg[k] for k in range(Ks + 1)],
                                                                            sp['margin_in'])):
        if s_v > 0:
            for x, y in zip(ids[:-1], ids[1:]):
                sharp[(min(x, y), max(x, y))] = s_v
    if sp['rim'] > 0:
        for base_ in (0, Nf):
            for b in range(L):
                x, y = base_ + walk[b], base_ + walk[(b + 1) % L]
                sharp[(min(x, y), max(x, y))] = sp['rim']
    # the strip's END: a concave corner of the plate's outline, where the end face's half-round meets the margin's in a
    # crease (the clay's shell: two rims meeting square); creasing the rim's two radial edges at the corner (notch > 0) makes
    # the limit cross itself there (b4-2: 8 vertices at 3.0), so it is off: the limit fills the corner with a fillet
    if sp.get('notch', 0.0) > 0:
        bn = walk.index(marg[Ks])
        for x, y in ((marg[Ks], 2 * Nf + bn), (2 * Nf + bn, Nf + marg[Ks])):
            sharp[(min(x, y), max(x, y))] = sp['notch']
    # the fit's per-vertex weights (fit_limit, regularised): the strip's END is a concave notch of the plate's outline (the
    # epipleuron's end edge meeting the margin's rim), where interpolating every target overshoots (b4-2: controls 0.46-0.74 mm
    # off, 7-19 limit quads folded there); its rim and boundary vertices within ELY_CAGE notch_steps of the notch's two corners
    # are held loosely (notch_w), the regularisation carries the surface through
    fit_w = np.ones(len(V))
    iw = {b for b, v in enumerate(walk) if v in (int(ve[Ks]), marg[Ks])}
    near = {(b + d) % L for b in iw for d in range(-ec['notch_steps'], ec['notch_steps'] + 1)}
    for b in near:
        fit_w[2 * Nf + b] = ec['notch_w']
        fit_w[walk[b]] = ec['notch_w']
        fit_w[Nf + walk[b]] = ec['notch_w']
    suture = [int(vm[0, j]) for j in range(n6 + 1)] + [int(vq[p, n1]) for p in range(1, n2 + 1)]   # scutellar corner -> tip
    loops = dict(margin=marg[:Ks + 1], suture=suture, base=[int(v) for v in vm[:, 0]], epipleural_edge=[int(v) for v in ve],
                 crest=list(range(2 * Nf, 2 * Nf + L)), outer_rim=walk, inner_rim=[Nf + v for v in walk],
                 y_vertex=int(vm[n1, n6]))
    log(f'[b4] elytron: plate cage {len(V)} vertices, {len(Q)} quads (a face {len(FQ)}: the body {NI} x {n6}, the apex {n2} x '
        f'{n1}, the epipleuron {Ks}; the rim {L} x 2); the Y at z {z_O:.2f} (a {a_O:.2f} of {a_O / al:.2f}), the arms to the '
        f'sutural edge at z {z_TA:.2f} and the margin at z {z_BT:.2f}; {time.time() - t0:.1f}s')
    return dict(mesh=mesh, sharp=sharp, loops=loops, ht=ht, c_m=c_m, chart=ch, Nf=Nf, n_face=len(FQ), walk=walk,
                y=dict(z_O=z_O, a_O=a_O, z_TA=z_TA, z_BT=z_BT), epi_end_z=float(zmg[Ks]), fit_w=fit_w)


class ShellField:
    """the clay elytron's own field, exactly: the distance to its mid-surface patch (the shell primitive's triangles) less its
    half-thickness (sdf.Program.shell's construction), on Warp's BVH; life mm, plan frame"""

    def __init__(self, V, F, ht, name='elytron'):
        import warp as wp
        self.dev = wp.get_preferred_device()
        self.V, self.F, self.ht, self.name = np.asarray(V, np.float64), np.asarray(F, np.int32), float(ht), name
        self.mesh = wp.Mesh(points=wp.array(self.V.astype(np.float32), dtype=wp.vec3, device=self.dev),
                            indices=wp.array(self.F.ravel(), dtype=wp.int32, device=self.dev))

    def __call__(self, P):
        import warp as wp
        P = np.atleast_2d(np.asarray(P, np.float32))
        out = wp.zeros(len(P), dtype=wp.vec3, device=self.dev)
        wp.launch(_kernels()['closest'], dim=len(P), inputs=[self.mesh.id, wp.array(P, dtype=wp.vec3, device=self.dev),
                                                             1.0e3, out], device=self.dev)
        return np.linalg.norm(out.numpy().astype(np.float64) - P, axis=1) - self.ht

    grad = Field.grad
    project = Field.project
    ray = Field.ray


def elytron_reference(R, chart=None, z_cut=None):
    """the clay elytron's mid-surface patch (plan frame, life mm) as a mesh for the gates: the clay's own (chart None), or the
    chart's patch (its epipleuron eased toward the strip's end, ElyChart.ease_epipleuron) less the epipleuron's cells behind
    z_cut (the strip's end): the shell round it is the clay as the cage builds it (ELY_CAGE's comment). Returns (V, F)"""
    d = R['descs']['elytron'][0]
    F = np.asarray(d['F'], np.int64)
    if chart is None:
        V = np.asarray(d['V'], np.float64).copy()
        V[:, 1] -= R['clear']
        return V, F
    V = chart.G.reshape(-1, 3).copy()
    if z_cut is not None:
        nt = chart.nt
        behind = (chart.zs[F // nt] < z_cut - 1e-9).any(1)           # a corner in a row behind the strip's end
        epi_cell = ((F % nt) > chart.c_m).any(1)                      # a corner past the fold
        F = F[~(behind & epi_cell)]
    return V, F


def mirror_mesh(mesh):
    """the right part from the left: x -> -x, the winding reversed (det < 0: the study-G rule); exact by construction"""
    V = mesh.V * np.array([-1.0, 1.0, 1.0])
    return QuadMesh(V, mesh.Q[:, ::-1].copy())


# ============================================================================================ THE SCUTELLUM
# The scutellum (arthropod_parts.scutellum_descs: a loft of rounded sections, its half-width M1d's visible scutellum narrowing to
# the apex, 0.7 thick, corners rho 0.18) as a small midline tube: meridians about its mid-height, the T cap round the APEX's
# rounded end, rings at stations, the B cap its BASE face (toward the pronotum's hind face); its edges the clay's rounding.
SCUT_CAGE = dict(nA=3, nB=2, n_out=8, apex_in=0.30, res=0.006, rmax=1.9, space=0.4, theta_step=2.0)
# (nA 3 across the half top, nB 2 down the side: the plate is 2.7 x 0.7 mm, so b4-1's nA 2 / nB 4 made the base face's cap
# cells 0.67 x 0.17 mm, aspect 4.2, min angle 17 at its corners; the ring keeps M 9)


def build_scutellum(R, grids, log=print):
    sc = SCUT_CAGE
    t0 = time.time()
    g = grids['scut']
    ely = R['elytron']
    pr = ely['profiles']
    za, zb = pr['z_scut_apex'], pr['z_base']
    # the mid-height along z (the loft's own top and thickness: arthropod_parts.SCUT)
    from ..families import arthropod_parts as AP
    tz = lambda z: np.interp(z, [za, zb], [AP.SCUT['top'][1], AP.SCUT['top'][0]]) - AP.SCUT['ht']   # noqa: E731
    th = np.arange(90.0, -90.0 - 1e-9, -sc['theta_step'])
    T = meridian_traces(g, lambda z: tz(np.asarray(z, np.float64)), th, za - 0.4, zb + 0.4, sc['rmax'], sc['res'])
    n_out = sc['n_out']
    K = n_out
    d_am = np.array([1.0, 1.0]) / np.sqrt(2.0)
    U = even_ring_stations(n_out, sc['space'])
    ST = np.zeros((len(T), K + 1))
    for j, tr in enumerate(T):
        se = tr['s'][-1]
        s0 = s_at_z(tr, tr['P'][0, 2] + sc['apex_in'], 0.0, se)
        sa = support_s(tr, d_am, s_lo=s0)
        ST[j] = s0 + U * (sa - s0)
    C = ring_curves(T, ST)
    cage = TubeCage(sc['nA'], sc['nB'], K)
    M = cage.M
    for k in range(K + 1):
        Ck = C[k]
        s_ = arclen(Ck)
        jw = int(np.argmax(Ck[:, 0]))
        P, _ = place_on_curve(Ck, {M // 2: s_[jw]}, M)
        for i in range(M):
            cage.put(cage.R[k, i], P[i], 'the scutellum (meridian stations)' if 0 < k < K else
                     ('the apex end\'s ring' if k == 0 else 'the base face\'s edge (45 deg support point)'))
    nA, nB = cage.nA, cage.nB
    for capG, kr, dz, tag in ((cage.T, 0, 1.0, 'the apex end (T cap)'), (cage.B, K, -1.0, 'the base face (B cap)')):
        ring = cage.P[cage.R[kr]]
        top, right, bot = ring[0:nA + 1], ring[nA:nA + nB + 1], ring[nA + nB:M][::-1]
        left = np.column_stack([np.zeros(nB + 1), np.linspace(ring[0, 1], ring[M - 1, 1], nB + 1),
                                np.linspace(ring[0, 2], ring[M - 1, 2], nB + 1)])
        PP = coons(top, bot, left, right)
        for a in range(nA + 1):
            for b in range(nB + 1):
                v = capG[a, b]
                if not np.isnan(cage.P[v, 0]):
                    continue
                p = PP[a, b].copy()
                if a == 0:
                    p[0] = 0.0
                z0 = ring[:, 2].min() - 0.5 if dz > 0 else ring[:, 2].max() + 0.5
                q = g.ray(np.array([[p[0], p[1], z0]]), np.array([[0.0, 0.0, dz]]), reach=1.5, step=0.003, enter=True)[0]
                if not np.isfinite(q[0]):
                    raise RuntimeError(f'scutellum {tag}: no surface')
                cage.put(v, q, tag)
    assert not np.isnan(cage.P).any()
    log(f'[b4] scutellum: the half cage {cage.n_half} vertices (M {M}, K {K}), {time.time() - t0:.1f}s')
    return dict(cage=cage, T=T)


# ============================================================================================ THE VENTER
# The ventral thorax and abdomen (arthropod_parts.venter_descs: a loft whose section is widest where the epipleura clasp it,
# its bottom M1l's ventral line, its end cut to an arc; carved by the pronotum's back (a socket in its front), the scutellum (a
# seat in its dorsum) and the meso- and metacoxae (cavities in its underside), all shrunk by SINK). THE FRONT (b4-3): the
# pronotum's hind face is flat (z -18.446); the clay's carve leaves the venter's front face only 0.08 mm inside it, and below
# and beside it (where the pronotum's shrunk outline crosses the venter's own front end) a LIP 0.37 mm proud, a step the cage
# folded on (b4-2: 550 limit folds, 32 of 64 children a quad there, p20_ven_front_c0); the cage's front is ONE flat face, the
# plane z_front = the hind face + SINK, so the waist overlaps by SINK all over it (the plan's 0.24-0.28 condyle; the carve gave
# 0.08), the exposed strip below the pronotum's back edge and the hind angles' recess 0.2-0.4 mm further back than the clay's
# lip. The cage: a tube of meridian traces about its mid-height line hc(z) on the venter laid without its carves and cut at
# z_front, from the axis at the abdominal tip round the outer surface to the FRONT EDGE ring on the plane, the B cap the flat
# front; targets inside a seat (the scutellum's, carved by it shrunk by SINK) snapped onto the carved clay; the coxal pockets
# INSET ports; rings at MEASURED stations (z on the ventral midline, VEN_CAGE rings): the STERNITE SUTURES (M3v:
# four transverse lines behind the metacoxae, each a LIP ring (the anterior ventrite's hind margin, proud) and a FOOT ring (the
# next one's start, recessed), curving forward to the sides as M3v shows), the coxal cavities' rings; the ring points by arc
# length, the underside's columns at fixed shares of each ring's widest x (the coxal ports' columns, the PLEURAL suture: M3v's
# metepisternum's medial edge).
# M3v READINGS (p02_m3v_abd2.png, the photo's own pixels, +-5 px; the specimen's midline x 1930): the sutures' midline rows S1
# 3245, S2 3352, S3 3466, S4 3568, the abdominal tip 3699; the femur's exit from the metacoxa (cx3_L) 3134. z on the clay
# proportional between the metacoxa (B1's coxae.meta, -31.43) and the venter's tip (VENTER tip -42.26): 0.01917 mm / px; the
# sutures' forward run to the sides (rows at |x| px 280 / 130, B1 mm by EW 0.02152 mm / px): S2 -6 / -2 px (-7 right), S3 -9 / -3
# (-14 right), S4 -36 / -13 (-30 right at |x| 220 px); S1 straight. The metepisternum's medial edge at |x| ~370 px (7.96 mm).
VEN_CAGE = dict(nA=5, nB=10, theta_step=1.0, res=0.025, rmax=10.0, zlo=-42.8, zhi=-17.3,
                # the outer rings, from the tip: (kind, z on the ventral midline); kinds: 'tip' (the T cap's rim), 'r', 'foot' /
                # 'lip' (a suture's pair), 'meta' / 'meso' (the coxal pockets' blocks: their z from each pocket's measured
                # footprint, b4-3), then the FRONT EDGE on the plane z_front (the B cap, flat, its inside: b4-3)
                # (each suture's LIP and FOOT 0.30 apart about M3v's suture line: b4-1's 0.12 made quads of aspect 7-23 along
                # the sutures and the interpolating fit folded the limit between them, 32 of each cage quad's 64 children)
                tail=(('tip', -41.55), ('r', -40.75), ('foot', -39.96), ('lip', -39.66), ('r', -38.80), ('foot', -38.00),
                      ('lip', -37.70), ('r', -36.70), ('foot', -35.82), ('lip', -35.52), ('r', -34.60), ('foot', -33.77),
                      ('lip', -33.47)),
                mid=(('r', -29.00), ('r', -27.40), ('r', -25.80), ('r', -24.30), ('r', -22.85)),
                fore=(('r', -19.30),),
                # THE COXAL POCKETS (b4-3): each a block bracketing its MEASURED footprint (where the carved clay leaves the
                # uncarved under the underside) by pocket_pad, of nz ring intervals x the columns `cols`, those columns ANCHORED
                # on its rings at the footprint's lateral / medial x + pad (the other underside columns spread between them; every
                # ring's shares blended back to `cols` within pocket_blend mm of the block); the block an INSET port: its
                # boundary on the pocket's RIM (creased rim_s), a loop on the wall at each of `insets` (shares of the pocket's
                # depth on its axis), the block's own grid the floor on the pocket's top (b4-2's block sat 0.8-1.0 mm medial of
                # the meso pocket, a loop and one wall ring for a pocket 1.6 mm deep: the limit stood 0.15-0.25 mm inside the
                # pocket all round and the coxae sank 0.61 / 0.65 mm, p20_ven_front_c0)
                pockets=dict(meta=dict(z=(-34.0, -28.0), cols=(13, 19), nz=3), meso=dict(z=(-24.0, -19.0), cols=(13, 17), nz=4)),
                pocket_pad=0.10, pocket_blend=1.2, insets=(0.35, 0.75), rim_margin=0.01, rim_s=2.0,
                tip_arc=(1.0, 0.6, 0.25),     # the first rings' columns blended toward even arc length by these weights
                tip_relax=40,                 # the T cap's interior relaxed on the surface this many times (relax_cap)
                tip_inset=0.30,               # the tip's O-grid loop this far from ring 0 toward the tip, along each meridian (mm)
                # the sutures' forward run at the sides (|x| B1 mm, mm forward), [M] M3v above, keyed by each suture's line z
                sut_run={-39.81: ((0.0, 0.0), (2.8, 0.25), (4.85, 0.63), (7.0, 1.1)),
                         -37.85: ((0.0, 0.0), (2.8, 0.06), (5.9, 0.22), (7.5, 0.33)),
                         -35.67: ((0.0, 0.0), (2.7, 0.03), (5.9, 0.125), (8.0, 0.2)),
                         -33.62: ((0.0, 0.0), (8.5, 0.0))},
                sut_step=0.05,          # [E] the suture's step (the lip proud and the foot recessed by half each)
                sut_theta=(-5.0, -35.0),  # the sutures (their run and step) faded in from this theta (the side) to this (below)
                front_floor=0.30, deep_in=0.35,   # the rings past the front edge: onto the socket's floor, then the deep ring
                # the half ring's columns: i_wide the widest point; the underside's at shares of it (the pleural line, the
                # coxal ports'); the dorsum's by arc length
                i_wide=8, cols={11: 0.925, 12: 0.65, 13: 0.512, 14: 0.419, 15: 0.33, 16: 0.25, 17: 0.17, 18: 0.10, 19: 0.045},
                # the ELYTRA / HINDWING port each side (CROSSBREED §7.3 wing; the hindwing base on wing_0 and the elytron's
                # articulation beside it): a K-loop on the dorsum, a PLANAR circle of radius r (planar by construction, at the
                # dorsum's mean height under it; the chord sag at x10 within 2 texels: K 12 holds r 0.634) centred on the block
                # of the columns `cols` x the meso pocket's rings (a square block: b4-2's 7 x 3 block forced onto a circle pleated
                # the limit, 11-13 folded children a quad, and its loop on the curved dorsum was off its plane by 0.076 r_bar);
                # the hindwing base wing_0 stands at (4.2, 10.4, -21.5) [D-pl], the block's centre 0.4 ahead of it
                wing=dict(cols=(3, 5), K=12, r=0.6),
                pleura=dict(i=11, z=(-31.0, -20.0), depth=0.025, s=1.0),
                groove=dict(z=(-28.0, -25.0), depth=0.04, s=1.0),     # (M3v's groove z -27.5 .. -25.3: both its rings)
                sharp=dict(lip=2.2, front=2.0))


def _ven_hc(g):
    """the venter's mid-height along z on its midline (the top and bottom where rays at x 0 meet it), smoothed; held at the
    front (inside the pronotum's socket only the cup's bottom strip remains) and at the tip"""
    zs = np.arange(-42.1, -18.4, 0.1)
    A1 = np.column_stack([np.zeros(len(zs)), np.full(len(zs), 13.0), zs])
    A2 = np.column_stack([np.zeros(len(zs)), np.full(len(zs), -1.0), zs])
    top = g.ray(A1, np.tile([0.0, -1.0, 0.0], (len(zs), 1)), reach=15.0, step=0.01, enter=True)[:, 1]
    bot = g.ray(A2, np.tile([0.0, 1.0, 0.0], (len(zs), 1)), reach=15.0, step=0.01, enter=True)[:, 1]
    mid = 0.5 * (top + bot)
    ok = np.isfinite(mid)
    from scipy.ndimage import gaussian_filter1d
    m = gaussian_filter1d(np.interp(zs, zs[ok], mid[ok]), 8, mode='nearest')
    zf, zt = -18.6, -41.6
    return lambda z: np.interp(np.clip(z, zt, zf), zs, m)


def _run(table, x):
    t = np.array(table, np.float64)
    return np.interp(np.abs(x), t[:, 0], t[:, 1], right=t[-1, 1])


def ven_pockets(g, gl, log=print):
    """the coxal pockets' FOOTPRINTS on the venter's underside: rays from below onto the uncarved venter (gl), where the carved
    clay (g) leaves it; per pocket (VEN_CAGE pockets: its z window) the x and z extents and the centre (life mm)"""
    xs, zs = np.arange(0.05, 6.5, 0.02), np.arange(-34.5, -18.5, 0.02)
    X, Zg = np.meshgrid(xs, zs, indexing='ij')
    A0 = np.column_stack([X.ravel(), np.full(X.size, -1.0), Zg.ravel()])
    Pu = np.vstack([gl.ray(A0[a:a + 15000], np.tile([0.0, 1.0, 0.0], (len(A0[a:a + 15000]), 1)), reach=4.5, step=0.01,
                           enter=True) for a in range(0, len(A0), 15000)])
    ok = np.isfinite(Pu[:, 0])
    cav = np.zeros(len(A0), bool)
    cav[ok] = (g(Pu[ok]) - gl(Pu[ok])) > 0.005
    P = Pu[cav]
    out = {}
    for nm, pk in VEN_CAGE['pockets'].items():
        m = (P[:, 2] > pk['z'][0]) & (P[:, 2] < pk['z'][1])
        if not m.any():
            raise RuntimeError(f'venter: the {nm}coxal pocket was not found under the underside')
        Q = P[m]
        out[nm] = dict(x=(float(Q[:, 0].min()), float(Q[:, 0].max())), z=(float(Q[:, 2].min()), float(Q[:, 2].max())),
                       centre=Q.mean(0))
        log(f'[b4] venter: the {nm}coxal pocket x {out[nm]["x"][0]:.2f}..{out[nm]["x"][1]:.2f}, z {out[nm]["z"][0]:.2f}..'
            f'{out[nm]["z"][1]:.2f}')
    return out


def port_pocket(cage, g, gl, ii, kk, label, key, joint, insets, margin, rim_s, centre, side='L'):
    """b4-3: a coxal POCKET as an INSET port in a TubeCage's ring grid (the block of rings kk x columns ii, bracketing the pocket's
    footprint): the block's boundary on the pocket's RIM (each vertex at its own angle about the pocket's centre, moved straight
    onto the rim, `margin` outside it on the outer surface; creased rim_s), TubeCage.inset's loops on the pocket's WALL at each of
    `insets` (shares of its depth on its axis), each vertex at the angle of the rim vertex it faces, the block's own grid the FLOOR
    on the pocket's top (a Coons patch of the innermost loop, each point onto the carved clay along the axis). Every target on the
    carved clay g (the pocket is the coxa shrunk by SINK: the joint's overlap). Returns the port's record"""
    (i0, i1), (k_a, k_b) = ii, kk
    walk_ki = block_walk((i0, i1), (k_a, k_b))
    fp = np.array([cage.P[cage.R[k, i]] for k, i in walk_ki])
    c0 = gl.project(np.asarray(centre, np.float64)[None])[0]
    Zc, Xc, Yc = port_frame(gl.grad(c0[None])[0], [0.0, 0.0, 1.0])
    walk_ki = orient_walk(walk_ki, fp, c0, Xc, Yc)
    fp = np.array([cage.P[cage.R[k, i]] for k, i in walk_ki])
    phi = np.unwrap(np.arctan2((fp - c0) @ Yc, (fp - c0) @ Xc))
    rim, _ = cavity_rim(g, gl, c0, Zc, Xc, len(walk_ki), margin=margin, phi=phi)
    walk = [int(cage.R[k, i]) for k, i in walk_ki]
    for n_, v in enumerate(walk):
        cage.put(v, rim[n_], f'{label}: the RIM at {np.degrees(phi[n_]):.0f} deg (creased)')
    cr = rim.mean(0)
    flo = g.ray((cr + 0.3 * Zc)[None], (-Zc)[None], reach=4.0, step=0.004, enter=True)[0]
    if not np.isfinite(flo[0]):
        raise RuntimeError(f'{label}: no pocket top on its axis')
    depth = float((cr - flo) @ Zc)
    block_ids = [int(cage.R[k, i]) for k in range(k_a, k_b + 1) for i in range(i0, i1 + 1)]
    loops = cage.inset(walk, block_ids, len(insets), tag=label)
    for t, lp in zip(insets, loops):
        A_ = cr - t * depth * Zc
        for n_, v in enumerate(lp):
            d_ = np.cos(phi[n_]) * Xc + np.sin(phi[n_]) * Yc
            q = g.ray(A_[None], d_[None], reach=4.0, step=0.003, enter=True)[0]
            if not np.isfinite(q[0]):
                raise RuntimeError(f'{label}: no wall at {np.degrees(phi[n_]):.0f} deg, {t} of its depth {depth:.3f}')
            cage.put(v, q, f'{label}: the wall at {t} of its depth')
    inner = loops[-1]
    pos_of = {wk: cage.P[inner[n_]] for n_, wk in enumerate(walk_ki)}
    PP = coons(np.array([pos_of[(k_a, i)] for i in range(i0, i1 + 1)]), np.array([pos_of[(k_b, i)] for i in range(i0, i1 + 1)]),
               np.array([pos_of[(k, i0)] for k in range(k_a, k_b + 1)]), np.array([pos_of[(k, i1)] for k in range(k_a, k_b + 1)]))
    floor = []
    for k in range(k_a + 1, k_b):
        for i in range(i0 + 1, i1):
            p = PP[i - i0, k - k_a]
            q = g.ray((p + 0.2 * Zc)[None], (-Zc)[None], reach=4.0, step=0.003, enter=True)[0]
            if not np.isfinite(q[0]):
                raise RuntimeError(f'{label}: no pocket top over a floor point')
            v = int(cage.R[k, i])
            cage.put(v, q, f'{label}: the floor (the pocket\'s top)')
            cage.plug[v] = True
            floor.append(v)
    cage.crease(walk, rim_s, closed=True)
    rec = dict(walk=walk, insets=loops, floor=floor, centre=c0, Z=Zc, X=Xc, K=len(walk), depth=depth, joint=joint,
               kind='socket', block=((k_a, k_b), (i0, i1)), side=side)
    cage.ports[key] = rec
    return rec


def port_wing(cage, gl, ii, kk, label, key, joint, K, r, side='L'):
    """b4-3: the ELYTRA / HINDWING port: the block of rings kk x columns ii on the dorsum, its boundary left where the ring grid
    puts it (the COLLAR) and one INSET loop inside it (TubeCage.inset) a PLANAR circle of radius r (K vertices at equal angles
    from the port frame's X, counter-clockwise about Z, the dorsum's outward normal at the block's centre: right-handed on the
    left), the plane at the dorsum's mean height under the circle (planar by construction: b4-2's circle projected onto the
    curved dorsum was off its plane by 0.076 r_bar); the plug the block's interior on the dorsum. (b4-3's first build moved the
    block's own boundary onto the circle: the outside quads twisted, the exact fit swung controls 1.4-1.8 mm, 40 of 64
    children folded a quad.) Returns the port's record"""
    from ..families import arthropod_cage as AC
    (i0, i1), (k_a, k_b) = ii, kk
    walk_ki = block_walk((i0, i1), (k_a, k_b))
    if len(walk_ki) != K:
        raise RuntimeError(f'{label}: the block {kk} x {ii} has {len(walk_ki)} boundary vertices, not K {K}')
    c0 = cage.P[cage.R[(k_a + k_b) // 2, (i0 + i1) // 2]].copy()
    Zc, Xc, Yc = AC.port_frame(gl.grad(c0[None])[0], side)
    fp = np.array([cage.P[cage.R[k, i]] for k, i in walk_ki])
    walk_ki = orient_walk(walk_ki, fp, c0, Xc, Yc)
    phi = 2.0 * np.pi * np.arange(K) / K
    D = np.cos(phi)[:, None] * Xc[None, :] + np.sin(phi)[:, None] * Yc[None, :]
    S_ = gl.ray(c0[None, :] + r * D + 0.5 * Zc[None, :], np.tile(-Zc, (K, 1)), reach=1.5, step=0.002, enter=True)
    if np.isnan(S_).any():
        raise RuntimeError(f'{label}: the dorsum is not under the port\'s circle')
    off = float(np.mean((S_ - c0) @ Zc))
    cp = c0 + off * Zc
    loop = cp[None, :] + r * D
    collar = [int(cage.R[k, i]) for k, i in walk_ki]
    block_ids = [int(cage.R[k, i]) for k in range(k_a, k_b + 1) for i in range(i0, i1 + 1)]
    walk = cage.inset(collar, block_ids, 1, tag=label)[0]
    for n_, v in enumerate(walk):
        cage.put(v, loop[n_], f'{label}: the planar loop at {np.degrees(phi[n_]):.0f} deg')
    plug = [int(cage.R[k, i]) for k in range(k_a + 1, k_b) for i in range(i0 + 1, i1)]
    for v in plug:
        cage.plug[v] = True
    rec = dict(walk=walk, collar=collar, plug=plug, centre=cp, Z=Zc, X=Xc, K=K, radius=r, plane_offset=off,
               off_dorsum=float(np.abs((S_ - loop) @ Zc).max()), joint=joint, kind='wing', block=((k_a, k_b), (i0, i1)),
               side=side)
    cage.ports[key] = rec
    return rec


def relax_cap(cage, capG, field, iters):
    """b4-3: a TubeCage cap's interior relaxed ON THE SURFACE: each vertex off the cap's boundary ring (b 1 .. nB - 1, a 0 .. nA - 1;
    the midline column a 0 kept at x 0, its mirror neighbour taken by symmetry) moved to the mean of its four grid neighbours and
    projected back onto the field, `iters` times; the ring fixed. (A Coons patch of a skewed ring projected along one axis bunches
    the rows next to the ring where the surface runs along that axis: the venter's tip pleated, c2-c4)"""
    nA, nB = capG.shape[0] - 1, capG.shape[1] - 1
    inner = [(a, b) for a in range(nA) for b in range(1, nB)]
    for _ in range(iters):
        P = cage.P
        pts = []
        for a, b in inner:
            if a > 0:
                m_ = P[capG[a - 1, b]]
            else:
                m_ = P[capG[1, b]] * np.array([-1.0, 1.0, 1.0])
            pts.append((P[capG[a + 1, b]] + m_ + P[capG[a, b - 1]] + P[capG[a, b + 1]]) / 4.0)
        pts = field.project(np.array(pts), it=6)
        for (a, b), q in zip(inner, pts):
            if a == 0:
                q[0] = 0.0
            cage.P[capG[a, b]] = q


def build_venter(R, grids, log=print):
    """the venter's half cage (b4-3, the VEN_CAGE comment and the section's): returns dict(cage, T, stations, hc, n_out, K,
    pockets)"""
    vc = VEN_CAGE
    t0 = time.time()
    g, gl = grids['ven_ref'], grids['ven_lay']
    z_f = R['z_front']
    pk = ven_pockets(g, gl, log=log)
    pad = vc['pocket_pad']
    blocks = {}
    for nm in ('meta', 'meso'):
        za, zb = pk[nm]['z'][0] - pad, pk[nm]['z'][1] + pad
        blocks[nm] = dict(z=np.linspace(za, zb, vc['pockets'][nm]['nz'] + 1), x=(pk[nm]['x'][1] + pad, pk[nm]['x'][0] - pad),
                          cols=vc['pockets'][nm]['cols'])
    rings = list(vc['tail']) + [('meta', float(z)) for z in blocks['meta']['z']] + list(vc['mid']) + \
        [('meso', float(z)) for z in blocks['meso']['z']] + list(vc['fore'])
    hc = _ven_hc(gl)
    th = np.arange(90.0, -90.0 - 1e-9, -vc['theta_step'])
    T = meridian_traces(gl, hc, th, vc['zlo'], vc['zhi'], vc['rmax'], vc['res'])
    nt = len(T)
    n_out = len(rings) - 1
    K = n_out + 1
    zr = np.array([z for _, z in rings])
    if np.any(np.diff(zr) <= 0.2) or zr[-1] > z_f - 0.5:
        raise RuntimeError(f'venter: the rings out of order or crowded: {np.round(zr, 2).tolist()} (front {z_f:.2f})')
    # each outer ring's forward run at the sides: a suture's own, between sutures interpolated by z, none ahead of S1
    sut_z = sorted(vc['sut_run'])
    def run_of(k, x):
        z = zr[k]
        if rings[k][0] in ('lip', 'foot'):
            # a suture's own lip and foot take its run exactly
            return _run(vc['sut_run'][min(sut_z, key=lambda s_: abs(s_ - z))], x)
        if z > max(sut_z):
            return 0.0 * x
        if z <= min(sut_z):
            return _run(vc['sut_run'][min(sut_z)], x)
        for za_, zb_ in zip(sut_z[:-1], sut_z[1:]):
            if za_ <= z <= zb_ + 0.15:
                f = np.clip((z - za_) / (zb_ - za_), 0.0, 1.0)
                return (1 - f) * _run(vc['sut_run'][za_], x) + f * _run(vc['sut_run'][zb_], x)
        return _run(vc['sut_run'][max(sut_z)], x) * 0.0
    ST = np.zeros((nt, K + 1))
    for j, tr in enumerate(T):
        se = tr['s'][-1]
        w = float(smooth01((-tr['theta'] + vc['sut_theta'][0]) / (vc['sut_theta'][0] - vc['sut_theta'][1])))
        # the outer segment ends at the FRONT EDGE: where the trace reaches the plane z_front (b4-3: the layout's cut)
        at_f = np.nonzero(tr['P'][:, 2] >= z_f - 0.01)[0]
        if not len(at_f):
            raise RuntimeError(f'venter: the trace at theta {tr["theta"]} never reaches the front plane z {z_f:.3f}')
        sfe = float(tr['s'][at_f[0]])
        for k in range(n_out + 1):
            s0 = s_at_z(tr, zr[k], 0.0, sfe)
            if s0 is None:
                raise RuntimeError(f'venter: ring {k} (z {zr[k]}) not crossed at theta {tr["theta"]}')
            x0 = abs(trace_at(tr, s0)[0])
            dz = w * float(run_of(k, x0))
            s1 = s_at_z(tr, zr[k] + dz, 0.0, sfe) if dz else s0
            ST[j, k] = s1 if s1 is not None else s0
        ST[j, n_out + 1] = sfe
        if np.any(np.diff(ST[j]) <= 0):
            raise RuntimeError(f'venter: rings cross at theta {tr["theta"]}: {np.round(ST[j], 3).tolist()}')
    C = ring_curves(T, ST)
    log(f'[b4] venter: {nt} meridian traces about its mid-height line, stations placed, {time.time() - t0:.1f}s')
    cage = TubeCage(vc['nA'], vc['nB'], K)
    M = cage.M
    iw = vc['i_wide']
    cols = vc['cols']
    pos = np.zeros((K + 1, M, 3))

    def col_x(k, xm):
        """the underside columns' x on ring k (b4-3): `cols`' shares of the ring's widest x, blended within pocket_blend mm of a
        pocket's block to that block's layout (its columns at the footprint's lateral / medial x + pad, evenly between; the
        columns from the pleural line to the block and from the block to the midline evenly in x)"""
        xd = {i: fr * xm for i, fr in cols.items()}
        z = zr[k]
        for nm, bl in blocks.items():
            zb0, zb1 = bl['z'][0], bl['z'][-1]
            dist = max(zb0 - z, z - zb1, 0.0)
            w = float(np.clip(1.0 - dist / vc['pocket_blend'], 0.0, 1.0))
            if w <= 0:
                continue
            c_lat, c_med = bl['cols']
            x_lat, x_med = bl['x']
            xb = {11: xd[11]}
            for i in range(12, c_lat):
                xb[i] = xd[11] + (x_lat - xd[11]) * (i - 11) / (c_lat - 11)
            for i in range(c_lat, c_med + 1):
                xb[i] = x_lat + (x_med - x_lat) * (i - c_lat) / (c_med - c_lat)
            for i in range(c_med + 1, 20):
                xb[i] = x_med * (20 - i) / (20 - c_med)
            xd = {i: (1.0 - w) * xd[i] + w * xb[i] for i in xd}
        return xd
    for k in range(K + 1):
        Ck = C[k]
        if k <= n_out:
            # in ANGLE space (fractional meridian index): equal angles, the widest point and the underside's columns anchored
            jw = np.nonzero((th <= 40.0) & (th >= -60.0))[0]
            jx = jw[np.argmax(Ck[jw, 0])]
            xm = Ck[jx, 0]
            an = {0: 0.0, M - 1: float(nt - 1), iw: float(jx)}
            for ii, xv in sorted(col_x(k, xm).items()):
                cr = np.nonzero(((Ck[:-1, 0] - xv) * (Ck[1:, 0] - xv) <= 0) & (np.arange(len(Ck) - 1) >= jx))[0]
                if not len(cr):
                    raise RuntimeError(f'venter ring {k}: no crossing of x {xv:.3f}')
                jj = cr[0]
                an[ii] = jj + (xv - Ck[jj, 0]) / (Ck[jj + 1, 0] - Ck[jj, 0])
            ks_ = sorted(an)
            fj = np.interp(np.arange(M), ks_, [an[q] for q in ks_])
            if k < len(vc['tip_arc']):
                # (b4-3: the tip's rings turned toward EVEN ARC LENGTH, the T cap's boundary: the underside's shares squeezed its
                # bottom run into 0.83 mm (the cap's corner quads 20-26 deg, 17 of 64 children folded a quad, c2); equal angles
                # about the axis of a section 6 x 2.2 mm bunched them at the midlines (worse, c3))
                w_ = vc['tip_arc'][k]
                s_ = arclen(Ck)
                fj = (1.0 - w_) * fj + w_ * np.interp(np.linspace(0.0, s_[-1], M), s_, np.arange(nt, dtype=np.float64))
            if np.any(np.diff(fj) <= 0):
                raise RuntimeError(f'venter ring {k}: anchors out of order')
            if k == n_out:
                fj_fe = fj.copy()
            if k == 0:
                fj_0 = fj.copy()
        else:
            fj = fj_fe                      # (the front edge: the last ring's columns, on the plane's corner)
        pos[k] = curve_at(Ck, fj)
    for k in range(K + 1):
        kind = rings[k][0] if k <= n_out else 'the front edge, on the plane z_front'
        for i in range(M):
            cage.put(cage.R[k, i], pos[k, i], f'venter ring {k} ({kind})')
    # ---- the caps: the abdominal TIP an O-grid (b4-3: one loop inset from ring 0 toward the tip, tip_inset mm along each
    # meridian, the T cap's grid inside it, onto the clay along -z, then relaxed on the surface: a grid cap's corners on the
    # tip's smooth ring are 180 deg corners, its corner quads pleated, c5), and the FRONT (b4-3: flat, on the plane z_front)
    nA, nB = cage.nA, cage.nB
    walk0 = [int(v) for v in cage.R[0]]
    Lt = cage.inset_open(walk0, cage.T.ravel().tolist(), 1, tag='the tip cap')[0]
    Cl = ring_curves(T, np.maximum(ST[:, :1] - vc['tip_inset'], 0.02))[0]
    PL = curve_at(Cl, fj_0)
    PL[0, 0] = PL[-1, 0] = 0.0
    for m_, v in enumerate(Lt):
        cage.put(v, PL[m_], 'the tip cap\'s inset loop (the O-grid)')
    TL = cage.T.copy()
    rmap = dict(zip(walk0, Lt))
    for a in range(nA + 1):
        for b in range(nB + 1):
            TL[a, b] = rmap.get(int(TL[a, b]), int(TL[a, b]))
    for capG, kr, tag in ((TL, None, 'the abdominal tip (T cap, inside its O-grid loop)'),
                          (cage.B, K, 'the front, the plane z_front (B cap)')):
        ring = PL if kr is None else pos[kr]
        kr = 0 if kr is None else kr
        top, right, bot = ring[0:nA + 1], ring[nA:nA + nB + 1], ring[nA + nB:M][::-1]
        left = np.column_stack([np.zeros(nB + 1), np.linspace(ring[0, 1], ring[M - 1, 1], nB + 1),
                                np.linspace(ring[0, 2], ring[M - 1, 2], nB + 1)])
        PP = coons(top, bot, left, right)
        for a in range(nA + 1):
            for b in range(nB + 1):
                v = capG[a, b]
                if not np.isnan(cage.P[v, 0]):
                    continue
                p = PP[a, b].copy()
                if a == 0:
                    p[0] = 0.0
                if kr == 0:
                    A_ = np.array([[p[0], p[1], ring[:, 2].max() + 0.6]])
                    q = gl.ray(A_, np.array([[0.0, 0.0, -1.0]]), reach=3.0, step=0.004)[0]
                    if not np.isfinite(q[0]):
                        raise RuntimeError(f'venter {tag}: no surface at ({p[0]:.2f}, {p[1]:.2f})')
                else:
                    q = np.array([p[0], p[1], z_f])
                cage.put(v, q, tag)
    relax_cap(cage, TL, gl, vc['tip_relax'])
    # ---- the sutures' step, the pleural line, the metaventral groove: targets moved along the clay's normal
    def nudge(v, d):
        p = cage.P[v]
        nn = unit(g.grad(p[None])[0])
        cage.P[v] = p + d * nn
    for k in range(n_out + 1):
        kind = rings[k][0]
        if kind not in ('lip', 'foot'):
            continue
        for i in range(M):
            p = cage.P[cage.R[k, i]]
            thp = np.degrees(np.arctan2(p[1] - hc(p[2]), abs(p[0])))
            w = float(smooth01((-thp + vc['sut_theta'][0]) / (vc['sut_theta'][0] - vc['sut_theta'][1])))
            nudge(cage.R[k, i], (0.5 if kind == 'lip' else -0.5) * vc['sut_step'] * w)
    pl = vc['pleura']
    for k in range(n_out + 1):
        z = zr[k]
        w = float(smooth01((z - pl['z'][0]) / 1.0) * smooth01((pl['z'][1] - z) / 1.0))
        if w > 0:
            nudge(cage.R[k, pl['i']], -pl['depth'] * w)
    gr = vc['groove']
    for k in range(n_out + 1):
        z = zr[k]
        w = float(smooth01((z - gr['z'][0]) / 0.6) * smooth01((gr['z'][1] - z) / 0.6))
        if w > 0:
            nudge(cage.R[k, M - 1], -gr['depth'] * w)
            cage.P[cage.R[k, M - 1], 0] = 0.0
    # ---- the blocks: the coxal pockets' (their rings x their anchored columns) and the wing port's (its columns x the meso
    # pocket's rings)
    def ring_span(kind):
        ks = [k for k in range(n_out + 1) if rings[k][0] == kind]
        return min(ks), max(ks)
    pocket_blk = {nm: (blocks[nm]['cols'], ring_span(nm)) for nm in ('meta', 'meso')}
    wg = vc['wing']
    wing_blk = (wg['cols'], ring_span('meso'))
    in_ports = set()
    for (i0, i1), (k_a, k_b) in list(pocket_blk.values()) + [wing_blk]:
        in_ports |= {int(cage.R[k, i]) for k in range(k_a, k_b + 1) for i in range(i0, i1 + 1)}
    # ---- the SEAT (the scutellum's, carved by it shrunk by SINK): every target off the ports whose layout point lies inside
    # a carve snapped onto the carved clay along the layout's normal (b4-2 held one column of it: the limit stood 0.11 mm high
    # under the scutellum, which sank 0.40)
    n_snap = 0
    for v in range(cage.n_half):
        if v in in_ports:
            continue
        p = cage.P[v]
        if abs(p[2] - z_f) < 1e-6 or float(g(p[None])[0] - gl(p[None])[0]) <= 0.003:
            continue                        # (not in a carve: the sutures' nudged steps stay)
        nn = unit(gl.grad((p - np.array([0.0, 0.0, 0.05]))[None])[0])
        q = g.ray((p + 0.5 * nn)[None], (-nn)[None], reach=1.5, step=0.002, enter=True)[0]
        if not np.isfinite(q[0]):
            raise RuntimeError(f'venter: a target in a seat with no carved surface under it at {np.round(p, 3).tolist()}')
        if p[0] == 0.0:
            q[0] = 0.0
        cage.put(v, q, 'the scutellum\'s seat (the carved clay)')
        n_snap += 1
    # ---- the COXAL POCKETS (inset ports, VEN_CAGE pockets) and the ELYTRA / HINDWING port (planar)
    for nm, key in (('meta', 'metacoxa_L'), ('meso', 'mesocoxa_L')):
        (i0, i1), (k_a, k_b) = pocket_blk[nm]
        port_pocket(cage, g, gl, (i0, i1), (k_a, k_b), f'the {nm}coxal pocket', key, 'body', vc['insets'], vc['rim_margin'],
                    vc['rim_s'], pk[nm]['centre'])
    (i0, i1), (k_a, k_b) = wing_blk
    port_wing(cage, gl, (i0, i1), (k_a, k_b), 'the elytra / hindwing port', 'wing_L', 'body', wg['K'], wg['r'])
    # ---- creases: each suture's lip ring on the underside (fading at the sides), the front edge
    sp = vc['sharp']
    for k in range(n_out + 1):
        if rings[k][0] != 'lip':
            continue
        ss = []
        for i in range(M - 1):
            p = 0.5 * (cage.P[cage.R[k, i]] + cage.P[cage.R[k, i + 1]])
            thp = np.degrees(np.arctan2(p[1] - hc(p[2]), abs(p[0])))
            ss.append(sp['lip'] * float(smooth01((-thp + vc['sut_theta'][0]) / (vc['sut_theta'][0] - vc['sut_theta'][1]))))
        cage.crease(cage.R[k], ss)
    cage.crease(cage.R[n_out + 1], sp['front'])
    plc = [cage.R[k, pl['i']] for k in range(n_out + 1) if pl['z'][0] + 0.5 <= zr[k] <= pl['z'][1] - 0.5]
    cage.crease(plc, pl['s'])
    grc = [cage.R[k, M - 1] for k in range(n_out + 1) if gr['z'][0] <= zr[k] <= gr['z'][1]]
    cage.crease(grc, vc['groove']['s'])
    po_me, po_mt, po_w = cage.ports['mesocoxa_L'], cage.ports['metacoxa_L'], cage.ports['wing_L']
    cage.loops.update({'front edge': cage.R[n_out + 1].tolist(), 'mesocoxal rim L': po_me['walk'],
                       'mesocoxal walls L': po_me['insets'], 'metacoxal rim L': po_mt['walk'],
                       'metacoxal walls L': po_mt['insets'], 'wing port L': po_w['walk'],
                       'pleural line L': [int(v) for v in plc], 'metaventral groove': [int(v) for v in grc]})
    for k in range(n_out + 1):
        if rings[k][0] in ('lip', 'foot'):
            cage.loops[f'suture {rings[k][0]} z {rings[k][1]}'] = cage.R[k].tolist()
    assert not np.isnan(cage.P).any(), 'venter: a cage vertex without a target'
    log(f'[b4] venter: the half cage {cage.n_half} vertices (M {M}, K {K}); the front plane z {z_f:.3f}; {n_snap} targets '
        f'snapped into the scutellum\'s seat; the mesocoxal pocket {po_me["block"]} K {po_me["K"]} depth {po_me["depth"]:.2f}, '
        f'the metacoxal {po_mt["block"]} K {po_mt["K"]} depth {po_mt["depth"]:.2f}, the wing port {po_w["block"]} K '
        f'{po_w["K"]} r {po_w["radius"]} (its plane {po_w["plane_offset"]:+.3f} off the block\'s centre, the dorsum within '
        f'{po_w["off_dorsum"]:.3f} of it); {time.time() - t0:.1f}s')
    return dict(cage=cage, T=T, stations=ST, hc=hc, n_out=n_out, K=K, pockets=pk, rings=rings)


# ============================================================================================ THE ROUND TUBES
# The antenna's SCAPE (a round cone, club-shaped), its FUNICLE (one shell of five beads blended), each LAMELLA (a stalk on the
# club's axis and a rounded leaf standing forward: P1's comb) and the two PALPS (segmented round cones on a bowed curve):
# heads/insect.antenna_descs / palp_descs, seated by reference() as build_parts seats them. Each a tube of rings of K vertices
# at equal angles about its axis (rotation-minimising frames), the ends capped; targets the first exit of rays from the axis on
# the part's own exact field (small parts: the program itself, no grid). THE RINGS (b4-2): the end rings at pole_in of the end
# sphere's radius from each pole, the rest spaced by the local radius (equal steps of ds / r: every ring interval the same
# multiple of its ring's edge, so the low's aspect is even along a tapering part: b4-1's even spacing put the scape's thin end
# at aspect 7.3), the funicle's evenly along it (b4-1 packed rings 0.04 mm apart at the beads' ends: aspect 6.2). The counts are
# the plan's (BEETLE_PLAN §4.6: scape K 12 x 12, funicle K 8 x 30, lamella 48 quads, palps K 8 within 1,056 for the four).
TUBES = dict(scape=dict(K=12, n=12, pole_in=0.5), funicle=dict(K=8, n=30, pole_in=0.6), lamella=dict(K=8, n=6, equal_arc=True),
             palp_max=dict(K=8, n=17, pole_in=0.6), palp_lab=dict(K=8, n=12, pole_in=0.6))
# (the scape at the plan's K 12 x 12 cannot meet the aspect gate: its 11 intervals over the 8.4 mm rod, radius 0.27-0.42, are
# ~0.78 mm against ring edges of 0.14-0.22, aspect ~5.5 even by its radius; 16 rings would hold 4 but give 792 triangles
# for the pair against the plan's 600, K 8 would hold both but facet a long silhouette; a rigid segment, 100 % on one joint,
# does not stretch them, so the plan's topology stands and the gate's exception is reported)


def stations_by_radius(field, axis, s0, s1, n, probe=8):
    """n stations on [s0, s1] along the dense polyline `axis`, equally spaced in the measure ds / r(s), r the part's mean radius
    about the axis (probe rays from the axis on its field)"""
    s = arclen(axis)
    ss = np.linspace(s0, s1, 120)
    T_, E1, E2 = rmf(axis)
    phi = 2.0 * np.pi * np.arange(probe) / probe
    rad = np.zeros(len(ss))
    for k, st in enumerate(ss):
        C = np.array([np.interp(st, s, axis[:, d]) for d in range(3)])
        j = min(int(np.searchsorted(s, st)), len(s) - 1)
        D = np.cos(phi)[:, None] * E1[j][None, :] + np.sin(phi)[:, None] * E2[j][None, :]
        P = field.ray(np.tile(C, (probe, 1)), D, reach=3.0, step=0.004)
        ok = np.isfinite(P[:, 0])
        rad[k] = np.linalg.norm(P[ok] - C, axis=1).mean() if ok.any() else np.nan
    rad = np.where(np.isfinite(rad), rad, np.nanmean(rad))
    m = np.concatenate([[0.0], np.cumsum(np.diff(ss) / (0.5 * (rad[1:] + rad[:-1])))])
    return np.interp(np.linspace(0.0, m[-1], n), m, ss)


def rmf(P):
    """rotation-minimising frames along a polyline P (n, 3): tangents T and two normals (e1, e2), e1 x e2 = T (double
    reflection, Wang et al. 2008), e1 at the start the projection of world up off T (or +z where T is near vertical)"""
    P = np.asarray(P, np.float64)
    T = np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    up = np.array([0.0, 1.0, 0.0]) if abs(T[0, 1]) < 0.9 else np.array([0.0, 0.0, 1.0])
    e1 = unit(up - T[0] * (T[0] @ up))
    E1 = [e1]
    for i in range(len(P) - 1):
        v1 = P[i + 1] - P[i]
        c1 = v1 @ v1
        rL = E1[-1] - (2.0 / c1) * (v1 @ E1[-1]) * v1
        tL = T[i] - (2.0 / c1) * (v1 @ T[i]) * v1
        v2 = T[i + 1] - tL
        c2 = v2 @ v2
        r = rL - (2.0 / c2) * (v2 @ rL) * v2 if c2 > 1e-20 else rL
        E1.append(unit(r - T[i + 1] * (T[i + 1] @ r)))
    E1 = np.array(E1)
    E2 = np.cross(T, E1)
    return T, E1, E2


def build_tube(name, field, axis, stations, K, log=print, reach=3.0, equal_arc=False, e1_hint=None):
    """a RoundTube on the field (life mm) along the polyline `axis` (dense), rings at arc-length `stations` along it (the first
    and last on the end domes), K vertices a ring at equal angles about the axis (equal_arc: at equal ARC LENGTH round the
    ring's section from angle 0, for a flat part: b4-1's equal angles round a lamella's 0.2 x 0.9 mm leaf put edges of 0.1 and
    0.4 mm side by side, the low's aspect 6.7); the caps' interiors by a Coons patch of their ring, then onto the clay along the
    axis (rays out of the solid). e1_hint: the frames' first axis at the start (else world up off the axis). Returns
    (RoundTube with targets, frames)"""
    t0 = time.time()
    s = arclen(axis)
    T_, E1, E2 = rmf(axis)
    if e1_hint is not None:
        # (the rotation-minimising frames turned about the axis so their first axis starts along the hint)
        h_ = unit(np.asarray(e1_hint, np.float64) - T_[0] * (T_[0] @ np.asarray(e1_hint, np.float64)))
        ang = np.arctan2(h_ @ E2[0], h_ @ E1[0])
        E1, E2 = np.cos(ang) * E1 + np.sin(ang) * E2, -np.sin(ang) * E1 + np.cos(ang) * E2
    tube = RoundTube(K, len(stations))
    phi = 2.0 * np.pi * np.arange(K) / K
    frames = []
    for k, st in enumerate(stations):
        C = np.array([np.interp(st, s, axis[:, d]) for d in range(3)])
        j = min(int(np.searchsorted(s, st)), len(s) - 1)
        t = T_[j]
        e1 = unit(E1[j] - t * (t @ E1[j]))
        e2 = np.cross(t, e1)
        if equal_arc:
            # the section by 144 rays, then K points at equal arc length from angle 0
            ph_ = 2.0 * np.pi * np.arange(144) / 144
            D_ = np.cos(ph_)[:, None] * e1[None, :] + np.sin(ph_)[:, None] * e2[None, :]
            S_ = field.ray(np.tile(C, (144, 1)), D_, reach=reach, step=0.002)
            if np.isnan(S_).any():
                raise RuntimeError(f'{name}: ring {k} at s {st:.3f}: a ray never leaves the part (axis outside the solid?)')
            sa_ = arclen(S_, closed=True)
            tq_ = np.linspace(0.0, sa_[-1], K, endpoint=False)
            Sc_ = np.vstack([S_, S_[:1]])
            Pk = np.column_stack([np.interp(tq_, sa_, Sc_[:, d]) for d in range(3)])
            # (back onto the section exactly: each point's own ray from the axis)
            D = unit(Pk - C - np.outer((Pk - C) @ t, t))
            Pk = field.ray(np.tile(C, (K, 1)), D, reach=reach, step=0.002)
        else:
            D = np.cos(phi)[:, None] * e1[None, :] + np.sin(phi)[:, None] * e2[None, :]
            Pk = field.ray(np.tile(C, (K, 1)), D, reach=reach, step=0.002)
        if np.isnan(Pk).any():
            raise RuntimeError(f'{name}: ring {k} at s {st:.3f}: a ray never leaves the part (axis outside the solid?)')
        for jj in range(K):
            tube.P[tube.R[k, jj]] = Pk[jj]
            tube.src[int(tube.R[k, jj])] = f'{name} ring {k}'
        frames.append((C, t, e1, e2))
    n = tube.n
    for capG, kr, sgn in ((tube.C0, 0, -1.0), (tube.C1, len(stations) - 1, 1.0)):
        C, t, e1, e2 = frames[kr]
        walk = tube.walk_idx()
        side = [np.array([tube.P[capG[p, q]] for p, q in walk[m * n:(m + 1) * n + 1]]) if m < 3 else
                np.array([tube.P[capG[p, q]] for p, q in walk[3 * n:] + walk[:1]]) for m in range(4)]
        top = side[0]                       # q 0, p 0 .. n
        right = side[1]                     # p n, q 0 .. n
        bot = side[2][::-1]                 # q n, p 0 .. n
        left = side[3][::-1]                # p 0, q 0 .. n
        PP = coons(top, bot, left, right)
        for p in range(1, n):
            for q in range(1, n):
                # (from the end ring's plane at the patch point's offset off the axis: inside the part, whatever its bend)
                off_ = PP[p, q] - C
                A_ = C + 0.9 * (off_ - t * (off_ @ t))
                hit = field.ray(A_[None], (sgn * t)[None], reach=2.5, step=0.002)[0]
                if not np.isfinite(hit[0]):
                    raise RuntimeError(f'{name}: no cap surface')
                tube.P[capG[p, q]] = hit
                tube.src[int(capG[p, q])] = f'{name} cap'
    assert not np.isnan(tube.P).any(), f'{name}: a vertex without a target'
    log(f'[b4] {name}: tube cage {tube.n_v} vertices, {len(tube.Q)} quads (K {K}, {len(stations)} rings), '
        f'{time.time() - t0:.1f}s')
    return tube, frames


def plan_pts(P, clear):
    P = np.atleast_2d(np.asarray(P, np.float64)).copy()
    P[:, 1] -= clear
    return P


def tube_axes(R):
    """the round tubes' axes (dense polylines, plan frame) and stations, from the seated descriptors"""
    clear = R['clear']
    D = R['descs']
    out = {}
    tb = TUBES
    # the scape: the round cone pole to pole, its rings by its radius
    d0 = D['scape'][0]
    a, b = plan_pts(d0['a'], clear)[0], plan_pts(d0['b'], clear)[0]
    u = unit(b - a)
    ax = np.linspace(a - d0['ra'] * u, b + d0['rb'] * u, 200)
    L = np.linalg.norm(ax[-1] - ax[0])
    pi_ = tb['scape']['pole_in']
    st = stations_by_radius(R['fields']['scape'], ax, pi_ * d0['ra'], L - pi_ * d0['rb'], tb['scape']['n'])
    out['scape'] = (ax, st)
    # the funicle: through its beads (blended end to end), its rings evenly along it
    beads = D['funicle']
    pts = [plan_pts(bd['a'], clear)[0] for bd in beads] + [plan_pts(beads[-1]['b'], clear)[0]]
    u = unit(pts[-1] - pts[0])
    a0 = pts[0] - beads[0]['ra'] * u
    a1 = pts[-1] + beads[-1]['rb'] * u
    ax = np.linspace(a0, a1, 400)
    pi_ = tb['funicle']['pole_in']
    out['funicle'] = (ax, np.linspace(pi_ * beads[0]['ra'], np.linalg.norm(a1 - a0) - pi_ * beads[-1]['rb'],
                                      tb['funicle']['n']))
    # each lamella: along its leaf (forward), from behind its stalk to the leaf's tip, both ends found on the part's own field
    # along the leaf's centreline (b4-1 put the tip 0.12 past the leaf's last point: the solid ends ~0.04 past it, the round
    # end's rho, so the last ring's axis point lay outside the part and its rays never left it)
    for k in range(4):
        st_, leaf = D[f'lamella_{k}']
        Pq = plan_pts(leaf['points'], clear)
        fwd = unit(Pq[-1] - Pq[0])
        fl = R['fields'][f'lamella_{k}']
        mid_ = 0.5 * (Pq[0] + Pq[-1])
        tip = fl.ray(mid_[None], fwd[None], reach=2.0, step=0.002)[0]
        base = fl.ray(mid_[None], -fwd[None], reach=2.5, step=0.002, last=True)[0]
        if not (np.isfinite(tip[0]) and np.isfinite(base[0])):
            raise RuntimeError(f'lamella_{k}: its centreline does not leave the part (the leaf\'s ends not found)')
        ax = np.linspace(base, tip, 200)
        L = np.linalg.norm(tip - base)
        # (three rings across the stalk, three along the leaf by its radius: the leaf narrows to its tip, b4-2's even rings
        # left the last interval 0.44 mm against the tip ring's 0.10 edges)
        st = np.concatenate([np.linspace(0.06, 2 * st_['ra'] - 0.04, 3),
                             stations_by_radius(fl, ax, 2 * st_['ra'] + 0.18, L - 0.06, tb['lamella']['n'] - 3)])
        out[f'lamella_{k}'] = (ax, st)
    # the palps: through their segments (round cones blended end to end)
    for nm in ('palp_max', 'palp_lab'):
        segs = D[nm]
        pts = [plan_pts(sg['a'], clear)[0] for sg in segs] + [plan_pts(segs[-1]['b'], clear)[0]]
        u0 = unit(pts[1] - pts[0])
        u1 = unit(pts[-1] - pts[-2])
        P0 = pts[0] - segs[0]['ra'] * u0
        P1 = pts[-1] + segs[-1]['rb'] * u1
        poly = np.vstack([P0] + pts + [P1])
        sp = arclen(poly)
        ss = np.linspace(0, sp[-1], 300)
        ax = np.column_stack([np.interp(ss, sp, poly[:, d]) for d in range(3)])
        # (smoothed: the segments' small angles at the joints, so the frames turn gently)
        from scipy.ndimage import gaussian_filter1d
        ax = np.column_stack([gaussian_filter1d(ax[:, d], 6, mode='nearest') for d in range(3)])
        ax[0], ax[-1] = P0, P1
        L = arclen(ax)[-1]
        pi_ = tb[nm]['pole_in']
        out[nm] = (ax, stations_by_radius(R['fields'][nm], ax, pi_ * segs[0]['ra'], L - pi_ * segs[-1]['rb'], tb[nm]['n']))
    return out


# ============================================================================================ RING RECORDS
def antenna_sleeve(R, scape_lim):
    """b4-3: the ANTENNAL SLEEVE (CROSSBREED §7.3 antenna_chain scape as corrected by R10 and the lead's decision 9: the graft ring
    the sleeve's PROXIMAL ring, 100 % on the parent, the head): the legs round's own sleeve (families/arthropod_cage.sleeve, so
    every graft ring of the beetle follows one rule): three planar rings normal to the scape's axis where it leaves the head (the
    head's field, B3h's, read only), each the scape's own section (rays on its limit) x in_child, K from the radius by §2.2's chord
    sag. Returns the sleeve dict (the left antenna)"""
    from ..families import arthropod_cage as AC
    d0 = R['descs']['scape'][0]
    a, b = plan_pts(d0['a'], R['clear'])[0], plan_pts(d0['b'], R['clear'])[0]
    fh = R['fields']['head_coarse']
    s_ = AC.sleeve('antennal socket', a, unit(b - a), fh, AC.MeshQ(scape_lim.V, scape_lim.tris()), graft=True)
    s_.update(parent='head', child='scape', parent_joint='head', child_joint='antenna_0_L')
    return s_


NECK = dict(step=0.15, in_child=0.84)   # the neck sleeve's ring spacing toward the head (mm) and its distal rings' share of the
#                                         head's own section (the legs' SLEEVE in_child)


def neck_sleeve(R, prox, centre):
    """b4-3: the NECK SLEEVE (CROSSBREED §7.3 head_region neck: the head -> prothorax sleeve in the pronotal emargination; R10: its
    proximal ring the graft ring, 100 % on the pronotum): the proximal ring the pronotum cage's NECK RING (a loop of its socket's
    wall at z_neck, planar, at equal angles about the socket's centre: `prox` its low vertices in CROSSBREED's order), two more
    rings toward the head (+z) at NECK step, each vertex at its proximal vertex's angle on the head's own section (B3h's field,
    read only) x in_child: hidden inside the head at rest. Returns a sleeve dict as the legs' (V, Q, K, X, axis, frame, radii,
    step, step_in, sag_texels)"""
    from ..families import arthropod_cage as AC
    prox = np.asarray(prox, np.float64)
    K = len(prox)
    fh = R['fields']['head_coarse']
    axis = np.array([0.0, 0.0, 1.0])
    Z, Xt, Y = AC.port_frame(axis, 'L')
    ang = np.arctan2((prox - centre) @ Y, (prox - centre) @ Xt)
    D = np.cos(ang)[:, None] * Xt[None, :] + np.sin(ang)[:, None] * Y[None, :]
    rings, radii = [prox], [np.linalg.norm((prox - centre) - ((prox - centre) @ axis)[:, None] * axis, axis=1)]
    for j in (1, 2):
        c = centre + j * NECK['step'] * axis
        S_ = fh.ray(np.tile(c, (K, 1)), D, reach=12.0, step=0.004)
        if np.isnan(S_).any():
            raise RuntimeError('the neck sleeve: a ray from its axis never leaves the head')
        r = NECK['in_child'] * np.linalg.norm(S_ - c, axis=1)
        rings.append(c[None, :] + r[:, None] * D)
        radii.append(r)
    V = np.vstack(rings)
    Q = np.array([(j * K + k, j * K + (k + 1) % K, (j + 1) * K + (k + 1) % K, (j + 1) * K + k) for j in range(2) for k in
                  range(K)], int)
    c_ = V[Q].mean(1)
    nq = np.cross(V[Q[:, 2]] - V[Q[:, 0]], V[Q[:, 3]] - V[Q[:, 1]])
    radial = c_ - (centre + ((c_ - centre) @ axis)[:, None] * axis[None, :])
    if np.sum(np.einsum('ij,ij->i', nq, radial)) < 0:
        Q = Q[:, ::-1].copy()
    sag = max(float(np.max(r) * (1.0 - np.cos(np.pi / K))) for r in radii) / AC.TEXEL_LIFE
    return dict(name='neck', V=V, Q=Q, K=K, X=centre, axis=axis, frame=dict(Z=Z, X=Xt, Y=Y), step=NECK['step'],
                step_in=NECK['step'], radii=radii, sag_texels=sag, graft=True, parent='pronotum', child='head',
                parent_joint='pronotum', child_joint='head')


def port_record(name, verts, normals, Z, X, joint, native, kind, cut, side='L', h=None, set_name='BODY', cls='chitin',
                build='', spec=None, sk=None, seam_k=None, origin=None):
    """b4-3: a SURFACE PORT's ring record (the elytra / hindwing port) in the legs round's schema (families/arthropod_cage.
    ring_record: CROSSBREED §2.11 at the author scale in metres, the frame and origin in the parent joint's bind frame when sk is
    given); verts / origin in the WORLD frame, life mm (the plan frame's h + the clearance: the legs' and the skeleton's frame),
    the LOW's vertices (the cage at its limit positions), the frozen normals the limit's; plus §2.2's checks (K = 0 mod 4, equal
    parametric angles about the origin (the vertices' centroid unless given), planarity within 0.02 r_bar, the chord sag within
    2 texels at x10)"""
    from ..families import arthropod_cage as AC
    a = float(spec['author_scale']) if spec is not None else 10.0
    sc = a * 1e-3
    V = np.asarray(verts, np.float64)
    K = len(V)
    Z = unit(np.asarray(Z, np.float64))
    X = unit(np.asarray(X, np.float64) - Z * (Z @ np.asarray(X, np.float64)))
    Y = np.cross(Z, X)
    c = V.mean(0) if origin is None else np.asarray(origin, np.float64)
    loc = np.column_stack([(V - c) @ X, (V - c) @ Y])
    secf, resid = AC.section_fit(loc)
    rr = np.hypot(loc[:, 0], loc[:, 1])
    rbar = float(rr.mean())
    planar = float(np.max(np.abs((V - c) @ Z)))
    ang = np.degrees(np.arctan2(loc[:, 1], loc[:, 0]))
    want = 360.0 * np.arange(K) / K
    dang = (ang - want + 180.0) % 360.0 - 180.0
    sag_t = float(rr.max() * (1.0 - np.cos(np.pi / K))) / AC.TEXEL_LIFE
    rec = dict(name=name, K=K, cut=cut, kind=kind, side=side, frame_creature=dict(normal=Z.tolist(), tangent=X.tolist()),
               origin_creature=(c * sc).tolist(), frame=None, origin=None,
               section={k: (v * sc if k == 'r0' else v) for k, v in secf.items()}, section_residual=(resid * sc).tolist(),
               verts=(V * sc).tolist(), normals=np.asarray(normals, np.float64).tolist(),
               weights=dict(joints=[joint], w=[[1.0] for _ in range(K)]), coat=None, h=(None if h is None else h * sc),
               seam_k=seam_k, px_per_m=PX_PER_M, set=set_name, **{'class': cls}, native=native, planarity=planar / rbar,
               sag_texels=sag_t, units='metres at the author scale', author_scale=a, build=build,
               checks=dict(K_mod4=K % 4 == 0, angle_dev_deg=float(np.abs(dang).max()), r_bar_x10_mm=rbar * a,
                           r_max_x10_mm=float(rr.max()) * a, planarity_rel=planar / rbar, planar_ok=planar <= 0.02 * rbar,
                           sag_texels=sag_t, sag_ok=sag_t <= 2.0))
    return AC.joint_frame(rec, sk) if sk is not None else rec


def sleeve_checks(rec):
    """§2.2's checks on a sleeve's ring record (the legs' schema, metres at the author scale): K = 0 mod 4, planarity, the sag;
    the angles about the ring's own centroid"""
    V = np.asarray(rec['verts'], np.float64)
    K = len(V)
    Z, X = np.asarray(rec['frame_creature']['normal']), np.asarray(rec['frame_creature']['tangent'])
    Y = np.cross(Z, X)
    c = V.mean(0)
    loc = np.column_stack([(V - c) @ X, (V - c) @ Y])
    ang = np.degrees(np.arctan2(loc[:, 1], loc[:, 0]))
    want = 360.0 * np.arange(K) / K
    if rec.get('side') == 'R':
        ang = -ang
    dang = (ang - want + 180.0) % 360.0 - 180.0
    rr = np.hypot(loc[:, 0], loc[:, 1])
    a = float(rec.get('author_scale', 10.0))
    return dict(K_mod4=K % 4 == 0, angle_dev_deg=float(np.abs(dang).max()), r_bar_x10_mm=float(rr.mean()) * 1e3 * 10.0 / a,
                r_max_x10_mm=float(rr.max()) * 1e3 * 10.0 / a, planarity_rel=float(rec['planarity']),
                planar_ok=float(rec['planarity']) <= 0.02, sag_texels=float(rec['sag_texels']),
                sag_ok=float(rec['sag_texels']) <= 2.0)



"""The octopus's SCULPT PLAN (the sculpt tier, features of ~1 mm and up; research/SD_SKIN_BRIEF.md §1.3).

Every stroke is placed on the BASE surface (the analytic block-out) in anatomical coordinates and planned BEFORE the
voxel grid exists, so the grid's band grows around each stroke (t10: suckers stand ~3-6 mm off the skin and a fixed
+-2.5 mm band sliced them flat at its voxel-staircase edge); then applied as stroke-local GPU brushes.

  * ARM features are planned on the reference arm (the one the stacked arms texture set bakes from) and replicated
    to the other seven by their azimuth rotation, so each arm's base inside the crown (the head texture set) continues
    exactly across the seam into the stacked arms set. Lengths are each arm's own (octopus.arm_length); one plan
    rotated holds only while the arms are identical (arm_rotations checks it: the live formula 3 = 2 > 4 > 1 needs
    per-pair plans). The arms' NEIGHBOURS are not identical (the webs by sector, the body's blend over L4 and R4), so
    the papillae's copies are each seated on their own arm's skin (polish 1, seat_papillae).
  * PAPILLAE sit at the centres of the skin's patches ("papillae often arise from the centre of patches", brief
    §2.1): the patch network is proc.cellular3 in the anatomical coordinate (the head set: the point itself; an arm:
    its straightened, radius-normalised coordinate, arm_coord), the same function the material pass draws the grooves
    with, so the two tiers agree by construction. Behind each arm's first node (the crown top round the head) the skin
    paints the head network and, fading out over 10 mm from the node, the arm's (crown v5d's octopus_skin): the head
    papillae go where it paints the head's, the arm's papillae where it paints the arm's (skin_net, root_sites), the
    head's denser there than the crown top's 0.38 (crown strip round, 10-27: that strip was planted by nobody).
  * SUCKERS (brief R1b, Tramacere 2013; research/BLOCKOUT_V4_SPEC.md 1.7, 4.7): SESSILE ("embedded without stalks";
    live photos 14, 15: low cups on a broad base, no neck), a base cone flaring into the arm, the cup up to the
    infundibulum disc with a raised rim, a shallow dish falling to the orifice (~0.18 d), the acetabulum chamber below
    it with the O. vulgaris roof protuberance showing through. Biserial, the first three single, and a single row
    carried across the oral disc to the lip; the largest (17.5 mm) the 15th-19th, about a sixth of the way out,
    tapering to about a millimetre at the tip.
  * EYES (v4: a 30 mm eyeball standing on its turret): the socket, a LID BOWL carved round the eyeball so the turret's
    skin slopes down onto it at the aperture's edge (eye_lid), the lid's rolled margin on the eyeball; the supraocular
    papillae ("horns") over each eye, primary papillae round its rim and the three ventral eye papillae under it
    (Allen et al. 2014), all on the turret outside the bowl.

Real-animal scale (Octopus vulgaris, ML 0.20 m); every size is in metres.
"""
import numpy as np
import warp as wp

from .. import growth as GR
from .. import proc
from ..voxel import STROKE_CONE, STROKE_CYL, STROKE_ECONE, STROKE_PRISM4, STROKE_PRISM6, STROKE_TORUS
from .octopus import arm_azimuths, arm_length, arm_radius, eye_geom, funnel_geom, sucker_size

# the skin's patch network: the head set's pitch 2.8 mm (live photo 04: 13 patches in 0.79 mound diameters, 0.014 ML
# at ML 200; 2.4 mm read a size finer), the arms' 1.8 mm (scaled down further with the arm's radius: arm_tables)
PATCH = dict(head=0.0028, arm=0.0018, disorder=0.9, seed_head=101, seed_arm=202)
# forward-only kernels, the cellular noise's neighbour loops left rolled (octopus_skin's options: k_arm_draw inlines the
# skin's twice-warped cellular3)
wp.set_module_options({'enable_backward': False, 'max_unroll': 1})


class Plan:
    """stroke batches (applied in order: each batch is unioned exactly within itself, then added or carved with its
    fillet) plus the instance data the material pass reads (suckers, papillae, growths)"""

    def __init__(self):
        self.ops = []
        self.inst = {}

    def add(self, kind, A, B, ra, rb, mode, k, tag, mat=None, rc=None):
        """mat: the batch's MATERIAL ID (voxel.SparseSDF.strokes: written where the batch wins; None = skin for an
        add, no write for a carve); rc: per-stroke spins (the prism kinds, growth.emit)"""
        A = np.asarray(A, np.float64).reshape(-1, 3)
        if len(A):
            n = len(A)
            self.ops.append(dict(kind=np.broadcast_to(np.asarray(kind, np.int32), (n,)).copy(), A=A,
                                 B=np.asarray(B, np.float64).reshape(-1, 3),
                                 ra=np.broadcast_to(np.asarray(ra, np.float64), (n,)).copy(),
                                 rb=np.broadcast_to(np.asarray(rb, np.float64), (n,)).copy(), mode=mode, k=float(k),
                                 tag=tag, mat=None if mat is None else int(mat),
                                 rc=np.zeros(n) if rc is None else np.broadcast_to(np.asarray(rc, np.float64),
                                                                                   (n,)).copy()))

    def bounds(self, prog=None, band=None):
        """each stroke's bounding sphere (centre, radius incl. its fillet): the voxel grid's extra activation. With
        prog and band, only the spheres the band cannot hold: an ADD reaching past 0.8 of the band off the block-out
        (t10: 100k papilla spheres inside the band anyway took the allocation from 35 s to 189 s and added 31M
        voxels), a CARVE reaching deeper than 0.8 of the band into it (the eye socket, ~20 mm under the skin). (One
        sphere round a whole lid bowl wakes a 27 mm ball of air in front of each eye; since voxel.redistance leaves
        the values past its band as sculpted, that air holds: spheres along the carves' surfaces in its place,
        tried 10-21, woke as many voxels, 35.2M against 35.0M round an eye and the largest suckers, and the same field,
        patches/v4_sculpt/check/check_shells.py)"""
        C, R, M = [], [], []
        for o in self.ops:
            A, B = o['A'], o['B']
            half = 0.5 * np.linalg.norm(B - A, axis=1)
            kind = o['kind']
            reach = np.where(kind == STROKE_CYL, o['ra'], np.where(kind == STROKE_TORUS, o['ra'] + o['rb'],
                                                                     np.maximum(o['ra'], o['rb'])))
            ec = kind == STROKE_ECONE
            pr = (kind == STROKE_PRISM6) | (kind == STROKE_PRISM4)
            one = ~ec & ~pr
            C.append(np.where((kind == STROKE_TORUS)[:, None], A, 0.5 * (A + B))[one])
            R.append((np.where(kind == STROKE_TORUS, reach, half + reach) + 2.0 * o['k'])[one])
            M.append(np.full(int(one.sum()), o['mode'] == 'add'))
            # a growth prism: spheres along its axis (thin) or on its wall (thick), never one round the whole crystal
            # (growth.prism_spheres)
            if pr.any():
                pc, rc = GR.prism_spheres(A[pr], B[pr], o['ra'][pr], o['rb'][pr], o['rc'][pr],
                                          np.where(kind[pr] == STROKE_PRISM6, 6, 4), band or 0.0025, o['k'])
                C.append(pc)
                R.append(rc)
                M.append(np.full(len(pc), o['mode'] == 'add'))
            # an elliptic cone: spheres along its WALL only, where it makes new surface (one sphere round the whole
            # cone woke ~26M voxels per eye: t10's allocation 194M voxels, 262 s)
            for i in np.nonzero(ec)[0]:
                pc, rc = econe_wall(A[i], B[i], o['ra'][i], o['rb'][i])
                C.append(pc)
                R.append(rc + 2.0 * o['k'] + (band or 0.0))
                M.append(np.full(len(pc), o['mode'] == 'add'))
        if not C:
            return np.zeros((0, 3)), np.zeros(0)
        C, R, M = np.concatenate(C), np.concatenate(R), np.concatenate(M)
        if prog is None or band is None:
            return C[M], R[M]
        f = prog.eval(C).astype(np.float64)
        need = np.where(M, f + R > 0.8 * band, f - R < -0.8 * band)
        return C[need], R[need]

    def apply(self, G, log=print, smooth=1, relevel=None):
        """the strokes in order (each batch with its material id and spins), then a light smooth and a relevel
        (the sculpt brief: every detail pass ends with Smooth(1..2, 0.5) and a Redistance so the details blend
        and the field is a distance again). With growth ids in the plan, both go by id: the crisp families (crystal
        facets) are held still (growth.smooth_table, growth.relevel_table)"""
        for o in self.ops:
            G.strokes(o['kind'], o['A'], o['B'], o['ra'], o['rb'], o['mode'], o['k'], rc=o.get('rc'),
                      mat=o.get('mat'))
        grown = any(o.get('mat') not in (None, GR.MAT_SKIN, GR.MAT_KEEP) for o in self.ops)
        if smooth:
            G.smooth(smooth, 0.5, id_weights=GR.smooth_table() if grown else None)
        if relevel is None or relevel > 0:        # (None: the whole band, voxel.SparseSDF.redistance; 0 skips it)
            G.redistance(relevel, id_weights=GR.relevel_table() if grown else None)
        log(f'[sculpt] applied {sum(len(o["A"]) for o in self.ops)} strokes in {len(self.ops)} batches '
            f'(+ smooth {smooth}, relevel {relevel}): ' + ', '.join(f'{o["tag"]} {len(o["A"])}' for o in self.ops))


def econe_wall(a, b, ha, hv, n_phi=96, n_z=10, z0=0.4):
    """points on an elliptic cone's wall (apex a, axis toward b, half-angles ha about the horizontal and hv about the
    vertical: voxel.sd_stroke's frame) from z0 of its length to its end, and the radius that closes the gaps"""
    ax = np.asarray(b, np.float64) - np.asarray(a, np.float64)
    L = np.linalg.norm(ax)
    n = ax / L
    e_h = np.cross([0.0, 1.0, 0.0], n)
    e_h /= np.linalg.norm(e_h)
    e_u = np.cross(n, e_h)
    phi = np.linspace(0.0, 2.0 * np.pi, n_phi, endpoint=False)
    d = n[None] + np.tan(ha * np.cos(phi))[:, None] * e_h[None] + np.tan(hv * np.sin(phi))[:, None] * e_u[None]
    z = np.linspace(z0 * L, L, n_z)
    P = np.asarray(a, np.float64)[None, None] + z[None, :, None] * d[:, None, :]
    gap = max(np.linalg.norm(np.roll(P, 1, axis=0) - P, axis=-1).max(),
              np.linalg.norm(np.diff(P, axis=1), axis=-1).max())
    return P.reshape(-1, 3), np.full(n_phi * n_z, 0.5 * gap)


def funnel_mask(pts, spec, margin=0.003):
    """1 on the funnel's skin (within its cone plus a margin, from where it leaves the body), 0 off it, a 4 mm ramp. The
    v4 funnel leaves from under the mantle's free margin at its exit (the margin's ventral point lies 0.065 of the cone
    behind it, octopus.mantle_margin), so the skin is the funnel's from the exit on: the ramp runs over its first 15 %
    (r4's 0.30-0.50 was where that funnel's cone left the head's side); the cut end and the channel are t = 1"""
    fa, fb, fra, frb = funnel_geom(spec)
    ax = fb - fa
    L = np.linalg.norm(ax)
    ax = ax / L
    t = np.clip((pts - fa) @ ax / L, 0.0, 1.0)
    d = np.linalg.norm(pts - (fa[None] + (t * L)[:, None] * ax[None]), axis=1)
    w_r = np.clip(1.0 - (d - (fra + (frb - fra) * t) - margin) / 0.004, 0.0, 1.0)
    return w_r * np.clip(t / 0.15, 0.0, 1.0)


def mouth_lip(plan, prog, rng, n=17):
    """the inner lip's radial RIDGES (ORAL_REFERENCE §4: about 16-17 main ridges near the opening, subdividing to about
    25-40 toward the lip's edge): each a low raised stroke from just outside the fringe out over the crest, forking in
    two at ~0.62 L, the branches fading out by height at uneven reach before the groove. (Round 5's 26 carved creases
    were the inverse: slots cut into the rim, overlapping there and tapering outward, a starburst of dark wedges.)"""
    M_ = prog.mouth
    c, up, R, r = M_['c'], M_['up'], M_['R'], M_['r']
    ax_, az_ = M_.get('ax', M_['r_open']), M_.get('az', M_['r_open'])
    rim = lambda a_: ax_ * az_ / np.sqrt((az_ * np.sin(a_)) ** 2 + (ax_ * np.cos(a_)) ** 2)   # the opening's radius
    L = R + r
    step = 2.0 * np.pi / n

    def column(a, rho):
        """the lip's surface straight above (along up) each (angle, radius) seen from below: the first crossing into
        the solid, so a point keeps its radius on the inner slope (settle's nearest point drifts ~1.5 mm outward
        there)"""
        u = np.column_stack([np.sin(a), np.zeros(len(a)), np.cos(a)])
        base = c[None] + rho[:, None] * u
        ts = np.linspace(-(r + 0.006), r + 0.004, 97)
        f = prog.eval((base[:, None] + ts[None, :, None] * up[None, None]).reshape(-1, 3)).reshape(len(a), -1)
        k = np.argmax(f < 0.0, axis=1)
        assert np.all(k > 0), 'a lip ridge point found no surface from below'
        lo, hi = ts[k - 1], ts[k]
        for _ in range(10):
            mid = 0.5 * (lo + hi)
            inside = prog.eval(base + mid[:, None] * up[None]) < 0.0
            hi, lo = np.where(inside, mid, hi), np.where(inside, lo, mid)
        p = base + (0.5 * (lo + hi))[:, None] * up[None]
        return p, prog.normals(p)

    segs = {'lip ridge': [], 'lip ridge branch': []}

    def ridge(a, rho, w, h, tag):
        """a ridge along the angles a (per point) and radii rho: half-width w, standing h proud of the skin"""
        p, nn = column(a, rho)
        p = p - nn * (w - h)[:, None]
        segs[tag].append((p[:-1], p[1:], w[:-1], w[1:]))

    for a0 in np.arange(n) * step + rng.normal(0.0, 0.15 * step, n):
        # the main ridge: rising from the fringe's foot, constant girth, to the fork
        r0, rf = 1.15 * rim(a0), 0.62 * L
        rho = np.linspace(r0, rf, 4)
        # (0.22 mm stood 0.7 of a 0.3 mm voxel, ORAL_REFERENCE R4.7 row 7: at least 0.35 mm to survive the grid)
        w = np.full(4, 0.00048 * (0.9 + 0.2 * rng.random()))
        h = 0.00036 * np.array([0.55, 0.9, 1.0, 1.0])
        ridge(np.full(4, a0), rho, w, h, 'lip ridge')
        # two branches diverging to half the main spacing, fading out by height (the corrugation subsides toward the
        # groove; no tapering wedge)
        for s in (-1.0, 1.0):
            re = L * (0.80 + 0.17 * rng.random())
            f = np.linspace(0.0, 1.0, 5)
            a_b = a0 + s * (0.25 * step) * (3.0 * f * f - 2.0 * f ** 3)
            w_b = np.full(5, 0.00040 * (0.9 + 0.2 * rng.random()))
            h_b = 0.00032 * (1.0 - f) ** 1.3
            h_b[-1] = -0.3 * w_b[-1]                            # the last point sunk: the branch ends under the skin
            ridge(a_b, rf + (re - rf) * f, w_b, h_b, 'lip ridge branch')
    for tag, ss in segs.items():
        plan.add(STROKE_CONE, *[np.concatenate(x) for x in zip(*ss)], 'add', 0.00030, tag)
    # ORAL_REFERENCE §1, §4: TWO lips. The inner lip (the torus) is ringed at its foot by a deep groove; outside it the
    # web's contractile edge makes a low, smooth outer lip; the inner lip's free edge is fringed with short finger-like
    # papillae (about 25-40). The groove sits on the SKIN's height at its radius, its tube 0.2 mm into it: 0.9 mm deep
    # all round (R4.3 item 4: on the mouth plane it cut 0.35 mm at the sides and 0.86 fore and aft; the v4 oral disc's
    # skin there lies 0.05-0.25 mm under the plane, patches/v4_sculpt)
    ag = np.arange(16) * 2.0 * np.pi / 16
    pg, _ = column(ag, np.full(16, 1.02 * L))
    hg = float(np.mean((pg - c[None]) @ up))
    plan.add(STROKE_TORUS, (c + up * (hg + 0.0002))[None], (c + up)[None], 1.02 * L, 0.0007, 'carve', 0.0003,
             'lip groove')
    # the outer lip as a chain of soft strokes of varying girth and reach, settled on the skin (a uniform torus read
    # as a washer, t10 round 5: the web's contractile edge is soft and uneven)
    no = 40
    ao = np.arange(no + 1) * 2.0 * np.pi / no
    ro_ = 1.22 * L * (1.0 + 0.03 * np.sin(3.0 * ao + 1.3) + 0.02 * np.sin(7.0 * ao + 0.4))
    uo = np.column_stack([np.sin(ao), np.zeros(no + 1), np.cos(ao)])
    po, nno = settle(prog, c[None] + uo * ro_[:, None] - up[None] * 0.002)
    go = 0.00075 * (1.0 + 0.25 * np.sin(5.0 * ao + 2.1) + 0.15 * rng.normal(0.0, 1.0, no + 1))
    go[-1] = go[0]
    po = po + nno * (0.15 * go)[:, None]
    plan.add(STROKE_CONE, po[:-1], po[1:], go[:-1], go[1:], 'add', 0.0010, 'outer lip')
    nf = 25                     # (32 fingers touched on the rim, 0.74 mm apart: ORAL_REFERENCE R4.7 row 25, 24-26)
    af = np.arange(nf) * 2.0 * np.pi / nf + rng.normal(0.0, 0.25 * 2.0 * np.pi / nf, nf)
    uf = np.column_stack([np.sin(af), np.zeros(nf), np.cos(af)])
    pf, nnf = settle(prog, c[None] + uf * (1.06 * rim(af))[:, None] - up[None] * 0.0008)
    # each finger from the rim inward over the opening and a little down, its length and girth varied
    tipd = -uf * 0.6 - up[None] * 0.4 + nnf * 0.3
    tipd /= np.linalg.norm(tipd, axis=1, keepdims=True)
    ln = 0.0008 + 0.0005 * rng.random(nf)
    rb = 0.00028 + 0.00012 * rng.random(nf)
    plan.add(STROKE_CONE, pf - nnf * (0.5 * rb)[:, None], pf + tipd * ln[:, None], rb, 0.45 * rb, 'add', 0.00012,
             'lip fringe')


def rot_y(phi):
    c, s = np.cos(phi), np.sin(phi)
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])


def arm_rotations(order, spec=None):
    """the rotations taking the reference arm (cage column 0 = arms[order[0]]) onto every arm (column order). A rotated
    copy is that arm's plan only when the arms are IDENTICAL: with spec, every arm's own length (octopus.arm_length)
    must equal the reference's (the live formula 3 = 2 > 4 > 1, SPEC['arm_pair_len'], waits on per-pair plans: rotated,
    a 0.90 m arm's suckers would land on a 0.72 m arm by its length, not its share)"""
    az = arm_azimuths()
    a0 = az[order[0]]
    if spec is not None:
        lens = np.array([arm_length(spec, az[o]) for o in order])
        assert np.allclose(lens, lens[0]), f'arms of unequal length {np.round(lens, 3)}: one plan rotated does not fit'
    return [rot_y(az[order[j]] - a0) for j in range(len(order))]


def ref_azimuth():
    """the reference arm's azimuth: the cage's column 0 (columns run by theta = -azimuth from 0: R1), the arm the
    stacked arms set bakes from (octopus.web_plan and build_cage order the arms the same way)"""
    az = arm_azimuths()
    return az[int(np.argmin(np.mod(-np.degrees(az), 360.0)))]


def replicate(plan_ref, rots, out):
    """copy every batch of a reference-arm plan onto all arms (identical arms: arm_rotations), with its material id; a
    prism's spin re-derived per copy, as growth.replicate does (onb alone does not give the rotated frame)"""
    for o in plan_ref.ops:
        A = np.concatenate([o['A'] @ R.T for R in rots])
        B = np.concatenate([o['B'] @ R.T for R in rots])
        n = len(rots)
        pr = (o['kind'] == STROKE_PRISM6) | (o['kind'] == STROKE_PRISM4)
        rcs = []
        if pr.any():
            _, u0, _, _ = GR.prism_frame(o['A'][pr], o['B'][pr], o['rc'][pr])
        for R in rots:
            r = o['rc'].copy()
            if pr.any():
                a, b = o['A'][pr] @ R.T, o['B'][pr] @ R.T
                r[pr] = GR.spin_for((b - a) / np.linalg.norm(b - a, axis=1, keepdims=True), u0 @ R.T)
            rcs.append(r)
        out.add(np.tile(o['kind'], n), A, B, np.tile(o['ra'], n), np.tile(o['rb'], n), o['mode'], o['k'], o['tag'],
                mat=o['mat'], rc=np.concatenate(rcs))


def seat_papillae(prog, p, n, rb, h, rots, tip=0.40, keep=5.0e-5, buried=0.004, floating=0.001, move=0.004):
    """(polish 1) the reference arm's PAPILLAE (base points p, normals n, base radii rb, heights h) on every arm, each
    copy SEATED on its own arm's skin. The arms are identical, their neighbours are not: the webs differ by sector,
    and on L4 and R4 the body's blend (the mantle's apex is the body sweep's first node, and sdf.sd_sweep divides the
    field behind it by its steep first segment's slope, so it reads 5-16 mm along their backs at s 0.25-0.7 and the
    arms' 16 mm blend swells them by up to 1.9 mm). Rotated copies sat under that skin (7,000 of L4's and of R4's
    12,337, 1.8-2.0 mm deep at s 0.20-0.33: the streak audit's largest plan and relief holes; 440-930 on each other
    arm, 0.3-0.6 mm under the webs' blends near the crown) or in the air beside it (up to 25 mm beside L1 and R4, where
    the reference's web junction has no counterpart). A copy on its arm's skin (|f| <= keep) stays replicate's exact
    copy; one under it by up to `buried` or over it by up to `floating` takes its nearest skin point (settle) when that
    lies within `move`; any other copy is dropped. Returns the batch (A, B, ra, rb in replicate's order: copy by copy
    in rots order) and the seated instances dict(p, n, rb, arm (the copy's column), moved), and per copy (kept as
    rotated, moved, dropped)"""
    A0 = p - n * (0.45 * rb)[:, None]                  # (papilla_strokes' stroke, on the reference arm)
    B0 = p + n * h[:, None]
    As, Bs, RB, Ps, Ns, J, MV, counts = [], [], [], [], [], [], [], []
    for j, R in enumerate(rots):
        A, B, pj, nj = A0 @ R.T, B0 @ R.T, p @ R.T, n @ R.T
        keep_m = np.ones(len(p), bool)
        mv = np.zeros(len(p), bool)
        if j > 0:
            f = prog.eval(pj).astype(np.float64)
            off = np.abs(f) > keep
            keep_m = ~off
            cand = np.nonzero(off & (f >= -buried) & (f <= floating))[0]
            if len(cand):
                q, nq = settle(prog, pj[cand])
                ok = np.linalg.norm(q - pj[cand], axis=1) <= move
                idx, q, nq = cand[ok], q[ok], nq[ok]
                A[idx] = q - nq * (0.45 * rb[idx])[:, None]
                B[idx] = q + nq * h[idx][:, None]
                pj[idx], nj[idx] = q, nq
                keep_m[idx] = True
                mv[idx] = True
        counts.append((int(keep_m.sum() - mv.sum()), int(mv.sum()), int((~keep_m).sum())))
        As.append(A[keep_m])
        Bs.append(B[keep_m])
        RB.append(rb[keep_m])
        Ps.append(pj[keep_m])
        Ns.append(nj[keep_m])
        J.append(np.full(int(keep_m.sum()), j))
        MV.append(mv[keep_m])
    rb_all = np.concatenate(RB)
    return (np.concatenate(As), np.concatenate(Bs), rb_all, tip * rb_all,
            dict(p=np.concatenate(Ps), n=np.concatenate(Ns), rb=rb_all, arm=np.concatenate(J), moved=np.concatenate(MV)),
            counts)


# ------------------------------------------------------------------------------------------- anatomical coordinates
def arm_tables(spec, n=4096, rmin=0.3, az=None):
    """the straightened arm coordinate: along = U(s) = the arclength in units of the local radius over the crown
    radius (patches and wrinkles shrink with the arm, clamped at rmin of the crown radius so they stay >= ~4 texels),
    around = an angle on a circle of radius R(s) (= r0 until the clamp, then shrinking with r so the two directions
    keep one scale), along the arm at azimuth az's OWN length (octopus.arm_length; default the reference arm's,
    ref_azimuth: the stacked arms set's). Returns (s, U, R) tables in metres"""
    s = np.linspace(0.0, 1.0, n)
    r = arm_radius(s, spec)
    r0 = spec['arm_r0']
    reff = np.maximum(r, rmin * r0)
    g = r0 / reff
    L = arm_length(spec, ref_azimuth() if az is None else az)
    U = np.concatenate([[0.0], np.cumsum(0.5 * (g[1:] + g[:-1]) * np.diff(s))]) * L
    return s, U, r0 * r / reff


def arm_coord(s, alpha, tables):
    st, U, R = tables
    u = np.interp(s, st, U)
    rr = np.interp(s, st, R)
    return np.column_stack([u, rr * np.cos(alpha), rr * np.sin(alpha)])


def arm_s_of_u(u, tables):
    st, U, R = tables
    return np.interp(u, U, st)


# ------------------------------------------------------------------------------------------- surface helpers
def arm_frame(arm, s):
    Pa, na, ba, ta = arm
    sa = np.linspace(0, 1, len(Pa))
    s = np.atleast_1d(s)
    ip = lambda X: np.column_stack([np.interp(s, sa, X[:, k]) for k in range(3)])
    return ip(Pa), ip(na), ip(ba)


def arm_surface(prog, arm, s, alpha, spec, maxd=0.05):
    """the base surface's point and normal on an arm at (s, alpha) (alpha from the aboral side toward +b)"""
    s = np.atleast_1d(np.asarray(s, np.float64))
    alpha = np.broadcast_to(np.atleast_1d(alpha), s.shape)
    c, n, b = arm_frame(arm, s)
    d = np.cos(alpha)[:, None] * n + np.sin(alpha)[:, None] * b
    r = arm_radius(s, spec)
    # (the projector takes the OUTWARD direction and marches against it from outside)
    p, st = prog.project(c + d * (r + 0.012)[:, None], d, maxd=maxd)
    return p, prog.normals(p), st


def settle(prog, pts, iters=3):
    """the nearest base-surface points (p - f grad f, repeated)"""
    p = np.asarray(pts, np.float64)
    for _ in range(iters):
        f = prog.eval(p).astype(np.float64)
        p = p - f[:, None] * prog.normals(p)
    return p, prog.normals(p)


def arm_owner(pts, arms, spec, margin=1.15, past_first=False):
    """for each point, whether it lies on an arm's tube (within margin x the local radius of a centreline) rather than
    on the crown's webs or the body: the territory the replicated arm features own. The nearest centreline POINT
    decides, so each first node holds a ball of margin x r0 (~30 mm) round it. past_first (head_sites; crown strip
    round 10-27): the ball's half BEHIND the node (the first segment's t < 0) is nobody's, since arm_sites plants s > 0
    only (it was planted by nobody: Skye's bare strip round the head). That is the polyline measure past the first
    node: behind its plane the node is the centreline's nearest point"""
    from scipy.spatial import cKDTree
    sa = np.linspace(0, 1, len(arms[0][0]))
    P = np.concatenate([a[0] for a in arms])
    S = np.tile(sa, len(arms))
    d, i = cKDTree(P).query(pts)
    own = d < margin * arm_radius(S[i], spec)
    if past_first:
        j, k = i // len(sa), i % len(sa)
        P0 = np.array([a[0][0] for a in arms])[j]
        t0 = np.array([a[0][1] - a[0][0] for a in arms])[j]
        own &= ~((k == 0) & (((np.asarray(pts, np.float64) - P0) * t0).sum(1) < 0.0))
    return own


# ------------------------------------------------------------------------------------------- the skin's patch networks
def _smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


@wp.kernel
def k_arm_draw(q: wp.array(dtype=wp.vec3), s_arm: float, disorder: float, seed: int, out: wp.array(dtype=float)):
    """the material pass's per-cell draw for the ARM patch network at arm coordinates q (octopus_skin.skin_at: the
    coordinate's cell after its two warps, the cell's random hashed again); a cell takes the arm network where the
    network's weight beats its draw"""
    t = wp.tid()
    qw = proc.warp3(proc.warp3(q[t], 0.008, 0.00055, seed + 5), 0.0026, 0.00022, seed + 6)
    cl = proc.cellular3(qw / s_arm, disorder, seed)
    out[t] = proc.u01(proc.hash3i(int(cl.rand * 16777216.0), 29, 31, seed + 7))


def skin_net(pts, arms, order, spec, tables):
    """which patch network the material pass paints at points of the head set, as crown v5d's octopus_skin.skin_at
    decides it (its first block, term by term; keep the two in step): the nearest arm by azimuth, the point rotated onto
    the reference arm, its nearest point on the centreline (t clamped), then (polish 1) the sweep's FOOT POINT near it
    (octopus_skin.foot_frame: s, seg, bd, alpha), the arm coordinate q continued off the tube from the arm's section
    radius (octopus_skin.section_k) and behind the first node, the network's weight w (armw, faded out over 10 mm behind
    the first node and near the sector's bisector) and per point whether its cell takes the ARM network (w over the
    cell's draw, k_arm_draw). Returns dict(arm (azimuth index), behind, bd, r, alpha, q, w, is_arm)"""
    from .octopus_skin import foot_frame, node_tangents, section_k
    st, U, R = tables
    rad = arm_radius(st, spec)
    az = arm_azimuths()
    Pr, Nr, Br = arms[order[0]][0], arms[order[0]][1], arms[order[0]][2]
    n = len(Pr)
    p = np.asarray(pts, np.float64).reshape(-1, 3)
    dz = np.abs(np.mod(np.arctan2(p[:, 0], p[:, 2])[:, None] - az[None] + np.pi, 2.0 * np.pi) - np.pi)
    jb = dz.argmin(1)
    best = dz[np.arange(len(p)), jb]
    q0 = np.einsum('kij,kj->ki', np.array([rot_y(az[order[0]] - a) for a in az])[jb], p)
    nodes = np.arange(0, n, 4)
    bi = nodes[np.linalg.norm(q0[:, None] - Pr[nodes][None], axis=2).argmin(1)]
    bd, s, seg = np.full(len(p), np.inf), np.zeros(len(p)), np.zeros(len(p), np.int64)
    for o in range(-5, 6):
        i = bi + o
        ok = (i >= 0) & (i <= n - 2)
        i = np.clip(i, 0, n - 2)
        e = Pr[i + 1] - Pr[i]
        t = np.clip(((q0 - Pr[i]) * e).sum(1) / np.maximum((e * e).sum(1), 1e-12), 0.0, 1.0)
        d = np.linalg.norm(q0 - Pr[i] - e * t[:, None], axis=1)
        b = ok & (d < bd)
        bd[b], s[b], seg[b] = d[b], ((i + t) / (n - 1))[b], i[b]
    fr = foot_frame(q0, Pr, Nr, node_tangents(Pr), s)
    s, seg, bd, alpha = fr['s'], fr['seg'], fr['bd'], fr['alpha']
    r = np.interp(s, st, rad)
    t0a = (Pr[1] - Pr[0]) / np.linalg.norm(Pr[1] - Pr[0])
    behind = np.where(seg == 0, np.maximum(-((q0 - Pr[0]) @ t0a), 0.0), 0.0)
    rk = np.maximum(bd / np.maximum(1.01 * r * section_k(alpha), 1e-6), 1.0)
    Rq = np.interp(s, st, R)
    q = np.column_stack([np.interp(s, st, U) - behind * Rq / np.maximum(r, 1e-6), Rq * rk * np.cos(alpha),
                         Rq * rk * np.sin(alpha)])
    w = ((1.0 - _smooth(r, 1.6 * r, bd)) * (1.0 - _smooth(0.0, 0.010, behind))
         * _smooth(0.004, 0.012, (np.pi / 8.0 - best) * np.hypot(p[:, 0], p[:, 2])))
    draw = np.ones(len(p))
    if len(p):
        out = wp.zeros(len(p), dtype=float)
        wp.launch(k_arm_draw, dim=len(p), inputs=[wp.array(q.astype(np.float32), dtype=wp.vec3), float(PATCH['arm']),
                                                   float(PATCH['disorder']), int(PATCH['seed_arm']), out])
        draw = out.numpy().astype(np.float64)
    return dict(arm=jb, behind=behind, bd=bd, r=r, alpha=alpha, q=q, w=w, is_arm=(w > 0.0) & (w > draw))


def sample_cage(cage, n, rng, weight_fn):
    """n random points on the cage, area-weighted and filtered by weight_fn(region onehot, st) in 0..1; the points,
    cage normals, region one-hots"""
    F = cage.tris()
    V = cage.V
    a = 0.5 * np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), axis=1)
    part = cage.attrs['part']
    fp = part[F].mean(1)
    w = a * weight_fn(fp, cage.attrs['st'][F].mean(1))
    fi = rng.choice(len(F), size=n, p=w / w.sum())
    r1, r2 = rng.random(n), rng.random(n)
    sq = np.sqrt(r1)
    b0, b1, b2 = 1 - sq, sq * (1 - r2), sq * r2
    P = V[F[fi, 0]] * b0[:, None] + V[F[fi, 1]] * b1[:, None] + V[F[fi, 2]] * b2[:, None]
    fn = np.cross(V[F[fi, 1]] - V[F[fi, 0]], V[F[fi, 2]] - V[F[fi, 0]])
    fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-20)
    return P, fn, fp[fi]


# ------------------------------------------------------------------------------------------- suckers
def sucker_layout(prog, arm, spec, rng):
    """the reference arm's suckers: (point on the base skin, its normal, diameter, s). Sizes by the arm's share s
    (octopus.sucker_size: the block-out owns them, its arms stand on their rims), spaced along the arm's OWN length
    (octopus.arm_length) at 1.15 d while single, then two
    staggered rows 0.52 d a step (photo 14: ~1.0-1.05 d within a row), d taken half a step ahead so a row keeps 1.04 d
    where the sizes change fastest (at the sucker's own d the rising rows closed to 1.02 d of the pair). The rims'
    clearance is asserted where the rows split and where the oral disc's row meets the arm's (r4: fused pairs there)"""
    az = np.arctan2(arm[0][0, 0], arm[0][0, 2])
    L = arm_length(spec, az)
    size = lambda s_: sucker_size(s_, spec)
    out = []
    s = 0.030
    k = 0
    row = 0
    while s < 0.985:
        d = size(s)
        if k < 3:
            out.append((s, d, 0))                 # the first three: single, on the oral midline
            step = 1.15
        else:
            out.append((s, d, 1 if row else -1))
            step = 0.52                           # two staggered rows: each row's pitch 1.04 d
            row ^= 1
        s += size(s + 0.5 * step * d / L) * step / L
        k += 1
    S = np.array(out)
    s_arr, d_arr, side = S[:, 0], S[:, 1], S[:, 2]
    # the rows' angle off the oral midline (alpha = pi), set so neighbours in a row sit ~1.1 d apart across the arm
    r = arm_radius(s_arr, spec)
    half = np.clip(0.62 * d_arr / r, np.radians(9.0), np.radians(34.0))
    alpha = np.pi + side * half
    p, nrm, st = arm_surface(prog, arm, s_arr, alpha, spec)
    ok = st == 0
    d_arr = d_arr[ok] * (1.0 + rng.normal(0.0, 0.05, ok.sum()))
    p, nrm, s_arr = p[ok], nrm[ok], s_arr[ok]
    if ok[:5].all():
        # where the single row splits in two: the third single sucker and the first of each row
        gap = rim_gaps(p, nrm, d_arr, [(2, 3), (2, 4), (3, 4)])
        assert gap.min() > 0.0, f'sucker rims fuse where the rows split: clearance {np.round(gap * 1000, 2)} mm'
    # the PROXIMAL suckers: the row carried in from the arm across the oral disc to the lip, uniserial and shrinking,
    # so the eight rows converge on the mouth as in the live animal (the underside reference: suckers crowd right up to
    # the mouth; t14: the rows stopped ~45 mm out and left a bare disc). s = -1 marks them
    mo = getattr(prog, 'mouth', None)
    if mo is not None and len(p):
        u = np.array([np.sin(az), 0.0, np.cos(az)])
        on_disc = lambda rr: settle(prog, mo['c'][None] + np.atleast_1d(rr)[:, None] * u[None] - mo['up'][None] * 0.004)
        r_end = float(np.linalg.norm(p[0, [0, 2]]))
        r_start = 1.45 * (mo['R'] + mo['r'])
        d_end = float(d_arr[0])
        rho, dia = [], []
        r_ = r_end
        while True:
            f = np.clip((r_ - r_start) / max(r_end - r_start, 1e-6), 0.0, 1.0)
            # 0.29 lip radii across at r_start (ORAL_REFERENCE §6: 0.27-0.5 (R + r), 3.0-5.6 mm for this lip; the
            # first rows shrank to 1.6 mm, 2-3.5 x too small). Each takes the size at its outer neighbour: v4's
            # innermost, 19 mm out, is 4.8 mm, ref 01's medians against the whole disc to the outer lip (1.33 and 0.33
            # of its 14.4 mm, ORAL_REFERENCE R4.1 g, R4.3)
            dd = 0.0032 + max(d_end - 0.0032, 0.0) * f
            r_ -= 1.15 * dd
            if not rho:
                # the outermost: in along the disc until its rim clears the arm's first two by 0.12 d (the arm's first
                # sits on the tent's underside, facing down and in: 1.15 d along the disc fused their rims, -0.46 mm)
                for _ in range(40):
                    pc, nc = on_disc(r_)
                    if rim_gaps(np.vstack([pc, p[:2]]), np.vstack([nc, nrm[:2]]), np.array([dd, d_arr[0], d_arr[1]]),
                                [(0, 1), (0, 2)]).min() > 0.12 * dd:
                        break
                    r_ -= 0.1 * dd
            if r_ < r_start:
                break
            rho.append(r_)
            dia.append(dd)
        if rho:
            pp, nn = on_disc(np.array(rho))
            dia = np.array(dia) * (1.0 + rng.normal(0.0, 0.05, len(dia)))
            # where the disc's row meets the arm's: its outermost sucker and the arm's first two
            P2, N2, D2 = np.vstack([pp[:1], p[:2]]), np.vstack([nn[:1], nrm[:2]]), np.concatenate([dia[:1], d_arr[:2]])
            gap = rim_gaps(P2, N2, D2, [(0, 1), (0, 2)])
            assert gap.min() > 0.0, f'sucker rims fuse where the oral row meets the arm\'s: {np.round(gap * 1e3, 2)} mm'
            p = np.vstack([pp[::-1], p])
            nrm = np.vstack([nn[::-1], nrm])
            d_arr = np.concatenate([dia[::-1], d_arr])
            s_arr = np.concatenate([np.full(len(dia), -1.0), s_arr])
    return p, nrm, d_arr, s_arr


def rim_circle(p, n, d):
    """the sucker rim's torus (sucker_strokes: the infundibulum's raised margin): its centre, axis, major radius and
    tube radius"""
    R = 0.5 * d
    return p + n * (0.36 * d - 0.10 * R)[:, None], n, 0.80 * R, 0.19 * R


def rim_gaps(p, n, d, pairs, m=72):
    """per pair (i, j) of suckers, the clearance between their rims: the closest approach of the two tori's tubes (each
    major circle at m points; < 0: the rims fuse)"""
    c, ax, Rm, rt = rim_circle(np.asarray(p, np.float64), np.asarray(n, np.float64), np.asarray(d, np.float64))
    t = np.linspace(0.0, 2.0 * np.pi, m, endpoint=False)

    def ring(i):
        e1 = np.cross(ax[i], [0.3, 1.0, 0.2])
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(ax[i], e1)
        return c[i] + Rm[i] * (np.cos(t)[:, None] * e1 + np.sin(t)[:, None] * e2)
    return np.array([np.linalg.norm(ring(i)[:, None] - ring(j)[None], axis=2).min() - rt[i] - rt[j]
                     for i, j in np.asarray(pairs, np.int64).reshape(-1, 2)])


# the suckers' size classes (diameter edges, m): each class its own batches (sucker_strokes)
SUCKER_CLASSES = (0.0024, 0.006, 0.011)


def sucker_strokes(plan, p, n, d):
    """the sucker anatomy as strokes, SESSILE (live photos 14, 15: a low cup on a broad base, no neck; the literature:
    "embedded without stalks", a short muscular base under a continuation of the dermis; r4's narrow stalk stood each
    cup on a neck): a base cone flaring into the arm, the cup up to the disc (0.36 d over the skin), the rim, the dish
    and the orifice chamber; below 2.4 mm only the base, the cup and a simple dimple (finer parts are sub-voxel).
    Every kind of stroke goes in one batch per size class (SUCKER_CLASSES), so each batch's one fillet (its median)
    stays near its suckers' own scale: one median over 2.4-17.8 mm suckers filleted the largest at a third of theirs,
    and each of them showed a flat facet on its wall toward the other row (the probe's close views); kind by kind, so
    every add comes before the carves"""
    R = 0.5 * d
    hs = 0.36 * d                                       # the disc's top above the skin
    cls = np.searchsorted(SUCKER_CLASSES, d, side='right')
    mm_ = [0.0] + [e * 1000.0 for e in SUCKER_CLASSES]
    groups = [(m_, c == 0, f' {mm_[c]:g}-{mm_[c + 1]:g} mm' if c < len(SUCKER_CLASSES) else f' {mm_[c]:g}+ mm')
              for c in range(len(SUCKER_CLASSES) + 1) for m_ in [cls == c] if m_.any()]
    big = [(m_, tag) for m_, small, tag in groups if not small]
    for m_, small, tag in groups:
        # the base: a broad cone from inside the skin, 1.05 R there, to 0.95 R at 0.20 d out, filleted into the arm
        pm, nm, Rm, dm = p[m_], n[m_], R[m_], d[m_]
        plan.add(STROKE_CONE, pm - nm * (0.10 * dm)[:, None], pm + nm * (0.20 * dm)[:, None], 1.05 * Rm, 0.95 * Rm,
                 'add', float(np.median(0.25 * Rm)), 'sucker base' + tag)
    for m_, small, tag in groups:
        # the cup's wall up to the disc
        pm, nm, Rm, dm, hm = p[m_], n[m_], R[m_], d[m_], hs[m_]
        plan.add(STROKE_CONE, pm + nm * (0.16 * dm)[:, None], pm + nm * (hm - 0.22 * Rm)[:, None], 0.95 * Rm,
                 0.92 * Rm, 'add', float(np.median(0.16 * Rm)), 'sucker cup' + tag)
    for m_, tag in big:
        # the rim: a soft torus round the disc's edge (the infundibulum's raised margin)
        rim_c, _, rim_R, rim_r = rim_circle(p[m_], n[m_], d[m_])
        plan.add(STROKE_TORUS, rim_c, rim_c + n[m_] * 0.001, rim_R, rim_r, 'add', float(np.median(0.14 * R[m_])),
                 'sucker rim' + tag)
    for m_, tag in big:
        # the dish: a ball over the disc leaving a broad funnel from the rim to the orifice (0.2 R deep)
        dc = p[m_] + n[m_] * (hs[m_] + 1.40 * R[m_])[:, None]
        plan.add(STROKE_CONE, dc, dc, 1.60 * R[m_], 1.60 * R[m_], 'carve', float(np.median(0.08 * R[m_])),
                 'sucker dish' + tag)
    for m_, tag in big:
        # the orifice (~0.18 d: live photos 14, 15 show 0.15-0.2 d) and the acetabulum chamber under it, centred 0.34 R
        # under the dish's floor (0.52 R over the skin), which it opens 0.12 R round the axis, about 0.17 R with its
        # fillet (0.42 R under the disc's top it opened 0.28-0.30 d, 0.52 R under it 0.20-0.25 d: the probe's profiles)
        ch = p[m_] + n[m_] * (hs[m_] - 0.54 * R[m_])[:, None]
        plan.add(STROKE_CONE, ch, ch, 0.36 * R[m_], 0.36 * R[m_], 'carve', float(np.median(0.06 * R[m_])),
                 'sucker chamber' + tag)
    for m_, tag in big:
        # the roof protuberance, showing through the orifice
        pr = p[m_] + n[m_] * (hs[m_] - 0.78 * R[m_])[:, None]
        plan.add(STROKE_CONE, pr, pr, 0.20 * R[m_], 0.20 * R[m_], 'add', float(np.median(0.06 * R[m_])),
                 'sucker roof' + tag)
    for m_, small, tag in groups:
        if small:
            # small suckers: a simple dimple in the cup
            cc = p[m_] + n[m_] * (hs[m_] + 0.25 * R[m_])[:, None]
            plan.add(STROKE_CONE, cc, cc, 0.55 * R[m_], 0.55 * R[m_], 'carve', float(np.median(0.08 * R[m_])),
                     'sucker dimple' + tag)


# ------------------------------------------------------------------------------------------- papillae
def papilla_strokes(plan, p, n, rb, h, tag, tip=0.40, k_frac=1.0):
    """conical papillae: a round cone from inside the skin to its tip, filleted into the skin by at least its base
    radius (the sculpt brief: small details blend into the forms, never read as cuts; t10: a 0.28 tip read as
    thorns on the arms' silhouettes; papillae are soft low cones)"""
    if not len(p):
        return
    plan.add(STROKE_CONE, p - n * (0.45 * rb)[:, None], p + n * h[:, None], rb, tip * rb, 'add',
             float(np.median(k_frac * rb)), tag)


def head_sites(prog, cage, arms, spec, rng, n_samples=400_000):
    """the head set's patch sites on the base surface (the body, the crown's webs and oral face, NOT the arm tubes):
    (site point, normal, region one-hot of the nearest sample, patch random), and the sites behind the arms' first
    nodes that the tubes' territory took and no arm plants (arm_owner past_first): (point, normal, region one-hot)"""
    S = PATCH['head']

    def head(fp, fst):
        return fp[:, 0] + fp[:, 1] + fp[:, 2]
    P, N, fp = sample_cage(cage, n_samples, rng, head)
    p, st = prog.project(P + N * 0.006, N, maxd=0.02)
    ok = st == 0
    p, fp = p[ok], fp[ok]
    cell, site, edge = proc.cells(p, S, PATCH['disorder'], PATCH['seed_head'])
    key, first = np.unique(cell, axis=0, return_index=True)
    cand = site[first]
    reg = fp[first]
    q, nq = settle(prog, cand)
    # a site belongs to the surface patch it lands in (its own cell) and must not be an arm tube's
    c2, _, _ = proc.cells(q, S, PATCH['disorder'], PATCH['seed_head'])
    own = np.all(c2 == key, axis=1)
    keep = own & ~arm_owner(q, arms, spec)
    rnd = rng.random(keep.sum())
    # (crown strip) the sites the first nodes' balls took behind the nodes: plan_octopus's strip pass plants them on
    # draws of its own, so these and every later draw stay the live plan's
    strip = own & ~keep & ~arm_owner(q, arms, spec, past_first=True)
    return q[keep], nq[keep], reg[keep], rnd, (q[strip], nq[strip], reg[strip])


def arm_sites(prog, arm, spec, tables, rng):
    """the reference arm's patch sites (aboral and lateral skin) in its straightened coordinate"""
    S = PATCH['arm']
    st_, U, R = tables
    # sample the coordinate densely: s by its U spacing, alpha around
    u = np.arange(0.0, U[-1], S * 0.35)
    s = arm_s_of_u(u, tables)
    al = np.linspace(-np.pi, np.pi, 160, endpoint=False)
    ss, aa = np.meshgrid(s, al, indexing='ij')
    q = arm_coord(ss.ravel(), aa.ravel(), tables)
    cell, site, edge = proc.cells(q, S, PATCH['disorder'], PATCH['seed_arm'])
    key, first = np.unique(cell, axis=0, return_index=True)
    cs = site[first]
    s_c = arm_s_of_u(cs[:, 0], tables)
    a_c = np.arctan2(cs[:, 2], cs[:, 1])
    # the site's own surface point (radially onto the tube) must lie in its own patch
    q2 = arm_coord(s_c, a_c, tables)
    c2, _, _ = proc.cells(q2, S, PATCH['disorder'], PATCH['seed_arm'])
    keep = np.all(c2 == key, axis=1) & (s_c > 0.0) & (s_c < 0.97)
    s_c, a_c = s_c[keep], a_c[keep]
    p, nrm, stt = arm_surface(prog, arm, s_c, a_c, spec)
    ok = stt == 0
    return p[ok], nrm[ok], s_c[ok], a_c[ok], rng.random(ok.sum())


def root_sites(prog, arms, order, spec, tables, rots, back=0.0105):
    """the ARM network's patch sites BEHIND each arm's first node: crown v5d's skin continues the arm coordinate there
    (q = (-behind, R k cos alpha, R k sin alpha), k = rad_k) and paints it, fading out over 10 mm, so its patches there
    carry the arm's papillae as on the tube (arm_sites plants s > 0 only). (polish 1) The strip's skin sampled densely:
    rays off the reference arm's backward axis (behind the node, round it), each sent along its radius onto EACH arm's
    own skin (the crown behind the first nodes differs from arm to arm: no replication); there the skin's own coordinate
    and network (skin_net). Each cell of the arm network it paints takes one site where the cell's site, sent onto the
    sampled skin (its nearest sample in the coordinate), lands in its own patch and on the arm network (head_sites'
    rule, and the old one's: sites on the coordinate's cylinder sent radially, which held only inside the old 1.15 r
    plateau; with the circle scaled from the section's radius, as skin_at now continues it, half of them failed their
    cell, 184 -> 87). Returns (points, normals, alpha, arm column)"""
    from scipy.spatial import cKDTree
    S = PATCH['arm']
    R0 = float(tables[2][0])
    x = np.arange(-back, 0.0, S * 0.12)
    al = np.linspace(-np.pi, np.pi, 480, endpoint=False)
    xx, aa = np.meshgrid(x, al, indexing='ij')
    xx, aa = xx.ravel(), aa.ravel()
    Pr, Nr, Br = arms[order[0]][0], arms[order[0]][1], arms[order[0]][2]
    t0 = (Pr[1] - Pr[0]) / np.linalg.norm(Pr[1] - Pr[0])
    c = Pr[0][None] + xx[:, None] * t0[None]
    d = np.cos(aa)[:, None] * Nr[0][None] + np.sin(aa)[:, None] * Br[0][None]
    out = []
    for j, Rm in enumerate(rots):
        p, stt = prog.project((c + d * (R0 + 0.012)) @ Rm.T, d @ Rm.T, maxd=0.05)
        p = p[stt == 0]
        if not len(p):
            continue
        net = skin_net(p, arms, order, spec, tables)
        m = (net['arm'] == order[j]) & (net['behind'] > 0.0)
        if not (m & net['is_arm']).any():
            continue
        p, q, a_, isa = p[m], net['q'][m], net['alpha'][m], net['is_arm'][m]
        cell, site, _ = proc.cells(q, S, PATCH['disorder'], PATCH['seed_arm'])
        key, first = np.unique(cell[isa], axis=0, return_index=True)    # the painted arm network's cells
        _, k = cKDTree(q).query(site[np.nonzero(isa)[0][first]])
        sel = k[np.all(cell[k] == key, axis=1) & isa[k]]
        if len(sel):
            out.append((p[sel], prog.normals(p[sel]), a_[sel], np.full(len(sel), j)))
    if not out:
        return np.zeros((0, 3)), np.zeros((0, 3)), np.zeros(0), np.zeros(0, np.int64)
    return tuple(np.concatenate(z) for z in zip(*out))


def band_sites(prog, cage, arms, order, spec, tables, rots, owned, rng, band=1.15, ds=0.0005, n_alpha=360,
               n_cage=1_500_000):
    """(crown v6b) the ARM network's patch sites in the BAND off each arm's tube past its first node: within `band`
    local radii of its centreline head_sites take none (arm_owner: the arms' territory), and arm_sites plant the arm
    coordinate's CYLINDER (one site per cell, sent radially onto the tube), while the skin paints the arm network on
    across the band (skin_net: the coordinate continued off the tube from the section's radius, the network's weight
    falling from r to 1.6 r): where the webs' walls meet the arms' flanks at s 0.21-0.28, 1.0-1.15 r off the axis,
    the polish's streak audit found 11 plan holes (22.6 cm2, 3-6 papillae per cm2 against 15-22 round them). Each
    arm's own skin there (the webs differ by sector: no replication) sampled densely: rays off the reference arm's
    tube every `ds` of s out to the head set's end (the tube's first ring, web_plan's sw) and n_alpha round, each sent
    along its radius onto that arm (rots), and the crown's two layers sampled by area on the cage (n_cage points on
    draws of rng, the planter's own stream, projected along the cage's normal as head_sites does: the webs' strips
    beside the arms, which the radial rays cross nearly edge-on); every arm-network cell it paints that no reference
    site owns (owned: the keys of arm_sites' cells) takes one site where the cell's site, sent onto the sampled skin
    (its nearest sample in the coordinate), lands in its own patch, on the arm network and in the band (root_sites'
    rule). Returns (points, normals, alpha, s, arm column)"""
    from scipy.spatial import cKDTree
    from .octopus import web_plan
    S = PATCH['arm']
    sw = float(np.max(web_plan(spec, arms)['sw']))
    ref = arms[order[0]]
    s_ = np.arange(ds, sw + 2.0 * ds, ds)
    al = np.linspace(-np.pi, np.pi, n_alpha, endpoint=False)
    ss, aa = np.meshgrid(s_, al, indexing='ij')
    ss, aa = ss.ravel(), aa.ravel()
    c, n_, b_ = arm_frame(ref, ss)
    d = np.cos(aa)[:, None] * n_ + np.sin(aa)[:, None] * b_
    x0 = c + d * (arm_radius(ss, spec) + 0.012)[:, None]
    Pc, Nc, _ = sample_cage(cage, n_cage, rng, lambda fp, fst: fp[:, 1] + fp[:, 2])
    pc, stc = prog.project(Pc + Nc * 0.006, Nc, maxd=0.02)
    pc = pc[stc == 0]
    net_c = skin_net(pc, arms, order, spec, tables)
    out = []
    for j, Rm in enumerate(rots):
        p, stt = prog.project(x0 @ Rm.T, d @ Rm.T, maxd=0.05)
        p = p[stt == 0]
        net = skin_net(p, arms, order, spec, tables)
        mc = net_c['arm'] == order[j]
        p = np.concatenate([p, pc[mc]])
        net = {k_: np.concatenate([net[k_], net_c[k_][mc]]) for k_ in ('arm', 'behind', 'bd', 'r', 'alpha', 'q',
                                                                       'is_arm')}
        m = (net['arm'] == order[j]) & (net['behind'] <= 0.0) & (net['bd'] < band * net['r'])
        if not (m & net['is_arm']).any():
            continue
        p, q, a_, isa = p[m], net['q'][m], net['alpha'][m], net['is_arm'][m]
        cell, site, _ = proc.cells(q, S, PATCH['disorder'], PATCH['seed_arm'])
        key, first = np.unique(cell[isa], axis=0, return_index=True)       # the painted arm network's cells
        free = np.array([tuple(k_) not in owned for k_ in key], bool)
        if not free.any():
            continue
        key, first = key[free], first[free]
        _, k = cKDTree(q).query(site[np.nonzero(isa)[0][first]])
        sel = k[np.all(cell[k] == key, axis=1) & isa[k]]
        if len(sel):
            out.append((p[sel], prog.normals(p[sel]), a_[sel], arm_s_of_u(q[sel, 0], tables),
                        np.full(len(sel), j)))
    if not out:
        return np.zeros((0, 3)), np.zeros((0, 3)), np.zeros(0), np.zeros(0), np.zeros(0, np.int64)
    return tuple(np.concatenate(z) for z in zip(*out))


def seg_dist(q, a, b):
    """the distance from points q (n, 3) to the segment a-b (a point when a == b)"""
    ab = b - a
    L2 = float(ab @ ab)
    t = np.clip((q - a) @ ab / L2, 0.0, 1.0) if L2 > 0.0 else np.zeros(len(q))
    return np.linalg.norm(q - (a[None] + t[:, None] * ab[None]), axis=1)


def eye_lid(spec, side, slope=28.0, n=64):
    """an eye's LID (v4: the 30 mm eyeball's front at its turret's skin, eye_geom): the eye's frame (E, Re, out, h, u),
    the aperture's half-angles fore-aft and up-down (spec['eye_ap']: the cage's eye port opens the same) and the LID
    BOWL the socket carve takes out of the turret: a ball on the eye's axis in front of the eyeball (a capsule along the
    aperture's long axis when it is oval) whose surface meets the eyeball on the aperture's edge and rises from it at
    `slope` degrees off the eye's plane, so the turret's skin runs down onto the eyeball all round. Measured on the v4
    block-out (patches/v4_sculpt/measure_blockout.py): 50 deg off the eye's axis the turret's skin stands 1.4 mm off the
    eyeball dorsally, 2.3 forward, 3.7 behind and 7.7 ventrally, where the head mass's blend bulges under the eye; a
    50 deg cone straight through it (r4's aperture) left the eyeball at the bottom of a pit, its ventral wall a 7 mm
    cliff. 28 deg is the cage's lid band below the eye as it first stood (its fixed lid edge to the fold on the cheek);
    the refit port's band there tilts 22 deg the same way, and its fitted low round the eye lies within 2.6 mm of the
    carved high along its normals, every vertex found as the bake searches (patches/v4_sculpt/check/check_cage.py). (The
    elliptic cone it replaces is not round either: its angular metric pulls the diagonals in, a round 50 deg aperture
    cut to 45 there, where the port's ring is round.) Returns dict(E, Re, out, h, u; A, B, rho: the bowl, a stroke A-B
    of radius rho; edge (n, 3) the lid's edge on the eyeball, edge_dir (n, 3) its azimuths round the axis (from u
    toward h), edge_th (n,) its angles off the axis; R_ap the aperture's radius off the axis at its short half-angle)"""
    from .octopus_eye import eye_axes
    E, Re, out, h, u = eye_axes(spec, side)
    a_h, a_v = np.radians(spec['eye_ap'][0]), np.radians(spec['eye_ap'][1])
    a_s, a_l, e_l = (a_v, a_h, h) if a_v <= a_h else (a_h, a_v, u)
    re = 1.003 * Re                                  # the bowl's surface a hair off the eyeball: no turret film on it
    sl = np.radians(slope)
    # the short axis sets the ball: through its edge point, its surface there at the slope
    zs, xs = re * np.cos(a_s), re * np.sin(a_s)
    rho = xs / np.sin(sl)
    zc = zs + xs / np.tan(sl)
    # the long axis: the capsule's half-length, so its end ball passes through that edge point
    zl, xl = re * np.cos(a_l), re * np.sin(a_l)
    w = max(xl - np.sqrt(max(rho * rho - (zc - zl) ** 2, 0.0)), 0.0)
    C = E + out * zc
    A, B = C - e_l * w, C + e_l * w
    # the lid's edge: per azimuth, the angle off the axis where the eyeball leaves the bowl (bisection)
    az = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
    dirs = np.cos(az)[:, None] * u[None] + np.sin(az)[:, None] * h[None]
    lo, hi = np.zeros(n), np.full(n, 0.5 * np.pi)
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        inside = seg_dist(E + re * (np.cos(mid)[:, None] * out + np.sin(mid)[:, None] * dirs), A, B) < rho
        lo, hi = np.where(inside, mid, lo), np.where(inside, hi, mid)
    th = 0.5 * (lo + hi)
    return dict(E=E, Re=Re, out=out, h=h, u=u, A=A, B=B, rho=rho, edge_dir=dirs, edge_th=th,
                edge=E + Re * (np.cos(th)[:, None] * out + np.sin(th)[:, None] * dirs), R_ap=Re * np.sin(a_s))


def eye_clear(q, spec, side, lid=None):
    """0..1 per point by an eye: 0 on its lid ring and inside its lid bowl (and 1 mm round it), easing to 1 by 1.9
    aperture radii off the eye's AXIS (the v4 eyeball sits 7.9 mm out of its turret's centre: within 1.4 eyeball radii
    of it, r4's ramp, lay the whole turret); 1 more than an eyeball radius back along the axis, where the axis distance
    no longer measures this eye"""
    L_ = eye_lid(spec, side) if lid is None else lid
    v = q - L_['E'][None]
    along = v @ L_['out']
    lat = np.linalg.norm(v - along[:, None] * L_['out'][None], axis=1)
    x = np.clip((lat / L_['R_ap'] - 1.25) / 0.65, 0.0, 1.0)
    x = np.where(along < -L_['Re'], 1.0, x * x * (3.0 - 2.0 * x))
    return np.where(seg_dist(q, L_['A'], L_['B']) < L_['rho'] + 0.001, 0.0, x)


def eye_socket(plan, spec, roll=0.0008):
    """per eye: the socket the eyeball sits in (0.3 mm all round), the LID BOWL through the turret in front of it
    (eye_lid: the aperture and the lid's slope in one round carve), the lid's free margin as a soft roll lying on the
    eyeball round the aperture (live eyes: the lid ring closes onto the iris, flush with it or over its edge; refs 04,
    08), then the eyeball itself as an OCCLUDER so the lids bake their true contact AO (its own mesh, octopus_eye,
    carries its surface). Both eyes go in each batch"""
    lids = [eye_lid(spec, side) for side in (+1, -1)]
    E = np.array([l_['E'] for l_ in lids])
    Re = np.array([l_['Re'] for l_ in lids])
    plan.add(STROKE_CONE, E, E, 1.02 * Re, 1.02 * Re, 'carve', 0.0006, 'eye socket')
    rho = [l_['rho'] for l_ in lids]
    plan.add(STROKE_CONE, [l_['A'] for l_ in lids], [l_['B'] for l_ in lids], rho, rho, 'carve', 0.0015,
             'eye lid bowl')
    # the margin: a chain round the edge on the eyeball, a third of its girth over the iris's edge, filleted into the
    # bowl's slope (0.8 mm: ~5 voxels across at the bake's 0.3 mm)
    A_ = []
    for l_ in lids:
        th = l_['edge_th'] + 0.7 * roll / l_['Re']
        A_.append(l_['E'] + (l_['Re'] + 0.3 * roll) * (np.cos(th)[:, None] * l_['out']
                                                         + np.sin(th)[:, None] * l_['edge_dir']))
    plan.add(STROKE_CONE, np.concatenate(A_), np.concatenate([np.roll(a_, -1, axis=0) for a_ in A_]), roll, roll,
             'add', 0.0006, 'eye lid margin')
    plan.add(STROKE_CONE, E, E, 0.995 * Re, 0.995 * Re, 'add', 0.0, 'eyeball occluder')


def funnel_lumen(plan, spec, prog=None, log=print, port=None):
    """the funnel's open END, matched to the cage's port (octopus.build_cage: the rim ring 3.0 mm past the tip point fb
    at 0.98 of the tip's radius, the lip 1.8 mm past it at (funnel_lumen + 0.02), the lumen ring 6.0 mm in at
    (funnel_lumen - 0.08), a flat cap there), so the bake finds every ring's surface within its reach. The block-out
    ends in the round cone's hemisphere, 9.5 mm past fb: the port's lip sat 6.3 mm inside it, past the bake's 6 mm (t14:
    the cap and walls missed and shipped flat grey), and r4's channel (a cone from 3 mm past fb to 12 mm in) no longer
    broke through it at funnel_lumen 0.50: an enclosed void. So: the end CUT square at the rim's plane, its edge rounded
    by the fillet (live photo 04: a blunt tube end round a round opening), then the CHANNEL, a cylinder of
    (funnel_lumen - 0.03) of the tip's radius (between the port's lip and lumen rings) to a floor 1.5 mm past the
    port's cap. With prog, nothing is carved where the funnel's tip is not the block-out's surface (v4 at 10-21: the
    body sweep and the head mass cover the whole funnel, 12-68 mm over its skin), so no hidden void is left; and
    nothing without the cage's PORT (port False: build_cage's info['funnel_rings'] empty; None: not known, a stand-in
    cage): the cage asks more than the tip, every surface line round the cone leaving the body sweep, and without a
    port its low runs closed over the funnel, where an open end in the high bakes as a hole the low cannot show"""
    fa, fb, fra, frb = funnel_geom(spec)
    ax = (fb - fa) / np.linalg.norm(fb - fa)
    fl = spec.get('funnel_lumen', 0.72)             # the cage's lip and lumen rings use the same share
    if prog is not None:
        # 1.5 mm off the tip's skin, 8 points round it: outside the block-out where the tip is its surface
        e1 = np.cross(ax, [0.0, 1.0, 0.0])
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(ax, e1)
        t = np.linspace(0.0, 2.0 * np.pi, 8, endpoint=False)
        f = prog.eval(fb + (frb + 0.0015) * (np.cos(t)[:, None] * e1 + np.sin(t)[:, None] * e2))
        if np.median(f) < 0.0:
            log(f'[plan] funnel end and lumen NOT carved: the funnel\'s tip lies inside the block-out (the field '
                f'1.5 mm off its skin {np.median(f) * 1000:+.1f} mm)'
                + ('; ⚠ yet the cage cut a port there: its lumen rings will find no surface' if port else ''))
            return
    if port is False:
        log('[plan] funnel end and lumen NOT carved: the cage cut no funnel port (its low runs closed over the funnel)')
        return
    # the end: a square cut at the rim's plane, a little wider than the tip, past its hemisphere
    plan.add(STROKE_CYL, (fb + ax * 0.0030)[None], (fb + ax * (0.0030 + frb))[None], 1.10 * frb, 0.0005, 'carve',
             0.0015, 'funnel end')
    # the channel, from past the cut to its floor
    plan.add(STROKE_CYL, (fb + ax * 0.0040)[None], (fb - ax * 0.0075)[None], (fl - 0.03) * frb, 0.0015, 'carve',
             0.0010, 'funnel lumen')


def eye_papillae(plan, prog, spec, rng):
    """per eye: two supraocular papillae, primary papillae round the rim, three ventral eye papillae, each at its
    distance off the eye's axis in aperture radii (the horns 1.45, on the turret's face over the eye: photo 09's erect
    ones stand 1.7-2.0 over the eye's centre by eye, near the turret's top at 1.84), on the TURRET (along a ray from the
    mound's centre, which the eye's axis runs through: eye_geom) and clear of the lid bowl by its own base radius and
    0.5 mm (the bowl lowers the skin up to 5.8 mm under the eye and 5.5 in front of it: a papilla planned on the
    block-out there would float)"""
    Y = np.array([0.0, 1.0, 0.0])
    gam = np.radians(np.arange(8.0, 89.0, 1.0))
    for side in (+1, -1):
        c, out, E, Re = eye_geom(spec, side)
        L_ = eye_lid(spec, side)
        up = Y - out * (Y @ out)
        up /= np.linalg.norm(up)
        rt = np.cross(out, up)

        def on_turret(ang, lat, rb):
            """per azimuth ang round the eye's axis (0 up, 90 toward rt): the turret's point lat aperture radii off the
            axis, or the nearest one clear of the bowl by rb + 0.5 mm; the first exit out of the solid along the ray
            from the mound's centre (12 mm in, inside every turret radius), and the normals there"""
            ang = np.atleast_1d(ang)
            d = up[None] * np.cos(ang)[:, None] + rt[None] * np.sin(ang)[:, None]
            ray = (np.cos(gam)[None, :, None] * out[None, None]
                   + np.sin(gam)[None, :, None] * d[:, None]).reshape(-1, 3)
            pt, st = prog.project(c[None] + ray * 0.012, ray, maxd=0.07)
            v = pt - c[None]
            al = v @ out
            la = np.linalg.norm(v - al[:, None] * out[None], axis=1).reshape(len(ang), -1)
            clear = seg_dist(pt, L_['A'], L_['B']).reshape(len(ang), -1) - L_['rho']
            bad = (st.reshape(len(ang), -1) != 0) | (clear < np.atleast_1d(rb)[:, None] + 0.0005)
            k = np.argmin(np.abs(la / L_['R_ap'] - lat) + 1.0e3 * bad, axis=1)
            assert not bad[np.arange(len(ang)), k].any(), 'an eye papilla found no turret skin clear of the lid bowl'
            p = pt.reshape(len(ang), -1, 3)[np.arange(len(ang)), k]
            return p, prog.normals(p)
        # supraocular: two cones over the eye, a little apart; broad and LOW (t11: a 4.2 mm cone over the smooth low
        # projected into a pale smear: tall features belong to geometry or stay low)
        for a, rb, h in ((-0.35, 0.0026, 0.0020), (0.30, 0.0020, 0.0015)):
            p, nn = on_turret(a, 1.45, rb)
            # along the surface's own normal (t14: tilted, the bake's rays fanned onto one flank: a pale starburst)
            plan.add(STROKE_CONE, p - nn * (0.5 * rb), p + nn * h, rb, 0.35 * rb, 'add', rb,
                     'supraocular papilla')
        # primary papillae round the rim (not over the supraocular ones)
        ang = np.radians(np.array([60, 100, 140, 180, 215, 250, 290]) + rng.normal(0, 6, 7))
        rb = 0.0008 + 0.0004 * rng.random(len(ang))
        p, nn = on_turret(ang, 1.30, rb)
        papilla_strokes(plan, p, nn, rb, rb * (1.1 + 0.4 * rng.random(len(p))), 'eye-rim papilla')
        # the three ventral eye papillae, below the rim's
        ang = np.radians(np.array([150.0, 180.0, 210.0]))
        rb = np.full(len(ang), 0.0011)
        p, nn = on_turret(ang, 1.75, rb)
        papilla_strokes(plan, p, nn, rb, rb * 1.3, 'ventral eye papilla')


def head_density(d0, q, spec, prog):
    """the head set's papilla density d0 per site, thinned out by the eyes, the funnel and the mouth's lip"""
    dens = d0
    # not on the eyes' lids or in their lid bowls (their own papillae follow): a ramp, not a cut, the papillae thinning
    # out toward the eye (t10: a hard circle at 1.55 eye radii read as a bald disc stamped round each eye)
    for side in (+1, -1):
        dens = dens * eye_clear(q, spec, side)
    # nor on the funnel (a siphon's skin is smooth: t10 had it warty) or the lip round the mouth (its folds follow)
    dens = dens * (1.0 - funnel_mask(q, spec))
    dens = dens * (np.linalg.norm(q - prog.mouth['c'], axis=1) > 1.45 * (prog.mouth['R'] + prog.mouth['r']))
    return dens


def head_features(plan, prog, q, nq, body, rng, avoid=None):
    """the head set's features on its planted sites q (body: each site's body share), their strokes added to the plan:
    WARTS, compound papillae (a main cone and 3-6 nodes round it, Allen 2014) on the mantle and head, and small
    PAPILLAE elsewhere (none within a wart's footprint; the webs' smaller). avoid = (warts' points, their base radii,
    every feature's points) already planned (the crown strip pass, beside the live plan's): no wart here within its
    footprint of one (the site keeps a papilla), no papilla here within a wart's footprint of theirs. Returns the
    warts' (p, n, rb) and the papillae's (p, n, rb)"""
    from scipy.spatial import cKDTree
    u = rng.random(len(q))
    wart = u < 0.035 * body
    qw, nw = q[wart], nq[wart]
    rbw = 0.0012 + 0.0010 * rng.random(len(qw))
    hw = rbw * (0.75 + 0.5 * rng.random(len(qw)))
    if avoid is not None and len(qw) and len(avoid[2]):
        clear = cKDTree(avoid[2]).query(qw)[0] > 2.2 * rbw
        wart[np.nonzero(wart)[0][~clear]] = False
        qw, nw, rbw, hw = qw[clear], nw[clear], rbw[clear], hw[clear]
    papilla_strokes(plan, qw, nw, rbw, hw, 'wart')
    nodes_p, nodes_r = [], []
    for i in range(len(qw)):
        k = rng.integers(3, 7)
        t1 = np.cross(nw[i], [0.3, 1.0, 0.2])
        t1 /= np.linalg.norm(t1)
        t2 = np.cross(nw[i], t1)
        ang = rng.random() * 2 * np.pi + np.arange(k) * 2 * np.pi / k + rng.normal(0, 0.25, k)
        d = t1[None] * np.cos(ang)[:, None] + t2[None] * np.sin(ang)[:, None]
        nodes_p.append(qw[i] + d * rbw[i] * 0.95 + nw[i] * rbw[i] * 0.35)
        nodes_r.append(np.full(k, rbw[i] * 0.36) * (0.8 + 0.4 * rng.random(k)))
    if nodes_p:
        npp, nnn = settle(prog, np.concatenate(nodes_p))
        nr = np.concatenate(nodes_r)
        papilla_strokes(plan, npp + nnn * (0.25 * nr)[:, None], nnn, nr, nr * 0.9, 'wart node')
    # small papillae elsewhere (none within a wart's footprint)
    keep = ~wart
    W, rW = (qw, rbw) if avoid is None else (np.vstack([qw, avoid[0]]), np.concatenate([rbw, avoid[1]]))
    if len(W):
        dd, _ = cKDTree(W).query(q)
        keep &= dd > 2.2 * rW.max()
    qs, ns_, bs = q[keep], nq[keep], body[keep]
    rbs = np.clip(np.exp(rng.normal(np.log(0.00050), 0.30, len(qs))), 0.00032, 0.0009)
    rbs = rbs * (0.75 + 0.25 * bs)                       # the webs' are smaller
    hs = rbs * (0.5 + 0.8 * rng.random(len(qs)))
    papilla_strokes(plan, qs, ns_, rbs, hs, 'papilla')
    return (qw, nw, rbw), (qs, ns_, rbs)


def plan_octopus(prog, cage, arms, info, spec, rng, log=print, sucker_geo=None):
    """sucker_geo: (d, s) -> the mask of the suckers that are GEOMETRY (species/octopus_suckers.py geo_mask): left out
    of the strokes (the skin under them stays the block-out's, their own mesh carries their relief) and marked in the
    instances (suckers_geo), where the bake's occluders and the material pass find them; None: every sucker sculpted"""
    plan = Plan()
    order = info['order']
    ref = arms[order[0]]
    rots = arm_rotations(order, spec)
    tables = arm_tables(spec, az=arm_azimuths()[order[0]])
    eye_socket(plan, spec)
    # --- the reference arm's features, then replicated onto all eight
    ref_plan = Plan()
    ps, ns, ds, ss = sucker_layout(prog, ref, spec, rng)
    geo = np.asarray(sucker_geo(ds, ss), bool) if sucker_geo else np.zeros(len(ds), bool)
    sucker_strokes(ref_plan, ps[~geo], ns[~geo], ds[~geo])
    pa, na_, sa, aa, ra = arm_sites(prog, ref, spec, tables, rng)
    # papillae: the aboral and lateral skin (cos alpha > -0.25), sparser toward the tip, about half the patches
    w = np.clip((np.cos(aa) + 0.25) / 0.6, 0.0, 1.0) * np.clip(1.0 - (sa - 0.45) / 0.5, 0.1, 1.0)
    on = ra < 0.55 * w
    scale = np.maximum(arm_radius(sa[on], spec) / spec['arm_r0'], 0.3)
    rba = np.clip(np.exp(rng.normal(np.log(0.00045), 0.28, on.sum())), 0.0003, 0.0008) * np.sqrt(scale)
    ha = rba * (0.35 + 0.55 * rng.random(on.sum()))
    replicate(ref_plan, rots, plan)
    # (polish 1) the papillae as the reference plan's last batch, as before, but each arm's copy SEATED on its own skin
    # (seat_papillae: rotated copies sat under the body's and the webs' blends or in the air beside an arm)
    A_p, B_p, ra_p, rb_p, seated, seat_n = seat_papillae(prog, pa[on], na_[on], rba, ha, rots)
    plan.add(STROKE_CONE, A_p, B_p, ra_p, rb_p, 'add', float(np.median(rba)), 'arm papilla')
    plan.inst['suckers'] = dict(p=ps, n=ns, d=ds, s=ss, geo=geo)
    plan.inst['arm_papillae'] = dict(p=pa[on], n=na_[on], rb=rba, s=sa[on], alpha=aa[on])
    plan.inst['arm_papillae_seated'] = seated
    # --- the head set's papillae and warts
    q, nq, reg, rnd, strip = head_sites(prog, cage, arms, spec, rng)
    dens = head_density(0.62 * reg[:, 0] + 0.38 * reg[:, 1] + 0.04 * reg[:, 2], q, spec, prog)
    on_h = rnd < dens
    (qw, nw, rbw), (qs, ns_, rbs) = head_features(plan, prog, q[on_h], nq[on_h], reg[on_h, 0], rng)
    # --- (crown strip, 10-27) the crown top BEHIND each arm's first node, which no arm plants and the head set left
    # bare (Skye's smooth strip round the head): planted as the skin paints it (skin_net, crown v5d), head papillae
    # where it paints the head network and the arm's papillae where it paints the arm's (root_sites); the crown top's
    # head sites there at every patch within 1.15 r of the node, easing to the live 0.38 by 1.6 r (the arms' reach;
    # the root tubes beside it carry ~18 arm papillae per cm2, the head network 14 sites). On draws of a child stream:
    # every draw of the live plan, above and below, stays as it was
    rng_s = rng.spawn(1)[0]
    lift = lambda n_, rg: np.where(n_['behind'] > 0.0, 1.0 - _smooth(1.15 * n_['r'], 1.6 * n_['r'], n_['bd']),
                                   0.0) * rg[:, 1]
    net = skin_net(q, arms, order, spec, tables)
    d_l = head_density(np.maximum(0.62 * reg[:, 0] + 0.38 * reg[:, 1] + 0.04 * reg[:, 2], lift(net, reg)), q, spec,
                       prog)
    more = (rnd >= dens) & (rnd < d_l) & ~net['is_arm']          # live sites the lift plants, on their own draws
    qn, nqn, rgn = strip
    net_n = skin_net(qn, arms, order, spec, tables)
    d_n = head_density(np.maximum(0.62 * rgn[:, 0] + 0.38 * rgn[:, 1] + 0.04 * rgn[:, 2], lift(net_n, rgn)), qn,
                       spec, prog)
    on_n = (rng_s.random(len(qn)) < d_n) & ~net_n['is_arm']
    (qw2, nw2, rbw2), (qs2, ns2, rbs2) = head_features(
        plan, prog, np.vstack([q[more], qn[on_n]]), np.vstack([nq[more], nqn[on_n]]),
        np.concatenate([reg[more, 0], rgn[on_n, 0]]), rng_s, avoid=(qw, rbw, np.vstack([qw, qs])))
    # the arm's papillae behind the node as on the tube (plan_octopus's arm papillae above, at s = 0)
    pr, nr_, ar, jr = root_sites(prog, arms, order, spec, tables, rots)
    on_r = rng_s.random(len(pr)) < 0.55 * np.clip((np.cos(ar) + 0.25) / 0.6, 0.0, 1.0)
    rbr = np.clip(np.exp(rng_s.normal(np.log(0.00045), 0.28, on_r.sum())), 0.0003, 0.0008)
    papilla_strokes(plan, pr[on_r], nr_[on_r], rbr, rbr * (0.35 + 0.55 * rng_s.random(on_r.sum())), 'arm papilla')
    # --- (crown v6b) the BAND off each arm's tube past its first node, where the webs' walls meet the arms' flanks
    # (band_sites): the arm's papillae as on the tube (the reference arm's density in alpha and s) where the skin
    # paints the arm network and no reference site owns the cell, on draws of a child stream of its own (every draw of
    # the live plan, the strip's included, stays as it was)
    rng_b = rng.spawn(1)[0]
    owned = {tuple(k_) for k_ in proc.cells(arm_coord(sa, aa, tables), PATCH['arm'], PATCH['disorder'],
                                            PATCH['seed_arm'])[0]}
    pb, nb_, ab_, sb_, jb_ = band_sites(prog, cage, arms, order, spec, tables, rots, owned, rng_b)
    on_b = rng_b.random(len(pb)) < 0.55 * (np.clip((np.cos(ab_) + 0.25) / 0.6, 0.0, 1.0) *
                                           np.clip(1.0 - (sb_ - 0.45) / 0.5, 0.1, 1.0))
    rbb = np.clip(np.exp(rng_b.normal(np.log(0.00045), 0.28, on_b.sum())), 0.0003, 0.0008) * \
        np.sqrt(np.maximum(arm_radius(sb_[on_b], spec) / spec['arm_r0'], 0.3))
    papilla_strokes(plan, pb[on_b], nb_[on_b], rbb, rbb * (0.35 + 0.55 * rng_b.random(on_b.sum())), 'arm papilla')
    plan.inst['band_papillae'] = dict(p=pb[on_b], n=nb_[on_b], rb=rbb, alpha=ab_[on_b], s=sb_[on_b], arm=jb_[on_b])
    eye_papillae(plan, prog, spec, rng)
    mouth_lip(plan, prog, rng)
    # the funnel's end and channel LAST: carved after the surface detail, nothing planned on its solid tip is left
    # floating in the hollow (t10); only where the cage cut its port (a stand-in's info carries no funnel_rings)
    funnel_lumen(plan, spec, prog, log, port=bool(len(info['funnel_rings'])) if 'funnel_rings' in info else None)
    plan.inst['head_papillae'] = dict(p=np.vstack([qs, qs2]), n=np.vstack([ns_, ns2]), rb=np.concatenate([rbs, rbs2]))
    plan.inst['warts'] = dict(p=np.vstack([qw, qw2]), n=np.vstack([nw, nw2]), rb=np.concatenate([rbw, rbw2]))
    plan.inst['root_papillae'] = dict(p=pr[on_r], n=nr_[on_r], rb=rbr, alpha=ar[on_r], arm=jr[on_r])
    log(f'[plan] suckers {len(ps)} per arm (d {ds.min()*1000:.1f}-{ds.max()*1000:.1f} mm), arm papillae {len(rba)} '
        f'per arm, head papillae {len(qs)}, warts {len(qw)}; behind the first nodes (crown strip) head papillae '
        f'{len(qs2)}, warts {len(qw2)}, the arms\' papillae {int(on_r.sum())}')
    log('[plan] arm papillae seated per arm (column: as rotated / moved onto its skin / dropped): '
        + ', '.join(f'{j} {a}/{b}/{c}' for j, (a, b, c) in enumerate(seat_n)))
    log(f'[plan] the band off the tubes (crown v6b): {len(pb)} free arm-network sites, {int(on_b.sum())} papillae '
        f'(per arm column {np.bincount(jb_[on_b], minlength=len(rots)).tolist()})')
    return plan


def grid_keep(spec, arms, order, margin=0.02):
    """the region the voxel grid lives in: the head, the mantle and the crown (a 0.24 m disc, out past the mantle's
    apex), the crown's reach beyond it: the webs' strips (their side lines run along the arms to web_plan's sw, 0.32 m
    off the axis in v4: the disc alone left each web's outer 7 % unsculpted) and EVERY arm out to sw and 0.03 past it
    (the crown's layers carry each arm's base, its suckers with it, in the head set, to the tube's first ring at s 0.33,
    0.31 m off the axis: with the reference arm alone the other seven lost 141 of the head set's vertices and 7 suckers
    each, patches/v4_sculpt/check), and arm order[0] (the stacked arms' reference) whole with its suckers. 3,071 coarse
    cells by the surface over t10's box (r4's disc and arm 2,127; the webs' strips without the seven arms 2,424)"""
    from scipy.spatial import cKDTree
    from .octopus import N_ARMS, body_axis, margin_s, web_lift, web_patch, web_plan
    plan = web_plan(spec, arms)
    sa = np.linspace(0.0, 1.0, len(arms[0][0]))
    tree = cKDTree(np.concatenate([arms[order[0]][0]] + [a[0][sa <= plan['sw'][i] + 0.03] for i, a in enumerate(arms)]))
    r_body = max(0.24, np.linalg.norm(body_axis(spec)[0][0, [0, 2]]) + 0.01)
    W = []
    for j in range(N_ARMS):
        ia, ib = plan['order'][j], plan['order'][(j + 1) % N_ARMS]
        V, _, _ = web_patch(arms[ia], arms[ib], spec, lambda lam, j=j: margin_s(lam, plan, j),
                            cap=max(plan['sw'][ia], plan['sw'][ib]) + 0.002, nl=41, ns=48,
                            lift=lambda lam, s, j=j: web_lift(spec, plan, j, lam, s))
        W.append(V[np.linalg.norm(V[:, [0, 2]], axis=1) > r_body - margin])
    webs = cKDTree(np.concatenate(W))

    def keep(pts):
        r = np.linalg.norm(pts[:, [0, 2]], axis=1)
        body = (r < r_body) & (pts[:, 1] > -0.02)
        d, _ = tree.query(pts)
        dw, _ = webs.query(pts)
        return body | (d < spec['arm_r0'] + margin + 0.03) | (dw < margin)
    return keep

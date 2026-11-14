"""The RAPTOR face's cage (HAWK_PLAN.md §4.6, §8.1): from the spine's last ring (the feather line round the cere and
the rictus: the plan's K 32 face ring) to the two beak rings.

THE TOPOLOGY (all quads; K's from §8.1):
  U  the upper rhamphotheca's ring, K 24: its shell's base section (heads/raptor.beak: the sink plane SINK mm behind
     the cere's margin) resampled by arc length, vertex 0 on the frame's X (+x, the bird's left), right-handed about
     the shell's base tangent Z (forward)
  L  the lower rhamphotheca's ring, K 16, the same way on its shell
  the GAPE STRIP between them: U's 7 bottom vertices (the keel's, k 15..21) and L's 7 top ones (j 7..1), a middle
     chain M of 7 (the mouth line), two rows of 6 quads. Two rows, not one: the figure loop round U + strip + L must
     have the face ring's 32 vertices, 18 + 10 + 4 = 32 with two rungs at each end (one row gives 33 or 31: the strip
     would be asymmetric)
  F  the figure loop (32): U's arc over the top (k 21 -> 15 through 0), M0, L's arc under the bottom (j 7 -> 1
     through 15), M6. The spine's last ring is bridged to it (loft.bridge, 2 rings between)
U and L stay open: the keratin shells sink into them (SOCKET seams, §8.1). Their ends of the strip (U15, U21, L7, L1)
carry one edge more than the rings' other vertices: the mouth's commissures, poles ON the rings by design; a SOCKET is
never welded across its ring, so the no-pole rule (a WELD's) is printed for these two, not gated.
"""
import numpy as np

from .. import loft as LF

KU, KL = 24, 16
U_CHAIN = list(range(15, 22))          # U's bottom vertices: the middle 7 of its lower half (12..23), the palate's line
#                                        between the tomia (D1.3: the keel's)
L_CHAIN = list(range(7, 0, -1))        # L's top vertices paired with them (157.5 .. 22.5 deg)


def _u(v):
    v = np.asarray(v, np.float64)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def ring_on_polygon(Pw, Z, K):
    """a closed polygon (n, 3) in a plane normal to Z, symmetric about x = 0 -> K points counter-clockwise about Z:
    vertex 0 at its crossing of the frame's X (+x projected off Z), vertex K/2 at its crossing of -X, and K/2 points by
    arc length over each half (D1.3b restart 2: one resampling over the whole loop put vertex K/2 off -X wherever the
    top and the bottom differ in length, so the mirror average below moved vertex 0 off X: 1.44 deg on the bell-
    section bill against the 1 deg bar). Returns the points and the frame (columns X, Y, Z)"""
    Z = _u(Z)
    X = _u(np.array([1.0, 0.0, 0.0]) - Z * Z[0])
    Y = np.cross(Z, X)

    def build(c):
        ang = np.arctan2((Pw - c) @ Y, (Pw - c) @ X) % (2 * np.pi)
        o = np.argsort(ang)
        P = Pw[o]
        a = ang[o]
        Pc = np.vstack([P[-1:], P, P[:1]])                        # cyclic, by angle
        ac = np.concatenate([[a[-1] - 2 * np.pi], a, [a[0] + 2 * np.pi]])

        def at(t):
            # the ray from c at angle t met on the segment between its angular neighbours (exactly: interpolated in
            # angle, a long segment's crossing stood 0.4 mm off the ray, 3 deg)
            i = int(np.searchsorted(ac, t))
            u2 = np.array([np.cos(t), np.sin(t)])
            p0 = np.array([(Pc[i - 1] - c) @ X, (Pc[i - 1] - c) @ Y])
            p1 = np.array([(Pc[i] - c) @ X, (Pc[i] - c) @ Y])
            cr = lambda a_, b_: a_[0] * b_[1] - a_[1] * b_[0]
            den = cr(p1 - p0, u2)
            f = float(np.clip(cr(-p0, u2) / den, 0.0, 1.0)) if abs(den) > 1e-12 else 0.0
            return Pc[i - 1] + f * (Pc[i] - Pc[i - 1])
        pA, pB = at(0.0), at(np.pi)
        halves = []
        for lo, hi, pa, pb in ((0.0, np.pi, pA, pB), (np.pi, 2 * np.pi, pB, pA)):
            path = np.vstack([pa, P[(a > lo) & (a < hi)], pb])
            s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
            t = np.linspace(0.0, s[-1], K // 2, endpoint=False)
            halves.append(np.stack([np.interp(t, s, path[:, k]) for k in range(3)], 1))
        R = np.vstack(halves)
        # symmetric about x = 0 (the shells are): vertex k and K/2 - k mirrored
        M = R[(K // 2 - np.arange(K)) % K] * np.array([-1.0, 1.0, 1.0])
        return 0.5 * (R + M)
    # the centre the crossings are taken from is the RING's own mean (its record's origin, where vertex 0 must lie on
    # X): a fixed point, from the polygon's points' mean (the dense top arc's: 31 deg off on the bell's first ring)
    # (solved by bisection on the centre's height along Y: iterating c = mean(ring(c)) oscillated, 2.2 deg)
    c0 = Pw.mean(0)
    yy = (Pw - c0) @ Y
    lo, hi = 0.9 * float(yy.min()), 0.9 * float(yy.max())
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        R = build(c0 + Y * mid)
        if (R.mean(0) - c0) @ Y > mid:
            lo = mid
        else:
            hi = mid
    return build(c0 + Y * 0.5 * (lo + hi)), np.column_stack([X, Y, Z])


def bridge_by_angle(mesh, loop_a, loop_b, rings, Z, c):
    """loft.bridge's quads (loop_a in its faces' boundary order, `rings` smoothstep-blended rings between), loop_b
    aligned to loop_a by its vertices' ANGLES about the axis (c, Z) rather than by the least summed distance: the
    figure loop's 32 crowd the upper bill's arc and spread thin under the lower, so the least-distance shift moved by
    one with small changes of the chin's clay and twisted the bridge (4 deg corners at the upper bill's flanks, D1.3b
    r2). Returns the mesh and the rings' id lists"""
    from ..mesh import QuadMesh
    A, B = np.asarray(loop_a), np.asarray(loop_b)
    K = len(A)
    V = mesh.V
    Z = _u(Z)
    X = _u(np.cross([0.0, 1.0, 0.0], Z))
    Y = np.cross(Z, X)
    ang = lambda P: np.arctan2((P - c) @ Y, (P - c) @ X)
    aA = ang(V[A])
    best = None
    for direction in (1, -1):
        Bd = B[::direction]
        aB = ang(V[Bd])
        for sh in range(K):
            d = np.angle(np.exp(1j * (aA - np.roll(aB, -sh))))
            cost = float((d * d).sum())
            if best is None or cost < best[0]:
                best = (cost, np.roll(Bd, -sh))
    Bs = best[1]
    ids, newV, nid = [A], [], len(V)
    attrs_new = {k: [] for k in mesh.attrs}
    for r in range(1, rings + 1):
        u = r / (rings + 1)
        h = u * u * (3 - 2 * u)
        newV.append((1 - h) * V[A] + h * V[Bs])
        for k, a in mesh.attrs.items():
            attrs_new[k].append((1 - u) * a[A] + u * a[Bs])
        ids.append(np.arange(nid, nid + K))
        nid += K
    ids.append(Bs)
    Qn = []
    for r in range(len(ids) - 1):
        a, b = ids[r], ids[r + 1]
        for k in range(K):
            k1 = (k + 1) % K
            Qn.append([a[k1], a[k], b[k], b[k1]])
    Vn = np.vstack([V] + newV) if newV else V
    attrs = {k: np.vstack([a] + attrs_new[k]) if attrs_new[k] else a for k, a in mesh.attrs.items()}
    return QuadMesh(Vn, np.vstack([mesh.Q, np.array(Qn)]), attrs), ids


FACE_BRIDGE = 1                        # rings between the spine's last ring (on the cere, 2 mm behind its margin) and the
#                                        figure loop (D1.3: 2 over 13 mm of bare face: 10 flipped quads)
COMMISSURE_OUT = 0.0                   # [E] mm (face(); swept 0-2.5 with drops -0.8..0.8 and one or two bridge rings
#                                        (scratchpad sweep.py): on the final head 0 / 0 / 1 ring is the only setting
#                                        with no folded quad (min corner 6.5 deg); on an earlier head it was 0.8. The
#                                        lower shell's margin section is a 12 x 1.6 mm slit (the chin's feathers cover
#                                        its base in c018's trace), so the quad beside its lateral corner is marginal)
COMMISSURE_DROP = 0.0                  # [E] mm the commissures stand below the strip's midpoints (face())
MOUTH_K = (31, 17)                    # the spine's head columns on the mouth line (left, right; avian_cage pins them
#                                        on the gape's crease back to the rictus). D1.3c fix 2: (30, 18) -> (31, 17):
#                                        the bridge now carries the MOUTH LINE into the upper ring's U21 / U15 (the
#                                        gape strip's upper ends, beside the tomia: the crease is the upper tomial
#                                        edge's own continuation), and the column under it into the commissure M6 /
#                                        M0; the arc over the top has the upper ring's 18 edges, the arc under the jaw
#                                        the strip's ends + the lower ring's 14. With the mouth line run into the
#                                        commissure ((30, 18)) the corner quad (the mouth column, the column over it,
#                                        U21, M6) wrapped the upper base's tomial edge: U21 and M6 both lie under it.
#                                        The corner quad's fold (the better split), each cage built whole in memory on
#                                        the final head (scratch d13c_fix2/fe2.py, logs/fe2_<a..l>.txt): (30, 18) 51.9
#                                        deg (fix 1: 59.6 against the bar's 60; 60.6-62.8 before the head's own tomial
#                                        edge was put back, raptor.head_members); with the commissure 0.5 / 1.0 mm out
#                                        51.6 / 50.1, 0.4 mm down 52.0, FACE_STOP 3.5: 52.6; (31, 17): 43.6. TRIED AND
#                                        DROPPED: the upper ring's vertices 15 / 21 placed ON the shell's tomia (62.4;
#                                        55.8 with (31, 17)): the quad then has the tomial edge for its diagonal; the
#                                        commissure placed on the crease line (61.2); two bridge rings (the nostril's
#                                        block lands across the second: 158 deg)


def face(cg, last_ring, last_frame, shells, log=print):
    """the figure loop at the keratin's MARGIN (D1.3b: U and L were the shells' sunk bases, 2 mm inside the cere's
    skin; the record is where the shell leaves the skin) bridged to the spine's last ring"""
    up, lo = shells['beak_upper'], shells['beak_lower']
    U, FU = ring_on_polygon(np.asarray(up['margin'], float), up['Tm'], KU)
    L, FL = ring_on_polygon(np.asarray(lo['margin'], float), lo['Tm'], KL)
    Ui, Li = cg.add(U), cg.add(L)
    M = np.array([0.5 * (U[U_CHAIN[i]] + L[L_CHAIN[i]]) for i in range(7)])
    # the commissures (the strip's ends) stand COMMISSURE_OUT mm out to the side: at the midpoints the corner quads
    # between U, M and L closed to a 1.6 deg sliver (D1.3b)
    for i in (0, 6):
        M[i] = M[i] + np.array([np.sign(M[i][0]) * COMMISSURE_OUT, -COMMISSURE_DROP, 0.0])
    Mi = cg.add(M)
    for i in range(6):
        cg.Q.append([Ui[U_CHAIN[i]], Ui[U_CHAIN[i + 1]], Mi[i + 1], Mi[i]])
        cg.Q.append([Mi[i], Mi[i + 1], Li[L_CHAIN[i + 1]], Li[L_CHAIN[i]]])
    arcU = [Ui[k % KU] for k in range(21, 15 + KU + 1)]           # 21, 22, 23, 0 .. 15
    arcL = [Li[j % KL] for j in range(7, 1 + KL + 1)]             # 7 .. 15, 0, 1
    F = arcU + [Mi[0]] + arcL + [Mi[6]]
    assert len(F) == 32 == len(last_ring), (len(F), len(last_ring))
    m = cg.mesh()
    loops = [l for l in LF.boundary_loop(m) if set(l) == set(int(v) for v in last_ring)]
    assert len(loops) == 1, 'the spine\'s last ring is not one boundary loop'
    Pl = m.V[np.asarray(last_ring)]
    m, br = bridge_by_angle(m, loops[0], np.array(F), FACE_BRIDGE, last_frame[:, 2], Pl.mean(0))
    cg.set_mesh(m)
    cg.record('beak_upper', Ui, FU, pinned=['head', 'upper_bill'], native=dict(joints=['upper_bill'],
                                                                                 kept_weighted_beyond=0),
              seam='SOCKET', commissures=[int(Ui[15]), int(Ui[21])])
    cg.record('beak_lower', Li, FL, pinned=['jaw'], native=dict(joints=['jaw'], kept_weighted_beyond=0),
              seam='SOCKET', commissures=[int(Li[7]), int(Li[1])])
    log(f'[cage] face: the 32 face ring bridged to the figure loop; U {KU} + the gape strip (2 x 6) + L {KL} '
        f'(SOCKET rings, open)')
    return dict(U=Ui, L=Li, M=Mi, bridge=br)

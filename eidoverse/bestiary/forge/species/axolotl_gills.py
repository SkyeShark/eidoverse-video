"""The axolotl's gill filaments: a STACKED, INSTANCED part (AXOLOTL_PLAN.md §5.7, built as species/octopus_suckers.py
builds the suckers). AX2 makes the templates and their placement for the clay's look; the bake (one template set,
its islands stacked by every instance) and the comb-card LOD come at AX5-AX11.

THE TEMPLATES (four shapes, p17: the filaments curve and cross): each a tapered tube along a curve in its own frame
(x the filament's root-to-tip direction, y the side it bends toward), in units of the ramus diameter D: length
gills.filament_len_D, width gills.filament_w_D with a slightly CLUBBED tip (p17: "the tip slightly clubbed or forked,
pale"); the shapes: near straight, curved back, S-curved, a curled tip. A ramus's filaments are similar copies of these
four scaled by its D, so the six rami (exact similar copies, gills.similar) stack on r1's filaments.

THE PLACEMENT (place), AX7b (10-30; the round-6 look: "spiky cones with one sparse comb of wires" where the photos show
broad feathery fringes; the readings are SPEC ax7b's, NOTES.md in work/bestiary/axolotl/ax7b_notes has the counts): the
fringe is TWO VANES, one along each edge of the stalk's posterior (comb) face, like a feather's (p17's middle ramus seen
from behind carries strands from both edges; p18's every ramus an up-back and a down-back vane), each vane TWO
staggered ranks ax7b.fil_spacing_D1 x r1's D apart along the stalk from ax7b.comb_from to comb_to of its length (to and
past the tip). The stalk is OVAL (families/sprawl's sweep, stalk_aspect: ax7b.ramus_aspect_built, the measured 1.37,
across the comb face, round at its root; r2 / r3 turned whole so they stack on r1, the SPEC's note):
each root sits on that section at its rank's azimuth off the comb direction (ax7b.vane_root_deg), buried ROOT_BURY x D,
and the strand leaves at its rank's splay (ax7b.vane_splay_deg) off the comb direction, leaning ax7b.fil_hang_deg toward
the ramus's tip, with a seeded template, jitter and a little droop. THE STRANDS ARE ONE SIZE ON EVERY RAMUS (r1's: p17's
top and middle rami and p18's three carry strands of one length), so a shorter ramus carries fewer: the count follows
its comb's length. No strand passes through a stalk (a capsule test on the oval stalks, its own beyond the root
included): a strand that would is re-drawn (template, jitter) and at last shortened to clear.
The comb side is fixed in the RAMUS's frame (the bind's posterior-ventral side of each stalk), so it turns with the
ramus in every posture. Filaments are rigid on the gill joint their root sits on.
(Before AX7b: two ranks within 48 deg of one side, gills.per_rank 23 each over 0.80 of the stalk, each strand scaled by
its own ramus's D: 276 strands; now ~650.)
"""
import numpy as np

SHAPES = ('straight', 'curved', 's_curve', 'curl')
RING = 6            # vertices round a template tube (LOD0's K 6, plan §5.7)
SEGS = 9            # rings along it
ROOT_BURY = 0.10    # x D into the stalk
JIT_HANG = 7.0      # deg: the spread of each strand's lean toward the tip
JIT_SCALE = 0.06    # the spread of each strand's length
INNER = 0.92        # the inner rank's strands this much shorter (p17: the rank behind the front row fainter)
RETRIES = 6         # re-draws of a strand that would pass through a stalk, before it is shortened to clear
SEED = 20261030
# (before AX7b: HANG 26, DROOP 0.15, SPREAD (-48, 48), TAPER 0.30, SEED 20261028: the round-6 comb)


def _bend(shape):
    """the template's sideways bend (toward +y, the ramus's tip) over its length u in 0..1, in units of its length:
    every shape curves the same way, like lashes (p14), the s-curve wavy (p17)"""
    return dict(straight=lambda u: 0.06 * u ** 2, curved=lambda u: 0.22 * u ** 2,
                s_curve=lambda u: 0.12 * np.sin(np.pi * u) * (1 - 2 * u) + 0.10 * u,
                curl=lambda u: 0.06 * u + 0.32 * np.clip((u - 0.55) / 0.45, 0, 1) ** 2)[shape]


def _dims(spec):
    """the template's length and width in D units: AX7b's readings (SPEC ax7b), else the plan's (gills.*)"""
    a7, g = spec.get('ax7b'), spec['gills']
    if a7:
        return a7['fil_len_D1'], a7['fil_w_D']
    return g['filament_len_D'], g['filament_w_D']


def centreline(shape, spec, t):
    """the template's centreline at stations t (0 root .. 1 tip), D units, x root -> tip, bending toward +y"""
    L, _ = _dims(spec)
    t = np.asarray(t, np.float64)
    return np.column_stack([t * L, _bend(shape)(t) * L, np.zeros_like(t)])


def radius(spec, t):
    """the template's radius at stations t, D units: near-parallel sides, the tip slightly clubbed (p17). The low
    (template) and the high (axolotl_sculpt.template_program) read this one function"""
    _, w = _dims(spec)
    t = np.asarray(t, np.float64)
    return 0.5 * w * (1.0 - 0.15 * t + 0.25 * np.exp(-((t - 0.93) / 0.05) ** 2))


def template(shape, spec, t=None):
    """one filament template in D units: (V (n, 3), F (m, 3)); x root -> tip, bending toward +y. t: the rings' stations
    along it (0 root .. 1 tip; default SEGS even ones, the clay's look; template_low: the plan's LOD0)"""
    L, w = _dims(spec)
    t = np.linspace(0.0, 1.0, SEGS) if t is None else np.asarray(t, np.float64)
    nseg = len(t)
    C = centreline(shape, spec, t)
    # the radius (radius()), the tip closed by a cap
    r = radius(spec, t)
    V, F = [], []
    T = np.gradient(C, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    for k in range(nseg):
        n1 = np.cross(T[k], [0.0, 0.0, 1.0])
        n1 /= np.linalg.norm(n1)
        n2 = np.cross(T[k], n1)
        for a in range(RING):
            ang = 2 * np.pi * a / RING
            V.append(C[k] + r[k] * (np.cos(ang) * n1 + np.sin(ang) * n2))
    tip = len(V)
    V.append(C[-1] + T[-1] * r[-1] * 0.8)
    for k in range(nseg - 1):
        for a in range(RING):
            a1 = (a + 1) % RING
            p, q, rr, s = k * RING + a, k * RING + a1, (k + 1) * RING + a1, (k + 1) * RING + a
            F += [[p, q, rr], [p, rr, s]]
    for a in range(RING):
        F.append([(nseg - 1) * RING + a, (nseg - 1) * RING + (a + 1) % RING, tip])
    return np.array(V), np.array(F, np.int64)


LOD0_T = (0.0, 0.25, 0.5, 0.75, 0.93, 1.0)    # plan §5.7's LOD0: K 6 x 6 rings and a tip fan (66 triangles); a ring on
#                                               the club's crest (t 0.93) and on the tip's last ring, as the clay's


def template_low(shape, spec):
    """the filament's LOD0 low (AX5): the same curve and radius as template(), on LOD0_T's six rings, in D units"""
    return template(shape, spec, t=LOD0_T)


def smooth01(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def stalk_aspect(spec, t):
    """the oval stalk's aspect (across the comb face over along it) at the stalk's share t (0 base .. 1 tip; t < 0 the
    buried root): round at the root, SPEC ax7b.ramus_aspect_built by ax7b.ramus_aspect_ramp (families/sprawl's sweep
    reads the same function, so the strands' roots sit on the clay's own stalk). The measured aspect is
    ax7b.ramus_aspect (1.37); the clay builds ramus_aspect_built (its TAGS note, the rami's stacks)"""
    a7 = spec.get('ax7b')
    t = np.asarray(t, np.float64)
    if not a7:
        return np.ones_like(t)
    return 1.0 + (a7['ramus_aspect_built'] - 1.0) * smooth01(t / a7['ramus_aspect_ramp'])


def oval_radius(r, asp, th):
    """the oval section's radius at azimuth th off its n axis (r along n, r x asp along b): sdf.sd_sweep's rule"""
    return r * asp / np.sqrt((asp * np.cos(th)) ** 2 + np.sin(th) ** 2)


def _stalk_frames(R, spec):
    """per node of one stalk: unit tangent, n (the comb side across the tangent), b = t x n, the n-radius, the aspect"""
    C, rad, comb = np.asarray(R['C'], np.float64), np.asarray(R['R'], np.float64), np.asarray(R['comb'], np.float64)
    T = np.gradient(C, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    N = comb - T * (comb * T).sum(1)[:, None]
    N /= np.linalg.norm(N, axis=1, keepdims=True)
    B = np.cross(T, N)
    arc = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
    return C, T, N, B, rad, stalk_aspect(spec, arc / arc[-1]), arc


def _inside_stalks(S, stalks, margin, own=None, own_from=0.0, S_t=None):
    """True per sample point S (m, 3) that lies inside any oval stalk (grown by margin (m,)). stalks: [(A, B, nA, bA,
    rA, rB, aspA, aspB)] segment arrays; own: the index of the strand's own stalk, whose test skips samples with S_t <
    own_from (the root, buried in it)"""
    hit = np.zeros(len(S), bool)
    for si, (A, Bq, nA, bA, rA, rB, aA, aB) in enumerate(stalks):
        AB = Bq - A
        u = np.clip(np.einsum('mkj,kj->mk', S[:, None, :] - A[None], AB) / np.maximum((AB * AB).sum(1), 1e-30)[None],
                    0.0, 1.0)
        Q = A[None] + u[..., None] * AB[None]
        q = S[:, None, :] - Q
        d = np.linalg.norm(q, axis=2)
        k = np.argmin(d, axis=1)
        m = np.arange(len(S))
        uu = u[m, k]
        qn = (q[m, k] * nA[k]).sum(1)
        qb = (q[m, k] * bA[k]).sum(1)
        r = rA[k] * (1 - uu) + rB[k] * uu
        asp = aA[k] * (1 - uu) + aB[k] * uu
        inside = d[m, k] < oval_radius(r, asp, np.arctan2(qb, qn)) + margin
        if own is not None and si == own and S_t is not None:
            inside &= S_t >= own_from
        hit |= inside
    return hit


def place(spec, rami):
    """the instances for each ramus (module docstring, AX7b). rami: {(r, side): dict(C (n, 3) centreline base -> tip,
    R (n,) the stalk's radius along its comb direction, comb (n, 3) unit comb-side direction per node, D, joint (n,) the
    gill joint index each node rides)} in any units (D the same units). Returns a list of dicts (ramus key, shape,
    origin, frame 3x3 (columns x, y, z), scale (units per template D unit), node index, joint, vane, rank, clear: the
    strand passes no stalk)"""
    a7 = spec['ax7b']
    rng = np.random.default_rng(SEED)
    out = []
    down = np.array([0.0, -1.0, 0.0])
    D1 = max(float(R['D']) for R in rami.values())             # r1's D: every strand is r1's size (module docstring)
    step = a7['fil_spacing_D1'] * D1
    prof = np.asarray(a7['fil_len_profile'], np.float64)
    L_t, w_t = _dims(spec)
    jit = a7['vane_jitter_deg']
    keys = list(rami)
    frames = {key: _stalk_frames(rami[key], spec) for key in keys}
    stalks = []
    for key in keys:
        C, T, N, B, rad, asp, arc = frames[key]
        stalks.append((C[:-1], C[1:], N[:-1], B[:-1], rad[:-1], rad[1:], asp[:-1], asp[1:]))
    t_s = np.linspace(0.0, 1.0, SEGS)
    cl = {s: centreline(s, spec, t_s) for s in SHAPES}
    n_redrawn = n_short = 0
    for si, key in enumerate(keys):
        R = rami[key]
        C, T, N, B, rad, asp, arc = frames[key]
        D = float(R['D'])
        Lr = arc[-1]
        a0, a1 = a7['comb_from'] * Lr, a7['comb_to'] * Lr
        for vane in (1.0, -1.0):
            for rank in range(a7['ranks_per_vane']):
                # the ranks staggered half a step, the two vanes a quarter step apart
                off = 0.5 * rank + (0.25 if vane < 0 else 0.0)
                for k in range(int(np.floor((a1 - a0) / step)) + 1):
                    a = a0 + (k + off) * step
                    if a > a1:
                        continue
                    i = int(np.clip(np.searchsorted(arc, a) - 1, 0, len(C) - 2))
                    f = (a - arc[i]) / max(arc[i + 1] - arc[i], 1e-12)
                    c = C[i] + f * (C[i + 1] - C[i])
                    t = T[i] * (1 - f) + T[i + 1] * f
                    t /= np.linalg.norm(t)
                    n = N[i] * (1 - f) + N[i + 1] * f
                    n = n - t * (n @ t)
                    n /= np.linalg.norm(n)
                    b = np.cross(t, n)
                    r_ = rad[i] * (1 - f) + rad[i + 1] * f
                    as_ = asp[i] * (1 - f) + asp[i + 1] * f
                    u = a / Lr
                    for attempt in range(RETRIES + 1):
                        # the root on the oval at the rank's azimuth, buried along the oval's own normal there
                        th = np.radians(vane * (a7['vane_root_deg'][rank] + rng.normal(0.0, 0.5 * jit)))
                        rho = oval_radius(r_, as_, th)
                        nrm = np.cos(th) * n + (np.sin(th) / as_ ** 2) * b
                        nrm /= np.linalg.norm(nrm)
                        origin = c + rho * (np.cos(th) * n + np.sin(th) * b) - nrm * ROOT_BURY * D
                        # the strand: its rank's splay off the comb side, leaning toward the tip, a little droop
                        ph = np.radians(vane * (a7['vane_splay_deg'][rank] + rng.normal(0.0, jit)))
                        d_out = np.cos(ph) * n + np.sin(ph) * b
                        hang = np.radians(a7['fil_hang_deg'] + rng.normal(0.0, JIT_HANG))
                        x = np.cos(hang) * d_out + np.sin(hang) * t
                        x = (1.0 - a7['fil_droop']) * x + a7['fil_droop'] * down
                        x /= np.linalg.norm(x)
                        y = t - x * (t @ x)                 # bend toward the ramus's tip
                        if np.linalg.norm(y) < 1e-6:
                            y = b
                        y /= np.linalg.norm(y)
                        z = np.cross(x, y)
                        Fm = np.column_stack([x, y, z])
                        scale = D1 * float(np.interp(u, prof[:, 0], prof[:, 1])) * (1.0 + rng.normal(0.0, JIT_SCALE))
                        if rank:
                            scale *= INNER
                        shape = SHAPES[int(rng.integers(len(SHAPES)))]
                        S = origin + (cl[shape] * scale) @ Fm.T
                        hit = _inside_stalks(S, stalks, np.full(len(S), 0.6 * w_t * scale), own=si, own_from=0.25,
                                             S_t=t_s)
                        if not hit.any():
                            break
                    clear = not hit.any()
                    if attempt:
                        n_redrawn += 1
                    if not clear:
                        # shortened to clear: the strand ends short of its first sample inside a stalk
                        j = int(np.argmax(hit))
                        scale *= max(0.25, 0.85 * t_s[max(j - 1, 1)])
                        S = origin + (cl[shape] * scale) @ Fm.T
                        clear = not _inside_stalks(S, stalks, np.full(len(S), 0.6 * w_t * scale), own=si,
                                                   own_from=0.25, S_t=t_s).any()
                        n_short += 1
                    out.append(dict(key=key, shape=shape, origin=origin, frame=Fm, scale=float(scale), node=i,
                                    joint=int(R['joint'][i]), vane=int(vane), rank=int(rank), clear=bool(clear)))
    place.stats = dict(n=len(out), redrawn=n_redrawn, shortened=n_short, uncleared=sum(not q['clear'] for q in out),
                       per_ramus={f'{k[0]}{k[1]}': sum(q['key'] == k for q in out) for k in keys})
    return out


def mesh(spec, instances, transforms=None):
    """the instanced filaments as one triangle mesh (for the clay's renders): each instance's template scaled, turned
    and moved; transforms {joint index: 4 x 4} moves each filament rigidly with its joint (the posture). Returns (V, F,
    per-face instance id)"""
    temps = {s: template(s, spec) for s in SHAPES}
    Vs, Fs, I = [], [], []
    off = 0
    for k, ins in enumerate(instances):
        Vt, Ft = temps[ins['shape']]
        P = ins['origin'] + (Vt * ins['scale']) @ ins['frame'].T
        if transforms is not None and ins['joint'] in transforms:
            M = transforms[ins['joint']]
            P = P @ M[:3, :3].T + M[:3, 3]
        Vs.append(P)
        Fs.append(Ft + off)
        I.append(np.full(len(Ft), k))
        off += len(P)
    return np.concatenate(Vs), np.concatenate(Fs), np.concatenate(I)

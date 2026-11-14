"""X5 (work/bestiary/research/LOBSTER_PLAN.md §8 and §12's X5 row): THE LOBSTER'S UVs on the accepted X4 cages
(work/bestiary/lobster/cage_x04_crusher.npz: both chelipeds, coxa to dactyl, with their sleeves; the other parts come
with their cages). The LIMBS 4096 set; every repeat stacked on its largest copy; the density printed and FROZEN. The
step script is work/bestiary/tests/x05_uv.py. The house's UV tools are read and called, never edited (forge/uv.py,
species/stag_beetle_uv.py: LSCM + ARAP charts, the meridian seam, the Fiedler split, the sleeve strip, the raster pack;
species/axolotl_uv.py: the thickness pads).

THE STACKS (plan §8's groups; Skye's rule, memory feedback_stack_identical_parts_uvs: repeated pieces share their largest
copy's shells, never an extra set):
  - MIRROR PAIRS: the right cheliped's proximal shells (coxa, basi-ischium, merus) and its four sleeves are the left's
    exact mirrors vertex for vertex (x -> -x, quads reversed: x04 gate 6), so each takes the left's UVs corner for corner,
    the tangent's sign flipped (glTF TANGENT w = -1).
  - THE RIGHT CLAW (the cutter) on its LEFT-BUILT cages (cheliped_propodus_cutter_L, cheliped_dactyl_cutter_L): x04 builds
    the cutter on the left from its own programs and mirrors it; the left-built copy is the primary (it is never drawn:
    the lobster's left claw is the crusher), the right claw its mirrored copy.
  - UNIQUE: the right CARPUS. Its shape is the left's mirror, but it carries the CUTTER's wrist margin (x04: its regions
    and skin are the cutter build's), so its membrane / chitin boundary differs from the left's: one baked zone or albedo
    cannot serve both. The two claws (crusher and cutter: different shells).
  - NOT the cross-side scaled stack of plan §8 row 2 (the proximal segments of one side on the other's at one scale): the
    two chelipeds' proximal chains are ONE cage here (x04: the cutter's proximal chain is the crusher's, identical), so
    the mirror pair is that stack at scale 1 (the checker's basi-ischium rule holds trivially).
HIDDEN MEANS HIDDEN (plan §8): x04's faces hidden over the motion range (hidden_<i>) get a token SHARE['hidden'] of the
density (valid UVs and tangents, ~1/256 of the area); EXCEPT the faces that x04 flags hidden but that STAND OUT on the
posed LOWS the engine draws (posed_low_out: the X4f check's rule, the X4g check's lowhid list: N x N samples a quad, the
shells rigid, the skinned cages by their weights, out of BOTH relations at some pose): those get the full density.
THE SEAMS: each shell's graft-ring loops (X3's records on a shell: the basi-ischium's autotomy weld, the carpus's wrist
ring) are island boundaries; each closed piece is then cut by stag_beetle_uv.unwrap_master (a tube along ONE meridian
on its hidden line, HIDDEN_DIR; every chart that fails the bars or mixes seen and hidden faces bisected). The sleeves are
strips (stag_beetle_uv.sleeve_strip), a graft sleeve's record ring held on one straight UV edge.
THE PACK: stag_beetle_uv.pack (raster, FFT, bottom-left, quarter turns), each island padded by its thickness / 8 within
PAD (axolotl_uv.island_pads; stacked islands x STACK_PAD). THE DENSITY (DENSITY's comment): what the fuller set (BODY,
by X2's measured areas) affords, 3,800 px/m at x4, frozen here; x05 prints what the chelipeds fill and the LIMBS page
projected with the walking legs' X2 areas (their cages come later).
X5b (the lead's call 1 on the X4h check, 11-09: the claws' seams crossed their broad faces, 197 / 86 / 84 / 116 / 72 mm in
sight on the crusher propodus / dactyl / carpus / cutter propodus / dactyl): THE CLAWS' SEAMS on the ventral margin, the
finger bases and the joint rings (claw_charts, CLAW_SHELLS; the study-T crab creature's claw, read only: its fixed finger one
island cut along its concave margin, the wrist one wrapped island, 12 islands, anisotropy p95 1.37):
  - each claw shell's hidden faces are cut off on their class line (a seam no one sees: one side is never in sight) and
    charted by the shared unwrap_master at the hidden share; X3's ring loops stay boundaries;
  - each SEEN piece is opened by ONE TREE of cheapest edge paths (cut_tree) joining its terminals: every boundary loop
    (the joint ends, the socket's opening) and, on an elongated piece, its two axial poles (the finger's tip); the cost
    makes the broad faces dear (x(1 + CUT A) where |n_x| passes CUT broad), the dorsal side dearer than the ventral
    (the cameras look down), and OCCLUDED edges cheap (exposure: the share of hemisphere rays that escape the claw's own
    chain and the ground within EXPOSURE reach): so the cuts take the ventral margin, the gape under the dactyl (the
    finger bases: the fixed finger's occlusal rim from the socket to its tip) and the joint ends, the lead's three places;
    creases and region boundaries (the occlusal rims, the joint margins) are cheaper still;
  - each seen piece is ONE chart, unwrapped whole (unwrap_whole: the shared LSCM + ARAP, LSCM's pins moved when a try
    flips or overlaps), never bisected across a face: the chart's bars are CLAW_ANISO (the crab creature's claw ships at p95
    1.37) and the shared CHART_SCALE;
  - the RIGHT CARPUS (unique: the cutter's wrist margin) takes the left's charts mirrored (mirror_charts: the same seams,
    its own texels; LSCM's pins under the mirror flipped 2 triangles at a spine tip that the left's did not).
true_seams counts a cut INSIDE a chart (a slit: unwrap_master's tube meridian, the trees) as a seam, as the texture sees it.
UNITS: the cages' lows in x4 metres (the npz); charts in life mm; texels at DENSITY px per x4 metre."""
import numpy as np

from . import axolotl_uv as AXU
from . import stag_beetle_uv as BU

SIZE = 4096
DENSITY = 3800.0                # px/m at x4 (15,200 at life, 0.066 mm a texel). Plan §8's rule: THE density is the one the
#                                 FULLER set affords. Its planning value 4,450 came from shape factors read by eye; X2's
#                                 measured clay (work/bestiary/lobster/x02_areas.json, sets) has BODY seen 50,807 mm^2 (plan
#                                 32,809) and LIMBS 38,675 (plan 30,842): BODY affords 3,801 px/m at packing 0.70, LIMBS
#                                 4,356. X5's own trial at 4,450 (x05 _dry, X4h) could not pack even the chelipeds on one
#                                 page (their seen 37,314 mm^2: 69 % of the square in triangles, 81 % with pads, then a
#                                 second page). So 3,800, BODY's at 0.70 (the lead's 10-28 note: "BODY ~3,920 px/m decided
#                                 at X5"); the palm's granules at ~4 texels, the carapace pits at 8-15
SCALE_X4 = 4.0
SHARE = {0: 1.0, 1: 1.0 / 16.0, 2: 1.0 / 16.0}      # by stag_beetle_uv's chart class (0 seen; 1 / 2 the hidden classes)
HIDDEN_DIR = (0.0, -1.0, 0.0)   # the chelipeds' cheap side: ventral (their seams' meridian)
LOW_SAMPLES = 11                # posed_low_out: N x N samples a quad (the X4g check's lowhid11)
M_X = np.array([-1.0, 1.0, 1.0])
JN = [f'cheliped_{s}_L' for s in ('coxa', 'basis', 'merus', 'carpus', 'propodus', 'dactyl')]
# X5b (module docstring): the claw shells charted by claw_charts, the unique mirror copies by mirror_charts
CLAW_SHELLS = ('cheliped_propodus_L', 'cheliped_dactyl_L', 'cheliped_carpus_L', 'cheliped_propodus_cutter_L',
               'cheliped_dactyl_cutter_L')
CLAW_MIRRORS = {'cheliped_carpus_R': 'cheliped_carpus_L'}
# the cut's cost per edge (cut_tree): length x (1 + view (1 - n.h)) x (1 + A s(|n_x|; broad)) x (lo + hi e^2), e the edge's
# exposure; x hidden on an edge touching a hidden face, x region on a region boundary, x crease on a creased edge. A 40:
# a broad-face edge costs 41 ventral ones (scratch x5b_probe: at 40 every claw's tree stays off its broad faces)
CUT = dict(A=40.0, broad=(0.45, 0.60), view=2.0, expo=(0.1, 0.9), hidden=0.05, region=0.3, crease=0.3, elong=2.5,
           feature=20.0)
# the exposure (exposure()): rays from each cage vertex over its hemisphere (cosine-weighted, `rays`), escaping when they
# meet nothing of the claw's own side (every shell and sleeve at the bind) nor the ground (y = ground) within `reach`
# (life mm: about the claw's half size)
EXPOSURE = dict(reach=40.0, rays=64, ground=0.0, lift=0.02)
# X5b's chart bar: the claws' charts, unwrapped whole, at anisotropy p95 <= CLAW_ANISO (area weighted, per chart): the study T
# crab creature's claw ships at p95 1.37 (its wrapped hand island 1.54, its finger 1.27, a scratch measurement); my worst
# claw chart needs 1.29 (the carpus's narrowing membrane band, opened once); the layout's own gate stays plan §8's 1.2
CLAW_ANISO = 1.35
# x6fix_x7 (11-11, Opus 5.5): ... and a claw chart that fails the LAYOUT's own bar (x05 gate 2's area-weighted p95 1.2)
# or overlaps itself is SPLIT ONCE (claw_charts): a second cheapest path between the tree's first two terminals,
# through none of its other vertices, cuts the piece in two along the next cheapest line (cut_tree second). On the A0
# clay (the flat fingers' plane, the round palm margins, the fist carpus) X5b's one-cut charts read: the crusher
# propodus p95 1.333 (X5b 1.164), the carpus 1.269 with 125 texels folded over itself and 1.279; the page's p95 1.274
# (x05 _a0g_smoke, scratch x6fix_x7 runs/x05_a0g_smoke.log)
CLAW_SPLIT = 1.2
BROAD_NX = 0.6                 # x05 gate 9: a seam edge on a BROAD face where its normal's |n_x| passes this (X4h's measure)
#                                 A0 (11-11): |n . T| with T the claw's own THIN axis (thin_axes) where one is given. The
#                                 world's x WAS that axis while the fingers' plane stood vertical (X1-X4h: the X5b / X6
#                                 check measured T = (0.94, 0.00, 0.34) on the propodus); since A0 the plane is flat
#                                 (rig.cheliped.claw_plane 0): the broad faces look up and down, and |n_x| would call the
#                                 claws' MARGINS broad and lay every cut along the middle of a broad face


def thin_axes(C, log=print):
    """A0: each claw shell's THIN axis T (unit; the direction its two broad faces look along), read from the cage itself:
    the least-variance axis of its claw's PROPODUS (a flattened spindle: the crusher's L : W : D = 115 : 62 : 30 mm), for
    that propodus, its dactyl and, on the crusher's side, the carpus that carries it; a mirror copy (CLAW_MIRRORS) takes
    its primary's axis mirrored. cut_tree's broad cost and seam_report's 'broad' class measure |n . T| with it"""
    out = {}
    for prop, shells in (('cheliped_propodus_L', ('cheliped_propodus_L', 'cheliped_dactyl_L', 'cheliped_carpus_L')),
                         ('cheliped_propodus_cutter_L', ('cheliped_propodus_cutter_L', 'cheliped_dactyl_cutter_L'))):
        if prop not in C:
            continue
        V = np.asarray(C[prop]['V'], np.float64)
        w, U = np.linalg.eigh(np.cov((V - V.mean(0)).T))
        T = U[:, 0] * (1.0 if U[1, 0] >= 0.0 else -1.0)
        for nm in shells:
            if nm in C:
                out[nm] = T
        sd = np.sqrt(np.maximum(w, 0.0))
        log(f'[lobster_uv] thin axis of {prop}: ({T[0]:+.3f}, {T[1]:+.3f}, {T[2]:+.3f}) (the cage vertices\' spread along '
            f'its three axes {sd[2]:.1f} / {sd[1]:.1f} / {sd[0]:.1f} mm)')
    for cp, pr in CLAW_MIRRORS.items():
        if pr in out and cp in C:
            out[cp] = out[pr] * M_X
    return out


def tex_per_mm(D=DENSITY):
    """texels per LIFE mm at D px per x4 metre"""
    return D * SCALE_X4 / 1000.0


# ============================================================================================ the cages
def load(z, meta, sc):
    """{name: dict(V life mm, Q, region, hidden, sharp {(a, b): s}, meta, skins)} from x04's npz"""
    out = {}
    for i, nm in enumerate(str(n) for n in z['names']):
        sh = {(int(a), int(b)): float(s_) for a, b, s_ in np.asarray(z[f'sharp_{i}']).reshape(-1, 3)}
        out[nm] = dict(name=nm, i=i, V=np.asarray(z[f'V_x4_{i}'], np.float64) / sc, Q=np.asarray(z[f'Q_{i}'], np.int64),
                       region=np.array([str(r) for r in z[f'region_{i}']]), hidden=np.asarray(z[f'hidden_{i}'], bool),
                       sharp=sh, meta=meta.get(nm, {}), skins=np.asarray(z[f'skins_{i}'], np.float64)
                       if f'skins_{i}' in z.files else None)
    return out


def stacks(C):
    """{copy: primary} by plan §8 (module docstring), each checked EXACT here: V_copy == M V_primary, Q reversed"""
    st = {}
    for nm in C:
        if not nm.endswith('_R') or nm == 'cheliped_carpus_R':
            continue
        p = nm[:-2] + '_L'
        if nm in ('cheliped_propodus_R', 'cheliped_dactyl_R'):
            p = nm.replace('_R', '_cutter_L')
        st[nm] = p
    return st


def mirror_residual(C, copy, prim):
    """the copy's corners against its primary's mirrored, vertex for vertex (life mm), and whether the quads match
    reversed"""
    a, b = C[copy], C[prim]
    if a['V'].shape != b['V'].shape or not np.array_equal(a['Q'], b['Q'][:, ::-1]):
        return np.inf, False
    return float(np.abs(a['V'] - b['V'] * M_X).max()), True


# ============================================================================================ the posed lows
def posed_low_out(C, spec, chain, body, log=print, ns=LOW_SAMPLES):
    """the faces x04 flags HIDDEN that stand out on the posed LOWS (module docstring; the X4f / X4g checks' probe): per
    shell the set of quad ids, both chains (the cutter's: its left-built claw, the right carpus mirrored back)"""
    import warp as wp
    from ..families import decapod_cage as DC

    @wp.kernel
    def k_sd(mesh: wp.uint64, pts: wp.array(dtype=wp.vec3), maxd: float, out: wp.array(dtype=float)):
        i = wp.tid()
        q = wp.mesh_query_point_sign_winding_number(mesh, pts[i], maxd)
        if q.result:
            out[i] = wp.length(pts[i] - wp.mesh_eval_position(mesh, q.face, q.u, q.v)) * q.sign
        else:
            out[i] = 1.0e9

    def sd(V, Q, P):
        T = np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]])
        m = wp.Mesh(points=wp.array(np.asarray(V, np.float32), dtype=wp.vec3),
                    indices=wp.array(T.astype(np.int32).ravel(), dtype=wp.int32))
        o = wp.zeros(len(P), dtype=float)
        wp.launch(k_sd, dim=len(P), inputs=[m.id, wp.array(np.asarray(P, np.float32), dtype=wp.vec3), 200.0, o])
        return o.numpy().astype(np.float64)

    def bilinear(V, Q):
        u = np.linspace(0.5 / ns, 1.0 - 0.5 / ns, ns)
        uu, vv = np.meshgrid(u, u, indexing='ij')
        uu, vv = uu.ravel()[:, None, None], vv.ravel()[:, None, None]
        P = V[Q]
        o = ((1 - uu) * (1 - vv) * P[None, :, 0] + uu * (1 - vv) * P[None, :, 1] + uu * vv * P[None, :, 2]
             + (1 - uu) * vv * P[None, :, 3])
        return np.transpose(o, (1, 0, 2))

    def cg(nm, mirror=False):
        c = C[nm]
        pairs = [list(p_) for p_ in (c['meta'].get('skins') or [])]
        d = dict(name=nm, V=c['V'], Q=c['Q'], hidden=c['hidden'], skins=c['skins'], pairs=pairs)
        if mirror:
            d.update(V=c['V'] * M_X, Q=c['Q'][:, ::-1].copy(),
                     pairs=[[p_[0][:-2] + '_L' if p_[0].endswith('_R') else p_[0], p_[1][:-2] + '_L'] for p_ in pairs])
        return d
    C0 = {j: cg(j) for j in JN}
    chains = dict(crusher=dict(C0), cutter=dict(C0))
    chains['cutter']['cheliped_carpus_L'] = cg('cheliped_carpus_R', mirror=True)
    chains['cutter']['cheliped_propodus_L'] = cg('cheliped_propodus_cutter_L')
    chains['cutter']['cheliped_dactyl_L'] = cg('cheliped_dactyl_cutter_L')
    MO = {k: DC.joint_motions(spec, chain, k) for k in chains}

    def posed(kind, i, a, j):
        c = chains[kind][j]
        mo = MO[kind][JN[i]]
        R = DC.rot_axis(mo['z'], a)
        o = np.asarray(mo['o'], np.float64)
        col = next((k_ for k_, p_ in enumerate(c['pairs']) if p_[1] == JN[i]), None)
        if col is not None and c['skins'] is not None:
            w = c['skins'][:, col][:, None]
            return (1.0 - w) * c['V'] + w * ((c['V'] - o) @ R.T + o)
        return (c['V'] - o) @ R.T + o if JN.index(j) >= i else c['V']
    out = {}
    for kind in ('crusher', 'cutter'):
        for i, j in enumerate(JN):
            if kind == 'cutter' and i < 3:
                continue
            c = chains[kind][j]
            q = np.nonzero(c['hidden'])[0]
            if not len(q):
                continue
            best = np.full(len(q), np.inf)
            rels = [('union', i)] + ([('child', i + 1)] if i + 1 < len(JN) else [])
            for rel, ji in rels:
                worst = np.full((len(q), ns * ns), -1e9)
                for a in MO[kind][JN[ji]]['angles']:
                    P = bilinear(posed(kind, ji, a, j), c['Q'][q]).reshape(-1, 3)
                    if rel == 'union':
                        d = body.eval(P)
                        for jj in JN[:i]:
                            d = np.minimum(d, sd(posed(kind, ji, a, jj), chains[kind][jj]['Q'], P))
                    else:
                        jc = JN[ji]
                        d = sd(posed(kind, ji, a, jc), chains[kind][jc]['Q'], P)
                    worst = np.maximum(worst, d.reshape(len(q), ns * ns))
                best = np.minimum(best, worst.max(axis=1))
            name = c['name']
            ids = set(int(x) for x in q[best > 0.0])
            out[name] = out.get(name, set()) | ids
            log(f'[lobster_uv] posed lows ({kind} chain): {name}: {len(q)} flagged hidden, {len(ids)} stand out '
                f'({sorted(ids)})')
    return out


# ============================================================================================ the charts
def ring_seams(c):
    """the shell's graft-ring loops (X3's records it carries: meta records {name: ring vertex ids}) as seam edges"""
    out = set()
    for rn, ids in (c['meta'].get('records') or {}).items():
        ids = [int(v) for v in ids]
        for a, b in zip(ids, ids[1:] + ids[:1]):
            out.add((min(a, b), max(a, b)))
    return out


def face_components(Q, cut):
    """face labels: quads joined across shared edges that are not in `cut`"""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    e2f = {}
    for f, q in enumerate(Q):
        for k in range(4):
            a, b = int(q[k]), int(q[(k + 1) % 4])
            e2f.setdefault((min(a, b), max(a, b)), []).append(f)
    r, s = [], []
    for e, fs in e2f.items():
        if e in cut or len(fs) != 2:
            continue
        r.append(fs[0])
        s.append(fs[1])
    G = coo_matrix((np.ones(len(r)), (r, s)), shape=(len(Q), len(Q)))
    return connected_components(G, directed=False)[1]


def sub_piece(Vs, Qs, sh, F):
    """the faces F of a piece as their own mesh: (V, Q, sharp, vs), vs = the piece's vertex ids"""
    vs = np.unique(Qs[F])
    rid = -np.ones(len(Vs), np.int64)
    rid[vs] = np.arange(len(vs))
    return Vs[vs], rid[Qs[F]], [(int(rid[a]), int(rid[b])) for (a, b) in sh if rid[a] >= 0 and rid[b] >= 0], vs


def free_seen(ch, Vs, Qs, sh, fc, log=print, name=''):
    """X5 (X4h): stag_beetle_uv.chart_class packs a chart at the HIDDEN share when under 15 % of its area is seen, and splits
    it on the class line only between 15 and 85 %: a small seen piece inside a large hidden chart stays at 1/16 of the
    density (on the X4h cages: the cutter dactyl's crease quad 3, on the posed lows' list, and 7 faces x04 never flagged
    hidden, on the coxa and the cutter propodus). Each such chart is charted again: its seen faces, piece by connected
    piece, as charts of their own (seen), the rest by unwrap_master (hidden). Ids stay the piece's (faces, orig)"""
    out = []
    for x in ch:
        s = x['faces'][fc[x['faces']] == 0]
        if x['cls'] == 0 or not len(s):
            out.append(x)
            continue
        h = x['faces'][fc[x['faces']] != 0]
        lab = face_components(Qs[s], set())
        groups = [s[lab == k] for k in np.unique(lab)]
        for F in groups + ([h] if len(h) else []):
            V2, Q2, sh2, vs = sub_piece(Vs, Qs, sh, F)
            for y in BU.unwrap_master(V2, Q2, sh2, fc[F], HIDDEN_DIR, log=log, name=f'{name}/freed'):
                y['faces'] = F[y['faces']]
                y['orig'] = vs[y['orig']]
                out.append(y)
        log(f'[lobster_uv] {name}: {len(s)} seen faces freed from a hidden chart of {len(x["faces"])} '
            f'({len(groups)} seen pieces)')
    return out


def shell_charts(c, seen_extra, log=print):
    """one master shell's charts (life mm): its ring loops cut first, each piece by stag_beetle_uv.unwrap_master, then
    free_seen; the face class 0 (seen) unless x04 flags it hidden and it is not in seen_extra (then 2). Returns charts with
    GLOBAL faces and orig (the shell's vertex ids)"""
    V, Q = c['V'], c['Q']
    fcls = np.where(c['hidden'], 2, 0)
    if seen_extra:
        fcls[np.array(sorted(seen_extra), int)] = 0
    lab = face_components(Q, ring_seams(c))
    out = []
    for L in np.unique(lab):
        fs = np.nonzero(lab == L)[0]
        Vs, Qs, sh, vs = sub_piece(V, Q, list(c['sharp']), fs)
        ch = BU.unwrap_master(Vs, Qs, sh, fcls[fs], HIDDEN_DIR, log=log, name=f'{c["name"]}#{L}')
        ch = free_seen(ch, Vs, Qs, sh, fcls[fs], log=log, name=f'{c["name"]}#{L}')
        for x in ch:
            x['faces'] = fs[x['faces']]
            x['orig'] = vs[x['orig']]
            x['shell'] = c['name']
        out += ch
    return out


def sleeve_chart(c):
    """a sleeve's strip (stag_beetle_uv.sleeve_strip): its axis from its rings' centres; a graft sleeve (one carrying a
    record) holds that ring on one straight UV edge"""
    K = int(c['meta']['K'])
    V = c['V']
    rings = [V[r * K:(r + 1) * K].mean(0) for r in range(len(V) // K)]
    ax = rings[-1] - rings[0]
    graft = bool(c['meta'].get('records'))
    ch = BU.sleeve_strip(V, c['Q'], K, HIDDEN_DIR, ax, graft=graft)
    if graft:                                           # (the strip orders the rings by the axis: the record must be
        rid = [int(v) for v in list(c['meta']['records'].values())[0]]      # its first ring, the straight edge)
        assert set(ch['orig'][ch['graft_edge']]) == set(rid), f'{c["name"]}: the strip\'s straight edge is not its record'
    ch['shell'] = c['name']
    return ch


# ============================================================================================ the gates' measures
def tri_density(Vc, Fc, uvt):
    """per triangle: texels per life mm (the root of the area ratio), the anisotropy, the 3D area (mm^2)"""
    import eidoverse.bestiary.forge.uv as UVm
    s1, s2, ok = UVm.stretch(Vc, Fc, uvt)               # mm per texel
    a3 = 0.5 * np.linalg.norm(np.cross(Vc[Fc[:, 1]] - Vc[Fc[:, 0]], Vc[Fc[:, 2]] - Vc[Fc[:, 0]]), axis=1)
    return np.where(ok, 1.0 / np.sqrt(s1 * s2), 0.0), np.where(ok, s1 / s2, 99.0), a3


def raster_overlaps(tris_px, size):
    """texels whose centre lies inside two or more of the triangles (texel coordinates, (m, 3, 2)); returns the count and
    the coverage count image"""
    cov = np.zeros((size, size), np.uint8)
    for t in tris_px:
        x0, y0 = np.floor(t.min(0)).astype(int)
        x1, y1 = np.ceil(t.max(0)).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, size - 1), min(y1, size - 1)
        if x1 < x0 or y1 < y0:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        a, b, c = t
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-12:
            continue
        l0 = ((b[1] - c[1]) * (gx - c[0]) + (c[0] - b[0]) * (gy - c[1])) / den
        l1 = ((c[1] - a[1]) * (gx - c[0]) + (a[0] - c[0]) * (gy - c[1])) / den
        l2 = 1.0 - l0 - l1
        e = 1e-9
        ins = (l0 > e) & (l1 > e) & (l2 > e)            # strictly inside: a shared edge's centres count once
        cov[gy[ins].astype(int), gx[ins].astype(int)] += 1
    return int((cov > 1).sum()), cov


# ============================================================================================ X5b: the claws' seams
def exposure(C, log=print):
    """per shell, per cage vertex (module docstring, X5b): the share of EXPOSURE rays (cosine-weighted over the vertex's
    hemisphere) that escape its own side's chain (every shell and sleeve of that side at the bind) and the ground within
    EXPOSURE reach (life mm). The left-built cutter reads the right chain's exact mirrors (cheliped_propodus_R /
    cheliped_dactyl_R: the same vertex ids). Warp on whatever device it was initialised on (x05: the CPU)"""
    import warp as wp

    @wp.kernel
    def k_expo(mesh: wp.uint64, P: wp.array(dtype=wp.vec3), N: wp.array(dtype=wp.vec3), D: wp.array(dtype=wp.vec3),
               nd: int, maxd: float, ground: float, lift: float, out: wp.array(dtype=float)):
        i = wp.tid()
        p = P[i]
        n = N[i]
        a = wp.vec3(1.0, 0.0, 0.0)
        if wp.abs(n[0]) > 0.9:
            a = wp.vec3(0.0, 1.0, 0.0)
        t = wp.normalize(wp.cross(n, a))
        b = wp.cross(n, t)
        free = float(0.0)
        o = p + n * lift
        for k in range(nd):
            d = D[k]
            w = t * d[0] + b * d[1] + n * d[2]
            q = wp.mesh_query_ray(mesh, o, w, maxd)
            hit = q.result
            if (not hit) and w[1] < 0.0:
                if (o[1] - ground) / (-w[1]) < maxd:
                    hit = True
            if not hit:
                free = free + 1.0
        out[i] = free / float(nd)
    ne = int(EXPOSURE['rays'])
    k = np.arange(ne) + 0.5
    r = np.sqrt(k / ne)
    ph = k * np.pi * (3.0 - np.sqrt(5.0))
    D = np.stack([r * np.cos(ph), r * np.sin(ph), np.sqrt(1.0 - r * r)], 1).astype(np.float32)
    out = {}
    for side in ('L', 'R'):
        names = [nm for nm in C if nm.endswith('_' + side) and 'cutter' not in nm]
        Vs, Fs, off = [], [], 0
        for nm in names:
            T, _ = BU.tris_of(C[nm]['Q'], C[nm]['V'])
            Vs.append(C[nm]['V'])
            Fs.append(T + off)
            off += len(C[nm]['V'])
        mesh = wp.Mesh(points=wp.array(np.concatenate(Vs).astype(np.float32), dtype=wp.vec3),
                       indices=wp.array(np.concatenate(Fs).astype(np.int32).ravel(), dtype=wp.int32))
        for nm in names:
            V, Q = C[nm]['V'], C[nm]['Q']
            fn, fa = BU.quad_normals(V, Q)
            vn = np.zeros_like(V)
            for j in range(4):
                np.add.at(vn, Q[:, j], fn * fa[:, None])
            vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)
            o = wp.zeros(len(V), dtype=float)
            wp.launch(k_expo, dim=len(V), inputs=[mesh.id, wp.array(V.astype(np.float32), dtype=wp.vec3),
                                                  wp.array(vn.astype(np.float32), dtype=wp.vec3),
                                                  wp.array(D, dtype=wp.vec3), ne, float(EXPOSURE['reach']),
                                                  float(EXPOSURE['ground']), float(EXPOSURE['lift']), o])
            out[nm] = o.numpy().astype(np.float64)
        log(f'[lobster_uv] exposure, side {side}: {len(names)} shells, {off} vertices; ' + ', '.join(
            f'{nm} median {np.median(out[nm]):.2f}' for nm in names if nm in CLAW_SHELLS or nm in CLAW_MIRRORS))
    for nm, src in (('cheliped_propodus_cutter_L', 'cheliped_propodus_R'), ('cheliped_dactyl_cutter_L', 'cheliped_dactyl_R')):
        if src in out:
            out[nm] = out[src]
    return out


def edge_frame(V, Q):
    """the quad mesh's unique edges E, their faces ef (-1 when one), inner, the second face (0 when none), the edge's
    normal (its faces' sum, normalised) and length"""
    E, QE, ef = BU.quad_edges(Q)
    fn, fa = BU.quad_normals(V, Q)
    inner = ef[:, 1] >= 0
    f1 = np.maximum(ef[:, 1], 0)
    en = fn[ef[:, 0]] + np.where(inner[:, None], fn[f1], 0.0)
    en /= np.maximum(np.linalg.norm(en, axis=1, keepdims=True), 1e-12)
    return E, ef, inner, f1, en, np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1)


def cut_tree(V, Q, fcls, region, sharp, expo, thin=None, second=False):
    """the cut edges that open one SEEN piece into a chart (module docstring, X5b): its TERMINALS (every boundary loop;
    on an elongated piece, CUT elong, its two axial poles not inside a loop) joined by one tree of cheapest paths, the
    two poles (or the two largest terminals) first. Returns a set of (a, b) piece vertex pairs. thin (A0): the claw's
    thin axis (thin_axes); None = the world's x (the vertical fingers' plane, X5b as built). second (x6fix_x7, CLAW_SPLIT):
    also a second cheapest path between those first two terminals through none of the tree's other vertices, which
    with the first splits the piece in two"""
    import scipy.sparse as sp
    from scipy.sparse.csgraph import connected_components, dijkstra
    E, ef, inner, f1, en, L = edge_frame(V, Q)
    nt = np.abs(en[:, 0]) if thin is None else np.abs(en @ np.asarray(thin, np.float64))
    s = np.clip((nt - CUT['broad'][0]) / (CUT['broad'][1] - CUT['broad'][0]), 0.0, 1.0)
    s = s * s * (3.0 - 2.0 * s)
    h = np.asarray(HIDDEN_DIR, np.float64)
    e_ = 0.5 * (expo[E[:, 0]] + expo[E[:, 1]])
    # x6fix_x7 (11-11): a BROAD face's edge keeps its full price however occluded it is at the bind (the exposure's
    # discount floored at its broad share s): the bind's exposure 0 under the carpus read a broad face 10 x cheaper,
    # and the tree crossed the cutter palm's ventral face there, 4.3 mm in sight over the wrist's range (x05 gate 9 on
    # the A0 cage, x05 _a0g_smoke); the margins' and the gape's occluded edges stay cheap
    cost = L * (1.0 + CUT['view'] * (1.0 - en @ h)) * (1.0 + CUT['A'] * s) * np.maximum(
        CUT['expo'][0] + CUT['expo'][1] * e_ * e_, s)
    # x6fix_x7 (11-11): an edge on a cage SPINE costs CUT feature x: on the A0 fist the carpus's tree climbed its spine
    # (17 of its 57 cut vertices on it), and the cone, slit at a foot whose fillet turns more than its tip, folded its
    # chart over itself (101 texels at 1024 whatever the pins and the ARAP iterations: x05 _a0g_smoke3-5; scratch
    # x6fix_x7 probe_uv_overlap.py). (The claws' molars keep X5b's prices: their occlusal rims are the cut's way)
    reg_ = np.asarray(region)
    fe = reg_ == 'spine'
    on_f = fe[ef[:, 0]] | (inner & fe[f1])
    cost = np.where(on_f, cost * CUT['feature'], cost)
    hid = (fcls[ef[:, 0]] != 0) | (inner & (fcls[f1] != 0))
    rb = inner & (region[ef[:, 0]] != region[f1]) & ~on_f
    shs = {(min(a, b), max(a, b)) for a, b in sharp}
    cr = np.array([(int(a), int(b)) in shs for a, b in E], bool)
    cost = np.where(hid, L * CUT['hidden'], np.where(rb, cost * CUT['region'], np.where(cr, cost * CUT['crease'], cost)))
    n = len(V)
    G = sp.coo_matrix((np.r_[cost, cost], (np.r_[E[:, 0], E[:, 1]], np.r_[E[:, 1], E[:, 0]])), shape=(n, n)).tocsr()

    def path(src, dst):
        d, pred, _ = dijkstra(G, indices=np.array(sorted(src)), return_predecessors=True, min_only=True)
        dl = np.array(sorted(dst))
        t = int(dl[np.argmin(d[dl])])
        out = []
        while pred[t] >= 0:
            u = int(pred[t])
            out.append((min(u, t), max(u, t)))
            t = u
        return out, float(d[dl].min())
    loops = []
    if (~inner).any():
        be = E[~inner]
        nc, lab = connected_components(sp.coo_matrix((np.ones(len(be)), (be[:, 0], be[:, 1])), shape=(n, n)),
                                       directed=False)
        vb = np.unique(be.ravel())
        loops = [set(int(v) for v in vb[lab[vb] == k]) for k in np.unique(lab[vb])]
    terms = list(loops)
    c0, ax, el = BU.tube_axis(V)
    if el > CUT['elong']:
        t = (V - c0) @ ax
        # x6fix_x7 (11-11): the poles are the piece's own ends, never a spine's tip: on the A0 fist the carpus's spine
        # (u 0.86, leaning 35 deg distally) stands past the rest along the axis, its tip became the far pole, and the
        # first path climbed the spine to it (14 of the cut's 58 vertices; the slit cone folded the chart, 69-101 texels
        # at 1024: x05 _a0g_smoke3-6, scratch x6fix_x7 probe_uv_overlap.py)
        on_sp = np.zeros(len(V), bool)
        on_sp[np.unique(Q[np.asarray(region) == 'spine'].ravel())] = True
        t_ = np.where(on_sp, np.nan, t)
        for p in (int(np.nanargmin(t_)), int(np.nanargmax(t_))):
            if not any(p in lp for lp in loops):
                terms.append({p})
    cut = set()
    if len(terms) < 2:
        return cut
    terms = sorted(terms, key=lambda s_: -len(s_))
    poles = [s_ for s_ in terms if len(s_) == 1]
    first = poles[:2] if len(poles) >= 2 else terms[:2]
    p_, _ = path(first[0], first[1])
    cut |= set(p_)
    tree = set(first[0]) | set(first[1]) | {v for e in cut for v in e}
    rest = [s_ for s_ in terms if s_ is not first[0] and s_ is not first[1] and not (s_ & tree)]
    while rest:
        best = None
        for i, lp in enumerate(rest):
            p_, d = path(lp, tree)
            if best is None or d < best[1]:
                best = (i, d, p_)
        i, d, p_ = best
        cut |= set(p_)
        tree |= rest.pop(i) | {v for e in p_ for v in e}
        rest = [s_ for s_ in rest if not (s_ & tree)]
    if second:
        # the second path keeps AWAY from the tree: no vertex within r_b of it (geodesic, along the edges), but near the
        # two terminals it joins, r_b a quarter of the piece's girth (its area over its axial length): next to the
        # tree, the cheapest path ran beside the first and cut a strip off the fist carpus (106 of 930 quads)
        Lg = sp.coo_matrix((np.r_[L, L], (np.r_[E[:, 0], E[:, 1]], np.r_[E[:, 1], E[:, 0]])), shape=(n, n)).tocsr()
        tv = np.array(sorted({v for e in cut for v in e}), int)
        ends = np.array(sorted(set(first[0]) | set(first[1])), int)
        ax_t = (V - c0) @ ax
        area = float(np.linalg.norm(np.cross(V[Q[:, 2]] - V[Q[:, 0]], V[Q[:, 3]] - V[Q[:, 1]]), axis=1).sum()) * 0.5
        r_b = 0.25 * area / max(float(ax_t.max() - ax_t.min()), 1e-6)
        d_tree = dijkstra(Lg, indices=tv, min_only=True) if len(tv) else np.full(n, np.inf)
        d_ends = dijkstra(Lg, indices=ends, min_only=True)
        block = (d_tree < r_b) & (d_ends > r_b)
        ok = ~(block[E[:, 0]] | block[E[:, 1]])
        G2 = sp.coo_matrix((np.r_[cost[ok], cost[ok]], (np.r_[E[ok, 0], E[ok, 1]], np.r_[E[ok, 1], E[ok, 0]])),
                           shape=(n, n)).tocsr()
        d2, pred2, _ = dijkstra(G2, indices=np.array(sorted(first[0])), return_predecessors=True, min_only=True)
        dl = np.array(sorted(first[1]))
        t = int(dl[np.argmin(d2[dl])])
        if np.isfinite(d2[t]):
            while pred2[t] >= 0:
                u = int(pred2[t])
                cut.add((min(u, t), max(u, t)))
                t = u
    return cut


def unwrap_whole(Vc, Fc, iters=16):
    """one chart unwrapped whole, never split: the shared LSCM (stag_beetle_uv.lscm_direct) then ARAP (uv.arap), oriented
    as stag_beetle_uv.unwrap_chart does; a try that flips or overlaps is repeated with LSCM's two pins at the chart's
    farthest boundary pair, then at its long axis's extremes. Returns (UV mm, metrics, overlap, pins, tries)"""
    import eidoverse.bestiary.forge.uv as UVm
    Eb = np.sort(np.concatenate([Fc[:, [0, 1]], Fc[:, [1, 2]], Fc[:, [2, 0]]]), axis=1)
    u_, cnt = np.unique(Eb, axis=0, return_counts=True)
    bv = np.unique(u_[cnt == 1].ravel())
    tries = [None]
    if len(bv) >= 2:
        P = Vc[bv]
        i = int(np.argmax(np.linalg.norm(P - P.mean(0), axis=1)))
        tries.append((int(bv[i]), int(bv[int(np.argmax(np.linalg.norm(P - P[i], axis=1)))])))
    c0, ax, _ = BU.tube_axis(Vc)
    t = (Vc - c0) @ ax
    tries.append((int(np.argmin(t)), int(np.argmax(t))))

    def orient(U):
        d1, d2 = U[Fc[:, 1]] - U[Fc[:, 0]], U[Fc[:, 2]] - U[Fc[:, 0]]
        if (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]).sum() < 0:
            U[:, 0] = -U[:, 0]
        return U
    best = None
    # x6fix_x7 (11-11): every pin tried again at 3 x the ARAP iterations when no try is clean (the A0 fist carpus folded
    # 125 texels over itself at 16, x05 _a0g_smoke)
    for k, (pin, it_) in enumerate([(p_, iters) for p_ in tries] + [(p_, 3 * iters) for p_ in tries]):
        if k == len(tries) and best is not None and best[0] == (0, 0):
            break
        U = orient(UVm.arap(Vc, Fc, orient(BU.lscm_direct(Vc, Fc, pin=pin)), iters=it_))
        met = BU.chart_metrics(Vc, Fc, U)
        ov = UVm.self_overlap(U, Fc, res=1024) if met['flipped'] == 0 else -1
        bad = (met['flipped'], max(ov, 0) if ov >= 0 else 10 ** 9)
        if best is None or bad < best[0]:
            best = (bad, U, met, ov, pin, k + 1)
        if bad == (0, 0):
            break
    return best[1], best[2], best[3], best[4], best[5]


def split_charts(Vs, Qs, sh, fc, region, ex, thin, vs, name, log=print):
    """x6fix_x7 (CLAW_SPLIT's comment): one SEEN claw piece split in two by cut_tree's second path, each part unwrapped
    whole with the tree's slits that stay inside it. Returns its charts (ids as claw_charts' before its outer mapping:
    faces the piece's, orig the piece's vertex ids), or [] when the second path does not split the piece"""
    cut2 = cut_tree(Vs, Qs, fc, region, sh, ex, thin=thin, second=True)
    lab = face_components(Qs, cut2)
    if len(np.unique(lab)) < 2:
        log(f'[lobster_uv] {name}: the second path does not split the piece: kept whole')
        return []
    out, rows = [], []
    for k in np.unique(lab):
        F2 = np.nonzero(lab == k)[0]
        V2, Q2, sh2, vs2 = sub_piece(Vs, Qs, sh, F2)
        rid = -np.ones(len(Vs), np.int64)
        rid[vs2] = np.arange(len(vs2))
        e2f = {}
        for f, q in enumerate(Q2):
            for j in range(4):
                a, b = int(q[j]), int(q[(j + 1) % 4])
                e2f.setdefault((min(a, b), max(a, b)), []).append(f)
        cut_in = set()
        for a, b in cut2:                               # (the slits inside this part: an edge it holds on both sides)
            ra, rb = int(rid[a]), int(rid[b])
            if ra >= 0 and rb >= 0 and len(e2f.get((min(ra, rb), max(ra, rb)), ())) == 2:
                cut_in.add((min(ra, rb), max(ra, rb)))
        Vc, Fc, orig, Qc, fq = BU._sub(V2, Q2, np.arange(len(Q2)), cut_in)
        U, met, ov, pin, ntry = unwrap_whole(Vc, Fc)
        out.append(dict(faces=F2, Vc=Vc, Fc=Fc, orig=vs2[orig], Qc=Qc, uv=U, metrics=met, overlap=ov, cls=0, tube=True,
                        claw=True, cut={(int(vs[vs2[a]]), int(vs[vs2[b]])) for a, b in cut_in}, tries=ntry, split=True))
        rows.append(f'{len(F2)} quads p95 {met["aniso95"]:.3f}, scale {met["s10"]:.3f} / {met["s90"]:.3f}, flipped '
                    f'{met["flipped"]}, overlap {ov}')
    new = cut2 - cut_tree(Vs, Qs, fc, region, sh, ex, thin=thin)
    log(f'[lobster_uv] {name}: SPLIT (CLAW_SPLIT) by a second path of {len(new)} edges '
        f'({sum(float(np.linalg.norm(Vs[a] - Vs[b])) for a, b in new):.0f} mm): ' + '; '.join(rows))
    return out


def claw_charts(c, seen_extra, expo, log=print, thin=None):
    """one claw shell's charts (module docstring, X5b): its hidden faces cut off on their class line and charted by the
    shared unwrap_master (the hidden share); X3's ring loops kept; each seen piece opened by cut_tree and unwrapped whole
    (unwrap_whole). Charts as shell_charts returns them (GLOBAL faces and orig), plus the cut (the shell's vertex pairs).
    thin (A0): the claw's thin axis for cut_tree's broad cost (thin_axes)"""
    V, Q = c['V'], c['Q']
    fcls = np.where(c['hidden'], 2, 0)
    if seen_extra:
        fcls[np.array(sorted(seen_extra), int)] = 0
    E, ef, inner, f1, en, L = edge_frame(V, Q)
    clsb = {(int(a), int(b)) for (a, b) in E[inner & (fcls[ef[:, 0]] != fcls[f1])]}
    lab = face_components(Q, ring_seams(c) | clsb)
    out = []
    for Lb in np.unique(lab):
        fs = np.nonzero(lab == Lb)[0]
        Vs, Qs, sh, vs = sub_piece(V, Q, list(c['sharp']), fs)
        if (fcls[fs] != 0).all():
            ch = BU.unwrap_master(Vs, Qs, sh, fcls[fs], HIDDEN_DIR, log=lambda s_: None, name=f'{c["name"]}#{Lb}')
        else:
            cut = cut_tree(Vs, Qs, fcls[fs], c['region'][fs], sh, expo[vs], thin=thin)
            Vc, Fc, orig, Qc, fq = BU._sub(Vs, Qs, np.arange(len(Qs)), cut)
            U, met, ov, pin, ntry = unwrap_whole(Vc, Fc)
            ch = [dict(faces=np.arange(len(Qs)), Vc=Vc, Fc=Fc, orig=orig, Qc=Qc, uv=U, metrics=met, overlap=ov, cls=0,
                       tube=True, claw=True, cut={(int(vs[a]), int(vs[b])) for a, b in cut}, tries=ntry)]
            log(f'[lobster_uv] {c["name"]}#{Lb}: a seen piece of {len(fs)} quads, ONE chart: the cut {len(cut)} edges '
                f'({sum(float(np.linalg.norm(Vs[a] - Vs[b])) for a, b in cut):.0f} mm), anisotropy p95 '
                f'{met["aniso95"]:.3f}, scale p10 / p90 {met["s10"]:.3f} / {met["s90"]:.3f}, flipped {met["flipped"]}, '
                f'overlap {ov} (unwrap try {ntry})')
            if met['aniso95'] > CLAW_SPLIT or ov != 0:
                ch2 = split_charts(Vs, Qs, sh, fcls[fs], c['region'][fs], expo[vs], thin, vs, f'{c["name"]}#{Lb}', log)
                # (kept only when it helps: every part 0.05 under the whole's p95, none folded or flipped; on the fist
                # carpus the second path ran beside the first and cut a strip off, p95 1.267 against 1.269)
                if ch2 and all(y['metrics']['aniso95'] <= met['aniso95'] - 0.05 and y['overlap'] == 0 and
                               y['metrics']['flipped'] == 0 for y in ch2):
                    ch = ch2
                elif ch2:
                    log(f'[lobster_uv] {c["name"]}#{Lb}: the split did not help: kept whole')
        for x in ch:
            x['faces'] = fs[x['faces']]
            x['orig'] = vs[x['orig']]
            x['shell'] = c['name']
        out += ch
    return out


def mirror_charts(charts, c):
    """the charts of a shell that is another's exact mirror (V = M V_p, the quads reversed, the ids kept: x04's right
    carpus) as the primary's charts mirrored: the same faces and cuts, the split quads reversed, the positions mirrored,
    u negated (each triangle keeps its winding in UV). Its own texels (the copy is not stacked)"""
    out = []
    for x in charts:
        y = dict(x)
        y['Qc'] = np.asarray(x['Qc'])[:, ::-1].copy()
        y['Vc'] = np.asarray(x['Vc']) * M_X
        y['Fc'], _ = BU.tris_of(y['Qc'], y['Vc'])
        y['uv'] = np.asarray(x['uv']) * np.array([-1.0, 1.0])
        assert np.array_equal(np.asarray(x['orig'])[y['Qc']], c['Q'][x['faces']]), f'{c["name"]}: not the mirror\'s quads'
        y['shell'] = c['name']
        y['mirror_of'] = x['shell']
        out.append(y)
    return out


def true_seams(c, charts):
    """per edge of the shell (edge_frame's order): a UV seam? Two faces in different charts, or in one chart whose split
    copies of the edge's corners differ (a slit: unwrap_master's tube meridian, cut_tree's paths). A sleeve strip is
    skipped (its own quads)"""
    Q = c['Q']
    S = -np.ones(Q.shape, np.int64)
    lab = -np.ones(len(Q), np.int64)
    off = 0
    for k, x in enumerate(charts):
        if x.get('strip'):
            continue
        Qc = np.asarray(x['Qc'])
        assert np.array_equal(np.asarray(x['orig'])[Qc], Q[x['faces']]), 'chart quads not in their faces\' order'
        S[x['faces']] = Qc + off
        lab[x['faces']] = k
        off += int(Qc.max()) + 1
    E, ef, inner, f1, en, L = edge_frame(c['V'], Q)

    def corner(f, v):
        return S[f, np.argmax(Q[f] == v[:, None], axis=1)]
    f0 = ef[:, 0]
    seam = inner & ((lab[f0] != lab[f1]) | (corner(f0, E[:, 0]) != corner(f1, E[:, 0])) |
                    (corner(f0, E[:, 1]) != corner(f1, E[:, 1])))
    return seam, (E, ef, inner, f1, en, L)


def seam_report(c, charts, seen_extra, expo=None, thin=None):
    """the shell's UV seams by where they run (life mm): 'ring' X3's ring loops; 'joint' against a hidden face (no one sees
    one side); between two SEEN faces: 'broad' on a broad face (|n_x| > BROAD_NX: x05 gate 9, target 0; A0: |n . thin|
    when the claw's thin axis is given, thin_axes), 'ventral' (n_y < -0.5), 'occluded' (exposure under 0.35), 'margin'
    the rest. Returns (lengths, the broad edges' rows)"""
    seam, (E, ef, inner, f1, en, L) = true_seams(c, charts)
    fcls = np.where(c['hidden'], 2, 0)
    if seen_extra:
        fcls[np.array(sorted(seen_extra), int)] = 0
    ring = ring_seams(c)
    isr = np.array([(int(a), int(b)) in ring for a, b in E], bool)
    both = (fcls[ef[:, 0]] == 0) & (fcls[f1] == 0)
    broad = (np.abs(en[:, 0]) if thin is None else np.abs(en @ np.asarray(thin, np.float64))) > BROAD_NX
    ex = 0.5 * (expo[E[:, 0]] + expo[E[:, 1]]) if expo is not None else np.ones(len(E))
    m = dict(ring=seam & isr, joint=seam & ~isr & ~both)
    s2 = seam & ~isr & both
    m['broad'] = s2 & broad
    m['ventral'] = s2 & ~broad & (en[:, 1] < -0.5)
    m['occluded'] = s2 & ~broad & ~m['ventral'] & (ex < 0.35)
    m['margin'] = s2 & ~broad & ~m['ventral'] & ~m['occluded']
    lens = {k: float(L[v].sum()) for k, v in m.items()}
    rows = [dict(edge=E[e].tolist(), mm=float(L[e]), n=np.round(en[e], 2).tolist(),
                 at=np.round(c['V'][E[e]].mean(0), 1).tolist(),
                 regions=[str(c['region'][ef[e, 0]]), str(c['region'][f1[e]])], exposure=float(ex[e]))
            for e in np.nonzero(m['broad'])[0]]
    return lens, rows

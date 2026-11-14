"""CARDS from the groom (HAIR_STUDY §9.3, §9.4; WOLF_PLAN §5.4): one card per clump, layered, ranked for LOD.

  spine     the clump's guide (grown from its clump centre: the strands of the clump are pulled toward it), cut or
            extended to the card's length = the members' length quantile (style: cards.length_q, 0.85)
  rows      by length (style: cards.rows [[max_mm, rows], ...]: one quad under ~1.5 cm, as a shipped game's shingles (study T); rows every
            ~1-1.5 cm on long hair); rows sit at equal arc length
  frame     T the spine's tangent; B = N x T with N the skin's normal under the row (the card lies IN the coat surface,
            a shingle, never an upright blade: SPECIMEN found blades a light trap); the root's own skin normal goes to
            the ABI's NORMAL
  width     per row, 2 x the members' |offset . B| quantile (cards.width_q 0.8) near that row, clamped and tapered
            (cards.width: min_mm, max_mm, tip_scale)
  layer     the card's mid height above the skin over its length, by quantile: inner -> dense tiles, outer -> sparse;
            a share of the outermost take the wisp row (study T's flyaway band)
  tile      density class (layer) x width class (the style's card widths split at quantiles, so each card takes a
            tile whose physical width matches its own and strands keep their drawn thickness) x variant (hash)
  ranks     NESTED Poisson thinning over the clump centres (radius alpha_f / sqrt(local card density), alpha_f found by
            bisection for each LOD fraction, priority = hash x a length bias so long cards survive), rank r = the
            coarsest LOD that still draws the card (0 = drawn at every card LOD); cards sorted by (set, rank)
  prefix    per primitive (texture set), the index count drawn at each LOD: draw range [0, prefix[lod]]

Coat round 2 (10-30):
  lie down  (the first pass's standing crest) every row segment of a spine is held at or under the style's own lift at
            that point of the strand: elevation over the skin under the segment's middle <= 90 - theta(t) + jitter, theta
            the growth's angle from the normal (strands.k_grow: lift.root_deg -> lift.tip_deg by lift.pow, plus the guide
            class's own lift); a steeper segment turns down about the card's width axis toward the flow, its length kept,
            the rows past it carried along, then every row is pushed out of the skin. Gated: the cards still outside
            the range are counted (Cards.lie_gate)
  root mip  (the oral web's grey cards) the explicit mip of the one root lookup (_ROOTDATA.z) is the card's footprint
            capped so its trilinear footprint stays inside the root's uv island: the octopus's albedo islands sit on an
            unpadded grey, and a seam-side root read it (Cards.root_mips)
  snap      root-row vertices go to the TRUE closest skin point (+ 0.5 mm along its normal) when further than 1 mm
            from it (the first pass moved them along one face's normal, which can leave a vertex beside a thin edge
            several mm away), and the root row's _FURCENTER follows the row (its midpoint)

Coat round 3 (10-30): THE OVERHANG (round 2's shaggy: 1,805 of 7,858 cards had some part over bare skin, the oral web's
pale paper cards; the root fade could not find them, their roots being deep in the coat). Every card is sampled where
the coat could leave it: each row's spine point and both edges, and the same at each segment's middle; each sample's
closest skin point reads the style's own coat mask (domain x not bare, the field the roots were drawn from):
  edge trim   a card whose spine reaches skin under the mask cut ends before it: its length cut at the crossing less a
              margin, its spine resampled along itself, its rows recounted (the groom's guard and trim make this rare;
              a card's spine can still be extended past its trimmed guide, resample() goes straight on)
  edge narrow a row whose edge (or a segment's middle edge) lies over bare skin is narrowed until it does not, the
              taper rule kept (the arm's flanks curve away under a wide flat card)
  overshoot   the mask says where a coat may grow, the coat pack's density where it really lies, and on a feathered hem they
              part: with the baked density (Cards.set_density) a card may lie cards.overshoot_mm past the last of the pelt
              under it (a hem's hairs do) and no further (the g4 check's overhang.py reads the density)
  gate        Cards.overhang_gate: cards with any sample over bare skin, on the spine, at the tip, under 0.3 (thin
              coat), before and after; the height of what is left over bare skin; its 'density' block: tips over thin coat,
              how far past the pelt, how high

Coat round 3: EDGE FINS (style cards.kind "fins": Cards.fit_fins, classify_fins, rank_all): a short pile's outline is not
shingles from the groom (one card per clump leaves ~1 card per cm of outline on a 1 cm arm: round 2's thorns) but true fins
(Lengyel, Praun, Finkelstein & Hoppe 2001), one on every coated edge of the low: a polygon silhouette runs along edges, so the
silhouette's fins always stand along the outline and face the camera, a continuous rim at any view. The groom gives each end
its height and its lean. Two things a fin does differently from a card, both load-bearing: its two ENDS carry their own skin
weights (a fin follows its skin edge exactly), and so its _FURCENTER is each vertex's own root corner, not the row's middle.
The runtime collapses a face-on card onto _FURCENTER, and three r184 runs the material's positionNode BEFORE skinning (read
from the compiled WGSL, g5_groom/scratch/shader/all_1.wgsl): a shared centre, skinned by two different weight sets, keeps an
area and is flung off a bent arm; folded onto its own corners a fin has zero area wherever it lands, whichever ends collapse.

B3 (11-07, HAIR_FUR H5): HAIR CARDS (Cards.fit_hair; style cards.kind "hair"). Hair hangs off the head, so a card is not
a shingle in the coat surface:
  rows      by CURVATURE along the guide (one row per cards.row_mm [min, max] of arc, an extra row wherever the spine
            turns cards.turn_deg since the last): long straight runs take few rows, the bend over the skull and the
            tucked end take many (study T's long strips: rows every ~1 cm, more in bends)
  frame     T the spine's tangent, N the SDF's gradient (outward from head + neck + shoulders: the hair shell's
            normal), B = N x T: a card lies IN the hair's shell at every row, the way study T's bob cards lie
  kinds     "strip" (2 vertices across), "vfold" (3 across, the middle raised along N by vfold x width: a bent card's
            volume, two study-T short hair styles), "ribbon" (a strip twisted about T by twist_turns over its length: the
            twisted ponytail / braid / loc strips); per group (cards.groups.<name> over cards)
  normal    "shell": each vertex's NORMAL is its row's N (the hair volume's own normal, the proxy-shell normal games light
            hair cards with), not the root's skin normal (a bob's ends hang 20 cm from their roots' scalp)
  budget    cards.budget_tris: the LOD0 triangles; over it, the finest Poisson ranks are thinned until it fits (the count
            follows the budget, HAIR_FUR §1.2's 28k +- 5k)
  gates     roots within cards.root_gate_mm of the scalp (study T p50 0.33 cm; ours: the snapped root row), triangles

What the ABI writer needs comes out as flat per-vertex arrays (Cards.vertex_arrays).
"""
import json

import numpy as np

from .fields import Fields, Pts
from .roots import hkey, poisson_keep
from . import strands as ST


def island_edge_texels(base, uv, sets, min_in=2.5):
    """texels from each uv (in its set, at that set's albedo resolution) to the nearest texel outside its uv island,
    and the uv to read the root's maps at: unchanged, unless it lies within min_in texels of the island's edge (a
    bilinear lookup there already reads the unpadded background), then the centre of the nearest texel min_in deep
    (a nudge of a texel or two: ~0.3-0.8 mm on the octopus)"""
    from scipy import ndimage
    from .coatmaps import uv_gbuffer
    out = np.zeros(len(uv))
    uv_new = np.array(uv, np.float64, copy=True)
    for k, s in enumerate(base.sets):
        m = sets == k
        if not m.any():
            continue
        R = int(base.tex(s, 'base').shape[0])
        tri, _ = uv_gbuffer(base, k, R, 'cpu')
        dist = ndimage.distance_transform_edt(tri >= 0)
        xi = np.clip((uv[m, 0] * R).astype(np.int64), 0, R - 1)
        yi = np.clip((uv[m, 1] * R).astype(np.int64), 0, R - 1)
        out[m] = dist[yi, xi]
        shallow = dist[yi, xi] < min_in
        if shallow.any():
            _, (iy, ix) = ndimage.distance_transform_edt(dist < min_in, return_indices=True)
            ii = np.nonzero(m)[0][shallow]
            ny, nx = iy[yi[shallow], xi[shallow]], ix[yi[shallow], xi[shallow]]
            uv_new[ii, 0] = (nx + 0.5) / R
            uv_new[ii, 1] = (ny + 0.5) / R
            out[ii] = dist[ny, nx]
    return out, uv_new


def resample(P, L, n):
    """a polyline (K, 3) of arc length ~L resampled to n points at equal arc length over [0, L] (extended linearly
    past its end along its last segment)"""
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    t = np.linspace(0, L, n)
    out = np.empty((n, 3))
    for d in range(3):
        out[:, d] = np.interp(t, s, P[:, d])
    over = t > s[-1]
    if over.any():
        tail = P[-1] - P[-2]
        tail /= max(np.linalg.norm(tail), 1e-12)
        out[over] = P[-1] + np.outer(t[over] - s[-1], tail)
    return out


class Cards:
    def __init__(self, groom_npz, base, surf, style):
        self.z = groom_npz
        self.base = base
        self.surf = surf
        self.style = style
        self.cs = style.get('cards', {})
        self.fields = Fields(base, style.get('fields', {}))
        self.mask_cut = float(style.get('mask_cut', 0.12))
        self.density = None
        self.sdf = None                                      # (B3) the groom's SDF, for hair cards' frames

    def set_density(self, maps):
        """(coat round 3) the baked coat's density, {set name: (h, w) on that set's uv}: the coat pack's R, the coat as it
        really lies (the mask says where a coat may grow; on a feathered hem the mask is still over its cut where the strands
        have thinned to nothing). With it fit() trims a card's overshoot and the gate reads it"""
        self.density = maps
        return self

    def coat_density(self, X):
        """the baked coat density at the closest skin point of each point"""
        X = np.asarray(X, np.float64).reshape(-1, 3)
        face, bary, _ = ST.query(self.surf, X)
        b = self.base
        uv = np.sum(b.UV[b.F[face]] * bary[..., None], 1)
        fs = b.face_set[face]
        out = np.zeros(len(X))
        for k, s in enumerate(b.sets):
            m = fs == k
            if m.any():
                d = self.density[s]
                h, w = d.shape[:2]
                out[m] = d[np.clip((uv[m, 1] * h).astype(np.int64), 0, h - 1),
                           np.clip((uv[m, 0] * w).astype(np.int64), 0, w - 1)]
        return out

    def coat_mask(self, X):
        """(coat round 3) the style's coat mask (domain x not bare) at the closest skin point of each point, and the
        point's signed height over that skin"""
        X = np.asarray(X, np.float64).reshape(-1, 3)
        if len(X) == 0:
            return np.zeros(0), np.zeros(0)
        face, bary, h = ST.query(self.surf, X)
        mexp = {'mul': [self.style.get('domain', 1.0), {'not': self.style.get('bare', 0.0)}]}
        return np.clip(self.fields.eval(mexp, Pts(self.base, face, bary)), 0.0, 1.0), h

    def bare_depth(self, X):
        """(coat round 3) how far into the bare zone each point's closest skin point lies, in mm over the skin (0 where
        the coat mask is at or over the cut), with the mask and the point's height over the skin"""
        X = np.asarray(X, np.float64).reshape(-1, 3)
        if len(X) == 0:
            return np.zeros(0), np.zeros(0), np.zeros(0)
        face, bary, h = ST.query(self.surf, X)
        mexp = {'mul': [self.style.get('domain', 1.0), {'not': self.style.get('bare', 0.0)}]}
        pts = Pts(self.base, face, bary)
        m = np.clip(self.fields.eval(mexp, pts), 0.0, 1.0)
        d_w, _ = self.fields.edge_distance_w({'not': mexp}, 1.0 - self.mask_cut)   # distance to where mask > cut
        dv = d_w[self.base.wid]
        depth = pts.vblend(np.where(np.isfinite(dv), dv, 1.0)) * 1e3
        return np.where(m >= self.mask_cut, 0.0, depth), m, h

    def fit(self, log=print):
        z, b, cs = self.z, self.base, self.cs
        P = z['points'].astype(np.float64)
        S, K = P.shape[:2]
        G = z['guides'].astype(np.float64)
        C = len(G)
        cid = z['clump'].astype(np.int64)
        Ls = z['length'].astype(np.float64)
        order = np.argsort(cid, kind='stable')
        starts = np.searchsorted(cid[order], np.arange(C + 1))
        lq = cs.get('length_q', 0.85)
        rows_tab = cs.get('rows', [[15, 2], [32, 3], [1e9, 4]])
        wcfg = cs.get('width', {})
        wmin, wmax = wcfg.get('min_mm', 2.0) * 1e-3, wcfg.get('max_mm', 18.0) * 1e-3
        tip_scale = wcfg.get('tip_scale', 0.45)
        wq = cs.get('width_q', 0.8)
        spines, widths, nrows, Lc, members = [], [], [], [], []
        keep = []
        # (coat round 3) a clump whose members the groom's trim cut to stubs at the coat's edge emits no card (its strands
        # still feed the coat maps): the same floor as the card-level edge trim
        min_card = float(cs.get('edge_min_mm', 0.0)) * 1e-3 if cs.get('edge_trim', True) else 0.0
        self.stub_clumps = 0
        for c in range(C):
            m = order[starts[c]:starts[c + 1]]
            if len(m) == 0:
                continue
            L = float(np.quantile(Ls[m], lq))
            if L < min_card:
                self.stub_clumps += 1
                continue
            nr = next(r for lim, r in rows_tab if L * 1e3 <= lim)
            sp = resample(G[c], L, nr)
            keep.append(c)
            spines.append(sp)
            nrows.append(nr)
            Lc.append(L)
            members.append(m)
        # LIE DOWN (coat round 2): no row segment steeper over the skin than the style's own lift at that point
        if self.style.get('lift') is not None and cs.get('lie_down', True):
            self._lie_down(spines, log)
        # (coat round 3) THE OVERHANG, the density: a card may lie a little past the last of the pelt under it, as a hem's
        # hairs do, and no further (first: the trim below has the last word over bare skin, a resampled spine can reach it)
        over_before, over_dropped = None, 0
        if self.density is not None and cs.get('overshoot_mm') is not None:
            over_before, drop = self._overshoot_trim(spines, nrows, Lc, rows_tab)
            if drop.any():
                keep = [c for c, d in zip(keep, drop) if not d]
                spines = [s for s, d in zip(spines, drop) if not d]
                nrows = [r for r, d in zip(nrows, drop) if not d]
                Lc = [x for x, d in zip(Lc, drop) if not d]
                members = [mm for mm, d in zip(members, drop) if not d]
                over_dropped = int(drop.sum())
        # (coat round 3) THE OVERHANG, the spine: a card whose spine reaches bare skin ends before it (a card that
        # would be shorter than edge_min_mm is dropped: its strands still feed the coat maps)
        spine_before, dropped = None, 0
        if cs.get('edge_trim', True):
            spine_before, drop = self._edge_trim(spines, nrows, Lc, rows_tab, log)
            if drop.any():
                keep = [c for c, d in zip(keep, drop) if not d]
                spines = [s for s, d in zip(spines, drop) if not d]
                nrows = [r for r, d in zip(nrows, drop) if not d]
                Lc = [x for x, d in zip(Lc, drop) if not d]
                members = [mm for mm, d in zip(members, drop) if not d]
                dropped = int(drop.sum())
        self.keep = np.array(keep, np.int64)
        n = len(keep)
        # frames: the skin normal under every spine point (closest point on the welded low)
        allsp = np.concatenate(spines)
        Nn = self._normals_at(allsp)
        off = np.concatenate([[0], np.cumsum(nrows)])
        frames, ws = [], []
        for i in range(n):
            sp = spines[i]
            nr = nrows[i]
            Nr = Nn[off[i]:off[i + 1]]
            T = np.gradient(sp, axis=0)
            T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
            B = np.cross(Nr, T)
            bl = np.linalg.norm(B, axis=1, keepdims=True)
            B = np.where(bl > 1e-6, B / np.maximum(bl, 1e-12), np.cross([0.0, 1.0, 0.0], T))
            B /= np.maximum(np.linalg.norm(B, axis=1, keepdims=True), 1e-12)
            # members' spread across B, row by row (each member point at its own arc fraction of the card)
            m = members[i]
            Q = P[m]                                                     # (M, K, 3)
            tk = np.linspace(0, 1, K)[None, :] * (Ls[m][:, None] / Lc[i])  # arc fraction along the card
            tr = np.linspace(0, 1, nr)
            w = np.zeros(nr)
            for r in range(nr):
                lo = tr[r] - 0.5 / max(nr - 1, 1)
                hi = tr[r] + 0.5 / max(nr - 1, 1)
                sel = (tk >= lo) & (tk <= hi)
                if sel.any():
                    d = (Q[sel] - sp[r]) @ B[r]
                    w[r] = 2.0 * np.quantile(np.abs(d), wq) if len(d) > 1 else 0.0
            # the card spans its members plus a margin (the tile squeezes them inside, cards.width.scale); taper: never
            # wider toward the tip than the root, never under tip_scale x the root at the tip
            w *= wcfg.get('scale', 1.15)
            w[0] = np.clip(w[0], wmin, wmax)
            for r in range(1, nr):
                w[r] = np.clip(w[r], w[0] * tip_scale, w[r - 1])
            frames.append((T, B, Nr))
            ws.append(w)
        # (coat round 3) THE OVERHANG, the edges: rows whose edges lie over bare skin narrowed until they do not; a card
        # whose edge still reaches further into the bare zone than the tolerance at the narrowing's floor is dropped (a
        # small card at the coat's thin edge: the coat maps carry that spot)
        narrowed = self._edge_narrow(spines, frames, ws, wmin) if cs.get('edge_narrow', True) else 0
        edge_dropped = 0
        if cs.get('edge_narrow', True):
            tol = float(cs.get('overhang_tol_mm', 1.0))
            Xe, own_e, _, _ = self._edge_samples(spines, frames, ws)
            de, _m, _h = self.bare_depth(Xe)
            deep = np.zeros(len(spines))
            np.maximum.at(deep, own_e, de)
            gone = deep > tol
            if gone.any():
                keep = [c for c, d in zip(keep, gone) if not d]
                spines = [s for s, d in zip(spines, gone) if not d]
                frames = [s for s, d in zip(frames, gone) if not d]
                ws = [s for s, d in zip(ws, gone) if not d]
                nrows = [s for s, d in zip(nrows, gone) if not d]
                Lc = [s for s, d in zip(Lc, gone) if not d]
                members = [s for s, d in zip(members, gone) if not d]
                self.keep = np.array(keep, np.int64)
                n = len(keep)
                edge_dropped = int(gone.sum())
        self.overhang_gate = self._overhang_gate(spines, frames, ws)
        self.overhang_gate.update(spine_over_bare_before_trim=spine_before, cards_dropped=dropped,
                                  cards_dropped_at_the_edge=edge_dropped, stub_clumps_no_card=int(self.stub_clumps),
                                  rows_narrowed=int(narrowed))
        if self.density is not None and cs.get('overshoot_mm') is not None:
            self.overhang_gate['density'] = self._density_gate(spines, over_before, over_dropped)
            self.overhang_gate['ok'] = bool(self.overhang_gate['ok'] and self.overhang_gate['density']['ok'])
        log(f'[cards] overhang: {json.dumps(self.overhang_gate)}')
        self.spines, self.frames, self.widths, self.nrows, self.Lc = spines, frames, ws, np.array(nrows), np.array(Lc)
        self.members = members
        self.root_w = np.array([w[0] for w in ws])
        # the root: the clump centre on the skin (tri, bary), its skin normal, uv, set, weights
        ctri, cbary = z['ctri'][self.keep].astype(np.int64), z['cbary'][self.keep].astype(np.float64)
        self.rP, self.rN, self.rUV, self.rset = b.tri_points(ctri, cbary)
        self.rJ, self.rW = b.tri_weights(ctri, cbary)
        self.ctri, self.cbary = ctri, cbary
        self.rnd = z['grnd'][self.keep].astype(np.float64)
        self.cslot = z['cslot'][self.keep].astype(np.int64)
        # mid height over length (the layer measure)
        mids = np.array([s[len(s) // 2] for s in spines])
        H, _ = self._heights(mids)
        self.h_rel = H / np.maximum(self.Lc, 1e-9)
        log(f'[cards] {n} cards from {C} clumps; rows {np.bincount(self.nrows)[2:].tolist()} (2, 3, 4...); root width mm '
            f'p10/50/90 {np.round(np.percentile(self.root_w * 1e3, [10, 50, 90]), 2).tolist()}; length mm '
            f'{np.round(np.percentile(self.Lc * 1e3, [10, 50, 90]), 1).tolist()}')
        return self

    # ---------------------------------------------------------------------------------------------- (B3) hair cards
    @staticmethod
    def rows_by_curvature(sp_fine, row_min, row_max, turn_deg):
        """indices into a fine polyline where a card's rows go: the root, then a row whenever the arc since the last
        reaches row_max, or the spine has turned turn_deg since the last and the arc is at least row_min; the tip"""
        seg = np.linalg.norm(np.diff(sp_fine, axis=0), axis=1)
        D = np.diff(sp_fine, axis=0)
        D /= np.maximum(np.linalg.norm(D, axis=1, keepdims=True), 1e-12)
        idx = [0]
        acc, d0 = 0.0, D[0]
        for k in range(1, len(sp_fine) - 1):
            acc += seg[k - 1]
            turn = np.degrees(np.arccos(np.clip(float(D[min(k, len(D) - 1)] @ d0), -1.0, 1.0)))
            if acc >= row_max or (acc >= row_min and turn >= turn_deg):
                idx.append(k)
                acc = 0.0
                d0 = D[min(k, len(D) - 1)]
        last = len(sp_fine) - 1
        if acc + seg[-1] < 0.5 * row_min and len(idx) > 1:
            idx[-1] = last                                 # a stub of a last segment merges into the one before
        else:
            idx.append(last)
        return np.array(idx)

    def fit_hair(self, log=print):
        """(B3) hair cards (the module doc's B3 block): one card per clump, rows by curvature, the frame in the hair
        shell (the SDF's gradient), strip / vfold / ribbon per group, widths from the members, the budget"""
        z, b, cs = self.z, self.base, self.cs
        sdf = self.sdf
        P = z['points'].astype(np.float64)
        S, K = P.shape[:2]
        G = z['guides'].astype(np.float64)
        C = len(G)
        cid = z['clump'].astype(np.int64)
        Ls = z['length'].astype(np.float64)
        cgroup = z['cgroup'].astype(np.int64) if 'cgroup' in z else np.zeros(C, np.int64)
        gnames = json.loads(str(z['groups'])) if 'groups' in z else ['coat']
        order = np.argsort(cid, kind='stable')
        starts = np.searchsorted(cid[order], np.arange(C + 1))

        def gc(gi):
            return dict(cs, **cs.get('groups', {}).get(gnames[gi], {}))
        spines, nrows, Lc, members, keep, kinds = [], [], [], [], [], []
        for c in range(C):
            m = order[starts[c]:starts[c + 1]]
            if len(m) == 0:
                continue
            g = gc(cgroup[c])
            L = float(np.quantile(Ls[m], g.get('length_q', 0.8)))
            # (c03) a hair card never runs past its own guide (resample extends a spine straight on along its last
            # segment: a guide cut at the jaw with members a little longer shot its card forward past the face)
            gl = float(np.linalg.norm(np.diff(G[c], axis=0), axis=1).sum())
            L = min(L, gl)
            if L < g.get('min_mm', 8.0) * 1e-3:
                continue
            fine = resample(G[c], L, 96)
            rmin, rmax = g.get('row_mm', [6.0, 16.0])
            ii = self.rows_by_curvature(fine, rmin * 1e-3, rmax * 1e-3, g.get('turn_deg', 12.0))
            sp = fine[ii]
            keep.append(c)
            spines.append(sp)
            nrows.append(len(sp))
            Lc.append(L)
            members.append(m)
            kinds.append(g.get('kind_card', 'strip'))
        self.keep = np.array(keep, np.int64)
        n = len(keep)
        allsp = np.concatenate(spines)
        if sdf is not None:
            Nn = self._sdf_normals(allsp)
        else:
            Nn = self._normals_at(allsp)
        off = np.concatenate([[0], np.cumsum(nrows)])
        frames, ws, across, folds = [], [], [], []
        for i in range(n):
            sp = spines[i]
            nr = nrows[i]
            g = gc(cgroup[keep[i]])
            Nr = Nn[off[i]:off[i + 1]].copy()
            T = np.gradient(sp, axis=0)
            T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
            Nr -= T * np.sum(Nr * T, 1, keepdims=True)
            Nr /= np.maximum(np.linalg.norm(Nr, axis=1, keepdims=True), 1e-12)
            B = np.cross(Nr, T)
            B /= np.maximum(np.linalg.norm(B, axis=1, keepdims=True), 1e-12)
            if kinds[i] == 'ribbon':
                tw = 2.0 * np.pi * float(g.get('twist_turns', 1.0)) * np.linspace(0.0, 1.0, nr)
                B, Nr = (B * np.cos(tw)[:, None] + Nr * np.sin(tw)[:, None],
                         -B * np.sin(tw)[:, None] + Nr * np.cos(tw)[:, None])
            m = members[i]
            Q = P[m]
            tk = np.linspace(0, 1, K)[None, :] * (Ls[m][:, None] / Lc[i])
            arc = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(sp, axis=0), axis=1))])
            tr = arc / max(arc[-1], 1e-12)
            w = np.zeros(nr)
            for r in range(nr):
                lo = tr[max(r - 1, 0)] if r else 0.0
                hi = tr[min(r + 1, nr - 1)]
                sel = (tk >= lo) & (tk <= hi)
                if sel.any():
                    d = (Q[sel] - sp[r]) @ B[r]
                    w[r] = 2.0 * np.quantile(np.abs(d), g.get('width_q', 0.8)) if len(d) > 1 else 0.0
            wc = g.get('width', {})
            wmin, wmax = wc.get('min_mm', 6.0) * 1e-3, wc.get('max_mm', 30.0) * 1e-3
            w *= wc.get('scale', 1.15)
            # a hair card widens from its root as its members spread, to a max, then narrows to the tip by tip_scale
            w = np.clip(w, wmin * wc.get('root_scale', 0.6), wmax)
            w[0] = np.clip(w[0], wmin * wc.get('root_scale', 0.6), wmax)
            w[-1] = min(w[-1], max(w[:-1].max() * wc.get('tip_scale', 0.7), wmin * 0.5))
            frames.append((T, B, Nr))
            ws.append(w)
            across.append(3 if kinds[i] == 'vfold' else 2)
            folds.append(float(g.get('vfold', 0.25)) if kinds[i] == 'vfold' else 0.0)
        self.spines, self.frames, self.widths = spines, frames, ws
        self.nrows, self.Lc, self.members = np.array(nrows), np.array(Lc), members
        self.across, self.folds, self.kinds = np.array(across), np.array(folds), kinds
        self.root_w = np.array([np.max(w) for w in ws])        # the card's widest row: its width class
        ctri, cbary = z['ctri'][self.keep].astype(np.int64), z['cbary'][self.keep].astype(np.float64)
        self.rP, self.rN, self.rUV, self.rset = b.tri_points(ctri, cbary)
        self.rJ, self.rW = b.tri_weights(ctri, cbary)
        self.ctri, self.cbary = ctri, cbary
        self.rnd = z['grnd'][self.keep].astype(np.float64)
        self.cslot = z['cslot'][self.keep].astype(np.int64)
        self.cgroup = cgroup[self.keep]
        self.shell_normals = cs.get('normal', 'shell') == 'shell'
        mids = np.array([s[len(s) // 2] for s in spines])
        if sdf is not None:
            self.h_rel = sdf.sample(mids) / np.maximum(self.Lc, 1e-9)
        else:
            H, _ = self._heights(mids)
            self.h_rel = H / np.maximum(self.Lc, 1e-9)
        tris = 2 * (self.nrows - 1) * (self.across - 1)
        self.hair_gate = dict(cards=int(n), clumps=int(C), triangles=int(tris.sum()),
                              rows_p10_50_90=np.percentile(self.nrows, [10, 50, 90]).tolist(),
                              length_mm_p10_50_90=np.round(np.percentile(self.Lc * 1e3, [10, 50, 90]), 1).tolist(),
                              width_mm_p10_50_90=np.round(np.percentile(self.root_w * 1e3, [10, 50, 90]), 1).tolist(),
                              by_group={gnames[gi]: int((self.cgroup == gi).sum()) for gi in np.unique(self.cgroup)},
                              kinds={k: kinds.count(k) for k in set(kinds)})
        log(f'[cards] hair: {json.dumps(self.hair_gate)}')
        return self

    def _sdf_normals(self, X):
        """(B3) the SDF's unit gradient at points (host side: central differences on the grid's trilinear samples)"""
        sdf = self.sdf
        h = sdf.h
        X = np.asarray(X, np.float64)
        g = np.zeros_like(X)
        for a in range(3):
            e = np.zeros(3)
            e[a] = h
            g[:, a] = sdf.sample(X + e) - sdf.sample(X - e)
        return g / np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-12)

    def push_out(self, va, margin_mm=0.8, rounds=4):
        """(B3, c01) every card vertex past the root row at least margin_mm over the SDF (a widened row's edge can cut
        into the head where it curves under the card: c01, 14 vertices up to 4.1 mm deep), pushed along the gradient;
        returns (vertices moved, the minimum SDF after, mm)"""
        sdf = self.sdf
        sel = np.nonzero(va['furdata'][:, 1] > 0)[0]
        X = va['POSITION'][sel].astype(np.float64)
        m = margin_mm * 1e-3
        moved = np.zeros(len(X), bool)
        for _ in range(rounds):
            ph = sdf.sample(X)
            low = ph < m
            if not low.any():
                break
            X[low] += self._sdf_normals(X[low]) * (m - ph[low])[:, None]
            moved |= low
        va['POSITION'][sel] = X.astype(np.float32)
        return int(moved.sum()), round(float(sdf.sample(X).min()) * 1e3, 3)

    def fit_budget(self, budget_tris, log=print):
        """(B3) the LOD0 budget: with ranks set, the cards of the finest ranks are dropped (finest first, within a rank
        by hash) until the triangles fit; the survivors keep their ranks"""
        tris = 2 * (self.nrows - 1) * (self.across - 1)
        total = int(tris.sum())
        self.budget_gate = dict(budget=int(budget_tris), before=total, dropped=0)
        if total <= budget_tris:
            self.budget_gate['after'] = total
            return self
        pr = self.ranks * 10.0 + hkey(31, self.ctri, self.cslot, ch=7)
        order = np.argsort(-pr)                                  # finest rank first
        cum = np.cumsum(tris[order])
        ndrop = int(np.searchsorted(cum, total - budget_tris) + 1)
        drop = np.zeros(len(tris), bool)
        drop[order[:ndrop]] = True
        self._subset_cards(~drop)
        tris = 2 * (self.nrows - 1) * (self.across - 1)
        self.budget_gate.update(dropped=int(drop.sum()), after=int(tris.sum()))
        log(f'[cards] budget: {json.dumps(self.budget_gate)}')
        return self

    def _subset_cards(self, k):
        idx = np.nonzero(k)[0]
        for a in ('spines', 'frames', 'widths', 'members', 'kinds'):
            setattr(self, a, [getattr(self, a)[i] for i in idx])
        for a in ('keep', 'nrows', 'Lc', 'across', 'folds', 'root_w', 'rP', 'rN', 'rUV', 'rset', 'rJ', 'rW', 'ctri',
                  'cbary', 'rnd', 'cslot', 'cgroup', 'h_rel', 'ranks', 'layer', 'wclass', 'variant', 'tile'):
            if hasattr(self, a) and getattr(self, a) is not None:
                setattr(self, a, np.asarray(getattr(self, a))[idx])

    # ---------------------------------------------------------------------------------------------- the overhang
    @staticmethod
    def _spine_samples(spines):
        """every card's rows and segment middles in order along its spine: points, owner card, arc length (m)"""
        X, own, arc = [], [], []
        for i, sp in enumerate(spines):
            nr = len(sp)
            pts = np.empty((2 * nr - 1, 3))
            pts[0::2] = sp
            pts[1::2] = 0.5 * (sp[1:] + sp[:-1])
            seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
            X.append(pts)
            own.append(np.full(len(pts), i))
            arc.append(np.concatenate([[0.0], np.cumsum(seg)]))
        return np.concatenate(X), np.concatenate(own), np.concatenate(arc)

    def crossing(self, A, B, n=24):
        """(coat round 3) where each straight segment A -> B (the last sample over the coat to the first over bare skin)
        first reaches skin under the mask cut, as a fraction of the segment: n sub-samples per segment (the mask's edge
        is a few mm wide, the samples ~10 mm apart: interpolating the two ends' masks put the cut well past the edge)"""
        A, B = np.asarray(A, np.float64), np.asarray(B, np.float64)
        f = np.linspace(0.0, 1.0, n + 1)[1:]
        X = A[:, None, :] + (B - A)[:, None, :] * f[None, :, None]
        m, _ = self.coat_mask(X.reshape(-1, 3))
        bad = m.reshape(len(A), n) < self.mask_cut
        k = np.where(bad.any(1), np.argmax(bad, axis=1), n - 1)
        return np.where(k > 0, f[np.maximum(k - 1, 0)], 0.0)       # the last sub-sample still over the coat

    def _edge_trim(self, spines, nrows, Lc, rows_tab, log=print):
        """cards whose spine reaches skin under the mask cut end before it (cards.edge_margin_mm short of the crossing,
        found by crossing()); a card that would be shorter than cards.edge_min_mm is marked to drop. Spines, rows and
        lengths change in place; returns (cards over bare skin before, drop flags)"""
        cut = self.mask_cut
        margin = float(self.cs.get('edge_margin_mm', 1.0)) * 1e-3
        min_len = float(self.cs.get('edge_min_mm', 2.0)) * 1e-3
        n = len(spines)
        drop = np.zeros(n, bool)
        before = 0
        for rnd_ in range(4):
            X, own, arc = self._spine_samples(spines)
            m, _ = self.coat_mask(X)
            first = np.r_[True, own[1:] != own[:-1]]
            bad = (m < cut) & ~first & ~drop[own]
            cards = np.unique(own[bad])
            if rnd_ == 0:
                before = int(len(cards))
            if len(cards) == 0:
                break
            start = np.searchsorted(own, np.arange(n + 1))
            js = np.array([start[i] + int(np.nonzero(bad[start[i]:start[i + 1]])[0][0]) for i in cards])
            fr = self.crossing(X[js - 1], X[js])
            for i, j, f in zip(cards, js, fr):
                Lx = arc[j - 1] + f * (arc[j] - arc[j - 1]) - margin
                if Lx < min_len:
                    drop[i] = True
                    continue
                nr = next(r for lim, r in rows_tab if Lx * 1e3 <= lim)
                spines[i] = resample(spines[i], Lx, nr)
                nrows[i] = nr
                Lc[i] = Lx
        return before, drop

    @staticmethod
    def _spine_fine(spines, per_segment=8):
        """every card's spine at per_segment samples per row segment: points, owner card, arc length (m)"""
        X, own, arc = [], [], []
        for i, sp in enumerate(spines):
            nr = len(sp)
            t = np.linspace(0.0, nr - 1.0, per_segment * (nr - 1) + 1)
            k = np.minimum(t.astype(np.int64), nr - 2)
            f = (t - k)[:, None]
            S = sp[k] * (1.0 - f) + sp[k + 1] * f
            X.append(S)
            own.append(np.full(len(S), i))
            arc.append(np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(S, axis=0), axis=1))])
        return np.concatenate(X), np.concatenate(own), np.concatenate(arc)

    def _overshoots(self, spines):
        """per card: how far (m) its tip lies past the last spine sample over coat density >= cards.density_cut, and the arc
        length of that sample; a low-density gap under the card's middle doesn't count, only the run out to the tip"""
        cut = float(self.cs.get('density_cut', 0.12))
        X, own, arc = self._spine_fine(spines)
        d = self.coat_density(X)
        n = len(spines)
        start = np.searchsorted(own, np.arange(n + 1))
        over, last = np.zeros(n), np.zeros(n)
        for i in range(n):
            di, ai = d[start[i]:start[i + 1]], arc[start[i]:start[i + 1]]
            good = np.nonzero(di >= cut)[0]
            last[i] = ai[good[-1]] if len(good) else 0.0
            over[i] = ai[-1] - last[i]
        return over, last

    def _overshoot_trim(self, spines, nrows, Lc, rows_tab):
        """a card whose tip runs more than cards.overshoot_mm past the last of the pelt under it ends overshoot_mm past it
        (a hem's hairs do lie a little past the pelt; round 2's paper cards lay tens of mm past it); one that would be
        shorter than cards.edge_min_mm is marked to drop. Spines, rows and lengths change in place; returns (cards over the
        limit before, drop flags)"""
        tol = float(self.cs.get('overshoot_mm', 4.0)) * 1e-3
        min_len = float(self.cs.get('edge_min_mm', 2.0)) * 1e-3
        n = len(spines)
        drop = np.zeros(n, bool)
        before = 0
        for rnd_ in range(3):
            over, last = self._overshoots(spines)
            hit = np.nonzero((over > tol + 1e-4) & ~drop)[0]
            if rnd_ == 0:
                before = int(len(hit))
            if len(hit) == 0:
                break
            for i in hit:
                Lx = float(last[i] + tol)
                if Lx < min_len:
                    drop[i] = True
                    continue
                nr = next(r for lim, r in rows_tab if Lx * 1e3 <= lim)
                spines[i] = resample(spines[i], Lx, nr)
                nrows[i] = nr
                Lc[i] = Lx
        return before, drop

    def _density_gate(self, spines, before, dropped):
        """what the check's overhang.py reads: tips over coat density under the cut, how far past the pelt, how high"""
        tol = float(self.cs.get('overshoot_mm', 4.0))
        cut = float(self.cs.get('density_cut', 0.12))
        over, _ = self._overshoots(spines)
        tips = np.array([sp[-1] for sp in spines])
        thin = self.coat_density(tips) < cut
        H, _ = self._heights(tips)
        o = over[thin] * 1e3
        return dict(density_cut=cut, overshoot_limit_mm=tol, cards_over_the_limit_before=before, dropped=dropped,
                    tips_over_thin_coat=int(thin.sum()), cards_over_the_limit=int((over * 1e3 > tol + 0.5).sum()),
                    overshoot_mm_p50_90_max=np.round(np.percentile(o, [50, 90, 100]), 2).tolist() if len(o) else None,
                    tip_height_mm_p50_90_max=np.round(np.percentile(H[thin] * 1e3, [50, 90, 100]), 2).tolist()
                    if len(o) else None,
                    ok=bool((over * 1e3 > tol + 0.5).sum() <= max(3, 0.001 * len(spines))))

    def _edge_samples(self, spines, frames, ws):
        """both edges of every row and of every segment's middle: points, owner card, the rows a sample belongs to"""
        X, own, ra, rb = [], [], [], []
        for i, (sp, fr, w) in enumerate(zip(spines, frames, ws)):
            B = fr[1]
            nr = len(sp)
            for side in (-1.0, 1.0):
                X.append(sp + B * (0.5 * w * side)[:, None])
                own.append(np.full(nr, i))
                ra.append(np.arange(nr))
                rb.append(np.arange(nr))
                if nr > 1:
                    Bm = B[1:] + B[:-1]
                    Bm /= np.maximum(np.linalg.norm(Bm, axis=1, keepdims=True), 1e-12)
                    X.append(0.5 * (sp[1:] + sp[:-1]) + Bm * (0.25 * (w[1:] + w[:-1]) * side)[:, None])
                    own.append(np.full(nr - 1, i))
                    ra.append(np.arange(nr - 1))
                    rb.append(np.arange(1, nr))
        return np.concatenate(X), np.concatenate(own), np.concatenate(ra), np.concatenate(rb)

    def _edge_narrow(self, spines, frames, ws, wmin, rounds=10, step=0.8):
        """rows whose edge (or a segment middle's edge) lies further into the bare zone than cards.overhang_tol_mm
        narrowed by `step` until it does not (never under a quarter of the row's width nor 0.4 x the style's minimum
        width), the taper rule kept; returns the number of row narrowings"""
        tol = float(self.cs.get('overhang_tol_mm', 1.0))
        floor = [np.maximum(0.25 * w, 0.4 * wmin) for w in ws]
        total = 0
        for _ in range(rounds):
            X, own, ra, rb = self._edge_samples(spines, frames, ws)
            dep, _m, _h = self.bare_depth(X)
            bad = dep > tol
            if not bad.any():
                break
            hit = set(zip(own[bad].tolist(), ra[bad].tolist())) | set(zip(own[bad].tolist(), rb[bad].tolist()))
            moved = 0
            for i, r in hit:
                w = ws[i]
                nw_ = max(w[r] * step, floor[i][r])
                if nw_ < w[r] - 1e-9:
                    w[r] = nw_
                    moved += 1
            for w in ws:
                for r in range(1, len(w)):
                    w[r] = min(w[r], w[r - 1])
            total += moved
            if moved == 0:
                break
        return total

    def _overhang_gate(self, spines, frames, ws):
        """every row's and segment middle's spine point and edges against the coat: per card the deepest sample's
        distance INTO the bare zone (mm over the skin; the root's own spine point excepted). A card overhangs when that
        is more than cards.overhang_tol_mm (a hairline's edge lies on the bare line by a fraction of a mm; round 2's
        paper cards lay 5-20 mm out); its tip when the last row's spine point lies over bare skin at all. Also: the
        counts at zero tolerance, cards over thin coat (mask under 0.3), the height of what overhangs"""
        cut = self.mask_cut
        tol = float(self.cs.get('overhang_tol_mm', 1.0))
        n = len(spines)
        Xs, own_s, _ = self._spine_samples(spines)
        ds, ms, hs = self.bare_depth(Xs)
        first = np.r_[True, own_s[1:] != own_s[:-1]]
        last = np.r_[own_s[1:] != own_s[:-1], True]
        Xe, own_e, _, _ = self._edge_samples(spines, frames, ws)
        de, me, he = self.bare_depth(Xe)
        ds = np.where(first, 0.0, ds)
        deep = np.zeros(n)
        np.maximum.at(deep, own_s, ds)
        np.maximum.at(deep, own_e, de)
        any0 = np.zeros(n, bool)
        any0[own_s[(ms < cut) & ~first]] = True
        any0[own_e[me < cut]] = True
        sp_bad = np.zeros(n, bool)
        sp_bad[own_s[ds > tol]] = True
        tip_bad = np.zeros(n, bool)
        tip_bad[own_s[last & (ms < cut)]] = True
        soft = np.zeros(n, bool)
        soft[own_s[(ms < 0.3) & ~first]] = True
        soft[own_e[me < 0.3]] = True
        over = deep > tol
        self.last_over = over | tip_bad                       # (per card: what the gate flags; fit_fins reads it)
        h_bad = np.concatenate([hs[ds > tol], he[de > tol]])
        return dict(cards=int(n), cut=cut, tol_mm=tol, cards_overhanging=int(over.sum()),
                    cards_overhanging_spine=int(sp_bad.sum()), cards_tip_over_bare=int(tip_bad.sum()),
                    cards_touching_bare_any=int(any0.sum()), cards_over_thin_coat_lt_0p3=int(soft.sum()),
                    depth_into_bare_mm_p99_max=np.round(np.percentile(deep, [99, 100]), 2).tolist(),
                    overhang_height_mm_p50_max=np.round(np.percentile(h_bad * 1e3, [50, 100]), 2).tolist()
                    if len(h_bad) else None,
                    ok=bool(tip_bad.sum() == 0 and over.sum() <= max(3, 0.001 * n)))

    def lift_allowed_deg(self, t):
        """the style's largest elevation over the skin (degrees) at strand fraction t for the guide class: 90 - theta(t)
        + jitter, theta = root_deg -> tip_deg by pow (strands.k_grow's angle from the normal) plus the class's lifts"""
        st = self.style
        lift = st.get('lift', {})
        classes = st.get('classes', [{}])
        gc = classes[min(int(st.get('clumps', {}).get('guide_class', 0)), len(classes) - 1)]
        th0 = lift.get('root_deg', 50.0) + gc.get('lift_root_deg', 0.0)
        th1 = min(lift.get('tip_deg', 80.0) + gc.get('lift_tip_deg', 0.0), 89.0)
        th = th0 + (th1 - th0) * np.power(np.clip(t, 0.0, 1.0), lift.get('pow', 1.0))
        return 90.0 - th + lift.get('jitter_deg', 0.0)

    def _segment_elev(self, spines):
        """per card, per row segment: elevation (degrees) over the skin under the segment's middle, and the allowed"""
        mids, tm, owner = [], [], []
        for i, sp in enumerate(spines):
            nr = len(sp)
            mids.append(0.5 * (sp[1:] + sp[:-1]))
            tm.append((np.arange(nr - 1) + 0.5) / max(nr - 1, 1))
            owner.append(np.full(nr - 1, i))
        M = np.concatenate(mids)
        N = self._normals_at(M)
        D = np.concatenate([np.diff(sp, axis=0) for sp in spines])
        D /= np.maximum(np.linalg.norm(D, axis=1, keepdims=True), 1e-12)
        el = np.degrees(np.arcsin(np.clip(np.sum(D * N, 1), -1.0, 1.0)))
        tm = np.concatenate(tm)
        return el, self.lift_allowed_deg(tm), np.concatenate(owner), N

    def _lie_down(self, spines, log=print, tol_deg=1.0, margin=None):
        """row by row over every card at once: a segment steeper than the allowed lift turns down about the card's
        width axis toward its own direction along the skin (length kept), the rows past it carried along; then every
        row off the root is pushed out of the skin (the style's margin) along its closest face's normal"""
        el0, al0, own0, _ = self._segment_elev(spines)
        margin = (self.style.get('margin_mm', 0.3) if margin is None else margin) * 1e-3
        turned = 0
        for _round in range(3):             # a push out of the skin can steepen a segment again in a fold: re-turn
            turned += self._lie_round(spines, tol_deg, margin)
            el1, al1, own1, _ = self._segment_elev(spines)
            if not (el1 > al1 + tol_deg).any():
                break
        n = len(spines)
        over0 = np.zeros(n, bool)
        over0[own0[el0 > al0 + tol_deg]] = True
        over1 = np.zeros(n, bool)
        over1[own1[el1 > al1 + tol_deg]] = True
        emax1 = np.full(n, -90.0)
        np.maximum.at(emax1, own1, el1)
        self.lie_gate = dict(
            allowed_deg_root_tip=[round(float(self.lift_allowed_deg(0.0)), 1), round(float(self.lift_allowed_deg(1.0)), 1)],
            segments_turned=int(turned), rounds=_round + 1, cards_outside_before=int(over0.sum()),
            cards_outside_after=int(over1.sum()),
            card_steepest_segment_deg_p50_90_99_max=np.round(np.percentile(emax1, [50, 90, 99, 100]), 1).tolist(),
            ok=bool(over1.sum() <= max(3, 0.001 * n)))
        if over1.any():
            # where the rest stand: the excess over the allowed and the skin's turn under the card
            ex = el1 - al1
            self.lie_gate['outside_excess_deg'] = np.round(np.sort(ex[ex > tol_deg])[::-1][:8], 1).tolist()
        log(f'[cards] lie down: {json.dumps(self.lie_gate)}')

    def _lie_round(self, spines, tol_deg, margin):
        nr_max = max(len(sp) for sp in spines)
        turned = 0
        for r in range(nr_max - 1):
            idx = [i for i, sp in enumerate(spines) if len(sp) > r + 1]
            if not idx:
                break
            A = np.array([spines[i][r] for i in idx])
            Bp = np.array([spines[i][r + 1] for i in idx])
            nr = np.array([len(spines[i]) for i in idx])
            t = (r + 0.5) / np.maximum(nr - 1, 1)
            N = self._normals_at(0.5 * (A + Bp))
            dv = Bp - A
            ln = np.linalg.norm(dv, axis=1)
            dh = dv / np.maximum(ln[:, None], 1e-12)
            e = np.arcsin(np.clip(np.sum(dh * N, 1), -1.0, 1.0))
            ea = np.radians(self.lift_allowed_deg(t))
            bad = e > ea + np.radians(tol_deg)
            if not bad.any():
                continue
            tang = dh - N * np.sum(dh * N, 1, keepdims=True)
            tl = np.linalg.norm(tang, axis=1, keepdims=True)
            tang = tang / np.maximum(tl, 1e-12)
            new_dir = np.cos(ea)[:, None] * tang + np.sin(ea)[:, None] * N
            for k in np.nonzero(bad & (tl[:, 0] > 1e-6))[0]:
                i = idx[k]
                shift = A[k] + new_dir[k] * ln[k] - spines[i][r + 1]
                spines[i][r + 1:] += shift
                turned += 1
        # out of the skin: every row past the root at least the margin above it (two passes: a push can change the
        # closest face)
        for _ in range(2):
            allp = np.concatenate([sp[1:] for sp in spines])
            H, F = self._heights(allp)
            low = H < margin
            if not low.any():
                break
            Fv = self.base.Vw[self.base.Fw[F[low]]]
            fn = np.cross(Fv[:, 1] - Fv[:, 0], Fv[:, 2] - Fv[:, 0])
            fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-12)
            allp[low] += fn * (margin - H[low])[:, None]
            o = 0
            for sp in spines:
                k = len(sp) - 1
                sp[1:] = allp[o:o + k]
                o += k
        return turned

    def _normals_at(self, X):
        import warp as wp
        d = self.surf.device
        Pw = wp.array(X.astype(np.float32), dtype=wp.vec3, device=d)
        H = wp.zeros(len(X), dtype=wp.float32, device=d)
        F = wp.zeros(len(X), dtype=wp.int32, device=d)
        wp.launch(ST.k_height, dim=len(X), device=d, inputs=[*self.surf.args(), Pw, H, F])
        fw = F.numpy()
        Fv = self.base.Fw[fw]
        # the face's welded normals averaged (smooth enough for a frame)
        N = self.base.Nw[Fv].mean(1)
        return N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)

    def _heights(self, X):
        import warp as wp
        d = self.surf.device
        Pw = wp.array(X.astype(np.float32), dtype=wp.vec3, device=d)
        return ST.heights(self.surf, Pw)

    # ---------------------------------------------------------------------------------------------- classes
    def classify(self, width_classes=None, n_var=2):
        """layer (density class), width class, variant -> tile index (density x n_width x n_var + width x n_var +
        variant); the wisp row is density class 3"""
        cs = self.cs
        q = cs.get('layer_q', [0.40, 0.80])
        h = self.h_rel
        lay = np.digitize(h, np.quantile(h, q))                 # 0 inner (dense) .. 2 outer (sparse)
        wisp_share = cs.get('wisp_share', 0.08)
        outer = lay == 2
        u = hkey(17, self.ctri, self.cslot, ch=21)
        lay[outer & (u < wisp_share / max(outer.mean(), 1e-9))] = 3
        if width_classes is None:
            width_classes = np.quantile(self.root_w, [0.125, 0.375, 0.625, 0.875])
        self.width_classes = np.asarray(width_classes, np.float64)
        edges = 0.5 * (self.width_classes[1:] + self.width_classes[:-1])
        wc = np.digitize(self.root_w, edges)
        var = (hkey(17, self.ctri, self.cslot, ch=22) < 0.5).astype(np.int64)
        nw = len(self.width_classes)
        self.layer, self.wclass, self.variant = lay, wc, var
        self.tile = lay * (nw * n_var) + wc * n_var + var
        self.n_tiles = 4 * nw * n_var
        return self

    # ---------------------------------------------------------------------------------------------- edge fins
    def fit_fins(self, log=print):
        """(coat round 3) VELVET'S OUTLINE as true FINS (Lengyel, Praun, Finkelstein & Hoppe 2001: shells and fins; the
        fins are the silhouette's part): one fin per coated edge of the base's welded low, standing on the edge (its
        root row IS the edge, on the skin by construction) and rising to the pile's top: at each end the welded
        vertex's normal x the local pile height plus the pile's own lean (both measured on the groom's strands rooted
        within cards.fins.radius_mm: the 80th-percentile tip height and the mean tangential run from root to tip), so
        neighbouring fins share their top corners and the fringe is one continuous ribbon. At a silhouette the
        silhouette edges' fins face the camera by construction: the rim is continuous and even at any view (round 2's
        shingles at 3.5 per cm2 put ~1 card per cm of outline on a 1 cm arm: the thorns). The ABI is unchanged: NORMAL
        = the edge's normal (the runtime's window), TANGENT = the fin's rise (the fibre direction), JOINTS / WEIGHTS
        per END (each end's own vertex weights), _FURCENTER = each vertex's own root corner (the module doc), rows = root
        line and top; every fin rank 0 (the fins come in together, at the style's short_end.fins onset). Fills the same
        per-card fields fit() does, so classify / rank / the vertex arrays / root mips / snap / the gates run unchanged"""
        from scipy.spatial import cKDTree
        z, b, cs = self.z, self.base, self.cs
        fc = cs.get('fins', {})
        P = z['points'].astype(np.float64)
        S, K = P.shape[:2]
        R0, T0 = P[:, 0], P[:, -1]
        _, Nr0, _, _ = b.tri_points(z['tri'].astype(np.int64), z['bary'].astype(np.float64))
        dv = T0 - R0
        hgt = np.sum(dv * Nr0, 1)
        run = dv - Nr0 * hgt[:, None]
        # per welded vertex: the coat mask (the minimum over its copies), the pile's height and lean around it
        mexp = {'mul': [self.style.get('domain', 1.0), {'not': self.style.get('bare', 0.0)}]}
        pv = Pts.vertices(b)
        mv = np.clip(self.fields.eval(mexp, pv), 0.0, 1.0)
        nw = len(b.Vw)
        mw = np.ones(nw)
        np.minimum.at(mw, b.wid, mv)
        tree = cKDTree(R0)
        rad = float(fc.get('radius_mm', 3.0)) * 1e-3
        nb = tree.query_ball_point(b.Vw, rad)
        Hv = np.zeros(nw)
        Rv = np.zeros((nw, 3))
        q = float(fc.get('height_q', 80.0))
        for v, ids in enumerate(nb):
            if len(ids) >= 3:
                Hv[v] = np.percentile(hgt[ids], q)
                rr = run[ids].mean(0)
                Rv[v] = rr - b.Nw[v] * np.dot(rr, b.Nw[v])
        # THE COAT'S EDGE, on the fins: the height and lean taper to nothing over cards.fins.taper_mm, so the band runs out
        # as a pelt thins at a bare patch (the last fins stood at full height and the fringe ended in a square cut:
        # g5_groom/renders/s12_h.png, the crease)
        taper_mm = float(fc.get('taper_mm', 0.0))
        fin_taper = 1.0
        if taper_mm > 0.0:
            ev = self.fields.eval({'ref': fc.get('edge_field', 'edge_mm')}, pv)
            ew = np.full(nw, np.inf)
            np.minimum.at(ew, b.wid, ev)
            x = np.clip(ew / taper_mm, 0.0, 1.0)
            fin_taper = x * x * (3.0 - 2.0 * x)
            Hv *= fin_taper
            Rv *= fin_taper[:, None]
        # the coated edges (both ends' mask at or over the fins' floor), each with one face that holds it
        E = np.concatenate([b.Fw[:, [0, 1]], b.Fw[:, [1, 2]], b.Fw[:, [2, 0]]])
        Fo = np.repeat(np.arange(len(b.Fw))[None, :], 3, axis=0).reshape(-1)
        Co = np.concatenate([np.zeros(len(b.Fw), np.int64), np.ones(len(b.Fw), np.int64), np.full(len(b.Fw), 2)])
        key = np.sort(E, axis=1)
        _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
        inv = inv.reshape(-1)
        # a triangulated quad's diagonal is the longest edge of both its faces: a silhouette seldom runs along one, and
        # its neighbours' fins stand either side of it (cards.fins.skip_diagonals saves a third of the fins)
        nf = len(b.Fw)
        Lf = np.linalg.norm(b.Vw[b.Fw[:, [1, 2, 0]]] - b.Vw[b.Fw], axis=2)
        lng = np.zeros(3 * nf, bool)
        lng[np.argmax(Lf, axis=1) * nf + np.arange(nf)] = True
        n_long = np.bincount(inv, weights=lng.astype(np.float64), minlength=len(first))
        n_face = np.bincount(inv, minlength=len(first))
        diag = (n_face == 2) & (n_long == 2)
        E, Fo, Co = E[first], Fo[first], Co[first]
        mmin = float(fc.get('min_mask', self.mask_cut))
        hmin = float(fc.get('min_height_mm', 0.25)) * 1e-3
        sel = (np.minimum(mw[E[:, 0]], mw[E[:, 1]]) >= mmin) & (np.maximum(Hv[E[:, 0]], Hv[E[:, 1]]) >= hmin)
        coated_edges = int(sel.sum())
        diagonals_skipped = int((sel & diag).sum()) if fc.get('skip_diagonals', False) else 0
        if fc.get('skip_diagonals', False):
            sel &= ~diag
        E, Fo, Co = E[sel], Fo[sel], Co[sel]
        n = len(E)
        i, j = E[:, 0], E[:, 1]
        A, B = b.Vw[i], b.Vw[j]
        # the tile's fibres end at 0.62-0.96 of its height: height_scale puts the fringe's middle at the pile's measured top
        hs = float(fc.get('height_scale', 1.2))
        # THE OVERHANG, on the fins: a fin's top stands off its vertex by the pile's lean, so along the coat's edge it can
        # end over bare skin. A vertex whose top leaves the coat loses its lean, step by step (the fin rises straight
        # there, as a pile thinning at a bare patch does), so neighbouring fins keep sharing that top corner
        used = np.unique(E)
        fin_lean_cut = 0
        for f_ in (0.6, 0.3, 0.0):
            Top = b.Vw[used] + (b.Nw[used] * Hv[used][:, None] + Rv[used]) * hs
            dep, _m, _h = self.bare_depth(Top)
            bad = used[dep > 0.0]
            if len(bad) == 0:
                break
            Rv[bad] *= f_
            fin_lean_cut += int(len(bad))
        TA = A + (b.Nw[i] * Hv[i][:, None] + Rv[i]) * hs
        TB = B + (b.Nw[j] * Hv[j][:, None] + Rv[j]) * hs

        def fin_shape(k, ta, tb):
            sp = np.stack([0.5 * (A[k] + B[k]), 0.5 * (ta + tb)])
            Tn = sp[1] - sp[0]
            Tn = Tn / max(np.linalg.norm(Tn), 1e-12)
            b0 = B[k] - A[k]
            b1 = tb - ta
            w = np.array([np.linalg.norm(b0), np.linalg.norm(b1)])
            Bx = np.stack([b0 / max(w[0], 1e-12), b1 / max(w[1], 1e-12)])
            return sp, (np.stack([Tn, Tn]), Bx, np.stack([Ne0[k], Ne0[k]])), w

        # a long edge between two coated vertices can still cross a thin bare sliver (the mask is a texture, the edges 8 mm
        # long): such a fin's top comes down (a pile thins at a bare patch), and one that still leaves the coat goes
        Ne0 = b.Nw[i] + b.Nw[j]
        Ne0 /= np.maximum(np.linalg.norm(Ne0, axis=1, keepdims=True), 1e-12)
        lowered, drop = 0, np.zeros(n, bool)
        for rnd_ in range(3):
            built = [fin_shape(k, TA[k], TB[k]) for k in range(n)]
            self._overhang_gate([s[0] for s in built], [s[1] for s in built], [s[2] for s in built])
            bad = self.last_over.copy()
            if not bad.any():
                break
            if rnd_ == 2:
                drop = bad
                break
            TA[bad] = A[bad] + (TA[bad] - A[bad]) * 0.5
            TB[bad] = B[bad] + (TB[bad] - B[bad]) * 0.5
            lowered += int(bad.sum())
        if drop.any():
            keep_ = ~drop
            E, Fo, Co, A, B, TA, TB = E[keep_], Fo[keep_], Co[keep_], A[keep_], B[keep_], TA[keep_], TB[keep_]
            n = len(E)
            i, j = E[:, 0], E[:, 1]
        Ne = b.Nw[i] + b.Nw[j]
        Ne /= np.maximum(np.linalg.norm(Ne, axis=1, keepdims=True), 1e-12)
        # the root: the edge's midpoint on the face that holds it (corners c, c + 1 of that face are the edge's ends)
        bary = np.zeros((n, 3))
        bary[np.arange(n), Co] = 0.5
        bary[np.arange(n), (Co + 1) % 3] = 0.5
        oneA = np.zeros((n, 3))
        oneB = np.zeros((n, 3))
        corner_of_i = np.where(b.Fw[Fo, Co] == i, Co, (Co + 1) % 3)
        oneA[np.arange(n), corner_of_i] = 1.0
        oneB[np.arange(n), np.where(corner_of_i == Co, (Co + 1) % 3, Co)] = 1.0
        self.rP, _, self.rUV, self.rset = b.tri_points(Fo, bary)
        self.rN = Ne
        self.rJ, self.rW = b.tri_weights(Fo, bary)
        JA, WA = b.tri_weights(Fo, oneA)
        JB, WB = b.tri_weights(Fo, oneB)
        self.rJ_side = np.stack([JA, JB], 1)
        self.rW_side = np.stack([WA, WB], 1)
        self.ctri, self.cbary = Fo, bary
        self.cslot = (np.minimum(i, j) * 7919 + np.maximum(i, j)) % 2147483647
        self.rnd = hkey(int(self.style.get('seed', 1)) + 61, self.ctri, self.cslot, ch=9)
        Ne0 = Ne
        spines, frames, ws, Lc = [], [], [], []
        for k in range(n):
            sp, fr, w = fin_shape(k, TA[k], TB[k])
            spines.append(sp)
            frames.append(fr)
            ws.append(w)
            Lc.append(float(np.linalg.norm(sp[1] - sp[0])))
        self.spines, self.frames, self.widths = spines, frames, ws
        self.nrows = np.full(n, 2, np.int64)
        self.Lc = np.array(Lc)
        self.members = [np.zeros(0, np.int64) for _ in range(n)]
        self.keep = np.arange(n, dtype=np.int64)
        self.root_w = np.array([w[0] for w in ws])
        self.fin_mask = np.minimum(mw[i], mw[j])
        self.fin_height = 0.5 * (Hv[i] + Hv[j])
        self.h_rel = self.fin_height / np.maximum(self.Lc, 1e-9)
        self.stub_clumps = 0
        self.overhang_gate = self._overhang_gate(spines, frames, ws)
        self.overhang_gate.update(kind='edge fins (on coated edges by construction)')
        self.fin_gate = dict(fins=int(n), coated_edges=coated_edges, diagonals_skipped=diagonals_skipped, triangles=int(2 * n),
                             lean_cut_at_the_edge=fin_lean_cut, tops_lowered_at_the_edge=lowered,
                             dropped_at_the_edge=int(drop.sum()),
                             edge_length_mm_p10_50_90=np.round(np.percentile(self.root_w * 1e3, [10, 50, 90]), 2).tolist(),
                             pile_height_mm_p10_50_90=np.round(np.percentile(self.fin_height * 1e3, [10, 50, 90]), 2).tolist(),
                             lean_mm_p50=round(float(np.median(np.linalg.norm(0.5 * (Rv[i] + Rv[j]), axis=1)) * 1e3), 2),
                             vertices_without_strands_near=int((Hv <= 0).sum()))
        log(f'[cards] edge fins: {json.dumps(self.fin_gate)}')
        return self

    def classify_fins(self, width_classes=None, n_var=2):
        """(coat round 3) the fins' tiles: the density row by the coat's mask at the edge (the pelt thins toward its
        bare edge: dense >= 0.85, medium >= 0.6, sparse >= 0.35, else the wisp row), the width class by the edge's length
        (each tile as wide as its class: the fibres keep their drawn thickness), a hashed variant"""
        m = self.fin_mask
        lay = np.where(m >= 0.85, 0, np.where(m >= 0.6, 1, np.where(m >= 0.35, 2, 3))).astype(np.int64)
        if width_classes is None:
            width_classes = np.quantile(self.root_w, [0.125, 0.375, 0.625, 0.875])
        self.width_classes = np.asarray(width_classes, np.float64)
        edges = 0.5 * (self.width_classes[1:] + self.width_classes[:-1])
        wc = np.digitize(self.root_w, edges)
        var = (hkey(17, self.ctri, self.cslot, ch=22) < 0.5).astype(np.int64)
        nw = len(self.width_classes)
        self.layer, self.wclass, self.variant = lay, wc, var
        self.tile = lay * (nw * n_var) + wc * n_var + var
        self.n_tiles = 4 * nw * n_var
        return self

    def rank_all(self, n_ranks=8):
        """(coat round 3) every card in rank 0 (the fins come in together: a thinned fin set is a broken fringe)"""
        self.ranks = np.zeros(len(self.keep), np.int64)
        self.fractions = [1.0] * n_ranks
        self.n_ranks = n_ranks
        return self

    # ---------------------------------------------------------------------------------------------- LOD ranks
    def rank(self, fractions=(1.0, 0.5, 0.25, 0.12), length_bias=0.5):
        """nested Poisson thinning: rank r = 0 for the coarsest LOD's set .. len-1 for cards only LOD0 draws"""
        n = len(self.keep)
        P = self.rP
        dens = np.maximum(self.z_density(), 1e-3)                # cards per cm2 at each root
        base_r = 1.0 / np.sqrt(dens * 1e4)                       # metres: the local card spacing
        pr = hkey(29, self.ctri, self.cslot, ch=5) * (self.Lc / self.Lc.max()) ** length_bias
        fr = sorted(fractions)                                   # ascending: 0.12, 0.25, 0.5, 1.0
        rank = np.full(n, len(fr) - 1, np.int64)
        kept = np.zeros(n, bool)
        for ri, f in enumerate(fr[:-1]):
            lo, hi = 0.5, 8.0
            for _ in range(18):
                a = 0.5 * (lo + hi)
                boost = pr + kept * 10.0
                sel = poisson_keep(P, a * base_r, boost)
                if len(sel) > f * n:
                    lo = a
                else:
                    hi = a
            sel = poisson_keep(P, hi * base_r, pr + kept * 10.0)
            new = np.zeros(n, bool)
            new[sel] = True
            new |= kept
            rank[new & ~kept] = ri
            kept = new
        self.ranks = rank
        self.fractions = fr[::-1]                                # LOD0 first: 1.0, 0.5, 0.25, 0.12
        self.n_ranks = len(fr)
        return self

    def z_density(self):
        """cards per cm2 at the card roots, from the clump density recorded at grow time (cdens) or the local
        nearest-neighbour spacing"""
        from scipy.spatial import cKDTree
        d, _ = cKDTree(self.rP).query(self.rP, k=7)
        sp = np.median(d[:, 1:], axis=1)                         # metres
        return 1.0 / np.maximum((sp * 100.0) ** 2, 1e-9) * 0.9

    # ---------------------------------------------------------------------------------------------- geometry
    def vertex_arrays(self, root_mip=None):
        """flat vertex / index arrays in ABI order: cards sorted by (set, rank); per vertex POSITION, NORMAL (the
        root's skin normal), TANGENT (the spine tangent, w 1), JOINTS / WEIGHTS (the root's), furdata (strandRandom,
        rootToTip, side, flex), rootdata (root uv glTF, mip, rank * 32 + tile), furcenter (the row's spine point)"""
        n = len(self.keep)
        order = np.lexsort((np.arange(n), self.ranks, self.rset))
        V, Nn, T, J, W, FD, RD, FC, idx = [], [], [], [], [], [], [], [], []
        card_first_index = np.zeros(n, np.int64)
        tri_count = np.zeros(n, np.int64)
        vbase = 0
        flex = np.clip(self.Lc / np.quantile(self.Lc, 0.9), 0.15, 1.0)
        mip = root_mip if root_mip is not None else np.zeros(n)
        prim_of = self.rset[order]
        icount = 0
        # (coat round 3) edge fins carry each END's own skin weights (rJ_side / rW_side: (n, 2, 4)), so a fin follows the
        # skin along its edge as the skin itself does; cards keep their root's one vector
        side_w = getattr(self, 'rJ_side', None) is not None
        # (B3) hair cards: 2 or 3 vertices across (vfold: the middle raised along the row's N), each vertex's NORMAL its
        # row's shell normal, rootToTip by arc length (rows sit at uneven arcs when placed by curvature)
        across = getattr(self, 'across', None)
        shell = getattr(self, 'shell_normals', False)
        for k, c in enumerate(order):
            sp = self.spines[c]
            Tn, B, Nrow = self.frames[c]
            w = self.widths[c]
            nr = len(sp)
            na = int(across[c]) if across is not None else 2
            sides = (-1.0, 0.0, 1.0) if na == 3 else (-1.0, 1.0)
            fold = float(self.folds[c]) if na == 3 else 0.0
            if across is not None:
                arc = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(sp, axis=0), axis=1))])
                t = arc / max(arc[-1], 1e-12)
            else:
                t = np.linspace(0.0, 1.0, nr)
            for r in range(nr):
                for side in sides:
                    V.append(sp[r] + B[r] * (0.5 * w[r] * side) + Nrow[r] * (fold * w[r] * (1.0 - abs(side))))
                    Nn.append(Nrow[r] if shell else self.rN[c])
                    T.append(np.append(Tn[r], 1.0))
                    J.append(self.rJ_side[c, int(side > 0)] if side_w else self.rJ[c])
                    W.append(self.rW_side[c, int(side > 0)] if side_w else self.rW[c])
                    FD.append((self.rnd[c], t[r], side, flex[c]))
                    RD.append((self.rUV[c, 0], self.rUV[c, 1], mip[c], self.ranks[c] * 32 + self.tile[c]))
                    # a FIN's _FURCENTER is the vertex's OWN ROOT CORNER, not the row's middle: the runtime collapses a
                    # face-on card onto its _FURCENTER, and a fin's two ends carry different skin weights, so a shared
                    # centre skinned twice is two different points (a collapsed fin kept an area, and bent arms drew it
                    # as a strip off the body). Folded onto its own corners a fin lies flat on its skin edge, zero area,
                    # whichever of its ends collapse, each end riding its own weights
                    FC.append(sp[0] + B[0] * (0.5 * w[0] * side) if side_w else sp[r])
            card_first_index[c] = icount
            for r in range(nr - 1):
                for q in range(na - 1):
                    a = vbase + na * r + q
                    # (a, a+1) this column pair on the row, (a+na, a+na+1) the next row's
                    idx += [a, a + 1, a + na + 1, a, a + na + 1, a + na]
                    icount += 6
            tri_count[c] = 2 * (nr - 1) * (na - 1)
            vbase += na * nr
        out = dict(POSITION=np.array(V, np.float32), NORMAL=np.array(Nn, np.float32),
                   TANGENT=np.array(T, np.float32), JOINTS_0=np.array(J, np.uint16),
                   WEIGHTS_0=np.array(W, np.float32), furdata=np.array(FD, np.float32),
                   rootdata=np.array(RD, np.float32), furcenter=np.array(FC, np.float32),
                   index=np.array(idx, np.uint32))
        # per primitive (texture set): its index slice and its prefix table over ranks (coarsest LOD first)
        prims = []
        ranks_sorted = self.ranks[order]
        tris_sorted = tri_count[order]
        istart = 0
        for s in np.unique(prim_of):
            m = prim_of == s
            ni = int(tris_sorted[m].sum() * 3)
            pre = [int(tris_sorted[m & (ranks_sorted <= r)].sum() * 3) for r in range(self.n_ranks)]
            prims.append(dict(set=int(s), index_start=istart, index_count=ni, cards=int(m.sum()),
                              prefix_by_rank=pre))
            istart += ni
        out['prims'] = prims
        out['order'] = order
        return out

    def snap_roots(self, va, max_mm=1.0, to_mm=0.5, sunk_mm=0.2):
        """the root row onto the skin: a card's root row lies flat in the tangent plane at its centre, so on a thin,
        curved part (an arm tip) a wide card's corners stand off the skin (or sink into it); every root-row vertex
        further than max_mm from its TRUE closest skin point (or sunk more than sunk_mm under it) goes to that point
        plus to_mm along the skin's normal there (the card bends at its root instead of floating: §9.3's gate keeps
        roots within 0.4 cm, study T's p50 is 0.33 cm). (Coat round 2: the first pass moved them along the closest face's
        normal and gated the height along it, which leaves a vertex beside a thin edge up to ~5 mm away while its
        "height" reads 1 mm.) The root row's _FURCENTER (the width floor's centreline) is set to the snapped row's
        midpoint, so it never sits off the row it centres."""
        r0 = np.nonzero(va['furdata'][:, 1] == 0)[0]
        P = va['POSITION'][r0].astype(np.float64)
        moved = np.zeros(len(P), bool)
        for _ in range(3):
            S, N = ST.closest(self.surf, P)
            off = P - S
            dist = np.linalg.norm(off, axis=1)
            sgn = np.sum(off * N, 1)
            bad = (dist > max_mm * 1e-3) | (sgn < -sunk_mm * 1e-3)
            if not bad.any():
                break
            P[bad] = S[bad] + N[bad] * (to_mm * 1e-3)
            moved |= bad
        va['POSITION'][r0] = P.astype(np.float32)
        # vertex_arrays writes each row as a (side -1, side +1) pair, so the root row's two vertices are adjacent
        # (a fin's _FURCENTER is each vertex's own root corner: vertex_arrays; a fin's root row lies on the edge already)
        if getattr(self, 'across', None) is not None and getattr(self, 'rJ_side', None) is None:
            # (B3) hair cards: 2 or 3 root-row vertices per card (in the written order); each card's centre = the mean
            # of its root row's outer pair (a vfold's middle vertex is raised off that line)
            na = self.across[va['order']]
            o = 0
            for k in na:
                ii = r0[o:o + k]
                mid = 0.5 * (P[o] + P[o + k - 1])
                va['furcenter'][ii] = mid.astype(np.float32)
                o += k
        elif getattr(self, 'rJ_side', None) is None:
            mid = 0.5 * (P[0::2] + P[1::2])
            va['furcenter'][r0[0::2]] = mid.astype(np.float32)
            va['furcenter'][r0[1::2]] = mid.astype(np.float32)
        S, N = ST.closest(self.surf, P)
        dist = np.linalg.norm(P - S, axis=1)
        self.snap_gate = dict(root_vertices=int(len(P)), moved=int(moved.sum()),
                              true_dist_mm_p50_p99_max=np.round(np.percentile(dist * 1e3, [50, 99, 100]), 3).tolist(),
                              within_1mm=bool(dist.max() <= max_mm * 1e-3 + 1e-6),
                              furcenter_off_row_mid_mm_max=0.0)
        return int(moved.sum())

    def root_mips(self):
        """the explicit mip of each card's ONE root lookup (_ROOTDATA.z): its footprint (max(root width, half its
        length) in its set's texels, the card's own average colour), capped at log2(texels from the root uv to the edge
        of its uv island) - 1 so the trilinear footprint never leaves the island (coat round 2: the octopus's albedo
        islands sit on an unpadded light grey, and seam-side roots read it in: the oral web's grey-lavender cards)"""
        b = self.base
        ppm = b.px_per_m()
        res_set = np.array([b.tex(s, 'base').shape[0] for s in b.sets])
        ppm_set = np.array([ppm[s] for s in b.sets])
        foot = np.maximum(self.root_w, self.Lc * 0.5) * ppm_set[self.rset]
        mip = np.clip(np.log2(np.maximum(foot, 1.0)), 0, np.log2(res_set[self.rset]))
        edge0, uv_in = island_edge_texels(b, self.rUV, self.rset)
        nudged = np.any(uv_in != self.rUV, axis=1)
        self.rUV_root = self.rUV.copy()
        self.rUV = uv_in                                      # what _ROOTDATA.xy carries: the lookup's uv
        edge = edge0
        cap = np.maximum(0.0, np.log2(np.maximum(edge, 1.0)) - 1.0)
        self.root_edge_px = edge
        self.root_mip_footprint = mip
        out = np.minimum(mip, cap)
        texel_mm = 1e3 / ppm_set[self.rset]
        shift = np.linalg.norm((uv_in - self.rUV_root) * res_set[self.rset][:, None], axis=1) * texel_mm
        self.root_mip_gate = dict(cards=int(len(mip)), capped=int((cap < mip).sum()),
                                  rooted_within_16_texels_of_an_island_edge=int((edge < 16).sum()),
                                  lookup_uv_nudged_in=int(nudged.sum()),
                                  nudge_mm_max=round(float(shift.max()), 3) if nudged.any() else 0.0,
                                  mip_p10_50_90=np.round(np.percentile(out, [10, 50, 90]), 2).tolist(),
                                  footprint_mip_p50=round(float(np.median(mip)), 2))
        return out

    def lod_table(self, va):
        """per LOD: the ranks drawn, cards, triangles (all primitives)"""
        rows = []
        R = self.n_ranks
        for lod in range(R):
            rmax = R - 1 - lod
            cards = int((self.ranks <= rmax).sum())
            tris = int(sum(p['prefix_by_rank'][rmax] for p in va['prims']) // 3)
            rows.append(dict(lod=lod, draws_ranks_upto=rmax, cards=cards, triangles=tris))
        return rows

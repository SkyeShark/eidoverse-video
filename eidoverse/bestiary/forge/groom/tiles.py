"""THE ATLAS: our own clump tiles, rendered from our strands (HAIR_STUDY §9.3, §2.5, §3.4).

Layout: 4 rows (density classes: dense, medium, sparse, wisp: study T's dense -> single strands plus a flyaway band) x
(width classes x 2 variants) columns, each column as wide in the atlas as its width class is physically (so every
tile has the same texels per millimetre across the strand, and strands keep their drawn thickness on every card:
study T's cards span 1-17 % of the atlas width for this reason). Inside a tile, u = (side + 1) / 2 across the card and
v = rootToTip from the root (the tile's top edge, glTF v0) to the tip (v1): the ABI's own rule, no TEXCOORD_0.

Content: for each tile, real cards of that class from the groom; their member strands are carried into the card's
frame (u = offset . B / half-width, v = arc fraction along the card, depth = offset . N) and each member spawns
children (dense 7, medium 4, sparse 2, wisp 1 with only a few members) jittered across the card, growing apart toward
the tip: the groom is grown at tens of strands per cm2, a pelt has hundreds, and a card must carry that density.
Strands are drawn as spindles (style atlas.width_um: root, mid, tip; MetaHuman's drawn widths are about twice real
hair, HAIR_STUDY §2.1).

Pages:
  coverage   one channel, rendered at 4096 with 4x4 supersampling per texel, box-filtered to 2048 (the delivered page)
  attributes 512 RGBA: R depth behind the card plane (0.5 on the plane, +-depth_mm full scale, toward the skin is
             smaller), G strand id (a random per strand), B root-to-tip along the strand, A the strand tangent's
             sideways component (du/dv, 0.5 = straight along v); every channel push-pull dilated over the whole page
             so mips never bleed black (as the MetaHuman maps)
  clip table for each mip the runtime generates (2x2 box), the alpha threshold keeping mip 0's coverage fraction at
             the base threshold (global and per density row)

ATLAS v2 (coat round 2, 10-30; render_v2, chosen by the style's atlas.version 2): the close range. The first pass drew
each tile as a few solid ~1 mm locks (89 % of the covered texels solid), stable at one sample per pixel but a flat
painted shingle up close. study T's and study R's pages, measured (HAIR_STUDY §10), draw strands 1/30-1/80 of a tile
wide with soft edges (half to nine tenths of the covered texels partial), thinner at both ends, coverage starting thin at
the root and peaking near 0.4 of the length. v2 draws FINE STRANDS from the groom's own members: each member spawns
children (as many as the row's target fill needs), every child a spindle (atlas.strand_um: root, mid, tip, the tip
tapering to a fraction of a texel so it fades), its root staggered over the first atlas.root_span of the tile (the
coverage ramps in: no square root edge where a shingle overlaps the one below), its tip staggered, and pulled toward its
SUB-LOCK's mean curve harder toward the tip (atlas.lock_pull): mips 0-1 show hairs, the coarse mips the hero distance
reads still show the first pass's locks (what keeps the no-TAA clip fallback stable). Coverage is the true area coverage
(8x8 supersampled polygons, box-filtered, one channel); the attribute page is 1024 (atlas.attr_res) and every texel
carries its topmost fine strand's depth, id, own root-to-tip and sideways slope.

ATLAS v3 (coat round 3, 10-30; render_v3, atlas.version 3): FUR UP CLOSE UNDER TAA. At 0.34-0.56 m at 1080p a pixel is
0.23-0.38 mm, so a 90-135 um strand is a third of a pixel and the page is read at mips 1-3: single strands cannot
resolve there, LOCKS can (1-3 mm: 3-12 px). v2 pulled strands into sub-locks only toward the tip (lock_pull x t^1.6:
0.23 at mid-length), so the visible half of every shingle was an even brush: under TAA, brushed felt (the g4 check).
v3 builds each tile as LOCKS: evenly spaced across the card (atlas.lock_mm per row), each following its members' own
path from the groom, spread at the root (where every hair grows from its own follicle), gathered into a bundle a fifth
of the way up (atlas.lock_frac of the spacing: real PARTINGS between neighbouring locks, coverage near 0 there) and
tapering to a point, the locks' tips staggered and each strand's tip staggered inside its lock; a share of strays
(atlas.stray) leave their lock and cross the parting. The attribute page carries what the runtime needs to shade a
clump (g5_runtime/FOR_GROOM.md, agreed 10-30): R DEPTH as the clump's shape (a lock's crest on the card plane, its
flanks under it by atlas.depth_lock_mm x (offset / half width)^2, strays deeper still), encoded over atlas.depth_mm =
the real spread; G a per-LOCK random (stratified per tile, so a tile's mean is 0.5) plus a small per-strand offset (the
runtime's id terms are linear in G: per-lock value, hue, highlight tilt survive the mips); B the sideways slope. NO
ALPHA: the page is written RGB, because the engine's glTF image path divides colour by alpha (Deno 2.8;
work/bestiary/patches/scratch_decode/NOTES.md) and divided round 2's page in every engine shot.

THE FIN ATLAS (coat round 3, 10-30; render_fins, a style with cards.kind "fins"): a short pile's outline, one tile per
(density row, edge-length class, variant). A tile is a SIDE VIEW of the pile: u along the skin's edge, v from the root
line up to the pile's top. What it must look like comes from photographs of real short pile at grazing
(g5_groom/refs, s03_outline.py: antler velvet on ~3 cm tines, the mole): a continuous, even band; the body solid up to
about two thirds of the height, the top third the fibres' tips dissolving; a few much finer strays just past it; no gaps,
no teeth. So: fibres stratified along the edge (never a bald stretch: each sits in its own slot, a little jittered), a
shorter under-pile that keeps the base opaque, tips staggered over the top third, a slight lean and bend per fibre, very
few long thin strays. The tile WRAPS in u (fibres leaving one side come in at the other): a fin's neighbour along the
outline starts with the same kind of fibre, so a fin's sides never show as a seam. Its page is 2048 x 512, not square: a
fin is about 8 mm wide and under 3 mm tall, so 512 rows keep the texels about square and it costs a quarter of a
square page. Attributes as atlas v3 (RGB, no alpha): R depth (a tuft's crest on the plane, its flanks deeper), G a
per-TUFT id with a small per-fibre offset (stratified over the tile: mean 0.5), B sideways slope. A pile's fibres
gather in small TUFTS, 1-2 mm: a fibre is far under a pixel at any game camera, so the tuft is the scale that reads, in
the outline's top (each tuft has its own height and lean and ends in a soft point) and in the band's tone (a per-fibre
id averages to 0.5 by mip 3, and the band was a flat paper ribbon: g5_groom/renders/s12_h.png beside the antler).
"""
import numpy as np
from PIL import Image, ImageDraw

from .roots import hkey

ROWS = ('dense', 'medium', 'sparse', 'wisp')
CHILDREN = (3, 2, 1, 1)         # jittered copies per member strand when atlas.children is on (off by default)
LOCK_SPACING_MM = (1.4, 1.9, 2.8, 4.0)   # one lock per this much card width, by row (the wisp row: 1-2 locks)
DETAIL_SHARE = (1.0, 0.7, 0.5, 1.0)      # the share of members also drawn as thin strands, by row
T_END = 0.97                    # no strand reaches the card's last 3 %: a card never ends in a blunt cut
ROOT_SPAN = 0.12                # strands start anywhere in the card's first 12 %: no straight root edge
# atlas v2 defaults (the style's atlas block overrides each): lists are per row, dense / medium / sparse / wisp
V2 = dict(fill=[0.36, 0.30, 0.22, 0.12],          # target mean coverage of a tile (the games' tiles: 0.06-0.32)
          strand_um=[90, 135, 12],                # spindle widths root / mid / tip (MetaHuman ~190, study T long ~250)
          root_span=0.35,                         # strands start anywhere in the tile's first 35 % (skewed early)
          tip_min=0.70,                           # a strand ends at 0.70-1.0 of T_END (skewed late: staggered tips)
          overlap=2.2,                            # the clumping's extra overlap over a random scatter (calibrated)
          lock_pull=[0.70, 0.65, 0.60, 0.30],     # pull toward the sub-lock's mean curve at the tip (x t^1.6)
          lock_mm=[1.4, 1.9, 2.8, 4.0],           # one sub-lock per this much card width
          tip_jitter=[0.10, 0.14, 0.20, 0.35],    # children's sideways spread at the tip (half widths, before the pull)
          ss=8, blur_px=0.35, attr_res=1024)
# atlas v3 defaults (coat round 3): lists per row, dense / medium / sparse / wisp
V3 = dict(V2,
          fill=[0.38, 0.33, 0.24, 0.13],          # the tile's mean coverage (kept near v2's: the LOD tone holds)
          overlap=2.3,                            # the bundling's extra overlap over a random scatter (calibrated on
                                                  # the octopus's shaggy: the rows' measured means against fill)
          sub=[2, 2, 2, 1],                       # sub-bundles per lock (a clump of clumps: thin inner partings)
          sub_off=0.48,                           # their centres, +- this x the lock's half width
          sub_sigma=0.30,                         # a strand's spread around its sub-bundle (x the lock's half width)
          lock_mm=[1.6, 2.1, 2.9, 4.0],           # one lock per this much card width
          lock_frac=[0.76, 0.66, 0.54, 0.45],     # a lock's width as a share of the spacing at mid-length (the rest:
                                                  # the parting)
          lock_root=0.20,                         # locks gather after this fraction of the length (spread before it)
          root_span=0.22,                         # strands start anywhere in the first 22 % (skewed early)
          lock_end=[0.82, 0.97],                  # each lock ends here (x T_END), staggered by a hash
          tip_min=0.72,                           # a strand ends at 0.72-1.0 of its lock's end
          core=0.58,                              # a strand's place across its lock: a gaussian of this sigma (x half
                                                  # width), so the core is denser and the flanks soft
          stray=[0.05, 0.07, 0.12, 0.22],         # the share of strands that leave their lock and cross the parting
          stray_mm=[1.0, 1.3, 1.8, 2.5],          # how far a stray drifts sideways by its tip
          depth_lock_mm=[1.1, 1.0, 0.9, 0.6],     # how far a lock's flank lies under its crest
          id_strand=0.22,                         # the per-strand offset around the lock's id (G)
          wave=0.0, wave_cyc=3.0)                 # (B3) a hair type's wave across the card: amplitude (card half widths)
                                                  # and cycles over the card's length (0: the fur's own small wiggle only)
# (B3, HAIR_FUR H5) THE FINE-STRAND PAGES PER HAIR TYPE: atlas v3 drawn for human hair (style atlas "hair_type"; the style's
# own atlas keys still override). Human hair on a card is a dense sheet of fine strands (HS §10: the games' pages draw
# strands 1/30-1/80 of a tile wide, 12-48 % of the covered texels solid; our fur pages drew 167-185 um strands, 66-70 %
# solid): drawn 55-85 um (MetaHuman's drawn widths are about twice a real hair's 70-78 um, HUMAN_PLAN §5.4), locks wide
# with thin partings (a combed sheet, not fur's tufts), few strays, and the ends nearly level for a cut style (tip_min,
# lock_end); the wave per type is the sideways bend the attribute page's B carries (the runtime's curl term reads it:
# the "sideways tangent channel" of H5)
HAIR_TYPES = {
    'straight': dict(strand_um=[55, 80, 22], fill=[0.62, 0.50, 0.34, 0.16], lock_mm=[2.4, 3.0, 3.8, 5.0],
                     lock_frac=[0.92, 0.86, 0.76, 0.60], sub=[3, 3, 2, 1], sub_off=0.55, sub_sigma=0.34, core=0.70,
                     lock_root=0.10, root_span=0.10, lock_end=[0.90, 0.99], tip_min=0.86,
                     stray=[0.02, 0.03, 0.05, 0.12], stray_mm=[0.8, 1.0, 1.4, 2.0], depth_lock_mm=[0.7, 0.6, 0.5, 0.4],
                     id_strand=0.30, overlap=1.8, wave=0.0, wave_cyc=3.0),
    'wavy': dict(strand_um=[55, 80, 22], fill=[0.58, 0.46, 0.32, 0.15], lock_mm=[2.6, 3.2, 4.0, 5.0],
                 lock_frac=[0.88, 0.82, 0.72, 0.58], sub=[3, 3, 2, 1], lock_root=0.12, root_span=0.12,
                 lock_end=[0.86, 0.99], tip_min=0.80, stray=[0.03, 0.04, 0.07, 0.14], id_strand=0.30, overlap=1.9,
                 wave=0.10, wave_cyc=3.5),
    'curly': dict(strand_um=[60, 85, 24], fill=[0.55, 0.44, 0.30, 0.14], lock_mm=[2.0, 2.6, 3.4, 4.5],
                  lock_frac=[0.80, 0.72, 0.62, 0.50], sub=[2, 2, 2, 1], lock_root=0.15, root_span=0.15,
                  lock_end=[0.80, 0.98], tip_min=0.75, stray=[0.06, 0.08, 0.12, 0.2], id_strand=0.30, overlap=2.0,
                  wave=0.22, wave_cyc=8.0),
    'coily': dict(strand_um=[60, 85, 26], fill=[0.55, 0.45, 0.32, 0.16], lock_mm=[1.6, 2.0, 2.8, 4.0],
                  lock_frac=[0.74, 0.66, 0.56, 0.46], sub=[2, 2, 1, 1], lock_root=0.15, root_span=0.18,
                  lock_end=[0.78, 0.97], tip_min=0.72, stray=[0.08, 0.10, 0.15, 0.25], id_strand=0.30, overlap=2.1,
                  wave=0.30, wave_cyc=16.0),
}
# (B3b) ATLAS v4, the human strand page (render_v4): lists per row, dense (inner cards) / medium / sparse / wisp (outer)
V4 = dict(fill=[0.55, 0.44, 0.30, 0.13],           # a tile's mean coverage (the games' 0.06-0.32 per page; a bob's card
                                                   # layers overlap 3-4 deep, so its inner rows run higher)
          strand_um=[60, 75, 8],                   # drawn width root / mid / tip (MetaHuman's 70/146/44; a sub-texel tip)
          clump_mm=[1.5, 1.9, 2.6, 3.4],           # one clump per this much card width
          clump_end=[0.86, 0.985],                 # each clump ends here (x T_END), skewed late: staggered, separated ends
                                                   # (c01's 0.70-0.97 left the tiles' last 15 % at 1 % coverage: the card's
                                                   # cut line rose by 2-4 cm)
          clump_lean=0.25,                         # a clump's sideways lean by its end (x the clump spacing)
          gather=0.22,                             # a clump has gathered from its root spread by this share of its length
          root_spread=1.45,                        # its half width at the root (x half the spacing: neighbours overlap)
          core=0.55,                               # a strand's place across its clump: a gaussian of this sigma
          root_span=[0.06, 0.18, 0.30, 0.35],      # strands start anywhere in this first share, per row (skewed early):
                                                   # the inner cards cover the scalp from their root, the outer cards'
                                                   # coverage ramps in over a third of their length so their root edges
                                                   # vanish into the layer below (e11: flat-topped shingle blocks)
          tip_min=0.84,                            # a strand ends at 0.84-1.0 of its clump's end
          taper=0.22,                              # the share of its own length a strand tapers over to its tip
          stray=[0.03, 0.05, 0.08, 0.18],          # the share of strands that leave their clump (a third run past its end)
          stray_mm=[0.9, 1.2, 1.6, 2.4],           # how far a stray drifts sideways by its tip
          stray_w=0.7,                             # a stray's width share
          wiggle=0.05,                             # a strand's own small sideways wiggle (x the clump's half width)
          depth_lock_mm=[0.6, 0.55, 0.5, 0.4],     # how far a clump's flank lies under its crest
          id_strand=0.25,                          # the per-strand offset around the clump's id (G)
          overlap=1.55,                            # the bundling's extra overlap over a random scatter
          ss=4, blur_px=0.35, attr_res=1024)
# the fin atlas's defaults (coat round 3): lists per row, dense / medium / sparse / wisp (the pile thinning toward its edge)
FIN = dict(fibres_mm=[15.0, 11.0, 7.0, 3.5],      # top fibres per mm of edge
           under_mm=[11.0, 8.0, 4.0, 1.5],        # the under-pile's fibres per mm (they keep the base opaque)
           strand_um=[60, 110, 14],               # spindle widths root / mid / tip
           tip_lo=[0.62, 0.55, 0.45, 0.35],       # a fibre ends in tip_lo .. tip_hi (skewed high): the staggered top
           tip_hi=0.96,
           under_tip=[0.28, 0.62],                # the under-pile's tips
           lean=0.22,                             # a fibre's own lean, +- mm sideways per mm of rise
           bend=0.08,                             # and its bend at the tip, +- as a share of the rise
           stray=0.012,                           # the share of top fibres that run on as a long thin stray ...
           stray_tip=1.0,                         # ... reaching the tile's top ...
           stray_width=0.55,                      # ... at this share of the width
           tuft_mm=[1.3, 1.6, 2.2, 3.0],          # one tuft per this much edge (the scale that survives the mips)
           tuft_top=[0.72, 1.0],                  # a tuft's top, as a share of the fibres' reach (hashed per tuft)
           tuft_point=0.14,                       # its flanks' fibres shorter by this: a tuft ends in a soft point
           tuft_gather=0.65,                      # how far a fibre closes on its tuft's axis by its tip
           tuft_lean=0.30,                        # a tuft's own lean, +- mm sideways per mm of rise, shared by its fibres
           tuft_depth=0.30,                       # how far a tuft's flank lies under its crest, x the pile's height
           id_fibre=0.16,                         # the per-fibre offset around the tuft's id (G)
           depth_mm=1.5,                          # what R's full scale means
           ss=6, blur_px=0.35, attr_div=4)        # supersampling, the page's blur, the attribute page's size divisor


def card_space(cards, c, P, Ls, K):
    """the member strands of card c in its frame: list of (u, v, depth_m) polylines, v in [0, T_END]; a member longer
    than the card is compressed to end at T_END instead of being cut there"""
    sp = cards.spines[c]
    T, B, N = cards.frames[c]
    w = cards.widths[c]
    nr = len(sp)
    tr = np.linspace(0, 1, nr)
    out = []
    for s in cards.members[c]:
        Q = P[s]
        t = np.linspace(0, 1, K) * min(Ls[s] / cards.Lc[c], T_END)
        C = np.stack([np.interp(t, tr, sp[:, d]) for d in range(3)], 1)
        Bt = np.stack([np.interp(t, tr, B[:, d]) for d in range(3)], 1)
        Nt = np.stack([np.interp(t, tr, N[:, d]) for d in range(3)], 1)
        wt = np.interp(t, tr, w)
        rel = Q - C
        u = np.sum(rel * Bt, 1) / np.maximum(0.5 * wt, 1e-6)
        dep = np.sum(rel * Nt, 1)
        out.append((u, t, dep, s))
    return out


def push_pull(img, mask, levels=12):
    """fill the texels outside mask from the inside (pull: masked averages down a pyramid; push: back up)"""
    h, w, c = img.shape
    pyr = [(img * mask[..., None], mask.astype(np.float64))]
    for _ in range(levels):
        a, m = pyr[-1]
        if a.shape[0] < 2 or a.shape[1] < 2:
            break
        hh, ww = a.shape[0] // 2 * 2, a.shape[1] // 2 * 2
        a2 = a[:hh, :ww].reshape(hh // 2, 2, ww // 2, 2, c).sum(axis=(1, 3))
        m2 = m[:hh, :ww].reshape(hh // 2, 2, ww // 2, 2).sum(axis=(1, 3))
        pyr.append((a2, m2))
    filled = None
    for a, m in reversed(pyr):
        cur = np.where(m[..., None] > 0, a / np.maximum(m[..., None], 1e-12), 0.0)
        if filled is not None:
            up = np.repeat(np.repeat(filled, 2, axis=0), 2, axis=1)
            up = np.pad(up, ((0, max(0, cur.shape[0] - up.shape[0])), (0, max(0, cur.shape[1] - up.shape[1])), (0, 0)),
                        mode='edge')[:cur.shape[0], :cur.shape[1]]
            cur = np.where(m[..., None] > 0, cur, up)
        filled = cur
    return np.where(mask[..., None], img, filled)


class Atlas:
    def __init__(self, cards, groom_npz, style):
        self.cards = cards
        self.z = groom_npz
        self.st = style.get('atlas', {})

    def layout(self, res=4096):
        wc = self.cards.width_classes * 1e3                      # mm
        nvar = 2
        cols = np.repeat(wc, nvar)
        xw = cols / cols.sum() * res
        x0 = np.concatenate([[0], np.cumsum(xw)])
        rh = res / len(ROWS)
        tiles = []
        for d in range(len(ROWS)):
            for wi in range(len(wc)):
                for v in range(nvar):
                    k = wi * nvar + v
                    tiles.append((x0[k] / res, d * rh / res, x0[k + 1] / res, (d + 1) * rh / res))
        self.tiles = np.array(tiles)                             # (n, 4) u0, v0, u1, v1 (glTF uv: v down)
        self.px_per_mm = res / cols.sum()
        self.res = res
        return self

    def _pick(self, d, wi, v, n_cards):
        """cards of density class d (wisp = 3), width class wi, variant v; the ones nearest the class's median member
        count, a few overlaid"""
        c = self.cards
        m = (c.layer == d) & (c.wclass == wi)
        if (m & (c.variant == v)).sum() >= n_cards:
            m &= c.variant == v
        if m.sum() == 0:
            m = c.wclass == wi
        idx = np.nonzero(m)[0]
        cnt = np.array([len(c.members[i]) for i in idx])
        med = np.median(cnt)
        order = idx[np.argsort(np.abs(cnt - med) + hkey(41 + v, idx, d, ch=3))]
        return order[:n_cards]

    def _locks(self, curves, d, wmm):
        """the members of a tile merged into locks: grouped by root u into n = width / LOCK_SPACING_MM[row] groups (1-2
        on the wisp row), each lock the parametric mean of its members' curves (u, v, depth) over 24 samples, ending at
        its members' 80th-percentile end, flagged as a lock (drawn with atlas.lock_um, scaled to the lock spacing)"""
        if not curves:
            return []
        n = int(np.clip(round(wmm / LOCK_SPACING_MM[d]), 1, 10)) if d < 3 else min(2, len(curves))
        n = min(n, len(curves))
        order = np.argsort([q[0][0] for q in curves])
        groups = np.array_split(order, n)
        tg = np.linspace(0.0, 1.0, 24)
        out = []
        for gi, g in enumerate(groups):
            us, ts, ds, ends = [], [], [], []
            for i in g:
                u, t, dep, s = curves[i]
                f = np.linspace(0.0, 1.0, len(t))
                us.append(np.interp(tg, f, u))
                ts.append(np.interp(tg, f, t))
                ds.append(np.interp(tg, f, dep))
                ends.append(t[-1])
            um, tm, dm = np.mean(us, 0), np.mean(ts, 0), np.mean(ds, 0)
            # the lock reaches its members' 80th-percentile end (a few long members carry on as strands past it)
            tend = float(np.quantile(ends, 0.8))
            tm = tm[0] + (tm - tm[0]) * (tend - tm[0]) / max(tm[-1] - tm[0], 1e-6)
            sid = float(hkey(67, int(curves[g[0]][3]), gi, ch=1))
            out.append((um, tm, dm - 0.2e-3, sid, True))
        return out

    def render(self, ss=4, out_res=2048, attr_res=512, depth_mm=None, log=print):
        st = self.st
        c = self.cards
        P = self.z['points'].astype(np.float64)
        Ls = self.z['length'].astype(np.float64)
        rnd = self.z['rnd'].astype(np.float64)
        K = P.shape[1]
        res = self.res
        w_um = st.get('width_um', [60, 110, 30])
        depth_mm = depth_mm or st.get('depth_mm', 4.0)
        cov = np.zeros((res, res), np.float32)
        attr = np.zeros((attr_res, attr_res, 4), np.float32)
        amask = np.zeros((attr_res, attr_res), bool)
        nvar = 2
        self.tile_info = []
        for ti, (u0, v0, u1, v1) in enumerate(self.tiles):
            d = ti // (len(c.width_classes) * nvar)
            wi = (ti // nvar) % len(c.width_classes)
            var = ti % nvar
            picks = self._pick(min(d, 3), wi, var, st.get('cards_per_tile', [1, 1, 1, 1])[d])
            curves = []
            for ci in picks:
                cs = card_space(c, ci, P, Ls, K)
                if d == 3:                                       # wisp: a few members only, the longest
                    cs = sorted(cs, key=lambda q: -q[1][-1])[:max(2, len(cs) // 5)]
                curves += cs
            # LOCKS: the members merged into a few tapered locks (grouped by their root position across the card, one
            # lock per LOCK_SPACING_MM[row] of card width), each the mean curve of its members; then the members
            # themselves as thin strands on top (the detail and the flyaways past the lock tips)
            wmm = float(c.width_classes[wi] * 1e3)
            strands = self._locks(curves, d, wmm)
            nch = CHILDREN[d] if self.st.get('children', False) else 1
            for (u, t, dep, s) in curves:
                if hkey(61, s, 0, ch=7) > DETAIL_SHARE[d]:
                    continue
                for j in range(nch):
                    h1 = hkey(53, s, j, ch=1)
                    h2 = hkey(53, s, j, ch=2)
                    h3 = hkey(53, s, j, ch=3)
                    if j == 0:
                        du0, du1, lf = 0.0, 0.0, 1.0
                    else:
                        du0 = (h1 - 0.5) * 0.35
                        du1 = (h2 - 0.5) * (0.25 + 0.35 * (d >= 1))
                        lf = 0.55 + 0.45 * h3
                    uu = u + du0 + (du1 - du0) * (t / max(t[-1], 1e-6))
                    # soft sides: strands out at the card's edges end sooner, so its outline dissolves
                    edge = np.clip((np.abs(uu[0]) - 0.75) / 0.25, 0.0, 1.0)
                    lf = lf * (1.0 - 0.35 * edge)
                    # staggered roots: each strand starts somewhere in the card's first ROOT_SPAN, so the root end is
                    # never one straight line across the card (shingled cards would show it as a plank's edge)
                    # (vs, never v0: v0 is the tile's own top edge in this loop)
                    vs = ROOT_SPAN * hkey(59, s, j, ch=4)
                    tt = vs + t * lf * (1.0 - vs)
                    strands.append((uu, tt, dep + (h3 - 0.5) * 0.4e-3, rnd[s] if j == 0 else h1, False))
            # draw: coverage at res * ss over the tile, attributes on the attr page
            x0, y0 = u0 * res, v0 * res
            tw, th = (u1 - u0) * res, (v1 - v0) * res
            W, H = int(round(tw * ss)), int(round(th * ss))
            img = Image.new('L', (W, H), 0)
            dr = ImageDraw.Draw(img)
            ax0, ay0 = u0 * attr_res, v0 * attr_res
            aw, ah = (u1 - u0) * attr_res, (v1 - v0) * attr_res
            apage = Image.new('RGBA', (max(int(round(aw)), 1), max(int(round(ah)), 1)), (0, 0, 0, 0))
            adr = ImageDraw.Draw(apage)
            px_mm = self.px_per_mm * ss
            # painter's order: deepest (toward the skin) first
            strands.sort(key=lambda q: float(np.mean(q[2])))
            # the tile spans the card's full width: the strands' 95th-percentile offset lands at 0.88 of the half
            # width, and a strand that leaves the tile sideways ends there (never squeezed into a dense edge band)
            allu = np.concatenate([np.abs(q[0]) for q in strands]) if strands else np.ones(1)
            usc = 0.88 / max(float(np.quantile(allu, 0.95)), 1e-6)
            kept = []
            for (uu, tt, dep, sid, lock) in strands:
                uu = uu * usc
                out_ = np.nonzero(np.abs(uu) > 0.97)[0]
                n_in = int(out_[0]) if len(out_) else len(uu)
                if n_in >= 2:
                    kept.append((uu[:n_in], tt[:n_in], dep[:n_in], sid, lock))
            strands = kept
            # COVERAGE AS LOCKS (the runtime builder's evidence, 10-29: at one sample per pixel and no TAA a 65 um
            # strand is a tenth of a pixel at the hero distance; its mips wash out and the clip cuts the tails): each
            # member strand is drawn as a tapered lock (style atlas.lock_um: root, mid, tip), its children as thinner
            # strands (atlas.width_um), both as filled ribbons; the fine strand structure lives in the attribute page
            lock_um = st.get('lock_um', [900, 600, 120])
            # a lock's root width: the style's, but never more than 0.8 of the row's lock spacing (gaps between locks)
            R_um = min(lock_um[0], 800.0 * LOCK_SPACING_MM[d])
            for (uu, tt, dep, sid, lock) in strands:
                X = (np.clip(uu, -0.97, 0.97) * 0.5 + 0.5) * W
                Y = np.clip(tt, 0, 1) * H
                n = len(X)
                tn = (tt - tt[0]) / max(tt[-1] - tt[0], 1e-6)
                if lock:                                         # rounded root, widest at 12 %, pointed tip
                    prof = np.interp(tn, [0.0, 0.12, 0.45, 1.0],
                                     [0.55 * R_um, R_um, R_um * lock_um[1] / lock_um[0], lock_um[2]])
                else:
                    prof = np.interp(tn, [0.0, 0.45, 1.0], w_um)
                prof = np.maximum(prof * 1e-3 * px_mm, 1.0)      # px, full width
                d2 = np.stack([np.gradient(X), np.gradient(Y)], 1)
                d2 /= np.maximum(np.linalg.norm(d2, axis=1, keepdims=True), 1e-9)
                nrm2 = np.stack([-d2[:, 1], d2[:, 0]], 1) * (0.5 * prof)[:, None]
                left = np.stack([X, Y], 1) + nrm2
                right = np.stack([X, Y], 1) - nrm2
                poly = [tuple(p) for p in left] + [tuple(p) for p in right[::-1]]
                dr.polygon(poly, fill=255)
                # attributes (no AA): depth, id, root-to-tip, sideways tangent
                AX = (np.clip(uu, -0.97, 0.97) * 0.5 + 0.5) * apage.width
                AY = np.clip(tt, 0, 1) * apage.height
                for k in range(n - 1):
                    dz = 0.5 + 0.5 * np.clip(dep[k] / (depth_mm * 1e-3), -1, 1)
                    du = (uu[k + 1] - uu[k]) / max(tt[k + 1] - tt[k], 1e-6) * (0.5 * c.width_classes[wi] /
                                                                                 max(c.Lc.mean(), 1e-6))
                    col = (int(255 * dz), int(255 * sid), int(255 * tt[k]), int(255 * (0.5 + 0.5 * np.clip(du, -1, 1))))
                    adr.line([(AX[k], AY[k]), (AX[k + 1], AY[k + 1])], fill=col, width=1)
            a = np.asarray(img, np.float32) / 255.0
            a = a[:H // ss * ss, :W // ss * ss].reshape(H // ss, ss, W // ss, ss).mean(axis=(1, 3))
            ys, xs = int(round(y0)), int(round(x0))
            hh, ww = min(a.shape[0], res - ys), min(a.shape[1], res - xs)
            cov[ys:ys + hh, xs:xs + ww] = np.maximum(cov[ys:ys + hh, xs:xs + ww], a[:hh, :ww])
            ap = np.asarray(apage, np.float32) / 255.0
            ays, axs = int(round(ay0)), int(round(ax0))
            hh, ww = min(ap.shape[0], attr_res - ays), min(ap.shape[1], attr_res - axs)
            sub = ap[:hh, :ww]
            m = sub[..., 3] > 0
            attr[ays:ays + hh, axs:axs + ww][m] = sub[m]
            amask[ays:ays + hh, axs:axs + ww] |= m
            self.tile_info.append(dict(tile=ti, row=ROWS[d], width_mm=round(float(c.width_classes[wi] * 1e3), 2),
                                       variant=var, cards=[int(x) for x in picks], strands=len(strands),
                                       coverage_mean=round(float(a.mean()), 3)))
        # the delivered coverage page: 4096 -> 2048 box (already 4x4 supersampled per 4096 texel)
        f = res // out_res
        self.cov4096 = cov
        self.cov = cov.reshape(out_res, f, out_res, f).mean(axis=(1, 3))
        self.attr = push_pull(attr.astype(np.float64), amask).astype(np.float32)
        self.attr_mask = amask
        log(f'[atlas] {len(self.tiles)} tiles, {self.px_per_mm:.1f} texels/mm at {res} '
            f'({self.px_per_mm * out_res / res:.1f} at {out_res}); mean coverage per row '
            + ', '.join(f'{ROWS[d]} {np.mean([t["coverage_mean"] for t in self.tile_info if t["row"] == ROWS[d]]):.2f}'
                        for d in range(len(ROWS))))
        return self

    def config_v2(self):
        """the v2 parameters: V2's defaults, the style's atlas block over them"""
        cfg = dict(V2)
        cfg.update({k: v for k, v in self.st.items() if k in V2})
        return cfg

    def render_v2(self, out_res=2048, log=print):
        """ATLAS v2 (the module doc): every tile drawn as fine strands from its cards' members, grouped into sub-locks;
        coverage = true area coverage at out_res (one channel, ss x ss supersampled polygons, box-filtered, a touch of
        blur so edges rise over ~1.5 texels as the games' do); attributes at attr_res, each texel its topmost strand's
        depth / id / own root-to-tip / sideways slope, push-pull dilated"""
        from scipy import ndimage
        st = self.st
        cfg = self.config_v2()
        c = self.cards
        P = self.z['points'].astype(np.float64)
        Ls = self.z['length'].astype(np.float64)
        K = P.shape[1]
        ss = int(cfg['ss'])
        attr_res = int(cfg['attr_res'])
        depth_mm = st.get('depth_mm', 4.0)
        um = np.asarray(cfg['strand_um'], np.float64)
        nvar = 2
        nw = len(c.width_classes)
        px_mm = self.px_per_mm * out_res / self.res          # texels per mm across, at the delivered size
        lc_mm = float(c.Lc.mean() * 1e3)
        cov = np.zeros((out_res, out_res), np.float32)
        attr = np.zeros((attr_res, attr_res, 4), np.float32)
        amask = np.zeros((attr_res, attr_res), bool)
        self.tile_info = []
        n_tot = 0
        for ti, (u0, v0, u1, v1) in enumerate(self.tiles):
            d = ti // (nw * nvar)
            wi = (ti // nvar) % nw
            var = ti % nvar
            picks = self._pick(min(d, 3), wi, var, st.get('cards_per_tile', [1, 1, 1, 1])[d])
            curves = []
            for ci in picks:
                cs = card_space(c, ci, P, Ls, K)
                if d == 3:                                       # wisp: a few members only, the longest
                    cs = sorted(cs, key=lambda q: -q[1][-1])[:max(2, len(cs) // 5)]
                curves += cs
            if not curves:
                continue
            wmm = float(c.width_classes[wi] * 1e3)
            # the members' 95th-percentile offset lands at 0.78 of the half width; children spread a little past it
            allu = np.concatenate([np.abs(q[0]) for q in curves])
            usc = 0.78 / max(float(np.quantile(allu, 0.95)), 1e-6)
            M = len(curves)
            pg = np.linspace(0.0, 1.0, 32)
            # each member as a function of its own parameter p in [0, 1]: u (scaled), tile v, depth
            mem = []
            for (u, t, dep, s) in curves:
                f = np.linspace(0.0, 1.0, len(t))
                mem.append((np.interp(pg, f, u) * usc, np.interp(pg, f, t), np.interp(pg, f, dep), int(s)))
            # SUB-LOCKS: the members grouped by their root's u, each lock the mean curve of its members
            nl = int(np.clip(round(wmm / cfg['lock_mm'][d]), 1, 12)) if d < 3 else min(2, M)
            nl = max(1, min(nl, M))
            order = np.argsort([m_[0][0] for m_ in mem])
            lock_of = np.zeros(M, np.int64)
            locks = []
            for gi, g in enumerate(np.array_split(order, nl)):
                lock_of[g] = gi
                locks.append(np.mean([mem[i][0] for i in g], 0))
            # how many fine strands: n (w_mid / W) lambda ~ -ln(1 - fill) for a random scatter, x overlap for the
            # clumping's extra overlap; lambda ~ 0.62, a strand's mean length share of the tile (staggered ends)
            n_fine = int(np.clip(round(-np.log(1.0 - cfg['fill'][d]) * wmm / (um[1] * 1e-3 * 0.62) * cfg['overlap']),
                                 4, 900))
            strands = []
            for k in range(n_fine):
                mi = k % M
                j = k // M
                um_, vm_, dm_, s = mem[mi]
                h = [hkey(91 + q, s, j, ch=q + 1) for q in range(9)]
                # staggered root (skewed early: ~1/4 of the strands start in the tile's first 5 %) and staggered tip
                # (skewed late), the member's shape stretched over [vs, ve] (its wiggle kept, its length not: a card
                # is as long as its members' 85th percentile, and members ending early left the first pass's tile
                # tips empty)
                vs = cfg['root_span'] * h[0] ** 1.5
                edge = np.clip((abs(um_[0]) - 0.70) / 0.25, 0.0, 1.0)      # soft sides: edge strands end sooner
                lf = (cfg['tip_min'] + (1.0 - cfg['tip_min']) * h[1] ** 0.5) * (1.0 - 0.25 * edge)
                ve = max(T_END * lf, vs + 0.15)
                f = np.linspace(0.0, 1.0, 24)
                v = vs + f * (ve - vs)
                p = f                                                       # the member's own parameter
                ur = (h[2] - 0.5) * 2.0 / nl if j > 0 else 0.0              # spread across the lock at the root
                ut = (h[3] - 0.5) * 2.0 * cfg['tip_jitter'][d]
                ufree = np.interp(p, pg, um_) + ur * (1.0 - f) + ut * f
                w = cfg['lock_pull'][d] * f ** 1.6
                u = (1.0 - w) * ufree + w * np.interp(p, pg, locks[lock_of[mi]])
                dep = np.interp(p, pg, dm_) + (h[4] - 0.5) * 0.6e-3 * (1.0 - w)
                wf = 0.75 + 0.5 * h[5]
                prof = np.interp(f, [0.0, 0.08, 0.40, 0.75, 1.0],
                                 [0.35 * um[0], um[0], um[1], 0.55 * um[1], um[2]]) * wf      # um, full width
                # a strand that leaves the tile sideways ends there (never squashed along the tile's edge)
                out_ = np.nonzero(np.abs(u) > 0.97)[0]
                n_in = int(out_[0]) if len(out_) else len(u)
                if n_in < 4:
                    continue
                if n_in < len(u):                                           # tapered where it leaves, not blunt
                    prof = prof.copy()
                    prof[n_in - 3:n_in] *= np.array([0.6, 0.3, 0.08])
                # the attribute page's root-to-tip: 0 at the CARD's root, 1 at this strand's own tip (a strand that
                # starts staggered is deep in the coat there, so its root shade follows the card; its light tip is
                # its own)
                rt = v / max(float(v[n_in - 1]), 1e-6)
                strands.append((u[:n_in], v[:n_in], dep[:n_in], prof[:n_in], h[6], rt[:n_in]))
            n_tot += len(strands)
            # draw: coverage at ss x the delivered size over the tile, attributes on the attribute page
            x0, y0 = u0 * out_res, v0 * out_res
            tw, th = (u1 - u0) * out_res, (v1 - v0) * out_res
            W, H = int(np.ceil(tw)) * ss, int(np.ceil(th)) * ss
            img = Image.new('L', (W, H), 0)
            dr = ImageDraw.Draw(img)
            ax0, ay0 = u0 * attr_res, v0 * attr_res
            aw, ah = max(int(round((u1 - u0) * attr_res)), 1), max(int(round((v1 - v0) * attr_res)), 1)
            apage = Image.new('RGBA', (aw, ah), (0, 0, 0, 0))
            adr = ImageDraw.Draw(apage)
            strands.sort(key=lambda q: float(np.mean(q[2])))          # painter's order: deepest first
            for (u, v, dep, prof, sid, f) in strands:
                X = (np.clip(u, -0.97, 0.97) * 0.5 + 0.5) * tw * ss
                Y = np.clip(v, 0.0, 1.0) * th * ss
                wpx = prof * 1e-3 * px_mm * ss                         # full width in supersampled pixels
                d2 = np.stack([np.gradient(X), np.gradient(Y)], 1)
                d2 /= np.maximum(np.linalg.norm(d2, axis=1, keepdims=True), 1e-9)
                nrm = np.stack([-d2[:, 1], d2[:, 0]], 1) * (0.5 * wpx)[:, None]
                ctr = np.stack([X, Y], 1)
                poly = [tuple(q) for q in ctr + nrm] + [tuple(q) for q in (ctr - nrm)[::-1]]
                dr.polygon(poly, fill=255)
                # attributes (no AA, topmost wins): depth, id, the strand's own root-to-tip, sideways slope
                AX = (np.clip(u, -0.97, 0.97) * 0.5 + 0.5) * aw
                AY = np.clip(v, 0.0, 1.0) * ah
                lw = np.maximum(1, np.round(prof * 1e-3 * px_mm * attr_res / out_res)).astype(int)
                dz = 0.5 + 0.5 * np.clip(dep / (depth_mm * 1e-3), -1.0, 1.0)
                slope = np.gradient(u) / np.maximum(np.gradient(v), 1e-6) * (0.5 * wmm / lc_mm)
                sw = 0.5 + 0.5 * np.clip(slope, -1.0, 1.0)
                for q in range(len(u) - 1):
                    col = (int(255 * dz[q]), int(255 * sid), int(255 * f[q]), int(255 * sw[q]))
                    adr.line([(AX[q], AY[q]), (AX[q + 1], AY[q + 1])], fill=col, width=int(lw[q]))
            a = np.asarray(img, np.float32) / 255.0
            a = a.reshape(H // ss, ss, W // ss, ss).mean(axis=(1, 3))
            if cfg['blur_px'] > 0:
                a = ndimage.gaussian_filter(a, cfg['blur_px'])
            ys, xs = int(round(y0)), int(round(x0))
            hh, ww = min(a.shape[0], out_res - ys, int(round(th))), min(a.shape[1], out_res - xs, int(round(tw)))
            cov[ys:ys + hh, xs:xs + ww] = np.maximum(cov[ys:ys + hh, xs:xs + ww], a[:hh, :ww])
            ap = np.asarray(apage, np.float32) / 255.0
            ays, axs = int(round(ay0)), int(round(ax0))
            hh, ww = min(ap.shape[0], attr_res - ays), min(ap.shape[1], attr_res - axs)
            sub = ap[:hh, :ww]
            m = sub[..., 3] > 0
            attr[ays:ays + hh, axs:axs + ww][m] = sub[m]
            amask[ays:ays + hh, axs:axs + ww] |= m
            prof_v = a.mean(1)
            self.tile_info.append(dict(tile=ti, row=ROWS[d], width_mm=round(wmm, 2), variant=var,
                                       cards=[int(x) for x in picks], members=M, strands=len(strands), locks=nl,
                                       coverage_mean=round(float(a.mean()), 3),
                                       coverage_max_band_at=round(float((np.argmax(prof_v) + 0.5) / len(prof_v)), 3)))
        self.cov4096 = None
        self.cov = cov
        self.attr = push_pull(attr.astype(np.float64), amask).astype(np.float32)
        self.attr_mask = amask
        self.v2 = dict(cfg, strands=n_tot, px_per_mm=round(float(px_mm), 2))
        log(f'[atlas v2] {len(self.tiles)} tiles, {n_tot} fine strands, {px_mm:.1f} texels/mm at {out_res}; mean '
            'coverage per row ' + ', '.join(
                f'{ROWS[d]} {np.mean([t["coverage_mean"] for t in self.tile_info if t["row"] == ROWS[d]]):.2f}'
                for d in range(len(ROWS))) + f'; attributes {attr_res}^2')
        return self

    def config_v3(self):
        """the v3 parameters: V3's defaults, the style's atlas block over them"""
        cfg = dict(V3)
        if self.st.get('hair_type'):                    # (B3) a hair type's page, under the style's own keys
            cfg.update(HAIR_TYPES[self.st['hair_type']])
        cfg.update({k: v for k, v in self.st.items() if k in V3})
        return cfg

    def render_v3(self, out_res=2048, log=print):
        """ATLAS v3 (the module doc): every tile drawn as LOCKS of fine strands with partings between them; coverage =
        true area coverage at out_res (one channel); attributes at attr_res, RGB (R depth as the clump's shape, G the
        lock's id + a small per-strand offset, B the sideways slope), each texel its topmost strand's, push-pull dilated"""
        st = self.st
        cfg = self.config_v3()
        c = self.cards
        P = self.z['points'].astype(np.float64)
        Ls = self.z['length'].astype(np.float64)
        K = P.shape[1]
        ss = int(cfg['ss'])
        attr_res = int(cfg['attr_res'])
        depth_mm = float(st.get('depth_mm', 2.0))
        um = np.asarray(cfg['strand_um'], np.float64)
        nvar = 2
        nw = len(c.width_classes)
        px_mm = self.px_per_mm * out_res / self.res
        lc_mm = float(c.Lc.mean() * 1e3)
        cov = np.zeros((out_res, out_res), np.float32)
        attr = np.zeros((attr_res, attr_res, 4), np.float32)
        amask = np.zeros((attr_res, attr_res), bool)
        self.tile_info = []
        n_tot = 0
        fq = np.linspace(0.0, 1.0, 28)
        span = 1.70                                              # lock centres span this much of the card's [-1, 1]
        for ti, (u0, v0, u1, v1) in enumerate(self.tiles):
            d = ti // (nw * nvar)
            wi = (ti // nvar) % nw
            var = ti % nvar
            picks = self._pick(min(d, 3), wi, var, st.get('cards_per_tile', [1, 1, 1, 1])[d])
            curves = []
            for ci in picks:
                cs = card_space(c, ci, P, Ls, K)
                if d == 3:
                    cs = sorted(cs, key=lambda q: -q[1][-1])[:max(2, len(cs) // 5)]
                curves += cs
            if not curves:
                continue
            wmm = float(c.width_classes[wi] * 1e3)
            allu = np.concatenate([np.abs(q[0]) for q in curves])
            usc = 0.78 / max(float(np.quantile(allu, 0.95)), 1e-6)
            M = len(curves)
            pg = np.linspace(0.0, 1.0, 32)
            mem = []
            for (u, t, dep, s) in curves:
                f = np.linspace(0.0, 1.0, len(t))
                mem.append((np.interp(pg, f, u) * usc, np.interp(pg, f, t), np.interp(pg, f, dep), int(s)))
            # LOCKS: evenly spaced root places across the card (a little jittered), each following the mean path (the
            # groom's own wiggle and lean) of the members rooted nearest it, offset to start at its own place
            nl = int(np.clip(round(wmm / cfg['lock_mm'][d]), 1, 10)) if d < 3 else int(min(2, M))
            nl = max(1, nl)
            sp_l = span / nl
            cen = -0.5 * span + (np.arange(nl) + 0.5) * sp_l
            cen = cen + (np.array([hkey(97 + var, ti, k, ch=1) for k in range(nl)]) - 0.5) * 0.25 * sp_l
            r0 = np.array([m_[0][0] for m_ in mem])
            near = np.argmin(np.abs(r0[:, None] - cen[None, :]), axis=1)
            paths = []
            for L in range(nl):
                g = np.nonzero(near == L)[0]
                if len(g) == 0:
                    g = np.array([int(np.argmin(np.abs(r0 - cen[L])))])
                pu = np.mean([mem[i][0] for i in g], 0)
                pv = np.mean([mem[i][1] for i in g], 0)
                pd = np.mean([mem[i][2] for i in g], 0)
                pv = np.maximum.accumulate(pv)                   # monotone in v for interpolation
                paths.append((cen[L] + 0.8 * (pu - pu[0]), pv, pd))
            W = 0.5 * cfg['lock_frac'][d] * sp_l                  # a lock's half width at mid-length (card units)
            ve_lock = T_END * (cfg['lock_end'][0] + (cfg['lock_end'][1] - cfg['lock_end'][0]) *
                               np.array([hkey(101 + var, ti, k, ch=2) for k in range(nl)]))
            # each lock's id: stratified over the tile (its mean is 0.5), permuted
            perm = np.argsort([hkey(103 + var, ti, k, ch=3) for k in range(nl)])
            gid = (perm + 0.5) / nl
            # how many fine strands: as v2 (a random scatter's -ln(1 - fill) x the overlap the bundling adds)
            n_fine = int(np.clip(round(-np.log(1.0 - cfg['fill'][d]) * wmm / (um[1] * 1e-3 * 0.62) * cfg['overlap']),
                                 4, 1200))
            dl = cfg['depth_lock_mm'][d] * 1e-3
            strands = []
            for k in range(n_fine):
                L = k % nl
                j = k // nl
                h = [hkey(111 + q, ti * 977 + L, j, ch=q + 1) for q in range(10)]
                pu, pv, pd = paths[L]
                z = np.sqrt(-2.0 * np.log(max(h[0], 1e-9))) * np.cos(2.0 * np.pi * h[1])
                nsub = int(cfg['sub'][d])
                if nsub > 1:                                       # a clump of clumps: the strand's sub-bundle
                    sb = j % nsub
                    sc = cfg['sub_off'] * (2.0 * sb / (nsub - 1) - 1.0)
                    s0 = float(np.clip(sc + z * cfg['sub_sigma'], -1.15, 1.15))
                else:
                    s0 = float(np.clip(z * cfg['core'], -1.15, 1.15))
                stray = h[2] < cfg['stray'][d]
                vs = cfg['root_span'] * h[3] ** 1.5
                ve = max(ve_lock[L] * (cfg['tip_min'] + (1.0 - cfg['tip_min']) * h[4] ** 0.5), vs + 0.15)
                v = vs + fq * (ve - vs)
                q = v / ve_lock[L]
                prof_w = np.interp(q, [0.0, cfg['lock_root'], 0.45, 0.75, 0.92, 1.0], [1.30, 1.10, 1.0, 0.62, 0.22, 0.05])
                s = np.full(len(v), s0)
                drift = np.zeros(len(v))
                if stray:                                          # leaves its lock for the parting beside it
                    side = 1.0 if h[5] > 0.5 else -1.0
                    amp = side * cfg['stray_mm'][d] * (0.6 + 0.4 * h[6]) / max(0.5 * wmm, 1e-6)   # mm -> card units
                    drift = amp * np.clip((q - cfg['lock_root']) / 0.7, 0.0, 1.0) ** 1.5
                wig = 0.06 * W * np.sin(2.0 * np.pi * ((0.5 + h[7]) * fq + h[8]))
                if cfg['wave'] > 0:                            # (B3) the hair type's wave, per lock in phase
                    wig = wig + cfg['wave'] * np.sin(2.0 * np.pi * (cfg['wave_cyc'] * (0.85 + 0.3 * h[7]) * fq
                                                                    + hkey(149, ti * 977 + L, 0, ch=1)))
                u = np.interp(v, pv, pu) + s * W * prof_w + drift + wig
                # depth: the clump's shape relative to its own crest (a strand at the lock's centre on the card plane,
                # its flanks deeper as (offset / half width)^2, growing in as the lock forms; a stray deeper still)
                rel = np.minimum(np.abs(s) + np.abs(drift) / max(W, 1e-6), 1.6)
                form = np.clip(q / max(cfg['lock_root'] * 1.5, 1e-3), 0.0, 1.0)
                dep = (-dl * np.minimum(rel * rel, 1.6) * form - (0.3 * dl if stray else 0.0)
                       + 0.1e-3 * (hkey(137, ti * 977 + L, j, ch=1) - 0.5))
                wf = 0.75 + 0.5 * h[9]
                prof = np.interp(fq, [0.0, 0.08, 0.40, 0.75, 1.0], [0.35 * um[0], um[0], um[1], 0.55 * um[1], um[2]]) * wf
                out_ = np.nonzero(np.abs(u) > 0.97)[0]
                n_in = int(out_[0]) if len(out_) else len(u)
                if n_in < 4:
                    continue
                if n_in < len(u):
                    prof = prof.copy()
                    prof[n_in - 3:n_in] *= np.array([0.6, 0.3, 0.08])
                sid = float(np.clip(gid[L] + cfg['id_strand'] * (hkey(131, ti * 977 + L, j, ch=1) - 0.5), 0.0, 1.0))
                strands.append((u[:n_in], v[:n_in], dep[:n_in], prof[:n_in], sid))
            n_tot += len(strands)
            x0, y0 = u0 * out_res, v0 * out_res
            tw, th = (u1 - u0) * out_res, (v1 - v0) * out_res
            Wp, Hp = int(np.ceil(tw)) * ss, int(np.ceil(th)) * ss
            img = Image.new('L', (Wp, Hp), 0)
            dr = ImageDraw.Draw(img)
            ax0, ay0 = u0 * attr_res, v0 * attr_res
            aw, ah = max(int(round((u1 - u0) * attr_res)), 1), max(int(round((v1 - v0) * attr_res)), 1)
            apage = Image.new('RGBA', (aw, ah), (0, 0, 0, 0))
            adr = ImageDraw.Draw(apage)
            strands.sort(key=lambda qq: float(np.mean(qq[2])))      # painter's order: deepest first, crests on top
            for (u, v, dep, prof, sid) in strands:
                X = (np.clip(u, -0.97, 0.97) * 0.5 + 0.5) * tw * ss
                Y = np.clip(v, 0.0, 1.0) * th * ss
                wpx = prof * 1e-3 * px_mm * ss
                d2 = np.stack([np.gradient(X), np.gradient(Y)], 1)
                d2 /= np.maximum(np.linalg.norm(d2, axis=1, keepdims=True), 1e-9)
                nrm = np.stack([-d2[:, 1], d2[:, 0]], 1) * (0.5 * wpx)[:, None]
                ctr = np.stack([X, Y], 1)
                poly = [tuple(qq) for qq in ctr + nrm] + [tuple(qq) for qq in (ctr - nrm)[::-1]]
                dr.polygon(poly, fill=255)
                AX = (np.clip(u, -0.97, 0.97) * 0.5 + 0.5) * aw
                AY = np.clip(v, 0.0, 1.0) * ah
                lw = np.maximum(1, np.round(prof * 1e-3 * px_mm * attr_res / out_res)).astype(int)
                dz = 0.5 + 0.5 * np.clip(dep / (depth_mm * 1e-3), -1.0, 1.0)
                slope = np.gradient(u) / np.maximum(np.gradient(v), 1e-6) * (0.5 * wmm / lc_mm)
                sw = 0.5 + 0.5 * np.clip(slope, -1.0, 1.0)
                for qq in range(len(u) - 1):
                    col = (int(255 * dz[qq]), int(255 * sid), int(255 * sw[qq]), 255)
                    adr.line([(AX[qq], AY[qq]), (AX[qq + 1], AY[qq + 1])], fill=col, width=int(lw[qq]))
            a = np.asarray(img, np.float32) / 255.0
            a = a.reshape(Hp // ss, ss, Wp // ss, ss).mean(axis=(1, 3))
            if cfg['blur_px'] > 0:
                from scipy import ndimage
                a = ndimage.gaussian_filter(a, cfg['blur_px'])
            ys, xs = int(round(y0)), int(round(x0))
            hh, ww = min(a.shape[0], out_res - ys, int(round(th))), min(a.shape[1], out_res - xs, int(round(tw)))
            cov[ys:ys + hh, xs:xs + ww] = np.maximum(cov[ys:ys + hh, xs:xs + ww], a[:hh, :ww])
            ap = np.asarray(apage, np.float32) / 255.0
            ays, axs = int(round(ay0)), int(round(ax0))
            hh2, ww2 = min(ap.shape[0], attr_res - ays), min(ap.shape[1], attr_res - axs)
            sub = ap[:hh2, :ww2]
            m = sub[..., 3] > 0
            attr[ays:ays + hh2, axs:axs + ww2][m] = sub[m]
            amask[ays:ays + hh2, axs:axs + ww2] |= m
            a_t = a[:hh, :ww]
            mid = a_t[int(0.35 * hh):int(0.65 * hh)].mean(0)       # the coverage across the card at mid-length
            prof_v = a_t.mean(1)
            self.tile_info.append(dict(tile=ti, row=ROWS[d], width_mm=round(wmm, 2), variant=var,
                                       cards=[int(x) for x in picks], members=M, strands=len(strands), locks=nl,
                                       coverage_mean=round(float(a_t.mean()), 3),
                                       mid_cross_p10_p90=np.round(np.percentile(mid, [10, 90]), 3).tolist(),
                                       coverage_max_band_at=round(float((np.argmax(prof_v) + 0.5) / len(prof_v)), 3)))
        self.cov4096 = None
        self.cov = cov
        attr[..., 3] = 1.0
        self.attr = push_pull(attr.astype(np.float64), amask).astype(np.float32)
        self.attr_mask = amask
        self.version = 3
        self.v2 = dict(cfg, strands=n_tot, px_per_mm=round(float(px_mm), 2), depth_mm=depth_mm)
        log(f'[atlas v3] {len(self.tiles)} tiles, {n_tot} fine strands in locks, {px_mm:.1f} texels/mm at {out_res}; mean '
            'coverage per row ' + ', '.join(
                f'{ROWS[d]} {np.mean([t["coverage_mean"] for t in self.tile_info if t["row"] == ROWS[d]]):.2f}'
                for d in range(len(ROWS))) + '; mid-length parting / lock coverage per row ' + ', '.join(
                f'{ROWS[d]} {np.mean([t["mid_cross_p10_p90"][0] for t in self.tile_info if t["row"] == ROWS[d]]):.2f} / '
                f'{np.mean([t["mid_cross_p10_p90"][1] for t in self.tile_info if t["row"] == ROWS[d]]):.2f}'
                for d in range(len(ROWS))) + f'; attributes {attr_res}^2 RGB')
        return self

    def config_v4(self):
        """(B3b) the v4 parameters: V4's defaults, the style's atlas block over them"""
        cfg = dict(V4)
        cfg.update({k: v for k, v in self.st.items() if k in V4})
        return cfg

    def render_v4(self, out_res=4096, log=print):
        """(B3b) ATLAS v4, THE HUMAN STRAND PAGE (the lead's B3b brief; study T's and MetaHuman's authored clump pages,
        HAIR_STUDY §3.4 / §10). v3 drew each tile from the groom's member paths, which on a hanging bob wander across
        the card (B3's dense row: solid wiggly blobs, 66 % of the covered texels solid) and ended every strand in the
        card's last 14 % (a blunt opaque block at the cut). A human card's curvature is the card's own (its rows follow
        the guide), so in card space hair runs straight along v, and the page carries what a card cannot:
          * CLUMPS of fine strands (V4 clump_mm per row): spread and overlapping at the root (no straight root edge,
            no gap where one card's root meets the next), gathering along the length and converging to a point at
            their own staggered end (clump_end), so PARTINGS open toward the tips and the ends separate;
          * every strand TAPERED over its last share (taper) to a sub-texel tip, and its own end staggered inside its
            clump (tip_min): a soft cut edge, never a block;
          * flyaways (stray) that leave their clump and cross a parting, thinner, a few running past the clump's end;
          * rows dense (the volume's inner cards) -> wisp (its outer cards): fewer, thinner strands outward.
        Attributes (RGB, no alpha, the v3 contract the runtime reads at version >= 3): R depth (a clump's crest on the
        plane, its flanks under it), G the clump's id (stratified, mean 0.5) + a per-strand offset, B the sideways
        slope. Coverage is true area coverage (ss x ss supersampled polygons, box-filtered)."""
        cfg = self.config_v4()
        c = self.cards
        ss = int(cfg['ss'])
        attr_res = int(cfg['attr_res'])
        depth_mm = float(self.st.get('depth_mm', 1.5))
        um = np.asarray(cfg['strand_um'], np.float64)
        nvar = 2
        nw = len(c.width_classes)
        px_mm = self.px_per_mm * out_res / self.res
        lc_mm = float(np.median(c.Lc) * 1e3)
        cov = np.zeros((out_res, out_res), np.float32)
        attr = np.zeros((attr_res, attr_res, 4), np.float32)
        amask = np.zeros((attr_res, attr_res), bool)
        self.tile_info = []
        n_tot = 0
        fq = np.linspace(0.0, 1.0, 40)
        for ti, (u0, v0, u1, v1) in enumerate(self.tiles):
            d = ti // (nw * nvar)
            wi = (ti // nvar) % nw
            var = ti % nvar
            wmm = float(c.width_classes[wi] * 1e3)
            H = lambda k, j, ch: float(hkey(211 + k, ti * 991 + var, j, ch=ch))   # noqa: E731
            nc = int(np.clip(round(wmm / cfg['clump_mm'][d]), 1, 14))
            sp_c = 1.8 / nc                                          # clump spacing in card units ([-0.9, 0.9])
            cen = -0.9 + (np.arange(nc) + 0.5) * sp_c + (np.array([H(0, k, 1) for k in range(nc)]) - 0.5) * 0.35 * sp_c
            lean = (np.array([H(1, k, 2) for k in range(nc)]) - 0.5) * 2.0 * cfg['clump_lean'] * sp_c
            ce = T_END * (cfg['clump_end'][0] + (cfg['clump_end'][1] - cfg['clump_end'][0]) *
                          np.array([H(2, k, 3) for k in range(nc)]) ** 0.7)
            gid = (np.argsort([H(3, k, 4) for k in range(nc)]) + 0.5) / nc
            # strands: a random scatter's -ln(1 - fill) x width / mean drawn width, x the bundling's overlap
            n_fine = int(np.clip(round(-np.log(1.0 - cfg['fill'][d]) * wmm / (um[1] * 1e-3 * 0.7) * cfg['overlap']),
                                 6, 1500))
            dl = cfg['depth_lock_mm'][d] * 1e-3
            W0 = 0.5 * sp_c                                          # a clump's half width at the root (card units)
            strands = []
            for k in range(n_fine):
                L = k % nc
                j = k // nc
                h = [H(10 + q, L * 4099 + j, q + 5) for q in range(12)]
                z = np.sqrt(-2.0 * np.log(max(h[0], 1e-9))) * np.cos(2.0 * np.pi * h[1])
                s0 = float(np.clip(z * cfg['core'], -1.3, 1.3))      # place across the clump (x its half width)
                stray = h[2] < cfg['stray'][d]
                rs = cfg['root_span']
                vs = (rs[d] if isinstance(rs, (list, tuple)) else rs) * h[3] ** 1.3
                ve = ce[L] * (cfg['tip_min'] + (1.0 - cfg['tip_min']) * h[4] ** 0.6)
                if stray and h[10] < 0.35:                           # a flyaway that runs on past its clump's end
                    ve = min(T_END, ce[L] + 0.04 + 0.08 * h[11])
                ve = max(ve, vs + 0.12)
                v = vs + fq * (ve - vs)
                q = np.clip(v / ce[L], 0.0, 1.2)
                # the clump's half width along its length: spread at the root, gathered, converging to its point
                prof_w = np.interp(q, [0.0, cfg['gather'], 0.55, 0.85, 1.0, 1.2],
                                   [cfg['root_spread'], 1.0, 0.82, 0.48, 0.10, 0.06])
                u = cen[L] + lean[L] * np.clip(q, 0, 1) ** 1.5 + s0 * W0 * prof_w
                if stray:                                            # leaves its clump: drifts across the parting
                    side = 1.0 if h[5] > 0.5 else -1.0
                    amp = side * cfg['stray_mm'][d] * (0.5 + 0.5 * h[6]) / max(0.5 * wmm, 1e-6)
                    u = u + amp * np.clip((q - 0.25) / 0.75, 0.0, 1.0) ** 1.4
                u = u + cfg['wiggle'] * W0 * np.sin(2.0 * np.pi * ((0.6 + 0.8 * h[7]) * fq + h[8]))
                rel = np.minimum(np.abs(s0), 1.4)
                dep = -dl * rel * rel * np.clip(q / 0.3, 0.0, 1.0) - (0.5 * dl if stray else 0.0) \
                    + 0.08e-3 * (h[9] - 0.5)
                # the strand's drawn width: thin at its very root, full by 8 %, tapering over its last `taper` share
                tq = cfg['taper'] * (0.7 + 0.6 * h[10])
                prof = np.interp(fq, [0.0, 0.06, 0.45, 1.0 - tq, 1.0], [0.4 * um[0], um[0], um[1], 0.8 * um[1], um[2]])
                prof = prof * (0.7 + 0.6 * h[11]) * (cfg['stray_w'] if stray else 1.0)
                out_ = np.nonzero(np.abs(u) > 0.97)[0]
                n_in = int(out_[0]) if len(out_) else len(u)
                if n_in < 4:
                    continue
                if n_in < len(u):
                    prof = prof.copy()
                    prof[n_in - 3:n_in] *= np.array([0.6, 0.3, 0.08])
                sid = float(np.clip(gid[L] + cfg['id_strand'] * (h[9] - 0.5), 0.0, 1.0))
                strands.append((u[:n_in], v[:n_in], dep[:n_in], prof[:n_in], sid))
            n_tot += len(strands)
            x0, y0 = u0 * out_res, v0 * out_res
            tw, th = (u1 - u0) * out_res, (v1 - v0) * out_res
            Wp, Hp = int(np.ceil(tw)) * ss, int(np.ceil(th)) * ss
            img = Image.new('L', (Wp, Hp), 0)
            dr = ImageDraw.Draw(img)
            ax0, ay0 = u0 * attr_res, v0 * attr_res
            aw, ah = max(int(round((u1 - u0) * attr_res)), 1), max(int(round((v1 - v0) * attr_res)), 1)
            apage = Image.new('RGBA', (aw, ah), (0, 0, 0, 0))
            adr = ImageDraw.Draw(apage)
            strands.sort(key=lambda qq: float(np.mean(qq[2])))      # painter's order: deepest first, crests on top
            for (u, v, dep, prof, sid) in strands:
                X = (np.clip(u, -0.97, 0.97) * 0.5 + 0.5) * tw * ss
                Y = np.clip(v, 0.0, 1.0) * th * ss
                wpx = np.maximum(prof * 1e-3 * px_mm * ss, 0.35)
                d2 = np.stack([np.gradient(X), np.gradient(Y)], 1)
                d2 /= np.maximum(np.linalg.norm(d2, axis=1, keepdims=True), 1e-9)
                nrm = np.stack([-d2[:, 1], d2[:, 0]], 1) * (0.5 * wpx)[:, None]
                ctr = np.stack([X, Y], 1)
                dr.polygon([tuple(qq) for qq in ctr + nrm] + [tuple(qq) for qq in (ctr - nrm)[::-1]], fill=255)
                AX = (np.clip(u, -0.97, 0.97) * 0.5 + 0.5) * aw
                AY = np.clip(v, 0.0, 1.0) * ah
                lw = np.maximum(1, np.round(prof * 1e-3 * px_mm * attr_res / out_res * 1.5)).astype(int)
                dz = 0.5 + 0.5 * np.clip(dep / (depth_mm * 1e-3), -1.0, 1.0)
                slope = np.gradient(u) / np.maximum(np.gradient(v), 1e-6) * (0.5 * wmm / lc_mm)
                sw = 0.5 + 0.5 * np.clip(slope, -1.0, 1.0)
                for qq in range(len(u) - 1):
                    adr.line([(AX[qq], AY[qq]), (AX[qq + 1], AY[qq + 1])],
                             fill=(int(255 * dz[qq]), int(255 * sid), int(255 * sw[qq]), 255), width=int(lw[qq]))
            a = np.asarray(img, np.float32) / 255.0
            a = a.reshape(Hp // ss, ss, Wp // ss, ss).mean(axis=(1, 3))
            if cfg['blur_px'] > 0:
                from scipy import ndimage
                a = ndimage.gaussian_filter(a, cfg['blur_px'])
            ys, xs = int(round(y0)), int(round(x0))
            hh, ww = min(a.shape[0], out_res - ys, int(round(th))), min(a.shape[1], out_res - xs, int(round(tw)))
            cov[ys:ys + hh, xs:xs + ww] = np.maximum(cov[ys:ys + hh, xs:xs + ww], a[:hh, :ww])
            ap = np.asarray(apage, np.float32) / 255.0
            ays, axs = int(round(ay0)), int(round(ax0))
            hh2, ww2 = min(ap.shape[0], attr_res - ays), min(ap.shape[1], attr_res - axs)
            sub = ap[:hh2, :ww2]
            m = sub[..., 3] > 0
            attr[ays:ays + hh2, axs:axs + ww2][m] = sub[m]
            amask[ays:ays + hh2, axs:axs + ww2] |= m
            a_t = a[:hh, :ww]
            mid = a_t[int(0.35 * hh):int(0.65 * hh)].mean(0)
            covd = a_t[a_t > 0.02]
            self.tile_info.append(dict(tile=ti, row=ROWS[d], width_mm=round(wmm, 2), variant=var, clumps=nc,
                                       strands=len(strands), coverage_mean=round(float(a_t.mean()), 3),
                                       solid_share=round(float((covd > 0.95).mean()) if len(covd) else 0.0, 3),
                                       mid_cross_p10_p90=np.round(np.percentile(mid, [10, 90]), 3).tolist(),
                                       tip_band_coverage=round(float(a_t[int(0.85 * hh):].mean()), 3)))
        self.cov4096 = None
        self.cov = cov
        attr[..., 3] = 1.0
        self.attr = push_pull(attr.astype(np.float64), amask).astype(np.float32)
        self.attr_mask = amask
        self.version = 3                                          # the runtime's v3 contract (RGB, B = sideways)
        self.v2 = dict(cfg, strands=n_tot, px_per_mm=round(float(px_mm), 2), depth_mm=depth_mm, page='v4')
        per = lambda key: ', '.join(f'{ROWS[d]} {np.mean([t[key] for t in self.tile_info if t["row"] == ROWS[d]]):.2f}'  # noqa: E731
                                    for d in range(len(ROWS)))
        log(f'[atlas v4] {len(self.tiles)} tiles, {n_tot} strands, {px_mm:.1f} texels/mm at {out_res}; coverage {per("coverage_mean")}; '
            f'solid share of covered {per("solid_share")}; tip band {per("tip_band_coverage")}; attributes {attr_res}^2 RGB')
        return self

    def layout_fins(self, width=2048, height=512):
        """the fin page (the module doc): 4 rows x (width classes x 2 variants) columns, each column as wide as its edge
        length class, on a page width x height"""
        self.layout(width)
        self.fin_page = (int(width), int(height))
        return self

    def render_fins(self, log=print):
        """THE FIN TILES (the module doc): each a side view of the pile, wrapping in u; coverage = true area coverage
        (ss x ss polygons, box-filtered), attributes on a page attr_div times smaller, RGB, push-pull dilated"""
        from scipy import ndimage
        c = self.cards
        cfg = dict(FIN)
        cfg.update(self.st.get('fins', {}))
        Wout, Hout = self.fin_page
        ss = int(cfg['ss'])
        div = int(cfg['attr_div'])
        Wa, Ha = Wout // div, Hout // div
        um = np.asarray(cfg['strand_um'], np.float64)
        nvar = 2
        nw = len(c.width_classes)
        px_mm = self.px_per_mm * Wout / self.res                 # texels per mm along the edge, at the delivered page
        H_mm = max(float(np.median(c.fin_height)) * 1e3, 0.5)    # the pile's median height: what the lean's mm mean
        cov = np.zeros((Hout, Wout), np.float32)
        attr = np.zeros((Ha, Wa, 4), np.float32)
        amask = np.zeros((Ha, Wa), bool)
        fq = np.linspace(0.0, 1.0, 12)
        self.tile_info = []
        n_tot = 0
        for ti, (u0, v0, u1, v1) in enumerate(self.tiles):
            d = ti // (nw * nvar)
            wi = (ti // nvar) % nw
            var = ti % nvar
            wmm = float(c.width_classes[wi] * 1e3)
            # THE TUFTS: a pile's fibres gather in small tufts; each fibre is far under a pixel at any camera, so a tuft is
            # the scale the outline and the runtime's per-id terms can read (the band was a flat ribbon: a per-fibre id
            # averages to 0.5 by the mip these cameras read). Each tuft: a centre, a top, a lean, an id stratified over
            # the tile (G's mean stays 0.5, so the id's terms stay mean-free at every distance)
            nt = max(1, int(round(wmm / float(cfg['tuft_mm'][d]))))
            t_h = [np.array([float(hkey(307 + q, ti, t, ch=var + 1)) for t in range(nt)]) for q in range(4)]
            t_id = np.zeros(nt)
            t_id[np.argsort(t_h[0])] = (np.arange(nt) + 0.5) / nt
            t_u = (np.arange(nt) + 0.5 + 0.7 * (t_h[1] - 0.5)) / nt
            t_top = cfg['tuft_top'][0] + (cfg['tuft_top'][1] - cfg['tuft_top'][0]) * t_h[2]
            t_lean = (t_h[3] - 0.5) * 2.0 * cfg['tuft_lean'] * H_mm / wmm
            fibres = []
            for layer, per_mm in (('top', cfg['fibres_mm'][d]), ('under', cfg['under_mm'][d])):
                n = int(round(per_mm * wmm))
                salt = 211 + 2 * var + (0 if layer == 'top' else 1)
                for k in range(n):
                    h = [hkey(salt + q, ti, k, ch=q + 1) for q in range(8)]
                    uc = (k + h[0]) / max(n, 1)                  # stratified along the edge: never a bald stretch
                    t = min(int(uc * nt), nt - 1)                # its tuft, and its place across it (-1 .. 1)
                    du = (t_u[t] - uc + 0.5) % 1.0 - 0.5         # toward the tuft's axis, the tile wrapping
                    a = float(np.clip(-du * 2.0 * nt, -1.0, 1.0))
                    stray = layer == 'top' and h[1] < cfg['stray']
                    if layer == 'top':
                        ve = (cfg['stray_tip'] if stray else
                              (cfg['tip_lo'][d] + (cfg['tip_hi'] - cfg['tip_lo'][d]) * h[2] ** 0.6)
                              * t_top[t] * (1.0 - cfg['tuft_point'] * a * a))
                        wf = (cfg['stray_width'] if stray else 0.75 + 0.5 * h[3])
                    else:
                        ve = cfg['under_tip'][0] + (cfg['under_tip'][1] - cfg['under_tip'][0]) * h[2]
                        wf = 0.75 + 0.5 * h[3]
                    lean = (h[4] - 0.5) * 2.0 * cfg['lean'] * H_mm / wmm     # tile widths per tile height
                    bend = (h[5] - 0.5) * 2.0 * cfg['bend'] * H_mm / wmm
                    v = fq * ve
                    u = uc + lean * v + bend * v * v / max(ve, 1e-3)
                    if layer == 'under':                         # the under-pile stays where it is: it keeps the base opaque
                        u = u + 0.5 * t_lean[t] * v
                    elif not stray:                              # the tuft's shared lean, and its fibres closing on its axis
                        u = u + t_lean[t] * v + cfg['tuft_gather'] * du * fq * fq
                    prof = np.interp(fq, [0.0, 0.10, 0.45, 0.80, 1.0],
                                     [0.6 * um[0], um[0], um[1], 0.55 * um[1], um[2]]) * wf
                    dep = -(0.15 + 0.85 * h[6]) * (0.0 if layer == 'top' else 0.6) * 1e-3 * H_mm * 0.4 \
                        - ((0.12 * h[6] + cfg['tuft_depth'] * abs(a) ** 1.5) * 1e-3 * H_mm if layer == 'top' else 0.0)
                    slope = np.gradient(u) / np.maximum(np.gradient(v), 1e-6) * (wmm / H_mm)
                    sid = float(h[7]) if stray else float(np.clip(t_id[t] + (h[7] - 0.5) * cfg['id_fibre'], 0.0, 1.0))
                    fibres.append((u, v, np.full(len(u), dep), prof, sid, slope))
            n_tot += len(fibres)
            x0, y0 = int(round(u0 * Wout)), int(round(v0 * Hout))
            tw, th = int(round(u1 * Wout)) - x0, int(round(v1 * Hout)) - y0
            Wp, Hp = tw * ss, th * ss
            img = Image.new('L', (Wp, Hp), 0)
            dr = ImageDraw.Draw(img)
            ax0, ay0 = u0 * Wa, v0 * Ha
            aw, ah = max(int(round((u1 - u0) * Wa)), 1), max(int(round((v1 - v0) * Ha)), 1)
            apage = Image.new('RGBA', (aw, ah), (0, 0, 0, 0))
            adr = ImageDraw.Draw(apage)
            fibres.sort(key=lambda q: float(q[2][0]))            # painter's order: deepest first
            for (u, v, dep, prof, sid, slope) in fibres:
                Y = v * Hp
                wpx = prof * 1e-3 * px_mm * ss
                for wrap in (-1.0, 0.0, 1.0):                    # the tile wraps in u
                    X = (u + wrap) * Wp
                    if X.max() < -wpx.max() or X.min() > Wp + wpx.max():
                        continue
                    d2 = np.stack([np.gradient(X), np.gradient(Y)], 1)
                    d2 /= np.maximum(np.linalg.norm(d2, axis=1, keepdims=True), 1e-9)
                    nrm = np.stack([-d2[:, 1], d2[:, 0]], 1) * (0.5 * wpx)[:, None]
                    ctr = np.stack([X, Y], 1)
                    poly = [tuple(q) for q in ctr + nrm] + [tuple(q) for q in (ctr - nrm)[::-1]]
                    dr.polygon(poly, fill=255)
                    AX, AY = (u + wrap) * aw, v * ah
                    dz = 0.5 + 0.5 * np.clip(dep / (cfg['depth_mm'] * 1e-3), -1.0, 1.0)
                    sw = 0.5 + 0.5 * np.clip(slope, -1.0, 1.0)
                    lw = np.maximum(1, np.round(prof * 1e-3 * px_mm / div)).astype(int)
                    for q in range(len(u) - 1):
                        adr.line([(AX[q], AY[q]), (AX[q + 1], AY[q + 1])],
                                 fill=(int(255 * dz[q]), int(255 * sid), int(255 * sw[q]), 255), width=int(lw[q]))
            a = np.asarray(img, np.float32) / 255.0
            a = a.reshape(th, ss, tw, ss).mean(axis=(1, 3))
            if cfg['blur_px'] > 0:
                a = ndimage.gaussian_filter(a, cfg['blur_px'], mode=('nearest', 'wrap'))
            cov[y0:y0 + th, x0:x0 + tw] = np.maximum(cov[y0:y0 + th, x0:x0 + tw], a)
            ap = np.asarray(apage, np.float32) / 255.0
            ays, axs = int(round(ay0)), int(round(ax0))
            hh, ww = min(ap.shape[0], Ha - ays), min(ap.shape[1], Wa - axs)
            sub = ap[:hh, :ww]
            m = sub[..., 3] > 0
            attr[ays:ays + hh, axs:axs + ww][m] = sub[m]
            amask[ays:ays + hh, axs:axs + ww] |= m
            bands = [float(a[int(q * th):int((q + 0.1) * th)].mean()) for q in np.arange(0.0, 0.95, 0.1)]
            self.tile_info.append(dict(tile=ti, row=ROWS[d], width_mm=round(wmm, 2), variant=var, fibres=len(fibres),
                                       coverage_mean=round(float(a.mean()), 3),
                                       coverage_by_height=[round(x, 3) for x in bands],
                                       seam_step=round(float(np.abs(a[:, 0] - a[:, -1]).mean()), 3)))
        self.cov4096 = None
        self.cov = cov
        attr[..., 3] = 1.0
        self.attr = push_pull(attr.astype(np.float64), amask).astype(np.float32)
        self.attr_mask = amask
        self.version = 3
        by = {ROWS[d]: np.round(np.mean([t['coverage_by_height'] for t in self.tile_info if t['row'] == ROWS[d]], 0),
                                3).tolist() for d in range(len(ROWS))}
        self.v2 = dict(cfg, strands=n_tot, px_per_mm=round(float(px_mm), 2), depth_mm=cfg['depth_mm'],
                       kind='fins', page=[Wout, Hout], coverage_by_height=by, median_height_mm=round(H_mm, 2))
        log(f'[atlas fins] {len(self.tiles)} tiles, {n_tot} fibres, page {Wout} x {Hout}, {px_mm:.1f} texels/mm along the '
            f'edge, {Hout / 4.0 / H_mm:.1f} texels/mm up the median pile ({H_mm:.2f} mm); coverage by height (0.05 .. 0.95): '
            + '; '.join(f'{k} {v}' for k, v in by.items()))
        return self

    def clip_table(self, thr=0.34, min_tile_px=2):
        """for each mip of the delivered coverage page (2x2 box, as the runtime's generator), the threshold keeping
        mip 0's coverage fraction (alpha >= thr) inside the tiles; global and per density row"""
        mips = [self.cov.astype(np.float64)]
        while min(mips[-1].shape) > 1:                       # (a fin page is wider than tall: stop at its short side)
            a = mips[-1]
            mips.append(a.reshape(a.shape[0] // 2, 2, a.shape[1] // 2, 2).mean(axis=(1, 3)))
        rows = {}
        n = mips[0].shape[0]
        out = []
        ref = (mips[0] >= thr).mean()
        refs = [((mips[0][int(r * n / 4):int((r + 1) * n / 4)]) >= thr).mean() for r in range(4)]
        tile_u, tile_v = (self.tiles[:, 2] - self.tiles[:, 0]).min(), (self.tiles[:, 3] - self.tiles[:, 1]).min()
        for m, a in enumerate(mips):
            size = a.shape[0]
            # the narrowest tile in texels of THIS page's own axes (a fin page is 4 x wider than tall: its narrowest tile is
            # 108 texels; read against the height it stopped the table at mip 3, and the plain path sampling mip 5 at the
            # hero then compared with mip 3's thresholds)
            if min(tile_u * a.shape[1], tile_v * size) < min_tile_px:
                break
            vals = np.sort(a.ravel())[::-1]
            k = int(round(ref * len(vals)))
            t = float(vals[min(max(k - 1, 0), len(vals) - 1)]) if k > 0 else 1.0
            per = []
            for r in range(4):
                sub = np.sort(a[int(r * size / 4):int((r + 1) * size / 4)].ravel())[::-1]
                kk = int(round(refs[r] * len(sub)))
                per.append(round(float(sub[min(max(kk - 1, 0), len(sub) - 1)]) if kk > 0 else 1.0, 4))
            # per row AND per band along root-to-tip (4 bands of the tile height): a dense root band and sparse tips
            # each keep their own coverage fraction (one threshold per row is set by the roots and cuts the tips)
            band = []
            for r in range(4):
                rb = []
                for q in range(4):
                    y0 = int((r + q / 4.0) * n / 4)
                    y1 = int((r + (q + 1) / 4.0) * n / 4)
                    f0 = (mips[0][y0:y1] >= thr).mean()
                    sy0 = int((r + q / 4.0) * size / 4)
                    sy1 = max(int((r + (q + 1) / 4.0) * size / 4), sy0 + 1)
                    sub = np.sort(a[sy0:sy1].ravel())[::-1]
                    kk = int(round(f0 * len(sub)))
                    rb.append(round(min(max(float(sub[min(max(kk - 1, 0), len(sub) - 1)]) if kk > 0 else 1.0,
                                            0.02), 0.98), 4))
                band.append(rb)
            out.append(dict(mip=m, size=size, threshold=round(min(max(t, 0.02), 0.98), 4), by_row=per, by_band=band,
                            fraction_at_base_thr=round(float((a >= thr).mean()), 4)))
        self.clip = dict(base_threshold=thr, coverage_fraction=round(float(ref), 4), mips=out)
        return self.clip

    def save(self, folder, prefix='atlas'):
        import os
        os.makedirs(folder, exist_ok=True)
        p1 = os.path.join(folder, f'{prefix}_coverage.png')
        Image.fromarray((np.clip(self.cov, 0, 1) * 255 + 0.5).astype(np.uint8), 'L').save(p1)
        p2 = os.path.join(folder, f'{prefix}_attributes.png')
        if getattr(self, 'version', 2) >= 3:
            # (round 3) RGB, no alpha channel: no decoder can divide it (the module doc)
            Image.fromarray((np.clip(self.attr[..., :3], 0, 1) * 255 + 0.5).astype(np.uint8), 'RGB').save(p2)
        else:
            Image.fromarray((np.clip(self.attr, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGBA').save(p2)
        return p1, p2

"""STREAK AUDIT (Skye, 10-27: "this colapsed UV pixel stretching/padding stretch where it shouldn't be look happens
sometimes in ways that wouldn't happen from human work ... now that you've found it, make sure to check for it in the
future"): the family of failure that LOOKS like stretched UVs or padding fill while the UVs and the bake are clean.

The case that taught it (work/bestiary/patches/scratch_crown_uvdiag, the octopus crown, 10-27): octopus_skin.skin_at's
arm coordinate q_a = (U(s), R cos a, R sin a) clamps s at the arm's first node and ignores the distance from the axis, so
behind the node the skin's pattern is constant along lines through it (radial streaks and fans in the albedo, roughness
and normal), and the sculpt planter left a band there with almost no papillae (a bare band whose smooth normals read
shiny). Every bake goes through this audit before anyone judges it by eye. Three checks per texture set, each where the
creature's adapter gives it what it needs:

 1. COORDINATE COLLAPSE. A generator that paints a pattern through a coordinate q(p) smears it wherever q's differential
    on the surface collapses: q constant along a direction = the pattern constant along it = a streak. Per covered
    texel: q at the texel's base point and across its footprint on the surface (p +- dP/dx, p +- dP/dy, one texel's step
    on the low), its singular values against the SURFACE metric (the generalised eigenvalues of Jq^T Jq against D^T D,
    D = [dP/dx dP/dy]): sigma2 / sigma1 = how round a pattern cell stays (1 round, 0 a streak); sigma2 against the
    coordinate's nominal scale = how far a cell is magnified; the second difference = a jump inside one footprint (a
    TEAR: a seam in the pattern). Weighted by how much the generator uses the coordinate there (the octopus: armw, the
    share of patch cells on the arm network). The eigenvector of sigma2 is the direction the pattern is constant along:
    the streak the maps will show. Per cluster its SMEAR: the median run of the collapse along each texel's own
    direction (mm, and pattern cells): a collapsed band narrower than a couple of cells stretches a cell by at most its
    width, so check 1 says how far any pattern WOULD smear and check 2 says what the maps show.
 2. STREAKS in the maps the generator wrote (albedo log-luminance, roughness, normal xy, the patch-random mask): per UV
    island (no filter crosses a seam or reads padding), high-passed (texture, not shading ramps), the gradient structure
    tensor smoothed over a couple of mm and carried into the SURFACE frame by the texel's own metric (a UV stretch is not
    a streak: a streak is anisotropic on the creature), its coherence (l1 - l2) / (l1 + l2) and orientation. Flagged
    where the coherence stands out of the creature's own baseline for that material zone and map, unless the HIGH
    explains it (the t10 bake of the high alone is coherent there along the same direction: a crease, a fold, a ruled
    flank; only where the bake covered the texel) or the adapter marks the anisotropy as designed (sucker grooves).
    Clusters over a meaningful area; per cluster a Hough vote of its streak lines finds FANS (lines converging on a
    point: the signature of a coordinate collapsed onto a node) or parallel BARS. And the bake's FILL (check_fill):
    inside-island texels no ray covered, which the dilation painted with copies of their nearest covered texel (real
    padding smear on the creature), read from the coverage itself, a finding where the copies run long enough to show.
 3. DETAIL HOLES in the sculpt plan's planted features (papillae, warts, any instanced detail): their density over the
    surface (a 3D Gaussian kernel estimate, normalised by the plantable area under the same kernel so zone borders do not
    read as holes, sheets facing away excluded), against an annulus round it and the zone's median: holes well below
    their neighbourhood whose extent (the half-density contour round a strict core) covers at least a square
    centimetre. Cross-checked against the RELIEF the bake actually carries (the t10 normal's high-passed RMS): a planned
    hole over a smooth high reads bare and shiny.
Attached parts (the bake's material ids: growths, cyborg plates) and texels hidden under growths are not the skin:
checks 2 and 3 leave them out and the report says how much (CreatureAudit.parts).

Outputs per run (out_dir): flags_<set>.npz (texel images), uv_flags_<set>.png (the flags on the UV layout, per check and
combined), overlay_<tag>.png (the flags painted on the creature, forge/lookdev.py), report.json and report.md
(a verdict, thresholds and why, baselines, clusters with their place on the creature, per-place totals, runtimes). The
images paint each check's REPORTED clusters; a flagged texel no cluster holds is a faint grey speck in the 'all' views.

ANOTHER CREATURE plugs in by subclassing CreatureAudit, which reads the forge's run-folder convention (low.npz V F UV N
face_set region, drivers_<set>.npz, T_<set>_<map>.png, instances.npz): sets() (its texture sets: faces and size), and as
far as it has them coordinates() (its generator's anatomical coordinates as vectorised functions, numpy or cupy),
features() and plantable() (its planted detail and where it belongs), zones() and designed() (material zones, designed
anisotropy), landmarks() and places() (named points and anatomical categories that label clusters and total them),
fidelity() (a replica's proof against the generator's own output). With sets() alone a creature already gets check 2
on its albedo, ORM roughness and normal, zoned by the bake's regions and explained by its T_<set>_N.png (tests/a01's
'minimal' run). audit_streaks_octopus.OctopusAudit is the first full adapter; run_audit(adapter, out_dir) runs it all.
"""
import json
import math
import os
import time

import numpy as np
import warp as wp

wp.set_module_options({'enable_backward': False})    # forward-only kernels

# ----------------------------------------------------------------------------------------------------- THRESHOLDS
# (the numbers and their reasons; report.md prints them. Calibrated 10-27 on the live octopus against crown v5d, where
# the same anatomy carries the clamped and the continued arm coordinate, and proved on planted defects:
# work/bestiary/tests/a01_streak_audit.py)
TH = dict(
    # --- 1. coordinate collapse
    coord_w=0.10,          # the generator draws at least a tenth of its cells through the coordinate here
    coord_aniso=0.40,      # sigma2 / sigma1 below this: a round cell becomes a 2.5 : 1 streak on the surface (healthy
                           # anatomical coordinates sit near 1; the octopus's clamped zone is exactly 0)
    coord_stretch=3.0,     # or sigma2 below 1/3 of the coordinate's nominal scale: cells magnified 3x along some way
    coord_tear=0.25,       # a jump of a quarter pattern cell inside one texel's footprint: a seam through the pattern
    coord_area=25.0,       # mm2: the smallest cluster reported (a 5 mm square; the crown strip is ~1000 mm2 per arm)
    coord_smear_cells=2.0,  # a cluster SMEARS when its distorted cells run 2+ cell WIDTHS long (median over the
                           # cluster): the run of the collapse along its own direction, capped at the cell's own
                           # elongation (cell / sigma2), times the squeeze across it (sigma1 over nominal, when over 1).
                           # Narrower, a cell is stretched by at most the band's width. Measured 10-27: crown v5d's
                           # 1.0-1.15 r tube rim p50 1.0 cell (1.8 mm, up to 2.3 cells; check 2 sees it only faintly,
                           # mostly in the patch mask); the live web junction 2.5-6.7 cells (4.5-12 mm, visible bars);
                           # the live crown strip 8.8-17 cells (16-31 mm). (Review 10-27: the squeeze term is what a
                           # POLE needs: an unwrap round a point pinches cells across, sigma1 -> inf, and its run stops
                           # at the pole's own tear: a 12 mm starburst of 3-10 : 1 cells read 1.7 cells and passed
                           # as clean. Where sigma1 stays at or under nominal, as on every octopus cluster, it changes
                           # no verdict; the cap only makes a partial stretch report its true elongation)
    # --- 2. streaks (scales in mm: the same on every set whatever its texel density)
    hp_mm=1.5,             # high-pass: the map minus its 1.5 mm Gaussian (keeps patches, grooves, bars; drops ramps)
    int_mm=2.0,            # the tensor's integration scale (a ~4 mm window holds a couple of skin patches)
    energy_floor=0.15,     # texels whose texture energy is under 0.15 x the zone's median have no texture to smear ...
    set_floor=0.05,        # ... nor under 0.05 x the whole set's median (a suppressed zone's 8-bit steps are no pattern)
    coh_k=4.0,             # flag above the zone's median + 4 robust sigmas (1.4826 MAD) ...
    coh_lo=0.55,           # ... but never below 0.55 (healthy skin patterns sit at 0.1-0.25, p99 under 0.45) ...
    coh_hi=0.65,           # ... nor above 0.65 in any zone: above every healthy texture's p99 measured (0.37-0.45 at
                           # this scale: body, crown top in v5d, arms) and below a collapsed coordinate's 0.7-0.95, so a
                           # zone whose baseline is raised (the oral layer: sucker rings, creases, quantisation, before
                           # those were excluded) cannot hide a collapse
    high_lo=0.40,          # the high explains a streak where its own coherence is over 0.40 (twice healthy skin's) ...
    high_tol=25.0,         # ... along the same direction within 25 deg ...
    high_reach_mm=2.0,     # ... there or within 2 mm in the same island (a crease's occlusion and cavity terms paint the
                           # albedo and roughness wider than the crease's own coherent line: v5d's web-fold crease)
    streak_area=25.0,      # mm2: the smallest streak cluster reported
    fan_vote_mm=45.0,      # a streak line votes out to 45 mm each way (the crown strip's fans span 10-30 mm)
    fan_frac=0.30,         # a fan: a centre that at least 30 % of the cluster's streak weight passes through ...
    fan_spread=25.0,       # ... from rays spread over at least 25 deg ...
    fan_align=0.94,        # ... each streak along its ray from the centre (mean |cos| over 0.94: within ~20 deg)
    bars_r=0.90,           # bars: the streak orientations agree (doubled-angle resultant over 0.90, ~ +-13 deg)
    fill_area=10.0,        # mm2: the smallest FILL cluster reported (inside-island texels the bake never covered, each
                           # painted with its nearest covered texel's value: a copy-streak as long as that distance) ...
    fill_len_mm=1.0,       # ... a finding when its longest copy runs 1 mm (3 texels at the octopus's 3.2 px/mm).
                           # Measured 10-27: the live crown's two misses copy 2.0-2.2 mm over 26-28 mm2 (its other 87
                           # under 1 mm or 10 mm2); crown v5d's longest copy is 0.45 mm
    # --- 3. detail holes
    kde_mm=(4.0, 6.0, 15.0),   # the local kernel (sigma 4 mm) and the annulus between sigma 6 and 15 mm (~6-25 mm out),
                               # at most: per feature zone all three scale down so the local kernel holds ...
    kde_count=8.0,         # ... about 8 features at the zone's median density (the mantle's 7.3 / cm2 under 4 mm: the
                           # noise the hole ratios below were set at), so a dense zone's narrow gaps are seen: the arm
                           # roots (24 / cm2) 2.3 mm, the arms set (44 / cm2) 1.7 mm (review 10-27: a bare ring 6 mm
                           # wide round an arm read 0.5 x its annulus under 4 mm) ...
    kde_min_mm=1.5,        # ... never under 1.5 mm (the query grid is 1 mm, the finer area samples a texel stride)
    kde_step_mm=1.0,       # query points ~1 mm apart, the plantable-area samples 2 mm
    part_margin_mm=4.0,    # no skin is planned under an attached part (G.part) nor this close to one: a part drops the
                           # detail its edge would cut (cyborg.drop_skin_features: within its junction's reach + 2 mm +
                           # the feature's own footprint, 3-6 mm; review 10-27, the C3 plated look: three 1-2 cm2 'holes'
                           # hugging the plate border without it)
    plant_min=0.25,        # tested where the design expects at least a quarter of its full density (plantable() is the
                           # design's relative density; the measured density is normalised by it, so tapers are no holes)
    hole_ring=0.30,        # a hole: the local density under 0.30 x the annulus round it ...
    hole_zone=0.50,        # ... and under 0.50 x its zone's median, or ...
    hole_deep=0.20,        # ... under 0.20 x the zone's median however large (a hole wider than the annulus)
    hole_area=100.0,       # mm2: a square centimetre (one papilla's neighbourhood is ~0.1 cm2 at 10 / cm2), of the
                           # hole's EXTENT:
    hole_extent=0.5,       # under 0.5 x min(annulus, zone), within one local kernel sigma of a strict core above. The
                           # strict cores sit a kernel's blur inside the bare skin (review 10-27: a 2 cm2 bald disk on
                           # the mantle cored 0.6 cm2 and went unreported, as did a 2 cm2 hole on the arms and an 8 mm
                           # band 60 mm long); the extent is the 0.5 contour, about where the bare skin ends, and the
                           # sigma guard keeps the thin sparse strips along a zone's margin out (live: the same 6 holes,
                           # grown toward their true size; v5d: one more, a sparse patch by the web margin)
    relief_hp_mm=1.0,      # the relief: the t10 normal minus its 1 mm Gaussian ...
    relief_mm=2.5,         # ... its RMS over 2.5 mm
    relief_hole=0.30,      # a relief hole: under 0.30 x the zone's median relief on plantable skin
)

FLAG_BITS = dict(coord=1, tear=2, streak=4, explained=8, hole=16, relief=32, fan=64, speck=128, fill=256)
# (coord, streak, fill, hole and relief mark the REPORTED clusters, over their area bars; speck: a texel some check
# flagged that no reported cluster holds, painted faintly in the 'all' views: below the bar, not a finding. uint16)
DRIVER_KEYS = ('normal', 'base', 'region', 'mat', 'hidden')     # what the audit reads of drivers_<set>.npz


# ----------------------------------------------------------------------------------------------------- kernels
@wp.kernel
def k_raster(uv_mesh: wp.uint64, size: int, tri: wp.array(dtype=wp.int32), bar: wp.array(dtype=wp.vec3)):
    """per texel centre (kernel order: row y = v * size) the set's triangle under it and its corner weights (u, v,
    1 - u - v), material.low_at's convention"""
    tid = wp.tid()
    x = tid % size
    y = tid // size
    q = wp.mesh_query_ray(uv_mesh, wp.vec3(float(x) + 0.5, float(y) + 0.5, 1.0), wp.vec3(0.0, 0.0, -1.0), 2.0)
    if q.result:
        tri[tid] = q.face
        bar[tid] = wp.vec3(q.u, q.v, 1.0 - q.u - q.v)
    else:
        tri[tid] = -1


@wp.kernel
def k_kde(qp: wp.array(dtype=wp.vec3), qn: wp.array(dtype=wp.vec3), fgrid: wp.uint64, fp: wp.array(dtype=wp.vec3),
          fn: wp.array(dtype=wp.vec3), sgrid: wp.uint64, sp: wp.array(dtype=wp.vec3), sn: wp.array(dtype=wp.vec3),
          sa: wp.array(dtype=wp.float32), s0: float, s1: float, s2: float, rcut: float, ncos: float,
          num: wp.array(dtype=wp.vec3), den: wp.array(dtype=wp.vec3)):
    """three Gaussian sums per query point: the planted features (count) and the plantable area (m2) round it, only
    from points whose normal faces the query's (the other side of a web or a fold is another sheet)"""
    i = wp.tid()
    x = qp[i]
    n = qn[i]
    a0 = 0.5 / (s0 * s0)
    a1 = 0.5 / (s1 * s1)
    a2 = 0.5 / (s2 * s2)
    r2 = rcut * rcut
    acc = wp.vec3(0.0)
    it = wp.hash_grid_query(fgrid, x, rcut)
    j = int(0)
    while wp.hash_grid_query_next(it, j):
        v = x - fp[j]
        d2 = wp.dot(v, v)
        if d2 < r2:
            if wp.dot(n, fn[j]) > ncos:
                acc = acc + wp.vec3(wp.exp(-d2 * a0), wp.exp(-d2 * a1), wp.exp(-d2 * a2))
    num[i] = acc
    acc2 = wp.vec3(0.0)
    it2 = wp.hash_grid_query(sgrid, x, rcut)
    k = int(0)
    while wp.hash_grid_query_next(it2, k):
        v2 = x - sp[k]
        d22 = wp.dot(v2, v2)
        if d22 < r2:
            if wp.dot(n, sn[k]) > ncos:
                acc2 = acc2 + sa[k] * wp.vec3(wp.exp(-d22 * a0), wp.exp(-d22 * a1), wp.exp(-d22 * a2))
    den[i] = acc2


# ----------------------------------------------------------------------------------------------------- helpers
def backend(gpu=True):
    """(xp, ndimage, to_numpy, on_gpu): cupy on the GPU when it is there, numpy otherwise"""
    if gpu:
        try:
            import cupy as cp
            from cupyx.scipy import ndimage as cnd
            cp.cuda.runtime.getDeviceCount()
            return cp, cnd, cp.asnumpy, True
        except Exception:                                   # no cupy / no device: the CPU path
            pass
    import scipy.ndimage as snd
    return np, snd, np.asarray, False


def smoothstep(xp, e0, e1, x):
    t = xp.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def srgb_eotf(s):
    s = np.asarray(s, np.float32)
    return np.where(s <= 0.04045, s / 12.92, ((s + 0.055) / 1.055) ** 2.4)


def _unit(v, axis=-1):
    return v / np.maximum(np.linalg.norm(v, axis=axis, keepdims=True), 1e-20)


def _wrap_half(a):
    """an orientation difference folded into [-pi/2, pi/2)"""
    return (a + 0.5 * np.pi) % np.pi - 0.5 * np.pi


def islands(F, UV, eps=1.0e-7):
    """per triangle its UV island (bake.islands' rule: triangles joined through shared UV corners)"""
    from .bake import islands as _isl
    return _isl(F, UV, eps)


# ----------------------------------------------------------------------------------------------------- the adapter
class CreatureAudit:
    """The creature's side of the audit. Subclass it; every method below has a default that reads the forge's run-folder
    convention or switches its check off. The octopus: audit_streaks_octopus.OctopusAudit.

      sets()            REQUIRED: [dict(name, faces (bool over low F), size)] the texture sets the bake wrote
      groups(set)       the maps check 2 reads ([dict(name, key, kind: loglum | channel (ch) | normal)])
      high_group(set)   the bake of the high alone (t10: T_<set>_N.png), what explains a streak; None = no explaining
      zones(set, G)     the material zones per inside texel (compact, len G.n) and their names: baselines are per zone
      designed(set, G)  bool per inside texel: anisotropy that is designed there (sucker grooves), never flagged
      parts(set, G)     bool per inside texel: not the creature's skin (by default the bake's material ids: growths,
                        cyborg plates; and texels hidden under growths): left out of checks 2 and 3
      coordinates(set)  [dict(name, fn(P (n,3), xp) -> (q (n,k), w (n,), sref (n,)), cell (m), note)]: the generator's
                        anatomical coordinates, w its use weight, sref its nominal scale on the surface; [] = no check 1
      features(set)     dict(p (n,3), n (n,3), rb (n,), kind (n,)) the planted detail near this set; None = no check 3
      plantable(set, P, N, zone)   0..1 per point: where the features belong by design (not where a planter put them)
      landmarks()       {name: (3,) point}: clusters and fan centres are labelled by the nearest
      describe(P)       a short anatomical place per point for the cluster lines (None: the nearest landmark only)
      places(set, P)    an anatomical CATEGORY per point ('crown strip', 'web junction', 'body' ...): each cluster takes
                        its texels' majority and the report totals every check by category (None: no totals)
      renders()         [dict(tag, views, center, span)] for the overlay; render_mesh() the mesh (V F UVg mat) it draws
      fidelity(set, G)  a replicated coordinate's proof against what the generator wrote (a dict for the report)
    """
    name = 'creature'

    def __init__(self, run_dir, label=None):
        self.run_dir = run_dir
        self.label = label or os.path.basename(os.path.normpath(run_dir))
        self._low = None
        self._drv = {}
        self.map_override = {}           # {(set, key): uint8 image}: planted defects without touching the run's files
        self.notes = []                  # lines for the report (what this adapter assumed, which variant it read)

    # ---- the run folder
    def low(self):
        if self._low is None:
            L = dict(np.load(os.path.join(self.run_dir, 'low.npz'), allow_pickle=True))
            if 'face_set' in L:
                L['face_set'] = np.asarray(L['face_set']).astype(str)
            self._low = L
        return self._low

    def sets(self):
        raise NotImplementedError

    def drivers(self, set_name):
        if set_name not in self._drv:
            z = np.load(os.path.join(self.run_dir, f'drivers_{set_name}.npz'))
            self._drv[set_name] = {k: z[k] for k in DRIVER_KEYS if k in z.files}
        return self._drv[set_name]

    def parts(self, set_name, G):
        """bool per inside texel: NOT the creature's own skin, left out of checks 2 and 3 (their flags, baselines and the
        plantable skin): where the bake's packed material id leads with an attached part (bake.py 'mat' & 255 != 0: a
        growth, a cyborg plate's paint, steel, gasket or scar) and where the bake hid the texel under a growth
        ('hidden'). Their looks come from other generators, whose designed edges and wear the skin's baselines read as
        streaks and whose footprint the skin's planters leave bare by design (review 10-27, the C3 plated look: 12
        streak clusters on the plates' edge wear and a 137 cm2 'hole' under them). None of either on a plain creature"""
        d = self.drivers(set_name)
        out = np.zeros(G.n, bool)
        if 'mat' in d:
            out |= (d['mat'][G.ys, G.xs] & 255) != 0
        if 'hidden' in d:
            out |= np.asarray(d['hidden'][G.ys, G.xs], bool)
        return out

    def map_path(self, set_name, key):
        return os.path.join(self.run_dir, f'T_{set_name}_{key}.png')

    def load_map(self, set_name, key):
        if (set_name, key) in self.map_override:
            return self.map_override[(set_name, key)]
        from PIL import Image
        p = self.map_path(set_name, key)
        return np.asarray(Image.open(p)) if os.path.exists(p) else None

    # ---- check 2
    def groups(self, set_name):
        return [dict(name='albedo', key='albedo', kind='loglum'), dict(name='roughness', key='orm', kind='channel', ch=1),
                dict(name='normal', key='normal', kind='normal')]

    def high_group(self, set_name):
        return dict(name='high', key='N', kind='normal')

    def zones(self, set_name, G):
        reg = self.drivers(set_name).get('region')
        if reg is None:
            return np.zeros(G.n, np.int16), {0: 'all'}
        z = reg[G.ys, G.xs].astype(np.int16)
        return z, {int(k): f'region {int(k)}' for k in np.unique(z)}

    def designed(self, set_name, G):
        return None

    def designed_dirs(self, set_name, G):
        """{group name: (dir (n, 3), mask (n,))} per inside texel: a direction along which that map's streaks are DESIGNED
        (the octopus's transverse arm wrinkles run round the arm); a streak within high_tol of it there is not flagged"""
        return {}

    def describe(self, P):
        """a short anatomical place per point (n, 3) for the report (None: the nearest landmark only)"""
        return None

    def places(self, set_name, P):
        """an anatomical category per point (n, 3), an array of str: the report's per-place totals (None: none)"""
        return None

    # ---- check 1
    def coordinates(self, set_name):
        return []

    # ---- check 3
    def features(self, set_name):
        return None

    def feature_zones(self, set_name, G):
        """the zones check 3 compares densities within (per inside texel, and names): by default check 2's"""
        return G.zone, G.zone_names

    def plantable(self, set_name, P, N, zone):
        """the plan's DESIGN density at points P, relative (0..1); zone: their feature zone. Check 3 tests where it is over
        plant_min and normalises the density by it, so a designed taper is not a hole"""
        return np.ones(len(P), np.float32)

    # ---- labels, renders, proofs
    def landmarks(self):
        return {}

    def renders(self):
        return [dict(tag='whole', views=('threeq', 'top', 'front'), center=None, span=None)]

    def render_mesh(self):
        """the low with one material per texture set (faces in no set are dropped); UV in glTF's convention"""
        L = self.low()
        mat = np.full(len(L['F']), -1, np.int32)
        for i, s in enumerate(self.sets()):
            mat[s.get('render_faces', s['faces'])] = i
        keep = mat >= 0
        UVg = L['UV'].copy()
        UVg[:, 1] = 1.0 - UVg[:, 1]
        return dict(V=L['V'], F=L['F'][keep], UV=UVg, N=L.get('N'), mat=mat[keep])

    def fidelity(self, set_name, G):
        return None

    def coord_breakdown(self, set_name, G, idx):
        """{name: bool mask over idx (compact inside-texel indices)}: where on the anatomy check 1's texels lie, for the
        report (None: no breakdown)"""
        return None


# ----------------------------------------------------------------------------------------------------- set geometry
class SetGeom:
    """one texture set's texels on the low: image order (row 0 = forge v = 1, the PNGs' order); per INSIDE texel (centre
    in a triangle) compact arrays: ys, xs, t (triangle), P (the low's point), N (its normal), B (the bake's base point,
    P where the bake lost it), Dx, Dy (the low's point per texel step along image x and image y, metres), area (m2 per
    texel); images: idx (row into the compact arrays or -1), island (-1 outside), cov (the bake covered it)"""


def raster(F, UV, size):
    """per texel centre the triangle under it (-1: none) and its corner weights, image order (GPU: material.uv_bvh's
    texel-space mesh, one ray per texel)"""
    from .material import uv_bvh
    m = uv_bvh(F, UV, size)
    n = size * size
    tri = wp.zeros(n, dtype=wp.int32)
    bar = wp.zeros(n, dtype=wp.vec3)
    wp.launch(k_raster, dim=n, inputs=[m.id, size, tri, bar])
    wp.synchronize()
    return tri.numpy().reshape(size, size)[::-1].copy(), bar.numpy().reshape(size, size, 3)[::-1].copy()


def tri_steps(V, F, UV, size):
    """per triangle D (m, 3, 2): the surface step (metres) per texel along image x (column) and image y (row, down)"""
    P = V[F]
    T = np.stack([UV[F][..., 0] * size, (1.0 - UV[F][..., 1]) * size], -1)
    E = np.stack([P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]], -1)                 # (m, 3, 2) the edges in 3D
    Tm = np.stack([T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]], -1)                # (m, 2, 2) the same edges in texels
    det = Tm[:, 0, 0] * Tm[:, 1, 1] - Tm[:, 0, 1] * Tm[:, 1, 0]
    ok = np.abs(det) > 1e-12
    inv = np.zeros_like(Tm)
    inv[ok, 0, 0] = Tm[ok, 1, 1] / det[ok]
    inv[ok, 1, 1] = Tm[ok, 0, 0] / det[ok]
    inv[ok, 0, 1] = -Tm[ok, 0, 1] / det[ok]
    inv[ok, 1, 0] = -Tm[ok, 1, 0] / det[ok]
    return E @ inv


def set_geometry(ad, sset, log=print):
    t0 = time.time()
    L = ad.low()
    V, UV, Nv = L['V'], L['UV'], L['N']
    F = L['F'][sset['faces']]
    S = int(sset['size'])
    tri, bar = raster(F, UV, S)
    G = SetGeom()
    G.name, G.size, G.F = sset['name'], S, F
    inside = tri >= 0
    G.ys, G.xs = np.nonzero(inside)
    G.n = len(G.ys)
    G.idx = np.full((S, S), -1, np.int32)
    G.idx[G.ys, G.xs] = np.arange(G.n, dtype=np.int32)
    G.t = tri[G.ys, G.xs]
    b = bar[G.ys, G.xs].astype(np.float64)
    Ft = F[G.t]
    G.P = (V[Ft] * b[..., None]).sum(1)
    G.N = _unit((Nv[Ft] * b[..., None]).sum(1))
    D = tri_steps(V, F, UV, S)
    G.Dx, G.Dy = D[G.t, :, 0], D[G.t, :, 1]
    G.area = np.linalg.norm(np.cross(G.Dx, G.Dy), axis=1)
    isl_t = islands(F, UV)
    G.island = np.full((S, S), -1, np.int16)
    G.island[G.ys, G.xs] = isl_t[G.t]
    G.isl_c = G.island[G.ys, G.xs]
    drv = ad.drivers(G.name)
    G.cov = drv['normal'][..., 3] > 0
    G.cov_c = G.cov[G.ys, G.xs]
    base = drv.get('base')
    G.B = G.P.copy()
    if base is not None:
        bw = base[G.ys, G.xs]
        ok = bw[:, 3] > 0.5
        G.B[ok] = bw[ok, :3]
    # the texel metric's Cholesky factor (the surface frame: s = R t; R = [[a, b], [0, c]], metres per texel)
    a = np.linalg.norm(G.Dx, axis=1)
    bb = np.einsum('ij,ij->i', G.Dx, G.Dy) / np.maximum(a, 1e-20)
    c = np.sqrt(np.maximum((G.Dy * G.Dy).sum(1) - bb * bb, 1e-30))
    G.Ra, G.Rb, G.Rc = a.astype(np.float32), bb.astype(np.float32), c.astype(np.float32)
    G.px_per_m = float(np.median(1.0 / np.sqrt(np.maximum(G.area, 1e-30))))
    # every island's bounding box
    G.boxes = {}
    for k in np.unique(G.isl_c):
        m = G.isl_c == k
        G.boxes[int(k)] = (int(G.ys[m].min()), int(G.ys[m].max()) + 1, int(G.xs[m].min()), int(G.xs[m].max()) + 1)
    G.zone, G.zone_names = ad.zones(G.name, G)
    dz = ad.designed(G.name, G)
    G.designed = np.zeros(G.n, bool) if dz is None else np.asarray(dz, bool)
    # attached parts and texels hidden under growths: not the skin (never flagged, out of the baselines and the plan)
    pz = ad.parts(G.name, G)
    G.part = np.zeros(G.n, bool) if pz is None else np.asarray(pz, bool)
    G.designed = G.designed | G.part
    hd = drv.get('hidden')
    G.hidden_c = np.zeros(G.n, bool) if hd is None else np.asarray(hd, bool)[G.ys, G.xs]
    log(f'[audit {ad.label}/{G.name}] {S}^2: {G.n} inside texels ({G.cov_c.mean()*100:.1f} % covered), '
        f'{len(G.boxes)} islands, {G.px_per_m/1000:.2f} px/mm'
        + (f', attached parts {G.area[G.part].sum()*1e4:.1f} cm2 left out' if G.part.any() else '')
        + f'; geometry {time.time()-t0:.1f}s')
    return G


def _img(G, vals, fill=0, dtype=None):
    """a compact per-inside-texel array as a full image"""
    vals = np.asarray(vals)
    out = np.full((G.size, G.size) + vals.shape[1:], fill, dtype or vals.dtype)
    out[G.ys, G.xs] = vals
    return out


def _clusters(G, mask_c, min_area_mm2, close=2, open_=1):
    """connected flags per island (8-connected after an opening of open_ and a closing of close texels, both inside the
    island), with their area (mm2): [dict(island, sel (compact indices), area_mm2)] largest first"""
    from scipy import ndimage as nd
    out = []
    M = _img(G, mask_c, False, bool)
    for k, (y0, y1, x0, x1) in G.boxes.items():
        isl = G.island[y0:y1, x0:x1] == k
        m = M[y0:y1, x0:x1] & isl
        if not m.any():
            continue
        if open_:
            m = nd.binary_opening(m, iterations=open_) & isl
        if close:
            m = nd.binary_closing(np.pad(m, close), iterations=close)[close:-close, close:-close] & isl
        lab, nl = nd.label(m, structure=np.ones((3, 3)))
        if nl == 0:
            continue
        ii = G.idx[y0:y1, x0:x1]
        for j in range(1, nl + 1):
            sel = ii[lab == j]
            sel = sel[sel >= 0]
            a = float(G.area[sel].sum() * 1e6)
            if a >= min_area_mm2:
                out.append(dict(island=int(k), sel=sel, area_mm2=a))
    out.sort(key=lambda c: -c['area_mm2'])
    return out


def _nearest_landmark(lm, p):
    if not lm or p is None:
        return None, None
    names = list(lm)
    d = [float(np.linalg.norm(np.asarray(lm[k]) - p)) for k in names]
    j = int(np.argmin(d))
    return names[j], d[j] * 1000.0


def _describe(ad, p):
    d = ad.describe(np.asarray(p, np.float64)[None]) if ad is not None else None
    return d[0] if d else None


def _cluster_info(G, cl, lm, ad=None):
    sel = cl['sel']
    w = G.area[sel]
    c3 = (G.P[sel] * w[:, None]).sum(0) / w.sum()
    # (the texel nearest the area-weighted centroid: on the surface, where a curved cluster's centroid is not)
    j = sel[int(np.argmin(np.linalg.norm(G.P[sel] - c3, axis=1)))]
    nm, d = _nearest_landmark(lm, G.P[j])
    return dict(island=cl['island'], area_mm2=round(cl['area_mm2'], 1), texels=int(len(sel)),
                centroid_mm=[round(float(v) * 1000, 1) for v in G.P[j]], where=_describe(ad, G.B[j]), nearest=nm,
                nearest_mm=None if d is None else round(d, 1),
                uv_box=[int(G.xs[sel].min()), int(G.ys[sel].min()), int(G.xs[sel].max()), int(G.ys[sel].max())],
                covered=round(float(G.cov_c[sel].mean()), 3))


# ----------------------------------------------------------------------------------------------------- 1. coordinates
def check_coord(ad, sset, G, gpu=True, log=print, chunk=150000):
    """check 1 over every coordinate the adapter exposes for this set; per covered inside texel: aniso (sigma2/sigma1),
    sig1, sig2 (coordinate units per surface metre), sref, jump (the larger second difference, coordinate units), w, the
    collapse direction (3D unit: the way the pattern is constant) and the flags"""
    specs = ad.coordinates(G.name)
    if not specs:
        return None
    xp, _, to_np, on_gpu = backend(gpu)
    sel = np.nonzero(G.cov_c)[0]
    res = {}
    for sp in specs:
        t0 = time.time()
        n = len(sel)
        A = {k: np.zeros(n, np.float32) for k in ('aniso', 'sig1', 'sig2', 'sref', 'jump', 'w', 'step')}
        A['dir'] = np.zeros((n, 3), np.float32)
        A['vt'] = np.zeros((n, 2), np.float32)           # the collapse direction in texel space (x, y), unit
        for s0 in range(0, n, chunk):
            ii = sel[s0:s0 + chunk]
            m = len(ii)
            pb = xp.asarray(G.B[ii])
            dx = xp.asarray(G.Dx[ii])
            dy = xp.asarray(G.Dy[ii])
            q, w, sref = sp['fn'](xp.concatenate([pb, pb + dx, pb - dx, pb + dy, pb - dy]), xp)
            q = q.reshape(5, m, -1)
            Jx = 0.5 * (q[1] - q[2])
            Jy = 0.5 * (q[3] - q[4])
            jump = xp.maximum(xp.linalg.norm(q[1] - 2 * q[0] + q[2], axis=1),
                              xp.linalg.norm(q[3] - 2 * q[0] + q[4], axis=1))
            G11, G12, G22 = (dx * dx).sum(1), (dx * dy).sum(1), (dy * dy).sum(1)
            H11, H12, H22 = (Jx * Jx).sum(1), (Jx * Jy).sum(1), (Jy * Jy).sum(1)
            # det(H - l G) = 0
            a2 = G11 * G22 - G12 * G12
            b2 = -(H11 * G22 + H22 * G11 - 2.0 * H12 * G12)
            c2 = H11 * H22 - H12 * H12
            disc = xp.sqrt(xp.maximum(b2 * b2 - 4.0 * a2 * c2, 0.0))
            l1 = xp.maximum((-b2 + disc) / (2.0 * a2), 0.0)
            l2 = xp.maximum(xp.minimum((-b2 - disc) / (2.0 * a2), l1), 0.0)
            # the collapse direction: (H - l2 G) v = 0, from the better-conditioned row
            r1 = xp.stack([-(H12 - l2 * G12), H11 - l2 * G11], 1)
            r2 = xp.stack([H22 - l2 * G22, -(H12 - l2 * G12)], 1)
            v = xp.where((xp.linalg.norm(r1, axis=1) >= xp.linalg.norm(r2, axis=1))[:, None], r1, r2)
            vt = v / xp.maximum(xp.linalg.norm(v, axis=1, keepdims=True), 1e-30)
            d3 = dx * vt[:, :1] + dy * vt[:, 1:2]
            st = xp.linalg.norm(d3, axis=1)                  # metres on the surface per texel step along vt
            d3 = d3 / xp.maximum(st[:, None], 1e-30)
            s1, s2 = xp.sqrt(l1), xp.sqrt(l2)
            A['aniso'][s0:s0 + m] = to_np(s2 / xp.maximum(s1, 1e-30))
            A['sig1'][s0:s0 + m] = to_np(s1)
            A['sig2'][s0:s0 + m] = to_np(s2)
            A['sref'][s0:s0 + m] = to_np(sref[:m])
            A['jump'][s0:s0 + m] = to_np(jump)
            A['w'][s0:s0 + m] = to_np(w[:m])
            A['dir'][s0:s0 + m] = to_np(d3)
            A['vt'][s0:s0 + m] = to_np(vt)
            A['step'][s0:s0 + m] = to_np(st)
        use = A['w'] >= TH['coord_w']
        tear = use & (A['jump'] > TH['coord_tear'] * sp['cell'])
        col = use & ~tear & ((A['aniso'] < TH['coord_aniso']) | (A['sig2'] < A['sref'] / TH['coord_stretch']))
        A['tear'], A['collapse'], A['sel'] = tear, col, sel
        A['clusters'] = _coord_clusters(ad, G, A, sp['cell'])
        res[sp['name']] = A
        sm = [c for c in A['clusters'] if c['smears']]
        log(f'[audit {ad.label}/{G.name}] check 1 "{sp["name"]}": {n} texels, used (w >= {TH["coord_w"]}) '
            f'{use.mean()*100:.1f} %, collapsed {col.sum()} ({G.area[sel[col]].sum()*1e4:.1f} cm2), tears {tear.sum()}; '
            f'clusters {len(A["clusters"])}, smearing {len(sm)} ({sum(c["area_mm2"] for c in sm)/100:.1f} cm2); '
            f'{time.time()-t0:.1f}s')
    return res


def _run_length(G, M, idx, vx, vy, step_m, tmax_mm=80.0):
    """per texel idx (compact indices): the length (mm) of the flagged run of image M through it along its own direction
    (vx, vy: texel space, unit), inside its island: how far a pattern cell is smeared there (a lower bound where the run
    crosses a UV seam: texel space cannot follow it)"""
    S = G.size
    x0, y0 = G.xs[idx].astype(np.float64), G.ys[idx].astype(np.float64)
    isl = G.isl_c[idx]
    tmax = max(1, int(tmax_mm * 1e-3 * G.px_per_m))
    tot = np.ones(len(idx))
    for sgn in (1.0, -1.0):
        alive = np.ones(len(idx), bool)
        for t in range(1, tmax + 1):
            xi = np.rint(x0 + sgn * t * vx).astype(np.int64)
            yi = np.rint(y0 + sgn * t * vy).astype(np.int64)
            ok = alive & (xi >= 0) & (xi < S) & (yi >= 0) & (yi < S)
            j = np.nonzero(ok)[0]
            ok[j] = M[yi[j], xi[j]] & (G.island[yi[j], xi[j]] == isl[j])
            tot += ok
            alive = ok
            if not alive.any():
                break
    return tot * step_m * 1000.0


def _coord_clusters(ad, G, A, cell, n_run=400, seed=11):
    """check 1's collapsed texels as clusters over coord_area, each with where it is, its anisotropy and use weight, and
    its SMEAR: the median run of the collapse along each texel's own collapse direction (sampled, smear_mm) and how many
    cell WIDTHS a distorted cell runs there (smear_cells: the run capped at cell / sigma2, times the squeeze sigma1 /
    nominal when over 1, squeeze_p50); smears = at least coord_smear_cells"""
    rng = np.random.default_rng(seed)
    mcol = np.zeros(G.n, bool)
    mcol[A['sel'][A['collapse']]] = True
    pos = np.full(G.n, -1, np.int64)
    pos[A['sel']] = np.arange(len(A['sel']))
    M = _img(G, mcol, False, bool)
    lm = ad.landmarks()
    out = []
    for c in _clusters(G, mcol, TH['coord_area']):
        sel = c['sel'][mcol[c['sel']]]                    # (the run starts on collapsed texels, not the closing's)
        if len(sel) == 0:
            continue
        info = _cluster_info(G, c, lm, ad)
        pj = pos[sel]
        info['aniso_p50'] = round(float(np.median(A['aniso'][pj])), 3)
        info['w_p50'] = round(float(np.median(A['w'][pj])), 3)
        smp = sel if len(sel) <= n_run else rng.choice(sel, n_run, replace=False)
        pk = pos[smp]
        run = _run_length(G, M, smp, A['vt'][pk, 0].astype(np.float64), A['vt'][pk, 1].astype(np.float64),
                          A['step'][pk].astype(np.float64))
        # in cell WIDTHS: the run, capped at the cell's own elongation (cell / sigma2), times the squeeze across it
        # (sigma1 over nominal when over 1: a pole pinches its cells across while its run stops at its own tear)
        sref = np.maximum(A['sref'][pk].astype(np.float64), 1e-20)
        s1, s2 = A['sig1'][pk] / sref, A['sig2'][pk] / sref
        cm = cell * 1000.0
        wid = np.minimum(run, cm / np.maximum(s2, 1e-6)) / cm * np.maximum(s1, 1.0)
        info['smear_mm'] = round(float(np.median(run)), 1)
        info['smear_cells'] = round(float(np.median(wid)), 2)
        info['squeeze_p50'] = round(float(np.median(np.maximum(s1, 1.0))), 2)
        info['smears'] = bool(info['smear_cells'] >= TH['coord_smear_cells'])
        info['_sel'] = c['sel']
        out.append(info)
    return out


# ----------------------------------------------------------------------------------------------------- 2. streaks
def _group_channels(ad, set_name, g):
    """the group's channels as float32 images (None when the map is missing)"""
    a = ad.load_map(set_name, g['key'])
    if a is None:
        return None
    a = np.asarray(a)
    if g['kind'] == 'loglum':
        lin = srgb_eotf(a[..., :3].astype(np.float32) / 255.0)
        L = lin[..., 0] * 0.2126 + lin[..., 1] * 0.7152 + lin[..., 2] * 0.0722
        return [np.log(np.maximum(L, 1e-3)).astype(np.float32)]
    if g['kind'] == 'normal':
        return [a[..., 0].astype(np.float32) / 127.5 - 1.0, a[..., 1].astype(np.float32) / 127.5 - 1.0]
    if g['kind'] == 'normal_delta':
        # the GENERATOR's own relief: the shipped normal less the bake of the high (g['ref']); the high's creases,
        # folds and rulings cancel by construction, what is left is the pattern the material pass drew
        r = ad.load_map(set_name, g['ref'])
        if r is None:
            return None
        return [(a[..., c].astype(np.float32) - r[..., c].astype(np.float32)) / 127.5 for c in (0, 1)]
    ch = g.get('ch', 0)
    return [(a[..., ch] if a.ndim == 3 else a).astype(np.float32) / 255.0]


def _tensor(xp, ndi, chans, M, Ra, Rb, Rc, s_hp, s_i):
    """the high-passed gradient structure tensor of chans inside mask M (crops, xp arrays), in the surface frame: the
    coherence, the dominant gradient's angle there, the energy (l1 + l2) and where it is valid"""
    Mf = M.astype(xp.float32)
    W = ndi.gaussian_filter(Mf, s_hp, mode='constant')
    Mg = M & xp.roll(M, 1, 1) & xp.roll(M, -1, 1) & xp.roll(M, 1, 0) & xp.roll(M, -1, 0)
    J11 = xp.zeros_like(Mf)
    J12 = xp.zeros_like(Mf)
    J22 = xp.zeros_like(Mf)
    for f in chans:
        lp = ndi.gaussian_filter(f * Mf, s_hp, mode='constant') / xp.maximum(W, 1e-6)
        hp = (f - lp) * Mf
        gx = 0.5 * (xp.roll(hp, -1, 1) - xp.roll(hp, 1, 1))
        gy = 0.5 * (xp.roll(hp, -1, 0) - xp.roll(hp, 1, 0))
        J11 += gx * gx
        J12 += gx * gy
        J22 += gy * gy
    Mgf = Mg.astype(xp.float32)
    Wi = ndi.gaussian_filter(Mgf, s_i, mode='constant')
    inv = 1.0 / xp.maximum(Wi, 1e-6)
    J11 = ndi.gaussian_filter(J11 * Mgf, s_i, mode='constant') * inv
    J12 = ndi.gaussian_filter(J12 * Mgf, s_i, mode='constant') * inv
    J22 = ndi.gaussian_filter(J22 * Mgf, s_i, mode='constant') * inv
    valid = M & (Wi > 0.25)
    # T_s = R^-T J R^-1 with R^-1 = [[p, q], [0, r]]
    p = 1.0 / Ra
    q = -Rb / (Ra * Rc)
    r = 1.0 / Rc
    T11 = p * p * J11
    T12 = p * (q * J11 + r * J12)
    T22 = q * q * J11 + 2.0 * q * r * J12 + r * r * J22
    tr = T11 + T22
    dif = xp.sqrt((T11 - T22) ** 2 + 4.0 * T12 * T12)
    coh = dif / xp.maximum(tr, 1e-30)
    phi = 0.5 * xp.arctan2(2.0 * T12, T11 - T22)
    return coh, phi, tr, valid


def _tensor_set(ad, G, g, gpu=True):
    """per inside texel the group's coherence, gradient angle (surface frame), energy and validity, island by island"""
    chans = _group_channels(ad, G.name, g)
    if chans is None:
        return None
    xp, ndi, to_np, _ = backend(gpu)
    s_hp = TH['hp_mm'] * 1e-3 * G.px_per_m
    s_i = TH['int_mm'] * 1e-3 * G.px_per_m
    pad = int(math.ceil(3.0 * max(s_hp, s_i))) + 2
    Ra = _img(G, G.Ra, 1.0, np.float32)
    Rb = _img(G, G.Rb, 0.0, np.float32)
    Rc = _img(G, G.Rc, 1.0, np.float32)
    out = dict(coh=np.zeros(G.n, np.float32), phi=np.zeros(G.n, np.float32), en=np.zeros(G.n, np.float32),
               val=np.zeros(G.n, bool))
    S = G.size
    for k, (y0, y1, x0, x1) in G.boxes.items():
        y0, x0 = max(y0 - pad, 0), max(x0 - pad, 0)
        y1, x1 = min(y1 + pad, S), min(x1 + pad, S)
        isl = G.island[y0:y1, x0:x1] == k
        # (rolls wrap round the crop: pad a ring of zeros so a wrap never joins two edges of the island)
        Mi = np.pad(isl, 1)
        cr = lambda a: xp.asarray(np.pad(a[y0:y1, x0:x1], 1, mode='edge'))
        coh, phi, en, val = _tensor(xp, ndi, [cr(c) for c in chans], xp.asarray(Mi), cr(Ra), cr(Rb), cr(Rc), s_hp, s_i)
        vm = to_np(val)[1:-1, 1:-1] & isl
        ii = G.idx[y0:y1, x0:x1][vm]
        out['coh'][ii] = to_np(coh)[1:-1, 1:-1][vm]
        out['phi'][ii] = to_np(phi)[1:-1, 1:-1][vm]
        out['en'][ii] = to_np(en)[1:-1, 1:-1][vm]
        out['val'][ii] = True
    return out


def _baselines(G, T, K, lo, hi, floor_frac):
    """per zone: the energy floor and the coherence threshold (median + K robust sigmas, clamped to [lo, hi]). The floor
    is the zone's (floor_frac x its median energy) but at least set_floor x the whole set's median: where a zone's own
    texture is suppressed (the octopus's oral layer keeps 5 % of the skin's relief) its maps' 8-bit steps are coherent
    contours, not a pattern (v5d's relief blob on the pale oral web)"""
    rows = {}
    thr = np.full(G.n, hi, np.float32)
    flo = np.full(G.n, np.inf, np.float32)
    skin = ~G.part                                       # (attached parts are no part of the skin's baselines)
    mall = T['val'] & (T['en'] > 0) & skin
    e_set = float(np.median(T['en'][mall])) if mall.any() else 0.0
    for z, nm in G.zone_names.items():
        mz = T['val'] & (G.zone == z) & (T['en'] > 0) & skin
        if mz.sum() < 500:
            continue
        e50 = float(np.median(T['en'][mz]))
        fl = max(floor_frac * e50, TH['set_floor'] * e_set)
        mm = mz & (T['en'] > fl)
        c = T['coh'][mm]
        med = float(np.median(c))
        mad = float(np.median(np.abs(c - med)))
        th = float(np.clip(med + K * 1.4826 * mad, lo, hi))
        sel = G.zone == z
        thr[sel] = th
        flo[sel] = fl
        rows[nm] = dict(texels=int(mm.sum()), coh_p50=round(med, 3), coh_mad=round(mad, 3),
                        coh_p95=round(float(np.percentile(c, 95)), 3), threshold=round(th, 3), energy_p50=e50)
    return thr, flo, rows


def _hough_fans(x, y, vx, vy, w, r_vote, cell, rng, max_fans=3, max_vote=8000):
    """each streak texel votes along its streak line (both ways, out to r_vote texels); a fan's centre collects the votes
    of every line through it. Returns fans (texel coords) with their support share, ray spread and alignment"""
    from scipy import ndimage as nd
    if len(x) > max_vote:
        j = rng.choice(len(x), max_vote, replace=False)
        x, y, vx, vy, w = x[j], y[j], vx[j], vy[j], w[j]
    wt = w.sum()
    alive = np.ones(len(x), bool)
    fans = []
    T = np.arange(2.0, r_vote, cell)
    T = np.concatenate([T, -T])
    x0, y0 = x.min() - r_vote - cell, y.min() - r_vote - cell
    nx = int((x.max() + r_vote + cell - x0) / cell) + 2
    ny = int((y.max() + r_vote + cell - y0) / cell) + 2
    for _ in range(max_fans):
        a = alive
        if a.sum() < 50:
            break
        px = x[a, None] + vx[a, None] * T[None]
        py = y[a, None] + vy[a, None] * T[None]
        ix = ((px - x0) / cell).astype(np.int64)
        iy = ((py - y0) / cell).astype(np.int64)
        acc = np.bincount((iy * nx + ix).ravel(), weights=np.repeat(w[a], len(T)), minlength=nx * ny)
        acc = nd.gaussian_filter(acc[:nx * ny].reshape(ny, nx), 1.0)
        jy, jx = np.unravel_index(int(np.argmax(acc)), acc.shape)
        cx, cy = x0 + (jx + 0.5) * cell, y0 + (jy + 0.5) * cell
        dx, dy = x - cx, y - cy
        dist = np.hypot(dx, dy)
        perp = np.abs(dx * vy - dy * vx)
        tol = np.maximum(2.0 * cell, dist * math.tan(math.radians(6.0)))
        sup = a & (perp < tol) & (dist < r_vote) & (dist > 1.0)
        if sup.sum() < 20:
            break
        ang = np.arctan2(dy[sup], dx[sup])
        mu = math.atan2(np.sin(ang).mean(), np.cos(ang).mean())
        rel = (ang - mu + np.pi) % (2 * np.pi) - np.pi
        spread = float(np.degrees(np.percentile(rel, 95) - np.percentile(rel, 5)))
        align = float((np.abs(dx[sup] * vx[sup] + dy[sup] * vy[sup]) / dist[sup] * w[sup]).sum() / w[sup].sum())
        fans.append(dict(cx=float(cx), cy=float(cy), frac=float(w[sup].sum() / wt), spread=spread, align=align,
                         n=int(sup.sum()), peak=float(acc.max())))
        alive &= ~sup
    return fans


def _streak_dirs(G, phi):
    """from the dominant gradient's angle in the surface frame: the streak direction (perpendicular to it) in texel
    space (unit vtx, vty) and on the creature (unit 3D)"""
    es0, es1 = -np.sin(phi), np.cos(phi)
    p, q, r = 1.0 / G.Ra, -G.Rb / (G.Ra * G.Rc), 1.0 / G.Rc
    vtx, vty = p * es0 + q * es1, r * es1
    nv = np.maximum(np.hypot(vtx, vty), 1e-20)
    vtx, vty = vtx / nv, vty / nv
    return vtx, vty, _unit(G.Dx * vtx[:, None] + G.Dy * vty[:, None])


def _to_3d(G, k, cx, cy):
    """a texel-space point of island k on the creature: the nearest island texel's point carried by its texel steps"""
    if getattr(G, 'isl_idx', None) is None:
        order = np.argsort(G.isl_c, kind='stable')
        cuts = np.searchsorted(G.isl_c[order], np.unique(G.isl_c), side='left')
        G.isl_idx = dict(zip(np.unique(G.isl_c).tolist(), np.split(order, cuts[1:])))
    m = G.isl_idx[int(k)]
    d = (G.xs[m] - cx) ** 2 + (G.ys[m] - cy) ** 2
    j = m[int(np.argmin(d))]
    return G.P[j] + G.Dx[j] * (cx - G.xs[j]) + G.Dy[j] * (cy - G.ys[j]), float(np.sqrt(d.min()))


def check_fill(ad, G, lm=None):
    """check 2's FILL: inside-island texels the bake never covered (drivers normal alpha 0; not hidden under a growth),
    which the dilation painted with their nearest covered texel's value in every map, the high's N included
    (bake.dilate_all; t11's maps alike): on the creature each is a copy-streak as long as that distance. Read from the
    coverage, not the maps: a miss a few mm deep copies bars as short as it is deep, and the copies from either side
    meet in a seam across them, so at the tensor's 1.5-2 mm scales its coherence drowns in the skin round it (review
    10-27, every map filled from the nearest covered texel: a 20 x 8 mm ellipse inside a mantle island and a 3 mm deep,
    40 mm sliver along an island's edge, both plainly barred, flagged 0 %). Clusters over fill_area, a finding when the
    longest copy reaches fill_len_mm; length_mm per inside texel (0 where covered)"""
    from scipy import ndimage as nd
    unc = ~G.cov_c & ~G.hidden_c
    out = dict(fill=unc, length_mm=np.zeros(G.n, np.float32), clusters=[])
    if not unc.any():
        return out
    d = nd.distance_transform_edt(~G.cov)              # the dilation's own transform: texels to the nearest covered
    L = (d[G.ys, G.xs] / (G.px_per_m * 1e-3)).astype(np.float32)
    del d
    out['length_mm'] = np.where(unc, L, 0.0).astype(np.float32)
    lm = ad.landmarks() if lm is None else lm
    for c in _clusters(G, unc, TH['fill_area'], close=1, open_=0):
        sel = c['sel'][unc[c['sel']]]
        if len(sel) == 0:
            continue
        info = _cluster_info(G, c, lm, ad)
        info['fill_len_max_mm'] = round(float(L[sel].max()), 2)
        info['fill_len_p50_mm'] = round(float(np.median(L[sel])), 2)
        info['finding'] = bool(info['fill_len_max_mm'] >= TH['fill_len_mm'])
        info['_sel'] = c['sel']
        out['clusters'].append(info)
    return out


def check_streaks(ad, sset, G, coord=None, gpu=True, log=print, seed=7):
    """check 2: per group the coherence against its zone baseline, explained by the high or not, clusters and fans;
    and the bake's FILL inside the islands (check_fill)"""
    t0 = time.time()
    groups = ad.groups(G.name)
    hg = ad.high_group(G.name)
    TT = {}
    for g in groups + ([hg] if hg else []):
        T = _tensor_set(ad, G, g, gpu)
        if T is not None:
            TT[g['name']] = T
    if not TT:
        return None
    t_tensors = time.time() - t0
    base = {}
    expl_ok = np.zeros(G.n, bool)
    hphi = None
    if hg and hg['name'] in TT:
        # the high explains where it is itself oriented, in absolute terms (its zone baseline can be high everywhere: on
        # the octopus's oral layer the smooth high is coherent almost all over, p50 0.57) and carries relief over its
        # zone's floor, the same floor the maps are held to there (a set-wide floor left the flanks of the oral creases
        # unexplained while the maps' zone floor kept them: v5d's normal-only fringes)
        H = TT[hg['name']]
        _, flo_h, rows_h = _baselines(G, H, 0.0, 0.0, 1.0, TH['energy_floor'])
        base[hg['name']] = rows_h
        # (only where the bake covered the texel: where it missed, the high's map holds the dilation's copies too, whose
        # bars would 'explain' the same bars in every other map)
        ok_h = H['val'] & (H['en'] > flo_h) & (H['coh'] > TH['high_lo']) & G.cov_c
        # every texel takes the nearest such texel of the high within high_reach_mm in its own island (its angle too)
        from scipy import ndimage as nd
        dist, (iy, ix) = nd.distance_transform_edt(~_img(G, ok_h, False, bool), return_indices=True)
        src = G.idx[iy[G.ys, G.xs], ix[G.ys, G.xs]]
        del iy, ix
        reach = TH['high_reach_mm'] * 1e-3 * G.px_per_m
        expl_ok = (src >= 0) & (dist[G.ys, G.xs] <= reach)
        expl_ok[expl_ok] &= G.isl_c[src[expl_ok]] == G.isl_c[expl_ok]
        hphi = np.where(expl_ok, H['phi'][np.maximum(src, 0)], 0.0)
    flags = {}
    excess = np.full(G.n, -1.0, np.float32)
    dom_phi = np.zeros(G.n, np.float32)
    dom = np.full(G.n, -1, np.int8)
    any_fl = np.zeros(G.n, bool)
    any_ex = np.zeros(G.n, bool)
    gnames = [g['name'] for g in groups if g['name'] in TT]
    ddirs = ad.designed_dirs(G.name, G) or {}
    for gi, nm in enumerate(gnames):
        T = TT[nm]
        thr, flo, rows = _baselines(G, T, TH['coh_k'], TH['coh_lo'], TH['coh_hi'], TH['energy_floor'])
        base[nm] = rows
        hot = T['val'] & (T['en'] > flo) & (T['coh'] > thr) & ~G.designed
        if nm in ddirs:
            dd, dm = ddirs[nm]
            d3g = _streak_dirs(G, T['phi'])[2]
            hot &= ~(dm & (np.abs((d3g * dd).sum(1)) > math.cos(math.radians(TH['high_tol']))))
        ex = np.zeros(G.n, bool)
        if hphi is not None:
            ex = hot & expl_ok & (np.abs(_wrap_half(T['phi'] - hphi)) < math.radians(TH['high_tol']))
        fl = hot & ~ex
        flags[nm] = dict(flag=fl, explained=ex, thr=thr)
        e = np.where(fl, T['coh'] - thr, -1.0)
        better = e > excess
        excess = np.where(better, e, excess)
        dom_phi = np.where(better, T['phi'], dom_phi)
        dom = np.where(better, gi, dom)
        any_fl |= fl
        any_ex |= ex
    # the streak direction per texel (from the dominant group): surface frame -> texel space -> 3D
    vtx, vty, d3 = _streak_dirs(G, dom_phi)
    # clusters and their fans
    lm = ad.landmarks()
    rng = np.random.default_rng(seed)
    cls = []
    px_mm = G.px_per_m * 1e-3
    cpos = {}
    for cn, A in (coord or {}).items():
        pos = np.full(G.n, -1, np.int64)
        pos[A['sel']] = np.arange(len(A['sel']))
        cpos[cn] = pos
    for c in _clusters(G, any_fl, TH['streak_area']):
        sel = c['sel']
        sel = sel[any_fl[sel]]
        if len(sel) < 30:
            continue
        info = _cluster_info(G, dict(c, sel=c['sel']), lm, ad)
        info['maps'] = {nm: round(float(flags[nm]['flag'][c['sel']].mean()), 3) for nm in gnames}
        # LATENT: only the masks the runtime reads later (the patch random) show it, not the colour, roughness or normal
        vis = [g['name'] for g in groups if g['name'] in gnames and not g.get('latent')]
        info['latent'] = bool(vis) and all(info['maps'][g] < 0.10 for g in vis)
        info['coh_p50'] = {nm: round(float(np.median(TT[nm]['coh'][sel])), 3) for nm in gnames}
        info['explained_share'] = round(float(any_ex[c['sel']].mean()), 3)
        # orientation agreement (bars) and fans
        w = np.maximum(excess[sel], 0.0) + 0.05
        ang2 = 2.0 * np.arctan2(vty[sel], vtx[sel])
        R2 = float(np.hypot((np.cos(ang2) * w).sum(), (np.sin(ang2) * w).sum()) / w.sum())
        fans = _hough_fans(G.xs[sel].astype(np.float64), G.ys[sel].astype(np.float64), vtx[sel].astype(np.float64),
                           vty[sel].astype(np.float64), w.astype(np.float64), TH['fan_vote_mm'] * px_mm,
                           max(1.0, 1.0 * px_mm), rng)
        fan_ok = [f for f in fans if f['frac'] >= TH['fan_frac'] and f['spread'] >= TH['fan_spread']
                  and f['align'] >= TH['fan_align']]
        for f in fans:
            p3, off = _to_3d(G, c['island'], f['cx'], f['cy'])
            f['centre_mm'] = [round(float(v) * 1000, 1) for v in p3]
            f['off_island_texels'] = round(off, 1)
            f['nearest'], f['nearest_mm'] = _nearest_landmark(lm, p3)
            if f['nearest_mm'] is not None:
                f['nearest_mm'] = round(f['nearest_mm'], 1)
            f['where'] = _describe(ad, p3)
            f['fan'] = f in fan_ok
        info['fans'] = fans
        info['kind'] = 'fan' if fan_ok else ('bars' if R2 >= TH['bars_r'] else 'mixed')
        info['orient_R'] = round(R2, 3)
        if coord:
            for cn, A in coord.items():
                pj = cpos[cn][sel]
                ok = pj >= 0
                if ok.any():
                    col = A['collapse'][pj[ok]]
                    info[f'coord_collapse_share[{cn}]'] = round(float(col.mean()), 3)
                    if col.any():
                        dd = np.abs((A['dir'][pj[ok]][col] * d3[sel][ok][col]).sum(1))
                        info[f'coord_dir_agree_deg[{cn}]'] = round(float(np.degrees(np.arccos(np.clip(np.median(dd),
                                                                                                         0, 1)))), 1)
        info['_sel'] = c['sel']
        cls.append(info)
    fill = check_fill(ad, G, lm)
    ff = [c for c in fill['clusters'] if c['finding']]
    log(f'[audit {ad.label}/{G.name}] check 2: flagged {any_fl.sum()} texels ({G.area[any_fl].sum()*1e4:.1f} cm2), '
        f'explained by the high {any_ex.sum()}; clusters {len(cls)} (fans {sum(c["kind"] == "fan" for c in cls)}, '
        f'bars {sum(c["kind"] == "bars" for c in cls)}); fill {int(fill["fill"].sum())} uncovered texels, '
        f'{len(ff)} fill findings ({sum(c["area_mm2"] for c in ff):.0f} mm2, copies up to '
        f'{max((c["fill_len_max_mm"] for c in ff), default=0.0):.2f} mm); {time.time()-t0:.1f}s '
        f'(tensors {t_tensors:.1f}s)')
    return dict(flags=flags, any=any_fl, explained=any_ex, excess=excess, dom=dom, vtx=vtx, vty=vty, d3=d3,
                baselines=base, clusters=cls, groups=gnames, tensors=TT, fill=fill)


# ----------------------------------------------------------------------------------------------------- 3. holes
def _relief(ad, G, gpu=True):
    """per inside texel the t10 normal's high-passed RMS over relief_mm (None without the high's map)"""
    hg = ad.high_group(G.name)
    if not hg:
        return None
    chans = _group_channels(ad, G.name, hg)
    if chans is None:
        return None
    xp, ndi, to_np, _ = backend(gpu)
    s_hp = TH['relief_hp_mm'] * 1e-3 * G.px_per_m
    s_r = TH['relief_mm'] * 1e-3 * G.px_per_m
    pad = int(math.ceil(3.0 * max(s_hp, s_r))) + 2
    out = np.zeros(G.n, np.float32)
    S = G.size
    for k, (y0, y1, x0, x1) in G.boxes.items():
        y0, x0 = max(y0 - pad, 0), max(x0 - pad, 0)
        y1, x1 = min(y1 + pad, S), min(x1 + pad, S)
        isl = G.island[y0:y1, x0:x1] == k
        M = xp.asarray(isl.astype(np.float32))
        W = ndi.gaussian_filter(M, s_hp, mode='constant')
        acc = xp.zeros_like(M)
        for c in chans:
            f = xp.asarray(c[y0:y1, x0:x1])
            hp = (f - ndi.gaussian_filter(f * M, s_hp, mode='constant') / xp.maximum(W, 1e-6)) * M
            acc += hp * hp
        Wr = ndi.gaussian_filter(M, s_r, mode='constant')
        rms = xp.sqrt(ndi.gaussian_filter(acc, s_r, mode='constant') / xp.maximum(Wr, 1e-6))
        ii = G.idx[y0:y1, x0:x1][isl]
        out[ii] = to_np(rms)[isl]
    return out


def check_holes(ad, sset, G, gpu=True, log=print):
    """check 3: the planted features' density per plantable surface area, local against its annulus and its zone"""
    feat = ad.features(G.name)
    if feat is None:
        return None
    t0 = time.time()
    k = max(1, int(round(TH['kde_step_mm'] * 1e-3 * G.px_per_m)))
    S = G.size
    gy, gx = np.meshgrid(np.arange(k // 2, S, k), np.arange(k // 2, S, k), indexing='ij')
    qi = G.idx[gy, gx]
    q_ok = qi >= 0
    q_idx = qi[q_ok]
    qP, qN = G.B[q_idx], G.N[q_idx]
    fz, fz_names = ad.feature_zones(G.name, G)
    # (no skin is planned under an attached part, G.part from the bake's material ids, nor within part_margin_mm of one)
    if G.part.any():
        from scipy.spatial import cKDTree
        _tree = cKDTree(G.B[G.part])
        skin_at = lambda P: ~np.isfinite(_tree.query(P, distance_upper_bound=TH['part_margin_mm'] * 1e-3)[0])
    else:
        skin_at = lambda P: np.ones(len(P), bool)
    plant_q = np.asarray(ad.plantable(G.name, qP, qN, fz[q_idx]), np.float32) * skin_at(qP)
    fp = np.asarray(feat['p'], np.float32)
    fnr = np.asarray(feat['n'], np.float32)
    dev = 'cuda:0' if wp.get_cuda_device_count() > 0 and gpu else 'cpu'

    def samples(stride):
        """the plantable-area samples every `stride` texels: points, normals, design-weighted area (m2)"""
        sy, sx = np.meshgrid(np.arange(stride // 2, S, stride), np.arange(stride // 2, S, stride), indexing='ij')
        si = G.idx[sy, sx]
        s_idx = si[si >= 0]
        w = np.asarray(ad.plantable(G.name, G.B[s_idx], G.N[s_idx], fz[s_idx]), np.float32) * skin_at(G.B[s_idx])
        return G.B[s_idx], G.N[s_idx], (G.area[s_idx] * stride * stride * w).astype(np.float32)

    def kde(sel, smp, sig):
        """the three Gaussian sums (features, plantable area) at query points sel under the kernels sig (m)"""
        sP, sN, s_area = smp
        rcut = 3.0 * float(sig[2])
        with wp.ScopedDevice(dev):
            fpa, fna = wp.array(fp, dtype=wp.vec3), wp.array(fnr, dtype=wp.vec3)
            spa, sna = wp.array(sP.astype(np.float32), dtype=wp.vec3), wp.array(sN.astype(np.float32), dtype=wp.vec3)
            fgrid = wp.HashGrid(128, 128, 128)
            fgrid.build(fpa, rcut)
            sgrid = wp.HashGrid(128, 128, 128)
            sgrid.build(spa, rcut)
            num = wp.zeros(len(sel), dtype=wp.vec3)
            den = wp.zeros(len(sel), dtype=wp.vec3)
            wp.launch(k_kde, dim=len(sel), inputs=[wp.array(qP[sel].astype(np.float32), dtype=wp.vec3),
                                                   wp.array(qN[sel].astype(np.float32), dtype=wp.vec3), fgrid.id, fpa,
                                                   fna, sgrid.id, spa, sna, wp.array(s_area, dtype=wp.float32),
                                                   float(sig[0]), float(sig[1]), float(sig[2]), rcut, 0.2, num, den])
            wp.synchronize()
            return num.numpy().astype(np.float64), den.numpy().astype(np.float64)

    def densities(num, den, s0_q):
        rho = num[:, 0] / np.maximum(den[:, 0], 1e-12)      # features per m2 of design-weighted plantable skin
        rho_ring = (num[:, 2] - num[:, 1]) / np.maximum(den[:, 2] - den[:, 1], 1e-12)
        # (tested where the design expects detail and the local kernel is at least half on plantable skin of that weight)
        plantable = (plant_q > TH['plant_min']) & (den[:, 0] > 0.5 * 2.0 * np.pi * s0_q * s0_q * np.maximum(plant_q, 1e-6))
        return rho, rho_ring, plantable

    zq = fz[q_idx]

    def medians(rho, plantable):
        return {z: float(np.median(rho[plantable & (zq == z)])) for z in fz_names
                if (plantable & (zq == z)).sum() >= 200}
    sig_def = np.asarray(TH['kde_mm'], np.float64) * 1e-3
    num, den = kde(np.arange(len(qP)), samples(2 * k), sig_def)
    s0_q = np.full(len(qP), sig_def[0])
    rho, rho_ring, plantable = densities(num, den, s0_q)
    # a kernel per zone that holds about kde_count features at the zone's own density (the noise the thresholds were set
    # at on the mantle, 7 / cm2 under 4 mm): a dense zone's narrow gaps are no longer blurred away (review 10-27: a bare
    # ring 6 mm wide round an arm at 44 / cm2 read 0.5 x its annulus under 4 mm, flagged 0 %)
    sig_zone, smp1 = {}, None
    for z, med in medians(rho, plantable).items():
        s0z = float(np.clip(np.sqrt(TH['kde_count'] / (2.0 * np.pi * max(med, 1e-9))), TH['kde_min_mm'] * 1e-3,
                            sig_def[0]))
        sig_zone[z] = s0z
        if s0z < 0.9 * sig_def[0]:
            smp1 = samples(k) if smp1 is None else smp1         # (finer area samples for a finer kernel)
            m = np.nonzero(zq == z)[0]
            num[m], den[m] = kde(m, smp1, sig_def * (s0z / sig_def[0]))
            s0_q[m] = s0z
    rho, rho_ring, plantable = densities(num, den, s0_q)
    rho_zone = np.zeros(len(qP))
    zrows = {}
    for z, nm in fz_names.items():
        m = plantable & (zq == z)
        if m.sum() < 200:
            continue
        med = float(np.median(rho[m]))
        rho_zone[zq == z] = med
        zrows[nm] = dict(points=int(m.sum()), density_p50_cm2=round(med * 1e-4, 2),
                         density_p10_cm2=round(float(np.percentile(rho[m], 10)) * 1e-4, 2),
                         kernel_mm=round(sig_zone.get(z, sig_def[0]) * 1e3, 2))
    ok_ref = rho_zone > 0
    hole = plantable & ok_ref & (((rho < TH['hole_ring'] * rho_ring) & (rho < TH['hole_zone'] * rho_zone))
                                 | (rho < TH['hole_deep'] * rho_zone))
    # the hole's EXTENT, what its area bar measures: the strict cores above sit a kernel's blur inside the bare skin
    extent = plantable & ok_ref & (rho < TH['hole_extent'] * np.minimum(rho_ring, rho_zone))
    # the relief the bake carries (t10), per zone over plantable skin
    rel = _relief(ad, G, gpu)
    rel_q = rel[q_idx] if rel is not None else None
    rel_ratio = None
    relief_hole = np.zeros(len(qP), bool)
    if rel_q is not None:
        rel_ratio = np.zeros(len(qP))
        full_w = plantable & (plant_q > 0.75)              # (relief is not linear in density: full-weight skin only)
        for z, nm in fz_names.items():
            m = full_w & (zq == z)
            if m.sum() < 200:
                continue
            med = float(np.median(rel_q[m]))
            rel_ratio[zq == z] = rel_q[zq == z] / max(med, 1e-9)
            if nm in zrows:
                zrows[nm]['relief_p50'] = round(med, 4)
        relief_hole = full_w & (rel_ratio < TH['relief_hole'])
    # per inside texel (the grid cell it falls in), and clusters
    # (padded to the full size: the grid's last cell can stop a row or column short of it, 1365 x 3 = 4095 of 4096)
    cell = lambda v: np.pad(np.repeat(np.repeat(v, k, 0), k, 1), ((0, max(0, S - v.shape[0] * k)),
                                                                  (0, max(0, S - v.shape[1] * k))), mode='edge')[:S, :S]
    Gimg = np.zeros(gy.shape, bool)
    Gimg[q_ok] = hole
    hole_c = cell(Gimg)[G.ys, G.xs]
    # the extent within one local kernel sigma of a strict core (a zone margin's thin sparse strips stay out)
    from scipy import ndimage as nd
    Gimg[q_ok] = extent
    Rimg = np.zeros(gy.shape, np.float32)
    Rimg[q_ok] = s0_q * G.px_per_m                         # (each zone's own local sigma, in texels)
    near_core = nd.distance_transform_edt(~_img(G, hole_c, False, bool)) <= cell(Rimg)
    ext_c = hole_c | (cell(Gimg) & near_core)[G.ys, G.xs]
    del near_core
    Gimg2 = np.zeros(gy.shape, bool)
    Gimg2[q_ok] = relief_hole
    rhole_c = cell(Gimg2)[G.ys, G.xs]
    gimg = lambda v: (lambda a: (a.__setitem__(q_ok, v), a)[1])(np.zeros(gy.shape, np.float32))
    rho_c = cell(gimg(rho))[G.ys, G.xs]
    ring_c = cell(gimg(rho_ring))[G.ys, G.xs]
    zone_c = cell(gimg(rho_zone))[G.ys, G.xs]
    relr_c = cell(gimg(rel_ratio))[G.ys, G.xs] if rel_ratio is not None else None
    plant_c = cell(gimg(plantable.astype(np.float32)))[G.ys, G.xs] > 0.5
    lm = ad.landmarks()
    cls = []
    hole_x = np.zeros(G.n, bool)
    for c in _clusters(G, ext_c, TH['hole_area'], close=k, open_=0):
        sel = c['sel']
        if not hole_c[sel].any():                          # (an extent with no strict core is no hole)
            continue
        hole_x[sel] = True
        info = _cluster_info(G, c, lm, ad)
        info['core_mm2'] = round(float(G.area[sel[hole_c[sel]]].sum() * 1e6), 1)
        info['density_cm2'] = round(float(np.median(rho_c[sel])) * 1e-4, 2)
        info['ring_cm2'] = round(float(np.median(ring_c[sel])) * 1e-4, 2)
        info['zone_cm2'] = round(float(np.median(zone_c[sel])) * 1e-4, 2)
        if relr_c is not None:
            info['relief_ratio'] = round(float(np.median(relr_c[sel])), 3)
            info['relief_bare_share'] = round(float(rhole_c[sel].mean()), 3)
        info['_sel'] = sel
        cls.append(info)
    hole_m = hole_c | hole_x                                # (the strict cores and the reported holes' extents)
    rcls = []
    for c in _clusters(G, rhole_c & ~hole_m, TH['hole_area'], close=k, open_=0):
        info = _cluster_info(G, c, lm, ad)
        if relr_c is not None:
            info['relief_ratio'] = round(float(np.median(relr_c[c['sel']])), 3)
        info['density_cm2'] = round(float(np.median(rho_c[c['sel']])) * 1e-4, 2)
        info['_sel'] = c['sel']
        rcls.append(info)
    log(f'[audit {ad.label}/{G.name}] check 3: {len(fp)} features, {len(qP)} points ({plantable.mean()*100:.0f} % '
        f'plantable), holes {G.area[hole_x].sum()*1e4:.1f} cm2 in {len(cls)} clusters (strict cores '
        f'{G.area[hole_c].sum()*1e4:.1f} cm2), relief-only holes {len(rcls)}; {time.time()-t0:.1f}s')
    return dict(hole=hole_m, hole_core=hole_c, relief=rhole_c & ~hole_m, rho=rho_c, ring=ring_c, zone_rho=zone_c,
                relief_ratio=relr_c, plantable=plant_c, zones=zrows, clusters=cls, relief_clusters=rcls, stride=k,
                n_features=len(fp))


# ----------------------------------------------------------------------------------------------------- outputs
def flag_image(G, c1, c2, c3):
    """the flags as one uint16 bit image per texel (FLAG_BITS): each check's REPORTED clusters under its own bit (coord,
    streak, fill, hole, relief), the tears and the high's explanations as they are (a tear is a line, no area bar), and
    every flagged texel no reported cluster holds as a speck"""
    bits = np.zeros(G.n, np.uint16)
    put = lambda m, nm: np.bitwise_or(bits, np.where(m, FLAG_BITS[nm], 0).astype(np.uint16), out=bits)

    def members(cls):
        m = np.zeros(G.n, bool)
        for c in cls or ():
            m[c['_sel']] = True
        return m
    raw = np.zeros(G.n, bool)
    if c1:
        for A in c1.values():
            m = np.zeros(G.n, bool)
            m[A['sel'][A['collapse']]] = True
            raw |= m
            put(m & members(A.get('clusters')), 'coord')
            m = np.zeros(G.n, bool)
            m[A['sel'][A['tear']]] = True
            put(m, 'tear')
    if c2:
        raw |= c2['any']
        put(c2['any'] & members(c2['clusters']), 'streak')
        put(c2['explained'] & ~c2['any'], 'explained')
        fl = c2.get('fill')
        if fl is not None:
            raw |= fl['fill']
            put(fl['fill'] & members([c for c in fl['clusters'] if c['finding']]), 'fill')
    if c3:
        raw |= c3['hole'] | c3['relief']
        put(c3['hole'] & members(c3['clusters']), 'hole')
        put(c3['relief'] & members(c3['relief_clusters']), 'relief')
    shown = (bits & (FLAG_BITS['coord'] | FLAG_BITS['streak'] | FLAG_BITS['fill'] | FLAG_BITS['hole']
                     | FLAG_BITS['relief'])) > 0
    put(raw & ~shown, 'speck')
    return bits


COLORS = dict(coord=(255, 40, 30), tear=(255, 170, 0), streak=(255, 40, 230), explained=(70, 120, 255),
              hole=(0, 230, 255), relief=(40, 215, 100), fan=(255, 255, 40), speck=(225, 225, 225),
              fill=(255, 255, 255))


def _composite(base_rgb, G, bits, which, fan_pts=None, grey=0.55):
    """the albedo greyed and darkened, the chosen flags laid over it (alpha), fan centres as yellow rings"""
    lum = base_rgb[..., :3].astype(np.float32) @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    img = np.repeat((lum * grey)[..., None], 3, -1)
    for nm in which:
        m = _img(G, (bits & FLAG_BITS[nm]) > 0, False, bool)
        a = 0.75 if nm in ('tear',) else (0.40 if nm == 'explained' else (0.30 if nm == 'speck' else
                                                                          (0.85 if nm == 'fill' else 0.62)))
        img[m] = img[m] * (1 - a) + np.array(COLORS[nm], np.float32) * a
    out = np.clip(img, 0, 255).astype(np.uint8)
    if fan_pts:
        from PIL import Image, ImageDraw
        im = Image.fromarray(out)
        dr = ImageDraw.Draw(im)
        r = max(6, G.size // 300)
        for x, y in fan_pts:
            dr.ellipse([x - r, y - r, x + r, y + r], outline=COLORS['fan'], width=max(2, r // 3))
            dr.line([x - 2 * r, y, x + 2 * r, y], fill=COLORS['fan'], width=max(1, r // 4))
            dr.line([x, y - 2 * r, x, y + 2 * r], fill=COLORS['fan'], width=max(1, r // 4))
        out = np.array(im)
    return out


def _fan_points(c2):
    pts = []
    if c2:
        for c in c2['clusters']:
            for f in c['fans']:
                if f['fan']:
                    pts.append((f['cx'], f['cy']))
    return pts


def uv_sheet(ad, G, bits, c2, out_png, tile=1024):
    """the flags on the UV layout: check 1 | check 2 | check 3 | all, each over the set's greyed albedo, islands outlined"""
    from PIL import Image, ImageDraw
    from scipy import ndimage as nd
    alb = ad.load_map(G.name, 'albedo')
    if alb is None:
        alb = np.full((G.size, G.size, 3), 128, np.uint8)
    edge = (nd.maximum_filter(G.island, 3) != nd.minimum_filter(G.island, 3))
    fans = _fan_points(c2)
    panels = [('1 coordinate collapse clusters (red) / tears (orange)', ('coord', 'tear'), None),
              ('2 streak clusters (magenta) / explained by the high (blue) / bake fill (white); fans yellow',
               ('explained', 'streak', 'fill'), fans),
              ('3 plan holes (cyan) / relief-only holes (green)', ('relief', 'hole'), None),
              ('all; flags under the area bars faint grey', ALL_FLAGS, fans)]
    tiles = []
    for title, which, fp in panels:
        img = _composite(alb, G, bits, which, fp)
        img[edge] = (230, 230, 230)
        im = Image.fromarray(img).resize((tile, tile), Image.LANCZOS)
        ImageDraw.Draw(im).rectangle([0, 0, tile, 18], fill=(0, 0, 0))
        ImageDraw.Draw(im).text((6, 3), f'{ad.label} / {G.name}: {title}', fill=(255, 255, 255))
        tiles.append(im)
    sheet = Image.new('RGB', (2 * tile, 2 * tile))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % 2) * tile, (i // 2) * tile))
    sheet.save(out_png)
    return out_png


ALL_FLAGS = ('speck', 'explained', 'relief', 'hole', 'coord', 'tear', 'streak', 'fill')
CHECK_FLAGS = (('check1', ('coord', 'tear'), 'check 1 coordinate collapse clusters (red) / tears (orange)'),
               ('check2', ('explained', 'streak', 'fill'),
                'check 2 streak clusters (magenta) / explained by the high (blue) / bake fill (white), fans yellow'),
               ('check3', ('relief', 'hole'), 'check 3 plan holes (cyan) / relief-only holes (green)'))


def overlay_renders(ad, geoms, bits_by_set, c2_by_set, out_dir, size=900, which=None, tag_prefix='overlay', only=None,
                    suffix='', title='all checks (1 red/orange, 2 magenta/blue/white fill, 3 cyan/green; under the bars '
                                     'grey)'):
    """the flags painted on the creature (forge/lookdev.py, the engine's shading): the greyed albedo with the flags and
    the set's own normal map (roughness floored at 0.35 so highlights do not hide the paint)"""
    from . import lookdev
    which = which or ALL_FLAGS
    mesh = ad.render_mesh()
    mats = []
    for s in ad.sets():
        G = geoms.get(s['name'])
        alb = ad.load_map(s['name'], 'albedo')
        if G is None or alb is None or s['name'] not in bits_by_set:
            mats.append(dict(albedo=np.full((8, 8, 3), 110, np.uint8), ior=1.33))
            continue
        fans = _fan_points(c2_by_set.get(s['name'])) if 'streak' in which else None
        img = _composite(alb, G, bits_by_set[s['name']], which, fans)
        nrm = ad.load_map(s['name'], 'normal')
        orm = ad.load_map(s['name'], 'orm')
        mats.append(dict(albedo=img, normal=None if nrm is None else nrm[..., :3],
                         rough=None if orm is None else np.maximum(orm[..., 1], 90), ior=1.33))
    outs = []
    for r in ad.renders():
        if only is not None and r['tag'] not in only:
            continue
        p = os.path.join(out_dir, f'{tag_prefix}_{r["tag"]}{suffix}.png')
        lookdev.render(mesh, mats, p, views=r['views'], size=size, center=r.get('center'), span=r.get('span'),
                       light_mix=(0.55, 0.65, 0.35), label=f'{ad.label} audit {r["tag"]}: {title}')
        outs.append(p)
    return outs


def _strip(o):
    """the report's JSON: no private arrays"""
    if isinstance(o, dict):
        return {k: _strip(v) for k, v in o.items() if not str(k).startswith('_')}
    if isinstance(o, (list, tuple)):
        return [_strip(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    return o


def _by_place(ad, set_name, G, cls, per=64):
    """each cluster's anatomical category (the majority of its texels, sampled, by ad.places) into c['place'], and the
    totals per category ({} without clusters, None when the adapter names no places)"""
    if not cls:
        return {}
    smp = [c['_sel'][::max(1, len(c['_sel']) // per)] for c in cls]
    pl = ad.places(set_name, G.B[np.concatenate(smp)])
    if pl is None:
        return None
    pl = np.asarray(pl).astype(str)
    out, k = {}, 0
    for c, s in zip(cls, smp):
        v, n = np.unique(pl[k:k + len(s)], return_counts=True)
        k += len(s)
        c['place'] = str(v[np.argmax(n)])
        o = out.setdefault(c['place'], dict(clusters=0, area_mm2=0.0))
        o['clusters'] += 1
        o['area_mm2'] = round(o['area_mm2'] + c['area_mm2'], 1)
    return out


def _verdict(row):
    """a set's verdict: CLEAN when no check reports a finding (no smearing collapse, no streak cluster, latent or not,
    no fill patch, no plan or relief hole); tears and collapses that do not smear are listed but do not fail it"""
    parts, clean = [], True
    a = lambda cl: round(sum(c['area_mm2'] for c in cl) / 100.0, 2)
    for nm, r in (row.get('check1') or {}).items():
        clean &= r['smearing'] == 0
        parts.append(f'check 1 "{nm}": {r["smearing"]} smearing collapses ({r["smearing_cm2"]} cm2) of '
                     f'{len(r["clusters"])} clusters, {r["tear_texels"]} tear texels')
    c2 = row.get('check2')
    if c2:
        vis = [c for c in c2['clusters'] if not c.get('latent')]
        clean &= not c2['clusters']
        parts.append(f'check 2: {len(vis)} streak clusters ({a(vis)} cm2, {sum(c["kind"] == "fan" for c in vis)} fans) '
                     f'+ {len(c2["clusters"]) - len(vis)} latent (masks only, {a([c for c in c2["clusters"] if c.get("latent")])} cm2)')
        ff = [c for c in (c2.get('fill') or {}).get('clusters') or () if c['finding']]
        clean &= not ff
        parts.append(f'check 2 fill: {len(ff)} patches the bake never covered ({a(ff)} cm2, copies up to '
                     f'{max((c["fill_len_max_mm"] for c in ff), default=0.0)} mm)')
    c3 = row.get('check3')
    if c3:
        clean &= not (c3['clusters'] or c3['relief_clusters'])
        parts.append(f'check 3: {len(c3["clusters"])} plan holes ({a(c3["clusters"])} cm2), '
                     f'{len(c3["relief_clusters"])} relief-only holes ({a(c3["relief_clusters"])} cm2)')
    return dict(clean=bool(clean), text=('CLEAN; ' if clean else 'FLAGS; ') + '; '.join(parts))


def _places_md(bp):
    return '; '.join(f'{k} {v["clusters"]} ({v["area_mm2"] / 100:.1f} cm2)'
                     for k, v in sorted(bp.items(), key=lambda kv: -kv[1]['area_mm2']))


def _md(rep):
    L = [f'# Streak audit: {rep["label"]}', '', f'run `{rep["run_dir"]}`, {rep["when"]}; total {rep["seconds"]:.1f} s', '']
    for n in rep.get('notes', []):
        L.append(f'- {n}')
    L += ['', '## Verdict', '']
    for s in rep['sets']:
        L.append(f'- set {s["name"]}: {s["verdict"]["text"]}')
    L += ['', '## Thresholds (audit_streaks.TH)', '']
    for k, v in rep['thresholds'].items():
        L.append(f'- `{k}` = {v}')
    for s in rep['sets']:
        L += ['', f'## Set {s["name"]} ({s["size"]}^2, {s["px_per_mm"]:.2f} px/mm, {s["texels"]} inside texels)', '']
        if s.get('parts_cm2'):
            L.append(f'- attached parts left out of checks 2 and 3 (the bake\'s material ids, texels hidden under '
                     f'growths): {s["parts_cm2"]} cm2')
        if s.get('fidelity'):
            L.append(f'- coordinate replica fidelity: {json.dumps(s["fidelity"])}')
        c1 = s.get('check1')
        if c1:
            for nm, r in c1.items():
                L.append(f'- check 1 `{nm}`: collapsed {r["collapsed_cm2"]} cm2 (weighted {r["weighted_cm2"]}), tears '
                         f'{r["tear_texels"]} texels; clusters {len(r["clusters"])} ({r["clusters_cm2"]} cm2), smearing '
                         f'{r["smearing"]} ({r["smearing_cm2"]} cm2)')
                if r.get('by_place'):
                    L.append(f'  - clusters by place: {_places_md(r["by_place"])}')
                for k, b in (r.get('by_anatomy') or {}).items():
                    L.append(f'  - {k}: {b["collapsed_cm2"]} of {b["cm2"]} cm2 collapsed, {b["tears"]} tear texels, '
                             f'aniso p50 {b["aniso_p50"]}')
                for c in r['clusters'][:12]:
                    L.append(f'  - {c["area_mm2"]:.0f} mm2, {c.get("where") or ""} at {c["centroid_mm"]} mm, aniso p50 '
                             f'{c.get("aniso_p50")}, w p50 {c.get("w_p50")}, smear {c["smear_mm"]} mm, '
                             f'{c["smear_cells"]} cell widths (squeeze {c.get("squeeze_p50")})'
                             f'{" (SMEARS)" if c["smears"] else ""}')
        else:
            L.append('- check 1: no coordinate exposed for this set')
        c2 = s.get('check2')
        if c2:
            L.append(f'- check 2: flagged {c2["flagged_cm2"]} cm2 ({c2["clusters_cm2"]} cm2 in {len(c2["clusters"])} '
                     f'clusters, {c2["specks_cm2"]} cm2 of specks under the area bar), explained by the high '
                     f'{c2["explained_cm2"]} cm2; per map {json.dumps(c2["per_map_cm2"])}')
            if c2.get('by_place'):
                L.append(f'  - clusters by place: {_places_md(c2["by_place"])}')
            fl = c2.get('fill') or {}
            if fl:
                L.append(f'  - fill (texels the bake never covered, painted by the dilation): {fl["texels"]} texels '
                         f'({fl["cm2"]} cm2), longest copy {fl["len_max_mm"]} mm; {fl["findings"]} patches over '
                         f'{TH["fill_area"]:.0f} mm2 with copies of {TH["fill_len_mm"]} mm or more'
                         + (f'; by place: {_places_md(fl["by_place"])}' if fl.get('by_place') else ''))
                for c in [c for c in fl['clusters'] if c['finding']][:8]:
                    L.append(f'    - fill {c["area_mm2"]:.0f} mm2, {c.get("where") or ""} at {c["centroid_mm"]} mm, uv '
                             f'{c["uv_box"]}: copies up to {c["fill_len_max_mm"]} mm (p50 {c["fill_len_p50_mm"]})')
            for g, rows in c2['baselines'].items():
                L.append(f'  - baseline `{g}`: ' + '; '.join(f'{z} p50 {r["coh_p50"]} thr {r["threshold"]}'
                                                            for z, r in rows.items()))
            for c in c2['clusters'][:16]:
                fz = [f for f in c['fans'] if f['fan']]
                fs = '; '.join(f'fan centre {f.get("where") or ""} {f["centre_mm"]} mm ({f["frac"]*100:.0f} % of the '
                               f'weight, rays over {f["spread"]:.0f} deg)' for f in fz)
                ca = ', '.join(f'{k.split("[")[0]} {v}' for k, v in c.items() if k.startswith('coord_'))
                L.append(f'  - {c["kind"]}{" (LATENT: masks only)" if c.get("latent") else ""} {c["area_mm2"]:.0f} mm2, '
                         f'{c.get("where") or ""} at {c["centroid_mm"]} mm; maps {c["maps"]}; explained share '
                         f'{c["explained_share"]}, covered {c["covered"]}' + (f'; {ca}' if ca else '')
                         + (f'; {fs}' if fs else ''))
        c3 = s.get('check3')
        if c3:
            L.append(f'- check 3: {c3["n_features"]} features; flagged {c3["hole_cm2"]} cm2 (strict cores '
                     f'{c3.get("core_cm2")} cm2), {len(c3["clusters"])} holes over the bar '
                     f'({round(sum(c["area_mm2"] for c in c3["clusters"]) / 100.0, 2)} cm2 of extent); relief-only '
                     f'{len(c3["relief_clusters"])}; zones {json.dumps(c3["zones"])}')
            if c3.get('by_place'):
                L.append(f'  - plan holes by place: {_places_md(c3["by_place"])}')
            if c3.get('relief_by_place'):
                L.append(f'  - relief-only holes by place: {_places_md(c3["relief_by_place"])}')
            for c in c3['clusters'][:12]:
                L.append(f'  - {c["area_mm2"]:.0f} mm2 (strict core {c.get("core_mm2")} mm2), {c.get("where") or ""} at '
                         f'{c["centroid_mm"]} mm: {c["density_cm2"]} / cm2 against ring {c["ring_cm2"]}, zone '
                         f'{c["zone_cm2"]}; relief ratio {c.get("relief_ratio")}')
            for c in c3['relief_clusters'][:6]:
                L.append(f'  - relief only: {c["area_mm2"]:.0f} mm2, {c.get("where") or ""} at {c["centroid_mm"]} mm: '
                         f'relief ratio {c.get("relief_ratio")}, planned {c["density_cm2"]} / cm2')
        L.append(f'- runtimes: {json.dumps(s["seconds"])}')
    L += ['', '## Images', ''] + [f'- `{os.path.basename(p)}`' for p in rep.get('images', [])]
    return '\n'.join(L) + '\n'


def run_audit(ad, out_dir, checks=(1, 2, 3), sets=None, gpu=True, renders=True, log=print, geoms=None):
    """the whole audit of one creature run: per set the geometry, the checks, the flag images and UV sheets; then the
    overlay renders and the report. geoms: {set: SetGeom} to reuse (planted-defect runs on the same low)"""
    os.makedirs(out_dir, exist_ok=True)
    t_all = time.time()
    rep = dict(label=ad.label, run_dir=ad.run_dir, when=time.strftime('%Y-%m-%d %H:%M'), thresholds=dict(TH),
               notes=list(ad.notes), sets=[], images=[])
    geoms = dict(geoms or {})
    bits_by, c2_by, results = {}, {}, {}
    for s in ad.sets():
        if sets and s['name'] not in sets:
            continue
        secs = {}
        t0 = time.time()
        G = geoms.get(s['name']) or set_geometry(ad, s, log)
        geoms[s['name']] = G
        secs['geometry'] = round(time.time() - t0, 1)
        t0 = time.time()
        c1 = check_coord(ad, s, G, gpu, log) if 1 in checks else None
        secs['check1'] = round(time.time() - t0, 1)
        t0 = time.time()
        c2 = check_streaks(ad, s, G, c1, gpu, log) if 2 in checks else None
        secs['check2'] = round(time.time() - t0, 1)
        t0 = time.time()
        c3 = check_holes(ad, s, G, gpu, log) if 3 in checks else None
        secs['check3'] = round(time.time() - t0, 1)
        t0 = time.time()
        fid = ad.fidelity(G.name, G) if 1 in checks else None
        bits = flag_image(G, c1, c2, c3)
        bits_by[G.name], c2_by[G.name] = bits, c2
        results[G.name] = dict(c1=c1, c2=c2, c3=c3)
        # the flags and the measures behind them, as texel images (float16; 0 where a check has no value)
        planes = {}
        if c1:
            A = next(iter(c1.values()))
            for k in ('aniso', 'w'):
                v = np.zeros(G.n, np.float16)
                v[A['sel']] = A[k]
                planes[f'c1_{k}'] = _img(G, v, 0, np.float16)
        if c2:
            planes['c2_excess'] = _img(G, np.maximum(c2['excess'], 0).astype(np.float16), 0, np.float16)
            if c2.get('fill') is not None:
                planes['c2_fill_mm'] = _img(G, c2['fill']['length_mm'].astype(np.float16), 0, np.float16)
        if G.part.any():
            planes['part'] = _img(G, G.part, False, bool)
        if c3:
            for k in ('rho', 'ring', 'zone_rho', 'relief_ratio'):
                if c3.get(k) is not None:
                    # (per cm2; clipped into float16's range where an empty annulus divides by ~0)
                    v = np.clip(np.asarray(c3[k], np.float64) * (1e-4 if k != 'relief_ratio' else 1.0), 0.0, 6.0e4)
                    planes[f'c3_{k}'] = _img(G, v.astype(np.float16), 0, np.float16)
            planes['c3_plantable'] = _img(G, c3['plantable'], False, bool)
        np.savez_compressed(os.path.join(out_dir, f'flags_{G.name}.npz'), bits=_img(G, bits, 0, np.uint16),
                            island=G.island, **planes)
        p = uv_sheet(ad, G, bits, c2, os.path.join(out_dir, f'uv_flags_{G.name}.png'))
        rep['images'].append(p)
        secs['outputs'] = round(time.time() - t0, 1)
        row = dict(name=G.name, size=G.size, px_per_mm=G.px_per_m * 1e-3, texels=G.n, seconds=secs, fidelity=fid,
                   parts_cm2=round(float(G.area[G.part].sum() * 1e4), 2))
        if c1:
            row['check1'] = {}
            for nm, A in c1.items():
                cl = A['clusters']
                sm = [c for c in cl if c['smears']]
                used = A['w'] >= TH['coord_w']
                row['check1'][nm] = dict(
                    collapsed_cm2=round(float(G.area[A['sel'][A['collapse']]].sum() * 1e4), 2),
                    weighted_cm2=round(float((G.area[A['sel']] * A['w'] * A['collapse']).sum() * 1e4), 2),
                    tear_texels=int(A['tear'].sum()), used_cm2=round(float(G.area[A['sel'][used]].sum() * 1e4), 1),
                    aniso_used_p05_p50=[round(float(np.percentile(A['aniso'][used], 5)), 3),
                                        round(float(np.median(A['aniso'][used])), 3)] if used.any() else None,
                    clusters_cm2=round(sum(c['area_mm2'] for c in cl) / 100.0, 2), smearing=len(sm),
                    smearing_cm2=round(sum(c['area_mm2'] for c in sm) / 100.0, 2),
                    by_place=_by_place(ad, G.name, G, cl), clusters=cl)
                bd = ad.coord_breakdown(G.name, G, A['sel'])
                if bd:
                    ar = G.area[A['sel']]
                    row['check1'][nm]['by_anatomy'] = {
                        k: dict(cm2=round(float(ar[m].sum() * 1e4), 1),
                                collapsed_cm2=round(float(ar[m & A['collapse']].sum() * 1e4), 1),
                                tears=int((m & A['tear']).sum()),
                                aniso_p50=round(float(np.median(A['aniso'][m & used])), 3) if (m & used).any() else None)
                        for k, m in bd.items()}
        if c2:
            inc = (bits & FLAG_BITS['streak']) > 0
            fl = c2.get('fill')
            fill_row = None if fl is None else dict(
                texels=int(fl['fill'].sum()), cm2=round(float(G.area[fl['fill']].sum() * 1e4), 2),
                len_max_mm=round(float(fl['length_mm'].max()), 2), clusters=fl['clusters'],
                findings=sum(c['finding'] for c in fl['clusters']),
                by_place=_by_place(ad, G.name, G, [c for c in fl['clusters'] if c['finding']]))
            row['check2'] = dict(flagged_cm2=round(float(G.area[c2['any']].sum() * 1e4), 2),
                                 explained_cm2=round(float(G.area[c2['explained']].sum() * 1e4), 2),
                                 clusters_cm2=round(float(G.area[inc].sum() * 1e4), 2),
                                 specks_cm2=round(float(G.area[c2['any'] & ~inc].sum() * 1e4), 2),
                                 by_place=_by_place(ad, G.name, G, c2['clusters']),
                                 baselines=c2['baselines'], clusters=c2['clusters'],
                                 per_map_cm2={g: round(float(G.area[c2['flags'][g]['flag']].sum() * 1e4), 2)
                                              for g in c2['groups']}, fill=fill_row)
        if c3:
            row['check3'] = dict(n_features=c3['n_features'], hole_cm2=round(float(G.area[c3['hole']].sum() * 1e4), 2),
                                 core_cm2=round(float(G.area[c3['hole_core']].sum() * 1e4), 2),
                                 relief_only_cm2=round(float(G.area[c3['relief']].sum() * 1e4), 2), zones=c3['zones'],
                                 by_place=_by_place(ad, G.name, G, c3['clusters']),
                                 relief_by_place=_by_place(ad, G.name, G, c3['relief_clusters']),
                                 clusters=c3['clusters'], relief_clusters=c3['relief_clusters'])
        row['verdict'] = _verdict(row)
        log(f'[audit {ad.label}/{G.name}] verdict: {row["verdict"]["text"]}')
        rep['sets'].append(row)
    if renders and bits_by:
        t0 = time.time()
        rep['images'] += overlay_renders(ad, geoms, bits_by, c2_by, out_dir)
        per = [r['tag'] for r in ad.renders() if r.get('per_check')]
        if per:
            for nm, which, title in CHECK_FLAGS:
                if int(nm[-1]) in checks:
                    rep['images'] += overlay_renders(ad, geoms, bits_by, c2_by, out_dir, which=which, only=per,
                                                     suffix=f'_{nm}', title=title)
        rep['render_seconds'] = round(time.time() - t0, 1)
    rep['seconds'] = time.time() - t_all
    with open(os.path.join(out_dir, 'report.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(_strip(rep), f, indent=1, default=float)
    with open(os.path.join(out_dir, 'report.md'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(_md(_strip(rep)))
    log(f'[audit {ad.label}] done in {rep["seconds"]:.1f}s -> {out_dir}')
    return dict(report=rep, geoms=geoms, results=results, bits=bits_by)

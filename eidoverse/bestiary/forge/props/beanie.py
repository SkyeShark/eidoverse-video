"""THE BEANIE (ACCESSORIES B5, 11-11; the old creator's hat 'beanie', ROADMAP B5; work/bestiary/accessories_b5/soft_NOTES.md):
a CUFFED RIB-KNIT WATCH CAP, the cap people picture when they hear "beanie" (the board: WIP_showcase/accessories/
beanie_00_...; the reference soft/beanie/refs_photos/bn_gingers_bar_cuffed_rib_CC0.jpg). Black by default; heather grey
and red as SKINS of one mesh and one set of maps. The old creator's beanie was a plain dome (creature_builder.js 2281);
the catalog plans it as a hat (remix/recipe.py ACCESSORIES['beanie']: radius 0.091, 2,000 triangles, knit).

THE OBJECT, AS WORN (a knit cap takes the head it is on: its rest shape here is the cap stretched over a person's head):
  * the BODY: one layer of 1 x 1 RIB knit from the head opening up over the crown, gathered at the top by SIX DECREASE
    LINES (the star where they meet);
  * the CUFF: the body's lower part turned up OUTWARD, a second layer on the first from the FOLD at the bottom edge to
    its top edge, which stands a little off the body (the cast-on edge);
  * the knit itself (the 1 x 1 rib's wales and purl valleys, each knit wale a column of V stitches, inverted on the cuff
    because it is turned up) is drawn in the material pass in OBJECT space, as the satin's floats are on the bow tie;
  * the wool's FUZZ is the runtime's own cloth terms (propMaterial: masks R drives the rim fuzz and the Charlie sheen),
    NOT a shell of cards: a shell is a second, alpha-tested draw over the whole crown (near pure overdraw: craft guide
    05.31, 15.43) and propMaterial has no alpha path; the silhouette is judged at the closest view before any shell.

  layers -> block-out SDF:  the knit's MID-SURFACE (the body at half its thickness, the fold's arc, the cuff's mid)
                            thickened by sdf.shell: the fold rounds the bottom edge, the shell's open edge rounds the
                            cuff's top lip
  -> the low:               lathe rings on 36 COLUMNS (every 6th on a decrease line) at the meridian's own stations
                            (turning angle), the fold and the lip as short arcs, a 4 -> 2 reduction to 18 and a 4 x 5
                            grid cap at the top (loft.reduce_ring / loft.cap: all quads); the inside at the same columns
  -> UV islands:            the crown and the cuff strip in three 60-degree SECTORS a side, the left side stacked on the
                            right (mirror); the top and the inside's top unique; the inside at half density
  -> voxel high + bake -> material (the knit) -> skins -> a glb delivered at 1024 with the hat's fit data

Frame (remix.js's item contract; forge/fit.py's hat): metres, +Y up, +Z the cap's FRONT, +X the wearer's left; the
ORIGIN the centre of the head opening on the SEAT PLANE: y = 0 is the fold's lowest point (the cap's bottom edge).

SIZES ([C] the catalog, [M] measured, [E] estimate of a real cap):
  * the head opening 152 x 192 mm at the band [E: a person's head at the band (ANSUR II breadth ~150-155, length
    ~190-198); the same oval the masks' strap rests on, face_mask SPEC head_a / head_c];
  * the inside's top 118 mm over the seat plane: a head's 95-100 mm over the band and 15-20 mm of air [E];
  * the knit 2.2 mm thick [E: a fine-gauge acrylic rib]; the cuff 62 mm [M: the photo, the cuff 0.38 of the held cap];
  * 166 wale pairs round [M: soft/beanie: 83 rib periods across the held cap's crown in the photo] = 3.4 mm a pair on
    the worn cap; the course 1.25 mm [E: fine-gauge machine knit].
"""
import numpy as np
import warp as wp

from .. import material as M
from .. import proc
from .. import sdf
from . import soft_common as SC

wp.set_module_options({'enable_backward': False, 'max_unroll': 1})

SPEC = dict(
    rx=0.076, rz=0.096,         # the INSIDE's semi-axes at the band (the head opening) [E]
    H=0.116,                    # the inside's dome height over its bottom ring (y0 = t): its top at y 0.118 [E]
    p=2.6,                      # the crown's superellipse exponent (fuller sides than an ellipse: a head) [E]
    back=0.008,                 # the top's centre lies this far behind the opening's centre (the occiput) [E]
    t=0.0022,                   # the knit's thickness, one layer [E]
    cuff=0.062,                 # the cuff's top edge over the seat plane [M]
    lip_flare=0.0006,           # the cuff's top edge stands this far off the body [E]
    wales=166,                  # wale pairs round the opening [M]
    course=0.00125,             # a course's height (one V stitch) [E]
    # (11-11 13:15: at 0.34 / 0.12 mm with a sharpened rib flank the knit's normals tilted so far that sub-pixel texels
    # faced away from the light at grazing angles: dark dotted speckle along the silhouettes and where the crown turns
    # away (beanie_06's macro view). A gentler cosine rib and shallower stitches; the valleys' shade stays in the AO
    # and the albedo)
    rib_amp=0.00022,            # a knit wale's crown over the purl valley [E]
    v_amp=0.00007,              # a V stitch's legs over the wale [E]
    dec_amp=0.00030,            # a decrease line's ridge [E]
    n_dec=6,                    # the decrease lines
)
K = 36                          # columns (column k at phi = 2 pi k / K from +Z toward +X); decreases on k = 3, 9, ...
RHO_RED, RHO_CAP = 0.33, 0.19   # the outer crown's reduction ring and the cap's ring (normalized radius)
REGIONS = ('crown', 'cuff', 'inside', 'top')
ZONES = ('knit', 'cuff', 'inside', 'trim')          # masks B = 0, 1/3, 2/3, 1 (the runtime's palette zones)
SHARES = dict(crown=1.0, cuff=1.0, top=1.0, inside=0.5, inside_top=0.5)
UV_SIZE = 2048              # the MASTER sheet (the bake's); delivered at DELIVER_SIZE
DELIVER_SIZE = 1024
# the recorded placing order and density (soft_common.pack's search, 11-11 11:45: 78.7 % of one 2048 sheet, least
# gutter 12.1 px, no overlap; 8,370 px/m = 0.119 mm a texel, delivered at 1024: 4,185 px/m = 1.8 texels a pixel of the
# closest view; `n05_forge.py low` with both set to None searches again, 10 minutes on a full machine)
UV_ORDER = ['crown_a', 'cuff_b', 'cuff_a', 'inside_c', 'crown_c', 'cuff_c', 'inside_b', 'crown_b', 'top', 'inside_top',
            'inside_a']
UV_PPM = 8370.055828052333

VARIANTS = dict(
    black=dict(name='beanie', knit=(0.016, 0.016, 0.017), heather=0.0),          # [E: a dyed black acrylic]
    heather=dict(name='beanie_heather', knit=(0.150, 0.150, 0.155), heather=0.55),   # a black-and-white fibre mix
    red=dict(name='beanie_red', knit=(0.420, 0.030, 0.026), heather=0.0),       # the watch cap's red
)
MATERIAL = dict(
    rough=0.86, rough_valley=0.93, fuzz=0.55, dust=(0.20, 0.19, 0.17), grime=0.30,
    seed=83, table_n=1024,
)


# ---------------------------------------------------------------------------------------------------- the layers
def y0(spec=SPEC):
    return spec['t']


def rho_y(y, o, spec=SPEC):
    """the normalized radius of the layer at offset o (0 inside, t the body's outside, 2 t the cuff's outside) at
    height y: a superellipse dome (vertical sides at its bottom ring y0)"""
    Hl = spec['H'] + o
    u = np.clip((np.asarray(y, np.float64) - y0(spec)) / Hl, 0.0, 1.0)
    return (1.0 - u ** spec['p']) ** (1.0 / spec['p'])


def y_rho(rho, o, spec=SPEC):
    rho = np.clip(np.asarray(rho, np.float64), 0.0, 1.0)
    return y0(spec) + (spec['H'] + o) * (1.0 - rho ** spec['p']) ** (1.0 / spec['p'])


def at_rho(phi, rho, o, spec=SPEC, flare=0.0, y=None):
    """a point of the layer at angle phi (from +Z toward +X) and normalized radius rho (its height from rho unless y
    is given: the fold and the cuff below the dome's bottom ring keep rho 1)"""
    phi, rho = np.broadcast_arrays(np.asarray(phi, np.float64), np.asarray(rho, np.float64))
    rx, rz = spec['rx'] + o + flare, spec['rz'] + o + flare
    cz = -spec['back'] * (1.0 - rho ** 2)
    yy = y_rho(rho, o, spec) if y is None else np.broadcast_to(np.asarray(y, np.float64), phi.shape)
    return np.stack([rx * rho * np.sin(phi), yy, cz + rz * rho * np.cos(phi)], -1)


def at_y(phi, y, o, spec=SPEC, flare=0.0):
    return at_rho(phi, rho_y(y, o, spec), o, spec, flare, y=y)


def rho_of_xz(x, z, o, spec=SPEC, flare=0.0):
    """the layer's normalized radius under (x, z) (the dome's top as a height field): rho^2 = (x / rx)^2 +
    ((z - cz(rho)) / rz)^2, solved by fixed point"""
    rx, rz = spec['rx'] + o + flare, spec['rz'] + o + flare
    x, z = np.asarray(x, np.float64), np.asarray(z, np.float64)
    r = np.sqrt((x / rx) ** 2 + (z / rz) ** 2)
    for _ in range(40):
        r = np.sqrt((x / rx) ** 2 + ((z + spec['back'] * (1.0 - r ** 2)) / rz) ** 2)
    return np.clip(r, 0.0, 1.0)


def project(P, o, spec=SPEC):
    """points moved onto the layer's dome along +Y (their (x, z) kept)"""
    P = np.array(P, np.float64)
    P[..., 1] = y_rho(rho_of_xz(P[..., 0], P[..., 2], o, spec), o, spec)
    return P


def flare(y, spec=SPEC):
    return spec['lip_flare'] * SC.smoothstep(spec['cuff'] - 0.015, spec['cuff'], y)


def meridian_stations(o, rho_lo, rho_hi, spec=SPEC, turn_deg=11.0, max_mm=13.0, side=0.5 * np.pi):
    """the dome's rings between rho_lo (low on the crown) and rho_hi (near the top): a new ring where the meridian has
    turned turn_deg or run max_mm since the last (craft guide 05.11; HIGH_TO_LOW rigid prop 16, the meridian's angle),
    read on the side's meridian (the front's agrees within a ring). Returns the rho of each ring, rho_lo first"""
    r = np.linspace(rho_lo, rho_hi, 4001)
    P = at_rho(np.full_like(r, side), r, o, spec)
    m = np.column_stack([np.hypot(P[:, 0], P[:, 2]), P[:, 1]])
    d = np.diff(m, axis=0)
    ang = np.degrees(np.arctan2(d[:, 1], -d[:, 0]))          # 90 at the vertical sides, 0 at the top
    ds = np.linalg.norm(d, axis=1)
    out = [rho_lo]
    acc_t, acc_s, a0 = 0.0, 0.0, ang[0]
    for i in range(len(d)):
        acc_s += ds[i]
        if abs(ang[i] - a0) >= turn_deg or acc_s >= max_mm * 1e-3:
            out.append(float(r[i + 1]))
            acc_s, a0 = 0.0, ang[i]
    if abs(out[-1] - rho_hi) < 0.02:
        out[-1] = rho_hi
    else:
        out.append(rho_hi)
    return np.array(out)


# ---------------------------------------------------------------------------------------------------- the low
PHI = 2.0 * np.pi * np.arange(K) / K


def _rings_part(rings, name, region, sector_isl, primary_side=True, attr_fn=None, orient_in=False, centre=None):
    """quads between consecutive rings of K points (rings: list of (K, 3)), islands by 60-degree SECTOR and side:
    quad column k in [0, 18) the primary side (x > 0), [18, 36) its mirror (quad k <-> 35 - k): names
    f'{sector_isl}_{a|b|c}' and '_R'. UVs: u the ring's own chord length from the sector's middle column, v the column's
    chord length from the first ring (the mirror's by symmetry the same numbers)"""
    nr = len(rings)
    V = np.vstack(rings)
    idx = np.arange(nr * K).reshape(nr, K)
    Q, isl, prim, uvq = [], [], [], []
    # chord lengths: along each ring (cumulative from column 0) and down each column
    ring_c = [np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(np.vstack([r, r[:1]]), axis=0), axis=1))])
              for r in rings]
    col_c = np.zeros((nr, K))
    for i in range(1, nr):
        col_c[i] = col_c[i - 1] + np.linalg.norm(rings[i] - rings[i - 1], axis=1)
    sect = ['a', 'b', 'c']
    for i in range(nr - 1):
        for k in range(K):
            k1 = (k + 1) % K
            q = [idx[i, k], idx[i, k1], idx[i + 1, k1], idx[i + 1, k]]
            side = k < K // 2
            km = k if side else K - 1 - k                    # the primary column this quad mirrors
            s = km // 6
            mid = 6 * s + 3                                  # the sector's middle column on the primary side
            corners = []
            for (ii, kk) in ((i, k), (i, k1), (i + 1, k1), (i + 1, k)):
                kp = kk if side else (K - kk) % K            # the vertex's primary twin column
                if not side and kk == 0:
                    kp = 0
                u = ring_c[ii][kp] - ring_c[ii][mid]
                corners.append([u, col_c[ii][kp]])
            Q.append(q)
            uvq.append(corners)
            isl.append(f'{sector_isl}_{sect[s]}' + ('' if side else '_R'))
            prim.append(side)
    Q = np.array(Q)
    uvq = np.array(uvq)
    if not primary_side:
        prim = [False] * len(Q)
    Qo = SC.orient(Q, V, centre=centre if centre is not None else np.array([0.0, 0.03, -0.004]))
    if orient_in:
        Qo = Qo[:, ::-1].copy()
    for f in range(len(Q)):
        if not np.array_equal(Qo[f], Q[f]):
            uvq[f] = uvq[f][::-1]
    attr = attr_fn(V) if attr_fn is not None else np.zeros((len(V), 4))
    return dict(name=name, region=region, V=V, Q=Qo, uv=uvq, island=isl, primary=np.array(prim), attr=attr)


def _attr(o, course_sign, base_y=None, spec=SPEC):
    """per-vertex material attributes: [0] rho of the layer under the vertex (the top's fade), [1] the course
    coordinate (metres along the wale: the height on the sides, continued over the dome by the meridian's chord), [2]
    the course direction (+1 the body, -1 the turned-up cuff), [3] the layer offset"""
    def f(V):
        rho = rho_of_xz(V[:, 0], V[:, 2], o, spec)
        A = np.zeros((len(V), 4))
        A[:, 0] = rho
        A[:, 1] = V[:, 1] if base_y is None else V[:, 1] - base_y
        A[:, 2] = course_sign
        A[:, 3] = o
        return A
    return f


def _top_part(ring36, o, name, region, island, inward=False, spec=SPEC):
    """the top: the 4 -> 2 reduction from a ring of 36 (ids 0..35 of `ring36`'s points) to 18 at RHO_CAP, and the 4 x 5
    grid cap (loft: all quads); every new vertex projected onto the layer's dome along +Y. One UNIQUE island, its UVs
    the plan (x, z): the top is within 25 degrees of level"""
    from .. import loft
    from ..mesh import QuadMesh
    rho_red = float(rho_of_xz(ring36[:, 0], ring36[:, 2], o, spec).mean())
    rho_cap = RHO_CAP * rho_red / RHO_RED
    V = np.asarray(ring36, np.float64)
    # (a dummy strip below the ring gives loft.cap's winding test the ring's existing faces; removed after)
    lower = V.copy()
    lower[:, 1] -= 0.002
    m = QuadMesh(np.vstack([V, lower]), np.array([[k, (k + 1) % K, K + (k + 1) % K, K + k] for k in range(K)]))
    inner_pos = at_rho(2.0 * np.pi * np.arange(K // 2) / (K // 2), rho_cap, o, spec)
    m, inner = loft.reduce_ring(m, np.arange(K), inner_pos)
    m, G = loft.cap(m, [int(x) for x in inner], [0.0, -1.0 if inward else 1.0, 0.0], shape=(4, 5))
    Vt = m.V.copy()
    new = np.arange(len(Vt)) >= 2 * K
    Vt[new] = project(Vt[new], o, spec)
    Qt = m.Q[K:]                                      # drop the dummy strip (its K faces came first)
    used = np.unique(Qt)
    remap = -np.ones(len(Vt), np.int64)
    remap[used] = np.arange(len(used))
    Vu = Vt[used]
    Qu = remap[Qt]
    Qo = SC.orient(Qu, Vu, toward=[0.0, -1.0 if inward else 1.0, 0.0])
    uv = np.column_stack([Vu[:, 0], -Vu[:, 2]])
    attr = _attr(o, 1.0, spec=spec)(Vu)
    return dict(name=name, region=region, V=Vu, Q=Qo, uv=uv, island=island, primary=True, attr=attr)


def build_low(spec=SPEC, log=print):
    """the designed low as PARTS (soft_common.assemble's): the crown (outer body above the cuff), the top (its reduction
    and cap), the cuff strip (the fold, the cuff's face, the lip into the body), the inside (its rings, its top). Every
    vertex on its layer by construction. Returns (parts, info)"""
    t, Hc = spec['t'], spec['cuff']
    o_in, o_out, o_cuff = 0.0, t, 2.0 * t
    # THE CROWN (the body's outside): from 3 mm under the cuff's lip (covered: the overlap, guide 05.27) to the
    # reduction ring, at the meridian's own stations
    rho_lo = float(rho_y(Hc - 0.003, o_out, spec))
    st = meridian_stations(o_out, rho_lo, RHO_RED, spec)
    crown_rings = [at_rho(PHI, r, o_out, spec) for r in st]
    crown = _rings_part(crown_rings, 'crown', 0, 'crown', attr_fn=_attr(o_out, 1.0, spec=spec))
    top = _top_part(crown_rings[-1], o_out, 'top', 3, 'top', spec=spec)
    # THE CUFF STRIP: the inside's bottom ring -> the FOLD (a half circle of radius t about (t, t) in the meridian
    # plane, 3 segments) -> the cuff's face (y t .. Hc, its rings where the head tapers) -> the LIP (the shell's rounded
    # edge, radius t/2 about the cuff's mid-surface end, 2 segments) -> into the body (0.25 mm under its outside)
    rings = []
    for th in np.radians([180.0, 240.0, 300.0, 360.0]):
        off = t + t * np.cos(th)
        yy = t + t * np.sin(th)
        rings.append(at_y(PHI, np.full(K, max(yy, 1e-6)), off, spec) * np.array([1.0, 0.0, 1.0])
                     + np.array([0.0, 1.0, 0.0]) * yy)
    for yy in (0.5 * (t + Hc), Hc):
        rings.append(at_y(PHI, np.full(K, yy), o_cuff, spec, flare=flare(yy, spec)))
    fl = flare(Hc, spec)
    for th in np.radians([90.0, 180.0]):
        off = 1.5 * t + fl + 0.5 * t * np.cos(th)
        yy = Hc + 0.5 * t * np.sin(th)
        rings.append(at_y(PHI, np.full(K, Hc), off, spec) * np.array([1.0, 0.0, 1.0])
                     + np.array([0.0, 1.0, 0.0]) * yy)
    rings.append(at_y(PHI, np.full(K, Hc - 0.0015), o_out - 0.00025, spec))
    cuff = _rings_part(rings, 'cuff', 1, 'cuff', attr_fn=_attr(o_cuff, -1.0, base_y=Hc, spec=spec))
    # THE INSIDE: from the fold's inner end up to its own reduction ring, every other crown station; then its top
    st_in = meridian_stations(o_in, float(rho_y(Hc, o_in, spec)), RHO_RED, spec, turn_deg=20.0, max_mm=26.0)
    in_rings = [at_y(PHI, np.full(K, t), o_in, spec), at_y(PHI, np.full(K, 0.5 * (t + Hc)), o_in, spec)]
    in_rings += [at_rho(PHI, r, o_in, spec) for r in st_in]
    inside = _rings_part(in_rings, 'inside', 2, 'inside', attr_fn=_attr(o_in, 1.0, spec=spec), orient_in=True)
    inside_top = _top_part(in_rings[-1], o_in, 'inside_top', 2, 'inside_top', inward=True, spec=spec)
    parts = [crown, top, cuff, inside, inside_top]
    nq = sum(len(p['Q']) for p in parts)
    log(f'[beanie] low: {len(parts)} parts, {nq} quads ({2 * nq} triangles): '
        + ', '.join(f'{p["name"]} {len(p["Q"])}' for p in parts)
        + f'; crown stations {len(st)} (rho {np.round(st, 3).tolist()}), inside {len(in_rings)}')
    return parts, dict(crown_rho=st, inside_rho=st_in)


# ------------------------------------------------------------------------------------------------ block-out
def mid_surface(spec=SPEC, n_phi=240):
    """the knit's MID-SURFACE as one grid (columns round, rows along the meridian path): the cuff's mid from its top
    edge down, the fold's arc, the body's mid up to the top. Returns (V, F, half-thickness per vertex)"""
    t, Hc = spec['t'], spec['cuff']
    phi = np.linspace(0.0, 2.0 * np.pi, n_phi, endpoint=False)
    rows = []
    for yy in np.linspace(Hc, t, 48):                                    # the cuff's mid, down
        rows.append(at_y(phi, np.full(n_phi, yy), 1.5 * t + flare(yy, spec), spec))
    for th in np.radians(np.linspace(360.0, 180.0, 13)[1:-1]):          # the fold's mid arc, round the bottom
        off = t + 0.5 * t * np.cos(th)
        yy = t + 0.5 * t * np.sin(th)
        rows.append(at_y(phi, np.full(n_phi, t), off, spec) * np.array([1.0, 0.0, 1.0]) + np.array([0.0, 1.0, 0.0]) * yy)
    rho = np.concatenate([rho_y(np.linspace(t, 0.08, 40), 0.5 * t, spec), np.linspace(0.84, 0.0, 120)[1:]])
    rho = np.unique(np.round(rho, 6))[::-1]
    for r in rho:                                                        # the body's mid, up to the top
        rows.append(at_rho(phi, np.full(n_phi, r), 0.5 * t, spec))
    V = np.vstack(rows)
    nr = len(rows)
    idx = np.arange(nr * n_phi).reshape(nr, n_phi)
    F = []
    for i in range(nr - 1):
        for k in range(n_phi):
            a, b, c, d = idx[i, k], idx[i, (k + 1) % n_phi], idx[i + 1, (k + 1) % n_phi], idx[i + 1, k]
            F += [[a, b, c], [a, c, d]]
    return V, np.array(F, np.int64), np.full(len(V), 0.5 * t)


def build_sdf(spec=SPEC):
    """the HIGH: the knit's mid-surface thickened (sdf.shell): the fold rounds the bottom edge, the shell's open edge
    the cuff's lip. The knit's relief (rib, stitches, decreases) is the material pass's (object space)"""
    prog = sdf.Program()
    V, F, ht = mid_surface(spec)
    prog.shell(V, F, ht, maxd=0.01, name='knit')
    return prog


def bounds(spec=SPEC, pad=0.004):
    t = spec['t']
    r = max(spec['rx'], spec['rz']) + 2.0 * t + spec['lip_flare'] + pad
    return np.array([-r, -pad, -r - spec['back']]), np.array([r, spec['H'] + 2.0 * t + t + pad, r])


# ------------------------------------------------------------------------------------------- the material pass
@wp.struct
class Surf:
    h: float
    col: wp.vec3
    rough: float
    fuzz: float
    zone: float
    cav: float
    wear: wp.vec4


@wp.func
def knit_h(p: wp.vec3, at: wp.vec4, texel: float, S: wp.array(dtype=wp.float32)):
    """the knit's height at p (metres): the 1 x 1 rib by the angle round (wale pairs S[0]), the V stitches along the
    knit wales (course S[1], the course direction at[2]), the decrease ridges on top (S[4] of them) where the wales
    converge; each term faded below 3 texels of its own pitch. Returns (height, the purl valley's depth 0..1)"""
    rx = S[6] + at[3]
    rz = S[7] + at[3]
    rho = at[0]
    cz = -S[8] * (1.0 - rho * rho)
    ang = wp.atan2(p[0] / rx, (p[2] - cz) / rz)                     # the parameter angle (-pi .. pi), 0 at the front
    rr = wp.max(rho, 0.02) * 0.5 * (rx + rz)
    pitch = 6.2831853 * rr / S[0]                                    # a wale pair's width here (metres)
    w = ang * S[0] / 6.2831853
    sw = w - wp.floor(w)                                             # 0 .. 1 across a wale pair (knit 0 .. 0.5)
    f_rib = proc.smoothstep(3.0, 5.0, pitch / texel) * proc.smoothstep(0.10, 0.30, rho)
    knit = 0.5 + 0.5 * wp.cos(6.2831853 * (sw - 0.25))
    rib = S[2] * (knit - 0.5) * f_rib                                # a plain cosine flank (13:15)
    # the V stitch: within the knit wale, two legs leaning in toward the wale's centre line
    dcen = wp.abs(sw - 0.25) / 0.25                                  # 0 at the wale's centre, 1 at its edges
    c = at[1] * at[2] / S[1] + 0.45 * wp.min(dcen, 1.0)
    g = c - wp.floor(c)
    leg = 1.0 - wp.abs(2.0 * g - 1.0)
    inwale = wp.clamp(1.0 - dcen, 0.0, 1.0)
    f_v = proc.smoothstep(3.0, 5.0, S[1] / texel) * f_rib
    vst = S[3] * (leg * leg - 0.33) * inwale * f_v - 0.4 * S[3] * wp.exp(-(dcen * dcen) / 0.02) * inwale * f_v
    # the decreases: S[4] ridges where the wales are gathered, on top
    sec = 6.2831853 / S[4]
    a2 = ang - 0.5 * sec
    dd = a2 - sec * wp.floor(a2 / sec + 0.5)                         # the angle to the nearest decrease line
    across = wp.abs(dd) * rr
    f_top = proc.smoothstep(0.62, 0.30, rho)
    dec = S[5] * wp.exp(-(across * across) / (0.0016 * 0.0016)) * f_top
    valley = wp.clamp(1.0 - knit, 0.0, 1.0) * f_rib
    return wp.vec2(rib + vst + dec, valley)


@wp.func
def surf_at(p: wp.vec3, reg: int, at: wp.vec4, ao: float, aol: float, texel: float,
            C: wp.array(dtype=wp.vec3), S: wp.array(dtype=wp.float32), seed: int, full: int):
    o = Surf()
    kh = knit_h(p, at, texel, S)
    o.h = kh[0]
    if full == 1:
        col = C[0]
        # the yarn's dye from course to course (+-3 %), the HEATHER's fibre mix (S[9]: black and white fibres twisted
        # into one yarn: a speckle at the plies' scale, 0.7 and 1.6 mm, stretched along the wale)
        q = wp.vec3(p[0], p[1] * 0.45, p[2])
        n1 = proc.noise3(q / 0.0007, seed + 3)
        n2 = proc.noise3(q / 0.0016, seed + 5)
        hz = S[9] * (0.65 * n1 + 0.35 * n2)
        lum = 1.0 + 0.03 * proc.noise3(p / 0.006, seed + 7) + hz
        col = col * wp.max(lum, 0.2)
        grime = wp.clamp(1.6 * (1.0 - ao) + 3.0 * wp.max(-aol, 0.0), 0.0, 1.0)
        w_dust = S[12] * grime * (0.5 + 0.5 * proc.noise3(p / 0.005, seed + 9))
        col = M.mix3(col, C[1], 0.25 * w_dust)
        o.col = col * (1.0 - 0.18 * kh[1])                          # the purl valleys a little darker (shade in the knit)
        o.rough = S[10] + (S[11] - S[10]) * kh[1]
        o.fuzz = S[13]
        o.zone = 0.0
        if reg == 1:
            o.zone = 1.0 / 3.0
        if reg == 2:
            o.zone = 2.0 / 3.0
        o.cav = kh[1]
        o.wear = wp.vec4(0.0, 0.0, w_dust, 0.0)
    return o


@wp.kernel
def k_beanie(uv_mesh: wp.uint64, size: int, ss: int, lpos: wp.array(dtype=wp.vec3), lnrm: wp.array(dtype=wp.vec3),
             ltan: wp.array(dtype=wp.vec4), lattr: wp.array(dtype=wp.vec4), lreg: wp.array(dtype=wp.int32),
             d_nrm: wp.array(dtype=wp.vec4), d_ao: wp.array(dtype=wp.float32), d_base: wp.array(dtype=wp.vec4),
             d_aol: wp.array(dtype=wp.float32), C: wp.array(dtype=wp.vec3), S: wp.array(dtype=wp.float32),
             texel: float, seed: int, o_alb: wp.array(dtype=wp.vec3), o_nrm: wp.array(dtype=wp.vec3),
             o_orm: wp.array(dtype=wp.vec3), o_mask: wp.array(dtype=wp.vec4), o_wear: wp.array(dtype=wp.vec4),
             o_hit: wp.array(dtype=wp.int32)):
    """bow_tie.k_tie's loop (supersampled texels, the bake's normal + the knit's height as a surface gradient, the
    normals' spread into roughness); the knit's purl valleys into the AO (ORM R) as well"""
    tid = wp.tid()
    x = tid % size
    y = tid // size
    dn = d_nrm[tid]
    if dn[3] <= 0.0:
        return
    tn_b = wp.normalize(wp.vec3(dn[0], dn[1], dn[2]))
    base = d_base[tid]
    inv = 1.0 / float(ss)
    dlt = 0.5 * inv
    acc_a = wp.vec3(0.0)
    acc_n = wp.vec3(0.0)
    acc_r = float(0.0)
    acc_k = wp.vec4(0.0)
    acc_w = wp.vec4(0.0)
    acc_c = float(0.0)
    hits = int(0)
    hb = float(0.0)
    have_hb = int(0)
    for i in range(ss):
        for j in range(ss):
            fx = float(x) + (float(i) + 0.5) * inv
            fy = float(y) + (float(j) + 0.5) * inv
            lo = M.low_at(uv_mesh, fx, fy, lpos, lnrm, ltan, lattr)
            if lo.ok == 0:
                continue
            if have_hb == 0:
                if base[3] > 0.5:
                    hb = wp.dot(wp.vec3(base[0], base[1], base[2]) - lo.p, lo.n)
                have_hb = 1
            lx = M.low_at(uv_mesh, fx + dlt, fy, lpos, lnrm, ltan, lattr)
            if lx.ok == 0:
                lx = M.low_at(uv_mesh, fx - dlt, fy, lpos, lnrm, ltan, lattr)
            ly = M.low_at(uv_mesh, fx, fy + dlt, lpos, lnrm, ltan, lattr)
            if ly.ok == 0:
                ly = M.low_at(uv_mesh, fx, fy - dlt, lpos, lnrm, ltan, lattr)
            reg = lreg[lo.face]
            pb0 = lo.p + lo.n * hb
            sf = surf_at(pb0, reg, lo.attr, d_ao[tid], d_aol[tid], texel, C, S, seed, 1)
            g = wp.vec3(0.0)
            if lx.ok == 1 and ly.ok == 1:
                pbx = lx.p + lx.n * hb
                pby = ly.p + ly.n * hb
                hx = surf_at(pbx, reg, lx.attr, 1.0, 0.0, texel, C, S, seed, 0).h
                hy = surf_at(pby, reg, ly.attr, 1.0, 0.0, texel, C, S, seed, 0).h
                g = M.surface_grad(pb0, pbx, pby, sf.h, hx, hy)
            nw = M.to_world(lo, tn_b)
            g = g - nw * wp.dot(g, nw)
            acc_n = acc_n + M.to_tangent(lo, wp.normalize(nw - g))
            acc_a = acc_a + sf.col
            acc_r = acc_r + wp.clamp(sf.rough, 0.04, 1.0)
            acc_k = acc_k + wp.vec4(sf.fuzz, 0.0, sf.zone, 0.0)
            acc_w = acc_w + sf.wear
            acc_c = acc_c + sf.cav
            hits = hits + 1
    if hits == 0:
        return
    fh = float(hits)
    ln = wp.length(acc_n) / fh
    var = wp.clamp((1.0 - ln) / wp.max(ln, 1.0e-4), 0.0, 1.0)
    rr = acc_r / fh
    a = rr * rr
    rr = wp.sqrt(wp.sqrt(a * a + var))
    o_alb[tid] = acc_a / fh
    o_nrm[tid] = wp.normalize(acc_n)
    o_orm[tid] = wp.vec3(d_ao[tid] * (1.0 - 0.30 * acc_c / fh), wp.clamp(rr, 0.0, 1.0), 0.0)
    o_mask[tid] = acc_k / fh
    o_wear[tid] = acc_w / fh
    o_hit[tid] = 1


def material_tables(variant, spec=SPEC, recipe=MATERIAL):
    C = np.array([VARIANTS[variant]['knit'], recipe['dust'], [0.0, 0.0, 0.0]], np.float32)
    S = np.array([spec['wales'], spec['course'], spec['rib_amp'], spec['v_amp'], spec['n_dec'], spec['dec_amp'],
                  spec['rx'], spec['rz'], spec['back'], VARIANTS[variant]['heather'], recipe['rough'],
                  recipe['rough_valley'], recipe['grime'], recipe['fuzz']], np.float32)
    return C, S


def run_material(L, drivers, size, texel, variant, ss=2, spec=SPEC, recipe=MATERIAL, log=print):
    import time

    from .. import calib
    t0 = time.time()
    pr = np.asarray(L['primary'], bool)
    F = L['F'][pr]
    uvm = M.uv_bvh(F, L['UV'], size)
    lpos, lnrm, ltan, lattr = M.corner_arrays(L['V'], F, L['N'], L['TAN'], L['ATTR'])
    keep = {k: drivers[k] for k in ('normal', 'ao', 'curvature', 'base', 'mat') if k in drivers}
    Dv = M.driver_arrays({**keep, **calib.relief_drivers(keep, 1.0 / texel)})
    C, S = material_tables(variant, spec, recipe)
    n = size * size
    o_alb, o_nrm, o_orm = (wp.zeros(n, dtype=wp.vec3) for _ in range(3))
    o_mask, o_wear = wp.zeros(n, dtype=wp.vec4), wp.zeros(n, dtype=wp.vec4)
    o_hit = wp.zeros(n, dtype=wp.int32)
    wp.launch(k_beanie, dim=n, inputs=[uvm.id, size, ss, lpos, lnrm, ltan, lattr,
                                       wp.array(np.asarray(L['region'], np.int32)[pr], dtype=wp.int32), Dv['normal'],
                                       Dv['ao'], Dv['base'], Dv['ao_local'], wp.array(C, dtype=wp.vec3),
                                       wp.array(S, dtype=wp.float32), float(texel), int(recipe['seed']), o_alb, o_nrm,
                                       o_orm, o_mask, o_wear, o_hit])
    wp.synchronize()
    img = lambda a, k: np.asarray(a.numpy()).reshape(size, size, k)[::-1]
    cov = np.asarray(o_hit.numpy()).reshape(size, size)[::-1] > 0
    maps = SC.finish_maps(img(o_alb, 3), img(o_nrm, 3), img(o_orm, 3), img(o_mask, 4), img(o_wear, 4), cov, ZONES)
    log(f'[beanie] material ({variant}) {size}^2 x ss {ss}: {time.time() - t0:.1f}s over {int(cov.sum())} texels '
        f'({cov.mean() * 100:.1f} % of the sheet); palette base (linear) '
        + ', '.join(f'{k} {np.round(v, 4).tolist()}' for k, v in maps['palette_base'].items()))
    return maps


# ------------------------------------------------------------------------------------------------- fit data
def fit_data(spec=SPEC, conform=None):
    """forge/fit.py's and the runtime's hat contract (cowboy_hat.fit_data's keys): the seat frame, the head opening,
    the crown's inner ceiling and outer size, the fit volume (G5), `rigid` (THE FIT LAW), conform per species"""
    t = spec['t']
    top_in = float(y_rho(0.0, 0.0, spec))
    top_out = float(y_rho(0.0, t, spec))
    r_out = max(spec['rx'], spec['rz']) + 2.0 * t + spec['lip_flare'] + 0.002
    hc = spec['cuff']
    circ = float(np.pi * (3 * (spec['rx'] + spec['rz'])
                          - np.sqrt((3 * spec['rx'] + spec['rz']) * (spec['rx'] + 3 * spec['rz']))))
    return dict(archetype='hat', prop='beanie', rigid=True,
                volume=dict(kind='cylinders', axis='+Y',
                            parts=[dict(name='cuff', y=[-0.002, round(hc + t + 0.002, 5)], radius=round(r_out, 5)),
                                   dict(name='crown', y=[-0.002, round(top_out + 0.002, 5)],
                                        radius=round(max(spec['rx'], spec['rz']) + t + 0.002, 5))],
                            note='the whole cap inside two upright cylinders about the seat axis (prop space, metres)'),
                seat=dict(origin=[0.0, 0.0, 0.0], up=[0.0, 1.0, 0.0], forward=[0.0, 0.0, 1.0], left=[1.0, 0.0, 0.0]),
                opening=dict(rx=spec['rx'], rz=spec['rz'], y=round(float(t), 5), circumference=round(circ, 5)),
                crown_inner_height=round(top_in, 5),
                crown_outer=dict(r_base=round(0.5 * (spec['rx'] + spec['rz']) + 2.0 * t, 5), r_top=0.0,
                                 height=round(top_out, 5)),
                cuff=dict(height=hc, layers=2, knit_thickness=t),
                knit=dict(wales=spec['wales'], course=spec['course'], decreases=spec['n_dec']),
                skins=list(VARIANTS), conform=conform or {})


def make_low(size=UV_SIZE, spec=SPEC, log=print):
    parts, info = build_low(spec, log)
    low = SC.assemble(parts)
    share = lambda nm: SHARES.get(nm.rsplit('_', 1)[0] if nm.split('_')[-1] in ('a', 'b', 'c', 'R') else nm,
                                  SHARES.get(nm.split('_')[0], 1.0))
    fill, place, ppm, order = SC.pack(low, {nm: share(nm) for nm in low['names']}, size=size, order=UV_ORDER,
                                      ppm=UV_PPM, g=4, tries=24, log=log)
    L = SC.low_arrays(low, place, ppm, size)
    log(f'[beanie] uv: {len(place)} primary islands of {len(low["names"])}; {ppm:.0f} px/m at {size} '
        f'({1000 / ppm:.3f} mm/texel), fill {fill * 100:.1f} %; order {order}')
    return L, low, info, dict(fill=fill, order=order, ppm=ppm)


def prop_json(L, spec=SPEC, out=None):
    """f07_fit.py's `prop=<json>` contract (the felt hats builder's fitter, used as it stands): the drawn low (V, F in
    the prop's frame) and band_tri, the triangles that grip the head: the inside's from the opening to the cuff's top"""
    reg = np.asarray(L['region'])
    F = L['F']
    cy = L['V'][F].mean(1)[:, 1]
    band = (reg == 2) & (cy <= spec['cuff'])
    return dict(low=dict(V=L['V'], F=F, band_tri=band),
                meta=dict(name='beanie', opening=dict(rx=spec['rx'], rz=spec['rz']), out=out))


def forge_bake(out_dir, size=UV_SIZE, voxel_size=0.0003, band_mm=0.0015, ss=2, seed=7, spec=SPEC, log=print):
    import os
    import time

    from .. import bake, voxel
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    L, low, info, uvr = make_low(size, spec, log=log)
    np.savez_compressed(os.path.join(out_dir, 'low_beanie.npz'),
                        **{k: v for k, v in L.items() if isinstance(v, np.ndarray)}, px_per_m=L['px_per_m'],
                        size=L['size'], quad_part=low['part'], Q=low['Q'], parts=np.array(low['parts']))
    prog = build_sdf(spec)
    f = np.abs(prog.eval(L['V']))
    log(f'[beanie] low on the block-out: |sdf| p50 {np.median(f) * 1e6:.0f} um, p99 '
        f'{np.percentile(f, 99) * 1e6:.0f} um, max {f.max() * 1e6:.0f} um')
    lo, hi = bounds(spec)
    G = voxel.SparseSDF(prog, lo, hi, voxel=voxel_size, band=band_mm, log=log)
    pr = L['primary']
    res = bake.bake(G, L['V'], L['F'][pr], L['UV'], L['N'], L['TAN'], L['region'][pr], size=size, ss=ss, cage=0.004,
                    ao_r=0.02, cav_r=0.002, n_thk=2, thk_max=0.01, seed=seed, log=log,
                    region_names=dict(enumerate(REGIONS)))
    keep = {k: (v.astype(np.float16) if v.dtype == np.float32 and k != 'base' else v) for k, v in res.items()
            if k != 'position' and isinstance(v, np.ndarray)}
    np.savez_compressed(os.path.join(out_dir, 'drivers_beanie.npz'), **keep)
    log(f'[beanie] the bake is saved (drivers_beanie.npz) after {time.time() - t0:.0f}s')
    return L


MASKS_CHANNELS = ('R fuzz / sheen amount (the wool), G material (0: a felt-like soft sheen), B palette zone (0 the knit, '
                  '1/3 the cuff, 2/3 the inside, 1 unused); RGB, no alpha')


def export_skins(out_dir, L, maps_by_variant, spec=SPEC, conform=None, deliver=DELIVER_SIZE):
    """THE SHIPPED CAP: ONE glb `beanie.glb`, its colours SKINS (black the default, heather, red: STAGED.md F5's format,
    the cowboy hat's way); maps delivered at `deliver` from the masters (soft_common.deliver_maps)"""
    import os
    order = ['black'] + [v for v in maps_by_variant if v != 'black']
    return SC.export_glb(os.path.join(out_dir, 'beanie.glb'), 'beanie', L, None, fit_data(spec, conform), ZONES,
                         MASKS_CHANNELS, 'hat', skins={v: maps_by_variant[v] for v in order}, deliver=deliver)

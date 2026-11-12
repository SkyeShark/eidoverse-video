"""Coasts (design section 4.11): sea cliffs cut back into the land, a wave-cut platform at their foot, beaches in
sheltered bays, stacks where the retreat isolates a strong knob of rock.

    stage ops (OPS; called by run.py as op(fields, level, params, seed, ctx=...)):
      'coast_land'  the land the sea will cut into, as a function of s0 (metres inland of an original coastline:
                    a line facing azimuth_deg, offset_m + retreat_m seaward of the main tile's centre, bent into
                    headlands and bays by wiggle noise): the shape (land_shape) rises inland from coast_frac at that
                    line to the uplands and falls seaward to base level kilometres out (the coastal plain of the low
                    sea levels the land was carved under, drowned and planed since). It writes U (U_m_per_yr x the
                    shape; sea_cliffs uses none: an old surface the rivers cut into), the start surface on a fresh
                    level, and coast_s0. The fluvial backbone (package 3) then carves the land toward that distant
                    base level, so its valleys reach the present cliff line high above the beach and are cut across:
                    the Seven Sisters' hanging dry valleys, Moher's plateau streams. (With the sea pinned at the
                    original coast instead, 300 m from the cliff, every valley graded to it and the cliff tops stood
                    16 m high where the reference's stand 63 m.)
      'coast'       the sea's work, on every level (the cliff is rebuilt sharp at each level's own cells):
        1. sea level: cells at or below it are sea;
        2. on the first level it runs on, the shore plan from the original shoreline: coast_land's s0 = 0 line where
           the land stage made one, else the surface's sea-level line, counting as sea only the water that reaches
           the window's edge (a hollow below sea level inland is land to the coast: sea_phi). The open-water fetch
           over 16 directions from every shore cell (the fetch kernel: an exact grid traversal over the sea mask
           up to fetch_max_m, 20 km) is normalised to the exposure 0..1 (0.5 on a straight open coast) and carried
           to every cell by jump flooding (JFA) from the shoreline at sub-cell precision together with the signed
           distance to that shoreline; both are fields (coast_E, coast_d0) that every finer level inherits, so all
           levels cut the same cliff line;
        3. the retreat distance R = retreat_m (E / 0.5)^exposure_power w(x): exposure times rock weakness (w =
           exp(weakness n), world-space noise: weak rock retreats into coves, strong rock stands as headlands;
           a strong knob on a headland cut from both sides stays as a stack, its walls at stack_face_deg, near
           vertical, so a narrow one stands as a column, not a pyramid) plus a few metres of crenellation (the
           cliff line's buttresses and recesses). Land closer than R to the original shore is cut away; cut regions
           that do not reach the sea or the window edge are filled back (the sea cannot get there);
        4. the cliff foot is the zero line of d0 - R; the signed distance s to it (JFA again, sub-cell) shapes the
           ground: inland the face, Z(s) = foot + s tan(face) (chalk 74-82 degrees, the angle of the nearest point
           of the foot line, so a face profile never turns down), or a rock column's stepped face (Moher: sandstone
           ledges at 84 degrees over siltstone at 58), meeting the land at a rounded edge, so the cliff stands as
           high as the land is there; seaward the wave-cut platform (platform_top_m at the foot, falling at
           platform_slope_deg to the sea floor sea_floor_m down, rough by a few decimetres), with a talus apron at
           35 degrees under the face (its height a share of the cliff's), a shingle toe on exposed coast, and in
           sheltered bays (low exposure) a sand beach: a berm, the beach face, and the Dean profile h = -A y^(2/3)
           below the waterline (A 0.1);
        5. wear (the rock cut away), talus (the apron), deposit (beach and shingle), bed (the rock surface) and Sc
           (the face's angle, for the detail package's breakup on the hero levels) are written; a child level's
           border band blends to its parent's surface.

Every input is a function of world position (metres) or a field inherited from the level that made the plan, so a
level's cliff line lies where its parent's does, at sub-cell precision.

Kernels (inline here, each with its numpy twin; core/gpu.py compiles them with common.glsl prefixed):
    coast_fetch  exposure of every shore sea cell (the 16-direction fetch, normalised; each ray walks every cell it
                 passes, so it cannot slip between two land cells meeting at a corner); -1 elsewhere
    coast_seed   the jump-flood seeds of a level set phi (< 0 seaward): every cell next to a sign change gets the
                 nearest zero crossing on its 8 neighbour segments (sub-cell), and the payload of the crossing's
                 seaward cell
    coast_jfa    one jump-flooding pass at a step: each cell keeps the nearest of the seeds its 9 probes see

Frames and units (design 2.1): arrays [row j, column i], row 0 south, cell centres at x0 + (i + 0.5) cell; metres,
degrees, years. Exposure is dimensionless (0..1).
"""
from __future__ import annotations

import math
import time

import numpy as np

from ..core import compose as C
from ..core import grid as Gd
from ..core import twins as T
from ..core import world_noise as N
from . import fluvial as FL

F32 = np.float32
E_REF = 0.5                     # the exposure of a straight open coast: half the rays run out to sea

# ------------------------------------------------------------------------------------------------ parameters ---

DEFAULTS = dict(
    sea_level=None,             # metres; None: the run's sea level (make_terrain's sea_level), else 0
    retreat_m=300.0,            # the retreat of a straight open coast (exposure 0.5) in average rock: about the
                                # wave-cut platform's width (Seven Sisters: 200-400 m)
    exposure_power=1.0,         # R ~ (E / 0.5)^power: headlands (high fetch) retreat faster than bays
    exposure_clamp=(0.25, 1.6),  # the exposure factor's range
    fetch_max_m=20000.0,        # the longest fetch the rays look along
    fetch_dirs=16,
    exposure_smooth_m=250.0,    # the exposure is smoothed along the shore (a cell's own fetch is noisy)
    weakness=0.15,              # ln-standard deviation of the rock weakness (chalk 0.15: a straight cliff line;
                                # layered shale and sandstone 0.45: coves, headlands, stacks)
    weakness_scales_m=(900.0, 300.0, 100.0),
    stacks=0.0,                 # strong knobs (0..1): where a headland is cut from both sides around one, a stack
    stack_scale_m=140.0,
    stack_face_deg=86.0,        # a knob stands because its rock is strong: its walls near vertical (with the
                                # coast's 74 degree bedded face a narrow knob converged to a pyramid, not a column)
    crenel_m=3.0,               # the cliff line's buttresses and recesses, metres (std)
    crenel_scales_m=(45.0, 15.0),
    face_deg=78.0,              # the cliff face (a single rock: chalk 74-82 degrees)
    face_spread_deg=4.0,        # +- by world noise at face_scale_m
    face_scale_m=70.0,
    column=None,                # None (one face angle), 'moher', or [(thickness_m, angle_deg), ...] repeating from
                                # column_base_m up: each bed stands at its own angle (the stepped face)
    column_base_m=0.0,          # the column's first bed starts at this stratigraphic height (m above sea level)
    column_dip_deg=0.0,         # the beds' dip and the compass direction they dip toward
    column_dip_azimuth_deg=180.0,
    top_round_m=2.5,            # the cliff top's rounding (a smooth minimum this many metres wide)
    talus_frac=0.07,            # the apron under the face: this share of the cliff's height, by noise 0.3-1.7 x
    talus_max_m=14.0,
    talus_deg=35.0,
    platform_top_m=-0.2,        # the wave-cut platform at the cliff foot, metres above sea level (intertidal: under
                                # the 0.3 m the references count as sea, so its runnels do not speckle the shore)
    platform_slope_deg=0.7,     # it falls seaward at this angle ...
    sea_floor_m=15.0,           # ... down to the sea floor this deep, which it meets in a smooth curve
    platform_rough_m=0.15,      # its runnels and steps (std, metres; 20 m and 6 m)
    shingle_m=1.3,              # the shingle toe at the foot of an exposed cliff: height and width
    shingle_w_m=14.0,
    beach_exposure=(0.30, 0.42),  # exposure where sand beaches take over (full beach below the first)
    beach_berm_m=2.2,           # the berm's height above sea level
    beach_backshore_m=35.0,     # the dry beach between the foot and the berm crest (full beach)
    beach_face_deg=6.0,         # the beach face from the berm crest to the waterline
    dean_A=0.1,                 # the Dean profile below the waterline: depth = A y^(2/3), m^(1/3) (fine sand)
    connect=True,               # cut regions must reach the sea (or the window edge)
    seed=0,
)

LAND_DEFAULTS = dict(
    azimuth_deg=200.0,          # the compass direction the coast faces (toward the sea): Seven Sisters 200
    offset_m=390.0,             # the cliff line passes this far from the main tile's centre, toward the sea
    retreat_m=300.0,            # (the coast stage's): the original coastline lies this much further seaward
    wiggle_m=120.0,             # the original coastline's headlands and bays (std, metres) ...
    wiggle_scale_m=2500.0,      # ... and their wavelength
    coast_frac=0.5,             # the land's height at the original coast, as a share of the uplands'
    rise_m=1500.0,              # inland of the original coast the land rises to the uplands over this distance ...
    inland_gain=0.35,           # ... then changes by this share toward tilt_m inland (negative: a dip slope, Moher)
    tilt_m=5000.0,
    texture=0.3,                # multi-scale texture of the uplift and the start (share)
    texture_scales_m=(3000.0, 1200.0),
    U_m_per_yr=0.0,             # uplift, m/yr x the shape (0: an old surface the rivers cut into, sea_cliffs' land)
    start_m=150.0,              # the start surface: the shape scaled to this height ...
    start_roughness=0.25,       # ... with this much noise (keep its gradients under the regional slope when U = 0,
    start_scales_m=(2400.0, 900.0),     # or its hollows outlast a short run)
    seed=0,
)
# Seaward of the original coast the land goes on down to base level (land_shape): the coastal plain of the low sea
# levels the downs were carved under, drowned since and planed by the waves. So the rivers' base level lies km out,
# and the valleys reach the present cliff line high above the beach, cut across: the Seven Sisters' hanging dry
# valleys (a sea pinned at the original coast instead graded every valley to it, 300 m from the cliff, and left the
# cliff tops 16 m high where the reference's stand 63 m).

# Rock columns for the stepped face: (thickness_m, face angle in degrees), from column_base_m up, repeated.
# Moher (Gull Island Formation over the Clare shales): sandstone beds standing near vertical, siltstone and shale
# partings cut back into ledges; the overall face about 74 degrees.
COLUMNS = {
    'moher': [(9.0, 84.0), (5.0, 58.0), (6.0, 82.0), (3.5, 55.0), (11.0, 85.0), (4.0, 60.0)],
}


def params_for(params=None, table=None):
    """The full parameter dict: DEFAULTS (or `table`), then the caller's values (an unknown key names the nearest)."""
    table = DEFAULTS if table is None else table
    out = dict(table)
    for k, v in (params or {}).items():
        if k in ('enabled',):
            continue
        if k not in table:
            import difflib
            near = difflib.get_close_matches(k, list(table), n=3)
            raise KeyError(f'coast: no parameter {k!r}' + (f'; nearest: {", ".join(near)}' if near else ''))
        out[k] = v
    return out


# =================================================================================================== kernels ===

def _dirs(n):
    """The fetch directions as exact float32 pairs (written into the kernel source, so the twin uses the same):
    n directions offset half a step from the grid axes, so no ray runs along an axis-aligned shore row."""
    a = 2.0 * math.pi * (np.arange(n) + 0.5) / n
    return np.stack([np.cos(a), np.sin(a)], 1).astype(F32)


def _inv_dirs(n):
    """1 / |direction| per axis, float32 (the ray parameter between two grid lines on that axis, in cells)."""
    return (1.0 / np.abs(_dirs(n).astype(np.float64))).astype(F32)


def _fetch_source(ndirs):
    d, inv = _dirs(ndirs), _inv_dirs(ndirs)
    table = ', '.join(f'vec2({float(x)!r}, {float(y)!r})' for x, y in d)
    itab = ', '.join(f'vec2({float(x)!r}, {float(y)!r})' for x, y in inv)
    return (r'''//! sampler seaT        x: 1 sea, 0 land
//! image   outE r32f     x: the exposure (mean fetch / the longest fetch, 0..1) of a shore sea cell; -1 elsewhere
//! uniform float uMaxCells   the longest fetch, cells
''' + f'const int NDIR = {ndirs};\nconst vec2 DIRS[{ndirs}] = vec2[{ndirs}]({table});\n'
            f'const vec2 INV[{ndirs}] = vec2[{ndirs}]({itab});\n' + r'''
/* Each ray walks every cell it passes through, in order (an exact grid traversal, Amanatides & Woo 1987: the k-th
   vertical grid line it crosses lies at t = (k + 0.5) / |dx| from the cell centre), so it cannot slip between two
   land cells that meet at a corner. The fetch is t where it enters the first land cell; leaving the grid over water
   or running past the longest fetch counts as open sea. */
void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(seaT, 0);
  if (!inside(p, n)) return;
  bool shore = false;
  if (texelFetch(seaT, p, 0).x > 0.5) {
    for (int k = 0; k < 8; k++) {
      ivec2 q;
      if (neighbour(p, k, n, BOUND_OPEN, q) && texelFetch(seaT, q, 0).x < 0.5) shore = true;
    }
  }
  if (!shore) {
    imageStore(outE, p, vec4(-1.0, 0.0, 0.0, 0.0));
    return;
  }
  float acc = 0.0;
  int maxIt = int(1.5 * uMaxCells) + 4;               /* a ray crosses at most |dx| + |dy| <= 1.42 lines per cell */
  for (int d = 0; d < NDIR; d++) {
    ivec2 st = ivec2(DIRS[d].x > 0.0 ? 1 : -1, DIRS[d].y > 0.0 ? 1 : -1);
    ivec2 c = p;
    int kx = 0;
    int ky = 0;
    float f = uMaxCells;
    for (int it = 0; it < maxIt; it++) {
      precise float tx = (float(kx) + 0.5) * INV[d].x;
      precise float ty = (float(ky) + 0.5) * INV[d].y;
      float t;
      if (tx < ty) {
        t = tx;
        c.x += st.x;
        kx++;
      } else {
        t = ty;
        c.y += st.y;
        ky++;
      }
      if (t > uMaxCells) break;
      if (!inside(c, n)) break;
      if (texelFetch(seaT, c, 0).x < 0.5) {
        f = max(t, 0.5);
        break;
      }
    }
    acc += f;
  }
  imageStore(outE, p, vec4(acc / (float(NDIR) * uMaxCells), 0.0, 0.0, 0.0));
}
''')


_FETCH = {}


def fetch_kernel(ndirs=16):
    if ndirs not in _FETCH:
        _FETCH[ndirs] = FL.Inline(f'coast_fetch_{ndirs}', _fetch_source(ndirs))
        T.twin(f'coast_fetch_{ndirs}')(lambda s, u, _n=ndirs: _fetch_twin(s, u, _n))
    return _FETCH[ndirs]


def shore_cells(sea):
    """Sea cells with a land cell among their 8 neighbours (the cells the fetch is measured from)."""
    sea = np.asarray(sea, bool)
    shore = np.zeros_like(sea)
    for k in range(8):
        q, ok = T.neighbour(sea, k, T.BOUND_OPEN, fill=True)
        shore |= ok & ~q
    return shore & sea


def _fetch_twin(s, u, ndirs):
    """The fetch kernel's exact grid traversal, vectorised over the shore cells (float32 as the kernel)."""
    sea = s['seaT'][..., 0] > 0.5
    H, W = sea.shape
    maxc = F32(u['uMaxCells'])
    max_it = int(F32(1.5) * maxc) + 4
    out = np.full((H, W), F32(-1.0))
    jj, ii = np.nonzero(shore_cells(sea))
    if jj.size == 0:
        return {'outE': out[..., None]}
    acc = np.zeros(jj.size, F32)
    for d, inv in zip(_dirs(ndirs), _inv_dirs(ndirs)):
        sx, sy = (1 if d[0] > 0 else -1), (1 if d[1] > 0 else -1)
        ci, cj = ii.astype(np.int64), jj.astype(np.int64)
        kx = np.zeros(jj.size, np.int64)
        ky = np.zeros(jj.size, np.int64)
        f = np.full(jj.size, maxc, F32)
        live = np.arange(jj.size)
        for _ in range(max_it):
            if live.size == 0:
                break
            tx = ((kx[live].astype(F32) + F32(0.5)) * inv[0]).astype(F32)
            ty = ((ky[live].astype(F32) + F32(0.5)) * inv[1]).astype(F32)
            xs = tx < ty
            t = np.where(xs, tx, ty)
            ci[live] += np.where(xs, sx, 0)
            cj[live] += np.where(xs, 0, sy)
            kx[live] += xs
            ky[live] += ~xs
            go = (t <= maxc)
            c_i, c_j = ci[live], cj[live]
            ins = (c_i >= 0) & (c_j >= 0) & (c_i < W) & (c_j < H)
            go &= ins
            land = np.zeros(live.size, bool)
            land[go] = ~sea[c_j[go], c_i[go]]
            hit = live[land]
            f[hit] = np.maximum(t[land], F32(0.5))
            live = live[go & ~land]
        acc = (acc + f).astype(F32)
    out[jj, ii] = acc / (F32(ndirs) * maxc)
    return {'outE': out[..., None]}


SEED = FL.Inline('coast_seed', r'''//! sampler phiT   x: the level set phi (metres): < 0 seaward (sea, cut), >= 0 landward
//! sampler payT   x: a payload read on the seaward cell of each crossing (the exposure)
//! image   outS rgba32f   x, y: the nearest zero crossing on the 8 neighbour segments (cells), z: payload, w: 1
/* outS is all 0 where the cell has no sign change among its neighbours */
void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(phiT, 0);
  if (!inside(p, n)) return;
  float a = texelFetch(phiT, p, 0).x;
  bool neg = a < 0.0;
  float pa = texelFetch(payT, p, 0).x;
  vec4 best = vec4(0.0);
  float bd = 1e30;
  for (int k = 0; k < 8; k++) {
    ivec2 q;
    if (!neighbour(p, k, n, BOUND_OPEN, q)) continue;
    float b = texelFetch(phiT, q, 0).x;
    if ((b < 0.0) == neg) continue;
    precise float t = a / (a - b);
    precise float dd = t * LEN[k];
    dd = dd * dd;
    if (dd < bd) {
      bd = dd;
      precise vec2 x = vec2(p) + t * vec2(OFF[k]);
      best = vec4(x, neg ? pa : texelFetch(payT, q, 0).x, 1.0);
    }
  }
  imageStore(outS, p, best);
}
''')

JFA = FL.Inline('coast_jfa', r'''//! sampler st     x, y: the nearest seed known (cell units), z: its payload, w: 1 when a seed is known
//! image   outS rgba32f
//! uniform int uStep   the probe step, cells
void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  vec4 best = texelFetch(st, p, 0);
  vec2 pc = vec2(p);
  precise vec2 d0 = best.xy - pc;
  precise float bd = best.w > 0.5 ? d0.x * d0.x + d0.y * d0.y : 1e30;
  for (int dy = -1; dy <= 1; dy++) {
    for (int dx = -1; dx <= 1; dx++) {
      if (dx == 0 && dy == 0) continue;
      ivec2 q = p + ivec2(dx, dy) * uStep;
      if (!inside(q, n)) continue;
      vec4 c = texelFetch(st, q, 0);
      if (c.w < 0.5) continue;
      precise vec2 d = c.xy - pc;
      precise float dd = d.x * d.x + d.y * d.y;
      if (dd < bd) {
        bd = dd;
        best = c;
      }
    }
  }
  imageStore(outS, p, best);
}
''')


@T.twin('coast_seed')
def coast_seed(s, u):
    phi = s['phiT'][..., 0]
    pay = s['payT'][..., 0]
    H, W = phi.shape
    jj, ii = np.mgrid[0:H, 0:W]
    pi, pj = ii.astype(F32), jj.astype(F32)
    neg = phi < 0
    best = np.zeros((H, W, 4), F32)
    bd = np.full((H, W), F32(1e30))
    for k in range(8):
        dx, dy = T.OFF[k]
        b, ok = T.neighbour(phi, k, T.BOUND_OPEN)
        pq, _ = T.neighbour(pay, k, T.BOUND_OPEN)
        cross = ok & ((b < 0) != neg)
        with np.errstate(divide='ignore', invalid='ignore', over='ignore'):
            t = (phi / (phi - b)).astype(F32)
            dd = (t * T.LEN[k]).astype(F32)
            dd = (dd * dd).astype(F32)
            take = cross & (dd < bd)
            bd = np.where(take, dd, bd)
            x = (pi + t * F32(dx)).astype(F32)
            y = (pj + t * F32(dy)).astype(F32)
        v = np.where(neg, pay, pq)
        for c, a in enumerate((x, y, v, np.ones_like(x))):
            best[..., c] = np.where(take, a, best[..., c])
    return {'outS': best}


@T.twin('coast_jfa')
def coast_jfa(s, u):
    st = s['st']
    step = int(u['uStep'])
    H, W = st.shape[:2]
    jj, ii = np.mgrid[0:H, 0:W]
    pi, pj = ii.astype(F32), jj.astype(F32)
    best = st.copy()
    dx0 = (best[..., 0] - pi).astype(F32)
    dy0 = (best[..., 1] - pj).astype(F32)
    bd = np.where(best[..., 3] > 0.5, (dx0 * dx0 + dy0 * dy0).astype(F32), F32(1e30))
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            c, ok = T.shift(st, dx * step, dy * step, T.BOUND_OPEN)
            ex = (c[..., 0] - pi).astype(F32)
            ey = (c[..., 1] - pj).astype(F32)
            dd = (ex * ex + ey * ey).astype(F32)
            take = ok & (c[..., 3] > 0.5) & (dd < bd)
            bd = np.where(take, dd, bd)
            best = np.where(take[..., None], c, best)
    return {'outS': best}


def jfa_steps(n):
    """The jump-flooding schedule for an n-cell grid: n/2, n/4, ..., 1, then 2 and 1 again (JFA+2: the few cells
    plain JFA leaves on a wrong seed pick the right one)."""
    steps = []
    k = 1
    while k < n:
        k *= 2
    k //= 2
    while k >= 1:
        steps.append(k)
        k //= 2
    return steps + [2, 1]


def nearest_crossing(dev, phi, payload=None):
    """Jump flooding from the zero line of `phi` ((n, n), < 0 seaward). Returns (dist_cells, payload): the
    unsigned distance of every cell centre to the nearest zero crossing (cell units, sub-cell precise) and that
    crossing's payload (0 when none is given). Cells with no crossing anywhere get +inf."""
    phi = np.asarray(phi, F32)
    pay = np.zeros_like(phi) if payload is None else np.asarray(payload, F32)
    H, W = phi.shape
    A = FL.Pair(dev, np.zeros((H, W, 4), F32))
    dev.run(SEED, {'phiT': dev.texture(phi), 'payT': dev.texture(pay)}, {'outS': A.src}, {})
    for st in jfa_steps(max(H, W)):
        dev.run(JFA, {'st': A.src}, {'outS': A.dst}, {'uStep': int(st)})
        A.swap()
    s = dev.read(A.src)
    jj, ii = np.mgrid[0:H, 0:W]
    d = np.hypot(s[..., 0] - ii, s[..., 1] - jj)
    d = np.where(s[..., 3] > 0.5, d, np.inf)
    return d, s[..., 2].astype(np.float64)


def exposure(dev, sea, cell, fetch_max_m=20000.0, ndirs=16):
    """The exposure of every shore sea cell (mean open-water fetch over ndirs directions / fetch_max_m, 0..1; rays
    leaving the grid over water count as open sea); -1 on every other cell."""
    sea = np.asarray(sea, F32)
    out = dev.empty(sea.shape, 1)
    dev.run(fetch_kernel(ndirs), {'seaT': dev.texture(sea)}, {'outE': out},
            {'uMaxCells': float(max(1, int(round(fetch_max_m / cell))))})
    return dev.read(out)[..., 0].astype(np.float64)


def exposure_bruteforce(sea, cell, fetch_max_m, ndirs=16, cells=None):
    """The test oracle: an independent ray count. From each shore sea cell (or the given (j, i) cells) a ray in
    each direction is walked through every grid cell it passes (an exact traversal, Amanatides & Woo 1987) until
    the first land cell or the longest fetch; leaving the grid counts as open sea. Returns {(j, i): exposure}."""
    sea = np.asarray(sea, bool)
    H, W = sea.shape
    maxc = max(1, int(round(fetch_max_m / cell)))
    if cells is None:
        cells = list(zip(*np.nonzero(shore_cells(sea))))
    out = {}
    for (j, i) in cells:
        acc = 0.0
        for k in range(ndirs):
            a = 2.0 * math.pi * (k + 0.5) / ndirs
            dx, dy = math.cos(a), math.sin(a)
            x, y = i + 0.5, j + 0.5                       # the cell centre in corner coordinates
            ci, cj = i, j
            sx, sy = (1 if dx > 0 else -1), (1 if dy > 0 else -1)
            tdx = abs(1.0 / dx) if abs(dx) > 1e-12 else math.inf
            tdy = abs(1.0 / dy) if abs(dy) > 1e-12 else math.inf
            tx = ((math.floor(x) + 1 - x) if dx > 0 else (x - math.floor(x))) * tdx if tdx < math.inf else math.inf
            ty = ((math.floor(y) + 1 - y) if dy > 0 else (y - math.floor(y))) * tdy if tdy < math.inf else math.inf
            f = float(maxc)
            while True:
                if tx < ty:
                    t, ci, tx = tx, ci + sx, tx + tdx
                else:
                    t, cj, ty = ty, cj + sy, ty + tdy
                if t > maxc:
                    break
                if not (0 <= ci < W and 0 <= cj < H):
                    break
                if not sea[cj, ci]:
                    f = max(t, 0.5)                       # the distance to where the ray enters the land cell
                    break
            acc += f
        out[(int(j), int(i))] = acc / (ndirs * maxc)
    return out


# ========================================================================================== world-space inputs ===

def _field(spec, level, seed, dev):
    """A world_noise field spec at the level's cells: on the GPU in production, numpy on the twins."""
    if dev is not None and dev.name == 'gpu':
        return N.field_gpu(spec, level, seed).astype(np.float64)
    x, y = level.xy()
    return np.asarray(N.field(spec, x, y, seed), np.float64)


def _unit_noise(scales, level, seed, dev, base_seed, min_cells=3.0, amps=None):
    """Noise of standard deviation 1 (fbm's 1/3, times 3): fbm at each scale the level resolves (min_cells cells and
    up), equal weights unless `amps` are given (relative amplitudes, normalised over ALL the scales, so a coarse
    level sees only the coarse share and every level the same values at the scales it resolves)."""
    sc = [float(s) for s in (scales or ())]
    amps = [1.0] * len(sc) if amps is None else [float(a) for a in amps]
    norm = math.sqrt(sum(a * a for a in amps)) or 1.0
    terms = [{'kind': 'fbm', 'wavelength_m': s, 'octaves': 2, 'seed': base_seed + i, 'amp': 3.0 * a / norm}
             for i, (s, a) in enumerate(zip(sc, amps)) if s >= min_cells * level.cell]
    if not terms:
        return np.zeros((level.n, level.n))
    return _field({'kind': 'sum', 'terms': terms}, level, seed, dev)


def _smoothstep(a, b, x):
    t = np.clip((np.asarray(x, np.float64) - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _centre(ctx, level):
    main = ctx.main if ctx is not None else None
    lv = main if main is not None else level
    return lv.x0 + lv.side / 2.0, lv.y0 + lv.side / 2.0


def _sea_vector(azimuth_deg):
    """The unit vector toward the sea, world (x east, y north), from the compass direction the coast faces."""
    a = math.radians(float(azimuth_deg))
    return math.sin(a), math.cos(a)


# ===================================================================================================== land ===

def shore_coordinate(level, P, seed, dev, centre):
    """s0: metres inland of the ORIGINAL coastline (negative offshore), a world function: a straight line facing
    azimuth_deg, offset_m + retreat_m seaward of the centre, bent into headlands and bays by wiggle_m of noise at
    wiggle_scale_m."""
    X, Y = level.xy()
    ux, uy = _sea_vector(P['azimuth_deg'])
    s = -((X - centre[0]) * ux + (Y - centre[1]) * uy) + float(P['offset_m']) + float(P['retreat_m'])
    if float(P['wiggle_m']) > 0:
        w = _field({'kind': 'fbm', 'wavelength_m': float(P['wiggle_scale_m']), 'octaves': 3, 'seed': 911,
                    'amp': 3.0}, level, seed, dev)
        s = s + float(P['wiggle_m']) * w
    return s


def land_shape(s0, P, tex=None):
    """The uplift and start shape (about 0..1) at s0 metres inland of the original coast: coast_frac at the coast,
    rising inland to 1 over rise_m (1 - (1 - c) e^(-s / rise)), then changing by inland_gain toward tilt_m inland
    (negative: a dip slope); seaward falling to 0 as c e^(s / L), L = c rise / (1 - c), which meets the inland side
    with the same slope (no crease along the old coast). Roughened by the texture."""
    s = np.asarray(s0, np.float64)
    c = float(np.clip(P['coast_frac'], 0.02, 0.98))
    rise = max(float(P['rise_m']), 1.0)
    inland = 1.0 - (1.0 - c) * np.exp(-np.maximum(s, 0.0) / rise)
    inland = inland * np.maximum(1.0 + float(P['inland_gain']) * np.clip(s / max(float(P['tilt_m']), 1.0), 0.0, 1.0),
                                 0.05)
    seaward = c * np.exp(np.minimum(s, 0.0) / (c * rise / (1.0 - c)))
    shape = np.where(s >= 0.0, inland, seaward)
    if tex is not None:
        shape = shape * np.maximum(1.0 + float(P['texture']) * tex, 0.1)
    return shape


def op_coast_land(fields, level, params, seed=0, ctx=None):
    """Stage 'coast_land' (module doc): U on the growing level, the start surface on a fresh one, and coast_s0 (metres
    inland of the original coastline, the coast stage's shore plan) on every pass."""
    ctx = ctx or FL.standalone_context(fields, level)
    dev = ctx.device or FL.device()
    P = params_for(params, LAND_DEFAULTS)
    s = int(seed) + int(P['seed'])
    centre = _centre(ctx, level)
    s0 = shore_coordinate(level, P, s, dev, centre)
    tex = _unit_noise(P['texture_scales_m'], level, s, dev, 1201)
    shape = land_shape(s0, P, tex)
    if ctx.role == 'grow' or ctx.fresh:
        fields['U'] = (float(P['U_m_per_yr']) * shape).astype(F32)
    if ctx.fresh:
        rough = _unit_noise(P['start_scales_m'], level, s, dev, 1301)
        h0 = np.maximum(float(P['start_m']) * shape * (1.0 + float(P['start_roughness']) * rough), 0.05)
        fields['h'] = h0.astype(F32)
        fields['bed'] = h0.astype(F32)
    fields['coast_s0'] = s0.astype(F32)
    return fields


# ===================================================================================================== cliffs ===

def column_table(column, base_m=0.0, z_lo=-60.0, z_hi=600.0, dz=0.25):
    """(zs, run): the horizontal run of a rock column's face, run(zs) = integral of dz / tan(angle(z)) from z_lo,
    tabulated every dz metres of stratigraphic height (the beds repeat from base_m up; below it the first bed)."""
    beds = COLUMNS[column] if isinstance(column, str) else [tuple(b) for b in column]
    th = np.array([b[0] for b in beds], np.float64)
    ang = np.array([b[1] for b in beds], np.float64)
    cyc = th.sum()
    edges = np.concatenate([[0.0], np.cumsum(th)])
    zs = np.arange(z_lo, z_hi + dz, dz)
    rel = np.mod(np.maximum(zs - base_m, 0.0), cyc)
    k = np.clip(np.searchsorted(edges, rel, side='right') - 1, 0, len(beds) - 1)
    inv_tan = 1.0 / np.tan(np.radians(ang[k]))
    run = np.concatenate([[0.0], np.cumsum(0.5 * (inv_tan[1:] + inv_tan[:-1]) * dz)])
    return zs, run


def face_profile(s, foot, theta_deg, column=None, col_off=None):
    """The face's height above sea level at s metres inland of its foot, the foot at `foot` metres: a single angle
    (theta_deg, per cell), or a column table (zs, run) offset by col_off (the dip: z = zs + off). Seaward of the foot
    (s < 0) the face continues down at its angle, under the platform."""
    s = np.asarray(s, np.float64)
    if column is None:
        return foot + s * np.tan(np.radians(theta_deg))
    zs_t, run_t = column
    off = 0.0 if col_off is None else col_off
    r0 = np.interp(foot - off, zs_t, run_t)
    z = np.interp(r0 + s, run_t, zs_t) + off
    # seaward of the foot the face goes straight down under the platform: the table's interpolation clamps at its
    # lowest bed (-60 m) and, where the beds' dip offset passed 60 m, held a flat shelf above the sea kilometres out
    return np.where(s < 0.0, foot + s * 10.0, z)


def beach_profile(y, P, amount):
    """The sand beach seaward of the cliff foot (y >= 0 metres): the dry backshore at the berm height out to the
    berm crest, the beach face down to the waterline, then the Dean profile -A y'^(2/3) (y' from the waterline).
    amount 0..1 scales the backshore's width and the berm (sheltered bays: 1)."""
    y = np.maximum(np.asarray(y, np.float64), 0.0)
    a = np.clip(amount, 0.0, 1.0)
    berm = float(P['beach_berm_m']) * a
    back = float(P['beach_backshore_m']) * a
    face = berm / math.tan(math.radians(float(P['beach_face_deg'])))
    yw = back + face                                   # the waterline
    z = np.where(y <= back, berm, berm - (y - back) * math.tan(math.radians(float(P['beach_face_deg']))))
    dean = -float(P['dean_A']) * np.power(np.maximum(y - yw, 0.0), 2.0 / 3.0)
    return np.where(y <= yw, z, dean)


def _max_filter(mask, r):
    """Binary dilation by a square of radius r cells (separable running max)."""
    m = np.asarray(mask, bool)
    if r <= 0:
        return m.copy()
    out = m.copy()
    for axis in (0, 1):
        acc = out.copy()
        for k in range(1, r + 1):
            a, _ = T.shift(out, k if axis == 1 else 0, k if axis == 0 else 0, T.BOUND_OPEN, False)
            b, _ = T.shift(out, -k if axis == 1 else 0, -k if axis == 0 else 0, T.BOUND_OPEN, False)
            acc |= a | b
        out = acc
    return out


def _connected(cut, sea0):
    """The cut cells that reach the original sea or the window edge through cut cells (8-connected): the rest is
    filled back (a weak patch behind a strong rib, which the sea cannot reach)."""
    from ..core.metrics import label
    lab, n = label(cut)
    if n == 0:
        return cut
    keep = np.zeros(n + 1, bool)
    keep[np.unique(lab[sea0 & cut])] = True
    edge = Gd.edge_distance(cut.shape) < 1
    keep[np.unique(lab[edge & cut])] = True
    keep[0] = False
    return keep[lab]


def sea_phi(land, sea_level):
    """The original shoreline of a surface as a level set (< 0 at sea): land - sea level, where only the sea that
    reaches the window's edge (or, when none does, the largest body) is sea; a hollow below sea level inland is
    land to the coast (the sea cannot get there; without this every such cell became a cut pit of its own)."""
    from ..core.metrics import label
    phi = np.asarray(land, np.float64) - sea_level
    wet = phi <= 0.0
    if wet.any():
        lab, n = label(wet)
        edge = Gd.edge_distance(wet.shape) < 1
        keep = np.zeros(n + 1, bool)
        keep[np.unique(lab[edge & wet])] = True
        keep[0] = False
        if not keep.any():
            counts = np.bincount(lab.ravel(), minlength=n + 1)
            counts[0] = 0
            keep[int(np.argmax(counts))] = True
        wet = keep[lab]
    return np.where(wet, np.minimum(phi, -1e-4), np.maximum(phi, 1e-4))


def plan_shore(dev, phi, cell, P, smooth_cells=None):
    """The shore plan of a level: (d0, E, info) - the signed distance (metres, + inland) of every cell to the
    original shoreline (the zero line of the level set phi, < 0 at sea: coast_land's s0, or sea_phi of a surface;
    sub-cell), and the exposure of the nearest shore, smoothed along the shore by exposure_smooth_m."""
    phi = np.asarray(phi, np.float64)
    sea = phi < 0.0
    phi = np.where(sea, np.minimum(phi, -1e-4), np.maximum(phi, 1e-4))
    if not sea.any() or sea.all():
        far = -1e7 if sea.all() else 1e7
        return np.full(phi.shape, far, F32), np.full(phi.shape, E_REF, F32), dict(shore_cells=0)
    E_shore = exposure(dev, sea, cell, float(P['fetch_max_m']), int(P['fetch_dirs']))
    pay = np.where(E_shore >= 0, E_shore, E_REF)
    d, E = nearest_crossing(dev, phi, pay)
    d0 = np.where(sea, -d, d) * cell
    sm = float(P['exposure_smooth_m']) / cell if smooth_cells is None else smooth_cells
    if sm > 0.5:
        from .hillslope import gaussian_blur
        E = gaussian_blur(E, sm)
    vals = E_shore[E_shore >= 0]
    info = dict(shore_cells=int(vals.size), exposure_p10=float(np.percentile(vals, 10)) if vals.size else None,
                exposure_p50=float(np.percentile(vals, 50)) if vals.size else None,
                exposure_p90=float(np.percentile(vals, 90)) if vals.size else None)
    return d0.astype(F32), E.astype(F32), info


def stack_weight(level, P, seed, dev):
    """0..1: the strong knobs (ridged world noise at stack_scale_m) that stand as stacks when the retreat passes
    both sides of them; 0 everywhere when stacks is 0."""
    if float(P['stacks']) <= 0:
        return np.zeros((level.n, level.n))
    k = _field({'kind': 'ridged', 'wavelength_m': float(P['stack_scale_m']), 'octaves': 2, 'seed': 1451},
               level, seed, dev)
    return float(P['stacks']) * _smoothstep(0.55, 0.8, k)


def retreat_field(E, level, P, seed, dev, stack_w=None):
    """R (metres): retreat_m x the exposure factor x the rock weakness, plus the crenellation."""
    f = np.clip((np.asarray(E, np.float64) / E_REF), 1e-3, None) ** float(P['exposure_power'])
    f = np.clip(f, *P['exposure_clamp'])
    w = np.ones_like(f)
    if float(P['weakness']) > 0:
        w = np.exp(float(P['weakness']) * _unit_noise(P['weakness_scales_m'], level, seed, dev, 1401))
    R = float(P['retreat_m']) * f * w
    if stack_w is None:
        stack_w = stack_weight(level, P, seed, dev)
    R = R * (1.0 - 0.85 * stack_w)
    if float(P['crenel_m']) > 0:
        R = R + float(P['crenel_m']) * _unit_noise(P['crenel_scales_m'], level, seed, dev, 1501)
    return R


def _band_weight(level):
    """A child's border band (run.py child_pins): 1 on the outer 2 cells, easing to 0 at `band` cells in."""
    d = Gd.edge_distance(level.n).astype(np.float64)
    t = np.clip((d - 2.0) / float(max(level.band - 2, 1)), 0.0, 1.0)
    return 1.0 - t * t * (3.0 - 2.0 * t)


CHILD_ZONE = 6                  # child cells (3 parent cells): the Catmull-Rom stencil reaches 2 parent cells


def _child_land(fields, level):
    """The uncut land on a child level, and the weight of the zone near the parent's cut: there the parent's land
    (coast_land, bilinear: the land is smooth, the error is centimetres), beyond it the parent's surface (h,
    Catmull-Rom: exactly the land wherever the parent cut nothing within the stencil), blended over 3 cells."""
    h_cr = np.asarray(fields['h'], np.float64)
    if 'coast_land' not in fields:
        return h_cr, np.zeros_like(h_cr)
    land_bl = np.asarray(fields['coast_land'], np.float64)
    cut = np.asarray(fields['coast_cut'], np.float64) > 1e-3 if 'coast_cut' in fields else np.zeros(h_cr.shape, bool)
    ring = _max_filter(cut, CHILD_ZONE)
    w = ring.astype(np.float64)
    for v in (0.75, 0.5, 0.25):           # 1 inside the zone, then 0.75 / 0.5 / 0.25 on the next three rings
        nxt = _max_filter(ring, 1)
        w = np.where(nxt & ~ring, v, w)
        ring = nxt
    return w * land_bl + (1.0 - w) * h_cr, w


def op_coast(fields, level, params, seed=0, ctx=None):
    """Stage 'coast' (module doc)."""
    ctx = ctx or FL.standalone_context(fields, level)
    if ctx.prepass is not None:
        return fields                            # the coarsest level's coarse-to-fine passes: the land still grows
    t0 = time.perf_counter()
    dev = ctx.device or FL.device()
    P = params_for(params)
    s = int(seed) + int(P['seed'])
    sea_level = float(P['sea_level'] if P['sea_level'] is not None else
                      (ctx.sea_level if ctx.sea_level is not None else 0.0))
    lv = level
    n, cell = lv.n, float(lv.cell)
    if 'h' not in fields:
        raise ValueError(f"stage 'coast' on {lv}: no height yet (the land comes first: 'coast_land' + 'fluvial', "
                         f"a DEM, or any start)")
    child = 'coast_d0' in fields
    info = {}
    if child:
        land, zone = _child_land(fields, lv)
        d0 = np.asarray(fields['coast_d0'], np.float64)
        E = np.asarray(fields['coast_E'], np.float64)
    else:
        land = np.asarray(fields['h'], np.float64)
        # the original shoreline: coast_land's (the land was carved to a base level far out, so its own sea-level
        # contour is not the coast the sea attacked), else the surface's sea level line; either way only the sea
        # that reaches the window's edge (the bent coastline closed off a patch of 'sea' inland once, and the sea
        # cut a ring-walled hole there)
        phi0 = (sea_phi(np.asarray(fields['coast_s0'], np.float64), 0.0) if 'coast_s0' in fields
                else sea_phi(land, sea_level))
        d0, E, info = plan_shore(dev, phi0, cell, P)
        d0 = d0.astype(np.float64)
        E = E.astype(np.float64)
    bed_in = np.asarray(fields['bed'], np.float64) if 'bed' in fields else land.copy()
    H = land - sea_level

    # the retreat and the cliff foot line
    stack_w = stack_weight(lv, P, s, dev)
    R = retreat_field(E, lv, P, s, dev, stack_w)
    phi = d0 - R
    cut = phi < 0.0
    if P['connect']:
        cut = _connected(cut, d0 < 0.0)
    phi = np.where(cut, np.minimum(phi, -1e-3), np.maximum(phi, 1e-3))
    # the face angle belongs to the cliff line: evaluated per cell it changed across one face (with a wide spread,
    # 88 degrees on a cell and 30 a cell inland made the profile fall inland: pits on the face), so every cell takes
    # the angle at its nearest point of the foot line, carried by the jump flood. (Clamped below 90 degrees: a value
    # past it turned tan negative and the face into a pit kilometres inland.)
    theta = np.clip(float(P['face_deg']) + float(P['face_spread_deg']) * _unit_noise([P['face_scale_m']], lv, s, dev,
                                                                                        1601), 30.0, 88.5)
    # stacks: land the cut has detached from the mainland (and a few cells of sea around it, where its foot line
    # lies) take the knob's near-vertical wall; a strong knob still joined to a headland keeps the coast's face
    sw = np.zeros(theta.shape)
    if float(P['stacks']) > 0 and cut.any():
        from ..core.metrics import label
        lab, nlab = label(~cut)
        if nlab > 1:
            counts = np.bincount(lab.ravel(), minlength=nlab + 1)
            counts[0] = 0
            detached = (lab > 0) & (lab != int(np.argmax(counts)))
            if detached.any():
                sw = _max_filter(detached, 3).astype(np.float64)
    theta = theta + (float(P['stack_face_deg']) - theta) * sw
    if cut.any() and (~cut).any():
        dist, theta_foot = nearest_crossing(dev, phi, theta)
        sd = np.where(cut, -dist, dist) * cell                       # metres from the cliff foot, + inland
        theta = np.where(np.isfinite(dist), theta_foot, theta)
    else:
        sd = np.where(cut, -1e7, 1e7)
    sd = np.where(np.isfinite(sd), sd, np.where(cut, -1e7, 1e7))

    # the face
    talus_n = np.clip(1.0 + 0.45 * _unit_noise([180.0, 60.0], lv, s, dev, 1651), 0.3, 1.7)
    t_h = np.clip(float(P['talus_frac']) * np.maximum(H, 0.0) * talus_n, 0.0, float(P['talus_max_m']))
    col = None
    col_off = None
    if P['column'] is not None:
        col = column_table(P['column'], float(P['column_base_m']))
        X, Y = lv.xy()
        dip = math.tan(math.radians(float(P['column_dip_deg'])))
        dx_, dy_ = _sea_vector(P['column_dip_azimuth_deg'])
        col_off = -dip * (X * dx_ + Y * dy_)                         # the beds fall toward the dip azimuth
    foot = sea_level + float(P['platform_top_m']) + t_h
    face = face_profile(sd, foot - sea_level, theta, col, col_off) + sea_level
    if col is not None and sw.any():
        # under a strong knob the bedded face gives way to the knob's own near-vertical wall
        face = face + sw * (face_profile(sd, foot - sea_level, theta) + sea_level - face)

    # erosion: the land above the face and the wave-cut platform is cut away, the cliff top rounded
    y = np.maximum(-sd, 0.0)
    rough = float(P['platform_rough_m']) * _unit_noise([20.0, 6.0], lv, s, dev, 1701, min_cells=2.0)
    platform = sea_level + float(P['platform_top_m']) - y * math.tan(math.radians(float(P['platform_slope_deg'])))
    platform = C.smooth_max(platform, sea_level - float(P['sea_floor_m']), 4.0) + rough
    k = float(P['top_round_m'])
    cut_prof = np.maximum(face, platform)
    rock = C.smooth_min(land, cut_prof, k) if k > 0 else np.minimum(land, cut_prof)
    rock = np.minimum(rock, land)
    # deposition at the foot: the talus apron (35 degrees from the apron's top against the face), the shingle toe
    # of an exposed cliff, and in sheltered bays sand up to the beach profile (berm, face, Dean), over the cut
    # platform or the old sea floor alike. Landward of the foot each falls at the repose angle into what is there
    tan_r = math.tan(math.radians(float(P['talus_deg'])))
    back = np.maximum(sd, 0.0) * tan_r
    apron = foot - y * tan_r - back
    beach_amt = 1.0 - _smoothstep(P['beach_exposure'][0], P['beach_exposure'][1], E)
    exposed = 1.0 - beach_amt
    wsh = max(float(P['shingle_w_m']), 1e-3)
    sh_t = exposed * float(P['shingle_m']) * (1.0 - (y / wsh) ** 2)       # its thickness above sea level
    shingle = np.where(sh_t > 0.0, sea_level + sh_t - back, -np.inf)        # none beyond its width or in a bay
    beach = sea_level + beach_profile(y, P, np.ones_like(y)) - back
    h = np.maximum(rock, np.maximum(apron, shingle))
    h = h + beach_amt * np.maximum(beach - h, 0.0)
    changed = np.abs(land - h) > 1e-3
    apron_part = np.where(changed, np.maximum(np.minimum(h, apron) - rock, 0.0), 0.0)
    deposit_add = np.where(changed, np.maximum(h - rock - apron_part, 0.0), 0.0)
    wear_add = np.where(changed, np.maximum(land - rock, 0.0), 0.0)

    # band: a child's outer cells blend to its parent's surface
    if child and ctx.pins is not None and lv.parent is not None:
        w = _band_weight(lv)
        ph = np.asarray(ctx.pins['pin_h'], np.float64)
        h = h * (1.0 - w) + ph * w

    # write. Near the parent's cut a child's inherited layers are the parent's, smeared across the cliff by the
    # upsampling: there this level's own coast layers replace them (the land at the cliff top is turf)
    near = (zone > 0.5) if child else np.zeros(h.shape, bool)
    fields['h'] = h.astype(F32)
    bed = np.where(changed, rock, np.where(near, h, bed_in))
    fields['bed'] = np.minimum(bed, h).astype(F32)
    for name, add in (('wear', wear_add), ('talus', apron_part), ('deposit', deposit_add)):
        base = np.asarray(fields[name], np.float64) if name in fields else np.zeros_like(h)
        base = np.where(near, 0.0, base)
        if name == 'wear':
            new = np.where(changed, base + add, base)
        else:
            new = np.where(changed, add, base)
        fields[name] = np.maximum(new, 0.0).astype(F32)
    sc_face = np.tan(np.radians(np.clip(theta, 30.0, 89.0)))
    sc = np.where(changed & (sd >= 0.0), sc_face, math.tan(math.radians(float(P['talus_deg']))))
    if 'Sc' in fields and not child:
        sc = np.where(changed, sc, np.asarray(fields['Sc'], np.float64))
    fields['Sc'] = sc.astype(F32)
    fields['coast_d0'] = d0.astype(F32)
    fields['coast_E'] = E.astype(F32)
    fields['coast_land'] = land.astype(F32)
    fields['coast_cut'] = np.maximum(land - h, 0.0).astype(F32)
    if P['column'] is not None:
        X, Y = lv.xy()
        fields['zs'] = (np.asarray(fields['h'], np.float64) - (col_off if col_off is not None else 0.0)).astype(F32)
    rec = dict(level=str(lv), plan=not child, cut_frac=round(float(cut.mean()), 4),
               retreat_p10_p50_p90=[round(float(v), 1) for v in np.percentile(R[np.abs(phi) < 3 * cell + 50], [10, 50, 90])]
               if (np.abs(phi) < 3 * cell + 50).any() else None, seconds=round(time.perf_counter() - t0, 3), **info)
    ctx.shared.setdefault('coast_log', []).append(rec)
    ctx.log(f"[terrain.coast] {lv.n}^2 @ {cell:.3g} m: {'shore plan + ' if not child else ''}cut {rec['cut_frac']:.1%}"
            + (f", retreat p10/50/90 {rec['retreat_p10_p50_p90']} m" if rec['retreat_p10_p50_p90'] else '')
            + (f", exposure p10/50/90 {info.get('exposure_p10', 0):.2f}/{info.get('exposure_p50', 0):.2f}/"
               f"{info.get('exposure_p90', 0):.2f}" if info.get('exposure_p50') is not None else '')
            + f", {rec['seconds']} s")
    return fields


op_coast_land.evolves = True       # run.py: U on every coarse-to-fine pass of the coarsest level
op_coast.evolves = True            # run.py runs it on the coarsest level's last pass too (it skips the pre-passes)
OPS = {'coast_land': op_coast_land, 'coast': op_coast}

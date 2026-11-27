"""eidoblend.sets.desert.land: the land round a town, composed. Plain Python (numpy, scipy, Pillow; no Blender):

    python blender/eidoblend/sets/desert/land.py --work work/desert [--grid film|draft]

Everything is in the TOWN'S OWN METRES (+x along its main road, the town about x -650..650, y -350..350 with its edge
for a town of 840 x 300 m, its ground a plane at z 0 that runs to 1600 m every way). What the land is made of:

  THE FLOOR      under the town's plane wherever the town has anything on the ground (its footprint, sources/
                 town_mask.npz, closed and grown 6 m), it rises through z 0 within 25 m of it, then 1 % and easing
                 (the town lies in the floor of a broad basin), up a pediment toward the escarpment (+y)
  THE WADIS      a braided main wadi along -y (bed 75-165 m wide, 1.9 m deep, bars in its bed) and three tributaries
                 that come down from the escarpment round the town's ends
  THE DUNES      the terrain family's simulated star dunes (sources/dunes_*: Werner transport, slip faces), scaled
                 0.36 as a whole (slopes kept) into a field on the -y side, 1.8-7 km out; its edge sinks the dunes into
                 the floor so only crests stand at its margin: the few small dunes nearer in
  THE ESCARPMENT the simulated mesas and buttes (sources/mesas_*: caprock retreat over talus), scaled 0.8, turned so
                 its plateau edge faces the town from +y, 2.5-3.5 km out, its outliers in front
  THE RANGES     the simulated fluvial range (sources/range_*: stream power, threshold slopes) DROWNED in its own
                 alluvium: only what stands above a fill level shows, so ranges and inselbergs rise abruptly from the
                 floor with drowned valleys as embayments; four inselberg groups at 3-8 km (the range's own peaks
                 scaled 0.4-0.45 as a whole), the ranges beyond 7 km, higher with distance and by direction
  THE APRONS     bajadas fanned from every range front (the blurred mass of what stands above the floor)
  THE TRACKS     going on from the town's own track ends (the plan's for its default town, else drawn from the mask)
  THE EARTH      its curvature (25 km: 49 m down)

Kept as three nested rasters centred on the town (build/land_A.npz: +-2048 m at 1 m; B: +-8192 at 4 m; C: +-32768 at
16 m; --grid draft: 4, 16 and 64 m), each the height and the masks the materials read (town distance, sand, wadi bed,
bars, escarpment, range, apron), and two images of what is finer than the mesh (build/near_marks.png, mid_marks.png:
tracks, beds and bars, the sand sheet). mesh.py makes the mesh from them; look.py the Blender collection. Where each
thing stands is PLAN (a dict: pass your own to Land(plan=...) to move the dunes, the escarpment, the inselbergs ...).
"""
import json
import math
import os
import sys
import time

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

EARTH_R = 6371000.0
GRIDS = {'film': (('A', 2048.0, 1.0), ('B', 8192.0, 4.0), ('C', 32768.0, 16.0)),
         'draft': (('A', 2048.0, 4.0), ('B', 8192.0, 16.0), ('C', 32768.0, 64.0))}
FIELDS = ('h', 'town', 'sand', 'sheet', 'bed', 'bar', 'esc', 'mtn', 'apron')

# ------------------------------------------------------------------------------------------------- where things are
DUNE = dict(c=(0.0, -4000.0), rot=20.0, scale=0.36, a=4400.0, b=2650.0)         # the dune field, -y (its crests to the wadi's bank)
# the escarpment: the source's east turned to the town's +y, scaled 0.8 as a whole (a wall of about 200 m at 2-3 km)
ESC = dict(c=(-2000.0, 2400.0), rot=90.0, scale=0.8)
# THE FLOOR'S DRAINAGE LINES: the fluvial range's own simulated network (its drainage area 'A' on its two finest
# levels), scaled 0.6 as a whole, turned 30 deg: a line every 150-250 m where sheet floods run, incised up to half a
# metre, finer silt and scrub along it; and the same network's ridges and hollows (its height above a 140 m mean) at
# 1 %: a dissected alluvial surface of low swells, its rills in the hollows
RILL = dict(scale=0.6, rot=30.0, off=(1800.0, -900.0), lo=4.25, hi=5.4, depth=0.5, relief=0.010, relief_cap=2.4)
DUNE_SHARP = dict(sigma=9.0, k=1.1)      # the scaled dunes' crests sharpened by an unsharp mask of 9 m, their brinks with them
RANGE = dict(rot=25.0, vscale=0.72)
# the ranges by direction (azimuth from +x toward +y, degrees; how much lower the fill lies there, m; spread, degrees):
# strongest toward -x and behind the plateau's east end, a range past the dunes, gaps between
SECTORS = ((180.0, 700.0, 38.0), (40.0, 520.0, 30.0), (232.0, 480.0, 24.0), (282.0, 330.0, 20.0), (342.0, 420.0, 20.0), (130.0, 300.0, 22.0))
# inselberg groups: town centre, source centre (windows of the range's main level), scale, turn (deg), metres of the
# source peak that stand above its fill, radius of the group (town m)
INSEL = (((5200.0, 600.0), (-4729.0, -205.0), 0.45, 30.0, 760.0, 1500.0),
         ((-5600.0, -2500.0), (-2232.0, -311.0), 0.45, -40.0, 700.0, 1300.0),
         ((-3300.0, 2500.0), (-146.0, -3486.0), 0.40, 75.0, 520.0, 950.0),
         ((3900.0, -2900.0), (-5115.0, -2713.0), 0.40, 10.0, 460.0, 900.0))
# the main wadi's line, and the tributaries (town m; smoothed and given their sinuosity below): points, half width, depth
TRIB = (([(2300, 2350), (2000, 1700), (1650, 1100), (1250, 550), (1120, 0), (1220, -520), (1560, -880)], 21.0, 1.4),
        ([(-2600, 2300), (-2150, 1650), (-1700, 1150), (-1300, 600), (-1180, 20), (-1330, -560), (-1760, -900)], 24.0, 1.5),
        ([(5400, 2300), (4500, 1300), (3700, 200), (3200, -600), (2900, -930)], 18.0, 1.2))
# THE TRACKS of the default town (eidoblend.sets.town at 840 x 300 m, seed 7): each starts where one of the town's own
# tracks stops (sources/town_mask.npz 'tracks'), runs out and fades; points, strength. Another town's are drawn from
# its own track ends (auto_tracks)
TRACKS = (([(547, -14), (900, -22), (1400, -60), (2200, -118), (3200, -96), (4300, -30), (6000, 150), (9000, 420), (13000, 700)], 1.0),
          ([(-589, -14), (-1000, -8), (-1700, 30), (-2600, 125), (-3800, 98), (-5500, -150), (-9000, -420), (-13000, -650)], 1.0),
          ([(50, -313), (62, -520), (92, -800), (130, -1150), (300, -1700), (700, -2300), (900, -2700)], 0.85),
          ([(-243, -296), (-300, -600), (-500, -1000), (-900, -1400), (-1600, -1800), (-2200, -2100)], 0.7),
          ([(390, -286), (450, -600), (700, -950), (1100, -1300), (1900, -1600), (2600, -1750)], 0.6),
          ([(174, 308), (200, 600), (300, 1100), (500, 1700), (700, 2200), (680, 2500)], 0.8),
          ([(-420, 298), (-500, 650), (-750, 1100), (-1200, 1700), (-1500, 2250)], 0.65),
          ([(316, 246), (400, 500), (800, 800), (1500, 1100), (2600, 1400), (3800, 1650), (5000, 1700)], 0.7),
          ([(2200, -118), (2500, -600), (2900, -1200), (3200, -1700)], 0.55),
          ([(-1700, 30), (-2000, 600), (-2600, 1400), (-3100, 1900)], 0.55),
          ([(583, -146), (800, -260), (1000, -430), (1150, -600)], 0.45),
          ([(-594, -146), (-800, -300), (-1000, -520)], 0.45),
          ([(606, 118), (850, 210), (1100, 340), (1300, 520)], 0.45),
          ([(-593, 118), (-850, 230), (-1050, 420)], 0.4),
          ([(-25, 244), (-40, 520), (-120, 900), (-260, 1300)], 0.5),
          ([(-245, -296), (-180, -600)], 0.4),
          ([(-611, -58), (-900, -120), (-1300, -260), (-1900, -420), (-2600, -560)], 0.6),
          ([(563, 74), (900, 120), (1500, 230), (2100, 380)], 0.5))
PLAN = dict(dune=DUNE, esc=ESC, rill=RILL, dune_sharp=DUNE_SHARP, range=RANGE, sectors=SECTORS, insel=INSEL, trib=TRIB,
            tracks=TRACKS)


def ss(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# ------------------------------------------------------------------------------------------------- the sources
def load_stack(src, name):
    """every level of one source (sources.simulate's <name>_L<i>.npz), coarsest first"""
    out = []
    i = 0
    while os.path.isfile(os.path.join(src, f'{name}_L{i}.npz')):
        z = np.load(os.path.join(src, f'{name}_L{i}.npz'))
        L = dict(x0=float(z['x0']), y0=float(z['y0']), cell=float(z['cell']), n=int(z['n']))
        L.update({k: z[k] for k in z.files if k not in ('x0', 'y0', 'side', 'cell', 'n')})
        out.append(L)
        i += 1
    if not out:
        raise FileNotFoundError(f'[desert] no {name}_L0.npz in {src}: run the sources step first (cli.py sources)')
    return out


def auto_tracks(town_tracks, seed=31, cx=0.0, cy=0.0):
    """tracks going on from a town's own track ends: from each track quad's outer end, straight on with a few bends
    (seeded), 2.5-13 km for the tracks along the town's long axis, 0.6-3 km for the rest; strength by its width"""
    rng = np.random.default_rng(seed)
    out = []
    for axis, x0, x1, y0, y1 in np.asarray(town_tracks, np.float64).reshape(-1, 5):
        if axis == 0:
            ex = x1 if abs(x1 - cx) > abs(x0 - cx) else x0
            p, d = np.array([ex, (y0 + y1) / 2.0]), np.array([math.copysign(1.0, ex - cx), 0.0])
            w = y1 - y0
        else:
            ey = y1 if abs(y1 - cy) > abs(y0 - cy) else y0
            p, d = np.array([(x0 + x1) / 2.0, ey]), np.array([0.0, math.copysign(1.0, ey - cy)])
            w = x1 - x0
        long_ = axis == 0
        length = rng.uniform(2500.0, 13000.0) if long_ and w > 4.5 else rng.uniform(600.0, 3000.0)
        pts, s = [tuple(p)], 0.0
        while s < length:
            step = rng.uniform(300.0, 1400.0) * (1.0 if s > 400.0 else 0.4)
            a = rng.uniform(-0.35, 0.35)
            d = np.array([d[0] * math.cos(a) - d[1] * math.sin(a), d[0] * math.sin(a) + d[1] * math.cos(a)])
            p = p + d * step
            pts.append(tuple(p))
            s += step
        out.append((pts, float(np.clip(0.3 + w / 10.0, 0.4, 1.0))))
    return tuple(out)


def plan_tracks(plan_tracks, town_tracks, tol=60.0):
    """the plan's tracks when every one that starts at the town starts within tol m of one of its track ends (the
    plan's were drawn by eye from the default town's), else None"""
    ends = []
    for axis, x0, x1, y0, y1 in np.asarray(town_tracks, np.float64).reshape(-1, 5):
        if axis == 0:
            ends += [(x0, (y0 + y1) / 2.0), (x1, (y0 + y1) / 2.0)]
        else:
            ends += [((x0 + x1) / 2.0, y0), ((x0 + x1) / 2.0, y1)]
    if not ends:
        return None
    ends = np.array(ends)
    for pts, _ in plan_tracks:
        x, y = pts[0]
        if math.hypot(x, y) < 1000.0 and np.hypot(ends[:, 0] - x, ends[:, 1] - y).min() > tol:
            return None
    return plan_tracks


def sample_stack(stack, field, u, v):
    """bilinear samples of a level stack at source points (u, v): the finest level holding each point, blended into its
    parent over its outer 24 cells (a finer level's border is pinned to its parent: the blend only hides rounding)"""
    out = np.zeros(u.shape, np.float32)
    first = True
    for L in stack:                                                  # coarsest first
        fi = (u - L['x0']) / L['cell'] - 0.5
        fj = (v - L['y0']) / L['cell'] - 0.5
        n = L['n']
        inside = np.minimum(np.minimum(fi, n - 1 - fi), np.minimum(fj, n - 1 - fj))
        w = np.ones(u.shape, np.float32) if first else np.clip((inside - 4.0) / 20.0, 0.0, 1.0).astype(np.float32)
        sel = w > 0
        if sel.any():
            s = ndi.map_coordinates(L[field], [fj[sel], fi[sel]], order=1, mode='nearest').astype(np.float32)
            out[sel] = out[sel] + (s - out[sel]) * w[sel]
        first = False
    return out


def turn(dx, dy, deg):
    """town offset -> source offset: turned by -deg"""
    a = math.radians(-deg)
    return math.cos(a) * dx - math.sin(a) * dy, math.sin(a) * dx + math.cos(a) * dy


# ------------------------------------------------------------------------------------------------- lines
def chaikin(pts, k=3):
    p = np.asarray(pts, np.float64)
    for _ in range(k):
        q = 0.75 * p[:-1] + 0.25 * p[1:]
        r = 0.25 * p[:-1] + 0.75 * p[1:]
        p = np.vstack([p[:1], np.column_stack([q, r]).reshape(-1, 2), p[-1:]])
    return p


def sinuous(p, amp, wave, seed, step=8.0):
    """resampled every `step` m along its length and given a meander of its own (two waves, a seeded phase)"""
    seg = np.hypot(*np.diff(p, axis=0).T)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    t = np.arange(0.0, s[-1], step)
    x, y = np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])
    dx, dy = np.gradient(x), np.gradient(y)
    ln = np.maximum(np.hypot(dx, dy), 1e-6)
    nx, ny = -dy / ln, dx / ln
    rng = np.random.default_rng(seed)
    ph1, ph2, ph3 = rng.uniform(0, 6.283, 3)
    # (one long bend, a shorter one at a third of its size, a small one at a sixth, at wavelengths that never line up:
    #  never a zigzag in plan)
    off = amp * (np.sin(2 * np.pi * t / wave + ph1) + 0.35 * np.sin(2 * np.pi * t / (wave * 0.43) + ph2) + 0.15 * np.sin(2 * np.pi * t / (wave * 0.17) + ph3))
    off *= ss(0.0, 60.0, t) * ss(0.0, 60.0, t[-1] - t)               # (its ends where they were put)
    return np.column_stack([x + nx * off, y + ny * off])


def main_wadi_line():
    xs = np.arange(-16000.0, 16001.0, 10.0)
    # (three bends that never line up, and a slow drift: no regular wave in plan)
    yc = (-930 + 62 * np.sin(2 * np.pi * xs / 3700 + 0.7) + 30 * np.sin(2 * np.pi * xs / 1630 + 2.1) + 13 * np.sin(2 * np.pi * xs / 770 + 4.0)
          - 0.035 * np.maximum(np.abs(xs) - 3500, 0))
    half = 0.5 * (115 + 35 * np.sin(2 * np.pi * xs / 2300 + 0.3) + 18 * np.sin(2 * np.pi * xs / 870 + 1.3))
    return np.column_stack([xs, yc]), half


class Grid:
    def __init__(self, half, cell):
        self.half, self.cell = half, cell
        self.n = int(round(2 * half / cell))
        self.x0 = self.y0 = -half
        c = (np.arange(self.n, dtype=np.float32) + 0.5) * cell - half
        self.X, self.Y = np.meshgrid(c, c)                            # [j, i]: y rows (south first), x columns

    def draw(self, lines, values=None, width_px=1):
        """polylines into a raster (0 none), each drawn with its value (1..255), for distance transforms"""
        im = Image.new('L', (self.n, self.n), 0)
        d = ImageDraw.Draw(im)
        for k, p in enumerate(lines):
            px = [((x - self.x0) / self.cell, (y - self.y0) / self.cell) for x, y in p]
            d.line(px, fill=int(values[k] if values is not None else 255), width=width_px)
        return np.asarray(im)                                         # row 0 is y0 (the image is not flipped)

    def dist(self, lines, values=None):
        """distance (m) from every cell to the nearest line, and that line's value there"""
        img = self.draw(lines, values)
        if not img.any():
            return np.full((self.n, self.n), 1e9, np.float32), np.zeros((self.n, self.n), np.uint8)
        d, idx = ndi.distance_transform_edt(img == 0, return_indices=True)
        return (d * self.cell).astype(np.float32), img[idx[0], idx[1]]


# ------------------------------------------------------------------------------------------------- the town
def town_distance(src):
    """distance (m) from the town's region (its footprint closed and grown 6 m) on a 2 m raster +-4096 m; its tracks"""
    p = os.path.join(src, 'town_mask.npz')
    if not os.path.isfile(p):
        raise FileNotFoundError(f'[desert] no town_mask.npz in {src}: run the mask step first (cli.py mask)')
    z = np.load(p)
    occ = z['occ'].astype(bool)
    cell = float(z['cell'])
    big = np.zeros((4096, 4096), bool)
    oy, ox = int((float(z['y0']) + 4096) / cell), int((float(z['x0']) + 4096) / cell)
    big[oy:oy + occ.shape[0], ox:ox + occ.shape[1]] = occ
    dil = ndi.distance_transform_edt(~big) * cell <= 24.0
    closed = ndi.distance_transform_edt(dil) * cell > 18.0
    region = ndi.distance_transform_edt(~closed) * cell <= 6.0
    return (ndi.distance_transform_edt(~region) * cell).astype(np.float32), z['tracks']


def town_dist_at(D, X, Y):
    fi, fj = (X + 4096.0) / 2.0 - 0.5, (Y + 4096.0) / 2.0 - 0.5
    inside = (fi > 1) & (fi < 4094) & (fj > 1) & (fj < 4094)
    out = np.empty(X.shape, np.float32)
    out[inside] = ndi.map_coordinates(D, [fj[inside], fi[inside]], order=1)
    ex = np.maximum(np.abs(X[~inside]) - 650.0, 0.0)
    ey = np.maximum(np.abs(Y[~inside]) - 360.0, 0.0)
    out[~inside] = np.hypot(ex, ey)
    return out


# ------------------------------------------------------------------------------------------------- the land
class Land:
    def __init__(self, work, plan=None, log=print):
        """work: the chain's folder (sources/ in, build/ out); plan: PLAN's entries to replace"""
        t0 = time.time()
        self.P = dict(PLAN, **(plan or {}))
        src = os.path.join(work, 'sources')
        self.S = dict(dunes=load_stack(src, 'dunes'), mesas=load_stack(src, 'mesas'), range=load_stack(src, 'range'))
        for L in self.S['range'][-2:]:                                 # the range's height above its 140 m mean (RILL relief)
            L['hp'] = (L['h'] - ndi.gaussian_filter(L['h'], 140.0 / L['cell'])).astype(np.float32)
        self.D, self.town_tracks = town_distance(src)
        self.wadi_p, self.wadi_half = main_wadi_line()
        self.tribs = [(sinuous(chaikin(p), 38.0, 1100.0, 11 + k), half, depth) for k, (p, half, depth) in enumerate(self.P['trib'])]
        trk = plan_tracks(self.P['tracks'], self.town_tracks) or auto_tracks(self.town_tracks)
        self.track_source = 'plan' if trk is self.P['tracks'] else 'drawn from the town\'s track ends'
        # (a track is driven straight between its bends: a small wander, a long wave)
        self.tracks = [(sinuous(chaikin(p, 2), 3.5, 1500.0, 31 + k, step=4.0), s) for k, (p, s) in enumerate(trk)]
        rng = np.random.default_rng(5)
        self.bars = []                                               # (x, y, half length, half width, height, angle)
        p, half = self.wadi_p, self.wadi_half
        ang = np.arctan2(np.gradient(p[:, 1]), np.gradient(p[:, 0]))
        k = 0
        while k < len(p) - 1:
            for _ in range(rng.integers(1, 3)):
                off = rng.uniform(-0.62, 0.62) * half[k]
                L, W = rng.uniform(35, 105), rng.uniform(7, 20)
                self.bars.append((p[k, 0] - math.sin(ang[k]) * off, p[k, 1] + math.cos(ang[k]) * off, L, min(W, half[k] * 0.4), rng.uniform(0.35, 0.85), ang[k] + rng.uniform(-0.18, 0.18)))
            k += int(rng.integers(9, 17))                            # every 90-170 m
        for q, h_, d_ in self.tribs:
            a = np.arctan2(np.gradient(q[:, 1]), np.gradient(q[:, 0]))
            for k in range(0, len(q), int(rng.integers(14, 24))):
                off = rng.uniform(-0.45, 0.45) * h_
                self.bars.append((q[k, 0] - math.sin(a[k]) * off, q[k, 1] + math.cos(a[k]) * off, rng.uniform(18, 45), rng.uniform(3, 7), rng.uniform(0.25, 0.5), a[k]))
        # the inselbergs' source peaks: the highest point of each window
        R = self.S['range']
        self.insel_peak = []
        for (_, sc, s, rot, emerge, rad) in self.P['insel']:
            g = np.linspace(-rad / s, rad / s, 121)
            uu, vv = np.meshgrid(g + sc[0], g + sc[1])
            self.insel_peak.append(float(sample_stack(R, 'h', uu, vv).max()))
        log(f'[desert] land sources in {time.time() - t0:.1f} s; {len(self.bars)} bars; {len(self.tracks)} tracks ({self.track_source}); '
            f'inselberg peaks {[round(v) for v in self.insel_peak]}')

    # ---- the parts, each on a grid
    def floor(self, X, Y, D):
        d = np.maximum(D - 40.0, 0.0)
        base = -0.5 + 0.9 * ss(0.0, 40.0, D)
        rise = 9.0 * (1.0 - np.exp(-d / 900.0)) + 0.0025 * d
        ped = 9.0 * ss(500.0, 3200.0, Y) * ss(0.0, 200.0, D)
        swell = 2.2 * np.sin(X / 2300.0 + 0.4) * np.sin(Y / 1900.0 + 1.1) * ss(200.0, 1500.0, D)
        swale = -1.5 * np.exp(-((Y - np.interp(X, self.wadi_p[:, 0], self.wadi_p[:, 1])) / 380.0) ** 2) * ss(0.0, 150.0, D)
        return base + rise + ped + swell + swale

    def channels(self, g):
        """the wadis cut into the floor: their depth below it (negative), the bed mask, the bars' height"""
        lines = [self.wadi_p] + [q for q, _, _ in self.tribs]
        halfs = [None] + [h_ for _, h_, _ in self.tribs]
        depths = [1.7] + [d_ for _, _, d_ in self.tribs]
        cut = np.zeros(g.X.shape, np.float32)
        bed = np.zeros(g.X.shape, np.float32)
        for k, ln in enumerate(lines):
            if k == 0:
                # the main wadi's half width varies along it: drawn per run of 100 m with its value (half width, m)
                runs = [ln[i:i + 11] for i in range(0, len(ln) - 1, 10)]
                vals = [max(1, min(255, int(round(self.wadi_half[min(i + 5, len(ln) - 1)])))) for i in range(0, len(ln) - 1, 10)]
                dist, hv = g.dist(runs, vals)
                half = hv.astype(np.float32)
            else:
                dist, _ = g.dist([ln])
                half = np.float32(halfs[k])
            bank = np.maximum(half * 0.12, 5.0)
            prof = 1.0 - ss(half - bank, half, dist)
            cut = np.minimum(cut, -depths[k] * prof)
            bed = np.maximum(bed, 1.0 - ss(half - bank * 0.6, half - bank * 0.1, dist))
        bar = np.zeros(g.X.shape, np.float32)
        if g.cell <= 4.0:
            for (bx, by, L, W, h_, a) in self.bars:
                r = max(L, W) + 2 * g.cell
                i0, i1 = int((bx - r - g.x0) / g.cell), int((bx + r - g.x0) / g.cell) + 1
                j0, j1 = int((by - r - g.y0) / g.cell), int((by + r - g.y0) / g.cell) + 1
                if i1 <= 0 or j1 <= 0 or i0 >= g.n or j0 >= g.n:
                    continue
                i0, j0, i1, j1 = max(i0, 0), max(j0, 0), min(i1, g.n), min(j1, g.n)
                dx, dy = g.X[j0:j1, i0:i1] - bx, g.Y[j0:j1, i0:i1] - by
                u = (math.cos(a) * dx + math.sin(a) * dy) / L
                v = (-math.sin(a) * dx + math.cos(a) * dy) / W
                q = np.clip(1.0 - u * u - v * v, 0.0, 1.0)
                bar[j0:j1, i0:i1] = np.maximum(bar[j0:j1, i0:i1], h_ * q ** 0.6)
            bar *= bed
        return cut, bed, bar

    def dunes(self, X, Y):
        p = self.P['dune']
        dx, dy = X - p['c'][0], Y - p['c'][1]
        rho = np.sqrt((dx / p['a']) ** 2 + (dy / p['b']) ** 2)
        out = np.zeros(X.shape, np.float32)
        sel = rho < 1.12
        if sel.any():
            u, v = turn(dx[sel], dy[sel], p['rot'])
            sand = p['scale'] * sample_stack(self.S['dunes'], 'sand', u / p['scale'], v / p['scale'])
            out[sel] = np.maximum(sand - 72.0 * ss(0.62, 1.05, rho[sel]), 0.0)
        sheet = ss(1.32, 0.78, rho)                                    # the sand sheet round the field
        return out, sheet.astype(np.float32)

    def escarpment(self, X, Y):
        p = self.P['esc']
        out = np.zeros(X.shape, np.float32)
        s = p['scale']
        sel = (Y > 900.0) & (np.abs(X - p['c'][0]) < 8000.0 * s) & (Y < p['c'][1] + 8000.0 * s)
        if sel.any():
            u, v = turn(X[sel] - p['c'][0], Y[sel] - p['c'][1], p['rot'])
            h = s * (sample_stack(self.S['mesas'], 'h', u / s, v / s) - 8.0)
            # (each fade ends inside the source's +-8 km (x 0.8): past it the samples are its edge drawn out; where
            #  each fade starts wanders, so the plateau's corners are not rounded rectangles in plan)
            xs_, ys_ = X[sel], Y[sel]
            lat = 3900.0 + 650.0 * np.sin(ys_ / 1450.0 + 0.3) + 330.0 * np.sin(ys_ / 610.0 + 2.0)
            back = p['c'][1] + 3900.0 + 600.0 * np.sin(xs_ / 1700.0) + 300.0 * np.sin(xs_ / 730.0 + 1.0)
            t = 340.0 * (1.0 - ss(1600.0, 2500.0, ys_)) + 340.0 * ss(lat, lat + 1500.0, np.abs(xs_ - p['c'][0])) + 340.0 * ss(back, back + 1500.0, ys_)
            out[sel] = np.maximum(h - t, 0.0)
        return out

    def rills(self, X, Y, relief=False):
        """the floor's drainage lines: 0..1 by the borrowed network's drainage area (RILL); with relief, also the
        floor's low swells and hollows (metres) from the same network"""
        p = self.P['rill']
        out = np.zeros(X.shape, np.float32)
        rel = np.zeros(X.shape, np.float32)
        sel = np.hypot(X, Y) < 7000.0
        if sel.any():
            u, v = turn(X[sel] - p['off'][0], Y[sel] - p['off'][1], p['rot'])
            A = sample_stack(self.S['range'][-2:], 'A', u / p['scale'], v / p['scale'])
            out[sel] = ss(p['lo'], p['hi'], np.log10(np.maximum(A, 1.0)))
            if relief:
                hp = sample_stack(self.S['range'][-2:], 'hp', u / p['scale'], v / p['scale'])
                rel[sel] = np.clip(p['relief'] * hp, -p['relief_cap'], p['relief_cap']) * ss(7000.0, 5500.0, np.hypot(X[sel], Y[sel]))
        return (out, rel) if relief else out

    def ranges(self, X, Y):
        r = np.hypot(X, Y)
        az = np.arctan2(Y, X)
        out = np.zeros(X.shape, np.float32)
        sel = r > 6000.0
        if sel.any():
            u, v = turn(X[sel], Y[sel], self.P['range']['rot'])
            H = sample_stack(self.S['range'], 'h', u, v)
            rr, aa = r[sel], az[sel]
            sector = np.zeros(rr.shape, np.float32)
            for a0, lower, spread in self.P['sectors']:
                da = np.angle(np.exp(1j * (aa - math.radians(a0))))
                sector = np.maximum(sector, lower * np.exp(-(da / math.radians(spread)) ** 2))
            fill = 2800.0 + 2800.0 * (1.0 - ss(7000.0, 12500.0, rr)) - 450.0 * ss(11000.0, 24000.0, rr) - sector
            out[sel] = self.P['range']['vscale'] * np.maximum(H - fill, 0.0)
        return out

    def inselbergs(self, X, Y):
        out = np.zeros(X.shape, np.float32)
        for k, ((cx, cy), (sx, sy), s, rot, emerge, rad) in enumerate(self.P['insel']):
            dx, dy = X - cx, Y - cy
            d = np.hypot(dx, dy)
            sel = d < rad * 1.6
            if not sel.any():
                continue
            u, v = turn(dx[sel], dy[sel], rot)
            H = sample_stack(self.S['range'], 'h', sx + u / s, sy + v / s)
            fill = self.insel_peak[k] - emerge + 1100.0 * ss(rad * 0.55, rad * 1.5, d[sel])
            out[sel] = np.maximum(out[sel], s * np.maximum(H - fill, 0.0))
        return out

    # ---- a level
    def level(self, name, half, cell, apron_c=None):
        t0 = time.time()
        g = Grid(half, cell)
        X, Y = g.X, g.Y
        D = town_dist_at(self.D, X, Y)
        F = self.floor(X, Y, D)
        cut, bed, bar = self.channels(g)
        sand, sheet = self.dunes(X, Y)
        if cell <= 4.0:                                               # (the crests and brinks sharpened)
            ds = self.P['dune_sharp']
            sand = np.maximum(sand + ds['k'] * (sand - ndi.gaussian_filter(sand, ds['sigma'] / cell)), 0.0).astype(np.float32)
        esc = self.escarpment(X, Y)
        mtn = np.maximum(self.ranges(X, Y), self.inselbergs(X, Y))
        if apron_c is None:                                           # (level C makes the aprons; the others sample them)
            ins_only = self.inselbergs(X, Y)
            apron = 0.10 * ndi.gaussian_filter(mtn, 700.0 / cell) + 0.12 * ndi.gaussian_filter(ins_only, 260.0 / cell) + 0.05 * ndi.gaussian_filter(esc, 300.0 / cell)
        else:
            ac, hc, cc = apron_c
            fi, fj = (X + hc) / cc - 0.5, (Y + hc) / cc - 0.5
            apron = ndi.map_coordinates(ac, [fj.ravel(), fi.ravel()], order=1, mode='nearest').reshape(X.shape).astype(np.float32)
        apron *= ss(300.0, 900.0, D)
        cut *= (1.0 - ss(0.5, 3.0, sand)) * (1.0 - ss(2.0, 20.0, mtn + esc))   # (no wadi cuts through a dune or through rock)
        rill, swell = self.rills(X, Y, relief=True)
        floor_only = (1.0 - ss(0.3, 2.0, sand)) * (1.0 - ss(1.0, 8.0, mtn + esc)) * (1.0 - bed)
        rill *= ss(60.0, 220.0, D) * floor_only
        swell *= ss(150.0, 700.0, D) * floor_only                     # (kept off the town's plane: its hollows stay over z 0)
        h = (F + cut + bar + sand + esc + mtn + apron - self.P['rill']['depth'] * rill + swell
             - (X.astype(np.float64) ** 2 + Y.astype(np.float64) ** 2).astype(np.float32) / (2.0 * EARTH_R))
        out = dict(h=h.astype(np.float32), town=np.minimum(D, 5000.0).astype(np.float32), sand=sand, sheet=sheet, bed=bed, bar=bar, esc=esc, mtn=mtn,
                   apron=apron.astype(np.float32), rill=rill.astype(np.float32))
        print(f'[desert] land level {name}: {g.n}^2 at {cell} m, h {float(h.min()):.1f}..{float(h.max()):.1f} in {time.time() - t0:.1f} s', flush=True)
        return g, out

    def marks(self, g):
        """what is finer than the mesh, as an image over a level's grid: R the tracks, G the wadi beds (0.6) and their
        bars (to 1), B the floor's drainage lines, A the sand sheet"""
        lines = [p for p, _ in self.tracks]
        vals = [int(255 * s) for _, s in self.tracks]
        d, sv = g.dist(lines, vals)
        width = 2.1 if g.cell <= 1.0 else 2.6
        trk = (1.0 - ss(width * 0.6, width + g.cell, d)) * (sv / 255.0)
        # a track fades along its length out of the town (who drives it thins out), and goes on faint
        trk *= 0.55 + 0.45 * np.exp(-np.maximum(np.hypot(g.X, g.Y) - 600.0, 0.0) / 4000.0)
        _, bed, bar = self.channels(g)
        sand, sheet = self.dunes(g.X, g.Y)
        D = town_dist_at(self.D, g.X, g.Y)
        rill = self.rills(g.X, g.Y) * ss(60.0, 220.0, D) * (1.0 - ss(0.3, 2.0, sand)) * (1.0 - bed)
        rill *= 1.0 - ss(1.0, 8.0, self.escarpment(g.X, g.Y) + np.maximum(self.ranges(g.X, g.Y), self.inselbergs(g.X, g.Y)))
        img = np.stack([trk, 0.6 * bed + 0.4 * np.minimum(bar / 0.35, 1.0), rill, np.maximum(sheet, ss(0.3, 3.0, sand))], -1)
        return (np.clip(img, 0, 1) * 255).astype(np.uint8)


def compose(work, grid='film', plan=None, log=print):
    """the land's three levels and its marks into <work>/build (C first: the aprons are made on it, the others sample
    them); the grid's name and cells into build/land.json"""
    build = os.path.join(work, 'build')
    os.makedirs(build, exist_ok=True)
    levels = GRIDS[grid]
    land = Land(work, plan, log)
    (nC, hC, cC) = levels[2]
    gC, oC = land.level(nC, hC, cC)
    np.savez(os.path.join(build, f'land_{nC}.npz'), half=gC.half, cell=gC.cell, n=gC.n, **oC)
    apron_c = (oC['apron'], hC, cC)
    del gC, oC
    for name, half, cell in levels[:2][::-1]:
        g, o = land.level(name, half, cell, apron_c)
        np.savez(os.path.join(build, f'land_{name}.npz'), half=g.half, cell=g.cell, n=g.n, **o)
        Image.fromarray(np.flipud(land.marks(g)), 'RGBA').save(os.path.join(build, 'near_marks.png' if name == 'A' else 'mid_marks.png'))
        del g, o
    with open(os.path.join(build, 'land.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(grid=grid, levels=[list(v) for v in levels], tracks=land.track_source), f, indent=1)
    log(f'[desert] land saved in {build}')


if __name__ == '__main__':
    A = sys.argv[1:]
    compose(os.path.abspath(A[A.index('--work') + 1]), A[A.index('--grid') + 1] if '--grid' in A else 'film')

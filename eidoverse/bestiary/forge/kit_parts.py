"""KIT PARTS: the robotics kit's machinist grammar as sdf.Program GENERATORS (ROADMAP §3 C4; research/parity/KIT_PORT.md
§6 K3). The kit's own generator source is not in the repo (KIT_PORT §0.2), and its GLBs can't be scaled to a creature: its
gaps, breaks and fasteners are absolutes, and a uniformly scaled TC70 reads as a toy (KIT_PORT §6 "what not to do"). So
the grammar is re-authored here: every part is SIZED FROM A SOCKET'S DIMS (remix/slots.py mount_dims: radius, bolt
circle, bolts, pilot; or a kit interface's name), its DIAMETERS follow the kit's measured ratios and its GAPS, BREAKS
and FASTENERS stay absolute. The output is a high (an sdf.Program), the pieces' material ids, the lathe lows' side
counts and the parts' kit-shaped ports. Route B's library: K2's spacer and collar face, K4's joints, K5's mount plate,
K6's small modules.

THE GENERATORS (each writes into a Part: one sdf.Program, one GROUP per piece, so a piece's own cuts never cut another
piece; a piece carries one material id):
  flange_face(part, frame, dims)      the six-bolt face: an annulus OD 2 r, a through PILOT bore, thickness t/OD from the
                                      kit (TC70 0.086 at OD 70 to MC110 0.127 at OD 110), counterbored socket heads on
                                      the bolt circle, sunk under the MATING face (the kit's heads are on it: the face a
                                      mated part covers sits flat)
  counterbore(part, host, centre, axis, screw, depth)
                                      the cut in the open host piece (the 0.35 x 45 deg polished mouth, the head's bore
                                      with 0.45 radial clearance, the shank hole) and its ISO 4762 socket head as its
                                      own piece (top edge break, the hex socket 0.7 d deep, the 90 deg countersink to
                                      1.25 x the hex's circumradius), sunk 0.3 mm
  joint_stack(part, frame, dims, kind)  'roll' (the M360 forearm's drive: input flange, the tapered stator, the seal on
                                      its top standing 1 mm proud, the 1 mm gap, the output flange on the hollow
                                      spindle) or 'pitch' (the M360 elbow: input flange, the bell housing with flat bore
                                      faces, bright inserts in its side pockets, the dark hollow spindle through them,
                                      the bright output collar 2.0 mm off the housing)
  sm40_foot(part, frame, pattern)     the SM40-style rectangular foot (kit 44 x 34 x 6, R8 corners, pattern 33 x 27): its
                                      outline from the pattern at the kit's proportions, grown where a counterbore would
                                      leave a lip under 1 mm; four counterbored heads at the pattern's corners

FRAMES. Every generator takes the SOCKET's frame (slots.port_frame: Z its outward normal, X its tangent; origin on the
mating plane). A host-side part (flange_face as a collar's distal face) lies under the plane (z <= 0); a module-side
part (the foot, a joint stack's input flange) lies over it (z >= 0). Ports are written as the kit writes them
(robotics/index.js 55-171): position, normal (OUT of the part: the mate opposes normals), tangent, and the interface's
dims in metres.

SIZES (kit_body NOTES §2.3, §2.6, §3.2, measured on the kit GLBs in
work/bestiary/research/cyborg_work/games/kit_body/kit_measure.json; radii, re-measured off the GLBs by C4's checker):
  flange      PCD / OD 0.764-0.786, pilot / OD 0.218-0.343, t / OD 0.086-0.127 (TC70 35 / 27.5 / 12 / 6 mm, MC110
              55 / 42 / 12 / 14 mm); 40-48 sides in the kit, here the SAGITTA rule
  stack       (TC70 elbow / forearm, R = the interface radius 35 mm) spindle 0.506 R hollow to the pilot (cables through
              the bore: no hose at a kit joint), insert 0.579 R x 8 mm, collar 0.70 R x 5 mm, pitch housing a bell 68 x
              70 x 67 (STACK['bell']), roll stator 0.914 R tapering to 0.857 R, seal r 0.6-0.886 R x 5 mm
  gaps        (absolute) shaft in its bore 0.29 radial, press fit 0.04, rotor over stator 0.5, collar past a housing
              2.0, by a seal 1.0, register 0.45-1 deep
  breaks      0.4 at 45 deg on machined edges, held under 0.4 of the wall; castings round 1.5; elastomer 0.6
  fasteners   ISO 4762 socket heads, head D <= 0.06 OD (the kit's 0.05-0.06), lips >= 1 mm, sunk 0.3, counterbore 0.45
              radial over the head, 0.35 mouth, hex 0.7 d deep, countersink 1.25 x the hex circumradius. M1.6 is the
              least: a part that can't hold M1.6 with its lips is REFUSED (KitPartError 'kit.fastener_min': use the
              split-clamp collar, cyborg_limb's), never scaled below it

SIDES (the low): sides(r, sag) = the least multiple of 4 whose chord sagitta r (1 - cos(pi / n)) <= sag; HERO_SAG =
0.1 mm (the C4 gate: under half a pixel at 0.2 m, 0.214 mm per pixel at 1080 lines / 60 deg). Each piece's lathe profile
is recorded with its side count; low_mesh() revolves them (the high's profile, every break a ring), so the low differs
from the high only by the chord sagitta. Bores, counterbores and heads are bake detail on the face (the kit's own
choice: its TC70 low is a plain annulus), but every head is one piece of a REPEAT group, so a consumer's UVs stack them.

MATERIAL IDS (forge/cyborg.py CYBORG_ID, read only; KIT_PORT §3 item 3, the kit's tiers folded into our rows):
  64 cyb_titanium      bright machined: flanges, inserts, collars, the foot (the kit's 'bright machined' tier)
  65 cyb_paint         housings, stators (the kit's paint, mask.r): the primary tint region
  66 cyb_steel         socket heads (black oxide)
  67 cyb_gasket        seals
  69 cyb_glow          the optional inlay ring in a roll stator's groove (one glow colour per creature)
  70 cyb_paint_accent  the dark spindle (cyborg.ACCENT_DEFAULT is the kit's dark machined tier): the accent region
  68 cyb_scar is the skin over a junction: never on a kit part (graft_socket's band carries it)
MASKS (the cyborg pack: R primary tint, G accent, B emissive, A wear): R, G, B follow the ids (masks_at); A is the bake's
(cyborg_limb's edge rule over WEARS: paint and accent wear to titanium, black oxide to bare steel).

Read with numpy and warp (sdf.Program evaluates on warp's device).
"""
import math
from contextlib import contextmanager

import numpy as np

from . import sdf as SD
from .cyborg import CYBORG_ID

MM = 1.0e-3
HERO_SAG = 0.1 * MM          # the C4 facet gate: chord sagitta at hero distance
# ---- the kit's interfaces (CAT records; kit_body §2.3): radius, bolt circle radius, bolts, pilot radius (m)
KIT_INTERFACES = {
    'TC70': dict(radius=35.0 * MM, bolt_circle=27.5 * MM, bolts=6, pilot=12.0 * MM, thickness=6.0 * MM),
    'MC110': dict(radius=55.0 * MM, bolt_circle=42.0 * MM, bolts=6, pilot=12.0 * MM, thickness=14.0 * MM,
                  opening=23.6 * MM),     # the through-bore its GLB and records carry ("mating opening r 23.6")
    'LEGACY64-R50': dict(radius=32.0 * MM, bolt_circle=25.0 * MM, bolts=6, pilot=9.0 * MM, thickness=None),
}
SM40 = dict(pattern=(33.0 * MM, 27.0 * MM), outline=(44.0 * MM, 34.0 * MM), corner=8.0 * MM, thickness=6.0 * MM)
# ---- the kit's measured ratio ranges (TC70, MC110) and the stack ratios (TC70 elbow / forearm, R = 35 mm)
RATIO = dict(pcd=(42.0 / 55.0, 27.5 / 35.0), pilot=(12.0 / 55.0, 12.0 / 35.0), t_od=(6.0 / 70.0, 14.0 / 110.0))
STACK = dict(spindle=17.7 / 35.0, insert=20.25 / 35.0, insert_len=8.0 / 70.0, collar=24.5 / 35.0, collar_len=5.0 / 70.0,
             housing_x=34.0 / 35.0, pocket=5.0 / 70.0,
             # the pitch housing's bell (stock bearing.tc70.pitch.housing, measured in its own axes; units of R, from
             # its base): r 32 at the base, 35 by 13 mm, straight to the bore's axis at 35, tapering to r 29 at 56,
             # rounded over to a flat top r 17 at 67; its two bore faces flat at +-34
             bell=((32.0, 0.0), (35.0, 13.0), (35.0, 35.0), (29.0, 56.0), (17.0, 67.0)), bell_axis=35.0,
             stator=32.0 / 35.0, stator_top=30.0 / 32.0, stator_len=33.0 / 70.0, stator_taper=(6.0 / 33.0, 27.0 / 33.0),
             seal_od=31.0 / 32.0, seal_id=21.0 / 35.0, seal_len=5.0 / 70.0)
# ---- absolutes (KS §1; kit_body §2.6, §3.2)
GAP = dict(bore=0.29 * MM, press=0.04 * MM, rotor=0.5 * MM, collar=2.0 * MM, seal=1.0 * MM, register=0.6 * MM)
BREAK = 0.4 * MM             # machined edge break, 45 deg
BREAK_WALL = 0.4             # a break stays under 0.4 of its wall
CAST_ROUND = 1.5 * MM        # castings (housings, stators)
SOFT_ROUND = 0.6 * MM        # elastomer
HOUSING_EDGE = 2.0 * MM      # the smooth cut where a bell housing meets its flat bore faces (sinks the edge k / 4)
SINK = 0.3 * MM              # a head's top under its face
CB_CLEAR = 0.45 * MM         # counterbore radial clearance over the head
MOUTH = 0.35 * MM            # the polished 45 deg mouth
LIP = 1.0 * MM               # least land round a counterbore
HEAD_OD_MAX = 0.06           # head D <= 0.06 OD (the kit's 0.05-0.06)
FOOT_HEAD = 0.12             # a foot's head D <= 0.12 of its short side (the kit's M2, 3.8 mm, on 34 mm: 0.112)
# ISO 4762 socket head cap screws: size -> (d, head D dk, head height k, hex AF s), m
ISO4762 = {'M1.6': (1.6, 3.0, 1.6, 1.5), 'M2': (2.0, 3.8, 2.0, 1.5), 'M2.5': (2.5, 4.5, 2.5, 2.0),
           'M3': (3.0, 5.5, 3.0, 2.5), 'M4': (4.0, 7.0, 4.0, 3.0), 'M5': (5.0, 8.5, 5.0, 4.0),
           'M6': (6.0, 10.0, 6.0, 5.0), 'M8': (8.0, 13.0, 8.0, 6.0)}
ISO4762 = {k: tuple(x * MM for x in v) for k, v in ISO4762.items()}
FASTENER_MIN = 'M1.6'
ID = dict(CYBORG_ID)
MASKS_RGB = {ID['cyb_paint']: (1.0, 0.0, 0.0), ID['cyb_paint_accent']: (0.0, 1.0, 0.0), ID['cyb_glow']: (0.0, 0.0, 1.0)}
WEARS = {ID['cyb_paint']: 'cyb_titanium', ID['cyb_paint_accent']: 'cyb_titanium', ID['cyb_steel']: 'bare steel'}
KIT_IDS = tuple(ID[n] for n in ('cyb_titanium', 'cyb_paint', 'cyb_steel', 'cyb_gasket', 'cyb_glow', 'cyb_paint_accent'))


class KitPartError(ValueError):
    """a kit part the forge refuses; .code names the rule (kit.fastener_min, kit.dims, kit.interface)"""

    def __init__(self, code, message):
        self.code = code
        super().__init__(f'{code}: {message}')


# ============================================================================================ sizing
def sides(r, sag=HERO_SAG, lo=8, hi=256):
    """the least multiple of 4 (lo..hi) whose chord sagitta round a circle of radius r is <= sag"""
    if r <= sag:
        return lo
    n = math.pi / math.acos(max(-1.0, 1.0 - sag / r))
    return int(min(hi, max(lo, 4 * math.ceil(n / 4.0 - 1e-9))))


def sagitta(r, n):
    return r * (1.0 - math.cos(math.pi / n))


def interface_dims(name):
    """a kit interface's dims in slots' mount vocabulary (radius, bolt_circle, bolts, pilot)"""
    if name not in KIT_INTERFACES:
        raise KitPartError('kit.interface', f'{name!r} is not a kit interface with dims ({tuple(KIT_INTERFACES)})')
    d = KIT_INTERFACES[name]
    return dict(radius=d['radius'], bolt_circle=d['bolt_circle'], bolts=d['bolts'], pilot=d['pilot'])


def kit_interface(dims, tol=0.15):
    """the kit interface a mount's dims name (radius within tol, the bolt count equal), or None: KIT_PORT §5.1"""
    best = None
    for k, d in KIT_INTERFACES.items():
        e = abs(dims['radius'] / d['radius'] - 1.0)
        if e <= tol and int(dims.get('bolts', 0)) == d['bolts'] and (best is None or e < best[1]):
            best = (k, e)
    return best[0] if best else None


def _check_dims(dims):
    try:
        R, Rb, n, Rp = float(dims['radius']), float(dims['bolt_circle']), int(dims['bolts']), float(dims['pilot'])
    except (KeyError, TypeError, ValueError) as e:
        raise KitPartError('kit.dims', f'mount dims need radius, bolt_circle, bolts, pilot (m): {dims!r}') from e
    if not (0.0 < Rp < Rb < R < 1.0) or n < 3:
        raise KitPartError('kit.dims', f'need 0 < pilot < bolt_circle < radius < 1 m and 3+ bolts: {dims!r}')
    return R, Rb, n, Rp


def t_ratio(od):
    """flange thickness over OD: the kit's TC70 0.086 at OD 70 mm to MC110 0.127 at OD 110 (linear between, held
    outside)"""
    a = min(1.0, max(0.0, (od - 70.0 * MM) / (40.0 * MM)))
    return RATIO['t_od'][0] + a * (RATIO['t_od'][1] - RATIO['t_od'][0])


def cb_radius(size):
    return 0.5 * ISO4762[size][1] + CB_CLEAR + MOUTH


def screw_depth(size):
    """the least wall under a counterbored head: sink + head height + a floor of max(0.5 mm, 0.3 d)"""
    d, dk, k, s = ISO4762[size]
    return SINK + k + max(0.5 * MM, 0.3 * d)


def opening_of(dims):
    """the face's visible through-bore: dims' 'opening' when given, else a kit interface's own opening scaled to the
    radius (MC110: r 23.6 of 55, wider than its 12 mm pilot record), else the pilot"""
    if 'opening' in dims:
        return float(dims['opening'])
    k = kit_interface(dims)
    if k and 'opening' in KIT_INTERFACES[k]:
        return KIT_INTERFACES[k]['opening'] * float(dims['radius']) / KIT_INTERFACES[k]['radius']
    return float(dims['pilot'])


def pick_screw(dims, thickness=None, od_rule=True):
    """the largest ISO 4762 size a flange face holds: head D <= 0.06 OD (od_rule; M1.6, the floor, is exempt: a small
    face keeps an absolute M1.6 head, larger than 0.06 of it, rather than a scaled one), every lip >= 1 mm (to the pilot
    bore, to the rim, between neighbours), and (when the thickness is given) the counterbore's wall. Refuses where even
    M1.6 can't keep its lips (KitPartError 'kit.fastener_min'). Returns (size, report)"""
    R, Rb, n, Rp = _check_dims(dims)
    Rp = max(Rp, opening_of(dims))
    why = []
    for size in sorted(ISO4762, key=lambda s: -ISO4762[s][0]):
        d, dk, k, s = ISO4762[size]
        cbr = cb_radius(size)
        lips = dict(pilot=Rb - cbr - Rp, rim=R - Rb - cbr, between=2.0 * Rb * math.sin(math.pi / n) - 2.0 * cbr)
        if od_rule and dk > HEAD_OD_MAX * 2.0 * R + 1e-12 and size != FASTENER_MIN:
            why.append(f'{size}: head D {dk / MM:.1f} > {HEAD_OD_MAX} OD')
            continue
        if min(lips.values()) < LIP - 1e-12:
            why.append(f'{size}: lip {min(lips, key=lips.get)} {min(lips.values()) / MM:.2f} mm < 1')
            continue
        if thickness is not None and thickness < screw_depth(size) - 1e-12:
            why.append(f'{size}: wall {thickness / MM:.2f} < {screw_depth(size) / MM:.2f} mm')
            continue
        return size, dict(size=size, head_od=dk / (2.0 * R), lips_mm={k_: v / MM for k_, v in lips.items()})
    raise KitPartError('kit.fastener_min', f'radius {R / MM:.2f} mm, bolt circle {Rb / MM:.2f}, pilot {Rp / MM:.2f}: '
                       f'no ISO 4762 size down to {FASTENER_MIN} fits ({"; ".join(why[-3:])}); use the split-clamp '
                       f'collar (forge/cyborg_limb.py), never a scaled face')


def flange_dims(radius, kind='TC70'):
    """a mount's dims at a radius in a kit flange's proportions (TC70: slots.mount_dims' own; MC110)"""
    d = KIT_INTERFACES[kind]
    s = radius / d['radius']
    return dict(radius=radius, bolt_circle=d['bolt_circle'] * s, bolts=d['bolts'], pilot=d['pilot'] * s)


# ============================================================================================ frames, parts
def _unit(v):
    v = np.asarray(v, np.float64)
    return v / np.linalg.norm(v)


class Frame:
    """origin, X (the tangent), Y = Z x X, Z (the normal): slots.port_frame's basis"""

    def __init__(self, origin=(0.0, 0.0, 0.0), z=(0.0, 0.0, 1.0), x=(1.0, 0.0, 0.0)):
        Z = _unit(z)
        X = np.asarray(x, np.float64) - Z * float(np.dot(x, Z))
        if np.linalg.norm(X) < 1e-9:
            raise KitPartError('kit.frame', 'the tangent lies along the normal')
        X = _unit(X)
        self.o = np.asarray(origin, np.float64)
        self.R = np.column_stack([X, np.cross(Z, X), Z])

    def p(self, q):
        return self.o + self.R @ np.asarray(q, np.float64)

    def v(self, d):
        return self.R @ np.asarray(d, np.float64)

    def sub(self, origin=(0.0, 0.0, 0.0), z=(0.0, 0.0, 1.0), x=(1.0, 0.0, 0.0)):
        return Frame(self.p(origin), self.v(z), self.v(x))


class Part:
    """one sdf.Program and its pieces. A piece is a GROUP (its union primitives, then its own cuts), one material id,
    optionally one member of a REPEAT group (identical pieces: their UVs stack). Lows: the lathe profiles and the
    extruded outlines with their side counts. Ports: kit-shaped records"""

    def __init__(self, name):
        self.name = name
        self.prog = SD.Program()
        self.pieces = []
        self.lows = []
        self.ports = []
        self.report = {}
        self._cur = None
        self._piece_progs = {}

    @contextmanager
    def piece(self, name, mat, repeat=None):
        assert self._cur is None, 'pieces do not nest'
        pc = dict(name=name, mat=mat, id=ID[mat], calls=[], repeat=repeat)
        self.pieces.append(pc)
        self.prog.begin_group(op=SD.UNION, k=0.0)
        self._cur = pc
        try:
            yield pc
        finally:
            self.prog.end_group()
            self._cur = None

    def add(self, meth, *a, **kw):
        assert self._cur is not None, 'primitives belong to a piece'
        if not self._cur['calls']:
            assert kw.get('op', SD.UNION) == SD.UNION, 'a piece starts with a union primitive'
        self._cur['calls'].append((meth, a, kw))
        return getattr(self.prog, meth)(*a, **kw)

    def lathe(self, frame, profile, centre=(0.0, 0.0, 0.0), axis=(0.0, 0.0, 1.0), op=SD.UNION, low=True, name='',
              low_profile=None, low_sag=0.0):
        """revolve a profile (r, y) about the frame-local axis through the frame-local centre; a union's profile is
        recorded for the low, its sides by the sagitta rule. low_profile: the same outline generated at a coarser
        chord sagitta low_sag (fillets: the high's arcs run at 0.01 mm); the low's sides then take what is left of the
        facet budget (generated, never decimated)"""
        c, a = frame.p(centre), _unit(frame.v(axis))
        P = np.asarray(profile, np.float64)
        self.add('revolve', P, c, a, op=op, name=name or self._cur['name'])
        if low and op == SD.UNION:
            L = P if low_profile is None else np.asarray(low_profile, np.float64)
            self.lows.append(dict(piece=len(self.pieces) - 1, kind='lathe', profile=L, centre=c, axis=a,
                                  x=frame.R[:, 0], low_sag=low_sag, sides=sides(float(L[:, 0].max()), HERO_SAG - low_sag),
                                  call=len(self._cur['calls']) - 1))

    def piece_prog(self, i, calls=None):
        """piece i's own Program (its primitives and cuts; calls: only these call indices)"""
        key = (i, None if calls is None else tuple(calls))
        if key not in self._piece_progs:
            p = SD.Program()
            for j, (m, a, kw) in enumerate(self.pieces[i]['calls']):
                if calls is None or j in calls:
                    getattr(p, m)(*a, **kw)
            self._piece_progs[key] = p
        return self._piece_progs[key]

    def ids_at(self, P, with_piece=False):
        """each point's material id: the piece whose own surface is nearest (its cuts included)"""
        P = np.atleast_2d(np.asarray(P, np.float64))
        D = np.stack([np.abs(self.piece_prog(i).eval(P)) for i in range(len(self.pieces))])
        k = np.argmin(D, axis=0)
        ids = np.asarray([pc['id'] for pc in self.pieces], np.int64)[k]
        return (ids, k) if with_piece else ids

    def masks_at(self, P):
        """(n, 4) MASKS: R primary tint, G accent, B emissive by the ids; A 0 (the bake writes the wear: WEARS)"""
        ids = self.ids_at(P)
        M = np.zeros((len(ids), 4))
        for i, rgb in MASKS_RGB.items():
            M[ids == i, :3] = rgb
        return M

    def port(self, name, interface, frame, normal_sign=1.0, dims=None):
        rec = dict(name=name, interface=interface, position_m=frame.o.tolist(),
                   normal=(normal_sign * frame.R[:, 2]).tolist(), tangent=frame.R[:, 0].tolist())
        if dims:
            rec.update(radius_m=dims['radius'], bolt_circle_radius_m=dims['bolt_circle'], bolt_count=int(dims['bolts']),
                       pilot_radius_m=dims['pilot'])
        self.ports.append(rec)
        return rec


def _brk(wall):
    return min(BREAK, BREAK_WALL * wall)


def _arc(c, r, a0, a1, n):
    t = np.linspace(a0, a1, n)
    return [(c[0] + r * math.cos(x), c[1] + r * math.sin(x)) for x in t]


def _fillet(P, radii, sag=0.01 * MM):
    """an open polyline P (n, 2) with vertex i rounded by radii[i] (0: kept sharp; the ends are always kept): each
    rounded corner becomes a tangent arc, its radius clamped so it takes at most half of either neighbouring segment,
    its points at a 0.01 mm chord sagitta (the high's polygon: far under the low's)"""
    P = np.asarray(P, np.float64)
    out = [P[0]]
    for i in range(1, len(P) - 1):
        r = radii[i]
        a, b = P[i - 1] - P[i], P[i + 1] - P[i]
        la, lb = np.linalg.norm(a), np.linalg.norm(b)
        a, b = a / la, b / lb
        th = math.acos(max(-1.0, min(1.0, float(a @ b))))
        if r <= 0.0 or th > math.pi - 1e-6:
            out.append(P[i])
            continue
        tl = r / math.tan(0.5 * th)
        tl_max = 0.5 * min(la, lb)
        if tl > tl_max:
            tl, r = tl_max, tl_max * math.tan(0.5 * th)
        p0, p1 = P[i] + a * tl, P[i] + b * tl
        bis = (a + b) / np.linalg.norm(a + b)
        c = P[i] + bis * (r / math.sin(0.5 * th))
        a0, a1 = math.atan2(*(p0 - c)[::-1]), math.atan2(*(p1 - c)[::-1])
        da = (a1 - a0 + math.pi) % (2.0 * math.pi) - math.pi
        n = max(2, int(math.ceil(abs(da) / (2.0 * math.acos(max(-1.0, 1.0 - sag / r))))) + 1)
        out += _arc(c, r, a0, a0 + da, n)
    out.append(P[-1])
    out = np.asarray(out)
    keep = np.concatenate([[True], np.linalg.norm(np.diff(out, axis=0), axis=1) > 1e-9])   # two arcs meeting
    return out[keep]


# ============================================================================================ counterbore + head
def counterbore(part, host_frame, xy, screw, depth, repeat='screw'):
    """the counterbore CUT in the open host piece at xy on the host frame's z = 0 face (the face's outward normal +Z;
    the wall is `depth` thick under it), then the socket head as its own piece. Call inside the host's piece; the head
    is added after the host closes (returned as a closure)"""
    d, dk, k, s = ISO4762[screw]
    if depth < screw_depth(screw) - 1e-12:
        raise KitPartError('kit.fastener_min', f'{screw} needs a {screw_depth(screw) / MM:.2f} mm wall, '
                           f'{depth / MM:.2f} given')
    hf = host_frame.sub((xy[0], xy[1], 0.0))
    e = 0.3 * MM
    rc = 0.5 * dk + CB_CLEAR
    h = SINK + k
    rs = 0.55 * d
    cut = [(0.0, e), (rc + MOUTH + e, e), (rc, -MOUTH), (rc, -h), (rs, -h), (rs, -depth - e), (0.0, -depth - e)]
    part.lathe(hf, cut, op=SD.SUBTRACT, low=False, name=f'{part._cur["name"]} counterbore')

    def head():
        yt, yb = -SINK, -SINK - k
        c = 0.1 * d
        prof = [(0.0, yt), (0.5 * dk - c, yt), (0.5 * dk, yt - c), (0.5 * dk, yb), (0.5 * d, yb), (0.5 * d, yb - d),
                (0.0, yb - d)]
        rh = s / math.sqrt(3.0)                                   # the hex's circumradius
        rk = 1.25 * rh
        with part.piece(f'socket head {screw}', 'cyb_steel', repeat=f'{repeat}:{screw}'):
            part.lathe(hf, prof, low=False)
            hexp = np.array([[rh * math.cos(a), rh * math.sin(a)] for a in np.arange(6) * math.pi / 3.0 + math.pi / 6])
            rho = 0.04 * MM
            core = SD.Program.section_core(hexp, rho)
            part.add('psweep', np.array([hf.p((0, 0, yt + e)), hf.p((0, 0, yt - 0.7 * d))]), core, rho=rho,
                     normal=hf.R[:, 0], op=SD.SUBTRACT, name='hex socket')
            part.lathe(hf, [(0.0, yt + e), (rk + e, yt + e), (0.0, yt - rk)], op=SD.SUBTRACT, low=False,
                       name='hex countersink')
    return head


# ============================================================================================ flange face
def flange_face(part, frame, dims, thickness=None, clock=0.0, name='flange', mat='cyb_titanium', interface=None,
                od_rule=True):
    """the six-bolt FACE under the frame's z = 0 plane (a host-side face; its outward normal +Z, the body z in [-t, 0]):
    OD 2 dims.radius, the pilot bore, the kit's thickness ratio (raised to the screw's wall where a small face needs it),
    counterbored heads on the bolt circle clocked from the frame's tangent (clock 0: the first head ON the tangent, as
    the kit's TC70 and MC110 maps put theirs at 0, 60, ... deg, so a generated face mates a kit face hole to hole).
    Writes the port (normal +Z, the dims) and the report (ratios, screw, sides)"""
    R, Rb, n, Rp = _check_dims(dims)
    od = 2.0 * R
    t = thickness if thickness is not None else t_ratio(od) * od
    screw, rep = pick_screw(dims, thickness=None, od_rule=od_rule)
    t_need = screw_depth(screw)
    if thickness is None and t < t_need:
        t = t_need
    elif t < t_need:
        raise KitPartError('kit.fastener_min', f'{name}: {screw} needs a {t_need / MM:.2f} mm face, {t / MM:.2f} given')
    Ro = opening_of(dims)                                         # the through-bore (the pilot, or MC110's opening)
    b = _brk(min(t, R - Ro))
    prof = [(Ro, -b), (Ro + b, 0.0), (R - b, 0.0), (R, -b), (R, -t + b), (R - b, -t), (Ro + b, -t), (Ro, -t + b)]
    heads = []
    with part.piece(name, mat):
        part.lathe(frame, prof)
        for i in range(n):
            a = clock + 2.0 * math.pi * i / n
            heads.append(counterbore(part, frame, (Rb * math.cos(a), Rb * math.sin(a)), screw, t))
    for h in heads:
        h()
    iface = interface or kit_interface(dims) or 'mount'
    part.port(f'{name}_face', iface, frame, 1.0, dims)
    part.report[name] = dict(od_mm=od / MM, t_mm=t / MM, pcd_od=Rb / R, pilot_od=Rp / R, opening_od=Ro / R,
                             t_od=t / od, screw=screw,
                             head_od=rep['head_od'], lips_mm=rep['lips_mm'], sides=sides(R), interface=iface,
                             thickness_raised=bool(thickness is None and t > t_ratio(od) * od + 1e-12))
    return t


# ============================================================================================ SM40 foot
def _rrect(hx, hy, rc, per_corner):
    pts = []
    for cx, cy, a0 in ((hx - rc, hy - rc, 0.0), (-hx + rc, hy - rc, 0.5 * math.pi), (-hx + rc, -hy + rc, math.pi),
                       (hx - rc, -hy + rc, 1.5 * math.pi)):
        pts += _arc((cx, cy), rc, a0, a0 + 0.5 * math.pi, per_corner)
    return np.asarray(pts)


def _rrect_edge(hx, hy, rc, p):
    """distance from p inside the rounded rectangle to its edge"""
    qx, qy = abs(p[0]) - (hx - rc), abs(p[1]) - (hy - rc)
    out = math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0)
    return rc - out


def sm40_foot(part, frame, pattern=None, thickness=None, scale=1.0, name='sm40 foot', mat='cyb_titanium'):
    """the SM40-style foot ON the frame's z = 0 plane (module side: body z in [0, t]; the port faces -Z, onto the
    socket): the kit's outline proportions about the screw pattern (pattern (px, py), m; default the kit's 33 x 27 times
    scale), the corner radius at the kit's 8 / 34 of the short side, grown where a counterbore's lip would fall under
    1 mm; four counterbored heads at the pattern's corners, from the top face"""
    px, py = pattern if pattern is not None else (SM40['pattern'][0] * scale, SM40['pattern'][1] * scale)
    t = thickness if thickness is not None else SM40['thickness'] * max(scale, 0.5)
    hx = 0.5 * px * SM40['outline'][0] / SM40['pattern'][0]
    hy = 0.5 * py * SM40['outline'][1] / SM40['pattern'][1]
    hole = (0.5 * px, 0.5 * py)
    chosen = None
    for size in sorted(ISO4762, key=lambda s: -ISO4762[s][0]):
        if ISO4762[size][1] > FOOT_HEAD * 2.0 * hy + 1e-12 and size != FASTENER_MIN:   # the kit's M2 on 34 mm
            continue
        if t < screw_depth(size) - 1e-12 and thickness is not None:
            continue
        if 2.0 * hole[1] - 2.0 * cb_radius(size) < LIP:
            continue
        chosen = size
        break
    if chosen is None:
        raise KitPartError('kit.fastener_min', f'{name}: pattern {px / MM:.1f} x {py / MM:.1f} mm holds no ISO 4762 '
                           f'size down to {FASTENER_MIN}')
    t = max(t, screw_depth(chosen))
    need = cb_radius(chosen) + LIP
    grow = 0.0
    rc = SM40['corner'] / SM40['outline'][1] * 2.0 * hy
    while _rrect_edge(hx + grow, hy + grow, rc, hole) < need - 1e-9:
        grow += 0.05 * MM
    hx, hy = hx + grow, hy + grow
    b = _brk(t)
    per = max(8, sides(rc) // 4 * 8)                              # the high's polygon: dense (its sagitta << the low's)
    core = SD.Program.section_core(_rrect(hx, hy, rc, per), b)
    heads = []
    with part.piece(name, mat):
        part.add('psweep', np.array([frame.p((0, 0, b)), frame.p((0, 0, t - b))]), core, rho=b, normal=frame.R[:, 0],
                 name=name)
        part.lows.append(dict(piece=len(part.pieces) - 1, kind='extrude', frame_o=frame.o, R=frame.R, hx=hx, hy=hy,
                              rc=rc, z0=0.0, z1=t, b=b, sides=sides(rc), call=0))
        top = frame.sub((0.0, 0.0, t))
        for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
            heads.append(counterbore(part, top, (sx * hole[0], sy * hole[1]), chosen, t))
    for h in heads:
        h()
    part.port(f'{name}_base', 'SM40' if abs(scale - 1.0) < 1e-9 and pattern is None else 'mount_rect', frame, -1.0)
    part.ports[-1]['pattern'] = [px, py]
    part.report[name] = dict(outline_mm=[2 * hx / MM, 2 * hy / MM], t_mm=t / MM, corner_mm=rc / MM, screw=chosen,
                             grown_mm=grow / MM, pattern_mm=[px / MM, py / MM],
                             edge_mm=_rrect_edge(hx, hy, rc, hole) / MM, sides_corner=sides(rc))
    return t


# ============================================================================================ joint stack
def joint_stack(part, frame, dims, kind='roll', length=None, glow=False, name='stack'):
    """a revolute JOINT STACK on a socket: the input flange over the frame's z = 0 plane (its heads on the mating face,
    the port facing -Z), then
      'roll'   the stator (paint, the kit's taper, cast rounds), the seal on its top 1 mm proud (gasket), the 1 mm gap,
               the output flange on the hollow spindle (accent; the bore = the pilot: cables through it); axis = Z. glow:
               an inlay ring (69) in a groove round the stator's straight band
      'pitch'  the bell housing (the kit's, revolved; its bore faces flat), cross-bored along X with its axis R over the
               base, a bright insert in each side pocket, the dark hollow spindle through them, the bright output collar
               2.0 mm off the -X face, the spindle standing past it; axis = X
    Diameters from the interface radius (STACK ratios), gaps absolute. Writes the ports (input, output) and the report"""
    R, Rb, n, Rp = _check_dims(dims)
    od = 2.0 * R
    flip = Frame(frame.o, -frame.R[:, 2], frame.R[:, 0])          # the input flange: its body over the plane
    t = flange_face(part, flip, dims, name=f'{name} input flange')
    part.ports[-1]['normal'] = (-frame.R[:, 2]).tolist()
    part.ports[-1]['name'] = f'{name}_input'
    r_sp = STACK['spindle'] * R
    r_sp = max(r_sp, Rp + 1.0 * MM)                               # a spindle wall of 1 mm at least
    rep = dict(kind=kind, r_spindle_mm=r_sp / MM, r_bore_mm=Rp / MM)
    if kind == 'roll':
        # the stator (the kit forearm's drive stator, measured: r 32 straight for 6 of its 33 mm, a taper to r 30 by
        # 27 mm, straight to its top), cast rounds at the taper's ends and its top rim
        L = length if length is not None else STACK['stator_len'] * od
        r_s = STACK['stator'] * R
        r_t = STACK['stator_top'] * r_s
        z0 = t + GAP['press']
        z1 = z0 + L                                               # the stator's top face
        r_in = r_sp + GAP['bore']
        b = _brk(r_s - r_in)
        za, zb = z0 + STACK['stator_taper'][0] * L, z0 + STACK['stator_taper'][1] * L
        outline = [(r_in + b, z0), (r_s, z0), (r_s, za), (r_t, zb), (r_t, z1), (r_in, z1)]
        rad = [0.0, b, 3.0 * CAST_ROUND, 3.0 * CAST_ROUND, CAST_ROUND, 0.0]
        prof = np.vstack([[(r_in, z0 + b)], _fillet(outline, rad)])
        low = np.vstack([[(r_in, z0 + b)], _fillet(outline, rad, sag=0.03 * MM)])
        with part.piece(f'{name} stator', 'cyb_paint'):
            part.lathe(frame, prof, low_profile=low, low_sag=0.03 * MM)
            if glow:                                              # the inlay groove in the straight band
                zg = 0.5 * (z0 + za)
                gw, gd = 1.2 * MM, 0.6 * MM
                part.lathe(frame, [(r_s - gd, zg - gw / 2), (r_s + 1 * MM, zg - gw / 2), (r_s + 1 * MM, zg + gw / 2),
                                   (r_s - gd, zg + gw / 2)], op=SD.SUBTRACT, low=False, name='glow groove')
        if glow:
            with part.piece(f'{name} glow inlay', 'cyb_glow'):
                e = 0.05 * MM
                part.lathe(frame, [(r_s - gd - 0.1 * MM, zg - gw / 2 + e), (r_s - 0.15 * MM, zg - gw / 2 + e),
                                   (r_s - 0.15 * MM, zg + gw / 2 - e), (r_s - gd - 0.1 * MM, zg + gw / 2 - e)])
        # the seal (the kit's axial seal: r 21-31 x 5 on the stator's r 30 top, 1 mm proud of it): elastomer, its
        # inner edge 1 mm clear of the spindle, soft rounds
        s_len = STACK['seal_len'] * od
        r_seal = STACK['seal_od'] * r_s
        ri_s = max(STACK['seal_id'] * R, r_sp + GAP['seal'])
        zs0, zs1 = z1 + GAP['press'], z1 + s_len
        sr = min(SOFT_ROUND, 0.3 * (r_seal - ri_s), 0.3 * s_len)
        sp = [(ri_s, zs0), (r_seal - sr, zs0)] + _arc((r_seal - sr, zs0 + sr), sr, -0.5 * math.pi, 0.0, 4)[1:] + \
            _arc((r_seal - sr, zs1 - sr), sr, 0.0, 0.5 * math.pi, 4) + \
            _arc((ri_s + sr, zs1 - sr), sr, 0.5 * math.pi, math.pi, 4)[1:]
        with part.piece(f'{name} seal', 'cyb_gasket'):
            part.lathe(frame, sp)
        zf = zs1 + GAP['seal'] + t                                 # the output face
        out = frame.sub((0.0, 0.0, zf))
        flange_face(part, out, dims, thickness=t, name=f'{name} output flange')
        part.ports[-1]['name'] = f'{name}_output'
        with part.piece(f'{name} spindle', 'cyb_paint_accent'):
            part.lathe(frame, [(Rp, z0 + 1.0 * MM), (r_sp, z0 + 1.0 * MM), (r_sp, zf - t - GAP['press']),
                               (Rp, zf - t - GAP['press'])])
        rep.update(stator_r_mm=r_s / MM, stator_top_r_mm=r_t / MM, seal_od_mm=2 * r_seal / MM,
                   seal_proud_mm=(r_seal - r_t) / MM, seal_gap_mm=GAP['seal'] / MM, length_mm=zf / MM,
                   steps=dict(flange_to_stator=1.0 - r_s / R, seal_over_stator_top=r_seal / r_t - 1.0))
    elif kind == 'pitch':
        # the housing: the kit's bell revolved about the socket's normal, its two bore faces cut flat at +-hx (a smooth
        # cut, HOUSING_EDGE; the low clips the revolved bell to the planes, so the edge's blend is left to the bake: see
        # facet_check), the bore's axis R over its base
        s_ = R / 35.0
        hx = STACK['housing_x'] * R
        zb0 = t + GAP['press']
        zc = zb0 + STACK['bell_axis'] * s_
        bell = [(r_ * s_, zb0 + z_ * s_) for r_, z_ in STACK['bell']]   # s_ = R / 35 mm: metres per kit mm
        outline = [(0.0, zb0)] + bell + [(0.0, bell[-1][1])]
        rad = [0.0, _brk(1.0), 0.4 * R, 0.5 * R, 0.4 * R, 0.25 * R, 0.0]
        prof = _fillet(outline, rad)
        hy = max(r_ for r_, _ in bell)
        hz = 0.5 * (bell[-1][1] - zb0)
        r_ins = STACK['insert'] * R
        L_ins = STACK['insert_len'] * od
        pocket = STACK['pocket'] * od
        r_col, L_col = STACK['collar'] * R, STACK['collar_len'] * od
        X = (1.0, 0.0, 0.0)
        with part.piece(f'{name} housing', 'cyb_paint'):
            part.lathe(frame, prof, low_profile=_fillet(outline, rad, sag=0.03 * MM), low_sag=0.03 * MM)
            part.lows[-1]['clip_x'] = hx
            part.lows[-1]['clip_k'] = HOUSING_EDGE
            part.add('roundbox', frame.p((0.0, 0.0, 0.5 * (zb0 + bell[-1][1]))), (hx, 2.0 * R, 2.0 * R), r=0.0,
                     axes=frame.R, op=SD.INTERSECT, k=HOUSING_EDGE, name='bore faces')
            # the side pockets (the inserts' seats), then the through bore for the spindle
            for sgn in (1.0, -1.0):
                part.lathe(frame, [(0.0, sgn * (hx - pocket - L_ins)), (r_ins + GAP['press'], sgn * (hx - pocket - L_ins)),
                                   (r_ins + GAP['press'], sgn * (hx + 1 * MM)), (0.0, sgn * (hx + 1 * MM))],
                           centre=(0.0, 0.0, zc), axis=X, op=SD.SUBTRACT, low=False, name='insert seat')
                b = _brk(1.0 * MM)
                part.lathe(frame, [(0.0, sgn * (hx - b - 1 * MM)), (r_ins + GAP['press'] + 1 * MM, sgn * (hx - b - 1 * MM)),
                                   (r_ins + GAP['press'] + b + 1 * MM, sgn * (hx + 0.0 * MM)),
                                   (0.0, sgn * (hx + 0.0 * MM))],
                           centre=(0.0, 0.0, zc), axis=X, op=SD.SUBTRACT, low=False, name='pocket mouth')
            part.lathe(frame, [(0.0, -hx - 1 * MM), (r_sp + GAP['bore'], -hx - 1 * MM), (r_sp + GAP['bore'], hx + 1 * MM),
                               (0.0, hx + 1 * MM)], centre=(0.0, 0.0, zc), axis=X, op=SD.SUBTRACT, low=False,
                       name='bore')
        for sgn, nm in ((1.0, 'closed'), (-1.0, 'output')):
            y0, y1 = sgn * (hx - pocket - L_ins), sgn * (hx - pocket)
            lo_, hi_ = min(y0, y1), max(y0, y1)
            b = _brk(r_ins - r_sp - GAP['bore'])
            with part.piece(f'{name} insert {nm}', 'cyb_titanium', repeat='insert'):
                ri = r_sp + GAP['bore']
                part.lathe(frame, [(ri, lo_ + b), (ri + b, lo_), (r_ins - b, lo_), (r_ins, lo_ + b), (r_ins, hi_ - b),
                                   (r_ins - b, hi_), (ri + b, hi_), (ri, hi_ - b)], centre=(0.0, 0.0, zc), axis=X)
        # the spindle: from inside the closed insert to past the collar; the collar 2.0 mm off the -X face
        xc1 = -hx - GAP['collar']
        xc0 = xc1 - L_col
        x_end = xc0 - 0.12 * od
        x_in = hx - pocket - 0.5 * L_ins
        b = _brk(r_sp - Rp)
        with part.piece(f'{name} spindle', 'cyb_paint_accent'):
            part.lathe(frame, [(Rp, x_end + b), (Rp + b, x_end), (r_sp - b, x_end), (r_sp, x_end + b), (r_sp, x_in - b),
                               (r_sp - b, x_in), (Rp + b, x_in), (Rp, x_in - b)], centre=(0.0, 0.0, zc), axis=X)
        b = _brk(r_col - r_sp)
        with part.piece(f'{name} collar', 'cyb_titanium'):
            ri = r_sp + GAP['press']
            part.lathe(frame, [(ri, xc0 + b), (ri + b, xc0), (r_col - b, xc0), (r_col, xc0 + b), (r_col, xc1 - b),
                               (r_col - b, xc1), (ri + b, xc1), (ri, xc1 - b)], centre=(0.0, 0.0, zc), axis=X)
        of = frame.sub((x_end, 0.0, zc), z=(-1.0, 0.0, 0.0), x=(0.0, 0.0, 1.0))
        part.port(f'{name}_output', 'spindle', of, 1.0)
        part.ports[-1].update(radius_m=r_sp, pilot_radius_m=Rp, joint_axis=frame.R[:, 0].tolist())
        rep.update(housing_mm=[2 * hx / MM, 2 * hy / MM, 2 * hz / MM], insert_r_mm=r_ins / MM, collar_r_mm=r_col / MM,
                   collar_gap_mm=GAP['collar'] / MM, bore_gap_mm=GAP['bore'] / MM)
    else:
        raise KitPartError('kit.stack', f'kind {kind!r}: roll or pitch')
    part.report[name] = rep
    return part


# ============================================================================================ the low
def extrude_sides(lw, sag=HERO_SAG):
    """an extruded low's (corner sides per full turn, segments per edge round): the rounds take a tenth of the sagitta,
    the corners the rest"""
    b = lw['b']
    m_r = 1
    while b * (1.0 - math.cos(0.25 * math.pi / m_r)) > 0.1 * sag:
        m_r += 1
    return sides(lw['rc'], sag - b * (1.0 - math.cos(0.25 * math.pi / m_r))), m_r


def low_mesh(part, sag=HERO_SAG):
    """every recorded low: the lathe profiles revolved at sides(r_max of the profile, sag), the extruded outlines with
    sides(corner radius, sag) per full turn of corner. Returns V, F, UV (per island: u the arc length round, v the
    profile's arc length), piece index per face, island index per face"""
    Vs, Fs, UVs, pcs, isl = [], [], [], [], []
    off = 0
    for li, lw in enumerate(part.lows):
        if lw['kind'] == 'lathe':
            P = lw['profile']
            n = sides(float(P[:, 0].max()), sag - lw.get('low_sag', 0.0))
            a = lw['axis']
            x = lw['x'] - a * float(lw['x'] @ a)
            if np.linalg.norm(x) < 1e-6:
                x = np.cross(a, [0.31, 0.83, 0.47])
            x = _unit(x)
            y = np.cross(a, x)
            Pc = np.vstack([P, P[:1]])
            th = np.arange(n + 1) * 2.0 * math.pi / n
            ring = np.column_stack([np.cos(th), np.sin(th)])
            V = (lw['centre'][None, None] + Pc[:, None, 0, None] * (ring[None, :, :1] * x + ring[None, :, 1:] * y)
                 + Pc[:, None, 1, None] * a)
            s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(Pc, axis=0), axis=1))])
            rmax = float(P[:, 0].max())
            U = np.stack(np.meshgrid(th * rmax, s), -1)
            rows, cols = V.shape[:2]
            idx = np.arange(rows * cols).reshape(rows, cols)
            F = []
            for i in range(rows - 1):
                if Pc[i, 0] < 1e-9 and Pc[i + 1, 0] < 1e-9:
                    continue
                for j in range(cols - 1):
                    a0, a1, b0, b1 = idx[i, j], idx[i, j + 1], idx[i + 1, j], idx[i + 1, j + 1]
                    F += [(a0, b0, a1), (a1, b0, b1)]
            V, U, F = V.reshape(-1, 3), U.reshape(-1, 2), np.asarray(F, np.int64)
            if 'clip_x' in lw:                                    # flat faces: the ring vertices pressed onto the planes
                u = (V - lw['centre']) @ x
                V = V + (np.clip(u, -lw['clip_x'], lw['clip_x']) - u)[:, None] * x
        else:
            # the extrusion: its edge rounds (rho = b) as rings (a 90 deg round's chord alone sags b (1 - cos 45) =
            # 0.117 mm at b 0.4), the corners' sides at the sagitta the rounds leave over (the two add where a round
            # turns a corner), capped by fans
            n, m_r = extrude_sides(lw, sag)
            per = max(1, n // 4)
            b = lw['b']
            rings = []
            for z, sgn in ((lw['z0'], 1.0), (lw['z1'], -1.0)):
                ang = np.linspace(0.0, 0.5 * math.pi, m_r + 1)
                for a_ in (ang if sgn > 0 else ang[::-1]):
                    ins, dz = b * (1.0 - math.sin(a_)), b * (1.0 - math.cos(a_))
                    rings.append((ins, z + sgn * dz))
            Vr, Ur = [], []
            for ins, z in rings:
                O = _rrect(lw['hx'] - ins, lw['hy'] - ins, lw['rc'] - ins, per + 1)
                O = np.vstack([O, O[:1]])
                ln = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(O, axis=0), axis=1))])
                Vr.append([lw['frame_o'] + lw['R'] @ np.array([q[0], q[1], z]) for q in O])
                Ur.append([(l_, z) for l_ in ln])
            m = len(Vr[0])
            V = np.asarray(Vr).reshape(-1, 3)
            U = np.asarray(Ur).reshape(-1, 2)
            F = []
            for i in range(len(rings) - 1):
                for j in range(m - 1):
                    a0, a1, b0, b1 = i * m + j, i * m + j + 1, (i + 1) * m + j, (i + 1) * m + j + 1
                    F += [(a0, a1, b0), (a1, b1, b0)]
            for i, flipc in ((0, True), (len(rings) - 1, False)):        # the caps: fans from each outline's centre
                c = len(V)
                V = np.vstack([V, lw['frame_o'] + lw['R'] @ np.array([0.0, 0.0, rings[i][1]])])
                U = np.vstack([U, [0.0, rings[i][1]]])
                for j in range(m - 1):
                    F.append((c, i * m + j + 1, i * m + j) if flipc else (c, i * m + j, i * m + j + 1))
            F = np.asarray(F, np.int64)
        Vs.append(V)
        Fs.append(F + off)
        UVs.append(U)
        pcs.append(np.full(len(F), lw['piece']))
        isl.append(np.full(len(F), li))
        off += len(V)
    return (np.concatenate(Vs), np.concatenate(Fs), np.concatenate(UVs), np.concatenate(pcs), np.concatenate(isl))


def facet_check(part, sag=HERO_SAG, k=6):
    """the low against its own piece's lathe (or extrusion) surface: every face sampled on a k x k barycentric grid,
    the piece's single profile primitive evaluated there. Returns per low: sides, max |d| (m), and the worst"""
    V, F, UV, pc, isl = low_mesh(part, sag)
    out = []
    w = np.array([(i / k, j / k) for i in range(k + 1) for j in range(k + 1 - i)])
    w = np.column_stack([w, 1.0 - w.sum(1)])
    for li, lw in enumerate(part.lows):
        m = isl == li
        T = V[F[m]]
        P = np.einsum('sk,fkd->fsd', w, T).reshape(-1, 3)
        calls = [lw['call']]
        excl = 0
        if 'clip_x' in lw:              # against the bell cut flat; the smooth cut's band (2 k) is the bake's
            calls = [lw['call'], lw['call'] + 1]
            u = np.abs((P - lw['centre']) @ _unit(lw['x'] - lw['axis'] * float(lw['x'] @ lw['axis'])))
            keep = u < lw['clip_x'] - 2.0 * lw['clip_k']
            excl = float(1.0 - keep.mean())
            P = P[keep]
        d = part.piece_prog(lw['piece'], calls=calls).eval(P)
        n = sides(float(lw['profile'][:, 0].max()), sag - lw.get('low_sag', 0.0)) if lw['kind'] == 'lathe' else \
            extrude_sides(lw, sag)[0]
        r = float(lw['profile'][:, 0].max()) if lw['kind'] == 'lathe' else lw['rc']
        out.append(dict(piece=part.pieces[lw['piece']]['name'], kind=lw['kind'], r_mm=r / MM, sides=n,
                        sagitta_mm=sagitta(r, n) / MM, max_dev_mm=float(np.abs(d).max()) / MM, tris=int(m.sum()),
                        excluded_share=excl))
    return out

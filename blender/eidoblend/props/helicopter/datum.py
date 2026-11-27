"""eidoblend.props.helicopter.datum: the helicopter's measured numbers (plain Python). Every part reads its places from
here, so the parts meet.

SPACE (millimetres): x AFT of the main rotor's mast (the nose at -4525), y to the aircraft's RIGHT, z UP from the
cabin's floor. The type is a UH-60M, checked against its published figures: fuselage 15.43 m, main rotor 16.36 m, tail
rotor 3.35 m, hub to hub 9.93 m, wheel base 8.84 m, track 2.705 m, cabin 3.84 m long (x -2390 .. +1440) x 2.21 wide x
1.37 high, cabin door 1.75 x 1.34. The rest was read off level side-on photographs under a 100 mm grid.

    HULL      the skin as a sections.Body: a blunt nose with a broad bill, the canopy's flat panes between their posts,
              the slab-sided cabin, the boom (keys K0 keel, K1 chine, K2 widest, K3 belt, K4 eave, K5 the windshield's
              centre post, K6 crown); HULL_BREAKS: creases across it at the windshield's foot and head
    CAVITY    the cockpit's and the cabin's hollow, a wall's thickness inside the skin, a flat floor, a ceiling
    openings  the cabin doorway, the gunner and cockpit-door windows, the windshields, the overhead and chin windows
"""

from __future__ import annotations

import math

from ..hardsurface.sections import Body

# ------------------------------------------------------------------------------------------------ stations
X_TIP = -4525.0            # the nose's foremost point (z 300)
X_FACE = -4450.0           # where the nose's blunt face begins to close
X_WS_FOOT = -3830.0        # the centre windshield's foot (z 700); it climbs at 45 degrees
X_A_FOOT = -3520.0         # the A-pillar's foot (the cockpit door's hinge post), z 740
X_WS_HEAD = -3060.0        # the windshield's head (z 1470)
X_A_HEAD = -3000.0         # the A-pillar's head
X_B_POST = -2560.0         # the cockpit door's rear edge
X_CABIN0, X_CABIN1 = -2390.0, 1440.0        # the cabin, inside
DOOR_X0, DOOR_X1, DOOR_Z0, DOOR_Z1 = -790.0, 960.0, 15.0, 1355.0   # the cabin door's opening
X_TAPER = 3000.0           # the slab sides end here
X_TAIL = 9320.0            # the hull's aft point, under the stabilator (z 505 .. 640)
W = 1180.0                 # half the cabin's outside width (2.36 m)
WALL, WALL_COCKPIT = 75.0, 50.0             # skin to liner: the cabin is 2.21 m wide inside
CEIL = 1370.0              # the cabin's ceiling
BELLY = -160.0
POST_Y = 245.0             # the two centre posts of the windshield: the centre pane about 0.4 m of glass, each side 0.62
# the A-pillar: the side pane's outer lower corner stands LOWER than the centre pane's foot (the sill falls away to each
# side), level with the cockpit door window's sill
A_FOOT, A_HEAD = (X_A_FOOT, 1080.0, 640.0), (X_A_HEAD, 900.0, 1470.0)
WS_FOOT, WS_HEAD = (X_WS_FOOT, POST_Y, 700.0), (X_WS_HEAD, POST_Y, 1470.0)
MAST_X, MAST_TILT = 0.0, 3.0                # the mast leans 3 degrees forward
HUB_Z = 2800.0                              # the blades' plane at the hub
TAIL_HUB = (9930.0, 330.0, 2900.0)          # the tail rotor, on the pylon's RIGHT side, canted 20 degrees
MAIN_WHEEL = (-1120.0, 1352.5, -350.0)      # axle centre, one side (track 2.705 m); tyre 660 x 255
TAIL_WHEEL = (7720.0, 0.0, -495.0)          # tyre 380 x 150
GROUND = -690.0

# ------------------------------------------------------------------------------------------------ the hull's sections
# (x, [K0 .. K6], [R1 .. R5]); the nose is deep and broad under the windshields: a wide flat deck, near-upright sides
# that carry the big chin windows, and a blunt bill as wide as the nose itself, 0.2 m proud of the cheeks behind it
HULL_KEYS = [
    (X_FACE, [(0, 165), (450, 165), (590, 255), (578, 345), (470, 404), (220, 418), (0, 420)], [120, 80, 60, 70, 30]),
    (-4370, [(0, 140), (480, 140), (625, 250), (612, 345), (500, 422), (235, 442), (0, 445)], [140, 90, 70, 80, 30]),
    (-4290, [(0, 92), (520, 92), (770, 235), (752, 372), (560, 458), (260, 482), (0, 486)], [230, 170, 100, 100, 40]),
    (-4050, [(0, 30), (600, 30), (870, 250), (850, 470), (640, 572), (300, 596), (0, 600)], [300, 220, 120, 110, 50]),
    (X_WS_FOOT, [(0, -5), (700, -5), (980, 300), (965, 540), (POST_Y + 45, 693), (POST_Y, 700), (0, 700)], [360, 260, 110, 12, 12]),
    (X_A_FOOT, [(0, -50), (820, -50), (1085, 320), (1095, 590), (1080, 640), (POST_Y, 1010), (0, 1010)], [400, 280, 40, 14, 12]),
    (X_WS_HEAD, [(0, -112), (985, -112), (1162, 330), (1123, 660), (921, 1374), (POST_Y, 1470), (0, 1470)], [390, 300, 150, 14, 12]),
    (X_A_HEAD, [(0, -118), (1000, -118), (1165, 330), (1125, 660), (900, 1470), (POST_Y, 1476), (0, 1478)], [380, 300, 150, 40, 12]),
    (X_B_POST, [(0, -148), (1150, -148), (1180, 330), (1172, 720), (985, 1488), (520, 1518), (0, 1525)], [300, 250, 150, 60, 0]),
    (-2420, [(0, -155), (1172, -155), (1180, 310), (1178, 900), (1120, 1500), (580, 1526), (0, 1532)], [260, 100, 190, 100, 0]),
    (-2300, [(0, BELLY), (W, BELLY), (W, 300), (W, 950), (1150, 1505), (600, 1530), (0, 1535)], [240, 0, 200, 110, 0]),
    (X_TAPER, [(0, BELLY), (W, BELLY), (W, 300), (W, 950), (1150, 1505), (600, 1530), (0, 1535)], [240, 0, 200, 110, 0]),
    (3300, [(0, -150), (1100, -150), (1105, 300), (1105, 950), (1075, 1500), (560, 1525), (0, 1530)], [240, 0, 200, 120, 0]),
    (3650, [(0, -95), (960, -95), (975, 320), (975, 900), (930, 1425), (480, 1462), (0, 1470)], [240, 100, 220, 140, 0]),
    (4000, [(0, -55), (760, -55), (790, 330), (790, 870), (720, 1335), (390, 1385), (0, 1395)], [230, 150, 230, 150, 0]),
    (4500, [(0, -25), (470, -25), (540, 380), (540, 800), (470, 1215), (260, 1280), (0, 1290)], [220, 200, 250, 160, 0]),
    (5000, [(0, -5), (370, -5), (435, 400), (435, 760), (370, 1120), (200, 1186), (0, 1195)], [200, 200, 240, 150, 0]),
    (6000, [(0, 78), (290, 78), (350, 430), (350, 730), (300, 1020), (165, 1077), (0, 1085)], [170, 170, 200, 130, 0]),
    (7000, [(0, 140), (235, 140), (285, 440), (285, 690), (245, 912), (135, 963), (0, 970)], [140, 140, 160, 110, 0]),
    (7700, [(0, 205), (200, 205), (245, 460), (245, 660), (210, 840), (115, 884), (0, 890)], [120, 120, 130, 95, 0]),
    (8500, [(0, 320), (150, 320), (190, 540), (190, 700), (160, 850), (90, 893), (0, 900)], [90, 90, 100, 70, 0]),
    (9000, [(0, 430), (75, 430), (100, 600), (100, 730), (85, 840), (50, 865), (0, 870)], [50, 50, 50, 40, 0]),
    (X_TAIL, [(0, 505), (9, 505), (12, 550), (12, 585), (10, 620), (6, 636), (0, 640)], [5, 5, 5, 5, 0]),
]
# creases ACROSS the hull: the windshield's foot and head (crown and posts), the A-pillar's foot and head (the eave)
HULL_BREAKS = {'K6z': [X_WS_FOOT, X_WS_HEAD], 'K5': [X_WS_FOOT, X_WS_HEAD], 'K4': [X_WS_FOOT, X_A_FOOT, X_A_HEAD]}
N_EDGE, N_CORNER = [8, 5, 6, 8, 8, 5], [14, 8, 6, 10, 4]
HULL = Body(HULL_KEYS, N_EDGE, N_CORNER, HULL_BREAKS)
HULL_MUST = [X_WS_FOOT, X_A_FOOT, X_WS_HEAD, X_A_HEAD, X_B_POST, -2420.0, -2300.0, X_TAPER, 3300.0, DOOR_X0, DOOR_X1]


def nose_rings(n=9):
    """the bill's lip: the X_FACE section closed in HEIGHT as an ellipse closes, its width kept (a broad rounded lip):
    [(x, height's scale, width's scale)] from the tip"""
    out = []
    for i in range(n, 0, -1):
        th = math.radians(80.0 * i / n)
        out.append((X_FACE - (X_FACE - X_TIP) * math.sin(th), math.cos(th), 1.0 - 0.16 * (1.0 - math.cos(th))))
    return out


# ------------------------------------------------------------------------------------------------ the hollow inside
def _lin(x, x0, v0, x1, v1):
    t = min(1.0, max(0.0, (x - x0) / (x1 - x0)))
    return v0 + (v1 - v0) * t


CAV_X0, CAV_X1 = -4020.0, X_CABIN1


def floor_z(x):
    """the floor: the cabin's and the pilots' at 0; forward of their seats it drops to the pedals' well in the nose"""
    k = HULL.ctrl(x)[0][0][1]
    return _lin(x, -3620.0, k + 70.0, -3350.0, 0.0)


def ceil_z(x):
    return _lin(x, -2600.0, HULL.ctrl(x)[0][6][1] - 50.0, X_CABIN0, CEIL)


def wall_t(x):
    return _lin(x, -2700.0, WALL_COCKPIT, X_CABIN0, WALL)


def cavity_ctrl(x):
    """the liner's control polygon at x: the hull's, a wall's thickness inside, cut off flat at the floor and ceiling"""
    K, R = HULL.ctrl(x)
    t, f, c = wall_t(x), floor_z(x), ceil_z(x)
    y_floor = (HULL.side_at(x, f + 60.0) or K[2][0]) - t - 10.0
    k2 = (K[2][0] - t, max(K[2][1], f + 150.0))
    k1 = (min(y_floor, k2[0]), f)
    k3 = (K[3][0] - t, max(K[3][1], k2[1] + 50.0))
    k4 = (K[4][0] - t, min(K[4][1] - 0.8 * t, c))
    k5 = (min(K[5][0], k4[0] - 30.0), min(K[5][1] - t, c))
    k6 = (0.0, min(K[6][1] - t, c))
    return [(0.0, f), k1, k2, k3, k4, k5, k6], [40.0, R[1] * 0.5, R[2], max(R[3] - t, 20.0), R[4]]


class _Cavity(Body):
    def __init__(self):                                       # (its numbers come from the hull's, station by station)
        self.n_edge, self.n_corner = [8, 4, 5, 6, 8, 5], [5, 5, 5, 8, 4]

    def ctrl(self, x):
        return cavity_ctrl(x)


CAVITY = _Cavity()

# ------------------------------------------------------------------------------------------------ the openings
# outlines in the side view (x, z) unless said; each is cut square through its wall and carries a pane and a frame
GUNNER_PANES = [(-1740.0, 560.0, -1440.0, 1290.0), (-1360.0, 560.0, -1060.0, 1290.0)]        # x0, z0, x1, z1; corners 90
DOOR_WINDOWS = [(210.0, 570.0, 730.0, 1260.0), (1010.0, 570.0, 1530.0, 1260.0)]             # in the cabin door, from its front edge
COCKPIT_DOOR_WINDOW = [(-3415, 700), (-3005, 1355), (-2965, 1392), (-2700, 1392), (-2640, 1335), (-2640, 760), (-2700, 700)]
COCKPIT_DOOR = [(-3490, 150), (-3490, 610), (-3470, 650), (-3035, 1345), (-2985, 1440), (-2600, 1440), (-2575, 1415), (-2575, 150), (-2610, 110), (-3455, 110)]
OVERHEAD_WINDOW = [(-2985, 300), (-2985, 815), (-2650, 885), (-2650, 300)]                   # plan (x, y), the right one
CENTRE_PANE_HALF, PANE_INSET = 203.0, 42.0
# the chin window: most of the nose's lower side from its shoulder round under its chine, back to the door's hinge post
CHIN = {'at': (-3800.0, 830.0, 260.0), 'normal': (-0.22, 0.80, -0.56),
        'outline': [(-330, -40), (-290, 190), (-180, 305), (0, 330), (300, 340), (322, 310), (322, -250), (240, -330), (-100, -330), (-270, -230)]}

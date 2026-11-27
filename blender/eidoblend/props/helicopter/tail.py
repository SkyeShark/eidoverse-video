"""eidoblend.props.helicopter.tail: the pylon, the stabilator, the tail rotor.

    the pylon       a swept fin of aerofoil section: its leading edge from (8150, 1000) to (9500, 2700); its trailing edge
                    in two runs with a step between them at z 2090; the tail rotor's gearbox under a domed cover on its
                    left face at the top, the rotor itself on its right; the drive shaft's cover up its leading edge; the
                    intermediate gearbox's bump at its foot; a beacon on top
    the stabilator  one slab through the fin's foot, 4.38 m across, tapered, a symmetrical 14 per cent section
    the tail rotor  four blades as two crossed beams, 3.35 m across, its shaft canted 20 degrees up: retention plates,
                    the pitch beam and its four links. Its hub turns about the shaft under the Empty 'tail_rotor' (its
                    local Y), itself under 'tail_rotor_cant'.
"""

from __future__ import annotations

import math

import bpy
from mathutils import Vector

from ..hardsurface import masses as hs, skins as bt
from ..hardsurface.sections import stations

PY_Z0, PY_Z1 = 860.0, 3035.0


def py_le(z):
    return 8150.0 + (z - 1000.0) * 0.794


def py_te(z):
    lo = 9640.0 + (z - 1020.0) * 0.364
    hi = 10170.0 + (z - 2100.0) * 0.62
    t = min(1.0, max(0.0, (z - 2060.0) / 55.0))
    return lo + (hi - lo) * t * t * (3.0 - 2.0 * t)


def foil_ring(x_le, x_te, half, z, n=26, blunt=0.0):
    """a horizontal section of the fin at height z: a symmetrical aerofoil from x_le to x_te, `half` thick each side"""
    c = x_te - x_le
    up = []
    for i in range(n + 1):
        s = 0.5 * (1.0 - math.cos(math.pi * i / n))            # bunched at both edges
        yt = 10.0 * (0.2969 * math.sqrt(s) - 0.1260 * s - 0.3516 * s * s + 0.2843 * s ** 3 - 0.1036 * s ** 4)    # 1 at its thickest
        up.append((x_le + c * s, max(blunt, half * yt)))
    return [(x, y, z) for x, y in up] + [(x, -y, z) for x, y in up[-2:0:-1]]


def ellipsoid(name, centre, radii, m, seg=28):
    rl = []
    for j in range(1, seg // 2):
        a = math.pi * j / (seg // 2)
        rl.append([(centre[0] + radii[0] * math.sin(a) * math.cos(2 * math.pi * i / seg), centre[1] + radii[1] * math.sin(a) * math.sin(2 * math.pi * i / seg),
                    centre[2] + radii[2] * math.cos(a)) for i in range(seg)])
    return bt.finish_smooth(hs.rings(name, rl), m)


def build(b):
    CLAY, GLASS, STEEL = b.clay, b.glass, b.steel
    rings_ = []
    for z in stations(PY_Z0, PY_Z1, 55.0, [2060.0, 2115.0]):
        half = 150.0 - 45.0 * (z - PY_Z0) / (PY_Z1 - PY_Z0)
        rings_.append(foil_ring(py_le(z), py_te(z), half, z, blunt=5.0))
    for k in range(1, 6):                                     # its top, turned over
        th = math.radians(86.0 * k / 5)
        z = PY_Z1 + 70.0 * math.sin(th)
        mid = (py_le(PY_Z1) + py_te(PY_Z1)) / 2.0
        rings_.append([(mid + (x - mid) * (0.55 + 0.45 * math.cos(th)), y * math.cos(th), z) for x, y, _z in foil_ring(py_le(PY_Z1), py_te(PY_Z1), 105.0, z, blunt=5.0)])
    bt.finish_smooth(hs.rings('tail_pylon', rings_), CLAY)
    ellipsoid('tail_gearbox_cover', (9990.0, -95.0, 2865.0), (470.0, 215.0, 285.0), CLAY)
    ellipsoid('intermediate_gearbox_bump', (8360.0, 0.0, 1015.0), (300.0, 150.0, 140.0), CLAY)
    # the drive shaft's cover up the leading edge, a hand ahead of it
    le_path = [Vector((py_le(z) - 18.0, 0.0, z)) for z in stations(1180.0, 2640.0, 90.0)]
    bt.finish_smooth(hs.sweep('pylon_shaft_cover', le_path, [(62.0 * math.cos(math.radians(a)), 62.0 * math.sin(math.radians(a))) for a in range(0, 360, 20)],
                              up=(1.0, 0.0, 0.0)), CLAY)
    # the beacon on the fin's top
    bx = (py_le(PY_Z1) + py_te(PY_Z1)) / 2.0 + 130.0
    hs.finish(hs.revolve('beacon_base', [(0.0, 0.0), (38.0, 0.0), (38.0, 26.0), (30.0, 34.0), (0.0, 34.0)], at=(bx, 0.0, PY_Z1 + 62.0), seg=24), 0.0, CLAY)
    hs.finish(hs.revolve('beacon_lens', [(0.0, 34.0), (27.0, 34.0), (27.0, 78.0), (20.0, 96.0), (8.0, 104.0), (0.0, 105.0)], at=(bx, 0.0, PY_Z1 + 62.0), seg=24), 0.0, GLASS)

    # ---------------------------------------------------------------- the stabilator
    ST_Q, ST_Z, ST_INC = 9330.0, 1030.0, math.radians(5.0)   # its quarter-chord line, its height, trailing edge down
    st = []
    ys = sorted({-2190.0 + 4380.0 * i / 48 for i in range(49)} | {s_ * (2190.0 - e_) for s_ in (-1, 1) for e_ in (4.0, 12.0, 24.0, 40.0)})
    for y in ys:
        edge = min(y + 2190.0, 2190.0 - y)                    # from the nearer tip
        r = 1.0 if edge > 45.0 else math.sqrt(max(0.02, 1.0 - (1.0 - edge / 45.0) ** 2))
        c = (1100.0 - 250.0 * abs(y) / 2190.0)
        ring = []
        n = 22
        for i in range(2 * n):
            s = 0.5 * (1.0 - math.cos(math.pi * (i if i <= n else 2 * n - i) / n))
            yt = 0.14 * c * 5.0 * (0.2969 * math.sqrt(s) - 0.1260 * s - 0.3516 * s * s + 0.2843 * s ** 3 - 0.1036 * s ** 4) * r
            dx, dz = (s - 0.25) * c * (0.6 + 0.4 * r), (yt if i <= n else -yt)
            ring.append((ST_Q + dx * math.cos(ST_INC) + dz * math.sin(ST_INC), y, ST_Z - dx * math.sin(ST_INC) + dz * math.cos(ST_INC)))
        st.append(ring)
    bt.finish_smooth(hs.rings('stabilator', st), CLAY)

    # ---------------------------------------------------------------- the tail rotor (its own frame: Y out along the shaft)
    CANT = math.radians(20.0)
    T_O = Vector((9930.0, 0.0, 2865.0))                       # the shaft leaves the fin here
    T_Y = Vector((0.0, math.cos(CANT), math.sin(CANT)))       # out to the right and up
    T_X = Vector((1.0, 0.0, 0.0))
    T_Z = T_X.cross(T_Y)
    T_HUB = T_O + T_Y * 330.0
    cant = hs.empty('tail_rotor_cant', T_HUB)
    cant.rotation_euler = (CANT, 0.0, 0.0)
    bpy.context.view_layer.update()
    trh = hs.empty('tail_rotor', T_HUB)
    trh.parent = cant
    trh.matrix_parent_inverse = cant.matrix_world.inverted()
    trh.rotation_euler = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()

    def TW(x, y, z):
        """a point of the tail rotor's own frame (x aft, y out along the shaft, z up the disc) in the aircraft's"""
        return T_HUB + T_X * x + T_Y * y + T_Z * z

    def t_revolve(name, profile, m, seg=32, parent=None):
        """a profile [(radius, y along the shaft)] turned about the shaft"""
        return hs.finish(hs.revolve(name, profile, at=T_HUB, axis=T_Y, seg=seg), 0.0, m, parent=parent)

    t_revolve('tail_rotor_shaft', [(0.0, -330.0), (46.0, -330.0), (46.0, -60.0), (58.0, -52.0), (58.0, -30.0), (0.0, -30.0)], STEEL)
    t_revolve('tail_rotor_hub', [(0.0, -34.0), (150.0, -34.0), (156.0, -28.0), (156.0, -16.0), (72.0, -12.0), (72.0, 12.0), (156.0, 16.0),
                                 (156.0, 28.0), (150.0, 34.0), (0.0, 34.0)], CLAY, seg=48, parent=trh)
    t_revolve('tail_rotor_pitch_shaft', [(0.0, 34.0), (24.0, 34.0), (24.0, 168.0), (40.0, 172.0), (40.0, 196.0), (22.0, 214.0), (0.0, 216.0)], STEEL, parent=trh)
    bolts, links, beams = [], [], []
    for k in range(4):
        a = math.radians(90.0 * k + 32.0)
        er = lambda r_, off=0.0, y=0.0, a=a: TW(r_ * math.cos(a) - off * math.sin(a), y, r_ * math.sin(a) + off * math.cos(a))    # noqa: E731
        # the blade: a flex beam's root fairing widening to the full chord, a thin symmetrical section, a squared tip
        rl = []
        t_rs = [240.0, 300.0, 380.0, 470.0] + [470.0 + (1676.0 - 470.0) * q / 14 for q in range(1, 15)]
        for r_ in t_rs:
            c = 120.0 + (247.0 - 120.0) * min(1.0, max(0.0, (r_ - 240.0) / 230.0)) ** 0.8
            th = 30.0 - 8.0 * min(1.0, (r_ - 240.0) / 230.0)
            if r_ > 1650.0:
                th *= 0.6
            ring = []
            n = 12
            for i in range(2 * n):
                s = 0.5 * (1.0 - math.cos(math.pi * (i if i <= n else 2 * n - i) / n))
                yt = th * 5.0 * (0.2969 * math.sqrt(s) - 0.1260 * s - 0.3516 * s * s + 0.2843 * s ** 3 - 0.1036 * s ** 4)
                ring.append(er(r_, (0.3 - s) * c, yt if i <= n else -yt))
            rl.append(ring)
        tb = hs.rings(f'tail_blade_{k}', rl)
        bt.blade_data(tb, 24, lambda i: 0.5 * (1.0 - math.cos(math.pi * (i if i <= 12 else 24 - i) / 12)),
                      lambda j, t_rs=t_rs: (t_rs[min(j, len(t_rs) - 1)] - 240.0) / (1676.0 - 240.0))
        bt.finish_smooth(tb, CLAY, parent=trh)
        for r_ in (112.0,):                                   # the plates' bolts
            for da in (-0.5, 0.5):
                p = TW(r_ * math.cos(a + da), 34.0, r_ * math.sin(a + da))
                bolts.append([hs.circle(p, T_Y, 11.0, 0.0, 6), hs.circle(p, T_Y, 11.0, 9.0, 6)])
        # the pitch link: from the pitch beam's arm out at the shaft's end down to the blade's horn at its trailing edge
        p0, p1 = TW(150.0 * math.cos(a - 0.55), 184.0, 150.0 * math.sin(a - 0.55)), er(300.0, 95.0, 14.0)
        links.append([hs.circle(p0, (p1 - p0), 8.0, 0.0, 8), hs.circle(p0, (p1 - p0), 8.0, (p1 - p0).length, 8)])
        arm = [TW(18.0 * math.cos(a - 0.55 + q) + 0.0, y, 18.0 * math.sin(a - 0.55 + q)) for q, y in ((1.57, 176.0), (1.57, 192.0), (-1.57, 192.0), (-1.57, 176.0))]
        tip = [TW(150.0 * math.cos(a - 0.55) + 12.0 * math.cos(a - 0.55 + q), y, 150.0 * math.sin(a - 0.55) + 12.0 * math.sin(a - 0.55 + q))
               for q, y in ((1.57, 177.0), (1.57, 191.0), (-1.57, 191.0), (-1.57, 177.0))]
        beams.append([arm, tip])
    hs.finish(hs.skins('tail_rotor_bolts', bolts), 0.0, STEEL, parent=trh)
    hs.finish(hs.skins('tail_rotor_pitch_links', links), 0.0, STEEL, parent=trh)
    hs.finish(hs.skins('tail_rotor_pitch_beam', beams), 0.0, CLAY, parent=trh)

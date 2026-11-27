"""The hall's skin and what hangs on it (private to the set): the walls, the dock's door, the services, the guards, the
yard beyond the door.

Called by hall.look with X, a namespace of what the look holds at that point: M (materials by name), L (the layout),
OBJ, MESH, the collections C_*, new_ob, swap_mesh, import_model, say, the hall's numbers (HX0, HX1, HY0, HY1, RZ, WT).
Every part is a real section: profiled sheet with its ribs, precast panels with their joints, rolled steel with its
flanges, plates with their bolts, channels, tubes with their bends.
"""
import math
import time

import bpy
import numpy as np
from mathutils import Vector

from . import _kit as kit
from ._kit import MB, c_section, i_section

PI = math.pi
RAD = math.radians
DADO_Z = 2.4          # the precast dado's top: the profiled liner stands on it
DADO_T = 0.09         # how far the dado stands into the hall
RIB = 0.040           # how far the liner's crowns stand into the hall
TRAY_Z = 5.9          # the cable tray's bottom


# ====================================================================================================== profiled sheet
def ribbed_sheet(name, runs, material, pitch=0.2, depth=0.028, stand=0.012):
    """Profiled steel sheet as ONE open mesh: trapezoidal ribs every `pitch`, `depth` high. A run is a rectangle of
    sheet: (o, d, n, e, u0, u1, t0, t1) = origin, the direction across the ribs, the direction the ribs stand toward,
    the direction the ribs run along (unit 3-vectors), and its extent across (u) and along (t). The ribs are phased by
    u from the origin, so runs that share an origin and a direction line up. UV = (u, t) in metres."""
    prof = ((0.0, 0.0), (0.10, 0.0), (0.125, 1.0), (0.175, 1.0))            # (place in a period, 0 = pan, 1 = crown)

    def dep(u):
        f = (u / pitch) % 1.0 * 0.2
        pts = prof + ((0.2, 0.0),)
        for (a, da), (b, db) in zip(pts[:-1], pts[1:]):
            if a <= f <= b:
                return da + (db - da) * (f - a) / (b - a)
        return 0.0

    verts, faces, uvs = [], [], []
    for o, d, n, e, u0, u1, t0, t1 in runs:
        o, d, n, e = Vector(o), Vector(d), Vector(n), Vector(e)
        us = [u0]
        k = math.floor(u0 / pitch)
        while k * pitch < u1:
            for off, _dd in prof:
                u = (k + off / 0.2) * pitch
                if u0 + 1e-6 < u < u1 - 1e-6:
                    us.append(u)
            k += 1
        us.append(u1)
        flip = d.cross(e).dot(n) < 0
        base = len(verts)
        for u in us:
            p = o + d * u + n * (stand + depth * dep(u))
            verts.append(tuple(p + e * t0))
            verts.append(tuple(p + e * t1))
            uvs += [(u, t0), (u, t1)]
        for i in range(len(us) - 1):
            a, b, c, dd = base + 2 * i, base + 2 * i + 2, base + 2 * i + 3, base + 2 * i + 1
            faces.append((a, dd, c, b) if flip else (a, b, c, dd))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    layer = me.uv_layers.new(name='UVMap')
    lv = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get('vertex_index', lv)
    layer.data.foreach_set('uv', np.array(uvs, np.float32)[lv].ravel())
    me.materials.append(material)
    me.update()
    return me


# ====================================================================================================== the walls
def walls(X):
    """the dado (precast panels, 6 m, a real joint between each), the liner above it (profiled sheet), the flashing
    between them, the portal frames (columns with base plates and haunches, rafters), the gable posts; the roof's deck as
    profiled sheet on its purlins"""
    M, L = X.M, X.L
    HX0, HX1, HY0, HY1, RZ = X.HX0, X.HX1, X.HY0, X.HY1, X.RZ
    dx0, dx1 = L['dock']['door_x']
    dh = L['dock']['door_h']
    fa, fb = dx0 - 0.24, dx1 + 0.24                                          # the door frame's outer edges
    Z = (0, 0, 1)
    # ---- the liner
    runs = [((HX1, 0, 0), (0, 1, 0), (-1, 0, 0), Z, HY0, HY1, DADO_Z, RZ),
            ((HX0, 0, 0), (0, 1, 0), (1, 0, 0), Z, HY0, HY1, DADO_Z, RZ),
            ((0, HY0, 0), (1, 0, 0), (0, 1, 0), Z, HX0, HX1, DADO_Z, RZ),
            ((0, HY1, 0), (1, 0, 0), (0, -1, 0), Z, HX0, fa, DADO_Z, RZ),
            ((0, HY1, 0), (1, 0, 0), (0, -1, 0), Z, fb, HX1, DADO_Z, RZ),
            ((0, HY1, 0), (1, 0, 0), (0, -1, 0), Z, fa, fb, dh + 0.25, RZ)]
    X.new_ob('hall_liner', ribbed_sheet('hall_liner', runs, M['hall_wall_panel']), X.C_SHELL)
    # ---- the roof's deck: ribs along X, hanging 45 mm under the slab, carried by the purlins
    me = ribbed_sheet('hall_roof_deck', [((0, 0, RZ), (0, 1, 0), (0, 0, -1), (1, 0, 0), HY0, HY1, HX0, HX1)], M['hall_roof'],
                      pitch=0.25, depth=0.045, stand=0.004)
    X.new_ob('hall_roof_deck', me, X.C_SHELL)
    mb = MB()
    mb.span((HX0 - X.WT, HY0 - X.WT, RZ), (HX1 + X.WT, HY1 + X.WT, RZ + 0.25))
    slab = mb.mesh('hall_roof_new', [M['hall_roof']])
    kit.uv_metres(slab)
    X.swap_mesh(X.OBJ['hall_roof'], slab)                                    # the layout's slab without its box beams
    # ---- the dado
    mb = MB()
    t = DADO_T

    def panels(a, b, place):
        """6 m panels from a to b (a < b), the first joint at a; place(u0, u1) adds the box"""
        u = a
        while u < b - 0.05:
            v = min(u + 6.0, b)
            if b - v < 1.2:                                                  # no sliver at the end: the last panel takes it
                v = b
            place(u + 0.01, v - 0.01)
            u = v

    panels(-HY1, -HY0, lambda a, b: mb.span((HX1 - t, -b, 0.0), (HX1, -a, DADO_Z)))            # joints counted from the dock end
    panels(-HY1, -HY0, lambda a, b: mb.span((HX0, -b, 0.0), (HX0 + t, -a, DADO_Z)))
    panels(HX0 + t, HX1 - t, lambda a, b: mb.span((a, HY0, 0.0), (b, HY0 + t, DADO_Z)))
    panels(-fa, -(HX0 + t), lambda a, b: mb.span((-b, HY1 - t, 0.0), (-a, HY1, DADO_Z)))      # from the door westward
    panels(fb, HX1 - t, lambda a, b: mb.span((a, HY1 - t, 0.0), (b, HY1, DADO_Z)))
    dado = X.new_ob('hall_dado', mb.mesh('hall_dado', [M['wall_concrete']]), X.C_SHELL)
    kit.finish(dado.data, bevel=0.008, inset=0.035, cavity=0.10, ground=0.0, log=X.say)
    # ---- the flashing on the dado's top: a folded galvanized trim with a drip
    mb = MB()

    def trim(o, d, n, u0, u1):
        o, d, n = Vector(o), Vector(d), Vector(n)
        for (n0, n1, z0, z1) in ((0.004, t + 0.012, DADO_Z, DADO_Z + 0.0025), (t + 0.0095, t + 0.012, DADO_Z - 0.022, DADO_Z),
                                 (0.004, 0.0065, DADO_Z, DADO_Z + 0.06)):
            p, q = o + d * u0 + n * n0, o + d * u1 + n * n1
            mb.span((min(p.x, q.x), min(p.y, q.y), z0), (max(p.x, q.x), max(p.y, q.y), z1))

    trim((HX1, 0, 0), (0, 1, 0), (-1, 0, 0), HY0, HY1)
    trim((HX0, 0, 0), (0, 1, 0), (1, 0, 0), HY0, HY1)
    trim((0, HY0, 0), (1, 0, 0), (0, 1, 0), HX0, HX1)
    trim((0, HY1, 0), (1, 0, 0), (0, -1, 0), HX0, fa)
    trim((0, HY1, 0), (1, 0, 0), (0, -1, 0), fb, HX1)
    fl = X.new_ob('hall_dado_flashing', mb.mesh('hall_dado_flashing', [M['steel_galv']]), X.C_SHELL)
    kit.finish(fl.data, bevel=0.0008, inset=0.006, cavity=0.0, log=X.say)
    # ---- the frames: columns at the side walls under every rafter, the rafters, posts on the gables
    mb = MB()
    COL = i_section(0.30, 0.20, 0.012, 0.008, r=0.012)
    RAF = i_section(0.40, 0.20, 0.014, 0.009, r=0.012)
    z_raf = RZ - 0.60                                                        # the rafters' underside (the purlins sit on them)
    frames_y = []
    y = HY1 - 6.0
    while y > HY0 + 1.0:
        frames_y.append(y)
        y -= 12.0
    for y in frames_y:
        mb.prism(RAF, HX0, HX1, 'x', 0, at=(y, z_raf + 0.20))
        for wx, s in ((HX1, -1), (HX0, 1)):                                  # s: the way into the hall
            mb.prism([(wx + v, y + u) for u, v in COL], 0.02, z_raf, 'z', 0)
            mb.span((min(wx, wx + s * 0.27), y - 0.17, 0.0), (max(wx, wx + s * 0.27), y + 0.17, 0.02), 0)    # the base plate
            for sy in (-1, 1):
                mb.bolt((wx + s * 0.215, y + sy * 0.125, 0.0265), 0.015, 0.012, 'z', 1)
                mb.cyl((wx + s * 0.215, y + sy * 0.125, 0.04), 0.007, 0.016, 'z', 8, 1)
            # the haunch: a tapered web and its flange, from the column's face out along the rafter
            xa, xb = wx + s * 0.15, wx + s * 1.55
            mb.prism([(xa, z_raf), (xb, z_raf), (xa, z_raf - 0.55)], y - 0.0045, y + 0.0045, 'y', 0)
            mb.bar((xa, y, z_raf - 0.55), (xb, y, z_raf), 0.20, 0.014, 0)
            mb.span((min(xa, xa + s * 0.012), y - 0.10, z_raf - 0.60), (max(xa, xa + s * 0.012), y + 0.10, z_raf), 0)   # the end plate
            for bz in (z_raf - 0.08, z_raf - 0.22, z_raf - 0.40):
                for sy in (-1, 1):
                    mb.bolt((xa + s * 0.018, y + sy * 0.065, bz), 0.013, 0.011, 'x', 1, washer=False)
    posts = [float(x) for x in np.arange(fa - 3.16, HX0 + 3.0, -6.0)] + [fb + 1.6]
    for wy, s, xs in ((HY1, -1, posts), (HY0, 1, posts + [-1.6])):
        for x in xs:
            mb.prism([(x + u, wy + v) for u, v in COL], 0.02, RZ - 0.21, 'z', 0)
            mb.span((x - 0.17, min(wy, wy + s * 0.27), 0.0), (x + 0.17, max(wy, wy + s * 0.27), 0.02), 0)
            for sx in (-1, 1):
                mb.bolt((x + sx * 0.125, wy + s * 0.215, 0.0265), 0.015, 0.012, 'z', 1)
    st = X.new_ob('hall_structure', mb.mesh('hall_structure', [M['column_paint'], M['steel_galv']]), X.C_SHELL)
    kit.finish(st.data, bevel=0.004, inset=0.022, cavity=0.10, ground=0.0, log=X.say)
    X.say('   walls: liner %d faces, dado %d, structure %d (frames at %d rafters)'
          % (len(X.MESH['hall_liner'].polygons), len(dado.data.polygons), len(st.data.polygons), len(frames_y)))
    return frames_y


# ====================================================================================================== the dock door
def dock_door(X):
    """the dock's roller shutter, open: its frame, the two guides fixed to the frame's face, the last laths hanging under
    the coil, the coil on its barrel between two bracket plates, the drive and its hand chain (west end: the returns
    cage stands at the east), the bottom rail and seal; the bollards; corner guards on the jambs; the control station
    beside it"""
    M, L = X.M, X.L
    HY1, WT = X.HY1, X.WT
    dx0, dx1 = L['dock']['door_x']
    dh = L['dock']['door_h']
    FR, GALV, CURT, RUB, YEL, DARK, TEAL = range(7)
    mb = MB()
    yf = HY1 - 0.06                                                          # the frame's face toward the hall
    for x in (dx0 - 0.12, dx1 + 0.12):                                       # the frame, where the layout put it
        mb.span((x - 0.12, yf, 0), (x + 0.12, HY1 + WT + 0.06, dh + 0.25), FR)
    mb.span((dx0 - 0.24, yf, dh), (dx1 + 0.24, HY1 + WT + 0.06, dh + 0.25), FR)
    for x in (dx0 - 0.12, dx1 + 0.12):                                       # its feet: plates and anchors
        mb.span((x - 0.19, yf - 0.11, 0.0), (x + 0.19, yf, 0.012), GALV)
        for sx in (-1, 1):
            mb.bolt((x + sx * 0.15, yf - 0.06, 0.018), 0.012, 0.01, 'z', GALV)
    yc = yf - 0.048                                                          # the curtain's plane
    for s, x in ((1, dx0 - 0.075), (-1, dx1 + 0.075)):                       # the guides: channels, open toward the opening
        mb.prism([(x + s * u, yc + v) for u, v in c_section(0.085, 0.08, 0.004)], 0.0, dh + 0.50, 'z', GALV)
        for z in np.arange(0.35, dh + 0.3, 0.75):                            # their cleats on the frame
            mb.box((x - s * 0.03, yc + 0.02, float(z)), (0.06, 0.05, 0.06), GALV)
            mb.bolt((x - s * 0.03, yc - 0.008, float(z)), 0.009, 0.007, 'y', GALV)
    lath = [(-0.007, 0.0), (0.007, 0.0), (0.012, 0.022), (0.012, 0.072), (0.007, 0.097), (-0.007, 0.097), (-0.002, 0.072), (-0.002, 0.022)]
    yr, zr, rr = yc - 0.29, dh + 0.62, 0.28                                  # the coil: the curtain leaves it at its +Y side
    xl0, xl1 = dx0 - 0.068, dx1 + 0.068
    z = dh - 0.10
    while z < zr:                                                            # the laths between the bottom rail and the coil
        mb.prism(lath, xl0, xl1, 'x', CURT, at=(yc, z))
        z += 0.1
    mb.span((xl0, yc - 0.03, dh - 0.16), (xl1, yc + 0.03, dh - 0.10), GALV)                   # the bottom rail
    mb.span((xl0, yc - 0.022, dh - 0.19), (xl1, yc + 0.022, dh - 0.16), RUB)                  # its seal
    n_l = 28                                                                 # the coil: every lath a lobe
    coil = []
    for i in range(n_l * 3):
        a = 2 * PI * i / (n_l * 3)
        r = rr - (0.009 if i % 3 == 0 else 0.0)
        coil.append((math.cos(a) * r, math.sin(a) * r))
    mb.prism(coil, dx0 - 0.10, dx1 + 0.10, 'x', CURT, at=(yr, zr))
    mb.cyl(((dx0 + dx1) / 2, yr, zr), 0.055, dx1 - dx0 + 0.56, 'x', 20, DARK)                # the barrel's shaft
    yw = HY1 - RIB - 0.002                                                   # just proud of the liner's crowns
    for x in (dx0 - 0.24, dx1 + 0.24):                                       # the bracket plates, bolted through to the wall
        mb.span((x - 0.006, yr - 0.34, zr - 0.34), (x + 0.006, yw, zr + 0.34), GALV)
        mb.span((x - 0.06, yw - 0.012, zr - 0.34), (x + 0.06, yw, zr + 0.34), GALV)            # its flange
        for bz in (-0.26, 0.0, 0.26):
            for sx in (-1, 1):
                mb.bolt((x + sx * 0.038, yw - 0.0165, zr + bz), 0.011, 0.009, 'y', GALV)
        mb.cyl((x, yr, zr), 0.085, 0.05, 'x', 20, DARK)                                       # the bearing
    xm, sd = dx0 - 0.24, -1                                                  # the drive, outboard of the west bracket
    mb.cyl((xm + sd * 0.22, yr, zr), 0.085, 0.34, 'x', 24, DARK)                              # the motor
    for i in range(9):                                                       # its cooling fins
        mb.cyl((xm + sd * (0.10 + 0.03 * i), yr, zr), 0.094, 0.006, 'x', 24, DARK)
    mb.box((xm + sd * 0.07, yr, zr - 0.02), (0.11, 0.19, 0.24), DARK)                         # the gearbox
    mb.box((xm + sd * 0.24, yr - 0.10, zr + 0.06), (0.11, 0.07, 0.09), DARK)                  # the terminal box
    xc_ = xm + sd * 0.42
    mb.cyl((xc_, yr, zr), 0.12, 0.022, 'x', 28, GALV)                                         # the hand chain's wheel
    mb.cyl((xc_, yr, zr), 0.03, 0.05, 'x', 12, DARK)
    for sy in (-1, 1):                                                       # the hand chain, hanging to within reach
        mb.rod((xc_, yr + sy * 0.115, zr), (xc_, yr + sy * 0.115, 1.25), 0.0045, 6, GALV)
    mb.tube(mb.arc((xc_, yr, 1.25), 0.115, PI, 2 * PI, 'x', 8), 0.0045, 6, GALV)
    for x in (dx0 - 0.5, dx1 + 0.5):                                         # the bollards
        mb.cyl((x, HY1 - 1.2, 0.56), 0.085, 1.10, 'z', 24, YEL)
        mb.cyl((x, HY1 - 1.2, 1.125), 0.085, 0.03, 'z', 24, YEL, r2=0.06)
        mb.cyl((x, HY1 - 1.2, 0.006), 0.16, 0.012, 'z', 24, GALV)
        for k in range(4):
            a = PI / 4 + k * PI / 2
            mb.bolt((x + math.cos(a) * 0.125, HY1 - 1.2 + math.sin(a) * 0.125, 0.0175), 0.012, 0.01, 'z', GALV)
    # corner guards: an angle over each jamb's arris, from the floor to 1.5 m, where trucks clip the frame
    mb.prism([(dx0 - 0.20, yf - 0.006), (dx0 + 0.006, yf - 0.006), (dx0 + 0.006, HY1 + 0.03), (dx0, HY1 + 0.03), (dx0, yf), (dx0 - 0.20, yf)],
             0.012, 1.5, 'z', YEL)
    mb.prism([(dx1 + 0.20, yf - 0.006), (dx1 + 0.20, yf), (dx1, yf), (dx1, HY1 + 0.03), (dx1 - 0.006, HY1 + 0.03), (dx1 - 0.006, yf - 0.006)],
             0.012, 1.5, 'z', YEL)
    cx, cz = dx0 - 1.05, 1.32                                                # the control station: up, stop, down
    ys = HY1 - DADO_T
    mb.box((cx, ys - 0.035, cz), (0.10, 0.07, 0.26), TEAL)
    for k, dz in enumerate((0.075, 0.0, -0.075)):
        mb.cyl((cx, ys - 0.072, cz + dz), 0.019, 0.006, 'y', 24, RUB)
        mb.cyl((cx, ys - 0.078, cz + dz), 0.014, 0.008, 'y', 24, GALV if k == 1 else DARK)
    mats_ = [M['column_paint'], M['steel_galv'], M['curtain_white'], M['rubber_black'], M['hazard_yellow'], M['steel_dark'], M['plastic_teal']]
    me = mb.mesh('dock_door_new', mats_)
    kit.finish(me, bevel=0.003, inset=0.016, cavity=0.08, ground=0.0, log=X.say)
    X.swap_mesh(X.OBJ['dock_door'], me)
    return {'control': (cx, ys - 0.035, cz + 0.13), 'motor': (xm + sd * 0.24, yr - 0.10, zr + 0.105)}


# ====================================================================================================== services
def services(X, door):
    """the cable tray round the hall on its brackets (a 3 m module, instanced), the conduits down from it with their
    saddles, and CC0 fittings (Poly Haven, fetched by ID: a distribution board, a call point, two cameras)"""
    M, L = X.M, X.L
    HX0, HX1, HY0, HY1 = X.HX0, X.HX1, X.HY0, X.HY1
    dx0, dx1 = L['dock']['door_x']
    GALV, RUB, GREY = 0, 1, 2
    # ---- the tray module: local +Y along the run, the wall at x = 0, the hall on -X
    mb = MB()
    xa, xb = -0.50, -0.20
    for x in (xa, xb):
        mb.span((x - 0.003, -1.5, 0.0), (x + 0.003, 1.5, 0.06), GALV)                         # side rails
        mb.span((x - 0.012, -1.5, 0.054), (x + 0.012, 1.5, 0.06), GALV)                       # their rolled tops
    y = -1.35
    while y < 1.5:
        mb.span((xa, y - 0.015, 0.006), (xb, y + 0.015, 0.024), GALV)                         # rungs
        y += 0.3
    for x, r, mi, lift in ((-0.46, 0.011, RUB, 0), (-0.435, 0.008, RUB, 0), (-0.405, 0.014, RUB, 0), (-0.37, 0.009, GREY, 0),
                           (-0.345, 0.009, GREY, 0), (-0.31, 0.016, RUB, 0), (-0.275, 0.007, GREY, 0), (-0.255, 0.007, RUB, 0),
                           (-0.42, 0.007, GREY, 0.024)):
        zc = 0.024 + r + lift
        mb.tube([(x, -1.5, zc), (x + 0.004, -0.5, zc), (x - 0.003, 0.5, zc), (x, 1.5, zc)], r, 8, mi, caps=False)   # the cables
    mb.span((-0.045, -0.02, -0.30), (0.0, 0.02, 0.12), GALV)                                  # the bracket: a strut on the wall,
    mb.span((-0.54, -0.018, -0.045), (-0.045, 0.018, 0.0), GALV)                              # its arm,
    mb.bar((-0.48, 0, -0.045), (-0.045, 0, -0.28), 0.03, 0.006, GALV)                         # its stay
    for bz in (-0.25, 0.08):
        mb.bolt((-0.049, 0.0, bz), 0.009, 0.007, 'x', GALV)
    tray_me = mb.mesh('cable_tray', [M['steel_galv'], M['rubber_black'], M['cable_grey']])
    kit.finish(tray_me, bevel=0.0012, inset=0.006, cavity=0.035, log=X.say)
    tray_ob = X.new_ob('asset_cable_tray', tray_me, X.C_LOOK)
    east = [(HX1, float(y), TRAY_Z) for y in np.arange(HY1 - 2.1, HY0 + 1.6, -3.0)]
    kit.instance_on_points('cable_tray_east', east, tray_ob, X.C_SHELL, 0.0)
    north = [(float(x), HY1, TRAY_Z) for x in np.arange(HX1 - 2.0, HX0 + 1.6, -3.0)]
    kit.instance_on_points('cable_tray_dock_wall', north, tray_ob, X.C_SHELL, PI / 2)
    # ---- conduits: 20 mm tube on saddles; they stand off the dado, step back over its flashing, and bend into the tray
    mb = MB()
    R = 0.0105
    off_lo, off_hi = DADO_T + 0.02 + R, RIB + 0.012 + R                      # a conduit's axis from the wall: low, high

    def saddle(c, w, off):
        """a spacer from the wall and a strap over the conduit at c; w: the unit step toward the wall"""
        c, w = Vector(c), Vector(w)
        ax = abs(w.x) > 0.5
        reach = off - (DADO_T if c.z < DADO_Z else RIB)
        b = c + w * (reach / 2)
        mb.box(tuple(b), (reach if ax else 0.03, 0.03 if ax else reach, 0.02), GALV)
        s = c - w * (R + 0.002)
        mb.box(tuple(s), (0.004 if ax else 0.038, 0.038 if ax else 0.004, 0.02), GALV)

    def drop(x, y, z0, w):
        """a conduit from z0 up the wall into the tray; (x, y): the wall's face there; w: the unit step toward the wall"""
        w = Vector((w[0], w[1], 0.0))
        p0 = Vector((x, y, 0.0)) - w * off_lo
        p1 = Vector((x, y, 0.0)) - w * off_hi
        top = TRAY_Z + 0.11
        pts = [(p0.x, p0.y, z0), (p0.x, p0.y, DADO_Z + 0.05)]
        for i in range(1, 6):                                                # the step back over the flashing
            f = i / 6.0
            q = p0 + (p1 - p0) * (0.5 - 0.5 * math.cos(PI * f))
            pts.append((q.x, q.y, DADO_Z + 0.05 + 0.16 * f))
        pts.append((p1.x, p1.y, DADO_Z + 0.21))
        pts.append((p1.x, p1.y, top - 0.09))
        for i in range(1, 7):                                                # the bend over into the tray
            a = (PI / 2) * i / 6
            q = p1 - w * (0.09 * (1.0 - math.cos(a)))
            pts.append((q.x, q.y, top - 0.09 + 0.09 * math.sin(a)))
        q = p1 - w * 0.17
        pts.append((q.x, q.y, top))
        mb.tube(pts, R, 10, GALV)
        z = z0 + 0.25
        while z < DADO_Z - 0.1:
            saddle((p0.x, p0.y, z), w, off_lo)
            z += 0.9
        z = DADO_Z + 0.45
        while z < top - 0.3:
            saddle((p1.x, p1.y, z), w, off_hi)
            z += 0.95

    N, E = (0, 1, 0), (1, 0, 0)                                              # toward the dock wall, toward the east wall
    cx, cy, cz = door['control']
    drop(cx, HY1, cz, N)                                                     # the door's control station
    mx, my, mz = door['motor']                                               # the drive's lead: a flexible conduit down from the tray
    mb.tube([(mx, my + 0.015, TRAY_Z + 0.03), (mx, my + 0.015, TRAY_Z - 0.12), (mx, my, mz + 0.16), (mx, my, mz)], 0.011, 10, RUB)
    pb = (HX1, 16.4, 1.5)                                                    # the distribution board on the east wall
    for dy in (-0.07, 0.07):
        drop(HX1, pb[1] + dy, pb[2] + 0.25, E)
    fa_ = (dx0 - 1.75, HY1, 1.42)                                            # the call point west of the door
    drop(fa_[0], HY1, fa_[2] + 0.07, N)
    cam1 = ((dx0 + dx1) / 2 + 1.3, HY1, 6.75)                                # a camera over the door, looking down the aisle
    yq = HY1 - off_hi
    mb.tube([(cam1[0], yq, cam1[2] - 0.05), (cam1[0], yq, TRAY_Z + 0.20)] + [
        (cam1[0], yq - 0.10 * (1 - math.cos(a)), TRAY_Z + 0.20 - 0.10 * math.sin(a)) for a in np.linspace(0.26, PI / 2, 6)]
        + [(cam1[0], yq - 0.22, TRAY_Z + 0.10)], R, 10, GALV)
    cam2 = (HX1, 8.6, 6.75)                                                  # and one over the office's side of the aisle
    xq = HX1 - off_hi
    mb.tube([(xq, cam2[1], cam2[2] - 0.05), (xq, cam2[1], TRAY_Z + 0.20)] + [
        (xq - 0.10 * (1 - math.cos(a)), cam2[1], TRAY_Z + 0.20 - 0.10 * math.sin(a)) for a in np.linspace(0.26, PI / 2, 6)]
        + [(xq - 0.22, cam2[1], TRAY_Z + 0.10)], R, 10, GALV)
    con = X.new_ob('hall_conduits', mb.mesh('hall_conduits', [M['steel_galv'], M['rubber_black']]), X.C_SHELL)
    kit.finish(con.data, bevel=0.0012, inset=0.006, cavity=0.03, log=X.say)

    # ---- the CC0 fittings
    def fit(asset, loc, rz):
        obs = X.import_model(asset)
        k = len([o for o in X.OBJ if o.name.startswith('fit_' + asset)])
        root = bpy.data.objects.new('fit_%s_%d' % (asset, k), None)
        X.C_SHELL.objects.link(root)
        root.empty_display_size = 0.1
        root.location, root.rotation_euler = loc, (0.0, 0.0, rz)
        for o in obs:
            X.C_SHELL.objects.link(o)
            if o.parent is None or o.parent not in obs:
                o.parent = root
        return root

    fit('power_box_01', (HX1 - DADO_T - 0.048, pb[1], pb[2]), -PI / 2)
    fit('fire_alarm', (fa_[0], HY1 - DADO_T - 0.013, fa_[2]), 0.0)
    fit('security_camera_01', (cam1[0], HY1 - RIB - 0.28, cam1[2]), 0.0)
    fit('security_camera_01', (HX1 - RIB - 0.28, cam2[1], cam2[2]), -PI / 2)
    X.say('   services: tray modules %d + %d, conduits %d faces' % (len(east), len(north), len(con.data.polygons)))


# ====================================================================================================== guards
def u_guard(mb, cx, cy, half, reach, h, open_to, t=0.006, mi=0, galv=1):
    """a U of plate round a post's foot: `half` its inner half width, `reach` how far its two arms run back from the
    post's middle, open toward the unit step `open_to`; two feet with an anchor each"""
    o = Vector((open_to[0], open_to[1]))
    s = Vector((-o.y, o.x))
    c = Vector((cx, cy))

    def P(a, b):                                                             # a toward the closed face, b across
        q = c - o * a + s * b
        return (q.x, q.y)

    poly = [P(-reach, -half - t), P(half + t, -half - t), P(half + t, half + t), P(-reach, half + t),
            P(-reach, half), P(half, half), P(half, -half), P(-reach, -half)]
    mb.prism(poly, 0.008, h, 'z', mi)
    for b in (-1, 1):
        q = c + s * (b * (half + t + 0.04))
        mb.box((q.x, q.y, 0.004), (0.08, 0.08, 0.008), mi)
        mb.bolt((q.x, q.y, 0.013), 0.010, 0.008, 'z', galv)


def guards(X, rows):
    """what keeps trucks off the steel: a U guard at the foot of every rack upright that faces an aisle (one asset,
    instanced with the frames), a barrier across the end of the rack rows at the dock end, a guard round every crane post
    (in the line module: every line has them)"""
    M, L = X.M, X.L
    mb = MB()
    u_guard(mb, -0.045, 0.0, 0.054, 0.035, 0.40, (-1, 0))
    g_me = mb.mesh('rack_upright_guard', [M['safety_yellow'], M['steel_galv']])
    kit.finish(g_me, bevel=0.002, inset=0.012, cavity=0.06, ground=0.0, log=X.say)
    g_ob = X.new_ob('asset_rack_upright_guard', g_me, X.C_LOOK)
    n = 0
    for name, pts, rz in rows:
        kit.instance_on_points('rack_%s_guards' % name, pts, g_ob, X.C_RACKS, rz)
        n += len(pts)
    mb = MB()
    ends = [(-6.62, -4.18, 13.8 + 0.42), (6.08, 7.20, 12.0 + 0.42)]
    for xa, xb, y in ends:
        for x in (xa, xb):
            mb.box((x, y, 0.22), (0.10, 0.10, 0.42), 0)                      # the posts
            mb.box((x, y, 0.445), (0.11, 0.11, 0.012), 0)
            mb.box((x, y, 0.005), (0.22, 0.22, 0.010), 0)
            for sx in (-1, 1):
                for sy in (-1, 1):
                    mb.bolt((x + sx * 0.08, y + sy * 0.08, 0.015), 0.011, 0.009, 'z', 1)
        for z in (0.34, 0.16):
            mb.rod((xa + 0.05, y, z), (xb - 0.05, y, z), 0.038, 16, 0)       # the rails
    b = X.new_ob('rack_end_barriers', mb.mesh('rack_end_barriers', [M['safety_yellow'], M['steel_galv']]), X.C_RACKS)
    kit.finish(b.data, bevel=0.003, inset=0.014, cavity=0.06, ground=0.0, log=X.say)
    GA = L['gantry']
    mb = MB()
    for rx, posts, o in zip(GA['rail_x'], (GA['post_y_west'], GA['post_y_east']), ((-1, 0), (1, 0))):
        for py in posts:
            u_guard(mb, rx, py, 0.20, 0.20, 0.45, o, t=0.008)
    pg = X.new_ob('line_crane_post_guards', mb.mesh('line_crane_post_guards', [M['hazard_yellow'], M['steel_galv']]), X.C_MODULE)
    kit.finish(pg.data, bevel=0.003, inset=0.014, cavity=0.06, ground=0.0, log=X.say)
    X.say('   guards: %d upright guards, %d end barriers, crane post guards on every line' % (n, len(ends)))


# ====================================================================================================== the yard
def trailer_mesh(M):
    """a box trailer seen from its rear (y = 0, toward -Y) and its sides: body, door leaves with their lock rods and
    hinges, the under-run bar, three axles, the landing gear"""
    W, G_, D_, R_, = 0, 1, 2, 3
    mb = MB()
    mb.span((-1.275, 0.04, 1.15), (1.275, 13.6, 4.0), W)
    for x in (-1.235, 1.235):
        mb.span((x - 0.045, 0.0, 1.10), (x + 0.045, 0.06, 4.02), D_)                          # the rear frame's posts
    mb.span((-1.28, 0.0, 3.93), (1.28, 0.06, 4.03), D_)
    mb.span((-1.28, 0.0, 1.06), (1.28, 0.06, 1.17), D_)
    for s in (-1, 1):
        mb.span((min(s * 0.012, s * 1.185), -0.022, 1.19), (max(s * 0.012, s * 1.185), 0.0, 3.91), W)   # a door leaf
        for x in (0.33, 0.86):
            mb.rod((s * x, -0.045, 1.14), (s * x, -0.045, 3.96), 0.016, 10, G_)                # lock rods
            mb.box((s * x, -0.04, 1.95), (0.05, 0.03, 0.26), G_)                               # their handles' keeps
            for z in (1.16, 3.94):
                mb.box((s * x, -0.035, z), (0.07, 0.05, 0.05), G_)                             # cams
        for z in (1.5, 2.3, 3.1, 3.7):
            mb.box((s * 1.2, -0.03, z), (0.09, 0.03, 0.12), G_)                                # hinges
    for x in (-1.275, 1.275):                                                                 # side rails top and bottom
        for z in (1.19, 3.97):
            mb.box((x, 6.82, z), (0.02, 13.56, 0.08), G_)
    mb.span((-1.2, 0.03, 0.46), (1.2, 0.13, 0.58), D_)                                        # the under-run bar
    for x in (-0.6, 0.6):
        mb.span((x - 0.04, 0.05, 0.58), (x + 0.04, 0.13, 1.06), D_)
    for x in (-0.5, 0.5):
        mb.span((x - 0.06, 0.3, 0.82), (x + 0.06, 13.3, 1.15), D_)                            # the chassis rails
    for y in (1.7, 3.05, 4.4):
        mb.cyl((0, y, 0.52), 0.06, 2.1, 'x', 10, D_)                                          # axle
        for x in (-1.06, 1.06):
            mb.cyl((x, y, 0.52), 0.52, 0.36, 'x', 28, R_)                                     # tyre
            mb.cyl((x + (0.16 if x > 0 else -0.16), y, 0.52), 0.27, 0.06, 'x', 20, G_)         # rim
    for x in (-0.75, 0.75):                                                                   # mudflaps behind the last axle
        mb.span((x - 0.3, 1.02, 0.25), (x + 0.3, 1.035, 0.9), R_)
    for x in (-0.55, 0.55):                                                                   # landing gear
        mb.span((x - 0.06, 11.1, 0.12), (x + 0.06, 11.22, 1.0), D_)
        mb.span((x - 0.14, 11.02, 0.0), (x + 0.14, 11.30, 0.03), D_)
    return mb.mesh('yard_trailer', [M['trailer_white'], M['steel_galv'], M['steel_dark'], M['rubber_black']])


def yard(X, trees=True):
    """outdoors, as the dock door sees it: the apron (the layout's), a kerb and a chain-link fence (a CC0 kit's panels,
    instanced), trailers parked at it, three lamp masts, open ground beyond, and SeedThree trees (eidoblend.trees:
    five individuals grown from their species and seeds, placed three rows deep behind the fence as a shelter belt
    stands round a yard). trees=False leaves them out"""
    M = X.M
    FY = 62.0
    mb = MB()
    mb.quad([(-420.0, FY + 0.35, 0.03), (420.0, FY + 0.35, 0.03), (420.0, 700.0, 0.03), (-420.0, 700.0, 0.03)])
    X.new_ob('yard_field', mb.mesh('yard_field', [M['yard_field']], recalc=False), X.C_DOCK)
    mb = MB()
    mb.span((-90.0, FY + 0.05, 0.0), (60.0, FY + 0.33, 0.13))
    kerb = X.new_ob('yard_kerb', mb.mesh('yard_kerb', [M['wall_concrete']]), X.C_DOCK)
    kit.finish(kerb.data, bevel=0.012, inset=0.04, cavity=0.0, log=X.say)
    tr = trailer_mesh(M)
    kit.finish(tr, bevel=0.006, inset=0.03, cavity=0.10, ground=0.0, log=X.say)
    for i, (x, y, yaw) in enumerate(((-24.6, 43.0, 0.0), (-20.9, 43.4, 0.0), (-12.8, 44.0, 0.0), (7.4, 45.5, 0.0), (-34.5, 46.5, RAD(6.0)))):
        o = X.new_ob('yard_trailer_%d' % i, tr, X.C_DOCK, (x, y, 0.0), yaw)
        o['note'] = 'a parked box trailer: its rear doors toward the dock'
    mb = MB()
    for x in (-31.0, -16.5, 9.5):                                            # lamp masts (none on the door's own axis)
        mb.cyl((x, FY - 0.6, 5.5), 0.11, 11.0, 'z', 16, 0, r2=0.06)
        mb.cyl((x, FY - 0.6, 0.012), 0.2, 0.024, 'z', 16, 0)
        mb.tube([(x, FY - 0.6, 10.9), (x, FY - 0.6, 11.25), (x, FY - 0.9, 11.42), (x, FY - 1.9, 11.48)], 0.04, 10, 0)
        mb.box((x, FY - 2.15, 11.46), (0.3, 0.62, 0.09), 1)
    masts = X.new_ob('yard_masts', mb.mesh('yard_masts', [M['steel_galv'], M['steel_dark']]), X.C_DOCK)
    kit.finish(masts.data, bevel=0.004, inset=0.02, cavity=0.0, log=X.say)
    # the fence: the CC0 kit's double panel (1.914 m) along the kerb
    obs = X.import_model('modular_chainlink_fence')
    panel = next(o for o in obs if o.name.startswith('modular_chainlink_fence_double'))
    panel.parent = None
    for o in obs:
        if o is not panel:
            bpy.data.objects.remove(o)
    X.C_LOOK.objects.link(panel)
    panel.location = (0, 0, 0)
    for m in panel.data.materials:
        m.surface_render_method = 'DITHERED'
        if 'wire' in m.name and m.node_tree:
            # at 40 m the mesh's opacity map averages out to a solid sheet: the link's cover is thinned to what wire of
            # that gauge covers, so the yard and the trees show through it
            bs = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if bs is not None and bs.inputs['Alpha'].is_linked:
                src = bs.inputs['Alpha'].links[0].from_socket
                mul = m.node_tree.nodes.new('ShaderNodeMath')
                mul.operation = 'MULTIPLY'
                mul.inputs[1].default_value = 0.32
                m.node_tree.links.new(src, mul.inputs[0])
                m.node_tree.links.new(mul.outputs[0], bs.inputs['Alpha'])
    pts = [(float(x), FY, 0.13) for x in np.arange(-88.0, 59.0, 1.914)]
    kit.instance_on_points('yard_fence', pts, panel, X.C_DOCK, 0.0)
    trees_out = []
    if trees:
        trees_out = _trees(X)
    X.trees = trees_out
    # the yard stays out of the volume probes' bake (840 x 640 m of field in it spreads the bake's surfels over the yard
    # and leaves the hall inside darker); the apron by the door stays in
    for o in X.C_DOCK.objects:
        if o.name.startswith('yard_'):
            o.hide_probe_volume = True
    X.say('   yard: field, kerb, 5 trailers, 3 masts, %d fence panels, %d SeedThree trees' % (len(pts), len(trees_out)))


def _trees(X):
    """five SeedThree individuals grown out of sight, duplicated three rows deep behind the fence, 48 to 90 m from the
    door. THE SUN'S WAY INTO THE DOOR STAYS OPEN: every ray that comes in under the lintel passes lower than 21 m at the
    first row, and a crown there turns the warm patch on the hall's floor into leaf shade whose flecks do not settle at
    16 samples; so no crown stands in that corridor (the narrow aspens stand at its edge, the wide trees beyond)"""
    from ....trees import make_seed_tree
    rng = np.random.default_rng(11)
    grown = []
    for sp, seed, dials in (('tulipPoplar', 4107, {'height': 25.0}), ('americanSycamore', 2203, {'height': 21.0}),
                            ('redMaple', 905, {'height': 16.5}), ('quakingAspen', 618, {'height': 15.0}),
                            ('whiteOak', 1737, {'height': 17.0})):
        t0 = time.time()
        t = make_seed_tree(species=sp, seed=seed, dials=dials, location=(0.0, 400.0, 0.0))
        grown.append(t)
        X.say('   tree %s seed %d: %s in %.1f s' % (sp, seed, {k: t['stats']['summary'].get(k) for k in
                                                              ('heightMeters', 'widthMeters', 'lod0Triangles')}, time.time() - t0))
    az = math.tan(RAD(X.L['dock']['sun']['azimuth_off_axis']))
    door = X.L['dock']['door_x']
    door_c, door_h = 0.5 * (door[0] + door[1]), 0.5 * (door[1] - door[0])

    def in_the_sun(x, y, crown_r):
        return abs(x - (door_c + (y - X.HY1) * az)) < door_h + 1.0 + 0.8 * crown_r

    radius = [0.5 * t['stats']['summary']['widthMeters'] for t in grown]
    narrow = min(range(len(grown)), key=lambda i: radius[i])
    trees, left_out = [], 0
    rows = ((72.0, 2.5, -62.0, 30.0, 8.6), (86.0, 4.0, -70.0, 36.0, 9.4), (106.0, 7.0, -84.0, 44.0, 11.5))
    k = 0
    for row, (y0, dy, xa, xb, pitch) in enumerate(rows):
        for x in np.arange(xa + (0.5 * pitch if row % 2 else 0.0), xb, pitch):
            i = (k * 3 + row) % len(grown)
            px, py = float(x + rng.uniform(-2.2, 2.2)), float(y0 + rng.uniform(-dy, dy))
            s = float(rng.uniform(0.82, 1.12))
            k += 1
            if in_the_sun(px, py, radius[i] * s):
                i = narrow
                if in_the_sun(px, py, radius[i] * s):
                    left_out += 1
                    continue
            t = make_seed_tree.duplicate(grown[i], location=(px, py, 0.0), rotation=float(rng.uniform(0.0, 6.283)))
            t['object'].scale = (s, s, s)
            trees.append(t)
    X.say('   trees: %d placed, %d places left empty (the sun\'s way into the door)' % (len(trees), left_out))
    for t in grown:                                                           # (the five grown out of sight go)
        make_seed_tree.remove(t)
    make_seed_tree.set_wind(strength=0.35, speed=0.9)
    sun = bpy.data.objects.get('sun_dock')
    if sun is not None:
        make_seed_tree.set_sun(sun)
    tree_mats = set()
    for t in trees:                                                           # into the dock's collection
        for o in [t['object']] + list(t['object'].children_recursive):
            for c in list(o.users_collection):
                c.objects.unlink(o)
            X.C_DOCK.objects.link(o)
            o.hide_probe_volume = True
            if o.type == 'MESH':
                tree_mats.update(m for m in o.data.materials if m is not None)
    # THE LEAVES CAST WHOLE SHADOWS: their cards are dithered, and so would their shadow be (the low sun through the
    # crowns lies on everything inside the door as loose speckle at 16 samples, crawling from frame to frame); a card's
    # shadow is the card's: a coarser dapple that holds still
    for m in tree_mats:
        if getattr(m, 'use_transparent_shadow', False):
            m.use_transparent_shadow = False
    return trees

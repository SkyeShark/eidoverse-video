"""The hall's machines as modelled assets (private to the set): the crane (its runway, bridge, trolley, belts, ring and
gripper pads) and the meter cabinet. The layout places and rigs them as plain boxes; here every one of their meshes is
rebuilt IN ITS OWN FRAME with real sections, so every object, origin, parent and driver stays as the layout made it.

Called by hall.look with X (see _shell's head).
"""
import math

import bpy
import numpy as np

from . import _kit as kit
from ._kit import MB, i_section

PI = math.pi


def replace_mesh(X, old_name, me):
    """every object that shows the mesh `old_name` shows `me` instead; `me` takes the name"""
    old = X.MESH.get(old_name)
    if old is None:
        X.say('   (no mesh named %s)' % old_name)
        return
    for o in X.OBJ:
        if o.data is old:
            o.data = me
    bpy.data.meshes.remove(old)
    me.name = old_name


def gear_motor(mb, c, axis, s, dark, galv, r=0.07, ln=0.24):
    """a small geared motor at c, its shaft along `axis`, the motor on the side s (+1 / -1) of its gearbox: finned
    housing, fan cowl, terminal box, the gearbox block with its cover's bolts"""
    i = 'xyz'.index(axis)

    def at(d, e=(0.0, 0.0)):                                                 # d along the axis, e across (the two other axes)
        p = list(c)
        p[i] += d * s
        j, k = [n for n in range(3) if n != i]
        p[j] += e[0]
        p[k] += e[1]
        return tuple(p)

    g = 0.11
    size = [g * 1.25, g * 1.25, g * 1.25]
    size[i] = g
    mb.box(at(0.0), tuple(size), dark)                                       # the gearbox
    mb.cyl(at(g / 2 + ln / 2), r, ln, axis, 24, dark)                        # the motor
    for n in range(int(ln / 0.022) - 1):
        mb.cyl(at(g / 2 + 0.02 + 0.022 * n), r * 1.12, 0.005, axis, 24, dark)   # its fins
    mb.cyl(at(g / 2 + ln + 0.02), r * 1.05, 0.04, axis, 24, dark)            # the fan cowl
    tb = [0.07, 0.07, 0.07]
    tb[i] = 0.09
    mb.box(at(g / 2 + ln * 0.45, (0.0, r + 0.025)), tuple(tb), dark)         # the terminal box
    mb.cyl(at(g / 2 + ln * 0.45, (0.045, r + 0.025)), 0.011, 0.02, 'xyz'[[n for n in range(3) if n != i][0]], 6, galv)   # its gland
    for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        mb.bolt(at(-g / 2 - 0.004, (a * g * 0.5, b * g * 0.5)), 0.008, 0.006, axis, galv, washer=False)


# ====================================================================================================== the crane
def crane(X):
    M, L = X.M, X.L
    G = L['gantry']
    RZ = L['hall']['roof_z']
    x0, x1 = G['rail_x']
    y0, y1 = G['rail_y']
    zt = G['rail_top']
    dy, gw = G['girder_dy'], G['girder_w']
    z0, z1 = G['girder_z']
    WH, GALV, RUB, TEAL, DARK, GREY = range(6)
    #   (WH: the crane's own paint, a worn safety yellow; its trucks, drives and grippers keep the machines' teal)
    MATS = [M['safety_yellow'], M['steel_galv'], M['rubber_black'], M['machine_teal'], M['steel_dark'], M['plastic_grey']]
    # ---------------------------------------------------------------- the runway: two rails on posts, tied at their ends
    mb = MB()
    RAIL = i_section(0.26, 0.14, 0.012, 0.008, r=0.010)
    for rx, posts in zip(G['rail_x'], (G['post_y_west'], G['post_y_east'])):
        mb.prism([(u, v) for u, v in RAIL], y0, y1, 'y', WH, at=(rx, zt - 0.13))
        mb.span((rx - 0.025, y0 + 0.02, zt), (rx + 0.025, y1 - 0.02, zt + 0.03), GALV)        # the wheels' rail
        y = y0 + 0.3
        while y < y1 - 0.2:                                                  # its clips, both sides
            for s in (-1, 1):
                mb.box((rx + s * 0.043, y, zt + 0.007), (0.03, 0.05, 0.014), GALV)
                mb.bolt((rx + s * 0.046, y, zt + 0.018), 0.008, 0.006, 'z', GALV, washer=False)
            y += 0.6
        for ye, s in ((y0, 1), (y1, -1)):                                    # the end stops and their buffers
            mb.box((rx, ye + s * 0.06, zt + 0.085), (0.10, 0.05, 0.17), WH)
            mb.cyl((rx, ye + s * 0.11, zt + 0.105), 0.04, 0.05, 'y', 16, RUB)
        for py in posts:
            mb.span((rx - 0.07, py - 0.07, 0.016), (rx + 0.07, py + 0.07, zt - 0.272), WH)     # the post
            mb.span((rx - 0.16, py - 0.16, 0.0), (rx + 0.16, py + 0.16, 0.016), WH)            # its foot
            mb.span((rx - 0.10, py - 0.10, zt - 0.272), (rx + 0.10, py + 0.10, zt - 0.26), WH)  # its cap, bolted under the rail
            for sx in (-1, 1):
                for sy in (-1, 1):
                    mb.bolt((rx + sx * 0.12, py + sy * 0.12, 0.0215), 0.012, 0.011, 'z', GALV)
                    mb.cyl((rx + sx * 0.12, py + sy * 0.12, 0.034), 0.006, 0.014, 'z', 8, GALV)
                    mb.bolt((rx + sx * 0.052, py + sy * 0.08, zt - 0.277), 0.009, 0.008, 'z', GALV, washer=False)
            for s in (-1, 1):                                                # gussets at the foot, knee braces under the rail
                mb.prism([(s * 0.07, 0.016), (s * 0.15, 0.016), (s * 0.07, 0.14)], py - 0.004, py + 0.004, 'y', WH, at=(rx, 0.0))
                mb.prism([(s * 0.07, 0.016), (s * 0.15, 0.016), (s * 0.07, 0.14)], rx - 0.004, rx + 0.004, 'x', WH, at=(py, 0.0))
                if y0 + 0.3 < py + s * 0.62 < y1 - 0.3:
                    mb.bar((rx, py + s * 0.07, zt - 0.86), (rx, py + s * 0.62, zt - 0.27), 0.06, 0.06, WH)
        for py in G['hang_y']:                                               # a drop tube from the roof steel (no floor post there)
            mb.cyl((rx, py, (zt + RZ - 0.6) / 2), 0.035, RZ - 0.6 - zt, 'z', 16, WH)
            mb.box((rx, py, zt + 0.008), (0.22, 0.22, 0.016), WH)
            mb.box((rx, py, RZ - 0.608), (0.26, 0.26, 0.016), WH)
            for sx in (-1, 1):
                for sy in (-1, 1):
                    mb.bolt((rx + sx * 0.08, py + sy * 0.08, zt + 0.021), 0.009, 0.008, 'z', GALV, washer=False)
    for ty in (y0, y1):                                                      # the end ties
        mb.span((x0 + 0.07, ty - 0.05, zt - 0.22), (x1 - 0.07, ty + 0.05, zt - 0.05), WH)
        for rx, s in ((x0, 1), (x1, -1)):
            mb.box((rx + s * 0.076, ty, zt - 0.135), (0.012, 0.16, 0.23), WH)
            for bz in (-0.08, 0.08):
                for sy in (-1, 1):
                    mb.bolt((rx + s * 0.085, ty + sy * 0.062, zt - 0.135 + bz), 0.009, 0.008, 'x', GALV, washer=False)
    # the conductor rail along the east rail's outer side: the bridge's current
    cx = x1 + 0.11
    mb.span((cx - 0.02, y0 + 0.2, zt - 0.20), (cx + 0.02, y1 - 0.2, zt - 0.14), GREY)
    y = y0 + 0.5
    while y < y1 - 0.3:
        mb.span((x1 + 0.004, y - 0.015, zt - 0.12), (cx + 0.02, y + 0.015, zt - 0.10), GALV)
        mb.box((cx, y, zt - 0.13), (0.03, 0.03, 0.02), GALV)
        y += 1.2
    me = mb.mesh('line_crane_runway_new', MATS)
    kit.finish(me, bevel=0.004, inset=0.02, cavity=0.08, ground=0.0, log=X.say)
    replace_mesh(X, 'line_crane_runway', me)
    # ---------------------------------------------------------------- the bridge: two box girders on end trucks
    mb = MB()
    xa, xb = x0 - 0.22, x1 + 0.22
    for s in (-1, 1):
        yc = s * dy
        mb.span((xa, yc - gw / 2 + 0.012, z0 + 0.012), (xb, yc + gw / 2 - 0.012, z1 - 0.012), WH)   # the box
        mb.span((xa, yc - gw / 2 - 0.015, z0), (xb, yc + gw / 2 + 0.015, z0 + 0.012), WH)           # its flange plates
        mb.span((xa, yc - gw / 2 - 0.015, z1 - 0.012), (xb, yc + gw / 2 + 0.015, z1), WH)
        mb.span((xa + 0.05, yc - 0.02, z1), (xb - 0.05, yc + 0.02, z1 + 0.02), GALV)                # the trolley's rail
        x = xa + 0.6
        while x < xb - 0.3:                                                  # stiffeners on the outer web
            mb.box((x, yc + s * (gw / 2 - 0.004), (z0 + z1) / 2), (0.008, 0.016, z1 - z0 - 0.024), WH)
            x += 1.1
        for xe, se in ((xa, 1), (xb, -1)):                                   # end stops for the trolley
            mb.box((xe + se * 0.07, yc, z1 + 0.05), (0.04, 0.07, 0.06), WH)
            mb.cyl((xe + se * 0.10, yc, z1 + 0.05), 0.022, 0.03, 'x', 12, RUB)
    for rx in (x0, x1):
        mb.span((rx - 0.10, -0.92, zt + 0.085), (rx + 0.10, 0.92, zt + 0.22), TEAL)                 # the end truck
        for wy in (-0.78, 0.78):
            mb.cyl((rx, wy, zt + 0.105), 0.075, 0.06, 'x', 28, GALV)                                # the wheel, its flanges,
            for sx in (-1, 1):
                mb.cyl((rx + sx * 0.036, wy, zt + 0.105), 0.09, 0.012, 'x', 28, GALV)
                mb.cyl((rx + sx * 0.106, wy, zt + 0.105), 0.045, 0.012, 'x', 20, DARK)              # the bearing caps
                for k in range(4):
                    a = PI / 4 + k * PI / 2
                    mb.bolt((rx + sx * 0.114, wy + math.cos(a) * 0.032, zt + 0.105 + math.sin(a) * 0.032), 0.006, 0.005, 'x', GALV, washer=False)
        for sy in (-1, 1):
            mb.cyl((rx, sy * 0.945, zt + 0.15), 0.04, 0.05, 'y', 16, RUB)                           # buffers
            for bx in (-0.075, 0.075):                                       # the girder's bolts down into the truck
                for by in (-0.05, 0.05):
                    mb.bolt((rx + bx, sy * dy + by, z1 + 0.004), 0.010, 0.008, 'z', GALV)
    gear_motor(mb, (x0 - 0.16, 0.45, zt + 0.14), 'x', -1, DARK, GALV)                               # the travel drives
    gear_motor(mb, (x1 + 0.16, 0.45, zt + 0.14), 'x', 1, DARK, GALV)
    ycr = dy + gw / 2 + 0.07                                                 # the trolley's conductor rail, along the north girder
    mb.span((xa + 0.3, ycr - 0.02, z1 - 0.10), (xb - 0.3, ycr + 0.02, z1 - 0.04), GREY)
    x = xa + 0.6
    while x < xb - 0.3:
        mb.span((x - 0.015, dy + gw / 2 + 0.015, z1 - 0.03), (x + 0.015, ycr + 0.02, z1 - 0.012), GALV)
        mb.box((x, ycr, z1 - 0.035), (0.03, 0.03, 0.02), GALV)
        x += 1.1
    mb.box((x1 + 0.11, -0.3, zt - 0.02), (0.05, 0.10, 0.08), DARK)                                  # the bridge's collector shoe
    mb.bar((x1 + 0.11, -0.3, zt + 0.02), (x1 + 0.06, -0.3, zt + 0.12), 0.02, 0.02, GALV)
    me = mb.mesh('crane_bridge_new', MATS)
    kit.finish(me, bevel=0.004, inset=0.02, cavity=0.08, log=X.say)
    replace_mesh(X, 'crane_bridge', me)
    # ---------------------------------------------------------------- the trolley: an open frame (a top view looks through it)
    mb = MB()
    ty, tx, tw = dy + 0.14, 0.675, 0.12                                      # (the cross members stand outside where the
    za, zb = z1 + 0.02, z1 + 0.14                                            #  belts hang: the belts fall clear inside)
    for s in (-1, 1):
        mb.span((-tx, min(s * ty, s * (ty - tw)), za), (tx, max(s * ty, s * (ty - tw)), zb), WH)     # side members
        mb.span((min(s * tx, s * (tx - tw)), -ty + tw, za), (max(s * tx, s * (tx - tw)), ty - tw, zb), WH)   # cross members
        for sx in (-1, 1):                                                   # corner plates and their bolts
            mb.box((sx * (tx - 0.09), s * (ty - 0.09), zb + 0.004), (0.20, 0.20, 0.008), WH)
            for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                mb.bolt((sx * (tx - 0.09) + a * 0.07, s * (ty - 0.09) + b * 0.07, zb + 0.012), 0.009, 0.007, 'z', GALV, washer=False)
            mb.cyl((sx * 0.40, s * dy, za + 0.05), 0.05, 0.04, 'y', 24, GALV)                       # the wheels on the girders' rails
            mb.cyl((sx * 0.40, s * (dy - 0.026), za + 0.05), 0.062, 0.010, 'y', 24, GALV)
            mb.cyl((sx * 0.40, s * (dy + 0.04), za + 0.05), 0.022, 0.05, 'y', 12, DARK)
    zd = z1 + 0.20                                                           # the belt drums: a belt leaves each on the line's side
    for sy in (-1, 1):
        yd = sy * 0.58
        mb.cyl((0.06, yd, zd), 0.018, 1.48, 'x', 14, GALV)                                          # the shaft the pair shares
        for sx in (-1, 1):
            mb.cyl((sx * 0.52, yd, zd), 0.060, 0.07, 'x', 28, GALV)                                  # the drum,
            for e in (-1, 1):
                mb.cyl((sx * 0.52 + e * 0.038, yd, zd), 0.085, 0.006, 'x', 28, GALV)                 # its cheeks,
            mb.cyl((sx * 0.52, yd, zd), 0.0635, 0.05, 'x', 28, DARK)                                 # the belt wound on it,
            mb.span((sx * 0.52 - 0.025, sy * 0.52 - 0.003, zb), (sx * 0.52 + 0.025, sy * 0.52 + 0.003, zd), DARK)   # and leaving it
            mb.box((sx * (tx - tw / 2), yd, zb + 0.042), (0.07, 0.07, 0.084), DARK)                  # a plummer block
            for e in (-1, 1):
                mb.bolt((sx * (tx - tw / 2), yd + e * 0.05, zb + 0.004), 0.007, 0.006, 'z', GALV, washer=False)
    mb.span((tx + 0.03, -0.60, zd - 0.06), (tx + 0.075, 0.60, zd + 0.06), TEAL)                      # the chain case joining the shafts
    gear_motor(mb, (tx + 0.14, 0.0, zd), 'x', 1, TEAL, GALV, r=0.075, ln=0.26)                       # the hoist's drive
    mb.box((-tx - 0.10, 0.25, za + 0.17), (0.16, 0.26, 0.30), GREY)                                  # the trolley's control box
    mb.box((-tx - 0.183, 0.25, za + 0.17), (0.006, 0.22, 0.26), GREY)                                # its door
    for k in range(3):
        mb.cyl((-tx - 0.10, 0.17 + 0.08 * k, za + 0.008), 0.011, 0.024, 'z', 6, GALV)                # glands under it
    mb.span((-tx - 0.10 - 0.02, 0.38, za + 0.05), (-tx - 0.10 + 0.02, ty + 0.10, za + 0.07), GALV)   # the collector's arm
    mb.box((-tx - 0.10, ty + 0.10, za + 0.02), (0.05, 0.05, 0.08), DARK)
    me = mb.mesh('crane_trolley_new', MATS)
    kit.finish(me, bevel=0.003, inset=0.014, cavity=0.06, log=X.say)
    replace_mesh(X, 'crane_trolley', me)
    # ---------------------------------------------------------------- a belt: flat webbing, its two selvedges proud
    mb = MB()
    mb.span((-0.025, -0.003, -1.0), (0.025, 0.003, 0.0), 0)
    for s in (-1, 1):
        mb.span((s * 0.0225 - 0.0025, -0.0042, -1.0), (s * 0.0225 + 0.0025, 0.0042, 0.0), 0)
    me = mb.mesh('crane_belt_new', [M['belt_webbing']])
    kit.uv_metres(me)
    replace_mesh(X, 'crane_belt', me)
    # ---------------------------------------------------------------- the ring that comes down round a hood
    ro, ri = G['ring_half_out'], G['ring_half_in']
    rm, rw = (ro + ri) / 2, ro - ri
    mb = MB()
    for s in (-1, 1):
        mb.span((-ro, s * rm - rw / 2, -0.04), (ro, s * rm + rw / 2, 0.04), WH)
        mb.span((s * rm - rw / 2, -ri, -0.04), (s * rm + rw / 2, ri, 0.04), WH)
    for sx in (-1, 1):
        for sy in (-1, 1):
            # a gusset over each corner (an L of plate) and its bolts
            mb.prism([(sx * (ro - 0.005), sy * (ro - 0.005)), (sx * (ro - 0.30), sy * (ro - 0.005)), (sx * (ro - 0.30), sy * (ri + 0.005)),
                      (sx * (ri + 0.005), sy * (ri + 0.005)), (sx * (ri + 0.005), sy * (ro - 0.30)), (sx * (ro - 0.005), sy * (ro - 0.30))],
                     0.04, 0.046, 'z', WH)
            for a, b in ((0.06, 0.06), (0.24, 0.06), (0.06, 0.24)):
                mb.bolt((sx * (ro - a), sy * (ro - b), 0.05), 0.008, 0.006, 'z', GALV, washer=False)
            # the belt's anchor: two lugs, a pin, the belt's loop round it
            for e in (-1, 1):
                mb.box((sx * 0.52 + e * 0.032, sy * 0.52, 0.078), (0.010, 0.05, 0.064), GALV)
            mb.cyl((sx * 0.52, sy * 0.52, 0.086), 0.008, 0.086, 'x', 12, GALV)
            mb.cyl((sx * 0.52, sy * 0.52, 0.086), 0.012, 0.05, 'x', 14, DARK)
    for a in range(4):                                                       # the four grippers: a cylinder block, guide bushes, air lines
        ca, sa = round(math.cos(a * PI / 2)), round(math.sin(a * PI / 2))

        def W(p, ca=ca, sa=sa):                                              # the gripper's own frame (+x outward) -> the ring's
            return (p[0] * ca - p[1] * sa, p[0] * sa + p[1] * ca, p[2])

        def wbox(c, s_, mi, a=a, W=W):
            mb.box(W(c), (s_[0], s_[1], s_[2]) if a % 2 == 0 else (s_[1], s_[0], s_[2]), mi)

        ax = 'x' if a % 2 == 0 else 'y'
        wbox((rm, 0.0, -0.105), (0.06, 0.20, 0.13), TEAL)                                            # the block (where the layout put it)
        wbox((rm + 0.033, 0.0, -0.105), (0.006, 0.17, 0.11), GALV)                                   # its end plate
        for e in (-1, 1):
            mb.cyl(W((rm - 0.036, e * 0.075, -0.105)), 0.016, 0.014, ax, 16, GALV)                   # guide bushes
            mb.bolt(W((rm + 0.038, e * 0.07, -0.065)), 0.006, 0.005, ax, GALV, washer=False)
            mb.bolt(W((rm + 0.038, e * 0.07, -0.145)), 0.006, 0.005, ax, GALV, washer=False)
            # an air line: up from the block, over the ring's top to the corner
            mb.cyl(W((rm, e * 0.05, -0.034)), 0.007, 0.012, 'z', 8, GALV)
            mb.tube([W((rm, e * 0.05, -0.03)), W((rm + 0.075, e * 0.05, -0.02)), W((rm + 0.085, e * 0.05, 0.03)), W((rm + 0.03, e * 0.06, 0.056)),
                     W((rm, e * 0.20, 0.052)), W((rm - 0.005, e * 0.40, 0.052))], 0.004, 6, RUB)
    mb.box((-rm, -rm + 0.02, 0.085), (0.09, 0.14, 0.07), GREY)                                       # the valve block on one corner
    for k in range(4):
        mb.cyl((-rm + 0.05, -rm - 0.025 + 0.03 * k, 0.085), 0.006, 0.014, 'x', 6, GALV)
    me = mb.mesh('crane_ring_new', MATS)
    kit.finish(me, bevel=0.003, inset=0.012, cavity=0.05, log=X.say)
    replace_mesh(X, 'crane_ring', me)
    # ---------------------------------------------------------------- a gripper's pad: grooved rubber on a plate, a rod, two pins
    mb = MB()
    mb.span((0.014, -0.12, -0.05), (0.02, 0.12, 0.05), 1)                                            # the backing plate
    mb.span((0.004, -0.118, -0.048), (0.014, 0.118, 0.048), 0)                                       # the rubber
    for k in range(7):
        y = -0.105 + 0.035 * k
        mb.span((0.0, y - 0.011, -0.046), (0.004, y + 0.011, 0.046), 0)                              # its ribs, toward the hood
    mb.cyl((0.065, 0, 0), 0.014, 0.09, 'x', 14, 1)
    for e in (-1, 1):
        mb.cyl((0.05, e * 0.075, 0), 0.008, 0.06, 'x', 10, 1)
    me = mb.mesh('crane_pad_new', [M['rubber_black'], M['steel_galv']])
    kit.finish(me, bevel=0.0015, inset=0.006, cavity=0.02, log=X.say)
    replace_mesh(X, 'crane_pad', me)


# ====================================================================================================== the meter cabinet
def cabinet(X, tray_z):
    """a sheet steel enclosure on a plinth frame, its right side to the east wall: door with a glazed window (bezel,
    gasket, screws), a label plate on rivets, pressed louvres, three hinges, a swing handle, a hasp and its padlock,
    lifting eyes, the back's screwed panel, two conduits up into the cable tray"""
    M, L = X.M, X.L
    MC = L['meter_cabinet']
    cx0, cx1 = MC['x']
    cy0, cy1 = MC['y']
    cx1 = min(cx1, X.HX1 - 0.09 - 0.012)                                     # clear of the wall's dado
    cxm = (MC['x'][0] + MC['x'][1]) / 2                                      # the window's middle stays where the drums are
    wz, (ww, wh) = MC['window_z'], MC['window']
    zp = MC['plinth']
    zt = zp + MC['h']
    dy = cy1
    PAINT, GALV, DARK, RUB, ALU, BRASS, TEAL = range(7)
    mb = MB()
    for a, b in (((cx0, cy0), (cx1, cy0 + 0.04)), ((cx0, cy1 - 0.04), (cx1, cy1)), ((cx0, cy0 + 0.04), (cx0 + 0.04, cy1 - 0.04)),
                 ((cx1 - 0.04, cy0 + 0.04), (cx1, cy1 - 0.04))):
        mb.span((a[0] + 0.006, a[1] + 0.006, 0.0), (b[0] - 0.006, b[1] - 0.006, zp), TEAL)           # the plinth's four sides
    for x in (cx0, cx1):
        for y in (cy0, cy1):
            sx, sy = (1 if x == cx0 else -1), (1 if y == cy0 else -1)
            mb.span((min(x, x + sx * 0.07), min(y, y + sy * 0.07), 0.0), (max(x, x + sx * 0.07), max(y, y + sy * 0.07), zp), TEAL)   # corners
    mb.tub((cx0, cy0, zp), (cx1, dy - 0.004, zt), 0.02, PAINT)                                       # the body: hollow, the drums stand in it
    mb.span((cx0 - 0.012, cy0 - 0.012, zt), (cx1 + 0.004, dy + 0.03, zt + 0.012), TEAL)              # its roof plate, over the door
    for x in (cx0 + 0.06, cx1 - 0.06):                                       # lifting eyes
        for y in (cy0 + 0.06, dy - 0.07):
            mb.cyl((x, y, zt + 0.018), 0.012, 0.012, 'z', 6, GALV)
            ring = mb.arc((x, y, zt + 0.045), 0.018, 0.0, 2 * PI, 'y', 12)
            mb.tube(ring[:-1] + [ring[0]], 0.005, 8, GALV, caps=False)
    mb.frame((cx0 + 0.012, dy - 0.004, zp + 0.012), (cx1 - 0.012, dy + 0.002, zt - 0.012), (cx0 + 0.034, zp + 0.034),
             (cx1 - 0.034, zt - 0.034), RUB)                                 # the door's gasket: a ring in the gap (the drums are behind)
    d0, d1 = dy + 0.002, dy + 0.018                                          # the door leaf, round its window
    xa, xb = cx0 + 0.008, cx1 - 0.008
    hole = ((cxm - ww / 2, wz - wh / 2), (cxm + ww / 2, wz + wh / 2))
    mb.frame((xa, d0, zp + 0.012), (xb, d1, zt - 0.012), hole[0], hole[1], PAINT)                     # one leaf, no seam
    bz = 0.016                                                               # the window's bezel: a frame screwed on, a gasket inside it
    mb.frame((cxm - ww / 2 - bz, d1, wz - wh / 2 - bz), (cxm + ww / 2 + bz, d1 + 0.005, wz + wh / 2 + bz), hole[0], hole[1], ALU)
    for sx in (-1, 0, 1):
        for sz in (-1, 1):
            mb.cyl((cxm + sx * (ww / 2 + bz / 2 - 0.002) * (1 if sx else 0), d1 + 0.0056, wz + sz * (wh / 2 + bz / 2)), 0.0042, 0.0014, 'y', 12, GALV)
    g_ = 0.0035
    mb.span((cxm - ww / 2, dy + 0.0045, wz + wh / 2 - g_), (cxm + ww / 2, d1 + 0.001, wz + wh / 2), RUB)
    mb.span((cxm - ww / 2, dy + 0.0045, wz - wh / 2), (cxm + ww / 2, d1 + 0.001, wz - wh / 2 + g_), RUB)
    mb.span((cxm - ww / 2, dy + 0.0045, wz - wh / 2 + g_), (cxm - ww / 2 + g_, d1 + 0.001, wz + wh / 2 - g_), RUB)
    mb.span((cxm + ww / 2 - g_, dy + 0.0045, wz - wh / 2 + g_), (cxm + ww / 2, d1 + 0.001, wz + wh / 2 - g_), RUB)
    mb.span((cxm - 0.13, d1, wz + 0.07), (cxm + 0.13, d1 + 0.0025, wz + 0.14), ALU)                  # the label's plate (meter_label_place)
    for sx in (-1, 1):
        for sz in (0.078, 0.132):
            mb.cyl((cxm + sx * 0.122, d1 + 0.003, wz + sz), 0.0032, 0.0016, 'y', 10, GALV)           # its rivets
    for i in range(7):                                                       # pressed louvres, low on the door: hoods open downward
        lz = zp + 0.16 + 0.035 * i
        mb.prism([(d1, lz), (d1 + 0.011, lz), (d1, lz + 0.024)], cxm - 0.22, cxm + 0.22, 'x', PAINT)
    for i in range(6):                                                       # and on the back, toward the line
        lz = zp + 1.45 + 0.035 * i
        mb.prism([(cy0, lz), (cy0 - 0.011, lz), (cy0, lz + 0.024)], cxm - 0.22, cxm + 0.22, 'x', PAINT)
    bp = 0.0025                                                              # the back's panel, screwed on round its edge
    mb.span((cx0 + 0.03, cy0 - bp, zp + 0.03), (cx1 - 0.03, cy0, zp + 1.38), PAINT)
    for z in np.linspace(zp + 0.05, zp + 1.36, 6):
        for x in (cx0 + 0.045, cx1 - 0.045):
            mb.cyl((x, cy0 - bp - 0.0008, float(z)), 0.0045, 0.0016, 'y', 12, GALV)
    for x in np.linspace(cx0 + 0.045, cx1 - 0.045, 5)[1:-1]:
        for z in (zp + 0.05, zp + 1.36):
            mb.cyl((float(x), cy0 - bp - 0.0008, z), 0.0045, 0.0016, 'y', 12, GALV)
    mb.span((cxm - 0.05, cy0 - 0.002, zp + 1.75), (cxm + 0.05, cy0, zp + 1.81), ALU)                 # a blank rating plate
    for hz in (zp + 0.22, (zp + zt) / 2, zt - 0.22):                         # hinges, on the wall side
        mb.cyl((xb + 0.004, d1 - 0.004, hz), 0.008, 0.07, 'z', 12, GALV)
        mb.box((xb - 0.02, d1 + 0.0015, hz), (0.045, 0.003, 0.06), GALV)
    hx = cx0 + 0.0675                                                        # the swing handle, on the free edge
    mb.box((hx, d1 + 0.004, 1.11), (0.04, 0.008, 0.19), DARK)                                        # its escutcheon
    mb.cyl((hx, d1 + 0.016, 1.16), 0.012, 0.018, 'y', 16, DARK)                                      # the hub
    mb.tube([(hx, d1 + 0.022, 1.16), (hx, d1 + 0.034, 1.155), (hx, d1 + 0.038, 1.13), (hx, d1 + 0.038, 1.03)], 0.008, 10, DARK)   # the lever
    mb.cyl((hx, d1 + 0.009, 1.045), 0.006, 0.004, 'y', 12, GALV)                                     # its lock's cylinder
    mb.box((cx0 + 0.0675, d1 + 0.002, 1.28), (0.065, 0.004, 0.06), GALV)                             # the hasp's plate
    for sx_ in (0.052, 0.084):
        mb.bolt((cx0 + sx_ + (0.012 if sx_ > 0.06 else -0.012), d1 + 0.0055, 1.262), 0.0045, 0.003, 'y', GALV, washer=False)
    mb.tube([(cx0 + 0.052, d1 + 0.004, 1.285), (cx0 + 0.052, d1 + 0.024, 1.285)] + mb.arc((cx0 + 0.068, d1 + 0.024, 1.285), 0.016, PI, 0.0, 'z', 8)[1:]
            + [(cx0 + 0.084, d1 + 0.004, 1.285)], 0.004, 8, GALV)                                    # its staple: a loop out of the door
    px, py_, pz = cx0 + 0.068, d1 + 0.031, 1.2235                            # the padlock: a brass body, a steel shackle through the staple
    mb.box((px, py_, pz), (0.046, 0.022, 0.050), BRASS)
    mb.tube([(px - 0.012, py_, pz + 0.025), (px - 0.012, py_, pz + 0.058)] + mb.arc((px, py_, pz + 0.058), 0.012, -PI / 2, PI / 2, 'y', 8)[1:]
            + [(px + 0.012, py_, pz + 0.025)], 0.0035, 8, GALV)
    mb.cyl((px, py_ - 0.0115, pz - 0.008), 0.005, 0.002, 'y', 12, GALV)                              # its keyway
    for px_ in (cx1 - 0.10, cx1 - 0.20):                                     # conduits from its roof up into the cable tray
        mb.bolt((px_, cy0 + 0.10, zt + 0.018), 0.016, 0.012, 'z', GALV)
        mb.cyl((px_, cy0 + 0.10, (zt + 0.02 + tray_z + 0.03) / 2), 0.0125, tray_z + 0.03 - zt - 0.02, 'z', 12, GALV)
    me = mb.mesh('meter_cabinet_new', [M['cabinet_grey'], M['steel_galv'], M['steel_dark'], M['rubber_black'], M['plate_alu'], M['brass'],
                                       M['machine_teal']])
    kit.finish(me, bevel=0.0018, inset=0.01, cavity=0.05, ground=0.0, log=X.say)
    replace_mesh(X, 'meter_cabinet', me)

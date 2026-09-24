# build_bridge.py — the Golden Gate, dreamt (DAISY bridge, bars 0–1). A stylised suspension bridge
# for a fog vignette: the south tower (two stepped, fluted legs; four portal struts with stepped
# corbels and the chevron band), the east walkway (Art Deco railing, pipe rail on the curb, lamp
# standards), the roadway, both main cables on their parabola and the suspender pairs with cable
# bands. International Orange throughout (paint roles; the engine binds PBR + weathering + fog).
#   blender --background --python build_bridge.py [-- preview]
# Bridge-local three space: the walkway runs along z (the camera looks toward -z at the tower),
# walkway top y = 0; x=0 is the curb, the outer railing at x=3.1. Writes assets/bridge.glb.
import sys
import os
import math
import json
import bpy
import bmesh
from mathutils import Vector, Matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib
import fx_core
importlib.reload(fx_core)
from fx_core import Mesh, reset_scene, ASSETS, T2B, material, preview, apply_modifiers, boolean, reuv_planar, hard_exit

reset_scene()
TZ = -57.0                     # tower centre (z)
TD = 6.0                       # leg depth along the bridge
CABLE_X = (3.55, -23.55)       # near / far cable planes = leg centres
TOP = 95.0
LOW_Z, LOW_Y = 25.0, 3.5       # the cable's low point (behind the camera)
def cable_y(z):
    k = (z - LOW_Z) / (TZ - LOW_Z)
    return LOW_Y + (TOP - 1.2 - LOW_Y) * k * k
SEG = [(-40.0, 24.0, 4.4, 6.0), (24.0, 48.0, 4.0, 5.5), (48.0, 68.0, 3.6, 5.0), (68.0, 88.0, 3.2, 4.5), (88.0, TOP, 3.0, 4.2)]
PORTALS = [(24.0, 30.0), (48.0, 53.0), (68.0, 72.0), (88.0, TOP - 1.0)]
OUT = {'cable_x': CABLE_X, 'tower_z': TZ, 'top': TOP, 'low': [LOW_Z, LOW_Y], 'lamps': [], 'suspenders': []}
EXPORT = []

# ═════════════════════════════════ THE TOWER ═════════════════════════════════
def leg(xc, name):
    """one stepped leg: stacked sections (each a real construction setback), with two vertical flutes
    cut into every face of every section."""
    m = Mesh(name)
    for (y0, y1, w, d) in SEG:
        m.box((xc, (y0 + y1) / 2, TZ), (w, y1 - y0, d), 'orange')
        # setback ledge/cap band at the top of each section
        m.box((xc, y1 - 0.25, TZ), (w + 0.18, 0.5, d + 0.18), 'orange')
    ob = m.finalize(weighted=False)
    cuts = []
    for (y0, y1, w, d) in SEG[1:]:
        for side in (-1, 1):
            for f in (-0.22, 0.22):          # flutes on the x faces
                c = Mesh('_f')
                c.box((xc + side * w / 2, (y0 + y1) / 2 - 0.2, TZ + f * d), (0.24, (y1 - y0) - 2.2, 0.34), 'orange')
                cuts.append(c.finalize(weighted=False))
            for f in (-0.25, 0.25):          # and on the z faces
                c = Mesh('_f')
                c.box((xc + f * w, (y0 + y1) / 2 - 0.2, TZ + side * d / 2), (0.34, (y1 - y0) - 2.2, 0.24), 'orange')
                cuts.append(c.finalize(weighted=False))
    boolean(ob, cuts, 'DIFFERENCE')
    for c in cuts:
        bpy.data.objects.remove(c)
    reuv_planar(ob)
    b = ob.modifiers.new('bevel', 'BEVEL')
    b.width = 0.05
    b.segments = 2
    b.limit_method = 'ANGLE'
    b.use_clamp_overlap = True
    ob.modifiers.new('wn', 'WEIGHTED_NORMAL')
    return ob


def portal(y0, y1, idx):
    """a portal strut between the legs: a deep beam with the chevron band along its soffit edges and
    three stepped corbels at each end, above and below (the stepped corners of the openings)."""
    m = Mesh('portal_%d' % idx)
    wseg = next(s for s in SEG if s[0] <= y0 < s[1])
    lw, ld = wseg[2], wseg[3]
    xa, xb = CABLE_X[1] + lw / 2, CABLE_X[0] - lw / 2          # inner faces of the far / near legs
    xm = (xa + xb) / 2
    L = xb - xa
    dd = ld - 0.9
    m.box((xm, (y0 + y1) / 2, TZ), (L + 0.4, y1 - y0, dd), 'orange')
    # a recessed panel band on the faces (reads as the strut's plate panels)
    for side in (-1, 1):
        m.box((xm, (y0 + y1) / 2, TZ + side * (dd / 2 + 0.04)), (L - 1.2, (y1 - y0) * 0.55, 0.08), 'orange')
    # chevrons: a row of Vs along the lower edge of both faces
    n = int(L / 1.25)
    for side in (-1, 1):
        zf = TZ + side * (dd / 2 + 0.02)
        for i in range(n):
            x0 = xa + 0.6 + i * (L - 1.2) / n
            x1 = x0 + (L - 1.2) / n
            xc = (x0 + x1) / 2
            ya = y0 + 0.15
            pts = [(x0 + 0.05, ya + 0.9), (xc, ya + 0.1), (x1 - 0.05, ya + 0.9)]
            # a small V-shaped rib, 0.16 proud
            for (p, q) in ((pts[0], pts[1]), (pts[1], pts[2])):
                m.beam((p[0], p[1], zf), (q[0], q[1], zf), 0.16, 0.2, 'orange', up=(0, 0, 1))
    # stepped corbels at both ends, below the strut and above it
    for end, xe, dirx in ((0, xa, 1), (1, xb, -1)):
        for k in range(3):
            sz = 1.6 - k * 0.5
            m.box((xe + dirx * sz / 2, y0 - 0.35 - k * 0.7, TZ), (sz, 0.7, dd - 0.2 - k * 0.15), 'orange')
            if idx < 3:
                m.box((xe + dirx * sz / 2, y1 + 0.35 + k * 0.7, TZ), (sz, 0.7, dd - 0.2 - k * 0.15), 'orange')
    ob = m.finalize(bevel=0.04, bevel_segs=2)
    return ob


tower = [leg(CABLE_X[0], 'tower_leg_near'), leg(CABLE_X[1], 'tower_leg_far')]
tower += [portal(y0, y1, i) for i, (y0, y1) in enumerate(PORTALS)]
# cable saddles on top of the legs
sad = Mesh('saddles')
for xc in CABLE_X:
    sad.box((xc, TOP + 0.9, TZ), (2.2, 1.8, 3.4), 'orange')
    sad.lathe([(0.0, 0.0), (0.3, 0.0), (0.3, 0.6), (0.0, 0.6)], 16, (xc, TOP + 1.8, TZ), 'orange', cap_top=True)
tower.append(sad.finalize(bevel=0.05))
EXPORT += tower

# ═════════════════════════════════ THE DECK ═════════════════════════════════
Z0, Z1 = -110.0, 60.0
def jog(z):
    """the walkway swings outboard round the tower leg (x offset), smoothly."""
    a, b = TZ + TD / 2 + 9.0, TZ + TD / 2 + 2.0
    c, d = TZ - TD / 2 - 2.0, TZ - TD / 2 - 9.0
    def s(x0, x1, x):
        k = max(0.0, min(1.0, (x - x0) / (x1 - x0)))
        return k * k * (3 - 2 * k)
    if z > a:
        return 0.0
    if z > b:
        return 6.0 * s(a, b, z)
    if z > c:
        return 6.0
    if z > d:
        return 6.0 * (1 - s(c, d, z))
    return 0.0


dk = Mesh('deck')
STEP = 1.0
zs = [Z1 - i * STEP for i in range(int((Z1 - Z0) / STEP) + 1)]
for i in range(len(zs) - 1):
    za, zb = zs[i], zs[i + 1]
    ja, jb = jog(za), jog(zb)
    # walkway slab top + edges
    dk.face([(0.0 + ja * 0.0, 0.0, za), (3.0 + ja, 0.0, za), (3.0 + jb, 0.0, zb), (0.0, 0.0, zb)], 'walkway',
            uvf=lambda co: (co.x, -co.z))
    if ja > 0 or jb > 0:
        pass
    dk.face([(3.0 + ja, 0.0, za), (3.0 + ja, -0.35, za), (3.0 + jb, -0.35, zb), (3.0 + jb, 0.0, zb)], 'walkway',
            uvf=lambda co: (-co.z, co.y))
# the curb and the roadway
dk.box((-0.07, 0.03, (Z0 + Z1) / 2), (0.16, 0.26, Z1 - Z0), 'walkway')
dk.face([(-19.4, -0.1, Z1), (-0.15, -0.1, Z1), (-0.15, -0.1, Z0), (-19.4, -0.1, Z0)], 'asphalt', uvf=lambda co: (co.x, -co.z))
# the far walkway (mostly lost in fog)
dk.face([(-23.0, 0.0, Z1), (-19.4, 0.0, Z1), (-19.4, 0.0, Z0), (-23.0, 0.0, Z0)], 'walkway', uvf=lambda co: (co.x, -co.z))
dk.box((-19.33, 0.03, (Z0 + Z1) / 2), (0.16, 0.26, Z1 - Z0), 'walkway')
dk_ob = dk.finalize(weighted=False)
EXPORT.append(dk_ob)

# outer railing: Art Deco — posts every 3.1 m, a profiled cap rail, flat balusters at 0.16 m, a base rail
rl = Mesh('railing')
def rail_run(x_of, za, zb, far=False):
    z = za
    posts = []
    while z > zb:
        posts.append(z)
        z -= 3.1
    for k in range(len(posts) - 1):
        p0, p1 = posts[k], posts[k + 1]
        x0, x1 = x_of(p0), x_of(p1)
        # post
        rl.box((x0, 0.66, p0), (0.12, 1.32, 0.14), 'orange')
        rl.box((x0, 1.35, p0), (0.16, 0.06, 0.18), 'orange')
        # cap rail + base rail (a beam from post to post)
        rl.beam((x0, 1.26, p0), (x1, 1.26, p1), 0.1, 0.07, 'orange')
        rl.beam((x0, 1.195, p0), (x1, 1.195, p1), 0.07, 0.03, 'orange')
        rl.beam((x0, 0.1, p0), (x1, 0.1, p1), 0.07, 0.05, 'orange')
        n = int((p0 - p1) / 0.16)
        for j in range(1, n):
            f = j / n
            zz = p0 + (p1 - p0) * f
            xx = x0 + (x1 - x0) * f
            rl.box((xx, 0.65, zz), (0.022, 1.08, 0.055), 'orange')
    return posts
posts = rail_run(lambda z: 3.14 + jog(z), Z1, Z0)
rail_run(lambda z: -23.1, Z1, Z0)
rl_ob = rl.finalize(bevel=0.006, bevel_segs=1)
EXPORT.append(rl_ob)

# pipe rail on the curb (roadway side of the walkway)
pr = Mesh('pipe_rail')
z = Z1
while z > Z0 + 2.9:
    if abs(z - TZ) > 9.5:
        pr.tube([(-0.05, 0.1, z), (-0.05, 1.02, z)], 0.035, 10, 'orange', caps=True)
        pr.tube([(-0.05, 1.02, z), (-0.05, 1.02, z - 2.9)], 0.028, 10, 'orange', caps=True)
        pr.tube([(-0.05, 0.62, z), (-0.05, 0.62, z - 2.9)], 0.018, 8, 'orange', caps=True)
    z -= 2.9
pr_ob = pr.finalize(weighted=False)
EXPORT.append(pr_ob)

# lamp standards: a tall post at the outer railing, an arm curving in over the walkway, a lantern
lp = Mesh('lamps')
for zl in [45.0, 20.0, -5.0, -30.0, -84.0, -108.0]:
    x0 = 3.32 + jog(zl)
    lp.tube([(x0, 0.0, zl), (x0, 7.6, zl)], 0.085, 14, 'orange', caps=True, radii=[0.1, 0.075])
    lp.lathe([(0.0, 0.0), (0.2, 0.0), (0.18, 0.35), (0.1, 0.5), (0.0, 0.5)], 16, (x0, 0.0, zl), 'orange')
    arc = []
    for k in range(13):
        a = k / 12 * math.pi * 0.62
        arc.append((x0 - 1.15 * math.sin(a), 7.6 + 0.85 * (1 - math.cos(a)) + 0.4 * math.sin(a) * 0.3, zl))
    lp.tube(arc, 0.055, 10, 'orange', caps=True)
    hx, hy = arc[-1][0] - 0.1, arc[-1][1] - 0.05
    lp.lathe([(0.0, 0.0), (0.16, 0.02), (0.26, 0.14), (0.24, 0.22), (0.0, 0.26)], 18, (hx, hy - 0.22, zl), 'orange')
    lp.lathe([(0.0, 0.0), (0.2, 0.0), (0.16, 0.07), (0.0, 0.08)], 18, (hx, hy - 0.3, zl), 'lamp_glass')
    OUT['lamps'].append([hx, hy - 0.3, zl])
lp_ob = lp.finalize(weighted=False)
EXPORT.append(lp_ob)

# ═════════════════════════════════ CABLES + SUSPENDERS ═════════════════════════════════
cb = Mesh('main_cables')
for xc in CABLE_X:
    pts = []
    for k in range(121):
        z = Z1 + 10 - (Z1 + 10 - TZ) * k / 120
        pts.append((xc, cable_y(z) + 0.45, z))
    pts.append((xc, TOP + 1.8, TZ))
    cb.tube(pts, 0.46, 20, 'cable', caps=True)
    # beyond the tower the next span mirrors this one (into the fog)
    pts2 = [(xc, TOP + 1.8, TZ)]
    for k in range(1, 41):
        z = TZ - k * 3.0
        pts2.append((xc, cable_y(2 * TZ - z) + 0.45, z))
    cb.tube(pts2, 0.46, 20, 'cable', caps=True)
cb_ob = cb.finalize(weighted=False)
EXPORT.append(cb_ob)
sp = Mesh('suspenders')
z = LOW_Z + 16
while z > TZ + TD / 2 + 3:
    for xc in CABLE_X:
        yc = cable_y(z) + 0.45
        for dz in (-0.14, 0.14):
            sp.tube([(xc, yc, z + dz), (xc, 0.35, z + dz)], 0.034, 6, 'cable', caps=False)
        # cable band where the pair hangs, a socket at the deck
        sp.lathe([(0.52, -0.25), (0.56, -0.2), (0.56, 0.2), (0.52, 0.25)], 16, (xc, yc, z), 'orange')
        sp.box((xc, 0.35, z), (0.2, 0.25, 0.5), 'orange')
    OUT['suspenders'].append(z)
    z -= 8.0
sp_ob = sp.finalize(weighted=False)
EXPORT.append(sp_ob)
json.dump(OUT, open(ASSETS + '/bridge_layout.json', 'w'), indent=1)

if 'preview' in sys.argv:
    preview(ASSETS + '/../probes/bridge_prev.png', [((0.55, 0.95, 6.2), (1.2, 3.2, -30.0), 46),
                                                   ((0.9, 1.25, 4.9), (1.15, 20.0, -57.0), 44),
                                                   ((40.0, 30.0, 30.0), (-10.0, 30.0, -57.0), 50)], world=(0.7, 0.72, 0.75))
for o in bpy.data.objects:
    o.select_set(False)
for o in EXPORT:
    o.select_set(True)
bpy.ops.export_scene.gltf(filepath=ASSETS + '/bridge.glb', export_format='GLB', use_selection=True, export_apply=True,
                          export_yup=True, export_materials='EXPORT', export_animations=False)
print('[fx] exported bridge.glb', os.path.getsize(ASSETS + '/bridge.glb') // 1024, 'KB')
hard_exit()

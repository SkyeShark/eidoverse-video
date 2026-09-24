"""Two-person dome tent (2.1 x 1.5 m inner, fly apex 1.15 m) in three fly colours sharing ONE
geometry. The rainfly is a parametric membrane over two crossing aluminium poles (clips + apex hub),
sagging between them, with a front vestibule. Its D-shaped door is unzipped and HALF ROLLED UP -
the lower half open, the roll tied with two toggles - showing the darker inner tent's mesh door.
Hem 6 cm off the ground shows the inner tent's bathtub floor. Guy lines (shallow catenaries) run
to aluminium hook stakes; the pole corners are webbed to stakes.
Front (door) faces -Y. Origin: ground centre.
-> glb/camp_tent_dome_{orange,green,mustard}.glb ('Tent')
   baked/camp_tent_dome_<c>_glow.jpg = emissive-ready map (fly colour x single-layer transmission;
   seams/binding/zip/poles dark; the inner mesh door warm) - use as emissiveMap when lit inside.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector, Matrix, noise
from mathutils.bvhtree import BVHTree
from clib import *
from camp_lib import *

reset()
H = 1.15
AX, BY, NSE = 1.225, 0.868, 4.0         # superellipse through the pole corners (+-1.03, +-0.73)
VEST = 0.40                              # front vestibule reach
PHI_C = math.atan2(0.73, 1.03)
POLE_AZ = [PHI_C, math.pi - PHI_C, math.pi + PHI_C, math.tau - PHI_C]
HEM = 0.062
DOOR_A, DOOR_B, DOOR_Z0 = 0.40, 0.85, 0.06
ROLL_Z = 0.52
COLORS = {'orange': (0.80, 0.215, 0.028), 'green': (0.105, 0.26, 0.075), 'mustard': (0.66, 0.40, 0.045)}


def G(phi):
    c, s = math.cos(phi), math.sin(phi)
    by = BY + VEST * max(0.0, -s) ** 6
    r = (abs(c / AX) ** NSE + abs(s / by) ** NSE) ** (-1.0 / NSE)
    return r * c, r * s


def panel_of(phi):
    phi %= math.tau
    for k in range(4):
        a0 = POLE_AZ[k]
        a1 = POLE_AZ[(k + 1) % 4] + (math.tau if k == 3 else 0)
        pp = phi if phi >= a0 else phi + math.tau
        if a0 <= pp < a1:
            return k, (pp - a0) / (a1 - a0), (a0 + a1) / 2
    return 0, 0.0, 0.0


SAG = [0.045, 0.065, 0.045, 0.10]         # end, back, end, front(vestibule) panels


def surf(phi, s):
    gx, gy = G(phi)
    k, f, _ = panel_of(phi)
    w = math.sin(math.pi * f) ** 2
    sg = SAG[k] * w * math.sin(math.pi * min(1.0, s)) ** 1.3
    z = H * max(0.0, 1 - s ** 2.1) ** 0.58 - sg
    pull = 1 - 0.30 * sg / max(1e-6, H) * 4
    return Vector((s * gx * pull, s * gy * pull, z))


def hem_z(phi):
    d = min(abs(math.atan2(math.sin(phi - a), math.cos(phi - a))) for a in POLE_AZ)
    return 0.022 + (HEM - 0.022) * min(1.0, d / 0.22)


def s_hem(phi):
    lo, hi = 0.5, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if surf(phi, mid).z > hem_z(phi):
            lo = mid
        else:
            hi = mid
    return lo


def surf_normal(phi, s, e=1e-3):
    p = surf(phi, s)
    a = surf(phi + e, s) - p
    b = surf(phi, min(1.0, s + e)) - p
    n = a.cross(b).normalized()
    if n.dot(Vector((p.x, p.y, p.z - 0.3))) < 0:
        n = -n
    return n


# ================================================================================ the rainfly
NP, NS = 160, 44
bm = bmesh.new()
apex = bm.verts.new(surf(0, 0))
cols = []
merid = {}
for i in range(NP):
    phi = i / NP * math.tau
    sh = s_hem(phi)
    col = []
    acc = 0.0
    prev = surf(phi, 0)
    for j in range(1, NS + 1):
        s = sh * (j / NS) ** 0.92
        p = surf(phi, s)
        acc += (p - prev).length
        prev = p
        v = bm.verts.new(p)
        merid[v] = acc
        col.append(v)
    cols.append(col)
merid[apex] = 0.0
for i in range(NP):
    i2 = (i + 1) % NP
    bm.faces.new((apex, cols[i][0], cols[i2][0]))
    for j in range(NS - 1):
        bm.faces.new((cols[i][j], cols[i][j + 1], cols[i2][j + 1], cols[i2][j]))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
# make sure normals point outward (away from the tent interior)
bm.faces.ensure_lookup_table()
f0 = bm.faces[len(bm.faces) // 2]
if f0.normal.dot(f0.calc_center_median() - Vector((0, 0, 0.35))) < 0:
    bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
# panel-local metric TexUV: u across the panel (horizontal), v down the meridian
uvl = bm.loops.layers.uv.new('TexUV')
for f in bm.faces:
    c = f.calc_center_median()
    k, _, mid = panel_of(math.atan2(c.y, c.x))
    t = Vector((-math.sin(mid), math.cos(mid), 0))
    for l in f.loops:
        l[uvl].uv = (l.vert.co.dot(t), merid.get(l.vert, 0.0))


def fly_extra_factory(target):
    def fly_extra(nb, col, vec):
        oc = obj_coord(nb)
        x, y, z = sep_xyz(nb, oc)
        geo = nb.n('ShaderNodeNewGeometry')
        # weave luminance as a subtle modulation of the true fly colour
        bw = nb.n('ShaderNodeRGBToBW'); nb.l(col, bw.inputs[0])
        mod = nb.n('ShaderNodeMapRange'); nb.l(bw.outputs[0], mod.inputs['Value'])
        mod.inputs['From Min'].default_value = 0.10; mod.inputs['From Max'].default_value = 0.45
        mod.inputs['To Min'].default_value = 0.82; mod.inputs['To Max'].default_value = 1.12
        c = nb.mix(1.0, mod.outputs['Result'], tuple(target), 'MULTIPLY', clamp=False)
        # ripstop: a heavier thread every 7 mm (panel-local metric UV)
        uvn = nb.n('ShaderNodeUVMap', uv_map='TexUV'); sp = nb.n('ShaderNodeSeparateXYZ'); nb.l(uvn.outputs['UV'], sp.inputs[0])
        def line(t, pitch):
            fr = nb.math('FRACT', nb.math('DIVIDE', t, pitch))
            return ramp_s(nb, nb.math('ABSOLUTE', nb.math('SUBTRACT', fr, 0.5)), 0.40, 0.49)
        rip = nb.math('MAXIMUM', line(sp.outputs['X'], 0.010), line(sp.outputs['Y'], 0.010))
        c = nb.mix(nb.math('MULTIPLY', rip, 0.05), c, (0.9, 0.9, 0.9), 'MULTIPLY')
        # taped panel seams under the poles (vertical planes through the diagonals)
        seam = None
        for a in (PHI_C, math.pi - PHI_C):
            d = nb.math('ABSOLUTE', nb.math('SUBTRACT', nb.math('MULTIPLY', x, math.sin(a)), nb.math('MULTIPLY', y, math.cos(a))))
            m = ramp_s(nb, d, 0.011, 0.006)
            seam = m if seam is None else nb.math('MAXIMUM', seam, m)
        c = nb.mix(nb.math('MULTIPLY', seam, 0.35), c, (0.0, 0.0, 0.0))
        stitch = nb.math('MULTIPLY', seam, ramp_s(nb, nb.math('ABSOLUTE', nb.math('SUBTRACT', nb.math('FRACT', nb.math('MULTIPLY', z, 260.0)), 0.5)), 0.2, 0.3))
        c = nb.mix(nb.math('MULTIPLY', stitch, 0.25), c, (0.95, 0.95, 0.9))
        # hem binding
        bind = ramp_s(nb, z, 0.092, 0.084)
        c = nb.mix(nb.math('MULTIPLY', bind, 0.7), c, (0.02, 0.02, 0.02))
        # door zipper tape along the D (front only)
        front = ramp_s(nb, y, -0.55, -0.75)
        ex = nb.math('DIVIDE', x, DOOR_A); ez = nb.math('DIVIDE', nb.math('SUBTRACT', z, DOOR_Z0), DOOR_B)
        ell = nb.math('SQRT', nb.math('ADD', nb.math('MULTIPLY', ex, ex), nb.math('MULTIPLY', ez, ez)))
        zipd = nb.math('ABSOLUTE', nb.math('SUBTRACT', ell, 1.0))
        zipm = nb.math('MULTIPLY', ramp_s(nb, zipd, 0.022, 0.012), front)
        c = nb.mix(zipm, c, (0.015, 0.015, 0.016))
        # sun-bleached top
        nz = sep_xyz(nb, geo.outputs['Normal'])[2]
        bleach = nb.math('MULTIPLY', ramp_s(nb, nz, 0.45, 0.95), 0.10)
        c = nb.mix(bleach, c, (0.75, 0.72, 0.66))
        # water stains and streaks on the lower panels
        wv = nb.n('ShaderNodeMapping'); wv.inputs['Scale'].default_value = (7.0, 7.0, 0.8); nb.l(oc, wv.inputs['Vector'])
        streak = nb.math('MULTIPLY', ramp_s(nb, nb.noise(wv.outputs[0], 3.0, 4.0, 0.55), 0.58, 0.72), ramp_s(nb, z, 0.8, 0.3))
        c = nb.mix(nb.math('MULTIPLY', streak, 0.18), c, (0.25, 0.22, 0.18))
        # dirt splash + grass stains near the hem
        dirt = nb.math('MULTIPLY', ramp_s(nb, nb.math('ADD', z, nb.math('MULTIPLY', nb.noise(oc, 8.0, 4.0, 0.6), 0.14)), 0.34, 0.12),
                       ramp_s(nb, nb.noise(oc, 24.0, 3.0, 0.6), 0.25, 0.65))
        c = nb.mix(nb.math('MULTIPLY', dirt, 0.65), c, (0.13, 0.095, 0.06))
        grass = nb.math('MULTIPLY', ramp_s(nb, z, 0.16, 0.06), ramp_s(nb, nb.noise(oc, 70.0, 2.0, 0.5), 0.64, 0.70))
        c = nb.mix(nb.math('MULTIPLY', grass, 0.7), c, (0.10, 0.20, 0.04))
        return c
    return fly_extra


def fly_glow_factory(target):
    def fly_glow(nb):
        oc = obj_coord(nb)
        x, y, z = sep_xyz(nb, oc)
        base = nb.n('ShaderNodeRGB'); base.outputs[0].default_value = (min(1, target[0] * 1.25 + 0.06), min(1, target[1] * 1.25 + 0.05), min(1, target[2] * 1.25 + 0.03), 1)
        g = base.outputs[0]
        seam = None
        for a in (PHI_C, math.pi - PHI_C):
            d = nb.math('ABSOLUTE', nb.math('SUBTRACT', nb.math('MULTIPLY', x, math.sin(a)), nb.math('MULTIPLY', y, math.cos(a))))
            m = ramp_s(nb, d, 0.011, 0.006)
            seam = m if seam is None else nb.math('MAXIMUM', seam, m)
        g = nb.mix(nb.math('MULTIPLY', seam, 0.55), g, (0, 0, 0))
        g = nb.mix(ramp_s(nb, z, 0.092, 0.084), g, (0, 0, 0))
        front = ramp_s(nb, y, -0.55, -0.75)
        ex = nb.math('DIVIDE', x, DOOR_A); ez = nb.math('DIVIDE', nb.math('SUBTRACT', z, DOOR_Z0), DOOR_B)
        ell = nb.math('SQRT', nb.math('ADD', nb.math('MULTIPLY', ex, ex), nb.math('MULTIPLY', ez, ez)))
        g = nb.mix(nb.math('MULTIPLY', ramp_s(nb, nb.math('ABSOLUTE', nb.math('SUBTRACT', ell, 1.0)), 0.022, 0.012), front), g, (0, 0, 0))
        low = ramp_s(nb, z, 0.30, 0.10)
        return nb.mix(nb.math('MULTIPLY', low, 0.45), g, (0, 0, 0))
    return fly_glow


def make_fly_mat(name, target):
    m = layered_mat(name, 'Fabric061', scale=9.0, rough_mul=0.9, rough_add=0.12, nstr=0.6,
                    extra_color=fly_extra_factory(target),
                    grime=dict(color=(0.05, 0.045, 0.04), dist=0.05, amount=0.35, gain=1.2))
    def rip_h(nb):
        uvn = nb.n('ShaderNodeUVMap', uv_map='TexUV'); sp = nb.n('ShaderNodeSeparateXYZ'); nb.l(uvn.outputs['UV'], sp.inputs[0])
        def line(t, pitch):
            fr = nb.math('FRACT', nb.math('DIVIDE', t, pitch))
            return ramp_s(nb, nb.math('ABSOLUTE', nb.math('SUBTRACT', fr, 0.5)), 0.40, 0.49)
        rip = nb.math('MAXIMUM', line(sp.outputs['X'], 0.010), line(sp.outputs['Y'], 0.010))
        # tension wrinkles: long soft ridges running down the panels
        oc = obj_coord(nb)
        wm = nb.n('ShaderNodeMapping'); wm.inputs['Scale'].default_value = (14.0, 14.0, 2.2); nb.l(oc, wm.inputs['Vector'])
        wr = nb.math('MULTIPLY', nb.noise(wm.outputs[0], 1.0, 3.0, 0.5), 6.0)
        return nb.math('ADD', nb.math('MULTIPLY', rip, 0.15), wr)
    add_bump(m, rip_h, strength=0.12, distance=0.0012)
    set_glow(m, fly_glow_factory(target))
    return m


def make_fly_inner_mat(name, target):
    """The fly's underside: silver-grey PU coating over the dyed nylon (seen inside the vestibule)."""
    tc = tuple(0.40 * t + 0.16 for t in target)
    def inner_col(nb, c, v):
        bw = nb.n('ShaderNodeRGBToBW'); nb.l(c, bw.inputs[0])
        mod = nb.n('ShaderNodeMapRange'); nb.l(bw.outputs[0], mod.inputs['Value'])
        mod.inputs['From Min'].default_value = 0.10; mod.inputs['From Max'].default_value = 0.45
        mod.inputs['To Min'].default_value = 0.88; mod.inputs['To Max'].default_value = 1.08
        return nb.mix(1.0, mod.outputs['Result'], tc, 'MULTIPLY', clamp=False)
    m = layered_mat(name, 'Fabric061', scale=9.0, rough_mul=0.8, rough_add=0.05, nstr=0.4, extra_color=inner_col,
                    grime=dict(color=(0.05, 0.045, 0.04), dist=0.05, amount=0.4, gain=1.2))
    set_glow(m, lambda nb: tuple(min(1.0, 0.35 * t + 0.03) for t in target))
    return m


FIRST = 'orange'
m_fly = make_fly_mat('fly', COLORS[FIRST])
m_fly_in = make_fly_inner_mat('fly_in', COLORS[FIRST])
fly = obj_from_bm('fly', bm, m_fly)
smooth(fly, 40)
fly.data.materials.append(m_fly_in)
sol = fly.modifiers.new('solid', 'SOLIDIFY')
sol.thickness = 0.0015
sol.offset = -1.0
sol.use_rim = True
sol.use_even_offset = True
sol.material_offset = 1
sol.material_offset_rim = 0
apply_mods(fly)

# ---- door: cut the lower half of the D out of the vestibule panel (hole-tolerant boolean)
bm = bmesh.new()
pts = []
for k in range(33):
    t = k / 32
    zz = -0.15 + t * (ROLL_Z + 0.15)
    zc = max(zz, DOOR_Z0)
    xx = DOOR_A * math.sqrt(max(0.0, 1 - ((zc - DOOR_Z0) / DOOR_B) ** 2))
    pts.append((xx, zz))
outline = [(x, z) for x, z in pts] + [(-x, z) for x, z in reversed(pts)]
front_vs = [bm.verts.new((x, -2.2, z)) for x, z in outline]
back_vs = [bm.verts.new((x, -0.72, z)) for x, z in outline]
n = len(outline)
bm.faces.new(front_vs)
bm.faces.new(list(reversed(back_vs)))
for i in range(n):
    j = (i + 1) % n
    bm.faces.new((front_vs[i], front_vs[j], back_vs[j], back_vs[i]))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
cutter = obj_from_bm('door_cut', bm)
bo = fly.modifiers.new('door', 'BOOLEAN')
bo.operation = 'DIFFERENCE'; bo.object = cutter; bo.solver = 'EXACT'
apply_mods(fly)
bpy.data.objects.remove(cutter)

# BVH of the fly for seating hardware on the membrane
dg = bpy.context.evaluated_depsgraph_get()
bvh = BVHTree.FromObject(fly, dg)


def on_fly_front(x, z):
    hit = bvh.ray_cast(Vector((x, -3.0, z)), Vector((0, 1, 0)))
    return hit[0], hit[1]


parts = [fly]
G_POLE, G_GROUND, G_DOOR = [], [], []

# ================================================================================ inner tent
AXI, BYI, NI = 1.02, 0.72, 5.0


def Gi(phi):
    c, s = math.cos(phi), math.sin(phi)
    r = (abs(c / AXI) ** NI + abs(s / BYI) ** NI) ** (-1.0 / NI)
    return r * c, r * s


def isurf(phi, s):
    gx, gy = Gi(phi)
    return Vector((s * gx, s * gy, 1.02 * max(0.0, 1 - s ** 2.6) ** 0.5))


# shrink the inner tent until it clears the fly by >= 4 cm everywhere
scale_i = 1.0
for it in range(30):
    ok = True
    for i in range(0, 72):
        phi = i / 72 * math.tau
        for s in (0.3, 0.55, 0.75, 0.9, 0.97):
            p = isurf(phi, s) * 1.0
            p = Vector((p.x * scale_i, p.y * scale_i, p.z * scale_i))
            hit = bvh.ray_cast(Vector((0, 0, 0.3)), (p - Vector((0, 0, 0.3))).normalized())
            if hit[0] is not None and (hit[0] - Vector((0, 0, 0.3))).length < (p - Vector((0, 0, 0.3))).length + 0.04:
                ok = False
    if ok:
        break
    scale_i *= 0.985
print('[tent] inner tent scale %.3f' % scale_i)
m_mesh = layered_mat('inner_mesh', 'Fabric062', scale=14.0, tint=(0.09, 0.09, 0.095), rough_add=0.2, nstr=0.8)
m_floor = layered_mat('inner_floor', 'Fabric061', scale=9.0, tint=(0.07, 0.07, 0.075), rough_mul=0.7, nstr=0.5,
                      extra_color=lambda nb, c, v: nb.mix(nb.math('MULTIPLY', ramp_s(nb, nb.noise(obj_coord(nb), 20.0, 3.0, 0.6), 0.5, 0.7), 0.6), c, (0.12, 0.09, 0.06)))
set_glow(m_mesh, lambda nb: nb.mix(ramp_s(nb, sep_xyz(nb, obj_coord(nb))[2], 0.10, 0.16), (0.08, 0.06, 0.04), (0.95, 0.78, 0.52)))
set_glow(m_floor, lambda nb: (0.05, 0.04, 0.03))
bm = bmesh.new()
ni, nsi = 96, 22
ictr = bm.verts.new(isurf(0, 0) * scale_i)
icol = []
for i in range(ni):
    phi = i / ni * math.tau
    icol.append([bm.verts.new(isurf(phi, j / nsi) * scale_i) for j in range(1, nsi + 1)])
for i in range(ni):
    i2 = (i + 1) % ni
    f = bm.faces.new((ictr, icol[i][0], icol[i2][0])); f.material_index = 0
    for j in range(nsi - 1):
        f = bm.faces.new((icol[i][j], icol[i][j + 1], icol[i2][j + 1], icol[i2][j]))
        f.material_index = 1 if f.calc_center_median().z < 0.13 else 0
floor = bm.faces.new([icol[i][-1] for i in range(ni)])
floor.material_index = 1
bmesh.ops.triangulate(bm, faces=[floor])
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
inner = obj_from_bm('inner', bm)
inner.data.materials.append(m_mesh)
inner.data.materials.append(m_floor)
smooth(inner, 40)
uv_tex(inner, 1.0)

# ================================================================================ poles & clips
m_pole = layered_mat('pole', 'Metal032', scale=10.0, tint=(0.62, 0.66, 0.60), metal=1.0, rough_add=0.18,
                     wear=dict(color=(0.75, 0.76, 0.74), radius=0.001, amount=0.8, rough=0.25, metal=1.0, gain=20),
                     grime=dict(color=(0.1, 0.09, 0.08), dist=0.01, amount=0.5))
m_plas = layered_mat('plastic', 'Plastic012B', scale=14.0, tint=(1.2, 1.2, 1.2), rough_add=0.15,
                     wear=dict(color=(0.14, 0.14, 0.14), radius=0.0008, amount=0.7, rough=0.5, gain=22))
m_cord = layered_mat('cord', 'Rope001', scale=40.0, tint=(0.85, 0.82, 0.76), sat=0.3, rough_add=0.1, nstr=0.8)
m_stake = layered_mat('stake', 'Metal049A', scale=12.0, tint=(0.62, 0.63, 0.64), metal=1.0, rough_add=0.35,
                      extra_color=lambda nb, c, v: nb.mix(ramp_s(nb, sep_xyz(nb, obj_coord(nb))[2], 0.03, 0.0), c, (0.12, 0.09, 0.06)))
m_web = layered_mat('webbing', 'Fabric061', scale=14.0, tint=(0.08, 0.08, 0.085), rough_add=0.2, nstr=0.9)
for m in (m_pole, m_plas, m_cord, m_stake, m_web):
    set_glow(m, lambda nb: (0.0, 0.0, 0.0))

POLE_R = 0.0048
corners = []
for pi_, (a0, a1) in enumerate(((POLE_AZ[0], POLE_AZ[2]), (POLE_AZ[1], POLE_AZ[3]))):
    pts = []
    for az, rng_ in ((a0, range(40, -1, -1)), (a1, range(1, 41))):
        sh = s_hem(az)
        for j in rng_:
            s = sh * (j / 40)
            p = surf(az, s)
            nrm = surf_normal(az, max(s, 0.02))
            lift = POLE_R + 0.0035 + (0.0105 if (pi_ == 1 and s < 0.12) else 0.0) * max(0.0, 1 - s / 0.12)
            pts.append(p + nrm * lift)
    # run each end on down into its corner grommet
    for end in (0, -1):
        p = pts[end]
        g = Vector((p.x * 1.035, p.y * 1.035, 0.028))
        if end == 0:
            pts.insert(0, g)
        else:
            pts.append(g)
        corners.append(g)
    po = tube_obj(f'pole{pi_}', pts, POLE_R, m_pole, bevel_res=2)
    G_POLE.append(po)
    # shock-cord ferrules every ~0.45 m and snap clips every ~0.22 m of arc
    acc, nextf, nextc = 0.0, 0.40, 0.20
    for k in range(1, len(pts)):
        acc += (pts[k] - pts[k - 1]).length
        d = (pts[k] - pts[k - 1]).normalized()
        if acc > nextf:
            fe = tube_obj('ferrule', [tuple(pts[k] - d * 0.009), tuple(pts[k] + d * 0.009)], POLE_R + 0.0009, m_pole, bevel_res=1)
            G_POLE.append(fe)
            nextf += 0.45
        if acc > nextc and pts[k].z > 0.2 and abs(pts[k].x) + abs(pts[k].y) > 0.12:
            cl = tube_obj('clip', [tuple(pts[k] - d * 0.011), tuple(pts[k] + d * 0.011)], POLE_R + 0.0028, m_plas, bevel_res=1)
            G_POLE.append(cl)
            # the clip's hook down onto the fly
            q = pts[k]
            phi = math.atan2(q.y, q.x)
            nrm = Vector((q.x, q.y, q.z - 0.2)).normalized()
            hook = tube_obj('clip_hook', [tuple(q - nrm * 0.004), tuple(q - nrm * (POLE_R + 0.0062))], 0.0022, m_plas, bevel_res=1)
            G_POLE.append(hook)
            nextc += 0.22
# apex hub
hub = lathe_obj('hub', [(0.0001, -0.006), (0.016, -0.006), (0.018, -0.002), (0.017, 0.004), (0.010, 0.008), (0.0001, 0.009)], 24, m_plas)
hub.location = surf(0, 0) + Vector((0, 0, POLE_R * 2 + 0.006))
select_only(hub); bpy.ops.object.transform_apply(location=True)
G_POLE.append(hub)


# ================================================================================ stakes & lines
def stake(base, away):
    """Aluminium hook stake driven at ~65 deg, leaning away from the pull. Returns the hook point."""
    away = Vector((away.x, away.y, 0)).normalized()
    top = base + away * 0.022 + Vector((0, 0, 0.05))
    bot = base - away * 0.004 - Vector((0, 0, 0.012))
    G_GROUND.append(tube_obj('stake', [tuple(bot), tuple(top)], 0.0028, m_stake, bevel_res=1))
    hk = [top]
    for k in range(1, 9):
        a = k / 8 * math.pi
        hk.append(top + Vector((0, 0, 0.008 * math.sin(a))) - away * (0.012 * (1 - math.cos(a)) / 2 * 2))
    G_GROUND.append(tube_obj('stake_hook', [tuple(p) for p in hk], 0.0026, m_stake, bevel_res=1))
    return top - away * 0.006 + Vector((0, 0, 0.004))


for g in corners:
    out = Vector((g.x, g.y, 0)).normalized()
    hkp = stake(Vector((g.x, g.y, 0)) + out * 0.11, out)
    # flat webbing strap from the grommet to the stake hook
    a, b = g + Vector((0, 0, -0.004)), hkp
    d = (b - a); d.z = 0; d.normalize()
    side = d.cross(Vector((0, 0, 1))).normalized() * 0.0095
    bmw = bmesh.new()
    vs = [bmw.verts.new(p) for p in (a - side, a + side, b + side, b - side)]
    bmw.faces.new(vs)
    web = obj_from_bm('web', bmw, m_web)
    sol = web.modifiers.new('s', 'SOLIDIFY'); sol.thickness = 0.0016
    apply_mods(web)
    G_GROUND.append(web)
    # grommet ring the pole tip sits in
    gr = lathe_obj('grommet', [(0.0035, -0.001), (0.0068, -0.001), (0.0072, 0.0015), (0.0035, 0.0015)], 20, m_stake)
    gr.location = g + Vector((0, 0, -0.004)); select_only(gr); bpy.ops.object.transform_apply(location=True)
    G_GROUND.append(gr)

for az in (0.0, math.pi, math.pi / 2, math.radians(300), math.radians(240)):
    sh = s_hem(az)
    lo, hi = 0.3, sh
    for _ in range(30):
        mid = (lo + hi) / 2
        if surf(az, mid).z > 0.62: lo = mid
        else: hi = mid
    ap = surf(az, lo)
    nrm = surf_normal(az, lo)
    # webbing guy-out loop sewn onto the fly
    G_GROUND.append(tube_obj('guy_loop', [tuple(ap + nrm * 0.002 + Vector((0, 0, 0.012))), tuple(ap + nrm * 0.012),
                                       tuple(ap + nrm * 0.002 - Vector((0, 0, 0.012)))], 0.0025, m_web, bevel_res=1))
    gx, gy = G(az)
    out = Vector((gx, gy, 0)).normalized()
    base = Vector((gx, gy, 0)) + out * 0.85
    hkp = stake(base, out)
    a = ap + nrm * 0.012
    cat = catenary(a, hkp, 0.012, 28)
    G_GROUND.append(tube_obj('guy', [tuple(p) for p in cat], 0.0015, m_cord, bevel_res=1))
    # line tensioner slider a hand's width above the stake
    tp = cat[-4]
    G_GROUND.append(tube_obj('tensioner', [tuple(tp + (cat[-5] - tp) * 0.5), tuple(tp)], 0.004, m_plas, bevel_res=1))

# ================================================================================ roll + zip + ties
roll_pts = []
for k in range(25):
    x = -0.345 + 0.69 * k / 24
    hit, nrm = on_fly_front(x, ROLL_Z + 0.03)
    if hit is None:
        continue
    roll_pts.append((hit, nrm))
rr_ = 0.032
rp = [tuple(h + n_ * (rr_ * 0.9) - Vector((0, 0, 0.012))) for h, n_ in roll_pts]
m_rollmat = m_fly
roll = tube_obj('roll', rp, rr_, m_fly, bevel_res=4)
G_DOOR.append(roll)
# zipper chain up and over the D above the roll
zp = []
for k in range(61):
    a = -math.pi / 2 + math.pi * k / 60
    ex = DOOR_A * math.sin(a)
    ez = DOOR_Z0 + DOOR_B * math.cos(a)
    if ez < ROLL_Z + 0.02:
        continue
    hit, nrm = on_fly_front(ex, ez)
    if hit is not None:
        zp.append(hit + nrm * 0.0022)
G_DOOR.append(tube_obj('zip', [tuple(p) for p in zp], 0.0024, m_web, bevel_res=1))
# the two open zip edges hanging below the roll + a pull tab on the right
for sx in (-1, 1):
    ez = ROLL_Z - 0.01
    ex = sx * DOOR_A * math.sqrt(max(0, 1 - ((ez - DOOR_Z0) / DOOR_B) ** 2))
    hit, nrm = on_fly_front(ex + sx * 0.012, ez)
    if hit is not None:
        side = [hit + nrm * 0.002]
        for k in range(1, 12):
            zz = ez - k * 0.04
            xx = sx * DOOR_A * math.sqrt(max(0, 1 - ((max(zz, DOOR_Z0) - DOOR_Z0) / DOOR_B) ** 2)) + sx * 0.012
            h2, n2 = on_fly_front(xx, zz)
            if h2 is None:
                break
            side.append(h2 + n2 * 0.002)
        if len(side) > 1:
            G_DOOR.append(tube_obj('zip_edge', [tuple(p) for p in side], 0.0022, m_web, bevel_res=1))
    if sx > 0 and zp:
        tab_top = zp[-1] + Vector((0, -0.004, -0.004))
        G_DOOR.append(tube_obj('pull', [tuple(tab_top), tuple(tab_top + Vector((0.004, -0.006, -0.028)))], 0.0035, m_plas, bevel_res=1))
# toggle ties around the roll
for tx in (-0.20, 0.20):
    hit, nrm = on_fly_front(tx, ROLL_Z + 0.03)
    if hit is None:
        continue
    c = hit + nrm * (rr_ * 0.9) - Vector((0, 0, 0.012))
    loop = []
    for k in range(25):
        a = k / 24 * math.tau
        loop.append(c + nrm * (rr_ + 0.003) * math.cos(a) + Vector((0, 0, (rr_ + 0.003) * math.sin(a))))
    G_DOOR.append(tube_obj('tie', [tuple(p) for p in loop] + [tuple(hit + Vector((0, 0, 0.09)))], 0.0028, m_web, bevel_res=1))
    tg = lathe_obj('toggle', [(0.0001, -0.012), (0.0035, -0.011), (0.004, 0.0), (0.0035, 0.011), (0.0001, 0.012)], 12, m_plas)
    tg.rotation_euler = (0, math.radians(90), 0)
    tg.location = c + nrm * (rr_ + 0.006) + Vector((0, 0, rr_ * 0.6))
    select_only(tg); bpy.ops.object.transform_apply(location=True, rotation=True)
    G_DOOR.append(tg)

def keep_texuv(o, cube=0.2):
    for uvn in list(o.data.uv_layers):
        if uvn.name != 'TexUV':
            o.data.uv_layers.remove(uvn)
    if 'TexUV' not in o.data.uv_layers:
        uv_tex(o, cube)


def pack_group(objs, name, u0, v0, size, margin=0.004):
    for o in objs:
        keep_texuv(o)
    o = join(objs, name) if len(objs) > 1 else objs[0]
    uv_bake(o, margin=margin, angle=58)
    for d in o.data.uv_layers['BakeUV'].data:
        d.uv = (u0 + d.uv.x * size, v0 + d.uv.y * size)
    return o


select_only(fly)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='DESELECT')
fly.active_material_index = 1
bpy.ops.object.material_slot_select()
bpy.ops.mesh.separate(type='SELECTED')
bpy.ops.object.mode_set(mode='OBJECT')
fly_in = [o for o in bpy.context.selected_objects if o is not fly][0]
fly_in.name = 'fly_in'
print('[tent] skins: outer %d faces, inner %d faces' % (len(fly.data.polygons), len(fly_in.data.polygons)))
grp = [pack_group([fly], 'g_fly', 0.0, 0.26, 0.74, 0.003),
       pack_group([fly_in], 'g_fly_in', 0.26, 0.0, 0.26, 0.004),
       pack_group([inner], 'g_inner', 0.0, 0.0, 0.26, 0.006),
       pack_group(G_POLE, 'g_pole', 0.74, 0.74, 0.26, 0.006),
       pack_group(G_GROUND, 'g_ground', 0.74, 0.48, 0.26, 0.006),
       pack_group(G_DOOR, 'g_door', 0.74, 0.22, 0.26, 0.006)]
T = join(grp, 'Tent')
for uvn in list(T.data.uv_layers):
    if uvn.name not in ('TexUV', 'BakeUV'):
        T.data.uv_layers.remove(uvn)

# ---- bake the first colour fully, then only colour + glow for the others (shared ORM/normal)
imgs, em = bake_all(T, f'camp_tent_dome_{FIRST}', size=2048, samples=40, ao_dist=0.25)
glows = {FIRST: bake_glow(T, f'camp_tent_dome_{FIRST}', size=2048, samples=8)}
color_imgs = {FIRST: os.path.join(BAKED, f'camp_tent_dome_{FIRST}_color.jpg')}
for cname, target in COLORS.items():
    if cname == FIRST:
        continue
    mv = make_fly_mat('fly_' + cname, target)
    mvi = make_fly_inner_mat('fly_in_' + cname, target)
    slot = next(i for i, s in enumerate(T.material_slots) if s.material and s.material.name == 'fly')
    slot_i = next(i for i, s in enumerate(T.material_slots) if s.material and s.material.name == 'fly_in')
    T.material_slots[slot].material = mv
    T.material_slots[slot_i].material = mvi
    im = bake(T, f'camp_tent_dome_{cname}', size=2048, maps=('color',), samples=24)
    color_imgs[cname] = os.path.join(BAKED, f'camp_tent_dome_{cname}_color.jpg')
    glows[cname] = bake_glow(T, f'camp_tent_dome_{cname}', size=2048, samples=8)
    T.material_slots[slot].material = m_fly
    T.material_slots[slot_i].material = m_fly_in

T.name = 'Tent_src'
variants = {}
for cname in COLORS:
    o = dup(T, f'Tent_{cname}')
    m = em.copy()
    m.name = f'camp_tent_dome_{cname}_baked'
    for nd in m.node_tree.nodes:
        if nd.type == 'TEX_IMAGE' and nd.image and nd.image.filepath_raw.endswith(f'camp_tent_dome_{FIRST}_color.jpg'):
            nd.image = load_img(color_imgs[cname])
    add_emissive(m, glows[cname], strength=0.0)       # emissiveTexture on, factor 0: the engine lights it
    m.use_backface_culling = False                     # single-skin membrane: both faces render
    swap_to(o, m)
    o.name = 'Tent'
    variants[cname] = o
    for other in variants.values():
        if other is not o:
            other.name = 'Tent_tmp'
    export_glb([o], f'camp_tent_dome_{cname}.glb')
    o.name = f'Tent_{cname}'
    o.hide_render = True

# ---- look-loop
bpy.data.objects.remove(T)
g = ground_plane(7.0)
for cname, o in variants.items():
    o.hide_render = False
    for other in variants.values():
        other.hide_render = other is not o
    if cname == FIRST:
        preview([o], f'tent_dome_{cname}', height=0.35)
        lit_shot(f'tent_dome_{cname}_door', (0.55, -2.35, 0.75), (0.0, -0.9, 0.45), lens=40, size=768)
        lit_shot(f'tent_dome_{cname}_corner', (1.9, -1.2, 0.35), (1.1, -0.6, 0.12), lens=45, size=768)
    else:
        lit_shot(f'tent_dome_{cname}', (2.6, -3.2, 1.5), (0.0, 0.0, 0.5), lens=35, size=768)

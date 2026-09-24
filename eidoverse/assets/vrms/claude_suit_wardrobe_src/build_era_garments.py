"""RECIPE (as run for the DAISY music video, 2026-09). Its stage inputs were working files that are not kept
here; claude_suit_wardrobe.blend is the finished, editable result. Read README.md in this folder first.

Era garments for digi's claudesona — the Blender half of the DAISY wardrobe (props/wardrobe.js is the other).

    bash run_blender.sh eidoverse/assets/vrms/claude_suit_wardrobe_src/build_era_garments.py

Loads cyclist_acc.blend (suit + 1890s cyclist + era accessories) and adds:
  jersey collar   the jersey's roll neck split into its own material `jersey_collar` (the hoodie hides it)
  coat_skirt      a knee-length skirt worn under the jacket — digi's jacket is a CUTAWAY (hem 0.84 m at the back,
                  ~1.1 at the front), so the skirt is its own piece, material `Jacket` so every paint matches:
                  the 1961 lab coat, the funeral overcoat
  shirt_rolled    the shirt with its sleeves rolled just below the elbow (verse 3, by the ocean)
  acc_hoodie      a hood lying down on the upper back, a kangaroo pocket and drawstrings (2016)
  acc_patches     three embroidered patches on the jacket, tex_baked/patches_atlas.png (the march)
  acc_boutonniere a daisy on the left lapel (the funeral)
Every skinned piece takes its weights from what it lies on (nearest vertex of the jacket / jersey), except the skirt,
whose weights are written: hips at the waist, blending into each thigh toward the knee so it swings with the legs.
Saved era_wardrobe.blend (now claude_suit_wardrobe.blend) and exported the VRM. Review in the engine:
    python vrm_turntable.py --outfits lab_coat_1961,mourning,march,sleeves_rolled,hoodie_2016 --frames head,body
"""
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector, kdtree
from mathutils.bvhtree import BVHTree

bpy.ops.preferences.addon_enable(module='bl_ext.blender_org.vrm')
REPO = os.path.dirname(os.path.abspath(__file__))
while REPO != os.path.dirname(REPO) and not os.path.exists(os.path.join(REPO, 'eido.py')):
    REPO = os.path.dirname(REPO)
BL = os.path.dirname(os.path.abspath(__file__))
TEXB = os.path.join(BL, 'tex_baked')


def log(*a):
    print('[garm]', *a, flush=True)


def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def mat_flat(name, rgb, outline=0.004, double_sided=False):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    ext = m.vrm_addon_extension.mtoon1
    ext.enabled = True
    ext.pbr_metallic_roughness.base_color_factor = (*rgb, 1.0)
    mt = ext.extensions.vrmc_materials_mtoon
    mt.shade_color_factor = tuple(c * 0.58 for c in rgb)
    mt.outline_width_mode = 'worldCoordinates' if outline > 0 else 'none'
    mt.outline_width_factor = outline
    mt.outline_color_factor = tuple(c * 0.25 for c in rgb)
    mt.outline_lighting_mix_factor = 0.0
    mt.parametric_rim_color_factor = (0.0, 0.0, 0.0)
    ext.double_sided = double_sided
    return m


def world_verts(o):
    W = o.matrix_world
    return [W @ v.co for v in o.data.vertices]


def bvh_of(o):
    return BVHTree.FromPolygons(world_verts(o), [tuple(p.vertices) for p in o.data.polygons])


def weight_table(src):
    names = {g.index: g.name for g in src.vertex_groups}
    return [[(names[g.group], g.weight) for g in v.groups if g.weight > 1e-4] for v in src.data.vertices]


def copy_weights(dst, src, kd, table):
    """every dst vertex takes the skin weights of the nearest src vertex"""
    groups = {}
    W = dst.matrix_world
    for v in dst.data.vertices:
        _, i, _ = kd.find(W @ v.co)
        for name, w in table[i]:
            g = groups.get(name) or dst.vertex_groups.get(name) or dst.vertex_groups.new(name=name)
            groups[name] = g
            g.add([v.index], w, 'REPLACE')


def kd_of(pts):
    kd = kdtree.KDTree(len(pts))
    for i, p in enumerate(pts):
        kd.insert(p, i)
    kd.balance()
    return kd


def new_object(name, bm, materials, arm, smooth=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    o = bpy.data.objects.new(name, me)
    bpy.data.objects['shirt'].users_collection[0].objects.link(o)
    for m in materials:
        me.materials.append(m)
    return o


def skin_to(o, arm):
    o.parent = arm
    o.matrix_parent_inverse = arm.matrix_world.inverted()
    mod = o.modifiers.new('Armature', 'ARMATURE')
    mod.object = arm


def bone_parent(o, arm, bone):
    mw = o.matrix_world.copy()
    o.parent = arm
    o.parent_type = 'BONE'
    o.parent_bone = bone
    bpy.context.view_layer.update()
    o.matrix_world = mw


def solidify(o, thickness, offset=-1.0):
    for ob in bpy.context.view_layer.objects:
        ob.select_set(False)
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    mod = o.modifiers.new('Solidify', 'SOLIDIFY')
    mod.thickness = thickness
    mod.offset = offset
    mod.use_even_offset = True
    bpy.ops.object.modifier_apply(modifier=mod.name)


def dup(name, newname):
    src = bpy.data.objects[name]
    o = src.copy()
    o.data = src.data.copy()
    o.name = newname
    o.data.name = newname
    for c in src.users_collection:
        c.objects.link(o)
    return o


# ------------------------------------------------------------------------------------------ jersey collar
def split_jersey_collar():
    o = bpy.data.objects['jersey']
    W = o.matrix_world
    bm = bmesh.new()
    bm.from_mesh(o.data)
    lip = [e for e in bm.edges if e.is_boundary and all((W @ v.co).z > 1.25 and abs((W @ v.co).x) < 0.15 for v in e.verts)]
    ring0 = {v for e in lip for v in e.verts}
    rowB = {f for v in ring0 for f in v.link_faces}                     # the folded lip
    ring1 = {v for f in rowB for v in f.verts}
    collar = {f for v in ring1 for f in v.link_faces}                   # + the upright roll
    src = bpy.data.materials['jersey']
    mc = bpy.data.materials.get('jersey_collar') or src.copy()
    mc.name = 'jersey_collar'
    if 'jersey_collar' not in [m.name for m in o.data.materials]:
        o.data.materials.append(mc)
    k = [m.name for m in o.data.materials].index('jersey_collar')
    for f in collar:
        f.material_index = k
    bm.to_mesh(o.data)
    bm.free()
    log('jersey collar: lip edges', len(lip), 'faces', len(collar))


# ------------------------------------------------------------------------------------------ coat skirt
def build_coat_skirt(arm):
    body = bpy.data.objects['BodyActual']
    names = {g.index: g.name for g in body.vertex_groups}
    Wb = body.matrix_world
    skin = [Wb @ v.co for v in body.data.vertices
            if not any(names[g.group].lower().startswith('tail') and g.weight > 0.3 for g in v.groups)]
    pants = world_verts(bpy.data.objects['pants'])
    jacket = world_verts(bpy.data.objects['jacket'])
    knee = (arm.matrix_world @ arm.data.bones['lower_leg.L'].head_local).z
    z_top, z_hem = 1.02, knee + 0.025
    NR, NA, P = 18, 72, 2.6

    def extents(z):
        near = [p for p in pants if abs(p.z - z) < 0.012] or [p for p in skin if abs(p.z - z) < 0.012]
        return (min(p.x for p in near), max(p.x for p in near), min(p.y for p in near), max(p.y for p in near))

    front = [p for p in jacket if abs(p.z - z_top) < 0.03 and p.y < -0.04]
    open_x = max(0.035, min(abs(p.x) for p in front)) if front else 0.05
    bm = bmesh.new()
    rings = []
    for i in range(NR + 1):
        t = i / NR
        z = z_top + (z_hem - z_top) * t
        x0, x1, y0, y1 = extents(z)
        ease = 0.012 + 0.03 * smoothstep(0.05, 0.3, t) + 0.028 * smoothstep(0.3, 1.0, t)   # room for the thighs
        xc, yc = (x0 + x1) / 2, (y0 + y1) / 2
        ax, ay = (x1 - x0) / 2 + ease, (y1 - y0) / 2 + ease * 0.8
        phi0 = math.asin(min(0.9, open_x / ax)) * (1 - t) + math.radians(34) * t   # the coat falls open toward the hem
        row = []
        for k in range(NA + 1):
            ph = phi0 + (2 * math.pi - 2 * phi0) * k / NA
            s, c = math.sin(ph), math.cos(ph)
            fold = 1.0 + 0.018 * t * math.sin(ph * 9.0 + 0.7)                  # soft drape folds
            x = xc + ax * fold * math.copysign(abs(s) ** (2 / P), s)
            y = yc - ay * fold * math.copysign(abs(c) ** (2 / P), c)
            row.append(bm.verts.new((x, y, z)))
        rings.append(row)
    for a, b in zip(rings, rings[1:]):
        for k in range(NA):
            bm.faces.new((a[k], a[k + 1], b[k + 1], b[k]))
    bm.normal_update()
    back = [f for f in bm.faces if f.calc_center_median().y > 0.05]
    if back and sum(f.normal.y for f in back) < 0:                     # normals out
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    o = new_object('coat_skirt', bm, [bpy.data.materials['Jacket']], arm)
    solidify(o, 0.0045, offset=-1.0)
    zt, zh = z_top, z_hem
    vg = {n: o.vertex_groups.new(name=n) for n in ('hips', 'upper_leg.L', 'upper_leg.R')}
    for v in o.data.vertices:
        t = (zt - v.co.z) / (zt - zh)
        leg = 0.86 * smoothstep(0.08, 0.85, t)
        s = smoothstep(-0.055, 0.055, v.co.x)
        vg['hips'].add([v.index], 1.0 - leg, 'REPLACE')
        vg['upper_leg.L'].add([v.index], leg * s, 'REPLACE')
        vg['upper_leg.R'].add([v.index], leg * (1 - s), 'REPLACE')
    skin_to(o, arm)
    log('coat_skirt verts', len(o.data.vertices), 'z', round(z_top, 3), '->', round(z_hem, 3), 'open_x', round(open_x, 3))
    return o


# ------------------------------------------------------------------------------------------ rolled sleeves
def build_shirt_rolled():
    o = dup('shirt', 'shirt_rolled')
    W = o.matrix_world
    Wi = W.inverted()
    bm = bmesh.new()
    bm.from_mesh(o.data)
    cut = 0.565                                                         # just below the elbow (0.486) in T-pose
    kill = [f for f in bm.faces if any(abs((W @ v.co).x) > cut for v in f.verts)]
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')

    def move(v, d):
        v.co = Wi @ ((W @ v.co) + d)

    for side in (1, -1):
        es = [e for e in bm.edges if e.is_boundary and all((W @ v.co).x * side > cut - 0.035 for v in e.verts)]
        if not es:
            continue
        vs = {v for e in es for v in e.verts}
        c = sum(((W @ v.co) for v in vs), Vector()) / len(vs)

        def radial(v):
            p = W @ v.co
            return Vector((0.0, p.y - c.y, p.z - c.z)).normalized()
        new_edges = es
        for step in range(4):                                           # out, back along the arm, back again, tuck in
            r = bmesh.ops.extrude_edge_only(bm, edges=new_edges)
            nv = [g for g in r['geom'] if isinstance(g, bmesh.types.BMVert)]
            for v in nv:
                if step == 0:
                    move(v, radial(v) * 0.010)
                elif step == 1:
                    move(v, Vector((-side * 0.022, 0, 0)) + radial(v) * 0.002)
                elif step == 2:
                    move(v, Vector((-side * 0.020, 0, 0)) - radial(v) * 0.001)
                else:
                    move(v, -radial(v) * 0.008 + Vector((side * 0.004, 0, 0)))
            new_edges = [g for g in r['geom'] if isinstance(g, bmesh.types.BMEdge) and all(v in nv for v in g.verts)]
    bm.to_mesh(o.data)
    bm.free()
    ms = bpy.data.materials['shirt'].copy()                              # the roll's inside shows: double-sided
    ms.name = 'shirt_rolled'
    ms.vrm_addon_extension.mtoon1.double_sided = True
    o.data.materials.clear()
    o.data.materials.append(ms)
    log('shirt_rolled verts', len(o.data.vertices))
    return o


# ------------------------------------------------------------------------------------------ hoodie
def build_hoodie(arm):
    jersey = bpy.data.objects['jersey']
    jb = bvh_of(jersey)
    fleece = mat_flat('fleece', (0.12, 0.12, 0.135), outline=0.004)
    cord = mat_flat('cord', (0.82, 0.8, 0.76), outline=0.0015)
    bm = bmesh.new()

    def surf_down(x, y, z0=1.7):
        hit, n, _, _ = jb.ray_cast(Vector((x, y, z0)), Vector((0, 0, -1)))
        return hit

    def surf_along(x, z, direction):
        o_ = Vector((x, -0.5 * direction, z))
        hit, n, _, _ = jb.ray_cast(o_, Vector((0, direction, 0)))
        return hit, n

    # the hood, down: a bunched cowl around the back of the neck (thick at the back, tapering to the front)
    NA, NS = 40, 14
    rings = []
    for i in range(NA + 1):
        a = -1 + 2 * i / NA
        al = math.radians(150) * a
        x, y = 0.108 * math.sin(al), 0.012 + 0.1 * math.cos(al)
        base = surf_down(x, y) or Vector((x, y, 1.36))
        r = 0.036 * (1 - 0.5 * abs(a) ** 1.4)
        cz = base.z + r * 0.62
        tang = Vector((0.108 * math.cos(al), -0.1 * math.sin(al), 0)).normalized()
        out = Vector((math.sin(al), math.cos(al), 0)).normalized()
        row = []
        for k in range(NS):
            th = 2 * math.pi * k / NS
            p = Vector((x, y, cz)) + out * (math.cos(th) * r * 1.15) + Vector((0, 0, 1)) * (math.sin(th) * r * 0.62)
            row.append(bm.verts.new(p))
        rings.append(row)
    for ra, rb in zip(rings, rings[1:]):
        for k in range(NS):
            bm.faces.new((ra[k], ra[(k + 1) % NS], rb[(k + 1) % NS], rb[k]))
    for rr in (rings[0], rings[-1]):
        bm.faces.new(rr if rr is rings[-1] else rr[::-1])
    # the hood's back panel, lying on the upper back and ending in a soft point
    NV, NU = 12, 12
    grid = []
    for j in range(NV + 1):
        v = j / NV
        z = 1.345 - 0.19 * v
        half = 0.115 * (1 - v ** 1.8) + 0.012
        row = []
        for i in range(NU + 1):
            u = -1 + 2 * i / NU
            x = half * u
            hit, n = surf_along(x, z, -1.0)
            p = (hit + n.normalized() * 0.011) if hit else Vector((x, 0.09, z))
            row.append(bm.verts.new(p))
        grid.append(row)
    for ra, rb in zip(grid, grid[1:]):
        for i in range(NU):
            bm.faces.new((ra[i], ra[i + 1], rb[i + 1], rb[i]))
    # the kangaroo pocket on the belly
    NV2, NU2 = 8, 16
    pk = []
    for j in range(NV2 + 1):
        v = j / NV2
        z = 1.105 - 0.13 * v
        half = 0.085 + 0.04 * v
        row = []
        for i in range(NU2 + 1):
            u = -1 + 2 * i / NU2
            hit, n = surf_along(half * u, z, 1.0)
            p = (hit + n.normalized() * 0.005) if hit else Vector((half * u, -0.1, z))
            row.append(bm.verts.new(p))
        pk.append(row)
    for ra, rb in zip(pk, pk[1:]):
        for i in range(NU2):
            bm.faces.new((ra[i], ra[i + 1], rb[i + 1], rb[i]))
    n_fleece = len(bm.faces)
    # drawstrings with aglets
    for sx in (-1, 1):
        top = surf_along(sx * 0.03, 1.345, 1.0)[0] or Vector((sx * 0.03, -0.09, 1.345))
        pts = [top + Vector((sx * 0.004 * math.sin(k / 3), -0.012 - 0.003 * k, -0.013 * k)) for k in range(11)]
        for i, p in enumerate(pts):
            hit, n = surf_along(p.x, p.z, 1.0)
            if hit and p.y > hit.y - 0.006:
                pts[i] = Vector((p.x, hit.y - 0.006, p.z))
        tube_(bm, pts, 0.0032, 8, 1)
        tube_(bm, [pts[-1], pts[-1] + Vector((0, 0, -0.016))], 0.0042, 8, 1)
    for f in list(bm.faces)[:n_fleece]:
        f.material_index = 0
    o = new_object('acc_hoodie', bm, [fleece, cord], arm)
    copy_weights(o, jersey, kd_of(world_verts(jersey)), weight_table(jersey))
    skin_to(o, arm)
    log('acc_hoodie verts', len(o.data.vertices))
    return o


def tube_(bm, pts, r, seg, mat_index):
    rings = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        a = t.orthogonal().normalized()
        b = t.cross(a).normalized()
        rings.append([bm.verts.new(p + (a * math.cos(2 * math.pi * k / seg) + b * math.sin(2 * math.pi * k / seg)) * r) for k in range(seg)])
    for ra, rb in zip(rings, rings[1:]):
        for k in range(seg):
            bm.faces.new((ra[k], ra[(k + 1) % seg], rb[(k + 1) % seg], rb[k])).material_index = mat_index
    bm.faces.new(rings[0][::-1]).material_index = mat_index
    bm.faces.new(rings[-1]).material_index = mat_index


# ------------------------------------------------------------------------------------------ patches
def build_patches(arm):
    jacket = bpy.data.objects['jacket']
    jb = bvh_of(jacket)
    img = bpy.data.images.load(os.path.join(TEXB, 'patches_atlas.png'), check_existing=True)
    m = bpy.data.materials.get('patches') or bpy.data.materials.new('patches')
    ext = m.vrm_addon_extension.mtoon1
    ext.enabled = True
    ext.pbr_metallic_roughness.base_color_factor = (1, 1, 1, 1)
    ext.pbr_metallic_roughness.base_color_texture.index.source = img
    ext.alpha_mode = 'MASK'
    ext.alpha_cutoff = 0.5
    mt = ext.extensions.vrmc_materials_mtoon
    mt.shade_color_factor = (0.66, 0.66, 0.66)
    mt.shade_multiply_texture.index.source = img
    mt.outline_width_mode = 'none'
    mt.parametric_rim_color_factor = (0.0, 0.0, 0.0)

    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')

    def patch(origin, direction, u_axis, size_u, size_v, cell, n=14):
        hit, nrm, _, _ = jb.ray_cast(origin, direction)
        if hit is None:
            log('patch missed', origin)
            return
        nrm = nrm.normalized()
        ua = (u_axis - nrm * u_axis.dot(nrm)).normalized()
        va = nrm.cross(ua).normalized()
        nu, nv = n, max(4, int(n * size_v / size_u))
        grid = []
        for j in range(nv + 1):
            row = []
            for i in range(nu + 1):
                p = hit + ua * (size_u * (i / nu - 0.5)) + va * (size_v * (j / nv - 0.5))
                h2, n2, _, _ = jb.ray_cast(p + nrm * 0.06, -nrm)
                q = (h2 + n2.normalized() * 0.0028) if h2 is not None else p + nrm * 0.0028
                row.append((bm.verts.new(q), (cell[0] + (cell[2] - cell[0]) * i / nu, cell[1] + (cell[3] - cell[1]) * j / nv)))
            grid.append(row)
        for ra, rb in zip(grid, grid[1:]):
            for i in range(nu):
                quad = (ra[i], ra[i + 1], rb[i + 1], rb[i])
                f = bm.faces.new([q[0] for q in quad])
                for loop, q in zip(f.loops, quad):
                    loop[uvl].uv = q[1]
                if f.normal.dot(nrm) < 0:
                    f.normal_flip()

    # T-pose: the upper arm's lateral side faces +Z; the patches sit on it, top of the sleeve
    patch(Vector((0.275, 0.004, 1.62)), Vector((0, 0, -1)), Vector((1, 0, 0)), 0.082, 0.082, (0.0, 0.5, 0.5, 1.0))   # our flower
    patch(Vector((-0.275, 0.004, 1.62)), Vector((0, 0, -1)), Vector((-1, 0, 0)), 0.082, 0.082, (0.5, 0.5, 1.0, 1.0))  # day's eye
    # the back, between the shoulder blades (below the petal ring, clear of the tail): the banner. Seen from
    # behind, reading left to right runs toward her right = -x
    patch(Vector((0.0, 0.5, 1.2)), Vector((0, -1, 0)), Vector((-1, 0, 0)), 0.29, 0.29 * 336 / 976,
          (24 / 1024, 1 - 936 / 1024, 1000 / 1024, 1 - 600 / 1024), n=24)
    bm.normal_update()
    o = new_object('acc_patches', bm, [m], arm)
    copy_weights(o, jacket, kd_of(world_verts(jacket)), weight_table(jacket))
    skin_to(o, arm)
    log('acc_patches verts', len(o.data.vertices))
    return o


# ------------------------------------------------------------------------------------------ boutonniere
def build_boutonniere(arm):
    jacket = bpy.data.objects['jacket']
    jb = bvh_of(jacket)
    hit, nrm, _, _ = jb.ray_cast(Vector((0.118, -0.5, 1.195)), Vector((0, 1, 0)))
    if hit is None:
        log('boutonniere: lapel missed')
        return None
    n = (nrm.normalized() + Vector((0, 0, 0.35))).normalized()          # tipped up a little, toward the light
    a = n.orthogonal().normalized()
    b = n.cross(a).normalized()
    c = hit + nrm.normalized() * 0.008
    bm = bmesh.new()
    NP = 16
    S = 1.35                                                            # a touch bigger than life: it reads on camera
    for k in range(NP):                                                 # ray florets: spoon petals, cupped
        th = 2 * math.pi * k / NP + (0.08 if k % 2 else 0)
        d = a * math.cos(th) + b * math.sin(th)
        side = n.cross(d).normalized()
        L = (0.0165 if k % 2 == 0 else 0.0152) * S
        pts = []
        for s in (0.0, 0.25, 0.5, 0.75, 0.92, 1.0):
            half = (0.0026 + 0.0019 * math.sin(math.pi * min(1.0, s * 0.95))) * S if s < 1.0 else 0.0008 * S
            p = c + d * (0.006 * S + L * s) + n * (0.0045 * S * s * s)
            pts.append((p - side * half, p + side * half))
        vs = [(bm.verts.new(l), bm.verts.new(r)) for l, r in pts]
        for (l0, r0), (l1, r1) in zip(vs, vs[1:]):
            bm.faces.new((l0, r0, r1, l1)).material_index = 0
    disc = []                                                           # the golden disc, domed
    for i in range(5):
        rr = 0.0072 * S * math.cos(math.pi / 2 * i / 5)
        h = 0.0042 * S * math.sin(math.pi / 2 * i / 5)
        disc.append([bm.verts.new(c + (a * math.cos(2 * math.pi * k / 20) + b * math.sin(2 * math.pi * k / 20)) * rr + n * (0.001 + h))
                     for k in range(20)])
    top = bm.verts.new(c + n * 0.0056 * S)
    for ra, rb in zip(disc, disc[1:]):
        for k in range(20):
            bm.faces.new((ra[k], ra[(k + 1) % 20], rb[(k + 1) % 20], rb[k])).material_index = 1
    for k in range(20):
        bm.faces.new((disc[-1][k], disc[-1][(k + 1) % 20], top)).material_index = 1
    bm.faces.new(disc[0][::-1]).material_index = 1
    tube_(bm, [c - n * 0.002, c - n * 0.004 - Vector((0, 0, 0.012)), c - n * 0.006 - Vector((0, 0, 0.026))], 0.0016, 8, 2)
    o = new_object('acc_boutonniere', bm, [mat_flat('bout_petal', (0.95, 0.94, 0.9), 0.0012, double_sided=True),
                                          mat_flat('bout_disc', (1.0, 0.66, 0.06), 0.0012),
                                          mat_flat('bout_stem', (0.12, 0.33, 0.09), 0.0)], arm)
    bone_parent(o, arm, 'chest')
    log('boutonniere at', tuple(round(x, 3) for x in hit))
    return o


# ------------------------------------------------------------------------------------------ main
bpy.ops.wm.open_mainfile(filepath=os.path.join(BL, 'cyclist_acc.blend'))
for nm in ('coat_skirt', 'shirt_rolled', 'acc_hoodie', 'acc_patches', 'acc_boutonniere'):
    if nm in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[nm], do_unlink=True)
arm = bpy.data.objects['Armature']
for nm in ('Jacket', 'shirt', 'jersey', 'pants'):
    mm = bpy.data.materials.get(nm)
    if mm:
        log(f'material {nm}: double_sided={mm.vrm_addon_extension.mtoon1.double_sided}')
split_jersey_collar()
build_coat_skirt(arm)
build_shirt_rolled()
build_hoodie(arm)
build_patches(arm)
build_boutonniere(arm)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BL, 'era_wardrobe.blend'))
out = os.path.join(REPO, 'eidoverse', 'assets', 'vrms', 'claude_suit_wardrobe.vrm')
tmp = out.replace('.vrm', '.part.vrm')                                   # renders may be reading the live file
res = bpy.ops.export_scene.vrm(filepath=tmp, export_invisibles=True, export_only_selections=False)
if 'FINISHED' in res and os.path.getsize(tmp) > 1_000_000:
    os.replace(tmp, out)
log('export', res, os.path.getsize(out))

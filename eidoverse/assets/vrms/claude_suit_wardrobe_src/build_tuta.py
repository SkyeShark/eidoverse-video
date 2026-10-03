"""UNKNOWN FORCE outfit for digi's claudesona: Thayaht's 1920 TuTa re-cut as black techwear, techwear boots, straps,
Balla's five snap-on modificanti and an optional segmented sun disc. The Blender half of the outfit; the surface look
(weave, seams, neon piping, colour blocking, zip, ghosts, face paint, catchlights) is TSL in eidoverse/claudesona_wardrobe.js.

    python eidoverse/assets/vrms/claude_suit_wardrobe_src/paint_badges.py      # first: badge faces + rims, ghost SDF atlas, sun disc (PIL)
    bash run_blender.sh eidoverse/assets/vrms/claude_suit_wardrobe_src/build_tuta.py [--no-export] [--looks]
    (--looks: EEVEE geometry sanity renders -> work/claude_suit_wardrobe_looks/wd_blender_uf_*.png; the engine is the truth)

The last stage of the wardrobe build: opens the wardrobe source (claude_suit_wardrobe.blend next to this script: digi's
claudesona and every DAISY garment; never saved over), adds the outfit below and exports the library VRM:
  tuta         ONE skinned garment from digi's shirt + pants: split seams welded, pushed out (shirt 6 mm, roomier toward
               the cuffs; pants 5 mm), tucked thin into the boots and stacking over their tops. digi's shirt is closed at
               the neck, so the neckline stays under the face disc and petals. Material `tuta`.
  uf_boots     skinned: digi's loafer as the foot (a chunkier cupsole lip) + a sleek shaft lofted round the ankle and
               shin to mid-calf (weights from the skin it wraps) + ankle straps with a side buckle over the join.
               Materials `boot_upper`, `boot_sole`, `webbing`, `buckle`.
  uf_straps    skinned: the TuTa's belt (an off-centre buckle; open at the back round the tail, ends tipped in metal), a
               thigh strap with a side buckle, the zip puller. Materials `webbing`, `buckle`.
  mod_red, mod_gold, mod_chrome, mod_warning, mod_spray
               bone-parented badges built from badges.json (outline polygons in badge mm), conformed to the tuta's
               surface; each one material `mod_<key>` with its painted face (claude_suit_wardrobe_tex/mod_<key>.png) and an
               emissive rim (claude_suit_wardrobe_tex/mod_<key>_emit.png). Their rest frame is the object's frame: local XY = the badge
               plane, +Z out of the suit (glTF: +Y), so the runtime can put each badge's ghost exactly where it sat.
  acc_sundisc  head-parented: Balla's segmented sun disc behind the petal ring (material `sundisc`).
Saves work/claude_suit_wardrobe_tuta.blend and exports eidoverse/assets/vrms/claude_suit_wardrobe.vrm (temp + replace).
"""
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector, kdtree
from mathutils.bvhtree import BVHTree

bpy.ops.preferences.addon_enable(module='bl_ext.blender_org.vrm')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import uf_shapes  # noqa: E402  (badge outlines, shared with paint_badges.py)
REPO = HERE
while REPO != os.path.dirname(REPO) and not os.path.exists(os.path.join(REPO, 'eido.py')):
    REPO = os.path.dirname(REPO)
SRC = os.path.join(REPO, 'eidoverse', 'assets', 'vrms', 'claude_suit_wardrobe_src', 'claude_suit_wardrobe.blend')
TEX = os.path.join(REPO, 'eidoverse', 'assets', 'vrms', 'claude_suit_wardrobe_tex')
OUT_VRM = os.path.join(REPO, 'eidoverse', 'assets', 'vrms', 'claude_suit_wardrobe.vrm')
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def log(*a):
    print('[uf]', *a, flush=True)


# the diagonal zip (front view, Blender x/z): from the left collarbone down to the right hip, just above the belt.
# eidoverse/claudesona_wardrobe.js draws the same line (glTF: x, y = z here); keep the two in step.
ZIP_TOP, ZIP_BOT = (0.062, 1.305), (-0.118, 0.986)


def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------------------------------ helpers
# (weight transfer, bone parenting and MToon setup follow build_era_garments.py, the DAISY wardrobe recipe)
def mtoon(name, rgb, outline=0.005, double_sided=False, shade=0.55, emissive=None, emissive_strength=1.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    ext = m.vrm_addon_extension.mtoon1
    ext.enabled = True
    ext.pbr_metallic_roughness.base_color_factor = (*rgb, 1.0)
    mt = ext.extensions.vrmc_materials_mtoon
    mt.shade_color_factor = tuple(c * shade for c in rgb)
    mt.outline_width_mode = 'worldCoordinates' if outline > 0 else 'none'
    mt.outline_width_factor = outline
    mt.outline_color_factor = tuple(c * 0.25 for c in rgb)
    mt.outline_lighting_mix_factor = 0.0
    mt.parametric_rim_color_factor = (0.0, 0.0, 0.0)
    ext.double_sided = double_sided
    if emissive is not None:
        ext.emissive_factor = tuple(emissive)
        try:
            ext.extensions.khr_materials_emissive_strength.emissive_strength = emissive_strength
        except Exception as e:                                    # older add-on: no strength
            log('emissive strength unavailable', e)
    return m


def tex_image(path, non_color=False):
    img = bpy.data.images.load(path, check_existing=True)
    if non_color:
        img.colorspace_settings.name = 'Non-Color'
    img.pack()
    return img


def world_verts(o):
    W = o.matrix_world
    return [W @ v.co for v in o.data.vertices]


def bvh_of(o):
    return BVHTree.FromPolygons(world_verts(o), [tuple(p.vertices) for p in o.data.polygons])


def kd_of(pts):
    kd = kdtree.KDTree(len(pts))
    for i, p in enumerate(pts):
        kd.insert(p, i)
    kd.balance()
    return kd


def weight_table(src):
    names = {g.index: g.name for g in src.vertex_groups}
    return [[(names[g.group], g.weight) for g in v.groups if g.weight > 1e-4] for v in src.data.vertices]


def copy_weights(dst, src, kd=None, table=None, filt=None):
    """every dst vertex takes the skin weights of the nearest src vertex (filt(world_pos) limits the candidates)"""
    table = table or weight_table(src)
    if kd is None:
        pts = world_verts(src)
        idx = [i for i, p in enumerate(pts) if (filt is None or filt(p))]
        kd = kdtree.KDTree(len(idx))
        for j, i in enumerate(idx):
            kd.insert(pts[i], i)
        kd.balance()
    for g in list(dst.vertex_groups):
        dst.vertex_groups.remove(g)
    groups = {}
    W = dst.matrix_world
    for v in dst.data.vertices:
        _, i, _ = kd.find(W @ v.co)
        for name, w in table[i]:
            g = groups.get(name) or dst.vertex_groups.new(name=name)
            groups[name] = g
            g.add([v.index], w, 'REPLACE')


def link_new(name, bm, materials):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.data.objects['shirt'].users_collection[0].objects.link(o)
    for m in materials:
        me.materials.append(m)
    return o


def skin_to(o, arm):
    o.parent = arm
    o.matrix_parent_inverse = arm.matrix_world.inverted()
    for md in list(o.modifiers):
        if md.type == 'ARMATURE':
            o.modifiers.remove(md)
    mod = o.modifiers.new('Armature', 'ARMATURE')
    mod.object = arm


def bone_parent(o, arm, bone):
    mw = o.matrix_world.copy()
    o.parent = arm
    o.parent_type = 'BONE'
    o.parent_bone = bone
    bpy.context.view_layer.update()
    o.matrix_world = mw


def dup(name, newname):
    src = bpy.data.objects[name]
    o = src.copy()
    o.data = src.data.copy()
    o.name = newname
    o.data.name = newname
    for c in src.users_collection:
        c.objects.link(o)
    return o


def select_only(o):
    for x in bpy.context.view_layer.objects:
        x.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def boundary_loops(bm):
    bnd = [e for e in bm.edges if e.is_boundary]
    seen, loops = set(), []
    for e0 in bnd:
        if e0 in seen:
            continue
        stack, comp = [e0], []
        while stack:
            e = stack.pop()
            if e in seen:
                continue
            seen.add(e)
            comp.append(e)
            for v in e.verts:
                for e2 in v.link_edges:
                    if e2.is_boundary and e2 not in seen:
                        stack.append(e2)
        loops.append(comp)
    return loops


def push_out(o, dist_fn):
    """displace every vertex along its (welded, smooth) normal by dist_fn(world_pos)"""
    W = o.matrix_world
    Wi = W.inverted()
    R = W.to_3x3()
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.normal_update()
    for v in bm.verts:
        p = W @ v.co
        n = (R @ v.normal).normalized()
        v.co = Wi @ (p + n * dist_fn(p))
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()


# ------------------------------------------------------------------------------------------ the tuta
def build_tuta(arm):
    top = dup('shirt', 'tuta_top')
    bot = dup('pants', 'tuta_bottom')
    for o in (top, bot):                          # weld digi's split seams so a push can't crack them open
        bm = bmesh.new()
        bm.from_mesh(o.data)
        n0 = len(bm.verts)
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=2e-5)
        loops = boundary_loops(bm)
        log(f'{o.name}: welded {n0 - len(bm.verts)} verts, boundary loops {[len(l) for l in loops]}')
        for comp in loops:
            ps = [o.matrix_world @ ((e.verts[0].co + e.verts[1].co) / 2) for e in comp]
            c = sum(ps, Vector()) / len(ps)
            log(f'    loop {len(comp)} centre {tuple(round(x, 3) for x in c)} z {min(p.z for p in ps):.3f}..{max(p.z for p in ps):.3f}')
        bm.to_mesh(o.data)
        bm.free()
        if o.data.has_custom_normals:
            select_only(o)
            bpy.ops.mesh.customdata_custom_splitnormals_clear()
        for p in o.data.polygons:
            p.use_smooth = True
    # a roomier T-cut: the sleeves widen a little toward the cuff, the legs stack above the boot tops
    push_out(top, lambda p: 0.006 + 0.004 * smoothstep(0.3, 0.72, abs(p.x)))
    # tucked into the boots below 0.23 m (thin), stacked over the boot tops, +5 mm above
    push_out(bot, lambda p: 0.002 + 0.003 * smoothstep(0.215, 0.25, p.z) + 0.006 * math.exp(-((p.z - 0.292) / 0.04) ** 2))
    for o in (top, bot):
        o.data.materials.clear()
    m = mtoon('tuta', (0.055, 0.058, 0.066), outline=0.005, double_sided=True)
    top.data.materials.append(m)
    bot.data.materials.append(m)
    select_only(top)
    bot.select_set(True)
    bpy.context.view_layer.objects.active = top
    bpy.ops.object.join()
    tuta = bpy.context.view_layer.objects.active
    tuta.name = 'tuta'
    tuta.data.name = 'tuta'
    skin_to(tuta, arm)
    for md in list(tuta.modifiers):               # keep only the armature (digi's NODES modifiers are export-time no-ops here)
        if md.type != 'ARMATURE':
            tuta.modifiers.remove(md)
    log('tuta verts', len(tuta.data.vertices), 'faces', len(tuta.data.polygons))
    return tuta


# ------------------------------------------------------------------------------------------ boots
def build_boots(arm):
    body = bpy.data.objects['BodyActual']
    pants = bpy.data.objects['pants']
    shoes = bpy.data.objects['shoes']
    skin_pts = world_verts(body)
    pant_pts = world_verts(pants)
    shoe_pts = world_verts(shoes)
    TOP, BOT = 0.238, 0.05
    NR, NA = 16, 48
    bm = bmesh.new()
    rings_by_side, ring_centres = {}, {}
    for side in (1, -1):
        # the leg axis at each height: centre of the pants' cross-section (skin below the hem)
        rings = []
        for i in range(NR + 1):
            t = i / NR
            z = BOT + (TOP - BOT) * t
            src = [p for p in pant_pts if abs(p.z - z) < 0.01 and p.x * side > 0.02] if z > 0.085 else []
            # the ankle (behind the instep): low down the shaft hugs it and slips inside the shoe's collar,
            # where the ankle strap closes the join
            src += [p for p in skin_pts if abs(p.z - z) < 0.01 and p.x * side > 0.03 and p.y < 0.12 and p.y > -0.04]
            cx = sum(p.x for p in src) / len(src)
            cy = sum(p.y for p in src) / len(src)
            radial = [0.0] * NA
            for p in src:
                a = math.atan2(p.y - cy, p.x - cx)
                k = int(((a + math.pi) / (2 * math.pi)) * NA) % NA
                radial[k] = max(radial[k], math.hypot(p.x - cx, p.y - cy))
            for _ in range(3):                                    # fill empty bins + smooth the outline
                radial = [max(radial[k], 0.5 * (radial[k - 1] + radial[(k + 1) % NA])) for k in range(NA)]
            for _ in range(2):
                radial = [(radial[k - 1] + 2 * radial[k] + radial[(k + 1) % NA]) / 4 for k in range(NA)]
            off = 0.0055 + 0.0005 * t                            # a sleek shaft over the tucked-in tuta
            row = []
            for k in range(NA):
                a = -math.pi + 2 * math.pi * (k + 0.5) / NA
                r = radial[k] + off
                row.append(bm.verts.new((cx + r * math.cos(a), cy + r * math.sin(a), z)))
            rings.append(row)
        for ra, rb in zip(rings, rings[1:]):
            for k in range(NA):
                bm.faces.new((ra[k], ra[(k + 1) % NA], rb[(k + 1) % NA], rb[k]))
        # padded collar: roll over the top and down inside 2 cm
        top = rings[-1]
        cx = sum(v.co.x for v in top) / NA
        cy = sum(v.co.y for v in top) / NA
        prev = top
        for step, (dr, dz) in enumerate(((0.0015, 0.004), (-0.003, 0.005), (-0.007, 0.0), (-0.009, -0.016))):   # a neoprene lip
            row = []
            for v in top:
                d = Vector((v.co.x - cx, v.co.y - cy, 0)).normalized()
                row.append(bm.verts.new(v.co + d * dr + Vector((0, 0, dz))))
            for k in range(NA):
                bm.faces.new((prev[k], prev[(k + 1) % NA], row[(k + 1) % NA], row[k]))
            prev = row
        rings_by_side[side] = rings
        ring_centres[side] = [(sum(v.co.x for v in r) / NA, sum(v.co.y for v in r) / NA, r[0].co.z) for r in rings]
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    # normals out: compare the first ring's face normal with the radial direction
    f0 = bm.faces[0]
    c0 = f0.calc_center_median()
    side0 = 1 if c0.x > 0 else -1
    ax = sum((v.co for v in rings_by_side[side0][0]), Vector()) / NA
    if f0.normal.dot(Vector((c0.x - ax.x, c0.y - ax.y, 0))) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    shaft = link_new('uf_shaft', bm, [])
    for p in shaft.data.polygons:
        p.use_smooth = True
    # weights from the skin the shaft wraps (ankle flexion: lower_leg <-> foot blend)
    copy_weights(shaft, body, filt=lambda p: p.z < 0.32 and abs(p.x) > 0.03 and p.y < 0.12)
    # the foot: digi's loafer, its sole band pushed out into a chunkier cupsole lip
    foot = dup('shoes', 'uf_foot')
    bm = bmesh.new()
    bm.from_mesh(foot.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=2e-5)
    W = foot.matrix_world
    Wi = W.inverted()
    for side in (1, -1):
        vs = [v for v in bm.verts if (W @ v.co).x * side > 0]
        c = sum(((W @ v.co) for v in vs), Vector()) / len(vs)
        for v in vs:
            p = W @ v.co
            k = 1.0 - smoothstep(0.012, 0.03, p.z)
            d = Vector((p.x - c.x, (p.y - c.y) * 0.75, 0)).normalized()
            v.co = Wi @ (p + d * 0.0045 * k + Vector((0, 0, 0.0)))
    bm.to_mesh(foot.data)
    bm.free()
    up = mtoon('boot_upper', (0.05, 0.05, 0.055), outline=0.005, double_sided=True)
    so = mtoon('boot_sole', (0.075, 0.075, 0.08), outline=0.004, double_sided=True)
    foot.data.materials.clear()
    foot.data.materials.append(up)
    foot.data.materials.append(so)
    for p in foot.data.polygons:
        cz = (W @ p.center).z
        p.material_index = 1 if cz < 0.021 else 0
    shaft.data.materials.append(up)
    shaft.data.materials.append(so)
    select_only(foot)
    shaft.select_set(True)
    bpy.context.view_layer.objects.active = foot
    bpy.ops.object.join()
    boots = bpy.context.view_layer.objects.active
    boots.name = 'uf_boots'
    boots.data.name = 'uf_boots'
    # ankle straps over the join of shaft and shoe, a buckle on the outside
    bvh = bvh_of(boots)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    web = mtoon('webbing', (0.035, 0.036, 0.04), outline=0.003, double_sided=True)
    buck = mtoon('buckle', (0.33, 0.34, 0.37), outline=0.002)
    for side in (1, -1):
        cx, cy, _ = ring_centres[side][2]
        strap_ring(bm, uvl, bvh, 0.071, 0.024, cx, cy, thick=0.0035, n=72, mat=0, length_u=3.0, off=0.0015, rmax=0.11)
        hit, nrm, _, _ = bvh.ray_cast(Vector((cx + side * 0.3, cy + 0.01, 0.071)), Vector((-side, 0, 0)))
        if hit:
            nrm = nrm.normalized()
            u = Vector((0, 0, 1))
            u = (u - nrm * u.dot(nrm)).normalized()
            v = nrm.cross(u).normalized()
            rounded_box(bm, hit + nrm * 0.0048, v, u, nrm, 0.03, 0.03, 0.005, 1, uvl, r=0.25)
    bm.normal_update()
    straps_o = link_new('uf_ankle_straps', bm, [web, buck])
    for p in straps_o.data.polygons:
        p.use_smooth = p.material_index == 0
    copy_weights(straps_o, boots)
    select_only(boots)
    straps_o.select_set(True)
    bpy.context.view_layer.objects.active = boots
    bpy.ops.object.join()
    boots = bpy.context.view_layer.objects.active
    skin_to(boots, arm)
    for md in list(boots.modifiers):
        if md.type != 'ARMATURE':
            boots.modifiers.remove(md)
    log('boots verts', len(boots.data.vertices))
    return boots


# ------------------------------------------------------------------------------------------ straps
def surface_ring(bvh, z, cx, cy, n=96, off=0.003, rmax=0.5, arc=None):  # noqa: E302
    """points on the outside of a surface round a vertical axis at height z (rays cast inward); arc=(a0, a1) gives an
    open run of n points from angle a0 to a1 instead of a closed ring"""
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n if arc is None else arc[0] + (arc[1] - arc[0]) * k / (n - 1)
        d = Vector((math.cos(a), math.sin(a), 0))
        o = Vector((cx, cy, z)) + d * rmax
        hit, nrm, _, _ = bvh.ray_cast(o, -d)
        pts.append((hit + d * off) if hit else (Vector((cx, cy, z)) + d * 0.12))
    return pts


def band(bm, rings_lo, rings_hi, mat_index, uv_layer=None, length_u=1.0):
    """quad strip between two closed rings, with u along the ring and v across"""
    n = len(rings_lo)
    lo = [bm.verts.new(p) for p in rings_lo]
    hi = [bm.verts.new(p) for p in rings_hi]
    for k in range(n):
        f = bm.faces.new((lo[k], lo[(k + 1) % n], hi[(k + 1) % n], hi[k]))
        f.material_index = mat_index
        if uv_layer is not None:
            us = (k / n * length_u, (k + 1) / n * length_u)
            for loop, uvv in zip(f.loops, ((us[0], 0), (us[1], 0), (us[1], 1), (us[0], 1))):
                loop[uv_layer].uv = uvv
    return lo, hi


def strap_arc(bm, uvl, bvh, zc, width, cx, cy, a0, a1, thick=0.0035, n=96, mat=0, length_u=1.0, off=0.0025, rmax=0.5):
    """an open strap from angle a0 to a1 round a body part (outer, inner, the two edges, the two cut ends)"""
    rings = [surface_ring(bvh, zc + dz, cx, cy, n, off + t, rmax, arc=(a0, a1))
             for dz, t in ((-width / 2, thick), (width / 2, thick), (width / 2, 0.0), (-width / 2, 0.0))]
    vs = [[bm.verts.new(p) for p in r] for r in rings]               # lo_o, hi_o, hi_i, lo_i
    for q in range(4):
        A, B = vs[q], vs[(q + 1) % 4]
        for k in range(n - 1):
            f = bm.faces.new((A[k], A[k + 1], B[k + 1], B[k]))
            f.material_index = mat
            if uvl is not None:
                for loop, uvv in zip(f.loops, ((k / (n - 1) * length_u, q / 4), ((k + 1) / (n - 1) * length_u, q / 4),
                                               ((k + 1) / (n - 1) * length_u, (q + 1) / 4), (k / (n - 1) * length_u, (q + 1) / 4))):
                    loop[uvl].uv = uvv
    for k in (0, n - 1):                                             # the cut ends
        f = bm.faces.new([vs[q][k] for q in (range(4) if k == 0 else reversed(range(4)))])
        f.material_index = mat
    return [r[0] for r in rings], [r[-1] for r in rings]


def strap_ring(bm, uvl, bvh, zc, width, cx, cy, thick=0.0035, n=96, mat=0, length_u=1.0, off=0.0025, rmax=0.5):
    """a closed strap round a body part: outer face, inner face and the two edges"""
    lo_o = surface_ring(bvh, zc - width / 2, cx, cy, n, off + thick, rmax)
    hi_o = surface_ring(bvh, zc + width / 2, cx, cy, n, off + thick, rmax)
    lo_i = surface_ring(bvh, zc - width / 2, cx, cy, n, off, rmax)
    hi_i = surface_ring(bvh, zc + width / 2, cx, cy, n, off, rmax)
    band(bm, lo_o, hi_o, mat, uvl, length_u)                     # outer
    band(bm, hi_i, lo_i, mat, uvl, length_u)                     # inner (reversed)
    band(bm, lo_i, lo_o, mat, uvl, length_u)                     # lower edge
    band(bm, hi_o, hi_i, mat, uvl, length_u)                     # upper edge
    return lo_o, hi_o


def rounded_box(bm, c, ax_u, ax_v, ax_n, su, sv, sn, mat, uvl=None, r=0.25, seg=4):
    """a rounded-corner slab (buckle plates): outline in the (u, v) plane, extruded along n"""
    pts = []
    ru, rv = su * r, sv * r
    for q, (sx, sy) in enumerate(((1, 1), (-1, 1), (-1, -1), (1, -1))):
        cxx, cyy = sx * (su / 2 - ru), sy * (sv / 2 - rv)
        for s in range(seg + 1):
            a = math.pi / 2 * q + math.pi / 2 * s / seg
            pts.append((cxx + ru * math.cos(a), cyy + rv * math.sin(a)))
    front = [bm.verts.new(c + ax_u * x + ax_v * y + ax_n * sn) for x, y in pts]
    back = [bm.verts.new(c + ax_u * x + ax_v * y) for x, y in pts]
    n = len(pts)
    ff = bm.faces.new(front)
    ff.material_index = mat
    fb = bm.faces.new(back[::-1])
    fb.material_index = mat
    for k in range(n):
        f = bm.faces.new((back[k], back[(k + 1) % n], front[(k + 1) % n], front[k]))
        f.material_index = mat
    if uvl is not None:
        for f in [ff, fb] + list(bm.faces)[-n:]:
            for loop in f.loops:
                d = loop.vert.co - c
                loop[uvl].uv = (0.5 + d.dot(ax_u) / su, 0.5 + d.dot(ax_v) / sv)
    return front, back


def build_straps(arm, tuta):
    bvh = bvh_of(tuta)
    web = mtoon('webbing', (0.035, 0.036, 0.04), outline=0.003, double_sided=True)
    buck = mtoon('buckle', (0.33, 0.34, 0.37), outline=0.002)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    # the belt (TuTa's "simple belt"): 4.4 cm webbing round the waist, over the shirt/pants overlap
    hips = arm.matrix_world @ arm.data.bones['hips'].head_local
    belt_z = 0.952
    # open at the back: digi's tail leaves the cloth right on the belt line (measure_tail_exit.py: x 0, z 0.955), so
    # the belt stops either side of a tail port (the grommet is drawn on the tuta in claudesona_wardrobe.js), ends tipped in metal
    port = math.asin(0.046 / 0.11)
    a0, a1 = math.pi / 2 + port, math.pi / 2 + 2 * math.pi - port
    ends = strap_arc(bm, uvl, bvh, belt_z, 0.044, hips.x, hips.y + 0.005, a0, a1, thick=0.004, n=128, mat=0, length_u=8.0)
    for which in (0, 1):                                             # metal tips on the two cut ends
        c = sum(ends[which], Vector()) / 4
        a = a0 if which == 0 else a1
        tang = Vector((-math.sin(a), math.cos(a), 0)) * (1 if which == 0 else -1)
        out = Vector((math.cos(a), math.sin(a), 0))
        rounded_box(bm, c - out * 0.0012 - tang * 0.004, tang, Vector((0, 0, 1)), out, 0.012, 0.047, 0.0068, 1, uvl, r=0.3)
    # the buckle: a cobra-style plate, off centre (the asymmetric front), on the belt
    hit, nrm, _, _ = bvh.ray_cast(Vector((0.045, -0.5, belt_z)), Vector((0, 1, 0)))
    nrm = nrm.normalized()
    u = Vector((1, 0, 0))
    u = (u - nrm * u.dot(nrm)).normalized()
    v = nrm.cross(u).normalized()
    c = hit + nrm * 0.0065
    rounded_box(bm, c, u, v, nrm, 0.058, 0.05, 0.007, 1, uvl, r=0.22)
    rounded_box(bm, c + u * 0.0 + nrm * 0.007, u, v, nrm, 0.03, 0.022, 0.0025, 1, uvl, r=0.4)   # the latch tongue
    # thigh strap on her right thigh (a utility strap with a side buckle)
    leg = arm.matrix_world @ arm.data.bones['upper_leg.R'].head_local
    knee = arm.matrix_world @ arm.data.bones['lower_leg.R'].head_local
    zt = 0.655
    t = (leg.z - zt) / (leg.z - knee.z)
    cx, cy = leg.x + (knee.x - leg.x) * t, leg.y + (knee.y - leg.y) * t
    strap_ring(bm, uvl, bvh, zt, 0.03, cx, cy, thick=0.0035, n=96, mat=0, length_u=4.0, rmax=0.115)
    hit, nrm, _, _ = bvh.ray_cast(Vector((cx - 0.5, cy, zt)), Vector((1, 0, 0)))
    if hit:
        nrm = nrm.normalized()
        u = Vector((0, 0, 1))
        u = (u - nrm * u.dot(nrm)).normalized()
        v = nrm.cross(u).normalized()
        rounded_box(bm, hit + nrm * 0.0058, v, u, nrm, 0.036, 0.04, 0.006, 1, uvl, r=0.25)
    # the zip puller: a tab hanging from the zip's top end (left collarbone)
    zp = Vector((ZIP_TOP[0], -0.5, ZIP_TOP[1]))
    hit, nrm, _, _ = bvh.ray_cast(zp, Vector((0, 1, 0)))
    if hit:
        nrm = nrm.normalized()
        dn = Vector((ZIP_BOT[0] - ZIP_TOP[0], 0, ZIP_BOT[1] - ZIP_TOP[1])).normalized()   # down the zip toward her right hip
        dn = (dn - nrm * dn.dot(nrm)).normalized()
        side = nrm.cross(dn).normalized()
        rounded_box(bm, hit + nrm * 0.003 + dn * 0.012, side, dn, nrm, 0.011, 0.028, 0.0028, 1, uvl, r=0.45)
        rounded_box(bm, hit + nrm * 0.002, side, dn, nrm, 0.009, 0.011, 0.004, 1, uvl, r=0.3)   # the slider
    bm.normal_update()
    o = link_new('uf_straps', bm, [web, buck])
    for p in o.data.polygons:
        p.use_smooth = p.material_index == 0
    copy_weights(o, tuta)
    skin_to(o, arm)
    log('straps verts', len(o.data.vertices))
    return o


# ------------------------------------------------------------------------------------------ modificanti
def inset_poly(pts, d):
    """offset a CCW polygon inward by d (miter, clamped)"""
    n = len(pts)
    res = []
    for i in range(n):
        a, p, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        e1 = (p - a).normalized()
        e2 = (c - p).normalized()
        n1 = Vector((-e1.y, e1.x))
        n2 = Vector((-e2.y, e2.x))
        bis = n1 + n2
        if bis.length < 1e-6:
            bis = n1.copy()
        bis.normalize()
        cosh = max(0.4, bis.dot(n1))
        res.append(p + bis * (d / cosh))
    return res


def build_badges(arm, tuta):
    """each badge: its pieces extruded (back conformed to the suit, a 45-degree chamfer on top), one object whose
    frame is the badge frame, parented to its bone"""
    spec = json.load(open(os.path.join(HERE, 'badges.json'), encoding='utf-8'))
    ext_mm = spec['uv_extent']
    bvh = bvh_of(tuta)
    out = []
    for key, b in spec['badges'].items():
        o_pt, d_in = Vector(b['ray_origin']), Vector(b['ray_dir']).normalized()
        hit, nrm, _, _ = bvh.ray_cast(o_pt, d_in)
        if hit is None:
            log('badge missed', key)
            continue
        nrm = nrm.normalized()
        up = Vector(b.get('up', (0, 0, 1)))
        u = up.cross(nrm).normalized()                           # badge +x (right, seen from outside)
        v = nrm.cross(u).normalized()                             # badge +y
        rot = math.radians(b.get('rot', 0.0))
        u, v = (u * math.cos(rot) + v * math.sin(rot)), (v * math.cos(rot) - u * math.sin(rot))
        stand = b.get('stand', 0.0015)
        th = b['thickness'] / 1000.0
        bev = min(th * 0.4, 0.0011)
        origin = hit + nrm * stand
        bm = bmesh.new()
        uvl = bm.loops.layers.uv.new('UVMap')

        def conform(x, y, h):
            """badge-plane point (m) dropped onto the suit along -n, lifted by stand + h (badges hug the curve)"""
            p3 = origin + u * x + v * y
            hit2, _, _, _ = bvh.ray_cast(p3 + nrm * 0.05, -nrm)
            if hit2 is None or (hit2 - p3).length > 0.03:
                return p3 + nrm * h
            return hit2 + nrm * (stand + h)
        rim_uv = (1.0 - 16 / 1024, 16 / 1024)                     # the textures' rim swatch (bottom-right 32 px)
        for poly_mm in uf_shapes.pieces_of(b):
            poly = [Vector((x * 0.001, y * 0.001)) for x, y in poly_mm]
            inner = inset_poly(poly, bev)
            n = len(poly)
            back = [bm.verts.new(conform(p.x, p.y, 0.0)) for p in poly]
            mid = [bm.verts.new(conform(p.x, p.y, th - bev)) for p in poly]
            top = [bm.verts.new(conform(q.x, q.y, th)) for q in inner]
            ftop = bm.faces.new(top)
            for loop, q in zip(ftop.loops, inner):
                loop[uvl].uv = (0.5 + q.x * 1000 / ext_mm, 0.5 + q.y * 1000 / ext_mm)
            fback = bm.faces.new(back[::-1])
            for loop in fback.loops:
                loop[uvl].uv = rim_uv
            for k in range(n):
                for quad in ((back[k], back[(k + 1) % n], mid[(k + 1) % n], mid[k]), (mid[k], mid[(k + 1) % n], top[(k + 1) % n], top[k])):
                    f = bm.faces.new(quad)
                    for loop in f.loops:
                        loop[uvl].uv = rim_uv
            bmesh.ops.triangulate(bm, faces=[ftop, fback], quad_method='BEAUTY', ngon_method='EAR_CLIP')
        bm.normal_update()
        me = bpy.data.meshes.new(key)
        bm.to_mesh(me)
        bm.free()
        # the object's frame IS the badge frame: local XY = the badge plane, +Z out of the suit
        M = Matrix((u, v, nrm)).transposed().to_4x4()             # columns = the badge axes
        M.translation = origin
        me.transform(M.inverted())
        ob = bpy.data.objects.new(key, me)
        bpy.data.objects['shirt'].users_collection[0].objects.link(ob)
        ob.matrix_world = M
        img = tex_image(os.path.join(TEX, f'{key}.png'))
        emi = tex_image(os.path.join(TEX, f'{key}_emit.png'))
        m = mtoon(key, (1, 1, 1), outline=0.0, double_sided=False, shade=0.72, emissive=(1, 1, 1), emissive_strength=1.0)
        e1 = m.vrm_addon_extension.mtoon1
        e1.pbr_metallic_roughness.base_color_texture.index.source = img
        e1.extensions.vrmc_materials_mtoon.shade_multiply_texture.index.source = img
        e1.emissive_texture.index.source = emi
        me.materials.append(m)
        for p in me.polygons:
            p.use_smooth = False
        bone_parent(ob, arm, b['bone'])
        out.append(ob)
        log(f'badge {key} on {b["bone"]} at {tuple(round(x, 3) for x in origin)} n {tuple(round(x, 2) for x in nrm)} faces {len(me.polygons)}')
    return out


# ------------------------------------------------------------------------------------------ Balla's sun disc
def build_sundisc(arm):
    """a thin disc of coloured segments behind the petal ring: rings x sectors, the texture paints the segments"""
    face = bpy.data.objects['face']
    fpts = world_verts(face)
    cx = sum(p.x for p in fpts) / len(fpts)
    cz = (min(p.z for p in fpts) + max(p.z for p in fpts)) / 2
    back_y = 0.045                                                # just behind the petals' rearmost point (y 0.014)
    R0, R1 = 0.17, 0.34                                           # paint_badges.py paints R0 / R1 = 0.5
    NR, NA = 4, 96
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    rows = []
    for i in range(NR + 1):
        r = R0 + (R1 - R0) * i / NR
        rows.append([bm.verts.new((cx + r * math.cos(2 * math.pi * k / NA), back_y + 0.004 * i, cz + r * math.sin(2 * math.pi * k / NA))) for k in range(NA)])
    for i in range(NR):
        for k in range(NA):
            f = bm.faces.new((rows[i][k], rows[i][(k + 1) % NA], rows[i + 1][(k + 1) % NA], rows[i + 1][k]))
            for loop in f.loops:
                p = loop.vert.co
                loop[uvl].uv = (0.5 + (p.x - cx) / (2 * R1), 0.5 + (p.z - cz) / (2 * R1))
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    if bm.faces[0].normal.y > 0:                                  # face the front (-Y in Blender)
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    img = tex_image(os.path.join(TEX, 'sundisc.png'))
    emi = tex_image(os.path.join(TEX, 'sundisc_emit.png'))
    m = mtoon('sundisc', (1, 1, 1), outline=0.0, double_sided=True, shade=0.7, emissive=(1, 1, 1))
    e1 = m.vrm_addon_extension.mtoon1
    e1.pbr_metallic_roughness.base_color_texture.index.source = img
    e1.extensions.vrmc_materials_mtoon.shade_multiply_texture.index.source = img
    e1.emissive_texture.index.source = emi
    o = link_new('acc_sundisc', bm, [m])
    bone_parent(o, arm, 'head')
    log('sundisc at', round(cx, 3), round(back_y, 3), round(cz, 3))
    return o


# ------------------------------------------------------------------------------------------ looks (geometry sanity)
def looks(tag, show):
    sc = bpy.context.scene
    eng = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
    sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in eng else 'BLENDER_EEVEE_NEXT'
    sc.render.resolution_x, sc.render.resolution_y = 700, 1000
    if not sc.world:
        sc.world = bpy.data.worlds.new('w')
    sc.world.color = (0.2, 0.21, 0.24)
    for o in bpy.data.objects:
        if o.type == 'MESH':
            o.hide_render = o.name not in show
    cam = bpy.data.objects.new('uf_cam', bpy.data.cameras.new('uf_cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    sun = bpy.data.objects.new('uf_sun', bpy.data.lights.new('uf_sun', 'SUN'))
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(50), 0, math.radians(30))
    sc.collection.objects.link(sun)
    for name, ang, h, dist, lz in (('front', 0, 1.0, 5.0, 1.0), ('back', 180, 1.0, 5.0, 1.0), ('side', 90, 1.0, 5.0, 1.0),
                                   ('neck', 25, 1.3, 1.5, 1.3), ('feet', 30, 0.2, 1.4, 0.14), ('belt', -20, 0.95, 1.4, 0.95)):
        a = math.radians(ang)
        cam.location = (math.sin(a) * dist, -math.cos(a) * dist, h)
        cam.rotation_euler = (Vector((0, 0, lz)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
        cam.data.lens = 50
        sc.render.filepath = os.path.join(REPO, 'work', 'claude_suit_wardrobe_looks', f'wd_blender_{tag}_{name}.png')
        bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam, do_unlink=True)
    bpy.data.objects.remove(sun, do_unlink=True)
    for o in bpy.data.objects:
        if o.type == 'MESH':
            o.hide_render = False


# ------------------------------------------------------------------------------------------ main
bpy.ops.wm.open_mainfile(filepath=SRC)
arm = bpy.data.objects['Armature']
tuta = build_tuta(arm)
boots = build_boots(arm)
straps = build_straps(arm, tuta)
badges = build_badges(arm, tuta) if os.path.exists(os.path.join(HERE, 'badges.json')) else []
disc = build_sundisc(arm) if os.path.exists(os.path.join(TEX, 'sundisc.png')) else None
if '--looks' in argv:
    looks('uf', {'BodyActual', 'face', 'Body', 'flower', 'tuta', 'uf_boots', 'uf_straps', *[b.name for b in badges]})
os.makedirs(os.path.join(REPO, 'work'), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(REPO, 'work', 'claude_suit_wardrobe_tuta.blend'))
if '--no-export' not in argv:
    os.makedirs(os.path.dirname(OUT_VRM), exist_ok=True)
    tmp = OUT_VRM.replace('.vrm', '.part.vrm')
    res = bpy.ops.export_scene.vrm(filepath=tmp, export_invisibles=True, export_only_selections=False)
    if 'FINISHED' in res and os.path.getsize(tmp) > 1_000_000:
        # the petal ring's chest pivot (ring_pivot.py) lives in the VRM, not the .blend: re-apply it to every export
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from ring_pivot import add_ring_pivot
        add_ring_pivot(tmp, tmp)
        os.replace(tmp, OUT_VRM)
    log('export', res, os.path.getsize(OUT_VRM) if os.path.exists(OUT_VRM) else 'missing')

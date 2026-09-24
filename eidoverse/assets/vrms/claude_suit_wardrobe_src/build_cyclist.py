"""RECIPE (as run for the DAISY music video, 2026-09). Its stage inputs were working files that are not kept
here; claude_suit_wardrobe.blend is the finished, editable result. Read README.md in this folder first.

New clothes for digi's claudesona: an 1890s bicycle-club outfit for DAISY's finale.

    bash run_blender.sh eidoverse/assets/vrms/claude_suit_wardrobe_src/build_cyclist.py --stage geo
    bash run_blender.sh eidoverse/assets/vrms/claude_suit_wardrobe_src/build_cyclist.py --stage tex
    bash run_blender.sh eidoverse/assets/vrms/claude_suit_wardrobe_src/build_cyclist.py --stage export

geo    : jersey (from the shirt: puffed + rolled neck), knickerbockers (from the pants: bisected below
         the knee, ballooned, buckled cuff band), argyle socks (lifted from the leg skin), straw boater
         (bone-parented to the head). Every new vertex inherits its source's skin weights. Saves
         cyclist_geo.blend + look renders.
tex    : fresh UVs + baked maps (stripes/knit, tweed, argyle, straw), MToon materials. -> cyclist_tex.blend
export : one VRM carrying BOTH outfits (suit + cyclist) -> work/claude_suit_cyclist_stage.vrm, a stage check
         (the complete wardrobe VRM comes from build_era_garments.py, or export_wardrobe_vrm.py).
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

bpy.ops.preferences.addon_enable(module='bl_ext.blender_org.vrm')
REPO = os.path.dirname(os.path.abspath(__file__))
while REPO != os.path.dirname(REPO) and not os.path.exists(os.path.join(REPO, 'eido.py')):
    REPO = os.path.dirname(REPO)
BL = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(BL, 'tex')
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
STAGE = argv[argv.index('--stage') + 1] if '--stage' in argv else 'geo'

NEW = ('jersey', 'knickers', 'socks', 'boater')
SUIT = ('jacket', 'tie', 'shirt', 'pants')


def log(*a):
    print('[cyclist]', *a, flush=True)


def world_z(o, co):
    return (o.matrix_world @ co).z


def dup(name, newname):
    src = bpy.data.objects[name]
    o = src.copy()
    o.data = src.data.copy()
    o.name = newname
    o.data.name = newname
    for c in src.users_collection:
        c.objects.link(o)
    return o


def to_local(o, p):
    return o.matrix_world.inverted() @ p


def mat_flat(name, rgb):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    ext = m.vrm_addon_extension.mtoon1
    ext.enabled = True
    ext.pbr_metallic_roughness.base_color_factor = (*rgb, 1.0)
    mt = ext.extensions.vrmc_materials_mtoon
    mt.shade_color_factor = tuple(c * 0.6 for c in rgb)
    mt.outline_width_mode = 'worldCoordinates'
    mt.outline_width_factor = 0.005
    mt.outline_color_factor = tuple(c * 0.25 for c in rgb)
    mt.outline_lighting_mix_factor = 0.0
    return m


def set_material(o, m):
    o.data.materials.clear()
    o.data.materials.append(m)


# ---------------------------------------------------------------------------------------- geometry
def build_jersey():
    o = dup('shirt', 'jersey')
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.normal_update()
    for v in bm.verts:                       # wool has body: 7 mm proud of the shirt
        v.co += v.normal * 0.007
    # the neck opening: boundary edges near the top centre
    W = o.matrix_world
    neck = [e for e in bm.edges if e.is_boundary and all((W @ v.co).z > 1.26 and abs((W @ v.co).x) < 0.13 for v in e.verts)]
    log('jersey neck boundary edges:', len(neck))
    if neck:
        vs = {v for e in neck for v in e.verts}
        c = sum(((W @ v.co) for v in vs), Vector()) / len(vs)
        up = to_local(o, c + Vector((0, 0, 1))) - to_local(o, c)
        # roll neck: up 3.2 cm hugging the neck, then a folded lip out and down
        ret = bmesh.ops.extrude_edge_only(bm, edges=neck)
        new1 = [g for g in ret['geom'] if isinstance(g, bmesh.types.BMVert)]
        cl = to_local(o, c)
        for v in new1:
            r = v.co - cl
            r.z = 0
            v.co += up.normalized() * 0.032 - r * 0.06
        e1 = [g for g in ret['geom'] if isinstance(g, bmesh.types.BMEdge) and all(v in new1 for v in g.verts)]
        ret2 = bmesh.ops.extrude_edge_only(bm, edges=e1)
        new2 = [g for g in ret2['geom'] if isinstance(g, bmesh.types.BMVert)]
        for v in new2:
            r = v.co - cl
            r.z = 0
            v.co += r.normalized() * 0.014 - up.normalized() * 0.012
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()
    return o


def build_knickers(knee_z):
    o = dup('pants', 'knickers')
    W = o.matrix_world
    cut = knee_z - 0.05                      # buckled just below the knee
    bm = bmesh.new()
    bm.from_mesh(o.data)
    pl_co = to_local(o, Vector((0, 0, cut)))
    pl_no = (to_local(o, Vector((0, 0, cut + 1))) - pl_co).normalized()
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=pl_co, plane_no=pl_no, clear_inner=True)
    bm.normal_update()
    # balloon: knickerbockers blouse out over the band
    for v in bm.verts:
        z = (W @ v.co).z
        k = (z - cut) / 0.26
        if 0 <= k <= 1:
            v.co += v.normal * 0.03 * math.sin(math.pi * min(1, k * 1.15)) ** 0.8
    cut_edges = [g for g in res['geom_cut'] if isinstance(g, bmesh.types.BMEdge)]
    log('knickers cut edges:', len(cut_edges))
    if cut_edges:
        # the cuff band: fold in 1.5 cm toward each leg's axis, then drop 3.5 cm
        vs = {v for e in cut_edges for v in e.verts}
        legs = {}
        for v in vs:
            legs.setdefault((W @ v.co).x > 0, []).append(v)
        ctr = {k: sum((v.co for v in vv), Vector()) / len(vv) for k, vv in legs.items()}
        down = (to_local(o, Vector((0, 0, cut - 1))) - pl_co).normalized()
        ret = bmesh.ops.extrude_edge_only(bm, edges=cut_edges)
        nv = [g for g in ret['geom'] if isinstance(g, bmesh.types.BMVert)]
        for v in nv:
            c = ctr[(W @ v.co).x > 0]
            r = v.co - c
            r -= r.project(down)
            v.co += -r.normalized() * 0.015
        ne = [g for g in ret['geom'] if isinstance(g, bmesh.types.BMEdge) and all(v in nv for v in g.verts)]
        ret2 = bmesh.ops.extrude_edge_only(bm, edges=ne)
        for g in ret2['geom']:
            if isinstance(g, bmesh.types.BMVert):
                g.co += down * 0.035
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()
    return o, cut


def build_socks(top_z, legs_xy):
    o = dup('BodyActual', 'socks')
    W = o.matrix_world
    bm = bmesh.new()
    bm.from_mesh(o.data)

    def keep(v):
        p = W @ v.co
        if not (0.07 <= p.z <= top_z):
            return False
        return any(math.hypot(p.x - lx, p.y - ly) < 0.095 for lx, ly in legs_xy)
    kill = [f for f in bm.faces if not all(keep(v) for v in f.verts)]
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.normal_update()
    for v in bm.verts:
        v.co += v.normal * 0.004
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()
    log('socks verts:', len(o.data.vertices))
    return o


def build_boater(arm):
    """Straw boater: flat crown, wide brim with a slight upturn, grosgrain band. Bone-parented to head."""
    bm = bmesh.new()
    seg = 48
    r_top, r_bot, h = 0.082, 0.086, 0.052
    r_brim, curl = 0.158, 0.007

    def ring(r, z):
        return [bm.verts.new((r * math.cos(2 * math.pi * i / seg), r * math.sin(2 * math.pi * i / seg), z)) for i in range(seg)]

    def bridge(a, b):
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new((a[i], a[j], b[j], b[i]))
    top = ring(r_top, h)
    bot = ring(r_bot, 0.0)
    bridge(bot, top)
    c = bm.verts.new((0, 0, h + 0.004))                       # a faintly domed crown
    for i in range(seg):
        bm.faces.new((top[i], top[(i + 1) % seg], c))
    under = ring(r_bot, -0.006)
    brim_top = ring(r_brim, curl)
    brim_bot = ring(r_brim, curl - 0.006)
    mid_t = ring((r_bot + r_brim) / 2, 0.0005)
    mid_b = ring((r_bot + r_brim) / 2, -0.0055)
    bridge(mid_t, bot)
    bridge(brim_top, mid_t)
    bridge(brim_bot, brim_top)
    bridge(mid_b, brim_bot)
    bridge(under, mid_b)
    cu = bm.verts.new((0, 0, -0.006))
    for i in range(seg):
        bm.faces.new((under[(i + 1) % seg], under[i], cu))
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new('boater')
    bm.to_mesh(me)
    bm.free()
    hat = bpy.data.objects.new('boater', me)
    bpy.data.objects['shirt'].users_collection[0].objects.link(hat)
    # the grosgrain band: a separate thin ring (its own material)
    bm = bmesh.new()
    lo = ring(r_bot + 0.0015, 0.004)
    hi = ring(r_top + 0.0017, 0.024)
    bridge(lo, hi)
    me2 = bpy.data.meshes.new('boater_band')
    bm.to_mesh(me2)
    bm.free()
    band = bpy.data.objects.new('boater_band', me2)
    hat.users_collection[0].objects.link(band)
    band.parent = hat
    # place: on the top of the face disc, in front of the petal ring, tipped jauntily
    face = bpy.data.objects['face']
    fz = [(face.matrix_world @ v.co) for v in face.data.vertices]
    top_z = max(p.z for p in fz)
    front_y = min(p.y for p in fz)                           # Blender front = -Y
    mid_y = sum(p.y for p in fz) / len(fz)
    hat.location = (0.035, (front_y + mid_y) / 2 - 0.01, top_z - 0.028)
    hat.rotation_euler = (math.radians(-14), math.radians(11), math.radians(8))
    bpy.context.view_layer.update()
    mw = hat.matrix_world.copy()
    hat.parent = arm
    hat.parent_type = 'BONE'
    hat.parent_bone = 'head'
    bpy.context.view_layer.update()
    hat.matrix_world = mw
    return hat, band


def looks(tag, show, hide):
    sc = bpy.context.scene
    eng = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
    sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in eng else 'BLENDER_EEVEE_NEXT'
    sc.render.resolution_x, sc.render.resolution_y = 900, 1100
    if not sc.world:
        sc.world = bpy.data.worlds.new('w')
    sc.world.color = (0.09, 0.1, 0.12)
    for n in hide:
        if n in bpy.data.objects:
            bpy.data.objects[n].hide_render = True
    for n in show:
        if n in bpy.data.objects:
            bpy.data.objects[n].hide_render = False
    cam = bpy.data.objects.get('look_cam') or bpy.data.objects.new('look_cam', bpy.data.cameras.new('look_cam'))
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    sc.camera = cam
    if 'look_sun' not in bpy.data.objects:
        sun = bpy.data.objects.new('look_sun', bpy.data.lights.new('look_sun', 'SUN'))
        sun.data.energy = 3.2
        sun.rotation_euler = (math.radians(52), 0, math.radians(28))
        sc.collection.objects.link(sun)
    shots = [('front', 0, 1.05, 4.6, 50), ('34', 38, 1.05, 4.6, 50), ('legs', 20, 0.45, 2.2, 50), ('head', -12, 1.62, 1.5, 55),
             ('back', 180, 1.05, 4.6, 50)]
    for name, ang, h, dist, lens in shots:
        a = math.radians(ang)
        cam.location = (math.sin(a) * dist, -math.cos(a) * dist, h)
        cam.rotation_euler = (math.radians(90 - math.degrees(math.atan2(h - (1.0 if name != 'head' else 1.62), dist)) + (0 if name != 'legs' else 3)), 0, a)
        cam.data.lens = lens
        sc.render.filepath = os.path.join(BL, f'{tag}_{name}.png')
        bpy.ops.render.render(write_still=True)


def stage_geo():
    bpy.ops.wm.open_mainfile(filepath=os.path.join(BL, 'claude_suit_base.blend'))
    arm = bpy.data.objects['Armature']
    knee = (arm.matrix_world @ arm.data.bones['lower_leg.L'].head_local).z
    log('knee z', round(knee, 3))
    jersey = build_jersey()
    knick, cut = build_knickers(knee)
    pants = bpy.data.objects['pants']
    W = pants.matrix_world
    near = [(W @ v.co) for v in pants.data.vertices if 0.25 < (W @ v.co).z < 0.35]
    legs = []
    for side in (1, -1):
        pts = [p for p in near if p.x * side > 0]
        legs.append((sum(p.x for p in pts) / len(pts), sum(p.y for p in pts) / len(pts)))
    log('leg axes', [(round(x, 3), round(y, 3)) for x, y in legs])
    socks = build_socks(cut + 0.06, legs)
    hat, band = build_boater(arm)
    set_material(jersey, mat_flat('jersey', (0.93, 0.89, 0.8)))
    set_material(knick, mat_flat('knickers', (0.46, 0.43, 0.38)))
    set_material(socks, mat_flat('socks', (0.85, 0.47, 0.34)))
    set_material(hat, mat_flat('straw', (0.86, 0.72, 0.45)))
    set_material(band, mat_flat('ribbon', (0.85, 0.35, 0.2)))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BL, 'cyclist_geo.blend'))
    looks('geo', show=NEW + ('boater_band',), hide=SUIT)
    log('geo done')


if STAGE == 'geo':
    stage_geo()

# ---------------------------------------------------------------------------------------- textures
ORANGE = (0.85, 0.47, 0.34)      # Claude orange (sRGB)
CREAM = (0.94, 0.90, 0.82)
BROWN = (0.30, 0.19, 0.12)


def lin(c):
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)


def setup_cycles():
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type = 'OPTIX'
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
        sc.cycles.device = 'GPU'
    except Exception as e:
        log('cycles GPU unavailable, CPU bake:', e)
    sc.cycles.samples = 8
    sc.render.bake.margin = 12
    sc.render.bake.use_clear = True


def select_only(o):
    for x in bpy.context.view_layer.objects:
        x.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def smart_uv(o):
    select_only(o)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(62), island_margin=0.004, scale_to_bounds=True)
    bpy.ops.object.mode_set(mode='OBJECT')


def new_image(name, size, non_color=False):
    img = bpy.data.images.get(name) or bpy.data.images.new(name, size, size, alpha=False, float_buffer=False)
    if non_color:
        img.colorspace_settings.name = 'Non-Color'
    return img


def bake(o, graph_fn, img, kind='EMIT'):
    """Assign a temporary bake material built by graph_fn(nodes, links, coord) -> (color_socket or normal
    socket), bake into img, restore materials."""
    keep = list(o.data.materials)
    m = bpy.data.materials.new(f'bake_{o.name}_{kind}')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sock = graph_fn(nt.nodes, nt.links, tc.outputs['Object'])
    if kind == 'EMIT':
        em = nt.nodes.new('ShaderNodeEmission')
        nt.links.new(sock, em.inputs['Color'])
        nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
    else:
        bs = nt.nodes.new('ShaderNodeBsdfPrincipled')
        nt.links.new(sock, bs.inputs['Normal'])
        nt.links.new(bs.outputs['BSDF'], out.inputs['Surface'])
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    nt.nodes.active = tex
    o.data.materials.clear()
    o.data.materials.append(m)
    select_only(o)
    if kind == 'EMIT':
        bpy.ops.object.bake(type='EMIT')
    else:
        bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT')
    o.data.materials.clear()
    for k in keep:
        o.data.materials.append(k)
    img.filepath_raw = os.path.join(BL, 'tex_baked', img.name + '.png')
    img.file_format = 'PNG'
    img.save()
    log('baked', img.name)


def N(nodes, t, **kw):
    n = nodes.new(t)
    for k, v in kw.items():
        if k.startswith('in_'):
            n.inputs[int(k[3:])].default_value = v
        else:
            setattr(n, k, v)
    return n


def math_(nodes, links, op, a, b=None, c=None, clamp=False):
    n = nodes.new('ShaderNodeMath')
    n.operation = op
    n.use_clamp = bool(clamp)
    for i, x in enumerate((a, b, c)):
        if x is None:
            continue
        if isinstance(x, (int, float)):
            n.inputs[i].default_value = x
        else:
            links.new(x, n.inputs[i])
    return n.outputs[0]


def box_image(nodes, links, coord, path, scale, non_color=False):
    img = bpy.data.images.load(path, check_existing=True)
    if non_color:
        img.colorspace_settings.name = 'Non-Color'
    mp = nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (scale, scale, scale)
    links.new(coord, mp.inputs['Vector'])
    t = nodes.new('ShaderNodeTexImage')
    t.image = img
    t.projection = 'BOX'
    t.projection_blend = 0.25
    links.new(mp.outputs['Vector'], t.inputs['Vector'])
    return t


def mix_rgb(nodes, links, fac, a, b):
    n = nodes.new('ShaderNodeMix')
    n.data_type = 'RGBA'
    for sock, v in ((n.inputs[0], fac), (n.inputs[6], a), (n.inputs[7], b)):
        if isinstance(v, (tuple, list)):
            sock.default_value = (*v, 1.0) if len(v) == 3 else v
        elif isinstance(v, (int, float)):
            sock.default_value = v
        else:
            links.new(v, sock)
    return n.outputs[2]


def band(nodes, links, c, width):
    """soft 0/1 stripes along coordinate c (width = one full period)"""
    f = math_(nodes, links, 'FRACT', math_(nodes, links, 'DIVIDE', c, width))
    tri = math_(nodes, links, 'ABSOLUTE', math_(nodes, links, 'SUBTRACT', f, 0.5))
    sm = nodes.new('ShaderNodeMapRange')
    sm.interpolation_type = 'SMOOTHSTEP'
    sm.inputs['From Min'].default_value = 0.23
    sm.inputs['From Max'].default_value = 0.27
    links.new(tri, sm.inputs['Value'])
    return sm.outputs['Result']


def knit_mod(nodes, links, coord, color_sock):
    """multiply by the wool scan's luminance, normalised around 1 (the knit reads in the albedo)"""
    w = box_image(nodes, links, coord, os.path.join(TEX, 'wool_boucle_diff_2k.jpg'), 9.0)
    bw = nodes.new('ShaderNodeRGBToBW')
    links.new(w.outputs['Color'], bw.inputs['Color'])
    k = math_(nodes, links, 'MULTIPLY_ADD', bw.outputs['Val'], 0.55, 0.72)
    mul = nodes.new('ShaderNodeMix')
    mul.data_type = 'RGBA'
    mul.blend_type = 'MULTIPLY'
    mul.inputs[0].default_value = 1.0
    links.new(color_sock, mul.inputs[6])
    cr = nodes.new('ShaderNodeCombineColor')
    for i in range(3):
        links.new(k, cr.inputs[i])
    links.new(cr.outputs['Color'], mul.inputs[7])
    return mul.outputs[2]


def jersey_color(nodes, links, coord):
    sep = nodes.new('ShaderNodeSeparateXYZ')
    links.new(coord, sep.inputs['Vector'])
    ax = math_(nodes, links, 'ABSOLUTE', sep.outputs['X'])
    torso = band(nodes, links, sep.outputs['Z'], 0.064)
    sleeve = band(nodes, links, ax, 0.064)
    wsl = nodes.new('ShaderNodeMapRange')
    wsl.interpolation_type = 'SMOOTHSTEP'
    wsl.inputs['From Min'].default_value = 0.19
    wsl.inputs['From Max'].default_value = 0.235
    links.new(ax, wsl.inputs['Value'])
    fac = mix_rgb(nodes, links, wsl.outputs['Result'], torso, sleeve)
    bw = nodes.new('ShaderNodeRGBToBW')
    links.new(fac, bw.inputs['Color'])
    col = mix_rgb(nodes, links, bw.outputs['Val'], lin(CREAM), lin(ORANGE))
    # rib bands in solid orange: roll neck, waistband, cuffs
    neck = math_(nodes, links, 'GREATER_THAN', sep.outputs['Z'], 1.355)
    waist = math_(nodes, links, 'LESS_THAN', sep.outputs['Z'], 0.985)
    cuff = math_(nodes, links, 'GREATER_THAN', ax, 0.655)
    rib = math_(nodes, links, 'MAXIMUM', math_(nodes, links, 'MAXIMUM', neck, waist), cuff)
    col = mix_rgb(nodes, links, rib, col, tuple(x * 0.82 for x in lin(ORANGE)))
    return knit_mod(nodes, links, coord, col)


def knit_normal(nodes, links, coord):
    t = box_image(nodes, links, coord, os.path.join(TEX, 'wool_boucle_nor_gl_2k.jpg'), 9.0, non_color=True)
    nm = nodes.new('ShaderNodeNormalMap')
    nm.inputs['Strength'].default_value = 0.8
    links.new(t.outputs['Color'], nm.inputs['Color'])
    return nm.outputs['Normal']


def tweed_color(nodes, links, coord):
    t = box_image(nodes, links, coord, os.path.join(TEX, 'texturecan_181_diff.jpg'), 5.5)
    warm = nodes.new('ShaderNodeMix')
    warm.data_type = 'RGBA'
    warm.blend_type = 'MULTIPLY'
    warm.inputs[0].default_value = 1.0
    links.new(t.outputs['Color'], warm.inputs[6])
    warm.inputs[7].default_value = (1.0, 0.93, 0.84, 1.0)
    sep = nodes.new('ShaderNodeSeparateXYZ')
    links.new(coord, sep.inputs['Vector'])
    cuff = math_(nodes, links, 'LESS_THAN', sep.outputs['Z'], CUFF_Z + 0.004)
    return mix_rgb(nodes, links, cuff, warm.outputs[2], tuple(x * 0.55 for x in lin((0.42, 0.36, 0.3))))


def tweed_normal(nodes, links, coord):
    t = box_image(nodes, links, coord, os.path.join(TEX, 'texturecan_181_normal.png'), 5.5, non_color=True)
    nm = nodes.new('ShaderNodeNormalMap')
    nm.inputs['Strength'].default_value = 1.0
    links.new(t.outputs['Color'], nm.inputs['Color'])
    return nm.outputs['Normal']


def straw_color(nodes, links, coord):
    sep = nodes.new('ShaderNodeSeparateXYZ')
    links.new(coord, sep.inputs['Vector'])
    r = math_(nodes, links, 'SQRT', math_(nodes, links, 'ADD', math_(nodes, links, 'POWER', sep.outputs['X'], 2.0),
                                          math_(nodes, links, 'POWER', sep.outputs['Y'], 2.0)))
    ang = math_(nodes, links, 'ARCTAN2', sep.outputs['Y'], sep.outputs['X'])
    rings = band(nodes, links, math_(nodes, links, 'ADD', r, sep.outputs['Z']), 0.0045)       # braided rows
    weave = band(nodes, links, math_(nodes, links, 'MULTIPLY', ang, 0.03), 0.0055)
    v = math_(nodes, links, 'MULTIPLY_ADD', rings, 0.22, math_(nodes, links, 'MULTIPLY', weave, 0.1))
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 260.0
    links.new(coord, noise.inputs['Vector'])
    v = math_(nodes, links, 'MULTIPLY_ADD', noise.outputs['Fac'], 0.25, v)
    return mix_rgb(nodes, links, v, lin((0.93, 0.8, 0.54)), lin((0.66, 0.5, 0.28)))


def ribbon_color(nodes, links, coord):
    sep = nodes.new('ShaderNodeSeparateXYZ')
    links.new(coord, sep.inputs['Vector'])
    ribs = band(nodes, links, sep.outputs['Z'], 0.0016)                                      # grosgrain
    return mix_rgb(nodes, links, math_(nodes, links, 'MULTIPLY', ribs, 0.25), lin(ORANGE), tuple(x * 0.7 for x in lin(ORANGE)))


def argyle_uv_and_image(o, legs):
    """Per-leg cylindrical UVs (left leg u 0-0.5, right 0.5-1; v up the sock) and a painted argyle."""
    import numpy as np
    me = o.data
    W = o.matrix_world
    if not me.uv_layers:
        me.uv_layers.new(name='UVMap')
    uvl = me.uv_layers.active.data
    zs = [(W @ v.co).z for v in me.vertices]
    z0, z1 = min(zs), max(zs)
    for poly in me.polygons:
        pts = [W @ me.vertices[me.loops[li].vertex_index].co for li in poly.loop_indices]
        side = 0 if sum(p.x for p in pts) > 0 else 1           # +x is the character's left
        cx, cy = legs[side]
        angs = [math.atan2(p.y - cy, p.x - cx) for p in pts]
        ref = angs[0]
        for li, p, a in zip(poly.loop_indices, pts, angs):
            while a - ref > math.pi:
                a -= 2 * math.pi
            while a - ref < -math.pi:
                a += 2 * math.pi
            u = ((a + math.pi) / (2 * math.pi)) % 1.0 if abs(angs[0]) < 3.0 else (a + math.pi) / (2 * math.pi)
            uvl[li].uv = (0.5 * side + 0.5 * min(max(u, 0.0), 1.0), (p.z - z0) / max(1e-6, z1 - z0))
    S = 1024
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float64)
    u = (xx / S * 2.0) % 1.0
    v = 1.0 - yy / S
    # argyle: 4 diamonds around the leg; diamond height ~ 1.35 x width (the sock is ~0.43 m tall, ~0.3 m round)
    n_around, height_ratio = 4.0, 1.35
    ux = u * n_around
    vy = v * (z1 - z0) / (0.3 / n_around * height_ratio)
    a1 = np.floor(ux + vy)
    a2 = np.floor(ux - vy)
    parity = ((a1 + a2) % 2 == 0)
    img = np.zeros((S, S, 3))
    img[parity] = ORANGE
    img[~parity] = BROWN
    # the overcheck: thin cream diagonals through the diamond centres
    d1 = np.abs(((ux + vy + 0.5) % 1.0) - 0.5)
    d2 = np.abs(((ux - vy + 0.5) % 1.0) - 0.5)
    line = (np.minimum(d1, d2) < 0.035)
    img[line] = CREAM
    # the ribbed turn-down at the top 5 cm and a heel-toe darkening at the bottom
    top = v > 1.0 - 0.05 / (z1 - z0)
    img[top] = np.array(BROWN) * 0.9 + (np.sin(xx[top] * 0.6)[:, None] * 0.03)
    im = new_image('socks_argyle', S)
    px = np.concatenate([img[::-1], np.ones((S, S, 1))], axis=2).reshape(-1)
    im.pixels = [float(x) for x in px]
    im.filepath_raw = os.path.join(BL, 'tex_baked', 'socks_argyle.png')
    im.file_format = 'PNG'
    im.save()
    return im


def mat_tex(name, base_img, nrm_img=None, shade=0.62):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    ext = m.vrm_addon_extension.mtoon1
    ext.enabled = True
    ext.pbr_metallic_roughness.base_color_factor = (1, 1, 1, 1)
    ext.pbr_metallic_roughness.base_color_texture.index.source = base_img
    mt = ext.extensions.vrmc_materials_mtoon
    mt.shade_color_factor = (shade, shade, shade)
    mt.shade_multiply_texture.index.source = base_img
    if nrm_img is not None:
        ext.normal_texture.index.source = nrm_img
    mt.outline_width_mode = 'worldCoordinates'
    mt.outline_width_factor = 0.005
    mt.outline_color_factor = (0.18, 0.14, 0.12)
    mt.outline_lighting_mix_factor = 0.0
    return m


def stage_tex():
    global CUFF_Z
    bpy.ops.wm.open_mainfile(filepath=os.path.join(BL, 'cyclist_geo.blend'))
    os.makedirs(os.path.join(BL, 'tex_baked'), exist_ok=True)
    arm = bpy.data.objects['Armature']
    knee = (arm.matrix_world @ arm.data.bones['lower_leg.L'].head_local).z
    CUFF_Z = knee - 0.05 - 0.035
    setup_cycles()
    jersey, knick, socks = (bpy.data.objects[n] for n in ('jersey', 'knickers', 'socks'))
    hat, band_o = bpy.data.objects['boater'], bpy.data.objects['boater_band']
    for o in (jersey, knick, hat, band_o):
        smart_uv(o)
    pants = bpy.data.objects['pants']
    W = pants.matrix_world
    near = [(W @ v.co) for v in pants.data.vertices if 0.25 < (W @ v.co).z < 0.35]
    legs = []
    for side in (1, -1):
        pts = [p for p in near if p.x * side > 0]
        legs.append((sum(p.x for p in pts) / len(pts), sum(p.y for p in pts) / len(pts)))
    imgs = {}
    imgs['jersey_c'] = new_image('jersey_color', 2048)
    bake(jersey, jersey_color, imgs['jersey_c'])
    imgs['jersey_n'] = new_image('jersey_normal', 2048, non_color=True)
    bake(jersey, knit_normal, imgs['jersey_n'], 'NORMAL')
    imgs['knick_c'] = new_image('knickers_color', 2048)
    bake(knick, tweed_color, imgs['knick_c'])
    imgs['knick_n'] = new_image('knickers_normal', 2048, non_color=True)
    bake(knick, tweed_normal, imgs['knick_n'], 'NORMAL')
    imgs['straw'] = new_image('boater_straw', 1024)
    bake(hat, straw_color, imgs['straw'])
    imgs['ribbon'] = new_image('boater_ribbon', 256)
    bake(band_o, ribbon_color, imgs['ribbon'])
    imgs['socks'] = argyle_uv_and_image(socks, legs)
    imgs['socks_n'] = new_image('socks_normal', 1024, non_color=True)
    bake(socks, knit_normal, imgs['socks_n'], 'NORMAL')
    set_material(jersey, mat_tex('jersey', imgs['jersey_c'], imgs['jersey_n']))
    set_material(knick, mat_tex('knickers', imgs['knick_c'], imgs['knick_n']))
    set_material(socks, mat_tex('socks', imgs['socks'], imgs['socks_n']))
    set_material(hat, mat_tex('straw', imgs['straw']))
    set_material(band_o, mat_tex('ribbon', imgs['ribbon']))
    for im in bpy.data.images:
        if im.filepath_raw and 'tex_baked' in im.filepath_raw:
            im.pack()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BL, 'cyclist_tex.blend'))
    looks('tex', show=NEW + ('boater_band',), hide=SUIT)
    log('tex done')


CUFF_Z = 0.4
if STAGE == 'tex':
    stage_tex()


# ---------------------------------------------------------------------------------------- export
def stage_export():
    bpy.ops.wm.open_mainfile(filepath=os.path.join(BL, 'cyclist_tex.blend'))
    for n in ('look_cam', 'look_sun'):
        o = bpy.data.objects.get(n)
        if o:
            bpy.data.objects.remove(o, do_unlink=True)
    for o in bpy.data.objects:
        if o.type == 'MESH':
            o.hide_render = False
            o.hide_viewport = False
            o.hide_set(False)
    op = bpy.ops.export_scene.vrm
    props = [p.identifier for p in op.get_rna_type().properties if p.identifier not in ('rna_type',)]
    log('export props:', props)
    out = os.path.join(REPO, 'work', 'claude_suit_cyclist_stage.vrm')    # never the library VRM: a subset
    os.makedirs(os.path.dirname(out), exist_ok=True)
    kw = {'filepath': out}
    if 'export_invisibles' in props:
        kw['export_invisibles'] = True
    if 'export_only_selections' in props:
        kw['export_only_selections'] = False
    res = op(**kw)
    log('export:', res, os.path.getsize(out) if os.path.exists(out) else 'missing')


if STAGE == 'export':
    stage_export()

"""camp_lib.py - helpers for the Vibecamp campsite assets (tents, bulb, pole, campfire, bench).
Builds on clib (never edits it)."""
import bpy, bmesh, math, os, random
from mathutils import Vector, Matrix, Euler, noise as mnoise
from clib import *


# ------------------------------------------------------------------------------ look-loop renders
def _rig(target, dist, energy=None, warm=False):
    lights = []
    ctr = Vector(target)
    ke = energy or 60.0 * dist * dist
    rig = (((dist, -dist, dist * 1.1), ke, (1, 0.92, 0.82)),
           ((-dist * 1.1, -dist * 0.5, dist * 0.45), ke * 0.3, (0.78, 0.86, 1.0)),
           ((0.2 * dist, dist * 1.1, dist * 0.8), ke * 0.55, (1, 1, 1)))
    for loc, en, col in rig:
        ld = bpy.data.lights.new('rig', 'AREA')
        ld.energy = en
        ld.size = dist * 0.8
        ld.color = col
        lo = bpy.data.objects.new('rig', ld)
        link(lo)
        lo.location = ctr + Vector(loc)
        lo.rotation_euler = (ctr - lo.location).to_track_quat('-Z', 'Y').to_euler()
        lights.append(lo)
    return lights


def world(color=(0.55, 0.6, 0.68), strength=0.2):
    sc = bpy.context.scene
    w = sc.world or bpy.data.worlds.new('w')
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (*color, 1)
    bg.inputs['Strength'].default_value = strength
    return w


def lit_shot(filename, cam_pos, target, lens=50, size=768, samples=64, energy=None, night=False,
             extra_lights=(), res=None):
    """A lit close-up for the look-loop (clib.closeup adds no lights)."""
    sc = bpy.context.scene
    sc.cycles.samples = samples
    try:
        sc.cycles.use_denoising = True
    except Exception:
        pass
    sc.render.resolution_x = res[0] if res else size
    sc.render.resolution_y = res[1] if res else size
    dist = (Vector(cam_pos) - Vector(target)).length
    if night:
        world((0.05, 0.07, 0.12), 0.35)
        lights = []
    else:
        world((0.55, 0.6, 0.68), 0.25)
        lights = _rig(target, max(dist * 0.9, 0.3), energy)
    for (loc, en, col, rad) in extra_lights:
        ld = bpy.data.lights.new('xl', 'POINT')
        ld.energy = en
        ld.color = col
        ld.shadow_soft_size = rad
        lo = bpy.data.objects.new('xl', ld)
        link(lo)
        lo.location = Vector(loc)
        lights.append(lo)
    cd = bpy.data.cameras.new('shot')
    cd.lens = lens
    cam = bpy.data.objects.new('shot', cd)
    link(cam)
    cam.location = Vector(cam_pos)
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.camera = cam
    sc.render.filepath = os.path.join(PREV, f'{filename}.png')
    bpy.ops.render.render(write_still=True)
    for lo in lights:
        bpy.data.objects.remove(lo)
    bpy.data.objects.remove(cam)
    print(f'[camp] shot {sc.render.filepath}', flush=True)
    return sc.render.filepath


def ground_plane(size=8.0, tex='Ground106', z=0.0):
    """A preview-only ground so hems/stakes read in context (never exported)."""
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=2, y_segments=2, size=size / 2)
    for v in bm.verts:
        v.co.z = z
    m = layered_mat('pv_ground', tex, scale=0.6, nstr=0.8)
    o = obj_from_bm('pv_ground', bm, m)
    uv_tex(o, 1.0)
    return o


# ------------------------------------------------------------------------------ material helpers
def mat_nodes(mat):
    return NB(mat)


def get_bsdf(mat):
    return next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')


def add_bump(mat, height_fn, strength=0.3, distance=0.001):
    """Insert a Bump node between the material's normal source and the BSDF. height_fn(nb)->socket."""
    nb = NB(mat)
    bs = get_bsdf(mat)
    bump = nb.n('ShaderNodeBump')
    bump.inputs['Strength'].default_value = strength
    bump.inputs['Distance'].default_value = distance
    if bs.inputs['Normal'].links:
        src = bs.inputs['Normal'].links[0].from_socket
        nb.l(src, bump.inputs['Normal'])
    nb.l(height_fn(nb), bump.inputs['Height'])
    nb.l(bump.outputs['Normal'], bs.inputs['Normal'])
    return bump


def set_glow(mat, glow_fn):
    """Store an emissive-ready socket as reroute OUT_GLOW (baked separately)."""
    nb = NB(mat)
    rr = nb.n('NodeReroute', name='OUT_GLOW', label='OUT_GLOW')
    s = glow_fn(nb)
    if isinstance(s, tuple):
        rgb = nb.n('ShaderNodeRGB')
        rgb.outputs[0].default_value = (*s[:3], 1)
        s = rgb.outputs[0]
    nb.l(s, rr.inputs[0])
    return rr


def obj_coord(nb):
    return nb.n('ShaderNodeTexCoord').outputs['Object']


def sep_xyz(nb, vec):
    s = nb.n('ShaderNodeSeparateXYZ')
    nb.l(vec, s.inputs[0])
    return s.outputs['X'], s.outputs['Y'], s.outputs['Z']


def out_color_socket(mat):
    """The socket currently feeding OUT_COLOR (to wrap more layers after layered_mat)."""
    nt = mat.node_tree
    rr = nt.nodes.get('OUT_COLOR')
    return rr.inputs[0].links[0].from_socket, rr


def wrap_color(mat, fn):
    """fn(nb, color_socket) -> new color socket; rewires OUT_COLOR."""
    nb = NB(mat)
    src, rr = out_color_socket(mat)
    nt = mat.node_tree
    for lk in list(rr.inputs[0].links):
        nt.links.remove(lk)
    new = fn(nb, src)
    nb.l(new, rr.inputs[0])


def wrap_rough(mat, fn):
    nb = NB(mat)
    nt = mat.node_tree
    rr = nt.nodes.get('OUT_ROUGH')
    src = rr.inputs[0].links[0].from_socket
    for lk in list(rr.inputs[0].links):
        nt.links.remove(lk)
    nb.l(fn(nb, src), rr.inputs[0])


def voronoi_cracks(nb, vec, scale=18.0, width=0.06):
    """1 inside cracks (Voronoi distance-to-edge), 0 elsewhere."""
    v = nb.n('ShaderNodeTexVoronoi', feature='DISTANCE_TO_EDGE')
    v.inputs['Scale'].default_value = scale
    nb.l(vec, v.inputs['Vector'])
    return nb.ramp(v.outputs['Distance'], 0.0, width, (1, 1, 1, 1), (0, 0, 0, 1))


# ------------------------------------------------------------------------------ bake extensions
def bake_glow(o, key, size=2048, samples=16):
    """Bake the OUT_GLOW reroutes of every material (EMIT) into BAKED/<key>_glow.jpg."""
    sc = bpy.context.scene
    sc.cycles.samples = samples
    me = o.data
    me.uv_layers.active = me.uv_layers['BakeUV']
    for uvl in me.uv_layers:
        uvl.active_render = (uvl.name == 'BakeUV')
    select_only(o)
    im = bpy.data.images.new(f'{key}_glow', size, size, alpha=False)
    mats = [s.material for s in o.material_slots if s.material]
    tnodes, routed = [], []
    for mt in mats:
        tn = mt.node_tree.nodes.new('ShaderNodeTexImage')
        tn.image = im
        mt.node_tree.nodes.active = tn
        tnodes.append((mt, tn))
        routed.append((mt, clib_emit_route(mt, 'OUT_GLOW', 0.0)))
    bpy.ops.object.bake(type='EMIT', margin=12, use_clear=True)
    for mt, (em, prev, out) in routed:
        if prev is not None:
            mt.node_tree.links.new(prev, out.inputs['Surface'])
        mt.node_tree.nodes.remove(em)
    for mt, tn in tnodes:
        mt.node_tree.nodes.remove(tn)
    path = os.path.join(BAKED, f'{key}_glow.jpg')
    im.filepath_raw = path
    im.file_format = 'JPEG'
    im.save()
    print(f'[camp] baked {key}_glow', flush=True)
    return path


def clib_emit_route(mat, sock_name, default):
    import clib
    return clib._emit_route(mat, sock_name, default)


def add_emissive(mat, img_path, factor=(1.0, 1.0, 1.0), strength=1.0):
    """Wire an emissive texture into an export material: Image -> Mix(MULTIPLY, factor) -> Emission.
    The glTF exporter reads the constant B input as emissiveFactor. strength=0 exports the map with
    emissiveFactor unset (0) so the engine switches it on."""
    nb = NB(mat)
    bs = get_bsdf(mat)
    uvn = nb.n('ShaderNodeUVMap', uv_map='BakeUV')
    ti = nb.n('ShaderNodeTexImage')
    ti.image = load_img(img_path)
    nb.l(uvn.outputs[0], ti.inputs[0])
    if factor != (1.0, 1.0, 1.0):
        mx = nb.n('ShaderNodeMix', data_type='RGBA', blend_type='MULTIPLY')
        mx.inputs['Factor'].default_value = 1.0
        nb.l(ti.outputs['Color'], mx.inputs[6])
        mx.inputs[7].default_value = (*factor, 1.0)
        nb.l(mx.outputs[2], bs.inputs['Emission Color'])
    else:
        nb.l(ti.outputs['Color'], bs.inputs['Emission Color'])
    bs.inputs['Emission Strength'].default_value = strength
    return mat


def finalize_export_material(mat, cull=True):
    mat.use_backface_culling = cull
    return mat


def bake_all(o, key, size=2048, samples=40, ao_dist=0.1):
    """bake() + export_material() WITHOUT swapping (so variants can re-bake colour)."""
    imgs = bake(o, key, size=size, samples=samples, ao_dist=ao_dist)
    m = export_material(key, imgs)
    return imgs, m


def swap_to(o, m):
    o.data.materials.clear()
    o.data.materials.append(m)
    for p in o.data.polygons:
        p.material_index = 0
    if 'TexUV' in o.data.uv_layers:
        o.data.uv_layers.remove(o.data.uv_layers['TexUV'])
    o.data.uv_layers['BakeUV'].active = True
    o.data.uv_layers['BakeUV'].active_render = True


def dup(o, name):
    c = o.copy()
    c.data = o.data.copy()
    c.name = name
    link(c)
    return c


def solidify(o, thickness, offset=-1.0, rim=True):
    m = o.modifiers.new('solid', 'SOLIDIFY')
    m.thickness = thickness
    m.offset = offset
    m.use_rim = rim
    m.use_even_offset = True
    apply_mods(o)
    return o


def boolean(o, cutter, op='DIFFERENCE'):
    m = o.modifiers.new('bool', 'BOOLEAN')
    m.operation = op
    m.object = cutter
    m.solver = 'EXACT'
    try:
        m.material_mode = 'TRANSFER'
    except Exception:
        pass
    apply_mods(o)
    bpy.data.objects.remove(cutter)
    return o


def catenary(a, b, sag, n=24):
    """Points on a hanging cable from a to b whose lowest point sits `sag` below the chord midpoint
    (parabolic approximation of a shallow catenary; exact enough for sag/span < 0.1)."""
    a, b = Vector(a), Vector(b)
    pts = []
    for i in range(n + 1):
        t = i / n
        p = a.lerp(b, t)
        p.z -= 4.0 * sag * t * (1 - t)
        pts.append(p)
    return pts


def rng(seed):
    r = random.Random(seed)
    return r


def ramp_s(nb, v, a, b, ca=(0, 0, 0, 1), cb=(1, 1, 1, 1)):
    """Order-safe ColorRamp: Blender does NOT re-sort stops set from Python, so a descending
    (a > b) ramp silently inverts. Swap stops + colours instead."""
    if a > b:
        a, b, ca, cb = b, a, cb, ca
    return nb.ramp(v, a, b, ca, cb)

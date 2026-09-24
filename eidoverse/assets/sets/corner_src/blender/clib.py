"""clib.py - shared Blender helpers for the DAISY corner/march set (Claude's Corner + the Vibecamp march).

Run asset scripts headless:
    blender.exe -b --factory-startup -P build_<asset>.py

Conventions
- Blender is Z-up; the glTF exporter writes Y-up (glTF (x, y, z) = Blender (x, z, -y)).
  So an object's FRONT faces Blender -Y (it faces +Z in eidoverse). Metres throughout.
- Every asset gets two UV maps: 'TexUV' (world-scaled projection that the layered material
  samples its AmbientCG maps with) and 'BakeUV' (a packed 0..1 atlas). The layered material
  (base PBR + edge wear + cavity grime + dust) is BAKED DOWN to color / ORM / normal on BakeUV,
  then the export material uses only the baked maps. TexUV is dropped before export.
- Objects the engine drives with its own material keep a plain named material
  ('SCREEN', 'PAGE', 'SHADE', 'BULB', 'GLASS', ...) and are exported unbaked.
"""
import bpy, bmesh, math, os, random
from mathutils import Vector, Matrix, Euler

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TEX = os.path.join(ROOT, 'tex')
GLB = os.path.join(ROOT, 'glb')
PREV = os.path.join(ROOT, 'previews')
BAKED = os.path.join(ROOT, 'baked')
for d in (GLB, PREV, BAKED):
    os.makedirs(d, exist_ok=True)


# ----------------------------------------------------------------------------------------- scene
def reset(samples=32):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    try:
        prefs.compute_device_type = 'OPTIX'
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type != 'CPU'
        sc.cycles.device = 'GPU'
    except Exception as e:
        print('[clib] GPU unavailable, CPU bake:', e)
    sc.cycles.samples = samples
    sc.render.bake.margin = 12
    sc.view_settings.view_transform = 'AgX'
    sc.unit_settings.system = 'METRIC'
    return sc


def link(o):
    bpy.context.collection.objects.link(o)
    return o


def select_only(objs):
    bpy.ops.object.select_all(action='DESELECT')
    objs = objs if isinstance(objs, (list, tuple)) else [objs]
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def obj_from_bm(name, bm, mat=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    link(o)
    if mat is not None:
        o.data.materials.append(mat)
    return o


def apply_mods(o):
    select_only(o)
    for m in list(o.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)


def bevel_mod(o, width, segments=3, limit='ANGLE', angle=40, profile=0.5, harden=True):
    m = o.modifiers.new('bevel', 'BEVEL')
    m.width = width
    m.segments = segments
    m.limit_method = limit
    if limit == 'ANGLE':
        m.angle_limit = math.radians(angle)
    m.profile = profile
    m.harden_normals = harden
    m.use_clamp_overlap = True
    return m


def smooth(o, angle=35):
    select_only(o)
    try:
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle))
    except Exception:
        for p in o.data.polygons:
            p.use_smooth = True


def weighted_normals(o):
    m = o.modifiers.new('wn', 'WEIGHTED_NORMAL')
    m.keep_sharp = True
    return m


def finish(o, bevel=None, segments=3, angle=40, smooth_angle=35):
    """Bevel (machining radius) + smooth-by-angle + weighted normals, applied."""
    if bevel:
        bevel_mod(o, bevel, segments, angle=angle)
    apply_mods(o)
    smooth(o, smooth_angle)
    weighted_normals(o)
    apply_mods(o)
    return o


def join(objs, name):
    select_only(objs)
    bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = name
    o.data.name = name
    return o


def set_origin(o, point):
    """Move the object's origin to a world-space point without moving the geometry."""
    p = Vector(point)
    mw = o.matrix_world.copy()
    local = mw.inverted() @ p
    o.data.transform(Matrix.Translation(-local))
    o.matrix_world = mw @ Matrix.Translation(local)


# ------------------------------------------------------------------------------ bmesh builders
def bm_box(bm, sx, sy, sz, cx=0.0, cy=0.0, cz=0.0):
    r = bmesh.ops.create_cube(bm, size=1.0)
    vs = r['verts']
    for v in vs:
        v.co = Vector((v.co.x * sx + cx, v.co.y * sy + cy, v.co.z * sz + cz))
    return vs


def bm_lathe(bm, profile, segs=48, axis='Z', close_top=False, close_bottom=False, angle=math.tau):
    """Revolve a list of (r, h) points around Z. Returns new verts. profile runs bottom->top."""
    vs = [bm.verts.new((r, 0.0, h)) for r, h in profile]
    es = [bm.edges.new((vs[i], vs[i + 1])) for i in range(len(vs) - 1)]
    res = bmesh.ops.spin(bm, geom=vs + es, cent=(0, 0, 0), axis=(0, 0, 1), angle=angle, steps=segs,
                         use_merge=abs(angle - math.tau) < 1e-6, use_duplicate=False)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    return res


def lathe_obj(name, profile, segs=48, mat=None, smooth_all=True):
    bm = bmesh.new()
    bm_lathe(bm, profile, segs)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = obj_from_bm(name, bm, mat)
    if smooth_all:
        smooth(o, 50)
    return o


def tube_obj(name, points, radius, mat=None, res=10, bevel_res=3, caps=True):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = radius
    cu.bevel_resolution = bevel_res
    cu.use_fill_caps = caps
    sp = cu.splines.new('POLY')
    sp.points.add(len(points) - 1)
    for p, v in zip(sp.points, points):
        p.co = (v[0], v[1], v[2], 1)
    o = bpy.data.objects.new(name, cu)
    link(o)
    select_only(o)
    bpy.ops.object.convert(target='MESH')
    o = bpy.context.view_layer.objects.active
    o.name = name
    if mat is not None:
        o.data.materials.clear()
        o.data.materials.append(mat)
    smooth(o, 60)
    return o


def bezier_points(pts, n=24):
    """Catmull-Rom through pts -> n samples (list of Vector)."""
    P = [Vector(p) for p in pts]
    out = []
    for i in range(len(P) - 1):
        p0 = P[max(0, i - 1)]; p1 = P[i]; p2 = P[i + 1]; p3 = P[min(len(P) - 1, i + 2)]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(P[-1])
    return out


# ----------------------------------------------------------------------------------- textures
def acg(tex_id):
    d = os.path.join(TEX, tex_id)
    maps = {}
    for f in os.listdir(d):
        fl = f.lower()
        full = os.path.join(d, f)
        if fl.endswith('_color.jpg'): maps['color'] = full
        elif fl.endswith('_roughness.jpg'): maps['rough'] = full
        elif fl.endswith('_normalgl.jpg'): maps['normal'] = full
        elif fl.endswith('_ambientocclusion.jpg'): maps['ao'] = full
        elif fl.endswith('_metalness.jpg'): maps['metal'] = full
        elif fl.endswith('_displacement.jpg'): maps['disp'] = full
    return maps


def load_img(path, color=True):
    im = bpy.data.images.load(path, check_existing=True)
    if not color:
        im.colorspace_settings.name = 'Non-Color'
    return im


# ------------------------------------------------------------------------- layered materials
class NB:
    """Tiny node-building helper."""
    def __init__(self, mat):
        self.nt = mat.node_tree
        self.N = self.nt.nodes
        self.L = self.nt.links

    def n(self, kind, **props):
        node = self.N.new(kind)
        for k, v in props.items():
            setattr(node, k, v)
        return node

    def l(self, a, b):
        self.L.new(a, b)

    def math(self, op, a, b=None, clamp=False):
        m = self.n('ShaderNodeMath', operation=op, use_clamp=clamp)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                m.inputs[i].default_value = v
            else:
                self.l(v, m.inputs[i])
        return m.outputs[0]

    def mix(self, fac, a, b, blend='MIX', clamp=True):
        m = self.n('ShaderNodeMixRGB', blend_type=blend, use_clamp=clamp)
        for sock, v in ((m.inputs[0], fac), (m.inputs[1], a), (m.inputs[2], b)):
            if isinstance(v, (int, float)):
                sock.default_value = v
            elif isinstance(v, tuple):
                sock.default_value = (*v[:3], 1.0) if len(v) >= 3 else v
            else:
                self.l(v, sock)
        return m.outputs[0]

    def ramp(self, v, a, b, ca=(0, 0, 0, 1), cb=(1, 1, 1, 1)):
        r = self.n('ShaderNodeValToRGB')
        r.color_ramp.elements[0].position = a
        r.color_ramp.elements[0].color = ca
        r.color_ramp.elements[1].position = b
        r.color_ramp.elements[1].color = cb
        self.l(v, r.inputs[0])
        return r.outputs['Color']

    def noise(self, vec, scale=6.0, detail=4.0, rough=0.55):
        t = self.n('ShaderNodeTexNoise')
        t.inputs['Scale'].default_value = scale
        t.inputs['Detail'].default_value = detail
        t.inputs['Roughness'].default_value = rough
        if vec is not None:
            self.l(vec, t.inputs['Vector'])
        return t.outputs['Fac']


def layered_mat(name, tex_id, *, scale=1.0, rot=0.0, tint=None, tint_amt=1.0, sat=1.0, val=1.0,
                rough_mul=1.0, rough_add=0.0, metal=None, nstr=1.0,
                wear=None, grime=None, dust=None, emission=None, extra_color=None):
    """AmbientCG base + layered masks. Stores the final color/rough/metal sockets as named
    reroutes OUT_COLOR / OUT_ROUGH / OUT_METAL so bake() can route them through emission.

    wear  = dict(color=(r,g,b), radius=0.004, amount=1.0, rough=0.35, noise=12)   convex edges
    grime = dict(color=(r,g,b), dist=0.05, amount=0.7, rough=+0.15)                 cavities (AO)
    dust  = dict(color=(r,g,b), amount=0.3)                                        up-facing
    extra_color(nb, color_socket, uvvec) -> socket   : optional hook for bespoke layers
    """
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nb = NB(m)
    nb.N.clear()
    out = nb.n('ShaderNodeOutputMaterial')
    bs = nb.n('ShaderNodeBsdfPrincipled')
    nb.l(bs.outputs[0], out.inputs[0])
    uvn = nb.n('ShaderNodeUVMap', uv_map='TexUV')
    mp = nb.n('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (scale, scale, scale)
    mp.inputs['Rotation'].default_value = (0, 0, rot)
    nb.l(uvn.outputs['UV'], mp.inputs['Vector'])
    vec = mp.outputs[0]
    maps = acg(tex_id)

    def img(key, color=True):
        n = nb.n('ShaderNodeTexImage')
        n.image = load_img(maps[key], color)
        nb.l(vec, n.inputs['Vector'])
        return n

    col = img('color').outputs['Color']
    if sat != 1.0 or val != 1.0:
        hsv = nb.n('ShaderNodeHueSaturation')
        hsv.inputs['Saturation'].default_value = sat
        hsv.inputs['Value'].default_value = val
        nb.l(col, hsv.inputs['Color'])
        col = hsv.outputs['Color']
    if tint is not None:
        col = nb.mix(tint_amt, col, tuple(tint), 'MULTIPLY')
    if extra_color is not None:
        col = extra_color(nb, col, vec)
    rough = img('rough', False).outputs['Color'] if 'rough' in maps else None
    rough_v = nb.math('MULTIPLY', rough if rough is not None else 0.6, rough_mul)
    rough_v = nb.math('ADD', rough_v, rough_add)
    metal_v = None
    if metal is not None:
        if metal == 'map' and 'metal' in maps:
            metal_v = img('metal', False).outputs['Color']
        else:
            metal_v = nb.math('ADD', float(metal), 0.0)
    geo = nb.n('ShaderNodeNewGeometry')
    obj_co = nb.n('ShaderNodeTexCoord').outputs['Object']
    if wear:
        bev = nb.n('ShaderNodeBevel', samples=8)
        bev.inputs['Radius'].default_value = wear.get('radius', 0.004)
        dp = nb.n('ShaderNodeVectorMath', operation='DOT_PRODUCT')
        nb.l(bev.outputs['Normal'], dp.inputs[0])
        nb.l(geo.outputs['Normal'], dp.inputs[1])
        edge = nb.math('SUBTRACT', 1.0, dp.outputs['Value'])
        edge = nb.math('MULTIPLY', edge, wear.get('gain', 18.0), clamp=True)
        brk = nb.noise(obj_co, wear.get('noise', 14.0), 6.0, 0.62)
        brk = nb.ramp(brk, 0.38, 0.62)
        wm = nb.math('MULTIPLY', edge, brk)
        wm = nb.math('MULTIPLY', wm, wear.get('amount', 1.0), clamp=True)
        col = nb.mix(wm, col, tuple(wear['color']))
        rough_v = nb.mix(wm, rough_v, (wear.get('rough', 0.3),) * 3)
        if metal_v is not None and 'metal' in wear:
            metal_v = nb.mix(wm, metal_v, (wear['metal'],) * 3)
    if grime:
        ao = nb.n('ShaderNodeAmbientOcclusion', samples=16, only_local=grime.get('local', True))
        ao.inputs['Distance'].default_value = grime.get('dist', 0.05)
        g = nb.math('SUBTRACT', 1.0, ao.outputs['AO'])
        g = nb.math('MULTIPLY', g, grime.get('gain', 1.6), clamp=True)
        gn = nb.ramp(nb.noise(obj_co, grime.get('noise', 5.0), 5.0, 0.6), 0.3, 0.75)
        g = nb.math('MULTIPLY', g, nb.math('ADD', nb.math('MULTIPLY', gn, 0.6), 0.4))
        g = nb.math('MULTIPLY', g, grime.get('amount', 0.7), clamp=True)
        col = nb.mix(g, col, tuple(grime['color']))
        rough_v = nb.math('ADD', rough_v, nb.math('MULTIPLY', g, grime.get('rough', 0.12)))
    if dust:
        sep = nb.n('ShaderNodeSeparateXYZ')
        nb.l(geo.outputs['Normal'], sep.inputs[0])
        up = nb.ramp(sep.outputs['Z'], 0.55, 0.95)
        dn = nb.ramp(nb.noise(obj_co, dust.get('noise', 9.0), 6.0, 0.6), 0.35, 0.7)
        dm = nb.math('MULTIPLY', nb.math('MULTIPLY', up, dn), dust.get('amount', 0.25), clamp=True)
        col = nb.mix(dm, col, tuple(dust['color']))
        rough_v = nb.mix(dm, rough_v, (0.9, 0.9, 0.9))
    # normal
    if 'normal' in maps and nstr > 0:
        nmap = nb.n('ShaderNodeNormalMap', uv_map='TexUV')
        nmap.inputs['Strength'].default_value = nstr
        nb.l(img('normal', False).outputs['Color'], nmap.inputs['Color'])
        nb.l(nmap.outputs['Normal'], bs.inputs['Normal'])
    rr = nb.n('NodeReroute', name='OUT_COLOR', label='OUT_COLOR')
    nb.l(col, rr.inputs[0])
    nb.l(rr.outputs[0], bs.inputs['Base Color'])
    rg = nb.n('NodeReroute', name='OUT_ROUGH', label='OUT_ROUGH')
    nb.l(rough_v, rg.inputs[0])
    nb.l(rg.outputs[0], bs.inputs['Roughness'])
    if metal_v is not None:
        rm = nb.n('NodeReroute', name='OUT_METAL', label='OUT_METAL')
        nb.l(metal_v, rm.inputs[0])
        nb.l(rm.outputs[0], bs.inputs['Metallic'])
    else:
        bs.inputs['Metallic'].default_value = 0.0
    if emission is not None:
        bs.inputs['Emission Color'].default_value = (*emission[:3], 1)
        bs.inputs['Emission Strength'].default_value = emission[3] if len(emission) > 3 else 1.0
    return m


def flat_mat(name, color=(0.8, 0.8, 0.8), rough=0.5, metal=0.0, emission=None, alpha=None):
    """For ENGINE-DRIVEN surfaces only (the engine swaps these materials); never a final look."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bs = m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*color, 1)
    bs.inputs['Roughness'].default_value = rough
    bs.inputs['Metallic'].default_value = metal
    if emission:
        bs.inputs['Emission Color'].default_value = (*emission[:3], 1)
        bs.inputs['Emission Strength'].default_value = emission[3]
    if alpha is not None:
        bs.inputs['Alpha'].default_value = alpha
    return m


# --------------------------------------------------------------------------------------- UVs
def uv_tex(o, cube=1.0):
    """World-scaled box projection into 'TexUV' (1 UV unit = `cube` metres)."""
    me = o.data
    if 'TexUV' not in me.uv_layers:
        me.uv_layers.new(name='TexUV')
    me.uv_layers.active = me.uv_layers['TexUV']
    select_only(o)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.cube_project(cube_size=cube, correct_aspect=False, clip_to_bounds=False, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode='OBJECT')


def uv_tex_axis(o, axis='X', scale=1.0):
    """Planar-cylindrical projection that keeps grain along one object axis (for wood members):
    U runs along `axis`, V around it. Written directly (no operator)."""
    me = o.data
    if 'TexUV' not in me.uv_layers:
        me.uv_layers.new(name='TexUV')
    uvl = me.uv_layers['TexUV']
    ai = 'XYZ'.index(axis)
    for poly in me.polygons:
        n = poly.normal
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            along = co[ai]
            others = [co[k] for k in range(3) if k != ai]
            nn = [abs(n[k]) for k in range(3) if k != ai]
            across = others[1] if nn[0] > nn[1] else others[0]
            uvl.data[li].uv = (along / scale, across / scale)


def uv_bake(o, margin=0.004, angle=62):
    me = o.data
    if 'BakeUV' not in me.uv_layers:
        me.uv_layers.new(name='BakeUV')
    me.uv_layers.active = me.uv_layers['BakeUV']
    select_only(o)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=margin, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    try:
        bpy.ops.uv.pack_islands(margin=margin, rotate=True)
    except Exception as e:
        print('[clib] pack_islands:', e)
    bpy.ops.object.mode_set(mode='OBJECT')


def uv_unit(o, name='UVMap'):
    """Keep/rename the first UV map as-is (for engine-driven surfaces with authored 0..1 UVs)."""
    me = o.data
    if len(me.uv_layers) == 0:
        me.uv_layers.new(name=name)
    me.uv_layers[0].name = name


# ------------------------------------------------------------------------------------- bake
def _emit_route(mat, sock_name, default):
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    prev = out.inputs['Surface'].links[0].from_socket if out.inputs['Surface'].links else None
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Strength'].default_value = 1.0
    src = nt.nodes.get(sock_name)
    if src is not None:
        nt.links.new(src.outputs[0], em.inputs['Color'])
    else:
        em.inputs['Color'].default_value = (default, default, default, 1)
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    return em, prev, out


def bake(o, key, size=2048, maps=('color', 'rough', 'metal', 'normal', 'ao'), samples=32, ao_dist=0.08):
    """Bake the layered materials of `o` down to images on BakeUV. Returns {map: image}."""
    sc = bpy.context.scene
    sc.cycles.samples = samples
    me = o.data
    me.uv_layers.active = me.uv_layers['BakeUV']
    for i, uvl in enumerate(me.uv_layers):
        uvl.active_render = (uvl.name == 'BakeUV')
    select_only(o)
    imgs = {}
    mats = [s.material for s in o.material_slots if s.material]
    for k in maps:
        im = bpy.data.images.new(f'{key}_{k}', size, size, alpha=False, float_buffer=(k == 'normal'))
        if k != 'color':
            im.colorspace_settings.name = 'Non-Color'
        tnodes = []
        for mt in mats:
            tn = mt.node_tree.nodes.new('ShaderNodeTexImage')
            tn.image = im
            mt.node_tree.nodes.active = tn
            tnodes.append((mt, tn))
        routed = []
        if k in ('color', 'rough', 'metal'):
            for mt in mats:
                sock = {'color': 'OUT_COLOR', 'rough': 'OUT_ROUGH', 'metal': 'OUT_METAL'}[k]
                default = {'color': 0.5, 'rough': 0.6, 'metal': 0.0}[k]
                routed.append((mt, _emit_route(mt, sock, default)))
            bpy.ops.object.bake(type='EMIT', margin=12, use_clear=True)
        elif k == 'normal':
            bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT', margin=12, use_clear=True)
        elif k == 'ao':
            sc.world = sc.world or bpy.data.worlds.new('w')
            sc.world.light_settings.distance = ao_dist
            bpy.ops.object.bake(type='AO', margin=12, use_clear=True)
        for mt, (em, prev, out) in routed:
            if prev is not None:
                mt.node_tree.links.new(prev, out.inputs['Surface'])
            mt.node_tree.nodes.remove(em)
        for mt, tn in tnodes:
            mt.node_tree.nodes.remove(tn)
        ext = 'png' if k == 'normal' else 'jpg'
        path = os.path.join(BAKED, f'{key}_{k}.{ext}')
        im.filepath_raw = path
        im.file_format = 'PNG' if ext == 'png' else 'JPEG'
        if ext == 'png':
            # 8-bit normal PNG
            sc.render.image_settings.color_depth = '8'
        im.save()
        if ext == 'png':
            # re-encode the tangent normal as a high-quality JPEG (a 2K noisy PNG is ~17 MB)
            try:
                from PIL import Image
                Image.open(path).convert('RGB').save(path[:-4] + '.jpg', quality=95, subsampling=0)
            except Exception as e:
                print('[clib] normal jpg re-encode failed:', e)
        imgs[k] = im
        print(f'[clib] baked {key}_{k} {size}px', flush=True)
    return imgs


def export_material(key, imgs, name=None):
    """glTF-ready material from baked maps: baseColor, ORM (R=ao G=rough B=metal), normal."""
    size = imgs['color'].size[0]
    import numpy as np
    def arr(im):
        a = np.empty(size * size * 4, np.float32)
        im.pixels.foreach_get(a)
        return a.reshape(-1, 4)
    ao = arr(imgs['ao'])[:, 0] if 'ao' in imgs else np.ones(size * size, np.float32)
    ro = arr(imgs['rough'])[:, 0] if 'rough' in imgs else np.full(size * size, 0.6, np.float32)
    me_ = arr(imgs['metal'])[:, 0] if 'metal' in imgs else np.zeros(size * size, np.float32)
    orm = np.stack([ao, ro, me_, np.ones_like(ao)], 1).ravel()
    om = bpy.data.images.new(f'{key}_orm', size, size, alpha=False)
    om.colorspace_settings.name = 'Non-Color'
    om.pixels.foreach_set(orm)
    om.filepath_raw = os.path.join(BAKED, f'{key}_orm.jpg')
    om.file_format = 'JPEG'
    om.save()
    # reload from disk so the exporter keeps JPEG/PNG as saved
    base = load_img(os.path.join(BAKED, f'{key}_color.jpg'))
    ormi = load_img(os.path.join(BAKED, f'{key}_orm.jpg'), False)
    npath = os.path.join(BAKED, f'{key}_normal.jpg')
    if not os.path.exists(npath):
        npath = os.path.join(BAKED, f'{key}_normal.png')
    nrm = load_img(npath, False)
    m = bpy.data.materials.new(name or f'{key}_baked')
    m.use_nodes = True
    nb = NB(m)
    bs = nb.N.get('Principled BSDF')
    uvn = nb.n('ShaderNodeUVMap', uv_map='BakeUV')
    tb = nb.n('ShaderNodeTexImage'); tb.image = base; nb.l(uvn.outputs[0], tb.inputs[0])
    nb.l(tb.outputs['Color'], bs.inputs['Base Color'])
    to = nb.n('ShaderNodeTexImage'); to.image = ormi; nb.l(uvn.outputs[0], to.inputs[0])
    sep = nb.n('ShaderNodeSeparateColor'); nb.l(to.outputs['Color'], sep.inputs[0])
    nb.l(sep.outputs['Green'], bs.inputs['Roughness'])
    nb.l(sep.outputs['Blue'], bs.inputs['Metallic'])
    tn = nb.n('ShaderNodeTexImage'); tn.image = nrm; nb.l(uvn.outputs[0], tn.inputs[0])
    nm = nb.n('ShaderNodeNormalMap', uv_map='BakeUV'); nb.l(tn.outputs['Color'], nm.inputs['Color'])
    nb.l(nm.outputs['Normal'], bs.inputs['Normal'])
    grp = bpy.data.node_groups.get('glTF Material Output')
    if grp is None:
        grp = bpy.data.node_groups.new('glTF Material Output', 'ShaderNodeTree')
        grp.interface.new_socket(name='Occlusion', in_out='INPUT', socket_type='NodeSocketFloat')
    gn = nb.n('ShaderNodeGroup'); gn.node_tree = grp
    nb.l(sep.outputs['Red'], gn.inputs['Occlusion'])
    return m


def bake_and_swap(o, key, size=2048, samples=32, ao_dist=0.08):
    """Full layered->baked pass for one object: BakeUV must exist. Replaces all materials."""
    imgs = bake(o, key, size=size, samples=samples, ao_dist=ao_dist)
    m = export_material(key, imgs)
    o.data.materials.clear()
    o.data.materials.append(m)
    for p in o.data.polygons:
        p.material_index = 0
    if 'TexUV' in o.data.uv_layers:
        o.data.uv_layers.remove(o.data.uv_layers['TexUV'])
    o.data.uv_layers['BakeUV'].active = True
    o.data.uv_layers['BakeUV'].active_render = True
    return m


# ------------------------------------------------------------------------------------ export
def export_glb(objs, filename):
    path = os.path.join(GLB, filename)
    select_only(objs)
    # include children
    for o in objs:
        for c in o.children_recursive:
            c.select_set(True)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_apply=True,
                              export_yup=True, export_image_format='AUTO', export_extras=True,
                              export_attributes=True)
    print(f'[clib] exported {path} ({os.path.getsize(path) / 1e6:.1f} MB)', flush=True)
    return path


# ----------------------------------------------------------------------------------- preview
def preview(objs, filename, target=None, dist=None, height=0.35, size=512, samples=48, angles=4,
            key_energy=None, world=0.18, lens=50):
    """4-angle Cycles contact sheet of the (baked) asset for the look-loop."""
    sc = bpy.context.scene
    sc.cycles.samples = samples
    try:
        sc.cycles.use_denoising = True
    except Exception:
        pass
    sc.render.resolution_x = size
    sc.render.resolution_y = size
    sc.render.film_transparent = False
    objs = objs if isinstance(objs, (list, tuple)) else [objs]
    # bounds
    mn = Vector((1e9, 1e9, 1e9)); mx = Vector((-1e9, -1e9, -1e9))
    for o in objs:
        for c in [o] + list(o.children_recursive):
            if c.type != 'MESH':
                continue
            for v in c.bound_box:
                w = c.matrix_world @ Vector(v)
                mn = Vector(map(min, mn, w)); mx = Vector(map(max, mx, w))
    ctr = (mn + mx) / 2 if target is None else Vector(target)
    rad = (mx - mn).length / 2
    dist = dist or rad * 3.2
    w = sc.world or bpy.data.worlds.new('w')
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.55, 0.6, 0.68, 1)
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = world
    lights = []
    ke = key_energy or 40 * rad * rad + 2
    for loc, en, col in (((dist, -dist, dist * 1.2), ke, (1, 0.93, 0.85)),
                         ((-dist, -dist * 0.6, dist * 0.5), ke * 0.35, (0.8, 0.88, 1.0)),
                         ((0, dist, dist * 0.9), ke * 0.6, (1, 1, 1))):
        ld = bpy.data.lights.new('pv', 'AREA')
        ld.energy = en * 20
        ld.size = rad * 2
        ld.color = col
        lo = bpy.data.objects.new('pv', ld)
        link(lo)
        lo.location = ctr + Vector(loc)
        lo.rotation_euler = (ctr - lo.location).to_track_quat('-Z', 'Y').to_euler()
        lights.append(lo)
    cd = bpy.data.cameras.new('pvcam')
    cd.lens = lens
    cam = bpy.data.objects.new('pvcam', cd)
    link(cam)
    sc.camera = cam
    shots = []
    for i in range(angles):
        a = math.radians(-30 + i * 90)
        pos = ctr + Vector((math.sin(a) * dist, -math.cos(a) * dist, rad * 2.2 * height + rad * 0.2))
        cam.location = pos
        cam.rotation_euler = (ctr - pos).to_track_quat('-Z', 'Y').to_euler()
        p = os.path.join(PREV, f'_{filename}_{i}.png')
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        shots.append(p)
    for lo in lights:
        bpy.data.objects.remove(lo)
    bpy.data.objects.remove(cam)
    try:
        from PIL import Image
        ims = [Image.open(p) for p in shots]
        sheet = Image.new('RGB', (size * 2, size * 2))
        for i, im in enumerate(ims):
            sheet.paste(im.convert('RGB'), ((i % 2) * size, (i // 2) * size))
        out = os.path.join(PREV, f'{filename}.png')
        sheet.save(out)
        for p in shots:
            os.remove(p)
        print(f'[clib] preview {out}', flush=True)
        return out
    except Exception as e:
        print('[clib] preview sheet failed:', e)
        return shots


def closeup(filename, cam_pos, target, lens=50, size=768, samples=64):
    sc = bpy.context.scene
    sc.cycles.samples = samples
    sc.render.resolution_x = size
    sc.render.resolution_y = size
    cd = bpy.data.cameras.new('cu')
    cd.lens = lens
    cam = bpy.data.objects.new('cu', cd)
    link(cam)
    cam.location = Vector(cam_pos)
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.camera = cam
    sc.render.filepath = os.path.join(PREV, f'{filename}.png')
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam)
    return sc.render.filepath

"""TEST FIXTURE ONLY: a little grass so the meadow probe can judge the ground BETWEEN blades.

Grass is the vegetation family's system (createFlora -> create_flora); this is not a port of it and
nothing outside tests/ may use it. It scatters tufts of blade cards cut from our own meadow blade
atlas (eidoverse/assets/grass/blades_meadow_*), with a Geometry Nodes Distribute + Instance on the
terrain, kept out of the clearing.
"""
import math
import random

import bpy
import numpy as np

from _fixture import WORKTREE

GRASS = WORKTREE / 'eidoverse' / 'assets' / 'grass'


def _blade_material():
    mat = bpy.data.materials.new('test_grass_blade')
    try:
        mat.use_nodes = True
    except Exception:
        pass
    mat.surface_render_method = 'DITHERED'
    mat.use_backface_culling = False
    nt = mat.node_tree
    bsdf = [n for n in nt.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled'][0]
    out = [n for n in nt.nodes if n.bl_idname == 'ShaderNodeOutputMaterial'][0]

    def img(name, cs):
        im = bpy.data.images.load(str(GRASS / name), check_existing=True)
        im.colorspace_settings.name = cs
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = im
        return t
    alb = img('blades_meadow_albedo.png', 'sRGB')
    nor = img('blades_meadow_normal.png', 'Non-Color')
    rou = img('blades_meadow_roughness.png', 'Non-Color')
    tra = img('blades_meadow_translucency.png', 'sRGB')
    # per-tuft colour drift (Object Info's Random is per instance in EEVEE): some yellowing, some dark
    oi = nt.nodes.new('ShaderNodeObjectInfo')
    hs = nt.nodes.new('ShaderNodeHueSaturation')
    for sock, lo, hi in (('Hue', 0.47, 0.53), ('Saturation', 0.75, 1.1), ('Value', 0.62, 1.08)):
        mr = nt.nodes.new('ShaderNodeMapRange')
        mr.inputs['To Min'].default_value = lo
        mr.inputs['To Max'].default_value = hi
        nt.links.new(oi.outputs['Random'], mr.inputs['Value'])
        nt.links.new(mr.outputs['Result'], hs.inputs[sock])
    nt.links.new(alb.outputs['Color'], hs.inputs['Color'])
    nt.links.new(hs.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(alb.outputs['Alpha'], bsdf.inputs['Alpha'])
    nt.links.new(rou.outputs['Color'], bsdf.inputs['Roughness'])
    nm = nt.nodes.new('ShaderNodeNormalMap')
    nt.links.new(nor.outputs['Color'], nm.inputs['Color'])
    nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    tl = nt.nodes.new('ShaderNodeBsdfTranslucent')
    nt.links.new(tra.outputs['Color'], tl.inputs['Color'])
    mix = nt.nodes.new('ShaderNodeMixShader')
    mix.inputs['Fac'].default_value = 0.3
    nt.links.new(bsdf.outputs['BSDF'], mix.inputs[1])
    nt.links.new(tl.outputs['BSDF'], mix.inputs[2])
    # the translucent half keeps the cut-out: blend it with transparency by the same alpha
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix2 = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(alb.outputs['Alpha'], mix2.inputs['Fac'])
    nt.links.new(tr.outputs['BSDF'], mix2.inputs[1])
    nt.links.new(mix.outputs['Shader'], mix2.inputs[2])
    nt.links.new(mix2.outputs['Shader'], out.inputs['Surface'])
    return mat


def _tuft_mesh(name, rng, mat, blades=14, seg=4):
    co, faces, uvs = [], [], []
    for b in range(blades):
        k = rng.randrange(8)
        h = rng.uniform(0.12, 0.55) * (1.0 if rng.random() > 0.2 else 0.5)
        w = h / 8.0 * 1.15
        r = rng.uniform(0.0, 0.09)
        a = rng.uniform(0, 2 * math.pi)
        yaw = rng.uniform(0, 2 * math.pi)
        lean = rng.uniform(0.15, 1.0)
        bx, by = r * math.cos(a), r * math.sin(a)
        dx, dy = math.cos(yaw), math.sin(yaw)        # card's width axis
        lx, ly = -dy, dx                              # the way it leans
        base = len(co)
        for s in range(seg + 1):
            t = s / seg
            off = math.sin(lean) * h * t * t          # bends more toward the tip
            z = h * t * math.cos(lean * t)
            cx, cy = bx + lx * off, by + ly * off
            co += [(cx - dx * w / 2, cy - dy * w / 2, z), (cx + dx * w / 2, cy + dy * w / 2, z)]
            uvs.append(((k + 0.0) / 8, t))
            uvs.append(((k + 1.0) / 8, t))
        for s in range(seg):
            i = base + 2 * s
            faces.append((i, i + 1, i + 3, i + 2))
    me = bpy.data.meshes.new(name)
    me.from_pydata(co, [], faces)
    uvl = me.uv_layers.new(name='UVMap')
    loop_uv = [uvs[li.vertex_index] for li in me.loops]
    uvl.uv.foreach_set('vector', np.asarray(loop_uv, dtype=np.float32).ravel())
    me.materials.append(mat)
    me.shade_smooth()
    return me


def add_test_grass(terrain, clear_radius=8.0, outer_radius=40.0, density=36.0, center=(0.0, 0.0), seed=3):
    """Scatter blade tufts over `terrain` between clear_radius+1 m and outer_radius around center."""
    rng = random.Random(seed)
    mat = _blade_material()
    coll = bpy.data.collections.new('test_grass_tufts')
    for v in range(6):
        me = _tuft_mesh('test_tuft_%d' % v, rng, mat)
        o = bpy.data.objects.new('test_tuft_%d' % v, me)
        coll.objects.link(o)

    ng = bpy.data.node_groups.new('test_grass_scatter', 'GeometryNodeTree')
    ng.interface.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, Lk = ng.nodes, ng.links
    gout = N.new('NodeGroupOutput')
    oi = N.new('GeometryNodeObjectInfo')
    oi.inputs['Object'].default_value = terrain
    oi.transform_space = 'RELATIVE'
    dist = N.new('GeometryNodeDistributePointsOnFaces')
    dist.distribute_method = 'RANDOM'
    dist.inputs['Seed'].default_value = seed
    Lk.new(oi.outputs['Geometry'], dist.inputs['Mesh'])
    pos = N.new('GeometryNodeInputPosition')
    sep = N.new('ShaderNodeSeparateXYZ')
    Lk.new(pos.outputs['Position'], sep.inputs[0])
    comb = N.new('ShaderNodeCombineXYZ')
    sub_x = N.new('ShaderNodeMath'); sub_x.operation = 'SUBTRACT'
    sub_y = N.new('ShaderNodeMath'); sub_y.operation = 'SUBTRACT'
    Lk.new(sep.outputs['X'], sub_x.inputs[0]); sub_x.inputs[1].default_value = center[0]
    Lk.new(sep.outputs['Y'], sub_y.inputs[0]); sub_y.inputs[1].default_value = center[1]
    Lk.new(sub_x.outputs[0], comb.inputs['X']); Lk.new(sub_y.outputs[0], comb.inputs['Y'])
    ln = N.new('ShaderNodeVectorMath'); ln.operation = 'LENGTH'
    Lk.new(comb.outputs[0], ln.inputs[0])

    def mrange(src, a, b, c=0.0, d=1.0, smooth=True):
        m = N.new('ShaderNodeMapRange')
        if smooth:
            m.interpolation_type = 'SMOOTHSTEP'
        m.inputs['From Min'].default_value = a
        m.inputs['From Max'].default_value = b
        m.inputs['To Min'].default_value = c
        m.inputs['To Max'].default_value = d
        Lk.new(src, m.inputs['Value'])
        return m.outputs['Result']
    inner = mrange(ln.outputs['Value'], clear_radius + 0.6, clear_radius + 3.5)
    outer = mrange(ln.outputs['Value'], outer_radius, outer_radius - 6.0)
    nz = N.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 0.35
    nz.inputs['Detail'].default_value = 3.0
    Lk.new(pos.outputs['Position'], nz.inputs['Vector'])
    patch = mrange(nz.outputs['Fac'], 0.35, 0.62, 0.25, 1.0)
    m1 = N.new('ShaderNodeMath'); m1.operation = 'MULTIPLY'
    m2 = N.new('ShaderNodeMath'); m2.operation = 'MULTIPLY'
    m3 = N.new('ShaderNodeMath'); m3.operation = 'MULTIPLY'
    Lk.new(inner, m1.inputs[0]); Lk.new(outer, m1.inputs[1])
    Lk.new(m1.outputs[0], m2.inputs[0]); Lk.new(patch, m2.inputs[1])
    Lk.new(m2.outputs[0], m3.inputs[0]); m3.inputs[1].default_value = density
    Lk.new(m3.outputs[0], dist.inputs['Density'])

    ci = N.new('GeometryNodeCollectionInfo')
    ci.inputs['Collection'].default_value = coll
    ci.inputs['Separate Children'].default_value = True
    ci.inputs['Reset Children'].default_value = True
    iop = N.new('GeometryNodeInstanceOnPoints')
    iop.inputs['Pick Instance'].default_value = True
    Lk.new(dist.outputs['Points'], iop.inputs['Points'])
    Lk.new(ci.outputs[0], iop.inputs['Instance'])
    def rnd(dtype, lo, hi, s):
        n = N.new('FunctionNodeRandomValue')
        n.data_type = dtype
        st = 'VALUE' if dtype == 'FLOAT' else 'INT'
        pick_in = lambda nm: next(x for x in n.inputs if x.name == nm and x.type == st)
        pick_in('Min').default_value = lo
        pick_in('Max').default_value = hi
        n.inputs['Seed'].default_value = s
        return next(x for x in n.outputs if x.type == st)
    rot = N.new('ShaderNodeCombineXYZ')
    Lk.new(rnd('FLOAT', 0.0, 2 * math.pi, seed + 1), rot.inputs['Z'])
    Lk.new(rot.outputs[0], iop.inputs['Rotation'])
    Lk.new(rnd('FLOAT', 0.7, 1.35, seed + 2), iop.inputs['Scale'])
    Lk.new(rnd('INT', 0, 5, seed + 3), iop.inputs['Instance Index'])
    Lk.new(iop.outputs['Instances'], gout.inputs['Geometry'])

    holder = bpy.data.objects.new('test_grass', bpy.data.meshes.new('test_grass_holder'))
    bpy.context.scene.collection.objects.link(holder)
    mod = holder.modifiers.new('test_grass', 'NODES')
    mod.node_group = ng
    holder['no_support_check'] = True            # the audits: scattered vegetation, not a placed prop
    holder['no_clipping_check'] = True
    return holder

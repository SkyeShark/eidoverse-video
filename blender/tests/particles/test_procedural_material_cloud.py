"""Models whose look comes from procedural materials, each beside its particle cloud: a marble head (Noise -> Color
Ramp on Object coordinates), a terrazzo ball (Voronoi cell colours through a Mapping) and a wood log (Wave rings ->
Color Ramp, a group node around it). The cloud's colours are the material's own, evaluated by Geometry Nodes at
every sampled point (particle_targets.graph_colors), so the cloud looks like the model; before, it was flat grey.

    out/<out>/procedural_cloud_f001.png   the three models (left of each pair) and their clouds (right)

Checks: each cloud's colours vary the way its material does (not one flat colour), and a cloud point takes the
colour the material shows at the nearest point of the model's surface (a KD-tree over a dense colour sampling).

    bash run_blender.sh blender/tests/particles/test_procedural_material_cloud.py [-- out=verify] [no-render]
    (a GPU job: 4 GB VRAM, 8 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)
"""

import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from eidoblend.fx import particle_morph as PM  # noqa: E402
from eidoblend.fx import particle_targets as PT  # noqa: E402

RENDER = 'no-render' not in S.argv()
N = 70000


def material(name, build, roughness=0.4):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes['Principled BSDF']
    bsdf.inputs['Roughness'].default_value = roughness
    nt.links.new(build(nt), bsdf.inputs['Base Color'])
    return m


def ramp(nt, fac, stops):
    r = nt.nodes.new('ShaderNodeValToRGB')
    els = r.color_ramp.elements
    els[0].position, els[0].color = stops[0][0], (*stops[0][1], 1.0)
    els[1].position, els[1].color = stops[-1][0], (*stops[-1][1], 1.0)
    for pos, c in stops[1:-1]:
        els.new(pos).color = (*c, 1.0)
    nt.links.new(fac, r.inputs['Fac'])
    return r.outputs['Color']


def marble(nt):
    tc = nt.nodes.new('ShaderNodeTexCoord')
    nz = nt.nodes.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 2.2
    nz.inputs['Detail'].default_value = 9.0
    nz.inputs['Distortion'].default_value = 1.6
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
    return ramp(nt, nz.outputs['Fac'], [(0.30, (0.015, 0.06, 0.04)), (0.47, (0.30, 0.42, 0.36)),
                                        (0.52, (0.92, 0.93, 0.90)), (0.70, (0.80, 0.82, 0.78))])


def terrazzo(nt):
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (6.0, 6.0, 6.0)
    nt.links.new(tc.outputs['Generated'], mp.inputs['Vector'])
    vo = nt.nodes.new('ShaderNodeTexVoronoi')
    nt.links.new(mp.outputs['Vector'], vo.inputs['Vector'])
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type, mix.blend_type = 'RGBA', 'MIX'
    ins = {s.identifier: s for s in mix.inputs}
    ins['Factor_Float'].default_value = 0.55
    ins['A_Color'].default_value = (0.75, 0.70, 0.62, 1.0)                 # the cement between the chips
    nt.links.new(vo.outputs['Color'], ins['B_Color'])
    return {s.identifier: s for s in mix.outputs}['Result_Color']


def wood(nt):
    grp = bpy.data.node_groups.new('wood_rings', 'ShaderNodeTree')
    grp.interface.new_socket('Vector', in_out='INPUT', socket_type='NodeSocketVector')
    grp.interface.new_socket('Color', in_out='OUTPUT', socket_type='NodeSocketColor')
    gi, go = grp.nodes.new('NodeGroupInput'), grp.nodes.new('NodeGroupOutput')
    wv = grp.nodes.new('ShaderNodeTexWave')
    wv.wave_type, wv.rings_direction = 'RINGS', 'Z'
    wv.inputs['Scale'].default_value = 3.0
    wv.inputs['Distortion'].default_value = 4.0
    wv.inputs['Detail'].default_value = 3.0
    grp.links.new(gi.outputs['Vector'], wv.inputs['Vector'])
    grp.links.new(ramp(grp, wv.outputs['Fac'], [(0.0, (0.10, 0.045, 0.015)), (0.55, (0.36, 0.17, 0.06)),
                                                 (1.0, (0.62, 0.36, 0.15))]), go.inputs['Color'])
    g = nt.nodes.new('ShaderNodeGroup')
    g.node_tree = grp
    nt.links.new(nt.nodes.new('ShaderNodeTexCoord').outputs['Object'], g.inputs['Vector'])
    return g.outputs['Color']


def main():
    sc = S.clean_scene(24, 1, 10)
    S.probe_render(sc, (960, 540), 16)
    S.world(sc, (0.02, 0.022, 0.03))
    S.sun('key', (-1.5, -2.5, 3.0), (1.0, 0.97, 0.92), 3.5)
    S.sun('fill', (2.0, -1.0, 1.0), (0.7, 0.8, 1.0), 0.8)
    S.floor(40.0, (0.05, 0.05, 0.055), 0.6)
    bpy.ops.mesh.primitive_monkey_add(size=1.3, location=(-5.0, 0.0, 1.0))
    head = bpy.context.object
    head.modifiers.new('sub', 'SUBSURF').levels = 2
    head.rotation_euler = (math.radians(-10), 0.0, 0.0)
    head.data.materials.append(material('marble', marble, 0.25))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.7, segments=64, ring_count=32, location=(-1.25, 0.0, 0.85))
    ball = bpy.context.object
    bpy.ops.object.shade_smooth()
    ball.data.materials.append(material('terrazzo', terrazzo, 0.35))
    bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=1.4, vertices=64, location=(2.35, 0.0, 0.8))
    log_ = bpy.context.object
    log_.rotation_euler = (0.0, math.radians(90), 0.0)
    log_.data.materials.append(material('wood', wood, 0.55))
    # each model with its cloud beside it, far enough apart not to overlap
    for i, (o, label, dx) in enumerate(((head, 'marble head', 1.9), (ball, 'terrazzo ball', 1.7),
                                        (log_, 'wood log', 1.8))):
        t = PT.from_object(o, N, seed=40 + i)
        S.check(f'{label}: the cloud\'s colours vary as its material does (not one flat colour)',
                t.colors is not None and float(t.colors.std(0).max()) > 0.05, f'sd {t.colors.std(0).round(3)}')
        dense = PT.from_object(o, 150000, seed=60 + i)
        from mathutils.kdtree import KDTree
        kd = KDTree(len(dense))
        for k, p in enumerate(dense.points):
            kd.insert(p, k)
        kd.balance()
        idx = np.array([kd.find(p)[1] for p in t.points[:4000]])
        err = float(np.median(np.abs(t.colors[:4000] - dense.colors[idx]).max(1)))
        S.check(f'{label}: a cloud point is the colour of the surface beside it (median over 4000)', err < 0.03,
                f'median max |diff| {err:.4f}')
        m = PM.make_particle_morph(count=N, targets=[t + (dx, 0.0, 0.0), t + (dx, 0.0, 0.0)], blending='normal',
                                   size=0.02, name=f'cloud_{i}', seed=50 + i)
        m.morph(0, 1, 0.0, 0.0)
    S.camera('cam', (-0.95, -12.5, 2.4), (-0.95, 0.0, 0.85), 38.0)
    if RENDER:
        S.render_still(os.path.join(S.OUT, 'procedural_cloud_f001.png'), 1)
    ok = S.summary('procedural cloud')
    sys.exit(0 if ok else 1)


try:
    main()
except SystemExit:
    raise
except Exception:
    import traceback
    traceback.print_exc()
    print('FAIL exception')
    sys.exit(1)

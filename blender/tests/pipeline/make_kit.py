"""make_kit.py <out.glb>: a three-part kit laid out in a row, as fetched kits come (test T10). The crate sits 0.5 m
up in the row and the post is off-centre, so load_kit's re-basing has something to do.

    bash run_blender.sh blender/tests/pipeline/make_kit.py blender/tests/pipeline/out/kit_parts.glb
"""
import os
import sys

import bpy

out = os.path.abspath(sys.argv[sys.argv.index('--') + 1])
bpy.ops.wm.read_homefile(use_empty=True)


def mat(name, rgb, rough):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgb, 1)
    b.inputs['Roughness'].default_value = rough
    return m


bpy.ops.mesh.primitive_cube_add(size=0.4, location=(0, 0, 0.7))
crate = bpy.context.object
crate.name = 'crate_small'
crate.data.materials.append(mat('crate_wood', (0.42, 0.27, 0.13), 0.7))
bpy.ops.mesh.primitive_torus_add(major_radius=0.25, minor_radius=0.06, location=(1.5, 0.3, 0.3),
                                 rotation=(1.5708, 0, 0))
pipe = bpy.context.object
pipe.name = 'pipe_elbow_01'
pipe.data.materials.append(mat('pipe_steel', (0.6, 0.6, 0.62), 0.35))
bpy.ops.mesh.primitive_cylinder_add(radius=0.06, depth=1.2, location=(3.0, -0.2, 0.6))
post = bpy.context.object
post.name = 'post_tall'
post.data.materials.append(mat('post_paint', (0.15, 0.32, 0.22), 0.5))
os.makedirs(os.path.dirname(out), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', use_selection=False)
print(f'[make_kit] wrote {out}', flush=True)

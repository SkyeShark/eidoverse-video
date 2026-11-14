"""Rhombic dodecahedron voxels in EEVEE: a filled box (the engine's spaced cells), a filled sphere closed into the true
tiling (fill=2), Suzanne voxelized, and the engine's reveal recipe (cells appearing inside a growing sphere) at two
frames of the scene time.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sdf/test_rhombic_render.py
    (a GPU job: 4 GB VRAM, 8 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

out/rd_f0012.png, out/rd_f0036.png. PASS lines: instance counts, the reveal hides and shows the right cells.
"""

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

import bpy  # noqa: E402

from eidoblend.sdf import rhombic_dodecahedron as RD  # noqa: E402


def mat(name, color, metal=0.0, rough=0.35):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1.0)
    b.inputs['Metallic'].default_value = metal
    b.inputs['Roughness'].default_value = rough
    return m


sc = C.stage(960, 540, 16, world_color=(0.35, 0.38, 0.45), world_strength=0.8, sun_energy=3.5,
             floor_color=(0.2, 0.2, 0.21))
sc.frame_start, sc.frame_end = 1, 48
crystal = RD.fill_volume_rd(bounds={'x': [-3.0, -1.0], 'y': [-1.0, 1.0], 'z': [0.25, 2.25]}, cell_size=0.25,
                            material=mat('pink', (1.0, 0.18, 0.58), rough=0.3), name='rd_crystal')
orb = RD.fill_sphere_rd(center=(0.0, 0.0, 1.1), radius=0.85, cell_size=0.2, fill=2.0,
                        material=mat('cyan', (0.0, 0.83, 1.0), metal=0.8, rough=0.25), name='rd_orb')
bpy.ops.mesh.primitive_monkey_add(size=1.6, location=(2.2, 0.0, 1.0))
monkey = bpy.context.active_object
monkey.hide_render = True
vox = RD.voxelize_mesh_rd(mesh=monkey, cell_size=0.08, material=mat('amber', (1.0, 0.67, 0.0), rough=0.45),
                          name='rd_monkey')
C.check('fill_volume_rd cells', len(crystal.points) > 100, f'{len(crystal.points)} cells')
C.check('fill_sphere_rd cells inside the sphere', len(orb.points) > 100 and
        float(np.linalg.norm(orb.points - [0, 0, 1.1], axis=1).max()) <= 0.85 + 1e-9, f'{len(orb.points)} cells')
C.check('voxelize_mesh_rd follows the mesh', 200 < len(vox.points) < 20000, f'{len(vox.points)} cells')
crystal.reveal(center=(-2.0, 0.0, 1.25), speed=1.0)


def visible(rd, frame):
    sc.frame_set(frame)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = rd.object.evaluated_get(dg)
    n_big = 0
    for inst in dg.object_instances:
        if inst.is_instance and inst.parent and inst.parent.original == rd.object:
            if inst.matrix_world.to_scale()[0] > 0.5:
                n_big += 1
    return n_big


fps = sc.render.fps
for f in (12, 36):
    t = (f - 1) / fps
    expect = int((np.linalg.norm(crystal.points - [-2.0, 0.0, 1.25], axis=1) < t * 1.0).sum())
    got = visible(crystal, f)
    C.check(f'reveal at frame {f}', abs(got - expect) <= max(2, 0.02 * expect), f'{got} cells shown, {expect} expected')
    C.camera((0.0, -6.8, 2.6), (0.0, 0.0, 1.0), lens=38)
    p = os.path.join(C.OUT, f'rd_f{f:04d}.png')
    C.check(f'render frame {f}', C.render(p), p)
C.sheet([os.path.join(C.OUT, 'rd_f0012.png'), os.path.join(C.OUT, 'rd_f0036.png')],
        os.path.join(C.OUT, 'rd_sheet.png'), cols=2)
C.summary()

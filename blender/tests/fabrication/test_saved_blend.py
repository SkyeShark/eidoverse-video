"""The saved manufacturing example plays on its own: reopen out/manufacturing_example.blend (written by
test_fabrication_render.py) in a fresh Blender without importing eidoblend, jump to frames out of order, and check
that the bead grows, the stocks deepen and the machines move from the file's own keys, nodes and drivers.

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    bash run_blender.sh <worktree>/blender/tests/fabrication/test_saved_blend.py
"""
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
import bpy  # noqa: E402

path = os.path.join(HERE, 'out', 'manufacturing_example.blend')
bpy.ops.wm.open_mainfile(filepath=path)
scene = bpy.context.scene
results = []


def check(name, ok, detail=''):
    line = f"{'PASS' if ok else 'FAIL'} {name}" + (f'  ({detail})' if detail else '')
    print(line, flush=True)
    results.append(ok)


bead = bpy.data.objects['FDM deposited bead']
stocks = [o for o in bpy.data.objects if o.name.startswith('CNC swept')]
fan = next(o for o in bpy.data.objects if o.name.startswith('extruder_fan'))
counts, depths, fans = {}, {}, {}
for f in (300, 40, 456, 120):                         # out of order, as a render farm would ask
    scene.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    counts[f] = len(bead.evaluated_get(dg).to_mesh().vertices)
    bead.evaluated_get(dg).to_mesh_clear()
    d = []
    for s in stocks:
        me = s.evaluated_get(dg).to_mesh()
        d.append(min(v.co.z for v in me.vertices if v.co.z > 1e-6))
        s.evaluated_get(dg).to_mesh_clear()
    depths[f] = d
    fans[f] = tuple(round(x, 6) for x in fan.matrix_world.to_quaternion())
order = sorted(counts)
check('the bead grows frame by frame from the file alone', all(counts[a] < counts[b] for a, b in zip(order, order[1:])),
      ', '.join(f'f{f}: {counts[f] // 16} chords' for f in order))
check('both stocks only ever get lower', all(all(x >= y - 1e-7 for x, y in zip(depths[a], depths[b]))
                                             for a, b in zip(order, order[1:])) and depths[order[-1]] != depths[order[0]],
      ', '.join(f"f{f}: {['%.2f mm' % (v * 1000) for v in depths[f]]}" for f in order))
check('the fan turns between frames', len(set(fans.values())) > 1)
drivers = [fc.driver for m in bpy.data.materials if m.node_tree and m.node_tree.animation_data
           for fc in m.node_tree.animation_data.drivers]
check('the finish filters drive from the camera with simple expressions (no script trust needed)',
      drivers and all(d.is_simple_expression and d.is_valid for d in drivers), f'{len(drivers)} drivers')
print(f'[saved] {sum(results)} passed, {len(results) - sum(results)} failed', flush=True)
sys.exit(0 if all(results) else 1)

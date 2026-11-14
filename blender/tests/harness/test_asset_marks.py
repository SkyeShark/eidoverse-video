"""tests/harness/test_asset_marks.py: harness.assets.import_model marks what it imports as a loaded asset
('eido_loaded_asset', the engine's userData._loadedAsset), so the tools that rewrite UVs and materials skip it
(Blender, no render):

    - a three-part GLB made here and exported (its parts' UVs and materials authored), imported with import_model:
      the root, every imported object and its mesh data carry the mark
    - clone_model's copies, load_kit's parts and its instances carry it too
    - a scene root holding the import, a clone and a plinth built here goes to the terrain family's layer_surface
      (texel density, an 'up' wear layer) whole: the imported meshes keep their UVs and materials exactly, the plinth
      is layered and rescaled

    bash run_blender.sh blender/tests/harness/test_asset_marks.py
"""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'blender'))
sys.dont_write_bytecode = True
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from eidoblend.harness import assets  # noqa: E402
from eidoblend.terrain import layer_surface  # noqa: E402

FAIL = []


def check(ok, what):
    print(f"[marks] {'PASS' if ok else 'FAIL'}: {what}", flush=True)
    if not ok:
        FAIL.append(what)


def material(name, rgb):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*rgb, 1.0)
    return m


def make_glb(path):
    """Three cubes in a row (part_a, part_b, part_c), each with its own material and the cube's own UVs: a small
    authored model, exported as a GLB."""
    bpy.ops.wm.read_homefile(use_empty=True)
    for i, (n, rgb) in enumerate((('part_a', (0.8, 0.2, 0.1)), ('part_b', (0.1, 0.6, 0.2)), ('part_c', (0.2, 0.3, 0.8)))):
        bpy.ops.mesh.primitive_cube_add(size=0.4, location=(i * 0.6, 0.0, 0.2))
        o = bpy.context.object
        o.name = n
        o.data.materials.append(material(n, rgb))
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB')


def uvs(ob):
    a = np.empty(len(ob.data.loops) * 2)
    ob.data.uv_layers.active.data.foreach_get('uv', a)
    return a


def main():
    glb = os.path.join(OUT, 'marks_parts.glb')
    make_glb(glb)
    bpy.ops.wm.read_homefile(use_empty=True)
    root = assets.import_model(glb, name='parts')
    sub = [root] + list(root.children_recursive)
    meshes = [o for o in sub if o.type == 'MESH']
    check(len(meshes) == 3, f'the import holds the three parts: {[o.name for o in meshes]}')
    check(all(o.get('eido_loaded_asset') for o in sub), 'the root and every imported object carry eido_loaded_asset')
    check(all(o.data.get('eido_loaded_asset') for o in meshes), "and every imported mesh's data")
    clone = assets.clone_model(root, name='parts_copy', location=(0.0, 1.0, 0.0))
    csub = [clone] + list(clone.children_recursive)
    check(all(o.get('eido_loaded_asset') for o in csub), f'clone_model copies carry it ({len(csub)} objects)')
    kit_root = assets.import_model(glb, name='kit_parts')
    kit = assets.load_kit(kit_root)
    inst = kit.get(kit.list()[0], location=(0.0, -1.0, 0.0))
    parts = [o for c in kit.parts.values() for o in c.all_objects]
    check(kit.count == 3 and all(o.get('eido_loaded_asset') for o in parts) and inst.get('eido_loaded_asset'),
          f'load_kit: its {len(parts)} parts (moved out of the import) and an instance carry it')

    # the built plinth: a cube with its own UVs and material, under the same scene root as the import and the clone
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.6, 0.0, -0.5))
    plinth = bpy.context.object
    plinth.name = 'plinth'
    plinth.scale = (2.0, 2.0, 1.0)
    plinth.data.materials.append(material('plinth', (0.5, 0.5, 0.5)))
    set_root = bpy.data.objects.new('set_root', None)
    bpy.context.scene.collection.objects.link(set_root)
    for o in (root, clone, plinth):
        o.parent = set_root
    bpy.context.view_layer.update()
    fetched = meshes + [o for o in clone.children_recursive if o.type == 'MESH']
    before_uv = {o.name: uvs(o) for o in fetched}
    before_mat = {o.name: o.material_slots[0].material.name for o in fetched}
    plinth_uv = uvs(plinth)
    made = layer_surface(set_root, metres_per_tile=0.5,
                         layers=[{'mask': 'up', 'color': 0x8a7859, 'amount': 0.5, 'power': 2}])
    after_uv_same = all(np.array_equal(before_uv[o.name], uvs(o)) for o in fetched)
    after_mat_same = all(o.material_slots[0].material.name == before_mat[o.name] for o in fetched)
    check(after_uv_same and after_mat_same, f'layer_surface on the whole scene root left the {len(fetched)} imported '
          'meshes (the import and its clone) exactly as authored: UVs and materials')
    pm = plinth.material_slots[0].material.name
    check(pm.endswith('_layered') and not np.array_equal(plinth_uv, uvs(plinth)),
          f"and layered the plinth built here ('{pm}', its UVs rescaled to 0.5 m a tile): {sorted(made)}")


if __name__ == '__main__':
    try:
        main()
    except Exception:                                                # noqa: BLE001
        traceback.print_exc()
        FAIL.append('raised')
    print(f"[marks] {'ALL PASS' if not FAIL else f'{len(FAIL)} FAIL'}", flush=True)
    sys.stdout.flush()
    os._exit(1 if FAIL else 0)

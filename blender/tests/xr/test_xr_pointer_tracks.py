"""tests/xr/test_xr_pointer_tracks.py: keyed material values reach the GLB as KHR_animation_pointer channels whatever
the object carries, no render (an API run):

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/xr/test_xr_pointer_tracks.py

Three planes, each with its own material whose base colour is keyed red -> blue over 25 frames: a plain one, one with
a Subdivision Surface modifier, one skinned (an Armature modifier). export_xr (no bakes, no world, no page) exports the
two modified ones from their evaluated meshes (export_apply), where Blender 5.2's exporter meets their materials as
evaluated copies (export._PointerMaterialFix hands it the originals). Checked for each: the export finishes, its GLB
has one pointer channel, on the glTF material its mesh draws with, red at the first key and blue at the last.
"""
import os
import shutil
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
WORKTREE = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(WORKTREE, 'blender'))
sys.dont_write_bytecode = True
OUT = os.path.join(HERE, 'out', 'pointer_tracks')
shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT, exist_ok=True)

from eidoblend.xr import export as X  # noqa: E402
from eidoblend.xr import glb as G  # noqa: E402

FAILS = []


def check(name, ok, detail=''):
    print(f"{'PASS' if ok else 'FAIL'} {name}{'  (' + str(detail) + ')' if detail else ''}", flush=True)
    if not ok:
        FAILS.append(name)


def plane(name, modifier):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, 25
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-.5, -.5, 0), (.5, -.5, 0), (.5, .5, 0), (-.5, .5, 0)], [], [(0, 1, 2, 3)])
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    m = bpy.data.materials.new(name + ' finish')
    m.use_nodes = True
    pb = m.node_tree.nodes['Principled BSDF']
    for f, c in ((1, (1.0, 0.0, 0.0, 1.0)), (25, (0.0, 0.0, 1.0, 1.0))):
        pb.inputs['Base Color'].default_value = c
        pb.inputs['Base Color'].keyframe_insert('default_value', frame=f)
    me.materials.append(m)
    if modifier == 'SUBSURF':
        ob.modifiers.new('subdivision', 'SUBSURF')
    elif modifier == 'ARMATURE':
        arm = bpy.data.objects.new(name + ' rig', bpy.data.armatures.new(name + ' rig'))
        sc.collection.objects.link(arm)
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode='EDIT')
        b = arm.data.edit_bones.new('root')
        b.head, b.tail = (0, 0, 0), (0, 0, .5)
        bpy.ops.object.mode_set(mode='OBJECT')
        ob.parent = arm
        ob.vertex_groups.new(name='root').add(list(range(4)), 1.0, 'REPLACE')
        ob.modifiers.new('skin', 'ARMATURE').object = arm
    return sc, m


for name, modifier in (('plain', None), ('subdivided', 'SUBSURF'), ('skinned', 'ARMATURE')):
    sc, mat = plane(name, modifier)
    out = os.path.join(OUT, name)
    try:
        man = X.export_xr(out, sc, name='scene', bake_materials=False, world=False, page=False, log=None)
    except Exception as e:  # noqa: BLE001
        check(f'{name}: the export finishes', False, str(e).splitlines()[-1][:160])
        continue
    g = G.read(os.path.join(out, 'scene.glb'))
    js = g.json
    used = {p.get('material') for me in js.get('meshes', []) for p in me['primitives']}
    chans = [(a, ch) for a in js.get('animations', []) for ch in a['channels'] if ch['target'].get('path') == 'pointer']
    ok, detail = False, f'{len(chans)} pointer channels'
    if len(chans) == 1:
        a, ch = chans[0]
        ptr = ch['target']['extensions']['KHR_animation_pointer']['pointer']
        idx = int(ptr.split('/')[2])
        v = g.accessor(a['samplers'][ch['sampler']]['output'])
        first, last = [round(float(x), 3) for x in v[0]], [round(float(x), 3) for x in v[-1]]
        ok = (ptr.endswith('pbrMetallicRoughness/baseColorFactor') and idx in used
              and js['materials'][idx].get('name') == mat.name and first == [1.0, 0.0, 0.0, 1.0]
              and last == [0.0, 0.0, 1.0, 1.0])
        detail = f"{ptr} on '{js['materials'][idx].get('name')}', {first} -> {last}, {len(v)} keys"
    check(f'{name}: the keyed base colour is a pointer channel on its own material, red to blue', ok, detail)
print('\n%d FAIL' % len(FAILS) if FAILS else '\nALL PASS', flush=True)
sys.exit(1 if FAILS else 0)

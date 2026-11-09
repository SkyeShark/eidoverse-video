"""The forest ring, the GLB export and the distance LOD on a white oak.

    bash run_blender.sh blender/tests/trees2/forest_export_lod.py

1. make_forest_ring: 64 slots of the oak's card LOD2 near the camera and its billboard
   beyond 120 m (per-instance rebin by the active camera), with the per-slot wind;
   checks the near / far split against the slot distances, that the grove moves
   between frames 1 and 24, that each slot sways with its own phase, and renders it.
2. export_glb: the app's export (MSFT_lod + screen coverage, KHR_materials_diffuse_
   transmission, _LODn nodes, _branches / _leaves meshes) and the proxy export
   (the bark exports brown, not green).
3. auto_lod + frame_camera_to_tree: the level each camera distance shows.
"""

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.trees import raw  # noqa: E402


def evaluated_points(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    P = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', P)
    ev.to_mesh_clear()
    return P.reshape(-1, 3)


def count_instances(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    n = 0
    for inst in dg.object_instances:
        if inst.is_instance and inst.parent and inst.parent.original == ob:
            n += 1
    return n


def main():
    api = raw()
    from seedthree.bl.forest import make_forest_ring
    from seedthree.bl.export import export_glb
    from seedthree.bl import lod as L
    from seedthree import glb as G
    scene = S.reset()
    S.render_settings(scene, 960, 540, 16)
    tree = api.create_tree(species='whiteOak', seed=1737, level='ALL', billboard=True)
    S.ground(scene, api.ASSETS_DIR, 'grass', tile=3.0)
    sun, _ = S.sky_and_sun(scene, sun_elev_deg=35, sun_az_deg=200, strength=0.10, sun_strength=4.0)
    api.set_sun(sun)
    cam = S.camera(scene, (0.0, -30.0, 6.0), (0.0, 60.0, 4.0), lens=28)
    S.show_only(tree, 'LOD0')

    # ---- 1. forest ring ----
    forest = make_forest_ring(tree, count=64, seed=1)
    fob = forest['object']
    bob = forest['billboard_object']
    slots = forest['slots']
    camp = cam.location
    far_expected = sum(1 for s in slots if (Vector((s['pos'][0], -s['pos'][2], s['pos'][1])) - camp).length > 120)
    n_inst = count_instances(bob)
    S.check('forest slots', len(slots) == 64)
    S.check('billboard instances = far slots (x2 cards)', n_inst == 2 * far_expected,
            '%d instances, %d far slots' % (n_inst, far_expected))
    S.check('near object holds no billboards', count_instances(fob) == 0)
    from seedthree.bl import cast_only
    recv = sun.light_linking.receiver_collection
    twin = cast_only.twin_of(sun)
    states = {'sun': cast_only.link_state(recv, bob), 'twin': cast_only.link_state(twin.light_linking.receiver_collection, bob)}
    S.check('far billboards cast only (sun EXCLUDE, shadowless twin INCLUDE)',
            states == {'sun': 'EXCLUDE', 'twin': 'INCLUDE'} and not twin.data.use_shadow and bob.visible_shadow, str(states))
    api.set_wind(strength=0.6)
    scene.frame_set(1)
    p1 = evaluated_points(fob)
    scene.frame_set(24)
    p24 = evaluated_points(fob)
    d = np.linalg.norm(p24 - p1, axis=1)
    S.check('the grove sways', d.max() > 0.02, 'max %.3f m' % d.max())
    # per-slot phase: displacement direction is the world wind heading for all; magnitude differs per slot
    near_slots = [s for s in slots if (Vector((s['pos'][0], -s['pos'][2], s['pos'][1])) - camp).length <= 120]
    # group realized vertices by nearest slot (xy)
    sxy = np.array([(s['pos'][0], -s['pos'][2]) for s in near_slots])
    idx = np.argmin(((p1[:, None, :2] - sxy[None]) ** 2).sum(-1), axis=1)
    per = [float(np.median(d[idx == i])) for i in range(len(near_slots)) if (idx == i).any()]
    S.check('slots sway out of step', np.std(per) > 1e-3, 'median motion per slot spread %.4f m' % np.std(per))
    disp = (p24 - p1)[d > 0.01]
    if len(disp):
        hd = disp[:, :2] / np.maximum(np.linalg.norm(disp[:, :2], axis=1), 1e-9)[:, None]
        wd = np.array([0.85, -0.53]) / np.linalg.norm([0.85, -0.53])
        S.check('sway along the world wind heading', float(np.median(np.abs(hd @ wd))) > 0.95,
                'median |cos| %.3f' % float(np.median(np.abs(hd @ wd))))
    api.set_wind(strength=0.0)
    scene.frame_set(1)
    api.light_probe(tree)
    S.render(scene, os.path.join(S.OUT, 'forest_ring_oak.png'))
    cam.location = (0.0, -160.0, 20.0)
    cam.rotation_euler = (Vector((0, 0, 4)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    S.render(scene, os.path.join(S.OUT, 'forest_ring_oak_far.png'))
    bpy.data.objects.remove(fob, do_unlink=True)
    bpy.data.objects.remove(bob, do_unlink=True)

    # ---- 2. GLB export ----
    path = os.path.join(S.OUT, 'white_oak_1737.glb')
    res = export_glb(tree, path)
    doc, binary = G.read_glb(path)
    names = [n.get('name') for n in doc['nodes']]
    print('[trees2] glb nodes', names)
    import re
    lod_nodes = [n for n in doc['nodes'] if re.match(r'^White_Oak_LOD\d+$', n.get('name') or '')]
    S.check('LOD nodes _LOD0.._LOD3', sorted(n['name'] for n in lod_nodes) == ['White_Oak_LOD%d' % i for i in range(4)])
    l0 = next(n for n in doc['nodes'] if n.get('name') == 'White_Oak_LOD0')
    ids = l0.get('extensions', {}).get('MSFT_lod', {}).get('ids')
    S.check('MSFT_lod on LOD0', ids is not None and len(ids) == 3 and
            [doc['nodes'][i]['name'] for i in ids] == ['White_Oak_LOD1', 'White_Oak_LOD2', 'White_Oak_LOD3'], str(ids))
    cov = l0.get('extras', {}).get('MSFT_screencoverage')
    h = tree['stats']['summary']['heightMeters']
    exp = [min(1, (h / (2 * dd * math.tan(math.radians(25)))) ** 2) for dd in (35, 70, 120)] + [0.001]
    S.check('MSFT_screencoverage', cov is not None and np.allclose(cov, exp, rtol=1e-6), '%s vs %s' % (cov, exp))
    S.check('extensionsUsed', set(doc.get('extensionsUsed', [])) >= {'MSFT_lod', 'KHR_materials_diffuse_transmission'},
            str(doc.get('extensionsUsed')))
    dts = [m for m in doc['materials'] if 'KHR_materials_diffuse_transmission' in m.get('extensions', {})]
    S.check('diffuse transmission on leaves + cards', len(dts) >= 2 and all(
        'diffuseTransmissionColorTexture' in m['extensions']['KHR_materials_diffuse_transmission'] for m in dts),
        ', '.join(m['name'] for m in dts))
    leaf_mat = next((m for m in doc['materials'] if 'leaves' in m['name']), None)
    S.check('leaf material MASK 0.4', leaf_mat is not None and leaf_mat.get('alphaMode') == 'MASK' and
            abs(leaf_mat.get('alphaCutoff', 0) - 0.4) < 1e-6 and leaf_mat.get('doubleSided'), str(leaf_mat and {k: leaf_mat.get(k) for k in ('alphaMode', 'alphaCutoff', 'doubleSided')}))
    meshes = [m['name'] for m in doc['meshes']]
    S.check('_branches and _leaves meshes', 'White_Oak_LOD0_branches' in meshes and 'White_Oak_LOD0_leaves' in meshes
            and 'White_Oak_LOD2_leaves' in meshes, str(meshes))
    S.check('billboard cards exported', 'billboard_front' in names and 'billboard_side' in names)
    print('[trees2] glb %.1f MB' % (res['bytes'] / 1e6))
    ppath = os.path.join(S.OUT, 'white_oak_1737_proxy.glb')
    export_glb(tree, ppath, materials='proxy')
    pdoc, _ = G.read_glb(ppath)
    bark_ok = False
    for mesh in pdoc['meshes']:
        if mesh['name'].endswith('_branches'):
            mi = mesh['primitives'][0].get('material')
            col = pdoc['materials'][mi]['pbrMetallicRoughness']['baseColorFactor']
            bark_ok = abs(col[0] - (0x6b / 255.0) ** 2.2) < 0.03 and col[0] > col[1]
            print('[trees2] proxy bark colour', col)
            break
    S.check('proxy export: bark is brown (fix f)', bark_ok)
    S.check('proxy export has no extensions', not pdoc.get('extensionsUsed'))

    # ---- 3. auto LOD ----
    bands = L.auto_lod(tree, cam)
    print('[trees2] bands', bands)
    seen = {}
    for dist in (10, 50, 90, 200):
        cam.location = (0.0, -float(dist), 0.0)
        bpy.context.view_layer.update()
        for fr in (2, 1):
            scene.frame_set(fr)
        vis = [n for n, objs in tree['objects'].items() if objs and not objs[0].hide_render]
        seen[dist] = vis
    print('[trees2] visible by distance', seen)
    S.check('auto LOD bands', seen[10] == ['LOD0'] and seen[50] == ['LOD1'] and seen[90] == ['LOD2'] and seen[200] == ['BB'],
            json.dumps(seen))
    cam.location = (30.0, -40.0, 5.0)
    fr = L.frame_camera_to_tree(tree, cam)
    base = fr['lodBaseDist']
    S.check('frameCameraToTree distances (oak: 1.5 / 3 / 5.5)', fr['lod1Dist'] == round(base * 1.5) and
            fr['lod2Dist'] == max(fr['lod1Dist'] + 5, round(base * 3.0)) and
            fr['billboardDist'] == max(fr['lod2Dist'] + 10, round(base * 5.5)), json.dumps(fr))
    bpy.context.view_layer.update()     # matrix_world follows the new location / rotation
    el = math.degrees(math.asin((cam.matrix_world.to_quaternion() @ Vector((0, 0, -1))).normalized().z * -1))
    S.check('framed 18 degrees down', abs(el - 18) < 0.5, '%.2f' % el)

    # ---- 4. the .glb as another engine gets it: re-imported by Blender's glTF importer ----
    reimport(api, path)
    S.summary('forest_export_lod')


def reimport(api, path):
    """Import white_oak_1737.glb into an empty scene and render its LOD0 and its billboard
    (LOD3) side by side under the probe sky: the export's look, not only its structure."""
    scene = S.reset()
    S.render_settings(scene, 960, 540, 16)
    S.ground(scene, api.ASSETS_DIR, 'grass', tile=3.0)
    S.sky_and_sun(scene, sun_elev_deg=35, sun_az_deg=200, strength=0.10, sun_strength=4.0)
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    nodes = {o.name: o for o in new}
    lod0 = nodes.get('White_Oak_LOD0')
    lod3 = nodes.get('White_Oak_LOD3')
    S.check('re-import: the LOD nodes come back', lod0 is not None and lod3 is not None,
            ', '.join(sorted(n for n in nodes if n.startswith('White_Oak_LOD') and n.count('_') == 2)))
    if lod0 is None or lod3 is None:
        return
    keep = {lod0, lod3} | set(lod0.children_recursive) | set(lod3.children_recursive)
    for o in new:
        if o.type == 'MESH' and o not in keep:
            o.hide_render = True
    # the LOD nodes share one spot: the billboard 18 m aside (world X)
    bpy.context.view_layer.update()
    mw = lod3.matrix_world.copy()
    mw.translation = mw.translation + Vector((18.0, 0.0, 0.0))
    lod3.matrix_world = mw
    leaf = next((m for o in lod0.children_recursive if o.type == 'MESH' for m in o.data.materials
                 if m and 'leaves' in m.name), None)
    S.check('re-import: the leaf material keeps its cutout and texture', leaf is not None and any(
        n.type == 'TEX_IMAGE' for n in leaf.node_tree.nodes), '%s, %s' % (
        leaf.name if leaf else 'no leaves material', getattr(leaf, 'surface_render_method', None)))
    S.camera(scene, (9.0, -46.0, 7.5), (9.0, 0.0, 7.5), lens=35)
    S.render(scene, os.path.join(S.OUT, 'glb_reimport_LOD0_and_billboard.png'))


main()

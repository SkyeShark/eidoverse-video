"""The iso field port's probe: three metaballs written into the engine's field layout each frame, meshed by
OpenVDB, played back as a PLY sequence by Geometry Nodes, lit by a key light that they shadow onto the floor
(the engine's raymarched surface could not cast shadows). The surface uses the engine's three TSL hooks:
color_node (a cool-to-warm tint by height), roughness_node (polished at the top, matte at the bottom, so the key
light's highlight is sharp on the upper blobs and spread on the lower ones) and emissive (a faint glow low down).

Checks (always, no render): each hook is linked into its Principled input (Base Color, Roughness, Emission
Color) from the shading point's Geometry Position, a material passed in is left as it is, the bake writes one PLY
per frame and the player sets the hooked material on the played mesh.

    bash run_blender.sh blender/tests/fx/test_iso_field.py [-- frames=1,24] [--no-render]
    (a GPU job: 4 GB VRAM, 8 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)
"""

import math
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.fx import iso_field as fxiso       # noqa: E402
from eidoblend.fx._util import color               # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
args = dict(a.split('=', 1) for a in argv if '=' in a)
RENDER = '--no-render' not in argv
FRAMES = [int(x) for x in args.get('frames', '1,24').split(',')]
OUT = os.path.join(HERE, 'out')
FAILS = []


def check(ok, what):
    print(f"[test_iso] {'PASS' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        FAILS.append(what)


def upstream(sock):
    """every node feeding a socket, transitively"""
    seen, todo = set(), [l.from_node for l in sock.links]
    while todo:
        n = todo.pop()
        if n.name in seen:
            continue
        seen.add(n.name)
        for s in n.inputs:
            todo += [l.from_node for l in s.links]
    return seen


for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y = 960, 540
sc.render.fps = 24
sc.frame_start, sc.frame_end = 1, 24
sc.eevee.taa_render_samples = 16
sc.eevee.use_raytracing = True
sc.eevee.use_fast_gi = True
sc.view_settings.view_transform = 'AgX'
world = bpy.data.worlds.new('w')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (*color('#9fb2c8'), 1)
world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.5
sc.world = world
bpy.ops.mesh.primitive_plane_add(size=6)
fm = bpy.data.materials.new('floor')
fm.use_nodes = True
fm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*color('#5c5a55'), 1)
bpy.context.active_object.data.materials.append(fm)
ld = bpy.data.lights.new('key', 'AREA')
ld.energy = 400
ld.size = 0.8
key = bpy.data.objects.new('key', ld)
sc.collection.objects.link(key)
key.location = (-1.6, -1.2, 2.6)
key.rotation_euler = (math.radians(40), math.radians(-30), math.radians(-35))


# the engine's hooks, written with the builder: (b, position, normal), world space
def tint(b, pos, nrm):
    _x, _y, z = pos.xyz()
    t = b.smoothstep(0.1, 0.9, z)
    return b.rgb_mix((*color('#b98a5e'), 1.0), (*color('#8fa3b8'), 1.0), t)


def rough(b, pos, nrm):
    _x, _y, z = pos.xyz()
    return b.mix(0.75, 0.08, b.smoothstep(0.25, 0.75, z))


def glow(b, pos, nrm):
    _x, _y, z = pos.xyz()
    k = (1.0 - b.smoothstep(0.05, 0.3, z)) * 0.6
    return b.vscale(b.combine(1.0, 0.35, 0.08), k)


iso = fxiso.make_iso_field(resolution=64, half=0.5, iso=50, cache_dir=os.path.join(OUT, 'iso_cache'), name='blobs',
                           metalness=0.9, color_node=tint, roughness_node=rough, emissive=glow)
bsdf = iso.material.node_tree.nodes['Principled BSDF']
for inp in ('Base Color', 'Roughness', 'Emission Color'):
    feeds = upstream(bsdf.inputs[inp])
    pos_fed = any(iso.material.node_tree.nodes[n].type == 'NEW_GEOMETRY' for n in feeds)
    check(bsdf.inputs[inp].is_linked and pos_fed, f'hook linked into {inp} from the shading point ({len(feeds)} nodes)')
check(abs(bsdf.inputs['Metallic'].default_value - 0.9) < 1e-6, 'metalness passed through')

own = bpy.data.materials.new('own')
own.use_nodes = True
own_links = len(own.node_tree.links)
iso2 = fxiso.make_iso_field(resolution=16, half=0.5, iso=50, material=own, roughness_node=rough, name='own_field',
                            cache_dir=os.path.join(OUT, 'iso_cache'))
check(iso2.material is own and len(own.node_tree.links) == own_links, 'a material passed in is used as it is')
bpy.data.objects.remove(iso2.object, do_unlink=True)

r = iso.res
g = np.linspace(0, 1, r)
X, Y, Z = np.meshgrid(g * 2 * iso.half - iso.half, g * 2 * iso.half, g * 2 * iso.half - iso.half, indexing='ij')


def update(frame, t, it):
    f = np.zeros_like(X)
    for k in range(3):
        a = t * 2.0 + k * 2.1
        c = (0.22 * math.cos(a), 0.45 + 0.18 * math.sin(a * 1.3), 0.22 * math.sin(a))   # engine axes, y up
        f += 100.0 * np.exp(-((X - c[0]) ** 2 + (Y - c[1]) ** 2 + (Z - c[2]) ** 2) / (2 * 0.11 ** 2))
    # the engine's layout: idx = x + y*res + z*res^2  ->  [z][y][x]
    it.field[:] = f.transpose(2, 1, 0).ravel().astype(np.float32)


iso.bake(1, 24, update=update)
plys = [os.path.join(iso.cache_dir, f'blobs_{f:04d}.ply') for f in range(1, 25)]
check(all(os.path.isfile(p) and os.path.getsize(p) > 1000 for p in plys), 'the bake wrote one PLY per frame')
mod = iso.object.modifiers.get('iso_player')
setm = [n for n in mod.node_group.nodes if n.bl_idname == 'GeometryNodeSetMaterial'] if mod else []
check(bool(setm) and setm[0].inputs['Material'].default_value == iso.material,
      'the player sets the hooked material on the played mesh')
sc.frame_set(12)
ev = iso.object.evaluated_get(bpy.context.evaluated_depsgraph_get())
me = ev.to_mesh()
zs = np.array([(iso.object.matrix_world @ v.co).z for v in me.vertices])
check(len(zs) > 500 and zs.min() > -0.05 and zs.max() < 1.05, f'frame 12 plays {len(zs)} vertices, z {zs.min():.2f}..'
                                                                f'{zs.max():.2f}')
ev.to_mesh_clear()

if RENDER:
    cd = bpy.data.cameras.new('cam')
    cd.lens = 45
    cam = bpy.data.objects.new('cam', cd)
    sc.collection.objects.link(cam)
    cam.location = (2.3, -2.6, 1.4)
    tgt = bpy.data.objects.new('tgt', None)
    sc.collection.objects.link(tgt)
    tgt.location = (0, 0, 0.45)
    c = cam.constraints.new('TRACK_TO')
    c.target = tgt
    c.track_axis = 'TRACK_NEGATIVE_Z'
    c.up_axis = 'UP_Y'
    sc.camera = cam
    for f in FRAMES:
        sc.frame_set(f)
        sc.render.filepath = os.path.join(OUT, f'iso_field_f{f:04d}.png')
        bpy.ops.render.render(write_still=True)
        print('[test_iso] wrote', sc.render.filepath)
print(f'[test_iso] {"FAIL" if FAILS else "PASS"}: {len(FAILS)} failed check(s)')
print('[test_iso] DONE')

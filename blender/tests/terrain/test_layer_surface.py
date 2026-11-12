"""Probe: layer_surface on geometry built in code (a lathed fountain basin, a bevelled stepped
plinth, a column), before and after, in EEVEE.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 \
        bash run_blender.sh <worktree>/blender/tests/terrain/test_layer_surface.py

Writes out/layers_before.png and out/layers_after.png from the same camera, and prints the texel
densities before/after normalising and the curvature ranges the masks read.

Then the two things an unrotated set cannot show (out/layers_rotated.png, out/layers_sphere.png):
three identical cubes under a grunge-only layer, unrotated, turned 90 deg about Z and tipped 90 deg
about X (the world-space triplanar must read as the same blotches on every face of all three, never
streaks), and a low-poly smooth sphere under an 'up' layer (the line must be round: the smooth
geometry normal, not the faceted true normal).
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixture as F  # noqa: E402

import bmesh  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from eidoblend.terrain import make_layered_material, layer_surface, find_set, add_curvature  # noqa: E402
from eidoblend.placement import place_on  # noqa: E402


def lathe(name, profile, segments=72):
    """Revolve an (r, z) profile about Z (smooth shaded): a basin."""
    bm = bmesh.new()
    verts = [bm.verts.new((r, 0.0, z)) for r, z in profile]
    edges = [bm.edges.new((verts[i], verts[i + 1])) for i in range(len(verts) - 1)]
    bmesh.ops.spin(bm, geom=verts + edges, cent=(0, 0, 0), axis=(0, 0, 1), angle=2 * math.pi,
                   steps=segments, use_merge=True)
    bm.normal_update()
    inner = [f for f in bm.faces if f.calc_center_median().xy.length < 0.8]
    if inner and inner[0].normal.z < 0:          # the floor faces up: the shell's outside is its front
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    me.uv_layers.new(name='UVMap')               # unwrapped in islands, at whatever scale: the
    bpy.context.view_layer.objects.active = o    # density normalising below sets it to metres
    o.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(50), island_margin=0.01)
    bpy.ops.object.mode_set(mode='OBJECT')
    return o


def bevelled_box(name, size, loc, width=0.035, segments=4):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    md = o.modifiers.new('bevel', 'BEVEL')
    md.width = width
    md.segments = segments
    md.harden_normals = True                    # flat caps, smooth bevel bands (ExtrudeGeometry's normals)
    bpy.ops.object.shade_smooth()
    bpy.ops.object.modifier_apply(modifier='bevel')
    return o


F.clean_scene()
F.render_settings(960, 540, 16)
F.test_daylight(sun_elevation=38, sun_azimuth=215)
ground, height_at = F.ground(size=24, seed=3, clearing_m=9, relief_m=0.8)

steps = [bevelled_box('step_%d' % i, (3.4 - 0.7 * i, 3.4 - 0.7 * i, 0.32), (2.6, 0.6, 0.16 + 0.32 * i))
         for i in range(3)]
basin = lathe('basin', [(0.0, 0.10), (0.95, 0.12), (1.12, 0.22), (1.20, 0.45), (1.24, 0.62), (1.30, 0.66),
                        (1.38, 0.64), (1.42, 0.58), (1.40, 0.40), (1.30, 0.16), (1.36, 0.05), (1.44, 0.0)])
basin.location = (-1.6, 0.4, 0.0)
bpy.ops.mesh.primitive_cylinder_add(radius=0.28, depth=2.2, vertices=48, location=(2.6, 0.6, 2.06))
col = bpy.context.active_object
col.name = 'column'
md = col.modifiers.new('bevel', 'BEVEL')
md.width, md.segments, md.harden_normals = 0.03, 4, True
bpy.ops.object.shade_smooth()
bpy.ops.object.modifier_apply(modifier='bevel')
built = steps + [basin, col]
place_on(basin, ground, xy=(-1.6, 0.4))

tex = find_set('Concrete034')
base = make_layered_material({'map': tex['color'], 'roughness_map': tex['roughness'], 'normal_map': tex['normal'],
                              'roughness': 1.0}, [], name='concrete')
for o in built:
    o.data.materials.clear()
    o.data.materials.append(base)

cam = F.camera('cam_layers', (-3.2, -6.4, 2.6), (0.6, 0.6, 0.7), 32)
F.render(cam, F.OUT / 'layers_before.png')

WEAR = [
    {'mask': 'cavity', 'scale': 0.75, 'color': 0x2b2419, 'roughness': 1.0, 'amount': 0.9, 'range': (0.15, 0.72),
     'grunge': 0.35},
    {'mask': 'edges', 'scale': 0.08, 'color': 0xc9bda0, 'roughness': 0.62, 'amount': 0.6, 'range': (0.2, 0.72)},
    {'mask': 'up', 'color': 0x8a7859, 'amount': 0.38, 'power': 3, 'grunge': 0.8},
    # splash and damp soil climbing the foot of everything that stands in the ground
    {'mask': 'below', 'z': 0.14, 'fade': 0.16, 'color': 0x3a2c1e, 'roughness': 0.95, 'amount': 0.8, 'grunge': 0.5},
]
layer_surface(built, metres_per_tile=1.15, grunge={'scale': 0.55, 'seed': 7}, layers=WEAR)
for o in built:
    c = np.empty(len(o.data.loops), dtype=np.float32)
    o.data.attributes['eido_curvature'].data.foreach_get('value', c)
    print('[layers-test] %-8s curvature 1/m: min %.2f  p50 %.2f  max %.2f' % (o.name, c.min(), np.median(c), c.max()))
F.render(cam, F.OUT / 'layers_after.png')
cam2 = F.camera('cam_layers_close', (-2.9, -1.6, 1.55), (-1.6, 0.4, 0.35), 35)
F.render(cam2, F.OUT / 'layers_after_basin.png')
cam3 = F.camera('cam_layers_steps', (0.9, -1.3, 1.25), (2.2, 0.2, 0.5), 35)
F.render(cam3, F.OUT / 'layers_after_steps.png')

# ── rotated objects and smooth normals ──
GRUNGE = [{'mask': 'grunge', 'color': 0x1a140c, 'amount': 1.0, 'range': (0.42, 0.58)}]
cubes = []
for i, (name, rot) in enumerate((('cube_unrotated', (0, 0, 0)), ('cube_yaw90', (0, 0, math.radians(90))),
                                 ('cube_tipX90', (math.radians(90), 0, 0)))):
    bpy.ops.mesh.primitive_cube_add(size=1.6, location=(-2.4 + i * 2.4, -6.0, 0.8), rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(make_layered_material({'color': 0xd8d2c4, 'roughness': 0.8}, [], name=name + '_base'))
    layer_surface([o], layers=GRUNGE, grunge={'scale': 0.55, 'seed': 7})
    cubes.append(o)
bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.9, location=(5.5, -4.0, 0.9))
sp = bpy.context.active_object
sp.name = 'sphere_up'
sp.data.shade_smooth()
sp.data.materials.append(make_layered_material({'color': 0x5a4636, 'roughness': 0.8}, [], name='sphere_base'))
layer_surface([sp], layers=[{'mask': 'up', 'color': 0xf2f2f2, 'amount': 1.0, 'power': 1, 'range': (0.55, 0.62)}])
for o in cubes + [sp]:
    at = o.data.attributes.get('eido_geometry_normal')
    print('[layers-test] %-14s geometry normal attribute: %s' % (o.name, (at.domain, at.data_type) if at else None))
cam4 = F.camera('cam_cubes', (3.6, -12.2, 3.2), (0.0, -5.8, 0.7), 35)
F.render(cam4, F.OUT / 'layers_rotated.png')
cam5 = F.camera('cam_sphere', (5.5, -6.3, 3.6), (5.5, -4.0, 1.0), 50)
F.render(cam5, F.OUT / 'layers_sphere.png')

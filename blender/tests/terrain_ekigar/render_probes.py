"""Probes of what this round added, rendered in EEVEE:

  hydrology_mountainRange   an eroded range (1024 texels, 3 km): the filled lakes as flat water meshes, the flow
                            channels darkened into the clay, vegetation density as moss: do the lakes sit in the
                            basins, do the channels follow the valleys?
  hydrology_island_sea      an island with a sea level: sea plane, channels draining to the coast
  display_grid_vs_field     Ekigar's display grid (side 256, bilinear) beside the full 1024 field, same terrain
  local_crop                a 2048-texel field: the local circle's crop at full resolution over the whole tile at
                            the display grid's 512, the crop lifted 2 m so both show
  hydrology_volcano_lakes   the volcano hero (1024 texels, 3 km): its crater lake and flank ponds as
                            build_lake_mesh water, from the hero camera and from over the crater rim, with the
                            channel and wetness masks in the clay

    python blender/tests/terrain_ekigar/render_probes.py --generate    # plain Python: the fields, cached
    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 \\
        bash run_blender.sh <worktree>/blender/tests/terrain_ekigar/render_probes.py [--only name,name]
"""
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, 'out', 'probes')
CACHE = os.path.join(OUT, 'cache')

SCENES = {
    'hydrology_mountainRange': (('chain', [('mountainRange', {'style': 'eroded', 'frequency': 3}),
                                           ('phacelle', {'strength': 0.25})]), 1024, 3000, 0.3),
    'hydrology_island_sea': (('op', 'island', {}), 1024, 3000, 0.3),
    'display_grid_vs_field': (('op', 'mountainRange', {'style': 'alpine', 'relief': 0.7}), 1024, 3000, 0.3),
    'local_crop': (('op', 'mountainRange', {'style': 'eroded'}), 2048, 3000, 0.3),
}
SEA = {'hydrology_island_sea': 0.05}


def build(ek, how):
    if how[0] == 'chain':
        g, ids = ek.chain_graph(how[1])
        return g, ids[-1]
    g, t, _fx = ek.operator_example(how[1], how[2])
    return g, t


def heightfield(ek, name):
    path = os.path.join(CACHE, f'{name}.npz')
    if os.path.exists(path):
        return ek.Heightfield.load(path)
    how, res, world, vs = SCENES[name]
    g, t = build(ek, how)
    hf = ek.generate(g, target=t, resolution=res, world_size=world, vertical_scale=vs, z_base='field')
    hf.meta.pop('graph', None)
    os.makedirs(CACHE, exist_ok=True)
    hf.save(path)
    return hf


if __name__ == '__main__' and '--generate' in sys.argv:
    import _ekigar_load
    ek = _ekigar_load.load()
    for name in SCENES:
        t0 = time.time()
        hf = heightfield(ek, name)
        print(f'{name}: {hf.resolution} {time.time() - t0:.1f}s', flush=True)
    sys.exit(0)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.common import script_args  # noqa: E402
from eidoblend.terrain import ekigar  # noqa: E402

args = script_args()
only = args[args.index('--only') + 1].split(',') if '--only' in args else None
os.makedirs(OUT, exist_ok=True)


def setup(res=(960, 540), samples=16):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = samples
    sc.view_settings.view_transform = 'AgX'
    sc.render.resolution_x, sc.render.resolution_y = res
    w = bpy.data.worlds.new('w')
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (0.42, 0.52, 0.66, 1.0)
    bg.inputs['Strength'].default_value = 0.35
    sun_d = bpy.data.lights.new('sun', 'SUN')
    sun_d.energy = 4.0
    sun_d.angle = math.radians(0.6)
    sun_d.color = (1.0, 0.93, 0.84)
    sun = bpy.data.objects.new('sun', sun_d)
    sc.collection.objects.link(sun)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.clip_end = 100000
    return sc, sun, cam


def aim(obj, at):
    obj.rotation_euler = (Vector(at) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def sun_from(sun, azimuth_deg, elevation_deg):
    a, e = math.radians(azimuth_deg), math.radians(elevation_deg)
    d = Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))
    sun.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()


def clay_with_masks(name='clay_hydro'):
    """Grey clay, darkened and cooled along the flow channels and wet ground, mossed where vegetation is dense:
    the masks read on the terrain, not a material."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes['Principled BSDF']
    bsdf.inputs['Roughness'].default_value = 0.9

    def attr(n):
        a = nt.nodes.new('ShaderNodeAttribute')
        a.attribute_type = 'GEOMETRY'
        a.attribute_name = 'ekigar_' + n
        return a
    ch, veg, wet = attr('channels'), attr('vegetation'), attr('wetness')
    m1 = nt.nodes.new('ShaderNodeMix')
    m1.data_type = 'RGBA'
    m1.inputs[6].default_value = (0.5, 0.5, 0.5, 1)
    m1.inputs[7].default_value = (0.20, 0.42, 0.18, 1)            # moss
    nt.links.new(veg.outputs['Fac'], m1.inputs[0])
    m2 = nt.nodes.new('ShaderNodeMix')
    m2.data_type = 'RGBA'
    m2.inputs[7].default_value = (0.10, 0.16, 0.24, 1)            # wet channel
    mx = nt.nodes.new('ShaderNodeMath')
    mx.operation = 'MAXIMUM'
    sc_w = nt.nodes.new('ShaderNodeMath')
    sc_w.operation = 'MULTIPLY'
    sc_w.inputs[1].default_value = 0.35
    nt.links.new(wet.outputs['Fac'], sc_w.inputs[0])
    nt.links.new(ch.outputs['Fac'], mx.inputs[0])
    nt.links.new(sc_w.outputs[0], mx.inputs[1])
    nt.links.new(mx.outputs[0], m2.inputs[0])
    nt.links.new(m1.outputs[2], m2.inputs[6])
    nt.links.new(m2.outputs[2], bsdf.inputs['Base Color'])
    return mat


def water(name='water'):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    b = mat.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.02, 0.05, 0.07, 1)
    b.inputs['Roughness'].default_value = 0.06
    return mat


def grey():
    return ekigar.preview_material('grey')


def render(sc, name):
    sc.render.filepath = os.path.join(OUT, f'{name}.png')
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f'[probes] {name} {time.time() - t0:.1f}s', flush=True)


def want(name):
    return not only or name in only


if want('hydrology_mountainRange'):
    hf = heightfield(ekigar, 'hydrology_mountainRange')
    hf.set_z_base('min')
    hf.hydrology()
    sc, sun, cam = setup()
    o = ekigar.build_mesh(hf, name='range', mask_names=['channels', 'vegetation', 'wetness'])
    o.data.materials.append(clay_with_masks())
    lk = ekigar.build_lake_mesh(hf, min_depth_m=0.5)
    if lk:
        lk.data.materials.append(water())
    cam.location = (-1700, -1900, 1150)
    cam.data.lens = 30
    aim(cam, (150, 150, 0))
    sun_from(sun, 215, 22)
    render(sc, 'hydrology_mountainRange')
    cam.location = (0, 0, 4200)
    cam.data.lens = 35
    aim(cam, (0, 0, 0))
    sun_from(sun, 215, 35)
    render(sc, 'hydrology_mountainRange_top')

if want('hydrology_island_sea'):
    hf = heightfield(ekigar, 'hydrology_island_sea')
    sea = SEA['hydrology_island_sea']
    hf.set_z_base('field')
    hf.hydrology(sea_level=sea)
    sc, sun, cam = setup()
    o = ekigar.build_mesh(hf, name='island', mask_names=['channels', 'vegetation', 'wetness'])
    o.data.materials.append(clay_with_masks())
    lk = ekigar.build_lake_mesh(hf, min_depth_m=0.5)
    if lk:
        lk.data.materials.append(water())
    bpy.ops.mesh.primitive_plane_add(size=hf.world_size * 1.5, location=(0, 0, sea * hf.metres_per_unit))
    bpy.context.active_object.data.materials.append(water('sea'))
    cam.location = (-1500, -1900, 900)
    cam.data.lens = 30
    aim(cam, (0, 0, 0))
    sun_from(sun, 220, 20)
    render(sc, 'hydrology_island_sea')

if want('display_grid_vs_field'):
    hf = heightfield(ekigar, 'display_grid_vs_field')
    hf.set_z_base('min')
    sc, sun, cam = setup()
    a = ekigar.build_mesh(hf, name='full', attributes=False, location=(-1600, 0, 0))
    b = ekigar.build_mesh(hf, name='grid256', side=256, attributes=False, location=(1600, 0, 0))
    for o in (a, b):
        o.data.materials.append(grey())
    cam.location = (0, -5200, 2300)
    cam.data.lens = 35
    aim(cam, (0, 0, 150))
    sun_from(sun, 210, 18)
    render(sc, 'display_grid_vs_field')

if want('local_crop'):
    hf = heightfield(ekigar, 'local_crop')
    hf.set_z_base('min')
    sc, sun, cam = setup()
    whole = ekigar.build_mesh(hf, name='whole512', side=512, attributes=False)
    whole.data.materials.append(grey())
    cut = ekigar.cut_for(hf, (1200.0, 600.0), radius_m=450.0, fade_m=100.0)
    crop = ekigar.build_mesh(hf, name='crop', crop=cut, mask_names=[], location=(0, 0, 2.0))
    m = bpy.data.materials.new('crop_clay')
    m.use_nodes = True
    m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.62, 0.48, 0.36, 1)
    m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.9
    crop.data.materials.append(m)
    cam.location = (-900, -1500, 1100)
    cam.data.lens = 32
    aim(cam, (1100, 600, 100))
    sun_from(sun, 215, 20)
    render(sc, 'local_crop')

if want('hydrology_volcano_lakes'):
    import numpy as np
    path = os.path.join(HERE, 'out', 'heroes', 'cache', 'hero_volcano.npz')
    if os.path.exists(path):
        hf = ekigar.Heightfield.load(path)
        H = hf.hydrology()
        sc, sun, cam = setup()
        o = ekigar.build_mesh(hf, name='volcano', mask_names=['channels', 'vegetation', 'wetness'])
        o.data.materials.append(clay_with_masks())
        lk = ekigar.build_lake_mesh(hf, min_depth_m=0.5)
        if lk:
            lk.data.materials.append(water())
        cam.location = (-1700, -2200, 900)
        cam.data.lens = 35
        aim(cam, (0, 0, 250))
        sun_from(sun, 230, 16)
        render(sc, 'hydrology_volcano_lakes')
        d = H['lakeDepth_m']
        j, i = np.unravel_index(int(np.argmax(d)), d.shape)
        xs, ys = hf.grid_xy()
        lx, ly = float(xs[j, i]), float(ys[j, i])
        lz = float((H['filled'][j, i] - hf.z_base) * hf.metres_per_unit)
        cam.location = (lx - 420, ly - 420, lz + 300)
        aim(cam, (lx, ly, lz))
        sun_from(sun, 230, 28)
        render(sc, 'hydrology_volcano_crater_lake')
    else:
        print('[probes] hydrology_volcano_lakes: no hero_volcano cache (run hero_scenes.py)', flush=True)
print('[probes] done', flush=True)

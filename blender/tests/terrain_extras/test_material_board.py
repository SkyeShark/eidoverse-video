"""Material boards for eidoblend.materials (procedural_materials.js): every generator, every factory, the recipe.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/terrain_extras/test_material_board.py [--no-render]
    (renders are GPU jobs: on a shared machine queue them with EIDO_GPU_WRAP, blender/tests/_where.py)

Builds three boards and renders each to blender/tests/terrain_extras/out/:
  pm_generators.png   every generator and composite mode as an unlit swatch (Standard view: the swatch shows the
                      image's own bytes), the engine's options in the labels
  pm_factories.png    the six factories, a cow-patched skin and the 90s plastic recipe on spheres and bevelled boxes
                      over a grey floor, studio light (AgX)
  pm_raking.png       four normal-mapped materials on flat tiles under one low light from the upper left, so the
                      relief's direction reads (raised scale centres light on their upper-left flanks)
Checks (PASS/FAIL): every image is packed and has the generator's size and colour space; the factories' sockets hold
the engine's values (roughness, metalness, coat, IOR, normal strength); the maps are wired where three reads them.
"""
import math
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.materials import procedural as PM  # noqa: E402

OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RENDER = '--no-render' not in ARGS
FAILS = []


def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok:
        FAILS.append(msg)


def reset(name):
    sc = bpy.data.scenes.new(name)
    if bpy.context.window:
        bpy.context.window.scene = sc
    return sc


def base_scene(sc, view='AgX', w=960, h=540, samples=16):
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.eevee.taa_render_samples = samples
    sc.view_settings.view_transform = view
    sc.view_settings.look = 'None'
    sc.render.image_settings.file_format = 'PNG'
    sc.render.film_transparent = False


def link(sc, ob):
    sc.collection.objects.link(ob)
    return ob


def plane(sc, name, size, loc, rot=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    s = size / 2
    me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='UVMap')
    for i, c in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
        uv.data[i].uv = c
    ob = bpy.data.objects.new(name, me)
    ob.location, ob.rotation_euler = loc, rot
    return link(sc, ob)


def label(sc, text, loc, size=0.07, rot=(0, 0, 0), mat=None):
    cu = bpy.data.curves.new('lbl', 'FONT')
    cu.body = text
    cu.size = size
    cu.align_x = 'CENTER'
    ob = bpy.data.objects.new('lbl_' + text[:20], cu)
    ob.location, ob.rotation_euler = loc, rot
    if mat:
        cu.materials.append(mat)
    return link(sc, ob)


def emit_mat(name, color=(1, 1, 1, 1), strength=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    e = nt.nodes.new('ShaderNodeEmission')
    e.inputs['Color'].default_value = color
    e.inputs['Strength'].default_value = strength
    o = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(e.outputs[0], o.inputs['Surface'])
    return m


def swatch_mat(img):
    """the image's bytes on screen under the Standard view: a Non-Color image's raw value v needs linear v^2.2-ish
    (the sRGB curve) to come back out as v; an sRGB image is already decoded by the texture node."""
    m = bpy.data.materials.new('sw_' + img.name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    t = nt.nodes.new('ShaderNodeTexImage')
    t.image = img
    t.interpolation = 'Closest'
    e = nt.nodes.new('ShaderNodeEmission')
    o = nt.nodes.new('ShaderNodeOutputMaterial')
    if img.colorspace_settings.name == 'sRGB':
        nt.links.new(t.outputs['Color'], e.inputs['Color'])
    else:
        sep = nt.nodes.new('ShaderNodeSeparateColor')
        comb = nt.nodes.new('ShaderNodeCombineColor')
        nt.links.new(t.outputs['Color'], sep.inputs[0])
        for i in range(3):
            # exact sRGB EOTF: v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ^ 2.4
            lo = nt.nodes.new('ShaderNodeMath'); lo.operation = 'DIVIDE'; lo.inputs[1].default_value = 12.92
            a = nt.nodes.new('ShaderNodeMath'); a.operation = 'MULTIPLY_ADD'
            a.inputs[1].default_value = 1 / 1.055; a.inputs[2].default_value = 0.055 / 1.055
            p = nt.nodes.new('ShaderNodeMath'); p.operation = 'POWER'; p.inputs[1].default_value = 2.4
            gt = nt.nodes.new('ShaderNodeMath'); gt.operation = 'GREATER_THAN'; gt.inputs[1].default_value = 0.04045
            mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'FLOAT'
            nt.links.new(sep.outputs[i], lo.inputs[0])
            nt.links.new(sep.outputs[i], a.inputs[0])
            nt.links.new(a.outputs[0], p.inputs[0])
            nt.links.new(sep.outputs[i], gt.inputs[0])
            nt.links.new(gt.outputs[0], mx.inputs[0])
            nt.links.new(lo.outputs[0], mx.inputs[2])
            nt.links.new(p.outputs[0], mx.inputs[3])
            nt.links.new(mx.outputs[0], comb.inputs[i])
        nt.links.new(comb.outputs[0], e.inputs['Color'])
    nt.links.new(e.outputs[0], o.inputs['Surface'])
    return m


def camera(sc, loc, look, lens=50.0, ortho=None):
    cd = bpy.data.cameras.new('cam')
    if ortho:
        cd.type = 'ORTHO'
        cd.ortho_scale = ortho
    else:
        cd.lens = lens
    cam = bpy.data.objects.new('cam', cd)
    cam.location = loc
    d = (look[0] - loc[0], look[1] - loc[1], look[2] - loc[2])
    from mathutils import Vector
    cam.rotation_euler = Vector(d).to_track_quat('-Z', 'Y').to_euler()
    link(sc, cam)
    sc.camera = cam
    return cam


def world(sc, color=(0.05, 0.05, 0.05), strength=1.0):
    w = bpy.data.worlds.new('w_' + sc.name)
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = tuple(color) + (1.0,)
    bg.inputs['Strength'].default_value = strength
    sc.world = w


def render(sc, path):
    if not RENDER:
        return
    sc.render.filepath = path
    if bpy.context.window:
        bpy.context.window.scene = sc
    bpy.ops.render.render(write_still=True, scene=sc.name)
    check(os.path.exists(path), 'rendered ' + os.path.basename(path))


# ------------------------------------------------------------------------------------------ the generators ---

def board_generators():
    sc = reset('pm_generators')
    base_scene(sc, view='Standard')
    world(sc, (0.02, 0.02, 0.02))
    S = 256
    noise_d = PM.noise(S, S)
    tiles = [
        ('scratches()', PM.scratches(S, S)),
        ('scratches density .6\ndepth .9 dir .3', PM.scratches(S, S, density=0.6, depth=0.9, direction=0.3, seed=7)),
        ('smudges()', PM.smudges(S, S)),
        ('smudges amount .8 scale 1.6', PM.smudges(S, S, amount=0.8, scale=1.6, seed=5)),
        ('noise()', noise_d),
        ('noise scale 12 oct 5\ncontrast .7', PM.noise(S, S, scale=12, octaves=5, contrast=0.7)),
        ('noise warp scale 3', PM.noise(S, S, {'scale': 3, 'warp': True})),
        ('voronoi cells', PM.voronoi(S, S)),
        ('voronoi edges', PM.voronoi(S, S, mode='edges', scale=6, edgeWidth=0.05)),
        ('voronoi distance', PM.voronoi(S, S, mode='distance', scale=10)),
        ('patches blob (cow)', PM.patches(S, S)),
        ('patches voronoi\n(giraffe)', PM.patches(S, S, shape='voronoi', base_color='#e8b04a', patch_color='#6b3a12',
                                                   scale=6, threshold=0.0, softness=0.12)),
        ('patches spots (frog)', PM.patches(S, S, shape='spots', base_color=0x70d0b1, patch_color=0x1a1a1a, scale=7,
                                            threshold=0.4)),
        ('pores()', PM.pores(S, S)),
        ('pores density .9\ndepth .8', PM.pores(S, S, density=0.9, depth=0.8, seed=3)),
        ('weave()', PM.weave(S, S)),
        ('grain()', PM.grain(S, S)),
        ('grain wood\nstretch 14', PM.grain(S, S, scale=3, stretch=14, contrast=1.6)),
        ('height_to_normal\n(noise) 1.0', PM.height_to_normal(noise_d)),
    ]
    sc_a = PM.scratches(S, S, density=0.5, depth=0.6)
    gr = PM.grain(S, S)
    wv = PM.weave(S, S)
    for mode in PM._gen.MODES:
        b = sc_a if mode in ('add', 'max') else (gr if mode in ('screen', 'overlay') else wv)
        tiles.append(('composite %s' % mode, PM.composite(noise_d, b, mode, strength=0.7 if mode == 'screen' else None)))
    cols = 9
    pitch = 1.18
    lm = emit_mat('lbl_white', (0.85, 0.85, 0.85, 1))
    for i, (txt, img) in enumerate(tiles):
        r, c = divmod(i, cols)
        x = (c - (cols - 1) / 2) * pitch
        y = -r * 1.42
        p = plane(sc, 'tile_%02d' % i, 1.0, (x, y, 0))
        p.data.materials.append(swatch_mat(img))
        label(sc, txt, (x, y - 0.6, 0), size=0.085, mat=lm)
    rows = (len(tiles) + cols - 1) // cols
    camera(sc, (0, -(rows - 1) * 1.42 / 2, 20), (0, -(rows - 1) * 1.42 / 2, 0), ortho=cols * pitch + 0.2)
    sc.render.resolution_x, sc.render.resolution_y = 960, int(960 * (rows * 1.42 + 0.3) / (cols * pitch + 0.2))
    # checks: sizes, colour spaces, packing
    for txt, img in tiles:
        ok = tuple(img.size) == (S, S) and img.packed_file is not None
        cs = img.colorspace_settings.name
        want = 'sRGB' if txt.startswith('patches') else 'Non-Color'
        check(ok and cs == want, '%-28s %dx%d packed=%s %s' % (txt.replace('\n', ' '), img.size[0], img.size[1],
                                                              img.packed_file is not None, cs))
    render(sc, os.path.join(OUT, 'pm_generators.png'))


# ------------------------------------------------------------------------------------------- the factories ---

def bevel_box(sc, name, size, loc):
    bpy.ops.mesh.primitive_cube_add(size=size, location=loc)
    ob = bpy.context.active_object
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    link(sc, ob)
    ob.name = name
    md = ob.modifiers.new('bevel', 'BEVEL')
    md.width = size * 0.12
    md.segments = 5
    md.harden_normals = False
    ob.data.shade_smooth()
    return ob


def sphere(sc, name, r, loc):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=96, ring_count=48)
    ob = bpy.context.active_object
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    link(sc, ob)
    ob.name = name
    ob.data.shade_smooth()
    return ob


def studio(sc, target=(0, 0, 0.4)):
    def area(name, loc, power, size, color=(1, 1, 1)):
        ld = bpy.data.lights.new(name, 'AREA')
        ld.energy = power
        ld.size = size
        ld.color = color
        ob = bpy.data.objects.new(name, ld)
        ob.location = loc
        from mathutils import Vector
        ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        link(sc, ob)
    area('key', (-3.0, -4.0, 4.0), 650, 3.0)
    area('rim', (3.5, 3.0, 2.5), 450, 2.0, (0.9, 0.95, 1.0))
    area('fill', (4.0, -3.5, 1.2), 120, 3.0)


def factory_materials():
    return [
        ('create_painted_metal\nscratches+smudges', PM.create_painted_metal(color=0x8a1c1c, scratches=True,
                                                                               smudges=True, repeat=(2, 2))),
        ('create_rubber()', PM.create_rubber(repeat=(2, 2))),
        ('create_skin()', PM.create_skin()),
        ('create_skin patches\n(cow)', PM.create_skin(color=0xfff0e0, patches={'shape': 'blob', 'patchColor': 0x1a1a1a,
                                                                                'scale': 3, 'threshold': 0.5})),
        ('create_scaly()', PM.create_scaly(repeat=(2, 2))),
        ('create_fabric wear', PM.create_fabric(wear={'amount': 0.5}, repeat=(2, 2))),
        ('create_worn_metal()', PM.create_worn_metal(repeat=(1, 1))),
        ('computer_plastic_90s', PM.computer_plastic_90s(repeat=(3, 3))),
    ]


def ink_mat():
    m = bpy.data.materials.new('ink')
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.004, 0.004, 0.004, 1)
    b.inputs['Roughness'].default_value = 0.9
    return m


def board_factories(mats):
    sc = reset('pm_factories')
    base_scene(sc, view='AgX', samples=32)
    world(sc, (0.18, 0.19, 0.21), 0.35)
    fl = plane(sc, 'floor', 30, (0, 0, 0))
    fm = bpy.data.materials.new('floor')
    fm.use_nodes = True
    fm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.06, 0.06, 0.065, 1)
    fm.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.8
    fl.data.materials.append(fm)
    lm = emit_mat('lbl_light', (0.8, 0.8, 0.8, 1), 1.2)
    cols = 5
    for i, (txt, m) in enumerate(mats):
        r, c = divmod(i, cols)
        x = (c - (cols - 1) / 2) * 1.55
        y = 0.9 - r * 1.75
        s = sphere(sc, 'sphere_%d' % i, 0.34, (x - 0.36, y + 0.12, 0.34))
        s.data.materials.append(m)
        b = bevel_box(sc, 'box_%d' % i, 0.5, (x + 0.38, y - 0.05, 0.25))
        b.rotation_euler = (0, 0, math.radians(28))
        b.data.materials.append(m)
        label(sc, txt, (x, y - 0.62, 0.002), size=0.085, mat=lm)
    studio(sc, target=(0, 0, 0.3))
    camera(sc, (0, -6.6, 6.6), (0, -0.4, 0.0), lens=34)
    render(sc, os.path.join(OUT, 'pm_factories.png'))
    # each row closer, so the maps' scale and the coat's reflections read (the back row seen over the front one)
    for r, y, z in ((0, 0.9, 3.0), (1, 0.9 - 1.75, 1.55)):
        camera(sc, (0, y - 4.6, z), (0, y, 0.3), lens=38)
        render(sc, os.path.join(OUT, 'pm_factories_close_row%d.png' % (r + 1)))


def board_raking(mats):
    sc = reset('pm_raking')
    base_scene(sc, view='AgX', samples=16)
    world(sc, (0.02, 0.02, 0.025), 1.0)
    by = {t.split('\n')[0]: m for t, m in mats}
    pick = [('rubber', by['create_rubber()']), ('skin pores', by['create_skin()']),
            ('90s plastic', by['computer_plastic_90s']),
            ('scaly cell 5\n(engine normal map)', PM.create_scaly(cell_size=5, name='pm_scaly_big')),
            ('scaly cell 5\nflip_green=True', PM.create_scaly(cell_size=5, flip_green=True, name='pm_scaly_big_flip'))]
    lm = emit_mat('lbl_r', (0.8, 0.8, 0.8, 1), 0.8)
    for i, (nm, m) in enumerate(pick):
        x = (i - (len(pick) - 1) / 2) * 1.1
        p = plane(sc, 'rk_%d' % i, 1.0, (x, 0, 0.5), rot=(math.radians(90), 0, 0))
        p.data.materials.append(m)
        label(sc, nm, (x, -0.01, -0.12), size=0.075, rot=(math.radians(90), 0, 0), mat=lm)
    ld = bpy.data.lights.new('rake', 'SUN')
    ld.energy = 4.0
    ld.angle = math.radians(1.0)
    sun = bpy.data.objects.new('rake', ld)
    # light from the upper left, 18 degrees off the tiles' plane: raised features light on their upper-left flanks
    from mathutils import Vector
    to_light = Vector((-0.7, -0.31, 0.64)).normalized()
    sun.rotation_euler = (-to_light).to_track_quat('-Z', 'Y').to_euler()
    link(sc, sun)
    camera(sc, (0, -6.6, 0.42), (0, 0, 0.42), lens=40)
    sc.render.resolution_x, sc.render.resolution_y = 960, 270
    render(sc, os.path.join(OUT, 'pm_raking.png'))


def check_factories(mats):
    by = {t.split('\n')[0]: m for t, m in mats}

    def bsdf(m):
        return m.node_tree.nodes['Principled BSDF']

    def linked(m, sock):
        return bsdf(m).inputs[sock].is_linked

    pm = by['create_painted_metal']
    b = bsdf(pm)
    check(abs(b.inputs['Metallic'].default_value - 0.4) < 1e-6 and abs(b.inputs['Roughness'].default_value - 0.3) < 1e-6
          and abs(b.inputs['Coat Weight'].default_value - 0.8) < 1e-6 and linked(pm, 'Coat Roughness'),
          'painted metal: metallic 0.4, roughness 0.3, coat 0.8, coat roughness from the scratch+smudge map')
    rb = by['create_rubber()']
    nm = [n for n in rb.node_tree.nodes if n.bl_idname == 'ShaderNodeNormalMap']
    check(linked(rb, 'Roughness') and nm and abs(nm[0].inputs['Strength'].default_value - 0.3) < 1e-6,
          'rubber: roughness 0.95 x map, normal map at 0.3')
    sk = by['create_skin()']
    b = bsdf(sk)
    check(abs(b.inputs['IOR'].default_value - 1.3) < 1e-6 and abs(b.inputs['Subsurface Weight'].default_value - 0.15)
          < 1e-6 and linked(sk, 'Base Color') and linked(sk, 'Normal'),
          'skin: IOR 1.3, subsurface 0.15 (the engine transmission), colour x variation map, pore normals')
    scl = by['create_scaly()']
    b = bsdf(scl)
    check(abs(b.inputs['Coat Weight'].default_value - 0.3) < 1e-6 and abs(b.inputs['Coat Roughness'].default_value
                                                                          - 0.4) < 1e-6
          and abs(b.inputs['Metallic'].default_value - 0.1) < 1e-6, 'scaly: coat 0.3 / 0.4, metallic 0.1')
    wm = by['create_worn_metal()']
    check(linked(wm, 'Metallic') and linked(wm, 'Roughness') and linked(wm, 'Base Color'),
          'worn metal: colour, roughness and metalness maps wired')
    imgs = [i for i in bpy.data.images if i.get('eido_procedural')]
    check(all(i.packed_file is not None for i in imgs), '%d procedural images, all packed' % len(imgs))
    # a packed image reloads from its packed PNG (what a saved .blend renders from) with the same bytes
    import numpy as np
    img = by['create_scaly()'].node_tree.nodes['Principled BSDF'].inputs['Base Color'].links[0].from_node.image
    before = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
    img.pixels.foreach_get(before)
    img.reload()
    after = np.empty_like(before)
    img.pixels.foreach_get(after)
    check(np.abs(before - after).max() < 1e-6, 'packed image reloads byte-identical (%s, max diff %.2g)'
          % (img.name, float(np.abs(before - after).max())))


def check_fabric_over_scan():
    """createFabric over a fetched scan (its diffuseMap, normalMap, roughnessMap): the scan's roughness multiplied
    by the weave, wear added; and help()"""
    from eidoblend.terrain import find_set, load_set
    try:
        s = load_set(find_set('Fabric023'))
    except Exception as ex:                       # the shared cache may not hold it
        print('SKIP createFabric over a scan: %s' % ex)
        return None
    m = PM.create_fabric(diffuse_map=s['color'], normal_map=s['normal'], roughness_map=s['roughness'],
                         wear={'amount': 0.4}, repeat=(2, 2), name='pm_fabric_scan')
    rough_img = [n for n in m.node_tree.nodes if n.bl_idname == 'ShaderNodeTexImage'
                 and n.image.get('eido_procedural', '').startswith('composite_add')]
    b = m.node_tree.nodes['Principled BSDF']
    check(b.inputs['Base Color'].is_linked and b.inputs['Normal'].is_linked and rough_img
          and tuple(rough_img[0].image.size) == tuple(s['roughness'].size),
          'create_fabric over Fabric023: scan colour x colour, scan normals, scan roughness x weave + wear '
          '(%dx%d, the scan\'s size)' % tuple(rough_img[0].image.size) if rough_img else 'create_fabric over a scan')
    txt = PM.help()
    check('create_painted_metal' in txt and 'computer_plastic_90s' in txt, 'help() prints the reference card')
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        mm = PM.mesh_material(color=0x808080, rougness=0.2, name='pm_typo')
    check("'rougness' is not a property" in buf.getvalue()
          and abs(mm.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value - 1.0) < 1e-6,
          'mesh_material: a misspelt option is ignored with three\'s warning (%s)' % buf.getvalue().strip())
    return m


def main():
    board_generators()
    mats = factory_materials()
    check_factories(mats)
    fab = check_fabric_over_scan()
    if fab is not None:
        mats.append(('create_fabric over\na fetched scan', fab))
    board_factories(mats)
    board_raking(mats)
    print('%s: %d failing' % ('FAIL' if FAILS else 'PASS', len(FAILS)))


main()

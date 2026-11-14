"""createClothPanel's look, ported: the default fabric (no material given) and a graphic handed straight to the panel
(opts.map / opts.texture), riding the folds.

Checks (always, no render):
    material=None gives the engine's default fabric: base colour 0xcccccc in linear, roughness 0.6, metalness 0,
        both faces drawn
    map= a drawing (media.raster.Canvas) becomes a packed sRGB image on the panel's UVMap, times the base colour
        (three's color x map), into Base Color; the drawing's top row lands on the panel's top row and its left
        column on the panel's left as seen from the front (-Y), so text reads
    texture= (the alias) takes an image file path; a bpy Image and a PIL image are taken as they are
    a material passed in gets the map when nothing feeds its Base Color, and keeps its own map when something
        does (three's `!mat.map`); a material with no Principled BSDF refuses a map with a clear error
    unknown options still raise
Render (unless --no-render): a banner with a painted graphic over the default fabric, draped over a ball in a gentle
wind, beside a plain default-fabric panel and a banner on its own material with a file texture:
out/cloth_map_f####.png.

    bash run_blender.sh blender/tests/fx/test_cloth_map.py [-- end=60 frames=1,30,60] [--no-render]
    (a GPU job: 4 GB VRAM, 8 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)
"""

import math
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.fx import cloth as fxcloth          # noqa: E402
from eidoblend.fx._util import color               # noqa: E402
from eidoblend.media import raster                 # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
args = dict(a.split('=', 1) for a in argv if '=' in a)
RENDER = '--no-render' not in argv
END = int(args.get('end', 60))
FRAMES = [int(x) for x in args.get('frames', '1,30,60').split(',')]
OUT = os.path.join(HERE, 'out')
CACHE = os.path.join(OUT, 'cloth_cache')
os.makedirs(OUT, exist_ok=True)
FAILS = []


def check(ok, what):
    print(f"[test_cloth_map] {'PASS' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        FAILS.append(what)


def principled(mat):
    return next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')


def map_node(mat):
    return mat.node_tree.nodes.get('cloth_map')


def banner_art(w=1024, h=512):
    """the graphic: a red band along the top, a word in the middle, a gold marker in the top-left corner"""
    cv = raster.Canvas(w, h, ss=2, background='#16141d')
    W, H = cv.w, cv.h
    cv.draw.rectangle([0, 0, W, int(H * 0.16)], fill='#c8283c')
    cv.draw.rectangle([int(W * 0.03), int(H * 0.03), int(W * 0.10), int(H * 0.13)], fill='#f2c14e')
    cv.text_fit('EIDOVERSE', x=W / 2, y=H * 0.30, max_width=W * 0.86, max_height=H * 0.42, font='Anton', px=260,
                fill='#f4efe6')
    cv.text_fit('cloth that carries its graphic', x=W / 2, y=H * 0.76, max_width=W * 0.8, max_height=H * 0.14,
                font='Share Tech Mono', px=72, fill='#8fd4e8')
    return cv


for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
sc = bpy.context.scene

# ---- the default fabric ------------------------------------------------------------------------------------------
plain = fxcloth.create_cloth_panel(name='plain', cache_dir=CACHE, location=(-3.6, 0.0, 2.2), width=2.0, height=2.0,
                                   cols=24, rows=24, wind=0.0004, wind_bias=0.1, floor=0.0)
m0 = plain.object.active_material
b0 = principled(m0)
lin = color(0xcccccc)
check(m0 is not None and plain.material is m0, 'no material given: the panel has the default fabric')
check(np.allclose(tuple(b0.inputs['Base Color'].default_value)[:3], lin, atol=1e-6) and abs(lin[0] - 0.6038) < 1e-3,
      f'default base colour 0xcccccc in linear ({lin[0]:.4f})')
check(abs(b0.inputs['Roughness'].default_value - 0.6) < 1e-6 and b0.inputs['Metallic'].default_value == 0.0,
      'default roughness 0.6, metalness 0')
check(not m0.use_backface_culling and not b0.inputs['Base Color'].is_linked, 'both faces drawn, no map')

# ---- map=: a drawing on the default fabric --------------------------------------------------------------------------
cv = banner_art()
banner = fxcloth.create_cloth_panel(name='banner', map=cv, cache_dir=CACHE, location=(0.0, 0.0, 2.3), width=3.0,
                                    height=1.5, cols=48, rows=24, wind=0.0004, wind_bias=0.1, floor=0.0)
m1 = banner.object.active_material
b1 = principled(m1)
tex = map_node(m1)
img = tex.image if tex else None
check(tex is not None and img is not None and tuple(img.size) == (1024, 512), 'map= a Canvas: an image of its size')
check(img is not None and img.colorspace_settings.name == 'sRGB' and img.packed_file is not None,
      'the drawing is a packed sRGB image')
mix = b1.inputs['Base Color'].links[0].from_node if b1.inputs['Base Color'].is_linked else None
ins = {s.identifier: s for s in mix.inputs} if mix else {}
check(mix is not None and mix.blend_type == 'MULTIPLY' and ins['B_Color'].links[0].from_node == tex
      and np.allclose(tuple(ins['A_Color'].default_value)[:3], lin, atol=1e-6),
      "Base Color = the fabric's colour x the map (three's color x map)")
uvn = tex.inputs['Vector'].links[0].from_node if tex and tex.inputs['Vector'].is_linked else None
check(uvn is not None and uvn.type == 'UVMAP' and uvn.uv_map == 'UVMap', "the map reads the panel's UVMap")

# orientation: where the panel's top-left vertex samples the image, the drawing's top-left corner is (the gold
# marker); the front faces -Y, so +X is the viewer's right
me = banner.object.data
uv = np.empty(len(me.loops) * 2, np.float32)
me.uv_layers['UVMap'].data.foreach_get('uv', uv)
uv = uv.reshape(-1, 2)
vi = np.empty(len(me.loops), np.int64)
me.loops.foreach_get('vertex_index', vi)
co = np.empty(len(me.vertices) * 3, np.float32)
me.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)
top_left = int(np.argmin(co[:, 0] - co[:, 2]))           # least x, most z
u, v = uv[np.where(vi == top_left)[0][0]]
px = np.array(img.pixels[:], np.float32).reshape(img.size[1], img.size[0], 4)       # row 0 = the image's bottom


def at(u_, v_):
    return px[min(int(v_ * img.size[1]), img.size[1] - 1), min(int(u_ * img.size[0]), img.size[0] - 1), :3]


gold = np.array([0xf2, 0xc1, 0x4e]) / 255.0       # a byte image's pixels are its stored (sRGB) values
red = np.array([0xc8, 0x28, 0x3c]) / 255.0
check(abs(u) < 1e-6 and abs(v - 1.0) < 1e-6, f"the panel's top-left vertex has UV ({u:.2f}, {v:.2f})")
check(np.abs(at(0.065, 0.92) - gold).max() < 0.03 and np.abs(at(0.5, 0.92) - red).max() < 0.03,
      'the drawing lands upright and unmirrored: its top-left marker at UV (0.07, 0.92), the band along the top')

# ---- texture=: the alias, from a file; a bpy Image and a PIL image as they are -------------------------------------
path = os.path.join(OUT, 'cloth_map_texture.png')
raster.save_png(banner_art(512, 256).result(), path)
own = bpy.data.materials.new('own_canvas')
own.use_nodes = True
principled(own).inputs['Base Color'].default_value = (*color('#e8e2d0'), 1.0)
side = fxcloth.create_cloth_panel(name='side_banner', material=own, texture=path, cache_dir=CACHE,
                                  location=(3.6, 0.0, 2.3), width=2.0, height=1.0, cols=32, rows=16, wind=0.0004,
                                  wind_bias=0.1, floor=0.0)
t2 = map_node(own)
check(t2 is not None and os.path.normcase(bpy.path.abspath(t2.image.filepath)) == os.path.normcase(path),
      'texture= an image file path: loaded from that file')
a2 = {s.identifier: s for s in principled(own).inputs['Base Color'].links[0].from_node.inputs}['A_Color']
check(np.allclose(tuple(a2.default_value)[:3], color('#e8e2d0'), atol=1e-6),
      "a material passed in with nothing on its Base Color takes the map, times its own colour")
im3 = bpy.data.images.new('given', 8, 8)
t3 = fxcloth.apply_decal(fxcloth.fabric_material('given_fabric'), im3)
check(t3 is not None and t3.image is im3, 'a bpy Image is used as it is')
t4 = fxcloth.apply_decal(fxcloth.fabric_material('pil_fabric'), cv.result())
check(t4 is not None and tuple(t4.image.size) == (1024, 512), 'a PIL image is taken')

# ---- a material that has its own map keeps it --------------------------------------------------------------------
mapped = bpy.data.materials.new('own_map')
mapped.use_nodes = True
nt = mapped.node_tree
own_tex = nt.nodes.new('ShaderNodeTexChecker')
nt.links.new(own_tex.outputs['Color'], principled(mapped).inputs['Base Color'])
n_links = len(nt.links)
kept = fxcloth.create_cloth_panel(name='kept', material=mapped, map=cv, cache_dir=CACHE, location=(0, 6, 2),
                                  cols=8, rows=8)
check(map_node(mapped) is None and len(nt.links) == n_links and
      principled(mapped).inputs['Base Color'].links[0].from_node == own_tex,
      "a material whose Base Color is already fed keeps its own map (three's !mat.map)")
bpy.data.objects.remove(kept.object, do_unlink=True)

emit = bpy.data.materials.new('emit_only')
emit.use_nodes = True
for n in list(emit.node_tree.nodes):
    if n.type == 'BSDF_PRINCIPLED':
        emit.node_tree.nodes.remove(n)
try:
    fxcloth.create_cloth_panel(name='bad', material=emit, map=cv, cache_dir=CACHE, cols=8, rows=8)
    check(False, 'a material with no Principled BSDF refuses a map')
except ValueError as e:
    check('Principled' in str(e), f'a material with no Principled BSDF refuses a map ({e})')
try:
    fxcloth.create_cloth_panel(name='bad2', cache_dir=CACHE, cols=8, rows=8, mapp=cv)
    check(False, 'an unknown option raises')
except TypeError:
    check(True, 'an unknown option raises')

if RENDER:
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = 960, 540
    sc.render.fps = 30
    sc.frame_start, sc.frame_end = 1, END
    sc.eevee.taa_render_samples = 16
    sc.eevee.use_raytracing = True
    sc.eevee.use_fast_gi = True
    sc.view_settings.view_transform = 'AgX'
    world = bpy.data.worlds.new('sky')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (*color('#8fa6c0'), 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.8
    sc.world = world
    sd = bpy.data.lights.new('sun', 'SUN')
    sd.energy = 3.5
    sd.angle = math.radians(2)
    sun = bpy.data.objects.new('sun', sd)
    sc.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50), 0, math.radians(-25))
    bpy.ops.mesh.primitive_plane_add(size=30)
    fl = bpy.context.active_object
    fm = bpy.data.materials.new('floor')
    fm.use_nodes = True
    principled(fm).inputs['Base Color'].default_value = (*color('#6d6a63'), 1)
    fl.data.materials.append(fm)
    # a ball behind the banner pushes a fold into it; a bar holds each panel's top edge
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.4, location=(0.55, 0.3, 1.9))
    ball = bpy.context.active_object
    for p in ball.data.polygons:
        p.use_smooth = True
    for c in (plain, banner, side):
        w, h = float(c.o['width']), float(c.o['height'])
        x, z = c.object.location.x, c.object.location.z + h / 2 + 0.03
        bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=w + 0.2, location=(x, 0.0, z),
                                            rotation=(0, math.radians(90), 0))
    banner.collide_with([ball], as_sphere=True)
    for c in (plain, banner, side):
        c.settle(60)
        c.bake(1, END)
    cd = bpy.data.cameras.new('cam')
    cd.lens = 30
    cam = bpy.data.objects.new('cam', cd)
    sc.collection.objects.link(cam)
    cam.location = (0.0, -8.6, 2.1)
    cam.rotation_euler = (math.radians(88), 0, 0)
    sc.camera = cam
    for f in FRAMES:
        sc.frame_set(f)
        sc.render.filepath = os.path.join(OUT, f'cloth_map_f{f:04d}.png')
        bpy.ops.render.render(write_still=True)
        print('[test_cloth_map] wrote', sc.render.filepath, flush=True)
print(f'[test_cloth_map] {"FAIL" if FAILS else "PASS"}: {len(FAILS)} failed check(s)')
print('[test_cloth_map] DONE')

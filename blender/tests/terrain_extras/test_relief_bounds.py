"""The relief's bounds (parallax_occlusion.js: silhouetteBounds, sampleBounds, faceBounds) on brick walls, real
displacement (eidoblend.terrain.relief), under raking daylight.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/terrain_extras/test_relief_bounds.py [--no-render]
    (renders are GPU jobs: on a shared machine queue them with EIDO_GPU_WRAP, blender/tests/_where.py)

Walls (3 x 2.4 m, Bricks097, 3 x 2.4 tiles, 3 cm deep), left to right:
  plain                no bounds: the displaced border is the outline (round one's wall)
  silhouette_bounds    [[0.4, 2.6], [0.3, 2.1]]: cut to that UV rectangle; the cut edge shows the bricks' depth
  sample_bounds        [[0, 1.5], [0, 2.4]] alone: past u = 1.5 the border texels continue (streaks)
  sample+silhouette    both on the same region: the tiling relief ends cleanly at u = 1.5
  debug_silhouette     the cut region painted magenta instead of cut
And world-UV merged boxes (an L of two blocks and a step) with face_bounds: one brick course runs across the
blocks' coplanar faces, each face displaces along its own normal, so the outline notches at the corners. And two floor
tiles, silhouette True and False, a 20 cm cube standing at z = 0 on each: both carve inward (the engine's flat SPOM and
its interior POM), so the cubes stand on the peaks; measured from the side in film-transparent renders
(relief_bounds_alpha_floor_*) and shown in relief_bounds_floor_contact.png. Also checked: the engine's hex colours,
face_bounds replacing silhouette_bounds' cut.
Renders: relief_bounds_front.png (the walls straight on), relief_bounds_graze.png (along them, the cut edges'
depth), relief_bounds_boxes.png (the merged boxes' corner), relief_bounds_march.png (debug_march's fract(uv)).
Checks (PASS/FAIL, numeric): the cut walls' alpha clip and shadow mode, the clamp nodes, the face attributes match
each face's UVs, the Edge Split leads the stack, coverage maths against the library's formula at sample UVs.
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / 'terrain'))
sys.path.insert(0, str(HERE.parents[1]))
import _fixture as F  # noqa: E402  (round one's terrain test fixture: clean scene, daylight, camera, render)

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from eidoblend.terrain import find_set, relief  # noqa: E402

OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
RENDER = '--no-render' not in F.args()
FAILS = []


def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok:
        FAILS.append(msg)


F.clean_scene()
F.render_settings(960, 540, 16)
F.test_daylight(sun_elevation=24, sun_azimuth=250)
tex = find_set('Bricks097')

# a floor
bpy.ops.mesh.primitive_plane_add(size=40)
floor = bpy.context.active_object
fm = bpy.data.materials.new('floor')
fm.use_nodes = True
fm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.09, 0.085, 0.08, 1)
fm.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.9
floor.data.materials.append(fm)


def wall(name, x, **kw):
    bpy.ops.mesh.primitive_plane_add(size=1.0)
    w = bpy.context.active_object
    w.name = name
    w.scale = (3.0, 2.4, 1.0)
    bpy.ops.object.transform_apply(scale=True)
    w.rotation_euler.x = math.radians(90)
    w.location = (x, 0.0, 1.2)
    m = relief.create_parallax_material(tex['displacement'], tex['color'], tex['normal'], tex['roughness'],
                                        uv_scale=(3.0, 2.4), tile_metres=1.0, depth_metres=0.03, roughness=0.85,
                                        name=name + '_mat', **kw)
    w.data.materials.append(m)
    relief.subdivide(w, edge=0.008)
    return w, m


walls = [
    ('plain', {}),
    ('silhouette_bounds', {'silhouette_bounds': [[0.4, 2.6], [0.3, 2.1]]}),
    ('sample_bounds', {'sample_bounds': [[0.0, 1.5], [0.0, 2.4]]}),
    ('sample_and_silhouette', {'sample_bounds': [[0.0, 1.5], [0.0, 2.4]],
                               'silhouette_bounds': [[0.0, 1.5], [0.0, 2.4]]}),
    ('debug_silhouette', {'silhouette_bounds': [[0.4, 2.6], [0.3, 2.1]], 'debug_silhouette': True}),
]
made = {}
for i, (nm, kw) in enumerate(walls):
    made[nm] = wall('wall_' + nm, (i - 2) * 3.4, **kw)

# --- checks on the material wiring
m = made['silhouette_bounds'][1]
nodes = m.node_tree.nodes
check(m.surface_render_method == 'DITHERED' and m.use_transparent_shadow
      and any(n.bl_idname == 'ShaderNodeBsdfTransparent' for n in nodes),
      'silhouette_bounds: transparent cut (dithered, alpha 0 or 1) with shadows that follow it')
m = made['sample_bounds'][1]
mins = [n for n in m.node_tree.nodes if n.bl_idname == 'ShaderNodeMath' and n.operation == 'MINIMUM']
check(len(mins) >= 2 and not any(n.bl_idname == 'ShaderNodeBsdfTransparent' for n in m.node_tree.nodes),
      'sample_bounds alone: clamped reads, no cut')
m = made['plain'][1]
check(not any(n.bl_idname == 'ShaderNodeBsdfTransparent' for n in m.node_tree.nodes), 'no bounds: no cut (round one)')


# --- the library call in a custom tree, the legacy hatches, the metalness map, the march options accepted
cm = bpy.data.materials.new('custom_pom')
cm.use_nodes = True
from eidoblend.terrain._nodes import Graph  # noqa: E402
g = Graph(cm.node_tree)
pom = relief.parallax_occlusion_uv(cm.node_tree, tex['displacement'], scale=0.05, silhouette_bounds=[0, 1],
                                   sample_bounds=[[0, 1], [0, 1]], min_layers=16, max_layers=48, min_view_z=0.05,
                                   curved_silhouette=True, curvature=[2 * math.pi / 3, 0], horizon_strength=0.5)
col = pom.sample(relief.load_image(tex['color'], 'color'))
sh = pom.shadow((0.3, 0.2, 0.9))
pb = cm.node_tree.nodes['Principled BSDF']
cm.node_tree.links.new(col, pb.inputs['Base Color'])
check(pom.coverage is not None and pom.missed is not None and col.node.bl_idname == 'ShaderNodeTexImage'
      and sh.node.bl_idname == 'ShaderNodeValue' and abs(sh.default_value - 1.0) < 1e-9,
      'parallax_occlusion_uv: uv, coverage, missed, sample() and shadow() (1: EEVEE shadows the real relief); the '
      'march options are accepted')
lm = relief.create_parallax_material(tex['displacement'], tex['color'], uv_scale=2.0, depth_metres=0.02,
                                     lambert=True, name='lambert_relief')
sl = relief.create_parallax_material(tex['displacement'], tex['color'], uv_scale=2.0, depth_metres=0.02,
                                     self_lit={'sun_dir': (0.5, -0.4, 0.8)}, name='selflit_relief')
mm = relief.create_parallax_material(tex['displacement'], tex['color'], metalness_map=tex['roughness'],
                                     uv_scale=2.0, depth_metres=0.02, min_layers=8, light_dir=(0, 0, 1),
                                     relief_shadow=True, name='metal_relief')


def surface_node(m):
    o = [n for n in m.node_tree.nodes if n.bl_idname == 'ShaderNodeOutputMaterial'][0]
    return o.inputs['Surface'].links[0].from_node.bl_idname


check(surface_node(lm) == 'ShaderNodeBsdfDiffuse' and surface_node(sl) == 'ShaderNodeEmission'
      and mm.node_tree.nodes['Principled BSDF'].inputs['Metallic'].is_linked,
      'lambert -> Diffuse BSDF, self_lit -> hand-lit emission, metalness_map -> Metallic from its red channel')
im = relief.create_parallax_material(tex['displacement'], tex['color'], uv_scale=2.0, inflate=0.05, name='infl')
dl = relief.create_parallax_material(tex['displacement'], tex['color'], uv_scale=2.0, depth_metres=0.02,
                                     debug_march_lit=True, name='march_lit')
dn = [n for n in im.node_tree.nodes if n.bl_idname == 'ShaderNodeDisplacement'][0]
check(abs(im['eido_relief_depth'] - 0.05) < 1e-12 and dn.inputs['Midlevel'].default_value == 0.0
      and surface_node(dl) == 'ShaderNodeBsdfPrincipled',
      'inflate=0.05 (the engine\'s number): outward, 5 cm peaks, floor on the surface; debug_march_lit stays lit')
# the engine's camelCase march options are accepted, ao_map is recorded unwired, an unknown option raises
cc = relief.create_parallax_material(tex['displacement'], tex['color'], uv_scale=2.0, depth_metres=0.02,
                                     minLayers=8, maxLayers=96, curvedSilhouette=True, shadowFloor=0.2,
                                     reliefShadow=True, worldPerTile=[1, 1], reliefWorld=0.02, heightNormal=True,
                                     ao_map=tex.get('ao') or tex['roughness'], name='camel_relief')
try:
    relief.create_parallax_material(tex['displacement'], depth_metres=0.02, silhuette_bounds=[0, 1], name='typo')
    raised = False
except TypeError:
    raised = True
check('eido_ao_map_unwired' in cc and raised,
      'camelCase march options accepted, ao_map recorded unwired, a misspelt option (silhuette_bounds) raises')

# --- the engine's colours, face_bounds replacing the bounds' cut, the inward carve with and without a silhouette
hx = relief.create_parallax_material(tex['displacement'], depth_metres=0.02, color=0x808080, name='hex_relief')
hs = relief.create_parallax_material(tex['displacement'], depth_metres=0.02, color='#808080', name='hexs_relief')
lin = ((0x80 / 255 + 0.055) / 1.055) ** 2.4
cols = [m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value[0] for m in (hx, hs)]
check(all(abs(c - lin) < 1e-5 for c in cols), 'color=0x808080 and \'#808080\' (the engine\'s sRGB hex) -> linear '
      '%.4f (%s)' % (lin, ', '.join('%.4f' % c for c in cols)))
fb = relief.create_parallax_material(tex['displacement'], depth_metres=0.02, face_bounds=True,
                                     silhouette_bounds=[[0.2, 0.8], [0.2, 0.8]], name='fb_relief')
check(not any(n.bl_idname == 'ShaderNodeBsdfTransparent' for n in fb.node_tree.nodes),
      'face_bounds replaces silhouette_bounds\' cut, as the engine\'s libSil = sil && !faceBounds')


def midlevel(m):
    return [n for n in m.node_tree.nodes if n.bl_idname == 'ShaderNodeDisplacement'][0].inputs['Midlevel'].default_value


fl_t = relief.create_parallax_material(tex['displacement'], tex['color'], tex['normal'], uv_scale=1.2,
                                       depth_metres=0.03, silhouette=True, name='floor_sil_true')
fl_f = relief.create_parallax_material(tex['displacement'], tex['color'], tex['normal'], uv_scale=1.2,
                                       depth_metres=0.03, silhouette=False, name='floor_sil_false')
check(abs(midlevel(fl_t) - 1.0) < 1e-6 and abs(midlevel(fl_f) - 1.0) < 1e-6,
      'silhouette False carves inward as True does (Midlevel at the contrast top, 1.0): the peaks on the polygon, '
      'as the engine\'s interior POM')
# two 1.2 m floor tiles with a 20 cm cube standing at z = 0 on each (measured and rendered below), off the main
# floor, over a dark plane 6 cm below them
bpy.ops.mesh.primitive_plane_add(size=5.0, location=(30.75, 0.0, -0.06))
under = bpy.context.active_object
under.name = 'floor_tiles_under'
under.data.materials.append(fm)
tiles = {}
for i, (sil, m_) in enumerate(((True, fl_t), (False, fl_f))):
    bpy.ops.mesh.primitive_plane_add(size=1.2, location=(30.0 + 1.5 * i, 0.0, 0.0))
    t_ = bpy.context.active_object
    t_.name = 'floor_tile_sil_%s' % sil
    t_.data.materials.append(m_)
    relief.subdivide(t_, edge=0.005)
    bpy.ops.mesh.primitive_cube_add(size=0.2, location=(30.0 + 1.5 * i, 0.0, 0.1))
    cb_ = bpy.context.active_object
    cb_.name = 'floor_cube_sil_%s' % sil
    gm = bpy.data.materials.new('cube_grey_%d' % i)
    gm.use_nodes = True
    gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.55, 0.55, 0.55, 1)
    cb_.data.materials.append(gm)
    tiles[sil] = (t_, cb_)

# --- the library's coverage formula, evaluated in Python on the node graph's constants
def coverage(u, v, b, feather=0.02):
    (u0, u1), (v0, v1) = relief._bounds(b)
    over = max(u0 - u, u - u1, v0 - v, v - v1)
    return min(1.0, max(0.0, 1.0 - over / feather))


b = [[0.4, 2.6], [0.3, 2.1]]
samples = [((1.0, 1.0), 1.0), ((0.39, 1.0), 0.5), ((0.37, 1.0), 0.0), ((2.61, 1.0), 0.5), ((1.0, 2.2), 0.0)]
ok = all(abs(coverage(u, v, b) - want) < 1e-9 for (u, v), want in samples)
check(ok, 'coverage = clamp(1 - max(overU, overV) / 0.02): 1 inside, 0.5 at 0.01 outside, 0 past 0.02')

# --- world-UV merged boxes with face bounds (an L of two blocks and a low step), Painted bricks
ptex = find_set('PaintedBricks004')
boxes = [((6.0, 6.0, 1.0), (3.0, 1.2, 2.0)), ((4.9, 7.8, 1.0), (0.8, 2.4, 2.0)), ((6.0, 4.9, 0.2), (3.0, 1.0, 0.4))]
ob = relief.world_uv_boxes(boxes, tile_metres=1.0, name='merged_boxes')
mb = relief.create_parallax_material(ptex['displacement'], ptex['color'], ptex['normal'], ptex['roughness'],
                                     uv_scale=1.0, tile_metres=1.0, depth_metres=0.03, roughness=0.8,
                                     face_bounds=True, name='merged_boxes_mat')
ob.data.materials.append(mb)
md = relief.face_bounds(ob)
relief.subdivide(ob, edge=0.01)
me = ob.data
uvmin = np.empty(len(me.polygons) * 2, dtype=np.float32)
me.attributes['uv_min'].data.foreach_get('vector', uvmin)
uvmax = np.empty(len(me.polygons) * 2, dtype=np.float32)
me.attributes['uv_max'].data.foreach_get('vector', uvmax)
uv = np.empty(len(me.loops) * 2, dtype=np.float32)
me.uv_layers.active.data.foreach_get('uv', uv)
uv = uv.reshape(-1, 2)
good = True
for p in me.polygons:
    s = uv[p.loop_start:p.loop_start + p.loop_total]
    good &= np.allclose(s.min(0), uvmin[2 * p.index:2 * p.index + 2]) and np.allclose(s.max(0),
                                                                                      uvmax[2 * p.index:2 * p.index + 2])
check(good and len(me.polygons) == 18, 'face_bounds: uv_min / uv_max hold each of the 18 faces\' UV rectangle')
check(ob.modifiers[0].type == 'EDGE_SPLIT' and ob.modifiers[1].type == 'SUBSURF' and mb.use_backface_culling,
      'face_bounds: Edge Split leads the stack, then the relief subdivision; back faces culled')
# world UVs: the L's two coplanar faces at y = 5.4 (front of block 1) and the step's top run on one pattern
check(abs(uv[:, 0].max() - uv[:, 0].min()) > 2.0, 'world UVs span the boxes in metres (u range %.2f)'
      % float(uv[:, 0].max() - uv[:, 0].min()))
check([u.name for u in me.uv_layers] == ['UVMap'], 'world_uv_boxes writes its UVs to the layer UVMap (%s)'
      % [u.name for u in me.uv_layers])



def alpha_of(path):
    img = bpy.data.images.load(str(path))
    a = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    out = a.reshape(img.size[1], img.size[0], 4)[..., 3].copy()
    bpy.data.images.remove(img)
    return out


# a lone world-UV cube with the same face-bounds relief, for the corner measurement below (the L's own boxes would
# stand behind its notches)
cube = relief.world_uv_boxes([((14.0, 14.0, 1.0), (2.0, 2.0, 2.0))], tile_metres=1.0, name='face_bounds_cube')
cube.data.materials.append(mb)
relief.face_bounds(cube)
relief.subdivide(cube, edge=0.01)


def measured_renders():
    """The bounds measured IN THE RENDER (EEVEE displaces at render time: the evaluated mesh, and every Python ray,
    still see the flat polygons): film-transparent alpha masks, small, with only the measured object visible."""
    sc = bpy.context.scene
    keep = (sc.render.film_transparent, sc.render.resolution_x, sc.render.resolution_y,
            sc.render.image_settings.color_mode)
    hidden = {o.name: o.hide_render for o in sc.objects}
    sc.render.film_transparent = True
    sc.render.image_settings.color_mode = 'RGBA'

    def only(obj):
        for o in sc.objects:
            if o.type == 'MESH':
                o.hide_render = o is not obj
    only(made['silhouette_bounds'][0])
    # 1. silhouette_bounds [[0.4, 2.6], [0.3, 2.1]] on a 3 x 2.4 wall, straight on: the opaque share of the wall's
    #    rectangle is the bounds' share grown by the library's half feather (coverage 0.5 lies 0.01 UV outside):
    #    (2.22 / 3) x (1.82 / 2.4) = 0.5612
    w = made['silhouette_bounds'][0]
    cd = bpy.data.cameras.new('ortho')
    cd.type = 'ORTHO'
    cd.ortho_scale = 3.0
    cam = bpy.data.objects.new('ortho', cd)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = (w.location.x, -6.0, 1.2)
    cam.rotation_euler = (math.radians(90), 0, 0)
    sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y = 600, 480
    p = OUT / 'relief_bounds_alpha_silhouette.png'
    sc.render.filepath = str(p)
    bpy.ops.render.render(write_still=True)
    a = alpha_of(p)
    share = float((a > 0.5).mean())
    want = (2.22 / 3.0) * (1.82 / 2.4)
    check(abs(share - want) < 0.004, 'silhouette_bounds in the render: %.4f of the wall opaque (the bounds\' share '
          'with the half feather: %.4f)' % (share, want))
    # 2. a face-bounds cube's corner (the edge at x 13, y 15) seen at 45 degrees, displaced (BOTH) against bump only:
    #    the notches are pixels the bump-only outline covers and the displaced one opens
    only(cube)
    cam.data.type = 'PERSP'
    cam.data.lens = 50
    cam.location = (11.6, 16.4, 1.15)
    from mathutils import Vector
    cam.rotation_euler = (Vector((13.0, 15.0, 1.0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.resolution_x, sc.render.resolution_y = 480, 480
    masks = {}
    for meth in ('BUMP', 'BOTH'):
        mb.displacement_method = meth
        p = OUT / ('relief_bounds_alpha_corner_%s.png' % meth.lower())
        sc.render.filepath = str(p)
        bpy.ops.render.render(write_still=True)
        masks[meth] = alpha_of(p) > 0.5
    mb.displacement_method = 'BOTH'
    opened = int((masks['BUMP'] & ~masks['BOTH']).sum())
    grown = int((~masks['BUMP'] & masks['BOTH']).sum())
    check(opened > 50 and grown < opened / 4,
          'face_bounds in the render: the displaced corner opens %d pixels the bump-only outline covers (the '
          'notches), and adds %d' % (opened, grown))
    # 3. each floor tile alone from the side (orthographic, 0.3 m across 480 px): the topmost opaque row is the
    #    relief's peak, the lowest its deepest well: peaks on the polygon (z 0) with silhouette True and False alike
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = 0.3
    sc.render.resolution_x, sc.render.resolution_y = 480, 480
    px = 0.3 / 480
    for sil, (t_, _c) in tiles.items():
        only(t_)
        cam.location = (t_.location.x, -4.0, 0.0)
        cam.rotation_euler = (math.radians(90), 0, 0)
        p = OUT / ('relief_bounds_alpha_floor_silhouette_%s.png' % str(sil).lower())
        sc.render.filepath = str(p)
        bpy.ops.render.render(write_still=True)
        rows = np.nonzero((alpha_of(p) > 0.5).any(axis=1))[0]          # Blender's rows run bottom-up
        z_top = -0.15 + (rows.max() + 0.5) * px if len(rows) else float('nan')
        z_low = -0.15 + (rows.min() + 0.5) * px if len(rows) else float('nan')
        check(abs(z_top) < 0.0015 and -0.03 < z_low < -0.015,
              'silhouette %s in the render: the floor relief\'s peaks at %+.1f mm, its wells down to %+.1f mm '
              '(a cube on the polygon stands on the peaks)' % (sil, z_top * 1000, z_low * 1000))
    bpy.data.objects.remove(cam)
    for o in sc.objects:
        o.hide_render = hidden.get(o.name, o.hide_render)
    cube.hide_render = True
    (sc.render.film_transparent, sc.render.resolution_x, sc.render.resolution_y,
     sc.render.image_settings.color_mode) = keep


# --- renders: each bound in a close view, raking daylight, then one labelled sheet
if RENDER:
    measured_renders()
    shots = []

    def shot(tag, label, loc, look, lens):
        cam = F.camera(tag, loc, look, lens=lens)
        p = OUT / ('relief_bounds_%s.png' % tag)
        F.render(cam, p)
        shots.append((p, label))

    X = {nm: (i - 2) * 3.4 for i, (nm, _kw) in enumerate(walls)}
    shot('row', 'the five walls: plain | silhouette_bounds | sample_bounds | sample+silhouette | debug_silhouette',
         (9.0, -6.5, 2.6), (-0.6, 0.0, 1.1), 28)
    xs = X['silhouette_bounds']
    shot('silhouette', 'silhouette_bounds [[0.4, 2.6], [0.3, 2.1]]: the cut edge shows the bricks\' depth',
         (xs + 2.3, -1.9, 2.5), (xs + 1.0, 0.0, 1.75), 32)
    xs = X['sample_bounds']
    shot('sample', 'sample_bounds [[0, 1.5], [0, 2.4]] alone: past u = 1.5 the border texels continue',
         (xs + 0.2, -3.6, 1.3), (xs + 0.2, 0.0, 1.2), 35)
    xs = X['sample_and_silhouette']
    shot('sample_cut', 'sample_bounds + silhouette_bounds: the relief ends cleanly at u = 1.5',
         (xs + 1.5, -2.2, 1.9), (xs - 0.1, 0.0, 1.3), 32)
    xs = X['debug_silhouette']
    shot('debug', 'debug_silhouette: the cut region painted magenta', (xs, -4.6, 1.25), (xs, 0.0, 1.2), 32)
    shot('boxes', 'face_bounds on world-UV merged boxes: one brick course across coplanar faces, notched corners',
         (2.9, 2.4, 2.7), (5.0, 6.6, 1.0), 30)
    shot('boxes_corner', 'face_bounds: the L\'s outer corner close, against the sky', (3.6, 9.9, 1.0),
         (4.55, 9.0, 1.15), 45)
    shot('floor_contact', 'floor tiles, silhouette True (left) and False (right): the cubes stand on the peaks',
         (30.75, -2.1, 0.16), (30.75, 0.0, 0.0), 35)
    # debug_march on the plain wall
    dm = relief.create_parallax_material(tex['displacement'], tex['color'], tex['normal'], uv_scale=(3.0, 2.4),
                                         depth_metres=0.03, debug_march=True, name='debug_march')
    made['plain'][0].data.materials[0] = dm
    xs = X['plain']
    shot('march', 'debug_march: fract(uv) unlit (red u, green v)', (xs, -4.6, 1.25), (xs, 0.0, 1.2), 32)
    for p, _l in shots:
        check(p.exists(), 'rendered %s' % p.name)
    try:
        from PIL import Image, ImageDraw
        cols, tw, th = 2, 960, 540
        rows = (len(shots) + cols - 1) // cols
        S = Image.new('RGB', (cols * tw, rows * (th + 24)), (14, 16, 20))
        dr = ImageDraw.Draw(S)
        for i, (p, lab) in enumerate(shots):
            r, c = divmod(i, cols)
            if p.exists():
                S.paste(Image.open(p).convert('RGB'), (c * tw, r * (th + 24)))
            dr.text((c * tw + 8, r * (th + 24) + th + 5), lab, fill=(225, 225, 225))
        S.save(OUT / 'relief_bounds_sheet.png')
    except ImportError as ex:
        print('no sheet (%s)' % ex)
print('%s: %d failing' % ('FAIL' if FAILS else 'PASS', len(FAILS)))

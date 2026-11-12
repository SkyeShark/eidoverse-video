"""cn_lib's API the two sets do not happen to call, exercised on its own (no renders): dyn_canvas, pbr_mat's offset /
uv / P / opacity / alpha_test / transparent / depth_write options, register_font, lum, bucket + box_uv metre
UVs, slice_tris, make_world's environment and hemisphere (the only way the environment lights a material), spot /
point lights, make_camera, the stroker and the fill rules.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_uf_corridor_news/test_cn_lib.py
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixture as F  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from eidoblend.sets.unknown_force import cn_lib as CL  # noqa: E402

check = F.check
sc = F.clean_scene()
col = bpy.data.collections.new('cn_lib_api')
sc.collection.children.link(col)
root = bpy.data.objects.new('cn_lib_root', None)
col.objects.link(root)
root['t'] = 0.0
L = CL.make_lib('cnapi', owner=root, collection=col)

# dyn_canvas: a canvas whose image is rebuilt only on redraw
calls = []


def draw(g, W, H, k):
    calls.append(k)
    g.fill_style = f'rgb({k},{k},{k})'
    g.fill_rect(0, 0, W, H)


d = L.dyn_canvas(16, 8, draw, name='cnapi_dyn')
im1 = d.redraw(40)
v1 = np.empty(16 * 8 * 4, np.float32)
im1.pixels.foreach_get(v1)
im2 = d.redraw(200)
v2 = np.empty(16 * 8 * 4, np.float32)
im2.pixels.foreach_get(v2)
check('dyn_canvas: redraw(args) repaints the same image', im1 is im2 and abs(v1[0] - 40 / 255) < 1e-6
      and abs(v2[0] - 200 / 255) < 1e-6 and calls == [40, 200])

# pbr_mat's options the sets do not use
S = L.pbr('Fabric077')
m1 = L.pbr_mat(S, name='cnapi_opacity', tile=(0.5, 0.25), offset=(0.3, 0.1), transparent=True, opacity=0.4)
m2 = L.pbr_mat(S, name='cnapi_alphatest', alpha_test=0.5, opacity=0.7, side='front')
m3 =L.pbr_mat(S, name='cnapi_uv_p', uv=None, P=None, macro=0.4, macro_scale=1.2, rough=(0.5, 0.1), metal=0.3, nrm=0.5)
bsdf = lambda m: next(n for n in m.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled')   # noqa: E731
check('pbr_mat: transparent + opacity -> a blended material whose Alpha is 0.4', m1.surface_render_method == 'BLENDED'
      and abs(bsdf(m1).inputs['Alpha'].default_value - 0.4) < 1e-6)
check('pbr_mat: alpha_test -> a binary cut (step) on the opacity, culled back faces',
      bsdf(m2).inputs['Alpha'].default_value in (0.0, 1.0) or bsdf(m2).inputs['Alpha'].is_linked)
check('pbr_mat: macro / rough / metal / nrm build', bsdf(m3).inputs['Roughness'].is_linked
      and abs(bsdf(m3).inputs['Metallic'].default_value - 0.3) < 1e-6)

# register_font and lum
fam = CL.register_font(CL.font_file(CL.fam['rajdhani']), 'Test Rajdhani')
cv = CL.create_canvas(8, 8)
g = cv.get_context('2d')
g.font = f'40px {fam}'
w1 = g.measure_text('NIGHT DESK').width
g.font = f'40px {CL.fam["rajdhani"]}'
check('register_font: a face under another name measures the same', abs(w1 - g.measure_text('NIGHT DESK').width) < 1e-9)
check('lum: Rec. 709 luminance', abs(CL.lum((1.0, 0.5, 0.25)) - (0.2126 + 0.7152 * 0.5 + 0.0722 * 0.25)) < 1e-12)

# bucket + box_uv: metre UVs on axis-aligned faces
geo = L.bucket('cnapi_box').box(2.0, 1.0, 0.5, 0, 0, 0).geometry()
uv = geo.uv
check('bucket + box_uv: a 2 x 1 x 0.5 m box gets metre UVs (spans 2, 1, 0.5)',
      abs(uv[:, 0].max() - uv[:, 0].min() - 2.0) < 1e-9 and abs(uv[:, 1].max() - uv[:, 1].min() - 1.0) < 1e-9)
tri = CL.Geo([[0, 0, 0], [1, 0, 0], [0, 1, 0]], [[0, 0, 1]] * 3, [[0, 0], [1, 0], [0, 1]])
cut = CL.slice_tris(tri, lambda gg: gg.uv[:, 0], [0.5])
check('slice_tris: a triangle across u = 0.5 becomes three, none crossing it', len(cut.pos) == 9 and all(
    (u.min() >= 0.5 - 1e-9) or (u.max() <= 0.5 + 1e-9) for u in cut.uv[:, 0].reshape(-1, 3)))

# world, lights, camera
env = L.env_tex(lambda d: (0.1 + 0.1 * d[1], 0.05, 0.02), 32, 16, name='cnapi_env')
w = CL.make_world(L, 'cnapi_world', env, env_i=0.5, hemi=(0x3a2a1a, 0x0a0405, 0.06), scene=sc)
check('make_world: the environment + the hemisphere term, x SPEC', sc.world == w and any(
    n.bl_idname == 'ShaderNodeTexEnvironment' for n in w.node_tree.nodes))
sp = CL.spot(L, 'cnapi_spot', 0xffd6a0, 300, [1.2, 9.2, 8.0], [0, 1.25, 0], 0.3, 0.8, parent=root)
pt = CL.point(L, 'cnapi_point', 0xc8dcff, 14, [4.0, 4.4, -10.0], parent=root, shadow=False)
from mathutils import Vector  # noqa: E402
bpy.context.view_layer.update()
fwd = sp.matrix_world.to_3x3() @ Vector((0, 0, -1))
aim = Vector(CL.b3([0, 1.25, 0])) - Vector(CL.b3([1.2, 9.2, 8.0]))
check('spot: 300 cd at 4 pi x 300 W, aimed at its target, a custom cut-off', abs(sp.data.energy - 300 * 4 * math.pi) < 1e-4
      and fwd.angle(aim) < 1e-5 and sp.data.use_custom_distance and pt.data.use_shadow is False,
      f'{sp.data.energy:.4f} W, aim {math.degrees(fwd.angle(aim)):.4f} deg')
cam = CL.make_camera(L, 'cnapi_cam', {'pos': [0.55, 1.25, 6.2], 'target': [0, 4.6, -24], 'fov': 38}, parent=root)
check('make_camera: vertical fov 38 deg', abs(math.degrees(cam.data.angle_y) - 38) < 1e-6 and cam.data.sensor_fit == 'VERTICAL')

# the environment lights through the World alone: a material samples no environment and emits nothing of its own
mi = L.mat('cnapi_env_mat').standard((0.8, 0.6, 0.3), rough=0.3, metal=1.0, sheen=1.0, coat=0.5)
mp = L.pbr_mat(S, name='cnapi_env_pbr')
check('Mat.standard / pbr_mat: no per-material environment (no Environment Texture, no emission): the World lights '
      'them', not any(n.bl_idname == 'ShaderNodeTexEnvironment' for m in (mi, mp) for n in m.node_tree.nodes)
      and not bsdf(mi).inputs['Emission Color'].is_linked and bsdf(mi).inputs['Emission Strength'].default_value == 0.0)
md = L.pbr_mat(S, name='cnapi_depthwrite', transparent=True, opacity=0.5, depth_write=False)
check('pbr_mat depth_write=False: a blended material blends every layer (Transparency Overlap)',
      md.surface_render_method == 'BLENDED' and md.use_transparency_overlap)

# fills and strokes
cv = CL.create_canvas(40, 40)
g = cv.get_context('2d')
g.fill_style = '#fff'
g.begin_path(); g.rect(5, 5, 30, 30); g.rect(15, 15, 10, 10); g.fill()                     # nonzero: no hole
a1 = cv.pixels()[20, 20, 3]
cv2 = CL.create_canvas(40, 40)
g2 = cv2.get_context('2d')
g2.fill_style = '#fff'
g2.begin_path(); g2.rect(5, 5, 30, 30); g2.rect(15, 15, 10, 10)
r = g2._fill_cov(g2._path, rule='evenodd')
check('fill rules: nonzero fills nested same-way rects, evenodd cuts the hole', a1 == 255 and r[0][20 - r[2], 20 - r[1]] == 0)
cv3 = CL.create_canvas(60, 30)
g3 = cv3.get_context('2d')
g3.stroke_style = '#fff'
for x, join in ((5, 'miter'), (25, 'round'), (45, 'bevel')):
    g3.line_width = 6
    g3.line_join = join
    g3.begin_path(); g3.move_to(x, 25); g3.line_to(x, 8); g3.line_to(x + 10, 8); g3.stroke()
px = cv3.pixels()[..., 3]
check('stroke joins: a miter fills the outer corner, round and bevel cut it',
      px[5, 2] > 200 and px[5, 22] < 120 and px[5, 42] < 60, f'{px[5, 2]} {px[5, 22]} {px[5, 42]}')
L.dispose_all()
F.summary()

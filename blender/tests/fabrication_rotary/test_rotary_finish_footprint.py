"""The rotary stock's pattern fades against the WebGPU's fwidth(phase), measured in a render.

The WebGPU finishStock faded the growth rings, the wood fibre and the metal brushing by fwidth(phase): the phase's
change from one pixel to the next on screen. stock.filter_finish computes that derivative from each pattern's 3D
gradient and the pixel's footprint on the surface. This renders the finished sample part (wood, and an aluminium copy
below it) from the examples' camera distance with AOVs of each pattern's phase, the exact fwidth and finish_stock's
own estimate (footprint x frequency), then takes the phase image's real pixel differences |dP/dx| + |dP/dy| (what
fwidth is) and compares. Prints PASS / FAIL and the distributions; writes out/footprint/ (the AOVs, a beauty frame).

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/fabrication_rotary/test_rotary_finish_footprint.py
"""

import math
import os
import shutil
import sys

import bpy
import numpy as np
from mathutils import Vector

sys.dont_write_bytecode = True                  # no __pycache__ in the repository
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.characters.robotics.studio import make_camera  # noqa: E402
from eidoblend.fabrication.cutting import stock_material, stock_profile  # noqa: E402
from eidoblend.fabrication.rotary import (create_rotary_stock, filter_finish, rotary_program,  # noqa: E402
                                          sample_rotary, swizzle_finish)
from eidoblend.fabrication.rotary.stock import FOOTPRINT_NODE  # noqa: E402

OUT = os.path.join(HERE, 'out', 'footprint')
shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT, exist_ok=True)
W, H = 640, 450
FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  ' + detail) if detail else ''), flush=True)
    if not ok:
        FAILS.append(name)


def math_node(nt, op, a, b):
    n = nt.nodes.new('ShaderNodeMath')
    n.operation = op
    for i, v in enumerate((a, b)):
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = v
        else:
            nt.links.new(v, n.inputs[i])
    return n.outputs[0]


def mult_by(node, k):
    """a Math MULTIPLY by the constant k (sockets hold float32: 1.4 is stored as 1.39999998)"""
    return node.type == 'MATH' and node.operation == 'MULTIPLY' and not node.inputs[1].is_linked \
        and abs(node.inputs[1].default_value - k) <= 1e-6 * max(1.0, abs(k))


def phase_and_fades(nt, k):
    """(the pattern's phase socket, the exact fwidth socket, finish_stock's estimate socket) for frequency k: finish_stock
    builds rings = radial * 4200 + broad * 2.8, fibre = (px + warp) * 18000, brushing = pz * 83000 + sin(px * 270) * .7;
    filter_finish feeds its fade MULTIPLY(., k) with fwidth * (1 / k)"""
    phase = exact = None
    for n in nt.nodes:
        if not mult_by(n, k) or not n.inputs[0].is_linked:
            continue
        src = n.inputs[0].links[0].from_node
        if mult_by(src, 1.0 / k):
            exact = n.outputs[0]                       # filter_finish's fwidth / k, times k again
        elif k == 18000.0:
            phase = n.outputs[0]
        else:
            phase = [lk.to_node for lk in nt.links if lk.from_node == n][0].outputs[0]       # the sum it starts
    pix = nt.nodes['pixel_angle']
    fp = [lk2.to_node for lk in nt.links if lk.from_node == pix
          for lk2 in nt.links if lk2.from_node == lk.to_node and mult_by(lk2.to_node, 1.4)][0]
    return phase, exact, math_node(nt, 'MULTIPLY', fp.outputs[0], k)


def aov(nt, name, sockets):
    comb = nt.nodes.new('ShaderNodeCombineXYZ')
    for i, s in enumerate(sockets):
        nt.links.new(s, comb.inputs[i])
    out = nt.nodes.new('ShaderNodeOutputAOV')
    out.aov_name = name
    nt.links.new(comb.outputs[0], out.inputs['Color'])


# ------------------------------------------------------------------------------------------------ the parts ---
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
program = rotary_program(sample_rotary, material='wood', tool='flat')
frame = bpy.data.objects.new('Rotary stock frame', None)
sc.collection.objects.link(frame)
cam = make_camera(36, 'footprint camera', sc)
eye = Vector((-.325, -.48, .22))                  # the examples' camera, relative to the stock's centre
cam.location = eye
cam.rotation_quaternion = (-eye).to_track_quat('-Z', 'Y')
cam.data.clip_start, cam.data.clip_end = .035, 10.0
sc.camera = cam
bpy.context.view_layer.update()
stock = create_rotary_stock(program.path, program.settings, parent=frame, resolution=(192, 72, 72),
                            cache_dir=os.path.join(OUT, 'cache'))
stock.update(program.path.sample(program.path.duration))
stock.write_frame(1)
wood = stock.material
check('wood: filter_finish rerouted 2 fades (growth rings, fibre) and marked the material',
      stock.footprint_fades == 2 and FOOTPRINT_NODE in wood.node_tree.nodes)
alu, _f = stock_material('aluminium part', stock_profile('aluminum'))
swizzle_finish(alu)
n_alu = filter_finish(alu)
check('aluminium: 1 fade (brushing); filtering again changes nothing', n_alu == 1 and filter_finish(alu) == 0)
metal = stock.to_mesh('aluminium copy')
metal.data.materials.clear()
metal.data.materials.append(alu)
metal.parent = frame
metal.matrix_parent_inverse.identity()
metal.location = (0, 0, -.062)

# ------------------------------------------------------------------------------------------- the AOVs ---
vl = sc.view_layers[0]
for name in ('rot_rings', 'rot_fibre', 'rot_brush'):
    a = vl.aovs.add()
    a.name, a.type = name, 'COLOR'
nt = wood.node_tree
aov(nt, 'rot_rings', phase_and_fades(nt, 4200.0))
aov(nt, 'rot_fibre', phase_and_fades(nt, 18000.0))
aov(alu.node_tree, 'rot_brush', phase_and_fades(alu.node_tree, 83000.0))
sc.eevee.taa_render_samples = 4
sc.render.filter_size = 0.5
ctree = bpy.data.node_groups.new('rotary footprint comp', 'CompositorNodeTree')
sc.compositing_node_group = ctree
rl = ctree.nodes.new('CompositorNodeRLayers')
fo = ctree.nodes.new('CompositorNodeOutputFile')
fo.directory = OUT + '/'
fo.file_name = 'aov_####_'
fo.save_as_render = False
fo.format.media_type = 'IMAGE'
fo.format.file_format = 'OPEN_EXR'
fo.format.color_depth = '32'
for name in ('rot_rings', 'rot_fibre', 'rot_brush'):
    fo.file_output_items.new('RGBA', name)
    ctree.links.new(rl.outputs[name], fo.inputs[name])
sc.render.image_settings.media_type = 'IMAGE'
sc.render.image_settings.file_format = 'PNG'
sc.render.filepath = os.path.join(OUT, 'footprint_beauty.png')
sc.frame_set(1)
bpy.ops.render.render(write_still=True)


def load(name):
    hits = sorted(f for f in os.listdir(OUT) if f.startswith('aov_') and name in f and f.endswith('.exr'))
    if not hits:
        return None
    img = bpy.data.images.load(os.path.join(OUT, hits[0]))
    px = np.empty(W * H * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(H, W, 4)[::-1].astype(np.float64)


print('written:', sorted(os.listdir(OUT)), flush=True)
for name, label, fade in (('rot_rings', 'growth rings', .28), ('rot_fibre', 'wood fibre', .3),
                          ('rot_brush', 'metal brushing', .25)):
    a = load(name)
    if a is None:
        check(f'{label}: AOV written', False)
        continue
    phase, exact, old = a[..., 0], a[..., 1], a[..., 2]
    on = np.abs(phase) > 1e-3
    inner = on.copy()                                  # two pixels clear of every silhouette
    for dy in (-2, -1, 0, 1, 2):
        for dx in (-2, -1, 0, 1, 2):
            inner &= np.roll(np.roll(on, dy, 0), dx, 1)
    fd = np.abs(np.roll(phase, -1, 1) - phase) + np.abs(np.roll(phase, -1, 0) - phase)
    ok = inner & (fd > 1e-3)
    ok[-2:, :] = ok[:, -2:] = False
    r_exact, r_old = exact[ok] / fd[ok], old[ok] / fd[ok]
    p_e = np.percentile(r_exact, (10, 50, 90))
    p_o = np.percentile(r_old, (10, 50, 90))
    within = np.mean(np.abs(r_exact - 1) < .25)
    fade_true = 1 - np.clip(fd[ok] * fade, 0, 1)
    fade_exact = 1 - np.clip(exact[ok] * fade, 0, 1)
    fade_old = 1 - np.clip(old[ok] * fade, 0, 1)
    print(f'{label}: {ok.sum()} pixels; exact / measured fwidth p10 {p_e[0]:.3f} p50 {p_e[1]:.3f} p90 {p_e[2]:.3f}; '
          f'finish_stock estimate / measured p10 {p_o[0]:.2f} p50 {p_o[1]:.2f} p90 {p_o[2]:.2f}; mean fade (pattern '
          f'kept) measured {fade_true.mean():.3f}, exact {fade_exact.mean():.3f}, estimate {fade_old.mean():.3f}',
          flush=True)
    check(f'{label}: the exact fwidth matches the rendered phase\'s pixel differences (median within 10 %, 75 % of '
          'pixels within 25 %)', ok.sum() > 2000 and abs(p_e[1] - 1) < .10 and within > .75,
          f'median {p_e[1]:.3f}, {within * 100:.1f} % within 25 %')
    check(f'{label}: so the pattern keeps the share of its contrast the WebGPU kept (mean fade within 0.05)',
          abs(fade_exact.mean() - fade_true.mean()) < .05,
          f'{fade_exact.mean():.3f} vs {fade_true.mean():.3f} (finish_stock\'s estimate: {fade_old.mean():.3f})')
print('\n%d FAIL' % len(FAILS) if FAILS else '\nALL PASS')

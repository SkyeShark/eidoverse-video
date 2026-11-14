"""materials.js's mirrored-normal-map parity, probed in EEVEE.

The WebGPU runtime flips normalScale.y for an object whose world matrix has a negative determinant, so a reflected kit
module (the humanoid's left side, a child re-attached under a mirrored parent) shades like its source; the rule is
"never reflect normal-map green or tangent.w to compensate". Blender's Normal Map node is meant to do the same through
the tangent space's sign. This measures it, with EEVEE's world-space Normal pass (1 sample, orthographic front view):

    A   the A650 arm as loaded
    B   the same arm mirrored (its empty scaled -1 in X): its image must be A's, flipped left-right, with every normal's X
        negated. The mean angle between B and mirror(A) over the arm's interior pixels is the parity error.
    G   B again with every kit normal map's green channel inverted (the compensation the rule forbids): if Blender did
        NOT handle the parity, G would be the one that matches mirror(A)
    F   A with every normal map's strength 0: how much the maps move the normals at all (the signal the error is
        compared with)

PASS: error(B) is a small fraction of the signal, and error(G) is larger than error(B). Also renders the beauty of A
and B side by side in the studio light (out/normal_parity_beauty.png) and writes out/normal_parity.json.

    bash run_blender.sh blender/tests/robotics/test_normal_parity.py
    # a GPU job; on a shared machine queue it with EIDO_GPU_WRAP (blender/tests/_where.py)
"""

import glob
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _rk as K  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from eidoblend.characters.robotics import make_robot, studio  # noqa: E402
from eidoblend.characters.robotics.studio import world_box  # noqa: E402

TMP = os.path.join(K.OUT, '_normal_parity')
os.makedirs(TMP, exist_ok=True)
RES = 512


def normal_pass_setup(sc):
    for vl in sc.view_layers:
        vl.use_pass_normal = True
    sc.render.use_compositing = True
    tree = bpy.data.node_groups.new('normal parity', 'CompositorNodeTree')
    sc.compositing_node_group = tree
    rl = tree.nodes.new('CompositorNodeRLayers')
    fo = tree.nodes.new('CompositorNodeOutputFile')
    fo.directory = TMP
    fo.file_name = 'n'
    fo.save_as_render = False
    fo.format.media_type = 'MULTI_LAYER_IMAGE'
    fo.format.file_format = 'OPEN_EXR_MULTILAYER'
    fo.format.color_depth = '32'
    fo.file_output_items.new('VECTOR', 'Normal')
    tree.links.new(rl.outputs['Normal'], fo.inputs['Normal'])


def read_exr(prefix, chans):
    import OpenImageIO as oiio
    f = sorted(glob.glob(os.path.join(TMP, prefix + '*.exr')))[-1]
    buf = oiio.ImageBuf(f)
    names = list(buf.spec().channelnames)
    px = np.asarray(buf.get_pixels(oiio.FLOAT)).reshape(buf.spec().height, buf.spec().width, -1)
    idx = [next(i for i, n in enumerate(names) if n.split('.')[-1].upper() == c) for c in chans]
    return px[..., idx]


def render_normals(sc, cam, tag):
    for old in glob.glob(os.path.join(TMP, '*')):
        os.remove(old)
    sc.render.filepath = os.path.join(TMP, tag + '_beauty.png')
    sc.camera = cam
    bpy.ops.render.render(write_still=False)
    return read_exr('n', 'XYZ')


def set_maps(materials, invert_green=False, strength=None):
    for m in materials:
        nt = m.node_tree
        for nm in [n for n in nt.nodes if n.type == 'NORMAL_MAP']:
            if strength is not None:
                nm.inputs['Strength'].default_value = strength
            if invert_green:
                link = nm.inputs['Color'].links[0] if nm.inputs['Color'].is_linked else None
                if link is None:
                    continue
                src = link.from_socket
                sep = nt.nodes.new('ShaderNodeSeparateColor')
                inv = nt.nodes.new('ShaderNodeMath')
                inv.operation = 'SUBTRACT'
                inv.inputs[0].default_value = 1.0
                comb = nt.nodes.new('ShaderNodeCombineColor')
                nt.links.new(src, sep.inputs['Color'])
                nt.links.new(sep.outputs['Red'], comb.inputs['Red'])
                nt.links.new(sep.outputs['Green'], inv.inputs[1])
                nt.links.new(inv.outputs[0], comb.inputs['Green'])
                nt.links.new(sep.outputs['Blue'], comb.inputs['Blue'])
                nt.links.new(comb.outputs['Color'], nm.inputs['Color'])


def angle_stats(n1, n2, mask):
    a = np.einsum('ijk,ijk->ij', n1, n2)
    l1 = np.linalg.norm(n1, axis=2)
    l2 = np.linalg.norm(n2, axis=2)
    cosv = np.clip(a / np.maximum(l1 * l2, 1e-9), -1, 1)
    ang = np.degrees(np.arccos(cosv))[mask]
    return float(ang.mean()), float(np.percentile(ang, 95))


def main():
    sc = K.clean_scene()
    K.probe_render(sc, (RES, RES), 1)
    sc.eevee.use_raytracing = False
    sc.render.filter_size = 0.01
    studio(sc, grid=False)
    normal_pass_setup(sc)
    arm = make_robot('arm', scene=sc)
    arm.joints([0.3, 0.5, -0.6, 0.4, 0.8, 0.2])
    lo, hi = world_box([arm.group])
    cd = bpy.data.cameras.new('ortho')
    cd.type = 'ORTHO'
    # the camera stays on x = 0 (so mirroring the arm in X mirrors its image), framed tight on the arm and its mirror
    cd.ortho_scale = max(2 * max(abs(lo.x), abs(hi.x)), hi.z - lo.z) * 1.08
    cam = bpy.data.objects.new('ortho', cd)
    sc.collection.objects.link(cam)
    cam.location = (0.0, -4.0, (lo.z + hi.z) / 2)
    cam.rotation_euler = (math.pi / 2, 0, 0)
    mats = arm.materials.materials
    nA = render_normals(sc, cam, 'A')
    arm.group.scale = (-1, 1, 1)
    bpy.context.view_layer.update()
    nB = render_normals(sc, cam, 'B')
    set_maps(mats, invert_green=True)
    nG = render_normals(sc, cam, 'G')
    arm.group.scale = (1, 1, 1)
    set_maps(mats, strength=0.0)
    nF = render_normals(sc, cam, 'F')
    mirA = nA[:, ::-1].copy()
    mirA[..., 0] *= -1
    cover = (np.linalg.norm(nA, axis=2) > 0.5) & (np.linalg.norm(nB, axis=2) > 0.5)
    from numpy.lib.stride_tricks import sliding_window_view
    pad = np.pad(cover, 2, constant_values=False)
    interior = sliding_window_view(pad, (5, 5)).all(axis=(2, 3))
    eB, pB = angle_stats(nB, mirA, interior)
    eG, pG = angle_stats(nG, mirA, interior)
    sig, psig = angle_stats(nA, nF, interior)
    print(f'[normal_parity] pixels {int(interior.sum())}; mirrored B vs mirror(A): mean {eB:.3f} deg (p95 {pB:.3f}); '
          f'green-inverted G: mean {eG:.3f} deg (p95 {pG:.3f}); map signal A vs no-map F: mean {sig:.3f} (p95 {psig:.3f})',
          flush=True)
    K.check('the arm covers the frame', interior.sum() > 5000, f'{int(interior.sum())} interior pixels')
    K.check('mirrored instance shades like its source (Blender handles the tangent parity)', eB < 0.25 * sig and eB < eG,
            f'error {eB:.3f} deg vs map signal {sig:.3f} deg, green-inverted {eG:.3f} deg')
    K.check('inverting normal-map green on the mirrored instance makes it worse (the rule holds in Blender)', eG > eB,
            f'{eG:.3f} > {eB:.3f}')
    # the beauty, side by side, in the studio light (the camera's view of A and of B)
    set_maps(mats, strength=1.0)
    for m in mats:                                    # undo the green inversion: reconnect the image to the map
        nt = m.node_tree
        for nm in [n for n in nt.nodes if n.type == 'NORMAL_MAP']:
            comb = nm.inputs['Color'].links[0].from_node if nm.inputs['Color'].is_linked else None
            if comb is not None and comb.type == 'COMBINE_COLOR':
                sep = comb.inputs['Red'].links[0].from_node
                src = sep.inputs['Color'].links[0].from_socket
                nt.links.new(src, nm.inputs['Color'])
    sc.compositing_node_group = None
    sc.render.use_compositing = False
    K.probe_render(sc, (RES, RES), 16)
    shots = []
    for tag, sx in (('A', 1), ('B', -1)):
        arm.group.scale = (sx, 1, 1)
        p = os.path.join(K.OUT, f'normal_parity_beauty_{tag}.png')
        K.still(sc, cam, 1, p)
        shots.append(p)
    K.save_results('normal_parity', {'mean_deg': {'mirrored': eB, 'green_inverted': eG, 'map_signal': sig},
                                     'p95_deg': {'mirrored': pB, 'green_inverted': pG, 'map_signal': psig},
                                     'beauty': shots})


main()

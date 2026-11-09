"""create_particles_compose checked by numbers: flat additive quads (emission over a transparent BSDF, BLENDED, the
way the sprites are drawn) of known linear radiance over black, rendered under AgX with the display match, must show
the 8-bit values three's ACESFilmic (then the sRGB transfer) gave that radiance on the engine's canvas. Two
exposures: the default (the scene's own exposure: three's 0.6 x 2^ev, as round one's fire match) and
engine_exposure=1.0 (three's own default toneMappingExposure, which the engine's scenes set).

    out/<out>/display_match_quads_{agx,match,match_exp1}_f001.png   the quads without the match, with it, with it
                                                                     at three's exposure 1

Checks: every grey quad within 2.5 / 255 of three's display value at each exposure (printed for the coloured ones,
which AgX may not reach); without the match the greys differ (AgX is not ACES).

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 6 bash run_blender.sh \
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/particles/test_display_match_numeric.py \
        [-- out=verify]
"""

import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from eidoblend.fx import particles as PA  # noqa: E402
from eidoblend.fx._look import three_aces  # noqa: E402

QUADS = [((0.02,) * 3, 'grey'), ((0.1,) * 3, 'grey'), ((0.3,) * 3, 'grey'), ((0.8,) * 3, 'grey'),
         ((2.0,) * 3, 'grey'), ((6.0,) * 3, 'grey'), ((1.0, 0.35, 0.05), 'orange'), ((0.05, 0.3, 0.5), 'cyan')]
W, H = 960, 270


def additive_quad(name, rgb, x):
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-0.4, 0, -0.4), (0.4, 0, -0.4), (0.4, 0, 0.4), (-0.4, 0, 0.4)], [], [(0, 1, 2, 3)])
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = (x, 0.0, 0.0)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.surface_render_method = 'BLENDED'
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    tr, em, add = nt.nodes.new('ShaderNodeBsdfTransparent'), nt.nodes.new('ShaderNodeEmission'), \
        nt.nodes.new('ShaderNodeAddShader')
    em.inputs['Color'].default_value = (*rgb, 1.0)
    em.inputs['Strength'].default_value = 1.0
    nt.links.new(tr.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs['Surface'])
    me.materials.append(m)
    return ob


def centres(path):
    from PIL import Image
    a = np.asarray(Image.open(path).convert('RGB')).astype(np.float64)
    out = []
    for i in range(len(QUADS)):
        cx = int((i + 0.5) * W / len(QUADS))
        out.append(a[H // 2 - 8:H // 2 + 8, cx - 8:cx + 8].reshape(-1, 3).mean(0))
    return np.array(out)


def main():
    sc = S.clean_scene(24, 1, 1)
    S.probe_render(sc, (W, H), 16)
    S.world(sc, (0.0, 0.0, 0.0), 0.0)
    for i, (rgb, _k) in enumerate(QUADS):
        additive_quad(f'quad_{i}', rgb, (i - (len(QUADS) - 1) / 2) * 1.0)
    cam = S.camera('cam', (0.0, -10.0, 0.0), (0.0, 0.0, 0.0), 50.0)
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = float(len(QUADS))
    p_agx = os.path.join(S.OUT, 'display_match_quads_agx_f001.png')
    S.render_still(p_agx, 1)
    got_agx = centres(p_agx)
    greys = [i for i, (_r, k) in enumerate(QUADS) if k == 'grey']
    for tag, eng_exp, three_exp in (('match', None, 0.6), ('match_exp1', 1.0, 1.0)):
        sc.compositing_node_group = None                     # a fresh compositor for each exposure
        PA.create_particles_compose(sc, engine_exposure=eng_exp)
        path = os.path.join(S.OUT, f'display_match_quads_{tag}_f001.png')
        S.render_still(path, 1)
        want = np.array([three_aces(np.array(rgb), three_exp) for rgb, _k in QUADS]) * 255.0
        got = centres(path)
        for (rgb, kind), w, g, a in zip(QUADS, want, got, got_agx):
            print(f'[display] {tag} {kind} {rgb}: three ACES (exposure {three_exp}) {w.round(1)}  match {g.round(1)}  '
                  f'plain AgX {a.round(1)}')
        err = np.abs(got[greys] - want[greys]).max()
        S.check(f'{tag}: every grey shows three\'s ACESFilmic display value at exposure {three_exp} (8-bit)',
                err < 2.5, f'max |diff| {err:.2f} / 255')
        d_agx = np.abs(got_agx[greys] - want[greys]).max()
        S.check(f'{tag}: without the match AgX shows them differently (the match does something)', d_agx > 5.0,
                f'plain AgX off by up to {d_agx:.1f} / 255')
    ok = S.summary('display match')
    sys.exit(0 if ok else 1)


try:
    main()
except SystemExit:
    raise
except Exception:
    import traceback
    traceback.print_exc()
    print('FAIL exception')
    sys.exit(1)

"""test_lib_example.py: interiors_lib as a library, outside the two sets: the guide's own example (a SetBuilder, the
material kit, a TSL-style recipe on a uniform, a mesh and a spot in three's axes, emit) run as written and checked,
plus the small helpers, a pbr set with a metalness map, the showroom's parts['turntable']['setSpin'] keyed alone, the
env as the World (no material carries an environment; the lookup turns with the set), and two sets sharing one scene
(env_switch, the keyed cut, a bake's isolation, dispose). No render (no GPU slot):

    bash run_blender.sh <worktree>/blender/tests/sets_uf_interiors/test_lib_example.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as T  # noqa: E402

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.sets.unknown_force import interiors_lib as L  # noqa: E402


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    # ---------------------------------------------------------------- the guide's example, as written there
    sb = L.SetBuilder('my_set', scene)                   # collection + root Empty + scene graph
    K = L.material_kit(sb, prefix='mine')
    steel = K.pbr('steel', L.acg('Metal027'), tint=(0.55, 0.56, 0.6), tile=1 / 0.8, rough=0.9, metal=1)
    m, g = K.new('glow')                                 # a custom recipe, TSL style
    sb.uniform('uT', 0.0)
    n = K.tri(g, 3.0)
    g.basic(g.vec3(1.0, 0.3, 0.1) * (g.sin(g.uniform('uT') * 4.0) * 0.5 + 0.5) * (n.x + 0.5))
    beam = L.MeshNode(L.box_uv(L.box_geometry(0.1, 2.0, 0.1), 1), steel, name='post')
    beam.set_position(0.0, 1.0, 0.0)                     # three's axes: 1 m up
    sb.root.add(beam)
    lamp = L.LightNode('spot', 0xffe2c4, 7, 7, 1.6, angle=0.32, penumbra=0.85, name='spot')
    lamp.set_position(1.3, 3.5, 2.4)
    lamp.target = L.Node('spotTarget').set_position(0, 0.75, 0)
    sb.root.add(lamp, lamp.target)
    sb.emit()                                            # Blender objects, lights aimed, energies in three's units

    # ---------------------------------------------------------------- what it made
    bpy.context.view_layer.update()
    obs = {o.name.split(':')[-1]: o for o in sb.made['objects']}
    post = obs.get('post')
    lo = post.matrix_world @ Vector(post.bound_box[0]) if post else None
    hi = post.matrix_world @ Vector(post.bound_box[6]) if post else None
    T.check('the post: a 0.1 x 2 x 0.1 m box centred 1 m up (three y up -> Blender z up), in the steel recipe',
            post is not None and abs((hi.z - lo.z) - 2.0) < 1e-5 and abs((lo.z + hi.z) / 2 - 1.0) < 1e-5
            and post.data.materials[0] == steel, f'z {lo.z:.3f}..{hi.z:.3f}' if post else 'no post')
    sp = obs.get('spot')
    tg = obs.get('spotTarget')
    want_pos = Vector(L.to_blender((1.3, 3.5, 2.4)))
    aim = -(sp.matrix_world.to_3x3() @ Vector((0, 0, 1))) if sp else None
    to_t = (tg.matrix_world.translation - sp.matrix_world.translation).normalized() if sp and tg else None
    d = (Vector(L.to_blender((1.3, 3.5, 2.4))) - Vector(L.to_blender((0, 0.75, 0)))).length
    want_w = 7 * 4 * math.pi * d ** (2 - 1.6)            # 7 cd, decay 1.6 matched to inverse square at the target
    T.check('the spot: at (1.3, 3.5, 2.4) three, aimed at its target, 7 cd -> W (decay 1.6 matched at the target), '
            'cone 2 x 0.32 rad, blend from the penumbra, cutoff 7 m',
            sp is not None and (sp.matrix_world.translation - want_pos).length < 1e-5 and aim.dot(to_t) > 0.9999
            and abs(sp.data.energy - want_w) < 1e-3 and abs(sp.data.spot_size - 0.64) < 1e-6
            and abs(sp.data.spot_blend - L.three_spot_blend(0.32, 0.85)) < 1e-6
            and sp.data.use_custom_distance and abs(sp.data.cutoff_distance - 7) < 1e-6,
            f'{sp.data.energy:.2f} W (want {want_w:.2f}), cos {aim.dot(to_t):.6f}' if sp else 'no spot')
    drv = m.node_tree.animation_data.drivers if m.node_tree.animation_data else []
    T.check("the glow recipe reads uT through a one-variable driver on the set's root",
            len(drv) >= 1 and all(dd.driver.is_valid for dd in drv)
            and any('uT' in dd.driver.variables[0].targets[0].data_path for dd in drv), f'{len(drv)} drivers')
    T.check('the steel recipe carries the AmbientCG maps (colour, normal, roughness)',
            sum(1 for nd in steel.node_tree.nodes if nd.bl_idname == 'ShaderNodeTexImage' and nd.image) >= 3)

    # ---------------------------------------------------------------- the small helpers, as interiors_lib.js
    ok = (L.fs_path('file:///C:/a/b%20c/f.ttf') == 'C:/a/b c/f.ttf' and L.fs_path('/srv/x.ttf') == '/srv/x.ttf'
          and L.lerp(2.0, 4.0, 0.25) == 2.5 and L.clamp01(1.7) == 1.0 and L.clamp01(-0.2) == 0.0
          and L.smooth(0.5) == 0.5 and L.ramp(3.0, 2.0, 4.0) == 0.5)
    T.check('fs_path / lerp / clamp01 / smooth / ramp as interiors_lib.js', ok)

    # ---------------------------------------------------------------- a new piece's options (no render)
    sc_ = [L.state_curve(s, 0.997) for s in (None, 0.4, (2.0, 4.0), (1.0, 3.0, 1.0, 0.0), (5.0, 5.0, 0.0, 2.0),
                                              lambda t: t * t)]
    got = [[round(c(t), 6) for t in (0.0, 3.0, 6.0)] for c in sc_]
    want = [[0.997] * 3, [0.4] * 3, [0.0, 0.5, 1.0], [1.0, 0.0, 0.0], [0.0, 0.0, 2.0], [0.0, 9.0, 36.0]]
    T.check('state_curve: default, held, (start, end), (start, end, from, to), a step when end <= start, a function',
            got == want, f'{got}')
    T.check('frame_list: (first, last) inclusive, a list as given, a range',
            L.frame_list((3, 6)) == [3, 4, 5, 6] and L.frame_list([3, 6]) == [3, 6] and L.frame_list(range(2, 4)) == [2, 3])
    import numpy as np
    from PIL import Image
    cv_p = L.override_canvas(lambda ctx, W, H: (setattr(ctx, 'fillStyle', '#ff0000'), ctx.fillRect(0, 0, W // 2, H)),
                             64, 32)
    cv_a = L.override_canvas(np.full((8, 16, 4), (0, 0, 255, 255), np.uint8), 64, 32)
    cv_i = L.override_canvas(Image.new('RGB', (128, 64), (0, 255, 0)), 64, 32)
    cv_c = L.override_canvas(cv_p, 64, 32)
    px = [c.rgba8() for c in (cv_p, cv_a, cv_i)]
    T.check('override_canvas: a painter on a fresh transparent canvas, an array, a Pillow image (resized to the '
            'canvas), a Canvas as it is', tuple(px[0][5, 5]) == (255, 0, 0, 255) and px[0][5, 50, 3] == 0 and
            tuple(px[1][20, 40]) == (0, 0, 255, 255) and tuple(px[2][10, 10]) == (0, 255, 0, 255) and cv_c is cv_p
            and all((c.width, c.height) == (64, 32) for c in (cv_p, cv_a, cv_i)))
    try:
        L.check_art({'board_centre': None}, ['board_center'], 'test')
        refused = False
    except KeyError:
        refused = True
    T.check('check_art refuses a canvas key the set does not have', refused)

    # ---------------------------------------------------------------- a set with a metalness map (materialKit's pbr)
    met_set = {'map': L.acg('Metal027')['map'], 'metalnessMap': L.acg('Metal027')['roughnessMap']}
    mm = K.pbr('metalmap', met_set, metal=1)
    bs = next(nd for nd in mm.node_tree.nodes if nd.bl_idname == 'ShaderNodeBsdfPrincipled')
    T.check("pbr: a set's metalnessMap drives the metalness (its red channel x metal)", bs.inputs['Metallic'].is_linked)

    # ---------------------------------------------------------------- the showroom's setSpin, keyed alone
    from eidoblend.sets.unknown_force import showroom as SR
    show = SR.build(scene, art_cache=T.ART, probe=False)
    show.parts['turntable']['setSpin'](0.7, frame=10)
    show.parts['turntable']['setSpin'](2.1, frame=20)
    scene.frame_set(15)
    a = show.parts['turntable']['platter'].rotation_euler.z
    T.check("parts['turntable']['setSpin'](a, frame=) keys the platter alone (LINEAR between keys)",
            abs(a - 1.4) < 1e-5, f'{a:.5f} rad at frame 15 (want 1.4)')

    # ---------------------------------------------------------------- a piece's own prop lit by the set's env (the guide)
    K2 = show.kit                                  # the set's material kit (its noise, its naming)
    mc, gc = K2.new('my-chrome')                   # disposed with the set
    gc.standard(color=(0.95, 0.95, 0.96), roughness=0.05, metalness=1.0)
    T.check("a piece's own material made through show.kit is the set's (disposed with it) and lit by its World",
            mc in show.sb.made['materials'] and mc.name == 'ufsr-my-chrome'
            and not any(nd.bl_idname == 'ShaderNodeTexEnvironment' for nd in mc.node_tree.nodes))

    # ---------------------------------------------------------------- the env is the World, turning with the set
    lit = SR.build(scene, art_cache=T.ART, probe=False, name='set:showroom_b')
    carry = [mt for mt in lit.sb.made['materials'] if any(nd.bl_idname == 'ShaderNodeTexEnvironment'
                                                          for nd in mt.node_tree.nodes)]
    env_tx = [nd for nd in lit.env.node_tree.nodes if nd.bl_idname == 'ShaderNodeTexEnvironment']
    turn = [nd for nd in lit.env.node_tree.nodes if nd.bl_idname == 'ShaderNodeVectorRotate']
    scene.world = lit.env                          # (a World the scene uses: the depsgraph evaluates its drivers)
    lit.root.rotation_euler = (0.0, 0.0, math.pi / 2)
    bpy.context.view_layer.update()
    we = lit.env.evaluated_get(bpy.context.evaluated_depsgraph_get())
    rz = [nd.inputs[2].default_value for nd in we.node_tree.nodes if nd.bl_idname == 'ShaderNodeCombineXYZ']
    lit.root.rotation_euler = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()
    T.check("the set's env is its World: no material carries an environment of its own, and the World's lookup turns "
            "with the set's root (its rotation through drivers)",
            not carry and len(env_tx) == 1 and len(turn) == 1 and turn[0].invert
            and env_tx[0].inputs['Vector'].is_linked and rz and abs(rz[0] - math.pi / 2) < 1e-5,
            f'{len(carry)} materials with an environment; turn {rz}')

    # ---------------------------------------------------------------- several sets in one scene: env_switch
    lit.root.location = (60.0, 0.0, 0.0)
    w = L.env_switch(scene, [show, lit])
    show.show(True, frame=1)
    lit.show(False, frame=1)
    show.show(False, frame=11)
    lit.show(True, frame=11)

    def weights(f):
        scene.frame_set(f)
        we = scene.world.evaluated_get(bpy.context.evaluated_depsgraph_get())
        return [round(next(x for x in nd.inputs if x.name == 'Scale').default_value, 3) for nd in we.node_tree.nodes
                if nd.bl_idname == 'ShaderNodeVectorMath' and nd.operation == 'SCALE'
                and not nd.inputs[3].is_linked]
    w5, w15 = weights(5), weights(15)
    vis = (show.root.hide_render, lit.root.hide_render)
    with L._alone(show, [show, lit]):
        alone = (show.root.hide_render, lit.root.hide_render, show.root['uf_env_on'], lit.root['uf_env_on'])
    scene.frame_set(15)
    back = (show.root.hide_render, lit.root.hide_render, show.root['uf_env_on'], lit.root['uf_env_on'])
    turns = sum(1 for nd in w.node_tree.nodes if nd.bl_idname == 'ShaderNodeVectorRotate')
    T.check("env_switch: one World holds both envs (each turning with its set), each switched with its set's keyed "
            "cut; a bake sees its set alone and the scene is left as it was",
            scene.world == w and w5 == [1.0, 0.0] and w15 == [0.0, 1.0] and vis == (True, False) and turns == 2
            and alone == (False, True, 1.0, 0.0) and back == (True, False, 0.0, 1.0)
            and {s.sb.name for s in L._live_sets(scene)} == {'set:showroom', 'set:showroom_b'},
            f'weights f5 {w5}, f15 {w15}; alone {alone}; after {back}')
    n_w = len(bpy.data.worlds)
    lit.dispose()
    kept = scene.world == w
    show.dispose()
    T.check('dispose: the shared World survives the first set and goes with the last', kept and scene.world is None
            and len(bpy.data.worlds) == n_w - 3, f'{n_w} -> {len(bpy.data.worlds)} worlds')
    sb.dispose()
    T.check('the example set and the showroom dispose to an empty file',
            not [o for o in bpy.data.objects], f'{len(bpy.data.objects)} objects left')
    return T.done()


if __name__ == '__main__':
    rc = main()
    sys.stdout.flush()
    if rc:
        sys.exit(rc)

"""test_lib_example.py: interiors_lib as a library, outside the two sets: the guide's own example (a SetBuilder, the
material kit, a TSL-style recipe on a uniform, a mesh and a spot in three's axes, emit) run as written and checked,
plus the small helpers and the showroom's parts['turntable']['setSpin'] keyed alone. No render (no GPU slot):

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
    K = L.material_kit(sb, env=None, prefix='mine')
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

    # ---------------------------------------------------------------- the showroom's setSpin, keyed alone
    from eidoblend.sets.unknown_force import showroom as SR
    show = SR.build(scene, art_cache=T.ART, probe=False)
    show.parts['turntable']['setSpin'](0.7, frame=10)
    show.parts['turntable']['setSpin'](2.1, frame=20)
    scene.frame_set(15)
    a = show.parts['turntable']['platter'].rotation_euler.z
    T.check("parts['turntable']['setSpin'](a, frame=) keys the platter alone (LINEAR between keys)",
            abs(a - 1.4) < 1e-5, f'{a:.5f} rad at frame 15 (want 1.4)')
    show.dispose()
    sb.dispose()
    T.check('the example set and the showroom dispose to an empty file',
            not [o for o in bpy.data.objects], f'{len(bpy.data.objects)} objects left')
    return T.done()


if __name__ == '__main__':
    rc = main()
    sys.stdout.flush()
    if rc:
        sys.exit(rc)

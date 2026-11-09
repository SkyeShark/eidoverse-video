"""tests/post_era/test_registry.py: the effect registry's rules (custom_effects_deno.js), checked without rendering:
names and listing, effects as a name / comma string / list, unknown and unported names, layering (ALWAYS_UNDER,
DEFAULT_UNDER, the layer switch), chaining order, the uniforms' shape for one and for several effects, options
(camelCase, unknown raises, WebGPU-only warned), register(), key(), update() / set_resolution(), U.cut(), remove() and
clear(); the cuts the temporal passes restart at (history.camera_jumps, era looks' camJumped(), on keyed and on
parented cameras; scene_cuts and camera_of with camera markers; the era pass's keyed restart and its taps never
reading across a cut); chain.use_saved_frames / use_render. The chain is rendered in test_era_looks.py
(registry_chain).

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/post_era/test_registry.py
"""
import contextlib
import io
import os
import sys
import traceback

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scenes as SC                                            # noqa: E402, F401  (puts eidoblend on the path)

from eidoblend.look.post import chain                          # noqa: E402
from eidoblend.look.post import custom_effects as fx           # noqa: E402
from eidoblend.look.post import history as HI                  # noqa: E402

FAIL = []
OUT = os.path.join(SC.OUT, 'registry')
os.makedirs(OUT, exist_ok=True)


def check(ok, what):
    print(f"[registry] {'PASS' if ok else 'FAIL'}: {what}", flush=True)
    if not ok:
        FAIL.append(what)


def raises(exc, f, *a, **k):
    try:
        f(*a, **k)
    except exc as e:
        return str(e)
    return None


def fresh_scene(name):
    sc = bpy.data.scenes.new(name)
    sc.render.resolution_x, sc.render.resolution_y = 960, 540
    HI.set_history_dir(sc, os.path.join(OUT, 'history', name))
    return sc


def main():
    names = fx.list_effects()
    check(all(n in names for n in fx.WEBGPU_NAMES), f'every WebGPU registry name is registered ({len(fx.WEBGPU_NAMES)}'
                                                  f' of custom_effects_deno.js), plus Blender\'s: '
                                                  f'{sorted(set(names) - set(fx.WEBGPU_NAMES))}')
    lst = fx.list()
    check(set(lst) == set(names) and all(isinstance(v, str) and v for v in lst.values()),
          'list(): every name with what it is and its options (CustomEffectsDeno.list)')
    missing = [n for n, v in lst.items() if v.startswith('not ported')]
    check('era_looks' not in missing and 'aeropittura' not in missing and 'after_image' not in missing,
          f'era_looks, aeropittura, after_image are ported; not ported (each with its reason): {missing}')
    check(fx.registry is fx.REGISTRY, 'registry: the table itself (CustomEffectsDeno.registry)')

    sc = fresh_scene('reg_parse')
    check(raises(ValueError, fx.apply_to, sc, '') is not None, "effects '' raises (opts.effects required)")
    check(raises(ValueError, fx.apply_to, sc, ' , ') is not None, "effects ' , ' raises (at least one entry)")
    msg = raises(KeyError, fx.apply_to, sc, 'sepia,nope')
    check(msg is not None and 'nope' in msg and 'era_looks' in msg, f'an unknown name raises, naming the registered '
                                                                    f'ones ({(msg or "")[:80]}...)')
    check(chain.stages(sc) == [], 'a failed apply_to adds nothing (names are checked before anything is built)')
    msg = raises(ValueError, fx.apply_to, sc, 'nuclear_explosion')
    check(msg is not None and 'camera' in msg, f"nuclear_explosion on a scene without a camera raises, as WebGPU's "
                                               f"applyTo did ({(msg or '')[:70]}...)")
    e = fx.apply_to(sc, ' sepia , rgb_shift ')
    check([x['name'] for x in e.effects] == ['sepia', 'rgb_shift'], 'a comma string, spaces trimmed, in order')
    e2 = fx.apply_to(fresh_scene('reg_list'), ['glitch_bars'])
    check([x['name'] for x in e2.effects] == ['glitch_bars'], 'a list')

    # layering: world effects under the overlay, signal effects over it
    check(fx.layer_of('godrays', {'layer': 'over'}) == 'under' and fx.layer_of('underwater') == 'under'
          and fx.layer_of('nuclear_explosion', {'layer': 'over'}) == 'under', 'ALWAYS_UNDER is locked')
    check(fx.layer_of('depth_fog') == 'under' and fx.layer_of('depth_fog', {'layer': 'over'}) == 'over'
          and fx.layer_of('retro_wireframe') == 'under', 'DEFAULT_UNDER starts under and can switch')
    check(fx.layer_of('sepia') == 'over' and fx.layer_of('sepia', {'layer': 'under'}) == 'under'
          and fx.layer_of('era_looks') == 'over' and fx.layer_of('aeropittura', {'layer': 'under'}) == 'under',
          'every other effect starts over and switches with layer')
    sc3 = fresh_scene('reg_layers')
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        e3 = fx.apply_to(sc3, 'rgb_shift,sepia,glitch_bars', {'sepia': {'layer': 'under'}})
    hud = sc3.compositing_node_group.nodes.new('CompositorNodeImage')
    chain.set_overlay(sc3, hud)
    st = [(s, n) for s, n, _x in chain.stages(sc3)]
    check(st == [('under', 'sepia'), ('overlay', 'overlay'), ('over', 'rgb_shift'), ('over', 'glitch_bars')],
          f'chain: under, then the overlay, then over, each in the order given ({st})')
    check('effects split' in buf.getvalue() and '[sepia]' in buf.getvalue(), 'several effects print the split: '
                                                                            + buf.getvalue().strip()[:90])
    # the uniforms' shape
    check('sepia' in e3.uniforms and 'amount' in e3.uniforms['sepia'] and 'amount' not in e3.uniforms,
          'several effects: uniforms keyed by effect name only')
    one = fx.apply_to(fresh_scene('reg_one'), 'glitch_bars')
    check(one.uniforms['opacity'] is one.uniforms['glitch_bars']['opacity'] and 'barFreq' in one.uniforms,
          'one effect: its uniforms flat too (camelCase as well), as the WebGPU registry returned them')
    check(one.update(1.0) is one and one.set_resolution(1920, 1080) is one, 'update(t) and set_resolution(w, h) exist')
    # options
    o2 = fx.apply_to(fresh_scene('reg_opts'), 'glitch_bars', {'glitch_bars': {'barFreq': 22, 'scroll_speed': 1.5}})
    check(abs(o2.uniforms['bar_freq'].default_value - 22) < 1e-6 and abs(o2.uniforms['scrollSpeed'].default_value
                                                                         - 1.5) < 1e-6, 'options camelCase or snake')
    msg = raises(KeyError, fx.apply_to, fresh_scene('reg_bad'), 'rgb_shift', {'rgb_shift': {'pixels': 4}})
    check(msg is not None and 'amount' in msg, f'an unknown option raises, naming the real ones ({(msg or "")[:60]})')
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fx.apply_to(fresh_scene('reg_warn'), 'era_looks', {'era_looks': {'cam_near': 0.1, 'deco': 0.5,
                                                                         'persist_frames': 0}})
    check('cam_near' in buf.getvalue() and 'ignored' in buf.getvalue(), 'a WebGPU-only option warns and is ignored: '
                                                                       + buf.getvalue().strip().splitlines()[0][:100])
    # key(): a beat as keyframes on the group input
    s = one.key('glitch_bars', 'opacity', 60, 1.0)
    ad = one.scene.compositing_node_group.animation_data
    check(ad is not None and ad.action is not None and s.default_value == 1.0, 'key(): the uniform keyed in the tree')
    # register(): another package's effect, then applied like any other
    def build_invert(scene, o):
        g = bpy.data.node_groups.new('fx_invert_test', 'CompositorNodeTree')
        g.interface.new_socket(name='Image', in_out='INPUT', socket_type='NodeSocketColor')
        f = g.interface.new_socket(name='amount', in_out='INPUT', socket_type='NodeSocketFloat')
        f.default_value = 1.0
        g.interface.new_socket(name='Image', in_out='OUTPUT', socket_type='NodeSocketColor')
        gi, go = g.nodes.new('NodeGroupInput'), g.nodes.new('NodeGroupOutput')
        inv = g.nodes.new('CompositorNodeInvert')
        g.links.new(gi.outputs['Image'], inv.inputs['Color'])
        g.links.new(gi.outputs['amount'], inv.inputs['Factor'])
        g.links.new(inv.outputs['Color'], go.inputs['Image'])
        return g
    fx.register('invert_test', build_invert, params=[('amount', 1.0, 0.0, 1.0)], doc='a test group')
    check('invert_test' in fx.list_effects() and 'a test group' in fx.list()['invert_test'], 'register(): listed')
    r = fx.apply_to(fresh_scene('reg_custom'), 'invert_test', {'invert_test': {'amount': 0.25}})
    check(abs(r.uniforms['amount'].default_value - 0.25) < 1e-6 and r.effects[0]['layer'] == 'over',
          'a registered effect applies with its options, on the default layer')
    check(raises(TypeError, fx.register, 'bad', 'not a function') is not None, 'register() needs a function')
    del fx.REGISTRY['invert_test']
    # temporal passes: U.cut(), remove(), clear()
    sc5 = fresh_scene('reg_temporal')
    t5 = fx.apply_to(sc5, 'after_image,sepia')
    t5.uniforms['after_image'].cut(12, 30)
    cuts = list(sc5.compositing_node_group.get('eido_cuts_after_image_trail', []))
    check(cuts == [1, 12, 30], f'U.cut(12, 30): the trail restarts at the scene start and both frames ({cuts})')
    n_before = len(sc5.compositing_node_group.nodes)
    fx.remove(sc5, 'after_image')
    left = [n.name for n in sc5.compositing_node_group.nodes if 'after_image' in n.name]
    check(not left and [n for _s, n, _x in fx.applied(sc5)] == ['sepia'],
          f'remove(): the pass, its history writer and taps go ({n_before} -> '
          f'{len(sc5.compositing_node_group.nodes)} nodes); sepia stays')
    fx.clear(sc5)
    check(fx.applied(sc5) == [] and not sc5.render.use_compositing, 'clear(): no effects left, the compositor off')
    # one scene, two calls: apply_to adds (the WebGPU applyTo replaced; clear() first for that)
    sc6 = fresh_scene('reg_add')
    fx.apply_to(sc6, 'bloom', {'bloom': {'strength': 0.5}})
    fx.apply_to(sc6, 'sepia')
    check([n for _s, n, _x in chain.stages(sc6)] == ['bloom', 'sepia'], 'a second apply_to adds to the chain')
    # native effects change the scene (a fog volume, the lens, a material override, the bubbles): applied() lists
    # them and clear() takes every change back, as the WebGPU applyTo dropped an effect when the next call replaced it
    sc8 = fresh_scene('reg_native')
    cam8 = bpy.data.objects.new('reg_native_cam', bpy.data.cameras.new('reg_native_cam'))
    sc8.collection.objects.link(cam8)
    sc8.camera = cam8
    cam8.data.dof.use_dof, cam8.data.dof.focus_distance, cam8.data.dof.aperture_fstop = False, 7.0, 5.6
    target = bpy.data.objects.new('reg_target', None)
    sc8.collection.objects.link(target)
    ee = sc8.eevee
    ee.use_volumetric_shadows, ee.use_volume_custom_range = False, False
    vl8 = sc8.view_layers[0]
    fx.apply_to(sc8, 'depth_fog,focus_blur,retro_wireframe,underwater',
                {'depth_fog': {'density': 0.02}, 'focus_blur': {'fstop': 2.0, 'focusObjects': [target]},
                 'retro_wireframe': {'color': 'amber'}, 'underwater': {'bubbleCount': 10}})
    names = [n for _s, n, _x in fx.applied(sc8)]
    check(sorted(names) == ['depth_fog', 'focus_blur', 'retro_wireframe', 'underwater']
          and 'look_depth_fog' in sc8.objects and cam8.data.dof.use_dof and abs(cam8.data.dof.aperture_fstop - 2) < 1e-6
          and cam8.data.dof.focus_object is not None and vl8.material_override is not None
          and 'uw_bubbles' in bpy.data.objects and ee.use_volumetric_shadows,
          f'native effects applied and listed by applied(): {names}')
    fx.apply_to(sc8, 'retro_wireframe', {'retro_wireframe': {'color': 'green'}})     # twice: the first state is kept
    fx.clear(sc8)
    d8 = cam8.data.dof
    check(fx.applied(sc8) == [] and 'look_depth_fog' not in bpy.data.objects and not d8.use_dof
          and abs(d8.focus_distance - 7.0) < 1e-6 and abs(d8.aperture_fstop - 5.6) < 1e-6 and d8.focus_object is None
          and 'focus_reg_native_cam' not in bpy.data.objects and vl8.material_override is None
          and 'uw_bubbles' not in bpy.data.objects and not ee.use_volumetric_shadows and not ee.use_volume_custom_range,
          'clear(): the fog volume, the focus empty and the bubbles gone; the lens, the override and the volume '
          'settings as they were')
    # the screen effects ported this round: each builds and takes its WebGPU options (camelCase too)
    samples = {'wavy': {'amplitude': 12, 'animSpeed': 2.0, 'animate': True}, 'kaleidoscope': {'segments': 8},
               'jitter': {'speed': 4.0}, 'melt': {'swirl': 0.5}, 'dithering': {'levels': 4},
               'chromatic_aberration_alpha': {'amount': 0.01, 'angle': 0.5},
               'bw_halftone': {'dotSize': 2.5, 'inkColor': (0.1, 0.0, 0.2), 'angle': 30},
               'bleach_bypass': {'amount': 0.7}, 'hash_blur': {'amount': 0.03, 'repeats': 16},
               'crt': {'opacity': 0.8}, 'vhs_tape': {'intensity': 1.5},
               'rain_on_camera': {'dropSize': 0.25, 'directions': 8, 'quality': 2},
               'full_toon': {'nearLevels': 5, 'outlineColor': (0.1, 0.0, 0.0), 'hueShift': 0.5},
               'cross_hatch': {'hatchStrength': 1.0, 'wiggle': 0.5},
               'underwater': {'fogDensity': 0.2, 'shallowColor': (0.2, 0.5, 0.6), 'bubbleCount': 50},
               'retro_wireframe': {'color': 'multicolor', 'lineWidth': 2.0, 'bgColor': (0.0, 0.02, 0.0)}}
    for name, o in samples.items():
        try:
            e = fx.apply_to(fresh_scene('reg_' + name), name, {name: o})
            build = ('repeats', 'directions', 'quality', 'bubbleCount', 'color', 'lineWidth', 'bgColor')
            ok = all(k in e.uniforms or k in build for k in o)
            vals = {k: (tuple(round(v, 3) for v in e.uniforms[k].default_value)[:3]
                        if hasattr(e.uniforms[k].default_value, '__len__') else round(e.uniforms[k].default_value, 3))
                    for k in o if k not in build}
            check(ok, f'{name}: builds ({len(e.nodes[name].node_tree.nodes)} nodes), options {vals}')
        except Exception as ex:                       # noqa: BLE001
            traceback.print_exc()
            check(False, f'{name}: {ex!r}')
    # blueprint's view space: three vector inputs driven from the scene camera's axes
    import math
    from mathutils import Euler
    sc7 = bpy.context.scene                          # the active scene: its depsgraph writes matrix_world back
    HI.set_history_dir(sc7, os.path.join(OUT, 'history', 'reg_blueprint'))
    cam = bpy.data.objects.new('reg_cam', bpy.data.cameras.new('reg_cam'))
    sc7.collection.objects.link(cam)
    sc7.camera = cam
    cam.rotation_euler = Euler((math.radians(70), 0.0, math.radians(30)))
    b = fx.apply_to(sc7, 'blueprint', {'blueprint': {'paperColor': (0.05, 0.1, 0.3), 'cellPx': 30}})
    cam.rotation_euler = Euler((math.radians(60), 0.0, math.radians(-40)))
    bpy.context.view_layer.update()
    sc7.frame_set(2)
    sc7.frame_set(1)
    nd = b.nodes['blueprint']
    m = cam.matrix_world
    got = [tuple(round(v, 4) for v in nd.inputs[k].default_value) for k in ('CamX', 'CamY', 'CamZ')]
    want = [tuple(round(m[r][c], 4) for r in range(3)) for c in range(3)]
    check(got == want and abs(want[2][2] - 0.5) < 1e-3, f'blueprint: the camera axes follow the scene camera by '
                                                         f'drivers (CamZ {got[2]} = {want[2]})')
    check(abs(b.uniforms['cell_px'].default_value - 30) < 1e-6 and 'cam_far' in b.uniforms,
          'blueprint: options set (cellPx 30), cam_far exposed')
    # every pass builds with every option the registry accepts
    for name in ('era_looks', 'aeropittura', 'after_image'):
        R = fx.REGISTRY[name]
        opts = [p[0] for p in R['params']] + sorted(R['build_opts'])
        check(len(opts) > 2, f'{name}: options {opts}')
    # aeropittura's underpainting: its own Kuwahara by default, Blender's node on request, anything else refused
    sc9 = fresh_scene('reg_aero_kw')
    cam9 = bpy.data.objects.new('reg_aero_cam', bpy.data.cameras.new('reg_aero_cam'))
    sc9.collection.objects.link(cam9)
    sc9.camera = cam9
    own = fx.apply_to(sc9, 'aeropittura').nodes['aeropittura'].node_tree
    fx.clear(sc9)
    bk = fx.apply_to(sc9, 'aeropittura', {'aeropittura': {'kuwahara': 'blender'}}).nodes['aeropittura'].node_tree
    has_node = lambda t: any(n.bl_idname == 'CompositorNodeKuwahara' for n in t.nodes)      # noqa: E731
    uses_own = lambda t: any(n.bl_idname == 'CompositorNodeGroup' and n.node_tree                   # noqa: E731
                             and n.node_tree.name.startswith('eido_aero_kuwa_row') for n in t.nodes)
    check(uses_own(own) and not has_node(own) and has_node(bk) and not uses_own(bk) and own.name != bk.name,
          f"aeropittura: its own Kuwahara by default ({own.name}), Blender's node with kuwahara='blender' ({bk.name})")
    msg = raises(ValueError, fx.apply_to, sc9, 'aeropittura', {'aeropittura': {'kuwahara': 'classic'}})
    check(msg is not None and 'own' in msg, f"aeropittura: kuwahara='classic' raises ({msg})")
    cuts_part()
    source_part()
    ease_part()


def ease_part():
    """aeropittura.ease_reading keys the film's smoothstepped ramps at the scene's own frame rate (30 here)."""
    from eidoblend.look.post import aeropittura as AP
    from eidoblend.look.post.history import _fcurves
    sc = fresh_scene('reg_ease')
    sc.render.fps, sc.render.fps_base = 30, 1.0
    cam = bpy.data.objects.new('reg_ease_cam', bpy.data.cameras.new('reg_ease_cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    e = fx.apply_to(sc, 'aeropittura')
    AP.apply_look(e.uniforms, AP.LOOKS['storm'], 1.0)                 # strokes 1 before the ease
    AP.ease_reading(e.uniforms, 10, 70)                               # e.uniforms as apply_to returns it, no fps
    t = sc.compositing_node_group
    fc = {f.data_path: f for f in _fcurves(t.animation_data.action, t)}[
        e.uniforms['strokes'].path_from_id('default_value')]
    x = (4 / 30) / 0.6                                                 # frame 14: 4 frames in at 30 fps
    want = 1.0 + (AP.READ['strokes'] - 1.0) * x * x * (3 - 2 * x)
    got = [round(fc.evaluate(f), 4) for f in (10, 14, 28, 60, 70)]
    check(abs(got[1] - want) < 1e-3 and abs(got[2] - AP.READ['strokes']) < 1e-3 and got[0] == 1.0 and got[4] == 1.0,
          f'ease_reading: smoothstepped in over 0.6 s and out over 0.45 s at the scene\'s 30 fps (strokes at frames '
          f'10, 14, 28, 60, 70: {got}; frame 14 should be {want:.4f})')
    fx.clear(sc)


def source_part():
    """chain.use_saved_frames swaps the chain's source for an image sequence and chain.use_render puts the Render
    Layers back, the stages' links kept both ways."""
    sc = fresh_scene('reg_source')
    fx.apply_to(sc, 'sepia')
    exr = os.path.join(SC.OUT, 'after_image', 'src', 'src_0001_combined.exr')
    if not os.path.exists(exr):
        check(False, f'use_saved_frames / use_render: no saved frame to test with ({exr}: run test_after_image.py '
                     f'--stage sources)')
        return
    st = chain.stages(sc)[0][2]
    n = chain.use_saved_frames(sc, exr)
    a = chain.source(sc)
    ok1 = a.bl_idname == 'CompositorNodeImage' and _img_link_from(st) == a
    rl = chain.use_render(sc)
    ok2 = chain.source(sc).bl_idname == 'CompositorNodeRLayers' and _img_link_from(st) == rl
    check(n == a and ok1 and ok2, 'use_saved_frames: the chain reads the image sequence; use_render: the Render '
                                  'Layers again, the stage linked from each')
    fx.clear(sc)


def _img_link_from(node):
    s = next((s for s in node.inputs if s.type == 'RGBA' and s.is_linked), None)
    return s.links[0].from_node if s is not None else None


def cuts_part():
    """era_looks' camJumped() as history.camera_jumps: frames where the camera moved > 0.6 m or turned > 10 degrees
    since the frame before, read from its F-curves or, for a parented camera, by stepping the scene; scene_cuts adds
    the markers that switch cameras; the era pass keys its persistence restart (Fresh) on all of them."""
    import math
    from eidoblend.look.post import era_looks as EL
    sc = fresh_scene('reg_cuts')
    sc.frame_start, sc.frame_end = 1, 12
    cam = bpy.data.objects.new('reg_cut_cam', bpy.data.cameras.new('reg_cut_cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    # a slow dolly and pan (0.1 m and 2 degrees a frame: no jump), a 1.5 m jump at 6, a 25 degree snap at 9
    for f in range(1, 13):
        x = 0.1 * (f - 1) + (1.5 if f >= 6 else 0.0)
        yaw = math.radians(2.0 * (f - 1) + (25.0 if f >= 9 else 0.0))
        cam.location = (x, -5.0, 1.5)
        cam.rotation_euler = (math.radians(80), 0.0, yaw)
        cam.keyframe_insert('location', frame=f)
        cam.keyframe_insert('rotation_euler', frame=f)
    from eidoblend.look.post.history import _fcurves
    for fc in _fcurves(cam.animation_data.action, cam):
        for k in fc.keyframe_points:
            k.interpolation = 'LINEAR'
    jumps = HI.camera_jumps(sc)
    check(jumps == [6, 9], f'camera_jumps: a 1.5 m jump at 6 and a 25 degree snap at 9, nothing on the slow move '
                           f'(found {jumps})')
    # the same camera parented to a moving empty: read by stepping the scene
    rig = bpy.data.objects.new('reg_cut_rig', None)
    sc.collection.objects.link(rig)
    cam.parent = rig
    rig.location = (0.0, 0.0, 0.0)
    rig.keyframe_insert('location', frame=1)
    rig.keyframe_insert('location', frame=3)
    rig.location = (0.0, 2.0, 0.0)
    rig.keyframe_insert('location', frame=4)                      # 2 m between frames 3 and 4
    for fc in _fcurves(rig.animation_data.action, rig):
        for k in fc.keyframe_points:
            k.interpolation = 'CONSTANT'
    jumps = HI.camera_jumps(sc)
    check(jumps == [4, 6, 9], f'camera_jumps with the camera parented to a moving rig (the scene stepped): the rig\'s '
                              f'2 m move at 4 as well (found {jumps})')
    # a marker switching to a second camera is a cut too; one binding the camera already in use is not (Blender
    # renders the first marker's camera from the start, so the first marker is no switch either)
    cam2 = bpy.data.objects.new('reg_cut_cam2', bpy.data.cameras.new('reg_cut_cam2'))
    sc.collection.objects.link(cam2)
    for nm, f, c in (('cam', 1, cam), ('cam_again', 7, cam), ('cam2', 11, cam2)):
        sc.timeline_markers.new(nm, frame=f).camera = c
    check(HI.scene_cuts(sc) == [1, 11], f'scene_cuts: the first frame and the switch to the second camera, not the '
                                        f'marker re-binding the first ({HI.scene_cuts(sc)})')
    check([HI.camera_of(sc, f).name for f in (1, 10, 11)] == ['reg_cut_cam', 'reg_cut_cam', 'reg_cut_cam2'],
          'camera_of: the marker camera a render of each frame uses')
    # the era pass, applied with no cuts given, keys its restart on the markers and the jumps
    t0 = chain.tree(sc)
    e = fx.apply_to(sc, 'era_looks')
    EL.set_look(e.uniforms, EL.ERA_LOOKS['crt'])
    # (the keys are read off their F-curves: this scene is not the window's, so a frame_set would not write the
    # animated values back onto its sockets; a render of it evaluates them, test_film_render.py)
    fcs = {fc.data_path: fc for fc in _fcurves(t0.animation_data.action, t0)}
    fresh = e.nodes['era_looks'].inputs['Fresh']
    fc_fresh = fcs[fresh.path_from_id('default_value')]
    on = [f for f in range(1, 13) if fc_fresh.evaluate(f) > 0.5]
    check(on == [1, 4, 6, 9, 11], f'era_looks restarts its CRT persistence on the first frame, the jumps and the '
                                  f'marker (Fresh keyed on {on})')
    h = e.histories['era_looks'][0]
    tap = h.taps(t0)[3]
    fc_off = fcs[f'nodes["{tap.name}"].frame_offset']
    reads = [f + int(round(fc_off.evaluate(f))) for f in (5, 6, 7, 8, 9, 10)]
    check(reads == [4, 6, 6, 6, 9, 9], f'the tap 3 frames back never reads across a cut: frames 5-10 read {reads}')
    fx.clear(sc)


try:
    main()
except Exception:
    traceback.print_exc()
    FAIL.append('exception: ' + traceback.format_exc().splitlines()[-1])
print(f"[registry] {'FAIL ' + str(len(FAIL)) if FAIL else 'PASS'}", flush=True)

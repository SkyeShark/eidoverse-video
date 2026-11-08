"""tests/post_era/test_registry.py: the effect registry's rules (custom_effects_deno.js), checked without rendering:
names and listing, effects as a name / comma string / list, unknown and unported names, layering (ALWAYS_UNDER,
DEFAULT_UNDER, the layer switch), chaining order, the uniforms' shape for one and for several effects, options
(camelCase, unknown raises, WebGPU-only warned), register(), key(), update() / set_resolution(), U.cut(), remove() and
clear(). The chain is rendered in test_era_looks.py (registry_chain).

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
    msg = raises(NotImplementedError, fx.apply_to, sc, 'nuclear_explosion')
    check(msg is not None and 'nuclear_explosion' in msg, f'a registered but unported name raises with its reason '
                                                          f'({(msg or "")[:70]}...)')
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


try:
    main()
except Exception:
    traceback.print_exc()
    FAIL.append('exception: ' + traceback.format_exc().splitlines()[-1])
print(f"[registry] {'FAIL ' + str(len(FAIL)) if FAIL else 'PASS'}", flush=True)

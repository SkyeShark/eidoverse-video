"""No-GPU checks of the sky's bookkeeping (seconds; nothing is rendered):

  replay     two passes of frame_states() over one Sky give bit-identical frames (a re-bake replays the sky),
             a partial range gives exactly the full range's frames, and a direction call made by an on_frame
             callback is not recorded (a second pass is not changed by the first)
  window     _cam_window covers Blender's camera frame exactly: landscape and portrait, sensor fit AUTO /
             HORIZONTAL / VERTICAL, lens shift, pixel aspect (against Blender's own sensor-fit rules)
  fog        use_fog splices into an existing post chain (Render Layers -> Glare -> output) and a re-bake
             keeps it; key_fog leaves another family's F-curves in the same tree alone
  caster     the cloud-shadow caster height just under the lowest cloud base of a bake

    blender --background --factory-startup --python blender/tests/sky/state_and_wiring.py
(prints PASS/FAIL lines; no GPU, so no slot needed)
"""
import os
import sys
import tempfile

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.sky import make_sky, _cam_window  # noqa: E402
from eidoblend.sky import cloud_shadows, fog as FOG  # noqa: E402
from eidoblend.sky.world_nodes import _fcurves  # noqa: E402

results = []
TMP = tempfile.mkdtemp(prefix='eido_sky_check_')


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print(('PASS ' if ok else 'FAIL ') + name + (('  ' + detail) if detail else ''))


def fresh_scene(fs=1, fe=48, fps=24):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = fps
    sc.frame_start, sc.frame_end = fs, fe
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    return sc, cam


def snapshot(sky, fs=None, fe=None):
    rows = {}
    for f, t, L in sky.frame_states(fs, fe):
        U = sky.sky.U
        rows[f] = (t, U['finalMul'], U['cloudWeatherGrey'], tuple(U['cloudDisplacement']), tuple(U['sunDir']),
                   L['sun_intensity'], L['hemi_dim'], tuple(L['fog_color']), sky.wx.state['name'])
    return rows


# ---------------------------------------------------------------- replay
sc, cam = fresh_scene()
sky = make_sky(sc, camera=cam, hours=15.0, clouds='cumulus', cache_dir=TMP, shadows=False, weather_fx=False)
sky.transition_to('storm', 1.0, 1.0, at=0.5)
sky.day_cycle(start_hour=15.0, seconds=30.0, at=0.25)
seen = []
sky.on_frame(lambda s, t: (seen.append(t), s.set_colors({'cloud': (1.0, 0.9, 0.8)}) if t >= 1.0 else None))
n_recipe = len(sky.recipe)
a = snapshot(sky)
b = snapshot(sky)
check('replay: a second pass gives bit-identical frames', a == b,
      'f01 finalMul %.3f grey %.2f | f48 finalMul %.3f grey %.2f disp (%.1f, %.1f)'
      % (a[1][1], a[1][2], a[48][1], a[48][2], a[48][3][0], a[48][3][2]))
check('replay: the sky changes over the range (the test means something)',
      a[1][1] != a[48][1] and a[1][4] != a[48][4] and a[48][8] == 'storm')
part = snapshot(sky, 25, 48)
check('replay: frames 25-48 of a partial pass equal the full pass', all(part[f] == a[f] for f in range(25, 49)),
      'f25 full %.3f/%.2f/(%.1f, %.1f) partial %.3f/%.2f/(%.1f, %.1f)'
      % (a[25][1], a[25][2], a[25][3][0], a[25][3][2], part[25][1], part[25][2], part[25][3][0], part[25][3][2]))
check('replay: an on_frame direction call is not recorded', len(sky.recipe) == n_recipe,
      'recipe %d -> %d entries' % (n_recipe, len(sky.recipe)))
sky.set_time(9.0)                  # an immediate call after a pass is part of the direction from now on
c = snapshot(sky)                  # (frame 1 starts at 09:00; the day cycle scheduled at 0.25 s still takes over)
check('replay: an immediate call made after a pass joins every following pass',
      c[1][4] != a[1][4] and c[48] == a[48] and c == snapshot(sky))

# ---------------------------------------------------------------- window
for (w, h, fit, shift, asp) in ((960, 540, 'AUTO', (0, 0), (1, 1)), (540, 960, 'AUTO', (0, 0), (1, 1)),
                                (1080, 1920, 'AUTO', (0, 0.1), (1, 1)), (540, 960, 'VERTICAL', (0.05, 0), (1, 1)),
                                (960, 540, 'VERTICAL', (0, 0), (1, 1)), (960, 540, 'HORIZONTAL', (0.08, -0.05), (1, 1)),
                                (540, 960, 'HORIZONTAL', (0, 0), (1, 1)), (720, 576, 'AUTO', (0, 0), (16, 11))):
    sc, cam = fresh_scene()
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.pixel_aspect_x, sc.render.pixel_aspect_y = asp
    cd = cam.data
    cd.sensor_fit, cd.lens, cd.sensor_width, cd.sensor_height = fit, 30.0, 36.0, 24.0
    cd.shift_x, cd.shift_y = shift
    # Blender's rules (BKE_camera_sensor_fit / BKE_camera_sensor_size): AUTO fits sensor_width to the larger
    # side; the shift is in units of the fitted side
    W, H = w * asp[0], h * asp[1]
    f = fit if fit != 'AUTO' else ('HORIZONTAL' if W >= H else 'VERTICAL')
    size = cd.sensor_height if fit == 'VERTICAL' else cd.sensor_width
    t_fit = size * 0.5 / cd.lens
    tx, ty = (t_fit, t_fit * H / W) if f == 'HORIZONTAL' else (t_fit * W / H, t_fit)
    sx, sy = shift[0] * 2 * t_fit, shift[1] * 2 * t_fit
    ref = (max(abs(sx - tx), abs(sx + tx)), max(abs(sy - ty), abs(sy + ty)))
    got = _cam_window(cam, sc)
    check('window %dx%d %-10s shift %s aspect %s' % (w, h, fit, shift, asp),
          abs(got[0] - ref[0]) < 1e-5 and abs(got[1] - ref[1]) < 1e-5,
          'window (%.4f, %.4f) frame (%.4f, %.4f)' % (got + ref))

# ---------------------------------------------------------------- fog
sc, cam = fresh_scene(1, 3)
tree = bpy.data.node_groups.new('post', 'CompositorNodeTree')
sc.compositing_node_group = tree
tree.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
rl = tree.nodes.new('CompositorNodeRLayers')
glare = tree.nodes.new('CompositorNodeGlare')
glare.name = 'family_glare'
go = tree.nodes.new('NodeGroupOutput')
tree.links.new(rl.outputs['Image'], glare.inputs['Image'])
tree.links.new(glare.outputs['Image'], go.inputs['Image'])
# another family's animation in the same tree (LINEAR keys at 1 and 3)
inp = next(s for s in glare.inputs if s.type == 'VALUE' and not s.is_linked)
inp.default_value = 0.1
inp.keyframe_insert('default_value', frame=1)
inp.default_value = 0.9
inp.keyframe_insert('default_value', frame=3)
for fc in _fcurves(tree.animation_data):
    for kp in fc.keyframe_points:
        kp.interpolation = 'LINEAR'
fake = [dict(frame=f, lights=dict(fog_color=(0.1 * f, 0.2, 0.3))) for f in (1, 2, 3)]
for _ in range(2):                                                       # bake, then re-bake
    FOG.key_fog(FOG.setup_fog(sc, density=0.0004), fake)


def upstream(sock):
    return [l.from_node.name for l in tree.links if l.to_socket == sock]


mix = tree.nodes['eido_fog_mix']
chain = (upstream(glare.inputs['Image']) == ['eido_fog_mix'] and upstream(go.inputs['Image']) == ['family_glare']
         and rl.name in upstream(next(s for s in mix.inputs if s.name == 'A' and s.is_linked)))
check('fog: spliced as Render Layers -> fog -> Glare -> output, after a re-bake', chain,
      'glare <- %s, output <- %s' % (upstream(glare.inputs['Image']), upstream(go.inputs['Image'])))
fcs = {fc.data_path: fc for fc in _fcurves(tree.animation_data)}
theirs = [fc for p, fc in fcs.items() if 'family_glare' in p]
ours = [fc for p, fc in fcs.items() if 'eido_fog_color' in p]
check("fog: another family's F-curve kept, LINEAR", len(theirs) == 1
      and all(kp.interpolation == 'LINEAR' for kp in theirs[0].keyframe_points))
check('fog: one set of fog keys at integer frames, CONSTANT', len(ours) >= 1 and all(
    [kp.co[0] for kp in fc.keyframe_points] == [1.0, 2.0, 3.0] and all(kp.interpolation == 'CONSTANT'
                                                                       for kp in fc.keyframe_points) for fc in ours),
      'keys %s' % [[kp.co[0] for kp in fc.keyframe_points] for fc in ours][:1])

# ---------------------------------------------------------------- caster
for weather, want in ((None, 0.9 * 700), ('overcast', 0.9 * 520), ('cyclone', 0.9 * 240),
                      ('darkstorm', 0.9 * (500 - 280))):
    sc, cam = fresh_scene(1, 2)
    sky = make_sky(sc, camera=cam, hours=15.0, clouds='cumulus', weather=weather, cache_dir=TMP, shadows=False,
                   weather_fx=False)
    frames = [dict(U=dict(sky.sky.U)) for _ in sky.frame_states()]
    h = cloud_shadows.caster_height_for(frames)
    check('caster height under %-9s %.0f m' % (weather or 'cumulus', h), abs(h - want) < 1e-6)

bad = [n for n, ok in results if not ok]
print('%d checks, %d failed%s' % (len(results), len(bad), (': ' + '; '.join(bad)) if bad else ''))
sys.stdout.flush()

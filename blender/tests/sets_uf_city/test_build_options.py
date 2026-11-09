"""The city's and the hole's options and controls that the renders do not reach (no GPU):

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_uf_city/test_build_options.py

  build options     city.build({'hole': False, 'seed': 7, 'rain_count': 500}); hole.build({'city': True}) (the whole
                    city); a hole built on a shared kit; emit_building's overrides
  dispose           every datablock a build made is removed
  plaza screen      set_canvas (a still), set_canvas(frames=...) (a keyed sequence), reset (keyed back to the sun)
  tickers           set_canvas
  set_lights        a light added after the build is made to skip the city (light linking EXCLUDE)
  set_focal         keyed
  update            the rain's velocity from a camera, by finite difference between calls, keyed; a still's controls
  animate           on your own clock: state(t) controls (the focal light on the dive's focal point, an object to
                    follow, turn_down, a flash as a step), the rain along the camera that renders each frame, the
                    clock; make_cameras (the dive; the hole's moves), the standalone hole's reel and clock
Prints PASS / FAIL.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from eidoblend.sets.unknown_force import citykit as KIT  # noqa: E402
from eidoblend.sets.unknown_force import city as C  # noqa: E402
from eidoblend.sets.unknown_force import hole as H  # noqa: E402

OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('[uf-options] %s %s %s' % ('PASS' if ok else 'FAIL', name, detail), flush=True)


for c in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras,
          bpy.data.node_groups, bpy.data.images, bpy.data.worlds):
    for x in list(c):
        c.remove(x)
for c in list(bpy.data.collections):
    bpy.data.collections.remove(c)
scene = bpy.context.scene
scene.render.fps = 24

# ---- emit_building's overrides (no Blender data)
plan = C.plan_city(1909)
lot = sorted(plan['lots'], key=lambda l: l['r0'])[300]
bctx = {'buf': {k: KIT.GeoBuf() for k in ('concrete', 'metal', 'frame', 'strip')}, 'signs': [], 'lights': []}
b = C.emit_building(lot, bctx, {'height': 180, 'lean': 2.0, 'style': 'ribbon', 'type': 'gradinata'})
check('emit_building overrides (height, style, type)', b['H'] == 180 and b['type'] == 'gradinata' and
      bctx['buf']['metal'].count > 0, str(b))
gb = KIT.GeoBuf()
i0 = gb.vert([0, 0, 0], [0, 1, 0], [0, 0], [0.5, 0, 0, 0], [2, 4, 4, 0], [0, 0, 0, 0])
i1 = gb.vert([1, 0, 0], [0, 1, 0], [1, 0], [0.5, 0, 0, 0], [2, 4, 4, 0], [0, 0, 0, 0])
i2 = gb.vert([0, 0, 1], [0, 1, 0], [0, 1], [0.5, 0, 0, 0], [2, 4, 4, 0], [0, 0, 0, 0])
gb.idx += [i0, i2, i1]
gb.box(KIT.make_xf([0, 0, 0]), 0, 0, 0, 1, 1, 1, {'aT': [0.1, 0.2, 0.3, 0], 'aM': [0, 3, 2, 0], 'aW': [0.2, 0.3, 0.8, 0]})
me = gb.build('uf_geobuf_probe')
check('GeoBuf: vert() triangles beside quad() / box()', len(me.polygons) == 7 and len(me.vertices) == 27,
      f'{len(me.polygons)} faces, {len(me.vertices)} vertices')
bpy.data.meshes.remove(me)

# ---- a city without the hole, another seed, a small rain
n_before = {k: len(getattr(bpy.data, k)) for k in ('objects', 'meshes', 'materials', 'images', 'node_groups', 'collections')}
city = C.build({'hole': False, 'seed': 7, 'rain_count': 500}, scene=scene)
P = city['parts']
check('city without the hole', P['hole'] is None and not any(o.name.startswith('uf_hole') for o in bpy.data.objects))
# the plan's blocks and lots are geometry (the same for every seed); the seed draws the buildings on them
check('another seed, other buildings on the same lots', len(P['plan']['lots']) == 1908 and P['stats']['signs'] != 4446
      and P['plan']['lots'][0]['seed'] != plan['lots'][0]['seed'], f"{P['stats']['signs']} signs (seed 1909: 4446)")
dg = bpy.context.evaluated_depsgraph_get()
cam = bpy.data.objects.new('opt_cam', bpy.data.cameras.new('opt_cam'))
scene.collection.objects.link(cam)
scene.camera = cam
dg.update()
check('rain_count', len(P['rain'].evaluated_get(bpy.context.evaluated_depsgraph_get()).data.vertices) == 500 * 4)
# the plaza screen
pz = P['plaza_screen']


def title(ctx, w, h):
    ctx.fillStyle = '#000'
    ctx.fillRect(0, 0, w, h)
    ctx.fillStyle = '#ffcf8a'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.font = f'{h * 0.12}px "Black Ops One"'
    ctx.fillText('UNKNOWN FORCE', w / 2, h / 2)


pz['set_canvas'](title)
nodes = pz['material'].node_tree.nodes
check('plaza set_canvas: a still replaces the sun', nodes['custom'].outputs[0].default_value == 1.0)
pz['set_canvas'](lambda ctx, w, h, t: (title(ctx, w, h), ctx.fillRect(0, 0, w * min(1, t), 8)), frames=range(760, 790),
                 fps=24, out_dir=OUT / 'opt_plaza_seq')
seq = [n.image for n in nodes if n.type == 'TEX_IMAGE' and n.image is not None and n.image.source == 'SEQUENCE']
check('plaza set_canvas(frames=...): a keyed sequence', len(seq) == 1 and seq[0].get('eido_frame_duration') == 30)
pz['reset'](frame=800)
check('plaza reset (keyed): the sun is back', nodes['custom'].outputs[0].default_value == 0.0 and
      pz['material'].node_tree.animation_data is not None)
# set_lights: a key light added after the build skips the city
key_d = bpy.data.lights.new('piece_key', 'SPOT')
key = bpy.data.objects.new('piece_key', key_d)
scene.collection.objects.link(key)
P['set_lights']([P['lights']['moon']])
rc = key.light_linking.receiver_collection
st = None
if rc is not None:
    for i, cc in enumerate(rc.children):
        if cc == P['collection']:
            st = rc.collection_children[i].light_linking.link_state
check('set_lights: a light added later excludes the city', st == 'EXCLUDE', str(st))
# set_focal keyed, update with a camera (finite difference) keyed
P['set_focal']((10.0, -5.0, 20.0), gain=2.0, frame=50)
U = P['uniforms']
check('set_focal keyed', U.tree.animation_data is not None and U['focal_gain'] == 2.0)
cam.location = (0.0, 0.0, 100.0)
city['update'](10.0, {'camera': cam}, frame=100)
cam.location = (0.0, 2.4, 100.0)            # 2.4 m in one frame at 24 fps = 57.6 m/s
city['update'](10.0 + 1 / 24, {'camera': cam}, frame=101)
check('update: the rain\'s velocity from the camera, keyed', abs(U['cam_vel'][1] - 57.6) < 1e-3, str(U['cam_vel']))
# dispose
city['dispose']()
n_after = {k: len(getattr(bpy.data, k)) for k in n_before}
mine = {'objects': 2}                           # this test's camera and its key light
leak = {k: n_after[k] - n_before[k] - mine.get(k, 0) for k in n_before if n_after[k] - n_before[k] - mine.get(k, 0)}
check('dispose removes what the build made', not leak, f'left: {leak}')

# ---- hole.build({'city': True}) builds the whole city; a hole on a shared kit
whole = H.build({'city': True, 'rain_count': 200}, scene=scene)
check('hole.build(city=True) is the city', whole['group'].name.startswith('set:city') and whole['parts']['hole'] is not None)
tk = whole['parts']['hole']['parts']['tickers'][2]
tk['set_canvas'](lambda ctx, w, h: (ctx.clearRect(0, 0, w, h), setattr(ctx, 'fillStyle', '#39ff9a'),
                                     ctx.fillRect(0, 0, w, h / 2)))
px = np.empty(2048 * 96 * 4, np.float32)
tk['texture'].pixels.foreach_get(px)
check('ticker set_canvas', abs(px.reshape(96, 2048, 4)[80, 100, 1] - 1.0) < 0.01, str(px.reshape(96, 2048, 4)[80, 100]))
K = whole['parts']['kit']
whole['dispose']()
K2 = KIT.make_kit()
KIT.make_light_map(K2, [H.draw_hole_lights])
h2 = H.build({'kit': K2}, scene=scene)
check('a hole on a shared kit (no standalone extras)', h2['parts']['extras'] is None and h2['parts']['kit'] is K2)
K2.made.dispose()


# ---- the registry with a harness ctx: eidoblend.sets.build(name, ctx) calls build(ctx, **kw); keys go through ctx.key
class HarnessCtx:
    """The surface of the harness ctx a set uses: scene, key (logged, as the harness logs), cut (camera markers)."""

    def __init__(self, sc):
        self.scene = sc
        self.keys = []
        self.cuts = []

    def key(self, target, data_path, index=-1, frame=None, interpolation='LINEAR'):
        f = self.scene.frame_current if frame is None else frame
        ok = target.keyframe_insert(data_path, index=index, frame=f)
        self.keys.append((target.name, data_path, f, interpolation))
        return ok

    def cut(self, when, camera, name=None):
        m = self.scene.timeline_markers.new(name or f'cut_{camera.name}', frame=int(when))
        m.camera = camera
        if self.scene.camera is None:
            self.scene.camera = camera
        self.cuts.append((int(when), camera.name))
        return m


from eidoblend import sets as SETS  # noqa: E402

for m in list(scene.timeline_markers):
    scene.timeline_markers.remove(m)
scene.frame_start = 1
hctx = HarnessCtx(scene)
cs = SETS.build('unknown_force.city', hctx, rain_count=300)
check('registry build(ctx): the set, its keys readable as attributes', cs.parts is cs['parts'] and
      cs.group.name.startswith('set:city') and callable(cs.animate) and callable(cs.make_cameras))
U = cs.parts.uniforms
check('a ctx build routes the kit\'s keys through ctx.key', U.keyer == hctx.key)
cams = cs.make_cameras()
dc = cams.get('dive')
n_cam_keys = sum(1 for k in hctx.keys if k[0] == (dc.name if dc else '') and k[1] == 'location')
check('make_cameras(): the dive, keyed through ctx.key, cut at the start', dc is not None and n_cam_keys == 980 and
      bool(hctx.cuts) and hctx.cuts[0] == (scene.frame_start, dc.name), f'{n_cam_keys} location keys, cuts {hctx.cuts[:2]}')
a0, a1 = cs.animate(lambda t: {'focal': C.dive_focal(t)}, frames=(1, 49))


def uvals(frame, *names):
    scene.frame_set(frame)
    nodes = U.tree.evaluated_get(bpy.context.evaluated_depsgraph_get()).nodes
    out = []
    for n in names:
        if n in KIT.U_VECTORS:
            out.append(tuple(nodes[f'u_{n}_{c}'].outputs[0].default_value for c in KIT.U_VECTORS[n][1]))
        else:
            out.append(nodes['u_' + n].outputs[0].default_value)
    return out if len(out) > 1 else out[0]


t25, fp, cv = uvals(25, 'time', 'focal_pos', 'cam_vel')
check('animate(state, frames): the clock and the focal light on your own clock (the dive\'s focal point)',
      (a0, a1) == (1, 49) and abs(t25 - 1.0) < 1e-4 and max(abs(a - b) for a, b in zip(fp, C.dive_focal(1.0))) < 1e-3,
      f't {t25:.4f}, focal {tuple(round(v, 3) for v in fp)}')
cv_want = KIT.cam_velocity(C.dive_cam, 1.0)
cv_err = max(abs(a - b) for a, b in zip(cv, cv_want)) / max(1e-6, max(abs(v) for v in cv_want))
check('animate: the rain streaks along the camera that renders the frame (the keyed dive, by its marker)',
      cv_err < 0.03, f'{tuple(round(v, 2) for v in cv)} vs {tuple(round(v, 2) for v in cv_want)}')
dcp = dc.evaluated_get(bpy.context.evaluated_depsgraph_get()).matrix_world.translation
check('the dive camera at frame 25 = dive_cam(1.0)', max(abs(a - b) for a, b in zip(dcp, C.dive_cam(1.0)['pos'])) < 1e-3)
F0 = 3000                                    # the lights going out one by one, 5 s into a 30 s stretch
cs.animate(lambda t: {'power': C.turn_down(t, 5.0, 24.0), 'focal': H.chest()}, frames=(F0, F0 + 24 * 30))
pw, fpo = uvals(F0 + int(round(23.5 * 24)), 'power', 'focal_pos')
want_pw = 1 - 0.85 * KIT.smooth((23.5 - 5.0) / 24)
check('animate: turn_down(t, start, length) keyed (1 - 0.85 smooth((t - start) / length)), the focal held on chest()',
      abs(pw - want_pw) < 2e-3 and max(abs(a - b) for a, b in zip(fpo, H.chest())) < 1e-4, f'{pw:.4f} vs {want_pw:.4f}')
hold = uvals(F0 + 60, 'power')
n_pw = sum(1 for k in hctx.keys if k[1] == 'nodes["u_power"].outputs[0].default_value' and F0 <= k[2] <= F0 + 720)
check('animate: a held value is not ramped (power exactly 1 before the turn-down) and holds take two keys',
      hold == 1.0 and n_pw < 24 * 24 + 8, f'power {hold} at 2.5 s, {n_pw} power keys over 721 frames')
cs.animate(lambda t: {'flash': 1.0 if 1.0 <= t < 1.125 else 0.0}, frames=(4000, 4048))
fl = [round(uvals(f, 'flash'), 4) for f in (4012, 4023, 4024, 4026, 4027, 4040)]
check('animate: a step (a lightning flash) stays a step', fl == [0.0, 0.0, 1.0, 1.0, 0.0, 0.0], str(fl))
mover = bpy.data.objects.new('focal_mover', None)
scene.collection.objects.link(mover)
mover.location = (0.0, 0.0, 20.0)
mover.keyframe_insert('location', frame=4500)
mover.location = (24.0, 0.0, 20.0)
mover.keyframe_insert('location', frame=4524)
KIT._set_interp(mover, 'location', 4500, 'LINEAR')
KIT._set_interp(mover, 'location', 4524, 'LINEAR')
cs.animate({'focal': mover}, frames=(4500, 4524), camera=False)
fm = uvals(4512, 'focal_pos')
check('animate: the focal light follows an object', abs(fm[0] - 12.0) < 1e-3 and abs(fm[2] - 20.0) < 1e-3, str(fm))
try:
    cs.animate({'sparkle': 1.0}, frames=(4600, 4601))
    check('animate: an unknown control is refused', False)
except KeyError as e:
    check('animate: an unknown control is refused', 'sparkle' in str(e))
cs.update(2.0, {'power': 0.5, 'focal': (1.0, 2.0, 3.0), 'focal_col': '#ff8800'})
check('update(t, state): a still sets the controls the state names', abs(U['power'] - 0.5) < 1e-6 and
      max(abs(a - b) for a, b in zip(U['focal_pos'], (1, 2, 3))) < 1e-6 and
      abs(U['focal_col'][1] - KIT.srgb_lin('#ff8800')[1]) < 1e-6)
U['power'] = 1.0
bpy.data.objects.remove(mover)
shots = cs.make_cameras(shots=[('spiral', 5000, 5288), ('close_sing', 5289, 5529)])
scene.frame_set(5000 + 144)
dg = bpy.context.evaluated_depsgraph_get()
sp = shots['spiral'].evaluated_get(dg).matrix_world.translation
check('make_cameras(shots): the hole\'s camera moves keyed and cut', set(shots) == {'spiral', 'closeSing'} and
      max(abs(a - b) for a, b in zip(sp, H.hole_cam('spiral', 6.0)['pos'])) < 1e-3 and
      (5000, shots['spiral'].name) in hctx.cuts and (5289, shots['closeSing'].name) in hctx.cuts, str(hctx.cuts))
pz = cs.parts.plaza_screen
pz['set_canvas'](title, frame=6000)
pz['reset'](frame=6100)
flag = []
for f in (5999, 6000, 6099, 6100):
    scene.frame_set(f)
    flag.append(pz['material'].node_tree.nodes['custom'].outputs[0].default_value)
check('plaza set_canvas(frame) / reset(frame): a keyed step', flag == [0.0, 1.0, 1.0, 0.0], str(flag))
cs.parts.set_focal((1.0, 2.0, 3.0), {'gain': 0.6, 'radius': 70.0}, frame=7000)
check('set_focal(pos, {gain, radius}) as city.js', abs(U['focal_gain'] - 0.6) < 1e-6 and abs(U['focal_r'] - 70) < 1e-6)
cs.dispose()
hs = SETS.build('unknown_force.hole', hctx)
reel = hs.make_cameras()
check('the standalone hole: make_cameras() keys all eight camera moves back to back', len(reel) == 8 and
      list(reel) == H.HOLE_CAMS, ', '.join(reel))
ha = hs.animate(range(100, 130))                 # frames first, as the other sets take them
U = hs.parts.uniforms
t_h = uvals(124, 'time')
check('the standalone hole: animate(frames) keys its own clock (0 s at the first frame)', ha == (100, 129) and
      abs(t_h - 1.0) < 1e-4, f'{ha}, t {t_h:.4f} at frame 124')
hs.dispose()
fails = [n for n, ok in results if not ok]
print(f'[uf-options] {len(results) - len(fails)}/{len(results)} passed' + (f'; FAILED: {fails}' if fails else ''))

"""Probe: THE HOLE built on its own (hole.build() with no kit: its own sky, rain, clouds, signs and street disc), its
screens and tickers redrawn through their API, one of its camera moves keyed, and stills rendered from its eight
camera moves.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 \
        bash run_blender.sh <worktree>/blender/tests/sets_uf_city/test_hole_render.py [--no-render] [--shots a,b]
        [--samples 16] [--res 960x540] [--her] [--vrm path] [--power 1.0] [--compare] [--refs dir]

Checks: the standalone extras; the light map painted with the hole's share only; billboards[0].set_canvas (a still),
billboards[1].set_canvas(frames=...) (a keyed PNG sequence with its hold file), billboards[0].reset(), tickers[1]
.set_items and its keyed speed; key_hole_cam ('spiral', 12 s at 24 fps) against hole_cam; the U.power turn-down; the
cloud deck drawn before every other blended object at each of the eight moves (three's renderOrder 1). Then
the screens and tickers go back to their camps, and the renders use the camera moves (spiral, riseUp, closeSing,
orbit, low, nadir, screens, enter) at mid-move, lit as the WebGPU probe stage lit its standalone hole (focal light at
(0, 0, 3), gain 0.35 over 70 m; the clock at 80 s + the move's time). --her puts a performer on the mark (a VRM) for
scale and for the performer-only lights. --compare writes out/compare_hole_alone_low.png beside the WebGPU probe
stage's fin_standalone_hole.png (from --refs, default <cwd>/work/unknown_force/sets/probes).
"""
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from eidoblend.common import script_args, ASSETS_DIR  # noqa: E402
from eidoblend.sets.unknown_force import citykit as KIT  # noqa: E402
from eidoblend.sets.unknown_force import hole as H  # noqa: E402
from eidoblend.sets import unknown_force as UF  # noqa: E402

OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
args = script_args()


def opt(name, default=None):
    return args[args.index(name) + 1] if name in args else default


RENDER = '--no-render' not in args
SAMPLES = int(opt('--samples', 16))
RES = [int(v) for v in opt('--res', '960x540').split('x')]
results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('[uf-hole] %s %s %s' % ('PASS' if ok else 'FAIL', name, detail), flush=True)


for c in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras,
          bpy.data.node_groups, bpy.data.images, bpy.data.worlds):
    for x in list(c):
        c.remove(x)
for c in list(bpy.data.collections):
    bpy.data.collections.remove(c)
scene = bpy.context.scene
scene.render.resolution_x, scene.render.resolution_y = RES
scene.render.resolution_percentage = 100
scene.render.fps = 24
KIT.eevee_settings(scene, samples=SAMPLES)

# the registry
check('registry lists every UNKNOWN FORCE set', UF.names() == ['city', 'quiet_room', 'hole', 'corridor', 'race', 'showroom',
                                                              'news', 'bin'], str(UF.names()))
check('registry finds the city and the hole on disk', {'city', 'hole'} <= set(UF.available()), str(UF.available()))
check('registry: lazy module access', UF.module('hole') is H and UF.hole is H)

t0 = time.perf_counter()
hole = UF.build('hole', scene=scene)
check('standalone build', True, f'{time.perf_counter() - t0:.1f} s')
P = hole['parts']
K = P['kit']
U = K.U
ex = P['extras']
check('standalone extras: sky, rain, clouds, signs, street', ex is not None and all(k in ex for k in
      ('sky', 'rain', 'clouds', 'signs', 'street')))
P['apply_atmosphere'](scene)
check('the hole\'s world is the scene\'s', scene.world == K.world)
check('standalone signs: the 12 outward ads + 12 Futurist walls', ex['signs']['uf_count'] == 24, str(ex['signs']['uf_count']))
lm = K.lm_canvas
s = lm.shape[0] / (2 * KIT.LM_R)
ctr = lm[int(KIT.LM_R * s), int(KIT.LM_R * s), :3]
far = lm[int((KIT.LM_R + 300) * s), int((KIT.LM_R + 300) * s), :3]
check('light map: the hole\'s share only (lit centre, dark city)', ctr.min() > 100 and far.max() == 0,
      f'centre {ctr.tolist()}, 300 m out {far.tolist()}')
want_ll = {P['her'].name: 'INCLUDE', hole['collection'].name: 'EXCLUDE'}
got_ll = {}
for k in ('screen0', 'screen1', 'screen2', 'screen3', 'kickL', 'kickR'):
    rcl = P['lights'][k].light_linking.receiver_collection
    got_ll[k] = {c.name: rcl.collection_children[i].light_linking.link_state for i, c in enumerate(rcl.children)}
check('screen and kicker lights: the performer only, never the set (even with nobody on the mark)',
      all(v == want_ll for v in got_ll.values()), str(got_ll['screen0']))

# the screens' API
bb = P['billboards']


def title(ctx, w, h):
    ctx.fillStyle = '#05040a'
    ctx.fillRect(0, 0, w, h)
    ctx.fillStyle = '#ffcf8a'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.font = f'{h * 0.3}px "Black Ops One"'
    ctx.fillText('UNKNOWN FORCE', w / 2, h / 2)


bb[0]['set_canvas'](title)
px = np.empty(1024 * 576 * 4, np.float32)
bb[0]['texture'].pixels.foreach_get(px)
gold = (np.abs(px.reshape(-1, 4)[:, :3] - np.array([1.0, 0.81, 0.54])).sum(1) < 0.1).mean()
check('billboard set_canvas: the still is in the image', gold > 0.02, f'{gold:.3f} of the pixels gold')


def count(ctx, w, h, t):
    ctx.fillStyle = '#000'
    ctx.fillRect(0, 0, w, h)
    ctx.fillStyle = '#29e7ff'
    ctx.fillRect(0, 0, w * min(1.0, t / 2.0), h)


seq_dir = OUT / 'hole_billboard_seq'
bb[1]['set_canvas'](count, frames=range(10, 59, 1), fps=24, out_dir=seq_dir)
n_png = len(list(seq_dir.glob('uf_billboard_1_seq_*.png')))
img1 = next(n.image for n in bb[1]['material'].node_tree.nodes if n.type == 'TEX_IMAGE')
check('billboard set_canvas(frames=...): a keyed PNG sequence + hold', img1.source == 'SEQUENCE' and n_png == 50,
      f'{img1.name} {img1.source}, {n_png} files (49 frames + the hold)')
bb[0]['reset']()
bb[0]['texture'].pixels.foreach_get(px)
red = (np.abs(px.reshape(-1, 4)[:, :3] - np.array(KIT.hex_rgb('#ff2a3a')) / 255).sum(1) < 0.12).mean()   # stored sRGB
check('billboard reset: the camp screen is back (GOD in red)', red > 0.02, f'{red:.3f}')
tk = P['tickers'][1]
tk['set_items']([['COULD YOU TURN IT DOWN', '#ff4fd8'], ['?', '#e9f3f1']])
tk['speed'].default_value = 0.05
tk['material'].node_tree.keyframe_insert('nodes["speed"].outputs[0].default_value', frame=1)
check('ticker set_items + keyable speed', tk['material'].node_tree.animation_data is not None)

# one of the camera moves keyed
cam_d = bpy.data.cameras.new('probe_cam')
cam_d.clip_start, cam_d.clip_end = 0.05, 6000.0
cam = bpy.data.objects.new('probe_cam', cam_d)
scene.collection.objects.link(cam)
scene.camera = cam
f0, f1 = H.key_hole_cam(cam, 'spiral', frame_start=1, fps=24)
check('key_hole_cam spiral: 12 s at 24 fps', (f0, f1) == (1, 289), f'{f0}..{f1}')
scene.frame_set(145)
dg = bpy.context.evaluated_depsgraph_get()
want = H.hole_cam('spiral', 6.0)
got = cam.evaluated_get(dg).matrix_world.translation
check('keyed spiral = hole_cam(spiral, 6 s)', (got - Vector(want['pos'])).length < 1e-3, str(tuple(round(v, 3) for v in got)))
fwd = -(cam.evaluated_get(dg).matrix_world.to_3x3() @ Vector((0, 0, 1)))
to_t = (Vector(want['target']) - Vector(want['pos'])).normalized()
check('keyed spiral looks at the mark', fwd.dot(to_t) > 0.9999, f'{fwd.dot(to_t):.6f}')
KIT.U_ALIASES  # (camelCase uniform names are accepted too)
U['power'] = 0.5
check('uniform aliases (camelCase)', abs(U['focalR'] - 230.0) < 1e-6 and U['power'] == 0.5)
U['power'] = float(opt('--power', 1.0))

# a performer on the mark (optional), lit by the screens and kickers through light linking
if '--her' in args:
    try:
        from eidoblend.characters import load_vrm, play_vrma_default
        hits = [Path(opt('--vrm'))] if opt('--vrm') else list(Path(ASSETS_DIR).rglob('claude_suit.vrm'))
        before = set(bpy.data.objects)
        her_h = load_vrm(str(hits[0]), name='uf_singer')
        play_vrma_default(her_h, 'idle', t=0.0)        # idling, as the WebGPU probe stage posed its figure
        new = [o for o in bpy.data.objects if o not in before]
        for o in new:
            if o.type == 'MESH':
                P['her'].objects.link(o)
        # a loaded VRM faces -Y (the characters family's convention): the mark's front, three's +Z
        check('a performer on the mark, idling', bool(new), hits[0].name)
        done, left = KIT.fog_objects(K, [o for o in new if o.type == 'MESH'])
        check('her materials take the haze, as scene.fogNode gave it (see-through ones keeping their alpha)',
              done > 0 and left == 0, f'{done} wrapped, {left} left')
    except Exception as e:                              # noqa: BLE001
        check('a performer on the mark', False, repr(e))

cam2_d = bpy.data.cameras.new('probe_cam_still')
cam2_d.clip_start, cam2_d.clip_end = 0.05, 6000.0
cam2 = bpy.data.objects.new('probe_cam_still', cam2_d)
scene.collection.objects.link(cam2)
# The cloud deck drawn first, as three's renderOrder 1 drew it, at each of the eight moves. EEVEE draws blended objects
# back to front by their origins along the view; in its own order the deck veiled the additive pillar of light where
# the view runs level (enter: a dark mottled patch where the pillar meets the far deck).
deck = ex['clouds']['sheets']
scene.camera = cam2
order = {}
for n in H.HOLE_CAMS:
    KIT.apply_cam(cam2, H.hole_cam(n, H.HOLE_CAM_DUR[n] * 0.5))
    dg = bpy.context.evaluated_depsgraph_get()
    m = cam2.evaluated_get(dg).matrix_world
    cp, fw = m.translation.copy(), -(m.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
    others = {}
    for o in scene.objects:
        if o.type != 'MESH' or o.hide_render or o in deck:
            continue
        ms = [sl.material for sl in o.material_slots if sl.material]
        ms += [mt for mt in getattr(o.evaluated_get(dg).data, 'materials', []) if mt]
        if any(getattr(mt, 'surface_render_method', '') == 'BLENDED' for mt in ms):
            others[o.name] = (o.evaluated_get(dg).matrix_world.translation - cp).dot(fw)
    order[n] = (min((s.evaluated_get(dg).matrix_world.translation - cp).dot(fw) for s in deck), others)
check('the cloud deck is drawn first at every move (its origins deeper along the view than every other blended '
      'object\'s, as three\'s renderOrder 1 drew it)',
      all(v[1] and v[0] > max(v[1].values()) for v in order.values()),
      'deck >= %.0f m; others <= %.0f m (%s)' % (min(v[0] for v in order.values()),
                                                  max(max(v[1].values(), default=0.0) for v in order.values()),
                                                  ', '.join(sorted(order['enter'][1]))))
scene.camera = cam
shots = [n for n in H.HOLE_CAMS]
if opt('--shots'):
    shots = [n for n in shots if any(k in n for k in opt('--shots').split(','))]
# back to the camps for the renders (the set's default screens and tickers, their scroll speeds)
bb[1]['reset']()
tk['set_items'](H.TICKERS[1])
tk['material'].node_tree.animation_data_clear()
tk['speed'].default_value = -(0.012 + 0.004 * 1)
times = []
if RENDER:
    scene.camera = cam2
    scene.render.image_settings.file_format = 'PNG'
    for n in shots:
        tt = H.HOLE_CAM_DUR[n] * 0.5
        KIT.apply_cam(cam2, H.hole_cam(n, tt))
        scene.frame_set(1)
        hole['update'](80.0 + tt, {'cam_vel': (0, 0, 0)})
        P['set_focal']((0.0, 0.0, 3.0), {'gain': 0.35, 'radius': 70.0})    # as the WebGPU probe stage lit its stills
        path = OUT / f'probe_hole_alone_{n}.png'
        scene.render.filepath = str(path)
        ts = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        times.append(time.perf_counter() - ts)
        if path.exists():
            im = bpy.data.images.load(str(path))
            a = np.empty(im.size[0] * im.size[1] * 4, np.float32)
            im.pixels.foreach_get(a)
            bpy.data.images.remove(im)
            lum = float((a.reshape(-1, 4)[:, :3] @ np.array([0.2126, 0.7152, 0.0722])).mean())
            check(f'render hole alone {n}', np.isfinite(a).all() and lum > 0.01, f'{times[-1]:.1f} s, luma {lum:.3f}')
        else:
            check(f'render hole alone {n}', False, 'no file')
if RENDER and '--compare' in args:
    from PIL import Image, ImageDraw
    ref = Path(opt('--refs', str(Path.cwd() / 'work' / 'unknown_force' / 'sets' / 'probes'))) / 'fin_standalone_hole.png'
    mine = OUT / 'probe_hole_alone_low.png'
    if ref.exists() and mine.exists():
        a = Image.open(ref).convert('RGB')
        b = Image.open(mine).convert('RGB').resize(a.size, Image.LANCZOS)
        sheet = Image.new('RGB', (a.width * 2 + 8, a.height + 28), (12, 12, 14))
        sheet.paste(a, (0, 28))
        sheet.paste(b, (a.width + 8, 28))
        d = ImageDraw.Draw(sheet)
        d.text((8, 7), 'WebGPU (the probe stage): fin_standalone_hole.png', fill=(230, 230, 230))
        d.text((a.width + 16, 7), 'Blender 5.2 EEVEE: probe_hole_alone_low.png', fill=(230, 230, 230))
        sheet.save(OUT / 'compare_hole_alone_low.png')
    check('compare sheet beside the WebGPU standalone hole', (OUT / 'compare_hole_alone_low.png').exists(), str(ref))
fails = [n for n, ok in results if not ok]
print(f'[uf-hole] {len(results) - len(fails)}/{len(results)} passed' + (f'; FAILED: {fails}' if fails else '') +
      (f'; renders {np.mean(times):.1f} s each' if times else ''), flush=True)

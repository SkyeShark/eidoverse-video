"""Probe: the era-2 voice machines of step A (c64, dectalk, desktop2001, mac1984), built by name in EEVEE.

From the main checkout (renders go through the shared GPU slot):
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \\
        <worktree>/blender/tests/voice_machines_a/test_machines.py \\
        [-- --only api,desk,close,crt,voice,mac,scene,lineup,plastic,kit,saved]

api     the registry (props.NAMES, voice_machines.MACHINES / build_machine / load_machine, the lazy loader), each
        machine's parts, update(t, state) keyed per frame (power, gain, LEDs, glow, the C64's blinking cursor, the
        DECtalk's direct leds, the desktop's drive flicker), set_text redraws keyed at their frames, footprints
        against the measured bounds, dispose()  (no render)
desk    each machine at true scale on an oak desk under a warm key light -> out/desk_<name>.png
close   each screen close up (the C64's raster, the Mac's 1-bit window, the desktop's Narrator dialog)
        -> out/close_<name>.png
crt     the C64's CRT switch-on: power 0.02 / 0.12 / 0.3 / 0.6 / 1.0 -> out/crt_switch_on.png (a strip)
voice   the voice-lit parts in a dim room, voice 0 vs 1: the C64's vents + monitor LED, the DECtalk's grille + SPEECH
        LED, the Mac's vents, the desktop's speaker cloth + drive light -> out/voice_<name>_<view>.png (off | on)
mac     the Mac's 1-bit screen near (crisp texels) and far (the dither greys, no moire) -> out/mac_near_far.png
scene   era canvas scenes on the tubes (show_scene: sam_1982 on the C64, mac_1984 on the Mac, desktop_2001 on the
        desktop), then each machine's own drawing back after the range -> out/scene_<name>.png; without t0 a scene
        starts on its range's first frame
lineup  all four side by side on one 3.3 m desk at true scale -> out/lineup_true_scale.png
plastic the kit's runtime plastic (plastic_material, write_curvature) beside the baked C64
        -> out/plastic_runtime_vs_baked.png
kit     the kit's geometry builders and canvas helpers as one new prop (a desktop voice box: rbox case with a printed
        canvas_texture label through planar_uv_facing, a keycap row baked and merged, a lofted rr_points knob, an
        extruded grille plate with rounded holes, a wire along a rounded_polyline), checked against the JS kit's
        numbers (out/parity_kit_js.json, from test_screens_parity.py) and rendered beside a C64
        -> out/kit_voice_box.png
saved   a C64 film saved as a .blend (text changes, the cursor blinking, power and voice keyed), reopened, and a
        frame rendered from the reopened file against the live scene -> out/saved_reopen.png
Prints PASS / FAIL lines for what it measures.
"""
import math
import shutil
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _stage as S  # noqa: E402
from eidoblend import props  # noqa: E402
from eidoblend.props import voice_machines as VM  # noqa: E402

A = S.args()
ONLY = set(A[A.index('--only') + 1].split(',')) if '--only' in A else {
    'api', 'desk', 'close', 'crt', 'voice', 'mac', 'scene', 'lineup', 'plastic', 'kit', 'saved'}
OUT = S.OUT
WORK = OUT / 'work'
MINE = ('c64', 'dectalk', 'desktop2001', 'mac1984')
RENDER = '--no-render' not in A           # --no-render: the kit probe's checks without its two stills (no GPU slot)


def check(ok, what):
    return S.check(what, ok)


def world_bounds(objs):
    bpy.context.view_layer.update()            # objects placed since the last update still have their old matrix
    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for o in objs:
        if o.type != 'MESH':
            continue
        for c in o.bound_box:
            v = o.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, v))
            hi = Vector(map(max, hi, v))
    return lo, hi


def centre_of(o):
    lo, hi = world_bounds([o])
    return (lo + hi) / 2


def place(m, x=0.0, y=0.0):
    """Centre a machine's footprint at (x, y) on the desk top (the registry's centre offset)."""
    cx, cy = VM.MACHINES[m.name]['center']
    m.group.location = (x - cx, y - cy, S.DESK_Z)
    bpy.context.view_layer.update()


def frame_on(sc, cam, objs, az=24.0, el=19.0, lens=45.0, margin=0.08, target=None):
    """Point the camera at the objects' bounds from azimuth az (degrees right of the front, -Y) and elevation el,
    as close as the bounds fit inside the frame with a margin."""
    lo, hi = world_bounds(objs)
    c = (lo + hi) / 2 if target is None else Vector(target)
    cam.data.lens = lens
    d = Vector((math.sin(math.radians(az)) * math.cos(math.radians(el)),
                -math.cos(math.radians(az)) * math.cos(math.radians(el)), math.sin(math.radians(el))))
    corners = [Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    from bpy_extras.object_utils import world_to_camera_view
    dist = 0.3
    for _ in range(200):
        cam.location = c + d * dist
        S.look_at(cam, c)
        bpy.context.view_layer.update()
        ok = all(margin <= p.x <= 1 - margin and margin <= p.y <= 1 - margin and p.z > 0
                 for p in (world_to_camera_view(sc, cam, q) for q in corners))
        if ok:
            break
        dist *= 1.04
    return c, dist


def png_array(p):
    from PIL import Image
    return np.asarray(Image.open(p).convert('RGB')).astype(np.float64)


def strip(paths, out, labels=None, h=270):
    from PIL import Image, ImageDraw
    ims = [Image.open(p).convert('RGB') for p in paths]
    ims = [im.resize((int(im.width * h / im.height), h), Image.Resampling.LANCZOS) for im in ims]
    sheet = Image.new('RGB', (sum(im.width for im in ims) + 6 * (len(ims) - 1), h + 20), (20, 20, 22))
    x = 0
    for i, im in enumerate(ims):
        sheet.paste(im, (x, 20))
        if labels:
            ImageDraw.Draw(sheet).text((x + 4, 4), labels[i], fill=(220, 220, 220))
        x += im.width + 6
    sheet.save(out)
    print(f'[sheet] {out}')
    return out


def fc_value(obj, prop, frame):
    fc = S.fcurve(obj, f'["{prop}"]')
    return None if fc is None else fc.evaluate(frame)


# ------------------------------------------------------------------------------------------------------- api ---
def probe_api():
    # the registry needs no Blender: names, records, the lazy loader
    check(props.NAMES == ['voder', 'mainframe', 'teletype', 'speakspell', 'c64', 'mac1984', 'dectalk',
                          'desktop2001', 'tandem'], f'props.NAMES = the eight machines and the tandem: {props.NAMES}')
    check(VM.NAMES == list(VM.MACHINES) and len(VM.NAMES) == 8, 'voice_machines.NAMES: eight, in index.js order')
    check([VM.MACHINES[n]['year'] for n in VM.NAMES] == [1939, 1961, 1966, 1978, 1982, 1984, 1984, 2001],
          'MACHINES years 1939 -> 2001 as index.js')
    for n in MINE:
        mod = VM.load_machine(n)
        check(callable(getattr(mod, 'build', None)) and props.load(n) is mod, f'load_machine({n!r}) -> its module')
    try:
        VM.load_machine('nope')
        check(False, 'an unknown machine raises')
    except ValueError as e:
        check('unknown machine' in str(e), f'an unknown machine raises: {e}')
    for n in ('voder', 'mainframe', 'teletype', 'speakspell', 'tandem'):      # step B's modules, found by name
        try:
            mod = props.load(n)
            check(callable(getattr(mod, 'build', None)), f'the registry finds {n}: {mod.__name__}.build')
        except ModuleNotFoundError as e:
            check('not written yet' in str(e), f'{n} is registered; its module is not written yet ({e})')
    # built through the registry (their modules are another step's work in progress: reported, not counted)
    S.fresh_scene(frames=(1, 24))
    for n in ('voder', 'mainframe', 'teletype', 'speakspell', 'tandem'):
        try:
            b = props.build(n)
            g = b.group if hasattr(b, 'group') else b['group']
            rec = g.get('voice_machine') if n != 'tandem' else True
            print(f'INFO props.build({n!r}) -> {type(b).__name__}, root {g.name!r}'
                  f'{", stamped " + rec["name"] if n != "tandem" and rec else ""}', flush=True)
        except Exception as e:                                        # noqa: BLE001
            print(f'INFO props.build({n!r}) raised {type(e).__name__}: {e}', flush=True)

    S.fresh_scene(frames=(1, 96))
    built = {}
    import time
    for n in MINE:
        t0 = time.perf_counter()
        m = props.build(n, screen_dir=str(WORK / 'api' / n)) if n != 'c64' else VM.build_machine(
            'c64', {'screen_dir': str(WORK / 'api' / n)})
        t1 = time.perf_counter()
        if m.screens:
            m.screens[0].draw(m.screens[0].pw, m.screens[0].ph)          # a drawing, as a redraw makes it
        t2 = time.perf_counter()
        print(f'  [cost] {n}: built in {t1 - t0:.2f} s (the GLB import included), a screen redraw '
              f'{(t2 - t1) * 1000:.0f} ms' if m.screens else f'  [cost] {n}: built in {t1 - t0:.2f} s', flush=True)
        built[n] = m
        rec = m.group.get('voice_machine')
        check(rec is not None and rec['name'] == n and rec['year'] == VM.MACHINES[n]['year'],
              f'{n}: the root carries its record (voice_machine = {{name, year, ...}})')
        lo, hi = world_bounds(m.objects)
        w, d, h = hi.x - lo.x, hi.y - lo.y, hi.z - lo.z
        fw, fd, fh = VM.MACHINES[n]['footprint']
        cx, cy = VM.MACHINES[n]['center']
        ok = abs(w - fw) < 0.012 and abs(d - fd) < 0.012 and abs(h - fh) < 0.012 and \
            abs((lo.x + hi.x) / 2 - cx) < 0.012 and abs((lo.y + hi.y) / 2 - cy) < 0.012
        check(ok, f'{n}: built bounds {w:.3f} x {d:.3f} x {h:.3f} m centre ({(lo.x + hi.x) / 2:.3f}, '
                  f'{(lo.y + hi.y) / 2:.3f}) = the registry footprint {fw} x {fd} x {fh} centre ({cx}, {cy})')
        check(abs(lo.z) < 0.003, f'{n}: rests on z = 0 of its root (lowest point {lo.z * 1000:.1f} mm)')
        check(all(o.parent == m.group for o in m.objects), f'{n}: every part is parented to the root')
        check(all(len(o.data.materials) and all(mm is not None for mm in o.data.materials) for o in m.objects),
              f'{n}: every part has its materials ({len(m.objects)} parts, {len(m.materials)} runtime materials)')

    # the C64: parts, the boot screen, update keys, the cursor's blink, set_text
    c = built['c64']
    check(set(c.parts) == {'computer', 'keys', 'monitor', 'screen', 'leds', 'speaker'} and
          set(c.parts['leds']) == {'computer', 'monitor'}, f'c64 parts: {sorted(c.parts)}')
    check(c.parts['screen'].lines[1] == '    **** SPEECH BASIC V2 ****', 'c64: boots to the SPEECH BASIC screen')
    for f in range(1, 49):
        t = (f - 1) / 24
        c.update(t, {'power': min(1.0, t), 'voice': 0.5 * (1 + math.sin(t * 9))})
    v = 0.5 * (1 + math.sin((30 - 1) / 24 * 9))
    check(abs(fc_value(c.group, 'gain', 30) - (1 + 0.4 * v)) < 1e-4, 'c64: gain keyed 1 + 0.4 voice at frame 30')
    check(abs(fc_value(c.group, 'power', 13) - 0.5) < 1e-4, 'c64: power keyed per frame (0.5 at t = 0.5 s)')
    check(fc_value(c.group, 'led_monitor', 1) == 0.0 and abs(fc_value(c.group, 'led_monitor', 30) -
                                                             (0.75 + 0.6 * v)) < 1e-4,
          'c64: the monitor LED is off at power 0, 0.75 + 0.6 voice when on')
    check(abs(fc_value(c.group, 'led_computer', 40) - 1.0) < 1e-6, 'c64: the computer LED is on the whole scene')
    scr = c.screens[0]
    # blinking: phase floor(3t) % 2 -> redraws at t = 1/3, 2/3, 1, 4/3, 5/3 (frames 9, 17, 25, 33, 41)
    check(scr.drawn == 6, f'c64: the cursor blinks every 1/3 s: {scr.drawn} drawings over 2 s (1 + 5 redraws)')
    a9, a8 = np.asarray(_png(scr._file(9))), np.asarray(_png(scr._file(8)))
    check(not np.array_equal(a9, a8), 'c64: frame 9 (t = 1/3 s) draws the cursor off')
    c.parts['screen'].set_text(['READY.', 'SAY "I WAS A MOUTH"'], 'solid')
    n0 = scr.drawn
    c.update(50 / 24, {'power': 1, 'voice': 0})
    check(scr.drawn == n0 + 1 and c.parts['screen'].lines == ['READY.', 'SAY "I WAS A MOUTH"'],
          'c64: set_text draws at the next update, keyed at its frame (51)')
    c.update(51 / 24, {'power': 1, 'voice': 0, 'lines': 'hello\nworld', 'cursorOn': False})
    check(c.parts['screen'].lines == ['HELLO', 'WORLD'] and scr.drawn == n0 + 2,
          'c64: update state {lines, cursorOn} (JS camelCase) sets the text, upper-cased')
    check(c.screens[0].image.source == 'SEQUENCE' and int(c.screens[0].image['eido_frame_duration']) == 52,
          f'c64: the screen is a {c.screens[0].image["eido_frame_duration"]}-frame PNG sequence')

    # the DECtalk: leds by update, the direct leds list, a Lamp keyed by hand
    dt = built['dectalk']
    check([x.name for x in dt.parts['leds']] == ['power', 'speech', 'back'] and dt.parts['speaker'].mesh,
          'dectalk parts: box, leds [power, speech, back], speaker')
    dt.update(0.0, {'power': 1, 'voice': 0.2})
    dt.update(1.0, {'power': 1, 'voice': 0.8})
    dt.update(2.0, {'leds': [0.0, 0.3, 1.0]})
    dt.update(3.0, {'power': 0, 'voice': 1})
    check(abs(fc_value(dt.group, 'led_speech', 1) - 0.08) < 1e-4 and
          abs(fc_value(dt.group, 'led_speech', 25) - (0.55 + 0.9 * 0.8)) < 1e-4,
          'dectalk: SPEECH = 0.4 voice when quiet, 0.55 + 0.9 voice when speaking')
    check(fc_value(dt.group, 'led_power', 49) == 0.0 and abs(fc_value(dt.group, 'led_speech', 49) - 0.3) < 1e-6
          and abs(fc_value(dt.group, 'speaker', 49) - 0.72) < 1e-6,
          'dectalk: update {leds: [...]} drives the LEDs directly (and leaves the speaker as it was)')
    check(fc_value(dt.group, 'led_back', 73) == 0.0 and fc_value(dt.group, 'speaker', 73) == 0.0,
          'dectalk: power 0 darkens every lamp')
    dt.parts['leds'][1].set(0.9, t=3.5)
    check(abs(fc_value(dt.group, 'led_speech', 85) - 0.9) < 1e-6, 'dectalk: parts.leds[1].set(v, t) keys one LED')

    # the Mac: options, set_text, voice
    mac = built['mac1984']
    check(mac.parts['screen'].text == 'hello' and mac.title == 'Note', 'mac1984: opens with "hello" in a Note')
    mac.update(0.0, {'power': 1, 'voice': 0})
    d0 = mac.screens[0].drawn
    mac.update(0.5, {'power': 1, 'voice': 1, 'text': 'I was\na mouth'})
    check(mac.screens[0].drawn == d0 + 1 and abs(fc_value(mac.group, 'gain', 13) - 1.3) < 1e-6 and
          abs(fc_value(mac.group, 'speaker', 13) - 0.8) < 1e-6, 'mac1984: text redraws; voice -> gain 1.3, vents 0.8')
    mac2 = VM.build_machine('mac1984', title='MacinTalk', text='hi', screen_dir=str(WORK / 'api' / 'mac2'))
    check(mac2.parts['screen'].text == 'hi' and mac2.title == 'MacinTalk', 'mac1984: build(title=, text=) options')
    mac2.dispose(files=True)

    # the desktop: LEDs, the drive flicker, the cloth
    pc = built['desktop2001']
    check(set(pc.parts['leds']) == {'mon', 'tw_power', 'tw_hdd', 'tw_cd', 'spk', 'kb0', 'kb1', 'kb2'},
          f'desktop2001 leds: {sorted(pc.parts["leds"])}')
    flick = [pc.drive_flicker((f - 1) / 24) for f in range(1, 97)]
    for f in range(1, 97):
        pc.update((f - 1) / 24, {'power': 1, 'voice': 0.6})
    vals = [fc_value(pc.group, 'led_tw_hdd', f) for f in range(1, 97)]
    check(np.allclose(vals, flick) and 0.1 in flick and 1.0 in flick,
          f'desktop2001: the drive light flickers with speech ({sum(x == 1.0 for x in flick)} of 96 frames lit)')
    pc.update(4.0, {'power': 0.0, 'voice': 0.0})
    check(abs(fc_value(pc.group, 'led_mon', 97) - 0.15) < 1e-6 and fc_value(pc.group, 'led_tw_power', 97) == 1.0,
          'desktop2001: power off -> the monitor LED dims to 0.15, the tower stays on')
    pc2 = VM.build_machine('desktop2001', title='Narrator', clock='11:59 PM', text='two\nlines',
                           screen_dir=str(WORK / 'api' / 'pc2'))
    check(pc2.clock == '11:59 PM' and pc2.parts['screen'].text == 'two\nlines', 'desktop2001: build(clock=, text=)')
    pc2.dispose(files=True)

    # every screen_material option builds its nodes (parallax, glow, flip and the node overrides are the kit's
    # options the Speak & Spell and other machines use; the four here use the rest)
    scr0 = c.screens[0]
    full = VM.screen_material('opts_probe', scr0, c.group, gain_k=0.5, window=(0.1, 0.1, 0.9, 0.9), parallax=0.003,
                              face_size=(0.2, 0.1), barrel=0.04, scan=200, scan_amt=0.3, corner=0.05, vignette=0.2,
                              tint='#eef3ff', bleed=0.001, glow='#203040', crt_on=True, flip=True, tube_height=0.2,
                              color_node=lambda nb, b: VM.lin('#101214'), roughness_node=lambda nb, b: 0.4,
                              coat_node=lambda nb, b: 0.8)
    kinds = {n.bl_idname for n in full.node_tree.nodes}
    need = {'ShaderNodeVectorTransform', 'ShaderNodeTexImage', 'ShaderNodeCameraData', 'ShaderNodeMapRange',
            'ShaderNodeBsdfPrincipled'}
    b = next(n for n in full.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled')
    check(need <= kinds and b.inputs['Emission Strength'].is_linked and
          abs(b.inputs['Roughness'].default_value - 0.4) < 1e-6,
          f'screen_material: every option builds ({len(full.node_tree.nodes)} nodes: the parallax view transform, '
          f'the scanline footprint, the switch-on, glow, the overrides)')
    images = sum(1 for n in full.node_tree.nodes if n.bl_idname == 'ShaderNodeTexImage')
    check(images == 3, f'screen_material: bleed samples the drawing three times ({images} image nodes)')
    bpy.data.materials.remove(full)
    # every driver a machine made is a one-variable AVERAGE with no path through the scene's camera pointer (a
    # driver first evaluated before the scene has a camera is switched off by Blender for good, and a scripted one
    # needs Python in the reopened blend)
    bad = []
    for mat in bpy.data.materials:
        ad = mat.node_tree.animation_data if mat.node_tree else None
        for fc in (ad.drivers if ad else ()):
            d = fc.driver
            if d.type != 'AVERAGE' or len(d.variables) != 1 or 'camera' in d.variables[0].targets[0].data_path:
                bad.append(f'{mat.name}: {fc.data_path}')
    check(not bad, f'machine drivers: one-variable AVERAGE drivers only, none through scene.camera '
                   f'({len(bad)} others{": " + ", ".join(bad[:3]) if bad else ""})')

    # dispose: everything this machine made leaves the blend; the shared source too when no machine uses it
    mats = [x.name for x in dt.materials]
    dt.dispose()
    check(not any(o.get('vm_machine') == 'dectalk' or o.name.startswith('vmsrc.dectalk') for o in bpy.data.objects)
          and not any(x in bpy.data.materials for x in mats),
          'dectalk.dispose(): its objects, runtime materials and imported source are gone')
    check(not any(c.get('eido_vm_source') == 'dectalk' for c in bpy.data.collections),
          'dispose(): the last DECtalk takes the imported source collection with it')
    two = VM.build_machine('c64', name='c64_b', screen_dir=str(WORK / 'api' / 'c64_b'))
    src_meshes = {o.data.name for o in VM.load_glb('c64').values()}
    check(two.parts['computer'].data.name in src_meshes and two.parts['computer'].data == c.parts['computer'].data,
          'a second C64 shares the baked meshes and maps of the first (one import per blend)')
    two.dispose(files=True)
    check(any(c2.get('eido_vm_source') == 'c64' for c2 in bpy.data.collections),
          'disposing the second C64 keeps the source the first still uses')


def _png(p):
    from PIL import Image
    return Image.open(p).convert('RGB')


# ------------------------------------------------------------------------------------------------- the renders ---
def stage(frames=(1, 48), samples=16, res=(960, 540)):
    sc = S.fresh_scene(res=res, samples=samples, frames=frames)
    S.desk_room(sc)
    return sc


def probe_desk_and_close():
    """Each machine at true scale on the desk under a key light, then its screen close up."""
    states = {'c64': {'power': 1, 'voice': 0.35, 'lines': ['', '    **** SPEECH BASIC V2 ****', '',
                                                            ' 64K RAM SYSTEM  38911 BASIC BYTES FREE', '', 'READY.',
                                                            'SAY "I WAS A MOUTH"', 'I WAS A MOUTH', 'READY.']},
              'dectalk': {'power': 1, 'voice': 0.5}, 'mac1984': {'power': 1, 'voice': 0.2},
              'desktop2001': {'power': 1, 'voice': 0.4, 'text': 'reading screens'}}
    views = {'c64': (22, 18, 40), 'dectalk': (20, 24, 50), 'mac1984': (24, 16, 40), 'desktop2001': (18, 17, 35)}
    for n in MINE:
        if not ONLY & {'desk', 'close'}:
            break
        sc = stage()
        m = VM.build_machine(n, screen_dir=str(WORK / 'desk' / n))
        place(m)
        m.update(0.0, states[n])
        cam = S.camera(sc, (0, -1, 1), (0, 0, 1))
        az, el, lens = views[n]
        c, dist = frame_on(sc, cam, m.objects, az=az, el=el, lens=lens)
        S.key_light(sc, c, dist=1.25, power=60.0)
        if 'desk' in ONLY:
            p = S.render(OUT / f'desk_{n}.png', 1)
            a = png_array(p)
            check(S.magenta_fraction(p) == 0.0 and a.std() > 12, f'desk {n}: rendered, no magenta, std {a.std():.1f}')
            if m._tubes:
                tube = m._tubes[0]['tube']
                x, y = S.project(sc, cam, centre_of(tube))
                mean = S.region_mean(p, (x - 12, y - 8, x + 12, y + 8))
                check(mean.max() > 60, f'desk {n}: the screen is lit (centre sRGB {np.round(mean).tolist()})')
            if n == 'mac1984':
                # the 50 % desktop between the screen's left edge and the window (canvas x 8..58, y 75..195: below
                # the menu bar, left of the window that starts at x 73), seen at about five texels a pixel: an even
                # grey, as the engine's mipmapped minification made it, not the moire bands of an aliased dither or
                # of scanlines finer than a pixel. (canvas x -> tube x: (0.0485 + x / 512 x 0.903 - 0.5) / 5;
                # canvas y -> tube z: (0.901 - y / 342 x 0.794 + 0.9737) / 6.5789 - 0.224, the GLB's UV map)
                ct = centre_of(m._tubes[0]['tube'])
                (x0, y0), (x1, y1) = (S.project(sc, cam, ct + Vector((-0.0875, 0.0, 0.0345))),
                                      S.project(sc, cam, ct + Vector((-0.0698, 0.0, -0.0079))))
                patch = a[int(min(y0, y1)) + 2:int(max(y0, y1)) - 2, int(min(x0, x1)) + 2:int(max(x0, x1)) - 2]
                lum = patch.mean(axis=2)
                check(lum.size > 100 and lum.std() < 9.0, f'desk mac1984: the dithered desktop reads as an even grey '
                                                          f'(std {lum.std():.1f} over {lum.shape[1]} x {lum.shape[0]} px)')
        if 'close' in ONLY and m._tubes:
            tube = m._tubes[0]['tube']
            ct = centre_of(tube)
            lo, hi = world_bounds([tube])
            cam.data.lens = 50
            cam.location = ct + Vector((0.08, -1.0, 0.12)).normalized() * max(hi.x - lo.x, 0.2) * 2.3
            S.look_at(cam, ct)
            p = S.render(OUT / f'close_{n}.png', 1)
            check(S.magenta_fraction(p) == 0.0, f'close {n}: rendered, no magenta')


def probe_crt():
    """The C64's CRT switch-on, keyed on frames 1-5, rendered close up."""
    sc = stage(frames=(1, 5))
    m = VM.build_machine('c64', screen_dir=str(WORK / 'crt'))
    place(m)
    powers = (0.02, 0.12, 0.3, 0.6, 1.0)
    for i, p in enumerate(powers):
        m.update(i / 24, {'power': p, 'voice': 0.0})
    tube = m._tubes[0]['tube']
    ct = centre_of(tube)
    cam = S.camera(sc, ct + Vector((0.05, -0.62, 0.08)), ct, lens=50)
    S.key_light(sc, ct, dist=1.2, power=40.0)
    paths = [S.render(WORK / f'crt_{i + 1}.png', i + 1) for i in range(5)]
    strip(paths, OUT / 'crt_switch_on.png', [f'power {p}' for p in powers], h=240)
    x, y = S.project(sc, cam, ct)
    cols = [png_array(pth).mean(axis=2)[:, int(x) - 30:int(x) + 30].mean(axis=1) for pth in paths]
    # the raster's own light over the nearly dark tube of power 0.02 (the glass and its reflections cancel), one
    # threshold for every frame: the lit band's height, first to last lit row
    diffs = [c - cols[0] for c in cols[1:]]
    thr = 0.15 * max(d.max() for d in diffs)
    band = []
    for d in diffs:
        lit = np.nonzero(d > thr)[0]
        band.append(int(lit[-1] - lit[0] + 1) if len(lit) else 0)
    check(0 < band[0] < band[1] < band[2] and band[3] >= band[2] - 2,
          f'crt: the raster opens from a line as power rises (lit band at power 0.12 / 0.3 / 0.6 / 1.0: {band} rows)')


def screen_box(sc, cam, o, pad=2):
    """The pixel box (x0, y0, x1, y1) the object's bounds cover in the render."""
    bpy.context.view_layer.update()
    pts = [S.project(sc, cam, o.matrix_world @ Vector(c)) for c in o.bound_box]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    W, H = sc.render.resolution_x, sc.render.resolution_y
    return (max(0, int(min(xs)) - pad), max(0, int(min(ys)) - pad), min(W, int(max(xs)) + pad + 1),
            min(H, int(max(ys)) + pad + 1))


def probe_voice():
    """Voice 0 vs 1 in a dim room: the lit vents, cloth, grille and LEDs, measured inside each part's projected
    bounds (the brightest 1 % of its pixels: the vents are slots, the LEDs a few pixels)."""
    # (machine, view tag): the parts measured, and az, el, lens, the parts to frame (side vents from the side)
    shots = [('c64', 'side', ['glow_vents'], (84, 8, 50, ('c64_mon',))),
             ('c64', 'front', ['led_mon_power'], (12, 16, 45, None)),
             ('dectalk', 'front', ['glow_grille', 'led_speech'], (10, 22, 50, None)),
             ('mac1984', 'side', ['glow_vents'], (84, 6, 50, ('mac_body',))),
             ('desktop2001', 'front', ['glowcloth_spk', 'led_tw_hdd'], (8, 12, 40, None))]
    for n, tag, parts, view in shots:
        sc = stage(frames=(1, 2))
        m = VM.build_machine(n, screen_dir=str(WORK / 'voice' / n))
        place(m)
        m.update(0.0, {'power': 1, 'voice': 0.0})
        m.update(1 / 24, {'power': 1, 'voice': 1.0})
        if n == 'desktop2001':                  # make sure the drive light is in its lit phase on frame 2
            m.parts['leds']['tw_hdd'].set(1.0, frame=2)
        cam = S.camera(sc, (0, -1, 1), (0, 0, 1))
        az, el, lens, frame_parts = view
        objs = [o for o in m.objects if frame_parts is None or o.name.split('.')[0] in frame_parts]
        c, dist = frame_on(sc, cam, objs, az=az, el=el, lens=lens)
        S.key_light(sc, c, dist=1.3, power=8.0)
        sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.3
        p0, p1 = S.render(WORK / f'voice_{n}_{tag}_0.png', 1), S.render(WORK / f'voice_{n}_{tag}_1.png', 2)
        strip([p0, p1], OUT / f'voice_{n}_{tag}.png', ['voice 0', 'voice 1'], h=360)
        a0, a1 = png_array(p0), png_array(p1)
        for part in parts:
            o = next(o for o in m.objects if o.name.split('.')[0] == part)
            x0, y0, x1, y1 = screen_box(sc, cam, o)
            r0, r1 = a0[y0:y1, x0:x1].sum(axis=2), a1[y0:y1, x0:x1].sum(axis=2)
            if not r0.size:
                check(False, f'voice {n}: {part} is in frame')
                continue
            q0, q1 = np.percentile(r0, 99), np.percentile(r1, 99)
            check(q1 > q0 * 1.15 + 20, f'voice {n}: {part} brightens with the voice (its brightest pixels '
                                       f'{q0 / 3:.0f} -> {q1 / 3:.0f})')


def probe_mac():
    """The 1-bit screen magnified (crisp) and minified (grey, no moire)."""
    sc = stage(frames=(1, 1))
    m = VM.build_machine('mac1984', screen_dir=str(WORK / 'mac'))
    place(m)
    m.update(0.0, {'power': 1, 'voice': 0})
    tube = m._tubes[0]['tube']
    ct = centre_of(tube)
    S.key_light(sc, ct, dist=1.3, power=40.0)
    cam = S.camera(sc, ct + Vector((0.0, -0.11, 0.0)), ct, lens=50)
    near = S.render(WORK / 'mac_near.png', 1)
    cam.location = ct + Vector((0.25, -2.6, 0.35))
    S.look_at(cam, ct)
    cam.data.lens = 50
    far = S.render(WORK / 'mac_far.png', 1)
    strip([near, far], OUT / 'mac_near_far.png', ['near: crisp 1-bit texels', 'far: the dither averages'], h=360)
    a = png_array(near).mean(axis=2)
    h, w = a.shape
    patch = a[h // 2 - 120:h // 2 + 120, w // 2 - 200:w // 2 + 200]
    hist = np.histogram(patch, bins=16, range=(0, 256))[0] / patch.size
    check(hist[:4].sum() > 0.08 and hist[-6:].sum() > 0.08,
          f'mac near: crisp black and white texels (dark {hist[:4].sum():.2f}, light {hist[-6:].sum():.2f})')
    x, y = S.project(sc, cam, ct + Vector((-0.075, 0, 0.02)))      # canvas (43, 114): the dithered desktop
    b = png_array(far).mean(axis=2)[int(y) - 3:int(y) + 3, int(x) - 3:int(x) + 3]
    check(b.std() < 18, f'mac far: the desktop dither reads as an even grey (std {b.std():.1f})')


def probe_scene():
    """Era canvas scenes on the tubes over frames 1-2 (1.6 s into each scene's own clock), the machines' own
    drawings from frame 3; and show_scene's default start: a scene shown later in the film plays from its own
    beginning."""
    from eidoblend.media import screens as MS
    pairs = (('c64', 'sam_1982'), ('mac1984', 'mac_1984'), ('desktop2001', 'desktop_2001'))
    from eidoblend.media.timebase import Timebase
    for n, scene_name in pairs:
        sc = stage(frames=(1, 3))
        tb = Timebase.of(sc)
        m = VM.build_machine(n, screen_dir=str(WORK / 'scene' / n))
        place(m)
        for f in (1, 2, 3):
            m.update(tb.t(f), {'power': 1, 'voice': 0.3})
        layer = m.show_scene(scene_name, (1, 2), t0=tb.t(1) - 1.6)         # frame 1 = 1.6 s into the scene
        check(layer.image.source == 'SEQUENCE' and fc_value(m.group, 'scene_0', 1) == 1.0 and
              fc_value(m.group, 'scene_0', 3) == 0.0, f'scene {scene_name} on {n}: baked, keyed 1 on frames 1-2, '
                                                      f'0 from frame 3 ({layer.px_size[0]} x {layer.px_size[1]})')
        tube = m._tubes[0]['tube']
        ct = centre_of(tube)
        lo, hi = world_bounds([tube])
        S.camera(sc, ct + Vector((0.06, -1.0, 0.1)).normalized() * (hi.x - lo.x) * 2.4, ct, lens=50)
        S.key_light(sc, ct, dist=1.2, power=40.0)
        p2, p3 = S.render(WORK / f'scene_{n}_2.png', 2), S.render(WORK / f'scene_{n}_3.png', 3)
        strip([p2, p3], OUT / f'scene_{n}.png', [f'{scene_name} (show_scene)', 'its own drawing after'], h=360)
        d = np.abs(png_array(p2) - png_array(p3)).mean()
        check(d > 6 and S.magenta_fraction(p2) == 0.0, f'scene {n}: the scene and the drawing differ '
                                                      f'(mean |diff| {d:.1f}), no magenta')
        if n == 'c64':                 # without t0 the scene starts at the range's first frame, wherever that is
            seen, real = {}, MS.bake_canvas_scene

            def spy(*a, **k):
                seen.update(k)
                return real(*a, **k)
            MS.bake_canvas_scene = spy
            try:
                m.show_scene(scene_name, (3, 3))
            finally:
                MS.bake_canvas_scene = real
            check(seen.get('t0') is not None and abs(seen['t0'] - tb.t(3)) < 1e-9,
                  f'show_scene without t0: the scene starts on the range\'s first frame (t0 {seen.get("t0")} s = '
                  f'frame 3 at {tb.t(3):.4f} s)')


def probe_lineup():
    """All four on one 3.3 m desk, at true scale side by side: the desktop, the Macintosh, the C64, the DECtalk."""
    sc = S.fresh_scene(frames=(1, 1))
    S.desk_room(sc, width=3.3, depth=0.9)
    xs = {'desktop2001': -1.02, 'mac1984': 0.02, 'c64': 0.62, 'dectalk': 1.25}
    states = {'desktop2001': {'power': 1, 'voice': 0.5, 'text': 'reading screens'},
              'mac1984': {'power': 1, 'voice': 0.3, 'text': 'hello'},
              'c64': {'power': 1, 'voice': 0.4, 'lines': ['READY.', 'SAY "I WAS A MOUTH"', 'I WAS A MOUTH', 'READY.']},
              'dectalk': {'power': 1, 'voice': 0.6}}
    objs = []
    for n, x in xs.items():
        m = VM.build_machine(n, screen_dir=str(WORK / 'lineup' / n))
        place(m, x, 0.0)
        m.update(0.0, states[n])
        objs += m.objects
    cam = S.camera(sc, (0, -1, 1), (0, 0, 1))
    c, dist = frame_on(sc, cam, objs, az=8, el=14, lens=40, margin=0.05)
    S.key_light(sc, c, dist=1.6, power=110.0, size=0.8)
    p = S.render(OUT / 'lineup_true_scale.png', 1)
    lo, hi = world_bounds(objs)
    check(S.magenta_fraction(p) == 0.0 and abs(lo.z - S.DESK_Z) < 0.003,
          f'lineup: four machines on one desk, all resting on its top ({(lo.z - S.DESK_Z) * 1000:.1f} mm)')


def probe_plastic():
    """The kit's runtime plastic (plastic_material + write_curvature) on bevelled shapes beside the baked C64: a
    yellowed beige case with a printed label, a dark keycap-like block, a clear-coated knob."""
    import bmesh
    from PIL import Image as PImage, ImageDraw
    sc = stage(frames=(1, 1))
    c = VM.build_machine('c64', screen_dir=str(WORK / 'plastic' / 'c64'))
    place(c, 0.3, 0.0)
    c.update(0.0, {'power': 1, 'voice': 0.2})

    def bevelled(name, size, loc, radius, segs=4):
        me = bpy.data.meshes.new(name)
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
        bmesh.ops.bevel(bm, geom=list(bm.edges) + list(bm.verts), offset=radius, segments=segs, profile=0.5,
                        affect='EDGES')
        uv = bm.loops.layers.uv.new('UVMap')
        for f in bm.faces:                                     # the front (-Y) projected 0..1 for the label
            for lp in f.loops:
                lp[uv].uv = ((lp.vert.co.x / size[0]) + 0.5, (lp.vert.co.z / size[2]) + 0.5)
        bm.to_mesh(me)
        bm.free()
        for p in me.polygons:
            p.use_smooth = True
        o = bpy.data.objects.new(name, me)
        sc.collection.objects.link(o)
        o.location = loc
        return o
    label = PImage.new('RGBA', (512, 128), (0, 0, 0, 0))
    d = ImageDraw.Draw(label)
    d.rounded_rectangle([40, 40, 472, 100], 10, fill=(40, 38, 36, 255))
    d.text((256, 72), 'VOICE  KIT  EIDO-82', fill=(225, 210, 170, 255), anchor='mm', font=VM.font('Arial', 30))
    img = bpy.data.images.new('plastic_label', 512, 128, alpha=True)
    img.pixels.foreach_set((np.asarray(label.transpose(PImage.Transpose.FLIP_TOP_BOTTOM), np.float32) / 255).ravel())
    img.pack()
    case = bevelled('plastic_case', (0.30, 0.18, 0.07), (-0.25, -0.05, S.DESK_Z + 0.035), 0.012)
    key = bevelled('plastic_key', (0.05, 0.05, 0.03), (-0.25, -0.09, S.DESK_Z + 0.085), 0.006)
    knob = bevelled('plastic_knob', (0.04, 0.04, 0.025), (-0.15, -0.06, S.DESK_Z + 0.0825), 0.011, segs=6)
    for o in (case, key, knob):
        tr = VM.write_curvature(o)
        check(len(tr) and np.percentile(tr, 99) > 30, f'write_curvature({o.name}): the bevels read convex '
                                                      f'(99th percentile {np.percentile(tr, 99):.0f} / m)')
    case.data.materials.append(VM.plastic_material('beige_aged', color='#d6ccb0', aged='#c9b27a', age_amt=0.6,
                                                   decal=img, decal_rough=0.35))
    key.data.materials.append(VM.plastic_material('keycap_dark', color='#4a423a', rough=0.45, grime_amt=0.8))
    knob.data.materials.append(VM.plastic_material('knob_coat', color='#8f1d16', clearcoat=1.0, rough=0.35))
    cam = S.camera(sc, (0, -1, 1), (0, 0, 1))
    frame_on(sc, cam, [case, key, knob] + c.objects, az=18, el=24, lens=45)
    S.key_light(sc, Vector((0.0, 0.0, S.DESK_Z + 0.1)), dist=1.2, power=45.0)
    p = S.render(OUT / 'plastic_runtime_vs_baked.png', 1)
    check(S.magenta_fraction(p) == 0.0, 'plastic: the runtime plastic renders beside the baked C64')


def probe_saved():
    """A C64 film saved, reopened and rendered: the keys and the screen sequence carry it."""
    sc = stage(frames=(1, 60))
    m = VM.build_machine('c64', screen_dir=str(WORK / 'saved' / 'screens'))
    place(m)
    script = [(0.0, ['READY.']), (1.0, ['READY.', 'SAY "DAISY"']), (2.0, ['READY.', 'SAY "DAISY"', 'DAISY'])]
    k = 0
    for f in range(1, 61):
        t = (f - 1) / 24
        while k < len(script) and script[k][0] <= t:
            m.parts['screen'].set_text(script[k][1], True)
            k += 1
        m.update(t, {'power': min(1.0, t / 0.6), 'voice': 0.5 + 0.5 * math.sin(t * 7)})
    tube = m._tubes[0]['tube']
    ct = centre_of(tube)
    cam = S.camera(sc, ct + Vector((0.05, -0.62, 0.08)), ct, lens=50)
    S.key_light(sc, ct, dist=1.2, power=40.0)
    box = screen_box(sc, cam, tube, pad=-40)                    # well inside the raster
    probe_frames = (10, 30, 52)
    live_vals = {f: {p: fc_value(m.group, p, f) for p in ('power', 'gain', 'led_monitor', 'speaker')}
                 for f in probe_frames}
    live = S.render(WORK / 'saved_live_f52.png', 52)
    blend = WORK / 'saved' / 'c64_film.blend'
    blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    sc = bpy.context.scene
    g = bpy.data.objects['c64']
    same = all(abs(fc_value(g, p, f) - v) < 1e-6 for f, vals in live_vals.items() for p, v in vals.items())
    check(same, 'saved: the reopened blend holds the keyed power, gain, LED and glow at frames 10, 30, 52')
    re_ = S.render(WORK / 'saved_reopen_f52.png', 52)
    re10 = S.render(WORK / 'saved_reopen_f10.png', 10)
    strip([live, re_, re10], OUT / 'saved_reopen.png', ['live, frame 52', 'reopened, frame 52',
                                                       'reopened, frame 10'], h=300)
    x0, y0, x1, y1 = box
    a, b = png_array(live)[y0:y1, x0:x1], png_array(re_)[y0:y1, x0:x1]
    d = np.abs(a - b).sum(axis=2)
    check(np.median(d) < 6 and np.percentile(d, 90) < 24,
          f'saved: the reopened blend draws frame 52\'s raster as the live scene (|diff| median {np.median(d):.1f}, '
          f'90th percentile {np.percentile(d, 90):.1f} over the raster; the glass reflection may differ)')
    d2 = np.abs(png_array(re_) - png_array(re10)).mean()
    check(d2 > 3, f'saved: frame 10 (raster opening, one line of text) differs from 52 (mean |diff| {d2:.1f})')


def probe_kit():
    """A new prop from the kit's geometry builders and canvas helpers: a desktop voice box. Each builder is checked
    against the JS kit's numbers (out/parity_kit_js.json, three's axes mapped (x, y, z) -> (x, -z, y)) where it has
    them, then the box is rendered on the desk beside a C64."""
    import json
    import bmesh
    jsf = OUT / 'parity_kit_js.json'
    js = json.loads(jsf.read_text(encoding='utf-8')) if jsf.is_file() else None
    if js is None:
        check(False, 'kit: out/parity_kit_js.json (run test_screens_parity.py first: it dumps the JS kit\'s numbers)')
    sc = stage(frames=(1, 1))
    coll = bpy.data.collections.new('voice_box')
    sc.collection.children.link(coll)

    def bounds(bm):
        co = np.array([v.co[:] for v in bm.verts])
        return co.min(axis=0), co.max(axis=0)

    def three_bounds(b):                       # three [minx, miny, minz, maxx, maxy, maxz] -> Blender lo, hi
        return np.array((b[0], -b[5], b[1])), np.array((b[3], -b[2], b[4]))

    # rbox and keycap against RoundedBoxGeometry
    if js:
        g = VM.rbox(*js['rbox']['args'])
        (lo, hi), (wl, wh) = bounds(g), three_bounds(js['rbox']['bounds'])
        check(np.allclose(lo, wl, atol=1e-6) and np.allclose(hi, wh, atol=1e-6),
              f'rbox{tuple(js["rbox"]["args"])}: bounds {np.round(hi - lo, 4).tolist()} m as RoundedBoxGeometry')
        g.free()
        args = js['keycap']['args']
        g = VM.keycap(*args)
        (lo, hi), (wl, wh) = bounds(g), three_bounds(js['keycap']['bounds'])
        top = max(abs(v.co.x) for v in g.verts if v.co.z > args[4] / 2 * 0.98)
        # the same rounded shape, sampled differently: three's fillet rings sit at about 27 and 45 degrees, the
        # bevel's at 45, so after the taper their widest rings differ by tens of microns
        check(np.allclose(lo, wl, atol=1e-4) and np.allclose(hi, wh, atol=1e-4) and
              abs(top - js['keycap']['top_half_width']) < 1e-5,
              f'keycap{tuple(args)}: base {np.round((hi - lo) * 1000, 3).tolist()} mm (the JS '
              f'{np.round((wh - wl) * 1000, 3).tolist()}), top half width {top * 1000:.3f} mm as the JS '
              f'({js["keycap"]["top_half_width"] * 1000:.3f} mm)')
        g.free()
        rings = [[(p[0], -p[2], p[1]) for p in ring] for ring in js['loft']['rings']]
        g = VM.loft_rings(rings)
        (lo, hi), (wl, wh) = bounds(g), three_bounds(js['loft']['bounds'])
        uvl = g.loops.layers.uv.active
        us = [lp[uvl].uv[0] for f in g.faces for lp in f.loops]
        vs = [lp[uvl].uv[1] for f in g.faces for lp in f.loops]
        check(len(g.verts) == js['loft']['n_vertices'] and 2 * len(g.faces) == js['loft']['n_triangles'] and
              np.allclose(lo, wl, atol=1e-9) and np.allclose(hi, wh, atol=1e-9) and max(vs) == 1.0 and
              max(us) == 1.0 and min(us) == 0.0,
              f'loft_rings: {len(g.verts)} vertices, {2 * len(g.faces)} triangles, the bounds of loftRings; u 0..1 '
              f'(the JS wrapped its seam column back to 0: u max {js["loft"]["umax"]:.2f})')
        g.free()

    # the label: a canvas with a rounded plate, lettering and speckled wear, as a texture
    lab = VM.make_canvas(512, 160)
    lab.fill_poly(VM.rr(8, 8, 496, 144, 18), '#2b2622')
    lab.stroke_poly(VM.rr(16, 16, 480, 128, 12), '#c9b98f', 3, closed=True)
    lab.text('EIDO VOICE BOX', 256, 82, 'Franklin Gothic Medium, Arial', 50, '#e3d6b0', 'center')
    lab.text('MODEL 82  ·  SPEECH UNIT', 256, 124, 'Arial', 22, '#c9b98f', 'center', bold=True)
    VM.speckle(lab, 512, 160, 900, 82, ['#5a5045', '#efe6cc', '#1a1714'], 1.2, 0.25)
    tex = VM.canvas_texture(lab, name='voice_box_label')
    px = np.empty(512 * 160 * 4, np.float32)
    tex.image.pixels.foreach_get(px)
    px = px.reshape(160, 512, 4)[::-1]                     # canvas rows, top first
    ref = np.asarray(lab.image(), np.float32) / 255
    opaque, empty = ref[..., 3] == 1.0, ref[..., 3] == 0.0
    check(tuple(tex.image.size) == (512, 160) and np.abs(px[..., 3] - ref[..., 3]).max() < 1 / 255 + 1e-6 and
          np.abs(px[opaque][:, :3] - ref[opaque][:, :3]).max() < 1 / 255 + 1e-6 and tex.interpolation == 'Linear'
          and tex.extension == 'EXTEND',
          'canvas_texture: the canvas upright (its top at v = 1, the lettering in place), alpha kept, Linear '
          '(mipmapped), EXTEND')
    bled = px[empty][:, :3]
    check(empty.any() and bled.max(axis=1).min() > 0.02,
          f'canvas_texture: every transparent texel carries the plate\'s colour (bleed_alpha; darkest '
          f'{bled.max(axis=1).min():.3f})')
    t2 = VM.canvas_texture(lab, nearest=True, repeat=True, name='label_nearest')
    t3 = VM.canvas_texture(lab, mips=False, srgb=False, name='label_nomips')
    check((t2.interpolation, t2.extension, t3.interpolation, t3.image.colorspace_settings.name) ==
          ('Closest', 'REPEAT', 'Cubic', 'Non-Color'), 'canvas_texture options: nearest, repeat, mips=False, srgb')
    lab2 = VM.make_canvas(64, 32)
    small = VM.canvas_texture(lab2, name='label_refresh')
    before = np.array(small.image.pixels[:])
    lab2.fill_rect(0, 0, 32, 32, '#ff0000')
    VM.refresh_canvas_texture(small)
    check(not np.array_equal(before, np.array(small.image.pixels[:])), 'refresh_canvas_texture: re-reads the canvas')
    for t in (t2, t3, small):
        bpy.data.images.remove(t.image)

    # the case: a rounded box, the label printed on its front through planar_uv_facing
    W, Hh, D, R = 0.26, 0.06, 0.17, 0.012
    foot = 0.004
    case_bm = VM.rbox(W, Hh, D, R, 3)
    # the label on the front's flat band (12 mm fillets leave the middle 36 mm of the 60 mm height flat), 3.2 : 1
    VM.planar_uv_facing(case_bm, -0.118, -0.016, -0.0156, 0.016, 'xz', (0.0, -1.0, 0.0), 0.35)
    uvl = case_bm.loops.layers.uv.active
    front_ok = all(tuple(lp[uvl].uv) != (-0.25, -0.25) for f in case_bm.faces if f.normal.y < -0.9 for lp in f.loops)
    back_ok = all(tuple(lp[uvl].uv) == (-0.25, -0.25) for f in case_bm.faces if f.normal.y > 0.1 or f.normal.z > 0.9
                  for lp in f.loops)
    check(front_ok and back_ok, 'planar_uv_facing: the front prints, the back and top map to (-0.25, -0.25)')
    cx, cy = -0.25, 0.02
    z0 = S.DESK_Z + foot
    case_bm = VM.bake(case_bm, pos=(cx, cy, z0 + Hh / 2))
    case = VM.mesh(case_bm, None, 'voice_box_case', coll)
    me = case.data
    top_n = [me.corner_normals[i].vector.z for p in me.polygons if p.normal.z > 0.999
             for i in range(p.loop_start, p.loop_start + p.loop_total)]
    check(len(top_n) and min(top_n) > 0.999, f'mesh(): area-weighted normals keep the top face flat (corner normal '
                                             f'z >= {min(top_n):.5f})')
    lo = np.array([min(v.co[k] for v in case.data.vertices) for k in range(3)])
    check(abs(lo[2] - z0) < 1e-6 and abs(lo[0] - (cx - W / 2)) < 1e-6, 'bake: the case moved to its place')
    VM.write_curvature(case)
    case.data.materials.append(VM.plastic_material('voice_box_case', color='#d8cdb2', aged='#cdb98a', age_amt=0.45,
                                                   decal=tex.image, decal_rough=0.3))

    # the keys: eight keycaps baked along the top and merged into one mesh
    caps = []
    kw, kd, kh = 0.016, 0.016, 0.0085
    for i in range(8):
        k = VM.keycap(kw, kd, kw * 0.72, kd * 0.74, kh, 0.0012)
        caps.append(VM.bake(k, pos=(cx - 0.085 + i * 0.0195, cy - 0.035, z0 + Hh + kh / 2 - 0.0005),
                            rot=(math.radians(4.0), 0.0, 0.0)))            # their tops tilted toward the user
        k.free()
    keys_bm = VM.merge(caps)
    check(len(keys_bm.verts) == 8 * len(caps[0].verts) and len(keys_bm.faces) == 8 * len(caps[0].faces),
          f'merge: eight keycaps, {len(keys_bm.verts)} vertices')
    keys = VM.mesh(keys_bm, None, 'voice_box_keys', coll)
    VM.write_curvature(keys)
    keys.data.materials.append(VM.plastic_material('voice_box_keys', color='#4a4038', rough=0.42, grime_amt=0.7))

    # the knob: rr_points rings lofted, closed by a pole on top
    prof = [(0.0, 0.026), (0.003, 0.027), (0.011, 0.026), (0.016, 0.022), (0.019, 0.015), (0.0205, 0.0)]
    rings = []
    for h_, s in prof:
        pts = VM.rr_points(max(s, 1e-7), max(s, 1e-7), max(s, 1e-7) * 0.32, 5)
        rings.append([(cx + 0.088 + x, cy + 0.02 + y, z0 + Hh + h_) for x, y in pts])
    knob = VM.mesh(VM.loft_rings(rings), None, 'voice_box_knob', coll)
    VM.write_curvature(knob)
    knob.data.materials.append(VM.plastic_material('voice_box_knob', color='#8f1d16', clearcoat=1.0,
                                                   clearcoat_rough=0.08, rough=0.35))

    # the grille: a rounded plate with a row of rounded slots, extruded, on the front right
    holes = [VM.rounded_rect_shape(0.0045, 0.022, 0.002, -0.036 + i * 0.008, 0.0) for i in range(10)]
    outline = VM.rounded_rect_shape(0.094, 0.032, 0.005)
    gr = VM.shape_geometry(outline, holes, depth=0.0016)
    closed = all(len(e.link_faces) == 2 for e in gr.edges)
    area = 0.0
    for poly in [outline] + holes:
        p = np.array(poly)
        area += 0.5 * abs(np.dot(p[:, 0], np.roll(p[:, 1], 1)) - np.dot(p[:, 1], np.roll(p[:, 0], 1))) * \
            (1 if poly is outline else -1)
    vol = gr.calc_volume()
    check(closed and abs(vol - area * 0.0016) < 1e-9, f'shape_geometry: the extruded grille is closed, volume '
                                                     f'{vol * 1e6:.4f} cm3 = (outline - 10 holes) x depth')
    sheet = VM.shape_geometry(outline, holes)
    sheet.normal_update()
    check(all(f.normal.y < -0.999 for f in sheet.faces), 'shape_geometry(depth 0): one sheet facing -Y')
    sheet.free()
    gr = VM.bake(gr, pos=(cx + 0.062, cy - D / 2 + 0.0002, z0 + Hh / 2))          # on the flat band, 1.4 mm proud
    grille = VM.mesh(gr, None, 'voice_box_grille', coll)
    grille.data.materials.append(VM.metal_material('voice_box_grille', '#9a9a9e', 0.35))

    # the feet: extruded rounded squares, smoothed, laid flat under the corners
    pad = VM.shape_geometry(VM.rounded_rect_shape(0.026, 0.026, 0.008), depth=foot)
    n_before = len(pad.verts)
    pads = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            pads.append(VM.bake(pad, pos=(cx + sx * (W / 2 - 0.027), cy + sy * (D / 2 - 0.027), S.DESK_Z),
                                rot=(math.radians(-90.0), 0.0, 0.0)))
    feet_bm = VM.smooth(VM.merge(pads))
    check(len(feet_bm.verts) <= 4 * n_before and not len(feet_bm.loops.layers.uv) and
          all(f.smooth for f in feet_bm.faces), 'smooth: welded, smooth faces, UVs dropped')
    feet = VM.mesh(feet_bm, None, 'voice_box_feet', coll)
    feet.data.materials.append(VM.plastic_material('voice_box_feet', color='#1d1b1a', rough=0.85, dust_amt=0.0))
    lo_f = min(v.co.z for v in feet.data.vertices)
    check(abs(lo_f - S.DESK_Z) < 1e-6, f'the feet stand on the desk ({(lo_f - S.DESK_Z) * 1000:.3f} mm)')

    # the cord: out of the back, down to the desk and away along it
    by = cy + D / 2
    path = VM.rounded_polyline([(cx + 0.06, by - 0.004, z0 + 0.022), (cx + 0.06, by + 0.05, z0 + 0.022),
                                (cx + 0.06, by + 0.09, S.DESK_Z + 0.003), (cx + 0.30, by + 0.12, S.DESK_Z + 0.003),
                                (cx + 0.36, by + 0.20, S.DESK_Z + 0.003)], 0.03)
    cord = VM.wire(path, 0.003, 'voice_box_cord', VM.plastic_material('voice_box_cord', color='#2a2826', rough=0.6),
                   coll, sides=10)
    dg = bpy.context.evaluated_depsgraph_get()
    em = cord.evaluated_get(dg).to_mesh()
    zs = [v.co.z for v in em.vertices]
    check(cord.type == 'CURVE' and abs(min(zs) - S.DESK_Z) < 0.0005 and len(em.vertices) > 100,
          f'wire: a {path.length * 100:.1f} cm cord, {len(em.vertices)} vertices, lying on the desk '
          f'({(min(zs) - S.DESK_Z) * 1000:.2f} mm)')
    cord.evaluated_get(dg).to_mesh_clear()

    # flip_uv on a mesh and on a BMesh
    pm = bpy.data.meshes.new('flip_probe')
    pm.from_pydata([(0, 0, 0), (1, 0, 0), (1, 0, 1)], [], [(0, 1, 2)])
    pm.uv_layers.new(name='UVMap')
    pm.uv_layers['UVMap'].data[2].uv = (0.3, 0.2)
    VM.flip_uv(pm)
    bmf = bmesh.new()
    bmf.from_mesh(pm)
    bmf.faces.ensure_lookup_table()
    VM.flip_uv(bmf)
    lay = bmf.loops.layers.uv.active
    back = [tuple(round(x, 6) for x in lp[lay].uv) for lp in bmf.faces[0].loops]
    check(abs(pm.uv_layers['UVMap'].data[2].uv[1] - 0.8) < 1e-6 and back[2] == (0.3, 0.2),
          'flip_uv: v -> 1 - v on a mesh, and back on a BMesh')
    bmf.free()
    bpy.data.meshes.remove(pm)

    # beside a C64, under the desk's key light
    if not RENDER:
        return
    c = VM.build_machine('c64', screen_dir=str(WORK / 'kit' / 'c64'))
    place(c, 0.24, 0.0)
    c.update(0.0, {'power': 1, 'voice': 0.2})
    objs = list(coll.objects) + c.objects
    cam = S.camera(sc, (0, -1, 1), (0, 0, 1))
    frame_on(sc, cam, objs, az=14, el=21, lens=42, margin=0.06)
    S.key_light(sc, Vector((0.0, 0.0, S.DESK_Z + 0.1)), dist=1.25, power=55.0)
    p = S.render(OUT / 'kit_voice_box.png', 1)
    check(S.magenta_fraction(p) == 0.0, 'kit: the voice box renders beside the C64')
    frame_on(sc, cam, [o for o in coll.objects if o.type == 'MESH'], az=20, el=26, lens=50, margin=0.1)
    p = S.render(OUT / 'kit_voice_box_close.png', 1)
    check(S.magenta_fraction(p) == 0.0, 'kit: the voice box close up')


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    probes = [('api', probe_api), (('desk', 'close'), probe_desk_and_close), ('crt', probe_crt),
              ('voice', probe_voice), ('mac', probe_mac), ('scene', probe_scene), ('lineup', probe_lineup),
              ('plastic', probe_plastic), ('kit', probe_kit), ('saved', probe_saved)]
    for keys, fn in probes:
        if not ONLY & (set(keys) if isinstance(keys, tuple) else {keys}):
            continue
        try:                                   # one probe failing never hides the others
            fn()
        except Exception:
            import traceback
            traceback.print_exc()
            check(False, f'{fn.__name__} ran to the end')
    for d in ('desk', 'api', 'crt', 'voice', 'mac', 'scene', 'lineup', 'plastic', 'kit', 'saved'):   # regenerable
        shutil.rmtree(WORK / d, ignore_errors=True)
    for f in WORK.glob('*.png'):              # the single frames the strips were made of
        f.unlink()
    S.summary('test_machines')


main()

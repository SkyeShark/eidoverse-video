"""test_quiet_room.py: the quiet room (UNKNOWN FORCE verse 1) built in Blender 5.2 EEVEE, checked, and rendered from
the film's cams with the claudesona at her mark.

    # pre-draw the canvases once (system Python, outside the GPU slot):
    cd blender && python -c "import sys; sys.path.insert(0, '.'); from eidoblend.sets.unknown_force import \
        quiet_room as QR; QR.draw_canvases('tests/sets_uf_interiors/out/art_cache')"
    # build, check, bake the room probe, render (from the main checkout, through the GPU slot):
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/sets_uf_interiors/test_quiet_room.py -- [--cams altar,pews,...] [--no_render]
        [--samples 16] [--res 960x540] [--no_vrm] [--probe_samples 512] [--probe_spacing 0.5] [--save]

Checks (PASS / FAIL lines): the build's contents (merged meshes, the 56 chairs, the 360-tower backdrop's
survivors, every board image at 960 texels per metre), three's light units, the probe fitted to the room, keyed
update() read back at its frames (crate, shutter, beacon, launch lights, hell flicker), cams aimed at their targets,
and each render's exposure. Stills: out/qr/qr_<cam>_<state>.png and a contact sheet.
"""
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as T  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.sets.unknown_force import interiors_lib as L  # noqa: E402
from eidoblend.sets.unknown_force import quiet_room as QR  # noqa: E402

A = T.args({'cams': 'altar,pews,crate,close,board,hatch,lectern,essay,altar_launch,altar_hell0', 'samples': 16,
            'res': '960x540', 'probe_samples': 512, 'probe_spacing': 0.5, 'no_render': False, 'no_vrm': False,
            'save': False, 'no_bloom': False, 'cycles': '', 'look': '', 'look_cams': 'altar,crate'})
OUT = os.path.join(T.OUT, 'qr')
os.makedirs(OUT, exist_ok=True)

# the shots: name -> (cam, song time, state) as the treatment times them
SHOTS = {
    'board': ('board', 41.0, {}),
    'close': ('close', 42.5, {}),
    'altar': ('altar', 45.6, {}),
    'pews': ('pews', 47.5, {}),
    'lectern': ('lectern', 50.8, {}),
    'essay': ('essay', 52.6, {}),
    'hatch': ('hatch', 56.4, {'shipT': 0.5}),
    'crate': ('crate', 59.0, {'shipT': 1.0, 'sale': 1.0}),
    'altar_launch': ('altar', 59.6, {'shipT': 1.0, 'sale': 1.0}),
    'altar_hell0': ('altar', 45.6, {'hell': 0.0}),        # the hell glow out: pits, slot, red key, vault light
}


def ref_crate(ship):
    """the engine's updateCrate, written out again for the check (three's axes)."""
    ship = min(1.0, max(0.0, ship))
    sm = lambda x: (lambda c: c * c * (3 - 2 * c))(min(1.0, max(0.0, x)))         # noqa: E731
    rp = lambda x, a, b: min(1.0, max(0.0, (x - a) / (b - a)))                   # noqa: E731
    sy = QR.HATCH['y1'] + sm(rp(ship, 0.02, 0.20)) * (QR.HATCH['y1'] - QR.HATCH['y0'] + 0.02)
    ride = rp(ship, 0.18, 0.88)
    e = 2 * ride * ride if ride < 0.5 else 1 - (-2 * ride + 2) ** 2 / 2
    z = QR.CRATE['zIn'] + (QR.CRATE['zOut'] - QR.CRATE['zIn']) * e
    bump = math.sin(rp(ship, 0.88, 0.96) * math.pi) * 0.035 * (1 - rp(ship, 0.88, 1)) if ship > 0.88 else 0.0
    return sy, z - bump, -bump * 0.4


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    W, H = (int(v) for v in A['res'].split('x'))
    t0 = time.perf_counter()
    room = QR.build(scene, art_cache=T.ART, probe_spacing=float(A['probe_spacing']), probe_samples=int(A['probe_samples']))
    dt = time.perf_counter() - t0
    made = room.sb.made
    T.check('build', True, f'{dt:.1f} s, {len(made["objects"])} objects, {len(made["meshes"])} meshes, '
            f'{len(made["materials"])} materials, {len(made["lights"])} lights')

    # ---------------------------------------------------------------------------------------- contents
    obs = {o.name.split(':', 2)[-1]: o for o in made['objects']}
    merged = [o for o in made['objects'] if o.type == 'MESH' and ':merged:' in o.name]
    T.check('static geometry merged into one mesh per material', len(merged) >= 20 and
            len({o.data.materials[0].name for o in merged}) == len(merged), f'{len(merged)} merged meshes')
    chairs = room.parts['chairs']
    T.check('three chair meshes, one per material', len(chairs) == 3 and all(c.type == 'MESH' for c in chairs))
    fab = chairs[0].data
    tone = fab.attributes.get('instance_color')
    ids = fab.attributes.get('instance_id')
    nid = len(set(np.round([v.value for v in ids.data]).astype(int))) if ids else 0
    T.check('the pews: 56 chairs (7 rows x 8), each with its own tone', nid == 56 and tone is not None, f'{nid} ids')
    towers = room.nodes['towers']
    T.check('the backdrop: 360 tries, every survivor outside the tower footprint', 340 <= len(towers) <= 360 and
            all(not (abs(x) < 55 and -60 < z < 50) for x, z, *_ in towers), f'{len(towers)} towers')
    # three's hash(id + 17 / 91 / 233) per tower and hash(id + 5) per aviation light, exact (pcg_hash), as instance
    # attributes: the neon edges, facade tones, window colours and blink phases sit on the engine's towers
    worst, names = 0.0, []
    for obn, offs in (('towers', (17, 91, 233)), ('aviation', (5,))):
        me = obs[obn].data
        iid = np.array([v.value for v in me.attributes['instance_id'].data])
        for off in offs:
            a = me.attributes.get(f'uf_h{off}')
            if a is None:
                names.append(f'{obn}.uf_h{off} missing')
                continue
            got = np.array([v.value for v in a.data])
            worst = max(worst, float(np.abs(got - L.pcg_hash(np.round(iid) + off)).max()))
    T.check("the towers' and aviation lights' per-instance hashes are three's (PCG on the instance id)",
            not names and worst < 1e-6, f'{names} worst {worst:.1e}')
    for b in ('center', 'odds', 'clip', 'timelines', 'want'):
        face = room.parts['boards'][b]
        img = face.data.materials[0].node_tree.nodes
        tex = [n.image for n in img if n.bl_idname == 'ShaderNodeTexImage' and n.image and 'rough' not in n.image.name]
        W_, H_ = QR.QA.board_size(b)
        T.check(f'board {b}: {W_} x {H_} canvas (960 texels per metre)', tex and tuple(tex[0].size) == (W_, H_),
                f'{tuple(tex[0].size) if tex else None}')
    # the env: Blender's equirect lookup sees the painted directions (red at -Z three = +Y Blender, low)
    env_img = bpy.data.images[room.env['uf_env_image']]
    px = np.array(env_img.pixels[:]).reshape(env_img.size[1], env_img.size[0], 4)

    def env_at(d_three):
        """Blender's Environment Texture lookup (node_tex_environment_equirectangular)."""
        d = np.array(L.to_blender(d_three))
        u = -math.atan2(d[1], d[0]) / (2 * math.pi) + 0.5
        v = math.atan2(d[2], math.hypot(d[0], d[1])) / math.pi + 0.5
        return px[min(env_img.size[1] - 1, int(v * env_img.size[1])), min(env_img.size[0] - 1, int(u * env_img.size[0]))][:3]
    red, back = env_at((0, 0.05, -1)), env_at((0, 0.05, 1))
    want = np.array(QR.env_paint(np.array([0.0]), np.array([0.05]), np.array([-1.0])))[:, 0]
    T.check('env World: the altar glow lies toward -Z (three) as painted', red[0] > 0.5 and red[0] > 5 * back[0] and
            abs(red[0] - min(1, want[0])) < 0.03, f'red {red.round(3)}, painted {want.round(3)}, core wall {back.round(3)}')

    # ---------------------------------------------------------------------------------------- lights in three's units
    lt = {o.name.split(':', 2)[-1]: o for o in made['objects'] if o.type == 'LIGHT'}
    room.update(0.0, {}, key=False)
    fl = 0.86 + 0.08 * math.sin(0) + 0.05 * math.sin(1.3) + 0.03 * math.sin(0.4)
    hl = lt['hellLight2']
    T.check('hell point light: 6 cd x flicker -> 4 pi cd W', abs(hl.data.energy - 4 * math.pi * 6 * fl) < 1e-4,
            f'{hl.data.energy:.4f} W')
    T.check('hell key: a sun of 5 lux x flicker, the one shadow caster', abs(lt['hellKey'].data.energy - 5 * (0.92 + 0.08 * fl)) < 1e-4
            and lt['hellKey'].data.use_shadow and sum(o.data.use_shadow for o in lt.values()) == 1,
            f'{lt["hellKey"].data.energy:.4f}, shadow casters {sum(o.data.use_shadow for o in lt.values())}')
    ks = lt['kicker']
    ang, pen = 0.30, 0.65
    T.check('kicker spot: cone 2 x 0.30 rad, three penumbra as blend, cutoff 10 m',
            abs(ks.data.spot_size - 0.6) < 1e-6 and abs(ks.data.spot_blend - L.three_spot_blend(ang, pen)) < 1e-6 and
            ks.data.use_custom_distance and abs(ks.data.cutoff_distance - 10) < 1e-6,
            f'blend {ks.data.spot_blend:.3f}')
    d_k = (Vector(L.to_blender((0, 1.0, 0.15))) - Vector(L.to_blender((-0.9, 2.6, -2.9)))).length
    T.check('kicker decay 1.4 -> inverse square matched at its target', abs(ks.data.energy - 16 * 4 * math.pi * d_k ** 0.6) < 1e-3,
            f'{ks.data.energy:.2f} W at {d_k:.2f} m')
    bpy.context.view_layer.update()
    aim = -(ks.matrix_world.to_3x3() @ Vector((0, 0, 1)))
    to_t = (room.parts['singerLights']['kickerTarget'].matrix_world.translation - ks.matrix_world.translation).normalized()
    T.check('kicker aimed at its target (Track To)', aim.dot(to_t) > 0.9999, f'cos {aim.dot(to_t):.6f}')
    # the probe: fitted to the room, its outer samples mid-wall
    pr = room.probe
    lo = pr.matrix_world.translation - Vector(pr.scale)
    hi = pr.matrix_world.translation + Vector(pr.scale)
    T.check('room probe encloses the room (glass to glass, floor to ceiling, core wall)',
            lo.x < -6 and hi.x > 6 and lo.y < -6.2 and hi.y > 9 and lo.z < 0 and hi.z > 3.9,
            f'{tuple(round(v, 2) for v in lo)} .. {tuple(round(v, 2) for v in hi)}, res '
            f'{pr.data.resolution_x}x{pr.data.resolution_y}x{pr.data.resolution_z}')

    # ---------------------------------------------------------------------------------------- keyed update
    # a sweep of shipT and sale keyed on frames 101..111, read back after jumping to each frame
    frames = list(range(101, 112))
    states = [(50 + i * 0.7, {'shipT': i / 10, 'sale': max(0.0, (i - 6) / 4), 'hell': 1.0}) for i in range(11)]
    for f, (t, st) in zip(frames, states):
        room.update(t, st, frame=f)
    bad = []
    for f, (t, st) in zip(reversed(frames), reversed(states)):
        scene.frame_set(f)
        sy, cz, rx = ref_crate(st['shipT'])
        cl = room.parts['crate']['group'].location
        sl = room.parts['shutter'].location
        want_c = L.to_blender((QR.CONV['x'], QR.CONV['top'], cz))
        if (Vector(cl) - Vector(want_c)).length > 1e-5 or abs(sl.z - sy) > 1e-5 or abs(room.parts['crate']['group'].rotation_euler.x - rx) > 1e-6:
            bad.append(f)
        s2 = st['sale'] ** 2
        if abs(room.parts['saleLights']['spots'][4].data.energy - room._sale_spots[4].watts(40 * s2)) > 1e-3:
            bad.append(('sale', f))
        if abs(room.root['uSale'] - st['sale']) > 1e-5 or abs(room.root['uT'] - t) > 1e-4:     # keys are float32
            bad.append(('uniform', f))
        flk = 0.86 + 0.08 * math.sin(t * 6.1) + 0.05 * math.sin(t * 13.7 + 1.3) + 0.03 * math.sin(t * 29.3 + 0.4)
        if abs(lt['hellLight2'].data.energy - 4 * math.pi * 6 * flk * (1 - 0.35 * st['sale'])) > 1e-3:
            bad.append(('hell', f))
        if abs(room.parts['beacon'].rotation_euler.z - t * 9.0) > 1e-4:
            bad.append(('beacon', f))
    T.check('update() keyed: crate, shutter, launch lights, hell flicker, uniforms and beacon read back at 11 frames',
            not bad, f'mismatch at {bad}' if bad else 'all 11')
    # the parts' own drivers, each keyed alone (the conductor can drive the crate and the launch separately)
    room.parts['crate']['update'](56.0, 0.42, frame=150)
    room.parts['saleLights']['set'](0.8, frame=150)
    room.parts['hell']['set'](0.6, 52.0, frame=150)
    room.show(False, frame=151)
    room.show(True, frame=152)
    scene.frame_set(150)
    sy, cz, rx = ref_crate(0.42)
    flk = 0.86 + 0.08 * math.sin(52 * 6.1) + 0.05 * math.sin(52 * 13.7 + 1.3) + 0.03 * math.sin(52 * 29.3 + 0.4)
    ok = ((Vector(room.parts['crate']['group'].location) - Vector(L.to_blender((QR.CONV['x'], QR.CONV['top'], cz)))).length < 1e-5
          and abs(room.parts['saleLights']['spots'][0].data.energy - room._sale_spots[0].watts(26 * 0.64)) < 1e-3
          and abs(room.parts['hell']['key'].data.energy - room._hell_key.watts(5.0 * 0.6 * (0.92 + 0.08 * flk) * (1 - 0.4 * 0.8))) < 1e-3)
    scene.frame_set(151)
    hidden = room.parts['hell']['key'].hide_render and room.parts['chairs'][0].hide_render
    scene.frame_set(152)
    shown = not room.parts['hell']['key'].hide_render
    scene.frame_set(1)
    before = not room.parts['hell']['key'].hide_render and not room.parts['chairs'][0].hide_render
    T.check("parts['crate']['update'], parts['saleLights']['set'], parts['hell']['set'] key alone; show() keys a cut",
            ok and hidden and shown and before,
            f'crate/sale/hell {ok}, shown before the cut {before}, hidden at 151 {hidden}, shown at 152 {shown}')
    # the backdrop hidden as a subtree (to put the city set there instead), then back
    hid = room.show_part('backdrop', False)
    names_h = {o.name.split(':')[-1] for o in hid}
    all_hidden = all(o.hide_render for o in hid)
    room.show_part('backdrop', True)
    T.check("show_part('backdrop', False) hides the whole subtree (sky, ground, towers, aviation lights)",
            all_hidden and {'sky', 'cityground', 'towers', 'aviation'} <= names_h and not any(o.hide_render for o in hid),
            f'{len(hid)} objects')
    fc = None
    ad = room.root.animation_data
    from bpy_extras import anim_utils
    cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    fc = next(c for c in cb.fcurves if c.data_path == '["uT"]')
    T.check('keys are LINEAR (sub-frame motion blur interpolates straight)',
            all(k.interpolation == 'LINEAR' for k in fc.keyframe_points), f'{len(fc.keyframe_points)} keys on uT')
    # the drivers: every uniform node reads the root
    drv = [d for m in made['materials'] if m.node_tree and m.node_tree.animation_data
           for d in m.node_tree.animation_data.drivers]
    T.check('material uniforms are valid one-variable drivers on the root', drv and all(d.driver.is_valid for d in drv),
            f'{len(drv)} drivers')
    scene.frame_set(101 + 5)
    v = room.root['uSale']
    node_vals = [d for d in drv if 'uSale' in (d.driver.variables[0].targets[0].data_path)]
    T.check('a driven uniform follows the keyed root', bool(node_vals), f'uSale {v:.3f}')

    # ---------------------------------------------------------------------------------------- cams
    cams = {}
    for nm in room.cams:
        cams[nm] = room.make_camera(nm)
    bpy.context.view_layer.update()
    worst = 0.0
    for nm, ob in cams.items():
        c = room.cams[nm]
        fwd = -(ob.matrix_world.to_3x3() @ Vector((0, 0, 1)))
        want = (Vector(c['target']) - Vector(c['pos'])).normalized()          # cams: Blender axes
        worst = max(worst, (fwd - want).length)
    T.check(f'{len(cams)} cams aimed at their targets, vertical fov as three', worst < 1e-5 and
            abs(math.degrees(cams['altar'].data.angle_y) - 42) < 1e-4, f'worst {worst:.2e}')
    T.check("the set reads as the engine's dict and as attributes; cams and mark in Blender axes",
            room['parts'] is room.parts and callable(room['update']) and set(room['cams']) == set(room['cams_three'])
            and tuple(room['cams']['altar']['pos']) == L.to_blender(room['cams_three']['altar']['pos'])
            and abs(room['mark']['pos'][2] - 0.006) < 1e-9)
    T.check('focal (the altar board) and mark where the engine put them',
            (room.focal.matrix_world.translation - Vector(L.to_blender((0, QR.TRIP['y0'] + QR.TRIP['h'] * 0.55, QR.TRIP['z'])))).length < 1e-6)

    # the registry builds it as the integration does (ctx first), and dispose() takes everything back out
    from eidoblend import sets as SETS
    count = lambda: tuple(len(getattr(bpy.data, k)) for k in ('objects', 'materials', 'images', 'worlds', 'actions'))  # noqa: E731
    n0 = count()
    r2 = SETS.build('unknown_force.quiet_room', None, art_cache=T.ART, probe=False)
    r2.update(50.0, {'shipT': 0.5, 'sale': 0.5}, frame=5)                   # keys: Actions the dispose must take too
    made2 = len(r2.sb.made['objects'])
    r2.dispose()
    T.check('built through eidoblend.sets.build(name, ctx), keyed, then dispose() removes all it made',
            made2 > 80 and count() == n0, f'{made2} objects made; objects, materials, images, worlds, actions '
            f'{count()} (were {n0})')

    if A['no_render']:
        return T.done()

    # ---------------------------------------------------------------------------------------- render
    T.render_setup(scene, (W, H), int(A['samples']), bloom=not A['no_bloom'])
    scene.world = room.env
    room.eevee_settings(scene)
    if not A['no_vrm']:
        T.load_singer(L.to_blender(QR.MARK['pos']), 0.0, QR.SUIT_SCALE)
    tb = time.perf_counter()
    secs = room.bake_probes(scene)
    T.check('room probe baked', bool(secs), f'{secs} ({time.perf_counter() - tb:.1f} s)')
    stills = []
    want = [c for c in A['cams'].split(',') if c]
    red = {}
    for i, nm in enumerate(want):
        cam, t, st = SHOTS[nm]
        f = 1 + i
        room.update(t, st, frame=f)
        tag = 'launch' if st.get('sale') else ('ship%02d' % round(100 * st['shipT']) if 'shipT' in st else
                                               ('hell%02d' % round(10 * st['hell']) if 'hell' in st else 'rest'))
        path = os.path.join(OUT, f'qr_{cam}_{tag}.png')
        T.render_still(scene, cams[cam], f, path)
        mean, clip, black = T.stats(path)
        lo = 0.01 if st.get('hell') == 0 else 0.03          # without its glow the room is meant to fall dark
        hi = 0.75 if cam == 'board' else 0.6                # the insert is all white enamel (the engine's is brighter)
        T.check(f'{nm}: exposed (mean luma {lo}..{hi}, clipped < 3 %)', lo < mean < hi and clip < 0.03,
                f'mean {mean:.3f}, clipped {100 * clip:.2f} %, black {100 * black:.1f} %')
        if cam == 'altar':
            from PIL import Image
            px = np.asarray(Image.open(path).convert('RGB'), np.float32) / 255
            red[nm] = float((px[..., 0] - px[..., 1:].mean(2)).clip(0).mean())       # how red the frame is
        stills.append(path)
    if {'altar', 'altar_hell0'} <= set(red):
        T.check('hell 0 takes the red glow out of the altar shot', red['altar_hell0'] < 0.5 * red['altar'],
                f"red excess {red['altar']:.4f} -> {red['altar_hell0']:.4f}")
    if A['look']:
        # the film's look over the same keyed frames (qr_final_altar_argue / qr_final_crate_sale_argue in the
        # WebGPU probes): the aeropittura under the HUD, its sun cones from the altar board
        U = T.film_look(scene, A['look'])
        for nm in [c for c in A['look_cams'].split(',') if c in want]:
            cam = SHOTS[nm][0]
            ok = T.aim_look(scene, U, cams[cam], room.focal)
            path = os.path.join(OUT, f'qr_{nm}_{A["look"]}.png')
            T.render_still(scene, cams[cam], 1 + want.index(nm), path)
            mean, clip, black = T.stats(path)
            T.check(f'{nm} under the {A["look"]} look: focal projected, exposed', ok and 0.03 < mean < 0.7,
                    f'mean {mean:.3f}, clipped {100 * clip:.2f} %')
            stills.append(path)
    if A['cycles']:
        nm = A['cycles']
        idx = want.index(nm) if nm in want else 0
        scene.render.engine = 'CYCLES'
        scene.cycles.device = 'GPU'
        scene.cycles.samples = 128
        p = os.path.join(OUT, f'qr_{nm}_cycles_reference.png')
        T.render_still(scene, cams[SHOTS[nm][0]], 1 + idx, p)
        scene.render.engine = 'BLENDER_EEVEE'
    T.sheet(stills, os.path.join(OUT, 'qr_sheet.jpg'))
    if A['save']:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'quiet_room_probe.blend'), compress=True)
    return T.done()


if __name__ == '__main__':
    rc = main()
    sys.stdout.flush()
    if rc:
        sys.exit(rc)

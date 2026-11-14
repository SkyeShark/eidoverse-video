"""test_showroom.py: the showroom built in Blender 5.2 EEVEE, checked, and rendered from the set's cams: the set
alone (--vrm stands the claudesona on the turntable, at the scale the cams are framed for).

    cd blender && python -c "import sys; sys.path.insert(0, '.'); from eidoblend.sets.unknown_force import \
        showroom as SR; SR.draw_canvases('tests/sets_uf_interiors/out/art_cache')"
    bash run_blender.sh \
        <worktree>/blender/tests/sets_uf_interiors/test_showroom.py -- [--cams reveal,toaster,...] [--no_render]
        [--samples 16] [--res 960x540] [--vrm] [--probe_samples 512] [--probe_spacing 0.6]
    (a GPU job; on a shared machine queue it with EIDO_GPU_WRAP: blender/tests/_where.py)

Checks: the build's contents (280 folded seats + 28 row ends, the toaster's CSG slots really open into the body,
the LED wall's pixel-footprint driver, the void seen by the camera only), three's light units and the one shadow
map, keyed update() and animate() (spin, lights, beams, screen, seq) read back at their frames, cams aimed, the
probe's lowest samples inside the floor slab, global illumination on, each render's exposure. Stills:
out/sr/sr_<cam>.png and a contact sheet.
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
from eidoblend.sets.unknown_force import showroom as SR  # noqa: E402

A = T.args({'cams': 'reveal,toaster,emptySeats,close,wall,reveal_dim,reveal_blackout', 'samples': 16,
            'res': '960x540', 'probe_samples': 512, 'probe_spacing': 0.6, 'no_render': False, 'vrm': False,
            'save': False, 'no_bloom': False, 'look': '', 'look_cams': 'reveal,close'})
OUT = os.path.join(T.OUT, 'sr')
os.makedirs(OUT, exist_ok=True)


def spin_at(t):
    return 0.35 * t                     # the engine's turntable rate, 0.35 rad/s, on the set's clock


# the stills: name -> (cam, t on the set's clock, state); the last two show the state keys a default render never
# moves
SHOTS = {
    'reveal': ('reveal', 0.5, {}),
    'close': ('close', 2.1, {}),
    'wall': ('wall', 3.5, {}),
    'toaster': ('toaster', 5.8, {}),
    'emptySeats': ('emptySeats', 8.5, {}),
    'reveal_dim': ('reveal', 2.9, {'seq': 0.3, 'screen': 0.45, 'beams': 0.0}),   # the bar at 30 %, the wall
    #                                                                               dimmed, the beam cones off
    'reveal_blackout': ('reveal', 3.4, {'lights': 0.0}),                          # a blackout: the LED wall stays
}


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    W, H = (int(v) for v in A['res'].split('x'))
    t0 = time.perf_counter()
    show = SR.build(scene, art_cache=T.ART, probe_spacing=float(A['probe_spacing']),
                    probe_samples=int(A['probe_samples']))
    dt = time.perf_counter() - t0
    made = show.sb.made
    T.check('build', True, f'{dt:.1f} s, {len(made["objects"])} objects, {len(made["meshes"])} meshes, '
            f'{len(made["materials"])} materials, {len(made["lights"])} lights')
    bpy.context.view_layer.update()

    # ---------------------------------------------------------------------------------------- contents
    seats = {o.name.split(':')[-1]: o for o in made['objects'] if o.type == 'MESH' and ':seats:' in o.name}

    def ids(ob):
        a = ob.data.attributes.get('instance_id')
        return len(set(np.round([v.value for v in a.data]).astype(int))) if a else 0
    T.check('280 folded-up seats (14 rows x 2 x 10), three meshes, and 28 row ends',
            all(ids(seats[k]) == 280 for k in ('fab', 'shell', 'metal')) and ids(seats['ends']) == 28,
            ', '.join(f'{k} {ids(v)}' for k, v in seats.items()))
    body = show.nodes['body'].ob
    mats = [m.name for m in body.data.materials]
    slot_faces = sum(1 for p in body.data.polygons if p.material_index == 1)
    T.check('toaster body: chrome with CSG-cut slots (the walls in the element material)',
            mats == ['ufsr-chrome', 'ufsr-toaster-slot'] and slot_faces >= 16, f'{mats}, {slot_faces} slot faces')
    # a ray straight down a slot, beside the toast standing in it (the toast is 0.122 m long, the slot 0.14 m), must
    # go INTO the body past its top before it meets the slot floor
    toaster = show.parts['toaster']
    Hy, slot_d = 0.205, 0.11
    deps = bpy.context.evaluated_depsgraph_get()
    hits = []
    for zs in (0.043, -0.043):
        o = toaster.matrix_world @ Vector(L.to_blender((-0.012 + 0.065, Hy + 0.05, zs)))
        dn = (toaster.matrix_world.to_3x3() @ Vector(L.to_blender((0, -1, 0)))).normalized()
        ok, loc, _n, _i, ob, _m = scene.ray_cast(deps, o, dn)
        hits.append((ok, ob.name.split(':')[-1] if ok else None, (o - loc).length if ok else None))
    depth_ok = all(h[0] and h[2] > 0.05 + slot_d * 0.6 for h in hits)
    T.check('the slots are open: a ray down each slot reaches the slot floor, deep inside the loaf', depth_ok,
            ', '.join(f'{h[1]} at {h[2]:.3f} m' if h[0] else 'miss' for h in hits))
    wall = show.parts['screen']['mesh']
    nt = wall.data.materials[0].node_tree
    reads = sorted(d.driver.variables[0].targets[0].data_path for d in nt.animation_data.drivers)
    T.check('LED wall reads its uniforms (seq, time, brightness, the pixel footprint) through valid drivers',
            reads == ['["uPixelAngle"]', '["uScreen"]', '["uSeq"]', '["uT"]'] and
            all(d.driver.is_valid for d in nt.animation_data.drivers), f'{reads}')
    void = next(o for o in made['objects'] if o.name.endswith(':void'))
    T.check('the void: seen by the camera, left out of the probes (they see the env, as the engine materials did)',
            void.visible_camera and void.hide_probe_volume and void.hide_probe_sphere)
    pr = show.probe
    if pr is not None:
        plo = pr.matrix_world.translation - Vector(pr.scale)
        psp = 2 * pr.scale.z / (pr.data.resolution_z + 1)            # EEVEE: N samples at (i + 1) / (N + 1)
        z_low = plo.z + psp
        T.check("the stage probe's lowest samples lie inside the auditorium's floor slab, the floor a spacing clear "
                "of the probe's edge", SR.FLOOR_Y - SR.FLOOR_SLAB < z_low < SR.FLOOR_Y and
                SR.FLOOR_Y - plo.z > 1.2 * psp, f'lowest samples z {z_low:.3f}, floor {SR.FLOOR_Y}, spacing {psp:.3f}')
        tp, tob = show.parts['toasterProbe'], show.parts['toaster']
        tmeshes = [o for o in tob.children_recursive if o.type == 'MESH']
        body = next(o for o in tmeshes if o.name.endswith(':toaster-body'))
        bpy.context.view_layer.update()
        inside = tp.matrix_world.inverted() @ body.matrix_world @ Vector(
            [sum(c[i] for c in body.bound_box) / 8 for i in range(3)])
        reach = max(tp.scale) * tp.data.parallax_distance
        T.check("the toaster's sphere probe: a child of the toaster, its box influence round the body, the toaster's "
                "meshes hidden from sphere captures, clip start 2 cm, parallax an ellipsoid reaching 2 m",
                tp.data.type == 'SPHERE' and tp.parent == tob and tp.data.influence_type == 'BOX' and
                max(abs(v) for v in inside) < 0.05 and len(tmeshes) >= 6 and
                all(o.hide_probe_sphere for o in tmeshes) and abs(tp.data.clip_start - 0.02) < 1e-6 and
                tp.data.use_custom_parallax and tp.data.parallax_type == 'ELIPSOID' and abs(reach - 2.0) < 1e-3,
                f'{len(tmeshes)} meshes, body centre in the probe {tuple(round(v, 3) for v in inside)}, '
                f'box {tuple(round(2 * v, 3) for v in tp.scale)} m, parallax reach {reach:.2f} m')
    on_meshes = {m.name for o in made['objects'] if o.type == 'MESH' for m in o.data.materials if m}
    need = {'ufsr-stage', 'ufsr-toast', 'ufsr-rubber', 'ufsr-bakelite', 'ufsr-velvet', 'ufsr-tt-top', 'ufsr-warning',
            'ufsr-dial', 'ufsr-ratingplate', 'ufsr-beam', 'ufsr-lens', 'ufsr-truss', 'ufsr-seat-fabric'}
    T.check('every engine material is on a mesh (stage, toast, cord, plug, drapes, platter, placard, dial, beams ...)',
            need <= on_meshes and len(on_meshes) == len(made['materials']),
            f'missing {sorted(need - on_meshes)}; {len(on_meshes)} of {len(made["materials"])} materials used')
    # the env: the wall glow behind (-Z three), the softbox strips overhead, the bounce card out front
    img = bpy.data.images[show.env['uf_env_image']]
    px = np.array(img.pixels[:]).reshape(img.size[1], img.size[0], 4)

    def env_at(d_three):
        d = np.array(L.to_blender(d_three), float)
        d /= np.linalg.norm(d)
        u = -math.atan2(d[1], d[0]) / (2 * math.pi) + 0.5
        v = math.atan2(d[2], math.hypot(d[0], d[1])) / math.pi + 0.5
        return px[min(img.size[1] - 1, int(v * img.size[1])), min(img.size[0] - 1, int(u * img.size[0]))][:3]
    wall_l, strip_l, card_l, side_l = (env_at((0, 0.2, -1)), env_at((0, 0.93, 0.37)), env_at((0, 0.12, 1)),
                                       env_at((1, 0.0, 0)))
    T.check('env World: wall glow behind, a softbox strip overhead, the bounce card in front, dark sides',
            wall_l[0] > 0.6 and strip_l[0] > 0.6 and card_l[0] > 0.3 and side_l[0] < 0.25,
            f'wall {wall_l[0]:.2f}, strip {strip_l[0]:.2f}, card {card_l[0]:.2f}, side {side_l[0]:.2f}')

    # ---------------------------------------------------------------------------------------- lights
    lt = {o.name.split(':')[-1]: o for o in made['objects'] if o.type == 'LIGHT'}
    T.check('six lights; the key is the only shadow map', len(lt) == 6 and lt['key'].data.use_shadow and
            sum(o.data.use_shadow for o in lt.values()) == 1, f'{sorted(lt)}')
    casters = [o for o in made['objects'] if o.type == 'MESH' and o.visible_shadow]

    def under(o, anc):
        while o is not None:
            if o is anc:
                return True
            o = o.parent
        return False
    plinth_g = show.parts['plinth']
    others = [o for o in made['objects'] if o.type == 'MESH' and not under(o, plinth_g)]
    T.check('shadow casters: only the toaster group (toaster, plinth, placard), as the engine picks them',
            casters and all(under(o, plinth_g) for o in casters) and not any(o.visible_shadow for o in others),
            f'{len(casters)} casters under the toaster group, {len(others)} other meshes receive only')
    d_t = (Vector(L.to_blender((SR.PLINTH['x'], SR.STAGE['y'] + SR.PLINTH['h'], SR.PLINTH['z'])))
           - Vector(L.to_blender((SR.PLINTH['x'] + 0.2, SR.TRUSS['y'] - 0.6, SR.TRUSS['zs'][0])))).length
    T.check('toaster spot: 26 cd, decay 1.4 matched at the plinth top', abs(lt['toasterSpot'].data.energy -
            26 * 4 * math.pi * d_t ** 0.6) < 1e-3, f'{lt["toasterSpot"].data.energy:.1f} W at {d_t:.2f} m')

    # ---------------------------------------------------------------------------------------- keyed update
    frames = list(range(201, 210))
    states = [(i * 1.2, {'spin': spin_at(i * 1.2), 'lights': 1 - i / 8, 'beams': i / 8,
                         'seq': 0.5 + i / 16, 'screen': 1.0}) for i in range(9)]
    for f, (t, st) in zip(frames, states):
        show.update(t, st, frame=f)
    bad = []
    for f, (t, st) in zip(reversed(frames), reversed(states)):
        scene.frame_set(f)
        pl = show.parts['turntable']['platter']
        if abs(pl.rotation_euler.z - st['spin']) > 1e-4:
            bad.append(('spin', f))
        lv = st['lights']
        exp = {'key': 1.5 * lv, 'rim': 2.2 * (0.4 + 0.6 * lv), 'toasterSpot': 26 * lv, 'seatSpill': 22 * lv,
               'topSpot': 12 * lv}
        for nm, cd in exp.items():
            node = show._lights['top' if nm == 'topSpot' else nm]
            if abs(lt[nm].data.energy - node.watts(cd)) > 1e-3:
                bad.append((nm, f))
        for u, v in (('uLights', lv), ('uBeams', st['beams']), ('uSeq', st['seq']), ('uScreen', 0.66), ('uT', t)):
            if abs(show.root[u] - v) > 1e-4:
                bad.append((u, f))
    T.check('update() keyed: spin, lights (blackout to full), beams, seq, screen read back at 9 frames', not bad,
            f'{bad}' if bad else 'all 9')
    # whatever stands on the mark rides the platter: a child of it turns with it
    probe_ob = bpy.data.objects.new('rider', None)
    scene.collection.objects.link(probe_ob)
    probe_ob.parent = show.parts['turntable']['platter']
    probe_ob.location = (0.5, 0, 0)
    scene.frame_set(205)
    bpy.context.view_layer.update()
    a = math.atan2(probe_ob.matrix_world.translation.y, probe_ob.matrix_world.translation.x)
    T.check('a child of the platter turns with the spin (the mark rides it)', abs(a - states[4][1]['spin']) < 1e-3 or
            abs(abs(a - states[4][1]['spin']) - 2 * math.pi) < 1e-3, f'{math.degrees(a):.2f} deg')
    bpy.data.objects.remove(probe_ob)

    # ---------------------------------------------------------------------------------------- cams
    cams = {nm: show.make_camera(nm) for nm in show.cams}
    bpy.context.view_layer.update()
    worst = 0.0
    for nm, ob in cams.items():
        c = show.cams[nm]
        fwd = -(ob.matrix_world.to_3x3() @ Vector((0, 0, 1)))
        want = (Vector(c['target']) - Vector(c['pos'])).normalized()          # cams: Blender axes
        worst = max(worst, (fwd - want).length)
    T.check(f'{len(cams)} cams aimed at their targets', worst < 1e-5, f'worst {worst:.2e}')
    scene.render.resolution_x, scene.render.resolution_y = W, H
    show.update(170.0, {}, frame=300, camera=cams['close'])
    want_pa = 2 * math.tan(cams['close'].data.angle_y / 2) / H
    scene.frame_set(300)
    T.check('update(camera=) keys the shot camera\'s pixel angle (the LED wall\'s fwidth scale)',
            abs(show.root['uPixelAngle'] - want_pa) < 1e-8, f'{show.root["uPixelAngle"]:.4e} rad (want {want_pa:.4e})')
    # animate(): the set on its own clock (spin a function of t, seq a span, lights a 4-tuple blackout), the LED
    # wall's camera switching at a cut (camera as a function of the frame)
    fps = 30.0
    cut = lambda f: cams['wall'] if f < 430 else cams['close']                    # noqa: E731
    keyed = show.animate((401, 460), t0=10.0, fps=fps, spin=spin_at, seq=(10.2, 11.2),
                         lights=(11.0, 11.5, 1.0, 0.0), camera=cut)
    bad = []
    for f in (401, 420, 429, 430, 445, 460):
        scene.frame_set(f)
        t = 10.0 + (f - 401) / fps
        lv = 1.0 - min(1.0, max(0.0, (t - 11.0) / 0.5))
        seq = min(1.0, max(0.0, (t - 10.2) / 1.0))
        cam = cut(f)
        pa = 2 * math.tan(cam.data.angle_y / 2) / H
        if abs(show.parts['turntable']['platter'].rotation_euler.z - spin_at(t)) > 1e-4:
            bad.append(('spin', f))
        if abs(show.root['uSeq'] - seq) > 1e-5 or abs(show.root['uLights'] - lv) > 1e-5 or abs(keyed[f] - t) > 1e-9:
            bad.append(('uniform', f))
        if abs(lt['key'].data.energy - show._lights['key'].watts(1.5 * lv)) > 1e-3:
            bad.append(('key light', f))
        if abs(show.root['uPixelAngle'] - pa) > 1e-8:
            bad.append(('pixel angle', f))
    T.check("animate(): 60 frames keyed on the set's own clock (spin(t), seq span, a blackout 4-tuple), the LED "
            "wall's camera switched at the cut, read back", not bad and len(keyed) == 60,
            f'mismatch at {bad}' if bad else '')

    # the registry builds it as the integration does (ctx first), and dispose() takes everything back out
    from eidoblend import sets as SETS
    count = lambda: tuple(len(getattr(bpy.data, k)) for k in ('objects', 'materials', 'images', 'worlds', 'actions'))  # noqa: E731
    n0 = count()
    s2 = SETS.build('unknown_force.showroom', None, art_cache=T.ART, probe=False)     # (the registry's own `name`
    #                                                                                   shadows the set's name option)
    s2.update(165.0, {'spin': 0.7, 'lights': 0.5}, frame=5)                # keys: Actions the dispose must take too
    made2 = len(s2.sb.made['objects'])
    s2.dispose()
    T.check('built through eidoblend.sets.build(name, ctx), keyed, then dispose() removes all it made',
            made2 > 50 and count() == n0, f'{made2} objects made; objects, materials, images, worlds, actions '
            f'{count()} (were {n0})')

    if A['no_render']:
        return T.done()

    # ---------------------------------------------------------------------------------------- render
    T.render_setup(scene, (W, H), int(A['samples']), bloom=not A['no_bloom'])
    scene.world = show.env
    ee = show.eevee_settings(scene)
    T.check('global illumination on (fast GI inside the ray tracing; reflections from the probes)',
            ee.use_fast_gi and ee.use_raytracing and ee.ray_tracing_method == 'PROBE',
            f'fast GI {ee.use_fast_gi}, ray tracing {ee.use_raytracing} ({ee.ray_tracing_method})')
    if A['vrm']:
        T.load_singer(L.to_blender(SR.MARK['pos']), 0.0, SR.SUIT_SCALE, parent=show.parts['turntable']['platter'])
    tb = time.perf_counter()
    secs = show.bake_probes(scene)
    T.check('stage probe baked', bool(secs), f'{secs} ({time.perf_counter() - tb:.1f} s)')
    stills = []
    want = [c for c in A['cams'].split(',') if c]
    lum = {}
    for i, nm in enumerate(want):
        cam, t, st = SHOTS[nm]
        f = 1 + i
        show.update(t, {'spin': spin_at(t), **st}, frame=f, camera=cams[cam])
        path = os.path.join(OUT, f'sr_{nm}.png')
        T.render_still(scene, cams[cam], f, path)
        mean, clip, black = T.stats(path)
        lum[nm] = mean
        hi = 0.75 if cam in ('close', 'wall') else 0.6      # the white ENGINE sheet fills these (no performer)
        T.check(f'{nm}: exposed (mean luma 0.02..{hi}, clipped < 4 %)', 0.02 < mean < hi and clip < 0.04,
                f'mean {mean:.3f}, clipped {100 * clip:.2f} %, black {100 * black:.1f} %')
        stills.append(path)
    if {'reveal', 'reveal_dim', 'reveal_blackout'} <= set(lum):
        T.check('the state keys read on screen: reveal > dimmed wall without beams > blackout',
                lum['reveal'] > lum['reveal_dim'] > lum['reveal_blackout'],
                f"{lum['reveal']:.3f} > {lum['reveal_dim']:.3f} > {lum['reveal_blackout']:.3f}")
    if A['look']:
        # an aeropittura look (INTERIORS.md's note: under argue every near-white lands between the ramp's orange and
        # white stops, so the stage paints peach; the palette weight pulled back to 0.22 keeps it white, as
        # sr_final_reveal_cold in the WebGPU probes); the sun cones come from the face height on the mark
        U = T.apply_look(scene, A['look'], palette=0.22 if A['look'] == 'argue' else None)
        for nm in [c for c in A['look_cams'].split(',') if c in want]:
            ok = T.aim_look(scene, U, cams[nm], show.focal)
            path = os.path.join(OUT, f'sr_{nm}_{A["look"]}_cold.png')
            T.render_still(scene, cams[nm], 1 + want.index(nm), path)
            mean, clip, black = T.stats(path)
            T.check(f'{nm} under the cold {A["look"]} look: focal projected, exposed', ok and 0.02 < mean < 0.7,
                    f'mean {mean:.3f}, clipped {100 * clip:.2f} %')
            stills.append(path)
    T.sheet(stills, os.path.join(OUT, 'sr_sheet.jpg'))
    if A['save']:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'showroom_probe.blend'), compress=True)
    return T.done()


if __name__ == '__main__':
    rc = main()
    sys.stdout.flush()
    if rc:
        sys.exit(rc)

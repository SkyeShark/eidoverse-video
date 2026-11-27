"""The WAKE ANOTHER ONE hall (eidoblend.sets.wake_another_one.hall): the small hall built with its look, its machines
driven through their controls, two stills. Blender (a GPU job: EEVEE, 960 x 540, 16 samples):

    bash run_blender.sh blender/tests/sets_wake_another_one/test_hall.py [--no-render] [--layout-only] [--no-trees]

Its CC0 sets and models come from the shared library (EIDO_ASSET_CACHE, else this checkout's cache; fetched on first
use unless EIDO_NO_FETCH=1). The yard's trees need a SeedThree checkout (SEEDTHREE_DIR, or one beside this checkout);
without one they are left out and the test says so. Checks (PASS / FAIL):
  1. the layout: its lines, units, cameras, control empties, the carton's measures
  2. the crane: run 0 -> 1 lifts unit 0's hood off its tray and sets it in the stack's first slot, the bridge back at its
     park; run 1.5 has it over unit 1, its ring down on the hood; along_offset moves the bridge
  3. swap rolls unit 0's tray out to the main track; travel rolls the stream; the meter's drums show the number; the
     pendant's button and the printer's sheet move with press and feed
  4. animate() keys a control and the machine follows it on the frame; no frame handler is installed, every driver is a
     simple expression (it evaluates without Python)
  5. the look: no layout material is left a flat colour (each reads a scan, an image or is an emitter or glass)
  6. the stills (out/hall_*.png): written, neither black nor blown
A PASS is not a look: open the stills.
"""
import os
import sys
import time

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend import common  # noqa: E402
from eidoblend.sets.wake_another_one import hall as HALL  # noqa: E402

OUT = os.path.join(HERE, 'out')
FAILS = []


def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg, flush=True)
    if not ok:
        FAILS.append(msg)


def wpos(name):
    bpy.context.view_layer.update()
    return bpy.data.objects[name].matrix_world.translation.copy()


def setp(ob, prop, v):
    bpy.data.objects[ob][prop] = float(v)
    bpy.data.objects[ob].update_tag()
    bpy.context.view_layer.update()


def seedthree():
    try:
        from eidoblend.trees.seedthree_api import find_seedthree
        return find_seedthree()
    except RuntimeError as ex:
        print(f'[skip] the yard\'s SeedThree trees: {ex}', flush=True)
        return None


def flat(m):
    """a material with no image, no scan, no emission and no transmission: a flat colour"""
    if m.node_tree is None:
        return True
    for n in m.node_tree.nodes:
        if n.type in ('TEX_IMAGE', 'TEX_ENVIRONMENT', 'TEX_NOISE', 'TEX_VORONOI', 'EMISSION'):
            return False
        if n.type == 'BSDF_PRINCIPLED' and (n.inputs['Emission Strength'].default_value > 0 or n.inputs['Emission Strength'].is_linked
                                           or n.inputs['Transmission Weight'].default_value > 0):
            return False
    return True


def main():
    a = common.script_args()
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = 24
    look = '--layout-only' not in a
    trees = look and '--no-trees' not in a and seedthree() is not None
    t0 = time.time()
    H = HALL.build(small=True, look=look, sky='sky' if look else None, trees=trees, bake=look and '--no-render' not in a)
    print(f'[test] built in {time.time() - t0:.1f} s (look {look}, trees {trees})', flush=True)
    rep = H.report['layout']
    L = H.layout
    # 1. the layout
    check(rep['lines']['lines'] == 3 and rep['lines']['units'] == 30, f"the small hall's lines: {rep['lines']}")
    need = {'cam_aisle_out', 'cam_aisle_in', 'cam_station', 'cam_dock', 'cam_drums', 'cam_line_long', 'cam_top_unit1'}
    check(need <= set(H.cameras), f'cameras: {len(H.cameras)} ({sorted(need - set(H.cameras))} missing)')
    ctl = {'gantry_ctl', 'track_ctl', 'crowd_ctl', 'meter_cabinet_ctl', 'gantry_pendant'} | ({'printer_ctl', 'look_ctl'} if look else set())
    check(ctl <= set(H.controls), f'controls: {sorted(H.controls)}')
    meas = rep['carton']
    check(abs(meas['hood_height'] - (L['carton']['size'][2] - L['carton']['seam_z'])) < 1e-6 and len(H.marks) >= 30,
          f"the carton {meas}, {len(H.marks)} marks")
    # 2. the crane
    setp('gantry_ctl', 'run', 0.0)
    h0_tray = wpos('line_00_hood_0')
    park = wpos('gantry_bridge').y
    setp('gantry_ctl', 'run', 0.5)
    h0_up = wpos('line_00_hood_0')
    setp('gantry_ctl', 'run', 1.0)
    h0_slot = wpos('line_00_hood_0')
    slot0 = wpos('line_00_stack_slot_0')
    check(h0_up.z > h0_tray.z + 0.4 and (h0_slot - slot0).length < 1e-4,
          f'run lifts unit 0\'s hood ({h0_tray.z:.3f} -> {h0_up.z:.3f} m at 0.5) and sets it in slot 0 at 1.0 (off by {(h0_slot - slot0).length * 1000:.3f} mm)')
    setp('gantry_ctl', 'run', 1.3)
    by = wpos('gantry_bridge').y
    ring = wpos('gantry_ring').z
    check(abs(by - (L['line']['pitch'] * 1)) < 0.02 and ring < L['gantry']['ring_top'] - 0.5,
          f'run 1.3: the bridge over unit 1 (y {by:.3f}, park {park:.3f}), the ring down at {ring:.3f} m')
    setp('gantry_ctl', 'along_offset', 0.5)
    by2 = wpos('gantry_bridge').y
    setp('gantry_ctl', 'along_offset', 0.0)
    check(abs(by2 - by - 0.5) < 1e-4, f'along_offset 0.5 moves the bridge {by2 - by:.4f} m')
    setp('gantry_ctl', 'run', 10.0)
    # 3. the other machines
    setp('track_ctl', 'swap', 0.0)
    ta0 = wpos('line_00_tray_a')
    setp('track_ctl', 'swap', 0.6)
    ta1 = wpos('line_00_tray_a')
    check(abs(ta0.x) < 1e-6 and abs(ta1.x - L['main_track']['x']) < 1e-4 and ta1.y > ta0.y + 5.0,
          f'swap rolls unit 0\'s tray out: x {ta0.x:.3f} -> {ta1.x:.3f}, y {ta0.y:.2f} -> {ta1.y:.2f}')
    setp('track_ctl', 'swap', 1.0)
    s0 = wpos('stream_box_00')
    setp('track_ctl', 'travel', 1.0)
    s1 = wpos('stream_box_00')
    setp('track_ctl', 'travel', 0.0)
    check(abs((s1 - s0).length - 1.0) < 1e-4, f'travel 1 m rolls a stream carton {(s1 - s0).length:.4f} m')
    setp('meter_cabinet_ctl', 'meter', 1234.0)
    rot = [bpy.data.objects['meter_drum_%d' % k].matrix_world.to_euler().x for k in range(4)]
    want = [4, 3, 2, 1]
    got = [round(((r / 0.6283185) % 10 + 10) % 10, 3) for r in rot]
    check(all(abs(g - w) < 0.01 or abs(g - w) > 9.99 for g, w in zip(got, want)), f'the meter shows 1234: the drums at {got} tenths of a turn')
    setp('gantry_pendant', 'press', 0.0)
    b0 = wpos('gantry_pendant_button')
    setp('gantry_pendant', 'press', 1.0)
    b1 = wpos('gantry_pendant_button')
    setp('gantry_pendant', 'press', 0.0)
    check(abs((b1 - b0).length - L['gantry']['pendant']['button_travel']) < 1e-5, f'press moves the button {(b1 - b0).length * 1000:.2f} mm')
    if look:
        p0 = wpos('sheet_path')
        setp('printer_ctl', 'feed', 1.0)
        p1 = wpos('sheet_path')
        out = wpos('sheet_out')
        setp('printer_ctl', 'feed', 0.0)
        check((p1 - out).length < 1e-4 and (p1 - p0).length > 0.05, f'feed carries the sheet {(p1 - p0).length * 1000:.1f} mm onto the tray')
    # 4. keys, no handler, simple drivers
    HALL.animate({'run': [(1, 2.0), (49, 3.0)], 'meter': [(1, 3861.0), (49, 3861.0)]})
    sc.frame_set(25)
    run25 = bpy.data.objects['gantry_ctl']['run']
    bpy.context.view_layer.update()
    by25 = wpos('gantry_bridge').y
    check(abs(run25 - 2.5) < 1e-4 and by25 > L['line']['stack']['y0'] - 2.0, f'animate keys run: frame 25 reads {run25:.4f}; the bridge at y {by25:.3f}')
    handlers = sum(len(h) for h in (bpy.app.handlers.frame_change_pre, bpy.app.handlers.frame_change_post,
                                    bpy.app.handlers.render_pre, bpy.app.handlers.depsgraph_update_post))
    drivers = [d for o in bpy.data.objects if o.animation_data for d in o.animation_data.drivers]   # (constraints' too)
    not_simple = [d.data_path for d in drivers if not d.driver.is_simple_expression]
    check(handlers == 0 and drivers and not not_simple, f'{len(drivers)} drivers, all simple expressions ({not_simple[:3]}); {handlers} handlers')
    sc.frame_set(1)
    # 5. the look
    if look:
        layout_mats = ['hall_concrete', 'hall_wall_panel', 'hall_roof', 'steel_galv', 'steel_dark', 'machine_white', 'machine_teal',
                       'rubber_black', 'rack_upright', 'rack_beam', 'floor_line_paint', 'cabinet_grey', 'drum_white', 'drum_ink',
                       'dock_apron', 'carton_board', 'carton_insert', 'paper_placeholder', 'strip_light_glow', 'glass_placeholder']
        flats = [n for n in layout_mats if flat(bpy.data.materials[n])]
        check(not flats, f'no layout material left a flat colour ({flats})')
        lk = H.report['look']
        print(f"[test] the look: {lk.get('light')}, racks {lk.get('racks')}, rollers {lk.get('rollers')}, probe bake "
              f"{lk.get('probe_bake_seconds')} s, {lk.get('seconds')} s", flush=True)
    # 6. the stills
    if '--no-render' in a or not look:
        print('[test] no stills (--no-render or --layout-only)', flush=True)
    else:
        sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 960, 540, 100
        sc.eevee.taa_render_samples = 16
        sc.render.use_motion_blur = False
        sc.render.image_settings.file_format = 'PNG'
        HALL.animate({'run': [(1, 3.4)], 'travel': [(1, 0.0)], 'swap': [(1, 1.0)], 'meter': [(1, 3861.0)]})
        for nm in ('cam_aisle_out', 'cam_station'):
            sc.camera = H.cameras[nm]
            sc.frame_set(1)
            H.bake_sky(nm, 1, 1)
            p = os.path.join(OUT, f'hall_{nm}.png')
            sc.render.filepath = p
            t1 = time.time()
            bpy.ops.render.render(write_still=True)
            img = bpy.data.images.load(p, check_existing=False)
            px = np.empty(img.size[0] * img.size[1] * 4, np.float32)
            img.pixels.foreach_get(px)
            px = px.reshape(-1, 4)[:, :3]
            m, hi = float(px.mean()), float((px > 0.98).mean())
            bpy.data.images.remove(img)
            check(0.03 < m < 0.9 and hi < 0.08, f'{os.path.basename(p)}: mean {m:.3f}, blown {hi * 100:.2f} % ({time.time() - t1:.1f} s)')
    print(f'[test] {len(FAILS)} failed in {time.time() - t0:.1f} s', flush=True)
    if FAILS:
        raise SystemExit(1)


main()

"""The claudesona's wardrobe (claudesona/wardrobe.py, _paint.py, look.py) on claude_suit_wardrobe.vrm at 0.87, every
outfit worn KEYED on its own block of frames (playing idle), then measured at each block and probed in close-ups.

Checks:
    WARDROBE, BADGES, MODIFICANTI, FINAL_CHORUS equal claudesona_wardrobe.js's (run in deno)
    every OPTIONAL layer is found (boater_band has no object of its own in this VRM: reported)
    at each outfit's frame: exactly its `show` layers render; each painted material's slot is the outfit's paint and
        every other painted material is back at slot 0; the hoodie's jersey_collar faces are gone (Geometry Nodes),
        present on the turtleneck
    cyclist_1892: each folded petal turned by its fold angle from its rest direction (measured on the pose) and kept
        there by the spring bake (initial state); the boater's brim plane normal along the head's up tipped 4 deg back;
        the auto fold found the petals the hat cuts; the brim lift within 30 mm
    petals('mac_launch_1984') repaints the petals alone, petals(None) gives the worn outfit's own back
    set_look('pbr') switches every MToon material to a Principled output and back
Stills: out/wardrobe_patterns_sheet.png (stripes, blocks + perPetal, rainbow petals, herringbone, gradient + sweep,
canvas, pinstripes, the hoodie), out/wardrobe_cyclist_sheet.png (front, side, back; then the same without the folds),
out/wardrobe_look_sheet.png (the lab coat in MToon and in PBR).

    bash run_blender.sh blender/tests/claudesona/test_wardrobe.py [--no-render]
    # a GPU job; on a shared machine queue it with EIDO_GPU_WRAP (blender/tests/_where.py)
"""

import json
import math
import os
import sys
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.characters import load_vrm, play_vrma_default  # noqa: E402
from eidoblend.characters.claudesona import look as LK  # noqa: E402
from eidoblend.characters.claudesona import tuta as TU  # noqa: E402
from eidoblend.characters.claudesona.wardrobe import OPTIONAL, WARDROBE, make_wardrobe, preset  # noqa: E402
from eidoblend.characters.springs import SpringRig, bake_springs  # noqa: E402

ARGS = S.argv()
RENDER = '--no-render' not in ARGS
FPS, HOLD = 30, 14
SCALE = 0.87


def parity(C, R):
    ref = S.run_mjs('face_parity.mjs', {'root': S.REPO, 'wardrobe': True}, 'wardrobe_tables')['wardrobe']
    mine = json.loads(json.dumps(WARDROBE))
    same = ref['WARDROBE'] == mine
    if not same:
        diff = [k for k in set(ref['WARDROBE']) | set(mine) if ref['WARDROBE'].get(k) != mine.get(k)]
        R['wardrobe_diff'] = diff
    C.check("WARDROBE equals claudesona_wardrobe.js's (18 presets, every show / paint / fold / hat)", same,
            f"{len(mine)} presets" + ('' if same else f' differ: {R["wardrobe_diff"]}'))
    C.check('BADGES, MODIFICANTI, FINAL_CHORUS equal the JS module',
            ref['BADGES'] == TU.BADGES and ref['MODIFICANTI'] == TU.MODIFICANTI and ref['FINAL_CHORUS'] == TU.FINAL_CHORUS,
            ', '.join(TU.BADGES))


def collar_faces(o, slot_name, wd):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    k = wd.slots[o.name].index(slot_name)
    mi = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get('material_index', mi)
    ev.to_mesh_clear()
    return int((mi == k).sum())


def main():
    R, C = {}, S.Checks('wardrobe')
    try:
        parity(C, R)
        sc = S.clean_scene(FPS)
        h = load_vrm('claude_suit_wardrobe')
        h.arm.scale = (SCALE,) * 3
        bpy.context.view_layer.update()
        wd = make_wardrobe(h)
        missing = [n for n in OPTIONAL if n not in wd.layers]
        R['missing_layers'] = missing
        C.check('every OPTIONAL layer found (but boater_band, which has no object in this VRM)', missing == ['boater_band'],
                f'{len(wd.layers)} layers; missing {missing}')
        preset('cyclist_1892:nofold', base='cyclist_1892', fold=None, hat={'seat': 'auto', 'sink': 0.008, 'tilt': -4,
                                                                            'scale': 1.15, 'fold': False})
        keys = list(WARDROBE)
        blocks = {k: 1 + i * HOLD for i, k in enumerate(keys)}
        sc.frame_start, sc.frame_end = 1, blocks[keys[-1]] + HOLD - 1
        play_vrma_default(h, 'idle', t=0.0, loop=True, until=sc.frame_end / FPS)
        worn = {}
        for k in keys:
            wd.wear(k, frame=blocks[k])
            worn[k] = {'folds': dict(wd.folds), 'lift': wd.lift, 'hat_n': (tuple(wd._hat_local['n']) if wd._hat_local else None)}
        R['cyclist_folds'] = worn['cyclist_1892']['folds']
        rep = bake_springs(h, 1, sc.frame_end, resets=list(blocks.values()), preroll=0.0)
        R['springs'] = {x: rep[x] for x in ('springs', 'joints', 'keys', 'nan', 'override_frames')}
        C.check('the spring bake over every outfit block: no NaN', rep['nan'] == 0, f"{rep['keys']} keys")
        bad = []
        for k in keys:
            f = blocks[k] + HOLD - 2
            sc.frame_set(f)
            p = WARDROBE[k]
            want = set(p.get('show', [])) & set(wd.layers)
            shown = {n for n, o in wd.layers.items() if not o.hide_render}
            if shown != want:
                bad.append((k, sorted(shown ^ want)))
            for name, spec in (p.get('paint') or {}).items():
                r = wd._rigs.get(name)
                if r is None or int(h.arm[r.prop]) != r.slots.index(spec):
                    bad.append((k, f'paint {name}'))
            if 'cs_tuta.eyes' in h.arm:          # the TuTa's catchlights: a step at the wear, held over the block
                on = 'tuta' in (p.get('uf') or [])
                for prop, want in (('cs_tuta.eyes', 1.0 if on else float(p.get('eyeLights', 0))),
                                   ('cs_tuta.eye_neon', 1.0 if on else 0.0)):
                    if abs(float(h.arm[prop]) - want) > 1e-6:
                        bad.append((k, f'{prop} {float(h.arm[prop]):.3f} != {want}'))
            for name, r in wd._rigs.items():
                want_slot = r.slots.index((p.get('paint') or {})[name]) if name in (p.get('paint') or {}) else 0
                if name not in (p.get('paint') or {}) and int(h.arm[r.prop]) != 0:
                    bad.append((k, f'{name} not reset'))
                # what the render reads: each material's switch driver, evaluated (valid, on the outfit's slot)
                for m in r.mats:
                    v = m.node_tree.nodes.get('cs.paint')
                    fc = next((fc for fc in m.node_tree.animation_data.drivers
                               if fc.data_path.startswith('nodes["cs.paint"]')), None) if m.node_tree.animation_data else None
                    if v is None or fc is None or not fc.driver.is_valid or abs(v.outputs[0].default_value - want_slot) > 1e-6:
                        bad.append((k, f'{m.name} driver {None if fc is None else fc.driver.is_valid} '
                                       f'{None if v is None else v.outputs[0].default_value} != {want_slot}'))
        R['outfit_mismatches'] = bad
        C.check("every outfit at its keyed frame: its layers, its paints (the property AND each material's driver, "
                "valid and on the slot: what the render reads), the rest reset", not bad,
                f'{len(keys)} outfits' + ('' if not bad else f'; {bad[:6]}'))
        # perPetal: the per-vertex colour attribute (the JS's petalColor) holds each petal's C64 colour, the centre its own
        from eidoblend.characters.claudesona._paint import PETAL_ATTR, lin, petal_rgb_attr
        spec = WARDROBE['colorblock_1982']['paint']['petals']
        fl = wd._flower_obj()
        at = fl.data.attributes.get(petal_rgb_attr(spec))
        ok, worst = at is not None, 0.0
        if ok:
            n = len(fl.data.vertices)
            ids = np.empty(n, np.float32)
            fl.data.attributes[PETAL_ATTR].data.foreach_get('value', ids)
            rgb = np.empty(n * 4, np.float32)
            at.data.foreach_get('color', rgb)
            rgb = rgb.reshape(-1, 4)[:, :3]
            pal = [lin(c) for c in spec['colors']] + [lin(spec['center'])]
            for k in range(13):
                sel = ids == k
                if sel.any():
                    worst = max(worst, float(np.abs(rgb[sel] - np.array(pal[k])).max()))
            ok = worst < 1e-5 and int((ids == 12).sum()) > 0
        C.check("perPetal: every flower vertex carries its petal's C64 colour, the centre #352879 (linear, the JS's "
                "petalColor)", ok, f'max error {worst:.1e}')
        jersey = wd.layers['jersey']
        sc.frame_set(blocks['hoodie_2016'] + 3)
        n_h = collar_faces(jersey, 'jersey_collar', wd)
        sc.frame_set(blocks['turtleneck_1966'] + 3)
        n_t = collar_faces(jersey, 'jersey_collar', wd)
        C.check("hide: the hoodie drops the jersey's roll neck (jersey_collar), the turtleneck keeps it", n_h == 0 and n_t > 0,
                f'hoodie {n_h} faces, turtleneck {n_t}')
        # the cyclist: folds and the hat, measured at its block
        fc = blocks['cyclist_1892']
        sc.frame_set(fc)
        ov = h.spring_overrides.get(fc, {})
        rig = SpringRig(h)
        angs = {}
        for key, (deg, s) in (WARDROBE['cyclist_1892']['fold'].items()):
            root = wd.petal_root(key)
            o = ov.get(root)
            if o is None or o['basis'] is None:
                continue
            b = h.arm.data.bones[root]
            ax = (rig.by_bone[root].axis)
            folded = (o['basis'] @ ax)
            angs[key] = round(math.degrees(ax.angle(folded)), 2)
        R['fold_turn_deg'] = angs
        auto = {}
        sc.frame_set(fc + HOLD - 2)
        for key in worn['cyclist_1892']['folds']:
            auto[key] = wd.petal_dir(key)
        R['petal_dirs_in_block'] = auto
        C.check('cyclist: each folded petal root is turned by its fold angle (the spring bake starts from it)',
                bool(angs) and all(a > 140 for a in angs.values()),
                f"{angs}; the auto fold: {worn['cyclist_1892']['folds']}")
        hat = wd.layers['boater']
        sc.frame_set(fc)
        hf = wd.head_frame()
        n_w = (hat.matrix_world.to_3x3() @ Vector(worn['cyclist_1892']['hat_n'])).normalized()
        tilt = math.degrees(n_w.angle(Vector(hf['uF'])))
        lift = worn['cyclist_1892']['lift']
        R['hat'] = {'tilt_deg': round(tilt, 2), 'lift_mm': round(1000 * lift, 1)}
        C.check("cyclist: the boater's brim normal along the head's up, tipped ~4 deg back; lift within 30 mm",
                abs(tilt - 4.0) < 1.5 and 0.0 <= lift <= 0.0301, f"tilt {tilt:.2f} deg, lift {1000 * lift:.1f} mm")
        # ... and it stays there through the block (the still is its last frames): in the head bone's frame
        hb = h.humanoid['head']
        rel = {}
        for f in (fc, fc + HOLD // 2, fc + HOLD - 2):
            sc.frame_set(f)
            rel[f] = (h.arm.matrix_world @ h.arm.pose.bones[hb].matrix).inverted() @ hat.matrix_world
        d_mm = max((rel[f].translation - rel[fc].translation).length for f in rel) * 1000
        d_deg = max(math.degrees(rel[f].to_quaternion().rotation_difference(rel[fc].to_quaternion()).angle) for f in rel)
        d_sc = max(abs(s - rel[fc].to_scale()[0]) for f in rel for s in rel[f].to_scale())
        R['hat_drift'] = {'mm': round(d_mm, 4), 'deg': round(d_deg, 4), 'scale': round(d_sc, 5)}
        C.check("cyclist: the boater stays seated through its block, to the still's frame (no easing toward the next "
                "outfit's hat)", d_mm < 0.1 and d_deg < 0.01 and d_sc < 1e-4, f"{R['hat_drift']}")
        # petals(): another era's petals only, then the outfit's own back
        f = sc.frame_end + 5
        wd.wear('professor_tweed_1984', frame=f)
        wd.petals('mac_launch_1984', frame=f + 5)
        wd.petals(None, frame=f + 10)
        r = wd._rigs['petals']
        sc.frame_set(f + 6)
        s1 = int(h.arm[r.prop])
        sc.frame_set(f + 11)
        s2 = int(h.arm[r.prop])
        ok = r.slots[s1] == WARDROBE['mac_launch_1984']['paint']['petals'] and r.slots[s2] == '#ff9800'
        C.check("petals(): the 1984 rainbow on the tweed outfit, then the tweed's amber back", ok, f'slots {s1} -> {s2}')
        if RENDER:
            render(sc, h, wd, blocks, R)
        # the PBR option (after the renders that use MToon)
        rep = LK.set_look(h, 'pbr')
        pbr = sum(1 for m in bpy.data.materials if m.node_tree and m.node_tree.get_output_node('EEVEE') is not None
                  and m.node_tree.get_output_node('EEVEE').name == 'pbr.out')
        rep2 = LK.set_look(h, 'mtoon')
        back = sum(1 for m in bpy.data.materials if m.node_tree and 'pbr.out' in m.node_tree.nodes)
        C.check("set_look('pbr') gives every MToon material a Principled EEVEE output; 'mtoon' takes it away",
                pbr == rep['materials'] and back == 0, f"{pbr} materials PBR, {back} left after 'mtoon'")
    except Exception:
        traceback.print_exc()
        R['error'] = traceback.format_exc()
        C.check('ran without an exception', False)
    R['checks'] = C.rows
    R['all_pass'] = C.all_pass and 'error' not in R
    with open(os.path.join(S.OUT, 'wardrobe.json'), 'w', encoding='utf-8') as f:
        json.dump(R, f, indent=1, default=str)
    print('[wardrobe] ALL PASS' if R['all_pass'] else '[wardrobe] SOME FAILED', flush=True)


def _chest_cam(h, name, yaw=20.0, dist=1.35, dz=-0.32, lens=50):
    hb = h.arm.matrix_world @ h.arm.data.bones[h.humanoid['head']].head_local
    c = Vector((hb.x, hb.y, hb.z + dz))
    a = math.radians(yaw)
    cam = S.camera(name, lens=lens)
    S.aim(cam, (c.x + dist * math.sin(a), c.y - dist * math.cos(a), c.z + 0.05), c)
    return cam


def render(sc, h, wd, blocks, R):
    S.probe_render(sc, res=(360, 420), samples=16)
    S.turntable_studio(sc, light=0.7)
    pats = ['ringer_tee_1978', 'colorblock_1982', 'mac_launch_1984', 'professor_tweed_1984', 'bing_2023', 'march',
            'sax_guy_2010', 'hoodie_2016']
    cam = _chest_cam(h, 'chest')
    paths = []
    for k in pats:
        p = os.path.join(S.OUT, f'wardrobe_{k}.png')
        S.still(sc, cam, blocks[k] + HOLD - 2, p)
        paths.append(p)
    R['patterns_sheet'] = S.sheet(paths, os.path.join(S.OUT, 'wardrobe_patterns_sheet.png'), cols=4)
    p2 = []
    for k in ('cyclist_1892', 'cyclist_1892:nofold'):
        for yaw in (15, 90, 180):
            cam = _chest_cam(h, f'hat{yaw}', yaw=yaw, dist=1.05, dz=0.02, lens=50)
            p = os.path.join(S.OUT, f'wardrobe_{k.replace(":", "-")}_y{yaw:03d}.png')
            S.still(sc, cam, blocks[k] + HOLD - 2, p)
            p2.append(p)
    R['cyclist_sheet'] = S.sheet(p2, os.path.join(S.OUT, 'wardrobe_cyclist_sheet.png'), cols=3)
    body = _chest_cam(h, 'body', yaw=20, dist=3.4, dz=-0.55, lens=50)
    f = blocks['lab_coat_1961'] + HOLD - 2
    p3 = [os.path.join(S.OUT, 'wardrobe_lab_coat_mtoon.png'), os.path.join(S.OUT, 'wardrobe_lab_coat_pbr.png')]
    S.still(sc, body, f, p3[0])
    LK.set_look(h, 'pbr')
    S.still(sc, body, f, p3[1])
    LK.set_look(h, 'mtoon')
    R['look_sheet'] = S.sheet(p3, os.path.join(S.OUT, 'wardrobe_look_sheet.png'), cols=2)


main()

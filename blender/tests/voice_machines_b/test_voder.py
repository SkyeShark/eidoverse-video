"""The Voder (props/voice_machines/voder.py): build, the demo fingering against voder.js, keyed updates, the
registry route, and probe renders at true scale.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/voice_machines_b/test_voder.py            # checks
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <this> --render              # + stills

Prints PASS / FAIL lines; stills go to out/voder_*.png.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _stage as S  # noqa: E402

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402


def run(render=False):
    sc = S.fresh_scene(frames=(1, 72))
    from eidoblend.props.voice_machines import voder
    vo = voder.build()
    P = vo.parts
    S.check('voder: 10 keys with their bands', len(P['keys']) == 10 and list(P['keys'][3]['band']) == [700, 1000])
    S.check('voder: 3 stop keys, quiet, wrist, pedal, needle, lamp, grille',
            len(P['stop_keys']) == 3 and all(P[k] is not None for k in ('quiet_key', 'wrist_bar', 'pedal', 'lamp', 'grille'))
            and P['dial']['needle'] is not None and 'cloth' in voder.roles_of(P['grille']))
    S.check('voder: every GLB role has a material', not vo.missing_roles, ', '.join(sorted(vo.missing_roles)))
    S.decals_drawn('voder', vo.made['images'])
    S.decals_on_panels('voder', vo, 5, set(vo.seated_decals) == {'voder_panel_labels'},
                       '; the panel labels, touching the panel at 0.01 mm, lifted to 0.2')

    # the demo fingering against the engine (deno dump of voder.js pattern(t))
    dump = S.OUT / 'parity_js.json'
    if dump.exists():
        J = json.loads(dump.read_text())
        worst = 0.0
        for row in J['pattern']:
            p = voder.pattern(row['t'])
            for k in ('quiet', 'wrist', 'pedal', 'level'):
                worst = max(worst, abs(p[k] - row[k]))
            for a, b in zip(p['keys'] + p['stops'], row['keys'] + row['stops']):
                worst = max(worst, abs(a - b))
        S.check('voder: pattern(t) equals voder.js on 401 samples', worst < 1e-12, f'max |diff| {worst:.2e}')
    else:
        S.check('voder: parity dump present (deno parity_dump.mjs)', False, str(dump))

    # footprint (the registry's measured box, Blender axes)
    bpy.context.view_layer.update()
    lo, hi = S.bounds([vo.group] + list(vo.group.children_recursive))
    size = hi - lo
    want = voder.MACHINE['footprint']
    S.check('voder: footprint matches index.js (1.28 x 1.32 x 1.70 m)',
            all(abs(a - b) < 0.03 for a, b in zip(size, want)), f'{size.x:.3f} x {size.y:.3f} x {size.z:.3f}')
    cx, cy = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
    feet = S.rest_height(vo)
    S.check("voder: centre matches index.js's (0.0, 0.32 in Blender axes); it stands on z = 0 (its cord runs into "
            'the floor)', abs(cx - voder.MACHINE['center'][0]) < 0.02 and abs(cy - voder.MACHINE['center'][1]) < 0.02
            and abs(feet) < 0.002, f'({cx:.3f}, {cy:.3f}), feet {feet * 1000:.1f} mm, cord {lo.z * 1000:.1f} mm')

    # it sings: keyed over a phrase, LINEAR, and the keys follow the pattern
    n = vo.animate(lambda t: {'voice': 0.85, 'power': 1.0}, frames=(1, 72))
    S.check('voder: animate keyed the phrase', n > 40, f'{n} keys after simplify')
    f = max(range(1, 73), key=lambda fr: voder.pattern(vo.time_at(fr))['keys'][7])
    t = vo.time_at(f)
    p = voder.pattern(t)
    g = voder.sstep(0.02, 0.35, 0.85)
    sc.frame_set(f)
    k8 = P['keys'][7]
    got = k8.rotation_euler[0]
    want8 = voder.KEY_MAX * p['keys'][7] * g
    S.check(f'voder: key 8 at frame {f} follows the fingering (keyed)', abs(got - want8) < 1e-5 and want8 > 0.05, f'{got:.5f} vs {want8:.5f}')
    lin = all(k.interpolation == 'LINEAR' for fc in voder._action_fcurves(k8.animation_data.action)
              for k in fc.keyframe_points)
    S.check('voder: keys are LINEAR', lin)
    S.check('voder: level keyed on the root', abs(vo.group['level'] - 0.85) < 1e-6, f"{vo.group['level']:.3f}")
    # the needle's rest is a tilt about X; the swing about the face normal must keep it
    nd = P['dial']['needle']
    S.check('voder: needle keeps its panel tilt while swinging', nd.rotation_mode == 'ZYX' and abs(nd.rotation_euler[0] - 2 * math.atan2(0.3577, 0.9338)) < 2e-3)

    # explicit control state (the JS's full-control form, camelCase accepted)
    vo2_level = vo.update(3.5, {'keys': [1, 0, 0, 0, 0, 0, 0, 0, 0, 0], 'wrist': 1, 'stops': [0, 1, 0], 'quiet': 0,
                                'pedal': 0.9, 'power': 1}, frame=90)
    S.check('voder: full-control update derives the level from the keys', abs(vo2_level - 0.3) < 1e-9, f'{vo2_level}')
    lv = vo.update(3.6, {'keys': [0.2] * 10, 'stops': [0, 0, 0], 'quiet': 1, 'wrist': 0, 'pedal': 0.1, 'level': 0.7},
                   frame=91)
    S.check('voder: an explicit level wins; quiet and the pedal turn their keys',
            abs(lv - 0.7) < 1e-12 and abs(P['quiet_key'].rotation_euler[0] - voder.STOP_MAX) < 1e-6
            and abs(vo.group['level'] - 0.7) < 1e-9)

    # the registry route (another step's registry; skipped while it is not written)
    try:
        from eidoblend.props import voice_machines as VM
        m2 = VM.build_machine('voder', {'name': 'voder_reg'})
        S.check('voder: registry build_machine stamps the record', m2.group.get('voice_machine', {}).get('name') == 'voder')
        m2.dispose()
        S.check('voder: dispose removes the second machine', 'voder_reg' not in bpy.data.objects)
    except Exception as e:  # noqa: BLE001
        S.check('voder: registry route', False, repr(e))
    S.dispose_leaves_nothing('voder', lambda: voder.build(name='voder_2', glb=str(Path(voder.PACK) / 'voder.glb'),
                                                          power=0.3))

    # the kit's canvasTex(...).redraw(fn): more drawing on the same canvas, the packed image updated
    import numpy as np
    ct = voder.canvas_tex('voder_redraw_probe', 64, 32, lambda c, w, h: c.fillRect(0, 0, w, h), alpha=False)

    def red_half(c, w, h):
        c.fillStyle = '#ff0000'
        c.fillRect(0, 0, w / 2, h)
    ct.redraw(red_half)
    px = np.empty(64 * 32 * 4, np.float32)
    ct.tex.pixels.foreach_get(px)
    px = px.reshape(32, 64, 4)
    S.check('voder: canvas_tex redraw draws over its canvas and repacks the image',
            ct.redraws == 1 and ct.tex.packed_file is not None and px[5, 5, 0] > 0.99 and px[5, 5, 1] < 0.01
            and px[5, 50, :3].max() < 0.01, f'left {px[5, 5, :3]}, right {px[5, 50, :3]}')
    bpy.data.images.remove(ct.tex)

    if render:
        # the canvas art itself, as drawn (before any material): a sheet to judge the canvas-2D port
        from PIL import Image
        L = voder.json_load('voder_layout.json')
        arts = [((0, 0), 1024, 358, voder._draw_panel(L)), ((0, 358), 1024, 32, voder._draw_strip(L)),
                ((0, 390), 512, 152, voder._draw_name), ((0, 542), 512, 512, voder._draw_dial),
                ((512, 542), 512, 512, voder._draw_bell)]
        sheet = Image.new('RGBA', (1024, 1054), (60, 60, 60, 255))
        for pos, w, h, fn in arts:
            c = voder.Ctx2D(w, h, ss=3)
            fn(c, w, h)
            sheet.alpha_composite(c.image(), pos)
        sheet.save(S.OUT / 'voder_canvas_art_sheet.png')

        S.studio(sc, (0, 0.35, 0.95), dist=3.2, key=260)
        S.floor(sc)
        S.wall(sc, y=1.25, color=(0.30, 0.29, 0.27))
        cam = S.camera(sc, (1.55, -2.55, 1.55), (0.0, 0.25, 0.85), lens=35)
        S.render(S.OUT / 'voder_three_quarter_f020.png', frame=20)
        S.look_from(cam, (0.30, -0.62, 1.22), (0.02, -0.06, 0.80), lens=40)
        S.render(S.OUT / 'voder_keys_dial_close_f020.png', frame=20)
        S.look_from(cam, (0.05, -0.55, 1.42), (0.05, 0.19, 0.95), lens=45)
        S.render(S.OUT / 'voder_panel_close_f020.png', frame=20)
        S.look_from(cam, (0.25, -0.75, 1.62), (0.0, 0.55, 1.33), lens=55)
        S.render(S.OUT / 'voder_bell_grille_f020.png', frame=20)
        vo.update(vo.time_at(40), {'voice': 0.0, 'power': 0.0}, frame=40)
        S.look_from(cam, (-0.9, -2.3, 1.3), (0.0, 0.3, 0.95), lens=35)
        S.render(S.OUT / 'voder_power_off_f040.png', frame=40)
    return S.summary('voder')


if __name__ == '__main__':
    sys.exit(1 if run(render='--render' in sys.argv) else 0)

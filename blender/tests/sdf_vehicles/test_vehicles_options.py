"""Every option of the four vehicles' make() and of the objects it returns, exercised: the engine's make({paintColor,
paintRoughness, decalText, metalColor, camo}), the live uniforms changed and keyed after the build (the camo's keys
holding), the engine's createSdfObject({...spec, uniforms}) overrides, the badge text redrawn, the lamps, two
instances with their own liveries, the baked shading path, the resolution options, the errors the engine raised, a
saved .blend reopened; plus the pure pieces (colour parsing, the camo names, the badge canvas, the GLSL evaluator
against the numpy library, the stripe masks at known points).

    cd <main checkout> && HEAVY_VRAM_GB=6 bash work/claude_body/work/tmp/heavy.sh 16 bash run_blender.sh \
        <worktree>/blender/tests/sdf_vehicles/test_vehicles_options.py [-- parts=a,b]   (parts: pure, live, sheets,
        reopen; default all)

Sheets in out/: opt_paint_roughness.png (the modern sedan in deep blue at paintRoughness 0, 0.18, 0.45, 0.8),
opt_metal_presets.png (one sleek car switched live through the six METAL_PRESETS), opt_camo.png (one jet
switched live through the four schemes), opt_cyber_live.png (repainted after the build, keyed cyan -> amber at frames
1 / 25 / 13, the badge redrawn), opt_cyber_baked.png (shading='parts' beside shading='baked'), opt_grille.png (the hex
grille close up beside the engine's march), opt_reopen.png (before saving and after reopening).
"""

import math
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _vcommon as V  # noqa: E402
import engine_march as EM  # noqa: E402  (tests/sdf, on sys.path through _vcommon)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend import sdf  # noqa: E402
from eidoblend.sdf.vehicles import parts as P  # noqa: E402
from eidoblend.sdf.vehicles import badge as B  # noqa: E402
from eidoblend.sdf.vehicles.livery import eval_glsl, stripe_masks  # noqa: E402

A = V.args()
PARTS_RUN = A.get('parts', 'pure,live,sheets,reopen').split(',')
W, H = int(A.get('w', '640')), int(A.get('h', '360'))
CACHE = os.path.join(V.OUT, 'cache_options')
EX = sdf.EXAMPLES


def close(a, b, tol=1e-4):
    return bool(np.allclose(np.asarray(a, float), np.asarray(b, float), atol=tol))


def render_to(name):
    p = os.path.join(V.OUT, name)
    V.render(p)
    return p


def raises(exc, fn):
    try:
        fn()
    except exc as e:
        return str(e) or exc.__name__
    except Exception as e:  # noqa: BLE001
        return None if isinstance(e, exc) else f'raised {type(e).__name__} instead: {e}'
    return None


# =============================================================================================== pure pieces ===
if 'pure' in PARTS_RUN:
    lin = P.linear_color(0xc8c8d2)
    V.check('colour: 0xc8c8d2 decodes as THREE.Color did (sRGB -> linear)', close(lin, (0.5776, 0.5776, 0.6445), 2e-4),
            str(tuple(round(x, 4) for x in lin)))
    V.check('colour: #rgb, #rrggbb, preset names and linear tuples',
            close(P.linear_color('#0ff'), P.linear_color(0x00ffff)) and close(P.linear_color('gold'),
            P.linear_color(0xffb44a)) and close(P.linear_color('magenta'), P.linear_color(0xff2bd6))
            and close(P.linear_color((0.95, 0.93, 0.88)), (0.95, 0.93, 0.88)),
            f"gold {tuple(round(x, 3) for x in P.linear_color('gold'))}")
    V.check('colour: a bad string raises', raises(ValueError, lambda: P.linear_color('#12')) is not None)
    V.check('camo: names in any case, integers truncated',
            [P.camo_id(c) for c in ('silver', 'SKY', 'Desert', 'forest', 2.7, 0)] == [0, 1, 2, 3, 2, 0])
    msg = raises(ValueError, lambda: P.camo_id('polka'))
    V.check('camo: an unknown name raises the engine\'s message', msg is not None and 'Use one of: silver, sky, desert, '
            'forest.' in msg, msg or 'did not raise')
    # the badge canvas: every '#' cell a 12 x 12 white square, the line centred (startX = 519 - 42 n, startY = 79)
    can = B.build_badge_decal('ALETH8APO')
    cells = sum(row.count('#') for ch in 'ALETH8APO' for row in B.BADGE_GLYPH_ATLAS[ch])
    ink = int((can[..., 3] > 0.5).sum())
    xs = np.nonzero(can[..., 3].max(axis=0) > 0.5)[0]
    ys = np.nonzero(can[..., 3].max(axis=1) > 0.5)[0]
    V.check('badge: ALETH8APO is its cells, 144 px each, centred on the canvas', ink == cells * 144
            and xs.min() == 141 and ys.min() == 79 and ys.max() == 79 + 6 * 14 + 11,
            f'{ink} px for {cells} cells, x {xs.min()}..{xs.max()}, y {ys.min()}..{ys.max()}')
    can2 = B.build_badge_decal('AXA')
    a_cells = sum(row.count('#') for row in B.BADGE_GLYPH_ATLAS['A'])
    mid = can2[:, 519 - 42 * 3 + 84:519 - 42 * 3 + 84 + 70, 3]
    V.check('badge: a glyph not in the atlas leaves its slot blank', int((can2[..., 3] > 0.5).sum()) == 2 * a_cells * 144
            and mid.max() == 0.0, f'{int((can2[..., 3] > 0.5).sum())} px')
    long = B.build_badge_decal('ALETHALETHALETH')
    full = sum(row.count('#') for ch in 'ALETHALETHALETH' for row in B.BADGE_GLYPH_ATLAS[ch]) * 144
    lk = int((long[..., 3] > 0.5).sum())
    lx = np.nonzero(long[..., 3].max(axis=0) > 0.5)[0]
    V.check('badge: a 15-glyph line runs off both canvas edges (clipped), as on the engine\'s canvas',
            0 < lk < full and lx.min() < 14 and lx.max() > 1009, f'{lk} of {full} px drawn, x {lx.min()}..{lx.max()}')
    up = B.decal_texture_array('ALETH8APO')
    V.check('badge: the texture array is the canvas flipped (three flipY): row 0 at the bottom',
            np.array_equal(up[0], can[-1]) and np.array_equal(up[-1], can[0]))
    # the GPU evaluator against the numpy mirror of the GLSL library
    rng = np.random.default_rng(7)
    pts = (rng.random((5000, 3)) * 6.0 - 3.0).astype(np.float32)
    gpu = eval_glsl('', 'fbm(p * 1.6)', pts)
    from eidoblend.sdf import SDF_NP
    cpu = np.asarray(SDF_NP.fbm(pts.astype(np.float64) * 1.6), np.float64)
    err = float(np.abs(gpu - cpu).max())
    V.check('eval_glsl: the GPU fbm equals the numpy library\'s', err < 2e-3, f'max |diff| {err:.2e} over 5000 points')
    # the stripe masks at points stripeMaskFn defines exactly
    side, top = stripe_masks(EX['stylized_cyberpunk_sedan']['extra'], mm=2.0)

    def side_at(z, y, k):
        i = int((z + 2.4) / 4.8 * side.shape[1])
        j = int(y / 1.55 * side.shape[0])
        return float(side[j, i, k])

    def top_at(x, z):
        i = int((x + 1.05) / 2.1 * top.shape[1])
        j = int((z + 2.4) / 4.8 * top.shape[0])
        return float(top[j, i])

    probes = {
        'right door tape (z 0.42, y 0.6)': (side_at(0.42, 0.6, 0), 1.0),
        'right flank between tapes (z 0.35, y 0.6)': (side_at(0.35, 0.6, 0), 0.0),
        'right number block (z -1.55, y 0.95)': (side_at(-1.55, 0.95, 0), 1.0),
        'right rocker tape (z 0.0, y 0.42)': (side_at(0.0, 0.42, 0), 1.0),
        'left wedge (z -1.5, y 0.85)': (side_at(-1.5, 0.85, 1), 1.0),
        'left flank at the right tape (z 0.42, y 0.6)': (side_at(0.42, 0.6, 1), 0.0),
        'inside the front arch (z 1.4, y 0.42)': (side_at(1.4, 0.42, 0), 0.0),
        'hood diagonal (x 0.40, z 1.50)': (top_at(0.40, 1.50), 1.0),
        'left roof stripe (x -0.35, z -0.5)': (top_at(-0.35, -0.5), 1.0),
        'roof centre (x 0.0, z -0.5)': (top_at(0.0, -0.5), 0.0),
    }
    bad = {k: round(v, 3) for k, (v, want) in probes.items() if abs(v - want) > 0.05}
    V.check('stripes: the livery masks hold stripeMaskFn\'s strokes where it draws them', not bad,
            f'{len(probes) - len(bad)} of {len(probes)} probes' + (f'; off: {bad}' if bad else ''))


# ========================================================================================== live uniforms ===
def stage():
    V.purge()
    sc = V.stage(W, H, 16)
    return sc


if 'live' in PARTS_RUN:
    sc = stage()
    car = EX['stylized_cyberpunk_sedan'].make({'paintColor': 0xff2bd6, 'paintRoughness': 0.3}, cache_dir=CACHE,
                                              quality='balanced', name='opt_cyber', log=None)
    car.place_on_ground(0.0)
    V.check('make({paintColor, paintRoughness}) (camelCase dict) sets the object\'s live uniforms',
            close(car.object['uPaint'], P.linear_color(0xff2bd6)) and abs(car.object['uRough'] - 0.3) < 1e-6
            and close(car.program.values['uPaint'], P.linear_color(0xff2bd6)), str(car.live_uniforms))
    V.check('quality=balanced doubles the vehicle voxel', abs(car.voxel - 0.008) < 1e-9, f'{car.voxel * 1000:.1f} mm')
    car.set_paint('acid')
    bpy.context.view_layer.update()
    ug = [ob for ob in car.lamps if ob.get('sdf_vehicle_lamp') == 'underglow']
    dg = bpy.context.evaluated_depsgraph_get()
    col = ug[0].evaluated_get(dg).data.color if ug else (0, 0, 0)
    V.check('set_paint after the build: the property, the program and the underglow lamps (drivers) follow',
            close(car.object['uPaint'], P.linear_color('acid')) and close(tuple(col), P.linear_color('acid'), 1e-3),
            f'lamp colour {tuple(round(c, 3) for c in col)}')
    car.live_uniforms['paint_roughness'] = 0.05
    V.check('live_uniforms[...] = v (engine option names accepted)', abs(car.object['uRough'] - 0.05) < 1e-6
            and set(car.live_uniforms.keys()) == {'uPaint', 'uRough', 'uDecal'}, str(dict(car.live_uniforms.items())))
    V.check('live_uniforms rejects what the vehicle does not have',
            raises(KeyError, lambda: car.set_uniform('uMetalColor', 'gold')) is not None)
    # keyed: cyan at frame 1, amber at frame 25 -> frame 13 is half way (LINEAR)
    sc.frame_start, sc.frame_end = 1, 25
    car.key_uniform('uPaint', frame=1, value='cyan')
    car.key_uniform('uPaint', frame=25, value='amber')
    sc.frame_set(13)
    mid = [0.5 * (a + b) for a, b in zip(P.linear_color('cyan'), P.linear_color('amber'))]
    V.check('key_uniform: keyed LINEAR, frame 13 is half way from cyan to amber', close(car.object['uPaint'], mid, 2e-3),
            f"{[round(x, 3) for x in car.object['uPaint']]} vs {[round(x, 3) for x in mid]}")
    shots = []
    for f in (1, 13, 25):
        sc.frame_set(f)
        cam = V.three_quarter(car.object, 35, 12, 1.0, name=f'cam{f}')
        sc.camera = cam
        shots.append(render_to(f'_opt_cyber_f{f}.png'))
    # the badge redrawn after the build
    before = np.array(car.parts['badge'].node_tree.nodes[[n.name for n in car.parts['badge'].node_tree.nodes
                                                          if n.type == 'TEX_IMAGE'][0]].image.pixels[:])
    car.set_decal_text('HELLO')
    img = [n for n in car.parts['badge'].node_tree.nodes if n.type == 'TEX_IMAGE'][0].image
    after = np.array(img.pixels[:]).reshape(B.CANVAS_H, B.CANVAS_W, 4)
    want = B.decal_texture_array('HELLO')
    V.check('set_decal_text: the badge image is the new canvas; the SDF program gets it too',
            np.array_equal(after[..., 3] > 0.5, want[..., 3] > 0.5) and not np.array_equal(before.reshape(after.shape),
            after) and np.array_equal(car.program.textures['uDecal'], want), f"text {car.decal_text!r}")
    tgt = V.three(0.834, 1.15, -0.95)
    bpy.context.view_layer.update()
    mw = car.object.matrix_world
    badge_w = mw @ Vector(tgt)
    cam = V.C.camera(tuple(badge_w + Vector((1.1, -0.15, 0.08))), tuple(badge_w), lens=50.0, name='cam_badge')
    sc.camera = cam
    shots.append(render_to('_opt_cyber_badge_hello.png'))
    V.sheet(shots, os.path.join(V.OUT, 'opt_cyber_live.png'), cols=2)
    # lamps
    n_lamps = len(car.lamps)
    car.set_lamps(False)
    V.check('set_lamps(False) hides every lamp', n_lamps == 6 and all(ob.hide_render for ob in car.lamps),
            f'{n_lamps} lamps')
    # a second instance keeps its own livery
    car2 = EX['stylized_cyberpunk_sedan'].make(paint_color='cyan', cache_dir=CACHE, quality='fast', name='opt_cyber2',
                                               lamps=False, lamp_power=2.0, log=None)
    V.check('two instances keep their own uniforms and materials (the GLSL original\'s per-instance uniforms)',
            not close(car.object['uPaint'], car2.object['uPaint']) and car.parts['paint'] != car2.parts['paint']
            and not car2.lamps, f"{[round(x, 3) for x in car.object['uPaint']]} / "
                                f"{[round(x, 3) for x in car2.object['uPaint']]}")
    car3 = EX['stylized_modern_sedan'].make(cache_dir=CACHE, quality='fast', name='opt_power', lamp_power=2.0, log=None)
    heads = [ob.data.energy for ob in car3.lamps if ob.get('sdf_vehicle_lamp') == 'head']
    V.check('lamp_power scales the lamps', heads and all(abs(e - 24.0) < 1e-6 for e in heads), str(heads))
    # the engine's errors
    errs = {
        'paint_color on the sleek car': raises(TypeError, lambda: EX['stylized_sci_fi_sleek_car'].make(
            paint_color=0xff0000, build=False, lamps=False)),
        'camo on a sedan': raises(TypeError, lambda: EX['stylized_modern_sedan'].make(camo='sky', build=False)),
        'decal_text on the modern sedan': raises(TypeError, lambda: EX['stylized_modern_sedan'].make(
            decal_text='X', build=False)),
        'metal_color on the jet': raises(TypeError, lambda: EX['stylized_fighter_jet'].make(metal_color='gold',
                                                                                           build=False)),
        'an unknown camo': raises(ValueError, lambda: EX['stylized_fighter_jet'].make(camo='polka', build=False)),
        'an unknown shading': raises(ValueError, lambda: EX['stylized_modern_sedan'].make(shading='toon',
                                                                                         build=False)),
        'bake() on a vehicle (its shape never changes)': raises(ValueError, lambda: car.bake(1, 2)),
    }
    V.check('make() refuses options the vehicle does not have (the engine ignored them silently) and an unknown '
            'camo (the engine\'s own error)',
            all(v is not None and not str(v).startswith('raised') for v in errs.values()),
            '; '.join(f'{k}: {v}' for k, v in errs.items()))
    cellcar = EX['stylized_modern_sedan'].make(cells=300, build=False, lamps=False, name='opt_cells')
    V.check('cells= replaces the vehicle voxel (cells along the longest side)', abs(cellcar.voxel - 4.8 / 300) < 1e-9,
            f'{cellcar.voxel * 1000:.1f} mm')
    # the engine's full-control path, createSdfObject({...spec, uniforms}), in its {uPaint: {value: colour}} style:
    # through make() (part materials) and through create_sdf_object (the generic baked path)
    ucar = EX['stylized_modern_sedan'].make(uniforms={'uPaint': {'value': 0xff2d95}, 'uRough': 0.3}, build=False,
                                            lamps=False, name='opt_uniforms')
    gen = sdf.create_sdf_object(EX['stylized_modern_sedan'], uniforms={'uPaint': ('color', 0xff2d95), 'uRough': 0.22},
                                build=False, name='opt_uniforms_generic')
    V.check('uniforms= overrides (the engine\'s {uPaint: {value}} style) set the paint, in make() and in '
            'create_sdf_object', close(ucar.object['uPaint'], P.linear_color(0xff2d95)) and abs(ucar.object['uRough']
            - 0.3) < 1e-6 and close(gen.program.values['uPaint'], P.linear_color(0xff2d95))
            and abs(gen.program.values['uRough'] - 0.22) < 1e-6,
            f"make: {[round(x, 3) for x in ucar.object['uPaint']]}; generic: "
            f"{[round(x, 3) for x in gen.program.values['uPaint']]}")
    # the jet's camo keys hold: a scheme is a switch, so silver at 1 -> forest at 25 stays silver until 25
    kjet = EX['stylized_fighter_jet'].make(build=False, lamps=False, name='opt_camo_keys')
    kjet.key_uniform('camo', frame=1, value='silver')
    kjet.key_uniform('camo', frame=25, value='forest')
    sc.frame_set(13)
    held = float(kjet.object['uCamoMode'])
    sc.frame_set(25)
    late = float(kjet.object['uCamoMode'])
    from eidoblend.harness.keying import interpolations
    kinds = interpolations(kjet.object).get('["uCamoMode"][0]', set())
    V.check('camo keys hold (CONSTANT): silver until the forest key, no sky or desert between', held == 0.0
            and late == 3.0 and kinds == {'CONSTANT'}, f'frame 13: {held}, frame 25: {late}, keys {sorted(kinds)}')


# ================================================================================================= sheets ===
if 'sheets' in PARTS_RUN:
    # the modern sedan's paint roughness in a deep blue (reflections read best on a dark paint)
    sc = stage()
    car = EX['stylized_modern_sedan'].make(paint_color=0x1b3a8c, cache_dir=CACHE, name='opt_modern', log=None)
    car.place_on_ground(0.0)
    cam = V.three_quarter(car.object, 35, 14, 0.95)
    shots = []
    for r in (0.0, 0.18, 0.45, 0.8):
        car.set_paint_roughness(r)
        shots.append(render_to(f'_opt_modern_r{int(r * 100):02d}.png'))
    V.sheet(shots, os.path.join(V.OUT, 'opt_paint_roughness.png'), cols=2)
    V.check('paint roughness sweep renders (no rebuild: the coat and base read uRough)', len(shots) == 4)

    sc = stage()
    car = EX['stylized_sci_fi_sleek_car'].make(cache_dir=CACHE, name='opt_sleek', log=None)
    car.place_on_ground(0.0)
    cam = V.three_quarter(car.object, 35, 12, 1.0)
    shots = []
    for preset, r in (('silver', 0.08), ('gold', 0.12), ('copper', 0.10), ('aluminum', 0.35), ('anodized_blue', 0.15),
                      ('anodized_purple', 0.15)):
        car.set_metal_color(preset)
        car.set_paint_roughness(r)
        shots.append(render_to(f'_opt_sleek_{preset}.png'))
    V.sheet(shots, os.path.join(V.OUT, 'opt_metal_presets.png'), cols=3)
    V.check('the six metal presets switched live on one sleek car (aluminum brushed at 0.35)', len(shots) == 6)

    sc = stage()
    jet = EX['stylized_fighter_jet'].make(camo='silver', cache_dir=CACHE, name='opt_jet', log=None)
    jet.place_on_ground(0.0)
    jet.object.location.z += 1.2
    cam = V.three_quarter(jet.object, 40, 24, 0.9)
    shots = []
    for camo in ('silver', 'sky', 'desert', 'forest'):
        jet.set_camo(camo)
        shots.append(render_to(f'_opt_jet_{camo}.png'))
    V.sheet(shots, os.path.join(V.OUT, 'opt_camo.png'), cols=2)
    V.check('camo schemes switched live on one jet (the fbm field per vertex, the scheme per pixel)',
            abs(jet.object['uCamoMode'] - 3.0) < 1e-6 and 'jet_camo_fbm' in jet.object.data.attributes,
            f"camo field range {jet.stats.get('camo_field')}")

    # the baked path beside the part materials, and the grille close up beside the engine's march
    sc = stage()
    parts = EX['stylized_cyberpunk_sedan'].make(cache_dir=CACHE, name='opt_parts', log=None)
    parts.place_on_ground(0.0)
    baked = EX['stylized_cyberpunk_sedan'].make(cache_dir=CACHE, name='opt_baked', shading='baked', lamps=False,
                                                 location=(2.6, 0.0, 0.0), log=None)
    baked.place_on_ground(0.0)
    V.check('shading=baked builds the engine\'s generic path (surface() baked; channels per vertex past the atlas '
            'budget)', baked.stats.get('carrier') in ('vertex', 'atlas') and baked.material is not None,
            f"carrier {baked.stats.get('carrier')}, constants {baked.stats.get('constants')}")
    cam = V.C.camera((1.3, -9.0, 2.4), (1.3, 0.0, 0.6), lens=45.0)
    a = render_to('_opt_parts_vs_baked.png')
    sdf.register_sdf_helper(sc)
    gp = parts.object.matrix_world @ Vector(V.three(0.0, 0.55, 2.26))
    cam = V.C.camera(tuple(gp + Vector((0.35, -1.2, 0.18))), tuple(gp), lens=60.0,
                     name='cam_grille')
    sc.camera = cam
    g = render_to('_opt_grille_eevee.png')
    ref = EM.march(parts, cam, W, H, samples=4)
    gr = V.save_linear_png(os.path.join(V.OUT, '_opt_grille_ref.png'), ref)
    V.sheet([a], os.path.join(V.OUT, 'opt_cyber_baked.png'), cols=1)
    V.sheet([g, gr], os.path.join(V.OUT, 'opt_grille.png'), cols=2)


# ================================================================================================= reopen ===
if 'reopen' in PARTS_RUN:
    sc = stage()
    car = EX['stylized_cyberpunk_sedan'].make(paint_color='magenta', decal_text='ALETH8APO', cache_dir=CACHE,
                                              quality='balanced', name='opt_save', pack_images=True, log=None)
    imgs = [bpy.data.images[n] for n in car.parts['paint']['stripe_images']]
    V.check('pack_images=True packs the stripe livery (and the badge is always packed)',
            all(i.packed_file is not None for i in imgs), ', '.join(i.name for i in imgs))
    car.place_on_ground(0.0)
    car.key_uniform('uPaint', frame=1)
    sc.camera = V.three_quarter(car.object, 30, 10, 0.95)
    a = render_to('_opt_reopen_before.png')
    path = os.path.join(V.OUT, 'opt_reopen.blend')
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    ob = bpy.data.objects['opt_save']
    V.check('the saved .blend keeps the live uniforms, the part materials, the lamps and their drivers',
            close(ob['uPaint'], P.linear_color('magenta'), 1e-4) and len(ob.material_slots) >= 12
            and sum(1 for o in bpy.data.objects if o.parent == ob and o.type == 'LIGHT') == 6,
            f'{len(ob.material_slots)} material slots')
    b = render_to('_opt_reopen_after.png')
    ia, ib = V.read_rgb(a), V.read_rgb(b)
    d = float(np.abs(ia - ib).mean())
    V.check('the reopened file renders as it did before saving', d < 0.01, f'mean |diff| {d:.4f}')
    V.sheet([a, b], os.path.join(V.OUT, 'opt_reopen.png'), cols=2)
    os.remove(path)                                   # a few hundred MB, and regenerable

V.summary()

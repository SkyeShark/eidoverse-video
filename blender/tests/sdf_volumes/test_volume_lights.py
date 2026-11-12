"""Do the SDF fires light the scene? EEVEE's volume emission alone, and light_from_emission's keyed lamps.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/sdf_volumes/test_volume_lights.py [-- cases=bonfire,candle_flame]

Per case (a bonfire on a grey floor at night with a chrome ball and a grey wall beside it; a candle on a table
top; the pyroclastic fireball, a surface SDF), four renders of one frame, to float EXR (measured) and AgX PNG
(looked at):
    base         EEVEE, the fire hidden: the floor under the world alone
    eevee        EEVEE, the fire's volume only: what its emission does to the floor (EEVEE: nothing)
    lamps        EEVEE, the volume + light_from_emission's lamps: the port
    lamps_only   EEVEE, the lamps with the volume hidden
The floor's radiance is read at patches round the fire. PASS lines: EEVEE's volume emission adds (almost) nothing,
the lamps light the floor, and the volume adds nothing over its lamps; the chrome ball's reflection of the fire
(volumes in ray-traced reflections) is printed and seen in the sheet. The surface fireball gets light_from_surface's
lamps (shadow linking lets them out of the solid); then it is baked over four frames with its lamps keyed per frame
(out/lights_explosion_baked.png).
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _vcommon as V  # noqa: E402

import bpy  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.sdf import EXAMPLES  # noqa: E402
from eidoblend.sdf.examples_volumes import fit_volume_range, light_from_emission, light_from_surface  # noqa: E402

A = V.args()
CASES = A.get('cases', 'bonfire,candle_flame,explosion').split(',')
W, H = int(A.get('w', 480)), int(A.get('h', 270))
CACHE = os.path.join(V.OUT, 'cache_lights')

RIGS = {
    # example, time, cells, camera, target, lens, floor patches (world xyz), chrome ball (centre, radius), wall
    'bonfire': dict(t=1.3, cells=140, cam=(0.0, -6.5, 2.0), target=(0.0, 0.0, 0.9), lens=40,
                    patches=[(-1.6, -0.6, 0.0), (1.6, -0.6, 0.0), (-1.0, -1.8, 0.0), (1.1, -1.7, 0.0),
                             (-2.6, 0.4, 0.0), (2.4, 0.6, 0.0)],
                    ball=((1.7, 0.8, 0.45), 0.45), wall=((-2.2, 1.6, 0.0), (1.6, 0.12, 1.4))),
    'candle_flame': dict(t=0.9, cells=200, cam=(0.0, -0.95, 0.42), target=(0.0, 0.0, 0.12), lens=40,
                         patches=[(-0.16, -0.08, 0.0), (0.16, -0.08, 0.0), (-0.1, -0.22, 0.0), (0.12, -0.2, 0.0),
                                  (-0.28, 0.06, 0.0), (0.26, 0.08, 0.0)],
                         ball=((0.2, 0.12, 0.05), 0.05), wall=((-0.25, 0.25, 0.0), (0.18, 0.02, 0.16))),
    # the pyroclastic fireball is a surface SDF (examples_solids.py): its emission is a mesh's, which EEVEE's fast
    # GI gathers only from the screen; light_from_surface's lamps light the scene
    'explosion': dict(t=2.0, solid=True, loc=(0.0, 0.0, 1.5), cam=(0.0, -7.5, 2.2), target=(0.0, 0.0, 1.2), lens=40,
                      patches=[(-2.2, -0.8, 0.0), (2.2, -0.8, 0.0), (-1.6, -1.4, 0.0), (1.7, -1.4, 0.0),
                               (-3.2, 0.6, 0.0), (3.0, 0.8, 0.0)],
                      ball=((2.4, 1.0, 0.55), 0.55), wall=((-3.0, 2.0, 0.0), (2.0, 0.15, 1.8))),
}


def box(name, centre, half, color=(0.5, 0.5, 0.5), metallic=0.0, roughness=0.8):
    me = bpy.data.meshes.new(name)
    hx, hy, hz = half
    v = [(sx * hx, sy * hy, sz * hz) for sx in (-1, 1) for sy in (-1, 1) for sz in (0, 2)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me.from_pydata(v, [], f)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = centre
    m = bpy.data.materials.new(name + '_mat')
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1.0)
    b.inputs['Metallic'].default_value = metallic
    b.inputs['Roughness'].default_value = roughness
    me.materials.append(m)
    return ob


def ball(name, centre, radius):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=centre, segments=48, ring_count=24)
    ob = bpy.context.active_object
    ob.name = name
    bpy.ops.object.shade_smooth()
    m = bpy.data.materials.new(name + '_mat')
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.9, 0.9, 0.9, 1.0)
    b.inputs['Metallic'].default_value = 1.0
    b.inputs['Roughness'].default_value = 0.08
    ob.data.materials.append(m)
    return ob


def patch(img, cam, p, r=3):
    """Mean linear RGB over a (2r+1)^2 window round a world point's pixel (img row 0 at the top)."""
    sc = bpy.context.scene
    co = world_to_camera_view(sc, cam, Vector(p))
    x = int(co.x * W)
    y = int((1.0 - co.y) * H)
    x0, x1 = max(0, x - r), min(W, x + r + 1)
    y0, y1 = max(0, y - r), min(H, y + r + 1)
    return img[y0:y1, x0:x1, :3].reshape(-1, 3).mean(0)


def lum(c):
    return float(np.dot(c, [0.2126, 0.7152, 0.0722]))


for case in CASES:
    R = RIGS[case]
    V.stage(W, H, 16, world=0.004, sun=0.0, floor=True, floor_color=(0.5, 0.5, 0.5), floor_size=30.0)
    sc = bpy.context.scene
    sc.frame_start = sc.frame_end = 1
    floor = bpy.data.objects['floor']
    floor.data.materials[0].node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.9
    cam = V.camera(R['cam'], R['target'], lens=R['lens'])
    cam.data.clip_start = 0.01
    ball('chrome', *R['ball'])
    box('wall', R['wall'][0], R['wall'][1])
    solid = R.get('solid', False)
    if solid:
        vol = EXAMPLES[case].make(cache_dir=CACHE, time=R['t'], name=f'{case}_lit_probe', location=R['loc'])
        rig = light_from_surface(vol)
    else:
        vol = EXAMPLES[case].make(cells=R['cells'], cache_dir=CACHE, time=R['t'], name=f'{case}_lit_probe')
        fit_volume_range(sc, cam, [vol], frames=[1], tile_size='2', samples=96)
        rig = light_from_emission(vol)
    lamps = rig.lights
    tags = (('base', False, False), ('eevee', True, False), ('lamps', True, True), ('lamps_only', False, True))

    def show(volume=True, lights=True):
        vol.object.hide_render = not volume
        for lo in lamps:
            lo.hide_render = not lights

    imgs = {}
    for tag, volume, lights in tags:
        show(volume, lights)
        exr = os.path.join(V.OUT, f'lights_{case}_{tag}.exr')
        imgs[tag] = V.render_linear(exr)
        png = V.save_linear_png(os.path.join(V.OUT, f'lights_{case}_{tag}.png'), imgs[tag][::-1])
        V.label(png, f'{case}: {tag}')
    V.sheet([os.path.join(V.OUT, f'lights_{case}_{t}.png') for t in ('base', 'eevee', 'lamps', 'lamps_only')
             if t in imgs], os.path.join(V.OUT, f'lights_{case}_sheet.png'), cols=2)
    rows = []
    for p in R['patches']:
        rows.append({t: lum(patch(imgs[t], cam, p)) for t in imgs})
    gain_eevee = np.mean([r['eevee'] - r['base'] for r in rows])
    for i, r in enumerate(rows):
        print(f'[lights] {case} patch {i}: ' + ', '.join(f'{k} {v:.4f}' for k, v in r.items()), flush=True)
    gain_lamps = np.mean([r['lamps'] - r['base'] for r in rows])
    gain_only = np.mean([r['lamps_only'] - r['base'] for r in rows])
    if solid:
        print(f'[lights] {case} (a surface SDF): floor gain EEVEE alone {gain_eevee:.4f} (fast GI on), with '
              f'light_from_surface {gain_lamps:.4f}', flush=True)
        V.check(f'{case}: EEVEE alone gathers little of the emissive surface\'s light', gain_eevee < 0.5 * gain_lamps,
                f'floor gain {gain_eevee:.4f} alone, {gain_lamps:.4f} with the lamps')
        V.check(f'{case}: light_from_surface lights the floor (shadow linking lets the light out)', gain_lamps > 1e-3,
                f'floor gain {gain_lamps:.4f}')
        continue
    print(f'[lights] {case}: floor gain over the base: EEVEE volume {gain_eevee:.4f}, EEVEE lamps {gain_lamps:.4f}, '
          f'lamps alone {gain_only:.4f}; lamp power {rig.total_power(None):.3g} W', flush=True)
    V.check(f'{case}: EEVEE volume emission does not light the floor', gain_eevee < 0.1 * gain_lamps,
            f'floor gain {gain_eevee:.4f} from the volume, {gain_lamps:.4f} with its lamps')
    V.check(f'{case}: the lamps light the floor, and the volume adds nothing over them',
            gain_lamps > 1e-3 and abs(gain_lamps - gain_only) < 0.15 * gain_lamps,
            f'with the volume {gain_lamps:.4f}, the lamps alone {gain_only:.4f}')
    bc, br = R['ball']
    rb = [lum(patch(imgs[t], cam, (bc[0], bc[1] - br * 0.9, bc[2]), r=2)) for t in ('base', 'eevee', 'lamps')]
    print(f'[lights] {case}: chrome ball front (base, eevee, lamps) = ' + ', '.join(f'{x:.4f}' for x in rb),
          flush=True)
    V.check(f'{case}: renders written', all(os.path.exists(os.path.join(V.OUT, f'lights_{case}_{t}.png'))
                                            for t in imgs), '')

# the fireball baked over a few frames: light_from_surface keys its lamps per frame from each frame's mesh
if 'explosion' in CASES:
    R = RIGS['explosion']
    V.stage(W, H, 16, world=0.004, sun=0.0, floor=True, floor_color=(0.5, 0.5, 0.5), floor_size=30.0)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, 4
    cam = V.camera(R['cam'], R['target'], lens=R['lens'])
    box('wall', R['wall'][0], R['wall'][1])
    boom = EXAMPLES['explosion'].make(cache_dir=CACHE, location=R['loc'], name='explosion_baked', build=False)
    boom.bake(1, 4, time_offset=1.2, time_scale=12.0, log=None)          # 0.5 s of its life a frame
    rig = light_from_surface(boom, time_offset=1.2, time_scale=12.0)
    e = [float(np.max(rig.frames[f][0]['power'])) for f in range(1, 5)]
    V.check('explosion baked: keyed lamps follow the fireball', min(e) > 0 and (max(e) - min(e)) / max(e) > 0.02,
            'power per frame ' + ', '.join(f'{x:.1f} W' for x in e) + f'; escape {rig.escape:.2f} at the last')
    shots = []
    for f in (1, 4):
        sc.frame_set(f)
        p = os.path.join(V.OUT, f'lights_explosion_baked_f{f}.png')
        V.render(p)
        V.label(p, f'explosion baked, frame {f}: {e[f - 1]:.0f} W')
        shots.append(p)
    V.sheet(shots, os.path.join(V.OUT, 'lights_explosion_baked.png'), cols=2)
V.summary()

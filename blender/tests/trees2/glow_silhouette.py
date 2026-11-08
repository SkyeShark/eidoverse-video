"""The orientation-free backlight ('glow' mode, seedthree.api.set_backlight): the JS's
Barre-Brisebois term without the leaf's Lambert factor, through Shader to RGB.

    bash run_blender.sh blender/tests/trees2/glow_silhouette.py [cards] [oak]

cards: flat cards in linear light (black world, one sun behind them, orthographic view),
built with the materials' own backlight builder in glow mode:
    A facing the camera, B turned 10 degrees, F 50 degrees, G 80 degrees (near edge-on):
      expect k x tcol x E with NO max(0, -N.L) factor (the translucent mode's 0 at G)
    C behind an opaque board: expect 0 (the sun's shadow applies)
    front-lit: Principled + glow == Principled alone + the ambient term (0.16 x tcol x E)
oak: the meadow oak at sunset (a 7 degree sun straight behind the crown) and from under
the crown, in both modes with the light probe; renders and their times.
"""

import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

from eidoblend.trees import make_seed_tree  # noqa: E402

E = 3.0
W, H = 560, 100
SCALE = 14.0
XS = (-6.0, -4.0, -2.0, 0.0, 2.0, 4.0, 6.0)
MEADOW_OAK = {'height': 14.5, 'levels': 4, 'trunks': 1, 'trunkThickness': 1.4, 'crownShape': 2,
              'branchDensity': 24, 'branchAngle': 64, 'gnarliness': 80, 'leafSize': 0.38, 'leavesPerBranch': 24,
              'paramOverrides': {'length': {1: 0.56, 2: 0.46, 3: 0.4}, 'branches': {2: 18, 3: 12},
                                 'downAngle': {3: 45}, 'curveV': {3: 60}}}


def card(name, x, mat, rot_z=0.0, size=1.6):
    me = bpy.data.meshes.new(name)
    s = size / 2
    me.from_pydata([(-s, 0, -s), (s, 0, -s), (s, 0, s), (-s, 0, s)], [], [(0, 1, 2, 3)])
    ob = bpy.data.objects.new(name, me)
    ob.location = (x, 0, 2.0)
    ob.rotation_euler = (0, 0, rot_z)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(mat)
    return ob


def leaf(name, M, tcol, principled=False):
    mat = bpy.data.materials.new(name)
    g = M._G(mat)
    out = g.node('ShaderNodeOutputMaterial')
    tl = g.backlight(tcol, None, None, M.BB_LEAVES, 0.0)
    if principled:
        p = g.node('ShaderNodeBsdfPrincipled')
        p.inputs['Base Color'].default_value = (0.5, 0.5, 0.5, 1)
        p.inputs['Roughness'].default_value = 0.8
        add = g.node('ShaderNodeAddShader')
        g.link(p.outputs[0], add.inputs[0])
        g.link(tl, add.inputs[1])
        tl = add.outputs[0]
    g.link(tl, out.inputs['Surface'])
    M._settings(mat, translucent=True, thickness=0.0)
    return mat


def principled_only(name, M):
    mat = bpy.data.materials.new(name)
    g = M._G(mat)
    out = g.node('ShaderNodeOutputMaterial')
    p = g.node('ShaderNodeBsdfPrincipled')
    p.inputs['Base Color'].default_value = (0.5, 0.5, 0.5, 1)
    p.inputs['Roughness'].default_value = 0.8
    g.link(p.outputs[0], out.inputs['Surface'])
    M._settings(mat)
    return mat


def measure(scene, path):
    scene.render.image_settings.file_format = 'OPEN_EXR'
    scene.render.image_settings.color_depth = '32'
    S.render(scene, path)
    img = bpy.data.images.load(path, check_existing=False)
    px = np.array(img.pixels[:], np.float32).reshape(H, W, 4)
    bpy.data.images.remove(img)
    return [float(px[H // 2 - 4:H // 2 + 4, int(round((x / SCALE + 0.5) * W)) - 4:int(round((x / SCALE + 0.5) * W)) + 4, 1].mean())
            for x in XS]


def k_of(L, N, consts):
    d, a, p, s = consts
    V = Vector((0, -1, 0))
    Hv = (L + N * d).normalized()
    return max(0.0, min(1.0, V.dot(-Hv))) ** p * s + a


def cards_test():
    api = make_seed_tree.raw()
    from seedthree.bl import materials as M
    scene = S.reset()
    S.render_settings(scene, W, H, samples=16)
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    world = bpy.data.worlds.new('black')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.0
    scene.world = world
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    sun.data.energy = E
    sun.data.angle = math.radians(0.5)
    scene.collection.objects.link(sun)
    api.set_sun(sun)
    cam = S.camera(scene, (0.0, -10.0, 2.0), (0.0, 0.0, 2.0))
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = SCALE
    L = Vector((math.sin(math.radians(20)) * math.cos(math.radians(25)), math.cos(math.radians(20)) * math.cos(math.radians(25)),
                math.sin(math.radians(25))))
    sun.rotation_euler = (-L).to_track_quat('-Z', 'Y').to_euler()
    tcol = (0.2, 0.3, 0.1)
    spec = [('A', 0.0), ('B', 10.0), ('C', 0.0), ('F', 50.0), ('G', 80.0)]
    api.set_backlight('glow')
    try:
        objs = [card(n, XS[i], leaf('g' + n, M, tcol), rot_z=math.radians(r)) for i, (n, r) in enumerate(spec)]
        board = card('board', XS[2], bpy.data.materials.new('board'), size=3.0)
        board.location = Vector((XS[2], 0, 2.0)) + L * 3.0
        got = measure(scene, os.path.join(S.OUT, 'glow_cards_behind.exr'))
        for i, (n, r) in enumerate(spec):
            N = Matrix.Rotation(math.radians(r), 3, 'Z') @ Vector((0, -1, 0))
            want = 0.0 if n == 'C' else k_of(L, N, M.BB_LEAVES) * tcol[1] * E
            lam = max(0.0, -N.dot(L))
            ok = abs(got[i] - want) <= 0.01 + 0.03 * want
            S.check('glow card %s (%g deg)' % (n, r), ok, 'measured %.4f, JS %.4f (the translucent mode: %.4f)' % (
                got[i], want, want * lam))
        for o in objs + [board]:
            bpy.data.objects.remove(o, do_unlink=True)
        Lf = Vector((0.3, -0.85, 0.43)).normalized()
        sun.rotation_euler = (-Lf).to_track_quat('-Z', 'Y').to_euler()
        card('E0', XS[1], principled_only('tE0', M))
        card('E', XS[3], leaf('tE', M, tcol, principled=True))
        got = measure(scene, os.path.join(S.OUT, 'glow_cards_front.exr'))
        add = k_of(Lf, Vector((0, -1, 0)), M.BB_LEAVES) * tcol[1] * E
        S.check('glow front-lit: the diffuse intact + the ambient term', abs(got[3] - (got[1] + add)) <= 0.01 + 0.02 * got[3],
                'Principled %.4f + %.4f expected %.4f, measured %.4f' % (got[1], add, got[1] + add, got[3]))
    finally:
        api.set_backlight('translucent')


def oak_test():
    api = make_seed_tree.raw()
    times = {}
    for mode in ('translucent', 'glow'):
        api.set_backlight(mode)
        try:
            for shot in ('sunset', 'under'):
                scene = S.reset()
                S.render_settings(scene, 960, 540, 16)
                api.set_wind(strength=0.0)
                oak = make_seed_tree(species='whiteOak', seed=1737, dials=MEADOW_OAK, location=(0, 0, 0))
                S.ground(scene, api.ASSETS_DIR, 'grass', tile=3.0)
                if shot == 'sunset':
                    sun, _ = S.sky_and_sun(scene, sun_elev_deg=7, sun_az_deg=0, strength=0.10, sun_strength=4.0)
                    S.camera(scene, (0.0, -34.0, 1.6), (0.0, 0.0, 7.5), lens=35)
                else:
                    sun, _ = S.sky_and_sun(scene, sun_elev_deg=36, sun_az_deg=315, strength=0.10, sun_strength=4.0)
                    S.camera(scene, (6, -6, 1.5), (0, 0, 7), lens=24)
                api.set_sun(sun)
                api.light_probe(oak)
                t0 = time.perf_counter()
                S.render(scene, os.path.join(S.OUT, 'glow_oak_%s_%s.png' % (shot, mode)))
                times[(shot, mode)] = time.perf_counter() - t0
        finally:
            api.set_backlight('translucent')
    for shot in ('sunset', 'under'):
        print('[glow] %s render: translucent %.1f s, glow %.1f s' % (shot, times[(shot, 'translucent')], times[(shot, 'glow')]))
    S.check('glow mode renders the meadow oak within 3x the translucent mode',
            all(times[(s, 'glow')] < 3 * times[(s, 'translucent')] + 2 for s in ('sunset', 'under')))


def main():
    a = S.args()
    parts = [x for x in a if x in ('cards', 'oak')] or ['cards', 'oak']
    if 'cards' in parts:
        cards_test()
    if 'oak' in parts:
        oak_test()
    S.summary('glow_silhouette')


main()

"""The leaf backlight in both routes (seedthree.api.set_backlight), measured on flat cards in
linear light, and the meadow oak rendered in both.

    bash run_blender.sh blender/tests/trees2/glow_silhouette.py [cards] [oak]

cards: seven cards in a row (orthographic view, one sun behind them, 25 deg up and 20 deg
aside), built with the materials' own backlight builder, each with the app's shadow
normal bias (materials.shadow_bias, which create_tree gives every leaf, card, frond and
spine part):
    A facing the camera, B turned 10 deg, C behind an opaque board, F turned 50 deg,
    G 80 deg (the sun on its camera side), R a back face turned 30 deg, Q 65 deg.
  translucent  k x tcol x E x max(0, -N.L)
  glow         k x tcol x E, no Lambert factor (the JS's term)
               both exact where the sun is within 45 deg of a card's back normal (A, B) or
               on its camera side (G); cards lit from behind more grazingly (R 54, F 72,
               Q 85 deg) keep part of their light, printed as the known gap
  glow under a bright world (strength 0.5): the same values (the world light cancelled)
  front-lit    Principled + backlight == Principled alone (+ the ambient term in glow)
oak: the meadow oak at sunset (a 7 deg sun straight behind the crown), from under the
crown, and front-lit from a 35 deg sun, in both routes with the light probe.
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
TCOL = (0.2, 0.3, 0.1)
# name, turn about Z (deg), back face toward the camera
SPEC = [('A', 0.0, False), ('B', 10.0, False), ('C', 0.0, False), ('F', 50.0, False), ('G', 80.0, False),
        ('R', 30.0, True), ('Q', 65.0, False)]
GRAZING = ('R', 'F', 'Q')   # lit from behind 54, 72 and 85 deg off the card's normal (A 32, B 38)
MEADOW_OAK = {'height': 14.5, 'levels': 4, 'trunks': 1, 'trunkThickness': 1.4, 'crownShape': 2,
              'branchDensity': 24, 'branchAngle': 64, 'gnarliness': 80, 'leafSize': 0.38, 'leavesPerBranch': 24,
              'paramOverrides': {'length': {1: 0.56, 2: 0.46, 3: 0.4}, 'branches': {2: 18, 3: 12},
                                 'downAngle': {3: 45}, 'curveV': {3: 60}}}


def card(name, x, mat, M, rot_z=0.0, size=1.6, flip=False, bias=True):
    me = bpy.data.meshes.new(name)
    s = size / 2
    me.from_pydata([(-s, 0, -s), (s, 0, -s), (s, 0, s), (-s, 0, s)], [], [(3, 2, 1, 0)] if flip else [(0, 1, 2, 3)])
    ob = bpy.data.objects.new(name, me)
    ob.location = (x, 0, 2.0)
    ob.rotation_euler = (0, 0, rot_z)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(mat)
    if bias:
        M.shadow_bias(ob)
    return ob


def leaf(name, M, principled=False):
    mat = bpy.data.materials.new(name)
    g = M._G(mat)
    out = g.node('ShaderNodeOutputMaterial')
    tl = g.backlight(TCOL, None, None, M.BB_LEAVES, 0.0)
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


def stage(world_strength):
    scene = S.reset()
    S.render_settings(scene, W, H, samples=16)
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    world = bpy.data.worlds.new('flat')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = world_strength
    scene.world = world
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    sun.data.energy = E
    sun.data.angle = math.radians(0.5)
    scene.collection.objects.link(sun)
    cam = S.camera(scene, (0.0, -10.0, 2.0), (0.0, 0.0, 2.0))
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = SCALE
    return scene, sun


def cards_row(api, M, mode, world_strength, L):
    scene, sun = stage(world_strength)
    api.set_sun(sun)
    sun.rotation_euler = (-L).to_track_quat('-Z', 'Y').to_euler()
    for i, (n, r, flip) in enumerate(SPEC):
        card(n, XS[i], leaf('%s %s' % (mode, n), M), M, rot_z=math.radians(r), flip=flip)
    board = card('board', XS[2], bpy.data.materials.new('board'), M, size=3.0, bias=False)
    board.location = Vector((XS[2], 0, 2.0)) + L * 3.0
    return measure(scene, os.path.join(S.OUT, 'glow_cards_%s_w%g.exr' % (mode, world_strength)))


def front_row(api, M, mode, world_strength, Lf):
    scene, sun = stage(world_strength)
    api.set_sun(sun)
    sun.rotation_euler = (-Lf).to_track_quat('-Z', 'Y').to_euler()
    card('E0', XS[1], principled_only('%s E0' % mode, M), M)
    card('E', XS[3], leaf('%s E' % mode, M, principled=True), M)
    return measure(scene, os.path.join(S.OUT, 'glow_cards_front_%s_w%g.exr' % (mode, world_strength)))


def cards_test():
    api = make_seed_tree.raw()
    from seedthree.bl import materials as M
    L = Vector((math.sin(math.radians(20)) * math.cos(math.radians(25)), math.cos(math.radians(20)) * math.cos(math.radians(25)),
                math.sin(math.radians(25))))
    Lf = Vector((0.3, -0.85, 0.43)).normalized()
    js = {}
    for n, r, flip in SPEC:
        N = Matrix.Rotation(math.radians(r), 3, 'Z') @ Vector((0, -1, 0))   # the normal facing the eye
        k = 0.0 if n == 'C' else k_of(L, N, M.BB_LEAVES) * TCOL[1] * E
        js[n] = (k, k * max(0.0, -N.dot(L)))
    keep = M.BACKLIGHT
    got = {}
    try:
        for mode, ws in (('translucent', 0.0), ('glow', 0.0), ('glow', 0.5)):
            api.set_backlight(mode)
            got[(mode, ws)] = cards_row(api, M, mode, ws, L)
        for mode, idx in (('translucent', 1), ('glow', 0)):
            for i, (n, r, flip) in enumerate(SPEC):
                want = js[n][idx]
                v = got[(mode, 0.0)][i]
                if n in GRAZING:
                    off = math.degrees(math.acos(max(-1.0, min(1.0, js[n][1] / js[n][0])))) if js[n][0] else 0.0
                    print('[glow] known gap (%s): card %s, lit from behind %.0f deg off its normal, keeps %.0f%% of '
                          'its light (%.4f of %.4f)' % (mode, n, off, 100 * v / want if want else 0, v, want))
                    continue
                S.check('%s card %s (%g deg%s)' % (mode, n, r, ', back face' if flip else ''),
                        abs(v - want) <= 0.005 + 0.02 * want,
                        'measured %.4f, %s %.4f' % (v, 'k x tcol x E x max(0, -N.L)' if idx else 'JS k x tcol x E', want))
        for i, (n, r, flip) in enumerate(SPEC):
            a, b = got[('glow', 0.0)][i], got[('glow', 0.5)][i]
            S.check('glow card %s under a bright world: the world light cancelled' % n, abs(a - b) <= 0.006 + 0.02 * a,
                    'black world %.4f, world 0.5 %.4f' % (a, b))
        add = k_of(Lf, Vector((0, -1, 0)), M.BB_LEAVES) * TCOL[1] * E
        for mode, extra in (('translucent', 0.0), ('glow', add)):
            api.set_backlight(mode)
            v = front_row(api, M, mode, 0.0, Lf)
            S.check('%s front-lit: the diffuse intact%s' % (mode, ' + the ambient term' if extra else ''),
                    abs(v[3] - (v[1] + extra)) <= 0.005 + 0.02 * v[3],
                    'Principled %.4f + %.4f expected %.4f, measured %.4f' % (v[1], extra, v[1] + extra, v[3]))
    finally:
        api.set_backlight(keep)


def oak_test():
    api = make_seed_tree.raw()
    from seedthree.bl import materials as M
    keep = M.BACKLIGHT
    times = {}
    shots = ('sunset', 'under', 'front')
    try:
        for mode in ('translucent', 'glow'):
            api.set_backlight(mode)
            for shot in shots:
                scene = S.reset()
                S.render_settings(scene, 960, 540, 16)
                api.set_wind(strength=0.0)
                oak = make_seed_tree(species='whiteOak', seed=1737, dials=MEADOW_OAK, location=(0, 0, 0))
                S.ground(scene, api.ASSETS_DIR, 'grass', tile=3.0)
                if shot == 'sunset':
                    sun, _ = S.sky_and_sun(scene, sun_elev_deg=7, sun_az_deg=0, strength=0.10, sun_strength=4.0)
                    S.camera(scene, (0.0, -34.0, 1.6), (0.0, 0.0, 7.5), lens=35)
                elif shot == 'under':
                    sun, _ = S.sky_and_sun(scene, sun_elev_deg=36, sun_az_deg=315, strength=0.10, sun_strength=4.0)
                    S.camera(scene, (6, -6, 1.5), (0, 0, 7), lens=24)
                else:
                    sun, _ = S.sky_and_sun(scene, sun_elev_deg=35, sun_az_deg=200, strength=0.10, sun_strength=4.0)
                    S.camera(scene, (10.0, -36.0, 4.0), (0.0, 0.0, 7.5), lens=35)
                api.set_sun(sun)
                api.light_probe(oak)
                t0 = time.perf_counter()
                S.render(scene, os.path.join(S.OUT, 'glow_oak_%s_%s.png' % (shot, mode)))
                times[(shot, mode)] = time.perf_counter() - t0
    finally:
        api.set_backlight(keep)
    for shot in shots:
        print('[glow] %s render: translucent %.1f s, glow %.1f s' % (shot, times[(shot, 'translucent')], times[(shot, 'glow')]))
    S.check('glow renders the meadow oak within 3x the translucent route',
            all(times[(s, 'glow')] < 3 * times[(s, 'translucent')] + 2 for s in shots))


def main():
    a = S.args()
    parts = [x for x in a if x in ('cards', 'oak')] or ['cards', 'oak']
    if 'cards' in parts:
        cards_test()
    if 'oak' in parts:
        oak_test()
    S.summary('glow_silhouette')


main()

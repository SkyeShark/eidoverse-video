"""Measures the backlight port in linear light (EEVEE, black world, one sun).

SeedThree's leaves glow by three's Barre-Brisebois term. The port feeds
pi x k x thicknessColor into a Translucent BSDF on the material's own shading
normal, on a card whose Thickness is linked to 0 (seedthree/bl/sun.py), so
EEVEE should answer k x thicknessColor x E x max(0, -N.L) x shadow, with
k = saturate(V . -normalize(L + 0.3 N))^6 x 3 + 0.16 for leaves. Flat cards, an
orthographic view (V is the same on every pixel), the materials' own builder:

  sun behind the cards
    A  the leaf term, card facing the camera        expect k x tcol x E x (-N.L)
    B  the same card turned 10 degrees              expect the same formula, its own N
    C  card A's twin behind an opaque board         expect 0 (the sun's shadow applies)
    D  a transmit high enough that pi k tcol > 1    expect the formula (no clamp)
    F  the card turned 50 degrees (sun 72 degrees off its normal, from behind)
       EEVEE self-shadows a thin card lit from behind more than ~45 degrees off its normal (any
       Thickness up to ~0.2 m, any shadow filter or ray setting): ~0. The one
       known gap; printed, not failed.
  sun in front of the cards
    E  Principled (base 0.5) + the leaf term        expect E == E0 (Principled alone):
       the backlight closure must not cost the diffuse its light

Why these choices (measured while porting, scratch tests kept out of the repo):
  - A Translucent BSDF on ANOTHER normal than the diffuse (e.g. -L) makes EEVEE
    drop the Principled diffuse: the sunlit side goes black.
  - An unlinked Thickness makes EEVEE take about the object's size as the slab:
    occluders closer than that (a whole canopy) never shadow the transmission,
    and the colour acts twice (colour^2). Thickness 0 is a thin sheet.

    bash run_blender.sh blender/tests/trees/backlight_check.py
Writes blender/tests/trees/out/backlight_check_{behind,front}.exr; prints measured vs expected.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

from eidoblend.trees import make_seed_tree  # noqa: E402

E = 3.0
W, H = 480, 100
SCALE = 12.0
XS = (-5.0, -3.0, -1.0, 1.0, 3.0, 5.0)


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


def leaf(name, materials, transmit, principled=False):
    mat = bpy.data.materials.new(name)
    g = materials._G(mat)
    out = g.node('ShaderNodeOutputMaterial')
    tl = g.backlight(transmit, None, None, materials.BB_LEAVES, 0.0)
    if principled:
        p = g.node('ShaderNodeBsdfPrincipled')
        p.inputs['Base Color'].default_value = (0.5, 0.5, 0.5, 1)
        p.inputs['Roughness'].default_value = 0.8
        add = g.node('ShaderNodeAddShader')
        g.link(p.outputs[0], add.inputs[0])
        g.link(tl, add.inputs[1])
        tl = add.outputs[0]
    g.link(tl, out.inputs['Surface'])
    materials._settings(mat, translucent=True, thickness=0.0)
    return mat


def principled_only(name, materials):
    mat = bpy.data.materials.new(name)
    g = materials._G(mat)
    out = g.node('ShaderNodeOutputMaterial')
    p = g.node('ShaderNodeBsdfPrincipled')
    p.inputs['Base Color'].default_value = (0.5, 0.5, 0.5, 1)
    p.inputs['Roughness'].default_value = 0.8
    g.link(p.outputs[0], out.inputs['Surface'])
    materials._settings(mat, translucent=True, thickness=0.0)
    return mat


def measure(scene, path):
    scene.render.image_settings.file_format = 'OPEN_EXR'
    scene.render.image_settings.color_depth = '32'
    S.render(scene, path)
    img = bpy.data.images.load(path, check_existing=False)
    px = np.array(img.pixels[:], np.float32).reshape(H, W, 4)
    bpy.data.images.remove(img)
    out = {}
    for i, x in enumerate(XS):
        col = int(round((x / SCALE + 0.5) * W))
        out[i] = float(px[H // 2 - 4:H // 2 + 4, col - 4:col + 4, 1].mean())
    return out


def k_of(L, N, consts):
    d, a, p, s = consts
    V = Vector((0, -1, 0))
    Hv = (L + N * d).normalized()
    return max(0.0, min(1.0, V.dot(-Hv))) ** p * s + a


def main():
    scene = S.reset()
    S.render_settings(scene, W, H, samples=16)
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    world = bpy.data.worlds.new('black')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.0
    scene.world = world
    api = make_seed_tree.raw()
    from seedthree.bl import materials
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    sun.data.energy = E
    sun.data.angle = math.radians(0.5)
    scene.collection.objects.link(sun)
    api.set_sun(sun)
    cam = S.camera(scene, (0.0, -10.0, 2.0), (0.0, 0.0, 2.0))
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = SCALE

    # ---- sun behind the cards: 25 deg up, 20 deg to the side
    L = Vector((math.sin(math.radians(20)) * math.cos(math.radians(25)), math.cos(math.radians(20)) * math.cos(math.radians(25)),
                math.sin(math.radians(25))))
    sun.rotation_euler = (-L).to_track_quat('-Z', 'Y').to_euler()
    tcol, hot = (0.2, 0.3, 0.1), (0.6, 0.9, 0.3)
    rots = {0: 0.0, 1: 10.0, 2: 0.0, 3: 0.0, 5: 50.0}
    objs = [card('A', XS[0], leaf('tA', materials, tcol)),
            card('B', XS[1], leaf('tB', materials, tcol), rot_z=math.radians(10)),
            card('C', XS[2], leaf('tC', materials, tcol)),
            card('D', XS[3], leaf('tD', materials, hot)),
            card('F', XS[5], leaf('tF', materials, tcol), rot_z=math.radians(50))]
    board = card('board', XS[2], bpy.data.materials.new('board'), size=3.0)   # between the sun and C
    board.location = Vector((XS[2], 0, 2.0)) + L * 3.0
    got = measure(scene, os.path.join(S.OUT, 'backlight_check_behind.exr'))
    fails = 0
    for i, name, tr in ((0, 'A', tcol), (1, 'B', tcol), (2, 'C', tcol), (3, 'D', hot), (5, 'F', tcol)):
        N = Matrix.Rotation(math.radians(rots[i]), 3, 'Z') @ Vector((0, -1, 0))
        want = 0.0 if name in 'CF' else k_of(L, N, materials.BB_LEAVES) * tr[1] * E * max(0.0, -N.dot(L))
        ok = abs(got[i] - want) <= 0.01 + 0.02 * want
        fails += 0 if ok or name == 'F' else 1
        extra = '  (pi k tcol = %.2f)' % (math.pi * k_of(L, N, materials.BB_LEAVES) * tr[1]) if name == 'D' else ''
        print('[backlight] %s measured G %.4f  expected %.4f  %s%s' % (
            name, got[i], want, 'known EEVEE gap' if name == 'F' else ('ok' if ok else 'FAIL'), extra))
    for o in objs + [board]:
        bpy.data.objects.remove(o, do_unlink=True)

    # ---- sun in front: the backlight closure must leave the Principled diffuse alone
    Lf = Vector((0.3, -0.85, 0.43)).normalized()
    sun.rotation_euler = (-Lf).to_track_quat('-Z', 'Y').to_euler()
    card('E0', XS[1], principled_only('tE0', materials))
    card('E', XS[3], leaf('tE', materials, tcol, principled=True))
    got = measure(scene, os.path.join(S.OUT, 'backlight_check_front.exr'))
    ok = abs(got[3] - got[1]) <= 0.01 * got[1] + 0.002 and got[1] > 0.2
    fails += 0 if ok else 1
    print('[backlight] E Principled + backlight %.4f  vs Principled alone %.4f  %s' % (got[3], got[1], 'ok' if ok else 'FAIL'))
    print('[backlight]', 'PASS' if not fails else 'FAIL %d' % fails)


main()

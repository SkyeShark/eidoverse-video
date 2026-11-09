"""The demo's haze pass at silhouettes: no haze bleeds onto near geometry, no dark rim.

    bash run_blender.sh blender/tests/trees2/haze_edge_check.py

A near green board pierced by small holes stands 10 m in front of the camera; far
behind it (300 m, past the app's 245-278 m haze wall) a grey wall rises to a straight
rim against the sky. The haze is pure red so any bleed shows. Checks, against the same
frame with the fog off:
  - the board keeps its own colour right up to its holes (each pixel takes its own
    position's factor; the app fogs per fragment), while the far wall seen through the
    holes is fully hazed;
  - the wall's rim against the sky has no dark line (its edge pixels hold no position
    but blend the wall in: they take their neighbours' factor);
  - with the haze off, the app's classic range fog (smoothstep(95, 300, depth)) hazes the
    wall and leaves the board (10 m) untouched.
Writes out/verify/haze_edge_{fog,nofog,range}.png.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402

from eidoblend.trees import raw  # noqa: E402

W, H = 320, 180
RED = (1.0, 0.0, 0.0)
FOG = (0.0, 0.0, 1.0)


def plane(name, verts, faces, color):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Roughness'].default_value = 1.0
    p.inputs['Specular IOR Level'].default_value = 0.0
    me.materials.append(m)
    return ob


def board():
    """A 6 x 2.5 m board at y = 10 m, cells of 0.1 m, every 6th cell in both directions a hole."""
    nx, nz, c = 60, 25, 0.1
    verts, faces, idx = [], [], {}

    def v(i, k):
        if (i, k) not in idx:
            idx[(i, k)] = len(verts)
            verts.append((-3.0 + i * c, 10.0, 0.5 + k * c))
        return idx[(i, k)]
    for i in range(nx):
        for k in range(nz):
            if i % 6 == 3 and k % 6 == 3:
                continue
            faces.append((v(i, k), v(i + 1, k), v(i + 1, k + 1), v(i, k + 1)))
    return plane('board', verts, faces, (0.05, 0.5, 0.05))


def read(path):
    img = bpy.data.images.load(path)
    px = np.array(img.pixels[:], np.float32).reshape(img.size[1], img.size[0], 4)[::-1, :, :3]
    bpy.data.images.remove(img)
    return px


def main():
    raw()
    from seedthree.scene import atmosphere as A
    scene = S.reset()
    S.render_settings(scene, W, H, 16)
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    w = bpy.data.worlds.new('haze test sky')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.6, 0.7, 0.9, 1)
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0
    scene.world = w
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    sun.data.energy = 3.0
    sun.rotation_euler = (0.6, 0.2, 0.3)
    scene.collection.objects.link(sun)
    board()
    plane('far wall', [(-400, 300, -50), (400, 300, -50), (400, 300, 22), (-400, 300, 22)], [(0, 1, 2, 3)],
          (0.3, 0.3, 0.3))
    S.camera(scene, (0.0, 0.0, 1.75), (0.0, 10.0, 1.75), lens=50.0)
    A.build_haze(scene, RED, 1.0, 110.0, fog_color=FOG, fog_near=95.0, fog_far=300.0)
    od = os.path.join(S.OUT, 'verify')
    os.makedirs(od, exist_ok=True)
    paths = {}
    for name, haze, on in (('fog', True, True), ('nofog', True, False), ('range', False, True)):
        A.set_haze_enabled(scene, haze)
        A.set_fog_on(scene, on)
        paths[name] = os.path.join(od, 'haze_edge_%s.png' % name)
        S.render(scene, paths[name])
    fog, clear, rng = (read(paths[k]) for k in ('fog', 'nofog', 'range'))
    green = (clear[..., 1] > clear[..., 0] * 1.6) & (clear[..., 1] > clear[..., 2] * 1.6)
    # board pixels at least 3 px inside the board (their 7 x 7 neighbourhood is all board)
    from numpy.lib.stride_tricks import sliding_window_view
    pad = np.pad(green, 3, constant_values=False)
    inner = sliding_window_view(pad, (7, 7)).all(axis=(-1, -2))
    near_hole = green & ~inner & sliding_window_view(np.pad(green, 1), (3, 3)).all(axis=(-1, -2))
    holes = ~green & sliding_window_view(np.pad(green, 4, constant_values=True), (9, 9)).mean(axis=(-1, -2)).__gt__(0.6)
    d_inner = np.abs(fog[inner] - clear[inner]).max() if inner.any() else 1
    d_edge = np.abs(fog[near_hole] - clear[near_hole])[:, 0].max() if near_hole.any() else 1
    S.check('board pixels keep their colour (no haze on near geometry)', d_inner < 0.02,
            'max change %.4f over %d pixels' % (d_inner, int(inner.sum())))
    S.check('board pixels next to the holes keep their colour (no bleed into the leaf gaps)', d_edge < 0.06,
            'max red gain %.4f over %d pixels next to holes' % (d_edge, int(near_hole.sum())))
    if holes.any():
        red_share = fog[holes][:, 0] / np.maximum(fog[holes].sum(-1), 1e-6)
        S.check('the far wall through the holes is hazed', float(np.median(red_share)) > 0.8,
                'median red share %.3f over %d hole pixels' % (float(np.median(red_share)), int(holes.sum())))
    # the rim: in the margin columns beside the board, where the far wall meets the sky
    lum = fog @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    redwall = (fog[..., 0] > 0.6) & (fog[..., 1] < 0.2)
    sky = (np.abs(fog - clear) < 0.02).all(-1) & (clear[..., 2] > 0.5) & ~green
    cols = [x for x in range(W) if not green[:, x].any() and redwall[:, x].any()]
    rim = []
    for x in cols:
        top = int(np.argmax(redwall[:, x]))
        if top > 1:
            rim.append(min(lum[top - 1, x], lum[top, x]))
    if rim:
        ref = min(float(np.median(lum[redwall])), float(np.median(lum[sky])) if sky.any() else 1.0)
        S.check('the far rim against the sky has no dark line', min(rim) > 0.85 * ref,
                'darkest rim pixel %.3f vs %.3f (the darker of haze and sky), %d columns' % (min(rim), ref, len(rim)))
    else:
        S.check('the far rim is in frame', False)
    blue = rng[..., 2] / np.maximum(rng.sum(-1), 1e-6)
    S.check('range fog: the far wall takes the fog colour', redwall.any() and float(np.median(blue[redwall])) > 0.8,
            'median blue share on the wall %.3f' % (float(np.median(blue[redwall])) if redwall.any() else -1))
    d_rng = np.abs(rng[inner] - clear[inner]).max() if inner.any() else 1
    S.check('range fog: the board at 10 m is untouched', d_rng < 0.02, 'max change %.4f' % d_rng)
    S.summary('haze_edge_check')


main()

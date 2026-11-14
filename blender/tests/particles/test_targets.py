"""Every kind of morph target the infrastructure takes, checked numerically (renders nothing):

  meshes (surface, vertices, volume, edges; modifiers evaluated), material colours (a Base Color value, an image texture
  at the right UVs, a byte sRGB texture linearised, emission, alpha cut), curves (with and without bevel), a text
  object, a metaball, Geometry Nodes output (instances and a point cloud), a collection instance, a particle-system
  instancer, a whole collection, my robot body (VRM) live in its pose on two frames and bound in the morph graph, the
  engine's vertex from_mesh live, files (.obj .fbx .glb .gltf .ply .stl written here from a test model, a Poly Haven
  model from the shared library, the repo's animated crow by 'model:' name playing its clip live while hidden, a
  'vrm:' spec), images (alpha, luma, dark, any, edges; colours), a silhouette, point clouds (a POINTCLOUD
  object, .ply, .xyz, .npy), volumes (a Geometry Nodes volume, a .vdb of the fire's cache), every shape, text / ASCII /
  banner specs, the resolver's dict and tuple specs, resampling, centroid matching, pairing, stagger.

    bash run_blender.sh blender/tests/particles/test_targets.py
Exit 0 when every check passes."""

import glob
import math
import os
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from eidoblend.fx import particle_morph as PM  # noqa: E402
from eidoblend.fx import particle_targets as PT  # noqa: E402

FILES = os.path.join(S.OUT, 'files')
os.makedirs(FILES, exist_ok=True)
N = 6000


def mat(name, rgb=(0.8, 0.8, 0.8), emission=None, image=None, alpha_from_image=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgb, 1.0)
    if emission is not None:
        b.inputs['Emission Color'].default_value = (*emission[0], 1.0)
        b.inputs['Emission Strength'].default_value = emission[1]
    if image is not None:
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = image
        nt.links.new(tex.outputs['Color'], b.inputs['Base Color'])
        if alpha_from_image:
            nt.links.new(tex.outputs['Alpha'], b.inputs['Alpha'])
    return m


def obj_with(op, name, material=None, **kw):
    op(**kw)
    o = bpy.context.object
    o.name = name
    if material is not None:
        o.data.materials.append(material)
    return o


def eval_cloud(m, frame=None):
    sc = bpy.context.scene
    if frame is not None:
        sc.frame_set(frame)
    m.uniforms.points_only.value = True
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = m.object.evaluated_get(dg)
    me = ev.to_mesh()
    try:
        P = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', P)
        a = me.attributes.get('p_color')
        C = None
        if a is not None:
            C = np.empty(len(a.data) * 4, np.float32)
            a.data.foreach_get('color', C)
            C = C.reshape(-1, 4)[:, :3]
    finally:
        ev.to_mesh_clear()
    m.uniforms.points_only.value = False
    return P.reshape(-1, 3), C


def finite(t):
    return np.isfinite(np.asarray(t.points)).all()


# ---------------------------------------------------------------------------------- procedural material colours ---

def _proc_mat(name, build):
    """A material whose Base Color is the socket build(node_tree) returns."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.links.new(build(nt), nt.nodes['Principled BSDF'].inputs['Base Color'])
    return m


C0, C1 = np.array([0.1, 0.3, 0.8]), np.array([0.9, 0.5, 0.1])


def _ramp(nt, fac):
    r = nt.nodes.new('ShaderNodeValToRGB')
    r.color_ramp.elements[0].color = (*C0, 1.0)
    r.color_ramp.elements[1].color = (*C1, 1.0)
    nt.links.new(fac, r.inputs['Fac'])
    return r.outputs['Color']


def _gradient_obj(nt, vector=None):
    """Gradient (linear) on the Object coordinates (or `vector`) -> the blue-orange ramp."""
    g = nt.nodes.new('ShaderNodeTexGradient')
    if vector is None:
        vector = nt.nodes.new('ShaderNodeTexCoord').outputs['Object']
    nt.links.new(vector, g.inputs['Vector'])
    return _ramp(nt, g.outputs['Fac'])


def _ramp_ref(fac):
    f = np.clip(fac, 0.0, 1.0)[:, None]
    return C0 + (C1 - C0) * f


def _local(o, P):
    M = np.array(o.matrix_world)
    return (np.asarray(P, np.float64) - M[:3, 3]) @ np.linalg.inv(M[:3, :3]).T


def _rgb_to_hsv(c):
    mx, mn = c.max(1), c.min(1)
    d = mx - mn
    s = np.where(mx > 0, d / np.where(mx > 0, mx, 1), 0.0)
    dd = np.where(d > 0, d, 1)
    rc, gc, bc = [(mx - c[:, k]) / dd for k in range(3)]
    h = np.where(c[:, 0] == mx, bc - gc, np.where(c[:, 1] == mx, 2.0 + rc - bc, 4.0 + gc - rc)) / 6.0
    h = np.where(s > 0, np.mod(h, 1.0), 0.0)
    return h, s, mx


def _hsv_to_rgb(h, s, v):
    i = np.floor(h * 6.0)
    f = h * 6.0 - i
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    i = i.astype(int) % 6
    r = np.choose(i, [v, q, p, p, t, v])
    g = np.choose(i, [t, v, v, q, p, p])
    b = np.choose(i, [p, p, t, v, v, q])
    return np.stack([r, g, b], 1)


def procedural_colours():
    """Material colour graphs the direct readers cannot read (procedural textures, ramps, Mapping, groups, the
    colour-adjust nodes, a mapped image), evaluated by Geometry Nodes at the points, against their formulas."""
    from mathutils import Euler
    n = 3000
    # Gradient -> Color Ramp on Object coordinates, the object moved, turned and scaled (object space, not world)
    a = obj_with(bpy.ops.mesh.primitive_uv_sphere_add, 'proc_gradient', _proc_mat('p_grad', _gradient_obj),
                 radius=1.0, location=(5.0, 0.0, 0.0))
    a.rotation_euler = (0.0, 0.0, math.radians(30.0))
    a.scale = (1.5, 1.5, 1.5)
    bpy.context.view_layer.update()
    t = PT.from_object(a, n, seed=3)
    ref = _ramp_ref(_local(a, t.points)[:, 0])
    err = float(np.abs(t.colors - ref).max())
    S.check('procedural colour: Gradient -> Color Ramp on Object coordinates (object moved, turned, scaled)',
            err < 2e-3, f'max |diff| {err:.2e}')
    tv_ = PT.from_object(a, 2000, mode='vertices', seed=3)          # the engine's vertex sampling: each vertex's own
    err = float(np.abs(tv_.colors - _ramp_ref(_local(a, tv_.points)[:, 0])).max())
    S.check('procedural colour at the vertices (mode vertices, the engine\'s fromMesh sampling)', err < 2e-2,
            f'max |diff| {err:.2e} (resampling jitter is 1 cm)')
    # Checker on the implicit Generated coordinates (the Vector unlinked: a material's default)
    def checker(nt):
        c = nt.nodes.new('ShaderNodeTexChecker')
        c.inputs['Scale'].default_value = 3.0
        c.inputs['Color1'].default_value = (1.0, 0.0, 0.0, 1.0)
        c.inputs['Color2'].default_value = (1.0, 1.0, 1.0, 1.0)
        return c.outputs['Color']
    b = obj_with(bpy.ops.mesh.primitive_cube_add, 'proc_checker', _proc_mat('p_check', checker), size=2.0,
                 location=(0.0, 4.0, 0.0))
    t = PT.from_object(b, n, seed=4)
    gen = (_local(b, t.points) + 1.0) / 2.0 * 3.0
    gen = (gen + 0.000001) * 0.999999
    xi, yi, zi = [np.abs(np.floor(gen[:, k])).astype(int) for k in range(3)]
    want_red = ((xi % 2) == (yi % 2)) == (zi % 2).astype(bool)
    got_red = t.colors[:, 1] < 0.5
    agree = float((want_red == got_red).mean())
    S.check('procedural colour: Checker on the implicit Generated coordinates', agree > 0.99 and 0.3 < got_red.mean()
            < 0.7, f'{100 * agree:.2f} % of points agree, {100 * got_red.mean():.0f} % red')
    # Mapping (POINT: scale, turn, move) before the gradient
    def mapped(nt):
        mp = nt.nodes.new('ShaderNodeMapping')
        mp.inputs['Location'].default_value = (0.25, 0.0, 0.0)
        mp.inputs['Rotation'].default_value = (0.0, 0.0, math.radians(90.0))
        mp.inputs['Scale'].default_value = (2.0, 1.0, 1.0)
        nt.links.new(nt.nodes.new('ShaderNodeTexCoord').outputs['Object'], mp.inputs['Vector'])
        return _gradient_obj(nt, mp.outputs['Vector'])
    c = obj_with(bpy.ops.mesh.primitive_uv_sphere_add, 'proc_mapping', _proc_mat('p_map', mapped), radius=1.0,
                 location=(0.0, -4.0, 0.0))
    t = PT.from_object(c, n, seed=5)
    R = np.array(Euler((0.0, 0.0, math.radians(90.0)), 'XYZ').to_matrix())
    v = (_local(c, t.points) * np.array([2.0, 1.0, 1.0])) @ R.T + np.array([0.25, 0.0, 0.0])
    err = float(np.abs(t.colors - _ramp_ref(v[:, 0])).max())
    S.check('procedural colour: Mapping (POINT: scale, rotate, move) into the texture', err < 2e-3,
            f'max |diff| {err:.2e}')
    # the same gradient inside a node group
    grp = bpy.data.node_groups.new('grad_group', 'ShaderNodeTree')
    grp.interface.new_socket('Vector', in_out='INPUT', socket_type='NodeSocketVector')
    grp.interface.new_socket('Color', in_out='OUTPUT', socket_type='NodeSocketColor')
    gin, gout = grp.nodes.new('NodeGroupInput'), grp.nodes.new('NodeGroupOutput')
    grp.links.new(_gradient_obj(grp, gin.outputs['Vector']), gout.inputs['Color'])

    def grouped(nt):
        gn = nt.nodes.new('ShaderNodeGroup')
        gn.node_tree = grp
        nt.links.new(nt.nodes.new('ShaderNodeTexCoord').outputs['Object'], gn.inputs['Vector'])
        return gn.outputs['Color']
    d = obj_with(bpy.ops.mesh.primitive_uv_sphere_add, 'proc_group', _proc_mat('p_group', grouped), radius=1.0,
                 location=(0.0, 8.0, 0.0))
    t = PT.from_object(d, n, seed=6)
    err = float(np.abs(t.colors - _ramp_ref(_local(d, t.points)[:, 0])).max())
    S.check('procedural colour: a node group (its inside evaluated with the outer links)', err < 2e-3,
            f'max |diff| {err:.2e}')
    # the colour-adjust nodes Geometry Nodes lacks, rebuilt: Bright/Contrast -> Invert -> Hue/Saturation, and RGB to BW
    def adjusted(nt):
        bc = nt.nodes.new('ShaderNodeBrightContrast')
        bc.inputs['Bright'].default_value, bc.inputs['Contrast'].default_value = 0.05, 0.1
        nt.links.new(_gradient_obj(nt), bc.inputs['Color'])
        iv = nt.nodes.new('ShaderNodeInvert')
        nt.links.new(bc.outputs['Color'], iv.inputs['Color'])
        hs = nt.nodes.new('ShaderNodeHueSaturation')
        hs.inputs['Hue'].default_value, hs.inputs['Saturation'].default_value = 0.3, 0.6
        hs.inputs['Value'].default_value = 1.1
        nt.links.new(iv.outputs['Color'], hs.inputs['Color'])
        return hs.outputs['Color']
    e = obj_with(bpy.ops.mesh.primitive_uv_sphere_add, 'proc_adjust', _proc_mat('p_adj', adjusted), radius=1.0,
                 location=(4.0, 8.0, 0.0))
    t = PT.from_object(e, n, seed=7)
    c0 = _ramp_ref(_local(e, t.points)[:, 0])
    c1 = np.maximum(1.1 * c0 + (0.05 - 0.1 * 0.5), 0.0)
    c2 = 1.0 - c1
    h, s_, v_ = _rgb_to_hsv(c2)
    ref = _hsv_to_rgb(np.mod(h + 0.3 + 0.5, 1.0), np.clip(s_ * 0.6, 0, 1), v_ * 1.1)
    err = float(np.abs(t.colors - ref).max())
    S.check('procedural colour: Bright/Contrast, Invert and Hue/Saturation (rebuilt for Geometry Nodes)', err < 3e-3,
            f'max |diff| {err:.2e}')

    def bw(nt):
        g = nt.nodes.new('ShaderNodeRGBToBW')
        nt.links.new(_gradient_obj(nt), g.inputs['Color'])
        return g.outputs['Val']
    f = obj_with(bpy.ops.mesh.primitive_uv_sphere_add, 'proc_bw', _proc_mat('p_bw', bw), radius=1.0,
                 location=(8.0, 8.0, 0.0))
    t = PT.from_object(f, n, seed=8)
    lum = _ramp_ref(_local(f, t.points)[:, 0]) @ np.array([0.2126, 0.7152, 0.0722])
    err = float(np.abs(t.colors - lum[:, None]).max())
    S.check('procedural colour: RGB to BW (a grey from the luminance)', err < 2e-3, f'max |diff| {err:.2e}')
    # an image through a Mapping (tiled UVs, as glTF texture transforms import): the stripes repeat twice
    img = bpy.data.images['halves']

    def tiled(nt):
        uvn = nt.nodes.new('ShaderNodeUVMap')
        mp = nt.nodes.new('ShaderNodeMapping')
        mp.inputs['Scale'].default_value = (2.0, 2.0, 1.0)
        nt.links.new(uvn.outputs['UV'], mp.inputs['Vector'])
        tx = nt.nodes.new('ShaderNodeTexImage')
        tx.image = img
        nt.links.new(mp.outputs['Vector'], tx.inputs['Vector'])
        return tx.outputs['Color']
    g = obj_with(bpy.ops.mesh.primitive_plane_add, 'proc_tiled', _proc_mat('p_tiled', tiled), size=2.0,
                 location=(0.0, 0.0, 6.0))
    t = PT.from_object(g, n, seed=9)
    x = _local(g, t.points)[:, 0]
    band = np.floor((x + 1.0) / 0.5).astype(int)                     # four bands across: red, blue, red, blue
    inner = np.abs(((x + 1.0) / 0.5) - np.round((x + 1.0) / 0.5)) > 0.1
    want_red = band % 2 == 0
    got_red = t.colors[:, 0] > t.colors[:, 2]
    agree = float((want_red == got_red)[inner].mean())
    S.check('procedural colour: an image through a Mapping (scale 2: the halves repeat)', agree > 0.99,
            f'{100 * agree:.2f} % of points in their band\'s colour')
    # world height (the Geometry node's Position) and facing (Texture Coordinate Normal, object space; flat shading)
    def height(nt):
        sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(nt.nodes.new('ShaderNodeNewGeometry').outputs['Position'], sep.inputs[0])
        return _ramp(nt, sep.outputs['Z'])
    hz = obj_with(bpy.ops.mesh.primitive_uv_sphere_add, 'proc_height', _proc_mat('p_height', height), radius=1.0,
                  location=(0.0, -12.0, 0.5))
    hz.rotation_euler = (0.7, 0.2, 0.0)
    t = PT.from_object(hz, n, seed=11)
    err = float(np.abs(t.colors - _ramp_ref(t.points[:, 2])).max())
    S.check("procedural colour: the Geometry node's Position (world height) -> ramp", err < 2e-3,
            f'max |diff| {err:.2e}')

    def facing(nt):
        sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(nt.nodes.new('ShaderNodeTexCoord').outputs['Normal'], sep.inputs[0])
        return _ramp(nt, sep.outputs['Z'])
    fz = obj_with(bpy.ops.mesh.primitive_cube_add, 'proc_facing', _proc_mat('p_facing', facing), size=2.0,
                  location=(4.0, -12.0, 0.0))
    fz.rotation_euler = (0.0, 0.0, 0.8)                  # turned about Z: object Z stays up, the sides stay sides
    t = PT.from_object(fz, n, seed=12)
    lp = _local(fz, t.points)
    top = (lp[:, 2] > 0.999) & (np.abs(lp[:, :2]).max(1) < 0.99)      # the top face's inside, not a side's rim
    side = np.abs(lp[:, 2]) < 0.99
    ok = np.allclose(t.colors[top], C1, atol=2e-3) and np.allclose(t.colors[side], C0, atol=2e-3)
    S.check('procedural colour: Texture Coordinate Normal (object space): the top orange, the sides blue', ok,
            f'top {t.colors[top].mean(0).round(3)}, sides {t.colors[side].mean(0).round(3)}')
    # a smooth-shaded sphere: the shading normal is the interpolated corner normal (close to radial), not the facet's
    sm = obj_with(bpy.ops.mesh.primitive_uv_sphere_add, 'proc_smooth', _proc_mat('p_smooth', facing), radius=1.0,
                  location=(8.0, -12.0, 0.0))
    bpy.ops.object.shade_smooth()
    t = PT.from_object(sm, n, seed=13)
    radial = _local(sm, t.points)
    radial /= np.linalg.norm(radial, axis=1, keepdims=True)
    err = float(np.abs(t.colors - _ramp_ref(radial[:, 2])).max())
    S.check('procedural colour: a smooth-shaded sphere reads its smooth (corner) normals, close to radial', err < 0.04,
            f'max |diff| to the radial normal {err:.3f}')
    # which graphs the direct readers keep (an image at the UVs, an image under a constant multiply tint) and which go
    # to the Geometry Nodes evaluation (a tint behind a reroute, which the direct reader would miss; a ramp)
    def tinted(nt, reroute=False):
        tx = nt.nodes.new('ShaderNodeTexImage')
        tx.image = img
        mx = nt.nodes.new('ShaderNodeMix')
        mx.data_type, mx.blend_type = 'RGBA', 'MULTIPLY'
        ins = {s.identifier: s for s in mx.inputs}
        ins['Factor_Float'].default_value = 1.0
        ins['B_Color'].default_value = (0.5, 0.9, 0.2, 1.0)
        nt.links.new(tx.outputs['Color'], ins['A_Color'])
        out = {s.identifier: s for s in mx.outputs}['Result_Color']
        if reroute:
            rr = nt.nodes.new('NodeReroute')
            nt.links.new(out, rr.inputs[0])
            out = rr.outputs[0]
        return out

    def plain_image(nt):
        tx = nt.nodes.new('ShaderNodeTexImage')
        tx.image = img
        return tx.outputs['Color']
    decisions = []
    for nm, build in (('image', plain_image), ('tint', tinted), ('tint_reroute', lambda nt: tinted(nt, True)),
                      ('ramp', _gradient_obj)):
        m_ = _proc_mat('p_dec_' + nm, build)
        decisions.append(PT._needs_graph(m_.node_tree.nodes['Principled BSDF'].inputs['Base Color']))
    S.check('direct reading kept for an image and an image under a constant tint; the graph for a tint behind a '
            'reroute and for a ramp', decisions == [False, False, True, True], str(decisions))
    # a node it cannot reproduce: the direct reading stands in (no failure)
    def odd(nt):
        w = nt.nodes.new('ShaderNodeWavelength')
        return w.outputs['Color']
    h_ = obj_with(bpy.ops.mesh.primitive_uv_sphere_add, 'proc_odd', _proc_mat('p_odd', odd), radius=1.0,
                  location=(0.0, -8.0, 0.0))
    t = PT.from_object(h_, 500, seed=10)
    S.check('procedural colour: an unreproducible node falls back to the direct reading (no failure)',
            t.colors is not None and np.isfinite(t.colors).all() and len(t) == 500, str(t.colors.mean(0).round(3)))
    for o in (a, b, c, d, e, f, g, h_, hz, fz, sm):
        bpy.data.objects.remove(o)


def main():
    sc = S.clean_scene(24, 1, 48)
    t0 = time.time()

    # ---------------------------------------------------------------- meshes and material colours
    red = mat('red', (0.8, 0.05, 0.05))
    cube = obj_with(bpy.ops.mesh.primitive_cube_add, 'cube', red, size=2.0, location=(0, 0, 0))
    t = PT.from_object(cube, N)
    P = t.points
    on_face = np.isclose(np.abs(P).max(1), 1.0, atol=1e-4)
    faces = np.argmax(np.abs(P), 1) * 2 + (P[np.arange(len(P)), np.argmax(np.abs(P), 1)] > 0)
    share = np.bincount(faces, minlength=6) / len(P)
    S.check('surface: every point on the cube\'s faces', on_face.all() and len(P) == N, f'{on_face.mean():.4f}')
    S.check('surface: area-weighted (each face ~1/6)', np.abs(share - 1 / 6).max() < 0.02, str(np.round(share, 3)))
    S.check('colour: a Base Color value', np.allclose(t.colors.mean(0), (0.8, 0.05, 0.05), atol=1e-4),
            str(t.colors.mean(0)))
    tv = PT.from_object(cube, N, mode='vertices')
    S.check('vertices mode (the engine\'s): points at the 8 corners', np.allclose(np.abs(tv.points), 1.0, atol=0.011),
            f'{len(tv)} points')
    tvol = PT.from_object(cube, N, mode='volume', voxel=0.05)
    inside = (np.abs(tvol.points) < 1.0 + 0.06).all(1)
    deep = (np.abs(tvol.points).max(1) < 0.7).mean()
    S.check('volume mode: points inside the cube, through its depth', inside.all() and deep > 0.2,
            f'inside {inside.mean():.3f}, |p|<0.7: {deep:.2f}')
    bpy.data.objects.remove(cube)

    # an image texture: left half red, right half blue (a float image, linear)
    img = bpy.data.images.new('halves', 64, 32, alpha=True, float_buffer=True)
    px = np.zeros((32, 64, 4), np.float32)
    px[:, :32] = (1, 0, 0, 1)
    px[:, 32:] = (0, 0, 1, 1)
    img.pixels.foreach_set(px.ravel())
    plane = obj_with(bpy.ops.mesh.primitive_plane_add, 'plane_tex', mat('tex', image=img), size=2.0)
    t = PT.from_object(plane, N)
    left, right = t.points[:, 0] < -0.05, t.points[:, 0] > 0.05
    S.check('colour: an image texture at the points\' UVs (left red, right blue)',
            t.colors[left, 0].mean() > 0.95 and t.colors[right, 2].mean() > 0.95,
            f'left {t.colors[left].mean(0).round(3)} right {t.colors[right].mean(0).round(3)}')
    bpy.data.objects.remove(plane)
    # a byte sRGB texture: 50 % grey in the file is 0.214 linear
    g8 = bpy.data.images.new('grey8', 8, 8, alpha=False, float_buffer=False)
    g8.colorspace_settings.name = 'sRGB'          # first: a generated image regenerates (blank) when it changes
    g8.pixels.foreach_set(np.full(8 * 8 * 4, 128 / 255.0, np.float32))
    plane = obj_with(bpy.ops.mesh.primitive_plane_add, 'plane_g8', mat('g8', image=g8), size=2.0)
    t = PT.from_object(plane, 500)
    S.check('colour: a byte sRGB texture is linearised', abs(float(t.colors.mean()) - 0.2158) < 0.01,
            f'{float(t.colors.mean()):.4f} (0.2158 expected)')
    bpy.data.objects.remove(plane)
    glow = obj_with(bpy.ops.mesh.primitive_uv_sphere_add, 'glow', mat('em', (0.1, 0.1, 0.1),
                                                                       emission=((0.0, 1.0, 0.2), 2.0)))
    t = PT.from_object(glow, 500)
    S.check('colour: emission adds to the base', t.colors[:, 1].mean() > 1.9, str(t.colors.mean(0).round(3)))
    bpy.data.objects.remove(glow)
    # alpha cut: the right half of the texture is transparent
    ac = bpy.data.images.new('alphacut', 64, 32, alpha=True, float_buffer=True)
    pa = np.ones((32, 64, 4), np.float32)
    pa[:, 32:, 3] = 0.0
    ac.pixels.foreach_set(pa.ravel())
    plane = obj_with(bpy.ops.mesh.primitive_plane_add, 'plane_cut', mat('cut', image=ac, alpha_from_image=True),
                     size=2.0)
    t = PT.from_object(plane, N)
    S.check('alpha cut: no points on transparent texels', (t.points[:, 0] < 0.02).all() and len(t) == N,
            f'max x {t.points[:, 0].max():.3f}')
    bpy.data.objects.remove(plane)
    # modifiers evaluated: an array of 3 cubes along X
    cube = obj_with(bpy.ops.mesh.primitive_cube_add, 'arrayed', red, size=1.0)
    arr = cube.modifiers.new('array', 'ARRAY')
    arr.count = 3
    t = PT.from_object(cube, N)
    S.check('modifiers evaluated (an array of 3)', t.points[:, 0].max() > 2.45, f'x max {t.points[:, 0].max():.2f}')
    bpy.data.objects.remove(cube)
    # the same faces handed over in another order, each from another corner (Blender can do that to an instance's
    # triangles from one session to the next): a seeded sample must not change
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0)
    src = bpy.context.object
    V = [tuple(v.co) for v in src.data.vertices]
    F = [tuple(p.vertices) for p in src.data.polygons]
    bpy.data.objects.remove(src)
    meshes = []
    # (turned by two corners: a quad keeps its diagonal, so the triangles are the same ones, handed over differently)
    for nm, faces in (('faces_a', F), ('faces_b', [f[2:] + f[:2] for f in reversed(F)])):
        me = bpy.data.meshes.new(nm)
        me.from_pydata(V, [], faces)
        o = bpy.data.objects.new(nm, me)
        sc.collection.objects.link(o)
        meshes.append(o)
    ta, tb = PT.from_object(meshes[0], 3000, seed=7), PT.from_object(meshes[1], 3000, seed=7)
    S.check('a seeded sample does not depend on the order or starting corner of the faces (the same points)',
            np.allclose(ta.points, tb.points, atol=1e-6), f'max |diff| {np.abs(ta.points - tb.points).max():.2e}')
    for o in meshes:
        bpy.data.objects.remove(o)
    procedural_colours()

    # ---------------------------------------------------------------- curves, text, metaballs
    bpy.ops.curve.primitive_bezier_circle_add(radius=1.0)
    circ = bpy.context.object
    t = PT.from_object(circ, 2000)
    r = np.linalg.norm(t.points[:, :2], axis=1)
    S.check('a curve without bevel: points along it (edges)', np.abs(r - 1).max() < 0.02, f'r {r.min():.3f}..{r.max():.3f}')
    circ.data.bevel_depth = 0.1
    t = PT.from_object(circ, 2000)
    r = np.linalg.norm(t.points[:, :2], axis=1)
    S.check('a bevelled curve: its tube surface', 0.85 < r.min() and r.max() < 1.15 and np.abs(t.points[:, 2]).max() > 0.05,
            f'r {r.min():.3f}..{r.max():.3f}')
    bpy.data.objects.remove(circ)
    bpy.ops.object.text_add()
    txt = bpy.context.object
    txt.data.body = 'HI'
    t = PT.from_object(txt, 3000)
    S.check('a text object: points in its glyphs', len(t) == 3000 and t.points[:, 0].max() > 0.5 and finite(t),
            f'x {t.points[:, 0].min():.2f}..{t.points[:, 0].max():.2f}')
    bpy.data.objects.remove(txt)
    bpy.ops.object.metaball_add(type='BALL', radius=1.0)
    mb = bpy.context.object
    t = PT.from_object(mb, 2000)
    r = np.linalg.norm(t.points, axis=1)
    S.check('a metaball: its polygonised surface', len(t) == 2000 and 0.5 < r.mean() < 1.5, f'mean r {r.mean():.2f}')
    bpy.data.objects.remove(mb)

    # ---------------------------------------------------------------- Geometry Nodes output, instancers, collections
    from eidoblend.fx._nodes import new_group, Builder
    host = obj_with(bpy.ops.mesh.primitive_plane_add, 'gn_host', None, size=0.1)
    tree, gi, go = new_group('test_instances', 'GeometryNodeTree', [('Geometry', 'NodeSocketGeometry')],
                             [('Geometry', 'NodeSocketGeometry')])
    b = Builder(tree)
    grid = b.node('GeometryNodeMeshGrid')
    grid.inputs['Size X'].default_value = grid.inputs['Size Y'].default_value = 4.0
    grid.inputs['Vertices X'].default_value = grid.inputs['Vertices Y'].default_value = 3
    cb = b.node('GeometryNodeMeshCube')
    cb.inputs['Size'].default_value = (0.4, 0.4, 0.4)
    sm = b.node('GeometryNodeSetMaterial')
    sm.inputs['Material'].default_value = red
    tree.links.new(cb.outputs[0], sm.inputs[0])
    iop = b.node('GeometryNodeInstanceOnPoints')
    tree.links.new(grid.outputs[0], iop.inputs['Points'])
    tree.links.new(sm.outputs[0], iop.inputs['Instance'])
    tree.links.new(iop.outputs[0], go.inputs[0])
    host.modifiers.new('gn', 'NODES').node_group = tree
    t = PT.from_object(host, 4500)
    xs = np.round(t.points[:, 0] / 2.0)
    S.check('Geometry Nodes instances: 9 cubes on a 4 m grid, in their material',
            set(np.unique(xs)) == {-1.0, 0.0, 1.0} and np.allclose(t.colors.mean(0), (0.8, 0.05, 0.05), atol=1e-3),
            f'x cells {sorted(set(np.unique(xs)))}')
    pts_tree, gi2, go2 = new_group('test_points', 'GeometryNodeTree', [('Geometry', 'NodeSocketGeometry')],
                                   [('Geometry', 'NodeSocketGeometry')])
    b2 = Builder(pts_tree)
    pn = b2.node('GeometryNodePoints')
    pn.inputs['Count'].default_value = 400
    rv = b2.node('FunctionNodeRandomValue', data_type='FLOAT_VECTOR')
    rv.inputs['Min'].default_value = (-1, -1, 2)
    rv.inputs['Max'].default_value = (1, 1, 3)
    pts_tree.links.new(rv.outputs['Value'], pn.inputs['Position'])
    pts_tree.links.new(pn.outputs[0], go2.inputs[0])
    host2 = obj_with(bpy.ops.mesh.primitive_plane_add, 'gn_points', None, size=0.1)
    host2.modifiers.new('gn', 'NODES').node_group = pts_tree
    t = PT.from_object(host2, 1000)
    S.check('Geometry Nodes point cloud output', (t.points[:, 2] >= 1.99).all() and len(t) == 1000,
            f'z {t.points[:, 2].min():.2f}..{t.points[:, 2].max():.2f}')
    bpy.data.objects.remove(host)
    bpy.data.objects.remove(host2)
    src_coll = bpy.data.collections.new('inst_src')
    sc.collection.children.link(src_coll)
    bpy.ops.mesh.primitive_ico_sphere_add(radius=0.5, location=(0, 0, 0))
    ico = bpy.context.object
    for c in list(ico.users_collection):
        c.objects.unlink(ico)
    src_coll.objects.link(ico)
    bpy.context.view_layer.layer_collection.children[src_coll.name].exclude = True
    empty = bpy.data.objects.new('instancer', None)
    empty.instance_type = 'COLLECTION'
    empty.instance_collection = src_coll
    empty.location = (5, 0, 1)
    sc.collection.objects.link(empty)
    t = PT.from_object(empty, 1000)
    S.check('a collection instance: points where it is instanced',
            np.allclose(t.centroid(), (5, 0, 1), atol=0.05), str(t.centroid().round(3)))
    emitter = obj_with(bpy.ops.mesh.primitive_plane_add, 'emitter', None, size=2.0, location=(-5, 0, 0))
    psm = emitter.modifiers.new('hair', 'PARTICLE_SYSTEM')
    pset = psm.particle_system.settings
    pset.type = 'HAIR'
    pset.count = 12
    pset.hair_length = 0.5
    pset.render_type = 'OBJECT'
    pset.instance_object = ico
    pset.particle_size = 0.3
    emitter.show_instancer_for_render = emitter.show_instancer_for_viewport = False
    bpy.context.view_layer.update()
    t = PT.from_object(emitter, 1200)
    S.check('a particle-system instancer: its instanced objects', len(t) == 1200 and abs(t.centroid()[0] + 5) < 0.6,
            f'centroid {t.centroid().round(2)}')
    bpy.data.objects.remove(emitter)
    bpy.data.objects.remove(empty)
    coll = bpy.data.collections.new('group')
    sc.collection.children.link(coll)
    for i, x in enumerate((-2.0, 2.0)):
        bpy.ops.mesh.primitive_cube_add(size=1.0 if i == 0 else 2.0, location=(x, 0, 0))
        o = bpy.context.object
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
    t = PT.from_object(coll, 5000)
    frac_big = (t.points[:, 0] > 0).mean()
    S.check('a whole collection, area-weighted (the 2 m cube has 4x the area)', abs(frac_big - 0.8) < 0.03,
            f'{frac_big:.3f} on the big cube')
    for o in list(coll.objects):
        bpy.data.objects.remove(o)

    # ---------------------------------------------------------------- my robot body, live
    from eidoblend.characters import load_vrm
    me = load_vrm('claude_robot_2k', name='claude', location=(0, 0, 0))
    pb = me.pb('rightUpperArm')
    if pb is not None:
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = (0, 0, 0)
        pb.keyframe_insert('rotation_euler', frame=1)
        pb.rotation_euler = (0.0, 0.0, 1.2)
        pb.keyframe_insert('rotation_euler', frame=10)
    sc.frame_set(1)
    body = PT.from_object(me, 8000, live=True)
    S.check('my body sampled live (a binding on its meshes)', body.live is not None and len(body) == 8000,
            f'{len(body.live.objects)} meshes')
    p1, p10 = body.live.points(1), body.live.points(10)
    moved = np.linalg.norm(p10 - p1, axis=1)
    S.check('live: the right arm moves between frames 1 and 10, the rest stays', moved.max() > 0.2 and
            np.median(moved) < 1e-4, f'max {moved.max():.3f} m, median {np.median(moved):.2e}')
    mean_col = body.colors.mean(0)
    S.check('my body in its own colours (its albedo textures, not the 0.8 grey default)',
            body.colors.std(0).max() > 0.05 and not np.allclose(mean_col, 0.8, atol=0.02), str(mean_col.round(3)))
    m = PM.make_particle_morph(count=8000, targets=[body, 'sphere'], name='live_check')
    P, C = eval_cloud(m, 10)
    err = float(np.abs(P - body.live.points(10)).max())
    S.check('the morph graph samples the live binding = the CPU binding (frame 10)', err < 2e-4, f'{err:.2e} m')
    S.check('the graph carries the body\'s colours', C is not None and np.abs(C - body.colors).max() < 1e-4)
    moved = body.scaled(0.5).translated((3.0, 1.0, 0.0)).resample(9000)       # a transformed, upsampled live target
    mt = PM.make_particle_morph(count=9000, targets=[moved, 'sphere'], name='live_moved')
    P, _ = eval_cloud(mt, 10)
    err = float(np.abs(P - moved.live.points(10)).max())
    S.check('a transformed live target (scaled, moved, upsampled): the graph = the CPU', err < 2e-4, f'{err:.2e} m')
    bpy.data.objects.remove(mt.object)
    eng = PM.from_mesh(me, 4000, live=True)
    m2 = PM.make_particle_morph(count=4000, targets=[eng, 'sphere'], name='live_check_vertices')
    P, _ = eval_cloud(m2, 10)
    err = float(np.abs(P - eng.live.points(10)).max())
    S.check('the engine\'s from_mesh live (vertex binding) in the graph', err < 2e-4, f'{err:.2e} m')
    snap = PM.from_mesh(me, 4000, frame=10)
    S.check('from_mesh(frame=10): a snapshot at that frame', isinstance(snap, np.ndarray) and snap.shape == (4000, 3)
            and sc.frame_current == 10)
    # stagger 'down' at m 0.5: the head leaves first
    m.set_stagger(0.6, 'down')
    m.uniforms.morph.value = 0.5
    P, _ = eval_cloud(m, 10)
    src = body.live.points(10)
    disp = np.linalg.norm(P - src, axis=1)
    top = src[:, 2] > np.percentile(src[:, 2], 80)
    bot = src[:, 2] < np.percentile(src[:, 2], 20)
    S.check('stagger down: the head has left, the feet have not yet', disp[top].mean() > 3 * disp[bot].mean(),
            f'head {disp[top].mean():.2f} m, feet {disp[bot].mean():.2f} m')
    for o in (m.object, m2.object):
        bpy.data.objects.remove(o)
    # keyed hidden (the hand-off) and nothing referencing it: sampled at a frame where it is hidden, still read live
    PM.key_visibility(me, 1, True)
    PM.key_visibility(me, 8, False)
    sc.frame_set(1)
    late = PT.from_object(me, 3000, frame=10, seed=5)
    p10 = body.live.points(10)
    sc.frame_set(10)
    p10b = body.live.points()
    S.check('keyed hidden at the frame asked: sampled there all the same (snapshot and live binding, the posed arm)',
            len(late) == 3000 and late.points[:, 2].max() > 1.0 and np.abs(p10 - p10b).max() < 1e-6 and
            np.linalg.norm(p10 - body.live.points(1), axis=1).max() > 0.2 and all(o.hide_render for o in me.meshes))
    sc.frame_set(1)
    PT.set_visible(me, False)

    # ---------------------------------------------------------------- files
    for o in list(bpy.context.selected_objects):
        o.select_set(False)
    monkey = obj_with(bpy.ops.mesh.primitive_monkey_add, 'monkey', red, location=(0, 0, 0))
    lo0, hi0 = PT.from_object(monkey, 20000).bounds()
    monkey.select_set(True)
    bpy.context.view_layer.objects.active = monkey
    paths = {'.obj': os.path.join(FILES, 'monkey.obj'), '.fbx': os.path.join(FILES, 'monkey.fbx'),
             '.glb': os.path.join(FILES, 'monkey.glb'), '.gltf': os.path.join(FILES, 'monkey.gltf'),
             '.ply': os.path.join(FILES, 'monkey.ply'), '.stl': os.path.join(FILES, 'monkey.stl')}
    bpy.ops.wm.obj_export(filepath=paths['.obj'], export_selected_objects=True)
    bpy.ops.export_scene.fbx(filepath=paths['.fbx'], use_selection=True)
    bpy.ops.export_scene.gltf(filepath=paths['.glb'], use_selection=True, export_format='GLB')
    bpy.ops.export_scene.gltf(filepath=paths['.gltf'], use_selection=True, export_format='GLTF_SEPARATE')
    bpy.ops.wm.ply_export(filepath=paths['.ply'], export_selected_objects=True)
    bpy.ops.wm.stl_export(filepath=paths['.stl'], export_selected_objects=True)
    bpy.data.objects.remove(monkey)
    for ext, p in paths.items():
        try:
            t = PT.from_file(p, 20000)
            lo, hi = t.bounds()
            err = float(max(np.abs(lo - lo0).max(), np.abs(hi - hi0).max()))
            S.check(f'a {ext} file: the model\'s shape', err < 0.02 and len(t) == 20000, f'bounds off by {err:.3f} m')
            if ext in ('.obj', '.fbx', '.glb', '.gltf'):
                S.check(f'a {ext} file: in its material\'s colour', np.allclose(t.colors.mean(0), (0.8, 0.05, 0.05),
                                                                                atol=0.03), str(t.colors.mean(0).round(3)))
        except Exception as e:
            S.check(f'a {ext} file', False, repr(e))
    try:
        stool = PT.target('polyhaven:wooden_stool_01', 20000, fit_height=1.5, at=(0, 0, 0.75), anchor='center')
        lo, hi = stool.bounds()
        S.check('polyhaven:wooden_stool_01 (the shared library): fit to 1.5 m, in its wood colours',
                abs((hi - lo)[2] - 1.5) < 1e-3 and stool.colors.std(0).max() > 0.01 and 0.02 < stool.colors.mean() < 0.6,
                f'height {(hi - lo)[2]:.3f}, colour {stool.colors.mean(0).round(3)} sd {stool.colors.std(0).round(3)}')
        S.check('the imported model stays hidden (the cloud stands for it)', stool.source.hide_render)
    except Exception as e:
        S.check('polyhaven:wooden_stool_01', False, repr(e))
    # the repo's own model library by name, an animated one, live: the crow flaps its own clip while hidden
    try:
        S.check("model:<name> resolves a unique part of a library name",
                os.path.basename(PT.model_path('crow')).startswith('crow_bird_animated'))
        sc.frame_end = max(sc.frame_end, 40)
        crow = PT.from_file('model:crow', 6000, live=True, clip=0, fit_height=0.8, at=(0, 0, 2.0))
        a, b_ = crow.live.points(5), crow.live.points(17)
        mv = np.linalg.norm(b_ - a, axis=1)
        S.check('model:crow live with its own clip: it moves between frames while hidden (wings flap)',
                crow.live is not None and mv.max() > 0.02 and all(o.hide_render for o in PT._objects_of(crow.source)
                                                                   if o.type == 'MESH'),
                f'max {mv.max():.3f} m over {len(crow.live.objects)} mesh(es), colour {crow.colors.mean(0).round(3)}')
        mc = PM.make_particle_morph(count=6000, targets=[crow, 'sphere'], name='crow_check')
        P5, _ = eval_cloud(mc, 5)
        P, _ = eval_cloud(mc, 17)
        err = float(np.abs(P - crow.live.points(17)).max())
        S.check('the morph graph follows the hidden animated model (frame 17 = the CPU binding; it moved from 5)',
                err < 2e-4 and float(np.abs(P - P5).max()) > 0.02, f'{err:.2e} m, moved {np.abs(P - P5).max():.3f} m')
        bpy.data.objects.remove(mc.object)
        PT.set_visible(crow.source, False)
    except Exception as e:
        import traceback
        traceback.print_exc()
        S.check('model:crow (live, clip)', False, repr(e))
    try:
        v = PT.target('vrm:claude_suit', 5000, fit_height=1.0, at=(4.0, 0, 1.0))
        lo, hi = v.bounds()
        S.check("'vrm:claude_suit' as a spec: the VRM in its MToon colours, fit to 1 m",
                abs((hi - lo)[2] - 1.0) < 1e-3 and v.colors is not None and v.colors.std(0).max() > 0.05,
                f'colour {v.colors.mean(0).round(3)}')
    except Exception as e:
        S.check("'vrm:claude_suit'", False, repr(e))

    # ---------------------------------------------------------------- images, silhouettes
    star = os.path.join(S.REPO, 'eidoverse', 'assets', 'particle_textures', 'star_01.png')
    t = PT.from_image(star, 5000, width=2.0, mode='alpha')
    S.check('an image\'s alpha (a silhouette): points in the XZ plane facing -Y', np.allclose(t.points[:, 1], 0) and
            t.points[:, 0].max() <= 1.0 and len(t) == 5000)
    prev = os.path.join(S.REPO, 'eidoverse', 'assets', 'vrms', 'claude_robot_preview.jpg')
    for mode in ('any', 'luma', 'dark', 'edges'):
        t = PT.from_image(prev, 5000, width=2.5, mode=mode)
        S.check(f'an image in mode {mode}: points, in the pixels\' colours', len(t) == 5000 and finite(t) and
                t.colors is not None and t.colors.std() > 0.01, f'colour mean {t.colors.mean(0).round(3)}')
    bpy.ops.mesh.primitive_monkey_add(location=(0, 0, 2))
    mk = bpy.context.object
    mk.data.materials.append(red)
    sil = PT.from_silhouette(mk, 5000, axis='-y')
    lo, hi = PT.from_object(mk, 20000).bounds()
    slo, shi = sil.bounds()
    S.check('a silhouette: flat (one y), the model\'s outline (its x and z extents), its colour',
            np.ptp(sil.points[:, 1]) < 1e-6 and abs(slo[0] - lo[0]) < 0.05 and abs(shi[2] - hi[2]) < 0.05 and
            np.allclose(sil.colors.mean(0), (0.8, 0.05, 0.05), atol=0.02), f'x {slo[0]:.2f}/{lo[0]:.2f}')

    # ---------------------------------------------------------------- point clouds, volumes
    t = PT.from_point_cloud(paths['.ply'], 3000)
    S.check('a .ply file as a point cloud', len(t) == 3000 and finite(t))
    xyz = os.path.join(FILES, 'cloud.xyz')
    rng = np.random.default_rng(3)
    cloud = np.concatenate([rng.normal(size=(800, 3)), rng.random((800, 3)) * 255], 1)
    np.savetxt(xyz, cloud, fmt='%.5f')
    np.save(os.path.join(FILES, 'cloud.npy'), cloud[:, :3])
    t = PT.target(xyz, 2000)
    S.check('an .xyz file with rgb 0..255 (colours linearised)', len(t) == 2000 and t.colors is not None and
            t.colors.max() <= 1.0)
    t = PT.target(os.path.join(FILES, 'cloud.npy'), 2000)
    S.check('an .npy file', len(t) == 2000 and finite(t))
    vhost = obj_with(bpy.ops.mesh.primitive_uv_sphere_add, 'vol_host', None, radius=1.0, location=(0, 4, 1))
    vt, vgi, vgo = new_group('test_volume', 'GeometryNodeTree', [('Geometry', 'NodeSocketGeometry')],
                             [('Geometry', 'NodeSocketGeometry')])
    vb = Builder(vt)
    m2v = vb.node('GeometryNodeMeshToVolume')
    vt.links.new(vgi.outputs[0], m2v.inputs['Mesh'])
    vt.links.new(m2v.outputs[0], vgo.inputs[0])
    vhost.modifiers.new('vol', 'NODES').node_group = vt
    t = PT.from_volume(vhost, 3000, threshold=0.1)
    d = np.linalg.norm(t.points - np.array([0, 4, 1]), axis=1)
    S.check('a Geometry Nodes volume: points inside it', len(t) == 3000 and d.max() < 1.1, f'max r {d.max():.2f}')
    bpy.data.objects.remove(vhost)
    vdbs = sorted(glob.glob(os.path.join(S.REPO, 'blender', 'tests', 'fx', 'out', 'fire_cache', 'fire_00*.vdb')))
    if vdbs:
        t = PT.from_file(vdbs[min(23, len(vdbs) - 1)], 4000)
        S.check(f'a .vdb (the fire cache, {os.path.basename(vdbs[min(23, len(vdbs) - 1)])}): density-coloured points',
                len(t) == 4000 and finite(t) and t.colors is not None and t.colors.std() > 0.01,
                f'bounds {t.bounds()[0].round(2)}..{t.bounds()[1].round(2)}')
    else:
        print('SKIP no .vdb in blender/tests/fx/out/fire_cache (run the fire test first)')

    # ---------------------------------------------------------------- shapes, text specs, the resolver
    for nm in PT.SHAPES:
        t = PT.target(nm, 3000, at=(1, 2, 3))
        S.check(f'shape {nm}', len(t) == 3000 and finite(t) and np.allclose(t.centroid(), (1, 2, 3), atol=1e-4))
    g = PT.shapes.galaxy(3000, colors=('#fff4d0', '#4060ff'))
    S.check('galaxy colours core -> rim', g.colors is not None and g.colors[:, 0].max() > g.colors[:, 0].min())
    for spec in ('text:HELLO', 'ascii: /\\_/\\\n( o.o )\n > ^ < ', 'banner:HI'):
        t = PT.target(spec, 4000, width=3.0)
        S.check(f'spec {spec.splitlines()[0]!r}', len(t) == 4000 and finite(t) and np.ptp(t.points[:, 0]) > 1.5,
                f'width {np.ptp(t.points[:, 0]):.2f}')
    print(PM.ascii_banner('CLAUDE'))
    S.check('ascii_banner: a block-letter banner', PM.ascii_banner('CLAUDE').count('#') > 100)
    thick = PM.from_text('DEPTH', 4000, depth=0.3)
    S.check('fromText depth: the letters 0.3 m thick (in Y, facing -Y)', 0.25 < np.ptp(thick[:, 1]) <= 0.3)
    # downsampled (no jitter), the points sit on the stride's pixel grid: the smallest column step is the stride
    def col_step(s):
        x = np.unique(np.round(PM.from_text('DOT', 500, pixel_stride=s)[:, 0].astype(np.float64), 6))
        return float(np.diff(x).min())
    r = col_step(4) / col_step(1)
    S.check('fromText pixelStride: stride 4 samples every 4th pixel column', 3.6 < r < 4.4, f'ratio {r:.2f}')
    orb = PM.font_file('Orbitron')
    S.check('fromText fontFamily: a repo display font by name (eidoverse/assets/fonts)', orb.endswith('Orbitron.ttf'),
            orb)
    # installed system families by name, as the engine's canvas found them (the films ask for these two)
    if os.path.exists('C:/Windows/Fonts/georgiab.ttf') and os.path.exists('C:/Windows/Fonts/ariblk.ttf'):
        geo = PM.font_file('Georgia, serif', 'bold')
        blk = PM.font_file('Arial Black, sans-serif', 'bold')
        S.check("fromText fontFamily: system families by name ('Georgia' bold -> georgiab, 'Arial Black' -> ariblk), "
                "not the generic fallback", os.path.basename(geo).lower() == 'georgiab.ttf' and
                os.path.basename(blk).lower() == 'ariblk.ttf', f'{os.path.basename(geo)}, {os.path.basename(blk)}')
    a_b = PM.text_mask('Wide', weight='bold')
    a_n = PM.text_mask('Wide', weight='normal')
    S.check('fromText weight: bold covers more pixels than normal', (a_b > 128).sum() > 1.15 * (a_n > 128).sum())
    S.check('the font ascent read from the font file (Arial ~0.905 em)', 0.85 < PM.font_ascent(
        PM.font_file('Arial, sans-serif', 'bold')) < 0.95)
    t = PT.target({'text': 'WORD', 'width': 2.0, 'at': (0, 0, 1.5)}, 2000)
    S.check('dict spec {"text": ..}', np.allclose(t.centroid(), (0, 0, 1.5), atol=1e-4))
    t = PT.target(('galaxy', {'radius': 1.0}), 2000)
    S.check('tuple spec (name, opts)', np.abs(t.points[:, :2]).max() < 1.6)
    t = PT.target({'shape': 'neural_net', 'layers': [3, 5, 3]}, 2000)
    S.check('the engine\'s generators by name', len(t) == 2000 and finite(t))

    # ---------------------------------------------------------------- counts, centroids, pairing
    a = PT.target('text:A', 3000)
    b_ = a.resample(5000)
    S.check('equal counts: resample up (cycle + jitter) and down', len(b_) == 5000 and len(a.resample(1000)) == 1000)
    ts = PT.match_centroids([PT.target('sphere', 2000) + (3, 0, 0), PT.target('cube', 2000), PT.target('text:HI', 2000)])
    S.check('matched centroids', all(np.allclose(t.centroid(), ts[0].centroid(), atol=1e-4) for t in ts))
    ph = PT.pair(PT.target('sphere', 2000), 'height')
    S.check('pairing by height: particle i is the i-th highest', np.all(np.diff(ph.points[:, 2]) <= 1e-7))
    sp = PT.pair(PT.target('cube', 2000), 'space')
    step = np.linalg.norm(np.diff(sp.points, axis=0), axis=1).mean()
    rnd_step = np.linalg.norm(np.diff(PT.target('cube', 2000).points, axis=0), axis=1).mean()
    S.check('pairing by space: consecutive particles are near each other', step < rnd_step / 3,
            f'{step:.3f} vs {rnd_step:.3f} m')
    print(f'[targets] {time.time() - t0:.1f} s')
    ok = S.summary('targets')
    sys.exit(0 if ok else 1)


try:
    main()
except SystemExit:
    raise
except Exception:
    import traceback
    traceback.print_exc()
    print('FAIL exception')
    sys.exit(1)

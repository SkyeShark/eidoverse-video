"""Metal near a blast reflects the mushroom cloud (the engine's nuclear_explosion reflection pass), through light probes:
nuclear_explosion's reflections=True (each volume's stand-in for the probes) and reflect_in(objects) (a sphere probe
round each metal object). The cloud at t = 7.5 s, scale 1 (13 m tall), 45 m off, emission-only as the effect draws it.

Checks (always; the cloud is built, nothing rendered):
    reflections=True gives each volume one stand-in: camera and shadow rays off, out of volume probes, parented to its
        volume; its mesh (Grid to Mesh of the density grid at reflection_density) carries 'nx_source', the medium's
        source function, warm in the cap and grey in the surge; its emission is driven by the effect's opacity
    reflect_in(ball) puts a sphere probe round the ball: near clip at its radius, parallax at the cloud's distance
    remove() takes the stand-ins, the probes and their data out with the rest
Render (unless --no-render; out/reflections/, 480 x 270, 16 samples, view 'Standard', linear EXRs): a chrome ball
(metallic, roughness 0.05) with the cloud behind the camera, so the ball's face reflects it. Against what the ball
should show: the cloud rendered by EEVEE from the ball's centre, looked up along each pixel's reflected ray (x the
metal's reflectance, measured on the ball against the flat world). Without the option the ball shows none of the cloud
(EEVEE's ray tracing and probes draw no volume); with it the error over the pixels that should show the cloud stays
under 35 % of their mean (the probe's picture is softer, filtered by the roughness and by its resolution); the same
render with the sphere probes at 2048 is measured beside it.
out/reflections/reflections_sheet.png: the ball without, with, and the reference (x4 crops);
out/reflections/reflections_look.png: the chrome ball and a brushed one (roughness 0.3) on dark ground at dusk, 960 x 540.

    cd <main checkout> && bash run_blender.sh \
        <worktree>/blender/tests/sdf_volumes/test_volume_reflections.py [--no-render]
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _vcommon as V  # noqa: E402

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.sdf import nuclear_explosion as NX  # noqa: E402
from eidoblend.sdf.examples_volumes import fit_volume_range  # noqa: E402

A = V.args()
RENDER = '--no-render' not in sys.argv
W, H = int(A.get('w', 480)), int(A.get('h', 270))
T = float(A.get('t', 7.5))
OUT = os.path.join(V.OUT, 'reflections')
CACHE = os.path.join(OUT, 'cache')
os.makedirs(OUT, exist_ok=True)
WORLD = 0.01
ORIGIN3 = (-18.0, 0.0, 45.0)            # three's axes: ground zero at Blender (-18, -45, 0), behind the camera, left
BALL_C = Vector((0.0, 0.0, 1.0))
BALL_R = 0.6


def lum(a):
    return a[..., :3] @ np.array([0.2126, 0.7152, 0.0722])


def exr(name):
    return V.render_linear(os.path.join(OUT, name + '.exr'))[..., :3]


def scene_with_ball():
    sc = V.stage(W, H, 16, world=WORLD, sun=0.0, floor=False)
    sc.view_settings.view_transform = 'Standard'
    sc.eevee.use_fast_gi = True
    cam = V.camera((0.0, -3.2, 1.25), tuple(BALL_C), lens=60)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=BALL_R, location=tuple(BALL_C), segments=96, ring_count=48)
    ball = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    m = bpy.data.materials.new('chrome')
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.9, 0.9, 0.9, 1)
    b.inputs['Metallic'].default_value = 1.0
    b.inputs['Roughness'].default_value = 0.05
    ball.data.materials.append(m)
    return sc, cam, ball


def build(sc, cam, reflections):
    nuke = NX.apply_to(sc, cam, {'origin': list(ORIGIN3), 'scale': 1.0, 'quality': 'fast', 'lights': 0,
                                 'reflections': reflections}, cache_dir=CACHE, name='refl_nuke')
    nuke.update(T)
    return nuke


# ---- the option, built ---------------------------------------------------------------------------------------------
sc, cam, ball = scene_with_ball()
nuke = build(sc, cam, True)
probes = nuke.reflect_in([ball])
dg = bpy.context.evaluated_depsgraph_get()
so = nuke.reflection_objects
V.check('one stand-in per volume, for the light probes alone', len(so) == len(nuke.objects) and all(
    not o.visible_camera and not o.visible_shadow and o.hide_probe_volume and o.parent in nuke.objects for o in so),
    ', '.join(o.name for o in so))
cols = {}
for o in so:
    me = o.evaluated_get(dg).data
    at = me.attributes.get('nx_source')
    c = np.zeros(len(me.vertices) * 4, np.float32)
    if at is not None and len(me.vertices):
        at.data.foreach_get('color', c)
    cols[o.parent.get('nuclear_explosion', o.name)] = (len(me.vertices), c.reshape(-1, 4)[:, :3])
detail = '; '.join(f'{k}: {n} vertices, mean source ({", ".join(f"{x:.3f}" for x in c.mean(0))})'
                   for k, (n, c) in cols.items() if n)
V.check("their meshes carry the medium's source function: warm in the cap, grey in the surge",
        all(n > 100 for n, _c in cols.values()) and cols['mushroom'][1].mean(0)[0] > cols['mushroom'][1].mean(0)[2]
        and cols['mushroom'][1].mean(0)[0] > 0.05, detail)
setm = next(n for n in so[0].modifiers['nx_reflection'].node_group.nodes if n.bl_idname == 'GeometryNodeSetMaterial')
mat = setm.inputs['Material'].default_value
em = next(n for n in mat.node_tree.nodes if n.type == 'EMISSION')
V.check("their emission follows the effect's opacity", em.inputs['Strength'].is_linked and
        em.inputs['Strength'].links[0].from_node.node_tree == nuke.opacity_socket.id_data, mat.name)
pd = probes[0].data
d_cloud = (sum((o.matrix_world.translation for o in nuke.objects), Vector()) / len(nuke.objects) - BALL_C).length
V.check('reflect_in: a sphere probe round the ball, the ball out of sphere probes, a 1 cm near clip (the ground it '
        'stands on stays in the picture), its parallax at the cloud',
        pd.type == 'SPHERE' and ball.hide_probe_sphere and pd.clip_start <= 0.011 and pd.use_custom_parallax and
        abs(pd.parallax_distance - d_cloud) < 1.0,
        f'clip {pd.clip_start:.3f} m, influence {pd.influence_distance:.3f} m, parallax {pd.parallax_distance:.1f} m '
        f'(the cloud {d_cloud:.1f} m off)')

if RENDER:
    with_standin = exr('with_reflections')
    for o in so:
        o.hide_render = True
    bare = exr('without_reflections')
    # what the ball should show: the cloud from the ball's centre (EEVEE, the real volume), along each reflected ray
    ball.hide_render = True
    rc = V.camera(tuple(BALL_C), (-18.0, -45.0, 6.0), lens=18, name='refcam')
    sc.camera = rc
    fit_volume_range(sc, rc, nuke.volumes, frames=[sc.frame_current])
    ref_img = exr('reference_view')
    sc.camera = cam
    ball.hide_render = False
    for o in so:
        o.hide_render = False
    cw = cam.matrix_world
    frame = cam.data.view_frame(scene=sc)
    tx, ty = max(abs(v.x) for v in frame) / abs(frame[0].z), max(abs(v.y) for v in frame) / abs(frame[0].z)
    ys, xs = np.mgrid[0:H, 0:W]
    ndx, ndy = ((xs + 0.5) / W) * 2 - 1, 1 - ((ys + 0.5) / H) * 2
    d = (np.array(cw.to_3x3()) @ np.stack([ndx * tx, ndy * ty, -np.ones_like(ndx)], 0).reshape(3, -1)).T
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    o, c = np.array(cw.translation), np.array(BALL_C)
    oc = o - c
    bq = d @ oc
    disc = bq * bq - (oc @ oc - BALL_R * BALL_R)
    hit = disc > 0
    x = o + d * (-bq - np.sqrt(np.maximum(disc, 0)))[:, None]
    n = (x - c) / BALL_R
    r = d - 2 * (d * n).sum(1, keepdims=True) * n
    far = np.c_[c + r * 1000.0, np.ones(len(r))] @ np.linalg.inv(np.array(rc.matrix_world)).T
    rf = rc.data.view_frame(scene=sc)
    rtx, rty = max(abs(v.x) for v in rf) / abs(rf[0].z), max(abs(v.y) for v in rf) / abs(rf[0].z)
    zf = -far[:, 2]
    u = (far[:, 0] / np.maximum(zf, 1e-6) / rtx + 1) * 0.5
    v = (far[:, 1] / np.maximum(zf, 1e-6) / rty + 1) * 0.5
    inside = hit & (zf > 0) & (u > 0) & (u < 1) & (v > 0) & (v < 1)
    pred = np.full((H * W, 3), WORLD)
    iu, iv = np.clip((u * W).astype(int), 0, W - 1), np.clip(((1 - v) * H).astype(int), 0, H - 1)
    pred[inside] = ref_img[iv[inside], iu[inside]]
    face = hit & ((-(d * n).sum(1)) > 0.5)                    # within 60 degrees of facing: no grazing Fresnel
    cloud_px = face & inside & (lum(pred) > 5 * WORLD)
    k = float(np.median((bare.reshape(-1, 3)[face & ~cloud_px] / WORLD).mean(1)))   # the metal's reflectance
    pred = pred * k
    mref = float(pred[cloud_px].mean())
    e_none = float(np.abs(bare.reshape(-1, 3)[cloud_px] - pred[cloud_px]).mean()) / mref
    e_on = float(np.abs(with_standin.reshape(-1, 3)[cloud_px] - pred[cloud_px]).mean()) / mref
    V.check('without the option the ball shows no cloud (no volume in EEVEE ray tracing or probes)', e_none > 0.9,
            f'|error| {e_none * 100:.0f} % of the {int(cloud_px.sum())} cloud pixels\' mean {mref:.4f}')
    V.check('with reflections=True and reflect_in, the ball shows the cloud', e_on < 0.35,
            f'|error| {e_on * 100:.0f} % of their mean (the metal reflects {k:.2f} of the world)')
    # the sphere probe's resolution: the same render with the probes captured at 2048 instead of the scene's own
    res0 = sc.eevee.gi_cubemap_resolution
    sc.eevee.gi_cubemap_resolution = '2048'
    fine = exr('with_reflections_2048')
    sc.eevee.gi_cubemap_resolution = res0
    e_fine = float(np.abs(fine.reshape(-1, 3)[cloud_px] - pred[cloud_px]).mean()) / mref
    print(f'[test_volume_reflections] sphere probes at 2048: |error| {e_fine * 100:.1f} % against '
          f'{e_on * 100:.1f} % at {res0}', flush=True)
    paths = []
    for nm, img in (('without', bare), ('with', with_standin), ('reference', pred.reshape(H, W, 3))):
        p = os.path.join(OUT, f'reflections_{nm}.png')
        V.save_linear_png(p, img[::-1])
        paths.append(p)
    import OpenImageIO as oiio
    crops = []
    for p in paths:
        a = np.asarray(oiio.ImageBuf(p).get_pixels(oiio.UINT8))[95:175, 190:290, :3]
        crops.append(np.repeat(np.repeat(a, 4, 0), 4, 1))
    sheet = np.concatenate(crops, axis=1)
    out = oiio.ImageOutput.create(os.path.join(OUT, 'reflections_sheet.png'))
    out.open(os.path.join(OUT, 'reflections_sheet.png'), oiio.ImageSpec(sheet.shape[1], sheet.shape[0], 3, 'uint8'))
    out.write_image(np.ascontiguousarray(sheet))
    out.close()
    # the look: the chrome ball and a brushed one (roughness 0.3) on dark ground at dusk, 960 x 540, AgX
    world = sc.world.node_tree.nodes['Background']
    world.inputs['Color'].default_value = (0.045, 0.05, 0.065, 1.0)
    bpy.ops.mesh.primitive_plane_add(size=60, location=(0.0, 0.0, BALL_C.z - BALL_R))
    ground = bpy.context.active_object
    gm = bpy.data.materials.new('asphalt')
    gm.use_nodes = True
    gb = gm.node_tree.nodes['Principled BSDF']
    gb.inputs['Base Color'].default_value = (0.035, 0.034, 0.033, 1)
    gb.inputs['Roughness'].default_value = 0.55
    ground.data.materials.append(gm)
    r2 = 0.42
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r2, location=(1.25, 0.55, BALL_C.z - BALL_R + r2), segments=96,
                                         ring_count=48)
    brushed = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    bm = bpy.data.materials.new('brushed')
    bm.use_nodes = True
    bb = bm.node_tree.nodes['Principled BSDF']
    bb.inputs['Base Color'].default_value = (0.75, 0.72, 0.68, 1)
    bb.inputs['Metallic'].default_value = 1.0
    bb.inputs['Roughness'].default_value = 0.3
    brushed.data.materials.append(bm)
    probes += nuke.reflect_in([brushed])
    look_cam = V.camera((0.55, -2.9, 1.35), (0.55, 0.2, 0.85), lens=40, name='lookcam')
    sc.camera = look_cam
    sc.render.resolution_x, sc.render.resolution_y = 960, 540
    sc.view_settings.view_transform = 'AgX'
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_depth = '8'
    V.render(os.path.join(OUT, 'reflections_look.png'))
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.view_settings.view_transform = 'Standard'

names = [o.name for o in so] + [p.name for p in probes]
nuke.remove()
left = [nm for nm in names if nm in bpy.data.objects] + [g for g in bpy.data.node_groups if g.name.endswith('_reflection')]
V.check('remove() takes the stand-ins and the probes out, and gives the ball its sphere-probe visibility back',
        not left and 'refl_nuke_reflection' not in bpy.data.materials and not ball.hide_probe_sphere, f'left: {left}')
# the post registry's native build and undo, with the option
NX.native_build(sc, {'origin': list(ORIGIN3), 'scale': 1.0, 'quality': 'fast', 'lights': 0, 'reflections': True,
                     'bake': (1, 1), 'name': 'refl_native', 'cache_dir': CACHE})
made = list(sc.get(NX.NATIVE_KEY, []))
NX.native_undo(sc)
left = ([n for n in made if n in bpy.data.objects] + [g.name for g in bpy.data.node_groups if 'refl_native' in g.name]
        + [m.name for m in bpy.data.materials if 'refl_native' in m.name])
V.check("the registry's native build lists the stand-ins, and its undo leaves nothing",
        any(n.endswith('_reflection') for n in made) and not left, f'{len(made)} made, left: {left}')
V.summary()

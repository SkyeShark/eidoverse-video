"""t_motion.py: does EEVEE's Vector pass see the flora's wind and pushers? (needed for DLSS 5's temporal path)

Builds a grass + daisy patch with a pusher sweeping through it, renders frame F's Vector pass through a compositor File
Output node (Blender 5.2 keeps passes out of the render's own EXR), and compares it with the motion of the field's
evaluated vertices projected to the screen between F-1, F and F+1. Then the control: the same frame with the wind and
the pusher switched off must give (near) zero vectors. Writes out/motion_beauty_fF.png, out/motion_vec_fF.png
(|vector| as grey), out/motion_vec_still_fF.png, and prints the numbers.
    bash run_blender.sh blender/tests/flora/t_motion.py [--frame 24]
"""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
import OpenImageIO as oiio  # noqa: E402
from eidoblend.flora import create_flora, reset_flora_occupancy  # noqa: E402

F = int(S.arg('--frame', '24'))
W, H = 960, 540
sc = S.new_scene((W, H), samples=4)
sc.frame_start, sc.frame_end = 1, 48
S.lights(sun_elev_deg=40, sun_az_deg=-50, strength=4.5)
S.ground()
reset_flora_occupancy()
grass = create_flora('grass', size=8, seed=3, height=0.45)
daisy = create_flora('daisy', size=5, seed=5, center=(0.3, 0.8), density=0.5, color='white')
# a pusher sweeping across the patch, 2 m/s along x at y = 0.6
walker = bpy.data.objects.new('walker', None)
sc.collection.objects.link(walker)
bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
for f, x in ((1, -2.4), (48, 2.4)):
    walker.location = (x, 0.6, 0.0)
    walker.keyframe_insert('location', frame=f)
grass.set_pushers([walker], radius=0.7)
cam = S.camera((0.0, -3.2, 1.1), (0.0, 0.8, 0.15), 35)

# the Vector pass leaves through the compositor
for vl in sc.view_layers:
    vl.use_pass_vector = True
sc.render.use_motion_blur = False
sc.render.use_compositing = True
tree = bpy.data.node_groups.new('flora_vec', 'CompositorNodeTree')
sc.compositing_node_group = tree
rl = tree.nodes.new('CompositorNodeRLayers')
fo = tree.nodes.new('CompositorNodeOutputFile')
tmp = os.path.join(S.OUT, '_vec')
os.makedirs(tmp, exist_ok=True)
fo.directory = tmp
fo.file_name = 'vec'
fo.save_as_render = False
fo.format.media_type = 'MULTI_LAYER_IMAGE'
fo.format.file_format = 'OPEN_EXR_MULTILAYER'
fo.format.color_depth = '32'
fo.file_output_items.new('VECTOR', 'Vector')
tree.links.new(rl.outputs['Vector'], fo.inputs['Vector'])


def render_vectors(tag):
    for old in glob.glob(os.path.join(tmp, '*')):
        os.remove(old)
    sc.frame_set(F)
    sc.render.filepath = os.path.join(S.OUT, f'motion_beauty{tag}_f{F}.png')
    bpy.ops.render.render(write_still=True)
    files = glob.glob(os.path.join(tmp, '*.exr'))
    if len(files) != 1:
        raise SystemExit(f'[motion] expected one EXR, got {files}')
    buf = oiio.ImageBuf(files[0])
    names = list(buf.spec().channelnames)
    px = buf.get_pixels(oiio.FLOAT)
    vec = [n for n in names if 'Vector' in n]
    order = sorted(vec, key=lambda n: 'XYZW'.index(n.split('.')[-1].upper()) if n.split('.')[-1].upper() in 'XYZW' else 'RGBA'.index(n.split('.')[-1].upper()))
    v = np.zeros(px.shape[:2] + (4,), np.float32)                    # (H, W, 4), rows top-down
    for i, n in enumerate(order[:4]):
        v[..., i] = px[..., names.index(n)]
    print(f'[motion] {tag or "wind"}: channels {order}')
    return v


def save_mag(v, path, vmax):
    mag = np.clip(np.hypot(v[..., 0], v[..., 1]) / vmax, 0, 1)
    im = bpy.data.images.new(os.path.basename(path), W, H, alpha=False)
    rgba = np.ones((H, W, 4), np.float32)
    rgba[..., 0] = rgba[..., 1] = rgba[..., 2] = mag[::-1]          # Blender images are bottom-up
    im.pixels.foreach_set(rgba.ravel())
    im.filepath_raw = path
    im.file_format = 'PNG'
    im.save()


def projected(frame):
    sc.frame_set(frame)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = grass.object.evaluated_get(dg)
    me = ev.to_mesh()
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32)
    me.vertices.foreach_get('co', co)
    aH = np.empty(n, np.float32)
    me.attributes['aH'].data.foreach_get('value', aH)
    ev.to_mesh_clear()
    co = co.reshape(-1, 3).astype(np.float64)
    P = np.array(cam.calc_matrix_camera(dg, x=W, y=H) @ cam.matrix_world.inverted())
    h = np.c_[co, np.ones(n)] @ P.T
    ndc = h[:, :2] / h[:, 3:4]
    pix = np.c_[(ndc[:, 0] * 0.5 + 0.5) * W, (ndc[:, 1] * 0.5 + 0.5) * H]
    return pix, aH, h[:, 3]


v = render_vectors('')
pa, aH, wz = projected(F - 1)
pb, _, _ = projected(F)
pc, _, _ = projected(F + 1)
inside = (pb[:, 0] > 0) & (pb[:, 0] < W) & (pb[:, 1] > 0) & (pb[:, 1] < H) & (wz > 0) & (aH > 0.6)
d_prev = np.hypot(*(pb - pa)[inside].T)
d_next = np.hypot(*(pc - pb)[inside].T)
mag_xy = np.hypot(v[..., 0], v[..., 1])
mag_zw = np.hypot(v[..., 2], v[..., 3])
moving = mag_xy > 0.02
print(f'[motion] geometry: blade tips in frame {inside.sum()}, screen motion F-1->F median {np.median(d_prev):.3f} px, '
      f'p90 {np.percentile(d_prev, 90):.3f}; F->F+1 median {np.median(d_next):.3f} px, p90 {np.percentile(d_next, 90):.3f}')
print(f'[motion] Vector pass: {moving.mean() * 100:.1f}% of pixels move; XY median over moving {np.median(mag_xy[moving]) if moving.any() else 0:.3f} px, '
      f'p90 {np.percentile(mag_xy[moving], 90) if moving.any() else 0:.3f}; ZW median {np.median(mag_zw[mag_zw > 0.02]) if (mag_zw > 0.02).any() else 0:.3f} px; '
      f'max {mag_xy.max():.2f} px')
vmax = max(1e-3, float(np.percentile(mag_xy[moving], 99)) if moving.any() else 1.0)
save_mag(v, os.path.join(S.OUT, f'motion_vec_f{F}.png'), vmax)

# control: wind and pusher off -> the Vector pass must go still
for f in (grass, daisy):
    f.set_wind(sway=0.0, gust=0.0, flutter=0.0)
grass.set_pushers([])
v0 = render_vectors('_still')
m0 = np.hypot(v0[..., 0], v0[..., 1])
print(f'[motion] control (wind + pusher off): {(m0 > 0.02).mean() * 100:.2f}% of pixels move, max {m0.max():.3f} px')
save_mag(v0, os.path.join(S.OUT, f'motion_vec_still_f{F}.png'), vmax)
for old in glob.glob(os.path.join(tmp, '*')):
    os.remove(old)
os.rmdir(tmp)
print('[motion] done')

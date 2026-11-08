"""Wind: the shared "SeedThree Wind" group deforms the tree over time, the leaves
stay on their twigs, and EEVEE writes real motion vectors for it.

    bash run_blender.sh blender/tests/trees/wind_probe.py

Renders the meadow oak (static camera) at frames 1 and 24 at JS default wind
(strength 0.5, speed 1), writes both beauty frames, a frame-difference image, a
close crop of twig/leaf attachment at frame 24, and reads the Vector pass (via a
compositor File Output node) to measure per-pixel motion on the canopy vs the
static ground.
"""

import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from eidoblend.trees import make_seed_tree  # noqa: E402
from meadow_oak_design import MEADOW_OAK, SEED  # noqa: E402

VEC_DIR = os.path.join(S.OUT, '_wind_vec')


def vector_setup(scene):
    for vl in scene.view_layers:
        vl.use_pass_vector = True
    scene.render.use_compositing = True
    scene.render.use_motion_blur = False
    tree = bpy.data.node_groups.new('wind vec', 'CompositorNodeTree')
    scene.compositing_node_group = tree
    rl = tree.nodes.new('CompositorNodeRLayers')
    fo = tree.nodes.new('CompositorNodeOutputFile')
    fo.directory = VEC_DIR
    fo.file_name = 'vec'
    fo.save_as_render = False
    fo.format.media_type = 'MULTI_LAYER_IMAGE'
    fo.format.file_format = 'OPEN_EXR_MULTILAYER'
    fo.format.color_depth = '32'
    fo.file_output_items.new('VECTOR', 'Vector')
    tree.links.new(rl.outputs['Vector'], fo.inputs['Vector'])
    # the beauty still still comes from the render itself
    comp = tree.nodes.new('CompositorNodeComposite') if hasattr(bpy.types, 'CompositorNodeComposite') else None
    if comp is not None:
        tree.links.new(rl.outputs['Image'], comp.inputs['Image'])


def read_vector():
    import OpenImageIO as oiio
    files = glob.glob(os.path.join(VEC_DIR, 'vec*'))
    buf = oiio.ImageBuf(files[0])
    names = list(buf.spec().channelnames)
    px = buf.get_pixels(oiio.FLOAT)
    ch = [i for i, n in enumerate(names) if 'Vector' in n]
    for f in files:
        os.remove(f)
    return px[..., ch], names


def main():
    scene = S.reset()
    S.render_settings(scene)
    oak = make_seed_tree(species='whiteOak', seed=SEED, dials=MEADOW_OAK, location=(0, 0, 0))
    make_seed_tree.set_wind(strength=0.5, speed=1.0)
    S.ground(scene, oak['api'].ASSETS_DIR, 'grass', tile=3.0)
    sun, _ = S.sky_and_sun(scene, 40, 215, strength=0.10, sun_strength=4.0)
    make_seed_tree.set_sun(sun)
    make_seed_tree.light_probe(oak)
    S.camera(scene, (24, -28, 1.6), (0, 0, 6.4), lens=32)
    vector_setup(scene)
    os.makedirs(VEC_DIR, exist_ok=True)
    frames = {}
    for f in (1, 24):
        scene.frame_set(f)
        S.render(scene, os.path.join(S.OUT, 'wind_f%02d.png' % f))
        vec, names = read_vector()
        frames[f] = vec
        mag = np.linalg.norm(vec[..., :2], axis=-1)
        h = mag.shape[0]
        # image rows: OIIO is top row first; the canopy is the upper half, the ground the lower fifth
        canopy, ground = mag[: h // 2], mag[int(h * 0.8):]
        print('[trees] frame %d Vector channels %s: canopy px moving >0.05 px: %.1f%%, canopy max %.2f px; '
              'ground max %.3f px' % (f, names, 100 * (canopy > 0.05).mean(), canopy.max(), ground.max()))
    from PIL import Image
    a = np.asarray(Image.open(os.path.join(S.OUT, 'wind_f01.png')).convert('RGB')).astype(np.int16)
    b = np.asarray(Image.open(os.path.join(S.OUT, 'wind_f24.png')).convert('RGB')).astype(np.int16)
    d = np.clip(np.abs(a - b).sum(-1) * 3, 0, 255).astype(np.uint8)
    Image.fromarray(d).save(os.path.join(S.OUT, 'wind_diff_f01_f24.png'))
    print('[trees] frame 1 vs 24: %.1f%% of pixels changed' % (100 * (d > 6).mean()))
    # attachment close-up at frame 24: leaves must still sit on their twigs
    scene.render.use_compositing = False   # the Vector File Output is done
    scene.frame_set(24)
    S.camera(scene, (6.5, -5.0, 3.2), (3.0, -1.0, 5.0), lens=50, name='close cam')
    S.render(scene, os.path.join(S.OUT, 'wind_f24_attach.png'))
    try:
        os.rmdir(VEC_DIR)
    except OSError:
        pass


main()

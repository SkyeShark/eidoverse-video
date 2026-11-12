"""The stock finish's pattern fades against the WebGPU's fwidth(phase), measured in renders, on both stocks.

The WebGPU finishStock faded the growth rings, the wood fibre and the metal brushing by fwidth(phase): the phase's
change from one pixel to the next on screen. finish_stock (eidoblend.fabrication.cutting) computes that derivative from
each pattern's 3D gradient and the pixel's footprint on the surface, for the 2.5D stock's axes ('bed') and the rotary
stock's ('rotary') alike. This renders, each with AOVs of every pattern's phase and its exact fwidth (the nodes
finish_stock names 'phase <pattern>' and 'fwidth <pattern>'):

    rotary   the finished rotary sample part in wood, an aluminium copy below it, from the examples' camera distance
             (640 x 450, the kit's vertical-fit camera)
    bed      the sample relief carved in wood (a heightfield mesh in stock coordinates), an aluminium copy beside it,
             made and evaluated before the scene has any camera; frame 1 through the kit's camera from a
             three-quarter view, then a marker cuts to a plain Blender camera (sensor fit AUTO, 50 mm) that holds
             the parts off the frame's centre at frame 2 (960 x 540)

then takes each phase image's real pixel differences |dP/dx| + |dP/dy| (what fwidth is) and compares. Prints PASS /
FAIL and the distributions; writes out/footprint/ (the AOVs, the beauty frames).

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \\
        <worktree>/blender/tests/fabrication/test_finish_footprint.py
"""

import os
import shutil
import sys

import bpy
import numpy as np
from mathutils import Vector

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util as U  # noqa: E402

from eidoblend.characters.robotics.studio import make_camera  # noqa: E402
from eidoblend import fabrication as fab  # noqa: E402
from eidoblend.fabrication.cutting import stock_material, stock_profile  # noqa: E402
from eidoblend.fabrication.rotary import create_rotary_stock, rotary_program, sample_rotary  # noqa: E402

OUT = os.path.join(U.OUT, 'footprint')
shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT, exist_ok=True)
PATTERNS = (('growth rings', .28), ('wood fibre', .3), ('metal brushing', .25))


def aov(mat):
    """an AOV per pattern of the material: (phase, fwidth, 0)"""
    nt = mat.node_tree
    for pattern, _k in PATTERNS:
        if 'phase ' + pattern not in nt.nodes:
            continue
        comb = nt.nodes.new('ShaderNodeCombineXYZ')
        nt.links.new(nt.nodes['phase ' + pattern].outputs[0], comb.inputs[0])
        nt.links.new(nt.nodes['fwidth ' + pattern].outputs[0], comb.inputs[1])
        out = nt.nodes.new('ShaderNodeOutputAOV')
        out.aov_name = 'fp_' + pattern.replace(' ', '_')
        nt.links.new(comb.outputs[0], out.inputs['Color'])


def fresh_scene(name, size):
    """the scene emptied (no camera left), set to render the AOVs at `size`"""
    sc = bpy.context.scene
    for ob in list(sc.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    sc.timeline_markers.clear()
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = size[0], size[1], 100
    sc.eevee.taa_render_samples = 4
    sc.render.filter_size = 0.5
    sc.world = bpy.data.worlds.new(name + ' world')
    sc.world.color = (0.05, 0.05, 0.05)
    sun = bpy.data.objects.new(name + ' sun', bpy.data.lights.new(name + ' sun', 'SUN'))
    sun.data.energy = 3.0
    sun.rotation_euler = (0.7, 0.2, 0.5)
    sc.collection.objects.link(sun)
    vl = sc.view_layers[0]
    for pattern, _k in PATTERNS:
        if 'fp_' + pattern.replace(' ', '_') not in [a.name for a in vl.aovs]:
            a = vl.aovs.add()
            a.name, a.type = 'fp_' + pattern.replace(' ', '_'), 'COLOR'
    return sc


def render(sc, tag, frame=1):
    ctree = bpy.data.node_groups.new(tag + ' footprint comp', 'CompositorNodeTree')
    sc.compositing_node_group = ctree
    rl = ctree.nodes.new('CompositorNodeRLayers')
    fo = ctree.nodes.new('CompositorNodeOutputFile')
    fo.directory = OUT + '/'
    fo.file_name = tag + '_####_'
    fo.save_as_render = False
    fo.format.media_type = 'IMAGE'
    fo.format.file_format = 'OPEN_EXR'
    fo.format.color_depth = '32'
    for pattern, _k in PATTERNS:
        n = 'fp_' + pattern.replace(' ', '_')
        fo.file_output_items.new('RGBA', n)
        ctree.links.new(rl.outputs[n], fo.inputs[n])
    sc.render.image_settings.media_type = 'IMAGE'
    sc.render.image_settings.file_format = 'PNG'
    sc.render.filepath = os.path.join(OUT, f'{tag}_beauty.png')
    sc.frame_set(frame)
    bpy.ops.render.render(write_still=True)
    return sc.camera


def load(tag, name, size):
    w, h = size
    hits = sorted(f for f in os.listdir(OUT) if f.startswith(tag + '_') and name in f and f.endswith('.exr'))
    if not hits:
        return None
    img = bpy.data.images.load(os.path.join(OUT, hits[0]))
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)[::-1].astype(np.float64)


def measure(tag, size):
    for pattern, fade in PATTERNS:
        a = load(tag, 'fp_' + pattern.replace(' ', '_'), size)
        if a is None:
            U.check(f'{tag} {pattern}: AOV written', False)
            continue
        phase, exact = a[..., 0], a[..., 1]
        on = np.abs(phase) > 1e-3
        inner = on.copy()                                  # two pixels clear of every silhouette
        for dy in (-2, -1, 0, 1, 2):
            for dx in (-2, -1, 0, 1, 2):
                inner &= np.roll(np.roll(on, dy, 0), dx, 1)
        fd = np.abs(np.roll(phase, -1, 1) - phase) + np.abs(np.roll(phase, -1, 0) - phase)
        ok = inner & (fd > 1e-3)
        ok[-2:, :] = ok[:, -2:] = False
        if ok.sum() < 2000:
            U.check(f'{tag} {pattern}: enough pixels', False, f'{ok.sum()}')
            continue
        r = exact[ok] / fd[ok]
        p = np.percentile(r, (10, 50, 90))
        within = np.mean(np.abs(r - 1) < .25)
        kept_true = (1 - np.clip(fd[ok] * fade, 0, 1)).mean()
        kept_exact = (1 - np.clip(exact[ok] * fade, 0, 1)).mean()
        print(f'[{tag}] {pattern}: {ok.sum()} pixels; exact / measured fwidth p10 {p[0]:.3f} p50 {p[1]:.3f} p90 '
              f'{p[2]:.3f}; mean share of the pattern kept: measured {kept_true:.3f}, exact {kept_exact:.3f}',
              flush=True)
        U.check(f"{tag} {pattern}: the exact fwidth matches the rendered phase's pixel differences (median within 10 %, "
                '75 % of pixels within 25 %)', abs(p[1] - 1) < .10 and within > .75,
                f'median {p[1]:.3f}, {within * 100:.1f} % within 25 %')
        U.check(f'{tag} {pattern}: so the pattern keeps the share of its contrast the WebGPU kept (within 0.05)',
                abs(kept_exact - kept_true) < .05, f'{kept_exact:.3f} vs {kept_true:.3f}')


def aim(cam, eye, target):
    cam.rotation_mode = 'QUATERNION'
    cam.location = Vector(eye)
    cam.rotation_quaternion = (Vector(target) - Vector(eye)).to_track_quat('-Z', 'Y')
    cam.data.clip_start, cam.data.clip_end = .02, 10.0
    return cam


def kit_camera(sc, eye, target, lens=36):
    """the kit's camera (vertical sensor fit, three's fov), made the scene's"""
    cam = aim(make_camera(lens, sc.name + ' camera', sc), eye, target)
    sc.camera = cam
    return cam


def measured_footprint_only(mat):
    """the finish reads its pixel footprint in the shader: no driver on a camera anywhere in its tree"""
    ad = mat.node_tree.animation_data
    drivers = list(ad.drivers) if ad else []
    on_camera = [fc.data_path for fc in drivers for v in fc.driver.variables for t in v.targets
                 if t.id_type in ('CAMERA', 'OBJECT') or 'camera' in (t.data_path or '')]
    return 'pixel footprint' in mat.node_tree.nodes and not on_camera, on_camera


# ------------------------------------------------------------------------------------------------ rotary ---
ROTARY = (640, 450)
sc = fresh_scene('rotary footprint', ROTARY)
program = rotary_program(sample_rotary, material='wood', tool='flat')
frame = bpy.data.objects.new('Rotary stock frame', None)
sc.collection.objects.link(frame)
kit_camera(sc, (-.325, -.48, .22), (0, 0, 0))
bpy.context.view_layer.update()
stock = create_rotary_stock(program.path, program.settings, parent=frame, resolution=(192, 72, 72),
                            cache_dir=os.path.join(OUT, 'cache'), collection=sc.collection)
stock.update(program.path.sample(program.path.duration))
stock.write_frame(1)
wood = stock.material
alu, _f = stock_material('aluminium part', stock_profile('aluminum'), axes='rotary')
metal = stock.to_mesh('aluminium copy', link=False)
sc.collection.objects.link(metal)
metal.data.materials.clear()
metal.data.materials.append(alu)
metal.parent = frame
metal.matrix_parent_inverse.identity()
metal.location = (0, 0, -.062)
U.check("the rotary stock's finish reads its axes with the exact fades built in, its footprint measured in the shader",
        all(n in wood.node_tree.nodes for n in ('fwidth growth rings', 'fwidth wood fibre'))
        and 'fwidth metal brushing' in alu.node_tree.nodes and measured_footprint_only(wood)[0])
aov(wood)
aov(alu)
render(sc, 'rotary')
measure('rotary', ROTARY)

# ------------------------------------------------------------------------------------------------ bed ---
BED = (960, 540)
sc = fresh_scene('bed footprint', BED)
cols, rows = 196, 320
xs, ys = (np.arange(cols) / (cols - 1) - .5) * .078, (np.arange(rows) / (rows - 1) - .5) * .128
X, Y = np.meshgrid(xs, ys)
Z = np.vectorize(fab.sample_relief)(X, Y)
verts = np.stack([X, Y, Z], -1).reshape(-1, 3)
faces = [(j * cols + i, j * cols + i + 1, (j + 1) * cols + i + 1, (j + 1) * cols + i)
         for j in range(rows - 1) for i in range(cols - 1)]
parts = []
for name, profile, dx in (('relief wood', 'wood', -.045), ('relief aluminium', 'aluminum', .045)):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts.tolist(), [], faces)
    me.shade_smooth()
    mat, _f = stock_material(name + ' finish', stock_profile(profile))          # axes='bed', the 2.5D stock's
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    ob.location = (dx, 0, 0)
    sc.collection.objects.link(ob)
    parts.append(mat)
    aov(mat)
# the stock made and evaluated with no camera in the scene (a scene-camera driver would be switched off for good here)
sc.frame_set(1)
bpy.context.view_layer.update()
ok_wood, on_cam = measured_footprint_only(parts[0])
U.check("the 2.5D stock's finish has the same exact fades ('bed' axes), its footprint measured in the shader (no "
        f'camera driver: {on_cam})', ok_wood and measured_footprint_only(parts[1])[0]
        and all(n in parts[0].node_tree.nodes for n in ('fwidth growth rings', 'fwidth wood fibre'))
        and 'fwidth metal brushing' in parts[1].node_tree.nodes, f'scene camera at evaluation: {sc.camera}')
cam_a = kit_camera(sc, (-.17, -.24, .21), (0, 0, .01))
# a plain Blender camera (sensor fit AUTO: the 36 mm sensor width fits the 16:9 frame), cut to by a marker, the parts
# held off the frame's centre
cd = bpy.data.cameras.new('cut camera')
cd.lens = 50.0
cam_b = bpy.data.objects.new('cut camera', cd)
sc.collection.objects.link(cam_b)
aim(cam_b, (.19, -.21, .16), (-.03, .02, .012))
for f, c in ((1, cam_a), (2, cam_b)):
    m = sc.timeline_markers.new(f'shot {f}', frame=f)
    m.camera = c
used = render(sc, 'bed', 1)
measure('bed', BED)
cut = render(sc, 'cut', 2)
U.check(f'frame 2 renders through the marker\'s camera ({cut.name}, sensor fit {cut.data.sensor_fit}, '
        f'{cut.data.lens:.0f} mm; frame 1 through {used.name})', cut == cam_b and used == cam_a)
measure('cut', BED)
ok = U.summary('finish_footprint')
print('ALL PASS' if ok else 'FAIL')

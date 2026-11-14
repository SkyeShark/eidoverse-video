"""The engine's own SDF check scenes and smoke tests, rebuilt in EEVEE and set beside the frames the engine rendered.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sdf/test_engine_check_scenes.py
    (a GPU job: 4 GB VRAM, 12 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

The WebGL engine kept regression scenes for its SDF examples with the frames it rendered (three.js, ACES tone
mapping): reference renders that live outside this repo, read from the folder $EIDO_ENGINE_CHECK_DIR names (hdri.hdr,
<scene>_frame.jpg). Two use this step's examples:
  sdf_hege_closeup    Mr. Hege's jacket close up, under the city HDRI, a 1.4 key light from (5, 9, 4), a grey
                      ground (roughness 0.3, metalness 0.2) at y = -1.35, a 28 degree camera 2.4 m from (0, 0.3, 0)
  sdf_all_examples    Mr. Hege and the red shoggoth (and two sedans, the vehicles step's) on that ground, the camera
                      at (0, 3.5, 14) looking at (0, 0.4, 0), 38 degrees (blender/tests/sdf_vehicles/
                      test_vehicles_check_scenes.py rebuilds this scene with the sedans, and the engine's ten other
                      vehicle check scenes, the SDF + GLB + VRM + underwater smoke test among them)
Each is rebuilt from the scene script's numbers, converted to Blender's axes, with the examples placed by the
engine's own rule (bounds.min on the ground), and rendered in EEVEE under AgX. out/engine_<scene>.png: EEVEE left,
the engine's frame right. The engine's SDF shade() lit itself with hand lights and the HDRI; here the scene's sun
and HDRI light the baked materials, and the tone curve is AgX, not ACES. PASS lines: the scenes build and render;
in sdf_all_examples the red skin (Mr. Hege's head and tentacles, the shoggoth, and their reflections) stands where
the engine drew it, at the same size (centre within 25 px, pixel count within a factor of two).
The engine's two screen smoke tests come too, their frames read from the folder above that one:
sdf_tex_smoketest/preview.jpg (the four recipes on a wall of monitors) and sdf_explosion_smoketest/v_t2.5s.jpg (the
detonation on an unlit plane); their PASS lines hold each screen's brightness, and the
detonation's sky, to the engine's frame, which the default encoding (the engine's sRGB render target) reproduces.
out/engine_tex_smoketest.png: EEVEE, the engine's frame, and EEVEE with encoding='srgb' (darker: the shader's values
read as display colours). out/engine_explosion_smoketest.png: EEVEE beside the engine.
Needs those reference renders (read only); without $EIDO_ENGINE_CHECK_DIR the test prints SKIP.
"""

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend import sdf  # noqa: E402

sys.path.insert(0, os.path.dirname(C.HERE))
import _where  # noqa: E402

CHECK = _where.external('EIDO_ENGINE_CHECK_DIR', "the WebGL engine's SDF check scenes (hdri.hdr and the frames it "
                        "rendered, <scene>_frame.jpg)")
HDRI = os.path.join(CHECK, 'hdri.hdr') if CHECK else None
W, H = 960, 540
CACHE = os.path.join(C.OUT, 'cache_engine_scenes')


def three(x, y, z):
    return (x, -z, y)


def engine_stage(ground=60.0):
    """The scenes' shared setup: the HDRI as world and background, the key light, the ground (its size as in the
    scene: its far edge shows against the HDRI)."""
    sc = C.stage(W, H, 32, floor=False, sun=False)
    w = sc.world
    nt = w.node_tree
    env = nt.nodes.new('ShaderNodeTexEnvironment')
    env.image = bpy.data.images.load(HDRI, check_existing=True)
    nt.links.new(env.outputs['Color'], nt.nodes['Background'].inputs['Color'])
    nt.nodes['Background'].inputs['Strength'].default_value = 1.0
    # DirectionalLight(0xffffff, 1.4) at (5, 9, 4) aimed at the origin: three's physical lights and a Blender sun
    # share the units (radiance = albedo * irradiance * N.L / pi)
    ld = bpy.data.lights.new('key', 'SUN')
    ld.energy = 1.4
    ld.angle = math.radians(0.5)
    ob = bpy.data.objects.new('key', ld)
    sc.collection.objects.link(ob)
    ob.rotation_euler = Vector(three(5.0, 9.0, 4.0)).normalized().to_track_quat('Z', 'Y').to_euler()
    me = bpy.data.meshes.new('ground')
    h = 0.5 * ground
    me.from_pydata([(-h, -h, -1.35), (h, -h, -1.35), (h, h, -1.35), (-h, h, -1.35)], [], [(0, 1, 2, 3)])
    g = bpy.data.objects.new('ground', me)
    sc.collection.objects.link(g)
    m = bpy.data.materials.new('ground')
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.2158, 0.2158, 0.2158, 1.0)       # 0x808080, linear
    b.inputs['Roughness'].default_value = 0.3
    b.inputs['Metallic'].default_value = 0.2
    me.materials.append(m)
    return sc


def camera(pos3, target3, fov_v_deg):
    cam = C.camera(three(*pos3), three(*target3))
    cam.data.sensor_fit = 'VERTICAL'
    cam.data.angle_y = math.radians(fov_v_deg)
    return cam


def place(name, pos3, **kw):
    """createSdfObject(EXAMPLES.x) at position.y = groundY - bounds.min.y (the engine's rule)."""
    o = sdf.EXAMPLES[name].make(name=f'engine_{name}', cache_dir=CACHE, location=three(*pos3), log=None, **kw)
    return o


def engine_frame(fname):
    import OpenImageIO as oiio
    buf = oiio.ImageBuf(os.path.join(CHECK, fname))
    small = oiio.ImageBufAlgo.resize(buf, roi=oiio.ROI(0, W, 0, H, 0, 1, 0, 3))
    return np.asarray(small.get_pixels(oiio.FLOAT))[..., :3]


def save_rgb(path, a):
    import OpenImageIO as oiio
    data = np.ascontiguousarray((np.clip(a, 0.0, 1.0) * 255 + 0.5).astype(np.uint8))
    out = oiio.ImageOutput.create(path)
    out.open(path, oiio.ImageSpec(data.shape[1], data.shape[0], 3, 'uint8'))
    out.write_image(data)
    out.close()
    return path


def read_rgb(path):
    import OpenImageIO as oiio
    return np.asarray(oiio.ImageBuf(path).get_pixels(oiio.FLOAT))[..., :3]


if HDRI is None or not os.path.exists(HDRI):
    print(f'SKIP engine check scenes: {HDRI} is not there' if HDRI else
          'SKIP engine check scenes: no check-scene folder (EIDO_ENGINE_CHECK_DIR)', flush=True)
    C.summary()
    sys.exit(0)

# ============================================================================== sdf_hege_closeup =================
sc = engine_stage(ground=20.0)
hege = place('mr_hege', (0.0, -1.35 + 1.40, 0.0))
T_CLOSE = 1.2                                         # renderFrame(t): the kept frame's view (its background)
a = -0.5 + T_CLOSE * 0.18
camera((2.4 * math.cos(a), 0.4 + math.sin(T_CLOSE * 0.3) * 0.1, 2.4 * math.sin(a)), (0.0, 0.3, 0.0), 28.0)
p = os.path.join(C.OUT, '_engine_hege_closeup_eevee.png')
C.check('sdf_hege_closeup: renders', C.render(p), p)
eng = engine_frame('sdf_hege_closeup_frame.jpg')
save_rgb(os.path.join(C.OUT, '_engine_hege_closeup_engine.png'), eng)
C.sheet([p, os.path.join(C.OUT, '_engine_hege_closeup_engine.png')], os.path.join(C.OUT, 'engine_hege_closeup.png'),
        cols=2)

# ============================================================================== sdf_all_examples ==================
sc = engine_stage()
cam = camera((0.0, 3.5, 14.0), (0.0, 0.4, 0.0), 38.0)
hege = place('mr_hege', (-5.0, -1.35 + 1.40, 0.0))
shog = place('red_shoggoth', (-2.5, -1.35 + 1.10, 0.0))
p = os.path.join(C.OUT, '_engine_all_examples_eevee.png')
C.check('sdf_all_examples (Mr. Hege and the shoggoth): renders', C.render(p), p)
eng = engine_frame('sdf_all_examples_frame.jpg')
save_rgb(os.path.join(C.OUT, '_engine_all_examples_engine.png'), eng)


def red(img):
    """The red skin (Mr. Hege's head and tentacles, the shoggoth) and its reflection, on the frame's left half
    (the right half holds the engine's sedans)."""
    a = img[:, :W // 2]
    return (a[..., 0] - a[..., 1:].max(axis=-1)) > 0.15


mine, theirs = red(read_rgb(p)), red(eng)
ys, xs = np.nonzero(mine)
ye, xe = np.nonzero(theirs)
ok = len(xs) > 500 and len(xe) > 500
if ok:
    d = math.hypot(xs.mean() - xe.mean(), ys.mean() - ye.mean())
    ok = d < 25 and 0.5 < len(xs) / len(xe) < 2.0
C.check('sdf_all_examples: the red skin stands where the engine drew it, at its size', ok,
        f'red pixels {len(xs)} (EEVEE) / {len(xe)} (engine), centres ({xs.mean():.0f}, {ys.mean():.0f}) / '
        f'({xe.mean():.0f}, {ye.mean():.0f})' if len(xs) and len(xe) else 'no red pixels')
C.sheet([p, os.path.join(C.OUT, '_engine_all_examples_engine.png')],
        os.path.join(C.OUT, 'engine_all_examples.png'), cols=2)

# ============================================================================== the screens' smoke tests ==========
# smoke test sdf_tex_smoketest: the four recipes on a 2 x 2 wall of monitors (512 x 384 textures, MeshStandardMaterial
# with the texture as map and emissiveMap, emissive white at 0.85), a 1.5 key light, background #0a0d18, the camera
# at (0, 0, 5.6) with a 45 degree view; ACES at exposure 1.1 (here AgX, exposure +0.14 stops)
SMOKE = os.path.dirname(CHECK)


def linear(hexrgb):
    c = np.array([(hexrgb >> 16) & 255, (hexrgb >> 8) & 255, hexrgb & 255], float) / 255.0
    return tuple(float(x) for x in np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4))


def plane(name, w, h, loc3, mat):
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2)], [],
                   [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='UVMap')
    for k, c in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
        uv.data[k].uv = c
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = three(*loc3)
    return ob


def dark_stage(w, h, bg_hex, key_energy, key_hex, exposure):
    sc = C.stage(w, h, 16, floor=False, sun=False, world_color=linear(bg_hex), world_strength=1.0)
    sc.view_settings.exposure = exposure
    if key_energy:
        ld = bpy.data.lights.new('key', 'SUN')
        ld.energy = key_energy
        ld.color = linear(key_hex)
        ob = bpy.data.objects.new('key', ld)
        sc.collection.objects.link(ob)
        ob.rotation_euler = Vector(three(2.0, 4.0, 4.0)).normalized().to_track_quat('Z', 'Y').to_euler()
    return sc


tex_frame = os.path.join(SMOKE, 'sdf_tex_smoketest', 'preview.jpg')
if os.path.exists(tex_frame):
    sc = dark_stage(W, H, 0x0a0d18, 1.5, 0xffeedd, math.log2(1.1))
    brass = bpy.data.materials.new('engine_brass')
    brass.use_nodes = True
    bb = brass.node_tree.nodes['Principled BSDF']
    bb.inputs['Base Color'].default_value = (*linear(0xc4a060), 1.0)
    bb.inputs['Metallic'].default_value = 0.85
    bb.inputs['Roughness'].default_value = 0.25
    slots = ((-1.4, 0.85), (1.4, 0.85), (-1.4, -0.85), (1.4, -0.85))
    screens = []
    for (recipe, mode), (x, y) in zip((('mandelbulb', 0.0), ('sierpinski_tetra', 1.0), ('menger_sponge', 2.0),
                                       ('gyroid', 3.0)), slots):
        tex = sdf.make_sdf_texture(recipe=recipe, width=512, height=384, uniforms={'paletteMode': mode},
                                   camera_orbit_radius=2.6, camera_orbit_speed=0.20, name=f'engine_{recipe}',
                                   cache_dir=CACHE)
        tex.update(0.0)
        screens.append(tex)
        plane(f'monitor_{recipe}', 2.4, 1.6, (x, y, 0.0), tex.material(emission_strength=0.85, roughness=0.35,
                                                                      metallic=0.1))
        for nm, (sx, sz, dx, dz) in (('top', (2.48, 0.04, 0.0, 0.82)), ('bottom', (2.48, 0.04, 0.0, -0.82)),
                                     ('left', (0.04, 1.6, -1.22, 0.0)), ('right', (0.04, 1.6, 1.22, 0.0))):
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=three(x + dx, y + dz, -0.02))
            fr = bpy.context.active_object
            fr.scale = (sx, 0.04, sz)
            fr.data.materials.append(brass)
    camera((0.0, 0.0, 5.6), (0.0, 0.0, 0.0), 45.0)
    sc.render.resolution_x, sc.render.resolution_y = 1280 // 2, 720 // 2
    p = os.path.join(C.OUT, '_engine_tex_eevee.png')
    C.check('sdf_tex_smoketest: the four screens render', C.render(p), p)
    import OpenImageIO as oiio
    buf = oiio.ImageBufAlgo.resize(oiio.ImageBuf(tex_frame), roi=oiio.ROI(0, 640, 0, 360, 0, 1, 0, 3))
    eng = np.asarray(buf.get_pixels(oiio.FLOAT))[..., :3]
    save_rgb(os.path.join(C.OUT, '_engine_tex_engine.png'), eng)
    mine = read_rgb(p)
    # the screens' mean brightness, screen by screen, against the engine's frame: the default encoding is the
    # engine's sRGB render target, so its skies come out as bright as the engine's did
    # (rows, columns) inside each screen at 640 x 360: the screens' centres are 108 px either side of the middle
    # and 66 px above and below it, 186 x 124 px each
    boxes = {'mandelbulb': (58, 170, 125, 295), 'sierpinski_tetra': (58, 170, 343, 513),
             'menger_sponge': (191, 302, 125, 295), 'gyroid': (191, 302, 343, 513)}
    def ratios(img):
        return {k: float(img[r0:r1, c0:c1].mean() / max(1e-6, eng[r0:r1, c0:c1].mean()))
                for k, (r0, r1, c0, c1) in boxes.items()}
    r_lin = ratios(mine)
    # the same wall with the screens read as display colours, for comparison
    for tex in screens:
        tex.encoding = 'srgb'
        tex.update(0.0)
    p2 = os.path.join(C.OUT, '_engine_tex_eevee_srgb.png')
    C.render(p2)
    r_srgb = ratios(read_rgb(p2))
    C.check("sdf_tex_smoketest: each screen as bright as the engine drew it (within a factor of 1.6)",
            all(1 / 1.6 < v < 1.6 for v in r_lin.values()),
            'EEVEE / engine mean brightness: ' + ', '.join(f'{k} {v:.2f}' for k, v in r_lin.items()) +
            "; with encoding='srgb': " + ', '.join(f'{k} {v:.2f}' for k, v in r_srgb.items()))
    C.sheet([p, os.path.join(C.OUT, '_engine_tex_engine.png'), p2],
            os.path.join(C.OUT, 'engine_tex_smoketest.png'), cols=3)
else:
    print(f'SKIP sdf_tex_smoketest: {tex_frame} is not on this machine', flush=True)

# smoke test sdf_explosion_smoketest: the detonation (1024 x 1024, its clock at 3 x the film's) on a 4.4 m plane in
# MeshBasicMaterial (the texture, unlit), background #08080c, the camera at (0, 0, 4) with a 45 degree view; the kept
# frame v_t2.5s.jpg is film time 2.5 s, shader time 7.5 s
ex_frame = os.path.join(SMOKE, 'sdf_explosion_smoketest', 'v_t2.5s.jpg')
if os.path.exists(ex_frame):
    sc = dark_stage(512, 512, 0x08080c, 0.0, 0xffffff, 0.0)
    blast = sdf.make_explosion_texture(width=512, height=512, camera_pos=(18, 7, 22), camera_target=(0, 5, 0),
                                       time_scale=3.0, name='engine_blast', cache_dir=CACHE)
    blast.update(2.5)
    m = bpy.data.materials.new('engine_basic')
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n)
    em = nt.nodes.new('ShaderNodeEmission')
    tx = nt.nodes.new('ShaderNodeTexImage')
    tx.image = blast.image
    nt.links.new(tx.outputs['Color'], em.inputs['Color'])
    nt.links.new(em.outputs[0], next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL').inputs['Surface'])
    plane('blast_plane', 4.4, 4.4, (0.0, 0.0, 0.0), m)
    camera((0.0, 0.0, 4.0), (0.0, 0.0, 0.0), 45.0)
    p = os.path.join(C.OUT, '_engine_blast_eevee.png')
    C.check('sdf_explosion_smoketest: the detonation plane renders', C.render(p), p)
    import OpenImageIO as oiio
    buf = oiio.ImageBufAlgo.resize(oiio.ImageBuf(ex_frame), roi=oiio.ROI(0, 512, 0, 512, 0, 1, 0, 3))
    eng = np.asarray(buf.get_pixels(oiio.FLOAT))[..., :3]
    save_rgb(os.path.join(C.OUT, '_engine_blast_engine.png'), eng)
    mine = read_rgb(p)
    sky_m, sky_e = mine[40:120, 40:200].mean(axis=(0, 1)), eng[40:120, 40:200].mean(axis=(0, 1))
    C.check('sdf_explosion_smoketest: the sky as pale as the engine drew it (within 0.12 per channel)',
            float(np.abs(sky_m - sky_e).max()) < 0.12,
            f'upper-left sky {sky_m.round(3).tolist()} (EEVEE) / {sky_e.round(3).tolist()} (engine)')
    C.sheet([p, os.path.join(C.OUT, '_engine_blast_engine.png')], os.path.join(C.OUT, 'engine_explosion_smoketest.png'),
            cols=2)
else:
    print(f'SKIP sdf_explosion_smoketest: {ex_frame} is not on this machine', flush=True)

for f in os.listdir(C.OUT):
    if f.startswith('_engine_'):
        os.remove(os.path.join(C.OUT, f))
C.summary()

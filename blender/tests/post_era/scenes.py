"""tests/post_era/scenes.py: the scenes the era looks, aeropittura and after_image tests photograph, and the plumbing
that renders them once and composites the post over the saved frames. Test dressing, not ports.

  - era_probe: the WebGPU era-looks probe (work/fx_probe/era_new.js, whose renders new_1..5.png are the reference):
    the claudesona (claude_suit_wardrobe.vrm) playing idle on a dark metallic floor, a hemisphere fill and a sun, the
    camera at three (1.2, 1.4, 2.2) looking at (0, 1.1, 0), vertical fov 50, a near-black background.
  - uf_hole: THE HOLE of UNKNOWN FORCE, built by its own port (eidoblend.sets.unknown_force), the claudesona
    dancing on her mark under the closeSing camera: aeropittura's real scene.
  - neon_night: a dark street with neon, lit windows and a sodium lamp, the claudesona dancing: the era looks' night
    presets, and aeropittura's stand-in if THE HOLE does not build.
  - mover: an emissive sphere and a lit cube crossing the frame, for the temporal effects (after_image, echo).
Units: three's light intensities carry over as numbers (a directional light of 2.5 is a 2.5 W/m2 sun; a hemisphere
light's irradiance I x colour is a world of radiance I x colour / pi), and three (x, y, z) is Blender (x, -z, y).
"""
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
WORKTREE = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
MAIN = os.path.abspath(os.path.join(WORKTREE, '..', 'eidoverse-video-prealpha-0.01'))
OUT = os.path.join(HERE, 'out')
REF = os.path.join(MAIN, 'work', 'fx_probe')                 # the WebGPU era-looks probe renders
sys.path.insert(0, os.path.join(WORKTREE, 'blender'))


def args():
    return sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def _code_mtime(test_file):
    import glob
    pkg = os.path.join(WORKTREE, 'blender', 'eidoblend', 'look', 'post')
    files = [test_file, os.path.abspath(__file__), os.path.join(HERE, 'ref_era.py')] + glob.glob(os.path.join(pkg, '*.py'))
    return max(os.path.getmtime(p) for p in files if os.path.exists(p))


def already_done(out_dir, stage, test_file):
    """True when this stage already ran with the code as it is now (its marker is newer than the test, the post
    package and these helpers): a queued duplicate of the same run then exits at once instead of rendering again."""
    marker = os.path.join(out_dir, f'.done_{stage}')
    if os.path.exists(marker) and os.path.getmtime(marker) > _code_mtime(test_file):
        print(f'[post_era] {os.path.basename(test_file)} --stage {stage}: already done with this code, skipped',
              flush=True)
        return True
    return False


def mark_done(out_dir, stage):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f'.done_{stage}'), 'w') as f:
        f.write('done\n')


def arg(a, k, d=None):
    return a[a.index(k) + 1] if k in a else d


def t2b(x, y, z):
    """three (x, y, z) -> Blender (x, -z, y)."""
    return Vector((x, -z, y))


def srgb(h):
    from eidoblend.look.post._graph import hex_lin
    return hex_lin(h)


def new_scene(fps=24, frames=(1, 48), res=(960, 540)):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    sc = bpy.context.scene
    sc.render.fps, sc.render.fps_base = fps, 1.0
    sc.frame_start, sc.frame_end = frames
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    return sc


def camera(scene, pos, aim, fov_v_deg=50.0, name='cam', clip_end=1000.0):
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    scene.collection.objects.link(cam)
    cam.data.sensor_fit = 'VERTICAL'
    cam.data.angle_y = math.radians(fov_v_deg)
    cam.data.clip_start, cam.data.clip_end = 0.05, clip_end
    cam.location = pos
    cam.rotation_euler = (Vector(aim) - Vector(pos)).to_track_quat('-Z', 'Y').to_euler()
    scene.camera = cam
    return cam


def material(name, color, rough=0.5, metal=0.0, emit=None, strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1.0)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if emit is not None:
        b.inputs['Emission Color'].default_value = (*emit, 1.0)
        b.inputs['Emission Strength'].default_value = strength
    return m


def box(scene, name, centre, size, mat):
    import bmesh
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    ob.location = centre
    ob.scale = size
    me.materials.append(mat)
    return ob


def hemisphere_world(scene, sky=(1.0, 1.0, 1.0), ground=(0.0144, 0.0144, 0.0513), intensity=0.8,
                     background=(0.0030, 0.0030, 0.0070)):
    """three's scene.background (a colour: lights nothing there, next to nothing here) as the world, and its
    HemisphereLight(sky, ground, intensity) as two suns 180 degrees wide, one from above in the sky colour and one from
    below in the ground colour: a hemisphere source gives irradiance strength x (1 + cos t) / 2, three's
    mix(ground, sky, 0.5 n.up + 0.5). Diffuse only (specular 0, no shadows), as three's hemisphere light: a metal floor
    then reflects the dark background, as it did there."""
    w = bpy.data.worlds.new('post_era_world')
    scene.world = w
    if w.node_tree is None:
        w.use_nodes = True
    bg = w.node_tree.nodes.get('Background') or next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs['Color'].default_value = (*background, 1.0)
    bg.inputs['Strength'].default_value = 1.0
    for name, col, z in (('hemi_sky', sky, 1.0), ('hemi_ground', ground, -1.0)):
        ld = bpy.data.lights.new(name, 'SUN')
        ld.energy = intensity
        ld.color = col
        ld.angle = math.pi
        ld.specular_factor = 0.0
        ld.use_shadow = False
        ob = bpy.data.objects.new(name, ld)
        scene.collection.objects.link(ob)
        ob.rotation_euler = (0.0, 0.0, 0.0) if z > 0 else (math.pi, 0.0, 0.0)
    return w


def sun(scene, three_pos, strength, color=(1.0, 1.0, 1.0), angle_deg=1.0, name='sun'):
    """three's DirectionalLight at three_pos aimed at the origin."""
    ld = bpy.data.lights.new(name, 'SUN')
    ld.energy = strength
    ld.color = color
    ld.angle = math.radians(angle_deg)
    ob = bpy.data.objects.new(name, ld)
    scene.collection.objects.link(ob)
    p = t2b(*three_pos)
    ob.location = p
    ob.rotation_euler = (-p).to_track_quat('-Z', 'Y').to_euler()
    return ob


def claudesona(scene, clip='idle', location=(0.0, 0.0, 0.0), rotation=0.0):
    from eidoblend.characters import load_vrm, play_vrma_default
    h = load_vrm('claude_suit_wardrobe', location=location, rotation=rotation, scene=scene)
    play_vrma_default(h, clip, t=0.0, scene=scene)
    return h


def look_settings(scene, exposure=0.0, samples=16, motion_blur=False):
    from eidoblend.look import render_settings as RS
    RS.apply_auto_enhance(scene, 'probe', resolution=(scene.render.resolution_x, scene.render.resolution_y),
                          samples=samples, exposure=exposure, motion_blur={} if motion_blur else False)
    scene.render.use_compositing = True


# ------------------------------------------------------------------------------------------------- the scenes
def era_probe(fps=24, frames=(1, 48)):
    """work/fx_probe/era_new.js, rebuilt."""
    sc = new_scene(fps, frames)
    hemisphere_world(sc)                                   # HemisphereLight(0xffffff, 0x202040, 0.8); bg 0x0a0a14
    sun(sc, (3, 6, 4), 2.5)                                # DirectionalLight(0xffffff, 2.5) at (3, 6, 4)
    floor = box(sc, 'floor', (0.0, 0.0, -0.005), (10.0, 10.0, 0.01),
                material('floor', srgb('#1a1a2e'), rough=0.35, metal=0.8))
    floor.name = 'floor'
    h = claudesona(sc, 'idle')
    camera(sc, t2b(1.2, 1.4, 2.2), t2b(0.0, 1.1, 0.0), 50.0, clip_end=100.0)
    look_settings(sc, exposure=0.0)
    return sc, h


def neon_night(fps=24, frames=(1, 48)):
    """A dark cyberpunk street at night (aeropittura's lab in miniature)."""
    sc = new_scene(fps, frames)
    hemisphere_world(sc, sky=srgb('#0a0d18'), ground=srgb('#020206'), intensity=0.6, background=srgb('#05060d'))
    wet = material('wet_ground', srgb('#0b0c10'), rough=0.12, metal=0.0)
    box(sc, 'street', (0.0, 0.0, -0.05), (60.0, 60.0, 0.1), wet)
    concrete = material('blocks', srgb('#15161c'), rough=0.8)
    win = material('windows', srgb('#000000'), emit=srgb('#ffb066'), strength=4.0)
    teal = material('teal_windows', srgb('#000000'), emit=srgb('#29d3e6'), strength=3.0)
    rng = [(-9.0, 14.0, 6.0, 14.0), (-2.5, 20.0, 8.0, 24.0), (5.5, 15.0, 7.0, 18.0), (12.5, 24.0, 9.0, 28.0),
           (-15.0, 26.0, 9.0, 32.0)]
    import random
    rnd = random.Random(7)
    for i, (x, y, wd, ht) in enumerate(rng):
        box(sc, f'block{i}', (x, y, ht / 2), (wd, 6.0, ht), concrete)
        _windows(sc, f'block{i}_windows', x, y - 3.01, wd, ht, (win, teal), rnd)
    pink = material('neon_pink', srgb('#000000'), emit=srgb('#ff2a8a'), strength=40.0)
    cyan = material('neon_cyan', srgb('#000000'), emit=srgb('#1fd4e8'), strength=35.0)
    box(sc, 'neon_a', (-2.6, 6.0, 3.2), (3.2, 0.08, 0.08), pink)
    box(sc, 'neon_b', (-2.6, 6.0, 2.6), (0.08, 0.08, 1.2), pink)
    box(sc, 'neon_c', (3.0, 7.5, 4.0), (0.08, 0.08, 3.0), cyan)
    box(sc, 'neon_d', (3.0, 7.5, 2.4), (2.0, 0.08, 0.08), cyan)
    lamp = material('sodium', srgb('#000000'), emit=srgb('#ff8a3d'), strength=60.0)
    box(sc, 'lamp_head', (1.8, 2.5, 4.2), (0.5, 0.25, 0.12), lamp)
    pole = material('pole', srgb('#202024'), rough=0.4, metal=0.9)
    box(sc, 'lamp_pole', (1.8, 2.6, 2.1), (0.08, 0.08, 4.2), pole)
    ls = bpy.data.lights.new('sodium_light', 'SPOT')
    ls.energy, ls.color = 900.0, srgb('#ff9a4d')
    ls.spot_size = math.radians(110)
    lso = bpy.data.objects.new('sodium_light', ls)
    sc.collection.objects.link(lso)
    lso.location = (1.8, 2.5, 4.05)
    for name, pos, col, w in (('pink_fill', (-2.6, 5.6, 2.9), '#ff2a8a', 300.0), ('cyan_fill', (3.0, 7.1, 3.2), '#1fd4e8', 250.0)):
        lp = bpy.data.lights.new(name, 'POINT')
        lp.energy, lp.color = w, srgb(col)
        lp.shadow_soft_size = 0.3
        lpo = bpy.data.objects.new(name, lp)
        sc.collection.objects.link(lpo)
        lpo.location = pos
    h = claudesona(sc, 'dance', location=(0.0, 4.0, 0.0), rotation=0.0)
    cam = camera(sc, (0.6, 0.4, 1.5), (0.0, 4.0, 1.15), 42.0, clip_end=500.0)
    for f, p in ((frames[0], (0.6, 0.4, 1.5)), (frames[1], (0.2, 1.4, 1.4))):
        cam.location = p
        cam.keyframe_insert('location', frame=f)
    look_settings(sc, exposure=0.5)
    sc.eevee.use_fast_gi = False
    return sc, h


def _windows(scene, name, x, y, wd, ht, mats, rnd, w=0.7, h=1.0, pitch=(1.4, 2.4)):
    """A facade's windows: one mesh, a lit window (warm or teal) in about half the bays."""
    import bmesh
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    nx, nz = int((wd - 1.0) // pitch[0]), int((ht - 2.0) // pitch[1])
    for ix in range(nx):
        for iz in range(nz):
            if rnd.random() < 0.45:
                continue
            cx = x - (nx - 1) * pitch[0] / 2 + ix * pitch[0]
            cz = 1.6 + iz * pitch[1]
            vs = [bm.verts.new((cx + dx, y, cz + dz)) for dx, dz in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2),
                                                                      (-w / 2, h / 2))]
            f = bm.faces.new(vs)
            f.material_index = 0 if rnd.random() < 0.7 else 1
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    return ob


def mover(fps=24, frames=(1, 24)):
    """An emissive sphere and a lit cube crossing the frame against a dark wall (the temporal effects)."""
    sc = new_scene(fps, frames)
    hemisphere_world(sc, sky=(1.0, 1.0, 1.0), ground=(0.2, 0.2, 0.2), intensity=0.5, background=(0.01, 0.01, 0.012))
    box(sc, 'wall', (0.0, 3.0, 1.5), (12.0, 0.2, 6.0), material('wall', (0.05, 0.05, 0.06), rough=0.9))
    box(sc, 'floor', (0.0, 0.0, -0.05), (12.0, 12.0, 0.1), material('floor', (0.08, 0.08, 0.09), rough=0.7))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.35, location=(-2.5, 1.0, 1.4))
    s = bpy.context.active_object
    s.name = 'emitter'
    s.data.materials.append(material('emit', (0, 0, 0), emit=(1.0, 0.55, 0.2), strength=25.0))
    c = box(sc, 'cube', (2.5, 1.0, 0.6), (0.6, 0.6, 0.6), material('cube', (0.1, 0.45, 0.9), rough=0.4))
    for f, sx, cx in ((frames[0], -2.6, 2.6), (frames[1], 2.6, -2.6)):
        s.location.x, c.location.x = sx, cx
        s.keyframe_insert('location', index=0, frame=f)
        c.keyframe_insert('location', index=0, frame=f)
    for ob in (s, c):
        _linear(ob)
    sun(sc, (3, 6, 4), 2.0)
    camera(sc, (0.0, -5.0, 1.3), (0.0, 1.0, 1.1), 40.0, clip_end=100.0)
    look_settings(sc, exposure=0.0)
    return sc


def _linear(ob):
    from bpy_extras import anim_utils
    ad = ob.animation_data
    cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    for fc in cb.fcurves:
        for k in fc.keyframe_points:
            k.interpolation = 'LINEAR'


def uf_hole(fps=24, frames=(1, 12), shot='closeSing', t0=4.0, res=(960, 540)):
    """THE HOLE of UNKNOWN FORCE, built by its own port (eidoblend.sets.unknown_force, the city family's), with the
    claudesona dancing on her mark and the camera on one of the film's chorus shots, `t0` seconds in at the first
    frame: aeropittura's real scene. Returns (scene, her handle, pre(frame)) where pre(frame) drives the set's
    per-frame state (screens, tickers, the focal light) as the film's probe stage did. Raises if the set fails."""
    from eidoblend.sets import unknown_force as UF
    from eidoblend.sets.unknown_force import citykit as KIT
    from eidoblend.sets.unknown_force import hole as H
    for c in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras,
              bpy.data.node_groups, bpy.data.images, bpy.data.worlds):
        for x in list(c):
            c.remove(x)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.fps, sc.render.fps_base = fps, 1.0
    sc.frame_start, sc.frame_end = frames
    KIT.eevee_settings(sc, samples=16)
    hole = UF.build('hole', scene=sc)
    P = hole['parts']
    P['apply_atmosphere'](sc)
    from eidoblend.characters import load_vrm, play_vrma_default
    h = load_vrm('claude_suit', location=(0.0, 0.0, 0.0), rotation=0.0, scene=sc)
    play_vrma_default(h, 'dance', t=0.0, scene=sc)
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.parent is not None
              and (o.parent == h.arm or o.parent.parent == h.arm)]
    for o in meshes:
        if o.name not in P['her'].objects:
            P['her'].objects.link(o)
    try:
        KIT.fog_objects(P['kit'], meshes)
    except Exception as e:                               # noqa: BLE001 (the haze on her is dressing)
        print(f'[scenes] uf_hole: fog_objects skipped ({e!r})', flush=True)
    cd = bpy.data.cameras.new('uf_cam')
    cd.clip_start, cd.clip_end = 0.05, 6000.0
    cam = bpy.data.objects.new('uf_cam', cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    H.key_hole_cam(cam, shot, frame_start=frames[0] - int(round(t0 * fps)), fps=fps)

    def pre(frame):
        tt = t0 + (frame - frames[0]) / fps
        hole['update'](80.0 + tt, {'cam_vel': (0, 0, 0)})
        P['set_focal']((0.0, 0.0, 3.0), {'gain': 0.35, 'radius': 70.0})
    return sc, h, pre


# ------------------------------------------------------------------------------------------------- render, then post
def render_sources(scene, out_dir, frames, name='src', passes=('Depth', 'Normal'), pre=None):
    """Render `frames` once (EEVEE) to EXR sequences: Combined and `passes` (look/post/chain.save_frames_passes), and
    a plain PNG through the view transform beside them; pre(frame), when given, runs before each frame's render.
    Returns {pass: path of the first frame}."""
    from eidoblend.look.post import chain
    os.makedirs(out_dir, exist_ok=True)
    pats = chain.save_frames_passes(scene, out_dir, tuple(passes), name=name)
    sc = scene
    sc.render.image_settings.media_type = 'IMAGE'
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_depth = '8'
    for f in frames:
        sc.frame_set(f)
        if pre is not None:
            pre(f)
        sc.render.filepath = os.path.join(out_dir, f'{name}_plain_{f:04d}.png')
        bpy.ops.render.render(write_still=True)
    paths = {p: os.path.join(out_dir, pat.replace('####', f'{frames[0]:04d}')) for p, pat in pats.items()}
    for p, path in paths.items():
        if not os.path.exists(path):
            raise RuntimeError(f'render_sources: {p} was not written ({path})')
    return paths


def post_scene(src, view, fps=24, frames=(1, 48), res=(960, 540), name='post', clip_end=1000.0):
    """A scene with nothing to render but a camera, its compositor reading the saved frames (src: render_sources'
    paths): the post runs over them as over a render. view: (view_transform, look, exposure) of the film; clip_end:
    the source camera's far plane (the era pass's storybook clamps the sky's depth there, as WebGPU's far)."""
    from eidoblend.look.post import chain
    sc = bpy.data.scenes.new(name)
    if bpy.context.window:
        bpy.context.window.scene = sc
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = 1
    sc.render.fps, sc.render.fps_base = fps, 1.0
    sc.frame_start, sc.frame_end = frames
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.use_motion_blur = False
    cam = bpy.data.objects.new(name + '_cam', bpy.data.cameras.new(name + '_cam'))
    cam.data.clip_end = float(clip_end)
    sc.collection.objects.link(cam)
    sc.camera = cam
    sc.view_settings.view_transform, sc.view_settings.look, sc.view_settings.exposure = view
    chain.tree(sc)
    chain.use_saved_frames(sc, src['Combined'], frame_start=1,
                           passes={k: v for k, v in src.items() if k != 'Combined'})
    return sc


def hud_pixels(W, H, lines, bar=(0.06, 0.82, 0.62, 0.94), badge=(0.085, 0.845, 0.115, 0.895),
               bar_rgba=(0.012, 0.014, 0.035, 0.82), badge_rgb=(0.02, 0.6, 0.7), size_px=None):
    """A broadcast lower third as a straight-alpha float RGBA array (H, W, 4), top-down: a dark translucent bar, a
    teal badge and white text lines in Press Start 2P, drawn by Blender's own text renderer (blf) into an offscreen
    buffer, as the era looks' glyph atlas is. bar / badge: (x0, y0, x1, y1) in frame fractions, y down. Test dressing
    (the overlay's contents belong to motion graphics)."""
    import blf
    import gpu
    import numpy as np
    from mathutils import Matrix
    font = os.path.join(WORKTREE, 'eidoverse', 'assets', 'fonts', 'PressStart2P-Regular.ttf')
    fid = blf.load(font)
    if fid < 0:
        raise FileNotFoundError(font)
    if bpy.app.background:
        try:
            gpu.init()
        except Exception:                                  # noqa: BLE001 (already up)
            pass
    size_px = size_px or max(8, int(round(H * 0.022)))
    off = gpu.types.GPUOffScreen(W, H, format='RGBA32F')
    with off.bind():
        fb = gpu.state.active_framebuffer_get()
        fb.clear(color=(0.0, 0.0, 0.0, 0.0))
        with gpu.matrix.push_pop():
            gpu.matrix.load_matrix(Matrix.Identity(4))
            gpu.matrix.load_projection_matrix(Matrix(((2.0 / W, 0, 0, -1), (0, 2.0 / H, 0, -1), (0, 0, 1, 0),
                                                      (0, 0, 0, 1))))
            blf.size(fid, size_px)
            blf.color(fid, 1.0, 1.0, 1.0, 1.0)
            x = (badge[2] + 0.012) * W
            top = H * (1.0 - bar[1])                       # y up in the buffer
            step = (bar[3] - bar[1]) * H / (len(lines) + 1)
            for i, line in enumerate(lines):
                blf.position(fid, x, top - step * (i + 1) - size_px * 0.4, 0)
                blf.draw(fid, line)
        buf = fb.read_color(0, 0, W, H, 4, 0, 'FLOAT')
    buf.dimensions = W * H * 4
    text = np.array(buf.to_list(), np.float32).reshape(H, W, 4)[::-1]          # top-down
    off.free()
    blf.unload(font)
    px = np.zeros((H, W, 4), np.float32)
    x0, y0, x1, y1 = (int(bar[0] * W), int(bar[1] * H), int(bar[2] * W), int(bar[3] * H))
    px[y0:y1, x0:x1] = bar_rgba
    bx0, by0, bx1, by1 = (int(badge[0] * W), int(badge[1] * H), int(badge[2] * W), int(badge[3] * H))
    px[by0:by1, bx0:bx1] = (*badge_rgb, 1.0)
    a = np.clip(text[..., 0:1], 0.0, 1.0)              # white text's coverage: its red over the cleared buffer
    px[..., :3] = px[..., :3] * (1.0 - a) + a
    px[..., 3:4] = np.maximum(px[..., 3:4], a)
    return px


def render_png(scene, path, frame):
    scene.frame_set(frame)
    scene.render.image_settings.media_type = 'IMAGE'
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_depth = '8'
    scene.render.filepath = path
    with bpy.context.temp_override(scene=scene):
        bpy.ops.render.render(write_still=True, scene=scene.name)
    if not os.path.exists(path):
        raise RuntimeError(f'render_png: {path} was not written')
    return path

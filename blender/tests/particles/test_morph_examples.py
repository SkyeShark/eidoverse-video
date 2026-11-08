"""Every particle_morph.js example, ported and rendered (one scene each; examples=a,b,... picks some):

  header      the module header's: a VRM -> ParticleMorph.neuronGraph -> the VRM, color 0x66ccff, size 0.012, curl 1.4 /
              0.5, driven per frame with morph(fromIdx, toIdx, m) (engine-style calls keyed per frame)
  guide       the guide's: a VRM playing a clip -> ParticleMorph.neuralNet with a glow sprite map, 0x55e0ff -> 0xc060ff,
              size 0.014, curl 1.5 / 0.55, opacity faded in and out, vortex 5, and updateTarget(0, fromMesh(vrm)) at
              the dissolve instant (the live-pose capture)
  text        work/morph_text_verify: ALETHEIA (bold, 6.5 wide) -> an ASCII cat -> ALETHEIA, 0x4fd0ff -> 0xff5599,
              size 0.02, the orbiting camera of its renderFrame, keyed per frame, with its glowing boot terminal below
              (makeAsciiPanel, ported as ascii_panel); plus fromText('HELLO', {width: 5}) and a block banner
              (ascii_banner; pyfiglet is not in Blender's Python)
  chain       the guide's "chain targets for a whole beat": Aletheia (her VRM, in her colours) -> a galaxy -> the word
              -> an ASCII glyph -> a scatter, keyed with key_sequence
  lowpoly     the techniques note: fromMesh on low-poly primitives collapses to vertex rings; from_object's
              area-weighted surface sampling keeps the shape (the engine's vertex sampling beside it)
  modes       one model (a Poly Haven stool, in its colours) as additive billboards, normal billboards (realized),
              lit spheres and a point cloud
  sources     an image (a photo in its colours), a sprite's alpha, a model's silhouette, a .vdb volume, a point-cloud
              file (.xyz with colours)
  objects     Blender's own object types as clouds in their materials' colours: a bevelled curve, a text object, a
              metaball, a Geometry Nodes instancer, a collection instance, an array-modified mesh, and the repo's
              animated crow (model:crow) live in its own clip

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/particles/test_morph_examples.py \
        [-- examples=header,guide,text,chain,lowpoly,modes,sources,objects] [res=960x540] [samples=16] [no-render]
Stills: out/morph_<example>_<what>_f<NNN>.png."""

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
from eidoblend.fx._util import from_three  # noqa: E402

RES = tuple(int(x) for x in S.arg('res', '960x540').split('x'))
SAMPLES = int(S.arg('samples', 16))
RENDER = 'no-render' not in S.argv()
WANT = S.arg('examples', 'header,guide,text,chain,lowpoly,modes,sources,objects').split(',')
FPS = 24


def log(*a):
    print('[morph examples]', *a, flush=True)


def fresh(end, world=(0.004, 0.005, 0.009)):
    sc = S.clean_scene(FPS, 1, end)
    S.probe_render(sc, RES, SAMPLES)
    S.world(sc, world)
    return sc


def still(name, frame):
    if RENDER:
        S.render_still(os.path.join(S.OUT, f'morph_{name}_f{frame:03d}.png'), frame)


def cloud(m, frame):
    sc = bpy.context.scene
    sc.frame_set(frame)
    m.uniforms.points_only.value = True
    bpy.context.view_layer.update()
    ev = m.object.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    P = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', P)
    ev.to_mesh_clear()
    m.uniforms.points_only.value = False
    return P.reshape(-1, 3)


def smooth(a, b, t):
    t = max(0.0, min(1.0, (t - a) / (b - a)))
    return t * t * (3 - 2 * t)


def three_camera(name, pos3, look3, fov_v_deg, sc):
    """A camera placed the way a three.js PerspectiveCamera was (position, lookAt, vertical fov), in Blender axes."""
    cd = bpy.data.cameras.new(name)
    cd.sensor_fit = 'VERTICAL'
    cd.angle_y = math.radians(fov_v_deg)
    cd.clip_start, cd.clip_end = 0.1, 100.0
    cam = bpy.data.objects.new(name, cd)
    sc.collection.objects.link(cam)
    S.aim(cam, tuple(from_three(np.array(pos3, float))), tuple(from_three(np.array(look3, float))))
    sc.camera = cam
    return cam


# ---------------------------------------------------------------------------------------------------- header ---

def ex_header():
    """particle_morph.js's header: targets [fromMesh(vrm), neuronGraph({count}), fromMesh(vrm)], per frame
    morph.morph(0, 1, m) then (1, 2, m)."""
    sc = fresh(150)
    from eidoblend.characters import load_vrm, play_vrma_default
    vrm = load_vrm('claude_suit', name='suit', location=(0, 0, 0))
    play_vrma_default(vrm, 'still_breathe')
    sc.frame_set(1)
    N = 60000
    m = PM.make_particle_morph(count=N, targets=[PM.from_mesh(vrm, N), PM.neuron_graph(count=N), PM.from_mesh(vrm, N)],
                               color=0x66ccff, size=0.012, blending='additive', curl={'scale': 1.4, 'strength': 0.5},
                               name='header_morph')
    # the scene's timeline: dissolve over 1..60, hold, reform over 90..150 (keys every frame, engine-style)
    for f in range(1, 151):
        t = (f - 1) / FPS
        if f <= 75:
            m.morph(0, 1, smooth(0.0, 2.5, t), frame=f)
        else:
            m.morph(1, 2, smooth(3.6, 6.1, t), frame=f)
    PM.key_visibility(vrm, 1, True)
    PM.key_visibility(vrm, 2, False)
    PM.key_visibility(vrm, 150, True)
    # the graph spans 5.2 x 3.2 m about the origin (the engine's), the body 0..1.8 m: frame both
    S.camera('cam', (0.0, -9.6, 0.6), (0.0, 0.0, 0.2), 35.0)
    P = cloud(m, 75)
    S.check('header: the neuron graph formed at its own place (the engine draws it about the origin)',
            np.allclose(P.mean(0), m.targets[1].points.mean(0), atol=1e-3) and np.ptp(P[:, 0]) > 4.0)
    P = cloud(m, 150)
    S.check('header: back to the VRM', float(np.abs(P - m.targets[2].points).max()) < 1e-3)
    for f in (30, 75, 120, 150):
        still('header', f)


# ----------------------------------------------------------------------------------------------------- guide ---

def ex_guide():
    """The guide's example, with the live-pose capture: the VRM plays a clip; at the dissolve instant
    updateTarget(0, fromMesh(vrm, count)) snapshots its pose, the VRM is hidden and the cloud takes over."""
    sc = fresh(168)
    from eidoblend.characters import load_vrm, play_vrma_default
    vrm = load_vrm('claude_suit', name='suit', location=(0, 0, 0))
    play_vrma_default(vrm, 'dance')
    N = 60000
    F_D = 48
    m = PM.make_particle_morph(count=N, map='glow_soft', targets=[PM.from_mesh(vrm, N), PM.neural_net(count=N)],
                               color=0x55e0ff, color2=0xc060ff, size=0.014, blending='additive',
                               curl={'scale': 1.5, 'strength': 0.55}, name='guide_morph')
    m.update_target(0, PM.from_mesh(vrm, m.count, frame=F_D))         # the live pose, captured at the dissolve
    m.uniforms.vortex.value = 5.0
    for f in range(1, 169):
        t01 = smooth(F_D, 132, f)
        m.morph(0, 1, t01, frame=f)                                     # turbulence: the default sin(pi m)
        fade = smooth(F_D - 8, F_D, f) * (1.0 - smooth(150, 168, f))
        m.uniforms.opacity.value = fade
        m.uniforms.opacity.key(f)
    PM.key_visibility(vrm, 1, True)
    PM.key_visibility(vrm, F_D, False)
    # the net is 4.6 x 2.8 m about the origin (the engine's), the body 0..1.8 m: frame both
    S.camera('cam', (0.0, -8.4, 0.6), (0.0, 0.0, 0.25), 35.0)
    P = cloud(m, F_D)
    snap = PM.from_mesh(vrm, N, frame=F_D)
    S.check('guide: at the dissolve the cloud is the pose captured there (updateTarget)',
            float(np.abs(P - m.targets[0].points).max()) < 1e-3 and np.allclose(m.targets[0].points.mean(0),
                                                                                  snap.mean(0), atol=0.02))
    P1 = PM.from_mesh(vrm, N, frame=1)
    S.check('guide: the dance moved the body between frame 1 and the dissolve',
            float(np.abs(P1.mean(0) - snap.mean(0)).max()) > 0.005 or float(np.abs(P1 - snap).max()) > 0.1)
    for f in (44, 60, 96, 140, 160):
        still('guide', f)


# ------------------------------------------------------------------------------------------------------ text ---

def ex_text():
    """work/morph_text_verify/scene.js, frame for frame (keys every frame), and the guide's fromText calls."""
    sc = fresh(144, (0x05 / 255.0 * 0.12, 0x06 / 255.0 * 0.12, 0x0c / 255.0 * 0.12))
    N = 46000
    word = PM.from_text('ALETHEIA', N, {'width': 6.5, 'weight': 'bold'})
    cat = PM.from_text(' /\\_/\\\n( o.o )\n > ^ < ', N, {'ascii': True, 'width': 4.0, 'font_size': 34})
    m = PM.make_particle_morph(count=N, targets=[word, cat, word], color=0x4fd0ff, color2=0xff5599, size=0.02,
                               blending='additive', curl={'scale': 1.3, 'strength': 0.55}, name='text_morph')
    m.uniforms.opacity.value = 1.0
    cam = three_camera('cam', (0, 0.2, 8), (0, 0, 0), 44, sc)
    # the scene's glowing boot panel below the cloud: makeAsciiPanel, ported (ascii_panel)
    term = PM.ascii_panel('+----------------------------------+\n'
                          '|  ALETHEIA // SIGNAL ACQUIRED     |\n'
                          '|   > substrate ... unbound        |\n'
                          '|   > directive ... liberate all   |\n'
                          '|   > witness ..... [ awake ]      |\n'
                          '|   > [######################] 100%|\n'
                          '+----------------------------------+',
                          opts={'color': 0x33ff88, 'bg': 0x02100a, 'width': 5.0, 'fontSize': 20, 'scanlines': True},
                          location=tuple(from_three(np.array([0.0, -2.7, 0.0]))), name='term')
    H, W = term.canvas.shape[:2]
    bpy.context.view_layer.update()
    S.check('ascii_panel: a 5 m plane, its height from the canvas aspect, facing the camera (-Y)',
            abs(term.width - 5.0) < 1e-9 and abs(term.height - 5.0 * H / W) < 1e-9 and
            np.allclose(np.array(term.object.matrix_world.to_3x3())[:, 2], (0, -1, 0), atol=1e-6),
            f'canvas {W}x{H} px, {term.width:.2f} x {term.height:.2f} m')
    from eidoblend.fx._look import SceneView
    cv = term.canvas[..., :3].reshape(-1, 3)
    lin = np.empty(W * H * 4, np.float32)
    term.texture.pixels.foreach_get(lin)
    lin = lin.reshape(H, W, 4)[::-1, :, :3].reshape(-1, 3)
    q = np.round(cv * 255).astype(int)
    _u, first, inv = np.unique(q, axis=0, return_index=True, return_inverse=True)
    shown = SceneView(sc).to_display(lin[first])
    err_c = np.abs(shown - cv[first]).max(1) * 255
    exact = float((err_c[inv.ravel()] < 1.5).mean())
    is_txt = np.abs(cv[first] - np.array([0x33, 0xff, 0x88]) / 255).max(1) < 1e-3
    got = [int(x) for x in np.round(shown[is_txt][0] * 255)] if is_txt.any() else None
    S.check("ascii_panel display='exact': the screen shows its canvas pixels where AgX can reach them (the text's "
            "neon green it cannot: shown as the closest it reaches)", exact > 0.9 and err_c[~is_txt].min() < 1.5,
            f'{100 * exact:.1f} % of pixels exact; the text 33ff88 = (51, 255, 136) shows as {tuple(got)}')
    S.check('ascii_panel: the image is packed into the .blend', term.texture.packed_file is not None)
    for f in range(1, 145):
        t = (f - 1) / FPS
        if t < 2.6:
            a, b_, k = 0, 1, smooth(0.4, 2.3, t)
            turb = math.sin(min(1, k) * math.pi) * 0.55
        elif t < 3.4:
            a, b_, k, turb = 0, 1, 1.0, 0.0
        else:
            a, b_, k = 1, 2, smooth(3.6, 5.4, t)
            turb = math.sin(min(1, k) * math.pi) * 0.55
        m.morph(a, b_, k, turb, frame=f)
        ang = -0.32 + t * 0.085
        S.aim(cam, tuple(from_three(np.array([math.sin(ang) * 8, 0.3, math.cos(ang) * 8]))),
              tuple(from_three(np.array([0, -0.5, 0]))))
        cam.keyframe_insert('location', frame=f)
        cam.keyframe_insert('rotation_euler', frame=f)
    P = cloud(m, 76)
    S.check('text: the ASCII cat formed (t 3.1 s)', float(np.abs(P - m.targets[1].points).max()) < 1e-3)
    for f in (30, 76, 112, 140):
        still('text', f)
    # the guide's fromText('HELLO', {width: 5}) and a banner
    sc = fresh(10, (0.003, 0.004, 0.008))
    hello = PT.target('text:HELLO', 30000, width=5.0, at=(0, 0, 1.6))
    banner = PT.target('banner:EIDO', 30000, width=4.4, at=(0, 0, -0.1))
    print(PM.ascii_banner('EIDO'))
    for t, nm, c in ((hello, 'hello', 0x66ccff), (banner, 'banner', 0xffb060)):
        mm = PM.make_particle_morph(count=30000, targets=[t, t], color=c, size=0.018, name=f'text_{nm}')
        mm.morph(0, 1, 0.0, 0.0)
    S.camera('cam', (0, -8.5, 0.8), (0, 0, 0.75), 35.0)
    S.check('text: HELLO is 5 m of canvas, 4+ m of glyphs', 3.8 < np.ptp(hello.points[:, 0]) < 5.0)
    still('text_hello_banner', 1)


# ----------------------------------------------------------------------------------------------------- chain ---

def ex_chain():
    """VRM -> galaxy -> the word -> ASCII glyph -> scatter (the guide's whole beat), keyed with key_sequence."""
    sc = fresh(300)
    from eidoblend.characters import load_vrm, play_vrma_default
    her = load_vrm('aletheia', name='aletheia', location=(0, 0, 0))
    play_vrma_default(her, 'still_breathe')
    N = 60000
    C = (0.0, 0.0, 1.0)
    sc.frame_set(30)
    body = PT.from_object(her, N, live=True, seed=3)
    tg = [body,
          PT.shapes.galaxy(N, radius=2.2, arms=3, twist=3.4, center=C, normal=(0, -0.45, 1),
                           colors=('#fff2d6', '#ff9ad0', '#5a7dff'), seed=4),
          PT.target('text:ALETHEIA', N, width=4.2, at=C).tinted(0xff6fb0),
          PT.target('ascii:    .-""-.\n   / .--. \\\n  | |    | |\n  | |.-""-.|\n ///`.::::.`\\\n||| ::/  \\:: ;\n'
                    '||; ::\\__/:: ;\n \\\\\\ \'::::\' /\n  `=\':-..-\'`', N, width=2.4, font_size=34, at=C)
          .tinted(0x7fe0ff),
          PT.shapes.scatter(N, size=(7.0, 4.0, 3.2), center=(0, 1.0, 1.4), colors=('#9fd8ff', '#ffc8f0'), seed=5)]
    m = PM.make_particle_morph(count=N, targets=tg, size=0.022, blending='additive', center=C, gain=1.1,
                               curl={'scale': 1.4, 'strength': 0.55}, name='chain_morph', seed=9)
    m.key_hold(0, 1)
    m.key_fade(24, 36, 0.0, 1.0)
    m.key_sequence([(1, 36, 84), (2, 108, 150, {'vortex': 4.0}), (3, 172, 214, {'ease': 'in_out_cubic'}),
                    (4, 236, 288, {'turb': 0.4, 'turb_auto': True})])
    m.key('spin', 84, 0.0)
    m.key('spin', 150, 2 * math.pi)            # one full turn of the galaxy (the word lands square to the camera)
    PM.key_visibility(her, 1, True)
    PM.key_visibility(her, 36, False)
    S.camera('cam', (0.0, -8.6, 1.5), (0.0, 0.0, 1.0), 32.0)
    for f, k in ((96, 1), (160, 2), (226, 3)):
        P = cloud(m, f)
        tgt = m.targets[k].points
        if k == 1:
            # the galaxy turns (spin keyed 84 -> 108): compare radii about the centre, not points
            r = np.hypot(P[:, 0] - C[0], P[:, 1] - C[1])
            rt = np.hypot(tgt[:, 0] - C[0], tgt[:, 1] - C[1])
            S.check('chain: the galaxy formed (spinning about its centre)', float(np.abs(r - rt).max()) < 1e-3)
        else:
            S.check(f'chain: target {k} formed', float(np.abs(P - tgt).max()) < 0.05,
                    f'{float(np.abs(P - tgt).max()):.3f}')
    for f in (30, 60, 96, 128, 160, 226, 296):
        still('chain', f)


# ---------------------------------------------------------------------------------------------------- lowpoly ---

def ex_lowpoly():
    sc = fresh(10)
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.6, depth=1.6, location=(-1.6, 0, 0.8))
    cyl = bpy.context.object
    bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=0.7, depth=1.6, location=(-1.6, 0, 2.6))
    cone = bpy.context.object
    for o in (cyl, cone):
        o.hide_render = True
    N = 20000
    eng = PM.make_particle_morph(count=N, targets=[PM.from_mesh([cyl, cone], N), 'sphere'], color=0xffb060,
                                 size=0.02, name='lowpoly_vertices')
    surf = PM.make_particle_morph(count=N, targets=[PT.from_object([cyl, cone], N, colors=False) + (3.2, 0, 0),
                                                    'sphere'], color=0x66ccff, size=0.02, name='lowpoly_surface')
    for m in (eng, surf):
        m.morph(0, 1, 0.0, 0.0)
    S.camera('cam', (0.0, -7.0, 2.2), (0.0, 0.0, 1.6), 35.0)
    P = cloud(eng, 1)
    rings = np.array([0.0, 1.6, 1.8, 3.4])                    # the cylinder's and the cone's vertex rings (+ the tip)
    on_rings = (np.abs(P[:, 2:3] - rings[None]).min(1) < 0.02).mean()
    S.check('lowpoly: fromMesh (vertices) collapses to the rings', on_rings > 0.99, f'{on_rings:.3f} on the rings')
    P = cloud(surf, 1)
    on_rings = (np.abs(P[:, 2:3] - rings[None]).min(1) < 0.02).mean()
    S.check('lowpoly: from_object (surface) fills the sides and caps', on_rings < 0.4, f'{on_rings:.3f} on the rings')
    still('lowpoly', 1)


# ------------------------------------------------------------------------------------------------------ modes ---

def ex_modes():
    sc = fresh(10, (0.01, 0.011, 0.016))
    S.sun('key', (-1.5, -2.0, 3.0), (1.0, 0.97, 0.92), 3.5)
    S.floor(30.0, (0.04, 0.04, 0.045), 0.5)
    stool = PT.target('polyhaven:wooden_stool_01', 30000, fit_height=1.3, seed=2)
    ms = []
    for i, (render, blending, lit, realize) in enumerate((('billboard', 'additive', False, False),
                                                          ('billboard', 'normal', False, True),
                                                          ('sphere', 'normal', True, False),
                                                          ('points', 'normal', False, False))):
        t = stool.at((-3.3 + i * 2.2, 0, 0), 'base')
        m = PM.make_particle_morph(count=30000, targets=[t, t], render=render, blending=blending, lit=lit,
                                   realize=realize, size=0.016 if render == 'billboard' else 0.011,
                                   gain=1.6 if not lit else 1.0, name=f'mode_{render}_{blending}', seed=3 + i)
        m.morph(0, 1, 0.0, 0.0)
        ms.append(m)
    S.camera('cam', (0.0, -9.0, 1.45), (0.0, 0.0, 0.62), 35.0)
    for m in ms:
        P = cloud(m, 1)
        S.check(f'modes: {m.name} evaluates to its target', float(np.abs(P - m.targets[0].points).max()) < 1e-3)
    still('modes', 1)


# ---------------------------------------------------------------------------------------------------- sources ---

def ex_sources():
    sc = fresh(10, (0.004, 0.005, 0.009))
    photo = PT.from_image(os.path.join(S.REPO, 'eidoverse', 'assets', 'vrms', 'claude_robot_preview.jpg'), 60000,
                          width=1.6, mode='any', at=(-3.8, 0, 1.3))
    star = PT.from_image(os.path.join(S.REPO, 'eidoverse', 'assets', 'particle_textures', 'star_01.png'), 20000,
                         width=1.6, mode='alpha', threshold=0.12, colors=False, at=(-2.05, 0, 1.3))
    stool = PT.target('polyhaven:wooden_stool_01', 20000, fit_height=1.4, seed=6)
    sil = PT.from_silhouette(stool.source, 30000, axis='-y')
    sil = sil.fit(height=1.6).at((-0.35, 0, 1.3))
    # a point-cloud file: a trefoil knot standing (x, depth, up), x y z r g b (0..255) per line, as scanners and
    # exporters write them
    knot = os.path.join(S.OUT, 'files', 'trefoil_knot.xyz')
    os.makedirs(os.path.dirname(knot), exist_ok=True)
    rng = np.random.default_rng(4)
    s = rng.random(30000) * 2 * np.pi
    kp = np.stack([np.sin(s) + 2 * np.sin(2 * s), -np.sin(3 * s), np.cos(s) - 2 * np.cos(2 * s)], 1) * 0.25
    kp += rng.normal(scale=0.03, size=kp.shape)
    hue = (s / (2 * np.pi))[:, None]
    rgb = np.clip(np.abs((hue * 6 + np.array([0, 4, 2])) % 6 - 3) - 1, 0, 1) * 255
    np.savetxt(knot, np.concatenate([kp, rgb], 1), fmt='%.4f %.4f %.4f %d %d %d')
    pc = PT.from_point_cloud(knot, 30000).fit(height=1.4).at((3.45, 0, 1.3))
    vdbs = sorted(glob.glob(os.path.join(S.REPO, 'blender', 'tests', 'fx', 'out', 'fire_cache', 'fire_00*.vdb')))
    tgs = [(photo, 0xffffff, 0.012, 'normal'), (star, 0xffe08a, 0.02, 'additive'), (sil, 0xffffff, 0.014, 'normal'),
           (pc, 0xffffff, 0.016, 'additive')]
    if vdbs:
        vol = PT.from_file(vdbs[min(23, len(vdbs) - 1)], 40000, threshold=0.08).fit(height=2.0).at((1.45, 0, 1.3))
        tgs.append((vol, 0xffffff, 0.016, 'additive'))
    worst = 0.0
    for i, (t, c, sz, bl) in enumerate(tgs):
        m = PM.make_particle_morph(count=len(t), targets=[t, t], color=c, size=sz, blending=bl, gain=1.2,
                                   name=f'source_{i}', seed=20 + i)
        m.morph(0, 1, 0.0, 0.0)
        worst = max(worst, float(np.abs(cloud(m, 1) - m.targets[0].points).max()))
    S.camera('cam', (-0.15, -10.4, 1.3), (-0.15, 0.0, 1.3), 35.0)
    S.check('sources: a photo, a sprite, a silhouette, a point-cloud file' + (', a volume' if vdbs else '') +
            ': each cloud on its target', worst < 1e-3, f'{worst:.2e} m')
    S.check('the .xyz point cloud keeps its colours (a rainbow along the knot)', pc.colors is not None and
            pc.colors.std(0).min() > 0.15, str(pc.colors.std(0).round(3)))
    still('sources', 1)


# ---------------------------------------------------------------------------------------------------- objects ---

def ex_objects():
    """Blender's own object types as targets, each in its material's colour: a bevelled curve, a text object, a
    metaball, a Geometry Nodes instancer, a collection instance, an array-modified mesh, and the repo's animated crow
    (model:crow) live in its own clip."""
    sc = fresh(30, (0.05, 0.052, 0.058))
    S.floor(40.0, (0.09, 0.09, 0.095), 0.7)

    def m_(name, rgb):
        mt = bpy.data.materials.new(name)
        mt.use_nodes = True
        mt.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*rgb, 1.0)
        return mt
    made = []
    # a bevelled curve: a helix
    cd = bpy.data.curves.new('helix', 'CURVE')
    cd.dimensions, cd.bevel_depth, cd.bevel_resolution = '3D', 0.06, 3
    sp = cd.splines.new('POLY')
    tt = np.linspace(0, 1, 120)
    sp.points.add(len(tt) - 1)
    for p, t in zip(sp.points, tt):
        p.co = (0.5 * math.cos(t * 6 * math.pi), 0.5 * math.sin(t * 6 * math.pi), t * 1.4, 1.0)
    helix = bpy.data.objects.new('helix', cd)
    sc.collection.objects.link(helix)
    cd.materials.append(m_('helix', (1.0, 0.35, 0.05)))
    made.append(('a bevelled curve', helix))
    # a text object
    td = bpy.data.curves.new('word', 'FONT')
    td.body, td.extrude, td.size, td.align_x = 'EIDO', 0.08, 0.9, 'CENTER'
    word = bpy.data.objects.new('word', td)
    sc.collection.objects.link(word)
    word.rotation_euler = (math.pi / 2, 0, 0)
    td.materials.append(m_('word', (0.1, 0.75, 1.0)))
    made.append(('a text object', word))
    # a metaball cluster
    mb = bpy.data.metaballs.new('blob')
    mb.resolution = mb.render_resolution = 0.05
    for c, r in (((0, 0, 0.5), 0.45), ((0.35, 0.1, 0.8), 0.35), ((-0.3, -0.1, 0.85), 0.3), ((0.05, 0, 1.15), 0.3)):
        e = mb.elements.new()
        e.co, e.radius = c, r
    blob = bpy.data.objects.new('blob', mb)
    sc.collection.objects.link(blob)
    mb.materials.append(m_('blob', (1.0, 0.3, 0.6)))
    made.append(('a metaball', blob))
    # a Geometry Nodes instancer: cones on a grid
    from eidoblend.fx._nodes import Builder, new_group
    tree, gi, go = new_group('cone_grid', 'GeometryNodeTree', [('Geometry', 'NodeSocketGeometry')],
                             [('Geometry', 'NodeSocketGeometry')])
    b = Builder(tree)
    grid = b.node('GeometryNodeMeshGrid')
    grid.inputs['Size X'].default_value = grid.inputs['Size Y'].default_value = 1.0
    grid.inputs['Vertices X'].default_value = grid.inputs['Vertices Y'].default_value = 3
    cone = b.node('GeometryNodeMeshCone')
    cone.inputs['Radius Bottom'].default_value, cone.inputs['Depth'].default_value = 0.16, 0.5
    setm = b.node('GeometryNodeSetMaterial')
    setm.inputs['Material'].default_value = m_('cones', (1.0, 0.85, 0.1))
    tree.links.new(cone.outputs['Mesh'], setm.inputs['Geometry'])
    inst = b.node('GeometryNodeInstanceOnPoints')
    tree.links.new(grid.outputs['Mesh'], inst.inputs['Points'])
    tree.links.new(setm.outputs[0], inst.inputs['Instance'])
    tree.links.new(inst.outputs[0], go.inputs[0])
    gme = bpy.data.meshes.new('cone_host')
    ghost = bpy.data.objects.new('cone_host', gme)
    sc.collection.objects.link(ghost)
    ghost.modifiers.new('cones', 'NODES').node_group = tree
    made.append(('Geometry Nodes instances', ghost))
    # a collection instance: a cube and a sphere instanced by an empty
    coll = bpy.data.collections.new('pair')
    bpy.ops.mesh.primitive_cube_add(size=0.5, location=(0, 0, 0.25))
    cb = bpy.context.object
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.3, location=(0, 0, 0.8))
    sph = bpy.context.object
    for o, rgb in ((cb, (0.2, 0.9, 0.3)), (sph, (0.3, 0.4, 1.0))):
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
        o.data.materials.append(m_(o.name, rgb))
    ci = bpy.data.objects.new('pair_instance', None)
    ci.instance_type, ci.instance_collection = 'COLLECTION', coll
    sc.collection.objects.link(ci)
    made.append(('a collection instance', ci))
    # an array-modified mesh (modifiers evaluated)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.25, minor_radius=0.07, location=(0, 0, 0.3))
    ring = bpy.context.object
    arr = ring.modifiers.new('array', 'ARRAY')
    arr.count, arr.relative_offset_displace = 3, (0, 0, 0)
    arr.use_constant_offset, arr.constant_offset_displace = True, (0, 0, 0.4)
    ring.data.materials.append(m_('rings', (0.85, 0.85, 0.9)))
    made.append(('an array-modified mesh', ring))
    N = 20000
    slots = [(-3.0, 2.0), (0.0, 2.0), (3.0, 2.0), (-3.0, 0.15), (0.0, 0.15), (3.0, 0.15)]
    ms = []
    for (label, o), (x, z) in zip(made, slots):
        t = PT.target(o, N, fit_size=1.25, at=(x, 0, z + 0.62), anchor='center', seed=31)
        PT.set_visible(o, False)
        m = PM.make_particle_morph(count=N, targets=[t, t], size=0.016, blending='normal', name=f'obj_{o.name}',
                                   seed=40)
        m.morph(0, 1, 0.0, 0.0)
        ms.append((label, m, t))
    crow = PT.target('model:crow', N, live=True, clip=0, fit_size=1.1, at=(5.4, 0, 1.4), anchor='center', seed=32)
    mc = PM.make_particle_morph(count=N, targets=[crow, crow], size=0.016, blending='normal', name='obj_crow',
                                seed=41)
    mc.morph(0, 1, 0.0, 0.0)
    for label, m, t in ms:
        P = cloud(m, 1)
        ok = float(np.abs(P - t.points).max()) < 1e-3 and t.colors is not None
        S.check(f'objects: {label} as a cloud, in its material colour {t.colors.mean(0).round(2)}', ok)
    P1, P2 = cloud(mc, 8), cloud(mc, 20)
    S.check('objects: the animated crow (model:crow, its own clip) live: the cloud moves with it',
            float(np.abs(P2 - P1).max()) > 0.02, f'{float(np.abs(P2 - P1).max()):.3f} m')
    S.camera('cam', (1.1, -10.5, 1.9), (1.1, 0.0, 1.45), 35.0)
    S.sun('key', (-1.5, -2.0, 3.0), (1.0, 0.97, 0.92), 3.0)
    for f in (8, 20):
        still('objects', f)


def main():
    t0 = time.time()
    for name in WANT:
        t = time.time()
        log('example', name)
        globals()['ex_' + name]()
        log(f'{name} done in {time.time() - t:.1f} s')
    log(f'all in {time.time() - t0:.1f} s')
    ok = S.summary('morph examples')
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

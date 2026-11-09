"""look/post/aeropittura.py: the futurist post pass of the UNKNOWN FORCE music video (effects_tsl/aeropittura.js), the
frame repainted as a Futurist painting of a dark cyberpunk night: one compositor pass, a weight per ingredient and a
master `force`.

    from eidoblend.look.post import custom_effects as fx, aeropittura as AP
    e = fx.apply_to(scene, 'aeropittura', {'aeropittura': {'layer': 'under'}})    # under the HUD: captions crisp
    U = e.uniforms
    AP.apply_look(U, AP.LOOKS['argue'], 1.0)                     # or apply_look(U, from, force, to, s): a crossfade
    AP.set_planes(U, AP.PLANES['balla_sun'])                     # the plane family (change it on cuts)
    AP.set_focal(U, 0.5, 0.42)                                   # uv, y DOWN; refuses a non-finite point (HAZARD)
    AP.set_spare(U, 0.5, 0.4, 0.12)                              # a face kept readable (uv, y down; r in frame heights)
    U.cut(120)                                                   # U.cut(): the time echoes restart at frame 120
    AP.apply_look(U, AP.LOOKS['storm'], 1.0, frame=96)           # frame=: keyed there (every setter takes it)
    AP.key_focal(U, scene, idol, range(1, 241))                  # projected through the camera every frame, keyed
    AP.key_spare(U, scene, (arm, 'head'), range(1, 241))         # her face (head + 0.12 m), the film's radius rule
    AP.drive_time(U['spin'], 0.03)                               # spin = 0.03 rad a second (a driver)
    AP.ease_reading(U, 312, 380)                                 # a reading shot: the brush eased toward READ, keyed

LOOKS (off, hush, argue, storm), PLANES (balla_sun, revolt, race_sun, iridescent, dive, quiet), RAMP (the palette,
dark to light), KEYS (the ingredients), PKEYS (the plane families), apply_look, set_planes, as in the WebGPU module;
READ and ease_reading, project_focal / key_focal, spare_radius / key_spare and drive_time carry the film's per-frame
logic (scene.js) as keys and drivers. Uniforms (group inputs, keyable): the ingredients, force, the plane weights,
focal, spare, spin, swirl, swirl_r, brush_angle, chev_dir. time and frame come from Scene Time.

The stages, as the WebGPU pass ran them:
  A  Crali's vortex round `focal`, simultaneity (R two echoes back, G one, B now; echo = 50 ms) and Balla's
     repetitions (up to four older copies of what moves), into DISPLAY space; alpha = motion. The earlier frames are
     the pass's own input, recorded every frame and read back from disk (look/post/history.py): the WebGPU history
     ring. A frame never rendered before reads as the current frame (the ring filled at a fresh start), and a cut
     (e.cut(f), the timeline's camera markers) restarts the echoes.
  B  the colour structure tensor (Sobel per channel)        C  the flow field: stroke direction, anisotropy, energy
  D  the underpainting: the pass's own anisotropic Kuwahara (kuwahara_aniso): 8 polynomial sectors (zeta 2 / RAD,
     eta 0.33) over the flow's ellipse, taps 1 px apart over [-8, 8]^2 at 1080p, as the WebGPU loop (the tap count
     is the built height's; their spacing follows the frame being composited, so the brush keeps its size in the
     picture at any render size). Nested function
     groups (one tap; a row of 17 taps; 17 rows) keep the build to some 500 nodes; inlined, it is 289 taps a pixel.
     Checked against the shader in numpy (tests/post_era/test_aero_kuwahara.py): 2e-4 at the worst pixel. Cost:
     0.3-0.6 s a frame at 960x540 and 1.4-2.8 s at 1920x1080 on the GPU compositor. kuwahara='blender' (a build
     option) uses Blender's Kuwahara node instead: 0.02-0.06 s, but its sectors barely overlap, so it smears far less
     (1.7-1.8 sRGB levels from the WebGPU picture, where the own filter is 0.00 and no filter 2.8-3.2).
  E  the light field: three's mip-chain Gaussian of A's bright parts (display value > 0.8), its gradient pointing
     away from each light: Balla's street-light halos
  F  the divisionist strokes: two layers of oriented strokes (14 px and 6 px cells at 1080p), each one colour of
     the underpainting pushed warm or cool, some toward the complement, V-strokes of the light's colour in a halo;
     `crisp` hands dense detail back sharp, and the spared face keeps most of its drawing
  G  the planes (ids from the families, slipped, shaded, glazed, with painted edges), the lines of force, the
     palette (the RAMP gradient map; saturated light keeps its hue), the canvas (weave, scanline, grain); back from
     display space to scene-linear.
HAZARD: a non-finite focal blacks out the whole frame in the WebGPU pass (0 x NaN). set_focal / set_spare refuse one,
key_focal falls back to (0.5, 0.42) behind the camera, the pass clamps focal and spare itself (a NaN keyed straight
into the socket stays finite) and clamps its input (NaN -> 0, Inf -> 64, on the GPU and the CPU compositor).
"""
from __future__ import annotations

import math

import bpy

from . import display as D
from ._graph import fn, hex_lin

RAMP = ['#020307', '#06141d', '#0d3644', '#33204f', '#b81f66', '#ff8a3d', '#e9f3f1']
DIAG = [(18, 0.22), (-34, -0.18), (71, 0.31), (-62, 0.36), (8, -0.41)]      # [angle deg, offset] long diagonals
RAYS = 9

LOOKS = {
    'off': {'echo': 0, 'multi': 0, 'strokes': 0, 'under': 0, 'halo': 0, 'planes': 0, 'lines': 0, 'palette': 0,
            'canvas': 0, 'crisp': 0},
    # the floor of the film: still a painting (there is no clean image under the paint), just a quiet one
    'hush': {'echo': 0.1, 'multi': 0, 'strokes': 0.6, 'under': 0.7, 'halo': 0.4, 'planes': 0.08, 'lines': 0.05,
             'palette': 0.4, 'canvas': 0.55, 'crisp': 0.85},
    'argue': {'echo': 0.5, 'multi': 0.25, 'strokes': 0.9, 'under': 0.85, 'halo': 0.75, 'planes': 0.55, 'lines': 0.4,
              'palette': 0.6, 'canvas': 0.6, 'crisp': 0.7},
    'storm': {'echo': 1, 'multi': 0.85, 'strokes': 1, 'under': 1, 'halo': 1, 'planes': 1, 'lines': 1, 'palette': 0.7,
              'canvas': 0.7, 'crisp': 0.5},
}
KEYS = list(LOOKS['off'])

# plane families (each 0/1-ish; the planes' edges fade with the weight, their ids switch at 0.5: change on cuts)
PLANES = {
    'balla_sun': {'rays': 1, 'rings': 1, 'diag': 0.6, 'chev': 0, 'tri': 0},   # "Mercury Passing Before the Sun"
    'revolt': {'rays': 0, 'rings': 0, 'diag': 0.5, 'chev': 1, 'tri': 0},      # Russolo's "The Revolt" wedges
    'race_sun': {'rays': 1, 'rings': 0, 'diag': 0, 'chev': 1, 'tri': 0},      # the sun's rays from its idol + wedges
    'iridescent': {'rays': 0, 'rings': 0, 'diag': 0, 'chev': 0, 'tri': 1},    # Balla's interpenetrations
    'dive': {'rays': 1, 'rings': 0, 'diag': 1, 'chev': 0, 'tri': 0},          # Crali's dive
    'quiet': {'rays': 0, 'rings': 0, 'diag': 0.6, 'chev': 0, 'tri': 0},       # a few long diagonals
}
PKEYS = list(PLANES['balla_sun'])
# the reading shots (postprocessing.md): ease the brush toward these while the camera is on words
READ = {'strokes': 0.28, 'under': 0.3, 'halo': 0.15, 'lines': 0, 'multi': 0, 'crisp': 1}

GROUP = 'eido_aeropittura'


# ------------------------------------------------------------------------------------------------- setters
def _key(sock, frame, interp='LINEAR'):
    """Key a uniform at `frame` (LINEAR, the harness's default; keyframe_insert ignores the preference)."""
    if frame is None:
        return
    sock.keyframe_insert('default_value', frame=int(frame))
    from .history import _fcurves
    tree = sock.id_data
    ad = tree.animation_data
    if not ad or not ad.action:
        return
    path = sock.path_from_id('default_value')
    for fc in _fcurves(ad.action, tree):
        if fc.data_path == path:
            for k in fc.keyframe_points:
                if abs(k.co.x - frame) < 1e-6:
                    k.interpolation = interp
            fc.update()


def apply_look(U, look, force=1.0, other=None, s=0.0, frame=None):
    """applyLook(U, look, force, other, s): every ingredient a + (b - a) s between two looks (no easing), and the
    master force. frame: key them there."""
    for k in KEYS:
        a = float(look.get(k, 0.0))
        b = float(other.get(k, 0.0)) if other else a
        U[k].default_value = a + (b - a) * float(s)
        _key(U[k], frame)
    U['force'].default_value = float(force)
    _key(U['force'], frame)
    return U


def set_planes(U, fam, frame=None):
    """setPlanes(U, family): the five plane weights (keyed CONSTANT at `frame`: a family switches on a cut)."""
    for k in PKEYS:
        U[k].default_value = float(fam.get(k, 0.0))
        _key(U[k], frame, 'CONSTANT')
    return U


def _finite(*v):
    return all(isinstance(x, (int, float)) and math.isfinite(x) for x in v)


def set_focal(U, x, y, frame=None):
    """The idol the cones and speed lines start from (uv, y DOWN). A non-finite point is refused (the WebGPU
    HAZARD: it blacks out the frame): returns False and leaves the focal where it was."""
    if not _finite(x, y):
        print(f'[aeropittura] focal ({x}, {y}) is not finite: kept at {tuple(U["focal"].default_value)[:2]}',
              flush=True)
        return False
    U['focal'].default_value = (float(x), float(y), 0.0)
    _key(U['focal'], frame)
    return True


def set_spare(U, x, y, r, frame=None):
    """A face kept readable: (x, y) uv y down, r in frame heights (0 = none). A non-finite value is refused."""
    if not _finite(x, y, r):
        print(f'[aeropittura] spare ({x}, {y}, {r}) is not finite: kept', flush=True)
        return False
    U['spare'].default_value = (float(x), float(y), float(r))
    _key(U['spare'], frame)
    return True


def project_focal(scene, point, camera=None):
    """A world point -> its focal (uv, y down) through the scene camera (as the scene's depsgraph has it at the
    current frame), or None behind the camera (never NaN)."""
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector
    from .history import evaluated
    cam = evaluated(scene, camera or scene.camera)
    co = world_to_camera_view(scene, cam, Vector(point))
    if co.z <= 0 or not _finite(co.x, co.y):
        return None
    return co.x, 1.0 - co.y


def _point(target, frame, scene=None):
    """A world point from an Object (its origin, or a pose bone's head: (armature, 'bone')), a callable
    frame -> point, or a fixed point. Objects are read as the scene's own depsgraph evaluated them (history.evaluated:
    right for a scene that is not the active one too)."""
    from mathutils import Vector
    from .history import evaluated
    ev = (lambda ob: evaluated(scene, ob)) if scene is not None else (lambda ob: ob)
    if callable(target):
        return Vector(target(frame))
    if isinstance(target, tuple) and len(target) == 2 and isinstance(target[0], bpy.types.Object):
        arm, bone = target
        a = ev(arm)
        return a.matrix_world @ a.pose.bones[bone].head
    if isinstance(target, bpy.types.Object):
        return ev(target).matrix_world.translation.copy()
    return Vector(target)


def key_focal(U, scene, target, frames, camera=None, fallback=(0.5, 0.42)):
    """The focal keyed on every frame of `frames`: `target` (an Object, (armature, 'bone'), a callable frame ->
    world point, or a point) projected through the camera, as the film projected its idol every frame. Behind the
    camera the fallback is keyed instead (the HAZARD's guard, the film's own). Returns {frame: (x, y)}."""
    out = {}
    keep = scene.frame_current
    for f in frames:
        scene.frame_set(int(f))
        uv = project_focal(scene, _point(target, f, scene), camera)
        out[int(f)] = uv if uv is not None else tuple(fallback)
        set_focal(U, *out[int(f)], frame=int(f))
    scene.frame_set(keep)
    return out


def spare_radius(dist):
    """UNKNOWN FORCE's face radius (frame heights) for a head `dist` metres from the camera: 0.9 x
    clamp(0.55 / max(0.6, dist), 0, 1)."""
    return 0.9 * min(1.0, max(0.0, 0.55 / max(0.6, dist)))


def key_spare(U, scene, head, frames, camera=None, lift=0.12, radius=spare_radius, visible=None):
    """The spared face keyed on every frame: `head` (as key_focal's target) lifted `lift` metres, projected through
    the camera; r = radius(distance to the camera), 0 behind it or while visible(frame) is False (the film's rule:
    her head bone + 0.12 m). Returns {frame: (x, y, r)}."""
    from mathutils import Vector
    from .history import evaluated
    out = {}
    keep = scene.frame_current
    for f in frames:
        scene.frame_set(int(f))
        cam = camera or scene.camera
        p = _point(head, f, scene) + Vector((0.0, 0.0, lift))
        uv = project_focal(scene, p, cam)
        on = uv is not None and (visible is None or visible(f))
        r = radius((evaluated(scene, cam).matrix_world.translation - p).length) if on else 0.0
        out[int(f)] = (*(uv if uv is not None else (0.5, 0.4)), r)
        set_spare(U, *out[int(f)], frame=int(f))
    scene.frame_set(keep)
    return out


def drive_time(socket, per_second, offset=0.0):
    """A driver making a uniform a function of the scene's time: offset + per_second x seconds (the film's
    spin: drive_time(U['spin'], 0.03))."""
    try:
        socket.driver_remove('default_value')
    except (TypeError, RuntimeError):
        pass
    fc = socket.driver_add('default_value')
    d = fc.driver
    d.type = 'SCRIPTED'
    tree = socket.id_data
    scene = next((s for s in bpy.data.scenes if s.compositing_node_group == tree), bpy.context.scene)
    for nm, path in (('fps', 'render.fps'), ('base', 'render.fps_base')):
        v = d.variables.new()
        v.name = nm
        v.type = 'SINGLE_PROP'
        v.targets[0].id_type = 'SCENE'
        v.targets[0].id = scene
        v.targets[0].data_path = path
    d.expression = f'{float(offset)!r} + {float(per_second)!r} * frame * base / fps'
    return fc


def _owner_fps(U):
    """The frame rate of the scene whose compositor holds these uniforms (24 when none is found). U: the pass's
    uniforms, or apply_to's e.uniforms (one effect: its uniforms answer at the top level)."""
    tree = U['force'].id_data
    for s in bpy.data.scenes:
        if s.compositing_node_group == tree:
            return s.render.fps / s.render.fps_base
    return 24.0


def ease_reading(U, start, end, ease_in=0.6, ease_out=0.45, fps=None, frame_step=1):
    """The film's reading shots: over frames start..end the brush eases toward READ, keyed every frame_step frames
    from the uniforms' values at `start`: k = min(smooth((t - t0) / 0.6), 1 - smooth((t - (t1 - 0.45)) / 0.45)), the
    film's own smoothstepped ramps (0 -> 1 -> 0), t in seconds at the scene's frame rate (fps: another rate)."""
    fps = float(fps or _owner_fps(U))
    base = {k: U[k].default_value for k in READ}

    def smooth(x):
        x = min(1.0, max(0.0, x))
        return x * x * (3.0 - 2.0 * x)
    for f in range(int(start), int(end) + 1, frame_step):
        t, t0, t1 = f / fps, start / fps, end / fps
        k01 = min(smooth((t - t0) / ease_in), 1.0 - smooth((t - (t1 - ease_out)) / ease_out))
        for k, v in READ.items():
            U[k].default_value = base[k] + (v - base[k]) * k01
            _key(U[k], f)
    for k in READ:
        U[k].default_value = base[k]
    return U


# ------------------------------------------------------------------------------------------------- the registry's hook
def gap_frames(fps):
    """Frames between echoes: 50 ms (3 at 60 fps, 2 at 30, 1 at 24), as Math.round."""
    return max(1, int(math.floor(fps * 0.05 + 0.5)))


def make(scene, o, stage='aeropittura', layer='over'):
    """Put the pass in the scene's post chain (custom_effects.apply_to calls this). Returns (node, uniforms,
    [History])."""
    from . import chain, history as HI
    fps = scene.render.fps / scene.render.fps_base
    gap = gap_frames(fps)
    height = scene.render.resolution_y * scene.render.resolution_percentage / 100.0
    grp = build(height, kuwahara=o.get('kuwahara', 'own'))
    t = chain.tree(scene)
    node = t.nodes.new('CompositorNodeGroup')
    node.node_tree = grp
    node.width = 220
    chain.add_stage(scene, layer, stage, node)
    D.drive_exposure(scene, node.inputs['Exposure'])
    D.sync(scene)
    D.keep_synced()                                    # before each render / save, if the view changes later
    h = HI.History(scene, f'{stage}_in', tree=t, rider_of=stage)
    chain.relink(scene)
    for k in range(1, 5):
        img, _present = h.tap(t, k * gap)
        t.links.new(img, node.inputs[f'Echo{k}'])
    cuts = o.get('cuts')
    h.set_cuts(HI.scene_cuts(scene) if cuts is None else cuts, t, fresh=node.inputs['Fresh'])
    names = KEYS + ['force'] + PKEYS + ['focal', 'spare', 'spin', 'swirl', 'swirl_r', 'brush_angle', 'chev_dir']
    U = {k: node.inputs[k] for k in names}
    defaults = {'force': 1.0, 'focal': (0.5, 0.42, 0.0), 'spare': (0.5, 0.4, 0.0), 'spin': 0.0, 'swirl': 0.0,
                'swirl_r': 0.6, 'brush_angle': 1.05, 'chev_dir': (1.0, 0.0, 0.0)}
    for k in KEYS:
        U[k].default_value = float(o.get(k, 0.0))
    for k in PKEYS:                                    # balla_sun by default, as the WebGPU uniforms started
        U[k].default_value = float(o.get(k, PLANES['balla_sun'][k]))
    for k, v in defaults.items():
        v = o.get(k, v)
        if isinstance(v, (tuple, list)):
            v = (tuple(float(x) for x in v) + (0.0, 0.0, 0.0))[:3]
        U[k].default_value = v
    if not _finite(*U['focal'].default_value):
        raise ValueError('aeropittura: focal must be finite (the HAZARD)')
    return node, U, [h]


# ------------------------------------------------------------------------------------------------- the pass
def _ins():
    ins = [('Image', 'C', (0, 0, 0, 1))] + [(f'Echo{k}', 'C', (0, 0, 0, 0)) for k in range(1, 5)]
    ins += [('Fresh', 'S', 0.0), ('Exposure', 'S', 0.0), ('force', 'S', 1.0)] + [(k, 'S', 0.0) for k in KEYS] + [(k, 'S', 0.0) for k in PKEYS]
    ins += [('focal', 'V', (0.5, 0.42, 0.0)), ('spare', 'V', (0.5, 0.4, 0.0)), ('spin', 'S', 0.0), ('swirl', 'S', 0.0),
            ('swirl_r', 'S', 0.6), ('brush_angle', 'S', 1.05), ('chev_dir', 'V', (1.0, 0.0, 0.0))]
    return ins


KUWAHARA = ('own', 'blender')


def build(height=1080, rebuild=False, kuwahara='own'):
    """The pass as one node group per render height: the height sets the underpainting's tap count (round(8 S),
    a loop unrolled into nodes). Everything else sizes itself from the frame as it composites (the taps' spacing,
    the stroke cells, every pixel offset), so the group also paints a frame rendered at another size, a probe capped
    smaller than the film, as the film's picture.
    kuwahara: 'own' (the pass's anisotropic Kuwahara, ported) or 'blender' (Blender's Kuwahara node: faster, and a
    different filter: further from the WebGPU picture, measured in postprocessing.md)."""
    if kuwahara not in KUWAHARA:
        raise ValueError(f'aeropittura: kuwahara {kuwahara!r}: one of {KUWAHARA}')
    S = float(height) / 1080.0
    # version 4: the stroke cells and the Kuwahara's spacing follow the frame's size (version 3: the pass's own
    # Kuwahara; version 2: the focal / spare guards); a file's older group is rebuilt
    name = f'{GROUP}_h{int(round(height))}' + ('' if kuwahara == 'own' else '_bk')
    return fn(name, _ins(), [('Image', 'C')], lambda g, a: _aero(g, a, S, kuwahara), rebuild=rebuild, version=4)


def _aero(g, a, S_const, kuwahara='own'):
    img = a['Image']
    co = g.coords(img)
    W, H, S = co.W, co.H, co.S
    aspect = W / H
    t, frame = g.time()
    force, ev = a['force'], a['Exposure']

    def W_(k):
        return a[k] * force

    to_disp = lambda c: D.to_disp(g, c, ev)                      # noqa: E731
    fo = a['focal']
    # the HAZARD, guarded in the graph as well: a non-finite focal keyed or set by hand becomes a finite point
    # (NaN -> -1000, the constant first: the CPU compositor's max keeps a NaN only when it comes first)
    fox = g.min(1e3, g.max(-1e3, fo.x))
    foy = g.min(1e3, g.max(-1e3, fo.y))
    uv = co.uv

    def toQ(px_, py_):
        return (px_ - fox) * aspect, py_ - foy

    # ---- A: Crali's vortex + simultaneity + Balla's repetitions, into display space. a = motion.
    qx, qy = toQ(uv.x, uv.y)
    r = g.sqrt(qx * qx + qy * qy)
    sr = a['swirl_r']
    ang = a['swirl'] * g.exp(-(r * r) / g.max(sr * sr, 1e-4))
    cs, sn = g.cos(ang), g.sin(ang)
    q2x, q2y = qx * cs - qy * sn, qx * sn + qy * cs
    p = g.vec(q2x / aspect + fox, q2y + foy)
    cur = g.tap_rgba(img, p)
    c0 = to_disp(g.sanitize(g.c(cur)))
    c = []
    for k in range(1, 5):
        e = g.tap_rgba(a[f'Echo{k}'], p)
        # 0 where the frame was never rendered, and on a cut frame: the ring's fresh fill (the current frame)
        present = g.alpha(e) * (1.0 - a['Fresh'])
        ek = g.mix(g.c(cur), g.c(e), present)
        c.append(to_disp(g.sanitize(ek)))
    split = g.vec(c[1].x, c[0].y, c0.z)
    m = W_('multi')
    ghost = g.max(c0, g.max(c[0] * g.mix(0.55, 0.75, m), g.max(c[1] * g.mix(0.3, 0.6, m),
                                                                  g.max(c[2] * (m * 0.5), c[3] * (m * 0.4)))))
    mv = g.length(c0 - c[1])
    col1 = g.mix(c0, g.mix(split, ghost, m * 0.4 + 0.35), g.clamp(W_('echo'), 0.0, 1.0))
    s1 = g.rgba(col1, g.smoothstep(0.03, 0.25, mv))
    s1_rgb = g.c(s1)

    # ---- B, C: the colour structure tensor and the flow field
    flow = flow_field(g, s1, co, a['brush_angle'])

    # ---- D: the underpainting: the pass's own anisotropic Kuwahara on A's picture, oriented by the flow field
    RAD = max(3, int(round(8.0 * S_const)))            # the tap count; their spacing follows the frame's size
    if kuwahara == 'blender':                          # Blender's Kuwahara node: fast, but a different filter
        kw = g.node('CompositorNodeKuwahara')
        kw.inputs['Type'].default_value = 'Anisotropic'
        g.link(g.max(3.0, S * 8.0), kw.inputs['Size'])  # 8 px at 1080p, at whatever size the frame renders
        kw.inputs['Uniformity'].default_value = max(1, int(round(4 * S_const)))
        kw.inputs['Sharpness'].default_value = 0.5
        kw.inputs['Eccentricity'].default_value = 1.0
        g.link(s1, kw.inputs['Image'])
        kw_rgb = g.c(kw.outputs['Image'])
    else:
        kw_rgb = kuwahara_aniso(g, s1, flow, RAD)
    under_w = g.clamp(W_('under'), 0.0, 1.0)
    s3_rgb = g.mix(s1_rgb, kw_rgb, under_w)
    s3 = g.image(s3_rgb)

    # ---- E: the light field (only real light sources: display value > ~0.8) and the halo directions
    mips = g.mips(s1, 0.8, 0.12)
    spx, spy, spz = [g.min(1e3, g.max(-1e3, c)) for c in (a['spare'].x, a['spare'].y, a['spare'].z)]

    def spared_at(px_, py_, lo, hi):
        dx_, dy_ = (px_ - spx) * aspect, py_ - spy
        sd0 = g.sqrt(dx_ * dx_ + dy_ * dy_)
        return (1.0 - g.smoothstep(spz * lo, spz * hi, sd0)) * g.step(1e-4, spz)

    def Lf(ox, oy):
        return g.lum(g.tap(mips[2], uv + g.vec(ox * S / W, oy * S / H)))
    hgx, hgy = Lf(7, 0) - Lf(-7, 0), Lf(0, 7) - Lf(0, -7)
    hdir = g.normalize(g.vec(-hgx + 1e-7, -hgy))                       # downhill = away from the light
    lw = g.clamp(g.lum(g.tap(mips[2], uv)), 0.0, 8.0)
    own = g.lum(s1_rgb)
    hmask = g.smoothstep(0.01, 0.09, lw) * (1.0 - g.smoothstep(0.35, 0.7, own)) \
        * g.smoothstep(0.0005, 0.004, g.sqrt(hgx * hgx + hgy * hgy)) * (1.0 - spared_at(uv.x, uv.y, 0.8, 1.3))
    halo = g.rgba(g.vec(hdir.x, hdir.y, hmask), lw)

    # ---- F: the divisionist strokes over the underpainting
    sharp = s1_rgb
    flw = g.alpha(flow)
    fl_A = g.c(flow).z
    strokesW, haloW = W_('strokes'), W_('halo')
    cell_fn = _cell_fn()
    layers = []
    # the stroke cells, 14 and 6 px at 1080p: sized from the frame being composited (WebGPU's 14 S and 6 S, S = H /
    # 1080 of the render), so a probe rendered smaller than the film paints the same strokes, smaller
    for C, Wk, salt in ((S * 14.0, 0.40, 101), (S * 6.0, 0.38, 211)):
        best, sc, cov = -1.0, g.v((0.0, 0.0, 0.0)), 0.0
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                o = g.call(cell_fn, Flow=flow, Halo=halo, Under=s3, Light=mips[1], Ref=img, C=C, Wk=Wk,
                           Salt=float(salt), DX=float(dx), DY=float(dy), HaloW=haloW, Best=best, Sc=sc, Cov=cov)
                best, sc, cov = o['Best'], o['Sc'], o['Cov']
        layers.append((sc, cov))
    spared = spared_at(uv.x, uv.y, 0.6, 1.0)
    detail = g.max(g.smoothstep(0.004, 0.06, flw), spared)              # edges and the face get the fine brush
    scm = g.mix(layers[0][0], layers[1][0], detail)
    covm = g.mix(layers[0][1], layers[1][1], detail)
    col4 = g.mix(s3_rgb, scm, covm * g.clamp(strokesW, 0.0, 1.0))
    crispK = g.max(g.smoothstep(0.006, 0.05, flw) * (1.0 - fl_A * 0.7) * a['crisp'], spared * 0.75)
    col4 = g.mix(col4, sharp, g.clamp(crispK, 0.0, 0.85))
    s4 = g.rgba(col4, g.alpha(s1))

    # ---- G: planes, lines of force, palette, canvas, back to linear
    return {'Image': g.rgba(_final(g, a, co, S, aspect, t, frame, uv, toQ, flow, s4, spared, force), 1.0)}


# ------------------------------------------------------------------------------------------------- the flow field
def flow_field(g, s1, co, brush_angle):
    """aeropittura.js stages B and C on the display-space picture s1 (an image; co: its Coords): the colour structure
    tensor (a Sobel per channel, taps S px apart), smoothed by 13 taps 3 S and 6 S px out, then the stroke direction
    t (the minor eigenvector, signed like the default brush_angle direction, which also fills flat areas), the
    anisotropy A and the edge energy. Returns an image: rgb = (t.x, t.y, A), alpha = energy."""
    uv, S, W, H = co.uv, co.S, co.W, co.H

    def at(src, dx, dy):
        return g.tap(src, uv + g.vec(dx * S / W, dy * S / H)) if (dx, dy) != (0, 0) else g.tap(src, uv)
    A_ = {(dx, dy): at(s1, dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0)}
    ca, cb, cc = A_[(-1, -1)], A_[(0, -1)], A_[(1, -1)]
    cd, cf = A_[(-1, 0)], A_[(1, 0)]
    cg, ch, ci = A_[(-1, 1)], A_[(0, 1)], A_[(1, 1)]
    gx = (cc + cf * 2.0 + ci - ca - cd * 2.0 - cg) * 0.25
    gy = (cg + ch * 2.0 + ci - ca - cb * 2.0 - cc) * 0.25
    s2 = g.image(g.vec(g.dot(gx, gx), g.dot(gx, gy), g.dot(gy, gy)))
    taps = ((0, 0, 4), (3, 0, 2), (-3, 0, 2), (0, 3, 2), (0, -3, 2), (3, 3, 1), (-3, 3, 1), (3, -3, 1), (-3, -3, 1),
            (6, 0, 1), (-6, 0, 1), (0, 6, 1), (0, -6, 1))
    wsum = float(sum(w for _x, _y, w in taps))
    acc = None
    for dx, dy, w in taps:
        term = at(s2, dx, dy) * (w / wsum)
        acc = term if acc is None else acc + term
    E, F, G_ = acc.x, acc.y, acc.z
    disc = g.sqrt(g.max((E - G_) * (E - G_) + F * F * 4.0, 0.0))
    l1, l2 = (E + G_ + disc) * 0.5, (E + G_ - disc) * 0.5
    tv0x, tv0y = l1 - E, -F
    defx, defy = g.cos(brush_angle), g.sin(brush_angle)
    sgn = g.mix(-1.0, 1.0, g.step(0.0, tv0x * defx + tv0y * defy))     # same sign as the default
    tvx, tvy = tv0x * sgn, tv0y * sgn
    energy = E + G_
    kk = g.smoothstep(2e-5, 6e-4, energy) * g.step(1e-12, tvx * tvx + tvy * tvy)
    tn = g.normalize(g.vec(tvx + 1e-9, tvy))
    tmix = g.normalize(g.mix(g.vec(defx, defy), tn, kk) + g.v((1e-6, 0.0, 0.0)))
    Aniso = (l1 - l2) / (l1 + l2 + 1e-9) * kk
    return g.rgba(g.vec(tmix.x, tmix.y, Aniso), energy)               # (t.x, t.y, A) + energy in alpha


# ------------------------------------------------------------------------------------------------- the underpainting
_ACC = [f'M{k}' for k in range(8)] + [f'S{k}' for k in range(8)] + [f'W{k}' for k in range(8)]


def _acc_specs():
    return [(n, 'V' if n[0] in 'MS' else 'S', (0.0, 0.0, 0.0) if n[0] in 'MS' else 0.0) for n in _ACC]


def _kuwa_tap_fn():
    """One tap d = (DX, DY) of the anisotropic Kuwahara (aeropittura.js stage D's loop body), Step pixels per unit of
    d: the tap's colour, its eight polynomial sector weights (zeta = 2 / RAD, eta = 0.33) times the radial Gaussian
    exp(-3.125 |v|^2), divided by their sum, inside the flow's ellipse only (|v| <= 1), added into each sector's sums
    of c, c^2 and the weights (M, S, W)."""
    def body(g, a):
        src = a['Src']
        co = g.coords(src)
        dx, dy, step = a['DX'], a['DY'], a['Step']
        cphi, sphi, ia, ib, zeta = a['Cphi'], a['Sphi'], a['IA'], a['IB'], a['Zeta']
        eta = 0.33
        vx = (dx * cphi + dy * sphi) * ia
        vy = (dy * cphi - dx * sphi) * ib
        vv = vx * vx + vy * vy
        inside = 1.0 - g.math('GREATER_THAN', vv, 1.0)                      # If(dot(v, v) <= 1)
        c = g.tap(src, co.uv + g.vec(dx * step * co.pxu, dy * step * co.pxv))
        cc = c * c
        vxx, vyy = zeta - vx * vx * eta, zeta - vy * vy * eta
        z = [g.max(vy + vxx, 0.0), None, g.max(vyy - vx, 0.0), None, g.max(vxx - vy, 0.0), None,
             g.max(vx + vyy, 0.0), None]
        rx, ry = (vx - vy) * 0.70710678, (vx + vy) * 0.70710678
        rxx, ryy = zeta - rx * rx * eta, zeta - ry * ry * eta
        z[1], z[3], z[5], z[7] = g.max(ry + rxx, 0.0), g.max(ryy - rx, 0.0), g.max(rxx - ry, 0.0), g.max(rx + ryy, 0.0)
        ws = [q * q for q in z]
        tot = ws[0]
        for q in ws[1:]:
            tot = tot + q
        gw = g.exp(vv * -3.125) / (tot + 1e-6) * inside
        out = {}
        for k in range(8):
            wk = ws[k] * gw
            out[f'M{k}'] = a[f'M{k}'] + c * wk
            out[f'S{k}'] = a[f'S{k}'] + cc * wk
            out[f'W{k}'] = a[f'W{k}'] + wk
        return out
    ins = [('Src', 'C', (0, 0, 0, 1)), ('DX', 'S', 0.0), ('DY', 'S', 0.0), ('Step', 'S', 1.0), ('Cphi', 'S', 1.0),
           ('Sphi', 'S', 0.0), ('IA', 'S', 0.125), ('IB', 'S', 0.125), ('Zeta', 'S', 0.25)] + _acc_specs()
    outs = [(n, 'V' if n[0] in 'MS' else 'S') for n in _ACC]
    return fn('eido_aero_kuwa_tap', ins, outs, body, version=2)


def _kuwa_row_fn(rad):
    """One row (DY) of taps, DX = -rad .. rad: the tap group called 2 rad + 1 times, its sums handed along."""
    def body(g, a):
        tap = _kuwa_tap_fn()
        acc = {n: a[n] for n in _ACC}
        for dx in range(-rad, rad + 1):
            o = g.call(tap, Src=a['Src'], DX=float(dx), DY=a['DY'], Step=a['Step'], Cphi=a['Cphi'], Sphi=a['Sphi'],
                       IA=a['IA'], IB=a['IB'], Zeta=a['Zeta'], **acc)
            acc = {n: o[n] for n in _ACC}
        return acc
    ins = [('Src', 'C', (0, 0, 0, 1)), ('DY', 'S', 0.0), ('Step', 'S', 1.0), ('Cphi', 'S', 1.0), ('Sphi', 'S', 0.0),
           ('IA', 'S', 0.125), ('IB', 'S', 0.125), ('Zeta', 'S', 0.25)] + _acc_specs()
    outs = [(n, 'V' if n[0] in 'MS' else 'S') for n in _ACC]
    return fn(f'eido_aero_kuwa_row{rad}', ins, outs, body, version=2)


def kuwahara_aniso(g, src, flow, rad, step=None):
    """aeropittura.js stage D: the anisotropic Kuwahara of `src` (an image), 8 sectors with polynomial weights
    (Kyprianidis et al. 2009 / 2011), over the ellipse a = rad (A + 1), b = rad / (A + 1) turned to the flow's stroke
    direction (flow: an image, rgb = (t.x, t.y, A) as stage C writes it), taps over the square [-rad, rad]^2 (the
    WebGPU loop's, which clips the long axis at rad); each sector's mean weighted by 1 / ((255 sum var)^4 + 1).
    Returns the filtered colour (a V).
    rad = round(8 S) at the height the pass is built for: the number of taps. step: pixels between taps; None = 8 S /
    rad with S the frame's own H / 1080 when it composites, so the brush covers 8 S px whatever size the frame renders
    at (1 px between taps at 1080p and 540p). (WebGPU sampled its taps d x S px out on top of rad = round(8 S), so
    below 1080p its brush shrank twice over; this keeps the 1080p look, and a probe rendered smaller than the size
    the pass was built for paints the film's picture.)"""
    fl = g.c(flow)
    cphi, sphi, A = fl.x, fl.y, fl.z
    ia = 1.0 / ((A + 1.0) * float(rad))                                # 1 / a
    ib = (A + 1.0) / float(rad)                                        # 1 / b
    if step is None:
        step = g.coords(src).S * (8.0 / float(rad))
    acc = {n: ((0.0, 0.0, 0.0) if n[0] in 'MS' else 0.0) for n in _ACC}
    row = _kuwa_row_fn(int(rad))
    for dy in range(-rad, rad + 1):
        o = g.call(row, Src=src, DY=float(dy), Step=step, Cphi=cphi, Sphi=sphi, IA=ia, IB=ib, Zeta=2.0 / rad, **acc)
        acc = {n: o[n] for n in _ACC}
    num, den = None, None
    for k in range(8):
        wk = acc[f'W{k}'] + 1e-6
        mk = acc[f'M{k}'] / wk
        vk = g.abs(acc[f'S{k}'] / wk - mk * mk)
        sv = (vk.x + vk.y + vk.z) * 255.0
        al = 1.0 / (g.pow(sv, 4.0) + 1.0)
        num = mk * al if num is None else num + mk * al
        den = al if den is None else den + al
    return num / (den + 1e-6)


def _cell_fn():
    """One cell of a stroke layer (the 5 x 5 neighbourhood loop's body): its stroke, if it covers this pixel and
    wins the cell's draw (the highest h3), replaces the colour so far."""
    def body(g, a):
        ref = a['Ref']
        co = g.coords(ref)
        W, H, S = co.W, co.H, co.S
        fcx, fcy = co.fx, co.fy
        C, Wk, salt = a['C'], a['Wk'], a['Salt']
        cellx = g.floor(fcx / C) + 4096.0 + a['DX']
        celly = g.floor(fcy / C) + 4096.0 + a['DY']
        h1, h2, h3 = g.hash3(cellx, celly, salt), g.hash3(cellx, celly, salt + 1.0), g.hash3(cellx, celly, salt + 2.0)
        ctrx = (cellx - 4096.0 + h1 * 0.9 + 0.05) * C
        ctry = (celly - 4096.0 + h2 * 0.9 + 0.05) * C
        cuv = g.vec(ctrx / W, ctry / H)
        f = g.tap_rgba(a['Flow'], cuv)
        fv = g.c(f)
        hl = g.c(g.tap_rgba(a['Halo'], cuv))
        hm = hl.z * a['HaloW']
        tt = g.normalize(g.mix(g.vec(fv.x, fv.y), g.vec(hl.x, hl.y), g.clamp(hm * 1.5, 0.0, 1.0)) + g.v((1e-6, 0, 0)))
        tx, ty = tt.x, tt.y
        dxp, dyp = fcx - ctrx, fcy - ctry
        al = dxp * tx + dyp * ty
        ac = dxp * (-ty) + dyp * tx
        L = C * (h3 * 0.8 + 0.9) * (fv.z * 0.5 + 0.8)
        Wd = C * Wk * (h1 * 0.5 + 0.75)
        acV = ac - g.abs(al) * 0.6 * g.clamp(hm * 2.0, 0.0, 1.0)          # V strokes in halos
        tap = g.max(1.0 - (al / L) * (al / L), 0.0)
        wv = Wd * g.sqrt(tap)
        inside = g.smoothstep(wv + 0.8 * S, wv - 0.8 * S, g.abs(acV)) * g.step(g.abs(al), L)
        # paint: the underpainting at the stroke's centre, value-jittered, pushed warm or cool, a few strokes toward
        # the complement (divisionism), plus the light's colour in a halo
        cc = g.tap(a['Under'], cuv) * (h2 * 0.3 + 0.85)
        cc = cc * g.mix((0.9, 0.97, 1.12), (1.12, 0.98, 0.88), h3)
        mxc, mnc = g.max3(cc), g.min3(cc)
        comp = g.splat(mxc + mnc) - cc
        cc = g.mix(cc, g.mix(cc, comp, 0.4), g.step(0.92, h1) * 0.5)
        lc = g.min(g.v((8.0, 8.0, 8.0)), g.max(g.v((0.0, 0.0, 0.0)), g.tap(a['Light'], cuv)))
        lcmx = g.max3(lc) + 1e-4
        lcComp = g.splat(lcmx + g.min3(lc)) - lc
        halo = g.mix(lc, lcComp * 0.8, g.step(0.6, h2)) * (hm * (h3 * 1.2 + 0.6))
        cc = cc + halo
        k = g.step(a['Best'], h3) * g.step(0.02, inside)
        return {'Sc': g.mix(a['Sc'], cc, k * inside), 'Best': g.mix(a['Best'], h3, k),
                'Cov': g.max(a['Cov'], inside * k)}
    ins = [('Flow', 'C', (0, 0, 0, 0)), ('Halo', 'C', (0, 0, 0, 0)), ('Under', 'C', (0, 0, 0, 1)),
           ('Light', 'C', (0, 0, 0, 1)), ('Ref', 'C', (0, 0, 0, 1)), ('C', 'S', 14.0), ('Wk', 'S', 0.4),
           ('Salt', 'S', 101.0), ('DX', 'S', 0.0), ('DY', 'S', 0.0), ('HaloW', 'S', 0.0), ('Best', 'S', -1.0),
           ('Sc', 'V', (0, 0, 0)), ('Cov', 'S', 0.0)]
    return fn('eido_aero_cell', ins, [('Sc', 'V'), ('Best', 'S'), ('Cov', 'S')], body)


def _final(g, a, co, S, aspect, t, frame, uv, toQ, flow, s4, spared, force):
    """G: planes, lines of force, palette, canvas; returns the scene-linear colour."""
    W, H = co.W, co.H
    fcx, fcy = co.fx, co.fy
    qx, qy = toQ(uv.x, uv.y)
    lq = g.sqrt(qx * qx + qy * qy)
    planesW = a['planes'] * force * (1.0 - spared * 0.85)
    linesW = a['lines'] * force

    def on(k):
        return g.step(0.5, a[k])
    ang = g.atan2(qy, qx) + a['spin']
    idv, edge = 0.0, 1e3

    def add_edge(edge, e, k):
        return g.min(edge, g.mix(1e3, e, on(k)))
    # rays (Balla's cones)
    sector = g.floor(ang / (2 * math.pi / RAYS) + 64.0)
    idv = idv + sector * on('rays')
    sa = g.fract(ang / (2 * math.pi / RAYS))
    edge = add_edge(edge, g.min(sa, 1.0 - sa) * (2 * math.pi / RAYS) * lq * H, 'rays')
    # rings, logarithmic (they widen outward like a dive); none inside the light's own disc
    lr = g.log(g.max(lq, 1e-3)) * 2.6 + t * 0.12
    inDisc = g.step(lq, 0.07)
    idv = idv + (g.floor(lr) + 32.0) * 977.0 * (1.0 - inDisc) * on('rings')
    rf = g.fract(lr)
    edge = add_edge(edge, g.mix(g.min(rf, 1.0 - rf) / 2.6 * lq * H, 1e3, inDisc), 'rings')
    # long diagonals
    for k, (deg, off) in enumerate(DIAG):
        th = a['spin'] * (0.35 * (1 if k % 2 else -1)) + deg * math.pi / 180.0
        sd = qx * g.sin(th) + qy * g.cos(th) - off
        idv = idv + g.step(0.0, sd) * (math.pow(2, k + 1) * 7.0) * on('diag')
        edge = add_edge(edge, g.abs(sd) * H, 'diag')
    # chevrons (Russolo's wedges): V-shaped bands pointing along chev_dir, travelling
    cdv = g.normalize(a['chev_dir'] * g.v((1.0, 1.0, 0.0)) + g.v((1e-6, 0.0, 0.0)))
    cdx, cdy = cdv.x, cdv.y
    along, acr = qx * cdx + qy * cdy, qx * (-cdy) + qy * cdx
    vv = (along - g.abs(acr) * 0.9) * 3.2 - t * 0.9
    idv = idv + (g.floor(vv) + 64.0) * 331.0 * on('chev')
    vf = g.fract(vv)
    edge = add_edge(edge, g.min(vf, 1.0 - vf) / (3.2 * 1.345) * H, 'chev')
    # triangles (Balla's iridescent interpenetrations): a skewed lattice, each cell split in two
    tsx, tsy = qx * 4.0, qy * 4.0
    ta, tb = tsx - tsy * 0.57735, tsy * 1.1547
    tfa, tfb = g.fract(ta), g.fract(tb)
    upper = g.step(1.0, tfa + tfb)
    idv = idv + ((g.floor(ta) + 64.0) * 53.0 + (g.floor(tb) + 64.0) * 97.0 + upper * 7.0) * on('tri')
    te = g.min(g.min(g.min(tfa, 1.0 - tfa), g.min(tfb, 1.0 - tfb)), g.abs(tfa + tfb - 1.0) * 0.7071)
    edge = add_edge(edge, te / (4.0 * 1.15) * H, 'tri')

    hA, hB, hC = g.hash3(idv + 1e5, 17.0, 3.0), g.hash3(idv + 1e5, 29.0, 5.0), g.hash3(idv + 1e5, 41.0, 7.0)
    slip = g.vec((hA - 0.5) * 0.012 * planesW, (hB - 0.5) * 0.012 * planesW)
    sp = uv + slip
    base = g.tap_rgba(s4, sp)
    col = g.c(base)
    moving = g.alpha(base)
    # lines of force 1: drag along the contour where things move
    tfl = g.c(g.tap_rgba(flow, sp))
    acc = None
    for k in range(-6, 7):
        o = g.vec(tfl.x * (k * 2.2 * S / W), tfl.y * (k * 2.2 * S / H)) if k else None
        term = g.tap(s4, sp + o) if k else col
        acc = term if acc is None else acc + term
    col = g.mix(col, acc / 13.0, g.clamp(moving * linesW * 1.2, 0.0, 1.0))
    # lines of force 2: sparse speed lines toward the focal point, off the middle of frame
    dn = g.normalize(g.vec(qx + 1e-5, qy))
    dux, duy = dn.x / aspect, dn.y
    acc2 = None
    for k in range(10):
        term = g.tap(s4, sp - g.vec(dux * (k * 0.0045), duy * (k * 0.0045))) if k else g.tap(s4, sp)
        acc2 = term if acc2 is None else acc2 + term
    ox_, oy_ = (uv.x - 0.5) * aspect, uv.y - 0.5
    offC = g.smoothstep(0.22, 0.55, g.sqrt(ox_ * ox_ + oy_ * oy_))
    radial = g.smoothstep(0.2, 0.9, lq) * offC * linesW
    fine = g.hash3(g.floor(ang * (180.0 / math.pi * 0.7) + 720.0), 3.0, 11.0)
    col = g.mix(col, acc2 / 10.0, radial * g.smoothstep(0.72, 0.95, fine))

    # palette FIRST: gradient map by perceptual luminance; saturated light keeps its own hue
    ramp = [hex_lin(h) for h in RAMP]
    lum = g.lum(col)
    xr = g.clamp(g.pow(g.max(lum, 0.0), 0.62) * 1.02, 0.0, 1.0) * float(len(RAMP) - 1)
    rc = g.v(ramp[0])
    for k in range(1, len(RAMP)):
        rc = g.mix(rc, ramp[k], g.clamp(xr - float(k - 1), 0.0, 1.0))
    chroma = col / g.max(lum, 1e-4) * g.lum(rc)
    mxc, mnc = g.max3(col), g.min3(col)
    sat = (mxc - mnc) / (mxc + 1e-4)
    col = g.mix(col, g.mix(rc, chroma, g.clamp(sat * 0.8 + 0.2, 0.0, 0.85)), g.clamp(a['palette'] * force, 0.0, 1.0))

    # planes: lighter/darker, warmer/cooler; SHADOW planes toward wet black; NEON planes glazed where there is light
    shade = 1.0 + (hC - 0.5) * 0.6 * planesW
    warm = g.mix((0.85, 0.95, 1.18), (1.15, 0.97, 0.85), hA)
    col = col * shade * g.mix((1.0, 1.0, 1.0), warm, planesW * 0.6)
    col = col * (1.0 - g.step(hC, 0.3) * planesW * 0.45)
    neon = g.mix(hex_lin('#1fd4e8'), hex_lin('#ff3fa4'), g.step(0.5, hB))
    gn = g.hash3(g.floor(fcx / (5.0 * S) + fcy / (17.0 * S)), g.floor(fcy / (5.0 * S)), 37.0)
    lit = g.smoothstep(0.02, 0.25, g.lum(col))
    glazeA = g.step(0.72, hC) * planesW * (gn * 0.10 + 0.08) * lit
    col = g.mix(col, g.v((1.0, 1.0, 1.0)) - (g.v((1.0, 1.0, 1.0)) - col) * (g.v((1.0, 1.0, 1.0)) - neon), glazeA)
    # the plane edges: broken, brushy painted lines, light or dark
    wob = g.hash3(g.floor(fcx / (9.0 * S)), g.floor(fcy / (9.0 * S)), 13.0) * 0.8 + 0.6
    stroke = (1.0 - g.smoothstep(1.0 * S, 2.6 * S, edge / wob)) * planesW
    stroke = stroke * g.smoothstep(0.18, 0.4, g.hash3(g.floor(fcx / (23.0 * S)), g.floor(fcy / (23.0 * S)), 31.0))
    inkL = g.mix((0.02, 0.01, 0.05), (1.0, 0.92, 0.85), g.step(0.5, hB))
    col = g.mix(col, inkL, stroke * g.mix(0.12, 0.5, lit))              # in the dark a plane edge is a hint

    # canvas: weave + VHS scanline + grain (grain scales with the light: no grey veil on the blacks)
    cw = a['canvas'] * force
    wx, wy = g.abs(g.fract(fcx / (3.0 * S)) - 0.5), g.abs(g.fract(fcy / (3.0 * S)) - 0.5)
    weave = g.mix(wx, wy, g.step(0.5, g.fract(fcx / (6.0 * S) + g.floor(fcy / (3.0 * S)) * 0.5)))
    scan = g.smoothstep(0.25, 0.5, g.abs(g.fract(fcy / (3.0 * S)) - 0.5))
    grain = g.hash3(g.floor(fcx), g.floor(fcy), frame) - 0.5
    col = col * (1.0 - cw * (weave * 0.10 + scan * 0.07)) + g.splat(grain * (g.lum(col) * 0.08 + 0.006) * cw)
    return g.sanitize(D.from_disp(g, g.clamp(col, 0.0, 1.0), a['Exposure']))

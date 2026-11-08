"""look/post/era_looks.py: graphic-arts looks from the history of computing, as weights on ONE compositor pass
(effects_tsl/era_looks.js, ported node for node).

    from eidoblend.look.post import custom_effects as fx, era_looks as EL
    e = fx.apply_to(scene, 'era_looks')                          # the pass in the chain's 'over' slot
    EL.set_look(e.uniforms, EL.ERA_LOOKS['c64_1982'])           # one preset: apply_look(U, look, look, 1)
    EL.apply_look(e.uniforms, EL.ERA_LOOKS['vector'], EL.ERA_LOOKS['amber1984'], 0.3, frame=96)   # keyed at 96
    EL.crossfade(e.uniforms, EL.ERA_LOOKS['bell1961'], EL.ERA_LOOKS['mac1984'], 48, 72)     # keyed, frames 48-72
    e.key('era_looks', 'glitch', 60, 1.0)                       # any weight over a preset, keyed
Build options: persist_frames (the CRT persistence's history length; None = enough for its damp, 0 = off, nothing
written) and cuts (the frames the persistence restarts at; None = the camera markers and the camera's jumps).

Every look is a group input (0..1) on the same pass, so looks crossfade and stack; ERA_LOOKS holds the tuned presets
and apply_look() blends two of them (s smoothstepped; the pixel grid `px` snaps at the midpoint).
LOOKS: sepia, deco (+ sunburst), bw, ascii (line printer, the Press Start 2P glyph atlas drawn by Blender's blf),
vector, vfd, c64 (+ raster bars), mac, amber, websafe, feature, glitch, riso, kuwahara, halftone, phosphor, toon,
halation, watercolor. LAYERS: px, grain, flicker, scan, vignette; lift (stops) for the print / paint looks.

How the WebGPU pieces became compositor nodes:
  - the pass is one node group (eido_era_looks) with each look in its own sub-group, inputs = the uniforms;
  - three's mip-chain Gaussian (BloomNode) is Scale 1/2 + Blur per level (_graph.mips), sampled back by Map UV;
  - the integer hashes are White Noise (Blender's bit hash: the same uniform spread, not the same numbers);
  - fwidth() is the analytic derivative where the field is analytic (the halftone spot) and a one-pixel difference
    of the materialised field elsewhere (the watercolour's value layers);
  - display space (toDisp / fromDisp) is the scene's own view transform and its exact inverse (look/post/display.py:
    AgX here, as ACES there), so paper and ink land on screen as authored;
  - the phosphor persistence (three's AfterImageNode, max(new, old * damp) on the input) is computed without feedback:
    max over the last K input frames of frame * damp^k (each surviving the 0.1 mask), the frames read back from disk
    (look/post/history.py). Cuts (camera markers, camera jumps) restart it, as camJumped() did, and so does the tube
    coming on: each recorded frame's alpha says whether the CRT was on then;
  - the uniform If-branches are gone: a compositor evaluates every node (measured: a Switch evaluates both sides),
    so a look that is off costs its nodes anyway. Two gates stay as exact selects (the CRT's scanline resampling and
    gun convergence), because they replace values rather than mix them by weight;
  - so the input is clamped first (NaN -> 0, +Inf -> 65504): with every look mixed in by its weight, 0 x Inf = NaN
    would carry one bad pixel through the blur pyramids into every look weighted 0 (the NaN clamp);
  - the storybook's depth is the Depth pass (metric), clamped at the far plane (a driver on the scene camera's clip
    end, WebGPU's camFar); its normals are the Normal pass (world space: only their dot products are used).
"""
from __future__ import annotations

import math
import os

import bpy

from ._graph import bayer4, fn, hex_lin

C64 = ['#000000', '#FFFFFF', '#880000', '#AAFFEE', '#CC44CC', '#00CC55', '#0000AA', '#EEEE77',
       '#DD8855', '#664400', '#FF7777', '#333333', '#777777', '#AAFF66', '#0088FF', '#BBBBBB']
RAMP = ' .:-=+*#%@'                       # line-printer density ramp
KEYS = ['sepia', 'deco', 'bw', 'ascii', 'vector', 'vfd', 'c64', 'raster', 'mac', 'amber', 'websafe', 'feature',
        'glitch', 'riso', 'kuwahara', 'grain', 'flicker', 'scan', 'vignette', 'halftone', 'phosphor', 'toon',
        'halation', 'watercolor', 'lift']
KEYS_ALL = KEYS                           # the JS module's second list (applyLook's), the same 25 names

# Named era presets: weights that together make each era's look (era_looks.js ERA_LOOKS, as written there).
ERA_LOOKS = {
    'clean': {},
    'voder1939': {'deco': 0.85, 'sepia': 0.15, 'grain': 0.7, 'flicker': 0.5, 'vignette': 0.8},
    'bell1961': {'bw': 1, 'grain': 0.5, 'flicker': 0.35, 'vignette': 0.6, 'scan': 0.15},
    'printer1961': {'ascii': 1},
    'eliza1966': {'bw': 0.6, 'sepia': 0.4, 'grain': 0.3, 'vignette': 0.4},
    'vector': {'vector': 1, 'scan': 0.5, 'vignette': 0.5},
    'vfd1978': {'vfd': 0.85, 'vignette': 0.4},
    'c64_1982': {'c64': 1, 'raster': 1, 'px': 4, 'scan': 0.25},
    'mac1984': {'mac': 1, 'px': 3},
    'amber1984': {'amber': 1, 'scan': 0.45, 'vignette': 0.45},
    'web2001': {'websafe': 1, 'px': 2},
    'neural2016': {'feature': 1},
    'glitch': {'glitch': 1},
    'zine': {'riso': 1},
    'painterly': {'kuwahara': 1, 'vignette': 0.35},
    'poster': {'halftone': 1, 'vignette': 0.2},                  # a CMYK protest poster / newsprint (daylit scenes)
    'poster_night': {'halftone': 1, 'lift': 1.6, 'vignette': 0.2},   # the same for a night scene
    'crt': {'phosphor': 1},                                      # any picture on a curved CRT
    'crt_8bit': {'c64': 1, 'raster': 1, 'px': 4, 'phosphor': 1},     # the 8-bit palette and raster bars on a TV tube
    'storybook': {'toon': 1, 'vignette': 0.15},                  # cel bands + ink lines: a storybook plate
    'candle_film': {'halation': 1, 'vignette': 0.55},            # candle-lit film: halation, gate weave, grain
    'watercolor': {'watercolor': 1, 'vignette': 0.2},            # wet-paper watercolour (daylit scenes)
    'watercolor_night': {'watercolor': 1, 'lift': 1.1, 'vignette': 0.2},   # the same for a night scene
}

# print & paint palettes, authored in sRGB as they should read on screen (era_looks.js), as THREE.Color makes them
NEWS_PAPER = hex_lin('#ebe5d5')
NEWS_INK = [hex_lin('#1486c6'), hex_lin('#d02c74'), hex_lin('#f4d11a'), hex_lin('#1c1a19')]   # C M Y K
WC_PAPER = hex_lin('#f6f1e4')
TOON_INK = hex_lin('#2a1b14')
TOON_PAGE = hex_lin('#fbf4e4')
PAL = [hex_lin(h) for h in C64]

GROUP = 'eido_era_looks'
FONT = 'PressStart2P-Regular.ttf'


# ------------------------------------------------------------------------------------------------- presets
def _smooth(s):
    return s * s * (3.0 - 2.0 * s)


def apply_look(U, from_, to, s, frame=None):
    """Crossfade between two named looks (dicts of weights; s = 0..1, smoothstepped). The pixel grid snaps at the
    midpoint. U: the effect's uniforms (sockets: their default_value is set). frame: also key every weight there
    (px keyed CONSTANT), so a crossfade lives in the .blend."""
    e = _smooth(float(s))
    for k in KEYS_ALL:
        sock = U[k]
        sock.default_value = float(from_.get(k, 0.0)) * (1.0 - e) + float(to.get(k, 0.0)) * e
        if frame is not None:
            _key(sock, frame, 'LINEAR')
    U['px'].default_value = float(from_.get('px', 1.0) if e < 0.5 else to.get('px', 1.0))
    if frame is not None:
        _key(U['px'], frame, 'CONSTANT')
    return U


def crossfade(U, from_, to, frame_a, frame_b):
    """apply_look keyed on every frame from frame_a (all `from_`) to frame_b (all `to`): the WebGPU per-frame
    applyLook(U, from, to, s) with s running 0 -> 1, as keyframes."""
    n = max(1, int(frame_b) - int(frame_a))
    for i in range(n + 1):
        apply_look(U, from_, to, i / n, frame=int(frame_a) + i)
    return U


def set_look(U, look, frame=None):
    """One preset, all its weights (the others 0): apply_look(U, look, look, 1)."""
    return apply_look(U, look, look, 1.0, frame=frame)


def _key(sock, frame, interp):
    sock.keyframe_insert('default_value', frame=int(frame))
    tree = sock.id_data
    ad = tree.animation_data
    if not ad or not ad.action:
        return
    from .history import _fcurves
    path = sock.path_from_id('default_value')
    for fc in _fcurves(ad.action, tree):
        if fc.data_path == path:
            for k in fc.keyframe_points:
                if abs(k.co.x - frame) < 1e-6:
                    k.interpolation = interp
            fc.update()


# ------------------------------------------------------------------------------------------------- glyph atlas
def glyph_atlas(font_path=None):
    """The line printer's glyph atlas: RAMP drawn in Press Start 2P at 30 px, one 32 x 56 cell per glyph, white on
    black, as era_looks.js draws it on a canvas (textBaseline 'middle', 2 px low). Drawn here by Blender's own text
    renderer (blf) into an offscreen buffer and kept PACKED in the .blend, so a saved file renders on its own."""
    name = 'eido_era_glyphs'
    im = bpy.data.images.get(name)
    if im is not None and im.get('eido_ramp') == RAMP and im.get('eido_atlas') == 2:
        return im
    import blf
    import gpu
    from mathutils import Matrix
    if font_path is None:
        here = os.path.dirname(os.path.abspath(__file__))
        font_path = os.path.normpath(os.path.join(here, '..', '..', '..', '..', 'eidoverse', 'assets', 'fonts', FONT))
    gw, gh = 32, 56
    W, H = gw * len(RAMP), gh
    fid = blf.load(font_path)
    if fid < 0:
        raise FileNotFoundError(f'era_looks: cannot load the glyph font {font_path}')
    if bpy.app.background:
        try:
            gpu.init()                     # headless: the GPU module starts on demand (a no-op when it is up)
        except Exception:
            pass
    off = gpu.types.GPUOffScreen(W, H, format='RGBA32F')
    with off.bind():
        fb = gpu.state.active_framebuffer_get()
        fb.clear(color=(0.0, 0.0, 0.0, 1.0))
        with gpu.matrix.push_pop():
            gpu.matrix.load_matrix(Matrix.Identity(4))
            gpu.matrix.load_projection_matrix(Matrix(((2.0 / W, 0, 0, -1), (0, 2.0 / H, 0, -1), (0, 0, 1, 0),
                                                      (0, 0, 0, 1))))
            blf.size(fid, 30)
            blf.color(fid, 1.0, 1.0, 1.0, 1.0)
            # textBaseline 'middle' at gh / 2 + 2 puts one baseline under every glyph. Placed to match the WebGPU
            # harness's own canvas (@napi-rs/canvas, drawn with this code, 11-07): '@' inks rows 14-40 of 56 (top
            # down) in both; the glyph widths agree within a pixel
            _w, h_full = blf.dimensions(fid, '@')
            base = gh / 2.0 - h_full / 2.0 - 4.0
            for i, ch in enumerate(RAMP):
                w, _h = blf.dimensions(fid, ch)
                blf.position(fid, gw * i + gw / 2.0 - w / 2.0, base, 0)
                blf.draw(fid, ch)
        buf = fb.read_color(0, 0, W, H, 4, 0, 'FLOAT')
    buf.dimensions = W * H * 4
    px = list(buf)
    off.free()
    blf.unload(font_path)
    if im is None:
        im = bpy.data.images.new(name, W, H, float_buffer=True, alpha=False)
    elif tuple(im.size) != (W, H):
        im.scale(W, H)
    im.colorspace_settings.name = 'Non-Color'
    im.pixels.foreach_set(px)
    im.pack()
    im['eido_ramp'] = RAMP
    im['eido_atlas'] = 2                          # the placement above; an older file's atlas is redrawn
    im.use_fake_user = True
    return im


# ------------------------------------------------------------------------------------------------- the registry's hook
def make(scene, o, stage='era_looks', layer='over'):
    """Put the era pass in the scene's post chain (custom_effects.apply_to calls this). o: the effect's options (any
    weight in KEYS, px; Blender's build options persist_frames and cuts). Wires the source's Depth and Normal (toon),
    the scene's exposure (display space) and the persistence history (the last K input frames, keyed so no tap reads
    across a cut). Returns (node, {uniform: socket}, [History])."""
    from . import chain, display as D, history as HI
    fps = scene.render.fps / scene.render.fps_base
    K = persist_frames(fps) if o.get('persist_frames') is None else max(0, int(o['persist_frames']))
    grp = build(fps, K)
    t = chain.tree(scene)
    node = t.nodes.new('CompositorNodeGroup')
    node.node_tree = grp
    node.width = 220
    chain.add_stage(scene, layer, stage, node)
    for pname, has in (('Depth', 'HasDepth'), ('Normal', 'HasNormal')):
        s = chain.source_pass(scene, pname)
        if s is not None:
            t.links.new(s, node.inputs[pname])
            node.inputs[has].default_value = 1.0
    D.drive_exposure(scene, node.inputs['Exposure'])
    drive_far(scene, node.inputs['Far'])
    D.sync(scene)                                      # the display nodes take the scene's view transform and look
    node.inputs['Damp'].default_value = math.exp(-1.0 / (fps * 0.04))
    hist = []
    if K > 0:                                          # persist_frames=0: no CRT persistence, nothing on disk
        h = HI.History(scene, f'{stage}_in', tree=t, rider_of=stage)
        h.alpha_from(node.outputs['TubeOn'])           # each recorded frame says whether the CRT was on
        chain.relink(scene)
        for k in range(1, K + 1):
            img, _present = h.tap(t, k)
            t.links.new(img, node.inputs[f'Persist{k}'])
        cuts = o.get('cuts')
        if cuts is None:
            cuts = HI.scene_cuts(scene) + HI.camera_jumps(scene)   # camJumped(): > 0.6 m or > 10 deg in a frame
        h.set_cuts(cuts, t, fresh=node.inputs['Fresh'])
        hist.append(h)
    uniforms = {k: node.inputs[k] for k in KEYS + ['px']}
    uniforms['cam_far'] = node.inputs['Far']
    for k in KEYS + ['px']:
        if k in o:
            uniforms[k].default_value = float(o[k])
    return node, uniforms, hist


def drive_far(scene, socket):
    """A driver keeping the pass's far plane equal to the scene camera's clip end (WebGPU's camFar, updated every
    frame from the camera): where nothing was drawn the WebGPU depth read the far plane, so the storybook's sky
    clamps there too. Blender's Depth pass is metric, so the near plane has no part (no depth to unpack)."""
    try:
        socket.driver_remove('default_value')
    except (TypeError, RuntimeError):
        pass
    fc = socket.driver_add('default_value')
    d = fc.driver
    d.type = 'SCRIPTED'
    var = d.variables.new()
    var.name = 'far'
    var.type = 'SINGLE_PROP'
    var.targets[0].id_type = 'SCENE'
    var.targets[0].id = scene
    var.targets[0].data_path = 'camera.data.clip_end'
    d.expression = 'far'
    if scene.camera is not None and scene.camera.type == 'CAMERA':
        socket.default_value = scene.camera.data.clip_end
    return fc


# ------------------------------------------------------------------------------------------------- the pass
def persist_frames(fps):
    """How many earlier frames the phosphor persistence reads: damp = exp(-1 / (fps * 0.04)) per frame, and a value
    of 64 (far above a real scene's radiance) is under the AfterImage mask's 0.1 after this many."""
    d = math.exp(-1.0 / (fps * 0.04))
    return max(2, int(math.ceil(math.log(0.1 / 64.0) / math.log(d))))


def _ins(K):
    ins = [('Image', 'C', (0, 0, 0, 1)), ('Depth', 'S', 1.0), ('Normal', 'V', (0.0, 0.0, 1.0)), ('HasDepth', 'S', 0.0),
           ('HasNormal', 'S', 0.0), ('Exposure', 'S', 0.0), ('Far', 'S', 1000.0)]
    ins += [(k, 'S', 0.0) for k in KEYS] + [('px', 'S', 1.0), ('Damp', 'S', 0.4), ('Fresh', 'S', 0.0)]
    ins += [(f'Persist{k}', 'C', (0, 0, 0, 0)) for k in range(1, K + 1)]
    return ins


def build(fps=24.0, K=None, rebuild=False):
    """The era pass as one node group (built once per K; `rebuild` forces it)."""
    K = persist_frames(fps) if K is None else int(K)
    atlas = glyph_atlas()
    # version 2: the Far input and the TubeOn output (a file's older group is rebuilt)
    return fn(f'{GROUP}_k{K}', _ins(K), [('Image', 'C'), ('TubeOn', 'S')], lambda g, a: _era(g, a, K, atlas),
              rebuild=rebuild, version=2)


class _Ctx:
    """What the look functions share: the builder, the inputs and the common fields of the pass."""


def _era(g, a, K, atlas):
    from . import display as D
    x = _Ctx()
    x.g, x.a, x.K = g, a, K
    orig = a['Image']
    # NaN -> 0, +Inf -> 65504 (half float's largest), before anything reads the frame. The WebGPU pass skipped a look
    # that was off; here every look is evaluated and mixed in by its weight, and 0 x Inf is NaN, so one non-finite
    # pixel would spread through the blur pyramids into every pixel of a look weighted 0 (the NaN clamp).
    img = g.image(g.sanitize(g.c(orig), hi=65504.0))
    x.img = img
    co = g.coords(img)
    x.co = co
    W, H, S = co.W, co.H, co.S
    x.W, x.H, x.S, x.res = W, H, S, co.res
    uv0, fc = co.uv, co.fc
    x.uv0, x.fc = uv0, fc
    t, frame = g.time()
    x.t, x.frame = t, frame
    w = {k: a[k] for k in KEYS}
    x.w = w
    ev = a['Exposure']
    x.ev = ev
    x.to_disp = lambda c: D.to_disp(g, c, ev)
    x.to_print = lambda c: D.to_disp(g, g.v(c) * g.pow(2.0, w['lift']), ev)
    x.from_disp = lambda d: g.sanitize(D.from_disp(g, d, ev))
    tap = lambda uv: g.tap(img, uv)                                 # noqa: E731
    x.tap = tap

    # --- pixel grid (C64 / Mac)
    px = g.max(a['px'], 1.0)
    x.px = px
    cell = g.vec(px / W, px / H)
    pxon = g.step(1.5, px)
    snapped = (g.floor(uv0 / cell) + g.v((0.5, 0.5, 0.0))) * cell
    suv = g.mix(uv0, snapped, pxon)
    pix0 = g.floor(fc / px)
    # --- glitch: tear bands, split chroma
    hb = g.hash(g.floor(uv0.y * 40.0) + g.floor(t * 20.0) * 131.0)
    tear = g.step(0.82, hb) * (hb - 0.5) * 0.10 * w['glitch']
    suv = suv + g.vec(tear, 0.0)
    # --- halation: gate weave, a slow wander plus a jolt per 24 fps film frame (CPU-driven there, Scene Time here)
    ff = g.floor(t * 24.0)
    jx, jy = g.hash(ff) - 0.5, g.hash(ff + 7919.0) - 0.5
    weave = g.vec(S * (0.42 * g.sin(t * 1.9 + 0.3) + 0.22 * g.sin(t * 5.3 + 1.1) + 0.45 * jx),
                  S * (0.55 * g.sin(t * 1.3 + 2.0) + 0.3 * g.sin(t * 4.1) + 0.6 * jy))
    suv = suv + weave * w['halation'] / x.res
    # --- phosphor: curved glass; the beam samples and holds each scanline's centre row
    phos = w['phosphor']
    pon = g.math('GREATER_THAN', phos, 0.001)                     # If(u.phosphor.greaterThan(0.001))
    x.pon = pon
    c = uv0 * 2.0 - g.v((1.0, 1.0, 0.0))
    cx, cy = c.x, c.y
    c = g.vec(cx * (1.0 + cy * cy * 0.045 * phos), cy * (1.0 + cx * cx * 0.065 * phos))
    crtW = c * 0.5 + g.v((0.5, 0.5, 0.0))
    x.crtW = crtW
    q = g.abs(crtW - g.v((0.5, 0.5, 0.0))) * x.res
    rad = 34.0 * S
    sd = g.length(g.max(q - x.res * 0.5 + g.s2(rad), g.v((0.0, 0.0, 0.0)))) - rad
    x.crtIn = 1.0 - g.smoothstep(-1.5 * S, 0.5 * S, sd)
    pix = g.mix(pix0, g.floor(crtW * x.res / px), pon)
    lp = g.max(px, 4.0 * S)
    yl = crtW.y * H / lp
    x.crtY = g.fract(yl) - 0.5
    sxp = g.mix(crtW.x, (g.floor(crtW.x / cell.x) + 0.5) * cell.x, g.step(1.5, px))
    suv_ph = g.vec(sxp + tear, (g.floor(yl) + 0.5) * lp / H)
    suv = g.mix(suv, suv_ph, pon)
    x.suv, x.pix = suv, pix
    ca = w['glitch'] * 0.006 + w['riso'] * 0.0035
    base = g.tap(img, suv)
    x.base_alpha = g.alpha(g.tap_rgba(orig, suv))                 # vec4(outc, base.a): the frame's own alpha
    split = g.vec(tap(suv + g.vec(ca, 0.0)).x, base.y, tap(suv - g.vec(ca, 0.0)).z)
    col = g.mix(base, split, g.min(w['glitch'] + w['riso'], 1.0))
    # --- phosphor: the three guns converge a little off, more toward the sides of the tube
    cv = g.vec((0.5 + g.abs(crtW.x - 0.5) * 2.6) * S * phos / W, 0.0)
    col = g.mix(col, g.vec(tap(suv + cv).x, col.y, tap(suv - cv).z), pon)
    x.base = base
    # --- kuwahara (painterly): 4 quadrants, radius 3, least-variance mean
    col = g.mix(col, g.call(_kuwahara_fn(), Image=img)['best'], w['kuwahara'])
    x.col = col

    lum = g.lum(col)
    plum = g.sqrt(g.clamp(lum))
    thr = bayer4(g, pix)
    x.lum, x.plum, x.thr = lum, plum, thr

    # --- single-hue looks
    looks = {}
    looks['sepia'] = g.vec(lum * 1.10, lum * 0.86, lum * 0.58)
    decoK = g.smoothstep(0.08, 0.95, plum)
    looks['deco'] = g.mix((0.03, 0.018, 0.01), (1.05, 0.72, 0.30), decoK) * g.mix(0.6, 1.35, decoK)
    looks['bw'] = g.vec(lum, lum, lum)
    looks['vector'] = g.vec(lum * 0.18, lum * 1.30, lum * 0.38)
    looks['vfd'] = g.vec(lum * 0.30, lum * 1.20, lum * 1.02)
    looks['amber'] = g.vec(lum * 1.30, lum * 0.70, lum * 0.10)
    bit = g.step(thr, plum)
    looks['mac'] = g.vec(bit, bit, bit) * 0.92
    # web-safe: 6 levels per channel (0, 51, ..., 255) with ordered dither
    qv = g.floor(g.sqrt(g.clamp(col, 0.0, 1.0)) * 5.0 + g.splat(thr)) / 5.0
    looks['websafe'] = qv * qv
    looks['c64'] = g.call(_c64_fn(), Col=col, Thr=thr)['c']
    looks['riso'] = _riso(x)
    looks['halftone'] = g.call(_halftone_fn(), **_paint_args(x))['c']
    looks['toon'] = g.call(_toon_fn(), **_paint_args(x), Depth=a['Depth'], Normal=a['Normal'],
                           HasDepth=a['HasDepth'], HasNormal=a['HasNormal'], Far=a['Far'])['c']
    mB = g.mips(img, None)                                        # blurBN: the whole input
    x.mB = mB
    looks['watercolor'] = g.call(_watercolor_fn(), **_paint_args(x), B0=mB[0], B1=mB[1])['c']

    # --- blend the colour looks
    order = ['sepia', 'deco', 'bw', 'vector', 'vfd', 'amber', 'mac', 'c64', 'websafe', 'riso', 'halftone', 'toon',
             'watercolor']
    ws = None
    for k in ['sepia', 'deco', 'bw', 'vector', 'vfd', 'amber', 'mac', 'c64', 'websafe', 'riso', 'halftone', 'toon',
              'watercolor']:
        ws = w[k] if ws is None else ws + w[k]
    norm = g.max(ws, 1.0)
    outc = col * g.clamp(1.0 - ws, 0.0, 1.0)
    for k in order:
        outc = outc + g.sanitize(looks[k]) * (w[k] / norm)

    # --- deco sunburst: rays fanning from (0.5, -0.15) (uv y down: above the top of the frame)
    d = (uv0 - g.v((0.5, -0.15, 0.0))) * g.vec(W / H, 1.0)
    ang = g.atan2(d.y, d.x)
    rays = g.step(0.5, g.fract(ang * (24.0 / 6.2832)))
    outc = outc * g.mix(1.0, g.mix(0.78, 1.12, rays), w['deco'] * 0.5)

    # --- C64 raster bars behind the subject (the demoscene's copper bars fill the dark)
    outc = _raster_mix(x, outc)

    # --- neural feature map: false-colour Sobel over a darkened, posterized field
    outc = g.mix(outc, _feature(x), w['feature'])
    # --- line printer: glyph per cell, black ink on green-bar fanfold paper
    outc = g.mix(outc, _ascii(x, atlas), w['ascii'])
    # --- halation: candle-lit film
    mG = g.mips(img, 0.55, 1.3)                                   # glowBN: highlights only
    film = g.call(_halation_fn(), Image=img, Outc=outc, Suv=suv, Frame=frame,
                  G0=mG[0], G1=mG[1], G2=mG[2], G3=mG[3], G4=mG[4])['film']
    outc = g.mix(outc, film, w['halation'])
    # --- phosphor: the picture on a CRT
    tube = _phosphor(x, outc)
    outc = g.mix(outc, tube, phos)

    # --- film layers
    outc = outc * (1.0 + (g.hash3(pix.x, pix.y, frame) - 0.5) * (w['grain'] + w['riso'] * 0.6) * 0.45)
    outc = outc * (1.0 + (g.hash(frame * 13.0 + 7.0) - 0.5) * w['flicker'] * 0.22)
    sl = g.abs(g.fract(uv0.y * H * 0.5) - 0.5) * 2.0
    outc = outc * (1.0 - w['scan'] * 0.38 * sl)
    r = g.length(uv0 - g.v((0.5, 0.5, 0.0))) * 1.35
    outc = outc * g.mix(1.0, 1.0 - g.smoothstep(0.35, 1.05, r), w['vignette'])
    return {'Image': g.rgba(outc, x.base_alpha), 'TubeOn': pon}


def _paint_args(x):
    """The inputs every print / paint sub-group takes."""
    return dict(Image=x.img, Suv=x.suv, Exposure=x.ev, Lift=x.w['lift'])


# ------------------------------------------------------------------------------------------------- kuwahara
def _kuwahara_fn():
    def body(g, a):
        img = a['Image']
        co = g.coords(img)
        S = co.S
        cache = {}

        def tap(i, j):
            if (i, j) not in cache:
                ox = 0.0 if i == 0 else i * 2.6 * S / co.W
                oy = 0.0 if j == 0 else j * 2.6 * S / co.H
                cache[(i, j)] = g.tap(img, co.uv if i == j == 0 else co.uv + g.vec(ox, oy))
            return cache[(i, j)]
        best, best_var = g.v((0.0, 0.0, 0.0)), 1e9
        R = 3
        for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            acc, acc2 = None, None
            for j in range(R + 1):
                for i in range(R + 1):
                    cc = tap(sx * i, sy * j)
                    lc = g.lum(cc)
                    acc = cc if acc is None else acc + cc
                    acc2 = lc * lc if acc2 is None else acc2 + lc * lc
            n = (R + 1) * (R + 1)
            mean = acc / float(n)
            lm = g.lum(mean)
            var = acc2 / float(n) - lm * lm
            better = g.step(var, best_var)
            best = g.mix(best, mean, better)
            best_var = g.min(best_var, var)
        return {'best': best}
    return fn('eido_era_kuwahara', [('Image', 'C', (0, 0, 0, 1))], [('best', 'V')], body)


# ------------------------------------------------------------------------------------------------- c64 palette
def _c64_fn():
    def body(g, a):
        col, thr = a['Col'], a['Thr']
        pc = g.sqrt(g.clamp(col, 0.0, 1.0)) + g.splat((thr - 0.5) * 0.12)
        best = g.v(PAL[0])
        dd = pc - g.v(PAL[0])
        bd = g.dot(dd, dd)
        for p in PAL[1:]:
            dv = pc - g.v(p)
            d = g.dot(dv, dv)
            better = g.step(d, bd)
            best = g.mix(best, g.v(p), better)
            bd = g.min(bd, d)
        return {'c': best * best}
    return fn('eido_era_c64', [('Col', 'V', (0, 0, 0)), ('Thr', 'S', 0.5)], [('c', 'V')], body)


# ------------------------------------------------------------------------------------------------- riso
def _riso(x):
    g, fc, S, plum, thr = x.g, x.fc, x.S, x.plum, x.thr
    paper = (0.93, 0.9, 0.84)
    rot = g.vec(fc.x * 0.866 - fc.y * 0.5, fc.x * 0.5 + fc.y * 0.866) / (6.0 * S)
    halft = g.length(g.fract(rot) - g.v((0.5, 0.5, 0.0)))
    mid = g.smoothstep(0.08, 0.5, plum) * (1.0 - g.smoothstep(0.55, 0.95, plum))
    dotsA = g.step(halft, mid * 0.62)                              # pink halftone on the midtones
    lumB = g.lum(x.tap(x.uv0 + g.v((0.004, -0.0028, 0.0))))        # blue plate, misregistered
    shadow = 1.0 - g.smoothstep(0.12, 0.42, g.sqrt(g.clamp(lumB)))
    dotsB = g.step(thr * 0.9, shadow)
    return g.v(paper) * g.mix((1.0, 1.0, 1.0), (1.0, 0.36, 0.62), dotsA * 0.9) \
        * g.mix((1.0, 1.0, 1.0), (0.08, 0.2, 0.62), dotsB * 0.92)


# ------------------------------------------------------------------------------------------------- halftone
_PAINT_INS = [('Image', 'C', (0, 0, 0, 1)), ('Suv', 'V', (0.5, 0.5, 0.0)), ('Exposure', 'S', 0.0), ('Lift', 'S', 0.0)]


def _paint_ctx(g, a):
    from . import display as D
    img = a['Image']
    co = g.coords(img)
    ev, lift = a['Exposure'], a['Lift']
    to_print = lambda c: D.to_disp(g, g.v(c) * g.pow(2.0, lift), ev)       # noqa: E731
    from_disp = lambda d: g.sanitize(D.from_disp(g, d, ev))                # noqa: E731
    return img, co, to_print, from_disp


def _halftone_fn():
    """Newsprint / protest poster: the key (black) is line art, under it four rotated, misregistered dot screens
    whose inks multiply as transmittances on newsprint, pressed a little unevenly."""
    def body(g, a):
        img, co, to_print, from_disp = _paint_ctx(g, a)
        suv, S, fc = a['Suv'], co.S, co.fc
        cellPx = 8.0 * S
        plates = ((15, (1.6, -1.0), 0), (75, (-1.2, 0.8), 1), (0, (2.2, 1.3), 2), (45, (0.0, 0.0), 3))
        trans = g.v((1.0, 1.0, 1.0))
        dMean = None
        for angDeg, (ox, oy), ch in plates:
            o = g.vec(ox * S / co.W, oy * S / co.H)
            dq = g.vec(0.24 * cellPx / co.W, 0.17 * cellPx / co.H)
            cs = (g.tap(img, suv + o + dq) + g.tap(img, suv + o - dq)) * 0.5
            d = g.sqrt(g.clamp(to_print(cs), 0.0, 1.0))                     # ~sRGB-encoded tone
            d2 = g.smoothstep(0.04, 0.96, d) * 0.6 + d * d * 0.4               # poster snap
            k0 = 1.0 - g.max3(d2)
            k = k0 * g.smoothstep(0.08, 0.7, k0)                               # black comes in early
            if ch == 3:
                a0 = k
            else:                                       # GCR, stabilized: under a near-full black no colour is laid
                comp = g.comps(d2)[ch]
                a0 = g.clamp((1.0 - comp - k) / g.max(1.0 - k, 0.12), 0.0, 1.0)
            aa_ = a0 + a0 * (1.0 - a0) * 0.35                                  # dot gain on soft stock
            ang = angDeg * math.pi / 180.0
            cA, sA = math.cos(ang), math.sin(ang)
            sqx = (fc.x * cA + fc.y * sA) / cellPx
            sqy = (fc.y * cA - fc.x * sA) / cellPx
            fx_, fy_ = g.fract(sqx) - 0.5, g.fract(sqy) - 0.5
            spot = 0.5 + (g.cos(fx_ * 6.2831853) + g.cos(fy_ * 6.2831853)) * 0.25
            # fwidth(spot), analytic: d(spot)/dx, d(spot)/dy of the rotated cosine screen
            sx_, sy_ = g.sin(fx_ * 6.2831853), g.sin(fy_ * 6.2831853)
            kk = 0.25 * 6.2831853 / cellPx
            dx = (sx_ * cA - sy_ * sA) * kk
            dy = (sx_ * sA + sy_ * cA) * kk
            fw = g.abs(dx) + g.abs(dy)
            aa = g.clamp(fw * 0.6, 0.004, 0.12)
            th = g.mix(-aa, aa + 1.0, 1.0 - aa_)                               # 0% = no ink, 100% = solid
            ink = g.smoothstep(th - aa, th + aa, spot)
            press = g.vnoise(g.vec(fc.x / (64.0 * S) + (37.0 + ch * 71.0), fc.y / (64.0 * S) + (11.0 + ch * 23.0)),
                             90 + ch)
            T = tuple(v / p for v, p in zip(NEWS_INK[ch], NEWS_PAPER))
            trans = trans * g.mix((1.0, 1.0, 1.0), T, g.min(ink * (press * 0.16 + 0.86), 1.0))
            if ch == 3:
                dMean = g.lum(d)
        # the key: solid black wherever the sharp picture is darkest, and on thin dark detail
        dk = g.sqrt(g.clamp(g.lum(to_print(g.tap(img, suv))), 0.0, 1.0))
        keyA = g.max(1.0 - g.smoothstep(0.1, 0.19, dk), g.smoothstep(0.1, 0.22, dMean - dk) * 0.92)
        T3 = tuple(v / p for v, p in zip(NEWS_INK[3], NEWS_PAPER))
        trans = trans * g.mix((1.0, 1.0, 1.0), T3, keyA)
        fib = (g.vnoise(g.vec(fc.x / (1.4 * S) + 500.0, fc.y / (1.4 * S) + 300.0), 7) - 0.5) * 0.05 \
            + (g.vnoise(g.vec(fc.x / (6.0 * S) + 900.0, fc.y / (6.0 * S) + 100.0), 8) - 0.5) * 0.06
        return {'c': from_disp(g.clamp(g.v(NEWS_PAPER) * trans * (fib + 1.0), 0.0, 1.0))}
    return fn('eido_era_halftone', _PAINT_INS, [('c', 'V')], body)


# ------------------------------------------------------------------------------------------------- toon
def _toon_fn():
    """Storybook cel: soft luminance bands (hue kept), ink wherever depth creases or jumps, normals turn or colour
    steps hard; lines thin out with distance so a far field stays painted."""
    def body(g, a):
        img, co, to_print, from_disp = _paint_ctx(g, a)
        suv, S, fc = a['Suv'], co.S, co.fc
        dimg = g.image(a['Depth'])
        nimg = g.image(a['Normal'])
        hasD, hasN, far = a['HasDepth'], a['HasNormal'], a['Far']

        def zAt(at):          # view depth (m), the far plane where nothing was drawn (WebGPU's perspectiveDepthToViewZ
            # of a cleared depth buffer); 1.0 without a depth pass, as WebGPU's without sceneDepth
            z = g.min(far, g.max(0.0, g.tap(dimg, at).x))
            return g.mix(1.0, z, hasD)
        r1 = g.mix(2.3 * S, 1.4 * S, g.smoothstep(2.5, 9.0, zAt(suv)))
        r2 = r1 * 3.0
        taps = ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))
        Ds, Ps, Zs, Ns = [], [], [], []
        for dx, dy in taps:
            at = suv + g.vec(dx * r1 / co.W, dy * r1 / co.H) if (dx, dy) != (0, 0) else suv
            D = to_print(g.tap(img, at))
            Ds.append(D)
            Ps.append(g.sqrt(g.lum(D)))
            Zs.append(zAt(at))
            n = g.tap(nimg, at)
            Ns.append(g.mix((0.0, 0.0, 1.0), n, hasN))
        zc = g.max(Zs[0], 1e-4)
        # flatten small texture into the fill: depth-aware 5-tap mean
        acc, wsum = Ds[0] * 2.0, 2.0
        for i in range(1, 5):
            wgt = 1.0 - g.smoothstep(0.01, 0.04, g.abs(Zs[i] - zc) / zc)
            acc = acc + Ds[i] * wgt
            wsum = wsum + wgt
        Dm = acc / wsum
        # bands on perceptual value: four soft steps, shadows never fall to black
        Lp = g.sqrt(g.max(g.lum(Dm), 1e-5))
        lv, tv, sw = (0.3, 0.52, 0.73, 0.93), (0.36, 0.6, 0.81), 0.035
        Lq = lv[0]
        for i in range(3):
            Lq = Lq + g.smoothstep(tv[i] - sw, tv[i] + sw, Lp) * (lv[i + 1] - lv[i])
        Lq = g.mix(Lp, Lq, g.smoothstep(0.07, 0.24, Lp))                # true darks stay dark (silhouettes)
        Lq = g.mix(Lq, Lp, g.smoothstep(150.0, 1500.0, zc))             # the sky keeps its painted gradient
        scale = Lq * Lq / (Lp * Lp)
        grey = g.lum(Dm)
        cel = g.mix(g.splat(grey), Dm, 1.12) * scale                   # hue kept, a little chroma
        shade = 1.0 - g.smoothstep(0.3, 0.55, Lq)                      # cool the shadow band
        cel = cel * g.mix((1.02, 1.0, 0.96), (0.88, 0.9, 1.08), shade)
        # ink: lines on the near side of a silhouette, only on shapes wider than ~r2
        eD, thin, eC, cont = 0.0, 0.0, 0.0, 1.0
        for i, j, ax in ((1, 2, (1, 0)), (3, 4, (0, 1))):
            fa, fb = (Zs[i] - zc) / zc, (Zs[j] - zc) / zc
            off = g.vec(ax[0] * r2 / co.W, ax[1] * r2 / co.H)
            za, zb = zAt(suv + off), zAt(suv - off)
            th = g.smoothstep(0.03, 0.12, g.min(za - zc, zb - zc) / zc)
            eD = g.max(eD, g.smoothstep(0.03, 0.12, g.max(fa, fb)) * (1.0 - th))
            thin = g.max(thin, th)
            cont = cont * (1.0 - g.smoothstep(0.01, 0.03, g.max(g.abs(fa), g.abs(fb))))
            pa, pb = Ps[i] - Ps[0], Ps[j] - Ps[0]
            ridge = g.step(pa, 0.0) * g.step(pb, 0.0) * g.min(g.abs(pa), g.abs(pb))
            eC = g.max(eC, g.max(g.abs(pa), g.abs(pb)) - ridge)
        nd = 0.0
        for i in range(1, 5):
            nd = nd + (1.0 - g.dot(Ns[0], Ns[i]))
        eN = g.smoothstep(0.35, 0.9, nd) * cont * 0.8 * (1.0 - g.smoothstep(3.5, 11.0, zc)) * hasN
        eCol = g.smoothstep(0.2, 0.4, eC) * 0.9 * (1.0 - g.smoothstep(3.0, 10.0, zc))
        fade = 1.0 - g.smoothstep(5.0, 30.0, zc) * 0.7                  # the far field: a lighter pen
        inkA = g.clamp(g.max(g.max(eD, eN), eCol) * (1.0 - thin * 0.85) * fade, 0.0, 1.0)
        # printed on a warm storybook page, with a whisper of paper grain
        grain = (g.vnoise(g.vec(fc.x / (1.8 * S) + 700.0, fc.y / (1.8 * S) + 900.0), 61) - 0.5) * 0.035
        page = g.mix((1.0, 1.0, 1.0), TOON_PAGE, 0.7) * (grain + 1.0)
        return {'c': from_disp(g.clamp(g.mix(cel * page, TOON_INK, inkA), 0.0, 1.0))}
    ins = _PAINT_INS + [('Depth', 'S', 1.0), ('Normal', 'V', (0.0, 0.0, 1.0)), ('HasDepth', 'S', 0.0),
                        ('HasNormal', 'S', 0.0), ('Far', 'S', 1000.0)]
    return fn('eido_era_toon', ins, [('c', 'V')], body, version=2)


# ------------------------------------------------------------------------------------------------- watercolor
def _watercolor_fn():
    """Wet paper: washes wander, wet patches bleed, pigment piles up on the dark side of every wash edge and settles
    into the paper tooth (Bousseau et al. 2006: c' = c - (c - c^2)(d - 1)); the palest washes let the grain show."""
    def body(g, a):
        img, co, to_print, from_disp = _paint_ctx(g, a)
        suv, S, fc = a['Suv'], co.S, co.fc
        ppx, ppy = fc.x / S + 311.0, fc.y / S + 173.0                     # paper coords (1080p px)
        pp = g.vec(ppx, ppy)

        def pn(div, salt):
            return g.vnoise(pp / div, salt)
        wob = g.vec((pn(38.0, 11) - 0.5) * 5.0 * S / co.W, (pn(38.0, 29) - 0.5) * 5.0 * S / co.H)
        uw = suv + wob
        c0 = to_print(g.tap(img, uw))
        b0 = to_print(g.tap(a['B0'], uw))
        b1 = to_print(g.tap(a['B1'], uw))

        def P(c):
            return g.sqrt(g.max(g.lum(c), 1e-5))
        # a wash, not a photograph: low-contrast texture melts into the local mean, strong edges stay
        flat = 1.0 - g.smoothstep(0.035, 0.13, g.abs(P(c0) - P(b0)))
        C = g.mix(c0, b0, flat * 0.85)
        # wet-in-wet: in the wet patches colour (not value) runs into its neighbours
        wet = g.smoothstep(0.4, 0.78, pn(90.0, 41)) * 0.7
        lc, l1 = g.lum(C), g.lum(b1)
        C = g.max(C + (b1 - g.splat(l1) - (C - g.splat(lc))) * wet, g.v((0.0, 0.0, 0.0)))
        # glazes: value settles into five soft layers on wobbling thresholds
        v = P(C)
        t0 = v * 4.0
        wAmp = g.min(g.fwidth(t0, co) * 45.0, 0.3)          # wobble only where the value moves: no islands
        tq = t0 + (pn(55.0, 23) - 0.5) * wAmp
        fq = g.fract(tq)
        vq = (g.floor(tq) + g.smoothstep(0.4, 0.6, fq)) / 4.0
        vg = g.mix(v, vq, 0.55)
        C = C * (vg * vg / g.max(v * v, 1e-5))
        fw = g.max(g.fwidth(tq, co), 1e-3)
        rim = g.smoothstep(0.5 - 0.02, 0.5, fq + fw * 2.2) * (1.0 - g.smoothstep(0.5, 0.52, fq))
        Lb = P(b1)
        edge = g.clamp((Lb - v) * 3.0, 0.0, 1.0)
        # pigment density (Bousseau et al. 2006): c' = c - (c - c^2)(d - 1)
        hp = pn(2.3, 3) * 0.6 + pn(6.5, 7) * 0.4                          # paper height
        turb = pn(130.0, 13) * 0.65 + pn(34.0, 17) * 0.35
        pig = 1.0 - v
        dens = 1.0 + rim * 0.38 + edge * 0.5 + (turb - 0.5) * 0.5 + (0.55 - hp) * 1.25 * pig
        cp = g.sqrt(g.clamp(C, 0.0, 1.0))
        cm = g.clamp(cp - (cp - cp * cp) * (dens - 1.0), 0.0, 1.0)
        # transparent pigment: the page glows through, and the tooth shows in the palest washes
        cm = g.mix(cm, (1.0, 1.0, 1.0), g.smoothstep(0.78, 0.93, hp) * g.smoothstep(0.72, 0.96, v) * 0.3)
        out = g.v(WC_PAPER) * g.max(cm * cm, g.v((0.04, 0.04, 0.04))) * ((hp - 0.5) * (0.07 + pig * 0.28) + 1.0)
        return {'c': from_disp(g.clamp(out, 0.0, 1.0))}
    ins = _PAINT_INS + [('B0', 'C', (0, 0, 0, 1)), ('B1', 'C', (0, 0, 0, 1))]
    return fn('eido_era_watercolor', ins, [('c', 'V')], body)


# ------------------------------------------------------------------------------------------------- raster, feature
def _raster_mix(x, outc):
    g, uv0, t, w = x.g, x.uv0, x.t, x.w
    bars = g.v((0.0, 0.0, 0.0))
    ramp = ((0.0, 0.0, 0.67), (0.0, 0.53, 1.0), (0.67, 1.0, 0.93), (1.0, 1.0, 1.0))
    for i in range(5):
        cy = 0.5 + 0.36 * g.sin(t * 1.25 + i * 0.62)
        z = (uv0.y - cy) / 0.032
        k = g.exp(-(z * z))
        band = g.floor(k * 3.99)
        c = g.mix(g.mix(ramp[0], ramp[1], g.step(1.0, band)), g.mix(ramp[2], ramp[3], g.step(3.0, band)),
                  g.step(2.0, band))
        bars = g.max(bars, c * g.step(0.05, k))
    dark = 1.0 - g.smoothstep(0.015, 0.07, x.lum)
    return g.mix(outc, bars * bars, dark * w['raster'])


def _feature(x):
    g, uv0, S, fc = x.g, x.uv0, x.S, x.fc
    ox, oy = 1.5 * S / x.W, 1.5 * S / x.H

    def L(dx, dy):
        return g.lum(x.tap(uv0 + g.vec(dx * ox, dy * oy)))
    l = {(dx, dy): L(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0)}
    gx = l[(1, -1)] + l[(1, 0)] * 2.0 + l[(1, 1)] - l[(-1, -1)] - l[(-1, 0)] * 2.0 - l[(-1, 1)]
    gy = l[(-1, 1)] + l[(0, 1)] * 2.0 + l[(1, 1)] - l[(-1, -1)] - l[(0, -1)] * 2.0 - l[(1, -1)]
    mag = g.clamp(g.sqrt(gx * gx + gy * gy) * 3.0, 0.0, 1.0)
    an = g.atan2(gy, gx) / 6.2832 + 0.5
    hueC = g.vec(g.abs(an * 6.0 - 3.0) - 1.0, 2.0 - g.abs(an * 6.0 - 2.0), 2.0 - g.abs(an * 6.0 - 4.0))
    edge = g.clamp(hueC, 0.0, 1.0) * (mag * 2.2)
    tile = g.step(0.97, g.max(g.fract(fc.x / (64.0 * S)), g.fract(fc.y / (64.0 * S))))
    field = g.v((0.5, 0.35, 0.9)) * (g.floor(x.plum * 4.0) / 4.0 * 0.22)
    return field + edge + g.v((0.1, 0.08, 0.2)) * tile


def _ascii(x, atlas):
    g, fc, S = x.g, x.fc, x.S
    csx, csy = 12.0 * S, 20.0 * S
    cix, ciy = g.floor(fc.x / csx), g.floor(fc.y / csy)
    clx, cly = g.fract(fc.x / csx), g.fract(fc.y / csy)
    cc = g.vec((cix + 0.5) * csx / x.W, (ciy + 0.5) * csy / x.H)
    L2 = g.lum(x.tap(cc))
    gi = g.floor(g.clamp(1.0 - g.sqrt(g.clamp(L2)) * 1.1, 0.0, 0.999) * float(len(RAMP)))
    # the atlas is stored upright, so the cell's top row reads the glyph's top: y down = cl.y
    an = g.node('CompositorNodeImage')
    an.image = atlas
    ink = g.tap(an.outputs['Image'], g.vec((gi + clx) / float(len(RAMP)), cly)).x
    barRow = g.mod(g.floor(ciy / 3.0), 2.0)
    pap = g.mix((0.95, 0.95, 0.9), (0.8, 0.9, 0.78), barRow)
    edgeHoles = g.step(fc.x, 22.0 * S) + g.step(x.W - 22.0 * S, fc.x)
    hx, hy = g.mod(fc.x, 22.0 * S) - 11.0 * S, g.mod(fc.y, 26.0 * S) - 13.0 * S
    hole = g.step(g.sqrt(hx * hx + hy * hy), 5.0 * S) * g.clamp(edgeHoles, 0.0, 1.0)
    printed = g.mix(pap, (0.06, 0.06, 0.09), ink * (1.0 - hole))
    return g.mix(printed, (0.02, 0.02, 0.02), hole)


# ------------------------------------------------------------------------------------------------- halation
def _halation_fn():
    """Candle-lit film: highlights bleed a red-orange halo (light through the emulsion, back off the base, into the
    red layer); warm print, lifted blacks, fine colour grain."""
    def body(g, a):
        img = a['Image']
        co = g.coords(img)
        S, fc, suv, outc, frame = co.S, co.fc, a['Suv'], a['Outc'], a['Frame']
        # the lens and emulsion are softer than a render: a quarter of a 1 px cross blur
        p1x, p1y = S / co.W, S / co.H
        soft = (g.tap(img, suv + g.vec(p1x, 0.0)) + g.tap(img, suv - g.vec(p1x, 0.0))
                + g.tap(img, suv + g.vec(0.0, p1y)) + g.tap(img, suv - g.vec(0.0, p1y))) * 0.25
        film = g.mix(outc, soft, 0.3)
        levels = [a[f'G{i}'] for i in range(5)]
        h0 = g.lum(g.tap(levels[0], suv))
        h1 = g.lum(g.tap(levels[1], suv))
        hc = g.lum(g.mip_composite(levels, suv))
        # orange next to the source, deep red further out (CineStill 800T without remjet)
        film = film + g.v((1.0, 0.36, 0.1)) * (h0 * 0.55) + g.v((1.0, 0.13, 0.035)) * (h1 * 1.5) \
            + g.v((1.0, 0.2, 0.06)) * (hc * 0.06)
        # print: warm highlights, cool lifted shadows (the base and a little fog)
        fl0 = g.lum(film)
        film = film * g.v((1.05, 1.0, 0.9)) + g.mix((0.0022, 0.0042, 0.0052), (0.004, 0.003, 0.0024),
                                                   g.smoothstep(0.0, 0.08, fl0))
        # grain: fine, clumped over ~2 px, mostly luma with some colour, strongest in the midtones
        fr = frame + 17.0
        gpx, gpy = fc.x / (1.15 * S) + 100.0, fc.y / (1.15 * S) + 100.0
        gn = g.vec(g.vnoise(g.vec(gpx + fr * 3.1, gpy + fr * 3.1), 71), g.vnoise(g.vec(gpx + fr * 5.3, gpy + fr * 5.3), 72),
                   g.vnoise(g.vec(gpx + fr * 7.7, gpy + fr * 7.7), 73))
        gN = (gn - g.v((0.5, 0.5, 0.5))) * 0.7 + g.splat((g.hash3(fc.x, fc.y, fr * 3.0) - 0.5) * 0.6)
        gm = g.mix(g.splat(g.dot(gN, (0.3333, 0.3333, 0.3333))), gN, 0.4)
        fl = g.sqrt(g.clamp(g.lum(film)))
        midW = g.smoothstep(0.02, 0.25, fl) * ((1.0 - g.smoothstep(0.55, 1.0, fl)) * 0.65 + 0.35)
        film = film * (gm * (0.34 * midW) + g.v((1.0, 1.0, 1.0)))
        return {'film': film}
    ins = [('Image', 'C', (0, 0, 0, 1)), ('Outc', 'V', (0, 0, 0)), ('Suv', 'V', (0.5, 0.5, 0.0)), ('Frame', 'S', 0.0)]
    ins += [(f'G{i}', 'C', (0, 0, 0, 1)) for i in range(5)]
    return fn('eido_era_halation', ins, [('film', 'V')], body)


# ------------------------------------------------------------------------------------------------- phosphor
def _phosphor(x, outc):
    """The picture on a CRT: each scanline a beam whose width swells with brightness, an RGB aperture grille (2 px
    stripes at 1080p), glass glow, a hum bar, persistence, and the curved, rounded tube face."""
    g, S, fc, crtW, t, a = x.g, x.S, x.fc, x.crtW, x.t, x.a
    Lr = g.sqrt(g.clamp(g.lum(outc)))
    sig = g.mix(0.17, 0.42, Lr)
    beam = g.exp(x.crtY * x.crtY / (sig * sig * -2.0))
    bnorm = g.clamp(sig * 2.5066, 0.42, 1.0)
    P = g.max(S, 1.0) * 6.0
    ph = g.fract(fc.x / P)

    def stripe(c0):
        return 1.0 - g.smoothstep(0.1, 0.2, g.abs(g.fract(ph - c0 + 0.5) - 0.5))
    mask = g.mix((0.42, 0.42, 0.42), (1.5, 1.5, 1.5), g.vec(stripe(1 / 6), stripe(0.5), stripe(5 / 6)))
    # light scattered in the glass: not masked, not scanned
    mB = x.mB
    glow = g.tap(mB[1], crtW) * 0.55 + g.tap(mB[2], crtW) * 0.35 + g.mip_composite(mB, crtW) * (0.1 / 3.0)
    # a faint hum bar rolling up the picture
    hf = g.fract(crtW.y * 0.8 - t * 0.09)
    hum = 1.0 + g.smoothstep(0.0, 0.5, hf) * (1.0 - g.smoothstep(0.5, 1.0, hf)) * 0.045
    sat = g.mix(g.splat(g.lum(outc)), outc, 1.1)
    # what was bright a moment ago still glows: three's AfterImage of the input, max over the last K frames
    cur = x.tap(x.suv)
    held = cur
    damp = a['Damp']
    # 0 on a cut frame: the persistence starts clean (camJumped). A recorded frame's alpha is 1 when it was rendered
    # with the tube on (0 when off, or never rendered): the frame k back counts only if every frame since was on,
    # as the WebGPU feedback restarted (damp 0) on the first frame the tube came on.
    valid = 1.0 - a['Fresh']
    for k in range(1, x.K + 1):
        rgba = g.tap_rgba(a[f'Persist{k}'], x.suv)
        valid = valid * g.alpha(rgba)
        hk = g.sanitize(g.c(rgba), hi=65504.0) * valid           # the recorded input is the raw frame: clamp it too
        # the frame k back survives the mask while it stays above 0.1: hk * damp^(k-1) > 0.1 (each step's max is
        # that same chain, so masking the max is masking it), and has faded by damp^k
        surv = g.step(g.splat(0.1), hk * g.pow(damp, float(k - 1)) if k > 1 else hk)
        held = g.max(held, hk * g.pow(damp, float(k)) * surv)
    sat = sat + g.max(g.min(held, g.v((1.0, 1.0, 1.0))) - cur, g.v((0.0, 0.0, 0.0))) * 0.5
    tube = g.max(sat, g.v((0.0, 0.0, 0.0))) * (beam / bnorm) * mask * (hum * 1.22) + glow * 0.24 \
        + g.v((0.0026, 0.0034, 0.003))                                  # the glass is never black
    e = crtW.x * crtW.y * (1.0 - crtW.x) * (1.0 - crtW.y) * 16.0
    return tube * (g.pow(g.clamp(e, 0.0, 1.0), 0.22) * x.crtIn)

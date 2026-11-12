"""look/post/custom_effects.py: the post-effect registry for Blender (CustomEffectsDeno, ported).

    from eidoblend.look.post import custom_effects as fx
    e = fx.apply_to(scene, 'glitch_bars,rgb_shift', {'glitch_bars': {'barFreq': 22, 'shift': 0.03, 'opacity': 0.85}})
    e.key('glitch_bars', 'opacity', 58, 0.0); e.key('glitch_bars', 'opacity', 60, 1.0)   # a keyed burst
    e.uniforms['rgb_shift']['amount'].default_value = 0.008      # a group input socket: set it, or key it
    fx.list()                                                    # {effect: what it is, its options}
    fx.list_effects()                                            # the names, as CustomEffectsDeno.listEffects()
    fx.register('my_look', build, params=[('amount', 1.0)])      # another package's effect, as register(name, fn)
    fx.applied(scene); fx.remove(scene, 'rgb_shift'); fx.clear(scene)   # what is applied; take effects out (a native
                                                                 # effect's scene-side changes are taken back too)
    e.uniforms.cut(120)                                          # a temporal effect's U.cut(): its history restarts

The registry keeps the WebGPU one's rules:
  - effects is a comma string or a list; every name must be registered (an unknown one raises, naming them all);
  - they chain in the order given, each seeing its predecessor's output (rtt() between stages there; one compositor
    graph here), split by LAYER: 'under' effects run before the overlay (a HUD), 'over' effects after it.
    ALWAYS_UNDER (nuclear_explosion, godrays, underwater) are locked under; DEFAULT_UNDER (depth_fog,
    retro_wireframe) start under; every other effect starts over; opts[name]['layer'] = 'under' | 'over' switches it;
  - the result's `uniforms` is the effect's own uniforms when ONE effect is applied (e.uniforms['opacity']), and keyed
    by effect name otherwise (e.uniforms['glitch_bars']['opacity']); e.uniforms[name] works either way;
  - update(t) and set_resolution(w, h) exist: Scene Time drives time inside the graph and the compositor follows the
    render size, so nothing is pushed per frame; update() copies the scene's view transform into the display-space
    looks again (call it after changing the view transform or look).
One difference: apply_to ADDS to the scene's chain (a set's bloom and the film's look both stay); the WebGPU applyTo
replaced the scene's effects on every call, which clear(scene) first gives.
Every WebGPU name is in the registry, each ported. The whole-frame passes have modules of their own (era_looks.py,
aeropittura.py, after_image.py); the screen effects (wavy, kaleidoscope, jitter, melt, dithering,
chromatic_aberration_alpha, bw_halftone, bleach_bypass, hash_blur, crt, old_bw_film, vhs_tape, rain_on_camera,
lensflare, anamorphic_flare, and full_toon, blueprint, cross_hatch, underwater, depth_fog's and focus_blur's screen
modes on the Depth and Normal passes) are groups in screen_effects.py; nuclear_explosion is the SDF volumes' cloud
(eidoblend.sdf.nuclear_explosion).

Options are the WebGPU effect's own (eidoverse/effects_tsl/<name>.js), snake_case; the camelCase spelling of a ported
scene is accepted (barFreq -> bar_freq). An option the effect does not know raises KeyError naming the ones it does; a
WebGPU option with no Blender counterpart is ignored with a printed warning saying why. Never silently.

The compositor groups port each WebGPU shader's maths node for node. They work on scene-linear light before AgX, as
the WebGPU hooks ran on the lit HDR frame before ACES. Every tap is a Map UV sample with the edges clamped (a WebGPU
texture's ClampToEdge), at UVs from Image Coordinates (Normalized = (pixel + 0.5) / size, so one pixel is
Normalized / (Pixel + 0.5), measured). Translate is not used for taps: it moves the image's domain, and a channel
combined with it inherits the shifted domain (measured: a bar at the frame edge, the unshifted channels clamped too).
    glitch_bars       horizontal bars scrolling (bar_freq, scroll_speed) down the frame; inside each, red and blue split
                      by a sin-driven shift; opacity
    rgb_shift         three's rgbShift: red at uv + amount (cos angle, sin angle), blue at uv - that (WebGPU's uv, y
                      down); opacity
    radial_blur       three's radialBlur: `count` taps toward (center_x, center_y) (WebGPU's uv: center_y from the
                      top), weight x decay^k, x exposure, added over the frame; opacity
(These three read y down the frame, as WebGPU's uv: this module's own _Coords run up, so they flip where y matters.)
    box_blur          three's boxBlur: a (2 size + 1)^2 grid of taps `separation` pixels apart, averaged; opacity
    sepia             three's sepia matrix (glfx.js), amount; opacity
    neon_edges        4-tap Laplacian of BT.601 luma, core + halo glowing in glow_color over the frame; opacity
    (old_bw_film, the silent-film pass with its simplex dust, is in screen_effects.py)
Native: what EEVEE does in the render is done there, not faked in post. The scene keeps a list of the native effects
applied and what each changed the first time, so remove() / clear() put the scene back (fog volume, lens, override).
    focus_blur        mode 'lens' (default): the camera's depth of field (focus_distance or focus_objects;
                      focal_length / bokeh_scale choose the f-stop that blurs as three's DepthOfFieldNode at full CoC:
                      fstop_for_blur; or fstop); mode 'screen': focus_blur.js as WebGPU ran it, three's
                      DepthOfFieldNode ported (screen_effects.focus_blur_screen), a chain stage
    nuclear_explosion the mushroom cloud as Volume objects (eidoblend.sdf.nuclear_explosion), baked over the frames
    depth_fog         mode 'volume' (default): a fog layer, a volume box (density per metre, color, noise_amount /
                      noise_scale), lit and shadowed by the scene, godrays come with it in sun; mode 'screen':
                      depth_fog.js as WebGPU ran it, a chain stage (screen_effects.depth_fog_screen)
    godrays           depth_fog's volume + volumetric shadows; light / strength / opacity set that light's volume
                      factor (strength / 0.5 x opacity); 'sun_beams' is the Glare fallback
    retro_wireframe   a view-layer material override and world override (screen_effects.py)
The pre-bloom flares (WebGPU's _autoEnhancePreBloomHook), three's nodes ported as groups in the 'prebloom' slot:
    lensflare         LensflareNode: ghosts of the highlights mirrored through the centre, at a quarter resolution
    anamorphic_flare  AnamorphicNode: a short horizontal streak of `samples` taps `scale` px apart, tinted `color`,
                      weighted by three's luminance() of the RGBA sample (Y + alpha: TSL pads the weights with 1.0)
Glare (the compositor's Glare node):
    bloom             'Bloom' in the chain's bloom slot (strength, radius = Glare Size, threshold)
    sun_beams         'Sun Beams' from a screen position (source=(x, y) 0..1)
Time comes from the compositor's Scene Time node: nothing is pushed per frame (FX.update only copies the scene's
view transform into the display-space looks again, display.sync).
"""
import builtins
import json
import re

import bpy

from . import chain

REGISTRY = {}
registry = REGISTRY                            # CustomEffectsDeno.registry
TAU = 6.283185307179586

# custom_effects_deno.js's layering: world effects under the overlay, signal effects over it
ALWAYS_UNDER = {'nuclear_explosion', 'godrays', 'underwater'}
DEFAULT_UNDER = {'depth_fog', 'retro_wireframe'}


def _snake(k):
    """barFreq -> bar_freq, centerX -> center_x, glowColor -> glow_color (snake_case stays as it is)."""
    return re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', str(k)).lower()


def _effect(name, slot=None, kind='group', params=(), build_opts=None, unsupported=None, aliases=None, doc='',
            undo=None, passthrough=False):
    """params: [(name, default, min, max)] keyable inputs (a tuple default is a colour); build_opts: {name: default}
    fixed when built (a loop count, a kernel size); unsupported: {WebGPU option: why it has no counterpart};
    aliases: {another spelling: the option it means}. slot: the chain slot; None = the WebGPU layer rule (layer_of).
    undo(scene): takes the effect's scene-side changes back (a fog volume, a material override, the bubbles, the
    lens's depth of field) when remove() / clear() take the effect out. passthrough: the options go to build as given
    (an effect whose own module validates them, camelCase too, and names the ones it knows)."""
    def deco(fn):
        REGISTRY[name] = {'build': fn, 'slot': slot, 'kind': kind, 'params': [*params],     # (list() is the API's)
                          'build_opts': dict(build_opts or {}), 'unsupported': dict(unsupported or {}),
                          'aliases': dict(aliases or {}), 'doc': doc, 'undo': undo, 'passthrough': bool(passthrough)}
        return fn
    return deco


def register(name, build, *, slot=None, kind='group', params=(), build_opts=None, unsupported=None, aliases=None,
             doc='', undo=None, passthrough=False):
    """CustomEffectsDeno.register(name, factory): add (or replace) an effect.
    kind 'group': build(scene, opts) returns a CompositorNodeTree whose first input and output are 'Image' and whose
        other inputs are `params`; apply_to puts a group node for it in the chain.
    kind 'pass': build(scene, opts, stage, layer) puts its own node in the chain (chain.add_stage) and returns
        (node, {uniform: socket}, [history.History]).
    kind 'native' (scene-side: a volume, a material override, the lens) or 'glare': build(scene, opts) returns
        (node or datablock, {uniform: socket}); undo(scene) takes a native effect back out (remove / clear).
    passthrough=True hands build the options as given (its module checks them)."""
    if not callable(build):
        raise TypeError(f'register({name!r}): build must be a function')
    _effect(name, slot=slot, kind=kind, params=params, build_opts=build_opts, unsupported=unsupported,
            aliases=aliases, doc=doc, undo=undo, passthrough=passthrough)(build)
    return REGISTRY[name]


def layer_of(name, opts=None):
    """custom_effects_deno.js layerOf: 'under' or 'over' for an effect (opts may switch it unless it is locked)."""
    if name in ALWAYS_UNDER:
        return 'under'
    lay = (opts or {}).get('layer')
    if lay in ('under', 'over'):
        return lay
    return 'under' if name in DEFAULT_UNDER else 'over'


def list_effects():
    """The registered names (CustomEffectsDeno.listEffects / .list in the WebGPU edition)."""
    return [*REGISTRY]


def list():                                    # noqa: A001 (the WebGPU API's name)
    """{effect: 'kind: what it does; options ...'} (an effect whose module checks its own options says so)."""
    out = {}
    for k, v in REGISTRY.items():
        opts = [p[0] for p in v['params']] + sorted(v['build_opts'])
        shown = ', '.join(opts) or ('its module\'s (see the doc)' if v.get('passthrough') else '-')
        out[k] = f"{v['kind']}: {v['doc']}; options {shown}" + \
                 (f"; WebGPU-only (ignored, warned): {', '.join(sorted(v['unsupported']))}" if v['unsupported'] else '')
    return out


class _Uniforms(dict):
    """Socket lookups that accept the WebGPU camelCase spelling too. A temporal effect's uniforms also carry
    cut(*frames), as WebGPU's U.cut() (aeropittura): there a call on the cut frame, here the frames, keyed."""

    cut = None

    def __getitem__(self, k):
        return dict.__getitem__(self, _snake(k))

    def __contains__(self, k):
        return dict.__contains__(self, _snake(k))

    def get(self, k, d=None):
        return dict.get(self, _snake(k), d)


class _FXUniforms(dict):
    """{effect: its uniforms}. With ONE effect applied, that effect's own uniform names work at the top level too
    (the WebGPU registry returns the flat object then): e.uniforms['opacity'] is e.uniforms['glitch_bars']['opacity']."""

    def _single(self):
        return next(iter(self.values())) if len(self) == 1 else None

    def __getitem__(self, k):
        if dict.__contains__(self, k):
            return dict.__getitem__(self, k)
        one = self._single()
        if one is not None and k in one:
            return one[k]
        raise KeyError(f'uniforms: no effect or uniform {k!r} (effects: {[*self]}'
                       + (f'; uniforms of the one effect: {sorted(one)}' if one is not None else '') + ')')

    def __contains__(self, k):
        one = self._single()
        return dict.__contains__(self, k) or (one is not None and k in one)

    def get(self, k, d=None):
        try:
            return self[k]
        except KeyError:
            return d

    def __getattr__(self, k):
        """With one effect, its uniforms' own attributes too: e.uniforms.cut(f), as WebGPU's U.cut()."""
        one = self._single() if not k.startswith('__') else None
        if one is not None and getattr(one, k, None) is not None:
            return getattr(one, k)
        raise AttributeError(k)


class FX:
    """What apply_to returns (the WebGPU { effects, uniforms, update, setResolution }, plus Blender's key and cut)."""

    def __init__(self, scene):
        self.scene = scene
        self.uniforms = _FXUniforms()
        self.nodes = {}
        self.effects = []                  # one handle per effect, in the order applied: {name, layer, node, uniforms}
        self.histories = {}                # effect -> its look.post.history.History records (temporal effects)

    def key(self, effect, param, frame, value):
        """Set a uniform and key it at `frame` (beat bursts are F-curves on the group's input)."""
        s = self.uniforms[effect][param]
        s.default_value = _socket_value(s, value)
        s.keyframe_insert('default_value', frame=int(frame))
        return s

    def update(self, t=None):
        """Scene Time drives the time-based effects inside the graph, so nothing is pushed per frame (kept for ported
        code). It does copy the scene's view transform and look into the display-space looks again (display.sync):
        call it after changing them, as the WebGPU passes read the renderer's tone mapping each frame."""
        from . import display
        display.sync(self.scene)
        return self

    def set_resolution(self, w=None, h=None):
        """Nothing to do: the compositor works at the render's size (kept for ported code: setResolution)."""
        return self

    def cut(self, *frames):
        """A camera cut at these frames (aeropittura's U.cut(), era_looks' camJumped()): every temporal effect's
        history restarts there, so no echo or persistence reads across it. Keyed, so it lives in the .blend."""
        for name, hs in self.histories.items():
            for h in hs:
                h.add_cuts(frames)
        return self


def _socket_value(sock, v):
    if sock.type == 'RGBA' and isinstance(v, (tuple, list)) and len(v) == 3:
        return (*v, 1.0)
    return v


def _options(name, R, raw):
    """A WebGPU options dict -> this effect's options (snake_case, aliases resolved). Unknown keys raise; WebGPU keys
    with no Blender counterpart print why and are dropped. A passthrough effect's options go on as given."""
    if R.get('passthrough'):
        return dict(raw)
    known = {p[0] for p in R['params'] if p[0]} | set(R['build_opts']) | {'layer'}
    out = {}
    for k, v in dict(raw).items():
        s = _snake(k)
        s = R['aliases'].get(s, s)
        if s in R['unsupported']:
            print(f"[custom_effects] {name}: option {k!r} has no Blender counterpart, ignored: {R['unsupported'][s]}",
                  flush=True)
            continue
        if s not in known:
            raise KeyError(f"effect {name!r}: unknown option {k!r}. Its options: {sorted(known - {'layer'})}"
                           + (f"; WebGPU-only (ignored with a warning): {sorted(R['unsupported'])}"
                              if R['unsupported'] else ''))
        out[s] = v
    return out


# ------------------------------------------------------------------------------------------------- graph helpers
def _group(name, params):
    g = bpy.data.node_groups.new(name, 'CompositorNodeTree')
    g.interface.new_socket(name='Image', in_out='INPUT', socket_type='NodeSocketColor')
    for p in params:
        pname, d = p[0], p[1]
        if isinstance(d, (tuple, type([]))):
            s = g.interface.new_socket(name=pname, in_out='INPUT', socket_type='NodeSocketColor')
            s.default_value = (*d, 1.0)[:4]
        else:
            s = g.interface.new_socket(name=pname, in_out='INPUT', socket_type='NodeSocketFloat')
            s.default_value = d
            if len(p) > 3:
                s.min_value, s.max_value = p[2], p[3]
    g.interface.new_socket(name='Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    gi = g.nodes.new('NodeGroupInput')
    go = g.nodes.new('NodeGroupOutput')
    gi.location, go.location = (-1200, 0), (1200, 0)
    return g, gi, go


def _set(g, src, sock):
    if isinstance(src, bpy.types.NodeSocket):
        g.links.new(src, sock)
    elif src is not None:
        sock.default_value = src


def _math(g, op, a, b=None, va=None, vb=None, c=None):
    n = g.nodes.new('ShaderNodeMath')
    n.operation = op
    for i, (src, val) in enumerate(((a, va), (b, vb), (c, None))):
        if src is not None:
            _set(g, src, n.inputs[i])
        elif val is not None:
            n.inputs[i].default_value = val
    return n.outputs[0]


def _add(g, a, b):
    return _math(g, 'ADD', a, b)


def _mul(g, a, b):
    return _math(g, 'MULTIPLY', a, b)


def _step(g, edge, x):
    """GLSL step(edge, x): 1 where x >= edge."""
    return _math(g, 'SUBTRACT', 1.0, _math(g, 'LESS_THAN', x, edge))


def _smoothstep(g, e0, e1, x):
    """GLSL smoothstep(e0, e1, x): Map Range's Hermite smoothstep, clamped."""
    n = g.nodes.new('ShaderNodeMapRange')
    n.interpolation_type = 'SMOOTHSTEP'
    n.clamp = True
    _set(g, x, n.inputs['Value'])
    _set(g, e0, n.inputs['From Min'])
    _set(g, e1, n.inputs['From Max'])
    n.inputs['To Min'].default_value, n.inputs['To Max'].default_value = 0.0, 1.0
    return n.outputs['Result']


def _mix_f(g, a, b, t):
    """GLSL mix(a, b, t) for floats."""
    return _add(g, a, _mul(g, _math(g, 'SUBTRACT', b, a), t))


def _sep(g, img):
    s = g.nodes.new('CompositorNodeSeparateColor')
    g.links.new(img, s.inputs['Image'])
    return s.outputs


def _comb(g, r, gg, b, a=1.0):
    c = g.nodes.new('CompositorNodeCombineColor')
    for sock, v in zip(('Red', 'Green', 'Blue', 'Alpha'), (r, gg, b, a)):
        _set(g, v, c.inputs[sock])
    return c.outputs['Image']


def _mix_rgb(g, blend, fac, a, b, clamp=False):
    n = g.nodes.new('ShaderNodeMix')
    n.data_type = 'RGBA'
    n.blend_type = blend
    n.clamp_result = clamp
    ins = [s for s in n.inputs if s.type == 'RGBA']
    for sock, v in ((n.inputs[0], fac), (ins[0], a), (ins[1], b)):
        if isinstance(v, bpy.types.NodeSocket):
            g.links.new(v, sock)
        elif sock.type == 'RGBA' and isinstance(v, (int, float)):
            sock.default_value = (v, v, v, 1.0)
        else:
            sock.default_value = v if not isinstance(v, tuple) or len(v) == 4 else (*v, 1.0)
    return next(o for o in n.outputs if o.type == 'RGBA')


def _scale(g, img, k):
    """A colour times a float (alpha too: callers restore alpha at the end)."""
    return _mix_rgb(g, 'MULTIPLY', 1.0, img, k)


def _luma601(g, img):
    """dot(rgb, (0.299, 0.587, 0.114)): the WebGPU effects' luma."""
    c = _sep(g, img)
    return _add(g, _add(g, _mul(g, c['Red'], 0.299), _mul(g, c['Green'], 0.587)), _mul(g, c['Blue'], 0.114))


def _finish(g, go, orig, effect, opacity, alpha=None):
    """mix(orig, effect, opacity), keeping the input's alpha (WebGPU: vec4(col.rgb, orig.a)); alpha=1.0 for a shader
    that wrote vec4(col, 1.0): its alpha is then mix(orig.a, 1, opacity)."""
    m = _sep(g, _mix_rgb(g, 'MIX', opacity, orig, effect))
    o = _sep(g, orig)
    a = o['Alpha'] if alpha is None else _mix_f(g, o['Alpha'], alpha, opacity)
    g.links.new(_comb(g, m['Red'], m['Green'], m['Blue'], a), go.inputs['Image'])


class _Coords:
    """The effect input's Image Coordinates: u, v normalised pixel centres (origin bottom left) and one pixel in
    those units (px, py)."""

    def __init__(self, g, img):
        ic = g.nodes.new('CompositorNodeImageCoordinates')
        g.links.new(img, ic.inputs['Image'])
        n = g.nodes.new('ShaderNodeSeparateXYZ')
        g.links.new(ic.outputs['Normalized'], n.inputs[0])
        p = g.nodes.new('ShaderNodeSeparateXYZ')
        g.links.new(ic.outputs['Pixel'], p.inputs[0])
        self.u, self.v = n.outputs['X'], n.outputs['Y']
        self.x, self.y = p.outputs['X'], p.outputs['Y']
        self.px = _math(g, 'DIVIDE', self.u, _math(g, 'ADD', self.x, None, vb=0.5))
        self.py = _math(g, 'DIVIDE', self.v, _math(g, 'ADD', self.y, None, vb=0.5))


def _tap(g, img, u, v):
    """The image at (u, v) normalised, edges clamped: Map UV with Extend (Z = 1: Map UV reads Z as coverage)."""
    c = g.nodes.new('ShaderNodeCombineXYZ')
    _set(g, u, c.inputs['X'])
    _set(g, v, c.inputs['Y'])
    c.inputs['Z'].default_value = 1.0
    mu = g.nodes.new('CompositorNodeMapUV')
    mu.inputs['Extension X'].default_value = 'Extend'
    mu.inputs['Extension Y'].default_value = 'Extend'
    g.links.new(img, mu.inputs['Image'])
    g.links.new(c.outputs[0], mu.inputs['UV'])
    return mu.outputs['Image']


def _time(g):
    return g.nodes.new('CompositorNodeSceneTime').outputs['Seconds']


# ------------------------------------------------------------------------------------------------- the groups
@_effect('glitch_bars', params=[('bar_freq', 20.0, 0, 1000), ('scroll_speed', 3.0, -100, 100),
                                ('shift', 0.025, -1, 1), ('opacity', 1.0, 0, 1)],
         doc='horizontal bars scrolling; inside each, red and blue split sideways by a sin-driven shift')
def _glitch_bars(scene, o):
    g, gi, go = _group('fx_glitch_bars', REGISTRY['glitch_bars']['params'])
    img = gi.outputs['Image']
    c = _Coords(g, img)
    t = _time(g)
    vd = _math(g, 'SUBTRACT', 1.0, c.v)                  # WebGPU's uv.y runs down the frame: the bars scroll down
    bar = _step(g, 0.7, _math(g, 'FRACT', _add(g, _mul(g, vd, gi.outputs['bar_freq']),
                                                _mul(g, t, gi.outputs['scroll_speed']))))
    direction = _math(g, 'SINE', _add(g, _mul(g, t, 12.0), _mul(g, vd, 50.0)))
    sh = _mul(g, _mul(g, bar, gi.outputs['shift']), direction)
    r = _sep(g, _tap(g, img, _add(g, c.u, sh), c.v))['Red']
    b = _sep(g, _tap(g, img, _math(g, 'SUBTRACT', c.u, sh), c.v))['Blue']
    base = _sep(g, img)
    _finish(g, go, img, _comb(g, r, base['Green'], b, 1.0), gi.outputs['opacity'], alpha=1.0)   # vec4(col, 1.0)
    return g


@_effect('rgb_shift', params=[('amount', 0.005, -1, 1), ('angle', 0.0, -TAU, TAU), ('opacity', 1.0, 0, 1)],
         doc="three's rgbShift: red sampled at uv + amount (cos angle, sin angle), blue at uv - that (UV units)")
def _rgb_shift(scene, o):
    g, gi, go = _group('fx_rgb_shift', REGISTRY['rgb_shift']['params'])
    img = gi.outputs['Image']
    c = _Coords(g, img)
    ox = _mul(g, gi.outputs['amount'], _math(g, 'COSINE', gi.outputs['angle']))
    oy = _mul(g, gi.outputs['amount'], _math(g, 'SINE', gi.outputs['angle']))
    # the offset is in WebGPU's uv, y running down: + sin(angle) moves red DOWN the frame (c.v here runs up)
    r = _sep(g, _tap(g, img, _add(g, c.u, ox), _math(g, 'SUBTRACT', c.v, oy)))['Red']
    b = _sep(g, _tap(g, img, _math(g, 'SUBTRACT', c.u, ox), _add(g, c.v, oy)))['Blue']
    base = _sep(g, img)
    _finish(g, go, img, _comb(g, r, base['Green'], b, base['Alpha']), gi.outputs['opacity'])
    return g


@_effect('radial_blur', params=[('center_x', 0.5, -1, 2), ('center_y', 0.5, -1, 2), ('weight', 0.9, 0, 1),
                                ('decay', 0.95, 0, 1), ('exposure', 1.5, 0, 50), ('opacity', 1.0, 0, 1)],
         build_opts={'count': 32}, doc="three's radialBlur: taps toward the centre weighted weight x decay^k, "
                                      "x exposure / count, added over the frame (0.5 blur + base)")
def _radial_blur(scene, o):
    count = max(8, int(o.get('count', 32)))
    g, gi, go = _group('fx_radial_blur', REGISTRY['radial_blur']['params'])
    img = gi.outputs['Image']
    c = _Coords(g, img)
    du = _math(g, 'DIVIDE', _math(g, 'SUBTRACT', gi.outputs['center_x'], c.u), None, vb=float(count))
    # center is in WebGPU's uv, y running down the frame (center_y 0.2 is near the top); c.v here runs up
    cy_up = _math(g, 'SUBTRACT', 1.0, gi.outputs['center_y'])
    dv = _math(g, 'DIVIDE', _math(g, 'SUBTRACT', cy_up, c.v), None, vb=float(count))
    # interleavedGradientNoise(screenCoordinate): a per-pixel start offset in 0..1 against banding; screenCoordinate
    # is the pixel centre counted from the TOP left (H - y - 0.5 here, H = (y + 0.5) / v)
    height = _math(g, 'DIVIDE', _add(g, c.y, 0.5), c.v)
    y_down = _math(g, 'SUBTRACT', height, _add(g, c.y, 0.5))
    noise = _math(g, 'FRACT', _mul(g, 52.9829189, _math(g, 'FRACT', _add(
        g, _mul(g, _add(g, c.x, 0.5), 0.06711056), _mul(g, y_down, 0.00583715)))))
    blur = None
    for k in range(1, count + 1):
        s = _add(g, noise, float(k))
        tap = _tap(g, img, _math(g, 'MULTIPLY_ADD', du, s, c=c.u), _math(g, 'MULTIPLY_ADD', dv, s, c=c.v))
        w = _mul(g, gi.outputs['weight'], _math(g, 'POWER', gi.outputs['decay'], None, vb=float(k - 1)))
        term = _scale(g, tap, w)
        blur = term if blur is None else _mix_rgb(g, 'ADD', 1.0, blur, term)
    blur = _scale(g, blur, _math(g, 'DIVIDE', gi.outputs['exposure'], None, vb=float(count)))
    colour = _mix_rgb(g, 'ADD', 1.0, img, _scale(g, blur, 0.5))          # mix(blur, base * 2, 0.5)
    _finish(g, go, img, colour, gi.outputs['opacity'])
    return g


@_effect('box_blur', params=[('opacity', 1.0, 0, 1)], build_opts={'size': 1, 'separation': 1},
         doc="three's boxBlur: a (2 size + 1)^2 grid of taps `separation` pixels apart, averaged (size 1..3)")
def _box_blur(scene, o):
    size = max(1, min(3, int(o.get('size', 1))))
    sep = max(1, int(o.get('separation', 1)))
    g, gi, go = _group('fx_box_blur', REGISTRY['box_blur']['params'])
    img = gi.outputs['Image']
    n = 2 * size + 1

    def one_axis(src, axis):
        c = _Coords(g, src)
        acc = None
        for i in range(-size, size + 1):
            if axis == 'x':
                tap = _tap(g, src, _math(g, 'MULTIPLY_ADD', c.px, float(i * sep), c=c.u), c.v)
            else:
                tap = _tap(g, src, c.u, _math(g, 'MULTIPLY_ADD', c.py, float(i * sep), c=c.v))
            acc = tap if acc is None else _mix_rgb(g, 'ADD', 1.0, acc, tap)
        return _scale(g, acc, 1.0 / n)
    # the grid's uniform weights separate: rows averaged, then columns (2n taps for n^2)
    _finish(g, go, img, one_axis(one_axis(img, 'x'), 'y'), gi.outputs['opacity'])
    return g


@_effect('sepia', params=[('amount', 1.0, 0, 1), ('opacity', 1.0, 0, 1)],
         doc="three's sepia matrix (glfx.js), blended by amount")
def _sepia(scene, o):
    g, gi, go = _group('fx_sepia', REGISTRY['sepia']['params'])
    img = gi.outputs['Image']
    c = _sep(g, img)

    def dot(w):
        return _add(g, _add(g, _mul(g, c['Red'], w[0]), _mul(g, c['Green'], w[1])), _mul(g, c['Blue'], w[2]))
    sep_col = _comb(g, dot((0.393, 0.769, 0.189)), dot((0.349, 0.686, 0.168)), dot((0.272, 0.534, 0.131)), c['Alpha'])
    blended = _mix_rgb(g, 'MIX', gi.outputs['amount'], img, sep_col)
    _finish(g, go, img, blended, gi.outputs['opacity'])
    return g


@_effect('neon_edges', params=[('glow_color', (1.0, 0.2, 0.8)), ('threshold', 0.05, 0, 10), ('strength', 1.0, 0, 20),
                               ('opacity', 1.0, 0, 1)],
         unsupported={'width': 'the compositor knows the frame size', 'height': 'the compositor knows the frame size'},
         doc='4-tap Laplacian of BT.601 luma; core + half the halo glow in glow_color, added over the frame')
def _neon_edges(scene, o):
    g, gi, go = _group('fx_neon_edges', REGISTRY['neon_edges']['params'])
    img = gi.outputs['Image']
    c = _Coords(g, img)
    l_c = _luma601(g, img)
    l_l = _luma601(g, _tap(g, img, _math(g, 'SUBTRACT', c.u, c.px), c.v))
    l_r = _luma601(g, _tap(g, img, _add(g, c.u, c.px), c.v))
    l_u = _luma601(g, _tap(g, img, c.u, _math(g, 'SUBTRACT', c.v, c.py)))
    l_d = _luma601(g, _tap(g, img, c.u, _add(g, c.v, c.py)))
    e = _math(g, 'ABSOLUTE', _math(g, 'SUBTRACT', _mul(g, l_c, 4.0), _add(g, _add(g, l_l, l_r), _add(g, l_u, l_d))))
    th = gi.outputs['threshold']
    core = _smoothstep(g, th, _mul(g, th, 2.0), e)
    halo = _smoothstep(g, _mul(g, th, 0.3), _mul(g, th, 1.5), e)
    k = _mul(g, _math(g, 'MULTIPLY_ADD', halo, 0.5, c=core), gi.outputs['strength'])
    glow = _scale(g, gi.outputs['glow_color'], k)
    _finish(g, go, img, _mix_rgb(g, 'ADD', 1.0, img, glow), gi.outputs['opacity'], alpha=1.0)   # vec4(col, 1.0)
    return g


# ------------------------------------------------------------------------------------------------- glare
def _glare(scene, name, slot, **vals):
    t = chain.tree(scene)
    n = next((x for _s, nm, x in chain.stages(scene) if nm == name), None)
    if n is None:
        n = t.nodes.new('CompositorNodeGlare')
        chain.add_stage(scene, slot, name, n)
    for k, v in vals.items():
        n.inputs[k].default_value = v
    return n


def _rgba(v):
    v = tuple(v)
    return v if len(v) == 4 else (*v, 1.0)


@_effect('bloom', slot='bloom', kind='glare', params=[('strength', 0.25), ('radius', 0.4), ('threshold', 0.85)],
         aliases={'size': 'radius'}, doc="Glare 'Bloom' (UnrealBloom's strength, radius -> Glare Size, threshold)")
def _bloom(scene, o):
    n = chain.set_bloom(scene, strength=float(o.get('strength', 0.25)), size=float(o.get('radius', 0.4)),
                        threshold=float(o.get('threshold', 0.85)))
    return n, {'strength': n.inputs['Strength'], 'radius': n.inputs['Size'], 'threshold': n.inputs['Threshold']}


def _screen_params(name):
    def fill():
        from . import screen_effects as SE
        return [tuple(p) for p in getattr(SE, name)]
    return fill


def _screen_group(fn_name):
    def build(scene, o):
        from . import screen_effects as SE
        return getattr(SE, fn_name)(scene, o)
    return build


@_effect('sun_beams', kind='glare', params=[('source', (0.5, 0.7)), ('threshold', 1.0), ('strength', 0.3)],
         doc="Glare 'Sun Beams' from a screen position (source=(x, y) 0..1): the godrays fallback")
def _sun_beams(scene, o):
    n = _glare(scene, 'sun_beams', 'under', Type='Sun Beams', Threshold=float(o.get('threshold', 1.0)),
               Strength=float(o.get('strength', 0.3)))
    src = tuple(o.get('source', (0.5, 0.7)))
    n.inputs['Sun Position'].default_value = (*src, 0.0)[:len(n.inputs['Sun Position'].default_value)]
    return n, {'threshold': n.inputs['Threshold'], 'strength': n.inputs['Strength'], 'source': n.inputs['Sun Position']}


# ------------------------------------------------------------------------------------------------- native
# Native effects change the scene, not the compositor: the scene remembers which are applied (NATIVE_KEY) and what
# they changed the first time (eido_prev_<effect>), so remove() / clear() take them back out, as the WebGPU applyTo
# dropped an effect's hooks when the next call replaced it.
NATIVE_KEY = 'eido_native_effects'


def _natives(scene):
    return [str(n) for n in scene.get(NATIVE_KEY, [])]


def _record_native(scene, name):
    lst = _natives(scene)
    if name not in lst:
        lst.append(name)
    scene[NATIVE_KEY] = lst


def _remember(scene, effect, state):
    """Keep what an effect is about to change, the first time only (a second apply_to keeps the original)."""
    key = f'eido_prev_{effect}'
    if key not in scene:
        scene[key] = json.dumps(state)


def _recall(scene, effect):
    key = f'eido_prev_{effect}'
    if key not in scene:
        return None
    state = json.loads(scene[key])
    del scene[key]
    return state


def _focus_blur_undo(scene):
    """The cameras' depth of field back as it was, and the focus empties focus_blur made gone."""
    prev = _recall(scene, 'focus_blur') or {}
    for name, (use, fstop, dist, fobj, made) in prev.items():
        cam = bpy.data.objects.get(name)
        if cam is not None and cam.type == 'CAMERA':
            d = cam.data.dof
            d.use_dof, d.aperture_fstop, d.focus_distance = bool(use), float(fstop), float(dist)
            d.focus_object = bpy.data.objects.get(fobj) if fobj else None
        e = bpy.data.objects.get(made) if made else None
        if e is not None:
            bpy.data.objects.remove(e, do_unlink=True)


def fstop_for_blur(scene, cam, focus_distance, focal_length=2.0, bokeh_scale=1.0):
    """The f-stop at which this camera blurs a point `focal_length` metres beyond the focus plane as three's
    DepthOfFieldNode does at full CoC: its 64-tap disc of radius bokeh_scale px, dilated by its 16-tap max pass of the
    same radius, about 1.5 x bokeh_scale px of radius at the render's resolution. Thin lens: the blur circle's
    radius on the sensor is f^2 |z - s| / (2 N z (s - f)), in pixels over the sensor span the frame fits."""
    d = cam.data
    r = scene.render
    w, h = r.resolution_x * r.resolution_percentage / 100.0, r.resolution_y * r.resolution_percentage / 100.0
    if d.sensor_fit == 'VERTICAL' or (d.sensor_fit == 'AUTO' and h > w):
        span_mm, span_px = (d.sensor_height if d.sensor_fit == 'VERTICAL' else d.sensor_width), h
    else:
        span_mm, span_px = d.sensor_width, w
    f = d.lens
    s = max(float(focus_distance) * 1000.0, f * 1.01)
    z = s + max(float(focal_length), 1e-4) * 1000.0
    radius_px = max(1.5 * float(bokeh_scale), 1e-3)
    n = (f * f * (z - s)) / (2.0 * z * (s - f)) / span_mm * span_px / radius_px
    return max(0.01, min(128.0, n))         # (three's blur is not a lens's: a wide lens may need an f-stop below 1)


@_effect('focus_blur', kind='native', params=[('fstop', 2.8), ('focus_distance', 5.0), ('focus_objects', None),
                                             ('focal_length', 2.0), ('bokeh_scale', 1.0), ('opacity', 1.0)],
         build_opts={'mode': 'lens'},
         doc="mode 'lens' (the default): the camera's depth of field, focus_distance or focus_objects (their focus "
             "points, averaged, followed every frame), the blur as WebGPU's focal_length / bokeh_scale (the f-stop "
             "that blurs a point focal_length beyond focus by bokeh_scale's radius: fstop_for_blur) or Blender's fstop "
             "directly; mode 'screen': focus_blur.js as WebGPU ran it, three's DepthOfFieldNode on the Depth pass "
             "(screen_effects.focus_blur_screen: near / far CoC fields, 64-tap disc, 16-tap max, opacity; "
             "focus_objects keyed per frame)",
         undo=_focus_blur_undo)
def _focus_blur(scene, o):
    mode = o.get('mode', 'lens')
    if mode not in ('lens', 'screen'):
        raise ValueError(f"focus_blur: mode {mode!r}: 'lens' (the camera's depth of field) or 'screen' (the WebGPU "
                         f"pass)")
    if mode == 'screen':
        from . import screen_effects as SE
        if 'fstop' in o:
            print("[custom_effects] focus_blur: option 'fstop' is the lens's; mode 'screen' ignores it "
                  "(focal_length / bokeh_scale set its blur)", flush=True)
        return SE.focus_blur_screen(scene, o, layer=layer_of('focus_blur', o))
    if 'opacity' in o:
        print("[custom_effects] focus_blur: option 'opacity' ignored in mode 'lens': depth of field is in the "
              "render, not mixed over it (mode 'screen' takes it)", flush=True)
    from .. import camera as C
    cams = {m.camera for m in scene.timeline_markers if m.camera} | ({scene.camera} if scene.camera else set())
    objs = o.get('focus_objects')
    if objs is not None and not isinstance(objs, (tuple, type([]))):
        objs = [objs]
    state = {}
    for cam in cams:
        d = cam.data.dof
        empty = f'focus_{cam.name}'
        state[cam.name] = [bool(d.use_dof), float(d.aperture_fstop), float(d.focus_distance),
                           d.focus_object.name if d.focus_object else '',
                           empty if (objs and bpy.data.objects.get(empty) is None) else '']
    _remember(scene, 'focus_blur', state)
    for cam in cams:
        if 'fstop' in o or not ('focal_length' in o or 'bokeh_scale' in o):
            fstop = float(o.get('fstop', 2.8))
        else:                                              # WebGPU's knobs: the f-stop giving that blur
            if objs:                                       # the focus depth on the first frame, read evaluated
                from mathutils import Vector
                from .history import evaluated
                scene.frame_set(scene.frame_start)
                cm = evaluated(scene, cam).matrix_world
                fwd = cm.to_3x3() @ Vector((0.0, 0.0, -1.0))
                dg = (bpy.context.view_layer if scene == bpy.context.scene else scene.view_layers[0]).depsgraph
                ds = [(C.focus_point(x, depsgraph=dg) - cm.translation).dot(fwd) for x in objs]
                ds = [x for x in ds if x > 0]
                fd = sum(ds) / len(ds) if ds else float(o.get('focus_distance', 5.0))
            else:
                fd = float(o.get('focus_distance', cam.data.dof.focus_distance or 5.0))
            fstop = fstop_for_blur(scene, cam, fd, float(o.get('focal_length', 2.0)),
                                   float(o.get('bokeh_scale', 1.0)))
        C.set_dof(cam, fstop=fstop)
        if objs:
            def mean(os_=tuple(objs)):
                from mathutils import Vector
                return sum((C.focus_point(x) for x in os_), Vector()) / len(os_)
            C.focus_on(scene, cam, (scene.frame_start, scene.frame_end), mean)
        elif 'focus_distance' in o:
            cam.data.dof.focus_object = None
            cam.data.dof.focus_distance = float(o['focus_distance'])
    return None, {}


_FOG_PARAMS = [('density', 0.004), ('color', (0.85, 0.88, 0.92)), ('anisotropy', 0.35), ('noise_amount', 0.0),
               ('noise_scale', 6.0), ('size', (600.0, 600.0, 30.0)), ('centre', (0.0, 0.0, 0.0)), ('near', 0.1),
               ('far', 300.0)]
_FOG_VOLUME_ONLY = ('anisotropy', 'size', 'centre', 'near', 'far')
_FOG_SCREEN_ONLY = {'edge_radius': 'a volume has no silhouette halo to push away from',
                    'edge_strength': 'a volume has no silhouette halo to push away from',
                    'opacity': "the fog's density sets how much it hides"}
_FOG_UNSUPPORTED = {}


def _fog_undo(scene):
    """The fog volume gone (unless the other fog effect still uses it) and the scene's volume settings back."""
    if any(n in _natives(scene) for n in ('depth_fog', 'godrays')):
        return
    ob = bpy.data.objects.get('look_depth_fog')
    if ob is not None:
        me = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if me is not None and me.users == 0:
            mats = [m for m in me.materials if m is not None]
            bpy.data.meshes.remove(me)
            for m in mats:
                if m.users == 0:
                    bpy.data.materials.remove(m)
    prev = _recall(scene, 'depth_fog')
    if prev:
        ee = scene.eevee
        ee.use_volumetric_shadows, ee.use_volume_custom_range = bool(prev[0]), bool(prev[1])
        ee.volumetric_start, ee.volumetric_end = float(prev[2]), float(prev[3])


@_effect('depth_fog', kind='native', params=_FOG_PARAMS + [('edge_strength', 2.0), ('opacity', 1.0)],
         build_opts={'mode': 'volume', 'edge_radius': 2}, aliases={'colour': 'color', 'center': 'centre'},
         unsupported=_FOG_UNSUPPORTED,
         doc="mode 'volume' (the default): a fog layer, a volume box (density per metre as WebGPU's exp falloff, "
             "color, noise_amount / noise_scale), lit and shadowed by the scene, godrays come with it in sun; mode "
             "'screen': depth_fog.js as WebGPU ran it, a screen pass on the Depth pass (fog colour, value noise in "
             "screen space, three's depthAwareBlend with edge_radius / edge_strength, opacity; WebGPU's defaults: "
             "density 0.04, color (0.55, 0.62, 0.72), noise_amount 0.4, noise_scale 6)", undo=_fog_undo)
def _depth_fog(scene, o):
    """Real fog as a finite layer (a world volume is infinite: it extinguishes the sun and the sky entirely, a black
    frame at 0.012 / m). The volume range is set to `far` metres so its froxels cover the fog, not the
    camera's whole clip range. noise_amount > 0 modulates the density with a noise field of noise_scale cells per
    10 m (WebGPU's 2D noise, here in 3D). mode='screen' is the WebGPU pass itself (screen_effects.depth_fog_screen):
    a stage in the chain, not a volume."""
    mode = o.get('mode', 'volume')
    if mode not in ('volume', 'screen'):
        raise ValueError(f"depth_fog: mode {mode!r}: 'volume' (a fog volume, lit) or 'screen' (the WebGPU pass)")
    if mode == 'screen':
        from . import screen_effects as SE
        for k in _FOG_VOLUME_ONLY:
            if k in o:
                print(f"[custom_effects] depth_fog: option {k!r} is the fog volume's; mode 'screen' ignores it",
                      flush=True)
        return SE.depth_fog_screen(scene, {k: v for k, v in o.items() if k not in _FOG_VOLUME_ONLY},
                                   layer=layer_of('depth_fog', o))
    for k, why in _FOG_SCREEN_ONLY.items():
        if k in o:
            print(f"[custom_effects] depth_fog: option {k!r} ignored in mode 'volume': {why} (mode 'screen' takes "
                  f"it)", flush=True)
    return _fog_volume(scene, o)


def _fog_volume(scene, o):
    import bmesh
    from mathutils import Vector
    sx, sy, h = o.get('size', (600.0, 600.0, 30.0))
    c = Vector(o.get('centre', (0.0, 0.0, 0.0)))
    ee = scene.eevee
    _remember(scene, 'depth_fog', [bool(ee.use_volumetric_shadows), bool(ee.use_volume_custom_range),
                                   float(ee.volumetric_start), float(ee.volumetric_end)])
    ob = bpy.data.objects.get('look_depth_fog')
    if ob is not None and ob.name not in scene.collection.all_objects:
        scene.collection.objects.link(ob)                 # made for another scene: this one gets it too
    if ob is None:
        me = bpy.data.meshes.new('look_depth_fog')
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new('look_depth_fog', me)
        scene.collection.objects.link(ob)
        m = bpy.data.materials.new('look_depth_fog')
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        vol = nt.nodes.new('ShaderNodeVolumePrincipled')
        vol.name = 'look_fog'
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        nt.links.new(vol.outputs['Volume'], out.inputs['Volume'])
        me.materials.append(m)
    ob.location = (c.x, c.y, c.z + h / 2 - 0.5)
    ob.scale = (sx, sy, h + 1.0)
    nt = ob.data.materials[0].node_tree
    vol = nt.nodes['look_fog']
    dens = float(o.get('density', 0.004))
    amt = float(o.get('noise_amount', 0.0))
    for n in [n for n in nt.nodes if n.name.startswith('look_fog_noise')]:
        nt.nodes.remove(n)
    if amt > 0:
        tc = nt.nodes.new('ShaderNodeTexCoord')
        tc.name = 'look_fog_noise_coord'
        nz = nt.nodes.new('ShaderNodeTexNoise')
        nz.name = 'look_fog_noise'
        nz.inputs['Scale'].default_value = float(o.get('noise_scale', 6.0)) / 10.0
        nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
        mr = nt.nodes.new('ShaderNodeMapRange')
        mr.name = 'look_fog_noise_density'
        nt.links.new(nz.outputs['Factor'], mr.inputs['Value'])
        mr.inputs['To Min'].default_value = dens * (1.0 - amt)
        mr.inputs['To Max'].default_value = dens * (1.0 + amt)
        nt.links.new(mr.outputs['Result'], vol.inputs['Density'])
    else:
        for lk in tuple(vol.inputs['Density'].links):
            nt.links.remove(lk)
        vol.inputs['Density'].default_value = dens
    vol.inputs['Color'].default_value = _rgba(o.get('color', (0.85, 0.88, 0.92)))
    vol.inputs['Anisotropy'].default_value = float(o.get('anisotropy', 0.35))
    ee.use_volumetric_shadows = True
    ee.use_volume_custom_range = True
    ee.volumetric_start = float(o.get('near', 0.1))
    ee.volumetric_end = float(o.get('far', 300.0))
    ob['look_effect'] = 'depth_fog'
    return vol, {'density': vol.inputs['Density'], 'color': vol.inputs['Color'], 'anisotropy': vol.inputs['Anisotropy']}


def _godrays_light(scene, light):
    """opts.light (an object or its name), else the scene's first sun or point light (WebGPU: the first
    DirectionalLight or PointLight)."""
    if isinstance(light, str):
        light = bpy.data.objects.get(light)
    if light is not None:
        if getattr(light, 'type', None) != 'LIGHT':
            raise ValueError(f'godrays: light {light!r} is not a light object')
        return light
    return next((ob for ob in scene.objects if ob.type == 'LIGHT' and ob.data.type in ('SUN', 'POINT')), None)


def _godrays_undo(scene):
    """The light's volume factor back as it was, then the fog (unless depth_fog still uses it)."""
    prev = _recall(scene, 'godrays_light') or {}
    for name, factor in prev.items():
        ob = bpy.data.objects.get(name)
        if ob is not None and ob.type == 'LIGHT':
            ob.data.volume_factor = float(factor)
    _fog_undo(scene)


@_effect('godrays', kind='native', params=_FOG_PARAMS + [('strength', 0.5), ('opacity', 1.0), ('light', None)],
         aliases={'colour': 'color', 'center': 'centre'},
         unsupported={'edge_radius': _FOG_SCREEN_ONLY['edge_radius'],
                      'edge_strength': _FOG_SCREEN_ONLY['edge_strength'],
                      'cloud_opacity_tex': "the sky family's cloud shadows occlude the sun itself"},
         doc="three's godrays as EEVEE makes them: a fog volume (depth_fog's, mode 'volume') with volumetric shadows, "
             "so the light's beams pass only through gaps in the geometry; light: the light whose beams these are "
             "(default the first sun or point light, as WebGPU's); strength (0.5 = its physical scattering) and "
             "opacity scale that light's volume factor (strength / 0.5 x opacity, set only when light, strength or "
             "opacity is given: key light.data.volume_factor to animate it); sun_beams is a post fallback",
         undo=_godrays_undo)
def _godrays(scene, o):
    lt = _godrays_light(scene, o.get('light'))
    k = float(o.get('strength', 0.5)) / 0.5 * float(o.get('opacity', 1.0))
    asked = any(x in o for x in ('light', 'strength', 'opacity'))  # else a light's own volume factor is left alone
    if lt is not None and asked:
        _remember(scene, 'godrays_light', {lt.name: float(lt.data.volume_factor)})
        lt.data.volume_factor = k
    elif asked:
        print('[custom_effects] godrays: no sun or point light in the scene: strength has no light to scale',
              flush=True)
    return _fog_volume(scene, {kk: v for kk, v in o.items() if kk not in ('strength', 'opacity', 'light')})


# ------------------------------------------------------------------------------------------------- the passes
# Whole-frame passes with a module of their own (era looks, aeropittura) and the temporal after_image: their build
# puts the node in the chain itself (with any history riders) and returns (node, {uniform: socket}, [History]).
def _pass_build(module, fn_name):
    def build(scene, o, stage, layer):
        import importlib
        mod = importlib.import_module(f'{__package__}.{module}')
        return getattr(mod, fn_name)(scene, o, stage, layer)
    return build


def _era_params():
    from .era_looks import KEYS
    return [(k, 0.0, 0.0, 10.0) for k in KEYS] + [('px', 1.0, 1.0, 64.0)]


def _aero_params():
    from .aeropittura import KEYS, PKEYS
    return ([(k, 0.0, 0.0, 1.0) for k in KEYS] + [('force', 1.0, 0.0, 4.0)] + [(k, 0.0, 0.0, 1.0) for k in PKEYS]
            + [('focal', (0.5, 0.42)), ('spare', (0.5, 0.4, 0.0)), ('spin', 0.0), ('swirl', 0.0), ('swirl_r', 0.6),
               ('brush_angle', 1.05), ('chev_dir', (1.0, 0.0))])


class _LazyParams(builtins.list):            # (this module's own list() is the registry listing)
    """A params list filled from its module the first time it is read (the modules import bpy-heavy code)."""

    def __init__(self, fill):
        super().__init__()
        self._fill = fill

    def _ensure(self):
        if self._fill is not None:
            f, self._fill = self._fill, None
            self.extend(f())

    def __iter__(self):
        self._ensure()
        return super().__iter__()

    def __len__(self):
        self._ensure()
        return super().__len__()


_effect('era_looks', kind='pass', params=_LazyParams(_era_params), build_opts={'persist_frames': None, 'cuts': None},
        unsupported={'time': 'Scene Time drives the pass', 'frame': 'Scene Time drives the pass',
                     'weave': 'the gate weave is computed from Scene Time inside the pass',
                     'cam_near': 'the Depth pass is metric: no near / far to unpack',
                     'cam_far': "the far plane follows the scene camera's clip end (a driver on the "
                                "uniform cam_far)"},
        doc='graphic-arts looks from the history of computing as weights on one pass (era_looks.py: ERA_LOOKS, '
            'apply_look, crossfade); the phosphor persistence reads the last frames back from disk')(
    _pass_build('era_looks', 'make'))
_effect('aeropittura', kind='pass', params=_LazyParams(_aero_params), build_opts={'cuts': None, 'kuwahara': 'own'},
        aliases={'swirlr': 'swirl_r', 'brushangle': 'brush_angle', 'chevdir': 'chev_dir'},
        unsupported={'time': 'Scene Time drives the pass', 'frame': 'Scene Time drives the pass'},
        doc='the futurist post pass of UNKNOWN FORCE (aeropittura.py: LOOKS, PLANES, RAMP, apply_look, set_planes); '
            'the time echoes read earlier frames back from disk; its own anisotropic Kuwahara underpainting '
            "(kuwahara='blender': Blender's node instead, faster, further from the WebGPU picture)")(
    _pass_build('aeropittura', 'make'))
_effect('after_image', kind='pass', params=[('damp', 0.96, 0.0, 1.0), ('opacity', 1.0, 0.0, 1.0)],
        build_opts={'cuts': None},
        doc="three's afterImage: max(new, old x damp) per channel, old masked below 0.1; old is this pass's own "
            'output a frame earlier, read back from disk (render the shot in order)')(
    _pass_build('after_image', 'make'))

# The smaller screen-space effects, ported in look/post/screen_effects.py (groups built from their shaders).
def _screen(fn_name):
    def build(scene, o):
        from . import screen_effects as SE
        return getattr(SE, fn_name)(scene, o)
    return build


_FRAME_SIZE = {'width': 'the compositor works at the frame size', 'height': 'the compositor works at the frame size'}
_effect('wavy', params=[('amplitude', 10.0, -1000, 1000), ('frequency', 0.1, -100, 100), ('phase', 0.0),
                        ('animate', 0.0, 0, 1), ('anim_speed', 1.0, -100, 100), ('opacity', 1.0, 0, 1)],
        unsupported=_FRAME_SIZE,
        doc='rows shifted sideways by amplitude px x sin(frequency x y_px + phase [+ animate x t x anim_speed])')(
    _screen('wavy'))
_effect('kaleidoscope', params=[('segments', 6.0, 1, 64), ('rotate', 0.0), ('opacity', 1.0, 0, 1)],
        doc='the frame folded into `segments` mirrored wedges about its centre, turned by `rotate` (rad)')(
    _screen('kaleidoscope'))
_effect('jitter', params=[('speed', 10.0, 0, 1000), ('amplitude', 0.2, 0, 10), ('opacity', 1.0, 0, 1)],
        doc='red, green and blue each displaced by a sin-hash burst (amplitude in uv), `speed` bursts a second')(
    _screen('jitter'))
_effect('melt', params=[('speed', 0.7, -100, 100), ('swirl', 0.2, 0, 100), ('opacity', 1.0, 0, 1)],
        doc='each pixel pulled along its own hue angle by its saturation, breathing with time')(_screen('melt'))
_effect('dithering', params=[('levels', 8.0, 2, 256), ('opacity', 1.0, 0, 1)],
        doc="perceptual (sqrt) quantisation to `levels` with three's bayerDither 4x4 offset, squared back")(
    _screen('dithering'))
_effect('chromatic_aberration_alpha', params=[('amount', 0.005, -1, 1), ('angle', 0.0), ('opacity', 1.0, 0, 1)],
        doc="red at uv + amount (cos, sin angle), blue at uv - that, each weighted by its own sample's alpha (a "
            "transparent edge does not fringe)")(_screen('chromatic_aberration_alpha'))
_effect('bw_halftone', params=[('threshold', 0.4, 0, 1), ('dot_size', 1.8, 0.01, 100), ('angle', 45.0),
                               ('ink_color', (0.0, 0.0, 0.0)), ('paper_color', (1.0, 1.0, 1.0)),
                               ('opacity', 1.0, 0, 1)],
        unsupported=_FRAME_SIZE,
        doc='a rotated cosine dot screen (dot_size, angle in degrees) against luminance, ink_color on paper_color')(
    _screen('bw_halftone'))
_effect('bleach_bypass', params=[('amount', 1.0, 0, 1), ('opacity', 1.0, 0, 1)],
        doc="three's bleach(): screen above luminance 0.45, multiply below, by amount; mixed by opacity")(
    _screen('bleach_bypass'))
_effect('hash_blur', params=[('amount', 0.05, 0, 1), ('opacity', 1.0, 0, 1)], build_opts={'repeats': 45},
        doc="three's hashBlur(): `repeats` taps (built in, at least 8) on a hashed spiral, radius ~amount (uv)")(
    _screen('hash_blur'))
_effect('crt', params=[('opacity', 1.0, 0, 1)], unsupported=_FRAME_SIZE,
        doc='a curved tube: barrel warp, wobble, converged guns and ghosts, vignette, rolling scanlines, flicker, '
            'a 2 px aperture grille (the era looks\' phosphor is the fuller CRT)')(_screen('crt'))
_effect('old_bw_film', params=[('opacity', 1.0, 0, 1)], unsupported=_FRAME_SIZE,
        doc='the silent-film pass: 12 fps cadence, gate weave, simplex dust specks in drifting regions on some frames, '
            'a jump cut at 7.7-8.2 s of a 24 s loop, exposure flicker, vignette, BT.601 luma')(_screen('old_bw_film'))
def _toon_params():
    from .screen_effects import FULL_TOON
    return [tuple(p) for p in FULL_TOON]


_effect('full_toon', kind='pass', params=_LazyParams(_toon_params),
        unsupported={**_FRAME_SIZE, 'cam_near': 'the Depth pass is metric: the near plane cancels in the depth',
                     'cam_far': "the far plane follows the scene camera's clip end (a driver)"},
        doc='a screen cel pass: depth-aware blur, luminance bands by depth, a three-stop palette tint (hue_shift), '
            'depth + normal outlines; reads the Depth and Normal passes')(_pass_build('screen_effects', 'full_toon'))
def _blueprint_params():
    from .screen_effects import BLUEPRINT
    return [tuple(p) for p in BLUEPRINT]


def _hatch_params():
    from .screen_effects import CROSS_HATCH
    return [tuple(p) for p in CROSS_HATCH]


def _retro_wireframe(scene, o):
    from . import screen_effects as SE
    return SE.retro_wireframe(scene, o)


def _retro_wireframe_undo(scene):
    from . import screen_effects as SE
    SE.retro_wireframe_cleanup(scene)


def _underwater_undo(scene):
    """The rising bubbles round the camera gone with the pass (the WebGPU effect left its bubble mesh in the scene; its
    next applyTo rebuilt the scene's hooks, and a Blender scene keeps objects until they are removed)."""
    ob = bpy.data.objects.get('uw_bubbles')
    if ob is not None:
        bpy.data.objects.remove(ob, do_unlink=True)


_effect('retro_wireframe', kind='native', undo=_retro_wireframe_undo,
        params=[('color', 'green'), ('line_width', 1.5, 0, 100), ('bg_color', (0.0, 0.0, 0.0)),
                ('line_intensity', 1.0, 0, 100), ('hdr_channel_cap', 6.3, 0, 1000)],
        doc="every mesh drawn as its triangle wireframe at a constant pixel width (a view-layer material override "
            "with the Wireframe node), color green / amber / blue / multicolor (a palette pick per triangle), the "
            "world the background colour; screen_effects.set_wire_color() and retro_wireframe_cleanup() as "
            "WebGPU's setColor() and cleanup()")(_retro_wireframe)


def _underwater_params():
    from .screen_effects import UNDERWATER
    return [tuple(p) for p in UNDERWATER]


_effect('underwater', kind='pass', params=_LazyParams(_underwater_params), undo=_underwater_undo,
        build_opts={'bubble_count': 600, 'bubble_radius': 6.0, 'bubble_range_y': 8.0},
        unsupported={'bubble_amt': 'declared by underwater.js but never read by its shader'},
        doc='the camera under water: a caustic water roof where nothing was drawn, caustics on up-facing geometry '
            'and depth fog toward the horizon colour, god rays (a screen pass on the Depth and Normal passes and '
            'the camera), and rising air bubbles round the camera (Geometry Nodes)')(
    _pass_build('screen_effects', 'underwater'))


_effect('cross_hatch', kind='pass', params=_LazyParams(_hatch_params),
        unsupported={**_FRAME_SIZE, 'cam_near': 'the Depth pass is metric: no depth to unpack',
                     'cam_far': "the far plane follows the scene camera's clip end (a driver)"},
        doc='a pencil drawing: noise-wiggled gradient outlines at three scales + depth edges, five hatch layers '
            'following the value (turned on near objects), a facing boost, paper grain; its 256 x 256 noise '
            'texture regenerated byte for byte')(_pass_build('screen_effects', 'cross_hatch'))


_effect('blueprint', kind='pass', params=_LazyParams(_blueprint_params),
        unsupported={**_FRAME_SIZE, 'cam_near': 'the Depth pass is metric: the near plane cancels in the depth',
                     'cam_far': "the far plane follows the scene camera's clip end (a driver)",
                     'shade_hi': 'declared by blueprint.js but never read by its shader'},
        doc='an engineering blueprint: paper, printed grid rulings, ink on depth / normal / rim edges and striped '
            'shading; reads the Depth and Normal passes, turned to view space by the camera (drivers)')(
    _pass_build('screen_effects', 'blueprint'))
_effect('rain_on_camera', params=[('amount', 1.0, 0, 10), ('speed', 1.0, -10, 10), ('drop_size', 0.2, 0, 1)],
        build_opts={'resolution': (1920, 1080), 'directions': 12, 'quality': 3, 'blur_size': 9},
        doc='drops running down the lens: the frame refracted through them and blurred behind them (directions x '
            'quality taps, blur_size px of `resolution`), sharp under each drop and trail')(_screen('rain_on_camera'))
_effect('vhs_tape', params=[('intensity', 1.0, 0, 10), ('opacity', 1.0, 0, 1)], unsupported=_FRAME_SIZE,
        doc='tape wobble, tracking noise, head-switching rows, YIQ chroma smear and delay, dropouts, AC beat, grain, '
            'a warm tint')(_screen('vhs_tape'))
# The two pre-bloom flares (WebGPU's _autoEnhancePreBloomHook): three's LensflareNode and AnamorphicNode ported as
# groups, in the chain's 'prebloom' slot so the bloom softens them too, as there.
_effect('lensflare', slot='prebloom', params=_LazyParams(_screen_params('LENSFLARE')), build_opts={'ghost_samples': 4},
        aliases={'ghost_attenuation_factor': 'ghost_attenuation'},
        doc="three's LensflareNode: ghost_samples ghosts of the highlights above threshold, mirrored through the "
            "centre ghost_spacing apart, faded by (1 - distance to centre) ^ ghost_attenuation, tinted ghost_tint, "
            "at a quarter resolution; added x strength before the bloom; opacity")(_screen_group('lensflare'))
_effect('anamorphic_flare', slot='prebloom', params=_LazyParams(_screen_params('ANAMORPHIC')),
        build_opts={'samples': 32}, aliases={'colour': 'color'},
        doc="three's AnamorphicNode: a horizontal streak of `samples` taps `scale` px apart through every highlight "
            "whose luminance (three's luminance() of the RGBA sample: Y + alpha) passes threshold, weighted by its "
            "excess and a linear falloff, tinted color (WebGPU's blue); added x strength before the bloom; "
            "opacity")(_screen_group('anamorphic_flare'))

# nuclear_explosion: the WebGPU screen raymarcher, ported by the SDF volumes as Volume objects in the scene
# (eidoblend/sdf/nuclear_explosion.py: its native_build / native_undo are this registry's build and undo); its options
# are that module's own, checked there (camelCase too).
def _nuke_module():
    try:
        from ...sdf import nuclear_explosion as NX
    except ImportError as ex:
        raise NotImplementedError("effect 'nuclear_explosion' needs eidoblend.sdf.nuclear_explosion (the SDF volumes' "
                                  f"port of nuclear_explosion.js), which did not import: {ex}") from ex
    return NX


def _nuke_build(scene, o):
    if scene.camera is None:                                 # NuclearExplosionFX.applyTo: 'opts.camera required'
        raise ValueError('nuclear_explosion: the scene has no camera (WebGPU\'s applyTo required one; the cloud is '
                         'baked over the scene\'s frames from it)')
    return _nuke_module().native_build(scene, o)


def _nuke_undo(scene):
    try:
        NX = _nuke_module()
    except NotImplementedError:
        return
    NX.native_undo(scene)


_effect('nuclear_explosion', kind='native', passthrough=True, undo=_nuke_undo,
        doc="the mushroom cloud as Volume objects in the scene (eidoblend.sdf.nuclear_explosion: cap, stem, trail, base "
            "surge, its heat palette and keyed glow lights), baked over the scene's frames from its camera; options "
            "that module's: origin (three axes), scale, time_offset, loop_seconds, opacity, quality, bake, "
            "disable_for_perf_test ...")(_nuke_build)

# the WebGPU registry's 33 names, in its order (custom_effects_deno.js), for coverage checks
WEBGPU_NAMES = ['underwater', 'vhs_tape', 'crt', 'old_bw_film', 'nuclear_explosion', 'anamorphic_flare', 'sepia',
                'bleach_bypass', 'after_image', 'rgb_shift', 'rain_on_camera', 'radial_blur', 'box_blur', 'hash_blur',
                'godrays', 'lensflare', 'chromatic_aberration_alpha', 'wavy', 'jitter', 'melt', 'kaleidoscope',
                'neon_edges', 'glitch_bars', 'bw_halftone', 'focus_blur', 'depth_fog', 'dithering', 'blueprint',
                'cross_hatch', 'full_toon', 'retro_wireframe', 'era_looks', 'aeropittura']


# ------------------------------------------------------------------------------------------------- apply
def _cutter(hist):
    def cut(*frames):
        """U.cut(frame, ...): the effect's history restarts at these frames (keyed)."""
        for h in hist:
            h.add_cuts(frames)
    return cut


def applied(scene):
    """The registry effects on the scene: [(slot, name, node)], the chain's in chain order (bloom and the overlay are
    the chain's own stages, not effects, unless 'bloom' was applied through the registry), then the native ones
    (slot 'native', node None: a fog volume, a material override, the lens) in the order applied."""
    return ([(s, n, x) for s, n, x in chain.stages(scene) if n in REGISTRY]
            + [('native', n, None) for n in _natives(scene)])


def remove(scene, *names):
    """Take effects out: a chain effect's node, its history writers and taps (recorded frames stay on disk until
    history.History.clear()) and its keys; a native effect's scene-side changes (undo: the fog volume, the wireframe
    override, the lens's depth of field as it was, the bubbles)."""
    from .history import _fcurves, _remove_fcurve
    t = scene.compositing_node_group
    for nm in names:
        gone = set()
        if t is not None:
            gone |= {n.name for _s, n2, n in chain.stages(scene) if n2 == nm}
            gone |= {n.name for n in t.nodes if n.get('look_input_of') == nm}
            for n in [n for n in t.nodes if n.get('eido_history') and str(n.get('eido_history')).startswith(nm + '_')]:
                gone.add(n.name)
                t.nodes.remove(n)
        chain.remove_stage(scene, nm)
        ad = t.animation_data if t is not None else None
        if ad and ad.action:                       # the removed nodes' keys (uniforms, history offsets) go too
            for fc in [f for f in _fcurves(ad.action, t) if any(f'nodes["{g}"]' in f.data_path for g in gone)]:
                _remove_fcurve(ad.action, t, fc)
        nat = _natives(scene)
        if nm in nat:
            nat.remove(nm)
            scene[NATIVE_KEY] = nat
        R = REGISTRY.get(nm)
        if R is not None and R.get('undo'):
            R['undo'](scene)


def clear(scene):
    """Remove every registry effect, chain and native. CustomEffectsDeno.applyTo replaced the scene's effects on each
    call; apply_to here adds to them, so clear(scene) first gives the WebGPU behaviour."""
    remove(scene, *[n for _s, n, _x in applied(scene)])


def _names(effects):
    if not effects:
        raise ValueError('apply_to: effects required (a name, a comma string or a list)')
    names = [str(e).strip() for e in (effects.split(',') if isinstance(effects, str) else effects)]
    names = [n for n in names if n]
    if not names:
        raise ValueError('apply_to: effects must contain at least one entry')
    return names


def apply_to(scene, effects, opts=None):
    """Add effects (a comma string or a list) to the scene's post chain, in order, each on its layer (layer_of).
    opts: {effect: {option: value}}, the WebGPU options (camelCase or snake_case). Returns an FX handle:
    .uniforms[effect][option] (or .uniforms[option] with one effect) -> the socket to set or key,
    .key(effect, option, frame, value), .cut(frame), .effects."""
    opts = opts or {}
    names = _names(effects)
    for nm in names:
        if nm not in REGISTRY:
            raise KeyError(f'apply_to: unknown effect {nm!r}. Registered: {", ".join(REGISTRY)}')
    fx = FX(scene)
    for nm in names:
        R = REGISTRY[nm]
        raw = opts.get(nm, {})
        o = _options(nm, R, raw)
        if nm in ALWAYS_UNDER and o.get('layer') == 'over':
            print(f"[custom_effects] {nm}: always under the overlay (a world effect); layer 'over' ignored",
                  flush=True)
        slot = R['slot'] or layer_of(nm, o)
        hist = []
        if R['kind'] == 'group':
            made = R['build'](scene, o)
            t = chain.tree(scene)
            node = t.nodes.new('CompositorNodeGroup')
            node.node_tree = made
            chain.add_stage(scene, slot, nm, node)
            socks = _Uniforms({s.name: s for s in node.inputs if s.name != 'Image'})
            for k, v in o.items():
                if k in socks:
                    s = socks[k]
                    s.default_value = _socket_value(s, v)
        elif R['kind'] == 'pass':
            node, socks, hist = R['build'](scene, o, nm, slot)
            socks = _Uniforms(socks)
        else:
            node, socks = R['build'](scene, o)
            socks = _Uniforms(socks)
            # a native effect that built a chain stage instead (depth_fog mode 'screen') is a chain effect
            if R['kind'] == 'native' and not any(n2 == nm for _s, n2, _x in chain.stages(scene)):
                _record_native(scene, nm)
        fx.nodes[nm] = node
        fx.uniforms[nm] = socks
        if hist:
            fx.histories[nm] = hist
            socks.cut = _cutter(hist)
        fx.effects.append({'name': nm, 'layer': slot, 'node': node, 'uniforms': socks})
    if len(names) > 1:
        under = [e['name'] for e in fx.effects if e['layer'] in ('prebloom', 'bloom', 'under')]
        over = [e['name'] for e in fx.effects if e['layer'] == 'over']
        print(f"[custom_effects] effects split: under the overlay [{', '.join(under) or 'none'}], "
              f"over it [{', '.join(over) or 'none'}]", flush=True)
    return fx

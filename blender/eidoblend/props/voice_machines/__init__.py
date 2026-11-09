"""eidoblend.props.voice_machines: eight historical voice machines, 1939 -> 2001, built by name. The WebGPU edition's
eidoverse/props/voice_machines/index.js (the registry) and the era-2 kit its machine modules share, in Blender 5.2.

    import sys; sys.path.insert(0, '<repo>/blender')
    from eidoblend.props import voice_machines as VM

    c64 = VM.build_machine('c64')                    # a Machine: group (its root Empty), parts, update, dispose
    c64.group.location = (0.0, 0.0, 0.74)            # on a desk top: every machine rests on z = 0 of its root
    c64.parts['screen'].set_text(['READY.', 'SAY "I WAS A MOUTH"', 'I WAS A MOUTH', 'READY.'], True)
    # per frame, deterministic in t, called in time order (a scene's render_frame(ctx, t, i) passes ctx):
    c64.update(t, {'power': 1.0, 'voice': loudness(t)}, ctx=ctx)

Every module can also be used on its own: ``from eidoblend.props.voice_machines import c64; m = c64.build()``.
The machines come from the pack eidoverse/assets/models/voice_machines/ (README.md, SOURCES.md): the same GLBs the
WebGPU modules load, imported once per blend into a source collection outside every scene, and linked from there.

All machines: metres, Blender axes (+Z up, the front toward -Y), resting on z = 0 of their root, deterministic in t.
MACHINES[name]['footprint'] is the measured bounding box (width x, depth y, height z) of the built group and 'center'
its XY centre offset from the root (add its negation to group.location to centre a machine on a pedestal).

How update(t, state) becomes Blender data: every WebGPU uniform of a machine (its screen's power and gain, each LED's
level, the speaker glow) is a float custom property on the machine's root Empty, and the materials read it through a
driver (one variable, no Python). update() computes the values exactly as the engine did and keys them at the frame of
t (CONSTANT by default: a uniform holds what the last update set). A screen is a PNG sequence through
eidoblend.media.screens: update() draws a new frame only when the drawing changes (text, a cursor blink); the frames
between hold the last drawing, and after the last one Blender holds it. So the saved .blend plays and renders any
frame on its own.

    c64.show_scene('sam_1982', (1, 90))           # an era canvas scene (era_screens_*.js) on the tube over a range

The era-2 kit (the JS kept an identical copy in speakspell, c64, mac1984, dectalk and desktop2001): rng, lin, the
tiling noise, triplanar, the baked / metal / glow / LED / screen / plastic materials (write_curvature, curvature and
bump_normal for plastic), pixel_footprint and pixel_angle (the screens' footprint, measured in the shader),
load_glb, EraScreen, SceneLayer, Channel, Lamp and the Machine base class; the canvas-2D core (make_canvas ->
Canvas2D, rr, speckle) with canvas_texture, build_mips and flip_uv; and the geometry builders on BMesh for new props
in the same style (rbox, keycap, rr_points, loft_rings, rounded_rect_shape + shape_geometry, bake, merge, smooth,
planar_uv, planar_uv_facing, rounded_polyline + wire, mesh). Guide: tools-guides/voice-machines.md.
"""
from __future__ import annotations

import glob
import importlib
import inspect
import math
import os
import re
import shutil
import tempfile
import uuid
from functools import lru_cache
from pathlib import Path

import numpy as np

try:
    import bpy
except ImportError:            # the registry and the screens' drawing code also run in plain Python (tests, docs)
    bpy = None

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]                                   # <repo>/blender/eidoblend/props/voice_machines
PACK = REPO / 'eidoverse' / 'assets' / 'models' / 'voice_machines'

# ------------------------------------------------------------------------------------------------- the registry ---
# year, title, era as index.js; footprint (width x, depth y, height z) and centre (x, y) in Blender axes: three's
# [w, h, d] and [cx, cz] mapped by (x, y, z) -> (x, -z, y). text / drive: the screen or text API and the state keys.
MACHINES = {
    'voder': dict(
        year=1939, title="Bell Labs Voder (New York World's Fair)", era=1,
        text=None, drive='{voice, power} or {keys[10], wrist, stops[3], quiet, pedal, level, power}',
        footprint=(1.28, 1.32, 1.70), center=(0.0, 0.32)),
    'mainframe': dict(
        year=1961, title='IBM 7090-era computer room (the Bell Labs "Daisy Bell")', era=1,
        text=None, drive='{tape_speed | tape_stop | tape_pos, voice, power}: call in time order',
        footprint=(4.58, 2.81, 1.87), center=(0.0, -0.64)),
    'teletype': dict(
        year=1966, title='Teletype ASR-33 on its pedestal (ELIZA)', era=1,
        text="update(t, {text, n_chars}) or parts['paper'].set_text(full_text, n_chars)",
        drive='{text, n_chars, voice, power}',
        footprint=(0.60, 0.76, 1.07), center=(0.0, 0.12)),
    'speakspell': dict(
        year=1978, title='Texas Instruments Speak & Spell', era=2,
        text="parts['display'].set_text('LOVE') (8 characters at most)", drive='{power, voice}',
        footprint=(0.18, 0.10, 0.26), center=(0.0, 0.03)),
    'c64': dict(
        year=1982, title='Commodore 64 with its colour monitor', era=2,
        text="parts['screen'].set_text([lines], cursor_on) or update state {lines, cursor_on}",
        drive='{power, voice, lines?, cursor_on?}',
        footprint=(0.41, 0.69, 0.34), center=(0.0, 0.09)),
    'mac1984': dict(
        year=1984, title='Macintosh 128K with keyboard and mouse', era=2,
        text="parts['screen'].set_text('hello')", drive='{power, voice, text?}',
        footprint=(0.45, 0.50, 0.34), center=(0.06, -0.05)),
    'dectalk': dict(
        year=1984, title='DECtalk DTC01 speech synthesizer', era=2,
        text=None, drive='{power, voice, leds?: [power, speech, back]}',
        footprint=(0.46, 0.31, 0.10), center=(0.0, 0.0)),
    'desktop2001': dict(
        year=2001, title='Early-2000s desktop PC (CRT, tower, speakers, keyboard, mouse)', era=2,
        text="parts['screen'].set_text('reading screens')", drive='{power, voice, text?}',
        footprint=(1.15, 0.91, 0.45), center=(0.0, -0.03)),
}

NAMES = list(MACHINES)


def load_machine(name: str):
    """The module for one machine (its build() plus any extras, e.g. the Voder's pattern(t)), imported on first use."""
    if name not in MACHINES:
        raise ValueError(f"[voice_machines] unknown machine '{name}' (have: {', '.join(NAMES)})")
    mod = f'{__name__}.{name}'
    try:
        return importlib.import_module(mod)
    except ModuleNotFoundError as e:
        if e.name == mod:
            raise ModuleNotFoundError(f"[voice_machines] '{name}' is registered but props/voice_machines/{name}.py "
                                      'is not written yet') from e
        raise


def _call_build(build, opts):
    """build(**opts) when it takes them as keywords; build(opts) when its first parameter is an options dict
    (``def build(opts)``, the JS form); otherwise a TypeError naming the options it does not take."""
    params = list(inspect.signature(build).parameters.values())
    named = {p.name for p in params if p.kind in (p.KEYWORD_ONLY, p.POSITIONAL_OR_KEYWORD)}
    if any(p.kind is p.VAR_KEYWORD for p in params) or not opts or set(opts) <= named:
        return build(**opts)
    if params and params[0].name == 'opts':
        return build(opts)
    raise TypeError(f'{build.__module__}.build() takes no option {", ".join(sorted(set(opts) - named))} '
                    f'(it takes {", ".join(sorted(named))})')


def build_machine(machine: str, opts: dict = None, /, **kw):
    """Build one machine by name -> its module's build(**opts) (a Machine: group, parts, update(t, state),
    dispose(), plus the module's own extras). Options come as a dict, as keywords, or both (name= is the root's
    object name). The root Empty gets the machine's record as 'voice_machine'."""
    o = dict(opts or {})
    o.update(kw)
    m = _call_build(load_machine(machine).build, o)
    group = m.group if hasattr(m, 'group') else m['group']
    group['voice_machine'] = {'name': machine, **{k: (list(v) if isinstance(v, tuple) else v)
                                                  for k, v in MACHINES[machine].items() if v is not None}}
    return m


# ================================================================================================= THE ERA-2 KIT ===
# The helpers the era-2 machines share (the JS keeps an identical copy in speakspell/c64/mac1984/dectalk/desktop2001;
# here they live once). A port of eraKit: rng, lin, the tiling noise, triplanar, the baked / metal / glow / LED /
# screen materials, the GLB loader and eraScreen (makeScreen), plus what Blender needs on top: the root channels
# (keyed uniforms) and the machine base class.

def _require_bpy():
    if bpy is None:
        raise RuntimeError('[voice_machines] building a machine needs Blender (bpy)')


def js_round(x: float) -> int:
    """JavaScript's Math.round: halves go up (Python's round() goes to even)."""
    return int(math.floor(x + 0.5))


# ---------------------------------------------------------------------------------------- numbers and colours ---
def _imul(a, b):
    return ((a & 0xFFFFFFFF) * (b & 0xFFFFFFFF)) & 0xFFFFFFFF


def rng(seed: int):
    """The kit's deterministic generator (never random()): a function returning floats in [0, 1), the same
    sequence as the JS rng(seed) to the last bit."""
    i32 = ((int(seed) + 0x80000000) & 0xFFFFFFFF) - 0x80000000        # seed | 0
    s = int(float(i32) * 2654435761.0) % 0x100000000                    # a double product, then >>> 0 (as JS)

    def nxt():
        nonlocal s
        s = (s + 0x6D2B79F5) & 0xFFFFFFFF
        t = s
        t = _imul(t ^ (t >> 15), t | 1)
        t ^= (t + _imul(t ^ (t >> 7), t | 61)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296
    return nxt


def srgb_to_linear(c: float) -> float:
    return c * 0.0773993808 if c < 0.04045 else (c * 0.9478672986 + 0.0521327014) ** 2.4


def hex_rgb(h: str) -> tuple:
    """'#rrggbb' -> (r, g, b) in 0..1, sRGB-encoded."""
    h = h.lstrip('#')
    if len(h) == 3:
        h = ''.join(ch * 2 for ch in h)
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def lin(h: str) -> tuple:
    """An sRGB hex -> linear RGB (three's new Color(hex), as the kit's lin() node)."""
    return tuple(srgb_to_linear(c) for c in hex_rgb(h))


def lin4(h: str) -> tuple:
    return (*lin(h), 1.0)


# --------------------------------------------------------------------------------------------- the tiling noise ---
NOISE_NAME = 'eido_vm_noise'


@lru_cache(maxsize=1)
def noise_data(n: int = 256) -> np.ndarray:
    """The kit's one shared tiling noise: 4 independent periodic fBm channels (R period 4, G 8, B 32, A 64 cells
    per tile), uint8 (n, n, 4), row 0 at v = 0. Bit-exact with the JS noiseTexture() (its lattices are float32
    arrays, the arithmetic doubles: the same here)."""
    chans = ((4, 5, 11), (8, 4, 23), (32, 3, 37), (64, 2, 53))
    out = np.empty((n, n, 4), np.uint8)
    idx = np.arange(n, dtype=np.float64)
    for ch, (period, octaves, seed) in enumerate(chans):
        r = rng(seed)
        lats = []
        for o in range(octaves):
            p = period << o
            lats.append((p, np.array([r() for _ in range(p * p)], np.float32).astype(np.float64)))
        v = np.zeros((n, n))
        amp, tot = 0.5, 0.0
        for p, L in lats:
            f = idx / n * p
            i0 = np.floor(f).astype(np.int64)
            fr = f - i0
            s = fr * fr * (3 - 2 * fr)
            x0, x1 = i0 % p, (i0 + 1) % p
            y0, y1 = x0 * p, x1 * p
            a = L[y0[:, None] + x0[None, :]]
            b = L[y0[:, None] + x1[None, :]]
            c = L[y1[:, None] + x0[None, :]]
            d = L[y1[:, None] + x1[None, :]]
            u, w = s[None, :], s[:, None]
            v += amp * (a + (b - a) * u + (c - a) * w + (a - b - c + d) * u * w)
            tot += amp
            amp *= 0.5
        out[..., ch] = np.floor(255 * v / tot + 0.5).astype(np.uint8)
    return out


def noise_image():
    """The tiling noise as a packed, non-colour Blender image (one per blend, shared by every machine)."""
    _require_bpy()
    img = bpy.data.images.get(NOISE_NAME)
    if img is not None and tuple(img.size) == (256, 256):
        return img
    data = noise_data()
    img = bpy.data.images.new(NOISE_NAME, 256, 256, alpha=True, float_buffer=False)
    img.colorspace_settings.name = 'Non-Color'
    img.alpha_mode = 'CHANNEL_PACKED'
    img.pixels.foreach_set((data.astype(np.float32) / 255.0).ravel())
    img.pack()
    return img


noise_texture = noise_image           # the JS name (noiseTexture)


# ------------------------------------------------------------------------------------------- a node graph helper ---
def _is_num(v):
    return isinstance(v, (int, float))


class Nodes:
    """A small expression helper over a shader node tree (the kit's TSL graphs, written as code): numbers fold in
    Python, sockets get Math / Vector Math nodes, constants land on the inputs."""

    def __init__(self, tree, x=-2400, y=1000):
        self.tree = tree
        self.k, self.x, self.y = 0, x, y

    def node(self, idname, label=None, **props):
        n = self.tree.nodes.new(idname)
        col, row = divmod(self.k, 16)
        n.location = (self.x + col * 210, self.y - row * 64)
        n.hide = True
        self.k += 1
        if label:
            n.label = label
        for key, val in props.items():
            setattr(n, key, val)
        return n

    def link(self, src, dst):
        if _is_num(src):
            dv = dst.default_value
            dst.default_value = tuple([float(src)] * len(dv)) if hasattr(dv, '__len__') else float(src)
        elif isinstance(src, (tuple, list)):
            n = len(dst.default_value)
            v = [float(x) for x in src][:n]
            dst.default_value = tuple(v + [1.0] * (n - len(v)))
        else:
            self.tree.links.new(src, dst)

    # scalars
    def math(self, op, a, b=0.0, clamp=False):
        n = self.node('ShaderNodeMath', operation=op, use_clamp=clamp)
        self.link(a, n.inputs[0])
        self.link(b, n.inputs[1])
        return n.outputs[0]

    def add(self, a, b):
        return a + b if _is_num(a) and _is_num(b) else self.math('ADD', a, b)

    def sub(self, a, b):
        return a - b if _is_num(a) and _is_num(b) else self.math('SUBTRACT', a, b)

    def mul(self, a, b):
        return a * b if _is_num(a) and _is_num(b) else self.math('MULTIPLY', a, b)

    def div(self, a, b):
        return a / b if _is_num(a) and _is_num(b) else self.math('DIVIDE', a, b)

    def min(self, a, b):
        return min(a, b) if _is_num(a) and _is_num(b) else self.math('MINIMUM', a, b)

    def max(self, a, b):
        return max(a, b) if _is_num(a) and _is_num(b) else self.math('MAXIMUM', a, b)

    def abs(self, a):
        return abs(a) if _is_num(a) else self.math('ABSOLUTE', a)

    def cos(self, a):
        return math.cos(a) if _is_num(a) else self.math('COSINE', a)

    def sqrt(self, a):
        return math.sqrt(a) if _is_num(a) else self.math('SQRT', a)

    def clamp(self, x, lo=0.0, hi=1.0):
        if lo == 0.0 and hi == 1.0:
            return self.math('ADD', x, 0.0, clamp=True)
        return self.max(self.min(x, hi), lo)

    def smoothstep(self, e0, e1, x):
        """GLSL smoothstep(e0, e1, x), also for e0 > e1 (a Map Range with its smoothstep curve, clamped)."""
        n = self.node('ShaderNodeMapRange', data_type='FLOAT', interpolation_type='SMOOTHSTEP', clamp=True)
        self.link(x, n.inputs['Value'])
        self.link(e0, n.inputs['From Min'])
        self.link(e1, n.inputs['From Max'])
        self.link(0.0, n.inputs['To Min'])
        self.link(1.0, n.inputs['To Max'])
        return n.outputs['Result']

    # vectors (colours ride as vectors)
    def vmath(self, op, a, b=None, scale=None):
        n = self.node('ShaderNodeVectorMath', operation=op)
        self.link(a, n.inputs[0])
        if b is not None:
            self.link(b, n.inputs[1])
        if scale is not None:
            self.link(scale, n.inputs[3])
        return n.outputs['Value'] if op in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE') else n.outputs['Vector']

    def vscale(self, v, s):
        return self.vmath('SCALE', v, scale=s)

    def sep(self, v):
        n = self.node('ShaderNodeSeparateXYZ')
        self.link(v, n.inputs[0])
        return n.outputs[0], n.outputs[1], n.outputs[2]

    def comb(self, x, y, z=0.0):
        n = self.node('ShaderNodeCombineXYZ')
        for i, c in enumerate((x, y, z)):
            self.link(c, n.inputs[i])
        return n.outputs[0]

    def green(self, color):
        n = self.node('ShaderNodeSeparateColor')
        self.link(color, n.inputs[0])
        return n.outputs['Green']

    def mix_color(self, k, a, b):
        """mix(a, b, k) of two colours. (A Mix node's sockets share names across its data types: inputs['A'] is the
        float one, so the colour sockets are picked by type.)"""
        n = self.node('ShaderNodeMix', data_type='RGBA')
        sock = lambda coll, name, typ: next(s for s in coll if s.name == name and s.type == typ)  # noqa: E731
        self.link(k, sock(n.inputs, 'Factor', 'VALUE'))
        self.link(a, sock(n.inputs, 'A', 'RGBA'))
        self.link(b, sock(n.inputs, 'B', 'RGBA'))
        return sock(n.outputs, 'Result', 'RGBA')

    def value(self, v=0.0, label=None):
        n = self.node('ShaderNodeValue', label=label)
        n.outputs[0].default_value = float(v)
        return n.outputs[0]

    def driven(self, obj, prop, default=0.0, label=None):
        """A Value node that follows obj[prop] through a one-variable driver (no Python expression)."""
        s = self.value(default, label or prop)
        drive(s, obj, prop)
        return s


def drive(socket, obj, prop, path='default_value'):
    """Drive socket.<path> by the custom property obj[prop] (an AVERAGE driver of one variable: no Python runs, so
    it evaluates in a blend opened with auto-run off)."""
    fc = socket.driver_add(path)
    d = fc.driver
    d.type = 'AVERAGE'
    for v in list(d.variables):
        d.variables.remove(v)
    v = d.variables.new()
    v.name = 'v'
    v.type = 'SINGLE_PROP'
    v.targets[0].id_type = 'OBJECT'
    v.targets[0].id = obj
    v.targets[0].data_path = f'["{prop}"]'
    return fc


# ----------------------------------------------------------------------------------------------------- materials ---
def new_material(name):
    """A material with a clean tree: a Principled BSDF into the output. -> (material, principled node)."""
    _require_bpy()
    m = bpy.data.materials.new(name)
    if m.node_tree is None:
        m.use_nodes = True
    t = m.node_tree
    t.nodes.clear()
    out = t.nodes.new('ShaderNodeOutputMaterial')
    out.location = (500, 0)
    b = t.nodes.new('ShaderNodeBsdfPrincipled')
    b.location = (150, 0)
    t.links.new(b.outputs['BSDF'], out.inputs['Surface'])
    return m, b


def triplanar(nb: Nodes, scale: float):
    """Object-space triplanar of the shared noise (the prop can roll in without the grain swimming) -> (rgb, alpha)
    sockets, the JS's vec4 sample. three's local planes yz / xz / xy are Blender's (z, -y) / (x, -y) / (x, z), its
    weights |n| / sum |n| (three's n.y is Blender's n.z)."""
    img = noise_image()
    tc = nb.node('ShaderNodeTexCoord')
    x, y, z = nb.sep(nb.vscale(tc.outputs['Object'], scale))
    ny = nb.mul(y, -1.0)
    planes = (nb.comb(z, ny), nb.comb(x, ny), nb.comb(x, z))
    ax, ay, az = nb.sep(nb.vmath('ABSOLUTE', tc.outputs['Normal']))
    tot = nb.max(nb.add(nb.add(ax, ay), az), 1e-4)
    weights = (nb.div(ax, tot), nb.div(az, tot), nb.div(ay, tot))
    rgb = alpha = None
    for vec, w in zip(planes, weights):
        t = nb.node('ShaderNodeTexImage', image=img, interpolation='Linear', extension='REPEAT')
        nb.link(vec, t.inputs['Vector'])
        c, a = nb.vscale(t.outputs['Color'], w), nb.mul(t.outputs['Alpha'], w)
        rgb = c if rgb is None else nb.vmath('ADD', rgb, c)
        alpha = a if alpha is None else nb.add(alpha, a)
    return rgb, alpha


def baked_material(src, copy=False):
    """bakedMaterial: the glTF material with its baked colour / roughness / normal maps. Blender's glTF importer
    already builds exactly that Principled graph (colour -> Base Color, the packed map's G -> Roughness, B x 0 ->
    Metallic, the normal map through a Normal Map node); copy=True gives a machine its own copy to add to (the
    desktop's speaker cloth). The baked AO stays in the file unwired: EEVEE's ray-traced GI and horizon scan make
    the occlusion, and the map on top would double it (the asset rule of the Blender edition)."""
    return src.copy() if copy else src


def metal_material(name, color='#b8b8bc', rough=0.32):
    """Runtime brushed / plated metal for screws, connector shells and the like: colour mottled by the noise's G,
    roughness broken up by its A (triplanar at 60 / m)."""
    m, b = new_material(name)
    nb = Nodes(m.node_tree)
    rgb, a = triplanar(nb, 60.0)
    g = nb.green(rgb)
    nb.link(nb.vscale(lin(color), nb.add(nb.mul(nb.sub(g, 0.5), 0.25), 1.0)), b.inputs['Base Color'])
    nb.link(nb.max(nb.min(nb.add(rough, nb.mul(nb.sub(a, 0.5), 0.3)), 1.0), 0.08), b.inputs['Roughness'])
    b.inputs['Metallic'].default_value = 1.0
    return m


def glow_material(name, color, root, prop, base='#050505'):
    """A surface lit by the machine's voice (behind grilles, cloth, slots): emission = colour x root[prop] x 2.4,
    broken up by the noise's G (triplanar at 25 / m)."""
    m, b = new_material(name)
    nb = Nodes(m.node_tree)
    b.inputs['Base Color'].default_value = lin4(base)
    b.inputs['Roughness'].default_value = 0.9
    b.inputs['Metallic'].default_value = 0.0
    rgb, _a = triplanar(nb, 25.0)
    nb.link(nb.vscale(lin(color), nb.add(nb.mul(nb.green(rgb), 0.5), 0.75)), b.inputs['Emission Color'])
    nb.link(nb.mul(nb.driven(root, prop, 0.0, 'level'), 2.4), b.inputs['Emission Strength'])
    return m


def led_material(name, color, root, prop, lens=None):
    """A small indicator (LED): a clear-coated lens whose emission is colour x root[prop] x 2.2."""
    m, b = new_material(name)
    nb = Nodes(m.node_tree)
    b.inputs['Base Color'].default_value = (*[c * 0.25 for c in lin(lens or color)], 1.0)
    b.inputs['Roughness'].default_value = 0.25
    b.inputs['Metallic'].default_value = 0.0
    b.inputs['Coat Weight'].default_value = 1.0
    b.inputs['Coat Roughness'].default_value = 0.05
    b.inputs['Emission Color'].default_value = lin4(color)
    nb.link(nb.mul(nb.driven(root, prop, 0.0, 'level'), 2.2), b.inputs['Emission Strength'])
    return m


CURVATURE = 'eido_curv'


def write_curvature(obj, name=CURVATURE):
    """The kit's curvature() as mesh data: 1/m, + convex, − concave, from the interpolated normal against position
    (the JS summed dot(dN, dP) / dot(dP, dP) along the screen's x and y; here the view-free trace of each triangle's
    shape operator, G^-1 B with G the Gram matrix of two edges and B_ij = e_i . (n_j - n_0)), in world metres by the
    object's scale, as a face-corner float attribute `name` for plastic_material. Blender's shader nodes have no
    screen-space derivatives of the normal (and Pointiness is Cycles only), so the mesh carries it. Rerun after a
    change of shape. Returns the per-triangle values."""
    _require_bpy()
    me = obj.data
    me.calc_loop_triangles()
    nt = len(me.loop_triangles)
    vals = np.zeros(len(me.loops), np.float32)
    tr = np.zeros(0)
    if nt:
        tl = np.empty(nt * 3, np.int64)
        me.loop_triangles.foreach_get('loops', tl)
        tl = tl.reshape(-1, 3)
        lv = np.empty(len(me.loops), np.int64)
        me.loops.foreach_get('vertex_index', lv)
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', co)
        cn = np.empty(len(me.loops) * 3)
        me.corner_normals.foreach_get('vector', cn)
        P, N = co.reshape(-1, 3)[lv[tl]], cn.reshape(-1, 3)[tl]
        e1, e2 = P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]
        n1, n2 = N[:, 1] - N[:, 0], N[:, 2] - N[:, 0]
        g11, g12, g22 = (e1 * e1).sum(1), (e1 * e2).sum(1), (e2 * e2).sum(1)
        det = g11 * g22 - g12 * g12
        b11, b12, b21, b22 = (e1 * n1).sum(1), (e1 * n2).sum(1), (e2 * n1).sum(1), (e2 * n2).sum(1)
        tr = np.where(det > 1e-20, (g22 * b11 - g12 * b21 - g12 * b12 + g11 * b22) / np.maximum(det, 1e-20), 0.0)
        tr = tr / (max(obj.matrix_world.to_scale()) or 1.0)
        vals[tl.ravel()] = np.repeat(tr, 3)
    a = me.attributes.get(name) or me.attributes.new(name, 'FLOAT', 'CORNER')
    a.data.foreach_set('value', vals)
    return tr


def plastic_material(name, *, color='#d6ccb0', aged=None, age_amt=0.3, grime='#3e372d', grime_amt=0.5,
                     dust='#b9b3a4', dust_amt=0.12, rough=0.5, rough_var=0.12, edge=0.25, peel=0.00006, scale=1.0,
                     decal=None, decal_uv=None, decal_rough=None, color_node=None, emissive=None, clearcoat=0.0,
                     clearcoat_rough=0.12, side='FRONT', mottle=0.08, curvature=CURVATURE):
    """plastic: moulded plastic. A base colour with large-scale ageing (yellowing or fading toward ``aged``,
    stronger on up-facing surfaces), mottling, grime in concave fillets, polished convex edges, a little dust on
    top, roughness speckle and a fine orange-peel bump; an optional printed decal. The kit's triplanar noise at 1.3
    / m x scale (the r ~20 cm blotches, g ~10 cm mottle), 6 / m (b ~5 mm grime breakup, a ~2.6 mm speckle) and 42 /
    m (the peel). Curvature comes from the face-corner attribute ``curvature`` (write_curvature(obj) on each mesh
    that wears it; without it the edges and fillets read flat). decal: an Image (with alpha) sampled on the UV map
    ``decal_uv`` (default the active one), unprinted outside 0..1; decal_rough: its roughness. color_node:
    callable (nb) -> colour socket replacing the base colour; emissive: (colour hex, strength); clearcoat /
    clearcoat_rough; side: 'FRONT' (back faces culled, as three's FrontSide) or 'DOUBLE'."""
    m, b = new_material(name)
    nb = Nodes(m.node_tree)
    b.inputs['Metallic'].default_value = 0.0
    nb_rgb, _ = triplanar(nb, 1.3 * scale)
    nm_rgb, nm_a = triplanar(nb, 6.0 * scale)
    sep = nb.node('ShaderNodeSeparateColor')
    nb.link(nb_rgb, sep.inputs[0])
    n_r, n_g = sep.outputs['Red'], sep.outputs['Green']
    sep2 = nb.node('ShaderNodeSeparateColor')
    nb.link(nm_rgb, sep2.inputs[0])
    m_r, m_b = sep2.outputs['Red'], sep2.outputs['Blue']
    cv = _curvature(nb, curvature)
    edge_m = nb.smoothstep(0.25, 0.9, nb.clamp(nb.mul(cv, 0.004)))
    cav_m = nb.smoothstep(0.2, 0.85, nb.clamp(nb.mul(cv, -0.004)))
    geo = nb.node('ShaderNodeNewGeometry')
    _, _, tz = nb.sep(geo.outputs['True Normal'])                      # three's normalWorldGeometry.y
    up = nb.math('POWER', nb.clamp(tz), 2.0)
    c = color_node(nb) if color_node else lin(color)
    c = nb.vscale(c, nb.add(nb.mul(nb.sub(n_g, 0.5), mottle * 2), 1.0))
    if aged:
        k = nb.clamp(nb.mul(nb.smoothstep(0.38, 0.72, nb.add(n_r, nb.mul(up, 0.22))), age_amt))
        c = nb.mix_color(k, c, lin(aged))
    c = nb.mix_color(nb.clamp(nb.mul(nb.mul(cav_m, grime_amt), nb.add(m_b, 0.35))), c, lin(grime))
    c = nb.mix_color(nb.mul(edge_m, edge), c, nb.vscale(c, 1.12))
    c = nb.mix_color(nb.clamp(nb.mul(nb.mul(up, dust_amt), nb.smoothstep(0.3, 0.7, m_r))), c, lin(dust))
    r = nb.add(nb.sub(nb.add(rough, nb.mul(nb.sub(nm_a, 0.5), rough_var * 2)), nb.mul(edge_m, 0.12)),
               nb.mul(up, dust_amt * 0.5))
    if decal is not None:
        t = nb.node('ShaderNodeTexImage', image=decal, interpolation='Linear', extension='CLIP')
        if decal_uv:
            uvn = nb.node('ShaderNodeUVMap', uv_map=decal_uv)
            nb.link(uvn.outputs['UV'], t.inputs['Vector'])
        da = t.outputs['Alpha']                       # extension CLIP: transparent outside 0..1, unprinted
        c = nb.mix_color(da, c, t.outputs['Color'])
        if decal_rough is not None:
            r = nb.add(nb.mul(r, nb.sub(1.0, da)), nb.mul(da, float(decal_rough)))
    nb.link(c, b.inputs['Base Color'])
    nb.link(nb.max(nb.min(r, 1.0), 0.04), b.inputs['Roughness'])
    if peel > 0:                                     # the orange peel: a bump of the 42 / m noise's B, in metres
        p_rgb, _ = triplanar(nb, 42.0 * scale)
        sep3 = nb.node('ShaderNodeSeparateColor')
        nb.link(p_rgb, sep3.inputs[0])
        nb.link(bump_normal(nb, nb.mul(sep3.outputs['Blue'], peel)), b.inputs['Normal'])
    if emissive:
        col, strength = emissive if isinstance(emissive, (tuple, list)) else (emissive, 1.0)
        b.inputs['Emission Color'].default_value = lin4(col)
        b.inputs['Emission Strength'].default_value = float(strength)
    if clearcoat > 0:
        b.inputs['Coat Weight'].default_value = clearcoat
        b.inputs['Coat Roughness'].default_value = clearcoat_rough
    m.use_backface_culling = side == 'FRONT'
    return m


plastic = plastic_material            # the JS name (the kit's plastic(o))


def drive_path(socket, idb, id_type, data_path, path='default_value'):
    """Drive socket.<path> by any property of an ID (an AVERAGE driver of one variable: no Python runs)."""
    fc = socket.driver_add(path)
    d = fc.driver
    d.type = 'AVERAGE'
    for v in list(d.variables):
        d.variables.remove(v)
    v = d.variables.new()
    v.name = 'v'
    v.type = 'SINGLE_PROP'
    v.targets[0].id_type = id_type
    v.targets[0].id = idb
    v.targets[0].data_path = data_path
    return fc


def _pixels_from_centre(nb: Nodes, scene, tc):
    """|2 wx - 1| W + |2 wy - 1| H: a shading point's distance from the frame's centre in pixels along x plus along
    y, with W x H the render size (three one-variable drivers on the scene's resolution x, y and percentage: no
    Python)."""
    wx, wy, _ = nb.sep(tc.outputs['Window'])
    res = []
    for prop in ('resolution_x', 'resolution_y', 'resolution_percentage'):
        s = nb.value(float(getattr(scene.render, prop)), prop)
        drive_path(s, scene, 'SCENE', f'render.{prop}')
        res.append(s)
    k = nb.div(res[2], 100.0)
    dx = nb.mul(nb.abs(nb.sub(nb.mul(wx, 2.0), 1.0)), nb.mul(res[0], k))
    dy = nb.mul(nb.abs(nb.sub(nb.mul(wy, 2.0), 1.0)), nb.mul(res[1], k))
    return nb.add(dx, dy)


def pixel_angle(nb: Nodes, scene, fallback=1.0 / 1500.0):
    """The camera's angle per pixel at the frame's centre (radians: a pixel's size on the image plane one metre
    out), the stand-in for the engine's fwidth() where a shader needs a footprint. Measured in the shader, with no
    camera driver: a shading point's View Vector (x, y, z) against its Window position (wx, wy) gives the field of
    view, |x / z| = |2 wx - 1| tan(fov_x / 2) and |y / z| = |2 wy - 1| tan(fov_y / 2), so

        pixel angle = 2 (|x| + |y|) / |z| / (|2 wx - 1| W + |2 wy - 1| H)

    with W x H the render size in pixels (three one-variable drivers on the scene's resolution x, y and percentage:
    no Python). It follows camera cuts and animated lenses and reads the same in a blend opened with scripts off.
    Exact for a perspective camera with square pixels and no lens shift; within a pixel of the frame's centre
    (where both sides vanish) it blends toward `fallback`. An orthographic camera has no angle per pixel: use
    pixel_footprint, which measures metres per pixel under either."""
    tc = nb.node('ShaderNodeTexCoord')
    cam = nb.node('ShaderNodeCameraData')
    vx, vy, vz = nb.sep(cam.outputs['View Vector'])
    den = _pixels_from_centre(nb, scene, tc)
    num = nb.div(nb.mul(nb.add(nb.abs(vx), nb.abs(vy)), 2.0), nb.max(nb.abs(vz), 1e-6))
    near_centre = nb.max(nb.sub(1.0, den), 0.0)
    return nb.div(nb.add(num, nb.mul(near_centre, fallback)), nb.max(den, 1.0))


def pixel_footprint(nb: Nodes, scene, fallback=1.0 / 1500.0):
    """The metres one pixel spans at the shading point, across the view: the depth times the pixel angle through a
    perspective camera, ortho_scale / width through an orthographic one. Measured in the shader like pixel_angle,
    from the point's camera-space position (x, y) against its Window position: |x| = |2 wx - 1| W f / 2 and
    |y| = |2 wy - 1| H f / 2 for a footprint f under either projection, so

        footprint = 2 (|x| + |y|) / (|2 wx - 1| W + |2 wy - 1| H)

    Exact for square pixels and no lens shift; within a pixel of the frame's centre it blends toward
    `fallback` x the view depth (a perspective camera's pixel angle there)."""
    tc = nb.node('ShaderNodeTexCoord')
    cx, cy, _ = nb.sep(tc.outputs['Camera'])
    depth = nb.node('ShaderNodeCameraData').outputs['View Z Depth']
    den = _pixels_from_centre(nb, scene, tc)
    num = nb.mul(nb.add(nb.abs(cx), nb.abs(cy)), 2.0)
    near_centre = nb.max(nb.sub(1.0, den), 0.0)
    return nb.div(nb.add(num, nb.mul(nb.mul(near_centre, fallback), depth)), nb.max(den, 1.0))


def screen_material(name, screen, root, *, power='power', gain='gain', gain_k=1.0, glass='#0b0d0c', rough=0.32,
                    coat=1.0, coat_rough=0.035, window=(0.0, 0.0, 1.0, 1.0), parallax=0.0, face_size=(1.0, 1.0),
                    barrel=0.0, scan=0, scan_amt=0.3, corner=0.0, vignette=0.0, tint=None, bleed=0.0, glow=None,
                    crt_on=False, flip=False, tube_height=None, color_node=None, roughness_node=None,
                    coat_node=None, scene=None, layers=()):
    """A display behind glass (screenMaterial): the screen's image as emission under a clear coat, so it reads as a
    lit screen and still catches reflections. ``screen`` is an EraScreen (its image sequence); power and gain are
    root properties (driven); the emission is image x power x gain x gain_k. layers: [(SceneLayer, prop)]: other
    frames (an era canvas scene, a movie) mixed over the drawing by root[prop] (0 / 1, keyed by show_scene), through
    the same raster, glass and switch-on.

    window (u0, v0, u1, v1): where the image sits in the mesh's UV (outside: glass only). Blender's glTF importer
    gives the UVs the engine's flipUV made, so the JS windows carry over unchanged, and Blender images are stored
    bottom-up like those UVs, so the image samples upright (the JS's flipV); flip=True flips it for odd UVs.
    parallax (m): the image recessed behind the glass, over face_size (m). barrel: CRT pincushion. scan: scanline
    count (scan_amt deep), faded where the lines get finer than a pixel (the engine's fwidth, from the pixel's
    footprint, pixel_footprint, and tube_height, the UV square's height in metres). corner: the tube mask's
    rounded corners (fraction of the window). vignette, tint (hex), bleed (horizontal phosphor smear, in u), glow
    (hex: a faint lit-phosphor floor inside the mask). crt_on: the raster opens from a bright line as power rises.
    color_node / roughness_node / coat_node: callables (nb, principled) -> socket that replace the glass colour,
    roughness and coat weight."""
    scene = scene or bpy.context.scene
    m, b = new_material(name)
    nb = Nodes(m.node_tree)
    b.inputs['Metallic'].default_value = 0.0
    b.inputs['Roughness'].default_value = rough
    b.inputs['Coat Weight'].default_value = coat
    b.inputs['Coat Roughness'].default_value = coat_rough
    nb.link(color_node(nb, b) if color_node else lin(glass), b.inputs['Base Color'])
    if roughness_node:
        nb.link(roughness_node(nb, b), b.inputs['Roughness'])
    if coat_node:
        nb.link(coat_node(nb, b), b.inputs['Coat Weight'])
    P = nb.driven(root, power, 1.0, 'power')
    G = nb.driven(root, gain, 1.0, 'gain')
    tc = nb.node('ShaderNodeTexCoord')
    sx, sy, _ = nb.sep(tc.outputs['UV'])
    if parallax > 0:                       # the view in the object's frame: three's x, y, z are Blender's x, z, -y
        vt = nb.node('ShaderNodeVectorTransform', vector_type='VECTOR', convert_from='WORLD', convert_to='OBJECT')
        nb.link(nb.node('ShaderNodeNewGeometry').outputs['Incoming'], vt.inputs[0])
        vx, vy, vz = nb.sep(nb.vmath('NORMALIZE', vt.outputs[0]))
        z3 = nb.max(nb.mul(vy, -1.0), 0.25)
        sx = nb.sub(sx, nb.mul(nb.div(vx, z3), parallax / face_size[0]))
        sy = nb.sub(sy, nb.mul(nb.div(vz, z3), parallax / face_size[1]))
    u0, v0, u1, v1 = window
    wx = nb.div(nb.sub(sx, u0), u1 - u0)
    wy = nb.div(nb.sub(sy, v0), v1 - v0)
    if barrel > 0:
        cx, cy = nb.sub(wx, 0.5), nb.sub(wy, 0.5)
        k = nb.add(1.0, nb.mul(nb.add(nb.mul(cx, cx), nb.mul(cy, cy)), barrel))
        wx, wy = nb.add(nb.mul(cx, k), 0.5), nb.add(nb.mul(cy, k), 0.5)
    mx, my = wx, wy                                          # the tube mask never squeezes
    squeeze = 1.0
    if crt_on:      # CRT switch-on: the raster opens from a bright horizontal line as power rises
        squeeze = nb.add(nb.mul(nb.smoothstep(0.05, 0.7, P), 0.99), 0.01)
        wy = nb.add(nb.div(nb.sub(wy, 0.5), squeeze), 0.5)
    s = nb.comb(wx, nb.sub(1.0, wy) if flip else wy)
    th = tube_height if tube_height else 0.25
    foot = []

    def footprint():
        """Metres of the screen one image pixel covers: the pixel's footprint across the view / the tilt (the
        stand-in for the engine's screen-space derivatives; perspective or orthographic)."""
        if not foot:
            geo = nb.node('ShaderNodeNewGeometry')
            tilt = nb.max(nb.abs(nb.vmath('DOT_PRODUCT', geo.outputs['Normal'], geo.outputs['Incoming'])), 0.25)
            foot.append(nb.div(pixel_footprint(nb, scene), tilt))
        return foot[0]

    def sample(scr, vec, nearest):
        if not nearest:
            n = scr.texture_node(m.node_tree)
            n.hide = True
            nb.link(vec, n.inputs['Vector'])
            return n.outputs['Color']
        # nearest magnification + mipmapped minification (the engine's NearestFilter / LinearMipmapLinearFilter):
        # crisp texels up close, the mip average far off (a 1-bit dither greys instead of shimmering). EEVEE's
        # Closest has no mips, so the two samples blend by the texels one pixel covers.
        near, smooth = scr.texture_node(m.node_tree, 'Closest'), scr.texture_node(m.node_tree, 'Linear')
        for n in (near, smooth):
            n.hide = True
            nb.link(vec, n.inputs['Vector'])
        texels_per_m = nb.div(scr.ph / (th * (v1 - v0)), squeeze)
        k = nb.smoothstep(0.6, 1.4, nb.mul(footprint(), texels_per_m))
        return nb.mix_color(k, near.outputs['Color'], smooth.outputs['Color'])
    mixes = [(layer, nb.driven(root, prop, 0.0, prop)) for layer, prop in layers]

    def tex(vec):
        col = sample(screen, vec, screen.nearest)
        for layer, k in mixes:
            col = nb.mix_color(k, col, sample(layer, vec, False))
        return col
    col = tex(s)
    if bleed > 0:   # horizontal phosphor / chroma bleed: a cheap 3-tap smear
        right = nb.vscale(tex(nb.vmath('ADD', s, (bleed, 0, 0))), 0.2)
        left = nb.vscale(tex(nb.vmath('SUBTRACT', s, (bleed, 0, 0))), 0.2)
        col = nb.vmath('ADD', nb.vmath('ADD', nb.vscale(col, 0.6), right), left)
    if scan > 0:
        ph = nb.mul(wy, scan * math.pi * 2)
        # the engine's fwidth(w.y * scan): scanlines per pixel, from the camera's pixel angle, the depth and the tilt
        per_m = nb.div(scan / (th * (v1 - v0)), squeeze)
        fw = nb.mul(footprint(), per_m)
        fade = nb.clamp(nb.sub(1.0, nb.mul(fw, 1.4)))
        dark = nb.mul(nb.mul(nb.add(nb.mul(nb.cos(ph), 0.5), 0.5), scan_amt), fade)
        col = nb.vscale(col, nb.sub(1.0, dark))
    qx, qy = nb.mul(nb.abs(nb.sub(mx, 0.5)), 2.0), nb.mul(nb.abs(nb.sub(my, 0.5)), 2.0)
    if corner > 0:
        cr = corner * 2
        kx, ky = nb.sub(qx, 1.0 - cr), nb.sub(qy, 1.0 - cr)
        px, py = nb.max(kx, 0.0), nb.max(ky, 0.0)
        dist = nb.sub(nb.add(nb.sqrt(nb.add(nb.mul(px, px), nb.mul(py, py))), nb.min(nb.max(kx, ky), 0.0)), cr)
    else:
        dist = nb.sub(nb.max(qx, qy), 1.0)
    inside = nb.sub(1.0, nb.smoothstep(-0.01, 0.003, dist))
    k = inside
    if crt_on:      # outside the opened raster: dark; a collapsed raster burns brighter
        qy2 = nb.mul(nb.abs(nb.sub(wy, 0.5)), 2.0)
        k = nb.mul(nb.mul(k, nb.sub(1.0, nb.smoothstep(0.98, 1.0, qy2))),
                   nb.min(nb.div(1.0, nb.add(nb.mul(squeeze, 0.85), 0.15)), 3.0))
    if vignette > 0:
        k = nb.mul(k, nb.sub(1.0, nb.mul(nb.add(nb.mul(qx, qx), nb.mul(qy, qy)), vignette * 0.5)))
    out = nb.vscale(col, k)
    if tint:
        out = nb.vmath('MULTIPLY', out, lin(tint))
    if glow:
        out = nb.vmath('ADD', out, nb.vscale(lin(glow), nb.mul(inside, 0.02)))
    nb.link(out, b.inputs['Emission Color'])
    nb.link(nb.mul(nb.mul(P, G), gain_k), b.inputs['Emission Strength'])
    m['eido_screen'] = screen.image.name
    return m


# ---------------------------------------------------------------------------------- the pack's GLBs, imported once ---
def load_glb(key: str) -> dict:
    """loadGLB: the machine's GLB from the pack, imported ONCE per blend into a source collection that is in no scene
    (kept by a fake user) -> {GLB node name: source object}. Machines copy these objects: the baked parts share the
    source's mesh and its imported materials and packed maps, so a second C64 costs no second set of textures."""
    _require_bpy()
    coll = next((c for c in bpy.data.collections if c.get('eido_vm_source') == key), None)
    if coll is None or not len(coll.objects):
        path = PACK / f'{key}.glb'
        if not path.is_file():
            raise FileNotFoundError(f'[{key}] {path} is missing (the voice machines pack, '
                                    'eidoverse/assets/models/voice_machines/)')
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(path))
        new = [o for o in bpy.data.objects if o not in before]
        if coll is None:
            coll = bpy.data.collections.new(f'vm_source_{key}')
        coll.use_fake_user = True
        coll['eido_vm_source'] = key
        coll['eido_src_asset'] = str(path)
        for o in new:
            for c in list(o.users_collection):
                c.objects.unlink(o)
            coll.objects.link(o)
            o['vm_part'] = re.sub(r'\.\d{3}$', '', o.name)       # the GLB node's own name (Blender may suffix it)
            o.name = f'vmsrc.{key}.{o["vm_part"]}'
    return {o['vm_part']: o for o in coll.objects}


# --------------------------------------------------------------------------------------------------- the screens ---
def _default_screen_dir(name):
    """//eido_screens/<blend>/<name> beside a saved blend, else a folder of its own under the system temp folder
    (as eidoblend.media.screens does: Blender's session temp is deleted when it exits)."""
    if bpy is not None and bpy.data.filepath:
        return Path(bpy.path.abspath(f'//eido_screens/{Path(bpy.data.filepath).stem}/{name}'))
    d = Path(tempfile.gettempdir()) / 'eido_screens' / f'{name}_{uuid.uuid4().hex[:8]}'
    print(f'[voice_machines] {name}: no screen_dir and the blend is unsaved, so its frames go to {d}')
    return d


class EraScreen:
    """eraScreen + makeScreen, kept as Blender data: the machine's canvas drawn at px wide (height by the aspect, as
    makeScreen rounds it), written as a PNG sequence (<name>_0001.png = the scene's first frame) and shown through
    eidoblend.media.screens. put(frame, image) draws one frame; frames skipped since the last one hold the last
    drawing (hard links, so a long hold costs no disk), and after the last frame Blender holds it."""

    def __init__(self, machine, name, width, height, px, draw, nearest=False, out_dir=None):
        from eidoblend.media import screens
        self._screens = screens
        self.machine = machine
        self.scene = machine.scene
        self.width, self.height = float(width), float(height)
        self.pw = max(2, js_round(px))
        self.ph = max(2, js_round(px * height / width))
        self.draw = draw
        self.nearest = nearest
        self.name = name
        self.prefix = re.sub(r'[^A-Za-z0-9_-]+', '_', name)
        self.dir = Path(out_dir) if out_dir else _default_screen_dir(self.prefix)
        self.dir.mkdir(parents=True, exist_ok=True)
        for old in self.dir.glob(f'{glob.escape(self.prefix)}_[0-9][0-9][0-9][0-9].png'):
            old.unlink()
        self.f0 = int(self.scene.frame_start)
        self.n = 0
        self.nodes = []
        self.drawn = 0                        # drawings made (redraws), for tests and logs
        self._save(1, self.draw(self.pw, self.ph))
        self._link(2, 1)
        self.n = 1
        self.screen = screens.make_screen(width=self.width, height=self.height, px=self.pw, source=self._file(1),
                                          frames=(self.f0, self.f0 + 1), name=name, standalone=False,
                                          interpolation='Closest' if nearest else 'Linear', scene=self.scene)
        self.image = self.screen.image

    def _file(self, k):
        return self.dir / f'{self.prefix}_{k:04d}.png'

    def _save(self, k, img):
        from eidoblend.media import raster
        raster.save_png(img, self._file(k))
        self.drawn += 1

    def _link(self, k, src_k):
        dst, src = self._file(k), self._file(src_k)
        tmp = dst.with_name(dst.name + '.part')
        if tmp.exists():
            tmp.unlink()
        try:
            os.link(src, tmp)
        except OSError:
            shutil.copyfile(src, tmp)
        os.replace(tmp, dst)

    def _hold(self):
        """The hold file (<name>_0000.png, shown before the first frame) follows a redrawn first frame."""
        from PIL import Image
        from PIL.PngImagePlugin import PngInfo
        info = PngInfo()
        info.add_text(self._screens.HOLD_KEY, '1')
        hold = self._file(0)
        tmp = hold.with_name(hold.name + '.part')
        with Image.open(self._file(1)) as im:
            im.save(tmp, format='PNG', pnginfo=info, compress_level=1)
        os.replace(tmp, hold)

    def texture_node(self, tree, interpolation=None):
        """An Image Texture node in any tree, stepping with this screen's frames (clamped at the edges)."""
        n = self.screen.texture_node(tree)
        n.interpolation = interpolation or ('Closest' if self.nearest else 'Linear')
        n.extension = 'EXTEND'
        self.nodes.append(n)
        return n

    def put(self, frame, img):
        """Make `img` the drawing from scene frame `frame` on."""
        k = int(frame) - self.f0 + 1
        if k < 1:
            print(f'[voice_machines] {self.name}: frame {frame} is before the scene start {self.f0}: not drawn')
            return
        if k > self.n:
            for j in range(self.n + 1, k):
                self._link(j, self.n)
        self._save(k, img)
        if k == 1:
            self._hold()
        self.n = max(self.n, k)
        if self.n < 2:
            self._link(2, 1)
        self.sync()

    def redraw(self, frame):
        self.put(frame, self.draw(self.pw, self.ph))

    def sync(self):
        """Point the image and its texture nodes at the frames written so far."""
        self.image['eido_frame_duration'] = max(self.n, 2)
        live = []
        for n in self.nodes:
            try:
                self._screens.configure_user(n.image_user, self.image)
                live.append(n)
            except ReferenceError:                # its material was rebuilt (show_scene) or removed
                pass
        self.nodes = live
        self.image.reload()

    @property
    def frames(self):
        return [self._file(k) for k in range(1, max(self.n, 2) + 1)]


class SceneLayer:
    """Frames shown over a machine's own drawing (show_scene): a media Screen (an era canvas scene's baked sequence,
    a still or a movie), sampled through the tube's raster like the drawing, linear and clamped at the edges."""

    nearest = False

    def __init__(self, screen, label=''):
        self.screen, self.label = screen, label
        self.image = screen.image
        self.pw, self.ph = screen.px_size

    def texture_node(self, tree, interpolation=None):
        n = self.screen.texture_node(tree)
        n.interpolation = interpolation or 'Linear'
        n.extension = 'EXTEND'
        return n

    def __repr__(self):
        return f'<SceneLayer {self.label} {self.pw} x {self.ph}>'


# --------------------------------------------------------------------------------------------- keys on the root ---
def _fcurve(idb, data_path, index=0):
    ad = getattr(idb, 'animation_data', None)
    if ad is None or ad.action is None:
        return None
    from bpy_extras import anim_utils
    cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    if cb is None:
        return None
    for fc in cb.fcurves:
        if fc.data_path == data_path and fc.array_index == index:
            return fc
    return None


def key_prop(obj, prop, frame, interpolation='CONSTANT', ctx=None):
    """Key obj[prop] at `frame` with this interpolation (through ctx.key when a scene's ctx is given: the runner then
    sets the interpolation after render_frame). keyframe_insert alone ignores the preference (BEZIER always)."""
    path = f'["{prop}"]'
    if ctx is not None:
        return ctx.key(obj, path, frame=frame, interpolation=interpolation)
    ok = obj.keyframe_insert(path, frame=frame)
    fc = _fcurve(obj, path)
    if fc is not None:
        pts = fc.keyframe_points
        hit = pts[-1] if len(pts) and abs(pts[-1].co.x - frame) < 1e-3 else next(
            (p for p in pts if abs(p.co.x - frame) < 1e-3), None)
        if hit is not None:
            hit.interpolation = interpolation
    return ok


class Channel:
    """One of the machine's uniforms (a JS uniform(), level, power ...): a float custom property on the machine's
    root that its material(s) follow through a driver. value reads or sets it without a key (a still, or a value
    nothing keys); set(v, t) keys it at the frame of t (or at the current frame when t is None)."""

    def __init__(self, machine, prop, default=0.0, description=''):
        self.machine, self.prop, self.default = machine, prop, float(default)
        g = machine.group
        g[prop] = float(default)
        try:
            g.id_properties_ui(prop).update(default=float(default), description=description)
        except (TypeError, AttributeError):
            pass

    @property
    def value(self) -> float:
        return float(self.machine.group.get(self.prop, self.default))

    @value.setter
    def value(self, v):
        self.machine.group[self.prop] = float(v)

    def set(self, v, t=None, ctx=None, frame=None):
        """Key the value at the frame of t (frame= wins; neither: the scene's current frame)."""
        self.machine.key(self.prop, v, t, ctx, frame)

    def __repr__(self):
        return f'<Channel {self.machine.group.name}["{self.prop}"] = {self.value:g}>'


class Lamp:
    """{mesh, level, set(v)}: an LED or a voice-lit surface; set clamps at 0 as the JS did. level is its Channel."""

    def __init__(self, name, mesh, level):
        self.name, self.mesh, self.level = name, mesh, level

    def set(self, v, t=None, ctx=None, frame=None):
        self.level.set(max(0.0, float(v)), t, ctx, frame)

    def __repr__(self):
        return f'<Lamp {self.name}: {self.level.value:g}>'


# --------------------------------------------------------------------------------------- fonts for the drawings ---
_WIN_FONTS = {   # family -> (regular, bold, italic, bold italic) in the Windows font folder
    'tahoma': ('tahoma.ttf', 'tahomabd.ttf', 'tahoma.ttf', 'tahomabd.ttf'),
    'verdana': ('verdana.ttf', 'verdanab.ttf', 'verdanai.ttf', 'verdanaz.ttf'),
    'arial': ('arial.ttf', 'arialbd.ttf', 'ariali.ttf', 'arialbi.ttf'),
    'franklin gothic medium': ('framd.ttf', 'framd.ttf', 'framdit.ttf', 'framdit.ttf'),
    'trebuchet ms': ('trebuc.ttf', 'trebucbd.ttf', 'trebucit.ttf', 'trebucbi.ttf'),
}
_OTHER_FONTS = ('/usr/share/fonts/truetype/dejavu/DejaVuSans{b}.ttf', '/Library/Fonts/Arial{b}.ttf')


def font_file(families, bold=False, italic=False):
    """The first installed face of a CSS-like family list ('Tahoma, Verdana, Arial'), as the canvas asked Skia's
    system font lookup for it; then DejaVu Sans; else None (Pillow's own default face is used)."""
    win = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
    names = [f.strip().strip('"\'').lower() for f in families.split(',')] if isinstance(families, str) else families
    slot = (2 if italic else 0) + (1 if bold else 0)
    for fam in names:
        files = _WIN_FONTS.get(fam)
        if files and (win / files[slot]).is_file():
            return str(win / files[slot])
    for pat in _OTHER_FONTS:
        p = Path(pat.format(b='-Bold' if bold else ''))
        if p.is_file():
            return str(p)
    return None


@lru_cache(maxsize=64)
def font(families, px, bold=False, italic=False):
    """A Pillow font at px pixels (the em size, as canvas-2D's 'NNpx')."""
    from PIL import ImageFont
    f = font_file(families, bold, italic)
    if f is None:
        return ImageFont.load_default(size=max(1, int(round(px))))
    return ImageFont.truetype(f, max(1, int(round(px))))


# ------------------------------------------------------------------------------------------ the canvas-2D core ---
# makeCanvas, rr and speckle, and the canvas-2D operations the drawings use, on a supersampled straight-alpha float
# buffer: shapes and text rasterised by Pillow, composited source-over in sRGB as canvas does.
CANVAS_SS = 3                         # supersampling (canvas-2D antialiases its shapes and text)


def css_rgba(c):
    """A canvas colour -> (r, g, b, a): rgb 0..255 sRGB, alpha 0..1. Takes '#rgb', '#rrggbb', 'rgb(r, g, b)',
    'rgba(r, g, b, a)' or a tuple (r, g, b[, a])."""
    if isinstance(c, (tuple, list)):
        return (float(c[0]), float(c[1]), float(c[2]), float(c[3]) if len(c) > 3 else 1.0)
    c = c.strip()
    if c.startswith('#'):
        h = c[1:]
        if len(h) == 3:
            h = ''.join(x * 2 for x in h)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
    m = re.match(r'rgba?\(([^)]*)\)', c)
    if m is None:
        raise ValueError(f'[voice_machines] canvas colour {c!r}: use #rrggbb, rgb(...) or rgba(...)')
    v = [float(x) for x in m.group(1).split(',')]
    return (v[0], v[1], v[2], v[3] if len(v) > 3 else 1.0)


class Gradient:
    """createLinearGradient(0, y0, 0, y1) with its colour stops: a vertical gradient (the only kind the drawings
    make), colours interpolated in sRGB as canvas does."""

    def __init__(self, y0, y1, stops):
        self.y0, self.y1 = float(y0), float(y1)
        self.stops = [(float(o), np.array(css_rgba(c), np.float64)) for o, c in stops]

    def rows(self, ys):
        """The RGBA (0..255, alpha 0..1) at canvas y values ys (1-D) -> (n, 4)."""
        t = np.clip((np.asarray(ys, np.float64) - self.y0) / max(self.y1 - self.y0, 1e-9), 0.0, 1.0)
        offs = np.array([o for o, _ in self.stops])
        cols = np.stack([c for _, c in self.stops])
        return np.stack([np.interp(t, offs, cols[:, k]) for k in range(4)], axis=1)


class Canvas2D:
    """makeCanvas: the canvas-2D operations the machines' drawings use, on a supersampled straight-alpha float RGBA
    buffer (w x h canvas pixels, ss x ss samples each): fills (solid / vertical gradient) of rects, polygons and
    ellipses, strokes of polylines and arcs, text at the alphabetic baseline with the canvas's alignments, blur
    (ctx.filter) and drop shadows, all composited source-over in sRGB as canvas does. image() resolves it to an RGBA
    Pillow image (a box filter of the premultiplied colour)."""

    def __init__(self, w, h, ss=CANVAS_SS):
        self.w, self.h, self.ss = int(w), int(h), int(ss)
        self.rgb = np.zeros((self.h * self.ss, self.w * self.ss, 3), np.float32)
        self.a = np.zeros((self.h * self.ss, self.w * self.ss), np.float32)

    @property
    def width(self):
        return self.w

    @property
    def height(self):
        return self.h

    # -- masks: an L image over a bbox (canvas px), drawn at ss
    def _mask(self, bbox, fn, blur=0.0):
        ss = self.ss
        pad = int(math.ceil(3 * blur)) + 2
        x0 = max(0, int(math.floor(bbox[0])) - pad)
        y0 = max(0, int(math.floor(bbox[1])) - pad)
        x1 = min(self.w, int(math.ceil(bbox[2])) + pad)
        y1 = min(self.h, int(math.ceil(bbox[3])) + pad)
        if x1 <= x0 or y1 <= y0:
            return None
        from PIL import Image, ImageDraw, ImageFilter
        img = Image.new('L', ((x1 - x0) * ss, (y1 - y0) * ss), 0)
        fn(ImageDraw.Draw(img), lambda x, y: ((x - x0) * ss, (y - y0) * ss))
        if blur > 0:
            img = img.filter(ImageFilter.GaussianBlur(blur * ss))
        return x0 * ss, y0 * ss, np.asarray(img, np.float32) / 255.0

    def _composite(self, m, paint, alpha=1.0, dx=0.0, dy=0.0):
        if m is None:
            return
        X, Y, mask = m
        X, Y = X + int(round(dx * self.ss)), Y + int(round(dy * self.ss))
        hh, ww = mask.shape
        xa, ya, xb, yb = max(0, X), max(0, Y), min(self.w * self.ss, X + ww), min(self.h * self.ss, Y + hh)
        if xb <= xa or yb <= ya:
            return
        mask = mask[ya - Y:yb - Y, xa - X:xb - X]
        rows = np.nonzero(mask.any(axis=1))[0]          # only the rows the shape touches
        if not len(rows):
            return
        r0, r1 = int(rows[0]), int(rows[-1]) + 1
        mask, ya, yb = mask[r0:r1], ya + r0, ya + r1
        if isinstance(paint, Gradient):
            ys = (np.arange(ya, yb, dtype=np.float64) + 0.5) / self.ss
            g = paint.rows(ys)
            col = g[:, None, :3].astype(np.float32)
            sa = mask * (g[:, None, 3].astype(np.float32) * alpha)
        else:
            c = css_rgba(paint)
            col = np.array(c[:3], np.float32)
            sa = mask * np.float32(c[3] * alpha)
        da = self.a[ya:yb, xa:xb]
        drgb = self.rgb[ya:yb, xa:xb]
        if da.min() >= 1.0:                               # onto opaque paint (all but the first fill): a lerp
            drgb += (col - drgb) * sa[..., None]
            return
        oa = sa + da * (1.0 - sa)
        safe = np.maximum(oa, 1e-6)[..., None]
        self.rgb[ya:yb, xa:xb] = (col * sa[..., None] + drgb * (da * (1.0 - sa))[..., None]) / safe
        self.a[ya:yb, xa:xb] = oa

    # -- fills
    def fill_rect(self, x, y, w, h, paint, alpha=1.0):
        self._composite(self._mask((x, y, x + w, y + h), lambda d, P: d.rectangle(
            [*P(x, y), P(x + w, y + h)[0] - 1, P(x + w, y + h)[1] - 1], fill=255)), paint, alpha)

    def fill_poly(self, pts, paint, alpha=1.0, blur=0.0, shadow=None):
        """Fill a polygon; shadow = (colour, shadowBlur, dx, dy) draws the canvas's drop shadow under it first (a
        Gaussian of sigma shadowBlur / 2, offset)."""
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        bbox = (min(xs), min(ys), max(xs), max(ys))

        def shape(d, P):
            d.polygon([P(*p) for p in pts], fill=255)
        if shadow:
            colour, sblur, dx, dy = shadow
            self._composite(self._mask(bbox, shape, blur=sblur / 2.0), colour, 1.0, dx, dy)
        self._composite(self._mask(bbox, shape, blur=blur), paint, alpha)

    def fill_ellipse(self, cx, cy, rx, ry, paint, alpha=1.0, blur=0.0):
        """Fill an ellipse (ctx.ellipse / arc + fill). Pillow's box is inclusive of its last sample, so the far
        corner steps one sample in (as fill_rect), or small dots come out a sample too wide."""
        def shape(d, P):
            x0, y0 = P(cx - rx, cy - ry)
            x1, y1 = P(cx + rx, cy + ry)
            d.ellipse([x0, y0, max(x0, x1 - 1), max(y0, y1 - 1)], fill=255)
        self._composite(self._mask((cx - rx, cy - ry, cx + rx, cy + ry), shape, blur=blur), paint, alpha)

    # -- strokes
    def stroke_poly(self, pts, colour, width, closed=False, alpha=1.0):
        p = list(pts) + ([pts[0]] if closed else [])
        xs, ys = [q[0] for q in p], [q[1] for q in p]
        w = max(1, int(round(width * self.ss)))
        self._composite(self._mask((min(xs) - width, min(ys) - width, max(xs) + width, max(ys) + width),
                                   lambda d, P: d.line([P(*q) for q in p], fill=255, width=w,
                                                       joint='curve' if len(p) > 2 else None)), colour, alpha)

    def stroke_arc(self, cx, cy, r, a0, a1, colour, width):
        ro = r + width / 2.0
        w = max(1, int(round(width * self.ss)))
        self._composite(self._mask((cx - ro, cy - ro, cx + ro, cy + ro), lambda d, P: d.arc(
            [*P(cx - ro, cy - ro), *P(cx + ro, cy + ro)], math.degrees(a0), math.degrees(a1), fill=255, width=w)),
            colour)

    # -- text
    def text(self, s, x, y, fam, px, colour, align='left', bold=False, italic=False, shadow=None):
        """fillText at the alphabetic baseline; shadow = (colour, dx, dy) (shadowBlur 0)."""
        if not s:
            return
        f = font(fam, px * self.ss, bold, italic)
        f1 = font(fam, px, bold, italic)
        wpx = f1.getlength(s)
        anchor = {'left': 'ls', 'center': 'ms', 'right': 'rs'}[align]
        bbox = (x - wpx - px, y - px * 1.5, x + wpx + px, y + px * 0.6)
        # Skia's fake bold for a family without a bold face: the outline grows by px x (1/24 at 9 px .. 1/32 at
        # 36 px) in all, half on each side
        fake = bold and font_file(fam, True, italic) == font_file(fam, False, italic)
        k = 1 / 24 + (1 / 32 - 1 / 24) * min(max((px - 9) / 27, 0.0), 1.0)
        sw = int(round(px * k * self.ss / 2)) if fake else 0
        m = self._mask(bbox, lambda d, P: d.text(P(x, y), s, font=f, fill=255, anchor=anchor, stroke_width=sw,
                                                 stroke_fill=255))
        if shadow:
            self._composite(m, shadow[0], 1.0, shadow[1], shadow[2])
        self._composite(m, colour)

    def measure(self, s, fam, px, bold=False, italic=False):
        return font(fam, px, bold, italic).getlength(s)

    def image(self, w=None, h=None):
        """The canvas at 1x (a box downsample of the premultiplied colour) as an RGBA Pillow image w x h (a larger
        size pads with transparent black, as a canvas bigger than the drawing)."""
        from PIL import Image
        ss = self.ss
        pm = self.rgb * self.a[..., None]
        H1, W1 = self.h, self.w
        pm = pm.reshape(H1, ss, W1, ss, 3).mean(axis=(1, 3))
        a = self.a.reshape(H1, ss, W1, ss).mean(axis=(1, 3))
        rgb = np.where(a[..., None] > 1e-6, pm / np.maximum(a, 1e-6)[..., None], 0.0)
        out = np.dstack([np.clip(rgb, 0, 255), np.clip(a * 255.0, 0, 255)]).round().astype(np.uint8)
        img = Image.fromarray(out, 'RGBA')
        if (w or W1, h or H1) != (W1, H1):
            canvas = Image.new('RGBA', (w or W1, h or H1), (0, 0, 0, 0))
            canvas.paste(img, (0, 0))
            img = canvas
        return img


def make_canvas(w, h, ss=CANVAS_SS):
    """makeCanvas: a w x h canvas (transparent black) -> Canvas2D."""
    return Canvas2D(w, h, ss)


def quad(p0, c, p1, n=12):
    """Points along a quadratic Bezier (quadraticCurveTo), p0 excluded."""
    return [((1 - s) ** 2 * p0[0] + 2 * (1 - s) * s * c[0] + s * s * p1[0],
             (1 - s) ** 2 * p0[1] + 2 * (1 - s) * s * c[1] + s * s * p1[1]) for s in (k / n for k in range(1, n + 1))]


def rr(x, y, w, h, r, n=8):
    """rr: the rounded-rectangle path (arcTo corners: circular arcs of radius min(r, w / 2, h / 2)) at (x, y) w x h
    in canvas pixels -> its outline [(x, y)], clockwise on the canvas, for Canvas2D.fill_poly or stroke_poly(...,
    closed=True) (the JS traced it on the context; ctx.fill() / ctx.stroke() followed)."""
    r = min(r, w / 2, h / 2)
    pts = []
    for cx, cy, a0 in ((x + w - r, y + r, -90), (x + w - r, y + h - r, 0), (x + r, y + h - r, 90),
                       (x + r, y + r, 180)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def speckle(g, w, h, n, seed, colors, r_max=1.5, alpha=0.08):
    """speckle: n dots of the colours at seeded places on a Canvas2D (rng(seed): the JS's sequence, drawn in its
    order: alpha, colour, x, y, radius), radius 0.3 .. 0.3 + r_max px, each at alpha x (0.3 .. 1.3); dust, flecks,
    grain on a printed decal. A per-dot alpha outside 0..1 keeps the one before (canvas ignores such a globalAlpha)."""
    r = rng(seed)
    ga = 1.0
    for _ in range(int(n)):
        a = alpha * (0.3 + r())
        if 0.0 <= a <= 1.0:
            ga = a
        col = colors[int(math.floor(r() * len(colors)))]
        x, y = r() * w, r() * h
        rad = 0.3 + r() * r_max
        g.fill_ellipse(x, y, rad, rad, col, alpha=ga)
    return g


# --------------------------------------------------------------------------------- canvas textures and mips ---
def build_mips(data, w=None, h=None, alpha_weighted=False):
    """buildMips: the CPU mip chain of an RGBA uint8 image ((h, w, 4), top row first; or flat with w, h) ->
    [{'data', 'width', 'height'}], level 0 first, down to 1 x 1: each texel the rounded mean of its 2 x 2 parents
    (an odd edge repeats its last row / column). alpha_weighted: colour averaged by alpha, so transparent texels
    never darken a decal's edge (all four transparent: the plain mean); alpha the plain mean. Bit-exact with the JS.
    EEVEE makes its own mips for every Linear image texture, so the screens need none of this; canvas_texture bleeds
    a decal's colour from the alpha-weighted chain (bleed_alpha) so those mips match."""
    src = np.asarray(data, np.uint8)
    if src.ndim == 1:
        src = src.reshape(int(h), int(w), 4)
    sh, sw = src.shape[:2]
    levels = [{'data': src, 'width': sw, 'height': sh}]
    while sw > 1 or sh > 1:
        dw, dh = max(1, sw >> 1), max(1, sh >> 1)
        r0, r1 = np.minimum(sh - 1, np.arange(dh) * 2), np.minimum(sh - 1, np.arange(dh) * 2 + 1)
        c0, c1 = np.minimum(sw - 1, np.arange(dw) * 2), np.minimum(sw - 1, np.arange(dw) * 2 + 1)
        s = src.astype(np.int64)
        A, B, C, D = s[r0][:, c0], s[r0][:, c1], s[r1][:, c0], s[r1][:, c1]
        plain = (A + B + C + D + 2) >> 2
        if alpha_weighted:
            wa, wb, wc, wd = A[..., 3:], B[..., 3:], C[..., 3:], D[..., 3:]
            ws = wa + wb + wc + wd
            num = (A[..., :3] * wa + B[..., :3] * wb + C[..., :3] * wc + D[..., :3] * wd).astype(np.float64)
            weighted = np.floor(num / np.maximum(ws, 1) + 0.5).astype(np.int64)          # JS Math.round
            dst = np.empty_like(plain)
            dst[..., :3] = np.where(ws > 0, weighted, plain[..., :3])
            dst[..., 3] = (ws[..., 0] + 2) >> 2
        else:
            dst = plain
        src = dst.astype(np.uint8)
        levels.append({'data': src, 'width': dw, 'height': dh})
        sw, sh = dw, dh
    return levels


def bleed_alpha(rgba):
    """An RGBA uint8 image (h, w, 4) with the colour of its fully transparent texels filled from the alpha-weighted
    mip chain, coarse to fine (texels with any alpha keep theirs): a straight-alpha decal whose mips, averaged
    by the GPU, never pull its edge toward the black of the empty texels."""
    a = np.asarray(rgba, np.uint8)
    levels = build_mips(a, alpha_weighted=True)
    fill = levels[-1]['data'][..., :3]
    for lv in reversed(levels[:-1]):
        d = lv['data']
        hh, ww = d.shape[:2]
        up = fill[np.minimum(np.arange(hh) // 2, fill.shape[0] - 1)][:, np.minimum(np.arange(ww) // 2,
                                                                                  fill.shape[1] - 1)]
        fill = np.where(d[..., 3:4] > 0, d[..., :3], up)
    out = a.copy()
    out[..., :3] = fill
    return out


def _rgba_array(cv):
    """A Canvas2D, a Pillow image or an (h, w, 4) uint8 array -> (h, w, 4) uint8, top row first."""
    if isinstance(cv, Canvas2D):
        cv = cv.image()
    if isinstance(cv, np.ndarray):
        return cv.astype(np.uint8)
    return np.asarray(cv.convert('RGBA'), np.uint8)


class CanvasTexture:
    """canvasTexture: a canvas (a Canvas2D, a Pillow image or an RGBA uint8 array, top row first) as a packed Blender
    image, its rows flipped so the canvas top lands at v = 1 (Blender images are stored bottom-up, as three's
    DataTexture was uploaded). The JS options: srgb (else non-colour data), mips (False: 'Cubic', the smooth EEVEE
    filter without mips), repeat ('REPEAT', else 'EXTEND'), nearest ('Closest'), alpha_weighted (bleed_alpha: the
    decal's colour carried into its transparent texels, as the JS's alpha-weighted CPU mips kept its edge clean).
    .image, .interpolation, .extension; node(tree) makes an Image Texture node with those settings; refresh()
    re-reads the canvas (refreshCanvasTexture)."""

    def __init__(self, cv, srgb=True, mips=True, repeat=False, nearest=False, alpha_weighted=True,
                 name='eido_canvas'):
        _require_bpy()
        self.cv, self.srgb, self.mips, self.repeat = cv, srgb, mips, repeat
        self.nearest, self.alpha_weighted, self.name = nearest, alpha_weighted, name
        self.interpolation = 'Closest' if nearest else ('Linear' if mips else 'Cubic')
        self.extension = 'REPEAT' if repeat else 'EXTEND'
        self.image = None
        self.refresh()

    def refresh(self, cv=None):
        """Re-read the canvas (or a new one) into the image (refreshCanvasTexture)."""
        if cv is not None:
            self.cv = cv
        a = _rgba_array(self.cv)
        hh, ww = a.shape[:2]
        if self.alpha_weighted and self.mips and not self.nearest and (a[..., 3] < 255).any():
            a = bleed_alpha(a)
        img = self.image
        if img is None or tuple(img.size) != (ww, hh):
            if img is not None:
                bpy.data.images.remove(img)
            img = bpy.data.images.new(self.name, ww, hh, alpha=True, float_buffer=False)
            img.colorspace_settings.name = 'sRGB' if self.srgb else 'Non-Color'
            img.alpha_mode = 'STRAIGHT'
            self.image = img
        img.pixels.foreach_set((a[::-1].astype(np.float32) / 255.0).ravel())
        img.update()
        img.pack()
        return img

    def node(self, tree):
        """An Image Texture node in `tree` sampling this canvas with its filter and wrap."""
        n = tree.nodes.new('ShaderNodeTexImage')
        n.image = self.image
        n.interpolation = self.interpolation
        n.extension = self.extension
        return n

    def __repr__(self):
        return f'<CanvasTexture {self.name} {tuple(self.image.size) if self.image else None} {self.interpolation}>'


def canvas_texture(cv, srgb=True, mips=True, repeat=False, nearest=False, alpha_weighted=True, name='eido_canvas'):
    """canvasTexture(cv, o) -> CanvasTexture (see the class)."""
    return CanvasTexture(cv, srgb, mips, repeat, nearest, alpha_weighted, name)


def refresh_canvas_texture(tex, cv=None):
    """refreshCanvasTexture(tex): re-read its canvas into the image."""
    return tex.refresh(cv)


def flip_uv(geo, layer=None):
    """flipUV: v -> 1 - v on a mesh's (or BMesh's) UV map (default the active one): glTF UVs run v-down, three's
    v-up. Blender's glTF importer already flips them, so the GLB machines never call it; it is for a mesh made with
    v-down UVs."""
    if hasattr(geo, 'loops') and hasattr(geo.loops, 'layers'):              # a BMesh
        uv = geo.loops.layers.uv.get(layer) if layer else geo.loops.layers.uv.active
        if uv is None:
            return geo
        for f in geo.faces:
            for lp in f.loops:
                lp[uv].uv = (lp[uv].uv[0], 1.0 - lp[uv].uv[1])
        return geo
    uvl = geo.uv_layers.get(layer) if layer else geo.uv_layers.active
    if uvl is None:
        return geo
    co = np.empty(len(uvl.data) * 2, np.float32)
    uvl.data.foreach_get('uv', co)
    co[1::2] = 1.0 - co[1::2]
    uvl.data.foreach_set('uv', co)
    geo.update()
    return geo


def bump_normal(nb: Nodes, height):
    """bumpNormal(h): the normal bent by a height in metres (a socket or a number), as a Bump node (strength 1,
    distance 1: the height is the displacement): the shader's surface-gradient bump."""
    bump = nb.node('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 1.0
    bump.inputs['Distance'].default_value = 1.0
    nb.link(height, bump.inputs['Height'])
    return bump.outputs['Normal']


def curvature(nb: Nodes, name=CURVATURE):
    """curvature(): the surface's curvature in 1/m (+ convex, - concave) as a socket, read from the face-corner
    attribute write_curvature(obj) stored (shader nodes have no screen-space derivatives of the normal)."""
    return nb.node('ShaderNodeAttribute', attribute_type='GEOMETRY', attribute_name=name).outputs['Fac']


_curvature = curvature                # plastic_material's own `curvature` argument (the attribute's name) hides it


# ---------------------------------------------------------------------------------------- geometry builders ---
# The kit's builders on BMesh: rbox, roundedRectShape (+ shape_geometry, the extrusion it fed), bake, smooth,
# merge, planarUV, planarUVFacing, rrPoints, loftRings, keycap, roundedPolyline (+ wire, the tube it fed), mesh. No
# machine calls them since the machines became GLBs (models/voice_machines_src/ builds those); they are for new
# props in the same style, worn with plastic_material. Blender axes: three's y (up) is z here and its z (toward the
# viewer) is -y, so three's front plane 'xy' is 'xz' and things face -Y.
_AXIS = {'x': 0, 'y': 1, 'z': 2}


def _bmesh():
    _require_bpy()
    import bmesh
    return bmesh


def _axes(axes):
    """'xz' / 'x-y' / ('x', '-y') -> two getters co -> float (Blender axes, a leading '-' negates)."""
    parts = re.findall(r'[+-]?[xyz]', axes) if isinstance(axes, str) else list(axes)
    if len(parts) != 2:
        raise ValueError(f'[voice_machines] axes {axes!r}: two of x, y, z (each may be negated: "x-y")')

    def getter(a):
        a = a.strip()
        sgn, i = (-1.0 if a.startswith('-') else 1.0), _AXIS[a.lstrip('+-')]
        return lambda co: sgn * co[i]
    return getter(parts[0]), getter(parts[1])


def _box_uv(bm, size):
    """Each face mapped 0..1 across its side of the box `size` (x, y, z) by its dominant normal axis, as three's
    box UVs: front (-Y) u = x, v = z; back mirrored; sides along y; top u = x, v = y; bottom v = -y."""
    sx, sy, sz = (max(float(s), 1e-9) for s in size)
    uv = bm.loops.layers.uv.active or bm.loops.layers.uv.new('UVMap')
    bm.normal_update()
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for lp in f.loops:
            x, y, z = lp.vert.co
            if ax == 1:
                u = (x / sx + 0.5) if n[1] < 0 else (0.5 - x / sx)
                v = z / sz + 0.5
            elif ax == 0:
                u = (y / sy + 0.5) if n[0] > 0 else (0.5 - y / sy)
                v = z / sz + 0.5
            else:
                u = x / sx + 0.5
                v = (y / sy + 0.5) if n[2] > 0 else (0.5 - y / sy)
            lp[uv].uv = (u, v)


def rbox(w, h, d, r, seg=3):
    """rbox (RoundedBoxGeometry): a w (x) x h (z, up) x d (y) box centred at the origin, every edge and corner rounded
    at radius r (clamped below half of each side) in seg segments; smooth, with three's per-side box UVs -> BMesh."""
    bmesh = _bmesh()
    from mathutils import Vector
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * w, v.co.y * d, v.co.z * h))
    r = min(r, w / 2 - 1e-5, h / 2 - 1e-5, d / 2 - 1e-5)
    if r > 1e-7 and seg > 0:
        bmesh.ops.bevel(bm, geom=list(bm.verts) + list(bm.edges), offset=r, offset_type='OFFSET',
                        segments=int(seg), profile=0.5, affect='EDGES', clamp_overlap=False)
    for f in bm.faces:
        f.smooth = True
    _box_uv(bm, (w, d, h))
    return bm


def rounded_rect_shape(w, h, r, cx=0.0, cy=0.0, hole=False, n=12):
    """roundedRectShape: a w x h rectangle centred at (cx, cy) with quadratic-curve corners (control point at the
    corner, radius min(r, w / 2, h / 2)) -> its outline [(x, y)], counter-clockwise from (x0 + r, y0), each corner n
    segments (three's curveSegments, 12). hole=True was the JS's Path (for a Shape's holes) instead of a Shape: the
    same outline here, since shape_geometry takes holes in either direction. Make geometry of it with
    shape_geometry."""
    x0, y0 = cx - w / 2, cy - h / 2
    r = min(r, w / 2, h / 2)
    pts = [(x0 + r, y0), (x0 + w - r, y0)]
    pts += quad((x0 + w - r, y0), (x0 + w, y0), (x0 + w, y0 + r), n)
    pts.append((x0 + w, y0 + h - r))
    pts += quad((x0 + w, y0 + h - r), (x0 + w, y0 + h), (x0 + w - r, y0 + h), n)
    pts.append((x0 + r, y0 + h))
    pts += quad((x0 + r, y0 + h), (x0, y0 + h), (x0, y0 + h - r), n)
    pts.append((x0, y0 + r))
    pts += quad((x0, y0 + r), (x0, y0), (x0 + r, y0), n)
    return _ring(pts)


def _ring(pts, eps=1e-9):
    """A closed outline without consecutive duplicates or a repeated first point."""
    out = []
    for p in pts:
        p = (float(p[0]), float(p[1]))
        if not out or abs(p[0] - out[-1][0]) > eps or abs(p[1] - out[-1][1]) > eps:
            out.append(p)
    while len(out) > 1 and abs(out[0][0] - out[-1][0]) <= eps and abs(out[0][1] - out[-1][1]) <= eps:
        out.pop()
    return out


def _cap_triangles(loops, flat):
    """The triangles filling the first loop minus the others, as index triples into `flat`, counter-clockwise:
    tessellate_polygon's scanline fill, then its edges rotated (beautify_fill), since features on a shared scanline
    (a row of equal slots) leave zero-area slivers in a scanline fill; any sliver left is dropped."""
    bmesh = _bmesh()
    from mathutils.geometry import tessellate_polygon
    tris = tessellate_polygon([[(p[0], p[1], 0.0) for p in lp] for lp in loops])
    tmp = bmesh.new()
    vs = [tmp.verts.new((p[0], p[1], 0.0)) for p in flat]
    tmp.verts.index_update()

    def cross(i, j, k):
        a, b, c = flat[i], flat[j], flat[k]
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    faces = []
    for i, j, k in tris:
        if cross(i, j, k) < 0:
            j, k = k, j
        try:
            faces.append(tmp.faces.new((vs[i], vs[j], vs[k])))
        except ValueError:                                  # the same triangle twice
            pass
    inner = [e for e in tmp.edges if len(e.link_faces) == 2]
    if faces and inner:
        bmesh.ops.beautify_fill(tmp, faces=faces, edges=inner)
    out = []
    for f in tmp.faces:
        i, j, k = (v.index for v in f.verts)
        c = cross(i, j, k)
        if abs(c) < 1e-16:                                  # a sliver (twice its area, m^2)
            continue
        out.append((i, j, k) if c > 0 else (i, k, j))
    tmp.free()
    return out


def shape_geometry(outline, holes=(), depth=0.0):
    """The geometry of a 2-D outline and its holes ([(x, y)] each, e.g. rounded_rect_shape): three's ShapeGeometry
    (depth 0, one sheet facing -Y) or ExtrudeGeometry without bevel (depth > 0: caps and walls, closed). The shape
    lies on the front plane (its x along X, its y up Z), extruded toward the viewer from y = 0 to y = -depth. UVs in
    metres as three's WorldUVGenerator: caps (x, y), walls (along the outline, across the depth). Faceted, as
    ExtrudeGeometry ships (smooth() rounds it) -> BMesh."""
    bmesh = _bmesh()
    loops = [_ring(outline)] + [_ring(hh) for hh in holes]
    flat = [p for lp in loops for p in lp]
    tris = _cap_triangles(loops, flat)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new('UVMap')
    yf = -float(depth) if depth > 0 else 0.0
    front = [bm.verts.new((p[0], yf, p[1])) for p in flat]
    back = [bm.verts.new((p[0], 0.0, p[1])) for p in flat] if depth > 0 else None
    for i, j, k in tris:                                   # counter-clockwise seen from the front: faces -Y
        f = bm.faces.new((front[i], front[j], front[k]))
        for lp, q in zip(f.loops, (i, j, k)):
            lp[uv].uv = flat[q]
        if back is not None:
            f = bm.faces.new((back[i], back[k], back[j]))
            for lp, q in zip(f.loops, (i, k, j)):
                lp[uv].uv = flat[q]
    if back is not None:
        off = 0
        for lp_pts in loops:
            n = len(lp_pts)
            s = 0.0
            for q in range(n):
                i0, i1 = off + q, off + (q + 1) % n
                seg = math.dist(flat[i0], flat[i1])
                f = bm.faces.new((front[i0], front[i1], back[i1], back[i0]))
                for lp, (u, v) in zip(f.loops, ((s, 0.0), (s + seg, 0.0), (s + seg, depth), (s, depth))):
                    lp[uv].uv = (u, v)
                s += seg
            off += n
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.normal_update()
    return bm


def bake(geo, pos=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0), scl=(1.0, 1.0, 1.0)):
    """bake: a copy of the geometry with a transform applied (location, a Blender XYZ Euler in radians, scale),
    keeping positions, normals and its first UV map (the other layers go; a UV map is added if it had none, so any
    two merge) -> BMesh."""
    bmesh = _bmesh()
    from mathutils import Euler, Matrix, Vector
    g = geo.copy()
    uvs = list(g.loops.layers.uv)
    for extra in uvs[1:]:
        g.loops.layers.uv.remove(extra)
    for coll in (g.loops.layers.color, g.verts.layers.float, g.verts.layers.int, g.faces.layers.float,
                 g.faces.layers.int):
        for layer in list(coll):
            coll.remove(layer)
    if not uvs:
        g.loops.layers.uv.new('UVMap')
    bmesh.ops.transform(g, matrix=Matrix.LocRotScale(Vector(pos), Euler(rot, 'XYZ'), Vector(scl)), verts=g.verts)
    g.normal_update()
    return g


def smooth(geo, dist=1e-6):
    """smooth: weld coincident vertices (within dist, 1 um) and make every face smooth (ExtrudeGeometry ships faceted
    normals; mesh() gives them three's area-weighted vertex normals); drops the UVs, as the JS did -> BMesh."""
    bmesh = _bmesh()
    g = geo.copy()
    bmesh.ops.remove_doubles(g, verts=list(g.verts), dist=dist)
    for layer in list(g.loops.layers.uv):
        g.loops.layers.uv.remove(layer)
    for f in g.faces:
        f.smooth = True
    g.normal_update()
    return g


def merge(geos):
    """merge (mergeGeometries): one geometry of many, faces with their UVs (the first map of each), smooth flags and
    material indices -> BMesh."""
    bmesh = _bmesh()
    out = bmesh.new()
    uv_out = out.loops.layers.uv.new('UVMap')
    for g in geos:
        uv_in = g.loops.layers.uv.active
        vmap = {v: out.verts.new(v.co) for v in g.verts}
        for f in g.faces:
            nf = out.faces.new([vmap[v] for v in f.verts])
            nf.smooth, nf.material_index = f.smooth, f.material_index
            if uv_in is not None:
                for a, b in zip(nf.loops, f.loops):
                    a[uv_out].uv = b[uv_in].uv
    out.normal_update()
    return out


def planar_uv(geo, x0, y0, x1, y1, axes='xz'):
    """planarUV: UVs from a rectangle (x0, y0)-(x1, y1) on two of the geometry's axes, u = (a - x0) / (x1 - x0),
    v = (b - y0) / (y1 - y0), for printed cards and keys. axes in Blender's letters, each may be negated: three's
    'xy' (the front, y up) is 'xz' here, its 'xz' (the top) is 'x-y', its 'zy' is '-yz'."""
    gu, gv = _axes(axes)
    uv = geo.loops.layers.uv.active or geo.loops.layers.uv.new('UVMap')
    for f in geo.faces:
        for lp in f.loops:
            co = lp.vert.co
            lp[uv].uv = ((gu(co) - x0) / (x1 - x0), (gv(co) - y0) / (y1 - y0))
    return geo


def planar_uv_facing(geo, x0, y0, x1, y1, axes='xz', direction=(0.0, -1.0, 0.0), min_dot=0.35):
    """planarUVFacing: planar_uv on the faces turned toward `direction` (default the front, -Y: the mean of their
    corners' normals . direction >= min_dot); every other face maps to (-0.25, -0.25), outside the 0..1 a decal
    prints on, so backs and bottoms stay unprinted (plastic_material's decal clips there)."""
    from mathutils import Vector
    planar_uv(geo, x0, y0, x1, y1, axes)
    geo.normal_update()
    uv = geo.loops.layers.uv.active
    d = Vector(direction)
    for f in geo.faces:
        ns = [(lp.vert.normal if f.smooth else f.normal) for lp in f.loops]
        if sum(n.dot(d) for n in ns) / len(ns) < min_dot:
            for lp in f.loops:
                lp[uv].uv = (-0.25, -0.25)
    return geo


def rr_points(w, h, r, n=6, cx=0.0, cy=0.0):
    """rrPoints: a rounded rectangle's outline, counter-clockwise from the top-right corner's arc, n + 1 points per
    corner (circular arcs, r clamped below half of each side), centred at (cx, cy) -> [(x, y)] (rings for
    loft_rings: map them into 3-D yourself)."""
    r = min(r, w / 2 - 1e-6, h / 2 - 1e-6)
    pts = []
    for x, y, a0 in ((w / 2 - r, h / 2 - r, 0.0), (-w / 2 + r, h / 2 - r, 0.5), (-w / 2 + r, -h / 2 + r, 1.0),
                     (w / 2 - r, -h / 2 + r, 1.5)):
        for i in range(n + 1):
            a = (a0 + 0.5 * i / n) * math.pi
            pts.append((cx + x + math.cos(a) * r, cy + y + math.sin(a) * r))
    return pts


def loft_rings(rings, flip=False):
    """loftRings: skin a surface through closed rings of equal point count ([(x, y, z)] each, Blender axes), smooth,
    open at both ends; u runs around (i / n, the seam's last column at u = 1), v across (j / (rings - 1)). A ring
    collapsed to one point (a pole) closes that end in triangles -> BMesh."""
    bmesh = _bmesh()
    n, R = len(rings[0]), len(rings)
    if any(len(rg) != n for rg in rings):
        raise ValueError('[voice_machines] loft_rings: every ring needs the same point count')
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new('UVMap')
    V = []
    for rg in rings:
        p = np.asarray(rg, np.float64)
        if np.ptp(p, axis=0).max() < 1e-9:                 # a pole: one vertex for the whole ring
            v = bm.verts.new(tuple(p[0]))
            V.append([v] * n)
        else:
            V.append([bm.verts.new(tuple(q)) for q in p])
    for j in range(R - 1):
        for i in range(n):
            i1 = (i + 1) % n
            corners = [(j, i, i / n), (j, i1, (i + 1) / n), (j + 1, i1, (i + 1) / n), (j + 1, i, i / n)]
            if flip:
                corners = [corners[0], corners[3], corners[2], corners[1]]
            used, vs = [], []
            for c in corners:
                v = V[c[0]][c[1]]
                if v not in vs:
                    vs.append(v)
                    used.append(c)
            if len(vs) < 3:
                continue
            f = bm.faces.new(vs)
            f.smooth = True
            for lp, (a, _b, u) in zip(f.loops, used):
                lp[uv].uv = (u, a / (R - 1))
    bm.normal_update()
    return bm


def keycap(w_b, d_b, w_t, d_t, h, r=0.0012):
    """keycap: a rounded box (rbox, 2 segments) whose top is narrower than its base, the sculpted-key taper: base
    w_b (x) x d_b (y), top w_t x d_t, height h (z), centred at the origin -> BMesh."""
    bm = rbox(w_b, h, d_b, r, 2)
    for v in bm.verts:
        t = (v.co.z + h / 2) / h
        v.co.x *= 1 + (w_t / w_b - 1) * t
        v.co.y *= 1 + (d_t / d_b - 1) * t
    bm.normal_update()
    return bm


def _unit(v):
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v                       # three's normalize(): a zero vector stays zero


class RoundedPolyline:
    """roundedPolyline (a three CurvePath): the polyline through pts with each inner corner rounded by a quadratic
    Bezier (control point the corner, its ends min(radius, 0.45 x the leg) along each leg). segments: [('line', p0,
    p1) | ('quad', p0, corner, p1)] in order; points(divisions) samples it as three's getPoints (a line 1 division,
    a fillet `divisions`, consecutive duplicates dropped); length as three's getLength (200 divisions a piece)."""

    def __init__(self, pts, radius):
        P = [np.asarray(q, np.float64) for q in pts]
        self.segments = []
        cur = P[0].copy()
        for i in range(1, len(P) - 1):
            a, b, c = P[i - 1], P[i], P[i + 1]
            ra, rc = min(radius, float(np.linalg.norm(a - b)) * 0.45), min(radius, float(np.linalg.norm(b - c)) * 0.45)
            p0, p1 = b + _unit(a - b) * ra, b + _unit(c - b) * rc
            if float(np.linalg.norm(cur - p0)) > 1e-6:
                self.segments.append(('line', cur.copy(), p0))
            self.segments.append(('quad', p0, b.copy(), p1))
            cur = p1
        self.segments.append(('line', cur.copy(), P[-1].copy()))

    @staticmethod
    def _point(seg, t):
        if seg[0] == 'line':
            p0, p1 = seg[1], seg[2]
            return p1.copy() if t == 1 else (p1 - p0) * t + p0
        p0, c, p1 = seg[1], seg[2], seg[3]
        k = 1 - t
        return k * k * p0 + 2 * k * t * c + t * t * p1

    def points(self, divisions=12):
        out = []
        for seg in self.segments:
            res = 1 if seg[0] == 'line' else divisions
            for d in range(res + 1):
                p = self._point(seg, d / res)
                if out and np.array_equal(out[-1], p):
                    continue
                out.append(p)
        return [tuple(float(x) for x in p) for p in out]

    @property
    def length(self):
        tot = 0.0
        for seg in self.segments:
            last = self._point(seg, 0.0)
            for d in range(1, 201):
                p = self._point(seg, d / 200)
                tot += float(np.linalg.norm(p - last))
                last = p
        return tot

    def __repr__(self):
        return f'<RoundedPolyline {len(self.segments)} pieces, {self.length:.3f} m>'


def rounded_polyline(pts, radius):
    """roundedPolyline(pts, radius) -> RoundedPolyline (bent wire and tubing: wire() makes it a tube)."""
    return RoundedPolyline(pts, radius)


def wire(path, radius, name='wire', material=None, collection=None, divisions=12, sides=8):
    """A bent wire or tube along path (a RoundedPolyline, sampled at `divisions` per fillet, or [(x, y, z)] points):
    a curve object with a round bevel of `radius` (m), about `sides` around, filled caps, smooth (the JS swept
    roundedPolyline with TubeGeometry)."""
    _require_bpy()
    pts = path.points(divisions) if isinstance(path, RoundedPolyline) else [tuple(map(float, p)) for p in path]
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_mode = 'ROUND'
    cu.bevel_depth = float(radius)
    cu.bevel_resolution = max(0, (int(sides) - 4) // 2)
    cu.use_fill_caps = True
    sp = cu.splines.new('POLY')
    sp.points.add(len(pts) - 1)
    for p, q in zip(sp.points, pts):
        p.co = (q[0], q[1], q[2], 1.0)
    sp.use_smooth = True
    ob = bpy.data.objects.new(name, cu)
    (collection or bpy.context.scene.collection).objects.link(ob)
    if material is not None:
        cu.materials.append(material)
    return ob


def area_weighted_normals(me):
    """three's computeVertexNormals on a Blender mesh: each vertex's normal the area-weighted sum of its triangles'
    normals (a rounded box's flat faces stay flat, where Blender's angle weighting tilts them toward the fillets),
    set as custom normals on the smooth faces' corners; flat faces keep their face normal."""
    nt = len(me.loop_triangles)
    if not nt:
        return me
    tv = np.empty(nt * 3, np.int64)
    me.loop_triangles.foreach_get('vertices', tv)
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    co, t = co.reshape(-1, 3), tv.reshape(-1, 3)
    cr = np.cross(co[t[:, 1]] - co[t[:, 0]], co[t[:, 2]] - co[t[:, 0]])          # 2 x area x the normal
    vn = np.zeros_like(co)
    for k in range(3):
        np.add.at(vn, t[:, k], cr)
    vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-20)
    lv = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get('vertex_index', lv)
    out = vn[lv]
    npoly = len(me.polygons)
    sm = np.empty(npoly, bool)
    me.polygons.foreach_get('use_smooth', sm)
    lt = np.empty(npoly, np.int64)
    me.polygons.foreach_get('loop_total', lt)
    pn = np.empty(npoly * 3)
    me.polygons.foreach_get('normal', pn)
    poly_of_loop = np.repeat(np.arange(npoly), lt)
    flat = ~sm[poly_of_loop]
    out[flat] = pn.reshape(-1, 3)[poly_of_loop[flat]]
    me.normals_split_custom_set([tuple(x) for x in out])
    return me


def mesh(geo, mat=None, name='', collection=None, weighted=True):
    """mesh: an object of a geometry (a BMesh) with its material, linked into `collection` (default the scene's);
    it casts and receives shadows (Blender's defaults). weighted: three's area-weighted vertex normals on its smooth
    faces (area_weighted_normals) -> the object."""
    _require_bpy()
    me = bpy.data.meshes.new(name or 'mesh')
    geo.to_mesh(me)
    if mat is not None:
        me.materials.append(mat)
    if weighted and len(me.polygons):
        area_weighted_normals(me)
    ob = bpy.data.objects.new(name or 'mesh', me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    return ob


# ------------------------------------------------------------------------------------------------ the machine ---
def _snake(k):
    return re.sub(r'(?<=[a-z0-9])([A-Z])', lambda m: '_' + m.group(1).lower(), k)


class Machine:
    """A built voice machine (the JS build() result): group (the root Empty, in a collection of its own), parts,
    update(t, state), dispose(). Subclasses build in __init__ and implement _update(t, state, frame, ctx).
    ``name`` is the machine's registry name ('c64'); key(prop, value, ...) keys one of its channels."""

    name = ''

    def __init__(self, key, *, name=None, scene=None, collection=None, interpolation='CONSTANT', screen_dir=None,
                 ctx=None):
        _require_bpy()
        self.name = key
        self.ctx = ctx
        self.scene = scene or (ctx.scene if ctx is not None else bpy.context.scene)
        self.interpolation = interpolation
        self.src = load_glb(key)
        g = bpy.data.objects.new(name or key, None)
        g.empty_display_type = 'PLAIN_AXES'
        g.empty_display_size = 0.1
        self.collection = bpy.data.collections.new(g.name)
        (collection or self.scene.collection).children.link(self.collection)
        self.collection.objects.link(g)
        g['eido_src_asset'] = str(PACK / f'{key}.glb')
        self.collection['eido_src_asset'] = g['eido_src_asset']
        g['eido_loaded_asset'] = True
        g['vm_machine'] = key
        self.group = g
        if screen_dir is None and ctx is not None:
            screen_dir = Path(ctx.out_dir) / 'screens' / g.name
        if isinstance(screen_dir, str) and screen_dir.startswith('//'):     # Blender-relative: beside the blend
            if bpy.data.filepath:
                screen_dir = bpy.path.abspath(screen_dir)
            else:          # a '//' path of an unsaved blend has no anchor (and on Windows Path reads it as a share)
                print(f'[voice_machines] {key}: screen_dir {screen_dir!r} is relative to a blend that is not saved '
                      'yet; its frames go to a folder of their own under the system temp folder')
                screen_dir = None
        self.screen_dir = screen_dir
        self.objects = []
        self.materials = []
        self.screens = []
        self.channels = {}
        self.parts = {}
        self._keyed = {}                      # prop -> the value of its last key (a CONSTANT hold skips repeats)
        self._tubes = []                      # each display glass: its screen, mesh and material recipe
        self._scene_layers = []
        self.updates = 0

    # parts and materials
    def part(self, name, runtime=False):
        """A copy of the GLB's node `name`, parented to the root. runtime=True gives it its own mesh data (its
        materials are this machine's: LEDs, glow, metal, the screen); baked parts share the source's mesh."""
        src = self.src.get(name)
        if src is None:
            raise KeyError(f'[{self.name}] GLB is missing {name}')
        o = src.copy()
        if runtime:
            o.data = src.data.copy()
            o.data.name = f'{self.group.name}.{name}'
        o.name = name
        o['vm_part'] = name
        o['vm_machine'] = self.name
        o['eido_loaded_asset'] = True
        self.collection.objects.link(o)
        o.parent = self.group
        o.matrix_parent_inverse.identity()
        self.objects.append(o)
        return o

    def parts_named(self, prefix):
        return [self.part(n, runtime=True) for n in sorted(self.src) if n.startswith(prefix)]

    def material(self, m):
        self.materials.append(m)
        return m

    @staticmethod
    def assign(obj, mat):
        """Every material slot of obj's (own) mesh -> mat, keeping the polygons' slot indices."""
        mats = obj.data.materials
        if not len(mats):
            mats.append(mat)
        for i in range(len(mats)):
            mats[i] = mat

    def channel(self, prop, default=0.0, description=''):
        c = self.channels[prop] = Channel(self, prop, default, description)
        return c

    def era_screen(self, width, height, px, draw, nearest=False, suffix='screen'):
        s = EraScreen(self, f'{self.group.name}_{suffix}', width, height, px, draw, nearest=nearest,
                      out_dir=(Path(self.screen_dir) / suffix) if self.screen_dir else None)
        self.screens.append(s)
        return s

    def make_tube(self, screen, part='screen_crt', **opts):
        """The GLB's display glass `part` with the screen's material (screen_material(**opts)); the recipe is kept
        so show_scene can rebuild it with a scene layer over the drawing."""
        tube = self.part(part, runtime=True)
        spec = {'screen': screen, 'tube': tube, 'opts': dict(opts), 'layers': [], 'material': None}
        self._tubes.append(spec)
        self._build_tube(spec)
        return tube

    def _build_tube(self, spec):
        i = self._tubes.index(spec)
        m = screen_material(f'{self.group.name}.screen' + (f'{i}' if i else ''), spec['screen'], self.group,
                            scene=self.scene, layers=spec['layers'], **spec['opts'])
        self.assign(spec['tube'], self.material(m))
        old, spec['material'] = spec['material'], m
        if old is not None:
            self.materials.remove(old)
            if old.users == 0:
                bpy.data.materials.remove(old)
        return m

    def show_scene(self, scene_name=None, frames=None, *, source=None, t0=None, W=None, H=None, lyrics=None,
                   cues=None, bpm=128, modules=None, art_fps=None, prewarm=False, tube=0):
        """An era canvas scene on the machine's own tube over frames (first, last): 'sam_1982' on the C64,
        'mac_1984' on the Macintosh, 'desktop_2001' on the desktop's CRT, or any scene of
        eidoverse/graphics/era_screens_*.js (eidoblend.media.canvas_scenes.list_scenes()). It is baked with the
        engine's own drawing code (media.screens.bake_canvas_scene: Deno + Skia) at the tube's aspect (W x H, by
        default the machine's canvas scaled to about 1024 px wide), and mixed over the machine's own drawing by a
        CONSTANT-keyed root property scene_<k> (1 inside the range), through the same glass, raster, scanlines,
        switch-on, power and gain. Before and after the range the machine's own drawing shows. t0: the scene's
        start in film seconds; by default the time of the range's first frame, so the scene plays from its own
        beginning wherever the range sits in the film (with a ``cues`` table and no t0, the scene's cue decides).
        lyrics / cues / bpm / modules / art_fps / prewarm as bake_canvas_scene. source= puts any frames instead (a
        <name>_0001.png sequence, a still, a movie), as make_screen(source=...). Returns the layer's media
        Screen."""
        if not self._tubes:
            raise ValueError(f'[{self.name}] has no screen to show a scene on')
        from eidoblend.media import screens
        from eidoblend.media.timebase import Timebase
        spec = self._tubes[tube]
        scr = spec['screen']
        a, b = (int(frames[0]), int(frames[1])) if frames else (self.scene.frame_start, self.scene.frame_end)
        if t0 is None and not cues:
            t0 = Timebase.of(self.scene).t(a)
        k = len(spec['layers'])
        label = scene_name or Path(str(source)).stem
        prefix = re.sub(r'[^A-Za-z0-9_-]+', '_', f'{self.group.name}_{label}')
        if source is None:
            if not scene_name:
                raise ValueError('show_scene needs a scene_name or a source')
            s = max(1, js_round(1024 / scr.pw))
            out = (Path(self.screen_dir) / f'scene{k}_{label}') if self.screen_dir else _default_screen_dir(prefix)
            info = screens.bake_canvas_scene(out, (a, b), scene_name=scene_name, modules=modules, t0=t0,
                                             W=W or scr.pw * s, H=H or scr.ph * s, lyrics=lyrics, cues=cues, bpm=bpm,
                                             art_fps=art_fps, prefix=prefix, scene=self.scene, prewarm=prewarm)
            source = info['first']
        layer = SceneLayer(screens.make_screen(source=source, frames=(a, b), name=prefix, standalone=False,
                                               scene=self.scene), label)
        self._scene_layers.append(layer)
        prop = f'scene_{k}' if tube == 0 else f'scene{tube}_{k}'
        self.channel(prop, 0.0, f'{label} on the tube over frames {a}..{b} (1 = shown)')
        spec['layers'].append((layer, prop))
        self._build_tube(spec)
        g, ctx = self.group, self.ctx
        if a > self.scene.frame_start:
            g[prop] = 0.0
            key_prop(g, prop, a - 1, 'CONSTANT', ctx)
        g[prop] = 1.0
        key_prop(g, prop, a, 'CONSTANT', ctx)
        g[prop] = 0.0
        key_prop(g, prop, b + 1, 'CONSTANT', ctx)
        return layer.screen

    # time and keys
    def frame_at(self, t, ctx=None):
        ctx = ctx or self.ctx
        if ctx is not None:
            return int(ctx.frame_at(t))
        from eidoblend.media.timebase import Timebase
        return Timebase.of(self.scene).frame_round(t)

    def key(self, prop, value, t=None, ctx=None, frame=None):
        """root[prop] = value, keyed at the frame of t (frame= wins; neither: the current frame). The first key of a
        property after the scene's first frame keeps the value before it up to the frame before (the engine's
        uniform held its value until the first update set it)."""
        ctx = ctx or self.ctx
        f = frame if frame is not None else (self.scene.frame_current if t is None else self.frame_at(t, ctx))
        g = self.group
        value = float(value)
        if prop not in self._keyed:
            self._keyed[prop] = None
            if f > self.scene.frame_start:
                key_prop(g, prop, f - 1, 'CONSTANT', ctx)
        elif self.interpolation == 'CONSTANT' and self._keyed[prop] == value:
            g[prop] = value                   # a held value needs no key: the last one holds it
            return f
        g[prop] = value
        key_prop(g, prop, f, self.interpolation, ctx)
        self._keyed[prop] = value
        return f

    @staticmethod
    def state(state=None, kw=None) -> dict:
        """The update state as one dict with snake_case keys (cursorOn -> cursor_on): JS-shaped states port as they
        are."""
        st = {}
        for src in (state or {}), (kw or {}):
            for k, v in src.items():
                st[_snake(k)] = v
        return st

    def update(self, t, state=None, ctx=None, **kw):
        """update(t, state): the machine at film time t (seconds), keyed at its frame. Deterministic in t; call in
        time order, as in the engine. ctx (a scene's ctx) routes the keys through ctx.key."""
        st = self.state(state, kw)
        ctx = ctx or self.ctx
        f = self.frame_at(t, ctx)
        out = self._update(float(t), st, f, ctx)
        self.updates += 1
        return out

    def _update(self, t, st, f, ctx):
        raise NotImplementedError

    # cleanup
    def dispose(self, files=False):
        """Remove the machine from the blend: its objects, own meshes, materials, screen images (and with files=True
        their PNG folders); the shared source goes too once no machine uses it."""
        meshes = {o.data for o in self.objects if o.data is not None and o.data.users <= 1}
        for o in self.objects + [self.group]:
            if o and o.name in bpy.data.objects:
                bpy.data.objects.remove(o, do_unlink=True)
        for me in meshes:
            if me.users == 0:
                bpy.data.meshes.remove(me)
        for m in self.materials:
            if m.name in bpy.data.materials:
                bpy.data.materials.remove(m)
        for s in self.screens:
            if s.image.name in bpy.data.images:
                bpy.data.images.remove(s.image)
            if files and s.dir.is_dir():
                shutil.rmtree(s.dir, ignore_errors=True)
        for layer in self._scene_layers:
            if layer.image.name in bpy.data.images:
                bpy.data.images.remove(layer.image)
        self._scene_layers, self._tubes = [], []
        if self.collection.name in bpy.data.collections:
            bpy.data.collections.remove(self.collection)
        if all(o.data is None or o.data.users <= 1 for o in self.src.values()):
            srcs = list(self.src.values())
            coll = next((c for c in bpy.data.collections if c.get('eido_vm_source') == self.name), None)
            data = [o.data for o in srcs if o.data is not None]
            for o in srcs:
                bpy.data.objects.remove(o, do_unlink=True)
            for me in data:
                if me.users == 0:
                    mats = [mm for mm in me.materials if mm]
                    bpy.data.meshes.remove(me)
                    for mm in mats:
                        if mm.name in bpy.data.materials and mm.users == 0:
                            imgs = {n.image.name for n in mm.node_tree.nodes
                                    if getattr(n, 'image', None)} if mm.node_tree else set()
                            bpy.data.materials.remove(mm)
                            for name in imgs:                 # a packed map can feed two nodes: by name, once
                                im = bpy.data.images.get(name)
                                if im is not None and im.users == 0:
                                    bpy.data.images.remove(im)
            if coll is not None:
                bpy.data.collections.remove(coll)
        self.objects, self.materials, self.screens = [], [], []


__all__ = ['MACHINES', 'NAMES', 'load_machine', 'build_machine', 'rng', 'lin', 'hex_rgb', 'srgb_to_linear',
           'noise_data', 'noise_image', 'noise_texture', 'Nodes', 'drive', 'new_material', 'triplanar',
           'baked_material', 'metal_material', 'glow_material', 'led_material', 'screen_material', 'pixel_angle',
           'pixel_footprint', 'load_glb',
           'EraScreen', 'SceneLayer', 'Channel', 'Lamp', 'Machine', 'key_prop', 'font', 'font_file', 'js_round',
           'PACK', 'plastic_material', 'plastic', 'write_curvature', 'CURVATURE', 'curvature', 'bump_normal',
           # the canvas-2D core, canvas textures and mips
           'CANVAS_SS', 'css_rgba', 'Gradient', 'Canvas2D', 'make_canvas', 'quad', 'rr', 'speckle', 'build_mips',
           'bleed_alpha', 'CanvasTexture', 'canvas_texture', 'refresh_canvas_texture', 'flip_uv',
           # the geometry builders
           'rbox', 'rounded_rect_shape', 'shape_geometry', 'bake', 'smooth', 'merge', 'planar_uv',
           'planar_uv_facing', 'rr_points', 'loft_rings', 'keycap', 'RoundedPolyline', 'rounded_polyline', 'wire',
           'area_weighted_normals', 'mesh']

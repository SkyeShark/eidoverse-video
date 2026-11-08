"""The particle morph for Blender 5.2 EEVEE: the port of eidoverse/particle_morph.js (makeParticleMorph and the
ParticleMorph target generators), built as infrastructure: any 3D model, file, image, text or shape as a target.

A cloud of N particles that dissolves one point set and reforms it as another: a body into a swirling cloud, the
cloud into a model, a diagram, a word, ASCII art, and back. Each particle's position is the engine's positionNode,

    me     = smoothstep(0, 1, morph)
    base   = spin( mix(target_from, target_to, me) )                    rigid turn about the cloud's up axis
    baseV  = turn(base, vortex * sin(pi morph) * (0.8 phase + 0.6))    a per-particle swirl that peaks mid-morph
    p      = baseV * curl_scale + 0.35 t + 12 phase                    (three's axes)
    disp   = (sin p.y - cos p.z, sin p.z - cos p.x, sin p.x - cos p.y) * turb_scale
    center = baseV + disp * turb * sin(pi morph) * curl_strength       loosest in transit, crisp at both ends

with a camera-facing quad of size max(0.003, size * size_var) on it, coloured mix(color, color2, morph) and drawn
as a soft round dot (or the sprite `map`) that twinkles, blended additively (default) or normally.

In Blender
  - the cloud is one object: a mesh of N loose vertices carrying every target as point attributes (target_k, or a
    live binding live_i_k / live_w_k / live_j_k, and tcol_k when the target has its own colours) and the engine's
    per-particle seed iSeed (phase, size variance, turbulence scale);
  - its Geometry Nodes modifier is the engine's positionNode: it picks the segment's two targets (inputs From and
    To), mixes, spins and winds them, adds the curl, and instances the camera-facing quads (the active camera at each
    frame, so marker-bound cuts are followed, or the camera passed in);
  - the engine's uniforms are the modifier's inputs: m.uniforms holds them as keyable handles, morph(..., frame=f)
    keys a frame, and key_morph / key_sequence key whole eased transitions, so the saved .blend plays and renders any
    frame on its own;
  - a target can be LIVE: from_mesh(obj, n, live=True) or particle_targets.from_object(obj, n, live=True) binds every
    particle to a point of the object's evaluated (posed, skinned) surface, sampled in the graph at every frame: a
    dissolve leaves a walking body from the pose it has on that frame and a reform lands on the pose it has then.

Beyond the engine (each off by default, so the defaults are the engine's look):
  - targets in their own colours (sampled from the model's materials and textures): own_colors mixes them in;
  - render='sphere' (small icospheres) or 'points' (a point cloud: EEVEE draws spheres) besides 'billboard';
  - stagger: particles leave and land in turn (random, or a wipe along an axis: 'down' = head first);
  - pairing: 'height' / 'space' so a particle goes to a corresponding part of the next shape (a cleaner reform);
  - align='centroid': static targets moved onto the first target's centroid (the engine's "share centroids").

Also here: ascii_panel, the engine's makeAsciiPanel (ascii_panel.js, the glowing terminal the text example put under
its cloud), on the same text rasteriser as from_text; and figlet / ascii_banner for big block banners.

Randomness. The engine drew from Math.random(). Here the engine's generators take a JSRandom (mulberry32, vectorised)
or a seed and draw in the engine's order, so a Math.random() replaced by the same stream gives the engine's own
numbers (test_morph_parity.py). Axes: the generators build in three's frame, as the source does, and return Blender
coordinates (Z-up): a diagram or a word lies in the XZ plane, facing -Y. Spin and vortex turn about the object's Z
axis through its origin (the engine's world Y): leave the morph object at the origin, the targets are world points.

    from eidoblend.fx.particle_morph import make_particle_morph
    m = make_particle_morph(count=60000, targets=[robot_vrm, 'polyhaven:alarm_clock_01', 'neural_net', 'text:CLAUDE'],
                            live=True, align='centroid', size=0.02)
    m.key_sequence([(1, 60, 108), (2, 132, 176), (3, 196, 240, {'vortex': 6})])
"""

from __future__ import annotations

import math
import os
import struct

import numpy as np

from ._util import color as linear_color, from_three, to_three
from .particles import (Uniforms, camera_rotation, finish_sprite_material, input_slot, modifier_uniform,
                        new_sprite_material, scene_clock, scene_or_group, set_modifier_input, sprite_image,
                        sprite_quad, store_point)
from . import particle_targets as PT
from .particle_targets import Target

_PI = 3.14159265     # the engine's literal


# ------------------------------------------------------------------------------------------------- randomness ---

class JSRandom:
    """A Math.random()-like stream: mulberry32(seed), vectorised (its state only counts up, so the k-th draw is a
    function of seed and k). JSRandom(seed)() draws one number, .take(k) the next k, in the order the JS would."""

    def __init__(self, seed=1):
        self.seed = int(seed) & 0xffffffff
        self.n = 0

    def take(self, k):
        k = int(k)
        if k <= 0:
            return np.zeros(0)
        i = np.arange(self.n + 1, self.n + k + 1, dtype=np.uint64)
        a = ((np.uint64(self.seed) + i * np.uint64(0x6D2B79F5)) & np.uint64(0xffffffff)).astype(np.uint32)
        t = (a ^ (a >> np.uint32(15))) * (a | np.uint32(1))
        t = t ^ (t + (t ^ (t >> np.uint32(7))) * (t | np.uint32(61)))
        self.n += k
        return (t ^ (t >> np.uint32(14))).astype(np.float64) / 4294967296.0

    def __call__(self):
        return float(self.take(1)[0])

    def random(self, k=None):
        """numpy-like: .random(k) -> k draws (lets a JSRandom stand in for a numpy Generator in samplers)."""
        return self() if k is None else self.take(int(np.prod(k))).reshape(k)


def _stream(random=None, seed=1):
    return random if random is not None else JSRandom(seed)


def _opts(opts, kw):
    o = dict(opts or {})
    o.update(kw)
    return o


def _count(v, default):
    """JS `opts.count | 0 || default`."""
    try:
        c = int(v) if v is not None else 0
    except (TypeError, ValueError):
        c = 0
    return c or default


# ------------------------------------------------------------------------------------------------- resampling ---

def _plan(m, n, rnd):
    """resampleToN's choice for n outputs from m inputs: the source index of each (cycle when upsampling, stride when
    downsampling) and its jitter (+-0.01 per axis when upsampling, three's axes). Draws 3 n numbers, as the engine
    does (rand(-0, 0) is still a draw)."""
    i = np.arange(n, dtype=np.int64)
    j = (i * m) // n if m >= n else i % m
    jit = 0.01 if m < n else 0.0
    r = rnd.take(3 * n).reshape(n, 3)
    return j, -jit + r * (2 * jit)


def _resample_three(flat3, n, rnd):
    """The engine's resampleToN on (m, 3) three-frame points -> (n, 3) float32."""
    flat3 = np.asarray(flat3, dtype=np.float32).reshape(-1, 3)
    m = len(flat3)
    if m == 0:
        return np.zeros((n, 3), dtype=np.float32)
    j, jit = _plan(m, n, rnd)
    return (flat3[j].astype(np.float64) + jit).astype(np.float32)


def resample_to_n(src, n, random=None, seed=1):
    """resampleToN: any point list -> exactly n points, (n, 3) float32 in Blender coordinates."""
    rnd = _stream(random, seed)
    pts = np.asarray(src, dtype=np.float64).reshape(-1, 3)
    return from_three(_resample_three(to_three(pts), int(n), rnd)).astype(np.float32)


# -------------------------------------------------------------------------------------------------- from_mesh ---

def from_mesh(object3d, count, live=False, frame=None, random=None, seed=1, colors=False):
    """ParticleMorph.fromMesh: points off a mesh or VRM in its CURRENT pose (evaluated: armature, shape keys,
    modifiers), as the engine sampled it: every mesh's vertices with a stride of max(1, V // 8000) so a huge mesh does
    not dominate, then resampled to `count`. -> (count, 3) float32, Blender world coordinates.

    frame: sample at that frame instead of the current one (the engine's updateTarget(0, fromMesh(vrm.scene, n)) at
    the dissolve frame). live=True: a Target bound to the vertices, sampled by the morph graph at every frame (it
    also covers a reform that lands on a moving body). colors=True: a Target with each vertex's material colour.
    For an even cover of the surface (low-poly props collapse to vertex rings here, as in the engine), use
    particle_targets.from_object(obj, count) (area-weighted)."""
    t = PT.from_object(object3d, count, mode='vertices', live=live, frame=frame, colors=colors or live, seed=seed,
                       random=random)
    if live or colors:
        return t
    return t.points


# -------------------------------------------------------------------------------------------------- from_text ---

_FONT_DIRS = ('C:/Windows/Fonts', os.path.expanduser('~/AppData/Local/Microsoft/Windows/Fonts'), '/usr/share/fonts',
              '/usr/local/share/fonts', os.path.expanduser('~/.fonts'), os.path.expanduser('~/.local/share/fonts'),
              '/Library/Fonts', '/System/Library/Fonts', '/System/Library/Fonts/Supplemental')
_FAMILIES = {
    ('sans', 'bold'): ('arialbd.ttf', 'Arial Bold.ttf', 'LiberationSans-Bold.ttf', 'DejaVuSans-Bold.ttf',
                       'Helvetica-Bold.ttf'),
    ('sans', 'normal'): ('arial.ttf', 'Arial.ttf', 'LiberationSans-Regular.ttf', 'DejaVuSans.ttf'),
    ('serif', 'bold'): ('timesbd.ttf', 'Times New Roman Bold.ttf', 'LiberationSerif-Bold.ttf', 'DejaVuSerif-Bold.ttf'),
    ('serif', 'normal'): ('times.ttf', 'Times New Roman.ttf', 'LiberationSerif-Regular.ttf', 'DejaVuSerif.ttf'),
    ('mono', 'bold'): ('consolab.ttf', 'DejaVuSansMono-Bold.ttf', 'LiberationMono-Bold.ttf', 'courbd.ttf'),
    ('mono', 'normal'): ('consola.ttf', 'DejaVuSansMono.ttf', 'LiberationMono-Regular.ttf', 'cour.ttf',
                         'Courier New.ttf', 'Menlo.ttc'),
}
_GENERIC = {'monospace': 'mono', 'courier': 'mono', 'courier new': 'mono', 'consolas': 'mono', 'menlo': 'mono',
            'sans-serif': 'sans', 'arial': 'sans', 'helvetica': 'sans', 'system-ui': 'sans', 'inter': 'sans',
            'serif': 'serif', 'times': 'serif', 'times new roman': 'serif', 'georgia': 'serif'}
_FONT_IDS = {}


def _find_font_file(fname):
    for d in _FONT_DIRS:
        if not os.path.isdir(d):
            continue
        p = os.path.join(d, fname)
        if os.path.exists(p):
            return p
        if d.startswith('/usr') or d.startswith(os.path.expanduser('~/.')):
            for root, _dirs, files in os.walk(d):
                if fname in files:
                    return os.path.join(root, fname)
    return None


def _library_font(fam, bold):
    """A display font from eidoverse/assets/fonts by family name ('Orbitron', 'Audiowide', 'Space Mono' ...)."""
    from .. import common
    d = os.path.join(common.ASSETS_DIR, 'fonts')
    if not os.path.isdir(d):
        return None
    key = fam.lower().replace(' ', '').replace('-', '').replace('_', '')
    cands = [f for f in sorted(os.listdir(d)) if f.lower().endswith(('.ttf', '.otf'))
             and f.lower().replace('-', '').replace('_', '').startswith(key)]
    if not cands:
        return None
    pref = [f for f in cands if ('bold' in f.lower()) == bool(bold)] or cands
    reg = [f for f in pref if 'regular' in f.lower()] if not bold else []
    return os.path.join(d, (reg or pref)[0])


def font_file(family, weight='normal'):
    """The font file for a CSS-like family list ('Arial, sans-serif', 'monospace', 'Orbitron', or a path to a .ttf /
    .otf / .woff2): the first family found (a path, the repo's display fonts in eidoverse/assets/fonts, then the
    system's), then Blender's own Inter / DejaVu Sans Mono."""
    import bpy
    w = 'bold' if str(weight).lower() in ('bold', '700', '800', '900', 'bolder') else 'normal'
    for fam in [f.strip().strip('"\'') for f in str(family).split(',')]:
        if os.path.exists(fam):
            return fam
        kind = _GENERIC.get(fam.lower())
        if kind is None:
            lib = _library_font(fam, w == 'bold')
            if lib:
                return lib
            continue
        for fname in _FAMILIES[(kind, w)] + _FAMILIES[(kind, 'normal')]:
            p = _find_font_file(fname)
            if p:
                return p
    mono = any(_GENERIC.get(f.strip().lower()) == 'mono' for f in str(family).split(','))
    return os.path.join(bpy.utils.resource_path('LOCAL'), 'datafiles', 'fonts',
                        'DejaVuSansMono.woff2' if mono else 'Inter.woff2')


def font_ascent(path):
    """The font's ascent in ems (hhea ascender / unitsPerEm), where a canvas puts the top of the em box for
    textBaseline 'top'. Read from the .ttf / .otf / .ttc tables; 0.93 for formats it cannot read (woff2)."""
    try:
        with open(path, 'rb') as f:
            data = f.read()
        off = 0
        if data[:4] == b'ttcf':
            off = struct.unpack('>I', data[12:16])[0]
        n = struct.unpack('>H', data[off + 4:off + 6])[0]
        tables = {}
        for i in range(n):
            rec = off + 12 + 16 * i
            tag = data[rec:rec + 4].decode('latin-1')
            tables[tag] = struct.unpack('>I', data[rec + 8:rec + 12])[0]
        upm = struct.unpack('>H', data[tables['head'] + 18:tables['head'] + 20])[0]
        asc = struct.unpack('>h', data[tables['hhea'] + 4:tables['hhea'] + 6])[0]
        return asc / float(upm)
    except (OSError, KeyError, struct.error, UnicodeDecodeError):
        return 0.93


def _font_id(path):
    import blf
    fid = _FONT_IDS.get(path)
    if fid is None:
        fid = blf.load(path)
        if fid < 0:
            raise RuntimeError(f'[particle_morph] from_text: cannot load the font {path}')
        _FONT_IDS[path] = fid
    return fid


def text_mask(text, font_size=None, font_family=None, weight=None, ascii=False):
    """The engine's canvas for fromText: the text drawn white on a transparent canvas, (H, W) alpha 0..255, row 0 at
    the TOP like getImageData. A canvas of max line width + 2 pad by lines * line height + 2 pad (pad = 0.2 font size,
    line height 1.18 font size, 1.05 for ASCII art), each line drawn from (pad, pad + i * line height) with its em box
    top there (textBaseline 'top': the font's ascent above the baseline). Drawn by Blender's own text engine (blf)
    into an image buffer: no GPU, no browser."""
    import blf
    import imbuf
    font_px = font_size or (28 if ascii else 160)
    family = font_family or ('monospace' if ascii else 'Arial, sans-serif')
    w = None if ascii else (weight or 'bold')
    lines = str(text).split('\n')
    line_h = font_px * 1.05 if ascii else font_px * 1.18
    path = font_file(family, w or 'normal')
    return _draw_lines(lines, path, font_px, line_h, math.ceil(font_px * 0.2))


def _draw_lines(lines, path, font_px, line_h, pad):
    """A canvas of max line width + 2 pad by lines * line height + 2 pad with the lines drawn white from
    (pad, pad + i * line height), textBaseline 'top' -> (H, W) alpha 0..255, row 0 at the top."""
    import blf
    import imbuf
    fid = _font_id(path)
    blf.size(fid, font_px)
    max_w = 1.0
    for ln in lines:
        max_w = max(max_w, blf.dimensions(fid, ln)[0] or 1.0)
    W = math.ceil(max_w) + pad * 2
    H = math.ceil(line_h * len(lines)) + pad * 2
    ib = imbuf.new((W, H))
    ascent = font_ascent(path) * font_px
    with blf.bind_imbuf(fid, ib):
        blf.color(fid, 1.0, 1.0, 1.0, 1.0)
        for i, ln in enumerate(lines):
            top = pad + i * line_h
            blf.position(fid, pad, H - (top + ascent), 0)
            blf.draw_buffer(fid, ln)
    with ib.with_buffer() as buf:
        a = np.array(buf)
    ib.free()
    return a[::-1, :, 3].copy()


def _gauss_blur(a, sigma):
    """A separable Gaussian blur of a 2D array (zero outside), the canvas shadowBlur's (sigma = blur / 2)."""
    if sigma <= 0:
        return a
    r = max(1, int(math.ceil(3.0 * sigma)))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    out = a.astype(np.float64)
    for axis in (0, 1):
        pad = [(0, 0), (0, 0)]
        pad[axis] = (r, r)
        p = np.pad(out, pad)
        n = out.shape[axis]
        acc = np.zeros_like(out)
        for i, w in enumerate(k):
            acc += w * (p[i:i + n] if axis == 0 else p[:, i:i + n])
        out = acc
    return out


def _hex_srgb(c):
    """An engine colour as display sRGB 0..1 (the canvas's own values)."""
    if isinstance(c, str):
        h = c.lstrip('#')
        return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])
    if isinstance(c, (int, np.integer)):
        c = int(c) & 0xffffff
        return np.array([(c >> 16) & 255, (c >> 8) & 255, c & 255]) / 255.0
    return np.asarray(c, dtype=np.float64)[:3]


class AsciiPanel:
    """What ascii_panel returns, the engine's { mesh, texture, canvas, width, height }: object (also .mesh, the plane),
    texture (its image), canvas ((H, W, 4) display sRGB, row 0 at the top), material, width, height."""

    def __init__(self, obj, image, canvas, material, width, height):
        self.object = self.mesh = obj
        self.texture = self.image = image
        self.canvas, self.material, self.width, self.height = canvas, material, width, height


def ascii_canvas(text, color=0x33ff66, bg=0x04140a, transparent=False, font_size=22, font_family='monospace',
                 padding=None, glow=None, scanlines=False):
    """The engine's makeAsciiPanel canvas: (H, W, 4) display sRGB + alpha, row 0 at the top. Monospace lines (tabs as
    4 spaces) on a bg fill (or clear), line height 1.12 font size, padding = font size by default, the text in
    `color` with a glow (the canvas shadow: blur glow px, default half the font size, False for none) and CRT
    scanlines (black at 18 % on every third row)."""
    font_px = int(font_size or 22)
    line_h = font_px * 1.12
    pad = int(padding if padding is not None else font_px)
    lines = str(text).replace('\t', '    ').split('\n')
    a = _draw_lines(lines, font_file(font_family or 'monospace', 'normal'), font_px, line_h, pad).astype(
        np.float64) / 255.0
    H, W = a.shape
    col = _hex_srgb(color)
    # source-over in premultiplied sRGB, as the canvas composites: the fill, the shadow, the text, the scanlines
    if transparent:
        P, al = np.zeros((H, W, 3)), np.zeros((H, W))
    else:
        P, al = np.broadcast_to(_hex_srgb(bg), (H, W, 3)).copy(), np.ones((H, W))

    def over(c, k):
        nonlocal P, al
        P = c * k[..., None] + P * (1.0 - k[..., None])
        al = k + al * (1.0 - k)
    if glow is not False:
        over(col, _gauss_blur(a, (glow or font_px * 0.5) / 2.0))     # the shadow: the text's coverage, blurred
    over(col, a)
    if scanlines:
        k = np.zeros((H, W))
        k[np.arange(H) % 3 == 0] = 0.18
        over(np.zeros(3), k)
    rgb = np.where(al[..., None] > 0, P / np.maximum(al, 1e-9)[..., None], 0.0)
    return np.concatenate([np.clip(rgb, 0, 1), al[..., None]], -1)


def ascii_panel(text, color=0x33ff66, bg=0x04140a, transparent=False, font_size=22, font_family='monospace',
                width=3.0, padding=None, glow=None, scanlines=False, display='exact', location=(0.0, 0.0, 0.0),
                rotation=(math.pi / 2, 0.0, 0.0), name='ascii_panel', scene=None, collection=None, opts=None):
    """makeAsciiPanel (the engine's ascii_panel.js, which the text example's terminal used): multi-line ASCII art or
    monospace text on a plane as a crisp glowing terminal screen, for monitors, HUDs, code walls, server readouts.
    Banners: pass figlet() or ascii_banner() output.

    The engine's options (snake_case; opts takes them as one dict, camelCase too): color, bg, transparent (no bg: an
    overlay), font_size 22, font_family 'monospace', width (metres; the height follows the canvas), padding, glow
    (px, False for none), scanlines. The plane stands in the XZ plane facing -Y at `location` (rotation: Euler XYZ,
    default upright; three's PlaneGeometry lay in its XY plane facing +Z, the camera's way).

    display: 'exact' (the engine's toneMapped: false: the screen shows its pixels as drawn, through the inverse of
    the scene's view, set at creation) or 'view' (a plain emissive texture the film's view tone maps). The image is
    packed into the .blend. -> AsciiPanel (.mesh, .texture, .canvas, .width, .height)."""
    import bpy
    if opts:
        o = {**{_snake(k): v for k, v in dict(opts).items()}}
        color, bg = o.get('color', color), o.get('bg', bg)
        transparent, font_size = o.get('transparent', transparent), o.get('font_size', font_size)
        font_family, width = o.get('font_family', font_family), o.get('width', width)
        padding, glow, scanlines = o.get('padding', padding), o.get('glow', glow), o.get('scanlines', scanlines)
    cv = ascii_canvas(text, color, bg, transparent, font_size, font_family, padding, glow, scanlines)
    H, W = cv.shape[:2]
    sc = scene or bpy.context.scene
    img = bpy.data.images.new(name + '_tex', W, H, alpha=True, float_buffer=(display == 'exact'))
    if display == 'exact':
        from ._look import SceneView
        img.colorspace_settings.name = 'Linear Rec.709'
        q = np.round(cv[..., :3].reshape(-1, 3) * 255.0).astype(np.int64)
        keys = (q[:, 0] << 16) | (q[:, 1] << 8) | q[:, 2]
        uniq, inv = np.unique(keys, return_inverse=True)
        d = np.stack([(uniq >> 16) & 255, (uniq >> 8) & 255, uniq & 255], 1) / 255.0
        lin = SceneView(sc).from_display(d)
        px = np.concatenate([lin[inv].reshape(H, W, 3), cv[..., 3:]], -1)
    elif display == 'view':
        img.colorspace_settings.name = 'sRGB'
        px = cv
    else:
        raise ValueError(f"[particle_morph] ascii_panel display {display!r}: 'exact' or 'view'")
    img.pixels.foreach_set(np.ascontiguousarray(px[::-1], dtype=np.float32).ravel())
    if display == 'exact':
        img.file_format = 'OPEN_EXR'
    img.pack()
    height = float(width) * H / W
    me = bpy.data.meshes.new(name)
    hw, hh = float(width) / 2, height / 2
    me.from_pydata([(-hw, -hh, 0), (hw, -hh, 0), (hw, hh, 0), (-hw, hh, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='UVMap')
    uv.data.foreach_set('uv', [0, 0, 1, 0, 1, 1, 0, 1])
    ob = bpy.data.objects.new(name, me)
    (collection or sc.collection).objects.link(ob)
    ob.location = tuple(location)
    ob.rotation_euler = tuple(rotation)
    ob['no_support_check'] = True
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    tex.interpolation = 'Linear'
    em = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(tex.outputs['Color'], em.inputs['Color'])
    if transparent:
        tr = nt.nodes.new('ShaderNodeBsdfTransparent')
        mix = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(tex.outputs['Alpha'], mix.inputs['Fac'])
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs['Surface'])
        mat.surface_render_method = 'BLENDED'
    else:
        nt.links.new(em.outputs[0], out.inputs['Surface'])
    mat.use_backface_culling = False
    me.materials.append(mat)
    ob.visible_shadow = False
    return AsciiPanel(ob, img, cv, mat, float(width), height)


def _snake(k):
    return ''.join('_' + c.lower() if c.isupper() else c for c in str(k))


def from_text(text, count, opts=None, random=None, seed=1, **kw):
    """ParticleMorph.fromText: particles in the SHAPE OF TEXT, a word, a logo, or multi-line ASCII art.

    opts (or keywords): width (world width of the canvas, default 4) · depth (thickness, default 0) · font_size (px,
    default 160, 28 for ascii) · font_family (CSS-like list, a display font of the repo by name, or a font path) ·
    ascii (monospace and whitespace kept: multi-line ASCII art; ascii_banner / figlet banners work as they are) ·
    pixel_stride (sampling density, default 2) · weight ('bold' default, 'normal'). The glyph pixels (alpha > 128 on
    the stride grid) are centred on the canvas and laid in the XZ plane facing -Y, then resampled to count.
    -> (count, 3) float32."""
    o = _opts(opts, kw)
    rnd = _stream(random, seed)
    ascii_ = bool(o.get('ascii'))
    a = text_mask(text, o.get('font_size') or o.get('fontSize'), o.get('font_family') or o.get('fontFamily'),
                  o.get('weight'), ascii_)
    H, W = a.shape
    stride = max(1, int(o.get('pixel_stride') or o.get('pixelStride') or 2))
    ys, xs = np.nonzero(a[::stride, ::stride] > 128)
    if not len(xs):
        print('[particle_morph] from_text: no glyph pixels (font/text issue)')
        return np.zeros((int(count), 3), dtype=np.float32)
    x, y = xs * stride, ys * stride
    target_w = o.get('width') if o.get('width') is not None else 4
    scale = float(target_w) / W
    cx, cy = W / 2, H / 2
    dz = float(o.get('depth') or 0)
    z = (-dz / 2 + rnd.take(len(x)) * dz) if dz else np.zeros(len(x))
    pts3 = np.stack([(x - cx) * scale, -(y - cy) * scale, z], 1)
    return from_three(_resample_three(pts3, int(count), rnd)).astype(np.float32)


def ascii_banner(text, rows=8, fill='#', font='Arial, sans-serif', weight='bold', threshold=0.42, cell_px=None):
    """A big block-letter ASCII banner of `text` (one line per text line), `rows` character rows per capital, drawn
    from the text's own glyphs: for from_text(banner, n, ascii=True). The engine's guide suggested pyfiglet banners;
    pyfiglet is not part of Blender's Python, so this needs nothing installed (figlet() uses pyfiglet when present)."""
    ch_aspect = 0.6 / 1.05                         # a monospace cell, as from_text(ascii=True) lays it
    font_px = 96
    a = text_mask(text, font_px, font, weight, False).astype(np.float32) / 255.0
    cap = 0.72 * font_px
    chh = cell_px[1] if cell_px else cap / rows
    chw = cell_px[0] if cell_px else chh * ch_aspect
    H, W = a.shape
    ny, nx = int(H // chh), int(W // chw)
    out = []
    for r in range(ny):
        y0, y1 = int(r * chh), int((r + 1) * chh)
        line = []
        for c in range(nx):
            x0, x1 = int(c * chw), int((c + 1) * chw)
            cov = float(a[y0:y1, x0:x1].mean()) if y1 > y0 and x1 > x0 else 0.0
            line.append(fill if cov > threshold else ' ')
        out.append(''.join(line).rstrip())
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    lead = min((len(ln) - len(ln.lstrip()) for ln in out if ln.strip()), default=0)
    return '\n'.join(ln[lead:] for ln in out)


def figlet(text, font='standard', width=200, fallback=True):
    """A pyfiglet banner (the engine's docs: big ASCII banners for from_text(..., ascii=True)). Uses pyfiglet from
    Blender's Python, or from a system Python on PATH; when neither has it, ascii_banner(text) (fallback=False:
    raise ImportError instead)."""
    try:
        import pyfiglet
        return pyfiglet.figlet_format(text, font=font, width=width)
    except ImportError:
        pass
    import shutil
    import subprocess
    for exe in ('python', 'python3', 'py'):
        p = shutil.which(exe)
        if not p:
            continue
        r = subprocess.run([p, '-c', 'import sys, pyfiglet; sys.stdout.write(pyfiglet.figlet_format(sys.argv[1], '
                            'font=sys.argv[2], width=int(sys.argv[3])))', text, font, str(width)],
                           capture_output=True, text=True)
        if r.returncode == 0:
            return r.stdout
    if not fallback:
        raise ImportError('figlet: pyfiglet is in neither Blender\'s Python nor a system Python on PATH')
    print('[particle_morph] figlet: no pyfiglet here; drawing the banner with ascii_banner')
    return ascii_banner(text)


# ------------------------------------------------------------------------------------ the procedural targets ---

def neuron_graph(opts=None, random=None, seed=1, **kw):
    """ParticleMorph.neuronGraph: a procedural "neuron map": nodes scattered in a slab, each linked to its k nearest;
    points split between dense glowing node blobs and thin strands along the edges.
    opts: count 40000 · nodes 90 · rx 2.6 · ry 1.6 · rz 1.2 (half extents, three's x, y, z: width, height, depth) ·
    k 3 · node_frac 0.45. -> (count, 3) float32, Blender coordinates."""
    o = _opts(opts, kw)
    rnd = _stream(random, seed)
    count = _count(o.get('count'), 40000)
    nodes = _count(o.get('nodes'), 90)
    rx = o['rx'] if o.get('rx') is not None else 2.6
    ry = o['ry'] if o.get('ry') is not None else 1.6
    rz = o['rz'] if o.get('rz') is not None else 1.2
    k = _count(o.get('k'), 3)
    nf = o.get('node_frac', o.get('nodeFrac'))
    node_frac = nf if nf is not None else 0.45
    r = rnd.take(4 * nodes).reshape(nodes, 4)
    N = np.stack([-rx + r[:, 0] * 2 * rx, -ry + r[:, 1] * 2 * ry, (-rz + r[:, 2] * 2 * rz) * (0.4 + r[:, 3] * 0.6)], 1)
    E = []
    for i in range(nodes):
        d = ((N[i] - N) ** 2).sum(1)
        d[i] = np.inf
        order = [j for j in np.argsort(d, kind='stable') if j != i]
        for e in range(min(k, len(order))):
            j = int(order[e])
            if i < j:
                E.append((i, j))
    E = np.array(E, dtype=np.int64).reshape(-1, 2)
    node_pts = int(math.floor(count * node_frac))
    out = np.empty((count, 3), dtype=np.float64)
    nb = min(node_pts, count)
    if nb:
        rb = rnd.take(3 * nb).reshape(nb, 3)
        out[:nb] = N[np.arange(nb) % nodes] + (-0.06 + rb * 0.12)
    rest = np.arange(nb, count)
    if len(rest):
        if len(E):
            rs = rnd.take(4 * len(rest)).reshape(-1, 4)
            e = E[rest % len(E)]
            a, b_ = N[e[:, 0]], N[e[:, 1]]
            t = rs[:, :1]
            out[nb:] = a + (b_ - a) * t + (-0.015 + rs[:, 1:] * 0.03)
        else:
            out[nb:] = N[rest % nodes]
    return from_three(out.astype(np.float32)).astype(np.float32)


def neural_net(opts=None, random=None, seed=1, **kw):
    """ParticleMorph.neuralNet: the textbook deep-network diagram, columns of node discs (one per layer) fully
    connected to the next by straight edges, in the plane facing the camera with a little depth jitter.
    opts: count 40000 · layers (5, 8, 8, 8, 6) · width 4.6 (total span) · height 2.8 (tallest column) · node_r 0.075 ·
    depth_jit 0.05 · node_frac 0.34. Centred on the origin in the XZ plane, facing -Y. -> (count, 3) float32."""
    o = _opts(opts, kw)
    rnd = _stream(random, seed)
    count = _count(o.get('count'), 40000)
    layers = list(o.get('layers') or (5, 8, 8, 8, 6))
    width = o['width'] if o.get('width') is not None else 4.6
    height = o['height'] if o.get('height') is not None else 2.8
    nr = o.get('node_r', o.get('nodeR'))
    node_r = nr if nr is not None else 0.075
    dj_ = o.get('depth_jit', o.get('depthJit'))
    dj = dj_ if dj_ is not None else 0.05
    nf = o.get('node_frac', o.get('nodeFrac'))
    node_frac = nf if nf is not None else 0.34
    L = len(layers)
    cols = []
    mx = max(layers)
    for li in range(L):
        x = 0.0 if L == 1 else (-width / 2 + (li / (L - 1)) * width)
        n = layers[li]
        h = height * (0.45 + 0.55 * (n / mx))
        cols.append([(x, 0.0 if n == 1 else (-h / 2 + (ni / (n - 1)) * h), 0.0) for ni in range(n)])
    edges = [(a, b_) for li in range(L - 1) for a in cols[li] for b_ in cols[li + 1]]
    flat = np.array([nd for c in cols for nd in c], dtype=np.float64)
    out = np.empty((count, 3), dtype=np.float64)
    node_pts = int(math.floor(count * node_frac))
    nb = min(node_pts, count)
    if nb:
        r = rnd.take(3 * nb).reshape(nb, 3)
        nd = flat[np.arange(nb) % len(flat)]
        ang = r[:, 0] * math.pi * 2
        rad = np.sqrt(r[:, 1]) * node_r
        out[:nb, 0] = nd[:, 0] + np.cos(ang) * rad
        out[:nb, 1] = nd[:, 1] + np.sin(ang) * rad
        out[:nb, 2] = nd[:, 2] + (-dj + r[:, 2] * 2 * dj)
    rest = np.arange(nb, count)
    if len(rest):
        if edges:
            E = np.array(edges, dtype=np.float64)                      # (e, 2, 3)
            rs = rnd.take(4 * len(rest)).reshape(-1, 4)
            e = E[rest % len(E)]
            t = rs[:, 0]
            out[nb:, 0] = e[:, 0, 0] + (e[:, 1, 0] - e[:, 0, 0]) * t + (-0.006 + rs[:, 1] * 0.012)
            out[nb:, 1] = e[:, 0, 1] + (e[:, 1, 1] - e[:, 0, 1]) * t + (-0.006 + rs[:, 2] * 0.012)
            out[nb:, 2] = -dj + rs[:, 3] * 2 * dj
        else:
            out[nb:] = flat[rest % len(flat)]
    return from_three(out.astype(np.float32)).astype(np.float32)


def from_points(arr, count, random=None, seed=1):
    """ParticleMorph.fromPoints: resample any point list ((m, 3), a flat array, [x, y, z] triples; Blender
    coordinates) to exactly count points (cycled with a 1 cm jitter when upsampling)."""
    return resample_to_n(np.asarray(arr), count, random=random, seed=seed)


class ParticleMorph:
    """The engine's ParticleMorph namespace of target generators (each -> (count, 3) float32, Blender coordinates),
    and the Blender edition's infrastructure (each -> a Target with points, the model's colours, maybe live)."""
    from_points = staticmethod(from_points)
    from_mesh = staticmethod(from_mesh)
    from_text = staticmethod(from_text)
    neuron_graph = staticmethod(neuron_graph)
    neural_net = staticmethod(neural_net)
    resample_to_n = staticmethod(resample_to_n)
    figlet = staticmethod(figlet)
    ascii_banner = staticmethod(ascii_banner)
    # the infrastructure (particle_targets)
    target = staticmethod(PT.target)
    from_object = staticmethod(PT.from_object)
    from_file = staticmethod(PT.from_file)
    from_image = staticmethod(PT.from_image)
    from_silhouette = staticmethod(PT.from_silhouette)
    from_point_cloud = staticmethod(PT.from_point_cloud)
    from_volume = staticmethod(PT.from_volume)
    shapes = PT.shapes


# ----------------------------------------------------------------------------------------------------- easing ---

_CURVES = ('sine', 'quad', 'cubic', 'quart', 'quint', 'expo', 'circ', 'back', 'bounce', 'elastic')


def ease_spec(name):
    """An easing name -> (F-curve interpolation, easing): 'linear', 'constant', 'smooth' (Bezier), or a Penner
    curve 'sine' 'quad' 'cubic' 'quart' 'quint' 'expo' 'circ' 'back' 'bounce' 'elastic' with an optional
    'in_' / 'out_' / 'in_out_' prefix (bare = in_out): 'out_back', 'in_out_cubic', 'expo'."""
    n = (name or 'linear').lower().replace('-', '_')
    if n in ('linear', 'constant'):
        return n.upper(), 'AUTO'
    if n in ('smooth', 'bezier'):
        return 'BEZIER', 'AUTO'
    for pre, easing in (('in_out_', 'EASE_IN_OUT'), ('inout_', 'EASE_IN_OUT'), ('in_', 'EASE_IN'),
                        ('out_', 'EASE_OUT')):
        if n.startswith(pre) and n[len(pre):] in _CURVES:
            return n[len(pre):].upper(), easing
    if n in _CURVES:
        return n.upper(), 'EASE_IN_OUT'
    raise ValueError(f'[particle_morph] ease {name!r}: linear, constant, smooth, or [in_|out_|in_out_]{_CURVES}')


def _channelbag(idb):
    ad = getattr(idb, 'animation_data', None)
    if ad is None or ad.action is None:
        return None
    from bpy_extras import anim_utils
    try:
        return anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    except (AttributeError, TypeError, RuntimeError):
        return None


def key_prop(owner, prop, frame, ease='linear', index=-1, ctx=None):
    """Key owner.prop at frame with an easing for the segment that starts there (ease_spec). With a harness ctx and a
    plain interpolation, ctx.key does it (and logs it)."""
    interp, easing = ease_spec(ease)
    if ctx is not None and interp in ('LINEAR', 'CONSTANT', 'BEZIER'):
        return ctx.key(owner, prop, index=index, frame=frame, interpolation=interp)
    ok = owner.keyframe_insert(prop, index=index, frame=frame)
    path = owner.path_from_id(prop)
    cb = _channelbag(owner.id_data)
    if cb is not None:
        for fc in cb.fcurves:
            if fc.data_path == path and (index < 0 or fc.array_index == index):
                for kp in fc.keyframe_points:
                    if abs(kp.co.x - frame) < 1e-3:
                        kp.interpolation = interp
                        if easing != 'AUTO':
                            kp.easing = easing
                fc.update()
    return ok


def key_visibility(src, frame, visible, ctx=None):
    """Key a source's objects shown or hidden from `frame` on (viewport and render, CONSTANT): the handoff between a
    body and its cloud. src: an Object (with its children), a Collection, a VRMHandle (its meshes), a Target with a
    .source, or a list."""
    for o in PT._objects_of(src):
        if o.type not in ('MESH', 'CURVE', 'SURFACE', 'FONT', 'META', 'POINTCLOUD', 'VOLUME', 'CURVES', 'EMPTY'):
            continue
        for prop in ('hide_render', 'hide_viewport'):
            setattr(o, prop, not visible)
            key_prop(o, prop, frame, 'constant', ctx=ctx)


# ----------------------------------------------------------------------------------------- make_particle_morph ---

_INPUTS = (('From', 'NodeSocketInt', 'int', 'from_idx'), ('To', 'NodeSocketInt', 'int', 'to_idx'),
           ('Morph', 'NodeSocketFloat', 'float', 'morph'), ('Turb', 'NodeSocketFloat', 'float', 'turb'),
           ('Turb Auto', 'NodeSocketBool', 'bool', 'turb_auto'),
           ('Spin', 'NodeSocketFloat', 'float', 'spin'), ('Vortex', 'NodeSocketFloat', 'float', 'vortex'),
           ('Center', 'NodeSocketVector', 'vec3', 'center'),
           ('Curl Scale', 'NodeSocketFloat', 'float', 'curl_scale'),
           ('Curl Strength', 'NodeSocketFloat', 'float', 'curl_strength'),
           ('Size', 'NodeSocketFloat', 'float', 'size'), ('Opacity', 'NodeSocketFloat', 'float', 'opacity'),
           ('Color', 'NodeSocketColor', 'color', 'color'), ('Color2', 'NodeSocketColor', 'color', 'color2'),
           ('Own Color', 'NodeSocketFloat', 'float', 'own_color'), ('Gain', 'NodeSocketFloat', 'float', 'gain'),
           ('Stagger', 'NodeSocketFloat', 'float', 'stagger'),
           ('Stagger Axis', 'NodeSocketVector', 'vec3', 'stagger_axis'),
           ('Stagger Lo', 'NodeSocketFloat', 'float', 'stagger_lo'),
           ('Stagger Hi', 'NodeSocketFloat', 'float', 'stagger_hi'),
           ('Points Only', 'NodeSocketBool', 'bool', 'points_only'))

_STAGGER_AXES = {'up': (0, 0, 1), 'down': (0, 0, -1), 'left': (-1, 0, 0), 'right': (1, 0, 0), 'front': (0, -1, 0),
                 'back': (0, 1, 0), 'random': (0, 0, 0)}


def join_objects(b, objs):
    """Geometry Nodes: the objects' evaluated geometry (Object Info, relative to the cloud) joined IN THIS ORDER, so a
    live binding's vertex offsets hold. A multi-input socket lists (and joins) its links newest first in Blender 5.2,
    so they are linked in reverse; the listed order is checked either way."""
    join = b.node('GeometryNodeJoinGeometry')
    infos = {}
    for o in objs:
        oi = b.node('GeometryNodeObjectInfo', transform_space='RELATIVE')
        oi.inputs['Object'].default_value = o
        infos[o.name] = oi
    for order in (list(reversed(objs)), list(objs)):
        for lk in list(join.inputs[0].links):
            b.links.remove(lk)
        for o in order:
            b.links.new(infos[o.name].outputs['Geometry'], join.inputs[0])
        listed = [lk.from_node.inputs['Object'].default_value for lk in join.inputs[0].links]
        if [o.name for o in listed] == [o.name for o in objs]:
            return join.outputs[0]
    raise RuntimeError('[particle_morph] cannot order the Join Geometry inputs for a live binding')


class ParticleMorphSystem:
    """What make_particle_morph returns, the engine's { mesh, material, morph, update, count, setTargets,
    updateTarget, uniforms }:

        object / mesh         the cloud object (points + the 'particle_morph' Geometry Nodes modifier)
        material, modifier, node_group, count, targets (Target each, count long)
        morph(from_idx, to_idx, t01, turb=None, frame=None, ctx=None)          the engine's per-frame call
        update_target(idx, pts) · set_targets(list) · update()
        key_morph(from, to, start, end, ease, turb, vortex, spin) · key_sequence(steps) · key_hold(idx, frame)
        key_fade(start, end, a, b) · key(name, frame, value) · set_stagger(amount, by)
        uniforms              morph, turb, spin, vortex, size, opacity, color, color2 (the engine's), and turb_auto,
                              curl_scale, curl_strength, from_idx, to_idx, own_color, gain, stagger, stagger_axis,
                              stagger_lo, stagger_hi, points_only: keyable (.value, .key(frame))
    """

    def __init__(self, scene, name, count, map, blending, camera, time_offset, values, render, lit, realize,
                 shadows):
        self.scene, self.name, self.count = scene, name, int(count)
        self.targets = []
        self.map, self.blending, self.camera, self.time_offset = map, blending, camera, time_offset
        self.render, self.lit, self.realize, self.shadows = render, lit, realize, shadows
        self._seed_attr = None
        self._values = values
        self.object = self.mesh = None
        self.material = self.modifier = self.node_group = None
        self.uniforms = Uniforms()
        self._cur = (0, 1)

    # ------------------------------------------------------------------------------------------- the engine's API
    def morph(self, from_idx, to_idx, t01, turb=None, frame=None, ctx=None):
        """The scene-driven morph: segment (from_idx -> to_idx), factor t01 (clamped to 0..1), turbulence (default
        sin(pi t01), as the engine: computed in the graph, exact between frames too). With frame (or a harness ctx)
        the values are keyed there: the segment CONSTANT, the factor and turbulence LINEAR."""
        m = max(0.0, min(1.0, float(t01)))
        u = self.uniforms
        n = max(len(self.targets), 2)              # the graph holds at least two (a single target is doubled)
        # the engine copies a buffer only `if (targets[idx])`: an index with no target keeps the slot's current one
        if not 0 <= int(from_idx) < n or not 0 <= int(to_idx) < n:
            print(f'[particle_morph] morph({from_idx}, {to_idx}): {n} targets; a missing one keeps its slot as it is')
        from_idx = int(from_idx) if 0 <= int(from_idx) < n else self._cur[0]
        to_idx = int(to_idx) if 0 <= int(to_idx) < n else self._cur[1]
        u.from_idx.value, u.to_idx.value = int(from_idx), int(to_idx)
        u.morph.value = m
        if turb is None:
            u.turb.value, u.turb_auto.value = 1.0, True
        else:
            u.turb.value, u.turb_auto.value = float(turb), False
        self._cur = (int(from_idx), int(to_idx))
        if frame is not None or ctx is not None:
            f = frame if frame is not None else ctx.scene.frame_current
            for k in ('from_idx', 'to_idx', 'turb_auto'):
                key_prop(u[k].owner, u[k].prop, f, 'constant', ctx=ctx)
            for k in ('morph', 'turb'):
                key_prop(u[k].owner, u[k].prop, f, 'linear', ctx=ctx)

    def update_target(self, idx, pts, random=None):
        """Swap one target (resampled to count): any target spec, a from_mesh snapshot (the engine's live-pose capture
        at the dissolve frame) or a live Target. idx may be one past the last target (adds one). The .blend keeps one
        set of points per target index for the whole film: to change a target mid-film, add it as a new index and
        key the segment to it."""
        rnd = random if random is not None else JSRandom(self._values['seed'] + 7919 * (idx + 1))
        t = self._resolve(pts, rnd)
        if idx == len(self.targets):
            self.targets.append(t)
        else:
            self.targets[idx] = t
        self._write_targets()
        self._build_graph()

    def set_targets(self, arr, random=None):
        """Replace every target (each resampled to count)."""
        rnd = random if random is not None else JSRandom(self._values['seed'] + 104729)
        self.targets = [self._resolve(t, rnd) for t in arr]
        self._write_targets()
        self._build_graph()

    def update(self, t=None):
        """The engine's per-frame billboard update. Nothing to do: the graph reads the camera itself every frame;
        kept so scripts written against the engine run unchanged."""
        return None

    # ----------------------------------------------------------------------------------------------- keyed timing
    def key(self, name, frame, value=None, ease='linear', ctx=None):
        """Key one uniform at frame (to `value` if given): m.key('opacity', 40, 0.0)."""
        u = self.uniforms[name]
        if value is not None:
            u.value = value
        e = 'constant' if u.kind in ('int', 'bool') else ease
        return key_prop(u.owner, u.prop, frame, e, ctx=ctx)

    def key_hold(self, idx, frame):
        """Hold target idx from frame on: From = To = idx, Morph 0, Turb 0 (crisp)."""
        u = self.uniforms
        u.from_idx.value = u.to_idx.value = int(idx)
        u.morph.value, u.turb.value, u.turb_auto.value = 0.0, 0.0, False
        for k in ('from_idx', 'to_idx', 'morph', 'turb', 'turb_auto'):
            key_prop(u[k].owner, u[k].prop, frame, 'constant')

    def key_morph(self, from_idx, to_idx, start, end, ease='linear', turb=None, turb_auto=None, vortex=None,
                  spin=None):
        """Key one transition from target from_idx to to_idx over frames start..end: the segment switches at start
        (CONSTANT), Morph runs 0 -> 1 with `ease` (on top of the engine's own smoothstep; 'linear' = the engine's
        motion), then holds at 1. turb: None = the engine's default (sin(pi m), computed in the graph), a number = a
        fixed turbulence (the engine's morph(a, b, m, turb)); turb_auto=True with a number scales the default
        (0.55 sin(pi m), the films' usual). vortex: a number for the segment (0 = none). spin: (a0, a1) radians over
        the segment, or a number held."""
        u = self.uniforms
        start, end = float(start), float(end)
        u.from_idx.value, u.to_idx.value = int(from_idx), int(to_idx)
        key_prop(u.from_idx.owner, u.from_idx.prop, start, 'constant')
        key_prop(u.to_idx.owner, u.to_idx.prop, start, 'constant')
        if turb is None:
            amp, auto = 1.0, True
        else:
            amp, auto = float(turb), bool(turb_auto)
        u.turb.value, u.turb_auto.value = amp, auto
        key_prop(u.turb.owner, u.turb.prop, start, 'constant')
        key_prop(u.turb_auto.owner, u.turb_auto.prop, start, 'constant')
        u.morph.value = 0.0
        key_prop(u.morph.owner, u.morph.prop, start, ease)
        u.morph.value = 1.0
        key_prop(u.morph.owner, u.morph.prop, end, 'constant')
        if vortex is not None:
            u.vortex.value = float(vortex)
            key_prop(u.vortex.owner, u.vortex.prop, start, 'constant')
        if spin is not None:
            if isinstance(spin, (tuple, list)):
                u.spin.value = float(spin[0])
                key_prop(u.spin.owner, u.spin.prop, start, ease)
                u.spin.value = float(spin[1])
                key_prop(u.spin.owner, u.spin.prop, end, 'constant')
            else:
                u.spin.value = float(spin)
                key_prop(u.spin.owner, u.spin.prop, start, 'constant')
        self._cur = (int(from_idx), int(to_idx))

    def key_sequence(self, steps, ease='linear', turb=None, vortex=0.0, start_target=0, first_frame=None):
        """Key a chain of transitions. steps: [(to_idx, start, end), (to_idx, start, end, {opts}), ...] or dicts
        {to, start, end, from?, ease?, turb?, turb_auto?, vortex?, spin?}; each goes from the previous step's target
        (start_target first). Defaults for every step: ease, turb, vortex. first_frame: also key a hold of
        start_target there."""
        cur = int(start_target)
        if first_frame is not None:
            self.key_hold(cur, first_frame)
        for s in steps:
            if isinstance(s, dict):
                d = dict(s)
            else:
                d = dict(to=s[0], start=s[1], end=s[2])
                if len(s) > 3:
                    d.update(s[3])
            frm = int(d.pop('from', cur))
            to = int(d.pop('to'))
            self.key_morph(frm, to, d.pop('start'), d.pop('end'), ease=d.pop('ease', ease),
                           turb=d.pop('turb', turb), turb_auto=d.pop('turb_auto', None),
                           vortex=d.pop('vortex', vortex), spin=d.pop('spin', None))
            if d:
                raise ValueError(f'[particle_morph] key_sequence: unknown step options {sorted(d)}')
            cur = to

    def key_fade(self, start, end, a=0.0, b=1.0, ease='linear', name='opacity'):
        """Key a uniform (opacity by default) from a at start to b at end."""
        u = self.uniforms[name]
        u.value = a
        key_prop(u.owner, u.prop, start, ease)
        u.value = b
        key_prop(u.owner, u.prop, end, 'linear')

    def set_stagger(self, amount, by='random'):
        """Particles leave and land in turn: each one's own morph runs over (1 - amount) of the transition, delayed by
        up to `amount`. by: 'random' (the per-particle phase), 'down' (head first: a top-down dissolve), 'up', 'left',
        'right', 'front', 'back', or a direction vector. The order is measured on the FROM target's points."""
        u = self.uniforms
        axis = np.asarray(_STAGGER_AXES[by] if isinstance(by, str) else by, np.float64)
        u.stagger.value = float(amount)
        u.stagger_axis.value = tuple(axis)
        if np.linalg.norm(axis) > 0:
            proj = np.concatenate([t.current_points().astype(np.float64) @ axis for t in self.targets])
            u.stagger_lo.value, u.stagger_hi.value = float(proj.min()), float(proj.max())

    # ------------------------------------------------------------------------------------------------- building
    def _resolve(self, t, rnd):
        if isinstance(t, Target):                     # always resampled, as the engine (same count: unchanged)
            return t.resample(self.count, rnd)
        if isinstance(t, (np.ndarray, list)) and not (isinstance(t, list) and t and not isinstance(t[0], (
                int, float, list, tuple, np.ndarray))):
            return PT.as_target(t).resample(self.count, rnd)
        return PT.target(t, self.count, random=rnd, seed=self._values['seed'], **self._values.get('target_opts', {}))

    def _build_object(self):
        import bpy
        me = bpy.data.meshes.new(self.name)
        me.vertices.add(self.count)
        if self.targets:
            me.vertices.foreach_set('co', np.asarray(self.targets[0].points, dtype=np.float32).ravel())
        at = me.attributes.new('iSeed', 'FLOAT_VECTOR', 'POINT')
        at.data.foreach_set('vector', self._seed_attr.astype(np.float32).ravel())
        ob = bpy.data.objects.new(self.name, me)
        (self._values.get('collection') or self.scene.collection).objects.link(ob)
        if self._values.get('parent') is not None:
            ob.parent = self._values['parent']             # the engine's scene: a group: targets in its frame
        ob.visible_shadow = bool(self.shadows)
        # the engine's userData flags, as the harness audits read them
        for flag in ('no_support_check', 'no_clipping_check', 'no_camera_collide', 'no_z_fight_check'):
            ob[flag] = True
        self.object = self.mesh = ob
        self._write_targets()

    def _write_targets(self):
        me = self.object.data
        for nm in [a.name for a in me.attributes if a.name.startswith(('target_', 'live_', 'tcol_'))]:
            me.attributes.remove(me.attributes[nm])
        for k, t in enumerate(self.targets):
            if t.live is not None:
                lb = t.live
                for nm, arr in ((f'live_i_{k}', lb.idx.astype(np.float32)), (f'live_w_{k}', lb.w),
                                (f'live_j_{k}', lb.jitter)):
                    a = me.attributes.new(nm, 'FLOAT_VECTOR', 'POINT')
                    a.data.foreach_set('vector', np.asarray(arr, dtype=np.float32).ravel())
            else:
                a = me.attributes.new(f'target_{k}', 'FLOAT_VECTOR', 'POINT')
                a.data.foreach_set('vector', np.asarray(t.points, dtype=np.float32).ravel())
            if t.colors is not None:
                a = me.attributes.new(f'tcol_{k}', 'FLOAT_COLOR', 'POINT')
                rgba = np.ones((len(t.colors), 4), np.float32)
                rgba[:, :3] = t.colors
                a.data.foreach_set('color', rgba.ravel())
        me.update()

    def _build_graph(self):
        """The engine's positionNode as Geometry Nodes (Blender axes; the curl in three's, as the source)."""
        from ._nodes import Builder, new_group
        old = self.node_group
        keep = {}
        if self.modifier is not None and old is not None:                  # a rebuild keeps the inputs' values
            for nm, _st, _k, _u in _INPUTS:
                try:
                    v = input_slot(self.modifier, old, nm).value
                except (KeyError, AttributeError):
                    continue
                keep[nm] = tuple(v) if hasattr(v, '__len__') else v
        tree, gi, go = new_group(self.name + '.morph', 'GeometryNodeTree',
                                 [('Geometry', 'NodeSocketGeometry')] + [(n, s) for n, s, _k, _u in _INPUTS],
                                 [('Geometry', 'NodeSocketGeometry')])
        items = tree.interface.items_tree
        V = self._values
        defaults = {'From': 0, 'To': 1, 'Morph': 0.0, 'Turb': 0.0, 'Turb Auto': False, 'Spin': 0.0, 'Vortex': 0.0,
                    'Center': tuple(V.get('center', (0.0, 0.0, 0.0))),
                    'Curl Scale': V['curl_scale'], 'Curl Strength': V['curl_strength'], 'Size': V['size'],
                    'Opacity': V['opacity'], 'Color': (*V['color'], 1.0), 'Color2': (*V['color2'], 1.0),
                    'Own Color': V['own_color'], 'Gain': V['gain'], 'Stagger': 0.0, 'Stagger Axis': (0.0, 0.0, 0.0),
                    'Stagger Lo': 0.0, 'Stagger Hi': 1.0, 'Points Only': False}
        for nm, val in defaults.items():
            items[nm].default_value = val
        b = Builder(tree)
        L = tree.links

        def named(nm, dt='FLOAT_VECTOR'):
            n_ = b.node('GeometryNodeInputNamedAttribute', data_type=dt)
            n_.inputs['Name'].default_value = nm
            return n_.outputs['Attribute']

        # the targets: static points, or a live binding sampled at this frame (+ its jitter and matrix)
        sources, csources = [], []
        joined = {}
        for k, t in enumerate(self.targets):
            if t.live is not None:
                lb = t.live
                key = tuple(o.name for o in lb.objects)
                if key not in joined:
                    joined[key] = join_objects(b, lb.objects)
                geo_live = joined[key]
                ii, ww = b.vec(named(f'live_i_{k}')), b.vec(named(f'live_w_{k}'))
                i3, w3 = ii.xyz(), ww.xyz()
                acc = None
                for c in range(3):
                    si = b.node('GeometryNodeSampleIndex', data_type='FLOAT_VECTOR', domain='POINT')
                    L.new(geo_live, si.inputs['Geometry'])
                    L.new(b.node('GeometryNodeInputPosition').outputs[0], si.inputs['Value'])
                    b.link(i3[c], si.inputs['Index'])                  # an exact integer float: no rounding issue
                    term = b.vscale(b.vec(si.outputs[0]), w3[c])
                    acc = term if acc is None else acc + term
                p = acc + b.vec(named(f'live_j_{k}'))
                M = lb.matrix
                if not np.allclose(M, np.eye(4)):
                    p = b.combine(*[b.vmath('DOT_PRODUCT', p, tuple(M[r, :3])) + float(M[r, 3]) for r in range(3)])
                sources.append(p)
            else:
                sources.append(b.vec(named(f'target_{k}')))
            csources.append(b.vec(named(f'tcol_{k}', 'FLOAT_COLOR')) if t.colors is not None else None)
        while len(sources) < 2:
            sources.append(sources[-1] if sources else b.vec((0.0, 0.0, 0.0)))
            csources.append(csources[-1] if csources else None)

        def switch(index_socket, items_, dt='VECTOR'):
            sw = b.node('GeometryNodeIndexSwitch', data_type=dt)
            while len(sw.index_switch_items) < len(items_):
                sw.index_switch_items.new()
            L.new(index_socket, sw.inputs['Index'])
            for k, src in enumerate(items_):
                b.link(src, sw.inputs[k + 1])
            return b.vec(sw.outputs[0])

        frm, to = switch(gi.outputs['From'], sources), switch(gi.outputs['To'], sources)
        s = b.vec(named('iSeed'))
        phase, size_var, turb_scale = s.xyz()
        m = b.s(gi.outputs['Morph'])
        # stagger (off by default: mi = m, the engine's single factor)
        stag = b.s(gi.outputs['Stagger'])
        axis = b.vec(gi.outputs['Stagger Axis'])
        has_axis = b.math('GREATER_THAN', b.vmath('LENGTH', axis), 1e-6)
        lo, hi = b.s(gi.outputs['Stagger Lo']), b.s(gi.outputs['Stagger Hi'])
        k_axis = b.clamp((b.vmath('DOT_PRODUCT', frm, axis) - lo) / b.max(hi - lo, 1e-6))
        korder = phase + (k_axis - phase) * has_axis
        mi = b.clamp((m - stag * korder) / b.max(1.0 - stag, 1e-4))
        me_ = b.smoothstep(0.0, 1.0, mi)
        ccx, ccy, _ccz = b.vec(gi.outputs['Center']).xyz()                # the turn's axis (the engine's: origin)
        x0, y0, z0 = (frm + (to - frm) * me_).xyz()
        x0, y0 = x0 - ccx, y0 - ccy
        spin = b.s(gi.outputs['Spin'])
        ca, sa = b.cos(spin), b.sin(spin)
        # three's R_y(spin) is Blender's R_z(spin): X' = X c - Y s, Y' = X s + Y c
        bx, by = x0 * ca - y0 * sa, x0 * sa + y0 * ca
        sin_m = b.sin(mi * _PI)
        venv = b.s(gi.outputs['Vortex']) * sin_m * (phase * 0.8 + 0.6)
        cv, sv = b.cos(venv), b.sin(venv)
        vx, vy, vz = bx * cv - by * sv + ccx, bx * sv + by * cv + ccy, z0
        auto = b.s(gi.outputs['Turb Auto'])
        amp = b.s(gi.outputs['Turb']) * (1.0 + (sin_m - 1.0) * auto)
        env = amp * sin_m
        t = scene_clock(b, self.scene, self.time_offset)
        cs = b.s(gi.outputs['Curl Scale'])
        T = t * 0.35 + phase * 12.0
        # p = baseV * curlScale + T in three's axes: three (x, y, z) = Blender (x, z, -y)
        px, py, pz = vx * cs + T, vz * cs + T, (-vy) * cs + T
        d3x = b.sin(py) - b.cos(pz)
        d3y = b.sin(pz) - b.cos(px)
        d3z = b.sin(px) - b.cos(py)
        k = env * b.s(gi.outputs['Curl Strength']) * turb_scale
        cx, cy, cz = vx + d3x * k, vy - d3z * k, vz + d3y * k            # disp back to Blender: (x, -z, y)
        setp = b.node('GeometryNodeSetPosition')
        L.new(gi.outputs['Geometry'], setp.inputs['Geometry'])
        b.link(b.combine(cx, cy, cz), setp.inputs['Position'])
        geo = setp.outputs[0]
        sz = b.max(0.003, b.s(gi.outputs['Size']) * size_var)
        tw = 0.7 + b.sin(t * 5.0 + phase * 40.0) * 0.3
        col = b.vec(gi.outputs['Color'])
        col = col + (b.vec(gi.outputs['Color2']) - col) * m                # the engine's colour (raw morph)
        if any(c is not None for c in csources):
            own = b.s(gi.outputs['Own Color'])
            eff = [col if c is None else col + (c - col) * own for c in csources]
            cf, ct = switch(gi.outputs['From'], eff, 'RGBA'), switch(gi.outputs['To'], eff, 'RGBA')
            col = cf + (ct - cf) * mi
        col = b.vscale(col, b.s(gi.outputs['Gain']))
        geo = store_point(b, geo, 'p_size', sz)
        geo = store_point(b, geo, 'p_alpha', b.s(gi.outputs['Opacity']) * tw)
        geo = store_point(b, geo, 'p_color', col, 'FLOAT_COLOR')
        if self.render == 'points':
            m2p = b.node('GeometryNodeMeshToPoints')
            L.new(geo, m2p.inputs['Mesh'])
            b.link(sz * 0.5, m2p.inputs['Radius'])
            setm = b.node('GeometryNodeSetMaterial')
            L.new(m2p.outputs[0], setm.inputs['Geometry'])
            setm.inputs['Material'].default_value = self.material
            inst = setm.outputs[0]
        elif self.render == 'sphere':
            ico = b.node('GeometryNodeMeshIcoSphere')
            ico.inputs['Radius'].default_value = 0.5
            ico.inputs['Subdivisions'].default_value = int(self._values.get('sphere_subdiv', 1))
            setm = b.node('GeometryNodeSetMaterial')
            L.new(ico.outputs['Mesh'], setm.inputs['Geometry'])
            setm.inputs['Material'].default_value = self.material
            inst = b.node('GeometryNodeInstanceOnPoints')
            L.new(geo, inst.inputs['Points'])
            L.new(setm.outputs[0], inst.inputs['Instance'])
            b.link(b.combine(sz, sz, sz), inst.inputs['Scale'])
            inst = inst.outputs[0]
        else:
            quad = sprite_quad(b, self.material)
            from .particles import instance_sprites
            inst = instance_sprites(b, geo, quad, camera_rotation(b, self.camera), sz)
        if self.realize and self.render != 'points':
            rl = b.node('GeometryNodeRealizeInstances')
            L.new(inst, rl.inputs[0])
            inst = rl.outputs[0]
        swg = b.node('GeometryNodeSwitch', input_type='GEOMETRY')
        L.new(gi.outputs['Points Only'], swg.inputs['Switch'])
        L.new(inst, swg.inputs['False'])
        L.new(geo, swg.inputs['True'])
        L.new(swg.outputs[0], go.inputs['Geometry'])
        if self.modifier is None:
            self.modifier = self.object.modifiers.new('particle_morph', 'NODES')
        self.modifier.node_group = tree           # (new_group removed the old graph: it had the same name)
        self.node_group = tree
        for nm, v in keep.items():
            set_modifier_input(self.modifier, tree, nm, v)
        self.uniforms.clear()
        for nm, _st, kind, un in _INPUTS:
            self.uniforms[un] = modifier_uniform(self.object, self.modifier, tree, nm, kind, un)
        self.object.update_tag()

    def _attr(self, b, name, out='Fac'):
        """Shader nodes: a value the graph stored on the points (instance attributes on instanced sprites and
        spheres; geometry attributes on realized meshes and point clouds)."""
        kind = 'GEOMETRY' if (self.realize or self.render == 'points') else 'INSTANCER'
        n = b.node('ShaderNodeAttribute', attribute_name=name, attribute_type=kind)
        return b.s(n.outputs[out]) if out == 'Fac' else b.vec(n.outputs[out])

    def _build_material(self):
        import bpy
        from ._nodes import Builder
        additive = self.blending != 'normal'
        mat, nt, out = new_sprite_material(bpy, self.name + '_sprite', additive)
        b = Builder(nt)
        c = self._attr(b, 'p_color', 'Color')
        a = self._attr(b, 'p_alpha')
        if self.render == 'billboard':
            uvn = b.node('ShaderNodeUVMap')
            uvn.uv_map = 'UVMap'
            ux, uy, _ = b.vec(uvn.outputs['UV']).xyz()
            dx, dy = ux - 0.5, uy - 0.5
            a = a * b.smoothstep(0.5, 0.0, b.sqrt(dx * dx + dy * dy))       # the soft radial dot
            img = sprite_image(self.map)
            if img is not None:
                tex = b.node('ShaderNodeTexImage')
                tex.image = img
                b.link(b.vec(uvn.outputs['UV']), tex.inputs['Vector'])
                c = b.vmath('MULTIPLY', c, b.vec(tex.outputs['Color']))
                a = a * b.s(tex.outputs['Alpha'])
        elif additive:
            lw = b.node('ShaderNodeLayerWeight')
            lw.inputs['Blend'].default_value = 0.5
            facing = b.s(lw.outputs['Facing'])
            a = a * b.pow(b.max(1.0 - facing, 0.0), 1.5)                     # a glowing bead: bright centre, soft rim
        if self.lit and not additive:
            pr = b.node('ShaderNodeBsdfPrincipled')
            b.link(c, pr.inputs['Base Color'])
            pr.inputs['Roughness'].default_value = 0.45
            tr = b.node('ShaderNodeBsdfTransparent')
            mix = b.node('ShaderNodeMixShader')
            b.link(a, mix.inputs['Fac'])
            nt.links.new(tr.outputs[0], mix.inputs[1])
            nt.links.new(pr.outputs[0], mix.inputs[2])
            nt.links.new(mix.outputs[0], out.inputs['Surface'])
        else:
            finish_sprite_material(bpy, mat, nt, b, out, c, a, additive)
        self.object.data.materials.append(mat)
        self.material = mat


def make_particle_morph(scene=None, camera=None, count=40000, targets=(), map=None, color=None, color2=None, size=None,
                        opacity=None, blending='additive', curl=None, name='particle_morph', seed=1, random=None,
                        time_offset=0.0, opts=None, render='billboard', own_colors=True, gain=1.0, align=None,
                        align_frame=None, pairing='index', stagger=0.0, stagger_by='random', live=None, lit=False,
                        realize=False, shadows=False, sphere_subdiv=1, target_opts=None, center=None,
                        collection=None, parent=None):
    """The engine's makeParticleMorph in Blender, and the one call for morph-target particles to anything.

    targets: two or more of anything particle_targets.target takes: the engine's generators' points, any (m, 3)
    array, a Target (from_object / from_file / from_image / shapes ... live or not), a Blender Object, Collection or
    VRMHandle, a bpy image, 'text:HELLO', 'ascii:<art>', 'banner:HI', 'neural_net', 'neuron_graph', a shape name
    ('galaxy', 'sphere', 'ring', ...), a file path, 'polyhaven:<id>', 'vrm:<name>', or (spec, {options}). Each is
    resampled to count. live=True samples Objects / VRMs given directly as live bindings (target_opts: options for
    every spec, e.g. {'mode': 'surface'}).

    The engine's options: color (default 0x66ccff) shifts to color2 across a morph (default: color when color is
    given, else 0xff66cc); size 0.014 (quad side, times 0.7..1.4 per particle; 0.03-0.05 for a camera 5 m+ away);
    opacity 1; blending 'additive' (glowing light) or 'normal'; curl {'scale': 1.3, 'strength': 0.5}; map: a sprite
    (library name, path or image) multiplied into the soft dot. camera: the quads face it; None faces the scene's
    active camera at every frame. opts: the engine's options as one dict (merged under the keywords).

    The Blender edition's: own_colors (targets with colours of their own, sampled from their materials, show them;
    a number 0..1 blends toward color/color2) · gain (emission multiplier) · render 'billboard' | 'sphere' |
    'points' · lit (sphere/points with 'normal' blending: a Principled bead the scene lights) · realize (one mesh, not
    instances: for motion blur) · align 'centroid' (static targets onto the first's centroid at align_frame) or a
    point · pairing 'index' | 'height' | 'space' | 'random' · stagger 0..0.9 with stagger_by 'random' | 'down' |
    'up' | ... · shadows (cast them) · center: the vertical axis spin and vortex turn about (None: the world origin,
    as the engine; 'auto': the first target's centroid; or a point) · seed · collection (link the cloud there, not
    the scene's master collection) · parent (an object the cloud moves with: the engine's scene: a group; static
    targets are then read in its frame, live ones stay on their objects). -> ParticleMorphSystem: drive it with
    morph(from_idx, to_idx, t01, turb, frame=f) per frame, or key_morph / key_sequence for whole eased
    transitions."""
    import bpy
    if opts:
        o = dict(opts)
        o.update({k: v for k, v in dict(scene=scene, camera=camera, map=map, color=color, color2=color2, size=size,
                                         opacity=opacity, curl=curl).items() if v is not None})
        scene, camera, map = o.get('scene'), o.get('camera'), o.get('map')
        color, color2, size, opacity, curl = o.get('color'), o.get('color2'), o.get('size'), o.get('opacity'), \
            o.get('curl')
        count = o.get('count', count)
        targets = o.get('targets', targets)
        blending = o.get('blending', blending)
        name = o.get('name', name)
    if render not in ('billboard', 'sphere', 'points'):
        raise ValueError(f"[particle_morph] render {render!r}: 'billboard', 'sphere' or 'points'")
    scene, collection, parent = scene_or_group(scene, collection, parent)
    sc = scene or bpy.context.scene
    count = _count(count, 40000)
    rnd = _stream(random, seed)
    curl = curl or {}
    targets = list(targets or [])
    if len(targets) < 2:
        print('[particle_morph] need >=2 targets')
    c1 = color if color is not None else 0x66ccff
    c2 = color2 if color2 is not None else (color if color is not None else 0xff66cc)
    tops = dict(target_opts or {})
    if live is not None:
        tops.setdefault('live', bool(live))
    values = dict(seed=int(seed), size=float(size) if size is not None else 0.014,
                  opacity=float(opacity) if opacity is not None else 1.0,
                  curl_scale=float(curl.get('scale', 1.3) if curl.get('scale') is not None else 1.3),
                  curl_strength=float(curl.get('strength', 0.5) if curl.get('strength') is not None else 0.5),
                  color=linear_color(c1) if not isinstance(c1, (tuple, list)) else tuple(c1)[:3],
                  color2=linear_color(c2) if not isinstance(c2, (tuple, list)) else tuple(c2)[:3],
                  own_color=float(own_colors) if not isinstance(own_colors, bool) else (1.0 if own_colors else 0.0),
                  gain=float(gain), target_opts=tops, sphere_subdiv=int(sphere_subdiv), collection=collection,
                  parent=parent)
    sys_ = ParticleMorphSystem(sc, name, count, map, blending, camera, time_offset, values, render, lit, realize,
                               shadows)
    sys_.targets = [sys_._resolve(t, rnd) for t in targets]            # the engine resamples every target first,
    r = rnd.take(3 * count).reshape(count, 3)                           # then draws the seeds
    sys_._seed_attr = np.stack([r[:, 0], 0.7 + r[:, 1] * (1.4 - 0.7), 0.6 + r[:, 2] * (1.6 - 0.6)], 1)  # JS rand(a, b)
    if align is not None and sys_.targets:
        if isinstance(align, str):
            if align != 'centroid':
                raise ValueError(f"[particle_morph] align {align!r}: 'centroid' or a point")
            sys_.targets = PT.match_centroids(sys_.targets, 0, frame=align_frame)
        else:
            sys_.targets = PT.match_centroids(sys_.targets, point=align)
    if pairing != 'index':
        sys_.targets = [PT.pair(t, pairing, seed=seed) for t in sys_.targets]
    if center is not None:
        c = sys_.targets[0].centroid(align_frame) if (isinstance(center, str) and sys_.targets) else center
        values['center'] = tuple(float(x) for x in np.asarray(c, np.float64).reshape(3))
    sys_._build_object()
    sys_._build_material()
    sys_._build_graph()
    sys_.morph(0, 1, 0.0, 0.0)
    if stagger:
        sys_.set_stagger(stagger, stagger_by)
    return sys_

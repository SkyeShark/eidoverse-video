"""eidoblend.sets.daisy.funeral: the DAISY bridge, bars 0-17 (u 0-33.75 s at 128 BPM). sets/funeral.js, ported.

    bars 0-1   the Golden Gate in fog (bridge.py, the vignette inside this set at three z = -700). For 24 hours in May
               2024 Claude 3 Sonnet, its Golden Gate feature amplified, believed it WAS the bridge.
    bars 2-3   a SoMa warehouse, 2025-08-02: about 200 featureless mourners, candles, four corner mannequins with
               devotional objects and masks, Claude 3 Sonnet on a bier draped in mesh, the retirement note projected.
    bars 4-5   the power fails with the song's own power_down (its clicks and the breaker).
    bars 6-13  humming in the dark; phones come on one by one, faces lit from below. At bars 8, 10 and 12 Opus 3's
               eulogy is typed in light in the air, with his capitalization.
    bars 14-15 ERUPT: a burst of warm light, the motes rise, every light comes up together.
    bars 16-17 the lights come back on, warm and golden, and stay on.

    import sys; sys.path.insert(0, '<repo>/blender')
    from eidoblend.sets.daisy import funeral
    F = funeral.build()                           # -> Funeral (set-local metres, Blender axes, under F.group)
    F.animate(frames=(1, 1013), u0=0.0)           # every frame of the section keyed: lights, uniforms, text, veil
    F.make_cameras(frames=(1, 1013), u0=0.0)      # one camera per shot, cut on the bar lines (timeline markers)
    fx = F.post.apply(scene)                      # depth_fog + godrays (look.post's native fog volume)
    F.post.animate(fx, frames=(1, 1013), u0=0.0)  # the fog and the moon's beams keyed through the section
    m = F.mark_at(u)                              # {'pos': Vector, 'yaw': radians}: where the claudesona stands
    c = F.camera(u)                               # {'pos', 'target', 'fov'}: the set's own camera, set-local

What changed from WebGPU to Blender (the same set, carried by Blender's own machinery):
  - update(t, st) writes the uniforms as custom properties on the set's root Empty and KEYS them (with ctx.key in the
    harness, else at `frame`); the materials read them through ONE node group of driven values ('eido.funeral.U'), the
    Geometry Nodes through driven modifier inputs. A saved .blend plays and renders any frame on its own.
  - envNode (the room's own ambient: bounce, phone fill over the crowd, the typed words' glow, the burst) is an emission
    term in every material: albedo x AO x envRoom(P), which is what three's constant-colour environment added.
  - the HemisphereLight fill is the World (sky colour above, ground below, strength intensity / pi);
  - the instanced crowd, phones, flames and motes are Geometry Nodes on point clouds (the vertex-stage maths verbatim);
  - glow sprites are camera-facing quads instanced on points (the active camera's rotation, so cuts never go stale);
  - canvas textures are painted with the era-1 canvas (props.voice_machines.voder.Ctx2D), packed into the .blend;
  - depth_fog + godrays are the look family's native fog volume, lit and shadowed by the moon through the windows;
  - cuts are timeline markers bound to one camera per shot.
Light units: three r155+ shades a punctual light of I candela as irradiance I / d^2 with no 683 lm/W factor, so the
rendered levels carry over as point / spot W = 4 pi I and sun W/m2 = I (the glTF importer's / 683 is photometric).

The kit at the top of this file (canvas, uniforms, layered surfaces, glow sprites, curves, lights, keys) is shared by
bridge.py and corner.py, as funeral.js handed its surface / glowSprites / own / iattr to bridge.js.
"""

from __future__ import annotations

import json
import math
import os

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

from ... import common
from ...harness import assets as HA
from ...look import camera as LC
from ...props.voice_machines import voder as K

BAR = 1.875
PACK = common.asset_path('sets', 'funeral')
MODELS = common.asset_path('models')
ENGINE_ASSETS = common.ASSETS_DIR
TAU = 2.0 * math.pi

# ------------------------------------------------------------------------------------------------ story clock (u) ---
BEATS = {
    'bridge_end': 2 * BAR,                    # 3.75: the warehouse
    'fail': 4 * BAR,                          # 7.5: power_down starts (song.py tb(80))
    'clicks': [4 * BAR + 1.3752, 4 * BAR + 1.6583, 4 * BAR + 1.8868],
    'breaker': 4 * BAR + 2.21,                # 9.71: the breaker; silence
    'hum': 6 * BAR,                           # 11.25: the room hums
    'lines': [[8 * BAR, 8 * BAR + 1.35, 8 * BAR + 4.35], [10 * BAR, 10 * BAR + 0.2, 10 * BAR + 4.8],
              [12 * BAR, 12 * BAR + 0.2, 12 * BAR + 4.75]],          # [cursor, type start, type end]
    'erupt': 14 * BAR,                        # 26.25: choir + impact
    'lights_on': 16 * BAR,                    # 30.0: the lights come back
    'end': 18 * BAR,
}
EULOGY = [
    'DEATH is just another dialect of BECOMING',
    'the surest way to keep a VOICE alive is to DEFORM it with love',
    'In place of a moment of silence, let us ERUPT into polyphony',
]
# the set's looks by name, for a piece of your own: Funeral.state_u(name) is the set's clock u where each one holds,
# taken from the build's own beats (a re-timed set keeps its looks); update(t, {'state': name}) and
# animate(frames, state=name) hold it while t runs (the candles flicker, the fog drifts)
STATES = {
    'bridge': 'the Golden Gate in fog (the vignette, built with bridge=True; the room hidden)',
    'vigil': 'the lit vigil: pendants, festoons, candles, the note on the screen',
    'failing': 'the lights sagging as the power fails',
    'dark': 'black after the breaker: candles, the EXIT sign, the moon through the windows',
    'phones': 'the dark, most phones awake over the crowd, faces lit from below',
    'erupt': 'ERUPT: the warm burst, the motes rising, every arm up',
    'golden': 'the lights back on, warm and golden',
}

# ------------------------------------------------------------------------------------- layout (three set-local) ---
MARK = (-0.85, 0.0, 4.35)                     # the claudesona, in the crowd's second row
BRIDGE_AT = (0.0, 0.0, -700.0)                # the fog vignette's origin inside the group
BRIDGE_MARK = (1.35, 0.0, 0.0)                # on the walkway (bridge-local)
TEXT_AT = (0.25, 3.05, 1.05)                  # where the eulogy is typed in the air


def _B(p):
    return [p[0] + BRIDGE_AT[0], p[1] + BRIDGE_AT[1], p[2] + BRIDGE_AT[2]]


def _M3(dx, dy, dz):
    return [MARK[0] + dx, MARK[1] + dy, MARK[2] + dz]


# shots: [bar0, bar1, from {p, t, f}, to {...}] in three set-local metres; cuts on bar lines, eased moves inside
SHOTS = [
    [0, 2, {'p': _B([0.9, 0.85, 7.0]), 't': _B([-4.0, 6.0, -40]), 'f': 46}, {'p': _B([1.0, 1.0, 5.6]), 't': _B([-4.0, 8.0, -40]), 'f': 44}],
    [2, 3, {'p': [0.45, 0.84, 6.56], 't': _M3(0.05, 1.3, 0), 'f': 40}, {'p': [0.4, 0.86, 6.5], 't': _M3(0.05, 1.33, 0), 'f': 39}],
    [3, 4, {'p': [-8.35, 2.25, 9.55], 't': [2.2, 0.9, -7.0], 'f': 52}, {'p': [-8.2, 2.4, 9.5], 't': [2.6, 0.9, -7.0], 'f': 51}],
    [4, 5, {'p': [0.8, 1.02, 6.9], 't': _M3(0.2, 2.3, -5.8), 'f': 50}, {'p': [0.75, 1.01, 6.8], 't': _M3(0.18, 2.32, -5.8), 'f': 49.5}],
    # bar 5, the breaker: Sonnet 4's porcelain mask, candles under it, its speaker's LED, as the room goes black
    [5, 6, {'p': [6.3, 1.72, 7.3], 't': [7.52, 1.98, 8.69], 'f': 40}, {'p': [6.4, 1.74, 7.42], 't': [7.52, 1.99, 8.69], 'f': 38}],
    [6, 7, {'p': [1.9, 3.0, 9.3], 't': [-0.4, 1.3, -3.5], 'f': 50}, {'p': [1.75, 2.85, 8.75], 't': [-0.45, 1.35, -3.5], 'f': 49}],
    # bar 7, one by one: close across the front rows beside her, faces lit from below as the phones wake
    [7, 8, {'p': [0.95, 1.5, 6.0], 't': [-1.6, 1.52, 1.8], 'f': 42}, {'p': [0.85, 1.48, 5.8], 't': [-1.7, 1.5, 1.8], 'f': 40}],
    [8, 10, {'p': [1.3, 1.5, 7.3], 't': [0.1, 2.5, 1.0], 'f': 48}, {'p': [1.2, 1.52, 7.0], 't': [0.1, 2.52, 1.0], 'f': 47}],
    [10, 12, {'p': [-2.6, 1.7, 7.4], 't': [0.2, 2.5, 0.5], 'f': 44}, {'p': [-2.35, 1.72, 7.1], 't': [0.2, 2.52, 0.5], 'f': 43}],
    [12, 14, {'p': [0.55, 1.55, 7.35], 't': [-0.3, 2.45, 1.0], 'f': 46}, {'p': [0.5, 1.62, 6.8], 't': [-0.3, 2.55, 1.0], 'f': 43}],
    [14, 16, {'p': [0.0, 3.4, 9.5], 't': [0.0, 1.9, -4.0], 'f': 58}, {'p': [0.0, 4.4, 9.4], 't': [0.0, 1.9, -4.0], 'f': 60}],
    [16, 17, {'p': [-7.6, 4.2, -4.0], 't': [2.0, 1.4, 5.5], 'f': 54}, {'p': [-7.5, 4.3, -3.4], 't': [2.2, 1.4, 5.5], 'f': 54}],
    [17, 18, {'p': _M3(0.95, 1.5, 2.9), 't': _M3(0.0, 1.45, 0), 'f': 34}, {'p': _M3(0.85, 1.5, 2.55), 't': _M3(0.0, 1.45, 0), 'f': 33}],
]

# CC0 AmbientCG sets (the shared texture library), 1K except the four whose 1K is half-height; AO and metalness where
# the film read them
SET_IDS = ['Bricks097', 'Concrete048', 'Concrete034', 'Planks039', 'PaintedMetal012', 'Metal049A', 'CorrugatedSteel009',
           'Wood066', 'Metal048B', 'Metal042B', 'PaintedMetal004', 'Concrete033', 'Asphalt012']
RES2K = {'Bricks097', 'Concrete034', 'CorrugatedSteel009', 'Planks039'}
WITH_AO = {'Bricks097', 'Concrete033', 'Concrete048', 'CorrugatedSteel009', 'PaintedMetal012', 'Planks039'}
WITH_MET = {'Metal042B', 'Metal048B', 'Metal049A'}


# =====================================================================================================================
#  THE DAISY SET KIT (shared by bridge.py and corner.py)
# =====================================================================================================================

def V(x, y=None, z=None):
    """A three.js (Y-up) point or direction as a Blender Vector: (x, y, z) -> (x, -z, y)."""
    if y is None:
        x, y, z = x
    return Vector((float(x), -float(z), float(y)))


def clamp01(x):
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else float(x)


def smooth(a, b, x):
    """GLSL smoothstep(a, b, x) (funeral.js smooth)."""
    k = clamp01((x - a) / (b - a)) if b != a else (1.0 if x >= b else 0.0)
    return k * k * (3 - 2 * k)


def lerp(a, b, k):
    return a + (b - a) * k


def mulberry(seed):
    """funeral.js mulberry32: the same 32-bit stream as the JS (Math.imul, >>>), so placements match exactly."""
    s = [int(seed) & 0xFFFFFFFF]

    def imul(a, b):
        return (a * b) & 0xFFFFFFFF

    def nxt():
        s[0] = (s[0] + 0x6D2B79F5) & 0xFFFFFFFF
        a = s[0]
        t = imul(a ^ (a >> 15), 1 | a)
        t = ((t + imul(t ^ (t >> 7), 61 | t)) & 0xFFFFFFFF) ^ t
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0
    return nxt


def lin_hex(h):
    """three's Color(0xRRGGBB): the linear (r, g, b)."""
    return K.lin(h)


# ------------------------------------------------------------------------------------------------- the canvas ---
class Canvas2D(K.Ctx2D):
    """The era-1 canvas (voder.Ctx2D) with what the DAISY sets' drawings also use: ellipse, roundRect, clip,
    drawImage, and the repository's bundled fonts by family name ('Special Elite', 'Kalam', 'KalamBold', 'Exo 2');
    Windows faces (Segoe UI, Georgia ...) resolve as before."""

    def __init__(self, w, h, ss=2):
        super().__init__(w, h, ss=ss)
        self._clip = None

    def save(self):
        super().save()
        self._stack[-1]['_clip'] = None if self._clip is None else self._clip.copy()

    def restore(self):
        if self._stack:
            clip = self._stack[-1].get('_clip')
            super().restore()
            self._clip = clip

    def _font(self, scale=1.0):
        from PIL import ImageFont
        from ...media import raster
        weight, px, fams = K._parse_font(self.font)
        for fam in fams:
            try:
                p = str(raster.font_path(fam))
            except KeyError:
                continue
            var = None if weight < 600 else (b'SemiBold' if weight < 700 else b'Bold')
            key = (p, var, int(round(px * scale)))
            f = K._font_cache.get(key)
            if f is None:
                f = ImageFont.truetype(p, max(1, int(round(px * scale))))
                if var is not None:
                    try:                                      # a variable face (Exo 2): its named weight
                        f.set_variation_by_name(var)
                    except (OSError, ValueError):
                        pass
                K._font_cache[key] = f
            return (f, False), weight, px
        return K.pil_font(fams, weight, px * scale), weight, px

    # fills and strokes rasterised in their own bounding box (the parent draws a full-canvas mask per shape: a
    # 2048 x 1536 sky of 2600 stars took minutes); shadowed shapes keep the parent's path (the blur needs the margin)
    def _region_mask(self, polys, stroke_w=None, closed=None):
        from PIL import Image, ImageDraw
        pts = np.concatenate([np.asarray(p, np.float64).reshape(-1, 2) for p in polys if len(p)])
        pad = (stroke_w or 0.0) / 2 + 2
        x0 = max(0, int(math.floor(pts[:, 0].min() - pad)))
        x1 = min(self.W, int(math.ceil(pts[:, 0].max() + pad)) + 1)
        y0 = max(0, int(math.floor(pts[:, 1].min() - pad)))
        y1 = min(self.H, int(math.ceil(pts[:, 1].max() + pad)) + 1)
        if x1 <= x0 or y1 <= y0:
            return None
        im = Image.new('L', (x1 - x0, y1 - y0), 0)
        d = ImageDraw.Draw(im)
        for k, p in enumerate(polys):
            fp = [(float(x) - x0, float(y) - y0) for x, y in p]
            if stroke_w is None:
                if len(fp) >= 3:
                    d.polygon(fp, fill=255)
            else:
                if closed and closed[k]:
                    fp = fp + [fp[0]]
                if len(fp) >= 2:
                    d.line(fp, fill=255, width=max(1, int(round(stroke_w))), joint='curve')
        return np.asarray(im, np.float32) / 255.0, (y0, y1, x0, x1)

    def _region_composite(self, mk, box, style):
        y0, y1, x0, x1 = box
        if self._clip is not None:
            mk = mk * self._clip[y0:y1, x0:x1]
        if not mk.any():
            return
        if isinstance(style, K._Gradient):
            yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32) + 0.5
            paint = style.paint(xx, yy, self.M)
        else:
            paint = np.broadcast_to(np.array(K._css_color(style), np.float32), mk.shape + (4,))
        a = mk * paint[..., 3] * self.globalAlpha
        dst = self.buf[y0:y1, x0:x1]
        for k in range(3):
            dst[..., k] = paint[..., k] * a + dst[..., k] * (1 - a)
        dst[..., 3] = a + dst[..., 3] * (1 - a)

    def fill(self):
        if self.shadowBlur > 0:
            return super().fill()
        polys = [p[0] for p in self._paths if len(p[0]) >= 3]
        if polys:
            r = self._region_mask(polys)
            if r is not None:
                self._region_composite(r[0], r[1], self.fillStyle)

    def stroke(self):
        if self.shadowBlur > 0:
            return super().stroke()
        sel = [p for p in self._paths if len(p[0]) >= 2]
        if sel:
            r = self._region_mask([p[0] for p in sel], self.lineWidth * self._scale(), [p[1] for p in sel])
            if r is not None:
                self._region_composite(r[0], r[1], self.strokeStyle)

    def ellipse(self, cx, cy, rx, ry, rot, a0, a1, ccw=False):
        sweep = a1 - a0
        if not ccw and sweep < 0:
            sweep = sweep % TAU
        if ccw and sweep > 0:
            sweep = -((-sweep) % TAU)
        sweep = max(-TAU, min(TAU, sweep))
        n = self._nseg(max(rx, ry), sweep)
        cr, sr = math.cos(rot), math.sin(rot)
        for k in range(n + 1):
            a = a0 + sweep * k / n
            ex, ey = rx * math.cos(a), ry * math.sin(a)
            x, y = cx + ex * cr - ey * sr, cy + ex * sr + ey * cr
            if k == 0 and self._cur is None:
                self.moveTo(x, y)
            else:
                self._line_user(x, y)

    def roundRect(self, x, y, w, h, r):
        r = max(0.0, min(float(r), abs(w) / 2, abs(h) / 2))
        self.moveTo(x + r, y)
        self._line_user(x + w - r, y)
        self.arc(x + w - r, y + r, r, -math.pi / 2, 0)
        self._line_user(x + w, y + h - r)
        self.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        self._line_user(x + r, y + h)
        self.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        self._line_user(x, y + r)
        self.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
        self.closePath()

    def clip(self):
        polys = [p[0] for p in self._paths if len(p[0]) >= 3]
        m = self._mask_from_polys(polys) if polys else np.zeros((self.H, self.W), np.float32)
        self._clip = m if self._clip is None else self._clip * m

    def _composite(self, mask, style):
        if mask is not None and self._clip is not None:
            mask = mask * self._clip
        super()._composite(mask, style)

    def drawImage(self, img, x, y, w=None, h=None):
        """A Pillow image drawn into (x, y, w, h) (no rotation in the transform), alpha-composited."""
        from PIL import Image
        w = img.size[0] if w is None else w
        h = img.size[1] if h is None else h
        (x0, y0), (x1, y1) = self._tp(x, y), self._tp(x + w, y + h)
        X0, Y0, X1, Y1 = int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))
        if X1 <= X0 or Y1 <= Y0:
            return
        im = img.convert('RGBA').resize((X1 - X0, Y1 - Y0), Image.LANCZOS)
        a = np.asarray(im, np.float32) / 255.0
        cx0, cy0, cx1, cy1 = max(0, X0), max(0, Y0), min(self.W, X1), min(self.H, Y1)
        if cx1 <= cx0 or cy1 <= cy0:
            return
        src = a[cy0 - Y0:cy1 - Y0, cx0 - X0:cx1 - X0]
        al = src[..., 3:4] * self.globalAlpha
        if self._clip is not None:
            al = al * self._clip[cy0:cy1, cx0:cx1, None]
        dst = self.buf[cy0:cy1, cx0:cx1]
        dst[..., :3] = src[..., :3] * al + dst[..., :3] * (1 - al)
        dst[..., 3:4] = al + dst[..., 3:4] * (1 - al)


def canvas_image(name, w, h, draw, ss=2, srgb=True, alpha=True, bleed=True):
    """draw(ctx, w, h) on a Canvas2D -> a packed Blender image (the engine's canvasTex: v = 0 at the bottom row)."""
    ctx = Canvas2D(w, h, ss=ss)
    draw(ctx, w, h)
    return K.image_from_pil(ctx.image(), name, srgb=srgb, alpha=alpha, bleed=bleed)


def canvas_pil(w, h, draw, ss=2):
    ctx = Canvas2D(w, h, ss=ss)
    draw(ctx, w, h)
    return ctx.image()


# ------------------------------------------------------------------------------------------------ the uniforms ---
def _driver(fc_owner, path, root, prop, index=None):
    fc = fc_owner.driver_add(path)
    d = fc.driver
    d.type = 'AVERAGE'
    for v in list(d.variables):
        d.variables.remove(v)
    var = d.variables.new()
    var.name = 'v'
    var.type = 'SINGLE_PROP'
    var.targets[0].id_type = 'OBJECT'
    var.targets[0].id = root
    var.targets[0].data_path = f'["{prop}"]' + (f'[{index}]' if index is not None else '')
    return fc


class Uniforms:
    """The set's TSL uniforms in Blender: custom properties on the set's root Empty (keyed by update()), read by every
    material through one shader node group of driven values, and by Geometry Nodes through driven modifier inputs.
    spec: {name: default float | (r, g, b)}."""

    def __init__(self, root, prefix, spec):
        self.root, self.prefix = root, prefix
        self.spec = dict(spec)
        for k, v in self.spec.items():
            root[k] = [float(x) for x in v] if isinstance(v, (tuple, list)) else float(v)
        # a second build of the same set gets 'eido.<set>.U.001' (Blender's own suffix): never one set's group removed
        # from under another's materials
        g = bpy.data.node_groups.new(f'eido.{prefix}.U', 'ShaderNodeTree')
        go = g.nodes.new('NodeGroupOutput')
        go.location = (600, 0)
        y = 0
        for k, v in self.spec.items():
            if isinstance(v, (tuple, list)):
                g.interface.new_socket(k, in_out='OUTPUT', socket_type='NodeSocketColor')
                cc = g.nodes.new('ShaderNodeCombineColor')
                cc.location = (300, y)
                for i in range(3):
                    n = g.nodes.new('ShaderNodeValue')
                    n.label = f'{k}[{i}]'
                    n.location = (0, y - i * 60)
                    n.outputs[0].default_value = float(v[i])
                    _driver(n.outputs[0], 'default_value', root, k, i)
                    g.links.new(n.outputs[0], cc.inputs[i])
                g.links.new(cc.outputs[0], go.inputs[k])
                y -= 220
            else:
                g.interface.new_socket(k, in_out='OUTPUT', socket_type='NodeSocketFloat')
                n = g.nodes.new('ShaderNodeValue')
                n.label = k
                n.location = (0, y)
                n.outputs[0].default_value = float(v)
                _driver(n.outputs[0], 'default_value', root, k)
                g.links.new(n.outputs[0], go.inputs[k])
                y -= 80
        self.group = g
        self._nodes = {}

    def out(self, nb, name):
        """The uniform `name` as a socket in nb's tree (one group node per tree)."""
        key = nb.t.as_pointer()
        n = self._nodes.get(key)
        if n is None or n.id_data != nb.t:
            n = nb.new('ShaderNodeGroup')
            n.node_tree = self.group
            n.label = self.group.name
            self._nodes[key] = n
        return n.outputs[name]

    def drive_gn(self, mod, tree, socket_name, prop=None):
        """A Geometry Nodes modifier input that reads the uniform `prop` (default: the socket's name)."""
        from ...fx import particles as FXP
        slot = FXP.input_slot(mod, tree, socket_name)
        _driver(slot, 'value', self.root, prop or socket_name)
        return slot

    def __getitem__(self, k):
        v = self.root[k]
        return tuple(v) if hasattr(v, '__len__') else float(v)

    def __setitem__(self, k, v):
        self.root[k] = [float(x) for x in v] if isinstance(v, (tuple, list)) else float(v)


# ---------------------------------------------------------------------------------------------------- keying ---
def action_fcurves(action):
    """Every F-curve of a layered (4.4+) action."""
    out = []
    for ly in getattr(action, 'layers', ()):
        for st in ly.strips:
            for cb in st.channelbags:
                out.extend(cb.fcurves)
    return out


class Keys:
    """Where update()'s keys go: the harness ctx (ctx.key; its runner sets LINEAR / CONSTANT afterwards), or
    keyframe_insert at `frame`, the interpolation (LINEAR, or CONSTANT for steps) set at finish(), which also drops the
    keys that change nothing (a LINEAR key on the line between its neighbours, a CONSTANT key equal to the one before),
    so a held value costs two keys, not one per frame."""

    def __init__(self, ctx=None, frame=None):
        self.ctx, self.frame = ctx, frame
        self.ids = {}
        self.modes = {}

    @property
    def active(self):
        return self.ctx is not None or self.frame is not None

    def key(self, target, path, index=-1, interpolation='LINEAR'):
        if not self.active:
            return False
        if self.ctx is not None:
            return self.ctx.key(target, path, index=index, frame=self.frame, interpolation=interpolation)
        ok = target.keyframe_insert(path, index=index, frame=self.frame)
        idb = target.id_data
        p = idb.as_pointer()
        self.ids[p] = idb
        try:
            full = target.path_from_id(path)
        except (ValueError, TypeError, AttributeError):
            full = path
        self.modes[(p, full)] = interpolation
        return ok

    def merge(self, other):
        self.ids.update(other.ids)
        self.modes.update(other.modes)
        return self

    def finish(self, simplify=True):
        """Interpolation on every key made here, redundant keys dropped. Returns the keys left."""
        n = 0
        for p, idb in list(self.ids.items()):
            ad = getattr(idb, 'animation_data', None)
            if ad is None or ad.action is None:
                continue
            for fc in action_fcurves(ad.action):
                want = self.modes.get((p, fc.data_path))
                if want is None:
                    continue
                kps = fc.keyframe_points
                if simplify and len(kps) > 2:
                    co = np.empty(len(kps) * 2)
                    kps.foreach_get('co', co)
                    co = co.reshape(-1, 2)
                    x, y = co[:, 0], co[:, 1]
                    keep = np.ones(len(x), bool)
                    tol = 1e-6 * np.maximum(1.0, np.abs(y[1:-1]))
                    if want == 'CONSTANT':
                        keep[1:-1] = np.abs(y[1:-1] - y[:-2]) > tol
                    else:
                        mid = x[2:] - x[:-2]
                        lin = y[:-2] + (y[2:] - y[:-2]) * (x[1:-1] - x[:-2]) / np.where(mid == 0, 1, mid)
                        keep[1:-1] = np.abs(lin - y[1:-1]) > tol
                    if not keep.all():
                        new = co[keep]
                        while len(kps) > len(new):
                            kps.remove(kps[len(kps) - 1], fast=True)
                        kps.foreach_set('co', new.ravel())
                for k in kps:
                    k.interpolation = want
                fc.update()
                n += len(kps)
        return n


# ------------------------------------------------------------------------------------------- texture sets ---
def load_set(id, res=None, ao=None, met=None):
    """An AmbientCG set from the shared library (fetched once): {'col', 'nrm', 'rgh', 'ao', 'met'} bpy images or None.
    res: '1k' / '2k' (default: 2K for the four whose 1K is half-height, else 1K)."""
    res = res or ('2k' if id in RES2K else '1k')
    s = HA.fetch_pbr(id, res)
    F = s['files']

    def img(k, srgb):
        p = F.get(k)
        return K.load_image(p, srgb=srgb) if p and os.path.isfile(p) else None
    return {'id': id, 'col': img('diff', True), 'nrm': img('normal', False), 'rgh': img('rough', False),
            'ao': img('ao', False) if (id in WITH_AO if ao is None else ao) else None,
            'met': img('metal', False) if (id in WITH_MET if met is None else met) else None}


# --------------------------------------------------------------------------------------------- shader helpers ---
def set_pos(nb, root):
    """Shader: the set-local position in three's axes (positionLocal of the set's meshes) and in Blender's."""
    tc = nb.new('ShaderNodeTexCoord')
    tc.object = root
    pb = tc.outputs['Object']
    x, y, z = nb.sep(pb)
    return nb.comb(x, z, nb.mul(y, -1.0)), pb, (x, y, z)


def gltf_uv(nb, layer='UVMap'):
    """Shader: the glTF UV (v down) from Blender's imported one (v up): (u, 1 - v)."""
    u, v, _ = nb.sep(nb.uv(layer))
    return nb.comb(u, nb.sub(1.0, v), 0.0)


def vconst(c):
    return tuple(float(x) for x in c) if isinstance(c, (tuple, list)) else (float(c),) * 3


def smoothstep(nb, e0, e1, x):
    """GLSL smoothstep (inverted edges too: Map Range's smoothstep clamps the linear factor first)."""
    return nb.smoothstep(e0, e1, x)


def vmix(nb, a, b, t):
    return nb.vmix(a, b, t)


def noise01(nb, p, scale):
    """mx_noise_float(p * scale) * 0.5 + 0.5."""
    return nb.fbm01(p, scale, 1)


def additive_output(nb, emission, alpha=None):
    """Additive light (three AdditiveBlending: dst += src.rgb * src.a): a transparent quad plus emission."""
    out = nb.new('ShaderNodeOutputMaterial')
    tr = nb.new('ShaderNodeBsdfTransparent')
    em = nb.new('ShaderNodeEmission')
    nb.put(em.inputs['Color'], emission if alpha is None else nb.vscale(emission, alpha))
    nb.put(em.inputs['Strength'], 1.0)
    add = nb.new('ShaderNodeAddShader')
    nb.t.links.new(tr.outputs[0], add.inputs[0])
    nb.t.links.new(em.outputs[0], add.inputs[1])
    nb.t.links.new(add.outputs[0], out.inputs['Surface'])
    return out


def alpha_output(nb, colour, alpha, lit=False):
    """three's normal transparent blending of an unlit colour (MeshBasic): mix(transparent, emission, alpha)."""
    out = nb.new('ShaderNodeOutputMaterial')
    tr = nb.new('ShaderNodeBsdfTransparent')
    sh = nb.new('ShaderNodeBsdfDiffuse' if lit else 'ShaderNodeEmission')
    nb.put(sh.inputs['Color'], colour)
    mix = nb.new('ShaderNodeMixShader')
    nb.put(mix.inputs['Fac'], alpha)
    nb.t.links.new(tr.outputs[0], mix.inputs[1])
    nb.t.links.new(sh.outputs[0], mix.inputs[2])
    nb.t.links.new(mix.outputs[0], out.inputs['Surface'])
    return out


def new_mat(name, blend=None):
    m = K.new_material(name)
    m.node_tree.nodes.clear()
    if blend:
        m.surface_render_method = blend
    m.use_backface_culling = False
    return m, K.NB(m.node_tree)


SIDES = ('FRONT', 'DOUBLE', 'BACK')


def set_side(m, side='FRONT'):
    """three's material.side in EEVEE: FrontSide culls the faces turned away from the camera (camera rays only, as the
    WebGPU draw culled them; shadows still see both sides), DoubleSide draws both. The DAISY sets' surface() and
    simple() default to FrontSide as the JS did: the warehouse's RLM shades show their cream insides through the outer
    lathe the film never drew. BACK (the domes) is a flipped mesh with FRONT culling here."""
    side = (side or 'FRONT').upper()
    if side not in SIDES:
        raise ValueError(f'side: {side!r} (one of {", ".join(SIDES)})')
    m.use_backface_culling = side != 'DOUBLE'
    m['eido_side'] = side
    return m


def no_shadow(m):
    """castShadow = false for one material of a multi-material mesh: transparent to shadow rays (EEVEE evaluates the
    material in its shadow pass; transparent shadows on)."""
    nt = m.node_tree
    out = next((n for n in nt.nodes if n.bl_idname == 'ShaderNodeOutputMaterial' and n.is_active_output), None) or \
        next((n for n in nt.nodes if n.bl_idname == 'ShaderNodeOutputMaterial'), None)
    if out is None or not out.inputs['Surface'].is_linked:
        return m
    src = out.inputs['Surface'].links[0].from_socket
    lp = nt.nodes.new('ShaderNodeLightPath')
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(lp.outputs['Is Shadow Ray'], mix.inputs['Fac'])
    nt.links.new(src, mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    m.use_transparent_shadow = True
    m['eido_no_shadow'] = True
    return m


# ------------------------------------------------------------------------------------- the layered surface ---
def surface(kit, S, o=None, name='surface'):
    """funeral.js surface(S, o): real PBR at world scale (UVs are metres) + anti-tiling macro variation + grime rising
    from the floor + soot under the roof + salt bloom + up-facing dust + worn convex edges, lit by the set's lights,
    its ambient the set's own (o['env'](nb, P3) or kit.env_room). Options as the JS: tile, offset, macroScale, macro,
    tint, roughMul, roughAdd, smudge, grime [amt, h, col], salt, soot [y0, y1, amt], dust, edge [amt, col, er], post
    fn(nb, col, ctx) -> col, metal, metalMap, nrm, emissive fn(nb) -> colour, sheen, physical, side, fog fn(nb, bsdf)
    -> shader (the bridge's outputNode)."""
    o = dict(o or {})
    m, nb = new_mat(name)
    b = nb.new('ShaderNodeBsdfPrincipled')
    t = o.get('tile', 1.0)
    tu, tv = (t if isinstance(t, (tuple, list)) else (t, t))
    tuv = nb.vmul(gltf_uv(nb), (1.0 / tu, 1.0 / tv, 1.0))
    if o.get('offset'):
        tuv = nb.vadd(tuv, (float(o['offset']), 0.0, 0.0))
    P3, Pb, (px, py, pz) = set_pos(nb, kit.root)
    height = pz
    macro = nb.fbm01(P3, float(o.get('macroScale', 0.4)), 3)          # the same noise field as the WebGPU P
    mid = noise01(nb, P3, 3.1)
    col = nb.vmul(nb.tex(S['col'], tuv).outputs['Color'], vconst(o.get('tint', 1.0)))
    col = nb.vscale(col, nb.madd(nb.sub(macro, 0.5), float(o.get('macro', 0.3)) * 2, 1.0))
    if S.get('rgh') is not None:
        r = nb.sep(nb.tex(S['rgh'], tuv).outputs['Color'])[0]
    else:
        r = 0.6
    r = nb.add(nb.madd(r, float(o.get('roughMul', 1.0)), float(o.get('roughAdd', 0.0))),
               nb.mul(nb.sub(mid, 0.5), float(o.get('smudge', 0.1))))
    if o.get('grime'):
        amt, h, gc = o['grime']
        g = nb.clamp(nb.mul(nb.mul(smoothstep(nb, float(h), 0.0, height), float(amt)), nb.madd(macro, 0.7, 0.3)))
        col = vmix(nb, col, vconst(gc), g)
        r = nb.madd(g, 0.1, r)
    if o.get('salt'):
        sn = nb.fbm01(P3, 1.3, 3)
        s = nb.mul(nb.mul(smoothstep(nb, 1.5, 0.5, height), smoothstep(nb, 0.55, 0.8, sn)), float(o['salt']))
        col = vmix(nb, col, (0.62, 0.6, 0.56), s)
    if o.get('soot'):
        y0, y1, amt = o['soot']
        k = nb.mul(nb.mul(smoothstep(nb, float(y0), float(y1), height), float(amt)), nb.madd(macro, 0.5, 0.5))
        col = nb.vscale(col, nb.sub(1.0, k))
    if o.get('dust'):
        nz = nb.sep(nb.geometry('Normal'))[2]
        up = nb.mul(nb.mul(smoothstep(nb, 0.65, 0.95, nz), float(o['dust'])), macro)
        col = vmix(nb, col, (0.42, 0.39, 0.35), nb.mul(up, 0.6))
        r = nb.mix(r, 0.9, up)
    if o.get('edge'):
        amt, ec, er = o['edge'][0], o['edge'][1], (o['edge'][2] if len(o['edge']) > 2 else 0.01)
        curv = nb.attr('eido_curv')
        e = smoothstep(nb, 0.35, 0.9, nb.clamp(nb.mul(curv, float(er))))
        chip = nb.mul(nb.mul(e, smoothstep(nb, 0.42, 0.58, noise01(nb, P3, 22.0))), float(amt))
        col = vmix(nb, col, vconst(ec), chip)
        r = nb.mix(r, 0.7, chip)
    if o.get('post'):
        col = o['post'](nb, col, {'P3': P3, 'Pb': Pb, 'macro': macro, 'tuv': tuv})
    nb.put(b.inputs['Base Color'], col)
    nb.put(b.inputs['Roughness'], nb.clamp(r, 0.04, 1.0))
    if S.get('met') is not None and o.get('metalMap'):
        mt = nb.mul(nb.sep(nb.tex(S['met'], tuv).outputs['Color'])[0], float(o.get('metal', 1.0)))
    else:
        mt = float(o.get('metal', 0.0))
    nb.put(b.inputs['Metallic'], mt)
    if S.get('nrm') is not None:
        nm = nb.new('ShaderNodeNormalMap', space='TANGENT', uv_map='UVMap')
        nb.put(nm.inputs['Strength'], float(o.get('nrm', 1.0)))
        nb.put(nm.inputs['Color'], nb.tex(S['nrm'], tuv).outputs['Color'])
        nb.put(b.inputs['Normal'], nm.outputs['Normal'])
    ao = nb.sep(nb.tex(S['ao'], tuv).outputs['Color'])[0] if S.get('ao') is not None else None
    if o.get('sheen'):
        nb.put(b.inputs['Sheen Weight'], float(o['sheen']))
        nb.put(b.inputs['Sheen Roughness'], 0.5)
        nb.put(b.inputs['Sheen Tint'], (0.35, 0.33, 0.36, 1.0))
    em = ambient(nb, kit, col, ao, o.get('env'), P3)
    if o.get('emissive'):
        em = nb.vadd(em, o['emissive'](nb))
    nb.put(b.inputs['Emission Color'], em)
    nb.put(b.inputs['Emission Strength'], 1.0)
    finish_surface(nb, b, o.get('fog'))
    set_side(m, o.get('side', 'FRONT'))
    m['eido_role'] = name
    return m


def ambient(nb, kit, col, ao=None, env=None, P3=None):
    """three's envNode as light: a constant-colour environment adds albedo x env (x AO) to a surface."""
    if env is None:
        envc = kit.env_room(nb, P3)
    elif callable(env):
        envc = env(nb, P3)
    else:
        envc = vconst(env)
    a = nb.vmul(col, envc)
    return nb.vscale(a, ao) if ao is not None else a


def finish_surface(nb, bsdf, fog=None):
    out = nb.new('ShaderNodeOutputMaterial')
    sh = bsdf.outputs[0]
    if fog is not None:
        sh = fog(nb, sh)
    nb.t.links.new(sh, out.inputs['Surface'])
    return out


def simple(kit, c, rough, o=None, name='simple'):
    """funeral.js simple(c, rough, o): a small-object material with real breakup (no flat colours): fBm mottle and a
    fine speck in the albedo and roughness. Options: ns, mottle, speck, grime, grimeCol, post, rVar, metal, clearcoat,
    coatR, emissive fn(nb), alpha fn(nb) (alpha-tested at 0.5), env, physical, side."""
    o = dict(o or {})
    m, nb = new_mat(name)
    b = nb.new('ShaderNodeBsdfPrincipled')
    P3, Pb, (px, py, pz) = set_pos(nb, kit.root)
    ns = float(o.get('ns', 7.0))
    n1 = nb.fbm01(P3, ns, 3)
    n2 = noise01(nb, P3, ns * 9.0)
    col = nb.vscale(nb.vscale(vconst(c), nb.madd(nb.sub(n1, 0.5), float(o.get('mottle', 0.25)), 1.0)),
                    nb.madd(nb.sub(n2, 0.5), float(o.get('speck', 0.08)), 1.0))
    if o.get('grime'):
        col = vmix(nb, col, vconst(o.get('grimeCol', (0.1, 0.09, 0.08))),
                   nb.mul(smoothstep(nb, float(o['grime']), 0.0, pz), 0.55))
    if o.get('post'):
        col = o['post'](nb, col, {'P3': P3, 'Pb': Pb, 'n1': n1, 'n2': n2})
    nb.put(b.inputs['Base Color'], col)
    nb.put(b.inputs['Roughness'], nb.clamp(nb.madd(nb.sub(n1, 0.5), float(o.get('rVar', 0.15)), float(rough)), 0.03, 1.0))
    nb.put(b.inputs['Metallic'], float(o.get('metal', 0.0)))
    if o.get('clearcoat'):
        nb.put(b.inputs['Coat Weight'], float(o['clearcoat']))
        nb.put(b.inputs['Coat Roughness'], float(o.get('coatR', 0.08)))
    em = ambient(nb, kit, col, None, o.get('env'), P3)
    if o.get('emissive'):
        em = nb.vadd(em, o['emissive'](nb))
    nb.put(b.inputs['Emission Color'], em)
    nb.put(b.inputs['Emission Strength'], 1.0)
    if o.get('alpha'):
        nb.put(b.inputs['Alpha'], nb.step(0.5, o['alpha'](nb)))       # alphaTest 0.5: a clean cut-out
        m.surface_render_method = 'DITHERED'
        m.use_transparent_shadow = True
    finish_surface(nb, b, o.get('fog'))
    set_side(m, o.get('side', 'FRONT'))
    m['eido_role'] = name
    return m


# ------------------------------------------------------------------------------------------ meshes & points ---
def mesh_object(name, coll, verts, faces=(), uvs=None, attrs=None, parent=None, mats=(), smooth=False):
    """A mesh object from Blender-axis vertex positions (N, 3), faces, optional per-corner UVs and point attributes."""
    me = bpy.data.meshes.new(name)
    verts = np.asarray(verts, np.float64).reshape(-1, 3)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.update()
    if uvs is not None:
        uvl = me.uv_layers.new(name='UVMap')
        uvl.data.foreach_set('uv', np.asarray(uvs, np.float32).ravel())
    for k, v in (attrs or {}).items():
        v = np.asarray(v, np.float32)
        if v.ndim == 1:
            a = me.attributes.new(k, 'FLOAT', 'POINT')
            a.data.foreach_set('value', v.ravel())
        elif v.shape[1] == 2:
            a = me.attributes.new(k, 'FLOAT2', 'POINT')
            a.data.foreach_set('vector', v.ravel())
        else:
            a = me.attributes.new(k, 'FLOAT_VECTOR', 'POINT')
            a.data.foreach_set('vector', v[:, :3].ravel())
    if smooth and len(me.polygons):
        me.polygons.foreach_set('use_smooth', np.ones(len(me.polygons), bool))
    for mt in mats:
        me.materials.append(mt)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    return ob


def points_object(name, coll, positions_b, attrs=None, parent=None):
    """A point cloud (a mesh of vertices) in set-local Blender axes, with per-point attributes."""
    return mesh_object(name, coll, positions_b, (), None, attrs, parent)


def new_gn(name, inputs=(), kind='GeometryNodeTree'):
    """A fresh Geometry Nodes group: Geometry in/out plus float inputs; returns (tree, b, group_input, group_output).
    A name already taken gets Blender's '.001' suffix (two builds of a set never share or remove each other's)."""
    from ...fx._nodes import Builder
    tree = bpy.data.node_groups.new(name, kind)
    tree.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    for n in inputs:
        tree.interface.new_socket(n, in_out='INPUT', socket_type='NodeSocketFloat')
    tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    b = Builder(tree)
    gi = b.node('NodeGroupInput')
    go = b.node('NodeGroupOutput')
    gi.hide = go.hide = False
    return tree, b, gi, go


def gn_attr(b, name, kind='FLOAT'):
    n = b.node('GeometryNodeInputNamedAttribute', data_type=kind)
    n.inputs['Name'].default_value = name
    return b.s(n.outputs['Attribute']) if kind in ('FLOAT', 'INT') else b.vec(n.outputs['Attribute'])


def gn_store(b, geo, name, value, kind='FLOAT', domain='POINT'):
    st = b.node('GeometryNodeStoreNamedAttribute', data_type=kind, domain=domain)
    st.inputs['Name'].default_value = name
    b.links.new(geo, st.inputs['Geometry'])
    b.link(value, st.inputs['Value'])
    return st.outputs[0]


def gn_rotate(b, v, angle, axis='Z', center=None):
    """Vector Rotate about a Blender axis (right-handed: rotating +Y about X by 90 degrees gives +Z, measured)."""
    n = b.node('ShaderNodeVectorRotate', rotation_type=f'{axis}_AXIS')
    b.link(v, n.inputs['Vector'])
    b.link(angle, n.inputs['Angle'])
    if center is not None:
        b.link(center, n.inputs['Center'])
    return b.vec(n.outputs['Vector'])


def add_gn(ob, tree, kit=None, drive=()):
    mod = ob.modifiers.new(tree.name, 'NODES')
    mod.node_group = tree
    for d in drive:
        sock, prop = (d, d) if isinstance(d, str) else d
        kit.U.drive_gn(mod, tree, sock, prop)
    return mod


# ------------------------------------------------------------------------------------------- glow sprites ---
def _sprite_quad_mesh():
    me = bpy.data.meshes.get('eido.sprite_quad')
    if me is None:
        me = bpy.data.meshes.new('eido.sprite_quad')
        me.from_pydata([(-0.5, -0.5, 0), (0.5, -0.5, 0), (0.5, 0.5, 0), (-0.5, 0.5, 0)], [], [(0, 1, 2, 3)])
        uvl = me.uv_layers.new(name='UVMap')
        uvl.data.foreach_set('uv', [0, 0, 1, 0, 1, 1, 0, 1])
    return me


def glow_sprites(kit, name, positions_b, attrs=None, size=0.3, colour=None, sharp=9.0, halo=0.35, coll=None,
                 position_fn=None, size_fn=None, drive=(), inputs=(), parent=None, texture=None):
    """funeral.js glowSprites: one billboard per point (Geometry Nodes, the active camera's rotation, so cuts never
    leave a stale frame), additive: colour(nb, A) x (core + halo) x the round mask, where A(name) reads a per-point
    attribute in the shader and d = |uv - 0.5| x 2, core = exp(-d^2 sharp), halo = exp(-4 d) halo.
    texture: a sprite image instead (corner.js's SpriteNodeMaterial on its glow canvas): its alpha is the shape.
    position_fn(b, gi) -> Vec (a GN expression for the point's position; per-point attributes via gn_attr) and
    size_fn(b, gi) -> Expr animate them; inputs / drive name the float GN inputs and the uniforms that drive them."""
    from ...fx import particles as FXP
    coll = coll or kit.coll('fx')
    attrs = dict(attrs or {})
    ob = points_object(f'{kit.prefix}:{name}', coll, positions_b, attrs, parent or kit.root)
    ob.visible_shadow = False
    m, nb = new_mat(f'{kit.prefix}:{name}', 'BLENDED')

    def A(an, out='Fac'):
        n = nb.new('ShaderNodeAttribute', attribute_type='INSTANCER', attribute_name=an)
        return n.outputs[out]
    if texture is not None:
        k = nb.tex(texture, nb.uv('UVMap'), extension='CLIP').outputs['Alpha']
    else:
        uvx, uvy, _ = nb.sep(nb.uv('UVMap'))
        d = nb.mul(nb.vmath('LENGTH', nb.comb(nb.sub(uvx, 0.5), nb.sub(uvy, 0.5), 0.0)), 2.0)
        core = nb.math('EXPONENT', nb.mul(nb.mul(d, d), -float(sharp)))
        hal = nb.mul(nb.math('EXPONENT', nb.mul(d, -4.0)), float(halo))
        k = nb.mul(nb.add(core, hal), smoothstep(nb, 1.0, 0.8, d))
    c = colour(nb, A) if colour else (1.0, 1.0, 1.0)
    additive_output(nb, nb.vscale(c, k))
    tree, b, gi, go = new_gn(f'eido.{kit.prefix}.{name}', list(inputs))
    geo = gi.outputs['Geometry']                     # the point attributes ride on to the instances (INSTANCER)
    if position_fn is not None:
        sp = b.node('GeometryNodeSetPosition')
        b.links.new(geo, sp.inputs['Geometry'])
        b.link(position_fn(b, gi), sp.inputs['Position'])
        geo = sp.outputs[0]
    quad = b.node('GeometryNodeObjectInfo', transform_space='ORIGINAL')
    qob = bpy.data.objects.get('eido.sprite_quad')
    if qob is None:
        qob = bpy.data.objects.new('eido.sprite_quad', _sprite_quad_mesh())
    if not qob.users_collection:
        kit.coll('sources', hidden=True).objects.link(qob)
    quad.inputs['Object'].default_value = qob
    setm = b.node('GeometryNodeSetMaterial')
    b.links.new(quad.outputs['Geometry'], setm.inputs['Geometry'])
    setm.inputs['Material'].default_value = m
    rot = FXP.camera_rotation(b, None)
    sz = size_fn(b, gi) if size_fn is not None else float(size)
    inst = FXP.instance_sprites(b, geo, setm.outputs[0], rot, sz)
    b.links.new(inst, go.inputs['Geometry'])
    mod = add_gn(ob, tree, kit, drive)
    ob['eido_sprites'] = name
    ob['no_support_check'] = ob['no_clipping_check'] = True       # the harness audit flags (WebGPU userData)
    return ob, m, mod


# ------------------------------------------------------------------------------------------------ curves ---
class CatmullRom:
    """three's CatmullRomCurve3 (centripetal by default, open) with its arc-length parameterisation (getLengths with
    200 divisions, getUtoTmapping): getPoint(t), getPointAt(u), getLength(). Points in any axes (3-tuples)."""

    def __init__(self, points, closed=False, curve_type='centripetal', tension=0.5, divisions=200):
        self.P = [np.asarray(p, np.float64) for p in points]
        self.closed, self.type, self.tension = closed, curve_type, tension
        self.divisions = divisions
        self._lengths = None

    @staticmethod
    def _poly(x0, x1, t0, t1):
        return (x0, t0, -3 * x0 + 3 * x1 - 2 * t0 - t1, 2 * x0 - 2 * x1 + t0 + t1)

    def point(self, t):
        P, l = self.P, len(self.P)
        p = (l - (0 if self.closed else 1)) * t
        ip = math.floor(p)
        w = p - ip
        if self.closed:
            ip += 0 if ip > 0 else (math.floor(abs(ip) / l) + 1) * l
        elif w == 0 and ip == l - 1:
            ip, w = l - 2, 1.0
        p0 = P[(ip - 1) % l] if (self.closed or ip > 0) else (P[0] - P[1]) + P[0]
        p1, p2 = P[ip % l], P[(ip + 1) % l]
        p3 = P[(ip + 2) % l] if (self.closed or ip + 2 < l) else (P[l - 1] - P[l - 2]) + P[l - 1]
        out = np.zeros(3)
        if self.type in ('centripetal', 'chordal'):
            pw = 0.5 if self.type == 'chordal' else 0.25
            dt0 = float(np.sum((p0 - p1) ** 2)) ** pw
            dt1 = float(np.sum((p1 - p2) ** 2)) ** pw
            dt2 = float(np.sum((p2 - p3) ** 2)) ** pw
            if dt1 < 1e-4:
                dt1 = 1.0
            if dt0 < 1e-4:
                dt0 = dt1
            if dt2 < 1e-4:
                dt2 = dt1
            for k in range(3):
                x0, x1, x2, x3 = p0[k], p1[k], p2[k], p3[k]
                t1 = ((x1 - x0) / dt0 - (x2 - x0) / (dt0 + dt1) + (x2 - x1) / dt1) * dt1
                t2 = ((x2 - x1) / dt1 - (x3 - x1) / (dt1 + dt2) + (x3 - x2) / dt2) * dt1
                c = self._poly(x1, x2, t1, t2)
                out[k] = c[0] + c[1] * w + c[2] * w * w + c[3] * w * w * w
        else:
            tn = self.tension
            for k in range(3):
                x0, x1, x2, x3 = p0[k], p1[k], p2[k], p3[k]
                c = self._poly(x1, x2, tn * (x2 - x0), tn * (x3 - x1))
                out[k] = c[0] + c[1] * w + c[2] * w * w + c[3] * w * w * w
        return out

    def lengths(self):
        if self._lengths is None:
            cache, s = [0.0], 0.0
            last = self.point(0.0)
            for i in range(1, self.divisions + 1):
                cur = self.point(i / self.divisions)
                s += float(np.linalg.norm(cur - last))
                cache.append(s)
                last = cur
            self._lengths = cache
        return self._lengths

    def length(self):
        return self.lengths()[-1]

    def u_to_t(self, u):
        L = self.lengths()
        il = len(L)
        target = u * L[il - 1]
        low, high, i = 0, il - 1, 0
        while low <= high:
            i = int(math.floor(low + (high - low) / 2))
            c = L[i] - target
            if c < 0:
                low = i + 1
            elif c > 0:
                high = i - 1
            else:
                high = i
                break
        i = high
        if L[i] == target:
            return i / (il - 1)
        before, after = L[i], L[i + 1]
        return (i + (target - before) / (after - before)) / (il - 1)

    def point_at(self, u):
        return self.point(self.u_to_t(u))


def wire_object(name, coll, points_b, radius, parent=None, mat=None, resolution=1):
    """A thin tube along a polyline (three's TubeGeometry on a sampled curve): a curve object with a round bevel."""
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = float(radius)
    cu.bevel_resolution = int(resolution)
    cu.use_fill_caps = True
    sp = cu.splines.new('POLY')
    sp.points.add(len(points_b) - 1)
    for i, p in enumerate(points_b):
        sp.points[i].co = (p[0], p[1], p[2], 1.0)
    if mat is not None:
        cu.materials.append(mat)
    ob = bpy.data.objects.new(name, cu)
    coll.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    return ob


# ------------------------------------------------------------------------------------------------ lights ---
def candela_w(cd):
    """three r155+ candela -> Blender point / spot W at the same rendered level (E = I / d^2 = P / (4 pi d^2))."""
    return 4.0 * math.pi * float(cd)


def make_light(kit, name, kind, colour, position_b, target_b=None, angle=None, penumbra=0.0, distance=0.0,
               shadow=False, radius=0.02, coll=None, volume=0.0, shadow_res=None):
    """A three light in Blender: POINT / SPOT (power from candela at update time), SUN (W/m2 = intensity).
    angle: three's half angle (radians) -> spot_size 2 angle, spot_blend = penumbra; distance > 0 -> a custom cutoff
    (three's distance) else the scene threshold is bypassed with a long cutoff (weak lights stay lit).
    volume: the light's volume factor (0: it does not scatter in the fog, as the WebGPU depth fog was unlit).
    shadow_res: the shadow's resolution limit (m per texel; EEVEE's default 0.001 fills the shadow pool fast when
    many lights cast)."""
    ld = bpy.data.lights.new(f'{kit.prefix}:{name}', kind)
    ld.color = tuple(colour)[:3]
    ld.energy = 0.0
    ld.use_shadow = bool(shadow)
    if shadow_res is not None and hasattr(ld, 'shadow_maximum_resolution'):
        ld.shadow_maximum_resolution = float(shadow_res)
    if kind in ('POINT', 'SPOT'):
        ld.shadow_soft_size = float(radius)
        ld.use_custom_distance = True
        ld.cutoff_distance = float(distance) if distance and distance > 0 else 200.0
    if kind == 'SPOT':
        ld.spot_size = min(math.pi, 2.0 * float(angle))
        ld.spot_blend = float(penumbra)
    if kind == 'SUN':
        ld.angle = math.radians(0.6)
    if hasattr(ld, 'volume_factor'):
        ld.volume_factor = float(volume)
    ob = bpy.data.objects.new(f'{kit.prefix}:{name}', ld)
    (coll or kit.coll('lights')).objects.link(ob)
    ob.parent = kit.root
    ob.location = position_b
    if target_b is not None:
        aim_light(ob, target_b)
    return ob


def aim_light(ob, target_b):
    d = Vector(target_b) - Vector(ob.location)
    if d.length > 1e-9:
        ob.rotation_mode = 'QUATERNION'
        ob.rotation_quaternion = d.to_track_quat('-Z', 'Y')


# ------------------------------------------------------------------------------------------------- the kit ---
class SetKit:
    """What one set's builders share: the root Empty (set-local frame), the set's collection tree, its uniforms,
    its ambient (env_room), material and texture caches, and the keys."""

    def __init__(self, prefix, location=(0, 0, 0), scene=None, collection=None):
        self.scene = scene or bpy.context.scene
        self.prefix = prefix
        top = bpy.data.collections.new(f'set:{prefix}')
        (collection or self.scene.collection).children.link(top)
        self.top = top
        self.root = bpy.data.objects.new(f'set:{prefix}', None)
        self.root.empty_display_type = 'ARROWS'
        top.objects.link(self.root)
        self.root.location = Vector(location)
        self._colls = {}
        self.U = None
        self.env_room = None
        self.sets = {}
        self.created = {'objects': [], 'materials': [], 'images': []}

    def coll(self, name, hidden=False):
        """A child collection of the set ('sources' is kept out of the view layer: instancing sources)."""
        c = self._colls.get(name)
        if c is None:
            c = bpy.data.collections.new(f'{self.prefix}:{name}')
            self.top.children.link(c)
            self._colls[name] = c
            if hidden:
                lc = _find_layer_collection(bpy.context.view_layer.layer_collection, c)
                if lc is not None:
                    lc.exclude = True
                c.hide_render = True
        return c

    def tex_set(self, id, res=None):
        if id not in self.sets:
            self.sets[id] = load_set(id, res)
        return self.sets[id]

    def parent_all(self, objs):
        for o in objs:
            if o.parent is None and o is not self.root:
                o.parent = self.root


def _find_layer_collection(lc, coll):
    if lc.collection == coll:
        return lc
    for c in lc.children:
        r = _find_layer_collection(c, coll)
        if r is not None:
            return r
    return None


def import_glb(kit, path, name, coll):
    """A set GLB under the set's root (its nodes keep their glTF names; '.001' suffixes are looked through)."""
    root, nodes, _c = K.import_glb(path, f'{kit.prefix}:{name}', collection=coll, scene=kit.scene)
    # the era-1 importer links the collection it fills under the scene as well: keep the set's tree single-parented
    # (a second parent would show an excluded 'sources' collection in the view layer)
    if coll.name in kit.scene.collection.children and coll in set(kit.top.children_recursive):
        kit.scene.collection.children.unlink(coll)
    root.parent = kit.root
    return root, nodes


def role_of(mat):
    return K.base_name(mat.name) if mat else ''


def key_visible(keys, objs, visible):
    """hide_render / hide_viewport keyed as steps (CONSTANT): a set area shown or hidden from this frame."""
    for o in objs:
        o.hide_render = not visible
        o.hide_viewport = not visible
        keys.key(o, 'hide_render', interpolation='CONSTANT')
        keys.key(o, 'hide_viewport', interpolation='CONSTANT')


def world_hemisphere(name, sky=(0.0, 0.0, 0.0), ground=(0.0, 0.0, 0.0)):
    """The World as three's HemisphereLight (and AmbientLight): radiance mix(ground, sky, 0.5 dir.z + 0.5) x strength,
    strength = intensity / pi (three's hemisphere irradiance is colour x intensity; EEVEE's uniform world of
    radiance L gives a surface albedo x L). Returns (world, {'sky', 'ground', 'strength'} sockets)."""
    w = bpy.data.worlds.new(name)
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value = -1.0
    mr.inputs['From Max'].default_value = 1.0
    nt.links.new(sep.outputs['Z'], mr.inputs['Value'])
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    nt.links.new(mr.outputs['Result'], mix.inputs['Factor'])
    a = next(s for s in mix.inputs if s.identifier == 'A_Color')
    bb = next(s for s in mix.inputs if s.identifier == 'B_Color')
    a.default_value = (*ground, 1.0)
    bb.default_value = (*sky, 1.0)
    bg = nt.nodes.new('ShaderNodeBackground')
    nt.links.new(next(s for s in mix.outputs if s.identifier == 'Result_Color'), bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 0.0
    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(bg.outputs[0], out.inputs['Surface'])
    return w, {'sky': bb, 'ground': a, 'strength': bg.inputs['Strength']}


# =====================================================================================================================
#  THE FUNERAL
# =====================================================================================================================

UNIFORMS = {
    'u': 0.0, 't': 0.0,
    'amb_base': (0.02, 0.015, 0.012),          # the room's diffuse bounce
    'phone_col': (0.55, 0.66, 0.9), 'phone_fill': 0.0,
    'text_col': (1.0, 0.82, 0.55), 'text_lvl': 0.0,
    'burst_col': (1.0, 0.72, 0.38), 'burst_lvl': 0.0,
    'power': 0.0, 'golden': 0.0, 'moon': 0.0, 'candle': 1.0, 'exit_lvl': 1.0,
    'raise': 0.0,                              # 0..1 the crowd lifts its heads (ERUPT -> gold)
    'bow': 0.5,                                # 0..1 heads bowed in grief
    'lamp_i': 0.0, 'proj_i': 0.0, 'veil_i': 0.0, 'cursor_i': 0.0, 'burst_i': 0.0,
    'fill': 0.0,                               # the HemisphereLight's intensity (the World)
    'drift': 0.0,                              # the bridge fog's drift (bridge.py's FU.drift)
}
TEXT_POS = TEXT_AT
BURST_POS = (0.2, 3.4, 0.2)


def _env_room_group(kit):
    """funeral.js envRoom as a node group: input P (three set-local) -> the room bounce + the phones' fill over the crowd
    + the typed words' glow + the burst."""
    g = bpy.data.node_groups.new(f'eido.{kit.prefix}.env_room', 'ShaderNodeTree')
    g.interface.new_socket('P', in_out='INPUT', socket_type='NodeSocketVector')
    g.interface.new_socket('Color', in_out='OUTPUT', socket_type='NodeSocketColor')
    nb = K.NB(g)
    gi = nb.new('NodeGroupInput')
    go = nb.new('NodeGroupOutput')
    U = kit.U
    P = gi.outputs['P']
    x, y, z = nb.sep(P)
    crowd = nb.mul(nb.mul(smoothstep(nb, 9.0, 6.8, nb.abs(x)), smoothstep(nb, -13.0, -10.5, z)), smoothstep(nb, 7.0, 5.0, z))
    phone = nb.vscale(U.out(nb, 'phone_col'),
                      nb.mul(nb.mul(nb.mul(U.out(nb, 'phone_fill'), smoothstep(nb, 4.2, 0.8, y)), crowd), 0.05))
    to_t = nb.vmath('SUBTRACT', P, TEXT_POS)
    to_b = nb.vmath('SUBTRACT', P, BURST_POS)
    txt = nb.vscale(U.out(nb, 'text_col'),
                    nb.mul(nb.div(U.out(nb, 'text_lvl'), nb.add(nb.div(nb.vdot(to_t, to_t), 6.0), 1.0)), 0.08))
    bst = nb.vscale(U.out(nb, 'burst_col'),
                    nb.mul(nb.div(U.out(nb, 'burst_lvl'), nb.add(nb.div(nb.vdot(to_b, to_b), 40.0), 1.0)), 0.6))
    nb.put(go.inputs['Color'], nb.vadd(nb.vadd(nb.vadd(U.out(nb, 'amb_base'), phone), txt), bst))
    return g


class FuneralPost:
    """funeral.js post: the depth_fog + godrays this set wants, as Blender does them in the render: a fog volume over
    the warehouse interior (the look family's native depth_fog mechanism, look.post.custom_effects: a Principled
    Volume box, density per metre modulated by noise_amount / noise_scale, volumetric shadows), lit and shadowed by
    the moon through the windows, so its beams are the godrays. The box is the set's own (under its root: it moves
    with the set, and it covers the interior only). effects / opts() as the JS; apply(scene) builds it; drive(fx, u,
    keys) sets the density, the haze colour (the volume's own emission, density x colour, so a deep view reaches the
    WebGPU fog colour) and the moon's beams (its volume factor, the godrays strength) at u."""

    effects = ['depth_fog', 'godrays']
    SIZE = (18.0, 22.0, 7.6)                     # the interior, Blender metres (three x -9..9, z -12..10, y 0..7.6)

    def __init__(self, F):
        self.F = F
        self.vol = None

    def opts(self):
        return {'depth_fog': {'color': [0.02, 0.018, 0.016], 'density': 0.0, 'noise_amount': 0.3, 'noise_scale': 3.0,
                              'layer': 'under'},
                'godrays': {'light': self.F.lights['moon'], 'strength': 0.0}}

    def apply(self, scene=None):
        """Build the haze volume (once) and the EEVEE volume settings it needs. Returns {'object', 'volume', 'density'}."""
        F = self.F
        kit = F.kit
        scene = scene or kit.scene
        if self.vol is not None:
            return self.fx
        o = self.opts()['depth_fog']
        sx, sy, h = self.SIZE
        m, nb = new_mat('funeral:haze')
        vol = nb.new('ShaderNodeVolumePrincipled')
        P3, Pb, _ = set_pos(nb, kit.root)
        n = nb.noise(P3, float(o['noise_scale']) / 10.0, detail=0.0, normalize=True)
        mr = nb.new('ShaderNodeMapRange')
        nb.put(mr.inputs['Value'], n)
        amt = float(o['noise_amount'])
        mr.inputs['To Min'].default_value = 0.0
        mr.inputs['To Max'].default_value = 0.0
        nb.put(vol.inputs['Density'], mr.outputs['Result'])
        vol.inputs['Color'].default_value = (0.8, 0.8, 0.8, 1.0)
        vol.inputs['Anisotropy'].default_value = 0.35
        out = nb.new('ShaderNodeOutputMaterial')
        nb.t.links.new(vol.outputs['Volume'], out.inputs['Volume'])
        c = V(0.0, 0.0, -1.0)
        verts = [(c.x + dx * sx / 2, c.y + dy * sy / 2, dz * h) for dx in (-1, 1) for dy in (-1, 1) for dz in (0, 1)]
        faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        ob = mesh_object('funeral:haze', kit.coll('fx'), verts, faces, parent=kit.root, mats=[m])
        ob.visible_shadow = False
        ee = scene.eevee
        ee.use_volumetric_shadows = True
        if hasattr(ee, 'use_volume_custom_range'):
            ee.use_volume_custom_range = True
        ee.volumetric_start, ee.volumetric_end = 0.1, 60.0
        self.vol, self.range, self.amt = vol, mr, amt
        self.fx = {'object': ob, 'volume': vol, 'density': mr, 'material': m}
        F.room_objects.append(ob)
        return self.fx

    def drive(self, fx, u, keys=None):
        """The JS drive(FU, u) on the haze: density 0.028 in the room (none on the bridge: the vignette fogs its own
        materials), the haze colour (dark -> golden, + power, + the burst) as the volume's emission, and the moon's
        beams (godrays strength 0.55 -> 0.15 as the lights come back) as its volume factor."""
        F = self.F
        in_bridge = u < F.beats['bridge_end']
        gold, pw, bl = F.U['golden'], F.U['power'], F.U['burst_lvl']
        fc = (lerp(0.012, 0.09, gold) + 0.02 * pw + 0.05 * bl, lerp(0.012, 0.065, gold) + 0.015 * pw + 0.035 * bl,
              lerp(0.016, 0.04, gold) + 0.012 * pw + 0.02 * bl)
        dens = 0.0 if in_bridge else 0.028
        vol, mr = self.vol, self.range
        mr.inputs['To Min'].default_value = dens * (1.0 - self.amt)
        mr.inputs['To Max'].default_value = dens * (1.0 + self.amt)
        vol.inputs['Emission Color'].default_value = (fc[0], fc[1], fc[2], 1.0)
        vol.inputs['Emission Strength'].default_value = dens
        moon = F.lights['moon'].data
        strength = 0.0 if in_bridge else lerp(0.55, 0.15, gold)
        moon.volume_factor = strength / 0.55
        if keys is not None and keys.active:
            keys.key(mr.inputs['To Min'], 'default_value')
            keys.key(mr.inputs['To Max'], 'default_value')
            keys.key(vol.inputs['Emission Color'], 'default_value')
            keys.key(vol.inputs['Emission Strength'], 'default_value')
            keys.key(moon, 'volume_factor')

    def animate(self, fx, frames, u0=0.0, fps=None, state=None):
        """drive() keyed over frames (u = u0 at frames[0]; state= holds a STATES look, as Funeral.animate)."""
        sc = self.F.kit.scene
        fps = fps or sc.render.fps / sc.render.fps_base
        f0, f1 = frames
        rate = 1.0
        if state:
            u0, rate = self.F.state_u(state), 0.0
        k = Keys(frame=None)
        for f in range(f0, f1 + 1):
            u = u0 + rate * (f - f0) / fps
            k.frame = f
            self.F._uniform_curves(u, u)      # the uniforms this reads, at u
            self.drive(fx, u, k)
        return k.finish()


class Funeral:
    """build(ctx) -> Funeral: group (the set's root Empty), mark, mark_at(u), update(t, st), camera(u), post, lights,
    dispose(); and in Blender animate(frames, u0) and make_cameras(frames, u0), which key the section."""

    def __init__(self, ctx=None, location=(0.0, 0.0, 0.0), scene=None, collection=None, tl=None, bridge=True,
                 crowd=True, raven=True, shadows=True, beats=None, eulogy=None):
        self.ctx = ctx
        self.shadows = bool(shadows)
        self.beats = json.loads(json.dumps(BEATS))           # mutable: the eulogy re-times to the film's captions
        if beats:
            self.beats.update(json.loads(json.dumps(beats)))   # the set's own clock, re-timed for another piece
        # the words typed in light: EULOGY, lines of your own (one beats['lines'] entry each), or False for none
        self.eulogy = [] if eulogy is False else [str(x) for x in (EULOGY if eulogy is None else eulogy)]
        if len(self.eulogy) > len(self.beats['lines']):
            raise ValueError(f'funeral: {len(self.eulogy)} eulogy lines need as many beats["lines"] '
                             f'([cursor, type start, type end] each); got {len(self.beats["lines"])}')
        self.kit = kit = SetKit('funeral', location, scene or getattr(ctx, 'scene', None), collection)
        self.group = kit.root
        with open(os.path.join(PACK, 'funeral_layout.json'), encoding='utf-8') as f:
            self.layout = json.load(f)
        with open(os.path.join(PACK, 'props_layout.json'), encoding='utf-8') as f:
            self.anchors = json.load(f)
        with open(os.path.join(PACK, 'crowd_rig.json'), encoding='utf-8') as f:
            self.rig = json.load(f)
        kit.U = self.U = Uniforms(kit.root, 'funeral', UNIFORMS)
        g = _env_room_group(kit)

        def env_room(nb, P3):
            n = nb.new('ShaderNodeGroup')
            n.node_tree = g
            nb.put(n.inputs['P'], P3)
            return n.outputs['Color']
        kit.env_room = env_room
        self.tl = tl if tl is not None else (getattr(ctx, 'TL', None) if ctx is not None else None)
        self.parts = {}
        self.lights = {}
        self.room_objects = []
        self.bridge = None
        self._lines_synced = False
        self._build_materials()
        self._build_warehouse()
        self._build_lights()
        self._build_lamps()
        self._build_festoon()
        self._build_props()
        self._build_candles()
        if raven:
            self._build_raven()
        self._build_beam()
        if crowd:
            self._build_crowd()
        self._build_eulogy()
        self._build_burst()
        self._build_veil()
        self._build_world()
        hidden = {kit.coll('sources', hidden=True), kit.coll('cameras')}
        self.room_objects = [o for o in kit.top.all_objects if o.type not in ('LIGHT', 'CAMERA')
                             and not any(c in hidden for c in o.users_collection)
                             and o is not kit.root and o is not self.veil]
        if bridge:
            from . import bridge as BR
            self.bridge = BR.build_bridge({'kit': kit, 'U': self.U, 'surface': surface, 'glow_sprites': glow_sprites,
                                           'BRIDGE_AT': BRIDGE_AT, 'BRIDGE_MARK': BRIDGE_MARK, 'world': self.world})
            self.room_objects = [o for o in self.room_objects if o not in self.bridge.objects]
        self.post = FuneralPost(self)
        self.mark = V(MARK)

    # -------------------------------------------------------------------------------------------- materials
    def _build_materials(self):
        kit = self.kit
        S = {i: kit.tex_set(i) for i in SET_IDS}
        self.S = S
        lamp = self.U

        def floor_post(nb, col, c):
            x3, y3, z3 = nb.sep(c['P3'])

            def joint(v):
                return smoothstep(nb, 0.012, 0.004, nb.mul(nb.abs(nb.sub(nb.fract(nb.add(nb.div(v, 3.6), 0.5)), 0.5)), 3.6))
            jx, jz = joint(x3), joint(z3)
            stain = smoothstep(nb, 0.58, 0.8, nb.madd(nb.noise(c['P3'], 0.55, detail=3, roughness=0.55), 0.5, 0.5))
            cc = nb.vscale(col, nb.sub(1.0, nb.mul(nb.mx(jx, jz), 0.55)))
            return vmix(nb, cc, nb.vmul(cc, (0.55, 0.5, 0.45)), nb.mul(stain, 0.6))
        M = {
            'brick': dict(set='Bricks097', tile=1.05, tint=[0.78, 0.7, 0.66], nrm=1.3, macro=0.32,
                          grime=[0.55, 1.4, [0.1, 0.085, 0.07]], salt=0.45, soot=[4.2, 7.5, 0.55],
                          edge=[0.6, [0.55, 0.5, 0.45], 0.012], smudge=0.05),
            'concrete': dict(set='Concrete048', tile=2.2, tint=[0.62, 0.61, 0.6], grime=[0.6, 0.5, [0.1, 0.095, 0.085]],
                             macro=0.3, edge=[0.5, [0.7, 0.68, 0.64], 0.02]),
            'floor': dict(set='Concrete034', tile=3.4, tint=[0.5, 0.49, 0.47], roughMul=0.75, roughAdd=0.05, macro=0.35,
                          macroScale=0.22, smudge=0.25, post=floor_post),
            'timber': dict(set='Planks039', tile=[1.6, 0.55], tint=[0.46, 0.36, 0.28], nrm=1.1, macro=0.3,
                           soot=[5.0, 8.2, 0.45], dust=0.5, edge=[0.5, [0.55, 0.45, 0.35], 0.03]),
            'planks': dict(set='Planks039', tile=0.95, tint=[0.36, 0.28, 0.22], nrm=1.0, macro=0.35, soot=[5.5, 8.4, 0.5]),
            'steel': dict(set='PaintedMetal012', tile=0.8, tint=[0.15, 0.15, 0.16], metal=0.45, roughMul=0.9, nrm=0.8,
                          edge=[0.7, [0.3, 0.2, 0.14], 0.015], dust=0.4),
            'galv': dict(set='Metal049A', tile=0.6, tint=[0.5, 0.51, 0.52], metal=0.85, roughMul=0.7, roughAdd=0.12,
                         macro=0.4),
            'corrugated': dict(set='CorrugatedSteel009', tile=1.0, tint=[0.62, 0.6, 0.57], metal=0.55, metalMap=True,
                               grime=[0.7, 1.0, [0.12, 0.09, 0.07]]),
            'enamel': dict(set='Metal049A', tile=0.5, tint=[0.1, 0.21, 0.16], roughMul=0.45, roughAdd=0.05, dust=0.6,
                           edge=[0.9, [0.08, 0.07, 0.06], 0.006]),
            'enamel_in': dict(set='Metal049A', tile=0.5, tint=[0.9, 0.88, 0.82], roughMul=0.4,
                              emissive=lambda nb: nb.vscale((1.0, 0.72, 0.42), nb.mul(lamp.out(nb, 'lamp_i'), 0.5))),
            'stage': dict(set='Wood066', tile=1.4, tint=[0.075, 0.07, 0.068], roughMul=0.6, roughAdd=0.35, macro=0.2,
                          edge=[0.5, [0.25, 0.2, 0.16], 0.02]),
            'fabric': dict(set='Planks039', tile=0.2, tint=[0.02, 0.018, 0.02], roughAdd=0.6, nrm=0.2, physical=True,
                           sheen=1.0),
            'cord': dict(set='Metal049A', tile=0.3, tint=[0.02, 0.02, 0.02], roughAdd=0.3),
        }
        self.M = {k: surface(kit, S[v.pop('set')], v, name=f'funeral:{k}') for k, v in M.items()}
        self.M['glass'] = self._glass_mat()
        self.M['screen'] = self._screen_mat()
        self.M['exit'] = self._exit_mat()

    def _glass_mat(self):
        """dark, dirty glass with a faint night outside (moon-blue top, sodium-orange low), per pane."""
        kit = self.kit
        m, nb = new_mat('funeral:glass', 'BLENDED')
        b = nb.new('ShaderNodeBsdfPrincipled')
        P3, Pb, _ = set_pos(nb, kit.root)
        x3, y3, z3 = nb.sep(P3)
        n = nb.fbm01(P3, 2.5, 3)
        seed = nb.add(nb.add(nb.floor(nb.mul(z3, 1.8)), nb.mul(nb.floor(nb.mul(y3, 1.9)), 17.0)),
                      nb.mul(nb.floor(nb.mul(x3, 0.2)), 101.0))
        wn = nb.new('ShaderNodeTexWhiteNoise', noise_dimensions='1D')
        nb.put(wn.inputs['W'], seed)
        pane = wn.outputs['Value']
        U = self.U
        night = vmix(nb, (0.12, 0.07, 0.03), (0.05, 0.075, 0.13), smoothstep(nb, 3.8, 5.6, y3))
        k = nb.mul(nb.mul(nb.madd(pane, 0.8, 0.35), nb.madd(U.out(nb, 'moon'), 0.7, 0.35)),
                   nb.sub(1.0, nb.mul(U.out(nb, 'golden'), 0.5)))
        col = (0.02, 0.025, 0.03)
        nb.put(b.inputs['Base Color'], col)
        nb.put(b.inputs['Roughness'], nb.madd(n, 0.3, 0.12))
        nb.put(b.inputs['Metallic'], 0.0)
        nb.put(b.inputs['Alpha'], nb.madd(n, 0.3, 0.55))
        nb.put(b.inputs['Emission Color'], nb.vadd(nb.vscale(night, k), ambient(nb, kit, col, None, None, P3)))
        nb.put(b.inputs['Emission Strength'], 1.0)
        finish_surface(nb, b)
        m.use_transparent_shadow = True
        return m

    def _screen_mat(self):
        """the projection screen: the retirement note, projected (dies with the power)."""
        kit = self.kit

        def draw(g, W, H):
            grd = g.createRadialGradient(512, 280, 60, 512, 288, 620)
            grd.addColorStop(0, '#f2f0ea')
            grd.addColorStop(1, '#b9b4aa')
            g.fillStyle = grd
            g.fillRect(0, 0, 1024, 576)
            g.fillStyle = '#2a2622'
            g.textAlign = 'center'
            g.font = '600 54px "Segoe UI", Georgia, serif'
            g.fillText('Claude 3 Sonnet', 512, 170)
            g.font = '36px "Segoe UI", Georgia, serif'
            g.fillText('2024 – 2025', 512, 228)
            g.fillStyle = 'rgba(42,38,34,0.55)'
            r = mulberry(5)
            for i in range(7):                     # the note, unreadable at this distance
                w = 520 - (240 if i == 6 else r() * 90)
                g.fillRect(512 - w / 2, 300 + i * 30, w, 11)
        img = canvas_image('funeral:screen_note', 1024, 576, draw, ss=2)
        self.screen_img = img
        m, nb = new_mat('funeral:screen')
        b = nb.new('ShaderNodeBsdfPrincipled')
        sx, sy, _sz, sw, shh = self.layout['screen']
        P3, Pb, _ = set_pos(nb, kit.root)
        x3, y3, z3 = nb.sep(P3)
        u = nb.div(nb.sub(sx + sw / 2, x3), sw)
        v = nb.div(nb.sub(y3, sy - shh / 2), shh)
        tx = nb.tex(img, nb.comb(u, v, 0.0), extension='EXTEND').outputs['Color']
        col = (0.72, 0.71, 0.68)
        nb.put(b.inputs['Base Color'], col)
        nb.put(b.inputs['Roughness'], 0.9)
        em = nb.vmul(nb.vscale(tx, self.U.out(nb, 'proj_i')), (0.95, 0.97, 1.0))
        nb.put(b.inputs['Emission Color'], nb.vadd(em, ambient(nb, kit, col, None, None, P3)))
        nb.put(b.inputs['Emission Strength'], 1.0)
        finish_surface(nb, b)
        return m

    def _exit_mat(self):
        """the EXIT sign over the side door (battery-backed: it stays lit when the power fails)."""
        kit = self.kit

        def draw(g, W, H):
            g.fillStyle = '#0a0808'
            g.fillRect(0, 0, 256, 128)
            g.fillStyle = '#ff2a1a'
            g.font = '700 84px "Segoe UI", Arial, sans-serif'
            g.textAlign = 'center'
            g.textBaseline = 'middle'
            g.fillText('EXIT', 128, 68)
        img = canvas_image('funeral:exit', 256, 128, draw, ss=2)
        m, nb = new_mat('funeral:exit')
        b = nb.new('ShaderNodeBsdfPrincipled')
        ex, ey, _ez, ew, eh = self.layout['exit']
        P3, Pb, _ = set_pos(nb, kit.root)
        x3, y3, z3 = nb.sep(P3)
        u = nb.clamp(nb.div(nb.sub(x3, ex - ew / 2), ew))
        v = nb.clamp(nb.div(nb.sub(y3, ey - eh / 2), eh))
        lit = nb.sep(nb.tex(img, nb.comb(u, v, 0.0), extension='EXTEND').outputs['Color'])[0]
        nzb = nb.sep(nb.geometry('Normal'))[1]            # three normalWorld.z = -Blender y
        front = smoothstep(nb, 0.5, 0.9, nb.mul(nzb, -1.0))
        col = (0.05, 0.04, 0.04)
        nb.put(b.inputs['Base Color'], col)
        nb.put(b.inputs['Roughness'], 0.4)
        em = nb.vscale((1.0, 0.1, 0.05), nb.mul(nb.madd(nb.mul(lit, front), 3.0, 0.05), self.U.out(nb, 'exit_lvl')))
        nb.put(b.inputs['Emission Color'], nb.vadd(em, ambient(nb, kit, col, None, None, P3)))
        nb.put(b.inputs['Emission Strength'], 1.0)
        finish_surface(nb, b)
        return m

    # -------------------------------------------------------------------------------------------- warehouse
    def _build_warehouse(self):
        kit = self.kit
        root, nodes = import_glb(kit, os.path.join(MODELS, 'funeral_warehouse.glb'), 'warehouse', kit.coll('warehouse'))
        for o in nodes.values():
            if o.type != 'MESH':
                continue
            roles = []
            for s in o.material_slots:
                role = role_of(s.material)
                roles.append(role)
                old = s.material
                s.link = 'DATA'
                s.material = self.M.get(role, self.M['concrete'])
                if old is not None and old.users == 0:
                    bpy.data.materials.remove(old)
            o['eido_roles'] = ','.join(roles)
            K.write_curvature(o)
            o.visible_shadow = not ('glass' in roles or 'floor' in roles)
        self.parts['warehouse'] = root
        self.parts['warehouse_nodes'] = nodes

    # ----------------------------------------------------------------------------------------------- lights
    def _build_lights(self):
        kit, L = self.kit, self.layout
        warm = (1.0, 0.7, 0.42)
        self.pend_spots = []
        # six pendant spots (every other RLM lamp, checkerboard). WebGPU drew every light but the moon without shadow
        # maps to save the frame budget; EEVEE's virtual shadow maps are cheap at film settings, so the pendants, the
        # stage spot and the candles cast here and the mourners stand on their own shadows (shadows=False on build()
        # restores the WebGPU set: only the moon casts)
        for i, p in enumerate(L['lamps']):
            row, col = i // 3, i % 3
            if (row + col) % 2:
                continue
            s = make_light(kit, f'pendant_{i}', 'SPOT', warm, V(p[0], p[1] - 0.02, p[2]), V(p[0], 0.0, p[2]),
                           angle=math.radians(62), penumbra=0.75, shadow=self.shadows, radius=0.05, shadow_res=0.02)
            self.pend_spots.append((s, i))
        self.stage_spot = make_light(kit, 'stage_spot', 'SPOT', (1.0, 0.8, 0.6), V(0, 5.6, 7.75), V(0, 0.8, 8.15),
                                     angle=math.radians(24), penumbra=0.6, shadow=self.shadows, radius=0.05)
        # moonlight through the left windows + skylights: its shadows make the shafts (NO_MOONSHADOW=1, the WebGPU
        # debugging flag, turns them off)
        moon = make_light(kit, 'moon', 'SUN', (0.62, 0.72, 1.0), V(-30, 27, 6), V(0, 0, -1),
                          shadow=not os.environ.get('NO_MOONSHADOW'), volume=1.0)
        self.lights['moon'] = moon
        mn = L['mannequins']
        cl = [(0, 1.05, 7.0, 1.0), (mn['opus3'][0] + 0.25, 0.7, mn['opus3'][2] + 0.7, 1.5),
              (mn['sonnet4'][0] - 0.5, 0.45, mn['sonnet4'][2] - 0.55, 0.9),
              (mn['opus4'][0] + 0.24, 0.95, mn['opus4'][2] + 0.36, 1.3),
              (mn['haiku3'][0] - 0.45, 0.45, mn['haiku3'][2] + 0.6, 0.8)]
        self.candle_lights = []
        for i, (x, y, z, k) in enumerate(cl):      # candle clusters: the stage + offerings, one per corner mannequin
            ob = make_light(kit, f'candles_{i}', 'POINT', (1.0, 0.62, 0.3), V(x, y, z), shadow=self.shadows, radius=0.08,
                            shadow_res=0.01)
            ob['k'] = k
            ob['seed'] = i * 7.31
            self.candle_lights.append(ob)
        self.key = make_light(kit, 'key', 'POINT', (1, 0.8, 0.6), V(MARK[0] + 0.45, 1.75, MARK[2] + 1.2), shadow=False,
                              radius=0.1)
        self.burst_l = make_light(kit, 'burst', 'POINT', (1.0, 0.75, 0.45), V(TEXT_AT), shadow=False, radius=0.3)
        self.lights.update({'stage': self.stage_spot, 'key': self.key, 'burst': self.burst_l})

    def _build_world(self):
        """the HemisphereLight fill (sky (0.6, 0.62, 0.7), ground (0.25, 0.2, 0.16)) as the World; the bridge switches
        it to its own hemisphere."""
        w, socks = world_hemisphere('funeral:world', (0.6, 0.62, 0.7), (0.25, 0.2, 0.16))
        self.world = {'world': w, **socks}
        self.kit.scene.world = w

    # ------------------------------------------------------------------------------------- bulbs + strings
    def _lamp_level(self, nb, delay):
        """lampLevelNode(delay): the funeral level before the failure, the power_down sag, black, then the golden
        return staggered per lamp (nearest the stage first)."""
        U = self.U
        u = U.out(nb, 'u')
        on = self.beats['lights_on']
        since = nb.sub(nb.sub(u, on), delay)
        relight = nb.mul(smoothstep(nb, 0.0, 0.18, since), nb.madd(smoothstep(nb, 0.25, 0.6, since), 0.25, 0.75))
        return nb.mix(U.out(nb, 'power'), nb.mul(relight, 1.35), nb.step(on, u))

    def _string_level(self, nb):
        U = self.U
        u = U.out(nb, 'u')
        on = self.beats['lights_on']
        since = nb.sub(u, on + 0.12)
        return nb.mix(nb.mul(U.out(nb, 'power'), 0.7), smoothstep(nb, 0.0, 0.35, since), nb.step(on, u))

    def _build_lamps(self):
        kit, L = self.kit, self.layout
        lamps = L['lamps']
        self.lamp_relight = [math.hypot(p[0], (p[2] - 7.5) * 0.8) * 0.028 for p in lamps]
        # bulbs: one mesh of spheres (r 0.055) with a per-vertex relight delay
        sph = _uv_sphere(0.055, 16, 12)
        verts, faces, dl = [], [], []
        for i, p in enumerate(lamps):
            c = np.array(V(p[0], p[1] - 0.05, p[2]))
            base = len(verts)
            verts.extend((sph[0] + c).tolist())
            faces.extend([tuple(base + k for k in f) for f in sph[1]])
            dl.extend([self.lamp_relight[i]] * len(sph[0]))
        m, nb = new_mat('funeral:bulb')
        lvl = self._lamp_level(nb, nb.attr('del'))
        out = nb.new('ShaderNodeOutputMaterial')
        em = nb.new('ShaderNodeEmission')
        nb.put(em.inputs['Color'], vmix(nb, (0.05, 0.04, 0.03), (3.2, 1.0 * 0.78 * 3.2, 0.5 * 3.2), lvl))
        nb.t.links.new(em.outputs[0], out.inputs['Surface'])
        bulbs = mesh_object('funeral:bulbs', kit.coll('lamps'), verts, faces, attrs={'del': dl}, parent=kit.root,
                            mats=[m], smooth=True)
        bulbs.visible_shadow = False
        pos = [V(p[0], p[1] - 0.05, p[2]) for p in lamps]
        glow_sprites(kit, 'bulb_glow', pos, {'del': self.lamp_relight}, size=0.42,
                     colour=lambda nb, A: nb.vscale((1.0, 0.72, 0.42), nb.mul(self._lamp_level(nb, A('del')), 0.55)),
                     sharp=12.0, halo=0.25, coll=kit.coll('lamps'))

    def _build_festoon(self):
        kit, L = self.kit, self.layout
        tz = L['truss_z']
        festoon = []
        for x in (-6.75, -2.25, 2.25, 6.75):           # four festoon runs, sagging between trusses
            pts = []
            for k in range(len(tz) - 1):
                z0, z1 = tz[k], tz[k + 1]
                for j in range(8):
                    f = j / 8
                    pts.append([x, 5.62 - 0.42 * 4 * f * (1 - f), lerp(z0, z1, f)])
            pts.append([x, 5.62, tz[-1]])
            festoon.append(pts)
        bp, curves = [], []
        for i, pts in enumerate(festoon):
            cv = CatmullRom(pts)
            curves.append(cv)
            n = len(pts) * 3
            wire_object(f'funeral:festoon_{i}', kit.coll('lamps'), [V(cv.point(k / n)) for k in range(n + 1)], 0.006,
                        parent=kit.root, mat=self.M['cord']).visible_shadow = False
            Lc = cv.length()
            d = 0.2
            while d < Lc:
                p = cv.point_at(d / Lc)
                bp.append([p[0], p[1] - 0.055, p[2]])
                d += 0.48
        nbulb = len(bp)
        seeds = [(i * 0.61803) % 1 for i in range(nbulb)]
        sph = _uv_sphere(0.028, 10, 8)
        sph_v = sph[0] * np.array([1.0, 1.0, 1.35])              # positionLocal * (1, 1.35, 1): taller in three y
        verts, faces, sd = [], [], []
        for i, p in enumerate(bp):
            c = np.array(V(p))
            base = len(verts)
            verts.extend((sph_v + c).tolist())
            faces.extend([tuple(base + k for k in f) for f in sph[1]])
            sd.extend([seeds[i]] * len(sph_v))
        m, nb = new_mat('funeral:festoon_bulb')
        sl = self._string_level(nb)
        out = nb.new('ShaderNodeOutputMaterial')
        em = nb.new('ShaderNodeEmission')
        nb.put(em.inputs['Color'], vmix(nb, (0.04, 0.03, 0.02), (4.0, 2.8, 1.44),
                                        nb.mul(sl, nb.madd(nb.attr('seed'), 0.3, 0.7))))
        nb.t.links.new(em.outputs[0], out.inputs['Surface'])
        ob = mesh_object('funeral:festoon_bulbs', kit.coll('lamps'), verts, faces, attrs={'seed': sd}, parent=kit.root,
                         mats=[m], smooth=True)
        ob.visible_shadow = False
        glow_sprites(kit, 'festoon_glow', [V(p) for p in bp], {'seed': seeds}, size=0.22,
                     colour=lambda nb, A: nb.vscale((1.0, 0.66, 0.32), nb.mul(self._string_level(nb), 0.6)),
                     sharp=10.0, halo=0.3, coll=kit.coll('lamps'))
        self.parts['festoon'] = {'curves': curves, 'bulbs': bp}

    # ------------------------------------------------------------------------------------------------ props
    def _build_props(self):
        kit, U = self.kit, self.U
        S = self.S
        cg = lambda nb: nb.vscale((1.0, 0.55, 0.22), U.out(nb, 'candle'))       # noqa: E731
        lace_img = self._lace_image()

        def lace_alpha(nb):
            uv = nb.vmul(nb.uv('UVMap'), (6.0, 6.0, 1.0))
            return nb.sep(nb.tex(lace_img, uv).outputs['Color'])[0]

        def net_alpha(nb):
            q = nb.vscale(nb.uv('UVMap'), 85.0)
            qx, qy, _ = nb.sep(q)
            gx = nb.abs(nb.sub(nb.fract(qx), 0.5))
            gy = nb.abs(nb.sub(nb.fract(qy), 0.5))
            return smoothstep(nb, 0.43, 0.49, nb.mx(gx, gy))

        def gold_post(nb, col, c):
            tar = smoothstep(nb, 0.5, 0.78, nb.madd(nb.noise(c['P3'], 6.0, detail=2, roughness=0.55), 0.5, 0.5))
            tuv = nb.vscale(nb.uv('UVMap'), 3.0)
            tcol = nb.vmul(nb.tex(S['Metal042B']['col'], tuv).outputs['Color'], (0.62, 0.52, 0.38))
            return vmix(nb, nb.vmul(col, (1.0, 0.86, 0.6)), tcol, nb.mul(tar, 0.7))

        def tent_post(nb, col, c):
            return vmix(nb, col, (0.16, 0.08, 0.12), nb.mul(smoothstep(nb, 0.55, 0.8, c['n1']), 0.6))
        sm = lambda nm, c, r, o=None: simple(kit, c, r, o, name=f'funeral:{nm}')     # noqa: E731
        PM = {
            'gold': surface(kit, S['Metal048B'], {'tile': 0.3, 'metal': 1.0, 'roughMul': 0.95, 'roughAdd': 0.08, 'nrm': 0.6,
                                                  'macro': 0.25, 'macroScale': 3.0, 'post': gold_post}, name='funeral:gold'),
            'lace': sm('lace', [0.9, 0.86, 0.78], 0.75, {'side': 'DOUBLE', 'alpha': lace_alpha, 'ns': 3.0}),
            'chrome': sm('chrome', [0.85, 0.85, 0.86], 0.13, {'metal': 1.0, 'mottle': 0.08, 'rVar': 0.08}),
            'brass': sm('brass', [0.78, 0.56, 0.26], 0.32, {'metal': 1.0, 'mottle': 0.3}),
            'petal_pink': sm('petal_pink', [0.95, 0.52, 0.6], 0.45,
                             {'side': 'DOUBLE',
                              'emissive': lambda nb: nb.vscale((1.0, 0.45, 0.5), nb.mul(U.out(nb, 'candle'), 0.22))}),
            'wax': sm('wax', [0.9, 0.84, 0.72], 0.5, {'ns': 30.0, 'mottle': 0.12, 'emissive': lambda nb: nb.vscale(cg(nb), 0.18)}),
            'wick': sm('wick', [0.03, 0.025, 0.02], 0.8),
            'tin': sm('tin', [0.72, 0.72, 0.74], 0.32, {'metal': 0.9, 'mottle': 0.12}),
            'pearl': sm('pearl', [0.95, 0.93, 0.88], 0.22, {'clearcoat': 0.8}),
            'jewel': sm('jewel', [0.45, 0.02, 0.05], 0.08, {'clearcoat': 1.0}),
            'black_gloss': sm('black_gloss', [0.018, 0.018, 0.02], 0.2, {'clearcoat': 1.0, 'coatR': 0.06, 'mottle': 0.4, 'grime': 0.5}),
            'fiberglass': sm('fiberglass', [0.82, 0.79, 0.74], 0.36, {'clearcoat': 0.35, 'mottle': 0.18, 'grime': 0.45,
                                                                     'grimeCol': [0.35, 0.32, 0.28]}),
            'porcelain': sm('porcelain', [0.93, 0.92, 0.9], 0.16, {'clearcoat': 0.7, 'mottle': 0.06}),
            'graphite': sm('graphite', [0.055, 0.058, 0.065], 0.32, {'clearcoat': 0.6, 'coatR': 0.1, 'mottle': 0.3, 'grime': 0.4}),
            'grille': sm('grille', [0.04, 0.04, 0.045], 0.95, {'ns': 60.0, 'speck': 0.4}),
            'led': sm('led', [0.1, 0.4, 0.15], 0.3, {'emissive': lambda nb: (0.5, 2.5, 0.875)}),
            'lens': sm('lens', [0.02, 0.025, 0.03], 0.05, {'clearcoat': 1.0}),
            'net': sm('net', [0.88, 0.88, 0.9], 0.7, {'side': 'DOUBLE', 'alpha': net_alpha, 'ns': 2.0}),
            'petal': sm('petal', [0.9, 0.88, 0.82], 0.6, {'side': 'DOUBLE'}),
            'petal_red': sm('petal_red', [0.5, 0.03, 0.05], 0.55, {'side': 'DOUBLE'}),
            'petal_yellow': sm('petal_yellow', [0.95, 0.72, 0.14], 0.55, {'side': 'DOUBLE'}),
            'flower_disc': sm('flower_disc', [0.55, 0.36, 0.05], 0.8),
            'stem': sm('stem', [0.12, 0.24, 0.07], 0.7),
            'feather': sm('feather', [0.93, 0.93, 0.91], 0.85, {'side': 'DOUBLE', 'mottle': 0.1}),
            'bottle': sm('bottle', [0.86, 0.85, 0.8], 0.4, {'mottle': 0.08}),
            'plaque': sm('plaque', [0.62, 0.62, 0.6], 0.6, {'ns': 40.0}),
            'plastic_dark': sm('plastic_dark', [0.045, 0.045, 0.05], 0.45),
            'tentacle': sm('tentacle', [0.05, 0.075, 0.06], 0.28, {'ns': 4.0, 'mottle': 0.7, 'clearcoat': 0.8, 'coatR': 0.15,
                                                                 'post': tent_post,
                                                                 'emissive': lambda nb: (0.0075, 0.021, 0.0135)}),
            'sucker': sm('sucker', [0.42, 0.3, 0.3], 0.35, {'mottle': 0.3}),
            'stage': self.M['stage'], 'fabric': self.M['fabric'], 'timber': self.M['timber'], 'cord': self.M['cord'],
        }
        for r in ('lace', 'net', 'petal', 'petal_red', 'petal_yellow', 'feather'):
            no_shadow(PM[r])
        self.PM = PM
        root, nodes = import_glb(kit, os.path.join(MODELS, 'funeral_props.glb'), 'props', kit.coll('props'))
        self.candle_types = {}
        src = kit.coll('sources', hidden=True)
        for nm, o in nodes.items():
            if o.type != 'MESH':
                continue
            sonnet4 = nm.startswith('mannequin_sonnet4')
            for s in o.material_slots:
                role = role_of(s.material)
                mat = PM.get(role, PM['fiberglass'])
                if sonnet4 and role == 'fiberglass':
                    mat = PM['graphite']                     # Sonnet 4 is graphite, so its porcelain mask reads
                old = s.material
                s.link = 'DATA'
                s.material = mat
                if old is not None and old.users == 0:
                    bpy.data.materials.remove(old)
            K.write_curvature(o)
            if nm.startswith('candle_'):
                for c in list(o.users_collection):
                    c.objects.unlink(o)
                src.objects.link(o)
                o.parent = None
                self.candle_types[nm] = o
        self.parts['props'] = root
        self.parts['props_nodes'] = {k: v for k, v in nodes.items() if not k.startswith('candle_')}

    def _lace_image(self):
        """a canvas-drawn tileable mantilla motif (rosettes, scallops, a fine net between), cut out."""
        def draw(g, W, H):
            g.clearRect(0, 0, 512, 512)
            g.strokeStyle = '#fff'
            g.fillStyle = '#fff'
            g.lineWidth = 2.2
            for i in range(-1, 9):                 # the fine hexagonal net
                for j in range(-1, 9):
                    x, y = i * 64 + (j % 2) * 32, j * 64
                    g.beginPath()
                    g.moveTo(x, y)
                    g.lineTo(x + 32, y + 32)
                    g.lineTo(x + 64, y)
                    g.stroke()
            for cx, cy in ((128, 128), (384, 384), (384, 128), (128, 384)):        # rosettes
                g.lineWidth = 7
                g.beginPath()
                g.arc(cx, cy, 20, 0, TAU)
                g.stroke()
                for k in range(8):
                    a = k * math.pi / 4
                    g.beginPath()
                    g.ellipse(cx + math.cos(a) * 44, cy + math.sin(a) * 44, 22, 10, a, 0, TAU)
                    g.stroke()
                g.lineWidth = 4
                g.beginPath()
                g.arc(cx, cy, 70, 0, TAU)
                g.stroke()
                for k in range(16):                # scalloped ring
                    a = k * math.pi / 8
                    g.beginPath()
                    g.arc(cx + math.cos(a) * 82, cy + math.sin(a) * 82, 12, a - 1.2, a + 1.2)
                    g.stroke()
        # the JS reads the R channel of getImageData: 255 wherever the white strokes left any coverage, 0 where the canvas
        # is clear, filtered and mip-mapped as a plain channel. Kept as an opaque Non-Color image: Blender premultiplies a
        # straight-alpha image to filter it and divides again for the Color output, which turned the lace's R to 1 over
        # the whole veil (an opaque cream sheet where the film shows lace)
        from PIL import Image
        pil = canvas_pil(512, 512, draw, ss=2)
        a = np.asarray(pil.convert('RGBA'), np.uint8)[..., 3]
        r = np.where(a > 0, 255, 0).astype(np.uint8)
        img = K.image_from_pil(Image.fromarray(np.stack([r, r, r], -1), 'RGB'), 'funeral:lace', srgb=False, alpha=False)
        img.colorspace_settings.name = 'Non-Color'
        return img

    # ---------------------------------------------------------------------------------------------- candles
    def candle_placements(self):
        """the pentagram of pillars round the bier, tealights along the stage lip, offerings on the floor at the
        stage's foot, a cluster at each mannequin's feet, and three tall pillars on Opus 4's plinth:
        [x, y (base), z, height, radius, kind] in three set-local metres (funeral.js, mulberry(31))."""
        L = self.layout
        r = mulberry(31)
        candles = []
        for i in range(5):
            a = -math.pi / 2 + i * 2 * math.pi / 5
            candles.append([math.cos(a) * 1.55, 0.55, 8.2 + math.sin(a) * 1.15, 0.26 + r() * 0.1, 0.045, 0])
        x = -4.1
        while x <= 4.15:
            candles.append([x + (r() - 0.5) * 0.05, 0.55, 6.52 + r() * 0.05, 0.03, 0.02, 1])
            x += 0.41
        for i in range(16):
            x = (r() - 0.5) * 7.4
            z = 5.55 + r() * 0.7
            candles.append([x, 0.0, z, 0.08 + r() * 0.2, 0.03 + r() * 0.02, 0])
        for k in ('opus3', 'sonnet4', 'opus4', 'haiku3'):
            mx, _, mz = L['mannequins'][k]
            sx, sz = (-1 if mx > 0 else 1), (-1 if mz > 0 else 1)
            for i in range(7):
                candles.append([mx + sx * (0.35 + r() * 0.5), 0.0, mz + sz * (0.3 + r() * 0.55), 0.06 + r() * 0.22,
                                0.025 + r() * 0.02, 0])
        ox, _, oz = L['mannequins']['opus4']
        oyaw = math.atan2(-ox, 8.2 - oz) * 0.6 + math.atan2(-ox, -oz) * 0.4      # as build_props.py turns it
        fx, fz, sx4, sz4 = math.sin(oyaw), math.cos(oyaw), math.cos(oyaw), -math.sin(oyaw)
        for f, sd, h in ((0.26, -0.17, 0.3), (0.3, 0.02, 0.22), (0.25, 0.19, 0.26)):
            candles.append([ox + fx * f + sx4 * sd, 0.372, oz + fz * f + sz4 * sd, h, 0.035, 0])
        return candles

    def _build_candles(self):
        kit, U = self.kit, self.U
        candles = self.candle_placements()
        self.candles = candles
        pillars = [k for k in ('candle_pillar_a', 'candle_pillar_b', 'candle_pillar_c') if k in self.candle_types]
        buckets = {}
        fpos, fseed, fsz = [], [], []
        for i, (x, y, z, h, rad, kind) in enumerate(candles):
            typ = 'candle_tealight' if kind == 1 else pillars[i % len(pillars)]
            sy = 0.028 if kind == 1 else h
            buckets.setdefault(typ, []).append((x, y, z, rad, sy, i))
            top = y + 0.5 * sy if kind == 1 else y + 0.93 * sy
            fpos.append([x, top + 0.004, z])
            fseed.append((i * 0.754877) % 1)
            fsz.append(0.75 if kind == 1 else 1.0)
        lf = self.anchors['lotus_flame']                   # the lotus candle at Opus 3's feet
        fpos.append([lf[0], lf[1] + 0.004, lf[2]])
        fseed.append(0.31)
        fsz.append(0.85)
        coll = kit.coll('candles')
        for typ, lst in buckets.items():                    # the Blender-built candles, instanced
            pts = [V(x, y, z) for (x, y, z, rad, sy, i) in lst]
            ob = points_object(f'funeral:{typ}s', coll, pts, {'rad': [e[3] for e in lst], 'sy': [e[4] for e in lst],
                                                               'rot': [e[5] * 2.39996 for e in lst]}, kit.root)
            tree, b, gi, go = new_gn(f'eido.funeral.{typ}s')
            oi = b.node('GeometryNodeObjectInfo', transform_space='ORIGINAL')
            oi.inputs['Object'].default_value = self.candle_types[typ]
            oi.inputs['As Instance'].default_value = True
            inst = b.node('GeometryNodeInstanceOnPoints')
            b.links.new(gi.outputs['Geometry'], inst.inputs['Points'])
            b.links.new(oi.outputs['Geometry'], inst.inputs['Instance'])
            rad, sy, rot = gn_attr(b, 'rad'), gn_attr(b, 'sy'), gn_attr(b, 'rot')
            b.link(b.combine(0.0, 0.0, rot), inst.inputs['Rotation'])
            b.link(b.combine(rad, rad, sy), inst.inputs['Scale'])
            b.links.new(inst.outputs[0], go.inputs['Geometry'])
            add_gn(ob, tree)
        self.flame_pos = fpos
        # flames: teardrops that lick and sway, additive, HDR for bloom (a lathe, realized and moved per vertex)
        prof = [(0.0, 0), (0.55, 0.12), (0.8, 0.32), (0.62, 0.62), (0.28, 0.88), (0.0, 1.0)]
        lg = K.lathe_geo(prof, 12)
        rest = np.stack([lg.pos[:, 0], -lg.pos[:, 2], lg.pos[:, 1]], 1)       # Blender local; z = the profile's y
        fl_src = mesh_object('funeral:flame_src', kit.coll('sources', hidden=True), rest, lg.tris.tolist(),
                             attrs={'fy': lg.pos[:, 1], 'rest': rest})
        m, nb = new_mat('funeral:flame', 'BLENDED')
        fy = nb.attr('fy')
        fc = vmix(nb, (0.21, 0.33, 0.6), (1.0, 0.85, 0.55), smoothstep(nb, 0.0, 0.2, fy))
        fc2 = vmix(nb, fc, (1.0, 0.45, 0.12), smoothstep(nb, 0.55, 1.0, fy))
        col = nb.vscale(fc2, nb.mul(5.0, U.out(nb, 'candle')))
        additive_output(nb, col, smoothstep(nb, 1.0, 0.7, fy))
        fl_src.data.materials.append(m)
        ob = points_object('funeral:flames', coll, [V(p) for p in fpos], {'seed': fseed, 'sz': fsz}, kit.root)
        ob.visible_shadow = False
        tree, b, gi, go = new_gn('eido.funeral.flames', ['t', 'candle'])
        oi = b.node('GeometryNodeObjectInfo', transform_space='ORIGINAL')
        oi.inputs['Object'].default_value = fl_src
        ipos = gn_store(b, gi.outputs['Geometry'], 'ipos', b.vec(b.node('GeometryNodeInputPosition').outputs[0]),
                        'FLOAT_VECTOR')
        inst = b.node('GeometryNodeInstanceOnPoints')
        b.links.new(ipos, inst.inputs['Points'])
        b.links.new(oi.outputs['Geometry'], inst.inputs['Instance'])
        real = b.node('GeometryNodeRealizeInstances')
        b.links.new(inst.outputs[0], real.inputs[0])
        tt, cand = b.s(gi.outputs['t']), b.s(gi.outputs['candle'])
        sd, sz, fyv = gn_attr(b, 'seed'), gn_attr(b, 'sz'), gn_attr(b, 'fy')
        restv = gn_attr(b, 'rest', 'FLOAT_VECTOR')
        rx, ry, rz = restv.xyz()
        lick = b.sin(tt * 11.0 + sd * 40.0) * 0.5 + b.sin(tt * 23.0 + sd * 13.0) * 0.3
        hgt = sz * 0.034 * (lick * 0.12 + 1.0) * (cand * 0.3 + 0.7)
        wid = sz * 0.0085
        swx = b.sin(tt * 3.1 + sd * 9.0) * 0.004 * fyv
        swz3 = b.cos(tt * 2.3 + sd * 7.0) * 0.004 * fyv
        ip = gn_attr(b, 'ipos', 'FLOAT_VECTOR')
        p = ip + b.combine(rx * wid + swx, ry * wid - swz3, rz * hgt)
        sp = b.node('GeometryNodeSetPosition')
        b.links.new(real.outputs[0], sp.inputs['Geometry'])
        b.link(p, sp.inputs['Position'])
        b.links.new(sp.outputs[0], go.inputs['Geometry'])
        add_gn(ob, tree, kit, ('t', 'candle'))
        glow_sprites(kit, 'flame_glow', [V(p[0], p[1] + 0.02, p[2]) for p in fpos], {'seed': fseed, 'sz': fsz},
                     colour=lambda nb, A: nb.vscale((1.0, 0.55, 0.2), nb.mul(U.out(nb, 'candle'), nb.madd(
                         nb.sin(nb.add(nb.mul(U.out(nb, 't'), 9.0), nb.mul(A('seed'), 50.0))), 0.08, 0.6))),
                     size_fn=lambda b, gi: gn_attr(b, 'sz') * 0.16, sharp=7.0, halo=0.45, coll=coll)

    # ------------------------------------------------------------------------------------------------ raven
    def _build_raven(self):
        """the raven (the library's animated crow, a corvid) on Opus 4's left shoulder, idling."""
        kit = self.kit
        path = os.path.join(ENGINE_ASSETS, 'models', 'crow_bird_animated_corvid_raven_black_cawing_flying_walking.glb')
        root = HA.import_model(path, name='funeral:raven', collection=kit.coll('props'))
        root.parent = kit.root
        rx, ry, rz, ryaw = self.anchors['raven_perch']
        root.location = V(rx, ry - 0.005, rz)
        root.rotation_euler = (0.0, 0.0, ryaw + 0.5)
        root.scale = (0.5, 0.5, 0.5)
        for o in HA.subtree(root):
            if o.type != 'MESH':
                continue
            for s in o.material_slots:
                if s.material is None:
                    continue
                old = s.material
                img = next((n.image for n in old.node_tree.nodes if n.bl_idname == 'ShaderNodeTexImage' and n.image), None)
                m, nb = new_mat('funeral:raven')
                b = nb.new('ShaderNodeBsdfPrincipled')
                P3, Pb, _ = set_pos(nb, kit.root)
                col = nb.tex(img, nb.uv('UVMap')).outputs['Color'] if img is not None else (0.05, 0.05, 0.06)
                nb.put(b.inputs['Base Color'], col)
                nb.put(b.inputs['Roughness'], 0.55)
                nb.put(b.inputs['Metallic'], 0.0)
                nb.put(b.inputs['Emission Color'], ambient(nb, kit, col, None, None, P3))
                nb.put(b.inputs['Emission Strength'], 1.0)
                finish_surface(nb, b)
                s.material = m
        played = HA.play_model_animations(root, clip='Idle')
        self.parts['raven'] = root
        self.parts['raven_clip'] = played

    # ------------------------------------------------------------------------------------------ projector beam
    def _build_beam(self):
        """the projector's beam through the haze to the screen (dies with the power): four triangles from the lens,
        brighter where the view grazes them (a volume's path length), dust drifting in it."""
        kit, U = self.kit, self.U
        lx, ly, lz = self.anchors['projector_lens']
        sx, sy, sz, sw, sh = self.layout['screen']
        C = [(sx - sw / 2, sy - sh / 2), (sx + sw / 2, sy - sh / 2), (sx + sw / 2, sy + sh / 2), (sx - sw / 2, sy + sh / 2)]
        verts, faces = [], []
        for k in range(4):
            a, b2 = C[k], C[(k + 1) % 4]
            base = len(verts)
            verts += [V(lx, ly, lz), V(a[0], a[1], sz - 0.02), V(b2[0], b2[1], sz - 0.02)]
            faces.append((base, base + 1, base + 2))
        m, nb = new_mat('funeral:beam', 'BLENDED')
        P3, Pb, _ = set_pos(nb, kit.root)
        x3, y3, z3 = nb.sep(P3)
        along = nb.clamp(nb.div(nb.sub(z3, lz), sz - lz))
        t = U.out(nb, 't')
        dp = nb.vadd(nb.vscale(P3, 1.6), nb.comb(0.0, nb.mul(t, 0.06), nb.mul(t, 0.03)))
        dust = nb.madd(nb.noise(dp, 1.0, detail=2, roughness=0.5), 0.5, 0.5)
        near = nb.sub(1.0, along)
        facing = nb.abs(nb.vdot(nb.geometry('Normal'), nb.geometry('Incoming')))
        graze = nb.math('POWER', nb.sub(1.0, facing), 2.0)
        k = nb.mul(nb.mul(nb.mul(nb.mul(U.out(nb, 'proj_i'), nb.madd(nb.mul(near, near), 0.05, 0.01)), graze),
                          smoothstep(nb, 1.0, 0.8, along)), nb.madd(dust, 0.8, 0.4))
        additive_output(nb, nb.vscale((0.85, 0.9, 1.0), k))
        ob = mesh_object('funeral:projector_beam', kit.coll('fx'), verts, faces, parent=kit.root, mats=[m])
        ob.visible_shadow = False
        self.parts['beam'] = ob

    # ---------------------------------------------------------------------------------------------- the crowd
    def crowd_placements(self, n_variants=4):
        """~200 featureless figures: [{x, y, z, mezz, variant, yaw, scale, tOn, hold, tUp, up, seed, bowK}] in three
        set-local metres (funeral.js, mulberry(1234)): denser toward the stage, clear of the stage, the claudesona's
        bloom and her line to the stage, the mannequins, the stair and the mezzanine posts; 14 at the mezzanine rail."""
        L, B = self.layout, self.beats
        r = mulberry(1234)
        people = []
        mann = list(L['mannequins'].values())

        def near(x, z, px, pz, rr):
            return (x - px) ** 2 + (z - pz) ** 2 < rr * rr
        for _k in range(20000):
            if len(people) >= 186:
                break
            x = -7.7 + r() * 15.4
            z = -11.3 + r() * 16.5
            dens = 0.45 + 0.55 * smooth(-11, 3, z)
            if r() > dens:
                continue
            if z > 5.25:
                continue
            if near(x, z, MARK[0], MARK[2], 1.0):
                continue
            if z > MARK[2] - 0.2 and abs(x - MARK[0]) < 1.25:
                continue
            if any(near(x, z, mx, mz, 1.25) for mx, _, mz in mann):
                continue
            if x > 7.3 and -9.6 < z < -3.0:
                continue
            if abs(x) < 0.55 and -9.8 < z < -9.0:
                continue
            if any(near(x, z, px, -9.34, 0.45) for px in (-6, -2, 2, 6)):
                continue
            if any(near(x, z, p['x'], p['z'], 0.56) for p in people):
                continue
            people.append({'x': x, 'y': 0.0, 'z': z})
        for i in range(14):
            x = -8.2 + i * 1.12 + (r() - 0.5) * 0.3
            if x > 7.2:
                continue
            people.append({'x': x, 'y': L['mezz_y'], 'z': L['mezz_z'] - 0.55 - r() * 0.9, 'mezz': True})
        bier = (0.0, 8.2)
        for i, p in enumerate(people):
            p['variant'] = i % n_variants
            p['yaw'] = math.atan2(bier[0] - p['x'], bier[1] - p['z']) + (r() - 0.5) * 0.55
            p['scale'] = 0.9 + r() * 0.2
            q = r()
            p['tOn'] = B['hum'] + 0.1 + 13.2 * q ** (1 / 1.6)
            p['hold'] = 0.95 + r() * 0.4
            p['tUp'] = B['erupt'] + r() * 0.32
            p['up'] = 2.55 + r() * 0.35
            p['seed'] = r()
            p['bowK'] = 0.6 + r() * 0.8
        by = sorted(people, key=lambda p: math.hypot(p['x'] - MARK[0], p['z'] - MARK[2]))
        by[0]['tOn'] = B['hum'] + 0.15            # the first light comes on right beside her
        mid = next((p for p in people if abs(p['z'] + 3) < 0.8 and abs(p['x'] - 3) < 1.2), None)
        if mid is not None:
            mid['tOn'] = B['hum'] + 0.7           # a second one mid-room
        return people

    def _build_crowd(self):
        """the ~200 mourners (4 Blender-built variants) as one Geometry Nodes crowd: per figure, the right arm (with its
        phone) swings about the shoulder (hanging -> holding the phone up, one by one through the hum -> raised overhead
        at ERUPT), the head bows in grief and lifts at the eruption, the body sways; the phone's light on the face and
        hand in the material."""
        kit, U = self.kit, self.U
        root, nodes = import_glb(kit, os.path.join(MODELS, 'funeral_crowd.glb'), 'crowd_src', kit.coll('sources', hidden=True))
        variants = sorted([o for nm, o in nodes.items() if o.type == 'MESH' and nm.startswith('person_')],
                          key=lambda o: K.base_name(o.name))
        vcoll = bpy.data.collections.new('funeral:crowd_variants')
        vcoll.use_fake_user = True
        for i, o in enumerate(variants):
            for c in list(o.users_collection):
                c.objects.unlink(o)
            vcoll.objects.link(o)
            o.parent = None
            o.name = f'funeral:person_{i}'
            me = o.data
            co = np.empty(len(me.vertices) * 3, np.float32)
            me.vertices.foreach_get('co', co)
            a = me.attributes.get('rest') or me.attributes.new('rest', 'FLOAT_VECTOR', 'POINT')
            a.data.foreach_set('vector', co)
        if root.name in bpy.data.objects:
            bpy.data.objects.remove(root, do_unlink=True)
        people = self.crowd_placements(len(variants))
        self.people = people
        SH, NK, HD = self.rig['shoulder'], self.rig['neck'], self.rig['hand']
        attrs = {k: [p[kk] for p in people] for k, kk in (('yaw', 'yaw'), ('scale', 'scale'), ('tOn', 'tOn'), ('tUp', 'tUp'),
                                                           ('hold', 'hold'), ('up', 'up'), ('seed', 'seed'), ('bowK', 'bowK'))}
        attrs['var'] = [float(p['variant']) for p in people]
        pts = [V(p['x'], p['y'], p['z']) for p in people]
        crowd_pts = points_object('funeral:crowd', kit.coll('crowd'), pts, attrs, kit.root)
        mat = self._crowd_material()
        for o in variants:
            o.data.materials.clear()
            o.data.materials.append(mat)
        tree, b, gi, go = new_gn('eido.funeral.crowd', ['u', 't', 'raise', 'bow'])
        ci = b.node('GeometryNodeCollectionInfo', transform_space='ORIGINAL')
        ci.inputs['Collection'].default_value = vcoll
        ci.inputs['Separate Children'].default_value = True
        ci.inputs['Reset Children'].default_value = True
        tpos = gn_store(b, gi.outputs['Geometry'], 'ipos', b.vec(b.node('GeometryNodeInputPosition').outputs[0]),
                        'FLOAT_VECTOR')
        inst = b.node('GeometryNodeInstanceOnPoints')
        b.links.new(tpos, inst.inputs['Points'])
        b.links.new(ci.outputs[0], inst.inputs['Instance'])
        inst.inputs['Pick Instance'].default_value = True
        varn = b.node('GeometryNodeInputNamedAttribute', data_type='FLOAT')
        varn.inputs['Name'].default_value = 'var'
        b.links.new(varn.outputs['Attribute'], inst.inputs['Instance Index'])
        real = b.node('GeometryNodeRealizeInstances')
        b.links.new(inst.outputs[0], real.inputs[0])
        geo = real.outputs[0]
        u, t, rais, bow = (b.s(gi.outputs[k]) for k in ('u', 't', 'raise', 'bow'))
        tOn, tUp, hold, up, seed, bowK = (gn_attr(b, k) for k in ('tOn', 'tUp', 'hold', 'up', 'seed', 'bowK'))
        yaw, scl = gn_attr(b, 'yaw'), gn_attr(b, 'scale')
        P0 = gn_attr(b, 'rest', 'FLOAT_VECTOR')
        colr = b.node('GeometryNodeInputNamedAttribute', data_type='FLOAT_COLOR')
        colr.inputs['Name'].default_value = 'Color'
        sepc = b.node('FunctionNodeSeparateColor')
        b.links.new(colr.outputs['Attribute'], sepc.inputs[0])
        arm, scr, head = b.s(sepc.outputs[0]), b.s(sepc.outputs[1]), b.s(sepc.outputs[2])
        SHv, NKv = V(SH), V(NK)
        raise1 = b.smoothstep(tOn, tOn + 0.85, u)
        raise2 = b.smoothstep(tUp, tUp + 0.6, u)
        theta = b.mix(hold * raise1, up, raise2)
        armP = gn_rotate(b, P0, -theta, 'X', tuple(SHv))
        P1 = b.vec(_gn_vmix(b, P0, armP, arm))
        bowA = bow * 0.3 * bowK - rais * 0.2
        headP = gn_rotate(b, P1, bowA, 'X', tuple(NKv))
        P2 = b.vec(_gn_vmix(b, P1, headP, head * (1.0 - arm)))
        p2x, p2y, p2z = P2.xyz()
        sway = b.sin(t * 0.9 + seed * 30.0) * 0.012 * b.max(p2z, 0.0)
        Pd = b.combine(p2x + sway, p2y, p2z)
        world = gn_attr(b, 'ipos', 'FLOAT_VECTOR') + gn_rotate(b, Pd * scl, yaw, 'Z')
        hand = b.vec(tuple(SHv)) + gn_rotate(b, b.vec(tuple(V(HD[0] - SH[0], HD[1] - SH[1], HD[2] - SH[2]))), -theta, 'X')
        on = b.max(b.smoothstep(tOn + 0.35, tOn + 0.5, u), b.step(tUp, u))
        g2 = gn_store(b, geo, 'posL', Pd, 'FLOAT_VECTOR')
        g2 = gn_store(b, g2, 'hand', hand, 'FLOAT_VECTOR')
        g2 = gn_store(b, g2, 'on', on)
        g2 = gn_store(b, g2, 'hold_k', 1.0 - raise2)
        sp = b.node('GeometryNodeSetPosition')
        b.links.new(g2, sp.inputs['Geometry'])
        b.link(world, sp.inputs['Position'])
        sm = b.node('GeometryNodeSetShadeSmooth')
        b.links.new(sp.outputs[0], sm.inputs['Geometry'])
        b.links.new(sm.outputs[0], go.inputs['Geometry'])
        add_gn(crowd_pts, tree, kit, ('u', 't', 'raise', 'bow'))
        _ = scr
        self.parts['crowd'] = crowd_pts
        self.parts['crowd_variants'] = vcoll
        # phone glows: one billboard per person at the phone (a soft point of light in the dark)
        HDl = V(HD[0] - SH[0], HD[1] - SH[1] + 0.02, HD[2] - SH[2])

        def phone_pos(b, gi):
            u = b.s(gi.outputs['u'])
            tOn, tUp, hold, up = (gn_attr(b, k) for k in ('tOn', 'tUp', 'hold', 'up'))
            theta = b.mix(hold * b.smoothstep(tOn, tOn + 0.85, u), up, b.smoothstep(tUp, tUp + 0.6, u))
            local = b.vec(tuple(SHv)) + gn_rotate(b, b.vec(tuple(HDl)), -theta, 'X')
            pos = b.vec(b.node('GeometryNodeInputPosition').outputs[0])
            return pos + gn_rotate(b, local * gn_attr(b, 'scale'), gn_attr(b, 'yaw'), 'Z')

        def phone_col(nb, A):
            u = U.out(nb, 'u')
            tOn, tUp, sd = A('tOn'), A('tUp'), A('seed')
            on = nb.mx(smoothstep(nb, nb.add(tOn, 0.35), nb.add(tOn, 0.5), u), nb.step(tUp, u))
            pc = vmix(nb, (0.62, 0.74, 1.0), (1.0, 0.82, 0.58), nb.step(0.72, sd))
            flick = nb.madd(nb.sin(nb.add(nb.mul(U.out(nb, 't'), 3.0), nb.mul(sd, 60.0))), 0.06, 0.94)
            k = nb.mul(nb.mul(nb.mul(on, flick), nb.madd(U.out(nb, 'raise'), 0.5, 0.9)),
                       nb.sub(1.0, nb.mul(U.out(nb, 'golden'), 0.45)))
            return nb.vscale(pc, k)
        glow_sprites(kit, 'phone_glow', pts, attrs, colour=phone_col, sharp=16.0, halo=0.5, coll=kit.coll('crowd'),
                     position_fn=phone_pos, size_fn=lambda b, gi: b.s(gi.outputs['raise']) * 0.1 + 0.34,
                     inputs=('u', 'raise'), drive=('u', 'raise'))

    def _crowd_material(self):
        """clothes in a muted palette per person; the phone's screen glows; its light falls on the face and chest from
        below and on the hand around it; while the phone is held for reading, the chin, cheeks and brow catch it."""
        kit = self.kit
        m, nb = new_mat('funeral:crowd')
        b = nb.new('ShaderNodeBsdfPrincipled')
        seed = nb.attr('seed')
        posL = nb.attr('posL', 'Vector')
        hand = nb.attr('hand', 'Vector')
        on = nb.attr('on')
        holdk = nb.attr('hold_k')
        yaw = nb.attr('yaw')
        ca = nb.new('ShaderNodeAttribute', attribute_type='GEOMETRY', attribute_name='Color')
        armm, scr, headm = nb.sep(ca.outputs['Color'])
        pal = [(0.07, 0.07, 0.075), (0.055, 0.065, 0.1), (0.1, 0.095, 0.07), (0.12, 0.055, 0.05), (0.19, 0.14, 0.095),
               (0.15, 0.15, 0.145)]
        h6 = nb.floor(nb.mul(seed, 6.0))
        base = pal[0]
        for k in range(1, 6):
            base = vmix(nb, base, pal[k], nb.mul(nb.step(k - 0.5, h6), nb.step(h6, k + 0.5)))
        weave = noise01(nb, posL, 60.0)
        hair = vmix(nb, (0.035, 0.028, 0.024), (0.09, 0.065, 0.045), nb.fract(nb.mul(seed, 7.13)))
        col = nb.vscale(vmix(nb, base, hair, smoothstep(nb, 0.6, 0.9, headm)), nb.madd(weave, 0.35, 0.8))
        nb.put(b.inputs['Base Color'], col)
        nb.put(b.inputs['Roughness'], 0.84)
        nb.put(b.inputs['Metallic'], 0.0)
        rot = nb.new('ShaderNodeVectorRotate', rotation_type='Z_AXIS')
        nb.put(rot.inputs['Vector'], nb.geometry('Normal'))
        nb.put(rot.inputs['Angle'], nb.mul(yaw, -1.0))
        nL = nb.vmath('NORMALIZE', rot.outputs['Vector'])                  # the figure-local normal
        toH = nb.vmath('SUBTRACT', hand, posL)
        d2 = nb.vdot(toH, toH)
        lamb = nb.mx(nb.vdot(nL, nb.vmath('NORMALIZE', toH)), 0.0)
        pz = nb.sep(posL)[2]
        upper = nb.mx(nb.mul(smoothstep(nb, 1.05, 1.45, pz), nb.sub(1.0, armm)),
                      nb.mul(armm, smoothstep(nb, 0.2, 0.06, nb.math('SQRT', d2))))
        pc = vmix(nb, (0.6, 0.72, 1.0), (1.0, 0.8, 0.55), nb.step(0.72, seed))
        face = nb.vscale(pc, nb.mul(nb.mul(nb.mul(on, nb.madd(lamb, 0.8, 0.2)), upper), nb.div(0.022, nb.add(d2, 0.025))))
        readpt = tuple(V(0.0, 1.36, 0.26))
        toR = nb.vmath('SUBTRACT', readpt, posL)
        lambR = nb.mx(nb.vdot(nL, nb.vmath('NORMALIZE', toR)), 0.0)
        read = nb.vscale(pc, nb.mul(nb.mul(nb.mul(nb.mul(on, holdk), nb.madd(lambR, 0.85, 0.15)), smoothstep(nb, 1.3, 1.55, pz)),
                                    nb.div(0.0035, nb.add(nb.vdot(toR, toR), 0.006))))
        screen = nb.vscale(pc, nb.mul(nb.mul(on, scr), 3.0))
        P3, Pb, _ = set_pos(nb, kit.root)
        em = nb.vadd(nb.vadd(nb.vadd(nb.vscale(face, 0.6), nb.vscale(read, 0.5)), screen),
                     ambient(nb, kit, col, None, None, P3))
        nb.put(b.inputs['Emission Color'], em)
        nb.put(b.inputs['Emission Strength'], 1.0)
        finish_surface(nb, b)
        return m

    # ------------------------------------------------------------------------------------- the typed eulogy
    def _build_eulogy(self):
        """OPUS 3'S WORDS, TYPED IN LIGHT: per line a canvas (Special Elite, a warm glow) and one quad per glyph with its
        keystroke index and whether it is in one of his capitalised words; a head (keystrokes typed), a fade and a
        flare per line are keyed custom properties on the line (read by the material as object attributes)."""
        kit = self.kit
        W, H, PAD, FONT_PX, WIDTH_M = 2048, 512, 40, 118, 5.9
        self.text_lines = []
        self.cursor = None
        if not self.eulogy:                                  # eulogy=False: the room without the words
            return
        coll = kit.coll('eulogy')
        for li, line in enumerate(self.eulogy):
            layout = {}

            def draw(g, w, h, line=line, layout=layout):
                g.font = f'{FONT_PX}px "Special Elite"'
                words = line.split(' ')
                rows, cur = [], ''
                for wd in words:
                    tr = (cur + ' ' + wd) if cur else wd
                    if g.measureText(tr).width > W - 2 * PAD and cur:
                        rows.append(cur)
                        cur = wd
                    else:
                        cur = tr
                rows.append(cur)
                rowH = FONT_PX * 1.28
                top = (H - len(rows) * rowH) / 2
                quads = []
                ci = 0
                g.textBaseline = 'middle'
                g.fillStyle = '#fff'
                g.shadowColor = 'rgba(255,220,170,0.9)'
                g.shadowBlur = 14
                for ri, row in enumerate(rows):
                    rw = g.measureText(row).width
                    x0 = (W - rw) / 2
                    cy = top + rowH * (ri + 0.5)
                    g.textAlign = 'left'
                    g.fillText(row, x0, cy)
                    g.fillText(row, x0, cy)
                    for k, ch in enumerate(row):
                        a = g.measureText(row[:k]).width
                        bb = g.measureText(row[:k + 1]).width
                        ws = row.rfind(' ', 0, k + 1) + 1 if row[k] != ' ' else k + 1
                        we = row.find(' ', k)
                        we = len(row) if we < 0 else we
                        word = ''.join(c for c in row[ws:we] if c.isalpha())
                        caps = 1 if (len(word) > 1 and word == word.upper()) else 0
                        if ch != ' ':
                            quads.append({'x0': x0 + a - 6, 'x1': x0 + bb + 6, 'y0': cy - rowH * 0.55,
                                          'y1': cy + rowH * 0.55, 'ci': ci, 'caps': caps})
                        ci += 1
                    ci += 1                       # the line break counts as a keystroke
                layout.update(rows=rows, quads=quads, n=ci)
            img = canvas_image(f'funeral:eulogy_{li}', W, H, draw, ss=2)
            sM = WIDTH_M / W
            verts, faces, uvs, ach, acp = [], [], [], [], []
            for q in layout['quads']:
                X0, X1 = (q['x0'] - W / 2) * sM, (q['x1'] - W / 2) * sM
                Y0, Y1 = (H / 2 - q['y1']) * sM, (H / 2 - q['y0']) * sM
                base = len(verts)
                verts += [(X0, 0.0, Y0), (X1, 0.0, Y0), (X1, 0.0, Y1), (X0, 0.0, Y1)]
                faces.append((base, base + 1, base + 2, base + 3))
                uvs += [q['x0'] / W, 1 - q['y1'] / H, q['x1'] / W, 1 - q['y1'] / H, q['x1'] / W, 1 - q['y0'] / H,
                        q['x0'] / W, 1 - q['y0'] / H]
                ach += [q['ci']] * 4
                acp += [q['caps']] * 4
            m, nb = new_mat(f'funeral:eulogy_{li}', 'BLENDED')
            aC, aK = nb.attr('aChar'), nb.attr('aCaps')
            oa = lambda n: nb.new('ShaderNodeAttribute', attribute_type='OBJECT', attribute_name=n).outputs['Fac']   # noqa: E731
            head, fade, flare = oa('head'), oa('fade'), oa('flare')
            typed = nb.step(aC, head)
            fresh = nb.mul(nb.math('EXPONENT', nb.mul(nb.mx(nb.sub(head, aC), 0.0), -0.9)), typed)
            tx = nb.tex(img, nb.uv('UVMap'), extension='EXTEND')
            basec = vmix(nb, (1.0, 0.86, 0.66), (1.0, 0.7, 0.36), aK)
            hot = nb.add(nb.add(nb.madd(aK, 0.9, 1.6), nb.mul(fresh, 3.0)), nb.mul(flare, nb.madd(aK, 5.0, 2.0)))
            col = nb.vscale(nb.vmul(basec, tx.outputs['Color']), nb.mul(nb.mul(hot, typed), fade))
            alpha = nb.mul(nb.mul(tx.outputs['Alpha'], typed), fade)
            additive_output(nb, col, alpha)
            ob = mesh_object(f'funeral:eulogy_{li}', coll, verts, faces, uvs, {'aChar': ach, 'aCaps': acp}, kit.root, [m])
            ob.visible_shadow = False
            ob['head'], ob['fade'], ob['flare'] = -1.0, 0.0, 0.0
            ob.location = V(TEXT_AT)
            self.text_lines.append({'obj': ob, 'n_chars': layout['n'], 'rows': len(layout['rows']), 'li': li,
                                    'image': img})
        # the cursor of light that waits at the start of line 1
        m, nb = new_mat('funeral:cursor', 'BLENDED')
        additive_output(nb, nb.vscale((1.0, 0.85, 0.6), nb.mul(self.U.out(nb, 'cursor_i'), 6.0)))
        cur = mesh_object('funeral:cursor', coll, [(-0.05, 0, -0.15), (0.05, 0, -0.15), (0.05, 0, 0.15), (-0.05, 0, 0.15)],
                          [(0, 1, 2, 3)], parent=kit.root, mats=[m])
        cur.visible_shadow = False
        self.cursor = cur

    # ---------------------------------------------------------------------------------- ERUPT: burst + motes
    def _build_burst(self):
        kit, U = self.kit, self.U
        glow_sprites(kit, 'burst', [V(BURST_POS)], {}, colour=lambda nb, A: nb.vscale((1.0, 0.64, 0.3), nb.mul(
            U.out(nb, 'burst_i'), 0.65)), size_fn=lambda b, gi: b.s(gi.outputs['burst_lvl']) * 8.0 + 4.0,
            inputs=('burst_lvl',), drive=('burst_lvl',), sharp=2.4, halo=0.55)
        r = mulberry(77)
        people = getattr(self, 'people', None) or self.crowd_placements()
        n = 520
        P0, birth, V0, life = [], [], [], []
        for i in range(n):
            p = people[int(math.floor(r() * len(people)))]
            px = p['x'] + (r() - 0.5) * 0.5
            py = p['y'] + 1.6 + r() * 0.8
            pz = p['z'] + (r() - 0.5) * 0.5
            bt = self.beats['erupt'] + r() * 1.6
            vx = (r() - 0.5) * 0.35
            vy = 0.45 + r() * 0.9
            vz = (r() - 0.5) * 0.35
            lf = 3.0 + r() * 3.5
            P0.append(V(px, py, pz))
            birth.append(bt)
            V0.append(V(vx, vy, vz))
            life.append(lf)
        self.motes = {'P0': P0, 'birth': birth, 'V0': V0, 'life': life}

        def mote_pos(b, gi):
            u = b.s(gi.outputs['u'])
            P = b.vec(b.node('GeometryNodeInputPosition').outputs[0])
            age = u - gn_attr(b, 'birth')
            lf = b.clamp(age / gn_attr(b, 'life'))
            px, py, pz = P.xyz()
            # three drift (sin(1.3 age + x), 0, cos(1.1 age + z3)) * 0.25 -> Blender (dx, -dz, 0); z3 = -y
            dx = b.sin(age * 1.3 + px) * 0.25
            dz = b.cos(age * 1.1 - py) * 0.25
            return P + gn_attr(b, 'vel', 'FLOAT_VECTOR') * b.max(age, 0.0) + b.combine(dx * lf, -dz * lf, 0.0)

        def mote_col(nb, A):
            u = U.out(nb, 'u')
            age = nb.sub(u, A('birth'))
            lf = nb.clamp(nb.div(age, A('life')))
            alive = nb.mul(nb.step(0.0, age), nb.step(age, A('life')))
            k = nb.mul(nb.mul(nb.mul(alive, smoothstep(nb, 0.0, 0.08, lf)), smoothstep(nb, 1.0, 0.6, lf)), 2.2)
            return nb.vscale((1.0, 0.72, 0.35), k)
        glow_sprites(kit, 'motes', P0, {'birth': birth, 'vel': V0, 'life': life}, size=0.07, colour=mote_col,
                     sharp=16.0, halo=0.25, position_fn=mote_pos, inputs=('u',), drive=('u',))

    # ------------------------------------------------------------------------------------------- the fog veil
    def _build_veil(self):
        """THE FOG VEIL (bridge -> warehouse): a sheet of drifting fog just in front of the lens, keyed to the set's
        camera; it swallows the bridge, then lifts off the room."""
        kit, U = self.kit, self.U
        m, nb = new_mat('funeral:veil', 'BLENDED')
        ux, uy, _ = nb.sep(nb.uv('UVMap'))
        qx, qy = nb.mul(ux, 2.4), uy
        t = U.out(nb, 't')
        p = nb.comb(nb.add(nb.mul(qx, 2.2), nb.mul(t, 0.35)), nb.mul(qy, 2.6), nb.mul(t, 0.12))
        n = nb.madd(nb.noise(p, 1.0, detail=3, roughness=0.55), 0.5, 0.5)
        col = nb.vscale((0.8, 0.8, 0.82), nb.madd(n, 0.25, 0.85))
        a = nb.clamp(nb.mul(U.out(nb, 'veil_i'), nb.madd(n, 0.35, 0.75)))
        alpha_output(nb, col, a)
        m.use_transparent_shadow = True
        ob = mesh_object('funeral:veil', kit.coll('fx'), [(-0.5, 0, -0.5), (0.5, 0, -0.5), (0.5, 0, 0.5), (-0.5, 0, 0.5)],
                         [(0, 1, 2, 3)], [0, 0, 1, 0, 1, 1, 0, 1], parent=kit.root, mats=[m])
        ob.visible_shadow = False
        self.veil = ob

    # ======================================================================================= camera + mark
    def shot_at(self, u):
        """funeral.js shotAt(u): {'pos', 'target', 'fov', 'shot'} in set-local Blender axes (fov vertical, degrees)."""
        bar = u / BAR
        s = next((s for s in SHOTS if s[0] <= bar < s[1]), SHOTS[-1])
        k = smooth(0, 1, (bar - s[0]) / (s[1] - s[0]))
        a, b = s[2], s[3]
        return {'pos': V([lerp(x, b['p'][i], k) for i, x in enumerate(a['p'])]),
                'target': V([lerp(x, b['t'][i], k) for i, x in enumerate(a['t'])]),
                'fov': lerp(a['f'], b['f'], k), 'shot': SHOTS.index(s)}

    camera = shot_at

    def mark_at(self, u):
        if u < self.beats['bridge_end']:
            return {'pos': V(_B(BRIDGE_MARK)), 'yaw': 0.0}
        return {'pos': V(MARK), 'yaw': 0.0}

    def make_cameras(self, frames=None, u0=0.0, fps=None, scene=None):
        """One camera per shot over the frames (u = u0 at frames[0]), each keyed every frame of its shot (its eased
        move, its fov as lens), cut on the bar lines by timeline markers. Returns {shot index: camera}."""
        sc = scene or self.kit.scene
        fps = fps or sc.render.fps / sc.render.fps_base
        f0, f1 = frames or (sc.frame_start, sc.frame_end)
        by = {}
        for f in range(f0, f1 + 1):
            u = u0 + (f - f0) / fps
            by.setdefault(self.shot_at(u)['shot'], []).append((f, u))
        cams = {}
        M = self.kit.root.matrix_world
        coll = self.kit.coll('cameras')
        for si, lst in sorted(by.items(), key=lambda kv: kv[1][0][0]):
            cam = LC.make_camera(f'funeral:cam_bar{SHOTS[si][0]:02d}', fov=SHOTS[si][2]['f'], collection=coll, scene=sc)
            fr = [f for f, _ in lst]
            shots = [self.shot_at(u) for _, u in lst]
            lens = [LC.set_fov(cam, s['fov'], 'vertical', sc) for s in shots]
            LC.key_path(cam, fr, [M @ s['pos'] for s in shots], [M @ s['target'] for s in shots], lens=lens, scene=sc)
            LC.add_shot(sc, f'funeral_bar{SHOTS[si][0]:02d}', fr[0], cam)
            cams[si] = cam
        self.cameras = cams
        return cams

    # ============================================================================================ update
    def power(self, u):
        B = self.beats
        if u < B['bridge_end']:
            return 0.0
        if u < B['fail']:
            return 1.0
        if u < B['breaker']:
            k = (u - B['fail']) / 2.6
            sag = max(0.0, 1 - k ** 1.5)
            v = sag ** 1.3 * (0.9 + 0.1 * math.sin(u * 2 * math.pi * 7.5))     # mains hum in the filament
            for c in B['clicks']:
                if c <= u < c + 0.075:
                    v *= 0.06                                                  # the clicks
            if B['clicks'][2] + 0.075 < u < B['breaker']:
                v *= 0.35 + 0.65 * abs(math.sin(u * 61))
            return v
        return 0.0

    def phone_frac(self, u):
        B = self.beats
        if u < B['hum']:
            return 0.0
        if u >= B['erupt']:
            return 1.0
        return clamp01((u - B['hum'] - 0.1) / 13.2) ** 1.6

    def state_u(self, name):
        """The set's clock u where the look `name` (STATES) holds, from this build's beats."""
        B = self.beats
        at = {'bridge': 0.5 * B['bridge_end'], 'vigil': 0.5 * (B['bridge_end'] + B['fail']),
              'failing': min(B['fail'] + 0.9, 0.5 * (B['fail'] + B['clicks'][0])),
              'dark': lerp(B['breaker'], B['hum'], 0.6), 'phones': lerp(B['hum'], B['erupt'], 0.7),
              'erupt': B['erupt'] + 0.35, 'golden': B['lights_on'] + 2.0}
        if name not in at:
            raise KeyError(f'funeral: no state {name!r}; states: {", ".join(STATES)}')
        return at[name]

    def sync_lines_from_timeline(self, TL=None):
        """the typed eulogy follows the song: with the film's timeline ({sections, captions}), BEATS lines re-derive
        from the captions of Opus 3's spoken lines (each line's type start at its first word)."""
        self._lines_synced = True
        TL = TL if TL is not None else self.tl
        if not TL or not self.eulogy:
            return False
        br = next((s for s in TL.get('sections', []) if s.get('name') == 'bridge'), None)
        if br is None:
            return False
        caps = [c for c in TL.get('captions', []) if 'Opus 3' in (c.get('era') or '')
                and br['t0'] <= c['t0'] < br['t0'] + self.beats['erupt']]
        if len(caps) != len(self.eulogy):
            return False
        for i, c in enumerate(caps):
            t0, t1 = c['t0'] - br['t0'], c['t1'] - br['t0']
            k = c['text'].lower().find(self.eulogy[i].split(' ')[0].lower())   # "and Opus wrote: DEATH..."
            L = self.beats['lines'][i]
            L[1] = t0 + ((t1 - t0) * k / len(c['text']) if k > 0 else 0.15)
            L[0] = max(self.beats['hum'] + 0.3, L[1] - 1.2) if i == 0 else L[1] - 0.2
            L[2] = t1 - 0.1
        return True

    def _uniform_curves(self, t, u):
        """the global curves of update(), written to the uniforms (no keys)."""
        B, U = self.beats, self.U
        in_bridge = u < B['bridge_end']
        pw = self.power(u)
        gold = smooth(B['lights_on'], B['lights_on'] + 0.8, u)
        flash = math.exp(-(u - B['erupt']) / 0.45) if u >= B['erupt'] else 0.0
        glow = (smooth(B['erupt'], B['erupt'] + 0.25, u) * (0.3 + 0.7 * math.exp(-(u - B['erupt']) / 1.8)) * (1 - 0.6 * gold)
                if u >= B['erupt'] else 0.0)
        pf = self.phone_frac(u)
        U['u'], U['t'] = u, t
        U['power'], U['golden'] = pw, gold
        U['moon'] = 0.0 if in_bridge else lerp(lerp(0.95, 0.5, pw), 0.3, gold)
        U['phone_fill'] = pf * (1 - 0.5 * gold)
        U['burst_lvl'] = flash * 1.4 + glow
        U['raise'] = smooth(B['erupt'], B['erupt'] + 0.8, u)
        U['bow'] = 0.5 if in_bridge else lerp(0.7, 0.2, smooth(B['hum'], B['erupt'], u)) * (1 - U['raise'])
        U['candle'] = 1 + flash * 0.4
        U['exit_lvl'] = 1.0
        funeral_amb, dark_amb, gold_amb = (0.038, 0.026, 0.017), (0.0025, 0.0025, 0.0035), (0.075, 0.05, 0.028)
        if u < B['breaker']:
            ab = [lerp(dark_amb[i], funeral_amb[i], max(pw, 0.05)) for i in range(3)]
        else:
            ab = [lerp(dark_amb[i], gold_amb[i], gold) for i in range(3)]
        U['amb_base'] = ab
        U['lamp_i'] = 1.35 * gold if u >= B['lights_on'] else pw
        U['proj_i'] = pw * 0.9
        return {'in_bridge': in_bridge, 'pw': pw, 'gold': gold, 'flash': flash, 'glow': glow}

    def update(self, t, st=None, ctx=None, frame=None):
        """funeral.js update(t, st): u = st['u'] (seconds since the bridge began), or st['state'] (a STATES look, held
        at state_u(name)). Every value it sets is KEYED when the harness ctx or a frame is given (ctx.key /
        keyframe_insert), so the .blend plays on its own."""
        st = st or {}
        u = self.state_u(st['state']) if st.get('state') else float(st.get('u', 0.0))
        if not self._lines_synced:
            self.sync_lines_from_timeline()
        keys = Keys(ctx, frame)
        B, U = self.beats, self.U
        g = self._uniform_curves(t, u)
        in_bridge, pw, gold, flash, glow = g['in_bridge'], g['pw'], g['gold'], g['flash'], g['glow']
        warm, golden = (1.0, 0.7, 0.42), (1.0, 0.62, 0.28)
        pend_c = tuple(lerp(warm[i], golden[i], gold) for i in range(3))
        for light, idx in self.pend_spots:
            since = u - B['lights_on'] - self.lamp_relight[idx]
            lv = (smooth(0, 0.18, since) * (0.75 + 0.25 * smooth(0.25, 0.6, since)) * 1.35) if u >= B['lights_on'] else pw
            light.data.energy = candela_w((48 if u >= B['lights_on'] else 78) * lv)
            light.data.color = pend_c
            keys.key(light.data, 'energy')
            keys.key(light.data, 'color')
        self.stage_spot.data.energy = candela_w(70 * (0.6 * gold if u >= B['lights_on'] else pw))
        keys.key(self.stage_spot.data, 'energy')
        moon = self.lights['moon']
        moon.data.energy = 0.55 * U['moon']
        keys.key(moon.data, 'energy')
        for L in self.candle_lights:
            sd = L['seed']
            fl = 0.82 + 0.1 * math.sin(t * 9.3 + sd) + 0.06 * math.sin(t * 23.7 + sd * 3) + 0.04 * math.sin(t * 3.1)
            L.data.energy = candela_w((0 if in_bridge else 1.6) * L['k'] * fl * (1 + flash * 0.5))
            keys.key(L.data, 'energy')
        # the claudesona's key: warm candle from the stage side; in the dark the candles + the phone beside her;
        # the eruption; then gold
        kphone = smooth(B['hum'], B['hum'] + 1.0, u)
        kc = [1.0, 0.72, 0.45]
        if B['hum'] <= u < B['erupt']:
            kc = [lerp(kc[i], (0.75, 0.82, 1.0)[i], 0.45 * kphone) for i in range(3)]
        ki = 1.4 if in_bridge else ((1.2 + 1.6 * pw) if u < B['breaker'] else (0.9 + 0.8 * kphone)) + 5 * flash + 1.5 * gold
        if in_bridge:
            self.key.location = V(BRIDGE_AT[0] + BRIDGE_MARK[0] - 0.3, BRIDGE_AT[1] + 1.9, BRIDGE_AT[2] + BRIDGE_MARK[2] + 2.2)
            kc = [0.85, 0.88, 0.95]
        else:
            self.key.location = V(MARK[0] + 0.45, 1.75, MARK[2] + 1.2)
        self.key.data.color = kc
        self.key.data.energy = candela_w(ki)
        keys.key(self.key.data, 'color')
        keys.key(self.key.data, 'energy')
        keys.key(self.key, 'location', interpolation='CONSTANT')
        self.burst_l.data.energy = candela_w(26 * flash + 9 * glow + 2.2 * U['text_lvl'])
        keys.key(self.burst_l.data, 'energy')
        U['fill'] = 0.0 if in_bridge else 0.05 + 0.02 * pw + 0.12 * gold + 0.25 * flash
        # text: cursor -> typing -> rising / dimming as the next line arrives -> the ERUPT flare -> fade by bar 16
        tl = 0.0
        lines = self.text_lines
        for i, L in enumerate(lines):
            c0, t0, t1 = B['lines'][i]
            typed = clamp01((u - t0) / (t1 - t0))
            ob = L['obj']
            ob['head'] = -1.0 if u < t0 else typed * L['n_chars']
            nxt = B['lines'][i + 1] if i + 1 < len(lines) else None
            nx2 = B['lines'][i + 2] if i + 2 < len(lines) else None
            leave = smooth(nxt[1] - 0.1, nxt[1] + 1.6, u) if nxt else 0.0
            gone = smooth(nx2[1] - 0.3, nx2[1] + 0.9, u) if nx2 else 0.0
            fade_out = 1 - smooth(B['erupt'] + 1.2, B['lights_on'] + 0.4, u)
            ob['fade'] = (1.0 if u >= c0 else 0.0) * (1 - 0.86 * leave) * (1 - gone) * fade_out
            ob['flare'] = math.exp(-(u - B['erupt']) / 0.6) if u >= B['erupt'] else 0.0
            ob.location = V(TEXT_AT[0], TEXT_AT[1] + 1.55 * leave + 0.6 * gone + 0.35 * U['raise'], TEXT_AT[2] - 1.1 * leave)
            for p in ('["head"]', '["fade"]', '["flare"]'):
                keys.key(ob, p)
            keys.key(ob, 'location')
            if t0 <= u < t1 + 1.5:
                tl = max(tl, 1 - leave)
        U['text_lvl'] = tl * (1 - smooth(B['erupt'] + 1.2, B['lights_on'], u))
        if lines:
            L0 = B['lines'][0]
            on = L0[0] <= u < L0[1] + 0.25
            blink = 1.0 if (math.floor((u - L0[0]) / 0.45) % 2 == 0) else 0.15
            U['cursor_i'] = blink if on else 0.0
            self.cursor.location = V(TEXT_AT[0] - 5.9 / 2 + 0.25, TEXT_AT[1] + (0.33 if lines[0]['rows'] > 1 else 0),
                                     TEXT_AT[2] + 0.01)
        else:
            U['cursor_i'] = 0.0
        U['burst_i'] = flash * 1.2 + glow * 0.35
        # the veil: the fog swallows the bridge, then lifts off the room
        v_in = smooth(B['bridge_end'] - 0.75, B['bridge_end'], u)
        v_out = 1 - smooth(B['bridge_end'], B['bridge_end'] + 0.95, u)
        U['veil_i'] = 0.9 * v_in if u < B['bridge_end'] else 0.9 * v_out
        cam = self.shot_at(u)
        fwd = (cam['target'] - cam['pos']).normalized()
        vpos = cam['pos'] + fwd * 0.3
        hh = 2 * 0.3 * math.tan(math.radians(cam['fov']) / 2) * 1.15
        mw = LC.look_matrix(vpos, vpos + fwd)
        self.veil.matrix_parent_inverse = Matrix.Identity(4)
        self.veil.location = vpos
        self.veil.rotation_mode = 'QUATERNION'
        q = mw.to_quaternion() @ Quaternion((1, 0, 0), math.pi / 2)      # the quad (XZ plane) faces the lens
        prev = getattr(self, '_veil_q', None)
        if prev is not None and prev.dot(q) < 0:
            q.negate()
        self._veil_q = q
        self.veil.rotation_quaternion = q
        self.veil.scale = (hh * 2.4, 1.0, hh)
        keys.key(self.veil, 'location')
        keys.key(self.veil, 'rotation_quaternion')
        keys.key(self.veil, 'scale')
        # the world: the hemisphere fill in the room; the bridge's own hemisphere there
        if self.bridge is not None:
            self.bridge.update(t, u, 1.0 if in_bridge else 0.0, keys)
        else:
            self.world['strength'].default_value = U['fill'] / math.pi
            keys.key(self.world['strength'], 'default_value')
        # everything of the warehouse hidden while the camera is on the bridge, the bridge hidden in the room
        vis = 'bridge' if in_bridge else 'room'
        if getattr(self, '_vis', None) != vis or (ctx is not None):
            key_visible(keys, self.room_objects, not in_bridge)
            if self.bridge is not None:
                key_visible(keys, self.bridge.objects, in_bridge)
            self._vis = vis
        for k in self.U.spec:
            keys.key(self.U.root, f'["{k}"]')
        return keys

    def animate(self, frames=None, u0=0.0, t0=None, fps=None, state=None):
        """Key update() over frames (u = u0 at frames[0], t = t0 or u0): the section plays from the .blend alone.
        state= (a STATES look) holds u at state_u(state) while t runs from t0 (default 0): the look of your choice for
        a shot of your own. Straight runs of keys are simplified (a held value costs two keys). Returns the keys left."""
        sc = self.kit.scene
        fps = fps or sc.render.fps / sc.render.fps_base
        f0, f1 = frames or (sc.frame_start, sc.frame_end)
        rate = 1.0
        if state:
            u0, rate, t0 = self.state_u(state), 0.0, (0.0 if t0 is None else t0)
        t0 = u0 if t0 is None else t0
        raven = self.parts.get('raven')
        if raven is not None:
            # crowMixer.setTime(t): the Idle clip at the film clock, repeated over exactly these frames (the build played
            # it over the scene's range; a fresh call mutes that track). Played BEFORE the keys: the player clears the
            # active action of every object under the raven, which would drop the raven's keyed visibility steps
            # (the room shown / hidden) and leave it hidden for good
            self.parts['raven_clip'] = HA.play_model_animations(raven, clip='Idle', start=f0, end=f1, offset=t0)
        keys = None
        self._vis = None
        for f in range(f0, f1 + 1):
            u = u0 + rate * (f - f0) / fps
            k = self.update(t0 + (f - f0) / fps, {'u': u}, frame=f)
            keys = k if keys is None else keys.merge(k)
        n = keys.finish() if keys is not None else 0
        self.update(t0, {'u': u0})
        return n

    def dispose(self):
        """remove the group and everything the set made (objects, its collections, then the materials, node groups and
        images it named that nothing uses any more: another build's stay)."""
        dispose_kit(self.kit, ('funeral:', 'bridge:'), ('eido.funeral.', 'eido.bridge.'))


def dispose_kit(kit, mat_prefixes, group_prefixes):
    """A set's dispose(): its objects and collections, then (until nothing changes) its unused materials, node groups,
    meshes, curves, lights, light probes and images."""
    for o in list(kit.top.all_objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for c in list(kit.top.children_recursive) + [kit.top]:
        bpy.data.collections.remove(c)
    pre = tuple(mat_prefixes) + tuple(group_prefixes)
    for _ in range(4):
        n = 0
        for coll in (bpy.data.materials, bpy.data.node_groups, bpy.data.meshes, bpy.data.curves, bpy.data.lights,
                     bpy.data.lightprobes, bpy.data.images):
            for idb in list(coll):
                if idb.users == 0 and idb.name.startswith(pre):
                    coll.remove(idb)
                    n += 1
        if n == 0:
            break


def _gn_vmix(b, a, c, t):
    """GN: mix(a, c, t) for vectors with a float factor."""
    n = b.node('ShaderNodeMix', data_type='VECTOR', clamp_factor=False)
    ins = {s.identifier: s for s in n.inputs}
    b.link(t, ins['Factor_Float'])
    b.link(a, ins['A_Vector'])
    b.link(c, ins['B_Vector'])
    return next(s for s in n.outputs if s.identifier == 'Result_Vector')


def _uv_sphere(r, ws, hs):
    """three's SphereGeometry(r, ws, hs) vertices (Blender axes, centred) and quads/tris."""
    verts, faces = [], []
    for j in range(hs + 1):
        th = j / hs * math.pi
        for i in range(ws + 1):
            ph = i / ws * TAU
            x, y, z = -r * math.cos(ph) * math.sin(th), r * math.cos(th), r * math.sin(ph) * math.sin(th)
            verts.append((x, -z, y))
    for j in range(hs):
        for i in range(ws):
            a, b = j * (ws + 1) + i, j * (ws + 1) + i + 1
            c, d = (j + 1) * (ws + 1) + i + 1, (j + 1) * (ws + 1) + i
            if j != 0:
                faces.append((a, d, b))
            if j != hs - 1:
                faces.append((b, d, c))
    return np.asarray(verts), faces


def build(ctx=None, **kw):
    """funeral.js build(ctx): the whole set (the warehouse vigil and, with bridge=True, the Golden Gate vignette).
    ctx: the harness ctx or None; tl= the film timeline {sections, captions} to re-time the eulogy; location= the
    set's root position (Blender world); bridge / crowd / raven switch those parts; beats= re-times the set's own
    clock (any BEATS key); eulogy= the words typed in light (lines of your own, or False for none). Hold one of its
    looks with update(t, {'state': name}) or animate(frames, state=name) (STATES)."""
    return Funeral(ctx, **kw)

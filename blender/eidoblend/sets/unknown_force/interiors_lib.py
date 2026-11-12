"""interiors_lib: shared helpers for the two UNKNOWN FORCE interiors (quiet_room.py, showroom.py), the Blender 5.2 EEVEE
edition of eidoverse/sets/unknown_force/interiors_lib.js.

The WebGPU edition drew its canvas art with @napi-rs/canvas (Skia) and uploaded it as mip-mapped DataTextures. Here the
same drawing code runs on `Context2D`, a canvas-2D context written on numpy + Pillow (paths, strokes with round caps,
joins and dashes, gradients, globalAlpha, save / restore / translate / rotate, fillText with the bundled fonts,
getImageData / putImageData). The art modules port line for line, every stroke lands where Skia put it (the mulberry32
streams match bit for bit), and the result becomes a packed Blender image. Blender builds the mip chains itself.

    from eidoblend.sets.unknown_force import interiors_lib as L
    N = L.napi()                                    # the UF font families (bundled TTFs)
    cv, ctx = L.canvas(N, 1536, 768)
    L.board_base(ctx, 1536, 768, L.rng(7), ghosts=[{'t': 'priors', 'x': 0.3, 'y': 0.3, 's': 0.05}])
    L.marker(ctx, 'P(DOOM) = 0.37', 60, 200, size=120, r=L.rng(8))
    img = L.canvas_texture(cv, name='my_board')     # a bpy Image (packed), canvas top at v = 1

The canvas half (everything above `data_texture`) is plain Python: it runs in the system Python as well as Blender's.
The Blender half:

  images      data_texture / canvas_texture / derived_texture / board_roughness: pixels -> packed bpy Images
  PBR sets    acg(id): an AmbientCG set from the shared library ({'map', 'normalMap', 'roughnessMap', 'aoMap'?})
  noise       noise_texture(): the four periodic fBm channels as one packed Non-Color image (byte-exact with the JS)
  geometry    three r184's Box / Plane / Cylinder / Cone / Sphere / RoundedBox / Shape / Extrude / Tube geometries and
              CatmullRomCurve3, in three's axes (Geo: numpy positions, normals, uvs, index), box_uv, clean,
              merge_geometries, merge_vertices
  scene graph Node / MeshNode / InstancedMeshNode / LightNode (three's Object3D, position + rotation + scale, children),
              merge_static (one mesh per material, as mergeStatic), and SetBuilder.emit, which makes the Blender
              objects once: three (x, y, z) -> Blender (x, -z, y), meshes, Empties, lights with Track To targets
  environment equirect_env(W, H, paint, root=): the LDR equirect painted from a direction function, as the set's
              World: it lights the set through EEVEE (the room's volume probe, the probes' reflections), its lookup
              turning with the set's root; env_switch(scene, sets): several sets lit by their envs in one scene,
              switched with their cuts (show(visible, frame) keys it); a set's probe always bakes with its set alone
  materials   ShaderGraph + V: TSL written as shader nodes (uv(), position_local(), texture(), mix, smoothstep, ...),
              uniforms as custom properties on the set's root read through one-variable drivers, and
              material_kit() with tri / keyed / pbr / solid, the recipes both interiors use
  lights      LightNode in three's units: candela -> W = 4 pi cd (pixel parity, measured: a 4 pi W point at 1 m on
              white diffuse renders 0.3145, three's 1 cd renders 1 / pi), lux -> sun strength 1:1; three's spot cone
              and penumbra -> spot_size and an exact spot_blend; distance -> custom cutoff distance (EEVEE's window
              is three's); decay != 2 -> inverse square matched at the light's target
  keys        Keyer: what update() changes, keyed at a frame (LINEAR), through ctx.key when a scene ctx is given
  the set     InteriorSet: what both builds return (a dict of the engine's contract whose keys read as attributes,
              show / show_part / make_camera / eevee_settings / bake_probes / dispose, and animate: the set keyed
              over a frame range on its own clock); scene_and_ctx (build(ctx) or build(scene)); make_camera +
              cam_to_blender (set cams, vertical fov); camera_pixel_angle (fwidth's scale for a camera)
  options     a new piece's own use of the sets: state_curve and frame_list (animate's curves and frames),
              override_canvas + check_art (build(art={canvas: painter, image or array}) redraws any of a set's
              canvases), media_image (a movie, an image sequence or a still for a screen)

Axes: geometry and the scene graph work in three.js's axes (+Y up), so the sets port number for number; emission
converts each point once, (x, y, z) -> Blender (x, -z, y), and object transforms likewise (common.from_three).
Everything is deterministic: seeded RNG only.
"""
from __future__ import annotations

import math
import os
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote, urlparse

import numpy as np

REPO = Path(__file__).resolve().parents[4]
FONT_DIR = REPO / 'eidoverse' / 'assets' / 'fonts'


def fs_path(u) -> str:
    """A file URL (or a path) as a filesystem path: interiors_lib.js's fsPath (drops the leading slash before C:/)."""
    s = str(u)
    if s.startswith('file:'):
        p = unquote(urlparse(s).path)
        return p[1:] if re.match(r'^/[A-Za-z]:/', p) else p
    return s


# ------------------------------------------------------------------------------------------------ small maths
def clamp01(x):
    return max(0.0, min(1.0, x))


def smooth(x):
    x = clamp01(x)
    return x * x * (3 - 2 * x)


def lerp(a, b, k):
    return a + (b - a) * k


def ramp(x, a, b):
    return clamp01((x - a) / (b - a))


_M32 = 0xFFFFFFFF


class Rng:
    """mulberry32, bit for bit the engine's L.rng(seed): r() -> [0, 1). take(n) draws the next n values at once."""

    __slots__ = ('a',)

    def __init__(self, seed):
        self.a = int(seed) & _M32

    def __call__(self):
        a = (self.a + 0x6D2B79F5) & _M32
        self.a = a
        t = ((a ^ (a >> 15)) * (1 | a)) & _M32
        t = ((t + (((t ^ (t >> 7)) * (61 | t)) & _M32)) & _M32) ^ t
        return ((t ^ (t >> 14)) & _M32) / 4294967296.0

    def peek(self, n):
        """The next n values without drawing them (numpy, float64)."""
        k = np.arange(1, n + 1, dtype=np.uint64)
        a = (np.uint64(self.a) + k * np.uint64(0x6D2B79F5)) & np.uint64(_M32)
        m = np.uint64(_M32)
        t = ((a ^ (a >> np.uint64(15))) * (np.uint64(1) | a)) & m
        t = (((t + (((t ^ (t >> np.uint64(7))) * (np.uint64(61) | t)) & m)) & m) ^ t)
        return ((t ^ (t >> np.uint64(14))) & m).astype(np.float64) / 4294967296.0

    def skip(self, n):
        self.a = (self.a + int(n) * 0x6D2B79F5) & _M32

    def take(self, n):
        v = self.peek(n)
        self.skip(n)
        return v


def rng(seed) -> Rng:
    """mulberry32 (interiors_lib.js's rng): deterministic, the same stream as the WebGPU edition."""
    return Rng(seed)


def pcg_hash(seed):
    """three's TSL hash(seed) (src/nodes/math/Hash.js, PCG on u32(seed)), exactly, in numpy (scalar or array in,
    float64 out, [0, 1]). The shader side (ShaderGraph.hash) is Blender's White Noise: the same distribution, other
    values, because shader nodes have no integer bit operations. Where the argument is known at build time (a hash of
    instanceIndex), compute it here and hand it to the shader as an instance attribute
    (InstancedMeshNode.set_instance_attr), and the same instances get the same values as in the engine."""
    s = np.clip(np.trunc(np.asarray(seed, np.float64)), 0, _M32)          # WGSL u32(f32): truncate, saturate
    m = np.uint64(_M32)
    st = (s.astype(np.uint64) * np.uint64(747796405) + np.uint64(2891336453)) & m
    word = (((st >> ((st >> np.uint64(28)) + np.uint64(4))) ^ st) * np.uint64(277803737)) & m
    res = ((word >> np.uint64(22)) ^ word) & m
    return res.astype(np.float32).astype(np.float64) / 4294967296.0      # f32(result) * 2^-32, as the shader rounds


# ------------------------------------------------------------------------------------------------ fonts
# the families interiors_lib.js registered under 'UF *' names (napi()), plus Georgia (bundled with the repo)
FAMILIES = {
    'UF Kalam Bold': 'Kalam-Bold.ttf', 'UF Kalam': 'Kalam-Regular.ttf', 'UF Caveat Brush': 'CaveatBrush-Regular.ttf',
    'UF Special Elite': 'SpecialElite-Regular.ttf', 'UF Black Ops': 'BlackOpsOne-Regular.ttf',
    'UF Rajdhani': 'Rajdhani-Bold.ttf', 'UF Michroma': 'Michroma-Regular.ttf', 'UF Mono': 'ShareTechMono-Regular.ttf',
    'UF Orbitron': 'Orbitron.ttf', 'UF Exo': 'Exo2.ttf',
}
STYLED = {'Georgia': {'': 'georgia.ttf', 'bold': 'georgiab.ttf', 'italic': 'georgiai.ttf', 'bold italic': 'georgiaz.ttf'}}


class FontMetrics:
    """A TrueType font's own horizontal metrics, read from the file, so canvas text is laid out as Skia lays it out:
    the cmap (characters -> glyphs), the unhinted advances (hmtx: Skia measures canvas text with linear metrics) and
    the pair kerning of the GPOS 'kern' feature (latn or DFLT script, default language), which HarfBuzz applies in
    Skia's fillText and measureText. Pillow without Raqm applies neither (its basic layout adds hinted advances).
    Ligatures (GSUB) are not applied. Values in font units; upem converts."""

    def __init__(self, path):
        import struct
        self.path = str(path)
        b = Path(path).read_bytes()
        self._b, self._u16, self._s16, self._u32 = b, struct.Struct('>H'), struct.Struct('>h'), struct.Struct('>L')
        n = self.u16(4)
        self.tables = {b[12 + 16 * i:16 + 16 * i].decode('latin1'): self.u32(20 + 16 * i) for i in range(n)}
        self.upem = self.u16(self.tables['head'] + 18)
        nh = self.u16(self.tables['hhea'] + 34)
        hm = self.tables['hmtx']
        self.adv = [self.u16(hm + 4 * i) for i in range(nh)]
        self.cmap = self._read_cmap()
        self.lookups = self._read_kern_lookups() if 'GPOS' in self.tables else []

    def u16(self, o):
        return self._u16.unpack_from(self._b, o)[0]

    def s16(self, o):
        return self._s16.unpack_from(self._b, o)[0]

    def u32(self, o):
        return self._u32.unpack_from(self._b, o)[0]

    # the cmap ----------------------------------------------------------------------------------------------
    def _read_cmap(self):
        base = self.tables['cmap']
        subs = {}
        for i in range(self.u16(base + 2)):
            r = base + 4 + 8 * i
            subs[(self.u16(r), self.u16(r + 2))] = base + self.u32(r + 4)
        for key in ((3, 10), (0, 4), (3, 1), (0, 3), (0, 1), (0, 0)):
            if key in subs and self.u16(subs[key]) in (4, 12):
                return self._cmap_table(subs[key])
        return {}

    def _cmap_table(self, o):
        out = {}
        if self.u16(o) == 12:
            for g in range(self.u32(o + 12)):
                r = o + 16 + 12 * g
                c0, c1, g0 = self.u32(r), self.u32(r + 4), self.u32(r + 8)
                for c in range(c0, c1 + 1):
                    out[c] = g0 + c - c0
            return out
        seg = self.u16(o + 6) // 2
        ends, starts = o + 14, o + 16 + 2 * seg
        deltas, ranges = starts + 2 * seg, starts + 4 * seg
        for s in range(seg):
            c0, c1 = self.u16(starts + 2 * s), self.u16(ends + 2 * s)
            delta, ro = self.s16(deltas + 2 * s), self.u16(ranges + 2 * s)
            for c in range(c0, min(c1, 0xFFFE) + 1):
                if ro == 0:
                    g = (c + delta) & 0xFFFF
                else:
                    g = self.u16(ranges + 2 * s + ro + 2 * (c - c0))
                    g = (g + delta) & 0xFFFF if g else 0
                if g:
                    out[c] = g
        return out

    # GPOS kerning -----------------------------------------------------------------------------------------
    def _read_kern_lookups(self):
        g = self.tables['GPOS']
        scripts, features, lookups = g + self.u16(g + 4), g + self.u16(g + 6), g + self.u16(g + 8)
        sys_ = {}
        for i in range(self.u16(scripts)):
            r = scripts + 2 + 6 * i
            sys_[self._b[r:r + 4].decode('latin1')] = scripts + self.u16(r + 4)
        script = sys_.get('latn') or sys_.get('DFLT')
        if script is None or self.u16(script) == 0:
            return []
        langsys = script + self.u16(script)
        idx = set()
        for k in range(self.u16(langsys + 4)):
            fi = self.u16(langsys + 6 + 2 * k)
            r = features + 2 + 6 * fi
            if self._b[r:r + 4] == b'kern':
                feat = features + self.u16(r + 4)
                idx.update(self.u16(feat + 4 + 2 * j) for j in range(self.u16(feat + 2)))
        out = []
        for li in sorted(idx):
            lk = lookups + self.u16(lookups + 2 + 2 * li)
            typ, subs = self.u16(lk), []
            for s in range(self.u16(lk + 4)):
                st = lk + self.u16(lk + 6 + 2 * s)
                t = typ
                if t == 9:                                             # Extension: the real subtable is further on
                    t, st = self.u16(st + 2), st + self.u32(st + 4)
                if t == 2:
                    subs.append(self._pair_subtable(st))
            if subs:
                out.append(subs)
        return out

    def _coverage(self, o):
        out = {}
        if self.u16(o) == 1:
            for i in range(self.u16(o + 2)):
                out[self.u16(o + 4 + 2 * i)] = i
        else:
            for r in range(self.u16(o + 2)):
                q = o + 4 + 6 * r
                g0, g1, c0 = self.u16(q), self.u16(q + 2), self.u16(q + 4)
                for gg in range(g0, g1 + 1):
                    out[gg] = c0 + gg - g0
        return out

    def _classdef(self, o):
        out = {}
        if self.u16(o) == 1:
            g0 = self.u16(o + 2)
            for i in range(self.u16(o + 4)):
                out[g0 + i] = self.u16(o + 6 + 2 * i)
        else:
            for r in range(self.u16(o + 2)):
                q = o + 4 + 6 * r
                for gg in range(self.u16(q), self.u16(q + 2) + 1):
                    out[gg] = self.u16(q + 4)
        return out

    def _value(self, o, fmt):
        """a ValueRecord's (XPlacement, XAdvance) in font units (device tables ignored: no hinting)."""
        xp = self.s16(o) if fmt & 1 else 0
        xa = self.s16(o + 2 * bin(fmt & 3).count('1')) if fmt & 4 else 0
        return xp, xa

    def _pair_subtable(self, st):
        fmt, cov = self.u16(st), self._coverage(st + self.u16(st + 2))
        f1, f2 = self.u16(st + 4), self.u16(st + 6)
        n1, n2 = 2 * bin(f1).count('1'), 2 * bin(f2).count('1')
        sub = {'format': fmt, 'cov': cov, 'f2': f2}
        if fmt == 1:
            sets = {}
            for g1, ci in cov.items():
                ps = st + self.u16(st + 10 + 2 * ci)
                rec = {}
                for k in range(self.u16(ps)):
                    r = ps + 2 + k * (2 + n1 + n2)
                    rec[self.u16(r)] = (self._value(r + 2, f1), self._value(r + 2 + n1, f2))
                sets[g1] = rec
            sub['sets'] = sets
        else:
            c1, c2 = self._classdef(st + self.u16(st + 8)), self._classdef(st + self.u16(st + 10))
            k1, k2 = self.u16(st + 12), self.u16(st + 14)
            vals = {}
            for i in range(k1):
                for j in range(k2):
                    r = st + 16 + (i * k2 + j) * (n1 + n2)
                    v = (self._value(r, f1), self._value(r + n1, f2))
                    if v != ((0, 0), (0, 0)):
                        vals[(i, j)] = v
            sub.update(c1=c1, c2=c2, vals=vals)
        return sub

    def _pair(self, subs, g1, g2):
        """the first subtable of a lookup that applies to (g1, g2): (value1, value2, its valueFormat2) or None.
        A format-2 subtable applies whenever g1 is covered (a zero value included), as HarfBuzz has it."""
        for s in subs:
            if g1 not in s['cov']:
                continue
            if s['format'] == 1:
                v = s['sets'].get(g1, {}).get(g2)
                if v is None:
                    continue
                return v[0], v[1], s['f2']
            v = s['vals'].get((s['c1'].get(g1, 0), s['c2'].get(g2, 0)), ((0, 0), (0, 0)))
            return v[0], v[1], s['f2']
        return None

    def glyph(self, ch):
        return self.cmap.get(ord(ch), 0)

    def advance(self, gid):
        return self.adv[gid] if gid < len(self.adv) else self.adv[-1]

    def layout(self, text):
        """[(x of each character's origin)], total advance: font units, kerned as HarfBuzz kerns (each kern lookup
        over the whole run, a pair consuming its second glyph when its second value record is not empty)."""
        gids = [self.glyph(c) for c in text]
        n = len(gids)
        adv = [float(self.advance(g)) for g in gids]
        off = [0.0] * n
        for subs in self.lookups:
            i = 0
            while i < n - 1:
                hit = self._pair(subs, gids[i], gids[i + 1])
                if hit is None:
                    i += 1
                    continue
                (xp1, xa1), (xp2, xa2), f2 = hit
                off[i] += xp1
                adv[i] += xa1
                off[i + 1] += xp2
                adv[i + 1] += xa2
                i += 2 if f2 else 1
        xs, x = [], 0.0
        for i in range(n):
            xs.append(x + off[i])
            x += adv[i]
        return xs, x


@lru_cache(maxsize=64)
def font_metrics(path):
    """FontMetrics of a font file, read once."""
    return FontMetrics(path)


class Fonts:
    """The font registry napi() returns: CSS font strings ('bold 132px "Georgia", "UF Special Elite"') -> a Pillow
    font. A family missing from the registry falls through to the next one, as in the browser; a font string with no
    known family raises (no silent stand-in)."""

    def __init__(self, font_dir=FONT_DIR):
        self.dir = Path(font_dir)
        self.families = {}
        for fam, f in FAMILIES.items():
            if (self.dir / f).is_file():
                self.families[fam] = {'': self.dir / f}
        for fam, styles in STYLED.items():
            have = {k: self.dir / f for k, f in styles.items() if (self.dir / f).is_file()}
            if not have and os.name == 'nt':
                win = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
                have = {k: win / f for k, f in styles.items() if (win / f).is_file()}
            if have:
                self.families[fam] = have

    def register(self, path, family):
        """GlobalFonts.registerFromPath: a font file under a family name."""
        self.families[family] = {'': Path(path)}

    _CSS = re.compile(r'^\s*((?:(?:italic|oblique|bold|normal|[1-9]00)\s+)*)([\d.]+)px\s+(.+)$')

    def parse(self, css):
        m = self._CSS.match(css)
        if not m:
            raise ValueError(f'font {css!r}: expected "[italic] [bold] <n>px <family>[, <family>]"')
        mods = m.group(1).split()
        bold = any(t in ('bold', '700', '800', '900') for t in mods)
        italic = any(t in ('italic', 'oblique') for t in mods)
        fams = [f.strip().strip('"\'') for f in m.group(3).split(',')]
        return float(m.group(2)), bold, italic, fams

    @lru_cache(maxsize=512)
    def resolve(self, css):
        """(font file, px) for a CSS font string: the first registered family of the list, its bold / italic face."""
        px, bold, italic, fams = self.parse(css)
        for fam in fams:
            styles = self.families.get(fam)
            if not styles:
                continue
            key = ' '.join(k for k, on in (('bold', bold), ('italic', italic)) if on)
            return styles.get(key) or styles.get('bold' if bold else '') or styles[''], px
        raise KeyError(f'font {css!r}: none of {fams} is registered ({", ".join(sorted(self.families))})')

    @lru_cache(maxsize=512)
    def font(self, css, scale=1.0):
        """(Pillow FreeTypeFont at px * scale, px) for a CSS font string."""
        from PIL import ImageFont
        path, px = self.resolve(css)
        return ImageFont.truetype(str(path), max(1.0, px * scale)), px

    @lru_cache(maxsize=4096)
    def layout(self, css, text):
        """Skia's layout of a run of text (fillText, measureText): ([x of each character], width) in px, from the
        font's unhinted advances and its GPOS pair kerning (FontMetrics). A character the font has no glyph for
        takes Pillow's advance for it (what it draws there)."""
        path, px = self.resolve(css)
        fm = font_metrics(str(path))
        xs, w = fm.layout(text)
        k = px / fm.upem
        if all(fm.glyph(c) for c in text):
            return tuple(x * k for x in xs), w * k
        f, _ = self.font(css, 1.0)                       # missing glyphs: Pillow's advance, no kerning around them
        out, x = [], 0.0
        for i, c in enumerate(text):
            out.append(x)
            if fm.glyph(c):
                nxt = text[i + 1] if i + 1 < len(text) and fm.glyph(text[i + 1]) else ''
                x += (fm.layout(c + nxt)[0][1] if nxt else fm.advance(fm.glyph(c))) * k
            else:
                x += f.getlength(c)
        return tuple(out), x


_FONTS = None


def napi() -> Fonts:
    """interiors_lib.js's napi(): the canvas backend with the UF font families registered. Here: the font registry."""
    global _FONTS
    if _FONTS is None:
        _FONTS = Fonts()
    return _FONTS


# ------------------------------------------------------------------------------------------------ colours
_NAMED = {'black': (0, 0, 0), 'white': (255, 255, 255), 'red': (255, 0, 0), 'transparent': (0, 0, 0)}


def parse_color(c):
    """CSS colour -> (r, g, b, a) floats 0..1 (sRGB-encoded, as canvas stores them)."""
    if isinstance(c, (tuple, list)):
        return tuple(float(v) for v in c) if len(c) == 4 else (*map(float, c), 1.0)
    s = c.strip().lower()
    if s.startswith('#'):
        h = s[1:]
        if len(h) in (3, 4):
            h = ''.join(ch * 2 for ch in h)
        v = [int(h[i:i + 2], 16) / 255.0 for i in range(0, len(h), 2)]
        return (v[0], v[1], v[2], v[3] if len(v) == 4 else 1.0)
    m = re.match(r'rgba?\(([^)]*)\)', s)
    if m:
        parts = [p.strip() for p in m.group(1).split(',')]
        rgb = [float(p) / 255.0 for p in parts[:3]]
        a = float(parts[3]) if len(parts) > 3 else 1.0
        return (rgb[0], rgb[1], rgb[2], a)
    if s in _NAMED:
        r, g, b = _NAMED[s]
        return (r / 255, g / 255, b / 255, 0.0 if s == 'transparent' else 1.0)
    raise ValueError(f'colour {c!r}')


def srgb_to_linear(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def hex_linear(h):
    """A three.js hex colour (0xff2a12, sRGB) as the linear RGB three uses in its lights and Color()."""
    return tuple(float(v) for v in srgb_to_linear([((h >> 16) & 255) / 255, ((h >> 8) & 255) / 255, (h & 255) / 255]))


# ------------------------------------------------------------------------------------------------ canvas 2D
SS = 3            # supersampling of fills and strokes (3 x 3 coverage samples per pixel)


class Gradient:
    def __init__(self, kind, args):
        self.kind, self.args, self.stops = kind, args, []

    def addColorStop(self, off, color):
        self.stops.append((float(off), parse_color(color)))
        self.stops.sort(key=lambda s: s[0])

    def transparent_outside(self):
        return bool(self.stops) and self.stops[-1][1][3] == 0.0

    def eval(self, ux, uy):
        """Premultiplied RGBA per point (user space). Stops interpolate UNPREMULTIPLIED, as Skia does by default (so
        a stop fading to rgba(0,0,0,0) greys on its way out: the whiteboards' blotches were drawn that way)."""
        if self.kind == 'linear':
            x0, y0, x1, y1 = self.args
            dx, dy = x1 - x0, y1 - y0
            L2 = dx * dx + dy * dy
            t = ((ux - x0) * dx + (uy - y0) * dy) / L2 if L2 > 0 else np.zeros_like(ux)
        else:
            x0, y0, r0, x1, y1, r1 = self.args
            d = np.hypot(ux - x1, uy - y1)            # concentric circles (every use in the sets)
            t = (d - r0) / (r1 - r0) if r1 != r0 else np.zeros_like(ux)
        t = np.clip(t, 0.0, 1.0)
        offs = np.array([s[0] for s in self.stops])
        cols = np.array([[c[0], c[1], c[2], c[3]] for _, c in self.stops])
        out = np.empty(t.shape + (4,), np.float32)
        out[..., 3] = np.interp(t, offs, cols[:, 3])
        for k in range(3):
            out[..., k] = np.interp(t, offs, cols[:, k]) * out[..., 3]
        return out


class TextMetrics:
    def __init__(self, width):
        self.width = width


class _State:
    __slots__ = ('fillStyle', 'strokeStyle', 'lineWidth', 'lineCap', 'lineJoin', 'globalAlpha', 'font', 'textAlign',
                 'textBaseline', 'dash', 'm', 'miterLimit')

    def copy(self):
        s = _State()
        for k in self.__slots__:
            setattr(s, k, getattr(self, k))
        s.dash = list(self.dash)
        s.m = self.m.copy()
        return s


class Canvas:
    """A canvas (napi createCanvas): width, height, getContext('2d'). Pixels are premultiplied float32, rows from the
    top, sRGB-encoded values as canvas stores them."""

    def __init__(self, w, h, fonts=None):
        self.width, self.height = int(w), int(h)
        self.buf = np.zeros((self.height, self.width, 4), np.float32)
        self.fonts = fonts or napi()
        self._ctx = None

    def getContext(self, kind='2d'):
        if self._ctx is None:
            self._ctx = Context2D(self)
        return self._ctx

    def rgba8(self):
        """Unpremultiplied RGBA8, row 0 at the top (getImageData's layout)."""
        a = self.buf[..., 3:4]
        rgb = np.where(a > 0, self.buf[..., :3] / np.maximum(a, 1e-8), 0.0)
        out = np.concatenate([rgb, a], axis=2)
        return np.clip(np.round(out * 255.0), 0, 255).astype(np.uint8)

    def save_png(self, path):
        from PIL import Image
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(self.rgba8(), 'RGBA').save(path)

    @classmethod
    def from_png(cls, path, fonts=None):
        from PIL import Image
        im = np.asarray(Image.open(path).convert('RGBA'), dtype=np.float32) / 255.0
        cv = cls(im.shape[1], im.shape[0], fonts)
        cv.buf[..., :3] = im[..., :3] * im[..., 3:4]
        cv.buf[..., 3] = im[..., 3]
        return cv


class ImageData:
    def __init__(self, data, w, h):
        self.data, self.width, self.height = data, w, h


def _arc_sweep(a0, a1, ccw):
    tau = 2 * math.pi
    if not ccw:
        if a1 - a0 >= tau:
            return tau
        return (a1 - a0) % tau
    if a0 - a1 >= tau:
        return -tau
    return -((a0 - a1) % tau)


class Context2D:
    """The subset of CanvasRenderingContext2D the UF art uses, on numpy + Pillow. Attribute names stay the canvas
    API's (fillStyle, lineWidth, ...) so drawing code ports line for line."""

    _ATTRS = set(_State.__slots__)

    def __init__(self, canvas):
        object.__setattr__(self, 'canvas', canvas)
        s = _State()
        s.fillStyle, s.strokeStyle, s.lineWidth, s.lineCap, s.lineJoin = '#000', '#000', 1.0, 'butt', 'miter'
        s.globalAlpha, s.font, s.textAlign, s.textBaseline, s.dash = 1.0, '10px "UF Mono"', 'start', 'alphabetic', []
        s.m, s.miterLimit = np.eye(3), 10.0
        object.__setattr__(self, '_s', s)
        object.__setattr__(self, '_stack', [])
        object.__setattr__(self, '_path', [])           # [[points (device), closed]]

    def __getattr__(self, k):
        if k in Context2D._ATTRS:
            return getattr(self._s, k)
        raise AttributeError(k)

    def __setattr__(self, k, v):
        if k in Context2D._ATTRS:
            setattr(self._s, k, v)
        else:
            object.__setattr__(self, k, v)

    # state
    def save(self):
        self._stack.append(self._s.copy())

    def restore(self):
        if self._stack:
            object.__setattr__(self, '_s', self._stack.pop())

    def translate(self, x, y):
        self._s.m = self._s.m @ np.array([[1, 0, x], [0, 1, y], [0, 0, 1]], float)

    def rotate(self, a):
        c, s = math.cos(a), math.sin(a)
        self._s.m = self._s.m @ np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], float)

    def scale(self, sx, sy):
        self._s.m = self._s.m @ np.array([[sx, 0, 0], [0, sy, 0], [0, 0, 1]], float)

    def setTransform(self, a=1, b=0, c=0, d=1, e=0, f=0):
        self._s.m = np.array([[a, c, e], [b, d, f], [0, 0, 1]], float)

    def resetTransform(self):
        self._s.m = np.eye(3)

    def setLineDash(self, seg):
        self._s.dash = [float(v) for v in seg]

    def _xf(self, x, y):
        m = self._s.m
        return (m[0, 0] * x + m[0, 1] * y + m[0, 2], m[1, 0] * x + m[1, 1] * y + m[1, 2])

    def _scale(self):
        m = self._s.m
        return math.sqrt(abs(m[0, 0] * m[1, 1] - m[0, 1] * m[1, 0]))

    # gradients
    def createLinearGradient(self, x0, y0, x1, y1):
        return Gradient('linear', (x0, y0, x1, y1))

    def createRadialGradient(self, x0, y0, r0, x1, y1, r1):
        return Gradient('radial', (x0, y0, r0, x1, y1, r1))

    # paths
    def beginPath(self):
        self._path.clear()

    def _cur(self):
        if not self._path or self._path[-1][1]:
            return None
        return self._path[-1][0]

    def moveTo(self, x, y):
        self._path.append([[self._xf(x, y)], False])

    def lineTo(self, x, y):
        cur = self._cur()
        if cur is None:
            self.moveTo(x, y)
        else:
            cur.append(self._xf(x, y))

    def closePath(self):
        if self._path and not self._path[-1][1]:
            pts = self._path[-1][0]
            self._path[-1][1] = True
            self._path.append([[pts[0]], False])

    def _add_pts(self, pts):
        cur = self._cur()
        if cur is None:
            self._path.append([list(pts), False])
        else:
            cur.extend(pts)

    def ellipse(self, x, y, rx, ry, rot, a0, a1, ccw=False):
        sweep = _arc_sweep(a0, a1, ccw)
        rdev = max(rx, ry) * self._scale()
        n = int(min(1024, max(8, abs(sweep) * max(1.0, rdev) / 2.0 + 1)))
        cr, sr = math.cos(rot), math.sin(rot)
        pts = []
        for i in range(n + 1):
            a = a0 + sweep * i / n
            ex, ey = rx * math.cos(a), ry * math.sin(a)
            pts.append(self._xf(x + ex * cr - ey * sr, y + ex * sr + ey * cr))
        self._add_pts(pts)

    def arc(self, x, y, r, a0, a1, ccw=False):
        self.ellipse(x, y, r, r, 0.0, a0, a1, ccw)

    def _last_user(self):
        cur = self._cur()
        if cur is None:
            return None
        inv = np.linalg.inv(self._s.m)
        x, y = cur[-1]
        return (inv[0, 0] * x + inv[0, 1] * y + inv[0, 2], inv[1, 0] * x + inv[1, 1] * y + inv[1, 2])

    def bezierCurveTo(self, c1x, c1y, c2x, c2y, x, y):
        p0 = self._last_user() or (c1x, c1y)
        L = math.hypot(c1x - p0[0], c1y - p0[1]) + math.hypot(c2x - c1x, c2y - c1y) + math.hypot(x - c2x, y - c2y)
        n = int(min(512, max(8, L * self._scale() / 3)))
        pts = []
        for i in range(1, n + 1):
            t = i / n
            u = 1 - t
            bx = u * u * u * p0[0] + 3 * u * u * t * c1x + 3 * u * t * t * c2x + t * t * t * x
            by = u * u * u * p0[1] + 3 * u * u * t * c1y + 3 * u * t * t * c2y + t * t * t * y
            pts.append(self._xf(bx, by))
        self._add_pts(pts)

    def quadraticCurveTo(self, cx, cy, x, y):
        p0 = self._last_user() or (cx, cy)
        self.bezierCurveTo(p0[0] + 2 / 3 * (cx - p0[0]), p0[1] + 2 / 3 * (cy - p0[1]),
                           x + 2 / 3 * (cx - x), y + 2 / 3 * (cy - y), x, y)

    def rect(self, x, y, w, h):
        self.moveTo(x, y)
        self.lineTo(x + w, y)
        self.lineTo(x + w, y + h)
        self.lineTo(x, y + h)
        self.closePath()

    # raster core -------------------------------------------------------------------------------------------
    def _bbox(self, polys, pad=0.0):
        allp = np.concatenate([np.asarray(p, float).reshape(-1, 2) for p in polys if len(p)], axis=0)
        x0, y0 = np.floor(allp.min(0) - pad - 1).astype(int)
        x1, y1 = np.ceil(allp.max(0) + pad + 1).astype(int)
        W, H = self.canvas.width, self.canvas.height
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
        return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None

    def _mask(self, bbox, polys, circles=()):
        """Coverage (bh, bw) of the union of polygons and discs (device px), SS x SS supersampled."""
        from PIL import Image, ImageDraw
        x0, y0, x1, y1 = bbox
        bw, bh = x1 - x0, y1 - y0
        im = Image.new('L', (bw * SS, bh * SS), 0)
        dr = ImageDraw.Draw(im)
        for p in polys:
            if len(p) >= 3:
                q = [((px - x0) * SS - 0.5, (py - y0) * SS - 0.5) for px, py in p]
                dr.polygon(q, fill=255)
        for cx, cy, r in circles:
            X, Y, R = (cx - x0) * SS - 0.5, (cy - y0) * SS - 0.5, r * SS
            if R < 0.5:
                continue
            dr.ellipse([X - R, Y - R, X + R, Y + R], fill=255)
        a = np.asarray(im, dtype=np.float32).reshape(bh, SS, bw, SS).mean(axis=(1, 3)) / 255.0
        return a

    def _composite(self, bbox, cov, style):
        x0, y0, x1, y1 = bbox
        ga = float(self._s.globalAlpha)
        dst = self.canvas.buf[y0:y1, x0:x1]
        if isinstance(style, Gradient):
            ys, xs = np.mgrid[y0:y1, x0:x1].astype(np.float64)
            inv = np.linalg.inv(self._s.m)
            dx, dy = xs + 0.5, ys + 0.5
            ux = inv[0, 0] * dx + inv[0, 1] * dy + inv[0, 2]
            uy = inv[1, 0] * dx + inv[1, 1] * dy + inv[1, 2]
            src = style.eval(ux, uy) * (cov * ga)[..., None]
        else:
            r, g, b, a = parse_color(style)
            sa = (cov * (a * ga)).astype(np.float32)
            src = np.empty(cov.shape + (4,), np.float32)
            src[..., 0], src[..., 1], src[..., 2], src[..., 3] = r * sa, g * sa, b * sa, sa
        dst *= (1.0 - src[..., 3:4])
        dst += src

    # fills ------------------------------------------------------------------------------------------------------
    def _polys(self):
        return [p for p, _closed in self._path if len(p) >= 3]

    def fill(self):
        polys = self._polys()
        if not polys:
            return
        bb = self._bbox(polys)
        if bb:
            self._composite(bb, self._mask(bb, polys), self._s.fillStyle)

    def _rect_poly(self, x, y, w, h):
        return [self._xf(x, y), self._xf(x + w, y), self._xf(x + w, y + h), self._xf(x, y + h)]

    def fillRect(self, x, y, w, h):
        poly = self._rect_poly(x, y, w, h)
        bb = self._bbox([poly])
        st = self._s.fillStyle
        if bb is None:
            return
        if isinstance(st, Gradient) and st.kind == 'radial' and st.transparent_outside():
            # padding beyond the outer circle is transparent: only its square can change pixels
            cx, cy, r1 = st.args[3], st.args[4], st.args[5]
            c = self._bbox([[self._xf(cx - r1, cy - r1), self._xf(cx + r1, cy - r1), self._xf(cx + r1, cy + r1),
                             self._xf(cx - r1, cy + r1)]])
            if c is None:
                return
            bb = (max(bb[0], c[0]), max(bb[1], c[1]), min(bb[2], c[2]), min(bb[3], c[3]))
            if bb[2] <= bb[0] or bb[3] <= bb[1]:
                return
        m = self._s.m
        if abs(m[0, 1]) < 1e-12 and abs(m[1, 0]) < 1e-12:
            cov = self._axis_rect_cov(bb, poly)
        else:
            cov = self._mask(bb, [poly])
        self._composite(bb, cov, st)

    def _axis_rect_cov(self, bb, poly):
        """Exact area coverage of an axis-aligned rectangle (fast path for fillRect without rotation)."""
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        rx0, rx1, ry0, ry1 = min(xs), max(xs), min(ys), max(ys)
        x0, y0, x1, y1 = bb
        px = np.arange(x0, x1, dtype=np.float64)
        py = np.arange(y0, y1, dtype=np.float64)
        cx = np.clip(np.minimum(px + 1, rx1) - np.maximum(px, rx0), 0, 1)
        cy = np.clip(np.minimum(py + 1, ry1) - np.maximum(py, ry0), 0, 1)
        return (cy[:, None] * cx[None, :]).astype(np.float32)

    def clearRect(self, x, y, w, h):
        poly = self._rect_poly(x, y, w, h)
        bb = self._bbox([poly])
        if bb:
            cov = self._axis_rect_cov(bb, poly)
            self.canvas.buf[bb[1]:bb[3], bb[0]:bb[2]] *= (1.0 - cov)[..., None]

    # strokes ----------------------------------------------------------------------------------------------------
    def _dash_split(self, pts, closed):
        dash = self._s.dash
        if not dash or sum(dash) <= 0:
            return [(pts, closed)]
        if len(dash) % 2:
            dash = dash * 2
        sc = self._scale()
        dash = [d * sc for d in dash]
        pts = list(pts) + ([pts[0]] if closed else [])
        out, cur, di, left, on = [], [pts[0]], 0, dash[0], True
        for i in range(len(pts) - 1):
            ax, ay = pts[i]
            bx, by = pts[i + 1]
            seg = math.hypot(bx - ax, by - ay)
            pos = 0.0
            while seg - pos > left:
                pos += left
                t = pos / seg
                p = (ax + (bx - ax) * t, ay + (by - ay) * t)
                if on:
                    cur.append(p)
                    out.append((cur, False))
                else:
                    cur = [p]
                on = not on
                di = (di + 1) % len(dash)
                left = dash[di]
            left -= seg - pos
            if on:
                cur.append((bx, by))
        if on and len(cur) > 1:
            out.append((cur, False))
        return out

    def _stroke_geom(self, pts, closed, hw):
        polys, circles = [], []
        cap, join = self._s.lineCap, self._s.lineJoin
        P = [pts[0]]
        for p in pts[1:]:
            if abs(p[0] - P[-1][0]) > 1e-9 or abs(p[1] - P[-1][1]) > 1e-9:
                P.append(p)
        if closed and len(P) > 2 and abs(P[0][0] - P[-1][0]) < 1e-9 and abs(P[0][1] - P[-1][1]) < 1e-9:
            P.pop()
        if len(P) == 1:
            if cap == 'round':
                circles.append((P[0][0], P[0][1], hw))
            elif cap == 'square':
                x, y = P[0]
                polys.append([(x - hw, y - hw), (x + hw, y - hw), (x + hw, y + hw), (x - hw, y + hw)])
            return polys, circles
        segs = list(zip(P[:-1], P[1:])) + ([(P[-1], P[0])] if closed else [])
        dirs = []
        for k, (a, b) in enumerate(segs):
            dx, dy = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dy)
            ux, uy = dx / L, dy / L
            dirs.append((ux, uy))
            nx, ny = -uy * hw, ux * hw
            ax, ay = a
            bx, by = b
            if not closed and cap == 'square':
                if k == 0:
                    ax, ay = ax - ux * hw, ay - uy * hw
                if k == len(segs) - 1:
                    bx, by = bx + ux * hw, by + uy * hw
            polys.append([(ax + nx, ay + ny), (bx + nx, by + ny), (bx - nx, by - ny), (ax - nx, ay - ny)])
        # joins at interior vertices (and the closing vertex)
        nj = len(segs) if closed else len(segs) - 1
        for k in range(nj):
            v = segs[k][1]
            d0, d1 = dirs[k], dirs[(k + 1) % len(segs)]
            if join == 'round':
                circles.append((v[0], v[1], hw))
                continue
            cross = d0[0] * d1[1] - d0[1] * d1[0]
            if abs(cross) < 1e-9:
                continue
            s = 1.0 if cross > 0 else -1.0           # outer side is opposite to the turn
            n0 = (d0[1] * hw * s, -d0[0] * hw * s)
            n1 = (d1[1] * hw * s, -d1[0] * hw * s)
            p0 = (v[0] + n0[0], v[1] + n0[1])
            p1 = (v[0] + n1[0], v[1] + n1[1])
            if join == 'miter':
                cosang = max(-1.0, min(1.0, -(d0[0] * d1[0] + d0[1] * d1[1])))
                theta = math.acos(cosang)                       # the interior angle between the segments
                if theta > 1e-6 and 1.0 / math.sin(theta / 2) <= self._s.miterLimit:
                    bxv, byv = n0[0] + n1[0], n0[1] + n1[1]
                    bl = math.hypot(bxv, byv)
                    ml = hw / math.sin(theta / 2)
                    mp = (v[0] + bxv / bl * ml, v[1] + byv / bl * ml)
                    polys.append([v, p0, mp, p1])
                    continue
            polys.append([v, p0, p1])
        if not closed and cap == 'round':
            circles.append((P[0][0], P[0][1], hw))
            circles.append((P[-1][0], P[-1][1], hw))
        return polys, circles

    def _stroke_paths(self, paths):
        hw = float(self._s.lineWidth) * self._scale() / 2.0
        polys, circles = [], []
        for pts, closed in paths:
            if not pts:
                continue
            for sub, cl in self._dash_split(pts, closed):
                p, c = self._stroke_geom(sub, cl, hw)
                polys += p
                circles += c
        if not polys and not circles:
            return
        allp = polys + [[(x - r, y - r), (x + r, y + r)] for x, y, r in circles]
        bb = self._bbox(allp)
        if bb:
            self._composite(bb, self._mask(bb, polys, circles), self._s.strokeStyle)

    def stroke(self):
        paths = [(p, closed) for p, closed in self._path if len(p) >= 1 and (len(p) > 1 or closed)]
        self._stroke_paths(paths)

    def strokeRect(self, x, y, w, h):
        self._stroke_paths([(self._rect_poly(x, y, w, h), True)])

    # text -------------------------------------------------------------------------------------------------------
    def measureText(self, text):
        """the run's advance as Skia measures it: unhinted advances plus the font's GPOS pair kerning."""
        return TextMetrics(self.canvas.fonts.layout(self._s.font, str(text))[1] if text else 0.0)

    def _text_mask(self, text, x, y, stroke_w=0.0):
        """(bbox, coverage) of text drawn at user (x, y) under the current transform: each glyph at the position
        Skia's shaping gives it (Fonts.layout: unhinted advances, GPOS pair kerning), rendered by FreeType."""
        from PIL import Image, ImageDraw
        if not text:
            return None, None
        sc = self._scale()
        k = SS * max(sc, 1e-6)
        fonts = self.canvas.fonts
        f, px = fonts.font(self._s.font, k)
        xs, width = fonts.layout(self._s.font, text)
        h0 = {'left': 0.0, 'start': 0.0, 'center': -0.5, 'right': -1.0, 'end': -1.0}.get(self._s.textAlign, 0.0) * width
        v = {'alphabetic': 's', 'middle': 'm', 'top': 'a', 'hanging': 'a', 'bottom': 'd', 'ideographic': 'd'}.get(
            self._s.textBaseline, 's')
        anchor = 'l' + v
        sw = int(round(stroke_w * k / 2)) if stroke_w else 0
        glyphs = [(c, (h0 + xi) * k) for c, xi in zip(text, xs) if not c.isspace()]
        boxes = []
        for c, gx in glyphs:
            l_, t_, r_, b_ = f.getbbox(c, anchor=anchor, stroke_width=sw)
            boxes.append((l_ + gx, t_, r_ + gx, b_))
        if not boxes:
            return None, None
        l = math.floor(min(q[0] for q in boxes)) - 2
        t = math.floor(min(q[1] for q in boxes)) - 2
        r = math.ceil(max(q[2] for q in boxes)) + 2
        b = math.ceil(max(q[3] for q in boxes)) + 2
        im = Image.new('L', (int(r - l), int(b - t)), 0)
        dr = ImageDraw.Draw(im)
        if stroke_w:
            inner = Image.new('L', im.size, 0)
            di = ImageDraw.Draw(inner)
            for c, gx in glyphs:
                dr.text((gx - l, -t), c, font=f, fill=255, anchor=anchor, stroke_width=sw, stroke_fill=255)
                di.text((gx - l, -t), c, font=f, fill=255, anchor=anchor)
            from PIL import ImageFilter
            er = max(3, (2 * sw + 1) | 1)
            inner = inner.filter(ImageFilter.MinFilter(er))
            im = Image.fromarray(np.clip(np.asarray(im, np.int16) - np.asarray(inner, np.int16), 0, 255).astype(np.uint8))
        else:
            for c, gx in glyphs:
                dr.text((gx - l, -t), c, font=f, fill=255, anchor=anchor)
        # mask pixel (i, j) centre <-> text-space point ((i + 0.5 + l) / k, (j + 0.5 + t) / k) relative to the anchor
        m = self._s.m @ np.array([[1, 0, x], [0, 1, y], [0, 0, 1]], float)
        corners = [(l / k, t / k), (r / k, t / k), (r / k, b / k), (l / k, b / k)]
        dev = [(m[0, 0] * cx + m[0, 1] * cy + m[0, 2], m[1, 0] * cx + m[1, 1] * cy + m[1, 2]) for cx, cy in corners]
        bb = self._bbox([dev])
        if bb is None:
            return None, None
        x0, y0, x1, y1 = bb
        # output pixel (u, v) at SS resolution: device point ((u + 0.5) / SS + x0, (v + 0.5) / SS + y0)
        # -> text point q = inv(m) * d -> mask pixel q * k - (l, t) (centre convention: minus 0.5 each side)
        inv = np.linalg.inv(m)
        A = inv[:2, :2] * (k / SS)
        off = inv[:2, :2] @ np.array([x0 + 0.5 / SS, y0 + 0.5 / SS]) + inv[:2, 2]
        c0 = off * k - np.array([l, t])
        # Pillow AFFINE maps output pixel CENTRE (u + .5, v + .5) to input coordinate a*(u+.5) + b*(v+.5) + c
        a, b_ = A[0, 0], A[0, 1]
        d, e = A[1, 0], A[1, 1]
        cc = c0[0] - (a * 0.5 + b_ * 0.5) + 0.5
        ff = c0[1] - (d * 0.5 + e * 0.5) + 0.5
        out = im.transform(((x1 - x0) * SS, (y1 - y0) * SS), Image.AFFINE, (a, b_, cc, d, e, ff),
                           resample=Image.BILINEAR)
        cov = np.asarray(out, np.float32).reshape(y1 - y0, SS, x1 - x0, SS).mean(axis=(1, 3)) / 255.0
        return bb, cov

    def fillText(self, text, x, y):
        bb, cov = self._text_mask(str(text), x, y)
        if bb:
            self._composite(bb, cov, self._s.fillStyle)

    def strokeText(self, text, x, y):
        bb, cov = self._text_mask(str(text), x, y, stroke_w=float(self._s.lineWidth))
        if bb:
            self._composite(bb, cov, self._s.strokeStyle)

    # pixels -----------------------------------------------------------------------------------------------------
    def getImageData(self, x, y, w, h):
        d = self.canvas.rgba8()[y:y + h, x:x + w].copy()
        return ImageData(d, w, h)

    def putImageData(self, img, x, y):
        d = np.asarray(img.data, np.float32).reshape(img.height, img.width, 4) / 255.0
        reg = self.canvas.buf[y:y + img.height, x:x + img.width]
        reg[..., 3] = d[..., 3]
        reg[..., :3] = d[..., :3] * d[..., 3:4]


def canvas(N, w, h):
    """interiors_lib.js's canvas(N, w, h) -> (canvas, ctx)."""
    cv = Canvas(w, h, N if isinstance(N, Fonts) else napi())
    return cv, cv.getContext('2d')


# ------------------------------------------------------------------------------------------------ hand-drawn marker
# All coordinates in canvas px. r = rng(). Kalam Bold reads as a chisel marker; Caveat Brush as a fat bullet tip.
def marker(ctx, text, x, y, size=60, color='#c3141e', font='UF Kalam Bold', rot=0.0, r=None, align='left', jit=0.035,
           alpha=0.93, track=1.0):
    """Marker lettering: each glyph jittered, tilted and inked (with a faint offset pass for ink pooling). Returns the
    width as measured before the jitter (the same number the engine's marker() returned)."""
    r = r or rng(1)
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(rot)
    ctx.font = f'{size}px "{font}"'
    ctx.textBaseline = 'alphabetic'
    w = ctx.measureText(text).width * track
    cx = -w / 2 if align == 'center' else -w if align == 'right' else 0.0
    ctx.fillStyle = color
    for ch in text:
        cw = ctx.measureText(ch).width * track
        if ch != ' ':
            ctx.save()
            ctx.translate(cx + (r() - 0.5) * size * jit, (r() - 0.5) * size * jit * 1.3)
            ctx.rotate((r() - 0.5) * 0.07)
            a = alpha * (0.82 + 0.18 * r())
            ctx.globalAlpha = a
            ctx.fillText(ch, 0, 0)
            ctx.globalAlpha = a * 0.3
            ctx.fillText(ch, size * 0.012, size * 0.008)        # ink pooling on the stroke
            ctx.restore()
        cx += cw * (0.97 + r() * 0.05)
    ctx.restore()
    return w


def mline(ctx, pts, w=6, color='#c3141e', r=None, jit=1.6, alpha=0.92, dashed=None):
    """A wobbly marker polyline (pts: [[x, y], ...]); dashed = [on, off] px."""
    r = r or rng(2)
    ctx.save()
    ctx.strokeStyle = color
    ctx.lineWidth = w
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    ctx.globalAlpha = alpha
    if dashed:
        ctx.setLineDash(dashed)
    ctx.beginPath()
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        L = math.hypot(x1 - x0, y1 - y0)
        n = max(2, round(L / 40))
        for k in range(n + 1):
            if i > 0 and k == 0:
                continue
            t = k / n
            px = x0 + (x1 - x0) * t + ((r() - 0.5) * jit * 2 if 0 < k < n else 0)
            py = y0 + (y1 - y0) * t + ((r() - 0.5) * jit * 2 if 0 < k < n else 0)
            if i == 0 and k == 0:
                ctx.moveTo(px, py)
            else:
                ctx.lineTo(px, py)
    ctx.stroke()
    ctx.restore()


def marrow(ctx, x0, y0, x1, y1, w=6, head=26, **o):
    """A marker arrow: the shaft and two barbs."""
    mline(ctx, [[x0, y0], [x1, y1]], w=w, **o)
    a = math.atan2(y1 - y0, x1 - x0)
    for s in (-1, 1):
        mline(ctx, [[x1, y1], [x1 - math.cos(a + s * 0.45) * head, y1 - math.sin(a + s * 0.45) * head]],
              w=w * 0.95, **o)


def mring(ctx, cx, cy, rx, ry, r=None, turns=1.12, **o):
    """A hand-drawn ellipse with an overshoot (the loop people draw round a number)."""
    given = r is not None
    r = r or rng(3)
    pts = []
    a0, n = r() * math.pi * 2, 40
    for i in range(n + 1):
        t = a0 + (i / n) * math.pi * 2 * turns
        k = 1 + (r() - 0.5) * 0.06 + (i / n) * 0.05
        pts.append([cx + math.cos(t) * rx * k, cy + math.sin(t) * ry * k])
    o = {**o, 'jit': 0.6}
    mline(ctx, pts, r=r if given else None, **o)         # as in the engine: without an r, mline draws its own


def board_base(ctx, W, H, r, ghosts=(), tint='#eceeea'):
    """A whiteboard surface: enamel white with tonal blotches, erased GHOSTS of older writing and eraser swipes.
    ghosts: [{'t': text, 'x', 'y' (fractions), 's' (size / H), 'c', 'a', 'rot', 'f'}]."""
    ctx.fillStyle = tint
    ctx.fillRect(0, 0, W, H)
    for _ in range(26):                        # faint tonal drift (a big sheet of enamel is never one value)
        x, y, rad = r() * W, r() * H, (0.15 + r() * 0.4) * max(W, H)
        g = ctx.createRadialGradient(x, y, 0, x, y, rad)
        dark = r() < 0.6
        g.addColorStop(0, f'rgba(150,158,160,{0.03 + r() * 0.05})' if dark else f'rgba(255,255,255,{0.05 + r() * 0.06})')
        g.addColorStop(1, 'rgba(0,0,0,0)')
        ctx.fillStyle = g
        ctx.fillRect(0, 0, W, H)
    for gh in ghosts:                          # earlier sessions' writing, mostly wiped
        marker(ctx, gh['t'], gh['x'] * W, gh['y'] * H, size=gh['s'] * H, color=gh.get('c') or '#7d8384',
               alpha=gh.get('a', 0.12), r=r, rot=gh.get('rot') or 0, font=gh.get('f') or 'UF Kalam Bold')
    ctx.save()                                 # eraser swipes: long soft strokes that lift the ghosts unevenly
    for _ in range(22):
        x, y, ln, hh, a = r() * W, r() * H, (0.15 + r() * 0.35) * W, (0.05 + r() * 0.06) * H, (r() - 0.5) * 0.5
        ctx.save()
        ctx.translate(x, y)
        ctx.rotate(a)
        g = ctx.createLinearGradient(0, -hh, 0, hh)
        al = 0.22 + r() * 0.3
        g.addColorStop(0, 'rgba(236,238,234,0)')
        g.addColorStop(0.5, f'rgba(236,238,234,{al})')
        g.addColorStop(1, 'rgba(236,238,234,0)')
        ctx.fillStyle = g
        ctx.fillRect(-ln / 2, -hh, ln, hh * 2)
        ctx.globalAlpha = 0.05 + r() * 0.05    # the swipe's own residue: faint grey streaks along it
        ctx.strokeStyle = '#8f9596'
        ctx.lineWidth = 1 + r() * 2
        for _k in range(6):
            yy = (r() - 0.5) * hh * 1.6
            ctx.beginPath()
            ctx.moveTo(-ln / 2, yy)
            ctx.lineTo(ln / 2, yy + (r() - 0.5) * 6)
            ctx.stroke()
        ctx.restore()
    ctx.restore()


def board_roughness_rgba(cv, r, base=0.16):
    """board_roughness's pixels (RGBA8, row 0 at the top): enamel glossy, dry ink and eraser haze matte."""
    W, H = cv.width, cv.height
    cells = 24
    field = np.array([r() for _ in range((cells + 1) * (cells + 1))], np.float64).reshape(cells + 1, cells + 1)
    xs = np.arange(W, dtype=np.float64) / W * cells
    ys = np.arange(H, dtype=np.float64) / H * cells
    xi, yi = np.floor(xs).astype(int), np.floor(ys).astype(int)
    xf, yf = xs - xi, ys - yi
    u, v = xf * xf * (3 - 2 * xf), yf * yf * (3 - 2 * yf)
    a = field[yi][:, xi]
    b = field[yi][:, xi + 1]
    c = field[yi + 1][:, xi]
    d = field[yi + 1][:, xi + 1]
    U, V = u[None, :], v[:, None]
    f = a + (b - a) * U + (c - a) * V + (a - b - c + d) * U * V
    px = cv.rgba8().astype(np.float64)
    R, G, B = px[..., 0], px[..., 1], px[..., 2]
    lum = (0.2126 * R + 0.7152 * G + 0.0722 * B) / 255
    sat = (np.maximum(np.maximum(R, G), B) - np.minimum(np.minimum(R, G), B)) / 255
    ink = np.clip((0.86 - lum) * 2.2 + sat * 0.8, 0, 1)
    q = np.round(np.clip(base + f * 0.16 + ink * 0.38, 0, 1) * 255).astype(np.uint8)
    out = np.empty((H, W, 4), np.uint8)
    out[..., 0] = out[..., 1] = out[..., 2] = q
    out[..., 3] = 255
    return out


def board_roughness(cv, r, base=0.16, name=None):
    """Whiteboard roughness derived from the finished albedo (a Non-Color image): glossy enamel, matte ink."""
    return data_texture(board_roughness_rgba(cv, r, base), cv.width, cv.height, srgb=False, name=name)


# ------------------------------------------------------------------------------------------------ mips (CPU)
def build_mips(data, w, h, alpha_weighted=False):
    """The engine's 2 x 2 box mip chain (alpha_weighted keeps transparent texels from darkening decal edges). Blender
    builds its own mips on upload; this is kept for parity checks and for exporting a chain."""
    src = np.asarray(data, np.uint8).reshape(h, w, 4).astype(np.int64)
    levels = [{'data': np.asarray(data, np.uint8).reshape(-1), 'width': w, 'height': h}]
    sw, sh = w, h
    while sw > 1 or sh > 1:
        dw, dh = max(1, sw >> 1), max(1, sh >> 1)
        ys0 = np.minimum(sh - 1, np.arange(dh) * 2)
        ys1 = np.minimum(sh - 1, np.arange(dh) * 2 + 1)
        xs0 = np.minimum(sw - 1, np.arange(dw) * 2)
        xs1 = np.minimum(sw - 1, np.arange(dw) * 2 + 1)
        A, B = src[ys0][:, xs0], src[ys0][:, xs1]
        C, D = src[ys1][:, xs0], src[ys1][:, xs1]
        if alpha_weighted:
            wa, wb, wc, wd = A[..., 3:4], B[..., 3:4], C[..., 3:4], D[..., 3:4]
            ws = wa + wb + wc + wd
            num = A[..., :3] * wa + B[..., :3] * wb + C[..., :3] * wc + D[..., :3] * wd
            with np.errstate(divide='ignore', invalid='ignore'):
                rgbw = np.floor(num / np.maximum(ws, 1) + 0.5)
            rgbu = (A[..., :3] + B[..., :3] + C[..., :3] + D[..., :3] + 2) >> 2
            rgb = np.where(ws > 0, rgbw, rgbu)
            alpha = (ws + 2) >> 2
            dst = np.concatenate([rgb, alpha], axis=2)
        else:
            dst = (A + B + C + D + 2) >> 2
        src = dst.astype(np.int64)
        levels.append({'data': src.astype(np.uint8).reshape(-1), 'width': dw, 'height': dh})
        sw, sh = dw, dh
    return levels


# ------------------------------------------------------------------------------------------------ noise (CPU)
def noise_rgba():
    """The shared tiling noise's RGBA8 (256 x 256): 4 independent periodic fBm channels (R period 4, G 8, B 32,
    A 64 cells per tile). Bit-exact with interiors_lib.js's noiseTexture (memory row 0 = v 0)."""
    N = 256
    data = np.zeros((N, N, 4), np.uint8)
    xs = np.arange(N, dtype=np.float64)
    for ch, (P, octs, seed) in enumerate(((4, 5, 11), (8, 4, 23), (32, 3, 37), (64, 2, 53))):
        r = rng(seed)
        lats = []
        for o in range(octs):
            p = P << o
            L = np.array([np.float32(r()) for _ in range(p * p)], np.float32).astype(np.float64)
            lats.append((p, L))
        v = np.zeros((N, N))
        amp, tot = 0.5, 0.0
        for p, L in lats:
            f = xs / N * p
            i = np.floor(f).astype(int)
            fr = f - i
            X0, X1 = i % p, (i + 1) % p
            u = fr * fr * (3 - 2 * fr)
            Y0, Y1 = (i % p) * p, ((i + 1) % p) * p
            a = L[Y0[:, None] + X0[None, :]]
            b = L[Y0[:, None] + X1[None, :]]
            c = L[Y1[:, None] + X0[None, :]]
            d = L[Y1[:, None] + X1[None, :]]
            U, W_ = u[None, :], u[:, None]
            v += amp * (a + (b - a) * U + (c - a) * W_ + (a - b - c + d) * U * W_)
            tot += amp
            amp *= 0.5
        data[..., ch] = np.floor(255 * v / tot + 0.5).astype(np.uint8)          # Math.round
    return data


# ================================================================================================================
# THE BLENDER HALF (bpy is imported where it is used, so the canvas half above stays plain Python)
# ================================================================================================================
def _bpy():
    import bpy
    return bpy


# ------------------------------------------------------------------------------------------------ images
def data_texture(rgba, w, h, srgb=True, mips=True, repeat=False, alpha_weighted=False, flip=True, name='uf_tex'):
    """dataTexture: RGBA8 rows (row 0 = the TOP of the picture, canvas order) -> a packed bpy Image. flip=True puts the
    picture's top at v = 1 (Blender's first pixel row is v = 0, as three's DataTexture's first data row); flip=False
    keeps memory row 0 at v = 0 (the noise, the equirect). Colour images are sRGB with straight alpha; data images
    (srgb=False) are Non-Color with the alpha channel packed (CHANNEL_PACKED: a fourth data channel).

    mips and alpha_weighted: EEVEE builds the mip chain itself on upload, from premultiplied texels, which is what
    the engine's alphaWeighted chain was for (transparent texels never darken a decal's edge); build_mips stays for
    parity checks. repeat: the sampler's wrap lives on the Image Texture node in Blender, so the image records it
    (img['uf_repeat']) and the material kit's texture() reads it."""
    bpy = _bpy()
    w, h = int(w), int(h)
    a = np.asarray(rgba, np.uint8).reshape(h, w, 4)
    if flip:
        a = a[::-1]
    img = bpy.data.images.new(name, w, h, alpha=True, float_buffer=False)
    img.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'
    img.alpha_mode = 'STRAIGHT' if srgb else 'CHANNEL_PACKED'
    img.pixels.foreach_set((a.astype(np.float32) * np.float32(1.0 / 255.0)).ravel())
    img.pack()
    img['uf_repeat'] = bool(repeat)
    img['uf_mips'] = bool(mips)
    return img


def canvas_texture(cv, srgb=True, mips=True, repeat=False, alpha_weighted=False, name='uf_canvas'):
    """canvasTexture: a finished canvas -> a packed bpy Image (canvas top at v = 1)."""
    return data_texture(cv.rgba8(), cv.width, cv.height, srgb=srgb, mips=mips, repeat=repeat,
                        alpha_weighted=alpha_weighted, name=name)


def derived_texture(cv, fn, srgb=False, name='uf_derived', **o):
    """derivedTexture: a per-pixel map derived from a canvas (roughness from an albedo). fn is vectorised: it gets
    numpy arrays (R, G, B, A, X, Y), values 0..255 and pixel coordinates, and returns (r, g, b) 0..255. Non-Color."""
    px = cv.rgba8().astype(np.float64)
    H, W = px.shape[:2]
    Y, X = np.mgrid[0:H, 0:W]
    r, g, b = fn(px[..., 0], px[..., 1], px[..., 2], px[..., 3], X, Y)
    out = np.empty((H, W, 4), np.uint8)
    for k, v in enumerate((r, g, b)):
        out[..., k] = np.clip(np.floor(np.asarray(v, np.float64) + 0.5), 0, 255).astype(np.uint8)
    out[..., 3] = 255
    return data_texture(out, W, H, srgb=srgb, name=name, **o)


# ------------------------------------------------------------------------------------------------ PBR sets
WITH_AO = {'Carpet012', 'Carpet013', 'CorrugatedSteel005'}       # the sets whose ambient-occlusion map is read


def acg(id, res='1k'):
    """A CC0 AmbientCG set by ID from the shared texture library (harness.assets.fetch_pbr: fetched once, on first
    use): {'map', 'normalMap', 'roughnessMap', 'aoMap'?} as bpy Images, marked repeating (three's RepeatWrapping).
    A missing file is reported ('[interiors] missing texture') and left out, as in the engine."""
    from ...harness import assets as A
    F = A.fetch_pbr(id, res)['files']
    out = {}
    want = [('map', 'diff', True), ('normalMap', 'normal', False), ('roughnessMap', 'rough', False)]
    if id in WITH_AO:
        want.append(('aoMap', 'ao', False))
    for key, fk, srgb in want:
        p = F.get(fk)
        if not p or not os.path.isfile(p):
            print('[interiors] missing texture', id, fk, p, flush=True)
            continue
        img = A.load_image_texture(p, srgb=srgb)
        img['uf_repeat'] = True
        out[key] = img
    return out


# ------------------------------------------------------------------------------------------------ noise image
NOISE_NAME = 'uf_interior_noise_v1'


def noise_texture():
    """noiseTexture: the shared tiling noise (noise_rgba, four periodic fBm channels) as ONE packed Non-Color image
    per blend, repeating, memory row 0 at v = 0."""
    bpy = _bpy()
    img = bpy.data.images.get(NOISE_NAME)
    if img is not None and tuple(img.size) == (256, 256):
        return img
    return data_texture(noise_rgba(), 256, 256, srgb=False, repeat=True, flip=False, name=NOISE_NAME)


# ================================================================================================ geometry (three axes)
def _normalize_rows(v):
    v = np.asarray(v, np.float64)
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12)


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], np.float64)


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], np.float64)


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], np.float64)


def euler_matrix(x, y, z, order='XYZ'):
    """three's Euler -> 3x3: order 'XYZ' is Rx @ Ry @ Rz (makeRotationFromEuler)."""
    R = {'X': rot_x(x), 'Y': rot_y(y), 'Z': rot_z(z)}
    return R[order[0]] @ R[order[1]] @ R[order[2]]


def rot_between(a, b):
    """quaternion.setFromUnitVectors(a, b) as a 3x3 rotation (the shortest arc taking unit a to unit b)."""
    a = np.asarray(a, np.float64) / max(np.linalg.norm(a), 1e-12)
    b = np.asarray(b, np.float64) / max(np.linalg.norm(b), 1e-12)
    c = float(np.dot(a, b))
    if c < -1 + 1e-9:                       # opposite: half a turn about any axis perpendicular to a (three's choice)
        ax = np.array([-a[1], a[0], 0.0]) if abs(a[0]) > abs(a[2]) else np.array([0.0, -a[2], a[1]])
        return axis_angle(ax, math.pi)
    v = np.cross(a, b)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]], np.float64)
    return np.eye(3) + K + K @ K / (1 + c)


def axis_angle(axis, angle):
    """quaternion.setFromAxisAngle / makeRotationAxis as a 3x3 rotation."""
    k = np.asarray(axis, np.float64)
    k = k / max(np.linalg.norm(k), 1e-12)
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]], np.float64)
    return np.eye(3) + math.sin(angle) * K + (1 - math.cos(angle)) * K @ K


def mat4(R=None, t=(0, 0, 0), s=(1, 1, 1)):
    """Matrix4.compose(position, rotation, scale) -> 4x4 (T @ R @ S)."""
    M = np.eye(4)
    M[:3, :3] = (np.eye(3) if R is None else np.asarray(R, np.float64)) * np.asarray(s, np.float64)[None, :]
    M[:3, 3] = t
    return M


class Geo:
    """three's BufferGeometry, the parts the sets use: pos (n, 3), nrm (n, 3) or None, uv (n, 2) or None, index (m,)
    or None (triangles), attrs {name: (n, k)} per-vertex data (instance colours and ids). three's axes, metres.
    The transforms mutate and return self, as three's do."""

    __slots__ = ('pos', 'nrm', 'uv', 'index', 'attrs')

    def __init__(self, pos, nrm=None, uv=None, index=None, attrs=None):
        self.pos = np.asarray(pos, np.float64).reshape(-1, 3)
        self.nrm = None if nrm is None else np.asarray(nrm, np.float64).reshape(-1, 3)
        self.uv = None if uv is None else np.asarray(uv, np.float64).reshape(-1, 2)
        self.index = None if index is None else np.asarray(index, np.int64).ravel()
        self.attrs = dict(attrs or {})

    @property
    def count(self):
        return len(self.pos)

    @property
    def triangles(self):
        return (len(self.index) if self.index is not None else len(self.pos)) // 3

    def clone(self):
        return Geo(self.pos.copy(), None if self.nrm is None else self.nrm.copy(),
                   None if self.uv is None else self.uv.copy(), None if self.index is None else self.index.copy(),
                   {k: v.copy() for k, v in self.attrs.items()})

    def to_non_indexed(self):
        if self.index is None:
            return self.clone()
        i = self.index
        return Geo(self.pos[i], None if self.nrm is None else self.nrm[i], None if self.uv is None else self.uv[i],
                   None, {k: v[i] for k, v in self.attrs.items()})

    def apply_matrix4(self, M):
        M = np.asarray(M, np.float64)
        self.pos = self.pos @ M[:3, :3].T + M[:3, 3]
        if self.nrm is not None:
            N = np.linalg.inv(M[:3, :3]).T
            self.nrm = _normalize_rows(self.nrm @ N.T)
        return self

    def apply_matrix3(self, R):
        return self.apply_matrix4(mat4(R))

    def translate(self, x, y, z):
        self.pos = self.pos + np.array([x, y, z], np.float64)
        return self

    def rotate_x(self, a):
        return self.apply_matrix3(rot_x(a))

    def rotate_y(self, a):
        return self.apply_matrix3(rot_y(a))

    def rotate_z(self, a):
        return self.apply_matrix3(rot_z(a))

    def scale(self, sx, sy, sz):
        return self.apply_matrix4(mat4(s=(sx, sy, sz)))

    def delete_attribute(self, name):
        if name == 'uv':
            self.uv = None
        elif name == 'normal':
            self.nrm = None
        else:
            self.attrs.pop(name, None)
        return self

    def compute_vertex_normals(self):
        """three's computeVertexNormals: per face (c - b) x (a - b); non-indexed -> flat, indexed -> the area-weighted
        sum at each vertex, normalised (smooth)."""
        p = self.pos
        if self.index is None:
            t = p.reshape(-1, 3, 3)
            n = _normalize_rows(np.cross(t[:, 2] - t[:, 1], t[:, 0] - t[:, 1]))
            self.nrm = np.repeat(n, 3, axis=0)
        else:
            f = self.index.reshape(-1, 3)
            a, b, c = p[f[:, 0]], p[f[:, 1]], p[f[:, 2]]
            fn = np.cross(c - b, a - b)
            acc = np.zeros_like(p)
            for k in range(3):
                np.add.at(acc, f[:, k], fn)
            self.nrm = _normalize_rows(acc)
        return self

    def bounds(self):
        return self.pos.min(0), self.pos.max(0)


def _grid_index(gx, gy, base=0):
    """three's grid triangles (a, b, d), (b, c, d) for a (gx + 1) x (gy + 1) vertex grid, row-major."""
    ix, iy = np.meshgrid(np.arange(gx), np.arange(gy))
    ix, iy = ix.ravel(), iy.ravel()
    g1 = gx + 1
    a = base + ix + g1 * iy
    b = base + ix + g1 * (iy + 1)
    c = base + ix + 1 + g1 * (iy + 1)
    d = base + ix + 1 + g1 * iy
    return np.stack([a, b, d, b, c, d], axis=1).ravel()


def box_geometry(width=1.0, height=1.0, depth=1.0, ws=1, hs=1, ds=1):
    """BoxGeometry (r184): six planes in three's order (px, nx, py, ny, pz, nz), indexed, uv per face."""
    P, N, U, I = [], [], [], []
    count = 0
    ax = {'x': 0, 'y': 1, 'z': 2}

    def plane(u, v, w, udir, vdir, wd, ht, dp, gx, gy):
        nonlocal count
        gx, gy = int(gx), int(gy)
        xs = np.arange(gx + 1) * (wd / gx) - wd / 2
        ys = np.arange(gy + 1) * (ht / gy) - ht / 2
        X, Y = np.meshgrid(xs, ys)
        n = (gx + 1) * (gy + 1)
        p = np.zeros((n, 3))
        p[:, ax[u]] = X.ravel() * udir
        p[:, ax[v]] = Y.ravel() * vdir
        p[:, ax[w]] = dp / 2
        nn = np.zeros((n, 3))
        nn[:, ax[w]] = 1.0 if dp > 0 else -1.0
        IX, IY = np.meshgrid(np.arange(gx + 1), np.arange(gy + 1))
        uv = np.stack([IX.ravel() / gx, 1 - IY.ravel() / gy], axis=1)
        P.append(p)
        N.append(nn)
        U.append(uv)
        I.append(_grid_index(gx, gy, count))
        count += n
    plane('z', 'y', 'x', -1, -1, depth, height, width, ds, hs)
    plane('z', 'y', 'x', 1, -1, depth, height, -width, ds, hs)
    plane('x', 'z', 'y', 1, 1, width, depth, height, ws, ds)
    plane('x', 'z', 'y', 1, -1, width, depth, -height, ws, ds)
    plane('x', 'y', 'z', 1, -1, width, height, depth, ws, hs)
    plane('x', 'y', 'z', -1, -1, width, height, -depth, ws, hs)
    return Geo(np.concatenate(P), np.concatenate(N), np.concatenate(U), np.concatenate(I))


def plane_geometry(width=1.0, height=1.0, ws=1, hs=1):
    """PlaneGeometry (r184): the XY plane facing +Z, uv (ix / gx, 1 - iy / gy)."""
    gx, gy = int(ws), int(hs)
    xs = np.arange(gx + 1) * (width / gx) - width / 2
    ys = np.arange(gy + 1) * (height / gy) - height / 2
    X, Y = np.meshgrid(xs, ys)
    n = (gx + 1) * (gy + 1)
    pos = np.stack([X.ravel(), -Y.ravel(), np.zeros(n)], axis=1)
    IX, IY = np.meshgrid(np.arange(gx + 1), np.arange(gy + 1))
    uv = np.stack([IX.ravel() / gx, 1 - IY.ravel() / gy], axis=1)
    return Geo(pos, np.tile([0.0, 0.0, 1.0], (n, 1)), uv, _grid_index(gx, gy))


def cylinder_geometry(radius_top=1.0, radius_bottom=1.0, height=1.0, radial_segments=32, height_segments=1,
                      open_ended=False, theta_start=0.0, theta_length=2 * math.pi):
    """CylinderGeometry (r184): the torso (slope normals) and, unless open, the caps (fans)."""
    rs, hs = int(radial_segments), int(height_segments)
    half = height / 2
    P, N, U, I = [], [], [], []
    slope = (radius_bottom - radius_top) / height
    v = np.arange(hs + 1) / hs
    u = np.arange(rs + 1) / rs
    V, Uu = np.meshgrid(v, u, indexing='ij')                     # rows y, columns x
    radius = V * (radius_bottom - radius_top) + radius_top
    th = Uu * theta_length + theta_start
    pos = np.stack([radius * np.sin(th), -V * height + half, radius * np.cos(th)], axis=-1).reshape(-1, 3)
    nrm = _normalize_rows(np.stack([np.sin(th), np.full_like(th, slope), np.cos(th)], axis=-1).reshape(-1, 3))
    uv = np.stack([Uu, 1 - V], axis=-1).reshape(-1, 2)
    P.append(pos)
    N.append(nrm)
    U.append(uv)
    idx = []
    row = lambda y, x: y * (rs + 1) + x                         # noqa: E731
    for x in range(rs):
        for y in range(hs):
            a, b, c, d = row(y, x), row(y + 1, x), row(y + 1, x + 1), row(y, x + 1)
            if radius_top > 0 or y != 0:
                idx += [a, b, d]
            if radius_bottom > 0 or y != hs - 1:
                idx += [b, c, d]
    I.append(np.array(idx, np.int64))
    count = len(pos)

    def cap(top):
        nonlocal count
        r = radius_top if top else radius_bottom
        sign = 1.0 if top else -1.0
        centre = np.tile([0.0, half * sign, 0.0], (rs, 1))
        uu = np.arange(rs + 1) / rs
        t = uu * theta_length + theta_start
        ring = np.stack([r * np.sin(t), np.full_like(t, half * sign), r * np.cos(t)], axis=1)
        P.append(np.concatenate([centre, ring]))
        N.append(np.tile([0.0, sign, 0.0], (rs + rs + 1, 1)))
        U.append(np.concatenate([np.full((rs, 2), 0.5), np.stack([np.cos(t) * 0.5 + 0.5, np.sin(t) * 0.5 * sign + 0.5], 1)]))
        c0, i0 = count, count + rs
        ii = []
        for x in range(rs):
            c, i = c0 + x, i0 + x
            ii += [i, i + 1, c] if top else [i + 1, i, c]
        I.append(np.array(ii, np.int64))
        count += rs + rs + 1
    if not open_ended:
        if radius_top > 0:
            cap(True)
        if radius_bottom > 0:
            cap(False)
    return Geo(np.concatenate(P), np.concatenate(N), np.concatenate(U), np.concatenate(I))


def cone_geometry(radius=1.0, height=1.0, radial_segments=32, height_segments=1, open_ended=False,
                  theta_start=0.0, theta_length=2 * math.pi):
    """ConeGeometry: a cylinder with radiusTop 0."""
    return cylinder_geometry(0.0, radius, height, radial_segments, height_segments, open_ended, theta_start,
                             theta_length)


def sphere_geometry(radius=1.0, width_segments=32, height_segments=16, phi_start=0.0, phi_length=2 * math.pi,
                    theta_start=0.0, theta_length=math.pi):
    """SphereGeometry (r184)."""
    ws, hs = max(3, int(width_segments)), max(2, int(height_segments))
    theta_end = min(theta_start + theta_length, math.pi)
    pos, uvs, grid = [], [], []
    k = 0
    for iy in range(hs + 1):
        v = iy / hs
        u_off = 0.5 / ws if (iy == 0 and theta_start == 0) else (-0.5 / ws if (iy == hs and theta_end == math.pi) else 0)
        row = []
        for ix in range(ws + 1):
            u = ix / ws
            pos.append((-radius * math.cos(phi_start + u * phi_length) * math.sin(theta_start + v * theta_length),
                        radius * math.cos(theta_start + v * theta_length),
                        radius * math.sin(phi_start + u * phi_length) * math.sin(theta_start + v * theta_length)))
            uvs.append((u + u_off, 1 - v))
            row.append(k)
            k += 1
        grid.append(row)
    idx = []
    for iy in range(hs):
        for ix in range(ws):
            a, b, c, d = grid[iy][ix + 1], grid[iy][ix], grid[iy + 1][ix], grid[iy + 1][ix + 1]
            if iy != 0 or theta_start > 0:
                idx += [a, b, d]
            if iy != hs - 1 or theta_end < math.pi:
                idx += [b, c, d]
    p = np.array(pos, np.float64)
    return Geo(p, _normalize_rows(p), np.array(uvs), np.array(idx, np.int64))


def rounded_box_geometry(width=1.0, height=1.0, depth=1.0, segments=2, radius=0.1):
    """RoundedBoxGeometry (three r184 addon): a 1 x 1 x 1 box of 2 * segments + 1 divisions, non-indexed, each vertex
    pushed onto the rounded corner and given its analytic normal. (Its own UVs are left as the box's: every use in
    the sets re-projects them with box_uv.)"""
    seg = int(segments) * 2 + 1
    radius = min(width / 2, height / 2, depth / 2, radius)
    g = box_geometry(1, 1, 1, seg, seg, seg).to_non_indexed()
    p = g.pos
    half = 0.5 / seg
    s = np.sign(p)
    n = _normalize_rows(p - s * half)
    box = np.array([width, height, depth]) / 2 - radius
    g.pos = box * s + n * radius
    g.nrm = n
    return g


# ------------------------------------------------------------------------------------------------ shapes, extrude
class Shape:
    """three's Shape / Path, the commands the sets draw with: move_to, line_to, quadratic_curve_to, bezier_curve_to;
    holes: a list of Shapes. get_points(divisions) follows Path.getPoints (a line gives its two ends, a curve
    `divisions` steps, consecutive duplicates dropped)."""

    def __init__(self):
        self.curves = []
        self.cur = (0.0, 0.0)
        self.holes = []

    def move_to(self, x, y):
        self.cur = (float(x), float(y))
        return self

    def line_to(self, x, y):
        self.curves.append(('L', self.cur, (float(x), float(y))))
        self.cur = (float(x), float(y))
        return self

    def quadratic_curve_to(self, cx, cy, x, y):
        self.curves.append(('Q', self.cur, (float(cx), float(cy)), (float(x), float(y))))
        self.cur = (float(x), float(y))
        return self

    def bezier_curve_to(self, c1x, c1y, c2x, c2y, x, y):
        self.curves.append(('C', self.cur, (float(c1x), float(c1y)), (float(c2x), float(c2y)), (float(x), float(y))))
        self.cur = (float(x), float(y))
        return self

    def get_points(self, divisions=12):
        pts, last = [], None
        for c in self.curves:
            if c[0] == 'L':
                cp = [c[1], c[2]]
            elif c[0] == 'Q':
                (x0, y0), (cx, cy), (x1, y1) = c[1], c[2], c[3]
                cp = []
                for i in range(divisions + 1):
                    t = i / divisions
                    k = 1 - t
                    cp.append((k * k * x0 + 2 * k * t * cx + t * t * x1, k * k * y0 + 2 * k * t * cy + t * t * y1))
            else:
                (x0, y0), (ax, ay), (bx, by), (x1, y1) = c[1], c[2], c[3], c[4]
                cp = []
                for i in range(divisions + 1):
                    t = i / divisions
                    k = 1 - t
                    cp.append((k ** 3 * x0 + 3 * k * k * t * ax + 3 * k * t * t * bx + t ** 3 * x1,
                               k ** 3 * y0 + 3 * k * k * t * ay + 3 * k * t * t * by + t ** 3 * y1))
            for p in cp:
                if last is not None and p[0] == last[0] and p[1] == last[1]:
                    continue
                pts.append(p)
                last = p
        return pts


def _area2(pts):
    a = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i - 1]
        x1, y1 = pts[i]
        a += x0 * y1 - x1 * y0
    return a * 0.5


def is_clockwise(pts):
    """ShapeUtils.isClockWise: the signed area is negative."""
    return _area2(pts) < 0


def _drop_dup_end(pts):
    pts = list(pts)
    if len(pts) > 2 and pts[0][0] == pts[-1][0] and pts[0][1] == pts[-1][1]:
        pts.pop()
    return pts


def triangulate(contour, holes=()):
    """ShapeUtils.triangulateShape: triangles (index triples into contour + holes, concatenated) over the polygon;
    Blender's scanfill (mathutils.geometry.tessellate_polygon) when it is there, ear clipping otherwise (no holes)."""
    try:
        from mathutils import geometry as MG
        loops = [[(x, y, 0.0) for x, y in contour]] + [[(x, y, 0.0) for x, y in h] for h in holes]
        return [tuple(t) for t in MG.tessellate_polygon(loops)]
    except ImportError:
        if holes:
            raise
    idx = list(range(len(contour)))
    ccw = _area2(contour) > 0
    tris = []

    def inside(p, a, b, c):
        def s(p1, p2, p3):
            return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])
        d1, d2, d3 = s(p, a, b), s(p, b, c), s(p, c, a)
        return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))
    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = contour[i0], contour[i1], contour[i2]
            cr = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if (cr > 0) != ccw or abs(cr) < 1e-15:
                continue
            if any(inside(contour[j], a, b, c) for j in idx if j not in (i0, i1, i2)):
                continue
            tris.append((i0, i1, i2))
            idx.pop(k)
            break
    if len(idx) == 3:
        tris.append(tuple(idx))
    return tris


def shape_geometry(shape, curve_segments=12):
    """ShapeGeometry (r184): the shape (with its holes) triangulated in the XY plane facing +Z, uv = (x, y)."""
    outer = _drop_dup_end(shape.get_points(curve_segments))
    if not is_clockwise(outer):
        outer = outer[::-1]
    holes = []
    for h in shape.holes:
        hp = _drop_dup_end(h.get_points(curve_segments))
        if is_clockwise(hp):
            hp = hp[::-1]
        holes.append(hp)
    pts = outer + [p for h in holes for p in h]
    tris = triangulate(outer, holes)
    P = np.array([(x, y, 0.0) for x, y in pts], np.float64)
    idx = []
    for a, b, c in tris:                                     # every face toward +Z (counter-clockwise seen from +Z)
        cr = (P[b, 0] - P[a, 0]) * (P[c, 1] - P[a, 1]) - (P[b, 1] - P[a, 1]) * (P[c, 0] - P[a, 0])
        idx += [a, b, c] if cr > 0 else [a, c, b]
    return Geo(P, np.tile([0.0, 0.0, 1.0], (len(P), 1)), P[:, :2].copy(), np.array(idx, np.int64))


def _bevel_vec(pt, prev, nxt):
    """ExtrudeGeometry's getBevelVec: the corner's offset direction (length chosen so the offset edges stay parallel)."""
    EPS = 2.220446049250313e-16
    vpx, vpy = pt[0] - prev[0], pt[1] - prev[1]
    vnx, vny = nxt[0] - pt[0], nxt[1] - pt[1]
    vp_lensq = vpx * vpx + vpy * vpy
    collinear0 = vpx * vny - vpy * vnx
    if abs(collinear0) > EPS:
        vp_len = math.sqrt(vp_lensq)
        vn_len = math.sqrt(vnx * vnx + vny * vny)
        psx, psy = prev[0] - vpy / vp_len, prev[1] + vpx / vp_len
        nsx, nsy = nxt[0] - vny / vn_len, nxt[1] + vnx / vn_len
        sf = ((nsx - psx) * vny - (nsy - psy) * vnx) / (vpx * vny - vpy * vnx)
        tx, ty = psx + vpx * sf - pt[0], psy + vpy * sf - pt[1]
        tl = tx * tx + ty * ty
        if tl <= 2:
            return (tx, ty)
        shrink = math.sqrt(tl / 2)
    else:
        eq = False
        if vpx > EPS:
            eq = vnx > EPS
        elif vpx < -EPS:
            eq = vnx < -EPS
        else:
            eq = math.copysign(1, vpy) == math.copysign(1, vny) if (vpy != 0 and vny != 0) else (vpy == vny)
        if eq:
            tx, ty, shrink = -vpy, vpx, math.sqrt(vp_lensq)
        else:
            tx, ty, shrink = vpx, vpy, math.sqrt(vp_lensq / 2)
    return (tx / shrink, ty / shrink)


def extrude_geometry(shape, depth=1.0, bevel_enabled=True, bevel_thickness=0.2, bevel_size=None, bevel_offset=0.0,
                     bevel_segments=3, curve_segments=12, steps=1):
    """ExtrudeGeometry (r184) for a shape without holes: bevel rings (sinusoidal profile, getBevelVec offsets), the
    lids triangulated, the side walls f4 -> (a, b, d), (b, c, d); non-indexed with flat normals, as three leaves it
    (computeVertexNormals on a non-indexed geometry). UVs: WorldUVGenerator (lids (x, y), walls (x or y, 1 - z))."""
    if shape.holes:
        raise NotImplementedError('extrude_geometry: shapes with holes are not used by the interiors')
    if bevel_size is None:
        bevel_size = bevel_thickness - 0.1
    if not bevel_enabled:
        bevel_segments, bevel_thickness, bevel_size, bevel_offset = 0, 0.0, 0.0, 0.0
    verts = _drop_dup_end(shape.get_points(curve_segments))
    if not is_clockwise(verts):
        verts = verts[::-1]
    faces = triangulate(verts)
    vlen = len(verts)
    moves = [_bevel_vec(verts[i], verts[i - 1], verts[(i + 1) % vlen]) for i in range(vlen)]
    layers = []

    def ring(bs, z):
        return [(verts[i][0] + moves[i][0] * bs, verts[i][1] + moves[i][1] * bs, z) for i in range(vlen)]
    for b in range(bevel_segments):
        t = b / bevel_segments
        z = bevel_thickness * math.cos(t * math.pi / 2)
        bs = bevel_size * math.sin(t * math.pi / 2) + bevel_offset
        layers.append(ring(bs, -z))
    bs = bevel_size + bevel_offset
    layers.append(ring(bs, 0.0) if bevel_enabled else [(x, y, 0.0) for x, y in verts])
    for s in range(1, steps + 1):
        layers.append(ring(bs, depth / steps * s) if bevel_enabled else [(x, y, depth / steps * s) for x, y in verts])
    for b in range(bevel_segments - 1, -1, -1):
        t = b / bevel_segments
        z = bevel_thickness * math.cos(t * math.pi / 2)
        bsb = bevel_size * math.sin(t * math.pi / 2) + bevel_offset
        layers.append(ring(bsb, depth + z))
    V = np.array([p for L_ in layers for p in L_], np.float64)
    tri_v, tri_uv = [], []

    def f3(a, b, c):
        for k in (a, b, c):
            tri_v.append(V[k])
            tri_uv.append((V[k][0], V[k][1]))

    def f4(a, b, c, d):
        A, B, C, D = V[a], V[b], V[c], V[d]
        if abs(A[1] - B[1]) < abs(A[0] - B[0]):
            uvs = [(A[0], 1 - A[2]), (B[0], 1 - B[2]), (C[0], 1 - C[2]), (D[0], 1 - D[2])]
        else:
            uvs = [(A[1], 1 - A[2]), (B[1], 1 - B[2]), (C[1], 1 - C[2]), (D[1], 1 - D[2])]
        for k, q in ((a, 0), (b, 1), (d, 3), (b, 1), (c, 2), (d, 3)):
            tri_v.append(V[k])
            tri_uv.append(uvs[q])
    top = vlen * (steps + bevel_segments * 2)
    for a, b, c in faces:                                    # the lids: the bottom faces -Z, the top +Z
        cr = (verts[b][0] - verts[a][0]) * (verts[c][1] - verts[a][1]) - (verts[b][1] - verts[a][1]) * (verts[c][0] - verts[a][0])
        a2, b2, c2 = (a, b, c) if cr > 0 else (a, c, b)       # counter-clockwise from +Z
        f3(c2, b2, a2)
        f3(a2 + top, b2 + top, c2 + top)
    for i in range(vlen - 1, -1, -1):                        # the side walls (outward on a clockwise contour)
        j, k = i, (i - 1 if i > 0 else vlen - 1)
        for s in range(steps + bevel_segments * 2):
            s1, s2 = vlen * s, vlen * (s + 1)
            f4(j + s1, k + s1, k + s2, j + s2)
    g = Geo(np.array(tri_v), None, np.array(tri_uv))
    return g.compute_vertex_normals()


# ------------------------------------------------------------------------------------------------ curves, tubes
class CatmullRomCurve3:
    """three's CatmullRomCurve3 ('centripetal' by default), with Curve's arc-length mapping (200 divisions) and
    computeFrenetFrames, as TubeGeometry uses them."""

    def __init__(self, points, closed=False, curve_type='centripetal', tension=0.5):
        self.points = [np.asarray(p, np.float64) for p in points]
        self.closed, self.curve_type, self.tension = closed, curve_type, tension
        self._lengths = None

    @staticmethod
    def _cubic(x0, x1, t0, t1, t):
        c0, c1 = x0, t0
        c2 = -3 * x0 + 3 * x1 - 2 * t0 - t1
        c3 = 2 * x0 - 2 * x1 + t0 + t1
        return c0 + c1 * t + c2 * t * t + c3 * t * t * t

    def get_point(self, t):
        pts, l = self.points, len(self.points)
        p = (l - (0 if self.closed else 1)) * t
        ip = math.floor(p)
        w = p - ip
        if self.closed:
            ip += 0 if ip > 0 else (math.floor(abs(ip) / l) + 1) * l
        elif w == 0 and ip == l - 1:
            ip, w = l - 2, 1.0
        p0 = pts[(ip - 1) % l] if (self.closed or ip > 0) else pts[0] - pts[1] + pts[0]
        p1, p2 = pts[ip % l], pts[(ip + 1) % l]
        p3 = pts[(ip + 2) % l] if (self.closed or ip + 2 < l) else pts[l - 1] - pts[l - 2] + pts[l - 1]
        if self.curve_type in ('centripetal', 'chordal'):
            pw = 0.5 if self.curve_type == 'chordal' else 0.25
            dt0 = float(np.dot(p1 - p0, p1 - p0)) ** pw
            dt1 = float(np.dot(p2 - p1, p2 - p1)) ** pw
            dt2 = float(np.dot(p3 - p2, p3 - p2)) ** pw
            if dt1 < 1e-4:
                dt1 = 1.0
            if dt0 < 1e-4:
                dt0 = dt1
            if dt2 < 1e-4:
                dt2 = dt1
            t1 = ((p1 - p0) / dt0 - (p2 - p0) / (dt0 + dt1) + (p2 - p1) / dt1) * dt1
            t2 = ((p2 - p1) / dt1 - (p3 - p1) / (dt1 + dt2) + (p3 - p2) / dt2) * dt1
            return self._cubic(p1, p2, t1, t2, w)
        k = self.tension
        return self._cubic(p1, p2, k * (p2 - p0), k * (p3 - p1), w)

    def get_lengths(self, divisions=200):
        if self._lengths is not None and len(self._lengths) == divisions + 1:
            return self._lengths
        L_, s, last = [0.0], 0.0, self.get_point(0)
        for p in range(1, divisions + 1):
            cur = self.get_point(p / divisions)
            s += float(np.linalg.norm(cur - last))
            L_.append(s)
            last = cur
        self._lengths = L_
        return L_

    def u_to_t(self, u):
        arc = self.get_lengths()
        n = len(arc)
        target = u * arc[-1]
        lo, hi = 0, n - 1
        while lo <= hi:
            i = lo + (hi - lo) // 2
            c = arc[i] - target
            if c < 0:
                lo = i + 1
            elif c > 0:
                hi = i - 1
            else:
                hi = i
                break
        i = hi
        if arc[i] == target:
            return i / (n - 1)
        before, after = arc[i], arc[i + 1]
        return (i + (target - before) / (after - before)) / (n - 1)

    def get_point_at(self, u):
        return self.get_point(self.u_to_t(u))

    def get_tangent_at(self, u):
        t = self.u_to_t(u)
        d = 0.0001
        t1, t2 = max(0.0, t - d), min(1.0, t + d)
        v = self.get_point(t2) - self.get_point(t1)
        return v / max(np.linalg.norm(v), 1e-12)

    def frenet_frames(self, segments):
        T = [self.get_tangent_at(i / segments) for i in range(segments + 1)]
        t0 = np.abs(T[0])
        mn, nrm = 1e300, None
        for k, e in ((0, (1.0, 0, 0)), (1, (0, 1.0, 0)), (2, (0, 0, 1.0))):
            if t0[k] <= mn:
                mn, nrm = t0[k], np.array(e)
        v = np.cross(T[0], nrm)
        v /= max(np.linalg.norm(v), 1e-12)
        N = [np.cross(T[0], v)]
        B = [np.cross(T[0], N[0])]
        for i in range(1, segments + 1):
            n = N[i - 1].copy()
            v = np.cross(T[i - 1], T[i])
            if np.linalg.norm(v) > 2.220446049250313e-16:
                v /= np.linalg.norm(v)
                th = math.acos(max(-1.0, min(1.0, float(np.dot(T[i - 1], T[i])))))
                n = axis_angle(v, th) @ n
            N.append(n)
            B.append(np.cross(T[i], n))
        return T, N, B


def tube_geometry(path, tubular_segments=64, radius=1.0, radial_segments=8, closed=False):
    """TubeGeometry (r184) along a curve with get_point_at / frenet_frames (CatmullRomCurve3)."""
    _T, Nf, Bf = path.frenet_frames(tubular_segments)
    P, N, U = [], [], []
    rows = list(range(tubular_segments)) + [0 if closed else tubular_segments]
    for i in rows:
        c = path.get_point_at(i / tubular_segments)
        for j in range(radial_segments + 1):
            v = j / radial_segments * math.pi * 2
            s, co = math.sin(v), -math.cos(v)
            n = co * Nf[i] + s * Bf[i]
            n = n / max(np.linalg.norm(n), 1e-12)
            N.append(n)
            P.append(c + radius * n)
    for i in range(tubular_segments + 1):
        for j in range(radial_segments + 1):
            U.append((i / tubular_segments, j / radial_segments))
    idx = []
    for j in range(1, tubular_segments + 1):
        for i in range(1, radial_segments + 1):
            a = (radial_segments + 1) * (j - 1) + (i - 1)
            b = (radial_segments + 1) * j + (i - 1)
            c = (radial_segments + 1) * j + i
            d = (radial_segments + 1) * (j - 1) + i
            idx += [a, b, d, b, c, d]
    return Geo(np.array(P), np.array(N), np.array(U), np.array(idx, np.int64))


# ------------------------------------------------------------------------------------------------ geometry utils
def box_uv(geo, scale=1.0, offset=(0.0, 0.0, 0.0)):
    """boxUV: box-projected UVs in metres (each triangle's dominant axis), on a NON-indexed copy (or on the geometry
    itself when it is already non-indexed). scale = tiles per metre."""
    g = geo.to_non_indexed() if geo.index is not None else geo
    t = g.pos.reshape(-1, 3, 3)
    e1, e2 = t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]
    nx = np.abs(e1[:, 1] * e2[:, 2] - e1[:, 2] * e2[:, 1])
    ny = np.abs(e1[:, 2] * e2[:, 0] - e1[:, 0] * e2[:, 2])
    nz = np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0])
    axis = np.where((nx >= ny) & (nx >= nz), 0, np.where(ny >= nz, 1, 2))
    axis = np.repeat(axis, 3)
    q = g.pos + np.asarray(offset, np.float64)
    x, y, z = q[:, 0], q[:, 1], q[:, 2]
    u = np.where(axis == 0, z, x)
    w = np.where(axis == 0, y, np.where(axis == 1, z, y))
    g.uv = np.stack([u, w], axis=1) * scale
    return g


def clean(geo):
    """keep only position / normal / uv, non-indexed: the common denominator for merging."""
    g = geo.to_non_indexed()
    g.attrs = {}
    if g.nrm is None:
        g.compute_vertex_normals()
    if g.uv is None:
        g.uv = np.zeros((g.count, 2))
    return g


def merge_geometries(geos, use_groups=False):
    """BufferGeometryUtils.mergeGeometries: all indexed or all not; attributes shared by every input are kept."""
    geos = [g for g in geos if g is not None and g.count]
    if not geos:
        return None
    indexed = geos[0].index is not None
    if any((g.index is not None) != indexed for g in geos):
        raise ValueError('merge_geometries: mixing indexed and non-indexed geometries')
    pos = np.concatenate([g.pos for g in geos])
    nrm = np.concatenate([g.nrm for g in geos]) if all(g.nrm is not None for g in geos) else None
    uv = np.concatenate([g.uv for g in geos]) if all(g.uv is not None for g in geos) else None
    keys = set(geos[0].attrs)
    for g in geos[1:]:
        keys &= set(g.attrs)
    attrs = {k: np.concatenate([g.attrs[k] for g in geos]) for k in keys}
    index = None
    if indexed:
        off, parts = 0, []
        for g in geos:
            parts.append(g.index + off)
            off += g.count
        index = np.concatenate(parts)
    return Geo(pos, nrm, uv, index, attrs)


def merge_vertices(geo, tolerance=1e-4):
    """BufferGeometryUtils.mergeVertices: vertices whose every attribute agrees to `tolerance` (truncated, as three
    hashes them) become one; the result is indexed."""
    g = geo.to_non_indexed() if geo.index is not None else geo
    mult = 10 ** math.log10(1 / tolerance)
    cols = [np.trunc(g.pos * mult)]
    if g.nrm is not None:
        cols.append(np.trunc(g.nrm * mult))
    if g.uv is not None:
        cols.append(np.trunc(g.uv * mult))
    key = np.ascontiguousarray(np.concatenate(cols, axis=1).astype(np.int64))
    _u, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    order = np.argsort(first)                                # keep three's first-seen vertex order
    rank = np.empty_like(order)
    rank[order] = np.arange(len(order))
    keep = first[order]
    return Geo(g.pos[keep], None if g.nrm is None else g.nrm[keep], None if g.uv is None else g.uv[keep],
               rank[inv.ravel()], {k: v[keep] for k, v in g.attrs.items()})


# ================================================================================================ the scene graph
class Node:
    """three's Object3D, as the sets use it: position, rotation (a 3x3 matrix; set with set_rotation / rotate_x ...),
    scale, children; user_data; keep (a mergeStatic 'userData.keep'); visible. After SetBuilder.emit, `ob` is its
    Blender object."""

    kind = 'group'

    def __init__(self, name=''):
        self.name = name
        self.position = np.zeros(3)
        self.R = np.eye(3)
        self.scl = np.ones(3)
        self.children = []
        self.parent = None
        self.user_data = {}
        self.keep = False
        self.ob = None

    # transforms
    def set_position(self, x, y, z):
        self.position = np.array([x, y, z], np.float64)
        return self

    def set_rotation(self, x=0.0, y=0.0, z=0.0, order='XYZ'):
        self.R = euler_matrix(x, y, z, order)
        return self

    def set_scale(self, x, y=None, z=None):
        self.scl = np.array([x, x if y is None else y, x if z is None else z], np.float64)
        return self

    def rotate_x(self, a):
        self.R = self.R @ rot_x(a)
        return self

    def rotate_y(self, a):
        self.R = self.R @ rot_y(a)
        return self

    def rotate_z(self, a):
        self.R = self.R @ rot_z(a)
        return self

    def set_from_unit_vectors(self, a, b):
        self.R = rot_between(a, b)
        return self

    def set_from_axis_angle(self, axis, angle):
        self.R = axis_angle(axis, angle)
        return self

    def matrix(self):
        return mat4(self.R, self.position, self.scl)

    def matrix_world(self):
        M = self.matrix()
        p = self.parent
        while p is not None:
            M = p.matrix() @ M
            p = p.parent
        return M

    def world_position(self):
        return self.matrix_world()[:3, 3].copy()

    # hierarchy
    def add(self, *nodes):
        for n in nodes:
            if n.parent is not None:
                n.parent.children.remove(n)
            n.parent = self
            self.children.append(n)
        return self

    def remove(self, n):
        if n in self.children:
            self.children.remove(n)
            n.parent = None
        return self

    def traverse(self, fn):
        fn(self)
        for c in list(self.children):
            c.traverse(fn)


class MeshNode(Node):
    """a Mesh: geo + one bpy material; cast / recv (castShadow / receiveShadow), render_order (kept for parity:
    EEVEE sorts blended surfaces per object itself)."""

    kind = 'mesh'

    def __init__(self, geo, material, name='', cast=True, recv=True, keep=False):
        super().__init__(name)
        self.geo, self.material = geo, material
        self.cast, self.recv, self.keep = cast, recv, keep
        self.render_order = 0


class InstancedMeshNode(MeshNode):
    """an InstancedMesh: one geometry, `count` matrices (set_matrix_at) and optional per-instance colours
    (set_color_at). It is realised into one Blender mesh at emission: positionLocal then includes the instance
    transform, as three's InstanceNode makes it, and the colour becomes the per-vertex attribute 'instance_color'
    (with 'instance_id', the instanceIndex) that the material multiplies in."""

    kind = 'instanced'

    def __init__(self, geo, material, count, name='', cast=True, recv=True):
        super().__init__(geo, material, name, cast, recv, keep=True)
        self.count = int(count)
        self.matrices = np.tile(np.eye(4), (self.count, 1, 1))
        self.colors = None
        self.inst_attrs = {}

    def set_matrix_at(self, i, M):
        self.matrices[i] = M

    def set_color_at(self, i, rgb):
        if self.colors is None:
            self.colors = np.ones((self.count, 3))
        self.colors[i] = rgb

    def set_instance_attr(self, name, values):
        """a per-instance float attribute (one value per instance, read in the material with g.attribute(name)):
        what the engine's shader derived from instanceIndex alone, computed at build time (e.g.
        pcg_hash(ids + 17.0), three's exact hash where White Noise would pick other instances)."""
        v = np.asarray(values, np.float64).reshape(-1)
        assert len(v) == self.count, f'{name}: {len(v)} values for {self.count} instances'
        self.inst_attrs[name] = v

    def realize(self):
        base = self.geo
        n = base.count
        M = self.matrices
        pos = np.einsum('kij,nj->kni', M[:, :3, :3], base.pos) + M[:, None, :3, 3]
        out = Geo(pos.reshape(-1, 3))
        if base.nrm is not None:
            Ninv = np.linalg.inv(M[:, :3, :3]).transpose(0, 2, 1)
            out.nrm = _normalize_rows(np.einsum('kij,nj->kni', Ninv, base.nrm).reshape(-1, 3))
        if base.uv is not None:
            out.uv = np.tile(base.uv, (self.count, 1))
        if base.index is not None:
            out.index = (base.index[None, :] + (np.arange(self.count) * n)[:, None]).ravel()
        out.attrs['instance_id'] = np.repeat(np.arange(self.count, dtype=np.float64), n)[:, None]
        if self.colors is not None:
            out.attrs['instance_color'] = np.repeat(self.colors, n, axis=0)
        for k, v in self.inst_attrs.items():
            out.attrs[k] = np.repeat(v, n)[:, None]
        return out


class CSGMeshNode(MeshNode):
    """three-bvh-csg's Evaluator.evaluate(A, B, SUBTRACTION) with useGroups: A's mesh minus B's, the cut faces in B's
    material. Emitted with Blender's exact Boolean (DIFFERENCE, materials transferred from the cutter), applied: the
    result is one mesh with two material slots. A is smooth-shaded (three merged its vertices and computed smooth
    normals), the cut walls flat."""

    kind = 'csg'

    def __init__(self, geo, material, cutter, cutter_material, name='', cast=True, recv=True):
        super().__init__(geo, material, name, cast, recv, keep=True)
        self.cutter, self.cutter_material = cutter, cutter_material


class LightNode(Node):
    """a three light: 'point' (PointLight(color, intensity cd, distance, decay)), 'spot' (SpotLight(color, intensity,
    distance, angle, penumbra, decay)) or 'directional' (DirectionalLight(color, intensity lux)); target (a Node);
    cast_shadow. Emitted as a Blender POINT / SPOT / SUN (lux_scale / candela conversion in the module docstring),
    aimed at its target by a Track To constraint, so moving the target re-aims it as in three."""

    kind = 'light'

    def __init__(self, light_type, color, intensity, distance=0.0, decay=2.0, angle=math.pi / 3, penumbra=0.0,
                 name='', cast_shadow=False, radius=0.03, sun_angle_deg=1.0):
        super().__init__(name)
        self.light_type = light_type
        self.color, self.intensity = int(color), float(intensity)
        self.distance, self.decay = float(distance), float(decay)
        self.angle, self.penumbra = float(angle), float(penumbra)
        self.cast_shadow = bool(cast_shadow)
        self.radius, self.sun_angle_deg = float(radius), float(sun_angle_deg)
        self.target = None
        self.energy_scale = None                 # W per candela (or W/m2 per lux), fixed at emission

    def watts(self, intensity=None):
        """The Blender energy for a three intensity (cd, or lux for a directional light)."""
        i = self.intensity if intensity is None else float(intensity)
        return i * (self.energy_scale if self.energy_scale is not None else self._scale())

    def _scale(self):
        if self.light_type == 'directional':
            return 1.0
        s = 4.0 * math.pi
        if abs(self.decay - 2.0) > 1e-6:
            # three's falloff is 1 / d^decay; Blender's is inverse square: match at the target (or 1 m)
            d = 1.0
            if self.target is not None:
                d = float(np.linalg.norm(self.target.world_position() - self.world_position())) or 1.0
            s *= d ** (2.0 - self.decay)
        return s


def three_spot_blend(angle, penumbra):
    """three's penumbra (a share of the cone ANGLE) as Blender's spot_blend (a share of 1 - cos(half angle)): both
    are a smoothstep in cos(theta), from cos(angle) to cos(angle * (1 - penumbra)), so this is exact."""
    ca = math.cos(angle)
    if 1 - ca < 1e-9:
        return 0.0
    return max(0.0, min(1.0, (math.cos(angle * (1 - penumbra)) - ca) / (1 - ca)))


def merge_static(root, shadows=True):
    """mergeStatic: the static meshes under `root` (recursively) become ONE mesh per material, in root space. Meshes
    and groups with keep stay; instanced meshes stay. Returns the new MeshNodes (added under root)."""
    inv = np.linalg.inv(root.matrix_world())
    buckets = {}
    victims = []

    def visit(o):
        if o is root or not isinstance(o, MeshNode) or isinstance(o, InstancedMeshNode) or o.keep:
            return
        p = o.parent
        while p is not None and p is not root:
            if p.keep:
                return
            p = p.parent
        if o.material is None or isinstance(o.material, (list, tuple)):
            return
        g = clean(o.geo)
        g.apply_matrix4(inv @ o.matrix_world())
        key = id(o.material)
        bk = buckets.setdefault(key, {'mat': o.material, 'geos': [], 'cast': False, 'recv': False})
        bk['geos'].append(g)
        bk['cast'] = bk['cast'] or o.cast
        bk['recv'] = bk['recv'] or o.recv
        victims.append(o)
    root.traverse(visit)
    for o in victims:
        o.parent.remove(o)
    out = []
    for bk in buckets.values():
        merged = merge_geometries(bk['geos'])
        if merged is None:
            print('[interiors] merge failed for', bk['mat'].name, flush=True)
            continue
        m = MeshNode(merged, bk['mat'], name='merged:' + bk['mat'].name, cast=shadows and bk['cast'], recv=bk['recv'])
        root.add(m)
        out.append(m)
    return out


# ================================================================================================ emission
C3 = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], np.float64)          # three (x, y, z) -> Blender (x, -z, y)


def to_blender_matrix(M):
    """A three-space 4x4 (a local or world transform) in Blender's axes: C @ M @ C^-1."""
    M = np.asarray(M, np.float64)
    B = np.eye(4)
    B[:3, :3] = C3 @ M[:3, :3] @ C3.T
    B[:3, 3] = C3 @ M[:3, 3]
    return B


def to_blender(p):
    return tuple(float(v) for v in C3 @ np.asarray(p, np.float64))


def mesh_from_geo(name, geo, weld=True, custom_normals=True, smooth=None):
    """A bpy Mesh from a Geo in three's axes: positions and normals converted to Blender's, triangles, the UV layer
    'UVMap', the normals as custom normals (three's analytic or computed ones, so a rounded box is smooth and a box
    is flat), per-vertex attrs as POINT attributes. weld merges vertices that agree in every attribute.
    custom_normals=False leaves the normals to Blender (smooth=True / False shades the faces so)."""
    bpy = _bpy()
    g = geo
    if not custom_normals:
        g = Geo(geo.pos, None, geo.uv, geo.index, geo.attrs)
    index = g.index if g.index is not None else np.arange(g.count)
    pos = g.pos @ C3.T
    nrm = None if g.nrm is None else g.nrm @ C3.T
    uv = g.uv
    attrs = dict(g.attrs)
    if weld and g.count:
        cols = [np.round(pos * 1e6)]
        if nrm is not None:
            cols.append(np.round(nrm * 1e5))
        if uv is not None:
            cols.append(np.round(uv * 1e6))
        for v in attrs.values():
            cols.append(np.round(np.asarray(v, np.float64).reshape(g.count, -1) * 1e6))
        key = np.ascontiguousarray(np.concatenate(cols, axis=1).astype(np.int64))
        _u, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
        inv = inv.ravel()
        pos = pos[first]
        nrm = None if nrm is None else nrm[first]
        uv_v = None if uv is None else uv[first]
        attrs = {k: np.asarray(v).reshape(g.count, -1)[first] for k, v in attrs.items()}
        index = inv[index]
    else:
        uv_v = uv
    tri = index.reshape(-1, 3)
    # degenerate triangles (two corners on one welded vertex) are dropped: Blender would not keep them
    ok = (tri[:, 0] != tri[:, 1]) & (tri[:, 1] != tri[:, 2]) & (tri[:, 0] != tri[:, 2])
    tri = tri[ok]
    nt = len(tri)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(pos))
    me.vertices.foreach_set('co', pos.astype(np.float32).ravel())
    me.loops.add(nt * 3)
    me.loops.foreach_set('vertex_index', tri.astype(np.int32).ravel())
    me.polygons.add(nt)
    me.polygons.foreach_set('loop_start', (np.arange(nt) * 3).astype(np.int32))
    me.polygons.foreach_set('loop_total', np.full(nt, 3, np.int32))
    if uv_v is not None:
        L = me.uv_layers.new(name='UVMap')
        L.data.foreach_set('uv', uv_v[tri.ravel()].astype(np.float32).ravel())
    for k, v in attrs.items():
        v = np.asarray(v, np.float32)
        if v.shape[1] == 1:
            a = me.attributes.new(k, 'FLOAT', 'POINT')
            a.data.foreach_set('value', v.ravel())
        else:
            a = me.attributes.new(k, 'FLOAT_VECTOR', 'POINT')
            a.data.foreach_set('vector', np.pad(v, ((0, 0), (0, 3 - v.shape[1]))).ravel())
    me.update()
    if nrm is not None and nt:
        me.polygons.foreach_set('use_smooth', np.ones(nt, bool))
        me.normals_split_custom_set_from_vertices(nrm.astype(np.float32))
    elif smooth is not None and nt:
        me.polygons.foreach_set('use_smooth', np.full(nt, bool(smooth)))
    return me


def csg_subtract(name, geo, material, cutter, cutter_material, collection, depsgraph_scene):
    """A minus B with Blender's exact Boolean (three-bvh-csg's SUBTRACTION with useGroups): a new bpy Mesh, A's
    faces in `material` (smooth), the walls the cutter made in `cutter_material` (flat)."""
    bpy = _bpy()
    me_a = mesh_from_geo(name, geo, custom_normals=False, smooth=True)
    me_b = mesh_from_geo(name + '_cutter', cutter, custom_normals=False, smooth=False)
    me_a.materials.append(material)
    me_b.materials.append(cutter_material)
    ob_a = bpy.data.objects.new(name + '_csgA', me_a)
    ob_b = bpy.data.objects.new(name + '_csgB', me_b)
    collection.objects.link(ob_a)
    collection.objects.link(ob_b)
    mod = ob_a.modifiers.new('csg', 'BOOLEAN')
    mod.operation, mod.solver, mod.object = 'DIFFERENCE', 'EXACT', ob_b
    mod.material_mode = 'TRANSFER'
    vl = depsgraph_scene.view_layers[0]
    dg = vl.depsgraph
    dg.update()
    me = bpy.data.meshes.new_from_object(ob_a.evaluated_get(dg))
    me.name = name
    for ob in (ob_a, ob_b):
        bpy.data.objects.remove(ob, do_unlink=True)
    for m_ in (me_a, me_b):
        if m_.users == 0:
            bpy.data.meshes.remove(m_)
    return me


class Keyer:
    """What update() changes, keyed at a frame. With a scene ctx (harness) the keys go through ctx.key (the runner
    makes them LINEAR afterwards); without one, the first key of a channel is made with keyframe_insert and every
    later one is written straight into its F-curve, LINEAR."""

    def __init__(self, ctx=None):
        self.ctx = ctx
        self._fc = {}

    def key(self, target, data_path, frame, index=-1, interpolation='LINEAR'):
        if self.ctx is not None:
            return self.ctx.key(target, data_path, index=index, frame=frame, interpolation=interpolation)
        k = (target.as_pointer(), data_path, index)
        fcs = self._fc.get(k)
        if fcs is None:
            target.keyframe_insert(data_path, index=index, frame=frame)
            fcs = self._find(target, data_path, index)
            self._fc[k] = fcs
            for fc in fcs:
                for kp in fc.keyframe_points:
                    if abs(kp.co.x - frame) < 1e-6:
                        kp.interpolation = interpolation
            return True
        val = target.path_resolve(data_path)
        for fc in fcs:
            v = val[fc.array_index] if hasattr(val, '__len__') else val
            kp = fc.keyframe_points.insert(frame, float(v), options={'FAST'})
            kp.interpolation = interpolation
        return True

    @staticmethod
    def _find(target, data_path, index):
        idb = target.id_data
        full = target.path_from_id(data_path)
        ad = idb.animation_data
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
        return [fc for fc in cb.fcurves if fc.data_path == full and (index < 0 or fc.array_index == index)]

    def finish(self):
        for fcs in self._fc.values():
            for fc in fcs:
                fc.update()


class SetBuilder:
    """A set's build in Blender: its collection, its root Empty (the WebGPU `group`: move it to park the set), the
    scene graph rooted there (root, three's axes), what it made (dispose removes it), and emit(), which turns the
    graph into Blender objects once the build is done."""

    def __init__(self, name, scene=None, collection=None):
        bpy = _bpy()
        self.scene = scene or bpy.context.scene
        self.name = name
        if collection is None:
            collection = bpy.data.collections.new(name)
            self.scene.collection.children.link(collection)
        self.coll = collection
        self.root_ob = bpy.data.objects.new(name, None)
        self.root_ob.empty_display_size = 0.5
        self.coll.objects.link(self.root_ob)
        self.root = Node(name)
        self.root.ob = self.root_ob
        self.made = {'objects': [self.root_ob], 'meshes': [], 'materials': [], 'images': [], 'worlds': [],
                     'lights': [], 'cameras': [], 'probes': [], 'collections': [self.coll] if collection else []}

    def track(self, x):
        bpy = _bpy()
        kinds = ((bpy.types.Material, 'materials'), (bpy.types.Image, 'images'), (bpy.types.World, 'worlds'),
                 (bpy.types.Mesh, 'meshes'), (bpy.types.Object, 'objects'))
        for t, k in kinds:
            if isinstance(x, t):
                self.made[k].append(x)
        return x

    def uniform(self, name, value=0.0):
        """Declare a uniform: a float custom property on the root Empty, read by the materials through drivers."""
        self.root_ob[name] = float(value)
        return name

    def emit(self):
        """The scene graph -> Blender objects (Empties, meshes, lights), parented as in three, transforms converted;
        then every light with a target gets its Track To. Returns the number of objects made."""
        bpy = _bpy()
        from mathutils import Matrix
        pending = []
        n0 = len(self.made['objects'])

        def link(ob):
            self.coll.objects.link(ob)
            self.made['objects'].append(ob)
            return ob

        def make(node, parent_ob):
            nm = f'{self.name}:{node.name or node.kind}'
            if node.kind == 'csg':
                me = csg_subtract(nm, node.geo, node.material, node.cutter, node.cutter_material, self.coll,
                                  self.scene)
                self.made['meshes'].append(me)
                ob = link(bpy.data.objects.new(nm, me))
                ob.visible_shadow = bool(node.cast)
            elif node.kind in ('mesh', 'instanced'):
                geo = node.realize() if node.kind == 'instanced' else node.geo
                if geo is None or geo.count == 0:
                    return
                me = mesh_from_geo(nm, geo)
                self.made['meshes'].append(me)
                if node.material is not None:
                    me.materials.append(node.material)
                ob = link(bpy.data.objects.new(nm, me))
                ob.visible_shadow = bool(node.cast)
                m = node.material
                if m is not None:
                    ob.hide_probe_volume = bool(m.get('uf_hide_probe_volume', False))
                    ob.hide_probe_sphere = bool(m.get('uf_hide_probe_sphere', False))
                    if m.get('uf_hide_camera', False):
                        ob.visible_camera = False
            elif node.kind == 'light':
                kind = {'point': 'POINT', 'spot': 'SPOT', 'directional': 'SUN'}[node.light_type]
                ld = bpy.data.lights.new(nm, kind)
                self.made['lights'].append(ld)
                ld.color = hex_linear(node.color)
                ld.use_shadow = node.cast_shadow
                if kind == 'SUN':
                    ld.angle = math.radians(node.sun_angle_deg)
                else:
                    ld.shadow_soft_size = node.radius
                    if node.distance > 0:
                        ld.use_custom_distance = True
                        ld.cutoff_distance = node.distance
                if kind == 'SPOT':
                    ld.spot_size = min(math.pi, 2.0 * node.angle)
                    ld.spot_blend = three_spot_blend(node.angle, node.penumbra)
                ob = link(bpy.data.objects.new(nm, ld))
                pending.append(node)
            else:
                ob = link(bpy.data.objects.new(nm, None))
                ob.empty_display_size = 0.1
            ob.parent = parent_ob
            ob.matrix_parent_inverse = Matrix.Identity(4)
            ob.matrix_basis = Matrix(to_blender_matrix(node.matrix()).tolist())
            node.ob = ob
            for c in node.children:
                make(c, ob)
        for c in self.root.children:
            make(c, self.root_ob)
        for ln in pending:
            ln.energy_scale = ln._scale()
            ln.ob.data.energy = ln.watts()
            if ln.target is not None and ln.light_type in ('spot', 'directional'):
                if ln.target.ob is None:
                    raise RuntimeError(f'light {ln.name}: its target {ln.target.name} is not in the set')
                c = ln.ob.constraints.new('TRACK_TO')
                c.target = ln.target.ob
                c.track_axis = 'TRACK_NEGATIVE_Z'
                c.up_axis = 'UP_Y'
        return len(self.made['objects']) - n0

    def dispose(self):
        """Remove everything the build made: objects, meshes, lights, materials, its images (not the shared library's
        or the shared noise), worlds with their env images (the scene lets go of the set's World first, as three's
        dispose released the env texture), the Actions its keys made, its collection."""
        bpy = _bpy()
        actions = []
        for ob in self.made['objects']:
            try:
                for idb in (ob, getattr(ob, 'data', None)):
                    ad = getattr(idb, 'animation_data', None) if idb is not None else None
                    if ad and ad.action:
                        actions.append(ad.action)
            except ReferenceError:
                pass
        for w in self.made['worlds']:
            try:
                img = bpy.data.images.get(w.get('uf_env_image', '')) if w is not None else None
                if img is not None:
                    self.made['images'].append(img)
                for sc in bpy.data.scenes:
                    if sc.world == w:
                        sc.world = None
            except ReferenceError:
                pass
        for ob in self.made['objects']:
            if ob and ob.name in bpy.data.objects:
                bpy.data.objects.remove(ob, do_unlink=True)
        for kind, coll in (('meshes', bpy.data.meshes), ('lights', bpy.data.lights), ('materials', bpy.data.materials),
                           ('worlds', bpy.data.worlds), ('images', bpy.data.images), ('cameras', bpy.data.cameras),
                           ('probes', bpy.data.lightprobes)):
            for d in self.made[kind]:
                try:
                    if d is not None and d.name in coll and d.users == 0:
                        coll.remove(d)
                except ReferenceError:
                    pass
        for a in {a.as_pointer(): a for a in actions}.values():
            try:
                if a.name in bpy.data.actions and a.users == 0:
                    bpy.data.actions.remove(a)
            except ReferenceError:
                pass
        for c in self.made['collections']:
            try:
                if c.name in bpy.data.collections:
                    bpy.data.collections.remove(c)
            except ReferenceError:
                pass


DEFAULT_PIXEL_ANGLE = 2 * math.tan(math.radians(20)) / 1080       # 1080p at a 40 degree vertical field of view


def camera_pixel_angle(scene, cam=None):
    """The angle one rendered pixel subtends at the centre of `cam` (default: the scene's camera), from its lens,
    sensor and sensor fit and the render size: fwidth's scale for a shader that must know its screen footprint.
    Without a camera: DEFAULT_PIXEL_ANGLE."""
    cam = cam or scene.camera
    if cam is None or cam.type != 'CAMERA' or cam.data.type != 'PERSP':
        return DEFAULT_PIXEL_ANGLE
    d, r = cam.data, scene.render
    k = r.resolution_percentage / 100.0
    rx, ry = r.resolution_x * k, r.resolution_y * k
    if d.sensor_fit == 'VERTICAL':
        return d.sensor_height / d.lens / ry
    if d.sensor_fit == 'HORIZONTAL':
        return d.sensor_width / d.lens / rx
    return d.sensor_width / d.lens / max(rx, ry)


def cam_to_blender(cam):
    """A three-space set cam {'pos', 'target', 'fov'} in Blender's axes (fov stays vertical degrees)."""
    out = dict(cam)
    out['pos'], out['target'] = to_blender(cam['pos']), to_blender(cam['target'])
    return out


def make_camera(sb, name, cam, clip_end=1000.0, clip_start=0.03, parent=True, axes='blender'):
    """A Blender camera for a set cam {'pos', 'target', 'fov' (vertical degrees, three's PerspectiveCamera)},
    set-local (Blender axes, or axes='three' for the engine's numbers): parented to the set's root, so it follows
    the set wherever the root is parked."""
    bpy = _bpy()
    from mathutils import Matrix, Vector
    from ...look import camera as LC
    if axes == 'three':
        cam = cam_to_blender(cam)
    cd = bpy.data.cameras.new(f'{sb.name}:cam:{name}')
    cd.sensor_fit = 'VERTICAL'
    cd.angle_y = math.radians(cam['fov'])
    cd.clip_start, cd.clip_end = clip_start, clip_end
    ob = bpy.data.objects.new(f'{sb.name}:cam:{name}', cd)
    sb.coll.objects.link(ob)
    sb.made['objects'].append(ob)
    sb.made['cameras'].append(cd)
    M = LC.look_matrix(Vector(cam['pos']), Vector(cam['target']))
    if parent:
        ob.parent = sb.root_ob
        ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = M
    return ob


# ================================================================================================ the set
def scene_and_ctx(first=None, scene=None):
    """build(ctx, ...) / build(scene, ...): the registry (eidoblend.sets.build) passes the harness ctx first; a
    scene works there too. -> (scene, ctx)."""
    bpy = _bpy()
    ctx = None
    if first is not None:
        if isinstance(first, bpy.types.Scene):
            scene = scene or first
        elif hasattr(first, 'scene') and hasattr(first, 'key'):
            ctx = first
            scene = scene or first.scene
        else:
            raise TypeError(f'build: the first argument is a harness ctx or a bpy Scene, not {type(first).__name__}')
    return scene or bpy.context.scene, ctx


# ------------------------------------------------------------------------------------------------ the asset's options
def frame_list(frames):
    """animate()'s frames: a (first, last) pair of ints (inclusive), a range, or any iterable of frame numbers."""
    if isinstance(frames, tuple) and len(frames) == 2 and all(isinstance(v, (int, np.integer)) for v in frames):
        fs = list(range(int(frames[0]), int(frames[1]) + 1))
    else:
        fs = [int(f) for f in frames]
    if not fs:
        raise ValueError('animate: no frames')
    return fs


def state_curve(spec, default=0.0):
    """One state key over time, for animate(): None (its default), a number (held), (start, end) seconds on the
    set's clock (0 -> 1, linear between them, held outside), (start, end, from, to) (from -> to), or a function of t
    (an eased ramp: lambda t: smooth(ramp(t, 2.0, 4.0)))."""
    if spec is None:
        v = float(default)
        return lambda t: v
    if callable(spec):
        return spec
    if isinstance(spec, (tuple, list)):
        if len(spec) == 2:
            a, b, v0, v1 = float(spec[0]), float(spec[1]), 0.0, 1.0
        elif len(spec) == 4:
            a, b, v0, v1 = (float(x) for x in spec)
        else:
            raise ValueError(f'state_curve: (start, end) or (start, end, from, to), not {spec!r}')
        if b <= a:
            return lambda t: v1 if t >= a else v0
        return lambda t: v0 + (v1 - v0) * ramp(t, a, b)
    v = float(spec)
    return lambda t: v


def override_canvas(o, W, H, fonts=None):
    """A piece's own art for one of a set's canvases (build(art={key: o})), as a W x H Canvas: a painter
    o(ctx, W, H) drawn on a fresh transparent canvas (the marker kit and the UF fonts work there), an image file
    (str or Path), a Pillow image, a uint8 RGBA / RGB array (row 0 at the top) or a Canvas. Pictures are resized to
    W x H (with premultiplied alpha): the set's UVs and the maps it derives from a canvas (a board's ink roughness)
    are laid out for that size. Plain Python (Pillow + numpy)."""
    from PIL import Image
    if isinstance(o, Canvas) and (o.width, o.height) == (int(W), int(H)):
        return o
    if callable(o) and not isinstance(o, Canvas):
        cv, ctx = canvas(fonts or napi(), W, H)
        o(ctx, W, H)
        return cv
    if isinstance(o, Canvas):
        im = Image.fromarray(o.rgba8(), 'RGBA')
    elif isinstance(o, (str, os.PathLike)):
        if not Path(o).is_file():
            raise FileNotFoundError(f'override_canvas: no image at {o}')
        im = Image.open(o)
    elif isinstance(o, Image.Image):
        im = o
    else:
        a = np.asarray(o)
        if a.dtype != np.uint8 or a.ndim != 3 or a.shape[2] not in (3, 4):
            raise TypeError('override_canvas: a painter, an image path, a Pillow image, a uint8 RGB(A) array or a '
                            f'Canvas, not {type(o).__name__}')
        im = Image.fromarray(a, 'RGBA' if a.shape[2] == 4 else 'RGB')
    im = im.convert('RGBA')
    if im.size != (int(W), int(H)):
        im = im.convert('RGBa').resize((int(W), int(H)), Image.LANCZOS).convert('RGBA')
    a = np.asarray(im, np.float32) / 255.0
    cv = Canvas(W, H, fonts)
    cv.buf[..., :3] = a[..., :3] * a[..., 3:4]
    cv.buf[..., 3] = a[..., 3]
    return cv


def check_art(art, canvases, where):
    """build(art=...)'s keys must name the set's canvases (a typo would silently keep the set's own art)."""
    bad = sorted(set(art or {}) - set(canvases))
    if bad:
        raise KeyError(f'{where}: no canvas {", ".join(map(repr, bad))} (canvases: {", ".join(canvases)})')


_SEQ_RE = re.compile(r'^(.*?)(\d+)(\.[A-Za-z0-9]+)$')


def media_image(path, name=None):
    """A clip for a screen: a movie (anything Blender's FFmpeg reads), an image sequence (name its first numbered
    file: the run of consecutive numbers from there, same digit count, is the clip) or a still. -> (bpy Image,
    {'frames': its length (1 for a still), 'offset': the image user's frame_offset that puts the named file on the
    clip's first frame, 'size': (w, h) or None when Blender has not read it}). sRGB, not packed (it plays from disk)."""
    bpy = _bpy()
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f'media_image: no file at {p}')
    img = bpy.data.images.load(str(p), check_existing=False)
    if name:
        img.name = name
    info = {'frames': 1, 'offset': 0, 'size': None}
    try:                                     # read while it is one file: a SEQUENCE reports 0 x 0 until it plays
        w, h = img.size[:]
        if w > 0 and h > 0:
            info['size'] = (int(w), int(h))
    except (RuntimeError, ValueError):
        pass
    if img.source == 'MOVIE':
        info['frames'] = int(img.frame_duration)
    else:
        m = _SEQ_RE.match(p.name)
        if m:
            pre, num, ext = m.groups()
            pat = re.compile(re.escape(pre) + r'(\d{%d})' % len(num) + re.escape(ext) + r'$')
            have = {int(mm.group(1)) for f in p.parent.iterdir() for mm in [pat.match(f.name)] if mm}
            first = k = int(num)
            while k in have:
                k += 1
            if k - first > 1:
                img.source = 'SEQUENCE'
                info['frames'], info['offset'] = k - first, first - 1
    return img, info


class InteriorSet(dict):
    """An interior as the engine returned it: a dict of its contract (group, collection, parts, update, dispose,
    cams, cams_three, mark, focal, env, probe, ...), whose keys also read as attributes (room.parts is
    room['parts']), plus the Blender side every interior shares: show, make_camera, eevee_settings, bake_probes."""

    CLIP_END = 1000.0

    STATE = {}                 # the set's update() keys and their defaults (each set says)
    STATE_ALIASES = {}         # snake_case spellings of the engine's keys (ship_t -> shipT)

    def __init__(self, sb, ctx=None):
        super().__init__()
        self.sb, self.ctx, self.keyer = sb, ctx, None
        self._env_switch = None                  # the shared World (env_switch) when several sets share the scene
        sb.root_ob['uf_env_on'] = 1.0            # this set's weight in a shared World: show() keys it with the cut
        _LIVE_SETS.append(weakref.ref(self))     # the sets built in this session: a bake hides the others
        self['group'] = self['root'] = sb.root_ob
        self['collection'] = sb.coll
        for k in ('update', 'animate', 'dispose', 'make_camera', 'eevee_settings', 'bake_probes', 'show', 'show_part'):
            self[k] = getattr(self, k)

    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k) from None

    # keys ------------------------------------------------------------------------------------------------
    def _ctx(self, ctx):
        return ctx if ctx is not None else self.ctx

    def _keyer(self, ctx):
        ctx = self._ctx(ctx)
        if self.keyer is None or self.keyer.ctx is not ctx:
            self.keyer = Keyer(ctx)
        return self.keyer

    def _frame(self, t, frame, ctx):
        if frame is not None:
            return frame
        ctx = self._ctx(ctx)
        if ctx is not None:
            return ctx.frame_at(t)
        return self.sb.scene.frame_current

    # the contract ------------------------------------------------------------------------------------------
    def update(self, t, state=None, frame=None, ctx=None, key=True):
        raise NotImplementedError

    def animate(self, frames, t0=0.0, fps=None, ctx=None, update_kw=None, **state):
        """Key the set over `frames` on its own clock: frame f plays time t = t0 + (f - first frame) / fps (fps: the
        scene's), and each state key given follows its curve (state_curve: a number, (start, end) seconds for
        0 -> 1, (start, end, from, to), or a function of t); keys not given hold their defaults (STATE). Every frame
        goes through update(), keyed, so the saved .blend plays on its own. update_kw: more update() arguments (a
        dict, or a function of the frame). Returns {frame: t}."""
        fs = frame_list(frames)
        sc = self.sb.scene
        fps = float(fps or sc.render.fps / sc.render.fps_base)
        curves = {}
        for k, spec in state.items():
            name = self.STATE_ALIASES.get(k, k)
            if name not in self.STATE:
                raise TypeError(f'animate: no state key {k!r} (keys: {", ".join(self.STATE)})')
            curves[name] = state_curve(spec, self.STATE[name])
        out = {}
        for f in fs:
            t = float(t0) + (f - fs[0]) / fps
            kw = update_kw(f) if callable(update_kw) else dict(update_kw or {})
            self.update(t, {k: c(t) for k, c in curves.items()}, frame=f, ctx=ctx, **kw)
            out[f] = t
        self._keyer(ctx).finish()
        return out

    def show(self, visible=True, frame=None, ctx=None):
        """Hide the whole set (its lights stop lighting; hide it when it is off screen) or show it; with a frame
        the switch is keyed (CONSTANT: a cut). The first keyed switch also keys the state before it on the frame
        before (an F-curve holds its first key backwards, which would switch the set off from the first frame).
        The set's env follows: its weight in a shared World (env_switch, several sets in one scene) is keyed with
        the cut, so each set is lit by its own env while it is on screen."""
        if not hasattr(self, '_vis_keyed'):
            self._vis_keyed = set()
        k = self._keyer(ctx) if frame is not None else None
        for ob in self.sb.made['objects']:
            if ob is None:
                continue
            if frame is not None and ob.as_pointer() not in self._vis_keyed:
                self._vis_keyed.add(ob.as_pointer())
                k.key(ob, 'hide_render', frame - 1, interpolation='CONSTANT')
                k.key(ob, 'hide_viewport', frame - 1, interpolation='CONSTANT')
            ob.hide_render = not visible
            ob.hide_viewport = not visible
            if frame is not None:
                k.key(ob, 'hide_render', frame, interpolation='CONSTANT')
                k.key(ob, 'hide_viewport', frame, interpolation='CONSTANT')
        root = self.sb.root_ob
        if frame is not None and ('uf_env_on', root.as_pointer()) not in self._vis_keyed:
            self._vis_keyed.add(('uf_env_on', root.as_pointer()))
            k.key(root, '["uf_env_on"]', frame - 1, interpolation='CONSTANT')
        root['uf_env_on'] = 1.0 if visible else 0.0
        if frame is not None:
            k.key(root, '["uf_env_on"]', frame, interpolation='CONSTANT')

    def show_part(self, part, visible=True, frame=None, ctx=None):
        """three's part.visible = false, which hides a whole subtree: a part (its name in parts, an object, or a
        list of them, e.g. 'backdrop' to replace the quiet room's city with the city set, 'beams'), hidden or shown
        with every object under it; keyed CONSTANT at `frame` when given (the first switch also keys the state
        before it on the frame before)."""
        obs = self['parts'][part] if isinstance(part, str) else part
        obs = list(obs) if isinstance(obs, (list, tuple)) else [obs]
        todo, seen = [], set()
        while obs:
            o = obs.pop()
            if o is None or o.as_pointer() in seen:
                continue
            seen.add(o.as_pointer())
            todo.append(o)
            obs.extend(o.children)
        if not hasattr(self, '_vis_keyed'):
            self._vis_keyed = set()
        k = self._keyer(ctx) if frame is not None else None
        for ob in todo:
            if frame is not None and ob.as_pointer() not in self._vis_keyed:
                self._vis_keyed.add(ob.as_pointer())
                k.key(ob, 'hide_render', frame - 1, interpolation='CONSTANT')
                k.key(ob, 'hide_viewport', frame - 1, interpolation='CONSTANT')
            ob.hide_render = not visible
            ob.hide_viewport = not visible
            if frame is not None:
                k.key(ob, 'hide_render', frame, interpolation='CONSTANT')
                k.key(ob, 'hide_viewport', frame, interpolation='CONSTANT')
        return todo

    def make_camera(self, name, clip_end=None):
        """A Blender camera at cams[name] (vertical fov as three's), parented to the set."""
        return make_camera(self.sb, name, self['cams'][name], clip_end=clip_end or self.CLIP_END)

    REFLECTIONS = 'env'

    def eevee_settings(self, scene=None, reflections=None):
        """The interior's EEVEE settings: global illumination on (fast GI over the set's baked room probe: bake it
        with bake_probes), shadows on, and the reflections:
          'env' (default): the engine's picture. The sets were made with SSR off, so every gloss and chrome there
                 reflected the set's own painted env: the showroom's softboxes, the altar glow in the quiet room's
                 glass. In EEVEE those are reflections from the light probes alone (the Light Probe tracing
                 method): the World (the set's env), the room's probe, and a set's sphere probes (the showroom's
                 toaster mirrors the plinth and the stage round it through its own).
          'traced': screen-traced reflections (max roughness 0.5): what is on screen reflects (the void in the
                 chrome, the LED wall in the polished stage), and the probes where the rays miss.
        Fast GI runs inside EEVEE's ray tracing, so the ray tracing is on in both."""
        sc = scene or self.sb.scene
        mode = reflections or self.REFLECTIONS
        if mode not in ('env', 'traced'):
            raise ValueError(f"eevee_settings: reflections={mode!r} (want 'env' or 'traced')")
        ee = sc.eevee
        ee.use_shadows = True
        ee.use_raytracing = True
        ee.ray_tracing_method = 'SCREEN' if mode == 'traced' else 'PROBE'
        ee.ray_tracing_options.trace_max_roughness = 0.5
        ee.use_fast_gi = True
        ee.fast_gi_method = 'GLOBAL_ILLUMINATION'
        return ee

    def bake_probes(self, scene=None):
        """Bake the set's volume probe (a GPU job: run it through heavy.sh). Returns {probe: seconds}. In a scene
        several sets share (env_switch), the bake sees this set alone, lit by its own env (the others hidden, their
        env weights 0, any keys on those switches muted for the bake), and the scene is left as it was."""
        from ...look import lighting as LL
        if self.get('probe') is None:
            return {}
        sc = scene or self.sb.scene
        others = [s for s in _live_sets(sc) if s is not self]
        if not others:
            return LL.bake_light_probes(sc, probes=[self['probe']])
        with _alone(self, [self] + others):
            return LL.bake_light_probes(sc, probes=[self['probe']])

    def dispose(self):
        if self._env_switch is not None:
            _env_switch_drop(self._env_switch, self)
        _LIVE_SETS[:] = [r for r in _LIVE_SETS if r() is not None and r() is not self]
        self.sb.dispose()


# ================================================================================================ environment
def equirect_env(W, H, paint, name='uf_env', vectorized=True, strength=1.0, root=None):
    """equirectEnv: an LDR equirect painted from a direction function, as the set's World: EEVEE lights the set with
    it (the room's volume probe bakes it, the probes reflect it) and the camera sees it past the set. paint(dx, dy, dz)
    gets THREE-space directions (+Y up) and returns (r, g, b) in 0..1 sRGB; vectorized=True passes numpy arrays (all
    the pixels at once). The image is laid out for Blender's equirect lookup (each pixel painted with the direction
    Blender's Environment Texture maps it to), so the World shows the same light in the same directions as the
    engine's envMap. root: the set's root object; the lookup turns with it (env_turn), so a set parked turned keeps
    its light where its env painted it. 8-bit sRGB, packed. Returns the World (its image: world['uf_env_image'])."""
    bpy = _bpy()
    u = (np.arange(W) + 0.5) / W
    v = (np.arange(H) + 0.5) / H
    U, Vv = np.meshgrid(u, v)                                # row 0 = v 0 (Blender's first row)
    phi = math.pi * (1 - 2 * U)
    th = math.pi * (1 - Vv)
    bx, by, bz = np.sin(th) * np.cos(phi), np.sin(th) * np.sin(phi), np.cos(th)
    dx, dy, dz = bx, bz, -by                                 # Blender (x, y, z) -> three (x, z, -y)
    if vectorized:
        r, g, b = paint(dx, dy, dz)
    else:
        r, g, b = np.zeros_like(dx), np.zeros_like(dx), np.zeros_like(dx)
        for i in np.ndindex(dx.shape):
            r[i], g[i], b[i] = paint(dx[i], dy[i], dz[i])
    rgba = np.empty((H, W, 4), np.uint8)
    for k, c in enumerate((r, g, b)):
        rgba[..., k] = np.floor(np.clip(np.broadcast_to(c, dx.shape), 0, 1) * 255 + 0.5).astype(np.uint8)
    rgba[..., 3] = 255
    img = data_texture(rgba, W, H, srgb=True, flip=False, repeat=True, name=name + '_equirect')
    w = bpy.data.worlds.new(name)
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    tx = nt.nodes.new('ShaderNodeTexEnvironment')
    tx.image = img
    tx.interpolation = 'Linear'
    tx.location = (-400, 0)
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Strength'].default_value = float(strength)
    out = nt.nodes.new('ShaderNodeOutputWorld')
    out.location = (250, 0)
    if root is not None:
        nt.links.new(env_turn(nt, root, (-700, 0)), tx.inputs['Vector'])
    nt.links.new(tx.outputs['Color'], bg.inputs['Color'])
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    w['uf_env_image'] = img.name
    if root is not None:
        w['uf_env_root'] = root.name
    return w


def env_turn(nt, root, location=(0, 0)):
    """In a World's node tree: the view direction turned back by `root`'s world rotation (three one-variable drivers
    on its Euler XYZ, no Python), for an Environment Texture's Vector: the environment turns with the set. Returns
    the output socket."""
    tc = nt.nodes.new('ShaderNodeTexCoord')
    tc.location = (location[0] - 400, location[1])
    rot = nt.nodes.new('ShaderNodeCombineXYZ')
    rot.label = 'set rotation'
    rot.location = (location[0] - 400, location[1] - 250)
    for i, ax in enumerate('XYZ'):
        drv = rot.inputs[i].driver_add('default_value').driver
        drv.type = 'AVERAGE'
        var = drv.variables.new()
        var.name = 'r'
        var.type = 'TRANSFORMS'
        tg = var.targets[0]
        tg.id = root
        tg.transform_type = f'ROT_{ax}'
        tg.transform_space = 'WORLD_SPACE'
        tg.rotation_mode = 'XYZ'
    vr = nt.nodes.new('ShaderNodeVectorRotate')
    vr.rotation_type = 'EULER_XYZ'
    vr.invert = True
    vr.location = location
    nt.links.new(tc.outputs['Generated'], vr.inputs['Vector'])
    nt.links.new(rot.outputs[0], vr.inputs['Rotation'])
    return vr.outputs['Vector']


def env_switch(scene, sets, name='uf_env_switch'):
    """Several interiors in one scene, each lit by its own env while it is on screen. Blender has one World per scene
    and scene.world cannot be keyed, so this World holds every set's env (each turning with its set, env_turn),
    each weighted by its root's 'uf_env_on' (a one-variable driver: no Python runs), and set.show(visible, frame)
    keys that weight with the set's cut. It becomes the scene's World; returns it. A set's bake_probes() bakes with
    that set alone in the scene, lit by its own env.

        room, show = QR.build(scene), SR.build(scene)
        show.root.location = (60, 0, 0)                                  # park the showroom beside the room
        L.env_switch(scene, [room, show])
        room.show(True, frame=1); show.show(False, frame=1)              # the room first ...
        room.show(False, frame=121); show.show(True, frame=121)          # ... the showroom from frame 121
        room.bake_probes(); show.bake_probes()
    """
    bpy = _bpy()
    sets = list(sets)
    for s in sets:
        if s._env_switch is not None:
            raise ValueError(f'env_switch: {s.sb.name} already shares a World ({s._env_switch["world"].name})')
    w = bpy.data.worlds.new(name)
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    out.location = (600, 0)
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.location = (400, 0)
    bg.inputs['Strength'].default_value = 1.0
    sw = {'world': w, 'sets': sets, 'nodes': {}}
    acc = None
    for i, s in enumerate(sets):
        env = s['env']
        src_bg = next((n for n in env.node_tree.nodes if n.bl_idname == 'ShaderNodeBackground'), None)
        strength = float(src_bg.inputs['Strength'].default_value) if src_bg is not None else 1.0
        tx = nt.nodes.new('ShaderNodeTexEnvironment')
        tx.image = bpy.data.images[env['uf_env_image']]
        tx.interpolation = 'Linear'
        tx.location = (-500, -280 * i)
        nt.links.new(env_turn(nt, s.root, (-800, -280 * i)), tx.inputs['Vector'])
        sc = nt.nodes.new('ShaderNodeVectorMath')
        sc.operation = 'SCALE'
        sc.location = (-200, -280 * i)
        nt.links.new(tx.outputs['Color'], sc.inputs[0])
        sock = next(x for x in sc.inputs if x.name == 'Scale')
        sock.default_value = float(s.root.get('uf_env_on', 1.0))
        d = sock.driver_add('default_value').driver
        d.type = 'AVERAGE'
        var = d.variables.new()
        var.name = 'on'
        var.type = 'SINGLE_PROP'
        var.targets[0].id_type = 'OBJECT'
        var.targets[0].id = s.root
        var.targets[0].data_path = '["uf_env_on"]'
        v = sc.outputs[0]
        if abs(strength - 1.0) > 1e-9:
            st = nt.nodes.new('ShaderNodeVectorMath')
            st.operation = 'SCALE'
            nt.links.new(v, st.inputs[0])
            next(x for x in st.inputs if x.name == 'Scale').default_value = strength
            v = st.outputs[0]
        if acc is None:
            acc = v
        else:
            add = nt.nodes.new('ShaderNodeVectorMath')
            add.operation = 'ADD'
            add.location = (100, -280 * i)
            nt.links.new(acc, add.inputs[0])
            nt.links.new(v, add.inputs[1])
            acc = add.outputs[0]
        sw['nodes'][id(s)] = (tx.name, sc.name)
        s._env_switch = sw
    if acc is not None:
        nt.links.new(acc, bg.inputs['Color'])
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    scene.world = w
    return w


def _env_switch_drop(sw, s):
    """A set leaves its shared World (its dispose): its branch goes dark and lets go of its env image; the World
    goes with the last set."""
    bpy = _bpy()
    s._env_switch = None
    sw['sets'] = [x for x in sw['sets'] if x is not s]
    try:
        w = sw['world']
        nt = w.node_tree
    except ReferenceError:
        return
    names = sw['nodes'].pop(id(s), None)
    if names:
        tx, sc = nt.nodes.get(names[0]), nt.nodes.get(names[1])
        if tx is not None:
            tx.image = None
        if sc is not None:
            sock = next(x for x in sc.inputs if x.name == 'Scale')
            sock.driver_remove('default_value')
            sock.default_value = 0.0
    if not sw['sets']:
        for sc_ in bpy.data.scenes:
            if sc_.world == w:
                sc_.world = None
        bpy.data.worlds.remove(w)


import weakref                             # noqa: E402  (here, below the art-hash marker: the canvas caches stay valid)
from contextlib import contextmanager      # noqa: E402

_LIVE_SETS = []                            # weak references to the sets built in this session


def _live_sets(scene):
    """The sets built in this session that stand in `scene` now (disposed or deleted ones are dropped)."""
    out, keep = [], []
    for ref in _LIVE_SETS:
        s = ref()
        if s is None:
            continue
        try:
            root = s.sb.root_ob
            alive = root.users > 0
            here = alive and scene.objects.get(root.name) == root
        except ReferenceError:
            alive = here = False
        if alive:
            keep.append(ref)
        if here:
            out.append(s)
    _LIVE_SETS[:] = keep
    return out


@contextmanager
def _alone(s, sets):
    """`s` shown and lit by its own env alone, the other sets hidden, for a bake; everything restored afterwards.
    The keys on these switches are muted meanwhile (a keyed value would win over the bake's on the next update)."""
    from bpy_extras import anim_utils
    paths = ('hide_render', 'hide_viewport', '["uf_env_on"]')
    saved, muted = [], []
    try:
        for x in sets:
            on = x is s
            for ob in x.sb.made['objects']:
                try:
                    if ob is None or ob.users == 0:
                        continue
                except ReferenceError:              # deleted since the build
                    continue
                ad = ob.animation_data
                if ad is not None and ad.action is not None:
                    cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
                    for fc in (cb.fcurves if cb is not None else ()):
                        if fc.data_path in paths and not fc.mute:
                            fc.mute = True
                            muted.append(fc)
                saved.append((ob, ob.hide_render, ob.hide_viewport, ob.get('uf_env_on')))
                ob.hide_render = ob.hide_viewport = not on
            x.root['uf_env_on'] = 1.0 if on else 0.0
        yield
    finally:
        for ob, hr, hv, env_on in saved:
            ob.hide_render, ob.hide_viewport = hr, hv
            if env_on is not None:
                ob['uf_env_on'] = env_on
        for fc in muted:
            fc.mute = False


# ================================================================================================ shader expressions
_MATH_PY = {
    'ADD': lambda a, b: a + b, 'SUBTRACT': lambda a, b: a - b, 'MULTIPLY': lambda a, b: a * b,
    'DIVIDE': lambda a, b: a / b if b != 0 else 0.0, 'MINIMUM': min, 'MAXIMUM': max,
    'POWER': lambda a, b: (a ** b) if a >= 0 or float(b).is_integer() else 0.0,
    'LESS_THAN': lambda a, b: 1.0 if a < b else 0.0, 'GREATER_THAN': lambda a, b: 1.0 if a > b else 0.0,
    'ARCTAN2': math.atan2, 'FLOORED_MODULO': lambda a, b: a - b * math.floor(a / b) if b != 0 else 0.0,
}
_UNARY_PY = {'ABSOLUTE': abs, 'FLOOR': math.floor, 'FRACT': lambda a: a - math.floor(a), 'SINE': math.sin,
             'COSINE': math.cos, 'EXPONENT': math.exp, 'SQRT': lambda a: math.sqrt(max(a, 0.0)),
             'NEGATE': lambda a: -a}
_VEC_OPS = {'ADD': 'ADD', 'SUBTRACT': 'SUBTRACT', 'MULTIPLY': 'MULTIPLY', 'DIVIDE': 'DIVIDE', 'MINIMUM': 'MINIMUM',
            'MAXIMUM': 'MAXIMUM'}
_VEC_UNARY = {'ABSOLUTE': 'ABSOLUTE', 'FLOOR': 'FLOOR', 'FRACT': 'FRACTION', 'SINE': 'SINE', 'COSINE': 'COSINE'}


def _is_sock(s):
    return hasattr(s, 'is_linked')


class V:
    """A shader value: a constant (float, or a 3-tuple) or a node socket, of kind 'f' (float) or 'v' (vector /
    colour). Arithmetic writes Math / Vector Math nodes (constants fold in Python); the TSL method names (add, mul,
    sub, div, clamp, pow, x / y / z ...) read as the engine's code did."""

    __slots__ = ('g', 's', 'k')

    def __init__(self, g, s, k):
        self.g, self.s, self.k = g, s, k

    @property
    def const(self):
        return not _is_sock(self.s)

    def __add__(self, o):
        return self.g.op('ADD', self, o)

    def __radd__(self, o):
        return self.g.op('ADD', o, self)

    def __sub__(self, o):
        return self.g.op('SUBTRACT', self, o)

    def __rsub__(self, o):
        return self.g.op('SUBTRACT', o, self)

    def __mul__(self, o):
        return self.g.op('MULTIPLY', self, o)

    def __rmul__(self, o):
        return self.g.op('MULTIPLY', o, self)

    def __truediv__(self, o):
        return self.g.op('DIVIDE', self, o)

    def __rtruediv__(self, o):
        return self.g.op('DIVIDE', o, self)

    def __neg__(self):
        return self.g.op('MULTIPLY', self, -1.0)

    add, sub, mul, div = __add__, __sub__, __mul__, __truediv__

    def negate(self):
        return -self

    def abs(self):
        return self.g.op1('ABSOLUTE', self)

    def floor(self):
        return self.g.op1('FLOOR', self)

    def fract(self):
        return self.g.op1('FRACT', self)

    def sin(self):
        return self.g.op1('SINE', self)

    def cos(self):
        return self.g.op1('COSINE', self)

    def exp(self):
        return self.g.op1('EXPONENT', self)

    def pow(self, e):
        return self.g.op('POWER', self, e)

    def min(self, o):
        return self.g.op('MINIMUM', self, o)

    def max(self, o):
        return self.g.op('MAXIMUM', self, o)

    def clamp(self, lo=0.0, hi=1.0):
        return self.g.clamp(self, lo, hi)

    def less_than(self, o):
        return self.g.op('LESS_THAN', self, o)

    def greater_than(self, o):
        return self.g.op('GREATER_THAN', self, o)

    def length(self):
        return self.g.vop_value('LENGTH', self)

    def normalize(self):
        return self.g.vop('NORMALIZE', self)

    def dot(self, o):
        return self.g.vop_value('DOT_PRODUCT', self, o)

    @property
    def x(self):
        return self.g.comp(self, 0)

    @property
    def y(self):
        return self.g.comp(self, 1)

    @property
    def z(self):
        return self.g.comp(self, 2)

    r, gg, b = x, y, z


class V4:
    """A vec4 (a texture sample's rgb + a, or a weighted sum of them): .x .y .z .w, mul / add like TSL's vec4."""

    __slots__ = ('rgb', 'a')

    def __init__(self, rgb, a):
        self.rgb, self.a = rgb, a

    def mul(self, k):
        return V4(self.rgb * k, self.a * k)

    def add(self, o):
        return V4(self.rgb + o.rgb, self.a + o.a)

    @property
    def x(self):
        return self.rgb.x

    @property
    def y(self):
        return self.rgb.y

    @property
    def z(self):
        return self.rgb.z

    @property
    def w(self):
        return self.a

    r, g, b = x, y, z


class TexSample(V4):
    """texture(img, uv): .rgb (the Color output), .a (Alpha), .r / .g / .b / .x / .y / .z / .w."""
    pass


class ShaderGraph:
    """Writes one material's node tree the way TSL wrote its graph. The material's output is set with
    standard(...) (MeshStandard / MeshPhysical -> Principled BSDF) or basic(...) (MeshBasic -> Emission, unlit).
    Sources: uv(), position_local() / normal_local() / position_world() (in THREE's axes, so the engine's math
    ports as written), view_dir(), view_distance(), facing(), attribute(name), uniform(name) (a driver on the set's
    root), texture(img, uv), hash(x)."""

    def __init__(self, mat, root_ob=None, scene=None):
        mat.use_nodes = True
        self.mat = mat
        self.nt = mat.node_tree
        self.nt.nodes.clear()
        self.root = root_ob
        self.scene = scene
        self._col = 0
        self._row = 0
        self._cache = {}
        self.out = self.nt.nodes.new('ShaderNodeOutputMaterial')
        self.out.location = (900, 0)

    # plumbing --------------------------------------------------------------------------------------------
    def node(self, idname, **props):
        n = self.nt.nodes.new(idname)
        for k, v in props.items():
            setattr(n, k, v)
        n.location = (-2600 + 230 * (self._row // 22), 700 - 180 * (self._row % 22))
        self._row += 1
        return n

    def w(self, x):
        if isinstance(x, V):
            return x
        if isinstance(x, (int, float)):
            return V(self, float(x), 'f')
        if isinstance(x, (tuple, list)):
            t = tuple(float(c) for c in x) + (0.0,) * (3 - len(x))
            return V(self, t[:3], 'v')
        if _is_sock(x):
            return V(self, x, 'f' if x.type in ('VALUE', 'INT', 'BOOLEAN') else 'v')
        raise TypeError(f'ShaderGraph: cannot use {x!r} as a value')

    def put(self, sock, val):
        """link a value into an input (a constant becomes the default; a float fills a vector input)."""
        v = self.w(val)
        if v.const:
            c = v.s
            if sock.type in ('VECTOR', 'RGBA'):
                n = len(sock.default_value)
                tup = (c,) * 3 if isinstance(c, float) else tuple(c)
                sock.default_value = (tup + (1.0,))[:n] if n == 4 else tup[:n]
            else:
                sock.default_value = c if isinstance(c, float) else sum(c) / 3.0
        else:
            self.nt.links.new(v.s, sock)

    def op(self, opname, a, b):
        a, b = self.w(a), self.w(b)
        if a.const and b.const:
            fa, fb = a.s, b.s
            f = _MATH_PY[opname]
            if isinstance(fa, float) and isinstance(fb, float):
                return V(self, float(f(fa, fb)), 'f')
            ta = fa if isinstance(fa, tuple) else (fa,) * 3
            tb = fb if isinstance(fb, tuple) else (fb,) * 3
            return V(self, tuple(float(f(x, y)) for x, y in zip(ta, tb)), 'v')
        if a.k == 'v' or b.k == 'v':
            vo = _VEC_OPS.get(opname)
            if vo is None:
                return self._per_comp(opname, a, b)
            n = self.node('ShaderNodeVectorMath', operation=vo)
            self.put(n.inputs[0], a)
            self.put(n.inputs[1], b)
            return V(self, n.outputs['Vector'], 'v')
        n = self.node('ShaderNodeMath', operation=opname)
        n.use_clamp = False
        self.put(n.inputs[0], a)
        self.put(n.inputs[1], b)
        return V(self, n.outputs[0], 'f')

    def _per_comp(self, opname, a, b):
        ca = [a.x, a.y, a.z] if a.k == 'v' else [a] * 3
        cb = [b.x, b.y, b.z] if b.k == 'v' else [b] * 3
        return self.vec3(*[self.op(opname, p, q) for p, q in zip(ca, cb)])

    def op1(self, opname, a):
        a = self.w(a)
        if a.const:
            f = _UNARY_PY[opname]
            if isinstance(a.s, float):
                return V(self, float(f(a.s)), 'f')
            return V(self, tuple(float(f(c)) for c in a.s), 'v')
        if opname == 'NEGATE':
            return a * -1.0
        if a.k == 'v':
            vo = _VEC_UNARY.get(opname)
            if vo is None:
                return self.vec3(self.op1(opname, a.x), self.op1(opname, a.y), self.op1(opname, a.z))
            n = self.node('ShaderNodeVectorMath', operation=vo)
            self.put(n.inputs[0], a)
            return V(self, n.outputs['Vector'], 'v')
        n = self.node('ShaderNodeMath', operation=opname)
        self.put(n.inputs[0], a)
        return V(self, n.outputs[0], 'f')

    def vop(self, opname, a, b=None):
        n = self.node('ShaderNodeVectorMath', operation=opname)
        self.put(n.inputs[0], a)
        if b is not None:
            self.put(n.inputs[1], b)
        return V(self, n.outputs['Vector'], 'v')

    def vop_value(self, opname, a, b=None):
        n = self.node('ShaderNodeVectorMath', operation=opname)
        self.put(n.inputs[0], a)
        if b is not None:
            self.put(n.inputs[1], b)
        return V(self, n.outputs['Value'], 'f')

    def comp(self, v, i):
        v = self.w(v)
        if v.const:
            c = v.s
            return V(self, c if isinstance(c, float) else c[i], 'f')
        if v.k == 'f':
            return v
        key = ('sep', v.s.as_pointer())
        n = self._cache.get(key)
        if n is None:
            n = self._cache[key] = self.node('ShaderNodeSeparateXYZ')
            self.nt.links.new(v.s, n.inputs[0])
        return V(self, n.outputs[i], 'f')

    # constructors ----------------------------------------------------------------------------------------
    def float(self, x):
        return self.w(x)

    def vec3(self, x, y=None, z=None):
        if y is None and z is None:
            v = self.w(x)
            if v.const:
                return V(self, (v.s,) * 3 if isinstance(v.s, float) else v.s, 'v')
            return V(self, v.s, 'v')                         # a float socket fills all three (Blender's conversion)
        parts = [self.w(c) for c in (x, y, z)]
        if all(p.const for p in parts):
            return V(self, tuple(p.s for p in parts), 'v')
        n = self.node('ShaderNodeCombineXYZ')
        for i, p in enumerate(parts):
            self.put(n.inputs[i], p)
        return V(self, n.outputs[0], 'v')

    def vec2(self, x, y):
        return self.vec3(x, y, 0.0)

    def mix(self, a, b, t):
        a, b, t = self.w(a), self.w(b), self.w(t)
        if a.const and b.const and t.const and isinstance(t.s, float):
            return a + (b - a) * t.s
        if a.k == 'f' and b.k == 'f' and t.k == 'f':
            n = self.node('ShaderNodeMix', data_type='FLOAT', clamp_factor=False)
            self.put(self._sock(n.inputs, 'Factor_Float'), t)
            self.put(self._sock(n.inputs, 'A_Float'), a)
            self.put(self._sock(n.inputs, 'B_Float'), b)
            return V(self, self._sock(n.outputs, 'Result_Float'), 'f')
        n = self.node('ShaderNodeMix', data_type='VECTOR', clamp_factor=False,
                      factor_mode='UNIFORM' if t.k == 'f' else 'NON_UNIFORM')
        self.put(self._sock(n.inputs, 'Factor_Float' if t.k == 'f' else 'Factor_Vector'), t)
        self.put(self._sock(n.inputs, 'A_Vector'), self.vec3(a) if a.k == 'f' else a)
        self.put(self._sock(n.inputs, 'B_Vector'), self.vec3(b) if b.k == 'f' else b)
        return V(self, self._sock(n.outputs, 'Result_Vector'), 'v')

    @staticmethod
    def _sock(coll, ident):
        for s in coll:
            if s.identifier == ident:
                return s
        raise KeyError(ident)

    def smoothstep(self, e0, e1, x):
        e0, e1, x = self.w(e0), self.w(e1), self.w(x)
        if e0.const and e1.const and x.const:
            t = clamp01((x.s - e0.s) / (e1.s - e0.s)) if e1.s != e0.s else (1.0 if x.s >= e0.s else 0.0)
            return V(self, t * t * (3 - 2 * t), 'f')
        if x.k == 'v':
            return self.vec3(self.smoothstep(e0, e1, x.x), self.smoothstep(e0, e1, x.y), self.smoothstep(e0, e1, x.z))
        n = self.node('ShaderNodeMapRange', data_type='FLOAT', interpolation_type='SMOOTHSTEP')
        self.put(n.inputs['Value'], x)
        self.put(n.inputs['From Min'], e0)
        self.put(n.inputs['From Max'], e1)
        n.inputs['To Min'].default_value = 0.0
        n.inputs['To Max'].default_value = 1.0
        return V(self, n.outputs['Result'], 'f')

    def step(self, edge, x):
        """step(edge, x) = x >= edge ? 1 : 0."""
        return 1.0 - self.op('LESS_THAN', x, edge)

    def clamp(self, x, lo=0.0, hi=1.0):
        x = self.w(x)
        if x.const and isinstance(x.s, float) and not isinstance(lo, V) and not isinstance(hi, V):
            return V(self, max(lo, min(hi, x.s)), 'f')
        if x.k == 'v':
            return self.op('MINIMUM', self.op('MAXIMUM', x, lo), hi)
        n = self.node('ShaderNodeClamp', clamp_type='MINMAX')
        self.put(n.inputs['Value'], x)
        self.put(n.inputs['Min'], lo)
        self.put(n.inputs['Max'], hi)
        return V(self, n.outputs[0], 'f')

    def select(self, cond, a, b):
        """select(cond, a, b): a where cond is 1, b where it is 0."""
        return self.mix(b, a, cond)

    def atan2(self, y, x):
        return self.op('ARCTAN2', y, x)

    def mod(self, a, b):
        return self.op('FLOORED_MODULO', a, b)

    def pow(self, a, e):
        return self.op('POWER', a, e)

    def max(self, a, b):
        return self.op('MAXIMUM', a, b)

    def min(self, a, b):
        return self.op('MINIMUM', a, b)

    def abs(self, a):
        return self.op1('ABSOLUTE', a)

    def exp(self, a):
        return self.op1('EXPONENT', a)

    def fract(self, a):
        return self.op1('FRACT', a)

    def floor(self, a):
        return self.op1('FLOOR', a)

    def sin(self, a):
        return self.op1('SINE', a)

    def cos(self, a):
        return self.op1('COSINE', a)

    def length(self, v):
        return self.w(v).length()

    def normalize(self, v):
        return self.w(v).normalize()

    def dot(self, a, b):
        return self.vop_value('DOT_PRODUCT', a, b)

    def hash(self, x):
        """TSL hash(x) -> a deterministic value in [0, 1): Blender's White Noise (a different hash function than
        three's PCG, the same uniform distribution; integer bit operations do not exist in shader nodes)."""
        x = self.w(x)
        n = self.node('ShaderNodeTexWhiteNoise', noise_dimensions='1D')
        self.put(n.inputs['W'], x)
        return V(self, n.outputs['Value'], 'f')

    # sources ---------------------------------------------------------------------------------------------
    def _cached(self, key, make):
        v = self._cache.get(key)
        if v is None:
            v = self._cache[key] = make()
        return v

    def _texcoord(self):
        return self._cached('texcoord', lambda: self.node('ShaderNodeTexCoord'))

    def _geometry(self):
        return self._cached('geometry', lambda: self.node('ShaderNodeNewGeometry'))

    def _three(self, sock):
        """a Blender-axes vector socket in three's axes: (x, y, z) -> (x, z, -y)."""
        v = V(self, sock, 'v')
        return self.vec3(v.x, v.z, -v.y)

    def uv(self):
        return self._cached('uv', lambda: V(self, self.node('ShaderNodeUVMap', uv_map='UVMap').outputs['UV'], 'v'))

    def position_local(self):
        return self._cached('plocal', lambda: self._three(self._texcoord().outputs['Object']))

    def normal_local(self):
        return self._cached('nlocal', lambda: self._three(self._texcoord().outputs['Normal']))

    def position_world(self):
        return self._cached('pworld', lambda: self._three(self._geometry().outputs['Position']))

    def view_dir(self):
        """normalize(positionWorld - cameraPosition), three's axes: the way from the eye to the point (-Incoming)."""
        return self._cached('vdir', lambda: -self._three(self._geometry().outputs['Incoming']))

    def view_distance(self):
        """length(positionWorld - cameraPosition)."""
        return self._cached('vdist', lambda: V(self, self.node('ShaderNodeCameraData').outputs['View Distance'], 'f'))

    def facing(self):
        """abs(dot(normalView, positionViewDirection)): how squarely the surface faces the eye."""
        g = self._geometry()
        return self._cached('facing', lambda: self.dot(V(self, g.outputs['Normal'], 'v'),
                                                       V(self, g.outputs['Incoming'], 'v')).abs())

    def attribute(self, name, kind='f'):
        n = self.node('ShaderNodeAttribute', attribute_type='GEOMETRY', attribute_name=name)
        return V(self, n.outputs['Fac'] if kind == 'f' else n.outputs['Vector'], kind)

    def uniform(self, name):
        """A uniform of the set: a Value node driven by the root Empty's custom property `name` (one variable, no
        Python), so a keyed property animates every material that reads it."""
        def make():
            n = self.node('ShaderNodeValue', label=name)
            n.outputs[0].default_value = float(self.root.get(name, 0.0)) if self.root is not None else 0.0
            if self.root is not None:
                fc = n.outputs[0].driver_add('default_value')
                d = fc.driver
                d.type = 'AVERAGE'
                var = d.variables.new()
                var.name = 'u'
                var.type = 'SINGLE_PROP'
                var.targets[0].id_type = 'OBJECT'
                var.targets[0].id = self.root
                var.targets[0].data_path = f'["{name}"]'
            return V(self, n.outputs[0], 'f')
        return self._cached(('uniform', name), make)

    def pixel_angle(self):
        """The angle one screen pixel subtends at the shot's camera (radians): the set's uniform uPixelAngle, which
        the set's update() computes from the camera (camera_pixel_angle) and keys. (Not a driver on scene.camera:
        a driver evaluated once while the scene has no camera is switched off by Blender for good, measured.)"""
        return self.uniform('uPixelAngle')

    def texture(self, img, uv=None, extension=None, interpolation='Linear'):
        """texture(img, uv) -> TexSample. The wrap is the image's (uf_repeat: REPEAT, else three's ClampToEdge,
        EXTEND) unless `extension` says otherwise."""
        uv = self.uv() if uv is None else self.w(uv)
        key = ('tex', img.name, None if uv.const else uv.s.as_pointer(), uv.s if uv.const else None, extension)
        def make():
            n = self.node('ShaderNodeTexImage')
            n.image = img
            n.interpolation = interpolation
            n.extension = extension or ('REPEAT' if img.get('uf_repeat', False) else 'EXTEND')
            self.put(n.inputs['Vector'], uv)
            return TexSample(V(self, n.outputs['Color'], 'v'), V(self, n.outputs['Alpha'], 'f'))
        return self._cached(key, make)

    def normal_map(self, tex_rgb, scale=(1.0, 1.0)):
        """normalMap(texture, vec2(s, s)): the tangent-space normal with x, y scaled before it is normalised (three's
        normalScale), into a Normal Map node (tangent space, UVMap)."""
        c = self.w(tex_rgb)
        sx, sy = (scale, scale) if isinstance(scale, (int, float)) else scale
        if abs(sx - 1) > 1e-9 or abs(sy - 1) > 1e-9:
            c = (c - 0.5) * (float(sx), float(sy), 1.0) + 0.5
        n = self.node('ShaderNodeNormalMap', space='TANGENT', uv_map='UVMap')
        n.inputs['Strength'].default_value = 1.0
        self.put(n.inputs['Color'], c)
        return V(self, n.outputs['Normal'], 'v')

    # outputs ---------------------------------------------------------------------------------------------
    def standard(self, color=None, roughness=None, metalness=None, normal=None, emissive=None, opacity=None,
                 coat=None, coat_roughness=None, sheen=None, sheen_tint=None, sheen_roughness=None, blend=None):
        """MeshStandard / MeshPhysical -> a Principled BSDF (three's defaults: roughness 1, metalness 0, F0 0.04)."""
        b = self.node('ShaderNodeBsdfPrincipled')
        b.location = (500, 0)
        for key, val in (('Base Color', color), ('Roughness', 1.0 if roughness is None else roughness),
                         ('Metallic', 0.0 if metalness is None else metalness), ('Normal', normal),
                         ('Emission Color', emissive), ('Alpha', opacity), ('Coat Weight', coat),
                         ('Coat Roughness', coat_roughness), ('Sheen Weight', sheen), ('Sheen Tint', sheen_tint),
                         ('Sheen Roughness', sheen_roughness)):
            if val is not None:
                self.put(b.inputs[key], val)
        if emissive is not None:
            b.inputs['Emission Strength'].default_value = 1.0
        self.nt.links.new(b.outputs[0], self.out.inputs['Surface'])
        if blend:
            self.mat.surface_render_method = blend
        return b

    def basic(self, color, opacity=None, additive=False):
        """MeshBasic -> unlit: an Emission of the colour (strength 1). opacity mixes with a Transparent BSDF, additive
        adds the emission over what is behind (BLENDED)."""
        e = self.node('ShaderNodeEmission')
        e.inputs['Strength'].default_value = 1.0
        self.put(e.inputs['Color'], color)
        sh = e.outputs[0]
        if additive:
            t = self.node('ShaderNodeBsdfTransparent')
            a = self.node('ShaderNodeAddShader')
            self.nt.links.new(e.outputs[0], a.inputs[0])
            self.nt.links.new(t.outputs[0], a.inputs[1])
            sh = a.outputs[0]
            self.mat.surface_render_method = 'BLENDED'
        elif opacity is not None:
            t = self.node('ShaderNodeBsdfTransparent')
            m = self.node('ShaderNodeMixShader')
            self.put(m.inputs['Fac'], opacity)
            self.nt.links.new(t.outputs[0], m.inputs[1])
            self.nt.links.new(e.outputs[0], m.inputs[2])
            sh = m.outputs[0]
            self.mat.surface_render_method = 'BLENDED'
        self.nt.links.new(sh, self.out.inputs['Surface'])
        self.mat['uf_unlit'] = True
        return e


# ================================================================================================ the material kit
class MaterialKit:
    """materialKit: the recipe both interiors use. Every material is its own Blender material named
    '<prefix>-<name>' (keyed), lit by the set's env through the World (equirect_env) as everything in the scene is,
    and gets triplanar breakup of value and roughness from the shared noise (tri), never a flat colour.

        K = L.MaterialKit(sb, prefix='ufsr')
        steel = K.pbr('steel', L.acg('Metal027'), tint=(0.55, 0.56, 0.6), tile=1 / 0.8, rough=0.9, metal=1)
        black = K.solid('black', (0.012, 0.012, 0.014), rough=0.8, vary=0.3, scale=1.5)
        m, g = K.new('custom'); n = K.tri(g, 3.0); g.standard(color=g.vec3(0.8) * (n.z * 0.1 + 0.95))
    """

    def __init__(self, sb, prefix='uf', track=None):
        self.sb, self.prefix = sb, prefix
        self.NOISE = noise_texture()
        self._track = track
        self.n = 0

    def new(self, name):
        """(material, ShaderGraph) for a custom recipe."""
        bpy = _bpy()
        m = bpy.data.materials.new(f'{self.prefix}-{name}')
        self.keyed(m, name)
        return m, ShaderGraph(m, self.sb.root_ob, self.sb.scene)

    def tri(self, g, scale):
        """object-space triplanar noise (vec4: four independent fBm channels), positionLocal * scale, weighted by
        abs(normalLocal) / (|nx| + |ny| + |nz|)."""
        p = g.position_local() * float(scale)
        n = g.normal_local().abs()
        w = n / g.max(n.x + n.y + n.z, 1e-4)
        tx = g.texture(self.NOISE, g.vec2(p.y, p.z))
        ty = g.texture(self.NOISE, g.vec2(p.x, p.z))
        tz = g.texture(self.NOISE, g.vec2(p.x, p.y))
        return tx.mul(w.x).add(ty.mul(w.y)).add(tz.mul(w.z))

    def keyed(self, m, name):
        m.name = f'{self.prefix}-{name}'
        self.n += 1
        self.sb.track(m)
        if self._track:
            self._track(m)
        return m

    @staticmethod
    def _extra(extra):
        out = {}
        for k, v in (extra or {}).items():
            k2 = {'clearcoat': 'coat', 'clearcoatRoughness': 'coat_roughness', 'clearcoat_roughness': 'coat_roughness',
                  'sheen': 'sheen', 'sheenRoughness': 'sheen_roughness', 'sheen_roughness': 'sheen_roughness',
                  'sheenColor': 'sheen_tint', 'sheen_color': 'sheen_tint'}.get(k)
            if k2 is None:
                raise KeyError(f'material extra {k!r}: the interiors use clearcoat, clearcoatRoughness, sheen, '
                               'sheenRoughness, sheenColor')
            out[k2] = v
        return out

    def pbr(self, name, set, tint=(1, 1, 1), tile=1.0, rough=1.0, rough_add=0.0, metal=0.0, n_scale=1.0, vary=0.18,
            vary_scale=0.6, physical=False, extra=None, instance_color=False):
        """a PBR set tiled in metres (box_uv geometry) with tint, triplanar breakup of value and roughness.
        instance_color multiplies the per-instance colour in (three does it for any InstancedMesh with colours)."""
        m, g = self.new(name)
        tuv = g.uv() * float(tile)
        n = self.tri(g, vary_scale)
        base = g.texture(set['map'], tuv).rgb if 'map' in set else g.vec3(1.0)
        col = base * tuple(float(c) for c in tint) * ((n.z - 0.5) * (vary * 2) + 1)
        if instance_color:
            col = col * g.attribute('instance_color', 'v')
        r0 = g.texture(set['roughnessMap'], tuv).r if 'roughnessMap' in set else g.float(0.6)
        rgh = g.clamp(r0 * float(rough) + float(rough_add) + (n.y - 0.5) * 0.16, 0.03, 1.0)
        nrm = g.normal_map(g.texture(set['normalMap'], tuv).rgb, n_scale) if 'normalMap' in set else None
        # a set with a metalness map: metalnessNode = its red channel x metal (the AmbientCG sets here have none)
        met = g.texture(set['metalnessMap'], tuv).r * float(metal) if 'metalnessMap' in set else float(metal)
        g.standard(color=col, roughness=rgh, metalness=met, normal=nrm, **self._extra(extra))
        return m

    def solid(self, name, col, rough=0.5, rough_var=0.25, metal=0.0, vary=0.2, scale=2.0, physical=False,
              extra=None, instance_color=False):
        """a 'solid' (no set): value + roughness breakup from the triplanar noise; never one flat colour."""
        m, g = self.new(name)
        n = self.tri(g, scale)
        n2 = self.tri(g, scale * 7.3)
        c = g.vec3(*[float(v) for v in col]) * ((n.z - 0.5) * (vary * 2) + 1) * ((n2.x - 0.5) * vary + 1)
        if instance_color:
            c = c * g.attribute('instance_color', 'v')
        r = g.clamp(float(rough) + (n.w - 0.5) * (rough_var * 2) + (n2.y - 0.5) * rough_var, 0.03, 1.0)
        g.standard(color=c, roughness=r, metalness=float(metal), **self._extra(extra))
        return m


def material_kit(sb, prefix='uf', track=None):
    """interiors_lib.js's materialKit(THREE, {env, prefix, track}) -> the kit (tri, keyed, pbr, solid); the env
    lights the materials through the World (equirect_env), so the kit takes none."""
    return MaterialKit(sb, prefix=prefix, track=track)


def hide_from_probes(mat, volume=True, sphere=False):
    """Mark a material's objects as left out of the volume-probe bake (emitters whose light the set's real lights
    already give, and anything animated: a probe is baked once) and, optionally, out of sphere-probe captures."""
    mat['uf_hide_probe_volume'] = bool(volume)
    mat['uf_hide_probe_sphere'] = bool(sphere)
    return mat

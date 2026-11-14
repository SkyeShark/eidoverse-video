"""The surface data's atlases (SURFACING_DESIGN.md 2.2, 2.6, 2.7): one tall image per family holding every level,
each level a square tile of its maps with a gutter of real terrain data around it, so Linear filtering and the mips
at a tile's edge read the ground there. No bpy at import; image() and save_image() need Blender.

    from eidoblend.terrain.surface import atlas as AT
    lay = AT.layout(levels, [n_texels per level])      # Layout: .width, .height, .tiles (one Tile per level)
    t = lay.tiles[i]                                    # t.x, t.y (the tile's corner, texels), t.n, t.gutter, t.texel
    t.rect(lay)                                         # (u0, v0, du, dv): the level's window in the atlas' UV
    arr = AT.assemble(lay, tiles_rgba)                  # (H, W, 4) float32 from each level's (n + 2g)^2 tile
    img = AT.image(name, arr, family)                   # a Blender image, made as the probes require

Tiles. A level of n texels per side (texel = side / n) gets a tile of n + 2 g texels, g = 32 up to 1024 texels and
64 above. The data sits in the middle; the gutter holds the coarser levels' maps at the gutter texels' own world
positions (the outermost level is edge-extended), filled by the caller (surface/__init__.py), so a read at the
window's edge, or a mip that averages across it, sees real terrain data. Tiles are packed on shelves, largest first:
the atlas is as wide as the largest tile (two context tiles share a shelf beside a main or hero tile's width).

UV. Blender's image rows run bottom to top, as the arrays' rows run south to north, so a level's texel (i, j) is
atlas pixel (t.x + g + i, t.y + g + j), and world (x, y) inside the window reads
    u = u0 + du (x - x0) / side,   v = v0 + dv (y - y0) / side,
    u0 = (t.x + g) / W, v0 = (t.y + g) / H, du = n / W, dv = n / H;
a texel centre lands on a pixel centre exactly.

Images (probes A2, A3 of the design): the colour space, the precision (use_half_precision: the 16F families are half
on the GPU, as their encodings assume) and the alpha mode ('CHANNEL_PACKED': four independent data channels) are set
before the pixels and never after; the images are not packed (a packed float image read 1.0 on the GPU in probe A3).
save_image() writes OpenEXR (half) for the float families and 8-bit PNG for the others and switches the image to the
file, which a .blend that renders elsewhere then references.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass

import numpy as np

F32 = np.float32


def gutter_for(n_texels):
    """The gutter of a tile of n texels per side: 32 up to 1024, 64 above."""
    return 32 if int(n_texels) <= 1024 else 64


@dataclass
class Tile:
    level: int
    n: int                      # data texels per side
    gutter: int
    texel: float                # metres per texel
    x0: float                   # the level's window, world metres (south-west corner) and side
    y0: float
    side: float
    x: int = 0                  # the tile's lower-left pixel in the atlas (gutter included)
    y: int = 0

    @property
    def size(self):
        return self.n + 2 * self.gutter

    def rect(self, lay):
        """(u0, v0, du, dv): the data region of the tile in the atlas' UV (0..1)."""
        W, H = float(lay.width), float(lay.height)
        return ((self.x + self.gutter) / W, (self.y + self.gutter) / H, self.n / W, self.n / H)

    def pixels(self):
        """(x0, y0, x1, y1): the tile's pixel box in the atlas, gutter included, end exclusive."""
        return self.x, self.y, self.x + self.size, self.y + self.size

    def centres(self):
        """World x (columns) and y (rows) of every texel centre of the tile, gutter included: float64 (size,)."""
        k = np.arange(-self.gutter, self.n + self.gutter) + 0.5
        return self.x0 + k * self.texel, self.y0 + k * self.texel

    def to_dict(self, lay):
        u0, v0, du, dv = self.rect(lay)
        return dict(level=self.level, x=self.x, y=self.y, size=self.size, n=self.n, gutter=self.gutter,
                    texel=self.texel, x0=self.x0, y0=self.y0, side=self.side, u0=u0, v0=v0, du=du, dv=dv)


@dataclass
class Layout:
    grid: str                   # 'detail' (D, E) or 'cell' (M, F, C, P)
    width: int
    height: int
    tiles: list                 # one Tile per level, by level index

    def to_dict(self):
        return dict(grid=self.grid, width=self.width, height=self.height,
                    tiles=[t.to_dict(self) for t in self.tiles])

    def __repr__(self):
        return (f'Layout({self.grid}, {self.width} x {self.height}, '
                + ', '.join(f'L{t.level} {t.n}+2x{t.gutter} @ ({t.x}, {t.y})' for t in self.tiles) + ')')


def layout(levels, n_texels, grid='cell'):
    """Pack one tile per level (n_texels[i] data texels per side) on shelves, largest first, into an atlas as wide
    as the largest tile. Deterministic: ties keep the level order."""
    tiles = []
    for lv, n in zip(levels, n_texels):
        n = int(n)
        tiles.append(Tile(int(lv.index), n, gutter_for(n), float(lv.side) / n, float(lv.x0), float(lv.y0),
                          float(lv.side)))
    order = sorted(range(len(tiles)), key=lambda k: (-tiles[k].size, k))
    W = max(t.size for t in tiles)
    y = 0
    shelf_h = 0
    x = 0
    for k in order:
        t = tiles[k]
        if shelf_h and (x + t.size <= W) and t.size <= shelf_h:
            t.x, t.y = x, y
            x += t.size
            continue
        y += shelf_h
        shelf_h = t.size
        t.x, t.y = 0, y
        x = t.size
    H = y + shelf_h
    if H > 32768 or W > 32768:
        raise ValueError(f'a {grid} atlas of {W} x {H} texels passes the GPU limit of 32768: fewer or smaller levels')
    return Layout(grid, int(W), int(H), tiles)


def _up2_axis(a, axis):
    """x2 bilinear along one axis, cell-centred, edges clamped (core/grid.py's 'bilinear' in float32)."""
    a = np.moveaxis(a, axis, 0)
    p = np.concatenate([a[:1], a, a[-1:]], 0)
    out = np.empty((2 * a.shape[0],) + a.shape[1:], F32)
    out[0::2] = F32(0.25) * p[:-2] + F32(0.75) * p[1:-1]
    out[1::2] = F32(0.75) * p[1:-1] + F32(0.25) * p[2:]
    return np.moveaxis(out, 0, axis)


def resample(a, n):
    """A level's map (m, m[, C]) on a grid of n texels over the same window: itself (m = n), x2 bilinear (n = 2m;
    core/grid.py's upsample2 'bilinear', texels nesting 2 x 2 in a cell), or a 2 x 2 box average (n = m / 2)."""
    a = np.asarray(a, F32)
    m = a.shape[0]
    if m == n:
        return a
    if n == 2 * m:
        return np.ascontiguousarray(_up2_axis(_up2_axis(a, 0), 1))
    if m == 2 * n:
        if a.ndim == 2:
            return a.reshape(n, 2, n, 2).mean(axis=(1, 3)).astype(F32)
        return a.reshape(n, 2, n, 2, a.shape[2]).mean(axis=(1, 3)).astype(F32)
    raise ValueError(f'a map of {m} texels cannot be put on a grid of {n} (only x2, /2 or equal)')


def sample_bilinear(a, x0, y0, texel, x, y):
    """Bilinear values of a texel-centred grid (m, m[, C]) at world points, clamped to its outermost centres."""
    a = np.asarray(a)
    h, w = a.shape[:2]
    fi = np.clip((np.asarray(x, np.float64) - x0) / texel - 0.5, 0.0, w - 1.0)
    fj = np.clip((np.asarray(y, np.float64) - y0) / texel - 0.5, 0.0, h - 1.0)
    i0 = np.minimum(np.floor(fi).astype(np.int64), max(w - 2, 0))
    j0 = np.minimum(np.floor(fj).astype(np.int64), max(h - 2, 0))
    ti, tj = (fi - i0).astype(F32), (fj - j0).astype(F32)
    i1, j1 = np.minimum(i0 + 1, w - 1), np.minimum(j0 + 1, h - 1)
    if a.ndim == 3:
        ti, tj = ti[..., None], tj[..., None]
    return ((a[j0, i0] * (1 - ti) + a[j0, i1] * ti) * (1 - tj) + (a[j1, i0] * (1 - ti) + a[j1, i1] * ti) * tj)


def sample_lattice(a, x0, y0, texel, xs, ys):
    """Bilinear values of a texel-centred grid (m, m) on the lattice of world points xs (columns) x ys (rows),
    clamped to its outermost centres: (len(ys), len(xs)) float32, separable (two 1D interpolations)."""
    a = np.asarray(a, F32)
    my, mx = a.shape[:2]

    def taps(v, o, m):
        f = np.clip((np.asarray(v, np.float64) - o) / texel - 0.5, 0.0, m - 1.0)
        i0 = np.minimum(np.floor(f).astype(np.int64), max(m - 2, 0))
        return i0, np.minimum(i0 + 1, m - 1), (f - i0).astype(F32)
    i0, i1, ti = taps(xs, x0, mx)
    j0, j1, tj = taps(ys, y0, my)
    r0, r1 = a[j0], a[j1]
    top = r0[:, i0] * (1 - ti) + r0[:, i1] * ti
    bot = r1[:, i0] * (1 - ti) + r1[:, i1] * ti
    return (top * (1 - tj)[:, None] + bot * tj[:, None]).astype(F32)


def gather_plan(m, x0, y0, texel, x, y):
    """The bilinear taps of world points on a texel-centred (m, m) grid, clamped to its outermost centres: the flat
    indices of the four corners and their weights, which gather() applies to any map on that grid."""
    fi = np.clip((np.asarray(x, np.float64) - x0) / texel - 0.5, 0.0, m - 1.0)
    fj = np.clip((np.asarray(y, np.float64) - y0) / texel - 0.5, 0.0, m - 1.0)
    i0 = np.minimum(np.floor(fi).astype(np.int64), max(m - 2, 0))
    j0 = np.minimum(np.floor(fj).astype(np.int64), max(m - 2, 0))
    ti, tj = (fi - i0).astype(F32), (fj - j0).astype(F32)
    i1, j1 = np.minimum(i0 + 1, m - 1), np.minimum(j0 + 1, m - 1)
    idx = (j0 * m + i0, j0 * m + i1, j1 * m + i0, j1 * m + i1)
    w = ((1 - ti) * (1 - tj), ti * (1 - tj), (1 - ti) * tj, ti * tj)
    return idx, w


def gather(a, plan):
    """A 2D map (m, m) at the points of a gather_plan."""
    idx, w = plan
    f = np.asarray(a, F32).reshape(-1)
    return f[idx[0]] * w[0] + f[idx[1]] * w[1] + f[idx[2]] * w[2] + f[idx[3]] * w[3]


def ring_mask(tile):
    """(size, size) bool: True on the tile's gutter texels."""
    s, g = tile.size, tile.gutter
    m = np.ones((s, s), bool)
    m[g:g + tile.n, g:g + tile.n] = False
    return m


def assemble(lay, tiles_rgba):
    """The atlas array (H, W, 4) float32 from each level's full tile array ((size, size, 4): data and gutter)."""
    out = np.zeros((lay.height, lay.width, 4), F32)
    for t, a in zip(lay.tiles, tiles_rgba):
        if a is None:
            continue
        a = np.asarray(a, F32)
        if a.shape[:2] != (t.size, t.size):
            raise ValueError(f'level {t.level}: a tile of {a.shape[:2]}, the layout holds {t.size} x {t.size}')
        x0, y0, x1, y1 = t.pixels()
        out[y0:y1, x0:x1, :a.shape[2]] = a
    return out


def megabytes(lay, family_format):
    """The GPU memory of an atlas in MB, mips included (a third more): RGBA8 4 bytes a texel, RGBA16F 8."""
    bpt = 8 if family_format == 'RGBA16F' else 4
    return lay.width * lay.height * bpt * (4.0 / 3.0) / 1e6


# ------------------------------------------------------------------------------------------------ images ---

def image(name, arr, fmt, colorspace, replace=True):
    """A Blender image holding the atlas array (H, W, 4) (values as the image stores them: 0..1 for the 8-bit
    families, sRGB-encoded for the sRGB ones). fmt 'RGBA16F' makes a half-float image, 'RGBA8' a byte image. The
    colour space, the precision and the alpha mode are set before the pixels; the image is not packed."""
    import bpy
    arr = np.ascontiguousarray(arr, F32)
    H, W = arr.shape[:2]
    old = bpy.data.images.get(name)
    if old is not None and replace:
        bpy.data.images.remove(old)
    is_float = fmt == 'RGBA16F'
    img = bpy.data.images.new(name, W, H, alpha=True, float_buffer=is_float)
    img.colorspace_settings.name = colorspace
    if is_float:
        img.use_half_precision = True
    img.alpha_mode = 'CHANNEL_PACKED'
    img.pixels.foreach_set(arr.ravel())
    img.update()
    img['eido_surface'] = True
    return img


def write_image(path, arr, fmt):
    """Write an atlas array (H, W, 4; row 0 the bottom, as Blender's pixels) to `path` with OpenImageIO (Blender's
    bundled module): fmt 'RGBA16F' as a half-float OpenEXR (ZIP), else an 8-bit PNG (values 0..1, rounded). Written
    to a temporary name and renamed into place, so a reader never sees half a file."""
    import OpenImageIO as oiio
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    a = np.asarray(arr)[::-1]                             # files run top to bottom
    H, W, C = a.shape
    if fmt == 'RGBA16F':
        spec = oiio.ImageSpec(W, H, C, 'half')
        spec.attribute('compression', 'zip')
        data = np.ascontiguousarray(a, np.float16)
    else:
        spec = oiio.ImageSpec(W, H, C, 'uint8')
        # four independent channels: the PNG writer must not divide the first three by the fourth (it does when it
        # takes the data for associated alpha, OpenImageIO's default)
        spec.attribute('oiio:UnassociatedAlpha', 1)
        # zlib's fastest level: the files are a cache rewritten with every bake (at the default level 6, E's 120 MB
        # of texels took 25 s to write)
        spec.attribute('png:compressionLevel', 1)
        data = np.ascontiguousarray(np.clip(np.rint(np.asarray(a, F32) * F32(255.0)), 0, 255), np.uint8)
    root, ext = os.path.splitext(path)
    tmp = f'{root}.{os.getpid()}.tmp{ext}'
    out = oiio.ImageOutput.create(tmp)
    if out is None:
        raise RuntimeError(f'OpenImageIO cannot write {tmp}: {oiio.geterror()}')
    if not (out.open(tmp, spec) and out.write_image(data)):
        err = out.geterror()
        out.close()
        raise RuntimeError(f'OpenImageIO could not write {tmp}: {err}')
    out.close()
    os.replace(tmp, path)
    return path


def load_image(path, name, fmt, colorspace, replace=True):
    """A Blender image reading an atlas file: the colour space, the precision (half for the 16F families) and the
    alpha mode ('CHANNEL_PACKED': four independent data channels) set at once, before anything reads its pixels."""
    import bpy
    old = bpy.data.images.get(name)
    if old is not None and replace:
        bpy.data.images.remove(old)
    img = bpy.data.images.load(path, check_existing=False)
    img.name = name
    img.colorspace_settings.name = colorspace
    if fmt == 'RGBA16F':
        img.use_half_precision = True
    img.alpha_mode = 'CHANNEL_PACKED'
    img['eido_surface'] = True
    return img


def texel_count(level, factor, cap):
    """Texels per side a level's tile holds: its cells times `factor`, at most `cap` (halved while over it)."""
    n = int(level.n) * int(factor)
    while n > cap:
        if n % 2:
            raise ValueError(f'level {level.index}: {n} texels cannot be halved to fit {cap}')
        n //= 2
    return n


__all__ = ['Tile', 'Layout', 'layout', 'assemble', 'resample', 'sample_bilinear', 'sample_lattice', 'gather_plan',
           'gather', 'ring_mask', 'gutter_for', 'image', 'write_image', 'load_image', 'megabytes', 'texel_count']

_ = math

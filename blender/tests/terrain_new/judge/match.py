"""Matching a generated field to a reference before anything is measured (DESIGN.md section 10 item 1: slope depends
on pixel size, so numbers are only compared at matched pixels). Numpy only.

    m = match(h, cell, ref, water=None, sea_level=None)
    m.gen, m.ref          the two surfaces on one grid (row 0 = south, metres), m.pixel, m.extent
    m.gen_water, m.ref_water   boolean lake masks on that grid (or None)
    m.notes               what was done (crops, coarsening, the radar chain), for the sheet and the report

The steps:
  1. The generated surface is h + water (a lake counts as its flat surface, as a DEM carries it) and, with a sea
     level, every cell at or under sea level + 0.3 m sits at sea level - 2 m (the references' sea rule).
  2. Extents: generate at the reference's extent. When they differ by more than 1 %, both are cropped about their
     centres to the smaller extent, and a note says so (relief and the spectrum depend on extent).
  3. Pixels: the generated field is box-averaged to the reference's pixel (core/grid.resample_box, exact area
     weights). The fetch's own chain (a Gaussian of 0.45 x the ratio, then bilinear) gives slopes within 0.1-1.2
     degrees of that on the four 3DEP mosaics measured (the p99 of the San Gabriels the most), far inside the bands.
     When the generated cell is coarser than the reference's pixel, the reference is box-averaged to the generated
     cell instead and the note says the numbers are at that coarser pixel.
  4. A reference whose source is coarser than its stored pixel (the 30 m radar DSMs; refs.NATIVE) gets its generated
     field through the same chain: box-averaged to the native resolution, upsampled (Catmull-Rom) to the stored
     pixel, then the fetch's Gaussian. So a crest a generator makes sharp is softened exactly as the radar softened
     the real one, and the two are compared alike.
"""
from __future__ import annotations

import math

import numpy as np

from .refs import grid

SEA_TOL_M = 0.3            # the references' sea rule (reference/fetch_references.py build())
SEA_DROP_M = 2.0


class Matched:
    def __init__(self, gen, ref, pixel, extent, notes, gen_water=None, ref_water=None):
        self.gen, self.ref, self.pixel, self.extent = gen, ref, float(pixel), float(extent)
        self.notes = notes
        self.gen_water, self.ref_water = gen_water, ref_water

    def __repr__(self):
        return f'Matched({self.gen.shape[1]}x{self.gen.shape[0]} @ {self.pixel:g} m; {"; ".join(self.notes)})'


def surface(h, water=None, sea_level=None):
    """(surface, lake mask or None): h with lakes as their flat surfaces and the sea at sea level - 2 m."""
    s = np.asarray(h, dtype=np.float64).copy()
    lake = None
    if water is not None:
        w = np.asarray(water, dtype=np.float64)
        lake = w > 0.01
        s = s + np.where(lake, w, 0.0)
    if sea_level is not None:
        sea = s <= sea_level + SEA_TOL_M
        s[sea] = sea_level - SEA_DROP_M
        if lake is not None:
            lake &= ~sea
    return s, lake


def crop_centre(a, side_cells):
    """The centred square of side_cells x side_cells cells."""
    ny, nx = a.shape
    j0, i0 = (ny - side_cells) // 2, (nx - side_cells) // 2
    return a[j0:j0 + side_cells, i0:i0 + side_cells]


def _cubic_axis(a, n_out, scale, axis):
    """Catmull-Rom resampling along one axis, cell-centred: output cell k sits at source index (k + 0.5) * scale -
    0.5 (scale = output cell / source cell), edges clamped."""
    a = np.moveaxis(np.asarray(a, dtype=np.float64), axis, 0)
    n = a.shape[0]
    x = (np.arange(n_out) + 0.5) * scale - 0.5
    i0 = np.floor(x).astype(np.int64)
    t = (x - i0)[(slice(None),) + (None,) * (a.ndim - 1)]
    w = ((-t ** 3 + 2 * t ** 2 - t) * 0.5, (3 * t ** 3 - 5 * t ** 2 + 2) * 0.5, (-3 * t ** 3 + 4 * t ** 2 + t) * 0.5,
         (t ** 3 - t ** 2) * 0.5)
    out = sum(wk * a[np.clip(i0 + k - 1, 0, n - 1)] for k, wk in enumerate(w))
    return np.moveaxis(out, 0, axis)


def cubic_resample(a, src_cell, dst_cell, n_out):
    r = float(dst_cell) / float(src_cell)
    return _cubic_axis(_cubic_axis(a, n_out, r, 0), n_out, r, 1)


def gaussian(a, sigma_px):
    """Separable Gaussian blur, edges reflected (numpy only)."""
    if sigma_px <= 0:
        return np.asarray(a, dtype=np.float64)
    rad = max(1, int(math.ceil(3.0 * sigma_px)))
    k = np.exp(-0.5 * (np.arange(-rad, rad + 1) / sigma_px) ** 2)
    k /= k.sum()
    out = np.asarray(a, dtype=np.float64)
    for axis in (0, 1):
        pad = [(0, 0), (0, 0)]
        pad[axis] = (rad, rad)
        p = np.pad(out, pad, mode='reflect')
        acc = np.zeros_like(out)
        n = out.shape[axis]
        for i, wk in enumerate(k):
            sl = [slice(None), slice(None)]
            sl[axis] = slice(i, i + n)
            acc += wk * p[tuple(sl)]
        out = acc
    return out


def _mask_to(mask, src_cell, dst_cell, n_out):
    if mask is None:
        return None
    return grid.resample_box(mask.astype(np.float64), src_cell, dst_cell, n_out) > 0.5


def match(h, cell, ref, water=None, sea_level=None, source_chain=True):
    """A generated field (row 0 = south, metres, `cell` metres per cell) and a refs.Reference on one grid.
    source_chain=False skips step 4 for a field that already carries the source's softness: the reference's own
    data, or a real_place terrain whose main level is that DEM (the chain twice would soften it twice)."""
    notes = []
    gs, glake = surface(h, water, sea_level)
    cell = float(cell)
    rh = ref.h
    rlake = ref.lake_mask()
    ext_g, ext_r = gs.shape[1] * cell, ref.extent
    if gs.shape[0] != gs.shape[1]:
        raise ValueError(f'the judge compares square tiles; got {gs.shape[1]} x {gs.shape[0]} cells')
    extent = ext_r
    if abs(ext_g - ext_r) > 0.01 * ext_r:
        extent = min(ext_g, ext_r)
        mg, mr = int(round(extent / cell)), int(round(extent / ref.pixel))
        gs = crop_centre(gs, mg)
        glake = crop_centre(glake, mg) if glake is not None else None
        rh = crop_centre(rh, mr)
        rlake = crop_centre(rlake, mr) if rlake is not None else None
        extent = min(mg * cell, mr * ref.pixel)
        notes.append(f'extent mismatch: generated {ext_g / 1000:g} km vs reference {ext_r / 1000:g} km; both cropped '
                     f'about their centres to {extent / 1000:g} km (generate at the reference extent)')
    pixel = max(ref.pixel, cell)
    n_out = int(round(extent / pixel))
    if ref.soft and source_chain and cell < ref.native_m:
        nat = ref.native_m
        n_nat = max(8, int(round(extent / nat)))
        coarse = grid.resample_box(gs, cell, extent / n_nat, n_nat)
        n_ref = int(round(extent / ref.pixel))
        g = cubic_resample(coarse, extent / n_nat, ref.pixel, n_ref)
        g = gaussian(g, ref.native_blur_px * nat / ref.pixel)
        notes.append(f'reference is {nat:g} m data stored at {ref.pixel:g} m: the generated field went through the '
                     f'same chain (box to {nat:g} m, Catmull-Rom up, Gaussian {ref.native_blur_px:g} native px)')
        gw = _mask_to(glake, cell, ref.pixel, n_ref)
        r = rh if rh.shape[0] == n_ref else grid.resample_box(rh, ref.pixel, ref.pixel, n_ref)
        return Matched(g, np.asarray(r, dtype=np.float64), ref.pixel, extent, notes, gw, rlake)
    if cell < pixel - 1e-9 or gs.shape[0] != n_out:
        g = grid.resample_box(gs, cell, pixel, n_out)
    else:
        g = np.asarray(gs, dtype=np.float64)
    gw = _mask_to(glake, cell, pixel, n_out)
    if pixel > ref.pixel + 1e-9 or rh.shape[0] != n_out:
        r = grid.resample_box(rh, ref.pixel, pixel, n_out)
        rw = _mask_to(rlake, ref.pixel, pixel, n_out)
        if pixel > ref.pixel + 1e-9:
            notes.append(f'generated cell {cell:g} m is coarser than the reference pixel {ref.pixel:g} m: both '
                         f'measured at {pixel:g} m')
    else:
        r, rw = np.asarray(rh, dtype=np.float64), rlake
    if cell < pixel - 1e-9:
        notes.append(f'generated {cell:g} m cells box-averaged to the reference pixel {pixel:g} m')
    return Matched(g, r, pixel, extent, notes, gw, rw)

"""The numpy twin of sample_creep.glsl: the same arithmetic in float32 with array shifts (the worked example of a
twin; register it by importing this module)."""
import os

import numpy as np

from eidoblend.terrain.core import twins as T

KERNEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sample_creep.glsl')
F = np.float32


@T.twin('sample_creep')
def sample_creep(s, u):
    st, par, pin = s['st'], s['par'], s['pin']
    h = st[..., 0]
    sc = par[..., 2]
    acc = np.zeros_like(h)
    for k in range(8):
        hq, ok = T.neighbour(h, k, u['uBound'])
        sl = (hq - h) / (T.LEN[k] * u['uDx'])
        r = sl / sc
        f = np.minimum(F(1) / np.maximum(F(1) - r * r, F(1e-9)), u['uCap'])
        acc = acc + np.where(ok, T.WISO[k] * f * (hq - h), F(0))
    hn = h + u['uDtSub'] * u['uD'] * acc / (u['uDx'] * u['uDx'])
    if u['uBound'] == T.BOUND_PINNED:
        hn = T.pin_apply(hn, pin[..., 0], pin[..., 1])
    return {'outS': T.rgba(hn, st[..., 1])}


def inputs(shape=(80, 96), seed=1, relief=400.0):
    """The parity test's fields: a rough height (one smoothing pass, so some neighbour pairs sit under the
    threshold and some are capped), A carried in .y, Sc = tan 35 deg +-15 %, and pins (border ramp + discs)."""
    h = T.random_field(shape, 0.0, relief, seed, smooth=1)
    A = T.random_field(shape, 100.0, 1e6, seed + 1)
    sc = np.tan(np.radians(35.0)) * (0.85 + 0.3 * T.random_field(shape, 0, 1, seed + 2, smooth=2))
    pw, ph = T.pin_pattern(shape, seed, band=4, value=(0.0, relief))
    return {'st': T.rgba(h, A), 'par': T.rgba(None, None, sc), 'pin': T.rgba(pw, ph)}


def uniforms(mode, cell=10.0, D=0.5, cap=5.0):
    dt = 0.9 * cell * cell / (3.4 * D * cap)                 # the stability bound of the design (section 4.1)
    return {'uDx': cell, 'uDtSub': dt, 'uD': D, 'uCap': cap, 'uBound': mode}

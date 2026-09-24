"""Cascade/parallel formant synthesis engine (Klatt 1980 lineage), numba-compiled.

Signal path per sample:
    glottal flow derivative (KLGLOTT88-style polynomial, open quotient `oq`,
    polyBLEP-smoothed closure) -> spectral tilt (one-pole low-pass)
    + aspiration noise, pitch-synchronously modulated (louder while the glottis is open)
    -> nasal zero -> nasal pole -> F6..F1 resonators in cascade      (voiced + aspiration)
    + frication noise -> three parallel band-pass resonators          (fricatives, bursts)
    -> sum -> DC blocker

Control parameters arrive at the control rate `cr` (Hz, default 1000) and are
linearly interpolated per sample; resonator coefficients are refreshed every
`coef_every` samples. All amplitudes are linear.
"""
from __future__ import annotations

import math

import numpy as np
from numba import njit

TWO_PI = 2.0 * math.pi


@njit(cache=True, fastmath=True)
def _res_coef(f, bw, sr):
    """Digital resonator (Klatt): y = a*x + b*y1 + c*y2, unity gain at DC."""
    if f <= 0.0 or f >= 0.49 * sr:
        return 1.0, 0.0, 0.0
    r = math.exp(-math.pi * bw / sr)
    c = -r * r
    b = 2.0 * r * math.cos(TWO_PI * f / sr)
    a = 1.0 - b - c
    return a, b, c


@njit(cache=True, fastmath=True)
def _res_coef_peak(f, bw, sr):
    """Band-pass resonator normalised to unity gain at its centre frequency."""
    if f <= 0.0 or f >= 0.49 * sr:
        return 0.0, 0.0, 0.0
    r = math.exp(-math.pi * bw / sr)
    c = -r * r
    b = 2.0 * r * math.cos(TWO_PI * f / sr)
    w = TWO_PI * f / sr
    # |1 - b e^{-jw} - c e^{-2jw}|
    re = 1.0 - b * math.cos(w) - c * math.cos(2.0 * w)
    im = b * math.sin(w) + c * math.sin(2.0 * w)
    g = math.sqrt(re * re + im * im)
    return g, b, c


@njit(cache=True, fastmath=True)
def _xorshift(s):
    # 32-bit xorshift held in an int64 (masked) so numba never widens the type mid-loop
    s ^= (s << 13) & 0xFFFFFFFF
    s ^= s >> 17
    s ^= (s << 5) & 0xFFFFFFFF
    return s & 0xFFFFFFFF


@njit(cache=True, fastmath=True)
def _polyblep(t, dt):
    if t < dt:
        t = t / dt
        return t + t - t * t - 1.0
    elif t > 1.0 - dt:
        t = (t - 1.0) / dt
        return t * t + t + t + 1.0
    return 0.0


@njit(cache=True, fastmath=True)
def synth_core(sr, cr, n_out, f0, av, ah, af, oq, tilt, F, B, fnp, fnz, fr_f, fr_b, fr_g,
               jitter, shimmer, seed, coef_every):
    """Render n_out samples. Control arrays are length n_ctrl at rate cr.

    F, B: (6, n_ctrl) formant frequencies/bandwidths; fr_*: (3, n_ctrl) frication bank.
    tilt: one-pole coefficient in [0, 0.99) (higher = darker source).
    """
    out = np.zeros(n_out)
    n_ctrl = f0.shape[0]
    st = np.int64(seed) & 0xFFFFFFFF
    if st == 0:
        st = np.int64(1234567)
    # cascade resonator states (6 formants + nasal pole) and antiresonator (nasal zero)
    y1 = np.zeros(7)
    y2 = np.zeros(7)
    ra = np.zeros(7)
    rb = np.zeros(7)
    rc = np.zeros(7)
    za = 1.0
    zb = 0.0
    zc = 0.0
    zx1 = 0.0
    zx2 = 0.0
    # frication bank states
    fy1 = np.zeros(3)
    fy2 = np.zeros(3)
    fa = np.zeros(3)
    fb = np.zeros(3)
    fc = np.zeros(3)
    phase = 0.0
    cyc_jit = 1.0
    cyc_shim = 1.0
    tilt_y = 0.0
    dc_x1 = 0.0
    dc_y1 = 0.0
    noise_lp = 0.0
    ratio = cr / sr
    for n in range(n_out):
        # control interpolation
        pos = n * ratio
        i0 = int(pos)
        if i0 >= n_ctrl - 1:
            i0 = n_ctrl - 2
            fr = 1.0
        else:
            fr = pos - i0
        i1 = i0 + 1
        _f0 = f0[i0] + (f0[i1] - f0[i0]) * fr
        _av = av[i0] + (av[i1] - av[i0]) * fr
        _ah = ah[i0] + (ah[i1] - ah[i0]) * fr
        _af = af[i0] + (af[i1] - af[i0]) * fr
        _oq = oq[i0] + (oq[i1] - oq[i0]) * fr
        _tl = tilt[i0] + (tilt[i1] - tilt[i0]) * fr
        if n % coef_every == 0:
            for k in range(6):
                fk = F[k, i0] + (F[k, i1] - F[k, i0]) * fr
                bk = B[k, i0] + (B[k, i1] - B[k, i0]) * fr
                a, b, c = _res_coef(fk, bk, sr)
                ra[k] = a
                rb[k] = b
                rc[k] = c
            _fnp = fnp[i0] + (fnp[i1] - fnp[i0]) * fr
            _fnz = fnz[i0] + (fnz[i1] - fnz[i0]) * fr
            a, b, c = _res_coef(_fnp, 100.0, sr)
            ra[6] = a
            rb[6] = b
            rc[6] = c
            a, b, c = _res_coef(_fnz, 100.0, sr)
            # antiresonator = inverse of resonator
            za = 1.0 / a
            zb = -b / a
            zc = -c / a
            for k in range(3):
                ff = fr_f[k, i0] + (fr_f[k, i1] - fr_f[k, i0]) * fr
                fbw = fr_b[k, i0] + (fr_b[k, i1] - fr_b[k, i0]) * fr
                g, b, c = _res_coef_peak(ff, fbw, sr)
                gg = fr_g[k, i0] + (fr_g[k, i1] - fr_g[k, i0]) * fr
                # a = (1-r) scaled so centre gain = gg: y = a*x + b*y1 + c*y2 with |H(wc)| = a/g
                fa[k] = gg * g
                fb[k] = b
                fc[k] = c
        # --- glottal source -------------------------------------------------
        dt = _f0 * cyc_jit / sr
        if dt > 0.45:
            dt = 0.45
        prev_phase = phase
        phase += dt
        if phase >= 1.0:
            phase -= 1.0
            # new cycle: draw jitter and shimmer
            st = _xorshift(st)
            u = (st / 4294967295.0) * 2.0 - 1.0
            cyc_jit = 1.0 + jitter * u
            st = _xorshift(st)
            u = (st / 4294967295.0) * 2.0 - 1.0
            cyc_shim = 1.0 + shimmer * u
        oqv = _oq
        if oqv < 0.2:
            oqv = 0.2
        if oqv > 0.95:
            oqv = 0.95
        if phase < oqv:
            tau = phase / oqv
            e = 2.0 * tau - 3.0 * tau * tau
            open_ph = 1.0
        else:
            e = 0.0
            open_ph = 0.0
        # polyBLEP at the closure (step of +1 at phase == oqv)
        tp = phase - oqv
        if tp < 0.0:
            tp += 1.0
        e += 0.5 * _polyblep(tp, dt if dt > 1e-9 else 1e-9)
        tilt_y = (1.0 - _tl) * e + _tl * tilt_y
        voiced = tilt_y * _av * cyc_shim
        # --- noise ----------------------------------------------------------
        st = _xorshift(st)
        wn = (st / 4294967295.0) * 2.0 - 1.0
        noise_lp = 0.5 * noise_lp + 0.5 * wn     # mild low-pass: breath with some air, not hiss
        asp = noise_lp * _ah * (0.35 + 0.65 * open_ph)
        src = voiced + asp
        # --- cascade: nasal zero, nasal pole, F6..F1 --------------------------
        x = za * src + zb * zx1 + zc * zx2
        zx2 = zx1
        zx1 = src
        yv = ra[6] * x + rb[6] * y1[6] + rc[6] * y2[6]
        y2[6] = y1[6]
        y1[6] = yv
        x = yv
        for k in range(5, -1, -1):
            yv = ra[k] * x + rb[k] * y1[k] + rc[k] * y2[k]
            y2[k] = y1[k]
            y1[k] = yv
            x = yv
        casc = x
        # --- parallel frication ---------------------------------------------
        par = 0.0
        if _af > 1e-7:
            st = _xorshift(st)
            fn = ((st / 4294967295.0) * 2.0 - 1.0) * _af
            for k in range(3):
                yv = fa[k] * fn + fb[k] * fy1[k] + fc[k] * fy2[k]
                fy2[k] = fy1[k]
                fy1[k] = yv
                par += yv
        else:
            for k in range(3):
                yv = fb[k] * fy1[k] + fc[k] * fy2[k]
                fy2[k] = fy1[k]
                fy1[k] = yv
                par += yv
        s = casc + par
        # DC blocker
        yd = s - dc_x1 + 0.9995 * dc_y1
        dc_x1 = s
        dc_y1 = yd
        out[n] = yd
    return out

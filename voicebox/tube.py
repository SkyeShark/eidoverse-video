"""Kelly-Lochbaum vocal tract: a physically modelled 1961 Bell Labs singing voice.

In 1961 John L. Kelly Jr. and Carol Lochbaum made an IBM 7090 sing "Daisy Bell" (Max
Mathews programmed the accompaniment). The voice was a physical model: the vocal tract
as a chain of cylindrical tube sections joined by scattering junctions (Kelly & Lochbaum,
"Speech synthesis", Proc. 4th ICA, Copenhagen 1962), its vowel shapes taken from Gunnar
Fant's X-ray area functions of Russian vowels. This module rebuilds that machine on
voicebox's own planning (`plan_segments`, `sung_f0`). It evokes the published principle;
it is not an emulation of the original program.

    tube_formants(areas, length_cm)    resonances of the lossy tube (chain matrices)
    fit_area(targets_hz, n_sections)   smooth area function for target F1-F3 (F4 optional)
    vowel_areas(n_sections, vtl)       cached fits for every VOWEL_MALE key and L R W Y
    render_tube(sung, ...)             the waveguide itself at fs = N c / (2 L): (y, fs, segs, tr)
    bell_labs_1961_clean(sung, ...)    the tube alone, band-limited to 48 kHz
    bell_labs_1961(sung, t_end, vtl)   era renderer: tube -> 10 kHz -> 12 bit -> tape -> 48 kHz

The waveguide. N sections of length L/N; section 0 is at the glottis, N-1 at the lips.
One-way travel through a section takes half a sample, so fs = N c / (2 L): 20 sections
of a 17.5 cm tract run at exactly 20 kHz. Both half-sample delays of a section are lumped
into its right-going path. Every loop keeps its delay, so every resonance is unchanged,
and the left-going sweep becomes delay-free: the classic lattice filter. (The direct
glottis->lips and glottis->nostrils paths do change, by a delay and a loss factor; both are
undone at the outputs.) Waves are power-normalised pressure waves, so a junction is the
rotation [[c, -k], [k, c]], k = (A_i - A_i+1) / (A_i + A_i+1), c = sqrt(1 - k^2). For fixed
areas that is the classic pressure-wave junction; unlike it, it stays lossless while areas
move. It is recomputed every sample from areas interpolated in log-area between 1 kHz
control frames (|k| < 1 because every area > 0).
Terminations: the glottis reflects r_g = 0.75 while voicing, less when it is spread for
voiceless sounds. The lips are Flanagan's radiation load (the parallel R-L of a piston
in a baffle) mapped by the bilinear transform to a first-order reflection filter: -1 at
DC, and more of the highs escape as the lip opening grows. Each section traversal loses
a little energy (MU). Output = d/dt of lip + nostril flow.
Source: a Rosenberg glottal flow pulse (AC-coupled) with jitter and shimmer, plus
aspiration noise pulsed by the glottal opening. Its strength follows the oral
constriction aerodynamically (see AERO_AG): a narrow mouth starves the glottis.

`tube_formants` models exactly this system (same loss, same glottal reflection, same
digital lip filter). With the velum shut it roots the chain product written in z, so it
gives the waveguide's exact poles; the waveguide's impulse response matches its transfer
function to < 0.001 dB. That is why fitted areas land where the waveguide sings them.

Articulation (Ohman-style): vowels, liquids and glides set area targets for a smooth
substrate; consonants are constriction gestures blended onto it at their place with a
Gaussian spatial profile, narrowest wins. Coronals pull the tongue body forward (the
alveolar F2 locus), and vowels reach their target ~40 ms after a consonant.
  stops       closure (1e-3 cm^2) at the place-of-articulation section, then a noise burst
              injected just downstream (coloured by place), then aspiration at the spread
              glottis (VOT, spilling into a following liquid as in "cr")
  fricatives  a ~0.1-0.2 cm^2 constriction with a noise pressure source (a dipole) just
              downstream; sibilants inject at the teeth; voiced ones add voicing and
              pulse the noise with the glottal flow
  nasals      a real side branch: velopharyngeal port + ~12 cm nasal tract radiating at
              the nostrils, joined to the oral tract by a three-port junction at the
              velum. The oral closure turns the mouth into a side cavity, so the murmur's
              pole-zero pattern comes out of the physics, not a table
  liquids and glides   area targets fitted to the formant targets in CONSONANTS
  /h/         aspiration noise at an open glottis in the shape of the following vowel
  voice bar   the pharyngeal pressure, low-passed at 250 Hz, stands in for sound radiated
              through the throat walls, so voiced closures still hum
"""
from __future__ import annotations

import cmath
import math
from fractions import Fraction

import numpy as np
from numba import njit
from scipy.ndimage import gaussian_filter1d
from scipy.optimize import least_squares
from scipy.signal import resample_poly

from .articulate import CR, Voice, plan_segments, sung_f0
from .phonemes import CONSONANTS, DIPHTHONGS, HIGH_FORMANTS, VOWEL_MALE, VOWELS, lerp, vowel_formants

# --- physical constants and defaults -------------------------------------------------------
C_CM = 35000.0            # speed of sound in warm, humid air (cm/s)
L_MALE_CM = 17.5          # adult male vocal-tract length (cm)
RG = 0.75                 # glottal reflection while voicing (pressure waves)
RG_SPREAD = 0.45          # glottis spread for voiceless obstruents
RG_OPEN = 0.30            # wide open for /h/
MU = 0.996                # wave amplitude kept per section traversal (oral tract): B1 ~ 60-180 Hz
MU_NASAL = 0.992          # the nasal passages are lossier (large, soft surface)
LIP_MIN = 0.05            # radiation filter floor for the lip opening (cm^2)
CLOSED = 1e-3             # area of a complete closure (cm^2); keeps |k| < 1
A_MIN, A_MAX = 0.25, 12.0  # bounds for fitted area functions (cm^2)
LARYNX = (1.75, 0.4, 1.2)  # epilaryngeal tube: first 1.75 cm (male) kept within 0.4-1.2 cm^2
VELUM_CM = 9.0            # velopharyngeal port position from the glottis (male, cm)
NASAL_CM = 11.4           # port-to-nostril length (male, cm)
VELUM_OPEN = 0.9          # port area when the velum is fully lowered (cm^2)
VELUM_SHUT = 1e-6         # port area with the velum raised (the waveguide never uses exactly 0)
RAD_RHO = 128.0 / (9.0 * math.pi ** 2)   # Flanagan: radiation resistance / (rho c / A)
BW_MAX = 900.0            # poles broader than this (Hz) are not counted as formants


def tract_length(vtl=0.0):
    """Vocal-tract length in cm for voicebox's vtl scale (0 = adult male 17.5 cm, 1 = adult
    female 14.3 cm, about the measured adult averages; Peterson & Barney's female vowels fit
    best there)."""
    return L_MALE_CM / (1.0 + 0.22 * vtl)


def tube_rate(n_sections, length_cm, c=C_CM):
    """The sample rate a section count implies: one section round trip per sample."""
    return n_sections * c / (2.0 * length_cm)


def nasal_areas(n):
    """Nasal tract area function (cm^2), port side first; element 0 is replaced by the port."""
    s = (np.arange(n) + 0.5) / n
    return 1.5 + 3.0 * np.sin(np.pi * s) ** 1.5


# --- lip / nostril radiation ---------------------------------------------------------------
@njit(cache=True)
def _rad_coefs(area, fs):
    """First-order reflection filter R(z) = (b0 + b1 z^-1) / (1 + a1 z^-1) for pressure waves
    leaving an opening of `area` cm^2: Flanagan's piston load R_r || L_r, bilinear-mapped."""
    r = math.sqrt(area / math.pi)
    tau = 8.0 * r / (3.0 * math.pi * C_CM)      # L_r / (rho c / A), seconds
    q = 2.0 * fs * tau
    a0 = q * (RAD_RHO + 1.0) + RAD_RHO
    b0 = (q * (RAD_RHO - 1.0) - RAD_RHO) / a0
    b1 = -(q * (RAD_RHO - 1.0) + RAD_RHO) / a0
    a1 = (RAD_RHO - q * (RAD_RHO + 1.0)) / a0
    return b0, b1, a1


# --- chain (transfer) matrices ---------------------------------------------------------------
@njit(cache=True)
def _tube_eval(A, fs, mu, rg, An, jv, mun, va, f):
    """Chain-matrix walk from the lips to the glottis at complex frequency f (Hz).

    Lip flow is normalised to (1 - R_L) so nothing has a pole on the way. Returns
    (Ug, Uout): the glottal source flow that produces it and the radiated flow (lips +
    nostrils). The transfer function is Uout / Ug; its poles, the resonances, are the
    zeros of Ug. Each section is a lossy line, [P;U]_in = [[ch, Z sh],[sh/Z, ch]] [P;U]_out
    with e^(gamma dx) = z^(1/2) / mu: exactly the waveguide's half-sample delay and loss.
    The nasal branch, when open, is a shunt admittance at junction jv.
    """
    N = A.shape[0]
    zh = cmath.exp(1j * math.pi * f / fs)
    zi = 1.0 / (zh * zh)
    la = A[N - 1] if A[N - 1] > LIP_MIN else LIP_MIN
    b0, b1, a1 = _rad_coefs(la, fs)
    RL = (b0 + b1 * zi) / (1.0 + a1 * zi)
    P = (1.0 + RL) / A[N - 1]
    U = 1.0 - RL + 0j
    Uout = U
    ch = 0.5 * (zh / mu + mu / zh)
    sh = 0.5 * (zh / mu - mu / zh)
    nasal = va > 1e-7 and jv > 0
    Zin = 1.0 + 0j
    tn = 0j
    if nasal:
        M = An.shape[0]
        chn = 0.5 * (zh / mun + mun / zh)
        shn = 0.5 * (zh / mun - mun / zh)
        nb0, nb1, na1 = _rad_coefs(An[M - 1], fs)
        RN = (nb0 + nb1 * zi) / (1.0 + na1 * zi)
        Pn = (1.0 + RN) / An[M - 1]
        Un = 1.0 - RN + 0j
        un_out = Un
        for m in range(M - 1, -1, -1):
            am = va if m == 0 else An[m]
            Pn, Un = chn * Pn + shn * Un / am, shn * am * Pn + chn * Un
        Zin = Pn / Un            # input impedance of the nasal branch at the port
        tn = un_out / Un         # nostril flow per unit flow into the port
    for i in range(N - 1, -1, -1):
        a = A[i]
        P, U = ch * P + sh * U / a, sh * a * P + ch * U
        if nasal and i == jv:
            uin = P / Zin
            Uout = Uout + uin * tn
            U = U + uin
    Zg = (1.0 / A[0]) * (1.0 + rg) / (1.0 - rg)
    return U + P / Zg, Uout


@njit(cache=True)
def _resonances(A, fs, mu, rg, An, jv, mun, va, fmax, df, nmax):
    """Peaks of |Uout/Ug| on a grid, each polished by complex Newton on Ug = 0.

    Returns (freqs, bandwidths, count): pole frequencies and -3 dB bandwidths in Hz."""
    ng = int(fmax / df)
    mag = np.empty(ng)
    for i in range(ng):
        ug, uo = _tube_eval(A, fs, mu, rg, An, jv, mun, va, (i + 1) * df + 0j)
        mag[i] = math.log(abs(uo) + 1e-300) - math.log(abs(ug) + 1e-300)
    fo = np.zeros(nmax)
    bo = np.zeros(nmax)
    cnt = 0
    for i in range(1, ng - 1):
        if cnt >= nmax:
            break
        if not (mag[i] > mag[i - 1] and mag[i] >= mag[i + 1]):
            continue
        den = mag[i - 1] - 2.0 * mag[i] + mag[i + 1]
        off = 0.5 * (mag[i - 1] - mag[i + 1]) / den if den < 0.0 else 0.0
        fp = (i + 1 + off) * df
        # curvature of log|H| at the peak -> bandwidth guess for a single pole
        bw0 = 2.0 * df * math.sqrt(2.0 * 0.3466 / max(-den, 1e-9)) if den < 0.0 else 60.0
        x = complex(fp, 0.5 * min(max(bw0, 10.0), 400.0))
        ok = False
        for it in range(40):
            g0, _ = _tube_eval(A, fs, mu, rg, An, jv, mun, va, x)
            gp, _ = _tube_eval(A, fs, mu, rg, An, jv, mun, va, x + 0.25)
            gm, _ = _tube_eval(A, fs, mu, rg, An, jv, mun, va, x - 0.25)
            d = (gp - gm) / 0.5
            if d == 0:
                break
            step = g0 / d
            if abs(step) > 200.0:
                step = step / abs(step) * 200.0
            x = x - step
            if abs(step) < 1e-7:
                ok = True
                break
        if ok and abs(x.real - fp) < 150.0 and 0.0 < x.imag < 1500.0:
            F, Bw = x.real, 2.0 * x.imag
        else:
            F, Bw = fp, bw0
        if cnt > 0 and abs(F - fo[cnt - 1]) < 3.0:
            continue
        fo[cnt] = F
        bo[cnt] = Bw
        cnt += 1
    return fo, bo, cnt


@njit(cache=True)
def _oral_poles(A, fs, mu, rg, fmax, bmax, nmax):
    """All resonances of the oral tube at once: the same chain matrices written in z.

    Scaled by 2 mu z^(1/2), a section's matrix is [[z + mu^2, (z - mu^2)/A], [(z - mu^2) A,
    z + mu^2]], a polynomial in z = e^(j 2 pi f / fs); the lip load (bilinear Flanagan filter)
    is first order. Walking lips -> glottis gives Ug(z) as a degree N+1 polynomial whose roots
    are exactly the waveguide's poles, so no resonance can be missed the way peak-picking a
    grid misses two broad formants that merge into one hump (/o/'s F1 and F2)."""
    N = A.shape[0]
    deg = N + 1
    P = np.zeros(deg + 1)
    U = np.zeros(deg + 1)
    la = A[N - 1] if A[N - 1] > LIP_MIN else LIP_MIN
    b0, b1, a1 = _rad_coefs(la, fs)
    # coefficients stored low power first: c[k] multiplies z^k
    P[1] = (1.0 + b0) / A[N - 1]
    P[0] = (a1 + b1) / A[N - 1]
    U[1] = 1.0 - b0
    U[0] = a1 - b1
    m2 = mu * mu
    d = 1
    for i in range(N - 1, -1, -1):
        a = A[i]
        Pn = np.zeros(deg + 1)
        Un = np.zeros(deg + 1)
        for k in range(d + 1):
            # (z + m2) P + (z - m2) U / a
            Pn[k + 1] += P[k] + U[k] / a
            Pn[k] += m2 * P[k] - m2 * U[k] / a
            # (z - m2) a P + (z + m2) U
            Un[k + 1] += a * P[k] + U[k]
            Un[k] += -m2 * a * P[k] + m2 * U[k]
        P = Pn
        U = Un
        d += 1
    g = (1.0 - rg) / (1.0 + rg) * A[0]         # 1 / Zg
    c = U + P * g
    top = deg
    while top > 0 and c[top] == 0.0:
        top -= 1
    coeffs = np.empty(top + 1)
    for k in range(top + 1):
        coeffs[k] = c[top - k]                  # np.roots wants high power first
    r = np.roots(coeffs.astype(np.complex128))
    fo = np.zeros(nmax)
    bo = np.zeros(nmax)
    cnt = 0
    F = np.empty(r.shape[0])
    Bw = np.empty(r.shape[0])
    for k in range(r.shape[0]):
        F[k] = math.atan2(r[k].imag, r[k].real) * fs / (2.0 * math.pi)
        Bw[k] = -math.log(abs(r[k]) + 1e-300) * fs / math.pi
    order = np.argsort(F)
    for k in order:
        if F[k] > 50.0 and F[k] < fmax and Bw[k] < bmax and cnt < nmax:
            fo[cnt] = F[k]
            bo[cnt] = Bw[k]
            cnt += 1
    return fo, bo, cnt


def _nasal_setup(n_sections, length_cm):
    """Velum junction index and nasal-branch areas. The nasal section count is chosen so the
    glottis->nostril and glottis->lip paths differ by an even number of sections: the
    waveguide lumps both half-sample delays of a section into one direction (exact for every
    loop, but it doubles path delays), and an even difference lets it restore the true
    lip/nostril timing with a whole-sample delay."""
    N = n_sections
    jv = int(round(VELUM_CM / L_MALE_CM * N))
    m = NASAL_CM / L_MALE_CM * N
    M = min((c for c in range(3, 4 * N) if (jv + c - N) % 2 == 0), key=lambda c: (abs(c - m), -c))
    return jv, nasal_areas(M)


def tube_formants(areas, length_cm=L_MALE_CM, n_formants=4, glottal_reflection=None, loss=None,
                  velum_area=0.0, return_bandwidths=False, fmax=None, c=C_CM):
    """Resonances of the lossy tube (glottis nearly closed, lips radiating), by chain matrices.

    `areas` (cm^2) run glottis -> lips in equal sections over `length_cm`. The model is the
    waveguide's own: per-section loss `loss`, glottal reflection `glottal_reflection`, the
    digital Flanagan lip filter at fs = N c / (2 L), and (if `velum_area` > 0) the nasal
    branch. Returns the first `n_formants` pole frequencies in Hz (NaN where fewer exist
    below `fmax`), plus bandwidths if asked. None = the module defaults RG and MU. With the
    velum shut the poles are the exact roots of the chain product written in z (see
    `_oral_poles`); with the nasal branch open, peaks of |H| polished by complex Newton.
    """
    glottal_reflection = RG if glottal_reflection is None else glottal_reflection
    loss = MU if loss is None else loss
    A = np.ascontiguousarray(np.asarray(areas, dtype=np.float64))
    N = len(A)
    fs = tube_rate(N, length_cm, c)
    jv, An = _nasal_setup(N, length_cm)
    fmax = fmax or min(0.5 * fs - 50.0, 6000.0)
    if velum_area > 0:      # side branch: peaks of |H| on a grid, polished by complex Newton
        fo, bo, cnt = _resonances(A, fs, loss, glottal_reflection, An, jv, MU_NASAL, float(velum_area), fmax,
                                  25.0, 12)
    else:                   # all-oral: every root of the z-domain chain product
        fo, bo, cnt = _oral_poles(A, fs, loss, glottal_reflection, fmax, BW_MAX, 12)
    F = np.full(n_formants, np.nan)
    B = np.full(n_formants, np.nan)
    m = min(cnt, n_formants)
    F[:m] = fo[:m]
    B[:m] = bo[:m]
    return (F, B) if return_bandwidths else F


def transfer_function(areas, freqs, length_cm=L_MALE_CM, glottal_reflection=None, loss=None, velum_area=0.0,
                      c=C_CM):
    """|Uout / Ug| of the tube at real frequencies (Hz): the chain-matrix transfer function."""
    glottal_reflection = RG if glottal_reflection is None else glottal_reflection
    loss = MU if loss is None else loss
    A = np.ascontiguousarray(np.asarray(areas, dtype=np.float64))
    fs = tube_rate(len(A), length_cm, c)
    jv, An = _nasal_setup(len(A), length_cm)
    out = np.empty(len(freqs))
    for i, f in enumerate(freqs):
        ug, uo = _tube_eval(A, fs, loss, glottal_reflection, An, jv, MU_NASAL, float(velum_area), complex(f))
        out[i] = abs(uo) / (abs(ug) + 1e-300)
    return out


# --- fitting area functions to formant targets -------------------------------------------------
def fit_area(targets_hz, n_sections=20, length_cm=L_MALE_CM, weights=None, a_min=None, a_max=None,
             smooth=0.03, prior=0.004, a_ref=3.0, init=None, larynx='default', bw_weight=1.0,
             bw_ref=(120.0, 160.0, 220.0, 300.0), max_nfev=400, return_info=False):
    """Smooth area function (cm^2, glottis -> lips) whose tube resonances hit `targets_hz`.

    Regularised least squares on log-area: relative formant errors (F1-F3, and F4 if
    given, weighted by `weights`), plus `smooth` x second differences of log-area (a
    smooth tongue) plus a weak pull of `prior` toward a uniform `a_ref` tube; areas are
    bounded to [a_min, a_max]. `larynx` = (length_cm, lo, hi) keeps the epilaryngeal tube
    just above the glottis narrow, as it is in X-ray and MRI area functions (without it the
    optimiser happily widens the glottis end to 12 cm^2 to tune back vowels). Many tracts
    share the same F1-F3; `bw_weight` x (bandwidth above `bw_ref`) / 1 kHz prefers the ones
    with sharp resonances, as real tracts have (without it /u/ fits with a 490 Hz-wide F2).
    The Jacobian is by finite differences on the exact z-domain poles, so its columns are the
    tube's acoustic sensitivity functions.
    """
    a_min = A_MIN if a_min is None else a_min
    a_max = A_MAX if a_max is None else a_max
    larynx = LARYNX if isinstance(larynx, str) else larynx
    T = np.asarray(targets_hz, dtype=np.float64)
    K = len(T)
    w = np.asarray(weights if weights is not None else [1.0, 1.0, 1.0, 0.3][:K], dtype=np.float64)
    N = n_sections
    fs = tube_rate(N, length_cm)
    fmax = min(0.5 * fs - 50.0, max(4500.0, T[-1] * 1.35))
    lo = np.full(N, math.log(a_min))
    hi = np.full(N, math.log(a_max))
    if larynx is not None:
        nl = int(round(larynx[0] / L_MALE_CM * N))      # scales with the tract
        lo[:nl] = math.log(larynx[1])
        hi[:nl] = math.log(larynx[2])
    x0 = np.log(init) if init is not None else np.full(N, math.log(a_ref))
    x0 = np.clip(x0, lo + 1e-6, hi - 1e-6)
    D2 = np.diff(np.eye(N), 2, axis=0)
    xr = math.log(a_ref)

    bref = np.asarray(bw_ref[:K], dtype=np.float64)

    def formants(x):
        fo, bo, cnt = _oral_poles(np.exp(x), fs, MU, RG, fmax, BW_MAX, 10)
        F = np.full(K, fmax)
        B = np.full(K, BW_MAX)
        m = min(cnt, K)
        F[:m] = fo[:m]
        B[:m] = bo[:m]
        return F, B

    def resid(x):
        F, B = formants(x)
        return np.concatenate([w * (F - T) / T, bw_weight * np.maximum(B - bref, 0.0) / 1000.0,
                               smooth * (D2 @ x), prior * (x - xr)])

    sol = least_squares(resid, x0, bounds=(lo, hi), method='trf', diff_step=2e-3, max_nfev=max_nfev,
                        x_scale=1.0)
    A = np.exp(sol.x)
    if return_info:
        F, B = formants(sol.x)
        return A, dict(formants=F, bandwidths=B, cost=sol.cost, nfev=sol.nfev, status=sol.status)
    return A


# --- cached targets: every vowel, plus the sonorant consonants ------------------------------------
SONORANTS = ('L', 'R', 'W', 'Y')
_AREA_CACHE = {}


def sonorant_targets(c, vtl=0.0):
    """F1-F4 targets for a liquid or glide, scaled for vtl the way articulate._cons_formants does."""
    f1, f2, f3 = CONSONANTS[c].formants
    s1, s2 = 1 + 0.10 * vtl, 1 + 0.17 * vtl
    f4 = lerp(HIGH_FORMANTS['male'][0], HIGH_FORMANTS['female'][0], vtl)
    return (f1 * s1, f2 * s2, f3 * s2, f4)


def vowel_areas(n_sections=20, vtl=0.0):
    """{phoneme: area function} for every VOWEL_MALE key (Peterson & Barney targets, F4 from
    HIGH_FORMANTS) and for L R W Y, fitted once per (n_sections, vtl) and cached."""
    key = (int(n_sections), round(float(vtl), 3))
    if key not in _AREA_CACHE:
        L = tract_length(vtl)
        out = {}
        for v in VOWEL_MALE:
            out[v] = fit_area(vowel_formants(v, vtl)[:4], n_sections, L)
        for c in SONORANTS:
            if c in CONSONANTS and CONSONANTS[c].formants is not None:
                out[c] = fit_area(sonorant_targets(c, vtl), n_sections, L)
        _AREA_CACHE[key] = out
    return _AREA_CACHE[key]


# --- the waveguide -------------------------------------------------------------------------------
@njit(cache=True)
def _xorshift(s):
    s ^= (s << 13) & 0xFFFFFFFF
    s ^= s >> 17
    s ^= (s << 5) & 0xFFFFFFFF
    return s & 0xFFFFFFFF


@njit(cache=True, fastmath=True)
def _kl_core(fs, cr, n_out, logA, vel, f0, av, ah, af, fpos, flp, rg, An, jv, mu, mun, tp, tn,
             jitter, shimmer, seed, asp_gain, wall_gain, fric_hp, ext_src, diff_out):
    """Kelly-Lochbaum lattice with a nasal side branch, one sample per section round trip.

    Control tracks arrive at rate `cr`: logA (N, n) log-areas glottis -> lips, vel (n) port
    area, f0/av/ah/af/rg (n), fpos (n) the junction where frication noise enters (-1 none,
    N-1 = at the lip opening), flp (n) the noise source's low-pass corner (Hz). Areas are
    interpolated in log-area and every junction is recomputed every sample.

    Waves are power-normalised pressure waves, p~ = p sqrt(A / rho c). A junction is then the
    rotation [[c, -k], [k, c]] with k = (A_i - A_i+1) / (A_i + A_i+1), c = sqrt(1 - k^2):
    the same filter as the classic pressure-wave junction for fixed areas, but lossless for
    any time variation. (Pressure waves are not: a closure section holds full-amplitude
    pressure at almost no power, and opening it in a few ms creates energy from nothing,
    a +12 dB pop at every stop release.)

    Frication noise is band-limited: 2nd-order high-pass at `fric_hp`, 2nd-order low-pass at
    flp (a turbulence source is weak at low frequencies and rolls off above a place-dependent
    peak). `ext_src` (if non-empty) replaces the glottal pulse train with a given flow signal;
    `diff_out` False returns the radiated flow itself.
    """
    N = logA.shape[0]
    n_ctrl = logA.shape[1]
    M = An.shape[0]
    out = np.zeros(n_out)
    A = np.empty(N)
    sA = np.empty(N)
    f = np.zeros(N)       # right-going wave at the glottis end of each section
    fr = np.zeros(N)      # ... one sample later, arriving at its lip end
    nf = np.zeros(M)      # nasal branch: outward waves at the port end of each section
    nfr = np.zeros(M)
    sAn = np.sqrt(An)
    mu2 = mu * mu
    mun2 = mun * mun
    nb0, nb1, na1 = _rad_coefs(An[M - 1], fs)
    lx1 = 0.0
    ly1 = 0.0
    nx1 = 0.0
    ny1 = 0.0
    phase = 0.0
    cyc_jit = 1.0
    cyc_shim = 1.0
    st = np.int64(seed) & 0xFFFFFFFF
    if st == 0:
        st = np.int64(1234567)
    asp_lp = 0.0
    u_prev = 0.0
    w_lp = 0.0
    w_lp2 = 0.0
    w_hp = 0.0
    k_wl = 1.0 - math.exp(-2.0 * math.pi * 250.0 / fs)
    k_wh = 1.0 - math.exp(-2.0 * math.pi * 60.0 / fs)
    k_fh = 1.0 - math.exp(-2.0 * math.pi * fric_hp / fs)
    fh1 = 0.0
    fh2 = 0.0
    fl1 = 0.0
    fl2 = 0.0
    use_ext = ext_src.shape[0] > 0
    g_mean = 0.5 * tp + tn * 2.0 / math.pi        # mean of the Rosenberg pulse over a period
    ratio = cr / fs
    # undo what lumping the delays and losses did to the two direct paths (see _nasal_setup)
    gL = mu ** (-N)
    gN = mu ** (-jv) * mun ** (-M)
    dL = (jv + M - N) // 2 if jv + M > N else 0
    dN = (N - jv - M) // 2 if N > jv + M else 0
    bufL = np.zeros(dL + 1)
    bufN = np.zeros(dN + 1)
    for n in range(n_out):
        pos = n * ratio
        i0 = int(pos)
        if i0 >= n_ctrl - 1:
            i0 = n_ctrl - 2
            w = 1.0
        else:
            w = pos - i0
        i1 = i0 + 1
        for i in range(N):
            a0 = logA[i, i0]
            A[i] = math.exp(a0 + w * (logA[i, i1] - a0))
            sA[i] = math.sqrt(A[i])
        _f0 = f0[i0] + w * (f0[i1] - f0[i0])
        _av = av[i0] + w * (av[i1] - av[i0])
        _ah = ah[i0] + w * (ah[i1] - ah[i0])
        _af = af[i0] + w * (af[i1] - af[i0])
        _rg = rg[i0] + w * (rg[i1] - rg[i0])
        va = vel[i0] + w * (vel[i1] - vel[i0])
        if va < VELUM_SHUT:
            va = VELUM_SHUT
        sva = math.sqrt(va)
        fp = fpos[i0] if w < 0.5 else fpos[i1]
        # --- glottal source: Rosenberg flow pulse, jitter and shimmer per cycle ----------------
        g = 0.0
        if use_ext:
            ug = ext_src[n] if n < ext_src.shape[0] else 0.0
        else:
            dt = _f0 * cyc_jit / fs
            if dt > 0.45:
                dt = 0.45
            phase += dt
            if phase >= 1.0:
                phase -= 1.0
                st = _xorshift(st)
                cyc_jit = 1.0 + jitter * ((st / 4294967295.0) * 2.0 - 1.0)
                st = _xorshift(st)
                cyc_shim = 1.0 + shimmer * ((st / 4294967295.0) * 2.0 - 1.0)
            if phase < tp:
                g = 0.5 - 0.5 * math.cos(math.pi * phase / tp)
            elif phase < tp + tn:
                g = math.cos(0.5 * math.pi * (phase - tp) / tn)
            # AC-coupled: the pulse's mean flow never radiates in a steady vowel, but in a linear
            # tube it would pile up behind every closure and discharge as a thump at the release
            ug = (g - g_mean) * _av * cyc_shim
        # aspiration: turbulent flow at the glottis, pulsed by the glottal opening while voicing
        st = _xorshift(st)
        asp_lp = 0.55 * asp_lp + 0.45 * ((st / 4294967295.0) * 2.0 - 1.0)
        mv = 0.7 * min(1.0, _av)
        ug += asp_gain * _ah * asp_lp * ((1.0 - mv) + mv * g)
        # frication: a pressure dipole just downstream of the constriction
        ns = 0.0
        if _af > 1e-7 and fp >= 0:
            st = _xorshift(st)
            x = (st / 4294967295.0) * 2.0 - 1.0
            fh1 += k_fh * (x - fh1)            # two one-pole high-passes: -12 dB/oct below fric_hp
            x -= fh1
            fh2 += k_fh * (x - fh2)
            x -= fh2
            _flp = flp[i0] + w * (flp[i1] - flp[i0])
            k_fl = 1.0 - math.exp(-2.0 * math.pi * _flp / fs)
            fl1 += k_fl * (x - fl1)            # two one-pole low-passes: -12 dB/oct above flp
            fl2 += k_fl * (fl1 - fl2)
            x = fl2
            mv = 0.6 * min(1.0, _av)
            ns = _af * x * ((1.0 - mv) + mv * g)
        # --- waves arrive at the lip end of their section (the lumped one-sample delay) -------
        for i in range(N):
            fr[i] = mu2 * f[i]
        la = A[N - 1] if A[N - 1] > LIP_MIN else LIP_MIN
        b0, b1, a1 = _rad_coefs(la, fs)
        pp = fr[N - 1]
        pm = b0 * pp + b1 * lx1 - a1 * ly1
        lx1 = pp
        ly1 = pm
        UL = sA[N - 1] * (pp - pm)
        if fp == N - 1:
            UL += ns
        # --- nasal branch: nostril radiation, then the delay-free inward sweep to the port -----
        for m in range(M):
            nfr[m] = mun2 * nf[m]
        npp = nfr[M - 1]
        npm = nb0 * npp + nb1 * nx1 - na1 * ny1
        nx1 = npp
        ny1 = npm
        UN = sAn[M - 1] * (npp - npm)
        nbl = npm
        for m in range(M - 2, -1, -1):
            am = va if m == 0 else An[m]
            sam = sva if m == 0 else sAn[m]
            am1 = An[m + 1]
            k = (am - am1) / (am + am1)
            c = 2.0 * sam * sAn[m + 1] / (am + am1)
            nf[m + 1] = c * nfr[m] - k * nbl
            nbl = k * nfr[m] + c * nbl
        # --- oral tract: delay-free left-going sweep, lips -> glottis --------------------------
        bl = pm
        pw = 0.0
        for j in range(N - 2, -1, -1):
            if j == jv - 1:
                # three-port junction at the velum: pharynx | mouth | nasal port
                ap = A[j]
                ao = A[j + 1]
                sj = 2.0 * (sA[j] * fr[j] + sA[j + 1] * bl + sva * nbl) / (ap + ao + va)
                f[j + 1] = sA[j + 1] * sj - bl
                nf[0] = sva * sj - nbl
                bl = sA[j] * sj - fr[j]
            else:
                s = A[j] + A[j + 1]
                k = (A[j] - A[j + 1]) / s
                c = 2.0 * sA[j] * sA[j + 1] / s
                right = c * fr[j] - k * bl
                bl = k * fr[j] + c * bl
                f[j + 1] = right
            if j == fp:
                f[j + 1] += 0.5 * ns * sA[j + 1]
                bl -= 0.5 * ns * sA[j]
            if j == 1:
                pw = (fr[j] + bl) / sA[j]
        # glottis: reflection plus the flow source (Norton source behind the glottal impedance)
        f[0] = _rg * bl + 0.5 * (1.0 + _rg) * ug / sA[0]
        # --- radiation: d/dt of lip + nostril flow, plus the throat-wall hum --------------------
        bufL[n % (dL + 1)] = UL * gL
        bufN[n % (dN + 1)] = UN * gN
        U = bufL[(n + 1) % (dL + 1)] + bufN[(n + 1) % (dN + 1)]
        w_lp += k_wl * (pw - w_lp)             # the throat walls are heavy: 2nd-order low-pass at 250 Hz
        w_lp2 += k_wl * (w_lp - w_lp2)
        w_hp += k_wh * (w_lp2 - w_hp)          # and no DC
        if diff_out:
            out[n] = (U - u_prev) + wall_gain * (w_lp2 - w_hp)
        else:
            out[n] = U
        u_prev = U
    return out


# glottal pulse shape (fractions of the period) and source gains
TP, TN = 0.42, 0.14        # Rosenberg opening / closing phase: open quotient 0.56, fairly sharp closure
ASP_GAIN = 10 ** (-15.2 / 20)   # aspiration flow per unit `ah`: ah = 1 is ~0 dB re the vowel
WALL_GAIN = 0.04           # throat-wall radiation: the voice bar sits ~27 dB under the vowel
FRIC_HP = 1000.0           # frication / burst noise: 2nd-order high-pass (Hz); the low-pass is per place


def run_tube(tracks, fs, n_out, n_sections, length_cm, jitter=0.004, shimmer=0.03, seed=7, ext_src=None,
             diff_out=True, mu=None, mun=None):
    """Run the waveguide on a tracks dict (see build_tube_tracks) at the tube rate fs."""
    mu = MU if mu is None else mu
    mun = MU_NASAL if mun is None else mun
    jv, An = _nasal_setup(n_sections, length_cm)
    ext = np.zeros(0) if ext_src is None else np.ascontiguousarray(ext_src, dtype=np.float64)
    t = tracks
    flp = t['flp'] if 'flp' in t else np.full(len(t['av']), 6000.0)
    return _kl_core(float(fs), float(CR), int(n_out), np.ascontiguousarray(t['logA']), t['vel'], t['f0'], t['av'],
                    t['ah'], t['af'], t['fpos'].astype(np.int64), flp, t['rg'], An, int(jv), float(mu),
                    float(mun), TP, TN, float(jitter), float(shimmer), int(seed), ASP_GAIN, WALL_GAIN, FRIC_HP, ext,
                    bool(diff_out))


def static_tracks(areas, dur, f0=130.0, av=1.0, ah=0.0, af=0.0, fpos=-1, rg=None, velum=0.0, ramp=0.02, flp=6000.0):
    """Constant control tracks (a held vowel or consonant posture) for tests and calibration."""
    rg = RG if rg is None else rg
    n = int(math.ceil(dur * CR)) + 2
    env = np.ones(n)
    r = max(1, int(ramp * CR))
    env[:r] = np.linspace(0, 1, r)
    env[-r:] = np.linspace(1, 0, r)
    logA = np.tile(np.log(np.asarray(areas, dtype=np.float64))[:, None], (1, n))
    return dict(logA=logA, vel=np.full(n, float(velum)), f0=np.full(n, float(f0)), av=av * env, ah=ah * env,
                af=af * env, fpos=np.full(n, int(fpos), dtype=np.int64), rg=np.full(n, float(rg)),
                flp=np.full(n, float(flp)))


def render_static(areas, dur=1.0, f0=130.0, length_cm=L_MALE_CM, **kw):
    """Sustain one tract posture: returns (y, fs) at the tube rate. kw -> static_tracks / run_tube."""
    N = len(areas)
    fs = tube_rate(N, length_cm)
    run_kw = {k: kw.pop(k) for k in ('jitter', 'shimmer', 'seed', 'ext_src', 'diff_out', 'mu', 'mun') if k in kw}
    tr = static_tracks(areas, dur, f0=f0, **kw)
    return run_tube(tr, fs, int(dur * fs), N, length_cm, **run_kw), fs


# --- articulation: phoneme timeline -> area and source tracks ---------------------------------------
# place of articulation as a fraction of tract length from the glottis (velar is context-dependent)
PLACE_FRAC = {'labial': 1.0, 'labiodental': 1.0, 'dental': 0.93, 'alveolar': 0.88, 'postalveolar': 0.82,
              'palatal': 0.74}
# how far a constriction gesture spreads along the tract (Gaussian sigma, cm at 17.5 cm)
PLACE_SIGMA_CM = {'labial': 0.45, 'labiodental': 0.45, 'dental': 0.5, 'alveolar': 0.55, 'postalveolar': 0.7,
                  'palatal': 0.9, 'velar': 0.9}
FRIC_AREA = {'labiodental': 0.15, 'dental': 0.18, 'alveolar': 0.08, 'postalveolar': 0.15, 'palatal': 0.2,
             'labial': 0.15, 'velar': 0.2}   # constriction area of a fricative (cm^2)
SIBILANT = ('alveolar', 'postalveolar')    # noise from the jet hitting the teeth, one section downstream
# noise source colour: 2nd-order low-pass corner (Hz) of the turbulence source, by place
FRIC_LP = {'alveolar': 9000.0, 'postalveolar': 5500.0, 'labiodental': 8000.0, 'dental': 8000.0,
           'palatal': 5000.0, 'labial': 6000.0, 'velar': 4000.0}
BURST_LP = {'labial': 2500.0, 'alveolar': 7000.0, 'velar': 2500.0, 'postalveolar': 5000.0, 'dental': 7000.0,
            'labiodental': 3000.0, 'palatal': 4000.0}
# Source-level calibration (measured with static postures on an AH substrate): the noise gain per
# place that makes af = 1 come out at 0 dB re a sustained AH at unit voicing, so CONSONANTS'
# fric_level / burst_level read as output level re the vowel. Palatal/velar fricatives are estimates.
FRIC_GAIN = {k: 10 ** (v / 20) for k, v in {'alveolar': -24.5, 'postalveolar': -22.0, 'labiodental': -18.3,
                                             'dental': -18.2, 'palatal': -21.5, 'labial': -18.3,
                                             'velar': -13.5}.items()}
BURST_GAIN = {k: 10 ** (v / 20) for k, v in {'labial': -7.1, 'alveolar': -19.1, 'velar': -1.0,
                                              'postalveolar': -18.5, 'dental': -18.5, 'labiodental': -7.0,
                                              'palatal': -9.5}.items()}
# Source-tract interaction, aerodynamically: a narrow oral constriction raises the pressure in the
# mouth and starves the glottis, so voicing scales with the transglottal pressure fraction
# A_c^2 / (A_g^2 + A_c^2) (glottis and constriction as orifices in series; A_c = narrowest oral
# area + velopharyngeal port). Without it the full-strength pulses pump the high-Q back cavity
# while a stop is still opening and the first cycles of the vowel ring up to +5 dB.
AERO_AG = 0.12             # effective glottal area while voicing (cm^2)
AERO_FLOOR = 0.25          # voicing that survives a complete closure (walls expand; heard as the voice bar)
ASP_DB = -17.0             # aspiration after a voiceless stop release (VOT), dB re the vowel
STOP_CLOSURE_MIN = 0.55    # share of a voiceless stop's planned segment that stays a silent closure
CLOSE_S = 0.03             # closing movement of a stop / nasal / fricative gesture (s)
RELEASE_S = 0.035          # opening movement after a stop or nasal release (s): the CV transition
FRIC_RELEASE_S = 0.025     # opening movement after a fricative (s)
VOWEL_LAG_S = 0.04         # after a consonant, a vowel's area target is reached this far into it
CORONAL = ('dental', 'alveolar', 'postalveolar')
CORONAL_BODY = 0.5         # how far coronal consonants pull the tongue body toward ...
CORONAL_BODY_TARGET = 'IH'  # ... a front vowel's shape (sections behind the tip only; lips untouched)
BURST_BOOST_DB = 6.0       # the tube's voiceless bursts sit this much above CONSONANTS' burst_level
BURST_BOOST_VOICED_DB = 0.0  # voiced stops release less oral pressure: no boost
BURST_MS = 4.0             # burst decay time constant (ms)
HH_DB = -14.0              # /h/, dB re the vowel


def db(x):
    return 10.0 ** (x / 20.0)


def _ramp(n, ta, tb, tc, td):
    """Gesture activation at CR: 0 before ta, raised-cosine rise to 1 at tb, hold, fall to 0 at td."""
    t = np.arange(n) / CR
    w = np.zeros(n)
    up = np.clip((t - ta) / max(tb - ta, 1e-4), 0, 1)
    dn = np.clip((td - t) / max(td - tc, 1e-4), 0, 1)
    w = np.minimum(up, dn)
    return 0.5 - 0.5 * np.cos(np.pi * w)


def _place_index(spec, N, ctx_f2=None):
    """(section index, sigma in sections) of a consonant's constriction."""
    if spec.place == 'velar':
        f2 = 1500.0 if ctx_f2 is None else ctx_f2
        frac = 0.57 + 0.11 * float(np.clip((f2 - 850.0) / 1450.0, 0.0, 1.0))   # fronted before front vowels
    else:
        frac = PLACE_FRAC.get(spec.place, 0.88)
    i = min(N - 1, int(frac * N))
    return i, PLACE_SIGMA_CM.get(spec.place, 0.6) / L_MALE_CM * N


def build_tube_tracks(segs, voice: Voice, t_end, f0_hz, n_sections=20, length_cm=None, areas=None):
    """Control tracks for the waveguide from voicebox's segment plan (see plan_segments).

    Coarticulation is Ohman's: vowels and sonorants set area targets for a smooth tongue
    "substrate" (interpolated through obstruents, smoothed in log-area with voice.smooth_ms);
    obstruents and nasals are constriction gestures laid on top of it at their place of
    articulation. A gesture blends the area (linearly) toward its constriction area with a
    Gaussian spatial profile and a raised-cosine time course, and the narrowest of all wins,
    so the formant transitions into and out of consonants come from the tube, not from loci.
    Returns control tracks at CR: logA (N, n), vel (port area), f0, av, ah, af, fpos, flp, rg,
    plus n_sections, length_cm and fs. `av` is the voicing actually applied (for visemes).
    """
    N = n_sections
    L = length_cm or tract_length(voice.vtl)
    areas = areas or vowel_areas(N, voice.vtl)
    n = int(math.ceil(t_end * CR)) + 2
    logT = np.full((N, n), np.nan)
    av = np.zeros(n)
    ah = np.zeros(n)
    af = np.zeros(n)
    rg = np.full(n, RG)
    vel_w = np.zeros(n)
    fpos = np.full(n, -1, dtype=np.int64)
    flp = np.full(n, 6000.0)
    gestures = []      # (section, sigma_sections, log target area, activation)
    bursts = []        # (frame, level, junction, place)
    aspirates = []     # (i0, i1, role): /h/ takes the shape of its vowel
    breath = db(voice.breath)
    cg = voice.consonant_gain_db
    rate = voice.consonant_rate

    def idx(t):
        return int(round(t * CR))

    def la(ph):
        return np.log(areas[ph])

    spills = []        # (i0, i1, level): aspiration a voiceless stop carries into a devoiced sonorant
    bodies = []        # (i0, i1, section): coronal consonants front the tongue body behind the tip
    for si, g in enumerate(segs):
        i0, i1 = max(0, idx(g['t0'])), min(n, idx(g['t1']))
        if i1 <= i0:
            continue
        t0, t1 = g['t0'], g['t1']
        ph = g['ph']
        vel = g.get('vel', 1.0)
        if ph in VOWELS:
            # after a consonant the tongue and lips reach the vowel's target a little into the
            # vowel (the CV transition); until then the substrate interpolates from the consonant
            prev = segs[si - 1] if si > 0 else None
            lag = 0
            if prev is not None and prev['ph'] not in VOWELS and prev['t1'] > g['t0'] - 0.03:
                lag = min(int(VOWEL_LAG_S * CR), int(0.3 * (i1 - i0)))
            if ph in DIPHTHONGS:
                a, b, frac = DIPHTHONGS[ph]
                x = np.linspace(0, 1, i1 - i0)
                w = np.clip((x - frac) / max(1e-3, 1 - frac), 0, 1)
                w = 0.5 - 0.5 * np.cos(np.pi * w)
                logT[:, i0 + lag:i1] = (la(a)[:, None] * (1 - w) + la(b)[:, None] * w)[:, lag:]
            else:
                logT[:, i0 + lag:i1] = la(ph)[:, None]
            av[i0:i1] = vel
            ah[i0:i1] = breath * vel
            if ph == 'NM':                  # hummed nucleus: lips shut, velum down
                gestures.append((N - 1, PLACE_SIGMA_CM['labial'] / L_MALE_CM * N, math.log(CLOSED),
                                 _ramp(n, t0 - CLOSE_S, t0, t1, t1 + RELEASE_S)))
                vel_w = np.maximum(vel_w, _ramp(n, t0 - 0.08, t0, t1, t1 + 0.05))
                av[i0:i1] = vel * db(-3.0)
                ah[i0:i1] = 0.0
            continue
        spec = CONSONANTS[ph]
        role = g.get('role', 'onset')
        ctx = g.get('next_f') if role == 'onset' else g.get('prev_f')
        ctx_f2 = ctx[1] if ctx is not None else None
        ic, sig = _place_index(spec, N, ctx_f2)
        if spec.place in CORONAL and spec.kind in ('stop', 'nasal', 'fricative', 'affricate'):
            bodies.append((i0, i1, ic))
        if spec.kind == 'stop':
            # the plan's stop segment holds closure + VOT; keep at least STOP_CLOSURE_MIN of it
            # silent, and let the rest of the VOT devoice a following liquid/glide (as in "cr")
            dur = i1 - i0
            vot = spec.vot * rate if role == 'onset' else 0.0
            n_vot_all = int(vot * CR)
            n_vot = min(n_vot_all, int(dur * (1.0 - STOP_CLOSURE_MIN)))
            ir = i0 + max(1, dur - n_vot)            # release
            tr_ = ir / CR
            nxt = segs[si + 1] if si + 1 < len(segs) else None
            if (n_vot_all > n_vot and nxt is not None and nxt['ph'] in CONSONANTS and nxt.get('role') == 'onset'
                    and CONSONANTS[nxt['ph']].kind in ('liquid', 'glide')):
                j0 = idx(nxt['t0'])
                j1 = min(idx(nxt['t1']), j0 + int(0.8 * (idx(nxt['t1']) - j0)), j0 + n_vot_all - n_vot)
                spills.append((j0, j1, db(ASP_DB) * vel))
            gestures.append((ic, sig, math.log(CLOSED), _ramp(n, t0 - CLOSE_S, t0, tr_, tr_ + RELEASE_S)))
            if spec.voiced:
                av[i0:i1] = vel                  # the aerodynamic factor turns this into the voice bar
            else:
                av[i0:i1] = 0.0
                rg[max(0, i0 - 10):i1] = RG_SPREAD
            if n_vot > 0:
                ah[ir:i1] = db(ASP_DB) * vel
            boost = BURST_BOOST_VOICED_DB if spec.voiced else BURST_BOOST_DB
            lvl = spec.burst_level + boost - (3.0 if role == 'coda' else 0.0) + cg
            bursts.append((ir, db(lvl) * vel * BURST_GAIN.get(spec.place, 1.0), ic, spec.place))
        elif spec.kind == 'affricate':
            dur = i1 - i0
            ir = i0 + max(1, int(dur * 0.35))
            tr_ = ir / CR
            gestures.append((ic, sig, math.log(CLOSED), _ramp(n, t0 - CLOSE_S, t0, tr_, tr_ + 0.025)))
            gestures.append((ic, sig, math.log(FRIC_AREA.get(spec.place, 0.15)),
                             _ramp(n, tr_ - 0.005, tr_ + 0.005, t1 - 0.01, t1 + 0.02)))
            jn = min(N - 1, ic + 1)
            af[ir:i1] = db(spec.fric_level + cg) * vel * FRIC_GAIN.get(spec.place, 1.0)
            fpos[ir:min(n, i1 + 20)] = jn
            flp[ir:min(n, i1 + 20)] = FRIC_LP.get(spec.place, 6000.0)
            bursts.append((ir, db(spec.burst_level + cg) * vel * BURST_GAIN.get(spec.place, 1.0), ic, spec.place))
            av[i0:i1] = vel if spec.voiced else 0.0
            if not spec.voiced:
                rg[max(0, i0 - 10):i1] = RG_SPREAD
        elif spec.kind == 'fricative':
            gestures.append((ic, sig, math.log(FRIC_AREA.get(spec.place, 0.15)),
                             _ramp(n, t0 - CLOSE_S, t0 + 0.01, t1 - 0.01, t1 + FRIC_RELEASE_S)))
            jn = min(N - 1, ic + 1) if spec.place in SIBILANT else ic
            af[i0:i1] = db(spec.fric_level + cg) * vel * FRIC_GAIN.get(spec.place, 1.0)
            fpos[max(0, i0 - 20):min(n, i1 + 20)] = jn
            flp[max(0, i0 - 20):min(n, i1 + 20)] = FRIC_LP.get(spec.place, 6000.0)
            av[i0:i1] = vel if spec.voiced else 0.0      # reduced by the constriction (aerodynamics)
            if not spec.voiced:
                rg[i0:i1] = RG_SPREAD
        elif spec.kind == 'aspirate':
            ah[i0:i1] = db(HH_DB) * vel
            av[i0:i1] = 0.0
            rg[i0:i1] = RG_OPEN
            aspirates.append((i0, i1, role))
        elif spec.kind == 'nasal':
            gestures.append((ic, sig, math.log(CLOSED), _ramp(n, t0 - CLOSE_S, t0, t1, t1 + RELEASE_S)))
            vel_w = np.maximum(vel_w, _ramp(n, t0 - 0.09, t0 - 0.01, t1, t1 + 0.06))
            av[i0:i1] = db(spec.av_level) * vel
        else:                                   # liquid / glide: a tongue target of its own
            key = ph if ph in areas else 'AX'
            logT[:, i0:i1] = la(key)[:, None]
            av[i0:i1] = db(spec.av_level) * vel
            ah[i0:i1] = breath * vel * 0.5

    for j0, j1, lvl in spills:                  # devoiced sonorant after an aspirated stop
        av[j0:j1] = 0.0
        ah[j0:j1] = lvl
        rg[j0:j1] = RG_SPREAD
    # /h/ is the following (or, in a coda, the preceding) vowel with an open glottis
    valid = ~np.isnan(logT[0])
    for i0, i1, role in aspirates:
        if role == 'onset':
            j = np.flatnonzero(valid[i1:])
            src = i1 + j[0] if len(j) else None
        else:
            j = np.flatnonzero(valid[:i0])
            src = j[-1] if len(j) else None
        if src is not None:
            logT[:, i0:i1] = logT[:, src:src + 1]
    # substrate: interpolate through obstruents, then smooth (coarticulation)
    valid = ~np.isnan(logT[0])
    if not np.any(valid):
        logT[:] = la('AX')[:, None]
    else:
        vi = np.flatnonzero(valid)
        for i in range(N):
            logT[i] = np.interp(np.arange(n), vi, logT[i, vi])
    # the tongue tip can only reach the ridge with the body forward: that is where the ~1.8 kHz
    # alveolar F2 locus comes from, and moving back out of it after the release IS the F2
    # transition (the tip opening alone is over in ~10 ms once the lips are rounded)
    jv = _nasal_setup(N, L)[0]
    front = la(CORONAL_BODY_TARGET) if CORONAL_BODY_TARGET in areas else None
    if front is not None and CORONAL_BODY > 0:
        for i0, i1, ic in bodies:
            b0 = max(0, jv - 3)
            if ic > b0:
                logT[b0:ic, i0:i1] = (1 - CORONAL_BODY) * logT[b0:ic, i0:i1] + CORONAL_BODY * front[b0:ic, None]
    sig_t = max(0.5, voice.smooth_ms / 2.0 * CR / 1000.0)
    logA = gaussian_filter1d(logT, sig_t, axis=1, mode='nearest')
    # constriction gestures: the narrowest wins
    out = logA.copy()
    x = np.arange(N)
    for ic, sig, lac, w in gestures:
        act = np.flatnonzero(w > 1e-4)
        if not len(act):
            continue
        a, b = act[0], act[-1] + 1
        prof = np.exp(-0.5 * ((x - ic) / max(sig, 0.3)) ** 2)[:, None] * w[None, a:b]
        # linear-area blend: a released articulator opens the area roughly linearly in time
        # (fast acoustically at first, then a 30-40 ms formant transition), and a closing one
        # only seals at the very end of its movement
        cand = np.log((1.0 - prof) * np.exp(logA[:, a:b]) + prof * math.exp(lac))
        out[:, a:b] = np.minimum(out[:, a:b], cand)
    logA = out
    # source tracks
    sig_a = max(0.5, voice.amp_smooth_ms * CR / 1000.0)
    av = gaussian_filter1d(av, sig_a, mode='nearest')
    a_c = np.exp(np.min(logA[jv:], axis=0)) + VELUM_OPEN * vel_w
    av = av * (AERO_FLOOR + (1.0 - AERO_FLOOR) * a_c ** 2 / (AERO_AG ** 2 + a_c ** 2))
    ah = gaussian_filter1d(ah, sig_a, mode='nearest')
    af = gaussian_filter1d(af, sig_a * 2.5, mode='nearest')
    rg = gaussian_filter1d(rg, 4.0, mode='nearest')
    for (ir, lvl, jn, place) in bursts:
        k = np.arange(min(n - ir, 14))
        if not len(k):
            continue
        af[ir:ir + len(k)] = np.maximum(af[ir:ir + len(k)], lvl * np.exp(-k / BURST_MS))
        fpos[ir:ir + len(k)] = jn
        flp[ir:ir + len(k)] = BURST_LP.get(place, 5000.0)
    f0 = f0_hz[:n] if len(f0_hz) >= n else np.pad(f0_hz, (0, n - len(f0_hz)), mode='edge')
    return dict(logA=np.ascontiguousarray(logA), vel=VELUM_OPEN * vel_w, f0=np.asarray(f0, dtype=np.float64),
                av=av, ah=ah, af=af, fpos=fpos, flp=flp, rg=rg, n_sections=N, length_cm=L, fs=tube_rate(N, L))


def formant_tracks(tr, every=10, n_formants=4):
    """F1..F4 of the tract over time (chain matrices every `every` control frames, interpolated)."""
    logA, vel = tr['logA'], tr['vel']
    n = logA.shape[1]
    frames = np.arange(0, n, every)
    F = np.full((n_formants, len(frames)), np.nan)
    for k, i in enumerate(frames):
        F[:, k] = tube_formants(np.exp(logA[:, i]), tr['length_cm'], n_formants, velum_area=vel[i])
    out = np.empty((n_formants, n))
    for j in range(n_formants):
        ok = np.isfinite(F[j])
        out[j] = np.interp(np.arange(n), frames[ok], F[j, ok]) if np.any(ok) else np.nan
    return out


# --- renderers -------------------------------------------------------------------------------------
def era_voice(vtl=0.0, **kw):
    """The 1961 performance: stiff pitch (no vibrato, quick glides), a steady buzzy source."""
    v = Voice(name='bell_labs_1961', vtl=vtl, breath=-40.0, jitter=0.003, shimmer=0.02, vib_depth=0.0,
              portamento=0.025, overshoot=0.0, scoop=0.0, drift=2.0, f1_tuning=False, smooth_ms=22.0,
              amp_smooth_ms=4.0, consonant_rate=1.1, consonant_gain_db=0.0)
    return v.but(**kw) if kw else v


def to_rate(y, fs_in, fs_out):
    """Band-limited resampling between arbitrary rates (polyphase, rational approximation)."""
    fr = Fraction(float(fs_out) / float(fs_in)).limit_denominator(2000)
    return resample_poly(y, fr.numerator, fr.denominator)


def render_tube(sung, t_end=None, vtl=0.0, n_sections=20, voice=None, with_formants=True):
    """Sing a `Sung` score through the waveguide. Returns (y, fs, segs, tracks); y is the raw
    radiated pressure at the tube's own rate fs = N c / (2 L) (20 kHz for 20 male sections)."""
    voice = voice or era_voice(vtl)
    if t_end is None:
        t_end = max(s.t_off for s in sung.syls) + 0.3
    segs = plan_segments(sung.syls, voice)
    f0 = sung_f0(sung.notes, voice, t_end)
    L = tract_length(voice.vtl)
    fs = tube_rate(n_sections, L)
    tr = build_tube_tracks(segs, voice, t_end, f0, n_sections, L)
    y = run_tube(tr, fs, int(t_end * fs), n_sections, L, jitter=voice.jitter, shimmer=voice.shimmer,
                 seed=voice.seed)
    if with_formants:
        tr['F'] = formant_tracks(tr)
    return y, fs, segs, tr


def bell_labs_1961_clean(sung, t_end=None, vtl=0.0, n_sections=20, voice=None):
    """The tube alone, without the era's DAC and tape: band-limited to 48 kHz, normalised."""
    from .eras import SR, _norm
    y, fs, segs, tr = render_tube(sung, t_end, vtl, n_sections, voice)
    return _norm(to_rate(y, fs, SR)), segs, tr


def bell_labs_1961(sung, t_end=None, vtl=0.0, n_sections=20, voice=None):
    """Bell Labs, 1961, as a physical model: Kelly-Lochbaum tube at fs = N c / (2 L), delivered
    at 10 kHz through a 12-bit converter onto tape (the Bell Labs recording's finishing chain)."""
    from .eras import SR, _norm, highpass, lowpass, quantize, small_room, tape, zoh_upsample
    y, fs, segs, tr = render_tube(sung, t_end, vtl, n_sections, voice)
    y = to_rate(y, fs, 10000)                  # the 1961 DAC rate
    y = quantize(_norm(y, -1), 12)
    y = zoh_upsample(y, 10000)
    y = lowpass(y, SR, 4800, 4)
    y = tape(y, SR, wow=0.003, flutter=0.001, hiss_db=-44, lp=4600)
    y = small_room(y, SR, mix=0.18, size=0.25)
    y = highpass(y, SR, 120)
    return _norm(y), segs, tr

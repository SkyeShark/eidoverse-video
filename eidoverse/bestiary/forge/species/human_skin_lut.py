"""The human's SKIN LUTs (HUMAN_PLAN §5.1, H3): skin colour from pigment concentrations, the transmission through thin
tissue, and the pre-integrated diffuse, each from ONE two-layer spectral model fitted to measured skin, packed as small
tables that the forge's look-dev twin (species/human_lookdev.py) and the TSL skin node (engine_test/human_skin.js) read
the same way (the parity rule, DESIGN.md's quality gates: a map judged in look-dev reads the same in the engine).

THE MODEL (per wavelength, coefficients in cm^-1; every constant sourced):
  * EPIDERMIS: a thin absorbing layer of thickness d_e whose diffuse light crosses it twice (Jacques 1998: "total photon
    path taken as twice the thickness"):  T2 = exp(-2 mua_epi d_e),  mua_epi = f_mel mua_mel + (1 - f_mel) mua_base;
      mua_mel(nm)  = 6.6e11 nm^-3.33                     (melanosome interior; Jacques 1998, "Skin optics", OMLC News)
      mua_base(nm) = 0.244 + 85.3 exp(-(nm - 154) / 66.2) (bloodless tissue; same)
      f_mel        the melanosome volume fraction: light adults 1.3-6.3 %, moderately pigmented 11-16 %, darkly
                   pigmented 18-43 % (same)
  * DERMIS: a semi-infinite scattering layer: mua_derm = f_blood C mua_blood + (1 - f_blood) mua_base (Jacques 1998),
      mua_blood    whole blood at 150 g Hb / L: 2.303 e(nm) 150 / 64500 with e = S e_HbO2 + (1 - S) e_Hb, Prahl's
                   tabulated molar extinction (OMLC, compiled from Gratzer and Kollias), oxygen saturation S (Donner
                   et al. 2008 and Jimenez et al. 2010 fix 0.75, as restated in arXiv:2501.01980 §3.2; FITTED here)
      C            the PIGMENT PACKAGING of blood confined to vessels of radius R_v: C = (1 - exp(-2 mua_blood R_v)) /
                   (2 mua_blood R_v) (the vessel correction of Svaasand et al. 1995 / van Veen et al. 2002, as used in
                   diffuse-reflectance skin fits): the Soret band (415 nm) flattens about 5x at R_v 10 um, the Q bands
                   (542 / 576 nm) by ~20 %, the red not at all; without it no one blood fraction fits both bands (the
                   first fit, 10-29 23:4x: the model's Soret dip too deep, its Q-band W too shallow, a* -2.6 short)
      musp_derm    (2e5 nm^-1.5 + 2e12 nm^-4) x SCAT (Mie fibres + Rayleigh; Jacques 1998; SCAT fitted)
    and its total diffuse reflectance by the diffusion approximation with an index-matched-for-skin boundary (eta 1.4):
      R_d = (a/2) (1 + exp(-(4/3) A sqrt(3 (1 - a)))) exp(-sqrt(3 (1 - a))),  a = musp / (mua + musp),
      A = (1 + F_dr) / (1 - F_dr), F_dr = -1.440 / eta^2 + 0.710 / eta + 0.668 + 0.0636 eta   (Jensen et al. 2001)
  * the DIFFUSE ALBEDO (what the shader's diffuse term takes) is R_body = T2 R_d; a spectrophotometer reading with the
    specular component included (NIST's 8 deg / hemispherical, Xiao's d / 8 SCI) adds the surface's Fresnel reflection,
    F0 = ((1.4 - 1) / (1.4 + 1))^2 = 0.028:  R_SCI = F0 + (1 - F0) R_body.
  * the global constants (d_e, SCAT, the melanin exponent's departure from 3.33 if any) are FITTED once to the NIST
    reference set (Cooksey, Allen and Tsai 2017, J Res NIST 122:26: 100 volunteers' inner right forearms, 8 deg / h,
    250-2500 nm at 3 nm; publicly available, nist.gov licensing), and each subject's (f_mel, f_blood) with them: the
    sourced RANGES are those fitted fractions (work/bestiary/human/h3/material/m01_skin_fit.py, skin_fit.json).

COLOUR: CIE 1931 2 deg colour matching functions (CVRL, 1 nm) under CIE D65 (CIE 15.2 Table 1.1), both already the
house's data (work/bestiary/research/colour_work/lit, sources in research/refs/colour/sources.md); XYZ normalised to a
perfect white's Y = 1; linear Rec.709 / sRGB primaries (IEC 61966-2-1) for the albedo; CIELAB against the computed white.

THE PACKS (write_packs / read_packs; float16 on disk, as the GPU samples them):
  * ALBEDO LUT, LUT_N x LUT_N, RGBA: u = sqrt(f_mel / MEL_MAX), v = sqrt(f_blood / BLOOD_MAX) at texel centres; RGB the
    linear Rec.709 diffuse albedo, A the epidermis's one-pass band transmittance's luminance (unused by the shader).
  * TRANS table, TRANS_N x 2, RGBA: row 0 E_c(u) the epidermis's one-pass transmittance per channel; row 1 k_c(v) the
    dermis's effective extinction per mm (sqrt(3 mua (mua + musp)) averaged over each channel's band): thin tissue of
    thickness t (mm) between two epidermal layers transmits E_c^2 exp(-k_c t).
  * PREINT table, PRE_N x PRE_N, RGBA: x = N.L * 0.5 + 0.5, y = curvature (1 / mm) / CURV_MAX at texel centres; RGB the
    pre-integrated diffuse (Penner & Borshukov 2011, GPU Pro 2) of the dermis's own radial diffusion profile (the
    dipole of Jensen et al. 2001 at the fitted dermis, the median subject's blood), per channel: the irradiance factor
    that replaces max(N.L, 0).
  The sampler twin (sample2d) reads them as the GPU does: bilinear between texel centres, clamped at the edges, the
  float16 values.
"""
import json
import math
import os
import re

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
RESEARCH = os.path.join(ROOT, 'work', 'bestiary', 'research')
CMF_CSV = os.path.join(RESEARCH, 'colour_work', 'lit', 'ciexyz31_1.csv')
D65_DAT = os.path.join(RESEARCH, 'colour_work', 'lit', 'ciesid65.dat')
OPTICS = os.path.join(RESEARCH, 'human_web', 'skin_optics')
HB_HTML = os.path.join(OPTICS, 'prahl_hemoglobin_summary.html')
NIST_TXT = os.path.join(OPTICS, 'nist_skinrefl_v3.txt')

ETA = 1.4                      # skin's relative index (the stratum corneum ~1.4-1.55; Jensen 2001 and three's skin ior)
F0 = ((ETA - 1.0) / (ETA + 1.0)) ** 2      # 0.0278: the surface's normal-incidence Fresnel reflectance
S_O2 = 0.75                    # dermal blood oxygen saturation (Donner 2008, Jimenez 2010)
HB_GL = 150.0                  # g Hb per litre of whole blood (Prahl)
HB_MW = 64500.0                # g / mol (Prahl)
LAM = np.arange(380.0, 781.0, 5.0)         # the colour integration grid (nm)

# the FIT's global constants (m01_skin_fit.py fills these from skin_fit.json; the defaults are Jacques 1998's, S 0.75,
# vessels 10 um). SCAT stays 1 (Jacques's dermis scattering: 49.9 cm^-1 at 500 nm, Jacques 2013's generic skin 46.0):
# a semi-infinite layer's reflectance depends only on mua / musp, so a free SCAT trades against the absorptions (the
# second fit ran SCAT to its bound of 10 with the blood fractions 10x up); the absolute scattering is kept from the
# literature because the transmission and the profile's width need it, and the bloodless absorptions are fitted as
# scales instead: derm_base (the dermis's) and epi_base (the epidermis's; it also stands in for its other weak blue
# absorbers, carotenoids and the like, which the model does not name)
FIT = dict(d_e_um=60.0, scat=1.0, mel_exp=3.33, s_o2=S_O2, vessel_um=10.0, derm_base=1.0, epi_base=1.0, scat_b=None)
# scat_b: None = Jacques 1998's two-term dermis scattering; a number = a power law (nm / 500)^-scat_b through the same
# value at 500 nm (49.9 cm^-1 x SCAT): the scattering's wavelength slope is the least certain of the model's shapes

# the LUT axes
LUT_N = 64
MEL_MAX = 1.00                 # f_mel at u = 1: a volume fraction's own limit (the fitted model's darkest real skins,
#                                ITA about -75, sit near 0.8: m01's extrapolation past NIST's darkest, ITA -21.5)
BLOOD_MAX = 0.20               # f_blood at v = 1 (lips and flush; beyond-human tints come from uniforms, not here)
TRANS_N = 64
PRE_N = 64
CURV_MAX = 1.0                 # 1 / mm at y = 1 (a 1 mm radius: the ear's rim, the alar groove)


# ------------------------------------------------------------------------------------------------------------ data
_CACHE = {}


def cie():
    """(lam 1 nm 360-830, xbar, ybar, zbar, D65 on the same grid) from the house's CIE tables"""
    if 'cie' not in _CACHE:
        c = np.loadtxt(CMF_CSV, delimiter=',')
        d = [float(s) for s in open(D65_DAT, encoding='latin-1') if s.strip() and not s.startswith(';')]
        dl = np.arange(300.0, 300.0 + 5.0 * len(d), 5.0)
        assert abs(np.interp(560.0, dl, d) - 100.0) < 1e-6, 'D65 table misread'
        lam = c[:, 0]
        _CACHE['cie'] = (lam, c[:, 1], c[:, 2], c[:, 3], np.interp(lam, dl, d))
    return _CACHE['cie']


def hb_table():
    """Prahl's molar extinction (cm^-1 / M): (nm, HbO2, Hb), 250-1000 nm at 2 nm, parsed from the saved page as text"""
    if 'hb' not in _CACHE:
        t = open(HB_HTML, encoding='latin-1').read()
        pre = re.findall(r'<pre>(.*?)</pre>', t, re.S)[-1]
        rows = [r.split() for r in pre.splitlines()]
        a = np.array([[float(x) for x in r] for r in rows if len(r) == 3 and r[0].replace('.', '').isdigit()])
        assert a.shape == (376, 3) and a[0, 0] == 250.0 and a[-1, 0] == 1000.0, 'Prahl table misread'
        _CACHE['hb'] = a
    return _CACHE['hb']


def nist():
    """the NIST reference set: (nm 250-2500 at 3 nm, R (100, n) the subjects' averages of their three scans,
    R3 (100, 3, n) the three scans), reflectance factor (8 deg / h, specular included)"""
    if 'nist' not in _CACHE:
        lines = open(NIST_TXT, encoding='latin-1').read().splitlines()
        hdr = [i for i, s in enumerate(lines) if s.startswith('Wavelength')][0]
        rows = []
        for s in lines[hdr + 1:]:
            f = s.split(',')
            if not f or not f[0].strip():
                continue
            rows.append([float(x) if x.strip() else np.nan for x in f])
        a = np.array(rows)
        lam = a[:, 0]
        vals = a[:, 1:401]
        assert vals.shape[1] == 400, f'NIST table: {vals.shape[1]} columns'
        R3 = np.stack([vals[:, 4 * k:4 * k + 3].T for k in range(100)])
        R = vals[:, 3::4].T
        _CACHE['nist'] = (lam, R, R3)
    return _CACHE['nist']


# ---------------------------------------------------------------------------------------------------------- optics
def mua_mel(lam, mel_exp=None):
    """melanosome absorption (cm^-1): Jacques 1998, 6.6e11 nm^-3.33; mel_exp != 3.33 keeps the value at 550 nm and bends
    the slope (a fitted departure, reported as such)"""
    e = FIT['mel_exp'] if mel_exp is None else mel_exp
    return 6.6e11 * 550.0 ** -3.33 * (np.asarray(lam, float) / 550.0) ** -e


def mua_base(lam):
    """bloodless tissue (cm^-1): Jacques 1998"""
    return 0.244 + 85.3 * np.exp(-(np.asarray(lam, float) - 154.0) / 66.2)


def mua_blood(lam, s_o2=None):
    """whole blood (cm^-1) at 150 g Hb / L and saturation s_o2 (Prahl's table, linear between its 2 nm rows)"""
    s = FIT['s_o2'] if s_o2 is None else s_o2
    h = hb_table()
    e = s * np.interp(lam, h[:, 0], h[:, 1]) + (1.0 - s) * np.interp(lam, h[:, 0], h[:, 2])
    return 2.303 * e * HB_GL / HB_MW


def mua_blood_packed(lam, s_o2=None, vessel_um=None):
    """blood's EFFECTIVE absorption in the dermis per unit blood fraction: mua_blood x the packaging factor C"""
    v = FIT['vessel_um'] if vessel_um is None else vessel_um
    mb = mua_blood(lam, s_o2)
    x = 2.0 * mb * v * 1e-4
    return mb * np.where(x > 1e-6, (1.0 - np.exp(-x)) / np.maximum(x, 1e-12), 1.0)


def musp_derm(lam, scat=None, scat_b='fit'):
    """dermis reduced scattering (cm^-1): Jacques 1998's Mie fibres + Rayleigh x SCAT, or (scat_b a number) a power
    law through the same value at 500 nm"""
    s = FIT['scat'] if scat is None else scat
    b = FIT.get('scat_b') if scat_b == 'fit' else scat_b
    lam = np.asarray(lam, float)
    if b is None:
        return s * (2e5 * lam ** -1.5 + 2e12 * lam ** -4.0)
    m500 = 2e5 * 500.0 ** -1.5 + 2e12 * 500.0 ** -4.0
    return s * m500 * (lam / 500.0) ** -b


def _A():
    fdr = -1.440 / ETA ** 2 + 0.710 / ETA + 0.668 + 0.0636 * ETA
    return (1.0 + fdr) / (1.0 - fdr)


def rd_semi(mua, musp):
    """the diffusion approximation's total diffuse reflectance of a semi-infinite layer (Jensen et al. 2001)"""
    a = musp / (mua + musp)
    s = np.sqrt(3.0 * (1.0 - a))
    return 0.5 * a * (1.0 + np.exp(-4.0 / 3.0 * _A() * s)) * np.exp(-s)


def body_reflectance(lam, f_mel, f_blood, fit=None):
    """the diffuse albedo spectrum R_body = T2 R_d (broadcasts f_mel, f_blood against lam on the last axis)"""
    F = dict(FIT, **(fit or {}))
    lam = np.asarray(lam, float)
    fm = np.asarray(f_mel, float)[..., None]
    fb = np.asarray(f_blood, float)[..., None]
    mb = mua_base(lam)
    mua_e = fm * mua_mel(lam, F['mel_exp']) + (1.0 - fm) * mb * F['epi_base']
    t2 = np.exp(-2.0 * mua_e * F['d_e_um'] * 1e-4)
    mua_d = fb * mua_blood_packed(lam, F['s_o2'], F['vessel_um']) + (1.0 - fb) * mb * F['derm_base']
    return t2 * rd_semi(mua_d, musp_derm(lam, F['scat'], F.get('scat_b')))


def sci(r_body):
    """a reading with the specular component included (NIST 8 / h, Xiao d / 8 SCI)"""
    return F0 + (1.0 - F0) * r_body


# ---------------------------------------------------------------------------------------------------------- colour
M_XYZ_TO_RGB = np.array([[3.2404542, -1.5371385, -0.4985314],
                         [-0.9692660, 1.8760108, 0.0415560],
                         [0.0556434, -0.2040259, 1.0572252]])


def xyz(lam, R):
    """reflectance spectra (..., len(lam)) -> XYZ under D65, 2 deg, a perfect white's Y = 1 (R interpolated onto 1 nm,
    held flat past its ends)"""
    cl, xb, yb, zb, S = cie()
    lam = np.asarray(lam, float)
    R = np.asarray(R, float)
    m = (cl >= 380) & (cl <= 780)
    cl, xb, yb, zb, S = cl[m], xb[m], yb[m], zb[m], S[m]
    if R.ndim == 1:
        Ri = np.interp(cl, lam, R)
    else:
        flat = R.reshape(-1, R.shape[-1])
        Ri = np.stack([np.interp(cl, lam, r) for r in flat]).reshape(R.shape[:-1] + (len(cl),))
    k = 1.0 / np.sum(S * yb)
    return k * np.stack([np.sum(S * Ri * xb, -1), np.sum(S * Ri * yb, -1), np.sum(S * Ri * zb, -1)], -1)


def white():
    return xyz(LAM, np.ones_like(LAM))


def lab(XYZ):
    w = white()
    t = np.asarray(XYZ, float) / w
    d = 6.0 / 29.0
    f = np.where(t > d ** 3, np.cbrt(t), t / (3 * d * d) + 4.0 / 29.0)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def lin_rgb(XYZ):
    return np.asarray(XYZ, float) @ M_XYZ_TO_RGB.T


def ita(L):
    """the individual typology angle (deg) of CIELAB colours: atan((L* - 50) / b*) (Chardon et al. 1991)"""
    L = np.asarray(L, float)
    return np.degrees(np.arctan2(L[..., 0] - 50.0, L[..., 2]))


def de76(a, b):
    return np.linalg.norm(np.asarray(a, float) - np.asarray(b, float), axis=-1)


def band_weights():
    """per linear sRGB channel, the weight of each wavelength (1 nm, 380-780) in that channel's response to an equal-
    energy D65 spectrum: S(l) [M_XYZ_TO_RGB @ cmf(l)]_c clipped at 0 and normalised (for band-averaging optics that are
    not reflectances: the transmission and the diffusion profile)"""
    cl, xb, yb, zb, S = cie()
    m = (cl >= 380) & (cl <= 780)
    cmf = np.stack([xb[m], yb[m], zb[m]], -1)
    w = np.clip(S[m, None] * (cmf @ M_XYZ_TO_RGB.T), 0.0, None)
    return cl[m], w / w.sum(0, keepdims=True)


# --------------------------------------------------------------------------------------------- packs and samplers
def axes_u(n=LUT_N):
    u = (np.arange(n) + 0.5) / n
    return u, MEL_MAX * u * u


def axes_v(n=LUT_N):
    v = (np.arange(n) + 0.5) / n
    return v, BLOOD_MAX * v * v


def albedo_lut(n=LUT_N, fit=None):
    """(n, n, 4) float: rows v (blood), columns u (melanin); RGB linear Rec.709 albedo, A the epidermis one-pass
    transmittance's luminance"""
    _, fm = axes_u(n)
    _, fb = axes_v(n)
    FM, FB = np.meshgrid(fm, fb)
    R = body_reflectance(LAM, FM, FB, fit)
    rgb = lin_rgb(xyz(LAM, R))
    E = trans_epi(fm, fit)
    lum = E @ np.array([0.2126, 0.7152, 0.0722])
    out = np.zeros((n, n, 4))
    out[..., :3] = rgb
    out[..., 3] = lum[None, :]
    return out


def trans_epi(f_mel, fit=None):
    """the epidermis's ONE-PASS diffuse transmittance per linear sRGB channel: exp(-2 mua_epi d_e)^(1/2) band-averaged
    (the factor 2 of T2 is the diffuse path of one crossing, both ways counted once each)"""
    F = dict(FIT, **(fit or {}))
    cl, w = band_weights()
    fm = np.asarray(f_mel, float)[..., None]
    mua_e = fm * mua_mel(cl, F['mel_exp']) + (1.0 - fm) * mua_base(cl) * F['epi_base']
    t1 = np.exp(-mua_e * F['d_e_um'] * 1e-4)
    return t1 @ w


def k_derm(f_blood, fit=None):
    """the dermis's effective extinction (1 / mm) per channel: sqrt(3 mua (mua + musp)) band-averaged in transmittance
    at 2 mm (the ear's scale), i.e. -ln(sum_l w_c(l) exp(-sigma_tr(l) 2 mm)) / 2 mm"""
    F = dict(FIT, **(fit or {}))
    cl, w = band_weights()
    fb = np.asarray(f_blood, float)[..., None]
    mua = fb * mua_blood_packed(cl, F['s_o2'], F['vessel_um']) + (1.0 - fb) * mua_base(cl) * F['derm_base']
    mus = musp_derm(cl, F['scat'], F.get('scat_b'))
    s_tr = np.sqrt(3.0 * mua * (mua + mus)) * 0.1          # cm^-1 -> mm^-1
    t = 2.0
    return -np.log(np.exp(-s_tr * t) @ w) / t


def trans_table(n=TRANS_N, fit=None):
    _, fm = axes_u(n)
    _, fb = axes_v(n)
    out = np.zeros((2, n, 4))
    out[0, :, :3] = trans_epi(fm, fit)
    out[1, :, :3] = k_derm(fb, fit)
    out[:, :, 3] = 1.0
    return out


def radial_profile(r_mm, f_blood, fit=None):
    """the dermis's radial diffusion profile R(r) per linear sRGB channel (the dipole of Jensen et al. 2001, band-
    averaged with band_weights), normalised so 2 pi int R r dr = 1 per channel"""
    F = dict(FIT, **(fit or {}))
    cl, w = band_weights()
    mua = (f_blood * mua_blood_packed(cl, F['s_o2'], F['vessel_um']) +
           (1.0 - f_blood) * mua_base(cl) * F['derm_base']) * 0.1                # mm^-1
    mus = musp_derm(cl, F['scat'], F.get('scat_b')) * 0.1
    st = mua + mus
    ap = mus / st
    s_tr = np.sqrt(3.0 * mua * st)
    zr = 1.0 / st
    zv = zr * (1.0 + 4.0 / 3.0 * _A())
    r = np.asarray(r_mm, float)[:, None]
    dr = np.sqrt(r * r + zr * zr)
    dv = np.sqrt(r * r + zv * zv)
    Rl = ap / (4 * np.pi) * (zr * (s_tr * dr + 1) * np.exp(-s_tr * dr) / dr ** 3 +
                             zv * (s_tr * dv + 1) * np.exp(-s_tr * dv) / dv ** 3)
    Rc = Rl @ w
    norm = 2 * np.pi * np.trapezoid(Rc * r, r[:, 0], axis=0)
    return Rc / norm


def preint_table(f_blood, n=PRE_N, fit=None, n_theta=721):
    """Penner & Borshukov's pre-integrated diffuse: for a sphere of radius rho = 1 / curvature lit at angle theta, the
    profile-weighted ring integral of the clamped cosine, D_c = int cos+(theta + x) R_c(2 rho sin(x / 2)) dx /
    int R_c(2 rho sin(x / 2)) dx over x in (-pi, pi]; at curvature 0 exactly max(cos theta, 0)"""
    x = (np.arange(n) + 0.5) / n
    ndl = x * 2.0 - 1.0
    th = np.arccos(np.clip(ndl, -1, 1))
    y = (np.arange(n) + 0.5) / n
    curv = y * CURV_MAX
    xs = np.linspace(-np.pi, np.pi, n_theta)
    out = np.zeros((n, n, 4))
    out[..., 3] = 1.0
    rr = np.linspace(0.0, 60.0, 6001)
    prof = radial_profile(rr, f_blood, fit)
    for j, c in enumerate(curv):
        rho = 1.0 / max(c, 1e-6)
        d = np.abs(2.0 * rho * np.sin(xs / 2.0))
        Rw = np.stack([np.interp(d, rr, prof[:, k], right=0.0) for k in range(3)], -1)
        for i, t in enumerate(th):
            cosp = np.clip(np.cos(t + xs), 0.0, None)
            out[j, i, :3] = np.trapezoid(cosp[:, None] * Rw, xs, axis=0) / np.trapezoid(Rw, xs, axis=0)
    return out


def sample2d(tab, x, y):
    """the GPU's bilinear lookup of a (rows, cols, ch) table at normalised (x across columns, y across rows), texel
    centres at (i + 0.5) / n, clamped to the edge (three's ClampToEdge + LinearFilter)"""
    h, w = tab.shape[:2]
    fx = np.clip(np.asarray(x, float) * w - 0.5, 0.0, w - 1.0)
    fy = np.clip(np.asarray(y, float) * h - 0.5, 0.0, h - 1.0)
    x0 = np.floor(fx).astype(int)
    y0 = np.floor(fy).astype(int)
    x1 = np.minimum(x0 + 1, w - 1)
    y1 = np.minimum(y0 + 1, h - 1)
    ax = (fx - x0)[..., None]
    ay = (fy - y0)[..., None]
    a = tab[y0, x0] * (1 - ax) + tab[y0, x1] * ax
    b = tab[y1, x0] * (1 - ax) + tab[y1, x1] * ax
    return a * (1 - ay) + b * ay


def pigment_uv(f_mel, f_blood):
    """the albedo LUT's coordinates of pigment fractions (the TSL node's mapping, exactly)"""
    return np.sqrt(np.clip(np.asarray(f_mel, float) / MEL_MAX, 0, 1)), \
        np.sqrt(np.clip(np.asarray(f_blood, float) / BLOOD_MAX, 0, 1))


def write_packs(out_dir, albedo, trans, preint, meta):
    """the three tables as float16 RGBA (the GPU's half floats), plus a JSON of their layout and provenance"""
    os.makedirs(out_dir, exist_ok=True)
    files = {}
    for name, t in (('albedo', albedo), ('trans', trans), ('preint', preint)):
        h16 = np.ascontiguousarray(t.astype(np.float16))
        p = os.path.join(out_dir, f'skin_lut_{name}.f16')
        h16.tofile(p)
        files[name] = dict(file=os.path.basename(p), rows=int(t.shape[0]), cols=int(t.shape[1]), channels=4)
    m = dict(meta, files=files, axes=dict(
        albedo='u = sqrt(f_mel / MEL_MAX) across columns, v = sqrt(f_blood / BLOOD_MAX) across rows; RGB linear '
               'Rec.709 diffuse albedo (no surface specular), A epidermis one-pass transmittance luminance',
        trans='row 0: E_c(u) epidermis one-pass transmittance; row 1: k_c(v) dermis extinction per mm; thin tissue '
              'of t mm transmits E^2 exp(-k t)',
        preint='x = N.L * 0.5 + 0.5 across columns, y = curvature / CURV_MAX across rows (curvature in 1/mm); RGB the '
               'pre-integrated diffuse irradiance factor'),
        MEL_MAX=MEL_MAX, BLOOD_MAX=BLOOD_MAX, CURV_MAX=CURV_MAX, F0=F0, ETA=ETA, FIT=FIT)
    with open(os.path.join(out_dir, 'skin_lut.json'), 'w', encoding='utf-8') as f:
        json.dump(m, f, indent=1)
    return m


def read_packs(out_dir):
    m = json.load(open(os.path.join(out_dir, 'skin_lut.json'), encoding='utf-8'))
    T = {}
    for name, d in m['files'].items():
        a = np.fromfile(os.path.join(out_dir, d['file']), dtype=np.float16)
        T[name] = a.reshape(d['rows'], d['cols'], d['channels']).astype(np.float32)
    return T, m

"""Calibration against the reference skin study (work/bestiary/research/REF_SKIN_STUDY.md §0, §8-§10).

Two jobs:
  * the RELIEF DRIVERS the colour stack needs, at the study's physical scales: AO_local (the study's hp16: ao minus
    its masked blur) and convexity (curvature over its p95 |.|, clamped +-3) in a fine and a mid band;
  * the REPORT every material pass prints beside the study's bars: albedo luminance and saturation by zone, the
    countershading ratios, roughness percentiles, ln L octave RMS and normal XY octave RMS.

The study measured at 800-2800 px/m and quoted pixels; here every scale is in millimetres, converted per set through
its texel density. Its octaves are masked Difference-of-Gaussian bands whose edges are the wavelengths each Gaussian
halves (5.34 sigma). Blurs run on the GPU when CuPy is there.
"""
import numpy as np

try:
    import cupy as cp
    from cupyx.scipy import ndimage as cnd
except Exception:                                  # pragma: no cover - CPU fallback
    cp = None


def mblur(x, m, sigma_px):
    """masked Gaussian (normalised convolution) of the 2-D x over the mask m"""
    if cp is not None:
        X = cp.asarray(x, dtype=cp.float32)
        Mk = cp.asarray(m, dtype=cp.float32)
        num = cnd.gaussian_filter(X * Mk, sigma_px, mode='constant')
        den = cnd.gaussian_filter(Mk, sigma_px, mode='constant')
        return cp.asnumpy(num / cp.maximum(den, 1e-6))
    from scipy import ndimage as nd
    num = nd.gaussian_filter(x * m, sigma_px, mode='constant')
    den = nd.gaussian_filter(m.astype(np.float32), sigma_px, mode='constant')
    return num / np.maximum(den, 1e-6)


def _p95(x, sel):
    """p95 |x| over the texels sel (1.0 where there are none)"""
    return float(np.percentile(np.abs(x[sel]), 95)) if sel.any() else 1.0


def _unit_p95(x, p95):
    """x over its scale p95, clamped +-3"""
    return np.clip(x / max(p95, 1e-12), -3.0, 3.0)


def skin_texels(drivers, cov):
    """the covered texels that carry NO cyborg id (forge/growth.py ID_RANGES['cyborg'] = 64-95) in either of the bake's
    two packed ids (voxel.lab_pack: id0 | id1 << 8 | w << 16): the skin (a growth's texels stay in); cov itself on a
    bake without material ids"""
    code = drivers.get('mat') if hasattr(drivers, 'get') else None
    if code is None:
        return cov
    code = np.asarray(code, np.int64)
    id0, id1 = code & 255, (code >> 8) & 255
    cyb = ((id0 >= 64) & (id0 <= 95)) | ((id1 >= 64) & (id1 <= 95))
    return cov & ~cyb


def _conv_bands(drivers, px_per_m, fine_sigma_mm, mid_sigma_mm):
    """the coverage, its float mask and the curvature's masked blurs at the fine and the mid sigma (mm)"""
    cov = np.asarray(drivers['normal'])[..., 3] > 0
    m = cov.astype(np.float32)
    mm = lambda s: s / 1000.0 * px_per_m
    cu = np.asarray(drivers['curvature'], np.float32)
    return cov, m, mblur(cu, m, mm(fine_sigma_mm)), mblur(cu, m, mm(mid_sigma_mm))


def conv_scale(drivers, px_per_m, fine_sigma_mm=0.6, mid_sigma_mm=3.0):
    """THE CONVEXITY NORMALISER'S SCALES, measured: p95 |curvature| blurred at the fine and at the mid sigma, over the
    skin texels of these drivers (skin_texels). A BASE measures them ONCE (t11's plain run) and records them beside its
    maps (write_conv_record); every look on that base takes them from that record (read_conv_record, conv_set) and
    never measures its own texels: a look or a graft changes the skin only where it is applied
    (patches/infra1_convexity.md). Returns relief_drivers' scale: dict(conv, conv_mid (the p95s, 1/m), px_per_m,
    fine_sigma_mm, mid_sigma_mm, skin_texels)"""
    cov, m, fine, mid = _conv_bands(drivers, px_per_m, fine_sigma_mm, mid_sigma_mm)
    skin = skin_texels(drivers, cov)
    return dict(conv=_p95(fine, skin), conv_mid=_p95(mid, skin), px_per_m=float(px_per_m),
                fine_sigma_mm=float(fine_sigma_mm), mid_sigma_mm=float(mid_sigma_mm), skin_texels=int(skin.sum()))


def relief_drivers(drivers, px_per_m, ao_sigma_mm=6.0, fine_sigma_mm=0.6, mid_sigma_mm=3.0, scale=None):
    """image-order float32 maps: ao_local (ao - its masked blur at ao_sigma), conv (fine) and conv_mid, each
    convexity divided by its scale and clamped +-3 (positive on bumps; study §0). scale: conv_scale's dict, the
    BASE's own (p95 |.| = 1 over its skin texels) or, on a look, its base's record (conv_set), checked against this
    call's density and sigmas; None measures it here over these drivers' skin texels (skin_texels: a cyborg's plates
    and feed, hard edges at many times the skin's curvature, set no skin's scale): a set that is its own base"""
    cov, m, fine, mid = _conv_bands(drivers, px_per_m, fine_sigma_mm, mid_sigma_mm)
    mm = lambda s: s / 1000.0 * px_per_m
    ao = np.asarray(drivers['ao'], np.float32)
    ao_local = (ao - mblur(ao, m, mm(ao_sigma_mm))) * m
    if scale is None:
        skin = skin_texels(drivers, cov)
        p_fine, p_mid = _p95(fine, skin), _p95(mid, skin)
    else:
        # the density within a relative 1e-9 (t11 applies 1.0 / texel, 3150.442910340359, where the density itself is
        # 3150.4429103403595: one density, the last digit apart), the sigmas exactly
        tol = dict(px_per_m=1e-9)
        bad = [f'{k} {scale.get(k, "(not given)")} (applied at {v})'
               for k, v in (('px_per_m', px_per_m), ('fine_sigma_mm', fine_sigma_mm), ('mid_sigma_mm', mid_sigma_mm))
               if k not in scale or not abs(float(scale[k]) - float(v)) <= tol.get(k, 0.0) * abs(float(v))]
        if bad:
            raise ConvRecordError('calib.relief_drivers: the convexity scale given was measured at ' + ', '.join(bad) +
                                  ': a scale holds only at the density and the sigmas it was measured at')
        p_fine, p_mid = float(scale['conv']), float(scale['conv_mid'])
    conv = _unit_p95(fine, p_fine) * m
    conv_mid = _unit_p95(mid, p_mid) * m
    return dict(ao_local=ao_local.astype(np.float32), conv=conv.astype(np.float32),
                conv_mid=conv_mid.astype(np.float32))


# ---- THE CONVEXITY NORMALISER, FROZEN PER BASE (patches/infra1_convexity.md): the base's scales recorded once beside
# its maps, with its identity; every look on that base reads them and never measures its own texels
CONV_RECORD = 'conv_scale.json'


class ConvRecordError(RuntimeError):
    """a look cannot take its base's convexity scales (the record is missing, unreadable, not as its base wrote it, or
    belongs to another base: a look never re-measures its own texels), or a scale is applied at another density or
    sigma than it was measured at (or names none)"""


def conv_record_sha1(rec):
    """a record's own check: the sha1 of its identity and its numbers (base and sets as JSON, sorted keys, no spaces);
    write_conv_record stores it, read_conv_record refuses a record whose content no longer gives it"""
    import hashlib
    import json
    body = json.dumps(dict(base=rec.get('base'), sets=rec.get('sets')), sort_keys=True, separators=(',', ':'))
    return hashlib.sha1(body.encode('utf-8')).hexdigest()


def arrays_sha1(src):
    """the identity of a dict of arrays, or of an .npz file's CONTENT (its zip members carry timestamps, so the file's
    bytes are no identity): sha1 over the sorted names, each with its dtype, its shape and its bytes"""
    import hashlib
    h = hashlib.sha1()
    z = np.load(src, allow_pickle=False) if isinstance(src, str) else None
    try:
        for k in (sorted(z.files) if z is not None else sorted(src)):
            a = np.ascontiguousarray(np.asarray(z[k] if z is not None else src[k]))
            h.update(f'{k}|{a.dtype.str}|{a.shape}|'.encode('utf-8'))
            h.update(a.tobytes())
    finally:
        if z is not None:
            z.close()
    return h.hexdigest()


def write_conv_record(folder, low_sha1, sets, log=print):
    """the BASE's record, written once beside its maps (folder/CONV_RECORD): its identity (base: the sha1 of its low's
    arrays and of each set's drivers: the high as its bake read it on that low, the very texels the scales were
    measured on) and each set's conv_scale numbers. sets: {set name: conv_scale's dict + drivers: that set's drivers
    sha1 (arrays_sha1)}"""
    import json
    import os
    rec = dict(record=('the convexity normaliser of this BASE, frozen: every look on it normalises its skin by these '
                       'scales, never by its own texels (forge/calib.py conv_scale / read_conv_record; '
                       'patches/infra1_convexity.md)'),
               base=dict(low=low_sha1, **{f'drivers_{k}': v['drivers'] for k, v in sets.items()}),
               sets={k: {kk: vv for kk, vv in v.items() if kk != 'drivers'} for k, v in sets.items()})
    rec['sha1'] = conv_record_sha1(rec)                     # the record's own check (read_conv_record)
    path = os.path.join(folder, CONV_RECORD)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        json.dump(rec, f, indent=1)
    log(f'[calib] the base records its convexity scales: {path} (low {low_sha1[:12]}; ' + '; '.join(
        f'{k}: p95 fine {v["conv"]:.3f}, mid {v["conv_mid"]:.3f} 1/m over {v["skin_texels"]} skin texels'
        for k, v in sets.items()) + ')')
    return rec


def read_conv_record(base_dir, low_sha1, why='this run'):
    """a LOOK's convexity scales: its base's record (base_dir/CONV_RECORD), proven to be that base's before a texel is
    painted: readable, and as its base wrote it (its sha1, conv_record_sha1: an altered number or a dropped key is
    caught here); the look's low must be the record's (a look is laid on its base's own low), and so must the folder's
    current low and drivers (a base re-made after its record no longer owns it). Raises ConvRecordError otherwise,
    saying what to do: a look NEVER re-measures its own texels. Returns the record (conv_set: one set's scales)"""
    import json
    import os
    path = os.path.join(base_dir, CONV_RECORD)
    head = (f"{why} is a LOOK on the base in {base_dir}: its skin's convexity is normalised by that base's FROZEN "
            f"scales, never by its own texels (patches/infra1_convexity.md)")
    if not os.path.isfile(path):
        raise ConvRecordError(f"{head}; but its record {path} does not exist. Run the plain base's t11 in that folder "
                              f"first, or point BESTIARY_BASE at the folder of the base this look is built on")
    try:
        with open(path, encoding='utf-8') as f:
            rec = json.load(f)
    except ValueError as e:
        raise ConvRecordError(f"{head}; but its record {path} cannot be read ({e}). Re-run the base's t11 there") from e
    if not isinstance(rec, dict) or rec.get('sha1') != conv_record_sha1(rec):
        raise ConvRecordError(f"{head}; but its record {path} is not as its base wrote it (its sha1 does not match its "
                              f"identity and numbers: altered, or not written by calib.write_conv_record). Re-run the "
                              f"base's t11 there")
    b = rec.get('base', {})
    if b.get('low') != low_sha1:
        raise ConvRecordError(f"{head}; but its record {path} belongs to ANOTHER BASE: the record's low is "
                              f"{str(b.get('low'))[:12]}, this look's low is {low_sha1[:12]} (a look is laid on its "
                              f"base's own low). Point BESTIARY_BASE at this look's base")
    now = dict(low=arrays_sha1(os.path.join(base_dir, 'low.npz')))
    for k in rec.get('sets', {}):
        now[f'drivers_{k}'] = arrays_sha1(os.path.join(base_dir, f'drivers_{k}.npz'))
    moved = [k for k in now if b.get(k) != now[k]]
    if moved:
        raise ConvRecordError(f"{head}; but its record {path} belongs to ANOTHER BASE than the one now in that folder ("
                              + '; '.join(f'{k}: recorded {str(b.get(k))[:12]}, in the folder {now[k][:12]}'
                                          for k in moved)
                              + "): the base was re-made after its record was written. Re-run the base's t11 there")
    return rec


def conv_set(rec, set_name):
    """one texture set's scales from a base's record (read_conv_record), for relief_drivers' scale= (which checks the
    density and the sigmas they were measured at against its own)"""
    s = rec.get('sets', {}).get(set_name)
    if s is None:
        raise ConvRecordError(f"the base's convexity record has no {set_name!r} set (it holds "
                              f"{sorted(rec.get('sets', {}))}): a look takes every set's scales from its base")
    return dict(s)


def octave_rms(x, m, px_per_m, sigmas=(0.5, 1, 2, 4, 8, 16, 32, 64, 128)):
    """the RMS of each DoG band between successive sigmas (px) inside m (eroded 3 px, as the study did); x is (H, W)
    or (H, W, k) (a vector band's length). Returns [(lambda_lo_mm, lambda_hi_mm, rms)]"""
    from scipy import ndimage as nd
    xs = x if x.ndim == 3 else x[..., None]
    inner = nd.binary_erosion(m > 0.5, iterations=3)
    if not inner.any():
        return []
    G = [np.stack([mblur(xs[..., c], m, s) for c in range(xs.shape[-1])], -1) for s in sigmas]
    out = []
    for k in range(len(sigmas) - 1):
        band = G[k] - G[k + 1]
        r2 = (band ** 2).sum(-1)[inner]
        lo = 5.34 * sigmas[k] / px_per_m * 1000.0
        hi = 5.34 * sigmas[k + 1] / px_per_m * 1000.0
        out.append((lo, hi, float(np.sqrt(r2.mean()))))
    return out


def srgb_to_lin(c):
    """8-bit sRGB -> linear: the house's exact EOTF (forge/material.py srgb_eotf), as the engine decodes the albedo"""
    from .material import srgb_eotf
    return srgb_eotf(np.asarray(c, np.float32) / 255.0)


def lin_to_srgb8(L):
    """linear -> sRGB in 0..255 (float): the house's exact OETF (forge/material.py srgb_oetf)"""
    from .material import srgb_oetf
    return srgb_oetf(L) * 255.0


def half_level8(L_bar):
    """half of one 8-bit sRGB level at the linear value L_bar, from the exact EOTF there: the linear width of the
    one-level code interval centred on L_bar's own code (srgb_oetf(L_bar) * 255 +- 0.5), halved. The albedo is 8-bit
    sRGB, so a value clamped at L_bar decodes up to about this far either side of it"""
    from .material import srgb_eotf, srgb_oetf
    s = float(srgb_oetf(L_bar))
    return 0.5 * float(srgb_eotf(min(s + 0.5 / 255.0, 1.0)) - srgb_eotf(max(s - 0.5 / 255.0, 0.0)))


# the study's bars for the octopus (§10a: the salamander creature's wet shading with the squid creature's cephalopod colour logic),
# with its COLOUR bars replaced where the real animal disagrees (research/REAL_OCTOPUS_COLOUR.md §1, §1b: a squid hook
# is not an octopus sucker, and the study-T countershading rule lands between two different real tissues). A dict value
# is per texture set: the head set (mantle, head, webs; its oral zone is the pale crown) and the arms set (the arms'
# oral faces keep their pigment)
OCTOPUS_BARS = dict(
    L_envelope=(0.010, 0.65),                   # §9 R2: final albedo clamp for skin
    L_p50=(0.035, 0.27),                        # §8: study T creatures are mid-dark to mid (the real animal agrees)
    aboral_S=dict(head=(0.34, 0.50), arms=(0.52, 0.62)),        # real: mantle 0.34-0.45, arms 0.54-0.61
    ventral_ratio=dict(head=(1.4, 2.6), arms=(1.3, 1.65)),      # oral/aboral L: pale crown; arms' oral faces
    ventral_S_ratio=dict(head=(0.10, 0.30), arms=(0.78, 1.0)),  # ... S: crown x0.16-0.19; arms' faces x0.79-1.0
    disc_S=(0.04, 0.09), disc_ratio=(2.1, 3.5),  # sucker discs: near-neutral, x2.1-3.5 the aboral L (24 suckers)
    rim_ratio=(0.33, 0.44), rim_S=(0.20, 0.40),  # the rim band: darker and pigmented, x0.33-0.44 the disc's L
    rough=((0.08, 0.12), (0.14, 0.20), (0.29, 0.40)),   # §9 R5 wet amphibian p5 / p50 / p95
    lnL_a10=(0.05, 0.10), lnL_beta=(0.30, 0.38),         # §10a mottling: RMS(lambda) = a (lambda / 10 mm)^beta
    nrm_fine=(0.03, 0.06), nrm_mid=(0.07, 0.10),         # §10a normal XY RMS: 1-3 mm and 7-20 mm
)


def _flag(v, lo, hi):
    # ASCII: Windows consoles redirected to a file encode cp1252 (t11 died printing a check mark)
    return 'ok' if lo <= v <= hi else ('LOW' if v < lo else 'HIGH')


def report(tag, maps, cov, px_per_m, bars=OCTOPUS_BARS, log=print):
    """maps: image-order uint8 albedo (sRGB), normal (GL), orm, masks (thin, ventral, sucker, prand); cov: the set's
    coverage. Prints the numbers beside the bars and returns them as a dict"""
    from scipy import ndimage as nd
    cov = nd.binary_erosion(cov, iterations=2)
    lin = srgb_to_lin(maps['albedo'])
    L = 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]
    s8 = maps['albedo'].astype(np.float32) / 255.0
    mx, mn = s8.max(-1), s8.min(-1)
    S = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    ven = maps['masks'][..., 1].astype(np.float32) / 255.0
    suck = maps['masks'][..., 2].astype(np.float32) / 255.0
    kind = tag.split()[0]
    bar = lambda k: bars[k][kind] if isinstance(bars[k], dict) else bars[k]
    rng = lambda b: f'{b[0]}-{b[1]}'
    # the sucker mask packs rim 1, disc 0.66, cup 0.33 (octopus_skin), so the parts separate by value
    zones = dict(aboral=cov & (ven < 0.2) & (suck < 0.2), oral=cov & (ven > 0.8) & (suck < 0.2),
                 disc=cov & (suck > 0.58) & (suck < 0.74), rim=cov & (suck > 0.9))
    out = {}
    log(f'[calib] {tag}: albedo L linear p5/p50/p95 (sRGB8 p50), S sRGB p50, by zone')
    for z, sel in zones.items():
        if sel.sum() < 100:
            continue
        p5, p50, p95 = np.percentile(L[sel], [5, 50, 95])
        out[z] = dict(L=(p5, p50, p95), S=float(np.median(S[sel])), n=int(sel.sum()))
        extra = ''
        if z == 'aboral':
            extra = (f'  p50 {_flag(p50, *bar("L_p50"))} (bar {rng(bar("L_p50"))}), S '
                     f'{_flag(out[z]["S"], *bar("aboral_S"))} (bar {rng(bar("aboral_S"))})')
        if z == 'disc':
            extra = f'  S {_flag(out[z]["S"], *bar("disc_S"))} (bar {rng(bar("disc_S"))})'
            if 'aboral' in out:
                rd = p50 / max(out['aboral']['L'][1], 1e-6)
                extra += f', L x{rd:.2f} the aboral {_flag(rd, *bar("disc_ratio"))} (bar x{rng(bar("disc_ratio"))})'
        if z == 'rim':
            extra = f'  S {_flag(out[z]["S"], *bar("rim_S"))} (bar {rng(bar("rim_S"))})'
            if 'disc' in out:
                rr = p50 / max(out['disc']['L'][1], 1e-6)
                extra += f', L x{rr:.2f} the disc {_flag(rr, *bar("rim_ratio"))} (bar x{rng(bar("rim_ratio"))})'
        log(f'    {z:7s} {p5:.3f}/{p50:.3f}/{p95:.3f} ({lin_to_srgb8(p50):.0f}), S {out[z]["S"]:.2f}, '
            f'{sel.mean() * 100 / max(cov.mean(), 1e-9):.0f} % of the set{extra}')
    if 'aboral' in out and 'oral' in out:
        rL = out['oral']['L'][1] / max(out['aboral']['L'][1], 1e-6)
        rS = out['oral']['S'] / max(out['aboral']['S'], 1e-6)
        log(f'    countershading: oral/aboral L x{rL:.2f} {_flag(rL, *bar("ventral_ratio"))} (bar x'
            f'{rng(bar("ventral_ratio"))}), S x{rS:.2f} {_flag(rS, *bar("ventral_S_ratio"))} (bar x'
            f'{rng(bar("ventral_S_ratio"))})')
        out['ratios'] = (rL, rS)
    lo_e, hi_e = bars['L_envelope']
    # judged at the texture's own precision (the lead's call, patches/infra1_srgb.md): a texel fails only when it lies
    # more than HALF AN 8-BIT LEVEL outside a bar (that level's size from the exact EOTF at the bar, half_level8). A grey
    # the skin clamps AT a bar never fails by its rounding; a colour's three channels round apart and can land a hair
    # past (at most 1.0013 half levels: 6 of the 15,064,023 codes an L <= 0.65 colour encodes to; none at the floor)
    tol_lo, tol_hi = half_level8(lo_e), half_level8(hi_e)
    Lc = L[cov]
    n_out = int(((Lc < lo_e - tol_lo) | (Lc > hi_e + tol_hi)).sum())
    n_half = int(((Lc < lo_e) | (Lc > hi_e)).sum()) - n_out
    out_env = 100.0 * n_out / max(Lc.size, 1)
    log(f'    envelope L {lo_e}-{hi_e}, judged to half an 8-bit level (-{tol_lo:.6f} / +{tol_hi:.6f}): {out_env:.2f} % '
        f'of texels outside (bar 0): {n_out} texels; {n_half} more within half a level of a bar')
    out['envelope'] = dict(outside=n_out, within_half_level=n_half, tol=(tol_lo, tol_hi))
    rgh = maps['orm'][..., 1].astype(np.float32) / 255.0
    skin = cov & (suck < 0.2)
    if skin.any():
        r5, r50, r95 = np.percentile(rgh[skin], [5, 50, 95])
        b = bars['rough']
        log(f'    roughness (skin) p5/p50/p95 {r5:.2f}/{r50:.2f}/{r95:.2f}  {_flag(r5, *b[0])} {_flag(r50, *b[1])} '
            f'{_flag(r95, *b[2])} (bars {b[0][0]}-{b[0][1]} / {b[1][0]}-{b[1][1]} / {b[2][0]}-{b[2][1]})')
        out['rough'] = (r5, r50, r95)
    m = cov.astype(np.float32)
    oct_l = octave_rms(np.log(np.maximum(L, 1e-4)), m, px_per_m)
    a_lo, a_hi = bars['lnL_a10']
    b_lo, b_hi = bars['lnL_beta']
    log('    ln L octave RMS (band mm: measured vs bar a (lambda/10)^beta):')
    rows = []
    for lo, hi, r in oct_l:
        lam = np.sqrt(lo * hi)
        if lam < 1.5 or lam > 250:
            continue
        x = lam / 10.0
        blo = a_lo * x ** (b_hi if x < 1 else b_lo)
        bhi = a_hi * x ** (b_lo if x < 1 else b_hi)
        rows.append((lam, r))
        log(f'      {lo:6.1f}-{hi:6.1f} mm: {r:.3f}  {_flag(r, blo, bhi)} (bar {blo:.3f}-{bhi:.3f})')
    out['lnL_octaves'] = rows
    n = maps['normal'][..., :2].astype(np.float32) / 127.5 - 1.0
    oct_n = octave_rms(n, m, px_per_m)
    log('    normal XY octave RMS (band mm: measured; bars 1-3 mm '
        f'{bars["nrm_fine"][0]}-{bars["nrm_fine"][1]}, 7-20 mm {bars["nrm_mid"][0]}-{bars["nrm_mid"][1]}):')
    nrows = []
    for lo, hi, r in oct_n:
        lam = np.sqrt(lo * hi)
        tag_b = ''
        if 1.0 <= lam <= 3.0:
            tag_b = f'  {_flag(r, *bars["nrm_fine"])}'
        elif 7.0 <= lam <= 20.0:
            tag_b = f'  {_flag(r, *bars["nrm_mid"])}'
        nrows.append((lam, r))
        log(f'      {lo:6.1f}-{hi:6.1f} mm: {r:.3f}{tag_b}')
    out['normal_octaves'] = nrows
    return out

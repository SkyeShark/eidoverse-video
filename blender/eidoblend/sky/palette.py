"""Time-of-day palette, cloud presets and the sun/moon paths, numerically identical to the WebGPU sky.

Ported from Eanpa Engine engine/sky_system.js (TOD, todAt, todDisc, PRESETS, setTime). No bpy: the
values here feed both the GLSL baker and the Blender lamps/world, so a frame's light and its sky agree.
Directions are three.js world vectors (Y up); `three_to_blender` converts them for Blender (Z up).
"""
import math

# sun-elevation keyed (degrees): zenith, horizon, sun colour, key intensity, star fade
TOD = (
    dict(el=-18, zen=(0.010, 0.016, 0.055), hor=(0.030, 0.042, 0.10), sun=(0.55, 0.65, 0.95), int=0.00, star=1.00),
    dict(el=-6, zen=(0.022, 0.045, 0.115), hor=(0.190, 0.120, 0.19), sun=(1.00, 0.42, 0.22), int=0.10, star=0.85),
    dict(el=0, zen=(0.070, 0.130, 0.300), hor=(1.000, 0.560, 0.32), sun=(1.00, 0.48, 0.23), int=0.55, star=0.25),
    dict(el=8, zen=(0.160, 0.340, 0.700), hor=(1.000, 0.760, 0.55), sun=(1.00, 0.69, 0.41), int=1.60, star=0.00),
    dict(el=30, zen=(0.150, 0.380, 0.820), hor=(0.620, 0.780, 0.92), sun=(1.00, 0.94, 0.86), int=2.60, star=0.00),
    dict(el=70, zen=(0.110, 0.350, 0.800), hor=(0.600, 0.760, 0.90), sun=(1.00, 1.00, 1.00), int=3.00, star=0.00),
)


def _lerp3(a, b, k):
    return tuple(a[i] + (b[i] - a[i]) * k for i in range(3))


def tod_at(el_deg):
    if el_deg <= TOD[0]['el']:
        return dict(TOD[0])
    if el_deg >= TOD[-1]['el']:
        return dict(TOD[-1])
    for a, b in zip(TOD, TOD[1:]):
        if a['el'] <= el_deg <= b['el']:
            k = (el_deg - a['el']) / (b['el'] - a['el'])
            return dict(el=el_deg, zen=_lerp3(a['zen'], b['zen'], k), hor=_lerp3(a['hor'], b['hor'], k),
                        sun=_lerp3(a['sun'], b['sun'], k), int=a['int'] + (b['int'] - a['int']) * k,
                        star=a['star'] + (b['star'] - a['star']) * k)
    return dict(TOD[2])


DISC_TAPS = 11


def tod_disc(el_deg, r_deg):
    """The palette integrated over a finite-angular-size source (a red giant's ~16 deg radius); 0 = point sun."""
    if not r_deg > 0.05:
        return tod_at(el_deg)
    r_eff = r_deg * max(0.0, min(1.0, (el_deg + r_deg) / r_deg))
    if not r_eff > 0.05:
        return tod_at(el_deg)
    zen, hor, sun = [0.0] * 3, [0.0] * 3, [0.0] * 3
    inten = star = wsum = 0.0
    for i in range(DISC_TAPS):
        t = ((i + 0.5) / DISC_TAPS) * 2 - 1
        w = math.sqrt(max(0.0, 1 - t * t))
        p = tod_at(el_deg + t * r_eff)
        for c in range(3):
            zen[c] += p['zen'][c] * w
            hor[c] += p['hor'][c] * w
            sun[c] += p['sun'][c] * w
        inten += p['int'] * w
        star += p['star'] * w
        wsum += w
    n = 1 / wsum
    return dict(el=el_deg, zen=tuple(v * n for v in zen), hor=tuple(v * n for v in hor),
                sun=tuple(v * n for v in sun), int=inten * n, star=star * n)


# ---- cloud presets (finalMul 0.2 = reference density); the high 2D layer is part of each preset ----
PRESETS = {
    'cumulus': dict(largeT=0.42, largeA=3.0, weatherT=0.30, finalMul=0.20, wScale=1.0, dScale=1.0, start=700, height=520,
                    stretch=(1, 1, 1), lightK=1.0, lightCacheDirect=0,
                    wispOn=0.28, wispScale=0.00125, wispThreshold=0.48, wispStrength=0.70, wispOpacity=1.45, wispFloor=0.0,
                    wispStretch=(0.75, 0.35, 1.65), wispFilament=0.18, wispTint=(1.0, 0.98, 0.94)),
    'stratus': dict(largeT=0.12, largeA=2.0, weatherT=0.08, finalMul=0.16, wScale=0.55, dScale=0.7, start=520, height=170,
                    stretch=(1, 0.7, 1), lightK=0.7, lightCacheDirect=0,
                    wispOn=0.72, wispScale=0.00082, wispThreshold=0.36, wispStrength=0.82, wispOpacity=1.05, wispFloor=0.0,
                    wispStretch=(0.90, 0.28, 1.15), wispFilament=0.04, wispTint=(0.72, 0.79, 0.88)),
    'cirrus': dict(largeT=0.48, largeA=2.0, weatherT=0.34, finalMul=0.0, wScale=1.2, dScale=1.0, start=3400, height=230,
                   stretch=(0.55, 1.1, 1.8), lightK=0.16, lightCacheDirect=0,
                   wispOn=1.0, wispScale=0.00030, wispThreshold=0.43, wispStrength=1.08, wispOpacity=1.00, wispFloor=0.0,
                   wispStretch=(0.052, 0.14, 2.05), wispFilament=1.0, wispTint=(0.98, 0.99, 1.0)),
    'clear': dict(largeT=0.95, largeA=1.0, weatherT=0.95, finalMul=0.00, wScale=1.0, dScale=1.0, start=700, height=520,
                  stretch=(1, 1, 1), lightK=0.0, lightCacheDirect=0,
                  wispOn=0.0, wispScale=0.001, wispThreshold=1.0, wispStrength=0.0, wispOpacity=0.0, wispFloor=0.0,
                  wispStretch=(1, 1, 1), wispFilament=0.0, wispTint=(1, 1, 1)),
}

# preset key -> uniform name (the JS setClouds mapping)
PRESET_UNIFORM = dict(largeT='largeT', largeA='largeA', weatherT='weatherT', finalMul='finalMul', wScale='wScale',
                      dScale='dScale', start='cloudStart', height='cloudHeight', stretch='stretch', lightK='lightK',
                      lightCacheDirect='lightCacheDirect', wispOn='wispOn', wispScale='wispScale',
                      wispThreshold='wispThreshold', wispStrength='wispStrength', wispOpacity='wispOpacity',
                      wispFloor='wispFloor', wispFilament='wispFilament', stormCanopy='stormCanopy',
                      wispStretch='wispStretch', wispTint='wispTint')

CLOUD_SCALAR_KEYS = ('largeT', 'largeA', 'weatherT', 'finalMul', 'wScale', 'dScale', 'cloudStart', 'cloudHeight',
                     'lightK', 'lightCacheDirect', 'wispOn', 'wispScale', 'wispThreshold', 'wispStrength',
                     'wispOpacity', 'wispFloor', 'wispFilament', 'stormCanopy')
CLOUD_VECTOR_KEYS = ('stretch', 'wispStretch', 'wispTint')


def norm3(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


def cross3(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def three_to_blender(v):
    """three.js (x, y, z) -> Blender (x, -z, y)."""
    return (v[0], -v[2], v[1])


def blender_to_three(v):
    """Blender (x, y, z) -> three.js (x, z, -y)."""
    return (v[0], v[2], -v[1])


def arc_az(h, span):
    """Daytime azimuth sweep that closes across the night, so a full day returns to its start (setTime)."""
    w = ((h % 24) + 24) % 24
    if 6 <= w < 18:
        return (w - 12) / 12 * span * math.pi
    n = ((w - 18) + 24) % 24
    return span * math.pi * 0.5 + n / 12 * (2 - span) * math.pi


def sun_moon_at(hours, az_base=1.9, el_max=62.0, az_span=0.9, noon_azimuth=None):
    """(sun_dir, moon_dir, sun_az, sun_el) in three.js world space for a time of day, exactly as setTime."""
    day_k = (hours - 6) / 12
    el = math.sin(day_k * math.pi) * el_max * math.pi / 180
    az = az_base + arc_az(hours, az_span)
    if noon_azimuth is not None:
        az += (noon_azimuth - az_base) * max(0.0, math.sin(day_k * math.pi)) ** 2
    mel = math.sin(((hours + 12 - 6) / 12) * math.pi) * 48 * math.pi / 180
    maz = az_base + math.pi + arc_az(hours + 12, 0.8)
    moon = norm3((math.cos(mel) * math.cos(maz), math.sin(mel), math.cos(mel) * math.sin(maz)))
    sun = norm3((math.cos(el) * math.cos(az), math.sin(el), math.cos(el) * math.sin(az)))
    return sun, moon, az, el

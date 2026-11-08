"""Per-frame weather values the WebGPU update writes to uniforms, as plain functions. No bpy.

rain_light: rain is translucent water, not self-emissive paint, so its radiance follows the live time-of-day palette,
the weather's sun dimming and the lightning (rainLight), and its colour follows the sky's chroma, blue-white in a local
flash (rainColor = litRain x the rain colour override).

cell_gate: rainCellAt, the local cloud supply over a world column: the macro coverage of the sky's weather field at
the upwind source of the drops falling there, through the state's cellLo/cellHi gate, opened fully under a sealed
storm canopy. Drops, splashes, moisture and the ripple gate all read it, so they agree on where it rains.
"""
import math

WATER_BASE = (0.72, 0.78, 0.86)
DISTANT_FLASH_RAIN = (0.82, 0.90, 1.0)


def rain_light(pal, w, storm_canopy, rain_k, flash, flash_d, strike_color, rain_tint=(1, 1, 1)):
    """(rainLight, litRain, rainColor) of one frame. pal = the sky's live palette (zen, hor), w the live weather def."""
    zen, hor = pal['zen'], pal['hor']
    lum = max(0.0, zen[0] * 0.22 + zen[1] * 0.45 + zen[2] * 0.13 + hor[0] * 0.06 + hor[1] * 0.10 + hor[2] * 0.04)
    ambient = max(0.06, min(1.0, lum * 1.35))
    weather_light = 0.32 + max(0.02, float(w.get('sunDim', 1))) * 0.68
    canopy = max(0.0, min(1.0, float(storm_canopy or 0)))
    canopy_rain = canopy * max(0.0, min(1.0, float(rain_k or 0)))
    floor = 0.08 + canopy_rain * 0.14
    light = min(2.4, floor + ambient * weather_light + flash * 1.6 + flash_d * 0.8)
    scene = [zen[i] * 0.58 + hor[i] * 0.42 for i in range(3)]
    peak = max(0.04, *scene)
    tint = [max(0.08, min(1.0, c / peak)) for c in scene]
    local = min(1.0, flash * 1.5)
    distant = min(1.0, flash_d * 0.6)
    lit = []
    for i in range(3):
        sky_tinted = WATER_BASE[i] * (0.68 + tint[i] * 0.32)
        locally = sky_tinted + (strike_color[i] - sky_tinted) * local
        lit.append(locally + (DISTANT_FLASH_RAIN[i] - locally) * distant)
    return light, tuple(lit), tuple(lit[i] * rain_tint[i] for i in range(3))


def _smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def coverage_uv(x3, z3, U):
    """tslCoverage's weather-map UV of a three (x, z) world point: drift-aware, wScale-scaled (repeat-wrapped)."""
    s = -0.00005 * float(U['wScale'])
    d = U['cloudDisplacement']
    return ((z3 - d[2]) * s, (x3 - d[0]) * s)


def upwind_source(x3, y3, z3, wind_vec, fall_speed, fall_mul, cloud_start):
    """The column the drops at (x3, y3, z3) fell from: back along the wind by their fall time from the cloud base."""
    k = max(cloud_start - y3, 0.0) / max(fall_speed * fall_mul, 1.0)
    return x3 - wind_vec[0] * k, z3 - wind_vec[2] * k


def cell_gate(coverage, cell_lo, cell_hi, storm_canopy):
    """smoothstep(cellLo, cellHi, coverage), opened to 1 under a sealed storm canopy."""
    g = _smoothstep(cell_lo, cell_hi, coverage)
    c = max(0.0, min(1.0, storm_canopy))
    return g + (1.0 - g) * c

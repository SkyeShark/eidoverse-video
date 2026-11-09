"""What every part of the four SDF vehicles is made of: the per-material numbers of each example's shade(), as
Principled values, plus the make() options' colour parsing and the presets the sources documented.

Plain Python (no bpy): examples_vehicles.py formats these numbers into its baked surface() GLSL and shading.py builds
the per-part Blender materials from the same table, so the two paths cannot drift apart.

How each engine term became a Principled input (the engine lit its parts by hand: a sun term, a sky term, a mirror
lookup `envR` scaled by a fresnel or a constant, and a Blinn highlight `pow(NdH, k)`):
  * a mirror `envR * F` term is the part's specular reflectance: F0 = F (metallic when F is tinted or above ~0.1, a
    Specular IOR Level when it is a dielectric's 0.04..0.08);
  * the highlight exponent k gives the roughness (k 200+ -> 0.05 or less, 80 -> ~0.1, 24..48 -> 0.4..0.55);
  * an unlit `col = emit * ...` term is emission (linear radiance, Emission Strength 1), its view-dependent core
    kept per pixel in the part materials (Layer Weight), head-on in the baked surface();
  * the hand AO, soft shadow and sky fill are EEVEE's own light now.
"""

from __future__ import annotations

# ------------------------------------------------------------------------------------------------- material ids ---
# each example's #define MAT_* block, as {id: part name}

MODERN_IDS = {0: 'paint', 1: 'glass', 2: 'tire', 3: 'rim', 4: 'chrome', 5: 'head', 6: 'tail', 8: 'plastic'}
CYBER_IDS = {0: 'paint', 1: 'glass', 2: 'tire', 3: 'rim', 4: 'chrome', 5: 'head', 6: 'tail', 8: 'plastic',
             9: 'underglow', 10: 'accent', 11: 'grille', 12: 'badge'}
SLEEK_IDS = {0: 'paint', 1: 'glass', 2: 'tire', 4: 'chrome', 5: 'head', 6: 'tail'}
JET_IDS = {0: 'hull', 1: 'glass', 2: 'weapon', 3: 'plume'}

# ------------------------------------------------------------------------------------------------ the uniforms ---
# the examples' live uniforms and their defaults (linear values; a hex colour is sRGB, decoded as THREE.Color did)
MODERN_DEFAULTS = {'uPaint': 0xc8c8d2, 'uRough': 0.45}          # pewter silver, matte single-stage paint
CYBER_DEFAULTS = {'uPaint': 0x00e7ff, 'uRough': 0.18}           # electric cyan accents, light satin body
SLEEK_DEFAULTS = {'uMetalColor': (0.95, 0.93, 0.88), 'uRough': 0.15}   # silver F0 (linear, as THREE.Color(r, g, b))
JET_DEFAULTS = {'uCamoMode': 1.0}                               # 'sky'
DEFAULT_DECAL_TEXT = 'ALETH8APO'

# the presets the sources named in their comments and check scenes
METAL_PRESETS = {                     # stylizedSciFiSleekCar: F0 colours (sRGB hex, as the sources wrote them)
    'silver': 0xf3eee0, 'gold': 0xffb44a, 'copper': 0xf2a387, 'aluminum': 0xe7e7e7,
    'anodized_blue': 0x4d80e6, 'anodized_purple': 0x8b4dcc,
}
ACCENT_PRESETS = {                    # stylizedCyberpunkSedan: the palette check scene's four liveries
    'cyan': 0x00e7ff, 'magenta': 0xff2bd6, 'acid': 0x7dff00, 'amber': 0xff8a1a,
}
CAMO_MODES = {'silver': 0, 'sky': 1, 'desert': 2, 'forest': 3}  # stylizedFighterJet make({camo})
# _jetCamoColor's (light, dark) per mode, linear
CAMO_COLORS = {
    0: ((0.55, 0.57, 0.60), (0.26, 0.27, 0.29)),     # silver / urban: light pewter on dark gunmetal
    1: ((0.30, 0.40, 0.62), (0.08, 0.14, 0.34)),     # sky / air superiority: slate blue on navy
    2: ((0.52, 0.42, 0.26), (0.28, 0.20, 0.12)),     # desert: coyote tan on dark khaki
    3: ((0.30, 0.34, 0.18), (0.12, 0.16, 0.08)),     # forest / woodland: olive on dark green-brown
}

# ------------------------------------------------------------------------------------------------- the parts ---
# Principled values per part. 'emission' is the engine's unlit colour; 'core' names its view-dependent factor:
#   'head'  0.55 + 1.4 * (1 - fres)^3            (headlamps: bright head-on, 0.55 at the rim)
#   'tail'  mix(0.7, 1.2, (1 - fres)^2)          (tail lamps)
#   'sleek_head'  0.85 + 1.6 * (1 - fres)^3
#   'sleek_tail'  mix(0.95, 1.5, (1 - fres)^2)
#   'glow'  k0 + k1 * (1 - fres)^2               (underglow 2.2 + 0.6, accent strips 1.5 + 0.4)
# with fres = (1 - N.V)^5; the baked surface() takes it head-on (fres = 0).

PAINT_FLOOR = {'modern': 0.35, 'cyber': 0.20, 'sleek': 0.06}    # each shade()'s max(uRough, floor)

MODERN = {
    # matte metallic paint: uPaint +- a two-scale fleck, F = mix(0.04, base, 0.55); its sharp env reflection is the
    # clear coat (Coat Roughness follows paintRoughness, the option's documented meaning)
    'paint': dict(metallic=0.55, coat=1.0),
    'glass': dict(albedo=(0.01, 0.012, 0.018), roughness=0.04, specular=1.0),   # tint + envR*(0.08 + 0.9 fres)
    'tire': dict(albedo=(0.025, 0.025, 0.028), roughness=0.85, specular=0.35),
    'rim': dict(albedo=(0.62, 0.62, 0.66), metallic=0.85, roughness=0.12),     # polished alloy, pow(NdH, 200)
    'chrome': dict(albedo=(0.55, 0.55, 0.56), metallic=1.0, roughness=0.03),   # envR*(0.5 + 0.85 fres)*0.95
    'head': dict(albedo=(0.85, 0.85, 0.85), roughness=0.05, coat=1.0, emission=(1.6, 1.55, 1.35), core='head'),
    'tail': dict(albedo=(0.30, 0.015, 0.012), roughness=0.08, coat=1.0, emission=(1.9, 0.10, 0.05), core='tail'),
    'plastic': dict(albedo=(0.02, 0.02, 0.022), roughness=0.5, specular=0.5),   # matte black, pow(NdH, 12)
}

CYBER = {
    # near-black body whose reflectance is F = mix(0.04, 0.5, 0.7) = 0.36 neutral, scaled by 0.7 (1 - 0.8 rough):
    # a dark gunmetal metal; the racing stripes are off-white dielectric decals; uPaint glows on the silhouette
    'paint': dict(albedo=(0.24, 0.24, 0.25), metallic=1.0, coat=1.0, stripe=(0.92, 0.90, 0.85),
                  stripe_roughness=0.55, rim_glow=0.55, stripe_glow=0.45),
    'glass': dict(albedo=(0.01, 0.012, 0.018), roughness=0.04, specular=1.0),
    'tire': dict(albedo=(0.025, 0.025, 0.028), roughness=0.85, specular=0.35),
    'rim': dict(albedo=(0.55, 0.55, 0.58), metallic=0.6, roughness=0.3),        # no part uses it (as in the source)
    'chrome': dict(albedo=(0.92, 0.92, 0.92), metallic=1.0, roughness=0.02),    # metalness 1, roughness 0: mirror
    'head': dict(albedo=(0.85, 0.85, 0.85), roughness=0.05, coat=1.0, emission=(1.6, 1.55, 1.35), core='head'),
    'tail': dict(albedo=(0.30, 0.015, 0.012), roughness=0.08, coat=1.0, emission=(1.9, 0.10, 0.05), core='tail'),
    'plastic': dict(albedo=(0.012, 0.012, 0.015), roughness=0.5, specular=0.5),
    'underglow': dict(albedo=(0.0, 0.0, 0.0), roughness=0.3, specular=0.2, glow=(2.2, 0.6)),
    'accent': dict(albedo=(0.0, 0.0, 0.0), roughness=0.3, specular=0.3, glow=(1.5, 0.4)),
    # hex cells glow uPaint * 0.85 under a 0.6..1.0 light factor; the walls are a dark mesh
    'grille': dict(albedo=(0.005, 0.005, 0.005), roughness=0.4, specular=0.3, cell_glow=0.85),
    'badge': dict(albedo=(0.012, 0.012, 0.015), roughness=0.45, specular=0.5, ink=(1.4, 1.4, 1.4)),
}

SLEEK = {
    'paint': dict(metallic=1.0),                         # uMetalColor IS F0; Schlick to white at grazing
    'glass': dict(albedo=(0.01, 0.012, 0.018), roughness=0.03, specular=1.0),
    'tire': dict(albedo=(0.025, 0.025, 0.028), roughness=0.85, specular=0.35),
    # hex-tiled hubcap: mirror cells (F0 0.95, 0.93, 0.88; roughness 0.02), border F0 * 0.35 at roughness 0.20
    'chrome': dict(albedo=(0.95, 0.93, 0.88), metallic=1.0, roughness=0.02, edge_scale=0.35, edge_roughness=0.20),
    'head': dict(albedo=(0.85, 0.85, 0.85), roughness=0.05, coat=1.0, emission=(3.6, 3.5, 3.0), core='sleek_head'),
    'tail': dict(albedo=(0.30, 0.015, 0.012), roughness=0.08, coat=1.0, emission=(4.5, 0.18, 0.08),
                 core='sleek_tail'),
}

JET = {
    # camo paint: diffuse + a low-key pow(NdH, 24) * 0.25 highlight + a thin grazing sheen
    'hull': dict(roughness=0.55, specular=0.3),
    'glass': dict(albedo=(0.02, 0.04, 0.07), roughness=0.03, specular=0.75),    # tint + envR*(0.06 + 0.95 fres)
    'weapon': dict(albedo=(0.20, 0.22, 0.18), roughness=0.42, specular=0.5, band=0.25),
    # hot core fading to orange at the silhouette: mix(cool, hot, smoothstep(0, 0.7, N.V))
    'plume': dict(albedo=(0.0, 0.0, 0.0), roughness=1.0, specular=0.0, hot=(2.4, 2.2, 1.4), cool=(2.0, 0.6, 0.15)),
}

PARTS = {'modern': MODERN, 'cyber': CYBER, 'sleek': SLEEK, 'jet': JET}
IDS = {'modern': MODERN_IDS, 'cyber': CYBER_IDS, 'sleek': SLEEK_IDS, 'jet': JET_IDS}


def core_head_on(kind):
    """A lamp's view-dependent core factor seen head-on (fres = 0): what the baked surface() stores."""
    return {'head': 0.55 + 1.4, 'tail': 1.2, 'sleek_head': 0.85 + 1.6, 'sleek_tail': 1.5}[kind]


# ----------------------------------------------------------------------------------------------- the colours ---

def srgb_to_linear(c):
    c = float(c)
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_color(value):
    """A make() colour option as linear (r, g, b), the way THREE.Color read it:
      0xRRGGBB (int) or '#rrggbb' / '#rgb' / 'rrggbb'  sRGB, decoded to linear (THREE.Color(hex), setStyle)
      (r, g, b) floats                                  linear already (THREE.Color(r, g, b))
      a mathutils Color or anything with .r .g .b       linear
      a METAL_PRESETS / ACCENT_PRESETS name             its hex
    (The sources also documented [r, g, b] arrays, which THREE.Color silently ignored, leaving white; here a
    sequence means what the documentation said: linear 0..1.)"""
    if isinstance(value, str):
        key = value.strip().lower().replace(' ', '_')
        if key in METAL_PRESETS:
            value = METAL_PRESETS[key]
        elif key in ACCENT_PRESETS:
            value = ACCENT_PRESETS[key]
        else:
            h = key.lstrip('#')
            if len(h) == 3:
                h = ''.join(ch * 2 for ch in h)
            if len(h) != 6:
                raise ValueError(f'colour {value!r}: expected #rrggbb, #rgb, an int 0xRRGGBB or (r, g, b)')
            value = int(h, 16)
    if isinstance(value, bool):
        raise TypeError(f'colour {value!r}: expected a colour')
    if isinstance(value, int):
        r, g, b = (value >> 16) & 255, (value >> 8) & 255, value & 255
        return tuple(srgb_to_linear(x / 255.0) for x in (r, g, b))
    if hasattr(value, 'r') and hasattr(value, 'g') and hasattr(value, 'b'):
        return (float(value.r), float(value.g), float(value.b))
    vals = [float(x) for x in value]
    if len(vals) < 3:
        raise ValueError(f'colour {value!r}: expected three components')
    return tuple(vals[:3])


def camo_id(camo):
    """make({camo}): 'silver' | 'sky' | 'desert' | 'forest' (any case) or an integer 0..3 (truncated, as `| 0` did)."""
    if isinstance(camo, str):
        k = camo.lower()
        if k not in CAMO_MODES:
            raise ValueError(f'stylized_fighter_jet: unknown camo "{camo}". Use one of: silver, sky, desert, forest.')
        return CAMO_MODES[k]
    return int(camo)


def glsl_vec3(v):
    return 'vec3(%s)' % ', '.join('%.6g' % float(x) for x in v)


def glsl_float(v):
    s = '%.6g' % float(v)
    return s if ('.' in s or 'e' in s) else s + '.0'

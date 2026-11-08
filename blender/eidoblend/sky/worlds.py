"""The three sky worlds, as eidoverse/sky_worlds.js defines them: one key selects a whole world.

Each entry is complete: its assets, its celestial bodies, its sky options and its geometry. A scene cannot
substitute any of it (sky_worlds.js: "A world is not a bag of assets a scene fills in"). Where Eanpa Engine's
standalone has a newer version of a world's module (src/ringsky.js, src/shieldworld.js), its additions are named
in the entry. No bpy here.
"""
import math

WORLDS = {
    'earth': dict(
        label='Earth',
        starmap='starmap_tycho_4k.jpg',
        moonmap='moon_color_1k.jpg',
        sky=dict(moonAngularDeg=0.55),
    ),
    'ringworld': dict(
        label='Orbital / Halo',
        starmap='starmap_tycho_4k.jpg',
        # the companion body is a ROCK GIANT of orange mineral: not a grey moon, and not swappable
        moonmap='celestial/rock_giant.png',
        # what it reflects is a warm near-white (a grey moon reflects cool light because it is grey)
        planetShine=(1.00, 0.92, 0.82),
        sky=dict(
            ringCurve=5000,           # the cloud deck bows up along the arc
            moonAngularDeg=16,        # ~10x luna: a looming companion world
            # Eanpa src/ringsky.js: the sun's noon sits in the ring plane, so the terminator sweeps the arc
            noonAzimuth=math.pi / 2,
        ),
        band=dict(
            glb='celestial/RINGWORLDskyelement.glb',
            landmask='celestial/ringworldlandmask.png',
            solarColor='celestial/SolarPanel001_1K-JPG_Color.jpg',
            solarNormal='celestial/SolarPanel001_1K-JPG_NormalGL.jpg',
            solarRough='celestial/SolarPanel001_1K-JPG_Roughness.jpg',
            solarMetal='celestial/SolarPanel001_1K-JPG_Metalness.jpg',
            bandNormal='celestial/ring_band_normal.png',
            bandAO='celestial/ring_band_ao.png',
            # the height field the normal map was derived from: displaced into real relief here (Eanpa's
            # ring_terrain_geometry.js), where the WebGPU edition ray-marched it (SPOM)
            bandHeight='celestial/ring_band_height.png',
            # AUTHORED placement: ring centre ~4940 m up, so the lowest arc plunges into the ground ~1.2 km away,
            # the band rises from the horizon at your feet and crests ~9.8 km overhead. Straight up.
            centerY=4940,
        ),
    ),
    'shieldworld': dict(
        label='Earth 5129323011 CE (Red Giant)',
        # the ONLY package with a shield, so the only one where a shield colour means anything
        shield=True,
        starmap='starmap_tycho_4k.jpg',
        # NO moonmap: this world's companion is the SHATTERED MOON, a GLB cluster of fragments on its orbit
        moon=dict(
            glb='celestial/asteroid_cluster_v3.glb',
            baked='celestial/asteroid_moon_baked.png',
            normal='celestial/asteroid_moon_normal.png',
            # CINEMATIC scale: ~4x the astronomically true 0.5 deg; ~14 deg of crumble at spread 1.75
            scale=1400,
            spread=1.75,
        ),
        # this moon reflects the RED GIANT, so its light is orange
        planetShine=(1.00, 0.60, 0.32),
        sky=dict(
            # the star subtends ~32 deg, so sunset stretches across the disc's real width
            sourceAngularRadiusDeg=0.28 * 180 / math.pi,
            # the Mie phase peaks ~180x forward, right only for a ~0.5 deg sun: a star this wide broadens it
            cloudPhaseSoften=0.85,
            moonLightIntensity=1.15,
        ),
    ),
}

SKY_WORLDS = {k: v['label'] for k, v in WORLDS.items()}


def ring_constants(ring_r, base=450.0, thick=280.0, local_half=4000.0, wisp_curve_half=None, shear_k=2.0):
    """sky_system.js's ring deck constants (RING_*), R-relative as the JS hardcodes them, for sky.glsl.

    The profile is a rounded-corner chord: flat across the local scene, a true circular fillet lifting the far deck,
    a clean fade-out before the crest. The slab bounds are the JS's 25 m precompute of the draped layer."""
    R = float(ring_r)
    zflat, zcrest, rise, zend = R * 0.84, R * 0.98, R * 0.07, R * 0.995
    arc_w = max(zcrest - zflat, 1.0)
    arc_rad = (arc_w * arc_w + rise * rise) / (2 * max(rise, 1.0))
    visible_end = min(zend, zcrest)
    end_fade = max(arc_w * 0.20, 1.0)

    def deck_y(z):
        uz = min(max(abs(z) - zflat, 0.0), arc_w * 0.999)
        return base + arc_rad - math.sqrt(max(arc_rad * arc_rad - uz * uz, 1.0))

    slab_lo, slab_hi = base - 20.0, base + thick + 20.0
    z = 0.0
    while z <= min(zend, R):
        sl = (deck_y(z + 50) - deck_y(z - 50)) / 100.0
        slab_hi = max(slab_hi, deck_y(z) + thick * math.sqrt(1 + sl * sl) + 20.0)
        z += 25.0
    return dict(RING_ON=1, RING_R=R, RING_BASE=float(base), RING_THICK=float(thick), RING_ZFLAT=zflat,
                RING_ZCREST=zcrest, RING_RISE=rise, RING_ZEND=zend, RING_ARC_W=arc_w, RING_ARC_RAD=arc_rad,
                RING_VISIBLE_END=visible_end, RING_END_FADE=end_fade, RING_SLAB_LO=slab_lo, RING_SLAB_HI=slab_hi,
                RING_SHEAR_K=float(shear_k), RING_LOCAL_HALF=float(local_half),
                RING_WISP_CURVE_HALF=float(wisp_curve_half if wisp_curve_half is not None else local_half * 0.5),
                RING_RISE_MAX=R * 0.60)


def ring_deck_y(z, k):
    """The deck base height at three z for ring constants k (the JS _deckY mirror)."""
    uz = min(max(abs(z) - k['RING_ZFLAT'], 0.0), k['RING_ARC_W'] * 0.999)
    return k['RING_BASE'] + k['RING_ARC_RAD'] - math.sqrt(max(k['RING_ARC_RAD'] ** 2 - uz * uz, 1.0))

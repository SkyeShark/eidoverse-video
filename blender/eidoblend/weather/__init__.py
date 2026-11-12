"""eidoblend.weather: the weather effects of eidoverse/weather_system.js and weather_audio.js in Blender 5.2 EEVEE.

make_sky builds this weather itself as soon as its weather rains, strikes or wets (make_sky(weather_fx=...)), and its
bake() bakes it. By hand, with the scene owning it:

    from eidoblend.sky import make_sky
    from eidoblend.weather import make_weather_system
    sky = make_sky(scene, camera=cam, hours=17.0, weather='overcast', cache_dir='C:/films/street/sky_cache',
                   weather_fx=False)
    wx = make_weather_system(scene, sky, strike_targets=[street], occluders=street)
    wx.wrap_scene()
    wx.transition_to('darkstorm', 1.0, 12.0, at=3.0)
    wx.bake()
    wx.bake_audio('C:/films/street/wx.wav')

make_weather_system(scene, None, cache_dir=...) rains over a scene that keeps its own world and lighting.

The sky package (eidoblend.sky) runs the weather state machine and the sky side (cloud cover, greying, sun dim).
This package ports the rest: rain streaks and splashes, wetness and puddles (the eido_wet group) with the 2D moisture
history, lightning (scheduler, bolt ribbon, strike light, sparks, smoke, scorch, the local-strike ray cast) and the
weather audio timeline. Modules:

    system      make_weather_system / WeatherFX: the facade (direction, wrap, plan, bake, keys, audio, dispose)
    lightning   EANPA_LIGHTNING_PROFILE, the scheduler, the impact particle data (plain Python)
    bolt        rebuildBolt's ribbon (plain Python)
    moisture    the 2D moisture history (numpy)
    frame       rainLight / rainColor and the rain cell gate (plain Python)
    rain        the rain streak and splash Geometry Nodes generators and their materials
    wet         the eido_wet group (and eidoverse's own, eido_wet_eidoverse), wrap_material / unwrap_material,
                the moisture image sequence
    strike      the strike light, bolt meshes, impact sparks / puffs / scorch, the local-strike ray cast
    values      the keyed shader values every weather material reads
    audio       the weather-audio timeline, make_weather_audio (makeWeatherAudio), bake_weather_audio.py, merge_av.py
    keys        bulk F-curves

Importing this package imports no bpy. Guide: tools-guides/weather-effects.md.
"""

from .lightning import (EANPA_LIGHTNING_PROFILE, LIGHTNING_CADENCE, LIGHTNING_PALETTES, LIGHTNING_STYLES,
                        js_hash, lightning_channel_at, lightning_event_gap_at, lightning_flash_at,
                        lightning_initial_event_gap_at, lightning_local_candidate_at, lightning_stroke_plan_at,
                        lightning_style_key_at, make_lightning_profile)


def make_weather_system(scene=None, sky=None, **opts):
    """The Blender makeWeatherSystem: see eidoblend.weather.system.make_weather_system."""
    from .system import make_weather_system as _make
    return _make(scene, sky, **opts)


def make_weather_audio(weather=None, camera=None, **opts):
    """The Blender makeWeatherAudio: see eidoblend.weather.audio.make_weather_audio."""
    from .audio import make_weather_audio as _make
    return _make(weather, camera, **opts)


def weather_states():
    """The WEATHER table and LEGACY_STATES (owned by the sky package)."""
    from ..sky.weather_system import WEATHER, LEGACY_STATES
    return WEATHER, LEGACY_STATES


__all__ = ['make_weather_system', 'make_weather_audio', 'weather_states', 'EANPA_LIGHTNING_PROFILE', 'LIGHTNING_CADENCE',
           'LIGHTNING_PALETTES', 'LIGHTNING_STYLES', 'js_hash', 'lightning_channel_at', 'lightning_event_gap_at',
           'lightning_flash_at', 'lightning_initial_event_gap_at', 'lightning_local_candidate_at',
           'lightning_stroke_plan_at', 'lightning_style_key_at', 'make_lightning_profile']

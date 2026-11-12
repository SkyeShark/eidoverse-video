"""eidoblend.harness.settings: EEVEE render presets and the scene config's "render" block.

The presets are my films' settings (episode three's house.blend, read 11-07, and the render-time overrides
render_h264.py measured on it):

  film   EEVEE, AgX ('AgX - Base Contrast'); ray tracing on (screen traces, full resolution, spatial + temporal +
         bilateral denoise, trace quality 0.5, thickness 0.05, max roughness 0.5); fast GI (global illumination,
         resolution 2, 8 steps, 2 rays, 0.6 m); shadows 2 rays x 12 steps; volumes 16 px tiles x 32 samples (measured on
         the house to look like 4 x 128 at 2.5 s a frame instead of 4.1), ray depth 16, volumetric shadows; clamp
         indirect 10; 3 diffuse bounces; 1024 cubemaps; light threshold 0.01; 32 samples; motion blur, shutter 0.5;
         filter 1.5 px.
  probe  the same look, cheaper: at most 960 x 540 (aspect kept), at most 16 samples, traces at half resolution.
         The team rule for shared-GPU probes, and still the film's light and materials.

Order of application (build): preset -> setup(ctx) -> the config's "render" block (it overrides the script: a per-run
choice) -> the frame range from the config. A probe's caps come last, at render time, and are never saved.
"""

from __future__ import annotations

import bpy

from . import config as cfgmod

FILM = {
    'eevee': {
        'taa_render_samples': 32,
        'use_raytracing': True, 'ray_tracing_method': 'SCREEN',
        'use_fast_gi': True, 'fast_gi_method': 'GLOBAL_ILLUMINATION', 'fast_gi_resolution': '2',
        'fast_gi_step_count': 8, 'fast_gi_ray_count': 2, 'fast_gi_distance': 0.6,
        'use_shadows': True, 'shadow_ray_count': 2, 'shadow_step_count': 12, 'shadow_resolution_scale': 1.0,
        'volumetric_tile_size': '16', 'volumetric_samples': 32, 'volumetric_ray_depth': 16,
        'use_volumetric_shadows': True,
        'clamp_surface_indirect': 10.0, 'gi_diffuse_bounces': 3, 'gi_cubemap_resolution': '1024',
        'light_threshold': 0.01, 'motion_blur_steps': 1,
    },
    'ray_tracing_options': {
        'resolution_scale': '1', 'use_denoise': True, 'denoise_spatial': True, 'denoise_temporal': True,
        'denoise_bilateral': True, 'screen_trace_quality': 0.5, 'screen_trace_thickness': 0.05,
        'trace_max_roughness': 0.5,
    },
    'render': {'use_motion_blur': True, 'motion_blur_shutter': 0.5, 'filter_size': 1.5, 'film_transparent': False,
               'resolution_percentage': 100},
    'view': {'view_transform': 'AgX', 'look': 'AgX - Base Contrast', 'exposure': 0.0, 'gamma': 1.0},
}
PROBE_CAPS = {'samples': cfgmod.PROBE_SAMPLES, 'max_size': cfgmod.PROBE_MAX, 'trace_resolution': '2'}


def _set(owner, name, value, applied, label):
    if not hasattr(owner, name):
        applied.append(f'{label}.{name}: not in this Blender (skipped)')
        return False
    try:
        setattr(owner, name, value)
        return True
    except (TypeError, ValueError, AttributeError) as e:
        applied.append(f'{label}.{name} = {value!r}: refused ({e})')
        return False


def apply_preset(scene, cfg: dict) -> list:
    """The film preset, the config's size and rate, AgX. Returns notes on anything this Blender refused."""
    notes = []
    r = scene.render
    r.engine = 'BLENDER_EEVEE'
    for k, v in FILM['eevee'].items():
        _set(scene.eevee, k, v, notes, 'eevee')
    for k, v in FILM['ray_tracing_options'].items():
        _set(scene.eevee.ray_tracing_options, k, v, notes, 'eevee.ray_tracing_options')
    for k, v in FILM['render'].items():
        _set(r, k, v, notes, 'render')
    vs = scene.view_settings
    _set(vs, 'view_transform', FILM['view']['view_transform'], notes, 'view')
    _set(vs, 'look', FILM['view']['look'], notes, 'view')
    vs.exposure = FILM['view']['exposure']
    vs.gamma = FILM['view']['gamma']
    apply_size_rate(scene, cfg)
    return notes


def apply_size_rate(scene, cfg: dict):
    r = scene.render
    r.resolution_x, r.resolution_y = int(cfg['width']), int(cfg['height'])
    r.pixel_aspect_x = r.pixel_aspect_y = 1.0
    fps = float(cfg['fps'])
    if fps == int(fps):
        r.fps, r.fps_base = int(fps), 1.0
    else:                                                    # 23.976 -> 24000/1001 style
        base = round(fps) / fps
        r.fps, r.fps_base = int(round(fps)), base
    fs, fe = cfgmod.frame_range(cfg)
    scene.frame_start, scene.frame_end = fs, fe
    scene.frame_step = 1


def apply_render_block(scene, block: dict) -> list:
    """The config's "render" block (after setup). Returns what it set, for the build record."""
    done = []
    ee, r, vs = scene.eevee, scene.render, scene.view_settings
    if 'samples' in block:
        ee.taa_render_samples = int(block['samples'])
        done.append(f"samples {ee.taa_render_samples}")
    if 'motion_blur' in block:
        r.use_motion_blur = bool(block['motion_blur'])
        done.append(f'motion blur {r.use_motion_blur}')
    if 'shutter' in block:
        r.motion_blur_shutter = float(block['shutter'])
        done.append(f'shutter {r.motion_blur_shutter}')
    if 'raytracing' in block:
        # false: reflections and refraction from the light probes, no screen traces; EEVEE's ray tracing itself
        # stays on, since fast GI runs inside it
        ee.use_raytracing = True
        ee.ray_tracing_method = 'SCREEN' if block['raytracing'] else 'PROBE'
        done.append(f'raytracing {ee.ray_tracing_method}')
    if 'volume_tile' in block:
        ee.volumetric_tile_size = str(int(block['volume_tile']))
        done.append(f'volume tile {ee.volumetric_tile_size}')
    if 'volume_samples' in block:
        ee.volumetric_samples = int(block['volume_samples'])
        done.append(f'volume samples {ee.volumetric_samples}')
    if 'exposure' in block:
        vs.exposure = float(block['exposure'])
        done.append(f'exposure {vs.exposure:+.2f}')
    if 'look' in block:
        vs.look = str(block['look'])
        done.append(f'look {vs.look}')
    if 'film_transparent' in block:
        r.film_transparent = bool(block['film_transparent'])
        done.append(f'film transparent {r.film_transparent}')
    if 'resolution_percentage' in block:
        r.resolution_percentage = int(block['resolution_percentage'])
        done.append(f'resolution {r.resolution_percentage}%')
    if block.get('bloom'):
        done.append(add_bloom(scene, block['bloom'] if isinstance(block['bloom'], dict) else {}))
    return done


def add_bloom(scene, opts: dict) -> str:
    """The bloom: the compositor chain's Glare stage (eidoblend.look.post.chain.set_bloom), the same stage the
    scene's _bloom_params and the post family's looks use, so a scene's own compositor stages keep their order:
    Render Layers -> bloom -> 'under' stages -> the overlay -> 'over' stages -> the output. In 5.2 the compositor is
    a node group (scene.compositing_node_group) and the Glare node's settings are input sockets."""
    from ..look.post import chain
    th, sz, st = float(opts.get('threshold', 1.0)), float(opts.get('size', 0.5)), float(opts.get('strength', 1.0))
    chain.set_bloom(scene, strength=st, size=sz, threshold=th)
    return f'bloom (compositor Glare: threshold {th:g}, size {sz:g}, strength {st:g})'


def apply_probe_caps(scene) -> list:
    """The probe preset's caps, at render time only (never saved): size, samples, half-resolution traces."""
    notes = []
    r, ee = scene.render, scene.eevee
    w, h = r.resolution_x * r.resolution_percentage / 100.0, r.resolution_y * r.resolution_percentage / 100.0
    mw, mh = PROBE_CAPS['max_size']
    if w < h:
        mw, mh = mh, mw
    k = min(1.0, mw / w, mh / h)
    if k < 1.0:
        nw, nh = int(w * k) // 2 * 2, int(h * k) // 2 * 2
        r.resolution_x, r.resolution_y, r.resolution_percentage = nw, nh, 100
        notes.append(f'size {int(w)}x{int(h)} -> {nw}x{nh}')
    if ee.taa_render_samples > PROBE_CAPS['samples']:
        notes.append(f"samples {ee.taa_render_samples} -> {PROBE_CAPS['samples']}")
        ee.taa_render_samples = PROBE_CAPS['samples']
    if getattr(ee.ray_tracing_options, 'resolution_scale', '2') == '1':
        ee.ray_tracing_options.resolution_scale = PROBE_CAPS['trace_resolution']
        notes.append('traces at half resolution')
    return notes


def describe(scene) -> dict:
    """The settings a render actually ran with, for the build record and the digest."""
    r, ee, vs = scene.render, scene.eevee, scene.view_settings
    return {
        'engine': r.engine, 'size': [r.resolution_x, r.resolution_y, r.resolution_percentage],
        'fps': round(r.fps / r.fps_base, 4), 'frames': [scene.frame_start, scene.frame_end],
        'samples': ee.taa_render_samples, 'raytracing': ee.use_raytracing,
        'trace_resolution': getattr(ee.ray_tracing_options, 'resolution_scale', None),
        'fast_gi': ee.use_fast_gi, 'motion_blur': [r.use_motion_blur, r.motion_blur_shutter],
        'volumes': [ee.volumetric_tile_size, ee.volumetric_samples],
        'colour': [vs.view_transform, vs.look, round(vs.exposure, 3)],
        'world': scene.world.name if scene.world else None, 'camera': scene.camera.name if scene.camera else None,
        'compositing': bool(scene.compositing_node_group) and r.use_compositing,
    }

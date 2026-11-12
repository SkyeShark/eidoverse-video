"""look/render_settings.py: the EEVEE look, as presets. The Blender edition's applyAutoEnhance.

The WebGPU harness ran a post chain on every frame (N8AO, SSR, bloom, TRAA, FXAA, ACES). EEVEE does those jobs in the
renderer: fast GI is the AO and one bounce, ray tracing is the SSR (falling back to sphere probes and the world),
taa_render_samples jittered samples per frame through a 1.5 px filter are the anti-aliasing, AgX is the tone map. What
carries over is the knobs and the lessons; this module sets them.

    from eidoblend.look import render_settings as rs
    rs.apply_auto_enhance(scene, 'film')                       # a finished film's measured look (below)
    rs.apply_auto_enhance(scene, 'probe')                      # the same look, small and quick, for probe stills
    rs.apply_auto_enhance(scene, 'film', exposure=1.0, ao={'distance': 0.4}, ssr={'max_roughness': 0.6})
    rs.apply_auto_enhance(scene, 'film', bloom={'strength': 0.2, 'threshold': 3.0})   # Glare bloom, off by default

'film' is read from a finished interior film's set (its saved .blend): the settings it rendered with. Exposure is the
scene's, not the preset's: it depends on the light (an indoor set took +2 under AgX, a physical sky needs far less);
measure it with look.exposure.auto_expose.
"""
import bpy

FILM = {
    'resolution': (1920, 1080),
    'samples': 32,                   # the film's renders at 32; its set's .blend keeps 128 for stills
    'filter_size': 1.5,
    'overscan': 3.0,                 # % of the frame added round the edges: screen-space effects hold at the borders
    'raytracing': {'method': 'SCREEN', 'resolution_scale': '1', 'max_roughness': 0.5, 'quality': 0.5, 'thickness': 0.05,
                   'backface_hit': True, 'denoise': True, 'denoise_spatial': True, 'denoise_temporal': True,
                   'denoise_bilateral': True},
    'fast_gi': {'method': 'GLOBAL_ILLUMINATION', 'resolution': '2', 'ray_count': 2, 'step_count': 8, 'distance': 0.6,
                'quality': 0.25, 'bias': 0.05},
    'clamp_surface_indirect': 10.0,
    'shadows': {'ray_count': 2, 'step_count': 12, 'pool': '1024', 'resolution_scale': 1.0, 'light_threshold': 0.01},
    # measured on the film's set: volumes at tile 16 x 32 samples look the same as its .blend's 4 x 128 (6 px of 2 M
    # differ) at 2.5 s a frame instead of 4.1
    'volumes': {'tile': '16', 'samples': 32, 'distribution': 0.85, 'shadows': True, 'shadow_samples': 32},
    'motion_blur': {'shutter': 0.5, 'position': 'CENTER', 'steps': 1},
    'colour': {'view': 'AgX', 'look': 'AgX - Base Contrast', 'gamma': 1.0},
}

PROBE = {**FILM, 'resolution': (960, 540), 'samples': 16,
         'volumes': {**FILM['volumes'], 'tile': '16', 'samples': 32}}

PREVIEW = {**FILM, 'resolution': (480, 270), 'samples': 8,
           'raytracing': {**FILM['raytracing'], 'resolution_scale': '2'},
           'volumes': {**FILM['volumes'], 'tile': '16', 'samples': 16, 'shadow_samples': 8}}

PRESETS = {'film': FILM, 'probe': PROBE, 'preview': PREVIEW}


def _set(obj, attr, value, done, key):
    if value is None or not hasattr(obj, attr):
        return
    setattr(obj, attr, value)
    done[key] = value


def apply_auto_enhance(scene, preset='film', *, resolution=None, percentage=100, samples=None, exposure=None, look=None,
                       ao=None, ssr=None, bloom=None, motion_blur=None, volumes=None, shadows=None, white_balance=None,
                       filter_size=None, fps=None, keep_sequencer=False):
    """Set the scene's EEVEE look from a preset, with per-knob overrides. Returns what it set (log it).

    ao           dict(distance=, method='GLOBAL_ILLUMINATION'|'AMBIENT_OCCLUSION_ONLY', quality=, ...): EEVEE's fast GI,
                 which is always on (indoors too, with a baked room probe: look.lighting.add_room_probe)
                 -- N8AO's lesson: contact scale. 0.3-0.6 m for people and props, metres for architecture.
    ssr          dict(max_roughness=, quality=, thickness=, resolution_scale=, method='SCREEN'|'PROBE') or False
                 (False: reflections from the light probes alone, EEVEE's 'PROBE' tracing; the ray tracing stays on,
                 since fast GI runs inside it)
    bloom        dict(strength=, size=, threshold=, type='Bloom'|'Fog Glow') or False / None (off, as in the house)
    motion_blur  dict(shutter=, position=, steps=) or False
    volumes      dict(tile=, samples=, distribution=, shadows=, shadow_samples=)
    white_balance  Kelvin (e.g. 5000) or False
    keep_sequencer False turns use_sequencer off: a scene whose VSE has strips renders the strips, not the 3D view.
    """
    P = PRESETS[preset] if isinstance(preset, str) else preset
    done = {}
    r, ee = scene.render, scene.eevee
    r.engine = 'BLENDER_EEVEE'
    done['engine'] = r.engine
    rx, ry = resolution or P['resolution']
    r.resolution_x, r.resolution_y, r.resolution_percentage = int(rx), int(ry), int(percentage)
    done['resolution'] = [r.resolution_x, r.resolution_y, r.resolution_percentage]
    if fps:
        r.fps, r.fps_base = int(fps), 1.0
    _set(r, 'filter_size', filter_size or P['filter_size'], done, 'filter_size')
    ee.taa_render_samples = int(samples or P['samples'])
    done['samples'] = ee.taa_render_samples
    if P.get('overscan'):
        ee.use_overscan = True
        ee.overscan_size = float(P['overscan'])
        done['overscan'] = ee.overscan_size

    # ray tracing: the SSR + reflections + refraction path, and fast GI's host (EEVEE runs fast GI inside it)
    rt = dict(P['raytracing'])
    rt.update(ssr or {})
    if ssr is False:
        rt['method'] = 'PROBE'
    ee.use_raytracing = True
    ee.ray_tracing_method = rt['method']
    o = ee.ray_tracing_options
    o.resolution_scale = str(rt['resolution_scale'])
    o.trace_max_roughness = float(rt['max_roughness'])
    o.screen_trace_quality = float(rt['quality'])
    o.screen_trace_thickness = float(rt['thickness'])
    o.use_backface_hit = bool(rt['backface_hit'])
    o.use_denoise = bool(rt['denoise'])
    o.denoise_spatial = bool(rt['denoise_spatial'])
    o.denoise_temporal = bool(rt['denoise_temporal'])
    o.denoise_bilateral = bool(rt['denoise_bilateral'])
    done['raytracing'] = rt

    # fast GI: N8AO's job (contact darkening) plus a screen-space bounce, on in every preset
    if ao is False:
        raise ValueError('apply_auto_enhance: fast GI stays on (EEVEE\'s global illumination, interiors included: '
                         'a room gets a baked volume probe, look.lighting.add_room_probe); ao takes a dict of its '
                         'settings')
    gi = dict(P['fast_gi'])
    gi.update(ao or {})
    ee.use_fast_gi = True
    ee.fast_gi_method = gi['method']
    ee.fast_gi_resolution = str(gi['resolution'])
    ee.fast_gi_ray_count = int(gi['ray_count'])
    ee.fast_gi_step_count = int(gi['step_count'])
    ee.fast_gi_distance = float(gi['distance'])
    ee.fast_gi_quality = float(gi['quality'])
    ee.fast_gi_bias = float(gi['bias'])
    done['fast_gi'] = gi
    ee.clamp_surface_indirect = float(P['clamp_surface_indirect'])

    sh = dict(P['shadows'])
    sh.update(shadows or {})
    ee.use_shadows = True
    ee.shadow_ray_count = int(sh['ray_count'])
    ee.shadow_step_count = int(sh['step_count'])
    ee.shadow_pool_size = str(sh['pool'])
    ee.shadow_resolution_scale = float(sh['resolution_scale'])
    ee.light_threshold = float(sh['light_threshold'])
    done['shadows'] = sh

    vo = dict(P['volumes'])
    vo.update(volumes or {})
    ee.volumetric_tile_size = str(vo['tile'])
    ee.volumetric_samples = int(vo['samples'])
    ee.volumetric_sample_distribution = float(vo['distribution'])
    ee.use_volumetric_shadows = bool(vo['shadows'])
    ee.volumetric_shadow_samples = int(vo['shadow_samples'])
    done['volumes'] = vo

    if motion_blur is False:
        r.use_motion_blur = False
        done['motion_blur'] = False
    else:
        mb = dict(P['motion_blur'])
        mb.update(motion_blur or {})
        r.use_motion_blur = True
        r.motion_blur_shutter = float(mb['shutter'])
        r.motion_blur_position = mb['position']
        ee.motion_blur_steps = int(mb['steps'])
        done['motion_blur'] = mb

    col = dict(P['colour'])
    set_view(scene, view=col['view'], look=look or col['look'], exposure=exposure, gamma=col['gamma'],
             white_balance=white_balance)
    vs = scene.view_settings
    done['colour'] = {'view': vs.view_transform, 'look': vs.look, 'exposure': vs.exposure,
                      'white_balance': vs.white_balance_temperature if vs.use_white_balance else None}

    if not keep_sequencer:
        r.use_sequencer = False
    if bloom:
        from .post import chain
        chain.set_bloom(scene, **bloom)
        done['bloom'] = bloom
    elif bloom is False:
        from .post import chain
        chain.set_bloom(scene, None)
        done['bloom'] = False
    return done


def set_view(scene, view='AgX', look=None, exposure=None, gamma=None, white_balance=None):
    """The view transform (three's renderer tone map): AgX and its look, exposure in stops, white balance in Kelvin.
    look names are the OCIO ones: 'AgX - Base Contrast', 'AgX - Punchy', 'AgX - Medium High Contrast', ...;
    'None' for none. view='False Color' is AgX's exposure-zone view, for review."""
    vs = scene.view_settings
    vs.view_transform = view
    if look is not None:
        vs.look = look
    if exposure is not None:
        vs.exposure = float(exposure)
    if gamma is not None:
        vs.gamma = float(gamma)
    if white_balance is False:
        vs.use_white_balance = False
    elif white_balance:
        vs.use_white_balance = True
        vs.white_balance_temperature = float(white_balance)
    return vs


def summary(scene):
    """One line of the look actually set (log it before every render)."""
    r, ee, vs = scene.render, scene.eevee, scene.view_settings
    return (f'{r.engine} {r.resolution_x}x{r.resolution_y}@{r.resolution_percentage}% {r.fps} fps, {ee.taa_render_samples} '
            f'samples, filter {r.filter_size}; raytracing {ee.use_raytracing} ({ee.ray_tracing_method}, max rough '
            f'{ee.ray_tracing_options.trace_max_roughness}); fast GI {ee.use_fast_gi} ({ee.fast_gi_method}, '
            f'{ee.fast_gi_distance} m); shadows {ee.shadow_ray_count} rays x {ee.shadow_step_count} steps; volumes tile '
            f'{ee.volumetric_tile_size} x {ee.volumetric_samples}; motion blur {r.use_motion_blur} ({r.motion_blur_shutter}); '
            f'{vs.view_transform} / {vs.look} / exposure {vs.exposure:+.2f}; compositing '
            f'{bool(scene.compositing_node_group) and r.use_compositing}; sequencer {r.use_sequencer}')

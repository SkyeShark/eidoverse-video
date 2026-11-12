"""eidoblend.look: the look family of the Blender edition (Blender 5.2, EEVEE). Cameras, lights, the EEVEE look presets,
the post chain, exposure by measurement, and the review tools.

Modules (import the one you need, or reach it as look.<name>: this package imports none of them until then, so
frame_stats runs outside Blender too):
    render_settings  apply_auto_enhance(scene, 'film'|'probe'|'preview', ...), set_view, summary
    exposure         exposure_sweep, pick_exposure, auto_expose: one render, every exposure measured
    frame_stats      the highlight check (share of pixels with a channel >= 250), sequence checks, contact sheets
    camera           make_camera, set_fov, focus_point, look_at_object, moves (dolly, push, orbit, pan, track, zoom,
                     handheld), focus_on (focus pulls), add_shot / shot_spans
    camera_safety    CameraSafety: check_camera (the keyed path, every frame), check_path, safe_position
    camera_audit     camera_motion_audit (bounce), framing_audit (speck), focus_audit (soft subject)
    lighting         units (lux, candela -> W), three-point rigs, practicals, create_rt_lighting, light probes, log_lights
    stage_rig        create_stage_rig: pars and profiles hung on pipes, lenses glowing at their light's level
    post             chain (the compositor order, its slots: prebloom, bloom, under, overlay, over), custom_effects
                     (the effect registry: every WebGPU effect by name), era_looks, aeropittura, after_image,
                     screen_effects (the passes), history (earlier frames through the disk, cuts), display (display
                     space through the view transform, kept synced)
    probe            render_stills at times (jump / preroll / replay), each measured
    probe_cli        the command line: --blend X --at 1.5 --at 4 [--preroll 1] [--compare]
    audit            the audit ledger (records, inventory, declarations, coverage, digest)
    overlap          exact mesh-mesh overlap from BVH trees, push_clear

Guides: tools-guides/camera-lighting.md, postprocessing.md, render-review.md, stack-notes.md.
"""

import importlib

MODULES = ('render_settings', 'exposure', 'frame_stats', 'camera', 'camera_safety', 'camera_audit', 'lighting',
           'stage_rig', 'post', 'probe', 'probe_cli', 'audit', 'overlap')


def __getattr__(name):
    """look.post, look.camera ...: the modules, imported on first use."""
    if name in MODULES:
        return importlib.import_module(f'{__name__}.{name}')
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


def __dir__():
    return sorted(set(globals()) | set(MODULES))

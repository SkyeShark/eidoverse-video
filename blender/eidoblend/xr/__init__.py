"""eidoblend.xr: a Blender scene in a headset browser, on the kit (eidoverse/xr/; tools-guides/webxr.md).

The films render in Blender; a headset runs a live WebGL2 page. The Blender edition's path from one to the other:

    import sys; sys.path.insert(0, '<repo>/blender')
    from eidoblend.xr.export import set_xr, survey_xr, export_xr      # inside Blender
    set_xr(scene, street=1.0, start=(0, -6, 0), facing=(0, 1, 0))
    survey_xr(scene)                 # what the export would do, changing nothing
    export_xr('work/<id>/vr')        # scene.glb + world.hdr + scene.xr.json + choreo.json + index.html

    bash run_blender.sh blender/eidoblend/xr/export_cli.py work/<id>/scene.blend work/<id>/vr   # the same, headless
    bash run_blender.sh blender/eidoblend/xr/export_cli.py work/<id>/scene.blend --survey

    python blender/eidoblend/xr/server.py --home /work/<id>/vr/index.html     # the kit's server (+ /blender/)
    python blender/eidoblend/xr/shots.py http://127.0.0.1:8894/work/<id>/vr/index.html work/<id>/vr/shots "t=4"

Modules (bpy only where it must be; server, shots and glb are plain Python):
    export     set_xr / get_xr (the scene's XR settings), survey_xr, export_xr (the bundle; any scene, made the context
               scene meanwhile: context_scene), write_page, export_objects, unsupported (what glTF cannot hold),
               volume_meshes (haze and fog boxes, left out), metaballs_to_meshes, check_channels, vrm_casts /
               export_vrm_casts (a cast's .vrm for the page's MToon), world_changes / world_sequence_frames (a sky
               that changes: a timed sequence), world_gpu_mb (the world's images on the headset's GPU),
               sound_strips (audio.mp3), pointer_targets (the GLB's KHR_animation_pointer channels)
    materials  survey / classify (what the exporter would drop), bake_for_gltf (Cycles bakes of exactly those
               channels), convert_mtoon / mtoon_to_gltf / drop_mtoon_outlines (a VRM cast), used_materials,
               cap_images (the film's textures scaled for the headset), volume_only
    motion     detect, instances_to_objects, deform_to_shape_keys, animated_properties, property_tracks,
               light_intensity / light_power / area_light_size / light_color (Blender's lights in three's units)
    world      bake_world_equirect (the world -> an .hdr in three's equirect convention), equirect_direction
    choreo     sample_tracks, markers, write (the guide's recipe: a piece's data into the page's JSON), quat_to_three
    landmarks  stand_at / to_table / activate / session_settings / head_pose / view_camera: Blender's own VR session
               (VR Scene Inspection), the kit's WorldRig.standAt / toTable as landmarks
    examples   EXAMPLES['city']: the kit's example.html as a Blender scene
    glb        read / write / strip_extras, summary (counts + Quest grades), sample / world_matrices / node_position /
               morph_weights / morphed_positions (a GLB read back the way three's mixer plays it)
    server     start (threads) / main: eidoverse/xr/serve.py's handler + /blender/ + a node_modules folder
    shots      shoot: eidoverse/xr/shot.mjs run and read back, still by still
    page/xr_page.html   the page export_xr copies: the GLB on the kit's rig, controls and telemetry

The kit itself (eidoverse/xr/xr_kit.js, serve.py, quest.py, shot.mjs) is used as it is.
Importing this package imports nothing (so the plain-Python modules work outside Blender): a module, or one of the
names set_xr / get_xr / survey_xr / export_xr (export) and EXAMPLES (examples), is imported on first access
(xr.export_xr(...), `from eidoblend.xr import export_xr`).
"""

import importlib

MODULES = ('export', 'materials', 'motion', 'world', 'choreo', 'landmarks', 'examples', 'glb', 'server', 'shots')
_NAMES = {'set_xr': 'export', 'get_xr': 'export', 'survey_xr': 'export', 'export_xr': 'export', 'EXAMPLES': 'examples'}


def __getattr__(name):
    if name in MODULES:
        return importlib.import_module(f'{__name__}.{name}')
    if name in _NAMES:
        return getattr(importlib.import_module(f'{__name__}.{_NAMES[name]}'), name)
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


def __dir__():
    return sorted(set(globals()) | set(MODULES) | set(_NAMES))

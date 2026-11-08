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
    export     set_xr / get_xr (the scene's XR settings), survey_xr, export_xr (the bundle), write_page,
               export_objects, unsupported (what glTF cannot hold), metaballs_to_meshes
    materials  survey / classify (what the exporter would drop), bake_for_gltf (Cycles bakes of exactly those
               channels), convert_mtoon / mtoon_to_gltf / drop_mtoon_outlines (a VRM cast), used_materials
    motion     detect, instances_to_objects, deform_to_shape_keys, animated_properties, property_tracks
    world      bake_world_equirect (the world -> an .hdr in three's equirect convention), equirect_direction
    choreo     sample_tracks, markers, write (the guide's recipe: a piece's data into the page's JSON)
    landmarks  stand_at / to_table / activate / session_settings / head_pose / view_camera: Blender's own VR session
               (VR Scene Inspection), the kit's WorldRig.standAt / toTable as landmarks
    examples   EXAMPLES['city']: the kit's example.html as a Blender scene
    glb        read / write / strip_extras, summary (counts + Quest grades), sample / world_matrices / node_position /
               morph_weights / morphed_positions (a GLB read back the way three's mixer plays it)
    server     start (threads) / main: eidoverse/xr/serve.py's handler + /blender/ + a node_modules folder
    shots      shoot: eidoverse/xr/shot.mjs run and read back, still by still
    page/xr_page.html   the page export_xr copies: the GLB on the kit's rig, controls and telemetry

The kit itself (eidoverse/xr/xr_kit.js, serve.py, quest.py, shot.mjs) is used as it is.
Importing this package imports nothing (so the plain-Python modules work outside Blender).
"""

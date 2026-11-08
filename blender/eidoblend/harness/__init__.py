"""eidoblend.harness: the Blender edition's runner and the pipeline tools a scene script uses.

    config          scene.json -> a checked config (plain Python; eido_blender.py uses it before Blender starts)
    runner          build (setup, render_frame keyed, caches stretched and baked, audits, the .blend and its inputs)
                    then render, inside Blender
    run_scene       the script eido_blender.py runs in headless Blender
    context         ctx, what setup(ctx) / render_frame(ctx, t, i) / cleanup(ctx) receive
    keying          ctx.key's keys made LINEAR (or as asked); changes render_frame made without a key, found
    settings        the film and probe EEVEE presets, the config's "render" block, bloom
    post            the engine's auto-enhance stack, its hooks and its overlay layer, on EEVEE and the compositor chain
    output          H.264 straight from EEVEE, PNG stills, .part/.prev safety, probe frames, progress lines
    ledger          eidoverse/audit_core.js, whole: the ledger, inventory, declarations, coverage, digest (plain Python)
    audits          preflight, coverage (audit_core on the scene), motion (+ locomotion on sliding feet, lipsync),
                    framing, palette (+ the showpiece nudge), asset checks
    assets          textures, PBR sets, models, clips (each file's own names and order, per-clip weights mixed in
                    the file's order), clones (that play, with their own actions if asked), kits (+ islands), glass,
                    HDRIs for lookdev
    model_preview   fetch_model.py's orientation preview rendered in Blender, with [PREVIEW_BBOX] / [ORIGIN_INFO] /
                    [KIT_INFO] in Blender's words (a script for run_blender.sh)
    render_common   render_common.mjs's helpers that mean something here: camera paths, setup_scene, alpha_composite,
                    progress lines, the ffmpeg rate controls
    gpu_check       gpu_check.mjs: hardware or software GPU, and a compute readback check (doctor runs it)
    html_mesh       the production engine's HTMLMesh: CSS-styled UI painted onto an unlit plane, 1 mm a pixel
    interior_window the production engine's interior-mapped windows: a room behind a flat quad, in EEVEE
    navigation      robot sensors, occupancy memory and the A* planner (the robot_*.js port)
    doctor          the in-Blender half of `eido_blender.py doctor`

Importing this package imports nothing: bpy is imported only by the modules that run inside Blender.
"""

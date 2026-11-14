#!/usr/bin/env bash
# tests/xr/run_all.sh: the xr tests in order, each Blender step through this checkout's run_blender.sh, as ONE GPU job
# (an estimated 6 GB of VRAM, up to 16 GB of RAM; on a shared machine queue it with EIDO_GPU_WRAP,
# blender/tests/_where.py):
#
#   bash blender/tests/xr/run_all.sh [city] [features] [tangents] [options] [cli] [films] [survey] [serve] [quest] \
#       [pages]
#
# With no arguments it runs every step:
#   city      test_xr_city.py       the kit example in Blender: EEVEE stills, VR landmarks, export, GLB checks
#   features  test_xr_features.py   a lit animated set through the whole export, number by number
#   tangents  test_xr_tangents_shadows.py   a bump baked on a mesh with its own UV map (the GLB's tangents), a sun left
#             at the origin (the page's sun shadow), an export of a scene that is not the context scene
#   options   test_xr_export_options.py     the export options the other tests leave at their defaults (motion step,
#             morph cap, no cameras, no page, a small world, the instance cap, an unlit cast, bake_all on the CPU)
#   cli       export_cli.py on the city's .blend: --survey, meshopt + WebP, Draco + JPEG (the page decodes both), the
#             bake size and world options; on the features' .blend the placement, shadow, no-bake / no-motion /
#             no-world, image cap and choreo options (CPU only); test_xr_cli.py reads every option back
#   films     test_xr_films.py      real films (product shot, crows, my robot walking, the theatre stage with its spot
#             lights, haze and camera cut), exported: the walk built by the test (_inputs.py), the other three read
#             from their families' test outputs and skipped, with the test that builds them, when those are missing
#   survey    test_xr_survey.py     survey_xr on five films (no render): a meadow and my walk built by the test, the
#             product shot, the crows and the fire teapot read when their families' tests have built them
#   serve     test_xr_serve.py      the kit's serve.py carried over (no GPU)
#   quest     test_xr_quest.py      the kit's quest.py, every command, against a stand-in adb (no GPU)
#   pages     test_xr_pages.py      every bundle in the kit page through shot.mjs, against EEVEE and the original
# Each step prints its [check] lines; the script exits 1 when any step failed.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
W="$(cd "$HERE/../../.." && pwd)"
steps="${*:-city features tangents options cli films survey serve quest pages}"
rc=0
for s in $steps; do
    echo "=== xr: $s"
    case "$s" in
        city)     bash "$W/run_blender.sh" "$HERE/test_xr_city.py" || rc=1 ;;
        features) bash "$W/run_blender.sh" "$HERE/test_xr_features.py" || rc=1 ;;
        tangents) bash "$W/run_blender.sh" "$HERE/test_xr_tangents_shadows.py" || rc=1 ;;
        options)  bash "$W/run_blender.sh" "$HERE/test_xr_export_options.py" || rc=1 ;;
        cli)
            bash "$W/run_blender.sh" "$W/blender/eidoblend/xr/export_cli.py" "$HERE/out/city/city.blend" \
                --survey || rc=1
            bash "$W/run_blender.sh" "$W/blender/eidoblend/xr/export_cli.py" "$HERE/out/city/city.blend" \
                "$HERE/out/city/vr_meshopt_webp" --compress meshopt --images WEBP --world-width 1024 || rc=1
            bash "$W/run_blender.sh" "$W/blender/eidoblend/xr/export_cli.py" "$HERE/out/city/city.blend" \
                "$HERE/out/city/vr_draco_jpeg" --compress draco --images JPEG --no-world --name city_draco || rc=1
            rm -rf "$HERE/out/city/vr_bake_sizes" "$HERE/out/city/vr_bake_cap"
            bash "$W/run_blender.sh" "$W/blender/eidoblend/xr/export_cli.py" "$HERE/out/city/city.blend" \
                "$HERE/out/city/vr_bake_sizes" --texel-density 4 --max-texture 4096 --world-frame 97 \
                --world-width 256 || rc=1
            bash "$W/run_blender.sh" "$W/blender/eidoblend/xr/export_cli.py" "$HERE/out/city/city.blend" \
                "$HERE/out/city/vr_bake_cap" --max-texture 512 --no-world || rc=1
            rm -rf "$HERE/out/features/vr_cli"
            bash "$W/run_blender.sh" "$W/blender/eidoblend/xr/export_cli.py" "$HERE/out/features/features.blend" \
                "$HERE/out/features/vr_cli" --street 0.5 --table 0.05 --start 1,-3 --facing 1,0 --name features_cli \
                --shadows --no-bake --no-motion --no-world --max-image 512 --choreo ball,cam_film || rc=1
            python "$HERE/test_xr_cli.py" || rc=1 ;;
        films)    bash "$W/run_blender.sh" "$HERE/test_xr_films.py" || rc=1 ;;
        survey)   bash "$W/run_blender.sh" "$HERE/test_xr_survey.py" || rc=1 ;;
        serve)    python "$HERE/test_xr_serve.py" || rc=1 ;;
        quest)    python "$HERE/test_xr_quest.py" || rc=1 ;;
        pages)    python "$HERE/test_xr_pages.py" || rc=1 ;;
        *)        echo "unknown step $s"; rc=2 ;;
    esac
done
exit $rc

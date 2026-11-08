#!/usr/bin/env bash
# tests/xr/run_all.sh: the xr tests in order. Run from the main checkout (run_blender.sh lives there), as ONE GPU job:
#
#   cd <main checkout> && HEAVY_VRAM_GB=6 bash work/claude_body/work/tmp/heavy.sh 16 \
#       bash <worktree>/blender/tests/xr/run_all.sh [city] [features] [cli] [films] [serve] [quest] [pages]
#
# With no arguments it runs every step:
#   city      test_xr_city.py       the kit example in Blender: EEVEE stills, VR landmarks, export, GLB checks
#   features  test_xr_features.py   a lit animated set through the whole export, number by number
#   cli       export_cli.py on the city's .blend: --survey, meshopt + WebP, Draco + JPEG (the page decodes both)
#   films     test_xr_films.py      real films round one built (product shot, crows, my robot walking), exported
#   survey    test_xr_survey.py     survey_xr on five round-one films, read only (no render)
#   serve     test_xr_serve.py      the kit's serve.py carried over (no GPU)
#   quest     test_xr_quest.py      the kit's quest.py, every command, against a stand-in adb (no GPU)
#   pages     test_xr_pages.py      every bundle in the kit page through shot.mjs, against EEVEE and the original
# Each step prints its [check] lines; the script exits 1 when any step failed.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
W="$(cd "$HERE/../../.." && pwd)"
steps="${*:-city features cli films survey serve quest pages}"
rc=0
for s in $steps; do
    echo "=== xr: $s"
    case "$s" in
        city)     bash run_blender.sh "$HERE/test_xr_city.py" || rc=1 ;;
        features) bash run_blender.sh "$HERE/test_xr_features.py" || rc=1 ;;
        cli)
            bash run_blender.sh "$W/blender/eidoblend/xr/export_cli.py" "$HERE/out/city/city.blend" --survey || rc=1
            bash run_blender.sh "$W/blender/eidoblend/xr/export_cli.py" "$HERE/out/city/city.blend" \
                "$HERE/out/city/vr_meshopt_webp" --compress meshopt --images WEBP --world-width 1024 || rc=1
            bash run_blender.sh "$W/blender/eidoblend/xr/export_cli.py" "$HERE/out/city/city.blend" \
                "$HERE/out/city/vr_draco_jpeg" --compress draco --images JPEG --no-world --name city_draco || rc=1 ;;
        films)    bash run_blender.sh "$HERE/test_xr_films.py" || rc=1 ;;
        survey)   bash run_blender.sh "$HERE/test_xr_survey.py" || rc=1 ;;
        serve)    python "$HERE/test_xr_serve.py" || rc=1 ;;
        quest)    python "$HERE/test_xr_quest.py" || rc=1 ;;
        pages)    python "$HERE/test_xr_pages.py" || rc=1 ;;
        *)        echo "unknown step $s"; rc=2 ;;
    esac
done
exit $rc

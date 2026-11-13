#!/usr/bin/env bash
# Several Blender runs in one GPU slot (glacial/slot.py runs a .sh from the main checkout):
#   bash views_and_tests.sh <views folder>
# 1. render_views.py: the photo-matched views in grey clay (<views folder>/job_clay.json, from photo_views.py)
# 2. render_textured.py: the same cameras on make_terrain with palettes and rocks (<views folder>/job_tex.json)
# 3. test_gpu.py: the package's GPU tests
# EIDO_TERRAIN_CACHE_GB keeps make_terrain from pruning the other packages' cached terrains.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
PV="$1"
export EIDO_TERRAIN_CACHE_GB="${EIDO_TERRAIN_CACHE_GB:-40}"
bash run_blender.sh "$HERE/render_views.py" --job "$PV/job_clay.json"
bash run_blender.sh "$HERE/render_textured.py" --job "$PV/job_tex.json"
bash run_blender.sh "$HERE/test_gpu.py"
echo "[views_and_tests] done"

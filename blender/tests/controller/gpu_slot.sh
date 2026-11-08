#!/usr/bin/env bash
# gpu_slot.sh <script.py> [args...]: run a Blender script through the shared GPU slot (heavy.sh, from the main
# checkout), retrying every 60 s while the slot is busy or short of VRAM ("not started"), for up to 60 minutes.
#     bash blender/tests/controller/gpu_slot.sh blender/tests/controller/render_shots.py out/TAG_shots.json
MAIN=/c/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
cd "$MAIN" || exit 2
for i in $(seq 1 60); do
    out=$(HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh "$@" 2>&1)
    code=$?
    if echo "$out" | grep -q "not started"; then
        echo "[gpu_slot] busy ($(echo "$out" | grep 'not started' | head -1 | cut -c1-140)); retry $i in 60 s"
        sleep 60
        continue
    fi
    echo "$out"
    exit $code
done
echo "[gpu_slot] gave up after 60 minutes"
exit 75

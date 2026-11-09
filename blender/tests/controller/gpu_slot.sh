#!/usr/bin/env bash
# gpu_slot.sh <script.py> [args...]: run a Blender script through the shared GPU slots (heavy.sh, heavy2.sh, heavy3.sh
# from the main checkout: the same rules, their own locks), trying each in turn and, while all three print "not started"
# (busy or short of VRAM), again every 60 s for up to 60 minutes.
#     bash blender/tests/controller/gpu_slot.sh blender/tests/controller/render_shots.py out/TAG_shots.json
MAIN=/c/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
cd "$MAIN" || exit 2
for i in $(seq 1 60); do
    for slot in heavy.sh heavy2.sh heavy3.sh; do
        [ -f "work/claude_body/work/tmp/$slot" ] || continue
        out=$(HEAVY_VRAM_GB=4 bash "work/claude_body/work/tmp/$slot" 12 bash run_blender.sh "$@" 2>&1)
        code=$?
        if echo "$out" | grep -q "not started"; then
            continue
        fi
        echo "[gpu_slot] ran in $slot"
        echo "$out"
        exit $code
    done
    echo "[gpu_slot] all slots busy; retry $i in 60 s"
    sleep 60
done
echo "[gpu_slot] gave up after 60 minutes"
exit 75

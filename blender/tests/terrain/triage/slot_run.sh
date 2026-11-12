#!/usr/bin/env bash
# Run one Blender script through a free GPU slot of the main checkout: heavy.sh, then heavy2.sh, then heavy3.sh; when
# all three refuse ("not started", exit 75), wait 60 s and try again, for up to 60 minutes. Every slot rule (the lock,
# the VRAM / RAM / disk checks, the shared ledger) stays with the heavy scripts themselves.
#
#     bash slot_run.sh <log file> <script.py> [args...]
set -u
log="$1"; shift
main=/c/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
cd "$main" || exit 2
deadline=$(( $(date +%s) + 3600 ))
while :; do
    for h in heavy heavy2 heavy3; do
        HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/$h.sh 12 bash run_blender.sh "$@" > "$log" 2>&1
        rc=$?
        if [ "$rc" -ne 75 ]; then
            echo "[slot_run] $h finished with exit $rc" >> "$log"
            exit "$rc"
        fi
    done
    if [ "$(date +%s)" -ge "$deadline" ]; then
        echo "[slot_run] no GPU slot came free in 60 minutes" >> "$log"
        exit 75
    fi
    sleep 60
done

#!/usr/bin/env bash
# Run one Blender script as a GPU job: through $EIDO_GPU_WRAP when it is set (blender/tests/_where.py: a queue that
# refuses with exit 75, "not started", while every slot is busy), waiting 60 s and trying again while it refuses, for
# up to 60 minutes; without it, Blender runs directly. Every slot rule (the lock, the VRAM / RAM / disk checks) stays
# with the queue itself.
#
#     bash slot_run.sh <log file> <script.py> [args...]
set -u
log="$1"; shift
root="$(cd "$(dirname "$0")/../../../.." && pwd)"
cd "$root" || exit 2
deadline=$(( $(date +%s) + 3600 ))
while :; do
    # the job's VRAM estimate and RAM cap; $EIDO_GPU_WRAP unquoted on purpose: a command prefix, split into words
    HEAVY_VRAM_GB=4 GPU_MEMCAP_GB=12 ${EIDO_GPU_WRAP:-} bash "$root/run_blender.sh" "$@" > "$log" 2>&1
    rc=$?
    if [ "$rc" -ne 75 ] || [ -z "${EIDO_GPU_WRAP:-}" ]; then
        echo "[slot_run] finished with exit $rc" >> "$log"
        exit "$rc"
    fi
    if [ "$(date +%s)" -ge "$deadline" ]; then
        echo "[slot_run] no GPU slot came free in 60 minutes" >> "$log"
        exit 75
    fi
    sleep 60
done

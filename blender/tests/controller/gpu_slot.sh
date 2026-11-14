#!/usr/bin/env bash
# gpu_slot.sh <script.py> [args...]: run a Blender script as a GPU job, through this checkout's run_blender.sh with
# $EIDO_GPU_WRAP's words in front when that is set (a machine's GPU queue: the command blender/tests/_where.py's
# blender_cmd builds). The arguments that name existing files are made absolute first: a queue may start the job in
# another folder.
#     bash blender/tests/controller/gpu_slot.sh blender/tests/controller/render_shots.py \
#         blender/tests/controller/out/TAG_shots.json
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
args=()
for a in "$@"; do
    if [ -e "$a" ]; then
        a="$(cd "$(dirname "$a")" && pwd)/$(basename "$a")"
    fi
    args+=("$a")
done
eval "wrap=(${EIDO_GPU_WRAP:-})"          # its words as a shell splits them (blender_cmd: shlex.split)
exec "${wrap[@]}" bash "$REPO/run_blender.sh" "${args[@]}"

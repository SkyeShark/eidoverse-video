#!/usr/bin/env bash
# The chaos floor's runs (PORT_PLAN.md 5.4, 5.5), one Blender job after another, started from this shell:
#
#     bash eidoverse/terrain/tests/parity/floor_runs.sh [--recipes a,b] [--seeds 1,2] [--patterns 0-5]
#          [--dump-seeds 1,2] [--quality draft] [--retry-failed]
#
# blender_chaos_floor.py --next names the next run that is not done (so this resumes where it stopped), and each run
# is `$EIDO_GPU_WRAP bash <Blender edition>/run_blender.sh blender_chaos_floor.py --run ...`, its output in the run's
# own blender.log. The jobs are started here and not from Python because a GPU queue may check that the shell which
# started it is still alive, which it cannot see through a Python parent.
#
# Environment (nothing here is a path of one machine):
#   EIDO_BLENDER_EDITION   the root of a checkout of the blender branch (not needed when this checkout holds blender/)
#   EIDO_BLENDER_PYTHON    Blender's own Python (numpy 2.3.4); default: beside the Blender that run_blender.sh finds
#   EIDO_GPU_WRAP          a command prefix that queues a GPU job (optional); exit code 75 from it means "every slot
#                          is busy": the run is tried again after a minute
#   EIDO_PARITY_OUT        where the runs go (default eidoverse/terrain/tests/out/parity/)
#   HEAVY_VRAM_GB, GPU_MEMCAP_GB   the queue's VRAM estimate and RAM cap for a run (defaults 4 and 8)
#   FLOOR_MAX_RUNS         stop after this many runs (default: all)
#   FLOOR_STOP_FILE        a path: when a file appears there, stop before the next run (the run in progress finishes)
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../../.." && pwd)"
if [ -d "$REPO/blender/eidoblend/terrain/core" ]; then EDITION="$REPO"; else EDITION="${EIDO_BLENDER_EDITION:-}"; fi
[ -n "$EDITION" ] && [ -d "$EDITION/blender/eidoblend/terrain/core" ] || {
    echo "floor_runs: no Blender edition: set EIDO_BLENDER_EDITION to the root of a checkout of the blender branch" >&2; exit 2; }
export EIDO_BLENDER_EDITION="$EDITION"

PY="${EIDO_BLENDER_PYTHON:-}"
if [ -z "$PY" ]; then                       # the Python bundled beside the Blender that run_blender.sh would run
    B="${BLENDER:-}"
    if [ -z "$B" ]; then
        if command -v blender >/dev/null 2>&1; then B="$(command -v blender)"; else
            for c in $(ls -d "$HOME"/Blender/*/blender.exe "/c/Program Files/Blender Foundation/"*/blender.exe \
                       /Applications/Blender.app/Contents/MacOS/Blender /usr/bin/blender /snap/bin/blender 2>/dev/null | sort -rV); do
                B="$c"; break
            done
        fi
    fi
    BD="$(dirname "$B")"
    for c in $(ls -d "$BD"/*/python/bin/python.exe "$BD"/*/python/bin/python3.[0-9][0-9] "$BD"/*/python/bin/python3.[0-9] \
               "$BD"/../Resources/*/python/bin/python3.[0-9][0-9] 2>/dev/null | sort -rV); do PY="$c"; break; done
fi
[ -n "$PY" ] && [ -e "$PY" ] || { echo "floor_runs: Blender's Python not found: set EIDO_BLENDER_PYTHON" >&2; exit 2; }

export HEAVY_VRAM_GB="${HEAVY_VRAM_GB:-4}" GPU_MEMCAP_GB="${GPU_MEMCAP_GB:-8}" PYTHONDONTWRITEBYTECODE=1

# One loop at a time per output folder: two loops would start the same run twice and write its folder together
# (it happened: a loop outlived the shell that was stopped, and a second was started beside it). The lock is a
# folder holding this shell's process id; a lock whose process is gone is taken over.
OUT_ROOT="${EIDO_PARITY_OUT:-$REPO/eidoverse/terrain/tests/out/parity}"
mkdir -p "$OUT_ROOT"
LOCK="$OUT_ROOT/.floor_runs.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
    other="$(cat "$LOCK/pid" 2>/dev/null || true)"
    if [ -n "$other" ] && kill -0 "$other" 2>/dev/null; then
        echo "floor_runs: another floor_runs.sh (process $other) is running on $OUT_ROOT: not starting a second" >&2
        exit 3
    fi
    echo "[floor_runs] taking over a lock left by a loop that is gone (process ${other:-unknown})"
fi
echo $$ > "$LOCK/pid"
trap 'rm -rf "$LOCK"' EXIT

ARGS=()
RETRY=0
for a in "$@"; do if [ "$a" = "--retry-failed" ]; then RETRY=1; else ARGS+=("$a"); fi; done
[ "$RETRY" = 1 ] && "$PY" -I "$HERE/blender_chaos_floor.py" --clear-failed "${ARGS[@]}"
MAX="${FLOOR_MAX_RUNS:-0}"
n=0
busy=0
t_all=$SECONDS
while :; do
    if [ -n "${FLOOR_STOP_FILE:-}" ] && [ -e "$FLOOR_STOP_FILE" ]; then
        echo "[floor_runs] $FLOOR_STOP_FILE exists: stopping before the next run"
        break
    fi
    mapfile -t NEXT < <("$PY" -I "$HERE/blender_chaos_floor.py" --next "${ARGS[@]}" | tr -d '\r')
    [ "${#NEXT[@]}" -ge 2 ] || break
    pdir="${NEXT[0]}"
    words=("${NEXT[@]:1}")
    t0=$SECONDS
    # shellcheck disable=SC2086  (the wrap is a command prefix: split into words on purpose)
    ( cd "$EDITION" && ${EIDO_GPU_WRAP:-} bash "$EDITION/run_blender.sh" "${words[@]}" ) > "$pdir/blender.log" 2>&1 < /dev/null
    rc=$?
    if [ "$rc" -eq 75 ]; then
        busy=$((busy + 1))
        [ "$busy" -le 240 ] || { echo "[floor_runs] every GPU slot busy for too long: stopping"; exit 75; }
        echo "[floor_runs] every GPU slot busy: waiting 60 s ($(basename "$(dirname "$pdir")")/$(basename "$pdir"))"
        sleep 60
        continue
    fi
    busy=0
    if [ -f "$pdir/done.json" ]; then
        echo "[floor_runs] $(basename "$(dirname "$pdir")")/$(basename "$pdir"): ok in $((SECONDS - t0)) s (total $(((SECONDS - t_all) / 60)) min)"
    else
        "$PY" -I "$HERE/blender_chaos_floor.py" --mark-failed "$pdir" --rc "$rc"
        echo "[floor_runs] $(basename "$(dirname "$pdir")")/$(basename "$pdir"): FAILED rc=$rc in $((SECONDS - t0)) s (see its blender.log)"
    fi
    n=$((n + 1))
    [ "$MAX" -gt 0 ] && [ "$n" -ge "$MAX" ] && break
done
echo "[floor_runs] $n run(s) in $(((SECONDS - t_all) / 60)) min"

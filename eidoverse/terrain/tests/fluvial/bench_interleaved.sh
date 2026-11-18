#!/usr/bin/env bash
# The fluvial step in both editions, back to back and interleaved, in one GPU job (PORT_PLAN.md 8.2 row P6: the step
# within 1.25 x Blender's measured cost; the lead's rule for the measurement: the two editions in the same GPU slot,
# interleaved, at least five repeats, the median ratio gated):
#
#     $EIDO_GPU_WRAP bash eidoverse/terrain/tests/fluvial/bench_interleaved.sh [repeats (5)] [out folder]
#
# Each repeat runs bench_blender.py in headless Blender (the Blender edition's run_blender.sh) and then bench_step.mjs
# in Deno, alternating, so both see the same machine load; then bench_summary.mjs writes the medians and the gate.
# The whole script is one GPU job: wrap it in the machine's queue, not its parts.
#
# Environment (nothing here is a path of one machine): EIDO_BLENDER_EDITION, the root of a checkout of the blender
# branch (not needed when this checkout holds blender/); deno on the PATH.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../../.." && pwd)"
if [ -d "$REPO/blender/eidoblend/terrain/core" ]; then EDITION="$REPO"; else EDITION="${EIDO_BLENDER_EDITION:-}"; fi
[ -n "$EDITION" ] && [ -f "$EDITION/run_blender.sh" ] || {
    echo "bench_interleaved: no Blender edition: set EIDO_BLENDER_EDITION to the root of a checkout of the blender branch" >&2; exit 2; }
export EIDO_BLENDER_EDITION="$EDITION" PYTHONDONTWRITEBYTECODE=1
REPEATS="${1:-5}"
OUT="${2:-$HERE/../out/fluvial/bench}"
mkdir -p "$OUT"
for r in $(seq 1 "$REPEATS"); do
    echo "=== repeat $r: blender"
    bash "$EDITION/run_blender.sh" "$HERE/bench_blender.py" --out "$OUT/blender_$r.json" > "$OUT/blender_$r.log" 2>&1 \
        || { echo "bench_blender.py failed (see $OUT/blender_$r.log)"; exit 1; }
    grep '\[bench\]' "$OUT/blender_$r.log"
    echo "=== repeat $r: port"
    deno run --no-config --no-lock --unstable-webgpu --allow-all "$HERE/bench_step.mjs" --out "$OUT/port_$r.json" \
        > "$OUT/port_$r.log" 2>&1 || { echo "bench_step.mjs failed (see $OUT/port_$r.log)"; exit 1; }
    grep '\[bench\]' "$OUT/port_$r.log"
done
deno run --no-config --no-lock --allow-all "$HERE/bench_summary.mjs" "$OUT" "$REPEATS"

#!/usr/bin/env bash
# render_all.sh [names...]: every robotics render test in ONE run of the shared GPU slot (one heavy.sh call):
#   catalog (all 89 entries), motion (every clip), parts (load_part), normal_parity, examples, inspector, mech_parts.
# Run it from the main checkout through the slot:
#   cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
#   HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash \
#       C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/robotics/render_all.sh [catalog motion ...]
# then the contact sheets: python blender/tests/robotics/contact_sheet.py blender/tests/robotics/out/catalog \
#   blender/tests/robotics/out/catalog_sheet.png --cols 10   (and out/motion, out/parts, out/mech_parts the same way)
here="$(cd "$(dirname "$0")" && pwd)"
names="${*:-catalog motion parts normal_parity examples inspector mech_parts studio}"
rc=0
for n in $names; do
    echo "=== $n ($(date +%H:%M:%S))"
    script="$here/test_${n}_render.py"
    [ -f "$script" ] || script="$here/test_${n}.py"
    bash run_blender.sh "$script" 2>&1 | grep -E "^(PASS|FAIL|SKIP|ALL PASS)|failed of|Traceback|Error:|^\[normal_parity\]" || rc=1
done
echo "=== done ($(date +%H:%M:%S))"
exit $rc

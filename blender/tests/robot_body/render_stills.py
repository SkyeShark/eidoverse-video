"""The stills a robot_body test listed (out/<tag>_shots.json) rendered from its saved out/<tag>.blend, so the test's CPU
run (--no-render) never holds the shared GPU slot:

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/robot_body/render_stills.py <tag> [prefix ...]

Each shot: {'name', 'frame', 'cam', 'target', 'lens'}; -> out/<tag>_<name>_f<frame>.png (_stage.render_shots: 960 x
540, 16 samples, EEVEE with ray tracing and Fast GI on). Prefixes after the tag render only the shots named so.
"""

import json
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bpy  # noqa: E402

ARGS = S.argv()
TAG, ONLY = ARGS[0], tuple(ARGS[1:])
bpy.ops.wm.open_mainfile(filepath=os.path.join(S.OUT, f'{TAG}.blend'))
shots = json.load(open(os.path.join(S.OUT, f'{TAG}_shots.json'), encoding='utf-8'))
if ONLY:
    shots = [s for s in shots if s['name'].startswith(ONLY)]
print('[render_stills]', json.dumps(S.render_shots(bpy.context.scene, TAG, shots)), flush=True)

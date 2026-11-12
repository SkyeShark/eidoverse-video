#!/usr/bin/env python3
"""tests/harness/test_fetch_preview.py: fetch_model.py's previews rendered in Blender (model_preview.py through
run_blender.sh), as a fetch and --build-previews make them. Renders (four 512 x 512 previews, 16 samples): run it
through the GPU slot. From the main checkout:

    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 python <worktree>/blender/tests/harness/test_fetch_preview.py

Copies of four models go to out/fetch_preview/ (the catalogue's own previews are never touched):
    the crow (feet at its origin, its nose curated as glTF +z), the funeral props (eleven named parts: a kit), the
    quad drone (one image for its base colour and its emission) and the shared library's stool (a Poly Haven glTF).
  - build_local_previews(models=[...]) renders the three missing previews in ONE Blender run: each lands beside its
    model, with [PREVIEW_BBOX_BLENDER], [ORIGIN_INFO] and (the props) a [KIT_INFO] naming both load_kits
  - a fetch's own preview (_render_preview, as a delivery calls it) renders the stool's and prints the same lines
  - a local delivery (_deliver_local_model) of the crow, its preview cached: the nose axis in drive_along's words, -y
LOOK at out/fetch_preview/*_preview.jpg.
"""
import io
import os
import re
import shutil
import sys
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, ROOT)
sys.dont_write_bytecode = True
sys.argv = sys.argv[:1]
for _stream in (sys.stdout, sys.stderr):                 # fetch_model prints arrows: a cp1252 console cannot
    if _stream and _stream.encoding and _stream.encoding.lower() not in ('utf-8', 'utf8'):
        _stream.reconfigure(encoding='utf-8', errors='replace')
OUT = os.path.join(HERE, 'out', 'fetch_preview')
MODELS = os.path.join(ROOT, 'eidoverse', 'assets', 'models')
FAIL = []


def check(ok, what):
    print(f"[fetch_preview] {'PASS' if ok else 'FAIL'}: {what}", flush=True)
    if not ok:
        FAIL.append(what)


def captured(fn, *a, **k):
    buf = io.StringIO()
    with redirect_stdout(buf):
        r = fn(*a, **k)
    text = buf.getvalue()
    print(text, flush=True)
    return r, text


def main():
    import fetch_model as fm
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    names = ['crow_bird_animated_corvid_raven_black_cawing_flying_walking.glb', 'funeral_props.glb',
             'scifi_quad_small_drone_blue.glb']
    copies = []
    for n in names:
        shutil.copy2(os.path.join(MODELS, n), os.path.join(OUT, n))
        copies.append(os.path.join(OUT, n))
    cache = os.environ.get('EIDO_ASSET_CACHE') or os.path.join(ROOT, 'eidoverse', 'assets', 'cache')
    stool_src = os.path.join(cache, 'models', 'wooden_stool_01_1k', 'wooden_stool_01_embedded.gltf')
    stool = os.path.join(OUT, 'wooden_stool_01_embedded.gltf')
    shutil.copy2(stool_src, stool)

    made, text = captured(fm.build_local_previews, models=copies)
    check(len(made) == 3 and all(os.path.getsize(p) > 20000 for p in made.values()),
          f'build_local_previews: {len(made)}/3 previews from one Blender run, each beside its model')
    check(text.count('] Blender: ') == 1, 'one Blender run for the batch')

    def lines_of(name):
        m = re.search(rf'\n  {re.escape(name)}: [^\n]*\n((?:    [^\n]*\n)*)', text)
        return m.group(1) if m else ''
    crow, props = lines_of(names[0]), lines_of(names[1])
    check('[PREVIEW_BBOX_BLENDER]' in crow and '[ORIGIN_INFO] Pivot/origin: at the BASE' in crow,
          'the crow: its size in Blender\'s axes and its pivot at the BASE (feet at the origin)')
    kit = re.search(r'\[KIT_INFO\][^\n]*', props)
    check(kit and 'LIKELY A MODULAR KIT' in kit.group(0) and 'eidoblend.harness.assets.load_kit' in kit.group(0)
          and 'eidoblend.placement.load_kit' in kit.group(0),
          f"the funeral props read as a kit, both load_kits named: {kit.group(0)[:120] if kit else 'no [KIT_INFO]'}")

    p, text = captured(fm._render_preview, stool)
    check(p and os.path.exists(p) and os.path.basename(p) == 'wooden_stool_01_embedded_preview.jpg'
          and '[PREVIEW_BBOX_BLENDER]' in text and '[ORIGIN_INFO]' in text and 'Deno' not in text,
          f'a delivery\'s preview, in Blender (no WebGPU fallback): {p}')
    bb = re.search(r'\[PREVIEW_BBOX_BLENDER\] (\S+) (\S+) (\S+)', text)
    z = float(bb.group(3)) if bb else 0.0
    check(0.35 < z < 0.55, f'the stool stands {z:.3f} m tall, Z up (real scale)')

    _r, text = captured(fm._deliver_local_model, copies[0])
    check("drive_along / face_toward forward axis: '-y'" in text and "forward='-y'" in text and 'Preview:' in text,
          'a local delivery of the crow: its cached preview, and its nose axis in drive_along\'s words (-y)')
    for c in copies + [stool]:
        os.remove(c)                                  # the previews stay to LOOK at; the model copies go


if __name__ == '__main__':
    try:
        main()
    except Exception as e:                                           # noqa: BLE001
        import traceback
        traceback.print_exc()
        check(False, f'raised {type(e).__name__}: {e}')
    print(f"[fetch_preview] {'ALL PASS' if not FAIL else f'{len(FAIL)} FAIL'}", flush=True)
    sys.exit(1 if FAIL else 0)

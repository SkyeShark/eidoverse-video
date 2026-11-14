"""The Blender numpy twins' kernel fixtures for the runner package's tests (runner_test.mjs, bench_runner.mjs,
scene_device_test.mjs): tests/design_probes/make_twin_fixtures.py run as it is, by Blender's own Python, with the
Python, numpy and zlib versions added to its manifest (PORT_PLAN.md 5.1, C6). P3's tests/parity/fixtures.py
--kernels takes this over once it lands.

    <Blender's python> -I eidoverse/terrain/tests/core_runner/twin_fixtures.py [out_dir]

The default out_dir is tests/out/core_runner/twin_fixtures/. The Blender edition is found as make_twin_fixtures.py
finds it: blender/ beside eidoverse/ in this checkout, else $EIDO_BLENDER_EDITION.
"""
import json
import os
import runpy
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'out', 'core_runner', 'twin_fixtures')
PROBE = os.path.join(HERE, '..', 'design_probes', 'make_twin_fixtures.py')

sys.argv = [PROBE, OUT]
runpy.run_path(PROBE, run_name='__main__')

import numpy as np  # noqa: E402  (the probe imported it)

path = os.path.join(OUT, 'manifest.json')
with open(path, encoding='utf-8') as f:
    man = json.load(f)
man.update(made_by='tests/design_probes/make_twin_fixtures.py', python=sys.version.split()[0], numpy=np.__version__,
           zlib=zlib.ZLIB_RUNTIME_VERSION, python_executable=os.path.basename(sys.executable))
with open(path, 'w', encoding='utf-8') as f:
    json.dump(man, f, indent=1)
print(f'[twin_fixtures] Python {man["python"]}, numpy {man["numpy"]}, zlib {man["zlib"]}: {len(man["cases"])} cases -> {OUT}')

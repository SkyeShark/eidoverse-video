"""Design probe (PORT_PLAN.md C9 and 10.1), the Python half: a heightmap PNG's IDAT payload as Blender's
core/io.py encode_png makes it (16-bit, half-up quantisation, big-endian rows, the Up filter), and the running
Python's zlib.compress(payload, 6) of it, named by that zlib's version. Run it under each Python to compare (Blender's
bundled Python with `-I`, and any other), then deflate_vs_zlib.mjs <out_dir>.

    <python> -I eidoverse/terrain/tests/design_probes/zlib_payload.py <out_dir> [<npz with 'h'>]

Without an npz the field is a seeded sum of sines (1024 x 1024), so the payload is the same on every machine.
"""
import json
import os
import sys
import zlib

import numpy as np

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
if len(sys.argv) > 2:
    h = np.load(sys.argv[2])['h'].astype(np.float64)
else:
    y, x = np.mgrid[0:1024, 0:1024] / 1024.0
    rng = np.random.default_rng(7)
    h = sum(a * np.sin(2 * np.pi * (fx * x + fy * y) + p)
            for a, fx, fy, p in zip(rng.random(12) * 300, rng.integers(1, 40, 12), rng.integers(1, 40, 12),
                                    rng.random(12) * 6.3))
t = (h - h.min()) / (h.max() - h.min())
q = np.clip(np.floor(t * 65535 + 0.5), 0, 65535).astype('>u2')          # io.py's _round_half_up, big-endian
raw = np.ascontiguousarray(q).view(np.uint8).reshape(q.shape[0], -1)
filt = np.empty((raw.shape[0], raw.shape[1] + 1), np.uint8)
filt[:, 0] = 2                                                             # encode_png: every row Up-filtered
filt[0, 1:] = raw[0]
filt[1:, 1:] = raw[1:] - raw[:-1]
payload = filt.tobytes()
with open(os.path.join(out, 'payload.bin'), 'wb') as f:
    f.write(payload)
name = f'payload.zlib_{zlib.ZLIB_RUNTIME_VERSION}.z6'
z = zlib.compress(payload, 6)
with open(os.path.join(out, name), 'wb') as f:
    f.write(z)
print(json.dumps({'python': sys.version.split()[0], 'zlib': zlib.ZLIB_RUNTIME_VERSION, 'numpy': np.__version__,
                  'payload_bytes': len(payload), 'file': name, 'compressed_bytes': len(z)}))

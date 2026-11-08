"""Print channel statistics of EXR files, and optionally save a tone-mapped PNG preview beside each.

    blender --background --factory-startup --python blender/tests/sky/inspect_exr.py -- [--png] a.exr b.exr ...
(no GPU work: OpenImageIO only)
"""
import sys

import numpy as np
import OpenImageIO as oiio

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
png = '--png' in argv
for path in [a for a in argv if not a.startswith('--')]:
    buf = oiio.ImageBuf(path)
    a = np.asarray(buf.get_pixels(oiio.FLOAT))
    names = buf.spec().channelnames
    print(path, a.shape, names)
    for c, n in enumerate(names):
        ch = a[..., c]
        print('   %s min %.4f mean %.4f max %.4f  p01 %.4f p99 %.4f' % (
            n, ch.min(), ch.mean(), ch.max(), np.percentile(ch, 1), np.percentile(ch, 99)))
    if png:
        rgb = a[..., :3] if a.shape[2] >= 3 else np.repeat(a[..., :1], 3, axis=2)
        x = rgb / (1.0 + rgb)                                  # simple Reinhard, display only
        x = np.clip(x, 0, 1) ** (1 / 2.2)
        out = oiio.ImageBuf(oiio.ImageSpec(a.shape[1], a.shape[0], 3, 'uint8'))
        out.set_pixels(oiio.ROI(), x.astype(np.float32))
        out.write(path[:-4] + '_preview.png')

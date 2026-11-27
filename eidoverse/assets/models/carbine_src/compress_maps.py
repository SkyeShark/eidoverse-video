"""compress_maps.py: every PNG in a folder stored again, losslessly smaller (plain Python with Pillow).

    python eidoverse/assets/models/carbine_src/compress_maps.py work/props/carbine/web

The pixels are unchanged (each file is checked after it is written); the GPU bake writes its maps quickly with light
compression, and the library keeps them at the best zlib level.
"""
import os
import sys

import numpy as np
from PIL import Image


def main(folder):
    for n in sorted(os.listdir(folder)):
        if not n.lower().endswith('.png'):
            continue
        p = os.path.join(folder, n)
        im = Image.open(p)
        im.load()
        a = np.asarray(im)
        before = os.path.getsize(p)
        tmp = p + '.tmp.png'
        im.save(tmp, optimize=True)
        if not np.array_equal(np.asarray(Image.open(tmp)), a):
            os.remove(tmp)
            raise SystemExit(f'{n}: the re-stored pixels differ; left as it was')
        os.replace(tmp, p)
        print(f'{n}: {before / 1e6:.2f} MB -> {os.path.getsize(p) / 1e6:.2f} MB')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])

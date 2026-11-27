"""measure_cc0_sets.py: a CC0 manifest's sets measured, so a material can divide a photograph by its own mean. System
Python with numpy and Pillow (no Blender):

    python blender/tools/measure_cc0_sets.py blender/eidoblend/sets/town/cc0_sets.json [--fetch]

A manifest (the town's and the desert's cc0_sets.json) names each set by its library ID and resolution ('id', 'res'),
with its real size in metres ('tile') and its displacement's range ('relief'). For every set found in the shared
library (eidoverse/assets/cache/textures/<id>_<res>/, or EIDO_ASSET_CACHE's; --fetch runs fetch_texture.py --cache
for a missing one) this writes back into the manifest:
  mean      the mean LINEAR colour of its colour map (sRGB decoded, over a 512 x 512 reduction)
  contrast  its luminance's standard deviation over its mean
The materials divide a set's colour by its mean, so the photograph keeps its grain, stains and hue shifts about 1 and
each surface takes its own tint (sets/town/materials.py ncol). A set it cannot find is listed and left as it was.
"""
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))


def library():
    return os.path.join(os.environ.get('EIDO_ASSET_CACHE') or os.path.join(REPO, 'eidoverse', 'assets', 'cache'), 'textures')


def colour_map(d):
    """the set's colour map: tex_urls.json's 'diff' beside it, else the usual names"""
    js = os.path.join(d, 'tex_urls.json')
    if os.path.isfile(js):
        f = json.load(open(js, encoding='utf-8')).get('diff')
        if f:
            p = os.path.join(d, os.path.basename(str(f).replace('\\', '/')))
            if os.path.isfile(p):
                return p
    for n in sorted(os.listdir(d)):
        if n.lower().endswith(('_color.jpg', '_diff.jpg', '_diff.png', '_color.png')):
            return os.path.join(d, n)
    return None


def measure(path):
    a = np.asarray(Image.open(path).convert('RGB').resize((512, 512)), np.float32) / 255.0
    lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    lum = lin @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    return [round(float(x), 5) for x in lin.reshape(-1, 3).mean(0)], round(float(lum.std() / max(lum.mean(), 1e-4)), 3)


def main(a):
    manifest = a[0]
    doc = json.load(open(manifest, encoding='utf-8'))
    missing = []
    for k, s in doc['sets'].items():
        d = os.path.join(library(), f"{s['id']}_{s['res']}")
        if not os.path.isdir(d) and '--fetch' in a:
            subprocess.run([sys.executable, os.path.join(REPO, 'fetch_texture.py'), s['id'], s['res'], '--cache'], cwd=REPO)
        p = colour_map(d) if os.path.isdir(d) else None
        if p is None:
            missing.append(f"{k} ({s['id']} {s['res']})")
            continue
        s['mean'], s['contrast'] = measure(p)
        print(f"{k:16s} {s['id']:24s} {s['res']}  tile {s['tile'][0]}x{s['tile'][1]} m  mean {s['mean']}  contrast {s['contrast']}")
    with open(manifest, 'w', encoding='utf-8') as f:
        json.dump(doc, f, indent=1)
        f.write('\n')
    print(f'wrote {manifest}: {len(doc["sets"]) - len(missing)} measured' + (f'; not in the library: {", ".join(missing)}' if missing else ''))
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1:]))
